# Backlog

A small routing surface, not a task log. The order of work is [`PLAN.md`](PLAN.md) (the one
plan since 2026-10-17); what is true now is [`CURRENT_STATE.md`](CURRENT_STATE.md); progress by
stage and the frozen streams with their unfreeze conditions are [`ROADMAP.md`](ROADMAP.md).

## Current queue

- **[`PLAN.md`](PLAN.md) stage 1 — the defects found, fixed first** (Julia, 2026-10-17:
  «поставить в приоритет»). The list is in `CURRENT_STATE.md`, «Known defects»; each fix is a
  commit with a test, a change to the chat path also an E2E test on one question per tenant.
  The indexes of the four corpora are rebuilt as a new generation beside the old (Julia
  agreed 2026-10-17). Nothing else runs on the Mac before it.
- **Dated:** 2026-10-24 — review the three ChromaDB CVE ignores and the npm advisory
  GHSA-ch52-4w7c-c8xp; 2026-11-03 — the npm exception expires, and from 2026-11-04 the Pages
  build and the unit suite are red until it is renewed or removed (ADR 0009).
- **Blocked on data, not on work:** phase B needs real shipment-bound requests (Q2b,
  [`PLAN.md`](PLAN.md) §6). Do not manufacture fixture cases to make a gate pass.
- **Chroma collections built before `534612e`** keep an unpersisted write-ahead-log tail until
  rebuilt ([rerun after the fix](docs/evidence/chroma-restart-stability-after-fix.md)); stage 1's
  new generation is built after it.

A slice counts only under the rule in [`CLAUDE.md`](CLAUDE.md): observable `/api/ask` or UI
behaviour with an E2E test, more real labelled cases, or a newly published number with
provenance. The autopilot planner reads this file; the queue is `PLAN.md`'s stages, so there is
no separate autopilot task list here.

## History

- This file before the tidy-up of 2026-10-17, with the quality thread's slice log (P1, P1b, P2,
  T-55…T-78, the external bases) and the MyFlow tree-pinning gap of 2026-09-08…10 —
  [`archive/docs/state/backlog-through-2026-10-17.md`](archive/docs/state/backlog-through-2026-10-17.md).
- The former 22 KB backlog, with inherited CI analysis and superseded autopilot tasks —
  [`archive/docs/status/backlog-through-2026-08-27.md`](archive/docs/status/backlog-through-2026-08-27.md).
  Evidence, not a source of new work.
