# RAG_new migration and delivery architecture

- Status: Active architecture plan
- Last updated: 2026-08-22
- Strategy: compatibility-preserving strangler with shadow-first promotion

## 1. Starting point

`RAG_new` begins from source commit `bd071793258391408ed7d3b41883246f0b24bae2`. The inherited runtime already supplies FastAPI, LangGraph, hybrid retrieval/reranking, provider routing, citations, multi-tenancy, durable ingestion/escalation work, evaluation, and observability. It also carries an explicit active remediation plan: production release is not complete.

The migration therefore has two visible streams:

- **Trust Foundation:** finish inherited bounded execution, canonical sync/SSE, fail-closed grounding/judge/evaluation, index lifecycle, live storage/restore, security, SLO, and rollout evidence.
- **Resolution Product:** build contracts, case/evidence state, temporal knowledge, governed actions, state grading, replay, and operator workflows in shadow mode.

Resolution work may start before every live deployment gate closes, but no controlled write or production promotion may hide or bypass a required Trust Foundation gate.

## 2. Source-to-target ownership map

| Inherited area | Reuse | New boundary | Migration rule |
|---|---|---|---|
| `api/app.py`, `api/routers/*` | Auth, middleware, current endpoints, lifecycle | Case and contract routers call application commands/queries | Routers stay thin; SSE projects persisted events. |
| `agent/state.py`, `agent/graph.py` | Current reasoning/retrieval/generation behavior | `ReasoningPort` with typed bounded tasks | Do not add case/action/policy state to `GraphState`. |
| `services/pipeline.py` | Capacity/orphan-work lifecycle | Bounded reasoning adapter and worker bulkhead | Cooperative deadline/budget remains Trust Foundation work. |
| `agent/tools.py` | KB search and ticket behavior as migration inputs | Action manifests/gateway/connectors | No production connector is exposed directly as an LLM tool. |
| `vectordb/*` | Hybrid + reranker + index manifest baseline | Temporal eligibility and projection manifest binding | Preserve current default; no GraphRAG/vector-store switch without evidence. |
| `ingestion/*`, upload/jobs | Loaders, versioned job/index work | Knowledge object/version/authority metadata | Business validity lives in PostgreSQL, not vector metadata alone. |
| `db/models.py`, Alembic | SQLAlchemy/PostgreSQL conventions | New contract/case/evidence/policy/action/outcome tables | New tenant tables get ownership FKs and RLS tests. |
| `services/escalation.py`, Bitrix/inbox | Durable idempotent escalation seam | First governed reversible write | Wrap behavior; preserve existing endpoint response until compatibility tests pass. |
| `evaluation/*` | Retrieval/text baselines and regression mechanics | `evaluation/resolution/*` state graders/replay | Existing quality metrics remain floors, not north-star outcome. |
| `tracing/*`, `monitoring/*` | Correlation, OTel, Prometheus | Resolution identities/metrics with redaction | Do not copy raw evidence/tool payloads into telemetry. |
| `static/*`, templates | Existing user/agent/admin surfaces | Case/evidence/contract views | Add minimal pilot UI; no frontend rewrite before verified pilot. |

## 3. Delivery slices

### Slice A — Architecture foundation (complete in this checkout)

Deliverables are the project clone, independent repository boundary, architecture index, system/data/security/migration documents, ADRs, and short root plan.

Verification: source provenance and counts are recorded; architecture links resolve; decisions agree on ownership, state, data, and failure semantics; project runtime is unchanged.

### Slice B — Resolution Contract schema v0.1 (complete)

Add strict Pydantic authoring models, exported JSON Schema, canonical serialization/digest, closed predicate AST, lifecycle enums, and fixtures. No database or runtime routing yet.

Verification:

- positive fixture validates and has stable canonical digest;
- unknown fields, invalid versions, unbounded budgets, unreachable branches, missing conflict handling, and unsafe write declarations fail;
- referenced safe operators are allowlisted; no `eval`/dynamic import path exists;
- schema snapshot and compatibility policy are documented.

### Slice C — Case and evidence persistence (complete)

Add domain entities, ports, PostgreSQL models/migrations, append-only events, optimistic versioning, repository adapters, tenant RLS, and a protected evidence reference abstraction.

Verification: domain tests require no infrastructure; PostgreSQL migration round trip, concurrency conflict, append immutability, tenant isolation/RLS, encryption/redaction, and restore smoke pass. SQLite-only evidence cannot close the slice.

Delivery status:

- **C1 complete locally:** stdlib-only immutable `SupportCase`, `CaseEvent`,
  protected `EvidenceSnapshot`/link/conflict types, optimistic transition
  mutations, and tenant-scoped append-only repository/unit-of-work ports.
- **C2 complete locally:** PostgreSQL models, revision `024`, and repository
  adapters with atomic event append plus compare-and-swap passed a real
  PostgreSQL round trip, stale-writer conflict, transaction rollback, and
  application-level tenant-negative contracts.
- **C3 complete locally:** revision `025` enables and forces tenant RLS on all
  four C2 tables; transaction-local context, default deny, own-tenant
  read/write, and cross-tenant negatives passed under a non-owner,
  non-`BYPASSRLS` role.
- **C4 complete locally:** revision `026` adds DB-level `UPDATE`/`DELETE`
  immutability guards for append-only events, evidence snapshots, and
  case/evidence links while preserving legal `SupportCase` compare-and-swap
  updates.
- **C5 complete locally (`98c2f09`):** revision `027` and matching
  PostgreSQL-only ORM metadata reject overlapping `[valid_from, valid_to)`
  windows for the same tenant/logical key/applicability/authority while
  accepting adjacency,
  cross-authority, and different-applicability windows.
- **C6 complete locally (`ac8e5bc`):** revision
  `028` encrypts only `evidence_snapshots.reference_locator` through the
  existing `EncryptedText`/`DB_ENCRYPTION_KEY` contract, durable storage
  accepts only `tenant-envelope-v1`, and the `customer-safe-v1` boundary
  emits only `id`, `digest`, `visibility`, and `profile`; unknown,
  restricted, and support-only paths fail closed without a locator. Closing
  evidence is recorded in
  [`../../c6-protected-evidence-encryption-redaction.md`](../../c6-protected-evidence-encryption-redaction.md).
- **C7 complete locally (`f1103bb`):** the restore verifier now compares the exact head
  inventory (**17 ORM + 5 migration-owned + `alembic_version` = 23 tables**)
  and fails closed on missing or extra tables. A real PostgreSQL 14 disposable
  source-to-target custom-format restore preserved representative Resolution
  data, encrypted locator behavior, RLS, append guards, temporal exclusion,
  and the protection constraint. Closing evidence is recorded in
  [`../../c7-resolution-restore-smoke.md`](../../c7-resolution-restore-smoke.md).
- **C8 complete on the authorized Mac target (`c78da01`):** a dedicated
  PostgreSQL 16
  cluster runs only on `127.0.0.1:55432`, separately from the existing service
  on `5432`. Database `ragnew_prod` is at head `028`; schema-owner, migrator,
  and direct runtime identities match the exact no-admin/no-inherit/non-owner
  contract. Runtime has only Resolution table/column/function grants. Exact
  RLS policy expressions, current and default ACLs, role settings, tenant
  negatives, append guard, revoke/restore, and restart persistence passed.
  Closing evidence is in
  [`../../c8-mac-postgres-deployment.md`](../../c8-mac-postgres-deployment.md)
  and the operator contract is in
  [`../operations/resolution-postgres-roles.md`](../operations/resolution-postgres-roles.md).
- Slice C is complete. This is not a full production/release-ready claim: C8
  did not switch the legacy application DSN or enable Resolution API/runtime
  routing.

### Slice D — Read-only shipment-status shadow loop

Implement one contract and adapters for a fixture/approved shipment source, existing retrieval, typed policy rules, freshness/conflict checks, response compilation, and evidence export. Run beside `/api/ask`; do not alter its response.

Required scenarios include happy path, missing shipment ID, unknown shipment, stale source result, conflicting policy, wrong tenant, provider timeout, retrieval empty, unsupported claim, and complete escalation brief.

Verification: at least 30 deterministic and multi-turn cases have explicit terminal state; every verified result has contract, source observation, policy, claim links, and postcondition versions; legacy behavior is unchanged.

Local delivery status (2026-08-22): complete on the explicitly fixture-backed
shadow surface. The implementation provides tenant-scoped source lookup,
bounded typed retrieval, deterministic freshness/conflict/policy/claim checks,
response compilation, version-pinned evidence export, and an isolated hook
that returns the exact legacy response object even when shadow observation
fails. The gate contains 30 deterministic/multi-turn scenario rows and 5
boundary tests; the final adjacent Resolution batch passed 65 tests. No live
source, database, provider, `/api/ask` router, or production setting changed.
Owner-approved source/postcondition/policy inputs and production shadow
registration remain promotion prerequisites, so this status is not live or
release-ready evidence.

### Slice E — Temporal knowledge projection

Add one authoritative knowledge source with valid/system ranges, applicability, authority, supersession, conflict records, and Chroma projection manifest binding.

Verification: queries before/after a policy change select the correct version; within-source overlap is rejected; cross-authority conflict is represented and fails closed; projection rebuild/rollback preserves known cases.

Delivery status (2026-08-22): **E1 pure contract complete locally.** The owner
approved `logistics-policy-primary` as the knowledge-source identity,
`shipment-source-primary` as the observation identity,
`shipment-observation-current` as the pinned postcondition, exact typed
applicability, and conflict-before-authority fail-closed semantics without
ranking. The stdlib-only domain implements half-open valid/system selection,
ownership, supersession/conflict and within-source overlap invariants. The
projection contract binds exact tenant, active Chroma collection/generation,
ordered knowledge version/content digests and embedding/index configuration;
runtime context drift fails closed. Legacy manifest schema v1 is unchanged.
Focused QA passed 20 tests after one batch fix; the independent adjacent gate
passed 67 tests plus Ruff/format/strict MyPy.

**E2 remains open:** add the six PostgreSQL knowledge tables and revision
`029`, composite tenant FKs, forced RLS/default deny, append-only and single
system-close guards, bitemporal exclusion, durable conflict/projection
records, repository/application adapters, exact approved identity enforcement
and Chroma eligible-version allowlisting. Real PostgreSQL
`028 -> 029 -> 028 -> 029`, tenant, RLS, immutability and exclusion evidence is
required. E1 changed no DB, Mac runtime, legacy routing, live source, provider,
production grants or deployment.

### Slice F — Governed ticket/escalation action

Add manifests, registry, PDP binding, confirmation model, action run/attempt/outbox records, worker lease, reconciliation, postcondition, and kill switches. Wrap existing `create_ticket`/escalation as the first reversible/idempotent write.

Verification: denial never invokes connector; same key and canonical input return one action; same key with different input conflicts; timeout/disconnect/worker restart create no duplicate; source-system ticket identity is verified; compensation is independently governed.

### Slice G — Simulator, replay, and release control

Compile contract branches into coverage targets, add deterministic state graders, personas, adversarial/fault cases, repeated trials, release manifests, impact selection, VR precision/VRY/coverage/recontact/cost reports, shadow comparison, and canary controls.

Verification: intentionally broken contract, policy, retriever, connector, postcondition, disclosure, and evaluator infrastructure each fail the release gate. Candidate generation cannot read hidden expected state.

### Slice H — Operator surfaces and pilot

Expose supervisor case/evidence/action/reconciliation views, contract lifecycle/replay diffs, and knowledge conflict queues. Run shadow, then read-only canary for one tenant; write remains confirmed.

Verification: measured outcome and safety gates, tested rollback, zero critical tenancy/policy/action incidents, and domain-owner sign-off on postconditions. Only then consider a second journey/domain.

## 4. Compatibility strategy

The migration uses ports and dual observation, not dual side effects.

- Existing endpoints remain the customer-visible baseline until a versioned case API is promoted.
- Shadow execution may read the same normalized request but cannot answer, mutate external systems, or alter legacy history.
- Shadow results are stored under a separate mode/release manifest and compared offline.
- A controlled-write candidate never runs in parallel with a legacy writer for the same logical operation.
- Feature gates key on environment, tenant, journey, contract version, and risk tier.
- The same terminal result feeds sync and SSE projections; parity does not generate a second answer.

## 5. Test architecture

| Level | Runs with | Proves |
|---|---|---|
| Domain unit | Pure Python, fake clock/ports | State transitions, predicates, invariants, canonical digests. |
| Schema/contract | Pydantic/JSON Schema fixtures | Authoring safety and compatibility. |
| Repository | Real PostgreSQL | Constraints, RLS, locking/versioning, migrations. |
| Adapter contract | Recorded/fake source plus schema | Connector mapping, redaction, idempotency, reconciliation. |
| Deterministic scenario | Fixed world state, no candidate access to expected state | Correct path and terminal business state. |
| Multi-turn/repeated | Bounded LLM/provider profiles | Clarification and non-deterministic reliability. |
| Adversarial/fault | Injection, tenant edges, timeouts, partial state | Fail-closed safety and recovery. |
| Replay/shadow | Versioned anonymized cases | Outcome comparison without side effects. |
| Canary/live | One approved tenant/journey | Production integration, SLO, rollback, and real outcome. |

The inherited retrieval regression remains a safety floor. Resolution tests add state and policy truth; they do not replace context precision/recall, faithfulness, citation, and provider gates.

## 6. Rollback strategy

- Code/config: disable the tenant/journey feature gate and return traffic to the inherited path.
- Contract: stop new case selection, retain pinned versions for in-flight/replay cases, publish a corrected version rather than mutate history.
- Policy: activate the previous signed/reviewed revision and record the rollback decision.
- Knowledge: roll back the projection manifest while retaining knowledge-version audit records.
- Connector: activate the action/tenant kill switch, drain dispatch, reconcile unknown runs, then roll back the manifest/adapter.
- Database: prefer forward correction after data-bearing migrations; downgrade is exercised on disposable databases and used only when its data-loss semantics are explicitly accepted.

Rollback is incomplete while an irreversible or unknown action remains unreconciled.

## 7. Architecture acceptance checklist

- [x] Product unit, first wedge, first read-only journey, and non-goals are explicit.
- [x] Deterministic versus probabilistic ownership is explicit.
- [x] Durable stores, projections, temporal model, tenancy, and retention are explicit.
- [x] Action authorization, confirmation, idempotency, ambiguous outcomes, reconciliation, and postconditions are explicit.
- [x] Failure modes, observability identities, promotion gates, and rollback are explicit.
- [x] Existing hotspots and compatibility seams are mapped.
- [ ] Domain owner confirms journey eligibility, authoritative systems, policy hierarchy, and postconditions.
- [ ] Security/operations confirm credential, RLS, retention, backup/restore, and connector deployment model.
- [ ] Product owner confirms VR/VRY definitions, eligible denominator, and recontact window.

## 8. First milestone success criteria

The first milestone is a **read-only shipment-status resolution loop in shadow mode**, not a redesigned chat UI. It is successful when one versioned case can be replayed from immutable identities, a deterministic grader distinguishes a correct end state from a fluent wrong answer, temporal conflict fails closed, every material response claim has valid evidence, and legacy production behavior remains unchanged.
