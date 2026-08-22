from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from knowledge.domain import KnowledgeVersion

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


class ProjectionBindingMismatch(ValueError):
    """The active Chroma manifest and temporal source set are not exactly bound."""


class IndexManifestLike(Protocol):
    active_collection: str
    generation: int


def _require_text(value: str, label: str, *, max_length: int = 256) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProjectionBindingMismatch(f"{label} must be a non-empty safe value")
    if len(value) > max_length or any(ord(character) < 32 for character in value):
        raise ProjectionBindingMismatch(f"{label} must be a bounded safe value")


def _manifest_identity(manifest: IndexManifestLike) -> tuple[str, int]:
    collection = manifest.active_collection
    generation = manifest.generation
    if (
        not isinstance(collection, str)
        or not 1 <= len(collection) <= 63
        or _COLLECTION_PATTERN.fullmatch(collection) is None
    ):
        raise ProjectionBindingMismatch("active collection is invalid")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise ProjectionBindingMismatch("manifest generation must be a positive integer")
    return collection, generation


def _validate_projection_context(
    *,
    tenant_id: UUID,
    embedding_model: str,
    embedding_dimension: int,
    index_config_digest: str,
) -> None:
    if not isinstance(tenant_id, UUID) or tenant_id.int == 0:
        raise ProjectionBindingMismatch("projection tenant must be a non-nil UUID")
    _require_text(embedding_model, "embedding model", max_length=128)
    if (
        isinstance(embedding_dimension, bool)
        or not isinstance(embedding_dimension, int)
        or embedding_dimension < 1
    ):
        raise ProjectionBindingMismatch("embedding dimension must be a positive integer")
    if (
        not isinstance(index_config_digest, str)
        or _DIGEST_PATTERN.fullmatch(index_config_digest) is None
    ):
        raise ProjectionBindingMismatch("index config digest must be a lowercase SHA-256 digest")


def _source_versions(
    tenant_id: UUID,
    versions: tuple[KnowledgeVersion, ...],
) -> tuple[tuple[str, str], ...]:
    if not versions:
        raise ProjectionBindingMismatch("projection requires source knowledge versions")
    identities: dict[UUID, str] = {}
    for version in versions:
        if version.tenant_id != tenant_id:
            raise ProjectionBindingMismatch("projection source version belongs to another tenant")
        previous = identities.setdefault(version.id, version.content_digest)
        if previous != version.content_digest:
            raise ProjectionBindingMismatch("knowledge version identity has conflicting digests")
    if len(identities) != len(versions):
        raise ProjectionBindingMismatch("projection source versions must be unique")
    return tuple(sorted((str(version_id), digest) for version_id, digest in identities.items()))


def _binding_payload(
    *,
    tenant_id: UUID,
    active_collection: str,
    manifest_generation: int,
    source_versions: tuple[tuple[str, str], ...],
    embedding_model: str,
    embedding_dimension: int,
    index_config_digest: str,
) -> dict[str, object]:
    return {
        "tenant_id": str(tenant_id),
        "active_collection": active_collection,
        "manifest_generation": manifest_generation,
        "source_versions": [list(item) for item in source_versions],
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "index_config_digest": index_config_digest,
    }


def _payload_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class KnowledgeProjectionBinding:
    tenant_id: UUID
    active_collection: str
    manifest_generation: int
    source_versions: tuple[tuple[str, str], ...]
    embedding_model: str
    embedding_dimension: int
    index_config_digest: str
    digest: str

    def as_dict(self) -> dict[str, object]:
        payload = _binding_payload(
            tenant_id=self.tenant_id,
            active_collection=self.active_collection,
            manifest_generation=self.manifest_generation,
            source_versions=self.source_versions,
            embedding_model=self.embedding_model,
            embedding_dimension=self.embedding_dimension,
            index_config_digest=self.index_config_digest,
        )
        return {**payload, "digest": self.digest}


def bind_projection_manifest(
    *,
    tenant_id: UUID,
    manifest: IndexManifestLike,
    versions: tuple[KnowledgeVersion, ...],
    embedding_model: str,
    embedding_dimension: int,
    index_config_digest: str,
) -> KnowledgeProjectionBinding:
    _validate_projection_context(
        tenant_id=tenant_id,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        index_config_digest=index_config_digest,
    )
    collection, generation = _manifest_identity(manifest)
    sources = _source_versions(tenant_id, versions)
    payload = _binding_payload(
        tenant_id=tenant_id,
        active_collection=collection,
        manifest_generation=generation,
        source_versions=sources,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        index_config_digest=index_config_digest,
    )
    return KnowledgeProjectionBinding(
        tenant_id=tenant_id,
        active_collection=collection,
        manifest_generation=generation,
        source_versions=sources,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        index_config_digest=index_config_digest,
        digest=_payload_digest(payload),
    )


def verify_projection_manifest(
    *,
    tenant_id: UUID,
    binding: KnowledgeProjectionBinding,
    manifest: IndexManifestLike,
    versions: tuple[KnowledgeVersion, ...],
    embedding_model: str,
    embedding_dimension: int,
    index_config_digest: str,
) -> None:
    _validate_projection_context(
        tenant_id=tenant_id,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        index_config_digest=index_config_digest,
    )
    if binding.tenant_id != tenant_id:
        raise ProjectionBindingMismatch("projection binding belongs to another tenant")
    collection, generation = _manifest_identity(manifest)
    sources = _source_versions(tenant_id, versions)
    if (
        binding.active_collection != collection
        or binding.manifest_generation != generation
        or binding.source_versions != sources
        or binding.embedding_model != embedding_model
        or binding.embedding_dimension != embedding_dimension
        or binding.index_config_digest != index_config_digest
    ):
        raise ProjectionBindingMismatch(
            "projection binding does not match the active manifest, source versions, "
            "and embedding/index configuration"
        )
    payload = _binding_payload(
        tenant_id=binding.tenant_id,
        active_collection=binding.active_collection,
        manifest_generation=binding.manifest_generation,
        source_versions=binding.source_versions,
        embedding_model=binding.embedding_model,
        embedding_dimension=binding.embedding_dimension,
        index_config_digest=binding.index_config_digest,
    )
    if binding.digest != _payload_digest(payload):
        raise ProjectionBindingMismatch("projection binding digest is invalid")


__all__ = [
    "IndexManifestLike",
    "KnowledgeProjectionBinding",
    "ProjectionBindingMismatch",
    "bind_projection_manifest",
    "verify_projection_manifest",
]
