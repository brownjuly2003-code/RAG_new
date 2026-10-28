"""Stage 4, step 1's reader: each question's retrieval and arm, the samples inside, the pairs.

docs/specs/stage4-step1-rerank-memory.md, registered with this tool before the first request.
On the Mac after a run, any Python 3.11, the standard library only:

  python -I step1_reader.py OUT --run SAMPLES RUN_DIR [--run SAMPLES RUN_DIR ...] [--corpus DIR]

A run is one file of step 0's sampler (step0_sampler.py, unchanged, beside this reader) and the
chat run it watched: the directory this folder's live_supervisor.py writes, its drivers two
levels up. Each question of a run (an ask) gets its registered arm and the action live_runner.py
took before it (its seconds, polls, the models Ollama held before and after and B's count of
llama-server processes); its spans in stages.jsonl, start and end paired per stage and thread
(the retrieval, its vector search and its rerank, the rerank's pool, the retriever's build, the
answer's stream and the other model calls); and the samples surely inside its retrieval, vector
search and rerank: their count, the counters' change from the first to the last, the pages
faulted back (page-ins plus decompressions) and the llama-server pids of the samples ps read.
An ask's arm held when (A) Ollama held the served model alone before and after the action and
every sample inside its retrieval lists one and the same llama-server, or (B) neither a model
in Ollama nor a llama-server process outlasted the unload and no sample inside its retrieval
lists one; at least one sample inside, either way. The two asks of one question, one in each
arm, make a pair; the readings are functions of the readable pairs alone.

OUT holds numbers, enums, ids, model names, the paths named here and SHA-256 strings: no
question, answer, prompt, source name or log line, and of an error its type only. Prints the
spec's readings; refuses an existing OUT.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

SCHEMA = "stage4-step1/v1"
SPEC = "docs/specs/stage4-step1-rerank-memory.md"
SAMPLES_SCHEMA = "stage4-step0-samples/v1"
HERE = Path(__file__).resolve().parent
TOOLS = ("step1_reader.py", "step0_sampler.py")
NOT_EVIDENCE = "NOT_EVIDENCE"
MIB = 1048576
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
# The registered runs: aircargo's registered order after step 0's five, each question once in
# each arm, at the same position in both runs. A rerun keeps its run's arms, labelled "-r2".
CASES = (
    "aircargo-dismissal-order",
    "aircargo-leave-sources",
    "aircargo-leave-compensation",
    "aircargo-leave-risk",
)
ARMS = {"s1-baba": "BABA", "s1-abab": "ABAB"}
# What a run must have run, two levels above its directory (live_supervisor.py's folder):
# V4's live_api.py and this folder's two copies; and step 0's sampler, beside this reader.
DRIVERS_SHA256 = {
    "live_api.py": "43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5",
    "live_runner.py": "c87838014a0517d5e6a3dde0402ed0b067a9e0148aaf5d842ffe272ca451a072",
    "live_supervisor.py": "915ffa9e22e3165f56cd54194fe20e89c8e4146f5a10170f32094a03138fe536",
}
SAMPLER_SHA256 = "a0b3e53d78584f454d252770898efb884b77aa80f0fff1729992ec1a37c6d18c"
# V4's settings, which step 1 keeps (the code defaults: K = 20 candidates, five kept, the CPU).
SETTINGS = {"retrieval_top_k": 20, "rerank_top_k": 5, "rag_device": "cpu"}
COUNTERS = ("pageins", "pageouts", "swapins", "swapouts", "compressions", "decompressions")
RETRIEVAL = "hybrid.get_relevant_documents_with_path"
VECTOR = "hybrid._vector_search"
RERANK = "hybrid._rerank_scored_with_status"
POOL = "hybrid.rerank_pool"
BUILD = "vectordb.manager.get_retriever"
STREAM = "ollama.generate_stream"
GENERATE = "ollama.generate"
STAGES = (RETRIEVAL, VECTOR, RERANK, POOL, BUILD, STREAM, GENERATE)
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
RUN_FILES = ("launch.json", "effective_settings.json", "stages.jsonl")
CORPUS_FILES = ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
# Sample notes that tell of nothing wrong: no model process, or one gone between ps and top.
QUIET_NOTES = ("ps: no process named llama-server", "top: no row for pid ")
# top may fail outright, not only miss a row, when a pid it is given is gone: quiet only in a
# sample one of whose llama-servers the next sample no longer lists (B's unload, a run's end).
TOP_FAILED = "top: failed"
# The spec's readings, frozen with it.
CONTENTION_RATIO = 0.5
MIN_PAIRS = 3


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


def ratio(top: Any, bottom: Any) -> float | None:
    top, bottom = num(top), num(bottom)
    return top / bottom if top is not None and bottom else None


def diff(later: Any, earlier: Any) -> float | None:
    later, earlier = num(later), num(earlier)
    return later - earlier if later is not None and earlier is not None else None


def rounded(value: float | None, places: int = 3) -> float | None:
    return None if value is None else round(value, places)


def quiet(note: str) -> bool:
    return note == QUIET_NOTES[0] or note.startswith(QUIET_NOTES[1])


def pids_of(row: dict[str, Any]) -> list[int]:
    """The llama-server pids a sample's ps listed."""
    procs = [proc for proc in row.get("procs") or [] if isinstance(proc, dict)]
    return sorted({proc["pid"] for proc in procs if num(proc.get("pid")) is not None})


def loud_notes(rows: list[dict[str, Any]]) -> dict[str, int]:
    """The sample notes that tell of something wrong, counted: all but the quiet ones, and but
    TOP_FAILED where one of the sample's llama-servers is gone by the next sample."""
    loud: Counter[str] = Counter()
    for row, after in pairwise([*rows, {}]):
        gone = set(pids_of(row)) - set(pids_of(after))
        for note in map(str, row.get("notes") or []):
            if not (quiet(note) or (note == TOP_FAILED and gone)):
                loud[note] += 1
    return dict(sorted(loud.items()))


def read_samples(path: Path, notes: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    first: dict[str, Any] = {}
    last: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        notes.append("samples: no file")
        lines = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else {}
        except ValueError:
            notes.append("samples: an unreadable line")
            continue
        if row.get("kind") == "start":
            first = row
        elif row.get("kind") == "stop":
            last = row
        elif row.get("kind") == "sample":
            rows.append(row)
    if not first:
        notes.append("samples: no start line")
    if not last:
        notes.append("samples: no stop line")
    sample_notes = Counter(note for row in rows for note in row.get("notes") or [])
    meta = {
        "file": path.name,
        "sha256": sha256(path),
        "schema": first.get("schema"),
        "every_sec": first.get("every_sec"),
        "samples": len(rows),
        "first_utc": rows[0].get("utc") if rows else None,
        "last_utc": rows[-1].get("utc") if rows else None,
        "stop_reason": last.get("reason"),
        "sample_notes": dict(sorted(sample_notes.items())),
    }
    return meta, rows


class Samples:
    """A run's samples by time: the windows between two times and the state at a moment."""

    def __init__(self, rows: list[dict[str, Any]], notes: list[str]) -> None:
        self.rows = [row for row in rows if num(row.get("monotonic")) is not None]
        if len(self.rows) < len(rows):
            notes.append(f"samples: {len(rows) - len(self.rows)} with no clock, left out")
        self.times = [row["monotonic"] for row in self.rows]
        self.ordered = all(a <= b for a, b in pairwise(self.times))
        if not self.ordered:
            notes.append("samples: the clock went down: no windows")
        sizes = [row["page_size"] for row in self.rows if num(row.get("page_size"))]
        self.page_size = sizes[0] if sizes else None

    def window(self, low: float | None, high: float | None) -> dict[str, Any] | None:
        """The samples taken between two times: their count, the llama-server pids of those ps
        read, and from two samples on the counters' change from the first to the last."""
        if low is None or high is None or not self.ordered:
            return None
        inside = self.rows[
            bisect.bisect_left(self.times, low) : bisect.bisect_right(self.times, high)
        ]
        read = [row for row in inside if "ps: failed" not in (row.get("notes") or [])]
        listed = [pids_of(row) for row in read]
        row: dict[str, Any] = {"from": round(low, 3), "to": round(high, 3), "samples": len(inside)}
        row.update(ps_read=len(read), with_llama=sum(1 for pids in listed if pids))
        row["llama_pids"] = sorted({pid for pids in listed for pid in pids})
        row["one_llama_each"] = all(len(pids) == 1 for pids in listed)
        row.update({key: None for key in COUNTERS}, sec=None, faulted_mib=None)
        row["faulted_mib_per_sec"] = None
        if len(inside) < 2:
            return row
        first, last = inside[0], inside[-1]
        row["sec"] = round(last["monotonic"] - first["monotonic"], 3)
        for key in COUNTERS:
            a, b = num((first.get("vm") or {}).get(key)), num((last.get("vm") or {}).get(key))
            row[key] = b - a if a is not None and b is not None else None
        faults = (row["pageins"], row["decompressions"])
        if self.page_size and None not in faults:
            row["faulted_mib"] = round(sum(faults) * self.page_size / MIB, 3)
            if row["sec"]:
                row["faulted_mib_per_sec"] = round(row["faulted_mib"] / row["sec"], 3)
        return row

    def state(self, moment: float | None) -> dict[str, Any] | None:
        """The last sample at or before a moment: swap, free pages, the compressor, llama-server."""
        if moment is None or not self.ordered:
            return None
        index = bisect.bisect_right(self.times, moment) - 1
        if index < 0:
            return None
        row = self.rows[index]
        vm = row.get("vm") or {}

        def mib(*keys: str) -> float | None:
            values = [num(vm.get(key)) for key in keys]
            if not self.page_size or None in values:
                return None
            return round(sum(v for v in values if v is not None) * self.page_size / MIB, 3)

        procs = [proc for proc in row.get("procs") or [] if isinstance(proc, dict)]
        mems = [num(proc.get("mem_mib")) for proc in procs]
        return {
            "ago_sec": round(moment - row["monotonic"], 3),
            "swap_used_mib": num((row.get("swap_mib") or {}).get("used")),
            "free_mib": mib("free", "speculative"),
            "compressor_mib": mib("compressor_occupied"),
            "llama_pids": pids_of(row),
            "llama_mem_mib": round(sum(m for m in mems if m is not None), 3)
            if mems and None not in mems
            else None,
        }


def span_fields(stage: str, begun: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """The numbers and enums a span keeps from its start and end rows; never a text."""
    out: dict[str, Any] = {"error": error_type(row.get("error"))}
    if stage == RETRIEVAL:
        path = row.get("path") if isinstance(row.get("path"), dict) else {}
        lanes = path.get("candidates") if isinstance(path.get("candidates"), dict) else {}
        timings = path.get("timings_ms") if isinstance(path.get("timings_ms"), dict) else {}
        out.update(docs=num(row.get("docs")), kind=a_name(path.get("kind")))
        out.update(rerank_status=a_name(path.get("rerank_status")))
        out["candidates"] = {key: num(lanes.get(key)) for key in ("vector", "bm25", "merged")}
        out["retrieved_contexts"] = num(path.get("retrieved_contexts"))
        out["retained_contexts"] = num(path.get("retained_contexts"))
        out["timings_ms"] = {a_name(key): num(value) for key, value in sorted(timings.items())}
    elif stage == RERANK:
        out.update(reranker_ok=row.get("reranker_ok") is True, docs=num(row.get("docs")))
    elif stage == POOL:
        # The candidates as a set, [source, chunk_index] each sorted by its JSON: the same set
        # is the same rerank work, whatever order near-tied fused ranks take.
        pool = row.get("pool") if isinstance(row.get("pool"), list) else []
        idents = [
            json.dumps(item[:2], ensure_ascii=False) for item in pool if isinstance(item, list)
        ]
        text = json.dumps(sorted(idents), ensure_ascii=False)
        out.update(candidates=len(pool), rerank_k=num(row.get("rerank_k")))
        out["pool_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest() if pool else None
        out["reranker_ok"] = row.get("reranker_ok") is True
    elif stage in (STREAM, GENERATE):
        out.update(prompt_est_tokens=num(begun.get("prompt_est_tokens")))
        out.update(max_tokens=num(begun.get("max_tokens")))
        out.update(first_chunk_sec=num(row.get("first_chunk_sec")), chunks=num(row.get("chunks")))
    return out


def read_spans(path: Path, notes: list[str]) -> list[dict[str, Any]]:
    """The observed stages of stages.jsonl, start and end paired per stage and thread, by start."""
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
            span.update(span_fields(row["stage"], begun, row))
            spans.append(span)
    left = Counter(stage for (stage, _), rows in started.items() for _ in rows)
    for stage, count in sorted(left.items()):
        notes.append(f"run: {count} {stage} started and never ended")
    spans.sort(key=lambda span: span["start"] if span["start"] is not None else float("inf"))
    return spans


def read_action(value: Any) -> dict[str, Any] | None:
    """live_runner.py's arm_action: its arm, polls, seconds and model names; an error's type."""
    if not isinstance(value, dict):
        return None
    out: dict[str, Any] = {"arm": value.get("arm") if value.get("arm") in ("A", "B") else None}
    out.update(polls=num(value.get("polls")), sec=num(value.get("sec")))
    out.update(done_monotonic=num(value.get("done_monotonic")))
    out["llama_servers"] = num(value.get("llama_servers"))  # B: ps's count at its last poll
    for key in ("ps_before", "ps_after"):
        names = value.get(key)
        out[key] = [a_name(name) for name in names] if isinstance(names, list) else None
    out["error"] = error_type(value.get("error"))
    return out


def read_cases(folder: Path, notes: list[str]) -> list[dict[str, Any]]:
    """Each case's id, position, times, tokens, route and arm action; never a question or an
    answer."""
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
        row.update(error_sec=num(case.get("error_sec")), drain_sec=num(case.get("drain_sec")))
        row.update(tokens=num(case.get("tokens")), http_status=num(case.get("http_status")))
        row.update(
            route=a_name(result.get("route")) if isinstance(result.get("route"), str) else None
        )
        row.update(client_error="client_error" in case, drain_error="drain_error" in case)
        # live_runner.py's own test of a delivered answer
        row["answered"] = bool(
            (row["tokens"] or 0) > 0
            and "result_sec" in case
            and row["route"] != "timeout"
            and not row["client_error"]
            and "error_sec" not in case
        )
        row["arm_action"] = read_action(case.get("arm_action"))
        cases.append({**row, "sha256": sha256(path)})
    if not cases:
        notes.append("run: no case files")
    return cases


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


def one(spans: list[dict[str, Any]], stage: str) -> dict[str, Any] | None:
    found = [span for span in spans if span["stage"] == stage]
    return found[0] if len(found) == 1 else None


def held(
    arm: str | None, action: dict[str, Any] | None, window: dict[str, Any] | None
) -> list[str]:
    """Why the ask's arm did not hold; empty when it did."""
    why = []
    if arm not in ("A", "B"):
        return ["no registered arm"]
    if action is None or action["error"] or action["arm"] != arm:
        why.append("no arm action of its arm, or a failed one")
    elif arm == "A" and (action["ps_before"] != [MODEL] or action["ps_after"] != [MODEL]):
        why.append("Ollama did not hold the served model alone")
    elif arm == "B" and (action["ps_after"] != [] or action["llama_servers"] != 0):
        why.append("a model or a llama-server outlasted the unload")
    if window is None or not window["ps_read"]:
        why.append("no sample inside the retrieval that ps read")
    elif arm == "A" and not (window["one_llama_each"] and len(window["llama_pids"]) == 1):
        why.append("not one and the same llama-server through the retrieval")
    elif arm == "B" and window["with_llama"]:
        why.append("a llama-server inside the retrieval")
    return why


def read_ask(
    case: dict[str, Any], spans: list[dict[str, Any]], samples: Samples, arm: str | None
) -> dict[str, Any]:
    """One question of a run: its stages, its arm, the samples inside, and whether it is read."""
    t0 = case["t0_monotonic"]
    action = case["arm_action"]
    count = Counter(span["stage"] for span in spans)
    retrieval, vector, rerank = one(spans, RETRIEVAL), one(spans, VECTOR), one(spans, RERANK)
    pool = one(spans, POOL)
    answer = next((span for span in spans if span["stage"] == STREAM), None)
    ask: dict[str, Any] = {key: case[key] for key in ("case_id", "index", "sha256")}
    ask["arm"] = arm
    ask.update({key: case[key] for key in ("answered", "route", "tokens", "http_status")})
    ask.update(total_sec=case["total_sec"], first_token_sec=case["first_token_sec"])
    ask["arm_action"] = action
    ask["whole_sec"] = rounded(
        case["total_sec"] + action["sec"]
        if action and action["sec"] is not None and case["total_sec"] is not None
        else None
    )
    ask["spans"] = {stage: count.get(stage, 0) for stage in STAGES}
    ask["retrieval_sec"] = rounded(retrieval["wall"]) if retrieval else None
    ask["vector_sec"] = rounded(vector["wall"]) if vector else None
    ask["rerank_sec"] = rounded(rerank["wall"]) if rerank else None
    ask["build_sec"] = rounded(sum(s["wall"] or 0 for s in spans if s["stage"] == BUILD))
    ask["retrieval_offset_sec"] = rounded(diff(retrieval["start"], t0)) if retrieval else None
    ask["path"] = (
        {key: retrieval[key] for key in ("kind", "rerank_status", "candidates", "timings_ms")}
        if retrieval
        else None
    )
    ask["reranker_ok"] = bool(rerank and rerank["reranker_ok"])
    ask["pool"] = (
        {key: pool[key] for key in ("candidates", "rerank_k", "pool_sha256")} if pool else None
    )
    ask["answer_call"] = None
    if answer:
        ask["answer_call"] = {
            "offset_sec": rounded(diff(answer["start"], t0)),
            "wall_sec": rounded(answer["wall"]),
            "first_chunk_sec": rounded(answer["first_chunk_sec"]),
            "prompt_est_tokens": answer["prompt_est_tokens"],
            "error": answer["error"],
        }
    ask["model_calls"] = count.get(STREAM, 0) + count.get(GENERATE, 0)
    ask["windows"] = {
        name: samples.window(span["start"], span["end"]) if span else None
        for name, span in (("retrieval", retrieval), ("vector", vector), ("rerank", rerank))
    }
    ask["at_rerank_start"] = samples.state(rerank["start"]) if rerank else None
    why = []
    if not case["answered"]:
        why.append("no delivered answer")
    for name, span in (("retrieval", retrieval), ("vector search", vector), ("rerank", rerank)):
        if span is None:
            why.append(f"not one {name}")
        elif span["error"] or span["wall"] is None:
            why.append(f"{name}: an error or no time")
    if pool is None or not pool["pool_sha256"]:
        why.append("not one rerank pool")
    if not ask["reranker_ok"] or not retrieval or retrieval["rerank_status"] != "ok":
        why.append("the rerank did not succeed")
    if answer is None or answer["error"]:
        why.append("no answer call, or a failed one")
    ask["unread"] = why
    ask["read"] = not why
    ask["arm_not_held"] = held(arm, action, ask["windows"]["retrieval"])
    ask["arm_held"] = not ask["arm_not_held"]
    return ask


def read_settings(path: Path, notes: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        notes.append("run: no readable effective_settings.json")
        return {}
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    out: dict[str, Any] = {}
    for key, value in SETTINGS.items():
        found = settings.get(key)
        out[key] = a_name(found) if isinstance(value, str) else num(found)
    return out


def read_run(samples_path: Path, run_dir: Path) -> dict[str, Any]:
    notes: list[str] = []
    meta, rows = read_samples(samples_path, notes)
    meta["loud_notes"] = loud_notes(rows)
    samples = Samples(rows, notes)
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
    label = str(kept.get("label") or "")
    registered = ARMS.get(label.removesuffix("-r2"))
    cases = read_cases(run_dir / "cases", notes)
    spans = read_spans(run_dir / "stages.jsonl", notes)
    groups = assign(spans, cases)
    asks = []
    for case in cases:
        position = case["index"]
        arm = None
        if registered and isinstance(position, int) and 1 <= position <= len(registered):
            arm = registered[position - 1]
        asks.append(read_ask(case, groups.get(id(case), []), samples, arm))
    settings = read_settings(run_dir / "effective_settings.json", notes)
    drivers = {name: sha256(run_dir.parent.parent / name) for name in DRIVERS_SHA256}
    # The samples span every question, from its request to its last event.
    spans_of_cases = [
        (c["t0_monotonic"], c["t0_monotonic"] + c["total_sec"])
        for c in cases
        if c["t0_monotonic"] is not None and c["total_sec"] is not None
    ]
    covered = bool(
        samples.times
        and cases
        and len(spans_of_cases) == len(cases)
        and samples.times[0] <= min(low for low, _ in spans_of_cases)
        and samples.times[-1] >= max(high for _, high in spans_of_cases)
    )
    gate = {
        "launch": kept.get("code_sha") == CODE_SHA
        and kept.get("status") == "complete"
        and kept.get("runner_exit") == 0
        and kept.get("mode") == "prod"
        and kept.get("model") == MODEL
        and registered is not None
        and kept.get("arm") == registered
        and kept.get("cases") == list(CASES),
        "settings": settings == SETTINGS,
        "drivers": drivers == DRIVERS_SHA256 and sha256(HERE / TOOLS[1]) == SAMPLER_SHA256,
        "asks": [a["case_id"] for a in sorted(asks, key=lambda a: a["index"] or 0)] == list(CASES)
        and all(ask["read"] for ask in asks),
        "actions": all(a["arm_action"] and not a["arm_action"]["error"] for a in asks),
        "samples": meta["schema"] == SAMPLES_SCHEMA and covered and not meta["loud_notes"],
        "b_held": any(ask["arm"] == "B" and ask["arm_held"] for ask in asks),
    }
    gate["passed"] = all(gate.values())
    pids = {pid for row in samples.rows for pid in pids_of(row)}
    return {
        "dir": str(run_dir),
        "label": kept.get("label"),
        "samples": meta,
        "launch": kept,
        "settings": settings,
        "sha256": {name: sha256(run_dir / name) for name in RUN_FILES},
        "drivers_sha256": drivers,
        "llama_pids_seen": len(pids),
        "asks": asks,
        "gate": gate,
        "notes": notes,
    }


def window_value(ask: dict[str, Any], name: str, key: str) -> Any:
    window = ask["windows"].get(name)
    return window.get(key) if window else None


def pair_up(runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each question's asks by arm: one in each makes a pair; readable when both runs passed
    their gates, both asks are read, both arms held, they share the position and the candidates,
    and the rerank and the whole question have times."""
    by_case: dict[str, dict[str, list[tuple[dict[str, Any], dict[str, Any]]]]] = {}
    for run in runs:
        for ask in run["asks"]:
            if ask["arm"] in ("A", "B") and ask["case_id"]:
                arms = by_case.setdefault(ask["case_id"], {"A": [], "B": []})
                arms[ask["arm"]].append((run, ask))
    pairs = []
    for case_id, arms in sorted(by_case.items()):
        pair: dict[str, Any] = {"case_id": case_id, "readable": False}
        if len(arms["A"]) != 1 or len(arms["B"]) != 1:
            pair["why"] = [f"{len(arms['A'])} asks in A and {len(arms['B'])} in B, not one each"]
            pairs.append(pair)
            continue
        (run_a, a), (run_b, b) = arms["A"][0], arms["B"][0]
        pair["a"] = {"run": run_a["label"], "index": a["index"]}
        pair["b"] = {"run": run_b["label"], "index": b["index"]}
        why = [
            f"run {run['label']}: its gate failed"
            for run in ((run_a,) if run_a is run_b else (run_a, run_b))
            if not run["gate"]["passed"]
        ]
        why += [f"{arm}: {reason}" for arm, ask in (("A", a), ("B", b)) for reason in ask["unread"]]
        why += [
            f"{arm}: {reason}"
            for arm, ask in (("A", a), ("B", b))
            for reason in ask["arm_not_held"]
        ]
        if a["index"] != b["index"]:
            why.append("not at the same position")
        if (a["pool"] or {}).get("pool_sha256") != (b["pool"] or {}).get("pool_sha256"):
            why.append("not the same candidates")
        if not a["rerank_sec"] or a["whole_sec"] is None or b["whole_sec"] is None:
            why.append("no rerank or whole time to compare")
        pair["why"] = why
        pair["readable"] = not why
        rerank_ratio = ratio(b["rerank_sec"], a["rerank_sec"])
        whole_diff = diff(b["whole_sec"], a["whole_sec"])
        pair["rerank_ratio"] = rounded(rerank_ratio, 4)
        pair["whole_diff_sec"] = rounded(whole_diff)
        pair["exact"] = {"rerank_ratio": rerank_ratio, "whole_diff_sec": whole_diff}
        call_a, call_b = a["answer_call"] or {}, b["answer_call"] or {}
        pair["printed"] = {
            "vector_ratio": rounded(ratio(b["vector_sec"], a["vector_sec"]), 4),
            "retrieval_ratio": rounded(ratio(b["retrieval_sec"], a["retrieval_sec"]), 4),
            "retrieval_diff_sec": rounded(diff(b["retrieval_sec"], a["retrieval_sec"])),
            "answer_offset_diff_sec": rounded(
                diff(call_b.get("offset_sec"), call_a.get("offset_sec"))
            ),
            # B's answer call loads the model: its first chunk less A's is the load and the
            # prompt cache B lost, not told apart
            "first_chunk_sec": {
                "a": call_a.get("first_chunk_sec"),
                "b": call_b.get("first_chunk_sec"),
            },
            "first_chunk_diff_sec": rounded(
                diff(call_b.get("first_chunk_sec"), call_a.get("first_chunk_sec"))
            ),
            "first_token_diff_sec": rounded(diff(b["first_token_sec"], a["first_token_sec"])),
            "total_diff_sec": rounded(diff(b["total_sec"], a["total_sec"])),
            "rerank_faulted_mib": {
                arm: window_value(ask, "rerank", "faulted_mib") for arm, ask in (("a", a), ("b", b))
            },
            "rerank_faulted_mib_per_sec": {
                arm: window_value(ask, "rerank", "faulted_mib_per_sec")
                for arm, ask in (("a", a), ("b", b))
            },
            "a_llama_mem_at_rerank_mib": (a["at_rerank_start"] or {}).get("llama_mem_mib"),
            "swap_used_at_rerank_mib": {
                arm: (ask["at_rerank_start"] or {}).get("swap_used_mib")
                for arm, ask in (("a", a), ("b", b))
            },
            "action_sec": {
                arm: (ask["arm_action"] or {}).get("sec") for arm, ask in (("a", a), ("b", b))
            },
        }
        pairs.append(pair)
    return pairs


def readings(pairs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The spec's readings: functions of the readable pairs alone."""
    readable = [pair for pair in pairs if pair["readable"]]
    ratios = [pair["exact"]["rerank_ratio"] for pair in readable]
    diffs = [pair["exact"]["whole_diff_sec"] for pair in readable]
    enough = len(readable) >= MIN_PAIRS
    contention = NOT_EVIDENCE
    net = NOT_EVIDENCE
    if enough:
        contention = "yes" if statistics.median(ratios) <= CONTENTION_RATIO else "no"
        net = "faster" if statistics.median(diffs) < 0 else "not faster"

    def printed(key: str, arm: str | None = None) -> float | None:
        values = [
            pair["printed"][key] if arm is None else pair["printed"][key][arm] for pair in readable
        ]
        return median([value for value in values if value is not None])

    return {
        "contention": {
            "answer": contention,
            "readable_pairs": len(readable),
            "median_rerank_ratio": rounded(statistics.median(ratios), 4) if ratios else None,
            "rerank_ratios": {pair["case_id"]: pair["rerank_ratio"] for pair in readable},
        },
        "net": {
            "answer": net,
            "readable_pairs": len(readable),
            "median_whole_diff_sec": median(diffs),
            "whole_diffs_sec": {pair["case_id"]: pair["whole_diff_sec"] for pair in readable},
        },
        "printed_deciding_nothing": {
            "median_vector_ratio": printed("vector_ratio"),
            "median_retrieval_ratio": printed("retrieval_ratio"),
            "median_retrieval_diff_sec": printed("retrieval_diff_sec"),
            "median_answer_offset_diff_sec": printed("answer_offset_diff_sec"),
            "median_first_chunk_sec": {arm: printed("first_chunk_sec", arm) for arm in ("a", "b")},
            "median_first_chunk_diff_sec": printed("first_chunk_diff_sec"),
            "median_first_token_diff_sec": printed("first_token_diff_sec"),
            "median_total_diff_sec": printed("total_diff_sec"),
            "median_rerank_faulted_mib": {
                arm: printed("rerank_faulted_mib", arm) for arm in ("a", "b")
            },
            "median_rerank_faulted_mib_per_sec": {
                arm: printed("rerank_faulted_mib_per_sec", arm) for arm in ("a", "b")
            },
            "median_a_llama_mem_at_rerank_mib": printed("a_llama_mem_at_rerank_mib"),
            "median_action_sec": {arm: printed("action_sec", arm) for arm in ("a", "b")},
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--run", nargs=2, action="append", required=True, metavar="PATH")
    parser.add_argument("--corpus")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"refused: {out} exists", file=sys.stderr)
        return 2
    runs = [read_run(Path(samples), Path(run_dir)) for samples, run_dir in args.run]
    labels = [run["label"] for run in runs]
    if len(set(labels)) < len(labels):
        parser.error("a run is named twice")
    corpus = None
    if args.corpus:
        folder = Path(args.corpus)
        corpus = {"dir": str(folder), "sha256": {n: sha256(folder / n) for n in CORPUS_FILES}}
    pairs = pair_up(runs)
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "corpus": corpus,
        "tools_sha256": {name: sha256(HERE / name) for name in TOOLS},
        "runs": runs,
        "pairs": [{k: v for k, v in pair.items() if k != "exact"} for pair in pairs],
        "readings": readings(pairs),
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"gates": {run["label"]: run["gate"] for run in runs}}, sort_keys=True))
    print(json.dumps(record["readings"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
