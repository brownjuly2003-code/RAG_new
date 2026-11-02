"""Read V6 against the package, including early harm; never sends a request."""

import argparse
from pathlib import Path

from v6_common import (
    BASES,
    KEYS,
    ROOT,
    STANDS,
    plan_name,
    public,
    read,
    require,
    rows,
    sha,
    tool_hashes,
    unique,
    v5_record,
)
from v6_judge import admitted, export_gate, old_export, run_hashes, shown_gate, summary_gate

v4 = v5_record.v4r


def renamed(value):
    """V5's frozen reader uses historical side names; only the labels change."""
    if isinstance(value, dict):
        return {({"v4": "package", "v5": "v6"}.get(k, k)): renamed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [renamed(v) for v in value]
    return value


def decision(primary, recall, corpora, keys, readable, not_counted):
    missing = {k: list(v) for k, v in not_counted.items()}
    if set(primary["keys"]) != set(BASES):
        missing.setdefault("wixqa", []).append("incomplete primary pool")
    result = v5_record.decision(primary, recall, corpora, keys, readable, missing)
    result["v6_replaces_package"] = result.pop("v5_replaces_v4")
    return result


def counted(record, data=None):
    return (
        record.get("status") == "counted"
        and record["retest"]["passed"]
        and not record.get("missing")
        and (data is None or all(v4.graded(r) for r in data.values()))
    )


def compare(key, old, new, measured):
    """The exact V5 corpus reader, with V6 observations adapted to its input schema."""
    require(set(old) == set(new) == set(measured), "paired case set differs")
    if key in BASES:
        require(
            all(old[c][f] == new[c][f] for c in old for f in ("cluster", "stratum")),
            "paired clusters/strata differ",
        )
    pairs = sorted(c for c in old if v4.graded(old[c]) and v4.graded(new[c]))
    families = {
        c: [f"{key}:cluster:{r['cluster']}" if key in BASES else f"{key}:answer:{c}"]
        for c, r in old.items()
    }
    adapted = {}
    for case, r in measured.items():
        adapted[case] = {
            "same_context": r["same_context"],
            "quoted": {"v4": r["package_quoted"], "v5": r["v6_quoted"]},
            "truncated": False,
            "at_token_cap": {"v4": r["package_chunks"] >= 1024, "v5": r["chunks"] >= 1024},
            "stream_sec": {"v4": r["package_stream_sec"], "v5": r["v6_stream_sec"]},
            "chunks": {"v4": r["package_chunks"], "v5": r["chunks"]},
        }
    numbers, same = v5_record.corpus(
        key, pairs, {"m1": old}, {"m1": new, "answers": adapted}, families
    )
    from stage2_common import spread

    observed = list(measured.values())
    numbers["guards"] = {
        kind: sum(kind in r["flags"] for r in observed)
        for kind in ("parse", "repeat", "language", "language_after_release")
    }
    numbers["fallbacks"] = sum(r["fallback"] for r in observed)
    numbers["fallback_at_token_cap"] = sum((r["fallback_chunks"] or 0) >= 1024 for r in observed)
    for field in (
        "answer_chars",
        "package_answer_chars",
        "first_shown_sec",
        "full_buffer_sec",
        "v6_stream_sec",
        "package_stream_sec",
        "package_first_sec",
        "fallback_stream_sec",
        "total_sec",
    ):
        numbers[field] = spread([r[field] for r in observed if r[field] is not None])
    numbers["prefix_whole_disagreements"] = sum(r["prefix_whole_disagreement"] for r in observed)
    numbers["timing"] = {
        group: {
            field: spread([r[field] for r in subset if r[field] is not None])
            for field in (
                "first_shown_sec",
                "full_buffer_sec",
                "total_sec",
                "v6_stream_sec",
                "package_first_sec",
                "package_stream_sec",
            )
        }
        for group, subset in (
            ("all_batches", observed),
            ("clean_batches", [r for r in observed if r["idle_clean"]]),
        )
    }
    return numbers, pairs, same, families


def build(private, records, spec_path, keys=KEYS):
    require(bool(keys) and len(keys) == len(set(keys)) and set(keys) <= set(KEYS), "invalid keys")
    keys = [k for k in KEYS if k in keys]
    inputs, corpora, plans, not_counted, readable = {}, {}, {}, {}, []
    pooled, same, recall = ({}, {}, {}), ({}, {}, {}), ({}, {}, {})
    m2_counted = True

    def remember(path):
        path = Path(path)
        # Names in the record are repository-relative, never private folder names.
        inputs[path.resolve().relative_to(ROOT).as_posix()] = sha(path)
        return path

    for key in keys:
        folder = Path(records) / STANDS[key]
        receipt = remember(folder / f"plans-{key}.json")
        work = Path(private) / key / "judge"
        location = Path(private) / key / "run-location.json"
        runs = Path(read(location)["runs"]) if location.exists() else Path(private) / key / "runs"
        pin = admitted(key, work, receipt, spec_path)
        summary = read(remember(folder / f"v6-{key}.json"))
        measured = summary_gate(summary, key)
        require(
            sha(folder / f"v6-{key}.json") == pin["answer_files"][f"v6-{key}.json"],
            "public replay differs from receipt",
        )
        require(
            run_hashes(runs, key) == pin["answer_files"], "private replay changed since receipt"
        )
        from scripts import chat_answer_judge as judge

        for number in range(1, 11):
            batch = runs / f"v6-{key}-b{number:02d}"
            for entry in judge.run_answers(batch):
                shown_gate(batch, entry, measured[entry["case_id"]])
        ready = all((folder / (plan_name(key, m) + ".json")).exists() for m in ("m1", "bridge"))
        if not ready:
            not_counted.setdefault(key, []).append("M1/bridge exports absent")
            m2_counted = False
            continue
        loaded = {"package": {}, "v6": {}}
        for metric, held in pin["old"].items():
            old_path = remember(ROOT / held["path"])
            remember(old_path.with_suffix(".cases.jsonl"))
            old_record, old_data = old_export(old_path, key, metric)
            new_path = folder / (plan_name(key, metric) + ".json")
            if metric == "m2" and not new_path.exists():
                require(not new_path.with_suffix(".cases.jsonl").exists(), "partial M2 export")
                not_counted.setdefault(key, []).append("m2 absent")
                m2_counted = False
                continue
            remember(new_path)
            remember(new_path.with_suffix(".cases.jsonl"))
            new_record, new_data = (
                read(new_path),
                unique(rows(new_path.with_suffix(".cases.jsonl"))),
            )
            export_gate(key, metric, work, pin, new_record, new_data, measured)
            require(set(old_data) == set(new_data) == set(measured), "judge case set differs")
            require(
                all(
                    old_data[c]["prompt_sha256"] == measured[c]["package_prompt_sha256"]
                    for c in old_data
                ),
                "old prompt is not replayed prompt",
            )
            loaded["package"][metric] = (old_record, old_data)
            loaded["v6"][metric] = (new_record, new_data)
            for side, record, data in (
                ("package", old_record, old_data),
                ("v6", new_record, new_data),
            ):
                name = f"{side}-{key}-{metric}"
                plans[name] = v4.plan_summary(record)
                if not counted(record, data):
                    not_counted.setdefault(key, []).append(name)
        bridge = read(remember(folder / (plan_name(key, "bridge") + ".json")))
        export_gate(key, "bridge", work, pin, bridge)
        plans[plan_name(key, "bridge")] = bridge
        if not counted(bridge):
            not_counted.setdefault(key, []).append(plan_name(key, "bridge"))
        if counted(bridge) and all(counted(*loaded[s]["m1"]) for s in loaded):
            readable.append(key)
        a, b = loaded["package"]["m1"][1], loaded["v6"]["m1"][1]
        numbers, pairs, context, families = compare(key, a, b, measured)
        corpora[key] = numbers
        numbers["idle"] = summary["idle"]
        if key not in BASES:
            continue
        for into, cases in ((pooled, pairs), (same, context)):
            into[0].update(v4.indicator(key, cases, a, v4.is_bad))
            into[1].update(v4.indicator(key, cases, b, v4.is_bad))
            into[2].update({f"{key}:{c}": families[c] for c in cases})
        if "m2" not in loaded["v6"]:
            continue
        first, second = loaded["package"]["m2"][1], loaded["v6"]["m2"][1]
        require(
            all(
                first[c][f] == second[c][f] == a[c][f]
                for c in first
                for f in ("cluster", "stratum")
            ),
            "M2 clusters/strata differ",
        )
        numbers["m2"], held = v5_record.m2(key, first, second, families)
        m2_counted = m2_counted and all(counted(*loaded[s]["m2"]) for s in loaded)
        recall[0].update(v4.indicator(key, held, first, v5_record.agrees))
        recall[1].update(v4.indicator(key, held, second, v5_record.agrees))
        recall[2].update({f"{key}:{c}": families[c] for c in held})
    bases = [k for k in BASES if k in corpora]
    primary = {"keys": bases, **v5_record.pair(*pooled)}
    agreement = {"keys": bases, **v5_record.pair(*recall)}
    result = {
        "keys": keys,
        "stands": {k: STANDS[k] for k in keys},
        "inputs": inputs,
        "spec_sha256": sha(spec_path),
        "tools": tool_hashes(),
        "primary": primary,
        "same_context": {"keys": bases, **v5_record.pair(*same)},
        "recall": agreement,
        "corpora": corpora,
        "plans": plans,
        "decision": decision(
            primary,
            agreement if bases == list(BASES) and m2_counted else None,
            corpora,
            keys,
            readable,
            not_counted,
        ),
    }
    return renamed(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("private", "records", "spec", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--keys", default=",".join(KEYS))
    args = parser.parse_args()
    result = build(args.private, args.records, args.spec, args.keys.split(","))
    public(args.out, result)
    print(result["decision"])
    if result["decision"]["harm"]:
        raise SystemExit(2)  # The operator propagates STOP to the Mac chain immediately.


if __name__ == "__main__":
    main()
