"""``OllamaProvider.generate_chat``: one non-streaming ``/api/chat`` call, messages as they are.

The web chat's self-eval continuation (api/routers/conversation.py) sends the answer's own
prompt, the answer and the request for a score as one chat, so llama-server reads again
only what follows the prefix its slot cached. That holds while the call's options are the
answer call's: another num_ctx reloads the model. Ollama's counters of the call ride on
the response, for the registered comparison of mode ``both``.
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
import types
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
import pytest

from llm.providers import ollama as ollama_module
from llm.providers.base import LLMResponse, ProviderBackedLLM, ProviderCapabilityError
from llm.providers.ollama import OLLAMA_CALL_COUNTERS, OllamaProvider
from llm.request_budget import (
    LLMBudgetExceeded,
    bind_llm_request_budget,
    clear_llm_request_budget,
)
from utils import request_deadline as rd

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MESSAGES = [
    {"role": "user", "content": "USER:\nContext: claims are filed in writing.\n\nQuestion: how?"},
    # Sent as it is: the whitespace a stream left around the answer stays.
    {"role": "assistant", "content": " In writing [1].\n"},
    {"role": "user", "content": "Now rate your answer above on a scale from 1 to 100."},
]
COUNTERS = {
    "prompt_eval_count": 19,
    "prompt_eval_duration": 1_200_000_000,
    "eval_count": 2,
    "eval_duration": 150_000_000,
}
REPLY = {
    "model": MODEL,
    "created_at": "2026-10-28T00:00:00Z",
    "message": {"role": "assistant", "content": "91"},
    "done": True,
    "done_reason": "stop",
    "total_duration": 1_400_000_000,
    **COUNTERS,
}


class _Chat:
    """A recording stand-in for the HTTP call: the url, payload and timeout of each request."""

    def __init__(self, reply: dict[str, Any] | BaseException = REPLY) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []

    def __call__(self, url: str, payload: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
        # A JSON round trip: what would go on the wire, frozen at the call.
        self.requests.append(
            {"url": url, "payload": json.loads(json.dumps(payload)), "timeout_sec": timeout_sec}
        )
        if isinstance(self.reply, BaseException):
            raise self.reply
        return dict(self.reply)


def _provider(**overrides: Any) -> OllamaProvider:
    values: dict[str, Any] = {
        "model_name": MODEL,
        "base_url": "http://ollama.test/",
        "timeout_sec": 60,
        "input_price_per_1m_tokens": 0,
        "output_price_per_1m_tokens": 0,
    }
    values.update(overrides)
    return OllamaProvider(**values)


@pytest.fixture(autouse=True)
def _no_wall_and_no_budget() -> Iterator[None]:
    rd.clear_request_deadline()
    clear_llm_request_budget()
    yield
    rd.clear_request_deadline()
    clear_llm_request_budget()


@pytest.fixture
def chat(monkeypatch: pytest.MonkeyPatch) -> _Chat:
    recorder = _Chat()
    monkeypatch.setattr(ollama_module, "_post_chat", recorder)
    return recorder


def test_the_messages_go_as_they_are_with_the_answer_calls_options(chat: _Chat) -> None:
    response = _provider().generate_chat(MESSAGES, temperature=0.0, max_tokens=128)

    (request,) = chat.requests
    assert request["url"] == "http://ollama.test/api/chat"
    assert request["payload"] == {
        "model": MODEL,
        "messages": MESSAGES,
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096, "num_predict": 128, "temperature": 0.0},
    }
    assert request["timeout_sec"] == 60.0
    assert (response.text, response.provider, response.model) == ("91", "ollama", MODEL)
    assert response.finish_reason == "stop"
    # Ollama's own counters of the call, and only them.
    assert response.metadata == COUNTERS
    assert tuple(response.metadata) == OLLAMA_CALL_COUNTERS


def test_num_ctx_is_the_one_the_answer_stream_sent(
    monkeypatch: pytest.MonkeyPatch, chat: _Chat
) -> None:
    bindings: list[dict[str, Any]] = []

    class Binding:
        def __init__(self, **kwargs: Any) -> None:
            bindings.append(kwargs)

        async def astream(self, prompt: str) -> AsyncIterator[str]:
            _ = prompt
            yield "In writing [1]."

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    monkeypatch.setitem(sys.modules, "langchain_ollama", module)
    provider = _provider(context_window=8192)

    async def _answer() -> str:
        tokens = provider.generate_stream(
            [{"role": "user", "content": "Question?"}], temperature=0.2, max_tokens=1024
        )
        return "".join([token async for token in tokens])

    assert asyncio.run(_answer()) == "In writing [1]."
    provider.generate_chat(MESSAGES, temperature=0.0, max_tokens=128)

    (answer_binding,) = bindings
    options = chat.requests[0]["payload"]["options"]
    assert options["num_ctx"] == answer_binding["num_ctx"] == 8192
    # The option names the answer call set, no others.
    assert set(options) == set(answer_binding) - {"model", "base_url", "timeout"}


def test_counters_ollama_does_not_send_stay_none(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _Chat({"message": {"role": "assistant", "content": "77"}, "done": True})
    monkeypatch.setattr(ollama_module, "_post_chat", chat)

    response = _provider().generate_chat(MESSAGES, max_tokens=128)

    assert response.text == "77"
    assert response.metadata == dict.fromkeys(OLLAMA_CALL_COUNTERS)
    assert response.finish_reason is None
    # Without a temperature none is sent, as on the other calls.
    assert chat.requests[0]["payload"]["options"] == {"num_ctx": 4096, "num_predict": 128}


def test_an_input_the_window_cannot_hold_is_refused_before_any_request(chat: _Chat) -> None:
    # Digits weigh one token each in the estimate: 4,000 against 3,443 left by num_ctx 4096.
    oversized = [{"role": "user", "content": "7" * 4000}, *MESSAGES[1:]]

    with pytest.raises(ValueError, match="exceeds the model input window"):
        _provider().generate_chat(oversized, temperature=0.0, max_tokens=128)

    assert chat.requests == []


def test_the_request_wall_bounds_the_call(chat: _Chat) -> None:
    rd.set_request_deadline(rd.RequestDeadline(expires_at=time.monotonic() + 8.0, source="ask"))

    _provider().generate_chat(MESSAGES, max_tokens=128)

    (request,) = chat.requests
    assert 7.0 < request["timeout_sec"] <= 8.0


def test_an_expired_wall_sends_nothing(chat: _Chat) -> None:
    rd.set_request_deadline(rd.RequestDeadline(expires_at=time.monotonic() - 1.0, source="ask"))

    with pytest.raises(rd.RequestDeadlineExceeded):
        _provider().generate_chat(MESSAGES, max_tokens=128)

    assert chat.requests == []


def test_a_reply_after_the_wall_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def _late(url: str, payload: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
        _ = url, payload, timeout_sec
        rd.set_request_deadline(rd.RequestDeadline(expires_at=0.0, source="ask"))
        return dict(REPLY)

    monkeypatch.setattr(ollama_module, "_post_chat", _late)
    rd.bind_request_deadline(30, source="ask")

    with pytest.raises(rd.RequestDeadlineExceeded):
        _provider().generate_chat(MESSAGES, max_tokens=128)


def test_a_timeout_cut_to_the_wall_is_the_walls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(url: str, payload: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
        _ = url, payload, timeout_sec
        rd.set_request_deadline(rd.RequestDeadline(expires_at=0.0, source="ask"))
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(ollama_module, "_post_chat", _timeout)
    rd.bind_request_deadline(30, source="ask")

    with pytest.raises(rd.RequestDeadlineExceeded):
        _provider().generate_chat(MESSAGES, max_tokens=128)


def test_a_timeout_without_a_wall_stays_the_transports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_module, "_post_chat", _Chat(httpx.ReadTimeout("timed out")))

    with pytest.raises(httpx.ReadTimeout):
        _provider().generate_chat(MESSAGES, max_tokens=128)


def test_a_reply_without_a_message_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_module, "_post_chat", _Chat({"done": True}))

    with pytest.raises(RuntimeError, match="carries no message"):
        _provider().generate_chat(MESSAGES, max_tokens=128)


@contextmanager
def _chat_server(reply: dict[str, Any]) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """A local stand-in for Ollama's ``/api/chat``: one JSON object per request."""
    seen: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            seen.append({"path": self.path, "payload": json.loads(self.rfile.read(length))})
            body = json.dumps(reply).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", seen
    finally:
        server.shutdown()
        server.server_close()


def test_the_call_goes_over_http_to_api_chat() -> None:
    with _chat_server(REPLY) as (url, seen):
        response = _provider(base_url=url).generate_chat(MESSAGES, temperature=0.0, max_tokens=128)

    assert seen == [
        {
            "path": "/api/chat",
            "payload": {
                "model": MODEL,
                "messages": MESSAGES,
                "stream": False,
                "think": False,
                "options": {"num_ctx": 4096, "num_predict": 128, "temperature": 0.0},
            },
        }
    ]
    assert response.text == "91"
    assert response.metadata == COUNTERS


def test_the_router_wrapper_forwards_the_chat_and_charges_the_budget(chat: _Chat) -> None:
    budget = bind_llm_request_budget(max_calls=5)
    assert budget is not None
    llm = ProviderBackedLLM(_provider())

    response = llm.generate_chat(MESSAGES, temperature=0.0, max_tokens=128)

    assert len(chat.requests) == 1
    assert response.metadata == COUNTERS
    assert llm.last_response is response
    assert (budget.calls, budget.input_tokens) == (1, response.input_tokens)


def test_the_router_wrapper_refuses_a_chat_past_the_budget(chat: _Chat) -> None:
    budget = bind_llm_request_budget(max_calls=1)
    assert budget is not None
    budget.calls = 1

    with pytest.raises(LLMBudgetExceeded):
        ProviderBackedLLM(_provider()).generate_chat(MESSAGES, max_tokens=128)

    assert chat.requests == []


def test_the_router_wrapper_refuses_a_chat_past_the_wall(chat: _Chat) -> None:
    rd.set_request_deadline(rd.RequestDeadline(expires_at=time.monotonic() - 1.0, source="ask"))

    with pytest.raises(rd.RequestDeadlineExceeded):
        ProviderBackedLLM(_provider()).generate_chat(MESSAGES, max_tokens=128)

    assert chat.requests == []


def test_the_wrappers_stream_reads_its_primary_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    servers: list[str] = []

    class Binding:
        def __init__(self, **kwargs: Any) -> None:
            servers.append(str(kwargs.get("base_url")))

        async def astream(self, prompt: str) -> AsyncIterator[str]:
            _ = prompt
            yield "In writing."

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    monkeypatch.setitem(sys.modules, "langchain_ollama", module)
    primary = _provider()
    # With the fallback cache on, the wrapper's other calls go to the fallback.
    llm = ProviderBackedLLM(
        primary,
        fallback_provider=_provider(base_url="http://other.test/"),
        fallback_cache_is_active=lambda: True,
    )

    async def _answer() -> str:
        tokens = llm.generate_stream([{"role": "user", "content": "Question?"}], max_tokens=1024)
        return "".join([token async for token in tokens])

    assert asyncio.run(_answer()) == "In writing."
    # The stream read the primary: the provider the self-eval continuation goes to.
    assert servers == ["http://ollama.test/"]
    assert llm.stream_provider is primary


def test_a_provider_without_chat_is_a_capability_error() -> None:
    class _Other:
        provider_id = "other"
        model_name = "other-model"

        def generate(
            self, messages: list[dict[str, Any]], tools: Any = None, **kwargs: Any
        ) -> LLMResponse:
            _ = messages, tools, kwargs
            return LLMResponse(text="", provider=self.provider_id, model=self.model_name)

    with pytest.raises(ProviderCapabilityError, match="chat continuation"):
        ProviderBackedLLM(_Other()).generate_chat(MESSAGES, max_tokens=128)
