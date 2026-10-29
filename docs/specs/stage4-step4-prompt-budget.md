# Stage 4, step 4: a shorter answer prompt — num_ctx below 4,096, read at «sent» on stage 2's lists

Status 2026-10-29: **registered before the count**, with the tool that reads it and its test
([Records](#records)), in `b192fb0`. [`PLAN.md`](../../PLAN.md) stage 4, item 4: «**Промпт короче**
(67 с на 2 270 токенах) и **подсказки** (13 с) — ≈ 1 ч». This is the prompt's half, offline: no
model call, no new retrieval. The live timing and the hints come after
([What comes after](#what-comes-after)).

## Why

The 4B reads an answer's prompt of 2,105–2,380 tokens in 61.7–75.0 s, 28–37 tokens a second, and
the self-evaluation reads it again with the answer: 2,377–2,690 tokens in 65.0–105.1 s
([step 0](../evidence/stage4-step0-record.md#per-request)). Of the chat's median 320 s, 67 s is
the prompt and 68 s the self-evaluation ([`PLAN.md`](../../PLAN.md) §3).

Both are as long as the window lets them be. The chat fits its prompt to
`window_input_limit(num_ctx, 1024)`, 2,636 estimated tokens at today's num_ctx of 4,096: whole
documents while they fit, the first that does not cut to its paragraphs closest to the question,
the rest dropped (`agent/context_window.fit_context_docs`). The self-evaluation reads the
documents the answer was given (`api/routers/conversation.py`). Stage 2's prompts sit at the
limit (the committed export, read 2026-10-29):

| Base | Median, estimated tokens | Cut at 4,096 |
|---|---|---|
| aircargo | 2,589.5 | 98 of 100 |
| MultiHop-RAG | 2,592.5 | 83 of 100 |
| WixQA | 2,235 | 20 of 100 |
| ConditionalQA | 2,181 | 11 of 100 |

The window is `OLLAMA_CONTEXT_WINDOW`, num_ctx on every call. It shortens the prompt on any base
and in any language, with no dictionary or rule of a corpus ([`PLAN.md`](../../PLAN.md) §2).
What it costs is gold the model no longer reads, and that is counted without the model, on stage
2's lists.

## Inputs

The K curve's ([Inputs](k-curve-expanded.md#inputs)): the runs `p2-wixqa`, `p2-conditionalqa`,
`p2-multihoprag` and `p2-aircargo` of stand `5e308fe`, their records and chunk archives on the
Mac, and the committed export `reports/stage2/retrieval-20261021/` by its manifest's SHA-256. Of
a record: `question`, `ranked`, `expanded`, `sent` (the documents the stand's fitting kept, each
with its text and whether it was cut) and `prompt` (the flattened prompt's SHA-256).

And V4's committed answer rows, `reports/answer-prompt-v4/4f48fed/v4-<base>.cases.jsonl` for
aircargo, WixQA and ConditionalQA. A row holds the five's scores to six places, the expanded
characters, and the SHA-256 of the answer prompt the live chat sent.

Stage 2's stand sent `QA_PROMPT_V3`; the code's answer prompt is `QA_PROMPT_V4` (since
`4f48fed`), 249 characters longer. The tool reads V3 from `agent/prompts.py` at `5e308fe` as a
literal, never run, to hold the records to; every window is fitted under V4, today's prompt.

Records and archives are kept only on the Mac, so the tool runs there. It runs in a clean
worktree of the registering commit, not in the gate checkout, which carries the laptop's
uncommitted files. About 3,600 fittings make it minutes, where the K curve took 10.5 s.

## The point at each window

The windows are num_ctx = 4,096, 3,840, 3,584, 3,328, 3,072, 2,816, 2,560 and 2,304. Their input
limits are 2,636, 2,406, 2,176, 1,945, 1,715, 1,484, 1,254 and 1,024 estimated tokens: the
answer's 1,024 output tokens stay. For every window and question, the product's own code:

1. **Documents:** the no-reranker point's expansion on the recorded five. It is the product's
   `HybridRetriever._expand_parents` over the chunk archive, at the run's window, budget and
   overlap. It gives the documents with their metadata: the fitting reads a document's source
   for its label and its header lines when it cuts.
2. **Fitting:** `api.routers.conversation._fit_stream_prompt`, as for the chat's first question:
   an owner of `context_window` = num_ctx, the recorded question, no history. It runs under
   `QA_PROMPT_V4`, set by the product's own override (`agent.prompt_registry.CURRENT_EXPERIMENT`).
   It gives the documents sent, each whole or cut, and the prompt as the provider flattens it.
3. **The point at «sent»:** stage 2's reading (`retrieval_summary.coverage`).
   - A whole document counts its joined chunks.
   - A cut one counts the paragraphs of its excerpt, located in its document (ConditionalQA,
     MultiHop-RAG). WixQA's gold is an article: a cut document counts if any text of it shows.
   - Metrics on the questions with gold — 100 WixQA, 80 ConditionalQA, 70 MultiHop-RAG: WixQA
     `gold_article` (primary) and `gold_articles`; the other two `all_evidence_coverage`
     (primary) and `evidence_recall`.
   - aircargo has no gold documents — its labels hold answer terms — so it gets sizes only.
4. **Sizes:** the documents sent, whether the last is cut, and the prompt's characters and
   estimated tokens (`estimate_window_tokens`, the fitting's own measure).

## Checks before any number

Each stops the tool, and nothing is written.

1. **The runs:** the no-reranker point's checks: complete runs of `5e308fe`, five kept,
   expansion on, the archive its index receipt and the export name.
2. **The expansion is the recorded one** on every question of the four bases, text for text
   (the no-reranker point had no miss on the three with gold).
3. **Stage 2's prompt reproduces:** `QA_PROMPT_V3` at 4,096 gives every record's sent documents,
   text and cut flag, and its prompt's SHA-256.
4. **Today's prompt is the chat's:**
   - `QA_PROMPT_V4` at 4,096 gives the SHA-256 of the prompt V4's live run sent. It is checked
     on every aircargo, WixQA and ConditionalQA question where V4 retrieved what the record
     holds (the five's scores to six places and the expanded characters equal); the record
     counts them.
   - The chat resolves its answer prompt to `QA_PROMPT_V4` with no override, and the answer's
     output budget is 1,024.
5. **The recount:** stage 2's points, read again from the records, are the export's. That is
   the no-reranker point's `recount` for ranked and expanded, and «sent» here with its excerpt
   pieces not found.

A question whose «sent» point cannot be read at some window is left out of every window, and
counted: a paragraph of an excerpt without a place in its document. More than five on a base
make its comparison `NOT_EVIDENCE`.

## How it is read — frozen before the count

Each window below 4,096 is set against 4,096 at «sent», per base and pooled over the three, on
the primary metric. The pair gives the questions read and the hits of each side. It gives the
discordant pairs: **b**, gold at 4,096 only; **c**, gold at the window only. And the exact
two-sided McNemar p (binomial on b + c at ½, the no-reranker point's `mcnemar`); per base, the
second metric's mean on each side.

- **loss** — b > c and p < 0.05: the window drops gold that 4,096 sends;
- **gain** — c > b and p < 0.05;
- **no detected difference** — otherwise, with b and c given.

**The smallest window without a detected loss** is the smallest window from which no window up
to 3,840 reads *loss*, on any base or pooled. A loss on one base vetoes its window, as in the K
curve; a *gain* vetoes nothing. If 3,840 reads a loss it is 4,096, the path of now. A base whose
comparison is `NOT_EVIDENCE` makes it `NOT_EVIDENCE`. It is read from the top, as the K curve
was. It is the window the live timing measures.

A window sends a prefix of 4,096's documents, its last one cut shorter, so c needs an excerpt at
the smaller budget to hold a paragraph the larger one left out. With c = 0 a loss needs b ≥ 6
(p = 0.031; five give 0.0625). No correction for the 28 comparisons: it would only guard against
a false *loss*, and a false loss only raises the window toward 4,096. *No detected loss* is not
*no loss* ([the K curve's spec](k-curve-expanded.md) gives the test's reach).

Beside the reading, per base and window:
- the documents sent (median and range) and the cut prompts;
- the estimated tokens, the tokens saved against 4,096, and how many prompts are shorter;
- the excerpt pieces not found.

And at 4,096: stage 2's «sent» (V3) against today's (V4), and V4's checked prompts.

## What it does not say

- **Seconds.** The tokens saved are estimates. The seconds come from the live timing after this
  count: the answer and the self-evaluation, on aircargo questions.
- **Which window enters the path.** A new window changes the answer path, and with it item 6 and
  stage 5, as K = 14 does; both are her word ([`PLAN.md`](../../PLAN.md) §8.3). If both come,
  they are one re-answer, not two.
- **Answer quality.** Gold sent is what the model can read, not what it answers. aircargo's
  answers are judged only at item 6.
- **The other calls.** num_ctx is one setting, so the self-evaluation, the hints, the graph path,
  `/api/ask` and the grader get the same window.
  - The self-evaluation's own limit, with its 128 output tokens, is about 806 estimated tokens
    above the answer's. It keeps the answer's documents unless the answer is long.
  - The hints' prompt (329–429 tokens at step 0) holds no whole document.
- **Memory.** The model's KV cache is allocated for num_ctx, so a smaller window holds less.
  Item 5 measures memory; this count does not.
- **The estimate.** `estimate_window_tokens` runs about 10% above the exact count on average
  (fitted on the Qwen2.5 tokenizer). The windows are read in the product's own measure.
- **One stand and one run a base.** MultiHop-RAG's pairs are small: gold at «sent» for 10 of its
  70 questions on stage 2's prompt.

## Forecast, written before the count

From the published numbers and stage 2's sizes, no question's gold read. The median expanded
document holds about 390 estimated tokens on WixQA, 370 on ConditionalQA, 590 on MultiHop-RAG and
730 on aircargo (characters a document times the base's tokens a character, the export). V4's
instructions and an English question take about 310. So the documents sent, the cut one
counted:
- at 4,096, five on WixQA and ConditionalQA, four on MultiHop-RAG and aircargo;
- at 3,328, four or five, three, and three;
- at 2,304, one or two on every base, the last cut.

The reading:
- At 3,840 and 3,584 nothing reads a loss: the fifth document, cut, still shows WixQA's article.
- At 3,328 no base reads a loss. The pooled b of 3–6 is the closest call.
- From 3,072 down, ConditionalQA and the pooled read a loss; WixQA from 2,816. MultiHop-RAG,
  ten hits at 4,096, reads one only at 2,560 and below.

**The smallest window without a detected loss: 3,328** (input limit 1,945). On aircargo it saves
a median of about 640 estimated tokens on the answer and as many on the self-evaluation. At step
0's 28–37 tokens a second that is about 17–23 s each, ≈ 40 s of the median 320 s; at 2,304
about twice that.

## What comes after

- **The live timing:** if the window is below 4,096, a registered ABBA timing on the idle Mac,
  like step 3's. Aircargo questions, the answer and the self-evaluation at that window against
  4,096; its own spec, after this count.
- **The hints**, item 4's other half: the chat would send the answer, its sources and its badge
  before the hints are generated, and the hints after them as their own event. That changes the
  chat's behaviour: its own slice, with an E2E test (rule (a)), not counted here.

## Records

`reports/stage4-step4/5e308fe/`, from
[`reports/stage4-step4/tools/prompt_budget.py`](../../reports/stage4-step4/tools/prompt_budget.py):
- `record.json`: the inputs, the tool and the measuring code by SHA-256, the two prompts by
  SHA-256, the windows and their limits, per base and pooled each window's pair and what stands
  beside it, the checks' counts, and the decision;
- `rows.jsonl`, a question a line: id, base, index, stratum, the V4 flags, the window whose
  «sent» could not be read, stage 2's points, and per window the documents sent, the cut, the
  characters, the estimated tokens and the point at «sent».

Ids, flags and numbers, never a text: `stage2_common.without_text` refuses a record that would
hold one. The count is a step toward a published number (rule (c)) only when a window enters the
path; until then it is preparation. Its record gets a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md), a capsule in `docs/evidence/` and a test that
reads it again.

`tests/test_stage4_step4_tools.py` covers the fitting through the product's code on a synthetic
archive, the checks, and the reading on hand-made rows. The tool and its test are committed with
this spec, and the test checks each SHA-256 below; a later change is a marked error fix that
updates this list:

- `reports/stage4-step4/tools/prompt_budget.py` `7e9adbcf3cbc2ce333640cd40b646a2cc337dcd5b240f26f34aa6f23875e7165`
- `tests/test_stage4_step4_tools.py` `1c9697143d5ccfceb9a6bf2582727b1ded7198fc189155ec12e8f7b6844b6881`
