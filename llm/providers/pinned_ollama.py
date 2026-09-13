from __future__ import annotations

import hashlib
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any

_DEFAULT_OPTIONS: dict[str, Any] = {"temperature": 0, "seed": 42, "num_ctx": 4096}
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_urlopen: Callable[..., Any] = urllib.request.urlopen
_sleep: Callable[[float], None] = time.sleep
_TRANSPORT_ERRORS = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    OSError,
    http.client.HTTPException,
)
_RESOLVE_TRANSPORT_ERRORS = _TRANSPORT_ERRORS + (
    json.JSONDecodeError,
    UnicodeDecodeError,
)


class OllamaUnreachable(RuntimeError):
    """Transient transport failure talking to the Ollama HTTP API."""


def _open(
    request: urllib.request.Request, timeout: float, opener: Callable[..., Any] | None
) -> Any:
    open_http = opener if opener is not None else _urlopen
    return open_http(request, timeout=timeout)


def _weights_digest(value: object, model: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise RuntimeError(f"Ollama model {model!r} has an invalid weights digest")
    return value


def resolve_ollama_digest(
    base_url: str,
    model: str,
    *,
    timeout: float = 30.0,
    opener: Callable[..., Any] | None = None,
) -> str:
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags", method="GET")
    try:
        with _open(request, timeout, opener) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if int(exc.code) < 500:
            raise RuntimeError(f"Ollama HTTP {exc.code} for model {model!r}") from exc
        raise OllamaUnreachable(f"Ollama model {model!r} is unreachable") from exc
    except _RESOLVE_TRANSPORT_ERRORS as exc:
        raise OllamaUnreachable(f"Ollama model {model!r} is unreachable") from exc
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise RuntimeError(f"Unknown Ollama model {model!r}")
    for entry in models:
        if isinstance(entry, dict) and entry.get("name") == model:
            return _weights_digest(entry.get("digest"), model)
    raise RuntimeError(f"Unknown Ollama model {model!r}")


def _chat_content(payload: object, model: str) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError(f"Ollama model {model!r} returned non-JSON")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"Ollama model {model!r} returned empty content")
    content = message.get("content")
    if not isinstance(content, str) or content == "":
        raise RuntimeError(f"Ollama model {model!r} returned empty content")
    return content


class PinnedOllamaChat:
    def __init__(
        self,
        base_url: str,
        model: str,
        digest: str,
        *,
        options: Mapping[str, Any] | None = None,
        timeout: float = 900.0,
        max_attempts: int = 5,
        backoff_s: float = 10.0,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if _DIGEST_RE.fullmatch(digest) is None:
            raise RuntimeError(f"Ollama model {model!r} has an invalid weights digest")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._digest = digest
        self._options = dict(_DEFAULT_OPTIONS if options is None else options)
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._opener = opener
        self._sleeper = sleeper

    def generation_record(self, format_schema: Mapping[str, Any] | None) -> dict[str, Any]:
        record = dict(self._options)
        record["format_sha256"] = hashlib.sha256(
            json.dumps(format_schema, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        ).hexdigest()
        return record

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        format_schema: Mapping[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [dict(item) for item in messages],
            "stream": False,
            "keep_alive": "30m",
            "options": dict(self._options),
        }
        if format_schema is not None:
            payload["format"] = format_schema
        request = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        content = self._generate(request)
        self._confirm_digest()
        return content

    def _backoff(self) -> None:
        sleeper = self._sleeper if self._sleeper is not None else _sleep
        sleeper(self._backoff_s)

    def _generate(self, request: urllib.request.Request) -> str:
        last_error: BaseException | None = None
        for attempt in range(self._max_attempts):
            try:
                raw = self._post(request)
                try:
                    body = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        f"Ollama model {self._model!r} returned non-JSON",
                    ) from exc
                return _chat_content(body, self._model)
            except RuntimeError:
                raise
            except _TRANSPORT_ERRORS as exc:
                last_error = exc
                if attempt + 1 >= self._max_attempts:
                    break
                self._backoff()
        raise RuntimeError(
            f"Ollama model {self._model!r} failed after {self._max_attempts} attempts",
        ) from last_error

    def _confirm_digest(self) -> None:
        last_error: BaseException | None = None
        for attempt in range(self._max_attempts):
            try:
                actual = resolve_ollama_digest(
                    self._base_url,
                    self._model,
                    opener=self._opener,
                )
            except OllamaUnreachable as exc:
                last_error = exc
                if attempt + 1 >= self._max_attempts:
                    raise
                self._backoff()
                continue
            if actual != self._digest:
                raise RuntimeError(
                    f"Ollama model {self._model!r} weights digest changed "
                    f"from {self._digest} to {actual}",
                )
            return
        raise OllamaUnreachable(
            f"Ollama model {self._model!r} is unreachable",
        ) from last_error

    def _post(self, request: urllib.request.Request) -> bytes:
        try:
            with _open(request, self._timeout, self._opener) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as exc:
            if 500 <= int(exc.code) <= 599:
                raise
            raise RuntimeError(f"Ollama HTTP {exc.code} for model {self._model!r}") from exc
