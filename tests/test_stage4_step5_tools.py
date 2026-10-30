"""reports/stage4-step5/tools: the series' reader on a synthetic run, its gate, its disturbance and
its reading.

docs/specs/stage4-step5-cache-cap-series.md. Synthetic fixtures only: every number, path and text
in them is made up. The log lines copy the shapes step 0's reader reads; the cache's lines and the
config-file line copy llama.cpp's format strings at b10630 (tools/server/server-context.cpp and
server-task.cpp, common/arg.cpp) in the order its server prints them. The run's files copy the
chat-live drivers' (reports/stage1/tools), the supervisor's resources.jsonl included.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step5" / "tools"
STEP0_TOOLS = ROOT / "reports" / "stage4-step0" / "tools"
SPEC = ROOT / "docs" / "specs" / "stage4-step5-cache-cap-series.md"
STEP0_SPEC = ROOT / "docs" / "specs" / "stage4-step0-diagnostics.md"
MIB = 1048576


def tool(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reader = tool(TOOLS / "step5_reader.py", "step5_reader")

STREAM, GENERATE = "ollama.generate_stream", "ollama.generate"
LLAMA, API, POSTGRES = 4242, 4321, 77
BASE = 5000.0  # the sampler's first sample on the monotonic clock
FIRST = 5010.0  # the first question's start
EVERY = 60.0  # a question every minute, 50 s long
CONFIG = "/fake/home/.config/llama.cpp/config.ini"
API_NAME = "a/RAG_Support_Assistant/.venv/bin/python"
LLAMA_NAME = "AG_new_tools_ollama_v0.33.2/llama-server"
PYTHON_NAME = "sources/Python.app/Contents/MacOS/Python"
VM_NAME = "MacOS/com.apple.Virtualization.VirtualMachine"
# role, stage, offset from the question's start, prompt tokens, generated tokens, seconds
CALLS = (
    ("answer", STREAM, 5.0, 2400, 200, 25.0),
    ("self_eval", GENERATE, 31.0, 2500, 4, 9.0),
    ("suggestions", GENERATE, 41.0, 400, 45, 6.0),
)


def slot(task: int, function: str, text: str) -> str:
    return f"slot {function[:12]:>12}: id  0 | task {task} | {text}"


def srv(function: str, text: str) -> str:
    return f"srv  {function[:12]:>12}: {text}"


def state_mib(tokens: int) -> float:
    """A prompt's saved state at 144 KiB a token, as step 0's test has it."""
    return round(tokens * 144 / 1024, 3)


def question_at(at: float, questions: int) -> int:
    """The question running at a time, counted from 1, held at the ends."""
    return min(questions, max(1, int((at - FIRST) // EVERY) + 1))


def preamble(
    cache: list[float], saved: int | None, limit: float
) -> tuple[list[str], list[float], int]:
    """The cache's update before a task: the slot's last prompt saved, the oldest entries removed
    to make room for it, the state printed with its limits. The lines, the cache, the removals."""
    lines = []
    removed = 0
    if saved is not None:
        size = state_mib(saved)
        lines.append(
            slot(-1, "get_available_slot", f" - checking sim = 0.008 (20/{saved}) > 0.100")
        )
        lines.append(srv("get_available_slot", "updating prompt cache"))
        lines.append(
            srv(
                "prompt_save",
                f" - saving prompt with length {saved}, total state size = {size:.3f} MiB "
                "(draft: 0.000 MiB)",
            )
        )
        while cache and sum(cache) + size > limit:
            lines.append(
                srv(
                    "alloc",
                    " - making room for prompt cache entry, removing oldest entry "
                    f"(size = {cache[0]:.3f} MiB)",
                )
            )
            cache, removed = cache[1:], removed + 1
        cache = [*cache, size]
    est = max(4096, int(limit * 1024 / 144))
    lines.append(
        srv(
            "update",
            f" - cache state: {len(cache)} prompts, {sum(cache):.3f} MiB "
            f"(limits: {limit:.3f} MiB, 4096 tokens, {est} est)",
        )
    )
    return lines, cache, removed


def task_lines(task: int, tokens: int, generated: int, at: float, seconds: float) -> list[Any]:
    """A task's slot lines: its prompt from at, its summary and release as it ends."""
    prompt_ms, eval_ms = seconds * 600.0, seconds * 400.0
    end = at + seconds
    summary = (
        f"prompt eval time = {prompt_ms:10.2f} ms / {tokens - 5:5d} tokens",
        f"       eval time = {eval_ms:10.2f} ms / {generated:5d} tokens",
        f"      total time = {prompt_ms + eval_ms:10.2f} ms / {tokens - 5 + generated:5d} tokens",
    )
    new = f"new prompt, n_ctx_slot = 4096, n_keep = 4, task.n_tokens = {tokens}"
    release = f"stop processing: n_tokens = {tokens + generated}, truncated = 0"
    return [
        (at, slot(task, "launch_slot_with_task", new)),
        (at, slot(task, "update_slots", "cached n_tokens = 5, memory_seq_rm [5, end)")),
        *((end - 0.4, slot(task, "print_timing", text)) for text in summary),
        (end - 0.3, slot(task, "release", release)),
    ]


def scenario(
    tmp_path: Path,
    questions: int = 30,
    limit: float = 1024.0,
    swap_per_question: float = 0.0,
    human: frozenset[int] = frozenset(),
    resources_extra: Callable[[float], tuple[list[Any], list[Any]]] | None = None,
    llama_servers: int = 1,
) -> dict[str, Any]:
    """One series on disk: the log, the sampler's file, the run with its resources, the drivers.
    A llama-server loads at 5003.4 s (with llama_servers 2, a second in question 13; with 0, the
    sampler sees none); question n starts at 5010 + 60 (n - 1) s and lasts 50 s,
    its answer, self-evaluation and (route auto) suggestions each one request. The footprint is
    2,900 MiB and the cache; the swap 3,000 MiB and swap_per_question for each question before.
    Also returned: the removals a question and the most the cache held."""
    timed: list[tuple[float, str]] = [
        (5003.4, "build: 7001 (abc1234) with Apple clang version 15.0.0 for x86_64-apple-darwin"),
        (5003.4, f"using config file: {CONFIG}"),
        (5003.5, "load_tensors: loading model tensors, this can take a while... (mmap = false)"),
        (5003.6, "main: model loaded"),
    ]
    stages: list[dict[str, Any]] = []
    states: list[tuple[float, float]] = []  # each cache-state line's time and the cache it holds
    cache: list[float] = []
    removals = [0] * questions
    saved: int | None = None
    task = 0
    for n in range(1, questions + 1):
        start = FIRST + EVERY * (n - 1)
        calls = CALLS[:2] if n in human else CALLS
        for _, stage, offset, tokens, generated, seconds in calls:
            at = start + offset
            lines, cache, removed = preamble(cache, saved, limit)
            removals[n - 1] += removed
            timed += [(at + 0.5, line) for line in lines]
            states.append((at + 0.5, float(f"{sum(cache):.3f}")))
            timed += task_lines(task, tokens, generated, at + 0.6, seconds)
            thread = 7001 if stage == STREAM else 7002
            info = {
                "stage": stage,
                "thread": thread,
                "prompt_est_tokens": tokens,
                "max_tokens": 512,
            }
            stages.append({**info, "event": "start", "monotonic": at})
            stages.append({**info, "event": "end", "monotonic": at + seconds + 0.6, "error": None})
            saved, task = tokens + generated, task + 3
    end = FIRST + EVERY * questions
    timed.sort(key=lambda pair: pair[0])
    log = tmp_path / "ollama_serve.log"
    log.write_bytes("".join(line + "\n" for _, line in timed).encode())
    rows: list[dict[str, Any]] = [
        {"kind": "start", "schema": "stage4-step0-samples/v1", "monotonic": BASE, "every_sec": 5.0},
    ]
    at = BASE
    while at <= end + 10:
        size = sum(len(line) + 1 for written, line in timed if written <= at)
        held = ([0.0] + [mib for written, mib in states if written <= at])[-1]
        procs = []
        if 5003.4 < at < end and llama_servers:
            procs.append({"pid": LLAMA, "rss_mib": 2500.0, "mem_mib": 2900.0 + held})
            if llama_servers == 2 and FIRST + EVERY * 12 < at < FIRST + EVERY * 13:
                procs.append({"pid": LLAMA + 1, "rss_mib": 2500.0, "mem_mib": 2900.0})
        swap = 3000.0 + swap_per_question * (question_at(at, questions) - 1)
        rows.append(
            {
                "kind": "sample",
                "utc": "2026-10-30T06:00:00.000Z",
                "monotonic": at,
                "log_bytes": size,
                "page_size": 4096,
                "vm": {},
                "swap_mib": {"total": 4096.0, "used": swap, "free": 4096.0 - swap},
                "loadavg": [3.1, 3.4, 2.9],
                "procs": procs,
                "notes": [] if procs else ["ps: no process named llama-server"],
            }
        )
        at += 5.0
    rows.append({"kind": "stop", "monotonic": at, "reason": "stop file"})
    samples = tmp_path / "step5" / "s5-test.samples.jsonl"
    samples.parent.mkdir()
    samples.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
    chatlive = tmp_path / "chatlive"
    run = chatlive / "runs" / "s5-test"
    (run / "cases").mkdir(parents=True)
    for name in reader.DRIVERS_SHA256:
        (chatlive / name).write_text(f"# a synthetic driver, {name}\n", "utf-8")
    ids = list(reader.CASES[:questions])
    launch: dict[str, Any] = {"label": "s5-test", "mode": "prod", "cases": ids}
    launch.update(client_cap_sec="1020/1200", code_sha=reader.CODE_SHA, model=reader.MODEL)
    launch.update(model_digest=reader.MODEL_DIGEST, status="complete", runner_exit=0)
    launch.update(ollama_models_before=[], api_pid=API, env={"API_TOKEN": "SECRET-0001"})
    (run / "launch.json").write_text(json.dumps(launch), "utf-8")
    (run / "stages.jsonl").write_text("".join(json.dumps(row) + "\n" for row in stages), "utf-8")
    for n, case_id in enumerate(ids, start=1):
        route = "human" if n in human else "auto"
        result = {"at": 49.0, "type": "result", "route": route, "answer": "SYNTHETIC ANSWER"}
        case: dict[str, Any] = {"case_id": case_id, "question": "SYNTHETIC QUESTION"}
        case.update(events=[{"at": 20.0, "type": "token", "text": "SYNTHETIC ANSWER"}, result])
        case.update(t0_monotonic=FIRST + EVERY * (n - 1), total_sec=50.0, tokens=200)
        (run / "cases" / f"{n:02d}-{case_id}.json").write_text(json.dumps(case), "utf-8")
    lines = []
    at = BASE + 5
    while at <= end + 5:
        procs_now: list[Any] = [
            [API, 40.0, 1800 * MIB, API_NAME],
            [LLAMA, 90.0, 2500 * MIB, LLAMA_NAME],
            [POSTGRES, 0.1, 30 * MIB, "/opt/fake/bin/postgres"],
        ]
        largest: list[Any] = [[LLAMA, 90.0, 2500 * MIB, LLAMA_NAME]]
        largest += [[API, 40.0, 1800 * MIB, API_NAME]]
        largest += [[9001, 2.0, 700 * MIB, " Chrome.app/Contents/MacOS/Google Chrome"]]
        if resources_extra is not None:
            more_procs, more_largest = resources_extra(at)
            procs_now += more_procs
            largest += more_largest
        row = {"at": "2026-10-30T06:00:00+00:00", "monotonic": at, "swap": "used = 3000.00M"}
        row.update(procs=procs_now, busiest=largest[:5], largest=largest[:5])
        lines.append(json.dumps(row))
        at += 3.0
    lines.insert(3, json.dumps({"monitor_error": "TimeoutExpired"}))
    (run / "resources.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
    peak = max(mib for _, mib in states)
    return {"log": log, "samples": samples, "run": run, "removals": removals, "peak_mib": peak}


@pytest.fixture
def drivers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The synthetic drivers' SHA-256 stand in for V4's in the gate."""
    digests = {
        name: hashlib.sha256(f"# a synthetic driver, {name}\n".encode()).hexdigest()
        for name in reader.DRIVERS_SHA256
    }
    monkeypatch.setattr(reader, "DRIVERS_SHA256", digests)


def read(folder: Path, paths: dict[str, Any], *more: str) -> dict[str, Any]:
    out = folder / "step5.json"
    argv = ["read", str(out), str(paths["log"]), str(paths["samples"]), str(paths["run"]), *more]
    assert reader.main(argv) == 0
    record: dict[str, Any] = json.loads(out.read_text("utf-8"))
    return record


def test_the_series_under_the_cap_reads_whole_and_the_flat_swap_holds(
    tmp_path: Path, drivers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = scenario(tmp_path, human=frozenset({2}))
    corpus = tmp_path / "corpus"
    (corpus / "index").mkdir(parents=True)
    for name in reader.load_step0(reader.step0_home()).CORPUS_FILES:
        (corpus / name).write_text(f"synthetic {name}\n", "utf-8")
    record = read(tmp_path, paths, "--corpus", str(corpus))
    shown = json.loads(capsys.readouterr().out)
    assert shown["reading"]["swap"] == "holds" and shown["disturbance"] == []
    assert (record["schema"], record["spec"]) == (reader.SCHEMA, reader.SPEC)
    assert record["gate"] == {"passed": True, "reasons": []}
    assert record["disturbance"] == {
        "llama_server_pids": 1,
        "foreign_python": [],
        "virtual_machines": [],
        "disturbed": False,
        "reasons": [],
    }
    assert record["config_files"] == [CONFIG]
    assert record["series_pid"] == LLAMA and record["resources"]["api_pid"] == API
    assert record["part"]["run"]["joined"] == {"calls": 89, "matched": 89, "requests": 89}
    assert record["reading"] == {
        "swap": "holds",
        "why": None,
        "reference_mib": 3000.0,
        "last_mib": 3000.0,
        "growth_mib": 0.0,
    }
    questions = record["questions"]
    assert [row["case_id"] for row in questions] == list(reader.CASES)
    assert [row["n"] for row in questions] == list(range(1, 31))
    assert questions[1]["route"] == "human" and questions[1]["roles"] == ["answer", "self_eval"]
    assert questions[0]["roles"] == ["answer", "self_eval", "suggestions"]
    assert all(row["samples"] == 11 for row in questions)
    assert all(row["api_rss_mib"] == 1800.0 for row in questions)
    assert all(row["load5"] == 3.4 for row in questions)
    # the cache never passes its limit: it removes its oldest entries from the second question on
    cache = record["cache"]
    assert cache["limits_mib"] == [1024.0] and cache["in_force"] is True
    assert cache["states"] == cache["requests"] == 89 and cache["reduced_to_mib"] == []
    assert cache["max_mib"] == paths["peak_mib"] <= 1024.0
    assert [row["removed_entries"] for row in questions] == paths["removals"]
    assert cache["removed_entries"] == sum(paths["removals"]) > 30
    assert paths["removals"][:2] == [0, 1]
    assert all(2900.0 <= row["footprint_mib"] <= 2900.0 + 1024.0 for row in questions)
    printed = record["printed"]
    assert printed["swap_slope_mib_per_question"] == 0.0
    assert printed["api_rss_change_mib"] == 0.0
    assert (printed["swap_first_sample_mib"], printed["swap_last_sample_mib"]) == (3000.0, 3000.0)
    assert printed["total_sec_median"] == 50.0 and printed["total_sec_sum"] == 1500.0
    assert printed["cache_max_mib"] == cache["max_mib"]
    assert record["corpus"] == {
        "dir": str(corpus),
        "sha256": {
            name: hashlib.sha256(f"synthetic {name}\n".encode()).hexdigest()
            for name in ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
        },
    }
    text = json.dumps(record)
    assert "SYNTHETIC" not in text and "SECRET" not in text and "Chrome" not in text
    assert record["tools_sha256"] == {
        "step5_reader.py": hashlib.sha256((TOOLS / "step5_reader.py").read_bytes()).hexdigest(),
        "step0_reader.py": reader.STEP0_SHA256["step0_reader.py"],
        "step0_sampler.py": reader.STEP0_SHA256["step0_sampler.py"],
    }


@pytest.mark.parametrize(
    ("per_question", "verdict", "growth"),
    [(0.0, "holds", 0.0), (25.0, "holds", 500.0), (25.6, "grows", 512.0), (30.0, "grows", 600.0)],
)
def test_the_swap_from_questions_6_to_10_against_26_to_30_decides(
    tmp_path: Path, drivers: None, per_question: float, verdict: str, growth: float
) -> None:
    record = read(tmp_path, scenario(tmp_path, swap_per_question=per_question))
    assert record["reading"]["swap"] == verdict
    assert record["reading"]["growth_mib"] == pytest.approx(growth)
    assert record["reading"]["reference_mib"] == pytest.approx(3000.0 + 7 * per_question)
    slope = record["printed"]["swap_slope_mib_per_question"]
    assert slope == pytest.approx(per_question)


def test_the_default_limit_fails_the_gate_and_the_check(
    tmp_path: Path, drivers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = scenario(tmp_path, limit=8192.0)
    assert reader.main(["check", str(paths["samples"]), str(paths["log"])]) == 1
    checked = json.loads(capsys.readouterr().out)
    assert checked["limits_mib"] == [8192.0] and checked["in_force"] is False
    record = read(tmp_path, paths)
    assert record["gate"] == {
        "passed": False,
        "reasons": ["the 1,024-MiB limit is not on every cache-state line, or it was passed"],
    }
    assert record["reading"]["swap"] == "NOT_EVIDENCE"
    assert record["reading"]["why"] == "the gate failed"
    assert record["reading"]["growth_mib"] == 0.0


def test_the_check_after_the_first_question_reads_the_limit_and_the_config_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = scenario(tmp_path, questions=1)
    rows = paths["samples"].read_text("utf-8").splitlines()
    paths["samples"].write_text("\n".join(rows[:-1]) + "\n", "utf-8")  # the sampler still runs
    assert reader.main(["check", str(paths["samples"]), str(paths["log"])]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked == {
        "config_files": [CONFIG],
        "in_force": True,
        "limits_mib": [1024.0],
        "max_mib": paths["peak_mib"],
        "states": 3,
    }
    assert paths["removals"] == [0]


def test_a_cache_held_past_its_limit_or_a_reduced_limit_is_not_in_force() -> None:
    def row(**values: Any) -> dict[str, Any]:
        base = {"cache_limit_mib": 1024.0, "cache_mib": 500.0, "cache_limit_reduced_mib": None}
        base.update(removed_entries=0, removed_mib=0.0, skipped_saves=0)
        return base | values

    def part(*rows: dict[str, Any]) -> dict[str, Any]:
        return {"processes": [{"requests": list(rows)}]}

    assert reader.cache_states(part(row(), row(cache_mib=1024.0)))["in_force"] is True
    assert reader.cache_states(part(row(), row(cache_mib=1024.5)))["in_force"] is False
    assert reader.cache_states(part(row(cache_limit_reduced_mib=200.0)))["in_force"] is False
    assert reader.cache_states(part(row(cache_limit_mib=None, cache_mib=None)))["in_force"] is False
    assert reader.cache_states(part())["in_force"] is False


def foreign_python(at: float) -> tuple[list[Any], list[Any]]:
    """A Python process at 600 MiB in question 21, another at 300 MiB throughout."""
    procs = [[6002, 5.0, 300 * MIB, PYTHON_NAME]]
    if FIRST + EVERY * 20 < at < FIRST + EVERY * 21:
        procs.append([6001, 99.0, 600 * MIB, PYTHON_NAME])
    return procs, []


def framework_python(at: float) -> tuple[list[Any], list[Any]]:
    """The same 600-MiB Python in question 21, only among the largest: a path with a capital
    `Python` alone misses the supervisor's list."""
    if FIRST + EVERY * 20 < at < FIRST + EVERY * 21:
        return [], [[6001, 99.0, 600 * MIB, PYTHON_NAME]]
    return [], []


def virtual_machine(at: float) -> tuple[list[Any], list[Any]]:
    """A virtual machine among the largest processes in question 4."""
    if FIRST + EVERY * 3 < at < FIRST + EVERY * 4:
        return [], [[7001, 50.0, 3000 * MIB, VM_NAME]]
    return [], []


@pytest.mark.parametrize(
    ("extra", "second", "reason"),
    [
        (foreign_python, False, "a Python process other than the API at 512 MiB or more"),
        (framework_python, False, "a Python process other than the API at 512 MiB or more"),
        (virtual_machine, False, "a virtual machine among the five largest processes"),
        (None, True, "2 llama-server processes"),
    ],
)
def test_another_model_a_large_python_or_a_virtual_machine_disturbs_the_series(
    tmp_path: Path,
    drivers: None,
    extra: Callable[[float], tuple[list[Any], list[Any]]] | None,
    second: bool,
    reason: str,
) -> None:
    paths = scenario(tmp_path, resources_extra=extra, llama_servers=2 if second else 1)
    record = read(tmp_path, paths)
    disturbance = record["disturbance"]
    assert disturbance["disturbed"] is True and disturbance["reasons"] == [reason]
    assert record["gate"]["passed"] is True
    assert record["reading"]["swap"] == "NOT_EVIDENCE"
    assert record["reading"]["why"] == "the series was disturbed"
    python = [{"pid": 6001, "name": PYTHON_NAME, "peak_rss_mib": 600.0}]
    pythons = (foreign_python, framework_python)
    assert disturbance["foreign_python"] == (python if extra in pythons else [])
    assert disturbance["virtual_machines"] == ([VM_NAME] if extra is virtual_machine else [])
    assert disturbance["llama_server_pids"] == (2 if second else 1)
    footprints = [row["footprint_mib"] for row in record["questions"]]
    assert (record["series_pid"] is None) is second
    assert all(value is None for value in footprints) is second


def test_a_short_series_a_client_error_or_another_stand_fails_the_gate(
    tmp_path: Path, drivers: None
) -> None:
    folder = tmp_path / "short"
    folder.mkdir()
    short = read(folder, scenario(folder, questions=29))
    assert "launch: cases is not the series'" in short["gate"]["reasons"]
    assert "the questions read are not the thirty in their order" in short["gate"]["reasons"]
    assert short["reading"] == {
        "swap": "NOT_EVIDENCE",
        "why": "the gate failed",
        "reference_mib": 3000.0,
        "last_mib": None,
        "growth_mib": None,
    }
    paths = scenario(tmp_path)
    case = paths["run"] / "cases" / f"07-{reader.CASES[6]}.json"
    row = json.loads(case.read_text("utf-8"))
    row["client_error"] = "client cap 1200.0s reached"
    case.write_text(json.dumps(row), "utf-8")
    launch = json.loads((paths["run"] / "launch.json").read_text("utf-8"))
    launch.update(code_sha="0" * 40, runner_exit=1, status="failed")
    (paths["run"] / "launch.json").write_text(json.dumps(launch), "utf-8")
    (paths["run"].parent.parent / "live_api.py").write_text("# another driver\n", "utf-8")
    assert read(tmp_path, paths)["gate"]["reasons"] == [
        "launch: code_sha is not the series'",
        "launch: status is not the series'",
        "launch: runner_exit is not the series'",
        "the chat drivers are not V4's",
        "a question with a client error",
    ]


def test_a_request_without_its_cache_state_or_an_unmatched_call_fails_the_gate(
    tmp_path: Path, drivers: None
) -> None:
    record = read(tmp_path, scenario(tmp_path))
    part, rows = record["part"], record["questions"]
    part["processes"][0]["requests"][40]["cache_limit_mib"] = None
    part["run"]["joined"]["matched"] = 88
    rows[4]["samples"] = 0
    cap = reader.cache_states(part)
    assert cap["in_force"] is True and cap["states"] == 89
    assert reader.gate(part, cap, rows, API, 1)["reasons"] == [
        "a question with no sample inside it",
        "the model calls and the log's requests do not match one to one",
        "a request with no cache-state line",
    ]
    assert reader.gate(part, cap, rows, None, 1)["reasons"][0] == "launch: no API pid"


def test_a_sampler_that_saw_no_llama_server_fails_the_gate_and_disturbs_nothing(
    tmp_path: Path, drivers: None
) -> None:
    record = read(tmp_path, scenario(tmp_path, llama_servers=0))
    assert record["gate"]["reasons"] == ["the sampler saw no llama-server process in the questions"]
    assert record["disturbance"]["llama_server_pids"] == 0
    assert record["disturbance"]["disturbed"] is False
    assert record["series_pid"] is None
    assert record["reading"]["swap"] == "NOT_EVIDENCE"
    assert record["reading"]["why"] == "the gate failed"


def test_the_reader_refuses_an_existing_out_or_another_step0_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = scenario(tmp_path, questions=1)
    out = tmp_path / "step5.json"
    out.write_text("{}\n", "utf-8")
    argv = ["read", str(out), str(paths["log"]), str(paths["samples"]), str(paths["run"])]
    assert reader.main(argv) == 2
    assert out.read_text("utf-8") == "{}\n"
    assert reader.step0_home() == STEP0_TOOLS
    monkeypatch.setitem(reader.STEP0_SHA256, "step0_reader.py", "0" * 64)
    with pytest.raises(SystemExit, match="is not step 0's reader"):
        reader.main(["check", str(paths["samples"]), str(paths["log"])])
    monkeypatch.setattr(reader, "STEP0_HOMES", (tmp_path,))
    with pytest.raises(SystemExit, match="no step0_reader.py"):
        reader.step0_home()


def test_the_spec_names_the_tools_and_the_readings_as_they_stand() -> None:
    """Registered before the first request: the spec names the SHA-256 of the tool and of this
    test, and a later change shows here (a marked error fix updates the spec)."""
    spec = SPEC.read_text("utf-8")
    pattern = r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`"
    named = dict(re.findall(pattern, spec))
    assert sorted(named) == [
        "reports/stage4-step5/tools/step5_reader.py",
        "tests/test_stage4_step5_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    step0 = dict(re.findall(pattern, STEP0_SPEC.read_text("utf-8")))
    for name, digest in reader.STEP0_SHA256.items():
        assert step0[f"reports/stage4-step0/tools/{name}"] == digest, name
        assert hashlib.sha256((STEP0_TOOLS / name).read_bytes()).hexdigest() == digest, name
    cases = (ROOT / "evaluation" / "curated_cases_aircargo.jsonl").read_bytes()
    assert hashlib.sha256(cases).hexdigest().startswith("3737d694")
    ids = [json.loads(line)["case_id"] for line in cases.decode("utf-8").splitlines() if line]
    assert tuple(ids[:30]) == reader.CASES
    frozen = (reader.CAP_MIB, reader.REFERENCE, reader.LAST, reader.GROWTH_MIB)
    assert frozen == (1024.0, (6, 10), (26, 30), 512.0)
    assert reader.FOREIGN_RSS_MIB == 512.0
    assert reader.VM_NAMES == ("qemu", "limactl", "virtualization")
    flat = " ".join(spec.split())
    for phrase in (
        "registered before the first request",
        "`cache-ram = 1024`",
        "questions 6–10",
        "questions 26–30",
        "below 512 MiB",
        "512 MiB or more",
        "`qemu`, `limactl` or `virtualization`",
        "`4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`",
        "`0edcdef34593…`",
    ):
        assert phrase in flat, phrase
