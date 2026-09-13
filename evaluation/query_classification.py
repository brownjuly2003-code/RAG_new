"""Cache production ``classify_complexity`` results for GR-2 measurement."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.graph import (
    _CLASSIFY_COMPLEXITY_SCHEMA,
    _SGR_QUESTION_CLASSES,
    _SGR_REASON_CODES,
    make_classify_complexity_node,
)
from agent.prompts import _resolve_prompt
from agent.state import create_initial_state
from llm.providers import LLMResponse
from llm.providers.pinned_ollama import PinnedOllamaChat

SCHEMA_VERSION = 1
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_ROW_FIELDS = (
    "case_id",
    "query_sha256",
    "complexity",
    "question_class",
    "entities",
    "needs_multi_hop",
    "reason_code",
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _query_sha256(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _prompt_template_sha256() -> str:
    return hashlib.sha256(_resolve_prompt("classify_complexity").encode("utf-8")).hexdigest()


def _schema_sha256() -> str:
    return _canonical_sha256(_CLASSIFY_COMPLEXITY_SCHEMA)


def _current_code_provenance() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_template_sha256": _prompt_template_sha256(),
        "schema_sha256": _schema_sha256(),
    }


def _classifier_options(classifier: Any) -> dict[str, Any]:
    options_raw = getattr(classifier, "options", None)
    if not isinstance(options_raw, Mapping):
        raise ValueError("classifier reports no options")
    return dict(options_raw)


def _options_from_chat(chat: PinnedOllamaChat) -> dict[str, Any]:
    record = chat.generation_record(_CLASSIFY_COMPLEXITY_SCHEMA)
    return {key: value for key, value in record.items() if key != "format_sha256"}


def _require_cached_classification(row: Mapping[str, Any]) -> None:
    case_id = row["case_id"]
    question_class = row["question_class"]
    reason_code = row["reason_code"]
    if question_class not in _SGR_QUESTION_CLASSES:
        raise ValueError(f"invalid question_class {question_class!r} for case {case_id}")
    if reason_code not in _SGR_REASON_CODES:
        raise ValueError(f"invalid reason_code {reason_code!r} for case {case_id}")


def _case_index(cases: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for case in cases:
        case_id = case.get("case_id")
        query = case.get("query")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case is missing case_id")
        if not isinstance(query, str):
            raise ValueError(f"case {case_id} is missing query")
        if case_id in index:
            raise ValueError(f"duplicate case_id {case_id}")
        index[case_id] = _query_sha256(query)
    return index


def _classifier_manifest(
    *,
    dataset_sha256: str,
    case_count: int,
    classifier: Any,
) -> dict[str, Any]:
    model_digest = getattr(classifier, "model_digest", None)
    if model_digest is not None and (
        not isinstance(model_digest, str) or _DIGEST_RE.fullmatch(model_digest) is None
    ):
        raise ValueError("Invalid model weights digest")
    return {
        **_current_code_provenance(),
        "dataset_sha256": dataset_sha256,
        "case_count": case_count,
        "provider": str(getattr(classifier, "provider_id", "") or ""),
        "model": str(getattr(classifier, "model_name", "") or ""),
        "model_digest": model_digest,
        "options": _classifier_options(classifier),
    }


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid classification cache manifest") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Invalid classification cache manifest")
    return manifest


def _manifest_mismatch(existing: Mapping[str, Any], expected: Mapping[str, Any]) -> ValueError:
    for key, value in expected.items():
        if existing.get(key) != value:
            return ValueError(
                f"Classification cache provenance mismatch: {key} "
                f"{existing.get(key)!r} != {value!r}"
            )
    return ValueError("Classification cache provenance mismatch")


def _parse_row(row: Mapping[str, Any], index: Mapping[str, str]) -> dict[str, Any]:
    missing = [field for field in _ROW_FIELDS if field not in row]
    if missing:
        raise ValueError("malformed classification cache row")
    case_id = row["case_id"]
    query_sha256 = row["query_sha256"]
    entities = row["entities"]
    needs_multi_hop = row["needs_multi_hop"]
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("malformed classification cache row")
    if not isinstance(query_sha256, str) or _DIGEST_RE.fullmatch(query_sha256) is None:
        raise ValueError("malformed classification cache row")
    if case_id not in index:
        raise ValueError(f"unknown case_id {case_id}")
    if query_sha256 != index[case_id]:
        raise ValueError(
            f"query_sha256 mismatch for case {case_id}: cache {query_sha256} != {index[case_id]}"
        )
    if not isinstance(entities, list) or any(not isinstance(item, str) for item in entities):
        raise ValueError("malformed classification cache row")
    if not isinstance(needs_multi_hop, bool):
        raise ValueError("malformed classification cache row")
    complexity = row["complexity"]
    question_class = row["question_class"]
    reason_code = row["reason_code"]
    if not isinstance(complexity, str) or not isinstance(question_class, str):
        raise ValueError("malformed classification cache row")
    if not isinstance(reason_code, str):
        raise ValueError("malformed classification cache row")
    parsed = {
        "case_id": case_id,
        "query_sha256": query_sha256,
        "complexity": complexity,
        "question_class": question_class,
        "entities": list(entities),
        "needs_multi_hop": needs_multi_hop,
        "reason_code": reason_code,
    }
    _require_cached_classification(parsed)
    return parsed


def _load_rows(path: Path, index: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise ValueError("incomplete classification cache tail")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("malformed classification cache row") from exc
            if not isinstance(row, dict):
                raise ValueError("malformed classification cache row")
            parsed = _parse_row(row, index)
            case_id = parsed["case_id"]
            if case_id in result:
                raise ValueError(f"duplicate case_id {case_id}")
            result[case_id] = parsed
    return result


def _row_from_state(case_id: str, query_sha256: str, state: Mapping[str, Any]) -> dict[str, Any]:
    entities_raw = state.get("entities") or []
    entities = list(entities_raw) if isinstance(entities_raw, list) else []
    return {
        "case_id": case_id,
        "query_sha256": query_sha256,
        "complexity": str(state.get("complexity") or ""),
        "question_class": str(state.get("question_class") or ""),
        "entities": entities,
        "needs_multi_hop": bool(state.get("needs_multi_hop")),
        "reason_code": str(state.get("reason_code") or ""),
    }


@contextmanager
def _isolate_classification_runtime() -> Iterator[None]:
    import agent.graph as graph
    import config.settings as settings_mod

    previous_settings = settings_mod.get_settings
    previous_log_step = graph.log_step
    previous_trace_llm_call = graph.trace_llm_call

    def _routing_on() -> Any:
        return SimpleNamespace(model_routing_enabled=True)

    def _drop_step(*args: object, **kwargs: object) -> None:
        _ = args, kwargs

    def _drop_llm(**kwargs: object) -> None:
        _ = kwargs

    settings_mod.get_settings = _routing_on
    setattr(graph, "log_step", _drop_step)
    setattr(graph, "trace_llm_call", _drop_llm)
    try:
        yield
    finally:
        settings_mod.get_settings = previous_settings
        setattr(graph, "log_step", previous_log_step)
        setattr(graph, "trace_llm_call", previous_trace_llm_call)


def _raise_classification_failure(classifier: Any, state: Mapping[str, Any], before: int) -> None:
    failures = getattr(classifier, "failures", None)
    if isinstance(failures, list) and len(failures) > before:
        raise failures[-1]
    message = str(state.get("error_message") or "classify_complexity failed")
    raise RuntimeError(message)


class PinnedOllamaClassifier:
    """Adapter that production ``classify_complexity`` accepts as its classifier LLM."""

    provider_id = "ollama"
    supports_structured_output = True

    def __init__(
        self,
        chat: PinnedOllamaChat,
        *,
        model_name: str,
        model_digest: str,
    ) -> None:
        if _DIGEST_RE.fullmatch(model_digest) is None:
            raise ValueError("Invalid model weights digest")
        self._chat = chat
        self.model_name = model_name
        self.model_digest = model_digest
        self.options = _options_from_chat(chat)
        self.failures: list[BaseException] = []
        self.last_response: LLMResponse | None = None

    def generate_with_schema(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        **kwargs: Any,
    ) -> LLMResponse:
        _ = kwargs
        try:
            content = self._chat.chat(messages, format_schema=schema)
            try:
                parsed: object = json.loads(content)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Ollama model {self.model_name!r} returned non-JSON") from exc
            required = schema.get("required")
            required_keys = required if isinstance(required, list) else []
            if not isinstance(parsed, dict) or any(key not in parsed for key in required_keys):
                raise RuntimeError(
                    f"Ollama model {self.model_name!r} returned a classification "
                    "that is not schema-conforming"
                )
            response = LLMResponse(
                text=content,
                provider=self.provider_id,
                model=self.model_name,
                structured_output=parsed,
            )
            self.last_response = response
            return response
        except Exception as exc:
            self.failures.append(exc)
            raise


def classify_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    dataset_sha256: str,
    classifier: Any,
    cache_dir: Path,
    max_calls: int | None = None,
) -> dict[str, dict[str, Any]]:
    if _DIGEST_RE.fullmatch(dataset_sha256) is None:
        raise ValueError("Invalid dataset provenance digest")
    if max_calls is not None and max_calls < 0:
        raise ValueError("max_calls must be nonnegative")
    index = _case_index(cases)
    manifest = _classifier_manifest(
        dataset_sha256=dataset_sha256,
        case_count=len(index),
        classifier=classifier,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "manifest.json"
    rows_path = cache_dir / "classifications.jsonl"
    if manifest_path.exists():
        existing = _read_manifest(manifest_path)
        if existing != manifest:
            raise _manifest_mismatch(existing, manifest)
    else:
        if rows_path.exists():
            raise ValueError("Classification cache has no provenance manifest")
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    cached = _load_rows(rows_path, index)
    node = make_classify_complexity_node(classifier)
    calls = 0
    for case in cases:
        case_id = str(case["case_id"])
        if case_id in cached:
            continue
        if max_calls is not None and calls >= max_calls:
            break
        failures = getattr(classifier, "failures", None)
        before = len(failures) if isinstance(failures, list) else 0
        with _isolate_classification_runtime():
            result = node(
                create_initial_state(
                    question=str(case["query"]),
                    trace_id=f"gr2-classify:{case_id}",
                )
            )
        after = getattr(classifier, "failures", None)
        failed = result.get("error") or (isinstance(after, list) and len(after) > before)
        if failed:
            _raise_classification_failure(classifier, result, before)
        row = _row_from_state(case_id, index[case_id], result)
        _require_cached_classification(row)
        _append_jsonl(rows_path, row)
        cached[case_id] = row
        calls += 1
    return cached


def load_classifications(
    cache_dir: Path,
    *,
    cases: Sequence[Mapping[str, Any]],
    dataset_sha256: str,
) -> dict[str, dict[str, Any]]:
    if _DIGEST_RE.fullmatch(dataset_sha256) is None:
        raise ValueError("Invalid dataset provenance digest")
    index = _case_index(cases)
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Classification cache has no provenance manifest")
    manifest = _read_manifest(manifest_path)
    expected_code = {"dataset_sha256": dataset_sha256, **_current_code_provenance()}
    for key, value in expected_code.items():
        if manifest.get(key) != value:
            raise ValueError(f"{key} mismatch: cache {manifest.get(key)!r} != {value!r}")
    rows = _load_rows(cache_dir / "classifications.jsonl", index)
    for case in cases:
        case_id = str(case["case_id"])
        if case_id not in rows:
            raise ValueError(f"missing classification for case {case_id}")
    return rows
