"""Durable PostgreSQL lifecycle primitives for conversation turns."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message, Session, SessionTurn

AsyncSessionFactory = Callable[[], AsyncSession]
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TurnStatus(StrEnum):
    RUNNING = "RUNNING"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"


class SessionTurnError(RuntimeError):
    """Base class for durable session-turn admission failures."""


class InvalidSessionTurn(ValueError):
    """The caller supplied an invalid durable turn value."""


class SessionNotFound(SessionTurnError):
    """The tenant does not own the requested durable session."""


class SessionVersionConflict(SessionTurnError):
    def __init__(self, *, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"session version conflict: expected {expected_version}, actual {actual_version}"
        )


class SessionTurnActive(SessionTurnError):
    def __init__(self, active_turn_id: str) -> None:
        self.active_turn_id = active_turn_id
        super().__init__("another turn is already active for this session")


class SessionTurnDeadlineElapsed(SessionTurnError):
    """The requested admission deadline has already elapsed on the DB clock."""


class SessionTurnIdempotencyConflict(SessionTurnError):
    """A tenant turn id was already bound to another request digest."""


class SessionTurnNotFound(SessionTurnError):
    """The tenant does not own the requested durable turn."""


class SessionTurnFenceConflict(SessionTurnError):
    """The supplied session/epoch token no longer owns the turn."""


class SessionTurnTerminalConflict(SessionTurnError):
    """A terminal turn cannot be overwritten by a different outcome."""


@dataclass(frozen=True, slots=True)
class SessionTurnSnapshot:
    tenant_id: str
    turn_id: str
    session_id: UUID
    request_digest: str
    expected_version: int
    turn_epoch: int
    status: TurnStatus
    admitted_at: datetime
    deadline_at: datetime
    terminal_at: datetime | None
    result_digest: str | None
    committed_version: int | None


@dataclass(frozen=True, slots=True)
class TurnAdmissionOutcome:
    turn: SessionTurnSnapshot
    admitted: bool


@dataclass(frozen=True, slots=True)
class TurnAbortOutcome:
    turn: SessionTurnSnapshot
    changed: bool


@dataclass(frozen=True, slots=True)
class SessionMessageSnapshot:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class SessionHistorySnapshot:
    tenant_id: str
    session_id: UUID
    version: int
    messages: tuple[SessionMessageSnapshot, ...]


@dataclass(frozen=True, slots=True)
class TurnCommitOutcome:
    turn: SessionTurnSnapshot
    changed: bool


def _require_text(value: str, *, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise InvalidSessionTurn(f"{field} must be non-empty without surrounding whitespace")
    if len(value) > max_length:
        raise InvalidSessionTurn(f"{field} exceeds {max_length} characters")
    return value


def _require_digest(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise InvalidSessionTurn(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _require_expected_version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidSessionTurn("expected_version must be a non-negative integer")
    return value


def _require_turn_epoch(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidSessionTurn("turn_epoch must be a positive integer")
    return value


def _require_deadline(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidSessionTurn("deadline_at must be timezone-aware")
    return value


def _require_message_content(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidSessionTurn(f"{field} must be a non-empty string")
    return value


def _message_pair_digest(
    request_digest: str,
    user_content: str,
    assistant_content: str,
) -> str:
    payload = json.dumps(
        {
            "domain": "session-terminal-pair-v1",
            "request_digest": request_digest,
            "messages": (("user", user_content), ("assistant", assistant_content)),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _snapshot(record: SessionTurn) -> SessionTurnSnapshot:
    return SessionTurnSnapshot(
        tenant_id=record.tenant_id,
        turn_id=record.turn_id,
        session_id=record.session_id,
        request_digest=record.request_digest,
        expected_version=record.expected_version,
        turn_epoch=record.turn_epoch,
        status=TurnStatus(record.status),
        admitted_at=record.admitted_at,
        deadline_at=record.deadline_at,
        terminal_at=record.terminal_at,
        result_digest=record.result_digest,
        committed_version=record.committed_version,
    )


async def set_session_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Bind tenant-owned session-turn rows to the current transaction only."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )


async def _lock_turn_identity(
    session: AsyncSession,
    *,
    tenant_id: str,
    turn_id: str,
) -> None:
    identity = f"{len(tenant_id)}:{tenant_id}{turn_id}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
        {"identity": identity},
    )


async def _database_now(session: AsyncSession) -> datetime:
    value = await session.scalar(select(func.clock_timestamp()))
    if not isinstance(value, datetime):
        raise RuntimeError("PostgreSQL clock_timestamp() did not return a datetime")
    return value


class SessionService:
    """Short-transaction owner of durable session-turn state and history."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def admit_turn(
        self,
        *,
        tenant_id: str,
        session_id: UUID | None,
        turn_id: str,
        request_digest: str,
        expected_version: int,
        deadline_at: datetime,
    ) -> TurnAdmissionOutcome:
        tenant = _require_text(tenant_id, field="tenant_id", max_length=50)
        identity = _require_text(turn_id, field="turn_id", max_length=128)
        digest = _require_digest(request_digest, field="request_digest")
        version = _require_expected_version(expected_version)
        deadline = _require_deadline(deadline_at)
        if session_id is not None and not isinstance(session_id, UUID):
            raise InvalidSessionTurn("session_id must be a UUID or None")

        async with self._session_factory() as db, db.begin():
            await set_session_tenant_context(db, tenant)
            await _lock_turn_identity(db, tenant_id=tenant, turn_id=identity)
            existing = await db.scalar(
                select(SessionTurn)
                .where(
                    SessionTurn.tenant_id == tenant,
                    SessionTurn.turn_id == identity,
                )
                .with_for_update()
            )
            if existing is not None:
                if existing.request_digest != digest or (
                    session_id is not None and existing.session_id != session_id
                ):
                    raise SessionTurnIdempotencyConflict(
                        "turn id is already bound to another request or session"
                    )
                return TurnAdmissionOutcome(turn=_snapshot(existing), admitted=False)

            if session_id is None:
                if version != 0:
                    raise SessionVersionConflict(expected_version=version, actual_version=0)
                actual_session_id = uuid4()
                session_record = Session(
                    id=actual_session_id,
                    tenant_id=tenant,
                    version=0,
                    turn_epoch=0,
                )
                db.add(session_record)
                await db.flush()
            else:
                actual_session_id = session_id
                existing_session = await db.scalar(
                    select(Session)
                    .where(
                        Session.id == actual_session_id,
                        Session.tenant_id == tenant,
                    )
                    .with_for_update()
                )
                if existing_session is None:
                    raise SessionNotFound("session was not found for tenant")
                session_record = existing_session

            if session_record.version != version:
                raise SessionVersionConflict(
                    expected_version=version,
                    actual_version=session_record.version,
                )

            active = await db.scalar(
                select(SessionTurn)
                .where(
                    SessionTurn.tenant_id == tenant,
                    SessionTurn.session_id == actual_session_id,
                    SessionTurn.status == TurnStatus.RUNNING.value,
                )
                .with_for_update()
            )
            database_now = await _database_now(db)
            if active is not None:
                if active.deadline_at > database_now:
                    raise SessionTurnActive(active.turn_id)
                active.status = TurnStatus.EXPIRED.value
                active.terminal_at = database_now

            if deadline <= database_now:
                raise SessionTurnDeadlineElapsed(
                    "turn deadline has already elapsed on the PostgreSQL clock"
                )

            session_record.turn_epoch += 1
            admitted = SessionTurn(
                tenant_id=tenant,
                turn_id=identity,
                session_id=actual_session_id,
                request_digest=digest,
                expected_version=version,
                turn_epoch=session_record.turn_epoch,
                status=TurnStatus.RUNNING.value,
                admitted_at=database_now,
                deadline_at=deadline,
                terminal_at=None,
                result_digest=None,
                committed_version=None,
            )
            db.add(admitted)
            await db.flush()
            return TurnAdmissionOutcome(turn=_snapshot(admitted), admitted=True)

    async def abort_turn(
        self,
        *,
        tenant_id: str,
        session_id: UUID,
        turn_id: str,
        turn_epoch: int,
    ) -> TurnAbortOutcome:
        tenant = _require_text(tenant_id, field="tenant_id", max_length=50)
        identity = _require_text(turn_id, field="turn_id", max_length=128)
        epoch = _require_turn_epoch(turn_epoch)
        if not isinstance(session_id, UUID):
            raise InvalidSessionTurn("session_id must be a UUID")

        async with self._session_factory() as db, db.begin():
            await set_session_tenant_context(db, tenant)
            session_record = await db.scalar(
                select(Session)
                .where(
                    Session.id == session_id,
                    Session.tenant_id == tenant,
                )
                .with_for_update()
            )
            if session_record is None:
                raise SessionNotFound("session was not found for tenant")
            if session_record.turn_epoch != epoch:
                raise SessionTurnFenceConflict("session turn epoch no longer matches")

            turn = await db.scalar(
                select(SessionTurn)
                .where(
                    SessionTurn.tenant_id == tenant,
                    SessionTurn.turn_id == identity,
                )
                .with_for_update()
            )
            if turn is None:
                raise SessionTurnNotFound("turn was not found for tenant")
            if turn.session_id != session_id or turn.turn_epoch != epoch:
                raise SessionTurnFenceConflict("turn fencing token does not match")
            if turn.status == TurnStatus.ABORTED.value:
                return TurnAbortOutcome(turn=_snapshot(turn), changed=False)
            if turn.status != TurnStatus.RUNNING.value:
                raise SessionTurnTerminalConflict(
                    "committed or expired turn cannot transition to aborted"
                )

            turn.status = TurnStatus.ABORTED.value
            turn.terminal_at = await _database_now(db)
            await db.flush()
            return TurnAbortOutcome(turn=_snapshot(turn), changed=True)

    async def commit_turn(
        self,
        *,
        tenant_id: str,
        session_id: UUID,
        turn_id: str,
        turn_epoch: int,
        request_digest: str,
        user_content: str,
        assistant_content: str,
    ) -> TurnCommitOutcome:
        tenant = _require_text(tenant_id, field="tenant_id", max_length=50)
        identity = _require_text(turn_id, field="turn_id", max_length=128)
        epoch = _require_turn_epoch(turn_epoch)
        request = _require_digest(request_digest, field="request_digest")
        user_message = _require_message_content(user_content, field="user_content")
        assistant_message = _require_message_content(
            assistant_content,
            field="assistant_content",
        )
        if not isinstance(session_id, UUID):
            raise InvalidSessionTurn("session_id must be a UUID")
        result_digest = _message_pair_digest(request, user_message, assistant_message)

        async with self._session_factory() as db, db.begin():
            await set_session_tenant_context(db, tenant)
            session_record = await db.scalar(
                select(Session)
                .where(
                    Session.id == session_id,
                    Session.tenant_id == tenant,
                )
                .with_for_update()
            )
            if session_record is None:
                raise SessionNotFound("session was not found for tenant")

            turn = await db.scalar(
                select(SessionTurn)
                .where(
                    SessionTurn.tenant_id == tenant,
                    SessionTurn.turn_id == identity,
                )
                .with_for_update()
            )
            if turn is None:
                raise SessionTurnNotFound("turn was not found for tenant")
            if turn.session_id != session_id or turn.turn_epoch != epoch:
                raise SessionTurnFenceConflict("turn fencing token does not match")
            if turn.request_digest != request:
                raise SessionTurnIdempotencyConflict(
                    "turn is already bound to another request digest"
                )
            if turn.status == TurnStatus.COMMITTED.value:
                if turn.result_digest != result_digest:
                    raise SessionTurnTerminalConflict(
                        "committed turn is bound to a different terminal result"
                    )
                return TurnCommitOutcome(turn=_snapshot(turn), changed=False)
            if turn.status != TurnStatus.RUNNING.value:
                raise SessionTurnTerminalConflict(
                    "aborted or expired turn cannot transition to committed"
                )
            if session_record.turn_epoch != epoch:
                raise SessionTurnFenceConflict("session turn epoch no longer matches")
            if session_record.version != turn.expected_version:
                raise SessionVersionConflict(
                    expected_version=turn.expected_version,
                    actual_version=session_record.version,
                )

            database_now = await _database_now(db)
            if turn.deadline_at <= database_now:
                raise SessionTurnDeadlineElapsed(
                    "turn deadline has elapsed on the PostgreSQL clock"
                )

            db.add_all(
                (
                    Message(
                        session_id=session_id,
                        tenant_id=tenant,
                        role="user",
                        content=user_message,
                        created_at=database_now,
                    ),
                    Message(
                        session_id=session_id,
                        tenant_id=tenant,
                        role="assistant",
                        content=assistant_message,
                        created_at=database_now,
                    ),
                )
            )
            session_record.version += 1
            turn.status = TurnStatus.COMMITTED.value
            turn.terminal_at = database_now
            turn.result_digest = result_digest
            turn.committed_version = session_record.version
            await db.flush()
            return TurnCommitOutcome(turn=_snapshot(turn), changed=True)

    async def load_history(
        self,
        *,
        tenant_id: str,
        session_id: UUID,
    ) -> SessionHistorySnapshot:
        tenant = _require_text(tenant_id, field="tenant_id", max_length=50)
        if not isinstance(session_id, UUID):
            raise InvalidSessionTurn("session_id must be a UUID")

        async with self._session_factory() as db, db.begin():
            await set_session_tenant_context(db, tenant)
            session_record = await db.scalar(
                select(Session)
                .where(
                    Session.id == session_id,
                    Session.tenant_id == tenant,
                )
                .with_for_update(read=True)
            )
            if session_record is None:
                raise SessionNotFound("session was not found for tenant")
            records = await db.scalars(
                select(Message)
                .where(
                    Message.session_id == session_id,
                    Message.tenant_id == tenant,
                )
                .order_by(Message.id)
            )
            messages = tuple(
                SessionMessageSnapshot(role=record.role, content=record.content)
                for record in records
            )
            return SessionHistorySnapshot(
                tenant_id=tenant,
                session_id=session_id,
                version=session_record.version,
                messages=messages,
            )


__all__ = [
    "InvalidSessionTurn",
    "SessionNotFound",
    "SessionHistorySnapshot",
    "SessionMessageSnapshot",
    "SessionService",
    "SessionTurnActive",
    "SessionTurnDeadlineElapsed",
    "SessionTurnError",
    "SessionTurnFenceConflict",
    "SessionTurnIdempotencyConflict",
    "SessionTurnNotFound",
    "SessionTurnSnapshot",
    "SessionTurnTerminalConflict",
    "SessionVersionConflict",
    "TurnAbortOutcome",
    "TurnAdmissionOutcome",
    "TurnCommitOutcome",
    "TurnStatus",
    "set_session_tenant_context",
]
