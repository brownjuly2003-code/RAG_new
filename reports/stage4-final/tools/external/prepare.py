"""Private-input preflight and text-free old-side receipt, before any stage-5 request."""

import argparse
import json
import re
from pathlib import Path

from protocol import (
    BASES,
    GOLD_N,
    OLD,
    PRIMARY,
    ROOT,
    SPEC,
    committed,
    forecast,
    frozen,
    judge_record,
    outside,
    pin_public,
    positive,
    private_hashes,
    public_write,
    questions,
    read,
    require,
    rows,
    runs_gate,
    sha,
    table,
)
from sent_gold import measure, stage2_gate

STAGE7_FILES = {
    "reports/stage7/5e308fe/rows.jsonl": "2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627",
    "reports/stage7/5e308fe/record.json": "b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4",
}


def stage7_inputs():
    pins = {}
    for name, digest in STAGE7_FILES.items():
        path = ROOT / name
        require(sha(path) == digest, "stage7 old-side file hash differs")
        pins.update(pin_public(path))
    return pins, rows(ROOT / "reports/stage7/5e308fe/rows.jsonl")


def stage7_gate(base, points):
    """Match the parity-checked H_old, never substitute H_new or the judge's context field."""
    require(base in PRIMARY, "stage7 gate is for the V4 primary bases")
    pins, archived = stage7_inputs()
    selected = [r for r in archived if r["base"] == base or r["label"] == "p2-" + base]
    require(
        all(r["base"] == base and r["label"] == "p2-" + base for r in selected),
        "stage7 old-side label differs",
    )
    held = table(selected, [r["case_id"] for r in points])
    hit, fraction = (
        ("gold_article", "gold_articles")
        if base == "wixqa"
        else ("all_evidence_coverage", "evidence_recall")
    )
    for point in points:
        row = held[point["case_id"]]
        old = row["H_old"]
        require(
            old["prompt"]["sha256"] == point["prompt_sha256"] and row["gold"] is point["gold"],
            "stage7 old-side prompt or gold differs",
        )
        if point["gold"]:
            sent = old["points"]["sent"]
            require(
                sent[hit] == point["hit"]
                and round(sent[fraction], 6) == round(point["fraction"], 6),
                "stage7 old-side reading differs",
            )
        else:
            require(point["hit"] is None and point["fraction"] is None, "gold-free reading differs")
    return pins


def data_layout(folder, manifest):
    """The cleaned laptop copy contains only the registered measurement files."""
    allowed = {
        "corpus.manifest.json",
        "chunks-report.json",
        "chunks.json.gz",
        "cases.jsonl",
        "index/index-receipt.json",
        *("corpus/" + entry["name"] for entry in manifest["files"]),
    }
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    require(actual == allowed, "private data layout differs (missing or extra file)")


def historical(config, base, ids, data):
    from run import corpus

    path = Path(config["answers"])
    pins = {**pin_public(path), **pin_public(path.with_suffix(".cases.jsonl"))}
    record = read(path)
    cases = rows(path.with_suffix(".cases.jsonl"))
    found = table(cases, ids)
    require([r["case_id"] for r in cases] == ids, "historical answer order differs")
    require(record["base"] == base, "historical base differs")
    cases_file, _ = questions(base, data)
    require(
        record["provenance"]["cases_file_sha256"] == sha(cases_file)
        and record["provenance"]["source_sha256"] == corpus(base, data),
        "historical generation differs",
    )
    counted = [r for r in record["runs"] if r["counted"]]
    require(
        len(counted) == 10
        and all(
            r["launch"]["status"] == "complete" and r["launch"]["code_sha"].startswith(OLD[base])
            for r in counted
        ),
        "historical stand incomplete or different",
    )
    for row in cases:
        require(
            row["answered"]
            and not row["path_breaks"]
            and not row.get("drain_error")
            and not row.get("client_error"),
            "historical path broke",
        )
        require(
            all(positive(row.get(k)) for k in ("result_sec", "total_sec", "first_token_sec")),
            "historical timings missing",
        )
        require(
            row["first_token_sec"] <= row["result_sec"] <= row["total_sec"] < 3600,
            "historical timing order",
        )
    frozen("cases")
    from stage2_common import spread

    times = {
        k: spread([r[k] for r in found.values()])
        for k in ("result_sec", "total_sec", "first_token_sec")
    }
    return cases, pins, times


def references(base, data, path, ids):
    cases_file, _ = questions(base, data)
    cases = {r["case_id"]: r for r in rows(cases_file)}
    made = frozen("export").reference_rows(base, [cases[i] for i in ids])
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in made).encode("utf-8")
    path = outside(path)
    require(path.is_file() and path.read_bytes() == payload, "references missing or changed")
    return sha(path)


def input_files(config):
    """Presence and hash preflight, before the M3 reconstruction; no writes or index needed."""
    from run import corpus

    from scripts import external_base

    require(set(config["bases"]) == set(BASES), "three historical bases required")
    require(re.fullmatch(r"[0-9a-f]{40}", config.get("item6_sha", "")), "full item6_sha required")
    data = outside(config["data"])
    pins, _ = stage7_inputs()
    inventory = {}
    for base in BASES:
        c = config["bases"][base]
        cases_file, ids = questions(base, data)
        corpus(base, data)
        manifest, _ = external_base._corpus(data / base)  # Checks every corpus file's hash.
        data_layout(data / base, manifest)
        refs = references(base, data, Path(c["references"]), ids)
        required = {"m1", "m2", "bridge"} if base in PRIMARY else {"m1", "m2"}
        require(set(c["plans"]) == required, "historical plan layout differs")
        require(outside(c["source"]) == outside(c["plans"]["m1"]), "bridge source is not old M1")
        judges = {}
        for metric in sorted(required):
            exported = Path(c[metric])
            pins.update(pin_public(exported))
            pins.update(pin_public(exported.with_suffix(".cases.jsonl")))
            provenance = read(exported)["provenance"]
            folder = outside(c["plans"][metric])
            hashes = {name: sha(folder / name) for name in ("plan.json", "verdicts.jsonl")}
            require(
                hashes["plan.json"] == provenance["plan_sha256"]
                and hashes["verdicts.jsonl"] == provenance["verdicts_sha256"],
                "historical private plan/replies differ",
            )
            if metric != "bridge":
                require(
                    provenance["references_sha256"] == refs, "historical reference hash differs"
                )
            judges[metric] = hashes
        published = Path(c["answers"])
        for p in (published, published.with_suffix(".cases.jsonl")):
            pins.update(pin_public(p))
        cases = rows(published.with_suffix(".cases.jsonl"))
        table(cases, ids)
        runs = outside(c["runs"])
        runs_gate(runs)
        labels = list(dict.fromkeys(r["run"] for r in cases))
        prefix = "v4" if base in PRIMARY else "p4"
        require(
            labels == [f"{prefix}-{base}-b{n:02d}" for n in range(1, 11)],
            "historical batch layout differs",
        )
        archives = {}
        from scripts import chat_answer_judge as answer

        for label in labels:
            folder = runs / label
            launch = read(folder / "launch.json")
            require(
                launch["status"] == "complete"
                and launch["code_sha"].startswith(OLD[base])
                and launch["tenant"] == "ext_" + base,
                "historical launch differs",
            )
            expected = {r["case_id"]: r for r in cases if r["run"] == label}
            actual = table(answer.run_answers(folder), list(expected))
            for ident, row in expected.items():
                require(
                    len(row["prompts"]) == 1
                    and actual[ident]["prompt_sha256"] == row["prompts"][0]["sha256"],
                    "historical saved prompt hash differs",
                )
            archives[label] = private_hashes(folder)
        inventory[base] = {
            "runs": archives,
            "plans": judges,
            "cases_sha256": sha(cases_file),
            "references_sha256": refs,
        }
    gate = config["stage2"]
    for p in (
        Path(gate["export"]),
        Path(gate["export"]).with_suffix(".cases.jsonl"),
        Path(gate["combined"]),
    ):
        pins.update(pin_public(p))
    p2 = outside(gate["run"])
    require(
        (p2 / "effective_settings.json").is_file()
        and bool(list((p2 / "retrieval").glob("*.json"))),
        "stage2 retrieval inputs missing",
    )
    inventory["p2-multihoprag"] = private_hashes(p2)
    return pins, inventory


def source_gate(source, old):
    from scripts import chat_answer_judge as answer

    source = outside(source)
    p = old["provenance"]
    hashes = {
        k: sha(source / (k + suffix)) for k, suffix in (("plan", ".json"), ("verdicts", ".jsonl"))
    }
    require(all(hashes[k] == p[k + "_sha256"] for k in hashes), "historical bridge inputs differ")
    plan = read(source / "plan.json")
    answer.check_plan(plan)
    copies = [r for r in plan["items"] if "retest_of" in r]
    valid = answer._vouched(plan, rows(source / "verdicts.jsonl"))
    require(
        len(copies) == 15 and all(r["retest_of"] in valid for r in copies),
        "15 admitted bridge originals required",
    )
    return hashes


def inputs(config, private):
    from run import corpus

    # The first operation checks the existing private inputs and committed hash sources.
    pins, inventory = input_files(config)
    outside(private)
    data = outside(config["data"])
    require(set(config["bases"]) == set(BASES), "three historical bases required")
    prepared = {}
    # The p2 parity gate precedes any V4 or new-context reading.
    _, multi_ids = questions("multihoprag", data)
    multi_cases, _, _ = historical(config["bases"]["multihoprag"], "multihoprag", multi_ids, data)
    gate = config["stage2"]
    old_multi = stage2_gate(
        data, outside(gate["run"]), Path(gate["export"]), Path(gate["combined"]), multi_cases
    )
    for p in (
        Path(gate["export"]),
        Path(gate["export"]).with_suffix(".cases.jsonl"),
        Path(gate["combined"]),
    ):
        pins.update(pin_public(p))
    for base in BASES:
        c = config["bases"][base]
        cases_file, ids = questions(base, data)
        refs = references(base, data, Path(c["references"]), ids)
        cases, hashes, times = historical(c, base, ids, data)
        pins.update(hashes)
        prompts = {r["case_id"]: r["prompts"][0]["sha256"] for r in cases}
        judges = {}
        for metric in ("m1", "m2") if base in PRIMARY else ("m1",):
            path = Path(c[metric])
            for p in (path, path.with_suffix(".cases.jsonl")):
                pins.update(pin_public(p))
            judges[metric], _ = judge_record(path, base, metric, ids, refs, OLD[base], prompts)
        bridge = source_gate(c["source"], judges["m1"])
        m3 = (
            old_multi
            if base == "multihoprag"
            else measure(base, data, outside(c["runs"]), cases, historical=True)
        )
        if base in PRIMARY:
            pins.update(stage7_gate(base, m3))
        require(sum(r["gold"] for r in m3) == GOLD_N[base], "gold denominator differs")
        old_hits = sum(r["hit"] or 0 for r in m3)
        require(old_hits < GOLD_N[base], "old M3 at a ceiling: amend reading before running")
        prepared[base] = {
            "ids": ids,
            "cases_sha256": sha(cases_file),
            "corpus": corpus(base, data),
            "references_sha256": refs,
            "old_code": OLD[base],
            "old_m3": m3,
            "old_m3_hits": old_hits,
            "old_m3_n": GOLD_N[base],
            "old_m3_ceiling": False,
            "times": times,
            "forecast": forecast(times["total_sec"]),
            "bridge_source": bridge,
            "old_judges": {
                k: {
                    name: v["provenance"][name]
                    for name in (
                        "plan_sha256",
                        "verdicts_sha256",
                        "references_sha256",
                        "references_withheld",
                        "prompt_id",
                        "route",
                        "salt",
                        "instructions_sha256",
                    )
                }
                for k, v in judges.items()
            },
            "archive_inputs": inventory[base],
        }
    # Do not emit private path strings; published source paths alone identify the old records.
    return {
        "spec": SPEC,
        "status": "counted",
        "item6_sha": config["item6_sha"],
        "order": list(BASES),
        "inputs": pins,
        "private_inputs": inventory,
        "bases": prepared,
    }


def check_receipt(receipt, config, private):
    committed(receipt)
    got = inputs(config, private)
    require(read(receipt) == got, "baseline receipt differs from checked inputs")
    return got


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = read(outside(args.config))
    result = inputs(config, args.private)
    if args.out.exists():
        require(read(args.out) == result, "existing preflight receipt differs")
    else:
        public_write(args.out, result, Path(config["data"]))
    print(
        json.dumps(
            {
                b: {
                    k: result["bases"][b][k]
                    for k in ("times", "forecast", "old_m3_hits", "old_m3_n")
                }
                for b in BASES
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
