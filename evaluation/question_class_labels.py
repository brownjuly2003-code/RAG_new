"""Question-class labels for the 100 curated air-cargo cases.

The class describes the *question*, not what today's retriever does with it:
``single_hop``, ``multi_hop``, ``aggregation`` or ``global``. Stream GR of
``plan_06_09_26.md`` reports every retrieval number per class, so every case
has to carry one.

The class lives in a sidecar, not in ``evaluation/curated_cases_aircargo.jsonl``.
Editing the dataset would make the published C.1a numbers no longer
re-derivable from the dataset at HEAD, for a label that has nothing to do
with them. The sidecar pins the dataset digest it was written against, which
is strictly better provenance than writing ``label.question_class`` into the
measured file.

``labelled_by`` and ``approved_by`` decide ``evidence_class`` the same way
the journey labels do: a label the agent proposed is ``agent_labelled``; only
a human approval earns ``real_labelled`` (ADR 0008). A file cannot claim the
second class by writing it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from evaluation.aircargo_labels import EvidenceClass, dataset_digest

LABEL_SCHEMA_VERSION = "aircargo-question-class-labels/v1.0"
MANIFEST_SCHEMA_VERSION = "aircargo-question-class-manifest/v1.0"

#: SHA-256 of ``evaluation/curated_cases_aircargo.jsonl`` as measured in the
#: checked-in phase C.1a report. The sidecar is written against this digest.
PHASE_C_DATASET_SHA256 = "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH: Final[Path] = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
DEFAULT_SIDECAR_PATH: Final[Path] = (
    PROJECT_ROOT / "evaluation" / "curated_cases_question_class.jsonl"
)
DEFAULT_MANIFEST_PATH: Final[Path] = (
    PROJECT_ROOT / "evaluation" / "curated_cases_question_class.manifest.json"
)

_MAX_NAME = 64
_MAX_REASON = 512

QUESTION_CLASSES: Final[frozenset[str]] = frozenset(
    {"single_hop", "multi_hop", "aggregation", "global"}
)


class QuestionClass(StrEnum):
    """Where the answer lives, independent of today's retriever."""

    SINGLE_HOP = "single_hop"
    MULTI_HOP = "multi_hop"
    AGGREGATION = "aggregation"
    GLOBAL = "global"


class DatasetDigestMismatchError(RuntimeError):
    """The sidecar must not join onto a dataset it was not written against."""


def _require_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > _MAX_NAME:
        raise ValueError(f"{field} must be non-empty bounded trimmed text")
    return value


def _require_reason(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\n" in value
        or len(value) > _MAX_REASON
    ):
        raise ValueError("reason must be a non-empty one-line string")
    return value


@dataclass(frozen=True, slots=True)
class QuestionClassLabel:
    """One reviewed claim about which class a case belongs to."""

    case_id: str
    question_class: QuestionClass
    reason: str
    labelled_by: str
    labelled_at: date
    batch: int
    approved_by: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.case_id, "case_id")
        _require_name(self.labelled_by, "labelled_by")
        _require_reason(self.reason)
        if self.approved_by is not None:
            _require_name(self.approved_by, "approved_by")
        if not isinstance(self.batch, int) or isinstance(self.batch, bool) or self.batch < 1:
            raise ValueError("batch must be a positive integer")

    @property
    def evidence_class(self) -> EvidenceClass:
        """Derived, never stored as a claim: only a human approval earns real_labelled."""
        if self.approved_by is None:
            return EvidenceClass.AGENT_LABELLED
        return EvidenceClass.REAL_LABELLED

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> QuestionClassLabel:
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
            case_id=payload["case_id"],
            question_class=QuestionClass(payload["question_class"]),
            reason=payload["reason"],
            labelled_by=payload["labelled_by"],
            labelled_at=date.fromisoformat(raw_date),
            batch=payload["batch"],
            approved_by=approved_by,
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
            "case_id": self.case_id,
            "question_class": self.question_class.value,
            "reason": self.reason,
            "labelled_by": self.labelled_by,
            "labelled_at": self.labelled_at.isoformat(),
            "batch": self.batch,
            "approved_by": self.approved_by,
            "evidence_class": self.evidence_class.value,
        }


_LABEL_FIELDS = frozenset(
    {
        "case_id",
        "question_class",
        "reason",
        "labelled_by",
        "labelled_at",
        "batch",
        "approved_by",
        "evidence_class",
    }
)
_REQUIRED_LABEL_FIELDS = frozenset(
    {
        "case_id",
        "question_class",
        "reason",
        "labelled_by",
        "labelled_at",
        "batch",
    }
)


@dataclass(frozen=True, slots=True)
class ClassifiedCase:
    """A dataset case joined with its question-class label."""

    case_id: str
    query: str
    tags: tuple[str, ...]
    label: QuestionClassLabel


def question_class_counts(labels: Sequence[QuestionClassLabel]) -> dict[str, int]:
    """Count every class, including zeros, so a class of three cannot hide."""
    counts = {name: 0 for name in sorted(QUESTION_CLASSES)}
    for label in labels:
        counts[label.question_class.value] += 1
    return counts


def load_question_class_sidecar(path: Path) -> tuple[QuestionClassLabel, ...]:
    """Parse the sidecar and refuse duplicates or empty reasons."""
    labels: list[QuestionClassLabel] = []
    seen: set[str] = set()
    raw = path.read_text(encoding="utf-8")
    for number, raw_line in enumerate(raw.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise ValueError(f"{path.name}:{number} is not a JSON object")
        try:
            label = QuestionClassLabel.from_mapping(payload)
        except ValueError as error:
            raise ValueError(f"{path.name}:{number}: {error}") from error
        if label.case_id in seen:
            raise ValueError(f"{path.name}:{number} repeats case_id {label.case_id!r}")
        seen.add(label.case_id)
        labels.append(label)
    return tuple(labels)


def _load_dataset_index(path: Path) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    rows: list[tuple[str, str, tuple[str, ...]]] = []
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
        tags = payload.get("tags") or []
        rows.append((case_id, str(payload.get("query", "")), tuple(str(tag) for tag in tags)))
    return tuple(rows)


def _pinned_digest(manifest_path: Path) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pinned = manifest.get("dataset_sha256")
    if not isinstance(pinned, str) or not pinned:
        raise DatasetDigestMismatchError(
            f"{manifest_path.name} has no dataset_sha256 to pin the sidecar against"
        )
    return pinned


def load_classified_cases(
    dataset_path: Path | None = None,
    sidecar_path: Path | None = None,
    manifest_path: Path | None = None,
) -> tuple[ClassifiedCase, ...]:
    """Join the sidecar onto the dataset by ``case_id``.

    Refuses to load when the sidecar's pinned digest disagrees with the
    live dataset, so a later edit of the measured file cannot silently
    inherit these labels.
    """
    dataset = dataset_path or DEFAULT_DATASET_PATH
    sidecar = sidecar_path or DEFAULT_SIDECAR_PATH
    manifest = manifest_path or DEFAULT_MANIFEST_PATH

    pinned = _pinned_digest(manifest)
    actual = dataset_digest(dataset)
    if pinned != actual:
        raise DatasetDigestMismatchError(
            f"question-class sidecar digest drift: pinned dataset_sha256 "
            f"{pinned} but {dataset.as_posix()} digest is {actual}"
        )

    dataset_rows = _load_dataset_index(dataset)
    labels = load_question_class_sidecar(sidecar)
    by_id = {label.case_id: label for label in labels}
    dataset_ids = {case_id for case_id, _query, _tags in dataset_rows}
    sidecar_ids = set(by_id)
    missing = sorted(dataset_ids - sidecar_ids)
    extra = sorted(sidecar_ids - dataset_ids)
    if missing or extra:
        raise ValueError(
            "question-class sidecar case_id set disagrees with the dataset: "
            f"missing={missing} extra={extra}"
        )

    return tuple(
        ClassifiedCase(
            case_id=case_id,
            query=query,
            tags=tags,
            label=by_id[case_id],
        )
        for case_id, query, tags in dataset_rows
    )


def build_manifest(
    dataset_path: Path,
    labels: Sequence[QuestionClassLabel],
    *,
    dataset: str = "evaluation/curated_cases_aircargo.jsonl",
) -> dict[str, Any]:
    counts = question_class_counts(labels)
    approved = sum(1 for label in labels if label.approved_by is not None)
    corpus_class = (
        EvidenceClass.REAL_LABELLED
        if approved == len(labels) and labels
        else EvidenceClass.AGENT_LABELLED
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset": dataset,
        "dataset_sha256": dataset_digest(dataset_path),
        "label_schema_version": LABEL_SCHEMA_VERSION,
        "evidence_class": corpus_class.value,
        "case_count": len(labels),
        "question_class_counts": counts,
    }


__all__ = [
    "DEFAULT_DATASET_PATH",
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_SIDECAR_PATH",
    "LABEL_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "PHASE_C_DATASET_SHA256",
    "QUESTION_CLASSES",
    "ClassifiedCase",
    "DatasetDigestMismatchError",
    "QuestionClass",
    "QuestionClassLabel",
    "build_manifest",
    "load_classified_cases",
    "load_question_class_sidecar",
    "question_class_counts",
]
