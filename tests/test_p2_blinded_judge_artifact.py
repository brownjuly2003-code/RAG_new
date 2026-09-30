"""Rebuild the published P2 verdict from the stored blinded replies."""

import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

from evaluation import blinded_judge as p2
from scripts import p1_adaptive_k as p1

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/p2/p2-blinded-judge-glm+sonnet.json"
SONNET_REPORT = ROOT / "reports/p2/p2-blinded-judge-sonnet.json"
SAMPLE = ROOT / "reports/p2/human-sample.html"
STORES = {
    judge: ROOT / f"reports/p2/replies/{judge}.jsonl"
    for judge in ("glm", "mistral", "sonnet")
}
REPORT_SHA256 = "4c1e60cdad361799a291fa88d0d0c3a35675ad772630a0147615ab30d3a31e7d"
SONNET_REPORT_SHA256 = "019131aa1952258771f47eff8c379fc3135e6a339bffa31967a3a37aa87baed0"
SAMPLE_SHA256 = "1826759edf68c9e04dcb5bc7c90fa56d6e436234c8e25fcfb03df3db66f223ba"
STORE_SHA256 = {
    "glm": "aac5c00993737194b0b5beaa9ee0cebc28d0434b647997056ffc1f69606f3da9",
    "mistral": "12efbbc7b81bea561cafdcc88b737ecc0239248e5db398d750a8f4fce12a7ea1",
    "sonnet": "c66101caa83c11e3b6cfee1e3fe10743c5cc684211265daf241da8654037f4ee",
}
CODE_COMMIT = "fa9e598e5bc6446c2c50d7fb9db038f036426c6a"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def published():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_published_bytes_and_versions_are_pinned(published):
    for path, digest in (
        (REPORT, REPORT_SHA256),
        (SONNET_REPORT, SONNET_REPORT_SHA256),
        (SAMPLE, SAMPLE_SHA256),
    ):
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert b"\r\n" not in raw
    for judge, path in STORES.items():
        assert _sha256(path) == STORE_SHA256[judge]
        assert b"\r\n" not in path.read_bytes()

    earlier = json.loads(SONNET_REPORT.read_text(encoding="utf-8"))
    assert earlier["verdict"]["decision"] == "PROVISIONAL_RULER_DOES_NOT_TRACK"
    assert earlier["verdict"]["judge_count"] == 1
    assert published["schema_version"] == "p2-blinded-judge/v1.0"
    assert published["evidence_class"] == "measured"


def test_code_and_input_provenance(published):
    provenance = published["provenance"]
    code = provenance["code"]
    assert code["commit"] == CODE_COMMIT
    for relative, digest in code["files"].items():
        blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{relative}"], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == digest
        assert _sha256(ROOT / relative) == digest

    inputs = p2.load_inputs()
    assert provenance["instruction_sha256"] == p2.INSTRUCTION_SHA256
    assert provenance["label_manifest_and_approvals"] == inputs.approvals
    assert provenance["pools"]["H"]["pool_sha256"] == p1.H_POOL_SHA256
    assert provenance["pools"]["Hm"]["pool_sha256"] == p1.HM_POOL_SHA256
    assert published["control"] == {"H_top_k_5": 0.5067, "valid": True}
    assert published["bootstrap"]["samples"] == 10000
    assert published["bootstrap"]["seed"] == 20260925
    for judge, route in provenance["judge_routes"].items():
        assert route["reply_files"][0]["sha256"] == STORE_SHA256[judge]
    assert provenance["judge_routes"]["glm"]["route"] == (
        "direct z.ai /api/anthropic/v1/messages SSE"
    )


def test_grades_and_primary_verdict_replay_from_replies(published):
    inputs = p2.load_inputs()
    request_digests = {
        (case.pool, case.case_id): p2.build_request(case).sha256
        for pool in inputs.pools.values()
        for case in pool.cases
    }
    stored = p2.merge_stores(list(STORES.values()), request_digests)
    grades, info = p2._current_grades(inputs, stored)
    assert {judge: sum(row["status"] == "graded" for row in p2.read_store(path))
            for judge, path in STORES.items()} == {"glm": 115, "mistral": 0, "sonnet": 115}
    assert info["mistral"]["pools"]["H"]["unavailable"]["code"] == "zero_limit"

    for pool_name, expected_cases in (("H", 100), ("Hm", 15)):
        pool = inputs.pools[pool_name]
        for judge in ("glm", "sonnet"):
            assert len(grades[pool_name][judge]) == expected_cases
        consensus, excluded = p2.consensus_grades(
            [case.case_id for case in pool.cases],
            {judge: grades[pool_name][judge] for judge in ("glm", "sonnet")},
        )
        assert excluded == []
        assert len(consensus) == expected_cases
        assert published["metrics"][pool_name]["consensus"]["graded_cases"] == expected_cases
        for arm in ("top_k_5", "rel_0.2", "held_out", "oracle_best_prefix"):
            if arm in inputs.arms[pool_name]:
                actual = p2.arm_metrics(consensus, inputs.arms[pool_name][arm])
                expected = published["metrics"][pool_name]["consensus"]["arms"][arm]["metrics"]
                assert actual.keys() == expected.keys()
                for name, value in expected.items():
                    if isinstance(value, float):
                        assert actual[name] == pytest.approx(value, rel=1e-12, abs=1e-15)
                    else:
                        assert actual[name] == value
        if pool_name == "H":
            h_consensus = consensus

    case_ids = sorted(h_consensus)
    pool = inputs.pools["H"]
    ruler = [pool.ruler_per_case[case_id] for case_id in case_ids]
    # Preserve the publication runtime's compensated sums for rank ties on Python 3.11.
    weights = [1 / (index + 1) for index in range(5)]
    judged = [
        math.fsum(grade / 3 * weight for grade, weight in
                  zip(h_consensus[case_id], weights, strict=True)) / math.fsum(weights)
        for case_id in case_ids
    ]
    for case_id, score in zip(case_ids, judged, strict=True):
        assert p2._case_metrics(h_consensus[case_id], 5)["ruler_shaped_judged_precision"] == (
            pytest.approx(score, rel=1e-12, abs=1e-15)
        )
    tau = p2.kendall_tau_b(ruler, judged)
    interval = p2.bootstrap_tau_ci(ruler, judged)
    alpha, units = p2._alpha_for_consensus(
        {judge: grades["H"][judge] for judge in ("glm", "sonnet")},
        ("glm", "sonnet"),
        [case.case_id for case in pool.cases],
    )
    assert units == 500
    assert alpha == pytest.approx(published["verdict"]["ordinal_krippendorff_alpha"])
    assert tau == pytest.approx(published["h_agreement"]["per_case"]["tau_b"])
    assert interval == pytest.approx(published["verdict"]["per_case_tau_b_ci95"])
    assert p2.verdict(interval, judge_count=2, alpha=alpha, human_kappa=None) == (
        published["verdict"]["decision"]
    )
    assert published["verdict"]["decision"] == "RULER_DOES_NOT_TRACK"
    assert published["human"]["grades"] is None
    assert published["human"]["sample_case_ids"] == [
        case.case_id for case in p2.draw_human_sample(pool.cases, pool.ruler_per_case)
    ]
