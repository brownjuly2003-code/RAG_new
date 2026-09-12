"""Resume validated entity extraction without repeating completed provider calls."""

import hashlib
import json
import os
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

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


def _entities(raw: str) -> list[str]:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\[.*\])\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        values = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid entities JSON") from exc
    if not isinstance(values, list) or len(values) > 12 or any(
        not isinstance(value, str) or not value.strip() or len(value.strip()) > 128
        for value in values
    ):
        raise ValueError("Invalid entities schema")
    return normalize_entities(values)


def extract_entities(
    chunks: Sequence[Any], *, tenant_id: str, corpus_sha256: str, model: str,
    cache_dir: Path, invoke: Callable[[str], str], max_calls: int | None = None,
) -> dict[str, list[str]]:
    if re.fullmatch(r"[0-9a-f]{64}", corpus_sha256) is None:
        raise ValueError("Invalid corpus provenance digest")
    if max_calls is not None and max_calls < 0:
        raise ValueError("max_calls must be nonnegative")
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
    manifest = {
        "schema_version": 1, "tenant_id": tenant_id, "corpus_sha256": corpus_sha256,
        "model": model, "model_digest": None, "temperature": 0,
        "prompt_sha256": hashlib.sha256(EXTRACT_PROMPT.encode("utf-8")).hexdigest(),
        "normalizer_version": "gr2-entity-v1", "chunk_count": len(inputs),
        "chunks_sha256": hashlib.sha256(json.dumps(
            sorted((key, value[0]) for key, value in inputs.items()),
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "manifest.json"
    rows_path = cache_dir / "entities.jsonl"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Extraction cache provenance mismatch")
    else:
        if rows_path.exists():
            raise ValueError("Extraction cache has no provenance manifest")
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    result: dict[str, list[str]] = {}
    if rows_path.exists():
        with rows_path.open(encoding="utf-8") as stream:
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
    calls = 0
    for chunk_id, (digest, content) in inputs.items():
        if chunk_id in result:
            continue
        if max_calls is not None and calls >= max_calls:
            break
        values = _entities(invoke(EXTRACT_PROMPT.format(chunk=content)))
        with rows_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"chunk_id": chunk_id, "content_sha256": digest,
                                     "entities": values}, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        result[chunk_id] = values
        calls += 1
    return result
