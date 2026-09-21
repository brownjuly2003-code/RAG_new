#!/usr/bin/env python3
"""GR-3 graph-lane A/B report: retrieval, parity, latency, paired generation, default."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ab_context_precision import (  # noqa: E402
    DEFAULT_CORPUS_MANIFEST_PATH,
    DEFAULT_DATASET_PATH,
    DEFAULT_LABEL_MANIFEST_PATH,
    DEFAULT_MULTI_DOC_DATASET_PATH,
    DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    DEFAULT_MULTI_DOC_SIDECAR_PATH,
    DEFAULT_SIDECAR_PATH,
    PHASE_C_CONTEXT_CHARS,
    PHASE_C_TOP_K,
    _bucket_row,
    _bucket_rows_by_class,
    _metric_delta,
    _nearest_rank,
    score_cases_by_class,
    sha256_file,
)
from scripts.generator_benchmark import load_benchmark_cases  # noqa: E402

SCHEMA_VERSION = "gr-graph-lane-ab/v1.0"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "gr" / "gr3-graph-lane-ab.json"
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 20260918
RETRIEVE_P95_BUDGET_MS = 200.0

PHASE_C_QUALITY_ARMS: tuple[str, ...] = ("H", "Hm", "G1", "G2")
BUCKET_QUALITY_ARMS: tuple[str, ...] = ("Hm", "G1", "G2")
PHASE_C_DELTA_PAIRS: tuple[tuple[str, str], ...] = (
    ("G1", "Hm"),
    ("G2", "Hm"),
    ("G2", "G1"),
    ("G1", "H"),
    ("G2", "H"),
    ("Hm", "H"),
)
BUCKET_DELTA_PAIRS: tuple[tuple[str, str], ...] = (
    ("G1", "Hm"),
    ("G2", "Hm"),
    ("G2", "G1"),
)
LOSS_TRANSITIONS: tuple[str, ...] = ("FULL->PART", "FULL->MISS", "PART->MISS")
PARITY_FIELDS: tuple[str, ...] = (
    "prerank_cands",
    "prerank_sources",
    "reranked_cands",
    "reranked_sources",
    "cands",
    "cand_sources",
    "top-5 cands",
    "top-5 cand_sources",
)
GENERATION_METRICS: tuple[str, ...] = (
    "llm_faithfulness",
    "nli_faithfulness",
    "nli_supported_claim_rate",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "latency_ms",
)
LOCKED_PROVENANCE: tuple[str, ...] = (
    "dataset_sha256",
    "ollama_model",
    "ollama_model_digest",
    "nli_model",
    "nli_revision",
)
LOCKED_CONFIG: tuple[str, ...] = (
    "prompt_version",
    "runs",
    "expected_cases",
    "selected_cases",
    "top_k_override",
    "context_chars",
    "seed_base",
    "temperature",
    "num_ctx",
    "num_predict",
    "nli_batch_size",
    "nli_support_threshold",
)
CRITERION_NAMES: tuple[str, ...] = (
    "precision_rose",
    "full_not_fallen",
    "llm_faithfulness_not_significantly_fallen",
    "nli_faithfulness_not_significantly_fallen",
    "retrieve_p95_within_200ms",
)
HYBRID_TIMING_KEYS: tuple[str, ...] = ("vector", "bm25")
GRAPH_TIMING_KEYS: tuple[str, ...] = ("vector", "bm25", "entity")
_EMPTY_CELL = "—"


def _load_pool(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"{path}: expected a JSON array of objects")
    return payload


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def _stored_manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return f"<external>/{resolved.name}"


def _corpus_from_manifest(path: Path) -> dict[str, Any]:
    payload = _load_object(path)
    missing = [key for key in ("corpus_sha256", "file_count") if payload.get(key) is None]
    if missing:
        raise ValueError(f"{path}: corpus manifest missing {', '.join(missing)}")
    return {
        "manifest": _stored_manifest_path(path),
        "manifest_sha256": sha256_file(path),
        "name": payload.get("name"),
        "root": payload.get("root"),
        "corpus_sha256": payload.get("corpus_sha256"),
        "file_count": payload.get("file_count"),
    }


def _as_pool_rows(value: Path | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, Path):
        return _load_pool(value)
    return [dict(row) for row in value]


def _pair_key(left: str, right: str) -> str:
    return f"{left}-{right}"


def _score_arm(
    label: str,
    *,
    pool_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    expected_cases: int,
    top_k: int,
    context_chars: int,
) -> dict[str, Any]:
    try:
        rows, _approved = score_cases_by_class(
            pool_path=pool_path,
            dataset_path=dataset_path,
            sidecar_path=sidecar_path,
            label_manifest_path=label_manifest_path,
            expected_cases=expected_cases,
            top_k=top_k,
            context_chars=context_chars,
            allow_short_contexts=True,
        )
        loaded = load_benchmark_cases(
            dataset_path=dataset_path,
            contexts_path=pool_path,
            expected_cases=expected_cases,
            top_k=top_k,
            context_chars=context_chars,
            allow_short_contexts=True,
        )
    except Exception as exc:
        raise ValueError(f"{label}: {exc}") from exc
    characters = [sum(len(text) for text in case["contexts"]) for case in loaded]
    return {
        "rows": rows,
        "buckets": _bucket_rows_by_class(rows),
        "all_cases": _bucket_row("all cases", rows),
        "mean_contexts": round(statistics.fmean(row["n_docs"] for row in rows), 4),
        "mean_characters": round(statistics.fmean(characters), 1) if characters else None,
    }


def _arm_public(scored: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "buckets": scored["buckets"],
        "all_cases": scored["all_cases"],
        "mean_contexts": scored["mean_contexts"],
        "mean_characters": scored["mean_characters"],
    }


def _delta_rows(minuend: Mapping[str, Any], subtrahend: Mapping[str, Any]) -> list[dict[str, Any]]:
    other = {row["question_class"]: row for row in subtrahend["buckets"]}
    rows = []
    for row in minuend["buckets"]:
        baseline = other[row["question_class"]]
        rows.append(
            {
                "question_class": row["question_class"],
                "context_precision": _metric_delta(
                    baseline["context_precision"],
                    row["context_precision"],
                ),
                "context_recall": _metric_delta(
                    baseline["context_recall"],
                    row["context_recall"],
                ),
            }
        )
    rows.append(
        {
            "question_class": "all cases",
            "context_precision": _metric_delta(
                subtrahend["all_cases"]["context_precision"],
                minuend["all_cases"]["context_precision"],
            ),
            "context_recall": _metric_delta(
                subtrahend["all_cases"]["context_recall"],
                minuend["all_cases"]["context_recall"],
            ),
        }
    )
    return rows


def _keyword_transitions(
    baseline_rows: Sequence[Mapping[str, Any]],
    new_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_new = {row["case_id"]: row for row in new_rows}
    counts: dict[str, int] = {}
    losses: dict[str, list[str]] = {name: [] for name in LOSS_TRANSITIONS}
    for row in baseline_rows:
        other = by_new[row["case_id"]]
        key = f"{row['kw_status']}->{other['kw_status']}"
        counts[key] = counts.get(key, 0) + 1
        if key in losses:
            losses[key].append(str(row["case_id"]))
    return {
        "counts": dict(sorted(counts.items())),
        "loss_case_ids": {name: sorted(ids) for name, ids in losses.items()},
    }


def retrieval_ab(
    *,
    arms: Mapping[str, Path],
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    expected_cases: int,
    pairs: Sequence[tuple[str, str]],
    top_k: int = PHASE_C_TOP_K,
    context_chars: int = PHASE_C_CONTEXT_CHARS,
) -> dict[str, Any]:
    """Score every quality arm on one dataset and publish paired deltas."""
    scored: dict[str, dict[str, Any]] = {}
    for label, pool_path in arms.items():
        scored[label] = _score_arm(
            label,
            pool_path=pool_path,
            dataset_path=dataset_path,
            sidecar_path=sidecar_path,
            label_manifest_path=label_manifest_path,
            expected_cases=expected_cases,
            top_k=top_k,
            context_chars=context_chars,
        )
    deltas: dict[str, list[dict[str, Any]]] = {}
    transitions: dict[str, dict[str, Any]] = {}
    for minuend_name, subtrahend_name in pairs:
        key = _pair_key(minuend_name, subtrahend_name)
        deltas[key] = _delta_rows(scored[minuend_name], scored[subtrahend_name])
        transitions[key] = _keyword_transitions(
            scored[subtrahend_name]["rows"],
            scored[minuend_name]["rows"],
        )
    return {
        "arms": {name: _arm_public(scored[name]) for name in arms},
        "deltas": deltas,
        "keyword_transitions": transitions,
    }


def _parity_value(row: Mapping[str, Any], field: str) -> Any:
    if field == "top-5 cands":
        cands = row.get("cands")
        return None if cands is None else list(cands)[:5]
    if field == "top-5 cand_sources":
        sources = row.get("cand_sources")
        return None if sources is None else list(sources)[:5]
    return row.get(field)


def pool_parity(
    new: Path | Sequence[Mapping[str, Any]],
    published: Path | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Case-by-case candidate/source comparison. Divergence never raises."""
    new_rows = _as_pool_rows(new)
    published_rows = _as_pool_rows(published)
    new_ids = [str(row.get("case_id") or "") for row in new_rows]
    published_ids = [str(row.get("case_id") or "") for row in published_rows]
    new_by_id = {str(row.get("case_id") or ""): row for row in new_rows}
    published_by_id = {str(row.get("case_id") or ""): row for row in published_rows}
    only_new = sorted(set(new_ids) - set(published_ids))
    only_published = sorted(set(published_ids) - set(new_ids))
    shared = sorted(set(new_ids) & set(published_ids))
    fields: dict[str, dict[str, Any]] = {}
    for field in PARITY_FIELDS:
        divergent = [
            case_id
            for case_id in shared
            if _parity_value(new_by_id[case_id], field)
            != _parity_value(published_by_id[case_id], field)
        ]
        fields[field] = {"count": len(divergent), "case_ids": divergent}
    identical = (
        not only_new
        and not only_published
        and new_ids == published_ids
        and all(item["count"] == 0 for item in fields.values())
    )
    return {
        "identical": identical,
        "only_new": only_new,
        "only_published": only_published,
        "fields": fields,
    }


def _finite_non_negative(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value >= 0


def _sum_timing(timing: Mapping[str, Any]) -> float:
    return float(sum(float(value) for value in timing.values()))


def _timing_row_missing(timing: Any, required_keys: Sequence[str]) -> bool:
    if not isinstance(timing, dict) or not timing:
        return True
    if any(key not in timing for key in required_keys):
        return True
    return any(not _finite_non_negative(value) for value in timing.values())


def _ms_summary(values: Sequence[float], *, missing: bool) -> dict[str, float | None]:
    if missing or not values:
        return {"p50": None, "p95": None}
    return {
        "p50": round(float(_nearest_rank(values, numerator=1, denominator=2)), 1),
        "p95": round(float(_nearest_rank(values, numerator=19, denominator=20)), 1),
    }


def _arm_latency(
    rows: Sequence[Mapping[str, Any]], *, required_keys: Sequence[str]
) -> dict[str, Any]:
    pools: list[float] = []
    rerank: list[float] = []
    totals: list[float] = []
    missing_timing = False
    missing_rerank = False
    for row in rows:
        timing = row.get("timing_ms")
        rerank_s = row.get("rerank_s")
        pools_ms: float | None = None
        rerank_ms: float | None = None
        if _timing_row_missing(timing, required_keys):
            missing_timing = True
        else:
            assert isinstance(timing, dict)
            pools_ms = _sum_timing(timing)
            pools.append(pools_ms)
        if isinstance(rerank_s, bool) or not isinstance(rerank_s, (int, float)):
            missing_rerank = True
        else:
            rerank_ms = 1000.0 * float(rerank_s)
            rerank.append(rerank_ms)
        if pools_ms is not None and rerank_ms is not None:
            totals.append(pools_ms + rerank_ms)
    return {
        "cases": len(rows),
        "pools_ms": _ms_summary(pools, missing=missing_timing),
        "rerank_ms": _ms_summary(rerank, missing=missing_rerank),
        "total_ms": _ms_summary(totals, missing=missing_timing or missing_rerank),
    }


def _sorted_case_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(str(row.get("case_id") or "") for row in rows)


def _require_timing_case_ids(label: str, arm_ids: Sequence[str], hybrid_ids: Sequence[str]) -> None:
    if list(arm_ids) == list(hybrid_ids):
        return
    arm_counts = Counter(arm_ids)
    hybrid_counts = Counter(hybrid_ids)
    differing = sorted(
        case_id
        for case_id in set(arm_counts) | set(hybrid_counts)
        if arm_counts[case_id] != hybrid_counts[case_id]
    )
    named = ", ".join(differing[:5])
    raise ValueError(f"{label}: timing pool case-id set differs from hybrid: {named}")


def latency(*, hybrid: Path, g1: Path, g2: Path) -> dict[str, Any]:
    """Pools + rerank latency for the same-run Hm / G1m / G2m arms, in milliseconds."""
    hybrid_rows = _load_pool(hybrid)
    g1_rows = _load_pool(g1)
    g2_rows = _load_pool(g2)
    hybrid_ids = _sorted_case_ids(hybrid_rows)
    _require_timing_case_ids("G1", _sorted_case_ids(g1_rows), hybrid_ids)
    _require_timing_case_ids("G2", _sorted_case_ids(g2_rows), hybrid_ids)
    arms = {
        "hybrid": _arm_latency(hybrid_rows, required_keys=HYBRID_TIMING_KEYS),
        "G1": _arm_latency(g1_rows, required_keys=GRAPH_TIMING_KEYS),
        "G2": _arm_latency(g2_rows, required_keys=GRAPH_TIMING_KEYS),
    }

    def _delta(arm: str) -> float | None:
        left = arms[arm]["total_ms"]["p95"]
        right = arms["hybrid"]["total_ms"]["p95"]
        if left is None or right is None:
            return None
        return round(float(left) - float(right), 1)

    return {
        **arms,
        "p95_total_delta_ms": {"G1": _delta("G1"), "G2": _delta("G2")},
    }


def _require_same(field: str, left: Any, right: Any) -> None:
    if left != right:
        raise ValueError(f"{field} differs: hybrid={left!r} graph={right!r}")


def _case_ids(report: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for run in report.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        for case in run.get("cases", []):
            if isinstance(case, Mapping) and case.get("case_id"):
                ids.add(str(case["case_id"]))
    return ids


def _rows_by_case(report: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for run in report.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        for case in run.get("cases", []):
            if not isinstance(case, Mapping) or not case.get("case_id"):
                continue
            by_case.setdefault(str(case["case_id"]), []).append(dict(case))
    return by_case


def _case_valid(row: Mapping[str, Any]) -> bool:
    return bool(row.get("generation_valid") and row.get("llm_judge_valid") and row.get("nli_valid"))


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _case_metric(row: Mapping[str, Any], metric: str) -> float:
    scores = _as_mapping(row.get("scores"))
    nli = _as_mapping(row.get("nli"))
    if metric == "llm_faithfulness":
        return float(scores["faithfulness"])
    if metric == "nli_faithfulness":
        return float(nli["nli_faithfulness"])
    if metric == "nli_supported_claim_rate":
        return float(nli["supported_claim_rate"])
    if metric == "answer_relevancy":
        return float(scores["answer_relevancy"])
    if metric == "context_precision":
        return float(scores["context_precision"])
    if metric == "context_recall":
        return float(scores["context_recall"])
    if metric == "latency_ms":
        return float(row["latency_ms"])
    raise ValueError(f"unknown metric {metric}")


def _evidence_class(report: Mapping[str, Any]) -> str | None:
    value = report.get("evidence_class")
    return None if value is None else str(value)


def _evidence_reasons(report: Mapping[str, Any]) -> list[str]:
    value = report.get("evidence_reasons")
    return [str(reason) for reason in value] if isinstance(value, list) else []


def _mean_context_count(report: Mapping[str, Any]) -> float | None:
    values: list[float] = []
    for run in report.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        for case in run.get("cases", []):
            if not isinstance(case, Mapping) or "context_count" not in case:
                continue
            value = case["context_count"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            values.append(float(value))
    if not values:
        return None
    return round(statistics.fmean(values), 4)


def paired_generation(
    hybrid_report: Mapping[str, Any],
    graph_report: Mapping[str, Any],
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired case-level percentile bootstrap of graph − hybrid generation metrics."""
    if hybrid_report.get("kind") != "phase-c-generator-benchmark":
        raise ValueError(f"kind: hybrid={hybrid_report.get('kind')!r}")
    if graph_report.get("kind") != "phase-c-generator-benchmark":
        raise ValueError(f"kind: graph={graph_report.get('kind')!r}")

    hybrid_prov = hybrid_report.get("provenance")
    graph_prov = graph_report.get("provenance")
    if not isinstance(hybrid_prov, Mapping):
        raise ValueError("provenance")
    if not isinstance(graph_prov, Mapping):
        raise ValueError("provenance")
    hybrid_config = hybrid_prov.get("config")
    graph_config = graph_prov.get("config")
    if not isinstance(hybrid_config, Mapping):
        raise ValueError("config")
    if not isinstance(graph_config, Mapping):
        raise ValueError("config")

    for field in LOCKED_PROVENANCE:
        _require_same(field, hybrid_prov.get(field), graph_prov.get(field))
    _require_same("ollama_think", hybrid_prov.get("ollama_think"), graph_prov.get("ollama_think"))
    for field in LOCKED_CONFIG:
        _require_same(field, hybrid_config.get(field), graph_config.get(field))
    _require_same("think", hybrid_config.get("think"), graph_config.get("think"))

    hybrid_ids = _case_ids(hybrid_report)
    graph_ids = _case_ids(graph_report)
    if hybrid_ids != graph_ids:
        raise ValueError(
            "case ids differ: "
            f"only hybrid={sorted(hybrid_ids - graph_ids)[:5]} "
            f"only graph={sorted(graph_ids - hybrid_ids)[:5]}"
        )

    hybrid_by_case = _rows_by_case(hybrid_report)
    graph_by_case = _rows_by_case(graph_report)
    n_hybrid_runs = len(hybrid_report.get("runs") or [])
    n_graph_runs = len(graph_report.get("runs") or [])
    excluded: list[str] = []
    included: list[str] = []
    for case_id in sorted(hybrid_ids):
        hybrid_rows = hybrid_by_case.get(case_id, [])
        graph_rows = graph_by_case.get(case_id, [])
        comparable = (
            len(hybrid_rows) == n_hybrid_runs
            and len(graph_rows) == n_graph_runs
            and all(_case_valid(row) for row in hybrid_rows)
            and all(_case_valid(row) for row in graph_rows)
        )
        if comparable:
            included.append(case_id)
        else:
            excluded.append(case_id)

    rng = random.Random(seed)
    n = len(included)
    metrics: dict[str, Any] = {}
    for metric in GENERATION_METRICS:
        if n == 0:
            metrics[metric] = {
                "hybrid_mean": None,
                "graph_mean": None,
                "mean_difference": None,
                "ci_low": None,
                "ci_high": None,
                "ci_high_raw": None,
                "better": 0,
                "worse": 0,
                "equal": 0,
            }
            continue
        hybrid_values = [
            statistics.fmean(_case_metric(row, metric) for row in hybrid_by_case[case_id])
            for case_id in included
        ]
        graph_values = [
            statistics.fmean(_case_metric(row, metric) for row in graph_by_case[case_id])
            for case_id in included
        ]
        diffs = [
            graph_value - hybrid_value
            for graph_value, hybrid_value in zip(graph_values, hybrid_values, strict=True)
        ]
        means: list[float] = []
        for _resample in range(resamples):
            sample = [diffs[rng.randrange(n)] for _ in range(n)]
            means.append(statistics.fmean(sample))
        better = sum(
            1
            for graph_value, hybrid_value in zip(graph_values, hybrid_values, strict=True)
            if graph_value > hybrid_value
        )
        worse = sum(
            1
            for graph_value, hybrid_value in zip(graph_values, hybrid_values, strict=True)
            if graph_value < hybrid_value
        )
        ci_high_raw = float(_nearest_rank(means, numerator=39, denominator=40))
        metrics[metric] = {
            "hybrid_mean": round(statistics.fmean(hybrid_values), 4),
            "graph_mean": round(statistics.fmean(graph_values), 4),
            "mean_difference": round(statistics.fmean(diffs), 4),
            "ci_low": round(float(_nearest_rank(means, numerator=1, denominator=40)), 4),
            "ci_high": round(ci_high_raw, 4),
            "ci_high_raw": ci_high_raw,
            "better": better,
            "worse": worse,
            "equal": n - better - worse,
        }

    hybrid_aggregate = hybrid_report.get("aggregate")
    graph_aggregate = graph_report.get("aggregate")
    return {
        "method": "paired case-level percentile bootstrap",
        "resamples": resamples,
        "seed": seed,
        "cases": n,
        "excluded_case_ids": excluded,
        "hybrid_evidence_class": _evidence_class(hybrid_report),
        "graph_evidence_class": _evidence_class(graph_report),
        "hybrid_evidence_reasons": _evidence_reasons(hybrid_report),
        "graph_evidence_reasons": _evidence_reasons(graph_report),
        "metrics": metrics,
        "hybrid_aggregate": dict(hybrid_aggregate)
        if isinstance(hybrid_aggregate, Mapping)
        else None,
        "graph_aggregate": dict(graph_aggregate) if isinstance(graph_aggregate, Mapping) else None,
        "graph_mean_context_count": _mean_context_count(graph_report),
    }


def _dig(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _criterion(status: str, **values: Any) -> dict[str, Any]:
    return {"status": status, "passed": status == "pass", **values}


def decide(report: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the GR-3 default-flip rule to a built report."""
    g2_precision = _dig(report, "phase_c", "arms", "G2", "all_cases", "context_precision")
    h_precision = _dig(report, "phase_c", "arms", "H", "all_cases", "context_precision")
    if g2_precision is None or h_precision is None:
        precision = _criterion(
            "not_measured",
            g2_precision=g2_precision,
            h_precision=h_precision,
        )
    else:
        precision = _criterion(
            "pass" if g2_precision > h_precision else "fail",
            g2_precision=g2_precision,
            h_precision=h_precision,
        )

    g2_full = _dig(report, "phase_c", "arms", "G2", "all_cases", "FULL")
    h_full = _dig(report, "phase_c", "arms", "H", "all_cases", "FULL")
    if g2_full is None or h_full is None:
        full = _criterion("not_measured", g2_full=g2_full, h_full=h_full)
    else:
        full = _criterion(
            "pass" if g2_full >= h_full else "fail",
            g2_full=g2_full,
            h_full=h_full,
        )

    def _faithfulness(name: str) -> dict[str, Any]:
        ci_high = _dig(report, "generation", "metrics", name, "ci_high")
        ci_high_raw = _dig(report, "generation", "metrics", name, "ci_high_raw")
        mean_difference = _dig(report, "generation", "metrics", name, "mean_difference")
        if report.get("generation") is not None:
            hybrid_class = _dig(report, "generation", "hybrid_evidence_class")
            graph_class = _dig(report, "generation", "graph_evidence_class")
            if hybrid_class != "measured" or graph_class != "measured":
                return _criterion(
                    "not_evidence",
                    ci_high=ci_high,
                    ci_high_raw=ci_high_raw,
                    mean_difference=mean_difference,
                    hybrid_evidence_class=hybrid_class,
                    graph_evidence_class=graph_class,
                )
        if ci_high_raw is None:
            return _criterion(
                "not_measured",
                ci_high=ci_high,
                ci_high_raw=ci_high_raw,
                mean_difference=mean_difference,
            )
        return _criterion(
            "pass" if ci_high_raw >= 0 else "fail",
            ci_high=ci_high,
            ci_high_raw=ci_high_raw,
            mean_difference=mean_difference,
        )

    llm = _faithfulness("llm_faithfulness")
    nli = _faithfulness("nli_faithfulness")

    g2_p95 = _dig(report, "latency", "phase_c", "G2", "total_ms", "p95")
    hybrid_p95 = _dig(report, "latency", "phase_c", "hybrid", "total_ms", "p95")
    host = _dig(report, "latency", "host")
    if g2_p95 is None or hybrid_p95 is None:
        retrieve = _criterion(
            "not_measured",
            g2_p95_total_ms=g2_p95,
            hybrid_p95_total_ms=hybrid_p95,
            delta_ms=None,
            threshold_ms=RETRIEVE_P95_BUDGET_MS,
            host=host,
        )
    else:
        delta_ms = round(float(g2_p95) - float(hybrid_p95), 1)
        retrieve = _criterion(
            "pass" if delta_ms <= RETRIEVE_P95_BUDGET_MS else "fail",
            g2_p95_total_ms=g2_p95,
            hybrid_p95_total_ms=hybrid_p95,
            delta_ms=delta_ms,
            threshold_ms=RETRIEVE_P95_BUDGET_MS,
            host=host,
        )

    criteria = {
        "precision_rose": precision,
        "full_not_fallen": full,
        "llm_faithfulness_not_significantly_fallen": llm,
        "nli_faithfulness_not_significantly_fallen": nli,
        "retrieve_p95_within_200ms": retrieve,
    }
    failed = [name for name in CRITERION_NAMES if not criteria[name]["passed"]]
    generation_missing = report.get("generation") is None
    if generation_missing:
        verdict = "PENDING_GENERATION"
    elif failed:
        verdict = "NO_SHIP_TO_DEFAULT"
    else:
        verdict = "AUTO_DEFAULT_AUTHORIZED"
    return {
        "verdict": verdict,
        "failed_criteria": failed,
        "criteria": criteria,
    }


def build_gr3_report(
    *,
    phase_c_h: Path,
    phase_c_hm: Path,
    phase_c_g1: Path,
    phase_c_g2: Path,
    phase_c_g1m: Path,
    phase_c_g2m: Path,
    bucket_hm: Path,
    bucket_g1: Path,
    bucket_g2: Path,
    bucket_g1m: Path,
    bucket_g2m: Path,
    code_commit: str,
    host: str,
    evidence_class: str,
    hybrid_generation: Path | None = None,
    graph_generation: Path | None = None,
    phase_c_dataset: Path = DEFAULT_DATASET_PATH,
    phase_c_sidecar: Path = DEFAULT_SIDECAR_PATH,
    phase_c_label_manifest: Path = DEFAULT_LABEL_MANIFEST_PATH,
    phase_c_corpus_manifest: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    bucket_dataset: Path = DEFAULT_MULTI_DOC_DATASET_PATH,
    bucket_sidecar: Path = DEFAULT_MULTI_DOC_SIDECAR_PATH,
    bucket_label_manifest: Path = DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    bucket_corpus_manifest: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    expected_cases: int = 100,
    bucket_expected_cases: int = 15,
    top_k: int = PHASE_C_TOP_K,
    context_chars: int = PHASE_C_CONTEXT_CHARS,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Build the GR-3 report from archived pools and optional generation reports."""
    if (hybrid_generation is None) ^ (graph_generation is None):
        raise ValueError("pass both hybrid_generation and graph_generation, or neither")

    phase_c = retrieval_ab(
        arms={
            "H": phase_c_h,
            "Hm": phase_c_hm,
            "G1": phase_c_g1,
            "G2": phase_c_g2,
        },
        dataset_path=phase_c_dataset,
        sidecar_path=phase_c_sidecar,
        label_manifest_path=phase_c_label_manifest,
        expected_cases=expected_cases,
        pairs=PHASE_C_DELTA_PAIRS,
        top_k=top_k,
        context_chars=context_chars,
    )
    multi_doc_bucket = retrieval_ab(
        arms={
            "Hm": bucket_hm,
            "G1": bucket_g1,
            "G2": bucket_g2,
        },
        dataset_path=bucket_dataset,
        sidecar_path=bucket_sidecar,
        label_manifest_path=bucket_label_manifest,
        expected_cases=bucket_expected_cases,
        pairs=BUCKET_DELTA_PAIRS,
        top_k=top_k,
        context_chars=context_chars,
    )
    parity = {
        "phase_c": {
            "Hm_vs_H": pool_parity(phase_c_hm, phase_c_h),
            "G1m_vs_G1": pool_parity(phase_c_g1m, phase_c_g1),
            "G2m_vs_G2": pool_parity(phase_c_g2m, phase_c_g2),
        },
        "multi_doc_bucket": {
            "G1m_vs_G1": pool_parity(bucket_g1m, bucket_g1),
            "G2m_vs_G2": pool_parity(bucket_g2m, bucket_g2),
        },
    }
    latency_block = {
        "host": host,
        "phase_c": latency(hybrid=phase_c_hm, g1=phase_c_g1m, g2=phase_c_g2m),
        "multi_doc_bucket": latency(hybrid=bucket_hm, g1=bucket_g1m, g2=bucket_g2m),
    }
    generation: dict[str, Any] | None = None
    if hybrid_generation is not None and graph_generation is not None:
        generation = paired_generation(
            _load_object(hybrid_generation),
            _load_object(graph_generation),
            resamples=bootstrap_resamples,
            seed=bootstrap_seed,
        )

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": evidence_class,
        "phase_c": phase_c,
        "multi_doc_bucket": multi_doc_bucket,
        "parity": parity,
        "latency": latency_block,
        "generation": generation,
        "decision": {},
        "provenance": {
            "inputs": {
                "phase_c_h": sha256_file(phase_c_h),
                "phase_c_hm": sha256_file(phase_c_hm),
                "phase_c_g1": sha256_file(phase_c_g1),
                "phase_c_g2": sha256_file(phase_c_g2),
                "phase_c_g1m": sha256_file(phase_c_g1m),
                "phase_c_g2m": sha256_file(phase_c_g2m),
                "bucket_hm": sha256_file(bucket_hm),
                "bucket_g1": sha256_file(bucket_g1),
                "bucket_g2": sha256_file(bucket_g2),
                "bucket_g1m": sha256_file(bucket_g1m),
                "bucket_g2m": sha256_file(bucket_g2m),
                "phase_c_dataset": sha256_file(phase_c_dataset),
                "phase_c_sidecar": sha256_file(phase_c_sidecar),
                "phase_c_label_manifest": sha256_file(phase_c_label_manifest),
                "phase_c_corpus_manifest": sha256_file(phase_c_corpus_manifest),
                "bucket_dataset": sha256_file(bucket_dataset),
                "bucket_sidecar": sha256_file(bucket_sidecar),
                "bucket_label_manifest": sha256_file(bucket_label_manifest),
                "bucket_corpus_manifest": sha256_file(bucket_corpus_manifest),
            },
            "phase_c": {
                "dataset_sha256": sha256_file(phase_c_dataset),
                "sidecar_sha256": sha256_file(phase_c_sidecar),
                "label_manifest_sha256": sha256_file(phase_c_label_manifest),
                "corpus_manifest_sha256": sha256_file(phase_c_corpus_manifest),
                "corpus": _corpus_from_manifest(phase_c_corpus_manifest),
            },
            "multi_doc_bucket": {
                "dataset_sha256": sha256_file(bucket_dataset),
                "sidecar_sha256": sha256_file(bucket_sidecar),
                "label_manifest_sha256": sha256_file(bucket_label_manifest),
                "corpus_manifest_sha256": sha256_file(bucket_corpus_manifest),
                "corpus": _corpus_from_manifest(bucket_corpus_manifest),
            },
            "code_commit": code_commit,
            "host": host,
            "config": {
                "top_k": top_k,
                "context_chars": context_chars,
                "bootstrap_resamples": bootstrap_resamples,
                "bootstrap_seed": bootstrap_seed,
            },
        },
    }
    if hybrid_generation is not None:
        report["provenance"]["inputs"]["hybrid_generation"] = sha256_file(hybrid_generation)
    if graph_generation is not None:
        report["provenance"]["inputs"]["graph_generation"] = sha256_file(graph_generation)
    report["decision"] = decide(report)
    return report


def write_gr3_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _metric_cell(value: Any) -> str:
    if value is None:
        return _EMPTY_CELL
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _evidence_cell(value: Any) -> str:
    return "none" if value is None else str(value)


def _evidence_line(side: str, generation: Mapping[str, Any]) -> str:
    rendered = _evidence_cell(generation.get(f"{side}_evidence_class"))
    reasons = generation.get(f"{side}_evidence_reasons") or []
    suffix = f" ({'; '.join(str(reason) for reason in reasons)})" if reasons else ""
    return f"{side} evidence: {rendered}{suffix}"


def _fpm(row: Mapping[str, Any]) -> str:
    return f"{row.get('FULL', _EMPTY_CELL)}/{row.get('PART', _EMPTY_CELL)}/{row.get('MISS', _EMPTY_CELL)}"


def _render_dataset(name: str, block: Mapping[str, Any], arm_names: Sequence[str]) -> list[str]:
    lines = [
        f"## {name} retrieval",
        "",
        "| class | "
        + " | ".join(f"{arm} precision | {arm} recall | {arm} FULL/PART/MISS" for arm in arm_names)
        + " |",
        "|" + "|".join(["---"] + ["---:"] * (len(arm_names) * 3)) + "|",
    ]
    class_rows = block["arms"][arm_names[0]]["buckets"]
    for class_row in [*class_rows, {"question_class": "all cases"}]:
        question_class = class_row["question_class"]
        cells = [question_class]
        for arm in arm_names:
            row = (
                block["arms"][arm]["all_cases"]
                if question_class == "all cases"
                else next(
                    item
                    for item in block["arms"][arm]["buckets"]
                    if item["question_class"] == question_class
                )
            )
            cells.extend(
                [
                    _metric_cell(row["context_precision"]),
                    _metric_cell(row["context_recall"]),
                    _fpm(row),
                ]
            )
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(["", "### deltas", ""])
    lines.append("| pair | class | precision | recall |")
    lines.append("|---|---|---:|---:|")
    for pair, rows in block["deltas"].items():
        display = pair.replace("-", " − ")
        for row in rows:
            lines.append(
                f"| {display} | {row['question_class']} | "
                f"{_metric_cell(row['context_precision'])} | "
                f"{_metric_cell(row['context_recall'])} |"
            )
    lines.extend(["", "### contexts handed on", ""])
    lines.append("| arm | mean contexts | mean characters |")
    lines.append("|---|---:|---:|")
    for arm in arm_names:
        item = block["arms"][arm]
        lines.append(
            f"| {arm} | {_metric_cell(item['mean_contexts'])} | {item['mean_characters']} |"
        )
    lines.extend(["", "### keyword transitions", ""])
    for pair, payload in block["keyword_transitions"].items():
        display = pair.replace("-", " − ")
        counts = ", ".join(f"{name}: {count}" for name, count in payload["counts"].items())
        lines.append(f"{display} counts: {counts or 'none'}")
        for name, case_ids in payload["loss_case_ids"].items():
            listed = ", ".join(case_ids) if case_ids else "none"
            lines.append(f"{display} {name}: {listed}")
    return lines


def _render_parity_block(title: str, block: Mapping[str, Any]) -> list[str]:
    lines = [f"### {title}"]
    for name, payload in block.items():
        status = "identical" if payload["identical"] else "divergent"
        lines.append(f"{name}: {status}")
        if payload["only_new"]:
            lines.append(f"{name} only new: {', '.join(payload['only_new'])}")
        if payload["only_published"]:
            lines.append(f"{name} only published: {', '.join(payload['only_published'])}")
        for field, details in payload["fields"].items():
            if details["count"]:
                lines.append(
                    f"{name} {field}: {details['count']} ({', '.join(details['case_ids'])})"
                )
    return lines


def _render_latency_dataset(name: str, block: Mapping[str, Any]) -> list[str]:
    lines = [
        f"### {name}",
        "| arm | cases | pools p50 | pools p95 | rerank p50 | rerank p95 | total p50 | total p95 | p95 total delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    deltas = block.get("p95_total_delta_ms") or {}
    for arm in ("hybrid", "G1", "G2"):
        row = block[arm]
        delta = deltas.get(arm, _EMPTY_CELL)
        lines.append(
            f"| {arm} | {row['cases']} | "
            f"{_metric_cell(row['pools_ms']['p50'])} | {_metric_cell(row['pools_ms']['p95'])} | "
            f"{_metric_cell(row['rerank_ms']['p50'])} | {_metric_cell(row['rerank_ms']['p95'])} | "
            f"{_metric_cell(row['total_ms']['p50'])} | {_metric_cell(row['total_ms']['p95'])} | "
            f"{_metric_cell(delta)} |"
        )
    return lines


def render_gr3_table(report: Mapping[str, Any]) -> str:
    """Markdown tables for retrieval, parity, latency, generation and the decision."""
    lines = [
        "# GR-3 graph-lane A/B",
        "",
        f"schema {report.get('schema_version', SCHEMA_VERSION)}",
        "",
    ]
    lines.extend(_render_dataset("phase_c", report["phase_c"], PHASE_C_QUALITY_ARMS))
    lines.append("")
    lines.extend(
        _render_dataset("multi_doc_bucket", report["multi_doc_bucket"], BUCKET_QUALITY_ARMS)
    )
    lines.extend(["", "## parity", ""])
    lines.extend(_render_parity_block("phase_c", report["parity"]["phase_c"]))
    lines.append("")
    lines.extend(_render_parity_block("multi_doc_bucket", report["parity"]["multi_doc_bucket"]))
    latency_block = report["latency"]
    lines.extend(["", "## latency", "", f"host: {latency_block.get('host', '')}", ""])
    lines.extend(_render_latency_dataset("phase_c", latency_block["phase_c"]))
    lines.append("")
    lines.extend(_render_latency_dataset("multi_doc_bucket", latency_block["multi_doc_bucket"]))
    generation = report.get("generation")
    lines.extend(["", "## generation", ""])
    if generation is None:
        lines.append("generation reports were not supplied")
    else:
        lines.append(
            f"{generation['method']}; resamples={generation['resamples']}; "
            f"seed={generation['seed']}; cases={generation['cases']}"
        )
        lines.append(_evidence_line("hybrid", generation))
        lines.append(_evidence_line("graph", generation))
        if generation.get("excluded_case_ids"):
            lines.append("excluded: " + ", ".join(generation["excluded_case_ids"]))
        if generation.get("graph_mean_context_count") is not None:
            lines.append(f"graph mean context_count: {generation['graph_mean_context_count']}")
        lines.extend(
            [
                "",
                "| metric | hybrid | graph | difference | 95% CI | better | worse | equal |",
                "|---|---:|---:|---:|---|---:|---:|---:|",
            ]
        )
        for metric, row in generation["metrics"].items():
            interval = f"[{_metric_cell(row['ci_low'])}, {_metric_cell(row['ci_high'])}]"
            lines.append(
                f"| {metric} | {_metric_cell(row['hybrid_mean'])} | "
                f"{_metric_cell(row['graph_mean'])} | {_metric_cell(row['mean_difference'])} | "
                f"{interval} | {row['better']} | {row['worse']} | {row['equal']} |"
            )
        lines.extend(["", "### run-level aggregates", ""])
        for side in ("hybrid_aggregate", "graph_aggregate"):
            aggregate = generation.get(side) or {}
            lines.append(f"{side}:")
            for metric, payload in aggregate.items():
                if not isinstance(payload, Mapping):
                    continue
                lines.append(
                    f"- {metric}: mean={_metric_cell(payload.get('mean'))} "
                    f"[{_metric_cell(payload.get('ci_low'))}, {_metric_cell(payload.get('ci_high'))}]"
                )
    decision = report["decision"]
    lines.extend(["", "## decision", "", f"verdict: {decision['verdict']}", ""])
    lines.append("| criterion | status |")
    lines.append("|---|---|")
    for name, payload in decision["criteria"].items():
        extra = []
        if name == "retrieve_p95_within_200ms" and payload.get("host"):
            extra.append(f"host={payload['host']}")
        if payload.get("delta_ms") is not None:
            extra.append(f"delta_ms={payload['delta_ms']}")
        if payload["status"] == "not_evidence":
            extra.append(f"hybrid={_evidence_cell(payload.get('hybrid_evidence_class'))}")
            extra.append(f"graph={_evidence_cell(payload.get('graph_evidence_class'))}")
        suffix = f" ({'; '.join(extra)})" if extra else ""
        lines.append(f"| {name} | {payload['status']}{suffix} |")
    if decision.get("failed_criteria"):
        lines.append("failed: " + ", ".join(decision["failed_criteria"]))
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-c-h", type=Path, required=True)
    parser.add_argument("--phase-c-hm", type=Path, required=True)
    parser.add_argument("--phase-c-g1", type=Path, required=True)
    parser.add_argument("--phase-c-g2", type=Path, required=True)
    parser.add_argument("--phase-c-g1m", type=Path, required=True)
    parser.add_argument("--phase-c-g2m", type=Path, required=True)
    parser.add_argument("--bucket-hm", type=Path, required=True)
    parser.add_argument("--bucket-g1", type=Path, required=True)
    parser.add_argument("--bucket-g2", type=Path, required=True)
    parser.add_argument("--bucket-g1m", type=Path, required=True)
    parser.add_argument("--bucket-g2m", type=Path, required=True)
    parser.add_argument("--hybrid-generation", type=Path)
    parser.add_argument("--graph-generation", type=Path)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--evidence-class", required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--phase-c-dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--phase-c-sidecar", type=Path, default=DEFAULT_SIDECAR_PATH)
    parser.add_argument("--phase-c-label-manifest", type=Path, default=DEFAULT_LABEL_MANIFEST_PATH)
    parser.add_argument(
        "--phase-c-corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST_PATH
    )
    parser.add_argument("--bucket-dataset", type=Path, default=DEFAULT_MULTI_DOC_DATASET_PATH)
    parser.add_argument("--bucket-sidecar", type=Path, default=DEFAULT_MULTI_DOC_SIDECAR_PATH)
    parser.add_argument(
        "--bucket-label-manifest",
        type=Path,
        default=DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    )
    parser.add_argument("--bucket-corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST_PATH)
    parser.add_argument("--expected-cases", type=int, default=100)
    parser.add_argument("--bucket-expected-cases", type=int, default=15)
    args = parser.parse_args(argv)
    if (args.hybrid_generation is None) ^ (args.graph_generation is None):
        parser.error("pass both --hybrid-generation and --graph-generation, or neither")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_gr3_report(
        phase_c_h=args.phase_c_h,
        phase_c_hm=args.phase_c_hm,
        phase_c_g1=args.phase_c_g1,
        phase_c_g2=args.phase_c_g2,
        phase_c_g1m=args.phase_c_g1m,
        phase_c_g2m=args.phase_c_g2m,
        bucket_hm=args.bucket_hm,
        bucket_g1=args.bucket_g1,
        bucket_g2=args.bucket_g2,
        bucket_g1m=args.bucket_g1m,
        bucket_g2m=args.bucket_g2m,
        hybrid_generation=args.hybrid_generation,
        graph_generation=args.graph_generation,
        phase_c_dataset=args.phase_c_dataset,
        phase_c_sidecar=args.phase_c_sidecar,
        phase_c_label_manifest=args.phase_c_label_manifest,
        phase_c_corpus_manifest=args.phase_c_corpus_manifest,
        bucket_dataset=args.bucket_dataset,
        bucket_sidecar=args.bucket_sidecar,
        bucket_label_manifest=args.bucket_label_manifest,
        bucket_corpus_manifest=args.bucket_corpus_manifest,
        expected_cases=args.expected_cases,
        bucket_expected_cases=args.bucket_expected_cases,
        code_commit=args.code_commit,
        host=args.host,
        evidence_class=args.evidence_class,
    )
    write_gr3_report(report, args.out)
    table = render_gr3_table(report)
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(table, encoding="utf-8", newline="\n")
    print(table, end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
