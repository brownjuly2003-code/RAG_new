# RAG_new implementation plan

## Goal

Evolve the inherited RAG assistant into a self-hosted, verifiable support-resolution platform without weakening the existing fail-closed runtime or changing production defaults before replay, shadow, and canary evidence exists.

## Tasks

- [x] Freeze provenance and architecture drivers from source commit `bd07179` and `D:\New_steps\rag.md` -> Verify: baseline counts, hotspots, open remediation gates, and source-to-target boundaries are recorded.
- [x] Define the modular-monolith target, deterministic resolution kernel, data ownership, trust boundaries, and failure semantics -> Verify: architecture diagrams and ADRs agree on every component owner.
- [x] Add `ResolutionContract` v0.1 as Pydantic models plus exported JSON Schema and positive/negative fixtures -> Verify: unknown fields and missing safety fields fail validation.
- [x] Add an append-only case/evidence data model behind repository ports -> Verify: Alembic round trip, tenant isolation, immutability rules, and temporal-conflict tests pass.
- [x] Implement one read-only `shipment-status` contract in shadow mode -> Verify: happy, clarify, stale, conflict, timeout, and escalation scenarios have deterministic terminal outcomes.
- [x] Add a pure temporal-knowledge and projection-binding contract -> Verify: bitemporal selection, exact applicability, fail-closed conflicts, tenant/config drift, and rebuild/rollback known cases pass without changing runtime defaults.
- [ ] Persist and integrate temporal knowledge authority -> Verify: revision `029` round trip, forced RLS, immutability/system-close guards, bitemporal exclusion, exact approved identities, and retrieval allowlisting pass on real PostgreSQL.
- [ ] Add the governed action gateway and wrap `create_ticket` as the first reversible/idempotent write -> Verify: retries and disconnects cannot create duplicate side effects; denial never calls the connector.
- [ ] Add scenario compilation, state grading, replay manifests, and VR/VRY reporting -> Verify: deliberately broken policy, evidence, connector, postcondition, and disclosure cases fail the gate.
- [ ] Promote one journey through shadow and canary only after the inherited remediation stream is green -> Verify: rollback, SLO, security, and outcome gates are backed by fresh non-skipped evidence.

## Done when

- [ ] A promoted contract can prove its inputs, policy version, material claims, actions, and postconditions from an exportable evidence bundle.
- [ ] `unverified_auto_rate`, unauthorized writes, duplicate critical writes, and cross-tenant evidence/action access are all zero in the promotion suite.
- [ ] Production release truth remains explicit: mock-only, skipped, stale, or self-judged results never close a gate.

## Notes

The completed schema contract and compatibility policy are documented in
`docs/architecture/resolution-contract-schema-v0.1.md`. Slice C is complete
through C8. C1–C7 delivered the domain/repository boundary, PostgreSQL
persistence, forced tenant RLS, append immutability, temporal exclusion,
protected evidence references, and a real disposable source-to-target restore
smoke. Exact C7 evidence is in `c7-resolution-restore-smoke.md`.

For C8 the owner authorized the Mac target and PostgreSQL role mutations.
Delivery commit `c78da01` records the provisioning contract and evidence. An
isolated PostgreSQL 16 cluster was verified on loopback port `55432`, migrated
to head `028`, with the exact schema-owner/migrator/runtime topology and
minimum Resolution grants documented in `c8-mac-postgres-deployment.md` and
`docs/operations/resolution-postgres-roles.md`. The pre-existing PostgreSQL on
`5432` remains available. C8 did not switch the legacy application
`DATABASE_URL` or enable API/runtime routing.

Slice D is locally complete on an explicitly fixture-backed shadow surface.
It adds tenant-scoped source lookup, bounded typed policy retrieval,
freshness/conflict/claim/postcondition gates, JSON-safe evidence export and an
exact-response legacy compatibility hook. Thirty deterministic/multi-turn
scenario rows and five boundary tests pass; no live source, DB, provider,
legacy router or production setting changed. Domain-owner approval of the
exact source/policy/postcondition identities and applicability semantics is now
recorded for local Slice E work; it is not a live-source connection approval.

E1 is locally complete as a pure-Python temporal knowledge and Chroma manifest
binding contract. It proves half-open valid/system selection, exact typed
applicability, same-source overlap rejection, fail-closed cross-authority
conflicts, exact tenant/manifest/source/config binding, and known-case
rebuild/rollback behavior. It does not add PostgreSQL persistence, migration
`029`, runtime retrieval, live shadow, canary or production grants. E2
PostgreSQL authority/persistence is the next named slice; fixture and E1
evidence do not close release gates.
