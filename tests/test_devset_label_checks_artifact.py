"""Replay the published label verification of the pilot drafts from the committed files."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from evaluation import label_verification as lv
from evaluation.devset_sources import corpus_directory
from scripts import devset_label_verify as tool

ROOT = Path(__file__).resolve().parent.parent
ROUND_1 = tool.BASE / "round-1"
ROUND_2 = tool.BASE / "round-2"
REPAIRS = tool.BASE / "repairs.jsonl"
SCAN = tool.BASE / "wide-scan.json"
CAPSULE = ROOT / "docs/evidence/devset-pilot-label-verification.md"
VERIFIER = "claude-opus-5-5"
ABSOLUTE_PATH = re.compile(r"\b[A-Za-z]:[\\/](?!/)|/Users/|/home/")
# What a repair of this run changed, and nothing else: the capsule says so.
REPAIRED_FIELDS = {"wrong_answer_severity", "critical_facts"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spaced(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


@pytest.fixture(scope="module")
def register() -> dict[str, Any]:
    return json.loads(tool.REGISTER.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def drafts() -> dict[str, dict[str, Any]]:
    return tool.pilot_drafts().by_id()


@pytest.fixture(scope="module")
def repairs() -> dict[str, dict[str, Any]]:
    return {case["case_id"]: case for case in tool.read_jsonl(REPAIRS)}


@pytest.fixture(scope="module")
def stores() -> dict[int, list[dict[str, Any]]]:
    return {
        number: tool.read_jsonl(directory / f"{VERIFIER}.jsonl")
        for number, directory in ((1, ROUND_1), (2, ROUND_2))
    }


def test_verified_set_and_register_are_what_the_stores_give(register: dict[str, Any]) -> None:
    result = tool.check(
        tool.pilot_drafts(),
        ROUND_1,
        ROUND_2,
        repairs=REPAIRS,
        verified=tool.VERIFIED,
        register=tool.REGISTER,
    )
    assert result["status"] == "ok"
    assert result["cases"] == 30
    assert result["complete"] is True and register["complete"] is True
    assert result["states"] == register["summary"]["states"]
    assert sum(result["states"].values()) == 30
    assert result["states"]["repair_pending"] == 0 and result["states"]["unverified"] == 0
    for path in (tool.VERIFIED, tool.REGISTER):
        assert b"\r" not in path.read_bytes()


def test_every_plan_rebuilds_from_the_corpus_the_scan_and_the_repairs() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    result = tool.check(
        tool.pilot_drafts(),
        ROUND_1,
        ROUND_2,
        repairs=REPAIRS,
        verified=tool.VERIFIED,
        register=tool.REGISTER,
        inputs=tool.RoundInputs(
            round=1,
            corpus_dir=directory,
            scan=SCAN,
            archive=tool.ARCHIVE,
            previous=ROUND_1,
            repairs=REPAIRS,
        ),
    )
    assert result["status"] == "ok"


def test_register_names_the_committed_files_by_their_hashes(register: dict[str, Any]) -> None:
    corpus = json.loads(
        (ROOT / "evaluation/aircargo_corpus.manifest.json").read_text(encoding="utf-8")
    )
    assert register["sha256"] == {
        "drafts": _sha256(ROOT / "evaluation/devset_pilot.jsonl"),
        "families": _sha256(ROOT / "evaluation/document_families.json"),
        "corpus": corpus["corpus_sha256"],
        "scan": _sha256(SCAN),
        "archive": _sha256(tool.ARCHIVE),
        "repairs": _sha256(REPAIRS),
        "drops": None,
        "plans": {"1": _sha256(ROUND_1 / "plan.json"), "2": _sha256(ROUND_2 / "plan.json")},
        "stores": {
            "1": {VERIFIER: _sha256(ROUND_1 / f"{VERIFIER}.jsonl")},
            "2": {VERIFIER: _sha256(ROUND_2 / f"{VERIFIER}.jsonl")},
        },
        "verified_set": _sha256(tool.VERIFIED),
    }
    assert register["schema_version"] == "devset-label-checks/v1"
    assert register["rubric_version"] == lv.RUBRIC_VERSION == "label-verification/v2"
    assert register["prompt_sha256"] == lv.PROMPT_SHA256 == lv.prompt_sha256()
    for text in _strings(register):
        assert ABSOLUTE_PATH.search(text) is None, text[:80]


def test_decisions_files_are_the_outcomes_recomputed_from_the_stores() -> None:
    pilot = tool.pilot_drafts()
    for directory, given in ((ROUND_1, None), (ROUND_2, REPAIRS)):
        decided = tool.load_round(directory, pilot, given)
        written = json.loads((directory / "decisions.json").read_text(encoding="utf-8"))
        assert written["plan_sha256"] == decided.plan_sha256
        assert written["stores_sha256"] == decided.store_sha256
        assert written["cases"] == json.loads(
            json.dumps(
                [
                    {"case_id": case_id, **decision}
                    for case_id, decision in decided.decisions.items()
                ]
            )
        )
        outcomes = [case["outcome"] for case in written["cases"]]
        assert written["summary"] == {
            "round": decided.plan["round"],
            "confirmed": outcomes.count("confirmed"),
            "rejected": outcomes.count("rejected"),
            "none": 0,
            "declared_drops": 0,
        }


def test_one_model_checked_every_label_and_the_status_says_so(
    register: dict[str, Any], stores: dict[int, list[dict[str, Any]]]
) -> None:
    assert list(register["verifiers"]) == [VERIFIER]
    assert register["verifiers"][VERIFIER]["vendor"] == "Anthropic"
    assert register["verifiers"][VERIFIER]["settings"]["effort"] == "max"
    assert register["verifiers"][VERIFIER]["settings"]["tools"] == "none"
    assert register["draft_author"] == {"model": "gpt-6.1-sol", "vendor": "OpenAI"}
    assert register["repair_author"] == {"model": VERIFIER, "vendor": "Anthropic"}
    assert register["label_origin"] == "agent_labelled"
    for rows in stores.values():
        assert {row["verifier"] for row in rows} == {VERIFIER}
        assert {row["model"] for row in rows if row["status"] == "valid"} == {VERIFIER}
    after_repair = set(register["summary"]["verified_after_repair"])
    verified = tool.read_jsonl(tool.VERIFIED)
    assert len(verified) == register["summary"]["states"]["verified"]
    for row in verified:
        label = row["label_check"]
        assert label["status"] == "single_model_verified"
        assert label["verifiers"] == [VERIFIER]
        assert row["draft_author"] == register["draft_author"]
        assert ("repair_author" in label) == (row["case_id"] in after_repair)
        assert label["round"] == (2 if row["case_id"] in after_repair else 1)
        # A model check is not an approval: nothing in a verified row claims one.
        assert row["label_origin"] == "agent_labelled" and row["approved_by"] is None


def test_a_repair_changes_the_severity_and_the_critical_facts_and_nothing_else(
    register: dict[str, Any],
    drafts: dict[str, dict[str, Any]],
    repairs: dict[str, dict[str, Any]],
) -> None:
    repaired = [entry["case_id"] for entry in register["cases"] if entry["repair"] is not None]
    assert repaired == sorted(repairs)
    assert repaired == [
        entry["case_id"]
        for entry in register["cases"]
        if entry["rounds"]["1"]["outcome"] == "rejected"
    ]
    for case_id in repaired:
        before, after = drafts[case_id], repairs[case_id]
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        assert changed and changed <= REPAIRED_FIELDS, (case_id, changed)
        assert all(fact in after["required_facts"] for fact in after["critical_facts"])
        assert all(fact in after["critical_facts"] for fact in before["critical_facts"])
        assert len(after["critical_facts"]) > len(before["critical_facts"])


def _class_rows(register: dict[str, Any]) -> list[str]:
    return [
        f"| `{name}` | {row['drafted']} | {row['decided']} | {row['rejected']} "
        f"| {row['share_rejected']:.4f} |"
        for name, row in register["summary"]["first_check_rejection_by_drafted_class"].items()
    ]


def _repair_rows(
    register: dict[str, Any],
    drafts: dict[str, dict[str, Any]],
    repairs: dict[str, dict[str, Any]],
) -> list[str]:
    rows = []
    for entry in register["cases"]:
        if entry["repair"] is None:
            continue
        case_id = entry["case_id"]
        before, after = drafts[case_id], repairs[case_id]
        checks = ", ".join(row["check"] for row in entry["rounds"]["1"]["rejecting_checks"])
        rows.append(
            f"| {case_id} | `{entry['drafted_class']}` | {checks} "
            f"| {before['wrong_answer_severity']} → {after['wrong_answer_severity']} "
            f"| {len(before['critical_facts'])} → {len(after['critical_facts'])} "
            f"of {len(after['required_facts'])} "
            f"| {entry['rounds']['2']['outcome']} | {entry['state']} |"
        )
    return rows


def _severity_rows(register: dict[str, Any]) -> list[str]:
    return [
        f"| {row['case_id']} | {row['round']} | {row['registered']} | {row['named']} "
        f"| {row['steps']} | {'yes' if row['crosses_critical'] else 'no'} |"
        for row in register["summary"]["severity_differences"]
    ]


def test_capsule_states_the_register_the_hashes_and_the_limits(
    register: dict[str, Any],
    drafts: dict[str, dict[str, Any]],
    repairs: dict[str, dict[str, Any]],
    stores: dict[int, list[dict[str, Any]]],
) -> None:
    capsule = CAPSULE.read_text(encoding="utf-8")
    flat = " ".join(capsule.split())
    assert ABSOLUTE_PATH.search(capsule) is None
    summary = register["summary"]
    for row in (
        *_class_rows(register),
        *_repair_rows(register, drafts, repairs),
        *_severity_rows(register),
    ):
        assert row in capsule, row
    table = [line for line in capsule.splitlines() if re.match(r"\| T64-\d\d \| \d \|", line)]
    assert table == _severity_rows(register)

    states = summary["states"]
    by_class = ", ".join(
        f"`{name}` {count}" for name, count in summary["verified_by_class"].items()
    )
    sent = register["sent"][VERIFIER]
    rows = [row for number in (1, 2) for row in stores[number]]
    cost = sum(row["usage"].get("total_cost_usd", 0.0) for row in rows if row["usage"])
    elapsed = sum(row["elapsed_s"] or 0.0 for row in rows)
    first = [entry["rounds"]["1"]["outcome"] for entry in register["cases"]]
    scanned = {
        number: [
            request["corpus_text_counts"]["scan"]
            for request in tool.load_plan(directory)["requests"]
            if request["corpus_text_counts"]["scan"]
        ]
        for number, directory in ((1, ROUND_1), (2, ROUND_2))
    }
    passages = scanned[1] + scanned[2]
    for phrase in (
        f"**{states['verified']} verified, {states['dropped']} dropped, "
        f"{states['repair_pending']} awaiting repair, {states['unverified']} unverified**",
        f"{first.count('confirmed')} cases were confirmed at the first check",
        f"{len(summary['verified_after_repair'])} of the {states['verified']} verified",
        f"{first.count('rejected')} of {len(first)} rejected",
        f"Verified by class: {by_class}",
        f"{sent['requests']} requests in {sent['attempts']} attempts",
        f"{_spaced(sent['characters'])} characters",
        f"{_spaced(sent['corpus_texts'])} corpus texts",
        f"with {len(scanned[1])} requests of round 1 and {len(scanned[2])} of round 2, "
        f"{min(passages)} to {max(passages)} passages each",
        f"${cost:.2f}",
        f"{elapsed / 3600:.1f} hours",
        f"{sum(row['status'] == 'valid' for row in rows)} valid rows",
        f"safety-critical verified: {summary['safety_critical']['verified']}",
        f"`authority_unverified`: {len(summary['authority_unverified'])}",
    ):
        assert phrase in flat, phrase
    assert [row["status"] for row in rows if row["status"] != "valid"] == ["unavailable"]
    assert summary["dropped"] == [] and summary["verifier_disagreements"] == []
    assert all(row["class_before"] == row["class_after"] for row in summary["repaired_cases"])
    for entry in register["cases"]:
        if entry["repair"] is None:
            continue
        families = ", ".join(f"`{name}`" for name in entry["repair"]["families"])
        assert f"{entry['case_id']} — {families}" in flat
        assert entry["repair"]["documents"] == drafts[entry["case_id"]]["documents"]
    for cases, words in (
        (list(drafts.values()), "the drafts hold"),
        (tool.read_jsonl(tool.VERIFIED), "the verified set holds"),
    ):
        levels = Counter(case["wrong_answer_severity"] for case in cases)
        assert (
            f"{words} {levels['moderate']} `moderate`, {levels['high']} `high` "
            f"and {levels['critical']} `critical`"
        ) in flat
        assert levels["low"] == 0

    assert _sha256(tool.REGISTER) in capsule
    pinned = register["sha256"]
    for digest in (
        *(pinned[name] for name in ("drafts", "families", "corpus", "scan", "archive", "repairs")),
        *pinned["plans"].values(),
        *(store[VERIFIER] for store in pinned["stores"].values()),
        pinned["verified_set"],
        register["prompt_sha256"],
    ):
        assert digest in capsule, digest
    for phrase in (
        "`single_model_verified`",
        "`agent_labelled`",
        "`label-verification/v2`",
        "one model",
        "no model of another vendor was called",
        "no person approved a case",
        "rule (b) is not met",
        "this model makes systematically pass unseen",
        "not a check by another party",
        "written and checked by the same model",
        "not on a third-party timestamp",
        "Neither reply is counted",
        "a budget, not a measured recall",
        "were written after the drafts were labelled",
        "does not unblock B.2/B.3/B.5",
    ):
        assert phrase in flat, phrase

    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    named = [
        line
        for line in index.splitlines()
        if "`tests/test_devset_label_checks_artifact.py`" in line
    ]
    assert len(named) == 1 and "docs/evidence/devset-pilot-label-verification.md" in named[0]
    assert f"{states['verified']} verified" in named[0]
    assert "single_model_verified" in named[0] and "agent_labelled" in named[0]
