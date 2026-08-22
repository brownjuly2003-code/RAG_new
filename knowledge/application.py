from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from knowledge.domain import KnowledgeQuery, KnowledgeSelectionStatus, KnowledgeVersion
from knowledge.ports import KnowledgeRepository
from knowledge.projection import (
    IndexManifestLike,
    KnowledgeProjectionRecord,
    ProjectionBindingMismatch,
    verify_projection_manifest,
)

APPROVED_KNOWLEDGE_SOURCE_ID = "logistics-policy-primary"
APPROVED_OBSERVATION_SOURCE_ID = "shipment-source-primary"
APPROVED_POSTCONDITION_ID = "shipment-observation-current"


class KnowledgeRetrievalDenied(RuntimeError):
    """Temporal knowledge is not safe to expose to retrieval."""

    def __init__(self, *reason_codes: str) -> None:
        if not reason_codes:
            raise ValueError("knowledge retrieval denial requires a reason code")
        self.reason_codes = tuple(reason_codes)
        super().__init__(", ".join(self.reason_codes))


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalRequest:
    query: KnowledgeQuery
    projection_id: UUID
    knowledge_source_id: str
    observation_source_id: str
    postcondition_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.projection_id, UUID) or self.projection_id.int == 0:
            raise ValueError("knowledge retrieval projection id must be a non-nil UUID")


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalAllowlist:
    tenant_id: UUID
    active_collection: str
    manifest_generation: int
    projection_digest: str
    knowledge_source_id: str
    versions: tuple[tuple[UUID, str], ...]


def _approved_identity(request: KnowledgeRetrievalRequest) -> bool:
    return (
        request.knowledge_source_id == APPROVED_KNOWLEDGE_SOURCE_ID
        and request.observation_source_id == APPROVED_OBSERVATION_SOURCE_ID
        and request.postcondition_id == APPROVED_POSTCONDITION_ID
    )


def _projection_versions(
    record: KnowledgeProjectionRecord,
    catalog_versions: tuple[KnowledgeVersion, ...],
) -> tuple[KnowledgeVersion, ...]:
    versions_by_id = {version.id: version for version in catalog_versions}
    projected: list[KnowledgeVersion] = []
    try:
        for version_text, digest in record.binding.source_versions:
            version_id = UUID(version_text)
            version = versions_by_id.get(version_id)
            if version is None or version.content_digest != digest:
                raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH")
            projected.append(version)
    except (TypeError, ValueError) as exc:
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH") from exc
    if not projected:
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH")
    return tuple(projected)


async def authorize_knowledge_retrieval(
    repository: KnowledgeRepository,
    *,
    request: KnowledgeRetrievalRequest,
    manifest: IndexManifestLike,
    embedding_model: str,
    embedding_dimension: int,
    index_config_digest: str,
) -> KnowledgeRetrievalAllowlist:
    """Resolve all authorities first, then issue an exact Chroma metadata allowlist."""

    if not _approved_identity(request):
        raise KnowledgeRetrievalDenied("UNAPPROVED_KNOWLEDGE_IDENTITY")

    query = request.query
    catalog = await repository.load_catalog(query.tenant_id, query.logical_key)
    selection = catalog.select(query)
    if selection.status is not KnowledgeSelectionStatus.ELIGIBLE:
        raise KnowledgeRetrievalDenied(*selection.reason_codes)

    objects_by_id = {knowledge_object.id: knowledge_object for knowledge_object in catalog.objects}
    if any(
        objects_by_id[version.object_id].source_id != APPROVED_KNOWLEDGE_SOURCE_ID
        or objects_by_id[version.object_id].authority != APPROVED_KNOWLEDGE_SOURCE_ID
        for version in selection.versions
    ):
        raise KnowledgeRetrievalDenied("UNAPPROVED_KNOWLEDGE_IDENTITY")

    record = await repository.get_projection(query.tenant_id, request.projection_id)
    if record is None:
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISSING")
    if record.tenant_id != query.tenant_id:
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH")

    try:
        projected_version_ids = tuple(
            UUID(version_text) for version_text, _digest in record.binding.source_versions
        )
    except (TypeError, ValueError) as exc:
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH") from exc
    persisted_versions = await repository.load_versions(
        query.tenant_id,
        projected_version_ids,
    )
    projected_versions = _projection_versions(record, persisted_versions)
    try:
        verify_projection_manifest(
            tenant_id=query.tenant_id,
            binding=record.binding,
            manifest=manifest,
            versions=projected_versions,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            index_config_digest=index_config_digest,
        )
    except ProjectionBindingMismatch as exc:
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH") from exc

    projected_ids = {version.id for version in projected_versions}
    if any(version.id not in projected_ids for version in selection.versions):
        raise KnowledgeRetrievalDenied("KNOWLEDGE_PROJECTION_MISMATCH")
    versions = tuple(
        sorted(
            ((version.id, version.content_digest) for version in selection.versions),
            key=lambda item: str(item[0]),
        )
    )
    return KnowledgeRetrievalAllowlist(
        tenant_id=query.tenant_id,
        active_collection=record.binding.active_collection,
        manifest_generation=record.binding.manifest_generation,
        projection_digest=record.binding.digest,
        knowledge_source_id=APPROVED_KNOWLEDGE_SOURCE_ID,
        versions=versions,
    )


_CandidateT = TypeVar("_CandidateT")


def allowlist_chroma_candidates(
    candidates: Iterable[_CandidateT],
    allowlist: KnowledgeRetrievalAllowlist,
) -> tuple[_CandidateT, ...]:
    """Retain only candidates carrying the complete authorized projection identity."""

    allowed_versions = {str(version_id): digest for version_id, digest in allowlist.versions}
    accepted: list[_CandidateT] = []
    for candidate in candidates:
        metadata = (
            candidate.get("metadata")
            if isinstance(candidate, Mapping)
            else getattr(candidate, "metadata", None)
        )
        if not isinstance(metadata, Mapping):
            continue
        version_id = metadata.get("knowledge_version_id")
        digest = metadata.get("knowledge_content_digest")
        if (
            metadata.get("tenant_id") != str(allowlist.tenant_id)
            or metadata.get("knowledge_projection_digest") != allowlist.projection_digest
            or metadata.get("knowledge_source_id") != allowlist.knowledge_source_id
            or not isinstance(version_id, str)
            or not isinstance(digest, str)
            or allowed_versions.get(version_id) != digest
            or metadata.get("content_digest") != digest
        ):
            continue
        accepted.append(candidate)
    return tuple(accepted)


__all__ = [
    "APPROVED_KNOWLEDGE_SOURCE_ID",
    "APPROVED_OBSERVATION_SOURCE_ID",
    "APPROVED_POSTCONDITION_ID",
    "KnowledgeProjectionRecord",
    "KnowledgeRetrievalAllowlist",
    "KnowledgeRetrievalDenied",
    "KnowledgeRetrievalRequest",
    "allowlist_chroma_candidates",
    "authorize_knowledge_retrieval",
]
