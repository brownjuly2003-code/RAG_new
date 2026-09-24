"""Tests for P1 adaptive-k cut rules: cell names, cut-rule counts, artifact loading."""

import gzip
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts import p1_adaptive_k as p1
from scripts import rerank_score_capture
from tests.test_gr_bucket_baseline import _write_fixture


def _row(case_id, n=6):
    return {
        "case_id": case_id,
        "prerank_cands": [f"{case_id}-text-{j}" for j in range(n)],
    }


def _rows(*case_ids):
    return [_row(case_id) for case_id in case_ids]


def _scores(rows, probs_by_case, pool_sha256="d" * 64):
    """Build a valid rerank score artifact for the given rows and probabilities."""
    per_case = []
    for row, probs in zip(rows, probs_by_case, strict=True):
        n = len(row["prerank_cands"])
        per_case.append(
            {
                "case_id": row["case_id"],
                "n_candidates": n,
                "probabilities": list(probs),
                "logits": [math.log(p / (1 - p)) for p in probs],
                "fresh_order": sorted(range(n), key=lambda j: probs[j], reverse=True),
            }
        )
    return {
        "schema_version": rerank_score_capture.SCHEMA_VERSION,
        "complete": True,
        "provenance": {"pool_sha256": pool_sha256},
        "per_case": per_case,
    }


def _base_artifact():
    rows = _rows("c1", "c2")
    probs_by_case = [[0.9, 0.8, 0.7, 0.3, 0.2, 0.1], [0.6, 0.5, 0.45, 0.4, 0.35, 0.3]]
    return rows, _scores(rows, probs_by_case)


def test_cell_name_formats_families_and_params():
    assert p1.cell_name("abs", 0.0) == "abs_0"
    assert p1.cell_name("abs", 0.01) == "abs_0.01"
    assert p1.cell_name("rel", 0.5) == "rel_0.5"
    assert p1.cell_name("gap_prob", p1.INF) == "gap_prob_inf"
    assert p1.cell_name("gap_logit", 6.0) == "gap_logit_6"
    assert p1.cell_name("top_k", 5) == "top_k_5"


def test_grid_cells_order_roles_and_uniqueness():
    assert p1.CONTROL_CELL == "top_k_5"
    cells = p1.grid_cells()
    names = [name for name, _family, _param, _role in cells]
    assert len(names) == 37
    assert len(set(names)) == 37
    assert [(name, role) for name, _f, _p, role in cells[:5]] == [
        ("top_k_1", "fixed_k"),
        ("top_k_2", "fixed_k"),
        ("top_k_3", "fixed_k"),
        ("top_k_4", "fixed_k"),
        ("top_k_5", "control"),
    ]
    assert cells[5:29] == [
        (p1.cell_name(family, param), family, param, "primary") for family, param in p1.PRIMARY_GRID
    ]
    assert cells[29:] == [
        (p1.cell_name(family, param), family, param, "secondary")
        for family, param in p1.SECONDARY_GRID
    ]
    roles = [role for _name, _family, _param, role in cells]
    assert roles[:5] == ["fixed_k"] * 4 + ["control"]
    assert roles[5:29] == ["primary"] * 24
    assert roles[29:] == ["secondary"] * 8


def test_kept_count_cut_rules():
    p = [0.9, 0.8, 0.2, 0.1, 0.05]
    x = [5.0, 4.0, 1.0, 0.5, 0.0]
    assert p1.kept_count("top_k", 3, p, x) == 3
    assert p1.kept_count("abs", 0.0, p, x) == 5
    assert p1.kept_count("abs", 0.5, p, x) == 2
    assert p1.kept_count("abs", 0.95, p, x) == 1
    assert p1.kept_count("rel", 0.0, p, x) == 5
    assert p1.kept_count("rel", 0.5, p, x) == 2
    assert p1.kept_count("gap_prob", p1.INF, p, x) == 5
    assert p1.kept_count("gap_prob", 0.7, p, x) == 5
    assert p1.kept_count("gap_prob", 0.6, p, x) == 2
    assert p1.kept_count("gap_prob", 0.0, p, x) == 2
    # gap_logit cuts on raw logits: the largest logit gap (3) sits after rank 2.
    assert p1.kept_count("gap_logit", 2.5, p, x) == 2
    # the largest probability gap (0.6) stays below 0.61, so nothing is cut
    assert p1.kept_count("gap_prob", 0.61, p, x) == 5


def test_kept_count_gap_ties():
    x = [2.0, 1.5, 1.0, 0.5, 0.0]
    # two equal largest gaps after ranks 1 and 2: the first one wins
    assert p1.kept_count("gap_prob", 0.0, [0.9, 0.5, 0.1, 0.05, 0.0], x) == 1
    # no positive gap anywhere: keep the whole top five
    assert p1.kept_count("gap_prob", 0.0, [0.5] * 5, x) == 5


def test_kept_count_rejects_invalid_inputs():
    x = [4.0, 3.0, 2.0, 1.0, 0.0]
    p = [0.9, 0.8, 0.5, 0.3, 0.1]
    nan_logits = [float("nan"), 3.0, 2.0, 1.0, 0.0]
    with pytest.raises(ValueError):
        p1.kept_count("abs", 0.5, [0.9, 0.8, 0.7, 0.6], x)  # only four probabilities
    with pytest.raises(ValueError):
        p1.kept_count("abs", 0.5, [0.1, 0.2, 0.3, 0.4, 0.5], x)  # increasing probabilities
    with pytest.raises(ValueError):
        p1.kept_count("abs", 0.5, [1.2, 0.8, 0.5, 0.3, 0.1], x)  # probability 1.2
    with pytest.raises(ValueError):
        p1.kept_count("abs", 0.5, p, nan_logits)  # NaN logit
    with pytest.raises(ValueError):
        p1.kept_count("abs", 0.5, [True, 0.8, 0.5, 0.3, 0.1], x)  # bool probability
    with pytest.raises(ValueError):
        p1.kept_count("median", 0.5, p, x)  # unknown family
    with pytest.raises(ValueError):
        p1.kept_count("top_k", 0, p, x)  # k below 1
    with pytest.raises(ValueError):
        p1.kept_count("top_k", 6, p, x)  # k above TOP_N


def test_load_scores_returns_per_case_list():
    rows, report = _base_artifact()
    per_case = p1.load_scores(report, rows, "d" * 64)
    assert isinstance(per_case, list)
    assert per_case == report["per_case"]
    assert [case["case_id"] for case in per_case] == ["c1", "c2"]


def test_load_scores_rejects_invalid_artifacts():
    rows, report = _base_artifact()
    report["schema_version"] = "wrong/v0"
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "d" * 64)

    rows, report = _base_artifact()
    report["complete"] = False
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "d" * 64)

    rows, report = _base_artifact()  # pool digest mismatch
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "e" * 64)

    rows, report = _base_artifact()  # case ids in a different order
    with pytest.raises(ValueError):
        p1.load_scores(report, list(reversed(rows)), "d" * 64)

    four_rows = [_row("c1", 4)]  # n_candidates 4 with only four texts
    with pytest.raises(ValueError):
        p1.load_scores(_scores(four_rows, [[0.9, 0.8, 0.7, 0.6]]), four_rows, "d" * 64)

    rows, report = _base_artifact()
    report["per_case"][0]["fresh_order"] = [0, 0, 1, 2, 3, 4]  # not a permutation
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "d" * 64)

    rows, report = _base_artifact()
    report["per_case"][0]["fresh_order"] = [5, 4, 3, 2, 1, 0]  # probabilities increase
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "d" * 64)

    rows, report = _base_artifact()
    report["per_case"][0]["logits"][0] = True  # bool logit
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "d" * 64)


def test_fresh_rankings_reorders_by_fresh_order():
    rows = _rows("c1")
    probs = [0.2, 0.9, 0.1, 0.7, 0.3, 0.5]
    order = [1, 3, 5, 4, 0, 2]
    report = _scores(rows, [probs])
    assert report["per_case"][0]["fresh_order"] == order
    rankings = p1.fresh_rankings(rows, report["per_case"])
    assert len(rankings) == 1
    ranking = rankings[0]
    assert ranking["case_id"] == "c1"
    assert ranking["texts"] == [rows[0]["prerank_cands"][j] for j in order]
    assert ranking["probabilities"] == [probs[j] for j in order]
    assert ranking["logits"] == [math.log(probs[j] / (1 - probs[j])) for j in order]


def test_rule_counts_applies_kept_count_to_top_five():
    rows = _rows("a", "b")
    probs_by_case = [
        [0.9, 0.8, 0.51, 0.4, 0.3, 0.2],
        [0.4, 0.6, 0.3, 0.2, 0.1, 0.05],
    ]
    scores = p1.load_scores(_scores(rows, probs_by_case), rows, "d" * 64)
    rankings = p1.fresh_rankings(rows, scores)
    assert [r["probabilities"][:5] for r in rankings] == [
        [0.9, 0.8, 0.51, 0.4, 0.3],
        [0.6, 0.4, 0.3, 0.2, 0.1],
    ]
    # case "a" keeps three candidates under abs 0.5; case "b" keeps only rank 1
    assert p1.rule_counts(rankings, "abs", 0.5) == [3, 1]
    assert p1.rule_counts(rankings, "top_k", 2) == [2, 2]


def test_preregistered_constants_are_pinned():
    assert [name for name, *_ in p1.grid_cells()] == [
        "top_k_1",
        "top_k_2",
        "top_k_3",
        "top_k_4",
        "top_k_5",
        "abs_0",
        "abs_0.01",
        "abs_0.05",
        "abs_0.1",
        "abs_0.2",
        "abs_0.3",
        "abs_0.5",
        "abs_0.7",
        "abs_0.9",
        "rel_0",
        "rel_0.1",
        "rel_0.2",
        "rel_0.3",
        "rel_0.5",
        "rel_0.7",
        "rel_0.9",
        "gap_prob_inf",
        "gap_prob_0.5",
        "gap_prob_0.4",
        "gap_prob_0.3",
        "gap_prob_0.2",
        "gap_prob_0.1",
        "gap_prob_0.05",
        "gap_prob_0",
        "gap_logit_inf",
        "gap_logit_6",
        "gap_logit_4",
        "gap_logit_3",
        "gap_logit_2",
        "gap_logit_1",
        "gap_logit_0.5",
        "gap_logit_0",
    ]
    assert p1.TOP_N == 5
    assert p1.CONTEXT_CHARS == 6000
    assert p1.FOLDS == 5
    assert p1.GRID_BOOTSTRAP_SAMPLES == 2000
    assert p1.HEADLINE_BOOTSTRAP_SAMPLES == 10000
    assert p1.BOOTSTRAP_SEED == 20260923
    assert p1.PRECISION_GATE == 0.63
    assert p1.REVIEW_FLOOR == {"context_recall": 0.92, "FULL": 88, "MISS": 4}
    assert p1.PUBLISHED_H == {
        "context_precision": 0.5067,
        "context_recall": 0.905,
        "FULL": 87,
        "PART": 7,
        "MISS": 6,
    }
    assert p1.H_POOL_SHA256 == "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10"
    assert p1.HM_POOL_SHA256 == "3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee"
    assert p1.CODE_PATHS == (
        "scripts/p1_adaptive_k.py",
        "scripts/rerank_score_capture.py",
        "scripts/gr1b_controls.py",
        "scripts/ab_context_precision.py",
        "scripts/generator_benchmark.py",
        "scripts/ab_remote_contextual.py",
        "evaluation/ragas_eval.py",
        "evaluation/question_class_labels.py",
    )


def test_load_scores_rejects_a_non_stable_tie_order():
    rows = _rows("t1")
    probs = [0.5] * 5 + [0.4]
    report = _scores(rows, [probs])
    p1.load_scores(report, rows, "d" * 64)
    report["per_case"][0]["fresh_order"] = [4, 3, 2, 1, 0, 5]
    with pytest.raises(ValueError):
        p1.load_scores(report, rows, "d" * 64)


def test_verdict_flags_compare_exact_sums():
    def _flag_row(case_id, precision, recall=1.0, status="FULL"):
        return {
            "case_id": case_id,
            "context_precision": precision,
            "context_recall": recall,
            "kw_status": status,
            "kept": 1,
            "n_docs": 1,
        }

    control = [_flag_row(case_id, 0.5) for case_id in ("a", "b", "c")]

    # the rounded mean is 0.63, yet the exact four-decimal sum misses 3 * 6300 by one unit
    short = p1.verdict_flags(
        [_flag_row("a", 0.6299), _flag_row("b", 0.63), _flag_row("c", 0.63)], control
    )
    assert short["precision_gate_met"] is False

    exact = p1.verdict_flags([_flag_row(case_id, 0.63) for case_id in ("a", "b", "c")], control)
    assert exact["precision_gate_met"] is True

    held_recalls = [
        _flag_row("a", 0.5, recall=0.9),
        _flag_row("b", 0.5, recall=0.9),
        _flag_row("c", 0.5, recall=1.0),
    ]
    control_recalls = [
        _flag_row("a", 0.5, recall=0.9),
        _flag_row("b", 0.5, recall=1.0),
        _flag_row("c", 0.5, recall=1.0),
    ]
    assert p1.verdict_flags(held_recalls, control_recalls)["h_relative_constraints_met"] is False
    assert p1.verdict_flags(control_recalls, control_recalls)["h_relative_constraints_met"] is True

    assert exact["review_floor_met"] is False
    assert short["review_floor_met"] is False

    assert list(exact) == ["precision_gate_met", "h_relative_constraints_met", "review_floor_met"]

    with pytest.raises(ValueError):
        p1.verdict_flags([], control)

    mismatched = [_flag_row(case_id, 0.5) for case_id in ("a", "b", "d")]
    with pytest.raises(ValueError):
        p1.verdict_flags(mismatched, control)


def _case(case_id, precision, recall=1.0, status="FULL", kept=5, n_docs=None, matched=()):
    return {
        "case_id": case_id,
        "context_precision": precision,
        "context_recall": recall,
        "kw_status": status,
        "kept": kept,
        "n_docs": kept if n_docs is None else n_docs,
        "matched_keywords": list(matched),
    }


def test_case_groups_join_tags_or_fall_back_to_case_ids():
    rows = [
        {"case_id": "c1", "tags": ["hr", "leave"]},
        {"case_id": "c2"},
        {"case_id": "c3", "tags": []},
        {"case_id": "c4", "tags": "hr"},
    ]
    assert p1.case_groups(rows) == {
        "c1": "hr/leave",
        "c2": "case:c2",
        "c3": "case:c3",
        "c4": "case:c4",
    }


def test_assign_folds_balances_whole_groups():
    groups = {}
    for name, count in (("a", 3), ("b", 2), ("c", 2), ("d", 1), ("e", 1)):
        for j in range(count):
            groups[f"{name}{j}"] = name
    folds = p1.assign_folds(groups, 2)
    folds_by_group = {}
    for case_id, fold in folds.items():
        folds_by_group.setdefault(groups[case_id], set()).add(fold)
    # groups by descending size then name land on folds 0, 1, 1, 0, 0
    assert folds_by_group == {"a": {0}, "b": {1}, "c": {1}, "d": {0}, "e": {0}}
    sizes = [sum(1 for fold in folds.values() if fold == i) for i in (0, 1)]
    assert sizes == [5, 4]


def test_assign_folds_rejects_invalid_fold_counts():
    groups = {"a1": "a", "b1": "b", "c1": "c", "d1": "d", "e1": "e"}
    with pytest.raises(ValueError):
        p1.assign_folds(groups, 1)
    with pytest.raises(ValueError):
        p1.assign_folds(groups, True)
    with pytest.raises(ValueError):
        p1.assign_folds(groups, 6)


def test_aggregate_means_status_counts_and_key_order():
    rows = [
        _case("a", 0.5, recall=0.9, status="FULL", kept=3, n_docs=4),
        _case("b", 0.62, recall=1.0, status="MISS", kept=5, n_docs=6),
    ]
    assert list(p1.aggregate(rows)) == [
        "num_cases",
        "context_precision",
        "context_recall",
        "FULL",
        "PART",
        "MISS",
        "mean_kept",
        "mean_n_docs",
    ]
    assert p1.aggregate(rows) == {
        "num_cases": 2,
        "context_precision": 0.56,
        "context_recall": 0.95,
        "FULL": 1,
        "PART": 0,
        "MISS": 1,
        "mean_kept": 4.0,
        "mean_n_docs": 5.0,
    }
    assert p1.aggregate([]) == {
        "num_cases": 0,
        "context_precision": None,
        "context_recall": None,
        "FULL": 0,
        "PART": 0,
        "MISS": 0,
        "mean_kept": None,
        "mean_n_docs": None,
    }


def test_select_cell_rejects_recall_and_status_regressions():
    case_ids = ("a", "b")
    control = [_case("a", 0.5), _case("b", 0.5)]
    per_cell = {
        "control": control,
        "loses_recall": [_case("a", 0.9, recall=0.9), _case("b", 0.9)],
        "full_to_part": [_case("a", 0.9), _case("b", 0.9, status="PART")],
        "adds_miss": [_case("a", 0.9), _case("b", 0.9, status="MISS")],
        "feasible": [_case("a", 0.9), _case("b", 0.9)],
    }
    for rejected in ("loses_recall", "full_to_part", "adds_miss"):
        assert p1.select_cell(per_cell, [rejected], "control", case_ids) == "control"
    assert p1.select_cell(per_cell, ["feasible"], "control", case_ids) == "feasible"


def test_select_cell_tie_breaks_and_fallbacks():
    case_ids = ("a",)
    control = [_case("a", 0.5)]
    per_cell = {
        "control": control,
        "narrow": [_case("a", 0.8, kept=2)],
        "wide": [_case("a", 0.8, kept=4)],
        "also_narrow": [_case("a", 0.8, kept=2)],
        "infeasible": [_case("a", 0.8, recall=0.9)],
    }
    # equal precision: the larger mean_kept wins, whatever the candidate order
    assert p1.select_cell(per_cell, ["narrow", "wide"], "control", case_ids) == "wide"
    assert p1.select_cell(per_cell, ["wide", "narrow"], "control", case_ids) == "wide"
    # equal precision and kept: the earlier candidate in the sequence wins
    assert p1.select_cell(per_cell, ["narrow", "also_narrow"], "control", case_ids) == "narrow"
    # no feasible candidate: the control cell itself is returned
    assert p1.select_cell(per_cell, ["infeasible"], "control", case_ids) == "control"
    # an empty case_ids collection selects no rows of the control cell
    with pytest.raises(ValueError):
        p1.select_cell(per_cell, ["narrow"], "control", ())


def test_select_cell_compares_exact_sums_not_rounded_means():
    control = [_case("a", 0.5), _case("b", 0.5)]
    slightly_better = [_case("a", 0.6301, kept=2), _case("b", 0.63, kept=2)]
    wider = [_case("a", 0.63, kept=3), _case("b", 0.63, kept=3)]
    per_cell = {"control": control, "slightly_better": slightly_better, "wider": wider}
    # both candidates report the same rounded 0.63 mean, recall and statuses
    for rows in (slightly_better, wider):
        assert p1.aggregate(rows)["context_precision"] == 0.63
        assert p1.aggregate(rows)["context_recall"] == 1.0
        assert p1.aggregate(rows)["FULL"] == 2
        assert p1.aggregate(rows)["MISS"] == 0
    # exact four-decimal sums: 12601 units beat 12600 despite the smaller kept total
    picked = p1.select_cell(per_cell, ["wider", "slightly_better"], "control", ("a", "b"))
    assert picked == "slightly_better"


def test_check_parity_requires_registered_model_archived_order_and_full_parity():
    def capture():
        rows = _rows("c1", "c2")
        report = _scores(rows, [[0.9, 0.8, 0.7, 0.3, 0.2, 0.1]] * 2)
        for row, case in zip(rows, report["per_case"], strict=True):
            row["cands"] = [row["prerank_cands"][j] for j in case["fresh_order"]]
        report["provenance"]["reranker"] = {"model": p1.RERANKER_MODEL}
        report["parity"] = {
            "order_matches": len(rows),
            "top_k_matches": len(rows),
            "mismatched_case_ids": [],
        }
        return rows, report

    rows, report = capture()
    p1.check_parity(rows, report)

    rows, report = capture()
    report["provenance"]["reranker"]["model"] = "another/model"
    with pytest.raises(ValueError, match="model"):
        p1.check_parity(rows, report)

    rows, report = capture()
    rows[1]["cands"] = list(reversed(rows[1]["cands"]))
    with pytest.raises(ValueError, match="c2"):
        p1.check_parity(rows, report)

    rows, report = capture()
    report["parity"]["order_matches"] -= 1
    with pytest.raises(ValueError, match="parity"):
        p1.check_parity(rows, report)

    rows, report = capture()
    report["parity"]["top_k_matches"] -= 1
    with pytest.raises(ValueError, match="parity"):
        p1.check_parity(rows, report)

    rows, report = capture()
    report["parity"]["mismatched_case_ids"] = ["c2"]
    with pytest.raises(ValueError, match="c2"):
        p1.check_parity(rows, report)


def test_fact_losses_reports_keywords_and_status_regressions_by_case_id():
    control = [
        _case("unchanged", 0.5, matched=("delta",)),
        _case("status", 0.5, matched=("gamma",)),
        _case("lost", 0.5, matched=("alpha", "beta")),
    ]
    lost = _case("lost", 0.6, status="PART", kept=2, matched=("beta",))
    lost.update(fold=1, cell="abs_0.5")
    selected = [
        lost,
        _case("status", 0.6, status="PART", kept=3, matched=("gamma",)),
        _case("unchanged", 0.6, matched=("delta",)),
    ]
    assert p1.fact_losses(selected, control) == [
        {
            "case_id": "lost",
            "fold": 1,
            "cell": "abs_0.5",
            "kept": 2,
            "lost_keywords": ["alpha"],
            "control_status": "FULL",
            "status": "PART",
        },
        {
            "case_id": "status",
            "kept": 3,
            "lost_keywords": [],
            "control_status": "FULL",
            "status": "PART",
        },
    ]
    with pytest.raises(ValueError, match="missing"):
        p1.fact_losses([_case("missing", 0.6)], control)


def test_verdict_flags_review_floor_exact_boundary():
    def floor_rows(*, recall=0.92, full=88, miss=4):
        return [
            _case(
                f"c{i}",
                0.63,
                recall=recall,
                status="FULL" if i < full else "MISS" if i < full + miss else "PART",
            )
            for i in range(100)
        ]

    all_full = floor_rows(recall=1.0, full=100, miss=0)
    assert p1.verdict_flags(all_full, all_full)["review_floor_met"] is True

    boundary = floor_rows()
    assert p1._units(boundary, "context_recall") == 9200 * 100
    assert p1.verdict_flags(boundary, boundary)["review_floor_met"] is True

    below = floor_rows()
    below[0]["context_recall"] = 0.9199
    assert p1.verdict_flags(below, below)["review_floor_met"] is False

    too_few_full = floor_rows(full=87)
    assert p1.verdict_flags(too_few_full, too_few_full)["review_floor_met"] is False

    too_many_miss = floor_rows(miss=5)
    assert p1.verdict_flags(too_many_miss, too_many_miss)["review_floor_met"] is False


def test_cross_validate_returns_each_case_in_control_order_with_its_fold_choice():
    case_ids = ("a", "b", "c", "d")
    per_cell = {
        p1.CONTROL_CELL: [_case(case_id, 0.5) for case_id in case_ids],
        "better": [_case(case_id, 0.9, kept=2) for case_id in case_ids],
    }
    folds = {"a": 0, "b": 1, "c": 0, "d": 1}

    held_out, choices = p1.cross_validate(per_cell, ["better"], p1.CONTROL_CELL, folds)

    assert [row["case_id"] for row in held_out] == list(case_ids)
    assert len({row["case_id"] for row in held_out}) == 4
    assert [(row["fold"], row["cell"], row["kept"]) for row in held_out] == [
        (folds[case_id], "better", 2) for case_id in case_ids
    ]
    assert [(choice["fold"], choice["cell"]) for choice in choices] == [
        (0, "better"),
        (1, "better"),
    ]
    assert [(choice["train_cases"], choice["test_cases"]) for choice in choices] == [
        (2, 2),
        (2, 2),
    ]


def test_cross_validate_selects_on_training_cases_only():
    control = [_case(case_id, 0.5) for case_id in ("a", "b", "c", "d")]
    better = [
        _case("a", 0.9, status="PART", kept=2),
        _case("b", 0.9, kept=2),
        _case("c", 0.9, kept=2),
        _case("d", 0.9, kept=2),
    ]
    folds = {"a": 0, "b": 0, "c": 1, "d": 1}

    held_out, choices = p1.cross_validate(
        {p1.CONTROL_CELL: control, "better": better}, ["better"], p1.CONTROL_CELL, folds
    )

    assert [(choice["fold"], choice["cell"]) for choice in choices] == [
        (0, "better"),
        (1, p1.CONTROL_CELL),
    ]
    assert [(row["cell"], row["kw_status"]) for row in held_out] == [
        ("better", "PART"),
        ("better", "FULL"),
        (p1.CONTROL_CELL, "FULL"),
        (p1.CONTROL_CELL, "FULL"),
    ]


def test_cross_validate_rejects_missing_case_fold():
    per_cell = {p1.CONTROL_CELL: [_case("a", 0.5), _case("b", 0.5)]}
    with pytest.raises(ValueError, match="folds_by_case"):
        p1.cross_validate(per_cell, [], p1.CONTROL_CELL, {"a": 0})


def test_oracle_best_prefix_preserves_keywords_then_precision_then_shortest_tie():
    prefixes = {
        1: (0.99, ("alpha",)),
        2: (0.7, ("alpha", "beta")),
        3: (0.8, ("alpha", "beta")),
        4: (0.8, ("alpha", "beta")),
        5: (0.5, ("alpha", "beta")),
    }
    per_cell = {
        f"top_k_{k}": [_case("a", precision, kept=k, matched=matched)]
        for k, (precision, matched) in prefixes.items()
    }

    picked = p1.oracle_best_prefix(per_cell)

    assert len(picked) == 1
    assert picked[0]["oracle_k"] == 3
    assert picked[0]["context_precision"] == 0.8
    assert picked[0]["matched_keywords"] == ["alpha", "beta"]


def test_oracle_best_prefix_rejects_worse_status_even_with_same_keywords():
    per_cell = {
        "top_k_1": [_case("a", 0.99, status="PART", kept=1, matched=("alpha",))],
        "top_k_2": [_case("a", 0.8, kept=2, matched=("alpha",))],
        "top_k_3": [_case("a", 0.7, kept=3, matched=("alpha",))],
        "top_k_4": [_case("a", 0.6, kept=4, matched=("alpha",))],
        "top_k_5": [_case("a", 0.5, matched=("alpha",))],
    }

    picked = p1.oracle_best_prefix(per_cell)

    assert picked[0]["oracle_k"] == 2
    assert picked[0]["kw_status"] == "FULL"
    assert picked[0]["context_precision"] == 0.8


def test_select_cell_rejects_miss_increase_without_recall_or_full_loss():
    control = [_case("a", 0.5), _case("b", 0.5, status="PART")]
    adds_miss = [_case("a", 0.9), _case("b", 0.9, status="MISS")]
    keeps_part = [_case("a", 0.9), _case("b", 0.9, status="PART")]
    per_cell = {p1.CONTROL_CELL: control, "adds_miss": adds_miss, "keeps_part": keeps_part}

    assert p1.aggregate(adds_miss)["context_recall"] == p1.aggregate(control)["context_recall"]
    assert p1.aggregate(adds_miss)["FULL"] == p1.aggregate(control)["FULL"]
    assert p1.select_cell(per_cell, ["adds_miss"], p1.CONTROL_CELL, ("a", "b")) == p1.CONTROL_CELL
    assert p1.select_cell(per_cell, ["keeps_part"], p1.CONTROL_CELL, ("a", "b")) == "keeps_part"


def _inputs(tmp_path: Path, *, model=None, swap_case=None) -> dict:
    paths = _write_fixture(tmp_path / "fx")
    rows = json.loads(paths["pool"].read_text(encoding="utf-8"))
    for row in rows:
        row["prerank_cands"] = row["cands"] + [
            f"filler {i} text without keywords" for i in range(4)
        ]
        row["cands"] = list(row["prerank_cands"])
        row["rerank_k"] = 5
        if row["case_id"] == swap_case:
            row["cands"][-2], row["cands"][-1] = row["cands"][-1], row["cands"][-2]
    raw = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    archive = tmp_path / "archive.json.gz"
    archive.write_bytes(gzip.compress(raw, mtime=0))
    digest = hashlib.sha256(raw).hexdigest()
    probabilities = [0.9, 0.8, 0.3, 0.2, 0.1, 0.05]
    scores = {
        "schema_version": rerank_score_capture.SCHEMA_VERSION,
        "complete": True,
        "parity": {"order_matches": 4, "top_k_matches": 4, "mismatched_case_ids": []},
        "provenance": {
            "pool_sha256": digest,
            "code": {"commit": "f" * 40},
            "reranker": {"model": model or p1.RERANKER_MODEL},
            "config": {"batch_size": 8},
        },
        "per_case": [
            {
                "case_id": row["case_id"],
                "n_candidates": 6,
                "probabilities": probabilities,
                "logits": [math.log(p / (1 - p)) for p in probabilities],
                "fresh_order": list(range(6)),
            }
            for row in rows
        ],
    }
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
    return {
        "h_scores": scores_path,
        "hm_scores": scores_path,
        "h_archive": archive,
        "hm_archive": archive,
        "h_pool_sha256": digest,
        "hm_pool_sha256": digest,
        "dataset_path": paths["dataset"],
        "hm_dataset_path": paths["dataset"],
        "sidecar_path": paths["sidecar"],
        "hm_sidecar_path": paths["sidecar"],
        "label_manifest_path": paths["label_manifest"],
        "hm_label_manifest_path": paths["label_manifest"],
        "corpus_manifest_path": paths["corpus_manifest"],
        "folds": 2,
        "grid_bootstrap_samples": 50,
        "headline_bootstrap_samples": 50,
        "code_commit": "0" * 40,
    }


@pytest.fixture(scope="module")
def synthetic_report(tmp_path_factory):
    inputs = _inputs(tmp_path_factory.mktemp("p1_synthetic"))
    return inputs, p1.build_report(**inputs)


def test_score_selection_keeps_dataset_order_and_keyword_evidence(synthetic_report):
    inputs, _report = synthetic_report
    rows = json.loads(gzip.decompress(inputs["h_archive"].read_bytes()))
    scores = json.loads(inputs["h_scores"].read_text(encoding="utf-8"))
    rankings = p1.fresh_rankings(rows, scores["per_case"])
    kept = [1, 2, 5, 1]

    selected, _approved = p1.score_selection(
        list(reversed(rows)),
        list(reversed(rankings)),
        list(reversed(kept)),
        dataset_path=inputs["dataset_path"],
        sidecar_path=inputs["sidecar_path"],
        label_manifest_path=inputs["label_manifest_path"],
    )

    dataset_ids = [
        json.loads(line)["case_id"]
        for line in inputs["dataset_path"].read_text(encoding="utf-8").splitlines()
    ]
    assert [row["case_id"] for row in selected] == dataset_ids
    assert [row["kept"] for row in selected] == kept
    assert [row["matched_keywords"] for row in selected] == [
        ["поля", "допуск"],
        ["юрист", "эскалаци"],
        [],
        ["хранени"],
    ]
    assert [row["context_chars"] for row in selected] == [
        sum(len(text) for text in ranking["texts"][:k])
        for ranking, k in zip(rankings, kept, strict=True)
    ]
    assert all(0 < row["n_docs"] <= row["kept"] for row in selected)


def test_build_report_has_pinned_top_level_and_grid_config(synthetic_report):
    _, report = synthetic_report
    assert list(report) == [
        "schema_version",
        "evidence_class",
        "labels",
        "provenance",
        "config",
        "h",
        "hm",
        "verdict",
    ]
    assert report["schema_version"] == p1.SCHEMA_VERSION
    assert report["config"]["cells"] == [name for name, *_ in p1.grid_cells()]
    assert list(report["config"]["rules"]) == [
        "top_k",
        "abs",
        "rel",
        "gap_prob",
        "gap_logit",
    ]


def test_build_report_h_cells_follow_grid_and_cut_counts(synthetic_report):
    _, report = synthetic_report
    cells = report["h"]["cells"]
    by_name = {cell["name"]: cell for cell in cells}
    assert [cell["name"] for cell in cells] == [name for name, *_ in p1.grid_cells()]
    assert by_name["top_k_1"]["kept"] == [1] * 4
    assert by_name["abs_0.5"]["kept"] == [2] * 4
    assert by_name["gap_prob_inf"]["aggregate"] == by_name["top_k_5"]["aggregate"]
    assert all(len(cell["comparison"]["precision_delta_ci95"]) == 2 for cell in cells)


def test_build_report_cross_validation_has_held_out_primary_choices(synthetic_report):
    _, report = synthetic_report
    cv = report["h"]["cross_validation"]
    choices = cv["choices"]
    per_case = cv["per_case"]
    assert report["verdict"]["headline"].startswith("2-fold ")
    assert len(per_case) == 4
    assert len({row["case_id"] for row in per_case}) == 4
    assert {row["fold"] for row in per_case} == {0, 1}
    assert [choice["fold"] for choice in choices] == [0, 1]
    assert all(choice["cell"] in report["config"]["primary"] for choice in choices)
    assert all(row["cell"] == choices[row["fold"]]["cell"] for row in per_case)


def test_build_report_decision_fails_closed_then_uses_both_gates(synthetic_report, monkeypatch):
    inputs, report = synthetic_report
    published_h = p1.PUBLISHED_H
    assert report["h"]["control_reproduces_published"] is False
    assert report["verdict"]["decision"] == "INVALID_CONTROL"
    assert isinstance(report["verdict"]["scope"], str) and report["verdict"]["scope"]

    control = next(cell for cell in report["h"]["cells"] if cell["name"] == p1.CONTROL_CELL)
    agg = control["aggregate"]
    monkeypatch.setattr(p1, "PUBLISHED_H", {key: agg[key] for key in published_h})
    rebuilt = p1.build_report(**inputs)
    verdict = rebuilt["verdict"]
    expected = (
        "SHIP_CANDIDATE"
        if verdict["precision_gate_met"] and verdict["h_relative_constraints_met"]
        else "NO_SHIP"
    )
    assert rebuilt["h"]["control_reproduces_published"] is True
    assert verdict["decision"] == expected

    calls = []
    current_flags = {
        "precision_gate_met": True,
        "h_relative_constraints_met": True,
        "review_floor_met": False,
    }

    def fake_verdict_flags(held_out, control_rows):
        calls.append((len(held_out), len(control_rows)))
        return dict(current_flags)

    monkeypatch.setattr(p1, "verdict_flags", fake_verdict_flags)
    for gate, relative, decision in (
        (True, True, "SHIP_CANDIDATE"),
        (True, False, "NO_SHIP"),
        (False, True, "NO_SHIP"),
    ):
        current_flags = {
            "precision_gate_met": gate,
            "h_relative_constraints_met": relative,
            "review_floor_met": False,
        }
        call_count = len(calls)
        rebuilt = p1.build_report(**inputs)
        assert len(calls) == call_count + 1
        assert rebuilt["h"]["control_reproduces_published"] is True
        assert rebuilt["verdict"]["decision"] == decision
        assert {key: rebuilt["verdict"][key] for key in current_flags} == current_flags

    monkeypatch.setattr(p1, "PUBLISHED_H", published_h)
    current_flags = {
        "precision_gate_met": True,
        "h_relative_constraints_met": True,
        "review_floor_met": False,
    }
    call_count = len(calls)
    rebuilt = p1.build_report(**inputs)
    assert len(calls) == call_count + 1
    assert rebuilt["h"]["control_reproduces_published"] is False
    assert rebuilt["verdict"]["decision"] == "INVALID_CONTROL"
    assert {key: rebuilt["verdict"][key] for key in current_flags} == current_flags
    assert calls == [(4, 4)] * 4


def test_build_report_fact_loss_shapes_and_table_bullets(synthetic_report):
    _, report = synthetic_report
    cv_losses = report["h"]["cross_validation"]["fact_losses"]
    hm_losses = report["hm"]["transfer"]["fact_losses"]
    assert isinstance(cv_losses, list)
    assert isinstance(hm_losses, list)
    assert cv_losses == [
        {
            "case_id": "syn-two",
            "fold": 1,
            "cell": "abs_0.9",
            "kept": 1,
            "lost_keywords": ["эскалаци"],
            "control_status": "FULL",
            "status": "PART",
        }
    ]
    # H and Hm use the same synthetic data, so this transfer has no fact losses.
    assert hm_losses == []
    losses = p1.fact_losses(
        [_case("a", 0.5, status="PART", kept=1)],
        [_case("a", 0.5, matched=("x",))],
    )
    assert len(losses) == 1
    assert list(losses[0]) == [
        "case_id",
        "kept",
        "lost_keywords",
        "control_status",
        "status",
    ]
    lines = p1.render_table(report).splitlines()
    assert sum(line.startswith("- Held-out fact losses:") for line in lines) == 1
    assert sum(line.startswith("- Hm transfer fact losses:") for line in lines) == 1
    with_loss = dict(report)
    with_loss["hm"] = dict(report["hm"])
    with_loss["hm"]["transfer"] = dict(report["hm"]["transfer"], fact_losses=losses)
    assert (
        "- Hm transfer fact losses: `a` (FULL->PART): `x`"
        in p1.render_table(with_loss).splitlines()
    )


def test_build_report_transfers_h_choice_and_marks_oracle_diagnostic(synthetic_report):
    _, report = synthetic_report
    oracle = report["h"]["oracle_best_prefix"]
    assert report["hm"]["transfer"]["cell"] == report["h"]["in_sample_best"]["cell"]
    assert oracle["kind"] == "oracle_diagnostic_not_deployable"
    assert len(oracle["oracle_k"]) == 4
    assert all(1 <= k <= 5 for k in oracle["oracle_k"])


def test_build_report_records_synthetic_provenance(synthetic_report):
    inputs, report = synthetic_report
    pools = report["provenance"]["pools"]
    assert pools["H"]["pool_sha256"] == inputs["h_pool_sha256"]
    assert pools["H"]["scores_code_commit"] == "f" * 40
    assert pools["H"]["reranker"]["model"] == p1.RERANKER_MODEL
    assert report["provenance"]["code"]["commit"] == "0" * 40


def test_build_report_is_deterministic_and_json_finite(synthetic_report):
    inputs, report = synthetic_report
    assert p1.build_report(**inputs) == report
    assert isinstance(json.dumps(report, allow_nan=False), str)


def test_build_report_rejects_incomplete_wrong_model_and_order(tmp_path):
    incomplete = _inputs(tmp_path / "incomplete")
    scores_path = incomplete["h_scores"]
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    scores["complete"] = False
    scores_path.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="complete"):
        p1.build_report(**incomplete)

    wrong_model = _inputs(tmp_path / "wrong_model", model="other/model")
    with pytest.raises(ValueError, match="model"):
        p1.build_report(**wrong_model)

    swapped = _inputs(tmp_path / "swapped", swap_case="syn-one")
    with pytest.raises(ValueError) as exc:
        p1.build_report(**swapped)
    message = str(exc.value)
    assert "syn-one" in message
    assert all(case_id not in message for case_id in ("syn-two", "syn-three", "syn-four"))


def test_render_table_and_write_report_cover_grid_and_round_trip(synthetic_report, tmp_path):
    _, report = synthetic_report
    lines = p1.render_table(report).splitlines()
    assert lines[2].startswith("| cell | role | precision | recall |")
    grid_rows = [line for line in lines if line.startswith("| ") and line != lines[2]]
    assert [line.split("|")[1].strip() for line in grid_rows] == report["config"]["cells"]
    assert any(line.startswith("- CV held-out ") for line in lines)
    assert any(line.startswith("**Decision: ") for line in lines)

    path = tmp_path / "report.json"
    assert p1.write_report(path, report) == path
    assert json.loads(path.read_text(encoding="utf-8")) == report
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert b"\r\n" not in raw


def test_main_writes_requested_report_and_prints_table(
    synthetic_report, tmp_path, monkeypatch, capsys
):
    inputs, report = synthetic_report
    path = tmp_path / "cli" / "report.json"
    monkeypatch.setattr(p1, "build_report", lambda **kw: report)

    result = p1.main(
        [
            "--h-scores",
            str(inputs["h_scores"]),
            "--hm-scores",
            str(inputs["hm_scores"]),
            "--report",
            str(path),
        ]
    )

    assert result == 0
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert capsys.readouterr().out == p1.render_table(report)
