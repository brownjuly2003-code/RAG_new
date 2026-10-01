"""Reproduce the single-arm P2 ruler and every capsule table number."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation import semantic_ruler as ruler

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "evaluation/semantic-ruler-p2-baseline.json"
CAPSULE = ROOT / "docs/evidence/semantic-ruler-p2-baseline.md"


@pytest.fixture(scope="module")
def baseline():
    return ruler.build_p2_baseline()


def test_artifact_reproduces_p2_and_capsule(baseline):
    published = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for key in baseline:
        if key != "provenance":
            assert published[key] == baseline[key]
    for key in ("p2_report_sha256", "pools", "reply_files"):
        assert published["provenance"][key] == baseline["provenance"][key]
    text = CAPSULE.read_text(encoding="utf-8")
    assert published["config"]["fact_matcher_version"] == ruler.FACT_MATCHER_VERSION
    assert f"version is `{ruler.FACT_MATCHER_VERSION}`" in text
    rows = re.findall(
        r"^\| (H|Hm) \| `(\w+)` \| ([^|]+) \| ([^|]+) \| (\d+) \| (\d+) \|$", text, re.M
    )
    assert len(rows) == 8
    for pool, metric, point, interval, n, excluded in rows:
        summary = published["pools"][pool]["metrics"][metric]
        assert float(point) == pytest.approx(summary["point"], abs=0.0000005)
        assert [float(v) for v in interval.strip().strip("[]").split(",")] == pytest.approx(
            summary["ci95"], abs=0.0000005
        )
        assert int(n) == summary["n"]
        assert int(excluded) == summary["excluded"]
    assert published["provisional_ruler"] is True
    assert published["pools"]["H"]["cluster_unit"]["count"] == 45
    assert published["pools"]["Hm"]["cluster_unit"]["count"] == 3
    assert published["pools"]["H"]["case_count"] == 100
    assert published["pools"]["Hm"]["case_count"] == 15
    for pool in published["pools"].values():
        for metric in ("evidence_recall_pool", "all_evidence_coverage", "fact_coverage"):
            assert pool["metrics"][metric]["point"] == "N/A"
        assert pool["metrics"]["precision_at_5"] == pool["metrics"]["sent_precision"]
    assert "NOT the production-expansion path" in text
    assert "provisional, replaced by the 1.3a family register" in text
    for name, pool in published["provenance"]["pools"].items():
        assert pool["pool_sha256"] in text
        assert pool["dataset_sha256"] in text
    assert str(published["config"]["seed"]) in text
    assert published["provenance"]["code_commit"] in text


def test_precision_points_match_original_p2_report(baseline):
    original = json.loads(
        (ROOT / "reports/p2/p2-blinded-judge-glm+sonnet.json").read_text(encoding="utf-8")
    )
    for name, pool in baseline["pools"].items():
        expected = original["metrics"][name]["consensus"]["arms"]["top_k_5"]["metrics"]
        assert pool["metrics"]["precision_at_5"]["point"] == expected["judged_precision"]
        assert pool["case_count"] == expected["graded_cases"]


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=60)


def _publishing_commit():
    """The commit that added the artifact, or None while it is uncommitted."""
    found = _git(
        "log", "--format=%H", "--diff-filter=A", "--", "evaluation/semantic-ruler-p2-baseline.json"
    )
    commits = found.stdout.decode().split()
    return commits[-1] if found.returncode == 0 and commits else None


def test_published_code_digests_describe_the_publishing_code():
    """Recorded digests name the code that built the artifact, not the live tree."""
    published = json.loads(ARTIFACT.read_text(encoding="utf-8"))["provenance"]
    if _git("rev-parse", "--is-shallow-repository").stdout.decode().strip() == "true":
        pytest.skip("shallow clone: the publishing commit may be unreachable")
    commit = _publishing_commit()
    for name, digest in published["code_files"].items():
        if commit is None:
            blob = (ROOT / name).read_bytes()
        else:
            shown = _git("show", f"{commit}:{name}")
            assert shown.returncode == 0, shown.stderr
            blob = shown.stdout
        assert hashlib.sha256(blob).hexdigest() == digest, name


def test_provenance_code_and_pinned_report(baseline):
    provenance = baseline["provenance"]
    assert (
        provenance["code_commit"]
        == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    )
    assert isinstance(provenance["tree_clean"], bool)
    assert (
        provenance["p2_report_sha256"]
        == "4c1e60cdad361799a291fa88d0d0c3a35675ad772630a0147615ab30d3a31e7d"
    )
    assert baseline["config"]["resamples"] == 10000


def test_cli_reproduces_artifact(tmp_path, baseline):
    output = tmp_path / "baseline.json"
    result = subprocess.run(
        [sys.executable, "-m", "evaluation.semantic_ruler", "p2-baseline", "--out", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == baseline
