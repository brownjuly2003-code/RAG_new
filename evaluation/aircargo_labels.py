"""Journey labels for the 100 curated air-cargo cases.

Audit 2026-08-23 (FIN-13): the repository holds 100 air-cargo cases and 17
synthetic resolution scenarios, and nothing joins them. A case carries a query
and a keyword expectation -- enough to score a retrieval answer, not enough to
say which resolution journey the request belongs to, what a correct outcome
would be, or what stops the kernel from reaching it. Phase B of
``plan_23_08_2026.md`` is that labelling, and the brief it comes from
(``D:\\New_steps\\rag.md`` phase 0) asks for exactly three fields per case:
journey, outcome, root cause -- or an explicit out-of-scope.

A label is a claim about the *request*, not about any implementation, so it
stays true when the kernel changes:

``journey``            which of the three contracts of the brief section 4.4
                       would own the request, or ``out_of_scope`` when none
                       would.
``expected_terminal``  the outcome a correct product should reach for the
                       request as written, in the kernel's own
                       ``TerminalOutcome`` vocabulary.
``root_cause``         what stops the resolution kernel from reaching that
                       outcome today.

``binds_shipment`` is separate from all three because it is the fact the whole
phase turns on: a journey cannot start without a shipment to run it against.

``labelled_by`` and ``approved_by`` decide ``evidence_class``: a label the
agent proposed is ``agent_labelled``; only a label a human approved is
``real_labelled`` (ADR 0008). A file cannot claim the second class by writing
it -- :class:`CaseLabel` derives the class from ``approved_by`` and rejects a
stored value that disagrees.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from resolution.contracts import TerminalOutcome

LABEL_SCHEMA_VERSION = "aircargo-case-labels/v1.0"
MANIFEST_SCHEMA_VERSION = "aircargo-case-label-manifest/v1.0"

#: Review batch size agreed with the domain-owner proxy (plan Q2).
BATCH_SIZE = 20

_MAX_NAME = 64
_MAX_NOTE = 512


class Journey(StrEnum):
    """The three journeys of the brief, plus the explicit fourth answer.

    ``customs_docs`` is the brief's "customs/document completeness check" and
    covers any completeness check of the documents and data a shipment needs
    against the applicable policy version -- customs, special-cargo acceptance
    and transport paperwork alike. ``out_of_scope`` is a decision, not a
    fallback: it says no resolution contract would own the request.
    """

    SHIPMENT_STATUS = "shipment_status"
    CUSTOMS_DOCS = "customs_docs"
    EXCEPTION_ESCALATION = "exception_escalation"
    OUT_OF_SCOPE = "out_of_scope"


class RootCause(StrEnum):
    """What stops the resolution kernel from serving the case today."""

    NONE = "none"
    NO_CONTRACT_FOR_INTENT = "no_contract_for_intent"
    NO_SHIPMENT_BINDING = "no_shipment_binding"
    SOURCE_SYSTEM_MISSING = "source_system_missing"


class LabelConfidence(StrEnum):
    """How firm the proposed label is, so review starts where it is weakest."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceClass(StrEnum):
    AGENT_LABELLED = "agent_labelled"
    REAL_LABELLED = "real_labelled"


def _require_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > _MAX_NAME:
        raise ValueError(f"{field} must be non-empty bounded trimmed text")
    return value


def _require_note(value: str, field: str) -> str:
    if not isinstance(value, str) or value != value.strip() or len(value) > _MAX_NOTE:
        raise ValueError(f"{field} must be trimmed text of at most {_MAX_NOTE} characters")
    return value


@dataclass(frozen=True, slots=True)
class CaseLabel:
    """One reviewed claim about one case."""

    journey: Journey
    expected_terminal: TerminalOutcome
    root_cause: RootCause
    binds_shipment: bool
    confidence: LabelConfidence
    labelled_by: str
    labelled_at: date
    batch: int
    approved_by: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        _require_name(self.labelled_by, "labelled_by")
        _require_note(self.note, "note")
        if self.approved_by is not None:
            _require_name(self.approved_by, "approved_by")
        if not isinstance(self.batch, int) or isinstance(self.batch, bool) or self.batch < 1:
            raise ValueError("batch must be a positive integer")
        if not isinstance(self.binds_shipment, bool):
            raise ValueError("binds_shipment must be a boolean")

        out_of_scope = self.journey is Journey.OUT_OF_SCOPE
        blames_contract = self.root_cause is RootCause.NO_CONTRACT_FOR_INTENT
        if out_of_scope != blames_contract:
            raise ValueError(
                "out_of_scope and no_contract_for_intent are the same claim: "
                "a case has both or neither"
            )
        if self.root_cause is RootCause.NONE and not self.binds_shipment:
            raise ValueError(
                "root_cause=none says the kernel can serve the case, which it "
                "cannot without a shipment to run the journey against"
            )
        if not self.binds_shipment and not out_of_scope and self.root_cause is not (
            RootCause.NO_SHIPMENT_BINDING
        ):
            raise ValueError(
                "an in-journey case that names no shipment is blocked by "
                "no_shipment_binding before anything else"
            )

    @property
    def evidence_class(self) -> EvidenceClass:
        """Derived, never stored: only a human approval earns ``real_labelled``."""
        if self.approved_by is None:
            return EvidenceClass.AGENT_LABELLED
        return EvidenceClass.REAL_LABELLED

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CaseLabel:
        unknown = sorted(set(payload) - _LABEL_FIELDS)
        if unknown:
            raise ValueError(f"unknown label fields: {unknown}")
        missing = sorted(_REQUIRED_LABEL_FIELDS - set(payload))
        if missing:
            raise ValueError(f"missing label fields: {missing}")

        approved_by = payload.get("approved_by")
        if approved_by is not None and not isinstance(approved_by, str):
            raise ValueError("approved_by must be a string or null")
        raw_date = payload["labelled_at"]
        if not isinstance(raw_date, str):
            raise ValueError("labelled_at must be an ISO date string")

        label = cls(
            journey=Journey(payload["journey"]),
            expected_terminal=TerminalOutcome(payload["expected_terminal"]),
            root_cause=RootCause(payload["root_cause"]),
            binds_shipment=payload["binds_shipment"],
            confidence=LabelConfidence(payload["confidence"]),
            labelled_by=payload["labelled_by"],
            labelled_at=date.fromisoformat(raw_date),
            batch=payload["batch"],
            approved_by=approved_by,
            note=payload.get("note", ""),
        )
        stored_class = payload.get("evidence_class")
        if stored_class is not None and stored_class != label.evidence_class.value:
            raise ValueError(
                f"stored evidence_class {stored_class!r} disagrees with the "
                f"approval state, which makes it {label.evidence_class.value!r}"
            )
        return label

    def as_dict(self) -> dict[str, Any]:
        return {
            "journey": self.journey.value,
            "expected_terminal": self.expected_terminal.value,
            "root_cause": self.root_cause.value,
            "binds_shipment": self.binds_shipment,
            "confidence": self.confidence.value,
            "labelled_by": self.labelled_by,
            "labelled_at": self.labelled_at.isoformat(),
            "batch": self.batch,
            "approved_by": self.approved_by,
            "evidence_class": self.evidence_class.value,
            "note": self.note,
        }


_LABEL_FIELDS = frozenset(
    {
        "journey",
        "expected_terminal",
        "root_cause",
        "binds_shipment",
        "confidence",
        "labelled_by",
        "labelled_at",
        "batch",
        "approved_by",
        "evidence_class",
        "note",
    }
)
_REQUIRED_LABEL_FIELDS = frozenset(
    {
        "journey",
        "expected_terminal",
        "root_cause",
        "binds_shipment",
        "confidence",
        "labelled_by",
        "labelled_at",
        "batch",
    }
)


@dataclass(frozen=True, slots=True)
class LabelledCase:
    case_id: str
    query: str
    tags: tuple[str, ...]
    label: CaseLabel


@dataclass(frozen=True, slots=True)
class LabelSummary:
    """The distribution, which is the point of the labelling."""

    case_count: int
    journey_counts: Mapping[str, int]
    expected_terminal_counts: Mapping[str, int]
    root_cause_counts: Mapping[str, int]
    confidence_counts: Mapping[str, int]
    binds_shipment_count: int
    real_labelled_count: int
    agent_labelled_count: int
    approved_batches: tuple[int, ...]
    journey_coverage_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "journey_counts": dict(self.journey_counts),
            "expected_terminal_counts": dict(self.expected_terminal_counts),
            "root_cause_counts": dict(self.root_cause_counts),
            "confidence_counts": dict(self.confidence_counts),
            "binds_shipment_count": self.binds_shipment_count,
            "real_labelled_count": self.real_labelled_count,
            "agent_labelled_count": self.agent_labelled_count,
            "approved_batches": list(self.approved_batches),
            "journey_coverage_count": self.journey_coverage_count,
        }


def _counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def summarise(cases: Sequence[LabelledCase]) -> LabelSummary:
    labels = [case.label for case in cases]
    approved = sorted({label.batch for label in labels if label.approved_by is not None})
    fully_approved = tuple(
        batch
        for batch in approved
        if all(
            label.approved_by is not None for label in labels if label.batch == batch
        )
    )
    return LabelSummary(
        case_count=len(cases),
        journey_counts=_counts(label.journey.value for label in labels),
        expected_terminal_counts=_counts(label.expected_terminal.value for label in labels),
        root_cause_counts=_counts(label.root_cause.value for label in labels),
        confidence_counts=_counts(label.confidence.value for label in labels),
        binds_shipment_count=sum(1 for label in labels if label.binds_shipment),
        real_labelled_count=sum(
            1 for label in labels if label.evidence_class is EvidenceClass.REAL_LABELLED
        ),
        agent_labelled_count=sum(
            1 for label in labels if label.evidence_class is EvidenceClass.AGENT_LABELLED
        ),
        approved_batches=fully_approved,
        journey_coverage_count=sum(
            1 for label in labels if label.journey is not Journey.OUT_OF_SCOPE
        ),
    )


def load_labelled_cases(path: Path) -> tuple[LabelledCase, ...]:
    """Read the dataset and require every case to carry a label.

    Phase B's claim is "100% of cases have a journey/outcome or an explicit
    out-of-scope", so a case without a label is a failure to load, not a case
    that is silently skipped.
    """
    cases: list[LabelledCase] = []
    seen: set[str] = set()
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        payload = json.loads(line)
        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path.name}:{number} has no case_id")
        if case_id in seen:
            raise ValueError(f"{path.name}:{number} repeats case_id {case_id!r}")
        seen.add(case_id)
        label_payload = payload.get("label")
        if not isinstance(label_payload, Mapping):
            raise ValueError(f"{path.name}:{number} ({case_id}) carries no label")
        try:
            label = CaseLabel.from_mapping(label_payload)
        except ValueError as error:
            raise ValueError(f"{path.name}:{number} ({case_id}): {error}") from error
        tags = payload.get("tags") or []
        cases.append(
            LabelledCase(
                case_id=case_id,
                query=str(payload.get("query", "")),
                tags=tuple(str(tag) for tag in tags),
                label=label,
            )
        )
    return tuple(cases)


def dataset_digest(path: Path) -> str:
    """SHA-256 of the dataset bytes, normalised to ``\\n`` line endings.

    A manifest that pins a digest which changes with a checkout on another
    platform pins nothing.
    """
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def build_manifest(
    path: Path,
    cases: Sequence[LabelledCase],
    *,
    dataset: str,
    case_source: str,
    case_source_note: str,
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    summary = summarise(cases)
    corpus_class = (
        EvidenceClass.REAL_LABELLED
        if summary.real_labelled_count == summary.case_count and summary.case_count > 0
        else EvidenceClass.AGENT_LABELLED
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "label_schema_version": LABEL_SCHEMA_VERSION,
        "dataset": dataset,
        "dataset_sha256": dataset_digest(path),
        "batch_size": batch_size,
        "case_source": case_source,
        "case_source_note": case_source_note,
        "evidence_class": corpus_class.value,
        "summary": summary.as_dict(),
    }


def verify_manifest(
    manifest: Mapping[str, Any],
    path: Path,
    cases: Sequence[LabelledCase],
) -> tuple[str, ...]:
    """Return every disagreement between the manifest and the dataset."""
    expected = build_manifest(
        path,
        cases,
        dataset=str(manifest.get("dataset", "")),
        case_source=str(manifest.get("case_source", "")),
        case_source_note=str(manifest.get("case_source_note", "")),
        batch_size=int(manifest.get("batch_size", BATCH_SIZE)),
    )
    problems: list[str] = []
    for key, value in expected.items():
        stored = manifest.get(key)
        if stored != value:
            problems.append(f"{key}: manifest has {stored!r}, dataset says {value!r}")
    return tuple(problems)


__all__ = [
    "BATCH_SIZE",
    "LABEL_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "CaseLabel",
    "EvidenceClass",
    "Journey",
    "LabelConfidence",
    "LabelSummary",
    "LabelledCase",
    "RootCause",
    "build_manifest",
    "dataset_digest",
    "load_labelled_cases",
    "summarise",
    "verify_manifest",
]
