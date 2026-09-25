"""Offline checks of the published Chroma restart-stability rerun after the fix."""

import copy
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import chroma_restart_stability as crs
from scripts import chroma_restart_stability_run as runner
from tests.capsule_prose import capsule_defects, numeric_claims, prose_lines

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "evaluation" / "chroma-restart-stability-after-fix.json"
FIRST_REPORT = ROOT / "evaluation" / "chroma-restart-stability.json"
D1_REPORT = ROOT / "evaluation" / "d1-pgvector-prererank.json"
CAPSULE = ROOT / "docs" / "evidence" / "chroma-restart-stability-after-fix.md"
FIRST_CAPSULE = ROOT / "docs" / "evidence" / "chroma-restart-stability.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
REPORT_SHA256 = "b3819a8d577f9f1f917b3b07e7bc9d413a1157e86ed1f1ccc8a6fceda3f897b3"
REPORT_BYTES = 217303
CODE_COMMIT = "534612eda228d90b2c5c4f2e92f432d738adecdf"
FIRST_SHA256 = "590fc711e6ddf9db3cc61178bd37f6c3b6d62fadb25201a96e46e15f38ed304d"
FIRST_COMMIT = "5e7037a985249d47dfb6b1ae88056d508b961b91"


@pytest.fixture(scope="module")
def published():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def first_report():
    return json.loads(FIRST_REPORT.read_text(encoding="utf-8"))


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

    collect({key: value for key, value in published.items() if key != "answers"})
    for section in published["comparison"].values():
        variations = section.values() if "trials" not in section else (section,)
        for variation in variations:
            integers.update(len(row["differing_cases"]) for row in variation["trials"])
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
    assert published["schema_version"] == crs.SCHEMA_VERSION == "chroma-restart-stability-v1"
    assert published["status"] == "measured"
    assert published["cleanup"] == {"directory_removed": True}


def test_inputs_are_d1s_and_the_first_runs(published, first_report, d1):
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
    assert list(digests) == list(first_report["input_sha256"])
    assert digests == first_report["input_sha256"]
    for name, digest in d1["input_sha256"].items():
        assert digests[name] == digest
    archive_bytes = runner.ARCHIVE.read_bytes()
    assert digests[runner.ARCHIVE.name] == _sha256(archive_bytes)
    assert digests["ab_phase2_G2_graph_chunks.json"] == _sha256(gzip.decompress(archive_bytes))
    for case_file in runner.CASE_FILES:
        assert digests[case_file.name] == _sha256(case_file.read_bytes())
    assert digests[D1_REPORT.name] == _sha256(D1_REPORT.read_bytes())


def test_source_digests_are_the_code_commits_blobs_and_calls_differ(published):
    assert published["code_commit"] == CODE_COMMIT
    source_digests = published["source_sha256"]
    assert list(source_digests) == list(runner.SOURCE_FILES)
    for relative in runner.SOURCE_FILES:
        blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{relative}"], cwd=ROOT)
        assert b"\r\n" not in blob
        assert source_digests[relative] == _sha256(blob)

    staged_path = "vectordb/index_staging.py"
    current_blob = subprocess.check_output(
        ["git", "show", f"{CODE_COMMIT}:{staged_path}"], cwd=ROOT
    )
    crs.assert_staged_build_call(current_blob.decode("utf-8"))
    first_blob = subprocess.check_output(["git", "show", f"{FIRST_COMMIT}:{staged_path}"], cwd=ROOT)
    with pytest.raises(ValueError, match="from_documents call changed"):
        crs.assert_staged_build_call(first_blob.decode("utf-8"))


def test_recorded_environment_and_protocol_match_the_first_run(published, first_report):
    for field in (
        "versions",
        "python",
        "platform",
        "host",
        "collection_name",
        "chunk_count",
        "case_count",
        "trial_count",
        "settings",
    ):
        assert published[field] == first_report[field]
    assert published["versions"] == {
        "numpy": "1.26.4",
        "chromadb": "1.5.9",
        "langchain-chroma": "1.1.0",
        "langchain-core": "1.4.0",
        "rank-bm25": "0.2.2",
    }
    assert published["python"] == "3.11.15"
    assert published["platform"] == "darwin"
    assert published["host"] == {
        "cpu_count": 4,
        "hw.model": "iMac18,3",
        "hw.memsize": "8589934592",
    }
    assert published["collection_name"] == crs.COLLECTION
    assert published["chunk_count"] == crs.EXPECTED_CHUNKS == 5589
    assert published["case_count"] == crs.EXPECTED_CASES == 115
    assert published["trial_count"] == crs.TRIALS == 7
    assert published["settings"] == {
        "retrieval_top_k": 20,
        "rrf_k": 60,
        "rrf_doc_key_chars": 200,
    }
    assert published["start_utc"] < published["end_utc"]
    assert len(published["load_average_start"]) == 3
    assert all(type(value) is float for value in published["load_average_start"])


def test_build_persisted_through_the_highest_log_sequence(published, first_report):
    build = published["build"]
    assert build["embed_documents_call_lengths"] == [5461, 128]
    assert sum(build["embed_documents_call_lengths"]) == published["chunk_count"]
    assert build["collection_count"] == build["restored_chunk_count"] == 5589
    first_hnsw = first_report["build"]["hnsw"]
    expected_hnsw = {**first_hnsw, "sync_threshold": 1}
    assert build["hnsw"] == expected_hnsw
    assert {key for key in first_hnsw if first_hnsw[key] != build["hnsw"][key]} == {
        "sync_threshold"
    }
    assert build["chroma_log_max_seq_id"] == build["chroma_vector_persisted_seq_id"] == 5589
    assert build["unpersisted_tail"] == 5589 - 5589 == 0
    assert build["settings"] == published["settings"]
    assert type(build["build_ms"]) is float and build["build_ms"] > 0
    assert type(build["process_wall_ms"]) is float and build["process_wall_ms"] > 0


def test_trials_follow_the_seven_process_protocol(published):
    trials = published["trials"]
    assert [trial["trial"] for trial in trials] == list(range(7))
    for trial in trials:
        assert set(trial) == {"restored_chunk_count", "settings", "trial", "process_wall_ms"}
        assert trial["restored_chunk_count"] == 5589
        assert trial["settings"] == published["settings"]
        assert type(trial["process_wall_ms"]) is float and trial["process_wall_ms"] > 0


def test_comparison_replays_from_the_report_alone(published):
    answers = published["answers"]
    build = answers["build"]
    trial_0 = answers["trial_0"]
    crs.validate_answers(build, 115, 20)
    crs.validate_answers(trial_0, 115, 20)

    rebuilt = []
    differences = answers["trial_differences"]
    assert [entry["trial"] for entry in differences] == list(range(1, 7))
    for entry in differences:
        trial = copy.deepcopy(build)
        for path in ("vector", "candidates"):
            cases = [item["case_index"] for item in entry[path]]
            assert cases == sorted(set(cases))
            for item in entry[path]:
                trial[path][item["case_index"]] = copy.deepcopy(item["answer"])
        crs.validate_answers(trial, 115, 20)
        rebuilt.append(trial)

    trial_answers = [trial_0, *rebuilt]
    assert crs.compare_answers(build, trial_answers) == published["comparison"]

    moved = copy.deepcopy(trial_answers)
    replacement = next(chunk for chunk in range(5589) if chunk not in moved[3]["vector"][0])
    moved[3]["vector"][0][-1] = replacement
    assert crs.compare_answers(build, moved) != published["comparison"]

    reordered_build = copy.deepcopy(build)
    reordered_build["candidates"][0].reverse()
    reordered = crs.compare_answers(reordered_build, trial_answers)
    assert reordered["build_vs_trials"] != published["comparison"]["build_vs_trials"]
    assert (
        reordered["candidate_sets_vs_build"] == published["comparison"]["candidate_sets_vs_build"]
    )


def test_no_trial_changes_any_case(published):
    comparison = published["comparison"]
    variations = [
        *comparison["build_vs_trials"].values(),
        *comparison["trial0_vs_later"].values(),
        comparison["candidate_sets_vs_build"],
    ]
    for variation in variations:
        assert variation["distinct_cases"] == 0
        assert all(row["differing_cases"] == [] for row in variation["trials"])

    differences = published["answers"]["trial_differences"]
    for entry in differences:
        assert entry["vector"] == []
        assert entry["candidates"] == []
    assert published["answers"]["trial_0"] == published["answers"]["build"]


def test_first_report_is_untouched_and_its_capsule_links_to_rerun(first_report):
    assert _sha256(FIRST_REPORT.read_bytes()) == FIRST_SHA256
    assert first_report["code_commit"] == FIRST_COMMIT
    assert first_report["build"]["unpersisted_tail"] == 128
    assert first_report["build"]["hnsw"]["sync_threshold"] == 1000
    assert (
        "**Rerun after the fix:** "
        "[chroma-restart-stability-after-fix](chroma-restart-stability-after-fix.md)."
        in FIRST_CAPSULE.read_text(encoding="utf-8")
    )


def test_capsule_quotes_only_report_numbers(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert capsule_defects(capsule, decimals=decimals, integers=integers) == []
    claims = set(numeric_claims("\n".join(prose_lines(capsule))))
    assert {"5589", "5461", "128", "115"} <= claims

    assert "resize_factor 1.2" in "\n".join(prose_lines(capsule))
    assert not any(f"{value:.1f}" == "999999.9" for value in decimals)
    changed = capsule.replace("resize_factor 1.2", "resize_factor 999999.9", 1)
    assert changed != capsule
    assert any(
        "prose quotes 999999.9," in defect
        for defect in capsule_defects(changed, decimals=decimals, integers=integers)
    )

    unreported = next(value for value in range(21, max(integers) + 2) if value not in integers)
    changed = capsule + f"\nThe unrelated count is {unreported}.\n"
    assert any(
        f"prose quotes {unreported}," in defect
        for defect in capsule_defects(changed, decimals=decimals, integers=integers)
    )


def test_capsule_names_digests_protocol_and_limits(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    for digest in (
        REPORT_SHA256,
        CODE_COMMIT,
        *published["input_sha256"].values(),
        *published["source_sha256"].values(),
    ):
        assert digest in capsule
    for phrase in (
        "../specs/chroma-restart-stability.md",
        "../specs/chroma-index-persistence.md",
        "(chroma-restart-stability.md)",
        "write-ahead log",
        "precomputed",
        "reranker",
        "NOT_EVIDENCE",
        "this corpus, this host and these versions",
        "rebuilt",
        "no runtime default",
    ):
        assert phrase in capsule


def test_evidence_index_row_points_at_capsule_report_and_test(published):
    index = INDEX.read_text(encoding="utf-8")
    rows = [
        line
        for line in index.splitlines()
        if "docs/evidence/chroma-restart-stability-after-fix.md" in line
    ]
    assert len(rows) == 1
    row = rows[0]
    slices = index.split("## Slices\n", 1)[1].splitlines()
    first_row = slices.index("| Slice | Capsule | Evidence class |") + 2
    last_row = next(
        (
            position
            for position in range(first_row, len(slices))
            if not slices[position].startswith("|")
        ),
        len(slices),
    )
    assert row in slices[first_row:last_row]
    assert "evaluation/chroma-restart-stability-after-fix.json" in row
    assert "tests/test_chroma_restart_stability_after_fix_artifact.py" in row
    assert "measured" in row
    decimals, integers = _report_numbers(published)
    assert capsule_defects(row, decimals=decimals, integers=integers) == []
    unreported = next(value for value in range(21, max(integers) + 2) if value not in integers)
    changed = row.replace("0 of 5589", f"{unreported} of 5589", 1)
    assert changed != row
    assert any(
        f"quotes {unreported}," in defect
        for defect in capsule_defects(changed, decimals=decimals, integers=integers)
    )
