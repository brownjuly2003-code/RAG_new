from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from resolution.contracts import ResolutionContract, resolution_contract_schema_json

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "resolution-contracts"
CONTRACTS = ROOT / "resolution" / "contracts"


def test_bundle_schema_matches_the_runtime_model() -> None:
    published = (BUNDLE / "schemas" / "resolution-contract-v0.1.schema.json").read_text(
        encoding="utf-8"
    )

    assert published == resolution_contract_schema_json()
    assert published == (CONTRACTS / "schemas" / "resolution-contract-v0.1.schema.json").read_text(
        encoding="utf-8"
    )
    Draft202012Validator.check_schema(json.loads(published))


@pytest.mark.parametrize(
    ("published_name", "source_name", "version", "has_response_shape"),
    [
        ("shipment-status-v0.1.json", "shipment-status.json", "0.1.0", False),
        ("shipment-status-response-v0.2.json", "shipment-status-response.json", "0.2.0", True),
    ],
)
def test_bundle_examples_match_valid_runtime_contracts(
    published_name: str,
    source_name: str,
    version: str,
    has_response_shape: bool,
) -> None:
    published = (BUNDLE / "fixtures" / published_name).read_text(encoding="utf-8")
    source = (CONTRACTS / "versions" / "v0.1" / source_name).read_text(encoding="utf-8")

    assert published == source
    contract = ResolutionContract.model_validate_json(published)
    assert contract.version == version
    assert (contract.response_shape is not None) is has_response_shape
    schema = json.loads((BUNDLE / "schemas" / "resolution-contract-v0.1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(json.loads(published))
