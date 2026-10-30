# Stage 4, item 5a: INT8 of the reranker in the chat, the short live series — 2026-10-30

The question: does INT8 of the reranker, the chat's `RAG_RERANKER_RUNTIME=onnx`, rerank faster in
the chat itself, beside the resident answer model, and does a whole question get faster with it?
On the idle Mac INT8 kept the gold and reranked aircargo's thirty faster on 30 of 30, a ratio
1.751 ([item 5a's record](stage4-step5a-record.md)); in the chat the rerank also waits for memory
([step 1's record](stage4-step1-record.md)). Eight runs of six aircargo questions through
`/api/ask/stream` at `81cd2ad`, PyTorch and INT8 ABBA twice, twenty pairs in four blocks, by
[`stage4-step5a-live.md`](../specs/stage4-step5a-live.md). The spec was registered with its tools
and their test in `3136fb8` before the first request; nothing changed after it.
The series started at 17:14 UTC on 2026-10-30 and stopped at 19:29 UTC, in its first block.

**`NOT_EVIDENCE` — nothing is read.** The block's INT8 run failed step 7's look at the Mac after
it twice: `s5a-int8-1` with 2 matches of step 3's pattern, and its rerun `s5a-int8-1-r2` with 2.
By step 7 the block's five pairs are unread and the series is below sixteen; the 6 runs left
could give 15 pairs at most, so they were not run. What the record's two runs measured is
printed below and decides nothing.

Record: [`reports/stage4-step5a-live/81cd2ad/`](../../reports/stage4-step5a-live/81cd2ad/):
- `live5a.json`: the two runs in the record's places — `s5a-torch-1`, and `s5a-int8-1-r2` read in
  its run's place —, the twenty pairs, the stand's gate and the readings, read by step 8 after
  the stop;
- `<run>.live5a.json`: each run's own read, taken right after it, with its gate; the replaced
  `s5a-int8-1`'s too, which the record never reads;
- `<run>.q1.live5a.json`: the first question's read in each of the three runs, taken while the run
  went on;
- `<run>.samples.jsonl`: each run's samples, one every 5 s;
- `environment.jsonl` and `hf.txt`: the stand's server and distributions, and the reranker's
  snapshot, before run 1 and after the last run that ran; `after-runs.txt`: step 7's look at the
  Mac after each run.

Every number below is the record's unless named otherwise: its readings, its runs and its pairs.
What it does not print itself — each pair's ratio and saving, a run's medians and length — the
test computes from the record and the samples. What is named outside the record is not in it and
not checked.

The tools are the spec's: this series' reader and supervisor
([`reports/stage4-step5a-live/tools/`](../../reports/stage4-step5a-live/tools/)), step 1's runner
and reader, V4's API driver and step 0's sampler, unchanged.
Checked by [`tests/test_stage4_step5a_live_artifact.py`](../../tests/test_stage4_step5a_live_artifact.py):
- the files are the bytes copied from the Mac, read by the tools the spec lists, by SHA-256;
- the pairs, the stand's gate and the readings are read again from the runs with the committed
  reader; each run's own read is the record's run or the replaced one, and the first question's
  reads are their runs' first asks;
- every window, state and load attaches again from the committed samples; no sample lies within
  a hundredth of a second of a window's or an answer call's edge, and the two that near a
  question's edge move neither its load nor the samples' cover across it;
- each sample's note is one step 1's reader keeps quiet: no `llama-server`, and top's one missing
  row, the rerun's server exiting after its last question;
- the runs ran in the registered order until the stop, the rerun right after its run; each passed
  its gate on all eight points, each ask ran beside the resident model, one `llama-server` a run;
- the blocks that never ran pair nothing; step 7 leaves the rerun's block unread, and the series
  is `NOT_EVIDENCE` whatever the rest would have read;
- the stand is V4's corpus and item 5a's export, on step 1's server and distributions before the
  first run and after the last that ran, with the reranker's snapshot alone both times;
- after each run no model and no lock; a match after both INT8 runs and none after PyTorch's, and
  each run's own sampler saw no `llama-server` at its end;
- the files hold numbers, ids, paths and hashes only;
- every table row below is built from the record, and so is each number of the prose that the
  test pins; the forecasts and the outcomes are the spec's words.

The record holds no question, answer, prompt, source name or log line.

## Provenance and method

- **The stand:** code `81cd2ade80ea9bc5a4f3ea721a16bd05037136fd`, raised once on the Mac by the
  spec's `raise_stand.sh` and reused; mode `prod` with the code defaults — K = 20 candidates,
  five kept, `RAG_DEVICE=cpu`, the 3,600-s ceiling; tenant `aircargo` on V4's corpus files, a
  byte-identical copy of its index for each run, removed after it.
- **The models:** the answer model `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef3…`) on the CPU,
  resident through each run (step 1's arm A); the reranker `BAAI/bge-reranker-v2-m3`, snapshot
  `953dc6f6…`, in PyTorch's CrossEncoder (`RAG_RERANKER_RUNTIME=torch`) or in item 5a's INT8
  export `57335a9f…` in ONNX Runtime 1.23.2 (`RAG_RERANKER_RUNTIME=onnx`); each run named its
  runtime.
- **The runs:** three of the eight — `s5a-torch-1`, `s5a-int8-1` and its rerun `s5a-int8-1-r2` —,
  each a fresh API, database and `llama-server`; the six questions in the registered order, the
  first, `aircargo-dismissal-lawyer`, the warm-up, never paired. The API loads the reranker at its
  start, before the model's preload and the first question.
- **The gates:** all three runs passed their gates on all eight points; the stand's gate passed.
- **The stop:** step 7's line after `s5a-int8-1` held 2 matches, and the run ran again as
  `s5a-int8-1-r2`; the line after the rerun held 2 again. No model and no lock after either, and
  each run's own sampler saw no `llama-server` in its last samples; which processes matched, the
  line does not say. By the supervisor's process log of each run, outside the record, a Python of
  another project's virtual environment ran at up to 100 % CPU in the last minutes of each INT8
  run — 18:38–18:41 and 19:24–19:28 UTC — and was still running when the log ended; the same
  environment ran in the middle of `s5a-torch-1`, 17:26–17:39 UTC, and was gone before its line.
  The chain that ran the series stopped at the rerun's line; step 4 after the last run and step 8
  were then run by hand at 19:37 UTC, the record over the two runs in the record's places.
- **The Mac:** no job of ours ran on it during the series. Ours there were the chain that ran it,
  a `grep` of its log over ssh every 4 min that waited for its milestones, and a few reads over
  ssh of its log, of finished files and of the process list.

## The reading

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| The rerank: INT8's seconds below PyTorch's on more readable pairs, the exact two-sided sign test's p below 0.05, every block below on more of its pairs than above, at least sixteen readable | **`NOT_EVIDENCE`** | 0 readable of 20: block 1's 5 unread by step 7, blocks 2–4 not run | faster, INT8 below on ≈ 16–19 of the 20, every block leaning INT8 |
| The whole question: the same rule on the whole seconds | **`NOT_EVIDENCE`** | 0 readable of 20: block 1's 5 unread by step 7, blocks 2–4 not run | no detected difference more likely than faster; INT8 below on ≈ 12–15 of the 20 |
| The outcome, by the rerank's reading | **`NOT_EVIDENCE`**: nothing is read | the stand's gate passed | faster |

A pair is readable when both runs passed their gates, both asks were read and held arm A, at the
same position on the same candidates, with rerank and whole seconds; step 7 leaves a block's five
unread when its run fails the look after it again as `-r2`. A tie counts on neither side. The
spec's outcome for `NOT_EVIDENCE`: «nothing is read».

## Block 1's five, as the reader pairs them — printed, deciding nothing

The reader does not read `after-runs.txt`: it pairs block 1's five, counts them readable and
reads them `NOT_EVIDENCE` too, as fewer than sixteen. One block cannot read faster at any
seconds: with all 5 one way the sign test's p is 0.0625, above 0.05.

| The reader on block 1's five | Rerank | Whole question |
|---|---|---|
| INT8 below / above / ties | 5 / 0 / 0 | 4 / 1 / 0 |
| By block | 5–0, 0–0, 0–0, 0–0 | 4–1, 0–0, 0–0, 0–0 |
| The exact two-sided sign test's p | 0.0625 | 0.375 |
| The median ratio, PyTorch's seconds over INT8's | **6.753** | **1.5638** |
| The ratio's range by pair | 4.716 to 9.895 | 0.801 to 3.193 |
| The median saving, PyTorch's seconds less INT8's | **145.898 s** | **146.473 s** |
| The saving's range by pair | 103.449 to 302.887 s | −99.758 to 419.814 s |
| The reader's answer | `NOT_EVIDENCE` | `NOT_EVIDENCE` |

PyTorch's run against INT8's rerun, a question at one position. The ratio is PyTorch's rerank
seconds over INT8's; the saving, PyTorch's whole seconds less INT8's. The five is the agreement
of the five kept, by the SHA-256 of their list.

| Block | Question | Rerank, s, PyTorch / INT8 | Ratio | Whole, s, PyTorch / INT8 | Saved, s | The five |
|---|---|---|---|---|---|---|
| 1 | `aircargo-dismissal-order` | 126.898 / 23.449 | 5.412 | 542.076 / 321.907 | 220.169 | same order |
| 1 | `aircargo-leave-sources` | 336.938 / 34.051 | 9.895 | 646.598 / 500.125 | 146.473 | same order |
| 1 | `aircargo-leave-compensation` | 160.521 / 34.040 | 4.716 | 402.575 / 502.333 | −99.758 | same order |
| 1 | `aircargo-leave-risk` | 209.978 / 31.094 | 6.753 | 611.229 / 191.415 | 419.814 | same order |
| 1 | `aircargo-matliab-check` | 167.501 / 21.603 | 7.754 | 403.154 / 257.803 | 145.351 | same set |

## The runs

The minutes run from a run's first sample to its last. The reranker's load fell in the API's
start; the warm-up is the run's first question, its rerank, its retriever's build and its whole
seconds. The later medians are the run's five paired questions'. The load is the Mac's 1-, 5- and
15-minute load in step 7's line after the run; the matches, that line's count of step 3's pattern.
The replaced run's numbers are its own read's; the record never reads them.

| Run | Runtime | UTC | Minutes | Reranker's load, s | Warm-up: rerank / build / whole, s | Later reranks, a median, s | Later whole, a median, s | Load after the run | Matches after the run |
|---|---|---|---|---|---|---|---|---|---|
| `s5a-torch-1` | torch | 17:14:34–18:05:57 | 51.4 | 3.390 | 122.022 / 2.334 / 361.043 | 167.501 | 542.076 | 3.97 / 4.37 / 4.15 | 0 |
| `s5a-int8-1`, replaced | onnx | 18:12:10–18:42:13 | 30.1 | 2.900 | 21.339 / 2.171 / 257.895 | 28.648 | 279.333 | 5.60 / 6.28 / 5.36 | 2 |
| `s5a-int8-1-r2`, the stop | onnx | 18:51:33–19:29:19 | 37.8 | 2.764 | 21.718 / 2.458 / 357.730 | 31.094 | 321.907 | 4.03 / 5.64 / 5.53 | 2 |

## Printed, deciding nothing

| Printed, a median over block 1's five | PyTorch | INT8 |
|---|---|---|
| The rerank, s | 167.501 | 31.094 |
| The whole question, s | 542.076 | 321.907 |
| The vector search, s | 83.581 | 74.699 |
| The retrieval, s | 244.457 | 98.699 |
| The first token, s | 307.550 | 166.999 |
| The question's total, s | 542.043 | 321.858 |
| The answer call's first chunk, s | 65.798 | 68.621 |
| Pages faulted back inside the rerank, MiB | 2,279.906 | 595.395 |
| llama-server's footprint at the rerank's start, MiB | 5,327.000 | 5,331.000 |
| The swap used at the rerank's start, MiB | 3,988.250 | 4,629.750 |
| The highest 1-minute load inside the rerank | 4.380 | 4.130 |
| The highest 1-minute load inside the question | 7.790 | 9.920 |

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| the eight run gates pass, and the stand's | 3 of the 3 runs that ran passed; `s5a-int8-1` ran again as `s5a-int8-1-r2`, 2 matches after it and 2 after the rerun, so the series stopped, 6 runs not run; the stand's passed |
| The rerank reads **faster**: INT8 below on ≈ 16–19 of the 20 pairs, every block leaning INT8 | **`NOT_EVIDENCE`**: 0 readable of 20; on block 1's 5 the reader pairs, INT8 below on 5, above on 0 |
| a ratio ≈ 1.5–2 and a saving ≈ 35–65 s of PyTorch's ≈ 100–135 s | on those 5: a ratio 6.753 and a saving 145.898 s of PyTorch's median 167.501 s |
| The whole question: INT8 below on ≈ 12–15 of the 20, the median saving about the rerank's; **no detected difference** is more likely than **faster** | **`NOT_EVIDENCE`**; on those 5: INT8 below on 4, above on 1, p 0.375; a median saving 146.473 s |
| the same order on 16 pairs and the same set on `aircargo-matliab-check`'s four | on those 5: the same order on 4, the same set on 1, another set on 0; `aircargo-matliab-check`'s: same set |
| the warm-up's rerank ≈ 90–180 s for PyTorch … and ≈ 35–70 s for INT8, below its later reranks' ≈ 50–90 s | PyTorch's 122.022 s; INT8's 21.718 s, its later reranks a median 31.094 s |
| A run's first question ≈ 480 s with PyTorch … and ≈ 350 s with INT8, no more than its later ones; a later one ≈ 400 s with PyTorch … and ≈ 350 s with INT8 | a first question 361.043 s with PyTorch and 357.730 s with INT8; a later one a median 542.076 s and 321.907 s |
| ≈ 5 h 30 min of runs once the Mac is idle … A run ≈ 44 min with PyTorch and ≈ 38 min with INT8 | 2 h 15 min from the first run's first sample to the rerun's last, where the series stopped; a run 51.4 min with PyTorch, 30.1 and 37.8 min with INT8, the replaced run and its rerun |

The forecast's ratio counted INT8's arithmetic and named its quarter of the weights to fault back,
not that quarter's size in the chat: PyTorch faulted back a median 2,279.906 MiB inside the
rerank, INT8 595.395 — printed, on one run a side.

## What it says

- **Nothing is read, by the frozen rule.** The rerun failed step 7's look again, block 1's five
  are unread, and the twenty less them is below sixteen: `NOT_EVIDENCE`, the spec's «nothing is
  read». The package question gets no chat number for INT8; its idle numbers stand
  ([item 5a's record](stage4-step5a-record.md)).
- **The pace, printed.** In the record's two runs INT8's rerank took 21.603 to 34.051 s on the
  block's five against PyTorch's 126.898 to 336.938 s, a median ratio 6.753 against the
  forecast's ≈ 1.5–2. The whole question a median 321.907 s against 542.076 s. One run a side,
  with another project's job inside both: a pace, not a reading.
- **The stop was not the series'.** No model, no lock and no `llama-server` at either INT8 run's
  end; another project's job on the shared Mac, outside the record, ran at both INT8 runs' ends,
  and the pattern meant to keep the runs clean stopped the series.

## What it does not say

- **INT8's gain in the chat.** Nothing is read; the pace above is one block, a run a side.
- **Seconds, not answers.** INT8's five differs from PyTorch's on 1 of the block's five here (the
  same set, another order) and on 307 of item 5a's 400; adopting it re-answers item 6 and
  stage 5. Nothing here reads quality.
- **Whether INT8 enters the path** is her word (PLAN.md §8.3, item 2).
- **Memory:** the sampler reads `llama-server`'s processes and the whole Mac, not the API's
  process; the reranker's own footprint in the chat is not read.
- **The cold start:** the load and the warm-up are printed, not compared.
- One block of five questions of one corpus, one stand, one day, on a Mac other projects share:
  not the product's speed (item 7).

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `live5a.json` | 64,921 | `aa2a03f0a672685f911a0ca2967206abf460eb89991ed123b5037b74c3ac7ae9` |
| `s5a-torch-1.live5a.json` | 31,849 | `3d21189fde3e1b81dcfc6be0cffbccae485ac8510d5ab9881a0c03fb7ec636d0` |
| `s5a-torch-1.q1.live5a.json` | 12,999 | `ce1e75b54f54b048ffc5ec235f08b9fdc8a1fde0eeafb8df37b7252f85503586` |
| `s5a-torch-1.samples.jsonl` | 394,029 | `3a63923336b79596af884d6f2b21db7f38fd99c5bae47ff83b3f3c57f893ce84` |
| `s5a-int8-1.live5a.json` | 31,967 | `979c969f34f78912aa373e70909784c05cd5c669da181ea618f19af32837a20f` |
| `s5a-int8-1.q1.live5a.json` | 13,121 | `224668aa2cf0f224ea2ddbb2b6543e56ae14045044e8bb1b46ab0b7956e1c579` |
| `s5a-int8-1.samples.jsonl` | 232,422 | `68c1ff7ada0bb9d24270c912b91f2bf5a9af7c352387704d70e0f5b256063ded` |
| `s5a-int8-1-r2.live5a.json` | 32,011 | `586adbb2b03ee81b980581d7f44db022944956ab4b710e2f33cf95d9034d8088` |
| `s5a-int8-1-r2.q1.live5a.json` | 13,159 | `ab9f03b25e5d586edeee71802a98148d0ceb8577f7f9dddf520a7e29a33133c1` |
| `s5a-int8-1-r2.samples.jsonl` | 291,507 | `d9b47f5a5ddbdf2008dced5ac0ea52ae4ac04948f20c52f8fba1527d294064aa` |
| `environment.jsonl` | 1,964 | `5420975ae1f072110db4aeeb733a73ecf202b865591887793d8898bf3def4ce3` |
| `hf.txt` | 164 | `2838d1392924c96cb9a9b5e808244210abbd67930888f9e8a2cda9a32b5bd925` |
| `after-runs.txt` | 253 | `9279f5f77e77ad1952c0176889c51b10872ed61cce6ea54a2db263d585a83596` |
