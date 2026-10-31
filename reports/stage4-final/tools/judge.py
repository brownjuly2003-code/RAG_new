"""Laptop: build M1 and its historical bridge from the actual sent prompts, pin before grading, export.

Uses the unchanged registered judge adapters, instructions, salts and handover reading.
No call is made by plan/export. Grade refuses a plan whose receipt is not committed.
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from common import BASES, ROOT, frozen, load, read, require, rows, sha, write
from record import answers


def inputs(data, source, old_m1):
    """Laptop preflight: four private corpus files and V4's published plan/reply hashes."""
    from record import judge_rows
    from run import corpus

    from scripts import chat_answer_judge as answer

    generation = corpus("aircargo", data)
    old, cases = judge_rows(old_m1, "aircargo", "answers")
    require(
        len(cases) == 100 and all(c.get("context_has_answer") is True for c in cases.values()),
        "V4 ceiling differs",
    )
    require(
        old["provenance"]["prompt_id"] == "QA_PROMPT_V4"
        and all(r["code_sha"].startswith("4f48fed") for r in old["provenance"]["runs"].values()),
        "not V4 aircargo",
    )
    hashes = {
        name: sha(source / (name + "." + suffix))
        for name, suffix in (("plan", "json"), ("verdicts", "jsonl"))
    }
    require(
        all(hashes[k] == old["provenance"][k + "_sha256"] for k in hashes),
        "private V4 input differs from published hashes",
    )
    plan = read(source / "plan.json")
    answer.check_plan(plan)
    valid = answer._vouched(plan, rows(source / "verdicts.jsonl"))
    require(
        all(item["retest_of"] in valid for item in plan["items"] if "retest_of" in item),
        "bridge originals must already have V4's admitted replies",
    )
    require(
        sum("retest_of" in item for item in plan["items"]) == 15, "V4 bridge must have 15 retests"
    )
    return {"corpus": generation, "v4": hashes, "old_m1_sha256": sha(old_m1)}


def bridge_export(folder, pin, out):
    """Same frozen admission/stability, without needing the historic private run folders."""
    from scripts import chat_answer_judge as answer

    export = frozen("export")
    plan = read(folder / "plan.json")
    lines = rows(folder / "verdicts.jsonl")
    valid = answer._vouched(plan, lines)
    admitted = export.admission(lines, valid)
    stability = export.stability(export.judge_of(plan), plan, valid)
    pairs = []
    for item in plan["items"]:
        if "retest_of" in item:
            pair = {
                "case_id": item["case_id"],
                "first": item["retest_of"],
                "copy": item["item_id"],
                "old_cli": admitted.get(item["retest_of"], (None, None))[1],
                "new_cli": admitted.get(item["item_id"], (None, None))[1],
            }
            pairs.append(export.plain(pair))
    result = {
        "status": "counted" if stability["passed"] else "NOT_EVIDENCE",
        "retest": stability,
        "source_plan_sha256": pin["inputs"]["v4"]["plan"],
        "source_verdicts_sha256": pin["inputs"]["v4"]["verdicts"],
        "plan_sha256": sha(folder / "plan.json"),
        "verdicts_sha256": sha(folder / "verdicts.jsonl"),
        "admitted_cli": {
            "old": sorted({p["old_cli"] for p in pairs if p["old_cli"]}),
            "new": sorted({p["new_cli"] for p in pairs if p["new_cli"]}),
        },
        "pairs": pairs,
    }
    write(out, result)
    return result


def make_plans(
    base, runs_dir, data, private, receipt, references=None, v4_source=None, old_m1=None
):
    from scripts import chat_answer_judge as answer

    measured = answers(runs_dir, base, data)  # Requires all ten, not the first nine.
    require(
        not private.exists() and not receipt.exists(), "new plan directory and receipt required"
    )
    runs = {label: runs_dir / label for label in measured["runs"]}
    checked = None
    if base == "aircargo":
        require(
            v4_source is not None and old_m1 is not None,
            "V4 private bridge source and published record required",
        )
        checked = inputs(data, v4_source, old_m1)
    private.mkdir(parents=True)
    if base != "aircargo":
        require(
            references is not None, "external M1 needs its references file for clusters, withheld"
        )
    plans = {
        "m1": answer.build_plan(
            runs,
            {},
            retest=15,
            references_sha256=sha(references) if references else None,
            withheld=references is not None,
        )
    }
    # External M3 is deterministic; stage 5 reuses M1 and registers its M2 separately.
    for key, plan in plans.items():
        write(private / key / "plan.json", plan)
    if base == "aircargo":
        export = frozen("export")
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        frozen_reading = subprocess.check_output(
            ["git", "show", f"{commit}:{export.HANDOVER}"], cwd=ROOT
        ).decode("utf-8")
        export.add_reading(private / "m1", frozen_reading, commit)
    if base == "aircargo":
        load("reports/answer-prompt-v4/tools/bridge_plan.py", "final_bridge").main(
            [str(v4_source), str(private / "bridge")]
        )
        plans["bridge"] = read(private / "bridge/plan.json")
    pin = {
        "base": base,
        "answers_sha256": {label: sha(run / "launch.json") for label, run in runs.items()},
        "plans": {k: sha(private / k / "plan.json") for k in plans},
        "requests": {
            k: sum("message" in i and (k != "bridge" or "retest_of" in i) for i in p["items"])
            for k, p in plans.items()
        },
        "inputs": checked,
    }
    if base == "aircargo":
        seed = (private / "bridge/verdicts.jsonl").read_bytes()
        pin["bridge_seed"] = {"bytes": len(seed), "sha256": hashlib.sha256(seed).hexdigest()}
    write(receipt, pin)
    return pin


def committed(receipt, private, metric):
    relative = receipt.resolve().relative_to(ROOT).as_posix()
    held = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    require(held == receipt.read_bytes(), "receipt has uncommitted changes")
    pin = json.loads(held)
    require(metric in pin["plans"], "metric not in the committed receipt")
    require(
        sha(private / metric / "plan.json") == pin["plans"][metric], "plan not the committed one"
    )
    if metric == "bridge":
        seed = pin["bridge_seed"]
        with (private / "bridge/verdicts.jsonl").open("rb") as stream:
            require(
                hashlib.sha256(stream.read(seed["bytes"])).hexdigest() == seed["sha256"],
                "V4 bridge replies changed",
            )
    return pin


def timed_sender(folder, requests, original):
    clock = folder / "grade-clock.json"
    stopped = folder / "NOT_EVIDENCE.json"
    require(not stopped.exists(), "judge already stopped; read the cause before a new plan")
    seconds = requests * 130
    if not clock.exists():
        write(clock, {"request_seconds": 0.0, "forecast": seconds})
    held = read(clock)
    require(held["forecast"] == seconds, "judge forecast changed")

    def guard():
        if held["request_seconds"] >= 3 * seconds:
            write(stopped, {"status": "NOT_EVIDENCE", "reason": "3x judge forecast"})
            require(False, "judge 3x forecast; keep replies, read cause, new plan required")

    guard()

    def send(*values):
        guard()
        started = time.monotonic()
        try:
            return original(*values)  # Always let an arrived reply reach the frozen journal.
        finally:
            held["request_seconds"] += time.monotonic() - started
            write(clock, held)  # The stop acts before the NEXT request, including after resume.

    print("JUDGE_FORECAST", seconds, "seconds; stop", 3 * seconds, flush=True)
    return send


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inputs", "plan", "grade", "export"))
    parser.add_argument("--base", choices=BASES, required=True)
    parser.add_argument("--private", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--references", type=Path)
    parser.add_argument("--metric", choices=("m1", "bridge"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--v4-source", type=Path)
    parser.add_argument("--old-m1", type=Path)
    args = parser.parse_args()
    if args.command == "inputs":
        require(
            all((args.data, args.v4_source, args.old_m1, args.out)),
            "inputs needs data, V4 source, old M1 and output receipt",
        )
        write(args.out, inputs(args.data, args.v4_source, args.old_m1))
        return
    require(
        args.private is not None and args.receipt is not None, "private folder and receipt required"
    )
    if args.command == "plan":
        require(args.runs is not None and args.data is not None, "plan needs runs and corpus")
        make_plans(
            args.base,
            args.runs,
            args.data,
            args.private,
            args.receipt,
            args.references,
            args.v4_source,
            args.old_m1,
        )
        return
    require(args.metric is not None, "choose metric")
    pin = committed(args.receipt, args.private, args.metric)
    require(pin["base"] == args.base, "receipt names another base")
    folder = args.private / args.metric
    plan = read(folder / "plan.json")
    from scripts import chat_answer_judge as answer

    if args.command == "grade":
        original = answer._isolated_sender(answer.CLI_TIMEOUT_S)
        answer.run_plan(plan, folder, timed_sender(folder, pin["requests"][args.metric], original))
    else:
        require(args.out is not None, "export needs OUT")
        if args.metric == "bridge":
            bridge_export(folder, pin, args.out / f"final-{args.base}-bridge.json")
            return
        require(args.runs is not None, "M1 export needs runs")
        runs = {label: args.runs / label for label in plan["runs"]}
        frozen("export").export(
            folder, f"final-{args.base}-{args.metric}", args.out, runs, args.references
        )


if __name__ == "__main__":
    main()
