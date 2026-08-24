# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-08-24 · Plan: [`plan_23_08_2026.md`](plan_23_08_2026.md)
(mode B) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)

---

## What this is

A clone of `RAG_Support_Assistant` at `bd07179` (brief: `D:\New_steps\rag.md`),
carrying the inherited RAG runtime plus a deterministic resolution kernel:
`resolution/`, `knowledge/`, `actions/`, `services/session.py`, migrations
024–031.

## What is true right now

- **Remote exists as of 2026-08-24:**
  `https://github.com/brownjuly2003-code/RAG_new` (private), `master` pushed,
  tag `freeze-2026-08-23` marks the state the audit describes (`26866e9`).
  Push over HTTPS with `gh` credentials — the account's git protocol is ssh
  and no key is loaded, so `git -c credential.helper='!gh auth git-credential'
  push` is the working form.
- **The kernel has a production caller as of 2026-08-24.** It had none for
  the whole life of the fork; `/api/ask` now runs the shipment-status journey
  as a read-only shadow behind `RESOLUTION_SHADOW_JOURNEYS`, off by default.
  The phase-A gate command returns a file rather than nothing:
  `grep -rlE 'from resolution|services\.session' api` →
  `api/routers/conversation.py`. The answer itself is still the legacy one,
  unchanged — that is the point of a shadow, and tests hold it to that.
- **Zero real labelled cases.** All 17 resolution scenarios are synthetic;
  verified-resolution yield is 1/17. Phase B changes this.
- **Full unit suite green locally** (2026-08-24, Windows): 2134 passed, 4
  skipped, coverage 76.05% against a gate of 72. Widening the coverage source
  to the kernel packages raised the number, not lowered it. The Postgres
  adapters read low in unit scope (`actions/postgres.py` 0%,
  `knowledge/postgres.py` 0%, `resolution/adapters/postgres.py` 29%,
  `services/session.py` 44%) because the integration job exercises them and
  runs without `--cov`.
- **CI has run, and the red is now down to what was inherited** (run
  32777742986): `type-check` went green once the two errors the widened scope
  exposed were fixed. Three jobs stay red — `test-integration` (both legs),
  `security`, `pre-commit` — all reproduced at the freeze tag. Earlier run
  32775056817, before the type fixes:
  `lint`, `migrations`, `helm`, `regression-eval`, `test-unit` (3.11 + 3.13,
  including the coverage gate) pass. `type-check`, `test-integration` (both
  legs), `security` and `pre-commit` fail. `baseline/freeze-2026-08-23` — a
  branch at the freeze tag, before any phase-0 commit — reproduces the
  integration, security and pre-commit failures and passes `type-check`, so
  three of the four reds are inherited and one is the widened type scope.

## Phase A — in progress

| # | Item | Status |
|---|---|---|
| A.1 | Shadow wired into `/api/ask` behind a flag, evidence into the trace | done — flag, composition root, packaged contract + fixture TMS, 13 tests |
| A.1b | Evidence into the Postgres tables (migrations 024–030) | open |
| A.2 | `SessionService` admit/commit around sync `/api/ask` | open |
| A.3 | Evidence tab on the trace in admin/agent UI | open |
| A.4 | Characterisation test: legacy answer byte-identical, flag off vs on | partial — object identity is held by unit tests; the HTTP-level check is open |
| A.5 | `tests/integration/test_shipment_status_e2e.py` | open |

The fixture TMS is a stand-in, not a transport management system. Every number
measured through it is fixture-sourced and has to say so — phase B is what
replaces it with real labelled cases.

## Phase 0 — done

| # | Item | Status |
|---|---|---|
| 0.1 | Private repo, push, `freeze-2026-08-23` tag | done — Q1 answered: separate private repo |
| 0.1b | First CI run green/red, honestly recorded | done — red, with a freeze-tag baseline separating inherited from new |
| 0.2.1 | Mistral pricing pinned to a dated snapshot + contract test | done — `c4b2d0c` |
| 0.2.2 | README: real mypy scope, real CI job list | done |
| 0.2.3 | mypy + coverage cover the kernel packages | done |
| 0.2.4 | `eval_gate.py` skip is `NOT_EVIDENCE`, exit 2 | done — `f57ade8` |
| 0.2.5 | `ragas_eval` tags copied reference answers | done — `f57ade8` |
| 0.2.6 | Cookie-auth `Origin` fail-closed | done |
| 0.3 | Doc hygiene: root ≤ 8 md, capsules to `docs/evidence/` | done |

### Open questions

Q1 is answered (separate private repo, 2026-08-24). Still open, each blocking
only its own phase:

- **Q2 (phase B):** Julia acting as domain-owner-proxy — approving 100 labels
  in batches of 20, plus 40 double-annotated calibration routes. Without it,
  phase B produces agent-labelled cases, not real ones.
- **Q3 (phase C):** heavy runs on Colab or the iMac.
- **Q4 (phase E):** publish as `RAG_new` or rename.

## The rule that governs every slice

A slice counts only if at least one holds:

- **(a)** observable `/api/ask` or UI behaviour changed, proven by an E2E test;
- **(b)** the count of real labelled cases went up;
- **(c)** a published quality number changed, with provenance (corpus SHA +
  code SHA + config).

"Locally complete" without (a)/(b)/(c) is preparation, not a slice. This
applies to agents and to autopilot, and it is the direct counter to FIN-01 /
FIN-02 — seven layers of release machinery were built on synthetic fixtures
because local provability was the path of least resistance.

## Two inherited failures need a decision from Julia

Detail and root-cause localisation in [`BACKLOG.md`](BACKLOG.md).

- **CI-RED-1:** governed-action reconcile writes a second `GovernedActionRun`
  row. The connector is not called twice, so no duplicate side effect — but
  the ledger shows two runs for one logical action, and "never dispatches a
  second create" is exactly what that slice claims. Fix before phase A, or
  after phase B?
- **CI-RED-2:** three chromadb CVEs, and 1.5.9 is the latest release — there
  is nothing to upgrade to. Options: a dated ignore (the pattern three earlier
  CVEs follow), stay red, or stop depending on chromadb — which is phase D
  (the pgvector spike) arriving early with one more argument behind it.

Until one of them is answered, CI stays red. That is preferable to unknown,
and preferable to a green achieved by lowering a gate.

## Next action

Phase A (wire the shipment-status
shadow into `/api/ask`) and phase B (label 100 real cases) run in parallel;
B needs Q2 answered, A does not.

## Gate for phase 0

```bash
cd /d/RAG_new
git remote -v                                          # non-empty
gh run list --limit 3                                  # CI status known
ls *.md | wc -l                                        # <= 8
grep -n 'pricing_snapshot_date' config/providers.yml   # present
python -m pytest tests -k "pricing or providers" -q    # green
grep -n 'graceful skip' scripts/eval_gate.py           # empty
```

## Links

- Roadmap and what is frozen — [`ROADMAP.md`](ROADMAP.md)
- One row per slice, with evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Task queue — [`BACKLOG.md`](BACKLOG.md)
- Removed/deprecated surfaces — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- History (do not plan from it) — [`AGENT_STATE.md`](AGENT_STATE.md)
