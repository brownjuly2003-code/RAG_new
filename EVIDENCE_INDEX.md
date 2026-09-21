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
| D.1 pgvector pre-reranker comparison: 115 cases, 3 runs; sequential scans, non-owner RLS; Phase D open | [Measurement and replay](docs/evidence/d1-pgvector-prererank.md) | measured |
| C.3 manual copilot: validated shipment skeleton in `ai_draft`, agent API readback, off parity and fallback | [Copilot verification](docs/evidence/c3-copilot-contract-draft.md) | synthetic |
| C.3 HTTP: pinned response shape → verified fixture answer; evidence binding and legacy-off parity | [HTTP verification](docs/evidence/c3-contract-shaped-response.md) | synthetic |
| GR-2 entity retrieval: bounded traversal → third RRF list → `/api/ask` → Evidence; stale graph rejection and off/auto fallback | [HTTP and retrieval verification](docs/evidence/gr2-entity-retrieval-wiring.md) | synthetic |
| GR-4 structural path: opt-in `/api/ask` → SQLite → Evidence; off/auto fallback, browser rendering and export | [HTTP and browser verification](docs/evidence/gr4-structural-product-wiring.md) | synthetic |
| GR-1b seed reservation: coherent 0.5472 / 0.9200; seed text preserved, no metric gain, NO-SHIP | [report and tests](docs/evidence/gr1b-seed-expansion.md) | measured |
| GR-1b structural replay: 100/100 exact; expansion alone 0.5125 / 0.9300, no G1 keyword losses, NO-SHIP | [stage report and tests](docs/evidence/gr1b-stage-replay.md) | measured |
| GR-1b query-only control: 0.6268 / 0.7250; 22 FULL regressions, NO-SHIP; missing-hit diagnosis | [report and reproduction test](docs/evidence/gr1b-query-control.md) | measured |
| GR-1b bounded safe-subset oracle: 0.6780 / 0.9250 with G1 fallback; label-dependent diagnostic only | [GR-1b oracle](docs/evidence/gr1b-safe-subset-oracle.md) | measured |
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
`36d4269` (T-02, the scorer), `bd82297` (T-08, the Russian half), and `491860d`
(T-07). All are local, not pushed, and have not been through remote CI.
T-09 then closes the validator gap: the exact double-space stem was RED before
the one-line source fix; 174 adjacent tests, strict Mypy and Ruff are green.
T-09 is local in its own commit, not pushed, and has not been through remote CI.

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

## Phase C (2026-08-30…2026-09-11) — generator benchmarks

| Slice | Evidence class | Evidence |
|---|---|---|
| C.1a Qwen 2.5 7B baseline over 3 × 100 cases | `measured` over `agent_labelled` | [raw report](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json) · [SHA-256](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json.sha256) · `tests/test_phase_c_baseline_artifact.py` |
| C.1b Qwen3 8B over 3 × 100 cases | `measured` over `agent_labelled` | [c1b-qwen3-generator-benchmark](docs/evidence/c1b-qwen3-generator-benchmark.md) · [raw report](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json) · [SHA-256](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json.sha256) · `tests/test_phase_c_qwen3_artifact.py` |

**C.4 decision (2026-09-21):** [NO-SHIP of Qwen3 as default](docs/evidence/c4-generator-model-decision.md), based on the two reports above; no new measurement. Faithfulness 0.8986 misses 0.90; NLI does not replace that gate, and total-host peak RAM is unknown. Existing artifact tests reproduce both reports.

**C.1a is a slice under rule (c):** a Mac run that actually happened, with
exact source, corpus, cached-context, model and config provenance. All 300
rows have valid generation, LLM-judge and NLI output; none has an error. The
run-level means are LLM faithfulness **0.8295** (95% CI
[0.8295, 0.8295]), NLI faithfulness **0.8919** ([0.8916, 0.8923]), context
precision **0.5067** ([0.5067, 0.5067]) and mean latency **197.50 seconds per
case** ([192.10, 202.90]).

This is generator-quality evidence over 100 agent-authored questions and
hash-pinned cached contexts from real documents; it is not a shipment-resolution
number. The baseline misses the phase-C faithfulness and precision thresholds.
C.1a alone was neither a default-model change nor the phase's final NO-SHIP
decision.

**C.1b is a second slice under rule (c):** Qwen3 8B completed the same 3 × 100
contract with zero failed cases. LLM faithfulness is **0.8986**, NLI
faithfulness **0.9908**, answer relevancy **0.8095**, and mean latency **176.81
seconds per case** (run-level 95% CI [105.34, 248.29]). Context precision stays
**0.506657** and recall **0.9050** because the cached-context digest is exactly
the C.1a digest. The result is now an input to C.4, not a model flip: the LLM
faithfulness mean remains 0.0014 below the 0.90 gate, and the report does not
contain a total-host peak-RAM measurement.

## Stream GR (2026-09-09) — the retrieval ruler

| Slice | Evidence class | Evidence |
|---|---|---|
| GR-0.3 phase C retrieval baseline split by question class, over the question-class sidecar `evaluation/curated_cases_question_class.jsonl` + its manifest (`tests/test_question_class_labels.py`) | `measured` over `agent_labelled` | [gr0-bucket-baseline](docs/evidence/gr0-bucket-baseline.md) · [report](reports/gr/gr0-bucket-baseline.json) · `tests/test_gr_bucket_baseline.py` · `python scripts/ab_context_precision.py --buckets` |
| GR-1a section coherence measured as a narrowing arm over the same pinned pool, against GR-0.3 and against fixed top-k truncation | `measured` over `agent_labelled` | [gr1a-section-coherence](docs/evidence/gr1a-section-coherence.md) · [report](reports/gr/gr1a-section-coherence.json) · `tests/test_section_coherence_arm.py` · `python scripts/ab_context_precision.py --section-coherence` |
| GR-1b recovered Mac structural pool: precision 0.5475, recall 0.9200; NO-SHIP at 0.63, prefilter 0/100; producer revision is handoff-attributed | `measured` over `agent_labelled` | [gr1b-structure-graph](docs/evidence/gr1b-structure-graph.md) · [report](reports/gr/gr1b-structure-graph.json) · `tests/test_gr1b_artifact.py` reproduces archived input |
| GR-1b same-pool controls: top-1 reaches 0.6403 but loses 23 FULL; no ordinary top-k meets precision and coverage together | `measured` over `agent_labelled` | [gr1b-same-pool-controls](docs/evidence/gr1b-same-pool-controls.md) · [report](reports/gr/gr1b-controls.json) · `tests/test_gr1b_controls.py` |
| GR-2 entity lane against GR-1 on the same cases: phase C 0.5475 → 0.5487 (single-hop 0.5487 → 0.5499, lane on 6/100), multi-document bucket unchanged on all 15 cases although the lane fired on 11; NO-SHIP at 0.63, default unchanged | `measured` over `agent_labelled` | [gr2-entity-graph-lane](docs/evidence/gr2-entity-graph-lane.md) · [report](reports/gr/gr2-entity-graph.json) · `tests/test_gr2_artifact.py` rebuilds from the archived pools |
| GR-3 three-arm A/B on the same cases: phase C `G2` 0.5487 vs hybrid 0.5067 (FULL 87 → 89); multi-doc bucket recall 0.5000 → 0.4000, FULL 4 → 1; retrieve p95 +8765.2 ms on `deproject-mac`; generation half `not_evidence` (297/300 valid, 99 paired cases); **NO-SHIP-to-default**, default unchanged | `measured` over `agent_labelled`; generation half `not_evidence` | [gr3-graph-lane-ab](docs/evidence/gr3-graph-lane-ab.md) · [report](reports/gr/gr3-graph-lane-ab.json) · [raw generation](evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json) · [sha256](evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json.sha256) · [reproduction test](tests/test_gr3_artifact.py) rebuilds from the archived pools |

**GR-0.3 is a slice under rule (c)** and the first published number of stream
GR: context precision **0.5067** and recall **0.9050** at top-5 over the pinned
arm-C pool (`91ce1745…`), reconciling exactly with the C.1a baseline, split as
`single_hop` 0.5063 / 0.9091 over **99** cases, `multi_hop` 0.5401 / 0.5000 over
**1**, `aggregation` and `global` over **0** each. All of it is over 100
questions agent-authored from real documents, still `agent_labelled` with 0
approved, whose question classes are agent-assigned and likewise unapproved.

The row is also where the T-11 question-class labels stop being an unmeasured
artefact: this is the first number computed over them. With 99 of the 100 cases
in one bucket the table cannot discriminate between classes, which is the
finding rather than a defect — GR-0.2's ≥ 15 new multi-hop questions are the
precondition for any bucketed comparison, and they need a new candidate pool
built on the Mac. No retrieval behaviour changed in this slice.

**GR-1a is a slice under rule (c)** and the first *arm* measured against that
ruler: section coherence over the same pool, off by default, reported as a whole
threshold grid rather than one cell. Twelve of the twenty cells cost no keyword
coverage; at the best of them it reaches context precision **0.5216** against
the baseline's **0.5067**, with recall **0.9050** and 87 / 7 / 6 unchanged —
but plain top-4
truncation of the same pool reaches **0.5214** with the same coverage, so on
this corpus the headline gain is a smaller *k*, not section structure. The arm
beats fixed truncation only where it drops harder: 82 FULL at 2.13 documents per
case against top-2's 79, and 71 FULL at 1.24 documents against top-1's 65. The
GR-1 target of 0.63 is reached only at the threshold that turns 16 FULL cases
into PART or MISS, all named in the capsule. No production retrieval behaviour
changed in this slice either.

## Corrections

Not slices — these fix claims that were false, so they do not go in the table
above.

### 2026-08-29

| Fix | Commit | Test |
|---|---|---|
| Human-calibration readiness now requires at least 40 unique cases with 40 valid double labels; the binding floors cannot be lowered | `56b6dcc` | `tests/test_calibration_artifact.py` |

This is a fail-closed correction, not B.4 completion. The checked-in calibration
set remains 10 synthetic routes; no human-labelled route was added or claimed.

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
