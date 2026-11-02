"""Serial, durable answer driver. Only the explicit CLI starts companion tasks."""

import argparse
import contextlib
import io
import math
import re
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import ceiling_common as c
from ceiling_route import CompanionClient, language

PILOT_SALT = "generator-ceiling-2026-11-02:pilot"
TERMINAL = ("accepted", "counted_out")


def pilot(cases):
    selected = []
    for key, size in zip(c.KEYS, (7, 7, 6), strict=True):
        ordered = sorted(
            cases[key],
            key=lambda row: (c.digest(f"{PILOT_SALT}:{key}:{row['case_id']}"), row["case_id"]),
        )
        selected.extend((key, row["case_id"]) for row in ordered[:size])
    return selected


def percentile90(values):
    ordered = sorted(values)
    c.require(
        bool(ordered) and all(math.isfinite(v) and v >= 0 for v in ordered), "invalid task times"
    )
    # Nearest rank, fixed before the pilot; no interpolation across task times.
    return ordered[math.ceil(0.9 * len(ordered)) - 1]


def forecast(times):
    c.require(len(times) >= 20, "pilot needs twenty measured tasks")
    task = max(60, 30 * math.ceil(percentile90(times) / 30))
    return {"task": task, "task_stop": 3 * task, "series_stop": 3 * 280 * task}


def initial(spec_hash):
    return {
        "spec_sha256": spec_hash,
        "cases": {},
        "probe": False,
        "pilot_step": 0,
        "pilot_passed": False,
        "stops": [],
        "infrastructure_streak": 0,
        "postpilot_seconds": 0,
        "agents_hashes": [],
        "chunks": [],
    }


def tag(key, case_id):
    return key + ":" + case_id


def reduce_attempt(state, key, case_id, attempt, question):
    """Replayable state transition; infrastructure never consumes the one route redo."""
    name = tag(key, case_id)
    row = state["cases"].setdefault(
        name,
        {"key": key, "case_id": case_id, "status": "pending", "route_failures": 0, "attempts": []},
    )
    if attempt["id"] in {a["id"] for a in row["attempts"]}:
        return
    c.require(row["status"] not in TERMINAL, "terminal question cannot be regenerated")
    row["attempts"].append(attempt)
    if attempt.get("postpilot"):
        state["postpilot_seconds"] += attempt["elapsed_s"]
    if attempt["kind"] == "infrastructure":
        state["infrastructure_streak"] += 1
    else:
        state["infrastructure_streak"] = 0
        if attempt["kind"] == "route_failure":
            row["route_failures"] += 1
            if row["route_failures"] >= 2:
                row["status"] = "counted_out"
        else:
            c.require(
                attempt["kind"] == "accepted" and attempt["gate"]["passed"],
                "invalid accepted attempt",
            )
            row["status"] = "accepted"
            row["accepted_attempt"] = attempt["id"]
            row["language"] = language(question, attempt["gate"]["answer"])
    if (attempt.get("timeout") and not attempt.get("series_timeout")) or attempt[
        "elapsed_s"
    ] > attempt["task_stop"]:
        state["stops"].append("task_forecast")
    if attempt.get("series_timeout"):
        state["stops"].append("series_forecast")
    if attempt.get("cleanup_failed"):
        state["cleanup_pending"] = attempt["id"]
    counted = [
        v for v in state["cases"].values() if v["key"] in c.KEYS and v["status"] == "counted_out"
    ]
    if len(counted) > 15 or any(sum(v["key"] == k for v in counted) > 5 for k in c.KEYS):
        state["stops"].append("counted_out_limit")
    if (
        sum(
            v.get("language", {}).get("match") is False
            for v in state["cases"].values()
            if v["key"] in c.KEYS
        )
        > 5
    ):
        state["stops"].append("language_limit")
    if state.get("forecast") and state["postpilot_seconds"] >= state["forecast"]["series_stop"]:
        state["stops"].append("series_forecast")
    state["stops"] = sorted(set(state["stops"]))


def attempt_public(attempt):
    fields = (
        "id",
        "kind",
        "reason",
        "elapsed_s",
        "task_forecast",
        "task_stop",
        "timeout",
        "processes_stopped",
        "job_id",
        "thread_id",
        "rollout_file",
        "rollout_sha256",
        "raw_output_sha256",
        "raw_output_mismatch",
        "agents_sha256",
        "request_sha256",
        "saved_prompt_sha256",
        "postpilot",
    )
    result = {name: attempt[name] for name in fields if name in attempt}
    if "gate" in attempt:
        result["gate"] = {
            name: attempt["gate"][name] for name in ("passed", "reasons", "tokens", "timing")
        }
        result["answer_sha256"] = c.digest(attempt["gate"]["answer"])
    return result


def summary(state, key):
    result = {"key": key, "spec_sha256": state["spec_sha256"], "rows": []}
    for row in state["cases"].values():
        if row["key"] == key:
            result["rows"].append(
                {
                    "case_id": row["case_id"],
                    "status": row["status"],
                    "language": row.get("language"),
                    "route_failures": row["route_failures"],
                    "attempts": [attempt_public(a) for a in row["attempts"]],
                }
            )
    result["rows"].sort(key=lambda row: row["case_id"])
    result["whole"] = len(result["rows"]) == 100 and all(
        r["status"] in TERMINAL for r in result["rows"]
    )
    return result


def route_numbers(state):
    cases = [v for v in state["cases"].values() if v["key"] in c.KEYS]
    attempts = [a for row in cases for a in row["attempts"]]
    times = [a["elapsed_s"] for a in attempts]
    return {
        "attempts": len(attempts),
        "redos": sum(
            max(0, sum(a["kind"] != "infrastructure" for a in r["attempts"]) - 1) for r in cases
        ),
        "counted_out": sum(r["status"] == "counted_out" for r in cases),
        "infrastructure_failures": sum(a["kind"] == "infrastructure" for a in attempts),
        "infrastructure_streak": state["infrastructure_streak"],
        "language_mismatches": sum(r.get("language", {}).get("match") is False for r in cases),
        "raw_output_mismatches": sum(a.get("raw_output_mismatch", False) for a in attempts),
        "agents_hashes": state["agents_hashes"],
        "processes_stopped": sum(a.get("processes_stopped", 0) for a in attempts),
        "task_seconds": {
            "n": len(times),
            "median": statistics.median(times) if times else None,
            "p90": percentile90(times) if times else None,
        },
        "tokens": {
            field: sum(a.get("gate", {}).get("tokens", {}).get(field) or 0 for a in attempts)
            for field in (
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
                "total_tokens",
            )
        },
        "stops": state["stops"],
        "pilot_passed": state["pilot_passed"],
        "forecast": state.get("forecast"),
        "chunks": state["chunks"],
        "probe": {
            "passed": state["probe"],
            "attempts": [
                attempt_public(a)
                for r in state["cases"].values()
                if r["key"] == "probe"
                for a in r["attempts"]
            ],
        },
    }


def persist(folder, state, records):
    c.write(folder / "state.json", state)
    for key in c.KEYS:
        c.public(records / f"arm-{key}.json", summary(state, key))
    c.public(records / "arm.json", route_numbers(state))


def input_hashes(s5, i6):
    result = {}
    for key in c.KEYS:
        source = Path(s5 if key in c.BASES else i6)
        for n in range(1, 11):
            folder = source / "runs" / f"final-answers-{key}-b{n:02d}"
            paths = [
                folder / "launch.json",
                *sorted((folder / "prompts").glob("*-stream.txt")),
                *sorted((folder / "cases").glob("*.json")),
            ]
            if key in c.BASES:
                paths.append(folder / "stages.jsonl")
            for path in paths:
                result[key + "/" + path.relative_to(source).as_posix()] = c.sha(path)
    return result


def one_attempt(
    state,
    folder,
    key,
    case,
    client,
    task_forecast,
    task_stop,
    agents_hash,
    *,
    postpilot=False,
    before_launch=lambda: None,
):
    case_id = case["case_id"]
    existing = state["cases"].get(tag(key, case_id), {})
    if existing.get("status") in TERMINAL:
        return False
    attempt_id = uuid.uuid4().hex
    target = folder / "attempts" / attempt_id
    (target / "cwd").mkdir(parents=True)
    (target / "request").mkdir()
    raw = case["saved"].encode("utf-8")
    request = raw if key == "probe" else c.wrap(raw)
    (target / "request/prompt.txt").write_bytes(request)
    remaining = (
        state["forecast"]["series_stop"] - state["postpilot_seconds"] if postpilot else task_stop
    )
    c.require(remaining > 0, "series forecast exhausted")
    launch = {
        "id": attempt_id,
        "key": key,
        "case_id": case_id,
        "cwd": str(target / "cwd"),
        "started": datetime.now(timezone.utc).isoformat(),
        "task_forecast": task_forecast,
        "task_stop": task_stop,
        "agents_sha256": agents_hash,
        "postpilot": postpilot,
        "request_sha256": c.digest(request),
        "saved_prompt_sha256": c.digest(raw),
        "spec_sha256": state["spec_sha256"],
        "timeout_s": min(task_stop, remaining),
    }
    # Forecast and exact request are durable before the task starts.
    before_launch()
    c.write(target / "launch.json", launch)
    result = client.run(target, launch["timeout_s"])
    if result.get("timeout") and launch["timeout_s"] < task_stop:
        result["series_timeout"] = True
    c.write(target / "outcome.json", result)
    reduce_attempt(state, key, case_id, {**launch, **result}, case["question"])
    return True


def recover(state, folder, cases, client):
    known = {a["id"] for r in state["cases"].values() for a in r["attempts"]}
    launches = sorted(
        (folder / "attempts").glob("*/launch.json"), key=lambda p: c.read(p)["started"]
    )
    for path in launches:
        launch = c.read(path)
        c.require(
            launch["spec_sha256"] == state["spec_sha256"]
            and launch["id"] == path.parent.name
            and Path(launch["cwd"]).resolve() == (path.parent / "cwd").resolve(),
            "recovery binding differs",
        )
        if launch["id"] in known:
            continue
        result = (
            c.read(path.parent / "outcome.json")
            if (path.parent / "outcome.json").exists()
            else client.recover(path.parent)
        )
        if (
            result.get("timeout")
            and launch.get("timeout_s", launch["task_stop"]) < launch["task_stop"]
        ):
            result["series_timeout"] = True
            c.write(path.parent / "outcome.json", result)
        case = cases[launch["key"]][launch["case_id"]]
        reduce_attempt(
            state, launch["key"], launch["case_id"], {**launch, **result}, case["question"]
        )


def pilot_gate(state, selected, step):
    rows = [state["cases"].get(tag(k, cid), {}) for k, cid in selected[:step]]
    if (
        any(
            row.get("status") == "counted_out" or row.get("language", {}).get("match") is False
            for row in rows
        )
        or state["stops"]
    ):
        state["stops"] = sorted(set(state["stops"] + ["pilot_failed"]))
        return False
    if not all(row.get("status") == "accepted" for row in rows):
        return False
    state["pilot_step"] = step
    if step == 20:
        # Include redo/infrastructure task time: discarded attempts still consumed time.
        times = [a["elapsed_s"] for r in rows for a in r["attempts"]]
        state["forecast"] = forecast(times)
        state["pilot_passed"] = True
    return True


def run(args, *, client=None, clock=time.monotonic):
    started = clock()
    c.require(math.isfinite(args.budget) and 0 < args.budget <= 840, "budget must be in (0, 840]")
    private = c.outside(args.private)
    c.require(re.fullmatch(r"[A-Za-z0-9_-]+", args.series), "invalid series name")
    folder, records = c.series_path(private, args.series), c.output_path(args.records)
    for path in (args.codex_home, args.companion):
        c.disjoint(private, [path])
    c.require(
        Path(args.state_root).resolve().is_relative_to(private), "companion state must be private"
    )
    spec_hash = c.registration(args.spec)
    state_path = folder / "state.json"
    state = c.read(state_path) if state_path.exists() else initial(spec_hash)
    c.require(state["spec_sha256"] == spec_hash, "amendment needs a fresh series")
    for old_summary in records.glob("arm-*.json"):
        c.require(
            c.read(old_summary)["spec_sha256"] == spec_hash,
            "amendment needs fresh public records; preserve earlier pilot",
        )
    if c.judge_stops(folder):
        return 2, "judge stopped; amendment required"
    # A new series is permitted only under different registered spec bytes.
    for other in private.glob("*/state.json"):
        if other != state_path:
            c.require(
                c.read(other)["spec_sha256"] != spec_hash, "same registration already has a series"
            )
    agents_hash = c.sha(Path(args.codex_home) / "AGENTS.md")
    changed = bool(state["agents_hashes"] and state["agents_hashes"][-1] != agents_hash)
    if not state["agents_hashes"] or changed:
        state["agents_hashes"].append(agents_hash)
    state["chunks"].append(
        {
            "started": datetime.now(timezone.utc).isoformat(),
            "agents_sha256": agents_hash,
            "changed": changed,
        }
    )
    if args.resume_infrastructure and state["infrastructure_streak"] >= 3:
        state["infrastructure_streak"] = 0
    client = client or CompanionClient(args.companion, args.codex_home, args.state_root, args.node)
    cases = {
        "probe": {
            "probe": {
                "case_id": "probe",
                "question": "Reply with exactly OK.",
                "saved": "Reply with exactly OK.",
            }
        }
    }
    selected = []
    if args.command != "probe":
        c.require(state["probe"], "data-free probe must pass first")
        c.require(args.s5 is not None and args.i6 is not None, "package paths required")
        c.disjoint(private, [args.s5, args.i6])
        package = c.package_cases(args.s5, args.i6)
        bindings = input_hashes(args.s5, args.i6)
        c.require(state.get("input_hashes", bindings) == bindings, "saved package inputs changed")
        state["input_hashes"] = bindings
        cases.update({k: c.unique(v) for k, v in package.items()})
        selected = pilot(package)
        c.require(
            state.get("pilot_ids", [list(pair) for pair in selected])
            == [list(pair) for pair in selected],
            "pilot selection changed",
        )
        state["pilot_ids"] = [list(pair) for pair in selected]
    recover(state, folder, cases, client)
    if state.get("cleanup_pending"):
        # Recheck cleanup before any new launch, including a resumed infrastructure run.
        from ceiling_route import cleanup, cleanup_failure

        pending = folder / "attempts" / state["cleanup_pending"]
        outcome = c.read(pending / "outcome.json")
        try:
            cleanup(pending / "cwd", tracked=outcome.get("cleanup_tree", ()))
        except (Exception, SystemExit) as exc:
            cleanup_failure(outcome, exc)
            c.write(pending / "outcome.json", outcome)
            raise
        del state["cleanup_pending"]
    persist(folder, state, records)
    if state["stops"]:
        return 2, "stopped; amendment required"
    if state["infrastructure_streak"] >= 3:
        return 5, "three consecutive infrastructure failures; diagnose"
    if args.command == "probe":
        if state["probe"]:
            return 0, "probe already accepted"
        order, task = [("probe", "probe")], {"task": 180, "task_stop": 540}
    elif args.command == "pilot":
        c.require(args.step in (1, 5, 20), "pilot step must be 1, 5 or 20")
        c.require(
            state["pilot_step"] >= {1: 0, 5: 1, 20: 5}[args.step], "read preceding pilot step first"
        )
        order, task = selected[: args.step], {"task": 180, "task_stop": 540}
    else:
        c.require(state["pilot_passed"], "pilot must pass unchanged")
        c.require(args.key in c.KEYS, "key required")
        for earlier in c.KEYS[: c.KEYS.index(args.key)]:
            c.require(summary(state, earlier)["whole"], "previous key incomplete")
        order = [(args.key, cid) for cid in cases[args.key] if (args.key, cid) not in selected]
        task = state["forecast"]
    # A full per-task ceiling must fit the foreground contract, including cleanup.
    c.require(
        task["task_stop"] <= 1080,
        "pilot forecast cannot fit 1200-second call; register an amendment",
    )
    for key, case_id in order:
        while state["cases"].get(tag(key, case_id), {}).get("status") not in TERMINAL:
            if (
                clock() - started >= args.budget
                or clock() - started + task["task_stop"] + 60 >= 1170
            ):
                persist(folder, state, records)
                return 3, "budget reached; rerun"
            one_attempt(
                state,
                folder,
                key,
                cases[key][case_id],
                client,
                task["task"],
                task["task_stop"],
                agents_hash,
                postpilot=args.command == "run",
                before_launch=lambda: c.require(
                    c.registration(args.spec) == spec_hash, "registration changed"
                ),
            )
            if args.command == "pilot":
                pilot_gate(state, selected, args.step)
            persist(folder, state, records)
            if state["stops"]:
                return 2, "stopped by arm rule"
            if state["infrastructure_streak"] >= 3:
                return 5, "three consecutive infrastructure failures; diagnose"
            if state.get("cleanup_pending"):
                return 5, "owned cleanup failed; diagnose before retry"
    if args.command == "probe":
        row = state["cases"][tag("probe", "probe")]
        state["probe"] = (
            row["status"] == "accepted"
            and row["attempts"][-1]["gate"]["answer"].strip().removesuffix(".") == "OK"
        )
        if not state["probe"]:
            state["stops"].append("probe_failed")
    elif args.command == "pilot":
        pilot_gate(state, selected, args.step)
    persist(folder, state, records)
    return (2, "stopped by arm rule") if state["stops"] else (0, f"{args.command} complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe", "pilot", "run"))
    for name in ("private", "companion", "codex-home", "state-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("s5", "i6"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--spec", type=Path, default=c.SPEC)
    parser.add_argument("--records", type=Path, default=c.PUBLIC)
    parser.add_argument("--series", default="attempt-01")
    parser.add_argument("--node", default="node")
    parser.add_argument("--step", type=int)
    parser.add_argument("--key", choices=c.KEYS)
    parser.add_argument("--budget", type=float, default=840)
    parser.add_argument("--resume-infrastructure", action="store_true")
    args = parser.parse_args()
    try:
        with (
            c.serial_lock(c.outside(args.private)),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code, status = run(args)
    except (Exception, SystemExit) as exc:
        code, status = 1, "refusal: " + type(exc).__name__
        # Full diagnostics remain private; provider text never reaches stdout.
        import traceback

        with contextlib.suppress(Exception):
            path = c.outside(args.private) / "driver-error.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(traceback.format_exc().encode("utf-8"))
    with contextlib.suppress(Exception):
        numbers = c.read(Path(args.records) / "arm.json")
        status += f"; AGENTS_changed={int(numbers['chunks'][-1]['changed'])}; rawOutput_mismatches={numbers['raw_output_mismatches']}; language_mismatches={numbers['language_mismatches']}"
    print(f"{code} {status}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
