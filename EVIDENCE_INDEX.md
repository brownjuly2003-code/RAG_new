# Evidence index

One row per slice. The capsule is the *record*; the *evidence* is the test or
the number it points at. A slice with no test and no published number is not
on this list.

**Evidence class** says what the claim rests on:

- `synthetic` — fixtures the project wrote for itself. Proves the mechanism
  works; proves nothing about the domain.
- `agent_labelled` — cases the agent labelled and no human has approved
  (ADR 0008's fallback for phase B). It is a proposal, not evidence.
- `real_labelled` — cases labelled from real air-cargo data by a human.
  **Nothing carries this class yet.** Phase B is the work of earning it.
- `measured` — a number produced by a run that actually happened, with
  provenance (corpus SHA + code SHA + config).

## Rule for adding a row

New evidence is a test plus one row here. Not a new capsule file in the repo
root — that habit is what produced 29 of them and is now closed.

## Slices

| Slice | Capsule | Evidence class |
|---|---|---|
| Postgres append immutability | [c4](docs/evidence/c4-postgres-append-immutability.md) | synthetic |
| Postgres temporal evidence | [c5](docs/evidence/c5-postgres-temporal-evidence.md) | synthetic |
| Protected evidence encryption + redaction | [c6](docs/evidence/c6-protected-evidence-encryption-redaction.md) | synthetic |
| Resolution restore smoke | [c7](docs/evidence/c7-resolution-restore-smoke.md) | synthetic |
| Mac Postgres deployment | [c8](docs/evidence/c8-mac-postgres-deployment.md) | synthetic |
| Postgres temporal knowledge authority | [e2](docs/evidence/e2-postgres-temporal-knowledge.md) | synthetic |
| Governed ticket action | [f](docs/evidence/f-governed-ticket-action.md) | synthetic |
| Deterministic resolution grader | [g1](docs/evidence/g1-deterministic-resolution-grader.md) | synthetic |
| Replay manifest impact report | [g2](docs/evidence/g2-replay-manifest-impact-report.md) | synthetic |
| Manifest-bound replay trials | [g3](docs/evidence/g3-manifest-bound-replay-trials.md) | synthetic |
| Versioned resolution corpus coverage | [g4](docs/evidence/g4-versioned-resolution-corpus-coverage.md) | synthetic |
| Versioned synthetic outcome ledger | [g5](docs/evidence/g5-versioned-synthetic-outcome-ledger.md) | synthetic |
| Synthetic outcome comparison | [g6](docs/evidence/g6-synthetic-outcome-comparison.md) | synthetic |
| Synthetic release evidence manifest | [g7](docs/evidence/g7-synthetic-release-evidence-manifest.md) | synthetic |
| Synthetic release safety gate | [g8](docs/evidence/g8-synthetic-release-safety-gate.md) | synthetic |
| Durable session admission contract | [capsule](docs/evidence/durable-session-admission-contract.md) | synthetic |
| Durable session terminal commit | [capsule](docs/evidence/durable-session-terminal-commit.md) | synthetic |
| Multi-replica session consistency SLA | [capsule](docs/evidence/multi-replica-session-consistency-sla.md) | synthetic |
| Escalation delivery telemetry | [capsule](docs/evidence/escalation-delivery-telemetry.md) | synthetic |
| Index dimension rebuild | [capsule](docs/evidence/index-dim-rebuild.md) | synthetic |
| Index dimension Windows activation | [capsule](docs/evidence/index-dim-windows-activation.md) | synthetic |
| Index lifecycle failure telemetry | [capsule](docs/evidence/index-lifecycle-failure-telemetry.md) | synthetic |
| Index manifest rollback | [capsule](docs/evidence/index-manifest-rollback.md) | synthetic |
| Orphan work telemetry | [capsule](docs/evidence/orphan-work-telemetry.md) | synthetic |
| Retention audit tenant contract | [capsule](docs/evidence/retention-audit-tenant-contract.md) | synthetic |
| Safety block telemetry | [capsule](docs/evidence/safety-block-telemetry.md) | synthetic |
| Tenant denied telemetry | [capsule](docs/evidence/tenant-denied-telemetry.md) | synthetic |
| Trace service lifecycle owner | [capsule](docs/evidence/trace-service-lifecycle-owner.md) | synthetic |
| Validated index rollback | [capsule](docs/evidence/validated-index-rollback.md) | synthetic |

29 slices, 29 `synthetic`, 0 `real_labelled`. Verified-resolution yield across
the 17 scenarios these gates cover: **1/17**. Both numbers are here rather
than in a summary elsewhere, because they are the argument for phase B.

## Phase A (2026-08-24) — the kernel gets a production caller

| Slice | Evidence class | Evidence |
|---|---|---|
| A.1 shipment-status shadow behind `/api/ask` | `fixture` | `tests/test_resolution_shadow_wiring.py` (15 tests) |
| A.5 the same shadow, proved through the endpoint | `fixture` | `tests/integration/test_shipment_status_e2e.py` (7 tests) |
| A.4 legacy body byte-identical, shadow off vs on | `fixture` | same file, `test_the_response_body_is_byte_identical_with_the_shadow_off_and_on` |
| A.1b evidence into the resolution tables | `fixture` | `tests/test_resolution_shadow_persistence.py` (24) + `tests/integration/test_resolution_shadow_postgres.py` (4) |
| A.2 durable session turn around sync `/api/ask` | `synthetic` | `tests/integration/test_session_turns_e2e.py` (8, real Postgres) + `tests/test_session_turn_wiring.py` (32) |
| A.2 database cooldown per tenant, and bounded | `synthetic` | `tests/test_db_cooldown_per_tenant.py` (15) |
| A.3 evidence view endpoint + Evidence tab + JSON export | `fixture` | `tests/test_evidence_view.py` (22) + `tests/test_admin_trace_evidence.py` (9) + `tests/integration/test_shipment_status_e2e.py` (3) |

**A.1 + A.5 together are a slice under rule (a)** (2026-08-25, `4a5bdf1`).
A.1 alone was not: the behaviour change was real — a `resolution_shadow` step
appears in the trace — but it was held by unit tests calling
`_run_resolution_shadows` directly. A.5 posts a shipment-status question to
`/api/ask` over HTTP and reads the evidence bundle back **out of the trace
store**, which is what the phase A.3 Evidence tab will have to do: the bundle
has to survive `_state_to_dict`, `json.dumps`, PII redaction and SQLite, not
just reach the sink.

A.4 is closed at the HTTP level in the same file. A.1 held "the answer does not
change" by object identity inside the process; the byte comparison of two real
response bodies, one with the shadow off and one on, is the claim that was
actually being made. That test also asserts the shadow ran, since otherwise it
would pass equally well with the shadow silently disabled.

**A.1b** (2026-08-25, `ae52cf7`) moves the same bundle from visible to
answerable: a `support_cases` row with the events for the states the run
actually walked, the `evidence_snapshots` it read, and the
`case_evidence_links` that tie them to the case version the answer came from.
The case path is asserted against `ALLOWED_CASE_TRANSITIONS` itself rather
than restated, and the round trip runs against real Postgres with the
append-only triggers and both evidence constraints live.

**A.2** (2026-08-25, `3586b0a` and `8548a1c`) is the second slice under rule
(a), and the first one that does not involve the resolution kernel at all.
`services/session.py` had a durable turn lifecycle with no caller — the other
half of FIN-01. Behind `SESSION_DURABLE_TURNS`, `/api/ask` now admits a turn
before it answers and ends it when it is done: a second request on a session
that is still answering gets a 503 instead of racing the first one, and the
message pair is written by the transaction that marks the turn terminal
rather than by a best-effort write that could drop it. The endpoint is driven
over HTTP against a disposable PostgreSQL and the rows are read back — turn
status, committed version, the pair through
`GET /api/sessions/{id}/history` after the in-memory session map is cleared.

Its second half fixes a defect the audit named: one process-wide
`_db_retry_after` deadline meant a single tenant's database failure stopped
session lookups and message writes for every tenant for a minute. The
cooldown is now per tenant and bounded, with a test that fails against the
old code — tenant B's pair is written while tenant A is in cooldown.

Deliberately absent: replay of a committed response body, `Idempotency-Key`,
`ETag`/`If-Match`. That is REL-03D and the durable-HTTP work, frozen in
`ROADMAP.md`; a turn stores the digest of its pair and no payload.

The A.2 rows are `synthetic`, not `fixture`: no fixture TMS is involved.
They prove the mechanism and say nothing about the domain.

**A.3** (2026-08-25) is the third slice under rule (a) and the first phase-A
item a person can look at. `GET /api/admin/traces/{trace_id}/evidence` joins a
shadow step into what a reviewer needs — contract and version, the policy
decision with its own `recorded_at`, every claim beside the evidence under it
and how old that evidence was when it was read, postconditions, and a replay
receipt of the digests the run was pinned to — and the admin UI renders it
beside Raw JSON with a JSON export. It reads the **trace**, not the resolution
tables: those are the queryable copy and their write is best-effort and
bounded, so a run whose database write timed out still has a complete trace
step. The view carries `case_id` and `case_version` so the queryable copy stays
one lookup away.

The row is `fixture`, not `synthetic`: the journey it renders runs against the
fixture TMS, so what it displays is fixture-sourced.

Building it found the defect in the corrections table below — until then every
bundle behind `/api/ask` was empty, so the tab would have rendered a permanent
blank. That is the argument for the rule: the tab is what made the emptiness
visible, and no amount of local test coverage had.

No row in this phase-A table is `measured`. The first `measured` number
from this journey is A.6 below: over the 100
agent-authored-over-real-documents cases, still `agent_labelled` and 0
approved, admission recall is 0.0000, not a resolution score.

`fixture` is a fourth evidence class, weaker than `synthetic`: the journey
runs against a fixture transport management system
(`resolution/adapters/fixtures/shipment-status-v0.1.json`), so it demonstrates
the wiring and proves nothing about air cargo. Phase B replaces it.

## Phase B (2026-08-25) — the labels, and what they found

| Slice | Evidence class | Evidence |
|---|---|---|
| B.1 journey/outcome/root-cause labels on all 100 air-cargo cases | `agent_labelled` | [capsule](docs/evidence/b1-aircargo-journey-labels.md) · `tests/test_aircargo_labels.py` (13) · `evaluation/curated_cases_aircargo.manifest.json` |

**B.1 is not yet a slice under rule (b).** Rule (b) counts *real* labelled
cases, and `real_labelled` is still 0: every label is the agent's proposal
until the domain-owner proxy approves a batch of 20 (Q2). ADR 0008 decided
that fallback in advance, and the code enforces it — `evidence_class` is
derived from `approved_by`, so a file cannot claim the stronger class by
writing it.

What the labelling produced instead is a finding that changes the rest of
phase B. **All 100 cases name no shipment**: 66 belong to no kernel journey at
all, and the 34 that do are blocked before they start by
`no_shipment_binding`. Nothing in the corpus can reach an observation, a
policy decision or a claim, so B.3 — "the first real numbers on the 100
labelled cases" — cannot be run against it, however good the kernel gets. The
brief's own NO-GO check (§15, "100 cases не отражают реальные обращения") is
what fired. `expected_terminal` is `verified` for 100 out of 100 for the same
reason: these are questions *about* air-cargo work, not requests *inside* it,
so the corpus exercises no escalation, disclosure or refusal path either.

The provenance is narrower than the audit's shorthand as well: the 201 source
documents are real, the 100 questions over them were written by an agent
(`325d63c`, `6b7417d`, `32e841f`). An approval makes the **labelling** real,
not the cases — the manifest says so in `case_source`.

## A.6 (2026-08-27) — admission scored, and what the score says

| Slice | Evidence class | Evidence |
|---|---|---|
| A.6 journey admission scored on the 100 labelled cases | `measured` over `agent_labelled` | [a6](docs/evidence/a6-journey-admission-and-clarification.md) · `python scripts/journey_admission_report.py` |

**A.6 is a slice under rule (c):** a published number with provenance
(corpus sha256 + HEAD sha + code digest + `Reproducible from HEAD`).
`/api/ask` did not change in A.6. T-03 later closed that endpoint gap as
A.7 below.

On these 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved, admission recall is **0.0000**. That is
the published number, and it is the point. The corpus cannot measure
resolution for three independent reasons: no case names a shipment (B.1);
the corpus is Russian and the gate's vocabulary was English
(`contains_both_domain_noun_and_status_cue: 0` at `36d4269`); and with
the language removed (`bd82297`), over the 100
agent-authored-over-real-documents cases, still `agent_labelled` and 0
approved, admission recall is still 0.0000 — reachability moved from
`both 0` to `both 1`, and the one admission is a false positive on a
case labelled `exception_escalation`. The third reason was only findable
because the Russian half is a translation of the English one, not a list
fitted to this corpus.

The before/after table and the report as it prints are in the capsule,
which also records that T-02 fixed four earlier provenance defects.
T-07 closes the remaining provenance gap in report schema v1.3: corpus and
manifest are each read once, their exact snapshots join the code inputs in
`reproducible_from_head`, and every comparison uses the same resolved commit
SHA rather than symbolic `HEAD:path`. Inputs outside the repository fail
closed. Two regressions were RED before the repair; the isolated Mac gate is
11 passed plus strict Mypy and Ruff. Commits: `6651964` (T-01, the gate),
`36d4269` (T-02, the scorer), `bd82297` (T-08, the Russian half), and T-07
(this commit). All are local, not pushed, and have not been through remote CI.

## A.7 (2026-08-27) — clarification owns the opt-in endpoint answer

| Slice | Evidence class | Evidence |
|---|---|---|
| A.7 `/api/ask` projects `CLARIFICATION_REQUIRED` for an admitted no-id request | `synthetic` | `tests/integration/test_shipment_status_e2e.py::test_clarification_flag_returns_the_contract_ask_and_updates_session_history` · `tests/test_resolution_shadow_wiring.py` |

**A.7 is a slice under rule (a).** The independent
`RESOLUTION_CLARIFICATION_JOURNEYS` allowlist defaults off and rejects unknown
journeys. With `shipment-status` named in both allowlists, a Russian status
question without an id returns the contract-derived disclosure and asks for
`shipment_id`; the response carries no claims, citations or measured quality.
The same E2E holds the response schema, trace/session identity and in-memory
session answer. Flag off, a declined request, every other terminal and a
shadow/projection failure keep the legacy response unchanged.

## A.8 (2026-08-27) — an empty Evidence view has an explicit cause

| Slice | Evidence class | Evidence |
|---|---|---|
| A.8 Evidence distinguishes disabled, declined and failed shadow production | `synthetic` | `tests/integration/test_shipment_status_e2e.py::test_clarification_flag_leaves_a_declined_request_on_the_legacy_path` · `tests/integration/test_shipment_status_e2e.py::test_a_shadow_that_raises_still_returns_the_legacy_answer` · `tests/test_evidence_view.py` · `tests/test_admin_trace_evidence.py` |

**A.8 is a slice under rule (a).** A request through `/api/ask` now leaves a
minimal trace outcome when `shipment-status` declines it or its producer
fails; `GET /api/admin/traces/{trace_id}/evidence` and the admin tab distinguish
those outcomes from a disabled shadow. The decline still returns the exact
legacy answer, calls neither source nor policy, and is not offered to the
resolution-table persistence path. Producer failures expose no exception
detail to the API.

## Corrections

Not slices — these fix claims that were false, so they do not go in the table
above.

### 2026-08-27

| Fix | Commit | Test |
|---|---|---|
| Multi-word admission nouns cannot be assembled across message boundaries; a complete noun and its status cue may still occur in different messages | with T-06 | `tests/test_shipment_status_admission.py` |

T-06 is a correction, not A.9. Public `/api/ask` currently supplies one
message to the shipment-status journey, so no endpoint or UI behaviour changed
and rule (a) is not satisfied. The internal tuple contract is still protected
because direct callers may supply more than one message.

### 2026-08-25

| Fix | Commit | Test |
|---|---|---|
| Governed-action ledger counts scoped to their tenant (CI-RED-1: the ledger was right, the assertion read another test's rows) | `0fdb29c` | `tests/integration/test_governed_actions_postgres.py` |
| Shipment-id extractor could not match any id the fixture TMS holds | with A.3 | `tests/integration/test_shipment_status_e2e.py` |

The extractor matched only `SHP-…`. The fixture TMS
(`resolution/adapters/fixtures/shipment-status-v0.1.json`) holds `AC-…`, and
every wiring and end-to-end test asks about `AC-100001`. So no question about a
shipment the fixture actually contains could reach an observation: the journey
answered `CLARIFICATION_REQUIRED` / `SHIPMENT_ID_REQUIRED` every time, and the
evidence bundle behind `/api/ask` never carried a source, a policy or a single
claim. Everything A.1, A.1b, A.4 and A.5 asserted was true — the shadow ran,
reached the trace, reached the tables — and none of it needed a bundle with
anything in it. The end-to-end test now drives a `verified` journey with its
claims resolved to their evidence.

The claim that was false was in [ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md)
and `BACKLOG.md`, not in the code: both stated that the governed-action
reconcile path recorded a second run row for one logical action. It never did.
The ADR carries a postscript saying so.

### Phase 0 (2026-08-24)

| Fix | Commit | Test |
|---|---|---|
| Mistral prices pinned to a dated snapshot | `c4b2d0c` | `tests/test_provider_pricing_snapshot.py` |
| Resolved model recorded behind `*-latest` | `c4b2d0c` | `tests/test_mistral_provider.py`, `tests/test_graph_helpers.py` |
| Skipped eval run is `NOT_EVIDENCE`, not a pass | `f57ade8` | `tests/test_eval_gate_skip_is_not_evidence.py` |
| Copied reference answers tagged and refused | `f57ade8` | `tests/test_ragas_eval.py` |
| Cookie-auth `Origin` fail-closed | see phase 0 commit | `tests/test_session_auth_cookie.py` |
| Kernel packages inside mypy + coverage | see phase 0 commit | `tests/test_precommit_config.py` |
