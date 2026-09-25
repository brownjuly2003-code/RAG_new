"""Offline checks of the committed D.5 cold-start report.

The measurement needs the Mac, its PostgreSQL and D.1's untracked vector files, so this
test does not re-run it. It pins report bytes, inputs against D.1's recorded digests and
source blobs at the measurement commit; recomputes summaries, ranking digests and the D.1
cross-check with committed helpers; and holds the capsule, index row and ADR section to
the report's numbers.
"""

import gzip
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import pytest

from scripts import pgvector_cold_start as d5
from scripts import pgvector_cold_start_run as runner
from tests.capsule_prose import capsule_defects, numeric_claims, prose_lines

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "evaluation" / "d5-pgvector-cold-start.json"
D1_REPORT = ROOT / "evaluation" / "d1-pgvector-prererank.json"
CAPSULE = ROOT / "docs" / "evidence" / "d5-pgvector-cold-start.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
ADR = ROOT / "docs" / "adr" / "0007-pgvector-spike.md"
REPORT_SHA256 = "a9f0277cdca82fabe6f62bf3eeb929d3bfd3db510984edaba41366719b8ec7d4"
REPORT_BYTES = 142937
CODE_COMMIT = "ccec9ca5c13302016cd52abe478b6fd6abaa16b4"


@pytest.fixture(scope="module")
def published():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def d1():
    return json.loads(D1_REPORT.read_text(encoding="utf-8"))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _report_numbers(published) -> tuple[list[float], set[int]]:
    decimals: list[float] = []
    integers: set[int] = set()

    def collect(value):
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, float):
            decimals.append(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            integers.add(value)

    collect({key: value for key, value in published.items() if key != "rankings"})
    # The spec also allows each trial's changed-case count and the recorded log tail.
    integers.update(
        len(trial["differing_cases"]) for trial in published["chroma_fused_variation"]["trials"]
    )
    setup = published["setup"]
    integers.add(setup["chroma_log_max_seq_id"] - setup["chroma_vector_persisted_seq_id"])
    return decimals, integers


def test_report_bytes_are_pinned(published):
    raw = REPORT.read_bytes()
    assert _sha256(raw) == REPORT_SHA256
    assert _sha256(bytes([raw[0] ^ 1]) + raw[1:]) != REPORT_SHA256
    assert len(raw) == REPORT_BYTES
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")

    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    assert json.loads(raw, parse_constant=reject_constant) == published
    assert published["schema_version"] == d5.SCHEMA_VERSION == runner.SCHEMA_VERSION
    assert published["schema_version"] == "d5-pgvector-cold-start-v2"
    assert published["status"] == "measured"
    assert published["cleanup"] == {
        "database_dropped": True,
        "role_dropped": True,
        "chroma_dir_removed": True,
    }
    assert re.fullmatch(r"rag_spike_d5_[0-9a-f]{16}", published["database"])


def test_inputs_are_d1s(published, d1):
    digests = published["input_sha256"]
    assert list(digests) == [
        "gr1b-4436d61-graph-chunks.json.gz",
        "chunks.npz",
        "d1-queries.npy",
        "curated_cases_aircargo.jsonl",
        "curated_cases_aircargo_gr_multihop.jsonl",
        "ab_phase2_G2_graph_chunks.json",
        "d1-pgvector-prererank.json",
    ]
    for name, digest in d1["input_sha256"].items():
        assert digests[name] == digest
    archive_bytes = runner.ARCHIVE.read_bytes()
    assert digests[runner.ARCHIVE.name] == _sha256(archive_bytes)
    assert digests["ab_phase2_G2_graph_chunks.json"] == _sha256(gzip.decompress(archive_bytes))
    for case_file in runner.CASE_FILES:
        assert digests[case_file.name] == _sha256(case_file.read_bytes())
    assert digests[D1_REPORT.name] == _sha256(D1_REPORT.read_bytes())


def test_source_digests_are_the_blobs_at_the_measurement_commit(published):
    assert published["code_base"] == CODE_COMMIT
    source_digests = published["source_sha256"]
    assert list(source_digests) == list(runner.SOURCE_FILES)
    for relative in runner.SOURCE_FILES:
        blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{relative}"], cwd=ROOT)
        assert b"\r\n" not in blob
        assert source_digests[relative] == _sha256(blob)


def test_recorded_environment_and_protocol(published):
    assert published["versions"] == {
        "numpy": "1.26.4",
        "chromadb": "1.5.9",
        "rank-bm25": "0.2.2",
        "psycopg2-binary": "2.9.12",
    }
    assert published["python"] == "3.11.15"
    assert published["platform"] == "darwin"
    assert published["pgvector"] == "0.8.1"
    assert published["postgres"].startswith("PostgreSQL 16.15")
    assert published["host"] == {"physical_memory_bytes": 8589934592, "cpu_count": 4}
    assert published["server_settings"] == {
        "shared_buffers": "128MB",
        "work_mem": "4MB",
        "maintenance_work_mem": "64MB",
        "effective_cache_size": "4GB",
    }
    assert published["config"] == {
        "trials": 7,
        "gated_ranking_paths": list(d5.GATED_PATHS),
        "order": "chroma_bm25 first on even trials; postgres first on odd trials",
        "top_k": 20,
        "rrf_k": 60,
        "ef_search": 100,
        "force_index": True,
        "chroma_space": "cosine",
        "chroma_batch": 500,
        "collection": "d5_aircargo",
        "tenant": "aircargo",
        "chunks": 5589,
        "cases": 115,
        "embedding_model": "BAAI/bge-m3",
        "query_vectors": "precomputed",
        "reranker": False,
        "embedding_model_loaded": False,
        "os_file_cache": "not_controlled",
        "postgres_restart": "not_controlled",
    }
    assert published["host_load"] == {
        "before": {
            "load_average": "1.22998046875, 1.7841796875, 1.58154296875",
            "swap_usage": "total = 1024.00M  used = 225.25M  free = 798.75M  (encrypted)",
        },
        "after": {
            "load_average": "1.458984375, 1.72314453125, 1.572265625",
            "swap_usage": "total = 1024.00M  used = 225.25M  free = 798.75M  (encrypted)",
        },
    }


def test_trials_follow_the_protocol(published):
    trials = published["trials"]
    assert len(trials) == 14
    assert [(t["trial"], t["arm"], t["position"]) for t in trials] == list(d5.trial_order(7))
    for trial in trials:
        arm = trial["arm"]
        assert set(trial) == d5._COMMON_FIELDS | d5._ARM_FIELDS[arm] | {
            "arm",
            "trial",
            "position",
            "process_wall_ms",
            "rankings_sha256",
        }
        for name in (
            d5._COMMON_FIELDS
            | d5._ARM_FIELDS[arm]
            | {
                "trial",
                "position",
                "process_wall_ms",
            }
        ):
            value = trial[name]
            assert type(value) in (int, float) and math.isfinite(value) and value >= 0
        steps = ["import_ms", "open_ms", "first_query_ms"]
        if arm == "chroma_bm25":
            steps = ["import_ms", "open_ms", "restore_ms", "bm25_ms", "first_query_ms"]
        assert math.isclose(
            trial["time_to_first_result_ms"],
            sum(trial[name] for name in steps),
            rel_tol=1e-12,
        )


def test_summaries_replay_through_the_committed_helper(published):
    assert set(published["summary"]) == {"chroma_bm25", "postgres"}
    for arm, summary in published["summary"].items():
        trials = [trial for trial in published["trials"] if trial["arm"] == arm]
        fields = d5._COMMON_FIELDS | d5._ARM_FIELDS[arm] | {"process_wall_ms"}
        assert set(summary) == fields
        for name in fields:
            assert summary[name] == d5.summarize([trial[name] for trial in trials])


def test_ranking_digests_and_the_postgresql_gate(published):
    rankings = published["rankings"]
    assert set(rankings) == {"chroma_fused", "postgres_fused", "postgres_hnsw"}
    for path, rows in rankings.items():
        assert len(rows) == 115 and all(isinstance(row, list) for row in rows)
        first = next(
            trial
            for trial in published["trials"]
            if trial["trial"] == 0 and path in trial["rankings_sha256"]
        )
        assert d5.rankings_sha256(rows) == first["rankings_sha256"][path]
        if path in d5.GATED_PATHS:
            for trial in published["trials"]:
                if trial["arm"] == "postgres":
                    assert trial["rankings_sha256"][path] == first["rankings_sha256"][path]
    variation = {
        entry["trial"]: entry["differing_cases"]
        for entry in published["chroma_fused_variation"]["trials"]
    }
    chroma = [trial for trial in published["trials"] if trial["arm"] == "chroma_bm25"]
    first_digest = chroma[0]["rankings_sha256"]["chroma_fused"]
    for trial in chroma[1:]:
        assert (trial["rankings_sha256"]["chroma_fused"] == first_digest) == (
            not variation[trial["trial"]]
        )
        assert variation[trial["trial"]]


def test_chroma_variation(published):
    variation = published["chroma_fused_variation"]
    assert variation == {
        "trials": [
            {"trial": 1, "differing_cases": [28, 51, 74, 93]},
            {"trial": 2, "differing_cases": [4, 5, 12, 23, 28, 59, 74]},
            {"trial": 3, "differing_cases": [7, 12, 23, 28, 72, 74]},
            {"trial": 4, "differing_cases": [4, 12, 23, 28, 59, 74]},
            {"trial": 5, "differing_cases": [12, 23, 28, 59]},
            {"trial": 6, "differing_cases": [4, 5, 7, 12, 23, 28, 52, 59, 72, 73, 93]},
        ],
        "distinct_cases": 13,
    }
    changed = set()
    for entry in variation["trials"]:
        cases = entry["differing_cases"]
        assert cases == sorted(set(cases))
        assert set(cases) <= set(range(115))
        changed.update(cases)
    assert len(changed) == variation["distinct_cases"]


def test_log_positions(published):
    setup = published["setup"]
    assert setup["chroma_log_max_seq_id"] == 5589 == published["config"]["chunks"]
    assert setup["chroma_vector_persisted_seq_id"] == 5000
    assert setup["chroma_log_max_seq_id"] - setup["chroma_vector_persisted_seq_id"] == 589


def test_d1_cross_check_replays(published, d1):
    recorded = published["d1_cross_check"]
    first = d1["runs"][0]
    assert (
        d5.compare_d1(published["rankings"]["chroma_fused"], first["chroma_bm25"]["rankings"])
        == recorded["chroma_bm25"]
        == {"equal": False, "matching_cases": 91}
    )
    assert (
        d5.compare_d1(published["rankings"]["postgres_fused"], first["postgres"]["rankings"])
        == recorded["postgres"]
        == {"equal": True, "matching_cases": 115}
    )


def test_memory_is_recorded_per_process(published):
    for trial in published["trials"]:
        rss = {key for key in trial if "rss" in key}
        expected = {"baseline_rss_bytes", "rss_after_workload_bytes", "peak_rss_bytes"}
        if trial["arm"] == "postgres":
            expected.add("backend_rss_bytes")
        assert rss == expected

    def check_keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert not re.search(r"(?:^|_)(?:sum|total|combined)(?:_|$)", key)
                check_keys(item)
        elif isinstance(value, list):
            for item in value:
                check_keys(item)

    check_keys(published)


def test_capsule_quotes_only_report_numbers(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert capsule_defects(capsule, decimals=decimals, integers=integers) == []
    claims = numeric_claims("\n".join(prose_lines(capsule)))
    assert {"85.7", "1494.7", "13", "589"} <= set(claims)


def test_capsule_number_check_rejects_an_unreported_number(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert not any(f"{value:.1f}" == "1494.9" for value in decimals)
    assert "1494.7" in "\n".join(prose_lines(capsule))
    changed = capsule.replace("1494.7", "1494.9", 1)
    assert "1494.9" in "\n".join(prose_lines(changed))
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any("prose quotes 1494.9," in defect for defect in defects)

    unreported = next(value for value in range(21, max(integers) + 2) if value not in integers)
    changed = capsule + f"\nThe unrelated count is {unreported}.\n"
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any(f"prose quotes {unreported}," in defect for defect in defects)


def test_capsule_names_digests_and_limits(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    for digest in (
        REPORT_SHA256,
        CODE_COMMIT,
        *published["input_sha256"].values(),
        *published["source_sha256"].values(),
    ):
        assert digest in capsule
    for phrase in (
        "amendment 1",
        "NOT_EVIDENCE",
        "not controlled",
        "precomputed",
        "never added",
        "write-ahead log",
        "EphemeralClient",
        "retain",
    ):
        assert phrase in capsule


def test_evidence_index_row_points_at_capsule_report_and_test(published):
    rows = [
        line
        for line in INDEX.read_text(encoding="utf-8").splitlines()
        if "docs/evidence/d5-pgvector-cold-start.md" in line
    ]
    assert len(rows) == 1
    row = rows[0]
    assert "evaluation/d5-pgvector-cold-start.json" in row
    assert "tests/test_pgvector_cold_start_artifact.py" in row
    assert "measured" in row
    decimals, integers = _report_numbers(published)
    assert capsule_defects(row, decimals=decimals, integers=integers) == []
    changed = row.replace("1494.7", "1494.9", 1)
    assert changed != row
    assert any(
        "1494.9" in defect
        for defect in capsule_defects(changed, decimals=decimals, integers=integers)
    )


def test_adr_d5_section_quotes_the_report(published):
    adr = ADR.read_text(encoding="utf-8")
    heading = "## D.5 cold-start and memory numbers"
    assert len(re.findall(r"(?m)^## D\.5 cold-start and memory numbers$", adr)) == 1
    section = adr.split(heading, 1)[1].split("\n## ", 1)[0]
    decimals, integers = _report_numbers(published)
    assert capsule_defects(section, decimals=decimals, integers=integers) == []
    changed = section.replace("1494.7", "1494.9", 1)
    assert changed != section
    assert any(
        "1494.9" in defect
        for defect in capsule_defects(changed, decimals=decimals, integers=integers)
    )
    for number in ("85.7", "1494.7", "68,644,864", "310,738,944", "98,246,656"):
        assert number in section
    status = next(line for line in adr.splitlines() if line.startswith("Status:"))
    assert "D.1–D.5 measured" in status and "retain" in status
    assert "../evidence/d5-pgvector-cold-start.md" in adr
