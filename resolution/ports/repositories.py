from __future__ import annotations

from typing import Protocol, Self
from uuid import UUID

from resolution.domain import (
    CaseEvent,
    CaseMutation,
    EvidenceLink,
    EvidenceSnapshot,
    SupportCase,
    TenantContext,
)


class SupportCaseRepository(Protocol):
    """Tenant-scoped append-only persistence for the SupportCase aggregate."""

    async def get(self, context: TenantContext, case_id: UUID) -> SupportCase | None: ...

    async def append(self, context: TenantContext, mutation: CaseMutation) -> SupportCase:
        """Atomically append the event and enforce mutation.expected_version."""
        ...

    async def list_events(
        self,
        context: TenantContext,
        case_id: UUID,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> tuple[CaseEvent, ...]: ...


class EvidenceRepository(Protocol):
    """Tenant-scoped append-only evidence and case-link persistence."""

    async def get_snapshot(
        self,
        context: TenantContext,
        evidence_id: UUID,
    ) -> EvidenceSnapshot | None: ...

    async def append_snapshot(
        self,
        context: TenantContext,
        snapshot: EvidenceSnapshot,
    ) -> EvidenceSnapshot: ...

    async def append_link(
        self,
        context: TenantContext,
        link: EvidenceLink,
    ) -> EvidenceLink: ...

    async def list_for_case(
        self,
        context: TenantContext,
        case_id: UUID,
        *,
        after_case_version: int = 0,
        limit: int = 100,
    ) -> tuple[EvidenceLink, ...]: ...


class ResolutionUnitOfWork(Protocol):
    """One transaction boundary for case and evidence appends."""

    cases: SupportCaseRepository
    evidence: EvidenceRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


__all__ = ["EvidenceRepository", "ResolutionUnitOfWork", "SupportCaseRepository"]
