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
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from resolution.contracts import TerminalOutcome

LABEL_SCHEMA_VERSION = "aircargo-case-labels/v1.0"
MANIFEST_SCHEMA_VERSION = "aircargo-case-label-manifest/v1.1"
APPROVALS_SCHEMA_VERSION = "aircargo-label-approvals/v1.0"
DATASET_NAME = "evaluation/curated_cases_aircargo.jsonl"

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
class BatchApproval:
    """A human approval of every case in one review batch."""

    batch: int
    approver: str
    approved_at: date
    case_ids: tuple[str, ...]
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.batch, int) or isinstance(self.batch, bool) or self.batch < 1:
            raise ValueError("batch must be a positive integer")
        _require_name(self.approver, "approver")
        if self.approver.casefold().startswith("agent"):
            raise ValueError("approver cannot start with 'agent'")
        if type(self.approved_at) is not date:
            raise ValueError("approved_at must be a date")
        if not isinstance(self.case_ids, tuple) or not self.case_ids:
            raise ValueError("case_ids must be a non-empty tuple")
        for case_id in self.case_ids:
            _require_name(case_id, "case_id")
        _require_note(self.note, "note")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> BatchApproval:
        if not isinstance(payload, Mapping):
            raise ValueError("approval must be a JSON object")
        unknown = sorted(set(payload) - _APPROVAL_FIELDS)
        if unknown:
            raise ValueError(f"unknown approval fields: {unknown}")
        missing = sorted(_REQUIRED_APPROVAL_FIELDS - set(payload))
        if missing:
            raise ValueError(f"missing approval fields: {missing}")
        raw_date = payload["approved_at"]
        if not isinstance(raw_date, str):
            raise ValueError("approved_at must be an ISO date string")
        try:
            approved_at = date.fromisoformat(raw_date)
        except ValueError as error:
            raise ValueError(f"approved_at is not an ISO date: {raw_date!r}") from error
        raw_ids = payload["case_ids"]
        if not isinstance(raw_ids, list):
            raise ValueError("case_ids must be a JSON array")
        return cls(
            batch=payload["batch"],
            approver=payload["approver"],
            approved_at=approved_at,
            case_ids=tuple(raw_ids),
            note=payload.get("note", ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch": self.batch,
            "approver": self.approver,
            "approved_at": self.approved_at.isoformat(),
            "case_ids": list(self.case_ids),
            "note": self.note,
        }


_APPROVAL_FIELDS = frozenset({"batch", "approver", "approved_at", "case_ids", "note"})
_REQUIRED_APPROVAL_FIELDS = _APPROVAL_FIELDS - {"note"}


@dataclass(frozen=True, slots=True)
class ApprovalSidecar:
    """Approvals pinned to one immutable dataset snapshot."""

    schema_version: str
    dataset: str
    dataset_sha256: str
    approvals: tuple[BatchApproval, ...]

    def __post_init__(self) -> None:
        if self.schema_version != APPROVALS_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {APPROVALS_SCHEMA_VERSION!r}")
        if self.dataset != DATASET_NAME:
            raise ValueError(f"dataset must be {DATASET_NAME!r}")
        if (
            not isinstance(self.dataset_sha256, str)
            or len(self.dataset_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.dataset_sha256)
        ):
            raise ValueError("dataset_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.approvals, tuple) or any(
            not isinstance(approval, BatchApproval) for approval in self.approvals
        ):
            raise ValueError("approvals must be a tuple of batch approvals")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ApprovalSidecar:
        if not isinstance(payload, Mapping):
            raise ValueError("sidecar must be a JSON object")
        unknown = sorted(set(payload) - _SIDECAR_FIELDS)
        if unknown:
            raise ValueError(f"unknown sidecar fields: {unknown}")
        missing = sorted(_SIDECAR_FIELDS - set(payload))
        if missing:
            raise ValueError(f"missing sidecar fields: {missing}")
        raw_approvals = payload["approvals"]
        if not isinstance(raw_approvals, list):
            raise ValueError("approvals must be a JSON array")
        return cls(
            schema_version=payload["schema_version"],
            dataset=payload["dataset"],
            dataset_sha256=payload["dataset_sha256"],
            approvals=tuple(BatchApproval.from_mapping(item) for item in raw_approvals),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset": self.dataset,
            "dataset_sha256": self.dataset_sha256,
            "approvals": [
                approval.as_dict()
                for approval in sorted(self.approvals, key=lambda item: item.batch)
            ],
        }


_SIDECAR_FIELDS = frozenset({"schema_version", "dataset", "dataset_sha256", "approvals"})


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


def load_labelled_cases_from_bytes(
    dataset_bytes: bytes,
    *,
    source_name: str,
) -> tuple[LabelledCase, ...]:
    """Parse one UTF-8 dataset snapshot and require a label on every case.

    Phase B's claim is "100% of cases have a journey/outcome or an explicit
    out-of-scope", so a case without a label is a failure to load, not a case
    that is silently skipped.
    """
    cases: list[LabelledCase] = []
    seen: set[str] = set()
    for number, raw_line in enumerate(dataset_bytes.decode("utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        payload = json.loads(line)
        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{source_name}:{number} has no case_id")
        if case_id in seen:
            raise ValueError(f"{source_name}:{number} repeats case_id {case_id!r}")
        seen.add(case_id)
        label_payload = payload.get("label")
        if not isinstance(label_payload, Mapping):
            raise ValueError(f"{source_name}:{number} ({case_id}) carries no label")
        try:
            label = CaseLabel.from_mapping(label_payload)
        except ValueError as error:
            raise ValueError(f"{source_name}:{number} ({case_id}): {error}") from error
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


def load_approval_sidecar(path: Path) -> ApprovalSidecar:
    """Parse one approval sidecar without changing the dataset."""
    return ApprovalSidecar.from_mapping(json.loads(path.read_text(encoding="utf-8")))


def apply_approvals(
    cases: Sequence[LabelledCase], sidecar: ApprovalSidecar, *, dataset_path: Path
) -> tuple[LabelledCase, ...]:
    """Validate and merge complete batch approvals onto dataset labels."""
    actual_digest = dataset_digest(dataset_path)
    if sidecar.dataset_sha256 != actual_digest:
        raise ValueError(
            "approval sidecar dataset digest mismatch: "
            f"pinned {sidecar.dataset_sha256}, actual {actual_digest}"
        )
    by_id = {case.case_id: case for case in cases}
    batch_ids: dict[int, set[str]] = {}
    for case in cases:
        batch_ids.setdefault(case.label.batch, set()).add(case.case_id)
    approved_by_id: dict[str, str] = {}
    seen_batches: set[int] = set()
    for approval in sidecar.approvals:
        batch = approval.batch
        if batch in seen_batches:
            raise ValueError(f"batch {batch} approved twice")
        seen_batches.add(batch)
        expected_ids = batch_ids.get(batch)
        if expected_ids is None:
            raise ValueError(f"batch {batch} is not in the dataset")
        for case_id in approval.case_ids:
            if case_id in approved_by_id:
                raise ValueError(f"case {case_id!r} approved twice in batch {batch}")
            approved_case = by_id.get(case_id)
            if approved_case is None:
                raise ValueError(f"batch {batch} names case {case_id!r} not in the dataset")
            if approved_case.label.batch != batch:
                raise ValueError(
                    f"batch {batch} names case {case_id!r} from batch {approved_case.label.batch}"
                )
            if approved_case.label.approved_by is not None:
                raise ValueError(f"case {case_id!r} already carries approved_by in the dataset")
            approved_by_id[case_id] = approval.approver
        missing = expected_ids - set(approval.case_ids)
        if missing:
            raise ValueError(f"batch {batch} approval does not cover {sorted(missing)}")
    return tuple(
        replace(case, label=replace(case.label, approved_by=approved_by_id[case.case_id]))
        if case.case_id in approved_by_id
        else case
        for case in cases
    )


def load_labelled_cases(
    path: Path, *, approvals_path: Path | None = None
) -> tuple[LabelledCase, ...]:
    """Read labels, merging an existing approval sidecar when requested."""
    cases = load_labelled_cases_from_bytes(path.read_bytes(), source_name=path.name)
    if approvals_path is None or not approvals_path.exists():
        return cases
    return apply_approvals(cases, load_approval_sidecar(approvals_path), dataset_path=path)


def dataset_digest_bytes(dataset_bytes: bytes) -> str:
    """SHA-256 of dataset bytes, normalised to ``\\n`` line endings."""
    return hashlib.sha256(dataset_bytes.replace(b"\r\n", b"\n")).hexdigest()


def dataset_digest(path: Path) -> str:
    """SHA-256 of the dataset bytes, normalised to ``\\n`` line endings.

    A manifest that pins a digest which changes with a checkout on another
    platform pins nothing.
    """
    return dataset_digest_bytes(path.read_bytes())


def build_manifest(
    path: Path,
    cases: Sequence[LabelledCase],
    *,
    dataset: str,
    case_source: str,
    case_source_note: str,
    batch_size: int = BATCH_SIZE,
    approvals_path: Path | None = None,
    approvals_name: str | None = None,
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
        "approvals": (
            {
                "file": approvals_name or approvals_path.name,
                "sha256": dataset_digest(approvals_path),
            }
            if approvals_path is not None and approvals_path.exists()
            else None
        ),
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
    *,
    approvals_path: Path | None = None,
    approvals_name: str | None = None,
) -> tuple[str, ...]:
    """Return every disagreement with the dataset and approval sidecar."""
    expected = build_manifest(
        path,
        cases,
        dataset=str(manifest.get("dataset", "")),
        case_source=str(manifest.get("case_source", "")),
        case_source_note=str(manifest.get("case_source_note", "")),
        batch_size=int(manifest.get("batch_size", BATCH_SIZE)),
        approvals_path=approvals_path,
        approvals_name=approvals_name,
    )
    legacy_without_sidecar = (
        manifest.get("schema_version") == "aircargo-case-label-manifest/v1.0"
        and "approvals" not in manifest
        and expected["approvals"] is None
    )
    if legacy_without_sidecar:
        expected["schema_version"] = "aircargo-case-label-manifest/v1.0"
        del expected["approvals"]
    problems: list[str] = []
    for key, value in expected.items():
        stored = manifest.get(key)
        if stored != value:
            if key == "approvals" and isinstance(stored, Mapping) and isinstance(value, Mapping):
                for field in ("file", "sha256"):
                    if stored.get(field) != value[field]:
                        problems.append(
                            f"approvals.{field}: manifest has {stored.get(field)!r}, "
                            f"sidecar says {value[field]!r}"
                        )
            else:
                problems.append(f"{key}: manifest has {stored!r}, dataset says {value!r}")
    return tuple(problems)


__all__ = [
    "APPROVALS_SCHEMA_VERSION",
    "BATCH_SIZE",
    "DATASET_NAME",
    "LABEL_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "ApprovalSidecar",
    "BatchApproval",
    "CaseLabel",
    "EvidenceClass",
    "Journey",
    "LabelConfidence",
    "LabelSummary",
    "LabelledCase",
    "RootCause",
    "apply_approvals",
    "build_manifest",
    "dataset_digest",
    "dataset_digest_bytes",
    "load_approval_sidecar",
    "load_labelled_cases",
    "load_labelled_cases_from_bytes",
    "summarise",
    "verify_manifest",
]
