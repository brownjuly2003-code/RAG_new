from __future__ import annotations

from dataclasses import dataclass

from resolution.contracts import (
    ResolutionContract,
    StepKind,
    TerminalOutcome,
    TransitionEvent,
    contract_digest,
)
from resolution.contracts.models import StepTransitionTarget, TerminalTransitionTarget

CanonicalState = tuple[tuple[str, str], ...]


def _require_text(value: str, field: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty without surrounding whitespace")


def _validate_canonical_state(state: CanonicalState) -> None:
    paths = [path for path, _value in state]
    if len(paths) != len(set(paths)):
        raise ValueError("canonical state paths must be unique")
    for path, value in state:
        _require_text(path, "canonical state path")
        _require_text(value, "canonical state value")
    if state != tuple(sorted(state)):
        raise ValueError("canonical state entries must be sorted")


@dataclass(frozen=True, slots=True)
class BranchRef:
    step_id: str
    event: TransitionEvent

    def __post_init__(self) -> None:
        _require_text(self.step_id, "branch step_id")


@dataclass(frozen=True, slots=True)
class BranchCoverageTarget:
    contract_id: str
    contract_version: str
    contract_digest: str
    step_id: str
    step_kind: StepKind
    event: TransitionEvent
    destination: str
    target_id: str


@dataclass(frozen=True, slots=True)
class CandidateScenarioInput:
    scenario_id: str
    journey_id: str
    messages: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        _require_text(self.journey_id, "journey_id")
        if not self.messages:
            raise ValueError("candidate messages cannot be empty")
        if any(not message or message != message.strip() for message in self.messages):
            raise ValueError("candidate messages must be non-empty trimmed text")

    def as_dict(self) -> dict[str, object]:
        return {
            "journey_id": self.journey_id,
            "messages": list(self.messages),
            "scenario_id": self.scenario_id,
        }


@dataclass(frozen=True, slots=True)
class ScenarioWorld:
    world_state_id: str
    fault_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.world_state_id, "world_state_id")
        if len(self.fault_ids) != len(set(self.fault_ids)):
            raise ValueError("scenario fault_ids must be unique")
        for fault_id in self.fault_ids:
            _require_text(fault_id, "fault_id")


@dataclass(frozen=True, slots=True)
class HiddenExpectedState:
    contract_id: str
    contract_version: str
    contract_digest: str
    branch_path: tuple[BranchRef, ...]
    terminal_outcome: TerminalOutcome
    reason_codes: tuple[str, ...]
    canonical_state: CanonicalState

    def __post_init__(self) -> None:
        _require_text(self.contract_id, "expected contract_id")
        _require_text(self.contract_version, "expected contract_version")
        _require_text(self.contract_digest, "expected contract_digest")
        if not self.branch_path:
            raise ValueError("expected branch_path cannot be empty")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("expected reason_codes must be unique")
        for reason_code in self.reason_codes:
            _require_text(reason_code, "expected reason_code")
        _validate_canonical_state(self.canonical_state)


@dataclass(frozen=True, slots=True)
class CompiledScenario:
    candidate_input: CandidateScenarioInput
    world: ScenarioWorld
    hidden_expected: HiddenExpectedState


def _destination(target: StepTransitionTarget | TerminalTransitionTarget) -> str:
    if isinstance(target, StepTransitionTarget):
        return f"step:{target.id}"
    return f"terminal:{target.outcome.value}"


def compile_branch_targets(contract: ResolutionContract) -> tuple[BranchCoverageTarget, ...]:
    digest = contract_digest(contract)
    targets: list[BranchCoverageTarget] = []
    for step in contract.steps:
        for event, target in step.transitions.items():
            destination = _destination(target)
            targets.append(
                BranchCoverageTarget(
                    contract_id=contract.id,
                    contract_version=contract.version,
                    contract_digest=digest,
                    step_id=step.id,
                    step_kind=step.kind,
                    event=event,
                    destination=destination,
                    target_id=(
                        f"{contract.id}@{contract.version}#{digest}:"
                        f"{step.id}:{event.value}:{destination}"
                    ),
                )
            )
    return tuple(sorted(targets, key=lambda item: (item.step_id, item.event.value)))


def compile_scenario(
    *,
    contract: ResolutionContract,
    candidate_input: CandidateScenarioInput,
    world: ScenarioWorld,
    branch_path: tuple[BranchRef, ...],
    terminal_outcome: TerminalOutcome,
    reason_codes: tuple[str, ...],
    canonical_state: CanonicalState,
) -> CompiledScenario:
    if candidate_input.journey_id != contract.id:
        raise ValueError("candidate journey_id does not match the contract")
    if not branch_path:
        raise ValueError("expected branch_path cannot be empty")

    steps = {step.id: step for step in contract.steps}
    for branch in branch_path:
        step = steps.get(branch.step_id)
        if step is None or branch.event not in step.transitions:
            raise ValueError(f"unknown branch '{branch.step_id}.{branch.event.value}'")
    if branch_path[0].step_id != contract.entrypoint:
        raise ValueError("expected branch_path must start at the contract entrypoint")

    for index, branch in enumerate(branch_path):
        step = steps[branch.step_id]
        target = step.transitions[branch.event]
        is_last = index == len(branch_path) - 1
        if isinstance(target, TerminalTransitionTarget):
            if not is_last:
                raise ValueError("expected branch_path continues after terminal")
            if target.outcome is not terminal_outcome:
                raise ValueError("expected terminal outcome does not match the branch path")
            continue
        if is_last:
            raise ValueError("expected branch_path does not reach a terminal outcome")
        if branch_path[index + 1].step_id != target.id:
            raise ValueError("expected branch_path contains a disconnected branch")

    expected = HiddenExpectedState(
        contract_id=contract.id,
        contract_version=contract.version,
        contract_digest=contract_digest(contract),
        branch_path=branch_path,
        terminal_outcome=terminal_outcome,
        reason_codes=reason_codes,
        canonical_state=canonical_state,
    )
    return CompiledScenario(
        candidate_input=candidate_input,
        world=world,
        hidden_expected=expected,
    )


__all__ = [
    "BranchCoverageTarget",
    "BranchRef",
    "CandidateScenarioInput",
    "CanonicalState",
    "CompiledScenario",
    "HiddenExpectedState",
    "ScenarioWorld",
    "compile_branch_targets",
    "compile_scenario",
]
