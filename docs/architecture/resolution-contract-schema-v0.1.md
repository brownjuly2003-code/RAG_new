# Resolution Contract schema v0.1

- Status: Implemented and frozen for Slice B
- Schema identity: `resolution-contract/v0.1`
- JSON Schema: `resolution/contracts/schemas/resolution-contract-v0.1.schema.json`
- Positive fixture: `tests/fixtures/resolution_contracts/v0.1/valid/shipment-status.json`

## Contract boundary

`ResolutionContract` is a strict authoring and static-validation boundary. It
does not execute a contract, publish a version, access a database, call a
provider, or route production traffic. Runtime code must first validate the
payload and then use its canonical JSON identity.

The v0.1 model fails closed when:

- the payload or a nested model contains an unknown field;
- schema or contract versions are malformed;
- a predicate uses an operator outside the closed allowlist;
- a predicate, action, freshness rule, or idempotency key references an
  undeclared input or evidence path;
- evidence omits freshness, valid-time, missing, stale, or conflict behavior;
- a step has the wrong branch set, targets an unknown node, is unreachable, or
  cannot reach a declared terminal outcome;
- a write lacks confirmation, idempotency, reconciliation, scopes, timeout, or
  a deterministic postcondition;
- a checker or manifest reference resembles a dynamic import path;
- a budget is absent, non-finite, or outside the v0.1 ceiling; or
- `verified`, clarification, escalation, disclosure, or handoff safety rules
  are inconsistent.

The predicate vocabulary is data only: `all`, `any`, `not`, `eq`, `in`,
`exists`, `lt`, `lte`, `gt`, `gte`, `date_before`, `date_after`, and
`range_contains`. There is no `eval`, generated Python, template execution,
dynamic import, arbitrary regex, SQL fragment, or network lookup in contract
validation.

## Canonical identity

Canonicalization happens only after successful Pydantic validation:

1. dump in JSON mode with field aliases, explicit nulls, and model defaults;
2. sort every object key;
3. encode UTF-8 without ASCII escaping or insignificant whitespace;
4. reject non-finite numbers; and
5. calculate SHA-256 over those exact bytes.

Equivalent authoring key order and whitespace therefore produce the same
digest. A changed validated value, default, enum, or canonicalization rule
changes the digest. Published versions store both semantic version and digest;
the digest does not replace human approval or durable immutability controls.

## Schema and fixture checks

The committed JSON Schema is a generated snapshot of the validation model.

```powershell
python -m resolution.contracts.schema --check
python -m pytest tests\test_resolution_contract_schema.py -q
```

The first command exits nonzero when the snapshot differs from the model. The
positive shipment fixture pins a canonical digest. Negative fixtures are
RFC 6902-style patches over that positive payload so every unsafe mutation is
small and reviewable; they cover unknown fields/operators, missing conflict
handling, invalid versions, unbounded budgets, undeclared paths, unreachable
steps, unsafe writes, and dynamic checker references.

## Compatibility policy

- The committed v0.1 schema snapshot is the compatibility authority.
- Published contract payloads are immutable. A content correction creates a
  new contract semantic version and digest.
- Any change to required fields, accepted types, constraints, enum values,
  predicate meaning, graph rules, safety validation, defaults, or canonical
  serialization requires a new schema identity such as
  `resolution-contract/v0.2`.
- An implementation fix may retain v0.1 only when it accepts and rejects the
  same payloads, emits the same schema snapshot, and preserves canonical bytes.
- Readers reject unknown schema identities and unknown fields; they do not
  silently downgrade, coerce, or ignore them.
- Database publication, adapter/checker registry resolution, signed approval,
  and effective-range collision checks belong to later slices and cannot be
  inferred from successful v0.1 authoring validation alone.
