"""P1b: replay frozen P1 cuts through production parent expansion."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scripts import p1_adaptive_k as p1
from scripts import rerank_score_capture
from scripts.ab_context_precision import (
    DEFAULT_DATASET_PATH,
    DEFAULT_LABEL_MANIFEST_PATH,
    DEFAULT_MULTI_DOC_DATASET_PATH,
    DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    DEFAULT_MULTI_DOC_SIDECAR_PATH,
    DEFAULT_SIDECAR_PATH,
    PROJECT_ROOT,
    _code_digests,
    _git_commit,
    _stored_path,
    sha256_file,
)
from scripts.corpus_manifest import diff_corpus, format_diff, load_manifest
from scripts.gr1b_controls import paired_comparison

SCHEMA_VERSION = "p1b-expanded-cut/v1.0"
EXPANSION_WINDOW = 2
EXPANSION_MAX_CHARS = 3600
CONTROL_ARM = "top_k_5+exp"
PRIMARY_ARM = "rel_0.2+exp"
CV_ARM = "p1_cv+exp"
DIAGNOSTIC_ARM = "top_k_3+exp"
PRIMARY_CELL = "rel_0.2"
PRIMARY_CONTEXT_CHARS = 0
DIAGNOSTIC_CONTEXT_CHARS = p1.CONTEXT_CHARS

P1_REPORT_PATH = PROJECT_ROOT / "reports/p1/p1-adaptive-k.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports/p1b/p1b-expanded-cut.json"
CORPUS_MANIFEST_PATH = PROJECT_ROOT / "evaluation/aircargo_corpus.manifest.json"
H_SCORES = PROJECT_ROOT / "evaluation/p1-511f3f9-H-rerank-scores.json"
HM_SCORES = PROJECT_ROOT / "evaluation/p1-511f3f9-Hm-rerank-scores.json"

Q1_SOURCE = "docs/operations/2026-07-18-q1-context-precision-ab-results.md"
Q1_RUN_ID = "20260718T173221Z-8c2fd13e"
Q1_ROWS = {
    "prod": {
        "rerank_k": 5,
        "window": 2,
        "max_chars": 3600,
        "context_precision": 0.5768,
        "context_recall": 0.980,
        "FULL": 97,
        "PART": 2,
        "MISS": 1,
        "source": Q1_SOURCE,
        "run_id": Q1_RUN_ID,
    },
    "k3": {
        "rerank_k": 3,
        "window": 2,
        "max_chars": 3600,
        "context_precision": 0.6179,
        "context_recall": 0.960,
        "FULL": 94,
        "PART": 4,
        "MISS": 2,
        "source": Q1_SOURCE,
        "run_id": Q1_RUN_ID,
    },
    "k3-grade": {
        "rerank_k": 3,
        "window": 2,
        "max_chars": 3600,
        "grade_docs": True,
        "context_precision": 0.6478,
        "context_recall": 0.945,
        "FULL": 92,
        "PART": 5,
        "MISS": 3,
        "source": Q1_SOURCE,
        "run_id": Q1_RUN_ID,
    },
}

CODE_PATHS = tuple(
    dict.fromkeys(
        (
            "scripts/p1b_expanded_cut.py",
            *p1.CODE_PATHS,
            "scripts/corpus_manifest.py",
            "vectordb/_base_manager.py",
            "vectordb/manager.py",
            "ingestion/loader.py",
            "config/settings.py",
        )
    )
)


def check_corpus(corpus_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Admit only a corpus whose named files match the manifest's digests."""
    manifest = load_manifest(manifest_path)
    diff = diff_corpus(manifest, corpus_dir)
    if not diff.ok():
        raise ValueError(f"corpus differs from manifest:\n{format_diff(diff)}")
    return {
        "manifest": _stored_path(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "name": manifest["name"],
        "corpus_sha256": manifest["corpus_sha256"],
        "file_count": manifest["file_count"],
    }


def rebuild_chunks(corpus_dir: Path) -> tuple[list[Any], dict[str, Any]]:
    """Rebuild the ParentExpander chunk pipeline under the frozen arm-C flags."""
    os.environ["RAG_SEMANTIC_CHUNKING"] = "false"
    os.environ["RAG_STRUCTURAL_CHUNKING"] = "true"

    from config.settings import get_settings
    from ingestion.loader import DocumentLoader
    from vectordb import manager
    from vectordb._base_manager import select_chunks

    settings = get_settings()
    if settings.semantic_chunking or not settings.structural_chunking:
        raise ValueError(
            "settings did not apply semantic_chunking=false and structural_chunking=true"
        )
    docs = DocumentLoader(recursive=False).load_documents(str(corpus_dir))
    if not docs:
        raise ValueError(f"no documents under {corpus_dir}")
    chunks = select_chunks(
        list(docs), None, settings.chunk_size, settings.chunk_overlap, settings=settings
    )
    if getattr(settings, "contextual_headers", False):
        chunks = manager.add_contextual_headers(chunks, docs, chunk_size=settings.chunk_size)
    record = {
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "contextual_headers": settings.contextual_headers,
        "semantic_chunking": settings.semantic_chunking,
        "structural_chunking": settings.structural_chunking,
        "chunk_count": len(chunks),
    }
    return chunks, record


def stamp_chunk_index(chunks: Sequence[Any]) -> None:
    """Give each chunk its ingestion-order index, including injected chunks."""
    for index, chunk in enumerate(chunks):
        metadata = chunk.metadata if isinstance(chunk.metadata, dict) else {}
        metadata["chunk_index"] = index
        chunk.metadata = metadata


def make_retriever(chunks: list[Any]) -> Any:
    """Construct the production expander and reject ambiguous retriever keys."""
    from vectordb._base_manager import HybridRetriever, _rrf_document_key

    retriever = HybridRetriever(
        vector_store=None,
        chunks=chunks,
        reranker=None,
        use_bm25=False,
        parent_expansion=True,
        parent_expansion_window=EXPANSION_WINDOW,
        parent_expansion_max_chars=EXPANSION_MAX_CHARS,
    )
    for index, chunk in enumerate(chunks):
        key = _rrf_document_key(chunk, retriever._doc_key_chars)
        mapped = retriever._chunk_positions.get(key)
        if mapped != index:
            source = (chunk.metadata or {}).get("source")
            raise ValueError(
                f"chunk position {index} maps to position {mapped} for source {source!r}; "
                f"duplicate retriever key {key!r}"
            )
    return retriever


def candidate_positions(
    rows: Sequence[dict[str, Any]],
    rankings: Sequence[dict[str, Any]],
    scores: Sequence[dict[str, Any]],
    chunks: Sequence[Any],
) -> list[list[int]]:
    """Match every fresh top-five text to exactly one same-source chunk."""
    by_source_and_text: dict[tuple[str, str], list[int]] = {}
    for index, chunk in enumerate(chunks):
        source = Path(str((chunk.metadata or {}).get("source", ""))).name
        by_source_and_text.setdefault((source, chunk.page_content), []).append(index)
    positions: list[list[int]] = []
    for row, ranking, score in zip(rows, rankings, scores, strict=True):
        selected: list[int] = []
        for rank, text in enumerate(ranking["texts"][: p1.TOP_N], start=1):
            source = row["prerank_sources"][score["fresh_order"][rank - 1]]
            matches = by_source_and_text.get((Path(source).name, text), [])
            if len(matches) != 1:
                raise ValueError(
                    f"case {row['case_id']!r} rank {rank}: expected one chunk from "
                    f"{source!r}, found {len(matches)}"
                )
            selected.append(matches[0])
        positions.append(selected)
    return positions


def expand_kept(
    retriever: Any, chunks: Sequence[Any], positions: Sequence[int], kept: int
) -> tuple[list[str], int]:
    """Expand one case's complete kept set through one production call."""
    expanded = retriever._expand_parents([chunks[position] for position in positions[:kept]])
    return (
        [document.page_content for document in expanded],
        sum(bool((document.metadata or {}).get("parent_expanded")) for document in expanded),
    )


def cv_counts(rankings: Sequence[dict[str, Any]], per_case: Sequence[dict[str, Any]]) -> list[int]:
    """Replay each H case's recorded P1 cross-validation cell and count."""
    cells = {name: (family, param) for name, family, param, _ in p1.grid_cells()}
    entries = {entry["case_id"]: entry for entry in per_case}
    if len(entries) != len(per_case):
        raise ValueError("duplicate P1 cross-validation case")
    counts: list[int] = []
    for ranking in rankings:
        case_id = ranking["case_id"]
        if case_id not in entries:
            raise ValueError(f"P1 cross-validation missing case {case_id!r}")
        entry = entries[case_id]
        cell = entry["cell"]
        if cell not in cells:
            raise ValueError(f"case {case_id!r}: unknown P1 cell {cell!r}")
        family, param = cells[cell]
        count = p1.kept_count(
            family, param, ranking["probabilities"][: p1.TOP_N], ranking["logits"][: p1.TOP_N]
        )
        if count != entry["kept"]:
            raise ValueError(
                f"case {case_id!r}: P1 recorded kept {entry['kept']} but recomputed {count}"
            )
        counts.append(count)
    foreign = set(entries).difference(ranking["case_id"] for ranking in rankings)
    if foreign:
        raise ValueError(f"P1 cross-validation contains foreign cases {', '.join(sorted(foreign))}")
    return counts


def score_rulers(
    rows: Sequence[dict[str, Any]],
    texts_by_case: Sequence[Sequence[str]],
    kept: Sequence[int],
    *,
    expanded_documents: Sequence[int] | None = None,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Score one expanded selection uncapped and under P1's diagnostic cap."""
    rankings = [{"texts": list(texts)} for texts in texts_by_case]
    expanded_counts = [len(texts) for texts in texts_by_case]
    grown_counts = [0] * len(rows) if expanded_documents is None else list(expanded_documents)
    common = {
        "dataset_path": dataset_path,
        "sidecar_path": sidecar_path,
        "label_manifest_path": label_manifest_path,
    }
    primary, _ = p1.score_selection(
        rows, rankings, expanded_counts, context_chars=PRIMARY_CONTEXT_CHARS, **common
    )
    diagnostic, _ = p1.score_selection(
        rows, rankings, expanded_counts, context_chars=DIAGNOSTIC_CONTEXT_CHARS, **common
    )
    kept_by_id = {row["case_id"]: count for row, count in zip(rows, kept, strict=True)}
    expanded_by_id = {row["case_id"]: count for row, count in zip(rows, grown_counts, strict=True)}
    for scored_rows in (primary, diagnostic):
        for row in scored_rows:
            row["kept"] = kept_by_id[row["case_id"]]
            row["expanded_documents"] = expanded_by_id[row["case_id"]]
    return primary, diagnostic


def _pool_info(
    archive: Path,
    scores_path: Path,
    digest: str,
    scores_report: dict[str, Any],
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
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
        "dataset": _stored_path(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "label_sidecar": _stored_path(sidecar_path),
        "label_sidecar_sha256": sha256_file(sidecar_path),
        "label_manifest": _stored_path(label_manifest_path),
        "label_manifest_sha256": sha256_file(label_manifest_path),
    }


def _admit_pool(archive: Path, expected_digest: str, scores_path: Path) -> dict[str, Any]:
    rows, digest = rerank_score_capture.load_pool_archive(archive, expected_digest)
    scores_report = json.loads(scores_path.read_text(encoding="utf-8"))
    scores = p1.load_scores(scores_report, rows, digest)
    p1.check_parity(rows, scores_report)
    return {
        "rows": rows,
        "digest": digest,
        "scores_report": scores_report,
        "scores": scores,
        "rankings": p1.fresh_rankings(rows, scores),
    }


def _expected_aggregate(report: dict[str, Any], pool: str, cell: str) -> dict[str, Any]:
    if cell == "p1_cv":
        return report["h"]["cross_validation"]["aggregate"]
    for entry in report[pool.lower()]["cells"]:
        if entry["name"] == cell:
            return entry["aggregate"]
    raise ValueError(f"P1 report missing {pool} cell {cell!r}")


def reproduce_p1(
    pools: dict[str, dict[str, Any]],
    p1_report: dict[str, Any],
    cv_kept: Sequence[int],
    paths: dict[str, dict[str, Path]],
) -> dict[str, Any]:
    """Compare every required unexpanded aggregate with P1, field by field."""
    checks: dict[str, dict[str, Any]] = {}
    for pool_name in ("H", "Hm"):
        pool = pools[pool_name]
        rankings = pool["rankings"]
        selections = {
            "top_k_5": [5] * len(rankings),
            PRIMARY_CELL: p1.rule_counts(rankings, "rel", 0.2),
        }
        if pool_name == "H":
            selections["p1_cv"] = list(cv_kept)
        pool_checks: dict[str, Any] = {}
        for name, kept in selections.items():
            scored, _ = p1.score_selection(
                pool["rows"], rankings, kept, context_chars=p1.CONTEXT_CHARS, **paths[pool_name]
            )
            observed = p1.aggregate(scored)
            expected = _expected_aggregate(p1_report, pool_name, name)
            pool_checks[name] = {
                "expected": expected,
                "observed": observed,
                "equal": observed == expected,
            }
        checks[pool_name] = pool_checks
    return {
        "checks": checks,
        "reproduces_p1": all(
            check["equal"] for pool_checks in checks.values() for check in pool_checks.values()
        ),
    }


def _score_pool(
    pool_name: str,
    pool: dict[str, Any],
    positions: Sequence[Sequence[int]],
    chunks: Sequence[Any],
    retriever: Any,
    cv_kept: Sequence[int],
    paths: dict[str, Path],
    *,
    grid_bootstrap_samples: int,
    headline_bootstrap_samples: int,
    seed: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    rankings = pool["rankings"]
    selections = {
        CONTROL_ARM: [5] * len(rankings),
        PRIMARY_ARM: p1.rule_counts(rankings, "rel", 0.2),
    }
    if pool_name == "H":
        selections[CV_ARM] = list(cv_kept)
    selections[DIAGNOSTIC_ARM] = [3] * len(rankings)
    arms: dict[str, Any] = {}
    scored_by_arm: dict[str, list[dict[str, Any]]] = {}
    for arm, kept in selections.items():
        expanded = [
            expand_kept(retriever, chunks, case_positions, count)
            for case_positions, count in zip(positions, kept, strict=True)
        ]
        texts = [result[0] for result in expanded]
        grown = [result[1] for result in expanded]
        primary, diagnostic = score_rulers(
            pool["rows"], texts, kept, expanded_documents=grown, **paths
        )
        scored_by_arm[arm] = primary
        arms[arm] = {
            "aggregate": p1.aggregate(primary),
            "diagnostic_aggregate": p1.aggregate(diagnostic),
            "kept_counts": list(kept),
            "mean_context_chars": round(
                sum(row["context_chars"] for row in primary) / len(primary), 4
            ),
            "expanded_document_total": sum(grown),
            "per_case": [
                {
                    "case_id": row["case_id"],
                    "kept": row["kept"],
                    "expanded_documents": row["expanded_documents"],
                    "context_chars": row["context_chars"],
                }
                for row in primary
            ],
        }
    control = scored_by_arm[CONTROL_ARM]
    for arm, rows in scored_by_arm.items():
        if arm == CONTROL_ARM:
            continue
        samples = (
            headline_bootstrap_samples
            if pool_name == "H" and arm == PRIMARY_ARM
            else grid_bootstrap_samples
        )
        arms[arm]["comparison"] = paired_comparison(rows, control, samples=samples, seed=seed)
        arms[arm]["fact_losses"] = p1.fact_losses(rows, control)
    return {"arms": arms}, scored_by_arm


def decide(
    scored: dict[str, dict[str, list[dict[str, Any]]]], reproduces_p1: bool
) -> dict[str, Any]:
    """Apply only the five preregistered gates to the scored rows."""
    h = scored["H"]
    hm = scored["Hm"]
    primary_flags = p1.verdict_flags(h[PRIMARY_ARM], h[CONTROL_ARM])
    cv_flags = p1.verdict_flags(h[CV_ARM], h[CONTROL_ARM])
    hm_flags = p1.verdict_flags(hm[PRIMARY_ARM], hm[CONTROL_ARM])
    losses = {
        "H": {
            PRIMARY_ARM: p1.fact_losses(h[PRIMARY_ARM], h[CONTROL_ARM]),
            CV_ARM: p1.fact_losses(h[CV_ARM], h[CONTROL_ARM]),
        },
        "Hm": {PRIMARY_ARM: p1.fact_losses(hm[PRIMARY_ARM], hm[CONTROL_ARM])},
    }
    fact_loss_cases = {
        pool: {arm: [loss["case_id"] for loss in arm_losses] for arm, arm_losses in by_arm.items()}
        for pool, by_arm in losses.items()
    }
    conditions = {
        "precision_gate_met": primary_flags["precision_gate_met"],
        "review_floor_met": primary_flags["review_floor_met"],
        "coverage_and_facts_met": primary_flags["h_relative_constraints_met"]
        and not losses["H"][PRIMARY_ARM],
        "held_out_check_met": all(cv_flags.values()) and not losses["H"][CV_ARM],
        "hm_check_met": hm_flags["h_relative_constraints_met"] and not losses["Hm"][PRIMARY_ARM],
    }
    decision = (
        "INVALID_CONTROL"
        if not reproduces_p1
        else "SHIP_CANDIDATE"
        if all(conditions.values())
        else "NO_SHIP"
    )
    return {
        **conditions,
        "fact_loss_cases": fact_loss_cases,
        "decision": decision,
        "scope": (
            "H-relative exploratory verdict on agent-authored cases; no default changes. "
            "A SHIP_CANDIDATE still needs P2's blinded relevance judgment, a fresh-query "
            "confirmation and the owner's decision before any default changes."
        ),
    }


def compare_q1(h_arms: dict[str, Any]) -> dict[str, Any]:
    """Quote Q1 and mark approximate matches, without gating the verdict."""
    checks = {}
    for name, arm in (("prod", CONTROL_ARM), ("k3", DIAGNOSTIC_ARM)):
        expected = Q1_ROWS[name]
        observed = h_arms[arm]["aggregate"]
        equal = (
            abs(observed["context_precision"] - expected["context_precision"]) <= 0.0001 + 1e-9
            and abs(observed["context_recall"] - expected["context_recall"]) <= 0.001 + 1e-9
            and all(observed[key] == expected[key] for key in ("FULL", "PART", "MISS"))
        )
        checks[name] = {"arm": arm, "equal": equal}
    return {
        "rows": Q1_ROWS,
        "checks": checks,
        "note": "Reported historical comparison; equality is not required for the verdict.",
    }


def build_report(
    *,
    corpus_dir: Path,
    h_scores: Path = H_SCORES,
    hm_scores: Path = HM_SCORES,
    h_archive: Path = p1.H_ARCHIVE,
    hm_archive: Path = p1.HM_ARCHIVE,
    h_pool_sha256: str = p1.H_POOL_SHA256,
    hm_pool_sha256: str = p1.HM_POOL_SHA256,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    sidecar_path: Path = DEFAULT_SIDECAR_PATH,
    label_manifest_path: Path = DEFAULT_LABEL_MANIFEST_PATH,
    hm_dataset_path: Path = DEFAULT_MULTI_DOC_DATASET_PATH,
    hm_sidecar_path: Path = DEFAULT_MULTI_DOC_SIDECAR_PATH,
    hm_label_manifest_path: Path = DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    corpus_manifest_path: Path = CORPUS_MANIFEST_PATH,
    p1_report_path: Path = P1_REPORT_PATH,
    grid_bootstrap_samples: int = p1.GRID_BOOTSTRAP_SAMPLES,
    headline_bootstrap_samples: int = p1.HEADLINE_BOOTSTRAP_SAMPLES,
    seed: int = p1.BOOTSTRAP_SEED,
    code_commit: str | None = None,
    chunks: list[Any] | None = None,
) -> dict[str, Any]:
    """Build P1b only from a checked corpus and admitted synthetic or pinned pools."""
    corpus = check_corpus(corpus_dir, corpus_manifest_path)
    p1_report = json.loads(p1_report_path.read_text(encoding="utf-8"))
    primary_cell = p1_report["h"]["in_sample_best"]["cell"]
    if primary_cell != PRIMARY_CELL:
        raise ValueError(f"P1 primary cell {primary_cell!r} differs from {PRIMARY_CELL!r}")
    if chunks is None:
        chunks, chunking = rebuild_chunks(corpus_dir)
    else:
        chunking = {"chunks": "injected", "chunk_count": len(chunks)}
    stamp_chunk_index(chunks)
    chunking["chunk_index"] = "ingestion order, as vectordb/manager.py"
    retriever = make_retriever(chunks)
    pools = {
        "H": _admit_pool(h_archive, h_pool_sha256, h_scores),
        "Hm": _admit_pool(hm_archive, hm_pool_sha256, hm_scores),
    }
    positions = {
        name: candidate_positions(pool["rows"], pool["rankings"], pool["scores"], chunks)
        for name, pool in pools.items()
    }
    cv_kept = cv_counts(pools["H"]["rankings"], p1_report["h"]["cross_validation"]["per_case"])
    paths = {
        "H": {
            "dataset_path": dataset_path,
            "sidecar_path": sidecar_path,
            "label_manifest_path": label_manifest_path,
        },
        "Hm": {
            "dataset_path": hm_dataset_path,
            "sidecar_path": hm_sidecar_path,
            "label_manifest_path": hm_label_manifest_path,
        },
    }
    reproduction = reproduce_p1(pools, p1_report, cv_kept, paths)
    reports = {}
    scored = {}
    for name in ("H", "Hm"):
        reports[name], scored[name] = _score_pool(
            name,
            pools[name],
            positions[name],
            chunks,
            retriever,
            cv_kept,
            paths[name],
            grid_bootstrap_samples=grid_bootstrap_samples,
            headline_bootstrap_samples=headline_bootstrap_samples,
            seed=seed,
        )
    corpus["chunk_count"] = len(chunks)
    verdict = decide(scored, reproduction["reproduces_p1"])
    verdict["headline"] = f"{PRIMARY_ARM} against {CONTROL_ARM} on H"
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "measured",
        "labels": p1_report["labels"],
        "provenance": {
            "code": dict(
                _git_commit()
                if code_commit is None
                else {"commit": code_commit, "tree_clean": None},
                files=_code_digests(CODE_PATHS),
            ),
            "corpus": corpus,
            "pools": {
                "H": _pool_info(
                    h_archive,
                    h_scores,
                    pools["H"]["digest"],
                    pools["H"]["scores_report"],
                    dataset_path,
                    sidecar_path,
                    label_manifest_path,
                ),
                "Hm": _pool_info(
                    hm_archive,
                    hm_scores,
                    pools["Hm"]["digest"],
                    pools["Hm"]["scores_report"],
                    hm_dataset_path,
                    hm_sidecar_path,
                    hm_label_manifest_path,
                ),
            },
            "p1_report": {
                "path": _stored_path(p1_report_path),
                "sha256": sha256_file(p1_report_path),
            },
        },
        "config": {
            "window": EXPANSION_WINDOW,
            "max_chars": EXPANSION_MAX_CHARS,
            "chunking": chunking,
            "rulers": {
                "primary": {"context_chars": PRIMARY_CONTEXT_CHARS},
                "diagnostic": {"context_chars": DIAGNOSTIC_CONTEXT_CHARS},
            },
            "bootstrap": {
                "grid_samples": grid_bootstrap_samples,
                "headline_samples": headline_bootstrap_samples,
                "seed": seed,
                "method": "paired case bootstrap percentile 95%, linear quantiles",
            },
            "precision_gate": p1.PRECISION_GATE,
            "review_floor": p1.REVIEW_FLOOR,
            "arms": {
                CONTROL_ARM: "keep the fresh top five",
                PRIMARY_ARM: "keep probability >= 0.2 * rank-one probability",
                CV_ARM: "keep each H case's recorded P1 cross-validation cell",
                DIAGNOSTIC_ARM: "keep the fresh top three; diagnostic only",
            },
            "preregistered": (
                "arms, rulers and verdict fixed on 2026-09-24 before any expanded-context "
                "metric was computed (docs/specs/p1b-expanded-cut-plan.md)"
            ),
        },
        "reproduction": reproduction,
        "h": reports["H"],
        "hm": reports["Hm"],
        "q1_comparison": compare_q1(reports["H"]["arms"]),
        "verdict": verdict,
    }


def render_table(report: dict[str, Any]) -> str:
    """Render the two pools, the P1 reproduction and the five verdict gates."""
    lines = [
        "| pool | arm | precision | recall | FULL/PART/MISS | mean kept | "
        "mean context chars | precision delta | CI95 |\n",
        "|---|---|---:|---:|---|---:|---:|---:|---|\n",
    ]
    for pool_name, key in (("H", "h"), ("Hm", "hm")):
        for arm, entry in report[key]["arms"].items():
            agg = entry["aggregate"]
            comparison = entry.get("comparison")
            if comparison is None:
                delta, ci = "—", "—"
            else:
                delta = f"{comparison['precision_delta']:+.4f}"
                low, high = comparison["precision_delta_ci95"]
                ci = f"[{low:.4f}, {high:.4f}]"
            lines.append(
                f"| {pool_name} | {arm} | {agg['context_precision']:.4f} "
                f"| {agg['context_recall']:.4f} "
                f"| {agg['FULL']}/{agg['PART']}/{agg['MISS']} "
                f"| {agg['mean_kept']:.2f} | {entry['mean_context_chars']:.2f} "
                f"| {delta} | {ci} |\n"
            )
    reproduction = report["reproduction"]["reproduces_p1"]
    lines.append(f"\n- Reproduces P1: {reproduction}\n")
    for name in (
        "precision_gate_met",
        "review_floor_met",
        "coverage_and_facts_met",
        "held_out_check_met",
        "hm_check_met",
    ):
        lines.append(f"- {name}: {report['verdict'][name]}\n")
    lines.append(f"**Decision: {report['verdict']['decision']}**\n")
    return "".join(lines)


def write_report(path: Path, report: dict[str, Any]) -> Path:
    """Write finite, indented JSON with P1's single-newline convention."""
    return p1.write_report(path, report)


def main(argv: Sequence[str] | None = None) -> int:
    """Build a P1b report for an explicitly supplied corpus directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--h-scores", type=Path, default=H_SCORES)
    parser.add_argument("--hm-scores", type=Path, default=HM_SCORES)
    parser.add_argument("--corpus-manifest", type=Path, default=CORPUS_MANIFEST_PATH)
    parser.add_argument("--p1-report", type=Path, default=P1_REPORT_PATH)
    parser.add_argument("--code-commit", default=None)
    args = parser.parse_args(argv)
    report = build_report(
        corpus_dir=args.corpus,
        h_scores=args.h_scores,
        hm_scores=args.hm_scores,
        corpus_manifest_path=args.corpus_manifest,
        p1_report_path=args.p1_report,
        code_commit=args.code_commit,
    )
    write_report(args.report, report)
    print(render_table(report), end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
