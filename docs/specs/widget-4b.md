# The widget on the 4B: R1 and ten answers through `/api/ask`

Status 2026-10-26: **registered before the first request**, with the tools that run and read
it and their tests ([Records](#records)). [`PLAN.md`](../../PLAN.md) stage 3, step 4: «R1 и R2
подтверждаются или опровергаются; исправление — словом Юли, с тестом. Десяток ответов виджета
на 4B даёт его время и маршруты … Их доля пишется в запись»; the
[handover signal plan](handover-signal.md), «R1 checked by one widget request under each
`RAG_ENV`». Julia's «да» of 2026-10-26 took it as part of the second of four items. No judge
call; no change of product code.

## Why

The chat (`/api/ask/stream`) has been measured on the 4B since stage 1; the widget
(`/api/ask`, the agent graph) never answered a question on it. Read in the code, R1: with
`RAG_ENV=production`, judge independence is required by default (`config/settings.py:558`);
with one model there is no independent judge, the evaluation fails closed
(`agent/judge_policy.py:113`, `agent/graph.py:2625`), and `route_or_retry` sends every answer
to a person (`agent/graph.py:2904`). Stage 3 replayed the widget's first pass (S6) on V4's chat
answers: it marked 70 of 100, 43 of the 63 good. What the widget does on its own answers — its
seconds, its routes, its retries, its grader — is unmeasured.

## The stand and the requests

- **The stand** is V4's, `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`, on the Mac at
  `/Users/julia/RAG_new_chat_4f48fed`: its product code is this commit's but for the chat and
  widget pages (the handover line, `60dfd90`) and `scripts/chat_signals.py`, neither on the
  `/api/ask` path. The 4B `qwen3:4b-instruct-2507-q4_K_M`, the code defaults (the 3,600-s
  ceiling, the CPU), the aircargo tenant on a byte-identical copy of its index, as stage 2's
  runs; the stage-2 API wrapper (`live_api.py`), which times the retrieval and every model call.
- **Production, one request:** `aircargo-matliab-disputed` (the 11th question of stage 3's plan)
  on a fresh API with `RAG_ENV=production`. That mode refuses to start without explicit
  `CORS_ORIGINS` and an `ADMIN_PASSWORD_HASH`: the supervisor sets the first to the stand's own
  address and the second to a bcrypt hash of a random secret made for the run, never printed;
  every other setting as in development.
- **Development, ten requests:** the first ten questions of stage 3's plan
  (`reports/handover-signal/d260d95/plan.json`, cases 1–10 of
  `evaluation/curated_cases_aircargo.jsonl`), in that order, on a fresh API with `RAG_ENV`
  unset — the setting every measured run had.
- Each request is a new conversation's first question, as the widget sends it; one at a time,
  the next after the API reports no pipeline in flight. A token per question names the tenant.
  The production request goes first.

## What is recorded

Per request, from the response, the trace (`traces.db`, each node's state as the product logs
it) and the API log; ids, labels, counts and seconds only, never a text of a question, a
document or an answer:

- the route, whether a ticket was made, the quality score and its source;
- the evaluation's judge status and reason, and the API log's `[evaluate]` line
  (`independent=…`, `require=…`);
- the passes: each pass's grader outcome (`doc_grade_outcome`) and kept documents, its claims
  (count, supported, and `NONE` — no claim), its factuality and grounding status, and the
  route it chose (`retry` included);
- the seconds: the whole request, and each node from the trace's step times; the model calls
  and their seconds from the wrapper's rows.

## How it is read — frozen before the first request

- **R1 confirmed** — the production request's evaluation reports `unavailable` with reason
  `no_independent_judge`, its `[evaluate]` line `require=True`, and its route is `human`; and no
  development request's evaluation reports that reason. **Refuted** — the production request's
  evaluation is `ok`. Otherwise **not settled**, with what was seen.
- **R2 seen** — a development answer whose claim extraction found no claim was routed `human`
  as a knowledge gap; otherwise **not seen on these ten** (stage 3 refuted it on V4's chat
  answers).
- **The grader's defects** (stage 3: the batch call graded no document in 187 contexts of 187):
  the passes with outcome `grader_error` or `partial_grader_error`, of all passes.
- **The routes and seconds** of the ten: counts of `auto`, `human`, `timeout`; the tickets; the
  median and the maximum seconds; the passes with a `retry`. Beside each question, the class
  V4's chat answer to it had (stage 3's judge) — description only: the widget's answer is its
  own, not judged.

What it does not decide: a fix. R1's and any widget change are Julia's word (§9), each with its
test.

**Forecast, written before the first request:** R1 confirmed. Of the ten, 6–9 routed `human`
(S6 marked 70 of 100), at least one `retry`; the grader's defects in most passes. A request
≈ 13 min, a retried one ≈ 23 min: the retrieval about 60 s, the grader 274 s and the claim check
137 s (stage 3's medians), the generation about 200 s, the evaluation and the suggested questions
about 110 s; a retry repeats the generation, the claim check and the evaluation. In all
≈ 2.5–3 h of the Mac.

## Order and stop

One run a time, each its own API: the production request, then the ten. A request with no
delivered response — an HTTP error, a `timeout` route (the product's 3,600-s ceiling, inside
3 × the 23-min forecast), a client cap of 4,200 s — stops the series; the questions not reached
are counted and left out. Another project's runs on the shared Mac are not stopped; the load is
recorded every 3 s, as in stage 2.

## Records

- Tools: [`reports/widget-4b/tools/`](../../reports/widget-4b/tools/) — `widget_supervisor.py`
  and `widget_runner.py` (copies of stage 1's supervisor and runner: the runner posts to
  `/api/ask`, the supervisor takes `ENV=production`), `widget.sh` (the two runs) and
  `widget_record.py` (the rows and the record, read from the run folders on the Mac). Their
  SHA-256 are in each run's `launch.json`.
- Tests: `tests/test_widget_4b.py` (the reading on hand-made rows),
  `tests/test_widget_4b_artifact.py` (the record read again from its rows).
- The record: `reports/widget-4b/4f48fed/`, its capsule in `docs/evidence/`, one row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md).
