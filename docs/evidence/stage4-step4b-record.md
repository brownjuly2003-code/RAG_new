# Stage 4, step 4b: num_ctx 3,584 against 4,096, timed — the answer and its self-evaluation — 2026-10-30

The question: how many seconds does num_ctx 3,584 save against today's 4,096 on the chat's two
calls of a question, the answer and its classic self-evaluation? Step 4
([its record](stage4-step4-record.md)) found 3,584 the smallest window without a detected loss
of the gold at «sent», and Julia's word on the window ([`PLAN.md`](../../PLAN.md) §8.3) needs
its seconds beside its gold. Thirteen aircargo questions on step 4's documents were timed in 26
blocks, ABBA, on the idle Mac, each block begun with no model, by
[`stage4-step4b-window-timing.md`](../specs/stage4-step4b-window-timing.md). The spec was
registered with its tool and the tool's test
in `d1ef9e5` before the first request; nothing changed after it.
The series started at 00:50 UTC on 2026-10-30.

Record: [`reports/stage4-step4b/d1ef9e5/`](../../reports/stage4-step4b/d1ef9e5/):
- `record.json`: the series' facts, the inputs by SHA-256 with the thirteen's prompt sizes, the
  model, the environment's lines, the attempts and the files rejected, the pairs and the
  readings;
- `rows.jsonl`, a block a line: its schedule, its numbers, and its gate's and its disturbance's
  reasons.

Every number below is the record's unless named otherwise: its `readings`, its `pairs` (a
question's two blocks, one at each window) and its rows. What the record does not print itself —
each call's medians, the tokens' ratios, the first token's seconds and the sizes' difference —
the test computes from them. Step 4's numbers are its record's
([`reports/stage4-step4/5e308fe/`](../../reports/stage4-step4/5e308fe/)); V4's are
[`v4-aircargo.cases.jsonl`](../../reports/answer-prompt-v4/4f48fed/v4-aircargo.cases.jsonl)'s.

The tool is
[`reports/stage4-step4b/tools/window_timing.py`](../../reports/stage4-step4b/tools/window_timing.py).
Checked by [`tests/test_stage4_step4b_artifact.py`](../../tests/test_stage4_step4b_artifact.py):
- the files are the bytes copied from the Mac, read by the tool the spec registers, by SHA-256;
- the pairs and the readings are read again from the rows with the committed tool;
- every block passed its gate undisturbed, at its window, on its first attempt;
- one Ollama server and one interpreter ran the series;
- the inputs are step 4's documents, and each block sent its question's registered prompt; at
  4,096 it is the prompt V4's live run sent;
- the files hold numbers, times, ids, enums, a model name, versions, package names, the spec's
  path and SHA-256 strings only;
- every table row below is built from the record, and so is each number of the prose that the
  test pins; the forecasts are the spec's words.

The record holds no question, document, source name, answer, prompt or command line.

## Provenance and method

- **The stand:** code `d1ef9e5584c37b91c426d41bfbc34a78362ae1be`, today's chat, in a clean
  worktree on the Mac; the series and the read ran its tool. Before its calls each block held
  the settings against V4's stand's, its first aircargo run's `effective_settings.json`: the
  provider profile, the model, the routing, the role parameters, the three timeouts, the quality
  evaluation and its threshold, the RAG parity and the provider registry. The self-evaluation's
  mode was `classic`, the default; only the window and the server differ.
- **The interpreter:** Python 3.11.15 with `langchain-ollama` 1.1.0, V4's stand's, in `env -i`
  with the three timeouts at 3,600 s and `RAG_DEVICE=cpu`. One set of distributions throughout,
  by its freeze's SHA-256.
- **Ollama:** 0.33.2 at the series' start, at its resume and at its end, and before and after
  every block. One server throughout, up since 2026-09-13. The model
  `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef3…`. No llama.cpp `config.ini` at any block
  or environment line: item 5's `cache-ram` line comes after this series.
- **The calls:** each block made the chat's two calls of a first question in process, through a
  proxy that kept Ollama's counters: the answer, streamed, with num_predict 1,024 and temperature
  0.2, then the classic self-evaluation, 128 and 0.0, both at the block's num_ctx. No API,
  database, retrieval, rerank or hints ran.
- **The questions:** the first thirteen of
  `evaluation/curated_cases_aircargo.jsonl` (`3737d694…`), step 3's, in its order.
  `aircargo-probation-data` came first: its two blocks pair with nothing. The other twelve make
  the pairs.
- **Their documents:** step 4's. The inputs step ran step 4's tool on stage 2's records with
  every check of it and kept the product's parent expansion of the recorded five. At both windows
  the chat's fitting gave step 4's committed rows (`a3cc90d2…`): the documents, the cut, the
  characters and the estimated tokens. At 4,096 it gave the SHA-256 of the prompt V4's live run
  sent, on all thirteen.
- **The blocks:** 26, a question's two in a row, 4,096 first at odd positions and 3,584 first at
  even ones; each window went first in six of the twelve pairs. Each block began with Ollama
  holding no model and no llama-server and loaded the model at its window. The series stopped
  after block 1 at the spec's stop file (one question first), was started again once and resumed
  at block 2.
- **The gates:** all 26 blocks passed on their first attempt; no file was rejected. After its
  calls every block's `/api/ps` held the one model at the block's window, on the CPU
  (`size_vram` 0). The self-evaluation's load was at most 0.018 s: it ran on the answer's loaded
  model.
- **The Mac:** no block was disturbed: no step 0 process at its start or end, no other model at
  its start, its own model and one llama-server alone at its end.
  The 5-minute load was 1.18 before block 1 and 1.94 before block 2, below the spec's 2.

## The reading

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| The answer: 3,584's prompt seconds below 4,096's on more pairs, the exact two-sided sign test's p below 0.05 | **faster** | below on 12 of 12 readable pairs, above on 0; p 0.000488 | faster, on 12 of 12 |
| The number: the median saving, 4,096's prompt seconds less 3,584's | **24.681 s** | 17.029–33.510 s by question | ≈ 23–30 s |
| The number: the median ratio, 3,584's prompt seconds over 4,096's | **0.792** | 0.724–0.850 by question | ≈ 0.82 |

The prompt seconds are the two calls' `prompt_eval_duration`, summed. With twelve readable pairs
faster needed at least 10 of 12 (p = 0.039); 3,584 was below on all twelve.

## Per question

A pair is a question's two blocks; "First" names the window that went first. Each cell of two
values is 4,096's / 3,584's. The tokens are Ollama's `prompt_eval_count` of each call, the
documents those of the answer's prompt. The saving is 4,096's prompt seconds less 3,584's, the
ratio 3,584's over 4,096's.

### The two prompts

| Position | Question | First | Documents | The answer's prompt, tokens | The self-evaluation's prompt, tokens | Prompt seconds | Saving, s | Ratio |
|---|---|---|---|---|---|---|---|---|
| 2 | `aircargo-probation-extend` | 3,584 | 3 / 3 | 2,380 / 1,965 | 2,696 / 2,190 | 131.929 / 104.295 | 27.634 | 0.791 |
| 3 | `aircargo-probation-dismissal` | 4,096 | 4 / 3 | 2,332 / 1,894 | 2,470 / 2,033 | 122.135 / 96.880 | 25.255 | 0.793 |
| 4 | `aircargo-dismissal-check` | 3,584 | 3 / 3 | 2,278 / 1,860 | 2,506 / 2,137 | 122.961 / 99.414 | 23.547 | 0.809 |
| 5 | `aircargo-dismissal-lawyer` | 4,096 | 4 / 3 | 2,279 / 1,937 | 2,392 / 2,050 | 118.537 / 99.774 | 18.763 | 0.842 |
| 6 | `aircargo-dismissal-order` | 3,584 | 4 / 3 | 2,296 / 1,754 | 2,473 / 1,838 | 121.227 / 87.717 | 33.510 | 0.724 |
| 7 | `aircargo-leave-sources` | 4,096 | 3 / 3 | 2,301 / 1,867 | 2,388 / 1,954 | 118.879 / 94.046 | 24.833 | 0.791 |
| 8 | `aircargo-leave-compensation` | 3,584 | 3 / 3 | 2,276 / 1,855 | 2,360 / 1,947 | 117.805 / 93.275 | 24.530 | 0.792 |
| 9 | `aircargo-leave-risk` | 4,096 | 3 / 3 | 2,201 / 1,904 | 2,291 / 2,009 | 113.488 / 96.459 | 17.029 | 0.850 |
| 10 | `aircargo-matliab-check` | 3,584 | 5 / 3 | 2,211 / 1,809 | 2,339 / 1,888 | 115.684 / 91.814 | 23.870 | 0.794 |
| 11 | `aircargo-matliab-disputed` | 4,096 | 4 / 3 | 2,286 / 1,813 | 2,368 / 1,895 | 117.964 / 91.111 | 26.853 | 0.772 |
| 12 | `aircargo-templates-choose` | 3,584 | 5 / 5 | 2,214 / 1,863 | 2,291 / 1,952 | 113.827 / 93.855 | 19.972 | 0.825 |
| 13 | `aircargo-templates-checklist` | 4,096 | 4 / 3 | 2,266 / 1,877 | 2,454 / 1,953 | 119.931 / 94.339 | 25.592 | 0.787 |

### The answers and the result

The whole is the two calls' `total_duration` less their loads; the result is the chat's wall
from the stream's start to the self-evaluation's score, less the answer's load. The score and the
route are the classic self-evaluation's.

| Position | Question | Generated tokens | Whole, s | Result, s | The result's saving, s | Score | Route |
|---|---|---|---|---|---|---|---|
| 2 | `aircargo-probation-extend` | 280 / 195 | 199.544 / 143.946 | 200.001 / 144.595 | 55.406 | 80 / 40 | auto / human |
| 3 | `aircargo-probation-dismissal` | 100 / 101 | 145.784 / 116.298 | 146.231 / 116.746 | 29.485 | 100 / 95 | auto / auto |
| 4 | `aircargo-dismissal-check` | 192 / 241 | 167.700 / 146.822 | 168.158 / 147.203 | 20.955 | 100 / 100 | auto / auto |
| 5 | `aircargo-dismissal-lawyer` | 73 / 73 | 135.856 / 114.603 | 136.110 / 114.864 | 21.246 | 100 / 100 | auto / auto |
| 6 | `aircargo-dismissal-order` | 141 / 44 | 153.978 / 96.148 | 154.229 / 96.390 | 57.839 | 100 / 100 | auto / auto |
| 7 | `aircargo-leave-sources` | 47 / 47 | 130.225 / 103.424 | 130.497 / 103.666 | 26.831 | 100 / 100 | auto / auto |
| 8 | `aircargo-leave-compensation` | 44 / 52 | 128.346 / 103.367 | 128.587 / 103.608 | 24.979 | 95 / 95 | auto / auto |
| 9 | `aircargo-leave-risk` | 50 / 65 | 124.769 / 109.277 | 124.995 / 109.507 | 15.488 | 100 / 100 | auto / auto |
| 10 | `aircargo-matliab-check` | 90 / 39 | 135.875 / 100.067 | 136.109 / 100.299 | 35.810 | 100 / 100 | auto / auto |
| 11 | `aircargo-matliab-disputed` | 42 / 42 | 128.119 / 99.394 | 128.345 / 99.623 | 28.722 | 100 / 100 | auto / auto |
| 12 | `aircargo-templates-choose` | 37 / 49 | 122.353 / 103.431 | 122.578 / 103.664 | 18.914 | 100 / 95 | auto / auto |
| 13 | `aircargo-templates-checklist` | 150 / 36 | 154.570 / 101.644 | 154.807 / 101.873 | 52.934 | 100 / 100 | auto / auto |

## Printed, deciding nothing

The spec's list, over the twelve readable pairs, the first question's two blocks at its end:

| Printed | 4,096 | 3,584 |
|---|---|---|
| The two prompts' seconds, a median | 118.708 | 94.192 |
| The result's seconds, a median | 136.110 | 103.665 |
| The answer's prompt, tokens, a median | 2,278.5 | 1,865 |
| The self-evaluation's prompt, tokens, a median | 2,390 | 1,953.5 |
| The answer's prompt read, tokens a second, a median | 39.610 | 40.790 |
| The answer's generated tokens, a median | 81.5 | 50.5 |
| The answer's generation, tokens a second, a median | 4.486 | 5.443 |
| The load, s, a median | 5.358 | 5.242 |
| `/api/ps`'s size, bytes, a median | 3,184,001,022 | 3,107,979,262 |
| Routes, auto / human | 12 / 0 | 11 / 1 |
| Scores parsed | 12 of 12 | 12 of 12 |
| The first question's prompt seconds | 122.008 | 86.515 |
| The first question's result, s | 202.752 | 117.155 |
| The first question's load, s | 11.286 | 6.896 |

The same counts, sign test and medians for the whole and the result:

| Compared, deciding nothing | 3,584 below on | Above on | p | Median saving, s | Median ratio |
|---|---|---|---|---|---|
| The whole | 12 of 12 | 0 | 0.000488 | 27.763 | 0.796 |
| The result | 12 of 12 | 0 | 0.000488 | 27.776 | 0.796 |

- The tokens saved a call, a median: 416.5 in the answer's prompt, 435.5 in the
  self-evaluation's.
- The same route in 11 of 12 pairs; the same answer, by SHA-256, in 3 of 12.
- By the window that went first: 4,096 first in 6 pairs, a median saving of 25.044 s;
  3,584 first in 6, 24.200 s.

### The first token (mine, no rule of the spec)

Not on the spec's list: the answer's first token, in seconds from the answer's request, its load
included, a median over the twelve: 63.079 at 4,096 against 51.014 at 3,584.
It came earlier at 3,584 in 12 of 12 pairs, by a median 12.095 s (8.273–14.978).

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| **faster**, on 12 of 12 | **faster**, on 12 of 12 |
| about 430 exact tokens a call: 469 estimated, the estimate about 10% above the exact count | a median 416.5 in the answer's prompt and 435.5 in the self-evaluation's, against 469 estimated |
| At 4,096 the two prompts take ≈ 150 s together | a median 118.708 s; the answer's prompt read at 39.610 tokens a second |
| the saving is ≈ 23–30 s and the ratio ≈ 0.82 | a saving of 24.681 s and a ratio of 0.792 |
| The whole and the result fall by about as much, with the answers' spread around it | the whole 27.763 s and the result 27.776 s less, a median; the result's saving 15.488–57.839 s by question |
| `/api/ps`'s size falls by about the KV cache of 512 tokens, ≈ 72 MiB at f16 (36 layers, 8 KV heads of 128) | 72.5 MiB: 3,184,001,022 bytes at 4,096 in every block, 3,107,979,262 at 3,584 |
| a block ≈ 200 s at 4,096 — a load ≈ 15 s, the answer's prompt ≈ 70 s, ≈ 190 tokens generated at ≈ 4 a second, the self-evaluation's prompt ≈ 75 s — and ≈ 180 s at 3,584 | at 4,096 a load of 5.358 s, the answer's prompt 57.674 s, 81.5 tokens generated at 4.486 a second, the self-evaluation's prompt 61.029 s, each a median; the result and the load 141.234 s at 4,096 and 110.520 s at 3,584 |
| ≈ 85 min for the 26, ≈ 1.5 h with the unloads and the checks | the record keeps no block's start or end |

The forecast's prompt seconds came from step 0's rates: the answer's prompt read at 28–37 tokens a
second, the self-evaluation's at 24–37 ([step 0](stage4-step0-record.md#per-request)). Here the
answer's prompt was read at a median 39.610 tokens a second at 4,096, above step 0's highest, so
the two prompts took less than forecast at both windows.

The series' wall is not in the record. By its log on the Mac, block 1 ran 00:50:36–00:54:13 UTC,
and blocks 2–26 ran 00:59:25–01:56:33, after the stop file and a wait for the 5-minute load:
about 61 minutes of blocks against the forecast's ≈ 85.

## What it says

- **3,584 reads the two prompts faster, by the frozen rule:**
  below 4,096 on 12 of 12 pairs, p 0.000488, where the spec needed p below 0.05.
  The median saving is 24.681 s, the median ratio 0.792.
- **Both calls saved about alike:**
  the answer's prompt a median 12.142 s and the self-evaluation's 12.597 s.
- **The seconds fell further than the tokens:** every pair's ratio of prompt seconds lies below
  its ratio of prompt tokens, a median 0.818.
  The answer's prompt was read at 40.790 tokens a second at 3,584 against 39.610 at 4,096.
  The record does not say why.
- **The answer's first token came earlier:** by a median 12.095 s (mine, above).
- **The whole and the result fell by more than the prompts:** a median 27.763 s and 27.776 s.
  The answers at 3,584 were shorter: 50.5 generated tokens a median against 81.5. One answer a
  question at temperature 0.2 cannot say whether the window shortens answers.
- **The KV cache shrank as forecast:** `/api/ps`'s size was 72.5 MiB smaller at 3,584, the same
  in every block of a window.
- **The order of the windows moved the saving little:**
  25.044 s with 4,096 first, 24.200 s with 3,584 first.
- **One route moved:** at 3,584 the self-evaluation
  scored `aircargo-probation-extend` 40 against 80 at 4,096 and sent it to a person.
  The other eleven pairs kept their route, and all 24 scores parsed.
  One score of one answer decides nothing on quality.

## What it does not say

- **Seconds of two calls; nothing on quality.** The scores and the routes are the classic
  self-evaluation's, printed; the answers are judged only at item 6. The window's gold is step
  4's ([its record](stage4-step4-record.md)): at 3,584 the three bases with gold
  keep it at «sent» in 134 of 250 questions against 137 at 4,096 (b 3, c 0, p = 0.25): no loss
  detected, none excluded.
- **No window is adopted here.** num_ctx stays 4,096, and
  the window in the path is Julia's word ([`PLAN.md`](../../PLAN.md) §8.3). A new num_ctx changes
  the answer path, and with it item 6 and stage 5, as K = 14 does; if both come, they are one
  re-answer, not two.
- **The other calls:** num_ctx is shared by the hints, the graph path, `/api/ask` and the
  grader; only the answer and its self-evaluation were timed.
- **The chat's whole wall:** no retrieval, rerank or hints ran. The final timing (item 7)
  measures the path as it ends up.
- **A resident model:** every block loaded the model at its window, and the load is read apart.
- **Memory:** `/api/ps`'s size is printed. The rows keep the swap used before and after each
  block: 2,244.25 MB before the first, 2,863.0 MB after the last,
  with the model unloaded before every block. Item 5 measures memory.
- Twelve questions of one corpus, one stand, one day, on a Mac other projects share.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `record.json` | 30,152 | `e56b023aa32928c218b65809a8bd8f393c4b3c1d0e907408605c9a952aeb9937` |
| `rows.jsonl` | 28,562 | `6eae246cb024446fc22738426640e4930568ca2fb997a753a4e3108a2e702905` |
