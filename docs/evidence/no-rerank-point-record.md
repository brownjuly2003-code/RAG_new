# The no-reranker point — the fused five against the reranker's, on stage 2's saved lists — 2026-10-26

Whether the CPU reranker earns its seconds and memory: stage 2's saved retrieval lists of stand
`5e308fe` read again by the rules [`no-rerank-point.md`](../specs/no-rerank-point.md), registered
with the tool in `f7492d5` before the count — the reranker's five against the first five of the
fused order, which the product keeps when no reranker is configured, both before and after the
product's own parent expansion ([`PLAN.md`](../../PLAN.md) stage 4, step 3; §8.3, item 14). No
model call, no new retrieval; 15 s on the Mac.

Record: [`reports/no-rerank/5e308fe/record.json`](../../reports/no-rerank/5e308fe/record.json)
and its [rows](../../reports/no-rerank/5e308fe/rows.jsonl), written by
[`reports/no-rerank/tools/no_rerank_point.py`](../../reports/no-rerank/tools/no_rerank_point.py).
Checked by [`tests/test_no_rerank_point_artifact.py`](../../tests/test_no_rerank_point_artifact.py):
every number of the record is read again from the rows; each question's recorded points, the
reranker's seconds and how many of the five the two orders share are read again from the
committed stage-2 export; every table row below is built from the record. The rows hold
identifiers, flags and numbers, never the text of a question or a document.

## Provenance and method

- **Inputs:** stage 2's retrieval runs `p2-wixqa`, `p2-conditionalqa`, `p2-multihoprag` and
  `p2-aircargo` on stand `5e308fe48cca0955c3007057a574a425f71e2a6a` (the retrieval V4's answers
  had), 100 questions each, all complete; the second generation's chunk archives, each by the
  SHA-256 its index receipt names; the committed export
  [`reports/stage2/retrieval-20261021/`](../../reports/stage2/retrieval-20261021/manifest.json),
  manifest SHA-256 `f8dbfb9e…`. Measured in the Mac's gate checkout at the overlay of `f7492d5`
  (`69e6066a`); the record names the tool and the measuring code by SHA-256.
- **Settings of the runs:** BM25 and BGE-M3, 20 each, RRF k = 60; the reranker keeps 5; parent
  expansion window 2, 3,600 characters, chunk overlap 200.
- **Points:** ranked — the reranker's five, as recorded; fused — the pool's first five in its
  recorded fused order; after expansion — the recorded expansion of the ranked five against the
  product's `HybridRetriever._expand_parents` run on the fused five over the chunk archive.
- **Metrics:** stage 2's — WixQA `gold_article`, ConditionalQA and MultiHop-RAG
  `all_evidence_coverage` (primary; the second metric beside it), questions with gold only.
  The exact two-sided McNemar test on the discordant questions: **b** — gold only with the
  reranker, **c** — gold only without it; *loss* when b > c and p < 0.05.
- **Checks before any number, all passed:** the recount equals the committed export's points
  on all 250 questions; the product's expansion of the ranked five gives the recorded texts,
  in order, on all 250 (none left out); no pool shorter than five; no point unread.

## Before expansion

| Base | Questions | Gold with the reranker | Gold with the fused five | Only with the reranker (b) | Only without (c) | p | Reading | Second metric, with → without |
|---|---|---|---|---|---|---|---|---|
| WixQA | 100 | 68 | 60 | 15 | 7 | 0.134 | no detected difference | 0.632 → 0.558 |
| ConditionalQA | 80 | 46 | 36 | 10 | 0 | 0.002 | loss | 0.733 → 0.633 |
| MultiHop-RAG | 70 | 7 | 4 | 5 | 2 | 0.453 | no detected difference | 0.460 → 0.356 |
| Pooled | 250 | 121 | 100 | 30 | 9 | 0.001 | loss | — |

## After expansion — the pair that decides

| Base | Questions | Gold with the reranker | Gold with the fused five | Only with the reranker (b) | Only without (c) | p | Reading | Second metric, with → without |
|---|---|---|---|---|---|---|---|---|
| WixQA | 100 | 68 | 60 | 15 | 7 | 0.134 | no detected difference | 0.632 → 0.558 |
| ConditionalQA | 80 | 60 | 53 | 10 | 3 | 0.092 | no detected difference | 0.834 → 0.768 |
| MultiHop-RAG | 70 | 13 | 8 | 7 | 2 | 0.180 | no detected difference | 0.526 → 0.430 |
| Pooled | 250 | 141 | 121 | 32 | 12 | 0.004 | loss | — |

**Decision: the reranker earns its place.**

## Beside it

| Base | Of the five, shared by the two orders (mean) | Questions sharing all five | Sharing none | Reranker seconds, median (p90) |
|---|---|---|---|---|
| WixQA | 2.13 | 1 | 9 | 21.3 (27.1) |
| ConditionalQA | 2.64 | 4 | 2 | 29.7 (41.3) |
| MultiHop-RAG | 2.29 | 3 | 10 | 32.9 (38.6) |
| aircargo | 2.47 | 1 | 2 | 26.8 (36.7) |

## What it says

- **Without the reranker, what the model reads holds less gold on every base:** WixQA 68 → 60
  questions, ConditionalQA 60 → 53, MultiHop-RAG 13 → 8. No base alone reaches p < 0.05 after
  expansion; the three together do (141 → 121 of 250, b 32 against c 12, p 0.004). By the frozen
  reading the reranker stays in the path; removing it would save its 21–33 s of a question
  (median of these runs; 102 s in the chat under memory pressure) and ≈ 2.27 GB at a net
  loss of the gold article in 8 of WixQA's 100 questions.
- **It is not a reshuffle of the same five:** the two orders share 2.1–2.6 of the five on
  average, all five in 1–4 questions of 100.
- **Both orders lose gold the pool holds.** On WixQA the reranker keeps 15 questions' gold the
  fused five lose (b) and loses 7 the fused five keep (c); of the 84 questions whose gold is
  among the candidates, 68 keep it with the reranker. The reranker's own misses remain a lever.
- **The forecast,** written before the count: on WixQA before expansion a *loss* — wrong in the
  reading (68 against 60, p 0.134), right in direction; on ConditionalQA after expansion no
  detected difference — right (the expansion turns its *loss* of 46 against 36 into 60 against
  53).

## What follows

§8.3, item 14: the reranker is not removed. Its seconds are to be won on the same reranker —
INT8 in ONNX Runtime (stage 4, step 5a) and fewer candidates (stage 4, step 3, the K curve) —
each measured against these lists by gold at the expanded point. Item 14's other half, a test of
another reranker on the saved lists, had the condition «только если реранк окажется важен»; it
holds now, and a new model in the product stays Julia's word (§9).

Limits: gold in the retrieved documents, not answer quality; one stand, one set of 100 questions
a base; MultiHop-RAG's pairs are small (its gold is in the pool for 22 of 70); the prompt's
fitting after expansion is not simulated.
