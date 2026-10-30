"""Stage 4, item 5a's short live series: the reader of PyTorch's and INT8's rerank in the chat.

docs/specs/stage4-step5a-live.md, registered with this tool before the first request. On the
Mac after a run, any Python 3.11, the standard library only:

  python -I live5a_reader.py OUT --run SAMPLES RUN_DIR [--run SAMPLES RUN_DIR ...]
      [--corpus DIR] [--environment FILE]

A run is read as step 1's reader reads one: step1_reader.py, byte for byte, beside this file,
loaded only when its SHA-256 is the one step 1 registered. Each question of a run (an ask) gets
its spans, its arm action and the samples inside, and whether it is read and its arm, A (the
model resident), held. This reader adds the run's reranker runtime, from launch.json and the
API's effective settings; the five the rerank kept, as the SHA-256 of their [source,
chunk_index] list in the order kept and of the same list sorted, from the rerank's end row; the
highest 1-minute load the samples read inside the rerank and inside the question; and the
reranker's load: the first get_reranker call, which the API makes at its start, building the
default tenant's retriever before the first question. A run's first question is its warm-up:
read and gated, never paired. A later question's pair is its ask in the PyTorch run and its ask
in the INT8 run of one block; the readings are functions of the readable pairs alone: the exact
two-sided sign test on the rerank's seconds and on the whole question's, every block leaning the
same way. With --corpus and --environment the stand is checked too: V4's corpus files and
stand_env.py's lines, before the first run and after the last, by their registered values.

OUT holds numbers, enums, ids, model names, the paths named in the spec and SHA-256 strings: no
question, answer, prompt, source name or log line, and of an error its type only. Prints the
spec's readings; refuses an existing OUT.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import math
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA = "stage4-step5a-live/v1"
SPEC = "docs/specs/stage4-step5a-live.md"
HERE = Path(__file__).resolve().parent
NOT_EVIDENCE = "NOT_EVIDENCE"
STEP1 = "step1_reader.py"
STEP1_SHA256 = "38f0abfe20143085ad593b361377ee09f5a59d30ca0c3ed69a75863ec288ea3b"
SAMPLER = "step0_sampler.py"
TOOLS = ("live5a_reader.py", STEP1, SAMPLER)
# The product's commit: RAG_RERANKER_RUNTIME=onnx loads RAG_RERANKER_ONNX (vectordb/onnx_reranker.py).
CODE_SHA = "81cd2ade80ea9bc5a4f3ea721a16bd05037136fd"
# Aircargo's registered order from step 0's fifth: step 0's fifth, step 1's four, then the next;
# the same six in every run. The first is the run's warm-up, read and gated but never paired: the
# API's fresh process pays its reranker's first call there (item 5a's PyTorch blocks took 133.1
# and 129.5 s for their first call against a median 28.2 s, INT8's 14.7 and 13.2 s).
CASES = (
    "aircargo-dismissal-lawyer",
    "aircargo-dismissal-order",
    "aircargo-leave-sources",
    "aircargo-leave-compensation",
    "aircargo-leave-risk",
    "aircargo-matliab-check",
)
WARM_UP, PAIRED = CASES[0], CASES[1:]
ARMS = "AAAAAA"
# The registered runs and their runtimes, in the order they run, ABBA twice; a rerun keeps its
# run's runtime, labelled "-r2". A block is a PyTorch run and the INT8 run beside it.
RUNS = {
    "s5a-torch-1": "torch",
    "s5a-int8-1": "onnx",
    "s5a-int8-2": "onnx",
    "s5a-torch-2": "torch",
    "s5a-torch-3": "torch",
    "s5a-int8-3": "onnx",
    "s5a-int8-4": "onnx",
    "s5a-torch-4": "torch",
}
BLOCKS = (
    ("s5a-torch-1", "s5a-int8-1"),
    ("s5a-torch-2", "s5a-int8-2"),
    ("s5a-torch-3", "s5a-int8-3"),
    ("s5a-torch-4", "s5a-int8-4"),
)
# The answer model by Ollama's digest, as step 1 ran it.
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
# V4's corpus files (step1_reader.CORPUS_FILES), as step 1 and item 5 hashed them.
CORPUS_SHA256 = {
    "corpus.manifest.json": "2b2e9232e69b4f52a55237f3ee620f34c91d1900383877c2310ba616c6590444",
    "chunks-report.json": "bf01530e5a4cf33de44a7ce4aa1282805fc600a49b3a2f82b30b3b5715c6a714",
    "index/index-receipt.json": "2dcc80e75d22e9dc34b31313c1db2724aa59c606203eb56c9ac7b84abb684666",
}
OLLAMA_VERSION = "0.33.2"
RERANKER = "BAAI/bge-reranker-v2-m3"
# Item 5a's INT8 export (reports/stage4-step5a/onnx/manifest.json, int8/model.onnx).
ONNX = "/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx"
ONNX_SHA256 = "57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343"
# What a run must have run, two levels above its directory (live_supervisor.py's folder):
# V4's live_api.py, step 1's live_runner.py and this folder's supervisor.
DRIVERS_SHA256 = {
    "live_api.py": "43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5",
    "live_runner.py": "c87838014a0517d5e6a3dde0402ed0b067a9e0148aaf5d842ffe272ca451a072",
    "live_supervisor.py": "e903a1498aa1d48fb7ef6a9ba8cd2e4bd94e866433420fb132a6ab7179bd8e59",
}
# The code defaults, which the series keeps: K = 20 candidates, five kept, the CPU.
SETTINGS = {
    "retrieval_top_k": 20,
    "rerank_top_k": 5,
    "rag_device": "cpu",
    "reranker_model": RERANKER,
}
LOAD = "vectordb._base_manager.get_reranker"
ALPHA = 0.05
MIN_PAIRS = 16
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
HEX = re.compile(r"[0-9a-f]{64}")


def load_step1() -> Any:
    """Step 1's reader beside this one, refused unless it is step 1's by its SHA-256."""
    path = HERE / STEP1
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if digest != STEP1_SHA256:
        raise SystemExit(f"refused: {STEP1} beside this reader is not step 1's: {digest}")
    spec = importlib.util.spec_from_file_location("step1_reader", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["step1_reader"] = module
    spec.loader.exec_module(module)
    return module


step1 = load_step1()


def median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def rounded(value: float | None, places: int = 3) -> float | None:
    return step1.rounded(value, places)


def expected_settings(runtime: str) -> dict[str, Any]:
    onnx_path = ONNX if runtime == "onnx" else ""
    return {**SETTINGS, "reranker_runtime": runtime, "reranker_onnx_path": onnx_path}


def read_settings(path: Path, notes: list[str]) -> dict[str, Any]:
    """The code defaults kept and the reranker's model, runtime and file, as the API took them."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        notes.append("run: no readable effective_settings.json")
        return {}
    public = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    every = data.get("all") if isinstance(data.get("all"), dict) else {}
    out: dict[str, Any] = {}
    for key, value in SETTINGS.items():
        found = public.get(key)
        out[key] = step1.a_name(found) if isinstance(value, str) else step1.num(found)
    out["reranker_runtime"] = step1.a_name(every.get("reranker_runtime"))
    found = every.get("reranker_onnx_path")
    out["reranker_onnx_path"] = found if found in ("", ONNX) else step1.a_name(found)
    return out


def file_sha256(path: Path) -> str | None:
    """A large file's SHA-256, read a megabyte at a time."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def sha_of(items: list[list[Any]]) -> str:
    return hashlib.sha256(json.dumps(items, ensure_ascii=False).encode("utf-8")).hexdigest()


def read_rows(path: Path) -> tuple[dict[float, dict[str, str]], list[dict[str, Any]]]:
    """From stages.jsonl, beside step 1's spans: each rerank's five, by its end row's time, and
    each get_reranker call in the order they ended, with its end row's time."""
    fives: dict[float, dict[str, str]] = {}
    loads: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fives, loads
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else {}
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("event") != "end":
            continue
        if row.get("stage") == LOAD:
            sec = rounded(step1.num(row.get("wall_sec")))
            error = step1.error_type(row.get("error"))
            loads.append({"sec": sec, "error": error, "end": step1.num(row.get("monotonic"))})
        elif row.get("stage") == step1.RERANK:
            sources, chunks = row.get("sources"), row.get("chunk_index")
            at = step1.num(row.get("monotonic"))
            if (
                isinstance(sources, list)
                and isinstance(chunks, list)
                and sources
                and len(sources) == len(chunks)
                and at is not None
            ):
                kept = [[source, chunk] for source, chunk in zip(sources, chunks, strict=True)]
                ordered = sorted(kept, key=lambda item: json.dumps(item, ensure_ascii=False))
                fives[at] = {"order_sha256": sha_of(kept), "set_sha256": sha_of(ordered)}
    return fives, loads


def load_max(samples: Any, low: float | None, high: float | None) -> float | None:
    """The highest 1-minute load (vm.loadavg's first) of the samples taken between two times."""
    if low is None or high is None or not samples.ordered:
        return None
    inside = samples.rows[
        bisect.bisect_left(samples.times, low) : bisect.bisect_right(samples.times, high)
    ]
    found = [
        step1.num(row["loadavg"][0])
        for row in inside
        if isinstance(row.get("loadavg"), list) and row["loadavg"]
    ]
    values = [value for value in found if value is not None]
    return max(values) if values else None


def read_run(samples_path: Path, run_dir: Path) -> dict[str, Any]:
    notes: list[str] = []
    meta, rows = step1.read_samples(samples_path, notes)
    meta["loud_notes"] = step1.loud_notes(rows)
    samples = step1.Samples(rows, notes)
    try:
        launch = json.loads((run_dir / "launch.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        notes.append("run: no readable launch.json")
        launch = {}
    kept = {key: launch[key] for key in step1.LAUNCH_KEYS if key in launch}
    for key in ("cases", "ollama_models_before", "ollama_models_after", "unloaded_models"):
        if isinstance(kept.get(key), list):
            name = step1.an_id if key == "cases" else step1.a_name
            kept[key] = [name(item) for item in kept[key]]
    for key in ("label", "arm", "model", "model_digest", "mode", "status", "tenant", "code_sha"):
        if key in kept:
            kept[key] = step1.a_name(kept[key])
    given = kept.get("overrides")
    overrides: dict[Any, Any] = given if isinstance(given, dict) else {}
    if "overrides" in kept:
        kept["overrides"] = {str(k): step1.a_name(v) for k, v in sorted(overrides.items())}
    label = str(kept.get("label") or "")
    runtime = RUNS.get(label.removesuffix("-r2"))
    cases = step1.read_cases(run_dir / "cases", notes)
    spans = step1.read_spans(run_dir / "stages.jsonl", notes)
    groups = step1.assign(spans, cases)
    fives, loads = read_rows(run_dir / "stages.jsonl")
    # The API loads the reranker at its start, building the default tenant's retriever: before
    # the first question, beside no resident model. A later call returns the loaded one.
    starts = [case["t0_monotonic"] for case in cases if case["t0_monotonic"] is not None]
    first = min(starts) if starts else None
    for load in loads:
        end = load.pop("end")
        load["before_first_case"] = end is not None and first is not None and end <= first
    asks = []
    for case in cases:
        position = case["index"]
        arm = None
        if isinstance(position, int) and 1 <= position <= len(ARMS):
            arm = ARMS[position - 1]
        mine = groups.get(id(case), [])
        ask = step1.read_ask(case, mine, samples, arm)
        rerank = step1.one(mine, step1.RERANK)
        ask["five"] = fives.get(rerank["end"]) if rerank else None
        t0, total = case["t0_monotonic"], case["total_sec"]
        ask["load1_max"] = {
            "rerank": load_max(samples, rerank["start"], rerank["end"]) if rerank else None,
            "question": load_max(samples, t0, t0 + total)
            if t0 is not None and total is not None
            else None,
        }
        asks.append(ask)
    settings = read_settings(run_dir / "effective_settings.json", notes)
    drivers = {name: step1.sha256(run_dir.parent.parent / name) for name in DRIVERS_SHA256}
    # The file is hashed once its run is over, never while it runs: its 571 MB, read then, would
    # stand in the page cache beside the processes the series times.
    over = kept.get("status") in ("complete", "failed")
    onnx_sha256 = file_sha256(Path(ONNX)) if runtime == "onnx" and over else None
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
    named = kept.get("overrides") or {}
    pids = {pid for row in samples.rows for pid in step1.pids_of(row)}
    gate = {
        "launch": kept.get("code_sha") == CODE_SHA
        and kept.get("status") == "complete"
        and kept.get("runner_exit") == 0
        and kept.get("mode") == "prod"
        and kept.get("model") == step1.MODEL
        and kept.get("model_digest") == MODEL_DIGEST
        and runtime is not None
        and kept.get("arm") == ARMS
        and kept.get("cases") == list(CASES)
        and named.get("RAG_RERANKER_RUNTIME") == runtime
        and named.get("RAG_RERANKER_ONNX") == (ONNX if runtime == "onnx" else None),
        "settings": runtime is not None and settings == expected_settings(runtime),
        "drivers": drivers == DRIVERS_SHA256
        and step1.sha256(HERE / SAMPLER) == step1.SAMPLER_SHA256,
        "asks": [a["case_id"] for a in sorted(asks, key=lambda a: a["index"] or 0)] == list(CASES)
        and all(ask["read"] for ask in asks),
        "actions": all(a["arm_action"] and not a["arm_action"]["error"] for a in asks),
        "samples": meta["schema"] == step1.SAMPLES_SCHEMA and covered and not meta["loud_notes"],
        "reranker": bool(loads)
        and loads[0]["before_first_case"]
        and not any(load["error"] for load in loads)
        and (runtime == "torch" or onnx_sha256 == ONNX_SHA256),
        # Arm A on every question: the resident model's one llama-server from the preload to
        # the unload; a second is a reload or another model beside it.
        "llama": len(pids) == 1,
    }
    gate["passed"] = all(gate.values())
    return {
        "dir": str(run_dir),
        "label": kept.get("label"),
        "runtime": runtime,
        "samples": meta,
        "launch": kept,
        "settings": settings,
        "sha256": {name: step1.sha256(run_dir / name) for name in step1.RUN_FILES},
        "drivers_sha256": drivers,
        "onnx_sha256": onnx_sha256,
        "reranker_loads": loads,
        "llama_pids_seen": len(pids),
        "asks": asks,
        "gate": gate,
        "notes": notes,
    }


def window_value(ask: dict[str, Any], name: str, key: str) -> Any:
    return step1.window_value(ask, name, key)


def pair_up(runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each paired question's ask in the PyTorch run and in the INT8 run of a block; readable when
    both runs passed their gates, both asks are read and held arm A, they share the position and
    the candidates, and both have the rerank's and the whole question's seconds."""
    by_label: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        base = str(run["label"] or "").removesuffix("-r2")
        if base in RUNS:
            by_label.setdefault(base, []).append(run)
    pairs = []
    for block, labels in enumerate(BLOCKS, start=1):
        for case_id in PAIRED:
            pair: dict[str, Any] = {"block": block, "case_id": case_id, "readable": False}
            sides: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
            why: list[str] = []
            for side, label in zip(("torch", "onnx"), labels, strict=True):
                found = by_label.get(label, [])
                if len(found) != 1:
                    why.append(f"{label}: {len(found)} runs, not one")
                    continue
                asks = [ask for ask in found[0]["asks"] if ask["case_id"] == case_id]
                if len(asks) != 1:
                    why.append(f"{label}: {len(asks)} asks of the question, not one")
                    continue
                sides[side] = (found[0], asks[0])
            if len(sides) == 2:
                (run_t, t), (run_o, o) = sides["torch"], sides["onnx"]
                pair["torch"] = {"run": run_t["label"], "index": t["index"]}
                pair["onnx"] = {"run": run_o["label"], "index": o["index"]}
                why += [
                    f"run {run['label']}: its gate failed"
                    for run in (run_t, run_o)
                    if not run["gate"]["passed"]
                ]
                for side, ask in (("torch", t), ("onnx", o)):
                    why += [f"{side}: {reason}" for reason in ask["unread"]]
                    why += [f"{side}: {reason}" for reason in ask["arm_not_held"]]
                if t["index"] != o["index"]:
                    why.append("not at the same position")
                if (t["pool"] or {}).get("pool_sha256") != (o["pool"] or {}).get("pool_sha256"):
                    why.append("not the same candidates")
                if not (t["rerank_sec"] and o["rerank_sec"]) or None in (
                    t["whole_sec"],
                    o["whole_sec"],
                ):
                    why.append("no rerank or whole time to compare")
                pair["rerank_sec"] = {"torch": t["rerank_sec"], "onnx": o["rerank_sec"]}
                pair["whole_sec"] = {"torch": t["whole_sec"], "onnx": o["whole_sec"]}
                pair["printed"] = printed_of(t, o)
            pair["why"] = why
            pair["readable"] = not why
            pairs.append(pair)
    return pairs


def printed_of(t: dict[str, Any], o: dict[str, Any]) -> dict[str, Any]:
    """A pair's figures that decide nothing, each by side."""

    def both(value: Any) -> dict[str, Any]:
        return {"torch": value(t), "onnx": value(o)}

    five_t, five_o = t["five"] or {}, o["five"] or {}
    five = None
    if five_t and five_o:
        five = "same order"
        if five_t["order_sha256"] != five_o["order_sha256"]:
            five = "same set" if five_t["set_sha256"] == five_o["set_sha256"] else "other set"
    return {
        "vector_sec": both(lambda ask: ask["vector_sec"]),
        "retrieval_sec": both(lambda ask: ask["retrieval_sec"]),
        "first_token_sec": both(lambda ask: ask["first_token_sec"]),
        "total_sec": both(lambda ask: ask["total_sec"]),
        "answer_first_chunk_sec": both(
            lambda ask: (ask["answer_call"] or {}).get("first_chunk_sec")
        ),
        "rerank_faulted_mib": both(lambda ask: window_value(ask, "rerank", "faulted_mib")),
        "llama_mem_at_rerank_mib": both(
            lambda ask: (ask["at_rerank_start"] or {}).get("llama_mem_mib")
        ),
        "swap_used_at_rerank_mib": both(
            lambda ask: (ask["at_rerank_start"] or {}).get("swap_used_mib")
        ),
        "load1_max_rerank": both(lambda ask: ask["load1_max"]["rerank"]),
        "load1_max_question": both(lambda ask: ask["load1_max"]["question"]),
        "five": five,
    }


def sign_test(below: int, above: int) -> float | None:
    """The exact two-sided sign test's p over the pairs that differ."""
    n = below + above
    if not n:
        return None
    tail = sum(math.comb(n, i) for i in range(min(below, above) + 1))
    return min(1.0, 2 * tail / 2**n)


def compare(pairs: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    """INT8's seconds against PyTorch's over the readable pairs; the ratio is item 5a's,
    PyTorch's seconds over INT8's, and the saving PyTorch's less INT8's. A block's pairs share
    two runs and the Mac's state in them, so a reading holds only when every block leans its
    way: one run's state cannot carry it alone."""
    readable = [pair for pair in pairs if pair["readable"]]
    below = sum(1 for pair in readable if pair[key]["onnx"] < pair[key]["torch"])
    above = sum(1 for pair in readable if pair[key]["onnx"] > pair[key]["torch"])
    blocks = {str(number): [0, 0] for number in range(1, len(BLOCKS) + 1)}
    for pair in readable:
        tally = blocks[str(pair["block"])]
        tally[0] += int(pair[key]["onnx"] < pair[key]["torch"])
        tally[1] += int(pair[key]["onnx"] > pair[key]["torch"])
    p = sign_test(below, above)
    answer = "no detected difference"
    if len(readable) < MIN_PAIRS:
        answer = NOT_EVIDENCE
    elif p is not None and p < ALPHA:
        if below > above and all(b > a for b, a in blocks.values()):
            answer = "faster"
        elif above > below and all(a > b for b, a in blocks.values()):
            answer = "slower"
    ratios = [pair[key]["torch"] / pair[key]["onnx"] for pair in readable if pair[key]["onnx"]]
    savings = [pair[key]["torch"] - pair[key]["onnx"] for pair in readable]
    return {
        "answer": answer,
        "readable_pairs": len(readable),
        "onnx_below": below,
        "onnx_above": above,
        "ties": len(readable) - below - above,
        "blocks_below_above": blocks,
        "p": rounded(p, 6),
        "median_ratio": rounded(median(ratios), 4),
        "median_saving_sec": rounded(median(savings)),
        "by_pair": {
            f"{pair['block']}:{pair['case_id']}": [pair[key]["torch"], pair[key]["onnx"]]
            for pair in readable
        },
    }


def warm_up(run: dict[str, Any]) -> dict[str, Any] | None:
    """A run's first question: its rerank, the reranker's first call, its retriever's build for
    the tenant (the reranker already loaded) and its whole seconds."""
    asks = [ask for ask in run["asks"] if ask["case_id"] == WARM_UP]
    if len(asks) != 1:
        return None
    return {key: asks[0][key] for key in ("index", "rerank_sec", "build_sec", "whole_sec")}


def a_time(value: Any) -> str | None:
    return str(value) if value is not None and TIME.fullmatch(str(value)) else None


def a_hex(value: Any) -> str | None:
    return str(value) if value is not None and HEX.fullmatch(str(value)) else None


def read_environment(path: Path | None) -> list[dict[str, Any]]:
    """stand_env.py's lines: Ollama's version, its servers' pid and start, and the interpreter's
    installed distributions by SHA-256; nothing else of a line."""
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
        lines = [json.loads(line) for line in text.splitlines() if line.strip()]
    except (OSError, ValueError):
        return []
    out = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        given = line.get("ollama")
        ollama: dict[str, Any] = given if isinstance(given, dict) else {}
        given = ollama.get("servers")
        servers = [s for s in given if isinstance(s, dict)] if isinstance(given, list) else []
        given = line.get("distributions")
        found: dict[str, Any] = given if isinstance(given, dict) else {}
        out.append(
            {
                "taken": a_time(line.get("taken")),
                "server_version": step1.a_name(ollama.get("server_version")),
                "servers": [[step1.num(s.get("pid")), a_time(s.get("started"))] for s in servers],
                "freeze_sha256": a_hex(found.get("freeze_sha256")),
            }
        )
    return out


def stand_gate(corpus: dict[str, Any] | None, environment: list[dict[str, Any]]) -> dict[str, Any]:
    """V4's corpus files by their registered SHA-256; two or more environment lines, each naming
    Ollama 0.33.2 and one server, the same server with the same start and the same distributions
    in every line."""
    servers = {json.dumps(line["servers"]) for line in environment}
    freezes = {line["freeze_sha256"] for line in environment}
    gate = {
        "corpus": corpus is not None and corpus["sha256"] == CORPUS_SHA256,
        "environment": len(environment) >= 2
        and all(
            line["server_version"] == OLLAMA_VERSION
            and len(line["servers"]) == 1
            and None not in line["servers"][0]
            for line in environment
        )
        and len(servers) == 1
        and len(freezes) == 1
        and None not in freezes,
    }
    gate["passed"] = all(gate.values())
    return gate


def readings(
    pairs: Sequence[dict[str, Any]], runs: Sequence[dict[str, Any]], stand: dict[str, Any]
) -> dict[str, Any]:
    """The spec's readings: functions of the readable pairs alone, `NOT_EVIDENCE` on a stand
    that failed its gate; and the runs' loads and warm-ups, printed."""
    readable = [pair for pair in pairs if pair["readable"]]
    rerank, whole = compare(pairs, "rerank_sec"), compare(pairs, "whole_sec")
    if not stand["passed"]:
        rerank["answer"] = whole["answer"] = NOT_EVIDENCE

    def medians(key: str) -> dict[str, float | None]:
        return {
            side: median(
                [
                    pair["printed"][key][side]
                    for pair in readable
                    if pair["printed"][key][side] is not None
                ]
            )
            for side in ("torch", "onnx")
        }

    fives = [pair["printed"]["five"] for pair in readable]
    return {
        "rerank": rerank,
        "whole": whole,
        "printed_deciding_nothing": {
            "median_rerank_sec": {
                side: median([pair["rerank_sec"][side] for pair in readable])
                for side in ("torch", "onnx")
            },
            "median_whole_sec": {
                side: median([pair["whole_sec"][side] for pair in readable])
                for side in ("torch", "onnx")
            },
            **{
                f"median_{key}": medians(key)
                for key in (
                    "vector_sec",
                    "retrieval_sec",
                    "first_token_sec",
                    "total_sec",
                    "answer_first_chunk_sec",
                    "rerank_faulted_mib",
                    "llama_mem_at_rerank_mib",
                    "swap_used_at_rerank_mib",
                    "load1_max_rerank",
                    "load1_max_question",
                )
            },
            "fives": {name: fives.count(name) for name in ("same order", "same set", "other set")},
            "reranker_load_sec": {
                str(run["label"]): (run["reranker_loads"] or [{}])[0].get("sec") for run in runs
            },
            "warm_up": {str(run["label"]): warm_up(run) for run in runs},
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--run", nargs=2, action="append", required=True, metavar="PATH")
    parser.add_argument("--corpus")
    parser.add_argument("--environment")
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
        corpus = {
            "dir": str(folder),
            "sha256": {name: step1.sha256(folder / name) for name in step1.CORPUS_FILES},
        }
    environment = read_environment(Path(args.environment) if args.environment else None)
    stand = stand_gate(corpus, environment)
    pairs = pair_up(runs)
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "corpus": corpus,
        "environment": environment,
        "stand_gate": stand,
        "tools_sha256": {name: step1.sha256(HERE / name) for name in TOOLS},
        "runs": runs,
        "pairs": pairs,
        "readings": readings(pairs, runs, stand),
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    gates = {run["label"]: run["gate"] for run in runs}
    print(json.dumps({"gates": gates, "stand": stand}, sort_keys=True))
    print(json.dumps(record["readings"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
