"""Freeze, receipt, grade and export; only grade sends requests."""

import argparse
import math
import shutil
from pathlib import Path

from v6_common import (
    BASES,
    HERE,
    JUDGE_SHA,
    KEYS,
    ROOT,
    SPEC,
    STANDS,
    digest,
    final,
    load,
    outside,
    plan_name,
    protocol,
    public,
    read,
    registration,
    require,
    rows,
    sha,
    stand_receipt,
    tool_hashes,
    unicode_gate,
    unique,
    write,
)
from v6_replay import stream_reading


def regex_gate(summary):
    versions = unicode_gate()
    for field, expected in versions.items():
        require(summary.get(field) == expected, field + " differs from replay")
    return versions


def old_export(path, key, metric):
    from scripts import chat_answer_judge as judge

    path = Path(path)
    protocol.committed(path)
    protocol.committed(path.with_suffix(".cases.jsonl"))
    for source in (path, path.with_suffix(".cases.jsonl")):
        data = source.read_bytes()
        require(
            b"\r" not in data and not data.startswith(b"\xef\xbb\xbf"), "old export needs UTF-8/LF"
        )
        data.decode("utf-8")
    record = read(path)
    data = unique(rows(path.with_suffix(".cases.jsonl")))
    p = record["provenance"]
    require(record["base"] == key and record["judge"] == "answers", "old base/instrument differs")
    require(len(data) == 100 and p["prompt_id"] == "QA_PROMPT_V4", "old cases/prompt differ")
    require(
        p["salt"] == judge.SALT
        and p["instructions_sha256"] == digest(judge.INSTRUCTIONS)
        and p["route"] == judge.isolated.settings(judge.SYSTEM_PROMPT),
        "old judge route differs",
    )
    require(
        p["adapter_sha256"] == JUDGE_SHA
        and p["tool_sha256"] == sha(final.frozen("export").__file__),
        "old judge/export bytes differ",
    )
    require(
        bool(p["runs"])
        and all(
            r["code_sha"].startswith(STANDS[key])
            and r["model_digest"] == final.MODEL_DIGEST
            and r["tenant"] == (key if key == "aircargo" else "ext_" + key)
            for r in p["runs"].values()
        ),
        "old stand/model/tenant differs",
    )
    if key in BASES:
        require(
            p["references_withheld"] is (metric == "m1") and ("m2" in record) is (metric == "m2"),
            "old reference exposure differs",
        )
    else:
        export = final.frozen("export")
        require(
            p["reading"]["text"]
            == export.reading_text((ROOT / export.HANDOVER).read_text("utf-8")),
            "aircargo reading differs",
        )
    return record, data


def source_gate(source, old):
    from scripts import chat_answer_judge as judge

    source = outside(source)
    hashes = {
        k: sha(source / (k + suffix)) for k, suffix in (("plan", ".json"), ("verdicts", ".jsonl"))
    }
    require(
        all(hashes[k] == old["provenance"][k + "_sha256"] for k in hashes),
        "bridge source hashes differ",
    )
    plan = read(source / "plan.json")
    judge.check_plan(plan)
    copies = [i for i in plan["items"] if "retest_of" in i]
    valid = judge._vouched(plan, rows(source / "verdicts.jsonl"))
    require(
        len(copies) == 15 and all(i["retest_of"] in valid for i in copies),
        "bridge needs 15 admitted originals",
    )
    return hashes


def run_hashes(runs, key):
    held = {}
    require(not list(Path(runs).rglob("._*")), "AppleDouble in runs")
    for number in range(1, 11):
        folder = Path(runs) / f"v6-{key}-b{number:02d}"
        require(folder.is_dir(), "V6 batch missing")
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                held[path.relative_to(runs).as_posix()] = sha(path)
    for name in (f"v6-{key}.json", "COMPLETE"):
        held[name] = sha(Path(runs) / name)
    return held


def summary_gate(summary, key):
    require(summary["key"] == key and summary["whole"] is True, "V6 key is incomplete")
    require(summary["code_sha"].startswith(STANDS[key]), "V6 stand differs")
    require(
        summary["tools"] == tool_hashes()
        and summary["prompt_template_sha256"] == sha(HERE / "qa_prompt_v6.txt"),
        "V6 tools/template differ",
    )
    require(
        stand_receipt(summary["environment_before"]) == stand_receipt(summary["environment_after"]),
        "V6 environment changed",
    )
    require(summary["started"] <= summary["finished"], "V6 time order differs")
    answers, parity = unique(summary["rows"]), unique(summary["parity"])
    require(len(answers) == 100 and set(answers) == set(parity), "V6 parity/case set differs")
    idle = {r["batch"]: r for r in summary["idle"]}
    require(len(summary["idle"]) == 10 and set(idle) == set(range(1, 11)), "idle batches differ")
    for case, row in answers.items():
        require(parity[case]["parity"] is True and row["parity"] is True, "package parity failed")
        for field in ("v6_prompt_sha256", "package_prompt_sha256", "same_context", "batch"):
            require(row[field] == parity[case][field], "V6 parity row differs")
        require(
            row["idle_clean"] is (not idle[row["batch"]]["busy"]), "idle classification differs"
        )
    return answers


def counts(plan, metric):
    from scripts import chat_answer_judge as judge

    judge.check_plan(plan)
    first = [i for i in plan["items"] if "retest_of" not in i]
    copies = [i for i in plan["items"] if "retest_of" in i]
    eligible = {i["item_id"] for i in first if "message" in i}
    require(
        len(first) == (15 if metric == "bridge" else 100)
        and len({i["case_id"] for i in first}) == len(first),
        "plan cases differ",
    )
    require(
        len(copies) == min(15, len(eligible))
        and len({i["retest_of"] for i in copies}) == len(copies)
        and all(i["retest_of"] in eligible and "message" in i for i in copies),
        "plan retests differ",
    )
    require(
        all(("message" in i) != bool(i.get("empty_answer")) for i in first),
        "plan empty-answer encoding differs",
    )
    return len(copies) if metric == "bridge" else len(eligible) + len(copies)


def shown_gate(folder, entry, row):
    """Recompute the pure function from private raw bytes before freezing any request."""
    folder = Path(folder)
    raw_path = folder / "raw" / (entry["prompt_file"] + ".raw")
    raw = raw_path.read_bytes().decode("utf-8")
    timeline = read(folder / "raw" / (entry["prompt_file"] + ".timeline.json"))
    result = stream_reading(raw, entry["question"], timeline["v6"])
    fallback = bool(set(result["flags"]) & {"parse", "language"})
    require(
        row["flags"] == result["flags"] and row["fallback"] is fallback, "raw guard flags differ"
    )
    fallback_path = folder / "raw" / (entry["prompt_file"] + ".fallback")
    require(fallback_path.exists() is fallback, "fallback artifact differs")
    shown = fallback_path.read_bytes().decode("utf-8") if fallback else result["text"]
    require((timeline["fallback"] is not None) is fallback, "fallback timeline differs")
    second = stream_reading(shown, "", timeline["fallback"], tagged=False) if fallback else None
    for trace, calculated in ((timeline["v6"], result), (timeline["fallback"], second)):
        if trace is not None:
            require(
                all(
                    trace[k] == calculated[k]
                    for k in ("answer_open_sec", "unit_seconds", "first_shown_sec")
                ),
                "release timeline differs",
            )
    when = result["first_shown_sec"]
    if fallback:
        when = second["first_shown_sec"]
        when = timeline["v6"]["end_sec"] + when if when is not None else None
    require(
        row["first_shown_sec"] == when
        and row["full_buffer_sec"] == (when if fallback else result["full_buffer_sec"])
        and row["cut_at"] == result["cut_at"]
        and row["prefix_whole_disagreement"] == result["prefix_whole_disagreement"]
        and row["v6_stream_sec"] == timeline["v6"]["end_sec"]
        and row["chunks"] == len(timeline["v6"]["chunks"])
        and row["fallback_chunks"] == (len(timeline["fallback"]["chunks"]) if fallback else None)
        and row["fallback_stream_sec"] == (timeline["fallback"]["end_sec"] if fallback else None),
        "derived display reading differs",
    )
    require(
        entry["answer"] == shown.strip() and digest(shown.strip()) == row["shown_sha256"],
        "shown answer differs from raw",
    )
    for field in ("v6_stream_sec", "total_sec", "package_stream_sec"):
        require(
            isinstance(row[field], (int, float)) and math.isfinite(row[field]) and row[field] >= 0,
            "invalid stream seconds",
        )
    require(
        row["v6_stream_sec"] <= 3600 and (row["fallback_stream_sec"] is not None) is fallback,
        "stream ceiling/fallback time differs",
    )
    if fallback:
        require(
            isinstance(row["fallback_stream_sec"], (int, float))
            and math.isfinite(row["fallback_stream_sec"])
            and 0 <= row["fallback_stream_sec"] <= 3600,
            "fallback stream ceiling",
        )
    require(
        abs(row["total_sec"] - row["v6_stream_sec"] - (row["fallback_stream_sec"] or 0)) < 1e-6,
        "pair stream time differs",
    )


def freeze(key, config, runs, private, receipt, spec_path):
    from scripts import chat_answer_judge as judge

    spec_hash = registration(spec_path)
    protocol.committed(spec_path)
    runs, private = outside(runs), outside(private)
    destination = private
    partial = private.with_name(private.name + ".partial")
    protected = [runs, outside(config["source"])]
    if key in BASES:
        protected.append(outside(config["references"]))
    require(
        all(
            not output.is_relative_to(p) and not p.is_relative_to(output)
            for output in (private, partial.resolve())
            for p in protected
        ),
        "judge output overlaps read-only input",
    )
    require(
        not partial.is_symlink() and partial.resolve().parent == private.parent,
        "unsafe partial folder",
    )
    if partial.exists() and not private.exists():
        # A kill after receipt publication but before the last rename is also resumable.
        if receipt.exists():
            require(
                (partial / "receipt.json").is_file()
                and sha(receipt) == sha(partial / "receipt.json"),
                "partial receipt differs; retain for diagnosis",
            )
            receipt.unlink()
        shutil.rmtree(partial)
    require(not private.exists() and not receipt.exists(), "plans/receipt freeze once")
    summary = read(runs / f"v6-{key}.json")
    versions = regex_gate(summary)
    measured = summary_gate(summary, key)
    require(
        summary["spec_sha256"] == spec_hash
        and read(runs / "COMPLETE")["summary_sha256"] == sha(runs / f"v6-{key}.json"),
        "V6 completion/spec differs",
    )
    old = {
        m: old_export(config["old_" + m], key, m)
        for m in (("m1", "m2") if key in BASES else ("m1",))
    }
    for _, data in old.values():
        require(
            set(data) == set(measured)
            and all(data[i]["prompt_sha256"] == measured[i]["package_prompt_sha256"] for i in data),
            "old judge prompts differ from replay",
        )
    source = source_gate(config["source"], old["m1"][0])
    refs = None
    if key in BASES:
        refs = outside(config["references"])
        require(
            all(r["provenance"]["references_sha256"] == sha(refs) for r, _ in old.values()),
            "references differ from package",
        )
        ref_rows = unique(rows(refs))
        require(set(ref_rows) == set(measured), "reference ids differ")
        for case, row in ref_rows.items():
            require(
                all(
                    data[case]["cluster"] == row["cluster"]
                    and data[case]["stratum"] == row["stratum"]
                    for _, data in old.values()
                ),
                "reference clusters/strata differ",
            )
    paths = {f"v6-{key}-b{n:02d}": runs / f"v6-{key}-b{n:02d}" for n in range(1, 11)}
    names, questions = set(), []
    for path in paths.values():
        launch = read(path / "launch.json")
        require(
            launch["status"] == "complete" and launch["code_sha"] == summary["code_sha"],
            "V6 launch incomplete/stand differs",
        )
        entries = judge.run_answers(path)
        require(
            len(entries) == 10 and [e["case_id"] for e in entries] == launch["cases"],
            "V6 batch order/count differs",
        )
        require(
            len(list((path / "prompts").glob("*-stream.txt"))) == 10,
            "one V6 prompt per case required",
        )
        for entry in entries:
            row = measured[entry["case_id"]]
            require(
                entry["prompt_id"] == "QA_PROMPT_V5"
                and entry["prompt_sha256"] == row["v6_prompt_sha256"]
                and digest(entry["answer"]) == row["shown_sha256"],
                "shown answer/prompt differs",
            )
            shown_gate(path, entry, row)
            names.update(n for n, _ in entry["documents"])
            questions.append(entry["question"])
    private = partial
    private.mkdir(parents=True)
    if refs:
        shutil.copyfile(refs, private / "references.jsonl")
        refs = private / "references.jsonl"
    for metric in old:
        plan = judge.build_plan(
            paths,
            judge._references(refs) if metric == "m2" else {},
            retest=15,
            references_sha256=sha(refs) if refs else None,
            withheld=metric == "m1" and refs is not None,
        )
        write(private / metric / "plan.json", plan)
        if key == "aircargo":
            # Reuse the exact package reading object, including its originating commit.
            plan["reading"] = old["m1"][0]["provenance"]["reading"]
            write(private / metric / "plan.json", plan)
    load("reports/answer-prompt-v4/tools/bridge_plan.py", "v6_bridge").main(
        [str(config["source"]), str(private / "bridge")]
    )
    metrics = [*old, "bridge"]
    pin = {
        "spec": SPEC,
        "spec_sha256": spec_hash,
        "key": key,
        **versions,
        "replay_versions": {field: summary[field] for field in versions},
        "stand": summary["code_sha"],
        "tools": tool_hashes(),
        "prompt_template_sha256": summary["prompt_template_sha256"],
        "plans": {m: sha(private / m / "plan.json") for m in metrics},
        "requests": {m: counts(read(private / m / "plan.json"), m) for m in metrics},
        "bridge_seed": protocol.prefix(private / "bridge/verdicts.jsonl"),
        "source": source,
        "references_sha256": sha(refs) if refs else None,
        "answer_files": run_hashes(runs, key),
        "old": {
            m: {
                "path": str(Path(config["old_" + m]).resolve().relative_to(ROOT).as_posix()),
                "record_sha256": sha(config["old_" + m]),
                "cases_sha256": sha(Path(config["old_" + m]).with_suffix(".cases.jsonl")),
            }
            for m in old
        },
    }
    public(private / "receipt.json", pin, names, questions)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(private / "receipt.json", receipt)
    private.rename(destination)
    return pin


def admitted(key, private, receipt, spec_path):
    registration(spec_path)
    protocol.committed(spec_path)
    protocol.committed(receipt)
    pin = read(receipt)
    require(
        pin["key"] == key and pin["spec"] == SPEC and pin["spec_sha256"] == sha(spec_path),
        "receipt key/spec differs",
    )
    require(pin["tools"] == tool_hashes(), "receipt tools differ")
    regex_gate(pin)
    regex_gate(pin["replay_versions"])
    require(
        set(pin["plans"]) == ({"m1", "m2", "bridge"} if key in BASES else {"m1", "bridge"}),
        "receipt lacks plans",
    )
    for metric, expected in pin["plans"].items():
        path = private / metric / "plan.json"
        require(
            sha(path) == expected and counts(read(path), metric) == pin["requests"][metric],
            "frozen plan differs",
        )
    protocol.seed_gate(private / "bridge/verdicts.jsonl", pin["bridge_seed"])
    if key in BASES:
        require(
            sha(private / "references.jsonl") == pin["references_sha256"],
            "frozen references differ",
        )
    for metric, held in pin["old"].items():
        path = ROOT / held["path"]
        old_export(path, key, metric)
        require(
            sha(path) == held["record_sha256"]
            and sha(path.with_suffix(".cases.jsonl")) == held["cases_sha256"],
            "old export changed after freeze",
        )
    return pin


def export_gate(key, metric, private, pin, record, data=None, measured=None):
    """Tie public readings to the frozen plan and admitted private replies, including gaps."""
    from scripts import chat_answer_judge as judge

    export = final.frozen("export")
    folder = Path(private) / metric
    plan = read(folder / "plan.json")
    lines = rows(folder / "verdicts.jsonl")
    valid = judge._vouched(plan, lines)
    instrument = export.judge_of(plan)
    retest = export.stability(instrument, plan, valid)
    require(record["retest"] == retest, "export retest differs from admitted replies")
    expected_status = (
        "counted"
        if retest["passed"] and not (folder / "NOT_EVIDENCE.json").exists()
        else "NOT_EVIDENCE"
    )
    require(record["status"] == expected_status, "export status differs")
    if metric == "bridge":
        require(
            record["plan_sha256"] == pin["plans"][metric]
            and record["verdicts_sha256"] == sha(folder / "verdicts.jsonl")
            and record["source_plan_sha256"] == pin["source"]["plan"]
            and record["source_verdicts_sha256"] == pin["source"]["verdicts"],
            "bridge provenance differs",
        )
        return
    p = record["provenance"]
    require(
        record["base"] == key and record["judge"] == "answers", "export base/instrument differs"
    )
    require(
        p["plan_sha256"] == pin["plans"][metric]
        and p["verdicts_sha256"] == sha(folder / "verdicts.jsonl"),
        "export plan/replies differ",
    )
    for field in (
        "salt",
        "prompt_id",
        "instructions_sha256",
        "route",
        "runs",
        "references_sha256",
        "references_withheld",
        "reading",
    ):
        require(p.get(field) == plan.get(field), "export provenance differs: " + field)
    require(
        p["adapter_sha256"] == JUDGE_SHA and p["tool_sha256"] == sha(export.__file__),
        "export tools differ",
    )
    require(p["prompt_id"] == "QA_PROMPT_V5", "not a V6-shaped prompt")
    first = unique([i for i in plan["items"] if "retest_of" not in i])
    require(set(first) == set(data) == set(measured), "export case ids differ")
    refs = unique(rows(Path(private) / "references.jsonl")) if key in BASES else {}
    for case, item in first.items():
        row = data[case]
        require(
            all(
                row.get(f) == item.get(f)
                for f in (
                    "item_id",
                    "run",
                    "documents",
                    "marks_listed",
                    "marks_unlisted",
                    "has_reference",
                    "empty_answer",
                    "empty_context",
                    "route",
                )
            ),
            "export planned fields differ",
        )
        grade = export.grade(instrument, item, valid)
        require(
            row["grade"] == grade and row["missing"] is (grade is None),
            "export grade differs from admitted reply",
        )
        require(
            row["prompt_sha256"] == item["prompt_sha256"] == measured[case]["v6_prompt_sha256"],
            "export prompt differs from replay",
        )
        if item["item_id"] in valid:
            require(
                all(row.get(f) == valid[item["item_id"]][f] for f in instrument["keep"]),
                "export verdict fields differ",
            )
        if key in BASES:
            require(
                all(row[f] == refs[case][f] for f in ("stratum", "cluster")),
                "export clusters/strata differ",
            )
        if metric == "m2":
            require(
                row["has_reference"] is item["has_reference"]
                and row.get("m2") == export.m2(item, valid.get(item["item_id"])),
                "export M2 differs",
            )
    require(
        record["missing"] == sorted(c for c, r in data.items() if r["missing"]),
        "export missing list differs",
    )


def export_one(key, metric, private, runs, pin, out):
    legacy = load("reports/stage4-final/tools/judge.py", "v6_package_judge")
    folder = private / metric
    name = plan_name(key, metric)
    require(run_hashes(runs, key) == pin["answer_files"], "answers changed since freeze")
    if metric == "bridge":
        result = legacy.bridge_export(
            folder, {"inputs": {"v4": pin["source"]}}, out / (name + ".json")
        )
    else:
        plan = read(folder / "plan.json")
        result = final.frozen("export").export(
            folder,
            name,
            out,
            {label: runs / label for label in plan["runs"]},
            private / "references.jsonl" if key in BASES else None,
        )
    if (folder / "NOT_EVIDENCE.json").exists():
        result.update(status="NOT_EVIDENCE", request_duration_stop=True)
        write(out / (name + ".json"), result)
    # The frozen exporter uses the host newline. Keep its data/instrument intact,
    # but publish V6 artifacts as UTF-8/LF on the Windows judge laptop too.
    for suffix in (".json", ".cases.jsonl"):
        path = out / (name + suffix)
        if path.is_file():
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    return result


def grade_one(private, metric, pin, *, limit=0, sender=None):
    from scripts import chat_answer_judge as judge

    require(limit >= 0, "negative grade limit")
    legacy = load("reports/stage4-final/tools/judge.py", "v6_package_judge")
    folder = private / metric
    require(not (folder / "NOT_EVIDENCE.json").exists(), "judge stopped")
    return judge.run_plan(
        read(folder / "plan.json"),
        folder,
        legacy.timed_sender(
            folder, pin["requests"][metric], sender or judge._isolated_sender(judge.CLI_TIMEOUT_S)
        ),
        limit=limit,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "grade", "export"))
    parser.add_argument("key", choices=KEYS)
    for name in ("private", "receipt", "spec"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("config", "runs", "out"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--metric", choices=("m1", "m2", "bridge"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    if args.command == "plan":
        require(args.config and args.runs, "plan needs config and runs")
        freeze(
            args.key, read(args.config)[args.key], args.runs, args.private, args.receipt, args.spec
        )
        return
    require(args.metric is not None, "choose metric")
    private = outside(args.private)
    pin = admitted(args.key, private, args.receipt, args.spec)
    require(args.metric in pin["plans"], "metric not registered for key")
    if args.command == "export":
        require(args.out and args.runs, "export needs runs and output")
        export_one(args.key, args.metric, private, args.runs, pin, args.out)
        return
    grade_one(private, args.metric, pin, limit=args.limit)


if __name__ == "__main__":
    main()
