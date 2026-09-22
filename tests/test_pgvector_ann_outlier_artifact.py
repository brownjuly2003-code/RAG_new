"""Offline replay of the two pinned D.2 pgvector ANN outlier artifacts.

The fresh-rebuild and original-index artifacts are pinned by raw bytes, then
replayed against their shared measurement contract and against the published
D.2 report row for ``aircargo-harassment-investigation-timeline``.  The
original-index artifact reproduces the published 4/20 recall outlier at
``ef_search=100``; the fresh-rebuild artifact reaches full recall there with
a different ranking.  No root cause is asserted.

Offline only: plain file reads plus ``json``/``hashlib``/``math`` and the
pure helpers from ``scripts.pgvector_ann``; no network, database,
subprocess, model, or environment dependency.
"""

import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts.pgvector_ann import plan_uses_hnsw, recall_at_k

REPO_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = REPO_ROOT / "evaluation"
SCRIPTS_DIR = REPO_ROOT / "scripts"
PUBLISHED_PATH = EVALUATION_DIR / "d2-pgvector-ann.json"

CASE_ID = "aircargo-harassment-investigation-timeline"
CASE_INDEX = 83
SCHEMA_VERSION = "d2-pgvector-ann-outlier-v1"
CHUNKS = 5589
CASES = 115
TOP_K = 20
EF_SEARCH_VALUES = [40, 100, 200, 400, 800, 1000]
BASELINE_EF_SEARCH = 100

RUNNER = "pgvector_ann_outlier_run.py"
SHARED_SOURCES = (
    "pgvector_ann_outlier.py",
    "pgvector_ann_run.py",
    "pgvector_ann.py",
    "pgvector_spike_db.py",
)
SOURCE_FILES = (RUNNER,) + SHARED_SOURCES

TOP_LEVEL_KEYS = {
    "schema_version",
    "code_base",
    "database",
    "case_id",
    "case_index",
    "query",
    "input_sha256",
    "source_sha256",
    "versions",
    "python",
    "postgres",
    "pgvector",
    "index_definition",
    "config",
    "rls",
    "planner",
    "exact",
    "ef_rows",
    "runs",
    "summary",
}

SHARED_CONFIG = {
    "chunks": CHUNKS,
    "cases": CASES,
    "top_k": TOP_K,
    "ef_search_values": EF_SEARCH_VALUES,
    "baseline_ef_search": BASELINE_EF_SEARCH,
    "repetitions": 3,
    "distance": "cosine",
    "hnsw_iterative_scan": "strict_order",
    "hnsw_plan_forced": True,
    "graph": "post-limit synthetic chunk-membership join",
    "embedding_action": "reused_without_reembedding",
    "reranker": False,
}

RLS_TABLES = ("spike_chunks", "kb_graph_nodes")
RLS_COUNTS = {"unset": 0, "aircargo": CHUNKS, "zzz_other": 1}

EF_ROW_KEYS = {
    "ef_search",
    "ranking",
    "recall_at_20",
    "recovered_exact_ids",
    "missed_exact_ids",
}

ANN_LABELS = [f"ann-{ef}" for ef in EF_SEARCH_VALUES]
EXPECTED_ORDERS = [
    ["exact"] + ANN_LABELS,  # ascending
    ANN_LABELS[::-1] + ["exact"],  # full reverse
    ["exact"] + ANN_LABELS,  # ascending again
]

ARTIFACT_SPECS = {
    "fresh": {
        "path": EVALUATION_DIR / "d2-pgvector-ann-outlier.json",
        "bytes": 68679,
        "sha256": "59258f8175d266fc8315270037e379c2d76f3ad534893c01079d8f9f0efe0b15",
        "code_base": "1aa662eda3ce6368109d08d1baa0450b36982ef0",
        "database": "rag_spike_d2_outlier_20260921_1aa662e",
        "database_mode": None,  # fresh rebuild predates database_mode
        "recall_grid": {40: 1.0, 100: 1.0, 200: 1.0, 400: 1.0, 800: 1.0, 1000: 1.0},
        "summary": {
            "first_full_recall_ef_search": 40,
            "monotonic_nondecreasing_recall": True,
            "diagnosis": "already_full_at_baseline",
        },
    },
    "original": {
        "path": EVALUATION_DIR / "d2-pgvector-ann-outlier-original-index.json",
        "bytes": 68807,
        "sha256": "ea8cd0f382c155c44b4cec8934a93a2f0b95d0f85b629684931f3c86c6aeb887",
        "code_base": "527af25b54eaaa59be18cc62ae4e9c7d80dedd1f",
        "database": "rag_spike_d2_ann_20260921",
        "database_mode": "existing_index",
        "recall_grid": {40: 1.0, 100: 0.2, 200: 1.0, 400: 1.0, 800: 1.0, 1000: 1.0},
        "summary": {
            "first_full_recall_ef_search": 40,
            "monotonic_nondecreasing_recall": False,
            "diagnosis": "recovered_by_higher_ef_search",
        },
    },
}


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_focused(name):
    """Parse one focused artifact after pinning its raw bytes."""
    spec = ARTIFACT_SPECS[name]
    raw = spec["path"].read_bytes()
    assert raw.endswith(b"\n"), f"{name}: raw bytes must end in LF"
    assert b"\r" not in raw, f"{name}: raw bytes must not contain CR"
    assert len(raw) == spec["bytes"], f"{name}: unexpected byte length"
    assert hashlib.sha256(raw).hexdigest() == spec["sha256"], f"{name}: sha256 mismatch"
    return spec, json.loads(raw)


def check_ranking(ranking):
    """Validate one raw ``[chunk_id, distance]`` ranking; return ordered IDs."""
    assert type(ranking) is list
    assert len(ranking) == TOP_K
    for pair in ranking:
        assert type(pair) is list and len(pair) == 2
    ids = [pair[0] for pair in ranking]
    assert len(set(ids)) == TOP_K
    assert all(type(i) is int and 0 <= i < CHUNKS for i in ids)
    assert all(type(d) in (int, float) and math.isfinite(d) for _, d in ranking)
    return ids


def ef_rows_by_search(art):
    """Map ef_search to its ef_rows row, pinning the six-row order."""
    rows = art["ef_rows"]
    assert type(rows) is list
    assert [row["ef_search"] for row in rows] == EF_SEARCH_VALUES
    return {row["ef_search"]: row for row in rows}


def recovered_missed(exact_ids, ids):
    """Recompute recovered/missed exact IDs, preserving exact ranking order."""
    hits = set(ids)
    recovered = [i for i in exact_ids if i in hits]
    missed = [i for i in exact_ids if i not in hits]
    return recovered, missed


@pytest.fixture(scope="module", params=tuple(ARTIFACT_SPECS))
def focused(request):
    return load_focused(request.param)


@pytest.fixture(scope="module")
def fresh():
    return load_focused("fresh")[1]


@pytest.fixture(scope="module")
def original():
    return load_focused("original")[1]


@pytest.fixture(scope="module")
def published():
    return json.loads(PUBLISHED_PATH.read_bytes())


@pytest.fixture(scope="module")
def published_row(published):
    matches = [row for row in published["rows"] if row["case_id"] == CASE_ID]
    assert len(matches) == 1, "expected one published D.2 row for the outlier case"
    return matches[0]


def test_focused_schema_and_provenance(focused):
    spec, art = focused
    assert art["schema_version"] == SCHEMA_VERSION
    assert art["code_base"] == spec["code_base"]
    assert art["database"] == spec["database"]
    assert art["case_id"] == CASE_ID
    assert art["case_index"] == CASE_INDEX
    assert set(art) == TOP_LEVEL_KEYS


def test_focused_config(focused):
    spec, art = focused
    if spec["database_mode"] is None:
        # The fresh rebuild ran before database_mode existed.
        assert "database_mode" not in art["config"]
        assert art["config"] == SHARED_CONFIG
    else:
        expected = {**SHARED_CONFIG, "database_mode": spec["database_mode"]}
        assert art["config"] == expected


def test_focused_rls(focused):
    _, art = focused
    # rls is a flat "role:table" -> visible-row-count mapping.
    assert art["rls"] == {
        f"{role}:{table}": count for role, count in RLS_COUNTS.items() for table in RLS_TABLES
    }


def test_focused_planner_and_index(focused):
    _, art = focused
    planner = art["planner"]
    assert planner["baseline_ef_search"] == BASELINE_EF_SEARCH
    assert planner["baseline_uses_hnsw"] is True
    assert plan_uses_hnsw(planner["baseline_explain"])
    index_definition = art["index_definition"]
    assert index_definition.strip()
    assert "USING hnsw" in index_definition
    assert "embedding" in index_definition


def test_focused_exact_and_ef_rows(focused):
    spec, art = focused
    # Exact carries no recall metadata; its IDs are the reference set.
    exact_ids = check_ranking(art["exact"])

    ef_map = ef_rows_by_search(art)
    recalls = []
    for ef in EF_SEARCH_VALUES:
        row = ef_map[ef]
        assert set(row) == EF_ROW_KEYS
        ids = check_ranking(row["ranking"])
        recall = recall_at_k(exact_ids, ids, TOP_K)
        assert row["recall_at_20"] == recall == spec["recall_grid"][ef]
        recovered, missed = recovered_missed(exact_ids, ids)
        assert row["recovered_exact_ids"] == recovered
        assert row["missed_exact_ids"] == missed
        recalls.append(recall)

    # The pinned summary must follow from the replayed recall grid.
    summary = art["summary"]
    assert summary == spec["summary"]
    assert summary["first_full_recall_ef_search"] == EF_SEARCH_VALUES[recalls.index(1.0)]
    nondecreasing = all(a <= b for a, b in zip(recalls, recalls[1:], strict=False))
    assert summary["monotonic_nondecreasing_recall"] == nondecreasing


def test_focused_runs(focused):
    _, art = focused
    runs = art["runs"]
    assert len(runs) == 3
    ef_map = ef_rows_by_search(art)
    canonical = {"exact": art["exact"]}
    canonical.update({f"ann-{ef}": ef_map[ef]["ranking"] for ef in EF_SEARCH_VALUES})
    for repetition, (run, order) in enumerate(zip(runs, EXPECTED_ORDERS, strict=True), start=1):
        assert set(run) == {"repetition", "order", "timings_ms", "rankings"}
        assert run["repetition"] == repetition
        assert run["order"] == order
        assert set(run["rankings"]) == set(order)
        assert set(run["timings_ms"]) == set(order)
        for label in order:
            assert run["rankings"][label] == canonical[label]
            timing = run["timings_ms"][label]
            assert type(timing) in (int, float)
            assert math.isfinite(timing) and timing > 0


def test_source_sha256_pins(fresh, original):
    assert set(original["source_sha256"]) == set(SOURCE_FILES)
    assert set(fresh["source_sha256"]) == set(SOURCE_FILES)
    # The original-index run matches the current scripts tree file-for-file.
    for name in SOURCE_FILES:
        assert original["source_sha256"][name] == sha256_file(SCRIPTS_DIR / name)
    # The fresh rebuild shares every digest except the outlier runner,
    # which gained reuse mode between the two runs.
    for name in SHARED_SOURCES:
        assert fresh["source_sha256"][name] == original["source_sha256"][name]
    assert fresh["source_sha256"][RUNNER] != original["source_sha256"][RUNNER]


def test_against_published_d2_report(fresh, original, published, published_row):
    # Both focused artifacts replay the published D.2 input corpus and case.
    assert fresh["input_sha256"] == original["input_sha256"] == published["input_sha256"]

    exact_ids = check_ranking(fresh["exact"])
    assert exact_ids == check_ranking(original["exact"]) == published_row["exact_indices"]

    # Original index: ef_search=100 reproduces the published 4/20 outlier.
    original_rows = ef_rows_by_search(original)
    original_ef100 = check_ranking(original_rows[BASELINE_EF_SEARCH]["ranking"])
    assert original_ef100 == published_row["hnsw_indices"]
    assert published_row["recall_at_20"] == 0.2
    assert recall_at_k(exact_ids, original_ef100, TOP_K) == 0.2

    # Fresh rebuild: same ef_search, full recall, different ranking, so the
    # published outlier is reproduced only on the original index.
    fresh_rows = ef_rows_by_search(fresh)
    fresh_ef100 = check_ranking(fresh_rows[BASELINE_EF_SEARCH]["ranking"])
    assert fresh_ef100 != published_row["hnsw_indices"]
    assert recall_at_k(exact_ids, fresh_ef100, TOP_K) == 1.0
