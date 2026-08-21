from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Protocol, TypeAlias

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

SEMANTIC_VERSION_PATTERN = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
CONTRACT_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$"
SYMBOL_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$"
COMPONENT_ID_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
FIELD_PATH_PATTERN = (
    r"^(?:inputs|evidence|case|actor|tenant)\.[a-z][a-z0-9_-]*"
    r"(?:\.[a-z][a-z0-9_-]*)*$"
)
SCOPE_PATTERN = r"^[a-z][a-z0-9]*(?:[.:_-][a-z0-9]+)*$"
LOCALE_PATTERN = r"^[a-z]{2,3}(?:-[A-Z]{2})?$"
REASON_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{1,63}$"
PAYLOAD_FIELD_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"

SemanticVersion = Annotated[
    str,
    StringConstraints(pattern=SEMANTIC_VERSION_PATTERN, min_length=5, max_length=128),
]
ContractId = Annotated[
    str,
    StringConstraints(pattern=CONTRACT_ID_PATTERN, min_length=3, max_length=128),
]
SymbolId = Annotated[
    str,
    StringConstraints(pattern=SYMBOL_ID_PATTERN, min_length=1, max_length=128),
]
ComponentId = Annotated[
    str,
    StringConstraints(pattern=COMPONENT_ID_PATTERN, min_length=1, max_length=128),
]
FieldPath = Annotated[
    str,
    StringConstraints(pattern=FIELD_PATH_PATTERN, min_length=3, max_length=256),
]
Scope = Annotated[
    str,
    StringConstraints(pattern=SCOPE_PATTERN, min_length=3, max_length=128),
]
Locale = Annotated[str, StringConstraints(pattern=LOCALE_PATTERN)]
ReasonCode = Annotated[str, StringConstraints(pattern=REASON_CODE_PATTERN)]
PayloadField = Annotated[str, StringConstraints(pattern=PAYLOAD_FIELD_PATTERN)]
Sha256Digest = Annotated[str, StringConstraints(pattern=SHA256_PATTERN)]
JsonScalar: TypeAlias = str | int | float | bool | None


class _Identified(Protocol):
    @property
    def id(self) -> str: ...


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class ContractLifecycle(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    SIMULATED = "simulated"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ContractRiskTier(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE_WRITE = "irreversible_write"


class TerminalOutcome(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    CLARIFICATION_REQUIRED = "clarification_required"
    ESCALATED = "escalated"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PredicateOperator(StrEnum):
    ALL = "all"
    ANY = "any"
    NOT = "not"
    EQ = "eq"
    IN = "in"
    EXISTS = "exists"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"
    RANGE_CONTAINS = "range_contains"


class InputType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class EvidenceSourceKind(StrEnum):
    SOURCE_SYSTEM = "source_system"
    KNOWLEDGE = "knowledge"
    USER_ASSERTION = "user_assertion"


class EvidenceFailureAction(StrEnum):
    CLARIFY = "clarify"
    ESCALATE = "escalate"
    DENY = "deny"


class StepKind(StrEnum):
    INPUT = "input"
    REASONING = "reasoning"
    GATHER_EVIDENCE = "gather_evidence"
    POLICY = "policy"
    READ_ACTION = "read_action"
    WRITE_ACTION = "write_action"
    POSTCONDITION = "postcondition"
    RESPONSE = "response"


class TransitionEvent(StrEnum):
    COMPLETE = "complete"
    MISSING = "missing"
    STALE = "stale"
    CONFLICT = "conflict"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    FAILURE = "failure"
    ALLOW = "allow"
    CLARIFY = "clarify"
    DENY = "deny"
    ESCALATE = "escalate"
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class ActionRisk(StrEnum):
    READ = "read"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE_WRITE = "irreversible_write"


class ConfirmationMode(StrEnum):
    NOT_REQUIRED = "not_required"
    EXPLICIT = "explicit"
    SUPERVISOR = "supervisor"


class IdempotencyStrategy(StrEnum):
    NOT_REQUIRED = "not_required"
    CONNECTOR_KEY = "connector_key"
    RECONCILE_BY_STATE = "reconcile_by_state"


class ClaimPolicy(StrEnum):
    SUPPORTED_ONLY = "supported_only"
    NO_MATERIAL_CLAIMS = "no_material_claims"


class EffectiveRange(_StrictModel):
    from_: AwareDatetime = Field(alias="from")
    to: AwareDatetime | None

    @model_validator(mode="after")
    def _validate_order(self) -> EffectiveRange:
        if self.to is not None and self.to <= self.from_:
            raise ValueError("effective.to must be later than effective.from")
        return self


class FieldOperand(_StrictModel):
    kind: Literal["field"]
    path: FieldPath


class LiteralOperand(_StrictModel):
    kind: Literal["literal"]
    value: JsonScalar

    @model_validator(mode="after")
    def _reject_non_finite_number(self) -> LiteralOperand:
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("literal numbers must be finite")
        return self


class DateTimeOperand(_StrictModel):
    kind: Literal["datetime"]
    value: AwareDatetime


class DateTimeRangeOperand(_StrictModel):
    kind: Literal["datetime_range"]
    from_: AwareDatetime = Field(alias="from")
    to: AwareDatetime

    @model_validator(mode="after")
    def _validate_order(self) -> DateTimeRangeOperand:
        if self.to <= self.from_:
            raise ValueError("datetime range end must be later than start")
        return self


Operand = Annotated[
    FieldOperand | LiteralOperand | DateTimeOperand | DateTimeRangeOperand,
    Field(discriminator="kind"),
]


class Predicate(_StrictModel):
    op: PredicateOperator
    args: tuple[Predicate, ...] | None = None
    field: FieldPath | None = None
    left: Operand | None = None
    right: Operand | None = None
    values: tuple[JsonScalar, ...] | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> Predicate:
        group_operators = {PredicateOperator.ALL, PredicateOperator.ANY}
        comparison_operators = {
            PredicateOperator.EQ,
            PredicateOperator.LT,
            PredicateOperator.LTE,
            PredicateOperator.GT,
            PredicateOperator.GTE,
            PredicateOperator.DATE_BEFORE,
            PredicateOperator.DATE_AFTER,
            PredicateOperator.RANGE_CONTAINS,
        }

        if self.op in group_operators:
            if not self.args:
                raise ValueError(f"predicate '{self.op}' requires non-empty args")
            self._require_only("args")
        elif self.op is PredicateOperator.NOT:
            if self.args is None or len(self.args) != 1:
                raise ValueError("predicate 'not' requires exactly one arg")
            self._require_only("args")
        elif self.op is PredicateOperator.EXISTS:
            if self.field is None:
                raise ValueError("predicate 'exists' requires field")
            self._require_only("field")
        elif self.op is PredicateOperator.IN:
            if self.field is None or not self.values:
                raise ValueError("predicate 'in' requires field and non-empty values")
            self._require_only("field", "values")
            self._reject_non_finite_values()
        elif self.op in comparison_operators:
            if self.left is None or self.right is None:
                raise ValueError(f"predicate '{self.op}' requires left and right operands")
            self._require_only("left", "right")
            self._validate_typed_comparison()
        else:  # pragma: no cover - enum validation rejects unknown values first
            raise ValueError(f"unsupported predicate operator: {self.op}")
        return self

    def _require_only(self, *allowed: str) -> None:
        populated = {
            name
            for name in ("args", "field", "left", "right", "values")
            if getattr(self, name) is not None
        }
        unexpected = populated.difference(allowed)
        if unexpected:
            rendered = ", ".join(sorted(unexpected))
            raise ValueError(f"predicate '{self.op}' has incompatible fields: {rendered}")

    def _reject_non_finite_values(self) -> None:
        assert self.values is not None
        if any(isinstance(value, float) and not math.isfinite(value) for value in self.values):
            raise ValueError("predicate values must contain only finite numbers")

    def _validate_typed_comparison(self) -> None:
        assert self.left is not None
        assert self.right is not None
        if self.op in {PredicateOperator.DATE_BEFORE, PredicateOperator.DATE_AFTER}:
            allowed = (FieldOperand, DateTimeOperand)
            if not isinstance(self.left, allowed) or not isinstance(self.right, allowed):
                raise ValueError(f"predicate '{self.op}' requires datetime or field operands")
        elif self.op is PredicateOperator.RANGE_CONTAINS:
            if not isinstance(self.left, (FieldOperand, DateTimeRangeOperand)) or not isinstance(
                self.right, (FieldOperand, DateTimeOperand)
            ):
                raise ValueError(
                    "predicate 'range_contains' requires range/field then datetime/field operands"
                )

    def field_paths(self) -> set[str]:
        paths: set[str] = set()
        if self.field is not None:
            paths.add(self.field)
        for operand in (self.left, self.right):
            if isinstance(operand, FieldOperand):
                paths.add(operand.path)
        if self.args is not None:
            for argument in self.args:
                paths.update(argument.field_paths())
        return paths


class InputRequirement(_StrictModel):
    id: SymbolId
    type: InputType
    required: bool
    sensitive: bool


class FreshnessRequirement(_StrictModel):
    observed_at: FieldPath
    max_age_seconds: Annotated[int, Field(strict=True, gt=0, le=31_536_000)]


class ValidTimeRequirement(_StrictModel):
    reference: FieldPath
    require_overlap: Literal[True]


class EvidenceRequirement(_StrictModel):
    id: SymbolId
    source_kind: EvidenceSourceKind
    authority: ComponentId
    freshness: FreshnessRequirement
    valid_time: ValidTimeRequirement
    on_missing: EvidenceFailureAction
    on_stale: EvidenceFailureAction
    on_conflict: EvidenceFailureAction


class RuleDefinition(_StrictModel):
    id: SymbolId
    predicate: Predicate


class SafeReference(_StrictModel):
    id: ComponentId
    version: SemanticVersion
    schema_digest: Sha256Digest


class ConfirmationRequirement(_StrictModel):
    mode: ConfirmationMode
    ttl_seconds: Annotated[int, Field(strict=True, gt=0, le=86_400)] | None = None

    @model_validator(mode="after")
    def _validate_ttl(self) -> ConfirmationRequirement:
        if self.mode is ConfirmationMode.NOT_REQUIRED and self.ttl_seconds is not None:
            raise ValueError("confirmation ttl is forbidden when confirmation is not required")
        if self.mode is not ConfirmationMode.NOT_REQUIRED and self.ttl_seconds is None:
            raise ValueError("confirmed actions require a finite confirmation ttl")
        return self


class IdempotencyRequirement(_StrictModel):
    strategy: IdempotencyStrategy
    key_fields: tuple[FieldPath, ...]

    @model_validator(mode="after")
    def _validate_key_fields(self) -> IdempotencyRequirement:
        if self.strategy is IdempotencyStrategy.NOT_REQUIRED and self.key_fields:
            raise ValueError("idempotency key fields are forbidden when not required")
        if self.strategy is not IdempotencyStrategy.NOT_REQUIRED and not self.key_fields:
            raise ValueError("idempotent actions require at least one canonical key field")
        if len(self.key_fields) != len(set(self.key_fields)):
            raise ValueError("idempotency key fields must be unique")
        return self


class ActionDeclaration(_StrictModel):
    manifest_id: ComponentId
    manifest_version: SemanticVersion
    manifest_schema_digest: Sha256Digest
    risk: ActionRisk
    required_scopes: Annotated[tuple[Scope, ...], Field(min_length=1)]
    input_fields: Annotated[tuple[FieldPath, ...], Field(min_length=1)]
    output_evidence_requirement_id: SymbolId
    timeout_seconds: Annotated[int, Field(strict=True, gt=0, le=300)]
    confirmation: ConfirmationRequirement
    idempotency: IdempotencyRequirement
    postcondition_id: SymbolId
    reconciliation_checker: SafeReference | None = None

    @model_validator(mode="after")
    def _validate_action_safety(self) -> ActionDeclaration:
        if len(self.required_scopes) != len(set(self.required_scopes)):
            raise ValueError("action scopes must be unique")
        if len(self.input_fields) != len(set(self.input_fields)):
            raise ValueError("action input fields must be unique")

        if self.risk is ActionRisk.READ:
            if self.confirmation.mode is not ConfirmationMode.NOT_REQUIRED:
                raise ValueError("read actions must not request write confirmation")
            return self

        if self.confirmation.mode is ConfirmationMode.NOT_REQUIRED:
            raise ValueError("write actions require explicit confirmation")
        if self.idempotency.strategy is IdempotencyStrategy.NOT_REQUIRED:
            raise ValueError("write actions require an idempotency strategy")
        if self.reconciliation_checker is None:
            raise ValueError("write actions require a reconciliation checker")
        if (
            self.risk is ActionRisk.IRREVERSIBLE_WRITE
            and self.confirmation.mode is not ConfirmationMode.SUPERVISOR
        ):
            raise ValueError("irreversible writes require supervisor confirmation")
        return self


class StepTransitionTarget(_StrictModel):
    type: Literal["step"]
    id: SymbolId


class TerminalTransitionTarget(_StrictModel):
    type: Literal["terminal"]
    outcome: TerminalOutcome


TransitionTarget = Annotated[
    StepTransitionTarget | TerminalTransitionTarget,
    Field(discriminator="type"),
]


class ContractStep(_StrictModel):
    _REQUIRED_EVENTS: ClassVar[dict[StepKind, frozenset[TransitionEvent]]] = {
        StepKind.INPUT: frozenset(
            {TransitionEvent.COMPLETE, TransitionEvent.MISSING, TransitionEvent.FAILURE}
        ),
        StepKind.REASONING: frozenset(
            {TransitionEvent.SUCCESS, TransitionEvent.TIMEOUT, TransitionEvent.FAILURE}
        ),
        StepKind.GATHER_EVIDENCE: frozenset(
            {
                TransitionEvent.COMPLETE,
                TransitionEvent.MISSING,
                TransitionEvent.STALE,
                TransitionEvent.CONFLICT,
                TransitionEvent.FAILURE,
            }
        ),
        StepKind.POLICY: frozenset(
            {
                TransitionEvent.ALLOW,
                TransitionEvent.CLARIFY,
                TransitionEvent.DENY,
                TransitionEvent.ESCALATE,
                TransitionEvent.FAILURE,
            }
        ),
        StepKind.READ_ACTION: frozenset(
            {TransitionEvent.SUCCESS, TransitionEvent.TIMEOUT, TransitionEvent.FAILURE}
        ),
        StepKind.WRITE_ACTION: frozenset(
            {TransitionEvent.SUCCESS, TransitionEvent.TIMEOUT, TransitionEvent.FAILURE}
        ),
        StepKind.POSTCONDITION: frozenset(
            {TransitionEvent.PASS, TransitionEvent.FAIL, TransitionEvent.UNKNOWN}
        ),
        StepKind.RESPONSE: frozenset(
            {TransitionEvent.SUCCESS, TransitionEvent.UNSUPPORTED, TransitionEvent.FAILURE}
        ),
    }

    id: SymbolId
    kind: StepKind
    evidence_requirement_ids: tuple[SymbolId, ...] = ()
    rule_id: SymbolId | None = None
    action: ActionDeclaration | None = None
    postcondition_ids: tuple[SymbolId, ...] = ()
    transitions: Annotated[dict[TransitionEvent, TransitionTarget], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_step_shape(self) -> ContractStep:
        actual_events = frozenset(self.transitions)
        required_events = self._REQUIRED_EVENTS[self.kind]
        if actual_events != required_events:
            missing = sorted(event.value for event in required_events.difference(actual_events))
            unexpected = sorted(event.value for event in actual_events.difference(required_events))
            raise ValueError(
                f"step '{self.id}' transitions mismatch; missing={missing}, unexpected={unexpected}"
            )

        if self.kind is StepKind.GATHER_EVIDENCE:
            if not self.evidence_requirement_ids:
                raise ValueError("gather_evidence steps require evidence_requirement_ids")
            self._forbid_references("rule", "action", "postcondition")
        elif self.kind is StepKind.POLICY:
            if self.rule_id is None:
                raise ValueError("policy steps require rule_id")
            self._forbid_references("evidence", "action", "postcondition")
        elif self.kind in {StepKind.READ_ACTION, StepKind.WRITE_ACTION}:
            if self.action is None:
                raise ValueError("action steps require an action declaration")
            expected_risk = (
                ActionRisk.READ if self.kind is StepKind.READ_ACTION else self.action.risk
            )
            if self.kind is StepKind.READ_ACTION and self.action.risk is not expected_risk:
                raise ValueError("read_action steps require action risk 'read'")
            if self.kind is StepKind.WRITE_ACTION and self.action.risk is ActionRisk.READ:
                raise ValueError("write_action steps require a write risk")
            self._forbid_references("evidence", "rule", "postcondition")
        elif self.kind is StepKind.POSTCONDITION:
            if not self.postcondition_ids:
                raise ValueError("postcondition steps require postcondition_ids")
            self._forbid_references("evidence", "rule", "action")
        else:
            self._forbid_references("evidence", "rule", "action", "postcondition")

        if len(self.evidence_requirement_ids) != len(set(self.evidence_requirement_ids)):
            raise ValueError("step evidence requirement ids must be unique")
        if len(self.postcondition_ids) != len(set(self.postcondition_ids)):
            raise ValueError("step postcondition ids must be unique")
        return self

    def _forbid_references(self, *reference_kinds: str) -> None:
        populated = {
            "evidence": bool(self.evidence_requirement_ids),
            "rule": self.rule_id is not None,
            "action": self.action is not None,
            "postcondition": bool(self.postcondition_ids),
        }
        forbidden = sorted(name for name in reference_kinds if populated[name])
        if forbidden:
            raise ValueError(f"step '{self.id}' has incompatible references: {forbidden}")


class PostconditionDeclaration(_StrictModel):
    id: SymbolId
    checker: SafeReference
    evidence_requirement_ids: Annotated[tuple[SymbolId, ...], Field(min_length=1)]
    required_for: Annotated[tuple[TerminalOutcome, ...], Field(min_length=1)]
    on_unknown: EvidenceFailureAction

    @model_validator(mode="after")
    def _validate_unique_references(self) -> PostconditionDeclaration:
        if len(self.evidence_requirement_ids) != len(set(self.evidence_requirement_ids)):
            raise ValueError("postcondition evidence requirement ids must be unique")
        if len(self.required_for) != len(set(self.required_for)):
            raise ValueError("postcondition required_for outcomes must be unique")
        return self


class TerminalOutcomeDefinition(_StrictModel):
    claim_policy: ClaimPolicy
    requires_all_postconditions: bool
    handoff_required: bool
    disclosure_id: SymbolId


class EscalationPolicy(_StrictModel):
    _REQUIRED_PAYLOAD_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"case_id", "contract_version", "evidence_summary", "reason_codes"}
    )

    enabled: Literal[True]
    reason_codes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    required_payload_fields: Annotated[tuple[PayloadField, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_handoff_payload(self) -> EscalationPolicy:
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("escalation reason codes must be unique")
        provided = set(self.required_payload_fields)
        missing = sorted(self._REQUIRED_PAYLOAD_FIELDS.difference(provided))
        if missing:
            raise ValueError(f"escalation payload is missing required fields: {missing}")
        if len(provided) != len(self.required_payload_fields):
            raise ValueError("escalation payload fields must be unique")
        return self


class DisclosurePolicy(_StrictModel):
    id: SymbolId
    version: SemanticVersion
    required: Literal[True]
    locales: Annotated[tuple[Locale, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_locales(self) -> DisclosurePolicy:
        if len(self.locales) != len(set(self.locales)):
            raise ValueError("disclosure locales must be unique")
        return self


class ContractBudgets(_StrictModel):
    wall_clock_seconds: Annotated[int, Field(strict=True, gt=0, le=600)]
    max_llm_calls: Annotated[int, Field(strict=True, ge=0, le=20)]
    max_input_tokens: Annotated[int, Field(strict=True, ge=0, le=200_000)]
    max_output_tokens: Annotated[int, Field(strict=True, ge=0, le=20_000)]
    max_retrieval_candidates: Annotated[int, Field(strict=True, gt=0, le=200)]
    max_rerank_candidates: Annotated[int, Field(strict=True, ge=0, le=100)]
    max_action_attempts: Annotated[int, Field(strict=True, gt=0, le=5)]
    max_clarification_turns: Annotated[int, Field(strict=True, ge=0, le=10)]
    max_evidence_items: Annotated[int, Field(strict=True, gt=0, le=200)]

    @model_validator(mode="after")
    def _validate_candidate_bounds(self) -> ContractBudgets:
        if self.max_rerank_candidates > self.max_retrieval_candidates:
            raise ValueError("max_rerank_candidates cannot exceed max_retrieval_candidates")
        return self


class ResolutionContract(_StrictModel):
    model_config = ConfigDict(
        json_schema_extra={"$id": "https://rag-new.local/schemas/resolution-contract/v0.1"}
    )

    schema_version: Literal["resolution-contract/v0.1"]
    id: ContractId
    version: SemanticVersion
    owner: ComponentId
    risk_tier: ContractRiskTier
    effective: EffectiveRange
    eligibility: Predicate | None = None
    entrypoint: SymbolId
    required_inputs: Annotated[tuple[InputRequirement, ...], Field(min_length=1)]
    evidence_requirements: Annotated[tuple[EvidenceRequirement, ...], Field(min_length=1)]
    rules: tuple[RuleDefinition, ...]
    steps: Annotated[tuple[ContractStep, ...], Field(min_length=1)]
    postconditions: Annotated[tuple[PostconditionDeclaration, ...], Field(min_length=1)]
    terminal_outcomes: Annotated[
        dict[TerminalOutcome, TerminalOutcomeDefinition], Field(min_length=1)
    ]
    escalation: EscalationPolicy
    disclosure: DisclosurePolicy
    budgets: ContractBudgets

    @model_validator(mode="after")
    def _validate_contract(self) -> ResolutionContract:
        input_ids = self._unique_ids(self.required_inputs, "required input")
        evidence_ids = self._unique_ids(self.evidence_requirements, "evidence requirement")
        rule_ids = self._unique_ids(self.rules, "rule")
        step_ids = self._unique_ids(self.steps, "step")
        postcondition_ids = self._unique_ids(self.postconditions, "postcondition")

        if self.entrypoint not in step_ids:
            raise ValueError(f"entrypoint '{self.entrypoint}' is not a declared step")

        self._validate_references(
            evidence_ids=evidence_ids,
            rule_ids=rule_ids,
            step_ids=step_ids,
            postcondition_ids=postcondition_ids,
        )
        self._validate_field_paths(input_ids=input_ids, evidence_ids=evidence_ids)
        self._validate_graph(step_ids)
        self._validate_terminal_safety()
        self._validate_risk_tier()
        return self

    @staticmethod
    def _unique_ids(items: tuple[_Identified, ...], label: str) -> set[str]:
        identifiers = [item.id for item in items]
        duplicates = sorted(
            {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
        )
        if duplicates:
            raise ValueError(f"duplicate {label} ids: {duplicates}")
        return set(identifiers)

    def _validate_references(
        self,
        *,
        evidence_ids: set[str],
        rule_ids: set[str],
        step_ids: set[str],
        postcondition_ids: set[str],
    ) -> None:
        for evidence in self.evidence_requirements:
            expected_prefix = f"evidence.{evidence.id}."
            if not evidence.freshness.observed_at.startswith(expected_prefix):
                raise ValueError(
                    f"freshness path for '{evidence.id}' must start with '{expected_prefix}'"
                )

        for step in self.steps:
            unknown_evidence = set(step.evidence_requirement_ids).difference(evidence_ids)
            if unknown_evidence:
                raise ValueError(
                    f"step '{step.id}' references unknown evidence: {sorted(unknown_evidence)}"
                )
            if step.rule_id is not None and step.rule_id not in rule_ids:
                raise ValueError(f"step '{step.id}' references unknown rule '{step.rule_id}'")
            unknown_postconditions = set(step.postcondition_ids).difference(postcondition_ids)
            if unknown_postconditions:
                raise ValueError(
                    f"step '{step.id}' references unknown postconditions: "
                    f"{sorted(unknown_postconditions)}"
                )
            if step.action is not None:
                if step.action.output_evidence_requirement_id not in evidence_ids:
                    raise ValueError(
                        f"action '{step.action.manifest_id}' references unknown output evidence"
                    )
                if step.action.postcondition_id not in postcondition_ids:
                    raise ValueError(
                        f"action '{step.action.manifest_id}' references unknown postcondition"
                    )

            for target in step.transitions.values():
                if isinstance(target, StepTransitionTarget) and target.id not in step_ids:
                    raise ValueError(f"step '{step.id}' targets unknown step '{target.id}'")
                if (
                    isinstance(target, TerminalTransitionTarget)
                    and target.outcome not in self.terminal_outcomes
                ):
                    raise ValueError(
                        f"step '{step.id}' targets undefined terminal '{target.outcome}'"
                    )

        for postcondition in self.postconditions:
            unknown_evidence = set(postcondition.evidence_requirement_ids).difference(evidence_ids)
            if unknown_evidence:
                raise ValueError(
                    f"postcondition '{postcondition.id}' references unknown evidence: "
                    f"{sorted(unknown_evidence)}"
                )
            undefined_outcomes = set(postcondition.required_for).difference(self.terminal_outcomes)
            if undefined_outcomes:
                rendered = sorted(outcome.value for outcome in undefined_outcomes)
                raise ValueError(
                    f"postcondition '{postcondition.id}' references undefined outcomes: {rendered}"
                )

    def _validate_field_paths(self, *, input_ids: set[str], evidence_ids: set[str]) -> None:
        paths: set[str] = set()
        if self.eligibility is not None:
            paths.update(self.eligibility.field_paths())
        for rule in self.rules:
            paths.update(rule.predicate.field_paths())
        for evidence in self.evidence_requirements:
            paths.add(evidence.freshness.observed_at)
            paths.add(evidence.valid_time.reference)
        for step in self.steps:
            if step.action is None:
                continue
            paths.update(step.action.input_fields)
            paths.update(step.action.idempotency.key_fields)

        reserved_paths = {
            "tenant.id",
            "actor.id",
            "actor.roles",
            "actor.channel",
            "case.id",
            "case.effective_at",
            "case.opened_at",
            "case.channel",
        }

        def is_declared(path: str) -> bool:
            if path in reserved_paths:
                return True
            if path.startswith("inputs."):
                return path.removeprefix("inputs.") in input_ids
            if path.startswith("evidence."):
                tail = path.removeprefix("evidence.")
                evidence_id = tail.split(".", maxsplit=1)[0]
                return evidence_id in evidence_ids
            return False

        undeclared = sorted(path for path in paths if not is_declared(path))
        if undeclared:
            raise ValueError(f"undeclared field paths: {undeclared}")

    def _validate_graph(self, step_ids: set[str]) -> None:
        step_by_id = {step.id: step for step in self.steps}
        reachable: set[str] = set()
        pending = [self.entrypoint]
        while pending:
            step_id = pending.pop()
            if step_id in reachable:
                continue
            reachable.add(step_id)
            for target in step_by_id[step_id].transitions.values():
                if isinstance(target, StepTransitionTarget):
                    pending.append(target.id)

        unreachable = sorted(step_ids.difference(reachable))
        if unreachable:
            raise ValueError(f"unreachable steps: {unreachable}")

        def can_reach_terminal(step_id: str, visiting: frozenset[str]) -> bool:
            if step_id in visiting:
                return False
            next_visiting = visiting.union({step_id})
            for target in step_by_id[step_id].transitions.values():
                if isinstance(target, TerminalTransitionTarget):
                    return True
                if can_reach_terminal(target.id, next_visiting):
                    return True
            return False

        dead_branches: list[str] = []
        for step in self.steps:
            for event, target in step.transitions.items():
                if isinstance(target, StepTransitionTarget) and not can_reach_terminal(
                    target.id, frozenset()
                ):
                    dead_branches.append(f"{step.id}.{event.value}")
        if dead_branches:
            raise ValueError(f"branches cannot reach a terminal outcome: {sorted(dead_branches)}")

    def _validate_terminal_safety(self) -> None:
        if TerminalOutcome.ESCALATED not in self.terminal_outcomes:
            raise ValueError("terminal_outcomes must define escalated")

        for outcome, definition in self.terminal_outcomes.items():
            if definition.disclosure_id != self.disclosure.id:
                raise ValueError(
                    f"terminal '{outcome}' references unknown disclosure "
                    f"'{definition.disclosure_id}'"
                )

        verified = self.terminal_outcomes.get(TerminalOutcome.VERIFIED)
        if verified is not None:
            if verified.claim_policy is not ClaimPolicy.SUPPORTED_ONLY:
                raise ValueError("verified terminal requires supported_only claims")
            if not verified.requires_all_postconditions:
                raise ValueError("verified terminal requires all postconditions")
            if not any(
                TerminalOutcome.VERIFIED in postcondition.required_for
                for postcondition in self.postconditions
            ):
                raise ValueError("verified terminal requires a declared postcondition")

        clarification = self.terminal_outcomes.get(TerminalOutcome.CLARIFICATION_REQUIRED)
        if (
            clarification is not None
            and clarification.claim_policy is not ClaimPolicy.NO_MATERIAL_CLAIMS
        ):
            raise ValueError("clarification_required cannot emit material claims")

        escalated = self.terminal_outcomes[TerminalOutcome.ESCALATED]
        if not escalated.handoff_required:
            raise ValueError("escalated terminal requires a handoff payload")

    def _validate_risk_tier(self) -> None:
        action_risks = {step.action.risk for step in self.steps if step.action is not None}
        if self.risk_tier is ContractRiskTier.READ_ONLY and action_risks.difference(
            {ActionRisk.READ}
        ):
            raise ValueError("read_only contracts cannot declare write actions")
        if (
            self.risk_tier is ContractRiskTier.REVERSIBLE_WRITE
            and ActionRisk.IRREVERSIBLE_WRITE in action_risks
        ):
            raise ValueError("reversible_write contracts cannot declare irreversible actions")


Predicate.model_rebuild()
ResolutionContract.model_rebuild()


__all__ = [
    "ActionDeclaration",
    "ActionRisk",
    "ClaimPolicy",
    "ConfirmationMode",
    "ContractBudgets",
    "ContractLifecycle",
    "ContractRiskTier",
    "ContractStep",
    "DisclosurePolicy",
    "EffectiveRange",
    "EvidenceFailureAction",
    "EvidenceRequirement",
    "EvidenceSourceKind",
    "IdempotencyStrategy",
    "InputRequirement",
    "InputType",
    "PostconditionDeclaration",
    "Predicate",
    "PredicateOperator",
    "ResolutionContract",
    "RuleDefinition",
    "SafeReference",
    "StepKind",
    "TerminalOutcome",
    "TerminalOutcomeDefinition",
    "TransitionEvent",
]
