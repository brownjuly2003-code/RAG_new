# RAG_new implementation plan

## Goal

Evolve the inherited RAG assistant into a self-hosted, verifiable support-resolution platform without weakening the existing fail-closed runtime or changing production defaults before replay, shadow, and canary evidence exists.

## Tasks

- [x] Freeze provenance and architecture drivers from source commit `bd07179` and `D:\New_steps\rag.md` -> Verify: baseline counts, hotspots, open remediation gates, and source-to-target boundaries are recorded.
- [x] Define the modular-monolith target, deterministic resolution kernel, data ownership, trust boundaries, and failure semantics -> Verify: architecture diagrams and ADRs agree on every component owner.
- [x] Add `ResolutionContract` v0.1 as Pydantic models plus exported JSON Schema and positive/negative fixtures -> Verify: unknown fields and missing safety fields fail validation.
- [ ] Add an append-only case/evidence data model behind repository ports -> Verify: Alembic round trip, tenant isolation, immutability rules, and temporal-conflict tests pass.
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
`docs/architecture/resolution-contract-schema-v0.1.md`. Slice C is active:
C1–C7 are complete locally through C7 commit `f1103bb`. This includes the
domain/repository boundary, PostgreSQL persistence, forced tenant RLS, append
immutability, temporal exclusion, protected evidence references, and a real
disposable source-to-target restore smoke. Exact C7 evidence is in
`c7-resolution-restore-smoke.md`.

The root checkbox stays open only for **C8 production runtime-role
operations/grants**. C8 is externally gated: a generic continuation request
does not authorize production mutation. The owner must identify the target
environment and explicitly authorize role/grant changes, confirm ownership,
the minimum grant matrix, maintenance window, and rollback/revoke owner. Until
then, do not select Slice D, runtime/API wiring, or an inherited backlog item
as a substitute. Domain-owner approval of journey postconditions and access
to a real shipment source of truth remain later product prerequisites, not
details for the LLM to infer.
