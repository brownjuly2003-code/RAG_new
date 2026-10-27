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
- **One yes/no for Julia is asked in this session's last message:** stage 3b's judge, 620
  requests, ≈ $116–130, ≈ 8–10 h. No grade before her «да». The WixQA plans can start once
  WixQA's tenth batch is done, beside the chain.
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
2. **After her «да» to the judge:** the previous handoff's step 11 — summaries, private copies,
   plans with SHA-256 committed before the first grade, the judge, bridges, the harm check after
   each key, the record.
3. **During the judge, B's Part 1** on the Mac, only after the gate checkout is synced to
   `3a9f942` or later and only while nothing else measures (step 11 of the previous handoff;
   `parity`, then `score`). Its last sync shipped `3a9f942`'s content just before the commit;
   sync again before Part 1.
4. Without her «да»: V5's answers wait; nothing is graded, and stage 3b has no record.

## Lessons

- **A test's numbers are read against the tool's rule before the first run.** The forecast
  factor of three was in the tool and the spec; the test's comment had assumed one.
- **A finished run is read before it is described.** The handoff's guess (budget at the claim
  check) held for two requests; the record showed five more at the generation and the grader's
  defects as the same cause.
