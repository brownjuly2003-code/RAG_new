from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge.domain import (
    ApplicabilityDimension,
    ApplicabilityTerm,
    ConflictStatus,
    KnowledgeApplicability,
    KnowledgeCatalog,
    KnowledgeConflict,
    KnowledgeDomainError,
    KnowledgeObject,
    KnowledgeQuery,
    KnowledgeSelectionStatus,
    KnowledgeSupersession,
    KnowledgeTemporalOverlap,
    KnowledgeVersion,
    TimeRange,
)
from knowledge.projection import (
    ProjectionBindingMismatch,
    bind_projection_manifest,
    verify_projection_manifest,
)

TENANT_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = UUID("30000000-0000-0000-0000-000000000002")
PRIMARY_OBJECT_ID = UUID("40000000-0000-0000-0000-000000000001")
SECONDARY_OBJECT_ID = UUID("40000000-0000-0000-0000-000000000002")
V1_ID = UUID("50000000-0000-0000-0000-000000000001")
V2_ID = UUID("50000000-0000-0000-0000-000000000002")
SECONDARY_VERSION_ID = UUID("50000000-0000-0000-0000-000000000003")
CONFLICT_ID = UUID("60000000-0000-0000-0000-000000000001")

SYSTEM_START = datetime(2026, 8, 1, tzinfo=UTC)
POLICY_CHANGE = datetime(2026, 9, 15, tzinfo=UTC)
SYSTEM_CORRECTION = datetime(2026, 10, 1, tzinfo=UTC)


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


def _object(
    *,
    object_id: UUID = PRIMARY_OBJECT_ID,
    tenant_id: UUID = TENANT_ID,
    source_id: str = "logistics-policy-primary",
    authority: str = "logistics-policy-primary",
) -> KnowledgeObject:
    return KnowledgeObject(
        id=object_id,
        tenant_id=tenant_id,
        logical_key="shipment-status.disclosure-policy",
        source_id=source_id,
        owner="logistics-ops",
        authority=authority,
    )


def _version(
    *,
    version_id: UUID,
    object_id: UUID = PRIMARY_OBJECT_ID,
    tenant_id: UUID = TENANT_ID,
    source_revision: str,
    digest: str,
    valid_from: datetime,
    valid_to: datetime | None,
    system_from: datetime = SYSTEM_START,
    system_to: datetime | None = None,
    channel: str = "chat",
) -> KnowledgeVersion:
    return KnowledgeVersion(
        id=version_id,
        tenant_id=tenant_id,
        object_id=object_id,
        source_revision=source_revision,
        content_digest=digest,
        valid_range=TimeRange(valid_from, valid_to),
        system_range=TimeRange(system_from, system_to),
        applicability=_applicability(channel=channel),
        locale="en",
    )


def _query(
    *,
    valid_at: datetime,
    system_at: datetime = datetime(2026, 9, 1, tzinfo=UTC),
    tenant_id: UUID = TENANT_ID,
    channel: str = "chat",
) -> KnowledgeQuery:
    return KnowledgeQuery(
        tenant_id=tenant_id,
        logical_key="shipment-status.disclosure-policy",
        applicability=_applicability(channel=channel),
        valid_at=valid_at,
        system_at=system_at,
    )


def _policy_change_catalog() -> tuple[KnowledgeCatalog, KnowledgeVersion, KnowledgeVersion]:
    old = _version(
        version_id=V1_ID,
        source_revision="policy-2026.09-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=POLICY_CHANGE,
    )
    current = _version(
        version_id=V2_ID,
        source_revision="policy-2026.09-r2",
        digest="b" * 64,
        valid_from=POLICY_CHANGE,
        valid_to=None,
    )
    return KnowledgeCatalog(objects=(_object(),), versions=(old, current)), old, current


def test_business_time_selects_policy_before_and_after_change() -> None:
    catalog, old, current = _policy_change_catalog()

    before = catalog.select(
        _query(valid_at=POLICY_CHANGE.replace(day=14), system_at=SYSTEM_CORRECTION)
    )
    after = catalog.select(_query(valid_at=POLICY_CHANGE, system_at=SYSTEM_CORRECTION))

    assert before.status is KnowledgeSelectionStatus.ELIGIBLE
    assert before.versions == (old,)
    assert after.status is KnowledgeSelectionStatus.ELIGIBLE
    assert after.versions == (current,)


def test_system_time_replays_original_and_corrected_policy() -> None:
    original = _version(
        version_id=V1_ID,
        source_revision="policy-recorded-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
        system_from=SYSTEM_START,
        system_to=SYSTEM_CORRECTION,
    )
    corrected = _version(
        version_id=V2_ID,
        source_revision="policy-recorded-r2",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
        system_from=SYSTEM_CORRECTION,
        system_to=None,
    )
    supersession = KnowledgeSupersession(
        predecessor_version_id=original.id,
        successor_version_id=corrected.id,
        reason="source-correction",
        recorded_at=SYSTEM_CORRECTION,
    )
    catalog = KnowledgeCatalog(
        objects=(_object(),),
        versions=(original, corrected),
        supersessions=(supersession,),
    )

    historical = catalog.select(
        _query(
            valid_at=datetime(2026, 9, 20, tzinfo=UTC),
            system_at=datetime(2026, 9, 30, tzinfo=UTC),
        )
    )
    corrected_replay = catalog.select(
        _query(
            valid_at=datetime(2026, 9, 20, tzinfo=UTC),
            system_at=SYSTEM_CORRECTION,
        )
    )

    assert historical.versions == (original,)
    assert corrected_replay.versions == (corrected,)


def test_within_source_bitemporal_overlap_is_rejected() -> None:
    first = _version(
        version_id=V1_ID,
        source_revision="policy-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=datetime(2026, 9, 20, tzinfo=UTC),
    )
    overlapping = _version(
        version_id=V2_ID,
        source_revision="policy-r2",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 19, tzinfo=UTC),
        valid_to=None,
    )

    with pytest.raises(KnowledgeTemporalOverlap, match="authoritative source"):
        KnowledgeCatalog(objects=(_object(),), versions=(first, overlapping))


def test_same_source_cannot_evade_overlap_by_changing_authority_label() -> None:
    first = _version(
        version_id=V1_ID,
        source_revision="policy-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )
    overlapping = _version(
        version_id=V2_ID,
        object_id=SECONDARY_OBJECT_ID,
        source_revision="policy-r2",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )

    with pytest.raises(KnowledgeTemporalOverlap, match="authoritative source"):
        KnowledgeCatalog(
            objects=(
                _object(),
                _object(
                    object_id=SECONDARY_OBJECT_ID,
                    source_id="logistics-policy-primary",
                    authority="untrusted-authority-label",
                ),
            ),
            versions=(first, overlapping),
        )


def test_same_valid_range_is_allowed_for_non_overlapping_system_ranges() -> None:
    original = _version(
        version_id=V1_ID,
        source_revision="policy-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
        system_to=SYSTEM_CORRECTION,
    )
    correction = _version(
        version_id=V2_ID,
        source_revision="policy-r2",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
        system_from=SYSTEM_CORRECTION,
    )

    catalog = KnowledgeCatalog(objects=(_object(),), versions=(original, correction))

    assert len(catalog.versions) == 2


def test_exact_applicability_prevents_cross_channel_fallback() -> None:
    chat = _version(
        version_id=V1_ID,
        source_revision="chat-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
        channel="chat",
    )
    email = _version(
        version_id=V2_ID,
        source_revision="email-r1",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
        channel="email",
    )
    catalog = KnowledgeCatalog(objects=(_object(),), versions=(chat, email))

    selected = catalog.select(_query(valid_at=datetime(2026, 9, 20, tzinfo=UTC), channel="email"))
    missing = catalog.select(_query(valid_at=datetime(2026, 9, 20, tzinfo=UTC), channel="api"))

    assert selected.versions == (email,)
    assert missing.status is KnowledgeSelectionStatus.MISSING


def test_wildcard_applicability_is_rejected() -> None:
    with pytest.raises(KnowledgeDomainError, match="wildcard"):
        ApplicabilityTerm(ApplicabilityDimension.REGION, "*")


def test_cross_authority_conflict_is_explicit_and_fails_closed() -> None:
    primary = _version(
        version_id=V1_ID,
        source_revision="primary-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )
    secondary = _version(
        version_id=SECONDARY_VERSION_ID,
        object_id=SECONDARY_OBJECT_ID,
        source_revision="secondary-r1",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
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
            _object(),
            _object(
                object_id=SECONDARY_OBJECT_ID,
                source_id="logistics-policy-secondary",
                authority="logistics-policy-secondary",
            ),
        ),
        versions=(primary, secondary),
        conflicts=(conflict,),
    )

    selection = catalog.select(_query(valid_at=datetime(2026, 9, 20, tzinfo=UTC)))

    assert selection.status is KnowledgeSelectionStatus.CONFLICT
    assert selection.versions == ()
    assert selection.conflicts == (conflict,)
    assert selection.reason_codes == ("KNOWLEDGE_CONFLICT",)


def test_unrecorded_cross_authority_difference_still_fails_closed() -> None:
    primary = _version(
        version_id=V1_ID,
        source_revision="primary-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )
    secondary = _version(
        version_id=SECONDARY_VERSION_ID,
        object_id=SECONDARY_OBJECT_ID,
        source_revision="secondary-r1",
        digest="b" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )
    catalog = KnowledgeCatalog(
        objects=(
            _object(),
            _object(
                object_id=SECONDARY_OBJECT_ID,
                source_id="logistics-policy-secondary",
                authority="logistics-policy-secondary",
            ),
        ),
        versions=(primary, secondary),
    )

    selection = catalog.select(_query(valid_at=datetime(2026, 9, 20, tzinfo=UTC)))

    assert selection.status is KnowledgeSelectionStatus.CONFLICT
    assert selection.reason_codes == ("UNRECORDED_KNOWLEDGE_CONFLICT",)


def test_tenant_and_object_ownership_mismatch_is_rejected() -> None:
    foreign = _version(
        version_id=V1_ID,
        tenant_id=OTHER_TENANT_ID,
        source_revision="foreign-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )

    with pytest.raises(KnowledgeDomainError, match="tenant ownership"):
        KnowledgeCatalog(objects=(_object(),), versions=(foreign,))


def test_projection_binding_pins_manifest_and_source_version_digests() -> None:
    from vectordb.index_manifest import IndexVersionManifest

    catalog, old, current = _policy_change_catalog()
    manifest = IndexVersionManifest(
        schema_version=1,
        active_collection="rag_docs_acme_v2",
        previous_collection="rag_docs_acme_v1",
        generation=2,
        updated_at="2026-10-01T00:00:00+00:00",
    )

    binding = bind_projection_manifest(
        tenant_id=TENANT_ID,
        manifest=manifest,
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )

    assert binding.active_collection == manifest.active_collection
    assert binding.manifest_generation == manifest.generation
    assert binding.source_versions == (
        (str(old.id), old.content_digest),
        (str(current.id), current.content_digest),
    )
    assert len(binding.digest) == 64
    verify_projection_manifest(
        tenant_id=TENANT_ID,
        binding=binding,
        manifest=manifest,
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "generation",
        "collection",
        "source",
        "embedding-model",
        "embedding-dimension",
        "index-config",
    ],
)
def test_projection_binding_rejects_stale_or_incomplete_identity(mutation: str) -> None:
    from vectordb.index_manifest import IndexVersionManifest

    catalog, old, current = _policy_change_catalog()
    manifest = IndexVersionManifest(
        schema_version=1,
        active_collection="rag_docs_acme_v2",
        previous_collection="rag_docs_acme_v1",
        generation=2,
        updated_at="2026-10-01T00:00:00+00:00",
    )
    binding = bind_projection_manifest(
        tenant_id=TENANT_ID,
        manifest=manifest,
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )
    checked_manifest = manifest
    checked_versions = catalog.versions
    checked_embedding_model = "bge-m3"
    checked_embedding_dimension = 1024
    checked_index_config_digest = "c" * 64
    if mutation == "generation":
        checked_manifest = IndexVersionManifest(
            schema_version=1,
            active_collection=manifest.active_collection,
            previous_collection=manifest.previous_collection,
            generation=3,
            updated_at=manifest.updated_at,
        )
    elif mutation == "collection":
        checked_manifest = IndexVersionManifest(
            schema_version=1,
            active_collection="rag_docs_acme_v3",
            previous_collection=manifest.active_collection,
            generation=manifest.generation,
            updated_at=manifest.updated_at,
        )
    elif mutation == "source":
        checked_versions = (old,)
    elif mutation == "embedding-model":
        checked_embedding_model = "bge-m3-updated"
    elif mutation == "embedding-dimension":
        checked_embedding_dimension = 768
    else:
        checked_index_config_digest = "d" * 64

    with pytest.raises(ProjectionBindingMismatch):
        verify_projection_manifest(
            tenant_id=TENANT_ID,
            binding=binding,
            manifest=checked_manifest,
            versions=checked_versions,
            embedding_model=checked_embedding_model,
            embedding_dimension=checked_embedding_dimension,
            index_config_digest=checked_index_config_digest,
        )


@contextmanager
def _held_tenant_lock(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: str,
) -> Iterator[object]:
    from vectordb import tenant_lock

    class _Connection:
        def close(self) -> None:
            return None

    monkeypatch.setattr(tenant_lock, "_open_lock_connection", _Connection)
    monkeypatch.setattr(tenant_lock, "_wait_timeout_sec", lambda: 0.0)
    monkeypatch.setattr(tenant_lock, "_acquire", lambda *args: None)
    monkeypatch.setattr(tenant_lock, "_release", lambda *args: None)

    with tenant_lock.tenant_index_lock(tenant_id) as lock_token:
        yield lock_token


def test_projection_rebuild_and_rollback_preserve_known_point_in_time_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vectordb.index_manifest import (
        publish_active_collection,
        rollback_active_collection,
    )

    catalog, old, current = _policy_change_catalog()
    tenant_key = str(TENANT_ID)
    chroma_directory = tmp_path / "vectordb" / "chroma"
    before_query = _query(
        valid_at=POLICY_CHANGE.replace(day=14),
        system_at=SYSTEM_CORRECTION,
    )
    after_query = _query(valid_at=POLICY_CHANGE, system_at=SYSTEM_CORRECTION)
    expected = (catalog.select(before_query).versions, catalog.select(after_query).versions)

    with _held_tenant_lock(monkeypatch, tenant_key) as lock_token:
        first = publish_active_collection(
            tenant_key,
            "rag_docs_policy_v1",
            lock_token=lock_token,
            chroma_directory=chroma_directory,
        )
        first_binding = bind_projection_manifest(
            tenant_id=TENANT_ID,
            manifest=first,
            versions=catalog.versions,
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )
        rebuilt = publish_active_collection(
            tenant_key,
            "rag_docs_policy_v2",
            lock_token=lock_token,
            chroma_directory=chroma_directory,
        )
        rebuilt_binding = bind_projection_manifest(
            tenant_id=TENANT_ID,
            manifest=rebuilt,
            versions=catalog.versions,
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="d" * 64,
        )
        rolled_back = rollback_active_collection(
            tenant_key,
            lock_token=lock_token,
            chroma_directory=chroma_directory,
        )
        rollback_binding = bind_projection_manifest(
            tenant_id=TENANT_ID,
            manifest=rolled_back,
            versions=catalog.versions,
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )

    assert first_binding.active_collection == "rag_docs_policy_v1"
    assert rebuilt_binding.active_collection == "rag_docs_policy_v2"
    assert rollback_binding.active_collection == "rag_docs_policy_v1"
    assert rollback_binding.source_versions == first_binding.source_versions
    assert (catalog.select(before_query).versions, catalog.select(after_query).versions) == expected
    verify_projection_manifest(
        tenant_id=TENANT_ID,
        binding=rebuilt_binding,
        manifest=rebuilt,
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="d" * 64,
    )
    verify_projection_manifest(
        tenant_id=TENANT_ID,
        binding=rollback_binding,
        manifest=rolled_back,
        versions=catalog.versions,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )


def test_projection_binding_rejects_cross_tenant_versions() -> None:
    from vectordb.index_manifest import IndexVersionManifest

    foreign = _version(
        version_id=V1_ID,
        tenant_id=OTHER_TENANT_ID,
        object_id=SECONDARY_OBJECT_ID,
        source_revision="foreign-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )
    manifest = IndexVersionManifest(
        schema_version=1,
        active_collection="rag_docs_acme_v1",
        previous_collection=None,
        generation=1,
        updated_at="2026-10-01T00:00:00+00:00",
    )

    with pytest.raises(ProjectionBindingMismatch, match="tenant"):
        bind_projection_manifest(
            tenant_id=TENANT_ID,
            manifest=manifest,
            versions=(foreign,),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )


def test_projection_verification_rejects_foreign_tenant_context() -> None:
    from vectordb.index_manifest import IndexVersionManifest

    foreign = _version(
        version_id=V1_ID,
        tenant_id=OTHER_TENANT_ID,
        object_id=SECONDARY_OBJECT_ID,
        source_revision="foreign-r1",
        digest="a" * 64,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_to=None,
    )
    manifest = IndexVersionManifest(
        schema_version=1,
        active_collection="rag_docs_acme_v1",
        previous_collection=None,
        generation=1,
        updated_at="2026-10-01T00:00:00+00:00",
    )
    binding = bind_projection_manifest(
        tenant_id=OTHER_TENANT_ID,
        manifest=manifest,
        versions=(foreign,),
        embedding_model="bge-m3",
        embedding_dimension=1024,
        index_config_digest="c" * 64,
    )

    with pytest.raises(ProjectionBindingMismatch, match="tenant"):
        verify_projection_manifest(
            tenant_id=TENANT_ID,
            binding=binding,
            manifest=manifest,
            versions=(foreign,),
            embedding_model="bge-m3",
            embedding_dimension=1024,
            index_config_digest="c" * 64,
        )
