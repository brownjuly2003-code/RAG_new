from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from evaluation.resolution import (
    ArtifactKey,
    ArtifactKind,
    ArtifactPin,
    BranchRef,
    CandidateScenarioInput,
    CompiledCorpusScenario,
    CompiledResolutionScenarioCorpus,
    CompiledScenario,
    EligibilityDisposition,
    GradeFailureCode,
    HiddenExpectedState,
    MetricKind,
    ObservedResolutionState,
    OutcomeCheckCode,
    OutcomeCheckResult,
    OutcomeCheckStatus,
    OutcomeIssueCode,
    PersonaDefinition,
    ReplayScenarioFixture,
    ResolutionDisposition,
    ScenarioWorld,
    SyntheticMetricDefinition,
    SyntheticOutcomeLedger,
    SyntheticOutcomeRecord,
    TrialStatus,
    build_manifest_coverage_report,
    build_replay_manifest,
    build_replay_plan,
    build_synthetic_outcome_report,
    canonical_synthetic_metric_definition_json,
    canonical_synthetic_outcome_ledger_json,
    canonical_synthetic_outcome_record_json,
    canonical_synthetic_outcome_report_json,
    compiled_corpus_pin,
    corpus_digest,
    execute_replay,
    manifest_coverage_report_digest,
    metric_definition_digest,
    replay_manifest_digest,
    replay_plan_digest,
    replay_result_digest,
    replay_trial_digest,
    scenario_binding_digest,
    summarize_trial_records,
    synthetic_outcome_ledger_digest,
    synthetic_outcome_record_digest,
    synthetic_outcome_report_digest,
)
from resolution.contracts import TerminalOutcome, TransitionEvent


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _fixture(scenario_id: str, terminal: TerminalOutcome) -> ReplayScenarioFixture:
    scenario = CompiledScenario(
        candidate_input=CandidateScenarioInput(
            scenario_id=scenario_id,
            journey_id="aircargo.shipment-status",
            messages=(f"PRIVATE INPUT {scenario_id}",),
        ),
        world=ScenarioWorld(
            world_state_id=f"PRIVATE-WORLD-{scenario_id}",
            fault_ids=(f"PRIVATE-FAULT-{scenario_id}",),
        ),
        hidden_expected=HiddenExpectedState(
            contract_id="aircargo.shipment-status",
            contract_version="0.1.0",
            contract_digest="1" * 64,
            branch_path=(BranchRef(f"step-{scenario_id}", TransitionEvent.SUCCESS),),
            terminal_outcome=terminal,
            reason_codes=() if terminal is TerminalOutcome.VERIFIED else ("EXPECTED",),
            canonical_state=(("private.expected.path", scenario_id),),
        ),
    )
    return ReplayScenarioFixture(
        scenario=scenario,
        world_pin=_pin(ArtifactKind.WORLD, f"world-{scenario_id}", digest_char="7"),
        coverage_target_ids=(f"target-{scenario_id}",),
        dependency_keys=(ArtifactKey(ArtifactKind.POLICY, "shipment-policy"),),
    )


def _reference_run():
    fixtures = (
        _fixture("case-a", TerminalOutcome.VERIFIED),
        _fixture("case-b", TerminalOutcome.ESCALATED),
        _fixture("case-c", TerminalOutcome.VERIFIED),
    )
    contract_pin = _pin(
        ArtifactKind.CONTRACT,
        "aircargo.shipment-status",
        version="0.1.0",
        digest_char="1",
    )
    corpus = CompiledResolutionScenarioCorpus(
        corpus_id="shipment-status-synthetic",
        version="2026.08.23-g5-test",
        contract_pin=contract_pin,
        personas=(PersonaDefinition("persona-reference", "1.0.0", _digest("persona")),),
        adversarial_intents=(),
        faults=(),
        scenarios=tuple(
            CompiledCorpusScenario(
                fixture=fixture,
                persona_id="persona-reference",
                adversarial_intent_ids=(),
                fault_coverage_target_ids=(),
            )
            for fixture in fixtures
        ),
        required_branch_target_ids=tuple(
            target for fixture in fixtures for target in fixture.coverage_target_ids
        ),
    )
    manifest = build_replay_manifest(
        code_revision="1" * 40,
        contract_pin=contract_pin,
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
        scenario_set_pin=compiled_corpus_pin(corpus),
        dependencies=(_pin(ArtifactKind.POLICY, "shipment-policy", digest_char="6"),),
        scenarios=tuple(fixture.binding() for fixture in fixtures),
    )
    plan = build_replay_plan(manifest, base_seed=47)
    by_world = {fixture.scenario.world.world_state_id: fixture.scenario for fixture in fixtures}

    def generate(candidate_input: CandidateScenarioInput, seed: int) -> tuple[str, int]:
        return candidate_input.scenario_id, seed

    def execute(
        world: ScenarioWorld,
        _candidate: tuple[str, int],
    ) -> ObservedResolutionState:
        expected = by_world[world.world_state_id].hidden_expected
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

    result = execute_replay(
        manifest,
        plan,
        fixtures,
        generate_candidate=generate,
        execute_candidate=execute,
    )
    coverage = build_manifest_coverage_report(corpus, manifest)
    assert coverage.complete
    return corpus, manifest, coverage, plan, result


def _definition(*, recontact_window_days: int = 7) -> SyntheticMetricDefinition:
    return SyntheticMetricDefinition(
        definition_id="synthetic-vr-metrics",
        version="0.1.0",
        recontact_window_days=recontact_window_days,
    )


def _checks(
    status: OutcomeCheckStatus = OutcomeCheckStatus.PASS,
) -> tuple[OutcomeCheckResult, ...]:
    return tuple(OutcomeCheckResult(code, status) for code in OutcomeCheckCode)


def _record(
    scenario_id: str,
    *,
    manifest,
    replay_result,
    eligibility: EligibilityDisposition,
    resolution: ResolutionDisposition,
    checks: tuple[OutcomeCheckResult, ...] | None = None,
) -> SyntheticOutcomeRecord:
    binding = next(value for value in manifest.scenarios if value.scenario_id == scenario_id)
    trials = tuple(record for record in replay_result.records if record.scenario_id == scenario_id)
    return SyntheticOutcomeRecord(
        manifest_digest=replay_manifest_digest(manifest),
        replay_result_digest=replay_result_digest(replay_result),
        scenario_binding_digest=scenario_binding_digest(binding),
        scenario_id=scenario_id,
        replay_trial_digests=tuple(replay_trial_digest(record) for record in trials),
        outcome_evidence_digest=_digest(f"PRIVATE OUTCOME EVIDENCE {scenario_id}"),
        eligibility=eligibility,
        resolution=resolution,
        checks=checks or _checks(),
    )


def _ledger(
    *,
    definition,
    corpus,
    manifest,
    coverage,
    plan,
    replay_result,
    records,
) -> SyntheticOutcomeLedger:
    return SyntheticOutcomeLedger(
        ledger_id="shipment-status-synthetic-outcomes",
        version="2026.08.23-g5-test",
        metric_definition_digest=metric_definition_digest(definition),
        manifest_digest=replay_manifest_digest(manifest),
        corpus_digest=corpus_digest(corpus),
        coverage_report_digest=manifest_coverage_report_digest(coverage),
        replay_plan_digest=replay_plan_digest(plan),
        replay_result_digest=replay_result_digest(replay_result),
        records=tuple(records),
    )


def _reference_ledger():
    corpus, manifest, coverage, plan, replay_result = _reference_run()
    definition = _definition()
    records = (
        _record(
            "case-a",
            manifest=manifest,
            replay_result=replay_result,
            eligibility=EligibilityDisposition.ELIGIBLE,
            resolution=ResolutionDisposition.CLAIMED_AUTO,
        ),
        _record(
            "case-b",
            manifest=manifest,
            replay_result=replay_result,
            eligibility=EligibilityDisposition.ELIGIBLE,
            resolution=ResolutionDisposition.NOT_CLAIMED,
        ),
        _record(
            "case-c",
            manifest=manifest,
            replay_result=replay_result,
            eligibility=EligibilityDisposition.INELIGIBLE,
            resolution=ResolutionDisposition.CLAIMED_AUTO,
        ),
    )
    ledger = _ledger(
        definition=definition,
        corpus=corpus,
        manifest=manifest,
        coverage=coverage,
        plan=plan,
        replay_result=replay_result,
        records=records,
    )
    return definition, corpus, manifest, coverage, plan, replay_result, ledger


def _report(definition, corpus, manifest, coverage, plan, replay_result, ledger):
    return build_synthetic_outcome_report(
        definition=definition,
        corpus=corpus,
        manifest=manifest,
        coverage_report=coverage,
        plan=plan,
        replay_result=replay_result,
        ledger=ledger,
    )


def test_case_level_metrics_bind_all_three_trials_and_publish_together() -> None:
    values = _reference_ledger()
    report = _report(*values)

    assert report.structurally_complete
    assert report.business_claimable is False
    assert report.owner_status == "unconfirmed"
    assert (report.vr_precision.numerator, report.vr_precision.denominator) == (1, 2)
    assert (report.vry.numerator, report.vry.denominator) == (1, 2)
    assert (
        report.eligibility_coverage.numerator,
        report.eligibility_coverage.denominator,
    ) == (2, 3)
    assert report.vr_precision.kind is MetricKind.EXACT
    assert report.vry.kind is MetricKind.EXACT
    assert report.eligibility_coverage.kind is MetricKind.EXACT
    assert report.verified_scenario_ids == ("case-a",)
    assert report.unverified_claimed_scenario_ids == ("case-c",)
    assert report.issues == ()
    assert all(len(record.replay_trial_digests) == 3 for record in values[-1].records)


def test_missing_duplicate_extra_and_foreign_records_use_conservative_denominators() -> None:
    definition, corpus, manifest, coverage, plan, replay_result, ledger = _reference_ledger()
    case_a, case_b, case_c = ledger.records
    foreign_b = replace(case_b, manifest_digest="f" * 64)
    extra = replace(
        case_c,
        scenario_id="case-extra",
        scenario_binding_digest="e" * 64,
        outcome_evidence_digest=_digest("PRIVATE EXTRA EVIDENCE"),
    )
    malformed = replace(ledger, records=(case_a, case_a, foreign_b, extra))

    report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        plan,
        replay_result,
        malformed,
    )

    assert (report.vr_precision.numerator, report.vr_precision.denominator) == (0, 3)
    assert (report.vry.numerator, report.vry.denominator) == (0, 3)
    assert (
        report.eligibility_coverage.numerator,
        report.eligibility_coverage.denominator,
    ) == (0, 3)
    assert {issue.code for issue in report.issues} >= {
        OutcomeIssueCode.DUPLICATE_OUTCOME_RECORD,
        OutcomeIssueCode.FOREIGN_RECORD_MANIFEST,
        OutcomeIssueCode.MISSING_OUTCOME_RECORD,
        OutcomeIssueCode.EXTRA_OUTCOME_RECORD,
    }
    assert not report.structurally_complete
    assert all(
        metric.kind is MetricKind.LOWER_BOUND
        for metric in (
            report.vr_precision,
            report.vry,
            report.eligibility_coverage,
        )
    )


def test_global_identity_drift_and_partial_plan_zero_all_metric_credit() -> None:
    definition, corpus, manifest, coverage, plan, replay_result, ledger = _reference_ledger()

    foreign = replace(ledger, manifest_digest="f" * 64)
    foreign_report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        plan,
        replay_result,
        foreign,
    )
    assert foreign_report.verified_scenario_ids == ()
    assert foreign_report.vr_precision.numerator == 0
    assert foreign_report.vry.numerator == 0
    assert foreign_report.eligibility_coverage.numerator == 0
    assert OutcomeIssueCode.LEDGER_MANIFEST_MISMATCH in {
        issue.code for issue in foreign_report.issues
    }

    partial_plan = replace(
        plan,
        selected_scenario_ids=("case-a",),
        selection_complete=False,
    )
    partial_ledger = replace(
        ledger,
        replay_plan_digest=replay_plan_digest(partial_plan),
    )
    partial_report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        partial_plan,
        replay_result,
        partial_ledger,
    )
    assert partial_report.vr_precision.numerator == 0
    assert partial_report.vry.denominator == 3
    assert partial_report.eligibility_coverage.denominator == 3
    assert OutcomeIssueCode.REPLAY_PLAN_SCOPE_MISMATCH in {
        issue.code for issue in partial_report.issues
    }


def test_failed_replay_and_unknown_check_never_become_verified() -> None:
    definition, corpus, manifest, coverage, plan, replay_result, _ledger_value = _reference_ledger()
    first = replay_result.records[0]
    failed_records = (
        replace(
            first,
            status=TrialStatus.FAILED,
            grade_failure_codes=(GradeFailureCode.TERMINAL_OUTCOME_MISMATCH,),
        ),
        *replay_result.records[1:],
    )
    failed_result = summarize_trial_records(manifest, plan, failed_records)
    failed_ledger = _ledger(
        definition=definition,
        corpus=corpus,
        manifest=manifest,
        coverage=coverage,
        plan=plan,
        replay_result=failed_result,
        records=(
            _record(
                "case-a",
                manifest=manifest,
                replay_result=failed_result,
                eligibility=EligibilityDisposition.ELIGIBLE,
                resolution=ResolutionDisposition.CLAIMED_AUTO,
            ),
            _record(
                "case-b",
                manifest=manifest,
                replay_result=failed_result,
                eligibility=EligibilityDisposition.ELIGIBLE,
                resolution=ResolutionDisposition.NOT_CLAIMED,
            ),
            _record(
                "case-c",
                manifest=manifest,
                replay_result=failed_result,
                eligibility=EligibilityDisposition.INELIGIBLE,
                resolution=ResolutionDisposition.NOT_CLAIMED,
            ),
        ),
    )
    failed_report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        plan,
        failed_result,
        failed_ledger,
    )
    assert failed_report.vr_precision.numerator == 0
    assert failed_report.unverified_claimed_scenario_ids == ("case-a",)
    assert failed_report.structurally_complete

    unknown_checks = tuple(
        OutcomeCheckResult(
            code,
            OutcomeCheckStatus.UNKNOWN
            if code is OutcomeCheckCode.NO_RECONTACT_IN_WINDOW
            else OutcomeCheckStatus.PASS,
        )
        for code in OutcomeCheckCode
    )
    unknown_record = _record(
        "case-a",
        manifest=manifest,
        replay_result=replay_result,
        eligibility=EligibilityDisposition.ELIGIBLE,
        resolution=ResolutionDisposition.CLAIMED_AUTO,
        checks=unknown_checks,
    )
    exact_ledger = _reference_ledger()[-1]
    unknown_ledger = replace(
        exact_ledger,
        records=(unknown_record, *exact_ledger.records[1:]),
    )
    unknown_report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        plan,
        replay_result,
        unknown_ledger,
    )
    assert unknown_report.vr_precision.numerator == 0
    assert unknown_report.vr_precision.kind is MetricKind.LOWER_BOUND
    assert OutcomeIssueCode.UNKNOWN_OUTCOME_CHECK in {issue.code for issue in unknown_report.issues}


def test_zero_claim_and_zero_eligible_metrics_are_undefined_not_perfect() -> None:
    definition, corpus, manifest, coverage, plan, replay_result, ledger = _reference_ledger()
    no_scope_records = tuple(
        replace(
            record,
            eligibility=EligibilityDisposition.INELIGIBLE,
            resolution=ResolutionDisposition.NOT_CLAIMED,
        )
        for record in ledger.records
    )
    no_scope = replace(ledger, records=no_scope_records)

    report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        plan,
        replay_result,
        no_scope,
    )

    assert (report.vr_precision.numerator, report.vr_precision.denominator) == (0, 0)
    assert (report.vry.numerator, report.vry.denominator) == (0, 0)
    assert report.vr_precision.kind is MetricKind.UNDEFINED
    assert report.vry.kind is MetricKind.UNDEFINED
    assert (
        report.eligibility_coverage.numerator,
        report.eligibility_coverage.denominator,
    ) == (0, 3)
    assert report.eligibility_coverage.kind is MetricKind.EXACT
    assert report.structurally_complete


def test_canonical_artifacts_are_stable_sensitive_private_and_non_claimable() -> None:
    definition, corpus, manifest, coverage, plan, replay_result, ledger = _reference_ledger()
    report = _report(
        definition,
        corpus,
        manifest,
        coverage,
        plan,
        replay_result,
        ledger,
    )
    reordered = replace(ledger, records=tuple(reversed(ledger.records)))

    assert canonical_synthetic_outcome_ledger_json(reordered) == (
        canonical_synthetic_outcome_ledger_json(ledger)
    )
    assert synthetic_outcome_ledger_digest(reordered) == synthetic_outcome_ledger_digest(ledger)
    assert synthetic_outcome_record_digest(ledger.records[0]) != (
        synthetic_outcome_record_digest(
            replace(ledger.records[0], outcome_evidence_digest="f" * 64)
        )
    )
    assert metric_definition_digest(_definition(recontact_window_days=14)) != (
        metric_definition_digest(definition)
    )
    assert synthetic_outcome_report_digest(report) == synthetic_outcome_report_digest(report)
    with pytest.raises(TypeError):
        replace(ledger.records[0], verified=True)  # type: ignore[call-arg]

    payload = "\n".join(
        (
            canonical_synthetic_metric_definition_json(definition),
            canonical_synthetic_outcome_record_json(ledger.records[0]),
            canonical_synthetic_outcome_ledger_json(ledger),
            canonical_synthetic_outcome_report_json(report),
        )
    ).lower()
    assert '"business_claimable":false' in payload
    assert '"owner_status":"unconfirmed"' in payload
    for forbidden in (
        "private input",
        "private-world",
        "private-fault",
        "private.expected.path",
        "private outcome evidence",
        "private raw response",
        "response_text",
        "customer_id",
        "tenant_id",
        "promotion",
        "release_verdict",
        "latency",
        "cost",
    ):
        assert forbidden not in payload


def test_schema_rejects_missing_checks_and_claimable_definition() -> None:
    definition, _corpus, _manifest, _coverage, _plan, _result, ledger = _reference_ledger()
    with pytest.raises(ValueError, match="every required outcome check"):
        replace(ledger.records[0], checks=ledger.records[0].checks[:-1])
    with pytest.raises(ValueError, match="business_claimable"):
        replace(definition, business_claimable=True)
