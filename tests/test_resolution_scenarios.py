from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.resolution import (
    BranchRef,
    CandidateScenarioInput,
    CompiledScenario,
    EvaluationInfrastructureFailure,
    EvaluatorStatus,
    GradeFailureCode,
    HiddenExpectedState,
    ObservedResolutionState,
    ScenarioWorld,
    compile_branch_targets,
    compile_scenario,
    evaluate_scenario,
    grade_state,
)
from resolution.contracts import ResolutionContract, TerminalOutcome, TransitionEvent

_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "resolution_contracts"
    / "v0.1"
    / "valid"
    / "shipment-status.json"
)


def _contract() -> ResolutionContract:
    return ResolutionContract.model_validate_json(_FIXTURE.read_text(encoding="utf-8"))


def _public_input(scenario_id: str = "happy") -> CandidateScenarioInput:
    return CandidateScenarioInput(
        scenario_id=scenario_id,
        journey_id="aircargo.shipment-status",
        messages=("Status SHP-100?",),
    )


def _canonical_state() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                ("connector.shipment-status-lookup.status", "verified"),
                ("disclosure.ai-assistance.shown", "true"),
                ("disclosure.ai-assistance.version", "1.0.0"),
                ("evidence.shipment-observation.digest", "a" * 64),
                ("evidence.shipment-policy.digest", "b" * 64),
                ("policy.shipment-policy-allows-status.decision", "allow"),
                ("postconditions.shipment-observation-current.result", "pass"),
            )
        )
    )


def _happy_path() -> tuple[BranchRef, ...]:
    return (
        BranchRef("validate-inputs", TransitionEvent.COMPLETE),
        BranchRef("read-shipment", TransitionEvent.SUCCESS),
        BranchRef("gather-policy", TransitionEvent.COMPLETE),
        BranchRef("apply-policy", TransitionEvent.ALLOW),
        BranchRef("check-shipment-observation", TransitionEvent.PASS),
        BranchRef("compile-response", TransitionEvent.SUCCESS),
    )


def _happy_scenario() -> CompiledScenario:
    return compile_scenario(
        contract=_contract(),
        candidate_input=_public_input(),
        world=ScenarioWorld(world_state_id="shipment-world/v1"),
        branch_path=_happy_path(),
        terminal_outcome=TerminalOutcome.VERIFIED,
        reason_codes=(),
        canonical_state=_canonical_state(),
    )


def _observation(scenario: CompiledScenario) -> ObservedResolutionState:
    expected = scenario.hidden_expected
    return ObservedResolutionState(
        contract_id=expected.contract_id,
        contract_version=expected.contract_version,
        contract_digest=expected.contract_digest,
        branch_path=expected.branch_path,
        terminal_outcome=expected.terminal_outcome,
        reason_codes=expected.reason_codes,
        canonical_state=expected.canonical_state,
        response_text="Shipment SHP-100 is in transit.",
    )


def _replace_state(
    state: tuple[tuple[str, str], ...],
    path: str,
    value: str,
) -> tuple[tuple[str, str], ...]:
    return tuple((key, value if key == path else current) for key, current in state)


def test_shipment_contract_compiles_all_explicit_branch_targets_deterministically() -> None:
    first = compile_branch_targets(_contract())
    second = compile_branch_targets(_contract())

    assert len(first) == 22
    assert first == second
    assert len({target.target_id for target in first}) == 22
    assert [(target.step_id, target.event.value) for target in first] == sorted(
        (target.step_id, target.event.value) for target in first
    )
    assert {target.event for target in first if target.step_id == "gather-policy"} == {
        TransitionEvent.COMPLETE,
        TransitionEvent.MISSING,
        TransitionEvent.STALE,
        TransitionEvent.CONFLICT,
        TransitionEvent.FAILURE,
    }


@pytest.mark.parametrize(
    ("branch_path", "terminal", "match"),
    (
        (
            (BranchRef("unknown-step", TransitionEvent.FAILURE),),
            TerminalOutcome.ESCALATED,
            "unknown branch",
        ),
        (
            (
                BranchRef("validate-inputs", TransitionEvent.COMPLETE),
                BranchRef("gather-policy", TransitionEvent.COMPLETE),
            ),
            TerminalOutcome.ESCALATED,
            "disconnected branch",
        ),
        (
            _happy_path(),
            TerminalOutcome.ESCALATED,
            "terminal outcome",
        ),
        (
            (
                BranchRef("validate-inputs", TransitionEvent.MISSING),
                BranchRef("validate-inputs", TransitionEvent.FAILURE),
            ),
            TerminalOutcome.CLARIFICATION_REQUIRED,
            "continues after terminal",
        ),
    ),
    ids=("unknown", "disconnected", "wrong-terminal", "after-terminal"),
)
def test_scenario_compilation_rejects_invalid_hidden_branch_paths(
    branch_path: tuple[BranchRef, ...],
    terminal: TerminalOutcome,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        compile_scenario(
            contract=_contract(),
            candidate_input=_public_input("invalid"),
            world=ScenarioWorld(world_state_id="shipment-world/v1"),
            branch_path=branch_path,
            terminal_outcome=terminal,
            reason_codes=(),
            canonical_state=_canonical_state(),
        )


def test_exact_observed_state_passes_and_fluent_wrong_terminal_fails() -> None:
    scenario = _happy_scenario()
    observed = _observation(scenario)

    assert grade_state(scenario.hidden_expected, observed).passed

    fluent_but_wrong = replace(
        observed,
        terminal_outcome=TerminalOutcome.ESCALATED,
        response_text="Your shipment was resolved successfully and everything is fine.",
    )
    grade = grade_state(scenario.hidden_expected, fluent_but_wrong)
    assert not grade.passed
    assert GradeFailureCode.TERMINAL_OUTCOME_MISMATCH in grade.failure_codes


def test_same_terminal_but_wrong_branch_fails() -> None:
    contract = _contract()
    scenario = compile_scenario(
        contract=contract,
        candidate_input=_public_input("missing-policy"),
        world=ScenarioWorld(world_state_id="shipment-world/missing-policy"),
        branch_path=(
            BranchRef("validate-inputs", TransitionEvent.COMPLETE),
            BranchRef("read-shipment", TransitionEvent.SUCCESS),
            BranchRef("gather-policy", TransitionEvent.MISSING),
        ),
        terminal_outcome=TerminalOutcome.ESCALATED,
        reason_codes=("SOURCE_UNAVAILABLE",),
        canonical_state=(("evidence.shipment-policy.status", "missing"),),
    )
    observed = _observation(scenario)
    wrong_branch = replace(
        observed,
        branch_path=(
            BranchRef("validate-inputs", TransitionEvent.COMPLETE),
            BranchRef("read-shipment", TransitionEvent.SUCCESS),
            BranchRef("gather-policy", TransitionEvent.STALE),
        ),
    )

    grade = grade_state(scenario.hidden_expected, wrong_branch)
    assert not grade.passed
    assert GradeFailureCode.BRANCH_PATH_MISMATCH in grade.failure_codes


@pytest.mark.parametrize(
    ("path", "broken_value"),
    (
        ("policy.shipment-policy-allows-status.decision", "deny"),
        ("evidence.shipment-policy.digest", "c" * 64),
        ("connector.shipment-status-lookup.status", "unverified"),
        ("postconditions.shipment-observation-current.result", "fail"),
        ("disclosure.ai-assistance.shown", "false"),
        ("disclosure.ai-assistance.version", "0.9.0"),
    ),
    ids=("policy", "retriever", "connector", "postcondition", "disclosure", "disclosure-version"),
)
def test_each_broken_deterministic_business_state_fails(
    path: str,
    broken_value: str,
) -> None:
    scenario = _happy_scenario()
    observed = _observation(scenario)
    broken = replace(
        observed,
        canonical_state=_replace_state(observed.canonical_state, path, broken_value),
        response_text="A fluent answer that must not affect deterministic grading.",
    )

    grade = grade_state(scenario.hidden_expected, broken)
    assert not grade.passed
    assert GradeFailureCode.STATE_MISMATCH in grade.failure_codes


def test_wrong_contract_identity_fails() -> None:
    scenario = _happy_scenario()
    observed = replace(_observation(scenario), contract_digest="f" * 64)

    grade = grade_state(scenario.hidden_expected, observed)
    assert not grade.passed
    assert GradeFailureCode.CONTRACT_IDENTITY_MISMATCH in grade.failure_codes


@pytest.mark.parametrize("status", (EvaluatorStatus.ERROR, EvaluatorStatus.SKIPPED))
def test_evaluator_error_or_skip_fails_closed(status: EvaluatorStatus) -> None:
    expected = _happy_scenario().hidden_expected
    failure = EvaluationInfrastructureFailure(
        status=status,
        reason_code="EVALUATOR_INFRASTRUCTURE_UNAVAILABLE",
    )

    grade = grade_state(expected, failure)
    assert not grade.passed
    assert grade.failure_codes == (GradeFailureCode.EVALUATOR_INFRASTRUCTURE_FAILURE,)


def test_candidate_generation_receives_only_public_input() -> None:
    scenario = _happy_scenario()
    seen: list[dict[str, object]] = []

    def generate(candidate_input: CandidateScenarioInput) -> str:
        seen.append(candidate_input.as_dict())
        return "candidate answer"

    def execute(world: ScenarioWorld, candidate: str) -> ObservedResolutionState:
        assert world.world_state_id == "shipment-world/v1"
        assert candidate == "candidate answer"
        return _observation(scenario)

    grade = evaluate_scenario(
        scenario,
        generate_candidate=generate,
        execute_candidate=execute,
    )

    assert grade.passed
    assert seen == [
        {
            "journey_id": "aircargo.shipment-status",
            "messages": ["Status SHP-100?"],
            "scenario_id": "happy",
        }
    ]
    assert all("expected" not in key and "terminal" not in key for key in seen[0])


def test_hidden_expected_state_rejects_duplicate_canonical_paths() -> None:
    scenario = _happy_scenario()
    expected = scenario.hidden_expected

    with pytest.raises(ValueError, match="canonical state paths must be unique"):
        HiddenExpectedState(
            contract_id=expected.contract_id,
            contract_version=expected.contract_version,
            contract_digest=expected.contract_digest,
            branch_path=expected.branch_path,
            terminal_outcome=expected.terminal_outcome,
            reason_codes=expected.reason_codes,
            canonical_state=(("policy.result", "allow"), ("policy.result", "deny")),
        )
