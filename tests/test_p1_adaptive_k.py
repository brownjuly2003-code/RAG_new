"""Tests for P1 adaptive-k cut rules: cell names, cut-rule counts, artifact loading."""

import math

import pytest

from scripts import p1_adaptive_k as p1
from scripts import rerank_score_capture


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
