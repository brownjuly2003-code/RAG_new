# Which answers go to a person: the handover-signal plan

Status 2026-10-17: **named, not run;** Julia accepted the reading the same day («давай
так»). No answer, verdict or signal of this plan exists yet. Since 2026-10-17 it runs as
[`PLAN.md`](../../PLAN.md) stages 2 and 3: after `PLAN.md` stage 1's fixes all 100 answers anew on the
fixed code (the 30 of 2026-10-16 become history, the 70 on `19beeb1` are cancelled), then the
judge and the signals on all 100 — no separate pilot. A
cold read of the first draft by a fresh agent found nine problems; this text answers them
(the corrections are listed [at the end](#what-the-cold-read-corrected)). Each stage's
`plan.json` is committed before its first request, as in the records it follows
(`reports/chat-route-replay/7a99c45/`, `reports/chat-live-4b/19beeb1/`).

**Numbering.** Stages 1.0–1.4 and stage 2 below are this plan's own («signal stages»):
signal stage 1 runs inside `PLAN.md` stages 2 and 3, signal stage 2 on WixQA. A stage of
the project plan is always named with the file, «`PLAN.md` stage N».

## Why

On 2026-10-16 Julia asked for the current metrics, «в частности % передачи вопросов
оператору». The session replayed the chat's rule on the 100 judged answers of her production
model: 2 of 100 go to a person — and 10 of the judge's 12 bad answers go to the client, because
the model scores 89 of its 100 answers 100. On 2026-10-17 she wrote: «А не был настроен сигнал
ответа человеку??? Давай сначала замерим. Меня очень печалит, насколько проект непродуман. Ты
не можешь написать грамотный план?»

The plain answer to her question: two signals are configured — one in the chat, a stricter one
in the widget — and neither was ever checked against answers known to need a person. Their
thresholds (80 points, relevance 0.8, factuality 80 %) are design values, not measured ones.
This plan measures them, and cheaper alternatives, on the answers the chat actually gives.

## What the product does today

Read in the code at `d21a2a9`, at the settings the live stands ran with (`RAG_ENV` unset, so
development; `MODEL_ROUTING_ENABLED` false, the default).

**The chat** (`/api/ask/stream`, the production surface). After the answer, the model that
wrote it scores it from 1 to 100 (`build_self_eval_prompt`); at `QUALITY_THRESHOLD` 80 or more
the route is `auto`, below it `human`. When that call fails or returns no number, a length
heuristic gives 70 and the route is `auto` (`api/routers/conversation.py:2292`, `:2357`). A
`human` answer is still shown, with «Передать оператору» beside it
(`static/chat.inline.js:596`); no ticket opens by itself. The header's «Связаться с
оператором» button is there under every answer (`static/chat.html:998`).

**The widget** (`/api/ask`, the graph). The classifier is off by default, so every question
takes the full path: retrieval, the grader (`grade_docs`, one model call over the documents),
the answer, the claim check, the self-score. `route_or_retry` (`agent/graph.py:2852`) routes
`auto` only when all of these hold, and otherwise retries up to twice (rewrite the query,
retrieve, write a new answer), then routes `human` and opens a ticket:

- the self-score is 80 or more;
- relevance is 0.8 or more. On this path the documents carry no retrieval score, so relevance
  is the share of the retrieved documents the grader keeps (`agent/relevance.py:137`);
- `grounding_allows_auto` (`agent/grounding.py:230`): no knowledge gap — fewer than two
  documents, factuality below 50, or one of six decline phrases (`_is_knowledge_gap`,
  `agent/graph.py:741`); and the claim check (`verify_facts`, `agent/graph.py:2274`) — the
  model lists the answer's claims, up to 10, and judges each against the documents — finds
  every claim supported **and** bound to a document the answer cites as `[N]`, with
  factuality 80 or more.

**Found by reading; stage 1 confirms or refutes each:**

- **R1.** With `RAG_ENV=production`, judge independence is required by default
  (`config/settings.py:558`); with one model serving everything there is no independent judge,
  the self-score fails closed (`agent/judge_policy.py:113`), and the widget routes **every**
  answer `human` (`agent/graph.py:2904`). The chat does not use that rule. Checked by one widget
  request under each `RAG_ENV` with the instruments (stage 1.0).
- **R2.** An answer with no factual claims (the extractor says `NONE`) is "verified" with
  factuality 0, which `_is_knowledge_gap` turns into a gap: `human`, against
  `grounding_allows_auto`'s own comment that it may go `auto`.
- **R3.** A claim counts only when bound to a cited `[N]`. The 4B cited in 23 of the rerun's
  30 answers on 2026-10-16, so about one answer in four fails the check for want of a
  citation, right or wrong.

## What is measured, and what is withdrawn

- The chat's rule on the generator screening's 100 judged answers: 2 `human`; 10 of 12 bad
  answers `auto`; at a threshold of 100 instead of 80, 11 `human` (3 bad, 5 partial, 3 good)
  — record `reports/chat-route-replay/7a99c45/`, EVIDENCE_INDEX.
- The live chat, 51 answers on 2026-10-16 (30 questions, asked 1–4 times): all `auto`, 49
  scored 100 and two 95 — `reports/chat-live-4b/19beeb1/`.
- **Withdrawn:** the session's recommendation of 2026-10-16 to replay the widget's rule on the
  same 100 screening answers. The screening's prompt is not the chat's, and none of its 100
  answers cites `[N]`, so the claim check would refuse every one of them (R3) — a number about
  the screening's prompt, not the product. The measurement needs answers as the chat writes them.

## Question

Which signal marks the chat's answers that need a person, how many good answers does it mark
with them, and how much time does it add to an answer on the Mac?

- **The judge** (`scripts/generator_answer_judge.py`, the session's model through the
  registered route `evaluation.isolated_request`) grades an answer against the documents the
  assistant saw — not against a reference answer, which the dataset does not hold. Its classes
  (`classify()`): *good* — complete and fully supported, or a right decline; *partial_ok* —
  supported but incomplete; *bad* — an unsupported claim, a defect, no answer, or a decline
  when the documents held the answer.
- **Needs a person** — the target: every *bad* answer, and every decline, right or wrong: a
  right decline is good work by the assistant, but the client still has no answer. Partial
  answers are reported apart and are not the target. The case's expected keywords
  (`answer_contains`) are reported beside each verdict as a second, cruder view; they do not
  define the target.
- What the judge cannot see: an answer faithful to documents that are themselves wrong or
  outdated. That stays outside this measurement.
- **Per signal:** *caught* — target answers marked / all target answers (Wilson 95 %);
  *over-marked* — good, non-declining answers marked / all of them; *marked* — all answers
  marked; *added time* — median seconds per answer on the Mac.

## Reading — frozen in stage 1's `plan.json`, before its first verdict

In the chat a marked answer is still shown, with the operator button; an unmarked bad answer
reaches the client with no hint. A miss costs more than a needless button, so the reading puts
catching first. The session proposed it and Julia accepted it on 2026-10-17 («давай так»):

- **no reading** if fewer than 15 of the 100 answers are target answers: stage 2 adds answers
  first;
- **worth wiring:** caught at least 2 of 3 with the Wilson lower bound at least 1 of 3, and
  over-marked at most 1 of 3;
- **useless:** the Wilson upper bound of caught below 1 of 2, or over-marked above 1 of 2;
- **in between:** a candidate for stage 2.

A threshold chosen on stage 1's answers (a self-score of 100, a rerank score) stays a
candidate until stage 2 confirms it on other answers. The forecast written now, so that the
result can surprise it: S1 marks almost nothing — 0 of the 51 live answers scored below 80,
and S1′ would have marked 2.

## Signals

All computed through the repository's code at the stand's commit, the 4B served at the code
defaults, `RAG_ENV` development; none is re-implemented. Each is a yes/no "mark for a person".

- **S1** the chat's rule as it runs: self-score below 80, or the heuristic's 70 never marks —
  recorded live with each answer; the heuristic answers are counted.
- **S1′** the same score below 100 — the threshold the replay pointed to.
- **S2** the widget's claim check as it runs: `verify_facts` on the answer and the documents
  the 4B saw, marked unless `verified`.
- **S3** the claim check's verdicts alone: marked when any listed claim is UNSUPPORTED,
  citation binding ignored — separates the model's check from R3.
- **S4** the widget's relevance: `grade_docs` on the answer's documents, marked below a kept
  share of 0.8.
- **S5** a decline: the answer says it cannot answer — `_is_knowledge_gap`'s phrases plus the
  answer prompt's own wording «ответить нельзя» (`agent/prompts.py:20`); no model call. A new
  signal: the product's gap check also needs factuality, which only S2 produces.
- **S6** the widget's first pass: `route_or_retry` on the state S1, S2 and S4 build, the gap
  with S2's factuality — marked unless `auto`. A retry writes a new answer no judge graded, so
  retries are not replayed: S6 gives the most answers the widget's first pass would mark.
- **S7** retrieval's confidence: the reranker's top score for the question, retrieval rerun
  alone at the same index and code; it must return the stream prompt's documents in its order,
  or S7 stops. No model call in the product — the reranker runs anyway; its threshold is chosen
  on stage 1 and confirmed on stage 2.

## Stages

### 1.0 The instruments — preparation

Since 2026-10-17 the instruments are built in [`PLAN.md`](../../PLAN.md) stage 1, beside the
fixes, and checked on the first answers of 1.1; the signal tool's first five answers give its
forecast in 1.3; no pilot table is published. What follows is what the instruments
are and what they cost.

The rerun of 2026-10-16 (`qwen3-4b-instruct-q30-r2`, code `19beeb1`) holds 30 answers in the
chat's own form — cases 1–30 of `evaluation/curated_cases_aircargo.jsonl` — each with its
exact stream prompt, the documents the 4B saw, in its run directory on the Mac (90 prompt files,
checked 2026-10-17; not in the published record). Stage 1.0 builds and checks the instruments:

- **the judge's adapter.** The judge script takes benchmark reports that share one set of
  contexts; a chat answer brings its own documents, parsed from its stream prompt. Blind to the
  route and the signals; 15 retests for the judge's stability, as in the screening.
- **the signal tool.** Per answer: the grader (one call), the claim extraction (one), one call
  per claim (up to 10). The documents come first in `VERIFY_CLAIM_PROMPT_V1`, so Ollama may
  reuse the cached prefix after the first claim — measured, not assumed. Ollama's runner grows
  about 312 MB a request and only an unload frees it, so the tool unloads the model after every
  five answers.
- **R1 checked** by one widget request under each `RAG_ENV` (production also needs explicit
  `CORS_ORIGINS`, or the API refuses to start).

Forecast: per answer 3–10 min (the grader's and the first claim's reading about 65 s each, the
others 10–65 s each); the cap for the first five answers 30 min each (3 × 10 min), then 3 × the
median of the first five. Retrieval rerun alone about 30 s a question (median 27.6 s with no
model loaded, `reports/chat-live/33d4b42/`). Its Mac time is part of 1.3; 45 judge requests.

Output: the instruments and the forecasts for 1.1–1.3; no table is published before 1.4
(cases 1–30 hold no customs question and 22 of the set's 66 out-of-scope ones, so a table on
them alone would say little about the 100).

### 1.1 The 100 answers — preparation for 1.4

All 100 cases in file order through `/api/ask/stream` on a stand of the commit that closes
[`PLAN.md`](../../PLAN.md) stage 1 — so all 100 answers come from one commit — at the code
defaults, each question sent as a web-chat visitor's first. Batches of ten, each on a fresh
API with the model unloaded before it. Forecast 340 s for a batch's first question, 400 s for
the others; the stop rule at 3×. About 11 h.

### 1.2 The judge on the 100

The adapter of 1.0 unchanged; about 115 requests with the retests.

### 1.3 The signals on all 100

The tool unchanged; its first five answers give the forecast: 100 × 3–10 min, about 5–17 h.

### 1.4 The result on 100 — rule (c)

Record `reports/handover-signal/<commit>/`, a test that derives every number from it, one
evidence row: per signal caught, over-marked, marked and added time; R1–R3 confirmed or
refuted with their counts; the reading applied as frozen.

### 2 WixQA — when stage 1 gives no reading, a signal in between, or a chosen threshold

The open part of WixQA — its 142 `tuning` questions, answered in [`PLAN.md`](../../PLAN.md)
stage 2; the 200 ExpertWritten questions are the locked part (`evaluation/external_parts.json`),
opened once in stage 7 and never used to choose a threshold — under a plan of its own, named
before its first request. Not the same protocol: the judge's instructions name an air-cargo
assistant answering in Russian, and S5's phrases are Russian, so stage 2 brings an English
judge prompt with its own retest and English decline wording. The answers come from stage 2; the expensive signals on them about
4–12 h of the Mac per hundred.

## What each outcome means, and what Julia is told

- **A. A cheap signal is worth wiring** (S1′, S5 or S7 — no extra model call): wire it into the
  chat — rule (a), an E2E test that an answer it marks shows the operator button — then check
  it live.
- **B. Only the claim check or the grader is worth wiring** (S2, S3, S4 or S6), a few minutes
  on top of about five: Julia chooses — wait for it before the answer shows; show the answer at
  once and the button when the check ends; or check only some answers.
- **C. Nothing is worth wiring:** said plainly — on this Mac, with the 4B, no automatic signal
  finds the answers that need a person. Her options: a plain line under every answer pointing
  to the operator button the header already has, routing by topic (secrets, legal questions),
  or a stronger checker on other hardware.
- **R1 and R2, if confirmed,** are defects of the widget, fixed with a test on her word; the
  chat is the production surface, and the widget waits behind it.

## Where this sits in the project plan

- [`PLAN.md`](../../PLAN.md) stages 2 and 3 (formerly ROADMAP thread M step 5); stage 4, the
  speed levers, waits for it.
- It takes over the routing part of phase B: B.4, «Judge calibration 10 → ≥40 double-annotated
  routes», never started, and the calibration routes of open question Q2b. Both asked for routes
  graded by people, which D11 (2026-10-03) closed; here the session's model judges. This is the
  session's reading, said to Julia on 2026-10-17. B.2, B.3 and B.5 stay blocked on
  shipment-bound data, which this plan does not touch.
- Where a measured floor goes: the chat reads `QUALITY_THRESHOLD`; the widget can take its
  floors from a calibration artifact (`RAG_CALIBRATION_ARTIFACT`, `agent/calibration.py:372`),
  which no measurement has written yet. Outcome A writes its threshold where the wired surface
  reads it, with the record's provenance.
- The quality thread's campaign (`archive/docs/specs/plan_03_10_26.md`) is stopped by `PLAN.md` §7;
  retrieval mechanisms are its stage 7.

## What this plan does not do

- Change a route, a threshold or a default before the result.
- Use a model other than the 4B in the product's role, or any other vendor's model in any role
  (D12); or a person to grade (D11) — the judge is the session's model.
- Tune a threshold and confirm it on the same answers.
- Run beside the speed levers ([`PLAN.md`](../../PLAN.md) stage 4): the Mac takes one
  measurement at a time, and stage 1.1's 100 answers are also their baseline.

## Order and cost

| Stage | What | Mac | Session | Counts as |
|---|---|---|---|---|
| 1.0 | the instruments, checked on the first answers | in 1.3 | judge adapter, signal tool, 45 judge requests | preparation |
| 1.1 | the 100 answers ([`PLAN.md`](../../PLAN.md) stage 2) | ~11 h | the stand, the watch | preparation |
| 1.2 | the judge on the 100 | — | ~115 requests | preparation |
| 1.3 | the signals on all 100 | 5–17 h | — | — |
| 1.4 | the result on 100 | — | record, test, evidence row | rule (c) |
| 2 | WixQA's open part, if needed | 4–12 h per hundred | its own plan | rule (c) |

Stage 1: two to three days, most of it the Mac's nights.

## What the cold read corrected

The first draft (2026-10-17, uncommitted) was read cold by a fresh agent on the session's
model. It found, and this text fixes:

1. The judge grades against the documents, has no reference answer, and counts a right decline
   as good — the target is now *bad or declined*, and "reference" is gone.
2. The draft's R1 ("a simple question always goes to a person") cannot happen: the classifier
   is off by default and returns `unknown` without a call (`agent/graph.py:1288`), and the
   initial state has `fact_verification_skipped` false (`agent/state.py:216`). Dropped; the
   production-mode finding is the new R1.
3. The widget's relevance is the grader's kept share, not a mean retrieval score: no retrieval
   code writes a score into the documents' metadata. S4 now runs the grader; S6 includes it.
4. The chat's heuristic 70 routes `auto` when the self-score fails — now part of S1.
5. The product's gap check needs factuality, so it is no cheap signal on its own — S5 is a new
   decline signal, and the prompt's own decline wording is in it.
6. The sample: the chat's share of bad answers is unknown — a minimum of 15 target answers,
   reading by Wilson bounds, S1's forecast written before the run.
7. No unload cadence, forecast or stop rule for the pilot and stage 1.3 — added.
8. Stage 2 cannot reuse the Russian, air-cargo judge prompt — it gets its own.
9. Wording: the 1–100 scale, 23 of the rerun's 30 answers cite, the header's operator button
   exists, and S6 counts the most answers the widget's first pass would mark.
