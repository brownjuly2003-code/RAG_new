"""/api/ask/stream: an answer slower than the old time limits reaches the client.

Until 2026-10-15 the code defaults were ``REQUEST_TIMEOUT_SEC`` 30,
``OLLAMA_REQUEST_TIMEOUT_SEC`` 60 and ``STREAMING_TIMEOUT_SEC`` 120. A local
model on the production Mac answers in minutes, so every question of the web
chat ended with route ``timeout`` after 30 s. The owner lifted the three limits
to a ceiling of 3,600 s. The test runs the chat's path on a real ``Settings()``
with none of them in the environment: HTTP -> the stream route -> a real
``ConversationSession`` (a fake retriever and no LLM, as production builds it)
-> the real provider runtime -> langchain-ollama and the ollama client -> HTTP
-> a fake Ollama server in this test. The server is silent for 65 s before the
first token (longer than 30 and 60 s), then streams until 129 s after the
request (longer than 120 s, with two tokens after it). No clock is faked: the
test waits about two minutes, by the owner's decision, in the regular suite.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any

import pytest

from agent import graph
from config.settings import Settings

QUESTION = "Как подать претензию о повреждении груза?"
_WORDS = (
    "Претензию о повреждении груза подают в письменной форме перевозчику "
    "в аэропорту назначения вместе с актом осмотра [1]."
).split()
ANSWER_TOKENS = [word + " " for word in _WORDS[:-1]] + [_WORDS[-1]]
ANSWER = "".join(ANSWER_TOKENS)
# The model "reads the prompt" this long before its first token: past the old
# request deadline (30 s) and the old Ollama read timeout (60 s).
FIRST_TOKEN_AFTER_SEC = 65.0
# 17 tokens 4 s apart: the last at 129 s, the 15th and later past the old
# 120-s stream budget, which would have cut the answer after the 15th.
TOKEN_GAP_SEC = 4.0
SUGGESTIONS = ["Какие документы приложить?", "Сколько ждать ответа?", "Куда отправить акт?"]
# Templates of the stream's two later model calls (agent/prompts.py).
SELF_EVAL_MARKER = "оценке качества ответов"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
LIMIT_ENV = ("REQUEST_TIMEOUT_SEC", "OLLAMA_REQUEST_TIMEOUT_SEC", "STREAMING_TIMEOUT_SEC")
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")


class _FakeOllama(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests: list[dict[str, Any]] = []
        self.answer_sent_after: list[float] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _Handler(BaseHTTPRequestHandler):
    server: _FakeOllama

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:  # noqa: N802
        received = time.monotonic()
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append({"path": self.path, "payload": payload})
        if self.path != "/api/generate":
            self.send_error(404)
            return
        prompt = str(payload.get("prompt") or "")
        try:
            if SELF_EVAL_MARKER in prompt:
                self._stream(payload, ["85"])
            elif SUGGESTIONS_MARKER in prompt:
                self._stream(payload, ["\n".join(SUGGESTIONS)])
            else:
                self._stream(payload, ANSWER_TOKENS, received=received)
        except (BrokenPipeError, ConnectionResetError):
            # The client gave up (the old limits): nothing left to answer.
            return

    def _stream(
        self, payload: dict[str, Any], tokens: list[str], *, received: float | None = None
    ) -> None:
        def line(**fields: Any) -> None:
            body = {"model": payload.get("model"), "created_at": "2026-10-15T00:00:00Z", **fields}
            self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8") + b"\n")
            self.wfile.flush()

        for index, token in enumerate(tokens):
            if received is not None:
                due = received + FIRST_TOKEN_AFTER_SEC + index * TOKEN_GAP_SEC
                time.sleep(max(0.0, due - time.monotonic()))
            if index == 0:
                # Like Ollama, nothing — not even the headers — before the first token.
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
            line(response=token, done=False)
            if received is not None:
                self.server.answer_sent_after.append(time.monotonic() - received)
        line(response="", done=True, done_reason="stop")


@pytest.fixture
def fake_ollama() -> Iterator[_FakeOllama]:
    server = _FakeOllama()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _events(text: str) -> list[dict[str, Any]]:
    return [
        json.loads(chunk[len("data: ") :])
        for chunk in text.split("\n\n")
        if chunk.startswith("data: ")
    ]


def test_stream_answer_slower_than_the_old_limits_arrives(
    monkeypatch, client, tmp_path, fake_ollama
):
    import api.app as api_app
    import config.settings
    from api.routers import conversation

    for name in LIMIT_ENV + PATH_ENV:
        monkeypatch.delenv(name, raising=False)
    # Suggested questions build their client from OLLAMA_HOST, not from the
    # settings' base URL; without it they would reach a real local Ollama.
    monkeypatch.setenv("OLLAMA_HOST", fake_ollama.url)
    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.ollama_base_url = fake_ollama.url
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "_default_breaker", None)
    from tracing import _base_trace

    # The graph fallback, which ends the request when the stream fails, writes a trace.
    _base_trace._init_db()

    documents = [
        SimpleNamespace(
            page_content=f"Раздел {i}. Претензия о повреждении груза подаётся в письменной форме.",
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

    started = time.monotonic()
    response = client.post("/api/ask/stream", json={"question": QUESTION})
    elapsed = time.monotonic() - started

    assert response.status_code == 200, response.text
    events = _events(response.text)
    assert [e for e in events if e.get("type") == "error"] == []
    results = [e for e in events if e.get("type") == "result"]
    assert len(results) == 1, events
    result = results[0]
    assert result["route"] == "auto", result
    assert result["generation_source"] == "stream", result
    # Every token arrived, the two after the old 120-s budget included.
    assert "".join(e["token"] for e in events if e.get("type") == "token") == ANSWER
    assert result["answer"] == ANSWER
    assert (result["quality_source"], result["quality_score"]) == ("llm", 85)
    assert result["suggested_questions"] == SUGGESTIONS
    # One answer request, streamed, never retried: the client waited out the
    # model's silence and the whole stream.
    answer_requests = [
        r["payload"]
        for r in fake_ollama.requests
        if QUESTION in str(r["payload"].get("prompt"))
        and SELF_EVAL_MARKER not in str(r["payload"].get("prompt"))
        and SUGGESTIONS_MARKER not in str(r["payload"].get("prompt"))
    ]
    assert len(answer_requests) == 1, fake_ollama.requests
    assert answer_requests[0]["stream"] is True
    assert {r["path"] for r in fake_ollama.requests} == {"/api/generate"}
    assert len(fake_ollama.answer_sent_after) == len(ANSWER_TOKENS)
    assert fake_ollama.answer_sent_after[0] > 60
    assert fake_ollama.answer_sent_after[-1] > 125
    assert elapsed > 125
