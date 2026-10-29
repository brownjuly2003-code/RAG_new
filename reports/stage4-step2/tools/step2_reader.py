"""Stage 4, step 2's reader: each question's two self-evaluations of its one answer, the pairs.

docs/specs/stage4-step2-self-eval-continuation.md, registered with this tool before the first
request. On the Mac after the run, any Python 3.11, the standard library only:

  python -I step2_reader.py OUT RUN_DIR [--corpus DIR]

RUN_DIR is the directory this folder's live_supervisor.py writes for a run in mode prod with
STREAMING_SELF_EVAL_MODE=both, its drivers two levels up. Each question of the run (an ask) gets
live_runner.py's test of a delivered answer; the two self-evaluations of that answer its result
event carries in `self_eval_both` - the continuation, whose score the result reports as its
quality and routes by, and the classic, the call the code made before step 2 - each with its
score, its seconds and Ollama's counters; its spans in stages.jsonl, start and end paired per
stage and thread: the answer's stream and the model calls after it; and, printed, the
supervisor's memory samples within it. An ask is read when its answer was delivered and
streamed without an error and both self-evaluations are in its result with a score and seconds;
the continuation held when it scored 1-100 and the result's quality, that quality's source and
the route are that score's. A pair, the two self-evaluations of one read ask of a run whose
gate passed, sets the continuation's cost - its seconds, with the classic's added where it did
not hold, as the code then falls back to the classic - against the classic's seconds; its
routes are compared where the continuation held and the classic scored 1-100. The readings are
functions of the pairs alone; the first ask's stop, of the first ask alone, read while the run
goes on.

OUT holds numbers, enums, ids, model names, the paths named here and SHA-256 strings: no
question, answer, prompt, source name or log line, and of an error its type only. Prints the
gate, the first ask's stop and the spec's readings; refuses an existing OUT.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA = "stage4-step2/v1"
SPEC = "docs/specs/stage4-step2-self-eval-continuation.md"
HERE = Path(__file__).resolve().parent
TOOLS = ("step2_reader.py",)
NOT_EVIDENCE = "NOT_EVIDENCE"
# The stand's commit: the code with the continuation (config/settings.py,
# streaming_self_eval_mode), archived whole to the Mac.
CODE_SHA = "57420db746e0510465bb5a08b7610e092b32e650"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
TENANT = "aircargo"
# The registered run: step 3's thirteen aircargo questions, in their order. A rerun stands in
# its place, labelled "-r2".
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
LABELS = ("s2-both", "s2-both-r2")
MODE = "both"
# What the run must have run, two levels above its directory: V4's live_api.py, step 1's
# live_runner.py and this folder's live_supervisor.py.
DRIVERS_SHA256 = {
    "live_api.py": "43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5",
    "live_runner.py": "c87838014a0517d5e6a3dde0402ed0b067a9e0148aaf5d842ffe272ca451a072",
    "live_supervisor.py": "0de222a762085f49f2455e813a50895fd88826f687683be2d6cb814926da9132",
}
# V4's settings, which step 2 keeps (the code defaults: K = 20 candidates, five kept, the CPU,
# the 4B), and the stream's self-evaluation: on, a score of 80 or more routed to auto.
SETTINGS = {
    "retrieval_top_k": 20,
    "rerank_top_k": 5,
    "rag_device": "cpu",
    "streaming_quality_eval": True,
    "quality_threshold": 80,
    "ollama_model_name": MODEL,
}
# Printed beside them, deciding nothing.
CONTEXT_SETTINGS = {"suggested_questions_enabled": True, "ollama_context_window": 0}
SIDES = ("continuation", "classic")
COUNTERS = ("prompt_tokens", "prompt_sec", "eval_tokens", "eval_sec")
STREAM = "ollama.generate_stream"
GENERATE = "ollama.generate"
STAGES = (STREAM, GENERATE)
# The provider's calls after the answer, by their output limit (llm/role_params.py): the
# classic's role, evaluate, and the suggestions', suggest. Printed, deciding nothing.
CALLS = {128: "classic", 256: "suggestions"}
LAUNCH_KEYS = (
    "label",
    "mode",
    "cases",
    "client_cap_sec",
    "started",
    "workspace",
    "code_sha",
    "overrides",
    "model",
    "model_digest",
    "tenant",
    "chroma_dir",
    "cases_file",
    "arm",
    "status",
    "runner_exit",
    "ollama_load_sec",
    "ollama_models_before",
    "ollama_models_after",
    "unloaded_models",
)
RUN_FILES = ("launch.json", "effective_settings.json", "stages.jsonl", "resources.jsonl")
CORPUS_FILES = ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
# The spec's readings, frozen with it.
THRESHOLD = 80
MIN_PAIRS = 10
ALPHA = 0.05
ROUTE_DIFFS = 1
MISSES = 1
FIRST_RATIO = 0.5
MIN_SAVING_SEC = 30.0


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def median(values: Sequence[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def num(value: Any) -> int | float | None:
    """A number as it is; anything else (a bool included) is None."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def an_id(value: Any) -> str | None:
    """A case id as it is; anything else masked (a warmup's id carries its question after ":")."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.-]+", str(value)) else "<not an id>"


def a_name(value: Any) -> str | None:
    """A model name or an enum as it is (a tag holds ":"); anything else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.:/-]+", str(value)) else "<not a name>"


def error_type(value: Any) -> str | None:
    """An error's type, the text before its first colon; never its message."""
    if value is None or value is False:
        return None
    head = str(value).split(":", 1)[0].strip()
    return head if re.fullmatch(r"[A-Za-z_][\w.]*", head) else "<error>"


def diff(later: Any, earlier: Any) -> float | None:
    later, earlier = num(later), num(earlier)
    return later - earlier if later is not None and earlier is not None else None


def rounded(value: float | None, places: int = 3) -> float | None:
    return None if value is None else round(value, places)


def a_score(value: Any) -> int | None:
    """A self-evaluation's score, an integer as it is (-1 is the code's "no score"); else None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def scored(value: Any) -> bool:
    return a_score(value) is not None and 1 <= value <= 100


def route_of(score: int) -> str:
    """The route the stream gives a model's score (api/routers/conversation.py)."""
    return "auto" if score >= THRESHOLD else "human"


def sign_p(wins: int, losses: int) -> float:
    """The exact two-sided sign test at one half."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def span_fields(begun: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """The numbers a model call's span keeps from its start and end rows; never a text."""
    return {
        "error": error_type(row.get("error")),
        "prompt_est_tokens": num(begun.get("prompt_est_tokens")),
        "max_tokens": num(begun.get("max_tokens")),
        "first_chunk_sec": num(row.get("first_chunk_sec")),
        "chunks": num(row.get("chunks")),
    }


def read_spans(path: Path, notes: list[str]) -> list[dict[str, Any]]:
    """The observed model calls of stages.jsonl, start and end paired per stage and thread."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        notes.append("run: no stages.jsonl")
        return []
    started: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    spans = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else {}
        except ValueError:
            notes.append("run: an unreadable stages.jsonl line")
            continue
        if row.get("stage") not in STAGES or num(row.get("monotonic")) is None:
            continue
        key = (row["stage"], row.get("thread"))
        if row.get("event") == "start":
            started.setdefault(key, []).append(row)
        elif row.get("event") == "end" and started.get(key):
            begun = started[key].pop(0)
            span = {"stage": row["stage"], "start": num(begun.get("monotonic"))}
            span.update(end=row["monotonic"], wall=num(row.get("wall_sec")))
            span.update(span_fields(begun, row))
            spans.append(span)
    left = Counter(stage for (stage, _), rows in started.items() for _ in rows)
    for stage, count in sorted(left.items()):
        notes.append(f"run: {count} {stage} started and never ended")
    spans.sort(key=lambda span: span["start"] if span["start"] is not None else float("inf"))
    return spans


def read_side(value: Any) -> dict[str, Any] | None:
    """One self-evaluation of `self_eval_both`: its score, its seconds, Ollama's counters."""
    if not isinstance(value, dict):
        return None
    sec = num(value.get("sec"))
    out: dict[str, Any] = {"score": a_score(value.get("score"))}
    out["sec"] = sec if sec is not None and sec >= 0 else None
    out.update({key: num(value.get(key)) for key in COUNTERS})
    return out


def read_cases(folder: Path, notes: list[str]) -> list[dict[str, Any]]:
    """Each case's id, position, times, tokens, route, quality and two self-evaluations; never a
    question or an answer."""
    cases = []
    for path in sorted(folder.glob("*.json")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            notes.append(f"run: case file {path.name} unreadable")
            continue
        events = [event for event in case.get("events") or [] if isinstance(event, dict)]
        result = next((event for event in events if event.get("type") == "result"), {})
        head = re.match(r"(\d+)-", path.name)
        row: dict[str, Any] = {"case_id": an_id(case.get("case_id"))}
        row["index"] = int(head.group(1)) if head else None
        keys = ("t0_monotonic", "total_sec", "first_token_sec", "last_token_sec", "result_sec")
        row.update({key: num(case.get(key)) for key in keys})
        row.update(tokens=num(case.get("tokens")), http_status=num(case.get("http_status")))
        for key in ("route", "quality_source", "answer_source", "generation_source"):
            row[key] = a_name(result.get(key)) if isinstance(result.get(key), str) else None
        row["quality_score"] = num(result.get("quality_score"))
        suggested = result.get("suggested_questions")
        row["suggested"] = len(suggested) if isinstance(suggested, list) else None
        both = result.get("self_eval_both")
        row["self_eval"] = {
            side: read_side(both.get(side)) if isinstance(both, dict) else None for side in SIDES
        }
        row.update(client_error="client_error" in case)
        # live_runner.py's own test of a delivered answer
        row["answered"] = bool(
            (row["tokens"] or 0) > 0
            and "result_sec" in case
            and row["route"] != "timeout"
            and not row["client_error"]
            and "error_sec" not in case
        )
        cases.append({**row, "sha256": sha256(path)})
    if not cases:
        notes.append("run: no case files")
    return cases


def swap_used_mib(text: Any) -> float | None:
    """The swap in use from vm.swapusage's line, as stage 2's tools read it."""
    match = re.search(r"used = ([0-9.]+)M", text if isinstance(text, str) else "")
    return float(match.group(1)) if match else None


def read_resources(path: Path, notes: list[str]) -> list[dict[str, Any]]:
    """The supervisor's samples, one each 3 s: the swap in use, the swap-outs so far and the
    largest process whose name holds "llama" (Ollama's server or its runner); never a name."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        notes.append("run: no resources.jsonl")
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else {}
        except ValueError:
            notes.append("run: an unreadable resources.jsonl line")
            continue
        if not isinstance(row, dict) or num(row.get("monotonic")) is None:
            continue
        procs = [proc for proc in row.get("procs") or [] if isinstance(proc, list)]
        sizes = [num(proc[2]) for proc in procs if len(proc) == 4 and "llama" in str(proc[3])]
        known = [size for size in sizes if size is not None]
        sample = {"monotonic": row["monotonic"], "swap_used_mib": swap_used_mib(row.get("swap"))}
        sample["swapouts"] = num(row.get("swapouts"))
        sample["llama_rss_mib"] = round(max(known) / 2**20, 1) if known else None
        rows.append(sample)
    rows.sort(key=lambda sample: sample["monotonic"])
    return rows


def memory_of(
    samples: list[dict[str, Any]], low: float | None, high: float | None
) -> dict[str, Any] | None:
    """The samples within an ask: the swap in use at the first and the last, the swap-outs
    between them and the largest llama process. Printed, deciding nothing."""
    if low is None or high is None:
        return None
    inside = [sample for sample in samples if low <= sample["monotonic"] <= high]
    if not inside:
        return {"samples": 0}
    first, last = inside[0], inside[-1]
    sizes = [sample["llama_rss_mib"] for sample in inside if sample["llama_rss_mib"] is not None]
    return {
        "samples": len(inside),
        "swap_used_mib": [first["swap_used_mib"], last["swap_used_mib"]],
        "swapouts": diff(last["swapouts"], first["swapouts"]),
        "llama_rss_mib_max": max(sizes) if sizes else None,
    }


def assign(spans: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[int, list[Any]]:
    """A span belongs to the last case begun before it starts, if it starts before that case's
    last event: a later question's spans, its case file not yet written, belong to none."""
    timed = sorted(
        (case for case in cases if case["t0_monotonic"] is not None),
        key=lambda case: case["t0_monotonic"],
    )
    starts = [case["t0_monotonic"] for case in timed]
    groups: dict[int, list[Any]] = {id(case): [] for case in timed}
    for span in spans:
        at = bisect.bisect_right(starts, span["start"]) - 1 if span["start"] is not None else -1
        if at < 0:
            continue
        case = timed[at]
        if case["total_sec"] is None or span["start"] <= case["t0_monotonic"] + case["total_sec"]:
            groups[id(case)].append(span)
    return groups


def held(ask: dict[str, Any]) -> list[str]:
    """Why the continuation did not hold; empty when it did: it scored 1-100, and the result's
    quality, that quality's source and the route are that score's."""
    side = ask["self_eval"]["continuation"]
    score = a_score(side["score"]) if side else None
    if score is None or not 1 <= score <= 100:
        return ["no continuation score of 1-100"]
    why = []
    if ask["quality_score"] != score:
        why.append("the result's quality is not the continuation's score")
    if ask["quality_source"] != "llm":
        why.append("the result's quality is not the model's")
    if ask["route"] != route_of(score):
        why.append("the result's route is not the continuation score's")
    return why


def read_ask(
    case: dict[str, Any], spans: list[dict[str, Any]], samples: list[dict[str, Any]]
) -> dict[str, Any]:
    """One question of the run: its answer's call, the calls after it, its two
    self-evaluations, its memory, whether it is read and whether the continuation held."""
    t0 = case["t0_monotonic"]
    count = Counter(span["stage"] for span in spans)
    streams = [span for span in spans if span["stage"] == STREAM]
    answer = streams[0] if len(streams) == 1 else None
    keys = ("case_id", "index", "sha256", "answered", "route", "tokens", "http_status")
    ask: dict[str, Any] = {key: case[key] for key in keys}
    more = ("quality_score", "quality_source", "answer_source", "generation_source", "suggested")
    ask.update({key: case[key] for key in more})
    ask.update(total_sec=case["total_sec"], first_token_sec=case["first_token_sec"])
    ask["self_eval"] = case["self_eval"]
    ask["spans"] = {stage: count.get(stage, 0) for stage in STAGES}
    end = t0 + case["total_sec"] if t0 is not None and case["total_sec"] is not None else None
    ask["memory"] = memory_of(samples, t0, end)
    ask["answer_call"] = None
    ask["after_answer"] = []
    if answer:
        ask["answer_call"] = {
            "offset_sec": rounded(diff(answer["start"], t0)),
            "wall_sec": rounded(answer["wall"]),
            "first_chunk_sec": rounded(answer["first_chunk_sec"]),
            "prompt_est_tokens": answer["prompt_est_tokens"],
            "error": answer["error"],
        }
        later = [
            span
            for span in spans
            if span["stage"] == GENERATE
            and span["start"] is not None
            and answer["end"] is not None
            and span["start"] >= answer["end"]
        ]
        ask["after_answer"] = [
            {
                "call": CALLS.get(span["max_tokens"], "other"),
                "offset_sec": rounded(diff(span["start"], answer["end"])),
                "wall_sec": rounded(span["wall"]),
                "prompt_est_tokens": span["prompt_est_tokens"],
                "max_tokens": span["max_tokens"],
                "error": span["error"],
            }
            for span in later
        ]
    why = []
    if not case["answered"]:
        why.append("no delivered answer")
    if answer is None or answer["error"]:
        why.append("not one answer stream, or a failed one")
    for side in SIDES:
        found = ask["self_eval"][side]
        if (
            found is None
            or found["sec"] is None
            or not (found["score"] == -1 or scored(found["score"]))
        ):
            why.append(f"no {side} self-evaluation with a score and seconds")
    ask["unread"] = why
    ask["read"] = not why
    ask["continuation_not_held"] = held(ask)
    ask["continuation_held"] = ask["read"] and not ask["continuation_not_held"]
    return ask


def read_settings(path: Path, notes: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The settings the API served, its self-evaluation's mode and its code's commit, as
    live_api.py wrote them; and the settings printed beside them."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        notes.append("run: no readable effective_settings.json")
        return {}, {}
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    every = data.get("all") if isinstance(data.get("all"), dict) else {}
    code = data.get("code") if isinstance(data.get("code"), dict) else {}

    def typed(found: Any, like: Any) -> Any:
        if isinstance(like, bool):
            return found if isinstance(found, bool) else None
        if isinstance(like, str):
            return a_name(found) if isinstance(found, str) else None
        return num(found)

    out = {key: typed(settings.get(key), value) for key, value in SETTINGS.items()}
    out["streaming_self_eval_mode"] = typed(every.get("streaming_self_eval_mode"), MODE)
    out["code_sha"] = typed(code.get("code_sha"), CODE_SHA)
    context = {key: typed(settings.get(key), like) for key, like in CONTEXT_SETTINGS.items()}
    return out, context


def read_run(run_dir: Path) -> dict[str, Any]:
    notes: list[str] = []
    try:
        launch = json.loads((run_dir / "launch.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        notes.append("run: no readable launch.json")
        launch = {}
    kept = {key: launch[key] for key in LAUNCH_KEYS if key in launch}
    for key in ("cases", "ollama_models_before", "ollama_models_after", "unloaded_models"):
        if isinstance(kept.get(key), list):
            kept[key] = [(an_id if key == "cases" else a_name)(item) for item in kept[key]]
    for key in ("label", "arm", "model", "model_digest", "mode", "status", "tenant", "code_sha"):
        if key in kept:
            kept[key] = a_name(kept[key])
    if "overrides" in kept:
        overrides = kept["overrides"] if isinstance(kept["overrides"], dict) else {}
        kept["overrides"] = {str(k): a_name(v) for k, v in sorted(overrides.items())}
    overrides = kept.get("overrides") or {}
    cases = read_cases(run_dir / "cases", notes)
    spans = read_spans(run_dir / "stages.jsonl", notes)
    groups = assign(spans, cases)
    samples = read_resources(run_dir / "resources.jsonl", notes)
    asks = [read_ask(case, groups.get(id(case), []), samples) for case in cases]
    asks.sort(key=lambda ask: ask["index"] if ask["index"] is not None else 0)
    settings, context = read_settings(run_dir / "effective_settings.json", notes)
    drivers = {name: sha256(run_dir.parent.parent / name) for name in DRIVERS_SHA256}
    gate = {
        "launch": kept.get("code_sha") == CODE_SHA
        and kept.get("label") in LABELS
        and kept.get("mode") == "prod"
        and kept.get("status") == "complete"
        and kept.get("runner_exit") == 0
        and kept.get("model") == MODEL
        and kept.get("tenant") == TENANT
        and kept.get("cases") == list(CASES)
        and kept.get("ollama_models_before") == []
        and "arm" not in kept
        and overrides.get("STREAMING_SELF_EVAL_MODE") == MODE
        and overrides.get("RAG_RETRIEVAL_TOP_K", "20") == "20",
        "settings": settings
        == {**SETTINGS, "streaming_self_eval_mode": MODE, "code_sha": CODE_SHA},
        "drivers": drivers == DRIVERS_SHA256,
        "asks": [(ask["index"], ask["case_id"]) for ask in asks] == list(enumerate(CASES, start=1)),
    }
    gate["passed"] = all(gate.values())
    return {
        "dir": str(run_dir),
        "label": kept.get("label"),
        "launch": kept,
        "settings": settings,
        "settings_printed": context,
        "sha256": {name: sha256(run_dir / name) for name in RUN_FILES},
        "drivers_sha256": drivers,
        "asks": asks,
        "gate": gate,
        "notes": notes,
    }


def pair_of(ask: dict[str, Any], passed: bool) -> dict[str, Any]:
    """An ask's two self-evaluations as a pair, readable when the run's gate passed and the ask
    is read: the continuation's cost - its seconds, with the classic's added where it did not
    hold, as the code then falls back - against the classic's seconds; its routes compared where
    the continuation held and the classic scored 1-100."""
    continuation, classic = (ask["self_eval"][side] for side in SIDES)
    why = [] if passed else ["the run's gate did not pass"]
    if not ask["read"]:
        why.append("its ask is not read")
    pair: dict[str, Any] = {"case_id": ask["case_id"], "index": ask["index"]}
    pair.update(readable=not why, unreadable=why)
    if why:
        return pair
    holds = ask["continuation_held"]
    sec = {"continuation": continuation["sec"], "classic": classic["sec"]}
    cost = sec["continuation"] + (0 if holds else sec["classic"])
    pair.update(held=holds, sec=sec, cost_sec=rounded(cost))
    pair["saving_sec"] = rounded(sec["classic"] - cost)
    pair["ratio"] = rounded(cost / sec["classic"], 4) if sec["classic"] else None
    score = {"continuation": continuation["score"], "classic": classic["score"]}
    uncompared = [] if holds else ["the continuation did not hold"]
    if not scored(classic["score"]):
        uncompared.append("no classic score of 1-100")
    pair.update(score=score, compared=not uncompared, uncompared=uncompared)
    if not uncompared:
        routes = {side: route_of(score[side]) for side in SIDES}
        pair.update(score_diff=score["continuation"] - score["classic"], routes=routes)
        pair["routes_differ"] = routes["continuation"] != routes["classic"]
    # the first call of each kind after the answer
    calls = {call["call"]: call["wall_sec"] for call in reversed(ask["after_answer"])}
    pair["printed"] = {
        "counters": {
            side: {key: ask["self_eval"][side][key] for key in COUNTERS} for side in SIDES
        },
        "answer_wall_sec": (ask["answer_call"] or {}).get("wall_sec"),
        "classic_call_wall_sec": calls.get("classic"),
        "suggestions_wall_sec": calls.get("suggestions"),
        "total_sec": ask["total_sec"],
        "first_token_sec": ask["first_token_sec"],
        "memory": ask["memory"],
    }
    return pair


def first_ask(asks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The spec's stop after the first question, read while the run goes on: the run stops
    unless its first ask is the first question's, read, with the continuation held and its
    seconds under half the classic's."""
    ask = next((ask for ask in asks if ask["index"] == 1), None)
    out: dict[str, Any] = {"case_id": ask["case_id"] if ask else None, "ratio": None}
    if ask is None or ask["case_id"] != CASES[0]:
        why = ["no first ask of the first question"]
    else:
        pair = pair_of(ask, True)
        why = list(pair["unreadable"])
        if pair["readable"]:
            out.update(ratio=pair["ratio"], sec=pair["sec"], score=pair["score"])
            out.update(counters=pair["printed"]["counters"], memory=pair["printed"]["memory"])
            if not pair["held"]:
                why.append("the continuation did not hold")
            elif pair["ratio"] is None or pair["ratio"] >= FIRST_RATIO:
                why.append("the continuation took half the classic's seconds or more")
        out.update(unread=ask["unread"], continuation_not_held=ask["continuation_not_held"])
    out.update(stop=bool(why), why=why)
    return out


def readings(pairs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The spec's readings, functions of the pairs alone: the speed and its use over the
    readable pairs, the routes over the compared ones, the continuation's misses."""
    readable = [pair for pair in pairs if pair["readable"]]
    enough = len(readable) >= MIN_PAIRS
    savings = [pair["saving_sec"] for pair in readable]
    wins = sum(saving > 0 for saving in savings)
    losses = sum(saving < 0 for saving in savings)
    p_value = sign_p(wins, losses)
    speed = NOT_EVIDENCE
    if enough:
        speed = "no difference"
        if p_value < ALPHA:
            speed = "faster" if wins > losses else "slower"
    median_saving = median(savings)
    useful = NOT_EVIDENCE
    if enough and median_saving is not None:
        useful = "useful" if median_saving >= MIN_SAVING_SEC else "not useful"
    compared = [pair for pair in readable if pair["compared"]]
    differ = [pair["case_id"] for pair in compared if pair["routes_differ"]]
    routes = NOT_EVIDENCE
    if len(compared) >= MIN_PAIRS:
        routes = "agree" if len(differ) <= ROUTE_DIFFS else "differ"
    missed = [pair["case_id"] for pair in readable if not pair["held"]]
    scores = NOT_EVIDENCE
    if enough:
        scores = "held" if len(missed) <= MISSES else "not held"
    candidate = NOT_EVIDENCE
    if NOT_EVIDENCE not in (speed, useful, routes, scores):
        adopt = (speed, useful, routes, scores) == ("faster", "useful", "agree", "held")
        candidate = "continuation" if adopt else "classic"
    ratios = [pair["ratio"] for pair in readable if pair["ratio"] is not None]

    def printed(key: str, side: str | None = None) -> float | None:
        values = [
            pair["printed"][key] if side is None else pair["printed"]["counters"][side][key]
            for pair in readable
        ]
        return median([value for value in values if value is not None])

    memories = [pair["printed"]["memory"] or {} for pair in readable]
    swaps = [swap for memory in memories for swap in memory.get("swap_used_mib") or []]
    sizes = [memory.get("llama_rss_mib_max") for memory in memories]
    outs = [memory["swapouts"] for memory in memories if memory.get("swapouts") is not None]
    diffs = [pair["score_diff"] for pair in compared]
    return {
        "speed": {
            "answer": speed,
            "readable_pairs": len(readable),
            "continuation_faster": wins,
            "continuation_slower": losses,
            "ties": len(readable) - wins - losses,
            "sign_p": round(p_value, 6),
            "median_ratio": rounded(statistics.median(ratios), 4) if ratios else None,
            "savings_sec": {pair["case_id"]: pair["saving_sec"] for pair in readable},
            "ratios": {pair["case_id"]: pair["ratio"] for pair in readable},
        },
        "useful": {
            "answer": useful,
            "median_saving_sec": median_saving,
            "least_median_saving_sec": MIN_SAVING_SEC,
        },
        "routes": {
            "answer": routes,
            "compared_pairs": len(compared),
            "differ": len(differ),
            "differing": differ,
        },
        "scores": {
            "answer": scores,
            "readable_pairs": len(readable),
            "missed": len(missed),
            "misses": missed,
        },
        "candidate": {"answer": candidate},
        "printed_deciding_nothing": {
            "total_saving_sec": rounded(sum(savings)) if savings else None,
            "worst_saving_sec": min(savings) if savings else None,
            "median_cost_sec": median([pair["cost_sec"] for pair in readable]),
            "median_classic_sec": median([pair["sec"]["classic"] for pair in readable]),
            "median_score": {
                side: median([pair["score"][side] for pair in compared]) for side in SIDES
            },
            "median_score_diff": median(diffs),
            "continuation_scored": {
                "higher": sum(d > 0 for d in diffs),
                "same": sum(d == 0 for d in diffs),
                "lower": sum(d < 0 for d in diffs),
            },
            "scores": {pair["case_id"]: pair["score"] for pair in readable},
            "median_counters": {
                side: {key: printed(key, side) for key in COUNTERS} for side in SIDES
            },
            "median_answer_wall_sec": printed("answer_wall_sec"),
            "median_classic_call_wall_sec": printed("classic_call_wall_sec"),
            "median_suggestions_wall_sec": printed("suggestions_wall_sec"),
            "median_total_sec": printed("total_sec"),
            "median_first_token_sec": printed("first_token_sec"),
            "continuation_routes": dict(
                sorted(Counter(pair["routes"]["continuation"] for pair in compared).items())
            ),
            "classic_routes": dict(
                sorted(Counter(pair["routes"]["classic"] for pair in compared).items())
            ),
            "memory": {
                "swap_used_mib_max": max((s for s in swaps if s is not None), default=None),
                "llama_rss_mib_max": max((s for s in sizes if s is not None), default=None),
                "swapouts": sum(outs) if outs else None,
            },
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("run_dir")
    parser.add_argument("--corpus")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"refused: {out} exists", file=sys.stderr)
        return 2
    run = read_run(Path(args.run_dir))
    pairs = [pair_of(ask, run["gate"]["passed"]) for ask in run["asks"]]
    corpus = None
    if args.corpus:
        folder = Path(args.corpus)
        corpus = {"dir": str(folder), "sha256": {n: sha256(folder / n) for n in CORPUS_FILES}}
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "corpus": corpus,
        "tools_sha256": {name: sha256(HERE / name) for name in TOOLS},
        "run": run,
        "first_ask": first_ask(run["asks"]),
        "pairs": pairs,
        "readings": readings(pairs),
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"gate": run["gate"], "first_ask": record["first_ask"]}, sort_keys=True))
    print(json.dumps(record["readings"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
