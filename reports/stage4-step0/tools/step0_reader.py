"""Stage 4, step 0's reader: llama-server's log slice and the sampler's rows, one row a request.

docs/specs/stage4-step0-diagnostics.md, registered with this tool before the first request.
On the Mac after a run, any Python 3.11, the standard library only:

  python -I step0_reader.py OUT LOG --part SAMPLES [RUN_DIR] [--part SAMPLES [RUN_DIR] ...]
      [--start BYTE --end BYTE] [--corpus DIR]

A part is one file of step0_sampler.py and, when named, the chat run it watched (the run
directory reports/stage1/tools/live_supervisor.py writes). The part's slice of LOG, Ollama's
serve log, runs from the log's size at the part's first sample to its size at the last; --start
and --end name the bytes instead, for one part. The slice is cut into llama-server processes (a
load_backend, build, system_info or load_tensors line after requests, or a task id below the
last one, starts one) and each process into requests. A request holds the cache lines before
its task (the slot's common prefix, the saved and the removed states, each cached prompt's
common prefix, the cache state), its prompt (its tokens and the first "cached n_tokens", the
prefix it reused), its print_timing summary and its release; the counters' change and the peaks
from the sample before it to the sample after it; and the samples certainly inside its prompt
and its generation. With a run directory, each request gets the model call it served (answer,
self_eval, suggestions or other) and its case id. A process holds its load lines: llama.cpp's
build, system_info, the backend library's file name, the load mode and the buffer sizes.

Lines are matched to the shapes llama-server printed on the Mac (2026-10-28) and to llama.cpp's
sources; a shape not found leaves null and a note, never a guess. OUT holds numbers, enums, ids,
the paths named here and SHA-256 strings: no log line, no prompt, question or answer text, and
no process's command line or environment. Prints the spec's readings; refuses an existing OUT.
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

SCHEMA = "stage4-step0/v1"
SPEC = "docs/specs/stage4-step0-diagnostics.md"
HERE = Path(__file__).resolve().parent
TOOLS = ("step0_reader.py", "step0_sampler.py")
NOT_EVIDENCE = "NOT_EVIDENCE"
MIB = 1048576
COUNTERS = ("pageins", "pageouts", "swapins", "swapouts", "compressions", "decompressions")
PEAKS = ("rss_mib", "mem_mib", "cmprs_mib")
CALLS = ("ollama.generate_stream", "ollama.generate")
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
    "status",
    "runner_exit",
    "ollama_load_sec",
    "ollama_models_before",
    "ollama_models_after",
)
RUN_FILES = ("launch.json", "effective_settings.json", "stages.jsonl")
DRIVERS = ("launch.py", "live_api.py", "live_runner.py", "live_supervisor.py")
CORPUS_FILES = ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
# The spec's readings, frozen with it.
Q1_MIN_GROWTH_MIB = 200.0
Q1_MIN_REQUESTS = 3
Q1_RATIO = (0.75, 1.25)
Q2_MIN_FAULTED_MIB = 25.0
Q2_MIN_WINDOWS = 2
Q3_MIN_REUSED = 100
Q3_LEVER_MS = 4000.0
Q3_MIN_ANSWERS = 2

NUM = r"(-?\d+(?:\.\d+)?)"
INT = r"(\d+)"
SLOT = re.compile(r"^slot\s+\S+:\s+id\s+\d+\s+\|\s+task\s+(-?\d+)\s+\|\s?(.*)$")
SRV = re.compile(r"^srv\s+\S+:\s?(.*)$")
GIN = re.compile(r'^\[GIN\][^|]*\|\s*(\d{3})\s*\|[^|]*\|[^|]*\|\s*([A-Z]+)\s+"([^"?]*)')
# Ollama 0.33.2's llama-server prints common's lines after a tag, "cmn  common_param: ", and its
# build as "common_params_print_info: build N (commit)" (error fix after run 1, 2026-10-28).
CMN = r"(?:cmn\s+\S+:\s+)?"
# Lines only a starting llama-server prints: after requests, a new process.
STARTS = re.compile(
    rf"^{CMN}(?:load_backend|build|system_info|load_tensors):|^{CMN}common_params_print_info: build "
)
REPACKED = ("CPU_REPACK", "CPU_AARCH64")  # ggml-cpu's repacked weights, its name and the old one
PLAIN = ("CPU", "CPU_Mapped")  # host buffers: the weights as the file holds them
BUILD = re.compile(rf"^{CMN}(?:build:|common_params_print_info: build) (\d+) \(([0-9a-f]+)\)")
SYSTEM_INFO = re.compile(
    rf"^{CMN}system_info: n_threads = (\d+)(?: \(n_threads_batch = (\d+)\))? / (\d+) \|(.*)$"
)
FLAG = re.compile(r"(\w+) = (\w+)")
BACKEND = re.compile(r"^load_backend: loaded (\S+) backend from (.+?)\s*$")
LOAD_MODE = re.compile(r"^load_tensors: loading model tensors.*\((load_mode|mmap) = (\w+)")
BUFFER = re.compile(
    r"^(\w+):\s+(\S+)\s+(model|KV|compute|output|RS) buffer size =\s*(\d+(?:\.\d+)?) MiB"
)
# Lines before a task: slot lines of task -1 and srv lines, the cache's update.
PREAMBLE = (
    ("sim", rf"^- checking sim = {NUM} \({INT}/{INT}\)"),
    ("selected", r"^selected slot by (LRU|LCP similarity|id)\b"),
    ("updating", r"^updating prompt cache$"),
    ("saved", rf"^- saving prompt with length {INT}, total state size = {NUM} MiB"),
    ("obsolete", rf"^- removing obsolete cached prompt with length {INT}"),
    ("removed", rf"removing oldest entry \(size = {NUM} MiB\)"),
    ("base", rf"^- looking for better prompt, base f_keep = {NUM}, f_sim = {NUM}"),
    ("candidate", rf"^- prompt with length\s+{INT}, lcp =\s+{INT}, f_keep = {NUM}"),
    ("found", rf"^- found better prompt with f_keep = {NUM}, f_sim = {NUM}"),
    (
        "state",
        rf"^- cache state: {INT} prompts, {NUM} MiB \(limits: {NUM} MiB, {INT} tokens, {INT} est",
    ),
    ("update_ms", rf"^prompt cache update took {NUM} ms"),
    ("skipped", rf"^- prompt state size {NUM} MiB exceeds cache size limit"),
    ("limit_reduced", rf"^- cache size limit reduced to {NUM} MiB"),
)
# Lines of a task: slot lines with its id.
TASK = (
    ("new_prompt", rf"^new prompt, n_ctx_slot = {INT}, n_keep = {INT}, task\.n_tokens = {INT}"),
    ("cached", rf"^cached n_tokens = {INT}"),
    ("prompt_eval", rf"^prompt eval time =\s*{NUM} ms /\s*{INT} tokens"),
    ("eval", rf"^eval time =\s*{NUM} ms /\s*{INT} tokens"),
    ("total", rf"^total time =\s*{NUM} ms /\s*{INT} tokens"),
    ("release", rf"^stop processing: n_tokens = {INT}, truncated = {INT}"),
)
PREAMBLE_SHAPES = [(key, re.compile(pattern)) for key, pattern in PREAMBLE]
TASK_SHAPES = [(key, re.compile(pattern)) for key, pattern in TASK]
# A shape whose numbers fill these fields, in order.
FIELDS = {
    "sim": ("sim_f", "sim_lcp", "sim_n"),
    "saved": ("saved_tokens", "saved_mib"),
    "base": ("base_f_keep", "base_f_sim"),
    "state": ("cache_prompts", "cache_mib", "cache_limit_mib", "cache_limit_tokens", "cache_est"),
    "update_ms": ("cache_update_ms",),
    "limit_reduced": ("cache_limit_reduced_mib",),
    "new_prompt": ("n_ctx_slot", "n_keep", "n_tokens"),
    "prompt_eval": ("prompt_ms", "prompt_tokens"),
    "eval": ("eval_ms", "eval_tokens"),
    "total": ("total_ms", "total_tokens"),
    "release": ("release_n_tokens", "truncated"),
}
FLAGS = {"updating": "cache_updated", "found": "restored"}
COUNTS = {
    "obsolete": "obsolete_entries",
    "removed": "removed_entries",
    "candidate": "candidates",
    "skipped": "skipped_saves",
}
POSITIONS = {"state": "state", "prompt_eval": "summary", "release": "release"}
PREAMBLE_ROW: dict[str, Any] = {
    **dict.fromkeys(("start_byte", "first_end", "selected_by", "best_candidate_lcp")),
    **dict.fromkeys(name for key, _ in PREAMBLE for name in FIELDS.get(key, ())),
    **dict.fromkeys(FLAGS.values(), False),
    **dict.fromkeys(COUNTS.values(), 0),
    "removed_mib": 0.0,
    "state_start": None,
    "state_end": None,
}
TASK_ROW: dict[str, Any] = {
    **dict.fromkeys(name for key, _ in TASK for name in FIELDS.get(key, ())),
    **dict.fromkeys(("task", "cached_tokens", "summary_start", "summary_end")),
    **dict.fromkeys(("release_start", "release_end")),
}


def number(text: str) -> int | float:
    return float(text) if "." in text else int(text)


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def median(values: Sequence[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def an_id(value: Any) -> str | None:
    """A case id as it is; anything else masked (a warmup's id carries its question after ":")."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.-]+", str(value)) else "<not an id>"


def fill(row: dict[str, Any], key: str, match: re.Match[str], start: int, end: int) -> None:
    """Puts one matched line's numbers into a request's row."""
    groups = match.groups()
    if key == "selected":
        row["selected_by"] = groups[0].split()[0]
    elif key in FLAGS:
        row[FLAGS[key]] = True
    elif key in COUNTS:
        row[COUNTS[key]] += 1
        if key == "removed":
            row["removed_mib"] = round(row["removed_mib"] + float(groups[0]), 3)
        elif key == "candidate":
            row["best_candidate_lcp"] = max(row["best_candidate_lcp"] or 0, int(groups[1]))
    elif key == "cached":
        # the first after "new prompt" is the reused prefix; the later ones count batches
        if row["n_tokens"] is not None and row["cached_tokens"] is None:
            row["cached_tokens"] = int(groups[0])
    else:
        row.update(zip(FIELDS[key], map(number, groups), strict=True))
        if key in POSITIONS:
            row[POSITIONS[key] + "_start"], row[POSITIONS[key] + "_end"] = start, end


class Reader:
    """Cuts a slice's lines into llama-server processes and their requests."""

    def __init__(self) -> None:
        self.processes: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.request: dict[str, Any] | None = None
        self.gin: Counter[str] = Counter()
        self.notes: list[str] = []
        self.new_process()

    def new_process(self, note: str | None = None) -> dict[str, Any]:
        if self.pending is not None:
            self.notes.append("cache lines with no task before a new process: left out")
            self.pending = None
        load: dict[str, Any] = {
            "lines": 0,
            "build": None,
            "commit": None,
            "system_info": None,
            "backends": [],
            "load_mode": None,
            "buffers": [],
            "notes": [],
        }
        notes = [note] if note else []
        process: dict[str, Any] = {"index": len(self.processes), "load": load, "notes": notes}
        process["requests"] = []
        self.processes.append(process)
        self.request = None
        return process

    def line(self, start: int, end: int, text: str) -> None:
        if STARTS.match(text) or BACKEND.match(text) or BUFFER.match(text):
            self.load_line(text)
        elif match := SLOT.match(text):
            task, message = int(match.group(1)), match.group(2).strip()
            if task < 0:
                self.preamble_line(start, end, message)
            else:
                self.task_line(start, end, task, message)
        elif match := SRV.match(text):
            self.preamble_line(start, end, match.group(1).strip())
        elif match := GIN.match(text):
            self.gin[f"{match.group(2)} {match.group(3)} {match.group(1)}"] += 1

    def load_line(self, text: str) -> None:
        process = self.processes[-1]
        if STARTS.match(text) and (process["requests"] or self.pending is not None):
            process = self.new_process()
        load = process["load"]
        load["lines"] += 1
        if match := BUILD.match(text):
            load["build"], load["commit"] = int(match.group(1)), match.group(2)
        elif match := SYSTEM_INFO.match(text):
            batch = match.group(2)
            load["system_info"] = {
                "n_threads": int(match.group(1)),
                "n_threads_batch": int(batch) if batch else None,
                "hw_threads": int(match.group(3)),
                "flags": dict(FLAG.findall(match.group(4))),
            }
        elif match := BACKEND.match(text):
            # the library's file name only: its folder is left out
            name = match.group(2).rsplit("/", 1)[-1]
            load["backends"].append({"name": match.group(1), "file": name})
        elif match := LOAD_MODE.match(text):
            load["load_mode"] = f"{match.group(1)} = {match.group(2)}"
        elif match := BUFFER.match(text):
            at, kind, size = match.group(1), match.group(3), float(match.group(4))
            load["buffers"].append({"at": at, "type": match.group(2), "kind": kind, "mib": size})

    def preamble_line(self, start: int, end: int, message: str) -> None:
        for key, pattern in PREAMBLE_SHAPES:
            if match := pattern.search(message):
                if self.pending is None:
                    self.pending = {**PREAMBLE_ROW, "start_byte": start, "first_end": end}
                fill(self.pending, key, match, start, end)
                return

    def task_line(self, start: int, end: int, task: int, message: str) -> None:
        request = self.request
        if request is None or request["task"] != task:
            requests = self.processes[-1]["requests"]
            if requests and task < requests[-1]["task"]:
                self.new_process("task ids went down with no load line: a new process")
            request = self.open_request(task, start, end)
        for key, pattern in TASK_SHAPES:
            if match := pattern.search(message):
                fill(request, key, match, start, end)
                return

    def open_request(self, task: int, start: int, end: int) -> dict[str, Any]:
        preamble = self.pending or {**PREAMBLE_ROW, "start_byte": start, "first_end": end}
        self.pending = None
        process = self.processes[-1]
        request = {**preamble, **TASK_ROW, "process": process["index"], "task": task, "notes": []}
        process["requests"].append(request)
        self.request = request
        return request

    def finish(self) -> None:
        if self.pending is not None:
            self.notes.append("cache lines with no task at the slice's end: left out")
            self.pending = None
        for process in self.processes:
            check_load(process["load"])
            for index, request in enumerate(process["requests"]):
                check_request(request, first=index == 0)


def check_load(load: dict[str, Any]) -> None:
    notes = load["notes"]
    if not load["lines"]:
        notes.append("no load lines in the slice")
        return
    for field, shape in (("build", "build"), ("system_info", "system_info")):
        if load[field] is None:
            notes.append(f"no {shape} line")
    if load["load_mode"] is None:
        notes.append("no load_tensors load-mode line")
    if not load["backends"]:
        notes.append("no load_backend line")
    if not any(buffer["kind"] == "model" for buffer in load["buffers"]):
        notes.append("no model buffer line")


def check_request(row: dict[str, Any], first: bool) -> None:
    notes = row["notes"]
    row["complete"] = row["n_tokens"] is not None and row["release_n_tokens"] is not None
    if row["n_tokens"] is None:
        notes.append("no new-prompt line: the request began before the slice")
    if row["release_n_tokens"] is None:
        notes.append("no release line: the request ended after the slice")
    if row["complete"]:
        shapes = {
            "cached_tokens": "cached n_tokens",
            "prompt_ms": "prompt eval time",
            "eval_ms": "eval time",
            "total_ms": "total time",
        }
        notes += [f"no {shape} line" for field, shape in shapes.items() if row[field] is None]
    if not first and row["sim_lcp"] is None:
        notes.append("no checking-sim line")
    if row["cache_updated"] and row["cache_mib"] is None:
        notes.append("a cache update with no cache-state line")
    row["eval_tps"] = row["prompt_ms_per_token"] = None
    if row["eval_ms"] and row["eval_tokens"] is not None:
        row["eval_tps"] = round(row["eval_tokens"] / row["eval_ms"] * 1000, 3)
    if row["prompt_ms"] is not None and row["prompt_tokens"]:
        row["prompt_ms_per_token"] = round(row["prompt_ms"] / row["prompt_tokens"], 3)


class Samples:
    """A part's samples that have a log size, and lookups by log byte and by time."""

    def __init__(self, rows: list[dict[str, Any]], notes: list[str]) -> None:
        self.rows = [row for row in rows if row.get("log_bytes") is not None]
        self.bytes = [row["log_bytes"] for row in self.rows]
        self.times = [row["monotonic"] for row in self.rows]
        self.ordered = all(a <= b for a, b in pairwise(self.bytes))
        self.ordered = self.ordered and all(a <= b for a, b in pairwise(self.times))
        if len(self.rows) < len(rows):
            notes.append(f"{len(rows) - len(self.rows)} samples with no log size: left out")
        if not self.ordered:
            notes.append("the log's size or the clock went down: no windows")
        pids = sorted({proc["pid"] for row in self.rows for proc in row.get("procs") or []})
        # one model process is the stand's; with two, whose lines the log holds is not known
        self.pid = pids[0] if len(pids) == 1 else None
        if len(pids) > 1:
            notes.append(f"{len(pids)} llama-server pids in the samples: no footprint is read")
        sizes = [row["page_size"] for row in self.rows if row.get("page_size")]
        self.page_size = sizes[0] if sizes else None

    def before(self, offset: int | None) -> int | None:
        """The last sample taken before the byte at offset was written."""
        if offset is None or not self.ordered:
            return None
        index = bisect.bisect_right(self.bytes, offset) - 1
        return index if index >= 0 else None

    def after(self, offset: int | None) -> int | None:
        """The first sample taken after the bytes up to offset were written."""
        if offset is None or not self.ordered:
            return None
        index = bisect.bisect_left(self.bytes, offset)
        return index if index < len(self.bytes) else None

    def stats(self, i: int, j: int) -> dict[str, Any]:
        """The counters' change from sample i to sample j and llama-server's peaks between."""
        first, last = self.rows[i], self.rows[j]
        span = round(last["monotonic"] - first["monotonic"], 3)
        row: dict[str, Any] = {"samples": j - i + 1, "sec": span}
        for key in COUNTERS:
            a, b = (first.get("vm") or {}).get(key), (last.get("vm") or {}).get(key)
            row[key] = b - a if a is not None and b is not None else None
        faults = (row["decompressions"], row["pageins"])
        row["faulted_mib"] = None
        if self.page_size and None not in faults:
            row["faulted_mib"] = round(sum(faults) * self.page_size / MIB, 3)
        a, b = (first.get("swap_mib") or {}).get("used"), (last.get("swap_mib") or {}).get("used")
        row["swap_used_mib"] = round(b - a, 3) if a is not None and b is not None else None
        procs = [proc for sample in self.rows[i : j + 1] for proc in sample.get("procs") or []]
        for key in PEAKS:
            values = [p[key] for p in procs if p.get("pid") == self.pid and p.get(key) is not None]
            row[key.replace("_mib", "_peak_mib")] = max(values) if values else None
        return row

    def inside(self, low: float, high: float) -> dict[str, Any]:
        """The samples taken between two times; the counters from two samples on."""
        i = bisect.bisect_left(self.times, low)
        j = bisect.bisect_right(self.times, high) - 1
        bounds = {"from": round(low, 3), "to": round(high, 3)}
        if j - i + 1 < 2:
            return {"samples": max(0, j - i + 1), **bounds}
        return {**self.stats(i, j), **bounds}

    def mem(self, index: int | None) -> float | None:
        if index is None:
            return None
        procs = self.rows[index].get("procs") or []
        return next((p.get("mem_mib") for p in procs if p.get("pid") == self.pid), None)

    def attach(self, row: dict[str, Any]) -> None:
        """A request's windows: around it, and certainly inside its prompt and its generation."""
        i, j = self.before(row["start_byte"]), self.after(row["release_end"])
        row["request_window"] = self.stats(i, j) if i is not None and j is not None else None
        k = self.after(row["first_end"])
        row["first_line_by"] = self.times[k] if k is not None else None
        k = self.before(row["release_start"])
        row["release_after"] = self.times[k] if k is not None else None
        row["mem_after_state_mib"] = self.mem(self.after(row["state_end"]))
        row["prompt_window"] = row["generation_window"] = None
        a, b = self.after(row["summary_end"]), self.before(row["summary_start"])
        if a is None or b is None or row["eval_ms"] is None or row["prompt_ms"] is None:
            return
        # The summary is printed as generation ends, between samples b and a: generation surely
        # ran from a - eval to b, and the prompt from a - eval - prompt to b - eval.
        late, early = self.times[a], self.times[b]
        gen, pp = row["eval_ms"] / 1000, row["prompt_ms"] / 1000
        row["prompt_window"] = self.inside(late - gen - pp, early - gen)
        window = row["generation_window"] = self.inside(late - gen, early)
        window["faulted_mib_per_token"] = None
        if window.get("faulted_mib") is not None and window["sec"] > 0 and row["eval_tps"]:
            tokens = row["eval_tps"] * window["sec"]
            window["faulted_mib_per_token"] = round(window["faulted_mib"] / tokens, 3)


def read_samples(path: Path, notes: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    first: dict[str, Any] = {}
    last: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
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


def read_slice(
    log: Path, start: int, end: int, notes: list[str]
) -> tuple[list[tuple[int, int, str]], dict[str, Any]]:
    """The whole lines of the log between two byte offsets, each with its start and end."""
    with log.open("rb") as fh:
        before = b"\n"
        if start > 0:
            fh.seek(start - 1)
            before = fh.read(1)
        data = fh.read(max(0, end - start))
    if len(data) < end - start:
        notes.append("the log is shorter than the slice")
    pieces = data.split(b"\n")
    if pieces.pop():
        notes.append("the slice ends inside a line: it is left out")
    lines = []
    offset = start
    for index, piece in enumerate(pieces):
        line_end = offset + len(piece) + 1
        if index == 0 and before != b"\n":
            notes.append("the slice starts inside a line: it is left out")
        else:
            lines.append((offset, line_end, piece.decode("utf-8", "replace").rstrip("\r")))
        offset = line_end
    digest = hashlib.sha256(data).hexdigest()
    cut = {"start": start, "end": end, "bytes": len(data), "lines": len(lines), "sha256": digest}
    return lines, cut


def read_calls(path: Path, notes: list[str]) -> list[dict[str, Any]]:
    """The model calls of stages.jsonl, start and end paired per stage and thread, by start."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        notes.append("run: no stages.jsonl")
        return []
    started: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    calls = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else {}
        except ValueError:
            notes.append("run: an unreadable stages.jsonl line")
            continue
        if row.get("stage") not in CALLS:
            continue
        key = (row["stage"], row.get("thread"))
        if row.get("event") == "start":
            started.setdefault(key, []).append(row)
        elif row.get("event") == "end" and started.get(key):
            begun = started[key].pop(0)
            call = {"stage": row["stage"], "start": begun.get("monotonic")}
            call.update(end=row.get("monotonic"), failed=row.get("error") is not None)
            call.update(max_tokens=begun.get("max_tokens"))
            call.update(prompt_est_tokens=begun.get("prompt_est_tokens"))
            calls.append(call)
    left = sum(len(rows) for rows in started.values())
    if left:
        notes.append(f"run: {left} model calls started and never ended")
    calls.sort(key=lambda call: call["start"] if call["start"] is not None else float("inf"))
    for index, call in enumerate(calls):
        call["index"] = index
    return calls


def read_cases(folder: Path, notes: list[str]) -> list[dict[str, Any]]:
    """Each case's id, times, token count and route; never its question or its answer."""
    cases = []
    for path in sorted(folder.glob("*.json")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            notes.append(f"run: case file {path.name} unreadable")
            continue
        events = [event for event in case.get("events") or [] if isinstance(event, dict)]
        result = next((event for event in events if event.get("type") == "result"), {})
        route = result.get("route")
        row: dict[str, Any] = {"case_id": an_id(case.get("case_id"))}
        row.update({key: case.get(key) for key in ("t0_monotonic", "total_sec", "drain_sec")})
        row.update(tokens=case.get("tokens"), route=route if isinstance(route, str) else None)
        row.update(client_error="client_error" in case, drain_error="drain_error" in case)
        cases.append({**row, "sha256": sha256(path)})
    if not cases:
        notes.append("run: no case files")
    return cases


def assign_roles(
    calls: list[dict[str, Any]], cases: list[dict[str, Any]], notes: list[str]
) -> None:
    """A call belongs to the last case begun before it. In a case the stream is the answer; the
    next two generate calls are the self-evaluation and the suggested questions."""
    timed = [case for case in cases if isinstance(case["t0_monotonic"], (int, float))]
    timed.sort(key=lambda case: case["t0_monotonic"])
    starts = [case["t0_monotonic"] for case in timed]
    groups: dict[int, list[dict[str, Any]]] = {}
    for call in calls:
        at = bisect.bisect_right(starts, call["start"]) - 1 if call["start"] is not None else -1
        call["case_id"] = timed[at]["case_id"] if at >= 0 else None
        groups.setdefault(at, []).append(call)
    for at, group in groups.items():
        stream = next((n for n, call in enumerate(group) if call["stage"] == CALLS[0]), None)
        for n, call in enumerate(group):
            call["role"] = "other"
            if at < 0 or stream is None or n < stream:
                continue
            if n == stream:
                call["role"] = "answer"
            elif call["stage"] == CALLS[1]:
                later = sum(1 for other in group[stream + 1 : n] if other["stage"] == CALLS[1])
                call["role"] = ("self_eval", "suggestions", "other")[min(later, 2)]
        if at >= 0:
            route = timed[at]["route"]
            expected = {"auto": 3, "human": 2}.get(route or "")
            if expected is not None and len(group) != expected:
                case_id = timed[at]["case_id"]
                notes.append(f"run: case {case_id}: {len(group)} model calls, route {route}")


def fits(call: dict[str, Any], row: dict[str, Any]) -> bool:
    """The call began before the request's first line was in the log, and ended after the
    last sample taken before its release line."""
    times = (call["start"], call["end"], row["first_line_by"], row["release_after"])
    return None not in times and times[0] <= times[2] and times[1] >= times[3]


def join(
    requests: list[dict[str, Any]], calls: list[dict[str, Any]], notes: list[str]
) -> dict[str, int]:
    """Each call takes the first request after the last one taken whose times fit it."""
    position = matched = 0
    for call in calls:
        call["task"] = None
        for k in range(position, len(requests)):
            row = requests[k]
            if fits(call, row):
                row.update(role=call["role"], case_id=call["case_id"], call=call["index"])
                call["task"] = row["task"]
                position, matched = k + 1, matched + 1
                break
        else:
            notes.append(f"run: call {call['index']} ({call['role']}) fits no request")
    notes += [f"run: task {row['task']} fits no call" for row in requests if row["call"] is None]
    return {"calls": len(calls), "requests": len(requests), "matched": matched}


def read_run(run_dir: Path, notes: list[str]) -> dict[str, Any]:
    try:
        launch = json.loads((run_dir / "launch.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        notes.append("run: no readable launch.json")
        launch = {}
    kept = {key: launch[key] for key in LAUNCH_KEYS if key in launch}
    if isinstance(kept.get("cases"), list):
        kept["cases"] = [an_id(case) for case in kept["cases"]]
    cases = read_cases(run_dir / "cases", notes)
    calls = read_calls(run_dir / "stages.jsonl", notes)
    assign_roles(calls, cases, notes)
    return {
        "dir": str(run_dir),
        "launch": kept,
        "sha256": {name: sha256(run_dir / name) for name in RUN_FILES},
        "drivers_sha256": {name: sha256(run_dir.parent.parent / name) for name in DRIVERS},
        "cases": cases,
        "calls": calls,
    }


def read_part(
    log: Path, samples_path: Path, run_dir: Path | None, start: int | None, end: int | None
) -> dict[str, Any]:
    notes: list[str] = []
    meta, rows = read_samples(samples_path, notes)
    samples = Samples(rows, notes)
    if start is None or end is None:
        if not samples.bytes:
            raise SystemExit(f"refused: {samples_path} has no sample with a log size")
        start, end = samples.bytes[0], samples.bytes[-1]
    if end < start:
        raise SystemExit("refused: the slice ends before it starts")
    lines, cut = read_slice(log, start, end, notes)
    reader = Reader()
    for line in lines:
        reader.line(*line)
    reader.finish()
    notes += reader.notes
    for process in reader.processes:
        for row in process["requests"]:
            samples.attach(row)
            row.update(role=None, case_id=None, call=None)
    run = None
    if run_dir is not None:
        run = read_run(run_dir, notes)
        complete = [row for p in reader.processes for row in p["requests"] if row["complete"]]
        run["joined"] = join(complete, run["calls"], notes)
    return {
        "samples": meta,
        "slice": cut,
        "pid": samples.pid,
        "page_size": samples.page_size,
        "processes": reader.processes,
        "gin": dict(sorted(reader.gin.items())),
        "run": run,
        "notes": notes,
    }


def q1(processes: list[dict[str, Any]]) -> dict[str, Any]:
    """Does the host prompt cache grow by about 300 MiB a request, and is it the growth of
    llama-server's footprint?"""
    deltas: list[float] = []
    growth = footprint = cache = 0.0
    steps = 0
    for process in processes:
        # each cache-state line with its request's place in the process
        requests = enumerate(process["requests"])
        states = [(n, row) for n, row in requests if row["cache_mib"] is not None]
        deltas += [round(b["cache_mib"] - a["cache_mib"], 3) for (_, a), (_, b) in pairwise(states)]
        if len(states) >= 2:
            (first, a), (last, b) = states[0], states[-1]
            growth, steps = growth + b["cache_mib"] - a["cache_mib"], steps + last - first
        span = [row for _, row in states if row["cache_prompts"] >= 1]
        span = [row for row in span if row["mem_after_state_mib"] is not None]
        if len(span) >= 2:
            footprint += span[-1]["mem_after_state_mib"] - span[0]["mem_after_state_mib"]
            cache += span[-1]["cache_mib"] - span[0]["cache_mib"]
    per_request = round(growth / steps, 3) if steps else None
    grows = None
    if per_request is not None and steps >= Q1_MIN_REQUESTS:
        grows = per_request >= Q1_MIN_GROWTH_MIB
    ratio = round(footprint / cache, 3) if cache > 0 else None
    accounts = None if ratio is None else Q1_RATIO[0] <= ratio <= Q1_RATIO[1]
    answer = "yes" if grows and accounts else "no"
    if grows is None or (grows and accounts is None):
        answer = NOT_EVIDENCE
    rows = [row for process in processes for row in process["requests"]]
    return {
        "answer": answer,
        "growth_per_request_mib": per_request,
        "requests_spanned": steps,
        "deltas_mib": deltas,
        "median_delta_mib": median(deltas),
        "grows": grows,
        "footprint_delta_mib": round(footprint, 3),
        "cache_delta_mib": round(cache, 3),
        "ratio": ratio,
        "accounts": accounts,
        "saved_mib": [row["saved_mib"] for row in rows if row["saved_mib"] is not None],
        "removed_entries": sum(row["removed_entries"] for row in rows),
        "restored": sum(1 for row in rows if row["restored"]),
        "skipped_saves": sum(row["skipped_saves"] for row in rows),
    }


def q2(processes: list[dict[str, Any]]) -> dict[str, Any]:
    """Does generation wait on memory: pages faulted back while it runs, per generated token?"""
    keys = ("samples", "sec", "faulted_mib", "faulted_mib_per_token", "pageouts", "swapins")
    per_request = []
    for process in processes:
        for row in process["requests"]:
            if row["complete"]:
                window = row["generation_window"] or {}
                kept = {key: window.get(key) for key in (*keys, "swap_used_mib")}
                per_request.append({"task": row["task"], "role": row["role"], **kept})
                per_request[-1]["eval_tps"] = row["eval_tps"]
    values = [row["faulted_mib_per_token"] for row in per_request]
    values = [value for value in values if value is not None]
    answer = NOT_EVIDENCE
    if len(values) >= Q2_MIN_WINDOWS:
        answer = "yes" if statistics.median(values) >= Q2_MIN_FAULTED_MIB else "no"
    return {
        "answer": answer,
        "windows": len(values),
        "median_faulted_mib_per_token": median(values),
        "requests": per_request,
    }


def best_prefix(row: dict[str, Any]) -> int | None:
    """The longest common prefix the request's prompt had with a state it could have used."""
    values = [value for value in (row["sim_lcp"], row["best_candidate_lcp"]) if value is not None]
    return max(values) if values else None


def q3(processes: list[dict[str, Any]]) -> dict[str, Any]:
    """Does an answer reuse its instructions, and would reusing its best prefix save 4 s?"""
    answers, self_evals = [], []
    for process in processes:
        seen = False
        for row in process["requests"]:
            if row["complete"] and row["role"] == "answer":
                if seen:
                    answers.append(row)
                seen = True
            elif row["complete"] and row["role"] == "self_eval":
                self_evals.append(row)
    readable = []
    for row in answers:
        best, cached, per_token = best_prefix(row), row["cached_tokens"], row["prompt_ms_per_token"]
        if best is None or cached is None or per_token is None:
            continue
        saving = round(max(0, best - cached) * per_token, 1)
        kept = {"task": row["task"], "case_id": row["case_id"], "cached_tokens": cached}
        readable.append({**kept, "best_prefix": best, "saving_ms": saving})
    reused = [float(row["cached_tokens"]) for row in readable]
    savings = [row["saving_ms"] for row in readable]
    answer = lever = NOT_EVIDENCE
    if len(readable) >= Q3_MIN_ANSWERS:
        answer = "yes" if statistics.median(reused) >= Q3_MIN_REUSED else "no"
        lever = "yes" if statistics.median(savings) >= Q3_LEVER_MS else "no"
    evals = [
        {
            "task": row["task"],
            "cached_tokens": row["cached_tokens"],
            "best_prefix": best_prefix(row),
        }
        for row in self_evals
    ]
    return {
        "answer": answer,
        "lever": lever,
        "median_cached_tokens": median(reused),
        "median_saving_ms": median(savings),
        "answers": readable,
        "unreadable_answers": len(answers) - len(readable),
        "self_eval": evals,
    }


def repack(processes: list[dict[str, Any]]) -> dict[str, Any]:
    """Are the weights repacked at load: a repacked model buffer, or only host buffers?"""
    loads = [process["load"] for process in processes]
    types = sorted({b["type"] for load in loads for b in load["buffers"] if b["kind"] == "model"})
    answer = NOT_EVIDENCE  # no model buffer line, or a buffer type named neither way
    if any(name in REPACKED for name in types):
        answer = "on"
    elif types and all(name in PLAIN for name in types):
        answer = "off"
    infos = [load["system_info"] for load in loads if load["system_info"]]
    backends = sorted({(b["name"], b["file"]) for load in loads for b in load["backends"]})
    return {
        "answer": answer,
        "model_buffers": types,
        "backends": [list(pair) for pair in backends] or None,
        "system_info_repack": infos[0]["flags"].get("REPACK") if infos else None,
        "n_threads": infos[0]["n_threads"] if infos else None,
        "load_mode": next((load["load_mode"] for load in loads if load["load_mode"]), None),
        "build": next((load["build"] for load in loads if load["build"] is not None), None),
    }


def readings(parts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The spec's readings: functions of the rows above alone."""
    processes = [process for part in parts for process in part["processes"]]
    return {
        "q1_cache_growth": q1(processes),
        "q2_memory_wait": q2(processes),
        "q3_prefix_reuse": q3(processes),
        "repack": repack(processes),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("log")
    parser.add_argument("--part", nargs="+", action="append", required=True, metavar="PATH")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--corpus")
    args = parser.parse_args(argv)
    if any(len(part) > 2 for part in args.part):
        parser.error("--part takes SAMPLES and at most one RUN_DIR")
    if (args.start is None) != (args.end is None) or (
        args.start is not None and len(args.part) > 1
    ):
        parser.error("--start and --end come together, for one part")
    out = Path(args.out)
    if out.exists():
        print(f"refused: {out} exists", file=sys.stderr)
        return 2
    parts = []
    for part in args.part:
        run_dir = Path(part[1]) if len(part) > 1 else None
        parts.append(read_part(Path(args.log), Path(part[0]), run_dir, args.start, args.end))
    corpus = None
    if args.corpus:
        folder = Path(args.corpus)
        corpus = {"dir": str(folder), "sha256": {n: sha256(folder / n) for n in CORPUS_FILES}}
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "log": args.log,
        "corpus": corpus,
        "tools_sha256": {name: sha256(HERE / name) for name in TOOLS},
        "parts": parts,
        "readings": readings(parts),
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(record["readings"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
