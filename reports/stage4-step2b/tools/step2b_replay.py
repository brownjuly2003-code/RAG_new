"""Stage 4, step 2b's replay: the continuation read cold, on step 2's answers and on V4's 80.

docs/specs/stage4-step2b-continuation-labels.md, registered with this tool before the first
request. On the Mac, in step 2's stand, whose folder step2b/ holds this tool,
by the stage's interpreter with the gate's site on its path:

  $PY step2b/step2b_replay.py check V4_RUNS PLAN LABELS STEP2_RUNS
  $PY step2b/step2b_replay.py bridge V4_RUNS STEP2_RUNS OUT [--first]
  $PY step2b/step2b_replay.py run V4_RUNS PLAN LABELS OUT [--first]

V4_RUNS holds V4's runs v4-aircargo-b01 ... b10 of stand 4f48fed: each answer's saved stream
prompt (prompts/NNN-stream.txt), its case file (cases/NN-<case>.json: the answer as it streamed
and the result event) and stages.jsonl; the stand's settings are held to its first run's. PLAN
is the handover signals' plan (reports/handover-signal/d260d95/plan.json): each answer's files
and the SHA-256 of its prompt and its answer. LABELS are the judge's grades
(reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl). STEP2_RUNS holds step 2's
runs s2-both and s2-both-r2, laid out as V4's.

bridge: each answer step 2 delivered, its runs in their order - live_runner.py's delivered
answer, whose result holds both self-evaluations - asked again, cold. Step 2 asked its
continuation warm, in the slot that had just streamed it; the reader sets the two side by side.
Its first turn is the run's own stream prompt, the one of V4's text that holds the case's
question; its answer the case's, which live_runner.py joined from the stream's token events.
run: the 80, the 17 targets (graded bad, or declined) and the 63 goods (graded good, not
declined), signal_record.py's classes: the targets first, each class in the plan's order. Each
answer's prompt is rebuilt by V5's replay (reports/answer-prompt-v5/tools/replay.py, loaded from
its file and used as it is): the question and documents of the saved prompt, the chat's own
fitting, and the rebuilt prompt, flattened as the provider stream sent it, is the saved file
byte for byte.

Each continuation is the chat's own (api/routers/conversation.py), its helpers in
_stream_continuation_self_eval's order: the first turn as the answer's stream path sent it
(_answer_request_text), the answer as it streamed, unstripped, and SELF_EVAL_CONTINUATION_V1
(_continuation_self_eval_messages); the window check (_continuation_input_limit); one /api/chat
call to the stream model's own OllamaProvider (_answer_stream_ollama, ProviderBackedLLM) with
the evaluate role's kwargs; the strict parse (_parse_continuation_score) and the entry
(_self_eval_entry). Its outcome is kept, which the chat's function folds into -1.

check: every answer's checks and its continuation's estimate, the bridge's and then the 80's,
no model call, a JSON line an answer on stdout and the counts on stderr; exit 3 if a check
fails. bridge and run: check, then each answer's continuation, one at a time, into
OUT/continuations.jsonl, a line an answer: ids, checks, the outcome, the score (-1: none), the
seconds and Ollama's counters; never a question, document, prompt, answer or reply, and of an
error its type only. OUT/launch.json keeps what the first segment froze (FROZEN: the stand,
the model and its digest, the tools' and the inputs' SHA-256, the window, the plan's sizes)
and each segment; a line names the segment that wrote it. A resume goes on after the lines
kept; one that would change a frozen value, or whose kept lines are not the plan's first, is
refused (exit 6). --first asks one answer and stops (exit 0). A segment loads the model before
its first answer. Before answers n = 6, 11, ..., 76 that a segment does not start with, it
unloads it, reads /api/ps and ps until neither holds it - ps counts every llama-server on the
host - and loads it again, the line keeping the seconds ("reload"): llama-server's host prompt
cache, which keeps each continuation's state, goes with its process. A segment ends with the
model unloaded the same way, before launch.json closes it: the seconds, or the error's type,
in the segment, whose exit stands. Exit 4: an answer took longer than ANSWER_STOP seconds
(kept; the replay stops); 5: the stop file OUT/step2b.stop; 6: the settings, the model, the
window or the instruction are not the spec's, or a resume is not its launch's; 7: an answer's
call failed (kept as the outcome "error", its type also in OUT/failures.jsonl; a resume goes on
with the next answer); 8: the model's unload or load failed, or the model or a llama-server
outlasted the unload by UNLOAD_LIMIT_SEC s (the error's type in the segment, no line; a resume
loads the model again); 9: at a segment's start Ollama held a model or a llama-server ran
(nothing written; a resume waits for an idle Mac).
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS = next(p for p in HERE.parents if (p / "agent" / "prompts.py").exists())
sys.path.insert(0, str(WS))

SCHEMA = "stage4-step2b/v1"
SPEC = "docs/specs/stage4-step2b-continuation-labels.md"
KEY = "aircargo"
# V5's replay and the template its Builder reads, as committed: their reading of V4's runs and
# their rebuild of V4's prompts, used as they are.
V5_TOOLS = WS / "reports" / "answer-prompt-v5" / "tools"
TOOLS = {
    "step2b_replay.py": Path(__file__).resolve(),
    "replay.py": V5_TOOLS / "replay.py",
    "qa_prompt_v5.txt": V5_TOOLS / "qa_prompt_v5.txt",
}
# V4's and step 2's answers streamed by the provider: each saved prompt is the flattened turn
# OllamaProvider.generate_stream sent (reports/stage2/tools/live_api.py).
STREAM_PATH = "provider"
USER_HEAD = "USER:\n"  # flatten_messages' head of the one user turn the provider's stream sent
PROMPT_ID = "SELF_EVAL_CONTINUATION_V1"
INSTRUCTION_SHA256 = "5062156de04ad24c573d9d6161a81aeb34fae4c82ba49e7f537dabff4104000c"
# The num_ctx V4's and step 2's answers were streamed at, and the continuation's input limit
# there with the evaluate role's 128 tokens (conversation._continuation_input_limit).
NUM_CTX = 4096
INPUT_LIMIT = 3443
PARAMS = {"temperature": 0.0, "max_tokens": 128}
TARGETS, GOODS = 17, 63
# Step 2's runs in their order: the registered run and its rerun (amendment 1).
STEP2_LABELS = ("s2-both", "s2-both-r2")
# 3x the forecast's longest answer, 85 s.
ANSWER_STOP = 255.0
# Each cold continuation leaves its state, ~400 MiB, in llama-server's host prompt cache, up to
# 8,192 MiB on a Mac of 8 GB: a reload every 5 answers keeps it under ~2 GiB.
RELOAD_EVERY = 5
# One deadline for an unload: its request, each /api/ps and ps read, and the polls.
UNLOAD_LIMIT_SEC = 120.0
POLL_SEC = 0.5
PS = ("/bin/ps", "-axo", "pid=,rss=,comm=")  # step 1's listing (stage4-step1's live_runner.py)
STOP = "step2b.stop"
FILES = ("launch.json", "continuations.jsonl", "failures.jsonl")
CHECKS = ("files", "prompt_sha256", "parity", "sent", "answer", "answer_sha256", "stream")
# The bridge's: one stream prompt holds the case's question; its first turn, given back to the
# chat's helper, is that prompt; the answer is the result's, from the stream; the stream's row
# holds it.
BRIDGE_CHECKS = ("files", "sent", "answer", "stream")
SIDES = ("continuation", "classic")
COUNTERS = ("prompt_tokens", "prompt_sec", "eval_tokens", "eval_sec")
# What a launch's first segment freezes.
FROZEN = (
    "schema",
    "spec",
    "phase",
    "key",
    "code_sha",
    "model",
    "model_digest",
    "stream_path",
    "prompt_id",
    "instruction_sha256",
    "num_ctx",
    "input_limit",
    "params",
    "answer_stop_sec",
    "reload_every",
    "tools_sha256",
    "inputs_sha256",
    "runs",
    "planned",
)


class ModelStop(Exception):
    """The model's unload or load failed: exit 8. Its text is the step, "unload" or "load"."""


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def a_name(value: Any) -> str | None:
    """An enum as it is (Ollama's done_reason); anything else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.:/-]+", str(value)) else "<not a name>"


@functools.cache
def v5() -> Any:
    """V5's replay (reports/answer-prompt-v5/tools/replay.py), loaded from its file."""
    spec = importlib.util.spec_from_file_location("stage4_step2b_v5_replay", TOOLS["replay.py"])
    if spec is None or spec.loader is None:
        raise SystemExit(f"no V5 replay at {TOOLS['replay.py']}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def append(path: Path, row: dict[str, Any]) -> None:
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def save(path: Path, value: dict[str, Any]) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def refused(why: str) -> int:
    print(f"refused: {why}", file=sys.stderr)
    return 6


def select(plan: dict[str, Any], labels: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The 80 answers in the replay's order: the targets - graded bad, or declined - then the
    goods - graded good, not declined - each in the plan's order (signal_record.py's classes).
    Ids, file names and SHA-256 strings only."""
    by_case = {(row["run"], row["case_id"]): row for row in labels}
    targets, goods = [], []
    for item in plan["items"]:
        row = by_case.get((item["run"], item["case_id"]))
        if row is None or row["prompt_sha256"] != item["prompt_sha256"] or row["missing"]:
            raise SystemExit(f"{item['case_id']}: the judge graded another answer, or none")
        if row["grade"] == "bad" or row["answers_question"] == "declined":
            targets.append(item)
        elif row["grade"] == "good":
            goods.append(item)
    if len(by_case) != len(plan["items"]):
        raise SystemExit("the judge holds answers the plan does not")
    if (len(targets), len(goods)) != (TARGETS, GOODS):
        raise SystemExit(f"{len(targets)} targets and {len(goods)} goods, not the spec's")
    order = [("target", item) for item in targets] + [("good", item) for item in goods]
    keys = ("item", "run", "case_id", "case_file", "prompt_file", "prompt_sha256", "answer_sha256")
    return [
        {"phase": "labels", "n": n, "class": kind, **{key: item[key] for key in keys}}
        for n, (kind, item) in enumerate(order, start=1)
    ]


def continuation(prompt: str, answer: str, *, stream_path: str | None) -> list[dict[str, str]]:
    """The continuation's three turns by the chat's own helpers: the first as the answer's stream
    path sent it, the answer as it streamed, the instruction."""
    from agent.prompts import build_self_eval_continuation_prompt
    from api.routers import conversation as chat

    return chat._continuation_self_eval_messages(
        chat._answer_request_text(prompt, stream_path=stream_path),
        answer,
        build_self_eval_continuation_prompt(),
    )


def request(
    streaming_llm: Any,
    *,
    stream_path: str | None,
    settings: Any,
    context_window: Any,
    prompt: str,
    answer: str,
) -> dict[str, Any]:
    """One continuation as conversation._stream_continuation_self_eval sends it, its helpers in
    its order, in this thread rather than a worker's: the line's numbers, its outcome ("scored",
    "not one integer", "window" or "error") and of an error its type."""
    from api.routers import conversation as chat
    from llm.providers.base import ProviderBackedLLM, estimate_window_tokens, flatten_messages
    from llm.role_params import generation_kwargs_for_role

    ollama = chat._answer_stream_ollama(
        streaming_llm, stream_path=stream_path, settings=settings, context_window=context_window
    )
    if ollama is None:
        raise SystemExit(f"the stream path {stream_path!r} names no Ollama provider")
    messages = continuation(prompt, answer, stream_path=stream_path)
    params = generation_kwargs_for_role("evaluate")
    num_ctx = int(ollama.context_window)
    est_input_tokens = estimate_window_tokens(flatten_messages(messages))
    limit = chat._continuation_input_limit(num_ctx, int(params["max_tokens"]))
    fields: dict[str, Any] = {
        "num_ctx": num_ctx,
        "est_input_tokens": est_input_tokens,
        "input_limit": limit,
        "error": None,
        "reply_chars": None,
        "done_reason": None,
    }
    if est_input_tokens > limit:
        # The chat sends nothing: Ollama would drop the first turn without an error.
        return {**fields, "outcome": "window", **chat._self_eval_entry(-1, 0.0)}
    chat_llm = ProviderBackedLLM(ollama)
    started = time.perf_counter()
    try:
        response = chat_llm.generate_chat(messages, **params)
    except Exception as exc:
        entry = chat._self_eval_entry(-1, time.perf_counter() - started)
        return {**fields, "outcome": "error", "error": type(exc).__name__, **entry}
    entry = chat._self_eval_entry(
        chat._parse_continuation_score(response.text),
        time.perf_counter() - started,
        response.metadata,
    )
    fields.update(reply_chars=len(response.text or ""), done_reason=a_name(response.finish_reason))
    return {**fields, "outcome": "scored" if entry["score"] != -1 else "not one integer", **entry}


def setup(runs: Path) -> tuple[Any, Any, dict[str, Any]]:
    """The stream model and the settings, held against V4's first run (V5's
    provider_and_settings: exit 6 if not V4's), and the continuation the stand makes of them:
    its provider, window, kwargs and instruction. Exit 6 if one is not the spec's."""
    from agent.prompts import PROMPT_REGISTRY, build_self_eval_continuation_prompt
    from api.routers import conversation as chat
    from llm.providers.ollama import OllamaProvider
    from llm.role_params import generation_kwargs_for_role

    replay = v5()
    llm, settings = replay.provider_and_settings(runs, KEY)
    provider = chat._answer_stream_ollama(
        llm,
        stream_path=STREAM_PATH,
        settings=settings,
        context_window=getattr(llm, "context_window", None),
    )
    params = generation_kwargs_for_role("evaluate")
    registered = PROMPT_REGISTRY["self_eval_continuation"]
    instruction = build_self_eval_continuation_prompt()
    differ = []
    if (
        not isinstance(provider, OllamaProvider)
        or provider.model_name != replay.MODEL
        or provider.context_window != NUM_CTX
        or chat._continuation_input_limit(NUM_CTX, int(params["max_tokens"])) != INPUT_LIMIT
    ):
        differ.append("the continuation's provider or window")
    if params != PARAMS:
        differ.append("the evaluate role's kwargs")
    if (
        instruction != registered["text"]
        or registered["prompt_id"] != PROMPT_ID
        or replay.digest(instruction) != INSTRUCTION_SHA256
    ):
        differ.append("the instruction")
    if differ:
        print("not the spec's: " + ", ".join(differ), file=sys.stderr)
        raise SystemExit(6)
    values: dict[str, Any] = {"prompt_id": PROMPT_ID, "instruction_sha256": INSTRUCTION_SHA256}
    values.update(num_ctx=NUM_CTX, input_limit=INPUT_LIMIT, params=params)
    return llm, settings, values


def stream_holds(row: dict[str, Any], case: dict[str, Any], text: str) -> bool:
    """The stand's stream row of the prompt holds the answer: no error, as many chunks as the
    case's token events and as many characters as its answer."""
    return (
        bool(row)
        and row.get("error") is None
        and row.get("chunks") == case.get("tokens")
        and row.get("output_chars") == len(text)
    )


def result_of(case: dict[str, Any]) -> dict[str, Any]:
    events = [event for event in case.get("events") or [] if isinstance(event, dict)]
    return next((event for event in events if event.get("type") == "result"), {})


def prepare(
    builder: Any, runs: Path, chosen: Sequence[dict[str, Any]]
) -> list[tuple[dict[str, Any], str, str]]:
    """Each chosen answer's line with its checks, and - kept in memory, never written - the
    prompt the chat passed to its stream and the answer as it streamed."""
    from api.routers import conversation as chat

    replay = v5()
    cases = {
        (batch, case["case_id"]): (name, case, saved)
        for batch, name, case, saved in replay.v4_cases(runs, KEY)
    }
    streams: dict[str, dict[str, Any]] = {}
    out = []
    for answer in chosen:
        checks = dict.fromkeys(CHECKS, False)
        prompt, text = "", ""
        found = cases.get((answer["run"], answer["case_id"]))
        if found is not None:
            name, case, (prompt_file, saved) = found
            checks["files"] = (name, prompt_file) == (answer["case_file"], answer["prompt_file"])
            checks["prompt_sha256"] = replay.digest(saved) == answer["prompt_sha256"]
            question, documents = replay.read_saved(saved)
            prompt, flat, _ = builder.build(builder.v4, question, documents)
            checks["parity"] = flat == saved
            checks["sent"] = chat._answer_request_text(prompt, stream_path=STREAM_PATH) == saved
            result = result_of(case)
            given = case.get("answer")
            text = given if isinstance(given, str) else ""
            checks["answer"] = bool(text) and result.get("answer") == text
            checks["answer"] = checks["answer"] and result.get("answer_source") == "stream"
            checks["answer_sha256"] = replay.digest(text.strip()) == answer["answer_sha256"]
            if answer["run"] not in streams:
                streams[answer["run"]] = replay.streams(Path(runs) / answer["run"])
            checks["stream"] = stream_holds(
                streams[answer["run"]].get(prompt_file) or {}, case, text
            )
        line = {**answer, "sent_answer_sha256": replay.digest(text), "answer_chars": len(text)}
        out.append(({**line, "checks": checks, "stream_path": STREAM_PATH}, prompt, text))
    return out


def delivered(case: dict[str, Any], result: dict[str, Any]) -> bool:
    """live_runner.py's test of a delivered answer: streamed tokens and a result event that is
    not a timeout, without any error."""
    return bool(
        isinstance(case.get("tokens"), int)
        and case["tokens"] > 0
        and "result_sec" in case
        and result.get("route") != "timeout"
        and "client_error" not in case
        and "error_sec" not in case
    )


def warm_side(value: Any) -> dict[str, Any] | None:
    """One of the two self-evaluations step 2's result holds, as its reader reads one: a score
    of -1 (none) or 1-100 and the seconds, Ollama's counters beside them; else None."""
    if not isinstance(value, dict):
        return None
    score, sec = value.get("score"), value.get("sec")
    if not isinstance(score, int) or isinstance(score, bool):
        return None
    if not (score == -1 or 1 <= score <= 100):
        return None
    if not isinstance(sec, (int, float)) or isinstance(sec, bool) or sec < 0:
        return None
    return {"score": score, "sec": sec, **{key: value.get(key) for key in COUNTERS}}


def bridge_items(step2: Path) -> list[tuple[dict[str, Any], str, str]]:
    """The bridge's answers - the asks step 2's reader reads: a delivered answer whose result
    holds both self-evaluations, read - step 2's runs in their order and each run's cases in
    theirs: each a line with its ids, its warm continuation and its checks and - kept in
    memory, never written - the prompt its stream was given and the answer as it streamed."""
    from api.routers import conversation as chat

    replay = v5()
    out: list[tuple[dict[str, Any], str, str]] = []
    for label in STEP2_LABELS:
        run = Path(step2) / label
        prompts: dict[str, list[tuple[str, str]]] = {}
        for path in sorted((run / "prompts").glob("*-stream.txt")):
            # Bytes, not read_text: its newline translation would send other white space.
            saved = path.read_bytes().decode("utf-8")
            if replay.V4_MARK in saved:
                question, _ = replay.read_saved(saved)
                prompts.setdefault(question, []).append((path.name, saved))
        streams = replay.streams(run)
        for path in sorted((run / "cases").glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            result = result_of(case)
            both = result.get("self_eval_both")
            warm = {
                side: warm_side(both.get(side)) if isinstance(both, dict) else None
                for side in SIDES
            }
            if str(case.get("case_id")).startswith("warmup-") or not delivered(case, result):
                continue
            if not all(warm.values()):
                continue
            found = prompts.get(case.get("question"), [])
            prompt_file, saved = found[0] if len(found) == 1 else (None, "")
            # The provider's stream sent USER_HEAD and the prompt stripped: the prompt is the rest.
            prompt = saved[len(USER_HEAD) :] if saved.startswith(USER_HEAD) else ""
            given = case.get("answer")
            text = given if isinstance(given, str) else ""
            checks = {
                "files": prompt_file is not None,
                "sent": bool(prompt)
                and chat._answer_request_text(prompt, stream_path=STREAM_PATH) == saved,
                "answer": bool(text)
                and result.get("answer") == text
                and result.get("answer_source") == "stream",
                "stream": stream_holds(streams.get(prompt_file or "") or {}, case, text),
            }
            line: dict[str, Any] = {"phase": "bridge", "n": len(out) + 1, "run": label}
            line.update(case_id=case.get("case_id"), case_file=path.name, prompt_file=prompt_file)
            line.update(case_sha256=sha256(path), prompt_sha256=replay.digest(saved))
            line.update(answer_sha256=replay.digest(text.strip()))
            line.update(sent_answer_sha256=replay.digest(text), answer_chars=len(text))
            line.update(warm=warm["continuation"], checks=checks, stream_path=STREAM_PATH)
            out.append((line, prompt, text))
    return out


def llama_servers(timeout: float = 20.0) -> int:
    """How many processes ps lists, host-wide, whose executable's base name is llama-server, as
    step 1 counts them (no path or argument kept); a failed ps raises."""
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


def unload(replay: Any) -> dict[str, Any]:
    """The model unloaded (keep_alive 0), then /api/ps and ps read every POLL_SEC s until Ollama
    holds no model and no llama-server is left: the seconds and the polls. One deadline,
    UNLOAD_LIMIT_SEC after the start, bounds the request, each read and the polls: past it a
    TimeoutError."""
    started = time.monotonic()
    deadline = started + UNLOAD_LIMIT_SEC

    def left(cap: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"the model or a llama-server {UNLOAD_LIMIT_SEC} s after the unload")
        return min(cap, remaining)

    replay.ollama("/api/generate", {"model": replay.MODEL, "keep_alive": 0}, left(60.0))
    polls = 0
    while True:
        polls += 1
        held = replay.ollama("/api/ps", None, left(10.0)).get("models")
        if not held and not llama_servers(left(20.0)):
            return {"unload_sec": round(time.monotonic() - started, 3), "polls": polls}
        time.sleep(POLL_SEC)


def estimate(prompt: str, text: str) -> int:
    from llm.providers.base import estimate_window_tokens, flatten_messages

    turns = continuation(prompt, text, stream_path=STREAM_PATH)
    return int(estimate_window_tokens(flatten_messages(turns)))


def drive(
    out: Path,
    items: Sequence[tuple[dict[str, Any], str, str]],
    frozen: dict[str, Any],
    ask: Callable[[str, str], dict[str, Any]],
    *,
    first: bool,
) -> int:
    """The continuations of `items` after the lines kept, one at a time, a segment of the
    launch in OUT, as the module says: the exit."""
    replay = v5()
    out.mkdir(parents=True, exist_ok=True)
    launch_path, lines_path, failures_path = (out / name for name in FILES)
    try:
        kept = read_jsonl(lines_path)
        launch = (
            json.loads(launch_path.read_text(encoding="utf-8")) if launch_path.exists() else None
        )
    except ValueError:
        return refused("a kept line or launch.json is no JSON")
    if launch is None:
        if kept:
            return refused("lines kept without a launch")
        launch = {**frozen, "started": now(), "finished": None, "model_errors": 0, "segments": []}
    elif launch.get("status") == "complete":
        return 0
    else:
        changed = [key for key in FROZEN if launch.get(key) != frozen[key]]
        if changed:
            return refused("not the launch's: " + ", ".join(changed))
    if len(kept) > len(items) or any(
        row.get(key) != value
        for row, (line, _, _) in zip(kept, items, strict=False)
        for key, value in line.items()
    ):
        return refused("the kept lines are not the plan's first")
    before = [m.get("name") for m in replay.ollama("/api/ps").get("models", [])]
    servers = llama_servers()
    if before or servers:
        print(f"not idle: {len(before)} models in Ollama, {servers} llama-server", file=sys.stderr)
        return 9
    launch["answers"] = len(kept)
    segment: dict[str, Any] = {"started": now(), "first": first, "from_n": len(kept) + 1}
    segment.update(status="running", ollama_models_before=before, llama_servers_before=servers)
    launch["segments"] = [*launch["segments"], segment]
    launch["status"] = "running"
    index = len(launch["segments"])
    save(launch_path, launch)
    loaded = False

    def load() -> float:
        started = time.monotonic()
        replay.ollama("/api/generate", {"model": replay.MODEL, "keep_alive": "30m"}, 300)
        return round(time.monotonic() - started, 3)

    def model(step: str, call: Callable[[], Any]) -> Any:
        try:
            return call()
        except Exception as exc:
            segment[f"{step}_error"] = type(exc).__name__
            raise ModelStop(step) from exc

    def answers() -> tuple[str, int]:
        nonlocal loaded
        for line, prompt, text in items[len(kept) :]:
            if (out / STOP).exists():
                return "stopped", 5
            reload = None
            try:
                if not loaded:
                    loaded = True
                    segment["ollama_load_sec"] = model("load", load)
                elif (line["n"] - 1) % RELOAD_EVERY == 0:
                    reload = model("unload", lambda: unload(replay))
                    reload["load_sec"] = model("load", load)
            except ModelStop as stop:
                return f"{stop}_stop", 8
            begun = now()
            got = ask(prompt, text)
            stamps = {"segment": index, "started": begun, "finished": now(), "reload": reload}
            append(lines_path, {**line, **stamps, **got})
            launch["answers"] += 1
            if got["outcome"] == "error":
                ids = {name: line[name] for name in ("n", "run", "case_id")}
                append(
                    failures_path, {**ids, "error": got["error"], "sec": got["sec"], "at": now()}
                )
                launch["model_errors"] += 1
                return "model_error", 7
            if got["sec"] > ANSWER_STOP:
                return "answer_stop", 4
            if first:
                return "first", 0
        return "complete", 0

    status, code = "crashed", 1
    try:
        status, code = answers()
    except BaseException as exc:
        segment["crash"] = type(exc).__name__
        raise
    finally:
        if loaded:
            try:
                segment["final_unload"] = unload(replay)
            except Exception as exc:
                segment["final_unload_error"] = type(exc).__name__
        segment.update(status=status, finished=now())
        launch["status"] = status
        if status == "complete":
            launch["finished"] = segment["finished"]
        save(launch_path, launch)
    return code


def start(
    phase: str,
    runs: Path,
    items: Sequence[tuple[dict[str, Any], str, str]],
    out: Path,
    model: tuple[Any, Any, dict[str, Any]],
    *,
    inputs: dict[str, str],
    planned: dict[str, int],
    first: bool,
) -> int:
    """Exit 3 if an answer's check failed and 6 for another model digest, before anything is
    written; else the phase's launch, frozen as FROZEN names it, and its drive."""
    failed = [line["n"] for line, _, _ in items if not all(line["checks"].values())]
    if failed or not items:
        print(f"checks failed: answers {failed}, of {len(items)}", file=sys.stderr)
        return 3
    replay = v5()
    tags = {m.get("name"): m.get("digest") for m in replay.ollama("/api/tags").get("models", [])}
    if tags.get(replay.MODEL) != replay.DIGEST:
        return refused("the model's digest is not the spec's")
    llm, settings, values = model
    frozen: dict[str, Any] = {"schema": SCHEMA, "spec": SPEC, "phase": phase, "key": KEY}
    frozen.update(code_sha=(WS / "CODE_SHA").read_text(encoding="utf-8").strip())
    frozen.update(model=replay.MODEL, model_digest=tags[replay.MODEL], stream_path=STREAM_PATH)
    frozen.update(answer_stop_sec=ANSWER_STOP, reload_every=RELOAD_EVERY)
    frozen.update(tools_sha256={name: sha256(path) for name, path in TOOLS.items()})
    frozen.update(inputs_sha256=inputs, runs=str(Path(runs).resolve()), planned=planned)
    frozen.update(values)

    def ask(prompt: str, text: str) -> dict[str, Any]:
        return request(
            llm,
            stream_path=STREAM_PATH,
            settings=settings,
            context_window=getattr(llm, "context_window", None),
            prompt=prompt,
            answer=text,
        )

    return drive(Path(out), items, frozen, ask, first=first)


def check(runs: Path, plan: Path, labels: Path, step2: Path) -> int:
    model = setup(runs)
    chosen = select(json.loads(Path(plan).read_text(encoding="utf-8")), read_jsonl(labels))
    groups = (
        ("bridge", bridge_items(step2)),
        ("answers", prepare(v5().Builder(model[0]), runs, chosen)),
    )
    failed_any = False
    for name, items in groups:
        failed = past = 0
        for line, prompt, text in items:
            est = estimate(prompt, text)
            print(json.dumps({**line, "est_input_tokens": est, "input_limit": INPUT_LIMIT}))
            failed += not all(line["checks"].values())
            past += est > INPUT_LIMIT
        print(f"CHECK {name} {len(items)} failed {failed} past_the_window {past}", file=sys.stderr)
        failed_any = failed_any or failed > 0
    return 3 if failed_any else 0


def bridge(runs: Path, step2: Path, out: Path, *, first: bool = False) -> int:
    model = setup(runs)
    items = bridge_items(step2)
    planned = {label: sum(line["run"] == label for line, _, _ in items) for label in STEP2_LABELS}
    return start("bridge", step2, items, out, model, inputs={}, planned=planned, first=first)


def run(runs: Path, plan: Path, labels: Path, out: Path, *, first: bool = False) -> int:
    model = setup(runs)
    chosen = select(json.loads(Path(plan).read_text(encoding="utf-8")), read_jsonl(labels))
    items = prepare(v5().Builder(model[0]), runs, chosen)
    inputs = {"plan": sha256(plan), "labels": sha256(labels)}
    planned = {"targets": TARGETS, "goods": GOODS}
    return start("labels", runs, items, out, model, inputs=inputs, planned=planned, first=first)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    named = {
        "check": ("runs", "plan", "labels", "step2"),
        "bridge": ("runs", "step2", "out"),
        "run": ("runs", "plan", "labels", "out"),
    }
    for command, names in named.items():
        sub = commands.add_parser(command)
        for name in names:
            sub.add_argument(name, type=Path)
        if command != "check":
            sub.add_argument("--first", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(args.runs, args.plan, args.labels, args.step2)
    if args.command == "bridge":
        code = bridge(args.runs, args.step2, args.out, first=args.first)
    else:
        code = run(args.runs, args.plan, args.labels, args.out, first=args.first)
    print(f"REPLAY exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
