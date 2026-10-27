# Session handoff 2026-10-27 — the widget read, Amendment 1 registered, V5 running on the Mac

Session of 2026-10-27, from ≈ 13:38 UTC; all times UTC (the laptop's clock is EDT, the Mac's
UTC+3). Previous handoff, whose model, glossary and step 11
still hold: [four items under her «да», the widget running](session-handoff-2026-10-26-widget-running.md).

## Read this first

- **V5's chain runs on the Mac with no session watching it** ([V5 spec](../specs/answer-prompt-v5.md)).
  Launched once at 13:56:16 UTC: `nohup sh $S/v5/v5_chain.sh >> $S/v5/v5-chain.out`, PID 14513.
  WixQA's check passed (100 cases, parity failed 0, same context 81); the first answer took
  114 s, inside the forecast of 110–130 s. Forecast ≈ 3.5 h a key, ≈ 10.5 h in all: the end
  near **00:30 UTC 2026-10-28**, if the idle wait before each key is short.
  - Its log `$S/v5/v5-chain.log` ends with `CHAIN_DONE` or `CHAIN_STOP …`.
  - While it measures: no `sync.py`, no `remote.py`, no tests and no downloads on the Mac.
    Never stop it, and never stop another project's process.
  - Exit codes and what may be run again: the previous handoff, step 9.
- **The judge has her word, in two steps** ([Amendment 1](../specs/answer-prompt-v5.md#amendment-1-2026-10-27-the-judge-in-two-steps),
  `c919a77`, registered before the first grade): the core first — of WixQA, then ConditionalQA,
  its bridge, then its M1 plan, 260 requests — and `v5_core.py`'s step after each base; M2 and
  aircargo (360) only on «go on». The judge pauses at 0.70 of the week (0.57 at 14:05 UTC, reset
  2026-10-31 21:00 UTC). The WixQA plans start once WixQA's tenth batch is done, beside the chain.
- **Nothing is pushed.** `3ef8b54`…this file's commit are local; a push needs her word and the
  checks of the memory note on CI parity.

## What this session did

| UTC | What |
|---|---|
| 13:40 | the widget chain found done: `CHAIN_DONE` 2026-10-26 20:27, all 11 requests HTTP 200 |
| 13:42 | the widget's rows on the Mac, the record on the laptop: **R1 confirmed, R2 not seen** |
| 13:49 | `cda30ee` — the widget evidence: rows, record, [capsule](../evidence/widget-4b-record.md), index row, status files, the 2026-10-26 handoff |
| 13:49 | `3a9f942` — Amendment 1 of the encoder test, with the tool's and the test's SHA-256 |
| 13:44–13:49 | B downloaded (`download_b.py`, 4 min 43 s); both files match the card in size and SHA-256 |
| 13:56 | V5's chain launched |
| 14:05 | usage probe: the week 0.57 used, the five hours 0.09 |
| 14:19 | `c919a77` — the V5 judge in two steps: amendment, `v5_core.py`, its test |

The 109 focused tests of the previous handoff's step 6 passed on the Mac before the commits. One
failed first: `test_the_fresh_writer_resumes_a_file_and_stops_at_three_times_its_forecast` set
a forecast of 1.5 min (a 270-s stop) where its own comment meant a 90-s stop. The test was
fixed to 0.5 min, the tool unchanged; `TEST_SHA` was computed again after the fix.

## Julia's words in this session (UTC)

- ≈ 13:38 «продолжи доработку» — by the previous handoff's next actions.
- ≈ 14:00 «напиши, что это за цепочка V5?» — answered: the evidence-first prompt on V4's saved
  contexts, 300 questions, ≈ 10.5 h, then the judge and the frozen decision table.
- ≈ 14:05 «а судья - это опус?» — answered: yes, `claude-opus-5-5` at effort `max`, stage 2's
  route and instructions; the bridges catch a drift since V4; D12 makes the judge and V5's author
  one model.
- ≈ 14:05 «сейчас лимита немного… Именно опус на макс - мы не переборщили?» — answered: keep
  the judge (a new one breaks the pairing with V4's verdicts), grade in two steps and stop early.
- ≈ 14:10 «хорошо, давай по твоему плану» — the two steps, then the first 260 requests.

## The widget's findings, for the message to Julia

- **R1 confirmed:** with `RAG_ENV=production` every widget answer goes to a person.
- **No retry finished:** all seven retried requests ran out of the 24-call budget — five
  `error_escalation` at the generation, two `human` at the claim check. The grader's five
  defects are the same budget. A retry starts on the claim check; three of seven on the claim cap
  of ten. A fix of R1 and of the budget is her word (§8.3, item 1).
- Seconds: median 31.1 min, on a Mac at load 6.5 — the forecast of 13/23 min was wrong.

## Next actions

1. **Wait for the chain:** a Monitor until-loop on `$S/v5/v5-chain.log` for `CHAIN_DONE` or
   `CHAIN_STOP`; check a key past ≈ 11 h (stop file in the previous handoff, step 9).
2. **The core of the judge, per base (WixQA, then ConditionalQA), once its tenth batch is done:**
   scripts in `.tmp/v5/` (git-ignored), V4's with V5's paths.
   - `sh D:/RAG_new/.tmp/v5/v5_copy_runs.sh 4f48fed KEY`, then
     `sh D:/RAG_new/.tmp/v5/v5_judge_plan.sh KEY` (both plans of a base; aircargo one). Commit
     the printed `PLAN_SHA256` lines with `git commit --allow-empty` before the first grade.
   - the bridge: `$PY D:/RAG_new/.tmp/v5/run_v5_judge.py bridge-KEY` in the background, a
     Monitor on `.tmp/v5/v5-judge.log`; then `sh D:/RAG_new/.tmp/v5/v5_export.sh bridge-KEY`.
     Exit 3 = not counted: the step is `stop, NOT_EVIDENCE`, M1 is not graded.
   - then `run_v5_judge.py KEY-m1` and `v5_export.sh KEY-m1`.
   - the summary on the Mac (`replay.py summary`, the previous handoff's step 11), the
     environment lines, both copied into `reports/answer-prompt-v5/4f48fed/`; then
     `v5_core.py reports/answer-prompt-v5/4f48fed OUT --keys <judged>`. Its step decides.
   - `stop` — stage 3b's outcome, V4 stays; tell Julia. `go on` — M2 of both bases, aircargo's
     plan and its bridge, then `v5_record.py`.
   - Before the core's read is published: `tests/test_answer_prompt_v5_core.py` and
     `tests/test_answer_prompt_v5.py` on the Mac after the chain (sync, then remote.py); the light
     grid check `.tmp/v5/grid_check.py` passed on the laptop.
3. **During the judge, B's Part 1** on the Mac, only after the gate checkout is synced to
   `3a9f942` or later and only while nothing else measures (step 11 of the previous handoff;
   `parity`, then `score`). Its last sync shipped `3a9f942`'s content just before the commit;
   sync again before Part 1.
4. **A stop leaves aircargo's plan and its bridge frozen,** graded after the week's reset for the
   encoders' Part 2 alone (the amendment); their verdicts change no step.

## Lessons

- **A test's numbers are read against the tool's rule before the first run.** The forecast
  factor of three was in the tool and the spec; the test's comment had assumed one.
- **A finished run is read before it is described.** The handoff's guess (budget at the claim
  check) held for two requests; the record showed five more at the generation and the grader's
  defects as the same cause.
- **A registered plan is staged by what can still change its outcome.** The table's row 3 reads
  the core alone, so M2 and aircargo can only add harm or `NOT_EVIDENCE`; grading them first
  would have spent 360 requests that cannot adopt V5.
