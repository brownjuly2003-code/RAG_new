"""Resume validated entity extraction without repeating completed provider calls."""

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ingestion.entity_normalization import normalize_entities
from ingestion.structure_graph import _chunk_order, _document_identity, _stable_id

EXTRACT_PROMPT = (
    "Извлеки из фрагмента корпоративного регламента ключевые СУЩНОСТИ:\n"
    "процессы, роли, документы, системы, типы грузов/операций, термины.\n"
    "Не извлекай общие слова (сотрудник, компания, документ без уточнения).\n"
    "Нормализуй: именительный падеж, единственное число, нижний регистр.\n"
    "Ответ — ТОЛЬКО JSON-массив строк, без пояснений. 3-12 сущностей.\n"
    "\nФрагмент:\n{chunk}\n\nJSON:"
)
EXTRACT_SCHEMA = {
    "type": "array",
    "items": {"type": "string", "minLength": 1, "maxLength": 128},
    "maxItems": 12,
}
_NORMALIZER_VERSION = "gr2-entity-v1"
_PROMPT_SHA256 = hashlib.sha256(EXTRACT_PROMPT.encode("utf-8")).hexdigest()
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ExtractionCache:
    manifest: dict[str, Any]
    entities: dict[str, list[str]]
    rejected: dict[str, str]
    total: int


def _entities(raw: str) -> list[str]:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\[.*\])\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        values = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid entities JSON") from exc
    if (
        not isinstance(values, list)
        or len(values) > 12
        or any(
            not isinstance(value, str) or not value.strip() or len(value.strip()) > 128
            for value in values
        )
    ):
        raise ValueError("Invalid entities schema")
    return normalize_entities(values)


def _extraction_inputs(chunks: Sequence[Any], tenant_id: str) -> dict[str, tuple[str, str]]:
    inputs: dict[str, tuple[str, str]] = {}
    for position, chunk in enumerate(chunks):
        metadata = chunk.metadata or {}
        source, _ = _document_identity(metadata, position)
        order = _chunk_order(metadata, position)
        chunk_id = _stable_id(tenant_id, "chunk", f"{source}\x1f{order}")
        content = chunk.page_content
        if chunk_id in inputs:
            raise ValueError("Duplicate chunk identity in extraction input")
        inputs[chunk_id] = (hashlib.sha256(content.encode("utf-8")).hexdigest(), content)
    return inputs


def _chunks_sha256(inputs: Mapping[str, tuple[str, str]]) -> str:
    return hashlib.sha256(
        json.dumps(
            sorted((key, value[0]) for key, value in inputs.items()),
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _extraction_manifest(
    *,
    tenant_id: str,
    corpus_sha256: str,
    model: str,
    inputs: Mapping[str, tuple[str, str]],
    provider: str,
    model_digest: str | None,
    generation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    stored_generation: dict[str, Any] = (
        {"temperature": 0} if generation is None else dict(generation)
    )
    return {
        "schema_version": 2,
        "tenant_id": tenant_id,
        "corpus_sha256": corpus_sha256,
        "model": model,
        "model_digest": model_digest,
        "temperature": 0,
        "prompt_sha256": _PROMPT_SHA256,
        "normalizer_version": _NORMALIZER_VERSION,
        "chunk_count": len(inputs),
        "chunks_sha256": _chunks_sha256(inputs),
        "provider": provider,
        "generation": stored_generation,
    }


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load_entity_rows(
    path: Path,
    inputs: Mapping[str, tuple[str, str]],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
                chunk_id = row["chunk_id"]
                if chunk_id in result or row["content_sha256"] != inputs[chunk_id][0]:
                    raise ValueError("Invalid cache chunk digest or duplicate")
                values = _entities(json.dumps(row["entities"]))
                if values != row["entities"] or not line.endswith("\n"):
                    raise ValueError("Invalid cache normalization or incomplete tail")
                result[chunk_id] = values
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("Invalid extraction cache row") from exc
    return result


def _load_rejected_rows(
    path: Path,
    inputs: Mapping[str, tuple[str, str]],
    cached: Mapping[str, object],
) -> dict[str, str]:
    rejected: dict[str, str] = {}
    if not path.exists():
        return rejected
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
                chunk_id = row["chunk_id"]
                if (
                    chunk_id in cached
                    or chunk_id in rejected
                    or row["content_sha256"] != inputs[chunk_id][0]
                    or not line.endswith("\n")
                ):
                    raise ValueError("Invalid cache chunk digest or duplicate")
                reason, answer_sha256, prefix = (
                    row["reason"],
                    row["answer_sha256"],
                    row["answer_prefix"],
                )
                if (
                    not isinstance(reason, str)
                    or not isinstance(answer_sha256, str)
                    or _DIGEST_RE.fullmatch(answer_sha256) is None
                    or not isinstance(prefix, str)
                    or len(prefix) > 200
                ):
                    raise ValueError("Invalid rejection row")
                rejected[chunk_id] = reason
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("Invalid extraction cache row") from exc
    return rejected


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid extraction cache manifest") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Invalid extraction cache manifest")
    return manifest


def _manifest_mismatch(existing: Mapping[str, Any], expected: Mapping[str, Any]) -> ValueError:
    if existing.get("schema_version") != expected["schema_version"]:
        return ValueError(
            "Extraction cache provenance mismatch: schema_version "
            f"{existing.get('schema_version')} != {expected['schema_version']}"
        )
    return ValueError("Extraction cache provenance mismatch")


def load_extraction_cache(
    cache_dir: Path,
    chunks: Sequence[Any],
    *,
    tenant_id: str,
    require_complete: bool = True,
) -> ExtractionCache:
    inputs = _extraction_inputs(chunks, tenant_id)
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Extraction cache has no provenance manifest")
    manifest = _read_manifest(manifest_path)
    expected = {
        "tenant_id": tenant_id,
        "chunk_count": len(inputs),
        "chunks_sha256": _chunks_sha256(inputs),
        "prompt_sha256": _PROMPT_SHA256,
        "normalizer_version": _NORMALIZER_VERSION,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError("Extraction cache provenance mismatch")
    entities = _load_entity_rows(cache_dir / "entities.jsonl", inputs)
    rejected = _load_rejected_rows(cache_dir / "rejected.jsonl", inputs, entities)
    total = len(inputs)
    if require_complete and len(entities) + len(rejected) < total:
        raise ValueError(
            f"Incomplete extraction cache: cached={len(entities)} "
            f"rejected={len(rejected)} total={total}",
        )
    return ExtractionCache(manifest=manifest, entities=entities, rejected=rejected, total=total)


def extract_entities(
    chunks: Sequence[Any],
    *,
    tenant_id: str,
    corpus_sha256: str,
    model: str,
    cache_dir: Path,
    invoke: Callable[[str], str],
    max_calls: int | None = None,
    provider: str = "mistral",
    model_digest: str | None = None,
    generation: Mapping[str, Any] | None = None,
    on_invalid: Literal["raise", "record"] = "raise",
) -> dict[str, list[str]]:
    if _DIGEST_RE.fullmatch(corpus_sha256) is None:
        raise ValueError("Invalid corpus provenance digest")
    if model_digest is not None and _DIGEST_RE.fullmatch(model_digest) is None:
        raise ValueError("Invalid model weights digest")
    if max_calls is not None and max_calls < 0:
        raise ValueError("max_calls must be nonnegative")
    if on_invalid not in ("raise", "record"):
        raise ValueError("on_invalid must be 'raise' or 'record'")
    inputs = _extraction_inputs(chunks, tenant_id)
    manifest = _extraction_manifest(
        tenant_id=tenant_id,
        corpus_sha256=corpus_sha256,
        model=model,
        inputs=inputs,
        provider=provider,
        model_digest=model_digest,
        generation=generation,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "manifest.json"
    rows_path = cache_dir / "entities.jsonl"
    rejected_path = cache_dir / "rejected.jsonl"
    if manifest_path.exists():
        existing = _read_manifest(manifest_path)
        if existing != manifest:
            raise _manifest_mismatch(existing, manifest)
    else:
        if rows_path.exists() or rejected_path.exists():
            raise ValueError("Extraction cache has no provenance manifest")
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    result = _load_entity_rows(rows_path, inputs)
    rejected = _load_rejected_rows(rejected_path, inputs, result)
    calls = 0
    for chunk_id, (digest, content) in inputs.items():
        if chunk_id in result or chunk_id in rejected:
            continue
        if max_calls is not None and calls >= max_calls:
            break
        answer = invoke(EXTRACT_PROMPT.format(chunk=content))
        try:
            values = _entities(answer)
        except ValueError as exc:
            if on_invalid == "raise":
                raise
            encoded = answer.encode("utf-8", "surrogatepass")
            _append_jsonl(
                rejected_path,
                {
                    "chunk_id": chunk_id,
                    "content_sha256": digest,
                    "reason": str(exc),
                    "answer_sha256": hashlib.sha256(encoded).hexdigest(),
                    "answer_prefix": encoded.decode("utf-8", "backslashreplace")[:200],
                },
            )
            calls += 1
            continue
        _append_jsonl(
            rows_path,
            {
                "chunk_id": chunk_id,
                "content_sha256": digest,
                "entities": values,
            },
        )
        result[chunk_id] = values
        calls += 1
    return result
