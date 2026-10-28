"""Stage 4, step 0's sampler: the Mac's paging, swap and llama-server's memory every few seconds.

docs/specs/stage4-step0-diagnostics.md, registered with this tool before the first request;
PLAN.md stage 4, step 0. On the Mac beside one live chat run, any Python 3.11, the standard
library only:

  python -I step0_sampler.py OUT [--every SEC] [--max-sec SEC] [--log PATH]

Writes OUT, JSON lines: a "start" line, then every SEC seconds (default 5) a "sample" line,
then a "stop" line. A sample holds the UTC time; time.monotonic(), the clock of the chat
driver's stages.jsonl and cases (one clock for the whole Mac); the byte size of Ollama's serve
log, which holds llama-server's lines and which step0_reader.py cuts by these sizes; vm_stat's
page size and counters; sysctl's vm.swapusage in MiB and vm.loadavg; and for each process
whose executable is named llama-server its pid, its RSS (ps) and its footprint and compressed
size (top's MEM and CMPRS, the measure of PLAN.md's +312 MB a request). ps prints the pid, the
RSS and the executable's path; the path's last part is compared with the name and dropped. No
argument, command line or environment of any process is read or written. A command that fails
or prints a shape this tool does not know leaves its field null and a note.

Stops after --max-sec seconds (default 1800), when the stop file OUT.stop appears, or on
SIGTERM or SIGINT, with one last sample; refuses an existing OUT or stop file.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

SPEC = "docs/specs/stage4-step0-diagnostics.md"
SCHEMA = "stage4-step0-samples/v1"
LOG = "/Users/julia/gr2_bench/ollama_serve.log"
NAMES = ("llama-server",)
VM_STAT = ("/usr/bin/vm_stat",)
SWAP = ("/usr/sbin/sysctl", "-n", "vm.swapusage")
LOAD = ("/usr/sbin/sysctl", "-n", "vm.loadavg")
PS = ("/bin/ps", "-axo", "pid=,rss=,comm=")
TOP = ("/usr/bin/top", "-l", "1", "-stats", "pid,mem,cmprs")
# vm_stat's line names and the keys a sample keeps them under
VM_KEYS = {
    "Pages free": "free",
    "Pages active": "active",
    "Pages inactive": "inactive",
    "Pages speculative": "speculative",
    "Pages wired down": "wired",
    "Pages purgeable": "purgeable",
    "Pages stored in compressor": "compressor_stored",
    "Pages occupied by compressor": "compressor_occupied",
    "Pageins": "pageins",
    "Pageouts": "pageouts",
    "Swapins": "swapins",
    "Swapouts": "swapouts",
    "Compressions": "compressions",
    "Decompressions": "decompressions",
}
UNITS = {"B": 1 / 1048576, "K": 1 / 1024, "M": 1.0, "G": 1024.0, "T": 1048576.0}

Runner = Callable[[Sequence[str]], "str | None"]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run(args: Sequence[str]) -> str | None:
    """A command's standard output, or None when it fails; its standard error is dropped."""
    try:
        done = subprocess.run(list(args), capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def mib(text: str) -> float | None:
    """A size as top and sysctl print it (2977M, 0B, 5G, 512K, 730.50M, 2977M+) in MiB."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([BKMGT])[+-]?", text.strip())
    return round(float(match.group(1)) * UNITS[match.group(2)], 3) if match else None


def parse_vm_stat(text: str) -> tuple[int | None, dict[str, int]]:
    """vm_stat's page size and the counters VM_KEYS names; a missing line is left out."""
    size = re.search(r"page size of (\d+) bytes", text)
    counters = {}
    for name, value in re.findall(r'^"?([^":\n]+?)"?:\s+(\d+)\.?\s*$', text, re.M):
        key = VM_KEYS.get(name.strip())
        if key:
            counters[key] = int(value)
    return (int(size.group(1)) if size else None), counters


def parse_swapusage(text: str) -> dict[str, float] | None:
    """sysctl -n vm.swapusage ("total = 2048.00M  used = 1317.50M  free = 730.50M ...")."""
    found = {key: mib(value) for key, value in re.findall(r"\b(total|used|free) = (\S+)", text)}
    sizes = {key: value for key, value in found.items() if value is not None}
    return sizes if set(sizes) == {"total", "used", "free"} else None


def parse_loadavg(text: str) -> list[float] | None:
    """sysctl -n vm.loadavg ("{ 1.23 1.45 1.67 }"): the 1-, 5- and 15-minute loads."""
    values = re.findall(r"\d+(?:\.\d+)?", text)
    return [float(value) for value in values] if len(values) == 3 else None


def parse_ps(text: str, names: Sequence[str] = NAMES) -> list[tuple[int, int]]:
    """(pid, RSS in KiB) of each process whose executable's base name is in names. The
    executable's path is compared here and never returned."""
    found = []
    for line in text.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            if parts[2].strip().rsplit("/", 1)[-1] in names:
                found.append((int(parts[0]), int(parts[1])))
    return found


def parse_top(text: str) -> dict[int, tuple[float | None, float | None]]:
    """top -l 1 -stats pid,mem,cmprs: {pid: (MEM, CMPRS)} in MiB, read below its PID header."""
    rows: dict[int, tuple[float | None, float | None]] = {}
    below = False
    for line in text.splitlines():
        parts = line.split()
        if parts[:1] == ["PID"]:
            below = True
        elif below and len(parts) == 3 and parts[0].isdigit():
            rows[int(parts[0])] = (mib(parts[1]), mib(parts[2]))
    return rows


def sample(log: Path, runner: Runner = run, names: Sequence[str] = NAMES) -> dict[str, Any]:
    """One sample: the clocks and the log's size first, then the commands."""
    notes: list[str] = []
    row: dict[str, Any] = {"kind": "sample", "utc": utc(), "monotonic": round(time.monotonic(), 3)}
    try:
        row["log_bytes"] = log.stat().st_size
    except OSError:
        row["log_bytes"] = None
        notes.append("log: no size")
    out = runner(VM_STAT)
    page_size, counters = parse_vm_stat(out) if out is not None else (None, {})
    missing = sorted(set(VM_KEYS.values()) - set(counters))
    if out is None:
        notes.append("vm_stat: failed")
    elif page_size is None or missing:
        notes.append("vm_stat: no " + ", ".join(["page size"] * (page_size is None) + missing))
    row["page_size"] = page_size
    row["vm"] = counters or None
    out = runner(SWAP)
    row["swap_mib"] = parse_swapusage(out) if out is not None else None
    if row["swap_mib"] is None:
        notes.append("swapusage: " + ("failed" if out is None else "unknown shape"))
    out = runner(LOAD)
    row["loadavg"] = parse_loadavg(out) if out is not None else None
    if row["loadavg"] is None:
        notes.append("loadavg: " + ("failed" if out is None else "unknown shape"))
    out = runner(PS)
    procs = parse_ps(out, names) if out is not None else []
    if out is None:
        notes.append("ps: failed")
    elif not procs:
        notes.append("ps: no process named " + " or ".join(names))
    sizes: dict[int, tuple[float | None, float | None]] = {}
    if procs:
        out = runner([*TOP, *(arg for pid, _ in procs for arg in ("-pid", str(pid)))])
        sizes = parse_top(out) if out is not None else {}
        if out is None:
            notes.append("top: failed")
    row["procs"] = []
    for pid, rss in procs:
        mem, cmprs = sizes.get(pid, (None, None))
        if pid not in sizes:
            notes.append(f"top: no row for pid {pid}")
        row["procs"].append(
            {"pid": pid, "rss_mib": round(rss / 1024, 3), "mem_mib": mem, "cmprs_mib": cmprs}
        )
    row["notes"] = notes
    return row


def write(fh: IO[str], row: dict[str, Any]) -> None:
    fh.write(json.dumps(row, sort_keys=True) + "\n")
    fh.flush()


def stop_reason(signals: list[str], stop_file: Path, started: float, max_sec: float) -> str | None:
    if signals:
        return "signal " + signals[0]
    if stop_file.exists():
        return "stop file"
    if time.monotonic() - started >= max_sec:
        return "max-sec"
    return None


def main(argv: Sequence[str] | None = None, runner: Runner = run) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--every", type=float, default=5.0)
    parser.add_argument("--max-sec", type=float, default=1800.0)
    parser.add_argument("--log", default=LOG)
    args = parser.parse_args(argv)
    out, stop_file, log = Path(args.out), Path(args.out + ".stop"), Path(args.log)
    if out.exists() or stop_file.exists():
        print(f"refused: {out} or {stop_file} exists", file=sys.stderr)
        return 2
    if args.every <= 0 or args.max_sec <= 0:
        print("refused: --every and --max-sec must be positive", file=sys.stderr)
        return 2
    signals: list[str] = []

    def caught(number: int, frame: object) -> None:
        signals.append(signal.Signals(number).name)

    previous = {each: signal.signal(each, caught) for each in (signal.SIGTERM, signal.SIGINT)}
    started = time.monotonic()
    count = 0
    try:
        with out.open("w", encoding="utf-8", newline="\n") as fh:
            start: dict[str, Any] = {"kind": "start", "schema": SCHEMA, "spec": SPEC, "utc": utc()}
            start.update(monotonic=round(started, 3), every_sec=args.every, max_sec=args.max_sec)
            write(fh, {**start, "log": str(log), "names": list(NAMES)})
            while True:
                write(fh, sample(log, runner))
                count += 1
                reason = stop_reason(signals, stop_file, started, args.max_sec)
                # the next slot of the grid started + k * every that is still ahead
                due = started + args.every * (int((time.monotonic() - started) / args.every) + 1)
                while reason is None and time.monotonic() < due:
                    time.sleep(min(0.5, max(0.0, due - time.monotonic())))
                    reason = stop_reason(signals, stop_file, started, args.max_sec)
                if reason is not None:
                    break
            write(fh, sample(log, runner))
            stop = {"kind": "stop", "utc": utc(), "monotonic": round(time.monotonic(), 3)}
            write(fh, {**stop, "reason": reason, "samples": count + 1})
    finally:
        for each, handler in previous.items():
            if handler is not None:
                signal.signal(each, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
