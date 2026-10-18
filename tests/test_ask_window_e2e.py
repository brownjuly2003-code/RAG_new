"""/api/ask: every model call of the graph fits the local model's input window.

HTTP -> real ConversationSession graph -> real ProviderBackedLLM/OllamaProvider;
only the langchain Ollama binding is a scripted fake. The provider refuses a
prompt its window cannot hold, and the test records every refusal, so one
unfitted call fails it even where a node swallows the error. Before this,
grading, generation, verification and the judge sent all five parent-expanded
documents and Ollama dropped the beginning of each prompt without an error.
"""

from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace

from agent import graph
from config.settings import Settings
from llm.providers.base import ProviderBackedLLM, estimate_window_tokens, window_input_limit
from llm.providers.ollama import OllamaProvider

QUESTION = "Как подать претензию о повреждении груза?"
ANSWER = "Претензию подают в письменной форме [1]."
_SENTENCES = (
    "Груз принимается к перевозке после проверки документов и взвешивания.",
    "Отправитель отвечает за правильность сведений в авиагрузовой накладной.",
    "Опасные грузы декларируются отдельно и упаковываются по инструкции.",
    "Хранение на складе сверх бесплатного срока оплачивается по тарифу.",
    "Претензия о повреждении груза подаётся в письменной форме.",
)


def _retrieved(index: int) -> SimpleNamespace:
    paragraphs = [
        f"Раздел {index}.{part}. " + " ".join(_SENTENCES[(index + part + k) % 5] for k in range(5))
        for part in range(1, 9)
    ]
    return SimpleNamespace(
        page_content="\n\n".join(paragraphs),
        metadata={
            "source": f"rules-{index}.md",
            "doc_id": f"doc-{index}",
            "title": f"Правила {index}",
        },
    )


def _reply(prompt: str) -> str:
    """The scripted model: one reply per graph prompt, told apart by its template."""
    if "Classify the user question" in prompt:
        return "COMPLEX"
    if "специалист по поисковым запросам" in prompt:
        return "претензия о повреждении груза"
    if "оценке релевантности документов" in prompt:
        if "[1] source=" in prompt:
            return json.dumps({"grades": [{"index": i, "relevant": True} for i in range(1, 6)]})
        return "YES"
    if "ассистент службы поддержки" in prompt:
        return ANSWER
    if "atomic factual claims" in prompt:
        return "- Претензию подают в письменной форме."
    if "fact-checker" in prompt:
        return "SUPPORTED: Претензия о повреждении груза подаётся в письменной форме."
    if "оценке качества ответов" in prompt:
        return '{"score": 90, "reason": "grounded"}'
    return "[]"


def _binding_module(calls: list[dict]) -> types.ModuleType:
    class Binding:
        def __init__(self, **kwargs):
            self.call = {"kwargs": kwargs}
            calls.append(self.call)

        def invoke(self, prompt):
            self.call["prompt"] = prompt
            return _reply(prompt)

        def stream(self, prompt):
            self.call["prompt"] = prompt
            yield _reply(prompt)

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    return module


def test_ask_graph_fits_every_model_call_into_the_window(monkeypatch, client, tmp_path):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from vectordb import manager

    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.agentic_mode = False
    settings.hyde = False
    settings.online_evaluators_enabled = False
    settings.fact_verification_enabled = True
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    from tracing import _base_trace

    _base_trace._init_db()

    calls: list[dict] = []
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding_module(calls))
    # A refused prompt never reaches the binding, and a node may swallow the
    # error; record refusals so none goes unseen.
    refused: list[str] = []
    window_kwargs = OllamaProvider._window_kwargs

    def recording_window_kwargs(self, prompt, kwargs):
        try:
            return window_kwargs(self, prompt, kwargs)
        except ValueError:
            refused.append(prompt[:120])
            raise

    monkeypatch.setattr(OllamaProvider, "_window_kwargs", recording_window_kwargs)
    llm = ProviderBackedLLM(
        OllamaProvider(
            model_name="qwen2.5:7b",
            base_url="http://ollama.test",
            timeout_sec=60,
            input_price_per_1m_tokens=0,
            output_price_per_1m_tokens=0,
        )
    )
    retriever = SimpleNamespace(
        get_relevant_documents=lambda query: [_retrieved(i) for i in range(1, 6)]
    )
    session = graph.ConversationSession(retriever, llm, max_iterations=0)

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["route"] != "error", body
    assert refused == []
    # Grading, generation, fact verification and the judge all called the model.
    for template in (
        "оценке релевантности документов",
        "ассистент службы поддержки",
        "fact-checker",
        "оценке качества ответов",
    ):
        assert any(template in c["prompt"] for c in calls), template
    generate_calls = [c for c in calls if "ассистент службы поддержки" in c["prompt"]]
    assert len(generate_calls) == 1, [c["prompt"][:80] for c in calls]
    prompt = generate_calls[0]["prompt"]
    # The model sees the instructions, the question and the leading sources.
    assert QUESTION in prompt and "[1 | source=rules-1.md]" in prompt
    assert "rules-5.md" not in prompt
    # Every call carries num_ctx and fits what the window leaves for input.
    for call in calls:
        assert call["kwargs"]["num_ctx"] == 4096
        limit = window_input_limit(4096, call["kwargs"]["num_predict"])
        assert estimate_window_tokens(call["prompt"]) <= limit, call["prompt"][:80]
    # The answer cites only documents the model was given.
    citations = body.get("citations") or []
    assert 1 <= len(citations) < 5, body
    assert [c["doc_id"] for c in citations] == [f"doc-{i}" for i in range(1, len(citations) + 1)]
