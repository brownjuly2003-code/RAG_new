"""Stage 4, item 5's reader: thirty questions in one chat run under a 1,024-MiB prompt cache.

docs/specs/stage4-step5-cache-cap-series.md, registered with this tool before the first request.
On the Mac, any Python 3.11, the standard library only, beside step 0's reader:

  python -I step5_reader.py check SAMPLES LOG
  python -I step5_reader.py read OUT LOG SAMPLES RUN_DIR [--corpus DIR]

check, after the first question: llama-server's cache-state lines in Ollama's serve log since
the samples began. Exit 0 when there is at least one and each prints the 1,024-MiB limit, else 1.

read, after the series: step 0's reader (step0_reader.read_part, by the SHA-256 its spec lists)
cuts the log and step 0's sampler rows into a row a request and joins the rows to the run's
model calls and cases. A question's window runs on the monotonic clock from its start to its
end; inside it, the medians of the swap in use and of llama-server's footprint (the sampler)
and of the API's RSS (the supervisor's resources.jsonl, by the API's pid). Then the spec's gate,
its disturbance and its reading, frozen here. OUT holds numbers, enums, ids, the paths named
here, process names and SHA-256 strings: no log line, prompt, question or answer, and no
process's command line or environment. Prints the gate, the disturbance and the reading;
refuses an existing OUT.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

SCHEMA = "stage4-step5/v1"
SPEC = "docs/specs/stage4-step5-cache-cap-series.md"
HERE = Path(__file__).resolve().parent
NOT_EVIDENCE = "NOT_EVIDENCE"
MIB = 1048576
# Step 0's reader and sampler by the SHA-256 its spec lists: beside this file on the Mac, in
# their own folder in the repository.
STEP0_SHA256 = {
    "step0_reader.py": "2bdca7e9288b41857651d1a91ec823c2437d7ed8b6305da183148dc3df95e978",
    "step0_sampler.py": "a0b3e53d78584f454d252770898efb884b77aa80f0fff1729992ec1a37c6d18c",
}
STEP0_HOMES = (HERE, HERE.parents[1] / "stage4-step0" / "tools")
# The series as the spec names it: V4's stand, its drivers as step 0's runs read them.
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
DRIVERS_SHA256 = {
    "launch.py": "3098a60df73f86d349a2c9619666340503f13d1f3113fb0b23a1eb1475da7531",
    "live_api.py": "43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5",
    "live_runner.py": "fd5f7d7b66e5be827cb1cbc23074d6b7955f64d18143a11a1f9cd4dbe9caf4d1",
    "live_supervisor.py": "32e5a40552b62c37ee1e3cc387ae01a453b7729adadd7b9f790d73bb1906138c",
}
# aircargo's registered order (evaluation/curated_cases_aircargo.jsonl, 3737d694...), its first 30
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
    "aircargo-templates-insufficient",
    "aircargo-secret-check",
    "aircargo-secret-not-auto",
    "aircargo-secret-disclosure",
    "aircargo-pdp-scope",
    "aircargo-pdp-data",
    "aircargo-pdp-uncertain",
    "aircargo-claims-delay",
    "aircargo-claims-damage",
    "aircargo-claims-lawyer",
    "aircargo-claims-forbidden",
    "aircargo-expedition-vs-carrier",
    "aircargo-expedition-mawb-hawb",
    "aircargo-expedition-risks",
    "aircargo-road-cutoff",
    "aircargo-road-penalty",
    "aircargo-road-seal",
)
# The spec's readings, frozen with it.
CAP_MIB = 1024.0
REFERENCE = (6, 10)  # questions, counted from 1, both ends in
LAST = (26, 30)
GROWTH_MIB = 512.0
FOREIGN_RSS_MIB = 512.0
VM_NAMES = ("qemu", "limactl", "virtualization")
CONFIG_FILE = re.compile(r"using config file: (\S+)\s*$")


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def median(values: Sequence[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def step0_home() -> Path:
    for home in STEP0_HOMES:
        if (home / "step0_reader.py").is_file():
            return home
    raise SystemExit("refused: no step0_reader.py beside this tool or in its repository folder")


def load_step0(home: Path) -> ModuleType:
    """Step 0's reader, refused unless its bytes are the ones its spec lists."""
    path = home / "step0_reader.py"
    if sha256(path) != STEP0_SHA256["step0_reader.py"]:
        raise SystemExit(f"refused: {path} is not step 0's reader by its SHA-256")
    spec = importlib.util.spec_from_file_location("step0_reader", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"refused: {path} does not load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def requests_of(part: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for process in part["processes"] for row in process["requests"]]


def cache_states(part: dict[str, Any]) -> dict[str, Any]:
    """Every request's cache-state line: the limits it printed and the sizes the cache held."""
    rows = requests_of(part)
    states = [row for row in rows if row["cache_limit_mib"] is not None]
    held = [row["cache_mib"] for row in states if row["cache_mib"] is not None]
    reduced = [row["cache_limit_reduced_mib"] for row in rows]
    reduced = [value for value in reduced if value is not None]
    limits = sorted({row["cache_limit_mib"] for row in states})
    in_force = bool(states) and limits == [CAP_MIB] and not reduced
    return {
        "requests": len(rows),
        "states": len(states),
        "limits_mib": limits,
        "max_mib": max(held) if held else None,
        "reduced_to_mib": reduced,
        "removed_entries": sum(row["removed_entries"] for row in rows),
        "removed_mib": round(sum(row["removed_mib"] for row in rows), 3),
        "skipped_saves": sum(row["skipped_saves"] for row in rows),
        "in_force": in_force and max(held, default=0.0) <= CAP_MIB,
    }


def config_files(step0: ModuleType, log: Path, samples_path: Path) -> list[str]:
    """The config files llama-server named as it started, in the samples' slice of the log."""
    notes: list[str] = []
    samples = step0.Samples(step0.read_samples(samples_path, notes)[1], notes)
    if not samples.bytes:
        return []
    lines, _ = step0.read_slice(log, samples.bytes[0], samples.bytes[-1], notes)
    found = (CONFIG_FILE.search(text) for _, _, text in lines)
    return sorted({match.group(1) for match in found if match})


def a_proc(value: Any) -> bool:
    """A supervisor's process entry: pid, CPU %, RSS in bytes, the executable's path's tail."""
    if not isinstance(value, list) or len(value) != 4:
        return False
    pid, cpu, rss, name = value
    numbers = isinstance(pid, int) and isinstance(cpu, (int, float)) and isinstance(rss, int)
    return numbers and isinstance(name, str)


def read_resources(path: Path, notes: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The supervisor's samples, every 3 s: its process list (python, ollama, postgres and
    llama by name) and the five largest processes by RSS; never a command line."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        notes.append("run: no resources.jsonl")
        lines = []
    rows = []
    errors = 0
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else {}
        except ValueError:
            errors += 1
            continue
        if not isinstance(row.get("monotonic"), (int, float)):
            errors += bool(row)  # a monitor error, or a shape this tool does not know
            continue
        procs = [proc for proc in row.get("procs") or [] if a_proc(proc)]
        largest = [proc for proc in row.get("largest") or [] if a_proc(proc)]
        rows.append({"monotonic": row["monotonic"], "procs": procs, "largest": largest})
    if errors:
        notes.append(f"resources: {errors} lines unread or with a monitor error")
    meta = {"file": path.name, "sha256": sha256(path), "samples": len(rows)}
    return meta, rows


def api_pid_of(run_dir: Path) -> int | None:
    try:
        pid = json.loads((run_dir / "launch.json").read_text(encoding="utf-8")).get("api_pid")
    except (OSError, ValueError, AttributeError):
        return None
    return pid if isinstance(pid, int) else None


def series_pid(samples: Any, low: float, high: float) -> tuple[int | None, int]:
    """The llama-server pid of the series' window when it is the only one, and how many."""
    rows = [row for row in samples.rows if low <= row["monotonic"] <= high]
    pids = sorted({proc.get("pid") for row in rows for proc in row.get("procs") or []} - {None})
    return (pids[0] if len(pids) == 1 else None), len(pids)


def timed_cases(part: dict[str, Any]) -> list[dict[str, Any]]:
    """The run's cases with a start and a duration, in the order they began."""
    cases = [
        case
        for case in (part["run"] or {}).get("cases") or []
        if isinstance(case.get("t0_monotonic"), (int, float))
        and isinstance(case.get("total_sec"), (int, float))
    ]
    return sorted(cases, key=lambda case: case["t0_monotonic"])


def question_rows(
    part: dict[str, Any],
    samples: Any,
    resources: list[dict[str, Any]],
    api_pid: int | None,
    pid: int | None,
) -> list[dict[str, Any]]:
    """A row a question, in the order they began: its window, its medians, its requests."""
    requests = requests_of(part)
    rows = []
    for n, case in enumerate(timed_cases(part), start=1):
        low, high = case["t0_monotonic"], case["t0_monotonic"] + case["total_sec"]
        inside = [row for row in samples.rows if low <= row["monotonic"] <= high]
        swap = [(row.get("swap_mib") or {}).get("used") for row in inside]
        procs = [proc for row in inside for proc in row.get("procs") or []]
        mem = [proc.get("mem_mib") for proc in procs if pid is not None and proc.get("pid") == pid]
        loads = [row.get("loadavg") for row in inside]
        api = [
            proc[2] / MIB
            for row in resources
            if low <= row["monotonic"] <= high
            for proc in row["procs"]
            if proc[0] == api_pid
        ]
        own = [row for row in requests if row.get("case_id") == case["case_id"]]
        states = [row for row in own if row["cache_mib"] is not None]
        rows.append(
            {
                "n": n,
                "case_id": case["case_id"],
                "route": case["route"],
                "tokens": case["tokens"],
                "client_error": case["client_error"],
                "start": round(low, 3),
                "end": round(high, 3),
                "total_sec": case["total_sec"],
                "samples": len(inside),
                "swap_mib": median([value for value in swap if value is not None]),
                "swap_max_mib": max((value for value in swap if value is not None), default=None),
                "footprint_mib": median([value for value in mem if value is not None]),
                "api_rss_mib": median(api),
                "load5": median([load[1] for load in loads if isinstance(load, list)]),
                "requests": len(own),
                "roles": [row["role"] for row in own],
                "cache_mib": states[-1]["cache_mib"] if states else None,
                "cache_prompts": states[-1]["cache_prompts"] if states else None,
                "removed_entries": sum(row["removed_entries"] for row in own),
            }
        )
    return rows


def disturbance(
    samples: Any, resources: list[dict[str, Any]], api_pid: int | None, low: float, high: float
) -> dict[str, Any]:
    """Another model, a large Python process other than the API, or a virtual machine, at any
    sample from the first question's start to the last one's end. A Python whose path holds only
    a capital `Python` misses the supervisor's list; it is looked for among the largest too."""
    _, pids = series_pid(samples, low, high)
    foreign: dict[int, dict[str, Any]] = {}
    vms: set[str] = set()
    for row in resources:
        if not low <= row["monotonic"] <= high:
            continue
        for pid, _, rss, name in row["procs"] + row["largest"]:
            if pid != api_pid and "python" in name.lower() and rss / MIB >= FOREIGN_RSS_MIB:
                seen = foreign.setdefault(pid, {"pid": pid, "name": name, "peak_rss_mib": 0.0})
                seen["peak_rss_mib"] = max(seen["peak_rss_mib"], round(rss / MIB, 1))
        vms.update(
            proc[3] for proc in row["largest"] if any(v in proc[3].lower() for v in VM_NAMES)
        )
    reasons = []
    if pids > 1:
        reasons.append(f"{pids} llama-server processes")
    if foreign:
        reasons.append("a Python process other than the API at 512 MiB or more")
    if vms:
        reasons.append("a virtual machine among the five largest processes")
    return {
        "llama_server_pids": pids,
        "foreign_python": [foreign[pid] for pid in sorted(foreign)],
        "virtual_machines": sorted(vms),
        "disturbed": bool(reasons),
        "reasons": reasons,
    }


def gate(
    part: dict[str, Any],
    cap: dict[str, Any],
    rows: list[dict[str, Any]],
    api_pid: int | None,
    llama_pids: int,
) -> dict[str, Any]:
    """The series as registered, each question read, each call one request, the cap in force."""
    run = part["run"] or {}
    launch = run.get("launch") or {}
    expected = {
        "code_sha": CODE_SHA,
        "status": "complete",
        "runner_exit": 0,
        "cases": list(CASES),
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "ollama_models_before": [],
    }
    reasons = [
        f"launch: {key} is not the series'"
        for key, value in expected.items()
        if launch.get(key) != value
    ]
    if run.get("drivers_sha256") != DRIVERS_SHA256:
        reasons.append("the chat drivers are not V4's")
    if api_pid is None:
        reasons.append("launch: no API pid")
    if [row["case_id"] for row in rows] != list(CASES):
        reasons.append("the questions read are not the thirty in their order")
    if any(row["client_error"] for row in rows):
        reasons.append("a question with a client error")
    if any(row["samples"] == 0 for row in rows):
        reasons.append("a question with no sample inside it")
    if llama_pids == 0:
        reasons.append("the sampler saw no llama-server process in the questions")
    joined = run.get("joined") or {}
    counts = {joined.get(key) for key in ("calls", "matched", "requests")}
    if not joined.get("requests") or len(counts) != 1:
        reasons.append("the model calls and the log's requests do not match one to one")
    if any(row["complete"] and row["cache_limit_mib"] is None for row in requests_of(part)):
        reasons.append("a request with no cache-state line")
    if not cap["in_force"]:
        reasons.append("the 1,024-MiB limit is not on every cache-state line, or it was passed")
    return {"passed": not reasons, "reasons": reasons}


def window(rows: list[dict[str, Any]], bounds: tuple[int, int], key: str) -> float | None:
    """The median of a field over the questions of a window; None if one of them lacks it."""
    values = [row[key] for row in rows if bounds[0] <= row["n"] <= bounds[1]]
    if len(values) != bounds[1] - bounds[0] + 1 or any(value is None for value in values):
        return None
    return median(values)


def change(rows: list[dict[str, Any]], key: str) -> float | None:
    first, last = window(rows, REFERENCE, key), window(rows, LAST, key)
    return round(last - first, 3) if first is not None and last is not None else None


def reading(
    rows: list[dict[str, Any]], gate_row: dict[str, Any], disturbed: dict[str, Any]
) -> dict[str, Any]:
    """«Своп не растёт»: the swap's median over questions 26-30 against 6-10."""
    out: dict[str, Any] = {"swap": NOT_EVIDENCE, "why": None}
    out.update(reference_mib=window(rows, REFERENCE, "swap_mib"))
    out.update(last_mib=window(rows, LAST, "swap_mib"), growth_mib=change(rows, "swap_mib"))
    if not gate_row["passed"]:
        out["why"] = "the gate failed"
    elif disturbed["disturbed"]:
        out["why"] = "the series was disturbed"
    elif out["growth_mib"] is None:
        out["why"] = "a question of the two windows has no swap"
    else:
        out["swap"] = "holds" if out["growth_mib"] < GROWTH_MIB else "grows"
    return out


def printed(rows: list[dict[str, Any]], samples: Any, cap: dict[str, Any]) -> dict[str, Any]:
    """What no reading uses: it decides nothing."""
    later = [row for row in rows if row["n"] >= REFERENCE[0] and row["swap_mib"] is not None]
    slope = None
    if len(later) >= 2:
        fit = statistics.linear_regression(
            [row["n"] for row in later], [row["swap_mib"] for row in later]
        )
        slope = round(fit.slope, 3)
    swap = [(row.get("swap_mib") or {}).get("used") for row in samples.rows]
    swap = [value for value in swap if value is not None]
    seconds = [row["total_sec"] for row in rows]
    return {
        "footprint_change_mib": change(rows, "footprint_mib"),
        "api_rss_change_mib": change(rows, "api_rss_mib"),
        "swap_slope_mib_per_question": slope,
        "swap_first_sample_mib": swap[0] if swap else None,
        "swap_last_sample_mib": swap[-1] if swap else None,
        "swap_max_in_questions_mib": max(
            (row["swap_max_mib"] for row in rows if row["swap_max_mib"] is not None), default=None
        ),
        "cache_max_mib": cap["max_mib"],
        "removed_entries": cap["removed_entries"],
        "removed_mib": cap["removed_mib"],
        "skipped_saves": cap["skipped_saves"],
        "total_sec_median": median(seconds),
        "total_sec_sum": round(sum(seconds), 3),
        "load5_median": median([row["load5"] for row in rows if row["load5"] is not None]),
    }


def read_series(
    step0: ModuleType, home: Path, log: Path, samples_path: Path, run_dir: Path
) -> dict[str, Any]:
    part = step0.read_part(log, samples_path, run_dir, None, None)
    notes: list[str] = []
    samples = step0.Samples(step0.read_samples(samples_path, notes)[1], notes)
    resources_meta, resources = read_resources(run_dir / "resources.jsonl", part["notes"])
    api_pid = api_pid_of(run_dir)
    cases = timed_cases(part)
    # the series' window: the first question's start to the last one's end
    low, high = 0.0, -1.0
    if cases:
        low = cases[0]["t0_monotonic"]
        high = max(case["t0_monotonic"] + case["total_sec"] for case in cases)
    pid, pids = series_pid(samples, low, high)
    rows = question_rows(part, samples, resources, api_pid, pid)
    cap = cache_states(part)
    disturbed = disturbance(samples, resources, api_pid, low, high)
    gate_row = gate(part, cap, rows, api_pid, pids)
    return {
        "schema": SCHEMA,
        "spec": SPEC,
        "log": str(log),
        "tools_sha256": {
            "step5_reader.py": sha256(HERE / "step5_reader.py"),
            "step0_reader.py": sha256(home / "step0_reader.py"),
            "step0_sampler.py": sha256(home / "step0_sampler.py"),
        },
        "config_files": config_files(step0, log, samples_path),
        "part": part,
        "resources": {**resources_meta, "api_pid": api_pid},
        "series_pid": pid,
        "questions": rows,
        "cache": cap,
        "gate": gate_row,
        "disturbance": disturbed,
        "reading": reading(rows, gate_row, disturbed),
        "printed": printed(rows, samples, cap),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    check = modes.add_parser("check")
    check.add_argument("samples")
    check.add_argument("log")
    read = modes.add_parser("read")
    for name in ("out", "log", "samples", "run_dir"):
        read.add_argument(name)
    read.add_argument("--corpus")
    args = parser.parse_args(argv)
    home = step0_home()
    step0 = load_step0(home)
    if args.mode == "check":
        part = step0.read_part(Path(args.log), Path(args.samples), None, None, None)
        cap = cache_states(part)
        result = {key: cap[key] for key in ("states", "limits_mib", "max_mib", "in_force")}
        result["config_files"] = config_files(step0, Path(args.log), Path(args.samples))
        print(json.dumps(result, sort_keys=True))
        return 0 if cap["in_force"] else 1
    out = Path(args.out)
    if out.exists():
        print(f"refused: {out} exists", file=sys.stderr)
        return 2
    record = read_series(step0, home, Path(args.log), Path(args.samples), Path(args.run_dir))
    corpus = None
    if args.corpus:
        folder = Path(args.corpus)
        corpus = {"dir": str(folder), "sha256": {n: sha256(folder / n) for n in step0.CORPUS_FILES}}
    record["corpus"] = corpus
    out.write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    shown = {key: record[key] for key in ("gate", "reading")}
    shown["disturbance"] = record["disturbance"]["reasons"]
    print(json.dumps(shown, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
