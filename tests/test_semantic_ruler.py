"""Registered semantic ruler contracts, independent of the P2 publication."""

import math

import pytest

from evaluation import semantic_ruler as ruler


def test_precision_populations_and_ndcg_ideal():
    grades = {"a": 3, "b": 1, "c": 2, "d": 3}
    assert ruler.precision_at_5(["a", "b"], grades) == 0.2
    assert ruler.sent_precision(["c"], grades) == 1
    assert ruler.sent_precision([], grades) == 0
    ideal = 3 + 3 / math.log2(3) + 2 / math.log2(4) + 1 / math.log2(5)
    assert ruler.ndcg_at_5(["b", "a", "a"], grades) == pytest.approx((1 + 3 / math.log2(3)) / ideal)
    assert ruler.ndcg_at_5(["a"], {"a": 0}) is None
    with pytest.raises(ValueError, match="unjudged"):
        ruler.sent_precision(["missing"], grades)


@pytest.mark.parametrize("metric", [ruler.precision_at_5, ruler.ndcg_at_5])
def test_top_five_seed_positions_do_not_pull_in_the_sixth_document(metric):
    seeds = ["a", "a", "b", "c", "d", "e"]
    grades = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 3}
    assert metric(seeds, grades) == 0
    assert (
        ruler.precision_at_5(seeds, {key: value for key, value in grades.items() if key != "e"})
        == 0
    )


@pytest.mark.parametrize("metric", [ruler.precision_at_5, ruler.ndcg_at_5])
def test_top_five_duplicate_is_a_zero_gain_rank(metric):
    grades = {"a": 3, "b": 2, "c": 0, "d": 0, "e": 3}
    seeds = ["a", "a", "b", "c", "d", "e"]
    ideal = 3 + 3 / math.log2(3) + 2 / math.log2(4)
    expected = 0.4 if metric is ruler.precision_at_5 else (3 + 2 / math.log2(4)) / ideal
    assert metric(seeds, grades) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("marker", "subject", "unit", "context", "expected"),
    [
        ("allowed", "cargo", "kg", "cargo not allowed 150 kg", 0),
        ("allowed", "cargo", "kg", "cargo disallowed 150 kg", 0),
        ("allowed", "cargo", "kg", "cargo unallowed 150 kg", 0),
        ("allowed", "cargo", "kg", "cargo allowed and forbidden 150 kg", 0),
        ("разрешено", "груз", "кг", "груз 150 кг разрешено", 1),
        ("разрешено", "груз", "кг", "груз 150 кг запрещено", 0),
        ("разрешено", "груз", "кг", "груз 150 кг не разрешено", 0),
        ("запрещено", "груз", "кг", "груз 150 кг запрещено", 1),
        ("не более", "груз", "кг", "груз не более 150 кг", 0),
        ("не более", "груз", "кг", "груз не менее 150 кг", 0),
        ("не менее", "груз", "кг", "груз не менее 150 кг", 0),
        ("только при", "груз", "кг", "груз 150 кг только при согласовании", 1),
    ],
)
def test_numeric_fact_polarity_uses_word_boundaries_and_negation(
    marker, subject, unit, context, expected
):
    fact = ruler.Fact(subject, marker, "", 150, unit)
    assert ruler.fact_coverage([fact], context) == expected


@pytest.mark.parametrize(
    "context", ["cargo not allowed 150 kg", "cargo allowed and disallowed 150 kg"]
)
def test_numeric_fact_ambiguous_polarity_reports_pending_blind_judgment(context):
    facts = [ruler.Fact("cargo", "allowed", "", 150, "kg")]
    pending = []
    assert ruler.fact_coverage(facts, context, needs_blind_judgment=pending) == 0
    assert pending == [0]
    for judgment in (False, True):
        pending = []
        assert ruler.fact_coverage(
            facts, context, blind_judgments={0: judgment}, needs_blind_judgment=pending
        ) == float(judgment)
        assert pending == []


@pytest.mark.parametrize(
    ("metric", "provisional_judge", "required"),
    [
        ("citation_correctness", True, True),
        ("citation_correctness", False, True),
        ("faithfulness", True, True),
        ("faithfulness", False, False),
    ],
)
def test_deciding_rule_requires_the_registered_human_check(metric, provisional_judge, required):
    rule = ruler.deciding_rules("sent_precision")[metric]
    arguments = {"provisional_judge": provisional_judge}
    expected = "INCONCLUSIVE" if required else "PASS"
    assert ruler.check_rule(rule, 0.1, [0.01, 0.2], **arguments) == expected
    assert (
        ruler.check_rule(rule, 0.1, [0.01, 0.2], human_check_passed=None, **arguments) == expected
    )
    assert ruler.check_rule(rule, 0.1, [0.01, 0.2], human_check_passed=True, **arguments) == "PASS"
    assert (
        ruler.check_rule(rule, 0.1, [0.01, 0.2], human_check_passed=False, **arguments) == "NO_SHIP"
    )


def test_deciding_rule_missing_human_check_is_not_passed_by_default():
    rules = ruler.deciding_rules("sent_precision")
    for metric in ("citation_correctness", "faithfulness"):
        assert ruler.check_rule(rules[metric], 0.1, [0.01, 0.2]) == "INCONCLUSIVE"


def test_family_components_join_multifamily_cases():
    mapping = {"a": ["x"], "b": ["x", "y"], "c": ["y"], "d": ["z"]}
    assert ruler.family_clusters(mapping) == [("a", "b", "c"), ("d",)]


def test_cluster_bootstrap_keeps_equal_case_weights():
    values = {"a": 0.0, "b": 0.0, "c": 1.0}
    summary = ruler.cluster_summary(values, {"a": ["x"], "b": ["x"], "c": ["y"]})
    assert summary["point"] == pytest.approx(1 / 3)
    assert summary["ci95"] == [0, 1]
    assert summary["clusters"] == 2
    assert summary == ruler.cluster_summary(values, {"a": ["x"], "b": ["x"], "c": ["y"]})


def test_paired_degenerate_cp_and_registered_invariance():
    values = {str(i): 0.5 for i in range(100)}
    families = {key: [key] for key in values}
    result = ruler.paired_comparison(values, values, families)
    assert result["verdict"] == "INCONCLUSIVE"
    upper = 1 - 0.05 ** (1 / 100)
    assert result["loss_rate_upper95"] == pytest.approx(upper)
    assert result["implied_metric_lower95"] == pytest.approx(-upper)
    assert result["nonzero_clusters"] == 0
    invariant = ruler.paired_comparison(values, values, families, structurally_invariant=True)
    assert invariant["verdict"] == "PASS"
    one_family = {key: ["same"] for key in values}
    assert (
        ruler.paired_comparison(values, values, one_family, structurally_invariant=True)["verdict"]
        == "PASS"
    )
    changed = dict(values, **{"0": 0.4})
    with pytest.raises(ValueError, match="invariant"):
        ruler.paired_comparison(values, changed, families, structurally_invariant=True)


def test_paired_validity_requires_both_thresholds():
    control = {str(i): 0.0 for i in range(200)}
    families = {key: [key] for key in control}
    arm = {key: (0.1 if int(key) < 10 else 0.0) for key in control}
    assert ruler.paired_comparison(control, arm, families)["interval_valid"] is True
    arm["9"] = 0
    assert ruler.paired_comparison(control, arm, families)["interval_valid"] is False
    dense = {key: 0.1 for key in control}
    grouped = {key: [str(int(key) % 9)] for key in control}
    result = ruler.paired_comparison(control, dense, grouped)
    assert result["interval_valid"] is False
    assert result["t_ci95"] is not None
    assert result["verdict"] == "INCONCLUSIVE"


def test_cp_and_small_cluster_t_against_known_values():
    assert ruler.clopper_pearson_upper(1, 10) == pytest.approx(0.3941633024)
    assert ruler.clopper_pearson_upper(10, 10) == 1
    assert ruler.student_t_critical(1) == pytest.approx(12.706204736, rel=1e-8)
    assert ruler.student_t_critical(9) == pytest.approx(2.262157163, rel=1e-8)


def test_cancelling_differences_within_families_are_degenerate():
    control = {str(i): 0.5 for i in range(20)}
    arm = {key: (0.6 if int(key) % 2 else 0.4) for key in control}
    families = {key: [str(int(key) // 2)] for key in control}
    result = ruler.paired_comparison(control, arm, families)
    assert result["ci95"] == [0, 0]
    assert result["nonzero_clusters"] == 0
    assert result["interval_valid"] is False
    assert result["verdict"] == "INCONCLUSIVE"


def test_single_arm_with_one_cluster_has_no_interval_to_offer():
    values = {str(i): (1.0 if i % 4 else 0.0) for i in range(20)}
    summary = ruler.single_arm_summary(values, {key: ["same"] for key in values})
    assert summary["point"] == pytest.approx(0.75)
    assert (summary["n"], summary["clusters"], summary["cluster_sizes"]) == (20, 1, [20])
    assert summary["ci95"] == pytest.approx([0.75, 0.75])
    assert summary["t_ci95"] == [0.0, 1.0]
    assert summary["ci95_conservative"] == [0.0, 1.0]
    low, high = summary["case_bootstrap_ci95"]
    assert low < 0.75 < high


def test_single_arm_under_ten_clusters_prints_the_t_interval_and_reads_the_wider_bound():
    means = {"a": 0.5, "b": 0.52, "c": 0.48, "d": 0.5}
    values = {f"{name}{i}": mean for name, mean in means.items() for i in range(25)}
    families = {key: [key[0]] for key in values}
    summary = ruler.single_arm_summary(values, families)
    radius = ruler.student_t_critical(3) * math.sqrt(4 / 3 * 0.5) / 100
    assert summary["point"] == pytest.approx(0.5)
    assert (summary["clusters"], summary["cluster_sizes"]) == (4, [25, 25, 25, 25])
    assert summary["t_ci95"] == pytest.approx([0.5 - radius, 0.5 + radius])
    assert summary["ci95_conservative"] == [
        min(summary["ci95"][0], summary["t_ci95"][0]),
        max(summary["ci95"][1], summary["t_ci95"][1]),
    ]
    assert summary["case_bootstrap_ci95"][1] - summary["case_bootstrap_ci95"][0] < 2 * radius
    wide = ruler.single_arm_summary({"a": 1.0, "b": 0.0, "c": 1.0}, {k: [k] for k in "abc"})
    assert wide["t_ci95"] == [0.0, 1.0]


def test_single_arm_with_ten_clusters_keeps_the_bootstrap_alone():
    values = {str(i): i / 10 for i in range(10)}
    summary = ruler.single_arm_summary(values, {key: [key] for key in values})
    assert summary["clusters"] == 10
    assert summary["t_ci95"] is None
    assert summary["ci95_conservative"] == summary["ci95"] == summary["case_bootstrap_ci95"]


def test_single_arm_counts_only_cases_that_have_a_value():
    families = {"a": ["x"], "b": ["x"], "c": ["y"], "d": ["z"]}
    summary = ruler.single_arm_summary({"a": 1.0, "c": 0.0}, families)
    assert (summary["n"], summary["clusters"], summary["cluster_sizes"]) == (2, 2, [1, 1])
    with pytest.raises(ValueError, match="bounded"):
        ruler.single_arm_summary({"a": 1.5}, families)
    with pytest.raises(ValueError, match="family mapping"):
        ruler.single_arm_summary({"e": 0.5}, families)


def test_gold_spans_groups_and_fact_matcher():
    span = ruler.GoldSpan("s", "v1", 0, 10, "required text")
    chunk = ruler.EvidenceChunk("s", "v1", "required text", 0, 10)
    other = ruler.EvidenceChunk("s", "v2", "required text", 0, 10)
    assert ruler.evidence_recall_pool([span], [chunk]) == 1
    assert ruler.evidence_recall_pool([span], [other]) == 0
    assert ruler.all_evidence_coverage([[span], [span]], [chunk]) == 1
    assert ruler.all_evidence_coverage([[span]], []) == 0
    fallback = ruler.EvidenceChunk("s", "v1", " Required   text ")
    assert ruler.evidence_recall_pool([span], [fallback]) == 1
    fact = ruler.Fact("cargo", "allowed", "", 150, "kg", tolerance=0.1)
    assert ruler.fact_coverage([fact], "cargo allowed 150.05 kg") == 1
    assert ruler.fact_coverage([fact], "cargo forbidden 150 kg") == 0
    assert ruler.fact_coverage([fact], "passenger allowed 150 kg") == 0
    assert ruler.fact_coverage([ruler.Fact("", "", "required text")], "Required text") == 1
    assert ruler.fact_coverage([], "") is None


def test_closed_deciding_table_and_coverage_point_rule():
    rules = ruler.deciding_rules("sent_precision")
    assert len(rules) == 14
    assert "ndcg_at_5" not in rules
    assert rules["retrieve_p95"].direction == "lower"
    assert rules["critical_errors"].interval == "none"
    assert (
        rules["citation_correctness"].denominator
        == "citations made; no-citation cases counted separately"
    )
    assert ruler.check_rule(rules["sent_precision"], 0.05, [0.001, 0.1]) == "PASS"
    assert ruler.check_rule(rules["sent_precision"], 0.049, [0.001, 0.1]) == "INCONCLUSIVE"
    assert ruler.check_rule(rules["precision_at_5"], 0, [-0.02, 0.01]) == "PASS"
    assert ruler.check_rule(rules["all_evidence_coverage"], -0.001, [-0.01, 0.01]) == "NO_SHIP"
    assert ruler.check_rule(rules["fact_coverage"], 0.1, [0, 0.2], critical_loss=True) == "NO_SHIP"
    assert ruler.check_rule(rules["retrieve_p95"], 100, [50, 201]) == "INCONCLUSIVE"
    assert ruler.deciding_rules("all_evidence_coverage")["all_evidence_coverage"].check == "primary"


def test_common_pair_mask_and_dropped_pair_guard():
    control = {str(i): 0.5 for i in range(20)}
    arm = {key: (None if int(key) < 3 else value) for key, value in control.items()}
    result = ruler.paired_comparison(control, arm, {key: [key] for key in control})
    assert result["n"] == 17
    assert result["dropped_arm"] == 3
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["worst_case_delta"] == pytest.approx(-0.15)
