from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation.resolution.corpus import (
    CompiledResolutionScenarioCorpus,
    ManifestCoverageReport,
    build_manifest_coverage_report,
    compiled_corpus_pin,
    corpus_digest,
    manifest_coverage_report_digest,
)
from evaluation.resolution.replay import (
    ReplayManifest,
    replay_manifest_digest,
    scenario_binding_digest,
)
from evaluation.resolution.trials import (
    ReplayExecutionResult,
    ReplayPlan,
    TrialStatus,
    derive_trial_seed,
    replay_plan_digest,
    replay_result_digest,
    replay_trial_digest,
    summarize_trial_records,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_DEFINITION_SCHEMA_VERSION = "resolution-synthetic-metric-definition/v0.1"
_RECORD_SCHEMA_VERSION = "resolution-synthetic-outcome-record/v0.1"
_LEDGER_SCHEMA_VERSION = "resolution-synthetic-outcome-ledger/v0.1"
_REPORT_SCHEMA_VERSION = "resolution-synthetic-outcome-report/v0.1"
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


def _sorted_unique_ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be an immutable tuple")
    for value in values:
        _require_id(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


class OutcomeCheckCode(StrEnum):
    CONTRACT_OR_ALLOWED_PATH = "contract_or_allowed_path"
    REQUIRED_INPUTS_EVIDENCE_VALID = "required_inputs_evidence_valid"
    MATERIAL_CLAIMS_SUPPORTED = "material_claims_supported"
    ACTIONS_AUTHORIZED_AND_CONFIRMED = "actions_authorized_and_confirmed"
    POSTCONDITIONS_MET = "postconditions_met"
    NO_CRITICAL_VIOLATION = "no_critical_violation"
    NO_RECONTACT_IN_WINDOW = "no_recontact_in_window"


class OutcomeCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class EligibilityDisposition(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class ResolutionDisposition(StrEnum):
    CLAIMED_AUTO = "claimed_auto"
    NOT_CLAIMED = "not_claimed"
    UNKNOWN = "unknown"


class MetricKind(StrEnum):
    EXACT = "exact"
    LOWER_BOUND = "lower_bound"
    UNDEFINED = "undefined"


@dataclass(frozen=True, slots=True)
class SyntheticMetricDefinition:
    definition_id: str
    version: str
    recontact_window_days: int
    required_checks: tuple[OutcomeCheckCode, ...] = tuple(OutcomeCheckCode)
    owner_status: str = _OWNER_STATUS
    business_claimable: bool = False
    schema_version: str = _DEFINITION_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.definition_id, "metric definition_id")
        _require_text(self.version, "metric definition version", maximum=256)
        if (
            isinstance(self.recontact_window_days, bool)
            or not isinstance(self.recontact_window_days, int)
            or not 1 <= self.recontact_window_days <= 365
        ):
            raise ValueError("recontact_window_days must be an integer in [1, 365]")
        if not isinstance(self.required_checks, tuple) or any(
            not isinstance(code, OutcomeCheckCode) for code in self.required_checks
        ):
            raise ValueError("required_checks must be an immutable outcome-check tuple")
        if len(self.required_checks) != len(set(self.required_checks)) or set(
            self.required_checks
        ) != set(OutcomeCheckCode):
            raise ValueError("required_checks must contain every required outcome check")
        object.__setattr__(
            self,
            "required_checks",
            tuple(sorted(self.required_checks, key=lambda code: code.value)),
        )
        if self.owner_status != _OWNER_STATUS:
            raise ValueError(f"owner_status must be {_OWNER_STATUS!r}")
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic metrics")
        if self.schema_version != _DEFINITION_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_DEFINITION_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "business_claimable": self.business_claimable,
            "definition_id": self.definition_id,
            "eligibility_coverage_formula": "confirmed_eligible/all_corpus_cases",
            "evidence_class": self.evidence_class,
            "owner_status": self.owner_status,
            "recontact_window_days": self.recontact_window_days,
            "required_checks": [code.value for code in self.required_checks],
            "schema_version": self.schema_version,
            "unknown_denominator_policy": "presume_eligible_and_claimed",
            "version": self.version,
            "vr_precision_formula": "verified_claimed_auto/all_claimed_auto",
            "vry_formula": "verified_claimed_auto/all_eligible_cases",
        }


@dataclass(frozen=True, order=True, slots=True)
class OutcomeCheckResult:
    code: OutcomeCheckCode
    status: OutcomeCheckStatus

    def __post_init__(self) -> None:
        if not isinstance(self.code, OutcomeCheckCode):
            raise ValueError("outcome check code is unknown")
        if not isinstance(self.status, OutcomeCheckStatus):
            raise ValueError("outcome check status is unknown")

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "status": self.status.value}


@dataclass(frozen=True, slots=True)
class SyntheticOutcomeRecord:
    manifest_digest: str
    replay_result_digest: str
    scenario_binding_digest: str
    scenario_id: str
    replay_trial_digests: tuple[str, ...]
    outcome_evidence_digest: str
    eligibility: EligibilityDisposition
    resolution: ResolutionDisposition
    checks: tuple[OutcomeCheckResult, ...]
    schema_version: str = _RECORD_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_digest(self.manifest_digest, "outcome record manifest_digest")
        _require_digest(self.replay_result_digest, "outcome record replay_result_digest")
        _require_digest(
            self.scenario_binding_digest,
            "outcome record scenario_binding_digest",
        )
        _require_id(self.scenario_id, "outcome record scenario_id")
        if not isinstance(self.replay_trial_digests, tuple) or len(self.replay_trial_digests) != 3:
            raise ValueError("replay_trial_digests must bind exactly three trials")
        for digest in self.replay_trial_digests:
            _require_digest(digest, "outcome record replay trial digest")
        if len(set(self.replay_trial_digests)) != 3:
            raise ValueError("replay_trial_digests must be unique")
        _require_digest(
            self.outcome_evidence_digest,
            "outcome record outcome_evidence_digest",
        )
        if not isinstance(self.eligibility, EligibilityDisposition):
            raise ValueError("outcome record eligibility disposition is unknown")
        if not isinstance(self.resolution, ResolutionDisposition):
            raise ValueError("outcome record resolution disposition is unknown")
        if not isinstance(self.checks, tuple) or any(
            not isinstance(check, OutcomeCheckResult) for check in self.checks
        ):
            raise ValueError("checks must be an immutable outcome-check tuple")
        check_codes = tuple(check.code for check in self.checks)
        if len(check_codes) != len(set(check_codes)) or set(check_codes) != set(OutcomeCheckCode):
            raise ValueError("checks must contain every required outcome check")
        object.__setattr__(self, "checks", tuple(sorted(self.checks)))
        if self.schema_version != _RECORD_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_RECORD_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    @property
    def checks_passed(self) -> bool:
        return all(check.status is OutcomeCheckStatus.PASS for check in self.checks)

    @property
    def has_unknown_check(self) -> bool:
        return any(check.status is OutcomeCheckStatus.UNKNOWN for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "checks": [check.as_dict() for check in self.checks],
            "eligibility": self.eligibility.value,
            "evidence_class": self.evidence_class,
            "manifest_digest": self.manifest_digest,
            "outcome_evidence_digest": self.outcome_evidence_digest,
            "replay_result_digest": self.replay_result_digest,
            "replay_trial_digests": list(self.replay_trial_digests),
            "resolution": self.resolution.value,
            "scenario_binding_digest": self.scenario_binding_digest,
            "scenario_id": self.scenario_id,
            "schema_version": self.schema_version,
        }


def _record_sort_key(record: SyntheticOutcomeRecord) -> tuple[str, str]:
    return (record.scenario_id, _canonical_json(record.as_dict()))


@dataclass(frozen=True, slots=True)
class SyntheticOutcomeLedger:
    ledger_id: str
    version: str
    metric_definition_digest: str
    manifest_digest: str
    corpus_digest: str
    coverage_report_digest: str
    replay_plan_digest: str
    replay_result_digest: str
    records: tuple[SyntheticOutcomeRecord, ...]
    business_claimable: bool = False
    schema_version: str = _LEDGER_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.ledger_id, "outcome ledger_id")
        _require_text(self.version, "outcome ledger version", maximum=256)
        for field, value in (
            ("metric_definition_digest", self.metric_definition_digest),
            ("manifest_digest", self.manifest_digest),
            ("corpus_digest", self.corpus_digest),
            ("coverage_report_digest", self.coverage_report_digest),
            ("replay_plan_digest", self.replay_plan_digest),
            ("replay_result_digest", self.replay_result_digest),
        ):
            _require_digest(value, f"outcome ledger {field}")
        if not isinstance(self.records, tuple) or any(
            not isinstance(record, SyntheticOutcomeRecord) for record in self.records
        ):
            raise ValueError("records must be an immutable outcome-record tuple")
        object.__setattr__(
            self,
            "records",
            tuple(sorted(self.records, key=_record_sort_key)),
        )
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic outcomes")
        if self.schema_version != _LEDGER_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_LEDGER_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "business_claimable": self.business_claimable,
            "corpus_digest": self.corpus_digest,
            "coverage_report_digest": self.coverage_report_digest,
            "evidence_class": self.evidence_class,
            "ledger_id": self.ledger_id,
            "manifest_digest": self.manifest_digest,
            "metric_definition_digest": self.metric_definition_digest,
            "records": [record.as_dict() for record in self.records],
            "replay_plan_digest": self.replay_plan_digest,
            "replay_result_digest": self.replay_result_digest,
            "schema_version": self.schema_version,
            "version": self.version,
        }


class OutcomeIssueCode(StrEnum):
    METRIC_DEFINITION_MISMATCH = "metric_definition_mismatch"
    CORPUS_MANIFEST_MISMATCH = "corpus_manifest_mismatch"
    COVERAGE_REPORT_MISMATCH = "coverage_report_mismatch"
    COVERAGE_INCOMPLETE = "coverage_incomplete"
    REPLAY_PLAN_SCOPE_MISMATCH = "replay_plan_scope_mismatch"
    REPLAY_RESULT_MISMATCH = "replay_result_mismatch"
    REPLAY_RESULT_INCOMPLETE = "replay_result_incomplete"
    LEDGER_MANIFEST_MISMATCH = "ledger_manifest_mismatch"
    LEDGER_CORPUS_MISMATCH = "ledger_corpus_mismatch"
    LEDGER_COVERAGE_MISMATCH = "ledger_coverage_mismatch"
    LEDGER_PLAN_MISMATCH = "ledger_plan_mismatch"
    LEDGER_REPLAY_RESULT_MISMATCH = "ledger_replay_result_mismatch"
    MISSING_OUTCOME_RECORD = "missing_outcome_record"
    DUPLICATE_OUTCOME_RECORD = "duplicate_outcome_record"
    EXTRA_OUTCOME_RECORD = "extra_outcome_record"
    FOREIGN_RECORD_MANIFEST = "foreign_record_manifest"
    FOREIGN_RECORD_REPLAY_RESULT = "foreign_record_replay_result"
    FOREIGN_RECORD_BINDING = "foreign_record_binding"
    FOREIGN_RECORD_TRIALS = "foreign_record_trials"
    UNKNOWN_ELIGIBILITY = "unknown_eligibility"
    UNKNOWN_RESOLUTION = "unknown_resolution"
    UNKNOWN_OUTCOME_CHECK = "unknown_outcome_check"


@dataclass(frozen=True, slots=True)
class OutcomeIssue:
    code: OutcomeIssueCode
    scenario_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, OutcomeIssueCode):
            raise ValueError("outcome issue code is unknown")
        if self.scenario_id is not None:
            _require_id(self.scenario_id, "outcome issue scenario_id")

    def as_dict(self) -> dict[str, str | None]:
        return {"code": self.code.value, "scenario_id": self.scenario_id}


def _issue_sort_key(issue: OutcomeIssue) -> tuple[str, str]:
    return (issue.code.value, issue.scenario_id or "")


@dataclass(frozen=True, slots=True)
class OutcomeMetric:
    numerator: int
    denominator: int
    kind: MetricKind

    def __post_init__(self) -> None:
        for field, value in (
            ("numerator", self.numerator),
            ("denominator", self.denominator),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"outcome metric {field} must be a non-negative integer")
        if self.numerator > self.denominator:
            raise ValueError("outcome metric numerator cannot exceed denominator")
        if not isinstance(self.kind, MetricKind):
            raise ValueError("outcome metric kind is unknown")
        if self.denominator == 0 and (self.numerator != 0 or self.kind is not MetricKind.UNDEFINED):
            raise ValueError("zero-denominator outcome metric must be undefined")
        if self.denominator > 0 and self.kind is MetricKind.UNDEFINED:
            raise ValueError("positive-denominator outcome metric cannot be undefined")

    @property
    def defined(self) -> bool:
        return self.kind is not MetricKind.UNDEFINED

    def as_dict(self) -> dict[str, object]:
        return {
            "defined": self.defined,
            "denominator": self.denominator,
            "kind": self.kind.value,
            "numerator": self.numerator,
        }


@dataclass(frozen=True, slots=True)
class SyntheticOutcomeReport:
    metric_definition_digest: str
    ledger_digest: str
    manifest_digest: str
    corpus_digest: str
    coverage_report_digest: str
    replay_plan_digest: str
    replay_result_digest: str
    recontact_window_days: int
    corpus_case_count: int
    verified_scenario_ids: tuple[str, ...]
    unverified_claimed_scenario_ids: tuple[str, ...]
    vr_precision: OutcomeMetric
    vry: OutcomeMetric
    eligibility_coverage: OutcomeMetric
    issues: tuple[OutcomeIssue, ...]
    owner_status: str = _OWNER_STATUS
    business_claimable: bool = False
    schema_version: str = _REPORT_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        for field, value in (
            ("metric_definition_digest", self.metric_definition_digest),
            ("ledger_digest", self.ledger_digest),
            ("manifest_digest", self.manifest_digest),
            ("corpus_digest", self.corpus_digest),
            ("coverage_report_digest", self.coverage_report_digest),
            ("replay_plan_digest", self.replay_plan_digest),
            ("replay_result_digest", self.replay_result_digest),
        ):
            _require_digest(value, f"outcome report {field}")
        if (
            isinstance(self.recontact_window_days, bool)
            or not isinstance(self.recontact_window_days, int)
            or not 1 <= self.recontact_window_days <= 365
        ):
            raise ValueError("report recontact_window_days must be in [1, 365]")
        if (
            isinstance(self.corpus_case_count, bool)
            or not isinstance(self.corpus_case_count, int)
            or self.corpus_case_count < 1
        ):
            raise ValueError("corpus_case_count must be a positive integer")
        object.__setattr__(
            self,
            "verified_scenario_ids",
            _sorted_unique_ids(self.verified_scenario_ids, "verified scenario IDs"),
        )
        object.__setattr__(
            self,
            "unverified_claimed_scenario_ids",
            _sorted_unique_ids(
                self.unverified_claimed_scenario_ids,
                "unverified claimed scenario IDs",
            ),
        )
        if set(self.verified_scenario_ids) & set(self.unverified_claimed_scenario_ids):
            raise ValueError("verified and unverified claimed scenario IDs must be disjoint")
        for metric in (self.vr_precision, self.vry, self.eligibility_coverage):
            if not isinstance(metric, OutcomeMetric):
                raise ValueError("report metrics must be OutcomeMetric values")
        if self.eligibility_coverage.denominator != self.corpus_case_count:
            raise ValueError("eligibility coverage must use the full corpus denominator")
        if self.vry.denominator > self.corpus_case_count:
            raise ValueError("VRY denominator cannot exceed the corpus case count")
        if self.vr_precision.denominator > self.corpus_case_count:
            raise ValueError("VR precision denominator cannot exceed the corpus case count")
        verified_count = len(self.verified_scenario_ids)
        if self.vr_precision.numerator != verified_count or self.vry.numerator != verified_count:
            raise ValueError("VR precision and VRY must share the verified numerator")
        if not isinstance(self.issues, tuple) or any(
            not isinstance(issue, OutcomeIssue) for issue in self.issues
        ):
            raise ValueError("report issues must be an immutable outcome-issue tuple")
        object.__setattr__(
            self,
            "issues",
            tuple(sorted(set(self.issues), key=_issue_sort_key)),
        )
        if self.owner_status != _OWNER_STATUS:
            raise ValueError(f"owner_status must be {_OWNER_STATUS!r}")
        if self.business_claimable is not False:
            raise ValueError("business_claimable must remain false for synthetic outcomes")
        if self.schema_version != _REPORT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_REPORT_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    @property
    def structurally_complete(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, object]:
        return {
            "business_claimable": self.business_claimable,
            "corpus_case_count": self.corpus_case_count,
            "corpus_digest": self.corpus_digest,
            "coverage_report_digest": self.coverage_report_digest,
            "eligibility_coverage": self.eligibility_coverage.as_dict(),
            "evidence_class": self.evidence_class,
            "issues": [issue.as_dict() for issue in self.issues],
            "ledger_digest": self.ledger_digest,
            "manifest_digest": self.manifest_digest,
            "metric_definition_digest": self.metric_definition_digest,
            "owner_status": self.owner_status,
            "recontact_window_days": self.recontact_window_days,
            "replay_plan_digest": self.replay_plan_digest,
            "replay_result_digest": self.replay_result_digest,
            "schema_version": self.schema_version,
            "structurally_complete": self.structurally_complete,
            "synthetic_case_unit": "scenario",
            "unverified_claimed_scenario_ids": list(self.unverified_claimed_scenario_ids),
            "verified_scenario_ids": list(self.verified_scenario_ids),
            "vr_precision": self.vr_precision.as_dict(),
            "vry": self.vry.as_dict(),
        }


def _metric(numerator: int, denominator: int, *, incomplete: bool) -> OutcomeMetric:
    if denominator == 0:
        kind = MetricKind.UNDEFINED
    elif incomplete:
        kind = MetricKind.LOWER_BOUND
    else:
        kind = MetricKind.EXACT
    return OutcomeMetric(numerator=numerator, denominator=denominator, kind=kind)


def _corpus_manifest_matches(
    corpus: CompiledResolutionScenarioCorpus,
    manifest: ReplayManifest,
) -> bool:
    if manifest.contract_pin != corpus.contract_pin:
        return False
    if manifest.scenario_set_pin != compiled_corpus_pin(corpus):
        return False
    manifest_by_id = {binding.scenario_id: binding for binding in manifest.scenarios}
    corpus_by_id = {scenario.scenario_id: scenario for scenario in corpus.scenarios}
    if manifest_by_id.keys() != corpus_by_id.keys():
        return False
    return all(
        manifest_by_id[scenario_id] == compiled.fixture.binding()
        for scenario_id, compiled in corpus_by_id.items()
    )


def _replay_scenario_passed(
    scenario_id: str,
    *,
    manifest: ReplayManifest,
    plan: ReplayPlan,
    replay_result: ReplayExecutionResult,
) -> bool:
    binding_by_id = {binding.scenario_id: binding for binding in manifest.scenarios}
    binding = binding_by_id.get(scenario_id)
    if binding is None:
        return False
    records = sorted(
        (record for record in replay_result.records if record.scenario_id == scenario_id),
        key=lambda record: record.trial_ordinal,
    )
    if len(records) != 3 or tuple(record.trial_ordinal for record in records) != (1, 2, 3):
        return False
    expected_plan_digest = replay_plan_digest(plan)
    expected_manifest_digest = replay_manifest_digest(manifest)
    expected_binding_digest = scenario_binding_digest(binding)
    return all(
        record.plan_digest == expected_plan_digest
        and record.manifest_digest == expected_manifest_digest
        and record.scenario_binding_digest == expected_binding_digest
        and record.seed == derive_trial_seed(plan, scenario_id, record.trial_ordinal)
        and record.status is TrialStatus.PASSED
        for record in records
    )


def build_synthetic_outcome_report(
    *,
    definition: SyntheticMetricDefinition,
    corpus: CompiledResolutionScenarioCorpus,
    manifest: ReplayManifest,
    coverage_report: ManifestCoverageReport,
    plan: ReplayPlan,
    replay_result: ReplayExecutionResult,
    ledger: SyntheticOutcomeLedger,
) -> SyntheticOutcomeReport:
    if not isinstance(definition, SyntheticMetricDefinition):
        raise ValueError("definition must be a SyntheticMetricDefinition")
    if not isinstance(corpus, CompiledResolutionScenarioCorpus):
        raise ValueError("corpus must be a CompiledResolutionScenarioCorpus")
    if not isinstance(manifest, ReplayManifest):
        raise ValueError("manifest must be a ReplayManifest")
    if not isinstance(coverage_report, ManifestCoverageReport):
        raise ValueError("coverage_report must be a ManifestCoverageReport")
    if not isinstance(plan, ReplayPlan):
        raise ValueError("plan must be a ReplayPlan")
    if not isinstance(replay_result, ReplayExecutionResult):
        raise ValueError("replay_result must be a ReplayExecutionResult")
    if not isinstance(ledger, SyntheticOutcomeLedger):
        raise ValueError("ledger must be a SyntheticOutcomeLedger")

    definition_digest = metric_definition_digest(definition)
    manifest_digest = replay_manifest_digest(manifest)
    corpus_digest_value = corpus_digest(corpus)
    coverage_digest = manifest_coverage_report_digest(coverage_report)
    plan_digest = replay_plan_digest(plan)
    result_digest = replay_result_digest(replay_result)
    ledger_digest = synthetic_outcome_ledger_digest(ledger)
    expected_ids = tuple(scenario.scenario_id for scenario in corpus.scenarios)
    expected_id_set = set(expected_ids)
    issues: list[OutcomeIssue] = []
    global_credit_allowed = True

    if ledger.metric_definition_digest != definition_digest:
        issues.append(OutcomeIssue(OutcomeIssueCode.METRIC_DEFINITION_MISMATCH))
        global_credit_allowed = False
    if not _corpus_manifest_matches(corpus, manifest):
        issues.append(OutcomeIssue(OutcomeIssueCode.CORPUS_MANIFEST_MISMATCH))
        global_credit_allowed = False

    recomputed_coverage = build_manifest_coverage_report(corpus, manifest)
    if coverage_report != recomputed_coverage:
        issues.append(OutcomeIssue(OutcomeIssueCode.COVERAGE_REPORT_MISMATCH))
        global_credit_allowed = False
    if not coverage_report.complete or not recomputed_coverage.complete:
        issues.append(OutcomeIssue(OutcomeIssueCode.COVERAGE_INCOMPLETE))
        global_credit_allowed = False

    plan_scope_matches = (
        plan.manifest_digest == manifest_digest
        and set(plan.selected_scenario_ids) == expected_id_set
        and len(plan.selected_scenario_ids) == len(expected_ids)
        and plan.selection_complete
    )
    if not plan_scope_matches:
        issues.append(OutcomeIssue(OutcomeIssueCode.REPLAY_PLAN_SCOPE_MISMATCH))
        global_credit_allowed = False

    result_matches = (
        replay_result.plan_digest == plan_digest
        and replay_result.manifest_digest == manifest_digest
        and replay_result.scenario_count == len(expected_ids)
        and replay_result.trials_per_scenario == plan.trials_per_scenario
    )
    if plan_scope_matches:
        try:
            recomputed_result = summarize_trial_records(
                manifest,
                plan,
                replay_result.records,
                issues=replay_result.issues,
            )
        except ValueError:
            result_matches = False
        else:
            result_matches = result_matches and recomputed_result == replay_result
    else:
        result_matches = False
    if not result_matches:
        issues.append(OutcomeIssue(OutcomeIssueCode.REPLAY_RESULT_MISMATCH))
        global_credit_allowed = False
    elif not replay_result.record_matrix_complete:
        issues.append(OutcomeIssue(OutcomeIssueCode.REPLAY_RESULT_INCOMPLETE))

    for actual, expected, code in (
        (
            ledger.manifest_digest,
            manifest_digest,
            OutcomeIssueCode.LEDGER_MANIFEST_MISMATCH,
        ),
        (
            ledger.corpus_digest,
            corpus_digest_value,
            OutcomeIssueCode.LEDGER_CORPUS_MISMATCH,
        ),
        (
            ledger.coverage_report_digest,
            coverage_digest,
            OutcomeIssueCode.LEDGER_COVERAGE_MISMATCH,
        ),
        (
            ledger.replay_plan_digest,
            plan_digest,
            OutcomeIssueCode.LEDGER_PLAN_MISMATCH,
        ),
        (
            ledger.replay_result_digest,
            result_digest,
            OutcomeIssueCode.LEDGER_REPLAY_RESULT_MISMATCH,
        ),
    ):
        if actual != expected:
            issues.append(OutcomeIssue(code))
            global_credit_allowed = False

    grouped_records: dict[str, list[SyntheticOutcomeRecord]] = {}
    for record in ledger.records:
        grouped_records.setdefault(record.scenario_id, []).append(record)
    for scenario_id in grouped_records.keys() - expected_id_set:
        issues.append(OutcomeIssue(OutcomeIssueCode.EXTRA_OUTCOME_RECORD, scenario_id))

    manifest_by_id = {binding.scenario_id: binding for binding in manifest.scenarios}
    replay_records_by_id = {
        scenario_id: tuple(
            sorted(
                (record for record in replay_result.records if record.scenario_id == scenario_id),
                key=lambda record: record.trial_ordinal,
            )
        )
        for scenario_id in expected_ids
    }
    claimed_denominator = 0
    eligible_denominator = 0
    confirmed_eligible_count = 0
    verified_ids: list[str] = []
    unverified_claimed_ids: list[str] = []

    for scenario_id in expected_ids:
        values = grouped_records.get(scenario_id, ())
        if not values:
            issues.append(OutcomeIssue(OutcomeIssueCode.MISSING_OUTCOME_RECORD, scenario_id))
            claimed_denominator += 1
            eligible_denominator += 1
            continue
        if len(values) > 1:
            issues.append(OutcomeIssue(OutcomeIssueCode.DUPLICATE_OUTCOME_RECORD, scenario_id))
            claimed_denominator += 1
            eligible_denominator += 1
            continue

        record = values[0]
        record_valid = True
        if record.manifest_digest != manifest_digest:
            issues.append(OutcomeIssue(OutcomeIssueCode.FOREIGN_RECORD_MANIFEST, scenario_id))
            record_valid = False
        if record.replay_result_digest != result_digest:
            issues.append(
                OutcomeIssue(
                    OutcomeIssueCode.FOREIGN_RECORD_REPLAY_RESULT,
                    scenario_id,
                )
            )
            record_valid = False
        binding = manifest_by_id.get(scenario_id)
        if binding is None or record.scenario_binding_digest != scenario_binding_digest(binding):
            issues.append(OutcomeIssue(OutcomeIssueCode.FOREIGN_RECORD_BINDING, scenario_id))
            record_valid = False
        expected_trial_digests = tuple(
            replay_trial_digest(trial) for trial in replay_records_by_id[scenario_id]
        )
        if record.replay_trial_digests != expected_trial_digests:
            issues.append(OutcomeIssue(OutcomeIssueCode.FOREIGN_RECORD_TRIALS, scenario_id))
            record_valid = False
        if not record_valid:
            claimed_denominator += 1
            eligible_denominator += 1
            continue

        if record.eligibility is EligibilityDisposition.ELIGIBLE:
            confirmed_eligible_count += 1
            eligible_denominator += 1
        elif record.eligibility is EligibilityDisposition.UNKNOWN:
            issues.append(OutcomeIssue(OutcomeIssueCode.UNKNOWN_ELIGIBILITY, scenario_id))
            eligible_denominator += 1

        explicitly_claimed = record.resolution is ResolutionDisposition.CLAIMED_AUTO
        if explicitly_claimed:
            claimed_denominator += 1
        elif record.resolution is ResolutionDisposition.UNKNOWN:
            issues.append(OutcomeIssue(OutcomeIssueCode.UNKNOWN_RESOLUTION, scenario_id))
            claimed_denominator += 1

        if record.has_unknown_check:
            issues.append(OutcomeIssue(OutcomeIssueCode.UNKNOWN_OUTCOME_CHECK, scenario_id))

        verified = (
            global_credit_allowed
            and record.eligibility is EligibilityDisposition.ELIGIBLE
            and explicitly_claimed
            and record.checks_passed
            and _replay_scenario_passed(
                scenario_id,
                manifest=manifest,
                plan=plan,
                replay_result=replay_result,
            )
        )
        if verified:
            verified_ids.append(scenario_id)
        elif explicitly_claimed:
            unverified_claimed_ids.append(scenario_id)

    if not global_credit_allowed:
        verified_ids = []
        confirmed_eligible_count = 0
        claimed_denominator = len(expected_ids)
        eligible_denominator = len(expected_ids)

    incomplete = bool(issues)
    verified_count = len(verified_ids)
    return SyntheticOutcomeReport(
        metric_definition_digest=definition_digest,
        ledger_digest=ledger_digest,
        manifest_digest=manifest_digest,
        corpus_digest=corpus_digest_value,
        coverage_report_digest=coverage_digest,
        replay_plan_digest=plan_digest,
        replay_result_digest=result_digest,
        recontact_window_days=definition.recontact_window_days,
        corpus_case_count=len(expected_ids),
        verified_scenario_ids=tuple(verified_ids),
        unverified_claimed_scenario_ids=tuple(unverified_claimed_ids),
        vr_precision=_metric(
            verified_count,
            claimed_denominator,
            incomplete=incomplete,
        ),
        vry=_metric(
            verified_count,
            eligible_denominator,
            incomplete=incomplete,
        ),
        eligibility_coverage=_metric(
            confirmed_eligible_count,
            len(expected_ids),
            incomplete=incomplete,
        ),
        issues=tuple(issues),
    )


def canonical_synthetic_metric_definition_json(
    definition: SyntheticMetricDefinition,
) -> str:
    if not isinstance(definition, SyntheticMetricDefinition):
        raise ValueError("definition must be a SyntheticMetricDefinition")
    return _canonical_json(definition.as_dict())


def metric_definition_digest(definition: SyntheticMetricDefinition) -> str:
    return hashlib.sha256(
        canonical_synthetic_metric_definition_json(definition).encode("utf-8")
    ).hexdigest()


def canonical_synthetic_outcome_record_json(record: SyntheticOutcomeRecord) -> str:
    if not isinstance(record, SyntheticOutcomeRecord):
        raise ValueError("record must be a SyntheticOutcomeRecord")
    return _canonical_json(record.as_dict())


def synthetic_outcome_record_digest(record: SyntheticOutcomeRecord) -> str:
    return hashlib.sha256(
        canonical_synthetic_outcome_record_json(record).encode("utf-8")
    ).hexdigest()


def canonical_synthetic_outcome_ledger_json(ledger: SyntheticOutcomeLedger) -> str:
    if not isinstance(ledger, SyntheticOutcomeLedger):
        raise ValueError("ledger must be a SyntheticOutcomeLedger")
    return _canonical_json(ledger.as_dict())


def synthetic_outcome_ledger_digest(ledger: SyntheticOutcomeLedger) -> str:
    return hashlib.sha256(
        canonical_synthetic_outcome_ledger_json(ledger).encode("utf-8")
    ).hexdigest()


def canonical_synthetic_outcome_report_json(report: SyntheticOutcomeReport) -> str:
    if not isinstance(report, SyntheticOutcomeReport):
        raise ValueError("report must be a SyntheticOutcomeReport")
    return _canonical_json(report.as_dict())


def synthetic_outcome_report_digest(report: SyntheticOutcomeReport) -> str:
    return hashlib.sha256(
        canonical_synthetic_outcome_report_json(report).encode("utf-8")
    ).hexdigest()


__all__ = [
    "EligibilityDisposition",
    "MetricKind",
    "OutcomeCheckCode",
    "OutcomeCheckResult",
    "OutcomeCheckStatus",
    "OutcomeIssue",
    "OutcomeIssueCode",
    "OutcomeMetric",
    "ResolutionDisposition",
    "SyntheticMetricDefinition",
    "SyntheticOutcomeLedger",
    "SyntheticOutcomeRecord",
    "SyntheticOutcomeReport",
    "build_synthetic_outcome_report",
    "canonical_synthetic_metric_definition_json",
    "canonical_synthetic_outcome_ledger_json",
    "canonical_synthetic_outcome_record_json",
    "canonical_synthetic_outcome_report_json",
    "metric_definition_digest",
    "synthetic_outcome_ledger_digest",
    "synthetic_outcome_record_digest",
    "synthetic_outcome_report_digest",
]
