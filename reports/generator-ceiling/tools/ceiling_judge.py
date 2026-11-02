"""Copy answers, freeze once, admit committed receipts, grade and export."""

import argparse
import contextlib
import copy
import io
import json
import math
import shutil
import time
from pathlib import Path

import ceiling_answer as arm
import ceiling_common as c
from ceiling_route import language, rollout_gate


def copy_runs(key, source_runs, destination, measured):
    """Only the two answer values change; launch and prompt bytes are copied."""
    destination = Path(destination)
    c.require(not destination.exists(), "arm runs already exist")
    for n in range(1, 11):
        label = f"final-answers-{key}-b{n:02d}"
        source, target = Path(source_runs) / label, destination / label
        (target / "prompts").mkdir(parents=True)
        (target / "cases").mkdir()
        shutil.copyfile(source / "launch.json", target / "launch.json")
        for path in sorted((source / "prompts").glob("*-stream.txt")):
            shutil.copyfile(path, target / "prompts" / path.name)
        for path in sorted((source / "cases").glob("*.json")):
            value = c.read(path)
            row = measured[value["case_id"]]
            c.require(row["status"] in arm.TERMINAL, "unfinished answer")
            answer = (
                next(
                    a["gate"]["answer"]
                    for a in row["attempts"]
                    if a["id"] == row["accepted_attempt"]
                )
                if row["status"] == "accepted"
                else ""
            )
            result = [event for event in value.get("events", []) if event.get("type") == "result"]
            c.require(
                len(result) == 1 and "answer" in value and "answer" in result[0],
                "case needs exactly two answer fields",
            )
            value["answer"] = result[0]["answer"] = answer
            c.write(target / "cases" / path.name, value)
        before, after = c.judge().run_answers(source), c.judge().run_answers(target)
        c.require(len(before) == len(after) == 10, "arm copy count differs")
        for first, second in zip(before, after, strict=True):
            c.require(
                {k: v for k, v in first.items() if k != "answer"}
                == {k: v for k, v in second.items() if k != "answer"},
                "arm copy changed prompt or route",
            )
    return {
        f"final-answers-{key}-b{n:02d}": destination / f"final-answers-{key}-b{n:02d}"
        for n in range(1, 11)
    }


def audit_measurement(key, series, state, package):
    measured = {r["case_id"]: r for r in state["cases"].values() if r["key"] == key}
    c.require(
        set(measured) == set(c.unique(package)) and len(measured) == 100, "key not answered whole"
    )
    files = {}
    for case in package:
        row = measured[case["case_id"]]
        rebuilt = arm.initial(state["spec_sha256"])
        for attempt in row["attempts"]:
            folder = series / "attempts" / attempt["id"]
            launch, outcome = c.read(folder / "launch.json"), c.read(folder / "outcome.json")
            c.require(attempt == {**launch, **outcome}, "attempt journal differs from state")
            c.require(
                launch["spec_sha256"] == state["spec_sha256"]
                and launch["key"] == key
                and launch["case_id"] == case["case_id"],
                "attempt identity differs",
            )
            c.require(
                Path(launch["cwd"]).resolve() == (folder / "cwd").resolve(),
                "attempt cwd binding differs",
            )
            c.require(
                (folder / "request/prompt.txt").read_bytes()
                == c.wrap(case["saved"].encode("utf-8")),
                "attempt prompt differs",
            )
            c.require(
                launch["saved_prompt_sha256"] == case["prompt_sha256"]
                and launch["request_sha256"] == c.sha(folder / "request/prompt.txt"),
                "attempt prompt hash differs",
            )
            if "gate" in outcome:
                c.require(
                    c.sha(folder / "rollout.jsonl") == outcome["rollout_sha256"], "rollout changed"
                )
                current = rollout_gate(
                    (folder / "rollout.jsonl").read_bytes(),
                    launch["cwd"],
                    outcome["thread_id"],
                    c.read(folder / "job.json"),
                )
                c.require(current == outcome["gate"], "saved route gate differs")
            arm.reduce_attempt(rebuilt, key, case["case_id"], attempt, case["question"])
            files.update(
                {
                    f"attempts/{attempt['id']}/{name}": value
                    for name, value in c.tree_hashes(folder).items()
                }
            )
        c.require(
            rebuilt["cases"][arm.tag(key, case["case_id"])] == row
            and row["status"] in arm.TERMINAL,
            "answer transition differs",
        )
        if row["status"] == "accepted":
            accepted = next(a for a in row["attempts"] if a["id"] == row["accepted_attempt"])
            c.require(
                row["language"] == language(case["question"], accepted["gate"]["answer"]),
                "language gate differs",
            )
    return measured, files


def freeze(key, s5, i6, series, records, spec=c.SPEC):
    spec_hash = c.registration(spec)
    c.public_inputs()
    series, records = c.outside(series), c.output_path(records)
    c.require(not c.judge_stops(series), "judge stopped; amendment required")
    state = c.read(series / "state.json")
    c.require(
        state["spec_sha256"] == spec_hash and state["pilot_passed"] and not state["stops"],
        "arm stopped or pilot not passed",
    )
    package = c.package_cases(s5, i6)[key]
    measured, attempt_files = audit_measurement(key, series, state, package)
    bindings = arm.input_hashes(s5, i6)
    c.require(
        all(bindings.get(k) == v for k, v in state["input_hashes"].items()), "source inputs changed"
    )
    source = Path(s5 if key in c.BASES else i6)
    source_judge = source / "judge" / (key + "-m1" if key in c.BASES else "m1")
    v6 = c.instruments()
    old = {
        m: v6.judge.old_export(c.old_path(key, m), key, m) for m in c.metrics(key) if m != "bridge"
    }
    old_hashes = {
        m: {
            "record_sha256": c.sha(c.old_path(key, m)),
            "cases_sha256": c.sha(c.old_path(key, m).with_suffix(".cases.jsonl")),
        }
        for m in old
    }
    source_pin = v6.judge.source_gate(source_judge, old["m1"][0])
    refs = source / "references" / (key + ".jsonl") if key in c.BASES else None
    for record, data in old.values():
        c.require(
            set(data) == set(measured)
            and all(data[r["case_id"]]["prompt_sha256"] == r["prompt_sha256"] for r in package),
            "paired ids/prompts differ",
        )
        if refs:
            c.require(
                record["provenance"]["references_sha256"] == c.sha(refs), "references changed"
            )
            reference_rows = c.unique(c.rows(refs))
            c.require(set(reference_rows) == set(measured), "reference ids differ")
            c.require(
                all(
                    data[cid][name] == reference_rows[cid][name]
                    for cid in measured
                    for name in ("cluster", "stratum")
                ),
                "reference strata/clusters differ",
            )
    work = series / key
    partial = work.with_name(work.name + ".partial")
    receipt = records / f"plans-{key}.json"
    c.disjoint(work, [source, source_judge, *([refs] if refs else [])])
    c.require(not work.exists(), "key already frozen")
    # Preserve incomplete staging; recover only an entirely published matching receipt.
    if partial.exists():
        if (
            receipt.exists()
            and (partial / "receipt.json").exists()
            and c.sha(receipt) == c.sha(partial / "receipt.json")
        ):
            c.require(c.read(receipt)["spec_sha256"] == spec_hash, "partial registration differs")
            validate_frozen(key, partial, c.read(receipt), series)
            partial.rename(work)
            return c.read(receipt)
        c.require(False, "incomplete partial freeze retained; diagnose before retry")
    c.require(not receipt.exists(), "receipt already exists")
    paths = copy_runs(key, source / "runs", partial / "runs", measured)
    c.write(partial / "measurement.json", measured)
    locations = {
        "source": str(source),
        "source_judge": str(source_judge),
        "references": str(refs) if refs else None,
    }
    c.write(partial / "locations.json", locations)
    if refs:
        shutil.copyfile(refs, partial / "references.jsonl")
    for metric in old:
        plan = c.judge().build_plan(
            paths,
            c.judge()._references(refs) if metric == "m2" else {},
            retest=15,
            references_sha256=c.sha(refs) if refs else None,
            withheld=metric == "m1" and refs is not None,
        )
        if key == "aircargo":
            plan["reading"] = old["m1"][0]["provenance"]["reading"]
        c.write(partial / metric / "plan.json", plan)
        (partial / metric / "verdicts.jsonl").touch()
    bridge = c.load("reports/answer-prompt-v4/tools/bridge_plan.py", "ceiling_bridge")
    bridge.main([str(source_judge), str(partial / "bridge")])
    pin = {
        "key": key,
        "spec_sha256": spec_hash,
        "tools": c.tool_hashes(),
        "wrapper_sha256": c.sha(c.HERE / "wrapper.txt"),
        "public_inputs": dict(c.INPUT_PINS),
        "plans": {m: c.sha(partial / m / "plan.json") for m in c.metrics(key)},
        "requests": {
            m: v6.judge.counts(c.read(partial / m / "plan.json"), m) for m in c.metrics(key)
        },
        "bridge_seed": v6.common.protocol.prefix(partial / "bridge/verdicts.jsonl"),
        "source": source_pin,
        "old": old_hashes,
        "references_sha256": c.sha(refs) if refs else None,
        "answer_files": c.tree_hashes(partial / "runs"),
        "attempt_files": attempt_files,
        "measurement_sha256": c.sha(partial / "measurement.json"),
        "locations_sha256": c.sha(partial / "locations.json"),
        "source_inputs": {k: v for k, v in bindings.items() if k.startswith(key + "/")},
    }
    c.public(partial / "receipt.json", pin)
    c.public(receipt, pin)
    partial.rename(work)  # Last step: no grade can see a partly frozen key.
    return pin


def validate_frozen(key, work, pin, series):
    c.require(
        pin["key"] == key
        and pin["tools"] == c.tool_hashes()
        and pin["wrapper_sha256"] == c.sha(c.HERE / "wrapper.txt"),
        "receipt tools/key differ",
    )
    c.require(set(pin["plans"]) == set(c.metrics(key)), "missing required plan")
    v6 = c.instruments()
    for metric in c.metrics(key):
        path = work / metric / "plan.json"
        c.require(
            c.sha(path) == pin["plans"][metric]
            and v6.judge.counts(c.read(path), metric) == pin["requests"][metric],
            "frozen plan changed",
        )
    c.require(c.tree_hashes(work / "runs") == pin["answer_files"], "arm runs changed")
    for name, expected in pin["attempt_files"].items():
        c.require(c.sha(series / name) == expected, "attempt changed after freeze")
    for name in ("measurement", "locations"):
        c.require(
            c.sha(work / (name + ".json")) == pin[name + "_sha256"], "private binding changed"
        )
    locations = c.read(work / "locations.json")
    source = Path(locations["source"])
    for name, expected in pin["source_inputs"].items():
        c.require(
            c.sha(source / name.split("/", 1)[1]) == expected, "source input changed after freeze"
        )
    for metric, old in pin["old"].items():
        path = c.old_path(key, metric)
        c.require(
            c.sha(path) == old["record_sha256"]
            and c.sha(path.with_suffix(".cases.jsonl")) == old["cases_sha256"],
            "paired package export changed",
        )
    c.require(
        v6.judge.source_gate(locations["source_judge"], c.read(c.old_path(key, "m1")))
        == pin["source"],
        "bridge source changed",
    )
    v6.common.protocol.seed_gate(work / "bridge/verdicts.jsonl", pin["bridge_seed"])
    if key in c.BASES:
        c.require(
            c.sha(work / "references.jsonl")
            == pin["references_sha256"]
            == c.sha(locations["references"]),
            "frozen references changed",
        )


def admitted(key, series, records, spec=c.SPEC):
    spec_hash = c.registration(spec)
    c.public_inputs()
    receipt = Path(records) / f"plans-{key}.json"
    c.committed(receipt)
    pin = c.read(receipt)
    c.require(
        pin["spec_sha256"] == spec_hash and pin["public_inputs"] == c.INPUT_PINS,
        "receipt spec/input mismatch",
    )
    work = Path(series) / key
    c.require(c.sha(work / "receipt.json") == c.sha(receipt), "private/public receipt differs")
    validate_frozen(key, work, pin, Path(series))
    return pin


def public_export(value):
    """Explicit frozen-export schema adaptation, before the strict public writer."""
    result = copy.deepcopy(value)
    provenance = result.get("provenance")
    if provenance:
        reading = provenance.pop("reading", None)
        provenance["reading_sha256"] = (
            c.digest(json.dumps(reading, sort_keys=True, ensure_ascii=False)) if reading else None
        )
        for run in provenance.get("runs", {}).values():
            for name in ("chroma_dir", "cases_file"):
                value = run.pop(name, None)
                if value is not None:
                    run[name + "_sha256"] = c.digest(value)
    for run in result.get("per_run", {}).values():
        if "reference" in run:
            run["reference_counts"] = run.pop("reference")
    fields = result.get("retest", {}).get("field_agreement", {})
    if "reference" in fields:
        fields["reference_counts"] = fields.pop("reference")
    c.public_guard(result)
    return result


def exports(key, series, pin, metric):
    """Frozen exporter writes privately first; all public bytes pass our guard."""
    work = Path(series) / key
    target = work / "export-cache"
    target.mkdir(exist_ok=True)
    name = c.plan_name(key, metric)
    v6 = c.instruments()
    if metric == "bridge":
        result = v6.legacy.bridge_export(
            work / metric, {"inputs": {"v4": pin["source"]}}, target / (name + ".json")
        )
        data = None
    else:
        plan = c.read(work / metric / "plan.json")
        result = v6.common.final.frozen("export").export(
            work / metric,
            name,
            target,
            {label: work / "runs" / label for label in plan["runs"]},
            work / "references.jsonl" if key in c.BASES else None,
        )
        data = c.rows(target / (name + ".cases.jsonl"))
    if (work / metric / "NOT_EVIDENCE.json").exists():
        result.update(status="NOT_EVIDENCE", request_duration_stop=True)
    result = public_export(result)
    if data is not None:
        c.public_guard(data)
    return result, data


def export_one(key, series, records, spec, metric):
    pin = admitted(key, series, records, spec)
    result, data = exports(key, series, pin, metric)
    target = Path(records) / (c.plan_name(key, metric) + ".json")
    c.public(target, result)
    if data is not None:
        c.public_rows(target.with_suffix(".cases.jsonl"), data)
    return result


class ChunkBudget(Exception):
    pass


def grade(
    key,
    series,
    records,
    spec,
    budget=600,
    *,
    sender=None,
    clock=time.monotonic,
    now=time.time,
    resume_unavailable=False,
):
    c.require(math.isfinite(budget) and 0 < budget <= 600, "budget must be in (0, 600]")
    started = clock()
    pin = admitted(key, series, records, spec)
    state = c.read(Path(series) / "state.json")
    if state["stops"] or c.judge_stops(series):
        return 2, "arm stopped"
    work, v6 = Path(series) / key, c.instruments()
    for metric in c.metrics(key):
        folder = work / metric
        if (folder / "NOT_EVIDENCE.json").exists():
            return 2, "judge stopped"
        held = v6.key.retry_state(folder)
        if resume_unavailable and held["consecutive_failures"] >= 7:
            held.update(consecutive_failures=0, retry_at=0)
            c.write(folder / "retry.json", held)
        while v6.key.pending(folder):
            if held["consecutive_failures"] >= 7:
                return 5, "seven unavailable attempts; diagnose"
            # Persisted 300-second backoff; return instead of blocking a foreground session.
            if clock() - started >= budget or held["retry_at"] > now():
                return 3, "budget or retry_at reached; rerun after persisted retry_at"
            before = len(v6.key.journal_rows(folder))

            def bounded_sender(system, message):
                elapsed = clock() - started
                remaining = 1140 - elapsed
                if elapsed >= budget:
                    raise ChunkBudget()
                transport = sender or c.judge()._isolated_sender(
                    min(c.judge().CLI_TIMEOUT_S, remaining)
                )
                return transport(system, message)

            try:
                # Uses the unmodified request clock and run_plan(..., limit=1).
                v6.judge.grade_one(work, metric, pin, limit=1, sender=bounded_sender)
            except ChunkBudget:
                return 3, "foreground budget reached"
            except (Exception, SystemExit):
                if (folder / "NOT_EVIDENCE.json").exists():
                    return 2, "judge request clock stopped"
                added = v6.key.journal_rows(folder)[before:]
                if not any(r["status"] == "unavailable" for r in added):
                    raise
                held.update(
                    consecutive_failures=held["consecutive_failures"] + 1,
                    retry_at=now() + 300,
                    journal_rows=before + len(added),
                )
                c.write(folder / "retry.json", held)
                return (
                    (5, "seven unavailable attempts; diagnose")
                    if held["consecutive_failures"] >= 7
                    else (3, "unavailable; retry_at persisted")
                )
            held = {
                "consecutive_failures": 0,
                "journal_rows": len(v6.key.journal_rows(folder)),
                "retry_at": 0,
            }
            c.write(folder / "retry.json", held)
            duration = c.read(folder / "grade-clock.json")
            if duration["request_seconds"] >= 3 * pin["requests"][metric] * 130:
                c.write(
                    folder / "NOT_EVIDENCE.json",
                    {"status": "NOT_EVIDENCE", "reason": "3x judge forecast"},
                )
                return 2, "judge request clock stopped"
        # Complete but unstable/missing grades stop further requests in this arm.
        result, data = exports(key, series, pin, metric)
        if (
            result["status"] != "counted"
            or result.get("missing")
            or (data and any(r["missing"] for r in data))
        ):
            c.write(
                folder / "NOT_EVIDENCE.json",
                {"status": "NOT_EVIDENCE", "reason": "judge stability or missing replies"},
            )
            return 2, "judge not evidence"
    return 0, "key grading complete"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "grade", "export"))
    parser.add_argument("key", choices=c.KEYS)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--series", default="attempt-01")
    parser.add_argument("--records", type=Path, default=c.PUBLIC)
    parser.add_argument("--spec", type=Path, default=c.SPEC)
    parser.add_argument("--s5", type=Path)
    parser.add_argument("--i6", type=Path)
    parser.add_argument("--budget", type=float, default=600)
    parser.add_argument("--resume-unavailable", action="store_true")
    args = parser.parse_args()
    try:
        series = c.series_path(args.private, args.series)
        c.output_path(args.records)
        with (
            c.serial_lock(args.private),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            if args.command == "freeze":
                c.require(args.s5 is not None and args.i6 is not None, "package paths required")
                pin = freeze(args.key, args.s5, args.i6, series, args.records, args.spec)
                count = sum(pin["requests"].values())
                code, status = (
                    0,
                    f"frozen; commit plans-{args.key}.json; requests={count}; forecast=${count * 0.1775:.2f}-{count * 0.2834:.2f}, seconds={count * 93}-{count * 130}",
                )
            elif args.command == "grade":
                code, status = grade(
                    args.key,
                    series,
                    args.records,
                    args.spec,
                    args.budget,
                    resume_unavailable=args.resume_unavailable,
                )
            else:
                for metric in c.metrics(args.key):
                    export_one(args.key, series, args.records, args.spec, metric)
                code, status = 0, "exports written"
    except (Exception, SystemExit) as exc:
        import traceback

        with contextlib.suppress(Exception):
            c.outside(args.private).mkdir(parents=True, exist_ok=True)
            (Path(args.private) / "judge-error.log").write_bytes(
                traceback.format_exc().encode("utf-8")
            )
        code, status = 1, "refusal: " + type(exc).__name__
    print(f"{code} {status}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
