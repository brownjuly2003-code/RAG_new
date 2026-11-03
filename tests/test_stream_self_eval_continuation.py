"""The web chat's self-eval as the next turn of the answer's own chat (stage 4, step 2).

llama-server reads again only what follows the prefix its slot cached, and the classic
self-eval prompt shares 5-7 tokens with the answer's (docs/evidence/stage4-step0-record.md).
In mode ``continuation`` (STREAMING_SELF_EVAL_MODE) the self-eval sends the exact string
the answer call sent, the answer as the stream delivered it and a request for the score
as one chat, to the server, model and num_ctx that streamed the answer; mode ``both``
scores by it and reads the classic self-eval after it, for a registered comparison;
``classic``, the default, is the self-eval as it was. A stream from anything but an
Ollama path, an input num_ctx cannot hold with the score, a failed call or a reply that is
not one integer from 1 to 100 keeps the classic self-eval. Where it can, the real
ProviderBackedLLM/OllamaProvider pair runs and only the langchain binding and the
``/api/chat`` transport are recording fakes. The client fixture and the session stand-in
follow tests/test_chat_stream_window.py.
"""

from __future__ import annotations

import asyncio
import dataclasses
import importlib
import json
import logging
import sys
import types
from collections.abc import AsyncIterator, Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from agent.prompts import PROMPT_REGISTRY, build_self_eval_continuation_prompt
from api.routers import conversation
from config.settings import Settings
from llm.providers import ollama as ollama_module
from llm.providers.base import (
    LLMResponse,
    ProviderBackedLLM,
    estimate_window_tokens,
    flatten_messages,
    window_input_limit,
)
from llm.providers.ollama import OllamaProvider
from tests import _fake_ollama

api_app = importlib.import_module("api.app")

CLIENT_SETTINGS_OVERRIDES = {
    "streaming_enabled": True,
}

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
QUESTION = "How is a warranty claim filed?"
ANSWER_TOKENS = ("A claim ", "is filed ", "in writing [1].")
ANSWER = "".join(ANSWER_TOKENS)
DOCS = (
    ("warranty.md", "A warranty claim is filed in writing within 30 days of purchase."),
    ("returns.md", "Returned goods travel in their original packaging with the receipt."),
)
SUGGESTIONS = ["Which papers go with a claim?", "How long is the review?", "Where is it sent?"]
# Ollama's counters of the continuation call as /api/chat reports them (nanoseconds).
COUNTERS = {
    "prompt_eval_count": 2301,
    "prompt_eval_duration": 1_200_000_000,
    "eval_count": 2,
    "eval_duration": 150_000_000,
}
# Templates of the classic self-eval and of the suggestions (agent/prompts.py).
SELF_EVAL_MARKER = "rating the quality of assistant answers"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
ENTRY_KEYS = {"score", "sec", "prompt_tokens", "prompt_sec", "eval_tokens", "eval_sec"}
# The result event's keys as they were: every mode but ``both`` keeps exactly these.
RESULT_KEYS = {
    "type",
    "answer",
    "answer_provider",
    "answer_model",
    "answer_source",
    "generation_source",
    "quality_score",
    "quality_source",
    "route",
    "session_id",
    "sources",
    "citations",
    "trace_id",
    "suggested_questions",
}
# The fields of the continuation's request: no format, system, tools, raw, template,
# suffix, context or keep_alive (the answer's calls send no keep_alive).
CHAT_FIELDS = {"model", "messages", "stream", "think", "options"}


def _kind(prompt: str) -> str:
    if SELF_EVAL_MARKER in prompt:
        return "classic"
    if SUGGESTIONS_MARKER in prompt:
        return "suggestions"
    return "other"


def _reply(kind: str, classic_reply: str) -> str:
    return {"classic": classic_reply, "suggestions": "\n".join(SUGGESTIONS)}.get(kind, "")


class _Retriever:
    def get_relevant_documents(self, question: str) -> list[SimpleNamespace]:
        _ = question
        return [
            SimpleNamespace(
                page_content=text, metadata={"source": source, "doc_id": f"doc-{index}"}
            )
            for index, (source, text) in enumerate(DOCS, start=1)
        ]


class _Session:
    def __init__(self, llm: Any) -> None:
        self._retriever = _Retriever()
        self._llm = llm
        self.history: list[dict[str, str]] = []

    def ask(
        self, question: str, trace_id: str | None = None, tenant_id: str = "default", **kwargs: Any
    ) -> dict[str, Any]:
        _ = question, trace_id, tenant_id, kwargs
        return {
            "answer": "fallback",
            "quality_score": 50,
            "route": "auto",
            "graded_docs": [],
            "trace_id": "trace-continuation-fallback",
        }


def _binding_module(
    calls: list[dict[str, Any]],
    classic_reply: str,
    answer_tokens: tuple[str, ...] = ANSWER_TOKENS,
) -> types.ModuleType:
    """A recording langchain Ollama binding: the answer streams, the rest by prompt."""

    class Binding:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def _once(self, method: str, prompt: str) -> str:
            kind = _kind(prompt)
            calls.append({"call": kind, "method": method, "prompt": prompt, "kwargs": self.kwargs})
            return _reply(kind, classic_reply)

        def invoke(self, prompt: str) -> str:
            return self._once("invoke", prompt)

        def stream(self, prompt: str) -> Iterator[str]:
            yield self._once("stream", prompt)

        async def astream(self, prompt: str) -> AsyncIterator[str]:
            calls.append(
                {"call": "answer", "method": "astream", "prompt": prompt, "kwargs": self.kwargs}
            )
            for token in answer_tokens:
                yield token

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    return module


def _chat_transport(calls: list[dict[str, Any]], *, reply: str, error: BaseException | None) -> Any:
    """A recording stand-in for ``llm.providers.ollama._post_chat``."""

    def _post_chat(url: str, payload: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
        calls.append(
            {"call": "continuation", "url": url, "payload": payload, "timeout_sec": timeout_sec}
        )
        if error is not None:
            raise error
        return {
            "model": payload["model"],
            "message": {"role": "assistant", "content": reply},
            "done": True,
            "done_reason": "stop",
            **COUNTERS,
        }

    return _post_chat


def _provider(**overrides: Any) -> OllamaProvider:
    values: dict[str, Any] = {
        "model_name": MODEL,
        "base_url": "http://ollama.test",
        "timeout_sec": 60,
        "input_price_per_1m_tokens": 0,
        "output_price_per_1m_tokens": 0,
    }
    values.update(overrides)
    return OllamaProvider(**values)


def _ollama_stack(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    *,
    chat_reply: str = "91",
    chat_error: BaseException | None = None,
    classic_reply: str = "85",
    answer_tokens: tuple[str, ...] = ANSWER_TOKENS,
) -> ProviderBackedLLM:
    """The production pair: only the binding and the /api/chat transport are fakes."""
    monkeypatch.setitem(
        sys.modules, "langchain_ollama", _binding_module(calls, classic_reply, answer_tokens)
    )
    monkeypatch.setattr(
        ollama_module, "_post_chat", _chat_transport(calls, reply=chat_reply, error=chat_error)
    )
    return ProviderBackedLLM(_provider())


class _Streamer:
    """A provider-path model that streams the answer and is no Ollama provider."""

    supports_streaming = True
    context_window = 4096

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    async def generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        self.calls.append({"call": "answer", "messages": messages, "kwargs": kwargs})
        for token in ANSWER_TOKENS:
            yield token


class _ChatStreamer(_Streamer):
    """The same model with a chat of its own; a call to it is recorded."""

    def generate_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        self.calls.append({"call": "continuation", "messages": messages, "kwargs": kwargs})
        return LLMResponse(text="91", provider="fake", model="fake")


class _Judge:
    """The session's model, without a stream or a window: the classic self-eval, the hints."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        kind = _kind(prompt)
        self.calls.append({"call": kind, "prompt": prompt, "kwargs": kwargs})
        return _reply(kind, "85")


class _StreamOnlyProvider:
    """A provider with a stream and without a chat continuation: another vendor's, say."""

    provider_id = "other"
    model_name = "other-model"
    context_window = 32768

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    def generate(
        self, messages: list[dict[str, Any]], tools: Any = None, **kwargs: Any
    ) -> LLMResponse:
        _ = tools
        prompt = flatten_messages(messages)
        kind = _kind(prompt)
        self.calls.append({"call": kind, "prompt": prompt, "kwargs": kwargs})
        return LLMResponse(
            text=_reply(kind, "85"), provider=self.provider_id, model=self.model_name
        )

    async def generate_stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        self.calls.append({"call": "answer", "messages": messages, "kwargs": kwargs})
        for token in ANSWER_TOKENS:
            yield token


@pytest.fixture
def calls() -> list[dict[str, Any]]:
    """Every model call of one request, in order, by what it was."""
    return []


def _set_setting(monkeypatch: pytest.MonkeyPatch, name: str, value: Any) -> None:
    # The client fixture's settings: what ask_stream reads on each request.
    monkeypatch.setattr(api_app.get_settings(), name, value, raising=False)


def _set_mode(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    _set_setting(monkeypatch, "streaming_self_eval_mode", mode)


def _serve_stream(monkeypatch: pytest.MonkeyPatch, streamer: Any) -> None:
    # The provider runtime's strong model streams when the session's model cannot.
    monkeypatch.setattr(
        api_app,
        "_build_provider_runtime",
        lambda settings: SimpleNamespace(strong=streamer, fast=None),
    )


def _stream(client: TestClient, monkeypatch: pytest.MonkeyPatch, llm: Any) -> list[dict]:
    async def _session(session_id: str | None, tenant_id: str = "default") -> tuple[str, Any]:
        _ = tenant_id
        return (session_id or "session-continuation", _Session(llm))

    monkeypatch.setattr(api_app, "_get_or_create_session", _session)
    response = client.post(
        "/api/ask/stream", json={"question": QUESTION}, headers={"Accept": "text/event-stream"}
    )
    assert response.status_code == 200
    return [
        json.loads(chunk[6:]) for chunk in response.text.split("\n\n") if chunk.startswith("data: ")
    ]


def _result(events: list[dict], answer: str = ANSWER) -> dict[str, Any]:
    (result,) = [event for event in events if event.get("type") == "result"]
    # The stream answered, not the synchronous fallback.
    assert (result["answer"], result["generation_source"]) == (answer, "stream")
    return result


def _self_eval_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "api.routers.conversation"
        and record.getMessage().startswith("Streaming self-eval call=")
    ]


def _fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split()[2:])


def test_continuation_sends_the_answers_own_chat(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]
) -> None:
    llm = _ollama_stack(monkeypatch, calls)
    _set_mode(monkeypatch, "continuation")

    events = _stream(client, monkeypatch, llm)
    result = _result(events)

    assert [call["call"] for call in calls] == ["answer", "continuation", "suggestions"]
    answer_call, continuation = calls[0], calls[1]
    payload = continuation["payload"]
    # The exact string the answer call sent to Ollama, the streamed answer, the request.
    assert payload["messages"] == [
        {"role": "user", "content": answer_call["prompt"]},
        {"role": "assistant", "content": ANSWER},
        {"role": "user", "content": build_self_eval_continuation_prompt()},
    ]
    assert answer_call["prompt"].startswith("USER:\n")
    # The answer call's server, model and window (another num_ctx reloads the model),
    # the evaluate role's limits, thinking off, one reply, the provider's own timeout.
    assert continuation["url"] == "http://ollama.test/api/chat"
    assert payload["model"] == answer_call["kwargs"]["model"] == MODEL
    assert payload["options"] == {
        "num_ctx": answer_call["kwargs"]["num_ctx"],
        "num_predict": 128,
        "temperature": 0.0,
    }
    assert (payload["stream"], payload["think"]) == (False, False)
    assert set(payload) == CHAT_FIELDS
    assert continuation["timeout_sec"] == 60.0
    # Its reply is the badge and the route: 91 clears the threshold of 80.
    assert (result["quality_score"], result["quality_source"], result["route"]) == (
        91,
        "llm",
        "auto",
    )
    # The suggestions follow the result in their own event (PLAN.md stage 4, item 4).
    assert result["suggested_questions"] == []
    assert events[-1] == {"type": "suggestions", "suggested_questions": SUGGESTIONS}
    assert set(result) == RESULT_KEYS


def test_both_scores_by_the_continuation_then_reads_the_classic(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="api.routers.conversation")
    llm = _ollama_stack(monkeypatch, calls, chat_reply="91", classic_reply="62")
    _set_mode(monkeypatch, "both")

    result = _result(_stream(client, monkeypatch, llm))

    # The classic prompt would overwrite the cached prefix: it comes second.
    assert [call["call"] for call in calls] == [
        "answer",
        "continuation",
        "classic",
        "suggestions",
    ]
    # The continuation's 91 drives the badge and the route; the classic 62 is recorded.
    assert (result["quality_score"], result["quality_source"], result["route"]) == (
        91,
        "llm",
        "auto",
    )
    assert set(result) == RESULT_KEYS | {"self_eval_both"}
    both = result["self_eval_both"]
    assert set(both) == {"continuation", "classic"}
    for entry in both.values():
        assert set(entry) == ENTRY_KEYS
        assert isinstance(entry["sec"], float) and entry["sec"] >= 0.0
    assert {key: value for key, value in both["continuation"].items() if key != "sec"} == {
        "score": 91,
        "prompt_tokens": 2301,
        "prompt_sec": 1.2,
        "eval_tokens": 2,
        "eval_sec": 0.15,
    }
    # The classic call reports no counters of its own.
    assert {key: value for key, value in both["classic"].items() if key != "sec"} == {
        "score": 62,
        "prompt_tokens": None,
        "prompt_sec": None,
        "eval_tokens": None,
        "eval_sec": None,
    }

    # One INFO line per call, numbers only.
    lines = _self_eval_lines(caplog)
    continuation_line, classic_line = (_fields(line) for line in lines)
    assert (continuation_line["call"], classic_line["call"]) == ("continuation", "classic")
    assert (continuation_line["mode"], classic_line["mode"]) == ("both", "both")
    assert (continuation_line["score"], classic_line["score"]) == ("91", "62")
    sent = calls[1]["payload"]["messages"]
    assert continuation_line["est_input_tokens"] == str(
        estimate_window_tokens(flatten_messages(sent))
    )
    assert classic_line["est_input_tokens"] == str(estimate_window_tokens(calls[2]["prompt"]))
    counters = ("prompt_tokens", "prompt_sec", "eval_tokens", "eval_sec")
    assert [continuation_line[key] for key in counters] == ["2301", "1.2", "2", "0.15"]
    assert [classic_line[key] for key in counters] == ["None"] * 4
    texts = [QUESTION, ANSWER, *(text for _, text in DOCS)]
    assert not [line for line in lines for text in texts if text in line]


def test_the_assistant_turn_is_the_answer_as_the_stream_delivered_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]
) -> None:
    tokens = ("  A claim  is filed", " in writing [1] [2].", "\n")
    streamed = "".join(tokens)
    llm = _ollama_stack(monkeypatch, calls, classic_reply="62", answer_tokens=tokens)
    _set_mode(monkeypatch, "both")

    result = _result(_stream(client, monkeypatch, llm), answer=streamed)

    assert [call["call"] for call in calls] == [
        "answer",
        "continuation",
        "classic",
        "suggestions",
    ]
    # Byte for byte: the citations, the double spaces, the edge whitespace stay.
    assert calls[1]["payload"]["messages"][1] == {"role": "assistant", "content": streamed}
    # The classic self-eval still reads its own cleaned copy, as before.
    assert "A claim is filed in writing." in calls[2]["prompt"]
    assert streamed.strip() not in calls[2]["prompt"]
    assert (result["quality_score"], result["quality_source"]) == (91, "llm")


@pytest.mark.parametrize("mode", [None, "classic", "turbo"])
def test_classic_and_the_default_make_no_chat_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    mode: str | None,
) -> None:
    llm = _ollama_stack(monkeypatch, calls)

    def _no_chat(self: Any, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        _ = self, messages, kwargs
        calls.append({"call": "generate_chat"})
        raise AssertionError("mode classic sends no chat")

    monkeypatch.setattr(ProviderBackedLLM, "generate_chat", _no_chat)
    monkeypatch.setattr(OllamaProvider, "generate_chat", _no_chat)
    if mode is None:
        # The default: the field's own with no STREAMING_SELF_EVAL_MODE set,
        # whatever the environment the client's settings were built in.
        monkeypatch.delenv("STREAMING_SELF_EVAL_MODE", raising=False)
        _set_mode(monkeypatch, _mode_from_env())
    else:
        # An unknown value falls back to classic.
        _set_mode(monkeypatch, mode)

    result = _result(_stream(client, monkeypatch, llm))

    assert [call["call"] for call in calls] == ["answer", "classic", "suggestions"]
    assert (result["quality_score"], result["quality_source"], result["route"]) == (
        85,
        "llm",
        "auto",
    )
    assert set(result) == RESULT_KEYS


@pytest.mark.parametrize("mode", ["continuation", "both"])
@pytest.mark.parametrize("failure", ["call fails", "no number", "not one integer"])
def test_a_failed_or_unscored_continuation_keeps_the_classic_score(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    mode: str,
    failure: str,
) -> None:
    if failure == "call fails":
        llm = _ollama_stack(monkeypatch, calls, chat_error=httpx.ConnectError("refused"))
    elif failure == "no number":
        llm = _ollama_stack(monkeypatch, calls, chat_reply="I would rather not say.")
    else:
        # The classic parse would read 80; the continuation's takes one integer only.
        llm = _ollama_stack(monkeypatch, calls, chat_reply="80/100")
    _set_mode(monkeypatch, mode)

    result = _result(_stream(client, monkeypatch, llm))

    assert [call["call"] for call in calls] == [
        "answer",
        "continuation",
        "classic",
        "suggestions",
    ]
    assert (result["quality_score"], result["quality_source"], result["route"]) == (
        85,
        "llm",
        "auto",
    )
    if mode == "both":
        both = result["self_eval_both"]
        assert (both["continuation"]["score"], both["classic"]["score"]) == (-1, 85)
    else:
        assert set(result) == RESULT_KEYS


def test_an_input_the_window_cannot_hold_keeps_the_classic_score(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]
) -> None:
    # Digits weigh one token each: the answer alone outgrows num_ctx 4096.
    long_answer = "7" * 4000
    _serve_stream(monkeypatch, _ollama_stack(monkeypatch, calls, answer_tokens=(long_answer,)))
    _set_mode(monkeypatch, "continuation")

    result = _result(_stream(client, monkeypatch, _Judge(calls)), answer=long_answer)

    # No request: Ollama would have dropped the first message, the context, without an error.
    assert [call["call"] for call in calls] == ["answer", "classic", "suggestions"]
    assert (result["quality_score"], result["quality_source"]) == (85, "llm")
    messages = conversation._continuation_self_eval_messages(
        calls[0]["prompt"], long_answer, build_self_eval_continuation_prompt()
    )
    assert estimate_window_tokens(flatten_messages(messages)) + 128 > calls[0]["kwargs"]["num_ctx"]


@pytest.mark.parametrize(
    "streamer", ["a model of its own", "the same with a chat", "another provider in the wrapper"]
)
def test_a_stream_from_no_ollama_provider_keeps_the_classic_score(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    streamer: str,
) -> None:
    models = {
        "a model of its own": lambda: _Streamer(calls),
        "the same with a chat": lambda: _ChatStreamer(calls),
        "another provider in the wrapper": lambda: ProviderBackedLLM(_StreamOnlyProvider(calls)),
    }
    _serve_stream(monkeypatch, models[streamer]())
    _set_mode(monkeypatch, "continuation")

    result = _result(_stream(client, monkeypatch, _Judge(calls)))

    # No slot of Ollama's holds this prefix: not even a model with a chat is asked.
    assert [call["call"] for call in calls] == ["answer", "classic", "suggestions"]
    assert (result["quality_score"], result["quality_source"]) == (85, "llm")


def test_the_continuation_goes_to_the_server_and_model_that_streamed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]
) -> None:
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding_module(calls, "85"))
    monkeypatch.setattr(ollama_module, "_post_chat", _chat_transport(calls, reply="91", error=None))
    # With the fallback cache on, the wrapper's calls go to the fallback; its stream does not.
    streamer = ProviderBackedLLM(
        _provider(),
        fallback_provider=_provider(
            model_name="other-model", base_url="http://other.test", context_window=8192
        ),
        fallback_cache_is_active=lambda: True,
    )
    _serve_stream(monkeypatch, streamer)
    _set_mode(monkeypatch, "continuation")

    result = _result(_stream(client, monkeypatch, _Judge(calls)))

    assert [call["call"] for call in calls] == ["answer", "continuation", "suggestions"]
    answer_call, continuation = calls[0], calls[1]
    assert (answer_call["kwargs"]["base_url"], answer_call["kwargs"]["model"]) == (
        "http://ollama.test",
        MODEL,
    )
    assert continuation["url"] == "http://ollama.test/api/chat"
    assert continuation["payload"]["model"] == MODEL
    assert continuation["payload"]["options"]["num_ctx"] == answer_call["kwargs"]["num_ctx"]
    assert (result["quality_score"], result["quality_source"]) == (91, "llm")


def test_the_raw_fallback_continues_on_the_server_it_streamed_from(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]
) -> None:
    async def _raw_stream(
        prompt: str, model: str, base_url: str, options: dict[str, Any] | None = None
    ) -> AsyncIterator[str]:
        calls.append(
            {
                "call": "answer",
                "prompt": prompt,
                "model": model,
                "base_url": base_url,
                "options": options,
            }
        )
        for token in ANSWER_TOKENS:
            yield token

    # No provider streams: the answer comes from settings' Ollama, as /api/generate.
    monkeypatch.setattr(api_app, "_build_provider_runtime", None)
    monkeypatch.setattr(api_app, "_stream_ollama", _raw_stream)
    monkeypatch.setattr(ollama_module, "_post_chat", _chat_transport(calls, reply="91", error=None))
    _set_setting(monkeypatch, "ollama_context_window", 8192)
    _set_setting(monkeypatch, "ollama_request_timeout_sec", 45.0)
    _set_mode(monkeypatch, "continuation")

    result = _result(_stream(client, monkeypatch, _Judge(calls)))

    assert [call["call"] for call in calls] == ["answer", "continuation", "suggestions"]
    answer_call, continuation = calls[0], calls[1]
    payload = continuation["payload"]
    # The raw call posts the prompt as it is: so does the continuation's first turn.
    assert payload["messages"][:2] == [
        {"role": "user", "content": answer_call["prompt"]},
        {"role": "assistant", "content": ANSWER},
    ]
    assert not payload["messages"][0]["content"].startswith("USER:")
    assert continuation["url"] == answer_call["base_url"] + "/api/chat"
    assert payload["model"] == answer_call["model"] == "test-model"
    assert payload["options"] == {
        "num_ctx": answer_call["options"]["num_ctx"],
        "num_predict": 128,
        "temperature": 0.0,
    }
    assert answer_call["options"]["num_ctx"] == 8192
    assert set(payload) == CHAT_FIELDS
    # The raw stream's own limit, OLLAMA_REQUEST_TIMEOUT_SEC.
    assert continuation["timeout_sec"] == 45.0
    assert (result["quality_score"], result["quality_source"]) == (91, "llm")


def test_quality_eval_off_still_switches_every_self_eval_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]
) -> None:
    llm = _ollama_stack(monkeypatch, calls)
    _set_mode(monkeypatch, "both")
    _set_setting(monkeypatch, "streaming_quality_eval", False)

    result = _result(_stream(client, monkeypatch, llm))

    assert [call["call"] for call in calls] == ["answer", "suggestions"]
    assert (result["quality_score"], result["quality_source"]) == (70, "heuristic")
    assert set(result) == RESULT_KEYS


def test_the_continuation_is_the_answers_turn_the_answer_and_the_request() -> None:
    assert conversation._continuation_self_eval_messages("USER:\nsent", " answer\n", "rate") == [
        {"role": "user", "content": "USER:\nsent"},
        {"role": "assistant", "content": " answer\n"},
        {"role": "user", "content": "rate"},
    ]


PROMPT = "  Context:\n[1 | source=warranty.md]\nClaims are filed in writing.\n\nQuestion: how?\n"


def test_the_provider_stream_sends_the_flattened_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    class Binding:
        def __init__(self, **kwargs: Any) -> None:
            _ = kwargs

        async def astream(self, prompt: str) -> AsyncIterator[str]:
            seen.append(prompt)
            yield "In writing."

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    monkeypatch.setitem(sys.modules, "langchain_ollama", module)
    provider = _provider()

    async def _answer() -> str:
        tokens = provider.generate_stream(
            [{"role": "user", "content": PROMPT}], temperature=0.2, max_tokens=1024
        )
        return "".join([token async for token in tokens])

    assert asyncio.run(_answer()) == "In writing."
    # What the binding sent to Ollama is the continuation's first turn, not the prompt itself.
    assert seen == [conversation._answer_request_text(PROMPT, stream_path="provider")]
    assert seen[0] == "USER:\n" + PROMPT.strip() != PROMPT


def test_the_raw_stream_sends_the_prompt_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_app, "get_settings", lambda: SimpleNamespace(ollama_request_timeout_sec=30.0)
    )

    async def _answer(url: str) -> str:
        tokens = api_app._stream_ollama(PROMPT, MODEL, url, options={"num_ctx": 4096})
        return "".join([token async for token in tokens])

    with _fake_ollama.running(lambda payload: _fake_ollama.Reply(["In writing."])) as server:
        assert asyncio.run(_answer(server.url)) == "In writing."

    (request,) = server.requests
    assert request["path"] == "/api/generate"
    # No prefix and no strip: the leading spaces and the final newline stay.
    assert (
        request["payload"]["prompt"]
        == conversation._answer_request_text(PROMPT, stream_path="raw")
        == PROMPT
    )


def _continue(
    monkeypatch: pytest.MonkeyPatch,
    *,
    answer: str = ANSWER,
    num_ctx: int = 4096,
    stream_path: str | None = "provider",
    reply: str = "91",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One continuation of a provider-path answer; the /api/chat requests it sent."""
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(ollama_module, "_post_chat", _chat_transport(sent, reply=reply, error=None))
    entry = asyncio.run(
        conversation._stream_continuation_self_eval(
            ProviderBackedLLM(_provider(context_window=num_ctx)),
            stream_path=stream_path,
            settings=SimpleNamespace(),
            context_window=num_ctx,
            prompt=PROMPT,
            answer=answer,
            mode="continuation",
        )
    )
    return entry, sent


def _continuation_tokens(answer: str) -> int:
    messages = conversation._continuation_self_eval_messages(
        conversation._answer_request_text(PROMPT, stream_path="provider"),
        answer,
        build_self_eval_continuation_prompt(),
    )
    return estimate_window_tokens(flatten_messages(messages))


def test_the_continuation_must_fit_the_answers_num_ctx(monkeypatch: pytest.MonkeyPatch) -> None:
    num_ctx = 1024
    limit = window_input_limit(num_ctx, 128)
    # Digits weigh one token each: the shortest answer of sevens past the limit.
    over = next(n for n in range(1, num_ctx) if _continuation_tokens("7" * n) > limit)

    entry, sent = _continue(monkeypatch, answer="7" * (over - 1), num_ctx=num_ctx)
    assert (entry["score"], len(sent)) == (91, 1)
    assert sent[0]["payload"]["options"]["num_ctx"] == num_ctx

    # Inside num_ctx with the score, past the margin the estimate and the template keep:
    # no request, as OllamaProvider._window_kwargs would refuse it.
    assert _continuation_tokens("7" * over) + 128 <= num_ctx
    entry, sent = _continue(monkeypatch, answer="7" * over, num_ctx=num_ctx)
    assert (entry["score"], sent) == (-1, [])

    # The turns and the score past num_ctx itself.
    assert _continuation_tokens("7" * num_ctx) + 128 > num_ctx
    entry, sent = _continue(monkeypatch, answer="7" * num_ctx, num_ctx=num_ctx)
    assert (entry["score"], sent) == (-1, [])


@pytest.mark.parametrize("num_ctx", [512, 1024, 4096, 8192, 32768])
def test_the_continuation_limit_leaves_the_score_room_in_num_ctx(num_ctx: int) -> None:
    limit = conversation._continuation_input_limit(num_ctx, 128)

    assert limit + 128 <= num_ctx
    # The provider's own rule: what passes here passes OllamaProvider._window_kwargs.
    assert limit == window_input_limit(num_ctx, 128)


def test_a_window_smaller_than_the_score_takes_no_continuation() -> None:
    assert conversation._continuation_input_limit(100, 128) < 0


@pytest.mark.parametrize("stream_path", [None, "graph"])
def test_an_unknown_stream_path_sends_no_continuation(
    monkeypatch: pytest.MonkeyPatch, stream_path: str | None
) -> None:
    entry, sent = _continue(monkeypatch, stream_path=stream_path)

    assert (entry["score"], sent) == (-1, [])
    with pytest.raises(ValueError, match="no Ollama stream path"):
        conversation._answer_request_text(PROMPT, stream_path=stream_path)


@pytest.mark.parametrize(
    ("reply", "score"),
    [("91", 91), (" 91. ", 91), ("100", 100), ("1", 1), ("\n85\n", 85), ("07", 7)],
)
def test_the_continuation_score_is_the_reply_as_one_integer(reply: str, score: int) -> None:
    assert conversation._parse_continuation_score(reply) == score


@pytest.mark.parametrize(
    "reply",
    [
        "80/100",
        "[1] 85",
        "150",
        "0",
        "1000",
        "-5",
        "85.5",
        "85!",
        "8 5",
        "Score: 85",
        "85 out of 100",
        "",
        None,
    ],
)
def test_anything_else_is_no_continuation_score(reply: str | None) -> None:
    assert conversation._parse_continuation_score(reply) == -1


@pytest.mark.parametrize("reply", ["80/100", "[1] 85", "150"])
def test_a_reply_the_strict_parse_refuses_is_no_score_of_a_recorded_call(
    monkeypatch: pytest.MonkeyPatch, reply: str
) -> None:
    entry, sent = _continue(monkeypatch, reply=reply)

    # -1 sends ask_stream to the classic self-eval (the E2E case "not one integer").
    assert (entry["score"], len(sent)) == (-1, 1)
    # The call happened: its counters are recorded all the same.
    assert entry["prompt_tokens"] == COUNTERS["prompt_eval_count"]


def _mode_from_env() -> str:
    (field,) = [
        item for item in dataclasses.fields(Settings) if item.name == "streaming_self_eval_mode"
    ]
    factory = field.default_factory
    assert callable(factory)
    return str(factory())


@pytest.mark.parametrize(
    ("value", "mode"),
    [
        (None, "classic"),
        ("", "classic"),
        ("classic", "classic"),
        ("continuation", "continuation"),
        (" Both ", "both"),
    ],
)
def test_the_setting_reads_streaming_self_eval_mode(
    monkeypatch: pytest.MonkeyPatch, value: str | None, mode: str
) -> None:
    if value is None:
        monkeypatch.delenv("STREAMING_SELF_EVAL_MODE", raising=False)
    else:
        monkeypatch.setenv("STREAMING_SELF_EVAL_MODE", value)

    assert _mode_from_env() == mode


def test_an_unknown_mode_is_classic_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("STREAMING_SELF_EVAL_MODE", "turbo")

    with caplog.at_level(logging.WARNING, logger="config.settings"):
        assert _mode_from_env() == "classic"

    assert any(
        "STREAMING_SELF_EVAL_MODE='turbo'" in record.getMessage() for record in caplog.records
    )


def test_the_continuation_prompt_carries_the_classic_rubric() -> None:
    entry = PROMPT_REGISTRY["self_eval_continuation"]
    text = build_self_eval_continuation_prompt()
    classic = PROMPT_REGISTRY["self_eval"]["text"]

    assert entry["prompt_id"] == "SELF_EVAL_CONTINUATION_V1"
    assert text == entry["text"]
    for line in (
        "- Answer relevance:",
        "- Answer accuracy:",
        "Do not reward an answer that invents facts.",
        "- Retrieval quality:",
        "- Answer language:",
        "Your task is to output ONE INTEGER from 1 to 100,",
        "where 1 is a terrible answer, 50 an average one, 100 an excellent one.",
        "OUTPUT ONLY THE NUMBER, WITHOUT WORDS OR COMMENTS.",
        "Output only an integer from 1 to 100:",
    ):
        assert line in classic and line in text
    # The question, the context and the answer are in the turns before it.
    assert "{" not in text and "QUESTION:" not in text and "CONTEXT:" not in text
    assert "the first message" in text and "your answer above" in text
    # The stream tests tell the two self-evals apart by the classic one's phrase.
    assert SELF_EVAL_MARKER in classic and SELF_EVAL_MARKER not in text


def test_a_self_eval_entry_has_six_keys_and_seconds_from_nanoseconds() -> None:
    entry = conversation._self_eval_entry(91, 0.123456, {**COUNTERS, "total_duration": 9})

    assert entry == {
        "score": 91,
        "sec": 0.123,
        "prompt_tokens": 2301,
        "prompt_sec": 1.2,
        "eval_tokens": 2,
        "eval_sec": 0.15,
    }
    # What a call did not report stays None: the classic call, a failed one, a stray type.
    assert conversation._self_eval_entry(-1, 0.0) == {
        "score": -1,
        "sec": 0.0,
        "prompt_tokens": None,
        "prompt_sec": None,
        "eval_tokens": None,
        "eval_sec": None,
    }
    odd = conversation._self_eval_entry(62, 1.0, {"prompt_eval_count": True, "eval_count": "2"})
    assert (odd["prompt_tokens"], odd["eval_tokens"]) == (None, None)
    # A NaN or infinite counter is none either: the entry never raises past the call.
    bad = {"prompt_eval_count": float("nan"), "eval_duration": float("inf"), "eval_count": 3.0}
    entry = conversation._self_eval_entry(70, 1.0, bad)
    assert (entry["prompt_tokens"], entry["eval_sec"], entry["eval_tokens"]) == (None, None, 3)
