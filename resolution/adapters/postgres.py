from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ResolutionCaseEvent,
    ResolutionEvidenceLink,
    ResolutionEvidenceSnapshot,
    ResolutionSupportCase,
)
from resolution.domain import (
    CaseEvent,
    CaseEventType,
    CaseMutation,
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
    InvalidDomainValue,
    ProtectedEvidenceReference,
    SupportCase,
    TenantBoundaryViolation,
    TenantContext,
    TimeRange,
)

AsyncSessionFactory = Callable[[], AsyncSession]


async def set_resolution_tenant_context(
    session: AsyncSession,
    context: TenantContext,
) -> None:
    """Bind the tenant UUID to the current PostgreSQL transaction only."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(context.tenant_id)},
    )


def _require_tenant(context: TenantContext, tenant_id: UUID) -> None:
    if context.tenant_id != tenant_id:
        raise TenantBoundaryViolation("repository context does not own the domain value")


def _validate_page(*, after: int, limit: int) -> None:
    if after < 0 or not 1 <= limit <= 1000:
        raise InvalidDomainValue("repository page bounds are invalid")


def _case_record(case: SupportCase) -> ResolutionSupportCase:
    return ResolutionSupportCase(
        id=case.id,
        tenant_id=case.tenant_id,
        contract_id=case.contract.contract_id,
        contract_version=case.contract.version,
        contract_digest=case.contract.digest,
        correlation_id=case.correlation_id,
        status=case.status.value,
        version=case.version,
        opened_at=case.opened_at,
        effective_at=case.effective_at,
        updated_at=case.updated_at,
    )


def _case_domain(record: ResolutionSupportCase) -> SupportCase:
    return SupportCase(
        id=record.id,
        tenant_id=record.tenant_id,
        contract=ContractVersionRef(
            contract_id=record.contract_id,
            version=record.contract_version,
            digest=record.contract_digest,
        ),
        correlation_id=record.correlation_id,
        status=CaseStatus(record.status),
        version=record.version,
        opened_at=record.opened_at,
        effective_at=record.effective_at,
        updated_at=record.updated_at,
    )


def _event_record(event: CaseEvent) -> ResolutionCaseEvent:
    return ResolutionCaseEvent(
        id=event.id,
        tenant_id=event.tenant_id,
        case_id=event.case_id,
        sequence=event.sequence,
        case_version=event.case_version,
        event_type=event.event_type.value,
        command_id=event.command_id,
        actor_id=event.actor_id,
        correlation_id=event.correlation_id,
        from_status=event.from_status.value if event.from_status is not None else None,
        to_status=event.to_status.value,
        reason_code=event.reason_code,
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
    )


def _event_domain(record: ResolutionCaseEvent) -> CaseEvent:
    return CaseEvent(
        id=record.id,
        tenant_id=record.tenant_id,
        case_id=record.case_id,
        sequence=record.sequence,
        case_version=record.case_version,
        event_type=CaseEventType(record.event_type),
        command_id=record.command_id,
        actor_id=record.actor_id,
        correlation_id=record.correlation_id,
        from_status=CaseStatus(record.from_status) if record.from_status is not None else None,
        to_status=CaseStatus(record.to_status),
        reason_code=record.reason_code,
        occurred_at=record.occurred_at,
        recorded_at=record.recorded_at,
    )


def _snapshot_record(snapshot: EvidenceSnapshot) -> ResolutionEvidenceSnapshot:
    return ResolutionEvidenceSnapshot(
        id=snapshot.id,
        tenant_id=snapshot.tenant_id,
        logical_key=snapshot.logical_key,
        source_type=snapshot.source_type.value,
        source_id=snapshot.source_id,
        source_version=snapshot.source_version,
        content_digest=snapshot.content_digest,
        valid_from=snapshot.valid_range.start,
        valid_to=snapshot.valid_range.end,
        recorded_at=snapshot.recorded_at,
        authority=snapshot.authority,
        applicability_key=snapshot.applicability_key,
        visibility=snapshot.visibility.value,
        reference_storage=snapshot.reference.storage.value,
        reference_locator=snapshot.reference.locator,
        encryption_profile=snapshot.reference.encryption_profile,
        redaction_profile=snapshot.reference.redaction_profile,
        retention_class=snapshot.reference.retention_class,
    )


def _snapshot_domain(record: ResolutionEvidenceSnapshot) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id=record.id,
        tenant_id=record.tenant_id,
        logical_key=record.logical_key,
        source_type=EvidenceSourceType(record.source_type),
        source_id=record.source_id,
        source_version=record.source_version,
        content_digest=record.content_digest,
        valid_range=TimeRange(start=record.valid_from, end=record.valid_to),
        recorded_at=record.recorded_at,
        authority=record.authority,
        applicability_key=record.applicability_key,
        visibility=EvidenceVisibility(record.visibility),
        reference=ProtectedEvidenceReference(
            storage=EvidenceStorage(record.reference_storage),
            locator=record.reference_locator,
            encryption_profile=record.encryption_profile,
            redaction_profile=record.redaction_profile,
            retention_class=record.retention_class,
        ),
    )


def _link_record(link: EvidenceLink) -> ResolutionEvidenceLink:
    return ResolutionEvidenceLink(
        id=link.id,
        tenant_id=link.tenant_id,
        case_id=link.case_id,
        case_version=link.case_version,
        evidence_id=link.evidence_id,
        requirement_id=link.requirement_id,
        purpose=link.purpose.value,
        gathered_at=link.gathered_at,
        freshness=link.freshness.value,
    )


def _link_domain(record: ResolutionEvidenceLink) -> EvidenceLink:
    return EvidenceLink(
        id=record.id,
        tenant_id=record.tenant_id,
        case_id=record.case_id,
        case_version=record.case_version,
        evidence_id=record.evidence_id,
        requirement_id=record.requirement_id,
        purpose=EvidencePurpose(record.purpose),
        gathered_at=record.gathered_at,
        freshness=FreshnessStatus(record.freshness),
    )


class PostgresSupportCaseRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _require_context(self, context: TenantContext) -> None:
        _require_tenant(context, self._tenant_id)

    async def get(self, context: TenantContext, case_id: UUID) -> SupportCase | None:
        self._require_context(context)
        record = await self._session.scalar(
            select(ResolutionSupportCase).where(
                ResolutionSupportCase.tenant_id == context.tenant_id,
                ResolutionSupportCase.id == case_id,
            )
        )
        return _case_domain(record) if record is not None else None

    async def append(self, context: TenantContext, mutation: CaseMutation) -> SupportCase:
        self._require_context(context)
        _require_tenant(context, mutation.case.tenant_id)
        _require_tenant(context, mutation.event.tenant_id)
        if mutation.expected_version is None:
            self._session.add(_case_record(mutation.case))
            await self._session.flush()
        else:
            result = await self._session.execute(
                update(ResolutionSupportCase)
                .where(
                    ResolutionSupportCase.tenant_id == context.tenant_id,
                    ResolutionSupportCase.id == mutation.case.id,
                    ResolutionSupportCase.version == mutation.expected_version,
                )
                .values(
                    status=mutation.case.status.value,
                    version=mutation.case.version,
                    updated_at=mutation.case.updated_at,
                )
                .execution_options(synchronize_session=False)
            )
            if int(getattr(result, "rowcount", 0)) != 1:
                actual_version = await self._session.scalar(
                    select(ResolutionSupportCase.version).where(
                        ResolutionSupportCase.tenant_id == context.tenant_id,
                        ResolutionSupportCase.id == mutation.case.id,
                    )
                )
                raise CaseVersionConflict(
                    expected_version=mutation.expected_version,
                    actual_version=actual_version or 0,
                )
        self._session.add(_event_record(mutation.event))
        await self._session.flush()
        return mutation.case

    async def list_events(
        self,
        context: TenantContext,
        case_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> tuple[CaseEvent, ...]:
        self._require_context(context)
        _validate_page(after=after_sequence, limit=limit)
        records = (
            await self._session.scalars(
                select(ResolutionCaseEvent)
                .where(
                    ResolutionCaseEvent.tenant_id == context.tenant_id,
                    ResolutionCaseEvent.case_id == case_id,
                    ResolutionCaseEvent.sequence > after_sequence,
                )
                .order_by(ResolutionCaseEvent.sequence, ResolutionCaseEvent.id)
                .limit(limit)
            )
        ).all()
        return tuple(_event_domain(record) for record in records)


class PostgresEvidenceRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _require_context(self, context: TenantContext) -> None:
        _require_tenant(context, self._tenant_id)

    async def get_snapshot(
        self,
        context: TenantContext,
        evidence_id: UUID,
    ) -> EvidenceSnapshot | None:
        self._require_context(context)
        record = await self._session.scalar(
            select(ResolutionEvidenceSnapshot).where(
                ResolutionEvidenceSnapshot.tenant_id == context.tenant_id,
                ResolutionEvidenceSnapshot.id == evidence_id,
            )
        )
        return _snapshot_domain(record) if record is not None else None

    async def append_snapshot(
        self,
        context: TenantContext,
        snapshot: EvidenceSnapshot,
    ) -> EvidenceSnapshot:
        self._require_context(context)
        _require_tenant(context, snapshot.tenant_id)
        self._session.add(_snapshot_record(snapshot))
        await self._session.flush()
        return snapshot

    async def append_link(self, context: TenantContext, link: EvidenceLink) -> EvidenceLink:
        self._require_context(context)
        _require_tenant(context, link.tenant_id)
        self._session.add(_link_record(link))
        await self._session.flush()
        return link

    async def list_for_case(
        self,
        context: TenantContext,
        case_id: UUID,
        *,
        after_case_version: int = 0,
        limit: int = 100,
    ) -> tuple[EvidenceLink, ...]:
        self._require_context(context)
        _validate_page(after=after_case_version, limit=limit)
        records = (
            await self._session.scalars(
                select(ResolutionEvidenceLink)
                .where(
                    ResolutionEvidenceLink.tenant_id == context.tenant_id,
                    ResolutionEvidenceLink.case_id == case_id,
                    ResolutionEvidenceLink.case_version > after_case_version,
                )
                .order_by(
                    ResolutionEvidenceLink.case_version,
                    ResolutionEvidenceLink.gathered_at,
                    ResolutionEvidenceLink.id,
                )
                .limit(limit)
            )
        ).all()
        return tuple(_link_domain(record) for record in records)


class PostgresResolutionUnitOfWork:
    cases: PostgresSupportCaseRepository
    evidence: PostgresEvidenceRepository

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        context: TenantContext,
    ) -> None:
        self._session_factory = session_factory
        self._context = context
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> PostgresResolutionUnitOfWork:
        if self._session is not None:
            raise RuntimeError("resolution unit of work cannot be entered twice")
        session = self._session_factory()
        try:
            await set_resolution_tenant_context(session, self._context)
        except BaseException:
            await session.rollback()
            await session.close()
            raise
        self._session = session
        self.cases = PostgresSupportCaseRepository(session, self._context.tenant_id)
        self.evidence = PostgresEvidenceRepository(session, self._context.tenant_id)
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
            raise RuntimeError("resolution unit of work is not active")
        return self._session


__all__ = [
    "PostgresEvidenceRepository",
    "PostgresResolutionUnitOfWork",
    "PostgresSupportCaseRepository",
    "set_resolution_tenant_context",
]
