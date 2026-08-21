"""Strict authoring contract for deterministic resolution journeys."""

from pathlib import Path
from typing import Any

from resolution.contracts.models import (
    ActionDeclaration,
    ActionRisk,
    ClaimPolicy,
    ConfirmationMode,
    ContractBudgets,
    ContractLifecycle,
    ContractRiskTier,
    ContractStep,
    DisclosurePolicy,
    EffectiveRange,
    EvidenceFailureAction,
    EvidenceRequirement,
    EvidenceSourceKind,
    IdempotencyStrategy,
    InputRequirement,
    InputType,
    PostconditionDeclaration,
    Predicate,
    PredicateOperator,
    ResolutionContract,
    RuleDefinition,
    SafeReference,
    StepKind,
    TerminalOutcome,
    TerminalOutcomeDefinition,
    TransitionEvent,
)
from resolution.contracts.serialization import canonical_contract_json, contract_digest

DEFAULT_JSON_SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "resolution-contract-v0.1.schema.json"
)


def resolution_contract_json_schema() -> dict[str, Any]:
    from resolution.contracts.schema import resolution_contract_json_schema as generate

    return generate()


def resolution_contract_schema_json() -> str:
    from resolution.contracts.schema import resolution_contract_schema_json as generate

    return generate()


def check_schema_snapshot(path: Path = DEFAULT_JSON_SCHEMA_PATH) -> bool:
    from resolution.contracts.schema import check_schema_snapshot as check

    return check(path)


__all__ = [
    "DEFAULT_JSON_SCHEMA_PATH",
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
    "canonical_contract_json",
    "check_schema_snapshot",
    "contract_digest",
    "resolution_contract_json_schema",
    "resolution_contract_schema_json",
]
