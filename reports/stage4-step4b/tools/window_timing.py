"""Stage 4, step 4b: num_ctx 3,584 against 4,096, timed - the answer and its self-evaluation.

docs/specs/stage4-step4b-window-timing.md, registered with this tool before the first request;
PLAN.md stage 4, item 4. Step 4 counted without a model that a window of 3,584 sends no gold
that 4,096 sends and drops none it keeps (docs/evidence/stage4-step4-record.md); this times
the window on the idle Mac. On the Mac, in a clean worktree of the registering commit:

  python window_timing.py inputs RUNS DATA_ROOT OUT   the documents of the thirteen questions
  python window_timing.py series OUT V4_STAND         the 26 blocks in order, resumable
  python window_timing.py block OUT V4_STAND NUMBER   one block; the series runs it
  python window_timing.py read OUT RECORD_DIR         the spec's reading of the blocks

inputs: step 4's tool (reports/stage4-step4/tools/prompt_budget.py) loads and checks stage 2's
aircargo records as it did for its count, and keeps, for aircargo's first thirteen questions,
the documents its fitting starts from: the product's parent expansion of the recorded five.
The chat's fitting of them at 4,096 must be V4's live prompt, and at both windows step 4's
committed row. OUT/inputs.json holds the questions and the documents' texts: it stays on the
Mac.

A block is one question at one window. Ollama is made to hold no model and no llama-server
(keep_alive 0, then /api/ps and ps until both are gone); then, in a process whose
OLLAMA_CONTEXT_WINDOW is the block's window, the chat's own model - the provider runtime's
strong model, built from the settings - makes the chat's calls of a first question in mode
classic, the default: the answer, streamed, then the classic self-evaluation. They go through
a local proxy that passes each request to Ollama unchanged and keeps Ollama's counters of it.
OUT/blocks/NN-WINDOW.json holds ids, numbers, flags and SHA-256 strings; the answer's text and
the self-evaluation's reply go to OUT/answers/, on the Mac only.

series stops with 3 at the stop file OUT/stop; 4 when the Mac is not idle within
IDLE_WAIT_SEC; 5 when a block runs past BLOCK_CAP_SEC (killed, the model unloaded); 6 when the
settings, the model, the window or the series' facts are not the registered ones; 7 when a
call to Ollama failed (nothing saved); 8 when a block's gate failed (its file moved to
OUT/rejected/); 9 when a block failed twice. Started again it resumes at its first block
without a file.
"""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import math
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))

SCHEMA = "stage4-step4b/v1"
SPEC = "docs/specs/stage4-step4b-window-timing.md"
NOT_EVIDENCE = "NOT_EVIDENCE"
BASE = "aircargo"
# aircargo's registered order, its first thirteen, as step 3 timed them: the first pairs with
# nothing; the other twelve make the pairs.
CASES = (
    "aircargo-probation-data",
    "aircargo-probation-extend",
    "aircargo-probation-dismissal",
    "aircargo-dismissal-check",
    "aircargo-dismissal-lawyer",
    "aircargo-dismissal-order",
    "aircargo-leave-sources",
    "aircargo-leave-compensation",
    "aircargo-leave-risk",
    "aircargo-matliab-check",
    "aircargo-matliab-disputed",
    "aircargo-templates-choose",
    "aircargo-templates-checklist",
)
TODAY, SMALL = 4096, 3584
WINDOWS = (TODAY, SMALL)
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
OLLAMA_VERSION = "0.33.2"
OLLAMA = "http://127.0.0.1:11434"
# V4's stand: its first aircargo run's settings and the provider registry it read.
V4_SETTINGS = Path("chatlive") / "runs" / "v4-aircargo-b01" / "effective_settings.json"
V4_REGISTRY = Path("config") / "providers.yml"
# The chat's settings as V4's run recorded them (effective_settings.json, "all"), beside the
# window and the registry, whose path is the stand's own.
SETTINGS = (
    "llm_provider_profile",
    "ollama_model_name",
    "model_routing_enabled",
    "llm_role_params_json",
    "streaming_timeout_sec",
    "ollama_request_timeout_sec",
    "request_timeout_sec",
    "streaming_quality_eval",
    "quality_threshold",
    "streaming_rag_parity",
)
STEP4_ROWS = WS / "reports" / "stage4-step4" / "5e308fe" / "rows.jsonl"
# Ollama's counters of a call, in the last line of its stream (nanoseconds, tokens).
COUNTERS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)
# The options the chat sends: the "generate" and "evaluate" roles (llm/role_params.py).
ANSWER_OPTIONS = {"num_predict": 1024, "temperature": 0.2}
EVAL_OPTIONS = {"num_predict": 128, "temperature": 0.0}
# 3x the forecast of a block at 4,096 (a load, both prompts, an answer of ~150 tokens).
BLOCK_CAP_SEC = 600
UNLOAD_LIMIT_SEC = 120.0
POLL_SEC = 0.5
IDLE_POLL_SEC = 30
IDLE_WAIT_SEC = 3600
MAX_ATTEMPTS = 2
UPSTREAM_TIMEOUT_SEC = 3600.0
# Step 0's rule of an idle Mac, its llama-server left out: a block's own model runs one.
FOREIGN = r"[p]ytest|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl"
PS = ("ps", "-axo", "pid=,rss=,comm=")
CI_LOCK = Path.home() / "ci_local" / ".lock_ci-local"
LLAMA_CONFIG = Path.home() / ".config" / "llama.cpp" / "config.ini"
MIN_PAIRS = 10
ALPHA = 0.05
# Headers that belong to one connection, not to the request.
HOP = {
    "connection",
    "keep-alive",
    "proxy-connection",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "content-length",
    "host",
}


def schedule() -> list[dict[str, Any]]:
    """The blocks in their order: the first question at 4,096 then 3,584, the next the other
    way round, and so on - A B B A A B ... - each window first in six of the twelve pairs."""
    blocks: list[dict[str, Any]] = []
    for position, case_id in enumerate(CASES, start=1):
        first = TODAY if position % 2 else SMALL
        for order, window in enumerate((first, SMALL if first == TODAY else TODAY), start=1):
            blocks.append(
                {
                    "block": len(blocks) + 1,
                    "position": position,
                    "case_id": case_id,
                    "window": window,
                    "order": order,
                }
            )
    return blocks


BLOCKS = schedule()


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rounded(value: float | None, places: int = 3) -> float | None:
    return None if value is None else round(value, places)


def median(values: list[float | None]) -> float | None:
    kept = [value for value in values if value is not None]
    return rounded(statistics.median(kept)) if kept else None


def seconds(nanoseconds: int | None) -> float | None:
    return None if nanoseconds is None else nanoseconds / 1e9


def write_json(path: Path, value: Any) -> None:
    """Written whole or not at all: a temporary file, then a rename."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)


def git(*args: str) -> str:
    done = subprocess.run(["git", "-C", str(WS), *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def block_path(out: Path, number: int) -> Path:
    return out / "blocks" / f"{number:02d}-{BLOCKS[number - 1]['window']}.json"


def case_of(inputs: dict[str, Any], case_id: str) -> dict[str, Any]:
    (case,) = [case for case in inputs["cases"] if case["case_id"] == case_id]
    return case


# --- inputs: step 4's documents of the thirteen ---


def prompts_at(pb: Any, question: str, plain: list[dict[str, Any]]) -> dict[str, Any]:
    """The chat's answer prompt of a first question at each window, as step 4 fits it: the
    string the provider sends, its size and the documents it holds."""
    from llm.providers.base import estimate_window_tokens

    got = {}
    for window in WINDOWS:
        flat, fitted = pb.fit(window, question, plain)
        got[str(window)] = {
            "sha256": digest(flat),
            "chars": len(flat),
            "est_tokens": estimate_window_tokens(flat),
            "documents": len(fitted),
            "cut": any(document["cut"] for document in pb.sent(fitted, plain)),
        }
    return got


def against_step4(prompts: dict[str, Any], step4_row: dict[str, Any]) -> list[str]:
    """Where the prompts differ from step 4's committed row of the question."""
    differ = []
    for window in WINDOWS:
        (entry,) = [e for e in step4_row["windows"] if e["window"] == window]
        for key in ("documents", "cut", "chars", "est_tokens"):
            if prompts[str(window)][key] != entry[key]:
                differ.append(f"{key} at {window}")
    return differ


@contextmanager
def keeping(pb: Any) -> Iterator[dict[str, Any]]:
    """Step 4's question() as it is, every check of it kept; for the thirteen, its record, its
    row and the documents its fitting started from - Base.documents', the product's parent
    expansion of the recorded five - are kept on the side, by case id."""
    seen: dict[str, Any] = {}
    kept: dict[str, Any] = {}
    documents, question = pb.Base.documents, pb.question

    def keeping_documents(self: Any, chunks: Any, members: Any) -> Any:
        seen["docs"] = documents(self, chunks, members)
        return seen["docs"]

    def keeping_question(base, case, record, chunks, places, expand, at):  # noqa: ANN001, ANN202
        seen.pop("docs", None)
        row = question(base, case, record, chunks, places, expand, at=at)
        if record["case_id"] in CASES:
            plain = [
                {"page_content": d.page_content, "metadata": d.metadata or {}} for d in seen["docs"]
            ]
            kept[record["case_id"]] = (record, row, plain)
        return row

    pb.Base.documents, pb.question = keeping_documents, keeping_question
    try:
        yield kept
    finally:
        pb.Base.documents, pb.question = documents, question


def inputs(runs: Path, root: Path, out: Path) -> int:
    sys.path.insert(0, str(WS / "reports" / "stage4-step4" / "tools"))
    import prompt_budget as pb

    nr = pb.nr
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != nr.CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    answer_prompts = (pb.stage2_prompt(), pb.code_prompt())
    with keeping(pb) as kept:
        pb.base_rows(BASE, runs, root, manifest, answer_prompts)
    if sorted(kept) != sorted(CASES):
        raise SystemExit("step 4's rows do not hold the thirteen")
    step4 = {row["case_id"]: row for row in pb.load_jsonl(STEP4_ROWS)}
    v4 = pb.v4_rows(BASE)
    cases = []
    with pb.answer_prompt(answer_prompts[1]):
        for position, case_id in enumerate(CASES, start=1):
            record, row, plain = kept[case_id]
            if not row["v4_prompt_checked"]:
                raise SystemExit(f"{case_id}: V4's run retrieved other documents")
            prompts = prompts_at(pb, record["question"], plain)
            if prompts[str(TODAY)]["sha256"] != v4[case_id]["prompts"][0]["sha256"]:
                raise SystemExit(f"{case_id}: the prompt at {TODAY} is not V4's run's")
            differ = against_step4(prompts, step4[case_id])
            if differ:
                raise SystemExit(f"{case_id}: not step 4's row: " + ", ".join(differ))
            cases.append(
                {
                    "position": position,
                    "case_id": case_id,
                    "index": record["index"],
                    "question": record["question"],
                    "plain": plain,
                    "prompts": prompts,
                }
            )
    value = {
        "schema": SCHEMA,
        "spec": SPEC,
        "base": BASE,
        "code_sha": git("rev-parse", "HEAD"),
        "tool_sha256": sha256(Path(__file__)),
        "step4_rows_sha256": sha256(STEP4_ROWS),
        "runs": str(runs),
        "data_root": str(root),
        "cases": cases,
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "inputs.json", value)
    # Read back as the blocks read it: the same prompts from the stored documents.
    stored = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    with pb.answer_prompt(answer_prompts[1]):
        for case in stored["cases"]:
            if prompts_at(pb, case["question"], case["plain"]) != case["prompts"]:
                raise SystemExit(f"{case['case_id']}: the stored documents give other prompts")
    for case in cases:
        sizes = ", ".join(
            f"{w}: {case['prompts'][str(w)]['documents']} documents, "
            f"{case['prompts'][str(w)]['est_tokens']} est. tokens"
            for w in WINDOWS
        )
        print(f"{case['position']:2d} {case['case_id']}: {sizes}")
    print(f"inputs.json sha256 {sha256(out / 'inputs.json')}")
    return 0


# --- the Mac and Ollama ---


def ollama(path: str, payload: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read() or b"{}")


def llama_servers(timeout: float = 20.0) -> int:
    """How many processes, host-wide, have llama-server as their executable's base name."""
    done = subprocess.run(PS, capture_output=True, text=True, timeout=timeout, check=True)
    rows = [line.split(None, 2) for line in done.stdout.splitlines()]
    return sum(
        1
        for row in rows
        if len(row) == 3
        and row[0].isdigit()
        and row[1].isdigit()
        and row[2].strip().rsplit("/", 1)[-1] == "llama-server"
    )


def foreign() -> list[str]:
    """The base names of the processes step 0's rule finds; no argument kept."""
    done = subprocess.run(["pgrep", "-f", FOREIGN], capture_output=True, text=True, timeout=20)
    names = []
    for pid in done.stdout.split():
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        got = subprocess.run(["ps", "-o", "comm=", "-p", pid], capture_output=True, text=True)
        name = got.stdout.strip().rsplit("/", 1)[-1]
        if name:
            names.append(name)
    return sorted(names)


def swap_used_mb() -> float | None:
    try:
        done = subprocess.run(
            ["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, timeout=10
        )
    except OSError:
        return None
    found = re.search(r"used = ([\d.]+)M", done.stdout)
    return float(found[1]) if found else None


def models() -> list[str]:
    return sorted(str(m.get("name") or m.get("model")) for m in ollama("/api/ps")["models"] or [])


def machine() -> dict[str, Any]:
    return {
        "loadavg": [round(value, 2) for value in os.getloadavg()],
        "swap_used_mb": swap_used_mb(),
        "foreign": foreign(),
        "llama_servers": llama_servers(),
        "models": models(),
        "ollama_version": ollama("/api/version").get("version"),
    }


def loaded() -> dict[str, Any]:
    """What /api/ps says of the model Ollama holds, when it holds one."""
    held = ollama("/api/ps")["models"] or []
    got: dict[str, Any] = {"count": len(held)}
    if len(held) == 1:
        model = held[0]
        got.update(
            name=model.get("name") or model.get("model"),
            digest=model.get("digest"),
            size=model.get("size"),
            size_vram=model.get("size_vram"),
            context_length=model.get("context_length"),
        )
    return got


def unload() -> dict[str, Any]:
    """Ollama made to hold no model and no llama-server to be left: keep_alive 0 when it holds
    one, then /api/ps and ps every POLL_SEC s until both are gone, as step 2b's replay did. One
    deadline, UNLOAD_LIMIT_SEC after the start, bounds the requests and the polls."""
    started = time.monotonic()
    deadline = started + UNLOAD_LIMIT_SEC

    def left(cap: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"a model or a llama-server {UNLOAD_LIMIT_SEC} s after the unload")
        return min(cap, remaining)

    requested, polls = False, 0
    while True:
        polls += 1
        held = ollama("/api/ps", None, left(10.0)).get("models")
        if not held and not llama_servers(left(20.0)):
            return {
                "unload_sec": rounded(time.monotonic() - started),
                "polls": polls,
                "requested": requested,
            }
        if held and not requested:
            ollama("/api/generate", {"model": MODEL, "keep_alive": 0}, left(60.0))
            requested = True
        time.sleep(POLL_SEC)


# --- the proxy: each request to Ollama unchanged, Ollama's counters kept ---


class Proxy(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, upstream: str) -> None:
        super().__init__(("127.0.0.1", 0), _Forward)
        parts = urllib.parse.urlsplit(upstream)
        self.upstream = (parts.hostname or "127.0.0.1", parts.port or 80)
        self.calls: list[dict[str, Any]] = []
        self.pending = 0
        self.changed = threading.Condition()
        self.origin = time.monotonic()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def settle(self, timeout: float = 30.0) -> bool:
        """Whether every request it took is recorded: a client may stop reading at Ollama's
        last line and return before the request's thread has kept its counters."""
        with self.changed:
            return self.changed.wait_for(lambda: self.pending == 0, timeout)


def request_fields(body: bytes) -> dict[str, Any]:
    """Of a request: its bytes' SHA-256 and length; of a JSON one, its fields' names, the model,
    the options and the prompt's SHA-256 and length - never the prompt."""
    got: dict[str, Any] = {"body_sha256": hashlib.sha256(body).hexdigest(), "body_bytes": len(body)}
    try:
        payload = json.loads(body) if body else None
    except ValueError:
        return got
    if isinstance(payload, dict):
        prompt = payload.get("prompt")
        got.update(
            fields=sorted(payload),
            model=payload.get("model"),
            stream=payload.get("stream"),
            think=payload.get("think"),
            keep_alive=payload.get("keep_alive"),
            options=payload.get("options"),
            prompt_sha256=digest(prompt) if isinstance(prompt, str) else None,
            prompt_chars=len(prompt) if isinstance(prompt, str) else None,
        )
    return got


def response_line(call: dict[str, Any], line: bytes, after: float) -> None:
    """One line of /api/generate's stream: when the first token came, and the last line's
    counters - never the text."""
    try:
        item = json.loads(line)
    except ValueError:
        call["unread_lines"] = call.get("unread_lines", 0) + 1
        return
    if not isinstance(item, dict):
        return
    if item.get("error"):
        call["ollama_error"] = True
    if item.get("response") and "first_token_sec" not in call:
        call["first_token_sec"] = rounded(after)
    if item.get("done"):
        call.update(
            done=True,
            done_sec=rounded(after),
            done_reason=item.get("done_reason"),
            counters={key: item.get(key) for key in COUNTERS},
        )


class _Forward(BaseHTTPRequestHandler):
    server: Proxy

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802
        self._forward(None)

    def do_POST(self) -> None:  # noqa: N802
        self._forward(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

    def _forward(self, body: bytes | None) -> None:
        received = time.monotonic()
        with self.server.changed:
            self.server.pending += 1
        call: dict[str, Any] = {
            "method": self.command,
            "path": self.path,
            "at_sec": rounded(received - self.server.origin),
        }
        if body is not None:
            call.update(request_fields(body))
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        connection = http.client.HTTPConnection(*self.server.upstream, timeout=UPSTREAM_TIMEOUT_SEC)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            reply = connection.getresponse()
            call["status"] = reply.status
            self.send_response(reply.status)
            for key, value in reply.getheaders():
                if key.lower() not in HOP:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            lines = 0
            while True:
                line = reply.readline()
                if not line:
                    break
                self.wfile.write(line)
                self.wfile.flush()
                lines += 1
                if self.path == "/api/generate":
                    response_line(call, line, time.monotonic() - received)
            call["lines"] = lines
        except OSError as exc:
            # The client gone or Ollama unreachable: the call is recorded as broken.
            call["error"] = type(exc).__name__
        finally:
            connection.close()
            call["end_sec"] = rounded(time.monotonic() - received)
            with self.server.changed:
                self.server.calls.append(call)
                self.server.pending -= 1
                self.server.changed.notify_all()


# --- a block: the chat's two calls at one window ---


def provider_and_settings(v4_stand: Path, window: int) -> tuple[Any, Any, list[str]]:
    """The chat's stream model, and its settings held against V4's first aircargo run: the
    same but for the window, which must be the block's, and the server, which is the proxy."""
    from config.settings import get_settings
    from llm.providers.runtime import build_provider_runtime

    settings = get_settings()
    recorded = json.loads((v4_stand / V4_SETTINGS).read_text(encoding="utf-8"))["all"]
    differ = [n for n in SETTINGS if str(getattr(settings, n, None)) != str(recorded.get(n))]
    if sha256(Path(settings.provider_registry_path)) != sha256(v4_stand / V4_REGISTRY):
        differ.append("the provider registry")
    if str(getattr(settings, "streaming_self_eval_mode", None)) != "classic":
        differ.append("streaming_self_eval_mode")
    if int(settings.ollama_context_window) != window:
        differ.append("ollama_context_window")
    proxy = os.environ.get("OLLAMA_BASE_URL")
    if settings.ollama_base_url != proxy:
        differ.append("ollama_base_url")
    llm = build_provider_runtime(settings).strong
    # The runtime wraps its provider (llm.providers.base.ProviderBackedLLM); no fallback.
    inner = getattr(llm, "_provider", llm)
    if (
        type(inner).__name__ != "OllamaProvider"
        or getattr(llm, "_fallback_provider", None) is not None
        or llm.model_name != MODEL
        or getattr(inner, "_base_url", None) != proxy
    ):
        differ.append("the stream model")
    if getattr(llm, "context_window", None) != window:
        differ.append("the stream model's window")
    return llm, settings, differ


async def chat_calls(
    llm: Any, settings: Any, question: str, plain: list[dict[str, Any]]
) -> dict[str, Any]:
    """The chat's stream from its fitting to its classic self-evaluation, on the documents the
    retrieval gave (api/routers/conversation.py, ask_stream: the direct stream of a first
    question, then the self-evaluation of mode classic). Every line that reaches the model is
    the chat's; tests/test_stage4_step4b_tools.py holds the calls to the chat's own."""
    from agent.context_window import fit_context_docs, prompt_input_tokens
    from agent.graph import _invoke_llm, _parse_int_score
    from agent.prompts import build_self_eval_prompt
    from api.routers.conversation import _fit_stream_prompt
    from config.settings import TIME_LIMIT_CEILING_SEC
    from llm.providers.base import estimate_window_tokens, flatten_messages
    from llm.request_budget import bind_llm_request_budget_from_settings
    from llm.role_params import generation_kwargs_for_role
    from utils.request_deadline import bind_request_deadline

    # ask_stream binds the request's deadline and model budget first.
    request_timeout = float(getattr(settings, "request_timeout_sec", TIME_LIMIT_CEILING_SEC))
    bind_request_deadline(request_timeout, source="ask_stream")
    bind_llm_request_budget_from_settings(settings, source="ask_stream")
    prompt, docs = _fit_stream_prompt(llm, question, list(plain), [])
    stream_params = generation_kwargs_for_role("generate")
    started = time.monotonic()
    stream_deadline = started + float(
        getattr(settings, "streaming_timeout_sec", TIME_LIMIT_CEILING_SEC)
    )
    full_answer, first, chunks, truncated = "", None, 0, False
    async for token in llm.generate_stream([{"role": "user", "content": prompt}], **stream_params):
        if first is None:
            first = time.monotonic() - started
        full_answer += token
        chunks += 1
        if time.monotonic() > stream_deadline:
            truncated = True
            break
    answered = time.monotonic()
    if not full_answer:
        raise RuntimeError("empty streaming answer")

    # The classic self-evaluation, as ask_stream runs it.
    answer_for_eval = re.sub(r"\s*\[\d+\]", "", full_answer)
    answer_for_eval = re.sub(r"\s{2,}", " ", answer_for_eval).strip()

    def _eval_prompt(selected: list[dict[str, Any]]) -> str:
        return build_self_eval_prompt(
            question=question, answer=answer_for_eval, context_docs=selected
        )

    eval_prompt = _eval_prompt(
        fit_context_docs(llm, question + " " + answer_for_eval, docs, _eval_prompt, role="evaluate")
    )
    raw_eval = await asyncio.get_running_loop().run_in_executor(
        None, lambda: _invoke_llm(llm, eval_prompt, role="evaluate")
    )
    evaluated = time.monotonic()
    score = _parse_int_score(raw_eval, default=-1)
    if score != -1:
        quality, source = score, "llm"
        route = "auto" if quality >= int(getattr(settings, "quality_threshold", 80)) else "human"
    else:
        quality = 70 if len(full_answer.strip()) > 20 or docs else 40
        source, route = "heuristic", "auto" if quality >= 70 else "human"
    flat = flatten_messages([{"role": "user", "content": prompt}])
    eval_flat = flatten_messages([{"role": "user", "content": eval_prompt}])
    return {
        "answer": full_answer,
        "raw_eval": str(raw_eval),
        "numbers": {
            "documents": len(docs),
            "prompt_sha256": digest(flat),
            "prompt_est_tokens": estimate_window_tokens(flat),
            "answer_sha256": digest(full_answer),
            "answer_chars": len(full_answer),
            "chunks": chunks,
            "first_chunk_sec": rounded(first),
            "truncated": truncated,
            "answer_wall_sec": rounded(answered - started),
            "eval_prompt_sha256": digest(eval_flat),
            "eval_est_tokens": prompt_input_tokens(eval_prompt),
            "eval_wall_sec": rounded(evaluated - answered),
            "result_wall_sec": rounded(evaluated - started),
            "score": score,
            "quality": quality,
            "quality_source": source,
            "route": route,
        },
    }


def series_facts(out: Path, v4_stand: Path) -> dict[str, Any]:
    return {
        "spec": SPEC,
        "tool_sha256": sha256(Path(__file__)),
        "code_sha": git("rev-parse", "HEAD"),
        "inputs_sha256": sha256(out / "inputs.json"),
        "v4_stand": str(v4_stand),
    }


def block(out: Path, v4_stand: Path, number: int) -> int:
    plan = BLOCKS[number - 1]
    window = plan["window"]
    state = json.loads((out / "series.json").read_text(encoding="utf-8"))
    facts = series_facts(out, v4_stand)
    if {key: state.get(key) for key in facts} != facts:
        print("the series' facts are not the block's", file=sys.stderr)
        return 6
    if os.environ.get("OLLAMA_CONTEXT_WINDOW") != str(window) or os.environ.get("OLLAMA_BASE_URL"):
        print(f"OLLAMA_CONTEXT_WINDOW is not {window}, or a server is set", file=sys.stderr)
        return 6
    case = case_of(json.loads((out / "inputs.json").read_text(encoding="utf-8")), plan["case_id"])
    row: dict[str, Any] = {
        "schema": SCHEMA,
        **plan,
        "code_sha": facts["code_sha"],
        "tool_sha256": facts["tool_sha256"],
        "inputs_sha256": facts["inputs_sha256"],
        "started": now(),
    }
    try:
        row["before"] = machine()
        row["unload"] = unload()
    except (OSError, TimeoutError, ValueError) as exc:
        print(f"before the block: {type(exc).__name__}", file=sys.stderr)
        return 7
    row["llama_config"] = LLAMA_CONFIG.exists()
    proxy = Proxy(OLLAMA)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    os.environ["OLLAMA_BASE_URL"] = proxy.url
    try:
        llm, settings, differ = provider_and_settings(v4_stand, window)
        if differ:
            print("not as registered: " + ", ".join(differ), file=sys.stderr)
            return 6
        try:
            got = asyncio.run(chat_calls(llm, settings, case["question"], case["plain"]))
        except Exception as exc:  # noqa: BLE001 - not saved; the block is asked again
            print(f"the model's calls: {type(exc).__name__}", file=sys.stderr)
            return 7
        if not proxy.settle():
            print("a request through the proxy did not end", file=sys.stderr)
            return 7
    finally:
        proxy.shutdown()
        proxy.server_close()
    row.update(got["numbers"])
    row["calls"] = list(proxy.calls)
    try:
        row["ps"] = loaded()
        row["after"] = machine()
    except (OSError, ValueError) as exc:
        print(f"after the block: {type(exc).__name__}", file=sys.stderr)
        return 7
    row["finished"] = now()
    for name in ("blocks", "answers"):
        (out / name).mkdir(exist_ok=True)
    write_json(
        out / "answers" / f"{number:02d}-{window}.json",
        {"answer": got["answer"], "raw_eval": got["raw_eval"]},
    )
    write_json(block_path(out, number), row)
    return 0


# --- what a block must be, and what it says ---


def model_calls(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        call
        for call in row.get("calls") or []
        if call.get("method") == "POST" and call.get("path") == "/api/generate"
    ]


def gate(
    row: dict[str, Any], plan: dict[str, Any], case: dict[str, Any], state: dict[str, Any]
) -> list[str]:
    """Why a block is not what the spec registered; empty when it is."""
    why = []
    window = plan["window"]
    for key in ("block", "position", "case_id", "window", "order"):
        if row.get(key) != plan[key]:
            why.append(f"its {key} is not the schedule's")
    for key in ("code_sha", "tool_sha256", "inputs_sha256"):
        if row.get(key) != state.get(key):
            why.append(f"its {key} is not the series'")
    calls = model_calls(row)
    if len(calls) != 2:
        why.append(f"{len(calls)} model calls, not two")
    else:
        for name, call, options in (
            ("answer", calls[0], ANSWER_OPTIONS),
            ("self-evaluation", calls[1], EVAL_OPTIONS),
        ):
            if call.get("status") != 200 or not call.get("done") or call.get("error"):
                why.append(f"the {name} call did not end well")
            if call.get("ollama_error") or call.get("unread_lines"):
                why.append(f"the {name} call's stream held an error or an unread line")
            counters = call.get("counters") or {}
            if any(not isinstance(counters.get(key), int) for key in COUNTERS):
                why.append(f"the {name} call lacks Ollama's counters")
            sent = call.get("options") or {}
            if call.get("model") != MODEL or sent.get("num_ctx") != window:
                why.append(f"the {name} call is not the model at num_ctx {window}")
            if any(sent.get(key) != value for key, value in options.items()):
                why.append(f"the {name} call's options are not the chat's")
        if calls[0].get("prompt_sha256") != case["prompts"][str(window)]["sha256"]:
            why.append("the answer's prompt is not the registered one")
        if calls[0].get("prompt_sha256") != row.get("prompt_sha256"):
            why.append("the answer's prompt is not the block's")
        if calls[1].get("prompt_sha256") != row.get("eval_prompt_sha256"):
            why.append("the self-evaluation's prompt is not the block's")
    ps = row.get("ps") or {}
    if (ps.get("count"), ps.get("name"), ps.get("digest"), ps.get("context_length")) != (
        1,
        MODEL,
        DIGEST,
        window,
    ):
        why.append(f"Ollama does not hold the one model at {window}")
    for when in ("before", "after"):
        if (row.get(when) or {}).get("ollama_version") != OLLAMA_VERSION:
            why.append(f"Ollama is not {OLLAMA_VERSION} {when} the block")
    if not isinstance((row.get("unload") or {}).get("polls"), int):
        why.append("the model was not unloaded before the block")
    if row.get("llama_config") is not False:
        why.append("a llama.cpp config.ini was present")
    if row.get("truncated") or not row.get("answer_chars"):
        why.append("the answer is empty or cut at the chat's wall")
    return why


def disturbed(row: dict[str, Any]) -> list[str]:
    """What else ran: step 0's processes at the block's start or end, another model, or a
    llama-server not the block's own at its end."""
    why = []
    before, after = row.get("before") or {}, row.get("after") or {}
    names = sorted(set(before.get("foreign") or []) | set(after.get("foreign") or []))
    if names:
        why.append("foreign processes: " + ", ".join(names))
    if any(model != MODEL for model in before.get("models") or []):
        why.append("another model in Ollama at the start")
    if after.get("models") != [MODEL] or after.get("llama_servers") != 1:
        why.append("at the end Ollama held more than the block's model")
    return why


def block_numbers(row: dict[str, Any]) -> dict[str, Any]:
    """A block's numbers: Ollama's counters of its two calls, in seconds and tokens, and the
    block's walls less the model's load."""
    calls = model_calls(row)
    answer, evaluation = (calls + [{}, {}])[:2]
    a, e = answer.get("counters") or {}, evaluation.get("counters") or {}

    def total(key: str) -> float | None:
        values = [a.get(key), e.get(key)]
        return None if None in values else seconds(sum(values))

    load = seconds(a.get("load_duration"))
    whole = None
    if None not in (total("total_duration"), total("load_duration")):
        whole = total("total_duration") - total("load_duration")
    result = row.get("result_wall_sec")
    ps, before, after = row.get("ps") or {}, row.get("before") or {}, row.get("after") or {}
    return {
        "prompt_sec": rounded(total("prompt_eval_duration")),
        "answer_prompt_sec": rounded(seconds(a.get("prompt_eval_duration"))),
        "eval_prompt_sec": rounded(seconds(e.get("prompt_eval_duration"))),
        "answer_prompt_tokens": a.get("prompt_eval_count"),
        "eval_prompt_tokens": e.get("prompt_eval_count"),
        "answer_tokens": a.get("eval_count"),
        "eval_tokens": e.get("eval_count"),
        "answer_gen_sec": rounded(seconds(a.get("eval_duration"))),
        "eval_gen_sec": rounded(seconds(e.get("eval_duration"))),
        "load_sec": rounded(load),
        "eval_load_sec": rounded(seconds(e.get("load_duration"))),
        "whole_sec": rounded(whole),
        "result_sec": rounded(None if None in (result, load) else result - load),
        "first_token_sec": answer.get("first_token_sec"),
        "documents": row.get("documents"),
        "prompt_est_tokens": row.get("prompt_est_tokens"),
        "eval_est_tokens": row.get("eval_est_tokens"),
        "answer_chars": row.get("answer_chars"),
        "answer_sha256": row.get("answer_sha256"),
        "prompt_sha256": row.get("prompt_sha256"),
        "eval_prompt_sha256": row.get("eval_prompt_sha256"),
        "score": row.get("score"),
        "quality_source": row.get("quality_source"),
        "route": row.get("route"),
        "ps_size": ps.get("size"),
        "ps_size_vram": ps.get("size_vram"),
        "context_length": ps.get("context_length"),
        "unload_sec": (row.get("unload") or {}).get("unload_sec"),
        "loadavg_before": before.get("loadavg"),
        "loadavg_after": after.get("loadavg"),
        "swap_before_mb": before.get("swap_used_mb"),
        "swap_after_mb": after.get("swap_used_mb"),
    }


# --- the series ---


def say(out: Path, text: str) -> None:
    line = f"{now()} {text}"
    print(line, flush=True)
    with (out / "series.log").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def environment_line(out: Path, tag: str) -> None:
    """V4's reading of the stand's environment (its stand_env.py: the Ollama server, the
    interpreter's distributions), with whether a llama.cpp config.ini is present."""
    sys.path.insert(0, str(WS / "reports" / "answer-prompt-v4" / "tools"))
    import stand_env

    line = {
        "tag": tag,
        "taken": now(),
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "ollama": stand_env.ollama(),
        "distributions": stand_env.distributions(),
        "llama_config": LLAMA_CONFIG.exists(),
    }
    with (out / "environment.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def busy(first: bool) -> list[str]:
    """What keeps the Mac from a block by step 0's rule; empty when it is idle. The model a
    block left loaded is no reason; before a series' first block the 5-minute load is one."""
    why = []
    names = foreign()
    if names:
        why.append("processes: " + ", ".join(names))
    try:
        held = models()
    except (OSError, ValueError) as exc:
        held = []
        why.append(f"Ollama does not answer: {type(exc).__name__}")
    if any(model != MODEL for model in held):
        why.append("another model in Ollama")
    if llama_servers() > (1 if held else 0):
        why.append("a llama-server of no model of the series")
    if CI_LOCK.exists():
        why.append("the CI lock")
    if first and os.getloadavg()[1] >= 2:
        why.append(f"the 5-minute load is {os.getloadavg()[1]:.2f}")
    return why


def wait_idle(out: Path, first: bool) -> bool:
    waited = 0
    while True:
        why = busy(first)
        if not why:
            return True
        if waited >= IDLE_WAIT_SEC:
            say(out, f"STOP: not idle after {waited} s: " + "; ".join(why))
            return False
        say(out, "waiting: " + "; ".join(why))
        time.sleep(IDLE_POLL_SEC)
        waited += IDLE_POLL_SEC


def unload_quietly(out: Path) -> None:
    try:
        say(out, f"unloaded: {unload()}")
    except (OSError, TimeoutError, ValueError) as exc:
        say(out, f"the unload failed: {type(exc).__name__}")


def series(out: Path, v4_stand: Path) -> int:
    if not (out / "inputs.json").exists():
        print(f"no {out / 'inputs.json'}: run inputs first", file=sys.stderr)
        return 6
    for name in ("OLLAMA_CONTEXT_WINDOW", "OLLAMA_BASE_URL"):
        if os.environ.get(name):
            say(out, f"STOP: {name} is set where the series runs")
            return 6
    if git("status", "--porcelain", "--untracked-files=normal"):
        say(out, "STOP: the worktree is not clean")
        return 6
    facts = series_facts(out, v4_stand)
    state_path = out / "series.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if {key: state.get(key) for key in facts} != facts:
            say(out, "STOP: the series was started with other facts")
            return 6
    else:
        state = {**facts, "started": now()}
        write_json(state_path, state)
    for name in ("blocks", "answers", "rejected"):
        (out / name).mkdir(exist_ok=True)
    cases = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    attempts_path = out / "attempts.json"
    attempts = (
        json.loads(attempts_path.read_text(encoding="utf-8")) if attempts_path.exists() else {}
    )
    environment_line(out, "start")
    first = True
    for plan in BLOCKS:
        number = plan["block"]
        path = block_path(out, number)
        if path.exists():
            continue
        if (out / "stop").exists():
            say(out, "STOP: the stop file")
            return 3
        if not wait_idle(out, first):
            return 4
        first = False
        tries = attempts.get(str(number), 0)
        if tries >= MAX_ATTEMPTS:
            say(out, f"STOP: block {number} failed {tries} times")
            return 9
        attempts[str(number)] = tries + 1
        write_json(attempts_path, attempts)
        say(out, f"block {number}: {plan['case_id']} at {plan['window']}, attempt {tries + 1}")
        command = [sys.executable, str(Path(__file__).resolve()), "block"]
        command += [str(out), str(v4_stand), str(number)]
        env = {**os.environ, "OLLAMA_CONTEXT_WINDOW": str(plan["window"])}
        try:
            code = subprocess.run(command, env=env, timeout=BLOCK_CAP_SEC).returncode
        except subprocess.TimeoutExpired:
            say(out, f"STOP: block {number} ran past {BLOCK_CAP_SEC} s")
            unload_quietly(out)
            return 5
        if code:
            say(out, f"STOP: block {number} exited {code}")
            unload_quietly(out)
            return code
        row = json.loads(path.read_text(encoding="utf-8"))
        why = gate(row, plan, case_of(cases, plan["case_id"]), state)
        if why:
            path.replace(out / "rejected" / f"{path.stem}-{tries + 1}.json")
            say(out, f"STOP: block {number}'s gate: " + "; ".join(why))
            unload_quietly(out)
            return 8
        numbers = block_numbers(row)
        say(
            out,
            f"block {number} read: prompts {numbers['prompt_sec']} s, result "
            f"{numbers['result_sec']} s, load {numbers['load_sec']} s; disturbed: "
            + ("; ".join(disturbed(row)) or "no"),
        )
    environment_line(out, "end")
    unload_quietly(out)
    say(out, "SERIES_DONE")
    return 0


# --- the reading ---


def sign_p(wins: int, losses: int) -> float:
    """The exact two-sided sign test at one half."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


COMPARED = ("prompt_sec", "whole_sec", "result_sec")
BESIDE = (
    "prompt_sec",
    "answer_prompt_sec",
    "eval_prompt_sec",
    "answer_prompt_tokens",
    "eval_prompt_tokens",
    "answer_tokens",
    "eval_tokens",
    "answer_gen_sec",
    "load_sec",
    "whole_sec",
    "result_sec",
    "documents",
    "prompt_est_tokens",
    "score",
    "route",
    "answer_sha256",
    "ps_size",
)


def pair_up(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each question's two blocks; a pair is readable when both passed their gates undisturbed
    and the question is not the first, which pairs with nothing."""
    pairs = []
    for position, case_id in enumerate(CASES, start=1):
        sides = {
            row["window"]: row for row in rows if row["position"] == position and row["present"]
        }
        why = []
        for window in WINDOWS:
            row = sides.get(window)
            if row is None:
                why.append(f"no block at {window}")
            elif row["gate"]:
                why.append(f"the block at {window} failed its gate")
            elif row["disturbed"]:
                why.append(f"the block at {window} was disturbed")
        first = BLOCKS[2 * (position - 1)]["window"]
        pair: dict[str, Any] = {
            "position": position,
            "case_id": case_id,
            "first": first,
            "warm_up": position == 1,
            "readable": position > 1 and not why,
            "why": why,
        }
        for window in WINDOWS:
            for name in BESIDE:
                pair[f"w{window}_{name}"] = (sides.get(window) or {}).get(name)
        if not why:
            for name in COMPARED:
                today, small = sides[TODAY][name], sides[SMALL][name]
                known = None not in (today, small)
                pair[f"{name}_saving"] = rounded(today - small) if known else None
                pair[f"{name}_ratio"] = rounded(small / today) if known and today else None
        pairs.append(pair)
    return pairs


def compared(readable: list[dict[str, Any]], name: str) -> dict[str, Any]:
    savings = [pair[f"{name}_saving"] for pair in readable]
    wins = sum(1 for value in savings if value is not None and value > 0)
    losses = sum(1 for value in savings if value is not None and value < 0)
    return {
        "small_faster": wins,
        "small_slower": losses,
        "sign_p": round(sign_p(wins, losses), 6),
        "median_saving_sec": median(savings),
        "median_ratio": median([pair[f"{name}_ratio"] for pair in readable]),
    }


def at_windows(readable: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return {f"w{w}": median([pair[f"w{w}_{name}"] for pair in readable]) for w in WINDOWS}


def rate(readable: list[dict[str, Any]], tokens: str, sec: str) -> dict[str, Any]:
    return {
        f"w{w}": median(
            [
                pair[f"w{w}_{tokens}"] / pair[f"w{w}_{sec}"]
                for pair in readable
                if pair[f"w{w}_{tokens}"] and pair[f"w{w}_{sec}"]
            ]
        )
        for w in WINDOWS
    }


def readings(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """The spec's answer and what stands beside it, from the readable pairs alone."""
    readable = [pair for pair in pairs if pair["readable"]]
    prompt = compared(readable, "prompt_sec")
    if len(readable) < MIN_PAIRS:
        answer = NOT_EVIDENCE
    elif prompt["small_faster"] > prompt["small_slower"] and prompt["sign_p"] < ALPHA:
        answer = "faster"
    elif prompt["small_slower"] > prompt["small_faster"] and prompt["sign_p"] < ALPHA:
        answer = "slower"
    else:
        answer = "no detected difference"
    token_saving = {
        call: median(
            [
                pair[f"w{TODAY}_{call}_prompt_tokens"] - pair[f"w{SMALL}_{call}_prompt_tokens"]
                for pair in readable
            ]
        )
        for call in ("answer", "eval")
    }
    by_order = {
        f"w{first}_first": {
            "pairs": len([pair for pair in readable if pair["first"] == first]),
            "median_prompt_saving_sec": median(
                [pair["prompt_sec_saving"] for pair in readable if pair["first"] == first]
            ),
        }
        for first in WINDOWS
    }
    warm_up = pairs[0]
    return {
        "answer": answer,
        "readable_questions": len(readable),
        "small_faster": prompt["small_faster"],
        "small_slower": prompt["small_slower"],
        "sign_p": prompt["sign_p"],
        "median_prompt_saving_sec": prompt["median_saving_sec"],
        "median_prompt_ratio": prompt["median_ratio"],
        "printed_deciding_nothing": {
            "whole": compared(readable, "whole_sec"),
            "result": compared(readable, "result_sec"),
            "median_prompt_sec": at_windows(readable, "prompt_sec"),
            "median_result_sec": at_windows(readable, "result_sec"),
            "median_answer_prompt_tokens": at_windows(readable, "answer_prompt_tokens"),
            "median_eval_prompt_tokens": at_windows(readable, "eval_prompt_tokens"),
            "median_prompt_token_saving": token_saving,
            "median_answer_prompt_rate": rate(
                readable, "answer_prompt_tokens", "answer_prompt_sec"
            ),
            "median_answer_tokens": at_windows(readable, "answer_tokens"),
            "median_generation_rate": rate(readable, "answer_tokens", "answer_gen_sec"),
            "median_load_sec": at_windows(readable, "load_sec"),
            "median_ps_size": at_windows(readable, "ps_size"),
            "routes": {
                f"w{w}": {
                    route: sum(1 for pair in readable if pair[f"w{w}_route"] == route)
                    for route in ("auto", "human")
                }
                for w in WINDOWS
            },
            "scores_parsed": {
                f"w{w}": sum(1 for pair in readable if pair[f"w{w}_score"] not in (None, -1))
                for w in WINDOWS
            },
            "same_route": sum(
                1 for pair in readable if pair[f"w{TODAY}_route"] == pair[f"w{SMALL}_route"]
            ),
            "same_answer": sum(
                1
                for pair in readable
                if pair[f"w{TODAY}_answer_sha256"] == pair[f"w{SMALL}_answer_sha256"]
            ),
            "by_order": by_order,
            "warm_up": {
                f"w{w}": {
                    name: warm_up[f"w{w}_{name}"]
                    for name in ("prompt_sec", "result_sec", "load_sec")
                }
                for w in WINDOWS
            },
        },
    }


def environment(out: Path) -> dict[str, Any]:
    """The stand's environment lines, as one: the servers, versions and interpreters seen."""
    path = out / "environment.jsonl"
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {
        "lines": len(lines),
        "tags": [line["tag"] for line in lines],
        "server_versions": sorted({str(line["ollama"].get("server_version")) for line in lines}),
        "servers": sorted(
            {
                f"{server['pid']} {server['started']}"
                for line in lines
                for server in line["ollama"].get("servers") or []
            }
        ),
        "python_versions": sorted({line["python_version"] for line in lines}),
        "freeze_sha256": sorted({line["distributions"]["freeze_sha256"] for line in lines}),
        "packages": sorted(
            {json.dumps(line["distributions"]["versions"], sort_keys=True) for line in lines}
        ),
        "llama_config": any(line["llama_config"] for line in lines),
    }


def read(out: Path, record_dir: Path) -> int:
    stage2_tools = str(WS / "reports" / "stage2" / "tools")
    if stage2_tools not in sys.path:
        sys.path.insert(0, stage2_tools)
    from stage2_common import without_text

    if record_dir.exists():
        print(f"refused: {record_dir} exists", file=sys.stderr)
        return 2
    state = json.loads((out / "series.json").read_text(encoding="utf-8"))
    inputs_value = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    if sha256(out / "inputs.json") != state["inputs_sha256"]:
        print("refused: inputs.json is not the series'", file=sys.stderr)
        return 2
    rows = []
    for plan in BLOCKS:
        path = block_path(out, plan["block"])
        row: dict[str, Any] = {**plan, "present": path.exists()}
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            row.update(block_numbers(value))
            row["gate"] = gate(value, plan, case_of(inputs_value, plan["case_id"]), state)
            row["disturbed"] = disturbed(value)
        rows.append(row)
    pairs = pair_up(rows)
    attempts_path = out / "attempts.json"
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "series": {key: state[key] for key in ("code_sha", "tool_sha256", "started")},
        "reader_sha256": sha256(Path(__file__)),
        "inputs": {
            "sha256": state["inputs_sha256"],
            "step4_rows_sha256": inputs_value["step4_rows_sha256"],
            "code_sha": inputs_value["code_sha"],
            "cases": [
                {key: case[key] for key in ("position", "case_id", "index", "prompts")}
                for case in inputs_value["cases"]
            ],
        },
        "model": {"name": MODEL, "digest": DIGEST, "ollama_version": OLLAMA_VERSION},
        "windows": list(WINDOWS),
        "environment": environment(out),
        "attempts": (
            json.loads(attempts_path.read_text(encoding="utf-8")) if attempts_path.exists() else {}
        ),
        "rejected": sorted(path.name for path in (out / "rejected").glob("*.json")),
        "pairs": pairs,
        "readings": readings(pairs),
    }
    names = {
        document["metadata"].get("source")
        for case in inputs_value["cases"]
        for document in case["plain"]
    } - {None}
    questions = [case["question"] for case in inputs_value["cases"]]
    without_text(record, names, questions)
    without_text(rows, names, questions)
    record_dir.mkdir(parents=True)
    write_json(record_dir / "record.json", record)
    (record_dir / "rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    print(json.dumps(record["readings"], ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else ""
    if command == "inputs" and len(args) == 4:
        return inputs(Path(args[1]), Path(args[2]), Path(args[3]))
    if command == "series" and len(args) == 3:
        return series(Path(args[1]), Path(args[2]))
    if command == "block" and len(args) == 4:
        return block(Path(args[1]), Path(args[2]), int(args[3]))
    if command == "read" and len(args) == 3:
        return read(Path(args[1]), Path(args[2]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
