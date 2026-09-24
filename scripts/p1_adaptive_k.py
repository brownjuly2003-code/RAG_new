"""P1: label-free adaptive-k cut rules on fresh reranker scores of an archived
candidate pool (rank 1 is always kept)."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Collection, Sequence
from math import isfinite
from pathlib import Path
from typing import Any

from evaluation.ragas_eval import _normalise
from scripts import rerank_score_capture
from scripts.ab_context_precision import (
    _KW_STATUS_ORDER,
    DEFAULT_CORPUS_MANIFEST_PATH,
    DEFAULT_DATASET_PATH,
    DEFAULT_LABEL_MANIFEST_PATH,
    DEFAULT_MULTI_DOC_DATASET_PATH,
    DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    DEFAULT_MULTI_DOC_SIDECAR_PATH,
    DEFAULT_SIDECAR_PATH,
    PROJECT_ROOT,
    _code_digests,
    _git_commit,
    _label_block,
    _stored_path,
    score_cases_by_class,
    sha256_file,
)
from scripts.generator_benchmark import load_benchmark_cases
from scripts.gr1b_controls import paired_comparison

SCHEMA_VERSION = "p1-adaptive-k/v1.0"
TOP_N = 5
INF = float("inf")
FIXED_K = (1, 2, 3, 4, 5)
CONTROL_CELL = "top_k_5"

PRIMARY_GRID: tuple[tuple[str, float], ...] = (
    tuple(("abs", t) for t in (0.0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9))
    + tuple(("rel", r) for r in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9))
    + tuple(("gap_prob", g) for g in (INF, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0))
)

SECONDARY_GRID: tuple[tuple[str, float], ...] = tuple(
    ("gap_logit", g) for g in (INF, 6.0, 4.0, 3.0, 2.0, 1.0, 0.5, 0.0)
)


def cell_name(family: str, param: float) -> str:
    """Return the report cell name for one rule family and parameter."""
    if family == "top_k":
        return f"top_k_{int(param)}"
    if param == INF:
        return f"{family}_inf"
    return f"{family}_{param:g}"


def grid_cells() -> list[tuple[str, str, float, str]]:
    """Return (name, family, param, role) for every report cell, in order."""
    cells: list[tuple[str, str, float, str]] = []
    for k in FIXED_K:
        role = "control" if k == TOP_N else "fixed_k"
        cells.append((cell_name("top_k", k), "top_k", k, role))
    cells.extend(
        (cell_name(family, param), family, param, "primary") for family, param in PRIMARY_GRID
    )
    cells.extend(
        (cell_name(family, param), family, param, "secondary") for family, param in SECONDARY_GRID
    )
    seen: set[str] = set()
    for name, _, _, _ in cells:
        if name in seen:
            raise ValueError(f"duplicate cell name: {name}")
        seen.add(name)
    return cells


def kept_count(
    family: str,
    param: float,
    probabilities: Sequence[float],
    logits: Sequence[float],
) -> int:
    """Return how many of the fresh top-5 candidates one cut rule keeps."""
    if len(probabilities) != TOP_N or len(logits) != TOP_N:
        raise ValueError(f"sequences must each hold exactly {TOP_N} values")
    for label, seq in (("probabilities", probabilities), ("logits", logits)):
        for value in seq:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{label} values must be int or float, not bool")
            if not isfinite(value):
                raise ValueError(f"{label} values must be finite")
    p = list(probabilities)
    for value in p:
        if not 0.0 <= value <= 1.0:
            raise ValueError("probabilities must lie within [0, 1]")
    for i in range(TOP_N - 1):
        if p[i] < p[i + 1]:
            raise ValueError("probabilities must be non-increasing")
    x = list(logits)
    if family == "top_k":
        k = int(param)
        if not 1 <= k <= TOP_N:
            raise ValueError(f"top_k param must satisfy 1 <= k <= {TOP_N}")
        return k
    if family == "abs":
        return max(1, sum(1 for v in p if v >= param))
    if family == "rel":
        return max(1, sum(1 for v in p if v >= param * p[0]))
    if family in ("gap_prob", "gap_logit"):
        s = p if family == "gap_prob" else x
        gaps = [s[i] - s[i + 1] for i in range(TOP_N - 1)]
        best = max(gaps)
        i = gaps.index(best)
        return i + 1 if best > 0 and best >= param else TOP_N
    raise ValueError(f"unknown family: {family}")


def load_scores(
    report: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    pool_sha256: str,
) -> list[dict[str, Any]]:
    """Validate a rerank score artifact against archive rows; return per_case."""
    if report["schema_version"] != rerank_score_capture.SCHEMA_VERSION:
        raise ValueError(
            f"schema_version {report['schema_version']!r} does not match "
            f"{rerank_score_capture.SCHEMA_VERSION!r}"
        )
    if report["complete"] is not True:
        raise ValueError("score capture artifact is not complete")
    if report["provenance"]["pool_sha256"] != pool_sha256:
        raise ValueError("pool_sha256 does not match the archive rows")
    per_case = report["per_case"]
    if [c["case_id"] for c in per_case] != [r["case_id"] for r in rows]:
        raise ValueError("per_case case_id sequence does not match archive rows")
    for case, row in zip(per_case, rows, strict=True):
        case_id = case["case_id"]
        n = len(row["prerank_cands"])
        n_candidates = case["n_candidates"]
        if isinstance(n_candidates, bool) or not isinstance(n_candidates, int):
            raise ValueError(f"case {case_id!r}: n_candidates must be int")
        if n_candidates != n:
            raise ValueError(f"case {case_id!r}: n_candidates != {n}")
        if n < TOP_N:
            raise ValueError(f"case {case_id!r}: needs at least {TOP_N} candidates")
        for key in ("logits", "probabilities"):
            values = case[key]
            if not isinstance(values, list) or len(values) != n:
                raise ValueError(f"case {case_id!r}: {key} must be a list of length {n}")
            for value in values:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"case {case_id!r}: {key} values must be int or float")
                if not isfinite(value):
                    raise ValueError(f"case {case_id!r}: {key} values must be finite")
        for value in case["probabilities"]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"case {case_id!r}: probabilities must lie within [0, 1]")
        order = case["fresh_order"]
        for j in order:
            if isinstance(j, bool) or not isinstance(j, int):
                raise ValueError(f"case {case_id!r}: fresh_order items must be int")
        if sorted(order) != list(range(n)):
            raise ValueError(f"case {case_id!r}: fresh_order must permute range({n})")
        probabilities = case["probabilities"]
        for i in range(n - 1):
            if probabilities[order[i]] < probabilities[order[i + 1]]:
                raise ValueError(f"case {case_id!r}: fresh_order not descending in probability")
        if order != rerank_score_capture.probability_order(probabilities):
            raise ValueError(f"case {case_id!r}: fresh_order is not the stable probability order")
    return per_case


def check_parity(rows: Sequence[dict[str, Any]], scores_report: dict[str, Any]) -> None:
    """Fail closed unless the capture used the pre-registered model and
    reproduces the archived order."""
    reranker = scores_report["provenance"].get("reranker")
    model = reranker.get("model") if isinstance(reranker, dict) else None
    if model != RERANKER_MODEL:
        raise ValueError(f"reranker model {model!r} differs from {RERANKER_MODEL!r}")
    mismatched = [
        row["case_id"]
        for row, case in zip(rows, scores_report["per_case"], strict=True)
        if [row["prerank_cands"][j] for j in case["fresh_order"]] != list(row["cands"])
    ]
    if mismatched:
        raise ValueError(f"fresh_order differs from archived cands for case_ids {mismatched!r}")
    parity = scores_report.get("parity")
    if (
        not isinstance(parity, dict)
        or parity.get("order_matches") != len(rows)
        or parity.get("top_k_matches") != len(rows)
        or parity.get("mismatched_case_ids") != []
    ):
        case_ids = [row["case_id"] for row in rows]
        raise ValueError(f"parity is not full for case_ids {case_ids!r}: {parity!r}")


def fresh_rankings(
    rows: Sequence[dict[str, Any]],
    scores: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Re-order each case's texts, probabilities and logits by fresh_order."""
    rankings: list[dict[str, Any]] = []
    for row, case in zip(rows, scores, strict=True):
        order = case["fresh_order"]
        cands = row["prerank_cands"]
        rankings.append(
            {
                "case_id": row["case_id"],
                "texts": [cands[j] for j in order],
                "probabilities": [case["probabilities"][j] for j in order],
                "logits": [case["logits"][j] for j in order],
            }
        )
    return rankings


def rule_counts(
    rankings: Sequence[dict[str, Any]],
    family: str,
    param: float,
) -> list[int]:
    """Return kept counts for one cut rule across all rankings, in order."""
    return [
        kept_count(family, param, r["probabilities"][:TOP_N], r["logits"][:TOP_N]) for r in rankings
    ]


def case_groups(dataset_rows: Sequence[dict[str, Any]]) -> dict[str, str]:
    """Map each case_id to its tag path, or a per-case fallback label."""
    groups: dict[str, str] = {}
    for row in dataset_rows:
        case_id = row["case_id"]
        tags = row.get("tags")
        if isinstance(tags, (list, tuple)) and tags and all(isinstance(tag, str) for tag in tags):
            groups[case_id] = "/".join(tags)
        else:
            groups[case_id] = f"case:{case_id}"
    return groups


def assign_folds(groups: dict[str, str], folds: int) -> dict[str, int]:
    """Assign whole case groups to folds, greedily balancing case counts."""
    if isinstance(folds, bool) or not isinstance(folds, int):
        raise ValueError("folds must be an int, not a bool")
    members: dict[str, list[str]] = {}
    for case_id, group in groups.items():
        members.setdefault(group, []).append(case_id)
    if folds < 2 or folds > len(members):
        raise ValueError(f"folds must be between 2 and {len(members)} (the group count)")
    loads = [0] * folds
    assignment: dict[str, int] = {}
    ordered = sorted(members.items(), key=lambda item: (-len(item[1]), item[0]))
    for group, case_ids in ordered:
        fold = min(range(folds), key=lambda i: loads[i])
        loads[fold] += len(case_ids)
        for case_id in case_ids:
            assignment[case_id] = fold
    return assignment


def aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Summarize one cell's per-case rows: means and keyword-status counts."""

    def mean(key: str) -> float | None:
        if not rows:
            return None
        return round(sum(row[key] for row in rows) / len(rows), 4)

    return {
        "num_cases": len(rows),
        "context_precision": mean("context_precision"),
        "context_recall": mean("context_recall"),
        "FULL": sum(1 for row in rows if row["kw_status"] == "FULL"),
        "PART": sum(1 for row in rows if row["kw_status"] == "PART"),
        "MISS": sum(1 for row in rows if row["kw_status"] == "MISS"),
        "mean_kept": mean("kept"),
        "mean_n_docs": mean("n_docs"),
    }


def _units(rows: Sequence[dict[str, Any]], key: str) -> int:
    """Exact sum of a four-decimal per-case metric, in units of 0.0001."""
    return sum(round(row[key] * 10_000) for row in rows)


def select_cell(
    per_cell: dict[str, list[dict[str, Any]]],
    candidates: Sequence[str],
    control: str,
    case_ids: Collection[str],
) -> str:
    """Pick the feasible candidate with the best precision on the given cases."""
    wanted = set(case_ids)
    control_rows = [row for row in per_cell[control] if row["case_id"] in wanted]
    if not control_rows:
        raise ValueError(f"case_ids select no rows of the control cell {control!r}")
    control_stats = aggregate(control_rows)
    best_key: tuple[int, int, int] | None = None
    best_cell = control
    for position, cell in enumerate(candidates):
        rows = [row for row in per_cell[cell] if row["case_id"] in wanted]
        stats = aggregate(rows)
        if stats["num_cases"] == 0:
            continue
        if (
            _units(rows, "context_recall") < _units(control_rows, "context_recall")
            or stats["FULL"] < control_stats["FULL"]
            or stats["MISS"] > control_stats["MISS"]
        ):
            continue
        key = (_units(rows, "context_precision"), sum(row["kept"] for row in rows), -position)
        if best_key is None or key > best_key:
            best_key = key
            best_cell = cell
    return best_cell


def verdict_flags(
    held_out: Sequence[dict[str, Any]],
    control: Sequence[dict[str, Any]],
) -> dict[str, bool]:
    """Gate, H-relative and review-floor flags from exact sums over the held-out rows."""
    if not held_out:
        raise ValueError("held_out must not be empty")
    if {row["case_id"] for row in held_out} != {row["case_id"] for row in control}:
        raise ValueError("held_out and control must cover the same case_ids")
    n = len(held_out)
    cv = aggregate(held_out)
    ctrl = aggregate(control)
    return {
        "precision_gate_met": _units(held_out, "context_precision")
        >= round(PRECISION_GATE * 10_000) * n,
        "h_relative_constraints_met": _units(held_out, "context_recall")
        >= _units(control, "context_recall")
        and cv["FULL"] >= ctrl["FULL"]
        and cv["MISS"] <= ctrl["MISS"],
        "review_floor_met": _units(held_out, "context_recall")
        >= round(REVIEW_FLOOR["context_recall"] * 10_000) * n
        and cv["FULL"] >= REVIEW_FLOOR["FULL"]
        and cv["MISS"] <= REVIEW_FLOOR["MISS"],
    }


def fact_losses(
    rows: Sequence[dict[str, Any]], control_rows: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Control keywords each case lost, and keyword-status regressions, case by case."""
    control_by_case = {row["case_id"]: row for row in control_rows}
    losses: list[dict[str, Any]] = []
    for row in rows:
        case_id = row["case_id"]
        if case_id not in control_by_case:
            raise ValueError(f"case {case_id!r}: missing from control rows")
        control = control_by_case[case_id]
        matched = set(row["matched_keywords"])
        lost = [kw for kw in control["matched_keywords"] if kw not in matched]
        worse = _KW_STATUS_ORDER[row["kw_status"]] < _KW_STATUS_ORDER[control["kw_status"]]
        if lost or worse:
            loss = {"case_id": case_id}
            if "fold" in row:
                loss["fold"] = row["fold"]
            if "cell" in row:
                loss["cell"] = row["cell"]
            loss["kept"] = row["kept"]
            loss["lost_keywords"] = lost
            loss["control_status"] = control["kw_status"]
            loss["status"] = row["kw_status"]
            losses.append(loss)
    return losses


def cross_validate(
    per_cell: dict[str, list[dict[str, Any]]],
    candidates: Sequence[str],
    control: str,
    folds_by_case: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Leave-one-fold-out validation of the label-free cell choice."""
    control_rows = per_cell[control]
    if {row["case_id"] for row in control_rows} != set(folds_by_case):
        raise ValueError("folds_by_case keys must equal the control cell's case_ids")
    rows_by_case = {name: {row["case_id"]: row for row in rows} for name, rows in per_cell.items()}
    choices: list[dict[str, Any]] = []
    cell_by_fold: dict[int, str] = {}
    for fold in sorted(set(folds_by_case.values())):
        train = {c for c, f in folds_by_case.items() if f != fold}
        test_count = sum(1 for f in folds_by_case.values() if f == fold)
        cell = select_cell(per_cell, candidates, control, train)
        cell_by_fold[fold] = cell
        cell_train = [row for row in per_cell[cell] if row["case_id"] in train]
        control_train = [row for row in control_rows if row["case_id"] in train]
        choices.append(
            {
                "fold": fold,
                "cell": cell,
                "train_cases": len(train),
                "test_cases": test_count,
                "train": aggregate(cell_train),
                "train_control": aggregate(control_train),
            }
        )
    held_out: list[dict[str, Any]] = []
    for row in control_rows:
        case_id = row["case_id"]
        fold = folds_by_case[case_id]
        cell = cell_by_fold[fold]
        picked = dict(rows_by_case[cell][case_id])
        picked["fold"] = fold
        picked["cell"] = cell
        held_out.append(picked)
    return held_out, choices


def oracle_best_prefix(per_cell: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Label-using diagnostic (never a selector): best covered prefix per case."""
    rows_by_case = {name: {row["case_id"]: row for row in rows} for name, rows in per_cell.items()}
    picked_rows: list[dict[str, Any]] = []
    for control_row in per_cell[CONTROL_CELL]:
        case_id = control_row["case_id"]
        target = set(control_row["matched_keywords"])
        best_row = control_row
        best_key = (control_row["context_precision"], -TOP_N)
        best_k = TOP_N
        for k in FIXED_K:
            row = rows_by_case[cell_name("top_k", k)][case_id]
            if not target <= set(row["matched_keywords"]):
                continue
            if _KW_STATUS_ORDER[row["kw_status"]] < _KW_STATUS_ORDER[control_row["kw_status"]]:
                continue
            key = (row["context_precision"], -k)
            if key > best_key:
                best_key = key
                best_row = row
                best_k = k
        picked = dict(best_row)
        picked["oracle_k"] = best_k
        picked_rows.append(picked)
    return picked_rows


CONTEXT_CHARS = 6000
FOLDS = 5
GRID_BOOTSTRAP_SAMPLES = 2000
HEADLINE_BOOTSTRAP_SAMPLES = 10000
BOOTSTRAP_SEED = 20260923
PRECISION_GATE = 0.63
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

PUBLISHED_H = {
    "context_precision": 0.5067,
    "context_recall": 0.905,
    "FULL": 87,
    "PART": 7,
    "MISS": 6,
}
REVIEW_FLOOR = {"context_recall": 0.92, "FULL": 88, "MISS": 4}

H_ARCHIVE = PROJECT_ROOT / "evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz"
H_POOL_SHA256 = "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10"
HM_ARCHIVE = PROJECT_ROOT / "evaluation/gr3-32de532-bucket-Hm-candidates.json.gz"
HM_POOL_SHA256 = "3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee"

CODE_PATHS = (
    "scripts/p1_adaptive_k.py",
    "scripts/rerank_score_capture.py",
    "scripts/gr1b_controls.py",
    "scripts/ab_context_precision.py",
    "scripts/generator_benchmark.py",
    "scripts/ab_remote_contextual.py",
    "evaluation/ragas_eval.py",
    "evaluation/question_class_labels.py",
)


def score_selection(
    rows: Sequence[dict[str, Any]],
    rankings: Sequence[dict[str, Any]],
    kept: Sequence[int],
    *,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    context_chars: int = CONTEXT_CHARS,
) -> tuple[list[dict[str, Any]], int]:
    """Score one kept-count selection as a pool; extend rows with keyword evidence."""
    pool_rows = [
        dict(row, cands=ranking["texts"][:k])
        for row, ranking, k in zip(rows, rankings, kept, strict=True)
    ]
    with tempfile.TemporaryDirectory(prefix="p1-adaptive-k-") as tmp_dir:
        pool_path = Path(tmp_dir) / "pool.json"
        pool_path.write_text(json.dumps(pool_rows, ensure_ascii=False) + "\n", encoding="utf-8")
        scored, approved = score_cases_by_class(
            pool_path=pool_path,
            dataset_path=dataset_path,
            sidecar_path=sidecar_path,
            label_manifest_path=label_manifest_path,
            expected_cases=len(rows),
            top_k=TOP_N,
            context_chars=context_chars,
            allow_short_contexts=True,
        )
        benchmark = load_benchmark_cases(
            dataset_path=dataset_path,
            contexts_path=pool_path,
            expected_cases=len(rows),
            top_k=TOP_N,
            context_chars=context_chars,
            allow_short_contexts=True,
        )
    kept_by_case = {row["case_id"]: k for row, k in zip(rows, kept, strict=True)}
    contexts_by_case = {case["case_id"]: case for case in benchmark}
    scored_rows: list[dict[str, Any]] = []
    for scored_row in scored:
        case_id = scored_row["case_id"]
        case = contexts_by_case[case_id]
        haystack = _normalise("\n".join(case["contexts"]))
        row = dict(scored_row)
        row["matched_keywords"] = [
            w for w in case["expected_keywords"] if _normalise(w) in haystack
        ]
        row["context_chars"] = sum(len(context) for context in case["contexts"])
        row["kept"] = kept_by_case[case_id]
        scored_rows.append(row)
    return scored_rows, approved


def evaluate_pool(
    *,
    archive: Path,
    pool_sha256: str,
    scores_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    """Score every grid cell over one archived pool of fresh reranker scores."""
    rows, digest = rerank_score_capture.load_pool_archive(archive, pool_sha256)
    scores_report = json.loads(scores_path.read_text(encoding="utf-8"))
    scores = load_scores(scores_report, rows, digest)
    check_parity(rows, scores_report)
    rankings = fresh_rankings(rows, scores)
    per_cell: dict[str, list[dict[str, Any]]] = {}
    approved = 0
    for name, family, param, _role in grid_cells():
        per_cell[name], cell_approved = score_selection(
            rows,
            rankings,
            rule_counts(rankings, family, param),
            dataset_path=dataset_path,
            sidecar_path=sidecar_path,
            label_manifest_path=label_manifest_path,
        )
        if name == CONTROL_CELL:
            approved = cell_approved
    cells: list[dict[str, Any]] = []
    for name, family, param, role in grid_cells():
        cells.append(
            {
                "name": name,
                "family": family,
                "param": "inf" if param == INF else param,
                "role": role,
                "aggregate": aggregate(per_cell[name]),
                "kept": [row["kept"] for row in per_cell[name]],
                "comparison": paired_comparison(
                    per_cell[name],
                    per_cell[CONTROL_CELL],
                    samples=bootstrap_samples,
                    seed=seed,
                ),
            }
        )
    return {
        "rows": rows,
        "per_cell": per_cell,
        "cells": cells,
        "approved": approved,
        "scores_report": scores_report,
        "digest": digest,
    }


def build_report(
    *,
    h_scores: Path,
    hm_scores: Path,
    h_archive: Path = H_ARCHIVE,
    hm_archive: Path = HM_ARCHIVE,
    h_pool_sha256: str = H_POOL_SHA256,
    hm_pool_sha256: str = HM_POOL_SHA256,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    sidecar_path: Path = DEFAULT_SIDECAR_PATH,
    label_manifest_path: Path = DEFAULT_LABEL_MANIFEST_PATH,
    hm_dataset_path: Path = DEFAULT_MULTI_DOC_DATASET_PATH,
    hm_sidecar_path: Path = DEFAULT_MULTI_DOC_SIDECAR_PATH,
    hm_label_manifest_path: Path = DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    folds: int = FOLDS,
    grid_bootstrap_samples: int = GRID_BOOTSTRAP_SAMPLES,
    headline_bootstrap_samples: int = HEADLINE_BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
    code_commit: str | None = None,
) -> dict[str, Any]:
    """Assemble the deterministic P1 report over the H and Hm pools."""
    h = evaluate_pool(
        archive=h_archive,
        pool_sha256=h_pool_sha256,
        scores_path=h_scores,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path,
        bootstrap_samples=grid_bootstrap_samples,
        seed=seed,
    )
    hm = evaluate_pool(
        archive=hm_archive,
        pool_sha256=hm_pool_sha256,
        scores_path=hm_scores,
        dataset_path=hm_dataset_path,
        sidecar_path=hm_sidecar_path,
        label_manifest_path=hm_label_manifest_path,
        bootstrap_samples=grid_bootstrap_samples,
        seed=seed,
    )
    primary = [name for name, _, _, role in grid_cells() if role == "primary"]
    control = h["per_cell"][CONTROL_CELL]
    ctrl = aggregate(control)
    control_ok = all(ctrl[key] == value for key, value in PUBLISHED_H.items())
    dataset_rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    folds_by_case = assign_folds(case_groups(dataset_rows), folds)
    held_out, choices = cross_validate(h["per_cell"], primary, CONTROL_CELL, folds_by_case)
    cv = aggregate(held_out)
    best = select_cell(h["per_cell"], primary, CONTROL_CELL, {row["case_id"] for row in control})
    oracle = oracle_best_prefix(h["per_cell"])
    flags = verdict_flags(held_out, control)
    if not control_ok:
        decision = "INVALID_CONTROL"
    elif flags["precision_gate_met"] and flags["h_relative_constraints_met"]:
        decision = "SHIP_CANDIDATE"
    else:
        decision = "NO_SHIP"
    corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))

    def pool_info(
        archive: Path,
        scores_path: Path,
        digest: str,
        scores_report: dict[str, Any],
        data_path: Path,
        sidecar: Path,
        label_manifest: Path,
    ) -> dict[str, Any]:
        provenance = scores_report["provenance"]
        return {
            "archive_path": _stored_path(archive),
            "archive_sha256": sha256_file(archive),
            "pool_sha256": digest,
            "scores_path": _stored_path(scores_path),
            "scores_sha256": sha256_file(scores_path),
            "scores_code_commit": provenance["code"].get("commit"),
            "reranker": provenance["reranker"],
            "batch_size": provenance["config"].get("batch_size"),
            "parity": scores_report["parity"],
            "dataset": _stored_path(data_path),
            "dataset_sha256": sha256_file(data_path),
            "label_sidecar": _stored_path(sidecar),
            "label_sidecar_sha256": sha256_file(sidecar),
            "label_manifest": _stored_path(label_manifest),
            "label_manifest_sha256": sha256_file(label_manifest),
        }

    hm_control = hm["per_cell"][CONTROL_CELL]
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "measured",
        "labels": {
            "H": _label_block(h["approved"]),
            "Hm": _label_block(hm["approved"]),
        },
        "provenance": {
            "code": dict(
                _git_commit()
                if code_commit is None
                else {"commit": code_commit, "tree_clean": None},
                files=_code_digests(CODE_PATHS),
            ),
            "corpus": {
                "manifest": _stored_path(corpus_manifest_path),
                "manifest_sha256": sha256_file(corpus_manifest_path),
                "name": corpus_manifest.get("name"),
                "corpus_sha256": corpus_manifest.get("corpus_sha256"),
                "file_count": corpus_manifest.get("file_count"),
            },
            "pools": {
                "H": pool_info(
                    h_archive,
                    h_scores,
                    h["digest"],
                    h["scores_report"],
                    dataset_path,
                    sidecar_path,
                    label_manifest_path,
                ),
                "Hm": pool_info(
                    hm_archive,
                    hm_scores,
                    hm["digest"],
                    hm["scores_report"],
                    hm_dataset_path,
                    hm_sidecar_path,
                    hm_label_manifest_path,
                ),
            },
        },
        "config": {
            "top_n": TOP_N,
            "context_chars": CONTEXT_CHARS,
            "rank_one_always_kept": True,
            "score_scale": (
                "abs, rel and gap_prob use CrossEncoder sigmoid probabilities; "
                "gap_logit uses raw logits"
            ),
            "rules": {
                "top_k": "keep exactly k",
                "abs": "keep ranks with probability >= tau; rank 1 always",
                "rel": "keep ranks with probability >= rho * p1; rank 1 always",
                "gap_prob": (
                    "cut after the first largest gap between adjacent top-five probabilities "
                    "when that gap is > 0 and >= g; g = inf never cuts; a zero gap never cuts"
                ),
                "gap_logit": "the gap_prob rule on raw logits",
            },
            "cells": [name for name, _, _, _ in grid_cells()],
            "primary": primary,
            "folds": folds,
            "grouping": "dataset tags joined by '/', else case:<id>",
            "fold_rule": (
                "groups by descending size then name, each to the fold with the fewest cases"
            ),
            "selection": (
                "max exact train precision (sum of per-case four-decimal values) s.t. train "
                "recall, FULL, MISS no worse than top_k_5; ties: more kept documents, then "
                "grid order"
            ),
            "bootstrap": {
                "grid_samples": grid_bootstrap_samples,
                "headline_samples": headline_bootstrap_samples,
                "seed": seed,
                "method": "paired case bootstrap percentile 95%, linear quantiles",
            },
            "precision_gate": PRECISION_GATE,
            "published_h": PUBLISHED_H,
            "review_floor": REVIEW_FLOOR,
            "preregistered": (
                "grid, CV rule and verdict fixed on 2026-09-23 before any score was seen"
            ),
        },
        "h": {
            "control_reproduces_published": control_ok,
            "cells": h["cells"],
            "cross_validation": {
                "choices": choices,
                "aggregate": cv,
                "comparison": paired_comparison(
                    held_out,
                    control,
                    samples=headline_bootstrap_samples,
                    seed=seed,
                ),
                "fact_losses": fact_losses(held_out, control),
                "per_case": [
                    {
                        "case_id": row["case_id"],
                        "fold": row["fold"],
                        "cell": row["cell"],
                        "kept": row["kept"],
                    }
                    for row in held_out
                ],
            },
            "in_sample_best": {
                "cell": best,
                "aggregate": aggregate(h["per_cell"][best]),
                "note": "selected on all 100 cases; optimistic, not the headline",
            },
            "oracle_best_prefix": {
                "kind": "oracle_diagnostic_not_deployable",
                "aggregate": aggregate(oracle),
                "comparison": paired_comparison(
                    oracle,
                    control,
                    samples=grid_bootstrap_samples,
                    seed=seed,
                ),
                "oracle_k": [row["oracle_k"] for row in oracle],
            },
        },
        "hm": {
            "cells": hm["cells"],
            "transfer": {
                "cell": best,
                "aggregate": aggregate(hm["per_cell"][best]),
                "control": aggregate(hm_control),
                "comparison": paired_comparison(
                    hm["per_cell"][best],
                    hm_control,
                    samples=grid_bootstrap_samples,
                    seed=seed,
                ),
                "fact_losses": fact_losses(hm["per_cell"][best], hm_control),
            },
        },
        "verdict": {
            "headline": f"{folds}-fold grouped cross-validation, held-out cases",
            "precision_gate_met": flags["precision_gate_met"],
            "h_relative_constraints_met": flags["h_relative_constraints_met"],
            "review_floor_met": flags["review_floor_met"],
            "decision": decision,
            "scope": (
                "H-relative exploratory verdict on the phase-C harness, without parent-window "
                "expansion; not shipment approval: no cut of the control's top five can reach "
                "the review floor, and production expansion is not measured"
            ),
            "note": (
                "SHIP_CANDIDATE is not a default change; production adoption is the "
                "owner's decision"
            ),
        },
    }


def render_table(report: dict[str, Any]) -> str:
    """Render the report's headline grid and verdict as Markdown lines."""
    h = report["h"]
    control = next(c for c in h["cells"] if c["name"] == CONTROL_CELL)["aggregate"]

    def stats(agg: dict[str, Any]) -> str:
        return (
            f"precision {agg['context_precision']:.4f}, recall {agg['context_recall']:.4f}, "
            f"{agg['FULL']}/{agg['PART']}/{agg['MISS']}, mean kept {agg['mean_kept']:.2f}"
        )

    lines: list[str] = [
        f"### H grid (fresh top-5, n = {control['num_cases']})\n",
        "\n",
        "| cell | role | precision | recall | FULL/PART/MISS | mean kept | precision delta CI95 "
        "| fact-loss cases | FULL regressions |\n",
        "|---|---|---:|---:|---|---:|---|---:|---:|\n",
    ]
    for cell in h["cells"]:
        agg = cell["aggregate"]
        comparison = cell["comparison"]
        low, high = comparison["precision_delta_ci95"]
        lines.append(
            f"| {cell['name']} | {cell['role']} | {agg['context_precision']:.4f} "
            f"| {agg['context_recall']:.4f} | {agg['FULL']}/{agg['PART']}/{agg['MISS']} "
            f"| {agg['mean_kept']:.2f} | [{low:.4f}, {high:.4f}] "
            f"| {len(comparison['lost_keyword_cases'])} "
            f"| {len(comparison['full_regressions'])} |\n"
        )
    lines.append("\n")
    cv = h["cross_validation"]
    low, high = cv["comparison"]["precision_delta_ci95"]
    fold_cells = ", ".join(choice["cell"] for choice in cv["choices"])
    lines.append(
        f"- CV held-out (cells per fold: {fold_cells}): {stats(cv['aggregate'])}; "
        f"precision delta {cv['comparison']['precision_delta']:+.4f} CI95 "
        f"[{low:.4f}, {high:.4f}]; fact-loss cases "
        f"{len(cv['comparison']['lost_keyword_cases'])}; FULL regressions "
        f"{len(cv['comparison']['full_regressions'])}\n"
    )
    loss_entries = []
    for loss in cv["fact_losses"]:
        kws = ", ".join(f"`{kw}`" for kw in loss["lost_keywords"]) or "status only"
        loss_entries.append(
            f"`{loss['case_id']}` (fold {loss['fold']}, `{loss['cell']}`, "
            f"{loss['control_status']}->{loss['status']}): {kws}"
        )
    lines.append("- Held-out fact losses: " + ("; ".join(loss_entries) or "none") + "\n")
    best = h["in_sample_best"]
    lines.append(f"- In-sample best ({best['cell']}, optimistic): {stats(best['aggregate'])}\n")
    oracle = h["oracle_best_prefix"]
    lines.append(f"- Oracle best prefix (labels; not deployable): {stats(oracle['aggregate'])}\n")
    transfer = report["hm"]["transfer"]
    lines.append(
        f"- Hm transfer ({transfer['cell']}) vs Hm control: {stats(transfer['aggregate'])} "
        f"vs {stats(transfer['control'])}; "
        f"fact-loss cases {len(transfer['comparison']['lost_keyword_cases'])}; "
        f"FULL regressions {len(transfer['comparison']['full_regressions'])}\n"
    )
    loss_entries = []
    for loss in transfer["fact_losses"]:
        kws = ", ".join(f"`{kw}`" for kw in loss["lost_keywords"]) or "status only"
        loss_entries.append(
            f"`{loss['case_id']}` ({loss['control_status']}->{loss['status']}): {kws}"
        )
    lines.append("- Hm transfer fact losses: " + ("; ".join(loss_entries) or "none") + "\n")
    verdict = report["verdict"]
    gate = "met" if verdict["precision_gate_met"] else "not met"
    relative = "met" if verdict["h_relative_constraints_met"] else "not met"
    floor = "met" if verdict["review_floor_met"] else "not met"
    lines.append(
        f"**Decision: {verdict['decision']}** (precision gate {gate}; "
        f"H-relative constraints {relative}; review floor {floor})\n"
    )
    return "".join(lines)


def write_report(path: Path, report: dict[str, Any]) -> Path:
    """Serialize one P1 report to a JSON file, creating parents as needed."""
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Build, persist and print the P1 report from captured reranker scores."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h-scores", type=Path, required=True)
    parser.add_argument("--hm-scores", type=Path, required=True)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports" / "p1" / "p1-adaptive-k.json",
    )
    parser.add_argument("--folds", type=int, default=FOLDS)
    parser.add_argument("--code-commit", default=None)
    args = parser.parse_args(argv)
    report = build_report(
        h_scores=args.h_scores,
        hm_scores=args.hm_scores,
        folds=args.folds,
        code_commit=args.code_commit,
    )
    write_report(args.report, report)
    print(render_table(report), end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
