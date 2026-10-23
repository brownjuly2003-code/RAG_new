# Session handoff — 2026-10-23 — stage 2 answers collected and published

Read with [current state](../../CURRENT_STATE.md), [the plan](../../PLAN.md) stage 2 and the
[registered spec](../specs/stage2-four-corpora.md). The two handoffs of 2026-10-22 — the
[pause](session-handoff-2026-10-22-stage2-paused.md) and the
[resume](session-handoff-2026-10-22-stage2-resume.md) — are history now; nothing in them is
still running.

## What matters to understand

Stage 2 measures the fixed chat path on four corpora before any product change: 100 aircargo
answers (part 1), retrieval without the answer model on 415 questions (part 2), the graph lane
from GR-3's archives (part 3) and 300 answers on the three external bases (part 4). Part 5 is
the combined record — the first answer-quality numbers on the customer's path.

**Every measurement on the Mac is done.** Part 4's last batch finished 2026-10-23 04:32 UTC.
What remains needs the registered judge, `claude-opus-5-5` at effort `max` through
`evaluation/isolated_request.py`: part 2's aircargo context judge (plan frozen in `77795a3`,
130 requests) and part 4's answer judge (three plans of 115 requests, one per base). Julia
said on 2026-10-21, and again on 2026-10-22, that Claude is unavailable; grading waits and no
replacement judge is allowed. So stage 2 stays open, and stage 3 (handover signals) starts
from the same 100 aircargo answers only after it.

## Done this session

- Read the resume worker's status: `ATTACHED_ALL_BASES_COMPLETE exit 0`, then
  `LOCAL_ALL_BASES_COMPLETE exit 0` and `WINDOWS_KEEP_AWAKE_RELEASED`; status `complete`,
  300 answers.
- Verified the private export `D:/RAG_new_stage2_private/p4/resume-20261022/`: its manifest
  (20 files) and every one of the 1,356 raw archive members by SHA-256; 300 case files; 30
  counted batches, each runner exit 0. ConditionalQA's p2/p4 summaries are byte-identical to
  those captured at the pause; the rewritten p2 files differ from the published retrieval
  baseline only by the parity field.
- Published the sanitized summaries byte for byte as
  `reports/stage2/external-answers-20261023/` (12 files plus `manifest.json`, which also pins
  the private archive's SHA-256), the capsule
  [`stage2-external-answers.md`](../evidence/stage2-external-answers.md), the test
  `tests/test_stage2_external_answers_artifact.py` and one `EVIDENCE_INDEX.md` row.
  Operational scripts: `.tmp/stage2/publish-20261023/` (`publish.py` refuses an existing
  folder; do not rerun it).

## The numbers, and how to read them

Per base: ConditionalQA, WixQA and MultiHop-RAG 100 answers each; routed to a person 27, 24
and 33; median total 253.1, 256.4 and 275.0 s. All 300 answers came in the question's
language; prompt parity with part 2 is 100/100 per base; no path break and no cap reached.

These are collection facts and product behaviour, not quality. The route follows the model's
self-score (below 80 → a person, true for all 300); whether a route was right is stage 3's
question. The times span three days of runs and are not a speed measurement (stage 4).

## Once Julia decides

- **Claude available again:** probe the route and both usage windows once
  (`.tmp/stage2/s2_route_probe.py`, focused venv), size the stream by the shorter window
  (≈ $0.11 and ≈ 45 s a request; 475 planned requests before re-asks), then run part 2's
  frozen context plan and, per base, freeze and run part 4's plans by the spec's «The judge».
  Export with `judge_export.py`, then part 5. Mac not needed.
- **Claude stays unavailable:** nothing in stage 2 can close. Stage 3's step 1.3 of the
  [handover-signal plan](../specs/handover-signal.md) — the signals on the 100 aircargo answers,
  5–17 h of Mac — needs only part 1's answers and part 1's judge record, which exist. The plan
  orders stage 3 after stage 2, and the Mac was released for part 4 only, so starting it
  is her word.
- **Push:** nothing is pushed since `172620f`. Before any push: the full Mac unit suite, mypy,
  bandit and dependency audits ([`CURRENT_STATE.md`](../../CURRENT_STATE.md) «CI and pushes»).

## State at the end

The Mac is idle: load about 1.6, Ollama holds no model, ports 8002 and 55433 free, no
measurement process. The frozen stand `/Users/julia/RAG_new_chat_5e308fe/` and the index root
`/Users/julia/RAG_new_external_s1` stay as they are. Untracked `demo/phase-e-raw.webm` and
`reports/ask100/` are not this work; leave them.

## Verification

Through the Mac gate on the synced tree of this commit: the new test, the neighbouring
artifact tests and the three docs tests (44 passed after the fixes), then the whole unit suite
without `tests/integration` — 5,950 passed, 124 skipped, 589 s. Only this handoff's text
changed after that run.

## Glossary

- **Batch** — ten registered questions on a fresh API; counts whole or not at all.
- **Path break** — a missing answer, a non-200 status, a lane with no candidates, a failed
  rerank or no documents; any one stops the work.
- **Parity** — the answer's stream prompt has the same SHA-256 as part 2's retrieval prompt
  for that question, so retrieval numbers describe the context the answer saw.
- **M1/M2/M3** — the judge's answer support and completeness, agreement with a reference
  answer, and gold coverage of the sent context (M3 needs no judge).

## Lessons

- A re-derived summary over preserved runs reproduced the pause capture byte for byte; compare
  manifests before trusting a resume.
- Settings hashes differ per batch only by each run's trace and index-copy paths; the test
  pins that, so a real configuration change would fail it.
- `4fe4aaf` shortened «CI and pushes» in `CURRENT_STATE.md` and dropped the CVE-2026-9856
  bullet that `tests/test_transformers_cve_floor.py` requires: the suite was red at HEAD with
  only docs tests run. The bullet is back. Before rewriting a root `.md`, grep `tests/` for it.
