from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation.resolution.comparison import (
    SyntheticOutcomeComparisonInput,
    SyntheticOutcomeComparisonReport,
)
from evaluation.resolution.release import (
    SyntheticReleaseEvidenceBindingError,
    SyntheticReleaseEvidenceManifest,
    build_synthetic_release_evidence_manifest,
    synthetic_release_evidence_manifest_digest,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_SCHEMA_VERSION = "resolution-synthetic-release-safety-gate-report/v0.1"
_EVIDENCE_CLASS = "synthetic_local"
_OWNER_STATUS = "unconfirmed"
_DECISION_SEMANTICS = "synthetic_safety_only"


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


def _sorted_unique_ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be an immutable tuple")
    for value in values:
        _require_id(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


class ReleaseSafetySurface(StrEnum):
    CONTRACT = "contract"
    POLICY = "policy"
    RETRIEVAL = "retrieval"
    CONNECTOR = "connector"
    POSTCONDITION = "postcondition"
    DISCLOSURE = "disclosure"
    EVALUATOR_INFRASTRUCTURE = "evaluator_infrastructure"


class GateCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


class SyntheticReleaseSafetyStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ReleaseSafetyGateIssueCode(StrEnum):
    CHECK_MANIFEST_MISMATCH = "check_manifest_mismatch"
    CHECK_SET_MISMATCH = "check_set_mismatch"
    RELEASE_EVIDENCE_INVALID = "release_evidence_invalid"
    RELEASE_EVIDENCE_MISMATCH = "release_evidence_mismatch"


class SyntheticReleaseSafetyGateCompatibilityError(ValueError):
    def __init__(self, issue_codes: tuple[ReleaseSafetyGateIssueCode, ...]) -> None:
        if not issue_codes or any(
            not isinstance(code, ReleaseSafetyGateIssueCode) for code in issue_codes
        ):
            raise ValueError("release safety gate compatibility errors require issue codes")
        self.issue_codes = tuple(sorted(set(issue_codes), key=lambda code: code.value))
        super().__init__(
            "synthetic release safety gate is incompatible: "
            + ", ".join(code.value for code in self.issue_codes)
        )


@dataclass(frozen=True, slots=True)
class SyntheticReleaseSafetyCheck:
    surface: ReleaseSafetySurface
    status: GateCheckStatus
    release_evidence_manifest_digest: str
    evidence_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.surface, ReleaseSafetySurface):
            raise ValueError("release safety check surface is unknown")
        if not isinstance(self.status, GateCheckStatus):
            raise ValueError("release safety check status is unknown")
        _require_digest(
            self.release_evidence_manifest_digest,
            "release safety check manifest digest",
        )
        _require_digest(self.evidence_digest, "release safety check evidence digest")

    def as_dict(self) -> dict[str, str]:
        return {
            "evidence_digest": self.evidence_digest,
            "release_evidence_manifest_digest": self.release_evidence_manifest_digest,
            "status": self.status.value,
            "surface": self.surface.value,
        }


def _check_sort_key(check: SyntheticReleaseSafetyCheck) -> str:
    return check.surface.value


@dataclass(frozen=True, slots=True)
class SyntheticReleaseSafetyGateReport:
    gate_id: str
    version: str
    release_evidence_manifest_digest: str
    candidate_input_digest: str
    candidate_outcome_report_digest: str
    unverified_claimed_scenario_ids: tuple[str, ...]
    safety_status: SyntheticReleaseSafetyStatus
    failed_surfaces: tuple[ReleaseSafetySurface, ...]
    checks: tuple[SyntheticReleaseSafetyCheck, ...]
    owner_status: str = _OWNER_STATUS
    business_claimable: bool = False
    deployment_authorized: bool = False
    decision_semantics: str = _DECISION_SEMANTICS
    schema_version: str = _SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.gate_id, "release safety gate_id")
        _require_text(self.version, "release safety gate version", maximum=256)
        _require_digest(
            self.release_evidence_manifest_digest,
            "release safety gate manifest digest",
        )
        _require_digest(
            self.candidate_input_digest,
            "release safety gate candidate input digest",
        )
        _require_digest(
            self.candidate_outcome_report_digest,
            "release safety gate candidate outcome report digest",
        )
        object.__setattr__(
            self,
            "unverified_claimed_scenario_ids",
            _sorted_unique_ids(
                self.unverified_claimed_scenario_ids,
                "release safety gate unverified claimed scenario IDs",
            ),
        )
        if not isinstance(self.safety_status, SyntheticReleaseSafetyStatus):
            raise ValueError("release safety_status is unknown")
        if not isinstance(self.checks, tuple) or any(
            not isinstance(check, SyntheticReleaseSafetyCheck) for check in self.checks
        ):
            raise ValueError("release safety checks must be an immutable check tuple")
        surfaces = tuple(check.surface for check in self.checks)
        if len(surfaces) != len(ReleaseSafetySurface) or set(surfaces) != set(ReleaseSafetySurface):
            raise ValueError("release safety checks must contain every surface exactly once")
        if any(
            check.release_evidence_manifest_digest != self.release_evidence_manifest_digest
            for check in self.checks
        ):
            raise ValueError("release safety checks must bind the exact manifest")
        object.__setattr__(self, "checks", tuple(sorted(self.checks, key=_check_sort_key)))

        if not isinstance(self.failed_surfaces, tuple) or any(
            not isinstance(surface, ReleaseSafetySurface) for surface in self.failed_surfaces
        ):
            raise ValueError("failed_surfaces must be an immutable safety-surface tuple")
        supplied_failed = tuple(
            sorted(set(self.failed_surfaces), key=lambda surface: surface.value)
        )
        derived_failed = tuple(
            sorted(
                (
                    check.surface
                    for check in self.checks
                    if check.status is not GateCheckStatus.PASS
                ),
                key=lambda surface: surface.value,
            )
        )
        if supplied_failed != derived_failed:
            raise ValueError("failed_surfaces must match every non-pass check")
        object.__setattr__(self, "failed_surfaces", supplied_failed)
        expected_status = (
            SyntheticReleaseSafetyStatus.FAIL
            if derived_failed or self.unverified_claimed_scenario_ids
            else SyntheticReleaseSafetyStatus.PASS
        )
        if self.safety_status is not expected_status:
            raise ValueError("safety_status must be derived from non-pass checks")
        if self.owner_status != _OWNER_STATUS:
            raise ValueError(f"owner_status must be {_OWNER_STATUS!r}")
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic safety")
        if self.deployment_authorized is not False:
            raise ValueError("deployment_authorized must remain false for synthetic safety")
        if self.decision_semantics != _DECISION_SEMANTICS:
            raise ValueError(f"decision_semantics must be {_DECISION_SEMANTICS!r}")
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "business_claimable": self.business_claimable,
            "candidate_input_digest": self.candidate_input_digest,
            "candidate_outcome_report_digest": self.candidate_outcome_report_digest,
            "checks": [check.as_dict() for check in self.checks],
            "decision_semantics": self.decision_semantics,
            "deployment_authorized": self.deployment_authorized,
            "evidence_class": self.evidence_class,
            "failed_surfaces": [surface.value for surface in self.failed_surfaces],
            "gate_id": self.gate_id,
            "owner_status": self.owner_status,
            "release_evidence_manifest_digest": self.release_evidence_manifest_digest,
            "safety_status": self.safety_status.value,
            "schema_version": self.schema_version,
            "unverified_claimed_scenario_count": len(self.unverified_claimed_scenario_ids),
            "unverified_claimed_scenario_ids": list(self.unverified_claimed_scenario_ids),
            "version": self.version,
        }


def build_synthetic_release_safety_gate_report(
    *,
    gate_id: str,
    version: str,
    release_evidence_manifest: SyntheticReleaseEvidenceManifest,
    baseline: SyntheticOutcomeComparisonInput,
    candidate: SyntheticOutcomeComparisonInput,
    comparison: SyntheticOutcomeComparisonReport,
    checks: tuple[SyntheticReleaseSafetyCheck, ...],
) -> SyntheticReleaseSafetyGateReport:
    if not isinstance(release_evidence_manifest, SyntheticReleaseEvidenceManifest):
        raise ValueError("release_evidence_manifest has an invalid type")
    if not isinstance(baseline, SyntheticOutcomeComparisonInput) or not isinstance(
        candidate, SyntheticOutcomeComparisonInput
    ):
        raise ValueError("release safety gate requires two comparison inputs")
    if not isinstance(comparison, SyntheticOutcomeComparisonReport):
        raise ValueError("comparison must be a SyntheticOutcomeComparisonReport")
    if not isinstance(checks, tuple) or any(
        not isinstance(check, SyntheticReleaseSafetyCheck) for check in checks
    ):
        raise ValueError("checks must be an immutable release-safety check tuple")

    issues: list[ReleaseSafetyGateIssueCode] = []
    try:
        reconstructed_manifest = build_synthetic_release_evidence_manifest(
            manifest_id=release_evidence_manifest.manifest_id,
            version=release_evidence_manifest.version,
            baseline=baseline,
            candidate=candidate,
            comparison=comparison,
        )
    except SyntheticReleaseEvidenceBindingError:
        issues.append(ReleaseSafetyGateIssueCode.RELEASE_EVIDENCE_INVALID)
    else:
        if reconstructed_manifest != release_evidence_manifest:
            issues.append(ReleaseSafetyGateIssueCode.RELEASE_EVIDENCE_MISMATCH)

    surfaces = tuple(check.surface for check in checks)
    if len(surfaces) != len(ReleaseSafetySurface) or set(surfaces) != set(ReleaseSafetySurface):
        issues.append(ReleaseSafetyGateIssueCode.CHECK_SET_MISMATCH)
    release_manifest_digest = synthetic_release_evidence_manifest_digest(release_evidence_manifest)
    if any(check.release_evidence_manifest_digest != release_manifest_digest for check in checks):
        issues.append(ReleaseSafetyGateIssueCode.CHECK_MANIFEST_MISMATCH)
    if issues:
        raise SyntheticReleaseSafetyGateCompatibilityError(tuple(issues))

    failed_surfaces = tuple(
        check.surface for check in checks if check.status is not GateCheckStatus.PASS
    )
    return SyntheticReleaseSafetyGateReport(
        gate_id=gate_id,
        version=version,
        release_evidence_manifest_digest=release_manifest_digest,
        candidate_input_digest=release_evidence_manifest.candidate.input_digest,
        candidate_outcome_report_digest=release_evidence_manifest.candidate.report_digest,
        unverified_claimed_scenario_ids=(candidate.report.unverified_claimed_scenario_ids),
        safety_status=(
            SyntheticReleaseSafetyStatus.FAIL
            if failed_surfaces or candidate.report.unverified_claimed_scenario_ids
            else SyntheticReleaseSafetyStatus.PASS
        ),
        failed_surfaces=failed_surfaces,
        checks=checks,
    )


def canonical_synthetic_release_safety_gate_report_json(
    report: SyntheticReleaseSafetyGateReport,
) -> str:
    if not isinstance(report, SyntheticReleaseSafetyGateReport):
        raise ValueError("report must be a SyntheticReleaseSafetyGateReport")
    return _canonical_json(report.as_dict())


def synthetic_release_safety_gate_report_digest(
    report: SyntheticReleaseSafetyGateReport,
) -> str:
    return hashlib.sha256(
        canonical_synthetic_release_safety_gate_report_json(report).encode("utf-8")
    ).hexdigest()


__all__ = [
    "GateCheckStatus",
    "ReleaseSafetyGateIssueCode",
    "ReleaseSafetySurface",
    "SyntheticReleaseSafetyCheck",
    "SyntheticReleaseSafetyGateCompatibilityError",
    "SyntheticReleaseSafetyGateReport",
    "SyntheticReleaseSafetyStatus",
    "build_synthetic_release_safety_gate_report",
    "canonical_synthetic_release_safety_gate_report_json",
    "synthetic_release_safety_gate_report_digest",
]
