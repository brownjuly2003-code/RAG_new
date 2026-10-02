"""Recorded-outcome contracts for the staged parity runner's llm cache."""

import json
import sys
from types import SimpleNamespace

import pytest

from scripts import production_parity as parity
from tests.test_production_index import inputs as index_inputs

MANIFEST = {"llm": {"model": parity.MODEL, "digest": parity.DIGEST}}
MESSAGES = [{"role": "user", "content": "grade"}]
SCHEMA = {"type": "object", "properties": {"relevant": {"type": "boolean"}}}


@pytest.fixture
def inputs(tmp_path):
    return index_inputs.__wrapped__(tmp_path)


def _patch_ollama(monkeypatch, generate):
    from llm.providers.ollama import OllamaProvider

    monkeypatch.setattr(OllamaProvider, "generate", generate)
    monkeypatch.setattr(
        "llm.providers.pinned_ollama.resolve_ollama_digest", lambda *a: parity.DIGEST
    )


def _record_invalid_outcome(root, monkeypatch):
    from llm.providers.base import LLMResponse, StructuredOutputValidationError

    calls = []

    def generate(self, messages, **kwargs):
        calls.append(1)
        return LLMResponse("YES", "ollama", parity.MODEL, input_tokens=680, output_tokens=1)

    _patch_ollama(monkeypatch, generate)
    cache = parity.ReplayCache(root, "run")
    llm = parity.make_llm(cache, True, MANIFEST)
    with pytest.raises(StructuredOutputValidationError, match="not valid JSON"):
        llm.generate_with_schema(MESSAGES, SCHEMA)
    assert len(list(root.glob("llm-*.json"))) == 1
    return cache, calls


def test_schema_validation_outcome_is_recorded_and_replayed(tmp_path, monkeypatch):
    from llm.providers.base import StructuredOutputValidationError

    cache, calls = _record_invalid_outcome(tmp_path, monkeypatch)
    assert calls == [1]
    value = json.loads(next(tmp_path.glob("llm-*.json")).read_text())["value"]
    assert value["outcome"] == "structured_output_invalid"
    assert value["raw_response"]["text"] == "YES"
    assert value["error"]["type"] == "StructuredOutputValidationError"
    assert value["error"]["message"] == "structured output is not valid JSON"
    assert cache.failures == []
    cache.require_clean()

    replay_cache = parity.ReplayCache(tmp_path, "run")
    replay = parity.make_llm(replay_cache, False, MANIFEST)
    with pytest.raises(StructuredOutputValidationError) as replayed:
        replay.generate_with_schema(MESSAGES, SCHEMA)
    assert str(replayed.value) == "structured output is not valid JSON"
    assert calls == [1]
    assert replay_cache.failures == []
    replay_cache.require_clean()


def test_valid_structured_reply_round_trips(tmp_path, monkeypatch):
    from llm.providers.base import LLMResponse

    def generate(self, messages, **kwargs):
        return LLMResponse(
            '{"relevant": true}', "ollama", parity.MODEL, input_tokens=680, output_tokens=1
        )

    _patch_ollama(monkeypatch, generate)
    cache = parity.ReplayCache(tmp_path, "run")
    llm = parity.make_llm(cache, True, MANIFEST)
    assert llm.generate_with_schema(MESSAGES, SCHEMA).structured_output == {"relevant": True}
    record = json.loads(next(tmp_path.glob("llm-*.json")).read_text())
    assert record["request"]["method"] == "generate_with_schema"
    assert record["value"]["outcome"] == "response"
    assert cache.failures == []
    replay_cache = parity.ReplayCache(tmp_path, "run")
    replay = parity.make_llm(replay_cache, False, MANIFEST)
    assert replay.generate_with_schema(MESSAGES, SCHEMA).structured_output == {"relevant": True}
    assert replay_cache.failures == []


def test_yes_reply_runs_production_fallback_through_all_stages(inputs, tmp_path, monkeypatch):
    import numpy as np

    from llm.providers.base import LLMResponse
    from scripts.production_index import build_index
    from vectordb import _base_manager

    receipt = build_index(**inputs)
    run = tmp_path / "run"
    run.mkdir()
    cfg = {**parity.CONFIG, "retrieval_top_k": 2, "rerank_top_k": 2}
    manifest = {
        "config": cfg,
        "index_receipt": receipt,
        "index": str(inputs["output"]),
        "checkpoint": str(inputs["checkpoint"]),
        "corpus": str(inputs["archive"]),
        "cases": [{"case_id": "case", "query": "What cargo?"}],
        "llm": {"model": parity.MODEL, "digest": parity.DIGEST},
        "reranker": {"model": "fixture", "revision": "a" * 40},
    }

    # Both grade prompts carry this phrase; the query-transform prompt does not.
    def generate(self, messages, **kwargs):
        graded = any("оценке релевантности" in message["content"] for message in messages)
        return LLMResponse(
            "YES" if graded else "cargo",
            "ollama",
            parity.MODEL,
            input_tokens=10,
            output_tokens=2,
        )

    _patch_ollama(monkeypatch, generate)
    monkeypatch.setattr(parity, "unload_llm", lambda: None)
    embedder = SimpleNamespace(
        manifest=inputs["expected_manifest"], embed_query=lambda q: [1.0, 0.0]
    )
    monkeypatch.setattr(_base_manager, "get_embeddings", lambda *a: embedder)

    class Encoder:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, pairs, **kwargs):
            return np.array([2.0 if "one" in text else 1.0 for _, text in pairs])

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=Encoder))
    for stage in ("transform", "embed", "retrieve", "grade"):
        parity.run_stage(SimpleNamespace(stage=stage, run=run, resume=False, limit=None), manifest)
    parity.run_stage(SimpleNamespace(stage="verify", run=run, resume=False, limit=None), manifest)
    assert (run / "comparison.json").exists()
    report = parity.read(run / "comparison.json")
    assert report["session_replay_matches"] == 2
    assert report["divergences"] == {}
    row = parity.load_stage(run / "verify/case.json", parity.digest(manifest))["chroma"]
    assert len(row["cands"]) == 2
    records = [json.loads(path.read_text()) for path in (run / "cache").glob("llm-*.json")]
    assert any(record["value"]["outcome"] == "structured_output_invalid" for record in records)
    assert any(
        record["request"]["method"] == "generate" and record["value"]["outcome"] == "response"
        for record in records
    )


def test_model_timeout_refuses_stage_with_cause(tmp_path, monkeypatch):
    def generate(self, messages, **kwargs):
        raise TimeoutError("model timeout")

    _patch_ollama(monkeypatch, generate)
    cache = parity.ReplayCache(tmp_path, "run")
    llm = parity.make_llm(cache, True, MANIFEST)
    with pytest.raises(TimeoutError, match="model timeout"):
        llm.generate_with_schema(MESSAGES, SCHEMA)
    assert not list(tmp_path.glob("llm-*.json"))
    assert len(cache.failures) == 1
    with pytest.raises(RuntimeError, match="failed") as excinfo:
        cache.require_clean()
    assert isinstance(excinfo.value.__cause__, TimeoutError)
    assert str(excinfo.value.__cause__) == "model timeout"


@pytest.mark.parametrize("variant", ["digest_changed", "no_captured_reply"])
def test_schema_error_without_verified_reply_is_a_failure(tmp_path, monkeypatch, variant):
    from llm.providers.base import LLMResponse, StructuredOutputValidationError
    from llm.providers.ollama import OllamaProvider

    def generate(self, messages, **kwargs):
        return LLMResponse("YES", "ollama", parity.MODEL)

    _patch_ollama(monkeypatch, generate)
    if variant == "digest_changed":
        digests = iter([parity.DIGEST])
        monkeypatch.setattr(
            "llm.providers.pinned_ollama.resolve_ollama_digest",
            lambda *a: next(digests, "f" * 64),
        )
        expected_error = ValueError
        expected_message = "digest mismatch after request"
    else:

        def generate_with_schema(self, messages, schema, **kwargs):
            raise StructuredOutputValidationError("structured output is not valid JSON")

        monkeypatch.setattr(OllamaProvider, "generate_with_schema", generate_with_schema)
        expected_error = StructuredOutputValidationError
        expected_message = "structured output is not valid JSON"

    cache = parity.ReplayCache(tmp_path, "run")
    llm = parity.make_llm(cache, True, MANIFEST)
    with pytest.raises(expected_error, match=expected_message) as call_error:
        llm.generate_with_schema(MESSAGES, SCHEMA)
    if variant == "digest_changed":
        assert not isinstance(call_error.value, StructuredOutputValidationError)
        assert isinstance(call_error.value.__cause__, StructuredOutputValidationError)
    assert not list(tmp_path.glob("llm-*.json"))
    assert len(cache.failures) == 1
    with pytest.raises(RuntimeError, match="failed") as refusal:
        cache.require_clean()
    assert refusal.value.__cause__ is call_error.value


def test_unknown_or_tampered_outcome_is_a_failure(tmp_path, monkeypatch):
    from llm.providers.base import StructuredOutputValidationError

    _record_invalid_outcome(tmp_path, monkeypatch)
    path = next(tmp_path.glob("llm-*.json"))
    record = json.loads(path.read_text())
    record["value"]["outcome"] = "mystery"
    record["value_sha256"] = parity.digest(record["value"])
    path.write_text(json.dumps(record))
    unknown_cache = parity.ReplayCache(tmp_path, "run")
    unknown_llm = parity.make_llm(unknown_cache, False, MANIFEST)
    with pytest.raises(ValueError, match="Unknown cached llm outcome") as excinfo:
        unknown_llm.generate_with_schema(MESSAGES, SCHEMA)
    assert not isinstance(excinfo.value, StructuredOutputValidationError)
    assert unknown_cache.failures

    tampered_root = tmp_path / "tampered"
    tampered_root.mkdir()
    _record_invalid_outcome(tampered_root, monkeypatch)
    path = next(tampered_root.glob("llm-*.json"))
    record = json.loads(path.read_text())
    record["value"]["raw_response"]["text"] = "TAMPERED"
    path.write_text(json.dumps(record))
    integrity_cache = parity.ReplayCache(tampered_root, "run")
    integrity_llm = parity.make_llm(integrity_cache, False, MANIFEST)
    with pytest.raises(ValueError, match="integrity"):
        integrity_llm.generate_with_schema(MESSAGES, SCHEMA)
    assert integrity_cache.failures
    with pytest.raises(RuntimeError, match="failed") as clean:
        integrity_cache.require_clean()
    assert clean.value.__cause__ is not None
