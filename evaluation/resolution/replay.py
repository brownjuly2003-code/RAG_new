from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation.resolution.scenarios import CompiledScenario

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_SCHEMA_VERSION = "resolution-replay-manifest/v0.1"
_EVIDENCE_CLASS = "synthetic_local"


class ArtifactKind(StrEnum):
    CONTRACT = "contract"
    SCENARIO_COMPILER = "scenario_compiler"
    STATE_GRADER = "state_grader"
    CANDIDATE = "candidate"
    SCENARIO_SET = "scenario_set"
    WORLD = "world"
    POLICY = "policy"
    KNOWLEDGE = "knowledge"
    KNOWLEDGE_INDEX = "knowledge_index"
    ACTION_MANIFEST = "action_manifest"
    CONNECTOR = "connector"
    POSTCONDITION = "postcondition"
    DISCLOSURE = "disclosure"
    MODEL = "model"
    PROVIDER = "provider"
    PROMPT = "prompt"
    RETRIEVER = "retriever"
    CONFIG = "config"


_GLOBAL_KINDS = {
    ArtifactKind.CONTRACT,
    ArtifactKind.SCENARIO_COMPILER,
    ArtifactKind.STATE_GRADER,
    ArtifactKind.CANDIDATE,
    ArtifactKind.SCENARIO_SET,
}
_DEPENDENCY_KINDS = set(ArtifactKind) - _GLOBAL_KINDS - {ArtifactKind.WORLD}


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


def _sorted_unique_text(
    values: tuple[str, ...],
    field: str,
    *,
    required: bool,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be an immutable tuple")
    if required and not values:
        raise ValueError(f"{field} cannot be empty")
    for value in values:
        _require_text(value, field, maximum=1024)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


@dataclass(frozen=True, order=True, slots=True)
class ArtifactKey:
    kind: ArtifactKind
    artifact_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ArtifactKind):
            raise ValueError("artifact kind is unknown")
        _require_id(self.artifact_id, "artifact_id")

    def as_dict(self) -> dict[str, str]:
        return {"artifact_id": self.artifact_id, "kind": self.kind.value}


@dataclass(frozen=True, slots=True)
class ArtifactPin:
    kind: ArtifactKind
    artifact_id: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ArtifactKind):
            raise ValueError("artifact kind is unknown")
        _require_id(self.artifact_id, "artifact_id")
        _require_text(self.version, "artifact version", maximum=256)
        _require_digest(self.digest, "artifact digest")

    @property
    def key(self) -> ArtifactKey:
        return ArtifactKey(self.kind, self.artifact_id)

    def as_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "digest": self.digest,
            "kind": self.kind.value,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class ScenarioReplayBinding:
    scenario_id: str
    candidate_input_digest: str
    world_pin: ArtifactPin
    world_state_digest: str
    fault_ids: tuple[str, ...]
    hidden_expected_digest: str
    coverage_target_ids: tuple[str, ...]
    dependency_keys: tuple[ArtifactKey, ...]

    def __post_init__(self) -> None:
        _require_id(self.scenario_id, "scenario_id")
        _require_digest(self.candidate_input_digest, "candidate input digest")
        if (
            not isinstance(self.world_pin, ArtifactPin)
            or self.world_pin.kind is not ArtifactKind.WORLD
        ):
            raise ValueError("scenario world_pin must have kind 'world'")
        _require_digest(self.world_state_digest, "world state digest")
        object.__setattr__(
            self,
            "fault_ids",
            _sorted_unique_text(self.fault_ids, "scenario fault_ids", required=False),
        )
        _require_digest(self.hidden_expected_digest, "hidden expected digest")
        object.__setattr__(
            self,
            "coverage_target_ids",
            _sorted_unique_text(
                self.coverage_target_ids,
                "scenario coverage_target_ids",
                required=True,
            ),
        )
        if not isinstance(self.dependency_keys, tuple) or not self.dependency_keys:
            raise ValueError("scenario dependency_keys must be a non-empty immutable tuple")
        for key in self.dependency_keys:
            if not isinstance(key, ArtifactKey) or key.kind not in _DEPENDENCY_KINDS:
                raise ValueError("scenario dependency key has an unsupported kind")
        if len(self.dependency_keys) != len(set(self.dependency_keys)):
            raise ValueError("scenario dependency_keys must be unique")
        object.__setattr__(self, "dependency_keys", tuple(sorted(self.dependency_keys)))

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_input_digest": self.candidate_input_digest,
            "coverage_target_ids": list(self.coverage_target_ids),
            "dependency_keys": [key.as_dict() for key in self.dependency_keys],
            "fault_ids_digest": _payload_digest(list(self.fault_ids)),
            "hidden_expected_digest": self.hidden_expected_digest,
            "scenario_id": self.scenario_id,
            "world_pin": self.world_pin.as_dict(),
            "world_state_digest": self.world_state_digest,
        }


@dataclass(frozen=True, slots=True)
class ReplayManifest:
    code_revision: str
    contract_pin: ArtifactPin
    scenario_compiler_pin: ArtifactPin
    state_grader_pin: ArtifactPin
    candidate_pin: ArtifactPin
    scenario_set_pin: ArtifactPin
    dependencies: tuple[ArtifactPin, ...]
    scenarios: tuple[ScenarioReplayBinding, ...]
    schema_version: str = _SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")
        if (
            not isinstance(self.code_revision, str)
            or _GIT_SHA1.fullmatch(self.code_revision) is None
        ):
            raise ValueError("code_revision must be an exact lowercase 40-character Git SHA")

        global_pins = (
            (self.contract_pin, ArtifactKind.CONTRACT, "contract_pin"),
            (
                self.scenario_compiler_pin,
                ArtifactKind.SCENARIO_COMPILER,
                "scenario_compiler_pin",
            ),
            (self.state_grader_pin, ArtifactKind.STATE_GRADER, "state_grader_pin"),
            (self.candidate_pin, ArtifactKind.CANDIDATE, "candidate_pin"),
            (self.scenario_set_pin, ArtifactKind.SCENARIO_SET, "scenario_set_pin"),
        )
        for pin, kind, field in global_pins:
            if not isinstance(pin, ArtifactPin) or pin.kind is not kind:
                raise ValueError(f"{field} must have kind {kind.value!r}")

        if not isinstance(self.dependencies, tuple) or not self.dependencies:
            raise ValueError("manifest dependencies must be a non-empty immutable tuple")
        dependency_by_key: dict[ArtifactKey, ArtifactPin] = {}
        for pin in self.dependencies:
            if not isinstance(pin, ArtifactPin) or pin.kind not in _DEPENDENCY_KINDS:
                raise ValueError("manifest dependency pin has an unsupported kind")
            if pin.key in dependency_by_key:
                raise ValueError("manifest has a duplicate dependency pin key")
            dependency_by_key[pin.key] = pin
        object.__setattr__(
            self,
            "dependencies",
            tuple(sorted(dependency_by_key.values(), key=lambda pin: pin.key)),
        )

        if not isinstance(self.scenarios, tuple) or not self.scenarios:
            raise ValueError("manifest scenarios must be a non-empty immutable tuple")
        scenario_by_id: dict[str, ScenarioReplayBinding] = {}
        referenced_keys: set[ArtifactKey] = set()
        for scenario in self.scenarios:
            if not isinstance(scenario, ScenarioReplayBinding):
                raise ValueError("manifest scenarios must be ScenarioReplayBinding values")
            if scenario.scenario_id in scenario_by_id:
                raise ValueError("manifest has a duplicate scenario_id")
            scenario_by_id[scenario.scenario_id] = scenario
            referenced_keys.update(scenario.dependency_keys)

        missing = referenced_keys - dependency_by_key.keys()
        if missing:
            raise ValueError("manifest scenario references a missing dependency pin")
        orphaned = dependency_by_key.keys() - referenced_keys
        if orphaned:
            raise ValueError("manifest contains an orphan dependency pin")
        object.__setattr__(
            self,
            "scenarios",
            tuple(sorted(scenario_by_id.values(), key=lambda scenario: scenario.scenario_id)),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_pin": self.candidate_pin.as_dict(),
            "code_revision": self.code_revision,
            "contract_pin": self.contract_pin.as_dict(),
            "dependencies": [pin.as_dict() for pin in self.dependencies],
            "evidence_class": self.evidence_class,
            "scenario_compiler_pin": self.scenario_compiler_pin.as_dict(),
            "scenario_set_pin": self.scenario_set_pin.as_dict(),
            "scenarios": [scenario.as_dict() for scenario in self.scenarios],
            "schema_version": self.schema_version,
            "state_grader_pin": self.state_grader_pin.as_dict(),
        }


class SelectionMode(StrEnum):
    NO_CHANGE = "no_change"
    TARGETED = "targeted"
    FULL = "full"
    FULL_FAIL_CLOSED = "full_fail_closed"


class ImpactReason(StrEnum):
    CODE_REVISION_CHANGED = "code_revision_changed"
    CONTRACT_CHANGED = "contract_changed"
    SCENARIO_COMPILER_CHANGED = "scenario_compiler_changed"
    STATE_GRADER_CHANGED = "state_grader_changed"
    CANDIDATE_CHANGED = "candidate_changed"
    SCENARIO_SET_CHANGED = "scenario_set_changed"
    CANDIDATE_INPUT_CHANGED = "candidate_input_changed"
    WORLD_CHANGED = "world_changed"
    FAULTS_CHANGED = "faults_changed"
    HIDDEN_EXPECTED_CHANGED = "hidden_expected_changed"
    COVERAGE_CHANGED = "coverage_changed"
    DEPENDENCY_PIN_CHANGED = "dependency_pin_changed"
    DEPENDENCY_GRAPH_CHANGED = "dependency_graph_changed"
    SCENARIO_MEMBERSHIP_CHANGED = "scenario_membership_changed"
    UNEXPLAINED_MANIFEST_CHANGE = "unexplained_manifest_change"


@dataclass(frozen=True, slots=True)
class ImpactSelectionReport:
    baseline_manifest_digest: str
    candidate_manifest_digest: str
    mode: SelectionMode
    selected_scenario_ids: tuple[str, ...]
    removed_scenario_ids: tuple[str, ...]
    changed_dependency_keys: tuple[ArtifactKey, ...]
    reason_codes: tuple[ImpactReason, ...]
    complete: bool

    def __post_init__(self) -> None:
        _require_digest(self.baseline_manifest_digest, "baseline manifest digest")
        _require_digest(self.candidate_manifest_digest, "candidate manifest digest")
        if not isinstance(self.mode, SelectionMode):
            raise ValueError("impact selection mode is unknown")
        object.__setattr__(
            self,
            "selected_scenario_ids",
            _sorted_unique_text(
                self.selected_scenario_ids,
                "selected scenario IDs",
                required=False,
            ),
        )
        object.__setattr__(
            self,
            "removed_scenario_ids",
            _sorted_unique_text(
                self.removed_scenario_ids,
                "removed scenario IDs",
                required=False,
            ),
        )
        if len(self.changed_dependency_keys) != len(set(self.changed_dependency_keys)):
            raise ValueError("changed dependency keys must be unique")
        if any(not isinstance(key, ArtifactKey) for key in self.changed_dependency_keys):
            raise ValueError("changed dependency keys contain an invalid value")
        object.__setattr__(
            self,
            "changed_dependency_keys",
            tuple(sorted(self.changed_dependency_keys)),
        )
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("impact reason codes must be unique")
        if any(not isinstance(reason, ImpactReason) for reason in self.reason_codes):
            raise ValueError("impact reason code is unknown")
        object.__setattr__(
            self,
            "reason_codes",
            tuple(sorted(self.reason_codes, key=lambda reason: reason.value)),
        )
        if self.mode is SelectionMode.NO_CHANGE:
            if (
                self.baseline_manifest_digest != self.candidate_manifest_digest
                or self.selected_scenario_ids
                or self.removed_scenario_ids
                or self.changed_dependency_keys
                or self.reason_codes
                or not self.complete
            ):
                raise ValueError("no-change impact report is internally inconsistent")
        elif not self.selected_scenario_ids:
            raise ValueError("changed manifests require a non-empty scenario selection")
        if self.mode is SelectionMode.FULL_FAIL_CLOSED and self.complete:
            raise ValueError("fail-closed impact selection cannot be complete")
        if self.mode is not SelectionMode.FULL_FAIL_CLOSED and not self.complete:
            raise ValueError("only fail-closed impact selection can be incomplete")

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline_manifest_digest": self.baseline_manifest_digest,
            "candidate_manifest_digest": self.candidate_manifest_digest,
            "changed_dependency_keys": [key.as_dict() for key in self.changed_dependency_keys],
            "complete": self.complete,
            "mode": self.mode.value,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "removed_scenario_ids": list(self.removed_scenario_ids),
            "selected_scenario_ids": list(self.selected_scenario_ids),
        }


def build_replay_manifest(
    *,
    code_revision: str,
    contract_pin: ArtifactPin,
    scenario_compiler_pin: ArtifactPin,
    state_grader_pin: ArtifactPin,
    candidate_pin: ArtifactPin,
    scenario_set_pin: ArtifactPin,
    dependencies: tuple[ArtifactPin, ...],
    scenarios: tuple[ScenarioReplayBinding, ...],
) -> ReplayManifest:
    return ReplayManifest(
        code_revision=code_revision,
        contract_pin=contract_pin,
        scenario_compiler_pin=scenario_compiler_pin,
        state_grader_pin=state_grader_pin,
        candidate_pin=candidate_pin,
        scenario_set_pin=scenario_set_pin,
        dependencies=dependencies,
        scenarios=scenarios,
    )


def _hidden_expected_payload(scenario: CompiledScenario) -> dict[str, object]:
    expected = scenario.hidden_expected
    return {
        "branch_path": [
            {"event": branch.event.value, "step_id": branch.step_id}
            for branch in expected.branch_path
        ],
        "canonical_state": [list(item) for item in expected.canonical_state],
        "contract_digest": expected.contract_digest,
        "contract_id": expected.contract_id,
        "contract_version": expected.contract_version,
        "reason_codes": list(expected.reason_codes),
        "terminal_outcome": expected.terminal_outcome.value,
    }


def bind_scenario(
    scenario: CompiledScenario,
    *,
    world_pin: ArtifactPin,
    coverage_target_ids: tuple[str, ...],
    dependency_keys: tuple[ArtifactKey, ...],
) -> ScenarioReplayBinding:
    if not isinstance(scenario, CompiledScenario):
        raise ValueError("scenario must be a CompiledScenario")
    return ScenarioReplayBinding(
        scenario_id=scenario.candidate_input.scenario_id,
        candidate_input_digest=_payload_digest(scenario.candidate_input.as_dict()),
        world_pin=world_pin,
        world_state_digest=_payload_digest({"world_state_id": scenario.world.world_state_id}),
        fault_ids=scenario.world.fault_ids,
        hidden_expected_digest=_payload_digest(_hidden_expected_payload(scenario)),
        coverage_target_ids=coverage_target_ids,
        dependency_keys=dependency_keys,
    )


def canonical_replay_manifest_json(manifest: ReplayManifest) -> str:
    if not isinstance(manifest, ReplayManifest):
        raise ValueError("manifest must be a ReplayManifest")
    return _canonical_json(manifest.as_dict())


def replay_manifest_digest(manifest: ReplayManifest) -> str:
    return hashlib.sha256(canonical_replay_manifest_json(manifest).encode("utf-8")).hexdigest()


def _dependency_users(manifest: ReplayManifest) -> dict[ArtifactKey, set[str]]:
    users: dict[ArtifactKey, set[str]] = {pin.key: set() for pin in manifest.dependencies}
    for scenario in manifest.scenarios:
        for key in scenario.dependency_keys:
            users[key].add(scenario.scenario_id)
    return users


def select_impacted_scenarios(
    baseline: ReplayManifest,
    candidate: ReplayManifest,
) -> ImpactSelectionReport:
    if not isinstance(baseline, ReplayManifest) or not isinstance(candidate, ReplayManifest):
        raise ValueError("impact selection requires two ReplayManifest values")
    baseline_digest = replay_manifest_digest(baseline)
    candidate_digest = replay_manifest_digest(candidate)
    if baseline_digest == candidate_digest:
        return ImpactSelectionReport(
            baseline_manifest_digest=baseline_digest,
            candidate_manifest_digest=candidate_digest,
            mode=SelectionMode.NO_CHANGE,
            selected_scenario_ids=(),
            removed_scenario_ids=(),
            changed_dependency_keys=(),
            reason_codes=(),
            complete=True,
        )

    baseline_scenarios = {scenario.scenario_id: scenario for scenario in baseline.scenarios}
    candidate_scenarios = {scenario.scenario_id: scenario for scenario in candidate.scenarios}
    candidate_ids = set(candidate_scenarios)
    removed_ids = set(baseline_scenarios) - candidate_ids
    selected: set[str] = set()
    reasons: set[ImpactReason] = set()
    changed_dependency_keys: set[ArtifactKey] = set()
    full = False
    fail_closed = False

    global_comparisons = (
        (
            baseline.code_revision,
            candidate.code_revision,
            ImpactReason.CODE_REVISION_CHANGED,
        ),
        (baseline.contract_pin, candidate.contract_pin, ImpactReason.CONTRACT_CHANGED),
        (
            baseline.scenario_compiler_pin,
            candidate.scenario_compiler_pin,
            ImpactReason.SCENARIO_COMPILER_CHANGED,
        ),
        (
            baseline.state_grader_pin,
            candidate.state_grader_pin,
            ImpactReason.STATE_GRADER_CHANGED,
        ),
        (baseline.candidate_pin, candidate.candidate_pin, ImpactReason.CANDIDATE_CHANGED),
        (
            baseline.scenario_set_pin,
            candidate.scenario_set_pin,
            ImpactReason.SCENARIO_SET_CHANGED,
        ),
    )
    for global_before, global_after, reason in global_comparisons:
        if global_before != global_after:
            full = True
            reasons.add(reason)

    baseline_dependencies = {pin.key: pin for pin in baseline.dependencies}
    candidate_dependencies = {pin.key: pin for pin in candidate.dependencies}
    baseline_keys = set(baseline_dependencies)
    candidate_keys = set(candidate_dependencies)
    changed_dependency_keys.update(baseline_keys ^ candidate_keys)
    if baseline_keys != candidate_keys:
        fail_closed = True
        reasons.add(ImpactReason.DEPENDENCY_GRAPH_CHANGED)
    shared_keys = baseline_keys & candidate_keys
    changed_pins = {
        key for key in shared_keys if baseline_dependencies[key] != candidate_dependencies[key]
    }
    if changed_pins:
        reasons.add(ImpactReason.DEPENDENCY_PIN_CHANGED)
        changed_dependency_keys.update(changed_pins)
        baseline_users = _dependency_users(baseline)
        candidate_users = _dependency_users(candidate)
        for key in changed_pins:
            selected.update(baseline_users[key] & candidate_ids)
            selected.update(candidate_users[key])

    if set(baseline_scenarios) != candidate_ids:
        fail_closed = True
        reasons.add(ImpactReason.SCENARIO_MEMBERSHIP_CHANGED)

    for scenario_id in set(baseline_scenarios) & candidate_ids:
        scenario_before = baseline_scenarios[scenario_id]
        scenario_after = candidate_scenarios[scenario_id]
        if scenario_before.candidate_input_digest != scenario_after.candidate_input_digest:
            selected.add(scenario_id)
            reasons.add(ImpactReason.CANDIDATE_INPUT_CHANGED)
        if (
            scenario_before.world_pin != scenario_after.world_pin
            or scenario_before.world_state_digest != scenario_after.world_state_digest
        ):
            selected.add(scenario_id)
            reasons.add(ImpactReason.WORLD_CHANGED)
        if scenario_before.fault_ids != scenario_after.fault_ids:
            selected.add(scenario_id)
            reasons.add(ImpactReason.FAULTS_CHANGED)
        if scenario_before.hidden_expected_digest != scenario_after.hidden_expected_digest:
            selected.add(scenario_id)
            reasons.add(ImpactReason.HIDDEN_EXPECTED_CHANGED)
        if scenario_before.coverage_target_ids != scenario_after.coverage_target_ids:
            selected.add(scenario_id)
            reasons.add(ImpactReason.COVERAGE_CHANGED)
        if scenario_before.dependency_keys != scenario_after.dependency_keys:
            fail_closed = True
            reasons.add(ImpactReason.DEPENDENCY_GRAPH_CHANGED)

    if fail_closed:
        selected = candidate_ids
        mode = SelectionMode.FULL_FAIL_CLOSED
        complete = False
    elif full:
        selected = candidate_ids
        mode = SelectionMode.FULL
        complete = True
    elif selected:
        mode = SelectionMode.TARGETED
        complete = True
    else:
        selected = candidate_ids
        reasons.add(ImpactReason.UNEXPLAINED_MANIFEST_CHANGE)
        mode = SelectionMode.FULL_FAIL_CLOSED
        complete = False

    return ImpactSelectionReport(
        baseline_manifest_digest=baseline_digest,
        candidate_manifest_digest=candidate_digest,
        mode=mode,
        selected_scenario_ids=tuple(selected),
        removed_scenario_ids=tuple(removed_ids),
        changed_dependency_keys=tuple(changed_dependency_keys),
        reason_codes=tuple(reasons),
        complete=complete,
    )


def canonical_impact_report_json(report: ImpactSelectionReport) -> str:
    if not isinstance(report, ImpactSelectionReport):
        raise ValueError("report must be an ImpactSelectionReport")
    return _canonical_json(report.as_dict())


def impact_report_digest(report: ImpactSelectionReport) -> str:
    return hashlib.sha256(canonical_impact_report_json(report).encode("utf-8")).hexdigest()


__all__ = [
    "ArtifactKey",
    "ArtifactKind",
    "ArtifactPin",
    "ImpactReason",
    "ImpactSelectionReport",
    "ReplayManifest",
    "ScenarioReplayBinding",
    "SelectionMode",
    "bind_scenario",
    "build_replay_manifest",
    "canonical_impact_report_json",
    "canonical_replay_manifest_json",
    "impact_report_digest",
    "replay_manifest_digest",
    "select_impacted_scenarios",
]
