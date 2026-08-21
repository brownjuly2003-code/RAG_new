# RAG_new migration and delivery architecture

- Status: Active architecture plan
- Last updated: 2026-08-21
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

### Slice C — Case and evidence persistence (next)

Add domain entities, ports, PostgreSQL models/migrations, append-only events, optimistic versioning, repository adapters, tenant RLS, and a protected evidence reference abstraction.

Verification: domain tests require no infrastructure; PostgreSQL migration round trip, concurrency conflict, append immutability, tenant isolation/RLS, encryption/redaction, and restore smoke pass. SQLite-only evidence cannot close the slice.

### Slice D — Read-only shipment-status shadow loop

Implement one contract and adapters for a fixture/approved shipment source, existing retrieval, typed policy rules, freshness/conflict checks, response compilation, and evidence export. Run beside `/api/ask`; do not alter its response.

Required scenarios include happy path, missing shipment ID, unknown shipment, stale source result, conflicting policy, wrong tenant, provider timeout, retrieval empty, unsupported claim, and complete escalation brief.

Verification: at least 30 deterministic and multi-turn cases have explicit terminal state; every verified result has contract, source observation, policy, claim links, and postcondition versions; legacy behavior is unchanged.

### Slice E — Temporal knowledge projection

Add one authoritative knowledge source with valid/system ranges, applicability, authority, supersession, conflict records, and Chroma projection manifest binding.

Verification: queries before/after a policy change select the correct version; within-source overlap is rejected; cross-authority conflict is represented and fails closed; projection rebuild/rollback preserves known cases.

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
