"""Phase A.1b — the shadow's evidence, in the tables rather than only the trace.

A.5 proved the evidence bundle reaches the trace and survives the trip. That
makes it visible; it does not make it answerable. A question like "what did
the system know about SHP-100001 when it said that" is a query against
`support_cases`, `case_events`, `evidence_snapshots` and
`case_evidence_links`, and until this slice those tables had never held a row
written by anything a user touched.

What is asserted here is the round trip through real Postgres, with the
append-only triggers, the protection-profile check and the temporal exclusion
constraint all live. The decisions about *what* is written — which states the
case walks, which reason code lands where, whose clock stamps the evidence —
are asserted without a database in `tests/test_resolution_shadow_persistence.py`.

The transport management system underneath is still a fixture. These rows
prove the wiring, not anything about air cargo.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from db.models import (
    ResolutionCaseEvent,
    ResolutionEvidenceLink,
    ResolutionEvidenceSnapshot,
    ResolutionSupportCase,
)
from resolution.adapters.postgres import set_resolution_tenant_context
from resolution.application.shipment_status import (
    ContractIdentity,
    PolicyDecisionExport,
    ShipmentEvidenceExport,
    SourceObservationExport,
)
from resolution.contracts import TerminalOutcome
from resolution.domain.cases import CaseStatus
from resolution.persistence import (
    POLICY_REQUIREMENT_ID,
    SOURCE_REQUIREMENT_ID,
    persist_shipment_shadow,
    shadow_context,
)

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATABASE_PATTERN = re.compile(r"^rag_shadow_p_[0-9a-f]{12}$")
_TEST_ENCRYPTION_KEY = "shadow-persistence-key-32-characters"
_NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def shadow_encryption_environment() -> Iterator[None]:
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
        raise RuntimeError("shadow persistence integration tests require PostgreSQL")
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
    explicit_url = os.environ.get("SHADOW_P_TEST_DATABASE_URL", "").strip()
    if explicit_url:
        database_url = _sync_url(explicit_url)
        if (
            database_url.database is None
            or _DATABASE_PATTERN.fullmatch(database_url.database) is None
        ):
            raise RuntimeError(
                "SHADOW_P_TEST_DATABASE_URL must name a disposable rag_shadow_p_* database"
            )
        yield database_url
        return

    source_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise RuntimeError("DATABASE_URL or SHADOW_P_TEST_DATABASE_URL is required")
    source = _sync_url(source_url)
    database_name = f"rag_shadow_p_{uuid4().hex[:12]}"
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
def shadow_database_url() -> Iterator[URL]:
    with _temporary_database() as database_url:
        _run_alembic(database_url, "upgrade", "head")
        try:
            yield database_url
        finally:
            _run_alembic(database_url, "downgrade", "base")


@pytest.fixture
def shadow_session_factory(
    shadow_database_url: URL,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(shadow_database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


def _export(
    *,
    tenant: str,
    discriminator: str,
    terminal_state: TerminalOutcome = TerminalOutcome.VERIFIED,
    reason_codes: tuple[str, ...] = (),
    shipment_id: str = "SHP-100001",
    with_evidence: bool = True,
) -> ShipmentEvidenceExport:
    observation = (
        SourceObservationExport(
            shipment_id=shipment_id,
            status="in_transit",
            location="FRA",
            estimated_delivery="2026-08-27",
            observed_at=_NOW - timedelta(minutes=5),
            source_id="fixture-tms",
            source_version="fixture-v1",
            content_digest="b" * 64,
        )
        if with_evidence
        else None
    )
    policy = (
        PolicyDecisionExport(
            implementation_version="typed-shipment-policy/v0.1",
            data_revision="policy-rev-7",
            authority="support-policy",
            content_digest="c" * 64,
            decision="allow",
            recorded_at=_NOW - timedelta(hours=2),
            valid_from=_NOW - timedelta(days=1),
            valid_to=None,
        )
        if with_evidence
        else None
    )
    return ShipmentEvidenceExport(
        mode="shadow",
        tenant_id=tenant,
        case_id=uuid5(NAMESPACE_URL, f"rag-new:test:shadow-case:{tenant}:{discriminator}"),
        case_version=1,
        correlation_id=uuid5(NAMESPACE_URL, f"rag-new:test:correlation:{discriminator}"),
        terminal_state=terminal_state,
        reason_codes=reason_codes,
        contract=ContractIdentity(
            schema_identity="resolution-contract/v0.1",
            contract_id="aircargo.shipment-status",
            version="0.1.0",
            digest="a" * 64,
        ),
        source_observation=observation,
        policy=policy,
        claim_links=(),
        postcondition_versions=(),
        escalation_brief=None,
    )


async def _counts(
    session_factory: async_sessionmaker[AsyncSession],
    tenant: str,
) -> dict[str, int]:
    context = shadow_context(tenant)
    async with session_factory() as session:
        await set_resolution_tenant_context(session, context)
        counts = {}
        for name, model in (
            ("cases", ResolutionSupportCase),
            ("events", ResolutionCaseEvent),
            ("snapshots", ResolutionEvidenceSnapshot),
            ("links", ResolutionEvidenceLink),
        ):
            counts[name] = int(
                await session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.tenant_id == context.tenant_id)
                )
                or 0
            )
        return counts


@pytest.mark.asyncio
async def test_a_verified_shadow_run_becomes_a_case_with_its_evidence(
    shadow_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant = f"verified-{uuid4().hex[:8]}"
    export = _export(tenant=tenant, discriminator="verified")
    context = shadow_context(tenant)

    assert await persist_shipment_shadow(shadow_session_factory, export, recorded_at=_NOW) is True

    async with shadow_session_factory() as session:
        await set_resolution_tenant_context(session, context)
        case = await session.scalar(
            select(ResolutionSupportCase).where(ResolutionSupportCase.id == export.case_id)
        )
        assert case is not None
        assert case.status == CaseStatus.VERIFIED.value
        assert case.contract_id == "aircargo.shipment-status"
        assert case.correlation_id == export.correlation_id

        events = (
            await session.scalars(
                select(ResolutionCaseEvent)
                .where(ResolutionCaseEvent.case_id == export.case_id)
                .order_by(ResolutionCaseEvent.sequence)
            )
        ).all()
        # received, then the five states a verified run walks through.
        assert [event.to_status for event in events] == [
            CaseStatus.RECEIVED.value,
            CaseStatus.ROUTED.value,
            CaseStatus.EVIDENCE_GATHERING.value,
            CaseStatus.POLICY_PENDING.value,
            CaseStatus.RESPONSE_COMPILING.value,
            CaseStatus.VERIFIED.value,
        ]
        assert case.version == len(events)

        links = (
            await session.scalars(
                select(ResolutionEvidenceLink).where(
                    ResolutionEvidenceLink.case_id == export.case_id
                )
            )
        ).all()
        assert sorted(link.requirement_id for link in links) == sorted(
            (SOURCE_REQUIREMENT_ID, POLICY_REQUIREMENT_ID)
        )
        # The links point at the version the case reached, so the Evidence tab
        # can ask "what backed the answer" rather than "what was ever gathered".
        assert {link.case_version for link in links} == {case.version}

        snapshots = (
            await session.scalars(
                select(ResolutionEvidenceSnapshot).where(
                    ResolutionEvidenceSnapshot.tenant_id == context.tenant_id
                )
            )
        ).all()
        by_key = {snapshot.logical_key: snapshot for snapshot in snapshots}
        assert set(by_key) == {
            "shipment:SHP-100001:status",
            "shipment-policy:SHP-100001:disclosure",
        }
        # Each snapshot carries the evidence's own clock, not the run instant.
        assert by_key["shipment:SHP-100001:status"].recorded_at.replace(
            tzinfo=UTC
        ) == _NOW - timedelta(minutes=5)
        assert by_key["shipment-policy:SHP-100001:disclosure"].recorded_at.replace(
            tzinfo=UTC
        ) == _NOW - timedelta(hours=2)


@pytest.mark.asyncio
async def test_replaying_the_same_run_writes_nothing_further(
    shadow_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A retried request must not open a second case for the same question."""
    tenant = f"replay-{uuid4().hex[:8]}"
    export = _export(tenant=tenant, discriminator="replay")

    assert await persist_shipment_shadow(shadow_session_factory, export, recorded_at=_NOW) is True
    after_first = await _counts(shadow_session_factory, tenant)

    assert await persist_shipment_shadow(shadow_session_factory, export, recorded_at=_NOW) is False
    assert await _counts(shadow_session_factory, tenant) == after_first


@pytest.mark.asyncio
async def test_a_run_that_never_reached_the_source_records_the_case_alone(
    shadow_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """No evidence gathered, no evidence rows — and still a case that says so."""
    tenant = f"escalated-{uuid4().hex[:8]}"
    export = _export(
        tenant=tenant,
        discriminator="escalated",
        terminal_state=TerminalOutcome.ESCALATED,
        reason_codes=("SOURCE_UNAVAILABLE",),
        with_evidence=False,
    )
    context = shadow_context(tenant)

    assert await persist_shipment_shadow(shadow_session_factory, export, recorded_at=_NOW) is True

    counts = await _counts(shadow_session_factory, tenant)
    assert counts == {"cases": 1, "events": 3, "snapshots": 0, "links": 0}

    async with shadow_session_factory() as session:
        await set_resolution_tenant_context(session, context)
        events = (
            await session.scalars(
                select(ResolutionCaseEvent)
                .where(ResolutionCaseEvent.case_id == export.case_id)
                .order_by(ResolutionCaseEvent.sequence)
            )
        ).all()
        assert [event.to_status for event in events] == [
            CaseStatus.RECEIVED.value,
            CaseStatus.ROUTED.value,
            CaseStatus.ESCALATED.value,
        ]
        # The run's finding belongs to the step that produced it.
        assert events[-1].reason_code == "SOURCE_UNAVAILABLE"
        assert "SOURCE_UNAVAILABLE" not in [event.reason_code for event in events[:-1]]


@pytest.mark.asyncio
async def test_two_tenants_never_see_each_other(
    shadow_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The kernel's tenancy is by UUID; the runtime's is by name. The mapping holds."""
    left = f"left-{uuid4().hex[:8]}"
    right = f"right-{uuid4().hex[:8]}"
    await persist_shipment_shadow(
        shadow_session_factory, _export(tenant=left, discriminator="iso"), recorded_at=_NOW
    )
    await persist_shipment_shadow(
        shadow_session_factory, _export(tenant=right, discriminator="iso"), recorded_at=_NOW
    )

    assert await _counts(shadow_session_factory, left) == {
        "cases": 1,
        "events": 6,
        "snapshots": 2,
        "links": 2,
    }
    assert await _counts(shadow_session_factory, right) == {
        "cases": 1,
        "events": 6,
        "snapshots": 2,
        "links": 2,
    }
