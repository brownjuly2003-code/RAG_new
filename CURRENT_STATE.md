# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-25 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· HEAD when this was written: `c3e86f4` + phase A.3

## Start here

### 1. Phase B — the number this repository is actually judged on

**Phase A is done.** 100 real labelled cases is what is left between this
repository and a number worth publishing. Blocked on **Q2** below, with a
decided fallback, so it never waits.

### 2. Housekeeping with a date on it

**Review 2026-09-24:** the three chromadb CVE ignores. If a fixed release
exists by then, upgrade and delete them from all four places the guard
requires them to match.

## What changed on 2026-08-25

- **Phase A closed** — A.1, A.1b, A.2, A.3, A.4 and A.5 all landed today.
- **A.3 — the Evidence tab** (rule (a), third slice).
  `GET /api/admin/traces/{trace_id}/evidence` joins a shadow step into what a
  reviewer needs — contract, the policy decision with its own `recorded_at`,
  every claim beside the evidence under it and how old that evidence was when
  it was read, postconditions, and a replay receipt — and the admin UI renders
  it beside Raw JSON with a JSON export. It reads the trace, not the
  resolution tables: those are the queryable copy and their write is
  best-effort, so a run whose write timed out still has a complete trace step.
- **Building it found a defect that made the whole journey hollow.** The
  shipment-id extractor matched only `SHP-…`, while the fixture TMS holds
  `AC-…` and every test asks about `AC-100001`, so no question about a
  shipment the fixture contains could reach an observation: every bundle
  behind `/api/ask` was `CLARIFICATION_REQUIRED` with no source, no policy and
  no claims. Fixed; the E2E now drives a `verified` journey with its claims
  resolved to their evidence. Full account in `EVIDENCE_INDEX.md`.
- **A.2 — the durable session turn** (rule (a), second slice). `3586b0a`
  wires `SessionService` into the synchronous `/api/ask` behind
  `SESSION_DURABLE_TURNS`, off by default: one turn per session at a time — a
  second request while the first is answering gets 503 — and the message pair
  written by the transaction that ends the turn rather than by a best-effort
  write that could lose it. `8548a1c` makes the process-wide
  `_db_retry_after` deadline a per-tenant, bounded cooldown. Deliberately
  absent: response replay, `Idempotency-Key`, `ETag`/`If-Match` — REL-03D and
  the durable-HTTP work, still frozen.
- **A.5 + A.4** (`4a5bdf1`) made A.1 + A.5 the first slice under rule (a);
  **A.1b** (`ae52cf7`) put the same evidence into the resolution tables and
  bounded that write at 2s. **Both inherited CI failures are closed**
  (`0fdb29c`, `af0d4fd`, `81427b5`) — ADR 0008's diagnosis of CI-RED-1 was
  wrong and carries a postscript; `BACKLOG.md` and `EVIDENCE_INDEX.md` have
  the detail.

## What is true right now

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private, tag
  `freeze-2026-08-23` = `26866e9` = the state the audit describes. The
  account's git protocol is ssh with no key loaded, so pushes go over HTTPS:
  `git -c credential.helper='!gh auth git-credential' push origin master`.
- **The kernel has a production caller** (2026-08-24), having had none for the
  whole life of the fork. `/api/ask` runs the shipment-status journey as a
  read-only shadow behind `RESOLUTION_SHADOW_JOURNEYS`, off by default; the
  answer stays the legacy one and tests hold it to that. The phase-A gate
  command returns a file rather than nothing:
  `grep -rlE 'from resolution|services\.session' api` → `api/routers/conversation.py`.
- **`services/session.py` has a caller too** (2026-08-25), behind
  `SESSION_DURABLE_TURNS`, also off by default. Both halves of FIN-01's
  "primitives with no caller" are closed; what is left of FIN-01 is that
  everything they run against is still synthetic.
- **Zero real labelled cases.** All 17 resolution scenarios are synthetic;
  verified-resolution yield 1/17. Phase B is what changes this.
- **Full unit suite green in CI** (run 32864216309): 2203 passed, 25 skipped,
  coverage 75.96% against a gate of 72; the integration job is 59 passed,
  1 skipped. Unit scope understates the Postgres adapters
  (`actions/postgres.py` and `knowledge/postgres.py` 0%,
  `resolution/adapters/postgres.py` 29%, `services/session.py` under half):
  the integration job exercises those, without `--cov`.
- **CI is fully green** — 11/11 on run 32864216309, and has stayed green
  through both A.2 commits. A red job now means a new problem; that was the
  whole point of clearing the inherited ones. The "Deploy docs site" workflow
  builds and skips its Pages deploy, which is unavailable on a private repo
  and lifts itself when Q4 makes the repo public.

## Accepted open risks

- **Three chromadb CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version
  available. Ignored by id per ADR 0008 — applied in `ci.yml`, still to apply
  in `.pre-commit-config.yaml`. **Review 2026-09-24.** A new chromadb CVE must
  still turn CI red.
- **The fixture TMS is a stand-in**, not a transport management system. Every
  number measured through it is fixture-sourced and has to say so. Phase B
  replaces it.
- **The integration job connects to Postgres as a superuser**, so RLS is inert
  for any assertion that does not deliberately go through a NOBYPASSRLS
  runtime role. All four Postgres modules do route their isolation assertions
  through one, so nothing is unguarded today — but this is the trap CI-RED-1
  fell into, and a new test that forgets it passes for the wrong reason. The
  real fix is a non-superuser application role for the job; not scheduled.

## The rule that governs every slice

A slice counts only if **(a)** observable `/api/ask` or UI behaviour changed
with an E2E test proving it, **(b)** real labelled cases went up, or **(c)** a
published number changed with provenance. Anything else is preparation, and
fixing a failing test is a repair — it goes in the corrections table of
[`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), not the slice table. Full text in
[`CLAUDE.md`](CLAUDE.md); it is the direct counter to FIN-01 / FIN-02, where
local provability was the path of least resistance.

## Phase A — done

| # | Item | Status |
|---|---|---|
| A.1 | Shadow wired into `/api/ask` behind a flag, evidence into the trace | `900236f`, 15 tests |
| A.5 | `tests/integration/test_shipment_status_e2e.py` | `4a5bdf1`, 7 tests; **A.1 + A.5 = a slice under rule (a)** |
| A.4 | Characterisation: legacy answer byte-identical, flag off vs on | `4a5bdf1`, byte comparison of two real response bodies |
| A.1b | Evidence into the Postgres tables (migrations 024–030) | `ae52cf7`, 24 unit + 4 Postgres tests |
| A.2 | `SessionService` admit/commit around sync `/api/ask`, per-tenant DB cooldown | `3586b0a` + `8548a1c`, 8 Postgres E2E + 47 unit; **a slice under rule (a)** |
| A.3 | Evidence view endpoint + tab, JSON export | 3 E2E + 31 unit; **a slice under rule (a)** |

## Phase 0 — done

0.1–0.3 all landed and every gate command in `plan_23_08_2026.md` §0 passes;
per-fix commits and tests are in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md).

## Open questions for Julia

Q1 is answered (separate private repo). Each of these blocks only its own phase:

- **Q2 (phase B):** act as domain-owner-proxy — approve 100 labels in batches
  of 20, plus 40 double-annotated calibration routes. **If unanswered when
  phase B starts**, ADR 0008 decides the fallback: proceed with agent-proposed
  labels tagged `evidence_class: agent_labelled`, never `real_labelled`, with
  phase B's gate explicitly not met and `real_labelled` still showing 0.
- **Q3 (phase C):** heavy runs on Colab or the iMac. **Q4 (phase E):** publish
  as `RAG_new` or rename.

## Links

- Roadmap and what is frozen — [`ROADMAP.md`](ROADMAP.md)
- One row per slice, with evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Defect detail and the pre-audit queue — [`BACKLOG.md`](BACKLOG.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · history (do not plan from it) —
  [`AGENT_STATE.md`](AGENT_STATE.md)
