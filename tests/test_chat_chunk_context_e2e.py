"""What the chat's model reads of a chunk: its header (PLAN.md stage 1, docs/specs/stage1-fixes.md).

The chunks are cut and headed by the product's own ingest steps (``select_chunks`` with
section chunking, then ``vectordb.manager.add_contextual_headers``) from an English page, and
a real ``HybridRetriever`` finds them by BM25 and expands them with their neighbours. The
question goes through the real path: HTTP -> the stream route -> a real
``ConversationSession`` -> langchain-ollama -> a fake Ollama server, which records the prompt.

Before stage 1 every chunk began with «[Контекст: Из документа returns_policy.md, раздел:
Returns policy › Damaged goods]»: Russian words before an English text, and the document's
title twice. Now the header names the page and its section once, in no language.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from agent import graph
from config.settings import Settings
from tests import _fake_ollama

QUESTION = "How do I report a damaged parcel?"
ANSWER = "Report it with a photo of the parcel [1]."
SELF_EVAL_MARKER = "оценке качества ответов"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")
HEADER = "[Returns policy › Damaged goods]"
CLAUSES = [
    f"Clause {i}: a damaged parcel is reported with photo number {i} and carton label {i * 7}."
    for i in range(1, 21)
]
PAGE = (
    "# Returns policy\n\n## Damaged goods\n\n"
    + " ".join(CLAUSES)
    + "\n\n## Refund timing\n\nRefunds are paid within ten working days of the inspection.\n"
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


def _chunks(settings: Settings) -> list[Any]:
    """The page cut and headed as ``vectordb.manager`` does before it embeds."""
    from vectordb import _base_manager, manager

    page = _base_manager.Document(page_content=PAGE, metadata={"source": "returns_policy.md"})
    chunks = _base_manager.select_chunks([page], None, 800, 200, settings=settings)
    chunks = manager.add_contextual_headers(chunks, full_documents=[page], chunk_size=800)
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
    return chunks


def test_the_chat_model_reads_a_language_free_header_naming_the_section_once(
    monkeypatch, client, tmp_path, fake_ollama
):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace
    from vectordb._base_manager import HybridRetriever

    for name in PATH_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama.url)
    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.ollama_base_url = fake_ollama.url
    settings.structural_chunking = True
    settings.contextual_headers = True
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    _base_trace._init_db()

    chunks = _chunks(settings)
    damaged = [c for c in chunks if c.metadata.get("h2") == "Damaged goods"]
    assert len(damaged) >= 3, [c.page_content[:60] for c in chunks]
    retriever = HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: []),
        chunks=chunks,
        reranker=None,
        use_bm25=True,
        parent_expansion=True,
        parent_expansion_window=2,
        parent_expansion_max_chars=3600,
    )
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
    answer_prompts = [
        p for p in prompts if SELF_EVAL_MARKER not in p and SUGGESTIONS_MARKER not in p
    ]
    assert len(answer_prompts) == 1, prompts
    prompt = answer_prompts[0]
    # The section's chunks reach the model under the header the ingest wrote.
    assert HEADER in prompt
    assert all(c.metadata["contextual_header"] == HEADER[1:-1] for c in damaged)
    # No words of a language in the header, and the page's title is said once: the file
    # name returns_policy.md and the heading "Returns policy" are the same words.
    assert "Контекст" not in prompt and "Из документа" not in prompt
