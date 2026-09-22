"""Provenance and replay checks for the Phase D.3 rerank artifact."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts.pgvector_spike import score_rows

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "evaluation" / "d3-pgvector-rerank.json"
ARTIFACT_SHA256 = "4e8450b2d3a59543e6799f9395cb999fb64ca60ee64a197e4609f4592ddc4345"
D1_PATH = ROOT / "evaluation" / "d1-pgvector-prererank.json"
CHUNKS_PATH = ROOT / "evaluation" / "gr1b-4436d61-graph-chunks.json.gz"

CODE_BASE = "1e64ee3"
CHUNKS = 5589
CASES = 115
TOP_K = 5
MODEL = "BAAI/bge-reranker-v2-m3"
ARMS = ("postgres", "chroma_bm25")
TOP5_SET_CHANGED = {"postgres": 112, "chroma_bm25": 114}
CASE_FILES = (
    "curated_cases_aircargo.jsonl",
    "curated_cases_aircargo_gr_multihop.jsonl",
)
BUCKETS = {
    "curated_cases_aircargo": (0, 100),
    "curated_cases_aircargo_gr_multihop": (100, CASES),
}
SOURCE_FILES = (
    "scripts/pgvector_rerank.py",
    "scripts/pgvector_rerank_run.py",
    "scripts/pgvector_spike.py",
    "evaluation/ragas_eval.py",
    "vectordb/_base_manager.py",
)
TOP_LEVEL_KEYS = {
    "code_base",
    "input_sha256",
    "source_sha256",
    "versions",
    "python",
    "config",
    "buckets",
    "arms",
}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_inputs() -> tuple[list[dict], list[str], bytes]:
    cases: list[dict] = []
    for filename in CASE_FILES:
        for line in (ROOT / "evaluation" / filename).read_text(
            encoding="utf-8"
        ).splitlines():
            row = json.loads(line)
            cases.append(
                {
                    "case_id": row["case_id"],
                    "query": row["query"],
                    "kws": row["expected"]["answer_contains"],
                }
            )
    chunk_bytes = gzip.decompress(CHUNKS_PATH.read_bytes())
    chunks = json.loads(chunk_bytes)["chunks"]
    texts = [chunk["page_content"] for chunk in chunks]
    return cases, texts, chunk_bytes


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def test_pgvector_rerank_artifact() -> None:
    artifact_raw = ARTIFACT_PATH.read_bytes()
    assert _sha256(artifact_raw) == ARTIFACT_SHA256
    artifact = json.loads(artifact_raw)
    d1_raw = D1_PATH.read_bytes()
    d1 = json.loads(d1_raw)
    cases, texts, chunk_bytes = _load_inputs()

    assert set(artifact) == TOP_LEVEL_KEYS
    assert artifact["code_base"] == CODE_BASE
    assert artifact["python"] == "3.11.15"
    assert artifact["versions"] == {
        "sentence-transformers": "2.7.0",
        "torch": "2.2.2",
    }
    assert len(cases) == CASES
    assert len(texts) == CHUNKS

    inputs = artifact["input_sha256"]
    assert inputs == {
        "ab_phase2_G2_graph_chunks.json": _sha256(chunk_bytes),
        D1_PATH.name: _sha256(d1_raw),
        **{
            filename: _sha256((ROOT / "evaluation" / filename).read_bytes())
            for filename in CASE_FILES
        },
    }
    for filename in ("ab_phase2_G2_graph_chunks.json", *CASE_FILES):
        assert inputs[filename] == d1["input_sha256"][filename]

    sources = artifact["source_sha256"]
    assert set(sources) == set(SOURCE_FILES)
    for relative in SOURCE_FILES:
        assert sources[relative] == _sha256((ROOT / relative).read_bytes())

    assert artifact["config"] == {
        "chunks": CHUNKS,
        "cases": CASES,
        "top_k": TOP_K,
        "reranker_model": MODEL,
        "reranker_device": "cpu",
        "reranker": True,
        "source_report": D1_PATH.name,
        "source_report_sha256": _sha256(d1_raw),
    }
    assert artifact["buckets"] == {
        name: {"start": start, "end": end}
        for name, (start, end) in BUCKETS.items()
    }

    arms = artifact["arms"]
    assert set(arms) == set(ARMS)
    scopes = {"global": (0, CASES), **BUCKETS}
    for arm_name in ARMS:
        arm = arms[arm_name]
        assert set(arm) == {"rankings", "latency_ms", "metrics"}
        rankings = arm["rankings"]
        latencies = arm["latency_ms"]
        saved_rankings = d1["runs"][0][arm_name]["rankings"]
        assert len(rankings) == CASES
        assert len(latencies) == CASES
        assert sum(
            reranked != saved
            for reranked, saved in zip(rankings, saved_rankings, strict=True)
        ) == CASES
        assert sum(
            set(reranked[:TOP_K]) != set(saved[:TOP_K])
            for reranked, saved in zip(rankings, saved_rankings, strict=True)
        ) == TOP5_SET_CHANGED[arm_name]
        for reranked, saved in zip(
            rankings,
            saved_rankings,
            strict=True,
        ):
            assert sorted(reranked) == sorted(saved)
            assert len(reranked) == len(set(reranked))
            assert all(type(value) is int and 0 <= value < CHUNKS for value in reranked)
        assert all(
            type(value) in (int, float) and math.isfinite(value) and value > 0
            for value in latencies
        )

        metrics = arm["metrics"]
        assert set(metrics) == set(scopes)
        for scope, (start, end) in scopes.items():
            measured = metrics[scope]
            expected = score_rows(
                cases[start:end],
                rankings[start:end],
                texts,
                top_k=TOP_K,
            )
            assert set(measured) == {
                "rows",
                "mean_context_precision",
                "mean_context_recall",
                "cases",
                "latency_p50_ms",
                "latency_p95_ms",
            }
            assert measured["rows"] == expected["rows"]
            assert measured["mean_context_precision"] == pytest.approx(
                expected["mean_context_precision"], abs=1e-12
            )
            assert measured["mean_context_recall"] == pytest.approx(
                expected["mean_context_recall"], abs=1e-12
            )
            assert measured["cases"] == end - start
            scope_latencies = latencies[start:end]
            assert measured["latency_p50_ms"] == pytest.approx(
                _percentile(scope_latencies, 0.50), abs=1e-12
            )
            assert measured["latency_p95_ms"] == pytest.approx(
                _percentile(scope_latencies, 0.95), abs=1e-12
            )
