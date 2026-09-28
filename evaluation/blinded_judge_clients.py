"""Network routes for P2's three independent, blinded judges."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class Reply:
    text: str
    model: str
    usage: dict[str, Any]
    elapsed_s: float


class JudgeUnavailable(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class RateLimited(Exception):
    def __init__(self, reset_at: float | None) -> None:
        self.reset_at = reset_at
        super().__init__("rate limited")


class TransportError(Exception):
    def __init__(self) -> None:
        super().__init__("judge transport error")


_KNOWN_FAILURES = {
    "model_auth_required",
    "authentication_error",
    "permission_error",
    "insufficient_quota",
    "quota_exceeded",
    "rate_limit_exceeded",
    "1308",
    "1310",
}


def _safe_code(value: object) -> str:
    code = str(value or "")
    return code if code in _KNOWN_FAILURES else "remote_failure"


def _reset_at(headers: Any) -> float | None:
    value = headers.get("retry-after") or headers.get("x-ratelimit-reset-requests")
    if not value:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            return parsedate_to_datetime(value).timestamp()
        except (TypeError, ValueError, IndexError):
            return None
    return time.time() + max(0.0, seconds)


def _error(status: int, headers: Any, body: bytes) -> None:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    failure = data.get("failure_code")
    detail = data.get("error")
    if isinstance(detail, dict):
        failure = failure or detail.get("code") or detail.get("type")
    if status == 429 and str(headers.get("x-ratelimit-limit-req-minute", "")) == "0":
        raise JudgeUnavailable("zero_limit", "Judge request limit is zero")
    if status == 429 and failure == "rate_limit_exceeded":
        reset = _reset_at(headers)
        if reset is not None:
            raise RateLimited(reset)
    if failure:
        code = _safe_code(failure)
        if code in _KNOWN_FAILURES:
            raise JudgeUnavailable(code, "Judge rejected the request")
    if status in (401, 403):
        raise JudgeUnavailable(str(status), "Judge authentication or permission failed")
    if status == 429:
        reset = _reset_at(headers)
        if reset is not None:
            raise RateLimited(reset)
        raise JudgeUnavailable("rate_limit", "Judge rate limit has no reset time")
    if status == 503 and failure:
        raise JudgeUnavailable(_safe_code(failure), "Judge is unavailable")
    raise TransportError()


def _open(request: urllib.request.Request, *, timeout: float = 60.0) -> Any:
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        _error(exc.code, exc.headers, exc.read())
        raise AssertionError("unreachable") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TransportError() from None


def _post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], *, timeout: float = 60.0
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    with _open(request, timeout=timeout) as response:
        try:
            data = json.load(response)
        except (UnicodeError, ValueError):
            raise TransportError() from None
    if not isinstance(data, dict):
        raise TransportError()
    failure = data.get("failure_code")
    detail = data.get("error")
    if isinstance(detail, dict):
        failure = failure or detail.get("code") or detail.get("type")
    if failure:
        code = _safe_code(failure)
        if code == "remote_failure":
            raise TransportError()
        raise JudgeUnavailable(code, "Judge rejected the request")
    return data


class SonnetClient:
    route = "GraceKelly POST /api/v1/orchestrate"
    parameters: ClassVar[dict[str, Any]] = {
        "model": "claude-sonnet-5",
        "adapter_hint": "browser",
        "reasoning": True,
        "decompose": False,
    }

    def __init__(self, base: str = "http://127.0.0.1:8011") -> None:
        self.base = base.rstrip("/")

    def grade(self, request_text: str) -> Reply:
        start = time.monotonic()
        data = _post_json(
            self.base + "/api/v1/orchestrate",
            {"prompt": request_text, **self.parameters},
            {},
            timeout=300.0,
        )
        if data.get("failure_code"):
            raise JudgeUnavailable(_safe_code(data["failure_code"]), "Judge is unavailable")
        model = data.get("model")
        model_id = model.get("id") if isinstance(model, dict) else model
        output = data.get("output_text")
        if not isinstance(output, str) or not output.strip() or not isinstance(model_id, str):
            raise TransportError()
        usage = data.get("usage")
        return Reply(
            output, model_id, usage if isinstance(usage, dict) else {}, time.monotonic() - start
        )


class GlmClient:
    route = "direct z.ai /api/anthropic/v1/messages SSE"
    parameters: ClassVar[dict[str, Any]] = {
        "model": "glm-5.3",
        "max_tokens": 48000,
        "thinking": {"type": "enabled", "budget_tokens": 8000},
        "output_config": {"effort": "xhigh"},
        "stream": True,
    }

    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path = settings_path or Path.home() / ".claude-glm" / "settings.json"

    def grade(self, request_text: str) -> Reply:
        try:
            env = json.loads(self.settings_path.read_text(encoding="utf-8"))["env"]
            base = env["ANTHROPIC_BASE_URL"].rstrip("/")
            key = env["ANTHROPIC_AUTH_TOKEN"]
        except (OSError, KeyError, TypeError, ValueError):
            raise JudgeUnavailable("credentials", "GLM settings are unavailable") from None
        if base != "https://api.z.ai/api/anthropic":
            raise JudgeUnavailable("endpoint", "Unexpected GLM endpoint")
        request = urllib.request.Request(
            base + "/v1/messages",
            data=json.dumps(
                {**self.parameters, "messages": [{"role": "user", "content": request_text}]},
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        start = time.monotonic()
        parts: list[str] = []
        model = ""
        usage: dict[str, Any] = {}
        stop_reason = ""
        stopped = False
        with _open(request) as response:
            try:
                for raw in response:
                    if time.monotonic() - start > 600:
                        raise TransportError()
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    kind = event.get("type")
                    if kind == "message_start":
                        message = event.get("message", {})
                        model = message.get("model", "")
                        usage.update(message.get("usage") or {})
                    elif kind == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            parts.append(delta.get("text", ""))
                    elif kind == "message_delta":
                        stop_reason = event.get("delta", {}).get("stop_reason", "")
                        usage.update(event.get("usage") or {})
                    elif kind == "message_stop":
                        stopped = True
                    elif kind == "error":
                        detail = event.get("error", {})
                        code = _safe_code(detail.get("code") if isinstance(detail, dict) else None)
                        if code in _KNOWN_FAILURES:
                            raise JudgeUnavailable(code, "Judge rejected the request")
                        raise TransportError()
            except (UnicodeError, ValueError, KeyError, TypeError, OSError):
                raise TransportError() from None
        if model != "glm-5.3":
            raise JudgeUnavailable("model_mismatch", "GLM returned a different model")
        text = "".join(parts)
        if not stopped or stop_reason != "end_turn" or not text.strip():
            raise TransportError()
        return Reply(text, model, usage, time.monotonic() - start)


class MistralClient:
    route = "Mistral POST /v1/chat/completions"
    parameters: ClassVar[dict[str, Any]] = {
        "model": "mistral-medium-2604",
        "temperature": 0,
        "random_seed": 20260925,
        "response_format": {"type": "json_object"},
        "max_tokens": 4000,
    }

    def __init__(self, key_file: Path) -> None:
        self.key_file = key_file

    def grade(self, request_text: str) -> Reply:
        try:
            match = re.search(
                r"(?<![A-Za-z0-9])[A-Za-z0-9]{32}(?![A-Za-z0-9])",
                self.key_file.read_text(encoding="utf-8"),
            )
        except OSError:
            match = None
        if match is None:
            raise JudgeUnavailable("credentials", "Mistral key is unavailable")
        start = time.monotonic()
        data = _post_json(
            "https://api.mistral.ai/v1/chat/completions",
            {**self.parameters, "messages": [{"role": "user", "content": request_text}]},
            {"Authorization": "Bearer " + match.group(0)},
        )
        try:
            content = data["choices"][0]["message"]["content"]
            model = data["model"]
        except (KeyError, IndexError, TypeError):
            raise TransportError() from None
        if not isinstance(content, str) or not content.strip() or model != self.parameters["model"]:
            raise TransportError()
        usage = data.get("usage")
        return Reply(
            content, model, usage if isinstance(usage, dict) else {}, time.monotonic() - start
        )
