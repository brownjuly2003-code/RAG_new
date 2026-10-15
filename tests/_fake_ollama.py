"""A local stand-in for Ollama's ``/api/generate``, for tests that wait for real.

It streams NDJSON lines as Ollama does and, like Ollama, sends nothing — not
even the headers — before its first token, so a client's read timeout meets
the same silence it meets while a real model reads a long prompt. ``reply``
maps each request's payload to the tokens to send and their timing.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass(frozen=True)
class Reply:
    tokens: list[str]
    # Silence before the first token, then the gap between tokens, in seconds.
    first_token_after: float = 0.0
    token_gap: float = 0.0


class FakeOllama(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, reply: Callable[[dict[str, Any]], Reply]) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.reply = reply
        # One entry per request: path, payload and when each token left, in
        # seconds after the request arrived.
        self.requests: list[dict[str, Any]] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _Handler(BaseHTTPRequestHandler):
    server: FakeOllama

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:  # noqa: N802
        received = time.monotonic()
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        record: dict[str, Any] = {"path": self.path, "payload": payload, "sent_after": []}
        self.server.requests.append(record)
        if self.path != "/api/generate":
            self.send_error(404)
            return
        reply = self.server.reply(payload)
        try:
            for index, token in enumerate(reply.tokens):
                due = received + reply.first_token_after + index * reply.token_gap
                time.sleep(max(0.0, due - time.monotonic()))
                if index == 0:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.end_headers()
                self._line(payload, response=token, done=False)
                record["sent_after"].append(time.monotonic() - received)
            self._line(payload, response="", done=True, done_reason="stop")
        except (BrokenPipeError, ConnectionResetError):
            # The client gave up waiting: nothing left to answer.
            return

    def _line(self, payload: dict[str, Any], **fields: Any) -> None:
        body = {"model": payload.get("model"), "created_at": "2026-10-15T00:00:00Z", **fields}
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8") + b"\n")
        self.wfile.flush()


@contextmanager
def running(reply: Callable[[dict[str, Any]], Reply]) -> Iterator[FakeOllama]:
    server = FakeOllama(reply)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
