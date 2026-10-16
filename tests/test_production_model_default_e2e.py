"""The code's default model is Julia's production model (ROADMAP, thread M, step 4).

On 2026-10-16 Julia took Qwen3-4B-Instruct-2507 for production («Согласна с
тобой»); before this, every default named ``qwen2.5:7b``. Read here from the
requests a fake Ollama server receives, on a real ``Settings()`` with no model,
profile or registry in the environment: the web chat's stream (the answer, the
self-evaluation and the suggested questions) and ``/api/ask``, the widget's
route (the provider runtime of ``config/providers.yml`` behind every node of
the graph), each asks Ollama for that model and no other.
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

PRODUCTION_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
QUESTION = "Как подать претензию о повреждении груза?"
ANSWER = "Претензию подают в письменной форме перевозчику [1]."
SUGGESTIONS = ["Какие документы приложить?", "Сколько ждать ответа?", "Куда отправить акт?"]
SELF_EVAL_MARKER = "оценке качества ответов"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
# Anything that would choose the model, the profile or the registry for the run.
CHOICE_ENV = (
    "OLLAMA_MODEL_NAME",
    "OLLAMA_FAST_MODEL_NAME",
    "MODEL_ROUTING_ENABLED",
    "LLM_PROVIDER_PROFILE",
    "PROVIDER_REGISTRY_PATH",
    "STREAMING_RAG_PARITY",
    "STREAMING_QUALITY_EVAL",
)


def _reply(payload: dict[str, Any]) -> _fake_ollama.Reply:
    """One reply per prompt of the stream and of the graph, told apart by its template."""
    prompt = str(payload.get("prompt") or "")
    if SUGGESTIONS_MARKER in prompt:
        return _fake_ollama.Reply(["\n".join(SUGGESTIONS)])
    if SELF_EVAL_MARKER in prompt:
        return _fake_ollama.Reply(['{"score": 90, "reason": "grounded"}'])
    if "Classify the user question" in prompt:
        return _fake_ollama.Reply(["COMPLEX"])
    if "специалист по поисковым запросам" in prompt:
        return _fake_ollama.Reply(["претензия о повреждении груза"])
    if "оценке релевантности документов" in prompt:
        if "[1] source=" in prompt:
            grades = [{"index": i, "relevant": True} for i in range(1, 4)]
            return _fake_ollama.Reply([json.dumps({"grades": grades})])
        return _fake_ollama.Reply(["YES"])
    if "atomic factual claims" in prompt:
        return _fake_ollama.Reply(["- Претензию подают в письменной форме."])
    if "fact-checker" in prompt:
        return _fake_ollama.Reply(["SUPPORTED: Претензия подаётся в письменной форме."])
    return _fake_ollama.Reply([ANSWER])


@pytest.fixture
def fake_ollama() -> Iterator[_fake_ollama.FakeOllama]:
    with _fake_ollama.running(_reply) as server:
        yield server


@pytest.fixture
def served(monkeypatch, tmp_path, fake_ollama):
    """The API on a real ``Settings()`` whose only change is where Ollama listens."""
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace

    for name in CHOICE_ENV:
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
    # No model handed in: the session builds its own from the settings.
    session = graph.ConversationSession(retriever, None, max_iterations=0)

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)
    return settings


def _events(text: str) -> list[dict[str, Any]]:
    return [
        json.loads(chunk[len("data: ") :])
        for chunk in text.split("\n\n")
        if chunk.startswith("data: ")
    ]


def test_settings_default_to_the_production_model(monkeypatch):
    for name in CHOICE_ENV:
        monkeypatch.delenv(name, raising=False)
    assert Settings().ollama_model_name == PRODUCTION_MODEL


def test_the_chat_stream_asks_ollama_for_the_production_model(client, served, fake_ollama):
    response = client.post("/api/ask/stream", json={"question": QUESTION})

    assert response.status_code == 200, response.text
    results = [e for e in _events(response.text) if e.get("type") == "result"]
    assert len(results) == 1, response.text
    assert results[0]["route"] == "auto", results[0]
    assert results[0]["suggested_questions"] == SUGGESTIONS
    prompts = [str(r["payload"].get("prompt")) for r in fake_ollama.requests]
    # The answer, the self-evaluation and the suggestions: three calls, one model.
    assert len(prompts) == 3, prompts
    assert sum(SELF_EVAL_MARKER in p for p in prompts) == 1
    assert sum(SUGGESTIONS_MARKER in p for p in prompts) == 1
    assert [r["payload"].get("model") for r in fake_ollama.requests] == [PRODUCTION_MODEL] * 3


def test_api_ask_asks_ollama_for_the_production_model(client, served, fake_ollama):
    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["route"] != "error", body
    prompts = [str(r["payload"].get("prompt")) for r in fake_ollama.requests]
    # The graph graded the documents, wrote the answer and judged it.
    for template in (
        "оценке релевантности документов",
        "ассистент службы поддержки",
        SELF_EVAL_MARKER,
    ):
        assert any(template in p for p in prompts), (template, [p[:80] for p in prompts])
    assert {r["path"] for r in fake_ollama.requests} == {"/api/generate"}
    assert {r["payload"].get("model") for r in fake_ollama.requests} == {PRODUCTION_MODEL}
