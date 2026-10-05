"""Minimums of the flags of plan step 1.3d: their numbers, what is counted, what is read.

No model and no network. The counts are checked on the verified pilot set of the repository
and on cases written here; the verified sets of rubric v3 are files in a temporary directory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import devset
from evaluation import devset_minimums as m

DEVELOPMENT = {"ru_to_en": 12, "numeric": 12, "traps": 12}
HOLDOUT = {"ru_to_en": 13, "numeric": 13, "traps": 13, "safety_critical": 7}
PILOT_TRAPS = {
    "conflicting_documents": 1,
    "dangerous_goods": 1,
    "false_premise": 3,
    "out_of_corpus": 1,
    "outdated_rule": 2,
}


def case(
    case_id: str,
    *,
    trap: str | None = None,
    ru_to_en: bool = False,
    numeric: bool = False,
    safety: bool = False,
    spans: int = 0,
    unverified: bool = False,
) -> dict[str, Any]:
    """What the counts read of a verified case."""
    return {
        "case_id": case_id,
        "trap_type": trap,
        "flags": {
            "ru_to_en": ru_to_en,
            "numeric": numeric,
            "safety_critical": safety,
            "adversarial_unanswerable": bool(trap),
        },
        "evidence_spans": [{"span_id": f"{case_id}-E{number + 1}"} for number in range(spans)],
        "authority_unverified": unverified,
    }


def write_set(
    directory: Path,
    name: str,
    cases: list[dict[str, Any]],
    *,
    complete: bool = True,
    sha256: str | None = None,
) -> None:
    verified, register = m.set_paths(name, directory)
    data = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in cases).encode("utf-8")
    verified.write_bytes(data)
    named = {"verified_set": sha256 or hashlib.sha256(data).hexdigest()}
    register.write_text(json.dumps({"complete": complete, "sha256": named}), encoding="utf-8")


def split_file(directory: Path) -> None:
    sizes = {"development": {"cases": 60}, "holdout": {"cases": 64}}
    (directory / "devset_split.json").write_text(json.dumps({"splits": sizes}), encoding="utf-8")


def pilot() -> list[dict[str, Any]]:
    state, cases = m.read_set("pilot", m.EVALUATION)
    assert state == "complete"
    return cases


# --- the numbers ---------------------------------------------------------------------------


def test_the_minimums_are_the_plans_numbers_scaled_to_the_registered_size_and_rounded_up() -> None:
    registered = json.loads((m.EVALUATION / "devset_split.json").read_bytes())["splits"]
    sizes = {split: registered[split]["cases"] for split in m.SETS}
    assert sizes == {"development": 60, "holdout": 64}
    assert m.minimums("development", sizes["development"]) == DEVELOPMENT
    assert m.minimums("holdout", sizes["holdout"]) == HOLDOUT
    # At its reference size a split has the numbers of the plan.
    for split, size in m.REFERENCE_SIZE.items():
        assert m.minimums(split, size) == m.PLAN_MINIMUMS[split]
    assert m.minimums("holdout", 1) == dict.fromkeys(HOLDOUT, 1)
    assert m.minimums("holdout", 51)["safety_critical"] == 6
    # Development has no safety-critical minimum: the plan gives one for the holdout alone.
    assert "safety_critical" not in m.minimums("development", 60)


# --- the counts ----------------------------------------------------------------------------


def test_the_counts_of_the_verified_pilot_set() -> None:
    counted = m.counts(pilot())
    assert counted == {
        "cases": 30,
        "ru_to_en": 10,
        "numeric": 9,
        "traps": 8,
        "trap_types": PILOT_TRAPS,
        # Three cases carry the flag, and the label of one quotes a rule of the corpus.
        "safety_critical": 1,
        "safety_critical_flagged": 3,
        "safety_critical_authority_confirmed": 3,
    }
    assert set(counted["trap_types"]) == devset.TRAPS
    assert m.unmet(DEVELOPMENT, counted) == [
        "ru_to_en: 10 of 12",
        "numeric: 9 of 12",
        "traps: 8 of 12",
    ]


def test_a_trap_is_a_case_with_a_trap_type_and_each_type_is_counted() -> None:
    cases = [
        case("A-01", trap="false_premise"),
        case("A-02", trap="false_premise", numeric=True),
        case("A-03", trap="dangerous_goods", safety=True),
        # A refusal without a trap type is no trap, whatever its flag says.
        {**case("A-04"), "flags": {**case("A-04")["flags"], "adversarial_unanswerable": True}},
        case("A-05", ru_to_en=True, numeric=True),
    ]
    counted = m.counts(cases)
    assert (counted["cases"], counted["traps"]) == (5, 3)
    assert counted["trap_types"] == {
        "conflicting_documents": 0,
        "dangerous_goods": 1,
        "false_premise": 2,
        "out_of_corpus": 0,
        "outdated_rule": 0,
    }
    assert (counted["ru_to_en"], counted["numeric"]) == (1, 2)
    # The number of traps is met and three of the five types have no case.
    assert m.unmet({"traps": 3}, counted) == [
        "trap types without a case: conflicting_documents, out_of_corpus, outdated_rule"
    ]
    # A split that is asked for no traps is not asked for their types.
    assert m.unmet({"numeric": 2}, counted) == []


def test_the_safety_critical_count_that_decides_needs_a_span_and_a_confirmed_authority() -> None:
    cases = [
        case("S-01", safety=True, spans=2),
        # No span: no rule of the corpus states the behaviour word for word.
        case("S-02", safety=True, trap="dangerous_goods"),
        case("S-03", safety=True, spans=1, unverified=True, trap="false_premise"),
        case("S-04", spans=1, unverified=True, numeric=True),
    ]
    counted = m.counts(cases)
    assert (
        counted["safety_critical"],
        counted["safety_critical_flagged"],
        counted["safety_critical_authority_confirmed"],
    ) == (1, 3, 2)
    # A case outside this count stays a case, a trap, a quantity.
    assert (counted["cases"], counted["traps"], counted["numeric"]) == (4, 2, 1)
    # The minimum is held against the count that decides, not against a wider one.
    assert m.unmet({"safety_critical": 2}, counted) == ["safety_critical: 1 of 2"]
    assert m.unmet({"safety_critical": 1}, counted) == []


# --- the sets ------------------------------------------------------------------------------


def test_a_set_is_counted_only_when_its_verification_is_complete(tmp_path: Path) -> None:
    assert m.set_paths("development-replacements", tmp_path) == (
        tmp_path / "devset_development_replacements_verified.jsonl",
        tmp_path / "devset_development_replacements_label_checks.json",
    )
    assert m.read_set("pilot-v3", tmp_path) == ("absent", [])
    cases = [case("P-01", numeric=True), case("P-02", trap="out_of_corpus")]
    write_set(tmp_path, "pilot-v3", cases, complete=False)
    assert m.read_set("pilot-v3", tmp_path) == ("incomplete", [])
    write_set(tmp_path, "pilot-v3", cases)
    assert m.read_set("pilot-v3", tmp_path) == ("complete", cases)
    write_set(tmp_path, "pilot-v3", cases, sha256="0" * 64)
    with pytest.raises(ValueError, match="the verified file of pilot-v3 is not the one its reg"):
        m.read_set("pilot-v3", tmp_path)


def test_a_split_is_reported_over_its_sets_together(tmp_path: Path) -> None:
    split_file(tmp_path)
    empty = m.counts([])
    assert m.report("development", tmp_path) == {
        "split": "development",
        "registered_size": 60,
        "reference_size": 60,
        "sets": dict.fromkeys(m.SETS["development"], "absent"),
        "minimums": DEVELOPMENT,
        "counts": empty,
        "unmet": [
            "ru_to_en: 0 of 12",
            "numeric: 0 of 12",
            "traps: 0 of 12",
            "trap types without a case: " + ", ".join(sorted(devset.TRAPS)),
        ],
    }
    first = [case("P-01", numeric=True), case("P-02", trap="out_of_corpus")]
    second = [case("DV-01", ru_to_en=True), case("DV-02", trap="false_premise", numeric=True)]
    later = [case("DV-03R", numeric=True)]
    write_set(tmp_path, "pilot-v3", first)
    write_set(tmp_path, "development", second)
    write_set(tmp_path, "development-replacements", later, complete=False)
    # The holdout has sets of its own: a file of it is not read for development.
    write_set(tmp_path, "holdout", [case("HO-01", safety=True, spans=1)])
    found = m.report("development", tmp_path)
    assert found["sets"] == {
        "pilot-v3": "complete",
        "development": "complete",
        "development-replacements": "incomplete",
    }
    assert found["counts"] == m.counts([*first, *second])
    assert found["unmet"][:3] == ["ru_to_en: 1 of 12", "numeric: 2 of 12", "traps: 2 of 12"]
    write_set(tmp_path, "development-replacements", later)
    assert m.report("development", tmp_path)["counts"] == m.counts([*first, *second, *later])
    held = m.report("holdout", tmp_path)
    assert (held["registered_size"], held["reference_size"]) == (64, 100)
    assert held["sets"] == {"holdout": "complete", "holdout-replacements": "absent"}
    assert (held["minimums"], held["counts"]["safety_critical"]) == (HOLDOUT, 1)
    assert "safety_critical: 1 of 7" in held["unmet"]
    # One case in two sets of a split would be counted twice.
    write_set(tmp_path, "development-replacements", [*later, second[0]])
    with pytest.raises(ValueError, match="a case stands in two verified sets of development"):
        m.report("development", tmp_path)


def test_the_command_prints_both_splits_or_the_refusal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(m, "report", lambda split: {"split": split})
    assert m.main() == 0
    assert json.loads(capsys.readouterr().out) == [{"split": "development"}, {"split": "holdout"}]

    def refuse(split: str) -> dict[str, Any]:
        raise ValueError("a case stands in two verified sets of development")

    monkeypatch.setattr(m, "report", refuse)
    assert m.main() == 2
    assert capsys.readouterr().out == "refused: a case stands in two verified sets of development\n"
