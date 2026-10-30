"""RAG_RERANKER_RUNTIME=onnx in the chat: the model reads the documents in the INT8 file's order
(PLAN.md stage 4, item 5a, the short live series' setting).

The question goes through the real path: HTTP -> the stream route -> a real
``ConversationSession`` -> langchain-ollama -> a fake Ollama server, which records the prompt.
The retriever is the product's own ``build_retriever`` over six one-chunk pages, its vector lane
empty, so BM25 alone finds the candidates; its reranker is what the factory's ``get_reranker()``
loads under the setting: item 5a's INT8 export of bge-reranker-v2-m3 with the model's own
tokenizer. The rerank's pairs and scores are recorded on their way, the test scores the same
pairs itself, straight in ONNX Runtime in one batch as the product did (the INT8 file quantizes
its activations per batch), and the three documents kept reach the model's prompt in the order
of those scores, not in the order BM25 handed them to the rerank.

The INT8 file lies on the Mac, ``RAG_RERANKER_ONNX_E2E`` or item 5a's export by default; without
it, onnxruntime or transformers the test skips, as in CI.
"""

from __future__ import annotations

import gc
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent import graph
from config.settings import Settings
from tests import _fake_ollama

MODEL = "BAAI/bge-reranker-v2-m3"
ONNX = Path(
    os.environ.get(
        "RAG_RERANKER_ONNX_E2E", "/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx"
    )
)
QUESTION = "How do I report a damaged parcel?"
ANSWER = "Photograph the parcel and send the photos to support [1]."
SELF_EVAL_MARKER = "rating the quality of assistant answers"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")
KEPT = 3
PAGES = {
    # The question's words again and again, and nothing of an answer: BM25's first.
    "doc-a.md": "Damaged parcel report. Report a damaged parcel: damaged parcel, parcel report, "
    "damaged report. The staff canteen opens at nine.",
    "doc-b.md": "If your parcel arrives damaged, photograph the box and what was inside and send "
    "the photos to support within 48 hours; we open a claim the same day.",
    "doc-c.md": "Parcel tracking numbers are sent by e-mail after dispatch.",
    "doc-d.md": "Refunds for a returned parcel are paid within ten working days of inspection.",
    "doc-e.md": "To report a problem with an order, open the order page and choose Report.",
    "doc-f.md": "The warehouse is closed on public holidays.",
}

pytestmark = pytest.mark.skipif(
    not ONNX.is_file(), reason=f"no INT8 export of the reranker at {ONNX}"
)


def _reply(payload: dict[str, Any]) -> _fake_ollama.Reply:
    prompt = str(payload.get("prompt") or "")
    if SELF_EVAL_MARKER in prompt:
        return _fake_ollama.Reply(["85"])
    if SUGGESTIONS_MARKER in prompt:
        return _fake_ollama.Reply(["One?\nTwo?\nThree?"])
    return _fake_ollama.Reply([ANSWER])


@pytest.fixture
def fake_ollama() -> Iterator[_fake_ollama.FakeOllama]:
    with _fake_ollama.running(_reply) as server:
        yield server


def _own_scores(pairs: list[tuple[str, str]]) -> list[float]:
    """The pairs scored straight in ONNX Runtime, in one batch, as CrossEncoder.predict scores."""
    import numpy as np
    import onnxruntime as ort
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    session = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"])
    features = tokenizer(
        [query.strip() for query, _ in pairs],
        [text.strip() for _, text in pairs],
        padding=True,
        truncation="longest_first",
        return_tensors="np",
    )
    feed = {item.name: features[item.name].astype(np.int64) for item in session.get_inputs()}
    logits = session.run(None, feed)[0][:, 0].astype(np.float32)
    return [float(score) for score in 1.0 / (1.0 + np.exp(-logits))]


def test_the_chat_model_reads_the_documents_in_the_int8_files_order(
    monkeypatch, client, tmp_path, fake_ollama
):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("transformers")
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace
    from vectordb import _base_manager
    from vectordb.onnx_reranker import OnnxCrossEncoder

    for name in PATH_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("RAG_RERANK_BATCH", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama.url)
    monkeypatch.setenv("RAG_RERANKER_MODEL", MODEL)  # conftest empties it
    monkeypatch.setenv("RAG_RERANKER_RUNTIME", "onnx")
    monkeypatch.setenv("RAG_RERANKER_ONNX", str(ONNX))
    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.ollama_base_url = fake_ollama.url
    settings.rerank_top_k = KEPT
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    monkeypatch.setattr(_base_manager, "_cached_reranker", None)
    _base_trace._init_db()

    calls: list[tuple[list[tuple[str, str]], list[float]]] = []
    predict = OnnxCrossEncoder.predict

    def recorded(self: OnnxCrossEncoder, sentences: Any, *args: Any, **kwargs: Any) -> Any:
        scores = predict(self, sentences, *args, **kwargs)
        calls.append(([(q, t) for q, t in sentences], [float(s) for s in scores]))
        return scores

    monkeypatch.setattr(OnnxCrossEncoder, "predict", recorded)
    chunks = [
        _base_manager.Document(page_content=text, metadata={"source": name, "chunk_index": 0})
        for name, text in PAGES.items()
    ]
    retriever = _base_manager.build_retriever(
        [], None, vector_store=SimpleNamespace(similarity_search=lambda query, k: []), chunks=chunks
    )
    # The factory's own get_reranker() loaded the file the setting names.
    reranker = _base_manager._cached_reranker
    assert isinstance(reranker, OnnxCrossEncoder) and reranker.path == ONNX
    assert retriever._reranker is reranker
    session = graph.ConversationSession(retriever, None)

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)

    response = client.post("/api/ask/stream", json={"question": QUESTION})

    assert response.status_code == 200, response.text
    events = [
        json.loads(chunk[len("data: ") :])
        for chunk in response.text.split("\n\n")
        if chunk.startswith("data: ")
    ]
    results = [event for event in events if event.get("type") == "result"]
    assert len(results) == 1 and results[0]["answer"] == ANSWER, response.text
    prompts = [str(r["payload"].get("prompt")) for r in fake_ollama.requests]
    answer_prompts = [p for p in prompts if ANSWER.split(" [")[0] not in p]
    assert len(answer_prompts) == 1, prompts
    read = re.findall(r"\[\d+ \| source=(doc-[a-f]\.md)\]", answer_prompts[0])

    # One rerank of the question's candidates, BM25's order in, the product's scores out.
    assert len(calls) == 1, calls
    pairs, scores = calls[0]
    assert {query for query, _ in pairs} == {QUESTION}
    source_of = {text: name for name, text in PAGES.items()}
    handed = [source_of[text] for _, text in pairs]
    assert len(handed) >= KEPT + 1 and handed[0] == "doc-a.md", handed
    # The product's session freed before the test's own is loaded.
    reranker = retriever = session = None
    monkeypatch.setattr(_base_manager, "_cached_reranker", None)
    gc.collect()
    own = _own_scores(pairs)
    assert max(abs(a - b) for a, b in zip(scores, own, strict=True)) < 1e-6, (scores, own)
    ranked = [name for _, name in sorted(zip(own, handed, strict=True), key=lambda p: -p[0])]
    # The model reads the INT8 file's first three, in its order, and not BM25's.
    assert read == ranked[:KEPT], (read, ranked, handed)
    assert ranked[:KEPT] != handed[:KEPT], (ranked, handed)
