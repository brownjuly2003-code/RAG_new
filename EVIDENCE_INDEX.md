# Evidence index

One row per slice. The capsule is the *record*; the *evidence* is the test or
the number it points at. A slice with no test and no published number is not
on this list.

**Evidence class** says what the claim rests on:

- `synthetic` — fixtures the project wrote for itself. Proves the mechanism
  works; proves nothing about the domain.
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

No row here is `measured`: no number is published from this journey yet.

`fixture` is a fourth evidence class, weaker than `synthetic`: the journey
runs against a fixture transport management system
(`resolution/adapters/fixtures/shipment-status-v0.1.json`), so it demonstrates
the wiring and proves nothing about air cargo. Phase B replaces it.

## Corrections

Not slices — these fix claims that were false, so they do not go in the table
above.

### 2026-08-25

| Fix | Commit | Test |
|---|---|---|
| Governed-action ledger counts scoped to their tenant (CI-RED-1: the ledger was right, the assertion read another test's rows) | `0fdb29c` | `tests/integration/test_governed_actions_postgres.py` |

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
