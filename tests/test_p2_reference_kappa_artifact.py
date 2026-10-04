"""Replay the published kappa of the P2 consensus to the two model references."""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from evaluation import blinded_judge as p2
from scripts import p2_reference_kappa as kappa

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / kappa.OUT
CAPSULE = ROOT / "docs/evidence/p2-model-reference-kappa.md"
LABELS = {
    "consensus": "consensus",
    "glm": "GLM",
    "sonnet": "Sonnet",
    "astra": "Astra",
    "opus": "Opus",
}
ABSOLUTE_PATH = re.compile(r"\b[A-Za-z]:[\\/](?!/)|/Users/|/home/")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def published() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def grades() -> dict[str, dict[str, list[int]]]:
    """The grades read without the calculation module, references from their ratings files."""
    report = json.loads((ROOT / kappa.P2_REPORT).read_text(encoding="utf-8"))
    sample = report["human"]["sample_case_ids"]
    result: dict[str, dict[str, list[int]]] = {}
    for judge in ("glm", "sonnet"):
        rows = p2.read_store(ROOT / f"reports/p2/replies/{judge}.jsonl")
        graded = {
            row["case_id"]: row["grades"]
            for row in rows
            if row.get("pool") == "H" and row.get("status") == "graded"
        }
        result[judge] = {case_id: graded[case_id] for case_id in sample}
    for name in ("astra", "opus"):
        ratings = json.loads(
            (ROOT / f"reports/p2/{name}-reference/ratings.json").read_text(encoding="utf-8")
        )
        assert [rating["case_id"] for rating in ratings] == sample
        result[name] = {rating["case_id"]: rating["grades"] for rating in ratings}
    result["consensus"] = {
        case_id: [
            p2.lower_median(pair)
            for pair in zip(result["glm"][case_id], result["sonnet"][case_id], strict=True)
        ]
        for case_id in sample
    }
    return result


def _replay(first: dict[str, list[int]], second: dict[str, list[int]]) -> dict[str, Any]:
    case_ids = list(first)
    assert case_ids == list(second) and len(case_ids) == 10

    def units(source: dict[str, list[int]], chosen: list[str]) -> list[int]:
        return [grade for case_id in chosen for grade in source[case_id]]

    rng = random.Random(20260925)
    draws = []
    for _ in range(10_000):
        chosen = [case_ids[rng.randrange(10)] for _ in range(10)]
        value = p2.quadratic_kappa(units(first, chosen), units(second, chosen))
        if value is not None:
            draws.append(value)
    draws.sort()
    left, right = units(first, case_ids), units(second, case_ids)
    return {
        "units": len(left),
        "quadratic_kappa": p2.quadratic_kappa(left, right),
        "ci95": [p2._percentile(draws, 0.025), p2._percentile(draws, 0.975)],
        "resamples_used": len(draws),
        "exact_agreement": sum(a == b for a, b in zip(left, right, strict=True)),
    }


def _comparisons(published: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {("consensus", name): row for name, row in published["references"].items()}
    rows[("astra", "opus")] = published["orientation"]["astra+opus"]
    for judge, by_reference in published["orientation"]["judges"].items():
        for name, row in by_reference.items():
            rows[(judge, name)] = row
    return rows


def test_artifact_is_the_calculation_over_the_pinned_inputs(published: dict[str, Any]) -> None:
    raw = ARTIFACT.read_bytes()
    assert b"\r\n" not in raw
    assert ABSOLUTE_PATH.search(raw.decode("utf-8")) is None
    assert kappa.build_report() == published

    provenance = published["provenance"]
    assert set(provenance["inputs_sha256"]) == {
        "reports/p2/p2-blinded-judge-glm+sonnet.json",
        "reports/p2/replies/glm.jsonl",
        "reports/p2/replies/sonnet.jsonl",
        "reports/p2/astra-reference/replies.jsonl",
        "reports/p2/astra-reference/summary.json",
        "reports/p2/opus-reference/replies.jsonl",
        "reports/p2/opus-reference/summary.json",
    }
    assert set(provenance["code_sha256"]) == {
        "scripts/p2_reference_kappa.py",
        "evaluation/blinded_judge.py",
    }
    for relative, digest in (provenance["inputs_sha256"] | provenance["code_sha256"]).items():
        assert _sha256(ROOT / relative) == digest, relative
    report = json.loads((ROOT / kappa.P2_REPORT).read_text(encoding="utf-8"))
    for judge in ("glm", "sonnet"):
        named = report["provenance"]["judge_routes"][judge]["reply_files"][0]
        assert named["sha256"] == provenance["inputs_sha256"][f"reports/p2/replies/{judge}.jsonl"]
    assert provenance["h_pool_sha256"] == report["provenance"]["pools"]["H"]["pool_sha256"]
    assert provenance["model_requests"] == 0
    assert published["bootstrap"]["samples"] == p2.BOOTSTRAP_SAMPLES == 10_000
    assert published["bootstrap"]["seed"] == p2.SEED == 20260925
    assert published["sample"]["case_ids"] == report["human"]["sample_case_ids"]
    assert (published["sample"]["cases"], published["sample"]["documents"]) == (10, 50)


def test_every_number_replays_without_the_calculation_module(
    published: dict[str, Any], grades: dict[str, dict[str, list[int]]]
) -> None:
    assert published["consensus"]["grades"] == grades["consensus"]
    assert published["consensus"]["excluded"] == []
    rows = _comparisons(published)
    assert len(rows) == 7
    for (first, second), row in rows.items():
        replayed = _replay(grades[first], grades[second])
        for name, value in replayed.items():
            assert row[name] == pytest.approx(value, rel=1e-12, abs=1e-15), (first, second, name)
        assert row["cases"] == 10 and row["resamples_undefined"] == 0
        assert sum(sum(cells.values()) for cells in row["cross_table"].values()) == 50
    # Published in the two reference capsules before this slice.
    assert round(rows[("astra", "opus")]["quadratic_kappa"], 4) == 0.9727
    assert round(rows[("glm", "astra")]["quadratic_kappa"], 4) == 0.8824
    assert round(rows[("sonnet", "astra")]["quadratic_kappa"], 4) == 0.8930
    assert round(rows[("glm", "opus")]["quadratic_kappa"], 4) == 0.9133
    assert round(rows[("sonnet", "opus")]["quadratic_kappa"], 4) == 0.8950


def test_registered_rule_gives_the_published_verdict(published: dict[str, Any]) -> None:
    assert published["rule"]["threshold"] == 0.7
    branches = {}
    for name in ("astra", "opus"):
        low, high = published["references"][name]["ci95"]
        branches[name] = "below" if high < 0.7 else "clears" if low >= 0.7 else "straddles"
        assert published["references"][name]["rule_branch"] == branches[name]
    assert branches == {"astra": "clears", "opus": "clears"}
    assert published["verdict"] == {
        "branch": 3,
        "ruler_status": "model-cross-checked",
        "per_reference": branches,
    }
    assert published["orientation"]["enters_rule"] is False
    assert published["references"]["astra"]["vendor"] == "OpenAI"
    assert published["references"]["opus"]["vendor"] == "Anthropic"
    assert published["references"]["astra"]["model"] == "gpt-6-astra"
    assert published["references"]["opus"]["model"] == "claude-opus-5-5"


def test_branches_are_read_in_the_registered_order() -> None:
    assert kappa.rule_branch([0.55, 0.6999]) == "below"
    assert kappa.rule_branch([0.6999, 0.9]) == "straddles"
    assert kappa.rule_branch([0.7, 0.9]) == "clears"
    assert kappa.rule_verdict({"astra": "straddles", "opus": "below"})["branch"] == 1
    assert kappa.rule_verdict({"astra": "below", "opus": "clears"})["ruler_status"] == (
        "consensus_not_used"
    )
    assert kappa.rule_verdict({"astra": "clears", "opus": "straddles"})["ruler_status"] == (
        "provisional_ruler"
    )
    assert kappa.rule_verdict({"astra": "clears", "opus": "clears"})["branch"] == 3


def test_capsule_states_the_numbers_the_rule_and_the_caveats(
    published: dict[str, Any], grades: dict[str, dict[str, list[int]]]
) -> None:
    capsule = CAPSULE.read_text(encoding="utf-8")
    flat = " ".join(capsule.split())
    assert ABSOLUTE_PATH.search(capsule) is None
    for (first, second), row in _comparisons(published).items():
        low, high = row["ci95"]
        assert (
            f"| {LABELS[first]} ↔ {LABELS[second]} | {row['quadratic_kappa']:.4f} "
            f"| [{low:.4f}, {high:.4f}] | {row['exact_agreement']}/50 |"
        ) in capsule
    for name in ("astra", "opus"):
        row = published["references"][name]
        assert f"{row['agreement_at_grade_ge_2']}/50 with {LABELS[name]}" in flat

    differing = []
    for case_id, consensus in grades["consensus"].items():
        for index, grade in enumerate(consensus):
            others = [grades[name][case_id][index] for name in ("astra", "opus")]
            if any(other != grade for other in others):
                judges = [grades[name][case_id][index] for name in ("glm", "sonnet")]
                differing.append([case_id, index + 1, *judges, grade, *others])
    table = []
    for line in capsule.splitlines():
        if line.startswith("| aircargo-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            table.append([cells[0], *(int(cell) for cell in cells[1:])])
    assert table == differing

    assert _sha256(ARTIFACT) in capsule
    for digest in (
        *published["provenance"]["inputs_sha256"].values(),
        *published["provenance"]["code_sha256"].values(),
        published["provenance"]["h_pool_sha256"],
    ):
        assert digest in capsule
    for phrase in (
        "branch 3",
        "`model-cross-checked`",
        "never `human-validated`",
        "10 000 resamples of cases",
        "seed 20260925",
        "does not enter the rule",
        # the four caveats of the task, in its order
        "cannot detect an error the models share",
        "not blind to its likely outcome",
        "was not adjusted",
        "unexpanded top-5 contexts",
        "at least 10 cases per class",
        "carries no contamination controls",
        # metrics spec, «No human annotator»
        "the reference labels are model labels",
        "inter-annotator reproducibility is not established",
        "a retest measures one model's stability only",
    ):
        assert phrase in flat, phrase
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    rows = [
        line for line in index.splitlines() if "`tests/test_p2_reference_kappa_artifact.py`" in line
    ]
    assert len(rows) == 1 and "docs/evidence/p2-model-reference-kappa.md" in rows[0]
    for name in ("astra", "opus"):
        row = published["references"][name]
        low, high = row["ci95"]
        assert (
            f"{row['quadratic_kappa']:.4f} to {LABELS[name]} (CI95 [{low:.4f}, {high:.4f}])"
        ) in rows[0]


def _copy_reference(root: Path, name: str) -> Path:
    directory = root / kappa.REFERENCES[name]["directory"]
    shutil.copytree(ROOT / kappa.REFERENCES[name]["directory"], directory)
    return directory


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_bytes(text.encode("utf-8"))


def test_reference_store_must_match_its_summary_and_the_sample(
    published: dict[str, Any], tmp_path: Path
) -> None:
    sample = published["sample"]["case_ids"]
    directory = _copy_reference(tmp_path, "astra")
    assert kappa.load_reference(tmp_path, "astra", sample)[0].keys() == set(sample)

    rows = p2.read_store(directory / "replies.jsonl")
    _write_rows(directory / "replies.jsonl", rows[:-1])
    with pytest.raises(p2.NotEvidence, match="differs from its summary"):
        kappa.load_reference(tmp_path, "astra", sample)

    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    summary["reply_store_sha256"] = _sha256(directory / "replies.jsonl")
    (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(p2.NotEvidence, match="cases differ from the P2 sample"):
        kappa.load_reference(tmp_path, "astra", sample)


def test_judge_store_must_match_the_report_and_cover_the_sample(
    published: dict[str, Any], tmp_path: Path
) -> None:
    sample = published["sample"]["case_ids"]
    relative = kappa.JUDGE_STORES["glm"]
    store = tmp_path / relative
    store.parent.mkdir(parents=True)
    rows = [row for row in p2.read_store(ROOT / relative) if row["case_id"] != sample[0]]
    _write_rows(store, rows)

    def report(digest: str, path: str = f"X:/elsewhere/{relative}") -> dict[str, Any]:
        files = [{"path": path, "sha256": digest}]
        return {"provenance": {"judge_routes": {"glm": {"reply_files": files}}}}

    with pytest.raises(p2.NotEvidence, match="differs from the P2 report"):
        kappa.load_judge(tmp_path, report("0" * 64), "glm", sample)
    with pytest.raises(p2.NotEvidence, match="does not name"):
        kappa.load_judge(
            tmp_path, report(_sha256(store), "X:/elsewhere/other.jsonl"), "glm", sample
        )
    with pytest.raises(p2.NotEvidence, match="has 0 graded rows"):
        kappa.load_judge(tmp_path, report(_sha256(store)), "glm", sample)
