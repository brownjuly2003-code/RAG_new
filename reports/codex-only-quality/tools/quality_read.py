"""Offline Q/R reading, including explicit NOT_EVIDENCE for incomplete/stopped runs."""

from __future__ import annotations

import contextlib
import io
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import quality_driver as d  # noqa: E402
import quality_freeze as f  # noqa: E402

cv = d.cv


def paired(before, after, groups, repo=d.ROOT):
    record = d.canonical_import(repo, "ceiling_record", "reports/generator-ceiling/tools")
    ruler = d.canonical_import(repo, "evaluation.semantic_ruler", "")
    cv.require(ruler.SEED == 20261001 and ruler.RESAMPLES == 10000, "interval registration differs")
    value = record.pair(before, after, groups)
    value["baseline_share"], value["product_share"] = value.pop("package"), value.pop("codex")
    return {
        **value,
        "baseline_count": sum(before.values()),
        "product_count": sum(after.values()),
        "seed": 20261001,
        "resamples": 10000,
    }


def fallen(value):
    return value["newcombe95"][1] < 0 and value["cluster95"][1] < 0


def decision(q, r, refusals, stopped):
    if refusals or stopped or q is None or r is None:
        return {
            "row": 1,
            "outcome": "NOT_EVIDENCE",
            "reasons": sorted(set(refusals)),
            "stop_fired": bool(stopped),
            "next_step": "Diagnose; amend rule changes before new requests; explicitly resume infrastructure only after diagnosis.",
        }
    q_fell, r_fell = fallen(q), fallen(r)
    if q_fell or r_fell:
        return {
            "row": 2,
            "outcome": "below stage 5v's Codex reading",
            "q_fell": q_fell,
            "r_fell": r_fell,
            "next_step": "Re-measure context selection at higher effort or off in a new registration."
            if r_fell
            else "Diagnose the answer path: release, exec flags and Windows numerics before any new registration.",
        }
    return {
        "row": 3,
        "outcome": "holds (no detected fall)",
        "q_fell": False,
        "r_fell": False,
        "next_step": "Publish these numbers as product quality under codex-only.",
    }


def match_baselines(registration, baseline, gate):
    cv.require(registration["q_baseline"] == baseline, "Q baseline differs from registration")
    cv.require(
        registration["r_gate"] == gate and gate.get("passed") is True,
        "R gate differs from registration",
    )


def sent_point(reader, cid, documents, baseline):
    if not documents:
        # The unchanged historical instrument requires 1..5 documents. The spec
        # defines its empty-set extension; the reproduced gate supplies gold.
        cv.require(not reader.cases[cid].get("unresolved_evidence"), "gold evidence unresolved")
        gold = baseline["gold"]
        cv.require(type(gold) is bool, "R gold flag missing")
        return {"gold": gold, "hit": 0 if gold else None, "fraction": 0.0 if gold else None}
    return reader.saved_point(reader.cases[cid], documents)


def analyze(old, new, measured, r_old, r_new, groups, repo=d.ROOT):
    q, r = {"per_key": {}}, {"per_key": {}, "cases": {}}
    q_before, q_after, q_groups, r_before, r_after, r_groups = {}, {}, {}, {}, {}, {}
    for key in cv.KEYS:
        ids = list(old[key])
        cv.require(
            len(ids) == 100
            and set(ids) == set(new[key]) == set(measured[key])
            and all(row["class"] in d.TERMINAL for row in measured[key].values()),
            "key not whole",
        )
        before, after, families = {}, {}, {}
        for cid in ids:
            row = new[key][cid]
            cv.require(
                row.get("grade") in {"good", "partial_ok", "bad"} and not row.get("missing"),
                "M1 verdict missing",
            )
            tag = key + ":" + cid
            before[tag] = int(
                old[key][cid]["grade"] == "good" and old[key][cid].get("context_has_answer") is True
            )
            after[tag] = int(
                measured[key][cid]["class"] == "accepted"
                and row["grade"] == "good"
                and row.get("context_has_answer") is True
            )
            families[tag] = groups[key][cid]
        q["per_key"][key] = paired(before, after, families, repo)
        q_before.update(before)
        q_after.update(after)
        q_groups.update(families)
        if key not in cv.KEYS[:2]:
            continue
        cv.require(set(r_old[key]) == set(r_new[key]) == set(ids), "R case set differs")
        before, after, families = {}, {}, {}
        r["cases"][key] = []
        for cid in ids:
            left, right = r_old[key][cid], r_new[key][cid]
            cv.require(left["gold"] is right["gold"], "R gold differs")
            r["cases"][key].append({"case_id": cid, "baseline": left, "product": right})
            if not left["gold"]:
                cv.require(
                    left["hit"] is right["hit"] is left["fraction"] is right["fraction"] is None,
                    "no-gold not null",
                )
                continue
            cv.require(left["hit"] in (0, 1) and right["hit"] in (0, 1), "R hit invalid")
            tag = key + ":" + cid
            before[tag], after[tag], families[tag] = left["hit"], right["hit"], groups[key][cid]
        cv.require(len(before) == (100 if key == "wixqa" else 80), "R denominator differs")
        r["per_key"][key] = paired(before, after, families, repo)
        r_before.update(before)
        r_after.update(after)
        r_groups.update(families)
    cv.require(len(q_before) == 300 and len(r_before) == 180, "pooled denominator differs")
    q["pooled"] = paired(q_before, q_after, q_groups, repo)
    r["pooled"] = paired(r_before, r_after, r_groups, repo)
    for item in [r["pooled"], *r["per_key"].values()]:
        item["hit_transitions"] = dict(
            zip(
                ("both_hit", "lost", "gained", "neither_hit"),
                (item["table"][k] for k in ("a", "b", "c", "d")),
                strict=True,
            )
        )
    return {"q": q, "r": r}


def latency(attempts):
    def numbers(values):
        values = sorted(values)
        return {
            "n": len(values),
            "median": values[math.ceil(len(values) * 0.5) - 1] if values else None,
            "p90": values[math.ceil(len(values) * 0.9) - 1] if values else None,
        }

    # Dispatch-to-result only; a broken stream duration is infrastructure time.
    values = [
        a
        for a in attempts
        if a.get("result_utc")
        and a.get("result", {}).get("route") is not None
        and a["classification"] in d.TERMINAL
    ]
    return {
        "with_cold": numbers([a["elapsed_s"] for a in values]),
        "without_cold": numbers([a["elapsed_s"] for a in values if not a.get("cold")]),
        "over_180": sum(a["elapsed_s"] > 180 for a in values),
    }


def diagnostics(state, old=None, new=None):
    per_key = {}
    all_rows = [r for r in state.get("cases", {}).values() if r["key"] in cv.KEYS]
    for key in (*cv.KEYS, "pooled"):
        rows = all_rows if key == "pooled" else [r for r in all_rows if r["key"] == key]
        attempts = [a for r in rows for a in r["attempts"]]
        terminals = [r["attempts"][-1] for r in rows if r["status"] in d.TERMINAL and r["attempts"]]
        keys = cv.KEYS if key == "pooled" else (key,)
        grades, bad_auto = (
            {},
            {
                "numerator": None,
                "denominator": sum(a.get("result", {}).get("route") == "auto" for a in terminals),
                "share": None,
            },
        )
        for side, source in (("baseline", old), ("product", new)):
            if source is not None and all(k in source for k in keys):
                counts = Counter(r.get("grade") for k in keys for r in source[k].values())
                grades[side] = {name: counts[name] for name in ("good", "partial_ok", "bad")}
        if new is not None and all(k in new for k in keys):
            numerator = sum(
                new[r["key"]].get(r["case_id"], {}).get("grade") == "bad"
                and r["attempts"][-1].get("result", {}).get("route") == "auto"
                for r in rows
                if r["status"] in d.TERMINAL and r["attempts"]
            )
            bad_auto.update(
                numerator=numerator,
                share=numerator / bad_auto["denominator"] if bad_auto["denominator"] else None,
            )
        efforts = Counter(c["effort"] for a in attempts for c in a["calls"])
        total = 300 if key == "pooled" else 100
        per_key[key] = {
            "m1": grades,
            "baseline_routes": dict(
                Counter(d.safe_route(r.get("route")) for k in keys for r in old[k].values())
            )
            if old is not None and all(k in old for k in keys)
            else None,
            "routes": dict(
                Counter(d.safe_route(a.get("result", {}).get("route")) for a in terminals)
            ),
            "bad_per_auto": bad_auto,
            "tickets": sum(a.get("tickets", {}).get("count", 0) for a in attempts),
            "ticket_sha256": sorted(
                {
                    cv.digest(str(t["id"]))
                    for a in attempts
                    for t in a.get("tickets", {}).get("rows", [])
                }
            ),
            "delivery_states": dict(
                Counter(
                    str(t.get("delivery_state"))
                    for a in attempts
                    for t in a.get("tickets", {}).get("rows", [])
                )
            ),
            "latency": latency(terminals),
            "infrastructure_attempts": sum(
                a["classification"] == "infrastructure" for a in attempts
            ),
            "pending": total - sum(r["status"] in d.TERMINAL for r in rows),
            "product_failures": sum(r["status"] == "product_failure" for r in rows),
            "counted_out": sum(r["status"] == "counted_out" for r in rows),
            "calls_by_effort": dict(efforts),
            "calls_per_question": {effort: count / total for effort, count in efforts.items()},
            "language_mismatches": sum(r.get("language", {}).get("match") is False for r in rows),
        }
    return {
        "per_key": per_key,
        "ollama_observations": sum(
            c.get("ollama_observations", 0) for c in state.get("chunks", [])
        ),
        "stop_reasons": [
            {"code": s["code"], "reason": s["reason"], "resolved": bool(s.get("resolved"))}
            for s in state.get("stops", [])
        ],
    }


def clusters(config, packages, old, repo):
    c, _ = f.modules(repo)
    exporter = c.instruments().common.final.frozen("export")
    result = {}
    for key in cv.KEYS:
        if key == "aircargo":
            result[key] = {r["case_id"]: [key + ":case:" + r["case_id"]] for r in packages[key]}
            continue
        cases = d.table(cv.rows(Path(config["private_data_root"]) / key / "cases.jsonl"))
        # reference_rows uses external_parts' frozen clustering via external_pilot;
        # the recomputation must equal the historical cluster and stratum labels.
        refs = exporter.reference_rows(key, [cases[r["case_id"]] for r in packages[key]])
        cv.require(
            all(
                all(row[name] == old[key][row["case_id"]][name] for name in ("cluster", "stratum"))
                for row in refs
            ),
            "external cluster/stratum differs",
        )
        result[key] = {row["case_id"]: [f"{key}:cluster:{row['cluster']}"] for row in refs}
    return result


def build(args, repo=d.ROOT):
    series, records = args.private / args.series, args.records / args.series
    c, _ = f.modules(repo)
    state, old, new, measured, plans = {}, {}, {}, {}, {}
    refusals, stopped, numbers, identity = [], False, {}, None
    inputs = {}
    stage = "state"
    try:
        state = cv.read(series / "state.json")
        stopped = bool(f.active_stops(state) or c.judge_stops(series))
    except (Exception, SystemExit):
        refusals.append("state missing or unreadable")
    try:
        stage = "registration and copy admission"
        config, registration = d.admit_chunk(
            SimpleNamespace(**{**vars(args), "budget": 600}), repo, offline=True
        )
        cv.require(
            state.get("registration_sha256") == cv.digest(cv.encoded(registration)),
            "state registration differs",
        )
        inputs["registration_sha256"] = cv.sha(records / "registration.json")
        packages, ids = d.load_packages(repo, config)
        verdicts = d.bind_attempt02(repo, config, packages)
        old = {key: d.table(verdicts[key]) for key in cv.KEYS}
        stage = "Q baseline and R instrument gate"
        baseline, gate = d.q_baseline(verdicts, ids), d.r_gate(repo, config, packages)
        match_baselines(registration, baseline, gate)
        cv.require(
            state.get("pilot_passed") and state.get("pilot_step") == 20, "all-20 pilot incomplete"
        )
        groups = clusters(config, packages, old, repo)
        stage = "judge route receipt"
        route = f.saved_route(
            series, records, cv.sha(Path(config["artifacts"]["claude_executable"])), c.judge()
        )
        if route["passed"] is not True:
            stopped = True
            refusals.append("judge route refused")
        inputs["judge_route_sha256"] = cv.sha(records / "judge-route.json")
        r_old, r_new, parsed = {}, {}, {}
        sent_gold = d.canonical_import(repo, "sent_gold", "reports/stage4-final/tools/external")
        for key in cv.KEYS:
            stage = key + ": whole key and frozen receipt"
            rows = {r["case_id"]: r for r in state["cases"].values() if r["key"] == key}
            cv.require(
                set(rows) == set(ids[key])
                and all(r["status"] in d.TERMINAL for r in rows.values()),
                "key not whole",
            )
            key_args = SimpleNamespace(**{**vars(args), "key": key})
            _, _, pin = f.admitted(key_args, repo)
            inputs[key] = {
                "receipt_sha256": cv.sha(records / f"plans-{key}.json"),
                "plans": pin["plans"],
            }
            work = series / key
            measured[key] = cv.read(work / "measurement.json")
            cv.require(
                all(measured[key][cid]["class"] == rows[cid]["status"] for cid in ids[key]),
                "frozen case status differs",
            )
            plans[key] = {}
            for metric in f.METRICS:
                stage = key + ": " + metric + " export"
                result, data = f.exports(key, series, pin, metric, repo)
                public = records / f"codex-only-{key}-judge-{metric}.json"
                cv.require(cv.read(public) == result, "public export differs from journal")
                inputs[key][metric + "_export_sha256"] = cv.sha(public)
                if data is not None:
                    cv.require(
                        cv.rows(public.with_suffix(".cases.jsonl")) == data,
                        "public case export differs from journal",
                    )
                    inputs[key][metric + "_cases_sha256"] = cv.sha(
                        public.with_suffix(".cases.jsonl")
                    )
                plans[key][metric] = {
                    "status": result["status"],
                    "retest": result["retest"],
                    "missing": result.get("missing", []),
                    "requests": pin["requests"][metric],
                }
                inputs[key][metric + "_verdicts_sha256"] = cv.sha(work / metric / "verdicts.jsonl")
                if (
                    result["status"] != "counted"
                    or result.get("missing")
                    or (data and any(r["missing"] for r in data))
                ):
                    refusals.append(key + ": " + metric + " missing or unstable")
                    stopped = True
                if metric == "m1":
                    new[key] = d.table(data, ids[key])
            parsed[key] = d.table(
                [
                    row
                    for batch in range(1, 11)
                    for row in c.judge().run_answers(
                        work / "runs" / f"final-answers-{key}-b{batch:02d}"
                    )
                ],
                ids[key],
            )
            if key in cv.KEYS[:2]:
                stage = key + ": product sent context"
                reader = sent_gold.SentGold(key, Path(config["private_data_root"]))
                r_old[key] = {
                    r["case_id"]: {
                        name: r[name] for name in ("gold", "hit", "fraction", "prompt_sha256")
                    }
                    for r in gate["keys"][key]["cases"]
                }
                r_new[key] = {
                    cid: {
                        **sent_point(reader, cid, parsed[key][cid]["documents"], r_old[key][cid]),
                        "prompt_sha256": parsed[key][cid]["prompt_sha256"],
                        "derived": measured[key][cid]["derived"],
                    }
                    for cid in ids[key]
                }
        stage = "paired Q/R reading"
        numbers = analyze(old, new, measured, r_old, r_new, groups, repo)
        comparison = []
        for package in packages["aircargo"]:
            cid = package["case_id"]
            before = {source for source, _ in package["documents"]}
            after = {source for source, _ in parsed["aircargo"][cid]["documents"]}
            comparison.append(
                {
                    "case_id": cid,
                    "same": before == after,
                    "baseline_sources_sha256": sorted(cv.digest(s) for s in before),
                    "product_sources_sha256": sorted(cv.digest(s) for s in after),
                }
            )
        identity = {"same": sum(r["same"] for r in comparison), "n": 100, "cases": comparison}
    except (Exception, SystemExit) as error:
        # Never expose exception text: historical parsers can include private prose.
        refusals.append(stage + " refused: " + type(error).__name__)
    try:
        observed = diagnostics(state, old, new)
    except (Exception, SystemExit):
        refusals.append("state diagnostics malformed")
        observed = {"status": "unavailable"}
    result = {
        "schema": "codex-quality-reading/1",
        "series": args.series,
        **numbers,
        "decision": decision(
            numbers.get("q", {}).get("pooled"),
            numbers.get("r", {}).get("pooled"),
            refusals,
            stopped,
        ),
        "diagnostics": observed,
        "plans": plans,
        "aircargo_document_identity": identity,
        "input_sha256": inputs,
        "limits": [
            "In-sample; one unseeded generation per side; one judge; no human grades (D11).",
            "Contexts, release, Windows numerics and exec framing change together; no isolated auxiliary causal effect.",
            "M2 absent; laptop under owner load; no detected fall does not establish equivalence.",
        ],
    }
    c.public(records / "reading.json", result)
    return result


def parser():
    result = cv.Parser(description=__doc__)
    for name in ("config", "private", "records"):
        result.add_argument("--" + name, type=Path, required=True)
    result.add_argument("--series", required=True)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        cv.require(re.fullmatch(r"[A-Za-z0-9_-]+", args.series), "invalid series")
        cv.require(
            args.records.resolve().is_relative_to(
                (d.ROOT / "reports/codex-only-quality").resolve()
            ),
            "invalid public path",
        )
        c, _ = f.modules(d.ROOT)
        with (
            c.serial_lock(args.private),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = build(args)
    except (Exception, SystemExit):
        print("NOT_EVIDENCE: invalid arguments or unavailable output/instruments")
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result["decision"]["row"] == 1 and result["decision"]["stop_fired"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
