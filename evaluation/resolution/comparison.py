from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation.resolution.corpus import (
    CompiledResolutionScenarioCorpus,
    ManifestCoverageReport,
)
from evaluation.resolution.outcomes import (
    EligibilityDisposition,
    MetricKind,
    OutcomeMetric,
    ResolutionDisposition,
    SyntheticMetricDefinition,
    SyntheticOutcomeLedger,
    SyntheticOutcomeRecord,
    SyntheticOutcomeReport,
    build_synthetic_outcome_report,
    metric_definition_digest,
    synthetic_outcome_ledger_digest,
    synthetic_outcome_report_digest,
)
from evaluation.resolution.replay import ReplayManifest
from evaluation.resolution.trials import ReplayExecutionResult, ReplayPlan

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_INPUT_SCHEMA_VERSION = "resolution-synthetic-outcome-comparison-input/v0.1"
_REPORT_SCHEMA_VERSION = "resolution-synthetic-outcome-comparison-report/v0.1"
_EVIDENCE_CLASS = "synthetic_local"
_OWNER_STATUS = "unconfirmed"


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


class ComparisonRole(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"


class ComparisonIssueCode(StrEnum):
    INPUT_BINDING_MISMATCH = "input_binding_mismatch"
    INPUT_NOT_STRUCTURALLY_COMPLETE = "input_not_structurally_complete"
    ROLE_MISMATCH = "role_mismatch"
    METRIC_DEFINITION_MISMATCH = "metric_definition_mismatch"
    CORPUS_UNIVERSE_MISMATCH = "corpus_universe_mismatch"


class SyntheticComparisonCompatibilityError(ValueError):
    def __init__(self, issue_codes: tuple[ComparisonIssueCode, ...]) -> None:
        if not issue_codes or any(
            not isinstance(code, ComparisonIssueCode) for code in issue_codes
        ):
            raise ValueError("comparison compatibility errors require issue codes")
        self.issue_codes = tuple(sorted(set(issue_codes), key=lambda code: code.value))
        super().__init__(
            "synthetic outcome comparison is incompatible: "
            + ", ".join(code.value for code in self.issue_codes)
        )


@dataclass(frozen=True, slots=True)
class SyntheticOutcomeComparisonInput:
    role: ComparisonRole
    input_id: str
    version: str
    definition: SyntheticMetricDefinition
    ledger: SyntheticOutcomeLedger
    report: SyntheticOutcomeReport
    business_claimable: bool = False
    schema_version: str = _INPUT_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        if not isinstance(self.role, ComparisonRole):
            raise ValueError("comparison input role is unknown")
        _require_id(self.input_id, "comparison input_id")
        _require_text(self.version, "comparison input version", maximum=256)
        if not isinstance(self.definition, SyntheticMetricDefinition):
            raise ValueError("definition must be a SyntheticMetricDefinition")
        if not isinstance(self.ledger, SyntheticOutcomeLedger):
            raise ValueError("ledger must be a SyntheticOutcomeLedger")
        if not isinstance(self.report, SyntheticOutcomeReport):
            raise ValueError("report must be a SyntheticOutcomeReport")
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic comparison")
        if self.schema_version != _INPUT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_INPUT_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

        issues: list[ComparisonIssueCode] = []
        definition_digest = metric_definition_digest(self.definition)
        ledger_digest = synthetic_outcome_ledger_digest(self.ledger)
        if (
            self.ledger.metric_definition_digest != definition_digest
            or self.report.metric_definition_digest != definition_digest
            or self.report.ledger_digest != ledger_digest
            or self.ledger.manifest_digest != self.report.manifest_digest
            or self.ledger.corpus_digest != self.report.corpus_digest
            or self.ledger.coverage_report_digest != self.report.coverage_report_digest
            or self.ledger.replay_plan_digest != self.report.replay_plan_digest
            or self.ledger.replay_result_digest != self.report.replay_result_digest
        ):
            issues.append(ComparisonIssueCode.INPUT_BINDING_MISMATCH)

        record_ids = tuple(record.scenario_id for record in self.ledger.records)
        claimed_ids = {
            record.scenario_id
            for record in self.ledger.records
            if record.resolution is ResolutionDisposition.CLAIMED_AUTO
        }
        reported_claimed_ids = set(self.report.verified_scenario_ids) | set(
            self.report.unverified_claimed_scenario_ids
        )
        if (
            len(record_ids) != len(set(record_ids))
            or len(record_ids) != self.report.corpus_case_count
            or claimed_ids != reported_claimed_ids
        ):
            issues.append(ComparisonIssueCode.INPUT_BINDING_MISMATCH)

        records_by_id = {record.scenario_id: record for record in self.ledger.records}
        if any(
            scenario_id not in records_by_id
            or records_by_id[scenario_id].eligibility is not EligibilityDisposition.ELIGIBLE
            or records_by_id[scenario_id].resolution is not ResolutionDisposition.CLAIMED_AUTO
            or not records_by_id[scenario_id].checks_passed
            for scenario_id in self.report.verified_scenario_ids
        ):
            issues.append(ComparisonIssueCode.INPUT_BINDING_MISMATCH)

        if (
            not self.report.structurally_complete
            or any(
                metric.kind is MetricKind.LOWER_BOUND
                for metric in (
                    self.report.vr_precision,
                    self.report.vry,
                    self.report.eligibility_coverage,
                )
            )
            or any(
                record.eligibility is EligibilityDisposition.UNKNOWN
                or record.resolution is ResolutionDisposition.UNKNOWN
                or record.has_unknown_check
                for record in self.ledger.records
            )
        ):
            issues.append(ComparisonIssueCode.INPUT_NOT_STRUCTURALLY_COMPLETE)
        if issues:
            raise SyntheticComparisonCompatibilityError(tuple(issues))

    @property
    def metric_definition_digest(self) -> str:
        return metric_definition_digest(self.definition)

    @property
    def corpus_digest(self) -> str:
        return self.ledger.corpus_digest

    @property
    def corpus_case_count(self) -> int:
        return self.report.corpus_case_count

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(record.scenario_id for record in self.ledger.records)

    def as_dict(self) -> dict[str, object]:
        return {
            "business_claimable": self.business_claimable,
            "definition": self.definition.as_dict(),
            "evidence_class": self.evidence_class,
            "input_id": self.input_id,
            "ledger": self.ledger.as_dict(),
            "report": self.report.as_dict(),
            "role": self.role.value,
            "schema_version": self.schema_version,
            "version": self.version,
        }


class VerificationDisposition(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class SyntheticCaseDisposition:
    eligibility: EligibilityDisposition
    resolution: ResolutionDisposition
    verification: VerificationDisposition

    def __post_init__(self) -> None:
        if not isinstance(self.eligibility, EligibilityDisposition) or self.eligibility not in {
            EligibilityDisposition.ELIGIBLE,
            EligibilityDisposition.INELIGIBLE,
        }:
            raise ValueError("comparison eligibility disposition must be exact")
        if not isinstance(self.resolution, ResolutionDisposition) or self.resolution not in {
            ResolutionDisposition.CLAIMED_AUTO,
            ResolutionDisposition.NOT_CLAIMED,
        }:
            raise ValueError("comparison resolution disposition must be exact")
        if not isinstance(self.verification, VerificationDisposition):
            raise ValueError("comparison verification disposition is unknown")
        if self.resolution is ResolutionDisposition.CLAIMED_AUTO:
            if self.verification is VerificationDisposition.NOT_APPLICABLE:
                raise ValueError("claimed cases require a verification disposition")
        elif self.verification is not VerificationDisposition.NOT_APPLICABLE:
            raise ValueError("not-claimed cases cannot have a verification disposition")
        if (
            self.verification is VerificationDisposition.VERIFIED
            and self.eligibility is not EligibilityDisposition.ELIGIBLE
        ):
            raise ValueError("verified cases must be eligible")

    def as_dict(self) -> dict[str, str]:
        return {
            "eligibility": self.eligibility.value,
            "resolution": self.resolution.value,
            "verification": self.verification.value,
        }


@dataclass(frozen=True, slots=True)
class SyntheticCaseTransition:
    baseline: SyntheticCaseDisposition
    candidate: SyntheticCaseDisposition
    scenario_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, SyntheticCaseDisposition) or not isinstance(
            self.candidate, SyntheticCaseDisposition
        ):
            raise ValueError("case transitions require two dispositions")
        if not isinstance(self.scenario_ids, tuple) or not self.scenario_ids:
            raise ValueError("case transition scenario_ids must be a non-empty tuple")
        for scenario_id in self.scenario_ids:
            _require_id(scenario_id, "case transition scenario_id")
        if len(self.scenario_ids) != len(set(self.scenario_ids)):
            raise ValueError("case transition scenario_ids must be unique")
        object.__setattr__(self, "scenario_ids", tuple(sorted(self.scenario_ids)))

    @property
    def count(self) -> int:
        return len(self.scenario_ids)

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline.as_dict(),
            "candidate": self.candidate.as_dict(),
            "count": self.count,
            "scenario_ids": list(self.scenario_ids),
        }


@dataclass(frozen=True, slots=True)
class OutcomeCountPairDelta:
    baseline: OutcomeMetric
    candidate: OutcomeMetric

    def __post_init__(self) -> None:
        if not isinstance(self.baseline, OutcomeMetric) or not isinstance(
            self.candidate, OutcomeMetric
        ):
            raise ValueError("count-pair delta requires two outcome metrics")
        if (
            self.baseline.kind is MetricKind.LOWER_BOUND
            or self.candidate.kind is MetricKind.LOWER_BOUND
        ):
            raise ValueError("count-pair delta cannot compare incomplete metrics")

    @property
    def numerator_delta(self) -> int:
        return self.candidate.numerator - self.baseline.numerator

    @property
    def denominator_delta(self) -> int:
        return self.candidate.denominator - self.baseline.denominator

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline.as_dict(),
            "candidate": self.candidate.as_dict(),
            "denominator_delta": self.denominator_delta,
            "numerator_delta": self.numerator_delta,
        }


@dataclass(frozen=True, slots=True)
class ComparisonInputReference:
    role: ComparisonRole
    input_digest: str
    ledger_digest: str
    report_digest: str
    manifest_digest: str
    coverage_report_digest: str
    replay_plan_digest: str
    replay_result_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ComparisonRole):
            raise ValueError("comparison input reference role is unknown")
        for field, value in (
            ("input_digest", self.input_digest),
            ("ledger_digest", self.ledger_digest),
            ("report_digest", self.report_digest),
            ("manifest_digest", self.manifest_digest),
            ("coverage_report_digest", self.coverage_report_digest),
            ("replay_plan_digest", self.replay_plan_digest),
            ("replay_result_digest", self.replay_result_digest),
        ):
            _require_digest(value, f"comparison input reference {field}")

    def as_dict(self) -> dict[str, str]:
        return {
            "coverage_report_digest": self.coverage_report_digest,
            "input_digest": self.input_digest,
            "ledger_digest": self.ledger_digest,
            "manifest_digest": self.manifest_digest,
            "replay_plan_digest": self.replay_plan_digest,
            "replay_result_digest": self.replay_result_digest,
            "report_digest": self.report_digest,
            "role": self.role.value,
        }


def _transition_sort_key(
    transition: SyntheticCaseTransition,
) -> tuple[str, str, str, str, str, str]:
    return (
        transition.baseline.eligibility.value,
        transition.baseline.resolution.value,
        transition.baseline.verification.value,
        transition.candidate.eligibility.value,
        transition.candidate.resolution.value,
        transition.candidate.verification.value,
    )


@dataclass(frozen=True, slots=True)
class SyntheticOutcomeComparisonReport:
    comparison_id: str
    version: str
    metric_definition_digest: str
    corpus_digest: str
    corpus_case_count: int
    baseline: ComparisonInputReference
    candidate: ComparisonInputReference
    vr_precision: OutcomeCountPairDelta
    vry: OutcomeCountPairDelta
    eligibility_coverage: OutcomeCountPairDelta
    case_transitions: tuple[SyntheticCaseTransition, ...]
    owner_status: str = _OWNER_STATUS
    business_claimable: bool = False
    schema_version: str = _REPORT_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.comparison_id, "comparison_id")
        _require_text(self.version, "comparison version", maximum=256)
        _require_digest(self.metric_definition_digest, "comparison metric definition digest")
        _require_digest(self.corpus_digest, "comparison corpus digest")
        if (
            isinstance(self.corpus_case_count, bool)
            or not isinstance(self.corpus_case_count, int)
            or self.corpus_case_count < 1
        ):
            raise ValueError("comparison corpus_case_count must be positive")
        if (
            not isinstance(self.baseline, ComparisonInputReference)
            or self.baseline.role is not ComparisonRole.BASELINE
            or not isinstance(self.candidate, ComparisonInputReference)
            or self.candidate.role is not ComparisonRole.CANDIDATE
        ):
            raise ValueError("comparison input references have invalid roles")
        for metric in (self.vr_precision, self.vry, self.eligibility_coverage):
            if not isinstance(metric, OutcomeCountPairDelta):
                raise ValueError("comparison metrics must be count-pair deltas")
        if not isinstance(self.case_transitions, tuple) or not self.case_transitions:
            raise ValueError("case_transitions must be a non-empty immutable tuple")
        if any(
            not isinstance(transition, SyntheticCaseTransition)
            for transition in self.case_transitions
        ):
            raise ValueError("case_transitions contain an invalid value")
        transition_keys = {
            (transition.baseline, transition.candidate) for transition in self.case_transitions
        }
        if len(transition_keys) != len(self.case_transitions):
            raise ValueError("case_transitions contain a duplicate disposition pair")
        object.__setattr__(
            self,
            "case_transitions",
            tuple(sorted(self.case_transitions, key=_transition_sort_key)),
        )
        scenario_ids = tuple(
            scenario_id
            for transition in self.case_transitions
            for scenario_id in transition.scenario_ids
        )
        if len(scenario_ids) != self.corpus_case_count or len(scenario_ids) != len(
            set(scenario_ids)
        ):
            raise ValueError("case transitions must partition the full corpus exactly once")

        baseline_verified = sum(
            transition.count
            for transition in self.case_transitions
            if transition.baseline.verification is VerificationDisposition.VERIFIED
        )
        candidate_verified = sum(
            transition.count
            for transition in self.case_transitions
            if transition.candidate.verification is VerificationDisposition.VERIFIED
        )
        baseline_claimed = sum(
            transition.count
            for transition in self.case_transitions
            if transition.baseline.resolution is ResolutionDisposition.CLAIMED_AUTO
        )
        candidate_claimed = sum(
            transition.count
            for transition in self.case_transitions
            if transition.candidate.resolution is ResolutionDisposition.CLAIMED_AUTO
        )
        baseline_eligible = sum(
            transition.count
            for transition in self.case_transitions
            if transition.baseline.eligibility is EligibilityDisposition.ELIGIBLE
        )
        candidate_eligible = sum(
            transition.count
            for transition in self.case_transitions
            if transition.candidate.eligibility is EligibilityDisposition.ELIGIBLE
        )
        expected_counts = (
            (self.vr_precision.baseline.numerator, baseline_verified),
            (self.vr_precision.candidate.numerator, candidate_verified),
            (self.vr_precision.baseline.denominator, baseline_claimed),
            (self.vr_precision.candidate.denominator, candidate_claimed),
            (self.vry.baseline.numerator, baseline_verified),
            (self.vry.candidate.numerator, candidate_verified),
            (self.vry.baseline.denominator, baseline_eligible),
            (self.vry.candidate.denominator, candidate_eligible),
            (self.eligibility_coverage.baseline.numerator, baseline_eligible),
            (self.eligibility_coverage.candidate.numerator, candidate_eligible),
            (
                self.eligibility_coverage.baseline.denominator,
                self.corpus_case_count,
            ),
            (
                self.eligibility_coverage.candidate.denominator,
                self.corpus_case_count,
            ),
        )
        if any(actual != expected for actual, expected in expected_counts):
            raise ValueError("comparison metrics do not match case dispositions")
        if self.owner_status != _OWNER_STATUS:
            raise ValueError(f"owner_status must be {_OWNER_STATUS!r}")
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic comparison")
        if self.schema_version != _REPORT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_REPORT_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline.as_dict(),
            "business_claimable": self.business_claimable,
            "candidate": self.candidate.as_dict(),
            "case_transitions": [transition.as_dict() for transition in self.case_transitions],
            "comparison_id": self.comparison_id,
            "corpus_case_count": self.corpus_case_count,
            "corpus_digest": self.corpus_digest,
            "eligibility_coverage": self.eligibility_coverage.as_dict(),
            "evidence_class": self.evidence_class,
            "metric_definition_digest": self.metric_definition_digest,
            "owner_status": self.owner_status,
            "schema_version": self.schema_version,
            "synthetic_case_unit": "scenario",
            "version": self.version,
            "vr_precision": self.vr_precision.as_dict(),
            "vry": self.vry.as_dict(),
        }


def build_synthetic_outcome_comparison_input(
    *,
    role: ComparisonRole,
    input_id: str,
    version: str,
    definition: SyntheticMetricDefinition,
    corpus: CompiledResolutionScenarioCorpus,
    manifest: ReplayManifest,
    coverage_report: ManifestCoverageReport,
    plan: ReplayPlan,
    replay_result: ReplayExecutionResult,
    ledger: SyntheticOutcomeLedger,
) -> SyntheticOutcomeComparisonInput:
    report = build_synthetic_outcome_report(
        definition=definition,
        corpus=corpus,
        manifest=manifest,
        coverage_report=coverage_report,
        plan=plan,
        replay_result=replay_result,
        ledger=ledger,
    )
    return SyntheticOutcomeComparisonInput(
        role=role,
        input_id=input_id,
        version=version,
        definition=definition,
        ledger=ledger,
        report=report,
    )


def _input_reference(
    comparison_input: SyntheticOutcomeComparisonInput,
) -> ComparisonInputReference:
    return ComparisonInputReference(
        role=comparison_input.role,
        input_digest=synthetic_outcome_comparison_input_digest(comparison_input),
        ledger_digest=synthetic_outcome_ledger_digest(comparison_input.ledger),
        report_digest=synthetic_outcome_report_digest(comparison_input.report),
        manifest_digest=comparison_input.report.manifest_digest,
        coverage_report_digest=comparison_input.report.coverage_report_digest,
        replay_plan_digest=comparison_input.report.replay_plan_digest,
        replay_result_digest=comparison_input.report.replay_result_digest,
    )


def _case_disposition(
    record: SyntheticOutcomeRecord,
    report: SyntheticOutcomeReport,
) -> SyntheticCaseDisposition:
    if record.resolution is ResolutionDisposition.CLAIMED_AUTO:
        verification = (
            VerificationDisposition.VERIFIED
            if record.scenario_id in report.verified_scenario_ids
            else VerificationDisposition.UNVERIFIED
        )
    else:
        verification = VerificationDisposition.NOT_APPLICABLE
    return SyntheticCaseDisposition(
        eligibility=record.eligibility,
        resolution=record.resolution,
        verification=verification,
    )


def build_synthetic_outcome_comparison_report(
    *,
    comparison_id: str,
    version: str,
    baseline: SyntheticOutcomeComparisonInput,
    candidate: SyntheticOutcomeComparisonInput,
) -> SyntheticOutcomeComparisonReport:
    if not isinstance(baseline, SyntheticOutcomeComparisonInput) or not isinstance(
        candidate, SyntheticOutcomeComparisonInput
    ):
        raise ValueError("comparison requires two SyntheticOutcomeComparisonInput values")
    issues: list[ComparisonIssueCode] = []
    if (
        baseline.role is not ComparisonRole.BASELINE
        or candidate.role is not ComparisonRole.CANDIDATE
    ):
        issues.append(ComparisonIssueCode.ROLE_MISMATCH)
    if (
        baseline.metric_definition_digest != candidate.metric_definition_digest
        or baseline.definition != candidate.definition
    ):
        issues.append(ComparisonIssueCode.METRIC_DEFINITION_MISMATCH)
    if (
        baseline.corpus_digest != candidate.corpus_digest
        or baseline.corpus_case_count != candidate.corpus_case_count
        or set(baseline.scenario_ids) != set(candidate.scenario_ids)
    ):
        issues.append(ComparisonIssueCode.CORPUS_UNIVERSE_MISMATCH)
    if issues:
        raise SyntheticComparisonCompatibilityError(tuple(issues))

    baseline_records = {record.scenario_id: record for record in baseline.ledger.records}
    candidate_records = {record.scenario_id: record for record in candidate.ledger.records}
    grouped: dict[
        tuple[SyntheticCaseDisposition, SyntheticCaseDisposition],
        list[str],
    ] = {}
    for scenario_id in baseline.scenario_ids:
        baseline_disposition = _case_disposition(baseline_records[scenario_id], baseline.report)
        candidate_disposition = _case_disposition(candidate_records[scenario_id], candidate.report)
        grouped.setdefault((baseline_disposition, candidate_disposition), []).append(scenario_id)
    transitions = tuple(
        SyntheticCaseTransition(
            baseline=baseline_disposition,
            candidate=candidate_disposition,
            scenario_ids=tuple(scenario_ids),
        )
        for (baseline_disposition, candidate_disposition), scenario_ids in grouped.items()
    )
    return SyntheticOutcomeComparisonReport(
        comparison_id=comparison_id,
        version=version,
        metric_definition_digest=baseline.metric_definition_digest,
        corpus_digest=baseline.corpus_digest,
        corpus_case_count=baseline.corpus_case_count,
        baseline=_input_reference(baseline),
        candidate=_input_reference(candidate),
        vr_precision=OutcomeCountPairDelta(
            baseline=baseline.report.vr_precision,
            candidate=candidate.report.vr_precision,
        ),
        vry=OutcomeCountPairDelta(
            baseline=baseline.report.vry,
            candidate=candidate.report.vry,
        ),
        eligibility_coverage=OutcomeCountPairDelta(
            baseline=baseline.report.eligibility_coverage,
            candidate=candidate.report.eligibility_coverage,
        ),
        case_transitions=transitions,
    )


def canonical_synthetic_outcome_comparison_input_json(
    comparison_input: SyntheticOutcomeComparisonInput,
) -> str:
    if not isinstance(comparison_input, SyntheticOutcomeComparisonInput):
        raise ValueError("comparison_input must be a SyntheticOutcomeComparisonInput")
    return _canonical_json(comparison_input.as_dict())


def synthetic_outcome_comparison_input_digest(
    comparison_input: SyntheticOutcomeComparisonInput,
) -> str:
    return hashlib.sha256(
        canonical_synthetic_outcome_comparison_input_json(comparison_input).encode("utf-8")
    ).hexdigest()


def canonical_synthetic_outcome_comparison_report_json(
    report: SyntheticOutcomeComparisonReport,
) -> str:
    if not isinstance(report, SyntheticOutcomeComparisonReport):
        raise ValueError("report must be a SyntheticOutcomeComparisonReport")
    return _canonical_json(report.as_dict())


def synthetic_outcome_comparison_report_digest(
    report: SyntheticOutcomeComparisonReport,
) -> str:
    return hashlib.sha256(
        canonical_synthetic_outcome_comparison_report_json(report).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ComparisonInputReference",
    "ComparisonIssueCode",
    "ComparisonRole",
    "OutcomeCountPairDelta",
    "SyntheticCaseDisposition",
    "SyntheticCaseTransition",
    "SyntheticComparisonCompatibilityError",
    "SyntheticOutcomeComparisonInput",
    "SyntheticOutcomeComparisonReport",
    "VerificationDisposition",
    "build_synthetic_outcome_comparison_input",
    "build_synthetic_outcome_comparison_report",
    "canonical_synthetic_outcome_comparison_input_json",
    "canonical_synthetic_outcome_comparison_report_json",
    "synthetic_outcome_comparison_input_digest",
    "synthetic_outcome_comparison_report_digest",
]
