"""Every curated case carries a question class; the dataset stays byte-identical.

GR-0.2 first half. The class lives in a sidecar so
``evaluation/curated_cases_aircargo.jsonl`` remains the file phase C measured.
These tests are the gate: coverage, ADR 0008 evidence class, the pinned digest,
and a loader that names digest drift instead of joining onto a moved dataset.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from evaluation.aircargo_labels import BATCH_SIZE, EvidenceClass, dataset_digest
from evaluation.question_class_labels import (
    QUESTION_CLASSES,
    DatasetDigestMismatchError,
    QuestionClassLabel,
    load_classified_cases,
)

# Literal from the checked-in C.1a report — not imported from production code,
# so editing the dataset and the module constant together cannot quiet this test.
PUBLISHED_PHASE_C_DATASET_SHA256 = (
    "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
SIDECAR = PROJECT_ROOT / "evaluation" / "curated_cases_question_class.jsonl"
MANIFEST = PROJECT_ROOT / "evaluation" / "curated_cases_question_class.manifest.json"


def _jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        payload = json.loads(line)
        assert isinstance(payload, dict)
        rows.append(payload)
    return rows


def _label_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": "aircargo-probation-extend",
        "question_class": "single_hop",
        "reason": "FAQ 07_faq_probation.md question 4 states the ban in one answer.",
        "labelled_by": "agent:test",
        "labelled_at": "2026-09-06",
        "batch": 1,
        "approved_by": None,
    }
    payload.update(overrides)
    return payload


def test_sidecar_covers_every_dataset_id_once() -> None:
    dataset_ids = [str(row["case_id"]) for row in _jsonl(DATASET)]
    sidecar_ids = [str(row["case_id"]) for row in _jsonl(SIDECAR)]

    assert len(dataset_ids) == 100
    assert len(sidecar_ids) == 100
    assert len(set(sidecar_ids)) == 100
    assert set(sidecar_ids) == set(dataset_ids)


def test_every_sidecar_row_is_a_complete_agent_labelled_claim() -> None:
    rows = _jsonl(SIDECAR)
    batches: dict[int, int] = {}
    for row in rows:
        assert row["question_class"] in QUESTION_CLASSES, row["case_id"]
        reason = row["reason"]
        assert isinstance(reason, str) and reason.strip() and reason == reason.strip()
        assert row["evidence_class"] == EvidenceClass.AGENT_LABELLED.value
        assert row["approved_by"] is None
        assert isinstance(row["labelled_by"], str) and str(row["labelled_by"]).startswith("agent:")
        batch = row["batch"]
        assert isinstance(batch, int) and not isinstance(batch, bool) and batch >= 1
        batches[batch] = batches.get(batch, 0) + 1

    assert sorted(batches) == [1, 2, 3, 4, 5]
    assert set(batches.values()) == {BATCH_SIZE}


def test_manifest_pins_the_live_dataset_digest_and_phase_c_baseline() -> None:
    """The labelled dataset is still the measured dataset.

    This is the test that stops a later slice from quietly editing
    ``evaluation/curated_cases_aircargo.jsonl``.
    """
    live = dataset_digest(DATASET)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert live == PUBLISHED_PHASE_C_DATASET_SHA256
    assert manifest["dataset_sha256"] == live
    assert manifest["dataset"] == "evaluation/curated_cases_aircargo.jsonl"
    assert manifest["case_count"] == 100
    assert manifest["evidence_class"] == EvidenceClass.AGENT_LABELLED.value


def test_dataset_file_is_byte_identical_not_merely_line_ending_identical() -> None:
    """The spec scenario is about the file's own SHA-256, so assert that one.

    ``dataset_digest`` normalises CRLF to LF on purpose, and
    ``tests/test_aircargo_labels.py`` pins that behaviour: a manifest whose
    digest changes with a checkout pins nothing. The consequence is that the
    guards written for this slice would survive an LF -> CRLF conversion of the
    dataset, while ``docs/specs/retrieval-buckets.md`` claims the file stays
    *byte*-identical. ``.gitattributes`` checks every text file out with LF on
    every platform (``* text=auto eol=lf``), so the raw digest is stable and the
    stronger invariant is the one worth asserting.
    """
    raw = hashlib.sha256(DATASET.read_bytes()).hexdigest()

    assert raw == PUBLISHED_PHASE_C_DATASET_SHA256
    assert raw == dataset_digest(DATASET)


def test_manifest_question_class_counts_match_the_sidecar() -> None:
    rows = _jsonl(SIDECAR)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = {name: 0 for name in sorted(QUESTION_CLASSES)}
    expected.update(Counter(str(row["question_class"]) for row in rows))

    assert manifest["question_class_counts"] == expected
    assert sum(expected.values()) == 100


def test_valid_checked_in_sidecar_and_dataset_still_load() -> None:
    """FALSE-REJECT CONTROL: the HEAD artefacts remain accepted."""
    cases = load_classified_cases()
    dataset_ids = [str(row["case_id"]) for row in _jsonl(DATASET)]

    assert len(cases) == 100
    assert [case.case_id for case in cases] == dataset_ids
    assert all(case.label.evidence_class is EvidenceClass.AGENT_LABELLED for case in cases)
    assert all(case.label.approved_by is None for case in cases)
    assert {case.label.question_class.value for case in cases} <= QUESTION_CLASSES


def test_loader_raises_naming_drift_when_the_pinned_digest_disagrees(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "curated_cases_aircargo.jsonl"
    sidecar = tmp_path / "curated_cases_question_class.jsonl"
    manifest = tmp_path / "curated_cases_question_class.manifest.json"
    dataset.write_bytes(DATASET.read_bytes() + b"\n")
    sidecar.write_bytes(SIDECAR.read_bytes())
    manifest.write_bytes(MANIFEST.read_bytes())

    pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))["dataset_sha256"]
    actual = dataset_digest(dataset)
    assert actual != pinned

    with pytest.raises(DatasetDigestMismatchError, match="drift") as caught:
        load_classified_cases(
            dataset_path=dataset,
            sidecar_path=sidecar,
            manifest_path=manifest,
        )

    message = str(caught.value)
    assert pinned in message
    assert actual in message


def test_evidence_class_cannot_be_claimed_by_writing_it() -> None:
    with pytest.raises(ValueError, match="disagrees with the approval state"):
        QuestionClassLabel.from_mapping(_label_payload(evidence_class="real_labelled"))

    approved = QuestionClassLabel.from_mapping(_label_payload(approved_by="julia"))
    assert approved.evidence_class is EvidenceClass.REAL_LABELLED

    proposed = QuestionClassLabel.from_mapping(_label_payload())
    assert proposed.evidence_class is EvidenceClass.AGENT_LABELLED


def test_from_mapping_rejects_non_string_case_id_reason_and_labelled_by() -> None:
    """Malformed sidecar rows must be rejected, not silently stringified.

    ``QuestionClassLabel.from_mapping`` passes raw values through so
    ``_require_name`` sees the original types. ``str()``-coercing ``case_id``
    / ``reason`` / ``labelled_by`` first would turn 42, a list and None into
    ``'42'``, a stringified list and ``'None'``, and the last then passes
    ``_require_name`` as if it were a labeller.
    """
    combined = _label_payload(
        case_id=42,
        reason=["not", "a", "string"],
        labelled_by=None,
    )
    with pytest.raises(ValueError):
        QuestionClassLabel.from_mapping(combined)

    with pytest.raises(ValueError, match="case_id"):
        QuestionClassLabel.from_mapping(_label_payload(case_id=42))

    with pytest.raises(ValueError, match="reason"):
        QuestionClassLabel.from_mapping(_label_payload(reason=["not", "a", "string"]))

    with pytest.raises(ValueError, match="labelled_by"):
        QuestionClassLabel.from_mapping(_label_payload(labelled_by=None))


def test_probation_data_reason_does_not_invert_the_kakie_vocabulary_lesson() -> None:
    """A.6: 'какие' is not a class signal; the reason must not claim the inverse.

    The one-answer justification already names what forced ``single_hop``.
    ``not aggregation because the question starts with какие`` reads as
    какие ⇒ not aggregation — the inverse of the naive pattern-match the
    pack itself cites.
    """
    rows = {str(row["case_id"]): row for row in _jsonl(SIDECAR)}
    reason = str(rows["aircargo-probation-data"]["reason"])

    assert "because the question starts with какие" not in reason
    assert "07_faq_probation.md" in reason
    assert "one answer" in reason


def test_single_hop_reasons_name_the_one_section_not_a_slash_joined_pair() -> None:
    """A slash-joined citation reads as the multi_hop boundary.

    ``multi_hop`` is two or more sections. A ``single_hop`` reason that cites
    ``Назначение/Доказательства`` names two sections, so the audit trail a
    human reads at ADR-0008 approval contradicts the class it justifies —
    even when both facts already co-occur in the first of those sections.
    """
    rows = {str(row["case_id"]): row for row in _jsonl(SIDECAR)}

    cargo_loss = rows["aircargo-cargo-loss-evidence-bundle"]
    assert cargo_loss["question_class"] == "single_hop"
    cargo_reason = str(cargo_loss["reason"])
    assert "Назначение/Доказательства" not in cargo_reason
    assert (
        "Назначение already lists shortage report and seal photos in one paragraph"
        in cargo_reason
    )

    late_delivery = rows["aircargo-late-delivery-reply-evidence"]
    assert late_delivery["question_class"] == "single_hop"
    late_reason = str(late_delivery["reason"])
    assert "Назначение/Контрольный список" not in late_reason
    assert "Назначение names offload reason and terminal timestamps in one paragraph" in late_reason

    employment = rows["aircargo-employment-contract-essential-terms"]
    assert employment["question_class"] == "single_hop"
    employment_reason = str(employment["reason"])
    assert "evidence/preamble" not in employment_reason
    assert (
        "Доказательства и источники line cites ст. 57 and трудовая функция in one bullet"
        in employment_reason
    )

    insurance = rows["aircargo-cargo-insurance-operational-limits"]
    assert insurance["question_class"] == "single_hop"
    insurance_reason = str(insurance["reason"])
    assert "Риски/Контрольный список" not in insurance_reason
    assert "Контрольный список" not in insurance_reason
    assert (
        "Риски и ограничения names special cargo and excluded route in one bullet"
        in insurance_reason
    )
