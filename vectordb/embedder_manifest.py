"""Embedding identity persisted with each Chroma collection."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MANIFEST_METADATA_KEY = "embedder_manifest"
logger = logging.getLogger(__name__)
_warned_unstamped: set[tuple[str, str]] = set()


@dataclass(frozen=True)
class EmbedderManifest:
    backend: str
    model_id: str
    revision: str | None
    revision_source: str
    dimension: int | None
    query_prompt: str
    document_prompt: str
    normalize: bool
    schema_version: int = 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()


class EmbedderManifestMismatch(RuntimeError):
    def __init__(
        self, stored: dict[str, Any], configured: dict[str, Any], mismatched_fields: list[str]
    ) -> None:
        self.stored = stored
        self.configured = configured
        self.mismatched_fields = mismatched_fields
        super().__init__("embedder_manifest_mismatch: " + ", ".join(mismatched_fields))

    def trace_record(self) -> dict[str, Any]:
        return {
            "status": "refused",
            "reason": "embedder_manifest_mismatch",
            "stored": self.stored,
            "configured": self.configured,
            "mismatched_fields": self.mismatched_fields,
            "evidence_status": "NOT_EVIDENCE",
        }


def stamp_collection(store: Any, embeddings: Any, *, tenant_id: str = "default") -> None:
    """Check before a write, stamping only an empty, unstamped collection."""
    record = check_collection_manifest(store, embeddings, tenant_id=tenant_id)
    manifest = getattr(embeddings, "manifest", None)
    if not isinstance(manifest, EmbedderManifest) or record["status"] != "unstamped":
        return
    collection = store._collection
    if collection.count() != 0:
        return
    metadata = dict(collection.metadata or {})
    metadata[MANIFEST_METADATA_KEY] = manifest.canonical_json
    collection.modify(metadata=metadata)


def open_chroma_for_write(
    chroma_cls: Any, embeddings: Any, *, tenant_id: str = "default", **kwargs: Any
) -> Any:
    """Create with metadata or check an existing collection before adding vectors."""
    manifest = getattr(embeddings, "manifest", None)
    if not isinstance(manifest, EmbedderManifest):
        return None
    store = chroma_cls(
        embedding_function=embeddings,
        collection_metadata={MANIFEST_METADATA_KEY: manifest.canonical_json},
        **kwargs,
    )
    stamp_collection(store, embeddings, tenant_id=tenant_id)
    return store


def check_collection_manifest(
    store: Any, embeddings: Any, *, backend: str = "chroma", tenant_id: str = "default"
) -> dict[str, Any]:
    """Read metadata only; never encode or retroactively stamp a legacy index."""
    manifest = getattr(embeddings, "manifest", None)
    configured = manifest.as_dict() if isinstance(manifest, EmbedderManifest) else None
    record: dict[str, Any] = {
        "status": "unidentified",
        "stored": None,
        "configured": configured,
        "mismatched_fields": [],
        "evidence_status": "NOT_EVIDENCE",
    }
    if backend != "chroma":
        record["status"] = "unsupported_backend"
        return record
    collection = getattr(store, "_collection", None)
    metadata = getattr(collection, "metadata", None) or {}
    encoded = metadata.get(MANIFEST_METADATA_KEY)
    if encoded is not None:
        try:
            stored = json.loads(encoded)
        except (ValueError, TypeError):
            stored = {}
        # Only manifest fields travel into the trace, never arbitrary metadata.
        record["stored"] = (
            {key: stored[key] for key in EmbedderManifest.__dataclass_fields__ if key in stored}
            if isinstance(stored, dict)
            else {}
        )
    if configured is None:
        return record
    if encoded is None:
        record["status"] = "unstamped"
        identity = (tenant_id, str(getattr(collection, "id", id(collection))))
        if identity not in _warned_unstamped:
            _warned_unstamped.add(identity)
            logger.warning(
                "Tenant %s loaded an unstamped index: NOT_EVIDENCE; rebuild it", tenant_id
            )
        return record
    stored = record["stored"]
    mismatched = [
        key for key, value in configured.items() if key not in stored or stored[key] != value
    ]
    if mismatched:
        raise EmbedderManifestMismatch(stored, configured, mismatched)
    if not all(
        identity.get("revision_source") == "hf_snapshot"
        and isinstance(identity.get("revision"), str)
        and re.fullmatch(r"[0-9a-fA-F]{40}", identity["revision"])
        for identity in (stored, configured)
    ):
        record["status"] = "unverified"
        record["reason"] = (
            "remote_unversioned" if configured["backend"] == "remote" else "revision_unresolved"
        )
        return record
    record["status"] = "match"
    record["evidence_status"] = "eligible"
    return record


def loaded_hf_revision(model: Any, model_id: str) -> str | None:
    """Resolve a loaded model's snapshot, without looking up a moving HF ref."""
    modules = getattr(model, "_modules", {})
    for module in modules.values():
        auto_model = getattr(module, "auto_model", None)
        config = getattr(auto_model, "config", None)
        tokenizer = getattr(module, "tokenizer", None)
        for owner in (module, auto_model, config, tokenizer):
            for attribute in ("name_or_path", "_name_or_path"):
                path = str(getattr(owner, attribute, "") or "").replace("\\", "/")
                match = re.search(r"/snapshots/([0-9a-f]{40})(?:/|$)", path)
                if match and Path(path).exists():
                    return match.group(1)
        commit = getattr(config, "_commit_hash", None)
        if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit):
            from huggingface_hub import try_to_load_from_cache

            cached = try_to_load_from_cache(model_id, "config.json", revision=commit)
            if isinstance(cached, str):
                match = re.search(r"/snapshots/([0-9a-f]{40})/", cached.replace("\\", "/"))
                if match and Path(cached).exists():
                    return match.group(1)
    return None


def local_manifest(model: Any, model_id: str, dimension: int | None) -> EmbedderManifest:
    name = getattr(model, "default_prompt_name", None)
    prompt = (getattr(model, "prompts", {}) or {}).get(name, "") if name is not None else ""
    revision = loaded_hf_revision(model, model_id)
    return EmbedderManifest(
        backend="local",
        model_id=model_id,
        revision=revision,
        revision_source="hf_snapshot" if revision else "unresolved",
        dimension=dimension,
        query_prompt=prompt,
        document_prompt=prompt,
        normalize=True,
    )
