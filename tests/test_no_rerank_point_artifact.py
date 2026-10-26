"""The no-reranker point: the record read again from its rows and the committed stage-2 export
(docs/specs/no-rerank-point.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/no-rerank/tools/no_rerank_point.py"
RECORD = ROOT / "reports/no-rerank/5e308fe/record.json"
ROWS = ROOT / "reports/no-rerank/5e308fe/rows.jsonl"
CAPSULE = ROOT / "docs/evidence/no-rerank-point-record.md"
NAMES = {
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "multihoprag": "MultiHop-RAG",
    "aircargo": "aircargo",
}


def _load():
    spec = importlib.util.spec_from_file_location("no_rerank_point_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["no_rerank_point_artifact"] = module
    spec.loader.exec_module(module)
    return module


nr = _load()
record = json.loads(RECORD.read_text(encoding="utf-8"))
rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def test_every_number_of_the_record_is_read_again_from_its_rows():
    for base in nr.LABELS:
        own = [r for r in rows if r["base"] == base]
        assert _json(nr.summary(base, own)) == record["bases"][base]
    gold = [r for r in rows if "points" in r]
    pooled = nr.pairs(gold, not_evidence=False)
    assert _json(pooled) == record["pooled"]
    per_base = {b: record["bases"][b] for b in nr.METRICS}
    assert nr.verdict(per_base, record["pooled"]) == record["decision"]


def test_the_checks_passed_before_any_number():
    for base in nr.METRICS:
        summary = record["bases"][base]
        assert summary["unreproduced"] == 0, "the product's expansion gave other texts"
        assert summary["short_pool"] == 0
        assert summary["unresolved"] == {"None": summary["with_gold"]}
    assert {b: record["bases"][b]["with_gold"] for b in nr.METRICS} == {
        "wixqa": 100,
        "conditionalqa": 80,
        "multihoprag": 70,
    }
    assert all(record["bases"][b]["questions"] == 100 for b in nr.LABELS)


def test_the_recorded_points_overlap_and_seconds_are_the_committed_exports():
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    assert (
        record["inputs"]["export_manifest_sha256"]
        == hashlib.sha256((nr.EXPORT / "manifest.json").read_bytes()).hexdigest()
    )
    by_case = {r["case_id"]: r for r in rows}
    for label in nr.LABELS.values():
        for exported in nr.export_rows(label, manifest).values():
            row = by_case[exported["case_id"]]
            assert row["rerank_sec"] == exported["walls"]["rerank"]
            # The reranker keeps the highest scores, ties in the fused order (a stable sort).
            pool = exported["pool"]
            kept = sorted(range(len(pool)), key=lambda i: (-pool[i][2], i))[: nr.TOP]
            assert [pool[i][2] for i in kept] == exported["ranked_scores"]
            assert row["shared_of_five"] == len(set(kept) & set(range(nr.TOP)))
            if "points" in row:
                assert row["points"]["ranked"] == exported["points"]["ranked"]
                assert row["points"]["expanded_ranked"] == exported["points"]["expanded"]


def test_the_record_names_its_stand_tool_and_settings():
    assert record["spec"] == nr.SPEC
    assert record["stand_code_sha"] == nr.CODE_SHA
    assert record["tool_sha256"] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert set(record["measure_code_sha256"]) == set(nr.MEASURE_CODE)
    for base, provenance in record["provenance"].items():
        assert provenance["label"] == nr.LABELS[base]
        assert provenance["code_sha"] == nr.CODE_SHA
        assert provenance["settings"] == {
            "rerank_top_k": 5,
            "rrf_k": 60,
            "chunk_overlap": 200,
            "parent_expansion_window": 2,
            "parent_expansion_max_chars": 3600,
        }


def test_the_rows_hold_ids_flags_and_numbers_only():
    keys = {
        "case_id",
        "base",
        "index",
        "pool_size",
        "shared_of_five",
        "rerank_sec",
        "reranker_ok",
        "stratum",
        "points",
        "unresolved",
        "expansion_reproduced",
        "short_pool",
    }
    for row in rows:
        assert set(row) <= keys
        assert row["case_id"].startswith(row["base"]) or row["base"] == "aircargo"
        assert set(row.get("points", {})) <= {
            "ranked",
            "fused",
            "expanded_ranked",
            "expanded_fused",
        }


def _p(value):
    return f"{value:.3f}"


def pair_rows(point):
    out = []
    for base in (*nr.METRICS, "pooled"):
        got = (record["pooled"] if base == "pooled" else record["bases"][base])[point]
        left, right = nr.PAIRS[point]
        second = "—"
        if base != "pooled":
            name = nr.METRICS[base][1]
            second = f"{got[name][left]:.3f} → {got[name][right]:.3f}"
        out.append(
            f"| {NAMES.get(base, 'Pooled')} | {got['n']} | {got['hits'][left]} | "
            f"{got['hits'][right]} | {got['b_reranker_only']} | {got['c_fused_only']} | "
            f"{_p(got['p'])} | {got['reading']} | {second} |"
        )
    return out


def beside_rows():
    out = []
    for base in nr.LABELS:
        got = record["bases"][base]
        shared = got["shared_of_five"]
        seconds = got["rerank_sec"]
        out.append(
            f"| {NAMES[base]} | {got['shared_of_five_mean']:.2f} | {shared.get('5', 0)} | "
            f"{shared.get('0', 0)} | {seconds['median']:.1f} ({seconds['p90']:.1f}) |"
        )
    return out


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in pair_rows("ranked") + pair_rows("expanded") + beside_rows():
        assert line in text, line
    assert f"**Decision: {record['decision']}.**" in text
