# Resolution contracts

This folder is a portable snapshot of the shipment-status `ResolutionContract`
used by RAG_new. A reviewer can inspect the JSON Schema and two complete
contract examples without starting the application. The contracts describe a
deterministic journey: required inputs, evidence, policy checks, steps, claims,
and terminal outcomes. They are not the `/api/ask` HTTP response schema.

| File | What it shows |
|---|---|
| [`schemas/resolution-contract-v0.1.schema.json`](schemas/resolution-contract-v0.1.schema.json) | Structural JSON Schema exported from the runtime `ResolutionContract` model. |
| [`fixtures/shipment-status-v0.1.json`](fixtures/shipment-status-v0.1.json) | Read-only shipment-status contract `0.1.0`, used by the legacy shadow journey. |
| [`fixtures/shipment-status-response-v0.2.json`](fixtures/shipment-status-response-v0.2.json) | Contract `0.2.0`, with response shape `1.0.0` binding status, location, and estimated delivery to claims and evidence. |

Both examples use `schema_version: "resolution-contract/v0.1"`. That identifies
the structure of the authoring format; each example's `version` identifies the
journey contract. The response-shaped variant is enabled only when the shadow
and response journey flags are both set. Both variants use a fixture TMS, not
real shipment data.

## Validation

Use a JSON Schema Draft 2020-12 validator to check either fixture against the
schema. Schema validation covers field types, required fields, enumerations,
and unknown fields. The runtime Pydantic model additionally checks references,
the step graph, and terminal safety; a schema-only pass does not establish
those conditions.

From the repository root, with the project's development dependencies installed:

```text
python -m resolution.contracts.schema --check
python -m pytest tests/test_resolution_contract_schema.py tests/test_resolution_contracts_bundle.py -q -p no:schemathesis
```

The first command checks the generated runtime schema. The tests validate both
examples with JSON Schema and the runtime model, and require this folder to
match the runtime files byte for byte. When a contract changes, update the
runtime source first, then refresh this snapshot and run those checks.

The [contract-shaped answer evidence](../docs/evidence/c3-contract-shaped-response.md)
explains how the optional `0.2.0` variant projects a supported answer. The
[negative fixtures](../tests/fixtures/resolution_contracts/v0.1/invalid/)
exercise safety rules enforced by the runtime model. The repository's
[OpenAPI schema](../README.md#main-runtime-surfaces) documents HTTP endpoints.
