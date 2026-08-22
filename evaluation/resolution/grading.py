from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from evaluation.resolution.scenarios import (
    BranchRef,
    CandidateScenarioInput,
    CanonicalState,
    CompiledScenario,
    HiddenExpectedState,
    ScenarioWorld,
    _require_text,
    _validate_canonical_state,
)
from resolution.contracts import TerminalOutcome


class EvaluatorStatus(StrEnum):
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class EvaluationInfrastructureFailure:
    status: EvaluatorStatus
    reason_code: str

    def __post_init__(self) -> None:
        _require_text(self.reason_code, "evaluator infrastructure reason_code")


@dataclass(frozen=True, slots=True)
class ObservedResolutionState:
    contract_id: str
    contract_version: str
    contract_digest: str
    branch_path: tuple[BranchRef, ...]
    terminal_outcome: TerminalOutcome
    reason_codes: tuple[str, ...]
    canonical_state: CanonicalState
    response_text: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.contract_id, "observed contract_id")
        _require_text(self.contract_version, "observed contract_version")
        _require_text(self.contract_digest, "observed contract_digest")
        if not self.branch_path:
            raise ValueError("observed branch_path cannot be empty")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("observed reason_codes must be unique")
        for reason_code in self.reason_codes:
            _require_text(reason_code, "observed reason_code")
        _validate_canonical_state(self.canonical_state)
        if self.response_text is not None:
            _require_text(self.response_text, "observed response_text")


class GradeFailureCode(StrEnum):
    EVALUATOR_INFRASTRUCTURE_FAILURE = "evaluator_infrastructure_failure"
    CONTRACT_IDENTITY_MISMATCH = "contract_identity_mismatch"
    BRANCH_PATH_MISMATCH = "branch_path_mismatch"
    TERMINAL_OUTCOME_MISMATCH = "terminal_outcome_mismatch"
    REASON_CODES_MISMATCH = "reason_codes_mismatch"
    STATE_MISMATCH = "state_mismatch"


@dataclass(frozen=True, slots=True)
class GradeResult:
    failure_codes: tuple[GradeFailureCode, ...]

    @property
    def passed(self) -> bool:
        return not self.failure_codes


def grade_state(
    expected: HiddenExpectedState,
    observed: ObservedResolutionState | EvaluationInfrastructureFailure,
) -> GradeResult:
    if isinstance(observed, EvaluationInfrastructureFailure):
        return GradeResult((GradeFailureCode.EVALUATOR_INFRASTRUCTURE_FAILURE,))

    failures: list[GradeFailureCode] = []
    if (
        observed.contract_id,
        observed.contract_version,
        observed.contract_digest,
    ) != (
        expected.contract_id,
        expected.contract_version,
        expected.contract_digest,
    ):
        failures.append(GradeFailureCode.CONTRACT_IDENTITY_MISMATCH)
    if observed.branch_path != expected.branch_path:
        failures.append(GradeFailureCode.BRANCH_PATH_MISMATCH)
    if observed.terminal_outcome is not expected.terminal_outcome:
        failures.append(GradeFailureCode.TERMINAL_OUTCOME_MISMATCH)
    if observed.reason_codes != expected.reason_codes:
        failures.append(GradeFailureCode.REASON_CODES_MISMATCH)
    if observed.canonical_state != expected.canonical_state:
        failures.append(GradeFailureCode.STATE_MISMATCH)
    return GradeResult(tuple(failures))


_CandidateT = TypeVar("_CandidateT")


def evaluate_scenario(
    scenario: CompiledScenario,
    *,
    generate_candidate: Callable[[CandidateScenarioInput], _CandidateT],
    execute_candidate: Callable[
        [ScenarioWorld, _CandidateT],
        ObservedResolutionState | EvaluationInfrastructureFailure,
    ],
) -> GradeResult:
    try:
        candidate = generate_candidate(scenario.candidate_input)
        observed = execute_candidate(scenario.world, candidate)
    except Exception:
        observed = EvaluationInfrastructureFailure(
            status=EvaluatorStatus.ERROR,
            reason_code="EVALUATOR_INFRASTRUCTURE_EXCEPTION",
        )
    return grade_state(scenario.hidden_expected, observed)


__all__ = [
    "EvaluationInfrastructureFailure",
    "EvaluatorStatus",
    "GradeFailureCode",
    "GradeResult",
    "ObservedResolutionState",
    "evaluate_scenario",
    "grade_state",
]
