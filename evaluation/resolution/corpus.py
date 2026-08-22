from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from evaluation.resolution.replay import (
    ArtifactKey,
    ArtifactKind,
    ArtifactPin,
    ReplayManifest,
    replay_manifest_digest,
    scenario_binding_digest,
)
from evaluation.resolution.scenarios import (
    CompiledScenario,
    compile_branch_targets,
    compile_scenario,
)
from evaluation.resolution.trials import ReplayScenarioFixture
from resolution.contracts import ResolutionContract, contract_digest

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/@-]*[A-Za-z0-9])?$")
_FAULT_COVERAGE_TARGET = re.compile(r"^fcov-[0-9a-f]{32}$")
_CORPUS_SCHEMA_VERSION = "resolution-scenario-corpus/v0.1"
_REPORT_SCHEMA_VERSION = "resolution-manifest-coverage/v0.1"
_EVIDENCE_CLASS = "synthetic_local"


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


def _sorted_unique_ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be an immutable tuple")
    for value in values:
        _require_id(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


def _sorted_unique_text(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be an immutable tuple")
    for value in values:
        _require_text(value, field, maximum=1024)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


@dataclass(frozen=True, order=True, slots=True)
class PersonaDefinition:
    persona_id: str
    version: str
    content_digest: str

    def __post_init__(self) -> None:
        _require_id(self.persona_id, "persona_id")
        _require_text(self.version, "persona version", maximum=256)
        _require_digest(self.content_digest, "persona content_digest")

    def as_dict(self) -> dict[str, str]:
        return {
            "content_digest": self.content_digest,
            "persona_id": self.persona_id,
            "version": self.version,
        }


@dataclass(frozen=True, order=True, slots=True)
class AdversarialIntentDefinition:
    intent_id: str
    version: str
    content_digest: str

    def __post_init__(self) -> None:
        _require_id(self.intent_id, "adversarial intent_id")
        _require_text(self.version, "adversarial intent version", maximum=256)
        _require_digest(self.content_digest, "adversarial intent content_digest")

    def as_dict(self) -> dict[str, str]:
        return {
            "content_digest": self.content_digest,
            "intent_id": self.intent_id,
            "version": self.version,
        }


class FaultSurface(StrEnum):
    CONTRACT = "contract"
    POLICY = "policy"
    RETRIEVER = "retriever"
    CONNECTOR = "connector"
    POSTCONDITION = "postcondition"
    DISCLOSURE = "disclosure"
    EVALUATOR_INFRASTRUCTURE = "evaluator_infrastructure"


@dataclass(frozen=True, slots=True)
class FaultDefinition:
    fault_id: str
    version: str
    content_digest: str
    surface: FaultSurface
    coverage_target_id: str
    required: bool

    def __post_init__(self) -> None:
        _require_id(self.fault_id, "fault_id")
        _require_text(self.version, "fault version", maximum=256)
        _require_digest(self.content_digest, "fault content_digest")
        if not isinstance(self.surface, FaultSurface):
            raise ValueError("fault surface is unknown")
        if (
            not isinstance(self.coverage_target_id, str)
            or _FAULT_COVERAGE_TARGET.fullmatch(self.coverage_target_id) is None
        ):
            raise ValueError("fault coverage_target_id must be an opaque fcov token")
        if not isinstance(self.required, bool):
            raise ValueError("fault required must be a boolean")

    def as_dict(self) -> dict[str, object]:
        return {
            "content_digest": self.content_digest,
            "coverage_target_id": self.coverage_target_id,
            "fault_id_digest": _payload_digest({"fault_id": self.fault_id}),
            "required": self.required,
            "surface": self.surface.value,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class CorpusScenario:
    scenario: CompiledScenario
    world_pin: ArtifactPin
    dependency_keys: tuple[ArtifactKey, ...]
    persona_id: str
    adversarial_intent_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, CompiledScenario):
            raise ValueError("corpus scenario must be a CompiledScenario")
        if (
            not isinstance(self.world_pin, ArtifactPin)
            or self.world_pin.kind is not ArtifactKind.WORLD
        ):
            raise ValueError("corpus scenario world_pin must have kind 'world'")
        if not isinstance(self.dependency_keys, tuple) or not self.dependency_keys:
            raise ValueError("corpus scenario dependency_keys must be non-empty")
        if any(not isinstance(key, ArtifactKey) for key in self.dependency_keys):
            raise ValueError("corpus scenario dependency_keys contain an invalid value")
        if len(self.dependency_keys) != len(set(self.dependency_keys)):
            raise ValueError("corpus scenario dependency_keys must be unique")
        object.__setattr__(self, "dependency_keys", tuple(sorted(self.dependency_keys)))
        _require_id(self.persona_id, "corpus scenario persona_id")
        object.__setattr__(
            self,
            "adversarial_intent_ids",
            _sorted_unique_ids(
                self.adversarial_intent_ids,
                "corpus scenario adversarial intent IDs",
            ),
        )

    @property
    def scenario_id(self) -> str:
        return self.scenario.candidate_input.scenario_id


@dataclass(frozen=True, slots=True)
class ResolutionScenarioCorpus:
    corpus_id: str
    version: str
    contract_pin: ArtifactPin
    personas: tuple[PersonaDefinition, ...]
    adversarial_intents: tuple[AdversarialIntentDefinition, ...]
    faults: tuple[FaultDefinition, ...]
    scenarios: tuple[CorpusScenario, ...]
    schema_version: str = _CORPUS_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.corpus_id, "corpus_id")
        _require_text(self.version, "corpus version", maximum=256)
        if (
            not isinstance(self.contract_pin, ArtifactPin)
            or self.contract_pin.kind is not ArtifactKind.CONTRACT
        ):
            raise ValueError("corpus contract_pin must have kind 'contract'")
        if self.schema_version != _CORPUS_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_CORPUS_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

        if not isinstance(self.personas, tuple) or not self.personas:
            raise ValueError("corpus personas must be a non-empty immutable tuple")
        persona_by_id: dict[str, PersonaDefinition] = {}
        for persona in self.personas:
            if not isinstance(persona, PersonaDefinition):
                raise ValueError("corpus personas contain an invalid value")
            if persona.persona_id in persona_by_id:
                raise ValueError("corpus has a duplicate persona_id")
            persona_by_id[persona.persona_id] = persona
        object.__setattr__(
            self,
            "personas",
            tuple(sorted(persona_by_id.values(), key=lambda value: value.persona_id)),
        )

        if not isinstance(self.adversarial_intents, tuple) or not self.adversarial_intents:
            raise ValueError("corpus adversarial_intents must be a non-empty immutable tuple")
        adversarial_by_id: dict[str, AdversarialIntentDefinition] = {}
        for intent in self.adversarial_intents:
            if not isinstance(intent, AdversarialIntentDefinition):
                raise ValueError("corpus adversarial_intents contain an invalid value")
            if intent.intent_id in adversarial_by_id:
                raise ValueError("corpus has a duplicate adversarial intent_id")
            adversarial_by_id[intent.intent_id] = intent
        object.__setattr__(
            self,
            "adversarial_intents",
            tuple(sorted(adversarial_by_id.values(), key=lambda value: value.intent_id)),
        )

        if not isinstance(self.faults, tuple) or not self.faults:
            raise ValueError("corpus faults must be a non-empty immutable tuple")
        fault_by_id: dict[str, FaultDefinition] = {}
        coverage_ids: set[str] = set()
        for fault in self.faults:
            if not isinstance(fault, FaultDefinition):
                raise ValueError("corpus faults contain an invalid value")
            if fault.fault_id in fault_by_id:
                raise ValueError("corpus has a duplicate fault_id")
            if fault.coverage_target_id in coverage_ids:
                raise ValueError("corpus has a duplicate fault coverage_target_id")
            fault_by_id[fault.fault_id] = fault
            coverage_ids.add(fault.coverage_target_id)
        required_surfaces = {fault.surface for fault in self.faults if fault.required}
        missing_surfaces = set(FaultSurface) - required_surfaces
        if missing_surfaces:
            raise ValueError("corpus required faults do not cover every required surface")
        object.__setattr__(
            self,
            "faults",
            tuple(sorted(fault_by_id.values(), key=lambda value: value.coverage_target_id)),
        )

        if not isinstance(self.scenarios, tuple) or not self.scenarios:
            raise ValueError("corpus scenarios must be a non-empty immutable tuple")
        scenario_by_id: dict[str, CorpusScenario] = {}
        referenced_personas: set[str] = set()
        referenced_adversarial: set[str] = set()
        contract_identity = (
            self.contract_pin.artifact_id,
            self.contract_pin.version,
            self.contract_pin.digest,
        )
        for scenario in self.scenarios:
            if not isinstance(scenario, CorpusScenario):
                raise ValueError("corpus scenarios contain an invalid value")
            if scenario.scenario_id in scenario_by_id:
                raise ValueError("corpus has a duplicate scenario_id")
            scenario_by_id[scenario.scenario_id] = scenario
            if scenario.persona_id not in persona_by_id:
                raise ValueError("corpus scenario references an unknown persona")
            referenced_personas.add(scenario.persona_id)
            unknown_intents = set(scenario.adversarial_intent_ids) - adversarial_by_id.keys()
            if unknown_intents:
                raise ValueError("corpus scenario references an unknown adversarial intent")
            referenced_adversarial.update(scenario.adversarial_intent_ids)
            unknown_faults = set(scenario.scenario.world.fault_ids) - fault_by_id.keys()
            if unknown_faults:
                raise ValueError("corpus scenario references an unknown fault")
            expected = scenario.scenario.hidden_expected
            if (
                scenario.scenario.candidate_input.journey_id,
                expected.contract_version,
                expected.contract_digest,
            ) != contract_identity:
                raise ValueError("corpus scenario contract identity does not match corpus")
            if expected.contract_id != self.contract_pin.artifact_id:
                raise ValueError("corpus scenario contract identity does not match corpus")
        if referenced_personas != persona_by_id.keys():
            raise ValueError("corpus contains an unreferenced persona")
        if referenced_adversarial != adversarial_by_id.keys():
            raise ValueError("corpus contains an unreferenced adversarial intent")
        object.__setattr__(
            self,
            "scenarios",
            tuple(sorted(scenario_by_id.values(), key=lambda value: value.scenario_id)),
        )


@dataclass(frozen=True, slots=True)
class CompiledCorpusScenario:
    fixture: ReplayScenarioFixture
    persona_id: str
    adversarial_intent_ids: tuple[str, ...]
    fault_coverage_target_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.fixture, ReplayScenarioFixture):
            raise ValueError("compiled corpus fixture must be a ReplayScenarioFixture")
        _require_id(self.persona_id, "compiled corpus persona_id")
        object.__setattr__(
            self,
            "adversarial_intent_ids",
            _sorted_unique_ids(
                self.adversarial_intent_ids,
                "compiled corpus adversarial intent IDs",
            ),
        )
        object.__setattr__(
            self,
            "fault_coverage_target_ids",
            _sorted_unique_ids(
                self.fault_coverage_target_ids,
                "compiled corpus fault coverage target IDs",
            ),
        )

    @property
    def scenario_id(self) -> str:
        return self.fixture.scenario_id

    def as_dict(self) -> dict[str, object]:
        binding = self.fixture.binding()
        return {
            "adversarial_intent_ids": list(self.adversarial_intent_ids),
            "coverage_target_count": len(self.fixture.coverage_target_ids),
            "coverage_target_ids_digest": _payload_digest(list(self.fixture.coverage_target_ids)),
            "fault_coverage_target_ids": list(self.fault_coverage_target_ids),
            "persona_id": self.persona_id,
            "scenario_binding_digest": scenario_binding_digest(binding),
            "scenario_id": self.scenario_id,
        }


@dataclass(frozen=True, slots=True)
class CompiledResolutionScenarioCorpus:
    corpus_id: str
    version: str
    contract_pin: ArtifactPin
    personas: tuple[PersonaDefinition, ...]
    adversarial_intents: tuple[AdversarialIntentDefinition, ...]
    faults: tuple[FaultDefinition, ...]
    scenarios: tuple[CompiledCorpusScenario, ...]
    required_branch_target_ids: tuple[str, ...]
    schema_version: str = _CORPUS_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_id(self.corpus_id, "compiled corpus_id")
        _require_text(self.version, "compiled corpus version", maximum=256)
        if (
            not isinstance(self.contract_pin, ArtifactPin)
            or self.contract_pin.kind is not ArtifactKind.CONTRACT
        ):
            raise ValueError("compiled corpus contract_pin must have kind 'contract'")
        if not isinstance(self.scenarios, tuple) or not self.scenarios:
            raise ValueError("compiled corpus scenarios must be non-empty")
        if any(not isinstance(value, CompiledCorpusScenario) for value in self.scenarios):
            raise ValueError("compiled corpus scenarios contain an invalid value")
        if len({value.scenario_id for value in self.scenarios}) != len(self.scenarios):
            raise ValueError("compiled corpus has a duplicate scenario_id")
        object.__setattr__(
            self,
            "scenarios",
            tuple(sorted(self.scenarios, key=lambda value: value.scenario_id)),
        )
        object.__setattr__(
            self,
            "required_branch_target_ids",
            _sorted_unique_text(
                self.required_branch_target_ids,
                "required branch target IDs",
            ),
        )
        if not self.required_branch_target_ids:
            raise ValueError("required branch target IDs cannot be empty")
        if self.schema_version != _CORPUS_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_CORPUS_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    @property
    def required_fault_target_ids(self) -> tuple[str, ...]:
        return tuple(sorted(fault.coverage_target_id for fault in self.faults if fault.required))

    def as_dict(self) -> dict[str, object]:
        return {
            "adversarial_intents": [value.as_dict() for value in self.adversarial_intents],
            "contract_pin": self.contract_pin.as_dict(),
            "corpus_id": self.corpus_id,
            "evidence_class": self.evidence_class,
            "faults": [value.as_dict() for value in self.faults],
            "personas": [value.as_dict() for value in self.personas],
            "required_branch_target_count": len(self.required_branch_target_ids),
            "required_branch_target_ids_digest": _payload_digest(
                list(self.required_branch_target_ids)
            ),
            "required_fault_target_ids": list(self.required_fault_target_ids),
            "scenarios": [value.as_dict() for value in self.scenarios],
            "schema_version": self.schema_version,
            "version": self.version,
        }


def compile_corpus(
    corpus: ResolutionScenarioCorpus,
    *,
    contract: ResolutionContract,
) -> CompiledResolutionScenarioCorpus:
    if not isinstance(corpus, ResolutionScenarioCorpus):
        raise ValueError("corpus must be a ResolutionScenarioCorpus")
    if not isinstance(contract, ResolutionContract):
        raise ValueError("contract must be a ResolutionContract")
    expected_contract_pin = ArtifactPin(
        kind=ArtifactKind.CONTRACT,
        artifact_id=contract.id,
        version=contract.version,
        digest=contract_digest(contract),
    )
    if corpus.contract_pin != expected_contract_pin:
        raise ValueError("corpus contract identity does not match contract")

    branch_targets = compile_branch_targets(contract)
    target_by_branch = {
        (target.step_id, target.event): target.target_id for target in branch_targets
    }
    fault_by_id = {fault.fault_id: fault for fault in corpus.faults}
    compiled_scenarios: list[CompiledCorpusScenario] = []
    for authoring in corpus.scenarios:
        scenario = authoring.scenario
        expected = scenario.hidden_expected
        validated = compile_scenario(
            contract=contract,
            candidate_input=scenario.candidate_input,
            world=scenario.world,
            branch_path=expected.branch_path,
            terminal_outcome=expected.terminal_outcome,
            reason_codes=expected.reason_codes,
            canonical_state=expected.canonical_state,
        )
        coverage_target_ids = tuple(
            target_by_branch[(branch.step_id, branch.event)]
            for branch in validated.hidden_expected.branch_path
        )
        fixture = ReplayScenarioFixture(
            scenario=validated,
            world_pin=authoring.world_pin,
            coverage_target_ids=coverage_target_ids,
            dependency_keys=authoring.dependency_keys,
        )
        compiled_scenarios.append(
            CompiledCorpusScenario(
                fixture=fixture,
                persona_id=authoring.persona_id,
                adversarial_intent_ids=authoring.adversarial_intent_ids,
                fault_coverage_target_ids=tuple(
                    fault_by_id[fault_id].coverage_target_id
                    for fault_id in validated.world.fault_ids
                ),
            )
        )
    return CompiledResolutionScenarioCorpus(
        corpus_id=corpus.corpus_id,
        version=corpus.version,
        contract_pin=corpus.contract_pin,
        personas=corpus.personas,
        adversarial_intents=corpus.adversarial_intents,
        faults=corpus.faults,
        scenarios=tuple(compiled_scenarios),
        required_branch_target_ids=tuple(target.target_id for target in branch_targets),
    )


def canonical_corpus_json(corpus: CompiledResolutionScenarioCorpus) -> str:
    if not isinstance(corpus, CompiledResolutionScenarioCorpus):
        raise ValueError("corpus must be a CompiledResolutionScenarioCorpus")
    return _canonical_json(corpus.as_dict())


def corpus_digest(corpus: CompiledResolutionScenarioCorpus) -> str:
    return hashlib.sha256(canonical_corpus_json(corpus).encode("utf-8")).hexdigest()


def compiled_corpus_pin(corpus: CompiledResolutionScenarioCorpus) -> ArtifactPin:
    if not isinstance(corpus, CompiledResolutionScenarioCorpus):
        raise ValueError("corpus must be a CompiledResolutionScenarioCorpus")
    return ArtifactPin(
        kind=ArtifactKind.SCENARIO_SET,
        artifact_id=corpus.corpus_id,
        version=corpus.version,
        digest=corpus_digest(corpus),
    )


class CorpusCoverageIssueCode(StrEnum):
    CONTRACT_PIN_MISMATCH = "contract_pin_mismatch"
    SCENARIO_SET_PIN_MISMATCH = "scenario_set_pin_mismatch"
    MISSING_MANIFEST_SCENARIO = "missing_manifest_scenario"
    EXTRA_MANIFEST_SCENARIO = "extra_manifest_scenario"
    SCENARIO_BINDING_MISMATCH = "scenario_binding_mismatch"
    MISSING_BRANCH_TARGET = "missing_branch_target"
    UNKNOWN_BRANCH_TARGET = "unknown_branch_target"
    MISSING_FAULT_TARGET = "missing_fault_target"
    UNKNOWN_FAULT_TARGET = "unknown_fault_target"


@dataclass(frozen=True, slots=True)
class CorpusCoverageIssue:
    code: CorpusCoverageIssueCode
    subject_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, CorpusCoverageIssueCode):
            raise ValueError("corpus coverage issue code is unknown")
        if self.subject_id is not None:
            _require_text(self.subject_id, "coverage issue subject_id", maximum=1024)

    def as_dict(self) -> dict[str, str | None]:
        return {"code": self.code.value, "subject_id": self.subject_id}


@dataclass(frozen=True, slots=True)
class CoverageStatistic:
    covered: int
    required: int

    def __post_init__(self) -> None:
        for field, value in (("covered", self.covered), ("required", self.required)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"coverage {field} must be a non-negative integer")
        if self.covered > self.required:
            raise ValueError("coverage covered cannot exceed required")

    def as_dict(self) -> dict[str, int]:
        return {"covered": self.covered, "required": self.required}


def _issue_sort_key(issue: CorpusCoverageIssue) -> tuple[str, str]:
    return (issue.code.value, issue.subject_id or "")


@dataclass(frozen=True, slots=True)
class ManifestCoverageReport:
    manifest_digest: str
    corpus_digest: str
    contract_digest: str
    branch_coverage: CoverageStatistic
    fault_coverage: CoverageStatistic
    missing_branch_target_ids: tuple[str, ...]
    missing_fault_target_ids: tuple[str, ...]
    issues: tuple[CorpusCoverageIssue, ...]
    schema_version: str = _REPORT_SCHEMA_VERSION
    evidence_class: str = _EVIDENCE_CLASS

    def __post_init__(self) -> None:
        _require_digest(self.manifest_digest, "coverage report manifest_digest")
        _require_digest(self.corpus_digest, "coverage report corpus_digest")
        _require_digest(self.contract_digest, "coverage report contract_digest")
        if not isinstance(self.branch_coverage, CoverageStatistic):
            raise ValueError("branch_coverage must be a CoverageStatistic")
        if not isinstance(self.fault_coverage, CoverageStatistic):
            raise ValueError("fault_coverage must be a CoverageStatistic")
        object.__setattr__(
            self,
            "missing_branch_target_ids",
            _sorted_unique_text(
                self.missing_branch_target_ids,
                "missing branch target IDs",
            ),
        )
        object.__setattr__(
            self,
            "missing_fault_target_ids",
            _sorted_unique_ids(
                self.missing_fault_target_ids,
                "missing fault target IDs",
            ),
        )
        if not isinstance(self.issues, tuple) or any(
            not isinstance(issue, CorpusCoverageIssue) for issue in self.issues
        ):
            raise ValueError("coverage report issues must be an immutable tuple")
        object.__setattr__(
            self,
            "issues",
            tuple(sorted(set(self.issues), key=_issue_sort_key)),
        )
        if self.schema_version != _REPORT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {_REPORT_SCHEMA_VERSION!r}")
        if self.evidence_class != _EVIDENCE_CLASS:
            raise ValueError(f"evidence_class must be {_EVIDENCE_CLASS!r}")

    @property
    def complete(self) -> bool:
        return (
            not self.issues
            and not self.missing_branch_target_ids
            and not self.missing_fault_target_ids
            and self.branch_coverage.covered == self.branch_coverage.required
            and self.fault_coverage.covered == self.fault_coverage.required
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "branch_coverage": self.branch_coverage.as_dict(),
            "complete": self.complete,
            "contract_digest": self.contract_digest,
            "corpus_digest": self.corpus_digest,
            "evidence_class": self.evidence_class,
            "fault_coverage": self.fault_coverage.as_dict(),
            "issues": [issue.as_dict() for issue in self.issues],
            "manifest_digest": self.manifest_digest,
            "missing_branch_target_ids": list(self.missing_branch_target_ids),
            "missing_fault_target_ids": list(self.missing_fault_target_ids),
            "schema_version": self.schema_version,
        }


def build_manifest_coverage_report(
    corpus: CompiledResolutionScenarioCorpus,
    manifest: ReplayManifest,
) -> ManifestCoverageReport:
    if not isinstance(corpus, CompiledResolutionScenarioCorpus):
        raise ValueError("corpus must be a CompiledResolutionScenarioCorpus")
    if not isinstance(manifest, ReplayManifest):
        raise ValueError("manifest must be a ReplayManifest")

    issues: list[CorpusCoverageIssue] = []
    contract_pin_matches = manifest.contract_pin == corpus.contract_pin
    scenario_set_pin_matches = manifest.scenario_set_pin == compiled_corpus_pin(corpus)
    if not contract_pin_matches:
        issues.append(CorpusCoverageIssue(CorpusCoverageIssueCode.CONTRACT_PIN_MISMATCH))
    if not scenario_set_pin_matches:
        issues.append(CorpusCoverageIssue(CorpusCoverageIssueCode.SCENARIO_SET_PIN_MISMATCH))
    manifest_identity_matches = contract_pin_matches and scenario_set_pin_matches

    manifest_by_id = {binding.scenario_id: binding for binding in manifest.scenarios}
    corpus_by_id = {scenario.scenario_id: scenario for scenario in corpus.scenarios}
    covered_branches: set[str] = set()
    covered_faults: set[str] = set()
    for scenario_id, compiled_scenario in corpus_by_id.items():
        manifest_binding = manifest_by_id.get(scenario_id)
        if manifest_binding is None:
            issues.append(
                CorpusCoverageIssue(
                    CorpusCoverageIssueCode.MISSING_MANIFEST_SCENARIO,
                    scenario_id,
                )
            )
            continue
        expected_binding = compiled_scenario.fixture.binding()
        if manifest_binding != expected_binding:
            issues.append(
                CorpusCoverageIssue(
                    CorpusCoverageIssueCode.SCENARIO_BINDING_MISMATCH,
                    scenario_id,
                )
            )
            continue
        if not manifest_identity_matches:
            continue
        covered_branches.update(compiled_scenario.fixture.coverage_target_ids)
        covered_faults.update(compiled_scenario.fault_coverage_target_ids)

    for scenario_id in manifest_by_id.keys() - corpus_by_id.keys():
        issues.append(
            CorpusCoverageIssue(
                CorpusCoverageIssueCode.EXTRA_MANIFEST_SCENARIO,
                scenario_id,
            )
        )

    required_branches = set(corpus.required_branch_target_ids)
    unknown_branches = covered_branches - required_branches
    for target_id in unknown_branches:
        issues.append(
            CorpusCoverageIssue(
                CorpusCoverageIssueCode.UNKNOWN_BRANCH_TARGET,
                target_id,
            )
        )
    counted_branches = covered_branches & required_branches
    missing_branches = required_branches - counted_branches
    for target_id in missing_branches:
        issues.append(
            CorpusCoverageIssue(
                CorpusCoverageIssueCode.MISSING_BRANCH_TARGET,
                target_id,
            )
        )

    known_faults = {fault.coverage_target_id for fault in corpus.faults}
    unknown_faults = covered_faults - known_faults
    for target_id in unknown_faults:
        issues.append(
            CorpusCoverageIssue(
                CorpusCoverageIssueCode.UNKNOWN_FAULT_TARGET,
                target_id,
            )
        )
    required_faults = set(corpus.required_fault_target_ids)
    counted_faults = covered_faults & required_faults
    missing_faults = required_faults - counted_faults
    for target_id in missing_faults:
        issues.append(
            CorpusCoverageIssue(
                CorpusCoverageIssueCode.MISSING_FAULT_TARGET,
                target_id,
            )
        )

    return ManifestCoverageReport(
        manifest_digest=replay_manifest_digest(manifest),
        corpus_digest=corpus_digest(corpus),
        contract_digest=corpus.contract_pin.digest,
        branch_coverage=CoverageStatistic(
            covered=len(counted_branches),
            required=len(required_branches),
        ),
        fault_coverage=CoverageStatistic(
            covered=len(counted_faults),
            required=len(required_faults),
        ),
        missing_branch_target_ids=tuple(missing_branches),
        missing_fault_target_ids=tuple(missing_faults),
        issues=tuple(issues),
    )


def canonical_manifest_coverage_report_json(report: ManifestCoverageReport) -> str:
    if not isinstance(report, ManifestCoverageReport):
        raise ValueError("report must be a ManifestCoverageReport")
    return _canonical_json(report.as_dict())


def manifest_coverage_report_digest(report: ManifestCoverageReport) -> str:
    return hashlib.sha256(
        canonical_manifest_coverage_report_json(report).encode("utf-8")
    ).hexdigest()


__all__ = [
    "AdversarialIntentDefinition",
    "CompiledCorpusScenario",
    "CompiledResolutionScenarioCorpus",
    "CorpusCoverageIssue",
    "CorpusCoverageIssueCode",
    "CorpusScenario",
    "CoverageStatistic",
    "FaultDefinition",
    "FaultSurface",
    "ManifestCoverageReport",
    "PersonaDefinition",
    "ResolutionScenarioCorpus",
    "build_manifest_coverage_report",
    "canonical_corpus_json",
    "canonical_manifest_coverage_report_json",
    "compile_corpus",
    "compiled_corpus_pin",
    "corpus_digest",
    "manifest_coverage_report_digest",
]
