from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from knowledge.application import (
    APPROVED_KNOWLEDGE_SOURCE_ID,
    APPROVED_OBSERVATION_SOURCE_ID,
    APPROVED_POSTCONDITION_ID,
    KnowledgeProjectionRecord,
    KnowledgeRetrievalDenied,
    KnowledgeRetrievalRequest,
    allowlist_chroma_candidates,
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
    KnowledgeVersion,
    TimeRange,
)
from knowledge.projection import bind_projection_manifest

TENANT_ID = UUID("71000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = UUID("71000000-0000-0000-0000-000000000002")
OBJECT_ID = UUID("72000000-0000-0000-0000-000000000001")
SECONDARY_OBJECT_ID = UUID("72000000-0000-0000-0000-000000000002")
VERSION_ID = UUID("73000000-0000-0000-0000-000000000001")
SECONDARY_VERSION_ID = UUID("73000000-0000-0000-0000-000000000002")
PROJECTION_ID = UUID("74000000-0000-0000-0000-000000000001")
CONFLICT_ID = UUID("75000000-0000-0000-0000-000000000001")
INSTANT = datetime(2026, 9, 20, tzinfo=UTC)


def _applicability() -> KnowledgeApplicability:
    return KnowledgeApplicability(
        terms=(
            ApplicabilityTerm(ApplicabilityDimension.PRODUCT, "shipment-status"),
            ApplicabilityTerm(ApplicabilityDimension.REGION, "global"),
            ApplicabilityTerm(ApplicabilityDimension.CUSTOMER_PLAN, "standard"),
            ApplicabilityTerm(ApplicabilityDimension.CARGO_TYPE, "general"),
            ApplicabilityTerm(ApplicabilityDimension.CHANNEL, "chat"),
        )
    )


def _knowledge_object(
    *,
    object_id: UUID = OBJECT_ID,
    source_id: str = APPROVED_KNOWLEDGE_SOURCE_ID,
    authority: str = APPROVED_KNOWLEDGE_SOURCE_ID,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=object_id,
        tenant_id=TENANT_ID,
        logical_key="shipment-status.disclosure-policy",
        source_id=source_id,
        owner="logistics-ops",
        authority=authority,
    )


def _knowledge_version(
    *,
    version_id: UUID = VERSION_ID,
    object_id: UUID = OBJECT_ID,
    digest: str = "a" * 64,
) -> KnowledgeVersion:
    return KnowledgeVersion(
        id=version_id,
        tenant_id=TENANT_ID,
        object_id=object_id,
        source_revision=f"policy-{version_id}",
        content_digest=digest,
        valid_range=TimeRange(datetime(2026, 9, 1, tzinfo=UTC), None),
        system_range=TimeRange(datetime(2026, 8, 1, tzinfo=UTC), None),
        applicability=_applicability(),
        locale="en",
    )


def _query() -> KnowledgeQuery:
    return KnowledgeQuery(
        tenant_id=TENANT_ID,
        logical_key="shipment-status.disclosure-policy",
        applicability=_applicability(),
        valid_at=INSTANT,
        system_at=INSTANT,
    )


def _manifest(*, generation: int = 3) -> SimpleNamespace:
    return SimpleNamespace(active_collection="rag_docs_policy_v3", generation=generation)


def _record(catalog: KnowledgeCatalog) -> KnowledgeProjectionRecord:
    binding = bind_projection_manifest(
        tenant_id=TENANT_ID,
        manifest=_manifest(),
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )
    return KnowledgeProjectionRecord(
        id=PROJECTION_ID,
        tenant_id=TENANT_ID,
        binding=binding,
        recorded_at=INSTANT,
    )


def _request() -> KnowledgeRetrievalRequest:
    return KnowledgeRetrievalRequest(
        query=_query(),
        projection_id=PROJECTION_ID,
        knowledge_source_id=APPROVED_KNOWLEDGE_SOURCE_ID,
        observation_source_id=APPROVED_OBSERVATION_SOURCE_ID,
        postcondition_id=APPROVED_POSTCONDITION_ID,
    )


@dataclass
class _FakeRepository:
    catalog: KnowledgeCatalog
    projection: KnowledgeProjectionRecord | None
    persisted_versions: tuple[KnowledgeVersion, ...] | None = None

    async def load_catalog(self, tenant_id: UUID, logical_key: str) -> KnowledgeCatalog:
        assert tenant_id == TENANT_ID
        assert logical_key == "shipment-status.disclosure-policy"
        return self.catalog

    async def get_projection(
        self,
        tenant_id: UUID,
        projection_id: UUID,
    ) -> KnowledgeProjectionRecord | None:
        assert tenant_id == TENANT_ID
        assert projection_id == PROJECTION_ID
        return self.projection

    async def load_versions(
        self,
        tenant_id: UUID,
        version_ids: tuple[UUID, ...],
    ) -> tuple[KnowledgeVersion, ...]:
        assert tenant_id == TENANT_ID
        versions = self.persisted_versions or self.catalog.versions
        versions_by_id = {version.id: version for version in versions}
        return tuple(
            versions_by_id[version_id] for version_id in version_ids if version_id in versions_by_id
        )


@dataclass(frozen=True)
class _Candidate:
    page_content: str
    metadata: object


@pytest.mark.asyncio
async def test_authority_returns_projection_bound_allowlist_for_exact_approved_context() -> None:
    version = _knowledge_version()
    catalog = KnowledgeCatalog(objects=(_knowledge_object(),), versions=(version,))
    record = _record(catalog)

    allowlist = await authorize_knowledge_retrieval(
        _FakeRepository(catalog, record),
        request=_request(),
        manifest=_manifest(),
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )

    assert allowlist.tenant_id == TENANT_ID
    assert allowlist.active_collection == "rag_docs_policy_v3"
    assert allowlist.manifest_generation == 3
    assert allowlist.projection_digest == record.binding.digest
    assert allowlist.knowledge_source_id == APPROVED_KNOWLEDGE_SOURCE_ID
    assert allowlist.versions == ((VERSION_ID, "a" * 64),)

    accepted = _Candidate(
        "approved",
        {
            "tenant_id": str(TENANT_ID),
            "knowledge_version_id": str(VERSION_ID),
            "knowledge_content_digest": "a" * 64,
            "content_digest": "a" * 64,
            "knowledge_projection_digest": record.binding.digest,
            "knowledge_source_id": APPROVED_KNOWLEDGE_SOURCE_ID,
        },
    )
    candidates = (
        accepted,
        replace(
            accepted,
            page_content="wrong tenant",
            metadata={**accepted.metadata, "tenant_id": str(OTHER_TENANT_ID)},
        ),  # type: ignore[arg-type]
        replace(
            accepted,
            page_content="wrong version",
            metadata={**accepted.metadata, "knowledge_version_id": str(SECONDARY_VERSION_ID)},
        ),  # type: ignore[arg-type]
        replace(
            accepted,
            page_content="wrong digest",
            metadata={**accepted.metadata, "knowledge_content_digest": "b" * 64},
        ),  # type: ignore[arg-type]
        replace(
            accepted,
            page_content="wrong policy digest",
            metadata={**accepted.metadata, "content_digest": "b" * 64},
        ),  # type: ignore[arg-type]
        replace(
            accepted,
            page_content="wrong projection",
            metadata={**accepted.metadata, "knowledge_projection_digest": "d" * 64},
        ),  # type: ignore[arg-type]
        replace(
            accepted,
            page_content="wrong source",
            metadata={**accepted.metadata, "knowledge_source_id": "logistics-policy-secondary"},
        ),  # type: ignore[arg-type]
        _Candidate("malformed", metadata=None),
    )

    assert allowlist_chroma_candidates(candidates, allowlist) == (accepted,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("knowledge_source_id", "logistics-policy-fallback"),
        ("observation_source_id", "shipment-source-fallback"),
        ("postcondition_id", "shipment-observation-fallback"),
    ],
)
async def test_authority_rejects_any_approved_identity_drift(field: str, value: str) -> None:
    version = _knowledge_version()
    catalog = KnowledgeCatalog(objects=(_knowledge_object(),), versions=(version,))
    request = replace(_request(), **{field: value})

    with pytest.raises(KnowledgeRetrievalDenied) as exc_info:
        await authorize_knowledge_retrieval(
            _FakeRepository(catalog, _record(catalog)),
            request=request,
            manifest=_manifest(),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )

    assert exc_info.value.reason_codes == ("UNAPPROVED_KNOWLEDGE_IDENTITY",)


@pytest.mark.asyncio
async def test_authority_collects_material_conflict_before_source_selection() -> None:
    primary = _knowledge_version()
    secondary = _knowledge_version(
        version_id=SECONDARY_VERSION_ID,
        object_id=SECONDARY_OBJECT_ID,
        digest="b" * 64,
    )
    conflict = KnowledgeConflict(
        id=CONFLICT_ID,
        tenant_id=TENANT_ID,
        fact_key="shipment-status.disclosure-allowed",
        left_version_id=primary.id,
        right_version_id=secondary.id,
        status=ConflictStatus.UNRESOLVED,
        owner="logistics-ops",
    )
    catalog = KnowledgeCatalog(
        objects=(
            _knowledge_object(),
            _knowledge_object(
                object_id=SECONDARY_OBJECT_ID,
                source_id="logistics-policy-secondary",
                authority="logistics-policy-secondary",
            ),
        ),
        versions=(primary, secondary),
        conflicts=(conflict,),
    )

    with pytest.raises(KnowledgeRetrievalDenied) as exc_info:
        await authorize_knowledge_retrieval(
            _FakeRepository(catalog, _record(catalog)),
            request=_request(),
            manifest=_manifest(),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )

    assert exc_info.value.reason_codes == ("KNOWLEDGE_CONFLICT",)


@pytest.mark.asyncio
async def test_authority_rejects_missing_projection_and_manifest_drift() -> None:
    version = _knowledge_version()
    catalog = KnowledgeCatalog(objects=(_knowledge_object(),), versions=(version,))

    with pytest.raises(KnowledgeRetrievalDenied) as missing:
        await authorize_knowledge_retrieval(
            _FakeRepository(catalog, None),
            request=_request(),
            manifest=_manifest(),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )
    assert missing.value.reason_codes == ("KNOWLEDGE_PROJECTION_MISSING",)

    with pytest.raises(KnowledgeRetrievalDenied) as drift:
        await authorize_knowledge_retrieval(
            _FakeRepository(catalog, _record(catalog)),
            request=_request(),
            manifest=_manifest(generation=4),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )
    assert drift.value.reason_codes == ("KNOWLEDGE_PROJECTION_MISMATCH",)


@pytest.mark.asyncio
async def test_authority_rejects_eligible_version_from_unapproved_source() -> None:
    version = _knowledge_version()
    catalog = KnowledgeCatalog(
        objects=(
            _knowledge_object(
                source_id="logistics-policy-secondary",
                authority="logistics-policy-secondary",
            ),
        ),
        versions=(version,),
    )

    with pytest.raises(KnowledgeRetrievalDenied) as exc_info:
        await authorize_knowledge_retrieval(
            _FakeRepository(catalog, _record(catalog)),
            request=_request(),
            manifest=_manifest(),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )

    assert exc_info.value.reason_codes == ("UNAPPROVED_KNOWLEDGE_IDENTITY",)


@pytest.mark.asyncio
async def test_authority_rejects_approved_source_with_unapproved_authority_label() -> None:
    version = _knowledge_version()
    catalog = KnowledgeCatalog(
        objects=(_knowledge_object(authority="unapproved-authority-label"),),
        versions=(version,),
    )

    with pytest.raises(KnowledgeRetrievalDenied) as exc_info:
        await authorize_knowledge_retrieval(
            _FakeRepository(catalog, _record(catalog)),
            request=_request(),
            manifest=_manifest(),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )

    assert exc_info.value.reason_codes == ("UNAPPROVED_KNOWLEDGE_IDENTITY",)


@pytest.mark.asyncio
async def test_projection_binding_can_include_another_logical_key() -> None:
    selected = _knowledge_version()
    other_object = replace(
        _knowledge_object(object_id=SECONDARY_OBJECT_ID),
        logical_key="shipment-status.retention-policy",
    )
    other_version = _knowledge_version(
        version_id=SECONDARY_VERSION_ID,
        object_id=SECONDARY_OBJECT_ID,
        digest="b" * 64,
    )
    query_catalog = KnowledgeCatalog(objects=(_knowledge_object(),), versions=(selected,))
    projection_catalog = KnowledgeCatalog(
        objects=(_knowledge_object(), other_object),
        versions=(selected, other_version),
    )

    allowlist = await authorize_knowledge_retrieval(
        _FakeRepository(
            query_catalog,
            _record(projection_catalog),
            persisted_versions=projection_catalog.versions,
        ),
        request=_request(),
        manifest=_manifest(),
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )

    assert allowlist.versions == ((VERSION_ID, "a" * 64),)
