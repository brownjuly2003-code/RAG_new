"""Final-path answer gates, V4's paired reading, exact speed intervals and SLO proposal.

Raw runs and plans stay private. Exported cases use stage 2's text-free summary schema.
Quality baselines are explicit paths, so this reader is reusable by later bases.
"""

import argparse
import json
import math
import statistics
from pathlib import Path

from common import (
    BASES,
    CACHE,
    INT8,
    MAX_REASK,
    MODEL_DIGEST,
    NOT_EVIDENCE,
    ONNX,
    PROMPT,
    SETTINGS,
    frozen,
    positive,
    questions,
    read,
    require,
    rows,
    sha,
    write,
)
from stand import effective, environment_gate


def case_gate(case):
    require(not case["path_breaks"], "chat path broke")
    require(not case.get("drain_error") and not case.get("client_error"), "chat did not drain")
    require(case.get("reranker_ok") is True, "reranker failed")
    require(case.get("retrievals") == 1, "not one retrieval")
    for lane in ("vector", "bm25"):
        count = case["path"]["candidates"].get(lane)
        require(isinstance(count, int) and 0 < count <= 14, "lane did not use K14")
    require(
        len(case.get("prompts", [])) == 1 and case["prompts"][0]["labels_source"] > 0,
        "no labelled prompt",
    )
    require(
        all(positive(case.get(k)) for k in ("first_token_sec", "result_sec", "total_sec")),
        "missing finite timing",
    )
    require(case["first_token_sec"] <= case["result_sec"] <= case["total_sec"], "timing order")
    require(case["total_sec"] < 3600, "question cap reached")


def stand_gate(held):
    effective(held["settings"], held["prompt_id"], held["input_limit"])
    require(held["export_sha256"] == INT8 and held["cache_sha256"] == CACHE, "stand digest differs")
    require(held["ollama"] == "0.33.2" and held["model_digest"] == MODEL_DIGEST, "model differs")
    environment_gate(held["environment"])
    require(held["rerank_batch"] is None and held["batch_size"] == 32, "rerank batch differs")
    require(
        held["server"]["server_version"] == "0.33.2" and len(held["server"]["servers"]) == 1,
        "Ollama server differs",
    )


def answer_run(run, ids, completed=True, all_attempts=False, checkpoint=None):
    from scripts import chat_answer_judge as judge

    run = Path(run)
    launch = read(run / "launch.json")
    if completed:
        require(
            launch.get("status") == "complete" and launch.get("runner_exit") == 0,
            "incomplete batch",
        )
        require(
            not any(launch.get(k) for k in ("pg_stop_error", "unload_error", "monitor_failed")),
            "cleanup or monitor failed",
        )
        require(launch["cases"] == ids, "launch question order differs")
    require(launch["ollama_models_before"] == [], "model was not unloaded")
    from run import preload_gate

    preload_gate(launch["preload"], launch["preload_models"], SETTINGS["ollama_context_window"])
    if completed:
        require(launch.get("llama_pid_after") == launch["llama_pid"], "llama-server pid changed")
    require(
        launch["model"] == SETTINGS["ollama_model_name"] and launch["model_digest"] == MODEL_DIGEST,
        "wrong model",
    )
    held = read(run / "stand.json")
    stand_gate(held)
    require(
        read(run / "loaded.json")
        == {
            "tokenizer_snapshot": held["environment"]["tokenizer_snapshot"],
            "ort_intra_op_num_threads": held["environment"]["ort_intra_op_num_threads"],
        },
        "loaded environment differs",
    )
    if completed:
        require(read(run / "stand-after.json") == held, "environment changed during batch")
    settings = read(run / "effective_settings.json")["settings"]
    require(
        all(k in settings and settings[k] == v for k, v in SETTINGS.items()), "API settings differ"
    )
    require(
        settings.get("reranker_runtime") == "onnx" and settings.get("reranker_onnx_path") == ONNX,
        "API runtime differs",
    )
    require(settings.get("vectordb_chroma_dir") == launch["chroma_dir"], "API index differs")
    summary = frozen("summary")
    if checkpoint is None and not completed and (run / "observation.json").exists():
        checkpoint = read(run / "observation.json")
    if checkpoint is not None:
        original_rows = summary.load_jsonl

        def observed_rows(path):
            if Path(path) == run / "resources.jsonl":
                with Path(path).open("rb") as stream:
                    return [
                        json.loads(line)
                        for line in stream.read(checkpoint["resources"]).splitlines()
                    ]
            return original_rows(path)

        # Per-import observer adapter; the frozen reader and its files are unchanged.
        summary.load_jsonl = observed_rows
    _, cases = summary.summarise_run(run, 0, True, {})
    if all_attempts:
        require(launch["speed"], "re-asks belong only to speed")
        require([c["case_id"] for c in cases[: len(ids)]] == ids, "first-pass order differs")
    else:
        require(
            [c["case_id"] for c in cases] == ids and len(set(ids)) == len(ids),
            "case order or completeness differs",
        )
    # Stage timestamps pair a prompt to an attempt, including repeated speed questions.
    # The frozen judge's question-only pairing remains unchanged for the quality plan.
    raw = [read(p) for p in sorted((run / "cases").glob("*.json"))]
    for case in cases:
        case_gate(case)
    for case, original in zip(cases, raw, strict=True):
        text = (run / "prompts" / case["prompts"][0]["file"]).read_text("utf-8")
        require(judge.prompt_id(text) == PROMPT, "answer was not V4")
        require(judge.read_prompt(text)[0] == original["question"], "prompt pairing differs")
    if completed:
        require(
            not memory(run, cases, allow_foreign=True), "unreadable memory or llama-server changed"
        )
    return cases


def provenance_gate(launch, base, cases_file, data):
    from run import corpus

    require(launch["cases_sha256"] == sha(cases_file), "question file differs")
    require(launch["tenant"] == (base if base == "aircargo" else "ext_" + base), "wrong tenant")
    require(launch["corpus_sha256"] == corpus(base, data), "recorded corpus differs")
    require(bool(launch["index_sha256"]), "index receipt missing")


def answers(runs, base, data):
    cases_file, ids = questions(base, data)
    directories = sorted(Path(runs).glob(f"final-answers-{base}-b*"))
    require(len(directories) == 10, "ten batches required before a plan or reading")
    held, cases, provenance = [], [], []
    for n, directory in enumerate(directories):
        require(directory.name == f"final-answers-{base}-b{n + 1:02d}", "batch order differs")
        launch = read(directory / "launch.json")
        provenance_gate(launch, base, cases_file, data)
        require(not launch["speed"], "speed run cannot be a quality batch")
        cases.extend(answer_run(directory, ids[n * 10 : n * 10 + 10]))
        held.append(read(directory / "stand.json"))
        provenance.append(
            {k: launch[k] for k in ("code_sha", "model_digest", "corpus_sha256", "cases_sha256")}
        )
    require(all(v == held[0] for v in held), "different stands in a base")
    require(all(v == provenance[0] for v in provenance), "different provenance in a base")
    return {
        "status": "counted",
        "base": base,
        "stand": held[0],
        "provenance": provenance[0],
        "cases": cases,
        "runs": [p.name for p in directories],
    }


def paired(old, new, families):
    return frozen("v4").paired(old, new, families)


def outcome(bad, good, context, admitted=True):
    if not admitted:
        return NOT_EVIDENCE
    if (
        bad["direction"] == "rises"
        or good["direction"] == "falls"
        or context["direction"] == "falls"
    ):
        return "harm detected"
    if bad["direction"] == "falls" or good["direction"] == "rises":
        return "gain detected"
    return "holds"


def judge_rows(path, base, kind):
    record = read(path)
    require(record["status"] == "counted" and record["retest"]["passed"], "judge stability failed")
    require(record["base"] == base and record["judge"] == kind, "wrong judge base or instrument")
    from evaluation import isolated_request
    from scripts import chat_answer_judge as answer
    from scripts import context_judge as context

    module = answer if kind == "answers" else context
    provenance = record["provenance"]
    require(
        provenance["route"] == isolated_request.settings(module.SYSTEM_PROMPT), "wrong judge route"
    )
    require(
        provenance["salt"] == module.SALT
        and provenance["instructions_sha256"] == answer._digest(module.INSTRUCTIONS),
        "judge instructions or salt differ",
    )
    if base == "aircargo" and kind == "answers":
        export = frozen("export")
        from common import ROOT

        require(
            provenance["reading"]["text"]
            == export.reading_text((ROOT / export.HANDOVER).read_text("utf-8")),
            "handover reading differs",
        )
    data = rows(Path(path).with_suffix(".cases.jsonl"))
    data = [r for r in data if not r.get("retest_of")]
    require(len({r["case_id"] for r in data}) == len(data), "duplicate judge case")
    return record, {r["case_id"]: r for r in data}


def quality(base, answer_record, old_m1, new_m1, bridge):
    require(base == "aircargo", "this M3 ceiling comparison is registered for aircargo")
    ids = [r["case_id"] for r in answer_record["cases"]]
    require(
        answer_record["status"] == "counted" and len(ids) == len(set(ids)) == 100,
        "answers not complete",
    )
    old, a = judge_rows(old_m1, base, "answers")
    new, b = judge_rows(new_m1, base, "answers")
    for rec, table, prefix in (
        (old, a, "4f48fed"),
        (new, b, answer_record["provenance"]["code_sha"]),
    ):
        require(set(table) == set(ids), "judge question set differs")
        require(
            all(r.get("grade") in ("good", "partial_ok", "bad") for r in table.values()),
            "missing or invalid M1 grade",
        )
        require(rec["provenance"]["prompt_id"] == PROMPT, "judge prompt is not V4")
        require(
            all(r["code_sha"].startswith(prefix) for r in rec["provenance"]["runs"].values()),
            "judge stand differs",
        )
    prompt_hashes = {r["case_id"]: r["prompts"][0]["sha256"] for r in answer_record["cases"]}
    require(
        all(b[i]["prompt_sha256"] == prompt_hashes[i] for i in ids),
        "new verdict is not on the sent prompt",
    )
    bridge_record = read(bridge)
    require(
        bridge_record["source_plan_sha256"] == old["provenance"]["plan_sha256"],
        "bridge is not V4's published plan",
    )
    require(
        bridge_record["source_verdicts_sha256"] == old["provenance"]["verdicts_sha256"],
        "bridge replies differ from V4",
    )
    require(
        bridge_record["status"] == "counted" and bridge_record["retest"]["passed"],
        "bridge stability failed; paired M1/M3 NOT_EVIDENCE",
    )
    families = {i: [str(a[i].get("cluster", i))] for i in ids}
    bad = paired(
        {i: int(a[i]["grade"] == "bad") for i in ids},
        {i: int(b[i]["grade"] == "bad") for i in ids},
        families,
    )
    good = paired(
        {i: int(a[i]["grade"] == "good") for i in ids},
        {i: int(b[i]["grade"] == "good") for i in ids},
        families,
    )
    require(
        all(a[i].get("context_has_answer") is True for i in ids), "V4 M3 ceiling is not 100/100"
    )
    require(all(isinstance(b[i].get("context_has_answer"), bool) for i in ids), "new M3 is missing")
    context = paired(
        {i: 1 for i in ids}, {i: int(b[i]["context_has_answer"]) for i in ids}, families
    )
    require(context["direction"] != "rises", "M3 cannot rise above its ceiling")
    return {
        "status": "counted",
        "base": base,
        "m1_bad": bad,
        "m1_good": good,
        "m3": context,
        "m3_old_ceiling": {
            "hits": 100,
            "n": 100,
            "instrument": "M1 context_has_answer",
            "reading": "only a detected fall is harm; no rise outcome",
        },
        "outcome": outcome(bad, good, context),
        "stage5": "wait for Julia's yes/no" if bad["direction"] == "rises" else "follows",
        "baselines": {"m1": "V4 4f48fed", "m3": "V4 4f48fed context_has_answer"},
        "admitted_cli": {
            "old": old["replies"]["admitted_cli"],
            "new": new["replies"]["admitted_cli"],
            "bridge": bridge_record["admitted_cli"],
        },
        "bridge": bridge_record,
        "provenance": answer_record["provenance"],
        "stand": answer_record["stand"],
        "input_sha256": {
            str(q): sha(q)
            for q in (
                Path(old_m1),
                Path(old_m1).with_suffix(".cases.jsonl"),
                Path(new_m1),
                Path(new_m1).with_suffix(".cases.jsonl"),
                Path(bridge),
            )
        },
        "pair_ids": ids,
    }


def quantile(values, p):
    """Nearest-rank point; equal-tailed exact order-statistic 95% confidence set.

    Tail ranks use Binomial(n,p), without a normal approximation. None is an unbounded
    endpoint, not a missing observation. Ties can only make coverage conservative.
    """
    require(bool(values) and all(positive(v) for v in values), "invalid times")
    values = sorted(values)
    n = len(values)
    masses = [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]
    lower = max(k for k in range(n + 1) if sum(masses[:k]) <= 0.025)
    upper = min(k for k in range(1, n + 2) if sum(masses[k:]) <= 0.025)
    return {
        "n": n,
        "p": p,
        "point": statistics.median(values) if p == 0.5 else values[math.ceil(n * p) - 1],
        "ci95": [values[lower - 1] if lower else None, values[upper - 1] if upper <= n else None],
        "ranks": [lower, upper],
        "coverage": sum(masses[lower:upper]),
    }


def sign(old, new):
    require(set(old) == set(new) and bool(old), "speed pairs differ")
    require(all(positive(v) for v in [*old.values(), *new.values()]), "invalid paired time")
    faster = sum(new[k] < old[k] for k in old)
    slower = sum(new[k] > old[k] for k in old)
    n = faster + slower
    p = (
        min(1.0, 2 * sum(math.comb(n, k) for k in range(min(faster, slower) + 1)) / 2**n)
        if n
        else 1.0
    )
    return {
        "faster": faster,
        "slower": slower,
        "ties": len(old) - n,
        "p_exact": p,
        "direction": ("faster" if faster > slower else "slower") if p < 0.05 else "not detected",
    }


def slo(p90):
    require(positive(p90), "invalid SLO input")
    return math.ceil(p90 / 30) * 30


def memory(run, cases, allow_foreign=False, checkpoint=None):
    def observations(name):
        if checkpoint is None:
            return rows(run / (name + ".jsonl"))
        with (run / (name + ".jsonl")).open("rb") as stream:
            return [json.loads(line) for line in stream.read(checkpoint[name]).splitlines()]

    samples, resources = observations("samples"), observations("resources")
    raw = [read(p) for p in sorted((run / "cases").glob("*.json"))]
    launch = read(run / "launch.json")
    own_pids = {launch.get(k) for k in ("api_pid", "runner_pid", "supervisor_pid", "llama_pid")}
    reasons = set()
    for case, original in zip(cases, raw, strict=True):
        low, high = original["t0_monotonic"], original["t0_monotonic"] + original["total_sec"]
        within = [s for s in samples if low <= s["monotonic"] <= high]
        resource = [s for s in resources if low <= s["monotonic"] <= high]
        for series in (within, resource):
            times = [s["monotonic"] for s in series]
            if (
                not times
                or times != sorted(times)
                or max(b - a for a, b in zip([low, *times], [*times, high], strict=True)) > 30
            ):
                reasons.add("resource observation gap >30s")
        if any([p["pid"] for p in s["procs"]] != [launch["llama_pid"]] for s in within):
            reasons.add("llama-server pid changed")
        foreign = set()
        for sample in resource:
            if set(sample.get("job_pids", [])) - own_pids:
                foreign.add("foreign job")
            for pid, _, rss, name in sample["procs"] + sample["largest"]:
                if pid in own_pids:
                    continue
                if "python" in name.lower() and rss >= 512 * 2**20:
                    foreign.add("foreign Python >=512 MiB")
                if any(v in name.lower() for v in ("qemu", "limactl", "virtualization")):
                    foreign.add("virtual machine")
        case["disturbed"] = sorted(foreign)
        if not allow_foreign:
            reasons.update(foreign)
        swaps = [s["swap_mib"]["used"] for s in within if s.get("swap_mib")]
        mem = [p["mem_mib"] for s in within for p in s["procs"] if p.get("mem_mib") is not None]
        rss = [p["rss_mib"] for s in within for p in s["procs"] if p.get("rss_mib") is not None]
        case["mac_memory"] = {
            "samples": len(within),
            "swap_mib": statistics.median(swaps) if swaps else None,
            "llama_mem_mib": statistics.median(mem) if mem else None,
            "llama_rss_mib": statistics.median(rss) if rss else None,
        }
        if not swaps or not mem or not rss:
            reasons.add("missing per-question memory")
    return sorted(reasons)


def reask_ids(first):
    require(
        len(first) == 30 and len({c["case_id"] for c in first}) == 30, "first pass must hold 30"
    )
    ids = [c["case_id"] for c in first if c["disturbed"]]
    require(len(ids) <= MAX_REASK, "more than 6 disturbed in the first pass")
    return ids


def select_attempts(attempts, ids):
    first, again = attempts[:30], attempts[30:]
    require([c["case_id"] for c in first] == ids, "first-pass order differs")
    wanted = reask_ids(first)
    require([c["case_id"] for c in again] == wanted, "re-ask order or completeness differs")
    require(not any(c["disturbed"] for c in again), "question disturbed twice")
    replacements = {c["case_id"]: c for c in again}
    return [replacements.get(c["case_id"], c) for c in first]


def baseline_gate(held, source, cases_sha):
    require(held["source"] == source and held["status"] == "counted", "wrong speed baseline")
    require(held["cases_sha256"] == cases_sha, "baseline question file differs")
    require(bool(held["input_sha256"]), "baseline input receipt missing")


def speed_read(cases, baseline, descriptive=None, reasons=()):
    require(
        len(cases) == 30 and len({c["case_id"] for c in cases}) == 30,
        "thirty readable questions required",
    )
    require(not reasons, "disturbed or unreadable: " + ", ".join(reasons))
    result = {"status": "counted", "times": {}, "paired_19beeb1": {}, "slo_proposal_seconds": {}}
    require(
        len(baseline) == 30 and len({r["case_id"] for r in baseline}) == 30,
        "baseline duplicates or missing cases",
    )
    for key in ("first_token_sec", "result_sec"):
        values = [c[key] for c in cases]
        result["times"][key] = {"median": quantile(values, 0.5), "p90": quantile(values, 0.9)}
        result["paired_19beeb1"][key] = sign(
            {c["case_id"]: c[key] for c in baseline}, {c["case_id"]: c[key] for c in cases}
        )
        result["slo_proposal_seconds"][key] = slo(result["times"][key]["p90"]["point"])
    if descriptive is not None:
        require(
            [c["case_id"] for c in descriptive] == [c["case_id"] for c in cases],
            "item 5 order differs",
        )
        require(
            all(positive(c[k]) for c in descriptive for k in ("first_token_sec", "result_sec")),
            "invalid item 5 times",
        )
        result["item5_descriptive"] = {
            k: statistics.median([r[k] for r in descriptive])
            for k in ("first_token_sec", "result_sec")
        }
    result["times"]["total_sec"] = {
        "median": quantile([c["total_sec"] for c in cases], 0.5),
        "p90": quantile([c["total_sec"] for c in cases], 0.9),
    }
    result["time_names"] = {
        "result_sec": "whole answer",
        "total_sec": "stream close including suggestions",
    }
    result["comparison"] = (
        "descriptive whole-path change against 19beeb1: V3 to V4, package, cache cap and intervening code; decides nothing"
    )
    result["slo_owner"] = "Julia; these are proposals, not an adopted SLO"
    result["cases"] = cases
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("answers", "quality", "speed"))
    parser.add_argument("--base", choices=BASES, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    for name in ("old-m1", "new-m1", "bridge", "baseline", "item5"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    require(not args.out.exists(), "record already exists")
    try:
        if args.kind == "speed":
            require(
                args.base == "aircargo" and args.baseline is not None,
                "speed needs aircargo and baseline",
            )
            cases_file, ids = questions(args.base, args.data)
            attempts = answer_run(args.runs, ids[:30], all_attempts=True)
            launch = read(args.runs / "launch.json")
            provenance_gate(launch, args.base, cases_file, args.data)
            require(launch["speed"], "quality times cannot decide speed")
            require(
                launch.get("exclusive_owned_work") is True, "exclusive owned work was not recorded"
            )
            reasons = memory(args.runs, attempts, allow_foreign=True)
            cases = select_attempts(attempts, ids[:30])
            for name in ("before", "after"):
                reasons.extend(read(args.runs / f"idle-{name}.json")["reasons"])
            old = read(args.baseline)
            baseline_gate(old, "19beeb1", launch["cases_sha256"])
            descriptive = read(args.item5) if args.item5 else None
            if descriptive:
                baseline_gate(descriptive, "item5", launch["cases_sha256"])
            result = speed_read(
                cases, old["cases"], descriptive["cases"] if descriptive else None, reasons
            )
            result["attempts"] = attempts
            result["reasked"] = reask_ids(attempts[:30])
            result["provenance"] = {
                "launch_sha256": sha(args.runs / "launch.json"),
                "stand": read(args.runs / "stand.json"),
                "code_sha": launch["code_sha"],
                "corpus_sha256": launch["corpus_sha256"],
                "cases_sha256": launch["cases_sha256"],
                "item5_sha256": sha(args.item5) if args.item5 else None,
                "baseline_sha256": sha(args.baseline),
                "samples_sha256": sha(args.runs / "samples.jsonl"),
                "resources_sha256": sha(args.runs / "resources.jsonl"),
                "exclusive_owned_work": launch["exclusive_owned_work"],
            }
        else:
            result = answers(args.runs, args.base, args.data)
            if args.kind == "quality":
                require(
                    all((args.old_m1, args.new_m1, args.bridge)),
                    "M1 records and bridge required",
                )
                result = quality(args.base, result, args.old_m1, args.new_m1, args.bridge)
        from stage2_common import source_names, without_text

        _, names = source_names(args.data, args.base)
        cases_file, _ = questions(args.base, args.data)
        without_text(result, names, [r["query"] for r in rows(cases_file)])
        write(args.out, result)
    except (SystemExit, ValueError, KeyError, OSError) as error:
        write(args.out, {"status": NOT_EVIDENCE, "reason_type": type(error).__name__})
        raise


if __name__ == "__main__":
    main()
