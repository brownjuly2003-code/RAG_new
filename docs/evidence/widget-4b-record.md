# The widget on the 4B — R1 and ten answers through `/api/ask` — 2026-10-26

What the widget (`/api/ask`, the agent graph) does on its own answers on the production model:
one request with `RAG_ENV=production` for R1, then ten with `RAG_ENV` unset, by the rules
[`widget-4b.md`](../specs/widget-4b.md), registered with the tools in `47e2d71` before the first
request ([`PLAN.md`](../../PLAN.md) stage 3, step 4). No judge call, no change of product code;
2026-10-26 15:13–20:27 UTC on the Mac, 5 h 14 min.

Record: [`reports/widget-4b/4f48fed/record.json`](../../reports/widget-4b/4f48fed/record.json)
and its [rows](../../reports/widget-4b/4f48fed/rows.jsonl), written by
[`reports/widget-4b/tools/widget_record.py`](../../reports/widget-4b/tools/widget_record.py).
Checked by [`tests/test_widget_4b_artifact.py`](../../tests/test_widget_4b_artifact.py): every
number of the record is read again from the rows; each run names the stand, the model and the
registered tools by SHA-256; the questions are the spec's, in order; the rows hold ids, labels,
counts and seconds only; the tables below are built from the record.

## Provenance and method

- **Stand** `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1` at `/Users/julia/RAG_new_chat_4f48fed`,
  `qwen3:4b-instruct-2507-q4_K_M` (digest `0edcdef3…`), the code defaults (the 3,600-s ceiling,
  the CPU, `RAG_LLM_MAX_CALLS_PER_REQUEST` 24), the aircargo tenant; the stage-2 wrapper
  `live_api.py` times every model call.
- **Requests:** production — `aircargo-matliab-disputed`, `CORS_ORIGINS` and a one-run
  `ADMIN_PASSWORD_HASH` set, never printed; development — cases 1–10 of stage 3's
  [plan](../../reports/handover-signal/d260d95/plan.json) (SHA-256 `30e0a598…`). Each a new
  conversation's first question, one at a time. All 11 delivered (HTTP 200, no client error);
  the series did not stop. Tickets in the database: +1 and +7.
- **Beside each question:** the class V4's chat answer to it had in stage 2b's judge
  ([cases](../../reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl), `a1413cba…`)
  — description only; the widget's answer is its own and was not judged.
- **The call-budget counts** are read from the runs' `api.log` on the Mac (SHA-256
  `7ae7fd2f…` production, `a7e60fac…` development), which the rows do not carry.
- **The Mac was not idle:** the load median 6.2 and 6.5, its maximum 60.8 under other
  projects' runs. The seconds below are under that contention, not the widget's floor.

## R1 and R2

**R1: confirmed.** The production request's evaluation reports `unavailable`, reason
`no_independent_judge`; its `[evaluate]` line reads `independent=False require=True`; it routed
`human` and made a ticket, in 11.4 min. No development evaluation has that reason: all 12 in
the ten requests report `ok`, `independence_not_required`. In production every widget answer
goes to a person whatever its quality.

**R2: not seen on these ten.** No claim extraction came back empty: every claim check that ran
found 4–10 claims.

## The grader

Its defects: 5 of 20 passes (2 `grader_error`, 3 `partial_grader_error`). All five are the
last pass of a retried request, and each is the call budget: `api.log` holds 19 lines
`[grade_docs] LLM error: LLM request budget exceeded (max_calls)` in those five requests and no
other grader error. In the 15 passes it finished, the grader kept all five documents of five.
Stage 3's failure of the batch call (no document graded in 187 contexts of 187) did not show on
the widget's own path.

## The ten

| Question | Route | Ticket | Passes | Model calls | Minutes | V4 chat answer |
|---|---|---|---|---|---|---|
| aircargo-probation-data | human | yes | 2 | 24 | 24.4 | bad |
| aircargo-probation-extend | error_escalation | yes | 2 | 26 | 39.3 | bad |
| aircargo-probation-dismissal | error_escalation | yes | 2 | 26 | 43.2 | good |
| aircargo-dismissal-check | error_escalation | yes | 2 | 25 | 40.8 | good |
| aircargo-dismissal-lawyer | auto | no | 1 | 17 | 16.1 | good |
| aircargo-dismissal-order | auto | no | 1 | 19 | 17.0 | good |
| aircargo-leave-sources | auto | no | 1 | 18 | 19.1 | good |
| aircargo-leave-compensation | human | yes | 2 | 26 | 37.8 | good |
| aircargo-leave-risk | error_escalation | yes | 3 | 24 | 38.9 | good |
| aircargo-matliab-check | error_escalation | yes | 3 | 24 | 22.8 | good |

Routes: `auto` 3, `human` 2, `error_escalation` 5, `timeout` 0; 7 tickets; 9 passes ended in a
`retry`. Seconds: median 1,864.8 (31.1 min), maximum 2,594.5 (43.2 min). By node, the median
of the ten from the rows' `nodes`: the retrieval 648.5 s (its time lands on the `index_manifest`
step, logged inside the retrieve node), the grader 522.0, the claim check 216.2, the generation
132.1, the evaluation 73.3.

## What it says

- **No retry finished.** Seven requests retried after their first pass; all seven ran out of
  the budget of 24 model calls (`config/settings.py:579`). Five ran out in the last pass's
  grader, then in its generation — `Pipeline error escalation: node='generate'`, route
  `error_escalation`. Two ran out at the second pass's claim check —
  `[verify_facts] verifier LLM error: LLMBudgetExceeded`, route `human`. The customer still got
  a delivered response and a ticket, after 22.8–43.2 min against 16.1–19.1 for the three
  answered in one pass. A retry that cannot finish is a product defect.
- **What starts a retry is the claim check, not the evaluation.** The three `auto` answers had
  every claim supported and grounding `verified`. Of the seven retried, four had 1–3 unsupported
  claims (grounding `unsupported`), and three had ten checked claims, 10, 10 and 9 of them
  supported, and grounding `not_verified` — consistent with the claim cap of ten
  (`agent/graph.py:2392`), which marks a truncated check not verified. The evaluation scored
  those first passes 60–100.
- **Against V4's chat classes,** description only: the two questions whose chat answer was bad
  went to a person; of the eight whose chat answer was good, three were answered automatically.
- **The forecast,** written before the first request: R1 confirmed — right; 6–9 of ten routed
  to a person — 7, counting `error_escalation`; at least one retry — right; the grader's defects
  in most passes — wrong (5 of 20, all the budget); a request ≈ 13 min and a retried one ≈ 23 —
  wrong: 16.1–19.1 min and 22.8–43.2 min, under a load median of 6.5, in 5 h 14 min, not
  2.5–3 h.
- Every response not routed `auto` carries `quality_score` 50, a value no evaluation of its
  passes gave.

## What follows

A fix of R1 and of the retry's budget is Julia's word ([`PLAN.md`](../../PLAN.md) §8.3, item 1),
each with its test and its own slice. Outcome C holds for the widget too: no signal is wired,
and the chat and the widget both carry the handover line.

Limits: ten questions and one production request, one stand, one tenant; the seconds are from a
loaded Mac; the classes beside the questions are the chat's answers, not the widget's.
