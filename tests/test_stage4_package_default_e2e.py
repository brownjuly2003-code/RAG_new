"""The stage-4 package is the chat's code default, observed at retrieval and HTTP.

Only the INT8 order test needs the Mac's export. The window and lane tests use
real BM25, the product's retriever factory and ConversationSession, and the real
langchain-ollama transport to a fake Ollama server, with no reranker installed.
"""

from __future__ import annotations

import gc
import json
import re
from types import SimpleNamespace

import pytest

from agent import graph
from config.settings import Settings
from tests import _fake_ollama
from tests.test_reranker_onnx_e2e import (
    ANSWER,
    MODEL,
    ONNX,
    PAGES,
    QUESTION,
    SELF_EVAL_MARKER,
    SUGGESTIONS_MARKER,
    _own_scores,
    _reply,
)
from vectordb import _base_manager

DEFAULT_ENV = (
    "RAG_RETRIEVAL_TOP_K",
    "OLLAMA_CONTEXT_WINDOW",
    "RAG_RERANKER_RUNTIME",
    "RAG_RERANK_TOP_K",
    "RAG_RERANK_BATCH",
    "RAG_HYBRID_SEARCH",
    "RAG_RETRIEVAL_STRATEGY",
    "RAG_PARENT_CHILD",
    "RAG_PARENT_EXPANSION",
    "STREAMING_RAG_PARITY",
    "STREAMING_QUALITY_EVAL",
    "STREAMING_SELF_EVAL_MODE",
    "LLM_PROVIDER_PROFILE",
    "PROVIDER_REGISTRY_PATH",
    "OLLAMA_MODEL_NAME",
    "MODEL_ROUTING_ENABLED",
)


@pytest.fixture
def fake_ollama():
    with _fake_ollama.running(_reply) as server:
        yield server


@pytest.fixture
def settings(monkeypatch, tmp_path, fake_ollama, client):
    import api.app as api_app
    import config.settings
    from tracing import _base_trace

    for name in DEFAULT_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama.url)
    settings = Settings()
    settings.ollama_base_url = fake_ollama.url
    settings.tracing_db_path = tmp_path / "traces.db"
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    monkeypatch.setattr(_base_manager, "_cached_reranker", None)
    _base_trace._init_db()
    return settings


def _ask(monkeypatch, client, retriever):
    import api.app as api_app
    from api.routers import conversation
    from llm.providers.ollama import OllamaProvider

    session = graph.ConversationSession(retriever, None)
    provider_calls = []
    generate_stream = OllamaProvider.generate_stream

    async def recorded_stream(self, messages, **kwargs):
        provider_calls.append(self)
        async for token in generate_stream(self, messages, **kwargs):
            yield token

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    # Undo these references before loading a second ORT session for independent scoring.
    with monkeypatch.context() as request_patch:
        request_patch.setattr(OllamaProvider, "generate_stream", recorded_stream)
        request_patch.setattr(api_app, "_get_or_create_session", session_factory)
        request_patch.setattr(api_app, "log_audit", no_postgres)
        request_patch.setattr(conversation, "_persist_ask_messages", no_postgres)
        response = client.post("/api/ask/stream", json={"question": QUESTION})
    assert response.status_code == 200, response.text
    events = [
        json.loads(chunk[len("data: ") :])
        for chunk in response.text.split("\n\n")
        if chunk.startswith("data: ")
    ]
    results = [event for event in events if event.get("type") == "result"]
    assert len(results) == 1 and results[0]["answer"] == ANSWER, response.text
    assert results[0]["quality_source"] == "llm", results[0]
    assert len(provider_calls) == 1  # real provider -> langchain-ollama, not the raw HTTP fallback


@pytest.fixture
def lanes(monkeypatch, settings):
    # 24 matching one-chunk pages, plus background pages to keep BM25 IDF positive.
    # Both lanes have more than the old 20 candidates available.
    chunks = [
        _base_manager.Document(
            page_content=f"Damaged parcel report {i}: photograph the box and contact support.",
            metadata={"source": f"parcel-{i}.md", "chunk_index": 0},
        )
        for i in range(24)
    ] + [
        _base_manager.Document(
            page_content=f"Canteen menu {i}: soup and bread at noon.",
            metadata={"source": f"menu-{i}.md", "chunk_index": 0},
        )
        for i in range(30)
    ]
    vector_calls = []
    pools = []

    def vector_search(query, k):
        vector_calls.append((query, k))
        return chunks[:k]

    retriever = _base_manager.build_retriever(
        [], None, vector_store=SimpleNamespace(similarity_search=vector_search), chunks=chunks
    )
    assert settings.reranker_model == ""  # conftest: no ONNX file or runtime required
    assert retriever._bm25 is not None
    scores = retriever._bm25.get_scores(_base_manager._tokenize_for_bm25(QUESTION))
    assert sum(score > 0 for score in scores) == 24
    merge = retriever._rrf_merge

    def recorded_merge(vector, bm25, *other):
        pools.append((list(vector), list(bm25)))
        return merge(vector, bm25, *other)

    monkeypatch.setattr(retriever, "_rrf_merge", recorded_merge)
    return retriever, vector_calls, pools


def test_default_chat_answer_and_classic_self_eval_send_3584(
    monkeypatch, client, settings, lanes, fake_ollama
):
    _ask(monkeypatch, client, lanes[0])
    payloads = [request["payload"] for request in fake_ollama.requests]
    answers = [
        p
        for p in payloads
        if SELF_EVAL_MARKER not in p["prompt"] and SUGGESTIONS_MARKER not in p["prompt"]
    ]
    evaluations = [p for p in payloads if SELF_EVAL_MARKER in p["prompt"]]
    assert len(answers) == 1 and len(evaluations) == 1, payloads
    assert settings.streaming_self_eval_mode == "classic"
    assert {request["path"] for request in fake_ollama.requests} == {"/api/generate"}
    for payload in [*answers, *evaluations]:
        assert payload["options"]["num_ctx"] == 3584, payload


def test_default_chat_retrieves_14_candidates_from_each_lane(monkeypatch, client, lanes):
    retriever, vector_calls, pools = lanes
    _ask(monkeypatch, client, retriever)
    assert vector_calls == [(QUESTION, 14)]
    assert len(pools) == 1
    vector, bm25 = pools[0]
    assert len(vector) == 14
    assert len(bm25) == 14
    assert len({doc.metadata["source"] for doc in bm25}) == 14


@pytest.mark.skipif(not ONNX.is_file(), reason=f"no INT8 export of the reranker at {ONNX}")
def test_default_chat_loads_int8_and_sends_its_top_five_in_score_order(
    monkeypatch, client, settings, fake_ollama
):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("transformers")
    from vectordb.onnx_reranker import OnnxCrossEncoder

    monkeypatch.setenv("RAG_RERANKER_MODEL", MODEL)  # conftest empties it
    monkeypatch.setenv("RAG_RERANKER_ONNX", str(ONNX))
    selected = Settings()
    settings.reranker_model = selected.reranker_model
    settings.reranker_onnx_path = selected.reranker_onnx_path
    # Check before loading: the baseline must fail, without downloading a torch model.
    assert settings.reranker_runtime == "onnx"
    settings.validate()
    calls = []
    predict = OnnxCrossEncoder.predict

    def recorded(self, sentences, *args, **kwargs):
        scores = predict(self, sentences, *args, **kwargs)
        calls.append(([(q, text) for q, text in sentences], [float(s) for s in scores]))
        return scores

    monkeypatch.setattr(OnnxCrossEncoder, "predict", recorded)
    chunks = [
        _base_manager.Document(page_content=text, metadata={"source": name, "chunk_index": 0})
        for name, text in PAGES.items()
    ]
    retriever = _base_manager.build_retriever(
        [],
        None,
        vector_store=SimpleNamespace(similarity_search=lambda query, k: []),
        chunks=chunks,
    )
    reranker = _base_manager._cached_reranker
    assert isinstance(reranker, OnnxCrossEncoder)
    assert reranker.path == ONNX
    assert retriever._reranker is reranker
    _ask(monkeypatch, client, retriever)
    prompts = [r["payload"]["prompt"] for r in fake_ollama.requests]
    answers = [p for p in prompts if SELF_EVAL_MARKER not in p and SUGGESTIONS_MARKER not in p]
    assert len(answers) == 1, prompts
    read = re.findall(r"\[\d+ \| source=(doc-[a-f]\.md)\]", answers[0])
    assert len(calls) == 1
    pairs, scores = calls[0]
    assert len(pairs) == 5  # BM25 alone matches five pages; the sixth shares no question term.
    assert {query for query, _ in pairs} == {QUESTION}
    source_of = {text: name for name, text in PAGES.items()}
    handed = [source_of[text] for _, text in pairs]
    reranker = retriever = None
    _base_manager._cached_reranker = None  # fixture already restores the original cache
    gc.collect()
    own = _own_scores(pairs)
    assert max(abs(a - b) for a, b in zip(scores, own, strict=True)) < 1e-6, (scores, own)
    ranked = [name for _, name in sorted(zip(own, handed, strict=True), key=lambda p: -p[0])]
    assert read == ranked[:5], (read, ranked, handed)
    assert ranked[:5] != handed[:5], (ranked, handed)
