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
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from db.models import (
    TemporalKnowledgeApplicability,
    TemporalKnowledgeConflict,
    TemporalKnowledgeObject,
    TemporalKnowledgeProjectionBinding,
    TemporalKnowledgeSupersession,
    TemporalKnowledgeVersion,
)
from knowledge.application import (
    APPROVED_KNOWLEDGE_SOURCE_ID,
    APPROVED_OBSERVATION_SOURCE_ID,
    APPROVED_POSTCONDITION_ID,
    KnowledgeProjectionRecord,
    KnowledgeRetrievalRequest,
    authorize_knowledge_retrieval,
)
from knowledge.domain import (
    ApplicabilityDimension,
    ApplicabilityTerm,
    ConflictStatus,
    KnowledgeApplicability,
    KnowledgeCatalog,
    KnowledgeConflict,
    KnowledgeObject,
    KnowledgeQuery,
    KnowledgeSupersession,
    KnowledgeVersion,
    TimeRange,
)
from knowledge.ports import KnowledgeSystemCloseConflict, KnowledgeTenantBoundaryViolation
from knowledge.postgres import PostgresKnowledgeUnitOfWork, set_knowledge_tenant_context
from knowledge.projection import bind_projection_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = "public"
_TABLES = (
    "knowledge_objects",
    "knowledge_applicability",
    "knowledge_versions",
    "knowledge_supersessions",
    "knowledge_conflicts",
    "knowledge_projection_bindings",
)
_APPEND_ONLY_TABLES = (
    "knowledge_objects",
    "knowledge_applicability",
    "knowledge_supersessions",
    "knowledge_conflicts",
    "knowledge_projection_bindings",
)
_DATABASE_PATTERN = re.compile(r"^rag_knowledge_e2_[0-9a-f]{12}$")
_RUNTIME_ROLE_PATTERN = re.compile(r"^rag_knowledge_runtime_[0-9a-f]{12}$")
_TEST_ENCRYPTION_KEY = "knowledge-test-key-32-characters"
_TENANT_A = UUID("81000000-0000-0000-0000-000000000001")
_TENANT_B = UUID("81000000-0000-0000-0000-000000000002")
_BASE_TIME = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def knowledge_encryption_environment() -> Iterator[None]:
    patcher = pytest.MonkeyPatch()
    patcher.setenv("DB_ENCRYPTION_KEY", _TEST_ENCRYPTION_KEY)
    try:
        yield
    finally:
        patcher.undo()


def _sync_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("temporal knowledge integration tests require PostgreSQL")
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
    explicit_url = os.environ.get("KNOWLEDGE_E2_TEST_DATABASE_URL", "").strip()
    if explicit_url:
        database_url = _sync_url(explicit_url)
        if (
            database_url.database is None
            or _DATABASE_PATTERN.fullmatch(database_url.database) is None
        ):
            raise RuntimeError(
                "KNOWLEDGE_E2_TEST_DATABASE_URL must name a disposable rag_knowledge_e2_* database"
            )
        yield database_url
        return

    source_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise RuntimeError("DATABASE_URL or KNOWLEDGE_E2_TEST_DATABASE_URL is required")
    source = _sync_url(source_url)
    database_name = f"rag_knowledge_e2_{uuid4().hex[:12]}"
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
def knowledge_database_url() -> Iterator[URL]:
    with _temporary_database() as database_url:
        _run_alembic(database_url, "upgrade", "head")
        try:
            yield database_url
        finally:
            _run_alembic(database_url, "downgrade", "base")


@pytest.fixture
def knowledge_session_factory(
    knowledge_database_url: URL,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(knowledge_database_url), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    asyncio.run(engine.dispose())


@pytest.fixture
def knowledge_runtime_role(knowledge_database_url: URL) -> Iterator[str]:
    role_name = f"rag_knowledge_runtime_{uuid4().hex[:12]}"
    assert _RUNTIME_ROLE_PATTERN.fullmatch(role_name) is not None
    quoted_role = f'"{role_name}"'
    engine = create_engine(knowledge_database_url, isolation_level="AUTOCOMMIT")
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
    knowledge_database_url: URL,
    knowledge_runtime_role: str,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_async_url(knowledge_database_url), poolclass=NullPool)
    quoted_role = f'"{knowledge_runtime_role}"'

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


def _applicability(*, channel: str = "chat") -> KnowledgeApplicability:
    return KnowledgeApplicability(
        terms=(
            ApplicabilityTerm(ApplicabilityDimension.PRODUCT, "shipment-status"),
            ApplicabilityTerm(ApplicabilityDimension.REGION, "global"),
            ApplicabilityTerm(ApplicabilityDimension.CUSTOMER_PLAN, "standard"),
            ApplicabilityTerm(ApplicabilityDimension.CARGO_TYPE, "general"),
            ApplicabilityTerm(ApplicabilityDimension.CHANNEL, channel),
        )
    )


def _catalog(
    tenant_id: UUID,
    *,
    object_id: UUID | None = None,
    version_id: UUID | None = None,
    source_id: str = APPROVED_KNOWLEDGE_SOURCE_ID,
    authority: str = APPROVED_KNOWLEDGE_SOURCE_ID,
    digest: str = "a" * 64,
    system_from: datetime = _BASE_TIME,
    system_to: datetime | None = None,
    channel: str = "chat",
) -> KnowledgeCatalog:
    knowledge_object = KnowledgeObject(
        id=object_id or uuid4(),
        tenant_id=tenant_id,
        logical_key="shipment-status.disclosure-policy",
        source_id=source_id,
        owner="logistics-ops",
        authority=authority,
    )
    version = KnowledgeVersion(
        id=version_id or uuid4(),
        tenant_id=tenant_id,
        object_id=knowledge_object.id,
        source_revision=f"policy-{uuid4().hex}",
        content_digest=digest,
        valid_range=TimeRange(datetime(2026, 9, 1, tzinfo=UTC), None),
        system_range=TimeRange(system_from, system_to),
        applicability=_applicability(channel=channel),
        locale="en",
    )
    return KnowledgeCatalog(objects=(knowledge_object,), versions=(version,))


def _projection_record(catalog: KnowledgeCatalog) -> KnowledgeProjectionRecord:
    manifest = SimpleNamespace(active_collection="rag_docs_policy_v1", generation=1)
    binding = bind_projection_manifest(
        tenant_id=catalog.objects[0].tenant_id,
        manifest=manifest,
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )
    return KnowledgeProjectionRecord(
        id=uuid4(),
        tenant_id=catalog.objects[0].tenant_id,
        binding=binding,
        recorded_at=_BASE_TIME,
    )


def test_revision_029_round_trips_exact_schema_on_real_postgresql(
    knowledge_database_url: URL,
) -> None:
    _run_alembic(knowledge_database_url, "downgrade", "028")
    engine = create_engine(knowledge_database_url)
    try:
        assert set(_TABLES).isdisjoint(inspect(engine).get_table_names())

        _run_alembic(knowledge_database_url, "upgrade", "029")
        inspector = inspect(engine)
        assert set(_TABLES) <= set(inspector.get_table_names())
        assert {item["name"] for item in inspector.get_foreign_keys("knowledge_versions")} == {
            "fk_knowledge_versions_applicability_owner",
            "fk_knowledge_versions_object_owner",
        }
        assert {item["name"] for item in inspector.get_foreign_keys("knowledge_supersessions")} == {
            "fk_knowledge_supersessions_predecessor_owner",
            "fk_knowledge_supersessions_successor_owner",
        }
        assert {item["name"] for item in inspector.get_foreign_keys("knowledge_conflicts")} == {
            "fk_knowledge_conflicts_left_owner",
            "fk_knowledge_conflicts_right_owner",
        }

        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname IN %s ORDER BY relname",
                (tuple(_TABLES),),
            ).all() == [(table_name, True, True) for table_name in sorted(_TABLES)]
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM pg_policies WHERE tablename IN %s "
                "AND policyname = 'knowledge_tenant_isolation'",
                (tuple(_TABLES),),
            ).scalar_one() == len(_TABLES)
            trigger_rows = connection.exec_driver_sql(
                "SELECT tables.relname, triggers.tgname FROM pg_trigger AS triggers "
                "JOIN pg_class AS tables ON tables.oid = triggers.tgrelid "
                "JOIN pg_namespace AS namespaces ON namespaces.oid = tables.relnamespace "
                "WHERE NOT triggers.tgisinternal AND namespaces.nspname = %s "
                "AND tables.relname IN %s ORDER BY tables.relname, triggers.tgname",
                (_SCHEMA, tuple(_TABLES)),
            ).all()
            exclusion_definition = connection.exec_driver_sql(
                "SELECT pg_get_constraintdef(constraints.oid) FROM pg_constraint AS constraints "
                "JOIN pg_class AS tables ON tables.oid = constraints.conrelid "
                "WHERE tables.relname = 'knowledge_versions' "
                "AND constraints.conname = 'ex_knowledge_versions_bitemporal_identity'"
            ).scalar_one()
            assert (
                connection.exec_driver_sql(
                    "SELECT extname FROM pg_extension WHERE extname = 'btree_gist'"
                ).scalar_one()
                == "btree_gist"
            )
        expected_triggers = sorted(
            [(table_name, f"trg_{table_name}_append_only") for table_name in _APPEND_ONLY_TABLES]
            + [
                ("knowledge_conflicts", "trg_knowledge_conflicts_validate"),
                (
                    "knowledge_projection_bindings",
                    "trg_knowledge_projection_bindings_validate",
                ),
                ("knowledge_versions", "trg_knowledge_versions_system_close"),
            ]
        )
        assert trigger_rows == expected_triggers
        assert "tstzrange(valid_from, valid_to, '[)'::text) WITH &&" in exclusion_definition
        assert "tstzrange(system_from, system_to, '[)'::text) WITH &&" in exclusion_definition

        _run_alembic(knowledge_database_url, "downgrade", "028")
        assert set(_TABLES).isdisjoint(inspect(engine).get_table_names())
        assert {"support_cases", "evidence_snapshots"} <= set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT extname FROM pg_extension WHERE extname = 'btree_gist'"
                ).scalar_one()
                == "btree_gist"
            )

        _run_alembic(knowledge_database_url, "upgrade", "029")
        assert set(_TABLES) <= set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == "029"
            )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_repository_round_trip_and_application_allowlist_use_persisted_authority(
    knowledge_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = uuid4()
    catalog = _catalog(tenant_id)
    projection = _projection_record(catalog)
    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        await work.knowledge.append_catalog(tenant_id, catalog)
        await work.knowledge.append_projection(projection)
        await work.commit()

    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        loaded = await work.knowledge.load_catalog(
            tenant_id,
            "shipment-status.disclosure-policy",
        )
        assert loaded.objects == catalog.objects
        assert loaded.versions == catalog.versions
        assert await work.knowledge.get_projection(tenant_id, projection.id) == projection

        query = KnowledgeQuery(
            tenant_id=tenant_id,
            logical_key="shipment-status.disclosure-policy",
            applicability=_applicability(),
            valid_at=datetime(2026, 9, 20, tzinfo=UTC),
            system_at=datetime(2026, 9, 20, tzinfo=UTC),
        )
        allowlist = await authorize_knowledge_retrieval(
            work.knowledge,
            request=KnowledgeRetrievalRequest(
                query=query,
                projection_id=projection.id,
                knowledge_source_id=APPROVED_KNOWLEDGE_SOURCE_ID,
                observation_source_id=APPROVED_OBSERVATION_SOURCE_ID,
                postcondition_id=APPROVED_POSTCONDITION_ID,
            ),
            manifest=SimpleNamespace(active_collection="rag_docs_policy_v1", generation=1),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )
    assert allowlist.versions == ((catalog.versions[0].id, catalog.versions[0].content_digest),)


@pytest.mark.asyncio
async def test_repository_round_trips_supersession_and_conflict_records(
    knowledge_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = uuid4()
    primary_object = KnowledgeObject(
        id=uuid4(),
        tenant_id=tenant_id,
        logical_key="shipment-status.disclosure-policy",
        source_id=APPROVED_KNOWLEDGE_SOURCE_ID,
        owner="logistics-ops",
        authority=APPROVED_KNOWLEDGE_SOURCE_ID,
    )
    secondary_object = replace(
        primary_object,
        id=uuid4(),
        source_id="logistics-policy-secondary",
        authority="logistics-policy-secondary",
    )
    original = KnowledgeVersion(
        id=uuid4(),
        tenant_id=tenant_id,
        object_id=primary_object.id,
        source_revision="policy-r1",
        content_digest="a" * 64,
        valid_range=TimeRange(datetime(2026, 9, 1, tzinfo=UTC), None),
        system_range=TimeRange(_BASE_TIME, _BASE_TIME + timedelta(days=1)),
        applicability=_applicability(),
        locale="en",
    )
    corrected = replace(
        original,
        id=uuid4(),
        source_revision="policy-r2",
        content_digest="b" * 64,
        system_range=TimeRange(_BASE_TIME + timedelta(days=1), None),
    )
    secondary = replace(
        corrected,
        id=uuid4(),
        object_id=secondary_object.id,
        source_revision="secondary-r1",
        content_digest="c" * 64,
    )
    supersession = KnowledgeSupersession(
        predecessor_version_id=original.id,
        successor_version_id=corrected.id,
        reason="source-correction",
        recorded_at=_BASE_TIME + timedelta(days=1),
    )
    conflict_ids = sorted((corrected.id, secondary.id))
    conflict = KnowledgeConflict(
        id=uuid4(),
        tenant_id=tenant_id,
        fact_key="shipment-status.disclosure-allowed",
        left_version_id=conflict_ids[0],
        right_version_id=conflict_ids[1],
        status=ConflictStatus.UNRESOLVED,
        owner="logistics-ops",
    )
    catalog = KnowledgeCatalog(
        objects=(primary_object, secondary_object),
        versions=(original, corrected, secondary),
        supersessions=(supersession,),
        conflicts=(conflict,),
    )

    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        await work.knowledge.append_catalog(tenant_id, catalog)
        await work.commit()
    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        loaded = await work.knowledge.load_catalog(
            tenant_id,
            "shipment-status.disclosure-policy",
        )
    assert loaded.supersessions == (supersession,)
    assert loaded.conflicts == (conflict,)


@pytest.mark.asyncio
async def test_bitemporal_exclusion_and_single_system_close_are_enforced(
    knowledge_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = uuid4()
    catalog = _catalog(tenant_id)
    version = catalog.versions[0]
    close_at = _BASE_TIME + timedelta(days=1)
    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        await work.knowledge.append_catalog(tenant_id, catalog)
        await work.commit()

    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        closed = await work.knowledge.close_version_system_time(
            tenant_id,
            version.id,
            close_at,
        )
        await work.commit()
    assert closed.system_range.end == close_at

    with pytest.raises(KnowledgeSystemCloseConflict):
        async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
            await work.knowledge.close_version_system_time(
                tenant_id,
                version.id,
                close_at + timedelta(days=1),
            )

    adjacent = replace(
        version,
        id=uuid4(),
        source_revision="policy-adjacent",
        content_digest="b" * 64,
        system_range=TimeRange(close_at, None),
    )
    async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
        await work.knowledge.append_version(tenant_id, adjacent)
        await work.commit()

    overlapping = replace(
        adjacent,
        id=uuid4(),
        source_revision="policy-overlap",
        content_digest="c" * 64,
        system_range=TimeRange(close_at + timedelta(hours=1), None),
    )
    with pytest.raises(IntegrityError) as overlap:
        async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
            await work.knowledge.append_version(tenant_id, overlapping)
    assert getattr(overlap.value.orig, "sqlstate", None) == "23P01"

    async with knowledge_session_factory() as session:
        await set_knowledge_tenant_context(session, tenant_id)
        with pytest.raises(DBAPIError) as mutation:
            await session.execute(
                text("UPDATE knowledge_objects SET owner = owner WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            )
        assert getattr(mutation.value.orig, "sqlstate", None) == "55000"
        await session.rollback()


@pytest.mark.asyncio
async def test_forced_rls_default_denies_and_composite_tenant_ownership_holds(
    knowledge_session_factory: async_sessionmaker[AsyncSession],
    runtime_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    catalog_a = _catalog(_TENANT_A, object_id=uuid4(), version_id=uuid4())
    catalog_b = _catalog(_TENANT_B, object_id=uuid4(), version_id=uuid4())
    for tenant_id, catalog in ((_TENANT_A, catalog_a), (_TENANT_B, catalog_b)):
        async with PostgresKnowledgeUnitOfWork(knowledge_session_factory, tenant_id) as work:
            await work.knowledge.append_catalog(tenant_id, catalog)
            await work.commit()

    models = (
        TemporalKnowledgeObject,
        TemporalKnowledgeApplicability,
        TemporalKnowledgeVersion,
        TemporalKnowledgeSupersession,
        TemporalKnowledgeConflict,
        TemporalKnowledgeProjectionBinding,
    )
    async with runtime_session_factory() as session:
        for model in models:
            assert await session.scalar(select(func.count()).select_from(model)) == 0

        await set_knowledge_tenant_context(session, _TENANT_A)
        assert (await session.scalars(select(TemporalKnowledgeObject.id))).all() == [
            catalog_a.objects[0].id
        ]
        assert (await session.scalars(select(TemporalKnowledgeVersion.id))).all() == [
            catalog_a.versions[0].id
        ]
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(TemporalKnowledgeObject)) == 0

    async with PostgresKnowledgeUnitOfWork(runtime_session_factory, _TENANT_A) as work:
        loaded = await work.knowledge.load_catalog(
            _TENANT_A,
            "shipment-status.disclosure-policy",
        )
        assert loaded.objects == catalog_a.objects
        assert loaded.versions == catalog_a.versions
        assert loaded.supersessions == catalog_a.supersessions
        assert loaded.conflicts == catalog_a.conflicts
        with pytest.raises(KnowledgeTenantBoundaryViolation):
            await work.knowledge.load_catalog(
                _TENANT_B,
                "shipment-status.disclosure-policy",
            )

    foreign_version = replace(
        catalog_a.versions[0],
        id=uuid4(),
        tenant_id=_TENANT_B,
    )
    async with knowledge_session_factory() as session:
        await set_knowledge_tenant_context(session, _TENANT_B)
        session.add(
            TemporalKnowledgeVersion(
                id=foreign_version.id,
                tenant_id=foreign_version.tenant_id,
                object_id=foreign_version.object_id,
                applicability_id=uuid4(),
                source_revision=foreign_version.source_revision,
                content_digest=foreign_version.content_digest,
                valid_from=foreign_version.valid_range.start,
                valid_to=foreign_version.valid_range.end,
                system_from=foreign_version.system_range.start,
                system_to=foreign_version.system_range.end,
                locale=foreign_version.locale,
            )
        )
        with pytest.raises(IntegrityError) as ownership:
            await session.flush()
        assert getattr(ownership.value.orig, "sqlstate", None) == "23503"
        await session.rollback()


def test_restore_inventory_tracks_session_turn_orm_table() -> None:
    from scripts.restore_verify import EXPECTED_MODEL_TABLES, EXPECTED_PUBLIC_TABLES

    assert set(_TABLES) <= set(EXPECTED_MODEL_TABLES)
    assert "session_turns" in EXPECTED_MODEL_TABLES
    assert len(EXPECTED_MODEL_TABLES) == 34
    assert len(EXPECTED_PUBLIC_TABLES) == 40
