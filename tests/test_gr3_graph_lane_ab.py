"""Synthetic, no-model contract tests for the GR-3 graph-lane A/B report."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.question_class_labels import QUESTION_CLASSES
from evaluation.ragas_eval import context_precision
from scripts.ab_context_precision import (
    PHASE_C_CONTEXT_CHARS,
    PHASE_C_TOP_K,
    _nearest_rank,
    sha256_file,
)
from scripts.generator_benchmark import load_benchmark_cases
from scripts.gr3_graph_lane_ab import (
    build_gr3_report,
    decide,
    main,
    paired_generation,
    parse_args,
    pool_parity,
    render_gr3_table,
    write_gr3_report,
)

_COMMIT = "1" * 40
_HOST = "deproject-mac, Intel i5-7500, 8 GiB, macOS 13.7.8"
_CASE_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("alpha-full", "single_hop", ("alpha", "beta")),
    ("gamma-full", "single_hop", ("gamma",)),
    ("delta-multi", "multi_hop", ("delta", "epsilon")),
)


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    return path


def _cands_for(case_id: str, keywords: tuple[str, ...], count: int) -> list[str]:
    joined = " ".join(keywords)
    relevant = [
        f"{joined} relevant-1 {case_id}",
        f"{joined} relevant-2 {case_id}",
        f"{joined} relevant-3 {case_id}",
    ]
    noise = [
        f"noise-4 {case_id} unrelated filler",
        f"noise-5 {case_id} unrelated filler",
    ]
    return (relevant + noise)[:count]


def _pool_row(
    case_id: str,
    keywords: tuple[str, ...],
    *,
    n_cands: int,
    timing: dict[str, float] | None,
    rerank_s: float,
    cands: list[str] | None = None,
) -> dict[str, Any]:
    texts = list(cands) if cands is not None else _cands_for(case_id, keywords, n_cands)
    sources = [f"{case_id}-{i}.md" for i in range(len(texts))]
    row: dict[str, Any] = {
        "case_id": case_id,
        "query": "x",
        "kws": list(keywords),
        "rerank_k": 5,
        "prerank_cands": list(texts),
        "prerank_sources": list(sources),
        "reranked_cands": list(texts),
        "reranked_sources": list(sources),
        "cands": list(texts),
        "cand_sources": list(sources),
        "rerank_s": rerank_s,
    }
    if timing is not None:
        row["timing_ms"] = dict(timing)
    return row


def _write_dataset(root: Path, *, prefix: str) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    dataset = root / f"{prefix}-cases.jsonl"
    sidecar = root / f"{prefix}-classes.jsonl"
    label_manifest = root / f"{prefix}-classes.manifest.json"
    corpus_manifest = root / f"{prefix}-corpus.manifest.json"
    _write_jsonl(
        dataset,
        [
            {
                "case_id": case_id,
                "tenant_id": "aircargo",
                "query": "x",
                "expected": {"answer_contains": list(keywords)},
            }
            for case_id, _label, keywords in _CASE_SPECS
        ],
    )
    _write_jsonl(
        sidecar,
        [
            {
                "case_id": case_id,
                "question_class": label,
                "reason": "synthetic fixture",
                "labelled_by": "test",
                "labelled_at": "2026-09-13",
                "batch": 1,
                "approved_by": None,
            }
            for case_id, label, _keywords in _CASE_SPECS
        ],
    )
    _write_json(
        label_manifest,
        {
            "schema_version": "aircargo-question-class-manifest/v1.0",
            "dataset": dataset.name,
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "case_count": len(_CASE_SPECS),
        },
    )
    _write_json(
        corpus_manifest,
        {
            "name": "synthetic",
            "root": "tests/fixtures/synthetic",
            "corpus_sha256": "c" * 64,
            "file_count": 1,
        },
    )
    return {
        "dataset": dataset,
        "sidecar": sidecar,
        "label_manifest": label_manifest,
        "corpus_manifest": corpus_manifest,
    }


def _write_pool(
    path: Path,
    *,
    n_cands: int,
    timing_kind: str | None,
    rerank_extra_s: float = 0.0,
    drift_ids: tuple[str, ...] = (),
) -> Path:
    rows: list[dict[str, Any]] = []
    for index, (case_id, _label, keywords) in enumerate(_CASE_SPECS):
        if timing_kind == "hybrid":
            timing: dict[str, float] | None = {
                "vector": 10.0 + 10.0 * index,
                "bm25": 10.0 + 10.0 * index,
            }
        elif timing_kind == "g1":
            timing = {
                "vector": 10.0 + 10.0 * index,
                "bm25": 10.0 + 10.0 * index,
                "entity": 0.0,
            }
        elif timing_kind == "g2":
            timing = {
                "vector": 10.0 + 10.0 * index,
                "bm25": 10.0 + 10.0 * index,
                "entity": 1.0,
            }
        else:
            timing = None
        row = _pool_row(
            case_id,
            keywords,
            n_cands=n_cands,
            timing=timing,
            rerank_s=0.1 + 0.1 * index + rerank_extra_s,
        )
        if case_id in drift_ids:
            row["cands"] = ["DRIFT " + row["cands"][0], *row["cands"][1:]]
        rows.append(row)
    return _write_json(path, rows)


def _write_generation(
    path: Path,
    *,
    case_ids: list[str],
    faithfulness: dict[str, float] | float,
    context_count: int | None = None,
    invalid: dict[str, int] | None = None,
    provenance_update: dict[str, Any] | None = None,
    config_update: dict[str, Any] | None = None,
    aggregate_update: dict[str, Any] | None = None,
) -> Path:
    runs: list[dict[str, Any]] = []
    for run_index in range(1, 4):
        cases: list[dict[str, Any]] = []
        for case_id in case_ids:
            score = faithfulness[case_id] if isinstance(faithfulness, dict) else float(faithfulness)
            valid = not (invalid and invalid.get(case_id) == run_index)
            row: dict[str, Any] = {
                "case_id": case_id,
                "generation_valid": valid,
                "llm_judge_valid": valid,
                "nli_valid": valid,
                "scores": {
                    "faithfulness": score,
                    "answer_relevancy": 0.9,
                    "context_precision": 0.6,
                    "context_recall": 0.9,
                },
                "nli": {
                    "nli_faithfulness": 0.7,
                    "supported_claim_rate": 0.8,
                },
                "latency_ms": 100.0,
            }
            if context_count is not None:
                row["context_count"] = context_count
            cases.append(row)
        runs.append({"run_index": run_index, "cases": cases})
    provenance: dict[str, Any] = {
        "code_sha": "c06bdf5721b434eff32dcf5b9991221d5b2a15f8",
        "code_tree_clean": True,
        "dataset_path": "evaluation/curated_cases_aircargo.jsonl",
        "dataset_sha256": "a" * 64,
        "contexts_path": "hybrid-contexts.json",
        "contexts_sha256": "b" * 64,
        "ollama_model": "qwen2.5:7b",
        "ollama_model_digest": ("845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"),
        "ollama_model_metadata": {"name": "qwen2.5:7b"},
        "nli_model": "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        "nli_revision": "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c",
        "host": {"platform": "macOS-13.7.8-x86_64", "python": "3.11.15", "machine": "x86_64"},
        "config": {
            "prompt_version": "aircargo-context-only-ru-v1",
            "runs": 3,
            "expected_cases": len(case_ids),
            "selected_cases": len(case_ids),
            "top_k_override": None,
            "context_chars": 6000,
            "seed_base": 42,
            "temperature": 0.0,
            "num_ctx": 4096,
            "num_predict": 384,
            "nli_batch_size": 4,
            "nli_support_threshold": 0.5,
        },
        "ollama_runtime": {"size_bytes": 1},
        "nli_process_peak_rss_bytes": 1,
    }
    if provenance_update:
        provenance.update(copy.deepcopy(provenance_update))
    if config_update:
        provenance["config"] = {**provenance["config"], **config_update}
    aggregate = {
        name: {
            "mean": 0.8,
            "ci_low": 0.8,
            "ci_high": 0.8,
            "n": 3,
            "ci_method": "student-t-95",
        }
        for name in (
            "llm_faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
            "nli_faithfulness",
            "nli_supported_claim_rate",
            "mean_latency_ms",
        )
    }
    if aggregate_update:
        for name, payload in aggregate_update.items():
            aggregate[name] = {**aggregate[name], **payload}
    return _write_json(
        path,
        {
            "kind": "phase-c-generator-benchmark",
            "evidence_class": "measured",
            "provenance": provenance,
            "aggregate": aggregate,
            "runs": runs,
        },
    )


def _bundle(
    tmp_path: Path,
    *,
    g2_n_cands: int = 3,
    hm_timing: bool = True,
    hm_drift_ids: tuple[str, ...] = (),
    g2m_rerank_extra_s: float = 0.0,
    with_generation: bool = True,
    generation_identical: bool = True,
) -> tuple[dict[str, Path], dict[str, Any]]:
    phase_meta = _write_dataset(tmp_path / "phase", prefix="phase")
    bucket_meta = _write_dataset(tmp_path / "bucket", prefix="bucket")
    phase = tmp_path / "phase"
    bucket = tmp_path / "bucket"
    paths: dict[str, Path] = {
        **{f"phase_{key}": value for key, value in phase_meta.items()},
        **{f"bucket_{key}": value for key, value in bucket_meta.items()},
        "phase_h": _write_pool(phase / "h.json", n_cands=5, timing_kind=None),
        "phase_hm": _write_pool(
            phase / "hm.json",
            n_cands=5,
            timing_kind="hybrid" if hm_timing else None,
            drift_ids=hm_drift_ids,
        ),
        "phase_g1": _write_pool(phase / "g1.json", n_cands=5, timing_kind=None),
        "phase_g2": _write_pool(phase / "g2.json", n_cands=g2_n_cands, timing_kind=None),
        "phase_g1m": _write_pool(phase / "g1m.json", n_cands=5, timing_kind="g1"),
        "phase_g2m": _write_pool(
            phase / "g2m.json",
            n_cands=g2_n_cands,
            timing_kind="g2",
            rerank_extra_s=g2m_rerank_extra_s,
        ),
        "bucket_hm": _write_pool(
            bucket / "hm.json",
            n_cands=5,
            timing_kind="hybrid" if hm_timing else None,
        ),
        "bucket_g1": _write_pool(bucket / "g1.json", n_cands=5, timing_kind=None),
        "bucket_g2": _write_pool(bucket / "g2.json", n_cands=g2_n_cands, timing_kind=None),
        "bucket_g1m": _write_pool(bucket / "g1m.json", n_cands=5, timing_kind="g1"),
        "bucket_g2m": _write_pool(
            bucket / "g2m.json",
            n_cands=g2_n_cands,
            timing_kind="g2",
            rerank_extra_s=g2m_rerank_extra_s,
        ),
    }
    case_ids = [case_id for case_id, _label, _kws in _CASE_SPECS]
    kwargs: dict[str, Any] = {
        "phase_c_h": paths["phase_h"],
        "phase_c_hm": paths["phase_hm"],
        "phase_c_g1": paths["phase_g1"],
        "phase_c_g2": paths["phase_g2"],
        "phase_c_g1m": paths["phase_g1m"],
        "phase_c_g2m": paths["phase_g2m"],
        "bucket_hm": paths["bucket_hm"],
        "bucket_g1": paths["bucket_g1"],
        "bucket_g2": paths["bucket_g2"],
        "bucket_g1m": paths["bucket_g1m"],
        "bucket_g2m": paths["bucket_g2m"],
        "phase_c_dataset": paths["phase_dataset"],
        "phase_c_sidecar": paths["phase_sidecar"],
        "phase_c_label_manifest": paths["phase_label_manifest"],
        "phase_c_corpus_manifest": paths["phase_corpus_manifest"],
        "bucket_dataset": paths["bucket_dataset"],
        "bucket_sidecar": paths["bucket_sidecar"],
        "bucket_label_manifest": paths["bucket_label_manifest"],
        "bucket_corpus_manifest": paths["bucket_corpus_manifest"],
        "expected_cases": len(_CASE_SPECS),
        "bucket_expected_cases": len(_CASE_SPECS),
        "code_commit": _COMMIT,
        "host": _HOST,
        "evidence_class": "synthetic",
    }
    if with_generation:
        paths["hybrid_generation"] = _write_generation(
            tmp_path / "hybrid-generation.json",
            case_ids=case_ids,
            faithfulness=0.83,
        )
        graph_update: dict[str, Any] = {
            "code_sha": "d" * 40,
            "contexts_sha256": "e" * 64,
            "contexts_path": "graph-contexts.json",
        }
        graph_config = {"allow_short_contexts": True}
        graph_faith = 0.83 if generation_identical else 0.73
        paths["graph_generation"] = _write_generation(
            tmp_path / "graph-generation.json",
            case_ids=case_ids,
            faithfulness=graph_faith,
            context_count=g2_n_cands,
            provenance_update=graph_update,
            config_update=graph_config,
        )
        kwargs["hybrid_generation"] = paths["hybrid_generation"]
        kwargs["graph_generation"] = paths["graph_generation"]
    return paths, kwargs


def _hand_precision(pool: Path, dataset: Path) -> tuple[float, float, float]:
    cases = load_benchmark_cases(
        dataset_path=dataset,
        contexts_path=pool,
        expected_cases=len(_CASE_SPECS),
        top_k=PHASE_C_TOP_K,
        context_chars=PHASE_C_CONTEXT_CHARS,
        allow_short_contexts=True,
    )
    precs = [
        round(
            context_precision(
                case["query"],
                [{"page_content": text} for text in case["contexts"]],
                case["expected_keywords"],
            ),
            4,
        )
        for case in cases
    ]
    mean_contexts = round(sum(len(case["contexts"]) for case in cases) / len(cases), 4)
    mean_characters = round(
        sum(sum(len(text) for text in case["contexts"]) for case in cases) / len(cases),
        1,
    )
    return round(sum(precs) / len(precs), 4), mean_contexts, mean_characters


def test_shorter_arm_publishes_fewer_contexts_and_matching_precision(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    report = build_gr3_report(**kwargs)
    h = report["phase_c"]["arms"]["H"]
    g2 = report["phase_c"]["arms"]["G2"]
    h_prec, h_ctx, h_chars = _hand_precision(kwargs["phase_c_h"], kwargs["phase_c_dataset"])
    g2_prec, g2_ctx, g2_chars = _hand_precision(kwargs["phase_c_g2"], kwargs["phase_c_dataset"])

    assert h["mean_contexts"] == 5.0
    assert g2["mean_contexts"] == 3.0
    assert h["mean_contexts"] != g2["mean_contexts"]
    assert h["mean_characters"] != g2["mean_characters"]
    assert h["mean_contexts"] == h_ctx
    assert g2["mean_contexts"] == g2_ctx
    assert h["mean_characters"] == h_chars
    assert g2["mean_characters"] == g2_chars
    assert h["all_cases"]["context_precision"] == h_prec
    assert g2["all_cases"]["context_precision"] == g2_prec
    assert g2_prec > h_prec


def test_every_sidecar_class_has_a_row_and_empty_class_is_null(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    report = build_gr3_report(**kwargs)
    buckets = report["phase_c"]["arms"]["H"]["buckets"]
    by_class = {row["question_class"]: row for row in buckets}
    assert set(QUESTION_CLASSES) <= set(by_class)
    assert by_class["aggregation"]["context_precision"] is None
    assert by_class["aggregation"]["context_recall"] is None
    assert by_class["global"]["context_precision"] is None
    assert by_class["global"]["num_cases"] == 0
    assert by_class["single_hop"]["num_cases"] == 2
    assert by_class["multi_hop"]["num_cases"] == 1


def test_arm_over_a_different_case_set_is_refused(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    rows = json.loads(kwargs["phase_c_g1"].read_text(encoding="utf-8"))
    rows[0]["case_id"] = "other-case"
    kwargs["phase_c_g1"].write_text(json.dumps(rows), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match=r"^G1:") as excinfo:
        build_gr3_report(**kwargs)
    assert "case" in str(excinfo.value).lower()


def test_parity_identical_and_two_top5_drifts_are_named(tmp_path: Path) -> None:
    drift_ids = ("alpha-full", "delta-multi")
    _paths, kwargs = _bundle(tmp_path, hm_drift_ids=drift_ids)
    report = build_gr3_report(**kwargs)

    hm_vs_h = report["parity"]["phase_c"]["Hm_vs_H"]
    assert hm_vs_h["identical"] is False
    assert hm_vs_h["fields"]["top-5 cands"]["count"] == 2
    assert hm_vs_h["fields"]["top-5 cands"]["case_ids"] == sorted(drift_ids)

    g1_parity = pool_parity(
        json.loads(kwargs["phase_c_g1m"].read_text(encoding="utf-8")),
        json.loads(kwargs["phase_c_g1"].read_text(encoding="utf-8")),
    )
    assert g1_parity["identical"] is True
    assert report["parity"]["phase_c"]["G1m_vs_G1"]["identical"] is True
    assert report["parity"]["multi_doc_bucket"]["G2m_vs_G2"]["identical"] is True


def test_latency_nearest_rank_null_timing_and_p95_gate(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    report = build_gr3_report(**kwargs)
    hybrid = report["latency"]["phase_c"]["hybrid"]
    totals = [120.0, 240.0, 360.0]
    assert hybrid["cases"] == 3
    assert hybrid["total_ms"]["p50"] == round(
        float(_nearest_rank(totals, numerator=1, denominator=2)), 1
    )
    assert hybrid["total_ms"]["p95"] == round(
        float(_nearest_rank(totals, numerator=19, denominator=20)), 1
    )
    assert hybrid["pools_ms"]["p50"] == 40.0
    assert hybrid["pools_ms"]["p95"] == 60.0
    assert report["latency"]["phase_c"]["p95_total_delta_ms"]["G2"] == 1.0

    _paths_null, kwargs_null = _bundle(tmp_path / "null-hm", hm_timing=False)
    null_report = build_gr3_report(**kwargs_null)
    null_hybrid = null_report["latency"]["phase_c"]["hybrid"]
    assert null_hybrid["pools_ms"]["p50"] is None
    assert null_hybrid["pools_ms"]["p95"] is None
    assert null_hybrid["total_ms"]["p50"] is None
    assert null_hybrid["total_ms"]["p95"] is None
    assert null_report["latency"]["phase_c"]["p95_total_delta_ms"]["G1"] is None
    assert null_report["latency"]["phase_c"]["p95_total_delta_ms"]["G2"] is None
    retrieve = null_report["decision"]["criteria"]["retrieve_p95_within_200ms"]
    assert retrieve["status"] == "not_measured"
    assert retrieve["host"] == _HOST
    assert null_report["decision"]["verdict"] == "NO_SHIP_TO_DEFAULT"
    assert "retrieve_p95_within_200ms" in null_report["decision"]["failed_criteria"]

    _paths_slow, kwargs_slow = _bundle(tmp_path / "slow-g2", g2m_rerank_extra_s=0.3)
    slow = build_gr3_report(**kwargs_slow)
    slow_retrieve = slow["decision"]["criteria"]["retrieve_p95_within_200ms"]
    assert slow_retrieve["status"] == "fail"
    assert slow_retrieve["delta_ms"] == 301.0
    assert slow_retrieve["host"] == _HOST
    assert _HOST in render_gr3_table(slow)
    assert slow["decision"]["verdict"] == "NO_SHIP_TO_DEFAULT"


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_paired_bootstrap_identical_lower_and_seed_stability(tmp_path: Path) -> None:
    case_ids = [case_id for case_id, _label, _kws in _CASE_SPECS]
    hybrid_path = _write_generation(tmp_path / "hybrid.json", case_ids=case_ids, faithfulness=0.8)
    graph_path = _write_generation(
        tmp_path / "graph.json",
        case_ids=case_ids,
        faithfulness=0.8,
        context_count=3,
        provenance_update={"code_sha": "d" * 40, "contexts_sha256": "e" * 64},
        config_update={"allow_short_contexts": True},
    )
    hybrid = _load_report(hybrid_path)
    graph = _load_report(graph_path)
    identical = paired_generation(hybrid, graph)
    faith = identical["metrics"]["llm_faithfulness"]
    assert faith["mean_difference"] == 0
    assert faith["ci_low"] == 0
    assert faith["ci_high"] == 0
    assert faith["ci_high_raw"] == 0
    assert identical["method"] == "paired case-level percentile bootstrap"

    lower_path = _write_generation(
        tmp_path / "graph-lower.json",
        case_ids=case_ids,
        faithfulness=0.7,
        context_count=3,
        provenance_update={"code_sha": "d" * 40, "contexts_sha256": "e" * 64},
        config_update={"allow_short_contexts": True},
    )
    lowered = paired_generation(hybrid, _load_report(lower_path))
    assert lowered["metrics"]["llm_faithfulness"]["ci_high"] < 0

    first = paired_generation(hybrid, graph, seed=20260918)
    second = paired_generation(hybrid, graph, seed=20260918)
    assert (
        first["metrics"]["llm_faithfulness"]["ci_low"]
        == second["metrics"]["llm_faithfulness"]["ci_low"]
    )
    assert (
        first["metrics"]["llm_faithfulness"]["ci_high"]
        == second["metrics"]["llm_faithfulness"]["ci_high"]
    )


def test_seeds_are_not_variance_and_decision_reads_paired_interval(tmp_path: Path) -> None:
    case_ids = [f"case-{index:02d}" for index in range(10)]
    hybrid_path = _write_generation(
        tmp_path / "hybrid.json",
        case_ids=case_ids,
        faithfulness=0.83,
        aggregate_update={"llm_faithfulness": {"mean": 0.83, "ci_low": 0.83, "ci_high": 0.83}},
    )
    graph_faith = {
        case_id: (0.83 + 0.2 if index < 5 else 0.83 - 0.3) for index, case_id in enumerate(case_ids)
    }
    graph_path = _write_generation(
        tmp_path / "graph.json",
        case_ids=case_ids,
        faithfulness=graph_faith,
        context_count=3,
        provenance_update={"code_sha": "d" * 40, "contexts_sha256": "e" * 64},
        config_update={"allow_short_contexts": True},
        aggregate_update={"llm_faithfulness": {"mean": 0.78, "ci_low": 0.78, "ci_high": 0.78}},
    )
    generation = paired_generation(_load_report(hybrid_path), _load_report(graph_path))
    llm = generation["metrics"]["llm_faithfulness"]
    assert generation["hybrid_aggregate"]["llm_faithfulness"]["ci_low"] == 0.83
    assert generation["hybrid_aggregate"]["llm_faithfulness"]["ci_high"] == 0.83
    assert generation["graph_aggregate"]["llm_faithfulness"]["ci_low"] == 0.78
    assert generation["graph_aggregate"]["llm_faithfulness"]["ci_high"] == 0.78
    assert (
        generation["graph_aggregate"]["llm_faithfulness"]["ci_high"]
        < generation["hybrid_aggregate"]["llm_faithfulness"]["ci_low"]
    )
    assert llm["ci_high"] > 0

    decision = decide(
        {
            "phase_c": {
                "arms": {
                    "H": {"all_cases": {"context_precision": 0.50, "FULL": 10}},
                    "G2": {"all_cases": {"context_precision": 0.60, "FULL": 10}},
                }
            },
            "latency": {
                "host": _HOST,
                "phase_c": {
                    "hybrid": {"total_ms": {"p95": 100.0}},
                    "G2": {"total_ms": {"p95": 150.0}},
                },
            },
            "generation": generation,
        }
    )
    assert decision["criteria"]["llm_faithfulness_not_significantly_fallen"]["status"] == "pass"
    assert decision["criteria"]["nli_faithfulness_not_significantly_fallen"]["status"] == "pass"
    assert decision["verdict"] == "AUTO_DEFAULT_AUTHORIZED"


def test_invalid_case_is_excluded_from_every_metric(tmp_path: Path) -> None:
    case_ids = [case_id for case_id, _label, _kws in _CASE_SPECS]
    hybrid = _load_report(
        _write_generation(tmp_path / "hybrid.json", case_ids=case_ids, faithfulness=0.8)
    )
    graph = _load_report(
        _write_generation(
            tmp_path / "graph.json",
            case_ids=case_ids,
            faithfulness=0.8,
            context_count=3,
            invalid={"alpha-full": 2},
            provenance_update={"code_sha": "d" * 40, "contexts_sha256": "e" * 64},
            config_update={"allow_short_contexts": True},
        )
    )
    result = paired_generation(hybrid, graph)
    assert result["excluded_case_ids"] == ["alpha-full"]
    assert result["cases"] == 2
    for metric in result["metrics"].values():
        assert metric["better"] + metric["worse"] + metric["equal"] == 2


def test_locked_generation_fields_and_allowed_diffs(tmp_path: Path) -> None:
    case_ids = [case_id for case_id, _label, _kws in _CASE_SPECS]
    hybrid = _load_report(
        _write_generation(tmp_path / "hybrid.json", case_ids=case_ids, faithfulness=0.8)
    )
    refused = _load_report(
        _write_generation(
            tmp_path / "graph-locked.json",
            case_ids=case_ids,
            faithfulness=0.8,
            provenance_update={"code_sha": "d" * 40, "contexts_sha256": "e" * 64},
            config_update={"allow_short_contexts": True, "num_predict": 128},
        )
    )
    with pytest.raises(ValueError, match="num_predict"):
        paired_generation(hybrid, refused)

    accepted = _load_report(
        _write_generation(
            tmp_path / "graph-ok.json",
            case_ids=case_ids,
            faithfulness=0.8,
            context_count=3,
            provenance_update={"code_sha": "d" * 40, "contexts_sha256": "e" * 64},
            config_update={"allow_short_contexts": True},
        )
    )
    result = paired_generation(hybrid, accepted)
    assert result["cases"] == 3
    assert result["graph_mean_context_count"] == 3.0


def test_decision_outcomes(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    authorized = build_gr3_report(**kwargs)
    assert authorized["decision"]["verdict"] == "AUTO_DEFAULT_AUTHORIZED"
    assert authorized["decision"]["failed_criteria"] == []
    assert authorized["decision"]["criteria"]["precision_rose"]["status"] == "pass"
    assert authorized["decision"]["criteria"]["full_not_fallen"]["status"] == "pass"

    _paths_same, kwargs_same = _bundle(tmp_path / "same-g2", g2_n_cands=5)
    no_ship = build_gr3_report(**kwargs_same)
    assert no_ship["decision"]["verdict"] == "NO_SHIP_TO_DEFAULT"
    assert "precision_rose" in no_ship["decision"]["failed_criteria"]
    assert (
        no_ship["phase_c"]["arms"]["G2"]["all_cases"]["context_precision"]
        == no_ship["phase_c"]["arms"]["H"]["all_cases"]["context_precision"]
    )

    _paths_pending, kwargs_pending = _bundle(tmp_path / "pending", with_generation=False)
    pending = build_gr3_report(**kwargs_pending)
    assert pending["generation"] is None
    assert pending["decision"]["verdict"] == "PENDING_GENERATION"


def test_report_round_trip_and_rendered_table(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    report = build_gr3_report(**kwargs)
    path = write_gr3_report(report, tmp_path / "gr3.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == report
    assert path.read_text(encoding="utf-8").endswith("\n")
    table = render_gr3_table(report)
    for label in ("H", "Hm", "G1", "G2"):
        assert label in table
    assert "AUTO_DEFAULT_AUTHORIZED" in table
    assert sha256_file(kwargs["phase_c_h"]) == report["provenance"]["inputs"]["phase_c_h"]


def test_cli_requires_both_generation_reports_and_prints_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths, kwargs = _bundle(tmp_path)
    required = [
        "--phase-c-h",
        str(kwargs["phase_c_h"]),
        "--phase-c-hm",
        str(kwargs["phase_c_hm"]),
        "--phase-c-g1",
        str(kwargs["phase_c_g1"]),
        "--phase-c-g2",
        str(kwargs["phase_c_g2"]),
        "--phase-c-g1m",
        str(kwargs["phase_c_g1m"]),
        "--phase-c-g2m",
        str(kwargs["phase_c_g2m"]),
        "--bucket-hm",
        str(kwargs["bucket_hm"]),
        "--bucket-g1",
        str(kwargs["bucket_g1"]),
        "--bucket-g2",
        str(kwargs["bucket_g2"]),
        "--bucket-g1m",
        str(kwargs["bucket_g1m"]),
        "--bucket-g2m",
        str(kwargs["bucket_g2m"]),
        "--code-commit",
        _COMMIT,
        "--host",
        _HOST,
        "--evidence-class",
        "synthetic",
        "--out",
        str(tmp_path / "out.json"),
        "--phase-c-dataset",
        str(kwargs["phase_c_dataset"]),
        "--phase-c-sidecar",
        str(kwargs["phase_c_sidecar"]),
        "--phase-c-label-manifest",
        str(kwargs["phase_c_label_manifest"]),
        "--phase-c-corpus-manifest",
        str(kwargs["phase_c_corpus_manifest"]),
        "--bucket-dataset",
        str(kwargs["bucket_dataset"]),
        "--bucket-sidecar",
        str(kwargs["bucket_sidecar"]),
        "--bucket-label-manifest",
        str(kwargs["bucket_label_manifest"]),
        "--bucket-corpus-manifest",
        str(kwargs["bucket_corpus_manifest"]),
        "--expected-cases",
        str(len(_CASE_SPECS)),
        "--bucket-expected-cases",
        str(len(_CASE_SPECS)),
    ]
    with pytest.raises(SystemExit):
        parse_args([*required, "--hybrid-generation", str(paths["hybrid_generation"])])

    markdown = tmp_path / "gr3.md"
    assert (
        main(
            [
                *required,
                "--hybrid-generation",
                str(kwargs["hybrid_generation"]),
                "--graph-generation",
                str(kwargs["graph_generation"]),
                "--markdown",
                str(markdown),
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert "AUTO_DEFAULT_AUTHORIZED" in printed
    assert markdown.read_text(encoding="utf-8") == printed


@pytest.mark.parametrize(
    "mutate",
    (
        pytest.param(lambda timing: timing.__setitem__("entity", None), id="entity-none"),
        pytest.param(lambda timing: timing.pop("entity"), id="entity-absent"),
    ),
)
def test_g2m_invalid_entity_timing_nulls_pools_and_retrieve(tmp_path: Path, mutate: Any) -> None:
    _paths, kwargs = _bundle(tmp_path)
    rows = json.loads(kwargs["phase_c_g2m"].read_text(encoding="utf-8"))
    mutate(rows[0]["timing_ms"])
    kwargs["phase_c_g2m"].write_text(json.dumps(rows), encoding="utf-8", newline="\n")

    report = build_gr3_report(**kwargs)
    g2 = report["latency"]["phase_c"]["G2"]
    assert g2["pools_ms"]["p50"] is None
    assert g2["pools_ms"]["p95"] is None
    assert g2["total_ms"]["p50"] is None
    assert g2["total_ms"]["p95"] is None
    assert report["latency"]["phase_c"]["p95_total_delta_ms"]["G2"] is None
    retrieve = report["decision"]["criteria"]["retrieve_p95_within_200ms"]
    assert retrieve["status"] == "not_measured"
    assert retrieve["host"] == _HOST
    assert "retrieve_p95_within_200ms" in report["decision"]["failed_criteria"]


def test_latency_refuses_g2m_missing_a_case(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    rows = json.loads(kwargs["phase_c_g2m"].read_text(encoding="utf-8"))
    dropped = str(rows.pop(0)["case_id"])
    kwargs["phase_c_g2m"].write_text(json.dumps(rows), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match=r"^G2:") as excinfo:
        build_gr3_report(**kwargs)
    assert dropped in str(excinfo.value)


def test_provenance_publishes_corpus_from_manifest(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    report = build_gr3_report(**kwargs)
    for block_name, manifest_path in (
        ("phase_c", kwargs["phase_c_corpus_manifest"]),
        ("multi_doc_bucket", kwargs["bucket_corpus_manifest"]),
    ):
        block = report["provenance"][block_name]
        corpus = block["corpus"]
        digest = sha256_file(manifest_path)
        assert block["corpus_manifest_sha256"] == digest
        assert corpus["manifest_sha256"] == digest
        assert corpus["name"] == "synthetic"
        assert corpus["root"] == "tests/fixtures/synthetic"
        assert corpus["corpus_sha256"] == "c" * 64
        assert corpus["file_count"] == 1


def test_corpus_manifest_without_corpus_sha256_is_refused(tmp_path: Path) -> None:
    _paths, kwargs = _bundle(tmp_path)
    manifest = kwargs["phase_c_corpus_manifest"]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    del payload["corpus_sha256"]
    manifest.write_text(json.dumps(payload), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match="corpus_sha256") as excinfo:
        build_gr3_report(**kwargs)
    assert str(manifest) in str(excinfo.value)


def test_faithfulness_criterion_uses_unrounded_ci_high_raw() -> None:
    raw = -0.00004
    rounded = round(raw, 4)
    assert rounded == -0.0
    assert rounded >= 0
    decision = decide(
        {
            "phase_c": {
                "arms": {
                    "H": {"all_cases": {"context_precision": 0.50, "FULL": 10}},
                    "G2": {"all_cases": {"context_precision": 0.60, "FULL": 10}},
                }
            },
            "latency": {
                "host": _HOST,
                "phase_c": {
                    "hybrid": {"total_ms": {"p95": 100.0}},
                    "G2": {"total_ms": {"p95": 150.0}},
                },
            },
            "generation": {
                "metrics": {
                    "llm_faithfulness": {
                        "mean_difference": raw,
                        "ci_high": rounded,
                        "ci_high_raw": raw,
                    },
                    "nli_faithfulness": {
                        "mean_difference": 0.1,
                        "ci_high": 0.1,
                        "ci_high_raw": 0.1,
                    },
                }
            },
        }
    )
    llm = decision["criteria"]["llm_faithfulness_not_significantly_fallen"]
    assert llm["status"] == "fail"
    assert llm["ci_high"] == rounded
    assert llm["ci_high_raw"] == raw
    assert decision["criteria"]["nli_faithfulness_not_significantly_fallen"]["status"] == "pass"
    assert decision["verdict"] == "NO_SHIP_TO_DEFAULT"
    assert "llm_faithfulness_not_significantly_fallen" in decision["failed_criteria"]
