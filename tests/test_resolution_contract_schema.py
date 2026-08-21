from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from resolution.contracts import (
    DEFAULT_JSON_SCHEMA_PATH,
    ContractLifecycle,
    PredicateOperator,
    ResolutionContract,
    TerminalOutcome,
    canonical_contract_json,
    contract_digest,
    resolution_contract_schema_json,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "resolution_contracts" / "v0.1"
VALID_FIXTURE = FIXTURE_ROOT / "valid" / "shipment-status.json"
EXPECTED_DIGEST = FIXTURE_ROOT / "valid" / "shipment-status.sha256"
INVALID_FIXTURE_ROOT = FIXTURE_ROOT / "invalid"


def _valid_payload() -> dict[str, Any]:
    return json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))


def _apply_json_patch(payload: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(payload)
    for operation in operations:
        parts = [
            part.replace("~1", "/").replace("~0", "~") for part in operation["path"].split("/")[1:]
        ]
        parent: Any = patched
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]

        leaf = parts[-1]
        match operation["op"]:
            case "add":
                if isinstance(parent, list):
                    if leaf == "-":
                        parent.append(operation["value"])
                    else:
                        parent.insert(int(leaf), operation["value"])
                else:
                    parent[leaf] = operation["value"]
            case "remove":
                if isinstance(parent, list):
                    parent.pop(int(leaf))
                else:
                    del parent[leaf]
            case "replace":
                if isinstance(parent, list):
                    parent[int(leaf)] = operation["value"]
                else:
                    parent[leaf] = operation["value"]
            case unsupported:
                raise AssertionError(f"unsupported fixture patch operation: {unsupported}")
    return patched


def test_valid_contract_fixture_has_stable_canonical_digest() -> None:
    contract = ResolutionContract.model_validate_json(VALID_FIXTURE.read_text(encoding="utf-8"))

    canonical = canonical_contract_json(contract)
    reparsed = ResolutionContract.model_validate_json(canonical)

    assert contract.id == "aircargo.shipment-status"
    assert contract.version == "0.1.0"
    assert canonical_contract_json(reparsed) == canonical
    assert contract_digest(contract) == EXPECTED_DIGEST.read_text(encoding="ascii").strip()


def test_exported_json_schema_matches_the_model_snapshot() -> None:
    generated = resolution_contract_schema_json()

    assert DEFAULT_JSON_SCHEMA_PATH.read_text(encoding="utf-8") == generated
    schema = json.loads(generated)
    assert schema["$id"] == "https://rag-new.local/schemas/resolution-contract/v0.1"
    assert schema["additionalProperties"] is False
    object_definitions = [
        definition
        for definition in schema["$defs"].values()
        if definition.get("type") == "object" and "properties" in definition
    ]
    assert object_definitions
    assert all(definition.get("additionalProperties") is False for definition in object_definitions)


def test_contract_vocabulary_is_closed_and_versioned() -> None:
    assert {operator.value for operator in PredicateOperator} == {
        "all",
        "any",
        "not",
        "eq",
        "in",
        "exists",
        "lt",
        "lte",
        "gt",
        "gte",
        "date_before",
        "date_after",
        "range_contains",
    }
    assert [state.value for state in ContractLifecycle] == [
        "draft",
        "validated",
        "simulated",
        "approved",
        "published",
        "superseded",
        "retired",
    ]
    assert {outcome.value for outcome in TerminalOutcome} == {
        "verified",
        "partial",
        "clarification_required",
        "escalated",
        "failed",
        "cancelled",
    }


@pytest.mark.parametrize(
    "fixture_path",
    sorted(INVALID_FIXTURE_ROOT.glob("*.patch.json")),
    ids=lambda path: path.stem.removesuffix(".patch"),
)
def test_negative_contract_fixtures_fail_closed(fixture_path: Path) -> None:
    negative_fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload = _apply_json_patch(_valid_payload(), negative_fixture["operations"])

    with pytest.raises(ValidationError) as exc_info:
        ResolutionContract.model_validate(payload)

    assert negative_fixture["expected_error"] in str(exc_info.value).lower()


def test_negative_fixture_inventory_covers_static_safety_failures() -> None:
    assert {path.name for path in INVALID_FIXTURE_ROOT.glob("*.patch.json")} == {
        "dynamic-checker-reference.patch.json",
        "invalid-version.patch.json",
        "missing-conflict-handling.patch.json",
        "unbounded-budget.patch.json",
        "undeclared-field-reference.patch.json",
        "unknown-field.patch.json",
        "unknown-operator.patch.json",
        "unreachable-branch.patch.json",
        "unsafe-write.patch.json",
    }
