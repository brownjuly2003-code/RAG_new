"""Foreground, file-resumable laptop driver. No request/reply text on stdout.

Exits: 0 complete, 1 refusal, 2 stopped, 3 budget, 4 receipt commit, 5 unavailable,
6 stop detected but Mac STOP not written (touch it by hand).
"""

import argparse
import contextlib
import io
import math
import re
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import v6_judge as grading
import v6_record as reading
from v6_common import (
    KEYS,
    STANDS,
    outside,
    plan_name,
    protocol,
    public,
    read,
    require,
    rows,
    sha,
    write,
)


def touch_stop(target):
    """One explicit Mac STOP target, or a mounted/local path; never a shell fragment."""
    remote = re.fullmatch(r"([A-Za-z0-9_.-]+):(/[A-Za-z0-9_./-]+/STOP)", target)
    if remote:
        subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=20",
                remote[1],
                "touch",
                remote[2],
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    else:
        path = Path(target)
        require(path.name == "STOP", "STOP target required")
        path.touch(exist_ok=True)


def journal_rows(folder):
    path = folder / "verdicts.jsonl"
    return rows(path) if path.exists() else []


def pending(folder):
    from scripts import chat_answer_judge as judge

    plan = read(folder / "plan.json")
    items = judge.check_plan(plan)
    journal = journal_rows(folder)
    done, replies = judge._vouched(plan, journal), judge._replies(items, journal)
    return any(
        "message" in item
        and item["item_id"] not in done
        and replies[item["item_id"]] < judge.REPLIES
        for item in plan["items"]
    )


def retry_state(folder):
    """Reconcile a kill after journal append but before the small state-file write."""
    path = folder / "retry.json"
    held = (
        read(path)
        if path.exists()
        else {"consecutive_failures": 0, "journal_rows": 0, "retry_at": 0}
    )
    journal = journal_rows(folder)
    for row in journal[held["journal_rows"] :]:
        if row["status"] == "unavailable":
            held["consecutive_failures"] += 1
            held["retry_at"] = time.time() + 300
        else:
            held["consecutive_failures"] = 0
            held["retry_at"] = 0
    held["journal_rows"] = len(journal)
    return held


def registered_keys(records):
    keys = []
    for key in KEYS:
        receipt = records / STANDS[key] / f"plans-{key}.json"
        if receipt.exists():
            try:
                protocol.committed(receipt)
            except SystemExit:
                continue
            keys.append(key)
    return keys


def run(args, *, sender=None, clock=time.monotonic, sleep=time.sleep):
    require(math.isfinite(args.budget) and args.budget > 0, "positive finite budget required")
    started = clock()
    private, runs = outside(args.private), outside(args.runs)
    out = args.records / STANDS[args.key]
    receipt = out / f"plans-{args.key}.json"
    work = private / args.key / "judge"
    location = private / args.key / "run-location.json"
    if location.exists():
        require(Path(read(location)["runs"]) == runs, "key run location changed")
    else:
        write(location, {"runs": str(runs)})
    new_plan = not receipt.exists() or (
        not work.exists() and work.with_name(work.name + ".partial").exists()
    )
    if new_plan:
        require(args.config is not None, "new plan needs config")
        grading.freeze(args.key, read(args.config)[args.key], runs, work, receipt, args.spec)
    summary_name = f"v6-{args.key}.json"
    if not (out / summary_name).exists():
        require(
            sha(runs / summary_name) == read(receipt)["answer_files"][summary_name],
            "replay changed since receipt",
        )
        public(out / summary_name, read(runs / summary_name))
    if new_plan:
        return 4, f"receipt waiting for commit: {receipt}"
    try:
        protocol.committed(receipt)
    except SystemExit:
        return 4, f"receipt waiting for commit: {receipt}"
    pin = grading.admitted(args.key, work, receipt, args.spec)
    metrics = [m for m in ("m1", "bridge", "m2") if m in pin["plans"]]

    def stopped():
        try:
            touch_stop(args.mac_stop)
        except (Exception, SystemExit) as exc:
            log = log_exception(args, exc)
            return (
                6,
                f"stop detected, Mac STOP not written: {args.mac_stop}; touch it by hand"
                + (f"; log: {log}" if log is not None else ""),
            )
        return 2, "stopped: NOT_EVIDENCE or harm"

    if any((work / m / "NOT_EVIDENCE.json").exists() for m in metrics):
        return stopped()
    # Preserve an already detected harm across a new foreground invocation.
    for path in sorted(args.records.glob("*/reading-*.json")):
        if read(path)["decision"]["harm"]:
            return stopped()
    for metric in metrics:
        folder = work / metric
        held = retry_state(folder)
        if getattr(args, "resume_unavailable", False) and held["consecutive_failures"] >= 7:
            held = {"consecutive_failures": 0, "journal_rows": held["journal_rows"], "retry_at": 0}
            write(folder / "retry.json", held)
        while pending(folder):
            if held["consecutive_failures"] >= 7:
                write(folder / "retry.json", held)
                return (
                    5,
                    "judge unavailable after seven consecutive failures; after diagnosis rerun with --resume-unavailable",
                )
            if held["consecutive_failures"]:
                # Across sessions wait only the remainder of the persisted backoff.
                backoff = max(0, min(300, held["retry_at"] - time.time()))
                if clock() - started + backoff >= args.budget:
                    write(folder / "retry.json", held)
                    return 3, "budget reached; rerun"
                if backoff:
                    sleep(backoff)
            before_rows = len(journal_rows(folder))
            try:
                grading.grade_one(work, metric, pin, limit=1, sender=sender)
            except (Exception, SystemExit):
                if (folder / "NOT_EVIDENCE.json").exists():
                    return stopped()
                if not any(
                    row["status"] == "unavailable" for row in journal_rows(folder)[before_rows:]
                ):
                    raise
                held["consecutive_failures"] += 1
                held["journal_rows"] = len(journal_rows(folder))
                held["retry_at"] = time.time() + 300
                write(folder / "retry.json", held)
                if held["consecutive_failures"] >= 7:
                    return (
                        5,
                        "judge unavailable after seven consecutive failures; after diagnosis rerun with --resume-unavailable",
                    )
                if clock() - started + 300 >= args.budget:
                    return 3, "budget reached; rerun"
                continue
            held = {
                "consecutive_failures": 0,
                "journal_rows": len(journal_rows(folder)),
                "retry_at": 0,
            }
            write(folder / "retry.json", held)
            if clock() - started >= args.budget:
                return 3, "budget reached; rerun"
        target = out / (plan_name(args.key, metric) + ".json")
        if not target.exists() or (
            metric != "bridge" and not target.with_suffix(".cases.jsonl").exists()
        ):
            grading.export_one(args.key, metric, work, runs, pin, out)
        reading_path = out / f"reading-{args.key}-after-{metric}.json"
        if metric == "m2" or (metric == "bridge" and not reading_path.exists()):
            result = reading.build(private, args.records, args.spec, registered_keys(args.records))
            public(reading_path, result)
            if result["decision"]["harm"]:
                return stopped()
    return 0, "key complete"


def log_exception(args, exc):
    try:
        private = outside(args.private)
    except (Exception, SystemExit):
        return None
    path = private / args.key / "driver.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(datetime.now(timezone.utc).isoformat() + "\n")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
    return path


def execute(args, **kwargs):
    try:
        # The frozen planner/judge prints ids/diagnostics. Keep the driver one-line.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return run(args, **kwargs)
    except (Exception, SystemExit) as exc:
        log = log_exception(args, exc)
        own_gate = (
            isinstance(exc, SystemExit)
            and isinstance(exc.code, str)
            and any(
                frame.f_code is require.__code__
                for frame, _ in traceback.walk_tb(exc.__traceback__)
            )
        )
        reason = " ".join(exc.code.split())[:200] if own_gate else type(exc).__name__
        return 1, f"refusal: {reason}" + (f"; log: {log}" if log is not None else "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", choices=KEYS)
    parser.add_argument("--budget", type=float, default=840)
    for name in ("spec", "private", "records", "runs"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--mac-stop", required=True)
    parser.add_argument("--resume-unavailable", action="store_true")
    code, status = execute(parser.parse_args())
    print(f"{code} {status}", flush=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
