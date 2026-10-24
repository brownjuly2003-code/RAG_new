"""The instructions the chat's model reads with every question (QA_PROMPT_V4, 2026-10-24).

Stage 2's judge found three of the answer prompt's own instructions in the bad answers of the
external bases (docs/specs/answer-prompt-v4.md): the 4B declined whenever the documents
answered only in part or in general terms, with the prompt's words «the available information
does not answer the question» (29 of WixQA's 63 bad answers, 13 of ConditionalQA's 64); it
added the prompt's «suggest contacting a support specialist» to ordinary answers, a
recommendation no document holds (53 of WixQA's 100 answers carry it); and it printed the
placeholder of «add [N] right after it» as it stands (25 answers). The question goes through
the real path: HTTP -> the stream route -> a real ``ConversationSession`` -> langchain-ollama
-> a fake Ollama server, which records the prompt.
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

QUESTION = "How do I connect a domain I bought elsewhere?"
ANSWER = "Open Domains and choose Connect a domain you already own [1]."
SELF_EVAL_MARKER = "rating the quality of assistant answers"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")
# BM25 keeps only positive scores, and over two pages none has one: a word in one page of two
# weighs log(1) = 0. The third page shares no word with the question and gives the others
# their weight; it scores 0 and stays out of the prompt.
PAGES = {
    "connect_domain.md": "To connect a domain you already own, open Domains and choose "
    "Connect a domain you already own, then follow the steps of your provider.",
    "buy_domain.md": "To buy a new domain, open Domains and choose Buy a domain.",
    "billing.md": "Invoices are sent by email every month.",
}


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


def test_the_chat_model_is_told_to_answer_in_part_and_to_cite_by_number(
    monkeypatch, client, tmp_path, fake_ollama
):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace
    from vectordb._base_manager import Document, HybridRetriever

    for name in PATH_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama.url)
    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.ollama_base_url = fake_ollama.url
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    _base_trace._init_db()

    chunks = [
        Document(page_content=text, metadata={"source": source, "chunk_index": index})
        for index, (source, text) in enumerate(PAGES.items())
    ]
    retriever = HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: []),
        chunks=chunks,
        reranker=None,
        use_bm25=True,
        rerank_k=2,
        parent_expansion=False,
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
    # The answer's prompt is the one without the answer: the self-evaluation and the
    # suggestions quote it.
    answer_prompts = [p for p in prompts if ANSWER.split(" [")[0] not in p]
    assert len(answer_prompts) == 1, prompts
    prompt = " ".join(answer_prompts[0].split())
    assert "[1 | source=" in prompt and "[2 | source=" in prompt
    # A citation is shown by a number the model can copy; no letter stands in for it.
    assert "[N]" not in prompt
    assert "[1] for the first document in the context list, [2] for the second" in prompt
    # An answer in part is due before a decline, and a decline only when nothing answers.
    assert (
        "If the context answers the question only in part, or in general terms that cover "
        "the user's case, give what the context says and briefly name what it does not cover."
    ) in prompt
    assert "Only when nothing in the context answers the question" in prompt
    assert "state them instead of a bare yes or no" in prompt
    # No advice of the prompt's own: the chat shows the operator button by itself.
    assert "specialist" not in prompt
    assert "Do NOT invent facts, conditions or advice" in prompt
