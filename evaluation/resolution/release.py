from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation.resolution.comparison import (
    ComparisonInputReference,
    ComparisonRole,
    SyntheticComparisonCompatibilityError,
    SyntheticOutcomeComparisonInput,
    SyntheticOutcomeComparisonReport,
    build_synthetic_outcome_comparison_report,
    synthetic_outcome_comparison_report_digest,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_SCHEMA_VERSION = "resolution-synthetic-release-evidence-manifest/v0.1"
_EVIDENCE_CLASS = "synthetic_local"
_OWNER_STATUS = "unconfirmed"
_DECISION_SEMANTICS = "evidence_only"


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _require_text(value: str, field: str, *, maximum: int = 512) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field} must be non-empty bounded trimmed text")


def _require_id(value: str, field: str) -> None:
    _require_text(value, field, maximum=256)
    if _SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{field} must be a stable safe identifier")


def _require_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


class ReleaseEvidenceIssueCode(StrEnum):
    COMPARISON_REPORT_MISMATCH = "comparison_report_mismatch"
    INPUT_PAIR_INCOMPATIBLE = "input_pair_incompatible"
    INPUT_REFERENCE_MISMATCH = "input_reference_mismatch"
    ROLE_MISMATCH = "role_mismatch"


class SyntheticReleaseEvidenceBindingError(ValueError):
    def __init__(self, issue_codes: tuple[ReleaseEvidenceIssueCode, ...]) -> None:
        if not issue_codes or any(
            not isinstance(code, ReleaseEvidenceIssueCode) for code in issue_codes
        ):
            raise ValueError("release evidence binding errors require issue codes")
        self.issue_codes = tuple(sorted(set(issue_codes), key=lambda code: code.value))
        super().__init__(
            "synthetic release evidence is incompatible: "
            + ", ".join(code.value for code in self.issue_codes)
        )


@dataclass(frozen=True, slots=True)
class SyntheticReleaseEvidenceManifest:
    manifest_id: str
    version: str
    comparison_id: str
    comparison_version: str
    metric_definition_digest: str
    corpus_digest: str
    corpus_case_count: int
    baseline: ComparisonInputReference
    candidate: ComparisonInputReference
    comparison_report_digest: str
    owner_status: str = _OWNER_STATUS
    business_claimable: bool = False
    decision_semantics: str = _DECISION_SEMANTICS
    schema_version: str = _SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.manifest_id, "release evidence manifest_id")
        _require_text(self.version, "release evidence version", maximum=256)
        _require_id(self.comparison_id, "release evidence comparison_id")
        _require_text(
            self.comparison_version,
            "release evidence comparison_version",
            maximum=256,
        )
        _require_digest(
            self.metric_definition_digest,
            "release evidence metric_definition_digest",
        )
        _require_digest(self.corpus_digest, "release evidence corpus_digest")
        _require_digest(
            self.comparison_report_digest,
            "release evidence comparison_report_digest",
        )
        if (
            isinstance(self.corpus_case_count, bool)
            or not isinstance(self.corpus_case_count, int)
            or self.corpus_case_count < 1
        ):
            raise ValueError("release evidence corpus_case_count must be positive")
        if (
            not isinstance(self.baseline, ComparisonInputReference)
            or self.baseline.role is not ComparisonRole.BASELINE
            or not isinstance(self.candidate, ComparisonInputReference)
            or self.candidate.role is not ComparisonRole.CANDIDATE
        ):
            raise ValueError("release evidence input references have invalid roles")
        if self.owner_status != _OWNER_STATUS:
            raise ValueError(f"owner_status must be {_OWNER_STATUS!r}")
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic evidence")
        if self.decision_semantics != _DECISION_SEMANTICS:
            raise ValueError(f"decision_semantics must be {_DECISION_SEMANTICS!r}")
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline.as_dict(),
            "business_claimable": self.business_claimable,
            "candidate": self.candidate.as_dict(),
            "comparison_id": self.comparison_id,
            "comparison_report_digest": self.comparison_report_digest,
            "comparison_version": self.comparison_version,
            "corpus_case_count": self.corpus_case_count,
            "corpus_digest": self.corpus_digest,
            "decision_semantics": self.decision_semantics,
            "evidence_class": self.evidence_class,
            "manifest_id": self.manifest_id,
            "metric_definition_digest": self.metric_definition_digest,
            "owner_status": self.owner_status,
            "schema_version": self.schema_version,
            "version": self.version,
        }


def build_synthetic_release_evidence_manifest(
    *,
    manifest_id: str,
    version: str,
    baseline: SyntheticOutcomeComparisonInput,
    candidate: SyntheticOutcomeComparisonInput,
    comparison: SyntheticOutcomeComparisonReport,
) -> SyntheticReleaseEvidenceManifest:
    if not isinstance(baseline, SyntheticOutcomeComparisonInput) or not isinstance(
        candidate, SyntheticOutcomeComparisonInput
    ):
        raise ValueError("release evidence requires two comparison inputs")
    if not isinstance(comparison, SyntheticOutcomeComparisonReport):
        raise ValueError("comparison must be a SyntheticOutcomeComparisonReport")

    if (
        baseline.role is not ComparisonRole.BASELINE
        or candidate.role is not ComparisonRole.CANDIDATE
    ):
        raise SyntheticReleaseEvidenceBindingError((ReleaseEvidenceIssueCode.ROLE_MISMATCH,))

    try:
        reconstructed = build_synthetic_outcome_comparison_report(
            comparison_id=comparison.comparison_id,
            version=comparison.version,
            baseline=baseline,
            candidate=candidate,
        )
    except SyntheticComparisonCompatibilityError as error:
        raise SyntheticReleaseEvidenceBindingError(
            (ReleaseEvidenceIssueCode.INPUT_PAIR_INCOMPATIBLE,)
        ) from error

    issues: list[ReleaseEvidenceIssueCode] = []
    if (
        comparison.baseline != reconstructed.baseline
        or comparison.candidate != reconstructed.candidate
    ):
        issues.append(ReleaseEvidenceIssueCode.INPUT_REFERENCE_MISMATCH)
    if comparison != reconstructed:
        issues.append(ReleaseEvidenceIssueCode.COMPARISON_REPORT_MISMATCH)
    if issues:
        raise SyntheticReleaseEvidenceBindingError(tuple(issues))

    return SyntheticReleaseEvidenceManifest(
        manifest_id=manifest_id,
        version=version,
        comparison_id=comparison.comparison_id,
        comparison_version=comparison.version,
        metric_definition_digest=comparison.metric_definition_digest,
        corpus_digest=comparison.corpus_digest,
        corpus_case_count=comparison.corpus_case_count,
        baseline=comparison.baseline,
        candidate=comparison.candidate,
        comparison_report_digest=synthetic_outcome_comparison_report_digest(comparison),
    )


def canonical_synthetic_release_evidence_manifest_json(
    manifest: SyntheticReleaseEvidenceManifest,
) -> str:
    if not isinstance(manifest, SyntheticReleaseEvidenceManifest):
        raise ValueError("manifest must be a SyntheticReleaseEvidenceManifest")
    return _canonical_json(manifest.as_dict())


def synthetic_release_evidence_manifest_digest(
    manifest: SyntheticReleaseEvidenceManifest,
) -> str:
    return hashlib.sha256(
        canonical_synthetic_release_evidence_manifest_json(manifest).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ReleaseEvidenceIssueCode",
    "SyntheticReleaseEvidenceBindingError",
    "SyntheticReleaseEvidenceManifest",
    "build_synthetic_release_evidence_manifest",
    "canonical_synthetic_release_evidence_manifest_json",
    "synthetic_release_evidence_manifest_digest",
]
