import gzip
import json

from evaluation.ragas_eval import _normalise
from scripts.generator_benchmark import _truncate_contexts
from scripts.gr1b_controls import DEFAULT_ARCHIVE
from scripts.gr1b_query_control import DEFAULT_REPORT, build_query_report, select_query_subset


def test_selection_preserves_query_terms_and_original_order():
    assert select_query_subset(
        query="alpha beta", candidates=["alpha", "noise", "beta", "noise", "noise"],
        context_chars=6000,
    ) == [0, 2]


def test_selection_scores_after_cap_and_falls_back_without_query_signal():
    assert select_query_subset(
        query="beta", candidates=["noise beta", "beta", "noise", "noise", "noise"],
        context_chars=4,
    ) == [1]
    assert select_query_subset(
        query="", candidates=["a", "b", "c", "d", "e"], context_chars=6000,
    ) == [0, 1, 2, 3, 4]


def test_published_query_control_reproduces_every_case_and_provenance():
    published = json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))
    rebuilt = build_query_report()
    for field in ("aggregate", "baseline", "per_case", "comparison", "labels"):
        assert rebuilt[field] == published[field]
    for field in ("archive_sha256", "pool_sha256", "dataset_sha256", "label_sidecar_sha256",
                  "label_manifest_sha256", "corpus", "config"):
        assert rebuilt["provenance"][field] == published["provenance"][field]
    assert published["aggregate"]["context_recall"] == 0.725
    assert len(published["comparison"]["full_regressions"]) == 22


def test_infeasible_cases_have_facts_absent_even_before_top_five_truncation():
    rows = {row["case_id"]: row for row in json.loads(gzip.decompress(DEFAULT_ARCHIVE.read_bytes()))}
    expected = {
        "aircargo-dangerous-goods-clearance": ["UN"],
        "aircargo-waybill-first-mile-fields": ["waybill_number", "vehicle_number"],
        "aircargo-cross-border-required-fields": ["route_countries", "vehicle_tir_carnet"],
    }
    for case_id, missing in expected.items():
        row = rows[case_id]
        baseline = _normalise("\n".join(_truncate_contexts(row["cands"][:5], 6000)))
        required = [word for word in row["kws"] if _normalise(word) in baseline]
        top_five = _normalise("\n".join(row["reranked_cands"][:5]))
        assert [word for word in required if _normalise(word) not in top_five] == missing
        all_candidates = _normalise("\n".join(row["reranked_cands"]))
        assert [word for word in required if _normalise(word) not in all_candidates] == (
            [] if case_id == "aircargo-dangerous-goods-clearance" else missing
        )
