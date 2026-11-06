"""Real HTTP/graph/provider paths; only retrieval, persistence and model I/O are fake."""

from __future__ import annotations

import json
import socket
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import graph
from config.settings import Settings
from llm.providers import runtime
from llm.providers.base import estimate_window_tokens, window_input_limit
from tests._fake_codex import ANSWER
from tests._fake_codex import fake_codex as fake_codex

QUESTION = "How do I submit a damage claim?"
LOCAL_ANSWER = "The local model says: submit a written damage claim [1]."
MODEL = "qwen3:4b-instruct-2507-q4_K_M"


def _reply(prompt, complexity):
    if "Classify the user question" in prompt:
        return json.dumps(
            {
                "complexity": complexity,
                "question_class": "single_hop",
                "entities": [],
                "needs_multi_hop": False,
                "reason_code": "SINGLE_SOURCE",
            }
        )
    if '"grades"' in prompt:
        return json.dumps({"grades": [{"index": i, "relevant": True} for i in range(1, 6)]})
    if '"relevant"' in prompt:
        return '{"relevant": true, "reason": "supported"}'
    if "YES" in prompt and "NO" in prompt:
        return "YES"
    if "rating the quality of assistant answers" in prompt:
        return "95"
    if "propose 3 short follow-up questions" in prompt:
        return "Which documents?\nWhich address?\nWhich deadline?"
    if "atomic factual claims" in prompt:
        return "- Submit a written damage claim."
    if "fact-checker" in prompt:
        return "SUPPORTED: Submit a written damage claim."
    if "You are a support assistant" in prompt:
        return LOCAL_ANSWER
    return "written damage claim"


def _binding(calls, complexity):
    class Binding:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def invoke(self, prompt):
            calls.append({"prompt": prompt, "kwargs": self.kwargs})
            return _reply(prompt, complexity)

        def stream(self, prompt):
            yield self.invoke(prompt)

        async def astream(self, prompt):
            yield self.invoke(prompt)

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    return module


def _documents():
    return [
        SimpleNamespace(
            page_content="\n\n".join(
                f"Section {i}.{j}: Submit a written damage claim. "
                + "Keep all shipping documents and delivery receipts. " * 12
                for j in range(8)
            ),
            metadata={"source": f"rules-{i}.md", "doc_id": f"doc-{i}", "title": f"Rules {i}"},
        )
        for i in range(1, 6)
    ]


def _setup(
    monkeypatch,
    tmp_path,
    fake,
    profile,
    calls,
    complexity,
    parity,
    max_iterations=0,
    *,
    routing=True,
):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace
    from vectordb import manager

    settings = Settings()
    settings.llm_provider_profile = profile
    settings.codex_binary = str(fake.binary)
    settings.codex_home = str(fake.root)
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.agentic_mode = False
    settings.hyde = False
    settings.online_evaluators_enabled = False
    settings.fact_verification_enabled = True
    settings.model_routing_enabled = routing
    settings.llm_cache_enabled = False
    settings.streaming_rag_parity = parity
    settings.streaming_quality_eval = True
    settings.streaming_self_eval_mode = "classic"
    settings.judge_independence_required = False
    settings.ollama_context_window = 3584
    for module in (config.settings, graph, api_app, manager):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding(calls, complexity))
    runtime.clear_provider_runtime_cache()
    graph.clear_support_graph_cache()
    _base_trace._init_db()
    session = graph.ConversationSession(
        SimpleNamespace(get_relevant_documents=lambda query: _documents()),
        None,
        max_iterations=max_iterations,
    )

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(*args, **kwargs):
        return None

    def no_network(*args, **kwargs):
        raise AssertionError("This test must never open a network connection")

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr(conversation, "_admit_durable_turn", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    return settings


def _request(client, endpoint):
    response = client.post(endpoint, json={"question": QUESTION})
    assert response.status_code == 200, response.text
    if endpoint.endswith("/stream"):
        events = [json.loads(p[6:]) for p in response.text.split("\n\n") if p.startswith("data: ")]
        results = [e for e in events if e.get("type") == "result"]
        assert len(results) == 1, response.text
        return results[0], events
    return response.json(), []


@pytest.mark.parametrize(
    "endpoint,parity", [("/api/ask", False), ("/api/ask/stream", False), ("/api/ask/stream", True)]
)
@pytest.mark.parametrize("complexity", ["simple", "complex"])
def test_codex_answer_matches_local_prompt_and_keeps_auxiliary_calls_local(
    monkeypatch, client, tmp_path, fake_codex, endpoint, parity, complexity
):
    runtime._FAILOVER_CACHE_UNTIL.clear()
    local_calls = []
    # Since 2026-11-06: legacy stream needs hybrid without model routing; graph keeps routing on.
    _setup(
        monkeypatch,
        tmp_path,
        fake_codex,
        "local-first",
        local_calls,
        complexity,
        parity,
        routing=endpoint == "/api/ask" or parity,
    )
    baseline, _ = _request(client, endpoint)
    assert baseline["answer"] == LOCAL_ANSWER, baseline
    answer_prompts = [
        c["prompt"] for c in local_calls if "You are a support assistant" in c["prompt"]
    ]
    assert len(answer_prompts) == 1
    expected_prompt = answer_prompts[0].encode("utf-8")

    codex_calls = []
    _setup(
        monkeypatch,
        tmp_path,
        fake_codex,
        "codex-answer",
        codex_calls,
        complexity,
        parity,
        routing=endpoint == "/api/ask" or parity,
    )
    body, events = _request(client, endpoint)
    assert body["answer"] == ANSWER, body
    assert (body["answer_provider"], body["answer_model"]) == ("codex", "gpt-6-astra")
    (record,) = fake_codex.records()
    wrapper = (Path(__file__).resolve().parents[1] / "llm/codex_wrapper.txt").read_bytes()
    assert record["stdin"].encode("utf-8") == wrapper.replace(b"{prompt}", expected_prompt, 1)
    assert "rules-5.md" not in expected_prompt.decode()
    assert not any("You are a support assistant" in c["prompt"] for c in codex_calls)
    for call in codex_calls:
        assert call["kwargs"]["model"] == MODEL
        assert call["kwargs"]["num_ctx"] == 3584
        assert estimate_window_tokens(call["prompt"]) <= window_input_limit(
            3584, call["kwargs"]["num_predict"]
        )
    assert any("rating the quality of assistant answers" in c["prompt"] for c in codex_calls)
    if endpoint == "/api/ask" or parity:
        assert any("Classify the user question" in c["prompt"] for c in codex_calls)
        if complexity == "complex":
            assert any("fact-checker" in c["prompt"] for c in codex_calls)
            assert any('"relevant"' in c["prompt"] for c in codex_calls)
    else:
        assert any("propose 3 short follow-up questions" in c["prompt"] for c in codex_calls)
    if events:
        assert "".join(e["token"] for e in events if e.get("type") == "token") == ANSWER


@pytest.mark.parametrize(
    "endpoint,parity", [("/api/ask", False), ("/api/ask/stream", False), ("/api/ask/stream", True)]
)
def test_failed_codex_uses_named_local_fallback_and_outage_cache(
    monkeypatch, client, tmp_path, fake_codex, endpoint, parity
):
    runtime._FAILOVER_CACHE_UNTIL.clear()
    fake_codex.configure(fixture="bad", exit_code=1)
    calls = []
    _setup(
        monkeypatch,
        tmp_path,
        fake_codex,
        "codex-answer",
        calls,
        "complex",
        parity,
        routing=endpoint == "/api/ask" or parity,
    )
    body, _ = _request(client, endpoint)
    assert body["answer"] == LOCAL_ANSWER, body
    assert (body["answer_provider"], body["answer_model"]) == ("ollama", MODEL)
    answer_calls = [c for c in calls if "You are a support assistant" in c["prompt"]]
    assert len(answer_calls) == 1
    assert (
        fake_codex.records()[0]["stdin"].split("<<<PROMPT\n", 1)[1].rsplit("\nPROMPT>>>", 1)[0]
        == answer_calls[0]["prompt"]
    )
    # A second request during the outage uses the existing failover cache.
    body, _ = _request(client, endpoint)
    assert body["answer"] == LOCAL_ANSWER
    assert body["answer_provider"] == "ollama"
    assert len(fake_codex.records()) == 1
    runtime._FAILOVER_CACHE_UNTIL.clear()


def test_retry_rewrites_on_4b_and_only_answers_on_codex(monkeypatch, client, tmp_path, fake_codex):
    from agent.prompts import build_query_rewrite_prompt
    from llm.providers.base import flatten_messages

    runtime._FAILOVER_CACHE_UNTIL.clear()
    original_reply = _reply
    scores = iter(["10", "95"])

    def retry_reply(prompt, complexity):
        if "rating the quality of assistant answers" in prompt:
            return next(scores)
        return original_reply(prompt, complexity)

    monkeypatch.setattr(sys.modules[__name__], "_reply", retry_reply)
    calls = []
    settings = _setup(
        monkeypatch, tmp_path, fake_codex, "codex-answer", calls, "complex", False, max_iterations=1
    )
    # Replayed CLI usage includes its system prompt; this test targets routing,
    # independently of the graph's separately tested per-request budget.
    settings.llm_max_calls_per_request = 100
    settings.llm_max_input_tokens_per_request = 100000
    settings.llm_max_total_tokens_per_request = 100000
    body, _ = _request(client, "/api/ask")
    assert body["answer"] == ANSWER and body["answer_provider"] == "codex", body
    assert len(fake_codex.records()) == 2
    expected_rewrite = flatten_messages(
        [
            {
                "role": "user",
                "content": build_query_rewrite_prompt(
                    question=QUESTION,
                    previous_answer=ANSWER,
                    quality_score=10,
                ),
            }
        ]
    )
    assert any(c["prompt"] == expected_rewrite for c in calls)
    assert all(c["kwargs"]["model"] == MODEL for c in calls)
    assert not any("You are a support assistant" in c["prompt"] for c in calls)


def test_stream_pipeline_recovery_preserves_codex_answer_attribution(
    monkeypatch, client, tmp_path, fake_codex
):
    from api.routers import conversation

    runtime._FAILOVER_CACHE_UNTIL.clear()
    calls = []
    _setup(
        monkeypatch, tmp_path, fake_codex, "codex-answer", calls, "complex", False, routing=False
    )

    def unavailable_stream_prompt(*args, **kwargs):
        raise RuntimeError("fixture stream path unavailable")

    monkeypatch.setattr(conversation, "_fit_stream_prompt", unavailable_stream_prompt)
    body, _ = _request(client, "/api/ask/stream")
    assert body["answer"] == ANSWER, body
    assert (body["answer_provider"], body["answer_model"]) == ("codex", "gpt-6-astra")
    assert len(fake_codex.records()) == 1
    assert calls and all(c["kwargs"]["model"] == MODEL for c in calls)
