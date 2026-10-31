"""Stage 5: pooled M1 is decisive; external sent-M3 is deterministic; MultiHop is advisory."""

import argparse
from pathlib import Path

from execute import series_gate
from grading import admitted
from prepare import check_receipt
from protocol import (
    BASES,
    GOLD_N,
    OLD,
    PRIMARY,
    SPEC,
    batch_hashes,
    frozen,
    judge_record,
    outside,
    product_diff,
    public_write,
    read,
    require,
    runs_gate,
    sha,
    table,
)
from record import answers, paired
from sent_gold import measure


def outcome(primary):
    if primary.get("status") == "NOT_EVIDENCE":
        return {"outcome": "NOT_EVIDENCE", "action": "no package decision"}
    direction = primary["bad"]["direction"]
    return {
        "outcome": {"rises": "harm detected", "falls": "gain detected", "not detected": "holds"}[
            direction
        ],
        "action": "Julia: one yes/no; package stays in code meanwhile"
        if direction == "rises"
        else "publish the package's numbers",
    }


def m3_read(base, old, new, families):
    require(set(old) == set(new), "M3 pair ids differ")
    require(all(old[i]["gold"] == new[i]["gold"] for i in old), "M3 gold membership differs")
    ids = [i for i in old if old[i]["gold"]]
    require(len(ids) == GOLD_N[base], "M3 gold denominator differs")
    require(all(old[i]["hit"] in (0, 1) and new[i]["hit"] in (0, 1) for i in ids), "M3 missing")
    hits = sum(old[i]["hit"] for i in ids)
    require(hits < len(ids), "old M3 ceiling differs from registration")
    readout = paired(
        {i: old[i]["hit"] for i in ids},
        {i: new[i]["hit"] for i in ids},
        {i: families[i] for i in ids},
    )
    return {
        "status": "counted",
        "old_hits": hits,
        "old_n": len(ids),
        "old_ceiling": False,
        "without_gold": len(old) - len(ids),
        "sent": readout,
        "reading": "harm detected"
        if readout["direction"] == "falls"
        else "gain detected"
        if readout["direction"] == "rises"
        else "holds",
        "fraction_mean": {
            side: sum(rows[i]["fraction"] for i in ids) / len(ids)
            for side, rows in (("old", old), ("new", new))
        },
    }


def bridge_gate(bridge, old, expected_plan):
    require(bridge["plan_sha256"] == expected_plan, "bridge export is not the frozen plan")
    require(
        bridge["source_plan_sha256"] == old["provenance"]["plan_sha256"]
        and bridge["source_verdicts_sha256"] == old["provenance"]["verdicts_sha256"],
        "bridge is not the historical plan and replies",
    )
    require(bridge["status"] == "counted" and bridge["retest"]["passed"], "bridge stability failed")


def compare(base, a, b, gold_old, gold_new):
    ids = list(a)
    require(set(a) == set(b), "M1 pair ids differ")
    require(
        all(a[i]["cluster"] == b[i]["cluster"] and a[i]["stratum"] == b[i]["stratum"] for i in ids),
        "clusters or strata differ",
    )
    require(
        all(
            (type(row.get("context_has_answer")) is bool or row.get("empty_answer") is True)
            for i in ids
            for row in (a[i], b[i])
        ),
        "judge context field missing",
    )
    families = {i: [f"{base}:{a[i]['cluster']}"] for i in ids}
    out = {"status": "counted", "advisory": base == "multihoprag"}
    for grade in ("bad", "good"):
        out[grade] = paired(
            {i: int(a[i]["grade"] == grade) for i in ids},
            {i: int(b[i]["grade"] == grade) for i in ids},
            families,
        )
    context_pairs = [(a[i].get("context_has_answer"), b[i].get("context_has_answer")) for i in ids]
    out["context_has_answer"] = {
        "same": context_pairs.count((True, True)) + context_pairs.count((False, False)),
        "lost": context_pairs.count((True, False)),
        "gained": context_pairs.count((False, True)),
    }
    out["empty_answers"] = sum(b[i].get("empty_answer") is True for i in ids)
    out["m3"] = m3_read(base, gold_old, gold_new, families)
    return out


def pooled(tables):
    if not all(b in tables for b in PRIMARY):
        return {"status": "NOT_EVIDENCE", "keys": list(PRIMARY)}
    old, new, families = {}, {}, {}
    for base in PRIMARY:
        a, b = tables[base]
        require(set(a) == set(b) and len(a) == 100, "pooled rule needs 100 pairs per base")
        for ident in a:
            tag = f"{base}:{ident}"
            old[tag], new[tag] = int(a[ident]["grade"] == "bad"), int(b[ident]["grade"] == "bad")
            families[tag] = [f"{base}:{a[ident]['cluster']}"]
    return {"status": "counted", "keys": list(PRIMARY), "bad": paired(old, new, families)}


def m2_read(base, record, new, old, admitted_base):
    if base == "multihoprag":
        require(old is None, "MultiHop M2 has no admitted old side")
        return {"status": "counted", "paired": False, "advisory": True, "new": record["m2"]}
    if not admitted_base:
        return {
            "status": "NOT_EVIDENCE",
            "reason": "base paired reading not admitted",
            "new": record["m2"],
        }
    require(
        set(old) == set(new) and all(old[i]["cluster"] == new[i]["cluster"] for i in old),
        "M2 clusters or ids differ",
    )
    return {
        "status": "counted",
        "paired": True,
        **frozen("v4").reference(
            base,
            old,
            new,
            {i: [f"{base}:{old[i]['cluster']}"] for i in old},
        ),
    }


def read_base(config, base, held, private, runs, baseline, receipt, exports, change):
    pin = admitted(receipt, private, baseline, base)
    require(batch_hashes(runs, base) == pin["answer_files"], "answers changed since plan freeze")
    data = Path(config["data"])
    measured = {base: answers(runs, base, data)}
    series = series_gate(runs, baseline, measured[base], base)
    require(series == pin["completion"], "completion differs from receipt")
    require(
        series["product_diff"] == change and series["code_sha"] == change["stage5_sha"],
        "registration comparison differs",
    )
    pair, hashes = None, {}
    old = held["bases"][base]
    ids = old["ids"]
    prompts = {r["case_id"]: r["prompts"][0]["sha256"] for r in measured[base]["cases"]}
    gold = table(measure(base, data, runs, measured[base]["cases"]), ids)
    new_paths = {m: exports / f"stage5-{base}-{m}.json" for m in ("m1", "m2", "bridge")}
    for path in new_paths.values():
        require(path.exists(), "all exported plans required")
        hashes[path.name] = sha(path)
        if path.with_suffix(".cases.jsonl").exists():
            hashes[path.with_suffix(".cases.jsonl").name] = sha(path.with_suffix(".cases.jsonl"))
    old_record, a = judge_record(
        Path(config["bases"][base]["m1"]), base, "m1", ids, old["references_sha256"], OLD[base]
    )
    try:
        rec, b = judge_record(
            new_paths["m1"],
            base,
            "m1",
            ids,
            old["references_sha256"],
            series["code_sha"],
            prompts,
        )
        require(
            rec["provenance"]["plan_sha256"] == pin["plans"][f"{base}-m1"],
            "M1 export plan differs",
        )
        require(
            sum(r.get("empty_answer") is True for r in b.values()) == pin["empty_answers"],
            "M1 export empty count differs",
        )
        bridge_gate(read(new_paths["bridge"]), old_record, pin["plans"][f"{base}-bridge"])
        result = compare(base, a, b, table(old["old_m3"], ids), gold)
        pair = (a, b)
    except SystemExit as error:
        result = {
            "status": "NOT_EVIDENCE",
            "reason": str(error),
            "advisory": base == "multihoprag",
        }
    try:
        rec, b2 = judge_record(
            new_paths["m2"],
            base,
            "m2",
            ids,
            old["references_sha256"],
            series["code_sha"],
            prompts,
        )
        require(
            rec["provenance"]["plan_sha256"] == pin["plans"][f"{base}-m2"],
            "M2 export plan differs",
        )
        require(
            sum(r.get("empty_answer") is True for r in b2.values()) == pin["empty_answers"],
            "M2 export empty count differs",
        )
        a2 = None
        if base in PRIMARY and result["status"] == "counted":
            _, a2 = judge_record(
                Path(config["bases"][base]["m2"]),
                base,
                "m2",
                ids,
                old["references_sha256"],
                OLD[base],
            )
        result["m2"] = m2_read(base, rec, b2, a2, result["status"] == "counted")
    except SystemExit as error:
        result["m2"] = {"status": "NOT_EVIDENCE", "reason": str(error)}
    result["sent_cases"] = list(gold.values())
    result["answers"] = measured[base]
    result["empty_answers"] = pin["empty_answers"]
    return result, pair, hashes


def build(config, private, runs, baseline, receipts, exports, source, stage5_sha):
    private, runs = outside(private), outside(runs)
    runs_gate(runs)
    held = check_receipt(baseline, config, private)
    change = product_diff(source, config["item6_sha"], stage5_sha)
    require(held["item6_sha"] == config["item6_sha"], "baseline registration differs")
    corpora, tables, hashes, receipt_hashes, absent = {}, {}, {}, {}, []
    for base in BASES:
        receipt = receipts / f"plans-{base}.json"
        if not receipt.is_file():
            absent.append(base)
            corpora[base] = {
                "status": "NOT_EVIDENCE",
                "reason": "base receipt absent",
                "advisory": base == "multihoprag",
            }
            continue
        try:
            result, pair, exported = read_base(
                config, base, held, private, runs, baseline, receipt, exports, change
            )
            receipt_hashes[base] = sha(receipt)
            hashes.update(exported)
            corpora[base] = result
            if pair is not None:
                tables[base] = pair
        except (SystemExit, OSError, ValueError, KeyError) as error:
            corpora[base] = {
                "status": "NOT_EVIDENCE",
                "advisory": base == "multihoprag",
                "reason": str(error) if isinstance(error, SystemExit) else type(error).__name__,
            }
    primary = pooled(tables)
    return {
        "spec": SPEC,
        "status": primary["status"],
        "corpora": corpora,
        "primary": primary,
        "decision": outcome(primary),
        "product_diff": change,
        "absent_bases": absent,
        "baseline_sha256": sha(baseline),
        "receipts_sha256": receipt_hashes,
        "exports_sha256": hashes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "private", "runs", "baseline", "receipts", "exports", "source", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--stage5-sha", required=True)
    args = parser.parse_args()
    config = read(outside(args.config))
    result = build(
        config,
        args.private,
        args.runs,
        args.baseline,
        args.receipts,
        args.exports,
        args.source,
        args.stage5_sha,
    )
    require(not args.out.exists(), "record exists")
    public_write(args.out, result, Path(config["data"]))
    print(result["decision"])


if __name__ == "__main__":
    main()
