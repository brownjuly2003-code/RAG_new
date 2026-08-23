from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.resolution import (
    ComparisonIssueCode,
    ComparisonRole,
    EligibilityDisposition,
    MetricKind,
    ObservedResolutionState,
    OutcomeCheckCode,
    OutcomeCheckResult,
    OutcomeCheckStatus,
    PassStatistic,
    ReplayExecutionResult,
    ResolutionDisposition,
    SyntheticComparisonCompatibilityError,
    SyntheticMetricDefinition,
    SyntheticOutcomeLedger,
    SyntheticOutcomeRecord,
    VerificationDisposition,
    build_manifest_coverage_report,
    build_replay_plan,
    build_synthetic_outcome_comparison_input,
    build_synthetic_outcome_comparison_report,
    canonical_synthetic_outcome_comparison_input_json,
    canonical_synthetic_outcome_comparison_report_json,
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
    synthetic_outcome_comparison_input_digest,
    synthetic_outcome_comparison_report_digest,
)
from evaluation.resolution.scenarios import CandidateScenarioInput, ScenarioWorld
from resolution.contracts import TerminalOutcome
from tests.test_resolution_corpus import _compiled_and_manifest

_ARTIFACT_DIR = Path(__file__).parents[1] / "evaluation" / "resolution" / "comparisons" / "v0.1"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _definition(*, recontact_window_days: int = 7) -> SyntheticMetricDefinition:
    return SyntheticMetricDefinition(
        definition_id="synthetic-vr-metrics",
        version="0.1.0",
        recontact_window_days=recontact_window_days,
    )


def _checks(
    failing_code: OutcomeCheckCode | None = None,
) -> tuple[OutcomeCheckResult, ...]:
    return tuple(
        OutcomeCheckResult(
            code,
            OutcomeCheckStatus.FAIL if code is failing_code else OutcomeCheckStatus.PASS,
        )
        for code in OutcomeCheckCode
    )


def _run(
    *,
    role: ComparisonRole,
    definition: SyntheticMetricDefinition,
    corpus=None,
):
    _contract, _authoring, reference_corpus, reference_manifest = _compiled_and_manifest()
    compiled = corpus or reference_corpus
    role_char = "a" if role is ComparisonRole.BASELINE else "b"
    manifest = replace(
        reference_manifest,
        code_revision=role_char * 40,
        candidate_pin=replace(
            reference_manifest.candidate_pin,
            version=f"2026.08.23-g6-{role.value}",
            digest=_digest(f"PRIVATE {role.value} CANDIDATE IMPLEMENTATION"),
        ),
        scenario_set_pin=compiled_corpus_pin(compiled),
    )
    coverage = build_manifest_coverage_report(compiled, manifest)
    assert coverage.complete
    plan = build_replay_plan(manifest, base_seed=61)
    fixtures = tuple(item.fixture for item in compiled.scenarios)
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
    assert result.record_matrix_complete
    verified_terminal_ids = tuple(
        item.scenario_id
        for item in compiled.scenarios
        if item.fixture.scenario.hidden_expected.terminal_outcome is TerminalOutcome.VERIFIED
    )
    assert verified_terminal_ids
    nonverified_claim_id = next(
        item.scenario_id
        for item in compiled.scenarios
        if item.scenario_id not in verified_terminal_ids
    )
    records: list[SyntheticOutcomeRecord] = []
    for item in compiled.scenarios:
        scenario_id = item.scenario_id
        expected_verified = scenario_id in verified_terminal_ids
        failing_code = None
        if role is ComparisonRole.BASELINE and scenario_id == verified_terminal_ids[0]:
            failing_code = OutcomeCheckCode.MATERIAL_CLAIMS_SUPPORTED
        elif role is ComparisonRole.CANDIDATE and scenario_id == nonverified_claim_id:
            failing_code = OutcomeCheckCode.CONTRACT_OR_ALLOWED_PATH
        if expected_verified or (
            role is ComparisonRole.CANDIDATE and scenario_id == nonverified_claim_id
        ):
            resolution = ResolutionDisposition.CLAIMED_AUTO
        else:
            resolution = ResolutionDisposition.NOT_CLAIMED
        binding = next(value for value in manifest.scenarios if value.scenario_id == scenario_id)
        trials = tuple(value for value in result.records if value.scenario_id == scenario_id)
        records.append(
            SyntheticOutcomeRecord(
                manifest_digest=replay_manifest_digest(manifest),
                replay_result_digest=replay_result_digest(result),
                scenario_binding_digest=scenario_binding_digest(binding),
                scenario_id=scenario_id,
                replay_trial_digests=tuple(replay_trial_digest(value) for value in trials),
                outcome_evidence_digest=_digest(
                    f"PRIVATE {role.value} OUTCOME EVIDENCE {scenario_id}"
                ),
                eligibility=EligibilityDisposition.ELIGIBLE,
                resolution=resolution,
                checks=_checks(failing_code),
            )
        )
    ledger = SyntheticOutcomeLedger(
        ledger_id=f"shipment-status-{role.value}-outcomes",
        version=f"2026.08.23-g6-{role.value}",
        metric_definition_digest=metric_definition_digest(definition),
        manifest_digest=replay_manifest_digest(manifest),
        corpus_digest=corpus_digest(compiled),
        coverage_report_digest=manifest_coverage_report_digest(coverage),
        replay_plan_digest=replay_plan_digest(plan),
        replay_result_digest=replay_result_digest(result),
        records=tuple(records),
    )
    comparison_input = build_synthetic_outcome_comparison_input(
        role=role,
        input_id=f"shipment-status-{role.value}",
        version=f"2026.08.23-g6-{role.value}",
        definition=definition,
        corpus=compiled,
        manifest=manifest,
        coverage_report=coverage,
        plan=plan,
        replay_result=result,
        ledger=ledger,
    )
    return (
        comparison_input,
        compiled,
        manifest,
        plan,
        result,
        verified_terminal_ids,
        nonverified_claim_id,
    )


def _pair(*, definition: SyntheticMetricDefinition | None = None):
    definition_value = definition or _definition()
    baseline = _run(role=ComparisonRole.BASELINE, definition=definition_value)
    candidate = _run(role=ComparisonRole.CANDIDATE, definition=definition_value)
    report = build_synthetic_outcome_comparison_report(
        comparison_id="shipment-status-synthetic-comparison",
        version="2026.08.23-g6",
        baseline=baseline[0],
        candidate=candidate[0],
    )
    return baseline, candidate, report


def test_full_corpus_inputs_compare_distinct_exact_runs_without_a_verdict() -> None:
    baseline, candidate, report = _pair()
    (
        baseline_input,
        corpus,
        baseline_manifest,
        baseline_plan,
        baseline_result,
        verified_ids,
        nonverified_claim_id,
    ) = baseline
    candidate_input, _, candidate_manifest, candidate_plan, candidate_result, _, _ = candidate

    assert report.corpus_case_count == len(corpus.scenarios) == 17
    assert baseline_input.metric_definition_digest == candidate_input.metric_definition_digest
    assert baseline_input.corpus_digest == candidate_input.corpus_digest
    assert replay_manifest_digest(baseline_manifest) != replay_manifest_digest(candidate_manifest)
    assert replay_plan_digest(baseline_plan) != replay_plan_digest(candidate_plan)
    assert replay_result_digest(baseline_result) != replay_result_digest(candidate_result)
    assert report.baseline.manifest_digest != report.candidate.manifest_digest
    assert report.baseline.replay_plan_digest != report.candidate.replay_plan_digest
    assert report.baseline.replay_result_digest != report.candidate.replay_result_digest

    assert report.vr_precision.baseline.numerator == len(verified_ids) - 1
    assert report.vr_precision.candidate.numerator == len(verified_ids)
    assert report.vr_precision.numerator_delta == 1
    assert report.vr_precision.denominator_delta == 1
    assert report.vry.numerator_delta == 1
    assert report.vry.denominator_delta == 0
    assert report.eligibility_coverage.numerator_delta == 0
    assert report.eligibility_coverage.denominator_delta == 0
    assert all(
        metric.baseline.kind is MetricKind.EXACT and metric.candidate.kind is MetricKind.EXACT
        for metric in (
            report.vr_precision,
            report.vry,
            report.eligibility_coverage,
        )
    )
    assert sum(transition.count for transition in report.case_transitions) == 17
    assert {
        scenario_id
        for transition in report.case_transitions
        for scenario_id in transition.scenario_ids
    } == {item.scenario_id for item in corpus.scenarios}
    assert any(
        transition.baseline.verification is VerificationDisposition.UNVERIFIED
        and transition.candidate.verification is VerificationDisposition.VERIFIED
        and transition.scenario_ids == (verified_ids[0],)
        for transition in report.case_transitions
    )
    assert any(
        transition.baseline.verification is VerificationDisposition.NOT_APPLICABLE
        and transition.candidate.verification is VerificationDisposition.UNVERIFIED
        and transition.scenario_ids == (nonverified_claim_id,)
        for transition in report.case_transitions
    )
    assert report.business_claimable is False
    assert report.owner_status == "unconfirmed"
    assert not hasattr(report, "promotion_verdict")
    assert not hasattr(report, "threshold")


@pytest.mark.parametrize(
    "field",
    ("manifest_digest", "replay_plan_digest", "replay_result_digest"),
)
def test_internal_ledger_report_run_drift_fails_closed(field: str) -> None:
    baseline, _candidate, _report = _pair()
    comparison_input = baseline[0]
    drifted_report = replace(comparison_input.report, **{field: "f" * 64})

    with pytest.raises(SyntheticComparisonCompatibilityError) as error:
        replace(comparison_input, report=drifted_report)

    assert ComparisonIssueCode.INPUT_BINDING_MISMATCH in error.value.issue_codes


def test_cross_pair_definition_and_universe_drift_fail_closed() -> None:
    baseline = _run(role=ComparisonRole.BASELINE, definition=_definition())[0]
    foreign_definition = _run(
        role=ComparisonRole.CANDIDATE,
        definition=_definition(recontact_window_days=14),
    )[0]
    with pytest.raises(SyntheticComparisonCompatibilityError) as definition_error:
        build_synthetic_outcome_comparison_report(
            comparison_id="shipment-status-synthetic-comparison",
            version="2026.08.23-g6",
            baseline=baseline,
            candidate=foreign_definition,
        )
    assert ComparisonIssueCode.METRIC_DEFINITION_MISMATCH in (definition_error.value.issue_codes)

    _contract, _authoring, corpus, _manifest = _compiled_and_manifest()
    foreign_corpus = replace(corpus, version="2026.08.23-g6-foreign-universe")
    foreign_universe = _run(
        role=ComparisonRole.CANDIDATE,
        definition=_definition(),
        corpus=foreign_corpus,
    )[0]
    with pytest.raises(SyntheticComparisonCompatibilityError) as universe_error:
        build_synthetic_outcome_comparison_report(
            comparison_id="shipment-status-synthetic-comparison",
            version="2026.08.23-g6",
            baseline=baseline,
            candidate=foreign_universe,
        )
    assert ComparisonIssueCode.CORPUS_UNIVERSE_MISMATCH in (universe_error.value.issue_codes)


def test_incomplete_full_run_cannot_be_materialized_as_a_comparison_input() -> None:
    definition = _definition()
    _contract, _authoring, corpus, manifest = _compiled_and_manifest()
    manifest = replace(
        manifest,
        code_revision="a" * 40,
        candidate_pin=replace(manifest.candidate_pin, digest=_digest("BASELINE")),
    )
    coverage = build_manifest_coverage_report(corpus, manifest)
    plan = build_replay_plan(manifest, base_seed=61)
    result = ReplayExecutionResult(
        plan_digest=replay_plan_digest(plan),
        manifest_digest=replay_manifest_digest(manifest),
        scenario_count=17,
        trials_per_scenario=3,
        records=(),
        issues=(),
        record_matrix_complete=False,
        pass_1=PassStatistic(k=1, numerator=0, denominator=51),
        pass_3=PassStatistic(k=3, numerator=0, denominator=17),
    )
    ledger = SyntheticOutcomeLedger(
        ledger_id="shipment-status-baseline-outcomes",
        version="2026.08.23-g6-baseline",
        metric_definition_digest=metric_definition_digest(definition),
        manifest_digest=replay_manifest_digest(manifest),
        corpus_digest=corpus_digest(corpus),
        coverage_report_digest=manifest_coverage_report_digest(coverage),
        replay_plan_digest=replay_plan_digest(plan),
        replay_result_digest=replay_result_digest(result),
        records=(),
    )

    with pytest.raises(SyntheticComparisonCompatibilityError) as error:
        build_synthetic_outcome_comparison_input(
            role=ComparisonRole.BASELINE,
            input_id="shipment-status-baseline",
            version="2026.08.23-g6-baseline",
            definition=definition,
            corpus=corpus,
            manifest=manifest,
            coverage_report=coverage,
            plan=plan,
            replay_result=result,
            ledger=ledger,
        )

    assert ComparisonIssueCode.INPUT_NOT_STRUCTURALLY_COMPLETE in (error.value.issue_codes)


def test_canonical_artifacts_are_materialized_stable_and_private() -> None:
    baseline, candidate, report = _pair()
    baseline_input = baseline[0]
    candidate_input = candidate[0]
    expected = {
        "shipment-status-baseline": (
            canonical_synthetic_outcome_comparison_input_json(baseline_input),
            synthetic_outcome_comparison_input_digest(baseline_input),
        ),
        "shipment-status-candidate": (
            canonical_synthetic_outcome_comparison_input_json(candidate_input),
            synthetic_outcome_comparison_input_digest(candidate_input),
        ),
        "shipment-status-comparison": (
            canonical_synthetic_outcome_comparison_report_json(report),
            synthetic_outcome_comparison_report_digest(report),
        ),
    }
    for artifact_name, (canonical, digest) in expected.items():
        payload = json.loads((_ARTIFACT_DIR / f"{artifact_name}.json").read_text(encoding="utf-8"))
        normalized = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        assert normalized == canonical
        assert (_ARTIFACT_DIR / f"{artifact_name}.sha256").read_text(
            encoding="utf-8"
        ).strip() == digest

    reordered = replace(
        baseline_input,
        ledger=replace(
            baseline_input.ledger,
            records=tuple(reversed(baseline_input.ledger.records)),
        ),
    )
    assert canonical_synthetic_outcome_comparison_input_json(reordered) == (
        canonical_synthetic_outcome_comparison_input_json(baseline_input)
    )
    assert synthetic_outcome_comparison_report_digest(report) == (
        synthetic_outcome_comparison_report_digest(report)
    )

    payload = "\n".join(
        (
            canonical_synthetic_outcome_comparison_input_json(baseline_input),
            canonical_synthetic_outcome_comparison_input_json(candidate_input),
            canonical_synthetic_outcome_comparison_report_json(report),
        )
    ).lower()
    assert '"business_claimable":false' in payload
    assert '"owner_status":"unconfirmed"' in payload
    for forbidden in (
        "private candidate message",
        "private-world",
        "private-fault",
        "private.expected.path",
        "private outcome evidence",
        "private raw response",
        "response_text",
        "customer_id",
        "tenant_id",
        "threshold",
        "promotion",
        "release_verdict",
        "live_shadow",
        "rate_delta",
        "percent",
    ):
        assert forbidden not in payload

    with pytest.raises(TypeError):
        replace(report, promotion_verdict="promote")  # type: ignore[call-arg]
