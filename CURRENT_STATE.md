# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-25 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· HEAD when this was written: `4a5bdf1`

## Start here

### 1. A.2 — `SessionService` admit/commit around sync `/api/ask`

The last wiring item before anything a user can see. Then **A.3**, the Evidence
tab, which is the first phase-A item that shows up in a UI — and the first
consumer of the rows A.1b started writing.

### 2. Phase B — the number this repository is actually judged on

100 real labelled cases. Blocked on **Q2** below, with a decided fallback, so
it is never blocked waiting.

### 3. Housekeeping with a date on it

**Review 2026-09-24:** the three chromadb CVE ignores. If a fixed release
exists by then, upgrade and delete them from all four places the guard
requires them to match.

## What changed on 2026-08-25

- **CI-RED-1 is closed** (`0fdb29c`, green on both legs, run 32831583779). The
  diagnosis in ADR 0008 was wrong: there was no ledger defect. Run rows are
  inserted at one site with one caller, `ActionGateway.request`, and the test
  calls it once. The count named no tenant, and the session connects as the
  Postgres superuser, which RLS does not apply to — so it counted the previous
  test's row too. The ADR has a postscript; `BACKLOG.md` has the full account.
- **A.5 and the HTTP half of A.4 landed** (`4a5bdf1`). A shipment-status
  question posted to `/api/ask` leaves exactly one `resolution_shadow` step in
  the trace the answer names, and the bundle is read back **out of the trace
  store**, not intercepted on the way in. The response body is byte-for-byte
  identical with the shadow off and on. **A.1 + A.5 together are a slice under
  rule (a)** — the first one here.
- **CI-RED-2 closed** (`af0d4fd`) and the docs-site deploy conditioned
  (`81427b5`): every workflow is green or honestly skipped.
- **A.1b landed** (`ae52cf7`, 31 tests). The shadow's evidence now goes into
  `support_cases` / `case_events` / `evidence_snapshots` /
  `case_evidence_links`, so it is queryable and not merely visible. The case
  walks the states the bundle justifies, checked against
  `ALLOWED_CASE_TRANSITIONS` itself. Wiring it up found a real defect on the
  way: an unreachable database does not fail fast, and the first version hung
  `/api/ask` — the write is now bounded at 2s with a test holding it.

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
- **Zero real labelled cases.** All 17 resolution scenarios are synthetic;
  verified-resolution yield 1/17. Phase B is what changes this.
- **Full unit suite green locally** (Windows): 2134 passed, 4 skipped,
  coverage 76.05% against a gate of 72 — widening the source to the kernel
  packages raised it. Unit scope understates the Postgres adapters
  (`actions/postgres.py` and `knowledge/postgres.py` 0%,
  `resolution/adapters/postgres.py` 29%, `services/session.py` 44%): the
  integration job exercises those, without `--cov`.
- **CI is fully green** — 11/11 on run 32843444796, for the first time in the
  life of this repository. A red job now means a new problem; that was the
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
- **The integration job connects to Postgres as a superuser**, so row-level
  security is inert for any assertion that does not deliberately go through a
  NOBYPASSRLS runtime role. All four Postgres modules currently do route their
  isolation assertions through one, so nothing is unguarded today — but this is
  the trap CI-RED-1 fell into, and a new test that forgets will pass for the
  wrong reason. Fixing it properly means a non-superuser application role for
  the whole job; not scheduled.

## The rule that governs every slice

A slice counts only if **(a)** observable `/api/ask` or UI behaviour changed
with an E2E test proving it, **(b)** real labelled cases went up, or **(c)** a
published number changed with provenance. Anything else is preparation. Full
text and rationale in [`CLAUDE.md`](CLAUDE.md); it is the direct counter to
FIN-01 / FIN-02, where local provability was the path of least resistance.

Fixing a failing test is **not** a slice and does not pretend to be — it is a
repair, and it goes in the corrections table of
[`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md).

## Phase A — in progress

| # | Item | Status |
|---|---|---|
| A.1 | Shadow wired into `/api/ask` behind a flag, evidence into the trace | done — `900236f`, 15 tests |
| A.5 | `tests/integration/test_shipment_status_e2e.py` | done — `4a5bdf1`, 7 tests; **A.1 + A.5 = a slice under rule (a)** |
| A.4 | Characterisation: legacy answer byte-identical, flag off vs on | done — `4a5bdf1`, byte comparison of two real response bodies |
| A.1b | Evidence into the Postgres tables (migrations 024–030) | done — `ae52cf7`, 24 unit + 4 Postgres tests |
| A.2 | `SessionService` admit/commit around sync `/api/ask` | **next** |
| A.3 | Evidence tab on the trace in admin/agent UI | open |

## Phase 0 — done

0.1–0.3 all landed; every gate command in `plan_23_08_2026.md` §0 passes.
`c4b2d0c` pricing snapshot · `f57ade8` eval-gate + ragas evidence classes ·
`4d82a68` kernel packages into mypy/coverage + cookie `Origin` fail-closed ·
`e541385` root 46 → 9 md · `fdeff62` the errors the widened type scope found.
Per-fix tests: the corrections table in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md).

## Open questions for Julia

Q1 is answered (separate private repo). Each of these blocks only its own phase:

- **Q2 (phase B):** act as domain-owner-proxy — approve 100 labels in batches
  of 20, plus 40 double-annotated calibration routes. **If unanswered when
  phase B starts**, ADR 0008 decides the fallback: proceed with agent-proposed
  labels tagged `evidence_class: agent_labelled`, never `real_labelled`, with
  phase B's gate explicitly not met and `real_labelled` still showing 0.
- **Q3 (phase C):** heavy runs on Colab or the iMac.
- **Q4 (phase E):** publish as `RAG_new` or rename.

## Links

- Roadmap and what is frozen — [`ROADMAP.md`](ROADMAP.md)
- One row per slice, with evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Defect detail and the pre-audit queue — [`BACKLOG.md`](BACKLOG.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md)
- Removed/deprecated surfaces — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- History (do not plan from it) — [`AGENT_STATE.md`](AGENT_STATE.md)
