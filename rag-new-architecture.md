# RAG_new implementation plan

## Goal

Evolve the inherited RAG assistant into a self-hosted, verifiable support-resolution platform without weakening the existing fail-closed runtime or changing production defaults before replay, shadow, and canary evidence exists.

## Tasks

- [x] Freeze provenance and architecture drivers from source commit `bd07179` and `D:\New_steps\rag.md` -> Verify: baseline counts, hotspots, open remediation gates, and source-to-target boundaries are recorded.
- [x] Define the modular-monolith target, deterministic resolution kernel, data ownership, trust boundaries, and failure semantics -> Verify: architecture diagrams and ADRs agree on every component owner.
- [x] Add `ResolutionContract` v0.1 as Pydantic models plus exported JSON Schema and positive/negative fixtures -> Verify: unknown fields and missing safety fields fail validation.
- [x] Add an append-only case/evidence data model behind repository ports -> Verify: Alembic round trip, tenant isolation, immutability rules, and temporal-conflict tests pass.
- [ ] Implement one read-only `shipment-status` contract in shadow mode -> Verify: happy, clarify, stale, conflict, timeout, and escalation scenarios have deterministic terminal outcomes.
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
`DATABASE_URL` or enable API/runtime routing. Slice D is the next architecture
slice on a future turn; domain-owner approval of journey postconditions and an
approved shipment source of truth remain product prerequisites, not details
for the LLM to infer.
