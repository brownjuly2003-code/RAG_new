"""Frozen HTTP reader and drain, with final-path checks after EVERY question (including 1, 5)."""

import os
import sys
import time
from pathlib import Path

from common import ROOT, load, read, require, write


def observation(run, after):
    """Wait for a fully flushed sample; byte offsets exclude a concurrent partial line."""
    end = time.monotonic() + 30
    while True:
        path = run / "observation.json"
        if path.exists():
            held = read(path)
            if held["monotonic"] >= after:
                return held
        require(time.monotonic() < end, "observation did not cover the question")
        time.sleep(1)


def main():
    run = Path(os.environ["CHAT_RUN_DIR"])
    reader = load("reports/stage1/tools/live_runner.py", "final_http_reader")
    sys.path.insert(0, str(ROOT))
    from record import answer_run, memory, reask_ids, select_attempts

    from auth.jwt_handler import create_access_token

    ids, deadline = sys.argv[1].split(","), float(sys.argv[2])
    speed = read(run / "launch.json")["speed"]
    cases = {c["case_id"]: c for c in __import__("common").rows(os.environ["CHAT_CASES_FILE"])}
    (run / "cases").mkdir()
    schedule = list(ids)
    for i, case_id in enumerate(schedule, 1):
        require(not (run.parent / "STOP").exists(), "operator stop")
        cap = min(3600, deadline - time.monotonic())
        require(cap > 0, "3x forecast reached")
        token = create_access_token("chat-live", role="admin", tenant=os.environ["CHAT_TENANT"])
        case = {
            "case_id": case_id,
            "question": cases[case_id]["query"],
            **reader.ask(cases[case_id]["query"], cap, token),
        }
        try:
            case["drain_sec"] = reader.drain()
        except Exception as error:
            case["drain_error"] = type(error).__name__
        write(run / "cases" / f"{i:02d}-{case_id}.json", case)
        checkpoint = observation(run, case["t0_monotonic"] + case["total_sec"])
        measured = answer_run(
            run, ids[:i], completed=False, all_attempts=speed, checkpoint=checkpoint
        )
        require(
            not memory(run, measured, allow_foreign=True, checkpoint=checkpoint),
            "unreadable memory or llama-server changed",
        )
        if speed and i == 30:
            schedule.extend(reask_ids(measured))
        if speed and i > 30:
            require(not measured[-1]["disturbed"], "question disturbed twice")
        require(time.monotonic() < deadline, "3x forecast reached")
        print(
            "CASE",
            i,
            case_id,
            "first",
            case.get("first_token_sec"),
            "whole",
            case.get("result_sec"),
            "stream_close_including_suggestions",
            case.get("total_sec"),
            "path ok",
            flush=True,
        )
    if speed:
        select_attempts(measured, ids)


if __name__ == "__main__":
    main()
