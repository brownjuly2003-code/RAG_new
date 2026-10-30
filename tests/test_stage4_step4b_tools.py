"""reports/stage4-step4b/tools/window_timing.py: num_ctx 3,584 against 4,096, timed.

docs/specs/stage4-step4b-window-timing.md. The tool's two model calls are held against the
chat's own (/api/ask/stream, a first question, mode classic) at both windows, with only the
langchain binding a recording fake. Its proxy runs with the real OllamaProvider and binding in
front of a fake Ollama that streams in HTTP/1.1 chunks; a block runs whole, in process, against
that fake with the host's probes faked; the series' driver runs with its block process faked;
the gate and the reading read hand-made blocks. No network, Ollama, API or model.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import threading
import types
import urllib.request
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import config.settings as config_settings
from api.routers.conversation import _fit_stream_prompt
from llm.providers.base import ProviderBackedLLM, flatten_messages
from llm.providers.ollama import OllamaProvider
from llm.providers.runtime import clear_provider_runtime_cache

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports" / "stage4-step4b" / "tools" / "window_timing.py"
STEP3 = ROOT / "reports" / "stage4-step3" / "tools" / "step3_reader.py"
STEP4 = ROOT / "reports" / "stage4-step4" / "tools" / "prompt_budget.py"

api_app = importlib.import_module("api.app")

CLIENT_SETTINGS_OVERRIDES = {
    "streaming_enabled": True,
}


def _load(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


wt = _load("window_timing", TOOL)
MODEL = wt.MODEL
STAND = "0123456789abcdef0123456789abcdef01234567"
QUESTION = "How is a damage claim filed?"
WORDS = ("cargo", "claim", "freight", "weight", "storage", "notice", "damage", "tariff")
# Five documents of about 420 estimated tokens each, in paragraphs: the five fit at 4,096 and
# fewer of them at 3,584 (tests/test_stage4_step4_tools.py's archive).
DOCS = [
    {
        "page_content": f"Part {i}. "
        + "\n\n".join(" ".join(WORDS[(i + p + k) % 8] for k in range(55)) + "." for p in range(5)),
        "metadata": {"source": f"doc-{i}.md", "chunk_index": i},
    }
    for i in range(5)
]
# The answer as the model streams it: the citations and the double space the self-evaluation
# drops from it.
ANSWER_TOKENS = ("A claim is filed  in writing [1]", " within thirty days [2].")
ANSWER = "".join(ANSWER_TOKENS)
SELF_EVAL_MARKER = "rating the quality of assistant answers"
HINTS = "Who files it?\nWhen is it due?\nWhere is it sent?"


def _plain() -> list[dict[str, Any]]:
    return [{"page_content": d["page_content"], "metadata": dict(d["metadata"])} for d in DOCS]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _flat(prompt: str) -> str:
    return flatten_messages([{"role": "user", "content": prompt}])


# --- the schedule ---


def test_the_thirteen_are_step_3s_and_the_order_is_abba() -> None:
    tree = ast.parse(STEP3.read_text(encoding="utf-8"))
    (cases,) = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [getattr(t, "id", None) for t in node.targets] == ["CASES"]
    ]
    assert wt.CASES == cases
    blocks = wt.schedule()
    assert [b["block"] for b in blocks] == list(range(1, 27))
    assert [b["window"] for b in blocks[:8]] == [4096, 3584, 3584, 4096, 4096, 3584, 3584, 4096]
    for position, case_id in enumerate(cases, start=1):
        pair = [b for b in blocks if b["position"] == position]
        assert [b["case_id"] for b in pair] == [case_id, case_id]
        assert sorted(b["window"] for b in pair) == [3584, 4096]
        assert [b["order"] for b in pair] == [1, 2]
    firsts = [b["window"] for b in blocks if b["order"] == 1 and b["position"] > 1]
    assert (firsts.count(4096), firsts.count(3584)) == (6, 6)
    assert wt.block_path(Path("out"), 3) == Path("out") / "blocks" / "03-3584.json"


# --- the chat's calls ---


def _binding(calls: list[dict[str, Any]], score: str = "85") -> types.ModuleType:
    """A recording langchain Ollama binding: the answer streams; the self-evaluation and the
    suggested questions come whole."""

    class OllamaLLM:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def _once(self, method: str, prompt: str) -> str:
            calls.append({"method": method, "prompt": prompt, "kwargs": self.kwargs})
            return score if SELF_EVAL_MARKER in prompt else HINTS

        def invoke(self, prompt: str) -> str:
            return self._once("invoke", prompt)

        def stream(self, prompt: str) -> Iterator[str]:
            yield self._once("stream", prompt)

        async def astream(self, prompt: str) -> AsyncIterator[str]:
            calls.append({"method": "astream", "prompt": prompt, "kwargs": self.kwargs})
            for token in ANSWER_TOKENS:
                yield token

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = OllamaLLM
    return module


def _llm(window: int, base_url: str = "http://ollama.test") -> ProviderBackedLLM:
    return ProviderBackedLLM(
        OllamaProvider(
            model_name=MODEL,
            base_url=base_url,
            timeout_sec=60,
            input_price_per_1m_tokens=0,
            output_price_per_1m_tokens=0,
            context_window=window,
        )
    )


class _Retriever:
    def get_relevant_documents(self, question: str) -> list[SimpleNamespace]:
        _ = question
        return [
            SimpleNamespace(page_content=d["page_content"], metadata=dict(d["metadata"]))
            for d in DOCS
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
            "trace_id": "trace-window-fallback",
        }


def _chat(client: TestClient, monkeypatch: pytest.MonkeyPatch, llm: Any) -> dict[str, Any]:
    """The chat's result event of a first question, its session's model the one given."""

    async def _session(session_id: str | None, tenant_id: str = "default") -> tuple[str, Any]:
        _ = tenant_id
        return (session_id or "session-window", _Session(llm))

    monkeypatch.setattr(api_app, "_get_or_create_session", _session)
    response = client.post(
        "/api/ask/stream", json={"question": QUESTION}, headers={"Accept": "text/event-stream"}
    )
    assert response.status_code == 200
    events = [
        json.loads(chunk[6:]) for chunk in response.text.split("\n\n") if chunk.startswith("data: ")
    ]
    (result,) = [event for event in events if event.get("type") == "result"]
    assert result["generation_source"] == "stream"
    return result


def _sent(call: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """A call as the binding received it; the client timeout is the deadline's remainder."""
    assert "timeout" in call["kwargs"]
    kwargs = {key: value for key, value in call["kwargs"].items() if key != "timeout"}
    return call["method"], call["prompt"], kwargs


@pytest.mark.parametrize("window", wt.WINDOWS)
def test_the_tools_calls_are_the_chats(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, window: int
) -> None:
    chat: list[dict[str, Any]] = []
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding(chat))
    result = _chat(client, monkeypatch, _llm(window))
    tool: list[dict[str, Any]] = []
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding(tool))
    got = asyncio.run(wt.chat_calls(_llm(window), api_app.get_settings(), QUESTION, _plain()))
    # The chat's first two calls: the answer, then the classic self-evaluation. The suggested
    # questions follow the result event; the timing has no part of them.
    assert [call["method"] for call in tool] == ["astream", "invoke"]
    assert [_sent(call) for call in tool] == [_sent(call) for call in chat[:2]]
    assert [call["kwargs"]["num_ctx"] for call in tool] == [window, window]
    assert [call["kwargs"]["num_predict"] for call in tool] == [1024, 128]
    numbers = got["numbers"]
    assert numbers["prompt_sha256"] == _digest(chat[0]["prompt"])
    assert numbers["eval_prompt_sha256"] == _digest(chat[1]["prompt"])
    assert (got["answer"], got["raw_eval"]) == (ANSWER, "85")
    assert (numbers["score"], numbers["quality_source"]) == (85, "llm")
    assert (numbers["quality"], numbers["route"]) == (result["quality_score"], result["route"])
    assert numbers["documents"] == len(result["sources"])
    assert numbers["answer_chars"] == len(ANSWER) and not numbers["truncated"]


def test_the_smaller_window_sends_less(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {}
    for window in wt.WINDOWS:
        calls: list[dict[str, Any]] = []
        monkeypatch.setitem(sys.modules, "langchain_ollama", _binding(calls))
        got = asyncio.run(wt.chat_calls(_llm(window), api_app.get_settings(), QUESTION, _plain()))
        prompt, fitted = _fit_stream_prompt(
            SimpleNamespace(context_window=window), QUESTION, _plain(), []
        )
        # The answer's prompt is step 4's fitting at the window, the one its count read.
        assert calls[0]["prompt"] == _flat(prompt)
        assert got["numbers"]["documents"] == len(fitted)
        sent[window] = got["numbers"]
    assert sent[3584]["prompt_est_tokens"] < sent[4096]["prompt_est_tokens"]
    assert sent[3584]["eval_est_tokens"] < sent[4096]["eval_est_tokens"]
    # All five at 4,096; at 3,584 the last is cut to its excerpt.
    assert sent[4096]["documents"] == 5


def test_an_unread_score_keeps_the_chats_heuristic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat: list[dict[str, Any]] = []
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding(chat, score="good"))
    result = _chat(client, monkeypatch, _llm(4096))
    monkeypatch.setitem(sys.modules, "langchain_ollama", _binding([], score="good"))
    got = asyncio.run(wt.chat_calls(_llm(4096), api_app.get_settings(), QUESTION, _plain()))
    numbers = got["numbers"]
    assert (numbers["score"], numbers["quality_source"]) == (-1, "heuristic")
    assert (numbers["quality"], numbers["route"]) == (result["quality_score"], result["route"])


# --- a fake Ollama: chunked streams, counters, /api/ps ---


def _counters(prompt: str, tokens: list[str], load_ns: int) -> dict[str, int]:
    prompt_tokens = len(prompt) // 4
    return {
        "total_duration": load_ns + prompt_tokens * 30_000_000 + len(tokens) * 200_000_000 + 1,
        "load_duration": load_ns,
        "prompt_eval_count": prompt_tokens,
        "prompt_eval_duration": prompt_tokens * 30_000_000,
        "eval_count": len(tokens),
        "eval_duration": len(tokens) * 200_000_000,
    }


class _Ollama(ThreadingHTTPServer):
    """Ollama's endpoints as the tool meets them: /api/generate streams NDJSON lines in HTTP/1.1
    chunks, Ollama's counters on the last; /api/ps holds the model the last call loaded, at its
    num_ctx, until a keep_alive of 0 unloads it; /api/version and /api/tags."""

    daemon_threads = True

    def __init__(self, score: str = "85") -> None:
        super().__init__(("127.0.0.1", 0), _OllamaHandler)
        self.score = score
        self.bodies: list[bytes] = []
        self.counters: list[dict[str, int]] = []
        self.lines: list[int] = []
        self.held: dict[str, Any] | None = None
        self.unloads = 0
        self.keeps = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _OllamaHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _Ollama

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _json(self, value: Any, status: int = 200) -> None:
        data = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _chunk(self, value: dict[str, Any]) -> None:
        data = json.dumps(value).encode("utf-8") + b"\n"
        self.wfile.write(b"%x\r\n" % len(data) + data + b"\r\n")

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/ps":
            self._json({"models": [self.server.held] if self.server.held else []})
        elif self.path == "/api/version":
            self._json({"version": wt.OLLAMA_VERSION})
        elif self.path == "/api/tags":
            self._json({"models": []})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.bodies.append(body)
        payload = json.loads(body)
        if payload.get("keep_alive") == 0 and "prompt" not in payload:
            self.server.unloads += 1
            if not self.server.keeps:
                self.server.held = None
            self._json({"model": payload["model"], "response": "", "done": True})
            return
        window = (payload.get("options") or {}).get("num_ctx")
        load_ns = 50_000_000 if self.server.held else 2_000_000_000
        self.server.held = {
            "name": payload["model"],
            "model": payload["model"],
            "digest": wt.DIGEST,
            "size": 4_000_000_000 + 100_000 * (window or 0),
            "size_vram": 0,
            "context_length": window,
        }
        prompt = payload.get("prompt") or ""
        tokens = [self.server.score] if SELF_EVAL_MARKER in prompt else list(ANSWER_TOKENS)
        counters = _counters(prompt, tokens, load_ns)
        self.server.counters.append(counters)
        self.server.lines.append(len(tokens) + 1)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        line = {"model": payload["model"], "created_at": "2026-10-29T00:00:00Z"}
        for token in tokens:
            self._chunk({**line, "response": token, "done": False})
        self._chunk({**line, "response": "", "done": True, "done_reason": "stop", **counters})
        self.wfile.write(b"0\r\n\r\n")


@contextmanager
def _serving(server: ThreadingHTTPServer) -> Iterator[Any]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


OPTIONS = ("num_ctx", "num_predict", "temperature")


async def _streamed(llm: Any, question: str) -> str:
    chunks = [
        token
        async for token in llm.generate_stream(
            [{"role": "user", "content": question}], max_tokens=1024, temperature=0.2
        )
    ]
    return "".join(chunks)


def test_the_proxy_passes_each_request_unchanged_and_keeps_ollamas_counters() -> None:
    with _serving(_Ollama()) as upstream, _serving(wt.Proxy(upstream.url)) as proxy:
        llm = _llm(4096, base_url=proxy.url)
        answer = asyncio.run(_streamed(llm, QUESTION))
        reply = llm.invoke(f"You are {SELF_EVAL_MARKER}. Score?", max_tokens=128, temperature=0.0)
        with urllib.request.urlopen(proxy.url + "/api/version", timeout=10) as got:
            version = json.loads(got.read())
        assert proxy.settle()
    assert (answer, reply, version) == (ANSWER, "85", {"version": wt.OLLAMA_VERSION})
    generate = wt.model_calls({"calls": proxy.calls})
    assert len(generate) == 2 and len(upstream.bodies) == 2
    for call, body, counters, lines in zip(
        generate, upstream.bodies, upstream.counters, upstream.lines, strict=True
    ):
        # The bytes Ollama received are the bytes the binding sent.
        assert call["body_sha256"] == hashlib.sha256(body).hexdigest()
        assert call["body_bytes"] == len(body)
        assert (call["status"], call["done"], call["done_reason"]) == (200, True, "stop")
        assert call["counters"] == counters and call["lines"] == lines
        assert call["model"] == MODEL and call["think"] is False
        assert 0 <= call["first_token_sec"] <= call["done_sec"] <= call["end_sec"]
        assert "error" not in call and "ollama_error" not in call
    assert generate[0]["prompt_sha256"] == _digest(_flat(QUESTION))
    sent = [{key: call["options"].get(key) for key in OPTIONS} for call in generate]
    assert sent == [
        {"num_ctx": 4096, "num_predict": 1024, "temperature": 0.2},
        {"num_ctx": 4096, "num_predict": 128, "temperature": 0.0},
    ]
    (other,) = [call for call in proxy.calls if call not in generate]
    assert (other["method"], other["path"], other["status"]) == ("GET", "/api/version", 200)
    assert "counters" not in other


def test_unload_waits_until_ollama_holds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    with _serving(_Ollama()) as upstream:
        monkeypatch.setattr(wt, "OLLAMA", upstream.url)
        monkeypatch.setattr(wt, "POLL_SEC", 0.01)
        monkeypatch.setattr(wt, "llama_servers", lambda timeout=20.0: 1 if upstream.held else 0)
        assert wt.unload()["requested"] is False
        upstream.held = {"name": MODEL}
        got = wt.unload()
        assert (got["requested"], upstream.unloads, upstream.held) == (True, 1, None)
        assert json.loads(upstream.bodies[-1]) == {"model": MODEL, "keep_alive": 0}
        upstream.held, upstream.keeps = {"name": MODEL}, True
        monkeypatch.setattr(wt, "UNLOAD_LIMIT_SEC", 0.2)
        with pytest.raises(TimeoutError):
            wt.unload()


# --- a block, whole ---


@pytest.fixture(scope="module")
def pb() -> types.ModuleType:
    """Step 4's tool, whose fitting the inputs step records."""
    return sys.modules.get("prompt_budget") or _load("prompt_budget", STEP4)


def _case(pb: types.ModuleType, position: int, case_id: str) -> dict[str, Any]:
    return {
        "position": position,
        "case_id": case_id,
        "index": position,
        "question": f"{QUESTION} ({position})",
        "plain": _plain(),
        "prompts": wt.prompts_at(pb, f"{QUESTION} ({position})", _plain()),
    }


def _inputs(tmp_path: Path, pb: types.ModuleType) -> Path:
    """OUT as the inputs step leaves it, of all thirteen."""
    out = tmp_path / "out"
    out.mkdir()
    cases = [_case(pb, p, case_id) for p, case_id in enumerate(wt.CASES, start=1)]
    wt.write_json(
        out / "inputs.json",
        {"schema": wt.SCHEMA, "code_sha": STAND, "step4_rows_sha256": "f" * 64, "cases": cases},
    )
    return out


def _out(tmp_path: Path, pb: types.ModuleType, v4_stand: Path) -> Path:
    """OUT as the series' start leaves it."""
    out = _inputs(tmp_path, pb)
    wt.write_json(out / "series.json", {**wt.series_facts(out, v4_stand), "started": "t0"})
    return out


def _git(*args: str) -> str:
    return STAND if args[0] == "rev-parse" else ""


def _stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, upstream: _Ollama) -> Path:
    """The Mac's probes faked, the chat's environment set, and V4's stand of these settings."""
    monkeypatch.setattr(wt, "OLLAMA", upstream.url)
    monkeypatch.setattr(wt, "POLL_SEC", 0.01)
    monkeypatch.setattr(wt, "LLAMA_CONFIG", tmp_path / "config.ini")
    monkeypatch.setattr(wt, "foreign", lambda: [])
    monkeypatch.setattr(wt, "swap_used_mb", lambda: 512.0)
    monkeypatch.setattr(wt, "llama_servers", lambda timeout=20.0: 1 if upstream.held else 0)
    monkeypatch.setattr(wt, "git", _git)
    # Set first, so that the undo removes what the block sets.
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://unset.test")
    monkeypatch.delenv("OLLAMA_BASE_URL")
    for name in ("STREAMING_SELF_EVAL_MODE", "EXPERIMENT_ID", "RAG_LLM_ROLE_PARAMS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_PROVIDER_PROFILE", "local-first")
    monkeypatch.setenv("OLLAMA_MODEL_NAME", MODEL)
    monkeypatch.setenv("MODEL_ROUTING_ENABLED", "false")
    for name in ("REQUEST_TIMEOUT_SEC", "OLLAMA_REQUEST_TIMEOUT_SEC", "STREAMING_TIMEOUT_SEC"):
        monkeypatch.setenv(name, "3600")
    config_settings._settings = None
    settings = config_settings.get_settings()
    v4_stand = tmp_path / "v4"
    runs = v4_stand / wt.V4_SETTINGS.parent
    runs.mkdir(parents=True)
    recorded = {name: getattr(settings, name) for name in wt.SETTINGS}
    (v4_stand / wt.V4_SETTINGS).write_text(json.dumps({"all": recorded}), encoding="utf-8")
    (v4_stand / "config").mkdir()
    shutil.copyfile(settings.provider_registry_path, v4_stand / wt.V4_REGISTRY)
    config_settings._settings = None
    return v4_stand


def _block(monkeypatch: pytest.MonkeyPatch, out: Path, v4_stand: Path, number: int) -> int:
    """One block as the series starts it: a fresh process's settings and runtime."""
    config_settings._settings = None
    clear_provider_runtime_cache()
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_CONTEXT_WINDOW", str(wt.BLOCKS[number - 1]["window"]))
    return wt.block(out, v4_stand, number)


def test_a_block_makes_the_chats_two_calls_and_passes_its_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pb: types.ModuleType
) -> None:
    with _serving(_Ollama()) as upstream:
        v4_stand = _stand(tmp_path, monkeypatch, upstream)
        out = _out(tmp_path, pb, v4_stand)
        assert [_block(monkeypatch, out, v4_stand, n) for n in (1, 2)] == [0, 0]
    state = json.loads((out / "series.json").read_text(encoding="utf-8"))
    inputs = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    for number in (1, 2):
        plan = wt.BLOCKS[number - 1]
        path = wt.block_path(out, number)
        row = json.loads(path.read_text(encoding="utf-8"))
        case = wt.case_of(inputs, plan["case_id"])
        assert wt.gate(row, plan, case, state) == []
        assert wt.disturbed(row) == []
        calls = wt.model_calls(row)
        assert [call["options"]["num_ctx"] for call in calls] == [plan["window"]] * 2
        assert calls[0]["prompt_sha256"] == case["prompts"][str(plan["window"])]["sha256"]
        assert row["ps"]["context_length"] == plan["window"]
        assert (row["before"]["models"], row["after"]["models"]) == (
            [] if number == 1 else [MODEL],
            [MODEL],
        )
        assert row["unload"]["requested"] is (number == 2)
        assert (row["score"], row["route"], row["llama_config"]) == (85, "auto", False)
        numbers = wt.block_numbers(row)
        answer, evaluation = upstream.counters[2 * number - 2 : 2 * number]
        assert numbers["answer_prompt_tokens"] == answer["prompt_eval_count"]
        assert numbers["prompt_sec"] == round(
            (answer["prompt_eval_duration"] + evaluation["prompt_eval_duration"]) / 1e9, 3
        )
        assert numbers["load_sec"] == 2.0
        # The block's file holds no text of the question or the documents; the answer and the
        # self-evaluation's reply go to answers/.
        text = path.read_text(encoding="utf-8")
        assert QUESTION not in text and "freight" not in text
        kept = json.loads((out / "answers" / path.name).read_text(encoding="utf-8"))
        assert kept == {"answer": ANSWER, "raw_eval": "85"}
    one, two = (
        wt.block_numbers(json.loads(wt.block_path(out, n).read_text("utf-8"))) for n in (1, 2)
    )
    assert two["answer_prompt_tokens"] < one["answer_prompt_tokens"]


@pytest.mark.parametrize(
    "spoil",
    [
        "settings",
        "registry",
        "window",
        "server",
        "mode",
    ],
)
def test_a_block_refuses_a_stand_not_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pb: types.ModuleType, spoil: str
) -> None:
    with _serving(_Ollama()) as upstream:
        v4_stand = _stand(tmp_path, monkeypatch, upstream)
        out = _out(tmp_path, pb, v4_stand)
        if spoil == "settings":
            path = v4_stand / wt.V4_SETTINGS
            recorded = json.loads(path.read_text(encoding="utf-8"))
            recorded["all"]["quality_threshold"] = 70
            path.write_text(json.dumps(recorded), encoding="utf-8")
        elif spoil == "registry":
            with (v4_stand / wt.V4_REGISTRY).open("a", encoding="utf-8") as handle:
                handle.write("\n# another registry\n")
        elif spoil == "mode":
            monkeypatch.setenv("STREAMING_SELF_EVAL_MODE", "both")
        config_settings._settings = None
        clear_provider_runtime_cache()
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.setenv("OLLAMA_CONTEXT_WINDOW", "3584" if spoil == "window" else "4096")
        if spoil == "server":
            monkeypatch.setenv("OLLAMA_BASE_URL", upstream.url)
        assert wt.block(out, v4_stand, 1) == 6
        assert upstream.counters == []
    assert not wt.block_path(out, 1).exists()


# --- the gate, and what disturbs a block ---

STATE = {"code_sha": STAND, "tool_sha256": "a" * 64, "inputs_sha256": "b" * 64}
CASE = {"prompts": {"4096": {"sha256": "c" * 64}, "3584": {"sha256": "d" * 64}}}


def _ns(seconds: float) -> int:
    return int(round(seconds * 1e9))


def _call(
    window: int,
    sha: str,
    options: dict[str, Any],
    *,
    load: float,
    prompt_sec: float,
    gen: float,
    tokens: int = 150,
) -> dict[str, Any]:
    return {
        "method": "POST",
        "path": "/api/generate",
        "status": 200,
        "done": True,
        "done_reason": "stop",
        "model": MODEL,
        "options": {"num_ctx": window, **options},
        "prompt_sha256": sha,
        "first_token_sec": load + prompt_sec,
        "counters": {
            "total_duration": _ns(load + prompt_sec + gen) + 1,
            "load_duration": _ns(load),
            "prompt_eval_count": int(prompt_sec * 32),
            "prompt_eval_duration": _ns(prompt_sec),
            "eval_count": int(tokens),
            "eval_duration": _ns(gen),
        },
    }


def _row(
    plan: dict[str, Any],
    case: dict[str, Any] = CASE,
    state: dict[str, Any] = STATE,
    *,
    answer_prompt: float = 70.0,
    eval_prompt: float = 80.0,
    **changes: Any,
) -> dict[str, Any]:
    """A block as the tool writes one, that passes its gate undisturbed."""
    window = plan["window"]
    answer_sha = case["prompts"][str(window)]["sha256"]
    eval_sha = _digest(f"self-evaluation {plan['block']}")
    calls = [
        _call(window, answer_sha, wt.ANSWER_OPTIONS, load=6.0, prompt_sec=answer_prompt, gen=35.0),
        _call(
            window, eval_sha, wt.EVAL_OPTIONS, load=0.05, prompt_sec=eval_prompt, gen=0.5, tokens=2
        ),
    ]
    row = {
        "schema": wt.SCHEMA,
        **plan,
        **{key: state[key] for key in ("code_sha", "tool_sha256", "inputs_sha256")},
        "before": {
            "loadavg": [1.1, 1.2, 1.3],
            "swap_used_mb": 100.0,
            "foreign": [],
            "llama_servers": 0,
            "models": [],
            "ollama_version": wt.OLLAMA_VERSION,
        },
        "unload": {"unload_sec": 0.4, "polls": 2, "requested": True},
        "llama_config": False,
        "documents": 4,
        "prompt_sha256": answer_sha,
        "prompt_est_tokens": 2500,
        "answer_sha256": _digest(f"answer {plan['position']}"),
        "answer_chars": 600,
        "truncated": False,
        "eval_prompt_sha256": eval_sha,
        "eval_est_tokens": 2700,
        "result_wall_sec": 6.0 + answer_prompt + 35.0 + eval_prompt + 0.6,
        "score": 85,
        "quality": 85,
        "quality_source": "llm",
        "route": "auto",
        "calls": calls,
        "ps": {
            "count": 1,
            "name": MODEL,
            "digest": wt.DIGEST,
            "size": 4_000_000_000 + window,
            "size_vram": 0,
            "context_length": window,
        },
        "after": {
            "loadavg": [1.5, 1.3, 1.3],
            "swap_used_mb": 120.0,
            "foreign": [],
            "llama_servers": 1,
            "models": [MODEL],
            "ollama_version": wt.OLLAMA_VERSION,
        },
    }
    row.update(changes)
    return row


def _spoiled(change: Callable[[dict[str, Any]], None]) -> list[str]:
    plan = wt.BLOCKS[2]
    row = _row(plan)
    change(row)
    return wt.gate(row, plan, CASE, STATE)


def test_a_good_block_passes_its_gate() -> None:
    plan = wt.BLOCKS[2]
    assert wt.gate(_row(plan), plan, CASE, STATE) == []
    assert wt.disturbed(_row(plan)) == []


@pytest.mark.parametrize(
    ("change", "why"),
    [
        (lambda r: r["calls"].pop(), "1 model calls, not two"),
        (lambda r: r["calls"][0]["options"].update(num_ctx=4096), "not the model at num_ctx"),
        (lambda r: r["calls"][1]["options"].update(temperature=0.2), "options are not the chat's"),
        (lambda r: r["calls"][0].update(model="qwen3:1.7b"), "not the model at num_ctx"),
        (lambda r: r["calls"][1]["counters"].pop("eval_count"), "lacks Ollama's counters"),
        (lambda r: r["calls"][0].update(status=500), "did not end well"),
        (lambda r: r["calls"][1].update(done=False), "did not end well"),
        (lambda r: r["calls"][0].update(error="BrokenPipeError"), "did not end well"),
        (lambda r: r["calls"][0].update(ollama_error=True), "held an error"),
        (lambda r: r["calls"][0].update(prompt_sha256="e" * 64), "not the registered one"),
        (lambda r: r["calls"][1].update(prompt_sha256="e" * 64), "self-evaluation's prompt"),
        (lambda r: r["ps"].update(context_length=4096), "does not hold the one model"),
        (lambda r: r["ps"].update(digest="0" * 64), "does not hold the one model"),
        (lambda r: r["after"].update(ollama_version="0.34.0"), "Ollama is not 0.33.2 after"),
        (lambda r: r.update(llama_config=True), "config.ini was present"),
        (lambda r: r.update(truncated=True), "empty or cut"),
        (lambda r: r.update(answer_chars=0), "empty or cut"),
        (lambda r: r.update(unload={}), "not unloaded"),
        (lambda r: r.update(window=4096), "its window is not the schedule's"),
        (lambda r: r.update(inputs_sha256="0" * 64), "its inputs_sha256 is not the series'"),
    ],
)
def test_the_gate_names_what_is_not_registered(
    change: Callable[[dict[str, Any]], None], why: str
) -> None:
    assert any(why in reason for reason in _spoiled(change))


@pytest.mark.parametrize(
    ("side", "change"),
    [
        ("before", {"foreign": ["pytest"]}),
        ("after", {"foreign": ["limactl"]}),
        ("before", {"models": ["qwen3:1.7b"]}),
        ("after", {"models": [MODEL, "qwen3:1.7b"]}),
        ("after", {"llama_servers": 2}),
    ],
)
def test_what_else_ran_disturbs_a_block(side: str, change: dict[str, Any]) -> None:
    row = _row(wt.BLOCKS[0])
    row[side].update(change)
    assert wt.disturbed(row)


def test_the_documents_kept_are_step_4s_fitting_and_its_row(pb: types.ModuleType) -> None:
    prompts = wt.prompts_at(pb, QUESTION, _plain())
    for window in wt.WINDOWS:
        prompt, fitted = _fit_stream_prompt(
            SimpleNamespace(context_window=window), QUESTION, _plain(), []
        )
        assert prompts[str(window)]["sha256"] == _digest(_flat(prompt))
        assert prompts[str(window)]["documents"] == len(fitted)
    keys = ("documents", "cut", "chars", "est_tokens")
    row = {
        "windows": [
            {"window": 4096, **{key: prompts["4096"][key] for key in keys}},
            {"window": 3840, **dict.fromkeys(keys, 0)},
            {"window": 3584, **{key: prompts["3584"][key] for key in keys}},
        ]
    }
    assert wt.against_step4(prompts, row) == []
    row["windows"][2]["documents"] += 1
    row["windows"][0]["chars"] -= 1
    assert wt.against_step4(prompts, row) == ["chars at 4096", "documents at 3584"]


def test_keeping_holds_step_4s_checks_and_keeps_the_thirteens_documents() -> None:
    expanded = [SimpleNamespace(page_content="text", metadata={"source": "a.md"})]

    class Base:
        def documents(self, chunks: Any, members: Any) -> Any:
            _ = chunks, members
            return expanded

    def question(base, case, record, chunks, places, expand, at):  # noqa: ANN001, ANN202
        _ = base, case, places, expand
        if record["case_id"] == "broken":
            raise SystemExit("the recorded expansion differs")
        at.documents(chunks, [0])
        return {"case_id": record["case_id"], "v4_prompt_checked": True}

    pb = SimpleNamespace(Base=Base, question=question)
    with wt.keeping(pb) as kept:
        for case_id in (wt.CASES[0], "aircargo-other"):
            pb.question("aircargo", None, {"case_id": case_id}, [], None, None, at=Base())
        with pytest.raises(SystemExit):
            pb.question("aircargo", None, {"case_id": "broken"}, [], None, None, at=Base())
    assert (pb.Base.documents, pb.question) == (Base.documents, question)
    assert list(kept) == [wt.CASES[0]]
    record, row, plain = kept[wt.CASES[0]]
    assert row["v4_prompt_checked"] is True
    assert plain == [{"page_content": "text", "metadata": {"source": "a.md"}}]


# --- the series ---


def _series_stand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pb: types.ModuleType
) -> tuple[Path, Path, list[str]]:
    v4_stand = tmp_path / "v4"
    v4_stand.mkdir()
    monkeypatch.setattr(wt, "git", _git)
    monkeypatch.delenv("OLLAMA_CONTEXT_WINDOW", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    out = _inputs(tmp_path, pb)
    tags: list[str] = []
    monkeypatch.setattr(wt, "environment_line", lambda out, tag: tags.append(tag))
    monkeypatch.setattr(wt, "wait_idle", lambda out, first: True)
    monkeypatch.setattr(wt, "unload", lambda: {"unload_sec": 0.0, "polls": 1, "requested": False})
    return out, v4_stand, tags


def _runner(
    out: Path, ran: list[tuple[int, str]], bad: Callable[[int], Any] = lambda n: None
) -> Callable[..., Any]:
    """The block process: it writes a block that passes its gate, or what bad(number) makes."""

    def run(command: list[str], env: dict[str, str], timeout: float) -> SimpleNamespace:
        number = int(command[-1])
        plan = wt.BLOCKS[number - 1]
        assert command[-4:] == ["block", str(out), command[-2], str(number)]
        assert timeout == wt.BLOCK_CAP_SEC
        ran.append((number, env["OLLAMA_CONTEXT_WINDOW"]))
        outcome = bad(number)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, int):
            return SimpleNamespace(returncode=outcome)
        state = json.loads((out / "series.json").read_text(encoding="utf-8"))
        inputs = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
        row = _row(plan, wt.case_of(inputs, plan["case_id"]), state)
        if isinstance(outcome, dict):
            row["ps"] = {**row["ps"], **outcome}
        wt.write_json(wt.block_path(out, number), row)
        return SimpleNamespace(returncode=0)

    return run


def test_the_series_runs_the_26_in_order_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pb: types.ModuleType
) -> None:
    out, v4_stand, tags = _series_stand(tmp_path, monkeypatch, pb)
    ran: list[tuple[int, str]] = []
    monkeypatch.setattr(wt.subprocess, "run", _runner(out, ran))
    assert wt.series(out, v4_stand) == 0
    assert ran == [(b["block"], str(b["window"])) for b in wt.BLOCKS]
    assert tags == ["start", "end"]
    assert "SERIES_DONE" in (out / "series.log").read_text(encoding="utf-8")
    assert json.loads((out / "attempts.json").read_text("utf-8")) == {
        str(n): 1 for n in range(1, 27)
    }
    for number in (12, 20):
        wt.block_path(out, number).unlink()
    ran.clear()
    assert wt.series(out, v4_stand) == 0
    assert ran == [(n, str(wt.BLOCKS[n - 1]["window"])) for n in (12, 20)]


def test_the_series_stops_where_the_spec_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pb: types.ModuleType
) -> None:
    out, v4_stand, _ = _series_stand(tmp_path, monkeypatch, pb)
    ran: list[tuple[int, str]] = []
    # A gate failure: the block moves to rejected/, the series stops with 8; a block that
    # failed twice stops it with 9 before a third.
    monkeypatch.setattr(
        wt.subprocess,
        "run",
        _runner(out, ran, lambda n: {"context_length": 8192} if n == 3 else None),
    )
    assert wt.series(out, v4_stand) == 8
    assert (out / "rejected" / "03-3584-1.json").exists() and not wt.block_path(out, 3).exists()
    assert wt.series(out, v4_stand) == 8
    assert wt.series(out, v4_stand) == 9
    assert [number for number, _ in ran] == [1, 2, 3, 3]
    # A block's own exit, a block past its cap, the stop file.
    for outcome, code in ((7, 7), (subprocess.TimeoutExpired("block", 600), 5)):
        attempts = json.loads((out / "attempts.json").read_text("utf-8"))
        attempts["3"] = 0
        wt.write_json(out / "attempts.json", attempts)
        monkeypatch.setattr(wt.subprocess, "run", _runner(out, ran, lambda n, o=outcome: o))
        assert wt.series(out, v4_stand) == code
    (out / "stop").write_text("", encoding="utf-8")
    assert wt.series(out, v4_stand) == 3


def test_the_series_refuses_a_stand_not_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pb: types.ModuleType
) -> None:
    out, v4_stand, _ = _series_stand(tmp_path, monkeypatch, pb)
    ran: list[tuple[int, str]] = []
    monkeypatch.setattr(wt.subprocess, "run", _runner(out, ran, lambda n: 7 if n == 2 else None))
    assert wt.series(out, v4_stand) == 7
    monkeypatch.setenv("OLLAMA_CONTEXT_WINDOW", "3584")
    assert wt.series(out, v4_stand) == 6
    monkeypatch.delenv("OLLAMA_CONTEXT_WINDOW")
    monkeypatch.setattr(wt, "git", lambda *args: " M api/app.py" if args[0] == "status" else STAND)
    assert wt.series(out, v4_stand) == 6
    monkeypatch.setattr(wt, "git", lambda *args: "" if args[0] == "status" else "f" * 40)
    assert wt.series(out, v4_stand) == 6
    assert ran == [(1, "4096"), (2, "3584")]


def test_busy_names_what_keeps_the_mac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wt, "foreign", lambda: [])
    monkeypatch.setattr(wt, "models", lambda: [MODEL])
    monkeypatch.setattr(wt, "llama_servers", lambda timeout=20.0: 1)
    monkeypatch.setattr(wt, "CI_LOCK", tmp_path / "lock")
    monkeypatch.setattr(wt.os, "getloadavg", lambda: (3.0, 2.5, 2.0))
    # The model a block left loaded is no reason; the 5-minute load counts before the first.
    assert wt.busy(first=False) == []
    assert wt.busy(first=True) == ["the 5-minute load is 2.50"]
    monkeypatch.setattr(wt, "foreign", lambda: ["pytest"])
    monkeypatch.setattr(wt, "models", lambda: ["qwen3:1.7b"])
    (tmp_path / "lock").write_text("", encoding="utf-8")
    assert wt.busy(first=False) == [
        "processes: pytest",
        "another model in Ollama",
        "the CI lock",
    ]

    def unreachable() -> list[str]:
        raise OSError("refused")

    monkeypatch.setattr(wt, "models", unreachable)
    assert "Ollama does not answer: OSError" in wt.busy(first=False)


# --- the reading ---


def _rows(
    prompts: Callable[[dict[str, Any]], tuple[float, float]],
    *,
    missing: tuple[int, ...] = (),
    disturbed: tuple[int, ...] = (),
) -> list[dict[str, Any]]:
    """The reader's rows of 26 hand-made blocks; prompts(plan) gives a block's two prompt
    seconds."""
    rows = []
    for plan in wt.BLOCKS:
        row: dict[str, Any] = {**plan, "present": plan["block"] not in missing}
        if row["present"]:
            answer, evaluation = prompts(plan)
            row.update(wt.block_numbers(_row(plan, answer_prompt=answer, eval_prompt=evaluation)))
            row["gate"] = []
            row["disturbed"] = ["foreign processes: pytest"] if plan["block"] in disturbed else []
        rows.append(row)
    return rows


def _faster(slower_at: tuple[int, ...] = ()) -> Callable[[dict[str, Any]], tuple[float, float]]:
    """3,584 reads its prompts in 57 + 66 s, 4,096 in 70 + 80, but at the positions given."""

    def prompts(plan: dict[str, Any]) -> tuple[float, float]:
        small = plan["window"] == 3584
        if plan["position"] in slower_at:
            small = not small
        return (57.0, 66.0) if small else (70.0, 80.0)

    return prompts


def test_twelve_faster_pairs_read_faster() -> None:
    got = wt.readings(wt.pair_up(_rows(_faster())))
    assert got["answer"] == "faster"
    assert (got["readable_questions"], got["small_faster"], got["small_slower"]) == (12, 12, 0)
    assert got["sign_p"] == round(2 / 4096, 6)
    assert (got["median_prompt_saving_sec"], got["median_prompt_ratio"]) == (27.0, 0.82)
    beside = got["printed_deciding_nothing"]
    assert beside["median_prompt_sec"] == {"w4096": 150.0, "w3584": 123.0}
    assert (
        beside["by_order"]["w4096_first"]["pairs"]
        == beside["by_order"]["w3584_first"]["pairs"]
        == 6
    )
    assert beside["same_answer"] == 12 and beside["same_route"] == 12


def test_the_warm_up_never_counts() -> None:
    pairs = wt.pair_up(_rows(_faster(slower_at=(1,))))
    assert pairs[0]["warm_up"] and not pairs[0]["readable"]
    assert wt.readings(pairs)["small_faster"] == 12


@pytest.mark.parametrize(
    ("slower_at", "answer"),
    [
        ((2, 3), "faster"),  # 10 of 12, p = 0.0386
        ((2, 3, 4), "no detected difference"),  # 9 of 12, p = 0.146
        (tuple(range(2, 14, 2)), "no detected difference"),  # 6 of 12
        (tuple(range(2, 14)), "slower"),
    ],
)
def test_the_sign_test_decides(slower_at: tuple[int, ...], answer: str) -> None:
    assert wt.readings(wt.pair_up(_rows(_faster(slower_at))))["answer"] == answer


def test_fewer_than_ten_readable_pairs_are_not_evidence() -> None:
    # Blocks 4 (position 2), 6 (position 3) and 7 (position 4): three pairs out.
    rows = _rows(_faster(), missing=(4,), disturbed=(6, 7))
    pairs = wt.pair_up(rows)
    assert [pair["position"] for pair in pairs if not pair["readable"]] == [1, 2, 3, 4]
    assert pairs[1]["why"] == ["no block at 3584"] or pairs[1]["why"] == ["no block at 4096"]
    got = wt.readings(pairs)
    assert (got["answer"], got["readable_questions"]) == (wt.NOT_EVIDENCE, 9)
    rows = _rows(_faster(), disturbed=(6, 7))
    assert wt.readings(wt.pair_up(rows))["answer"] == "faster"


def _environment(out: Path) -> None:
    line = {
        "python_version": "3.11.15",
        "ollama": {
            "server_version": wt.OLLAMA_VERSION,
            "servers": [{"pid": 7, "started": "2026-10-29T08:00:00+00:00"}],
        },
        "distributions": {"freeze_sha256": "9" * 64, "versions": {"langchain-ollama": "1.1.0"}},
        "llama_config": False,
    }
    with (out / "environment.jsonl").open("w", encoding="utf-8") as handle:
        for tag in ("start", "end"):
            handle.write(json.dumps({"tag": tag, **line}) + "\n")


def test_read_writes_the_record_and_refuses_text_of_the_base(
    tmp_path: Path, pb: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    out, v4_stand, _ = _series_stand(tmp_path, monkeypatch, pb)
    wt.write_json(out / "series.json", {**wt.series_facts(out, v4_stand), "started": "t0"})
    state = json.loads((out / "series.json").read_text(encoding="utf-8"))
    inputs = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    (out / "blocks").mkdir()
    (out / "rejected").mkdir()
    for plan in wt.BLOCKS:
        small = plan["window"] == 3584
        row = _row(
            plan,
            wt.case_of(inputs, plan["case_id"]),
            state,
            answer_prompt=57.0 if small else 70.0,
            eval_prompt=66.0 if small else 80.0,
        )
        wt.write_json(wt.block_path(out, plan["block"]), row)
    _environment(out)
    assert wt.read(out, tmp_path / "record") == 0
    record = json.loads((tmp_path / "record" / "record.json").read_text(encoding="utf-8"))
    assert record["readings"]["answer"] == "faster"
    assert record["series"]["code_sha"] == STAND
    assert record["environment"]["server_versions"] == [wt.OLLAMA_VERSION]
    assert [case["case_id"] for case in record["inputs"]["cases"]] == list(wt.CASES)
    rows = (tmp_path / "record" / "rows.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 26 and all(json.loads(row)["gate"] == [] for row in rows)
    text = (tmp_path / "record" / "record.json").read_text(encoding="utf-8")
    assert QUESTION not in text and "freight" not in text
    assert wt.read(out, tmp_path / "record") == 2
    # A string of a block that holds a question is refused, the record unwritten.
    row = json.loads(wt.block_path(out, 5).read_text(encoding="utf-8"))
    row["after"]["foreign"] = [inputs["cases"][2]["question"]]
    wt.write_json(wt.block_path(out, 5), row)
    with pytest.raises(SystemExit):
        wt.read(out, tmp_path / "record-2")
    assert not (tmp_path / "record-2").exists()


# --- the spec ---


def test_the_tool_measures_what_the_spec_registers() -> None:
    """The spec names the SHA-256 of the tool and of this test, and a later change shows here
    (a marked error fix updates it); the frozen values stand as it states them."""
    spec = (ROOT / wt.SPEC).read_text(encoding="utf-8")
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage4-step4b/tools/window_timing.py",
        "tests/test_stage4_step4b_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    for phrase in (
        "registered before the first request",
        "Forecast, written before the first request",
        "**faster**, on 12 of 12",
        "With twelve, faster needs at least 10 of 12 (p = 0.039)",
        "`NOT_EVIDENCE` with fewer than ten readable pairs",
        "a block past 600 s",
        "the self-evaluation mode `classic`, the default",
        "answer num_predict 1,024 and temperature 0.2, the self-evaluation 128 and 0.0",
        wt.MODEL,
        wt.DIGEST[:8],
        wt.FOREIGN,
        "5e308fe",
    ):
        assert phrase in spec, phrase
    assert (wt.TODAY, wt.SMALL, wt.MIN_PAIRS, wt.ALPHA) == (4096, 3584, 10, 0.05)
    assert (wt.BLOCK_CAP_SEC, wt.MAX_ATTEMPTS, wt.IDLE_WAIT_SEC) == (600, 2, 3600)
    assert wt.ANSWER_OPTIONS == {"num_predict": 1024, "temperature": 0.2}
    assert wt.EVAL_OPTIONS == {"num_predict": 128, "temperature": 0.0}
    assert wt.sign_p(10, 2) < wt.ALPHA < wt.sign_p(9, 3)
