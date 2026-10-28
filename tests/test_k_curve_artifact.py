"""The K curve after expansion: the record read again from its rows and the committed stage-2
export (docs/specs/k-curve-expanded.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/k-curve/tools/k_curve.py"
RECORD = ROOT / "reports/k-curve/5e308fe/record.json"
ROWS = ROOT / "reports/k-curve/5e308fe/rows.jsonl"
CAPSULE = ROOT / "docs/evidence/k-curve-record.md"
NO_RERANK = ROOT / "reports/no-rerank/5e308fe/record.json"


def _load():
    spec = importlib.util.spec_from_file_location("k_curve_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["k_curve_artifact"] = module
    spec.loader.exec_module(module)
    return module


kc = _load()
nr = kc.nr
record = json.loads(RECORD.read_text(encoding="utf-8"))
rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def test_every_number_of_the_record_is_read_again_from_its_rows():
    for base in nr.LABELS:
        own = [r for r in rows if r["base"] == base]
        assert _json(kc.summary(base, own)) == record["bases"][base]
    gold = [r for r in rows if r["base"] in nr.METRICS]
    assert _json(kc.pooled_curve(gold, not_evidence=False)) == record["pooled"]
    per_base = {b: record["bases"][b] for b in nr.METRICS}
    assert _json(kc.decision(per_base, record["pooled"])) == record["decision"]


def test_the_checks_passed_before_any_number():
    for base in nr.LABELS:
        summary = record["bases"][base]
        assert (summary["questions"], summary["reranker_ok"]) == (100, 100)
        # K = 20 is the recorded five on every question.
        assert summary["curve"][-1]["same_five_mean"] == 5.0
    assert {b: record["bases"][b]["with_gold"] for b in nr.METRICS} == {
        "wixqa": 100,
        "conditionalqa": 80,
        "multihoprag": 70,
    }
    assert all(record["bases"][b]["unresolved"] == 0 for b in nr.METRICS)
    for row in rows:
        if "points" in row:
            top = kc.at(row, kc.KMAX)
            assert (top["ranked"], top["expanded"]) == (
                row["points"]["ranked"],
                row["points"]["expanded_ranked"],
            )


def test_k_20_and_every_k_before_the_expansion_are_the_committed_exports():
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    assert (
        record["inputs"]["export_manifest_sha256"]
        == hashlib.sha256((nr.EXPORT / "manifest.json").read_bytes()).hexdigest()
    )
    by_case = {r["case_id"]: r for r in rows}
    for label in nr.LABELS.values():
        committed = nr.export_rows(label, manifest)
        own = [by_case[case_id] for case_id in committed]
        nr.recount(own, committed)
        kc.against_export(own, committed)
        for row in own:
            assert kc.at(row, kc.KMAX)["candidates"] == len(committed[row["case_id"]]["pool"])
    assert len(by_case) == len(rows) == 400


def test_the_record_names_its_stand_tool_and_settings():
    assert record["spec"] == kc.SPEC
    assert record["stand_code_sha"] == nr.CODE_SHA
    assert record["tool_sha256"] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert set(record["measure_code_sha256"]) == set(kc.MEASURE_CODE)
    assert record["ks"] == list(kc.KS)
    # The no-reranker point's inputs, file by file.
    no_rerank = json.loads(NO_RERANK.read_text(encoding="utf-8"))
    assert record["inputs"] == no_rerank["inputs"]
    for base, provenance in record["provenance"].items():
        assert provenance["label"] == nr.LABELS[base]
        assert provenance["code_sha"] == nr.CODE_SHA
        for key in ("tenant", "archive_sha256", "cases_file_sha256", "launch_sha256"):
            assert provenance[key] == no_rerank["provenance"][base][key]
        assert provenance["settings"] == {
            "rerank_top_k": 5,
            "rrf_k": 60,
            "chunk_overlap": 200,
            "parent_expansion_window": 2,
            "parent_expansion_max_chars": 3600,
            "retrieval_top_k": 20,
            # The runs' settings snapshot shows a name holding «key» only as set or empty.
            "rrf_doc_key_chars": "<set>",
        }


def test_the_rows_hold_ids_flags_and_numbers_only():
    keys = {"case_id", "base", "index", "reranker_ok", "curve", "stratum", "unresolved", "points"}
    for row in rows:
        assert set(row) <= keys
        assert row["case_id"].startswith(row["base"]) or row["base"] == "aircargo"
        assert [e["k"] for e in row["curve"]] == list(kc.KS)
        for entry in row["curve"]:
            assert set(entry) <= {"k", "candidates", "same_five", "ranked", "expanded"}
        assert set(row.get("points", {})) <= {"ranked", "expanded_ranked"}


def _cell(got):
    text = f"{got['hits']['k']} ({got['b_k20_only']}/{got['c_k_only']}, {got['p']:.3f})"
    return text + {"loss": " **loss**", "gain": " *gain*"}.get(got["reading"], "")


def curve_rows(point):
    first = [record["bases"][b]["curve"][0][point] for b in nr.METRICS] + [
        record["pooled"][0][point]
    ]
    out = ["| 20 | " + " | ".join(f"{g['hits']['k20']} of {g['n']}" for g in first) + " |"]
    for i, k in enumerate(kc.KS[:-1]):
        cells = [_cell(record["bases"][b]["curve"][i][point]) for b in nr.METRICS]
        cells.append(_cell(record["pooled"][i][point]))
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return out


def beside_rows():
    out = []
    for i, k in enumerate(kc.KS):
        got = [record["bases"][b]["curve"][i] for b in nr.LABELS]
        medians = " / ".join(f"{g['candidates']['median']:g}" for g in got)
        shared = " / ".join(f"{g['same_five_mean']:.2f}" for g in got)
        out.append(f"| {k} | {medians} | {shared} |")
    return out


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in curve_rows("expanded") + curve_rows("ranked") + beside_rows():
        assert line in text, line
    smallest = record["decision"]["smallest_k_without_a_detected_loss"]
    assert f"**The smallest K without a detected loss: {smallest}.**" in text
