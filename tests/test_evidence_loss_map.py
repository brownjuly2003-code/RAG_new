"""Re-derive the archive map, capsule numbers and development-ledger pins."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import evidence_loss_map as loss_map
from scripts.ab_remote_contextual import _kw_status

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / loss_map.ARTIFACT


@pytest.fixture(scope="module")
def published():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rebuilt():
    return loss_map.build_report()


def test_archive_artifact_and_every_capsule_number_reproduce(published, rebuilt):
    for key in published:
        if key != "provenance":
            assert published[key] == rebuilt[key], key
    for key in published["provenance"]:
        if key not in ("code_sha", "tree_clean", "code_files"):
            assert published["provenance"][key] == rebuilt["provenance"][key], key
    # Full rendering equality checks every number, denominator, case and hash,
    # including prose claims, rather than a permissive subset of table cells.
    assert (ROOT / loss_map.CAPSULE).read_text(encoding="utf-8") == loss_map.render_capsule(
        published
    )


def test_harness_matcher_and_first_observation_contract(published):
    terms = ["temperature_range", "CUSTOMS HOLD", "ручную проверку"]
    text = ["Temperature range; customs hold; ручную проверку"]
    assert loss_map._hits(terms, text) == ["CUSTOMS HOLD", "ручную проверку"]
    assert _kw_status(terms, text) == "PART"
    for lane in published["maps"].values():
        rows = lane["per_case"]
        assert len(rows) == len({row["case_id"] for row in rows}) == 100
        assert sum(len(row["terms"]) for row in rows) == 200
        for row in rows:
            assert row["status"]["initial_pool"] == "not observable"
            assert row["first_observed_loss"] == min(
                (term["first_observed_loss"] for term in row["terms"]),
                key=loss_map.LOSS_ORDER.index,
            )
            for term in row["terms"]:
                presence = term["presence"]
                assert presence["initial_pool"] is None
                expected = (
                    "index_absent_proxy"
                    if not presence["index"]
                    else "index_to_after_caps_unknown"
                    if not presence["after_caps_dedup"]
                    else "pool_to_sent_unknown"
                    if not presence["sent_context"]
                    else "no_observed_loss"
                )
                assert term["first_observed_loss"] == expected
                assert term["index_witness"] is not None
        for stratum in ("summary", "ru_to_en"):
            summary = lane[stratum]
            assert sum(summary["first_loss_cases"].values()) == summary["case_denominator"]
            assert sum(summary["first_loss_terms"].values()) == summary["term_denominator"]
            assert summary["stages"]["initial_pool"]["cases_observed"] == 0
            assert summary["stages"]["initial_pool"]["terms_missing"] is None
    assert published["index_stage_losses"] == []
    assert published["label_problem_candidates"] == []
    assert published["maps"]["hybrid"]["official_lexical"]["context_precision"] == 0.5067
    assert published["maps"]["hybrid"]["official_lexical"]["context_recall"] == 0.9050
    assert published["provenance"]["campaign_baseline"].startswith("NOT_EVIDENCE")


def test_g3_does_not_attribute_selection_or_marginals_to_expansion(published):
    for arm in published["g3"]["p1b_archived_arms"].values():
        assert arm["case_denominator"] == arm["uncapped"]["num_cases"] == 100
        assert arm["expansion_only_term_losses"] == "not observable"
        assert arm["cap_only_term_losses"] == "not observable"
    for row in published["g3"]["evaluation_cap_raw_terms"].values():
        assert row["lost_terms"] == sum(len(case["terms"]) for case in row["losses"])
        assert row["lost_cases"] == len(row["losses"])
        assert row["gained_terms"] == 0


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=60)


def test_code_digests_pin_publishing_commit_with_worktree_fallback(published):
    if _git("rev-parse", "--is-shallow-repository").stdout.decode().strip() == "true":
        pytest.skip("shallow clone: artifact publishing commit may be unreachable")
    result = _git("log", "--format=%H", "--diff-filter=A", "--", loss_map.ARTIFACT)
    assert result.returncode == 0, result.stderr
    commits = result.stdout.decode().split()
    commit = commits[-1] if commits else None
    for name, digest in published["provenance"]["code_files"].items():
        if commit is None:
            blob = (ROOT / name).read_bytes()
        else:
            shown = _git("show", f"{commit}:{name}")
            assert shown.returncode == 0, shown.stderr
            blob = shown.stdout
        assert hashlib.sha256(blob).hexdigest() == digest, name
    assert len(published["provenance"]["code_sha"]) == 40
    assert isinstance(published["provenance"]["tree_clean"], bool)


def test_ledger_registers_this_artifact_and_h_families(published):
    rows = [
        json.loads(line)
        for line in (ROOT / "evaluation/dev_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    first = rows[0]
    assert first["entry"] == 1
    assert first["date"] == published["date"]
    assert first["slice"] == published["slice"]
    assert first["config_sha256"] == published["config_sha256"]
    assert first["artifact"] == loss_map.ARTIFACT
    assert first["artifact_sha256"] == hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
    assert first["families_touched"] == ["H"]


def test_cli_is_deterministic_in_temp_dir(tmp_path, rebuilt):
    output = tmp_path / "map.json"
    capsule = tmp_path / "map.md"
    ledger = tmp_path / "ledger.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.evidence_loss_map",
            "--out",
            str(output),
            "--capsule",
            str(capsule),
            "--ledger",
            str(ledger),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    derived = json.loads(output.read_text(encoding="utf-8"))
    assert derived == rebuilt
    assert capsule.read_text(encoding="utf-8") == loss_map.render_capsule(derived)
    assert (
        json.loads(ledger.read_text(encoding="utf-8"))["artifact_sha256"]
        == hashlib.sha256(output.read_bytes()).hexdigest()
    )
