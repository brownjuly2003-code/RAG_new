# Stage 4, item 5a: n-gram decoding in the answer model's own llama-server — 2026-10-30

The question: does `--spec-type ngram-simple` write the chat's answer faster, a token at a time,
in the llama-server Ollama runs as the model's runner, and does it keep the answer's bytes?
Research 6 named it the second lever of item 5a ([`PLAN.md`](../../PLAN.md) stage 4); its seconds
and its bytes decide whether it reaches the package question (§8.3, item 2). Step 4b's thirteen
aircargo questions at num_ctx 4,096 were sent to the runner started directly, as it is (base)
and with n-gram decoding (ngram), in four blocks ABBA, after a block through Ollama for the
fidelity, by [`stage4-step5a-ngram-decoding.md`](../specs/stage4-step5a-ngram-decoding.md). The
spec was registered with its tool and the tool's test
in `5558ca8` before the first request; nothing changed after it.
The series started at 14:38 UTC on 2026-10-30.

Record: [`reports/stage4-step5a-ngram/5558ca8/`](../../reports/stage4-step5a-ngram/5558ca8/):
- `record.json`: the inputs by SHA-256 — step 4b's, the calls' prompts, the model, its renderer,
  parser and options, the runner's binary, version, arguments and environment, the GGUF —, the
  tool by SHA-256 and the commit measured, each block's facts, the attempts and the files
  rejected, the readings and the outcome;
- `rows.jsonl`, a question a line: its id and position, per direct block the call's numbers, its
  text's SHA-256 and length and whether it was disturbed, where differing texts first part, and
  for the first three block 0's counters.

Every number below is the record's unless named otherwise: its `readings`, its blocks and its
rows. What the record does not print itself — each question's milliseconds a token, ratio and
saving, the medians of the prompt and the first chunk, the figures marked mine — the test
computes from the rows.

The tool is
[`reports/stage4-step5a-ngram/tools/ngram_decode.py`](../../reports/stage4-step5a-ngram/tools/ngram_decode.py).
Checked by [`tests/test_stage4_step5a_ngram_artifact.py`](../../tests/test_stage4_step5a_ngram_artifact.py):
- the files are the bytes copied from the Mac, read by the tool the spec registers, by SHA-256;
- the readings and the outcome are read again from the rows with the committed tool;
- every block passed its gate at its first attempt, and the four direct blocks ran one server's
  settings but speculation's type;
- block 0's three questions through Ollama are block 1's text and counters;
- the inputs are step 4b's, the options the chat's, the runner Ollama's own;
- the files hold no Cyrillic, no question and no path of the Mac outside the runner and the
  GGUF;
- every table row below is built from the record, and so is each number of the prose that the
  test pins; the forecasts are the spec's words.

The record holds no question, prompt, answer or document.

## Provenance and method

- **The stand:** code `5558ca84aa17f46eebe5bb7e03266895db1c2ab3`, in a clean worktree on the Mac;
  the tool refuses one that is not clean, at the series' start and before each block. Its
  `inputs` rebuilt the thirteen's prompts from step 4b's inputs (`6dc8f49e…`) with step 4's
  fitting, rendered by Ollama itself.
- **The runner:** Ollama 0.33.2's own llama-server binary,
  `88a427f3…`, `version: 0.3.0-dev (build 1, commit d222767c7)`,
  started by the tool with the arguments Ollama gives it but `--port`, and with the runner's
  `DYLD_LIBRARY_PATH` and `LLAMA_MEDIA_MARKER` over a bare `PATH`, `HOME` and `LC_ALL=C`; the
  GGUF
  `85e4a5b7…`, 2,497,280,480 bytes,
  of `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef3…`.
- **The calls:** each direct block a warm-up and the thirteen, block 0 a warm-up and the first
  three; the chat's answer call at num_ctx 4,096 with its options:
  num_predict 1,024, temperature 0.2, top_k 20, top_p 0.8, seed 1030.
  Base's blocks ran `speculative.types` `none`, ngram's `none,ngram-simple`, at its defaults;
  the other 48 settings
  the server reported were the same in all four direct blocks.
- **The blocks:** 0 through Ollama, then base, ngram, ngram, base. The series stopped after block
  1, as the spec makes it (two blocks first), was started again and resumed at block 2.
- **The gates:** all five blocks passed at their first attempt; no file was rejected; no sample
  went unanswered.
- **The Mac:** blocks 0 and 1 ran undisturbed. In blocks 2–4 jobs that were not ours ran beside
  the series at some calls' edges; the samples flagged
  3 questions in block 2, 1 in block 3 and 3 in block 4,
  6 questions in all, one of them in two blocks;
  others' CPU at most 95.9 % in block 2 and 91.8 % in block 4.
  By the blocks' samples on the Mac, outside the record, the processes that matched step 0's
  pattern were named `uv` and `python`.
  No job of ours ran on the Mac during the series.
  Ours there were the series itself, a `pgrep` over ssh once a minute that waited for its end
  and one look at its log.

## The reading

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| The fidelity: block 0's calls through Ollama against block 1's first four — the same text, prompt tokens and answer tokens | **holds** | 4 of 4 calls | holds |
| The speed: ngram's milliseconds a written token below base's on more readable questions, the exact two-sided sign test's p below 0.05, at least 10 readable | **`NOT_EVIDENCE`** | 7 readable of 13; ngram below on 1, above on 6; p 0.125 | faster, on 11 or 12 of the thirteen |
| The number: the median ratio, base's milliseconds a token over ngram's | **0.751** | from 0.415 to 1.395 by readable question | ≈ 1.1 |
| The number: the median writing saved, base's seconds less ngram's | **−3.384 s** | from −13.286 to 3.194 s by readable question | ≈ 2.2 s a question |
| The answers' bytes: base repeats itself on all thirteen, then each base–ngram pair of blocks gives the same text on all thirteen | **differ** | base 13 of 13, ngram 13 of 13; each pair 9 of 13 | byte-equal |
| The outcome | **`NOT_EVIDENCE`**: the lever closes | too few readable | faster and byte-equal |

A question is readable when no block disturbed it. The spec's outcome: «not faster: `not
faster`, or `NOT_EVIDENCE` with too few readable — the lever closes».

## Per question

Each arm's value is the mean of its two blocks' — base's 1 and 4, ngram's 2 and 3 — as the
tool's speed takes it. Each arm wrote the same text in both its blocks, so its tokens and drafts
are one number. The ratio is base's milliseconds a token over ngram's; the writing saved, base's
seconds less ngram's. A question disturbed in any block is not read; its numbers are printed.

| Position | Question | Disturbed in block | Milliseconds a written token, base / ngram | Ratio | Writing saved, s | Tokens written, base / ngram | Drafted / kept | The same answer |
|---|---|---|---|---|---|---|---|---|
| 1 | `aircargo-probation-data` | 2 | 217.687 / 492.843 | 0.442 | −113.686 | 286 / 357 | 240 / 58 | no, from character 737 |
| 2 | `aircargo-probation-extend` | 2 | 239.023 / 569.231 | 0.420 | −59.522 | 263 / 215 | 192 / 31 | no, from character 567 |
| 3 | `aircargo-probation-dismissal` | 2, 4 | 478.309 / 472.104 | 1.013 | 0.956 | 154 / 154 | 48 / 7 | yes |
| 4 | `aircargo-dismissal-check` | 4 | 505.425 / 465.320 | 1.086 | 1.755 | 183 / 195 | 96 / 35 | no, from character 471 |
| 5 | `aircargo-dismissal-lawyer` | 4 | 389.990 / 327.271 | 1.192 | 4.578 | 73 / 73 | 48 / 0 | yes |
| 6 | `aircargo-dismissal-order` | none | 416.705 / 298.696 | 1.395 | 3.194 | 103 / 133 | 96 / 24 | no, from character 152 |
| 7 | `aircargo-leave-sources` | none | 229.039 / 305.543 | 0.750 | −3.596 | 47 / 47 | 48 / 30 | yes |
| 8 | `aircargo-leave-compensation` | none | 225.986 / 520.039 | 0.435 | −12.938 | 44 / 44 | 96 / 6 | yes |
| 9 | `aircargo-leave-risk` | none | 212.088 / 279.767 | 0.758 | −3.384 | 50 / 50 | 48 / 19 | yes |
| 10 | `aircargo-matliab-check` | none | 212.553 / 283.174 | 0.751 | −2.754 | 39 / 39 | 48 / 22 | yes |
| 11 | `aircargo-matliab-disputed` | none | 224.311 / 540.645 | 0.415 | −13.286 | 42 / 42 | 96 / 10 | yes |
| 12 | `aircargo-templates-choose` | none | 218.316 / 286.596 | 0.762 | −3.346 | 49 / 49 | 48 / 20 | yes |
| 13 | `aircargo-templates-checklist` | 3 | 259.998 / 369.375 | 0.704 | −11.266 | 103 / 103 | 96 / 25 | yes |

## The blocks

The warm-up is each block's first call; block 0's includes Ollama's load of the model. The load
and the resident sizes are the direct server's; the swap is the Mac's at the block's first and
last sample.

| Block | Arm | UTC | Calls | Warm-up, s | Load, s | RSS after the load, MiB | Largest RSS after a call, MiB | Swap, first and last sample, MB | Others' CPU at most, % | Questions disturbed |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | ollama | 14:38:59–14:44:48 | 4 | 16.074 | — | — | — | 1,973.75 / 1,973.75 | 8.6 | 0 |
| 1 | base | 14:44:50–15:03:46 | 14 | 6.309 | 29.910 | 3,026.9 | 4,246.6 | 1,973.75 / 4,343.5 | 9.0 | 0 |
| 2 | ngram | 15:19:59–15:49:06 | 14 | 6.472 | 31.939 | 3,030.5 | 5,034.9 | 2,057.25 / 6,156.0 | 95.9 | 3 |
| 3 | ngram | 15:49:14–16:10:41 | 14 | 6.226 | 30.470 | 3,030.3 | 4,943.7 | 2,320.0 / 5,816.5 | 7.8 | 1 |
| 4 | base | 16:11:14–16:36:16 | 14 | 6.343 | 30.959 | 3,032.5 | 3,915.5 | 2,302.0 / 5,360.75 | 91.8 | 3 |

## Printed, deciding nothing

The tokens drafted and kept, a block, over the thirteen:

| Block | Drafted | Kept | Thrown away | Kept over drafted |
|---|---|---|---|---|
| 2 | 1,200 | 287 | 913 | 0.2392 |
| 3 | 1,200 | 287 | 913 | 0.2392 |

| Printed, over the seven readable | base | ngram |
|---|---|---|
| Milliseconds a written token, a median | 224.311 | 298.696 |
| The call's wall seconds, a median | 71.396 | 75.001 |
| The prompt's seconds, a median | 60.955 | 57.909 |
| The first chunk's seconds, a median | 61.963 | 59.303 |

- ngram's two blocks gave the same text on all thirteen, as base's did.
- Where base's and ngram's texts differ,
  the answers part at characters 737 (position 1), 567 (position 2), 471 (position 4), 152 (position 6)
  of base's text.
- The swap grew in every direct block, by 2,370 to 4,099 MB; the server's largest resident size
  after a call was larger in ngram's blocks than in base's.

### The two cleanest blocks (mine, no rule of the spec)

Not the spec's reading: block 1, base's, ran undisturbed and block 3, ngram's, disturbed one
question. A written token was
slower in block 3 than in block 1 on 12 of the 12 questions
both blocks kept undisturbed. The one readable question read faster,
`aircargo-dismissal-order`,
was slow in base's block 4 with no other job seen at its call's edges:
608.029 ms a token and a prompt of 93.056 s in block 4 against 225.382 and 60.451 s in block 1.

### The cost of a draft (mine, no rule of the spec)

On `aircargo-leave-compensation` and `aircargo-matliab-disputed` — readable, the same answer in
all four blocks, 96 tokens drafted, 6 and 10 kept — ngram wrote
12.938 and 13.286 s slower
than base: at least 135–138 ms a drafted token,
where the spec's arithmetic counted ≈ 25 ms, the prompt's rate a token. The kept tokens' saving
would only raise that floor.

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| the five blocks pass their gates and the fidelity holds | all five passed at their first attempt, no file rejected; the fidelity holds on all 4 calls |
| Base repeats itself on all thirteen | 13 of 13 |
| `ngram` keeps base's text on all thirteen — **byte-equal** | **differ**: each base–ngram pair of blocks the same on 9 of 13; ngram repeats itself on 13 of 13 |
| `ngram` reads **faster**, on 11 or 12 of the thirteen (p 0.022 or 0.003) | **`NOT_EVIDENCE`**: 7 readable, fewer than 10; on them ngram below on 1, above on 6, p 0.125 |
| kept over drafted ≈ 0.2, so ≈ 1,325 tokens drafted and ≈ 1,060 thrown away | 0.2392 in each ngram block: 1,200 drafted, 287 kept, 913 thrown away |
| the net: ≈ 26 s, ≈ 2.2 s a question — ≈ 9 % of the 281 s of writing, a ratio ≈ 1.1 | a median −3.384 s and a ratio 0.751 over the 7 readable |
| ≈ 1.5 h of the Mac once it is idle | 14:38:59–16:36:16 UTC, 1 h 57 min, with the stop after block 1 the spec makes |

The guess on the matches held: 287 of 1,200 drafted tokens were kept, near the guessed 0.2. The
cost of checking them did not: the spec counted a checked token at the prompt's rate, ≈ 25 ms,
and named the risk that a batch of a few dozen tokens costs more a token than a prompt of
≈ 2,300; it cost at least 135–138 ms here (mine, above).

## What it says

- **The lever closes, by the frozen rule:** the speed is `NOT_EVIDENCE`, seven readable where the
  spec needs ten, and its outcome for that is «the lever closes».
- **The readable seven lean the other way:**
  ngram below base on 1 of the 7 readable questions, above on 6
  (p 0.125); base's medians against ngram's,
  224.311 ms a written token against 298.696,
  the median ratio 0.751, a median −3.384 s
  of writing a question. The one faster question owes it to a slow base call in block 4, and
  the two cleanest blocks have ngram slower on every question both kept (mine, above).
- **The drafts matched, the checks cost:** a quarter of the drafted tokens were kept, as guessed,
  but checking a draft cost several times what the forecast counted, so the writing slowed.
- **The answers differ:** four of the thirteen part, from 152 to 737 characters in, so even a
  faster ngram would have changed the answer's path and come only with item 6's new answers.
- **The method holds:** the runner started directly gives Ollama's generation to the byte on the
  fidelity's four calls.

## What it does not say

- **Seconds of one call; nothing on quality.** Which of two differing answers is better is not
  read.
- **"Slower" is not a reading.** The frozen rule reads nothing with seven readable; the lever
  closes on too few readable, and the lean above is printed.
- **Other settings:** draft sizes other than the defaults, `ngram-cache`, draft models, another
  CPU — not measured.
- Whether n-gram enters the product was her word; the lever closes before it.
- **The chat's seconds:** the answer call ran alone, without the reranker or the embedder.
- Thirteen questions of one corpus, one seed, one day, on a Mac other projects share.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `record.json` | 16,008 | `9d0009afa4d36595c45c129dedde1f92ae9510eec4692878e130c2adaffd6ea8` |
| `rows.jsonl` | 20,729 | `9edcb7326d0590fb416b1f868e631b0af73e5e1e9118d30981b70259387bb233` |
