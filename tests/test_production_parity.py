"""Safety contracts for the real-model staged parity measurement."""

import json
import sys
from types import SimpleNamespace

import pytest

from scripts import production_parity as parity
from tests.test_production_index import inputs as index_inputs


@pytest.fixture
def inputs(tmp_path):
    return index_inputs.__wrapped__(tmp_path)


def test_selection_is_order_independent_and_refuses_duplicate_ids():
    cases = [{"case_id": str(i), "query": f"question {i}"} for i in range(40)]
    chosen = parity.select_cases(cases, 30)
    assert len(chosen) == 30
    assert chosen == parity.select_cases(list(reversed(cases)), 30)
    with pytest.raises(ValueError, match="unique"):
        parity.select_cases(cases + [cases[0]], 30)


def test_cache_reuses_exact_request_and_binds_run_identity(tmp_path):
    cache = parity.ReplayCache(tmp_path, "run-a")
    calls = []

    def compute():
        calls.append(1)
        return {"text": "real reply"}

    request = {"prompt": "p", "temperature": 0, "digest": "a"}
    assert cache.call("llm", request, compute) == {"text": "real reply"}
    assert cache.call("llm", request) == {"text": "real reply"}
    assert len(calls) == 1
    for other in ({**request, "digest": "b"}, {**request, "temperature": 1}):
        with pytest.raises(RuntimeError, match="cache miss"):
            cache.call("llm", other)
    with pytest.raises(RuntimeError, match="cache miss"):
        parity.ReplayCache(tmp_path, "run-b").call("llm", request)
    assert len(cache.failures) == 2


def test_corrupt_cache_is_rejected_without_recomputing(tmp_path):
    cache = parity.ReplayCache(tmp_path, "run")
    cache.call("llm", {"prompt": "p"}, lambda: {"text": "original"})
    path = next(tmp_path.glob("llm-*.json"))
    record = json.loads(path.read_text())
    record["value"]["text"] = "tampered"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="integrity"):
        cache.call("llm", {"prompt": "p"}, lambda: pytest.fail("must not recompute"))


def test_failed_model_call_is_retained_as_failure_not_cached(tmp_path):
    cache = parity.ReplayCache(tmp_path, "run")

    def fail():
        raise TimeoutError("model timeout")

    with pytest.raises(TimeoutError):
        cache.call("rerank", ["query", "text"], fail)
    assert cache.failures
    assert not list(tmp_path.glob("*.json"))
    with pytest.raises(RuntimeError, match="failed"):
        cache.require_clean()


def test_parity_compares_order_query_and_post_grade_hash():
    row = {
        "case_id": "case", "query_effective": "q", "query_transform": "rewrite",
        "query_transform_hash": "hash", "sent_context_sha256": "context",
        "pool": [1, 2], "ranked": [1], "vector": [1, 2],
    }
    assert parity.differences(row, dict(row)) == []
    assert parity.differences(row, {**row, "pool": [2, 1]}) == ["pool"]
    assert parity.differences(row, {**row, "sent_context_sha256": "other"}) == [
        "sent_context_sha256"
    ]
    assert parity.differences(row, {**row, "query_effective": "other"}) == ["query_effective"]


def test_invalid_query_vectors_are_refused():
    parity.validate_vector([1.0, 0.0], 2)
    for value in ([0.0, 0.0], [float("nan"), 0], [1.0], [2.0, 0]):
        with pytest.raises(ValueError, match="vector"):
            parity.validate_vector(value, 2)


def test_stage_record_binds_run_and_detects_changes(tmp_path):
    path = tmp_path / "stage.json"
    parity.save_stage(path, {"state": {"question": "q"}}, "run")
    assert parity.load_stage(path, "run") == {"state": {"question": "q"}}
    with pytest.raises(ValueError, match="Stage integrity"):
        parity.load_stage(path, "other-run")
    data = json.loads(path.read_text())
    data["result"]["state"]["question"] = "changed"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Stage integrity"):
        parity.load_stage(path, "run")


@pytest.mark.parametrize("failure", [None, "cache_miss", "graded_mismatch"])
def test_all_stages_replay_real_chroma_with_fixture_models(inputs, tmp_path, monkeypatch, failure):
    import numpy as np

    from llm.providers.base import LLMResponse
    from llm.providers.ollama import OllamaProvider
    from scripts.production_index import build_index
    from vectordb import _base_manager

    receipt = build_index(**inputs)
    run = tmp_path / "run"
    run.mkdir()
    cfg = {**parity.CONFIG, "retrieval_top_k": 2, "rerank_top_k": 2}
    manifest = {
        "config": cfg, "index_receipt": receipt, "index": str(inputs["output"]),
        "checkpoint": str(inputs["checkpoint"]), "corpus": str(inputs["archive"]),
        "cases": [{"case_id": "case", "query": "What cargo?"}],
        "llm": {"model": parity.MODEL, "digest": parity.DIGEST},
        "reranker": {"model": "fixture", "revision": "a" * 40},
    }
    calls = []

    def generate(self, messages, **kwargs):
        calls.append("transform")
        return LLMResponse("cargo", "ollama", parity.MODEL, input_tokens=10, output_tokens=2)

    def structured(self, messages, schema, **kwargs):
        calls.append("grade")
        # Reject the first document to prove that parity uses post-grading context.
        value = {"grades": [{"index": 1, "relevant": False}, {"index": 2, "relevant": True}]}
        return LLMResponse(json.dumps(value), "ollama", parity.MODEL,
                           input_tokens=20, output_tokens=10, structured_output=value)

    monkeypatch.setattr(OllamaProvider, "generate", generate)
    monkeypatch.setattr(OllamaProvider, "generate_with_schema", structured)
    monkeypatch.setattr("llm.providers.pinned_ollama.resolve_ollama_digest", lambda *a: parity.DIGEST)
    monkeypatch.setattr(parity, "unload_llm", lambda: None)
    embedder = SimpleNamespace(manifest=inputs["expected_manifest"], embed_query=lambda q: [1., 0.])
    monkeypatch.setattr(_base_manager, "get_embeddings", lambda *a: embedder)

    class Encoder:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, pairs, **kwargs):
            calls.append("rerank")
            return np.array([2. if "one" in text else 1. for _, text in pairs])

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=Encoder))
    for stage in ("transform", "embed", "retrieve", "grade"):
        parity.run_stage(SimpleNamespace(stage=stage, run=run, resume=False, limit=None), manifest)
    if failure == "cache_miss":
        for path in (run / "cache").glob("rerank-*.json"):
            path.unlink()
    elif failure == "graded_mismatch":
        path = run / "grade/case.json"
        record = parity.read(path)
        record["result"]["chroma"]["ranked"] = [1, 0]
        record["result_sha256"] = parity.digest(record["result"])
        path.write_text(json.dumps(record))
    args = SimpleNamespace(stage="verify", run=run, resume=False, limit=None)
    if failure:
        with pytest.raises((RuntimeError, ValueError), match="failed|mismatch"):
            parity.run_stage(args, manifest)
        assert not (run / "comparison.json").exists()
        return
    parity.run_stage(args, manifest)
    report = parity.read(run / "comparison.json")
    assert report["session_replay_matches"] == 2
    assert report["divergences"] == {}
    row = parity.load_stage(run / "verify/case.json", parity.digest(manifest))["chroma"]
    assert row["ranked"] == [0, 1]
    assert row["cand_metadata"][0]["chunk_index"] == 1
    assert len(row["cands"]) == 1
    assert calls == ["transform", "rerank", "grade"]
