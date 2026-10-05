"""What the registered decision rule can show at a given size (plan step 1.3c).

The decision rule of ``docs/specs/semantic-precision-metrics.md`` reads an interval of the
mean paired difference between an arm and the control. Before any run, this module answers what
such an interval can show: it takes the interval as ``mean ± critical × standard error``, where
the standard error comes from the per-case variance of paired differences, the number of cases
and a design effect for cases that share a cluster. With fewer than ten clusters the Student
quantile with ``clusters - 1`` degrees of freedom takes the place of the normal one, as the
interval-validity rule does. The powers are normal approximations: they describe the rule, they
do not replace the cluster bootstrap that decides a comparison.

Nothing here reads a result of a mechanism. The inputs are a variance, cluster sizes and an
intra-cluster correlation; ``pair_variance`` measures the first and the last on a pilot.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import NormalDist
from typing import Any

from evaluation.semantic_ruler import clopper_pearson_upper, family_clusters, student_t_critical

POWER = 0.8
MUE = 0.05
MARGIN = -0.02
MIN_NONZERO_CLUSTERS = 10
MIN_DIFFERING_SHARE = 0.05
_NORMAL = NormalDist()
_Z_TWO_SIDED = _NORMAL.inv_cdf(0.975)


def pair_variance(
    differences: Mapping[str, float], families: Mapping[str, Sequence[str]]
) -> dict[str, Any]:
    """Describe the paired differences of a pilot: their variance and what the clusters add.

    ``effective_variance`` is the per-case variance that gives the cluster-robust variance of
    the mean when divided by n — the same residual sum the decision rule's t-interval uses.
    """
    if not differences:
        raise ValueError("no paired differences")
    if not set(differences) <= set(families):
        raise ValueError("missing family mapping")
    groups = [
        [key for key in group if key in differences]
        for group in family_clusters(families)
        if any(key in differences for key in group)
    ]
    n, count = len(differences), len(groups)
    mean = math.fsum(differences.values()) / n
    variance = (
        math.fsum((value - mean) ** 2 for value in differences.values()) / (n - 1)
        if n > 1
        else None
    )
    effective = None
    if count > 1:
        residuals = [math.fsum(differences[key] - mean for key in group) for group in groups]
        effective = count / (count - 1) * math.fsum(r * r for r in residuals) / n
    differing = sum(value != 0 for value in differences.values())
    return {
        "n": n,
        "clusters": count,
        "cluster_sizes": sorted((len(group) for group in groups), reverse=True),
        "mean": mean,
        "variance": variance,
        "effective_variance": effective,
        "design_effect": effective / variance if effective is not None and variance else None,
        "intraclass_correlation": intraclass_correlation(differences, groups),
        "differing_pairs": differing,
        "differing_share": differing / n,
        "nonzero_clusters": sum(
            math.fsum(differences[key] for key in group) != 0 for group in groups
        ),
    }


def intraclass_correlation(
    values: Mapping[str, float], groups: Sequence[Sequence[str]]
) -> float | None:
    """One-way analysis-of-variance estimate, kept inside [0, 1]; None when it has no basis.

    It needs a cluster with two cases and two clusters. On a pilot of a few multi-case clusters
    the estimate is rough; the published tables bracket it with 0 and 1.
    """
    n, count = sum(len(group) for group in groups), len(groups)
    if count < 2 or n <= count:
        return None
    mean = math.fsum(values[key] for group in groups for key in group) / n
    means = [math.fsum(values[key] for key in group) / len(group) for group in groups]
    paired = list(zip(groups, means, strict=True))
    between = math.fsum(len(group) * (group_mean - mean) ** 2 for group, group_mean in paired) / (
        count - 1
    )
    within = math.fsum(
        (values[key] - group_mean) ** 2 for group, group_mean in paired for key in group
    ) / (n - count)
    typical = (n - math.fsum(len(group) ** 2 for group in groups) / n) / (count - 1)
    denominator = between + (typical - 1) * within
    if denominator <= 0:
        return None
    return min(1.0, max(0.0, (between - within) / denominator))


def design_effect(cluster_sizes: Sequence[int], icc: float) -> float:
    """Variance inflation of a mean over clusters of these sizes: ``1 + (Σm²/n − 1)·icc``."""
    if not cluster_sizes or any(size < 1 for size in cluster_sizes):
        raise ValueError("cluster sizes must be positive")
    if not 0 <= icc <= 1:
        raise ValueError("the intra-cluster correlation lies in [0, 1]")
    n = sum(cluster_sizes)
    return 1 + (math.fsum(size * size for size in cluster_sizes) / n - 1) * icc


def critical(clusters: int) -> float:
    """Two-sided 95 % quantile: normal from ten clusters on, Student below, as the rule reads."""
    if clusters < 2:
        raise ValueError("an interval needs at least two clusters")
    return _Z_TWO_SIDED if clusters >= MIN_NONZERO_CLUSTERS else student_t_critical(clusters - 1)


def standard_error(variance: float, cluster_sizes: Sequence[int], icc: float) -> float:
    if variance < 0:
        raise ValueError("a variance is not negative")
    return math.sqrt(variance * design_effect(cluster_sizes, icc) / sum(cluster_sizes))


def mde(se: float, clusters: int, power: float = POWER) -> float:
    """Smallest true effect whose interval lies above zero with this power."""
    return (critical(clusters) + _NORMAL.inv_cdf(power)) * se


def power_lower_bound(se: float, clusters: int, effect: float, bound: float) -> float:
    """P(lower end of the interval ≥ bound) at a true effect: the gain and the NI checks."""
    if se == 0:
        return float(effect >= bound)
    return _NORMAL.cdf((effect - bound) / se - critical(clusters))


def power_primary_rule(se: float, clusters: int, effect: float, minimum: float = MUE) -> float:
    """P(point ≥ the minimally useful effect and the lower end > 0) at a true effect."""
    threshold = max(minimum, critical(clusters) * se)
    if se == 0:
        return float(effect >= threshold)
    return 1 - _NORMAL.cdf((threshold - effect) / se)


def validity_probability(cluster_sizes: Sequence[int], differing_share: float) -> float:
    """P(the interval-validity rule holds) when each pair differs independently with this chance.

    The rule asks for ten clusters with a non-zero difference and for 5 % of pairs to differ.
    A cluster counts here as soon as one of its pairs differs, so differences that cancel
    inside a cluster make the true probability lower, as does a mechanism that changes cases of
    the same clusters together.
    """
    if not 0 <= differing_share <= 1:
        raise ValueError("a share lies in [0, 1]")
    n = sum(cluster_sizes)
    needed = math.ceil(MIN_DIFFERING_SHARE * n - 1e-12)
    states: dict[tuple[int, int], float] = {(0, 0): 1.0}
    for size in cluster_sizes:
        pmf = [
            math.comb(size, k) * differing_share**k * (1 - differing_share) ** (size - k)
            for k in range(size + 1)
        ]
        following: dict[tuple[int, int], float] = {}
        for (clusters, pairs), mass in states.items():
            for k, chance in enumerate(pmf):
                if chance:
                    key = (min(clusters + (k > 0), MIN_NONZERO_CLUSTERS), min(pairs + k, needed))
                    following[key] = following.get(key, 0.0) + mass * chance
        states = following
    return states.get((MIN_NONZERO_CLUSTERS, needed), 0.0)


def cases_for_zero_loss_bound(margin: float = -MARGIN) -> int:
    """Cases a metric needs so that zero observed losses bound its loss rate by the margin."""
    n = 1
    while clopper_pearson_upper(0, n) > margin:
        n += 1
    return n


def scenario(
    variance: float,
    cluster_sizes: Sequence[int],
    icc: float,
    *,
    differing_share: float | None = None,
) -> dict[str, Any]:
    """One published row: what a design of these clusters shows for a metric of this variance."""
    clusters = len(cluster_sizes)
    se = standard_error(variance, cluster_sizes, icc)
    detectable = mde(se, clusters)
    row: dict[str, Any] = {
        "n": sum(cluster_sizes),
        "clusters": clusters,
        "variance": variance,
        "intraclass_correlation": icc,
        "design_effect": design_effect(cluster_sizes, icc),
        "standard_error": se,
        "critical": critical(clusters),
        "mde": detectable,
        "power_gain_at_mue": power_lower_bound(se, clusters, MUE, 0.0),
        "power_gain_at_mde": power_lower_bound(se, clusters, detectable, 0.0),
        "power_rule_at_mue": power_primary_rule(se, clusters, MUE),
        "power_rule_at_mde": power_primary_rule(se, clusters, detectable),
        "power_noninferiority_at_zero": power_lower_bound(se, clusters, 0.0, MARGIN),
        "effect_for_noninferiority": detectable + MARGIN,
    }
    if differing_share is not None:
        row["differing_share"] = differing_share
        row["interval_validity_probability"] = validity_probability(cluster_sizes, differing_share)
    return row
