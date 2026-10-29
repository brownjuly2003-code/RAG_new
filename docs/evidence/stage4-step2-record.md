# Stage 4, step 2: the self-evaluation as the answer's next turn, beside the classic — 2026-10-29

The question: how many of the stream's self-evaluation seconds does the continuation save, and
does it score and route the answers as the classic does? Julia's word of 2026-10-28 on the
quality badge ([`PLAN.md`](../../PLAN.md) stage 4, item 2) was to keep it and make it faster.
Thirteen aircargo questions were asked on stand `57420db` in mode `both`. Each answer was scored twice in
one process: first the continuation, the rubric as the answer chat's next turn, then the classic,
the rubric in a prompt of its own. The runs were read by
[`stage4-step2-self-eval-continuation.md`](../specs/stage4-step2-self-eval-continuation.md). The
spec was registered with its tools and their test
in `f532c96` before the first request; Amendment 1, after the first run had stopped
and before the rerun's first request, in `c11696e`.
The runs started at 08:37 and 17:13 UTC on 2026-10-29.

Record: [`reports/stage4-step2/57420db/`](../../reports/stage4-step2/57420db/):
- `step2.s2-both-r2.json`, the rerun: its run, its pairs and the readings;
- `step2.json`, the first run, `s2-both`, which stopped at its thirteenth question; its gate
  failed, so it holds no pair and no reading;
- each run's first question's read, taken while the run went on (`s2-both.q1.step2.json`,
  `s2-both-r2.q1.step2.json`);
- `environment.jsonl`, the lines before and after each run.

Every number below is `step2.s2-both-r2.json`'s unless named otherwise: its `readings`, its
`pairs` (an answer's two self-evaluations) and its `run` (the launch, the settings and the
thirteen asks). The test computes from them what the record does not print itself: the ranges,
the runs' medians and sums, and `s2-both`'s sides.

The reader is
[`reports/stage4-step2/tools/step2_reader.py`](../../reports/stage4-step2/tools/step2_reader.py).
Checked by [`tests/test_stage4_step2_artifact.py`](../../tests/test_stage4_step2_artifact.py):
- the files are the bytes copied from the Mac, read by the readers and the drivers the spec
  lists, by SHA-256. `s2-both` was read by the reader as registered, the rerun by
  Amendment 1's, which changed the gate's launch point alone;
- the pairs, the readings and the first questions' reads are read again from the records' asks
  with the committed reader;
- the rerun passed its gate on all four points, with every ask read; `s2-both` failed on its
  launch point alone;
- each first question's read is its run's first ask, taken while the run went on;
- the stand, the settings, the corpus and the questions are the spec's and V4's;
- the environment lines bracket each run on V4's Ollama server;
- the files hold numbers, times, ids, enums, the reader's fixed reasons, the paths the spec names,
  versions and SHA-256 strings only;
- every table row below is built from the records, and so is each number of the prose that the
  test pins; the forecasts are the spec's words.

The record holds no question, answer, prompt, source name, log line, command line or process environment.

## Provenance and method

- **The stand:** `S=/Users/julia/RAG_new_chat_57420db`, code
  `57420db746e0510465bb5a08b7610e092b32e650` in both launches: V4's stand with the commits
  since, the continuation's code among them ([the spec](../specs/stage4-step2-self-eval-continuation.md#the-stand)).
  Mode `prod`, tenant `aircargo`, V4's model `qwen3:4b-instruct-2507-q4_K_M` on the CPU.
  - The drivers, two levels above each run, are the spec's by SHA-256 and the committed files:
    V4's `live_api.py`, step 1's `live_runner.py` and this step's `live_supervisor.py`.
- **The configuration,** as each run's `effective_settings.json` gave it: V4's
  `retrieval_top_k` 20, `rerank_top_k` 5, `rag_device` `cpu` and model, the stream's
  self-evaluation on, routing to `auto` at 80 or more; `streaming_self_eval_mode` `both`.
  Printed beside them, V4's too: the model's window, 4,096, and the suggestions on.
  - The launch's overrides were V4's, the 3,600-s timeouts and the CPU, and
    `STREAMING_SELF_EVAL_MODE=both`.
  - The supervisor's bound was 2,010 s for a run's first question and 1,365 s for the others.
- **The corpus:** aircargo's second-generation index under
  `/Users/julia/RAG_new_external_s1/aircargo`; the spec registered a byte-identical copy of it
  for each run. The record names its three files by SHA-256, V4's; the copies' check is not in
  it.
- **The questions:** the first thirteen of `evaluation/curated_cases_aircargo.jsonl`, V4's
  file and step 3's, in the same order in both runs.
- **The runs:**
  - `s2-both`, as registered: its thirteenth question ran past its cap, and the supervisor
    stopped the run, `failed` with the runner's exit 5. Its gate failed on its launch point
    alone, so no pair was read and every reading is `NOT_EVIDENCE`.
  - `s2-both-r2`, by Amendment 1: step 1's arm `B` on each question, the model unloaded before
    each, so no question started on the host cache's states of the ones before it. Its gate
    passed on all four points: launch, settings, drivers and asks. All thirteen asks were read,
    and the continuation held on each.
- **A pair** is one answer's two self-evaluations in one llama-server process: the continuation
  first, on the answer's own slot, then the classic. The answer's call loads the model, so the
  rerun's unload does not stand between a pair's two sides.
- **The first question's reads** were taken while each run went on. Each holds one ask, read,
  the record's first ask of that run. Its gate fails `launch` (the run still `running`) and
  `asks` (one of thirteen), as a read of one question of a running run must. The continuation
  held on both and took under half the classic's seconds, so neither run stopped there.
- **The environment:** four lines, one before and one after each run; the line after `s2-both`
  was taken late, shortly before the rerun's own. All four name Ollama 0.33.2 and one server, V4's, with
  V4's Python and distributions.
- **The Mac was shared,** as the spec says: other projects' processes ran beside `s2-both`
  (Amendment 1).

## The reading

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| Speed: the continuation's cost below the classic's seconds on more questions, the exact two-sided sign test's p below 0.05 | **faster** | below on 13 of 13 readable questions, above on 0; p 0.000244 | faster, on 13 of 13 |
| Use: the median saving, the classic's seconds less the continuation's cost, at least 30 s | **useful** | 54.009 s, 50.964–67.758 s by question; the median ratio 0.1408 | useful |
| Routes: at most one compared question routed otherwise | **agree** | 1 of 13: `aircargo-probation-extend` | agree, with the least confidence |
| Scores: the continuation scored 1–100 on all but at most one readable question | **held** | missed on 0 of 13 | held |
| The candidate: the continuation when faster, useful, agreeing and held | **continuation** | all four | the continuation |

With thirteen readable questions, faster needed at least 11 of 13 (p = 0.0225); the
continuation was below on all thirteen.

## Per question

The rerun's thirteen pairs. A pair's cost is the continuation's seconds, with the classic's added
where the continuation did not hold, which it held on all thirteen. Its saving is the classic's
seconds less that cost, and its ratio is that cost over the classic's seconds. A route is `auto`
at a score of 80 or more, else `human`. The last column is the continuation's request as Ollama
counted it: its prompt's tokens and the seconds spent reading them.

| Position | Question | The classic, s | The continuation, s | Saving, s | Ratio | Scores, the classic / the continuation | Routes, the classic / the continuation | The continuation's prompt, tokens / s |
|---|---|---|---|---|---|---|---|---|
| 1 | `aircargo-probation-data` | 61.775 | 8.483 | 53.292 | 0.1373 | 100 / 100 | auto / auto | 2,558 / 7.633 |
| 2 | `aircargo-probation-extend` | 76.328 | 8.570 | 67.758 | 0.1123 | 60 / 90 | human / auto | 2,832 / 7.906 |
| 3 | `aircargo-probation-dismissal` | 75.894 | 8.635 | 67.259 | 0.1138 | 95 / 100 | auto / auto | 2,677 / 7.748 |
| 4 | `aircargo-dismissal-check` | 79.246 | 12.789 | 66.457 | 0.1614 | 100 / 100 | auto / auto | 2,718 / 11.859 |
| 5 | `aircargo-dismissal-lawyer` | 69.467 | 13.853 | 55.614 | 0.1994 | 100 / 100 | auto / auto | 2,593 / 10.706 |
| 6 | `aircargo-dismissal-order` | 64.716 | 8.782 | 55.934 | 0.1357 | 100 / 100 | auto / auto | 2,671 / 7.656 |
| 7 | `aircargo-leave-sources` | 62.223 | 8.764 | 53.459 | 0.1408 | 100 / 100 | auto / auto | 2,590 / 7.663 |
| 8 | `aircargo-leave-compensation` | 61.280 | 8.997 | 52.283 | 0.1468 | 95 / 100 | auto / auto | 2,570 / 7.762 |
| 9 | `aircargo-leave-risk` | 59.491 | 8.527 | 50.964 | 0.1433 | 100 / 100 | auto / auto | 2,493 / 7.560 |
| 10 | `aircargo-matliab-check` | 59.833 | 8.429 | 51.404 | 0.1409 | 100 / 100 | auto / auto | 2,492 / 7.553 |
| 11 | `aircargo-matliab-disputed` | 62.985 | 8.526 | 54.459 | 0.1354 | 100 / 100 | auto / auto | 2,570 / 7.646 |
| 12 | `aircargo-templates-choose` | 59.749 | 8.449 | 51.300 | 0.1414 | 100 / 100 | auto / auto | 2,505 / 7.629 |
| 13 | `aircargo-templates-checklist` | 62.691 | 8.682 | 54.009 | 0.1385 | 100 / 100 | auto / auto | 2,611 / 7.773 |

## Per run

The medians and the memory are over each run's read asks, within each ask's own window of the
supervisor's samples.

| Run | Started, UTC | Arm | Status, the runner's exit | Asks read | The model's load at the preload, s | The first token, a median, s | The total, a median, s | The swap used, at most, MiB | llama-server's resident memory, at most, MiB |
|---|---|---|---|---|---|---|---|---|---|
| `s2-both` | 08:37:29 | none | failed, 5 | 12 of 13 | 52.809 | 490.527 | 639.163 | 11,582.00 | 3,741.1 |
| `s2-both-r2` | 17:13:05 | `B` before each question | complete, 0 | 13 of 13 | 41.139 | 137.087 | 246.674 | 3,565.25 | 3,772.1 |

`s2-both`'s thirteenth ask, unread, had its first token at 1,281 s and its total at 1,365.057 s,
past its cap.

## Printed, deciding nothing

The spec's list, over the rerun's thirteen pairs:

| Printed | The rerun |
|---|---|
| The saving, summed, s | 734.192 |
| The saving, the least, s | 50.964 |
| The continuation's cost, a median, s | 8.635 |
| The classic's seconds, a median | 62.691 |
| The classic's call in its span, a median, s | 62.664 |
| The continuation's counters, medians: prompt tokens, prompt s, generated tokens, generated s | 2,590, 7.663, 4, 0.750 |
| The scores, a median, the classic / the continuation | 100 / 100 |
| The continuation scored higher / the same / lower | 3 / 10 / 0 |
| The classic's routes | auto 12, human 1 |
| The continuation's routes | auto 13 |
| The answer's call, a median, s | 91.588 |
| The first token, a median, s | 137.087 |
| The total, a median, s | 246.674 |
| The swap used, at most, MiB | 3,565.25 |
| llama-server's resident memory, at most, MiB | 3,772.1 |
| The swap-outs, summed over the asks | 1,645,921 |

The classic's counters are null in every ask: the code builds the classic's entry from its score
and seconds alone (`_self_eval_entry` in `api/routers/conversation.py`), so the record holds
Ollama's counters for the continuation only. The classic's prompt was
estimated at 2,665–2,907 tokens in its span.

After the classic each ask made one more model call, whose span carries no output limit. The
reader names it `other`, not the suggestions', so it prints no suggestions' seconds; every answer
got three suggestions.

### `s2-both`'s twelve, outside the rule

Not on the spec's list (mine, no rule of the spec): `s2-both`'s gate failed, so its asks make no
pair, and their two sides stand here as its record keeps them. On its twelve read asks the
continuation took
8.847–15.284 s against the classic's 60.245–131.300 s
and scored the same or higher on 12 of 12.
Their routes differed on `aircargo-probation-extend` alone,
the classic's 60 against the continuation's 95.

| Position | Question | The classic, s | The continuation, s | Scores, the classic / the continuation | The total, s |
|---|---|---|---|---|---|
| 1 | `aircargo-probation-data` | 66.487 | 9.035 | 100 / 100 | 576.606 |
| 2 | `aircargo-probation-extend` | 80.803 | 10.622 | 60 / 95 | 527.568 |
| 3 | `aircargo-probation-dismissal` | 131.300 | 14.000 | 100 / 100 | 847.510 |
| 4 | `aircargo-dismissal-check` | 72.406 | 10.170 | 100 / 100 | 1,165.399 |
| 5 | `aircargo-dismissal-lawyer` | 79.898 | 15.284 | 100 / 100 | 953.136 |
| 6 | `aircargo-dismissal-order` | 67.566 | 9.254 | 95 / 100 | 536.467 |
| 7 | `aircargo-leave-sources` | 63.085 | 8.962 | 100 / 100 | 397.771 |
| 8 | `aircargo-leave-compensation` | 64.006 | 8.847 | 95 / 100 | 449.327 |
| 9 | `aircargo-leave-risk` | 60.245 | 8.869 | 100 / 100 | 437.805 |
| 10 | `aircargo-matliab-check` | 65.077 | 10.017 | 100 / 100 | 944.869 |
| 11 | `aircargo-matliab-disputed` | 66.568 | 11.332 | 100 / 100 | 775.816 |
| 12 | `aircargo-templates-choose` | 70.609 | 11.988 | 100 / 100 | 701.721 |

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| **faster** on 13 of 13, and **useful**: the continuation's prompt read in ≈ 10–15 s against the classic's 65–105 s | **faster** on 13 of 13, and **useful**: the continuation's prompt read in 7.553–11.859 s, the classic took 59.491–79.246 s |
| **scores held** | **held**: the continuation scored all 13 |
| **routes agree**, with the least confidence of the four | **agree**: 1 of 13 routed otherwise |
| The forecast candidate: the continuation. | The candidate: **continuation**. |
| ≈ 1 h 10 min – 1 h 30 min for the thirteen on an idle Mac | the thirteen asks' totals 55.8 min; 59.6 min from the launch to the environment line after the run |

The last row is Amendment 1's forecast for the rerun.
`s2-both`'s thirteen asks' totals summed to 161.3 min, its thirteenth at its cap.

## What it says

- **The continuation is faster, by the frozen rule:**
  below the classic on 13 of 13 questions, p 0.000244, where the spec needed p below 0.05.
  The median saving is 54.009 s, the median ratio 0.1408.
- **The slot was kept, by the seconds and the counters:** the continuation took
  a median 8.635 s against the classic's 62.691 s,
  with a median 2,590 prompt tokens counted, read in 7.663 s.
  By step 0 the classic, reading its own prompt from its start,
  read 2,377–2,690 prompt tokens and spent 65.0–105.1 s reading them.
  The record does not count the tokens kept from the slot.
- **The routes agree, by the frozen rule,** and the one that moved went up:
  `aircargo-probation-extend`: the classic's 60 (human) against the continuation's 90 (auto).
  The continuation scored
  higher on 3 of 13 questions and lower on none.
  The spec's forecast feared this: a model rating its own answer in its own conversation may
  score it higher. Thirteen answers cannot tell that from a classic too strict.
- **The scores held:** the continuation gave one integer of 1–100 on every answer, so no answer
  fell back to the classic.
- **The candidate is the continuation.** A candidate is no default (below).
- **`s2-both` agrees, outside the rule:** on its twelve read asks the continuation was faster
  on each and scored none lower, and the same one route moved
  ([its table](#s2-boths-twelve-outside-the-rule)).
- **The rerun's memory stayed low:** with the model unloaded before each question, the swap
  used reached 3,565.25 MiB at most against `s2-both`'s 11,582.00 MiB, and the rerun took
  a median 246.674 s an ask against `s2-both`'s 639.163.
  That is Amendment 1's arm, not production's path (below).

## What it does not say

- **No default changes here.**
  The default stays `classic` until step 2b reads.
  Step 2b asks the continuation cold, first on step 2's 25 warm-scored answers, then on stage
  3's 80 labelled aircargo answers, the 17 bad ones first, beside the classic's 2 caught of 17
  and 0 marked of 63
  ([its spec](../specs/stage4-step2b-continuation-labels.md), registered in `1e0600a` and amended
  in `45f7e51`, both before its first request). It runs because this candidate is the
  continuation.
- **Nothing on the badge's quality here.** All thirteen answers were routed `auto` by the
  continuation and all but one by the classic. Whether the continuation catches a bad answer is
  step 2b's to read.
- **Not production's pace.** The rerun unloaded the model before each question: its retrieval ran
  without the model resident, and its answer paid the model's load. Its totals and first tokens
  say nothing of production's pace, which keeps the model resident (Amendment 1). The
  continuation's seconds are a warm slot's, as production's would be: it ran right after its
  answer, in the answer's process.
- **The classic ran second,** right after the continuation, on the same answer: its seconds are
  a classic's after a continuation, not a classic-only run's, and that bias is not measured.
- **The two sides do not see the same text.** The continuation sees the answer as it streamed,
  `[N]` markers in, beside the answer prompt's instructions and documents; the classic sees it
  without markers, beside the documents in V3's layout. A route difference is read, not
  explained.
- **Thirteen questions of one corpus, one stand, one day, on a Mac other projects share.** K = 20
  only. A prefix kept is read from the seconds and the counters, not from token ids.
- Step 2 is no slice by the acceptance rule: the default is unchanged, and no case or quality
  number changes.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `step2.json` | 29,332 | `e28b0fcbf032f2e745593d07baa01db9536a29f5ed52d961534779e78919e15f` |
| `s2-both.q1.step2.json` | 6,993 | `78ab61762b164f0c05bc87b5497e987ef03937b06596bb0b23b8c74dae59dbbb` |
| `step2.s2-both-r2.json` | 44,504 | `2cc0d1dd284d4790bb92122a8c42eec59db108a0a4fadc40abaae6e03b5fa65c` |
| `s2-both-r2.q1.step2.json` | 7,032 | `a792cdcdb47dbe3f154a8f5d5bef49f37910f718160aab7df509a17560494968` |
| `environment.jsonl` | 3,928 | `a6033ffe6af8d8033e640210a44b0edcd86cbf1a0890bef7353ed423f1a429b4` |
