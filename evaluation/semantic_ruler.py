"""Pre-registered development ruler; no runtime defaults or product gates change."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation import blinded_judge as p2

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261001
RESAMPLES = 10_000
FACT_MATCHER_VERSION = "semantic-ruler/claim-window-v3"
POLARITY_LEXICON = {
    "allowed": ("allowed", "permitted", "разрешено"),
    "forbidden": ("forbidden", "disallowed", "prohibited", "запрещено"),
    "at_most": ("at most", "не более"),
    "at_least": ("at least", "не менее"),
    "only_if": ("only if", "только при"),
}


def _grades(ids: Sequence[str], grades: Mapping[str, int]) -> list[int]:
    if any(key not in grades for key in ids):
        raise ValueError("unjudged document in deciding population")
    values = [grades[key] for key in ids]
    if any(type(value) is not int or not 0 <= value <= 3 for value in values):
        raise ValueError("grades must be integers 0-3")
    return values


def _seed_grades(seeds: Sequence[str], grades: Mapping[str, int]) -> list[int]:
    values = _grades(seeds[:5], grades)
    return [value if seeds[rank] not in seeds[:rank] else 0 for rank, value in enumerate(values)]


def precision_at_5(seeds: Sequence[str], grades: Mapping[str, int]) -> float:
    return sum(value >= 2 for value in _seed_grades(seeds, grades)) / 5


def sent_precision(sent: Sequence[str], grades: Mapping[str, int]) -> float:
    return sum(value >= 2 for value in _grades(sent, grades)) / len(sent) if sent else 0.0


def ndcg_at_5(seeds: Sequence[str], grades: Mapping[str, int]) -> float | None:
    def dcg(values: Sequence[int]) -> float:
        return math.fsum(value / math.log2(rank + 2) for rank, value in enumerate(values))

    ideal = dcg(sorted(_grades(list(grades), grades), reverse=True)[:5])
    return dcg(_seed_grades(seeds, grades)) / ideal if ideal else None


@dataclass(frozen=True)
class GoldSpan:
    source_id: str
    corpus_version: str
    char_start: int | None
    char_end: int | None
    normalized_text: str


@dataclass(frozen=True)
class EvidenceChunk:
    source_id: str
    corpus_version: str
    text: str
    char_start: int | None = None
    char_end: int | None = None


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _span_present(span: GoldSpan, chunks: Sequence[EvidenceChunk]) -> bool:
    for chunk in chunks:
        if (span.source_id, span.corpus_version) != (chunk.source_id, chunk.corpus_version):
            continue
        if (
            span.char_start is not None
            and span.char_end is not None
            and chunk.char_start is not None
            and chunk.char_end is not None
        ):
            if chunk.char_start <= span.char_start and chunk.char_end >= span.char_end:
                return True
        elif span.normalized_text and _normalized(span.normalized_text) in _normalized(chunk.text):
            return True
    return False


def evidence_recall_pool(gold: Sequence[GoldSpan], pool: Sequence[EvidenceChunk]) -> float | None:
    return sum(_span_present(span, pool) for span in gold) / len(gold) if gold else None


def all_evidence_coverage(
    groups: Sequence[Sequence[GoldSpan]], sent: Sequence[EvidenceChunk]
) -> float | None:
    return (
        float(all(any(_span_present(span, sent) for span in group) for group in groups))
        if groups
        else None
    )


@dataclass(frozen=True)
class Fact:
    subject: str
    polarity: str
    text: str
    value: float | None = None
    unit: str = ""
    condition: str = ""
    tolerance: float = 0.0


def _polarity_matches(window: str, polarity: str) -> bool | None:
    window = window.translate(str.maketrans("’‘ʼ", "'''"))
    if re.search(
        r"\b(?:not|no|never|neither|nor|cannot|without|except|unless|не|нет|ни|никогда|без|кроме)\b"
        r"|\b\w+n't\b",
        window,
    ):
        return None
    lexicon = {marker: key for key, markers in POLARITY_LEXICON.items() for marker in markers}
    expected = lexicon.get(_normalized(polarity))
    pattern = r"(?<!\w)(?:" + "|".join(re.escape(marker) for marker in lexicon) + r")(?!\w)"
    matches = list(re.finditer(pattern, window))
    if expected is None or not matches:
        return None
    observed = {lexicon[match.group()] for match in matches}
    return expected in observed if len(observed) == 1 else None


def fact_coverage(
    facts: Sequence[Fact],
    context: str,
    *,
    blind_judgments: Mapping[int, bool] | None = None,
    needs_blind_judgment: list[int] | None = None,
) -> float | None:
    """Registered containment/claim matcher; ambiguous facts require blind judgments.

    Numeric claims match within one sentence and at most 120 characters of the
    number. Polarity uses the registered lexicon with word boundaries. Any negation
    cue or conflicting/unknown markers need blind judgment, including disagreement
    across candidate windows; their unresolved fact
    indices are appended to needs_blind_judgment and do not count as present.
    Critical-fact acceptance remains a blind human check, outside this matcher.
    """
    normalized = _normalized(context)
    present = 0
    for index, fact in enumerate(facts):
        if blind_judgments is not None and index in blind_judgments:
            present += blind_judgments[index]
        elif fact.value is None:
            present += bool(fact.text and _normalized(fact.text) in normalized)
        else:
            polarities: set[bool | None] = set()
            for sentence in re.split(r"[;!?\n]|\.(?!\d)", normalized):
                for match in re.finditer(
                    r"(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w.])\s*"
                    + re.escape(_normalized(fact.unit))
                    + r"(?!\w)",
                    sentence,
                ):
                    number = re.match(r"-?\d+(?:[.,]\d+)?", match.group())
                    assert number is not None
                    window = sentence[max(0, match.start() - 120) : match.end() + 120]
                    if abs(
                        float(number.group().replace(",", ".")) - fact.value
                    ) <= fact.tolerance and all(
                        _normalized(part) in window for part in (fact.subject, fact.condition)
                    ):
                        polarities.add(_polarity_matches(window, fact.polarity))
            if (None in polarities or len(polarities) > 1) and needs_blind_judgment is not None:
                needs_blind_judgment.append(index)
            present += polarities == {True}
    return present / len(facts) if facts else None


def family_clusters(mapping: Mapping[str, Sequence[str]]) -> list[tuple[str, ...]]:
    parents = {key: key for key in mapping}

    def find(key: str) -> str:
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    owners: dict[str, str] = {}
    for case in sorted(mapping):
        if not mapping[case]:
            raise ValueError("each case needs an explicit family")
        for family in mapping[case]:
            if family in owners:
                parents[find(case)] = find(owners[family])
            else:
                owners[family] = case
    groups: dict[str, list[str]] = {}
    for case in sorted(mapping):
        groups.setdefault(find(case), []).append(case)
    return sorted(tuple(group) for group in groups.values())


def _quantile(ordered: Sequence[float], p: float) -> float:
    position = (len(ordered) - 1) * p
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _bootstrap(
    values: Mapping[str, float], clusters: Sequence[Sequence[str]], seed: int, resamples: int
) -> list[float]:
    if resamples < 1:
        raise ValueError("resamples must be positive")
    blocks = [
        (
            math.fsum(values[key] for key in cluster if key in values),
            sum(key in values for key in cluster),
        )
        for cluster in clusters
    ]
    blocks = [block for block in blocks if block[1]]
    if not blocks:
        raise ValueError("no applicable cases")
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        drawn = rng.choices(blocks, k=len(blocks))
        samples.append(math.fsum(block[0] for block in drawn) / sum(block[1] for block in drawn))
    samples.sort()
    return [_quantile(samples, 0.025), _quantile(samples, 0.975)]


def cluster_summary(
    values: Mapping[str, float],
    families: Mapping[str, Sequence[str]],
    *,
    seed: int = SEED,
    resamples: int = RESAMPLES,
) -> dict[str, Any]:
    if not set(values) <= set(families):
        raise ValueError("missing family mapping")
    clusters = family_clusters(families)
    active = [cluster for cluster in clusters if any(key in values for key in cluster)]
    return {
        "point": math.fsum(values.values()) / len(values),
        "ci95": _bootstrap(values, clusters, seed, resamples),
        "n": len(values),
        "clusters": len(active),
    }


def clopper_pearson_upper(losses: int, n: int) -> float:
    if not 0 <= losses <= n or n < 1:
        raise ValueError("invalid binomial counts")
    if losses == n:
        return 1.0
    if losses == 0:
        return -math.expm1(math.log(0.05) / n)
    low, high = 0.0, 1.0
    for _ in range(80):
        p = (low + high) / 2
        cdf = math.fsum(
            math.exp(
                math.lgamma(n + 1)
                - math.lgamma(k + 1)
                - math.lgamma(n - k + 1)
                + k * math.log(p)
                + (n - k) * math.log1p(-p)
            )
            for k in range(losses + 1)
        )
        if cdf > 0.05:
            low = p
        else:
            high = p
    return (low + high) / 2


def _beta_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta (Student t CDF)."""
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = 1 / max(d, 1e-300)
    h = d
    for m in range(1, 201):
        for aa in (
            m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
            -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1)),
        ):
            d = 1 + aa * d
            c = 1 + aa / c
            if abs(d) < 1e-300:
                d = 1e-300
            if abs(c) < 1e-300:
                c = 1e-300
            d = 1 / d
            delta = d * c
            h *= delta
        if abs(delta - 1) < 1e-14:
            break
    return h


def _beta(a: float, b: float, x: float) -> float:
    if x == 0 or x == 1:
        return x
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1) / (a + b + 2):
        return front * _beta_fraction(a, b, x) / a
    return 1 - front * _beta_fraction(b, a, 1 - x) / b


def student_t_critical(df: int) -> float:
    if df < 1:
        raise ValueError("t interval needs at least two clusters")
    low, high = 0.0, 1000.0
    for _ in range(80):
        value = (low + high) / 2
        tail = 0.5 * _beta(df / 2, 0.5, df / (df + value * value))
        if tail > 0.025:
            low = value
        else:
            high = value
    return (low + high) / 2


def paired_comparison(
    control: Mapping[str, float | None],
    arm: Mapping[str, float | None],
    families: Mapping[str, Sequence[str]],
    *,
    seed: int = SEED,
    resamples: int = RESAMPLES,
    structurally_invariant: bool = False,
    margin: float = -0.02,
) -> dict[str, Any]:
    if set(control) != set(arm) or not set(control) <= set(families):
        raise ValueError("register a common population and family mapping")
    differences = {}
    for key, control_value in control.items():
        arm_value = arm[key]
        if arm_value is not None and control_value is not None:
            differences[key] = arm_value - control_value
    if not differences:
        raise ValueError("no valid pairs")
    if any(
        not math.isfinite(v) or not 0 <= v <= 1
        for values in (control, arm)
        for v in values.values()
        if v is not None
    ):
        raise ValueError("paired bounded metrics must lie in [0, 1]")
    clusters = family_clusters(families)
    active = [group for group in clusters if any(key in differences for key in group)]
    n, count = len(differences), len(active)
    nonzero = sum(math.fsum(differences.get(key, 0) for key in group) != 0 for group in active)
    differing = sum(value != 0 for value in differences.values())
    summary = cluster_summary(differences, families, seed=seed, resamples=resamples)
    point = float(summary["point"])
    t_ci: list[float] | None = None
    if count < 10:
        if count == 1:
            t_ci = [-1.0, 1.0]
        else:
            residuals = [
                math.fsum(differences[key] - point for key in group if key in differences)
                for group in active
            ]
            se = math.sqrt(count / (count - 1) * math.fsum(v * v for v in residuals)) / n
            radius = student_t_critical(count - 1) * se
            t_ci = [point - radius, point + radius]
    deciding = list(summary["ci95"])
    if t_ci is not None:
        deciding = [min(deciding[0], t_ci[0]), max(deciding[1], t_ci[1])]
    losses = sum(value < 0 for value in differences.values())
    upper = clopper_pearson_upper(losses, n)
    dropped_control = sum(v is None for v in control.values())
    dropped_arm = sum(v is None for v in arm.values())
    mask_valid = (len(control) - n) / len(control) <= 0.1 and abs(
        dropped_control - dropped_arm
    ) / len(control) <= 0.05
    valid = nonzero >= 10 and differing / n >= 0.05
    if structurally_invariant and differing:
        raise ValueError("registered invariant has observed differences")
    verdict = "INCONCLUSIVE"
    if mask_valid and structurally_invariant:
        verdict = "PASS" if 0 >= margin else "NO_SHIP"
    elif mask_valid and valid:
        verdict = (
            "PASS"
            if deciding[0] >= margin
            else "NO_SHIP"
            if deciding[1] < margin
            else "INCONCLUSIVE"
        )
    return {
        **summary,
        "bootstrap": {"seed": seed, "resamples": resamples, "method": "cluster percentile CI95"},
        "ci95_deciding": deciding,
        "t_ci95": t_ci,
        "nonzero_clusters": nonzero,
        "differing_pairs": differing,
        "differing_share": differing / n,
        "interval_valid": valid,
        "structurally_invariant": structurally_invariant,
        "decision_basis": "registered structural invariance"
        if structurally_invariant
        else "paired intervals",
        "losses": losses,
        "loss_rate_upper95": upper,
        "implied_metric_lower95": -upper,
        "verdict": verdict,
        "dropped_control": dropped_control,
        "dropped_arm": dropped_arm,
        "common_pair_mask": sorted(differences),
        "pair_mask_valid": mask_valid,
        "worst_case_delta": (math.fsum(differences.values()) - (len(control) - n)) / len(control),
    }


@dataclass(frozen=True)
class DecisionRule:
    direction: str
    denominator: str
    check: str
    interval: str = "cluster bootstrap"
    human_check: str = "none"


def deciding_rules(primary: str) -> dict[str, DecisionRule]:
    if primary not in ("sent_precision", "all_evidence_coverage"):
        raise ValueError("register sent_precision or all_evidence_coverage")
    denominators = {
        "sent_precision": "cases with gold evidence",
        "all_evidence_coverage": "cases with gold evidence",
        "precision_at_5": "all judged cases",
        "evidence_recall_pool": "cases with gold spans",
        "fact_coverage": "cases with facts",
        "abstention_correct": "registered unresolvable cases",
        "faithfulness": "answered cases",
        "answer_fact_coverage": "answered cases with facts",
        "citation_correctness": "citations made; no-citation cases counted separately",
        "citation_presence": "answered non-refusal cases",
        "action_correct": "all cases; per action class reported",
        "context_precision": "H",
    }
    rules = {
        name: DecisionRule(
            "higher",
            denominator,
            "primary"
            if name == primary
            else "coverage_ni"
            if name == "all_evidence_coverage"
            else "ni",
            human_check="always"
            if name == "citation_correctness"
            else "provisional_judge"
            if name == "faithfulness"
            else "none",
        )
        for name, denominator in denominators.items()
    }
    rules["critical_errors"] = DecisionRule("fewer", "all cases", "new_error_blocks", "none")
    rules["retrieve_p95"] = DecisionRule(
        "lower",
        "all cases; warm-up excluded, interleaved arms, >=3 repeats per case",
        "latency",
        "bootstrap over cases",
    )
    return rules


def check_rule(
    rule: DecisionRule,
    point: float,
    ci95: Sequence[float],
    *,
    interval_valid: bool = True,
    critical_loss: bool = False,
    full_to_part_miss: bool = False,
    human_check_passed: bool | None = None,
    provisional_judge: bool = True,
) -> str:
    """Consume already masked, valid comparisons; human/critical checks are mandatory inputs."""
    if critical_loss or full_to_part_miss or human_check_passed is False:
        return "NO_SHIP"
    if human_check_passed is None and (
        rule.human_check == "always"
        or (rule.human_check == "provisional_judge" and provisional_judge)
    ):
        return "INCONCLUSIVE"
    if rule.check == "new_error_blocks":
        return "NO_SHIP" if point > 0 else "PASS"
    if not interval_valid:
        return "INCONCLUSIVE"
    if rule.check == "latency":
        return "PASS" if ci95[1] <= 200 else "NO_SHIP" if ci95[0] > 200 else "INCONCLUSIVE"
    if rule.check == "coverage_ni" and point < 0:
        return "NO_SHIP"
    if rule.check == "primary":
        return (
            "PASS"
            if point >= 0.05 and ci95[0] > 0
            else "NO_SHIP"
            if ci95[1] <= 0
            else "INCONCLUSIVE"
        )
    return "PASS" if ci95[0] >= -0.02 else "NO_SHIP" if ci95[1] < -0.02 else "INCONCLUSIVE"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_p2_baseline() -> dict[str, Any]:
    report_path = ROOT / "reports/p2/p2-blinded-judge-glm+sonnet.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    provenances = report["provenance"]["pools"]
    pools = {name: p2._load_pool(ROOT, name, provenances[name]) for name in ("H", "Hm")}
    inputs = p2.Inputs(pools, {}, float(report["control"]["H_top_k_5"]), report, {}, {})
    paths: list[Path] = []
    replies = {}
    for judge in ("glm", "sonnet"):
        entry = report["provenance"]["judge_routes"][judge]["reply_files"][0]
        path = ROOT / "reports/p2/replies" / Path(entry["path"]).name
        if _sha(path) != entry["sha256"]:
            raise ValueError("P2 reply digest mismatch")
        paths.append(path)
        replies[judge] = {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path)}
    requests = {
        (case.pool, case.case_id): p2.build_request(case).sha256
        for pool in pools.values()
        for case in pool.cases
    }
    grades_by_pool, _ = p2._current_grades(inputs, p2.merge_stores(paths, requests))
    results = {}
    for name, pool in pools.items():
        ids = [case.case_id for case in pool.cases]
        consensus, excluded = p2.consensus_grades(ids, grades_by_pool[name])
        if excluded or set(consensus) != set(ids):
            raise ValueError("P2 baseline requires both judges on every case")
        dataset = [
            json.loads(line)
            for line in (ROOT / provenances[name]["dataset"])
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        mapping = {
            str(row["case_id"]): [json.dumps(row["tags"][:2], ensure_ascii=False)]
            if name == "H"
            else list(row["source_documents"])
            for row in dataset
        }
        metrics: dict[str, Any] = {}
        values: dict[str, dict[str, float]] = {
            metric: {}
            for metric in ("precision_at_5", "sent_precision", "ndcg_at_5", "context_precision")
        }
        for case in pool.cases:
            doc_ids = [f"D{i}" for i in range(5)]
            grades = dict(zip(doc_ids, consensus[case.case_id], strict=True))
            values["precision_at_5"][case.case_id] = precision_at_5(doc_ids, grades)
            values["sent_precision"][case.case_id] = sent_precision(doc_ids, grades)
            ndcg = ndcg_at_5(doc_ids, grades)
            if ndcg is not None:
                values["ndcg_at_5"][case.case_id] = ndcg
            values["context_precision"][case.case_id] = pool.ruler_per_case[case.case_id]
        for metric, per_case in values.items():
            metrics[metric] = {
                **cluster_summary(per_case, mapping),
                "excluded": len(ids) - len(per_case),
            }
        for metric in ("evidence_recall_pool", "all_evidence_coverage", "fact_coverage"):
            metrics[metric] = {
                "point": "N/A",
                "reason": "P2 has no approved gold spans, required evidence groups or atomic facts",
                "n": 0,
            }
        results[name] = {
            "case_count": len(ids),
            "cluster_unit": {
                "status": "provisional, replaced by the 1.3a family register",
                "basis": "tags pair (topic)"
                if name == "H"
                else "source_documents connected components",
                "mapping": mapping,
                "components": [list(component) for component in family_clusters(mapping)],
                "count": len(family_clusters(mapping)),
            },
            "per_case": values,
            "metrics": metrics,
        }
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, timeout=10
    ).strip()
    files = (
        "evaluation/semantic_ruler.py",
        "evaluation/blinded_judge.py",
        "evaluation/blinded_judge_clients.py",
    )
    return {
        "schema_version": "semantic-ruler-p2/v1",
        "evidence_class": "development-baseline",
        "provisional_ruler": True,
        "population": "Phase-C unexpanded top-5 reranked seeds, P2 top_k_5; sent context is the same five documents. NOT the production-expansion path (slice 2.5).",
        "grade_source": "P2 lower-median consensus GLM 5.3 + Sonnet 5; human grades absent",
        "config": {
            "resamples": RESAMPLES,
            "seed": SEED,
            "interval": "percentile CI95, linear quantiles",
            "weights": "equal case weights",
            "gain": "grade",
            "relevant_grade_min": 2,
            "top_k": 5,
            "context_chars": 6000,
            "production_expansion": False,
            "RAG_RERANK_BATCH": {name: provenances[name]["batch_size"] for name in pools},
            "official_context_precision_gate": 0.63,
            "fact_matcher_version": FACT_MATCHER_VERSION,
        },
        "provenance": {
            "code_commit": commit,
            "tree_clean": not bool(status),
            "code_files": {name: _sha(ROOT / name) for name in files},
            "cli_file": "evaluation/semantic_ruler.py",
            "p2_report": report_path.relative_to(ROOT).as_posix(),
            "p2_report_sha256": _sha(report_path),
            "pools": provenances,
            "reply_files": replies,
            "instruction_sha256": report["provenance"]["instruction_sha256"],
        },
        "pools": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["p2-baseline"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(
        json.dumps(build_p2_baseline(), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
