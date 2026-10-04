"""Check the published parity measurement without models or network access."""

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts.production_parity import ReplayCache, differences, digest, file_sha, select_cases

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/parity/c729b23"
CAPSULE = ROOT / "docs/evidence/production-parity-30-cases.md"
FILES = {
    "manifest.json": ("98b58484408e419fab244a2c7d9b3c3f99f178a2c4a7e823f6178c13dbdf50a3", 29571),
    "comparison.json": ("6dcc2aff88277dc781ed0adbfdc5074fae516163fee91725cc603b6bc710ae47", 856),
    "report.json": ("3fd4080eda5a7c2a435eb7404632d463780f6e43949b3ed809ad4807a7f3db90", 133985),
    "cache-outcomes.json": (
        "00a1999b63488a39489fcd64fed2703fed22cae5a1426d87d02747364c508e99",
        309,
    ),
    "cache_outcomes.py": ("94ef2b0eb8e1fe9ee4a8707b81e29f81885a6275de49ebbc943597cd1d529f4b", 1790),
}
CODE_SHA = "c729b2360e1074ac4e6c1ca641a8d20c6b826d8f"
DATASET = "evaluation/curated_cases_aircargo.jsonl"
# The directories whose `*.py` files `source_identity` hashed at the run commit.
SOURCE_DIRS = ("agent", "config", "ingestion", "llm", "scripts", "utils", "vectordb")


def load(name):
    return json.loads((REPORT / name).read_text(encoding="utf-8"))


def cell(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def provenance(manifest):
    receipt = manifest["index_receipt"]
    return {
        "code_sha": manifest["code_sha"],
        "source_sha256": manifest["source_sha256"],
        "dataset_sha256": manifest["dataset_sha256"],
        "corpus_sha256": receipt["corpus_sha256"],
        "chunk_count": receipt["chunk_count"],
        "index_receipt_sha256": manifest["index_receipt_sha256"],
        "checkpoint_sha256": receipt["checkpoint_sha256"],
        "index build code_sha": receipt["code_sha"],
        "embedder_manifest": receipt["embedder_manifest"],
        "reranker": manifest["reranker"],
        "llm": manifest["llm"],
        "config": manifest["config"],
        "runtime": manifest["runtime"],
        "host snapshot corpus path": manifest["corpus"],
        "index path": manifest["index"],
        "checkpoint path": manifest["checkpoint"],
    }


def check_capsule(body, manifest, report, comparison, cache):
    # A number is pinned with the character after it: `13` must not accept `130`.
    phrases = [
        f"Cases: {report['cases']},",
        f"`{DATASET}`",
        f"tenant `{manifest['cases'][0]['tenant_id']}`",
        f"Selection: `{manifest['selection']}`",
        f"session_replay_matches: {report['session_replay_matches']} (",
        f"context_hash_matches: {report['context_hash_matches']} of {report['cases']}.",
        f"Divergent cases: {len(comparison['divergences'])}.",
        f"cache_records: {cache['cache_records']}.",
        f"integrity_mismatches: {cache['integrity_mismatches']}.",
        f": {report['cases'] - report['context_hash_matches']} of {report['cases']} here",
        "latency_evidence: false",
        "no answers and no quality verdict",
        "one run, no repeat",
        "one tenant",
        manifest["limits"],
        report["limits"],
        f"evidence_status: `{manifest['index_receipt']['evidence_status']}`",
    ]
    for field, values in report["differences"].items():
        phrases.append(f"| `{field}` | {values['order']} | {values['membership']} |")
    for field, value in report["query_differences"].items():
        phrases.append(f"{field}: {value}.")
    for group in ("records_by_kind", "llm_outcomes"):
        for field, value in cache[group].items():
            phrases.append(f"{group}.{field}: {value}.")
    for field, value in provenance(manifest).items():
        phrases.append(f"| {field} | `{cell(value)}` |")
    for name, (sha, size) in FILES.items():
        phrases.append(f"](../../reports/parity/c729b23/{name}) | {size} | `{sha}` |")
    for case_id, fields in comparison["divergences"].items():
        phrases.append(f"| `{case_id}` | {', '.join(f'`{f}`' for f in fields)} |")
    for phrase in phrases:
        assert phrase in body, phrase
    assert "latency_evidence: true" not in body
    assert "quality verdict: pass" not in body


def test_published_file_integrity():
    for name, (sha, size) in FILES.items():
        assert file_sha(REPORT / name) == sha
        assert (REPORT / name).stat().st_size == size


def test_manifest_and_input_identity():
    manifest, report = load("manifest.json"), load("report.json")
    assert manifest["code_sha"] == CODE_SHA
    assert REPORT.name == CODE_SHA[:7]
    assert report["manifest"] == manifest
    identity = digest(manifest)
    assert identity == report["manifest_sha256"]
    assert identity == load("comparison.json")["manifest_sha256"]
    assert identity == load("cache-outcomes.json")["manifest_sha256"]
    for name in ("manifest.json", "comparison.json"):
        assert report["input_sha256"][name] == file_sha(REPORT / name)
    assert select_cases(manifest["cases"], 30) == manifest["cases"]


def test_source_and_cases_come_from_the_run_commit():
    manifest = load("manifest.json")
    raw = subprocess.check_output(["git", "archive", CODE_SHA, *SOURCE_DIRS], cwd=ROOT)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isfile() and member.name.endswith(".py"):
                files[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert digest(files) == manifest["source_sha256"]
    blob = subprocess.check_output(["git", "show", f"{CODE_SHA}:{DATASET}"], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == manifest["dataset_sha256"]
    cases = [json.loads(line) for line in blob.decode("utf-8").splitlines()]
    assert select_cases(cases, 30) == manifest["cases"]


def test_artifact_counts_are_consistent():
    manifest, report = load("manifest.json"), load("report.json")
    comparison, cache = load("comparison.json"), load("cache-outcomes.json")
    assert comparison["cases"] == report["cases"] == len(manifest["cases"]) == 30
    assert len({case["tenant_id"] for case in manifest["cases"]}) == 1
    assert len(report["per_case"]) == report["cases"]
    assert [r["case_id"] for r in report["per_case"]] == [c["case_id"] for c in manifest["cases"]]
    assert (
        comparison["session_replay_matches"]
        == report["session_replay_matches"]
        == 2 * report["cases"]
    )
    divergences = {}
    context_matches = 0
    counts = {field: {"order": 0, "membership": 0} for field in report["differences"]}
    queries = dict.fromkeys(report["query_differences"], 0)
    for row in report["per_case"]:
        left, right = row["chroma"], row["exact"]
        diff = differences(left, right)
        assert row["differences"] == diff
        if diff:
            divergences[row["case_id"]] = diff
        for field, values in counts.items():
            values["order"] += left[field] != right[field]
            values["membership"] += set(left[field]) != set(right[field])
        for field in queries:
            queries[field] += left[field] != right[field]
        context_matches += left["sent_context_sha256"] == right["sent_context_sha256"]
    assert counts == report["differences"]
    assert queries == report["query_differences"]
    assert divergences == comparison["divergences"]
    assert context_matches == report["context_hash_matches"]
    assert sum(cache["records_by_kind"].values()) == cache["cache_records"]
    assert sum(cache["llm_outcomes"].values()) == cache["records_by_kind"]["llm"]
    assert cache["integrity_mismatches"] == 0
    assert report["latency_evidence"] is comparison["latency_evidence"] is False


def test_capsule_matches_published_fields():
    check_capsule(
        CAPSULE.read_text(encoding="utf-8"),
        load("manifest.json"),
        load("report.json"),
        load("comparison.json"),
        load("cache-outcomes.json"),
    )


def test_capsule_rejects_changed_outcome_count():
    cache = load("cache-outcomes.json")
    count = cache["llm_outcomes"]["structured_output_invalid"]
    phrase = f"llm_outcomes.structured_output_invalid: {count}."
    body = CAPSULE.read_text(encoding="utf-8")
    assert phrase in body
    # An appended digit keeps the published number as a prefix of the wrong one.
    corrupted = body.replace(phrase, f"llm_outcomes.structured_output_invalid: {count}0.", 1)
    with pytest.raises(AssertionError, match="structured_output_invalid"):
        check_capsule(
            corrupted, load("manifest.json"), load("report.json"), load("comparison.json"), cache
        )


def test_cache_counter_checks_runner_records(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("cache_counter", REPORT / "cache_outcomes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = {"test": "cache counting"}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    cache = ReplayCache(tmp_path / "cache", digest(manifest))
    records = [
        ("llm", {"outcome": "response", "response": {"text": "OK"}}),
        (
            "llm",
            {
                "outcome": "structured_output_invalid",
                "error": {"type": "StructuredOutputValidationError", "message": "invalid JSON"},
                "raw_response": {"text": "YES"},
            },
        ),
        ("embedding", [1.0, 0.0]),
        ("rerank", [0.5]),
    ]
    for index, (kind, value) in enumerate(records):
        cache.call(kind, {"call": index}, lambda value=value: value)
    cache.require_clean()
    module.main(tmp_path)
    expected = {
        "manifest_sha256": digest(manifest),
        "cache_records": 4,
        "records_by_kind": {"llm": 2, "embedding": 1, "rerank": 1},
        "llm_outcomes": {"response": 1, "structured_output_invalid": 1},
        "integrity_mismatches": 0,
    }
    assert json.loads(capsys.readouterr().out) == expected
    path = next((tmp_path / "cache").glob("embedding-*.json"))
    record = json.loads(path.read_text(encoding="utf-8"))
    record["value"] = [0.0, 1.0]
    path.write_text(json.dumps(record), encoding="utf-8")
    module.main(tmp_path)
    assert json.loads(capsys.readouterr().out) == {**expected, "integrity_mismatches": 1}
