"""MultiHop-RAG's retrieval by the official rule: the record read again from its rows, stage 2's
committed export and judge export, and the published tables
(docs/specs/multihop-official-retrieval.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/multihop-official/tools/multihop_official.py"
RECORD = ROOT / "reports/multihop-official/5e308fe/record.json"
ROWS = ROOT / "reports/multihop-official/5e308fe/rows.jsonl"
CAPSULE = ROOT / "docs/evidence/multihop-official-record.md"
NO_RERANK = ROOT / "reports/no-rerank/5e308fe/record.json"
JUDGED = ROOT / "reports/stage2/5e308fe/p4-multihoprag-judge-m1.cases.jsonl"


def _load():
    spec = importlib.util.spec_from_file_location("multihop_official_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["multihop_official_artifact"] = module
    spec.loader.exec_module(module)
    return module


mo = _load()
record = json.loads(RECORD.read_text(encoding="utf-8"))
rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]
evaluated = [r for r in rows if r["evaluated"]]
exported = {r["case_id"]: r for r in mo.load_jsonl(mo.EXPORT / f"{mo.LABEL}.cases.jsonl")}
with_gold = sorted(case for case, r in exported.items() if r["gold"])


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def families():
    """Stage 2's clusters of the 70 as its committed judge export numbers them. The bootstrap
    reads the partition alone (semantic_ruler.family_clusters sorts by case), so these give the
    tool's intervals whatever the numbers."""
    judged = {r["case_id"]: r["cluster"] for r in mo.load_jsonl(JUDGED)}
    return {r["case_id"]: [f"cluster:{judged[r['case_id']]}"] for r in evaluated}


def test_every_number_of_the_record_is_read_again_from_its_rows():
    clusters = families()
    for key, name, read in (
        ("official", "official_primary", True),
        ("official_expanded", "official_expanded", False),
    ):
        got = record[name]
        for metric in mo.METRICS:
            mean = math.fsum(r[key][metric] for r in evaluated) / len(evaluated)
            assert got["metrics"][metric] == pytest.approx(mean, abs=1e-12)
        assert got["printed"] == mo.printed(got["metrics"])
        assert _json(mo.official_numbers(got["metrics"], evaluated, key, clusters, read)) == got
    assert _json(mo.beside(evaluated, clusters)) == record["beside"]
    assert mo.discordant(evaluated) == record["discordant_at_4"]
    sizes = Counter(family[0] for family in clusters.values())
    assert record["questions"] == {
        "run": len(rows),
        "skipped_null_query": len(rows) - len(evaluated),
        "evaluated": len(evaluated),
        "strata": dict(Counter(r["stratum"] for r in evaluated)),
        "clusters": len(sizes),
        "largest_cluster": max(sizes.values()),
        "short_of_ten": sum(1 for r in evaluated if r["listed"] < mo.DEPTH),
        "facts": sum(r["facts"] for r in evaluated),
        "facts_repeated": sum(r["facts"] - r["distinct"] for r in evaluated),
        "facts_empty": sum(r["facts_empty"] for r in evaluated),
    }
    assert record["published"]["bands"] == {m: list(mo.band(m)) for m in mo.METRICS}


def test_the_questions_are_stage_2s_70_with_gold_and_its_30_null_queries():
    assert len(rows) == len(exported) == 100
    assert sorted(r["case_id"] for r in rows) == sorted(exported)
    assert sorted(r["case_id"] for r in evaluated) == with_gold
    assert [r["raw_index"] for r in rows] == sorted(r["raw_index"] for r in rows)
    for row in rows:
        assert row["raw_index"] == int(row["case_id"].rsplit("-", 1)[1])
        assert row["stratum"] == exported[row["case_id"]]["stratum"]
        assert row["evaluated"] == (row["stratum"] != mo.NULL_QUERY)
    assert record["questions"]["strata"] == {"inference_query": 70}
    assert _json(mo.committed_points(exported, with_gold)) == record["stage2_committed"]


def test_each_question_reads_the_same_under_both_definitions_of_a_hit():
    for row in evaluated:
        # One fact a group: none repeated, none unplaced (the export's unresolved_evidence 0).
        assert row["groups"] == row["facts"] == row["distinct"]
        assert exported[row["case_id"]]["unresolved_evidence"] == 0
        assert row["listed"] == mo.DEPTH
        for k in mo.KS:
            found = row["substring_found"][f"@{k}"]
            assert row["official"][f"Hits@{k}"] == float(found > 0)
        assert row["substring_found"]["@4"] <= row["substring_found"]["@10"] <= row["distinct"]
        assert row["range"]["@4"]["evidence_recall"] <= row["range"]["@10"]["evidence_recall"]


def test_the_record_names_its_rule_stand_tool_and_inputs():
    assert record["spec"] == mo.SPEC
    assert record["stand_code_sha"] == mo.CODE_SHA
    assert record["tool_sha256"] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert set(record["measure_code_sha256"]) == set(mo.MEASURE_CODE)
    assert record["official"] == mo.OFFICIAL
    registered = json.loads((ROOT / "evaluation/external_bases.json").read_text(encoding="utf-8"))
    base = registered["bases"][mo.BASE]
    entry = next(f for f in base["files"] if f["path"] == mo.RAW_FILE)
    assert record["raw"] == {**entry, "revision": base["revision"]}
    assert record["inputs"]["export"] == str(mo.EXPORT.relative_to(ROOT))
    assert (
        record["inputs"]["export_manifest_sha256"]
        == hashlib.sha256((mo.EXPORT / "manifest.json").read_bytes()).hexdigest()
    )
    provenance = record["provenance"]
    assert (provenance["label"], provenance["code_sha"]) == (mo.LABEL, mo.CODE_SHA)
    # The no-reranker point's run, file by file.
    no_rerank = json.loads(NO_RERANK.read_text(encoding="utf-8"))["provenance"][mo.BASE]
    for key in ("tenant", "archive_sha256", "cases_file_sha256", "launch_sha256"):
        assert provenance[key] == no_rerank[key]
    committed = json.loads((mo.EXPORT / f"{mo.LABEL}.json").read_text(encoding="utf-8"))
    assert provenance["archive_sha256"] == committed["provenance"]["archive_sha256"]
    assert provenance["settings"] == {
        "rerank_top_k": 5,
        "rrf_k": 60,
        "chunk_overlap": 200,
        "parent_expansion_window": 2,
        "parent_expansion_max_chars": 3600,
    }
    assert record["published"]["paper_table5"] == mo.PAPER
    assert record["published"]["script_multi_meta_rag_table2"] == mo.SCRIPT


def test_the_rows_hold_ids_flags_and_numbers_only():
    keys = {
        "case_id",
        "raw_index",
        "stratum",
        "evaluated",
        "facts",
        "distinct",
        "facts_empty",
        "groups",
        "listed",
        "official",
        "official_expanded",
        "substring_found",
        "range",
    }
    for row in rows:
        assert row["stratum"] in {"inference_query", mo.NULL_QUERY}
        if not row["evaluated"]:
            assert set(row) == {"case_id", "raw_index", "stratum", "evaluated"}
            continue
        assert set(row) == keys
        assert set(row["official"]) == set(row["official_expanded"]) == set(mo.METRICS)
        assert set(row["substring_found"]) == set(row["range"]) == {"@4", "@10"}
        for got in row["range"].values():
            assert set(got) == {"all_evidence_coverage", "evidence_recall"}


ORDER = ("Hits@4", "Hits@10", "MRR@10", "MAP@10")


def _span(span):
    return f"{span[0]:.4f}–{span[1]:.4f}"


def _value(printed, entry):
    if "hits" in entry:
        return f"{printed} ({entry['hits']} of {entry['n']})"
    return printed


def official_rows():
    primary, expanded = record["official_primary"], record["official_expanded"]
    out = []
    for metric in ORDER:
        got = primary["intervals"][metric]
        cells = (
            _value(primary["printed"][metric], got),
            _span(got["read95"]),
            _span(record["published"]["bands"][metric]),
            primary["readings"][metric],
            _value(expanded["printed"][metric], expanded["intervals"][metric]),
            _span(expanded["intervals"][metric]["read95"]),
        )
        out.append(f"| {metric} | " + " | ".join(cells) + " |")
    return out


def beside_rows():
    out = []
    for k in mo.KS:
        got = record["beside"][f"@{k}"]
        cells = [
            f"{got[name]['hits']} of {got[name]['n']} ({_span(got[name]['read95'])})"
            for name in ("substring_any", "range_any", "substring_all", "range_all")
        ]
        recall = got["evidence_recall"]
        cells.append(f"{recall['mean']:.4f} ({_span(recall['read95'])})")
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return out


def committed_rows():
    names = {"ranked": "the reranked five", "expanded": "the expanded five", "sent": "«sent»"}
    out = []
    for point, name in names.items():
        got = record["stage2_committed"][point]
        out.append(
            f"| {name} | {got['all_evidence']} of {got['n']} | {got['any_evidence']} of"
            f" {got['n']} | {got['evidence_recall']:.4f} |"
        )
    return out


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in official_rows() + beside_rows() + committed_rows():
        assert line in text, line
    discordant = record["discordant_at_4"]
    assert (
        f"Discordant at four: {discordant['substring_only']} by the substring alone,"
        f" {discordant['range_only']} by the ranges alone." in text
    )
