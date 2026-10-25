# Backlog

A small routing surface, not a task log. The order of work is [`PLAN.md`](PLAN.md) (the one
plan since 2026-10-17); what is true now is [`CURRENT_STATE.md`](CURRENT_STATE.md); progress by
stage and the frozen streams with their unfreeze conditions are [`ROADMAP.md`](ROADMAP.md).

## Current queue

- **[`PLAN.md`](PLAN.md) stage 3 — the handover signals** on V4's 100 aircargo answers (stage
  2b closed 2026-10-25, V4 adopted: [its record](docs/evidence/answer-prompt-v4-record.md)),
  by the [handover plan](docs/specs/handover-signal.md) and the V4 spec's «Then»; S3 reads
  aircargo's unsupported claims. One measurement on the Mac at a time.
- **Dated:** 2026-11-24 — review the three ChromaDB CVE ignores (ADR 0008; 2026-10-24: no
  fixed release). The npm exception GHSA-ch52-4w7c-c8xp was removed 2026-10-24 with
  `http-cache-semantics` 4.3.0, not a fix but outside its range (ADR 0009's log).
- **Locks refreshed 2026-10-25, local:** CI's `pip-audit` on `requirements.lock` clean (aiohttp,
  certifi, filelock 3 → 4, opentelemetry, pypdf, setuptools), the npm gate DEP-01 PASS (astro
  7.2 → 7.3 with markdown-remark, dompurify, fast-uri, undici, vite, zod). Before the push: the
  Mac's guard tests and the site build; CI alone installs the Linux lock. Not gated: the dev
  lock's test-only `httpx2==2.10.0` (three advisories); `CVE-2025-3000` matches nothing.
- **Blocked on data, not on work:** phase B needs real shipment-bound requests (Q2b,
  [`PLAN.md`](PLAN.md) §6). Do not manufacture fixture cases to make a gate pass.
- **Chroma collections built before `534612e`** keep an unpersisted write-ahead-log tail until
  rebuilt ([rerun after the fix](docs/evidence/chroma-restart-stability-after-fix.md)); stage 1's
  second generation, which the chat now reads, is built after it.

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
