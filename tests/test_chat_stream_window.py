"""The web chat stream fits its prompt into the local model window.

The real ProviderBackedLLM/OllamaProvider pair runs; only the langchain Ollama
binding is a recording fake. Before this, five parent-expanded Russian chunks
went to Ollama whole: about 5,700 tokens against num_ctx 4096, and Ollama
dropped the beginning of the prompt (instructions, first sources) silently.
"""

from __future__ import annotations

import importlib
import json
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from llm.providers.base import ProviderBackedLLM
from llm.providers.ollama import OllamaProvider

api_app = importlib.import_module("api.app")

CLIENT_SETTINGS_OVERRIDES = {
    "streaming_enabled": True,
}

QUESTION = "Как подать претензию о повреждении груза?"
ANSWER_TOKENS = ("Претензию ", "подают ", "письменно [1].")
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


class _Retriever:
    def get_relevant_documents(self, question: str):
        _ = question
        return [_retrieved(index) for index in range(1, 6)]


class _Session:
    def __init__(self, llm) -> None:
        self._retriever = _Retriever()
        self._llm = llm
        self.history: list[dict[str, str]] = []

    def ask(
        self, question: str, trace_id: str | None = None, tenant_id: str = "default", **kwargs
    ) -> dict:
        _ = question, trace_id, tenant_id, kwargs
        return {
            "answer": "fallback",
            "quality_score": 50,
            "route": "auto",
            "graded_docs": [],
            "trace_id": "trace-window-fallback",
        }


def _binding_module(calls: list[dict]) -> types.ModuleType:
    class Binding:
        def __init__(self, **kwargs):
            self.call = {"kwargs": kwargs}
            calls.append(self.call)

        def invoke(self, prompt):
            self.call.update(method="invoke", prompt=prompt)
            return "85"

        def stream(self, prompt):
            self.call.update(method="stream", prompt=prompt)
            yield "85"

        async def astream(self, prompt):
            self.call.update(method="astream", prompt=prompt)
            for token in ANSWER_TOKENS:
                yield token

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    return module


def _events(payload: str) -> list[dict]:
    return [json.loads(chunk[6:]) for chunk in payload.split("\n\n") if chunk.startswith("data: ")]


def _stream(client: TestClient, monkeypatch: pytest.MonkeyPatch, llm, path: str) -> list[dict]:
    async def _session(session_id, tenant_id="default"):
        return (session_id or "session-window", _Session(llm))

    monkeypatch.setattr(api_app, "_get_or_create_session", _session)
    response = client.post(
        path, json={"question": QUESTION}, headers={"Accept": "text/event-stream"}
    )
    assert response.status_code == 200
    return _events(response.text)


@pytest.mark.parametrize("path", ["/api/chat/stream", "/api/ask/stream"])
def test_stream_prompt_fits_the_ollama_window(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
):
    calls: list[dict] = []
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding_module(calls))
    llm = ProviderBackedLLM(
        OllamaProvider(
            model_name="qwen2.5:7b",
            base_url="http://ollama.test",
            timeout_sec=60,
            input_price_per_1m_tokens=0,
            output_price_per_1m_tokens=0,
        )
    )

    events = _stream(client, monkeypatch, llm, path)

    result = next(event for event in events if event.get("type") == "result")
    assert result["answer"] == "".join(ANSWER_TOKENS)
    (generate_call,) = [call for call in calls if call.get("method") == "astream"]
    # After the answer come the self-eval and, on an "auto" route, the
    # suggested questions: two more model calls before the result event.
    eval_call = next(call for call in calls if call.get("method") in ("invoke", "stream"))
    prompt = generate_call["prompt"]
    # The instructions and the question survive; the tail of the ranking does not.
    assert QUESTION in prompt
    assert "[Документ 1 | source=rules-1.md]" in prompt
    assert "rules-5.md" not in prompt
    assert generate_call["kwargs"]["num_ctx"] == 4096
    assert generate_call["kwargs"]["num_predict"] == 1024

    from llm.providers.base import estimate_window_tokens, window_input_limit

    assert estimate_window_tokens(prompt) <= window_input_limit(4096, 1024)
    # Sources and citations name exactly the documents the model was given.
    citations = result["citations"]
    assert 1 <= len(citations) < 5
    assert [item["doc_id"] for item in citations] == [
        f"doc-{i}" for i in range(1, len(citations) + 1)
    ]
    assert all(source["page_content"] in prompt for source in result["sources"])
    # The self-eval call runs with the evaluate role's output budget, fitted to it.
    assert eval_call["kwargs"]["num_predict"] == 128
    assert estimate_window_tokens(eval_call["prompt"]) <= window_input_limit(4096, 128)
    assert (result["quality_score"], result["quality_source"]) == (85, "llm")


def test_model_without_a_declared_window_still_gets_every_document(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, object] = {}

    class _StreamingLLM:
        supports_streaming = True

        async def generate_stream(self, messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            captured["kwargs"] = kwargs
            for token in ANSWER_TOKENS:
                yield token

    events = _stream(client, monkeypatch, _StreamingLLM(), "/api/chat/stream")

    result = next(event for event in events if event.get("type") == "result")
    assert result["answer"] == "".join(ANSWER_TOKENS)
    assert "rules-5.md" in captured["prompt"]
    assert len(result["citations"]) == 5
    assert captured["kwargs"] == {"temperature": 0.2, "max_tokens": 1024}


def test_long_history_gives_way_before_the_documents():
    from api.routers.conversation import _fit_stream_prompt
    from llm.providers.base import estimate_window_tokens, window_input_limit

    history = [
        {
            "role": "user" if turn % 2 == 0 else "assistant",
            "content": f"Реплика {turn}. " + " ".join(_SENTENCES) * 6,
        }
        for turn in range(6)
    ]
    docs = [{"page_content": _retrieved(1).page_content, "metadata": {"source": "rules-1.md"}}]

    prompt, fitted = _fit_stream_prompt(
        SimpleNamespace(context_window=4096), QUESTION, docs, history
    )

    assert estimate_window_tokens(prompt) <= window_input_limit(4096, 1024)
    assert "Реплика 5." in prompt
    assert "Реплика 1." not in prompt
    # The top document stays whole; old turns made room for it.
    assert fitted == docs
