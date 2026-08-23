from __future__ import annotations

import asyncio
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from db.models import Message, Session, SessionTurn
from services.session import (
    SessionHistorySnapshot,
    SessionMessageSnapshot,
    SessionNotFound,
    SessionService,
    SessionTurnActive,
    SessionTurnDeadlineElapsed,
    SessionTurnFenceConflict,
    SessionTurnIdempotencyConflict,
    SessionTurnTerminalConflict,
    SessionVersionConflict,
    TurnCommitOutcome,
    TurnStatus,
    set_session_tenant_context,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATABASE_PATTERN = re.compile(r"^rag_session_turns_b_[0-9a-f]{12}$")
_RUNTIME_ROLE_PATTERN = re.compile(r"^rag_session_runtime_[0-9a-f]{12}$")
_TEST_ENCRYPTION_KEY = "session-turn-test-key-32-chars!!"
_TENANT_A = "tenant-session-a"
_TENANT_B = "tenant-session-b"


def _selects_session(statement: Any) -> bool:
    return any(
        description.get("entity") is Session
        for description in getattr(statement, "column_descriptions", ())
    )


class _SessionSelectBarrier(AsyncSession):
    def __init__(
        self,
        *args: Any,
        session_select_barrier: asyncio.Barrier,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._session_select_barrier = session_select_barrier
        self._session_select_waited = False

    async def scalar(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if not self._session_select_waited and _selects_session(statement):
            self._session_select_waited = True
            await self._session_select_barrier.wait()
        return await super().scalar(statement, *args, **kwargs)


class _PausedSnapshotSession(AsyncSession):
    def __init__(
        self,
        *args: Any,
        snapshot_locked: asyncio.Event,
        release_snapshot: asyncio.Event,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._snapshot_locked = snapshot_locked
        self._release_snapshot = release_snapshot
        self._snapshot_paused = False

    async def scalar(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        result = await super().scalar(statement, *args, **kwargs)
        if not self._snapshot_paused and _selects_session(statement):
            self._snapshot_paused = True
            self._snapshot_locked.set()
            await self._release_snapshot.wait()
        return result


class _ObservedCommitSession(AsyncSession):
    def __init__(
        self,
        *args: Any,
        backend_pid: asyncio.Future[int],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._backend_pid = backend_pid
        self._backend_pid_recorded = False

    async def scalar(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if not self._backend_pid_recorded and _selects_session(statement):
            self._backend_pid_recorded = True
            connection = await self.connection()
            process_id = await connection.scalar(text("SELECT pg_backend_pid()"))
            self._backend_pid.set_result(int(process_id))
        return await super().scalar(statement, *args, **kwargs)


@pytest.fixture(scope="module", autouse=True)
def session_encryption_environment() -> Iterator[None]:
    patcher = pytest.MonkeyPatch()
    patcher.setenv("DB_ENCRYPTION_KEY", _TEST_ENCRYPTION_KEY)
    try:
        yield
    finally:
        patcher.undo()


def _sync_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("session service integration tests require PostgreSQL")
    return url.set(drivername="postgresql+psycopg2")


def _async_url(url: URL) -> str:
    return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


def _run_alembic(database_url: URL, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    environment["DB_ENCRYPTION_KEY"] = _TEST_ENCRYPTION_KEY
    process = subprocess.run(
        ["alembic", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(arguments)} failed:\n{process.stdout}\n{process.stderr}"
        )


@contextmanager
def _temporary_database() -> Iterator[URL]:
    explicit_url = os.environ.get("SESSION_TURN_TEST_DATABASE_URL", "").strip()
    if explicit_url:
        database_url = _sync_url(explicit_url)
        if (
            database_url.database is None
            or _DATABASE_PATTERN.fullmatch(database_url.database) is None
        ):
            raise RuntimeError(
                "SESSION_TURN_TEST_DATABASE_URL must name a disposable "
                "rag_session_turns_b_* database"
            )
        yield database_url
        return

    source_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise RuntimeError("DATABASE_URL or SESSION_TURN_TEST_DATABASE_URL is required")
    source = _sync_url(source_url)
    database_name = f"rag_session_turns_b_{uuid4().hex[:12]}"
    database_url = source.set(database=database_name)
    admin_engine = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        try:
            yield database_url
        finally:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (database_name,),
                )
                connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="module")
def session_database_url() -> Iterator[URL]:
    with _temporary_database() as database_url:
        _run_alembic(database_url, "upgrade", "head")
        try:
            yield database_url
        finally:
            _run_alembic(database_url, "downgrade", "base")


@pytest.fixture
def session_factory(
    session_database_url: URL,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(session_database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


@pytest.fixture
def session_runtime_role(session_database_url: URL) -> Iterator[str]:
    role_name = f"rag_session_runtime_{uuid4().hex[:12]}"
    assert _RUNTIME_ROLE_PATTERN.fullmatch(role_name) is not None
    quoted_role = f'"{role_name}"'
    engine = create_engine(session_database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            owner_name = str(connection.exec_driver_sql("SELECT current_user").scalar_one())
            quoted_owner = f'"{owner_name.replace(chr(34), chr(34) * 2)}"'
            connection.exec_driver_sql(
                f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
            connection.exec_driver_sql(f"GRANT {quoted_role} TO {quoted_owner}")
            connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON sessions, session_turns TO {quoted_role}"
            )
        try:
            yield role_name
        finally:
            with engine.connect() as connection:
                connection.exec_driver_sql(
                    f"REVOKE ALL PRIVILEGES ON sessions, session_turns FROM {quoted_role}"
                )
                connection.exec_driver_sql(f"REVOKE USAGE ON SCHEMA public FROM {quoted_role}")
                connection.exec_driver_sql(f"REVOKE {quoted_role} FROM {quoted_owner}")
                connection.exec_driver_sql(f"DROP ROLE {quoted_role}")
    finally:
        engine.dispose()


@pytest.fixture
def runtime_session_factory(
    session_database_url: URL,
    session_runtime_role: str,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(session_database_url), poolclass=NullPool)
    quoted_role = f'"{session_runtime_role}"'

    @event.listens_for(engine.sync_engine, "connect")
    def _set_runtime_role(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"SET ROLE {quoted_role}")
        finally:
            cursor.close()

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


async def _seed_session(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    session_id: UUID | None = None,
) -> UUID:
    actual_id = session_id or uuid4()
    async with session_factory() as session, session.begin():
        session.add(Session(id=actual_id, tenant_id=tenant_id))
    return actual_id


async def _session_state(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    session_id: UUID,
) -> tuple[int, int, int]:
    async with session_factory() as session:
        record = await session.scalar(
            select(Session).where(
                Session.id == session_id,
                Session.tenant_id == tenant_id,
            )
        )
        assert record is not None
        message_count = await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.session_id == session_id,
                Message.tenant_id == tenant_id,
            )
        )
        return record.version, record.turn_epoch, int(message_count or 0)


async def _turn(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    turn_id: str,
) -> SessionTurn:
    async with session_factory() as session:
        await set_session_tenant_context(session, tenant_id)
        record = await session.scalar(
            select(SessionTurn).where(
                SessionTurn.tenant_id == tenant_id,
                SessionTurn.turn_id == turn_id,
            )
        )
        assert record is not None
        return record


def _deadline(minutes: int = 5) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


async def _wait_for_database_blocker(
    session_factory: async_sessionmaker[AsyncSession],
    process_id: int,
) -> None:
    deadline = asyncio.get_running_loop().time() + 2.0
    while True:
        async with session_factory() as session:
            blockers = await session.scalar(
                text("SELECT pg_blocking_pids(:process_id)"),
                {"process_id": process_id},
            )
        if blockers:
            return
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail("terminal commit did not block behind the history snapshot lock")
        await asyncio.sleep(0.02)


def test_revision_031_round_trips_session_turn_schema_on_real_postgresql(
    session_database_url: URL,
) -> None:
    _run_alembic(session_database_url, "downgrade", "030")
    engine = create_engine(session_database_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "session_turns" not in inspector.get_table_names(schema="public")
            session_columns = {column["name"] for column in inspector.get_columns("sessions")}
            assert "version" not in session_columns
            assert "turn_epoch" not in session_columns

        _run_alembic(session_database_url, "upgrade", "031")
        with engine.connect() as connection:
            inspector = inspect(connection)
            table_names = set(inspector.get_table_names(schema="public"))
            assert "session_turns" in table_names
            assert len(table_names) == 38
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "031"
            )
            session_columns = {column["name"] for column in inspector.get_columns("sessions")}
            assert {"version", "turn_epoch"} <= session_columns
            turn_columns = {column["name"] for column in inspector.get_columns("session_turns")}
            assert turn_columns == {
                "tenant_id",
                "turn_id",
                "session_id",
                "request_digest",
                "expected_version",
                "turn_epoch",
                "status",
                "admitted_at",
                "deadline_at",
                "terminal_at",
                "result_digest",
                "committed_version",
            }
            indexes = {index["name"]: index for index in inspector.get_indexes("session_turns")}
            assert indexes["uq_session_turns_one_running"]["unique"] is True
            foreign_keys = inspector.get_foreign_keys("session_turns")
            assert len(foreign_keys) == 1
            assert foreign_keys[0]["constrained_columns"] == ["session_id", "tenant_id"]
            assert foreign_keys[0]["referred_columns"] == ["id", "tenant_id"]
            rls = connection.execute(
                text(
                    "SELECT c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = 'session_turns'"
                )
            ).one()
            assert rls.relrowsecurity is True
            assert rls.relforcerowsecurity is True

        _run_alembic(session_database_url, "downgrade", "030")
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "session_turns" not in inspector.get_table_names(schema="public")
            session_columns = {column["name"] for column in inspector.get_columns("sessions")}
            assert "version" not in session_columns
            assert "turn_epoch" not in session_columns
        _run_alembic(session_database_url, "upgrade", "head")
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_admission_creates_first_session_and_replays_before_version_check(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SessionService(session_factory)
    concurrent = await asyncio.gather(
        *(
            service.admit_turn(
                tenant_id=_TENANT_A,
                session_id=None,
                turn_id="first-turn-idempotency-key",
                request_digest="a" * 64,
                expected_version=0,
                deadline_at=_deadline(),
            )
            for _ in range(2)
        )
    )
    admitted_outcomes = [outcome for outcome in concurrent if outcome.admitted]
    replayed_outcomes = [outcome for outcome in concurrent if not outcome.admitted]
    assert len(admitted_outcomes) == 1
    assert len(replayed_outcomes) == 1
    admitted = admitted_outcomes[0]
    assert admitted.turn.status is TurnStatus.RUNNING
    assert admitted.turn.expected_version == 0
    assert admitted.turn.turn_epoch == 1
    assert replayed_outcomes[0].turn == admitted.turn
    replayed = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=None,
        turn_id="first-turn-idempotency-key",
        request_digest="a" * 64,
        expected_version=99,
        deadline_at=_deadline(),
    )
    assert replayed.admitted is False
    assert replayed.turn == admitted.turn
    assert await _session_state(session_factory, _TENANT_A, admitted.turn.session_id) == (0, 1, 0)

    with pytest.raises(SessionTurnIdempotencyConflict):
        await service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=uuid4(),
            turn_id="first-turn-idempotency-key",
            request_digest="a" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        )

    with pytest.raises(SessionTurnIdempotencyConflict):
        await service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=None,
            turn_id="first-turn-idempotency-key",
            request_digest="b" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        )


@pytest.mark.asyncio
async def test_admission_rejects_stale_active_and_elapsed_deadline_then_expires_overdue(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session_id = await _seed_session(session_factory, _TENANT_A)
    service = SessionService(session_factory)

    with pytest.raises(SessionVersionConflict) as stale:
        await service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id="stale-version",
            request_digest="c" * 64,
            expected_version=1,
            deadline_at=_deadline(),
        )
    assert stale.value.actual_version == 0

    with pytest.raises(SessionTurnDeadlineElapsed):
        await service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id="elapsed-deadline",
            request_digest="d" * 64,
            expected_version=0,
            deadline_at=datetime.now(UTC) - timedelta(seconds=1),
        )

    active = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id="active-turn",
        request_digest="e" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    with pytest.raises(SessionTurnActive) as collision:
        await service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id="competing-turn",
            request_digest="f" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        )
    assert collision.value.active_turn_id == active.turn.turn_id

    async with session_factory() as session, session.begin():
        await set_session_tenant_context(session, _TENANT_A)
        await session.execute(
            text(
                "UPDATE session_turns "
                "SET admitted_at = clock_timestamp() - interval '10 seconds', "
                "deadline_at = clock_timestamp() - interval '1 second' "
                "WHERE tenant_id = :tenant_id AND turn_id = :turn_id"
            ),
            {"tenant_id": _TENANT_A, "turn_id": active.turn.turn_id},
        )

    successor = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id="successor-turn",
        request_digest="1" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    expired = await _turn(session_factory, _TENANT_A, active.turn.turn_id)
    assert expired.status == TurnStatus.EXPIRED.value
    assert expired.terminal_at is not None
    assert successor.turn.turn_epoch == 2
    assert await _session_state(session_factory, _TENANT_A, session_id) == (0, 2, 0)


@pytest.mark.asyncio
async def test_abort_requires_exact_fence_and_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session_id = await _seed_session(session_factory, _TENANT_A)
    service = SessionService(session_factory)
    admitted = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id="abort-turn",
        request_digest="2" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    other_session_id = await _seed_session(session_factory, _TENANT_A)
    other_turn = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=other_session_id,
        turn_id="other-abort-turn",
        request_digest="0" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )

    with pytest.raises(SessionTurnFenceConflict):
        await service.abort_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id=admitted.turn.turn_id,
            turn_epoch=admitted.turn.turn_epoch + 1,
        )
    with pytest.raises(SessionTurnFenceConflict):
        await service.abort_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id=other_turn.turn.turn_id,
            turn_epoch=admitted.turn.turn_epoch,
        )

    aborted = await service.abort_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id=admitted.turn.turn_id,
        turn_epoch=admitted.turn.turn_epoch,
    )
    assert aborted.changed is True
    assert aborted.turn.status is TurnStatus.ABORTED
    replayed = await service.abort_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id=admitted.turn.turn_id,
        turn_epoch=admitted.turn.turn_epoch,
    )
    assert replayed.changed is False
    assert replayed.turn == aborted.turn
    assert await _session_state(session_factory, _TENANT_A, session_id) == (0, 1, 0)


@pytest.mark.asyncio
async def test_two_connections_serialize_one_session_but_not_distinct_sessions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_session = await _seed_session(session_factory, _TENANT_A)
    second_session = await _seed_session(session_factory, _TENANT_A)
    service = SessionService(session_factory)

    same_session_results = await asyncio.gather(
        service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=first_session,
            turn_id="concurrent-a",
            request_digest="3" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        ),
        service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=first_session,
            turn_id="concurrent-b",
            request_digest="4" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        ),
        return_exceptions=True,
    )
    admitted = [result for result in same_session_results if not isinstance(result, BaseException)]
    rejected = [result for result in same_session_results if isinstance(result, SessionTurnActive)]
    assert len(admitted) == 1
    assert len(rejected) == 1
    assert await _session_state(session_factory, _TENANT_A, first_session) == (0, 1, 0)

    distinct_results = await asyncio.gather(
        service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=second_session,
            turn_id="distinct-a",
            request_digest="5" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        ),
        service.admit_turn(
            tenant_id=_TENANT_B,
            session_id=None,
            turn_id="distinct-b",
            request_digest="6" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        ),
    )
    assert all(outcome.admitted for outcome in distinct_results)
    assert distinct_results[0].turn.session_id != distinct_results[1].turn.session_id


@pytest.mark.asyncio
async def test_forced_rls_and_service_tenant_predicates_fail_closed(
    session_factory: async_sessionmaker[AsyncSession],
    runtime_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a = "tenant-session-rls-a"
    tenant_b = "tenant-session-rls-b"
    session_id = await _seed_session(session_factory, tenant_a)
    tenant_b_session_id = await _seed_session(session_factory, tenant_b)
    service = SessionService(runtime_session_factory)
    admitted = await service.admit_turn(
        tenant_id=tenant_a,
        session_id=session_id,
        turn_id="rls-owned-turn",
        request_digest="7" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    assert admitted.admitted is True

    async with runtime_session_factory() as session:
        target_count = (
            select(func.count())
            .select_from(SessionTurn)
            .where(SessionTurn.turn_id == admitted.turn.turn_id)
        )
        assert await session.scalar(target_count) == 0
        await set_session_tenant_context(session, tenant_b)
        assert await session.scalar(target_count) == 0
        await session.commit()
        assert await session.scalar(target_count) == 0

    async with runtime_session_factory() as session:
        await set_session_tenant_context(session, tenant_a)
        assert await session.scalar(target_count) == 1
        with pytest.raises(DBAPIError) as blocked_insert:
            await session.execute(
                text(
                    "INSERT INTO session_turns "
                    "(tenant_id, turn_id, session_id, request_digest, expected_version, "
                    "turn_epoch, status, admitted_at, deadline_at) "
                    "VALUES (:tenant_id, 'foreign-insert', :session_id, :digest, 0, 2, "
                    "'RUNNING', clock_timestamp(), clock_timestamp() + interval '1 minute')"
                ),
                {
                    "tenant_id": tenant_b,
                    "session_id": tenant_b_session_id,
                    "digest": "8" * 64,
                },
            )
        assert getattr(blocked_insert.value.orig, "sqlstate", None) == "42501"
        await session.rollback()

    with pytest.raises(SessionNotFound):
        await service.admit_turn(
            tenant_id=tenant_b,
            session_id=session_id,
            turn_id="foreign-session",
            request_digest="9" * 64,
            expected_version=0,
            deadline_at=_deadline(),
        )


@pytest.mark.asyncio
async def test_terminal_commit_persists_one_ordered_pair_and_replays_idempotently(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session_id = await _seed_session(session_factory, _TENANT_A)
    service = SessionService(session_factory)
    empty = await service.load_history(tenant_id=_TENANT_A, session_id=session_id)
    assert isinstance(empty, SessionHistorySnapshot)
    assert empty.version == 0
    assert empty.messages == ()

    admitted = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id="terminal-success",
        request_digest="a" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    committed = await service.commit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id=admitted.turn.turn_id,
        turn_epoch=admitted.turn.turn_epoch,
        request_digest=admitted.turn.request_digest,
        user_content="first question",
        assistant_content="first answer",
    )
    assert isinstance(committed, TurnCommitOutcome)
    assert committed.changed is True
    assert committed.turn.status is TurnStatus.COMMITTED
    assert committed.turn.committed_version == 1
    assert committed.turn.result_digest is not None

    history = await service.load_history(tenant_id=_TENANT_A, session_id=session_id)
    assert history.tenant_id == _TENANT_A
    assert history.session_id == session_id
    assert history.version == 1
    assert all(isinstance(message, SessionMessageSnapshot) for message in history.messages)
    assert [(message.role, message.content) for message in history.messages] == [
        ("user", "first question"),
        ("assistant", "first answer"),
    ]

    replayed = await service.commit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id=admitted.turn.turn_id,
        turn_epoch=admitted.turn.turn_epoch,
        request_digest=admitted.turn.request_digest,
        user_content="first question",
        assistant_content="first answer",
    )
    assert replayed.changed is False
    assert replayed.turn == committed.turn
    assert await _session_state(session_factory, _TENANT_A, session_id) == (1, 1, 2)

    with pytest.raises(SessionTurnTerminalConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id=admitted.turn.turn_id,
            turn_epoch=admitted.turn.turn_epoch,
            request_digest=admitted.turn.request_digest,
            user_content="first question",
            assistant_content="changed answer",
        )
    assert await _session_state(session_factory, _TENANT_A, session_id) == (1, 1, 2)


@pytest.mark.asyncio
async def test_concurrent_duplicate_terminal_commit_advances_once(
    session_factory: async_sessionmaker[AsyncSession],
    session_database_url: URL,
) -> None:
    session_id = await _seed_session(session_factory, _TENANT_A)
    service = SessionService(session_factory)
    admitted = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id="terminal-concurrent",
        request_digest="b" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    barrier = asyncio.Barrier(2)
    engine = create_async_engine(_async_url(session_database_url), poolclass=NullPool)
    commit_factory = async_sessionmaker(
        engine,
        class_=_SessionSelectBarrier,
        expire_on_commit=False,
        session_select_barrier=barrier,
    )
    commit_service = SessionService(commit_factory)
    try:
        outcomes = await asyncio.gather(
            *(
                commit_service.commit_turn(
                    tenant_id=_TENANT_A,
                    session_id=session_id,
                    turn_id=admitted.turn.turn_id,
                    turn_epoch=admitted.turn.turn_epoch,
                    request_digest=admitted.turn.request_digest,
                    user_content="concurrent question",
                    assistant_content="concurrent answer",
                )
                for _ in range(2)
            )
        )
    finally:
        await engine.dispose()
    assert sorted(outcome.changed for outcome in outcomes) == [False, True]
    assert outcomes[0].turn == outcomes[1].turn
    assert await _session_state(session_factory, _TENANT_A, session_id) == (1, 1, 2)


@pytest.mark.asyncio
async def test_terminal_commit_rejects_wrong_fence_abort_and_elapsed_deadline(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SessionService(session_factory)

    fenced_session_id = await _seed_session(session_factory, _TENANT_A)
    fenced = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=fenced_session_id,
        turn_id="terminal-wrong-fence",
        request_digest="c" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    with pytest.raises(SessionTurnFenceConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=fenced_session_id,
            turn_id=fenced.turn.turn_id,
            turn_epoch=fenced.turn.turn_epoch + 1,
            request_digest=fenced.turn.request_digest,
            user_content="must not persist",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, fenced_session_id) == (0, 1, 0)

    aborted_session_id = await _seed_session(session_factory, _TENANT_A)
    aborted = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=aborted_session_id,
        turn_id="terminal-aborted",
        request_digest="d" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    await service.abort_turn(
        tenant_id=_TENANT_A,
        session_id=aborted_session_id,
        turn_id=aborted.turn.turn_id,
        turn_epoch=aborted.turn.turn_epoch,
    )
    with pytest.raises(SessionTurnTerminalConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=aborted_session_id,
            turn_id=aborted.turn.turn_id,
            turn_epoch=aborted.turn.turn_epoch,
            request_digest=aborted.turn.request_digest,
            user_content="must not persist",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, aborted_session_id) == (0, 1, 0)

    expired_session_id = await _seed_session(session_factory, _TENANT_A)
    expired = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=expired_session_id,
        turn_id="terminal-expired",
        request_digest="e" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    async with session_factory() as session, session.begin():
        await set_session_tenant_context(session, _TENANT_A)
        await session.execute(
            text(
                "UPDATE session_turns "
                "SET admitted_at = clock_timestamp() - interval '10 seconds', "
                "deadline_at = clock_timestamp() - interval '1 second' "
                "WHERE tenant_id = :tenant_id AND turn_id = :turn_id"
            ),
            {"tenant_id": _TENANT_A, "turn_id": expired.turn.turn_id},
        )
    with pytest.raises(SessionTurnDeadlineElapsed):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=expired_session_id,
            turn_id=expired.turn.turn_id,
            turn_epoch=expired.turn.turn_epoch,
            request_digest=expired.turn.request_digest,
            user_content="must not persist",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, expired_session_id) == (0, 1, 0)


@pytest.mark.asyncio
async def test_history_snapshot_is_tenant_scoped_versioned_and_ordered(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session_id = await _seed_session(session_factory, _TENANT_A)
    service = SessionService(session_factory)
    for version in range(2):
        admitted = await service.admit_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id=f"history-turn-{version}",
            request_digest=str(version + 1) * 64,
            expected_version=version,
            deadline_at=_deadline(),
        )
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=session_id,
            turn_id=admitted.turn.turn_id,
            turn_epoch=admitted.turn.turn_epoch,
            request_digest=admitted.turn.request_digest,
            user_content=f"question-{version}",
            assistant_content=f"answer-{version}",
        )

    history = await service.load_history(tenant_id=_TENANT_A, session_id=session_id)
    assert history.version == 2
    assert [(message.role, message.content) for message in history.messages] == [
        ("user", "question-0"),
        ("assistant", "answer-0"),
        ("user", "question-1"),
        ("assistant", "answer-1"),
    ]
    with pytest.raises(SessionNotFound):
        await service.load_history(tenant_id=_TENANT_B, session_id=session_id)


@pytest.mark.asyncio
async def test_terminal_commit_binds_request_and_rejects_foreign_stale_or_expired_tokens(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SessionService(session_factory)

    request_session_id = await _seed_session(session_factory, _TENANT_A)
    request_turn = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=request_session_id,
        turn_id="terminal-request-binding",
        request_digest="6" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    with pytest.raises(SessionTurnIdempotencyConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=request_session_id,
            turn_id=request_turn.turn.turn_id,
            turn_epoch=request_turn.turn.turn_epoch,
            request_digest="7" * 64,
            user_content="wrong request",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, request_session_id) == (0, 1, 0)

    foreign_session_id = await _seed_session(session_factory, _TENANT_A)
    foreign_turn = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=foreign_session_id,
        turn_id="terminal-foreign-turn",
        request_digest="8" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    with pytest.raises(SessionTurnFenceConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=request_session_id,
            turn_id=foreign_turn.turn.turn_id,
            turn_epoch=request_turn.turn.turn_epoch,
            request_digest=foreign_turn.turn.request_digest,
            user_content="foreign request",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, request_session_id) == (0, 1, 0)

    stale_session_id = await _seed_session(session_factory, _TENANT_A)
    stale_turn = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=stale_session_id,
        turn_id="terminal-stale-version",
        request_digest="9" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE sessions SET version = 1 WHERE id = :session_id AND tenant_id = :tenant_id"
            ),
            {"session_id": stale_session_id, "tenant_id": _TENANT_A},
        )
    with pytest.raises(SessionVersionConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=stale_session_id,
            turn_id=stale_turn.turn.turn_id,
            turn_epoch=stale_turn.turn.turn_epoch,
            request_digest=stale_turn.turn.request_digest,
            user_content="stale request",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, stale_session_id) == (1, 1, 0)

    expired_session_id = await _seed_session(session_factory, _TENANT_A)
    expired_turn = await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=expired_session_id,
        turn_id="terminal-expired-status",
        request_digest="0" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    async with session_factory() as session, session.begin():
        await set_session_tenant_context(session, _TENANT_A)
        await session.execute(
            text(
                "UPDATE session_turns "
                "SET admitted_at = clock_timestamp() - interval '10 seconds', "
                "deadline_at = clock_timestamp() - interval '1 second' "
                "WHERE tenant_id = :tenant_id AND turn_id = :turn_id"
            ),
            {"tenant_id": _TENANT_A, "turn_id": expired_turn.turn.turn_id},
        )
    await service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=expired_session_id,
        turn_id="terminal-expired-successor",
        request_digest="1" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    with pytest.raises(SessionTurnTerminalConflict):
        await service.commit_turn(
            tenant_id=_TENANT_A,
            session_id=expired_session_id,
            turn_id=expired_turn.turn.turn_id,
            turn_epoch=expired_turn.turn.turn_epoch,
            request_digest=expired_turn.turn.request_digest,
            user_content="expired request",
            assistant_content="must not persist",
        )
    assert await _session_state(session_factory, _TENANT_A, expired_session_id) == (0, 2, 0)


@pytest.mark.asyncio
async def test_terminal_commit_rolls_back_pair_version_and_status_on_insert_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = "tenant-session-terminal-rollback"
    session_id = await _seed_session(session_factory, tenant_id)
    service = SessionService(session_factory)
    admitted = await service.admit_turn(
        tenant_id=tenant_id,
        session_id=session_id,
        turn_id="terminal-insert-rollback",
        request_digest="2" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "CREATE FUNCTION test_reject_terminal_assistant() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'forced terminal assistant failure'; END $$"
            )
        )
        await session.execute(
            text(
                "CREATE TRIGGER test_reject_terminal_assistant "
                "BEFORE INSERT ON messages FOR EACH ROW "
                "WHEN (NEW.tenant_id = 'tenant-session-terminal-rollback' "
                "AND NEW.role = 'assistant') "
                "EXECUTE FUNCTION test_reject_terminal_assistant()"
            )
        )
    try:
        with pytest.raises(DBAPIError):
            await service.commit_turn(
                tenant_id=tenant_id,
                session_id=session_id,
                turn_id=admitted.turn.turn_id,
                turn_epoch=admitted.turn.turn_epoch,
                request_digest=admitted.turn.request_digest,
                user_content="rollback question",
                assistant_content="rollback answer",
            )
        assert await _session_state(session_factory, tenant_id, session_id) == (0, 1, 0)
        turn = await _turn(session_factory, tenant_id, admitted.turn.turn_id)
        assert turn.status == TurnStatus.RUNNING.value
        assert turn.result_digest is None
        assert turn.committed_version is None
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(
                text("DROP TRIGGER IF EXISTS test_reject_terminal_assistant ON messages")
            )
            await session.execute(text("DROP FUNCTION IF EXISTS test_reject_terminal_assistant"))


@pytest.mark.asyncio
async def test_history_snapshot_holds_a_consistent_version_message_boundary(
    session_factory: async_sessionmaker[AsyncSession],
    session_database_url: URL,
) -> None:
    session_id = await _seed_session(session_factory, _TENANT_A)
    admission_service = SessionService(session_factory)
    admitted = await admission_service.admit_turn(
        tenant_id=_TENANT_A,
        session_id=session_id,
        turn_id="history-lock-boundary",
        request_digest="3" * 64,
        expected_version=0,
        deadline_at=_deadline(),
    )

    snapshot_locked = asyncio.Event()
    release_snapshot = asyncio.Event()
    backend_pid: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    snapshot_engine = create_async_engine(_async_url(session_database_url), poolclass=NullPool)
    commit_engine = create_async_engine(_async_url(session_database_url), poolclass=NullPool)
    snapshot_factory = async_sessionmaker(
        snapshot_engine,
        class_=_PausedSnapshotSession,
        expire_on_commit=False,
        snapshot_locked=snapshot_locked,
        release_snapshot=release_snapshot,
    )
    commit_factory = async_sessionmaker(
        commit_engine,
        class_=_ObservedCommitSession,
        expire_on_commit=False,
        backend_pid=backend_pid,
    )
    snapshot_task = asyncio.create_task(
        SessionService(snapshot_factory).load_history(
            tenant_id=_TENANT_A,
            session_id=session_id,
        )
    )
    commit_task: asyncio.Task[TurnCommitOutcome] | None = None
    try:
        await asyncio.wait_for(snapshot_locked.wait(), timeout=2.0)
        commit_task = asyncio.create_task(
            SessionService(commit_factory).commit_turn(
                tenant_id=_TENANT_A,
                session_id=session_id,
                turn_id=admitted.turn.turn_id,
                turn_epoch=admitted.turn.turn_epoch,
                request_digest=admitted.turn.request_digest,
                user_content="snapshot question",
                assistant_content="snapshot answer",
            )
        )
        process_id = await asyncio.wait_for(asyncio.shield(backend_pid), timeout=2.0)
        await _wait_for_database_blocker(session_factory, process_id)
        release_snapshot.set()
        snapshot = await snapshot_task
        committed = await commit_task
    finally:
        release_snapshot.set()
        await asyncio.gather(
            snapshot_task,
            *(task for task in (commit_task,) if task is not None),
            return_exceptions=True,
        )
        await snapshot_engine.dispose()
        await commit_engine.dispose()

    assert snapshot.version == 0
    assert snapshot.messages == ()
    assert committed.changed is True
    final_history = await admission_service.load_history(
        tenant_id=_TENANT_A,
        session_id=session_id,
    )
    assert final_history.version == 1
    assert [(message.role, message.content) for message in final_history.messages] == [
        ("user", "snapshot question"),
        ("assistant", "snapshot answer"),
    ]
