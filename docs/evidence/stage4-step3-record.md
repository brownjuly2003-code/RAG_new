# Stage 4, step 3: K = 14 against 20, timed with the retrieval alone — 2026-10-28

The question: how many of the rerank's seconds does K = 14 save against 20? The K curve
([its record](k-curve-record.md)) found 14 the smallest K without a detected loss of the gold
after expansion, and Julia's word on K ([`PLAN.md`](../../PLAN.md) §8.3) needs its seconds
beside its gold. Thirteen aircargo questions were asked on V4's stand with no model, in four
runs, ABBA, read by [`stage4-step3-k-timing.md`](../specs/stage4-step3-k-timing.md). The spec
was registered with its reader and the reader's test
in `3fc8ce7` before the first request; nothing changed after it.
The runs started between 22:21 and 22:57 UTC on 2026-10-28.

Record: [`reports/stage4-step3/4f48fed/`](../../reports/stage4-step3/4f48fed/):
- `step3.json`, the four runs, the pairs and the readings;
- each run's own read, the gate's (`s3-k20-1.step3.json`, `s3-k14-1.step3.json`,
  `s3-k14-2.step3.json`, `s3-k20-2.step3.json`);
- the first question's read, taken while run 1 went on (`s3-k20-1.q1.step3.json`).

Every number below is `step3.json`'s unless named otherwise: its `readings`, its `pairs` (a
question's four asks, two at each K) and its `runs` (each run's launch, settings, build and
thirteen asks). What the record does not print itself — the candidates' ratios, the per-run
medians and sums, the asks' gaps and the reads against one K = 20 run — the test computes from
them. The K curve's numbers are its record's
([`reports/k-curve/5e308fe/`](../../reports/k-curve/5e308fe/)); V4's are
[`v4-aircargo.json`](../../reports/answer-prompt-v4/4f48fed/v4-aircargo.json)'s.

The reader is
[`reports/stage4-step3/tools/step3_reader.py`](../../reports/stage4-step3/tools/step3_reader.py).
Checked by [`tests/test_stage4_step3_artifact.py`](../../tests/test_stage4_step3_artifact.py):
- the files are the bytes copied from the Mac, read by the reader and the drivers the spec
  lists, by SHA-256;
- the pairs and the readings are read again from the record's asks with the committed reader;
- each run's own read is the record's run. The first question's read is run 1's first ask,
  taken while the run went on;
- all four runs pass their gates on all five points;
- the stand, the settings and the questions are the spec's, V4's and the K curve's;
- the live pools have the K curve's counts, and the five kept at 14 are K = 20's exactly where
  the K curve kept all five;
- the files hold numbers, times, ids, enums, the reader's fixed notes, a model name, the spec's
  path and SHA-256 strings only;
- every table row below is built from the record, and so is each number of the prose that the
  test pins; the forecasts are the spec's words.

The record holds no question, document, source name, prompt or command line.

## Provenance and method

- **The stand:** V4's, `S=/Users/julia/RAG_new_chat_4f48fed`, code
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1` in every launch, mode `retrieval`, tenant
  `aircargo`.
  - Mode `retrieval` starts no API and no database. The supervisor runs stage 2's
    `live_retrieval.py` once, on the CPU: the API's retriever, a question at a time, nothing
    generated. Ollama held no model before or after any run; the launch names V4's model,
    `qwen3:4b-instruct-2507-q4_K_M`, which this mode never loads.
  - The drivers, two levels above each run, are the spec's by SHA-256 and the committed files:
    step 1's `live_supervisor.py`, stage 2's `live_retrieval.py` and `stage2_common.py`, V4's
    `live_api.py`.
- **The configuration,** as each run's `effective_settings.json` gave it: `retrieval_top_k` the
  run's K, `rerank_top_k` 5 and `rag_device` `cpu`, V4's values but K. The reader keeps no
  other setting.
  - K = 20 is the code default: `s3-k20-1` and `s3-k20-2` set no `RAG_RETRIEVAL_TOP_K`. K = 14
    came from `RAG_RETRIEVAL_TOP_K=14` in `s3-k14-1` and `s3-k14-2`.
  - The supervisor's bound was 1,400 s.
  - The cross-encoder is V4's,
    `BAAI/bge-reranker-v2-m3` by V4's settings; step 3's record does not name it.
- **The corpus:** aircargo's second-generation index under
  `/Users/julia/RAG_new_external_s1/aircargo`; the spec registered a byte-identical copy of it
  for each run. V4's record names that corpus by SHA-256 (its manifest `2b2e9232…`).
  Step 3's record names no corpus file, and the copies' `diff -rq` check is not in it.
- **The questions:** the first thirteen of
  `evaluation/curated_cases_aircargo.jsonl` (`3737d694…`, V4's file and the K curve's), in the
  same order in every run. `aircargo-probation-data` came first: it loads the two encoders in
  every run and pairs with nothing. The other twelve make the pairs.
- **The runs:** `s3-k20-1`, `s3-k14-1`, `s3-k14-2` and `s3-k20-2`, at K = 20, 14, 14 and 20,
  each asking the thirteen at positions 1–13 ([Per run](#per-run)).
- **The gates:** all four runs' gates passed on all five points: launch, settings, drivers, asks
  and summary. Every ask was read: its rerank `ok`, its vector and BM25 lanes K long, five kept.
  The rerank scored every merged candidate. No run carries a note.
- **The first question's read** was taken while `s3-k20-1` went on. Its one ask was read, and it
  is the record's first ask of that run. Its gate fails `launch` (the run still `running`),
  `asks` and `summary` (no `retrieval-cpu.json` yet), as a read of one question of a running run
  must.
- **The Mac was shared,** as the spec says. Step 3 runs no sampler, so the record holds no load,
  and the idle check before each run is not in it.

## The reading

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| The answer: K = 14 below on more questions, the exact two-sided sign test's p below 0.05 | **faster** | below on 12 of 12 readable questions, above on 0; p 0.000488 | faster, on 12 of 12 |
| The number: the median saving, K = 20's rerank seconds less K = 14's | **14.566 s** | 9.282–25.307 s by question | ≈ 7–9 s |
| The number: the median ratio, K = 14's rerank seconds over K = 20's | **0.528** | 0.492–0.582 by question | ≈ 0.70 |

With twelve readable questions faster needed at least 10 of 12 (p = 0.039); K = 14 was below on
all twelve.

## Per question

A side is the mean of a K's two asks: the saving is K = 20's side less K = 14's, the ratio
K = 14's over K = 20's. The reranks are listed in run order, `s3-k20-1` / `s3-k20-2` and
`s3-k14-1` / `s3-k14-2`. Both asks of a K reranked the same pool, by SHA-256, and its count is
the K curve's; the candidates' ratio is the pool at 14 over the pool at 20. The last column
says whether the five kept at 14 are K = 20's five, in K = 20's order, by SHA-256.

| Position | Question | Pool at 20 / 14 | K = 20's reranks, s | K = 14's reranks, s | Saving, s | Ratio | Candidates' ratio | The five at 14 are K = 20's |
|---|---|---|---|---|---|---|---|---|
| 2 | `aircargo-probation-extend` | 36 / 24 | 38.596 / 50.989 | 22.053 / 21.995 | 22.768 | 0.492 | 0.667 | yes |
| 3 | `aircargo-probation-dismissal` | 37 / 25 | 37.044 / 48.268 | 23.856 / 23.692 | 18.882 | 0.557 | 0.676 | yes |
| 4 | `aircargo-dismissal-check` | 35 / 24 | 22.702 / 32.058 | 14.704 / 14.799 | 12.629 | 0.539 | 0.686 | no |
| 5 | `aircargo-dismissal-lawyer` | 35 / 23 | 22.921 / 31.958 | 14.034 / 14.226 | 13.309 | 0.515 | 0.657 | no |
| 6 | `aircargo-dismissal-order` | 30 / 22 | 20.039 / 28.277 | 13.835 / 13.858 | 10.312 | 0.573 | 0.733 | no |
| 7 | `aircargo-leave-sources` | 39 / 27 | 31.683 / 41.737 | 18.058 / 18.057 | 18.653 | 0.492 | 0.692 | yes |
| 8 | `aircargo-leave-compensation` | 37 / 25 | 25.545 / 32.515 | 14.697 / 14.720 | 14.322 | 0.507 | 0.676 | yes |
| 9 | `aircargo-leave-risk` | 39 / 27 | 30.519 / 40.333 | 18.511 / 18.590 | 16.876 | 0.524 | 0.692 | yes |
| 10 | `aircargo-matliab-check` | 28 / 20 | 17.238 / 24.469 | 11.122 / 11.050 | 9.768 | 0.532 | 0.714 | yes |
| 11 | `aircargo-matliab-disputed` | 29 / 21 | 19.086 / 25.364 | 12.842 / 13.045 | 9.282 | 0.582 | 0.724 | no |
| 12 | `aircargo-templates-choose` | 37 / 25 | 27.716 / 33.091 | 15.577 / 15.611 | 14.809 | 0.513 | 0.676 | yes |
| 13 | `aircargo-templates-checklist` | 39 / 27 | 58.943 / 50.077 | 29.270 / 29.135 | 25.307 | 0.536 | 0.692 | no |

## Per run

The first question loads the two encoders in every run and pairs with nothing; its seconds stand
here beside the twelve's.

| Run | K | Started, UTC | The retriever's build, s | First question's vector search, s | First question's rerank, s | The twelve's reranks, a median, s | The build and the thirteen retrievals, s |
|---|---|---|---|---|---|---|---|
| `s3-k20-1` | 20 | 22:21:02 | 15.382 | 52.838 | 86.272 | 26.631 | 509.774 |
| `s3-k14-1` | 14 | 22:36:45 | 9.105 | 1.858 | 15.985 | 15.140 | 237.225 |
| `s3-k14-2` | 14 | 22:46:51 | 8.946 | 1.680 | 19.627 | 15.205 | 240.739 |
| `s3-k20-2` | 20 | 22:57:02 | 14.864 | 2.108 | 51.820 | 32.803 | 512.504 |

## Printed, deciding nothing

The spec's list, over the twelve readable questions:

| Printed | K = 20 | K = 14 |
|---|---|---|
| The rerank's seconds, a median over both asks of the twelve | 31.820 | 15.188 |
| The same K's spread, a median of the two asks' difference over their mean | 0.277 | 0.004 |
| Questions whose two asks reranked the same pool | 12 of 12 | 12 of 12 |
| Questions whose two asks kept the same five | 12 of 12 | 12 of 12 |
| Questions whose pool had the K curve's count | 12 of 12 | 12 of 12 |

The same medians for the retrieval and its vector search are in [What it says](#what-it-says);
each run's build is in [Per run](#per-run).

### K = 14 against one K = 20 run alone

Not on the spec's list (mine, no rule of the spec): K = 14's side against each K = 20 run's ask
alone, since K = 20's two runs were apart ([What it says](#what-it-says)).

| K = 20's run | K = 14 below on | Median saving, s | Median ratio | Ratio by question |
|---|---|---|---|---|
| `s3-k20-1` | 12 of 12 | 11.402 | 0.612 | 0.495–0.691 |
| `s3-k20-2` | 12 of 12 | 17.817 | 0.460 | 0.432–0.583 |

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| **faster**, on 12 of 12 | **faster**, on 12 of 12 |
| the ratio ≈ 0.70, the K curve's candidates at 14 over 20 for these twelve (0.64–0.73) | 0.528; those candidates' ratio a median 0.689, 0.657–0.733 |
| a saving ≈ 7–9 s of a rerank ≈ 25–28 s at K = 20 | a saving of 14.566 s of a rerank of 31.820 s at K = 20, 26.631 and 32.803 s by run |
| a K = 20 run ≈ 7.6 min | 8.5 min in each, its build and thirteen retrievals |
| a K = 14 run ≈ 6 min | 4.0 min in each |
| ≈ 27 min for the four, ≈ 35 min with the copies, the checks and the reads | 25.0 min of the four builds and retrievals; from the first start to the last retrieval's end at least 44.5 min |

The forecast's run times held the retriever's build and the thirteen questions, as the measured
ones do. The record keeps no run's end, so no run's whole wall is read. The spec's range for the
candidates' ratio, 0.64–0.73, is not the K curve's counts for these twelve, which give the range
above.

## What it says

- **K = 14 reranks faster, by the frozen rule:**
  below K = 20 on 12 of 12 questions, p 0.000488, where the spec needed p below 0.05.
  The median saving is 14.566 s, the median ratio 0.528.
- **The rerank fell further than its candidates:**
  a median ratio of 0.528 against the pools' 0.689.
  Every question's ratio, 0.582 at most,
  lies below every question's candidates' ratio, 0.657 at least.
  The record does not say why.
- **The saving is the rerank's:**
  the whole retrieval saved a median 14.644 s and its vector search 0.108 s.
- **K = 20's two runs were apart, K = 14's were not:**
  `s3-k20-2` reranked slower than `s3-k20-1` on 11 of 12 questions, and the same K's
  spread was 0.277 at K = 20 against 0.004 at K = 14. A question's two K = 14 asks were
  at most 0.203 s apart, its two K = 20 asks 5.375–12.393 s.
  Against either K = 20 run alone K = 14 is below on 12 of 12, and
  the ratio is 0.612 against the first and 0.460 against the second.
- **The pools were the K curve's counts:** at both K, in every run, each question's pool had
  the K curve's count of candidates, the first question's too. The five kept at 14 were K = 20's
  five, in K = 20's order, by SHA-256,
  on 8 of 13 questions, exactly those where the K curve kept all five
  of K = 20's; where it kept four, they differed. What would be sent to the model moved on one
  question, `aircargo-matliab-disputed`:
  4 documents and 2,636 tokens at K = 20, 3 and 2,599 at K = 14.
  On the other twelve the documents sent and the prompt's estimated tokens were the same at
  both K.

## What it does not say

- **Retrieval seconds only; nothing on quality.** No model answered and nothing was judged.
  K's gold is the K curve's: at K = 14 the three external bases keep the gold after expansion
  in 136 of 250 questions against 141 at K = 20 (b 6, c 1, exact McNemar p 0.125): no loss
  detected, none excluded ([its record](k-curve-record.md)).
- **No K is adopted here.** The code default stays K = 20, and
  changing K in production is Julia's word ([`PLAN.md`](../../PLAN.md) §8.3). A changed K
  changes the answer path. By PLAN, stage 4's item 6 then answers the 100 aircargo questions
  anew (100 × 200–300 s ≈ 6–8 h), judged by M1 and M3, and stage 5 runs: 300 answers on the
  three external bases (≈ 17–30 h) and ≈ 330 judge requests.
- **The rerank without the model:** with the 4B resident its seconds also hold the memory's
  wait ([step 1's record](stage4-step1-record.md)), and K's share of that wait is not
  measured here. The final timing (item 7) measures the path as it ends up.
- **Twelve questions of one corpus, one stand, one day, on a Mac other projects share.**
  K = 20's two runs were apart, so the ratio's size depends on which K = 20 run it is read
  against (0.460–0.612); its sign does not.
- **A pool's count is not its set:** the K curve keeps no pool's identity, so the live pools
  match it by count only.
- The record names no corpus file and keeps no run's end.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `step3.json` | 52,460 | `efdbdedcfc607b87792a3f342653a30256edbec5c973f25522af72bab5b70e34` |
| `s3-k20-1.step3.json` | 18,143 | `e2061a05da5665f7d7fee6d513ae352a8db2b0fe01662a3d79bc4bd61b740ada` |
| `s3-k14-1.step3.json` | 18,140 | `717b82068fc99e018e2ef0de4956ff342b8e008937c0ea4c7e9aa63c0510b2cc` |
| `s3-k14-2.step3.json` | 18,130 | `836e08c145ec9bc44a3dfc801a2b66a69e5d5931e047b374653bf54fc02c7e23` |
| `s3-k20-2.step3.json` | 18,140 | `97f61a28c152aeae533836ef07243bd51033fb92f6c79671cff8c7178dad8fc4` |
| `s3-k20-1.q1.step3.json` | 9,516 | `92fc29edd3b73262aedf4cef46d62ad82d7d3b9ab078491b6f78c9b3f564fe7a` |
