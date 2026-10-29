# The K curve after expansion — each lane's first K against 20, on stage 2's saved lists — 2026-10-28

The question: how many candidates a lane can give the reranker before the gold the model reads
falls. Stage 2's saved retrieval lists of stand `5e308fe` were read again by the rules
[`k-curve-expanded.md`](../specs/k-curve-expanded.md), registered with the tool in `0b4a439`
before the count. For K = 5 … 20 the product's own fusion, rerank cut and parent expansion ran
on each lane's first K, and each K is set against K = 20 at the expanded point
([`PLAN.md`](../../PLAN.md) stage 4, step 3). No model call, no new retrieval; 10.5 s on the Mac.

Record: [`reports/k-curve/5e308fe/record.json`](../../reports/k-curve/5e308fe/record.json) and
its [rows](../../reports/k-curve/5e308fe/rows.jsonl), written by
[`reports/k-curve/tools/k_curve.py`](../../reports/k-curve/tools/k_curve.py). Checked by
[`tests/test_k_curve_artifact.py`](../../tests/test_k_curve_artifact.py):
- every number of the record is read again from the rows;
- K = 20's points and every K's point before expansion are read again from the committed
  stage-2 export;
- every table row below is built from the record.

The rows hold identifiers, flags and numbers, never the text of a question or a document.

## Provenance and method

- **Inputs:** the no-reranker point's ([record](no-rerank-point-record.md)), the same files by
  SHA-256:
  - the runs `p2-wixqa`, `p2-conditionalqa`, `p2-multihoprag` and `p2-aircargo` on stand
    `5e308fe48cca0955c3007057a574a425f71e2a6a`, 100 questions each;
  - the second generation's chunk archives;
  - the export [`reports/stage2/retrieval-20261021/`](../../reports/stage2/retrieval-20261021/manifest.json),
    manifest SHA-256 `f8dbfb9e…`.

  Measured in the Mac's gate checkout at the overlay of `97fc31e` (`4e239a84`), the
  registration's next commit, which changed status files only. The record names the tool and
  the measuring code by SHA-256.
- **Settings of the runs:** BM25 and BGE-M3, 20 a lane, RRF k = 60. The reranker keeps 5.
  Parent expansion uses window 2, 3,600 characters and chunk overlap 200.

  The fusion's key length is masked in the runs' settings as `<set>`: their snapshot hides
  every name holding «key» as secret-like, and `rrf_doc_key_chars` holds one. The length went
  unread. The fusion keys a candidate by its source and chunk index, and reaches the length only
  for a document without them; a string there would have raised. K = 20 reproduced all 400
  recorded pools.
- **The point at each K:**
  1. `HybridRetriever._rrf_merge` fuses the first K of each recorded lane.
  2. `_rerank_scored_with_status` keeps five by each candidate's recorded score, ties in the K
     pool's fused order.
  3. `_expand_parents` expands those five over the chunk archive.
- **Metrics:** stage 2's, on the questions with gold — WixQA `gold_article`; ConditionalQA and
  MultiHop-RAG `all_evidence_coverage`. The exact two-sided McNemar test sets K = 20 against K:
  **b** counts questions with gold only at 20, **c** gold only at K. A *loss* is b > c with
  p < 0.05.
- **Checks before any number, all passed:**
  - on all 400 questions K = 20 gives the recorded pool, five and scores, and on the 250 with
    gold the recorded expansion, text for text;
  - its points are the export's;
  - every K's five before expansion give the export's K curve;
  - no candidate lacks a score, and no point is unread.

## After expansion — the pair that decides

Each cell gives the questions with gold at K, then (b/c, p) against K = 20.

| K | WixQA | ConditionalQA | MultiHop-RAG | Pooled |
|---|---|---|---|---|
| 20 | 68 of 100 | 60 of 80 | 13 of 70 | 141 of 250 |
| 5 | 60 (10/2, 0.039) **loss** | 60 (6/6, 1.000) | 10 (5/2, 0.453) | 130 (21/10, 0.071) |
| 6 | 63 (7/2, 0.180) | 63 (3/6, 0.508) | 10 (5/2, 0.453) | 136 (15/10, 0.424) |
| 7 | 66 (5/3, 0.727) | 62 (3/5, 0.727) | 11 (4/2, 0.688) | 139 (12/10, 0.832) |
| 8 | 66 (6/4, 0.754) | 61 (4/5, 1.000) | 10 (4/1, 0.375) | 137 (14/10, 0.541) |
| 9 | 66 (4/2, 0.688) | 58 (4/2, 0.688) | 10 (4/1, 0.375) | 134 (12/5, 0.143) |
| 10 | 65 (4/1, 0.375) | 58 (4/2, 0.688) | 9 (4/0, 0.125) | 132 (12/3, 0.035) **loss** |
| 11 | 66 (3/1, 0.625) | 59 (3/2, 1.000) | 9 (4/0, 0.125) | 134 (10/3, 0.092) |
| 12 | 66 (3/1, 0.625) | 58 (3/1, 0.625) | 9 (4/0, 0.125) | 133 (10/2, 0.039) **loss** |
| 13 | 66 (3/1, 0.625) | 58 (3/1, 0.625) | 9 (4/0, 0.125) | 133 (10/2, 0.039) **loss** |
| 14 | 68 (1/1, 1.000) | 58 (2/0, 0.500) | 10 (3/0, 0.250) | 136 (6/1, 0.125) |
| 15 | 69 (0/1, 1.000) | 59 (1/0, 1.000) | 11 (2/0, 0.500) | 139 (3/1, 0.625) |
| 16 | 69 (0/1, 1.000) | 59 (1/0, 1.000) | 11 (2/0, 0.500) | 139 (3/1, 0.625) |
| 17 | 69 (0/1, 1.000) | 59 (1/0, 1.000) | 11 (2/0, 0.500) | 139 (3/1, 0.625) |
| 18 | 69 (0/1, 1.000) | 60 (0/0, 1.000) | 12 (1/0, 1.000) | 141 (1/1, 1.000) |
| 19 | 68 (0/0, 1.000) | 60 (0/0, 1.000) | 13 (0/0, 1.000) | 141 (0/0, 1.000) |

**The smallest K without a detected loss: 14.**

## Before expansion — beside it

| K | WixQA | ConditionalQA | MultiHop-RAG | Pooled |
|---|---|---|---|---|
| 20 | 68 of 100 | 46 of 80 | 7 of 70 | 121 of 250 |
| 5 | 60 (10/2, 0.039) **loss** | 45 (4/3, 1.000) | 5 (4/2, 0.688) | 110 (18/7, 0.043) **loss** |
| 6 | 63 (7/2, 0.180) | 47 (3/4, 1.000) | 5 (4/2, 0.688) | 115 (14/8, 0.286) |
| 7 | 66 (5/3, 0.727) | 48 (2/4, 0.688) | 5 (4/2, 0.688) | 119 (11/9, 0.824) |
| 8 | 66 (6/4, 0.754) | 49 (1/4, 0.375) | 5 (4/2, 0.688) | 120 (11/10, 1.000) |
| 9 | 66 (4/2, 0.688) | 47 (1/2, 1.000) | 5 (4/2, 0.688) | 118 (9/6, 0.607) |
| 10 | 65 (4/1, 0.375) | 47 (1/2, 1.000) | 5 (4/2, 0.688) | 117 (9/5, 0.424) |
| 11 | 66 (3/1, 0.625) | 46 (1/1, 1.000) | 5 (4/2, 0.688) | 117 (8/4, 0.388) |
| 12 | 66 (3/1, 0.625) | 45 (1/0, 1.000) | 4 (4/1, 0.375) | 115 (8/2, 0.109) |
| 13 | 66 (3/1, 0.625) | 45 (1/0, 1.000) | 4 (4/1, 0.375) | 115 (8/2, 0.109) |
| 14 | 68 (1/1, 1.000) | 46 (0/0, 1.000) | 4 (4/1, 0.375) | 118 (5/2, 0.453) |
| 15 | 69 (0/1, 1.000) | 46 (0/0, 1.000) | 6 (2/1, 1.000) | 121 (2/2, 1.000) |
| 16 | 69 (0/1, 1.000) | 46 (0/0, 1.000) | 6 (2/1, 1.000) | 121 (2/2, 1.000) |
| 17 | 69 (0/1, 1.000) | 46 (0/0, 1.000) | 5 (2/0, 0.500) | 120 (2/1, 1.000) |
| 18 | 69 (0/1, 1.000) | 46 (0/0, 1.000) | 6 (1/0, 1.000) | 121 (1/1, 1.000) |
| 19 | 68 (0/0, 1.000) | 46 (0/0, 1.000) | 7 (0/0, 1.000) | 121 (0/0, 1.000) |

## Candidates scored and the five kept

Each cell lists four bases in order: WixQA / ConditionalQA / MultiHop-RAG / aircargo.

| K | Candidates the reranker scores, median | Of the five, K = 20's (mean) |
|---|---|---|
| 5 | 10 / 9 / 9 / 9 | 2.92 / 3.18 / 2.88 / 3.20 |
| 6 | 11.5 / 11 / 11 / 10.5 | 3.28 / 3.42 / 3.10 / 3.45 |
| 7 | 13 / 13 / 12 / 12 | 3.45 / 3.65 / 3.32 / 3.62 |
| 8 | 15 / 15 / 14 / 14 | 3.71 / 3.81 / 3.53 / 3.77 |
| 9 | 17 / 16 / 16 / 16 | 3.94 / 4.01 / 3.72 / 3.91 |
| 10 | 18 / 18 / 17 / 17.5 | 4.11 / 4.19 / 3.95 / 4.12 |
| 11 | 20 / 20 / 19 / 19 | 4.22 / 4.29 / 4.08 / 4.20 |
| 12 | 22 / 22 / 20.5 / 21 | 4.39 / 4.36 / 4.20 / 4.33 |
| 13 | 24 / 23 / 22 / 23 | 4.49 / 4.41 / 4.32 / 4.42 |
| 14 | 26 / 25 / 24 / 25 | 4.58 / 4.47 / 4.47 / 4.57 |
| 15 | 27 / 27 / 26 / 26.5 | 4.68 / 4.59 / 4.56 / 4.68 |
| 16 | 29 / 29 / 27.5 / 28 | 4.75 / 4.66 / 4.65 / 4.74 |
| 17 | 30.5 / 30.5 / 29 / 30 | 4.80 / 4.75 / 4.74 / 4.81 |
| 18 | 32 / 32 / 31 / 32 | 4.86 / 4.90 / 4.84 / 4.89 |
| 19 | 34 / 34 / 32.5 / 33.5 | 4.92 / 4.96 / 4.91 / 4.95 |
| 20 | 36 / 36 / 34 / 35 | 5.00 / 5.00 / 5.00 / 5.00 |

## What it says

- **14 a lane is the smallest K the frozen reading allows.** Four comparisons read a loss:
  - WixQA at K = 5;
  - the pooled three at K = 10, 12 and 13 (p 0.035–0.039).

  From 14 up no K reads one on any base or pooled. At 14 the reranker scores a median of 24–26
  candidates instead of 34–36, about 30 % fewer.
- **No detected loss is not no loss.** At K = 14 the pooled gold after expansion is 136 of 250
  against 141 (b 6, c 1, p 0.125): five questions behind, 2 points, too few for 250 questions
  to show. Only K = 18 and 19 equal K = 20 there.
- **The pooled losses in the middle come from three small one-way lags.** At K = 10–13 WixQA
  trails by 2–3, ConditionalQA by 1–2 and MultiHop-RAG by 4. No base alone reads a loss, the
  three together do. The curve is not monotone: pooled K = 7 is 139 and K = 10 is 132.
- **At K = 5 the expansion changes the reading, not the gap.** Pooled K = 5 trails K = 20 by
  11 questions both before and after expansion:

  | | Gold at K = 5 against 20 | b | c | p | Reading |
  |---|---|---|---|---|---|
  | before expansion | 110 against 121 | 18 | 7 | 0.043 | loss |
  | after expansion | 130 against 141 | 21 | 10 | 0.071 | none |

  The expansion adds discordant questions on both sides (ConditionalQA's 4/3 become 6/6), so
  the same gap no longer reaches p < 0.05. WixQA's expansion joins only the seeds' own article,
  so its two curves are one.
- **The forecast's answer was wrong.** Written before the count from the published means, it
  gave 6.
  - **Right base by base:** WixQA loses at K = 5 (60 against 68); ConditionalQA and
    MultiHop-RAG read no detected difference at any K.
  - **Wrong pooled:** there is no loss at K = 5, where the expansion adds discordant questions,
    and there are losses at 10, 12 and 13, where lags too small for any one base add up.

## What follows

The step's live timing measures K = 14 against 20 on the Mac (≈ 1.5 h, after step 0): the
reranker's seconds with about 30 % fewer candidates. Read 2026-10-28:
[its record](stage4-step3-record.md). «В путь рычаг входит по своим числам;
настройки прода и рантайм реранкера — её словом (§8.3)». If K changes, step 6 answers the 100
aircargo questions again, judged by M1 and M3. The other lever on the same reranker, INT8 in
ONNX Runtime (step 5a), is read against these lists the same way.

Limits:
- gold in the retrieved documents, not answer quality;
- the vector lane's first K stand in for a search of K;
- one stand and one set of 100 questions a base;
- MultiHop-RAG's pairs are small;
- the prompt's fitting after expansion is not simulated.
