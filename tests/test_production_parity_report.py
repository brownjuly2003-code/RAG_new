"""A parity publication must come from all registered, integrity-checked rows."""

import hashlib
import json

import pytest

from scripts import production_parity as parity


@pytest.fixture
def completed_run(tmp_path):
    cases = parity.select_cases([
        {"case_id": f"case-{i}", "query": f"question {i}"} for i in range(30)
    ], 30)
    manifest = {
        "cases": cases, "code_sha": "a" * 40, "dataset_sha256": "b" * 64,
        "config": {"graph_retrieval": "off"},
        "index_receipt": {"corpus_sha256": "c" * 64},
    }
    parity.write_new(tmp_path / "manifest.json", manifest)
    identity = parity.digest(manifest)
    divergences = {}
    for i, case in enumerate(cases):
        texts = ["cargo rules"]
        row = {
            **case, "query_effective": case["query"], "query_transform": "none",
            "query_transform_hash": "transform", "cands": texts,
            "sent_context_sha256": hashlib.sha256("\n\n".join(texts).encode()).hexdigest(),
            "vector": [1, 2], "pool": [1, 2], "ranked": [1],
        }
        other = {**row, "vector": [2, 1]} if i == 0 else dict(row)
        if i == 1:
            other = {**row, "pool": [1, 3]}
        pair = {"chroma": row, "exact": other}
        diff = parity.differences(row, other)
        if diff:
            divergences[case["case_id"]] = diff
        parity.save_stage(tmp_path / "grade" / (case["case_id"] + ".json"), pair, identity)
        parity.save_stage(tmp_path / "verify" / (case["case_id"] + ".json"), {
            **pair, "chroma_exact_differences": diff,
        }, identity)
    parity.write_new(tmp_path / "comparison.json", {
        "manifest_sha256": identity, "cases": 30, "session_replay_matches": 60,
        "divergences": divergences, "latency_evidence": False,
    })
    return tmp_path, cases


def test_report_separates_order_from_membership_and_preserves_provenance(completed_run):
    from scripts.production_parity_report import build_report

    run, cases = completed_run
    report = build_report(run)
    assert report["cases"] == 30
    assert report["session_replay_matches"] == 60
    assert report["differences"]["vector"] == {"order": 1, "membership": 0}
    assert report["differences"]["pool"] == {"order": 1, "membership": 1}
    assert report["differences"]["ranked"] == {"order": 0, "membership": 0}
    assert report["context_hash_matches"] == 30
    assert report["manifest"]["code_sha"] == "a" * 40
    assert report["manifest"]["index_receipt"]["corpus_sha256"] == "c" * 64
    assert report["latency_evidence"] is False
    assert len(report["input_sha256"]) == 62
    assert report["per_case"][0]["case_id"] == cases[0]["case_id"]


@pytest.mark.parametrize("damage", [
    "missing", "corrupt", "wrong_run", "wrong_case", "wrong_context",
    "grade_mismatch", "false_summary", "false_differences", "duplicate_case",
])
def test_report_refuses_incomplete_or_inconsistent_evidence(completed_run, damage):
    from scripts.production_parity_report import build_report

    run, cases = completed_run
    path = run / "verify" / (cases[0]["case_id"] + ".json")
    record = parity.read(path)
    if damage == "missing":
        path.rename(path.with_suffix(".incomplete"))
    elif damage == "false_summary":
        path = run / "comparison.json"
        record = parity.read(path)
        record["session_replay_matches"] = 59
    elif damage == "duplicate_case":
        path = run / "manifest.json"
        record = parity.read(path)
        record["cases"][1] = record["cases"][0]
    else:
        if damage == "wrong_run":
            record["run_sha256"] = "other"
        elif damage == "wrong_case":
            record["result"]["chroma"]["case_id"] = "other"
        elif damage in ("wrong_context", "corrupt"):
            record["result"]["chroma"]["cands"] = ["changed text"]
        elif damage == "grade_mismatch":
            record["result"]["chroma"]["ranked"] = [2]
        elif damage == "false_differences":
            record["result"]["chroma_exact_differences"] = []
        if damage != "corrupt":
            record["result_sha256"] = parity.digest(record["result"])
    if damage != "missing":
        path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises((ValueError, FileNotFoundError)):
        build_report(run)


def test_report_cli_does_not_replace_an_existing_artifact(completed_run, tmp_path):
    from scripts.production_parity_report import main

    run, _ = completed_run
    output = tmp_path / "report.json"
    assert main(["--run", str(run), "--output", str(output)]) == 0
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        main(["--run", str(run), "--output", str(output)])
    assert output.read_bytes() == original
