from __future__ import annotations

from dataclasses import replace

import pytest

from evaluation.resolution import (
    ArtifactKey,
    ArtifactKind,
    ArtifactPin,
    BranchRef,
    CandidateScenarioInput,
    CompiledScenario,
    EvaluationInfrastructureFailure,
    EvaluatorStatus,
    HiddenExpectedState,
    ImpactSelectionReport,
    ObservedResolutionState,
    ReplayIssueCode,
    ReplayManifest,
    ReplayScenarioFixture,
    ScenarioWorld,
    SelectionMode,
    TrialStatus,
    bind_scenario,
    build_replay_manifest,
    build_replay_plan,
    canonical_replay_plan_json,
    canonical_replay_result_json,
    canonical_replay_trial_json,
    derive_trial_seed,
    execute_replay,
    replay_manifest_digest,
    replay_plan_digest,
    replay_result_digest,
    replay_trial_digest,
    scenario_binding_digest,
    summarize_trial_records,
)
from resolution.contracts import TerminalOutcome, TransitionEvent

_CONTRACT_ID = "aircargo.shipment-status"
_CONTRACT_VERSION = "0.1.0"
_CONTRACT_DIGEST = "1" * 64


def _pin(
    kind: ArtifactKind,
    artifact_id: str,
    *,
    version: str = "1.0.0",
    digest_char: str = "a",
) -> ArtifactPin:
    return ArtifactPin(
        kind=kind,
        artifact_id=artifact_id,
        version=version,
        digest=digest_char * 64,
    )


def _scenario(scenario_id: str) -> CompiledScenario:
    return CompiledScenario(
        candidate_input=CandidateScenarioInput(
            scenario_id=scenario_id,
            journey_id=_CONTRACT_ID,
            messages=(f"PRIVATE INPUT {scenario_id}",),
        ),
        world=ScenarioWorld(
            world_state_id=f"PRIVATE-WORLD-{scenario_id}",
            fault_ids=(f"PRIVATE-FAULT-{scenario_id}",),
        ),
        hidden_expected=HiddenExpectedState(
            contract_id=_CONTRACT_ID,
            contract_version=_CONTRACT_VERSION,
            contract_digest=_CONTRACT_DIGEST,
            branch_path=(BranchRef("read-shipment", TransitionEvent.SUCCESS),),
            terminal_outcome=TerminalOutcome.VERIFIED,
            reason_codes=(),
            canonical_state=(("private.expected.path", f"PRIVATE-{scenario_id}"),),
        ),
    )


def _fixture(scenario_id: str) -> ReplayScenarioFixture:
    return ReplayScenarioFixture(
        scenario=_scenario(scenario_id),
        world_pin=_pin(
            ArtifactKind.WORLD,
            f"world-{scenario_id}",
            digest_char="7",
        ),
        coverage_target_ids=(f"target-{scenario_id}",),
        dependency_keys=(ArtifactKey(ArtifactKind.POLICY, "shipment-policy"),),
    )


def _manifest(
    fixtures: tuple[ReplayScenarioFixture, ...] | None = None,
) -> ReplayManifest:
    fixture_values = fixtures or (_fixture("scenario-a"), _fixture("scenario-b"))
    return build_replay_manifest(
        code_revision="1" * 40,
        contract_pin=_pin(
            ArtifactKind.CONTRACT,
            _CONTRACT_ID,
            version=_CONTRACT_VERSION,
            digest_char="1",
        ),
        scenario_compiler_pin=_pin(
            ArtifactKind.SCENARIO_COMPILER,
            "resolution-scenario-compiler",
            digest_char="2",
        ),
        state_grader_pin=_pin(
            ArtifactKind.STATE_GRADER,
            "resolution-state-grader",
            digest_char="3",
        ),
        candidate_pin=_pin(
            ArtifactKind.CANDIDATE,
            "shipment-candidate",
            digest_char="4",
        ),
        scenario_set_pin=_pin(
            ArtifactKind.SCENARIO_SET,
            "shipment-resolution-cases",
            digest_char="5",
        ),
        dependencies=(
            _pin(
                ArtifactKind.POLICY,
                "shipment-policy",
                digest_char="6",
            ),
        ),
        scenarios=tuple(
            bind_scenario(
                fixture.scenario,
                world_pin=fixture.world_pin,
                coverage_target_ids=fixture.coverage_target_ids,
                dependency_keys=fixture.dependency_keys,
            )
            for fixture in fixture_values
        ),
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
        response_text="PRIVATE RAW RESPONSE",
    )


def _passing_callbacks(
    fixture_by_world: dict[str, CompiledScenario],
) -> tuple[object, object]:
    def generate(candidate_input: CandidateScenarioInput, seed: int) -> tuple[str, int]:
        return candidate_input.scenario_id, seed

    def execute(
        world: ScenarioWorld,
        _candidate: tuple[str, int],
    ) -> ObservedResolutionState:
        return _observation(fixture_by_world[world.world_state_id])

    return generate, execute


def _execute_passing(
    manifest: ReplayManifest,
    fixtures: tuple[ReplayScenarioFixture, ...],
    *,
    base_seed: int = 41,
):
    plan = build_replay_plan(manifest, base_seed=base_seed)
    by_world = {fixture.scenario.world.world_state_id: fixture.scenario for fixture in fixtures}
    generate, execute = _passing_callbacks(by_world)
    return plan, execute_replay(
        manifest,
        plan,
        fixtures,
        generate_candidate=generate,  # type: ignore[arg-type]
        execute_candidate=execute,  # type: ignore[arg-type]
    )


def test_plan_and_trial_order_are_deterministic_and_seeded() -> None:
    fixtures = (_fixture("scenario-b"), _fixture("scenario-a"))
    manifest = _manifest(fixtures)
    plan, result = _execute_passing(manifest, fixtures)

    assert plan.selected_scenario_ids == ("scenario-a", "scenario-b")
    assert [(record.scenario_id, record.trial_ordinal) for record in result.records] == [
        ("scenario-a", 1),
        ("scenario-a", 2),
        ("scenario-a", 3),
        ("scenario-b", 1),
        ("scenario-b", 2),
        ("scenario-b", 3),
    ]
    assert [record.seed for record in result.records] == [
        derive_trial_seed(plan, record.scenario_id, record.trial_ordinal)
        for record in result.records
    ]
    changed_plan = build_replay_plan(manifest, base_seed=42)
    assert replay_plan_digest(changed_plan) != replay_plan_digest(plan)
    assert derive_trial_seed(changed_plan, "scenario-a", 1) != derive_trial_seed(
        plan, "scenario-a", 1
    )


def test_impact_selection_is_bound_and_no_change_cannot_create_success() -> None:
    manifest = _manifest()
    manifest_digest = replay_manifest_digest(manifest)
    report = ImpactSelectionReport(
        baseline_manifest_digest="e" * 64,
        candidate_manifest_digest=manifest_digest,
        mode=SelectionMode.TARGETED,
        selected_scenario_ids=("scenario-b",),
        removed_scenario_ids=(),
        changed_dependency_keys=(),
        reason_codes=(),
        complete=True,
    )

    plan = build_replay_plan(manifest, base_seed=1, impact_report=report)
    assert plan.selected_scenario_ids == ("scenario-b",)
    assert plan.selection_report_digest is not None

    with pytest.raises(ValueError, match="candidate manifest"):
        build_replay_plan(
            manifest,
            base_seed=1,
            impact_report=replace(report, candidate_manifest_digest="f" * 64),
        )

    no_change = ImpactSelectionReport(
        baseline_manifest_digest=manifest_digest,
        candidate_manifest_digest=manifest_digest,
        mode=SelectionMode.NO_CHANGE,
        selected_scenario_ids=(),
        removed_scenario_ids=(),
        changed_dependency_keys=(),
        reason_codes=(),
        complete=True,
    )
    with pytest.raises(ValueError, match="no replay work"):
        build_replay_plan(manifest, base_seed=1, impact_report=no_change)


def test_generator_receives_only_public_input_and_derived_seed() -> None:
    fixture = _fixture("scenario-a")
    manifest = _manifest((fixture,))
    plan = build_replay_plan(manifest, base_seed=9)
    calls: list[tuple[CandidateScenarioInput, int]] = []

    def generate(candidate_input: CandidateScenarioInput, seed: int) -> str:
        calls.append((candidate_input, seed))
        return "candidate"

    def execute(_world: ScenarioWorld, _candidate: str) -> ObservedResolutionState:
        return _observation(fixture.scenario)

    result = execute_replay(
        manifest,
        plan,
        (fixture,),
        generate_candidate=generate,
        execute_candidate=execute,
    )

    assert [call[0] for call in calls] == [fixture.scenario.candidate_input] * 3
    assert [call[1] for call in calls] == [
        derive_trial_seed(plan, "scenario-a", ordinal) for ordinal in (1, 2, 3)
    ]
    assert all(record.status is TrialStatus.PASSED for record in result.records)


@pytest.mark.parametrize(
    "drift",
    (
        "candidate",
        "world",
        "fault",
        "hidden",
        "world_pin",
        "coverage",
        "dependency",
    ),
)
def test_fixture_drift_fails_closed_before_candidate_invocation(drift: str) -> None:
    fixture = _fixture("scenario-a")
    manifest = _manifest((fixture,))
    scenario = fixture.scenario
    if drift == "candidate":
        scenario = replace(
            scenario,
            candidate_input=replace(scenario.candidate_input, messages=("DRIFT",)),
        )
    elif drift == "world":
        scenario = replace(
            scenario,
            world=replace(scenario.world, world_state_id="DRIFT-WORLD"),
        )
    elif drift == "fault":
        scenario = replace(
            scenario,
            world=replace(scenario.world, fault_ids=("DRIFT-FAULT",)),
        )
    elif drift == "hidden":
        scenario = replace(
            scenario,
            hidden_expected=replace(
                scenario.hidden_expected,
                canonical_state=(("private.expected.path", "DRIFT"),),
            ),
        )

    changed = replace(fixture, scenario=scenario)
    if drift == "world_pin":
        changed = replace(changed, world_pin=replace(changed.world_pin, digest="8" * 64))
    elif drift == "coverage":
        changed = replace(changed, coverage_target_ids=("target-drift",))
    elif drift == "dependency":
        changed = replace(
            changed,
            dependency_keys=(ArtifactKey(ArtifactKind.CONFIG, "drift-config"),),
        )

    calls = 0

    def generate(_candidate_input: CandidateScenarioInput, _seed: int) -> str:
        nonlocal calls
        calls += 1
        return "candidate"

    result = execute_replay(
        manifest,
        build_replay_plan(manifest, base_seed=1),
        (changed,),
        generate_candidate=generate,
        execute_candidate=lambda _world, _candidate: _observation(changed.scenario),
    )

    assert calls == 0
    assert len(result.records) == 3
    assert [record.trial_ordinal for record in result.records] == [1, 2, 3]
    assert all(record.status is TrialStatus.ERROR for record in result.records)
    assert not result.record_matrix_complete
    assert ReplayIssueCode.SCENARIO_BINDING_MISMATCH in {issue.code for issue in result.issues}
    assert result.pass_1.numerator == 0
    assert result.pass_1.denominator == 3


@pytest.mark.parametrize("drift", ("manifest_pin", "candidate_journey"))
def test_contract_identity_drift_fails_closed_before_invocation(drift: str) -> None:
    fixture = _fixture("scenario-a")
    if drift == "candidate_journey":
        fixture = replace(
            fixture,
            scenario=replace(
                fixture.scenario,
                candidate_input=replace(
                    fixture.scenario.candidate_input,
                    journey_id="aircargo.other-journey",
                ),
            ),
        )
    manifest = _manifest((fixture,))
    if drift == "manifest_pin":
        manifest = replace(
            manifest,
            contract_pin=_pin(
                ArtifactKind.CONTRACT,
                _CONTRACT_ID,
                version="0.2.0",
                digest_char="9",
            ),
        )
    calls = 0

    def generate(_candidate_input: CandidateScenarioInput, _seed: int) -> str:
        nonlocal calls
        calls += 1
        return "candidate"

    result = execute_replay(
        manifest,
        build_replay_plan(manifest, base_seed=1),
        (fixture,),
        generate_candidate=generate,
        execute_candidate=lambda _world, _candidate: _observation(fixture.scenario),
    )

    assert calls == 0
    assert len(result.records) == 3
    assert all(record.status is TrialStatus.ERROR for record in result.records)
    assert ReplayIssueCode.CONTRACT_IDENTITY_MISMATCH in {issue.code for issue in result.issues}


def test_pass_one_and_pass_three_use_fixed_three_trial_denominators() -> None:
    fixtures = (_fixture("scenario-a"), _fixture("scenario-b"))
    manifest = _manifest(fixtures)
    plan = build_replay_plan(manifest, base_seed=17)
    by_world = {fixture.scenario.world.world_state_id: fixture.scenario for fixture in fixtures}
    failing_seed = derive_trial_seed(plan, "scenario-a", 1)

    def generate(candidate_input: CandidateScenarioInput, seed: int) -> tuple[str, int]:
        return candidate_input.scenario_id, seed

    def execute(
        world: ScenarioWorld,
        candidate: tuple[str, int],
    ) -> ObservedResolutionState:
        observed = _observation(by_world[world.world_state_id])
        if candidate[1] == failing_seed:
            return replace(observed, terminal_outcome=TerminalOutcome.ESCALATED)
        return observed

    result = execute_replay(
        manifest,
        plan,
        fixtures,
        generate_candidate=generate,
        execute_candidate=execute,
    )

    assert (result.pass_1.numerator, result.pass_1.denominator) == (5, 6)
    assert (result.pass_3.numerator, result.pass_3.denominator) == (1, 2)
    assert result.record_matrix_complete


def test_two_of_three_passes_is_not_pass_at_three() -> None:
    fixture = _fixture("scenario-a")
    manifest = _manifest((fixture,))
    plan = build_replay_plan(manifest, base_seed=17)
    failing_seed = derive_trial_seed(plan, "scenario-a", 1)

    def execute(_world: ScenarioWorld, candidate: int) -> ObservedResolutionState:
        observed = _observation(fixture.scenario)
        if candidate == failing_seed:
            return replace(observed, terminal_outcome=TerminalOutcome.ESCALATED)
        return observed

    result = execute_replay(
        manifest,
        plan,
        (fixture,),
        generate_candidate=lambda _candidate_input, seed: seed,
        execute_candidate=execute,
    )

    assert (result.pass_1.numerator, result.pass_1.denominator) == (2, 3)
    assert (result.pass_3.numerator, result.pass_3.denominator) == (0, 1)


def test_error_and_skipped_trials_are_structural_records_but_not_passes() -> None:
    fixture = _fixture("scenario-a")
    manifest = _manifest((fixture,))
    plan = build_replay_plan(manifest, base_seed=23)
    seeds = [derive_trial_seed(plan, "scenario-a", ordinal) for ordinal in (1, 2, 3)]

    def generate(_candidate_input: CandidateScenarioInput, seed: int) -> int:
        if seed == seeds[0]:
            raise RuntimeError("PRIVATE EXCEPTION")
        return seed

    def execute(
        _world: ScenarioWorld,
        candidate: int,
    ) -> ObservedResolutionState | EvaluationInfrastructureFailure:
        if candidate == seeds[1]:
            return EvaluationInfrastructureFailure(
                status=EvaluatorStatus.SKIPPED,
                reason_code="PRIVATE_SKIP_REASON",
            )
        return _observation(fixture.scenario)

    result = execute_replay(
        manifest,
        plan,
        (fixture,),
        generate_candidate=generate,
        execute_candidate=execute,
    )

    assert [record.status for record in result.records] == [
        TrialStatus.ERROR,
        TrialStatus.SKIPPED,
        TrialStatus.PASSED,
    ]
    assert result.record_matrix_complete
    assert (result.pass_1.numerator, result.pass_1.denominator) == (1, 3)
    assert (result.pass_3.numerator, result.pass_3.denominator) == (0, 1)


def test_fixture_topology_errors_preserve_denominators_and_skip_invalid_work() -> None:
    fixture_a = _fixture("scenario-a")
    fixture_b = _fixture("scenario-b")
    manifest = _manifest((fixture_a, fixture_b))
    plan = build_replay_plan(manifest, base_seed=3)
    extra = _fixture("scenario-extra")
    calls: list[str] = []

    def generate(candidate_input: CandidateScenarioInput, _seed: int) -> str:
        calls.append(candidate_input.scenario_id)
        return candidate_input.scenario_id

    result = execute_replay(
        manifest,
        plan,
        (fixture_a, fixture_a, extra),
        generate_candidate=generate,
        execute_candidate=lambda _world, _candidate: _observation(fixture_a.scenario),
    )

    issue_codes = {issue.code for issue in result.issues}
    assert ReplayIssueCode.DUPLICATE_SCENARIO in issue_codes
    assert ReplayIssueCode.MISSING_SCENARIO in issue_codes
    assert ReplayIssueCode.EXTRA_SCENARIO in issue_codes
    assert calls == []
    assert len(result.records) == 6
    assert all(record.status is TrialStatus.ERROR for record in result.records)
    assert not result.record_matrix_complete
    assert (result.pass_1.numerator, result.pass_1.denominator) == (0, 6)
    assert (result.pass_3.numerator, result.pass_3.denominator) == (0, 2)


def test_record_summarizer_rejects_missing_duplicate_extra_and_foreign_evidence() -> None:
    fixture = _fixture("scenario-a")
    manifest = _manifest((fixture,))
    plan, executed = _execute_passing(manifest, (fixture,))
    first, second, third = executed.records
    malformed = (
        first,
        first,
        replace(second, manifest_digest="f" * 64),
        replace(third, seed=third.seed + 1),
        replace(third, trial_ordinal=4),
    )

    result = summarize_trial_records(manifest, plan, malformed)

    issue_codes = {issue.code for issue in result.issues}
    assert ReplayIssueCode.DUPLICATE_TRIAL in issue_codes
    assert ReplayIssueCode.FOREIGN_MANIFEST in issue_codes
    assert ReplayIssueCode.INVALID_TRIAL_IDENTITY in issue_codes
    assert ReplayIssueCode.EXTRA_TRIAL in issue_codes
    assert ReplayIssueCode.MISSING_TRIAL in issue_codes
    assert not result.record_matrix_complete
    assert (result.pass_1.numerator, result.pass_1.denominator) == (0, 3)
    assert (result.pass_3.numerator, result.pass_3.denominator) == (0, 1)


def test_fail_closed_impact_selection_never_becomes_complete() -> None:
    fixtures = (_fixture("scenario-a"), _fixture("scenario-b"))
    manifest = _manifest(fixtures)
    report = ImpactSelectionReport(
        baseline_manifest_digest="e" * 64,
        candidate_manifest_digest=replay_manifest_digest(manifest),
        mode=SelectionMode.FULL_FAIL_CLOSED,
        selected_scenario_ids=("scenario-a", "scenario-b"),
        removed_scenario_ids=(),
        changed_dependency_keys=(),
        reason_codes=(),
        complete=False,
    )
    plan = build_replay_plan(manifest, base_seed=4, impact_report=report)
    by_world = {fixture.scenario.world.world_state_id: fixture.scenario for fixture in fixtures}
    generate, execute = _passing_callbacks(by_world)

    result = execute_replay(
        manifest,
        plan,
        fixtures,
        generate_candidate=generate,  # type: ignore[arg-type]
        execute_candidate=execute,  # type: ignore[arg-type]
    )

    assert (result.pass_1.numerator, result.pass_1.denominator) == (6, 6)
    assert (result.pass_3.numerator, result.pass_3.denominator) == (2, 2)
    assert not result.record_matrix_complete
    assert ReplayIssueCode.IMPACT_SELECTION_INCOMPLETE in {issue.code for issue in result.issues}


def test_canonical_artifacts_are_stable_sensitive_and_compartmentalized() -> None:
    fixture = _fixture("scenario-a")
    manifest = _manifest((fixture,))
    plan, result = _execute_passing(manifest, (fixture,))
    record = result.records[0]

    assert replay_plan_digest(plan) == replay_plan_digest(plan)
    assert replay_trial_digest(record) == replay_trial_digest(record)
    assert replay_result_digest(result) == replay_result_digest(result)
    assert replay_trial_digest(replace(record, observation_digest="f" * 64)) != replay_trial_digest(
        record
    )

    payload = "\n".join(
        (
            canonical_replay_plan_json(plan),
            canonical_replay_trial_json(record),
            canonical_replay_result_json(result),
        )
    ).lower()
    for forbidden in (
        "private input",
        "private-world",
        "private-fault",
        "private.expected.path",
        "private raw response",
        "response_text",
        "latency",
        "cost",
        "vr_precision",
        "vry",
        "recontact",
        "promotion",
        "release_verdict",
    ):
        assert forbidden not in payload
    assert scenario_binding_digest(manifest.scenarios[0]) == scenario_binding_digest(
        manifest.scenarios[0]
    )


def test_replay_identity_validation_rejects_invalid_seed_and_trial_count() -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="base_seed"):
        build_replay_plan(manifest, base_seed=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exactly 3"):
        replace(build_replay_plan(manifest, base_seed=1), trials_per_scenario=2)

    fixture = _fixture("scenario-a")
    single_manifest = _manifest((fixture,))
    plan, result = _execute_passing(single_manifest, (fixture,))
    with pytest.raises(ValueError, match="trial_ordinal"):
        derive_trial_seed(plan, "scenario-a", 0)
    with pytest.raises(ValueError, match="selected scenario"):
        derive_trial_seed(plan, "scenario-b", 1)
    with pytest.raises(ValueError, match="failure_codes"):
        replace(
            result.records[0],
            status=TrialStatus.FAILED,
            grade_failure_codes=(),
        )
