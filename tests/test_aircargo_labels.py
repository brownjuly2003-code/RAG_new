"""The labels are only worth something if they cannot quietly become false.

Phase B's claim is "every one of the 100 air-cargo cases has a journey and an
outcome, or an explicit out-of-scope, and the ones a human approved say so".
Three things could rot that claim without anyone noticing: a case added
without a label, a label that contradicts itself, and a file that writes
``real_labelled`` next to an approval that never happened. Each has a test.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from evaluation.aircargo_labels import (
    BATCH_SIZE,
    CaseLabel,
    EvidenceClass,
    Journey,
    LabelConfidence,
    RootCause,
    dataset_digest,
    load_labelled_cases,
    summarise,
    verify_manifest,
)
from resolution.contracts import TerminalOutcome

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
MANIFEST = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.manifest.json"


def _label(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "journey": "shipment_status",
        "expected_terminal": "verified",
        "root_cause": "no_shipment_binding",
        "binds_shipment": False,
        "confidence": "high",
        "labelled_by": "agent:test",
        "labelled_at": "2026-08-25",
        "batch": 1,
        "approved_by": None,
    }
    payload.update(overrides)
    return payload


def test_every_checked_in_case_carries_a_label() -> None:
    cases = load_labelled_cases(DATASET)

    assert len(cases) == 100
    assert len({case.case_id for case in cases}) == 100
    assert all(case.label.labelled_by for case in cases)


def test_batches_are_the_size_the_reviewer_agreed_to() -> None:
    cases = load_labelled_cases(DATASET)

    sizes = {batch: 0 for batch in {case.label.batch for case in cases}}
    for case in cases:
        sizes[case.label.batch] += 1

    assert sorted(sizes) == [1, 2, 3, 4, 5]
    assert set(sizes.values()) == {BATCH_SIZE}


def test_manifest_still_describes_the_dataset() -> None:
    cases = load_labelled_cases(DATASET)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert verify_manifest(manifest, DATASET, cases) == ()
    assert manifest["dataset_sha256"] == dataset_digest(DATASET)


def test_the_phase_b_gate_is_not_met_by_labelling_alone() -> None:
    """Nothing here may read as 100 real labelled cases (ADR 0008 fallback).

    Until the domain-owner proxy approves a batch, every label is the agent's
    proposal. The corpus class follows the weakest label, not the intent.
    """
    cases = load_labelled_cases(DATASET)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = summarise(cases)

    approved = sum(1 for case in cases if case.label.approved_by is not None)
    assert summary.real_labelled_count == approved
    assert summary.agent_labelled_count == len(cases) - approved
    if approved < len(cases):
        assert manifest["evidence_class"] == EvidenceClass.AGENT_LABELLED.value


def test_no_case_binds_a_shipment_without_saying_why_the_kernel_stops() -> None:
    """The finding phase B turned on: the corpus starts no journey."""
    cases = load_labelled_cases(DATASET)

    for case in cases:
        label = case.label
        if label.binds_shipment:
            continue
        expected = (
            RootCause.NO_CONTRACT_FOR_INTENT
            if label.journey is Journey.OUT_OF_SCOPE
            else RootCause.NO_SHIPMENT_BINDING
        )
        assert label.root_cause is expected, case.case_id


def test_evidence_class_cannot_be_claimed_by_writing_it() -> None:
    with pytest.raises(ValueError, match="disagrees with the approval state"):
        CaseLabel.from_mapping(_label(evidence_class="real_labelled"))

    approved = CaseLabel.from_mapping(_label(approved_by="julia"))
    assert approved.evidence_class is EvidenceClass.REAL_LABELLED

    proposed = CaseLabel.from_mapping(_label())
    assert proposed.evidence_class is EvidenceClass.AGENT_LABELLED


def test_out_of_scope_and_no_contract_are_the_same_claim() -> None:
    with pytest.raises(ValueError, match="same claim"):
        CaseLabel.from_mapping(_label(journey="out_of_scope"))

    with pytest.raises(ValueError, match="same claim"):
        CaseLabel.from_mapping(_label(root_cause="no_contract_for_intent"))


def test_a_case_the_kernel_can_serve_must_name_a_shipment() -> None:
    with pytest.raises(ValueError, match="without a shipment"):
        CaseLabel.from_mapping(_label(root_cause="none", binds_shipment=False))

    served = CaseLabel.from_mapping(_label(root_cause="none", binds_shipment=True))
    assert served.root_cause is RootCause.NONE


def test_unknown_and_missing_label_fields_are_refused() -> None:
    with pytest.raises(ValueError, match="unknown label fields"):
        CaseLabel.from_mapping(_label(reviewer_mood="sceptical"))

    incomplete = _label()
    del incomplete["journey"]
    with pytest.raises(ValueError, match="missing label fields"):
        CaseLabel.from_mapping(incomplete)


def test_a_case_without_a_label_fails_to_load(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps({"case_id": "c1", "query": "q", "label": _label()}, ensure_ascii=False)
        + "\n"
        + json.dumps({"case_id": "c2", "query": "q"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="carries no label"):
        load_labelled_cases(path)


def test_digest_survives_a_checkout_that_changes_line_endings(tmp_path: Path) -> None:
    body = json.dumps({"case_id": "c1", "query": "q", "label": _label()}, ensure_ascii=False)
    unix = tmp_path / "unix.jsonl"
    windows = tmp_path / "windows.jsonl"
    unix.write_bytes((body + "\n").encode("utf-8"))
    windows.write_bytes((body + "\r\n").encode("utf-8"))

    assert dataset_digest(unix) == dataset_digest(windows)


def test_summary_counts_the_journeys_the_kernel_could_own() -> None:
    cases = load_labelled_cases(DATASET)
    summary = summarise(cases)

    in_journey = sum(
        1 for case in cases if case.label.journey is not Journey.OUT_OF_SCOPE
    )
    assert summary.journey_coverage_count == in_journey
    assert sum(summary.journey_counts.values()) == len(cases)
    assert summary.binds_shipment_count == sum(
        1 for case in cases if case.label.binds_shipment
    )


def test_a_label_is_immutable_and_typed() -> None:
    label = CaseLabel(
        journey=Journey.CUSTOMS_DOCS,
        expected_terminal=TerminalOutcome.VERIFIED,
        root_cause=RootCause.NO_SHIPMENT_BINDING,
        binds_shipment=False,
        confidence=LabelConfidence.MEDIUM,
        labelled_by="agent:test",
        labelled_at=date(2026, 8, 25),
        batch=3,
    )

    assert label.as_dict()["evidence_class"] == "agent_labelled"
    with pytest.raises(AttributeError):
        label.journey = Journey.OUT_OF_SCOPE  # type: ignore[misc]
