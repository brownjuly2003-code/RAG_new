from __future__ import annotations

import asyncio
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from actions.application import ActionGateway, ActionRegistry
from actions.domain import (
    ActionCommand,
    ActionIdempotencyConflict,
    ActionManifest,
    ActionPolicyDecision,
    ActionPolicyRequest,
    ActionPolicyResult,
    ActionPostconditionResult,
    ActionReceiptState,
    ActionRisk,
    ActionRun,
    ConfirmationDecision,
    ConnectorResult,
    PostconditionStatus,
)
from actions.postgres import PostgresActionStore, set_action_tenant_context
from db.models import (
    GovernedActionAttempt,
    GovernedActionConfirmation,
    GovernedActionKillSwitch,
    GovernedActionManifest,
    GovernedActionOutboxEvent,
    GovernedActionPostconditionResult,
    GovernedActionRun,
    GovernedPolicyDecision,
    ResolutionSupportCase,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = "public"
_TABLES = (
    "action_manifests",
    "policy_decisions",
    "action_runs",
    "action_confirmations",
    "action_attempts",
    "action_outbox_events",
    "action_postcondition_results",
    "action_kill_switches",
)
_DATABASE_PATTERN = re.compile(r"^rag_actions_f_[0-9a-f]{12}$")
_RUNTIME_ROLE_PATTERN = re.compile(r"^rag_actions_runtime_[0-9a-f]{12}$")
_TEST_ENCRYPTION_KEY = "actions-test-key-32-characters!!"
_TENANT_A = UUID("83000000-0000-0000-0000-000000000001")
_TENANT_B = UUID("83000000-0000-0000-0000-000000000002")
_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def action_encryption_environment() -> Iterator[None]:
    patcher = pytest.MonkeyPatch()
    patcher.setenv("DB_ENCRYPTION_KEY", _TEST_ENCRYPTION_KEY)
    try:
        yield
    finally:
        patcher.undo()


def _sync_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("governed action integration tests require PostgreSQL")
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
    explicit_url = os.environ.get("ACTION_F_TEST_DATABASE_URL", "").strip()
    if explicit_url:
        database_url = _sync_url(explicit_url)
        if (
            database_url.database is None
            or _DATABASE_PATTERN.fullmatch(database_url.database) is None
        ):
            raise RuntimeError(
                "ACTION_F_TEST_DATABASE_URL must name a disposable rag_actions_f_* database"
            )
        yield database_url
        return

    source_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise RuntimeError("DATABASE_URL or ACTION_F_TEST_DATABASE_URL is required")
    source = _sync_url(source_url)
    database_name = f"rag_actions_f_{uuid4().hex[:12]}"
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
def action_database_url() -> Iterator[URL]:
    with _temporary_database() as database_url:
        _run_alembic(database_url, "upgrade", "head")
        try:
            yield database_url
        finally:
            _run_alembic(database_url, "downgrade", "base")


@pytest.fixture
def action_session_factory(
    action_database_url: URL,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(action_database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


@pytest.fixture
def action_runtime_role(action_database_url: URL) -> Iterator[str]:
    role_name = f"rag_actions_runtime_{uuid4().hex[:12]}"
    assert _RUNTIME_ROLE_PATTERN.fullmatch(role_name) is not None
    quoted_role = f'"{role_name}"'
    engine = create_engine(action_database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            owner_name = str(connection.exec_driver_sql("SELECT current_user").scalar_one())
            quoted_owner = f'"{owner_name.replace(chr(34), chr(34) * 2)}"'
            connection.exec_driver_sql(
                f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
            connection.exec_driver_sql(f"GRANT {quoted_role} TO {quoted_owner}")
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(_TABLES)} TO {quoted_role}"
            )
        try:
            yield role_name
        finally:
            with engine.connect() as connection:
                connection.exec_driver_sql(
                    f"REVOKE ALL PRIVILEGES ON {', '.join(_TABLES)} FROM {quoted_role}"
                )
                connection.exec_driver_sql(f"REVOKE {quoted_role} FROM {quoted_owner}")
                connection.exec_driver_sql(f"DROP ROLE {quoted_role}")
    finally:
        engine.dispose()


@pytest.fixture
def runtime_session_factory(
    action_database_url: URL,
    action_runtime_role: str,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(action_database_url), poolclass=NullPool)
    quoted_role = f'"{action_runtime_role}"'

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


class _Policy:
    async def decide(self, request: ActionPolicyRequest) -> ActionPolicyDecision:
        return ActionPolicyDecision(
            id=uuid4(),
            tenant_id=request.tenant_id,
            case_id=request.case_id,
            action_digest=request.action_digest,
            input_digest=request.input_digest,
            evidence_digest=request.evidence_digest,
            result=ActionPolicyResult.ALLOW,
            reason_codes=("POLICY_ALLOW",),
            policy_adapter="typed-local",
            policy_revision="ticket-policy/1.0.0",
            decided_at=_NOW,
            expires_at=_NOW + timedelta(minutes=10),
        )


class _Connector:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.reconcile_calls = 0
        self.timeout = False
        self.reconcile_result: ConnectorResult | None = None

    async def execute(self, manifest: ActionManifest, run: ActionRun) -> ConnectorResult:
        self.execute_calls += 1
        if self.timeout:
            raise TimeoutError("ambiguous dispatch timeout")
        return ConnectorResult(
            connector_id=manifest.connector_id,
            action_id=manifest.action_id,
            downstream_idempotency_key=run.downstream_idempotency_key,
            remote_operation_id=f"operation:{run.id}",
            remote_resource_id=f"ticket:{run.id}",
            response_digest="d" * 64,
            observed_at=_NOW,
        )

    async def reconcile(
        self,
        manifest: ActionManifest,
        run: ActionRun,
    ) -> ConnectorResult | None:
        del manifest, run
        self.reconcile_calls += 1
        return self.reconcile_result


class _Checker:
    async def check(
        self,
        manifest: ActionManifest,
        run: ActionRun,
        result: ConnectorResult,
        checked_at: datetime,
    ) -> ActionPostconditionResult:
        return ActionPostconditionResult(
            id=uuid4(),
            tenant_id=run.tenant_id,
            run_id=run.id,
            checker_id=manifest.postcondition_id,
            checker_version=manifest.postcondition_version,
            observation_digest=result.response_digest,
            status=PostconditionStatus.PASS,
            reason_codes=("POSTCONDITION_PASS",),
            checked_at=checked_at,
        )


def _manifest(tenant_id: UUID) -> ActionManifest:
    return ActionManifest(
        tenant_id=tenant_id,
        id="support.create-ticket",
        version="1.0.0",
        connector_id="legacy-escalation",
        action_id="create_ticket",
        schema_digest="a" * 64,
        risk=ActionRisk.REVERSIBLE_WRITE,
        required_scopes=("ticket:create",),
        timeout_seconds=10,
        confirmation_ttl_seconds=300,
        postcondition_id="ticket-state",
        postcondition_version="1.0.0",
        compensation_manifest_id="support.cancel-ticket",
        max_reconciliation_attempts=2,
        recorded_at=_NOW,
    )


def _command(
    tenant_id: UUID,
    case_id: UUID,
    manifest: ActionManifest,
    *,
    summary: str = "Shipment status requires an operator",
) -> ActionCommand:
    return ActionCommand(
        tenant_id=tenant_id,
        case_id=case_id,
        contract_id="aircargo.shipment-status",
        contract_version="0.1.0",
        contract_digest="b" * 64,
        step_id="escalate-create-ticket",
        manifest_id=manifest.id,
        manifest_version=manifest.version,
        manifest_schema_digest=manifest.schema_digest,
        actor_id="agent@example.test",
        actor_scopes=manifest.required_scopes,
        logical_operation_key="shipment:SHP-100:ticket",
        input_payload={
            "session_id": "session-SHP-100",
            "summary": summary,
            "priority": "high",
        },
        evidence_digest="c" * 64,
        correlation_id=uuid4(),
        requested_at=_NOW,
    )


async def _seed_case(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    case_id: UUID,
) -> None:
    async with session_factory() as session:
        await set_action_tenant_context(session, tenant_id)
        session.add(
            ResolutionSupportCase(
                id=case_id,
                tenant_id=tenant_id,
                contract_id="aircargo.shipment-status",
                contract_version="0.1.0",
                contract_digest="b" * 64,
                correlation_id=uuid4(),
                status="policy_pending",
                version=1,
                opened_at=_NOW,
                effective_at=_NOW,
                updated_at=_NOW,
            )
        )
        await session.commit()


def test_revision_030_round_trips_exact_action_schema_on_real_postgresql(
    action_database_url: URL,
) -> None:
    _run_alembic(action_database_url, "downgrade", "029")
    engine = create_engine(action_database_url)
    try:
        with engine.connect() as connection:
            assert not (set(inspect(connection).get_table_names(schema=_SCHEMA)) & set(_TABLES))
        _run_alembic(action_database_url, "upgrade", "030")
        with engine.connect() as connection:
            inspector = inspect(connection)
            table_names = set(inspector.get_table_names(schema=_SCHEMA))
            assert set(_TABLES).issubset(table_names)
            assert len(table_names) == 37
            assert len(inspector.get_unique_constraints("action_runs")) >= 3
            rls = connection.execute(
                text(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = ANY(:tables)"
                ),
                {"tables": list(_TABLES)},
            ).all()
            assert len(rls) == len(_TABLES)
            assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls)
            trigger_names = {
                row.tgname
                for row in connection.execute(
                    text(
                        "SELECT t.tgname FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid = t.tgrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relname = ANY(:tables) "
                        "AND NOT t.tgisinternal"
                    ),
                    {"tables": list(_TABLES)},
                )
            }
            assert {
                "trg_action_manifests_append_only",
                "trg_policy_decisions_append_only",
                "trg_action_runs_transition",
                "trg_action_confirmations_transition",
                "trg_action_attempts_transition",
                "trg_action_outbox_events_transition",
                "trg_action_postcondition_results_append_only",
                "trg_action_kill_switches_append_only",
            }.issubset(trigger_names)
        _run_alembic(action_database_url, "downgrade", "029")
        with engine.connect() as connection:
            assert not (set(inspect(connection).get_table_names(schema=_SCHEMA)) & set(_TABLES))
        _run_alembic(action_database_url, "upgrade", "030")
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "030"
            )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_postgres_gateway_is_transactional_idempotent_and_postcondition_bound(
    action_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    await _seed_case(action_session_factory, tenant_id, case_id)
    manifest = _manifest(tenant_id)
    store = PostgresActionStore(action_session_factory, tenant_id)
    await store.append_manifest(manifest)
    connector = _Connector()
    registry = ActionRegistry()
    registry.register(manifest, connector=connector, checker=_Checker())
    gateway = ActionGateway(
        store=store,
        registry=registry,
        policy=_Policy(),
        environment="test",
        clock=lambda: _NOW,
    )
    command = _command(tenant_id, case_id, manifest)

    requested = await gateway.request(command)
    assert requested.confirmation_id is not None
    ready = await gateway.confirm(
        tenant_id=tenant_id,
        confirmation_id=requested.confirmation_id,
        actor_id="owner@example.test",
        action_digest=requested.action_digest,
        decision=ConfirmationDecision.APPROVED,
    )
    assert ready.outbox_event_id is not None
    completed = await gateway.dispatch(tenant_id, ready.outbox_event_id)

    assert completed.state is ActionReceiptState.POSTCONDITION_PASSED
    assert connector.execute_calls == 1
    replay = await gateway.request(command)
    assert replay.run_id == completed.run_id
    assert replay.replayed is True
    with pytest.raises(ActionIdempotencyConflict):
        await gateway.request(
            replace(command, input_payload={**command.input_payload, "summary": "changed"})
        )

    async with action_session_factory() as session:
        await set_action_tenant_context(session, tenant_id)
        assert await session.scalar(select(func.count()).select_from(GovernedPolicyDecision)) == 1
        assert await session.scalar(select(func.count()).select_from(GovernedActionRun)) == 1
        assert (
            await session.scalar(select(func.count()).select_from(GovernedActionConfirmation)) == 1
        )
        assert (
            await session.scalar(select(func.count()).select_from(GovernedActionOutboxEvent)) == 1
        )
        assert await session.scalar(select(func.count()).select_from(GovernedActionAttempt)) == 1
        assert (
            await session.scalar(
                select(func.count()).select_from(GovernedActionPostconditionResult)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_timeout_reconciliation_never_dispatches_a_second_create(
    action_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    await _seed_case(action_session_factory, tenant_id, case_id)
    manifest = _manifest(tenant_id)
    store = PostgresActionStore(action_session_factory, tenant_id)
    await store.append_manifest(manifest)
    connector = _Connector()
    connector.timeout = True
    registry = ActionRegistry()
    registry.register(manifest, connector=connector, checker=_Checker())
    gateway = ActionGateway(
        store=store,
        registry=registry,
        policy=_Policy(),
        environment="test",
        clock=lambda: _NOW,
    )
    requested = await gateway.request(_command(tenant_id, case_id, manifest))
    assert requested.confirmation_id is not None
    ready = await gateway.confirm(
        tenant_id=tenant_id,
        confirmation_id=requested.confirmation_id,
        actor_id="owner@example.test",
        action_digest=requested.action_digest,
        decision=ConfirmationDecision.APPROVED,
    )
    assert ready.outbox_event_id is not None
    unknown = await gateway.dispatch(tenant_id, ready.outbox_event_id)
    assert unknown.state is ActionReceiptState.OUTCOME_UNKNOWN
    assert unknown.outbox_event_id is not None
    run = await store.get_run(tenant_id, requested.run_id)
    assert run is not None
    connector.reconcile_result = ConnectorResult(
        connector_id=manifest.connector_id,
        action_id=manifest.action_id,
        downstream_idempotency_key=run.downstream_idempotency_key,
        remote_operation_id="operation:existing",
        remote_resource_id="ticket:existing",
        response_digest="e" * 64,
        observed_at=_NOW,
    )

    reconciled = await gateway.reconcile(tenant_id, unknown.outbox_event_id)

    assert reconciled.state is ActionReceiptState.POSTCONDITION_PASSED
    assert connector.execute_calls == 1
    assert connector.reconcile_calls == 1
    async with action_session_factory() as session:
        await set_action_tenant_context(session, tenant_id)
        assert await session.scalar(select(func.count()).select_from(GovernedActionRun)) == 1
        assert await session.scalar(select(func.count()).select_from(GovernedActionAttempt)) == 2


@pytest.mark.asyncio
async def test_forced_rls_and_transition_guards_fail_closed(
    action_session_factory: async_sessionmaker[AsyncSession],
    runtime_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    case_id = uuid4()
    await _seed_case(action_session_factory, _TENANT_A, case_id)
    manifest = _manifest(_TENANT_A)
    store = PostgresActionStore(action_session_factory, _TENANT_A)
    await store.append_manifest(manifest)
    registry = ActionRegistry()
    registry.register(manifest, connector=_Connector(), checker=_Checker())
    gateway = ActionGateway(
        store=store,
        registry=registry,
        policy=_Policy(),
        environment="test",
        clock=lambda: _NOW,
    )
    receipt = await gateway.request(_command(_TENANT_A, case_id, manifest))
    assert receipt.run_id is not None

    models = (
        GovernedActionManifest,
        GovernedPolicyDecision,
        GovernedActionRun,
        GovernedActionConfirmation,
        GovernedActionAttempt,
        GovernedActionOutboxEvent,
        GovernedActionPostconditionResult,
        GovernedActionKillSwitch,
    )
    async with runtime_session_factory() as session:
        for model in models:
            assert await session.scalar(select(func.count()).select_from(model)) == 0
        await set_action_tenant_context(session, _TENANT_A)
        assert await session.scalar(select(func.count()).select_from(GovernedActionRun)) == 1
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(GovernedActionRun)) == 0

    async with action_session_factory() as session:
        await set_action_tenant_context(session, _TENANT_A)
        with pytest.raises(DBAPIError) as manifest_mutation:
            await session.execute(
                text(
                    "UPDATE action_manifests SET schema_digest = schema_digest "
                    "WHERE tenant_id = :tenant_id"
                ),
                {"tenant_id": _TENANT_A},
            )
        assert getattr(manifest_mutation.value.orig, "sqlstate", None) == "55000"
        await session.rollback()

        await set_action_tenant_context(session, _TENANT_A)
        with pytest.raises(DBAPIError) as illegal_transition:
            await session.execute(
                text("UPDATE action_runs SET state = 'succeeded' WHERE id = :run_id"),
                {"run_id": receipt.run_id},
            )
        assert getattr(illegal_transition.value.orig, "sqlstate", None) == "55000"
        await session.rollback()

    async with action_session_factory() as session:
        await set_action_tenant_context(session, _TENANT_B)
        session.add(
            GovernedActionConfirmation(
                id=uuid4(),
                tenant_id=_TENANT_B,
                run_id=receipt.run_id,
                action_digest=receipt.action_digest,
                actor_id=None,
                decision="pending",
                expires_at=_NOW + timedelta(minutes=5),
                created_at=_NOW,
                decided_at=None,
            )
        )
        with pytest.raises(IntegrityError) as ownership:
            await session.flush()
        assert getattr(ownership.value.orig, "sqlstate", None) == "23503"
        await session.rollback()
