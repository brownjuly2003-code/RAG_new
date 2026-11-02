"""Read the registered ceiling comparison; never sends a model request."""

import argparse
import contextlib
import copy
import io
from collections import Counter
from pathlib import Path

import ceiling_answer as arm
import ceiling_common as c
import ceiling_judge as grading


def renamed(value):
    if isinstance(value, dict):
        return {{"v4": "package", "v5": "codex"}.get(k, k): renamed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [renamed(v) for v in value]
    return value


def pair(first, second, families):
    return renamed(c.instruments().common.v5_record.pair(first, second, families))


def strata(old, stage5):
    result = {}
    for key in c.KEYS:
        c.require(len(old[key]) == 100, "package key incomplete")
        if key in c.BASES:
            sent = c.unique(stage5["corpora"][key]["sent_cases"])
            c.require(set(sent) == set(old[key]), "M3 ids differ")
            result[key] = {}
            for cid, row in sent.items():
                c.require(
                    row["prompt_sha256"] == old[key][cid]["prompt_sha256"], "M3 prompt differs"
                )
                c.require(
                    type(row["gold"]) is bool and (not row["gold"] or row["hit"] in (0, 1)),
                    "M3 labels invalid",
                )
                result[key][cid] = (
                    c.STRATA[0 if row["hit"] == 1 else 1] if row["gold"] else c.STRATA[2]
                )
        else:
            c.require(
                all(type(r.get("context_has_answer")) is bool for r in old[key].values()),
                "aircargo M3 missing",
            )
            result[key] = {
                cid: c.STRATA[0 if r["context_has_answer"] else 1] for cid, r in old[key].items()
            }
        counts = Counter(result[key].values())
        c.require(tuple(counts[s] for s in c.STRATA) == c.EXPECTED[key], "M3 stratum counts differ")
    return result


def families(key, rows):
    # The exports pin external_parts-derived reference clusters, not new clusters.
    return {
        cid: [f"{key}:cluster:{r['cluster']}" if key in c.BASES else f"{key}:case:{cid}"]
        for cid, r in rows.items()
    }


def comparison(key, ids, old, new, groups, predicate):
    return pair(
        {f"{key}:{cid}": int(predicate(old[cid])) for cid in ids},
        {f"{key}:{cid}": int(predicate(new[cid])) for cid in ids},
        {f"{key}:{cid}": groups[cid] for cid in ids},
    )


def primary(old, new, labels):
    before, after, clusters = {}, {}, {}
    for key in c.KEYS:
        groups = families(key, old[key])
        for cid, label in labels[key].items():
            if label == c.STRATA[0]:
                tag = arm.tag(key, cid)
                before[tag], after[tag] = (
                    int(old[key][cid]["grade"] == "good"),
                    int(new[key][cid]["grade"] == "good"),
                )
                clusters[tag] = groups[cid]
    c.require(len(before) == 224, "primary n differs from registered 224")
    return {"indicator": "good", **pair(before, after, clusters)}


def decision(primary_result, refusals, stopped):
    # V5/V6 adoption and harm gates are intentionally not this diagnosis's table.
    if refusals or stopped:
        return {
            "row": 1,
            "outcome": "NOT_EVIDENCE",
            "reasons": sorted(set(refusals)),
            "stop_fired": bool(stopped),
        }
    c.require(primary_result is not None and primary_result["n"] == 224, "primary unavailable")
    detected_rise = primary_result["detected"] and primary_result["direction"] == "rises"
    return {
        "row": 2 if detected_rise else 3,
        "outcome": "the generator is the bottleneck"
        if detected_rise
        else "the generator is not shown to be the bottleneck - retrieval next",
        "production_change": False,
        "stop_fired": False,
    }


def loss_accounting(old, new, labels):
    losses = {
        name: []
        for name in (
            "generator_losses",
            "retrieval_losses",
            "neither",
            "codex_good_without_gold_in_context",
        )
    }
    retained, lost = [], []
    for cid, row in old.items():
        good = new[cid]["grade"] == "good"
        if row["grade"] == "good":
            (retained if good else lost).append(cid)
        else:
            inside = labels[cid] == c.STRATA[0]
            name = (
                ("generator_losses" if good else "neither")
                if inside
                else ("codex_good_without_gold_in_context" if good else "retrieval_losses")
            )
            losses[name].append(cid)
    c.require(
        sum(map(len, losses.values())) == sum(r["grade"] != "good" for r in old.values()),
        "loss accounting does not partition",
    )
    return {
        "package_not_good": sum(map(len, losses.values())),
        **{name: {"n": len(ids), "ids": sorted(ids)} for name, ids in losses.items()},
        "retained_good": {"n": len(retained), "ids": sorted(retained)},
        "lost_good": {"n": len(lost), "ids": sorted(lost)},
    }


def diagnostics(rows):
    values = list(rows.values())
    v4 = c.instruments().common.v5_record.v4r
    # Empty answers carry no verdict; their claim contribution is zero.
    claims = v4.claims(
        [{k: r.get(k) or 0 for k in ("claims_supported", "claims_total")} for r in values]
    )
    return {
        "answers_question": dict(
            Counter(r.get("answers_question") or "ungraded_empty" for r in values)
        ),
        "claims": claims,
        "defects": dict(Counter(r.get("defect") or "empty_answer" for r in values)),
        "unsupported_claim_answers": sum(
            (r.get("claims_supported") or 0) < (r.get("claims_total") or 0) for r in values
        ),
        "unsupported_claims": claims["total"] - claims["supported"],
        "marks_listed": sum(r.get("marks_listed") or 0 for r in values),
        "marks_unlisted": sum(r.get("marks_unlisted") or 0 for r in values),
    }


def normalize_counted_out(new, measured):
    result = copy.deepcopy(new)
    c.require(set(result) == set(measured), "measurement ids differ")
    for cid, row in measured.items():
        c.require(row["status"] in arm.TERMINAL, "key not answered whole")
        if row["status"] == "counted_out":
            c.require(
                result[cid].get("empty_answer") is True and result[cid]["grade"] == "bad",
                "counted-out case must be an exported empty answer",
            )
            result[cid]["grade"] = "bad"
    return result


def analyze(old, new, old_m2, new_m2, stage5):
    labels = strata(old, stage5)
    for key in c.KEYS:
        c.require(set(old[key]) == set(new[key]), "paired ids differ")
        for cid, row in old[key].items():
            c.require(
                row["prompt_sha256"] == new[key][cid]["prompt_sha256"], "paired prompt differs"
            )
            if key in c.BASES:
                c.require(
                    all(row[f] == new[key][cid][f] for f in ("cluster", "stratum")),
                    "paired external clusters differ",
                )
    result = {"primary": primary(old, new, labels), "corpora": {}}
    v5 = c.instruments().common.v5_record
    recall = ({}, {}, {})
    for key in c.KEYS:
        first, second = old[key], new[key]
        groups = families(key, first)
        # Reuse the frozen corpus reader's grade/claim/transition aggregates.
        # Its stream-only fields have no 5v meaning and are not published.
        adapted = {
            cid: {
                "same_context": True,
                "quoted": dict.fromkeys(v5.SIDES, False),
                "truncated": False,
                "at_token_cap": dict.fromkeys(v5.SIDES, False),
                "stream_sec": dict.fromkeys(v5.SIDES, 0),
                "chunks": dict.fromkeys(v5.SIDES, 0),
            }
            for cid in first
        }
        safe = [
            {
                cid: {
                    **row,
                    "claims_supported": row.get("claims_supported") or 0,
                    "claims_total": row.get("claims_total") or 0,
                }
                for cid, row in side.items()
            }
            for side in (first, second)
        ]
        corpus, _ = v5.corpus(
            key, sorted(first), {"m1": safe[0]}, {"m1": safe[1], "answers": adapted}, groups
        )
        numbers = renamed({name: corpus[name] for name in ("pairs", "bad", "good", "transitions")})
        numbers["diagnostics"] = {"package": diagnostics(first), "codex": diagnostics(second)}
        numbers["strata"] = {}
        for label in c.STRATA:
            ids = sorted(cid for cid in first if labels[key][cid] == label)
            numbers["strata"][label] = {
                "n": len(ids),
                **{
                    name: comparison(key, ids, first, second, groups, test)
                    for name, test in (("good", v5.v4r.is_good), ("bad", v5.v4r.is_bad))
                },
            }
        numbers["losses"] = loss_accounting(first, second, labels[key])
        if key in c.BASES:
            a, b = old_m2[key], new_m2[key]
            c.require(set(a) == set(b) == set(first), "M2 paired ids differ")
            for cid in a:
                c.require(
                    a[cid]["prompt_sha256"]
                    == b[cid]["prompt_sha256"]
                    == first[cid]["prompt_sha256"],
                    "M2 prompt differs",
                )
                c.require(
                    all(a[cid][f] == b[cid][f] == first[cid][f] for f in ("cluster", "stratum")),
                    "M2 clusters differ",
                )
                c.require(
                    a[cid]["has_reference"] is (labels[key][cid] != c.STRATA[2]),
                    "M2 references and gold differ",
                )
            m2, held = v5.m2(key, a, b, groups)
            c.require(
                len(held) == (100 if key == "wixqa" else 80), "M2 reference-bearing count differs"
            )
            numbers["m2"] = renamed(m2)
            numbers["m2"]["strata"] = {
                label: comparison(
                    key, [cid for cid in held if labels[key][cid] == label], a, b, groups, v5.agrees
                )
                for label in c.STRATA
            }
            numbers["m2"]["unsupported_claim_defects"] = {
                "package": diagnostics(a),
                "codex": diagnostics(b),
            }
            for cid in held:
                tag = arm.tag(key, cid)
                recall[0][tag], recall[1][tag], recall[2][tag] = (
                    int(v5.agrees(a[cid])),
                    int(v5.agrees(b[cid])),
                    groups[cid],
                )
            if key == "conditionalqa":
                ids = [cid for cid in first if labels[key][cid] == c.STRATA[2]]
                numbers["right_declines"] = comparison(
                    key, ids, first, second, groups, v5.v4r.declined
                )
        result["corpora"][key] = numbers
    c.require(len(recall[0]) == 180, "pooled M2 n differs")
    result["m2"] = pair(*recall)
    return result


def build(series, records, spec=c.SPEC):
    series, records = Path(series), Path(records)
    refused, plans, inputs = [], {}, {}
    state = (
        c.read(series / "state.json") if (series / "state.json").is_file() else arm.initial(None)
    )
    stopped = bool(state["stops"] or c.judge_stops(series))
    result = {"arm": arm.route_numbers(state), "plans": plans, "input_sha256": inputs}
    old, new, old_m2, new_m2 = {}, {}, {}, {}
    try:
        inputs.update(c.public_inputs())
        c.require(
            state["spec_sha256"] == c.registration(spec) and state["pilot_passed"],
            "registration or pilot refused",
        )
        for key in c.KEYS:
            c.require(arm.summary(state, key)["whole"], "key not answered whole")
            pin = grading.admitted(key, series, records, spec)
            measured = c.read(series / key / "measurement.json")
            c.require(
                measured == {r["case_id"]: r for r in state["cases"].values() if r["key"] == key},
                "frozen measurement differs from state",
            )
            for metric in c.metrics(key):
                name = c.plan_name(key, metric)
                path = records / (name + ".json")
                exported, rows = grading.exports(key, series, pin, metric)
                c.require(c.read(path) == exported, "public export differs from journal")
                inputs[path.name] = c.sha(path)
                data = c.unique(rows) if rows is not None else None
                if data is not None:
                    c.require(
                        c.rows(path.with_suffix(".cases.jsonl")) == rows,
                        "public case export differs",
                    )
                    inputs[path.with_suffix(".cases.jsonl").name] = c.sha(
                        path.with_suffix(".cases.jsonl")
                    )
                plans[name] = {
                    k: exported[k] for k in ("status", "retest", "missing") if k in exported
                }
                c.require(
                    c.instruments().record.counted(exported, data),
                    "required plan or bridge not counted",
                )
                if metric != "bridge":
                    _, baseline = c.instruments().judge.old_export(
                        c.old_path(key, metric), key, metric
                    )
                    if metric == "m1":
                        old[key], new[key] = baseline, normalize_counted_out(data, measured)
                    else:
                        old_m2[key], new_m2[key] = baseline, data
        result.update(
            analyze(
                old,
                new,
                old_m2,
                new_m2,
                c.read(c.ROOT / "reports/stage4-final/stage5/2057ad0/record.json"),
            )
        )
    except (Exception, SystemExit) as exc:
        # Store diagnostics privately; public refusal contains no provider/data prose.
        import traceback

        series.mkdir(parents=True, exist_ok=True)
        (series / "reading-error.log").write_bytes(traceback.format_exc().encode("utf-8"))
        refused.append("evidence_refused:" + type(exc).__name__)
    result["decision"] = decision(result.get("primary"), refused, stopped)
    c.public(records / "reading.json", result)
    return result, 2 if result["decision"]["row"] == 1 and stopped else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--series", default="attempt-01")
    parser.add_argument("--records", type=Path, default=c.PUBLIC)
    parser.add_argument("--spec", type=Path, default=c.SPEC)
    args = parser.parse_args()
    c.output_path(args.records)
    series = c.series_path(args.private, args.series)
    with (
        c.serial_lock(args.private),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        result, code = build(series, args.records, args.spec)
    print(f"{code} {result['decision']['outcome']}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
