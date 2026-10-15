"""The chat's model calls ask the model not to think (ROADMAP, thread M, step 3).

On this path qwen3:1.7b, a model that can think, spent 130-155 output tokens
thinking before a one-sentence answer
(``reports/chat-live-small/33d4b42/tools/think_probe.out``): langchain-ollama
sent ``think: null`` and the model kept its default. Every model call of the
chat's stream — the answer, the self-evaluation and the suggested questions —
now carries ``think: false``, read here from the payloads a fake Ollama server
receives through the real path: HTTP -> the stream route -> a real
``ConversationSession`` -> the provider runtime and the graph's own model ->
langchain-ollama and the ollama client -> HTTP. So do the provider's tool calls
and the raw stream fallback. Ollama 0.33.2 answers ``think: false`` from a model
that cannot think (qwen2.5:7b) as it does without it and refuses only
``think: true`` (``reports/chat-live-small/33d4b42/tools/think_false_probe.out``, 2026-10-15).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from agent import graph
from config.settings import Settings
from tests import _fake_ollama

QUESTION = "Как подать претензию о повреждении груза?"
ANSWER = "Претензию подают в письменной форме перевозчику [1]."
SUGGESTIONS = ["Какие документы приложить?", "Сколько ждать ответа?", "Куда отправить акт?"]
SELF_EVAL_MARKER = "оценке качества ответов"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")


def _reply(payload: dict[str, Any]) -> _fake_ollama.Reply:
    prompt = str(payload.get("prompt") or "")
    if SELF_EVAL_MARKER in prompt:
        return _fake_ollama.Reply(["85"])
    if SUGGESTIONS_MARKER in prompt:
        return _fake_ollama.Reply(["\n".join(SUGGESTIONS)])
    return _fake_ollama.Reply([ANSWER])


@pytest.fixture
def fake_ollama() -> Iterator[_fake_ollama.FakeOllama]:
    with _fake_ollama.running(_reply) as server:
        yield server


def _events(text: str) -> list[dict[str, Any]]:
    return [
        json.loads(chunk[len("data: ") :])
        for chunk in text.split("\n\n")
        if chunk.startswith("data: ")
    ]


def test_every_model_call_of_the_chat_stream_turns_thinking_off(
    monkeypatch, client, tmp_path, fake_ollama
):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace

    for name in PATH_ENV:
        monkeypatch.delenv(name, raising=False)
    # Suggested questions build their client from OLLAMA_HOST.
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama.url)
    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.ollama_base_url = fake_ollama.url
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    _base_trace._init_db()

    documents = [
        SimpleNamespace(
            page_content=f"Раздел {i}. Претензия о повреждении груза подаётся письменно.",
            metadata={"source": f"rules-{i}.md", "doc_id": f"doc-{i}", "title": f"Правила {i}"},
        )
        for i in range(1, 4)
    ]
    retriever = SimpleNamespace(get_relevant_documents=lambda query: documents)
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
    results = [e for e in _events(response.text) if e.get("type") == "result"]
    assert len(results) == 1, response.text
    result = results[0]
    assert (result["route"], result["generation_source"]) == ("auto", "stream"), result
    assert result["answer"] == ANSWER
    assert (result["quality_source"], result["quality_score"]) == ("llm", 85)
    assert result["suggested_questions"] == SUGGESTIONS
    # The answer, the self-evaluation and the suggestions: three calls, none thinking.
    prompts = [str(r["payload"].get("prompt")) for r in fake_ollama.requests]
    assert len(prompts) == 3, prompts
    assert sum(SELF_EVAL_MARKER in p for p in prompts) == 1
    assert sum(SUGGESTIONS_MARKER in p for p in prompts) == 1
    assert [r["payload"].get("think") for r in fake_ollama.requests] == [False, False, False]


def test_raw_stream_fallback_turns_thinking_off(fake_ollama):
    import api.app as api_app

    async def collect() -> list[str]:
        return [
            token async for token in api_app._stream_ollama(QUESTION, "qwen3:1.7b", fake_ollama.url)
        ]

    assert "".join(asyncio.run(collect())) == ANSWER
    assert [r["payload"].get("think") for r in fake_ollama.requests] == [False]


def test_tool_call_binding_turns_thinking_off():
    from langchain_ollama import ChatOllama, OllamaLLM

    from llm.providers.ollama import _instantiate_with_timeout

    for cls in (OllamaLLM, ChatOllama):
        binding = _instantiate_with_timeout(cls, model="qwen3:1.7b", timeout_sec=15)
        assert binding.reasoning is False, cls


def test_binding_without_a_reasoning_field_gets_none():
    from llm.providers.ollama import _instantiate_with_timeout

    class Binding:
        model_fields: ClassVar[dict[str, object]] = {"model": object(), "timeout": object()}

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    binding = _instantiate_with_timeout(Binding, model="test", timeout_sec=15)
    assert "reasoning" not in binding.kwargs
