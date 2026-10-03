"""Baseline capture contracts; fixture models only, no quality measurements."""

import gzip
import hashlib
import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from evaluation.judge_contract import _validate_chunk_address
from llm.providers.pinned_ollama import resolve_ollama_digest
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from tests.test_production_index import inputs as index_inputs


@pytest.fixture(autouse=True)
def _stop_chroma_systems():
    # Real-Chroma tests leak descriptors; the Mac gate's ssh shell has ulimit -n 256.
    yield
    if "chromadb" in sys.modules:
        from chromadb.api.shared_system_client import SharedSystemClient

        for system in list(SharedSystemClient._identifier_to_system.values()):
            system.stop()
        SharedSystemClient.clear_system_cache()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def addressed(tmp_path):
    sources = {"one.md": "prefix cargo one suffix", "two.md": "cargo two"}
    manifest = {"files": [{"name": k, "sha256": sha(v)} for k, v in sources.items()]}
    return baseline.AddressBook(manifest, sources, "gr1b-4436d61-graph-chunks:" + "a" * 64)


def test_production_baseline_valid_address_control(addressed):
    doc = {
        "page_content": "expanded text",
        "metadata": {
            "source": "one.md",
            "content_hash": sha("prefix cargo one suffix"),
            "h1": "Cargo",
            "h2": "",
            "h3": "Rules",
        },
    }
    record = addressed.document(doc)
    assert _validate_chunk_address(record["chunk_address"])["section_path"] == ["Cargo", "Rules"]
    assert record["text_sha256"] == sha("expanded text")
    assert record["address_reason"] is None


@pytest.mark.parametrize("body,reason", [("cargo one", None), ("missing", "address_unresolved")])
def test_production_baseline_offsets_use_seed_body(addressed, body, reason):
    seed = {
        "page_content": "[Контекст: cargo]\n" + body,
        "metadata": {
            "source": "one.md",
            "content_hash": sha("prefix cargo one suffix"),
        },
    }
    expanded = {**seed, "page_content": "full expanded text"}
    row = addressed.document(expanded, seed)
    assert row["address_reason"] == reason
    if reason is None:
        address = _validate_chunk_address(row["chunk_address"])
        assert address["char_start"] == 7
        assert address["char_end"] == 16
    assert row["text_sha256"] == sha("full expanded text")


def test_production_baseline_ambiguous_and_missing_address(addressed):
    addressed.sources["two.md"] = "cargo two cargo two"
    for doc in (
        {
            "page_content": "cargo two",
            "metadata": {"source": "two.md", "content_hash": sha("cargo two")},
        },
        {"page_content": "cargo", "metadata": {}},
    ):
        assert addressed.document(doc)["address_reason"] == "address_unresolved"


def test_production_baseline_source_revision_mismatch_is_integrity_failure(addressed):
    with pytest.raises(baseline.IntegrityError, match="source revision"):
        addressed.document(
            {
                "page_content": "cargo",
                "metadata": {
                    "source": "one.md",
                    "content_hash": "0" * 64,
                    "h1": "Cargo",
                },
            }
        )


def test_production_baseline_cache_model_failure_vs_integrity(tmp_path):
    cache = baseline.BaselineCache(tmp_path, "run")
    with pytest.raises(baseline.IntegrityError):
        cache.call("llm", "bad", lambda: (_ for _ in ()).throw(TimeoutError("timeout")))
    with pytest.raises(baseline.IntegrityError, match="cache"):
        cache.call("embedding", "missing")
    with pytest.raises(baseline.IntegrityError, match="digest"):
        cache.call(
            "llm",
            "digest",
            lambda: (_ for _ in ()).throw(ValueError("LLM digest mismatch before request")),
        )
    cache.call("llm", "good", lambda: {"text": "ok"})
    path = next(tmp_path.glob("llm-*.json"))
    record = parity.read(path)
    record["value"] = "tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(baseline.IntegrityError):
        cache.call("llm", "good")


def test_production_baseline_resume_checks_referenced_cache(tmp_path):
    cache = baseline.BaselineCache(tmp_path / "cache", "run")
    cache.call("llm", "request", lambda: {"text": "valid"})
    parity.save_stage(tmp_path / "case.json", {"model_calls": cache.calls}, "run")
    assert baseline.load_case(tmp_path / "case.json", "run", tmp_path)["model_calls"] == cache.calls
    path = next((tmp_path / "cache").glob("*.json"))
    record = parity.read(path)
    record["value"]["text"] = "tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(baseline.IntegrityError, match="cache integrity"):
        baseline.load_case(tmp_path / "case.json", "run", tmp_path)


def test_production_baseline_expansion_timer_and_text_capture(monkeypatch):
    doc = SimpleNamespace(page_content="expanded text", metadata={"chunk_index": 0})
    instance = SimpleNamespace(
        _expand_parents=lambda docs: [doc],
        _rerank_scored_with_status=lambda query, docs: ([(doc, 3.0)], True),
        _vector_store=SimpleNamespace(similarity_search=lambda *a, **kw: [doc]),
    )
    probe = {}
    monkeypatch.setattr(parity, "make_retriever", lambda *a: (instance, probe))
    clock = iter([10.0, 10.002])
    monkeypatch.setattr(baseline.time, "perf_counter", lambda: next(clock))
    wrapped, _ = baseline.make_retriever({}, None)
    wrapped._rerank_scored_with_status("cargo", [doc])
    assert wrapped._expand_parents([doc]) == [doc]
    assert probe["expansion_ms"] == pytest.approx(2.0)
    assert probe["expanded"][0]["page_content"] == "expanded text"
    assert probe["ranked_scores"] == [3.0]


def test_production_baseline_report_exclusion_and_all_provenance(tmp_path):
    manifest = {
        "cases": [{"case_id": "bad", "subset": "H"}, {"case_id": "clean", "subset": "Hm"}],
        "source_manifest": {"corpus_sha256": "c" * 64},
        "index_receipt": {"corpus_sha256": "a" * 64, "embedder_manifest": {"model_id": "fixture"}},
        "code_sha": "b" * 40,
        "datasets": {},
        "config": parity.CONFIG,
        "llm": {"model": parity.MODEL, "digest": parity.DIGEST},
        "reranker": {"revision": parity.RERANK_REVISION},
        "runtime": {},
        "chunker_version": "archive:a",
        "ledger_entry": {"config_sha256": "config"},
    }
    common = {
        "timings_ms": {"transform": 2.0, "expansion": 1.0},
        "host": "fixture",
        "peak_rss_bytes": 100,
    }
    clean = {
        **common,
        "status": "ok",
        "documents": [{"chunk_address": None}],
        "expanded_documents": [{"chunk_address": None}],
        "sent_context_sha256": "text",
        "query_effective": "cargo",
        "query_transform": "rewrite",
        "query_transform_hash": "query",
        "embedder_load_check": "eligible",
    }
    bad = {
        **common,
        "status": "excluded",
        "exclusion": {"case_id": "bad", "stage": "transform", "reason": "timeout"},
    }
    identity = parity.digest(manifest)
    parity.save_stage(tmp_path / "grade/bad.json", bad, identity)
    parity.save_stage(tmp_path / "grade/clean.json", clean, identity)
    baseline.report(tmp_path, manifest, False)
    report = parity.load_stage(tmp_path / "report.json", identity)
    assert report["denominator"] == 1
    assert report["denominators"] == {"H": 0, "Hm": 1}
    assert report["exclusions"] == [bad["exclusion"]]
    assert report["documents_without_address"] == 1
    provenance = report["provenance"]
    assert set(baseline.PROVENANCE_FIELDS) <= provenance.keys()
    assert all(provenance[field] is not None for field in baseline.PROVENANCE_FIELDS)
    for field in ("graph_digest", "generator_fingerprint", "judge_model", "bootstrap_seed"):
        assert provenance[field].startswith("N/A:")
    assert provenance["config"]["RAG_RERANK_BATCH"] == 8
    assert len(provenance["effective_queries"]) == 2
    assert report["timings_ms"]["expansion"] == {"n": 2, "p50": 1.0, "p95": 1.0}
    baseline.report(tmp_path, manifest, True)
    with pytest.raises(FileExistsError):
        baseline.report(tmp_path, manifest, False)


@pytest.fixture
def real_run(tmp_path, monkeypatch):
    import numpy as np

    from llm.providers.base import LLMResponse
    from llm.providers.ollama import OllamaProvider
    from scripts.production_embeddings import prepare_embeddings
    from scripts.production_index import build_index
    from vectordb import _base_manager

    inputs = index_inputs.__wrapped__(tmp_path)
    payload = json.loads(gzip.decompress(inputs["archive"].read_bytes()))
    for chunk in payload["chunks"]:
        chunk["metadata"].update(content_hash=sha(chunk["page_content"]), h1="Cargo")
    inputs["archive"].write_bytes(gzip.compress(json.dumps(payload).encode()))
    inputs["archive_sha256"] = parity.file_sha(inputs["archive"])
    inputs["checkpoint"] = tmp_path / "addressed-vectors.npz"
    prepare_embeddings(
        [c["page_content"] for c in payload["chunks"]],
        SimpleNamespace(
            manifest=inputs["expected_manifest"],
            embed_documents=lambda texts: [[1.0, 0.0], [0.0, 1.0]],
        ),
        inputs["checkpoint"],
        corpus_sha256=inputs["archive_sha256"],
    )
    receipt = build_index(**inputs)
    run = tmp_path / "run"
    run.mkdir()
    manifest = {
        "config": {**parity.CONFIG, "retrieval_top_k": 2, "rerank_top_k": 2},
        "index_receipt": receipt,
        "index": str(inputs["output"]),
        "checkpoint": str(inputs["checkpoint"]),
        "corpus": str(inputs["archive"]),
        "cases": [
            {"case_id": "bad", "query": "Bad cargo?", "subset": "H"},
            {"case_id": "clean", "query": "What cargo?", "subset": "Hm"},
        ],
        "llm": {"model": parity.MODEL, "digest": parity.DIGEST},
        "reranker": {"model": "fixture", "revision": "a" * 40},
        "code_sha": "b" * 40,
        "runtime": {"platform": "fixture-host"},
        "datasets": {},
        "source_manifest": {
            "files": [
                {"name": "one.md", "sha256": sha("cargo one")},
                {"name": "two.md", "sha256": sha("cargo two")},
            ]
        },
        "chunker_version": "gr1b-4436d61-graph-chunks:" + receipt["corpus_sha256"],
        "ledger_entry": {"config_sha256": parity.digest(parity.CONFIG)},
    }
    sources = tmp_path / "sources"
    sources.mkdir()
    for name, text in {"one.md": "cargo one", "two.md": "cargo two"}.items():
        (sources / name).write_text(text, encoding="utf-8")
    manifest["source_directory"] = str(sources)
    calls = []

    def generate(self, messages, **kwargs):
        calls.append("transform")
        return LLMResponse("cargo", "ollama", parity.MODEL)

    def structured(self, messages, schema, **kwargs):
        calls.append("grade")
        value = {"grades": [{"index": 1, "relevant": True}, {"index": 2, "relevant": True}]}
        return LLMResponse(json.dumps(value), "ollama", parity.MODEL, structured_output=value)

    monkeypatch.setattr(OllamaProvider, "generate", generate)
    monkeypatch.setattr(OllamaProvider, "generate_with_schema", structured)
    monkeypatch.setattr(
        "llm.providers.pinned_ollama.resolve_ollama_digest", lambda *a: parity.DIGEST
    )
    monkeypatch.setattr(parity, "unload_llm", lambda: None)
    embedder = SimpleNamespace(
        manifest=inputs["expected_manifest"], embed_query=lambda q: [1.0, 0.0]
    )
    monkeypatch.setattr(_base_manager, "get_embeddings", lambda *a: embedder)

    class Encoder:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, pairs, **kwargs):
            calls.append("rerank")
            return np.array([2.0 if "one" in text else 1.0 for _, text in pairs])

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=Encoder))
    return run, manifest, calls


def execute(run, manifest, stage, resume=False):
    baseline.run_stage(SimpleNamespace(stage=stage, run=run, resume=resume), manifest)


@pytest.mark.parametrize(
    "models",
    [
        [{"name": parity.MODEL, "digest": "invalid"}],
        [],
    ],
)
def test_production_baseline_digest_resolution_aborts(real_run, monkeypatch, models):
    from llm.providers import pinned_ollama

    run, manifest, _ = real_run

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps({"models": models}).encode()

    monkeypatch.setattr(pinned_ollama, "_urlopen", lambda *a, **kw: Response())
    monkeypatch.setattr(pinned_ollama, "resolve_ollama_digest", resolve_ollama_digest)
    with pytest.raises(baseline.IntegrityError, match="digest") as caught:
        execute(run, manifest, "transform")
    assert caught.value.__cause__ is not None
    assert not (run / "transform/bad.json").exists()


@pytest.mark.parametrize("error", ["ollama", "provider", "connection", "timeout", "url", "httpx"])
def test_production_baseline_model_environment_aborts_mid_stage(real_run, monkeypatch, error):
    import urllib.error

    from llm.providers.base import ProviderUnavailable
    from llm.providers.ollama import OllamaProvider
    from llm.providers.pinned_ollama import OllamaUnreachable

    run, manifest, _ = real_run
    errors = {
        "ollama": OllamaUnreachable("offline"),
        "provider": ProviderUnavailable("offline"),
        "connection": ConnectionError("offline"),
        "timeout": TimeoutError("offline"),
        "url": urllib.error.URLError("offline"),
        "httpx": httpx.ConnectError("offline"),
    }
    original = OllamaProvider.generate

    def generate(self, messages, **kwargs):
        if any("What cargo" in m["content"] for m in messages):
            raise errors[error]
        return original(self, messages, **kwargs)

    monkeypatch.setattr(OllamaProvider, "generate", generate)
    with pytest.raises(baseline.IntegrityError) as caught:
        execute(run, manifest, "transform")
    cause = caught.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert cause is errors[error]
    assert parity.load_stage(run / "transform/bad.json", parity.digest(manifest))["status"] == "ok"
    assert not (run / "transform/clean.json").exists()
    marker = parity.read(run / "transform.abort.json")
    assert marker["reason"] == str(caught.value)
    assert marker["cause_type"] == type(caught.value.__cause__).__name__
    assert marker["streak_records"] == []
    with pytest.raises(baseline.IntegrityError, match="transform.*offline"):
        execute(run, manifest, "embed")


def test_production_baseline_unload_does_not_mask_environment_cause(real_run, monkeypatch):
    from llm.providers.ollama import OllamaProvider
    from llm.providers.pinned_ollama import OllamaUnreachable

    run, manifest, _ = real_run
    failure = OllamaUnreachable("offline")

    def generate(*args, **kwargs):
        raise failure

    def unload():
        raise OSError("unload also offline")

    monkeypatch.setattr(OllamaProvider, "generate", generate)
    monkeypatch.setattr(parity, "unload_llm", unload)
    with pytest.raises(baseline.IntegrityError) as caught:
        execute(run, manifest, "transform")
    cause = caught.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert cause is failure
    assert not (run / "transform/bad.json").exists()


@pytest.mark.parametrize(
    "queries,aborts",
    [
        (["fail", "fail", "fail", "cargo"], True),
        (["fail", "cargo", "fail"], False),
    ],
)
def test_production_baseline_consecutive_exclusions_control(real_run, monkeypatch, queries, aborts):
    from agent import graph

    run, manifest, _ = real_run
    manifest["cases"] = [
        {"case_id": str(i), "query": q, "subset": "H"} for i, q in enumerate(queries)
    ]

    def factory(llm):
        def transform(state):
            if state["question"] == "fail":
                raise baseline.ModelFailure("model refused") from RuntimeError("refusal")
            return {**state, "search_query": "cargo"}

        return transform

    monkeypatch.setattr(graph, "make_transform_query_node", factory)
    if aborts:
        with pytest.raises(
            baseline.IntegrityError, match="consecutive exclusions.*environment suspected"
        ):
            execute(run, manifest, "transform")
        assert not (run / "transform/3.json").exists()
        assert len(list((run / "transform").glob("*.json"))) == 0
        marker = parity.read(run / "transform.abort.json")
        assert marker["stage"] == "transform"
        assert marker["run_sha256"] == parity.digest(manifest)
        assert marker["error_type"] == "IntegrityError"
        assert marker["timestamp_utc"].endswith("+00:00")
        assert [r["case_id"] for r in marker["streak_records"]] == ["0", "1", "2"]
        assert all(r["exclusion"]["error_type"] == "RuntimeError" for r in marker["streak_records"])
        with pytest.raises(FileExistsError, match="resume"):
            execute(run, manifest, "transform")
        with pytest.raises(baseline.IntegrityError, match="transform.*consecutive exclusions"):
            execute(run, manifest, "embed")
        # The refusal is not an embed stop: no marker, no output, no --resume needed later.
        assert not (run / "embed.abort.json").exists()
        assert not (run / "embed").exists()
        with pytest.raises(baseline.IntegrityError, match="transform.*consecutive exclusions"):
            baseline.report(run, manifest, False)
        monkeypatch.setattr(
            graph,
            "make_transform_query_node",
            lambda llm: lambda state: {**state, "search_query": "cargo"},
        )
        execute(run, manifest, "transform", resume=True)
        assert not (run / "transform.abort.json").exists()
        assert parity.read(run / "aborts/transform-1.json") == marker
        assert all(
            parity.load_stage(run / f"transform/{i}.json", parity.digest(manifest))["status"]
            == "ok"
            for i in range(4)
        )
        assert (
            parity.load_stage(run / "transform/3.json", parity.digest(manifest))["status"] == "ok"
        )
    else:
        execute(run, manifest, "transform")
        assert (
            parity.load_stage(run / "transform/1.json", parity.digest(manifest))["status"] == "ok"
        )
        assert (
            parity.load_stage(run / "transform/2.json", parity.digest(manifest))["status"]
            == "excluded"
        )
    for stage in baseline.STAGES[2:]:
        execute(run, manifest, stage)
    stops = parity.load_stage(run / "report.json", parity.digest(manifest))["provenance"][
        "stage_aborts"
    ]
    if aborts:
        assert stops == [
            {
                "stage": "transform",
                "reason": marker["reason"],
                "error_type": "IntegrityError",
                "streak_case_ids": ["0", "1", "2"],
            }
        ]
    else:
        assert stops == []
        assert not (run / "aborts").exists()


def test_production_baseline_streak_survives_kill(real_run, monkeypatch):
    from agent import graph

    run, manifest, _ = real_run
    manifest["cases"] = [{"case_id": str(i), "query": "cargo", "subset": "H"} for i in range(3)]
    count = 0

    def transform(state):
        nonlocal count
        count += 1
        if count == 3:
            raise KeyboardInterrupt("simulated kill")
        raise baseline.ModelFailure("refusal") from RuntimeError("refusal")

    monkeypatch.setattr(graph, "make_transform_query_node", lambda llm: transform)
    with pytest.raises(KeyboardInterrupt):
        execute(run, manifest, "transform")
    assert len(list((run / "transform").glob("*.json"))) == 2
    assert not (run / "transform.abort.json").exists()
    with pytest.raises(baseline.IntegrityError, match="consecutive exclusions"):
        execute(run, manifest, "transform", resume=True)
    assert list((run / "transform").glob("*.json")) == []
    marker = parity.read(run / "transform.abort.json")
    assert [r["case_id"] for r in marker["streak_records"]] == ["0", "1", "2"]
    # A new stop archives the open marker; a changed failure type may finish.
    with pytest.raises(baseline.IntegrityError, match="consecutive exclusions"):
        execute(run, manifest, "transform", resume=True)
    assert parity.read(run / "aborts/transform-1.json") == marker

    def changed(state):
        if state["question"] == "cargo":
            state["question"] = "changed"
            raise baseline.ModelFailure("different refusal") from TypeError("different")
        return state

    # Only one different failure: the other two succeed.
    count = 0

    def fixed(state):
        nonlocal count
        count += 1
        return changed(state) if count == 1 else state

    monkeypatch.setattr(graph, "make_transform_query_node", lambda llm: fixed)
    execute(run, manifest, "transform", resume=True)
    assert (run / "aborts/transform-2.json").exists()
    assert not (run / "transform.abort.json").exists()


def test_production_baseline_forwarded_exclusions_do_not_count(real_run, monkeypatch):
    run, manifest, _ = real_run
    manifest["cases"] = [{"case_id": str(i), "query": "cargo", "subset": "H"} for i in range(3)]
    for case in manifest["cases"]:
        parity.save_stage(
            run / "transform" / (case["case_id"] + ".json"),
            {
                "case_id": case["case_id"],
                "status": "excluded",
                "exclusion": {
                    "case_id": case["case_id"],
                    "stage": "transform",
                    "reason": "refusal",
                    "error_type": "RuntimeError",
                },
            },
            parity.digest(manifest),
        )
    execute(run, manifest, "embed")
    execute(run, manifest, "embed", resume=True)
    assert len(list((run / "embed").glob("*.json"))) == 3
    assert not list(run.glob("*.abort.json"))
    assert not (run / "aborts").exists()


def test_production_baseline_forwarded_exclusion_does_not_break_streak(real_run, monkeypatch):
    from agent import graph
    from vectordb import _base_manager

    run, manifest, _ = real_run
    manifest["cases"] = [
        {"case_id": str(i), "query": q, "subset": "H"}
        for i, q in enumerate(["first", "fail", "third", "fourth"])
    ]

    def transform(state):
        if state["question"] == "fail":
            raise baseline.ModelFailure("model refused") from RuntimeError("refusal")
        return {**state, "search_query": "cargo"}

    monkeypatch.setattr(graph, "make_transform_query_node", lambda llm: transform)
    execute(run, manifest, "transform")
    fixture = _base_manager.get_embeddings("fixture")

    def refused(query):
        raise ValueError("embedding refused")

    monkeypatch.setattr(
        _base_manager,
        "get_embeddings",
        lambda *a: SimpleNamespace(manifest=fixture.manifest, embed_query=refused),
    )
    # 0, 2 and 3 fail alike at embed; the forwarded exclusion of 1 sits between them.
    with pytest.raises(baseline.IntegrityError, match="embed: consecutive exclusions"):
        execute(run, manifest, "embed")
    marker = parity.read(run / "embed.abort.json")
    assert [r["case_id"] for r in marker["streak_records"]] == ["0", "2", "3"]
    assert sorted(p.stem for p in (run / "embed").glob("*.json")) == ["1"]


@pytest.mark.parametrize("mode", ["error", "missing", "empty"])
def test_production_baseline_vector_query_confirmation(real_run, monkeypatch, mode):
    run, manifest, calls = real_run
    execute(run, manifest, "transform")
    execute(run, manifest, "embed")
    original = parity.make_retriever
    failure = OSError("Chroma offline")

    def make(*args):
        instance, probe = original(*args)
        instance._bm25 = SimpleNamespace(get_scores=lambda tokens: [1.0, 0.5])

        def search(*a, **kw):
            if mode == "error":
                raise failure
            return []

        instance._vector_store.similarity_search = search
        if mode == "missing":
            instance._vector_search = lambda query: []
        return instance, probe

    monkeypatch.setattr(parity, "make_retriever", make)
    if mode == "empty":
        execute(run, manifest, "retrieve")
        assert (
            parity.load_stage(run / "retrieve/clean.json", parity.digest(manifest))["status"]
            == "ok"
        )
    else:
        with pytest.raises(baseline.IntegrityError, match="vector") as caught:
            execute(run, manifest, "retrieve")
        if mode == "error":
            assert caught.value.__cause__ is failure
        assert not (run / "retrieve/bad.json").exists()
    assert "rerank" in calls


@pytest.mark.parametrize("excluded", [False, True])
def test_production_baseline_rss_preserves_stage_peaks(real_run, monkeypatch, excluded):
    from agent import graph

    run, manifest, _ = real_run
    for stage, rss in [("transform", None), ("embed", 200), ("retrieve", 900), ("grade", 100)]:
        monkeypatch.setattr(baseline, "peak_rss", lambda: rss)
        if stage == "grade" and excluded:
            monkeypatch.setattr(
                graph,
                "make_grade_docs_node",
                lambda llm: lambda state: {**state, "doc_grade_outcome": "grader_error"},
            )
        execute(run, manifest, stage)
    row = parity.load_stage(run / "grade/clean.json", parity.digest(manifest))
    assert row["peak_rss_bytes"] == 900
    assert row["peak_rss_by_stage"] == {
        "transform": None,
        "embed": 200,
        "retrieve": 900,
        "grade": 100,
    }
    assert (
        parity.load_stage(run / "report.json", parity.digest(manifest))["provenance"][
            "peak_rss_bytes"
        ]
        == 900
    )


def test_production_baseline_rss_unavailable_without_resource(real_run, monkeypatch):
    run, manifest, _ = real_run
    monkeypatch.setitem(sys.modules, "resource", None)
    monkeypatch.setitem(sys.modules, "psutil", None)
    assert baseline.peak_rss() is None
    for stage in baseline.STAGES[1:]:
        execute(run, manifest, stage)
    assert (
        parity.load_stage(run / "grade/clean.json", parity.digest(manifest))["peak_rss_bytes"]
        is None
    )
    assert parity.load_stage(run / "report.json", parity.digest(manifest))["provenance"][
        "peak_rss_bytes"
    ].startswith("N/A:")


def test_production_baseline_clean_real_chroma_control_and_resume(real_run):
    run, manifest, calls = real_run
    for stage in baseline.STAGES[1:]:
        execute(run, manifest, stage)
        before = list(calls)
        execute(run, manifest, stage, resume=True)
        assert calls == before
        with pytest.raises(FileExistsError, match="resume"):
            execute(run, manifest, stage)
    row = parity.load_stage(run / "grade/clean.json", parity.digest(manifest))
    assert row["status"] == "ok"
    assert row["documents"]
    assert row["expanded_documents"]
    assert row["timings_ms"]["expansion"] >= 0
    assert row["timings_ms"]["grade"] >= 0
    assert row["routing"]["effective"] == "hybrid"
    assert row["ranked_scores"] == [2.0, 1.0]
    report = parity.load_stage(run / "report.json", parity.digest(manifest))
    assert report["denominator"] == 2
    assert report["exclusions"] == []
    assert report["documents_without_address"] == 0
    for doc in row["documents"]:
        _validate_chunk_address(doc["chunk_address"])
    assert set(baseline.PROVENANCE_FIELDS) <= report["provenance"].keys()
    assert report["provenance"]["config"]["RAG_RERANK_BATCH"] == 8
    assert report["provenance"]["judge_model"].startswith("N/A:")
    assert report["timings_ms"]["expansion"]["n"] == 2
    assert report["latency_evidence"] is False
    assert report["provenance"]["stage_aborts"] == []
    assert "stage_aborts" in baseline.PROVENANCE_FIELDS
    assert not list(run.glob("*.abort.json"))
    assert not (run / "aborts").exists()


def test_production_baseline_preflight_integrity_marker(real_run, monkeypatch):
    run, manifest, _ = real_run
    failure = baseline.IntegrityError("source revision mismatch")

    def fail(manifest):
        raise failure

    monkeypatch.setattr(baseline, "load_address_book", fail)
    with pytest.raises(baseline.IntegrityError) as caught:
        execute(run, manifest, "transform")
    assert caught.value is failure
    marker = parity.read(run / "transform.abort.json")
    assert marker["reason"] == str(failure)
    assert marker["cause_type"] is None


@pytest.mark.parametrize("failure", ["transform", "grade", "rerank"])
def test_production_baseline_exclusion_continues_and_reaches_report(real_run, monkeypatch, failure):
    from agent import graph
    from llm.providers.ollama import OllamaProvider

    run, manifest, _ = real_run
    if failure == "transform":
        original = OllamaProvider.generate

        def fail(self, messages, **kwargs):
            if any("Bad cargo" in m["content"] for m in messages):
                raise RuntimeError("fixture model refusal")
            return original(self, messages, **kwargs)

        monkeypatch.setattr(OllamaProvider, "generate", fail)
    elif failure == "grade":
        original_factory = graph.make_grade_docs_node

        def factory(llm):
            original = original_factory(llm)

            def grade(state):
                if state["question"].startswith("Bad"):
                    return {**state, "doc_grade_outcome": "partial_grader_error"}
                return original(state)

            return grade

        monkeypatch.setattr(graph, "make_grade_docs_node", factory)
    else:
        original = parity.make_retriever

        def retriever(*args):
            instance, probe = original(*args)
            ranked = instance._rerank_scored_with_status
            count = 0

            def rank(query, docs):
                nonlocal count
                count += 1
                if count == 1:
                    raise RuntimeError("Reranker fallback invalidates measurement")
                return ranked(query, docs)

            instance._rerank_scored_with_status = rank
            return instance, probe

        monkeypatch.setattr(parity, "make_retriever", retriever)
    for stage in baseline.STAGES[1:]:
        execute(run, manifest, stage)
    report = parity.load_stage(run / "report.json", parity.digest(manifest))
    assert report["denominator"] == 1
    assert report["exclusions"][0]["case_id"] == "bad"
    assert report["exclusions"][0]["stage"] == {"rerank": "retrieve"}.get(failure, failure)
    clean = parity.load_stage(run / "grade/clean.json", parity.digest(manifest))
    assert clean["status"] == "ok"


def test_production_baseline_digest_error_stops_stage(real_run, monkeypatch):
    run, manifest, _ = real_run
    monkeypatch.setattr("llm.providers.pinned_ollama.resolve_ollama_digest", lambda *a: "f" * 64)
    with pytest.raises(baseline.IntegrityError, match="digest"):
        execute(run, manifest, "transform")
    assert not (run / "transform/clean.json").exists()


def test_production_baseline_registration_all_cases_in_file_order(tmp_path, monkeypatch):
    root = tmp_path
    evaluation = root / "evaluation"
    evaluation.mkdir()
    for filename, count in (
        ("curated_cases_aircargo.jsonl", 100),
        ("curated_cases_aircargo_gr_multihop.jsonl", 15),
    ):
        path = evaluation / filename
        rows = [{"case_id": filename + str(i), "query": "cargo"} for i in range(count)]
        path.write_text("\n".join(json.dumps(c) for c in rows) + "\n", encoding="utf-8")
        if count == 100:
            parity.write_new(
                path.with_suffix(".manifest.json"), {"dataset_sha256": parity.file_sha(path)}
            )
    archive = evaluation / "gr1b-4436d61-graph-chunks.json.gz"
    archive.write_bytes(gzip.compress(json.dumps({"chunks": []}).encode()))
    checkpoint = root / "checkpoint"
    checkpoint.write_bytes(b"fixture")
    index = root / "index"
    index.mkdir()
    parity.write_new(
        index / "index-receipt.json",
        {
            "corpus_sha256": parity.file_sha(archive),
            "checkpoint_sha256": parity.file_sha(checkpoint),
            "embedder_manifest": {"revision": "a" * 40},
        },
    )
    parity.write_new(
        evaluation / "aircargo_corpus.manifest.json", {"files": [], "corpus_sha256": "c" * 64}
    )
    monkeypatch.chdir(root)
    monkeypatch.setattr(parity, "runtime_identity", lambda: {"platform": "fixture"})
    monkeypatch.setattr(baseline, "corpus_directory", lambda: root)
    args = SimpleNamespace(
        run=root / "run", index=index, checkpoint=checkpoint, code_sha="b" * 40, resume=False
    )
    baseline.prepare(args)
    manifest = parity.read(args.run / "manifest.json")
    assert len(manifest["cases"]) == 115
    assert manifest["cases"][0]["case_id"].endswith("jsonl0")
    assert manifest["cases"][99]["subset"] == "H"
    assert manifest["cases"][100]["subset"] == "Hm"
    assert len(list((args.run / "prepare").glob("*.json"))) == 115
    baseline.validate_inputs(manifest)
    args.resume = True
    baseline.prepare(args)
    args.resume = False
    with pytest.raises(FileExistsError, match="resume"):
        baseline.prepare(args)
    dataset = evaluation / "curated_cases_aircargo_gr_multihop.jsonl"
    dataset.write_text("tampered", encoding="utf-8")
    with pytest.raises(baseline.IntegrityError, match="Input"):
        baseline.validate_inputs(manifest)


def test_production_baseline_corrupt_stage_record_records_stop(real_run):
    run, manifest, _ = real_run
    execute(run, manifest, "transform")
    record = run / "transform/clean.json"
    original = record.read_text()
    payload = json.loads(original)
    payload["result_sha256"] = "0" * 64
    record.write_text(json.dumps(payload))
    with pytest.raises(baseline.IntegrityError, match="Stage record integrity mismatch"):
        execute(run, manifest, "embed")
    marker = parity.read(run / "embed.abort.json")
    assert marker["error_type"] == "IntegrityError"
    assert marker["cause_type"] == "ValueError"
    assert marker["run_sha256"] == parity.digest(manifest)
    assert marker["streak_records"] == []
    with pytest.raises(baseline.IntegrityError, match="Open abort at embed"):
        execute(run, manifest, "retrieve")
    assert not (run / "retrieve.abort.json").exists()
    record.write_text(original)
    with pytest.raises(FileExistsError, match="resume"):
        execute(run, manifest, "embed")
    execute(run, manifest, "embed", resume=True)
    assert not (run / "embed.abort.json").exists()
    assert parity.read(run / "aborts/embed-1.json") == marker
    execute(run, manifest, "retrieve")
    execute(run, manifest, "grade")
    stops = parity.load_stage(run / "report.json", parity.digest(manifest))["provenance"][
        "stage_aborts"
    ]
    assert stops == [
        {
            "stage": "embed",
            "reason": marker["reason"],
            "error_type": "IntegrityError",
            "streak_case_ids": [],
        }
    ]


def test_production_baseline_missing_referenced_cache_records_stop(real_run):
    run, manifest, _ = real_run
    execute(run, manifest, "transform")
    row = parity.load_stage(run / "transform/clean.json", parity.digest(manifest))
    cache = run / row["model_calls"][0]["cache_file"]
    assert cache.exists()
    cache.unlink()
    with pytest.raises(baseline.IntegrityError, match="Referenced cache integrity mismatch"):
        execute(run, manifest, "embed")
    marker = parity.read(run / "embed.abort.json")
    assert marker["error_type"] == "IntegrityError"
    assert marker["cause_type"] == "FileNotFoundError"
    assert marker["run_sha256"] == parity.digest(manifest)


def test_production_baseline_main_input_check_records_stop(real_run, monkeypatch):
    run, manifest, _ = real_run
    parity.write_new(run / "manifest.json", manifest)
    parity.write_new(run / "registration.json", {"manifest_sha256": parity.digest(manifest)})

    def fail(manifest_arg):
        raise baseline.IntegrityError("Source changed since registration")

    monkeypatch.setattr(baseline, "validate_inputs", fail)
    with pytest.raises(baseline.IntegrityError, match="Source changed"):
        baseline.main(["--stage", "transform", "--run", str(run)])
    marker = parity.read(run / "transform.abort.json")
    assert marker["run_sha256"] == parity.digest(manifest)
    with pytest.raises(baseline.IntegrityError, match="Open abort at transform"):
        baseline.main(["--stage", "embed", "--run", str(run)])
    assert not (run / "embed.abort.json").exists()
    monkeypatch.setattr(baseline, "validate_inputs", lambda *_: None)
    with pytest.raises(FileExistsError, match="resume"):
        baseline.main(["--stage", "transform", "--run", str(run)])
    assert baseline.main(["--stage", "transform", "--run", str(run), "--resume"]) == 0
    assert not (run / "transform.abort.json").exists()
    assert parity.read(run / "aborts/transform-1.json") == marker


def test_production_baseline_main_manifest_failures_use_registered_identity(real_run, monkeypatch):
    run, manifest, _ = real_run
    parity.write_new(run / "manifest.json", manifest)
    parity.write_new(run / "registration.json", {"manifest_sha256": parity.digest(manifest)})
    monkeypatch.setattr(baseline, "validate_inputs", lambda *_: None)
    on_disk = parity.read(run / "manifest.json")
    on_disk["code_sha"] = "c" * 40
    (run / "manifest.json").write_text(json.dumps(on_disk))
    with pytest.raises(baseline.IntegrityError, match="Manifest integrity mismatch"):
        baseline.main(["--stage", "transform", "--run", str(run)])
    marker = parity.read(run / "transform.abort.json")
    assert marker["run_sha256"] == parity.digest(manifest)
    (run / "registration.json").unlink()
    with pytest.raises(baseline.IntegrityError, match="Manifest integrity mismatch"):
        baseline.main(["--stage", "transform", "--run", str(run), "--resume"])
    second = parity.read(run / "transform.abort.json")
    assert second["run_sha256"] == "N/A: registration unreadable"
    assert parity.read(run / "aborts/transform-1.json") == marker


def test_production_baseline_validate_inputs_wraps_unexpected_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(parity, "source_identity", lambda path: "src")
    monkeypatch.setattr(parity, "runtime_identity", lambda: {"platform": "x"})
    with pytest.raises(baseline.IntegrityError, match="Input check failed: KeyError"):
        baseline.validate_inputs({})
    manifest = {
        "source_sha256": "src",
        "runtime": {"platform": "x"},
        "corpus": str(tmp_path / "missing-corpus.jsonl.gz"),
        "checkpoint": str(tmp_path / "missing-vectors.npz"),
        "index": str(tmp_path / "missing-index"),
        "index_receipt": {"corpus_sha256": "0" * 64, "checkpoint_sha256": "0" * 64},
        "index_receipt_sha256": "0" * 64,
        "source_manifest_path": str(tmp_path / "missing-sources.json"),
        "source_manifest_sha256": "0" * 64,
        "datasets": {},
    }
    with pytest.raises(baseline.IntegrityError, match="Input check failed: FileNotFoundError"):
        baseline.validate_inputs(manifest)


def test_production_baseline_refusals_record_nothing(real_run, monkeypatch):
    run, manifest, _ = real_run
    with pytest.raises(FileNotFoundError):
        execute(run, manifest, "embed")
    assert not list(run.glob("*.abort.json"))
    execute(run, manifest, "transform")
    with pytest.raises(FileExistsError, match="resume"):
        execute(run, manifest, "transform")
    assert not list(run.glob("*.abort.json"))
    parity.write_new(run / "manifest.json", manifest)
    parity.write_new(run / "registration.json", {"manifest_sha256": parity.digest(manifest)})
    monkeypatch.setattr(baseline, "validate_inputs", lambda *_: None)
    assert baseline.main(["--stage", "embed", "--run", str(run)]) == 0
    assert not list(run.glob("*.abort.json"))
    assert not (run / "aborts").exists()


def test_production_baseline_processing_error_records_stop(real_run, monkeypatch):
    from vectordb import _base_manager

    run, manifest, _ = real_run
    execute(run, manifest, "transform")
    fixture_manifest = _base_manager.get_embeddings("fixture").manifest
    monkeypatch.setattr(
        _base_manager,
        "get_embeddings",
        lambda *_: SimpleNamespace(manifest=fixture_manifest, embed_query=lambda query: [2.0, 0.0]),
    )
    with pytest.raises(ValueError):
        execute(run, manifest, "embed")
    marker = parity.read(run / "embed.abort.json")
    assert marker["error_type"] == "ValueError"
    assert marker["run_sha256"] == parity.digest(manifest)
    assert marker["streak_records"] == []


def test_production_baseline_registered_run_without_manifest_records_stop(tmp_path):
    run = tmp_path / "run"
    manifest = {"code_sha": "b" * 40}
    parity.write_new(run / "registration.json", {"manifest_sha256": parity.digest(manifest)})
    with pytest.raises(baseline.IntegrityError, match="Manifest integrity mismatch"):
        baseline.main(["--stage", "transform", "--run", str(run)])
    marker = parity.read(run / "transform.abort.json")
    assert marker["run_sha256"] == parity.digest(manifest)
    assert marker["cause_type"] == "FileNotFoundError"
    assert marker["streak_records"] == []


def test_production_baseline_unprepared_run_is_a_refusal(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    with pytest.raises(FileNotFoundError):
        baseline.main(["--stage", "transform", "--run", str(run)])
    assert not list(run.glob("*.abort.json"))
