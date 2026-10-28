"""reports/stage4-step0/tools: the sampler's parsers and loop, the reader's rows and readings.

docs/specs/stage4-step0-diagnostics.md. Synthetic fixtures only: every number, path and text in
them is made up. The log lines copy two sources of shapes. The request, timing and cache lines
copy what llama-server printed into Ollama's serve log on the Mac (read 2026-10-28). The load
lines, and the cache lines that log has not shown (a restored, obsolete or skipped prompt, the
other two evictions, a reduced limit, a slot selected by similarity), copy the format strings
of llama.cpp's sources. The vm_stat, sysctl, ps and top fixtures follow macOS 13's shapes; they
were not read on the Mac, and a shape the Mac prints otherwise shows as a sampler note.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import signal
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step0" / "tools"
SPEC = ROOT / "docs" / "specs" / "stage4-step0-diagnostics.md"


def tool(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sampler = tool("step0_sampler")
reader = tool("step0_reader")

VM_STAT = """\
Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                                5120.
Pages active:                            401234.
Pages inactive:                          398765.
Pages speculative:                         1234.
Pages throttled:                              0.
Pages wired down:                        345678.
Pages purgeable:                            321.
"Translation faults":                  98765432.
Pages copy-on-write:                    1234567.
Pages zero filled:                     45678901.
Pages reactivated:                      2345678.
Pages purged:                             12345.
File-backed pages:                        56789.
Anonymous pages:                         743210.
Pages stored in compressor:              567890.
Pages occupied by compressor:            123456.
Decompressions:                         3456789.
Compressions:                           4567890.
Pageins:                                5678901.
Pageouts:                                 67890.
Swapins:                                 789012.
Swapouts:                                890123.
"""
SWAP = "total = 2048.00M  used = 1317.50M  free = 730.50M  (encrypted)\n"
LOADAVG = "{ 1.23 1.45 1.67 }\n"
PS = """\
  101   20480 /sbin/launchd
 4242 3048576 /Applications/Ollama.app/Contents/Resources/llama-server
 4243    1024 /Users/someone/bin/llama-server-helper
 4244    2048 /Applications/Some Tools/not-llama-server
"""
TOP = """\
Processes: 456 total, 3 running, 453 sleeping, 2345 threads
2026/10/28 09:00:00
Load Avg: 1.23, 1.45, 1.67
CPU usage: 12.50% user, 10.00% sys, 77.50% idle
PhysMem: 7934M used (1914M wired, 1200M compressor), 257M unused.
VM: 30T vsize, 4096M framework vsize, 789012(0) swapins, 890123(0) swapouts.

PID   MEM    CMPRS
4242  2977M+ 1024M
"""


def fake(
    vm: str | None = VM_STAT,
    swap: str | None = SWAP,
    loadavg: str | None = LOADAVG,
    ps: str | None = PS,
    top: str | None = TOP,
) -> tuple[Callable[[Sequence[str]], str | None], list[list[str]]]:
    """A runner that answers each of the sampler's commands with its fixture."""
    calls: list[list[str]] = []

    def run(args: Sequence[str]) -> str | None:
        calls.append(list(args))
        name = Path(args[0]).name
        if name == "sysctl":
            return swap if args[-1] == "vm.swapusage" else loadavg
        return {"vm_stat": vm, "ps": ps, "top": top}[name]

    return run, calls


def test_the_sampler_parses_the_shapes_macos_prints() -> None:
    page_size, counters = sampler.parse_vm_stat(VM_STAT)
    assert page_size == 4096 and set(counters) == set(sampler.VM_KEYS.values())
    assert (counters["decompressions"], counters["pageins"], counters["wired"]) == (
        3456789,
        5678901,
        345678,
    )
    assert sampler.parse_swapusage(SWAP) == {"total": 2048.0, "used": 1317.5, "free": 730.5}
    assert sampler.parse_swapusage("total = 2048.00M  used = 1317.50M") is None
    assert sampler.parse_loadavg(LOADAVG) == [1.23, 1.45, 1.67]
    assert sampler.parse_loadavg("{ 1.23 1.45 }") is None
    two = PS + " 4245    4096 /Applications/Other App/llama-server\n"
    assert sampler.parse_ps(two) == [(4242, 3048576), (4245, 4096)]
    assert sampler.parse_top(TOP) == {4242: (2977.0, 1024.0)}
    sizes = ("2977M", "0B", "5G", "512K", "730.50M", "2977M+", "12M-", "n/a")
    assert [sampler.mib(size) for size in sizes] == [
        2977.0,
        0.0,
        5120.0,
        0.5,
        730.5,
        2977.0,
        12.0,
        None,
    ]


def test_a_sample_reads_each_command_and_keeps_no_path(tmp_path: Path) -> None:
    log = tmp_path / "serve.log"
    log.write_bytes(b"x" * 1234)
    run, calls = fake()
    row = sampler.sample(log, run)
    assert (row["kind"], row["log_bytes"], row["page_size"], row["notes"]) == (
        "sample",
        1234,
        4096,
        [],
    )
    assert row["vm"]["swapins"] == 789012 and row["swap_mib"]["used"] == 1317.5
    assert row["loadavg"] == [1.23, 1.45, 1.67]
    assert row["procs"] == [
        {"pid": 4242, "rss_mib": 2977.125, "mem_mib": 2977.0, "cmprs_mib": 1024.0}
    ]
    assert calls[-1] == [*sampler.TOP, "-pid", "4242"]
    assert "/" not in json.dumps(row)  # no executable's path, no command line


def test_a_failed_or_unknown_output_leaves_null_and_a_note(tmp_path: Path) -> None:
    missing = tmp_path / "missing.log"
    run, calls = fake(vm=None, swap="no such shape", loadavg=None, ps=None)
    row = sampler.sample(missing, run)
    assert [row[key] for key in ("log_bytes", "page_size", "vm", "swap_mib", "loadavg")] == [
        None
    ] * 5
    assert row["procs"] == [] and not any(args[0].endswith("top") for args in calls)
    assert row["notes"] == [
        "log: no size",
        "vm_stat: failed",
        "swapusage: unknown shape",
        "loadavg: failed",
        "ps: failed",
    ]
    lines = VM_STAT.splitlines()
    run, _ = fake(vm="\n".join(x for x in lines if not x.startswith(("Mach", "Swapins"))), ps="")
    row = sampler.sample(missing, run)
    assert row["page_size"] is None and "swapins" not in row["vm"] and row["procs"] == []
    assert row["notes"][1:] == [
        "vm_stat: no page size, swapins",
        "ps: no process named llama-server",
    ]
    run, _ = fake(top=None)
    row = sampler.sample(missing, run)
    assert row["procs"] == [{"pid": 4242, "rss_mib": 2977.125, "mem_mib": None, "cmprs_mib": None}]
    assert row["notes"][1:] == ["top: failed", "top: no row for pid 4242"]


def test_a_signal_the_stop_file_or_the_time_ends_the_loop(tmp_path: Path) -> None:
    stop, now = tmp_path / "s.jsonl.stop", time.monotonic()
    assert sampler.stop_reason([], stop, now, 60.0) is None
    assert sampler.stop_reason(["SIGTERM"], stop, now, 60.0) == "signal SIGTERM"
    assert sampler.stop_reason([], stop, now - 61.0, 60.0) == "max-sec"
    stop.touch()
    assert sampler.stop_reason([], stop, now, 60.0) == "stop file"


def test_the_loop_writes_a_start_samples_and_a_stop(tmp_path: Path) -> None:
    log = tmp_path / "serve.log"
    log.write_bytes(b"")
    handlers = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT))
    out = tmp_path / "a.jsonl"
    run, _ = fake()
    assert (
        sampler.main([str(out), "--every", "0.01", "--max-sec", "0.05", "--log", str(log)], run)
        == 0
    )
    start, *samples, stop = [json.loads(line) for line in out.read_text("utf-8").splitlines()]
    assert (start["kind"], start["schema"], start["spec"], start["every_sec"]) == (
        "start",
        sampler.SCHEMA,
        sampler.SPEC,
        0.01,
    )
    assert len(samples) >= 2 and {row["kind"] for row in samples} == {"sample"}
    assert (stop["kind"], stop["reason"], stop["samples"]) == ("stop", "max-sec", len(samples))
    assert b"\r" not in out.read_bytes()
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)) == handlers
    out = tmp_path / "b.jsonl"
    run, calls = fake()

    def stop_in_the_first_sample(args: Sequence[str]) -> str | None:
        if len(calls) >= 4:
            Path(f"{out}.stop").touch()
        return run(args)

    argv = [str(out), "--every", "0.01", "--max-sec", "60", "--log", str(log)]
    assert sampler.main(argv, stop_in_the_first_sample) == 0
    rows = [json.loads(line) for line in out.read_text("utf-8").splitlines()]
    assert (len(rows), rows[-1]["reason"], rows[-1]["samples"]) == (4, "stop file", 2)


def test_the_sampler_refuses_an_existing_file_or_a_bad_interval(tmp_path: Path) -> None:
    run, _ = fake()
    out = tmp_path / "a.jsonl"
    out.write_text("", "utf-8")
    assert sampler.main([str(out)], run) == 2
    other = tmp_path / "b.jsonl"
    Path(f"{other}.stop").touch()
    assert sampler.main([str(other)], run) == 2 and not other.exists()
    assert sampler.main([str(tmp_path / "c.jsonl"), "--every", "0"], run) == 2
    assert not (tmp_path / "c.jsonl").exists()


# The reader. A line of llama-server: "slot" or "srv", the function's name cut and right-aligned
# to 12 characters, then for a slot its id and task; as the Mac's log prints them.
def slot(task: int, function: str, text: str) -> str:
    return f"slot {function[:12]:>12}: id  0 | task {task} | {text}"


def srv(function: str, text: str) -> str:
    return f"srv  {function[:12]:>12}: {text}"


def gin(method: str = "POST", path: str = "/api/generate") -> str:
    return (
        f'[GIN] 2026/10/28 - 09:00:00 | 200 |        1m43s |       127.0.0.1 | {method:<8} "{path}"'
    )


def state_mib(tokens: int) -> float:
    """A prompt's saved state at 144 KiB a token, the f16 cache of the Mac's log."""
    return tokens * 144 / 1024


def feed(log: Any, lines: Sequence[str]) -> None:
    offset = 0
    for text in lines:
        log.line(offset, offset + len(text) + 1, text)
        offset += len(text) + 1
    log.finish()


STREAM, GENERATE = "ollama.generate_stream", "ollama.generate"
PID = 4242
BEFORE = (  # an earlier request's end, before the part's first sample
    slot(99, "release", "stop processing: n_tokens = 10, truncated = 0"),
    gin(),
)
OLLAMA = (  # Ollama's own line with a command line: never in a record
    'time=2026-10-28T09:00:02.300+03:00 level=INFO source=server.go:431 msg="starting runner" '
    'cmd="/fake/bin/llama-server --model /fake/blobs/sha256-0000 --api-key SECRET-0000"'
)
LOAD = (  # llama.cpp's sources; the Mac's llama-server tags two of them (LOAD_OLLAMA)
    "load_backend: loaded CPU backend from /fake/lib/ollama/libggml-cpu-haswell.so",
    "build: 7001 (abc1234) with Apple clang version 15.0.0 for x86_64-apple-darwin22.6.0",
    "system info: n_threads = 4, n_threads_batch = 4, total_threads = 4",
    "",
    "system_info: n_threads = 4 (n_threads_batch = 4) / 4 | CPU : SSE3 = 1 | AVX = 1 | "
    "AVX2 = 1 | F16C = 1 | FMA = 1 | BMI2 = 1 | LLAMAFILE = 1 | REPACK = 1 | ",
    "llama_model_loader: - kv   0:                               general.name str = Synthetic",
    "load_tensors: loading model tensors, this can take a while... (mmap = false)",
    "load_tensors:   CPU_REPACK model buffer size =  1404.00 MiB",
    "load_tensors:          CPU model buffer size =  1050.25 MiB",
    "llama_context:        CPU  output buffer size =     0.58 MiB",
    "llama_kv_cache:        CPU KV buffer size =   576.00 MiB",
    "llama_context:        CPU compute buffer size =   301.75 MiB",
    srv("init", "initializing slots, n_slots = 1"),
    slot(-1, "init", "new slot, n_ctx = 4096"),
    "main: model loaded",
)
# case, route, role, stage, task, prompt tokens, ms a processed token, generated tokens, ms
CALLS = (
    ("synthetic-q1", "human", "answer", STREAM, 0, 2300, 27.0, 200, 40000.0),
    ("synthetic-q1", "human", "self_eval", GENERATE, 3, 1000, 25.0, 20, 5000.0),
    ("synthetic-q2", "human", "answer", STREAM, 6, 2400, 27.0, 200, 40000.0),
    ("synthetic-q2", "human", "self_eval", GENERATE, 9, 1000, 25.0, 20, 5000.0),
    ("synthetic-q3", "auto", "answer", STREAM, 12, 2400, 27.0, 200, 40000.0),
    ("synthetic-q3", "auto", "self_eval", GENERATE, 15, 1000, 25.0, 20, 5000.0),
    ("synthetic-q3", "auto", "suggestions", GENERATE, 18, 600, 25.0, 60, 12000.0),
)


def preamble(n_tokens: int, saved: int, cache: list[int], lcps: list[int]) -> list[str]:
    """The cache's update before a task: the slot shares 20 tokens with the new prompt, its
    state is saved, each cached state's common prefix is checked, the state is printed."""
    f_sim = f"{20 / n_tokens:.3f}"
    lines = [
        slot(-1, "get_available_slot", f" - checking sim = {f_sim} (20/{n_tokens}) > 0.100"),
        slot(-1, "get_available_slot", "selected slot by LRU, t_last = 3903056266200"),
        srv("get_available_slot", "updating prompt cache"),
        srv(
            "prompt_save",
            f" - saving prompt with length {saved}, total state size = "
            f"{state_mib(saved):.3f} MiB (draft: 0.000 MiB)",
        ),
        srv(
            "load", f" - looking for better prompt, base f_keep = {20 / saved:.3f}, f_sim = {f_sim}"
        ),
    ]
    for length, lcp in zip(cache, lcps, strict=True):
        keep, sim = f"{lcp / length:.3f}", f"{lcp / n_tokens:.3f}"
        text = (
            f"   - prompt with length {length:7d}, lcp = {lcp:7d}, f_keep = {keep}, f_sim = {sim}"
        )
        lines.append(srv("load", text))
    total = sum(map(state_mib, cache))
    limits = "(limits: 8192.000 MiB, 4096 tokens, 58249 est)"
    lines.append(srv("update", f" - cache state: {len(cache)} prompts, {total:.3f} MiB {limits}"))
    for n, length in enumerate(cache):
        size = f"{state_mib(length):9.3f}"
        lines.append(
            srv(
                "update",
                f"   - prompt 0x6000035{n:05x}: {length:7d} tokens, checkpoints:  0, {size} MiB",
            )
        )
    lines.append(srv("get_available_slot", "prompt cache update took 950.00 ms"))
    lines.append(slot(-1, "launch_slot_", "sampler chain: logits -> ?penalties -> top-k -> dist"))
    return lines


def request(
    task: int,
    n_tokens: int,
    cached: int,
    per_token: float,
    generated: int,
    eval_ms: float,
    at: float,
) -> tuple[list[tuple[float, str]], float]:
    """A task's lines with the times they are written, from its first line at `at`."""
    tokens = n_tokens - cached
    prompt_ms = tokens * per_token
    timed = [
        (at, slot(task, "launch_slot_", "processing task, is_child = 0")),
        (
            at,
            slot(
                task,
                "operator()",
                f"new prompt, n_ctx_slot = 4096, n_keep = 4, task.n_tokens = {n_tokens}",
            ),
        ),
        (
            at,
            slot(task, "operator()", f"cached n_tokens = {cached}, memory_seq_rm [{cached}, end)"),
        ),
    ]
    if tokens > 512:  # one batch done: its progress line, then "cached n_tokens" again
        batch, done = at + 512 * per_token / 1000, cached + 512
        progress = (
            f"prompt processing, n_tokens =    512, progress = {512 / tokens:.2f}, "
            f"t = {512 * per_token / 1000:6.2f} s / {1000 / per_token:.2f} tokens per second"
        )
        timed.append((batch, slot(task, "print_timing", progress)))
        timed.append(
            (
                batch,
                slot(task, "operator()", f"cached n_tokens = {done}, memory_seq_rm [{done}, end)"),
            )
        )
    at += prompt_ms / 1000
    timed.append(
        (at, slot(task, "init_sampler", f"init sampler, took 0.80 ms, tokens: text = {n_tokens}"))
    )
    tps = generated / eval_ms * 1000
    if generated >= 100:
        rate = f"tg = {tps:6.2f} t/s, tg_3s = {tps:6.2f} t/s"
        timed.append((at + 100 / tps, slot(task, "print_timing", f"n_gen = {100:6d}, {rate}")))
    at += eval_ms / 1000
    summary = (
        f"prompt eval time = {prompt_ms:10.2f} ms / {tokens:5d} tokens "
        f"({per_token:8.2f} ms per token, {1000 / per_token:8.2f} tokens per second)",
        f"       eval time = {eval_ms:10.2f} ms / {generated:5d} tokens "
        f"({1000 / tps:8.2f} ms per token, {tps:8.2f} tokens per second)",
        f"      total time = {prompt_ms + eval_ms:10.2f} ms / {tokens + generated:5d} tokens",
        f"   graphs reused = {generated - 1:10d}",
    )
    timed += [(at, slot(task, "print_timing", text)) for text in summary]
    release = f"stop processing: n_tokens = {n_tokens + generated}, truncated = 0"
    timed += [(at, slot(task, "release", release)), (at, srv("update_slots", "all slots are idle"))]
    return timed, at


def sample_row(
    at: float, size: int, procs: list[dict[str, Any]] | None = None, swap: float = 1000.0, **vm: int
) -> dict[str, Any]:
    counters = dict.fromkeys(sampler.VM_KEYS.values(), 0) | vm
    return {
        "kind": "sample",
        "utc": "2026-10-28T06:00:00.000Z",
        "monotonic": at,
        "log_bytes": size,
        "page_size": 4096,
        "vm": counters,
        "swap_mib": {"total": 4096.0, "used": swap, "free": 4096.0 - swap},
        "loadavg": [0.5, 0.6, 0.7],
        "procs": procs or [],
        "notes": [] if procs else ["ps: no process named llama-server"],
    }


def scenario(tmp_path: Path) -> dict[str, Path]:
    """One part on disk: the log, the sampler's file, the run and its drivers, the corpus. A
    llama-server loads at 1003.4 s and serves seven calls of three cases. Samples every 5 s from
    1000 s to 1465 s; the footprint is 2,900 MiB and the cache; 6,400 pages a second (25 MiB) are
    decompressed throughout; swap grows 2 MiB a second."""
    timed = [(1002.3, OLLAMA), *((1003.4, line) for line in LOAD), (1010.5, gin())]
    timed.append((1011.0, gin("GET", "/api/ps")))
    stages: list[dict[str, Any]] = []
    cases: dict[str, dict[str, Any]] = {}
    states: list[tuple[float, float]] = []  # the time of each cache-state line, the cache
    cache: list[tuple[str, int]] = []
    held: tuple[str, int] | None = None
    end = 1013.3
    for n, (case_id, route, role, stage, task, tokens, per_token, generated, ms) in enumerate(
        CALLS, start=1
    ):
        start = end + 0.5
        if case_id not in cases:
            cases[case_id] = {"t0": end + 0.7, "route": route}
            start = end + 1.7
            for event, at in (("start", end + 0.9), ("end", end + 1.5)):
                stages.append(
                    {"stage": "hybrid.lanes", "event": event, "monotonic": at, "thread": 1}
                )
        at, cached = start + 0.5, 0
        if held is not None:
            cache.append(held)
            lcps = [140 if role == kind == "answer" else 20 for kind, _ in cache]
            timed += [(at, line) for line in preamble(tokens, held[1], [c for _, c in cache], lcps)]
            states.append((at, sum(state_mib(c) for _, c in cache)))
            at, cached = at + 1.0, 20
        lines, end = request(task, tokens, cached, per_token, generated, ms, at)
        timed += [*lines, (end + 0.1, gin())]
        info = {"prompt_file": f"{n:03d}-{stage[7:]}.txt", "prompt_chars": 4 * tokens}
        info.update(prompt_est_tokens=tokens, max_tokens=512 if stage == STREAM else 256)
        thread = 7001 if stage == STREAM else 7002
        stages.append(
            {"stage": stage, "event": "start", **info, "monotonic": start, "thread": thread}
        )
        done: dict[str, Any] = {"wall_sec": end + 0.3 - start, "output_chars": 4 * generated}
        if stage == STREAM:
            done.update(first_chunk_sec=1.0, chunks=generated, error=None)
        stages.append(
            {
                "stage": stage,
                "event": "end",
                **info,
                **done,
                "monotonic": end + 0.3,
                "thread": thread,
            }
        )
        held = (role, tokens + generated)
    unload = end + 3.3
    timed.append((unload + 0.1, gin()))
    assert [at for at, _ in timed] == sorted(at for at, _ in timed)
    before = "".join(line + "\n" for line in BEFORE)
    log = tmp_path / "ollama_serve.log"
    log.write_bytes((before + "".join(line + "\n" for _, line in timed)).encode())
    rows: list[dict[str, Any]] = [
        {"kind": "start", "schema": sampler.SCHEMA, "spec": sampler.SPEC, "monotonic": 1000.0},
    ]
    rows[0].update(every_sec=5.0, max_sec=1800.0, log=str(log), names=["llama-server"])
    for k in range(94):
        at = 1000.0 + 5 * k
        size = len(before) + sum(len(line) + 1 for written, line in timed if written <= at)
        held_mib = ([0.0] + [mib for written, mib in states if written <= at])[-1]
        proc = {
            "pid": PID,
            "rss_mib": 2500 + held_mib,
            "mem_mib": 2900 + held_mib,
            "cmprs_mib": 0.0,
        }
        procs = [proc] if 1003.4 < at < unload else []
        faults = {"decompressions": 6400 * 5 * k, "compressions": 3000 * 5 * k}
        rows.append(
            sample_row(at, size, procs, 1000.0 + 10 * k, pageins=50000, pageouts=7000, **faults)
        )
    rows.append({"kind": "stop", "monotonic": 1465.2, "reason": "stop file", "samples": 94})
    samples = tmp_path / "step0" / "s0-test.samples.jsonl"
    samples.parent.mkdir()
    samples.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
    chatlive = tmp_path / "chatlive"
    run = chatlive / "runs" / "s0-test"
    (run / "cases").mkdir(parents=True)
    for name in reader.DRIVERS:
        (chatlive / name).write_text("# a synthetic driver\n", "utf-8")
    launch: dict[str, Any] = {
        "label": "s0-test",
        "mode": "prod",
        "cases": list(cases),
        "client_cap_sec": "1020/1200",
    }
    launch.update(code_sha="0" * 40, model="synthetic:4b", status="complete", runner_exit=0)
    launch.update(api_pid=4321, env={"API_TOKEN": "SECRET-0001"})
    (run / "launch.json").write_text(json.dumps(launch), "utf-8")
    (run / "effective_settings.json").write_text(json.dumps({"OLLAMA_TIMEOUT": 3600}), "utf-8")
    (run / "stages.jsonl").write_text("".join(json.dumps(row) + "\n" for row in stages), "utf-8")
    for index, (case_id, case) in enumerate(cases.items(), start=1):
        result = {
            "at": 100.0,
            "type": "result",
            "route": case["route"],
            "answer": "SYNTHETIC ANSWER",
        }
        events = [{"at": 60.0, "type": "token", "text": "SYNTHETIC ANSWER"}, result]
        row: dict[str, Any] = {"case_id": case_id, "question": "SYNTHETIC QUESTION"}
        row["events"] = events
        row.update(answer="SYNTHETIC ANSWER", t0_monotonic=case["t0"], tokens=200, total_sec=100.0)
        row.update(drain_sec=0.2)
        (run / "cases" / f"{index:02d}-{case_id}.json").write_text(json.dumps(row), "utf-8")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for name in ("corpus.manifest.json", "chunks-report.json"):
        (corpus / name).write_bytes(b"{}\n")
    return {"log": log, "samples": samples, "run": run, "corpus": corpus}


def test_a_part_reads_into_rows_and_readings_with_no_text(tmp_path: Path) -> None:
    paths = scenario(tmp_path)
    out = tmp_path / "s0-test.step0.json"
    argv = [str(out), str(paths["log"]), "--part", str(paths["samples"]), str(paths["run"])]
    assert reader.main([*argv, "--corpus", str(paths["corpus"])]) == 0
    text = out.read_text("utf-8")
    for leak in ("SECRET", "SYNTHETIC", "/fake/", "0x6000035", "cmd=", "eval time", "t_last"):
        assert leak not in text, leak
    record = json.loads(text)
    assert (record["schema"], record["spec"]) == (reader.SCHEMA, reader.SPEC)
    assert record["corpus"]["sha256"]["index/index-receipt.json"] is None
    assert record["corpus"]["sha256"]["chunks-report.json"] == hashlib.sha256(b"{}\n").hexdigest()
    [part] = record["parts"]
    assert part["notes"] == [] and (part["pid"], part["page_size"]) == (PID, 4096)
    assert part["samples"]["sample_notes"] == {"ps: no process named llama-server": 3}
    assert part["gin"] == {"GET /api/ps 200": 1, "POST /api/generate 200": 9}
    assert part["slice"]["start"] == sum(len(line) + 1 for line in BEFORE)
    [process] = part["processes"]
    load = process["load"]
    assert (load["build"], load["commit"], load["load_mode"], load["notes"]) == (
        7001,
        "abc1234",
        "mmap = false",
        [],
    )
    assert load["backends"] == [{"name": "CPU", "file": "libggml-cpu-haswell.so"}]
    assert load["system_info"]["n_threads"] == 4 and load["system_info"]["flags"]["REPACK"] == "1"
    assert [(b["at"], b["type"], b["kind"], b["mib"]) for b in load["buffers"]] == [
        ("load_tensors", "CPU_REPACK", "model", 1404.0),
        ("load_tensors", "CPU", "model", 1050.25),
        ("llama_context", "CPU", "output", 0.58),
        ("llama_kv_cache", "CPU", "KV", 576.0),
        ("llama_context", "CPU", "compute", 301.75),
    ]
    rows = {row["task"]: row for row in process["requests"]}
    assert [(task, rows[task]["role"], rows[task]["complete"]) for task in rows] == [
        (call[4], call[2], True) for call in CALLS
    ]
    assert all(row["notes"] == [] for row in rows.values())
    first, answer = rows[0], rows[6]
    assert (first["cached_tokens"], first["sim_lcp"], first["cache_mib"]) == (0, None, None)
    assert (answer["n_tokens"], answer["cached_tokens"], answer["prompt_tokens"]) == (
        2400,
        20,
        2380,
    )
    assert (answer["prompt_ms"], answer["prompt_ms_per_token"]) == (64260.0, 27.0)
    assert (answer["eval_tokens"], answer["eval_ms"], answer["eval_tps"]) == (200, 40000.0, 5.0)
    assert (answer["total_ms"], answer["total_tokens"], answer["release_n_tokens"]) == (
        104260.0,
        2580,
        2600,
    )
    assert (answer["sim_f"], answer["sim_lcp"], answer["sim_n"], answer["selected_by"]) == (
        0.008,
        20,
        2400,
        "LRU",
    )
    assert answer["cache_updated"] and not answer["restored"] and answer["removed_entries"] == 0
    assert (answer["saved_tokens"], answer["saved_mib"]) == (1020, 143.438)
    assert (answer["candidates"], answer["best_candidate_lcp"], answer["cache_update_ms"]) == (
        2,
        140,
        950.0,
    )
    assert [answer[key] for key in ("cache_prompts", "cache_mib", "cache_limit_mib")] == [
        2,
        495.0,
        8192.0,
    ]
    assert (answer["cache_limit_tokens"], answer["cache_est"], answer["case_id"]) == (
        4096,
        58249,
        "synthetic-q2",
    )
    assert answer["mem_after_state_mib"] == 3395.0
    window = first["request_window"]  # from the sample at 1015 s to the one at 1120 s
    assert (window["samples"], window["sec"], window["decompressions"], window["pageins"]) == (
        22,
        105.0,
        672000,
        0,
    )
    assert (window["faulted_mib"], window["swap_used_mib"], window["mem_peak_mib"]) == (
        2625.0,
        210.0,
        3251.5625,
    )
    generation = first["generation_window"]
    assert [generation[key] for key in ("from", "to", "samples", "sec")] == [
        1080.0,
        1115.0,
        8,
        35.0,
    ]
    assert (generation["faulted_mib"], generation["faulted_mib_per_token"]) == (875.0, 5.0)
    assert [first["prompt_window"][key] for key in ("from", "to", "samples")] == [
        1017.9,
        1075.0,
        12,
    ]
    assert rows[3]["generation_window"] == {
        "samples": 1,
        "from": 1145.0,
        "to": 1145.0,
        "faulted_mib_per_token": None,
    }
    run = part["run"]
    assert run["joined"] == {"calls": 7, "requests": 7, "matched": 7}
    assert run["launch"] == {
        "label": "s0-test",
        "mode": "prod",
        "cases": ["synthetic-q1", "synthetic-q2", "synthetic-q3"],
        "client_cap_sec": "1020/1200",
        "code_sha": "0" * 40,
        "model": "synthetic:4b",
        "status": "complete",
        "runner_exit": 0,
    }
    assert [(case["case_id"], case["route"]) for case in run["cases"]] == [
        ("synthetic-q1", "human"),
        ("synthetic-q2", "human"),
        ("synthetic-q3", "auto"),
    ]
    assert set(run["drivers_sha256"]) == set(reader.DRIVERS)
    assert (
        record["tools_sha256"]["step0_reader.py"]
        == hashlib.sha256((TOOLS / "step0_reader.py").read_bytes()).hexdigest()
    )
    readings = record["readings"]
    q1 = readings["q1_cache_growth"]
    assert (q1["answer"], q1["requests_spanned"], q1["ratio"]) == ("yes", 5, 1.0)
    assert q1["growth_per_request_mib"] == pytest.approx(232.313, abs=0.001)
    assert q1["saved_mib"] == [351.562, 143.438, 365.625, 143.438, 365.625, 143.438]
    q2 = readings["q2_memory_wait"]
    assert (q2["answer"], q2["windows"], q2["median_faulted_mib_per_token"]) == ("no", 4, 5.0)
    q3 = readings["q3_prefix_reuse"]
    assert (q3["answer"], q3["lever"], q3["median_cached_tokens"], q3["median_saving_ms"]) == (
        "no",
        "no",
        20.0,
        3240.0,
    )
    assert [(a["task"], a["case_id"], a["best_prefix"]) for a in q3["answers"]] == [
        (6, "synthetic-q2", 140),
        (12, "synthetic-q3", 140),
    ]
    assert q3["self_eval"] == [
        {"task": t, "cached_tokens": 20, "best_prefix": 20} for t in (3, 9, 15)
    ]
    repack = readings["repack"]
    assert (repack["answer"], repack["model_buffers"], repack["system_info_repack"]) == (
        "on",
        ["CPU", "CPU_REPACK"],
        "1",
    )
    assert (repack["backends"], repack["n_threads"], repack["build"]) == (
        [["CPU", "libggml-cpu-haswell.so"]],
        4,
        7001,
    )
    assert reader.main(argv) == 2  # an existing record is never overwritten


SOURCE_ONLY = (  # llama.cpp's format strings for cache events the Mac's log has not shown
    slot(
        -1,
        "get_available_slot",
        "selected slot by LCP similarity, f_sim_best = 0.950 (> 0.100 thold), f_keep = 0.900",
    ),
    srv("get_available_slot", "updating prompt cache"),
    srv("alloc", " - removing obsolete cached prompt with length 2000"),
    srv(
        "alloc", " - prompt state size 9000.000 MiB exceeds cache size limit 8192.000 MiB, skipping"
    ),
    srv("alloc", " - cache size limit reduced to 4096.000 MiB"),
    srv("load", " - found better prompt with f_keep = 0.900, f_sim = 0.950"),
    srv("update", " - cache size limit reached, removing oldest entry (size = 351.562 MiB)"),
    srv(
        "update",
        " - cache token limit (4096, est: 58249) reached, "
        "removing oldest entry (size = 143.438 MiB)",
    ),
)


def test_the_sources_cache_lines_fill_their_fields() -> None:
    log = reader.Reader()
    prompt = "new prompt, n_ctx_slot = 4096, n_keep = 4, task.n_tokens = 2000"
    task = (
        slot(7, "operator()", prompt),
        slot(7, "operator()", "cached n_tokens = 1900, memory_seq_rm [1900, end)"),
        slot(7, "release", "stop processing: n_tokens = 2100, truncated = 0"),
    )
    feed(log, [*SOURCE_ONLY, *task])
    [row] = log.processes[0]["requests"]
    assert (row["selected_by"], row["cache_updated"], row["restored"], row["cached_tokens"]) == (
        "LCP",
        True,
        True,
        1900,
    )
    assert (row["obsolete_entries"], row["skipped_saves"], row["removed_entries"]) == (1, 1, 2)
    assert (row["removed_mib"], row["cache_limit_reduced_mib"]) == (495.0, 4096.0)
    assert row["notes"] == [
        "no prompt eval time line",
        "no eval time line",
        "no total time line",
        "a cache update with no cache-state line",
    ]


def test_requests_cut_by_the_slice_and_new_processes_are_kept_apart() -> None:
    log = reader.Reader()
    begun = slot(41, "operator()", "new prompt, n_ctx_slot = 4096, n_keep = 4, task.n_tokens = 99")
    feed(
        log,
        [
            slot(40, "release", "stop processing: n_tokens = 105, truncated = 0"),
            begun,
            slot(41, "release", "stop processing: n_tokens = 110, truncated = 0"),
            begun.replace("task 41", "task 2"),
            LOAD[0],
            begun.replace("task 41", "task 0"),
        ],
    )
    first, second, third = log.processes
    assert [row["task"] for row in first["requests"]] == [40, 41]
    assert first["requests"][0]["complete"] is False and first["requests"][1]["complete"] is True
    assert "no new-prompt line: the request began before the slice" in first["requests"][0]["notes"]
    assert first["load"]["notes"] == ["no load lines in the slice"]
    assert second["notes"] == ["task ids went down with no load line: a new process"]
    assert third["load"]["backends"] == [{"name": "CPU", "file": "libggml-cpu-haswell.so"}]
    assert "no release line: the request ended after the slice" in third["requests"][0]["notes"]
    assert (
        "no build line" in third["load"]["notes"]
        and "no model buffer line" in third["load"]["notes"]
    )


LOAD_OLLAMA = (  # the shapes of Ollama 0.33.2's llama-server in run 1's log, 2026-10-28
    "cmn  common_param: common_params_print_info: build 1 (abc1234) with AppleClang 21.0.0 for "
    "Darwin x86_64",
    "cmn  common_param: common_params_print_info: verbosity = 4 (adjust with the `-lv N` CLI arg)",
    "cmn  common_param: system_info: n_threads = 4 (n_threads_batch = 4) / 4 | CPU : SSE3 = 1 | "
    "AVX2 = 1 | FMA = 1 | REPACK = 1 | ",
    srv("load_model", "loading model '/fake/blobs/sha256-0000'"),
    "cmn  common_init_: fitting params to device memory ...",
    "load_tensors: loading model tensors, this can take a while... (load_mode = none)",
    "load_tensors:          CPU model buffer size =   692.63 MiB",
    "load_tensors:   CPU_REPACK model buffer size =  1683.28 MiB",
)


def test_the_tagged_build_and_system_info_lines_are_read_and_start_a_process() -> None:
    log = reader.Reader()
    begun = slot(0, "operator()", "new prompt, n_ctx_slot = 4096, n_keep = 4, task.n_tokens = 99")
    feed(log, [*LOAD_OLLAMA, begun, *LOAD_OLLAMA])
    first, second = log.processes
    assert [row["task"] for row in first["requests"]] == [0] and second["requests"] == []
    for process in (first, second):
        load = process["load"]
        assert (load["lines"], load["build"], load["commit"], load["load_mode"]) == (
            5,
            1,
            "abc1234",
            "load_mode = none",
        )
        assert load["system_info"] == {
            "n_threads": 4,
            "n_threads_batch": 4,
            "hw_threads": 4,
            "flags": {"SSE3": "1", "AVX2": "1", "FMA": "1", "REPACK": "1"},
        }
        assert load["backends"] == [] and load["notes"] == ["no load_backend line"]
    repack = reader.repack([first])
    assert (repack["answer"], repack["system_info_repack"], repack["n_threads"]) == ("on", "1", 4)
    assert repack["build"] == 1 and repack["backends"] is None


def test_a_slice_drops_the_lines_it_cuts(tmp_path: Path) -> None:
    log = tmp_path / "serve.log"
    log.write_bytes(b"first line\nsecond line\nthird line\n")
    notes: list[str] = []
    lines, cut = reader.read_slice(log, 3, 26, notes)
    assert lines == [(11, 23, "second line")] and (cut["bytes"], cut["lines"]) == (23, 1)
    assert notes == [
        "the slice ends inside a line: it is left out",
        "the slice starts inside a line: it is left out",
    ]
    notes = []
    assert reader.read_slice(log, 11, 23, notes)[0] == [(11, 23, "second line")] and notes == []


def test_two_pids_or_a_shrinking_log_leave_null() -> None:
    procs = [{"pid": pid, "rss_mib": 1.0, "mem_mib": 2.0, "cmprs_mib": 0.0} for pid in (1, 2)]
    notes: list[str] = []
    two = reader.Samples([sample_row(1000.0 + 5 * k, 100 * k, procs) for k in range(3)], notes)
    assert two.pid is None and two.stats(0, 2)["mem_peak_mib"] is None and two.mem(1) is None
    assert notes == ["2 llama-server pids in the samples: no footprint is read"]
    notes = []
    rows = [sample_row(1000.0, 500), sample_row(1005.0, 400), {"kind": "sample", "log_bytes": None}]
    down = reader.Samples(rows, notes)
    assert down.before(450) is None and down.after(450) is None
    assert notes == [
        "1 samples with no log size: left out",
        "the log's size or the clock went down: no windows",
    ]


def test_roles_follow_the_order_of_a_cases_calls() -> None:
    cases = [
        {"case_id": "c1", "t0_monotonic": 10.0, "route": "auto"},
        {"case_id": "c2", "t0_monotonic": 50.0, "route": "human"},
    ]
    # one call before any case, then five in c1 (one before its stream), then c2's stream
    starts = [(GENERATE, 5.0), (GENERATE, 11.0), (STREAM, 12.0), (GENERATE, 20.0)]
    starts += [(GENERATE, 30.0), (GENERATE, 40.0), (STREAM, 51.0)]
    calls = [
        {"stage": stage, "start": at, "end": at + 1.0, "index": n}
        for n, (stage, at) in enumerate(starts)
    ]
    notes: list[str] = []
    reader.assign_roles(calls, cases, notes)
    assert [(c["case_id"], c["role"]) for c in calls] == [
        (None, "other"),
        ("c1", "other"),
        ("c1", "answer"),
        ("c1", "self_eval"),
        ("c1", "suggestions"),
        ("c1", "other"),
        ("c2", "answer"),
    ]
    assert notes == [
        "run: case c1: 5 model calls, route auto",
        "run: case c2: 1 model calls, route human",
    ]


def test_a_runs_files_keep_ids_and_named_keys_only(tmp_path: Path) -> None:
    run = tmp_path / "chatlive" / "runs" / "s0-x"
    (run / "cases").mkdir(parents=True)
    warmup = "warmup:Is this a SYNTHETIC question?"  # a warmup's id carries its question
    launch = {"label": "s0-x", "cases": ["synthetic-q1", warmup], "env": {"KEY": "SECRET-2"}}
    (run / "launch.json").write_text(json.dumps(launch), "utf-8")
    case = {"case_id": warmup, "question": warmup[7:], "t0_monotonic": 5.0, "events": []}
    (run / "cases" / "01-warmup-1.json").write_text(json.dumps(case), "utf-8")
    notes: list[str] = []
    kept = reader.read_run(run, notes)
    assert kept["launch"] == {"label": "s0-x", "cases": ["synthetic-q1", "<not an id>"]}
    assert [(c["case_id"], c["t0_monotonic"], c["route"]) for c in kept["cases"]] == [
        ("<not an id>", 5.0, None)
    ]
    assert "SECRET" not in json.dumps(kept) and "SYNTHETIC" not in json.dumps(kept)
    assert notes == ["run: no stages.jsonl"]
    assert kept["sha256"]["stages.jsonl"] is None and kept["calls"] == []
    notes = []
    assert reader.read_run(tmp_path / "chatlive" / "runs" / "none", notes)["cases"] == []
    assert notes == ["run: no readable launch.json", "run: no case files", "run: no stages.jsonl"]


def a_row(**values: Any) -> dict[str, Any]:
    """A request's row as read_part leaves it, with the given fields."""
    base = {**reader.PREAMBLE_ROW, **reader.TASK_ROW, "complete": True, "notes": []}
    base.update(role=None, case_id=None, eval_tps=None, prompt_ms_per_token=None)
    return {**base, "generation_window": None, "mem_after_state_mib": None, **values}


def test_q1_needs_the_cache_to_grow_and_the_footprint_to_follow() -> None:
    def process(cache: Sequence[float], mem: Sequence[float | None]) -> list[dict[str, Any]]:
        states = [
            a_row(task=k + 1, cache_mib=c, cache_prompts=k + 1, mem_after_state_mib=m)
            for k, (c, m) in enumerate(zip(cache, mem, strict=True))
        ]
        return [{"requests": [a_row(task=0), *states]}]

    grows = [300.0, 600.0, 900.0, 1200.0]
    yes = reader.q1(process(grows, [3300.0, 3600.0, 3900.0, 4200.0]))
    assert (yes["answer"], yes["growth_per_request_mib"], yes["ratio"]) == ("yes", 300.0, 1.0)
    other = reader.q1(process(grows, [3300.0, 3300.0, 3300.0, 4800.0]))
    assert (other["answer"], other["accounts"], other["ratio"]) == ("no", False, 1.667)
    flat = reader.q1(process([300.0, 320.0, 340.0, 360.0], [3300.0] * 4))
    assert (flat["answer"], flat["grows"]) == ("no", False)
    short = reader.q1(process([300.0, 600.0], [3300.0, 3600.0]))
    assert (short["answer"], short["grows"]) == (reader.NOT_EVIDENCE, None)
    unread = reader.q1(process(grows, [None] * 4))
    assert (unread["answer"], unread["ratio"]) == (reader.NOT_EVIDENCE, None)


def test_q2_reads_the_pages_faulted_back_per_generated_token() -> None:
    def process(*values: float | None) -> list[dict[str, Any]]:
        window = {"samples": 3, "sec": 10.0, "faulted_mib": 1.0}
        windows = [{**window, "faulted_mib_per_token": value} for value in values]
        return [{"requests": [a_row(task=k, generation_window=w) for k, w in enumerate(windows)]}]

    assert reader.q2(process(30.0, 40.0))["answer"] == "yes"
    low = reader.q2(process(1.0, 2.0, None))
    assert (low["answer"], low["windows"], low["median_faulted_mib_per_token"]) == ("no", 2, 1.5)
    assert reader.q2(process(30.0, None))["answer"] == reader.NOT_EVIDENCE
    assert reader.q2([{"requests": [a_row(task=0, complete=False)]}])["requests"] == []


def test_q3_reads_the_reused_prefix_and_what_the_best_one_would_save() -> None:
    def process(*later: tuple[int | None, int, int]) -> list[dict[str, Any]]:
        """The first answer, later answers (cached, the slot's prefix, the best cached one)
        at 27 ms a prompt token, and a self-evaluation."""
        answer = {"role": "answer", "prompt_ms_per_token": 27.0}
        first = a_row(task=0, cached_tokens=0, **answer)
        rest = [
            a_row(task=k + 1, cached_tokens=c, sim_lcp=s, best_candidate_lcp=b, **answer)
            for k, (c, s, b) in enumerate(later)
        ]
        evaluation = a_row(task=9, role="self_eval", cached_tokens=900, sim_lcp=900)
        return [{"requests": [first, *rest, evaluation]}]

    lever = reader.q3(process((130, 130, 2000), (140, 140, 1800)))
    assert (lever["answer"], lever["lever"]) == ("yes", "yes")
    assert [answer["saving_ms"] for answer in lever["answers"]] == [50490.0, 44820.0]
    plain = reader.q3(process((20, 20, 140), (45, 45, 48)))
    assert (plain["answer"], plain["lever"], plain["median_saving_ms"]) == ("no", "no", 1660.5)
    assert plain["self_eval"] == [{"task": 9, "cached_tokens": 900, "best_prefix": 900}]
    one = reader.q3(process((20, 20, 140), (None, 45, 48)))
    assert (one["answer"], one["lever"], one["unreadable_answers"]) == (
        reader.NOT_EVIDENCE,
        reader.NOT_EVIDENCE,
        1,
    )


def test_repack_is_read_from_the_model_buffers_only() -> None:
    def processes(*types: str) -> list[dict[str, Any]]:
        buffers = [{"at": "load_tensors", "type": t, "kind": "model", "mib": 1.0} for t in types]
        load = dict.fromkeys(("system_info", "load_mode", "build"))
        return [{"load": {**load, "buffers": buffers, "backends": []}}]

    assert reader.repack(processes("CPU_REPACK", "CPU"))["answer"] == "on"
    assert reader.repack(processes("CPU_AARCH64", "CPU"))["answer"] == "on"
    assert reader.repack(processes("CPU"))["answer"] == "off"
    assert reader.repack(processes("CPU_Mapped"))["answer"] == "off"
    assert reader.repack(processes("AMX", "CPU"))["answer"] == reader.NOT_EVIDENCE
    assert reader.repack(processes())["answer"] == reader.NOT_EVIDENCE


def test_the_reader_refuses_a_bad_command_line_or_no_log_size(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    bad = (["--start", "5"], ["--part", "t", "--start", "1", "--end", "2"], ["r", "x"])
    for extra in bad:
        with pytest.raises(SystemExit):
            reader.main([str(out), "log", "--part", "s", *extra])
    samples = tmp_path / "s.jsonl"
    unsized = {"kind": "sample", "monotonic": 1.0, "log_bytes": None}
    samples.write_text(json.dumps(unsized) + "\n", "utf-8")
    with pytest.raises(SystemExit, match="no sample with a log size"):
        reader.main([str(out), str(tmp_path / "log"), "--part", str(samples)])
    out.write_text("{}\n", "utf-8")
    assert reader.main([str(out), "log", "--part", str(samples)]) == 2


def test_the_spec_names_the_tools_and_the_readings_as_they_stand() -> None:
    """Registered before the first request: the spec names the SHA-256 of each tool and of this
    test, and a later change shows here (a marked error fix updates the spec)."""
    spec = SPEC.read_text("utf-8")
    assert "registered before the first request" in spec
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage4-step0/tools/step0_reader.py",
        "reports/stage4-step0/tools/step0_sampler.py",
        "tests/test_stage4_step0_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    q1 = (reader.Q1_MIN_GROWTH_MIB, reader.Q1_MIN_REQUESTS, reader.Q1_RATIO)
    q2 = (reader.Q2_MIN_FAULTED_MIB, reader.Q2_MIN_WINDOWS)
    q3 = (reader.Q3_MIN_REUSED, reader.Q3_LEVER_MS, reader.Q3_MIN_ANSWERS)
    assert (q1, q2, q3) == ((200.0, 3, (0.75, 1.25)), (25.0, 2), (100, 4000.0, 2))
    phrases = (
        "200 MiB a request",
        "at least three requests",
        "0.75 to 1.25",
        "25 MiB a generated token",
        "at least two generation windows",
        "100 tokens",
        "4,000 ms",
        "at least two later answers",
    )
    for phrase in phrases:
        assert phrase in spec, phrase
