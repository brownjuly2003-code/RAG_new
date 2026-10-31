"""Freeze one base's M1, M2 and bridge before that base's first grade."""

import argparse
from pathlib import Path

from execute import series_gate
from prepare import check_receipt
from protocol import (
    BASES,
    REQUESTS,
    SPEC,
    batch_hashes,
    committed,
    frozen,
    outside,
    prefix,
    public_write,
    read,
    require,
    runs_gate,
    seed_gate,
    sha,
    write,
)
from record import answers


def output_gate(private, config):
    """Never place generated plans/references inside (or above) a read-only input root."""
    private = outside(private)
    protected = [config["data"], config["stage2"]["run"]]
    for c in config["bases"].values():
        protected.extend([c["runs"], c["references"], *c["plans"].values()])
    for value in protected:
        path = outside(value)
        require(
            not private.is_relative_to(path) and not path.is_relative_to(private),
            "judge output overlaps read-only inputs",
        )
    return private


def plan_counts(plan, metric):
    """Count the frozen judge's messages; empty originals are deterministic bad answers."""
    first = [i for i in plan["items"] if "retest_of" not in i]
    copies = [i for i in plan["items"] if "retest_of" in i]
    empty = sum(i.get("empty_answer") is True for i in first)
    eligible = {i["item_id"] for i in first if "message" in i}
    require(
        len(first) == (15 if metric == "bridge" else 100)
        and len({i["case_id"] for i in first}) == len(first)
        and all(("message" in i) != bool(i.get("empty_answer")) for i in first)
        and len(copies) == min(15, len(eligible))
        and len({i["retest_of"] for i in copies}) == len(copies)
        and all(i["retest_of"] in eligible and "message" in i for i in copies),
        "plan does not hold all registered requests",
    )
    if metric == "bridge":
        require(empty == 0, "historical bridge has empty originals")
        return len(copies), empty
    return len(eligible) + len(copies), empty


def freeze(config, private, runs, baseline, receipt, base):
    from common import load

    from scripts import chat_answer_judge as answer

    require(base in BASES, "choose base")
    private, runs = output_gate(private, config), outside(runs)
    runs_gate(runs)
    held = check_receipt(baseline, config, private)
    folders = [private / "judge" / f"{base}-{metric}" for metric in REQUESTS]
    require(
        not any(p.exists() for p in folders) and not receipt.exists(),
        "new judge folder and receipt required",
    )
    measured = answers(runs, base, Path(config["data"]))
    complete = series_gate(runs, baseline, measured, base)
    require(
        complete["product_diff"]["item6_sha"] == held["item6_sha"],
        "completion registration differs",
    )
    pin = {
        "spec": SPEC,
        "base": base,
        "baseline_sha256": sha(baseline),
        "completion": complete,
        "answer_files": batch_hashes(runs, base),
        "plans": {},
        "requests": {},
        "bridge_seeds": {},
    }
    bridge = load("reports/answer-prompt-v4/tools/bridge_plan.py", "stage5_bridge_plan")
    paths = {label: runs / label for label in measured["runs"]}
    refs = private / "references" / f"{base}.jsonl"
    origin = outside(config["bases"][base]["references"])
    require(sha(origin) == held["bases"][base]["references_sha256"], "references changed")
    require(not refs.exists(), "new references copy required")
    refs.parent.mkdir(parents=True, exist_ok=True)
    refs.write_bytes(origin.read_bytes())
    for metric in ("m1", "m2"):
        plan = answer.build_plan(
            paths,
            {} if metric == "m1" else answer._references(refs),
            retest=15,
            references_sha256=sha(refs),
            withheld=metric == "m1",
        )
        require(plan["prompt_id"] == "QA_PROMPT_V4", "new plan prompt differs")
        write(private / "judge" / f"{base}-{metric}" / "plan.json", plan)
    bridge.main([config["bases"][base]["source"], str(private / "judge" / f"{base}-bridge")])
    for metric in REQUESTS:
        key = f"{base}-{metric}"
        folder = private / "judge" / key
        plan = read(folder / "plan.json")
        count, empty = plan_counts(plan, metric)
        if metric == "m1":
            pin["empty_answers"] = empty
        elif metric == "m2":
            require(empty == pin["empty_answers"], "M1/M2 empty answer count differs")
        pin["plans"][key] = sha(folder / "plan.json")
        pin["requests"][key] = count
        if metric == "bridge":
            pin["bridge_seeds"][base] = prefix(folder / "verdicts.jsonl")
    pin["inputs"] = {
        base: {
            "source": held["bases"][base]["bridge_source"],
            "references_sha256": held["bases"][base]["references_sha256"],
        }
    }
    public_write(receipt, pin, Path(config["data"]))
    return pin


def admitted(receipt, private, baseline, base):
    private = outside(private)
    committed(receipt)
    committed(baseline)
    pin = read(receipt)
    require(
        pin["spec"] == SPEC and pin["baseline_sha256"] == sha(baseline), "receipt baseline differs"
    )
    require(pin["base"] == base, "receipt belongs to another base")
    expected = {f"{base}-{m}" for m in REQUESTS}
    require(
        set(pin["plans"]) == expected and set(pin["requests"]) == expected, "receipt lacks plans"
    )
    refs = private / "references" / f"{base}.jsonl"
    require(sha(refs) == pin["inputs"][base]["references_sha256"], "references differ from receipt")
    for metric in REQUESTS:
        key = f"{base}-{metric}"
        path = private / "judge" / key / "plan.json"
        require(
            sha(path) == pin["plans"][key],
            "plan differs from committed receipt",
        )
        count, empty = plan_counts(read(path), metric)
        require(
            pin["requests"][key] == count and (metric == "bridge" or pin["empty_answers"] == empty),
            "plan counts differ from committed receipt",
        )
    seed_gate(private / "judge" / f"{base}-bridge" / "verdicts.jsonl", pin["bridge_seeds"][base])
    return pin


def export_one(base, metric, private, runs, pin, out):
    from judge import bridge_export

    require(pin["base"] == base, "receipt belongs to another base")
    folder = private / "judge" / f"{base}-{metric}"
    if metric == "bridge":
        result = bridge_export(
            folder,
            {"inputs": {"v4": pin["inputs"][base]["source"]}},
            out / f"stage5-{base}-bridge.json",
        )
    else:
        require(
            batch_hashes(runs, base) == pin["answer_files"], "answers changed since plan freeze"
        )
        plan = read(folder / "plan.json")
        result = frozen("export").export(
            folder,
            f"stage5-{base}-{metric}",
            out,
            {label: runs / label for label in plan["runs"]},
            private / "references" / f"{base}.jsonl",
        )
    if (folder / "NOT_EVIDENCE.json").exists():
        # Preserve every verdict and its statistics, even if enough retests already agree.
        result.update(status="NOT_EVIDENCE", request_duration_stop=True)
        write(out / f"stage5-{base}-{metric}.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "grade", "export"))
    for name in ("private", "receipt", "baseline"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--base", choices=BASES, required=True)
    parser.add_argument("--metric", choices=REQUESTS)
    args = parser.parse_args()
    if args.command == "plan":
        require(
            args.config is not None and args.runs is not None, "plan needs private config and runs"
        )
        freeze(
            read(outside(args.config)),
            args.private,
            args.runs,
            args.baseline,
            args.receipt,
            args.base,
        )
        return
    require(args.base is not None and args.metric is not None, "choose base and metric")
    pin = admitted(args.receipt, args.private, args.baseline, args.base)
    if args.command == "export":
        require(
            args.out is not None and (args.metric == "bridge" or args.runs is not None),
            "export needs output and answer runs",
        )
        export_one(args.base, args.metric, args.private, args.runs, pin, args.out)
        return
    from judge import timed_sender

    from scripts import chat_answer_judge as answer

    key = f"{args.base}-{args.metric}"
    folder = args.private / "judge" / key
    answer.run_plan(
        read(folder / "plan.json"),
        folder,
        timed_sender(folder, pin["requests"][key], answer._isolated_sender(answer.CLI_TIMEOUT_S)),
    )


if __name__ == "__main__":
    main()
