"""Offline replay of the committed P1 adaptive-k report.

The whole report is rebuilt from committed inputs. Only the live-code file digests are
pinned separately, against the git blobs at CODE_COMMIT.
"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import p1_adaptive_k as p1
from scripts import rerank_score_capture
from scripts.ab_context_precision import (
    DEFAULT_DATASET_PATH,
    DEFAULT_LABEL_MANIFEST_PATH,
    DEFAULT_SIDECAR_PATH,
)
from tests.capsule_prose import capsule_defects, numeric_claims, prose_lines

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/p1/p1-adaptive-k.json"
CAPSULE = ROOT / "docs/evidence/p1-adaptive-k.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
H_SCORES = ROOT / "evaluation/p1-511f3f9-H-rerank-scores.json"
HM_SCORES = ROOT / "evaluation/p1-511f3f9-Hm-rerank-scores.json"
REPORT_SHA256 = "30e55459e1787c134215597d5672293ec4b32ef051c8bc96e8d289dfa50cb65d"
CODE_COMMIT = "4999ea3a5665155648858ce226ff18d5b27ab0c5"
SCORES_CODE_COMMIT = "511f3f90d9bef29d8f1b393b94ba12324eef9937"
H_SCORES_SHA256 = "3ced6d0259fdee8da1d4cbf7dcb1cea55fed7e4379003d23f327a25e331bb50b"
HM_SCORES_SHA256 = "6789200b8a112d076ef7e7999cf8c261747131cab609dbd334abfc51dc06c03d"
RERANKER = "BAAI/bge-reranker-v2-m3"
DECISION = "NO_SHIP"


@pytest.fixture(scope="module")
def published():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rebuilt(published):
    """The report bootstraps 10000 resamples, so it is built once."""

    def code_digests(paths):
        assert paths == p1.CODE_PATHS
        return dict(published["provenance"]["code"]["files"])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(p1, "_git_commit", lambda: {"commit": CODE_COMMIT, "tree_clean": True})
        mp.setattr(p1, "_code_digests", code_digests)
        return p1.build_report(h_scores=H_SCORES, hm_scores=HM_SCORES)


def test_report_bytes_are_pinned(published):
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")

    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    assert json.loads(raw, parse_constant=reject_constant) == published


def test_score_artifacts_are_pinned(published):
    for label, path, digest, count, pool_digest in (
        ("H", H_SCORES, H_SCORES_SHA256, 100, p1.H_POOL_SHA256),
        ("Hm", HM_SCORES, HM_SCORES_SHA256, 15, p1.HM_POOL_SHA256),
    ):
        raw = path.read_bytes()
        artifact = json.loads(raw)
        assert hashlib.sha256(raw).hexdigest() == digest
        assert artifact["schema_version"] == rerank_score_capture.SCHEMA_VERSION
        assert artifact["complete"] is True
        assert artifact["cases_total"] == artifact["cases_scored"] == count
        parity = artifact["parity"]
        assert parity["order_matches"] == parity["top_k_matches"] == count
        assert parity["mismatched_case_ids"] == []
        provenance = artifact["provenance"]
        assert provenance["pool_sha256"] == pool_digest
        assert provenance["code"]["commit"] == SCORES_CODE_COMMIT
        assert provenance["reranker"]["model"] == RERANKER == p1.RERANKER_MODEL
        assert len(artifact["per_case"]) == count
        assert published["provenance"]["pools"][label]["scores_sha256"] == digest


def test_rebuilt_report_equals_the_published_json(rebuilt, published):
    assert rebuilt == published


def test_code_digests_are_the_blobs_at_the_measurement_commit(published):
    code = published["provenance"]["code"]
    assert code["commit"] == CODE_COMMIT
    assert code["tree_clean"] is True
    files = code["files"]
    assert list(files) == list(p1.CODE_PATHS)
    for rel, digest in files.items():
        blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{rel}"], cwd=ROOT)
        assert b"\r\n" not in blob, rel
        assert hashlib.sha256(blob).hexdigest() == digest, rel


def test_control_reproduces_the_published_h_baseline(published):
    h = published["h"]
    assert h["control_reproduces_published"] is True
    assert published["config"]["published_h"] == p1.PUBLISHED_H
    control = next(cell for cell in h["cells"] if cell["name"] == "top_k_5")
    aggregate = control["aggregate"]
    for key, value in p1.PUBLISHED_H.items():
        assert aggregate[key] == value
    assert aggregate["num_cases"] == 100
    assert aggregate["mean_kept"] == 5.0


def test_verdict_follows_from_the_cross_validated_rows(published):
    pool = p1.evaluate_pool(
        archive=p1.H_ARCHIVE,
        pool_sha256=p1.H_POOL_SHA256,
        scores_path=H_SCORES,
        dataset_path=DEFAULT_DATASET_PATH,
        sidecar_path=DEFAULT_SIDECAR_PATH,
        label_manifest_path=DEFAULT_LABEL_MANIFEST_PATH,
        bootstrap_samples=10,
        seed=p1.BOOTSTRAP_SEED,
    )
    cv = published["h"]["cross_validation"]
    cell_by_fold = {choice["fold"]: choice["cell"] for choice in cv["choices"]}
    rows = {
        name: {row["case_id"]: row for row in cell_rows}
        for name, cell_rows in pool["per_cell"].items()
    }
    assert sorted(cell_by_fold) == [0, 1, 2, 3, 4]
    assert all(cell in published["config"]["primary"] for cell in cell_by_fold.values())
    held_out = cv["per_case"]
    control = pool["per_cell"]["top_k_5"]
    assert [entry["case_id"] for entry in held_out] == [row["case_id"] for row in control]
    for entry in held_out:
        assert entry["cell"] == cell_by_fold[entry["fold"]]
        assert entry["kept"] == rows[entry["cell"]][entry["case_id"]]["kept"]
    selected = [rows[entry["cell"]][entry["case_id"]] for entry in held_out]
    flags = p1.verdict_flags(selected, control)
    keys = ("precision_gate_met", "h_relative_constraints_met", "review_floor_met")
    assert flags == {key: published["verdict"][key] for key in keys}
    assert published["h"]["control_reproduces_published"] is True
    expected = (
        "SHIP_CANDIDATE"
        if flags["precision_gate_met"] and flags["h_relative_constraints_met"]
        else "NO_SHIP"
    )
    assert published["verdict"]["decision"] == DECISION == expected


def test_capsule_embeds_the_table_and_the_digests(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    assert p1.render_table(published) in capsule
    assert "a67f517" in capsule
    for digest in (
        REPORT_SHA256,
        CODE_COMMIT,
        SCORES_CODE_COMMIT,
        H_SCORES_SHA256,
        HM_SCORES_SHA256,
        p1.H_POOL_SHA256,
        p1.HM_POOL_SHA256,
    ):
        assert digest in capsule
    for phrase in (DECISION, "not deployable", "optimistic", "pre-registered", "agent_labelled"):
        assert phrase in capsule


def _report_numbers(published) -> tuple[list[float], set[int]]:
    decimals = []
    integers = set()

    def collect(value):
        if isinstance(value, dict):
            # The spec's "capsule states a number" scenario includes these named list counts.
            if "lost_keyword_cases" in value and "full_regressions" in value:
                integers.add(len(value["lost_keyword_cases"]))
                integers.add(len(value["full_regressions"]))
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, float):
            decimals.append(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            integers.add(value)

    collect(published)
    return decimals, integers


def test_capsule_quotes_only_report_numbers(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert capsule_defects(capsule, decimals=decimals, integers=integers) == []
    claims = numeric_claims("\n".join(prose_lines(capsule)))
    assert sum("." in claim for claim in claims) >= 8


def test_capsule_number_check_rejects_a_count_the_report_does_not_carry(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert "with 22 FULL regressions" in capsule
    unreported = next(value for value in range(23, max(integers) + 2) if value not in integers)
    assert unreported > 22 and unreported not in integers
    changed = capsule.replace("with 22 FULL regressions", f"with {unreported} FULL regressions", 1)
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any(f"prose quotes {unreported}," in defect for defect in defects)

    other_list_count = len(published["config"]["cells"])
    assert other_list_count not in integers
    changed = capsule + f"\nThe unrelated list has {other_list_count} entries.\n"
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any(f"prose quotes {other_list_count}," in defect for defect in defects)


def test_evidence_index_row_points_at_the_capsule_report_and_test():
    rows = [
        line
        for line in INDEX.read_text(encoding="utf-8").splitlines()
        if "docs/evidence/p1-adaptive-k.md" in line
    ]
    assert len(rows) == 1
    row = rows[0]
    assert "reports/p1/p1-adaptive-k.json" in row
    assert "tests/test_p1_adaptive_k_artifact.py" in row
    assert DECISION in row
