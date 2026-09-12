"""Same-pool controls must expose coverage losses, not just a higher mean."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from scripts import gr1b_controls as controls
from tests.test_gr_bucket_baseline import _mark_as_g1_pool, _write_fixture


def _inputs(tmp_path: Path) -> dict:
    paths = _mark_as_g1_pool(_write_fixture(tmp_path))
    rows = json.loads(paths["pool"].read_text(encoding="utf-8"))
    for row in rows:
        row["reranked_cands"] = row["cands"] + ["unrelated"] * 3
        row["prerank_cands"] = list(reversed(row["reranked_cands"]))
    archive = tmp_path / "pool.json.gz"
    archive.write_bytes(gzip.compress(json.dumps(rows).encode(), mtime=0))
    return dict(
        archive_path=archive, dataset_path=paths["dataset"],
        sidecar_path=paths["sidecar"], label_manifest_path=paths["label_manifest"],
        corpus_manifest_path=paths["corpus_manifest"], expected_cases=4,
        bootstrap_samples=100, code_commit="0" * 40,
    )


def test_controls_use_original_rankings_and_keep_every_case(tmp_path: Path) -> None:
    kwargs = _inputs(tmp_path)
    report = controls.build_controls_report(**kwargs)
    arms = {arm["name"]: arm for arm in report["arms"]}
    assert list(arms) == ["g1", *(f"reranked_top_{k}" for k in range(1, 6)), "prerank_top_5"]
    assert all(arm["aggregate"]["num_cases"] == 4 for arm in arms.values())
    assert arms["reranked_top_1"]["per_case"][1]["context_recall"] == 0.5
    assert arms["g1"]["per_case"][1]["context_recall"] == 1.0
    assert arms["reranked_top_1"]["comparison"]["full_regressions"] == ["syn-two"]
    assert arms["reranked_top_1"]["comparison"]["lost_keyword_cases"] == ["syn-two"]
    assert arms["prerank_top_5"]["aggregate"]["context_precision"] < arms["g1"]["aggregate"]["context_precision"]
    assert report == controls.build_controls_report(**kwargs)


def test_character_cap_applies_before_scoring_and_fact_comparison(tmp_path: Path) -> None:
    report = controls.build_controls_report(**_inputs(tmp_path), context_chars=1)
    for arm in report["arms"]:
        assert all(row["context_chars"] <= 1 for row in arm["per_case"])
        assert all(row["context_recall"] == 0 for row in arm["per_case"])


@pytest.mark.parametrize("field", ["reranked_cands", "prerank_cands"])
def test_missing_or_short_original_ranking_fails_closed(tmp_path: Path, field: str) -> None:
    kwargs = _inputs(tmp_path)
    archive = kwargs["archive_path"]
    rows = json.loads(gzip.decompress(archive.read_bytes()))
    rows[0][field] = ["only one"]
    archive.write_bytes(gzip.compress(json.dumps(rows).encode(), mtime=0))
    with pytest.raises(ValueError, match=field):
        controls.build_controls_report(**kwargs)


def test_paired_comparison_matches_ids_and_detects_fact_swaps() -> None:
    baseline = [
        dict(case_id="a", context_precision=0.5, context_recall=0.5, kw_status="PART", matched_keywords=["x"]),
        dict(case_id="b", context_precision=1.0, context_recall=1.0, kw_status="FULL", matched_keywords=["z"]),
    ]
    arm = [dict(baseline[1]), dict(baseline[0], matched_keywords=["y"])]
    result = controls.paired_comparison(arm, baseline, samples=100, seed=42)
    assert result["precision_delta"] == 0
    assert result["precision_delta_ci95"] == [0, 0]
    assert result["recall_delta_ci95"] == [0, 0]
    assert result["lost_keyword_cases"] == ["a"]
    assert result["full_regressions"] == []
    arm[1]["context_precision"] = 0
    arm[0]["context_precision"] = 0.5
    result = controls.paired_comparison(arm, baseline, samples=100, seed=42)
    assert result["precision_delta_ci95"] == [-0.5, -0.5]


@pytest.mark.parametrize("oracle", [False, True])
def test_cli_selects_controls_mode_without_other_work(tmp_path: Path, oracle: bool) -> None:
    from scripts.ab_context_precision import main

    kwargs = _inputs(tmp_path)
    output = tmp_path / "controls.json"
    assert main([
        "--structural-oracle" if oracle else "--structural-controls",
        "--controls-archive", str(kwargs["archive_path"]),
        "--oracle-report" if oracle else "--controls-report", str(output), "--expected-cases", "4",
        "--dataset", str(kwargs["dataset_path"]), "--sidecar", str(kwargs["sidecar_path"]),
        "--label-manifest", str(kwargs["label_manifest_path"]),
        "--corpus-manifest", str(kwargs["corpus_manifest_path"]),
    ]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    if oracle:
        assert report["kind"] == "oracle_diagnostic_not_deployable"
    else:
        assert report["arms"][0]["name"] == "g1"


def test_published_controls_reproduce_every_case_and_interval() -> None:
    report = json.loads(controls.DEFAULT_REPORT.read_text(encoding="utf-8"))
    rebuilt = controls.build_controls_report()
    assert rebuilt["arms"] == report["arms"]
    for field in ("archive_sha256", "pool_sha256", "dataset_sha256", "label_sidecar_sha256",
                  "label_manifest_sha256", "corpus", "config"):
        assert rebuilt["provenance"][field] == report["provenance"][field]
    arms = {arm["name"]: arm for arm in report["arms"]}
    assert arms["g1"]["aggregate"]["context_recall"] == 0.92
    assert arms["reranked_top_1"]["aggregate"]["context_precision"] == 0.6403
    assert len(arms["reranked_top_1"]["comparison"]["full_regressions"]) == 23
    capsule = (controls.PROJECT_ROOT / "docs/evidence/gr1b-same-pool-controls.md").read_text(encoding="utf-8")
    assert controls.render_controls_table(report).strip() in capsule


def test_oracle_preserves_keyword_identity_and_source_order() -> None:
    result = controls.best_safe_subset(
        query="alpha beta", keywords=["alpha", "beta"],
        candidates=["alpha", "noise", "beta", "noise", "noise"],
        baseline_texts=["alpha", "beta"], context_chars=6000,
    )
    assert result["candidate_indices"] == [0, 2]
    assert result["context_precision"] == 0.5
    assert result["context_recall"] == 1.0
    assert result["kw_status"] == "FULL"
    assert result["subsets_evaluated"] == 31


def test_oracle_cannot_recover_expansion_only_fact_or_truncated_fact() -> None:
    assert controls.best_safe_subset(
        query="alpha beta", keywords=["alpha", "beta"],
        candidates=["alpha", "noise", "noise", "noise", "noise"],
        baseline_texts=["alpha beta"], context_chars=6000,
    ) is None
    assert controls.best_safe_subset(
        query="alpha beta", keywords=["alpha", "beta"],
        candidates=["alpha beta", "noise", "noise", "noise", "noise"],
        baseline_texts=["alpha beta"], context_chars=5,
    ) is None


def test_oracle_excludes_sixth_candidate_and_remains_diagnostic(tmp_path: Path) -> None:
    assert controls.best_safe_subset(
        query="beta", keywords=["beta"],
        candidates=["noise"] * 5 + ["beta"], baseline_texts=["beta"], context_chars=6000,
    ) is None
    report = controls.build_oracle_report(**_inputs(tmp_path))
    assert report["kind"] == "oracle_diagnostic_not_deployable"
    assert report["all_cases_with_g1_fallback"]["num_cases"] == 4
    assert all(row["lost_keywords"] == [] for row in report["per_case"])
