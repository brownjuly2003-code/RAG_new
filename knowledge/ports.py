from __future__ import annotations

from datetime import datetime
from typing import Protocol, Self
from uuid import UUID

from knowledge.domain import KnowledgeCatalog, KnowledgeVersion
from knowledge.projection import KnowledgeProjectionRecord


class KnowledgeTenantBoundaryViolation(PermissionError):
    """A repository context was used with another tenant's identity."""


class KnowledgeSystemCloseConflict(RuntimeError):
    """A version was missing, already closed, or could not be closed exactly once."""


class KnowledgeRepository(Protocol):
    """Tenant-scoped persistence for temporal knowledge and projection records."""

    async def append_catalog(self, tenant_id: UUID, catalog: KnowledgeCatalog) -> None: ...

    async def append_version(self, tenant_id: UUID, version: KnowledgeVersion) -> None: ...

    async def load_catalog(self, tenant_id: UUID, logical_key: str) -> KnowledgeCatalog: ...

    async def load_versions(
        self,
        tenant_id: UUID,
        version_ids: tuple[UUID, ...],
    ) -> tuple[KnowledgeVersion, ...]: ...

    async def close_version_system_time(
        self,
        tenant_id: UUID,
        version_id: UUID,
        closed_at: datetime,
    ) -> KnowledgeVersion: ...

    async def append_projection(self, record: KnowledgeProjectionRecord) -> None: ...

    async def get_projection(
        self,
        tenant_id: UUID,
        projection_id: UUID,
    ) -> KnowledgeProjectionRecord | None: ...


class KnowledgeUnitOfWork(Protocol):
    knowledge: KnowledgeRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


__all__ = [
    "KnowledgeRepository",
    "KnowledgeSystemCloseConflict",
    "KnowledgeTenantBoundaryViolation",
    "KnowledgeUnitOfWork",
]
