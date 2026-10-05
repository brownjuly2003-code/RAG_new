"""What the decision rule can show at a given size: the formulas of plan step 1.3c."""

from __future__ import annotations

import math

import pytest

from evaluation import power
from evaluation.semantic_ruler import paired_comparison

SINGLETONS_100 = [1] * 100


def _binomial_tail(n: int, p: float, at_least: int) -> float:
    return sum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(at_least, n + 1))


def test_mde_is_the_illustration_of_the_spec() -> None:
    # «at n = 100 and v = 0.10–0.20 that is 0.089–0.125»
    low = power.mde(power.standard_error(0.10, SINGLETONS_100, 0.0), 100)
    high = power.mde(power.standard_error(0.20, SINGLETONS_100, 0.0), 100)
    assert round(low, 3) == 0.089 and round(high, 3) == 0.125
    assert power.critical(100) == pytest.approx(1.959964, abs=1e-6)


def test_power_at_the_mde_is_the_registered_power() -> None:
    se = power.standard_error(0.15, SINGLETONS_100, 0.0)
    assert power.power_lower_bound(se, 100, power.mde(se, 100), 0.0) == pytest.approx(0.8)
    # A neutral mechanism passes −0.02 with power 0.8 only when the MDE itself is 0.02.
    small = 0.02 / (power.critical(100) + 0.8416212335729143)
    assert power.power_lower_bound(small, 100, 0.0, power.MARGIN) == pytest.approx(0.8)
    assert power.power_lower_bound(se, 100, 0.0, power.MARGIN) < 0.1


def test_the_whole_rule_at_the_minimally_useful_effect_holds_half_the_time() -> None:
    # The interval is narrow enough that the point condition binds: P(point ≥ 0.05 | 0.05) = 0.5.
    se = 0.02
    assert power.critical(100) * se < power.MUE
    assert power.power_primary_rule(se, 100, power.MUE) == pytest.approx(0.5)
    # A wide interval: the lower end binds and the composite equals the gain check.
    wide = 0.04
    assert power.power_primary_rule(wide, 100, 0.2) == pytest.approx(
        power.power_lower_bound(wide, 100, 0.2, 0.0)
    )


def test_design_effect_runs_from_cases_to_clusters() -> None:
    sizes = [4] * 25
    assert power.design_effect(sizes, 0.0) == 1.0
    assert power.design_effect(sizes, 1.0) == 4.0
    # With full correlation only the clusters count: the error is that of 25 units.
    assert power.standard_error(0.1, sizes, 1.0) == pytest.approx(math.sqrt(0.1 / 25))
    assert power.design_effect([94, 2, 2, 2], 1.0) == pytest.approx((94**2 + 12) / 100)
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        power.design_effect(sizes, 1.5)
    with pytest.raises(ValueError, match="positive"):
        power.design_effect([3, 0], 0.5)


def test_fewer_than_ten_clusters_read_the_student_quantile() -> None:
    assert power.critical(10) == pytest.approx(1.959964, abs=1e-6)
    assert power.critical(5) == pytest.approx(2.776445, abs=1e-5)
    assert power.critical(2) == pytest.approx(12.7062, abs=1e-3)
    with pytest.raises(ValueError, match="two clusters"):
        power.critical(1)
    se = power.standard_error(0.1, [25] * 4, 0.0)
    assert power.mde(se, 4) > power.mde(se, 40)


def test_validity_probability_is_the_binomial_tail_for_independent_cases() -> None:
    # 100 singletons: ten differing pairs give ten clusters and more than 5 % of the pairs.
    expected = _binomial_tail(100, 0.05, 10)
    assert power.validity_probability(SINGLETONS_100, 0.05) == pytest.approx(expected)
    assert power.validity_probability(SINGLETONS_100, 0.0) == 0.0
    assert power.validity_probability(SINGLETONS_100, 1.0) == pytest.approx(1.0)


def test_validity_needs_ten_clusters_whatever_the_cases() -> None:
    assert power.validity_probability([20] * 9, 1.0) == 0.0
    assert power.validity_probability([10] * 10, 1.0) == pytest.approx(1.0)
    # Ten clusters of ten: every cluster must hold a differing pair.
    every = (1 - 0.9**10) ** 10
    assert power.validity_probability([10] * 10, 0.1) == pytest.approx(every)
    # The 5 % share binds where the clusters do not: 30 singletons need 2 pairs, but 10 clusters.
    assert power.validity_probability([1] * 30, 0.2) == pytest.approx(_binomial_tail(30, 0.2, 10))
    with pytest.raises(ValueError, match="share"):
        power.validity_probability([1] * 30, 1.2)


def test_zero_losses_bound_the_margin_only_from_149_cases() -> None:
    assert power.cases_for_zero_loss_bound() == 149


def test_pair_variance_separates_the_cases_from_the_clusters() -> None:
    families = {"a": ["f1"], "b": ["f1"], "c": ["f2"], "d": ["f2"], "e": ["f3"], "x": ["f9"]}
    differences = {"a": 1.0, "b": 1.0, "c": 0.0, "d": 0.0, "e": 0.0}
    measured = power.pair_variance(differences, families)
    assert measured["n"] == 5 and measured["clusters"] == 3
    assert measured["cluster_sizes"] == [2, 2, 1]
    assert measured["mean"] == pytest.approx(0.4)
    assert measured["variance"] == pytest.approx(0.3)
    assert measured["differing_pairs"] == 2 and measured["nonzero_clusters"] == 1
    assert measured["differing_share"] == pytest.approx(0.4)
    # Cases of one cluster move together: the clusters carry all of the variance.
    assert measured["intraclass_correlation"] == 1.0
    assert measured["design_effect"] > 1
    # The effective variance is the one behind the rule's own cluster-robust interval.
    rule = paired_comparison(
        {key: 0.0 for key in differences}, differences, families, resamples=200
    )
    radius = (rule["t_ci95"][1] - rule["t_ci95"][0]) / 2
    se = math.sqrt(measured["effective_variance"] / measured["n"])
    assert radius == pytest.approx(power.critical(3) * se)


def test_pair_variance_refuses_what_it_cannot_describe() -> None:
    with pytest.raises(ValueError, match="no paired differences"):
        power.pair_variance({}, {})
    with pytest.raises(ValueError, match="missing family mapping"):
        power.pair_variance({"a": 0.5}, {})
    alone = power.pair_variance({"a": 0.5}, {"a": ["f"]})
    assert alone["variance"] is None and alone["effective_variance"] is None
    assert alone["intraclass_correlation"] is None and alone["design_effect"] is None
    singletons = power.pair_variance(
        {"a": 1.0, "b": 0.0, "c": 0.0}, {"a": ["f1"], "b": ["f2"], "c": ["f3"]}
    )
    assert singletons["intraclass_correlation"] is None
    assert singletons["design_effect"] == pytest.approx(1.0)


def test_intraclass_correlation_is_zero_when_clusters_explain_nothing() -> None:
    groups = [["a", "b"], ["c", "d"], ["e", "f"]]
    values = {"a": 1.0, "b": 0.0, "c": 1.0, "d": 0.0, "e": 1.0, "f": 0.0}
    assert power.intraclass_correlation(values, groups) == 0.0
    assert power.intraclass_correlation({key: 0.0 for key in values}, groups) is None


def test_scenario_row_carries_the_checks_of_the_rule() -> None:
    row = power.scenario(0.1, [4] * 25, 0.5, differing_share=0.1)
    assert row["n"] == 100 and row["clusters"] == 25
    assert row["design_effect"] == pytest.approx(2.5)
    assert row["mde"] == pytest.approx(
        (power.critical(25) + 0.8416212335729143) * math.sqrt(0.1 * 2.5 / 100)
    )
    assert row["power_gain_at_mde"] == pytest.approx(0.8)
    assert row["effect_for_noninferiority"] == pytest.approx(row["mde"] - 0.02)
    assert 0 < row["power_noninferiority_at_zero"] < row["power_gain_at_mue"] < 0.8
    assert 0 < row["interval_validity_upper_bound"] < 1
    assert "differing_share" not in power.scenario(0.1, [4] * 25, 0.5)


def test_a_row_may_take_the_student_quantile_at_any_number_of_clusters() -> None:
    # Clusters that move as one case each: the sample is the clusters, not the cases.
    assert power.critical(18) == pytest.approx(1.959963984540054)
    assert power.critical(18, student=True) == pytest.approx(2.1098, abs=1e-4)
    assert power.critical(8, student=True) == power.critical(8)
    normal = power.scenario(0.1, [4] * 18, 1.0)
    student = power.scenario(0.1, [4] * 18, 1.0, student=True)
    assert student["standard_error"] == normal["standard_error"]
    assert student["critical"] == power.critical(18, student=True)
    assert student["mde"] == pytest.approx(
        (student["critical"] + 0.8416212335729143) * student["standard_error"]
    )
    assert student["mde"] > normal["mde"]
    assert student["power_gain_at_mde"] == pytest.approx(0.8)
    assert student["power_noninferiority_at_zero"] < normal["power_noninferiority_at_zero"]
    assert student["power_rule_at_mue"] < normal["power_rule_at_mue"]


def test_the_correlation_estimate_is_published_as_it_comes_out_too() -> None:
    # Cases of a cluster differ more than cases of different clusters: a negative estimate.
    families = {key: [key[0]] for key in ("a1", "a2", "b1", "b2", "c1", "c2")}
    differences = {"a1": 1.0, "a2": 0.0, "b1": 1.0, "b2": 0.0, "c1": 0.0, "c2": 1.0}
    measured = power.pair_variance(differences, families)
    assert measured["intraclass_correlation"] == 0.0
    assert measured["intraclass_correlation_unclamped"] == pytest.approx(-1.0)
    alone = power.pair_variance({"a1": 0.5}, families)
    assert alone["intraclass_correlation_unclamped"] is None
