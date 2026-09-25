"""Tests for the Mac-only Phase D.5 measurement, not production code."""

import hashlib
import json
import math

import pytest

from scripts.pgvector_cold_start import (
    build_report,
    compare_d1,
    parse_rss,
    rankings_sha256,
    summarize,
    text_digest,
    trial_order,
    validate_trial_record,
)


def test_text_digest_matches_length_prefixed_utf8():
    expected = hashlib.sha256()
    for value in ("a", "ёж"):
        encoded = value.encode("utf-8")
        expected.update(len(encoded).to_bytes(8, "big"))
        expected.update(encoded)
    assert text_digest(["a", "ёж"]) == expected.hexdigest()


def test_order():
    """Scenario: order."""
    assert list(trial_order(7)) == [
        (0, "chroma_bm25", 0),
        (0, "postgres", 1),
        (1, "postgres", 0),
        (1, "chroma_bm25", 1),
        (2, "chroma_bm25", 0),
        (2, "postgres", 1),
        (3, "postgres", 0),
        (3, "chroma_bm25", 1),
        (4, "chroma_bm25", 0),
        (4, "postgres", 1),
        (5, "postgres", 0),
        (5, "chroma_bm25", 1),
        (6, "chroma_bm25", 0),
        (6, "postgres", 1),
    ]


def test_summaries():
    """Scenario: summaries."""
    assert summarize([7, 1, 6, 2, 5, 3, 4]) == {"min": 1, "median": 4, "max": 7}


@pytest.mark.parametrize("values", [[], [math.nan], [math.inf], [-1], [True]])
def test_summaries_reject_invalid_values(values):
    with pytest.raises(ValueError):
        summarize(values)


def test_resident_set_parsing():
    """Scenario: resident set parsing."""
    assert parse_rss("  51200\n") == 52428800
    with pytest.raises(ValueError):
        parse_rss("")
    with pytest.raises(ValueError):
        parse_rss("unknown")


def _trial(arm, rankings):
    result = {
        "arm": arm,
        "import_ms": 1.0,
        "open_ms": 2.0,
        "time_to_first_result_ms": 3.0,
        "workload_ms": 4.0,
        "baseline_rss_bytes": 100,
        "rss_after_workload_bytes": 200,
        "peak_rss_bytes": 300,
        "rankings": rankings,
    }
    if arm == "chroma_bm25":
        result.update(restore_ms=1.0, bm25_ms=1.0, first_query_ms=1.0)
    else:
        result.update(first_query_ms=1.0, first_ann_ms=1.0, ann_workload_ms=1.0)
        result["backend_rss_bytes"] = 400
    return result


def test_trial_record_validation_accepts_valid_and_rejects_bad():
    valid = _trial("chroma_bm25", {"chroma_fused": [[1], [0]]})
    assert validate_trial_record(valid, "chroma_bm25", 2) == valid
    with pytest.raises(ValueError):
        validate_trial_record({**valid, "import_ms": True}, "chroma_bm25", 2)
    with pytest.raises(ValueError):
        validate_trial_record({**valid, "rankings": {"chroma_fused": [[1]]}}, "chroma_bm25", 2)
    with pytest.raises(ValueError):
        validate_trial_record({**valid, "arm": "postgres"}, "chroma_bm25", 2)


def test_rankings_digest_stability_and_d1_comparison():
    rankings = [[2, 1], [0]]
    canonical = json.dumps(rankings, sort_keys=True, separators=(",", ":"))
    assert rankings_sha256(rankings) == hashlib.sha256(canonical.encode()).hexdigest()
    assert rankings_sha256(rankings) == rankings_sha256([[2, 1], [0]])
    assert compare_d1(rankings, [[2, 1], [1]]) == {"equal": False, "matching_cases": 1}
    assert compare_d1(rankings, rankings) == {"equal": True, "matching_cases": 2}


def test_build_report_status_keys_and_separate_memory():
    """Scenario: a cleanup failure."""
    password = "secret-db-password"
    context = {
        "code_base": "a" * 40,
        "database": "rag_spike_d5_0123456789abcdef",
        "input_sha256": {},
        "source_sha256": {},
        "versions": {},
        "python": "3.11",
        "platform": "darwin",
        "host": {},
        "postgres": "PostgreSQL 16",
        "pgvector": "0.7",
        "server_settings": {},
        "setup": {},
        "host_load": {},
        "d1_cross_check": {},
        "chunks": 2,
        "cases": 2,
        "trials": 1,
    }
    records = [
        {
            **_trial("chroma_bm25", {"chroma_fused": [[1], [0]]}),
            "trial": 0,
            "position": 0,
            "process_wall_ms": 10,
        },
        {
            **_trial("postgres", {"postgres_fused": [[1], [0]], "postgres_hnsw": [[1], [0]]}),
            "trial": 0,
            "position": 1,
            "process_wall_ms": 11,
        },
    ]
    clean = {"database_dropped": True, "role_dropped": True, "chroma_dir_removed": True}
    report = build_report(context, records, clean)
    assert report["status"] == "measured"
    assert set(report) == {
        "schema_version",
        "status",
        "code_base",
        "database",
        "input_sha256",
        "source_sha256",
        "versions",
        "python",
        "platform",
        "host",
        "postgres",
        "pgvector",
        "server_settings",
        "config",
        "setup",
        "host_load",
        "trials",
        "summary",
        "rankings",
        "d1_cross_check",
        "cleanup",
    }
    assert set(report["summary"]) == {"chroma_bm25", "postgres"}
    assert "backend_rss_bytes" in report["summary"]["postgres"]
    assert all("combined" not in key for fields in report["summary"].values() for key in fields)
    assert report["trials"][0]["rankings_sha256"]["chroma_fused"]
    assert "rankings" not in report["trials"][0]
    assert password not in json.dumps(report)
    with pytest.raises(ValueError, match="incomplete"):
        build_report(context, records[:1], clean)
    failed = build_report(context, records, {**clean, "database_dropped": False})
    assert failed["status"] == "cleanup_failed"
    assert failed["database"] == context["database"]
