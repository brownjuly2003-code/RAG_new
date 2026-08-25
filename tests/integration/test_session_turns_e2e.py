"""Phase A.2 — `/api/ask` borrows the session for a turn, over real PostgreSQL.

`services/session.py` has had a durable turn lifecycle — admission, fencing,
terminal commit — since long before this fork had a caller for it. That was
the other half of finding FIN-01: primitives proved against Postgres by their
own tests, with `/api/ask` still writing its message pair on a best-effort
path that could drop it, and two requests on one session free to interleave
their answers into a single history.

`tests/test_session_turn_wiring.py` holds the wiring decisions without a
database. These tests are the slice under rule (a): the endpoint itself, over
HTTP, against a disposable PostgreSQL, observably behaving differently.

What that difference is, concretely:

- the message pair is written by the transaction that ends the turn, and the
  session version moves with it — so a reader that never shared this process
  sees the pair through `GET /api/sessions/{id}/history`;
- a request arriving while the session already has a turn in flight is
  refused with 503 instead of racing the first one;
- with the flag off, none of this happens and the endpoint answers exactly as
  it did before phase A.2.

The pipeline underneath is the DEMO fallback — no retriever, no LLM — because
what is under test is the turn, not the answer. Every assertion here is about
which rows exist and what HTTP said, both of which are the same whatever
produced the text.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.routers import conversation
from db.models import Message, SessionTurn
from db.models import Session as DBSession
from services.session import SessionService, TurnStatus, set_session_tenant_context

pytestmark = pytest.mark.integration

# A handler that raises must answer 500 rather than blow up the test client:
# one of these tests is about what the turn does when the request does not
# survive to its answer.
CLIENT_WITH_KEY_RAISE_SERVER_EXCEPTIONS = False

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATABASE_PATTERN = re.compile(r"^rag_session_turns_e_[0-9a-f]{12}$")
_TEST_ENCRYPTION_KEY = "session-turn-e2e-key-32-chars!!!"
_TENANT = "acme"
_QUESTION = "What is the status of my order?"
_OTHER_QUESTION = "And what about the invoice?"


# --- the disposable database ------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def session_turn_encryption_environment() -> Iterator[None]:
    """`messages.content` is pgcrypto-encrypted; reads need the same key."""
    from db import crypto as crypto_module

    patcher = pytest.MonkeyPatch()
    patcher.setenv("DB_ENCRYPTION_KEY", _TEST_ENCRYPTION_KEY)
    patcher.setattr(
        crypto_module,
        "get_settings",
        lambda: SimpleNamespace(db_encryption_key=_TEST_ENCRYPTION_KEY),
    )
    try:
        yield
    finally:
        patcher.undo()


def _sync_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("session turn e2e tests require PostgreSQL")
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
    """Create and drop a database of our own; never touch a real one."""
    explicit_url = os.environ.get("SESSION_TURN_E2E_DATABASE_URL", "").strip()
    if explicit_url:
        database_url = _sync_url(explicit_url)
        if (
            database_url.database is None
            or _DATABASE_PATTERN.fullmatch(database_url.database) is None
        ):
            raise RuntimeError(
                "SESSION_TURN_E2E_DATABASE_URL must name a disposable "
                "rag_session_turns_e_* database"
            )
        yield database_url
        return

    source_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise RuntimeError("DATABASE_URL or SESSION_TURN_E2E_DATABASE_URL is required")
    source = _sync_url(source_url)
    database_name = f"rag_session_turns_e_{uuid4().hex[:12]}"
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
def session_turn_database_url() -> Iterator[URL]:
    with _temporary_database() as database_url:
        _run_alembic(database_url, "upgrade", "head")
        try:
            yield database_url
        finally:
            _run_alembic(database_url, "downgrade", "base")


@pytest.fixture
def durable_database(
    session_turn_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    """Point every database import the endpoint makes at the disposable one.

    `db.engine.async_session` is imported inside the functions that use it, so
    replacing the module attribute reaches `_get_or_create_session`, the
    best-effort writer and the `SessionService` the router builds — the real
    one, built by the real code path, rather than a service handed in by the
    test.
    """
    from db import engine as db_engine

    truncate_engine = create_engine(session_turn_database_url, isolation_level="AUTOCOMMIT")
    try:
        with truncate_engine.connect() as connection:
            connection.exec_driver_sql("TRUNCATE session_turns, messages, sessions CASCADE")
    finally:
        truncate_engine.dispose()

    engine = create_async_engine(_async_url(session_turn_database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db_engine, "async_session", factory)
    conversation._session_turn_service = None
    try:
        yield factory
    finally:
        conversation._session_turn_service = None
        asyncio.run(engine.dispose())


# --- the endpoint -----------------------------------------------------------


async def _fake_log_audit(**kwargs: Any) -> None:
    _ = kwargs


@pytest.fixture
def ask_client(
    monkeypatch: pytest.MonkeyPatch,
    integration_client,
    integration_api_app,
    durable_database,
):
    """`/api/ask` with a real database and no pipeline behind it.

    With no retriever and no vector store the session bootstrap falls to its
    dict branch and the endpoint answers the fixed DEMO string. That is the
    point: the answer is a constant, so every assertion below is about the
    turn rather than about what an LLM said.
    """
    monkeypatch.setattr(integration_api_app, "log_audit", _fake_log_audit)
    integration_api_app._session_llm_state.clear()
    integration_api_app._retriever = None
    integration_api_app._vector_store = None
    integration_api_app._db_retry_after = 0.0
    return integration_client


@pytest.fixture
def durable_turns_on(monkeypatch: pytest.MonkeyPatch, integration_api_app, ask_client):
    """Set the flag on the very settings object the router reads."""
    settings = integration_api_app.get_settings()
    monkeypatch.setattr(settings, "session_durable_turns", True, raising=False)
    return settings


def _ask(client, headers, session_id: str, question: str = _QUESTION):
    return client.post(
        "/api/ask",
        json={"question": question, "session_id": session_id},
        headers=headers,
    )


# --- reading the rows back --------------------------------------------------


def _turns(factory, session_id: UUID) -> list[dict[str, Any]]:
    async def _load() -> list[dict[str, Any]]:
        async with factory() as db:
            await set_session_tenant_context(db, _TENANT)
            result = await db.execute(
                select(SessionTurn)
                .where(SessionTurn.session_id == session_id)
                .order_by(SessionTurn.turn_epoch)
            )
            return [
                {
                    "turn_id": turn.turn_id,
                    "status": turn.status,
                    "turn_epoch": turn.turn_epoch,
                    "expected_version": turn.expected_version,
                    "committed_version": turn.committed_version,
                    "result_digest": turn.result_digest,
                }
                for turn in result.scalars()
            ]

    return asyncio.run(_load())


def _messages(factory, session_id: UUID) -> list[tuple[str, str]]:
    async def _load() -> list[tuple[str, str]]:
        async with factory() as db:
            await set_session_tenant_context(db, _TENANT)
            result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at, Message.id)
            )
            return [(message.role, message.content) for message in result.scalars()]

    return asyncio.run(_load())


def _version(factory, session_id: UUID) -> int:
    async def _load() -> int:
        async with factory() as db:
            await set_session_tenant_context(db, _TENANT)
            version = await db.scalar(select(DBSession.version).where(DBSession.id == session_id))
            return int(version)

    return asyncio.run(_load())


def _create_session_row(factory, session_id: UUID) -> None:
    """Insert the session the endpoint would have created on its first call."""

    async def _insert() -> None:
        async with factory() as db, db.begin():
            await set_session_tenant_context(db, _TENANT)
            db.add(DBSession(id=session_id, tenant_id=_TENANT))

    asyncio.run(_insert())


def _admit_out_of_band(
    factory,
    *,
    session_id: UUID,
    turn_id: str,
    request_digest: str,
    expected_version: int = 0,
    lifetime_seconds: float = 60.0,
) -> None:
    """Take the session's turn the way another in-flight request would."""
    service = SessionService(factory)
    asyncio.run(
        service.admit_turn(
            tenant_id=_TENANT,
            session_id=session_id,
            turn_id=turn_id,
            request_digest=request_digest,
            expected_version=expected_version,
            deadline_at=datetime.now(UTC) + timedelta(seconds=lifetime_seconds),
        )
    )


# --- the slice --------------------------------------------------------------


def test_the_question_and_its_answer_are_written_by_the_turn(
    ask_client,
    integration_headers,
    durable_turns_on,
    durable_database,
) -> None:
    """One `/api/ask`, one committed turn, one message pair, version 0 → 1."""
    session_id = uuid4()
    response = _ask(ask_client, integration_headers(_TENANT, "admin"), session_id.hex)

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert answer, "the endpoint answered nothing, so there was nothing to commit"

    turns = _turns(durable_database, session_id)
    assert len(turns) == 1, "exactly one turn should have run this request"
    assert turns[0]["status"] == TurnStatus.COMMITTED.value
    assert turns[0]["expected_version"] == 0
    assert turns[0]["committed_version"] == 1
    assert turns[0]["result_digest"], "a committed turn names the pair it wrote"
    assert turns[0]["turn_id"].startswith("ask-")

    assert _version(durable_database, session_id) == 1
    assert _messages(durable_database, session_id) == [
        ("user", _QUESTION),
        ("assistant", answer),
    ]


def test_the_pair_the_turn_wrote_is_the_history_a_fresh_reader_sees(
    ask_client,
    integration_headers,
    integration_api_app,
    durable_turns_on,
    durable_database,
) -> None:
    """Durable means: survives the process that produced it.

    The in-memory session map is cleared between the two calls, which is what
    a restart or a second replica looks like from the endpoint's side. What
    comes back is what `commit_turn` wrote, not what the handler remembered.
    """
    session_id = uuid4()
    headers = integration_headers(_TENANT, "admin")
    answer = _ask(ask_client, headers, session_id.hex).json()["answer"]

    integration_api_app._session_llm_state.clear()

    history = ask_client.get(f"/api/sessions/{session_id.hex}/history", headers=headers)

    assert history.status_code == 200
    assert [(item["role"], item["content"]) for item in history.json()["messages"]] == [
        ("user", _QUESTION),
        ("assistant", answer),
    ]


def test_a_request_arriving_while_the_session_answers_is_refused(
    ask_client,
    integration_headers,
    durable_turns_on,
    durable_database,
) -> None:
    """The behaviour change this slice exists for.

    Before A.2 the second question ran too, and both pairs landed in one
    history with nothing recording which answer belonged to which question.
    """
    session_id = uuid4()
    _create_session_row(durable_database, session_id)
    _admit_out_of_band(
        durable_database,
        session_id=session_id,
        turn_id="ask-" + "f" * 60,
        request_digest="c" * 64,
    )

    response = _ask(
        ask_client,
        integration_headers(_TENANT, "admin"),
        session_id.hex,
        question=_OTHER_QUESTION,
    )

    assert response.status_code == 503
    assert (
        _messages(durable_database, session_id) == []
    ), "the refused request still wrote to the history it was refused from"
    assert [turn["status"] for turn in _turns(durable_database, session_id)] == [
        TurnStatus.RUNNING.value
    ]


def test_a_duplicate_of_the_request_in_flight_is_refused_too(
    ask_client,
    integration_headers,
    durable_turns_on,
    durable_database,
) -> None:
    """Idempotent admission: the retry joins the running turn, and is turned away.

    `admit_turn` hands the running turn back instead of raising, because the
    id is the one it already holds. Answering it a second time is exactly what
    must not happen.
    """
    session_id = uuid4()
    _create_session_row(durable_database, session_id)
    turn_id, request_digest = conversation._durable_turn_identity(
        tenant_id=_TENANT,
        session_id=session_id.hex,
        expected_version=0,
        question=_QUESTION,
        confirm=False,
    )
    _admit_out_of_band(
        durable_database,
        session_id=session_id,
        turn_id=turn_id,
        request_digest=request_digest,
    )

    response = _ask(ask_client, integration_headers(_TENANT, "admin"), session_id.hex)

    assert response.status_code == 503
    assert len(_turns(durable_database, session_id)) == 1
    assert _messages(durable_database, session_id) == []


def test_a_turn_past_its_deadline_does_not_hold_the_session(
    ask_client,
    integration_headers,
    durable_turns_on,
    durable_database,
) -> None:
    """A request that died mid-turn may cost one deadline, not the session.

    The abort on the way out of the handler is the fast path; this is the
    backstop under it, and the backstop is the one that has to work when the
    process that held the turn is gone.
    """
    session_id = uuid4()
    stale_turn_id = "ask-" + "e" * 60
    _create_session_row(durable_database, session_id)
    _admit_out_of_band(
        durable_database,
        session_id=session_id,
        turn_id=stale_turn_id,
        request_digest="d" * 64,
        lifetime_seconds=1.0,
    )
    time.sleep(1.5)

    response = _ask(ask_client, integration_headers(_TENANT, "admin"), session_id.hex)

    assert response.status_code == 200
    statuses = {turn["turn_id"]: turn["status"] for turn in _turns(durable_database, session_id)}
    assert statuses[stale_turn_id] == TurnStatus.EXPIRED.value
    assert TurnStatus.COMMITTED.value in statuses.values()
    assert _version(durable_database, session_id) == 1


def test_the_same_question_asked_again_gets_a_turn_of_its_own(
    ask_client,
    integration_headers,
    durable_turns_on,
    durable_database,
) -> None:
    """Committing moves the version, so the repeat is a new turn, not a collision.

    This is what stops the id derivation from turning one committed turn into
    a permanent refusal of every repeat of the same question.
    """
    session_id = uuid4()
    headers = integration_headers(_TENANT, "admin")

    first = _ask(ask_client, headers, session_id.hex)
    second = _ask(ask_client, headers, session_id.hex)

    assert first.status_code == second.status_code == 200
    turns = _turns(durable_database, session_id)
    assert [turn["status"] for turn in turns] == [
        TurnStatus.COMMITTED.value,
        TurnStatus.COMMITTED.value,
    ]
    assert [turn["expected_version"] for turn in turns] == [0, 1]
    assert turns[0]["turn_id"] != turns[1]["turn_id"]
    assert _version(durable_database, session_id) == 2
    assert len(_messages(durable_database, session_id)) == 4


def test_a_request_that_never_reaches_its_answer_gives_the_session_back(
    ask_client,
    integration_headers,
    integration_api_app,
    monkeypatch: pytest.MonkeyPatch,
    durable_turns_on,
    durable_database,
) -> None:
    """The handler can leave through a raise; the session may not stay held.

    The turn ends ABORTED on the way out, and the session is answering again
    on the next request — without waiting out a deadline.
    """
    explode = {"now": True}

    def _cache_key(*args: Any, **kwargs: Any) -> str:
        if explode["now"]:
            raise RuntimeError("the request died before it had an answer")
        return ""

    monkeypatch.setattr(durable_turns_on, "llm_cache_enabled", True, raising=False)
    monkeypatch.setattr(integration_api_app, "_cache_key", _cache_key)

    session_id = uuid4()
    headers = integration_headers(_TENANT, "admin")

    failed = _ask(ask_client, headers, session_id.hex)
    assert failed.status_code == 500

    turns = _turns(durable_database, session_id)
    assert [turn["status"] for turn in turns] == [TurnStatus.ABORTED.value]
    assert _messages(durable_database, session_id) == []
    assert _version(durable_database, session_id) == 0

    # A different question is a different turn id, so the session answers
    # immediately rather than colliding with the turn that died.
    explode["now"] = False
    recovered = _ask(ask_client, headers, session_id.hex, question=_OTHER_QUESTION)

    assert recovered.status_code == 200
    assert _version(durable_database, session_id) == 1


def test_with_the_flag_off_the_endpoint_is_the_one_that_predates_a2(
    ask_client,
    integration_headers,
    durable_database,
) -> None:
    """Off by default, end to end: no turn, and the best-effort writer still writes."""
    session_id = uuid4()
    response = _ask(ask_client, integration_headers(_TENANT, "admin"), session_id.hex)

    assert response.status_code == 200
    assert _turns(durable_database, session_id) == []
    assert _version(durable_database, session_id) == 0
    assert _messages(durable_database, session_id) == [
        ("user", _QUESTION),
        ("assistant", response.json()["answer"]),
    ]
