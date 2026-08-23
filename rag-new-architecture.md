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
- [x] Persist and integrate temporal knowledge authority -> Verify: revision `029` round trip, forced RLS, immutability/system-close guards, bitemporal exclusion, exact approved identities, and retrieval allowlisting pass on real PostgreSQL.
- [x] Add the governed action gateway and wrap `create_ticket` as the first reversible/idempotent write -> Delivered locally at `ed82d6a`; retries and disconnects cannot create duplicate side effects, and denial never calls the connector.
- [x] Add scenario compilation, state grading, replay manifests, and synthetic VR/VRY reporting -> G1 through G6 are locally complete, including a full-corpus exact-bound comparison. Full Slice G remains open only beyond this local synthetic contract.
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
rebuild/rollback behavior.

E2 is locally complete on disposable PostgreSQL. Revision `029` persists the
contract in exactly six new tenant-owned tables with forced RLS,
append/system-close guards and bitemporal exclusion. The repository and
application seam authorize only exact persisted versions bound to the current
projection; the legacy retrieval adapter applies that allowlist without
switching production routing. Head `029`, 23 ORM tables and the exact 29-table
public restore inventory are verified.

Slice F is locally complete at `ed82d6a`. It delivers the governed action
domain/gateway, PostgreSQL revision `030` with eight action tables, and the
isolated ticket adapter without switching the runtime route or invoking an
external connector.

G1 is locally complete in the scoped commit containing its status docs. The
pure evaluator compiles the pinned 6-step shipment contract into 22 stable
contract-bound targets, hides expected paths/state from candidate generation,
grades exact terminal state, and fails closed on evaluator error/skip. This is
not runtime execution of all edges or release evidence.

G2 is locally complete in the scoped commit containing its status docs. Its
pure offline immutable manifest pins code, global evaluator identities,
versioned SHA256 dependencies, and digested scenario compartments without raw
candidate/world/fault/hidden data. Baseline-versus-candidate comparison selects
known dependency impact narrowly, global impact fully, and structural,
membership, or unexplained drift fully fail closed. The report has no replay
outcome, promotion/release verdict, or business-metric semantics.

G3 is locally complete in the scoped commit containing this update; resolve its
exact SHA from Actual Git. The manifest/impact-bound callback executor records
exactly three deterministic derived-seed trials per planned scenario as
immutable canonical hashes.
Structural failures remain explicit `ERROR` evidence; fixed fail-closed
denominators define `pass^1` over `3 * N` planned trials and `pass^3` over `N`
planned scenarios. Raw candidate/world/fault/hidden/response payloads remain
compartmentalized outside canonical records.

G4 is locally complete in the scoped commit containing this update; resolve its
exact SHA from Actual Git. It adds an immutable versioned synthetic
persona/adversarial/fault corpus, derives branch coverage from revalidated
hidden contract paths, fixes denominators at all 22 pinned branches and seven
required fault surfaces, and credits coverage only for exact manifest and
scenario bindings. A privacy-safe canonical snapshot and SHA guard contain no
raw candidate/world/fault/oracle/response payload.

G5 is locally complete in the scoped commit containing its update; resolve its
exact SHA from Actual Git. Its immutable versioned case ledger binds exact
manifest, corpus, structural coverage, full replay plan/result, scenario and
three-trial identities. Deterministic VR precision, VRY, and eligibility
coverage use conservative fixed-denominator accounting. Only an eligible,
claimed-auto case with all seven provisional VR checks and all three replay
trials passing receives verified credit. Definitions remain owner-unconfirmed,
synthetic-only, and explicitly non-business-claimable.

G6 is locally complete in the scoped commit containing this update; resolve its
exact SHA from Actual Git. Two versioned inputs embed the same provisional
metric definition and complete 17-case corpus identity while retaining
different exact manifest, coverage, replay-plan, replay-result, ledger, and
report identities. Their deterministic comparison emits only count-pair deltas
and an exhaustive case-disposition transition partition. Checked-in canonical
JSON/SHA-256 artifacts exclude raw candidate/world/fault/oracle/response data.

The materialized numbers are constructed synthetic contract evidence, not
measured candidate performance: VR precision changes from `0/1` to `1/2`, VRY
from `0/17` to `1/17`, and eligibility coverage remains `17/17`. No rate delta,
threshold, success, release, or promotion verdict is produced.

Full Slice G remains open beyond the local synthetic contract. Runtime/live
shadow outcomes, owner-approved definitions and thresholds, observed recontact,
latency/cost, confidence bounds, canary, promotion, external connector, deploy,
and push require separate authority. No next local G slice is auto-selected.
