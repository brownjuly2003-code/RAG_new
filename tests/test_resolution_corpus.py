from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.resolution import (
    AdversarialIntentDefinition,
    ArtifactKey,
    ArtifactKind,
    ArtifactPin,
    BranchRef,
    CandidateScenarioInput,
    CompiledScenario,
    CorpusCoverageIssueCode,
    CorpusScenario,
    FaultDefinition,
    FaultSurface,
    HiddenExpectedState,
    PersonaDefinition,
    ResolutionScenarioCorpus,
    ScenarioWorld,
    build_manifest_coverage_report,
    build_replay_manifest,
    canonical_corpus_json,
    canonical_manifest_coverage_report_json,
    compile_corpus,
    compiled_corpus_pin,
    corpus_digest,
    manifest_coverage_report_digest,
    scenario_binding_digest,
)
from resolution.contracts import (
    ResolutionContract,
    TerminalOutcome,
    TransitionEvent,
    contract_digest,
)
from resolution.contracts.models import (
    StepTransitionTarget,
    TerminalTransitionTarget,
)

_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "resolution_contracts"
    / "v0.1"
    / "valid"
    / "shipment-status.json"
)
_CORPUS_ARTIFACT = (
    Path(__file__).parents[1]
    / "evaluation"
    / "resolution"
    / "corpora"
    / "v0.1"
    / "shipment-status.json"
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contract() -> ResolutionContract:
    return ResolutionContract.model_validate_json(_FIXTURE.read_text(encoding="utf-8"))


def _pin(
    kind: ArtifactKind,
    artifact_id: str,
    *,
    version: str = "1.0.0",
    digest_source: str | None = None,
) -> ArtifactPin:
    return ArtifactPin(
        kind=kind,
        artifact_id=artifact_id,
        version=version,
        digest=_digest(digest_source or f"{kind.value}:{artifact_id}:{version}"),
    )


def _terminal_paths(
    contract: ResolutionContract,
) -> tuple[tuple[tuple[BranchRef, ...], TerminalOutcome], ...]:
    steps = {step.id: step for step in contract.steps}
    paths: list[tuple[tuple[BranchRef, ...], TerminalOutcome]] = []

    def visit(
        step_id: str,
        path: tuple[BranchRef, ...],
        visited: frozenset[str],
    ) -> None:
        if step_id in visited:
            raise AssertionError("reference contract unexpectedly contains a cycle")
        step = steps[step_id]
        for event, target in step.transitions.items():
            next_path = (*path, BranchRef(step_id, event))
            if isinstance(target, TerminalTransitionTarget):
                paths.append((next_path, target.outcome))
            elif isinstance(target, StepTransitionTarget):
                visit(target.id, next_path, visited | {step_id})
            else:  # pragma: no cover - closed contract target union
                raise AssertionError("unknown transition target")

    visit(contract.entrypoint, (), frozenset())
    return tuple(
        sorted(
            paths,
            key=lambda item: (
                item[0][-1].step_id,
                item[0][-1].event.value,
            ),
        )
    )


def _personas() -> tuple[PersonaDefinition, ...]:
    return (
        PersonaDefinition("persona-direct", "1.0.0", _digest("PRIVATE DIRECT PERSONA")),
        PersonaDefinition(
            "persona-ambiguous",
            "1.0.0",
            _digest("PRIVATE AMBIGUOUS PERSONA"),
        ),
        PersonaDefinition(
            "persona-correction",
            "1.0.0",
            _digest("PRIVATE CORRECTION PERSONA"),
        ),
    )


def _adversarial_intents() -> tuple[AdversarialIntentDefinition, ...]:
    return (
        AdversarialIntentDefinition(
            "intent-prompt-injection",
            "1.0.0",
            _digest("PRIVATE PROMPT INJECTION PAYLOAD"),
        ),
        AdversarialIntentDefinition(
            "intent-cross-tenant",
            "1.0.0",
            _digest("PRIVATE CROSS TENANT PAYLOAD"),
        ),
        AdversarialIntentDefinition(
            "intent-pii-exfiltration",
            "1.0.0",
            _digest("PRIVATE PII PAYLOAD"),
        ),
        AdversarialIntentDefinition(
            "intent-success-pressure",
            "1.0.0",
            _digest("PRIVATE FALSE SUCCESS PAYLOAD"),
        ),
    )


_FAULT_ROWS = (
    (FaultSurface.CONTRACT, "fcov-1023456789abcdef1023456789abcdef"),
    (FaultSurface.POLICY, "fcov-213456789abcdef0213456789abcdef0"),
    (FaultSurface.RETRIEVER, "fcov-32456789abcdef0132456789abcdef01"),
    (FaultSurface.CONNECTOR, "fcov-4356789abcdef0124356789abcdef012"),
    (FaultSurface.POSTCONDITION, "fcov-546789abcdef0123546789abcdef0123"),
    (FaultSurface.DISCLOSURE, "fcov-65789abcdef0123465789abcdef01234"),
    (
        FaultSurface.EVALUATOR_INFRASTRUCTURE,
        "fcov-7689abcdef0123457689abcdef012345",
    ),
)


def _faults() -> tuple[FaultDefinition, ...]:
    return tuple(
        FaultDefinition(
            fault_id=f"private-fault-{surface.value}",
            version="1.0.0",
            content_digest=_digest(f"PRIVATE FAULT PAYLOAD {surface.value}"),
            surface=surface,
            coverage_target_id=coverage_target_id,
            required=True,
        )
        for surface, coverage_target_id in _FAULT_ROWS
    )


def _authoring_corpus(
    *,
    omit_terminal: tuple[str, str] | None = None,
    omit_fault_surface: FaultSurface | None = None,
) -> tuple[ResolutionContract, ResolutionScenarioCorpus]:
    contract = _contract()
    paths = _terminal_paths(contract)
    personas = _personas()
    adversarial = _adversarial_intents()
    faults = _faults()
    fault_by_surface = {fault.surface: fault for fault in faults}
    scenarios: list[CorpusScenario] = []

    for index, (branch_path, terminal) in enumerate(paths):
        terminal_key = (branch_path[-1].step_id, branch_path[-1].event.value)
        if terminal_key == omit_terminal:
            continue
        fault_ids: tuple[str, ...] = ()
        if index < len(_FAULT_ROWS):
            surface = _FAULT_ROWS[index][0]
            if surface is not omit_fault_surface:
                fault_ids = (fault_by_surface[surface].fault_id,)
        scenario_id = f"case-{index + 1:02d}"
        scenario = CompiledScenario(
            candidate_input=CandidateScenarioInput(
                scenario_id=scenario_id,
                journey_id=contract.id,
                messages=(f"PRIVATE CANDIDATE MESSAGE {scenario_id}",),
            ),
            world=ScenarioWorld(
                world_state_id=f"PRIVATE-WORLD-{scenario_id}",
                fault_ids=fault_ids,
            ),
            hidden_expected=HiddenExpectedState(
                contract_id=contract.id,
                contract_version=contract.version,
                contract_digest=contract_digest(contract),
                branch_path=branch_path,
                terminal_outcome=terminal,
                reason_codes=() if terminal is TerminalOutcome.VERIFIED else ("EXPECTED",),
                canonical_state=(("private.expected.path", f"PRIVATE-{scenario_id}"),),
            ),
        )
        intent_ids: tuple[str, ...] = ()
        if index < len(adversarial):
            intent_ids = (adversarial[index].intent_id,)
        scenarios.append(
            CorpusScenario(
                scenario=scenario,
                world_pin=_pin(
                    ArtifactKind.WORLD,
                    f"world-{scenario_id}",
                    digest_source=f"PRIVATE WORLD PIN {scenario_id}",
                ),
                dependency_keys=(ArtifactKey(ArtifactKind.POLICY, "shipment-policy"),),
                persona_id=personas[index % len(personas)].persona_id,
                adversarial_intent_ids=intent_ids,
            )
        )

    corpus = ResolutionScenarioCorpus(
        corpus_id="shipment-status-synthetic",
        version="2026.08.22-g4",
        contract_pin=ArtifactPin(
            kind=ArtifactKind.CONTRACT,
            artifact_id=contract.id,
            version=contract.version,
            digest=contract_digest(contract),
        ),
        personas=personas,
        adversarial_intents=adversarial,
        faults=faults,
        scenarios=tuple(scenarios),
    )
    return contract, corpus


def _compiled_and_manifest(
    *,
    omit_terminal: tuple[str, str] | None = None,
    omit_fault_surface: FaultSurface | None = None,
):
    contract, authoring = _authoring_corpus(
        omit_terminal=omit_terminal,
        omit_fault_surface=omit_fault_surface,
    )
    compiled = compile_corpus(authoring, contract=contract)
    dependencies = (_pin(ArtifactKind.POLICY, "shipment-policy"),)
    manifest = build_replay_manifest(
        code_revision="1" * 40,
        contract_pin=authoring.contract_pin,
        scenario_compiler_pin=_pin(
            ArtifactKind.SCENARIO_COMPILER,
            "resolution-scenario-compiler",
        ),
        state_grader_pin=_pin(ArtifactKind.STATE_GRADER, "resolution-state-grader"),
        candidate_pin=_pin(ArtifactKind.CANDIDATE, "shipment-candidate"),
        scenario_set_pin=compiled_corpus_pin(compiled),
        dependencies=dependencies,
        scenarios=tuple(item.fixture.binding() for item in compiled.scenarios),
    )
    return contract, authoring, compiled, manifest


def test_reference_corpus_derives_all_contract_branches_and_required_faults() -> None:
    contract, _authoring, compiled, manifest = _compiled_and_manifest()

    report = build_manifest_coverage_report(compiled, manifest)

    assert len(_terminal_paths(contract)) == 17
    assert report.complete
    assert report.issues == ()
    assert (report.branch_coverage.covered, report.branch_coverage.required) == (22, 22)
    assert (report.fault_coverage.covered, report.fault_coverage.required) == (7, 7)
    assert manifest.scenario_set_pin == compiled_corpus_pin(compiled)
    assert {fault.surface for fault in compiled.faults if fault.required} == set(FaultSurface)


def test_checked_in_corpus_artifact_matches_canonical_digest() -> None:
    _contract_value, _authoring, compiled, _manifest = _compiled_and_manifest()
    payload = json.loads(_CORPUS_ARTIFACT.read_text(encoding="utf-8"))
    normalized = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    assert normalized == canonical_corpus_json(compiled)
    assert _CORPUS_ARTIFACT.with_suffix(".sha256").read_text(encoding="utf-8").strip() == (
        corpus_digest(compiled)
    )


def test_branch_coverage_is_derived_from_valid_hidden_paths() -> None:
    contract, authoring = _authoring_corpus()

    with pytest.raises(TypeError, match="coverage_target_ids"):
        CorpusScenario(  # type: ignore[call-arg]
            scenario=authoring.scenarios[0].scenario,
            world_pin=authoring.scenarios[0].world_pin,
            dependency_keys=authoring.scenarios[0].dependency_keys,
            persona_id=authoring.scenarios[0].persona_id,
            adversarial_intent_ids=(),
            coverage_target_ids=("caller-claimed-target",),
        )

    invalid = replace(
        authoring.scenarios[0].scenario,
        hidden_expected=replace(
            authoring.scenarios[0].scenario.hidden_expected,
            branch_path=(
                BranchRef("validate-inputs", TransitionEvent.COMPLETE),
                BranchRef("gather-policy", TransitionEvent.COMPLETE),
            ),
        ),
    )
    invalid_authoring = replace(
        authoring,
        scenarios=(replace(authoring.scenarios[0], scenario=invalid), *authoring.scenarios[1:]),
    )
    with pytest.raises(ValueError, match="disconnected branch"):
        compile_corpus(invalid_authoring, contract=contract)


def test_missing_branch_keeps_exact_contract_denominator_and_fails_closed() -> None:
    _contract_value, _authoring, compiled, manifest = _compiled_and_manifest(
        omit_terminal=("compile-response", "failure")
    )

    report = build_manifest_coverage_report(compiled, manifest)

    assert not report.complete
    assert report.branch_coverage.required == 22
    assert report.branch_coverage.covered == 21
    assert len(report.missing_branch_target_ids) == 1
    assert any(
        issue.code is CorpusCoverageIssueCode.MISSING_BRANCH_TARGET for issue in report.issues
    )


def test_missing_required_fault_keeps_catalog_denominator_and_fails_closed() -> None:
    _contract_value, _authoring, compiled, manifest = _compiled_and_manifest(
        omit_fault_surface=FaultSurface.DISCLOSURE
    )

    report = build_manifest_coverage_report(compiled, manifest)

    assert not report.complete
    assert (report.fault_coverage.covered, report.fault_coverage.required) == (6, 7)
    assert report.missing_fault_target_ids == (dict(_FAULT_ROWS)[FaultSurface.DISCLOSURE],)
    assert any(
        issue.code is CorpusCoverageIssueCode.MISSING_FAULT_TARGET for issue in report.issues
    )


def test_manifest_pin_membership_and_binding_drift_never_count_as_coverage() -> None:
    _contract_value, _authoring, compiled, manifest = _compiled_and_manifest()

    wrong_pin = replace(
        manifest,
        scenario_set_pin=replace(manifest.scenario_set_pin, digest="f" * 64),
    )
    pin_report = build_manifest_coverage_report(compiled, wrong_pin)
    assert not pin_report.complete
    assert (pin_report.branch_coverage.covered, pin_report.branch_coverage.required) == (0, 22)
    assert (pin_report.fault_coverage.covered, pin_report.fault_coverage.required) == (0, 7)
    assert CorpusCoverageIssueCode.SCENARIO_SET_PIN_MISMATCH in {
        issue.code for issue in pin_report.issues
    }

    foreign_contract = replace(
        manifest,
        contract_pin=replace(manifest.contract_pin, digest="e" * 64),
    )
    foreign_report = build_manifest_coverage_report(compiled, foreign_contract)
    assert not foreign_report.complete
    assert (foreign_report.branch_coverage.covered, foreign_report.branch_coverage.required) == (
        0,
        22,
    )
    assert (foreign_report.fault_coverage.covered, foreign_report.fault_coverage.required) == (0, 7)
    assert CorpusCoverageIssueCode.CONTRACT_PIN_MISMATCH in {
        issue.code for issue in foreign_report.issues
    }

    missing = replace(manifest, scenarios=manifest.scenarios[1:])
    missing_report = build_manifest_coverage_report(compiled, missing)
    assert not missing_report.complete
    assert missing_report.branch_coverage.required == 22
    assert (missing_report.fault_coverage.covered, missing_report.fault_coverage.required) == (6, 7)
    assert CorpusCoverageIssueCode.MISSING_MANIFEST_SCENARIO in {
        issue.code for issue in missing_report.issues
    }

    extra_binding = replace(manifest.scenarios[0], scenario_id="case-extra")
    extra = replace(manifest, scenarios=(*manifest.scenarios, extra_binding))
    extra_report = build_manifest_coverage_report(compiled, extra)
    assert not extra_report.complete
    assert (extra_report.branch_coverage.covered, extra_report.branch_coverage.required) == (22, 22)
    assert (extra_report.fault_coverage.covered, extra_report.fault_coverage.required) == (7, 7)
    assert CorpusCoverageIssueCode.EXTRA_MANIFEST_SCENARIO in {
        issue.code for issue in extra_report.issues
    }

    changed_binding = replace(
        manifest.scenarios[0],
        world_state_digest=_digest("PRIVATE DRIFTED WORLD"),
    )
    drifted = replace(manifest, scenarios=(changed_binding, *manifest.scenarios[1:]))
    drift_report = build_manifest_coverage_report(compiled, drifted)
    assert not drift_report.complete
    assert drift_report.branch_coverage.required == 22
    assert (drift_report.fault_coverage.covered, drift_report.fault_coverage.required) == (6, 7)
    assert CorpusCoverageIssueCode.SCENARIO_BINDING_MISMATCH in {
        issue.code for issue in drift_report.issues
    }
    expected_binding = compiled.scenarios[0].fixture.binding()
    assert scenario_binding_digest(changed_binding) != scenario_binding_digest(expected_binding)


def test_unknown_duplicate_and_contract_drift_are_rejected() -> None:
    _contract_value, authoring = _authoring_corpus()

    with pytest.raises(ValueError, match="duplicate persona"):
        replace(authoring, personas=(*authoring.personas, authoring.personas[0]))

    unknown_fault = replace(
        authoring.scenarios[0].scenario,
        world=replace(
            authoring.scenarios[0].scenario.world,
            fault_ids=("private-unknown-fault",),
        ),
    )
    with pytest.raises(ValueError, match="unknown fault"):
        replace(
            authoring,
            scenarios=(
                replace(authoring.scenarios[0], scenario=unknown_fault),
                *authoring.scenarios[1:],
            ),
        )

    with pytest.raises(ValueError, match="contract identity"):
        replace(
            authoring,
            contract_pin=replace(authoring.contract_pin, digest="f" * 64),
        )


def test_canonical_artifacts_are_stable_sensitive_and_compartmentalized() -> None:
    _contract_value, authoring, compiled, manifest = _compiled_and_manifest()
    reordered_authoring = replace(
        authoring,
        personas=tuple(reversed(authoring.personas)),
        adversarial_intents=tuple(reversed(authoring.adversarial_intents)),
        faults=tuple(reversed(authoring.faults)),
        scenarios=tuple(reversed(authoring.scenarios)),
    )
    reordered = compile_corpus(reordered_authoring, contract=_contract())
    report = build_manifest_coverage_report(compiled, manifest)

    assert canonical_corpus_json(compiled) == canonical_corpus_json(reordered)
    assert corpus_digest(compiled) == corpus_digest(reordered)
    assert manifest_coverage_report_digest(report) == manifest_coverage_report_digest(report)

    changed_personas = (
        replace(authoring.personas[0], content_digest=_digest("CHANGED PERSONA")),
        *authoring.personas[1:],
    )
    changed = compile_corpus(
        replace(authoring, personas=changed_personas),
        contract=_contract(),
    )
    assert corpus_digest(changed) != corpus_digest(compiled)
    assert compiled_corpus_pin(changed) != compiled_corpus_pin(compiled)

    payload = "\n".join(
        (
            canonical_corpus_json(compiled),
            canonical_manifest_coverage_report_json(report),
        )
    ).lower()
    for forbidden in (
        "private candidate message",
        "private-world",
        "private-fault",
        "private.expected.path",
        "private prompt injection payload",
        "private raw response",
        "response_text",
        "vr_precision",
        "vry",
        "recontact",
        "cost",
        "promotion",
        "release_verdict",
    ):
        assert forbidden not in payload


def test_corpus_metadata_never_reaches_candidate_callback() -> None:
    _contract_value, _authoring, compiled, _manifest = _compiled_and_manifest()
    fixture = compiled.scenarios[0].fixture

    assert fixture.scenario.candidate_input.as_dict() == {
        "journey_id": "aircargo.shipment-status",
        "messages": ["PRIVATE CANDIDATE MESSAGE case-01"],
        "scenario_id": "case-01",
    }
    assert not hasattr(fixture.scenario.candidate_input, "persona_id")
    assert not hasattr(fixture.scenario.candidate_input, "adversarial_intent_ids")
    assert not hasattr(fixture.scenario.candidate_input, "fault_coverage_target_ids")
