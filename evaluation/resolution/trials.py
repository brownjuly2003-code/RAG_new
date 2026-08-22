from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from evaluation.resolution.grading import (
    EvaluationInfrastructureFailure,
    EvaluatorStatus,
    GradeFailureCode,
    ObservedResolutionState,
    evaluate_scenario,
)
from evaluation.resolution.replay import (
    ArtifactKey,
    ArtifactPin,
    ImpactSelectionReport,
    ReplayManifest,
    ScenarioReplayBinding,
    SelectionMode,
    bind_scenario,
    impact_report_digest,
    replay_manifest_digest,
    scenario_binding_digest,
)
from evaluation.resolution.scenarios import (
    CandidateScenarioInput,
    CompiledScenario,
    ScenarioWorld,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_PLAN_SCHEMA_VERSION = "resolution-replay-plan/v0.1"
_TRIAL_SCHEMA_VERSION = "resolution-replay-trial/v0.1"
_RESULT_SCHEMA_VERSION = "resolution-replay-result/v0.1"
_EVIDENCE_CLASS = "synthetic_local"
_TRIALS_PER_SCENARIO = 3
_MAX_SEED = 2**63


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _payload_digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _require_id(value: str, field: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{field} must be a stable safe identifier")


def _require_seed(value: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < _MAX_SEED:
        raise ValueError(f"{field} must be an integer in [0, 2^63)")


def _sorted_unique_ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field} must be a non-empty immutable tuple")
    for value in values:
        _require_id(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


@dataclass(frozen=True, slots=True)
class ReplayScenarioFixture:
    scenario: CompiledScenario
    world_pin: ArtifactPin
    coverage_target_ids: tuple[str, ...]
    dependency_keys: tuple[ArtifactKey, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, CompiledScenario):
            raise ValueError("fixture scenario must be a CompiledScenario")
        binding = bind_scenario(
            self.scenario,
            world_pin=self.world_pin,
            coverage_target_ids=self.coverage_target_ids,
            dependency_keys=self.dependency_keys,
        )
        object.__setattr__(self, "coverage_target_ids", binding.coverage_target_ids)
        object.__setattr__(self, "dependency_keys", binding.dependency_keys)

    @property
    def scenario_id(self) -> str:
        return self.scenario.candidate_input.scenario_id

    def binding(self) -> ScenarioReplayBinding:
        return bind_scenario(
            self.scenario,
            world_pin=self.world_pin,
            coverage_target_ids=self.coverage_target_ids,
            dependency_keys=self.dependency_keys,
        )


@dataclass(frozen=True, slots=True)
class ReplayPlan:
    manifest_digest: str
    selected_scenario_ids: tuple[str, ...]
    base_seed: int
    selection_report_digest: str | None
    selection_complete: bool
    trials_per_scenario: int = _TRIALS_PER_SCENARIO
    schema_version: str = _PLAN_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_digest(self.manifest_digest, "manifest_digest")
        object.__setattr__(
            self,
            "selected_scenario_ids",
            _sorted_unique_ids(self.selected_scenario_ids, "selected scenario IDs"),
        )
        _require_seed(self.base_seed, "base_seed")
        if self.selection_report_digest is not None:
            _require_digest(self.selection_report_digest, "selection_report_digest")
        if not isinstance(self.selection_complete, bool):
            raise ValueError("selection_complete must be a boolean")
        if self.trials_per_scenario != _TRIALS_PER_SCENARIO:
            raise ValueError("trials_per_scenario must be exactly 3")
        if self.schema_version != _PLAN_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_PLAN_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "base_seed": self.base_seed,
            "evidence_class": self.evidence_class,
            "manifest_digest": self.manifest_digest,
            "schema_version": self.schema_version,
            "selected_scenario_ids": list(self.selected_scenario_ids),
            "selection_complete": self.selection_complete,
            "selection_report_digest": self.selection_report_digest,
            "trials_per_scenario": self.trials_per_scenario,
        }


class TrialStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ReplayTrialRecord:
    plan_digest: str
    manifest_digest: str
    scenario_binding_digest: str
    scenario_id: str
    trial_ordinal: int
    seed: int
    status: TrialStatus
    grade_failure_codes: tuple[GradeFailureCode, ...]
    observation_digest: str
    schema_version: str = _TRIAL_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_digest(self.plan_digest, "plan_digest")
        _require_digest(self.manifest_digest, "manifest_digest")
        _require_digest(self.scenario_binding_digest, "scenario_binding_digest")
        _require_id(self.scenario_id, "scenario_id")
        if (
            isinstance(self.trial_ordinal, bool)
            or not isinstance(self.trial_ordinal, int)
            or self.trial_ordinal < 1
        ):
            raise ValueError("trial_ordinal must be a positive integer")
        _require_seed(self.seed, "seed")
        if not isinstance(self.status, TrialStatus):
            raise ValueError("trial status is unknown")
        if not isinstance(self.grade_failure_codes, tuple):
            raise ValueError("grade_failure_codes must be an immutable tuple")
        if any(not isinstance(code, GradeFailureCode) for code in self.grade_failure_codes):
            raise ValueError("grade_failure_codes contains an unknown value")
        if len(self.grade_failure_codes) != len(set(self.grade_failure_codes)):
            raise ValueError("grade_failure_codes must be unique")
        object.__setattr__(
            self,
            "grade_failure_codes",
            tuple(sorted(self.grade_failure_codes, key=lambda code: code.value)),
        )
        infrastructure_codes = (GradeFailureCode.EVALUATOR_INFRASTRUCTURE_FAILURE,)
        if self.status is TrialStatus.PASSED and self.grade_failure_codes:
            raise ValueError("passed trial grade_failure_codes must be empty")
        if self.status is TrialStatus.FAILED and not self.grade_failure_codes:
            raise ValueError("failed trial grade_failure_codes cannot be empty")
        if self.status in {TrialStatus.ERROR, TrialStatus.SKIPPED} and (
            self.grade_failure_codes != infrastructure_codes
        ):
            raise ValueError(
                "error or skipped trial grade_failure_codes must identify infrastructure"
            )
        _require_digest(self.observation_digest, "observation_digest")
        if self.schema_version != _TRIAL_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_TRIAL_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_class": self.evidence_class,
            "grade_failure_codes": [code.value for code in self.grade_failure_codes],
            "manifest_digest": self.manifest_digest,
            "observation_digest": self.observation_digest,
            "plan_digest": self.plan_digest,
            "scenario_binding_digest": self.scenario_binding_digest,
            "scenario_id": self.scenario_id,
            "schema_version": self.schema_version,
            "seed": self.seed,
            "status": self.status.value,
            "trial_ordinal": self.trial_ordinal,
        }


class ReplayIssueCode(StrEnum):
    IMPACT_SELECTION_INCOMPLETE = "impact_selection_incomplete"
    MISSING_SCENARIO = "missing_scenario"
    DUPLICATE_SCENARIO = "duplicate_scenario"
    EXTRA_SCENARIO = "extra_scenario"
    SCENARIO_BINDING_MISMATCH = "scenario_binding_mismatch"
    CONTRACT_IDENTITY_MISMATCH = "contract_identity_mismatch"
    MISSING_TRIAL = "missing_trial"
    DUPLICATE_TRIAL = "duplicate_trial"
    EXTRA_TRIAL = "extra_trial"
    FOREIGN_PLAN = "foreign_plan"
    FOREIGN_MANIFEST = "foreign_manifest"
    FOREIGN_BINDING = "foreign_binding"
    INVALID_TRIAL_IDENTITY = "invalid_trial_identity"


@dataclass(frozen=True, slots=True)
class ReplayIssue:
    code: ReplayIssueCode
    scenario_id: str | None = None
    trial_ordinal: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, ReplayIssueCode):
            raise ValueError("replay issue code is unknown")
        if self.scenario_id is not None:
            _require_id(self.scenario_id, "issue scenario_id")
        if self.trial_ordinal is not None and (
            isinstance(self.trial_ordinal, bool)
            or not isinstance(self.trial_ordinal, int)
            or self.trial_ordinal < 1
        ):
            raise ValueError("issue trial_ordinal must be a positive integer")

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "scenario_id": self.scenario_id,
            "trial_ordinal": self.trial_ordinal,
        }


@dataclass(frozen=True, slots=True)
class PassStatistic:
    k: int
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.k not in {1, 3}:
            raise ValueError("pass statistic k must be 1 or 3")
        for field, value in (
            ("numerator", self.numerator),
            ("denominator", self.denominator),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"pass statistic {field} must be a non-negative integer")
        if self.numerator > self.denominator:
            raise ValueError("pass statistic numerator cannot exceed denominator")

    def as_dict(self) -> dict[str, int]:
        return {
            "denominator": self.denominator,
            "k": self.k,
            "numerator": self.numerator,
        }


def _record_sort_key(record: ReplayTrialRecord) -> tuple[object, ...]:
    return (
        record.scenario_id,
        record.trial_ordinal,
        record.plan_digest,
        record.manifest_digest,
        record.scenario_binding_digest,
        record.seed,
        record.status.value,
        tuple(code.value for code in record.grade_failure_codes),
        record.observation_digest,
    )


def _issue_sort_key(issue: ReplayIssue) -> tuple[object, ...]:
    return (
        issue.code.value,
        issue.scenario_id or "",
        issue.trial_ordinal or 0,
    )


@dataclass(frozen=True, slots=True)
class ReplayExecutionResult:
    plan_digest: str
    manifest_digest: str
    scenario_count: int
    trials_per_scenario: int
    records: tuple[ReplayTrialRecord, ...]
    issues: tuple[ReplayIssue, ...]
    record_matrix_complete: bool
    pass_1: PassStatistic
    pass_3: PassStatistic
    schema_version: str = _RESULT_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_digest(self.plan_digest, "plan_digest")
        _require_digest(self.manifest_digest, "manifest_digest")
        if (
            isinstance(self.scenario_count, bool)
            or not isinstance(self.scenario_count, int)
            or self.scenario_count < 1
        ):
            raise ValueError("scenario_count must be a positive integer")
        if self.trials_per_scenario != _TRIALS_PER_SCENARIO:
            raise ValueError("trials_per_scenario must be exactly 3")
        if not isinstance(self.records, tuple) or any(
            not isinstance(record, ReplayTrialRecord) for record in self.records
        ):
            raise ValueError("records must be an immutable tuple of ReplayTrialRecord")
        if not isinstance(self.issues, tuple) or any(
            not isinstance(issue, ReplayIssue) for issue in self.issues
        ):
            raise ValueError("issues must be an immutable tuple of ReplayIssue")
        object.__setattr__(self, "records", tuple(sorted(self.records, key=_record_sort_key)))
        object.__setattr__(
            self,
            "issues",
            tuple(sorted(set(self.issues), key=_issue_sort_key)),
        )
        if not isinstance(self.record_matrix_complete, bool):
            raise ValueError("record_matrix_complete must be a boolean")
        if not isinstance(self.pass_1, PassStatistic) or (
            self.pass_1.k != 1
            or self.pass_1.denominator != self.scenario_count * self.trials_per_scenario
        ):
            raise ValueError("pass_1 denominator must cover every planned trial")
        if not isinstance(self.pass_3, PassStatistic) or (
            self.pass_3.k != 3 or self.pass_3.denominator != self.scenario_count
        ):
            raise ValueError("pass_3 denominator must cover every planned scenario")
        if self.schema_version != _RESULT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_RESULT_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_class": self.evidence_class,
            "issues": [issue.as_dict() for issue in self.issues],
            "manifest_digest": self.manifest_digest,
            "pass_1": self.pass_1.as_dict(),
            "pass_3": self.pass_3.as_dict(),
            "plan_digest": self.plan_digest,
            "record_matrix_complete": self.record_matrix_complete,
            "records": [record.as_dict() for record in self.records],
            "scenario_count": self.scenario_count,
            "schema_version": self.schema_version,
            "trials_per_scenario": self.trials_per_scenario,
        }


def build_replay_plan(
    manifest: ReplayManifest,
    *,
    base_seed: int,
    impact_report: ImpactSelectionReport | None = None,
) -> ReplayPlan:
    if not isinstance(manifest, ReplayManifest):
        raise ValueError("manifest must be a ReplayManifest")
    manifest_digest = replay_manifest_digest(manifest)
    manifest_ids = tuple(scenario.scenario_id for scenario in manifest.scenarios)
    manifest_id_set = set(manifest_ids)
    if impact_report is None:
        selected_ids = manifest_ids
        report_digest = None
        selection_complete = True
    else:
        if not isinstance(impact_report, ImpactSelectionReport):
            raise ValueError("impact_report must be an ImpactSelectionReport")
        if impact_report.candidate_manifest_digest != manifest_digest:
            raise ValueError("impact report candidate manifest does not match manifest")
        if impact_report.mode is SelectionMode.NO_CHANGE:
            raise ValueError("no replay work exists for a no-change impact report")
        selected_ids = impact_report.selected_scenario_ids
        if not set(selected_ids) <= manifest_id_set:
            raise ValueError("impact report selects a scenario outside the manifest")
        if impact_report.mode in {SelectionMode.FULL, SelectionMode.FULL_FAIL_CLOSED} and (
            set(selected_ids) != manifest_id_set
        ):
            raise ValueError("full impact report must select every manifest scenario")
        report_digest = impact_report_digest(impact_report)
        selection_complete = impact_report.complete
    return ReplayPlan(
        manifest_digest=manifest_digest,
        selected_scenario_ids=selected_ids,
        base_seed=base_seed,
        selection_report_digest=report_digest,
        selection_complete=selection_complete,
    )


def canonical_replay_plan_json(plan: ReplayPlan) -> str:
    if not isinstance(plan, ReplayPlan):
        raise ValueError("plan must be a ReplayPlan")
    return _canonical_json(plan.as_dict())


def replay_plan_digest(plan: ReplayPlan) -> str:
    return hashlib.sha256(canonical_replay_plan_json(plan).encode("utf-8")).hexdigest()


def derive_trial_seed(plan: ReplayPlan, scenario_id: str, trial_ordinal: int) -> int:
    if not isinstance(plan, ReplayPlan):
        raise ValueError("plan must be a ReplayPlan")
    _require_id(scenario_id, "scenario_id")
    if scenario_id not in plan.selected_scenario_ids:
        raise ValueError("scenario_id must identify a selected scenario")
    if (
        isinstance(trial_ordinal, bool)
        or not isinstance(trial_ordinal, int)
        or not 1 <= trial_ordinal <= _TRIALS_PER_SCENARIO
    ):
        raise ValueError("trial_ordinal must be in [1, 3]")
    digest = _payload_digest(
        {
            "base_seed": plan.base_seed,
            "plan_digest": replay_plan_digest(plan),
            "scenario_id": scenario_id,
            "schema_version": "resolution-replay-seed/v0.1",
            "trial_ordinal": trial_ordinal,
        }
    )
    return int(digest[:16], 16) & (_MAX_SEED - 1)


def _observation_payload(
    observed: ObservedResolutionState | EvaluationInfrastructureFailure,
) -> dict[str, object]:
    if isinstance(observed, EvaluationInfrastructureFailure):
        return {
            "kind": "evaluation_infrastructure_failure",
            "reason_code": observed.reason_code,
            "status": observed.status.value,
        }
    return {
        "branch_path": [
            {"event": branch.event.value, "step_id": branch.step_id}
            for branch in observed.branch_path
        ],
        "canonical_state": [list(item) for item in observed.canonical_state],
        "contract_digest": observed.contract_digest,
        "contract_id": observed.contract_id,
        "contract_version": observed.contract_version,
        "kind": "observed_resolution_state",
        "reason_codes": list(observed.reason_codes),
        "response_text": observed.response_text,
        "terminal_outcome": observed.terminal_outcome.value,
    }


def _trial_status(
    observed: ObservedResolutionState | EvaluationInfrastructureFailure,
    passed: bool,
) -> TrialStatus:
    if isinstance(observed, EvaluationInfrastructureFailure):
        if observed.status is EvaluatorStatus.SKIPPED:
            return TrialStatus.SKIPPED
        return TrialStatus.ERROR
    if passed:
        return TrialStatus.PASSED
    return TrialStatus.FAILED


def _structural_failure_records(
    plan: ReplayPlan,
    manifest_digest: str,
    binding: ScenarioReplayBinding,
    reason_code: str,
) -> tuple[ReplayTrialRecord, ...]:
    failure = EvaluationInfrastructureFailure(
        status=EvaluatorStatus.ERROR,
        reason_code=reason_code,
    )
    plan_digest = replay_plan_digest(plan)
    binding_digest = scenario_binding_digest(binding)
    observation_digest = _payload_digest(_observation_payload(failure))
    return tuple(
        ReplayTrialRecord(
            plan_digest=plan_digest,
            manifest_digest=manifest_digest,
            scenario_binding_digest=binding_digest,
            scenario_id=binding.scenario_id,
            trial_ordinal=trial_ordinal,
            seed=derive_trial_seed(plan, binding.scenario_id, trial_ordinal),
            status=TrialStatus.ERROR,
            grade_failure_codes=(GradeFailureCode.EVALUATOR_INFRASTRUCTURE_FAILURE,),
            observation_digest=observation_digest,
        )
        for trial_ordinal in range(1, _TRIALS_PER_SCENARIO + 1)
    )


_CandidateT = TypeVar("_CandidateT")


def execute_replay(
    manifest: ReplayManifest,
    plan: ReplayPlan,
    fixtures: tuple[ReplayScenarioFixture, ...],
    *,
    generate_candidate: Callable[[CandidateScenarioInput, int], _CandidateT],
    execute_candidate: Callable[
        [ScenarioWorld, _CandidateT],
        ObservedResolutionState | EvaluationInfrastructureFailure,
    ],
) -> ReplayExecutionResult:
    if not isinstance(manifest, ReplayManifest):
        raise ValueError("manifest must be a ReplayManifest")
    if not isinstance(plan, ReplayPlan):
        raise ValueError("plan must be a ReplayPlan")
    manifest_digest = replay_manifest_digest(manifest)
    if plan.manifest_digest != manifest_digest:
        raise ValueError("plan manifest_digest does not match manifest")
    manifest_bindings = {binding.scenario_id: binding for binding in manifest.scenarios}
    if not set(plan.selected_scenario_ids) <= manifest_bindings.keys():
        raise ValueError("plan selects a scenario outside the manifest")
    if not isinstance(fixtures, tuple) or any(
        not isinstance(fixture, ReplayScenarioFixture) for fixture in fixtures
    ):
        raise ValueError("fixtures must be an immutable tuple of ReplayScenarioFixture")

    fixture_groups: dict[str, list[ReplayScenarioFixture]] = {}
    for fixture in fixtures:
        fixture_groups.setdefault(fixture.scenario_id, []).append(fixture)

    selected_ids = set(plan.selected_scenario_ids)
    issues: list[ReplayIssue] = []
    for scenario_id in selected_ids:
        count = len(fixture_groups.get(scenario_id, ()))
        if count == 0:
            issues.append(ReplayIssue(ReplayIssueCode.MISSING_SCENARIO, scenario_id))
        elif count > 1:
            issues.append(ReplayIssue(ReplayIssueCode.DUPLICATE_SCENARIO, scenario_id))
    for scenario_id in set(fixture_groups) - selected_ids:
        issues.append(ReplayIssue(ReplayIssueCode.EXTRA_SCENARIO, scenario_id))

    plan_digest = replay_plan_digest(plan)
    records: list[ReplayTrialRecord] = []
    contract_identity = (
        manifest.contract_pin.artifact_id,
        manifest.contract_pin.version,
        manifest.contract_pin.digest,
    )
    for scenario_id in plan.selected_scenario_ids:
        scenario_fixtures = fixture_groups.get(scenario_id, ())
        expected_binding = manifest_bindings[scenario_id]
        if len(scenario_fixtures) != 1:
            records.extend(
                _structural_failure_records(
                    plan,
                    manifest_digest,
                    expected_binding,
                    "REPLAY_FIXTURE_TOPOLOGY_INVALID",
                )
            )
            continue
        fixture = scenario_fixtures[0]
        actual_binding = fixture.binding()
        if actual_binding != expected_binding:
            issues.append(ReplayIssue(ReplayIssueCode.SCENARIO_BINDING_MISMATCH, scenario_id))
            records.extend(
                _structural_failure_records(
                    plan,
                    manifest_digest,
                    expected_binding,
                    "REPLAY_FIXTURE_BINDING_MISMATCH",
                )
            )
            continue
        expected = fixture.scenario.hidden_expected
        if (
            fixture.scenario.candidate_input.journey_id != contract_identity[0]
            or (
                expected.contract_id,
                expected.contract_version,
                expected.contract_digest,
            )
            != contract_identity
        ):
            issues.append(ReplayIssue(ReplayIssueCode.CONTRACT_IDENTITY_MISMATCH, scenario_id))
            records.extend(
                _structural_failure_records(
                    plan,
                    manifest_digest,
                    expected_binding,
                    "REPLAY_CONTRACT_IDENTITY_MISMATCH",
                )
            )
            continue

        binding_digest = scenario_binding_digest(expected_binding)
        for trial_ordinal in range(1, _TRIALS_PER_SCENARIO + 1):
            seed = derive_trial_seed(plan, scenario_id, trial_ordinal)
            observed_values: list[ObservedResolutionState | EvaluationInfrastructureFailure] = []

            def generate(public_input: CandidateScenarioInput) -> _CandidateT:
                return generate_candidate(public_input, seed)

            def execute(
                world: ScenarioWorld,
                candidate: _CandidateT,
            ) -> ObservedResolutionState | EvaluationInfrastructureFailure:
                observed = execute_candidate(world, candidate)
                if not isinstance(
                    observed,
                    (ObservedResolutionState, EvaluationInfrastructureFailure),
                ):
                    raise TypeError("candidate executor returned an unsupported observation")
                observed_values.append(observed)
                return observed

            grade = evaluate_scenario(
                fixture.scenario,
                generate_candidate=generate,
                execute_candidate=execute,
            )
            if observed_values:
                observed = observed_values[0]
            else:
                observed = EvaluationInfrastructureFailure(
                    status=EvaluatorStatus.ERROR,
                    reason_code="EVALUATOR_INFRASTRUCTURE_EXCEPTION",
                )
            records.append(
                ReplayTrialRecord(
                    plan_digest=plan_digest,
                    manifest_digest=manifest_digest,
                    scenario_binding_digest=binding_digest,
                    scenario_id=scenario_id,
                    trial_ordinal=trial_ordinal,
                    seed=seed,
                    status=_trial_status(observed, grade.passed),
                    grade_failure_codes=grade.failure_codes,
                    observation_digest=_payload_digest(_observation_payload(observed)),
                )
            )

    return summarize_trial_records(
        manifest,
        plan,
        tuple(records),
        issues=tuple(issues),
    )


def summarize_trial_records(
    manifest: ReplayManifest,
    plan: ReplayPlan,
    records: tuple[ReplayTrialRecord, ...],
    *,
    issues: tuple[ReplayIssue, ...] = (),
) -> ReplayExecutionResult:
    if not isinstance(manifest, ReplayManifest):
        raise ValueError("manifest must be a ReplayManifest")
    if not isinstance(plan, ReplayPlan):
        raise ValueError("plan must be a ReplayPlan")
    if not isinstance(records, tuple) or any(
        not isinstance(record, ReplayTrialRecord) for record in records
    ):
        raise ValueError("records must be an immutable tuple of ReplayTrialRecord")
    if not isinstance(issues, tuple) or any(not isinstance(issue, ReplayIssue) for issue in issues):
        raise ValueError("issues must be an immutable tuple of ReplayIssue")

    manifest_digest = replay_manifest_digest(manifest)
    if plan.manifest_digest != manifest_digest:
        raise ValueError("plan manifest_digest does not match manifest")
    manifest_bindings = {binding.scenario_id: binding for binding in manifest.scenarios}
    if not set(plan.selected_scenario_ids) <= manifest_bindings.keys():
        raise ValueError("plan selects a scenario outside the manifest")

    all_issues = list(issues)
    if not plan.selection_complete:
        all_issues.append(ReplayIssue(ReplayIssueCode.IMPACT_SELECTION_INCOMPLETE))
    plan_digest = replay_plan_digest(plan)
    grouped: dict[tuple[str, int], list[ReplayTrialRecord]] = {}
    selected_ids = set(plan.selected_scenario_ids)
    for record in records:
        if record.plan_digest != plan_digest:
            all_issues.append(
                ReplayIssue(
                    ReplayIssueCode.FOREIGN_PLAN,
                    record.scenario_id,
                    record.trial_ordinal,
                )
            )
            continue
        if record.manifest_digest != manifest_digest:
            all_issues.append(
                ReplayIssue(
                    ReplayIssueCode.FOREIGN_MANIFEST,
                    record.scenario_id,
                    record.trial_ordinal,
                )
            )
            continue
        if record.scenario_id not in selected_ids or record.trial_ordinal > _TRIALS_PER_SCENARIO:
            all_issues.append(
                ReplayIssue(
                    ReplayIssueCode.EXTRA_TRIAL,
                    record.scenario_id,
                    record.trial_ordinal,
                )
            )
            continue
        grouped.setdefault((record.scenario_id, record.trial_ordinal), []).append(record)

    passing_keys: set[tuple[str, int]] = set()
    for scenario_id in plan.selected_scenario_ids:
        expected_binding_digest = scenario_binding_digest(manifest_bindings[scenario_id])
        for trial_ordinal in range(1, _TRIALS_PER_SCENARIO + 1):
            key = (scenario_id, trial_ordinal)
            values = grouped.get(key, ())
            if not values:
                all_issues.append(
                    ReplayIssue(
                        ReplayIssueCode.MISSING_TRIAL,
                        scenario_id,
                        trial_ordinal,
                    )
                )
                continue
            if len(values) > 1:
                all_issues.append(
                    ReplayIssue(
                        ReplayIssueCode.DUPLICATE_TRIAL,
                        scenario_id,
                        trial_ordinal,
                    )
                )
                continue
            record = values[0]
            valid = True
            if record.scenario_binding_digest != expected_binding_digest:
                all_issues.append(
                    ReplayIssue(
                        ReplayIssueCode.FOREIGN_BINDING,
                        scenario_id,
                        trial_ordinal,
                    )
                )
                valid = False
            if record.seed != derive_trial_seed(plan, scenario_id, trial_ordinal):
                all_issues.append(
                    ReplayIssue(
                        ReplayIssueCode.INVALID_TRIAL_IDENTITY,
                        scenario_id,
                        trial_ordinal,
                    )
                )
                valid = False
            if valid and record.status is TrialStatus.PASSED:
                passing_keys.add(key)

    all_three_passed = sum(
        all((scenario_id, ordinal) in passing_keys for ordinal in (1, 2, 3))
        for scenario_id in plan.selected_scenario_ids
    )
    scenario_count = len(plan.selected_scenario_ids)
    return ReplayExecutionResult(
        plan_digest=plan_digest,
        manifest_digest=manifest_digest,
        scenario_count=scenario_count,
        trials_per_scenario=_TRIALS_PER_SCENARIO,
        records=records,
        issues=tuple(all_issues),
        record_matrix_complete=not all_issues,
        pass_1=PassStatistic(
            k=1,
            numerator=len(passing_keys),
            denominator=scenario_count * _TRIALS_PER_SCENARIO,
        ),
        pass_3=PassStatistic(
            k=3,
            numerator=all_three_passed,
            denominator=scenario_count,
        ),
    )


def canonical_replay_trial_json(record: ReplayTrialRecord) -> str:
    if not isinstance(record, ReplayTrialRecord):
        raise ValueError("record must be a ReplayTrialRecord")
    return _canonical_json(record.as_dict())


def replay_trial_digest(record: ReplayTrialRecord) -> str:
    return hashlib.sha256(canonical_replay_trial_json(record).encode("utf-8")).hexdigest()


def canonical_replay_result_json(result: ReplayExecutionResult) -> str:
    if not isinstance(result, ReplayExecutionResult):
        raise ValueError("result must be a ReplayExecutionResult")
    return _canonical_json(result.as_dict())


def replay_result_digest(result: ReplayExecutionResult) -> str:
    return hashlib.sha256(canonical_replay_result_json(result).encode("utf-8")).hexdigest()


__all__ = [
    "PassStatistic",
    "ReplayExecutionResult",
    "ReplayIssue",
    "ReplayIssueCode",
    "ReplayPlan",
    "ReplayScenarioFixture",
    "ReplayTrialRecord",
    "TrialStatus",
    "build_replay_plan",
    "canonical_replay_plan_json",
    "canonical_replay_result_json",
    "canonical_replay_trial_json",
    "derive_trial_seed",
    "execute_replay",
    "replay_plan_digest",
    "replay_result_digest",
    "replay_trial_digest",
    "summarize_trial_records",
]
