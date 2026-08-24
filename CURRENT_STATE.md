# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-24 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· HEAD when this was written: `c6d6796`

## Start here — the next three things, in this order

The decisions behind this ordering are written out in
[ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md). They were made by an
agent under explicit delegation; overrule any of them freely, the reasoning is
there so that is cheap.

### 1. Fix CI-RED-1 — timebox: one working session

`tests/integration/test_governed_actions_postgres.py::test_timeout_reconciliation_never_dispatches_a_second_create`
fails `assert 2 == 1` on the `GovernedActionRun` count.

Already localised, so start from here rather than from scratch: run rows are
inserted at exactly one site, `actions/postgres.py:407`, guarded by a lookup on
`(tenant_id, operation_key_digest)`; `complete_event` only selects. Two rows
means the reconcile path arrives with a different `operation_key_digest` than
the request path computed. The connector is *not* called twice, so this is a
ledger defect, not a duplicate side effect.

This goes first because step 3 lands a new test in this same job — a new
integration test cannot be verified inside a job that is already red.

**If the timebox expires without a root cause:** mark it
`@pytest.mark.xfail(strict=True)` citing ADR 0008, and log it in
[`BACKLOG.md`](BACKLOG.md). Never delete, never plain-`skip`, never weaken the
assertion. `strict=True` so an accidental fix cannot pass unnoticed.

### 2. Apply the CI-RED-2 ignore — 15 minutes

Add `--ignore-vuln` for CVE-2026-45830, CVE-2026-45833 and CVE-2026-45831 to
the `security` job in `.github/workflows/ci.yml` and to the `pip-audit` hook in
`.pre-commit-config.yaml`. chromadb 1.5.9 is the latest release on PyPI; there
is nothing to upgrade to. All five conditions in ADR 0008 are mandatory —
inline comment with CVE id and date, **review 2026-09-24**, by id only, never a
blanket ignore, never dropping `--strict`.

After steps 1 and 2, CI should be green. From then on a red job means a new
problem, which is the entire reason for doing them first.

### 3. A.5 — the E2E test that turns A.1 into an actual slice

`tests/integration/test_shipment_status_e2e.py`: a shipment-status question
through the real endpoint → legacy answer plus a `resolution_shadow` step in
the trace carrying the evidence bundle. A.1 is wired and unit-tested but is
**not yet a slice** under the rule below, and this is what closes that.

Then, in order: A.4 (HTTP-level characterisation — answer byte-identical with
the flag off and on), A.1b (evidence into the Postgres tables), A.2
(`SessionService` admit/commit), A.3 (Evidence tab).

## What is true right now

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private,
  `master` pushed, tag `freeze-2026-08-23` = `26866e9`, the state the audit
  describes. The account's git protocol is ssh with no key loaded, so pushes go
  over HTTPS:
  `git -c credential.helper='!gh auth git-credential' push origin master`.
- **The kernel has a production caller** (2026-08-24), having had none for the
  whole life of the fork. `/api/ask` runs the shipment-status journey as a
  read-only shadow behind `RESOLUTION_SHADOW_JOURNEYS`, off by default; the
  answer stays the legacy one and tests hold it to that. The phase-A gate
  command now returns a file rather than nothing:
  `grep -rlE 'from resolution|services\.session' api` →
  `api/routers/conversation.py`.
- **Zero real labelled cases.** All 17 resolution scenarios are synthetic;
  verified-resolution yield 1/17. Phase B is what changes this.
- **Full unit suite green locally** (Windows): 2134 passed, 4 skipped,
  coverage 76.05% against a gate of 72 — widening the source to the kernel
  packages raised it. Unit scope understates the Postgres adapters
  (`actions/postgres.py` and `knowledge/postgres.py` 0%,
  `resolution/adapters/postgres.py` 29%, `services/session.py` 44%): the
  integration job exercises those, without `--cov`.
- **CI red is only what was inherited** (run 32780432073): eight jobs green;
  `test-integration` (both legs), `security` and `pre-commit` red, all three
  reproducing at the freeze tag on branch `baseline/freeze-2026-08-23`. Phase 0
  and phase A.1 added none of it. Compare against that branch before assuming a
  new failure is inherited.

## Accepted open risks

- **Three chromadb CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version
  available. Ignored by id per ADR 0008 once step 2 lands. **Review 2026-09-24.**
  A new chromadb CVE must still turn CI red.
- **The fixture TMS is a stand-in**, not a transport management system. Every
  number measured through it is fixture-sourced and has to say so. Phase B
  replaces it.

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
| A.5 | `tests/integration/test_shipment_status_e2e.py` | **next**, after CI is green |
| A.4 | Characterisation: legacy answer byte-identical, flag off vs on | partial — object identity held by unit tests; HTTP-level check open |
| A.1b | Evidence into the Postgres tables (migrations 024–030) | open |
| A.2 | `SessionService` admit/commit around sync `/api/ask` | open |
| A.3 | Evidence tab on the trace in admin/agent UI | open |

## Phase 0 — done

0.1–0.3 all landed; every gate command in `plan_23_08_2026.md` §0 passes.
`c4b2d0c` pricing snapshot · `f57ade8` eval-gate + ragas evidence classes ·
`4d82a68` kernel packages into mypy/coverage + cookie `Origin` fail-closed ·
`e541385` root 46 → 9 md · `fdeff62` the errors the widened type scope found.
The corrections table in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) has the
per-fix tests.

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
