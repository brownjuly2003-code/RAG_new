# Backlog

A small routing surface, not a task log. The order of work is [`PLAN.md`](PLAN.md) (the one
plan since 2026-10-17); what is true now is [`CURRENT_STATE.md`](CURRENT_STATE.md); progress by
stage and the frozen streams with their unfreeze conditions are [`ROADMAP.md`](ROADMAP.md).

## Current queue

- **[`PLAN.md`](PLAN.md) stage 4 with V4: step 2b, the continuation on stage 3's 80 labelled
  answers, read 2026-10-29 — not held on the catches, the default stays `classic`
  ([record](docs/evidence/stage4-step2b-record.md)); stage 7's probe read, G2 failed, E stops
  ([record](docs/evidence/stage7-entity-probe-record.md)); item 4's window timed
  2026-10-30, 3,584 faster on 12 of 12 ([record](docs/evidence/stage4-step4b-record.md)); item 5
  under her cap `cache-ram = 1024` read 2026-10-30, the swap holds, the limit not adopted
  ([record](docs/evidence/stage4-step5-record.md)); item 5a's INT8 read 2026-10-30, `int8`
  passes, its five changes on 307 of the 400 ([record](docs/evidence/stage4-step5a-record.md));
  the n-gram lever closed 2026-10-30, `NOT_EVIDENCE` ([record](docs/evidence/stage4-step5a-ngram-record.md));
  INT8's short live series in the chat read 2026-10-30, `NOT_EVIDENCE`, stopped in its first
  block ([record](docs/evidence/stage4-step5a-live-record.md)); her «да» to the package 2026-10-30, the code's defaults since `6c52b06`; items 6 and 7 read 2026-10-31, aircargo a detected gain ([record](docs/evidence/stage4-item6-final-aircargo-record.md)); stage 5 read 2026-11-02, holds, WixQA's M1 good a detected fall ([record](docs/evidence/stage5-final-external-record.md)); V6 (stage 5б) on the Mac since 2026-11-02**: stage 3
  stays at outcome C — the handover line under every answer; the encoders and Horizon guard base
  in between ([record](docs/evidence/encoder-checkers-record.md)); stage 3б closed 2026-10-28,
  V5 not adopted ([record](docs/evidence/answer-prompt-v5-record.md)). The widget's R1 and
  retry-budget fixes wait for her word. One measurement on the Mac at a time.
- **Dated:** 2026-11-24 — review the three ChromaDB CVE ignores (ADR 0008; 2026-10-24: no
  fixed release). The npm exception GHSA-ch52-4w7c-c8xp was removed 2026-10-24 with
  `http-cache-semantics` 4.3.0, not a fix but outside its range (ADR 0009's log).
- **Locks refreshed 2026-10-28:** CI's `pip-audit` found 7 new advisories in `authlib` 1.7.0;
  the floor `authlib>=1.9.1` moved both locks to 1.9.1 alone, and the audit is clean again
  (5 ignored). The OIDC and auth tests and a client smoke passed on authlib 1.9.1 on the Mac;
  the Mac's unit suite, both CI mypy commands, bandit and DEP-01 pass. Pushed 2026-10-28 with
  `7caaf21` after ci_local PASS: the Linux lock installed and the site build on astro 7.3 passed.
- **Locks refreshed 2026-10-25:** CI's `pip-audit` on `requirements.lock` clean (aiohttp,
  certifi, filelock 3 → 4, opentelemetry, pypdf, setuptools), the npm gate DEP-01 PASS (astro
  7.2 → 7.3 with markdown-remark, dompurify, fast-uri, undici, vite, zod). Not gated: the dev
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
