"""Summarize a completed 30-case parity run without loading models or rerunning it.

This validates saved records, not live HTTP latency or retrieval quality. The
registered source snapshot must remain unchanged while its model stages run.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from scripts.production_parity import (
    differences,
    digest,
    file_sha,
    load_stage,
    read,
    select_cases,
    write_new,
)


def build_report(run: Path) -> dict[str, Any]:
    manifest = read(run / "manifest.json")
    cases = manifest["cases"]
    if len(cases) != 30 or select_cases(cases, 30) != cases:
        raise ValueError("Expected 30 registered cases in selection order")
    identity = digest(manifest)
    comparison = read(run / "comparison.json")
    input_hashes = {
        name: file_sha(run / name) for name in ("manifest.json", "comparison.json")
    }
    counts = {key: {"order": 0, "membership": 0} for key in ("vector", "pool", "ranked")}
    query_counts = {key: 0 for key in (
        "query_effective", "query_transform", "query_transform_hash",
    )}
    context_matches = 0
    per_case = []
    divergences = {}
    for case in cases:
        records = {}
        for stage in ("grade", "verify"):
            name = f"{stage}/{case['case_id']}.json"
            records[stage] = load_stage(run / name, identity)
            input_hashes[name] = file_sha(run / name)
            for arm in ("chroma", "exact"):
                row = records[stage][arm]
                if row["case_id"] != case["case_id"] or row["query"] != case["query"]:
                    raise ValueError(f"Case identity mismatch: {name}/{arm}")
                context_hash = hashlib.sha256("\n\n".join(row["cands"]).encode()).hexdigest()
                if context_hash != row["sent_context_sha256"]:
                    raise ValueError(f"Context hash mismatch: {name}/{arm}")
        verified = records["verify"]
        for arm in ("chroma", "exact"):
            if differences(records["grade"][arm], verified[arm]):
                raise ValueError(f"Saved session replay mismatch: {case['case_id']}/{arm}")
        left, right = verified["chroma"], verified["exact"]
        diff = differences(left, right)
        if diff != verified["chroma_exact_differences"]:
            raise ValueError(f"Saved differences mismatch: {case['case_id']}")
        if diff:
            divergences[case["case_id"]] = diff
        for key, values in counts.items():
            values["order"] += left[key] != right[key]
            values["membership"] += set(left[key]) != set(right[key])
        for key in query_counts:
            query_counts[key] += left[key] != right[key]
        context_matches += left["sent_context_sha256"] == right["sent_context_sha256"]
        fields = ("vector", "pool", "ranked", *query_counts, "sent_context_sha256")
        per_case.append({
            "case_id": case["case_id"], "differences": diff,
            **{arm: {**{key: verified[arm][key] for key in fields},
                     "context_documents": len(verified[arm]["cands"])}
               for arm in ("chroma", "exact")},
        })
    expected = {
        "manifest_sha256": identity, "cases": 30, "session_replay_matches": 60,
        "divergences": divergences, "latency_evidence": False,
    }
    if comparison != expected:
        raise ValueError("Comparison summary does not match the saved records")
    return {
        "schema_version": 1, "manifest": manifest, "manifest_sha256": identity,
        "input_sha256": input_hashes, "cases": 30, "session_replay_matches": 60,
        "differences": counts, "query_differences": query_counts,
        "context_hash_matches": context_matches, "per_case": per_case,
        "latency_evidence": False,
        "limits": "Saved staged session replay; no live HTTP latency, answers or quality verdict.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    report = build_report(args.run)
    write_new(args.output, report)
    print(f"Saved {report['cases']} cases; context hashes match: {report['context_hash_matches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
