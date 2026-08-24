from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    TemporalKnowledgeApplicability,
    TemporalKnowledgeConflict,
    TemporalKnowledgeObject,
    TemporalKnowledgeProjectionBinding,
    TemporalKnowledgeSupersession,
    TemporalKnowledgeVersion,
)
from knowledge.domain import (
    ApplicabilityDimension,
    ApplicabilityTerm,
    ConflictStatus,
    KnowledgeApplicability,
    KnowledgeCatalog,
    KnowledgeConflict,
    KnowledgeDomainError,
    KnowledgeObject,
    KnowledgeSupersession,
    KnowledgeVersion,
    TimeRange,
)
from knowledge.ports import KnowledgeSystemCloseConflict, KnowledgeTenantBoundaryViolation
from knowledge.projection import (
    KnowledgeProjectionBinding,
    KnowledgeProjectionRecord,
    ProjectionBindingMismatch,
)

AsyncSessionFactory = Callable[[], AsyncSession]


async def set_knowledge_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    if not isinstance(tenant_id, UUID) or tenant_id.int == 0:
        raise KnowledgeDomainError("knowledge tenant context must be a non-nil UUID")
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _require_tenant(expected: UUID, actual: UUID) -> None:
    if expected != actual:
        raise KnowledgeTenantBoundaryViolation("knowledge repository context does not own value")


def _applicability_values(applicability: KnowledgeApplicability) -> dict[str, str]:
    values = {term.dimension.value: term.value for term in applicability.terms}
    required = {dimension.value for dimension in ApplicabilityDimension}
    if set(values) != required:
        raise KnowledgeDomainError("knowledge applicability must contain the exact five dimensions")
    return values


def _applicability_id(tenant_id: UUID, applicability: KnowledgeApplicability) -> UUID:
    canonical = json.dumps(
        applicability.key,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return uuid5(
        NAMESPACE_URL,
        f"rag-new:knowledge-applicability:{tenant_id}:{canonical}",
    )


def _object_record(value: KnowledgeObject) -> TemporalKnowledgeObject:
    return TemporalKnowledgeObject(
        id=value.id,
        tenant_id=value.tenant_id,
        logical_key=value.logical_key,
        source_id=value.source_id,
        owner=value.owner,
        authority=value.authority,
    )


def _object_domain(record: TemporalKnowledgeObject) -> KnowledgeObject:
    return KnowledgeObject(
        id=record.id,
        tenant_id=record.tenant_id,
        logical_key=record.logical_key,
        source_id=record.source_id,
        owner=record.owner,
        authority=record.authority,
    )


def _version_record(
    value: KnowledgeVersion,
    applicability_id: UUID,
) -> TemporalKnowledgeVersion:
    return TemporalKnowledgeVersion(
        id=value.id,
        tenant_id=value.tenant_id,
        object_id=value.object_id,
        applicability_id=applicability_id,
        source_revision=value.source_revision,
        content_digest=value.content_digest,
        valid_from=value.valid_range.start,
        valid_to=value.valid_range.end,
        system_from=value.system_range.start,
        system_to=value.system_range.end,
        locale=value.locale,
    )


def _applicability_domain(
    record: TemporalKnowledgeApplicability,
) -> KnowledgeApplicability:
    return KnowledgeApplicability(
        terms=(
            ApplicabilityTerm(ApplicabilityDimension.PRODUCT, record.product),
            ApplicabilityTerm(ApplicabilityDimension.REGION, record.region),
            ApplicabilityTerm(
                ApplicabilityDimension.CUSTOMER_PLAN,
                record.customer_plan,
            ),
            ApplicabilityTerm(ApplicabilityDimension.CARGO_TYPE, record.cargo_type),
            ApplicabilityTerm(ApplicabilityDimension.CHANNEL, record.channel),
        )
    )


def _version_domain(
    record: TemporalKnowledgeVersion,
    applicability: TemporalKnowledgeApplicability,
) -> KnowledgeVersion:
    return KnowledgeVersion(
        id=record.id,
        tenant_id=record.tenant_id,
        object_id=record.object_id,
        source_revision=record.source_revision,
        content_digest=record.content_digest,
        valid_range=TimeRange(record.valid_from, record.valid_to),
        system_range=TimeRange(record.system_from, record.system_to),
        applicability=_applicability_domain(applicability),
        locale=record.locale,
    )


class PostgresKnowledgeRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _require_context(self, tenant_id: UUID) -> None:
        _require_tenant(self._tenant_id, tenant_id)

    async def _ensure_applicability(
        self,
        tenant_id: UUID,
        applicability: KnowledgeApplicability,
    ) -> UUID:
        values = _applicability_values(applicability)
        applicability_id = _applicability_id(tenant_id, applicability)
        statement = (
            postgresql_insert(TemporalKnowledgeApplicability)
            .values(id=applicability_id, tenant_id=tenant_id, **values)
            .on_conflict_do_nothing(
                index_elements=[
                    "tenant_id",
                    "product",
                    "region",
                    "customer_plan",
                    "cargo_type",
                    "channel",
                ]
            )
        )
        await self._session.execute(statement)
        record = await self._session.scalar(
            select(TemporalKnowledgeApplicability).where(
                TemporalKnowledgeApplicability.tenant_id == tenant_id,
                TemporalKnowledgeApplicability.product == values["product"],
                TemporalKnowledgeApplicability.region == values["region"],
                TemporalKnowledgeApplicability.customer_plan == values["customer_plan"],
                TemporalKnowledgeApplicability.cargo_type == values["cargo_type"],
                TemporalKnowledgeApplicability.channel == values["channel"],
            )
        )
        if record is None or record.id != applicability_id:
            raise KnowledgeDomainError("durable applicability identity mismatch")
        return applicability_id

    async def append_catalog(self, tenant_id: UUID, catalog: KnowledgeCatalog) -> None:
        self._require_context(tenant_id)
        for knowledge_object in catalog.objects:
            _require_tenant(tenant_id, knowledge_object.tenant_id)
        for version in catalog.versions:
            _require_tenant(tenant_id, version.tenant_id)
        for conflict in catalog.conflicts:
            _require_tenant(tenant_id, conflict.tenant_id)

        self._session.add_all([_object_record(value) for value in catalog.objects])
        await self._session.flush()

        for version in catalog.versions:
            applicability_id = await self._ensure_applicability(tenant_id, version.applicability)
            self._session.add(_version_record(version, applicability_id))
        await self._session.flush()

        versions_by_id = {version.id: version for version in catalog.versions}
        for relation in catalog.supersessions:
            predecessor = versions_by_id[relation.predecessor_version_id]
            self._session.add(
                TemporalKnowledgeSupersession(
                    tenant_id=tenant_id,
                    predecessor_version_id=relation.predecessor_version_id,
                    successor_version_id=relation.successor_version_id,
                    object_id=predecessor.object_id,
                    reason=relation.reason,
                    recorded_at=relation.recorded_at,
                )
            )
        for conflict in catalog.conflicts:
            left_version_id, right_version_id = sorted(
                (conflict.left_version_id, conflict.right_version_id)
            )
            self._session.add(
                TemporalKnowledgeConflict(
                    id=conflict.id,
                    tenant_id=conflict.tenant_id,
                    fact_key=conflict.fact_key,
                    left_version_id=left_version_id,
                    right_version_id=right_version_id,
                    status=conflict.status.value,
                    owner=conflict.owner,
                )
            )
        await self._session.flush()

    async def append_version(self, tenant_id: UUID, version: KnowledgeVersion) -> None:
        self._require_context(tenant_id)
        _require_tenant(tenant_id, version.tenant_id)
        applicability_id = await self._ensure_applicability(tenant_id, version.applicability)
        self._session.add(_version_record(version, applicability_id))
        await self._session.flush()

    async def load_catalog(self, tenant_id: UUID, logical_key: str) -> KnowledgeCatalog:
        self._require_context(tenant_id)
        objects = (
            await self._session.scalars(
                select(TemporalKnowledgeObject)
                .where(
                    TemporalKnowledgeObject.tenant_id == tenant_id,
                    TemporalKnowledgeObject.logical_key == logical_key,
                )
                .order_by(TemporalKnowledgeObject.id)
            )
        ).all()
        if not objects:
            return KnowledgeCatalog(objects=(), versions=())

        object_ids = tuple(record.id for record in objects)
        version_records = (
            await self._session.scalars(
                select(TemporalKnowledgeVersion)
                .where(
                    TemporalKnowledgeVersion.tenant_id == tenant_id,
                    TemporalKnowledgeVersion.object_id.in_(object_ids),
                )
                .order_by(TemporalKnowledgeVersion.id)
            )
        ).all()
        applicability_ids = {record.applicability_id for record in version_records}
        applicability_records = (
            await self._session.scalars(
                select(TemporalKnowledgeApplicability).where(
                    TemporalKnowledgeApplicability.tenant_id == tenant_id,
                    TemporalKnowledgeApplicability.id.in_(applicability_ids),
                )
            )
        ).all()
        applicability_by_id = {record.id: record for record in applicability_records}
        versions = tuple(
            _version_domain(record, applicability_by_id[record.applicability_id])
            for record in version_records
        )
        version_ids = tuple(version.id for version in versions)
        supersession_records = (
            await self._session.scalars(
                select(TemporalKnowledgeSupersession)
                .where(
                    TemporalKnowledgeSupersession.tenant_id == tenant_id,
                    TemporalKnowledgeSupersession.predecessor_version_id.in_(version_ids),
                    TemporalKnowledgeSupersession.successor_version_id.in_(version_ids),
                )
                .order_by(
                    TemporalKnowledgeSupersession.predecessor_version_id,
                    TemporalKnowledgeSupersession.successor_version_id,
                )
            )
        ).all()
        conflict_records = (
            await self._session.scalars(
                select(TemporalKnowledgeConflict)
                .where(
                    TemporalKnowledgeConflict.tenant_id == tenant_id,
                    TemporalKnowledgeConflict.left_version_id.in_(version_ids),
                    TemporalKnowledgeConflict.right_version_id.in_(version_ids),
                )
                .order_by(TemporalKnowledgeConflict.id)
            )
        ).all()
        return KnowledgeCatalog(
            objects=tuple(_object_domain(record) for record in objects),
            versions=versions,
            supersessions=tuple(
                KnowledgeSupersession(
                    predecessor_version_id=record.predecessor_version_id,
                    successor_version_id=record.successor_version_id,
                    reason=record.reason,
                    recorded_at=record.recorded_at,
                )
                for record in supersession_records
            ),
            conflicts=tuple(
                KnowledgeConflict(
                    id=record.id,
                    tenant_id=record.tenant_id,
                    fact_key=record.fact_key,
                    left_version_id=record.left_version_id,
                    right_version_id=record.right_version_id,
                    status=ConflictStatus(record.status),
                    owner=record.owner,
                )
                for record in conflict_records
            ),
        )

    async def load_versions(
        self,
        tenant_id: UUID,
        version_ids: tuple[UUID, ...],
    ) -> tuple[KnowledgeVersion, ...]:
        self._require_context(tenant_id)
        if not version_ids:
            return ()
        records = (
            await self._session.scalars(
                select(TemporalKnowledgeVersion)
                .where(
                    TemporalKnowledgeVersion.tenant_id == tenant_id,
                    TemporalKnowledgeVersion.id.in_(version_ids),
                )
                .order_by(TemporalKnowledgeVersion.id)
            )
        ).all()
        applicability_ids = {record.applicability_id for record in records}
        applicability_records = (
            await self._session.scalars(
                select(TemporalKnowledgeApplicability).where(
                    TemporalKnowledgeApplicability.tenant_id == tenant_id,
                    TemporalKnowledgeApplicability.id.in_(applicability_ids),
                )
            )
        ).all()
        applicability_by_id = {record.id: record for record in applicability_records}
        return tuple(
            _version_domain(record, applicability_by_id[record.applicability_id])
            for record in records
        )

    async def close_version_system_time(
        self,
        tenant_id: UUID,
        version_id: UUID,
        closed_at: datetime,
    ) -> KnowledgeVersion:
        self._require_context(tenant_id)
        if closed_at.tzinfo is None or closed_at.utcoffset() is None:
            raise KnowledgeSystemCloseConflict("system close must be timezone-aware")
        record = await self._session.scalar(
            select(TemporalKnowledgeVersion)
            .where(
                TemporalKnowledgeVersion.tenant_id == tenant_id,
                TemporalKnowledgeVersion.id == version_id,
            )
            .with_for_update()
        )
        if record is None or record.system_to is not None or closed_at <= record.system_from:
            raise KnowledgeSystemCloseConflict("knowledge version cannot be system-closed")
        result = await self._session.execute(
            update(TemporalKnowledgeVersion)
            .where(
                TemporalKnowledgeVersion.tenant_id == tenant_id,
                TemporalKnowledgeVersion.id == version_id,
                TemporalKnowledgeVersion.system_to.is_(None),
            )
            .values(system_to=closed_at)
            .execution_options(synchronize_session=False)
        )
        if int(getattr(result, "rowcount", 0)) != 1:
            raise KnowledgeSystemCloseConflict("knowledge version close lost a race")
        await self._session.flush()
        await self._session.refresh(record)
        applicability = await self._session.scalar(
            select(TemporalKnowledgeApplicability).where(
                TemporalKnowledgeApplicability.tenant_id == tenant_id,
                TemporalKnowledgeApplicability.id == record.applicability_id,
            )
        )
        if applicability is None:
            raise KnowledgeDomainError("knowledge version applicability is missing")
        return _version_domain(record, applicability)

    async def append_projection(self, record: KnowledgeProjectionRecord) -> None:
        self._require_context(record.tenant_id)
        self._session.add(
            TemporalKnowledgeProjectionBinding(
                id=record.id,
                tenant_id=record.tenant_id,
                active_collection=record.binding.active_collection,
                manifest_generation=record.binding.manifest_generation,
                source_versions=[list(item) for item in record.binding.source_versions],
                embedding_model=record.binding.embedding_model,
                embedding_dimension=record.binding.embedding_dimension,
                index_config_digest=record.binding.index_config_digest,
                digest=record.binding.digest,
                recorded_at=record.recorded_at,
            )
        )
        await self._session.flush()

    async def get_projection(
        self,
        tenant_id: UUID,
        projection_id: UUID,
    ) -> KnowledgeProjectionRecord | None:
        self._require_context(tenant_id)
        record = await self._session.scalar(
            select(TemporalKnowledgeProjectionBinding).where(
                TemporalKnowledgeProjectionBinding.tenant_id == tenant_id,
                TemporalKnowledgeProjectionBinding.id == projection_id,
            )
        )
        if record is None:
            return None
        source_versions_value = record.source_versions
        try:
            source_versions = tuple((str(item[0]), str(item[1])) for item in source_versions_value)
        except (IndexError, TypeError) as exc:
            raise ProjectionBindingMismatch(
                "stored projection source versions are invalid"
            ) from exc
        binding = KnowledgeProjectionBinding(
            tenant_id=record.tenant_id,
            active_collection=record.active_collection,
            manifest_generation=record.manifest_generation,
            source_versions=source_versions,
            embedding_model=record.embedding_model,
            embedding_dimension=record.embedding_dimension,
            index_config_digest=record.index_config_digest,
            digest=record.digest,
        )
        return KnowledgeProjectionRecord(
            id=record.id,
            tenant_id=record.tenant_id,
            binding=binding,
            recorded_at=record.recorded_at,
        )


class PostgresKnowledgeUnitOfWork:
    knowledge: PostgresKnowledgeRepository

    def __init__(self, session_factory: AsyncSessionFactory, tenant_id: UUID) -> None:
        self._session_factory = session_factory
        self._tenant_id = tenant_id
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> PostgresKnowledgeUnitOfWork:
        if self._session is not None:
            raise RuntimeError("knowledge unit of work cannot be entered twice")
        session = self._session_factory()
        try:
            await set_knowledge_tenant_context(session, self._tenant_id)
        except BaseException:
            await session.rollback()
            await session.close()
            raise
        self._session = session
        self.knowledge = PostgresKnowledgeRepository(session, self._tenant_id)
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None or not self._committed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._committed = False

    async def commit(self) -> None:
        session = self._require_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        session = self._require_session()
        await session.rollback()
        self._committed = False

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("knowledge unit of work is not active")
        return self._session


__all__ = [
    "PostgresKnowledgeRepository",
    "PostgresKnowledgeUnitOfWork",
    "set_knowledge_tenant_context",
]
