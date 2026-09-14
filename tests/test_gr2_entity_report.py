"""Synthetic, no-model contract tests for the GR-2 G2-versus-G1 report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.ab_context_precision import (
    PROJECT_ROOT,
    _g2_latency,
    build_arm_comparison,
    build_bucket_report,
    build_gr2_report,
    main,
    parse_args,
    write_gr2_report,
)
from scripts.ab_remote_contextual import _candidates_artifact, _pool_artifact_paths

_COMMIT = "1" * 40
_CASE_COUNT = 3


def _write_inputs(root: Path, *, prefix: str = "phase") -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    dataset = root / f"{prefix}-cases.jsonl"
    sidecar = root / f"{prefix}-classes.jsonl"
    label_manifest = root / f"{prefix}-classes.manifest.json"
    corpus_manifest = root / f"{prefix}-corpus.manifest.json"
    g1_pool = root / f"{prefix}-g1.json"
    g2_pool = root / f"{prefix}-g2.json"
    g2_meta = root / f"{prefix}-g2-meta.json"
    cases = [
        ("single-regression", "single_hop", "multi_hop", ["alpha", "beta"]),
        ("single-parity", "single_hop", "single_hop", ["delta"]),
        ("multi-gain", "multi_hop", "multi_hop", ["gamma"]),
    ]
    dataset.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": case_id,
                    "tenant_id": "aircargo",
                    "query": f"query {case_id}",
                    "expected": {"answer_contains": keywords},
                }
            )
            + "\n"
            for case_id, _label, _routed, keywords in cases
        ),
        encoding="utf-8",
        newline="\n",
    )
    sidecar.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": case_id,
                    "question_class": label,
                    "reason": "synthetic",
                    "labelled_by": "test",
                    "labelled_at": "2026-09-13",
                    "batch": 1,
                    "approved_by": None,
                }
            )
            + "\n"
            for case_id, label, _routed, _keywords in cases
        ),
        encoding="utf-8",
        newline="\n",
    )
    label_manifest.write_text(
        json.dumps(
            {
                "schema_version": "aircargo-question-class-manifest/v1.0",
                "dataset": dataset.name,
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "case_count": len(cases),
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    corpus_manifest.write_text(
        json.dumps(
            {
                "name": "synthetic",
                "root": "tests/fixtures/synthetic",
                "corpus_sha256": "c" * 64,
                "file_count": 1,
            }
        ),
        encoding="utf-8",
        newline="\n",
    )

    g1_rows: list[dict[str, Any]] = []
    g2_rows: list[dict[str, Any]] = []
    for case_id, _label, routed, keywords in cases:
        g1_contexts = [" ".join(keywords), "noise"]
        g2_contexts = [keywords[0], "noise"] if case_id == "single-regression" else g1_contexts
        common = {
            "case_id": case_id,
            "query": f"query {case_id}",
            "kws": keywords,
            "rerank_k": 2,
            "graph_postprocessed": True,
            "graph_prefiltered": case_id == "multi-gain",
        }
        g1_rows.append(common | {"cands": g1_contexts, "rerank_s": 0.08})
        g2_rows.append(
            common
            | {
                "cands": g2_contexts,
                "rerank_s": 0.10,
                "routed_question_class": routed,
                "query_entities": ["awb"],
                "matched_entities": ["awb"],
                "entity_hops": 2 if routed == "multi_hop" else 0,
                "entity_candidates": 3 if routed == "multi_hop" else 0,
                "timing_ms": {
                    "vector": 4.0,
                    "bm25": 2.0,
                    "entity": 6.0 if routed in {"multi_hop", "aggregation", "global"} else 0.0,
                },
            }
        )
    g1_pool.write_text(json.dumps(g1_rows), encoding="utf-8", newline="\n")
    g2_pool.write_text(json.dumps(g2_rows), encoding="utf-8", newline="\n")
    g2_meta.write_text(
        json.dumps(
            {
                "cases_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "graph_chunks_sha256": "g" * 64,
                "entities_manifest_sha256": "e" * 64,
                "classifications_manifest_sha256": "l" * 64,
                "structure_graph_digest": "s" * 64,
                "node_counts": {"chunk": 2, "entity": 1},
                "edge_counts": {"mentions": 2},
                "projection_build_s": 0.25,
                "peak_rss_bytes": 10485760,
                "routed_class_counts": {"multi_hop": 2, "single_hop": 1},
                "rejected_chunk_ids": [],
                "rejected_count": 0,
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "dataset": dataset,
        "sidecar": sidecar,
        "label_manifest": label_manifest,
        "corpus_manifest": corpus_manifest,
        "g1_pool": g1_pool,
        "g2_pool": g2_pool,
        "g2_meta": g2_meta,
    }


def _bucket(paths: dict[str, Path], arm: str) -> dict[str, Any]:
    return build_bucket_report(
        pool_path=paths[f"{arm.lower()}_pool"],
        dataset_path=paths["dataset"],
        sidecar_path=paths["sidecar"],
        label_manifest_path=paths["label_manifest"],
        corpus_manifest_path=paths["corpus_manifest"],
        expected_cases=_CASE_COUNT,
        top_k=2,
        code_commit=_COMMIT,
        pool_arm=arm,
        pool_meta_path=paths["g2_meta"] if arm == "G2" else None,
    )


def _rerank_by_case(path: Path) -> dict[str, float]:
    return {row["case_id"]: row["rerank_s"] for row in json.loads(path.read_text(encoding="utf-8"))}


def _comparison(paths: dict[str, Path]) -> dict[str, Any]:
    return build_arm_comparison(
        _bucket(paths, "G1"),
        _bucket(paths, "G2"),
        g1_rerank_s=_rerank_by_case(paths["g1_pool"]),
        g2_rerank_s=_rerank_by_case(paths["g2_pool"]),
    )


def test_valid_g2_report_keeps_routed_class_beside_labelled_class(tmp_path: Path) -> None:
    report = _bucket(_write_inputs(tmp_path), "G2")

    row = next(item for item in report["per_case"] if item["case_id"] == "single-regression")
    assert row["question_class"] == "single_hop"
    assert row["routed_question_class"] == "multi_hop"
    assert report["pool_diagnostics"]["routed_class_counts"] == {
        "multi_hop": 2,
        "single_hop": 1,
    }
    assert report["latency"]["entity_lane_ms"] == {
        "cases": 2,
        "p50": 6.0,
        "p95": 6.0,
        "max": 6.0,
    }


def test_fixture_entity_timing_matches_harness_lane_routing(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    rows = json.loads(paths["g2_pool"].read_text(encoding="utf-8"))
    entity_lane_classes = {"multi_hop", "aggregation", "global"}

    for row in rows:
        expected = 6.0 if row["routed_question_class"] in entity_lane_classes else 0.0
        assert row["timing_ms"]["entity"] == expected


def test_g2_latency_uses_only_entity_lane_rows() -> None:
    lane_rows = [
        {
            "routed_question_class": "multi_hop",
            "timing_ms": {"vector": 1.0, "bm25": 2.0, "entity": entity_ms},
            "rerank_s": 0.1,
        }
        for entity_ms in (40.0, 41.0, 42.0, 43.0)
    ]
    non_lane_rows = [
        {
            "routed_question_class": "single_hop",
            "timing_ms": {"vector": 1.0, "bm25": 2.0, "entity": 0.0},
            "rerank_s": 0.1,
        }
        for _ in range(96)
    ]

    latency = _g2_latency([*lane_rows, *non_lane_rows])

    assert latency["entity_lane_ms"] == {
        "cases": 4,
        "p50": 41.0,
        "p95": 43.0,
        "max": 43.0,
    }
    assert latency["retrieve_ms"]["cases"] == 100
    assert latency["rerank_s"]["cases"] == 100


def test_g2_latency_rounds_retrieve_sum_before_percentile_selection() -> None:
    latency = _g2_latency(
        [
            {
                "routed_question_class": "single_hop",
                "timing_ms": {"vector": 0.1, "bm25": 0.2, "entity": 0.0},
                "rerank_s": 0.1,
            }
        ]
    )

    assert latency["retrieve_ms"]["p50"] == 0.3


def test_g2_latency_without_entity_lane_uses_null_percentiles() -> None:
    latency = _g2_latency(
        [
            {
                "routed_question_class": "single_hop",
                "timing_ms": {"vector": 1.0, "bm25": 2.0, "entity": 0.0},
                "rerank_s": 0.1,
            }
        ]
    )

    assert latency["entity_lane_ms"] == {
        "cases": 0,
        "p50": None,
        "p95": None,
        "max": None,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [("routed_question_class", None), ("entity_candidates", 51), ("entity_hops", 3)],
)
def test_g2_rejects_missing_route_and_entity_lane_limit_breaks(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    paths = _write_inputs(tmp_path)
    rows = json.loads(paths["g2_pool"].read_text(encoding="utf-8"))
    if value is None:
        rows[0].pop(field)
    else:
        rows[0][field] = value
    paths["g2_pool"].write_text(json.dumps(rows), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match="single-regression"):
        _bucket(paths, "G2")


@pytest.mark.parametrize("meta_field", ["cases_sha256", "routed_class_counts"])
def test_g2_rejects_meta_dataset_or_routed_count_mismatch(
    tmp_path: Path,
    meta_field: str,
) -> None:
    paths = _write_inputs(tmp_path)
    meta = json.loads(paths["g2_meta"].read_text(encoding="utf-8"))
    meta[meta_field] = "other-dataset" if meta_field == "cases_sha256" else {"global": 2}
    paths["g2_meta"].write_text(json.dumps(meta), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError) as excinfo:
        _bucket(paths, "G2")
    assert "other-dataset" in str(excinfo.value) or "global" in str(excinfo.value)
    assert "single_hop" in str(excinfo.value) or hashlib.sha256(
        paths["dataset"].read_bytes()
    ).hexdigest() in str(excinfo.value)


def test_comparison_lists_single_hop_downgrade_next_to_multi_hop_delta(tmp_path: Path) -> None:
    comparison = _comparison(_write_inputs(tmp_path))

    assert comparison["precision_deltas"] == {"single_hop": -0.0667, "multi_hop": 0.0}
    assert comparison["cost"]["G2_entity_search_ms"] == {
        "cases": 2,
        "p50": 6.0,
        "p95": 6.0,
    }
    assert comparison["downgrades"] == [
        {
            "case_id": "single-regression",
            "question_class": "single_hop",
            "routed_question_class": "multi_hop",
            "transition": "FULL->PART",
        }
    ]


def test_comparison_rounds_paired_rerank_deltas(tmp_path: Path) -> None:
    comparison = _comparison(_write_inputs(tmp_path))

    assert comparison["cost"]["paired_rerank_s_delta"] == {"p50": 0.02, "p95": 0.02}


def test_comparison_refuses_case_set_and_dataset_digest_mismatches(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    g1 = _bucket(paths, "G1")
    g2 = _bucket(paths, "G2")
    rerank = _rerank_by_case(paths["g1_pool"])
    with pytest.raises(ValueError, match="case ids"):
        build_arm_comparison(
            {**g1, "per_case": g1["per_case"][:1]},
            g2,
            g1_rerank_s=rerank,
            g2_rerank_s=_rerank_by_case(paths["g2_pool"]),
        )
    with pytest.raises(ValueError, match="dataset digest"):
        build_arm_comparison(
            {**g1, "provenance": {**g1["provenance"], "dataset_sha256": "x" * 64}},
            g2,
            g1_rerank_s=rerank,
            g2_rerank_s=_rerank_by_case(paths["g2_pool"]),
        )


@pytest.mark.parametrize("arm", ["G1", "G2"])
def test_gr2_bundle_requires_rerank_seconds_for_each_arm(tmp_path: Path, arm: str) -> None:
    phase = _write_inputs(tmp_path / "phase", prefix="phase")
    bucket = _write_inputs(tmp_path / "bucket", prefix="bucket")
    target = phase[f"{arm.lower()}_pool"]
    rows = json.loads(target.read_text(encoding="utf-8"))
    rows[0].pop("rerank_s")
    target.write_text(json.dumps(rows), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match=rf"single-regression arm {arm}"):
        build_gr2_report(
            g1_pool_path=phase["g1_pool"],
            g2_pool_path=phase["g2_pool"],
            g2_pool_meta_path=phase["g2_meta"],
            bucket_g1_pool_path=bucket["g1_pool"],
            bucket_g2_pool_path=bucket["g2_pool"],
            bucket_g2_pool_meta_path=bucket["g2_meta"],
            dataset_path=phase["dataset"],
            sidecar_path=phase["sidecar"],
            label_manifest_path=phase["label_manifest"],
            corpus_manifest_path=phase["corpus_manifest"],
            bucket_dataset_path=bucket["dataset"],
            bucket_sidecar_path=bucket["sidecar"],
            bucket_label_manifest_path=bucket["label_manifest"],
            bucket_corpus_manifest_path=bucket["corpus_manifest"],
            expected_cases=_CASE_COUNT,
            bucket_expected_cases=_CASE_COUNT,
            top_k=2,
            code_commit=_COMMIT,
        )


def test_gr2_bundle_reproduces_and_cli_prints_both_tables(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    phase = _write_inputs(tmp_path / "phase", prefix="phase")
    bucket = _write_inputs(tmp_path / "bucket", prefix="bucket")
    kwargs = {
        "g1_pool_path": phase["g1_pool"],
        "g2_pool_path": phase["g2_pool"],
        "g2_pool_meta_path": phase["g2_meta"],
        "bucket_g1_pool_path": bucket["g1_pool"],
        "bucket_g2_pool_path": bucket["g2_pool"],
        "bucket_g2_pool_meta_path": bucket["g2_meta"],
        "dataset_path": phase["dataset"],
        "sidecar_path": phase["sidecar"],
        "label_manifest_path": phase["label_manifest"],
        "corpus_manifest_path": phase["corpus_manifest"],
        "bucket_dataset_path": bucket["dataset"],
        "bucket_sidecar_path": bucket["sidecar"],
        "bucket_label_manifest_path": bucket["label_manifest"],
        "bucket_corpus_manifest_path": bucket["corpus_manifest"],
        "expected_cases": _CASE_COUNT,
        "bucket_expected_cases": _CASE_COUNT,
        "top_k": 2,
        "code_commit": _COMMIT,
    }
    first = write_gr2_report(build_gr2_report(**kwargs), tmp_path / "first.json")
    second = write_gr2_report(build_gr2_report(**kwargs), tmp_path / "second.json")
    assert first.read_bytes() == second.read_bytes()

    output = tmp_path / "cli.json"
    assert (
        main(
            [
                "--gr2-report",
                "--g1-pool",
                str(phase["g1_pool"]),
                "--g2-pool",
                str(phase["g2_pool"]),
                "--g2-pool-meta",
                str(phase["g2_meta"]),
                "--bucket-g1-pool",
                str(bucket["g1_pool"]),
                "--bucket-g2-pool",
                str(bucket["g2_pool"]),
                "--bucket-g2-pool-meta",
                str(bucket["g2_meta"]),
                "--dataset",
                str(phase["dataset"]),
                "--sidecar",
                str(phase["sidecar"]),
                "--label-manifest",
                str(phase["label_manifest"]),
                "--corpus-manifest",
                str(phase["corpus_manifest"]),
                "--bucket-dataset",
                str(bucket["dataset"]),
                "--bucket-sidecar",
                str(bucket["sidecar"]),
                "--bucket-label-manifest",
                str(bucket["label_manifest"]),
                "--bucket-corpus-manifest",
                str(bucket["corpus_manifest"]),
                "--expected-cases",
                str(_CASE_COUNT),
                "--bucket-expected-cases",
                str(_CASE_COUNT),
                "--top-k",
                "2",
                "--gr2-out",
                str(output),
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert output.is_file()
    assert "phase_c" in printed
    assert "multi_doc_bucket" in printed
    assert "graph_prefiltered=true" in printed
    assert "peak_rss_bytes" in printed
    assert "Keyword transitions: FULL->FULL: 2, FULL->PART: 1" in printed
    assert "Keyword loss case ids: single-regression" in printed
    assert "paired rerank_s delta p50=0.02 s" in printed


def test_gr2_bundle_reports_non_lane_parity_without_refusing_divergence(tmp_path: Path) -> None:
    phase = _write_inputs(tmp_path / "phase", prefix="phase")
    bucket = _write_inputs(tmp_path / "bucket", prefix="bucket")
    kwargs = {
        "g1_pool_path": phase["g1_pool"],
        "g2_pool_path": phase["g2_pool"],
        "g2_pool_meta_path": phase["g2_meta"],
        "bucket_g1_pool_path": bucket["g1_pool"],
        "bucket_g2_pool_path": bucket["g2_pool"],
        "bucket_g2_pool_meta_path": bucket["g2_meta"],
        "dataset_path": phase["dataset"],
        "sidecar_path": phase["sidecar"],
        "label_manifest_path": phase["label_manifest"],
        "corpus_manifest_path": phase["corpus_manifest"],
        "bucket_dataset_path": bucket["dataset"],
        "bucket_sidecar_path": bucket["sidecar"],
        "bucket_label_manifest_path": bucket["label_manifest"],
        "bucket_corpus_manifest_path": bucket["corpus_manifest"],
        "expected_cases": _CASE_COUNT,
        "bucket_expected_cases": _CASE_COUNT,
        "top_k": 2,
        "code_commit": _COMMIT,
    }
    assert build_gr2_report(**kwargs)["phase_c"]["comparison"]["non_lane_parity"] == {
        "cases": 1,
        "divergent_case_ids": [],
    }

    rows = json.loads(phase["g2_pool"].read_text(encoding="utf-8"))
    next(row for row in rows if row["case_id"] == "single-parity")["cands"] = ["divergent"]
    phase["g2_pool"].write_text(json.dumps(rows), encoding="utf-8", newline="\n")

    assert build_gr2_report(**kwargs)["phase_c"]["comparison"]["non_lane_parity"] == {
        "cases": 1,
        "divergent_case_ids": ["single-parity"],
    }


def test_gr2_cli_defaults_match_harness_artifact_helpers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = parse_args(["--gr2-report"])
    phase_out_dir = PROJECT_ROOT / ".tmp"
    bucket_out_dir = phase_out_dir / "gr2_bucket"

    assert Path(args.g1_pool) == _candidates_artifact("G1", phase_out_dir)
    assert Path(args.g2_pool) == _candidates_artifact("G2", phase_out_dir)
    assert Path(args.g2_pool_meta) in _pool_artifact_paths("G2", phase_out_dir)
    assert Path(args.bucket_g1_pool) == _candidates_artifact("G1", bucket_out_dir)
    assert Path(args.bucket_g2_pool) == _candidates_artifact("G2", bucket_out_dir)
    assert Path(args.bucket_g2_pool_meta) in _pool_artifact_paths("G2", bucket_out_dir)

    with pytest.raises(SystemExit, match="0"):
        parse_args(["--help"])
    assert "bucket run uses --out-dir .tmp/gr2_bucket" in capsys.readouterr().out
