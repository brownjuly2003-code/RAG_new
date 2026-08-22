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
    HiddenExpectedState,
    ImpactReason,
    ReplayManifest,
    ScenarioReplayBinding,
    ScenarioWorld,
    SelectionMode,
    bind_scenario,
    build_replay_manifest,
    canonical_impact_report_json,
    canonical_replay_manifest_json,
    impact_report_digest,
    replay_manifest_digest,
    select_impacted_scenarios,
)
from resolution.contracts import TerminalOutcome, TransitionEvent


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


def _dependency_pins() -> tuple[ArtifactPin, ...]:
    pins = (
        _pin(ArtifactKind.POLICY, "policy-a", digest_char="1"),
        _pin(ArtifactKind.POLICY, "policy-b", digest_char="2"),
        _pin(ArtifactKind.KNOWLEDGE, "knowledge-a", digest_char="3"),
        _pin(ArtifactKind.KNOWLEDGE, "knowledge-b", digest_char="4"),
        _pin(ArtifactKind.ACTION_MANIFEST, "action-a", digest_char="5"),
        _pin(ArtifactKind.ACTION_MANIFEST, "action-b", digest_char="6"),
        _pin(ArtifactKind.MODEL, "model-a", digest_char="7"),
        _pin(ArtifactKind.MODEL, "model-b", digest_char="8"),
        _pin(ArtifactKind.KNOWLEDGE_INDEX, "shipment-index", digest_char="9"),
        _pin(ArtifactKind.CONNECTOR, "shipment-connector", digest_char="a"),
        _pin(ArtifactKind.POSTCONDITION, "shipment-checker", digest_char="b"),
        _pin(ArtifactKind.DISCLOSURE, "ai-disclosure", digest_char="c"),
        _pin(ArtifactKind.PROVIDER, "local-provider", digest_char="d"),
        _pin(ArtifactKind.PROMPT, "shipment-prompt", digest_char="e"),
        _pin(ArtifactKind.RETRIEVER, "shipment-retriever", digest_char="f"),
        _pin(ArtifactKind.CONFIG, "resolution-config", digest_char="0"),
    )
    return tuple(sorted(pins, key=lambda pin: pin.key))


def _scenario(
    scenario_id: str,
    dependencies: tuple[ArtifactPin, ...],
    *,
    candidate_digest: str = "a" * 64,
    hidden_digest: str = "b" * 64,
) -> ScenarioReplayBinding:
    suffix = scenario_id[-1]
    own_keys = tuple(
        pin.key
        for pin in dependencies
        if pin.artifact_id.endswith(f"-{suffix}")
        or pin.kind
        in {
            ArtifactKind.KNOWLEDGE_INDEX,
            ArtifactKind.CONNECTOR,
            ArtifactKind.POSTCONDITION,
            ArtifactKind.DISCLOSURE,
            ArtifactKind.PROVIDER,
            ArtifactKind.PROMPT,
            ArtifactKind.RETRIEVER,
            ArtifactKind.CONFIG,
        }
    )
    return ScenarioReplayBinding(
        scenario_id=scenario_id,
        candidate_input_digest=candidate_digest,
        world_pin=_pin(
            ArtifactKind.WORLD,
            f"world-{suffix}",
            digest_char="c" if suffix == "a" else "d",
        ),
        world_state_digest=("e" if suffix == "a" else "f") * 64,
        fault_ids=(f"fault-{suffix}-2", f"fault-{suffix}-1"),
        hidden_expected_digest=hidden_digest,
        coverage_target_ids=(f"target-{suffix}-2", f"target-{suffix}-1"),
        dependency_keys=tuple(reversed(own_keys)),
    )


def _manifest(
    *,
    dependencies: tuple[ArtifactPin, ...] | None = None,
    scenarios: tuple[ScenarioReplayBinding, ...] | None = None,
    code_revision: str = "1" * 40,
) -> ReplayManifest:
    dependency_pins = dependencies or _dependency_pins()
    scenario_bindings = scenarios or (
        _scenario("scenario-a", dependency_pins),
        _scenario(
            "scenario-b",
            dependency_pins,
            candidate_digest="e" * 64,
            hidden_digest="f" * 64,
        ),
    )
    return build_replay_manifest(
        code_revision=code_revision,
        contract_pin=_pin(ArtifactKind.CONTRACT, "aircargo.shipment-status"),
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
            version="2026.08.22",
            digest_char="5",
        ),
        dependencies=dependency_pins,
        scenarios=scenario_bindings,
    )


def _compiled_scenario(expected_value: str) -> CompiledScenario:
    return CompiledScenario(
        candidate_input=CandidateScenarioInput(
            scenario_id="scenario-a",
            journey_id="aircargo.shipment-status",
            messages=("PRIVATE SHIPMENT SHP-100",),
        ),
        world=ScenarioWorld(
            world_state_id="PRIVATE-WORLD-PAYLOAD",
            fault_ids=("provider-timeout",),
        ),
        hidden_expected=HiddenExpectedState(
            contract_id="aircargo.shipment-status",
            contract_version="0.1.0",
            contract_digest="1" * 64,
            branch_path=(BranchRef("read-shipment", TransitionEvent.SUCCESS),),
            terminal_outcome=TerminalOutcome.VERIFIED,
            reason_codes=(),
            canonical_state=(("secret.expected.path", expected_value),),
        ),
    )


def test_manifest_canonicalization_is_order_independent_and_identity_sensitive() -> None:
    manifest = _manifest()
    reordered_scenarios = tuple(
        replace(
            scenario,
            fault_ids=tuple(reversed(scenario.fault_ids)),
            coverage_target_ids=tuple(reversed(scenario.coverage_target_ids)),
            dependency_keys=tuple(reversed(scenario.dependency_keys)),
        )
        for scenario in reversed(manifest.scenarios)
    )
    reordered = replace(
        manifest,
        dependencies=tuple(reversed(manifest.dependencies)),
        scenarios=reordered_scenarios,
    )

    assert canonical_replay_manifest_json(manifest) == canonical_replay_manifest_json(reordered)
    assert replay_manifest_digest(manifest) == replay_manifest_digest(reordered)

    changed_policy = tuple(
        replace(pin, digest="6" * 64)
        if pin.key == ArtifactKey(ArtifactKind.POLICY, "policy-a")
        else pin
        for pin in manifest.dependencies
    )
    assert replay_manifest_digest(replace(manifest, dependencies=changed_policy)) != (
        replay_manifest_digest(manifest)
    )


def test_bind_scenario_compartmentalizes_candidate_world_and_hidden_payloads() -> None:
    dependencies = _dependency_pins()
    binding = bind_scenario(
        _compiled_scenario("PRIVATE-EXPECTED-VALUE"),
        world_pin=_pin(ArtifactKind.WORLD, "shipment-world", digest_char="7"),
        coverage_target_ids=("shipment-target",),
        dependency_keys=tuple(pin.key for pin in dependencies),
    )
    manifest = _manifest(dependencies=dependencies, scenarios=(binding,))
    serialized = canonical_replay_manifest_json(manifest)

    assert binding.scenario_id == "scenario-a"
    assert "PRIVATE SHIPMENT SHP-100" not in serialized
    assert "PRIVATE-WORLD-PAYLOAD" not in serialized
    assert "provider-timeout" not in serialized
    assert "PRIVATE-EXPECTED-VALUE" not in serialized
    assert "secret.expected.path" not in serialized
    assert "candidate_input_digest" in serialized
    assert "world_state_digest" in serialized
    assert "fault_ids_digest" in serialized
    assert "hidden_expected_digest" in serialized
    assert "promotion" not in serialized.lower()


def test_bind_scenario_pins_world_reference_without_exposing_it() -> None:
    scenario = _compiled_scenario("expected")
    changed_world = replace(
        scenario,
        world=replace(scenario.world, world_state_id="PRIVATE-WORLD-PAYLOAD-CHANGED"),
    )
    world_pin = _pin(ArtifactKind.WORLD, "shipment-world", digest_char="7")
    dependencies = _dependency_pins()
    binding_kwargs = {
        "world_pin": world_pin,
        "coverage_target_ids": ("shipment-target",),
        "dependency_keys": tuple(pin.key for pin in dependencies),
    }

    baseline_binding = bind_scenario(scenario, **binding_kwargs)
    changed_binding = bind_scenario(changed_world, **binding_kwargs)

    assert baseline_binding.world_state_digest != changed_binding.world_state_digest
    assert baseline_binding.world_pin == changed_binding.world_pin
    baseline = _manifest(dependencies=dependencies, scenarios=(baseline_binding,))
    candidate = _manifest(dependencies=dependencies, scenarios=(changed_binding,))
    report = select_impacted_scenarios(baseline, candidate)
    assert replay_manifest_digest(baseline) != replay_manifest_digest(candidate)
    assert report.mode is SelectionMode.TARGETED
    assert report.selected_scenario_ids == ("scenario-a",)
    assert report.reason_codes == (ImpactReason.WORLD_CHANGED,)


@pytest.mark.parametrize(
    ("kind", "artifact_id"),
    (
        (ArtifactKind.POLICY, "policy-a"),
        (ArtifactKind.KNOWLEDGE, "knowledge-a"),
        (ArtifactKind.ACTION_MANIFEST, "action-a"),
        (ArtifactKind.MODEL, "model-a"),
    ),
)
def test_known_dependency_change_selects_only_bound_scenario(
    kind: ArtifactKind,
    artifact_id: str,
) -> None:
    baseline = _manifest()
    changed_key = ArtifactKey(kind, artifact_id)
    changed_dependencies = tuple(
        replace(pin, digest="0" * 64) if pin.key == changed_key else pin
        for pin in baseline.dependencies
    )
    candidate = replace(baseline, dependencies=changed_dependencies)

    report = select_impacted_scenarios(baseline, candidate)

    assert report.mode is SelectionMode.TARGETED
    assert report.selected_scenario_ids == ("scenario-a",)
    assert report.changed_dependency_keys == (changed_key,)
    assert report.complete
    assert ImpactReason.DEPENDENCY_PIN_CHANGED in report.reason_codes


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("code_revision", "2" * 40),
        (
            "contract_pin",
            _pin(
                ArtifactKind.CONTRACT,
                "aircargo.shipment-status",
                version="0.2.0",
            ),
        ),
        (
            "scenario_compiler_pin",
            _pin(
                ArtifactKind.SCENARIO_COMPILER,
                "resolution-scenario-compiler",
                version="2.0.0",
            ),
        ),
        (
            "state_grader_pin",
            _pin(
                ArtifactKind.STATE_GRADER,
                "resolution-state-grader",
                version="2.0.0",
            ),
        ),
        (
            "candidate_pin",
            _pin(
                ArtifactKind.CANDIDATE,
                "shipment-candidate",
                version="2.0.0",
            ),
        ),
        (
            "scenario_set_pin",
            _pin(
                ArtifactKind.SCENARIO_SET,
                "shipment-resolution-cases",
                version="2026.08.23",
                digest_char="6",
            ),
        ),
    ),
)
def test_global_identity_change_selects_every_scenario(
    field: str,
    value: object,
) -> None:
    baseline = _manifest()
    candidate = replace(baseline, **{field: value})

    report = select_impacted_scenarios(baseline, candidate)

    assert report.mode is SelectionMode.FULL
    assert report.selected_scenario_ids == ("scenario-a", "scenario-b")
    assert report.complete


def test_hidden_expected_digest_change_is_targeted_without_revealing_oracle() -> None:
    dependencies = _dependency_pins()
    baseline_binding = bind_scenario(
        _compiled_scenario("expected-one"),
        world_pin=_pin(ArtifactKind.WORLD, "shipment-world"),
        coverage_target_ids=("shipment-target",),
        dependency_keys=tuple(pin.key for pin in dependencies),
    )
    candidate_binding = bind_scenario(
        _compiled_scenario("expected-two"),
        world_pin=_pin(ArtifactKind.WORLD, "shipment-world"),
        coverage_target_ids=("shipment-target",),
        dependency_keys=tuple(pin.key for pin in dependencies),
    )
    baseline = _manifest(dependencies=dependencies, scenarios=(baseline_binding,))
    candidate = _manifest(dependencies=dependencies, scenarios=(candidate_binding,))

    report = select_impacted_scenarios(baseline, candidate)

    assert report.mode is SelectionMode.TARGETED
    assert report.selected_scenario_ids == ("scenario-a",)
    assert report.reason_codes == (ImpactReason.HIDDEN_EXPECTED_CHANGED,)
    assert "expected-one" not in canonical_impact_report_json(report)
    assert "expected-two" not in canonical_impact_report_json(report)


def test_dependency_graph_change_selects_all_fail_closed() -> None:
    baseline = _manifest()
    old_key = ArtifactKey(ArtifactKind.POLICY, "policy-a")
    new_pin = _pin(ArtifactKind.POLICY, "policy-a-next", digest_char="0")
    candidate_dependencies = tuple(
        new_pin if pin.key == old_key else pin for pin in baseline.dependencies
    )
    candidate_scenarios = tuple(
        replace(
            scenario,
            dependency_keys=tuple(
                new_pin.key if key == old_key else key for key in scenario.dependency_keys
            ),
        )
        for scenario in baseline.scenarios
    )
    candidate = replace(
        baseline,
        dependencies=candidate_dependencies,
        scenarios=candidate_scenarios,
    )

    report = select_impacted_scenarios(baseline, candidate)

    assert report.mode is SelectionMode.FULL_FAIL_CLOSED
    assert report.selected_scenario_ids == ("scenario-a", "scenario-b")
    assert not report.complete
    assert ImpactReason.DEPENDENCY_GRAPH_CHANGED in report.reason_codes


def test_removed_scenario_selects_all_remaining_fail_closed() -> None:
    baseline = _manifest()
    remaining = tuple(
        scenario for scenario in baseline.scenarios if scenario.scenario_id == "scenario-b"
    )
    referenced = set(remaining[0].dependency_keys)
    remaining_dependencies = tuple(pin for pin in baseline.dependencies if pin.key in referenced)
    candidate = replace(
        baseline,
        dependencies=remaining_dependencies,
        scenarios=remaining,
    )

    report = select_impacted_scenarios(baseline, candidate)

    assert report.mode is SelectionMode.FULL_FAIL_CLOSED
    assert report.selected_scenario_ids == ("scenario-b",)
    assert report.removed_scenario_ids == ("scenario-a",)
    assert not report.complete
    assert ImpactReason.SCENARIO_MEMBERSHIP_CHANGED in report.reason_codes


def test_same_manifest_requires_no_replay() -> None:
    manifest = _manifest()

    report = select_impacted_scenarios(manifest, manifest)

    assert report.mode is SelectionMode.NO_CHANGE
    assert report.selected_scenario_ids == ()
    assert report.changed_dependency_keys == ()
    assert report.reason_codes == ()
    assert report.complete


def test_impact_report_is_canonical_and_has_no_release_or_business_verdict() -> None:
    baseline = _manifest()
    report = select_impacted_scenarios(
        baseline,
        replace(baseline, code_revision="2" * 40),
    )

    assert impact_report_digest(report) == impact_report_digest(report)
    payload = canonical_impact_report_json(report).lower()
    for forbidden in (
        "promotion",
        "release_verdict",
        "replay_outcome",
        "passed",
        "vr_precision",
        "vry",
        "recontact",
        "cost",
    ):
        assert forbidden not in payload


def test_manifest_rejects_invalid_or_ambiguous_identity_graph() -> None:
    with pytest.raises(ValueError, match="kind"):
        ArtifactPin(  # type: ignore[arg-type]
            kind="unknown",
            artifact_id="unknown",
            version="1.0.0",
            digest="a" * 64,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        _pin(ArtifactKind.POLICY, "policy-a", digest_char="z")

    manifest = _manifest()
    duplicate = replace(manifest.dependencies[0], digest="0" * 64)
    with pytest.raises(ValueError, match="duplicate"):
        replace(manifest, dependencies=(*manifest.dependencies, duplicate))

    dangling = replace(
        manifest.scenarios[0],
        dependency_keys=(
            *manifest.scenarios[0].dependency_keys,
            ArtifactKey(ArtifactKind.POLICY, "missing"),
        ),
    )
    with pytest.raises(ValueError, match="missing dependency"):
        replace(manifest, scenarios=(dangling, manifest.scenarios[1]))

    orphan = _pin(ArtifactKind.POLICY, "orphan", digest_char="0")
    with pytest.raises(ValueError, match="orphan"):
        replace(manifest, dependencies=(*manifest.dependencies, orphan))


def test_manifest_rejects_invalid_revision_and_non_world_pin() -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="40-character"):
        replace(manifest, code_revision="abcdef")
    with pytest.raises(ValueError, match="world_pin"):
        replace(
            manifest.scenarios[0],
            world_pin=_pin(ArtifactKind.CONFIG, "not-a-world"),
        )
