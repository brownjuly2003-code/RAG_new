from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import services.session as session_module
from db.models import Session, SessionTurn
from services.session import (
    AsyncSessionFactory,
    SessionService,
    SessionTurnActive,
    SessionTurnIdempotencyConflict,
    TurnStatus,
)


class _AsyncContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeSession:
    def __init__(self, scalar_results: list[object]) -> None:
        self._scalar_results = iter(scalar_results)
        self.scalar_events: list[str] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def begin(self) -> _AsyncContext:
        return _AsyncContext()

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def scalar(self, _statement: object) -> Any:
        self.scalar_events.append(f"scalar-{len(self.scalar_events) + 1}")
        return next(self._scalar_results)


def _factory(fake_session: _FakeSession) -> AsyncSessionFactory:
    return cast(AsyncSessionFactory, lambda: cast(AsyncSession, fake_session))


def _running_turn(*, session_id=None) -> SessionTurn:
    admitted_at = datetime.now(UTC)
    return SessionTurn(
        tenant_id="tenant-a",
        turn_id="same-key",
        session_id=session_id or uuid4(),
        request_digest="a" * 64,
        expected_version=0,
        turn_epoch=1,
        status=TurnStatus.RUNNING.value,
        admitted_at=admitted_at,
        deadline_at=admitted_at + timedelta(minutes=5),
        terminal_at=None,
        result_digest=None,
        committed_version=None,
    )


@pytest.mark.asyncio
async def test_replay_rejects_an_explicitly_different_session_but_recovers_first_session() -> None:
    existing = _running_turn()
    fake_session = _FakeSession([existing, existing])
    service = SessionService(_factory(fake_session))

    with pytest.raises(SessionTurnIdempotencyConflict):
        await service.admit_turn(
            tenant_id=existing.tenant_id,
            session_id=uuid4(),
            turn_id=existing.turn_id,
            request_digest=existing.request_digest,
            expected_version=0,
            deadline_at=existing.deadline_at,
        )

    recovered = await service.admit_turn(
        tenant_id=existing.tenant_id,
        session_id=None,
        turn_id=existing.turn_id,
        request_digest=existing.request_digest,
        expected_version=99,
        deadline_at=existing.deadline_at,
    )
    assert recovered.admitted is False
    assert recovered.turn.session_id == existing.session_id


@pytest.mark.asyncio
async def test_admission_reads_database_clock_after_locking_the_active_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid4()
    session_record = Session(
        id=session_id,
        tenant_id="tenant-a",
        version=0,
        turn_epoch=1,
    )
    active = _running_turn(session_id=session_id)
    fake_session = _FakeSession([None, session_record, active])
    events = fake_session.scalar_events
    database_now = datetime.now(UTC)

    async def _record_database_now(_session: AsyncSession) -> datetime:
        events.append("clock")
        return database_now

    monkeypatch.setattr(session_module, "_database_now", _record_database_now)
    service = SessionService(_factory(fake_session))

    with pytest.raises(SessionTurnActive):
        await service.admit_turn(
            tenant_id=session_record.tenant_id,
            session_id=session_id,
            turn_id="competing-key",
            request_digest="b" * 64,
            expected_version=0,
            deadline_at=database_now + timedelta(minutes=5),
        )

    assert events == ["scalar-1", "scalar-2", "scalar-3", "clock"]
