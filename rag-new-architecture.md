# RAG_new implementation plan

## Goal

Evolve the inherited RAG assistant into a self-hosted, verifiable support-resolution platform without weakening the existing fail-closed runtime or changing production defaults before replay, shadow, and canary evidence exists.

## Tasks

- [x] Freeze provenance and architecture drivers from source commit `bd07179` and `D:\New_steps\rag.md` -> Verify: baseline counts, hotspots, open remediation gates, and source-to-target boundaries are recorded.
- [x] Define the modular-monolith target, deterministic resolution kernel, data ownership, trust boundaries, and failure semantics -> Verify: architecture diagrams and ADRs agree on every component owner.
- [ ] Add `ResolutionContract` v0.1 as Pydantic models plus exported JSON Schema and positive/negative fixtures -> Verify: unknown fields and missing safety fields fail validation.
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

The next named implementation slice is **Resolution Contract schema v0.1**. Domain-owner approval of journey postconditions and access to a real shipment source of truth remain product prerequisites, not details for the LLM to infer.
