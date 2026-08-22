from __future__ import annotations

import asyncio
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from resolution.adapters.postgres import PostgresResolutionUnitOfWork
from resolution.domain import (
    CaseStatus,
    CaseVersionConflict,
    ContractVersionRef,
    EvidenceLink,
    EvidencePurpose,
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceStorage,
    EvidenceVisibility,
    FreshnessStatus,
    ProtectedEvidenceReference,
    SupportCase,
    TenantBoundaryViolation,
    TenantContext,
    TimeRange,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATABASE_NAME_PATTERN = re.compile(r"^rag_resolution_(?:migration|repository)_[0-9a-f]{12}$")


def _sync_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("resolution persistence integration tests require PostgreSQL")
    return url.set(drivername="postgresql+psycopg2")


def _async_url(url: URL) -> str:
    return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


def _run_alembic(database_url: URL, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    environment.setdefault("DB_ENCRYPTION_KEY", "resolution-test-key-32-characters-long")
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
def _temporary_database(kind: str) -> Iterator[URL]:
    explicit_name = f"RESOLUTION_{kind.upper()}_TEST_DATABASE_URL"
    explicit_url = os.environ.get(explicit_name, "").strip()
    if explicit_url:
        database_url = _sync_url(explicit_url)
        if (
            database_url.database is None
            or _DATABASE_NAME_PATTERN.fullmatch(database_url.database) is None
        ):
            raise RuntimeError(f"{explicit_name} must name a disposable rag_resolution_* database")
        yield database_url
        return

    source_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise RuntimeError(f"DATABASE_URL or {explicit_name} is required")

    source = _sync_url(source_url)
    database_name = f"rag_resolution_{kind}_{uuid4().hex[:12]}"
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
def migration_database_url() -> Iterator[URL]:
    with _temporary_database("migration") as database_url:
        yield database_url


@pytest.fixture(scope="module")
def repository_database_url() -> Iterator[URL]:
    with _temporary_database("repository") as database_url:
        _run_alembic(database_url, "upgrade", "head")
        try:
            yield database_url
        finally:
            _run_alembic(database_url, "downgrade", "base")


@pytest.fixture
def resolution_session_factory(
    repository_database_url: URL,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(repository_database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def _context(tenant_id: UUID, actor_id: UUID | None = None) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        actor_id=actor_id or uuid4(),
        scopes=frozenset({"case:agent"}),
    )


def _open_case(
    context: TenantContext,
    *,
    case_id: UUID | None = None,
    event_id: UUID | None = None,
    recorded_at: datetime | None = None,
):
    now = recorded_at or datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    return SupportCase.open(
        case_id=case_id or uuid4(),
        tenant_id=context.tenant_id,
        contract=ContractVersionRef(
            contract_id="aircargo.shipment-status",
            version="0.1.0",
            digest="a" * 64,
        ),
        correlation_id=uuid4(),
        event_id=event_id or uuid4(),
        command_id=uuid4(),
        actor_id=context.actor_id,
        occurred_at=now,
        recorded_at=now,
        effective_at=now - timedelta(hours=1),
    )


def _snapshot(tenant_id: UUID, *, evidence_id: UUID | None = None) -> EvidenceSnapshot:
    valid_from = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)
    return EvidenceSnapshot(
        id=evidence_id or uuid4(),
        tenant_id=tenant_id,
        logical_key="shipment:020-12345675:status",
        source_type=EvidenceSourceType.SOURCE_SYSTEM,
        source_id="tms-primary",
        source_version="event-4431",
        content_digest="b" * 64,
        valid_range=TimeRange(start=valid_from, end=valid_from + timedelta(hours=12)),
        recorded_at=valid_from + timedelta(minutes=2),
        authority="tms",
        applicability_key="shipment:020-12345675",
        visibility=EvidenceVisibility.CUSTOMER_SAFE,
        reference=ProtectedEvidenceReference(
            storage=EvidenceStorage.POSTGRES_ENCRYPTED,
            locator="evidence/020-12345675/event-4431",
            encryption_profile="tenant-envelope-v1",
            redaction_profile="shipment-status-v1",
            retention_class="support-case-90d",
        ),
    )


def test_resolution_revision_round_trips_on_real_postgresql(
    migration_database_url: URL,
) -> None:
    tables = {
        "support_cases",
        "case_events",
        "evidence_snapshots",
        "case_evidence_links",
    }

    _run_alembic(migration_database_url, "downgrade", "base")
    _run_alembic(migration_database_url, "upgrade", "023")
    engine = create_engine(migration_database_url)
    try:
        assert tables.isdisjoint(inspect(engine).get_table_names())

        _run_alembic(migration_database_url, "upgrade", "head")
        inspector = inspect(engine)
        assert tables <= set(inspector.get_table_names())
        assert {item["name"] for item in inspector.get_unique_constraints("case_events")} >= {
            "uq_case_events_tenant_case_sequence",
            "uq_case_events_tenant_case_version",
            "uq_case_events_tenant_case_command",
        }
        assert {item["name"] for item in inspector.get_foreign_keys("case_evidence_links")} == {
            "fk_case_evidence_links_case_version_owner",
            "fk_case_evidence_links_evidence_owner",
        }

        _run_alembic(migration_database_url, "downgrade", "023")
        assert tables.isdisjoint(inspect(engine).get_table_names())

        _run_alembic(migration_database_url, "upgrade", "head")
        assert tables <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_case_and_evidence_round_trip_through_tenant_scoped_repositories(
    resolution_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    context = _context(uuid4())
    opened = _open_case(context)
    snapshot = _snapshot(context.tenant_id)
    link = EvidenceLink.create(
        link_id=uuid4(),
        case=opened.case,
        evidence=snapshot,
        requirement_id="shipment_status",
        purpose=EvidencePurpose.FACT,
        gathered_at=snapshot.recorded_at,
        freshness=FreshnessStatus.CURRENT,
    )

    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        assert await work.cases.append(context, opened) == opened.case
        assert await work.evidence.append_snapshot(context, snapshot) == snapshot
        assert await work.evidence.append_link(context, link) == link
        await work.commit()

    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        assert await work.cases.get(context, opened.case.id) == opened.case
        assert await work.cases.list_events(context, opened.case.id) == (opened.event,)
        assert await work.evidence.get_snapshot(context, snapshot.id) == snapshot
        assert await work.evidence.list_for_case(context, opened.case.id) == (link,)


@pytest.mark.asyncio
async def test_case_append_compare_and_swap_rejects_stale_concurrent_transition(
    resolution_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    context = _context(uuid4())
    opened = _open_case(context)
    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        await work.cases.append(context, opened)
        await work.commit()

    first = opened.case.transition(
        to_status=CaseStatus.ROUTED,
        expected_version=1,
        event_id=uuid4(),
        command_id=uuid4(),
        actor_id=context.actor_id,
        reason_code="ROUTED_TO_SHIPMENT_STATUS",
        occurred_at=opened.case.updated_at + timedelta(seconds=1),
        recorded_at=opened.case.updated_at + timedelta(seconds=2),
    )
    stale = opened.case.transition(
        to_status=CaseStatus.ROUTED,
        expected_version=1,
        event_id=uuid4(),
        command_id=uuid4(),
        actor_id=context.actor_id,
        reason_code="STALE_CONCURRENT_ROUTE",
        occurred_at=opened.case.updated_at + timedelta(seconds=3),
        recorded_at=opened.case.updated_at + timedelta(seconds=4),
    )

    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        assert await work.cases.append(context, first) == first.case
        await work.commit()

    with pytest.raises(CaseVersionConflict) as exc_info:
        async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
            await work.cases.append(context, stale)
    assert exc_info.value.expected_version == 1
    assert exc_info.value.actual_version == 2

    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        assert await work.cases.get(context, opened.case.id) == first.case
        assert await work.cases.list_events(context, opened.case.id) == (
            opened.event,
            first.event,
        )


@pytest.mark.asyncio
async def test_failed_event_insert_rolls_back_case_version_advance(
    resolution_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    context = _context(uuid4())
    opened = _open_case(context)
    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        await work.cases.append(context, opened)
        await work.commit()

    duplicate_event = opened.case.transition(
        to_status=CaseStatus.ROUTED,
        expected_version=1,
        event_id=opened.event.id,
        command_id=uuid4(),
        actor_id=context.actor_id,
        reason_code="ROUTED_TO_SHIPMENT_STATUS",
        occurred_at=opened.case.updated_at + timedelta(seconds=1),
        recorded_at=opened.case.updated_at + timedelta(seconds=2),
    )
    with pytest.raises(IntegrityError):
        async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
            await work.cases.append(context, duplicate_event)

    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        assert await work.cases.get(context, opened.case.id) == opened.case
        assert await work.cases.list_events(context, opened.case.id) == (opened.event,)


@pytest.mark.asyncio
async def test_tenant_context_cannot_read_or_append_another_tenants_records(
    resolution_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    owner = _context(uuid4())
    intruder = _context(uuid4())
    opened = _open_case(owner)
    snapshot = _snapshot(owner.tenant_id)
    link = EvidenceLink.create(
        link_id=uuid4(),
        case=opened.case,
        evidence=snapshot,
        requirement_id="shipment_status",
        purpose=EvidencePurpose.FACT,
        gathered_at=snapshot.recorded_at,
        freshness=FreshnessStatus.CURRENT,
    )
    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        await work.cases.append(owner, opened)
        await work.evidence.append_snapshot(owner, snapshot)
        await work.evidence.append_link(owner, link)
        await work.commit()

    async with PostgresResolutionUnitOfWork(resolution_session_factory) as work:
        assert await work.cases.get(intruder, opened.case.id) is None
        assert await work.cases.list_events(intruder, opened.case.id) == ()
        assert await work.evidence.get_snapshot(intruder, snapshot.id) is None
        assert await work.evidence.list_for_case(intruder, opened.case.id) == ()
        with pytest.raises(TenantBoundaryViolation):
            await work.cases.append(intruder, opened)
        with pytest.raises(TenantBoundaryViolation):
            await work.evidence.append_snapshot(intruder, snapshot)
        with pytest.raises(TenantBoundaryViolation):
            await work.evidence.append_link(intruder, link)
