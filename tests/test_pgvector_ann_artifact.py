"""Provenance and replay checks for the Phase D.2 pgvector ANN artifact."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.pgvector_ann import plan_uses_hnsw, recall_at_k

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "evaluation" / "d2-pgvector-ann.json"
D1_PATH = ROOT / "evaluation" / "d1-pgvector-prererank.json"

ARTIFACT_SHA256 = "93d5b2da4c82abecf645be00501ee6b5aa054addbe4cfdaa703b1ca8b88fad45"
SCHEMA_VERSION = "d2-pgvector-ann-v1"
CODE_BASE = "5c1075c9306eabc467b4f3349328c38e65652a5e"

CHUNKS = 5589
CASES = 115
TOP_K = 20
REPETITIONS = 3
ARMS = ("exact", "hnsw")

BUCKETS = {
    "curated_cases_aircargo": (0, 100),
    "curated_cases_aircargo_gr_multihop": (100, CASES),
}

EXPECTED_CONFIG = {
    "chunks": CHUNKS,
    "cases": CASES,
    "top_k": TOP_K,
    "hnsw_ef_search": 100,
    "hnsw_iterative_scan": "strict_order",
    "repetitions": REPETITIONS,
    "distance": "cosine",
    "default_plan_forced": False,
    "hnsw_plan_forced": True,
    "graph": "post-limit chunk-membership join",
    "cold_start_ram": "not_measured",
    "reranker": False,
}

EXPECTED_RLS = {
    f"{tenant}:{table}": count
    for tenant, count in (("unset", 0), ("aircargo", CHUNKS), ("zzz_other", 1))
    for table in ("spike_chunks", "kb_graph_nodes")
}
SOURCE_FILES = ("pgvector_ann_run.py", "pgvector_ann.py", "pgvector_spike_db.py")
TOP_LEVEL_KEYS = {
    "schema_version",
    "code_base",
    "database",
    "input_sha256",
    "source_sha256",
    "versions",
    "python",
    "postgres",
    "pgvector",
    "config",
    "rls",
    "planner",
    "buckets",
    "rows",
    "runs",
    "metrics",
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_pgvector_ann_artifact() -> None:
    raw = ARTIFACT_PATH.read_bytes()
    assert sha256_hex(raw) == ARTIFACT_SHA256
    artifact = json.loads(raw)

    assert set(artifact) == TOP_LEVEL_KEYS
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["code_base"] == CODE_BASE
    for key in ("database", "python", "postgres", "pgvector"):
        assert artifact[key]

    inputs = artifact["input_sha256"]
    assert inputs == json.loads(D1_PATH.read_bytes())["input_sha256"]
    graph_bytes = gzip.decompress(
        (ROOT / "evaluation" / "gr1b-4436d61-graph-chunks.json.gz").read_bytes()
    )
    assert sha256_hex(graph_bytes) == inputs["ab_phase2_G2_graph_chunks.json"]
    for filename in (
        "curated_cases_aircargo.jsonl",
        "curated_cases_aircargo_gr_multihop.jsonl",
    ):
        assert sha256_hex((ROOT / "evaluation" / filename).read_bytes()) == inputs[filename]

    sources = artifact["source_sha256"]
    assert set(sources) == set(SOURCE_FILES)
    for name in SOURCE_FILES:
        assert sha256_hex((ROOT / "scripts" / name).read_bytes()) == sources[name]

    assert artifact["config"] == EXPECTED_CONFIG
    assert artifact["rls"] == EXPECTED_RLS

    planner = artifact["planner"]
    assert planner["default_uses_hnsw"] is True
    assert planner["forced_uses_hnsw"] is True
    assert plan_uses_hnsw(planner["default_explain"])
    assert plan_uses_hnsw(planner["forced_explain"])

    assert artifact["buckets"] == {
        name: {"start": start, "end": end} for name, (start, end) in BUCKETS.items()
    }

    rows = artifact["rows"]
    assert len(rows) == CASES
    assert len({row["case_id"] for row in rows}) == CASES
    recalls: list[float] = []
    for index, row in enumerate(rows):
        bucket = next(name for name, (start, end) in BUCKETS.items() if start <= index < end)
        assert row["bucket"] == bucket
        for arm in ARMS:
            indices = row[f"{arm}_indices"]
            assert len(indices) == TOP_K
            assert len(set(indices)) == TOP_K
            assert all(type(value) is int and 0 <= value < CHUNKS for value in indices)
        recall = recall_at_k(row["exact_indices"], row["hnsw_indices"], TOP_K)
        recalls.append(recall)
        assert row["recall_at_20"] == pytest.approx(recall, abs=1e-12)

    runs = artifact["runs"]
    assert len(runs) == REPETITIONS
    for run in runs:
        assert set(run) == set(ARMS)
        for arm in ARMS:
            arm_data = run[arm]
            assert set(arm_data) == {"rankings", "latency_ms"}
            rankings = arm_data["rankings"]
            latencies = arm_data["latency_ms"]
            assert len(rankings) == CASES
            assert len(latencies) == CASES
            assert rankings == [row[f"{arm}_indices"] for row in rows]
            assert all(
                type(value) in (int, float) and math.isfinite(value) and value > 0
                for value in latencies
            )

    metrics = artifact["metrics"]
    assert set(metrics) == {"global", *BUCKETS}
    scopes = {"global": (0, CASES), **BUCKETS}
    for scope, (start, end) in scopes.items():
        block = metrics[scope]
        assert set(block) == {
            "cases",
            "mean_recall_at_20",
            "min_recall_at_20",
            "latency_runs",
        }
        assert block["cases"] == end - start
        assert block["mean_recall_at_20"] == pytest.approx(
            sum(recalls[start:end]) / (end - start), abs=1e-12
        )
        assert block["min_recall_at_20"] == pytest.approx(min(recalls[start:end]), abs=1e-12)
        latency_runs = block["latency_runs"]
        assert len(latency_runs) == REPETITIONS
        for run_index, run_metrics in enumerate(latency_runs):
            assert set(run_metrics) == set(ARMS)
            for arm in ARMS:
                percentiles = run_metrics[arm]
                assert set(percentiles) == {"latency_p50_ms", "latency_p95_ms"}
                latencies = runs[run_index][arm]["latency_ms"][start:end]
                assert percentiles["latency_p50_ms"] == pytest.approx(
                    float(np.percentile(latencies, 50)), abs=1e-12
                )
                assert percentiles["latency_p95_ms"] == pytest.approx(
                    float(np.percentile(latencies, 95)), abs=1e-12
                )
