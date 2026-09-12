"""Offline, same-pool controls for the archived GR-1b retrieval result."""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import tempfile
from pathlib import Path
from typing import Any

from scripts.ab_context_precision import (
    DEFAULT_CORPUS_MANIFEST_PATH,
    DEFAULT_DATASET_PATH,
    DEFAULT_LABEL_MANIFEST_PATH,
    DEFAULT_SIDECAR_PATH,
    PROJECT_ROOT,
    _bucket_row,
    _bucket_rows_by_class,
    _stored_path,
    build_bucket_report,
    score_cases_by_class,
    sha256_file,
    write_bucket_report,
)

DEFAULT_ARCHIVE = PROJECT_ROOT / "evaluation/gr1b-4436d61-candidates.json.gz"
DEFAULT_REPORT = PROJECT_ROOT / "reports/gr/gr1b-controls.json"


def paired_comparison(
    arm: list[dict[str, Any]], baseline: list[dict[str, Any]], *, samples: int, seed: int,
) -> dict[str, Any]:
    """Case-paired bootstrap and losses, including swaps hidden by equal recall."""
    by_id = {row["case_id"]: row for row in arm}
    paired = [(by_id[row["case_id"]], row) for row in baseline]
    deltas = [
        (after["context_precision"] - before["context_precision"],
         after["context_recall"] - before["context_recall"])
        for after, before in paired
    ]
    rng = random.Random(seed)
    draws: list[list[float]] = [[], []]
    for _ in range(samples):
        indices = [rng.randrange(len(paired)) for _ in paired]
        for metric in range(2):
            draws[metric].append(sum(deltas[i][metric] for i in indices) / len(paired))
    result: dict[str, Any] = {}
    for metric, name in enumerate(("precision", "recall")):
        values = sorted(draws[metric])
        bounds = []
        for fraction in (0.025, 0.975):
            position = (len(values) - 1) * fraction
            left = int(position)
            right = min(left + 1, len(values) - 1)
            bounds.append(round(values[left] + (values[right] - values[left]) * (position - left), 6))
        result[f"{name}_delta"] = round(sum(d[metric] for d in deltas) / len(paired), 6)
        result[f"{name}_delta_ci95"] = bounds
    result["full_regressions"] = [
        before["case_id"] for after, before in paired
        if before["kw_status"] == "FULL" and after["kw_status"] != "FULL"
    ]
    result["lost_keyword_cases"] = [
        before["case_id"] for after, before in paired
        if set(before["matched_keywords"]) - set(after["matched_keywords"])
    ]
    result["transitions"] = {
        f"{before_status}->{after_status}": sum(
            before["kw_status"] == before_status and after["kw_status"] == after_status
            for after, before in paired
        )
        for before_status in ("FULL", "PART", "MISS")
        for after_status in ("FULL", "PART", "MISS")
    }
    return result


def build_controls_report(
    *, archive_path: Path = DEFAULT_ARCHIVE,
    dataset_path: Path = DEFAULT_DATASET_PATH, sidecar_path: Path = DEFAULT_SIDECAR_PATH,
    label_manifest_path: Path = DEFAULT_LABEL_MANIFEST_PATH,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    expected_cases: int = 100, context_chars: int = 6000,
    bootstrap_samples: int = 2000, seed: int = 42, code_commit: str | None = None,
) -> dict[str, Any]:
    from evaluation.ragas_eval import _normalise
    from scripts.generator_benchmark import load_benchmark_cases

    if expected_cases < 1 or context_chars < 1 or bootstrap_samples < 1:
        raise ValueError("case count, character cap and bootstrap samples must be positive")
    raw = gzip.decompress(archive_path.read_bytes())
    original = json.loads(raw)
    common = dict(
        dataset_path=dataset_path, sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path, expected_cases=expected_cases,
        context_chars=context_chars,
    )
    with tempfile.TemporaryDirectory(prefix="gr1b-controls-") as directory:
        pool = Path(directory) / "pool.json"
        pool.write_bytes(raw)
        baseline = build_bucket_report(
            pool_path=pool, corpus_manifest_path=corpus_manifest_path,
            top_k=5, pool_arm="G1", code_commit=code_commit, **common,
        )
        for row in original:
            for field in ("reranked_cands", "prerank_cands"):
                candidates = row.get(field)
                if (not isinstance(candidates, list) or len(candidates) < 5
                        or not all(isinstance(text, str) for text in candidates)):
                    raise ValueError(f"{row['case_id']}: {field} requires at least five text candidates")
        arms = []
        variants = [("g1", "cands", 5), *(
            (f"reranked_top_{k}", "reranked_cands", k) for k in range(1, 6)
        ), ("prerank_top_5", "prerank_cands", 5)]
        for name, field, top_k in variants:
            rows = [dict(row, cands=row[field]) for row in original]
            pool.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8", newline="\n")
            scored, _ = score_cases_by_class(
                pool_path=pool, top_k=top_k, allow_short_contexts=name == "g1", **common,
            )
            cases = load_benchmark_cases(
                dataset_path=dataset_path, contexts_path=pool, expected_cases=expected_cases,
                context_chars=context_chars, top_k=top_k, allow_short_contexts=name == "g1",
            )
            for row, case in zip(scored, cases, strict=True):
                blob = _normalise("\n".join(case["contexts"]))
                row["matched_keywords"] = [
                    word for word in case["expected_keywords"] if _normalise(word) in blob
                ]
                row["context_chars"] = sum(map(len, case["contexts"]))
            arms.append(dict(
                name=name, candidate_field=field, top_k=top_k,
                aggregate=_bucket_row("all cases", scored),
                buckets=_bucket_rows_by_class(scored), per_case=scored,
            ))
    for arm in arms:
        arm["comparison"] = paired_comparison(
            arm["per_case"], arms[0]["per_case"], samples=bootstrap_samples, seed=seed,
        )
    provenance = baseline["provenance"]
    provenance["pool_path"] = _stored_path(archive_path) + " (decompressed)"
    provenance["archive_path"] = _stored_path(archive_path)
    provenance["archive_sha256"] = sha256_file(archive_path)
    provenance["pool_sha256"] = hashlib.sha256(raw).hexdigest()
    provenance["code"]["files"]["scripts/gr1b_controls.py"] = sha256_file(Path(__file__))
    provenance["config"]["controls"] = {
        "candidate_fields": ["cands", "reranked_cands", "prerank_cands"],
        "reranked_top_k": [1, 2, 3, 4, 5], "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": seed, "ci": "paired case bootstrap percentile 95%, linear quantiles",
        "scope": "exploratory; cases not held out; shared-source dependence not modelled",
        "keyword_losses": "recall-normalised keyword sets; FULL uses original kw_status",
    }
    return dict(
        schema_version="gr1b-same-pool-controls/v1.0", evidence_class="measured",
        labels=baseline["labels"], provenance=provenance,
        pool_diagnostics=baseline["pool_diagnostics"], reference_arm="g1", arms=arms,
    )


def render_controls_table(report: dict[str, Any]) -> str:
    lines = [
        "| arm | precision | recall | FULL/PART/MISS | precision delta CI95 | FULL losses | fact-loss cases |",
        "|---|---:|---:|---|---|---:|---:|",
    ]
    for arm in report["arms"]:
        row, comparison = arm["aggregate"], arm["comparison"]
        low, high = comparison["precision_delta_ci95"]
        lines.append(
            f"| {arm['name']} | {row['context_precision']:.4f} | {row['context_recall']:.4f} "
            f"| {row['FULL']}/{row['PART']}/{row['MISS']} | [{low:.6f}, {high:.6f}] "
            f"| {len(comparison['full_regressions'])} | {len(comparison['lost_keyword_cases'])} |"
        )
    return "\n".join(lines) + "\n"


def run_controls_report(args: Any) -> int:
    report = build_controls_report(
        archive_path=Path(args.controls_archive), dataset_path=Path(args.dataset),
        sidecar_path=Path(args.sidecar), label_manifest_path=Path(args.label_manifest),
        corpus_manifest_path=Path(args.corpus_manifest), expected_cases=args.expected_cases,
        context_chars=args.context_chars,
    )
    write_bucket_report(report, Path(args.controls_report))
    print(render_controls_table(report), end="")
    return 0
