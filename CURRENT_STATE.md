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
- **The kernel is not wired into the product.** `/api/ask` has not changed
  since the fork:
  `grep -rlE "from (resolution|knowledge|actions)|services\.session" api/ agent/`
  returns nothing. Phase A changes this.
- **Zero real labelled cases.** All 17 resolution scenarios are synthetic;
  verified-resolution yield is 1/17. Phase B changes this.
- **Full unit suite green locally** (2026-08-24, Windows): 2134 passed, 4
  skipped, coverage 76.05% against a gate of 72. Widening the coverage source
  to the kernel packages raised the number, not lowered it. The Postgres
  adapters read low in unit scope (`actions/postgres.py` 0%,
  `knowledge/postgres.py` 0%, `resolution/adapters/postgres.py` 29%,
  `services/session.py` 44%) because the integration job exercises them and
  runs without `--cov`.
- **First CI run is in flight** — the number above is local, not CI.

## Phase 0 — in progress

| # | Item | Status |
|---|---|---|
| 0.1 | Private repo, push, `freeze-2026-08-23` tag | done — Q1 answered: separate private repo |
| 0.1b | First CI run green/red, honestly recorded | **open** — `ci.yml` is on the remote but has not registered yet |
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

## Next action

Get the first CI run to happen and record its result honestly — green or red,
both acceptable; "unknown" is not. Then phase A (wire the shipment-status
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
