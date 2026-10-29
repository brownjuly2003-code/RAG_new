# Stage 4, step 4: the answer prompt's window — num_ctx below 4,096 against 4,096 at «sent», on stage 2's saved lists — 2026-10-29

The question: how far the chat's window can shrink before the gold the model reads falls. Stage
2's saved retrieval lists of stand `5e308fe` were fitted again by the rules
[`stage4-step4-prompt-budget.md`](../specs/stage4-step4-prompt-budget.md), registered with the
tool in `b192fb0` before the count. At num_ctx 4,096 down to 2,304 in steps of 256, the
product's own expansion and fitting ran under today's answer prompt `QA_PROMPT_V4`. Each window
is set against 4,096 at «sent» ([`PLAN.md`](../../PLAN.md) stage 4, item 4). No model call, no
new retrieval; 38.7 s on the Mac.

Record: [`reports/stage4-step4/5e308fe/record.json`](../../reports/stage4-step4/5e308fe/record.json)
and its [rows](../../reports/stage4-step4/5e308fe/rows.jsonl), written by
[`reports/stage4-step4/tools/prompt_budget.py`](../../reports/stage4-step4/tools/prompt_budget.py).
Checked by [`tests/test_stage4_step4_artifact.py`](../../tests/test_stage4_step4_artifact.py):
- every number of the record is read again from the rows;
- stage 2's points are read again from the committed export;
- every prompt fits its window's limit, and a smaller window sends no more documents or tokens;
- every table row below is built from the record.

The rows hold identifiers, flags and numbers, never the text of a question or a document.

## Provenance and method

- **Inputs:** the K curve's ([record](k-curve-record.md)), the same files by SHA-256:
  - the runs `p2-wixqa`, `p2-conditionalqa`, `p2-multihoprag` and `p2-aircargo` on stand
    `5e308fe48cca0955c3007057a574a425f71e2a6a`, 100 questions each;
  - the second generation's chunk archives;
  - the export [`reports/stage2/retrieval-20261021/`](../../reports/stage2/retrieval-20261021/manifest.json),
    manifest SHA-256 `f8dbfb9e…`.

  And V4's committed answer rows, `reports/answer-prompt-v4/4f48fed/`, for aircargo, WixQA and
  ConditionalQA, by SHA-256. Measured on the Mac in a clean worktree of `b192fb0`, the
  registering commit, 23:01:45–23:02:24 UTC, no model loaded. The record names the tool, the
  measuring code and both prompts by SHA-256.
- **The prompts:** stage 2's stand sent `QA_PROMPT_V3`, read from `agent/prompts.py` at
  `5e308fe` as a literal. Every window was fitted under `QA_PROMPT_V4`, today's, 249 characters
  longer, set by the product's own override. The answer keeps 1,024 output tokens, so a window's
  input limit is `window_input_limit(num_ctx, 1024)`.
- **The point at each window:**
  1. `_expand_parents` expands the recorded five over the chunk archive.
  2. `_fit_stream_prompt` fits the chat's first question at the window.
  3. Stage 2's reading at «sent» (`retrieval_summary.coverage`) reads the documents it keeps.
- **Metrics:** stage 2's, on the questions with gold — WixQA `gold_article`; ConditionalQA and
  MultiHop-RAG `all_evidence_coverage`. The exact two-sided McNemar test sets 4,096 against the
  window: **b** counts questions with gold only at 4,096, **c** gold only at the window. A *loss*
  is b > c with p < 0.05.
- **Checks before any number, all passed:**
  - on all 400 questions the expansion is the recorded one, text for text;
  - stage 2's prompt at 4,096 gives every record's sent documents, cut flags and prompt SHA-256;
  - today's prompt at 4,096 gives the SHA-256 of the prompt V4's live run sent, on all 300
    questions of aircargo, WixQA and ConditionalQA: V4 retrieved what the record holds on each;
  - the chat resolves its answer prompt to `QA_PROMPT_V4`, its output budget 1,024;
  - stage 2's points, read again, are the export's;
  - no excerpt piece went unfound and no point unread, at any window.

## At «sent» — the pair that decides

Each cell gives the questions with gold at the window, then (b/c, p) against 4,096. The first
column gives num_ctx and, in brackets, its input limit in estimated tokens.

| num_ctx (limit) | WixQA | ConditionalQA | MultiHop-RAG | Pooled |
|---|---|---|---|---|
| 4,096 (2,636) | 68 of 100 | 60 of 80 | 9 of 70 | 137 of 250 |
| 3,840 (2,406) | 68 (0/0, 1.000) | 60 (0/0, 1.000) | 7 (2/0, 0.500) | 135 (2/0, 0.500) |
| 3,584 (2,176) | 68 (0/0, 1.000) | 59 (1/0, 1.000) | 7 (2/0, 0.500) | 134 (3/0, 0.250) |
| 3,328 (1,945) | 64 (4/0, 0.125) | 58 (2/0, 0.500) | 5 (4/0, 0.125) | 127 (10/0, 0.002) **loss** |
| 3,072 (1,715) | 63 (5/0, 0.062) | 55 (5/0, 0.062) | 3 (6/0, 0.031) **loss** | 121 (16/0, 0.000) **loss** |
| 2,816 (1,484) | 61 (7/0, 0.016) **loss** | 52 (8/0, 0.008) **loss** | 1 (8/0, 0.008) **loss** | 114 (23/0, 0.000) **loss** |
| 2,560 (1,254) | 57 (11/0, 0.001) **loss** | 47 (13/0, 0.000) **loss** | 1 (8/0, 0.008) **loss** | 105 (32/0, 0.000) **loss** |
| 2,304 (1,024) | 54 (14/0, 0.000) **loss** | 42 (18/0, 0.000) **loss** | 0 (9/0, 0.004) **loss** | 96 (41/0, 0.000) **loss** |

**The smallest window without a detected loss: 3,584** (input limit 2,176).

## The prompts' sizes — beside it

Each cell lists four bases in order: WixQA / ConditionalQA / MultiHop-RAG / aircargo. The
documents, the estimated tokens and the tokens saved are medians over a base's 100 questions;
the last column counts the prompts whose last document is cut.

| num_ctx | Documents sent | Estimated tokens | Saved against 4,096 | Prompts cut |
|---|---|---|---|---|
| 4,096 | 5 / 5 / 4 / 4 | 2,296 / 2,242 / 2,598.5 / 2,604.5 | 0 / 0 / 0 / 0 | 22 / 12 / 81 / 99 |
| 3,840 | 5 / 5 / 4 / 3 | 2,273.5 / 2,207.5 / 2,381.5 / 2,366.5 | 0 / 0 / 209 / 241.5 | 41 / 39 / 89 / 99 |
| 3,584 | 5 / 5 / 3 / 3 | 2,117.5 / 2,125 / 2,149.5 / 2,152 | 172 / 115 / 460 / 456 | 59 / 53 / 95 / 97 |
| 3,328 | 5 / 5 / 3 / 3 | 1,903.5 / 1,904 / 1,913.5 / 1,901 | 403 / 347 / 691 / 691 | 72 / 69 / 94 / 97 |
| 3,072 | 4 / 4 / 3 / 2 | 1,691 / 1,686 / 1,694 / 1,670 | 633 / 548 / 911.5 / 926.5 | 89 / 74 / 96 / 98 |
| 2,816 | 3 / 3 / 2 / 2 | 1,467.5 / 1,463.5 / 1,437.5 / 1,440 | 861 / 807.5 / 1,153.5 / 1,157 | 95 / 89 / 97 / 99 |
| 2,560 | 3 / 3 / 2 / 2 | 1,236.5 / 1,238 / 1,253 / 1,235 | 1,087 / 1,047 / 1,366.5 / 1,382 | 97 / 88 / 95 / 98 |
| 2,304 | 2 / 2 / 2 / 2 | 1,016.5 / 1,010.5 / 1,001 / 987 | 1,296 / 1,255 / 1,611 / 1,611.5 | 95 / 91 / 96 / 99 |

## Stage 2's prompt against today's, at 4,096

| Base | Gold at «sent», V3 | V4 | b/c, p |
|---|---|---|---|
| WixQA | 68 of 100 | 68 | 0/0, 1.000 |
| ConditionalQA | 60 of 80 | 60 | 0/0, 1.000 |
| MultiHop-RAG | 10 of 70 | 9 | 1/0, 1.000 |

## What it says

- **3,584 is the smallest window the frozen reading allows.** Its input limit is 2,176
  estimated tokens, 460 below today's 2,636. At 3,328 the pooled three read a loss — 127
  against 137 of 250 (b 10, c 0, p 0.002) — where no base alone does (b 4, 2 and 4).
  MultiHop-RAG reads one from 3,072 down, every base from 2,816.
- **On aircargo, 3,584 saves a median 456 estimated tokens** of the answer's prompt (186–808,
  every prompt shorter): 2,152 instead of 2,604.5, a median of three documents sent instead of
  four. The other bases save a median 172 (WixQA), 115 (ConditionalQA) and 460 (MultiHop-RAG).
- **No detected loss is not no loss.** At 3,584 the pooled gold is 134 against 137 (b 3, c 0,
  p 0.25). MultiHop-RAG loses 2 of its 9 already at 3,840: too few pairs to read.
- **A smaller window never sent gold the larger one did not.** c is 0 in all 28 comparisons:
  a window sends a prefix of 4,096's documents, its last cut shorter, and no excerpt at a
  smaller budget held a gold paragraph the larger one left out.
- **Today's prompt costs one question of gold against stage 2's.** At 4,096 V4's 249 more
  characters leave out MultiHop-RAG's gold on one question (10 → 9 of 70); WixQA and
  ConditionalQA are unchanged.
- **The forecast was one step low.** Written before the count, it gave 3,328.
  - **Right:** no base alone reads a loss at 3,328; WixQA's first loss is at 2,816; the
    documents sent at 4,096 and at 2,304; about 640 estimated tokens saved on aircargo at
    3,328 (691).
  - **Wrong:** the pooled b at 3,328 is 10, not 3–6, so a loss; ConditionalQA's first loss is
    at 2,816, not 3,072; MultiHop-RAG's at 3,072, not 2,560 — its nine hits at 4,096 fall to
    three. And the count took 38.7 s, not minutes.

## What follows

- **The live timing** ([the spec's next step](../specs/stage4-step4-prompt-budget.md#what-comes-after)):
  3,584 against 4,096 on aircargo questions, ABBA on the idle Mac, the answer and the
  self-evaluation; its own spec, registered before the first request. At step 0's 28–37 tokens
  a second, 456 estimated tokens are about 11–16 s for each of the two calls: a forecast, not a
  number.
- **The window in the path is her word** ([`PLAN.md`](../../PLAN.md) §8.3): a new num_ctx
  changes the answer path, and with it item 6 and stage 5, as K = 14 does. If both come, they
  are one re-answer, not two.
- **The hints**, item 4's other half, are their own slice, with an E2E test.

Limits:
- gold in the documents sent, not answer quality;
- estimated tokens, about 10% above the exact count, and no seconds;
- one stand and one run a base; MultiHop-RAG's pairs are small;
- num_ctx is shared by the self-evaluation, the hints, the graph path, `/api/ask` and the
  grader; only the answer's prompt was counted.
