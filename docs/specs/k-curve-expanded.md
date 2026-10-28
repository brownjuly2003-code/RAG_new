# The K curve after expansion: how many candidates a lane gives the reranker, on stage 2's lists

Status 2026-10-28: **registered before the count**, with the tool that reads it and its test
([Records](#records)), in `0b4a439`; read the same day — **the smallest K without a detected
loss is 14**, the forecast 6 ([record](../evidence/k-curve-record.md)). [`PLAN.md`](../../PLAN.md)
stage 4, step 3: «Качество для K от 5 до 20 считается без Mac по оценкам этапа 2, на четырёх
корпусах», and since the [no-reranker point](no-rerank-point.md) «кривая K здесь и INT8
(п. 5а), каждый по эталону после расширения на тех же списках». No model call, no new
retrieval; the live timing comes after.

## Why

The reranker stays: without it the gold after expansion falls from 141 to 121 of 250 (exact
McNemar p = 0.004, [record](../evidence/no-rerank-point-record.md)). Its seconds — a median of
21.3–32.9 s a question by base, the same record — grow with the candidates it scores: two lanes
of 20 fuse into a median of 34–36, their first 10 into 17–18, their first 5 into 9–10 (the
committed export's pools, read 2026-10-28). Stage 2's K curve ([stage 2](stage2-four-corpora.md),
«The K curve») ends before the expansion — on WixQA 0.60 at K = 5, 0.68 at 20 — and the model
reads the expansion, which on ConditionalQA brings back the gold the rerank drops (46 → 60 of 80;
both in the [analysis](../operations/research-2026-10-25/analysis.md)).

## Inputs

The no-reranker point's ([Inputs](no-rerank-point.md#inputs)): the runs `p2-wixqa`,
`p2-conditionalqa`, `p2-multihoprag` and `p2-aircargo` of stand `5e308fe`, their records and
chunk archives on the Mac, and the committed export `reports/stage2/retrieval-20261021/` by its
manifest's SHA-256. Of a record: `lanes` (source and `chunk_index` by rank, as the fusion got
them), `pool` (fused order, whole scores), `ranked` (the five kept, their scores) and
`expanded`. Of the run's `effective_settings.json`: 20 a lane, RRF k = 60, five kept, window 2,
3,600 characters, overlap 200, and the fusion's key length (`rrf_doc_key_chars`). Records and
archives are kept only on the Mac, so the tool runs there, as the no-reranker point's did in 15 s.

## The point at each K

For K = 5, 6, … 20 and every question, the product's own code on the recorded lists:

1. **Lanes:** the first K of each. BM25's are what a search of K returns (one sort, one cut);
   the vector lane's stand in for one ([What it does not say](#what-it-does-not-say)).
2. **Pool:** `HybridRetriever._rrf_merge` over the two at the run's k and key length, in its own
   fused order; the vector lane alone if BM25's is empty, as the code does. A record without
   `lanes` is that case, its pool the vector lane, as stage 2 reads it (the export has none).
3. **Five:** `HybridRetriever._rerank_scored_with_status` with a stand-in cross-encoder that
   returns each candidate's recorded whole score: one stable sort, score descending, ties in the
   K pool's fused order, cut at five. Every candidate at K is in the pool at 20, so its score is
   recorded; a score missing or not finite stops the tool, and nothing is written.
4. **Expansion:** the no-reranker point's `Expansion` — the product's
   `HybridRetriever._expand_parents` over the chunk archive at the run's window, budget and
   overlap — on the five in their order, which decides the seed a shared neighbour joins.
5. **Metrics:** stage 2's, by `scripts/external_pilot.read_gold` (`Places.members` for an
   expansion), on the questions with gold — 100 WixQA, 80 ConditionalQA, 70 MultiHop-RAG: WixQA
   `gold_article` (primary) and `gold_articles`; the other two `all_evidence_coverage` (primary)
   and `evidence_recall`. The prompt fitting (`sent`) is not simulated. aircargo has no gold
   documents — its labels hold answer terms — so it gets no reading, only what stands beside.

On the committed pools no tie falls at the cut at any K, and the two tie rules — the K pool's
here, the 20-pool's in stage 2's curve — give the same five in the same order at every K; scores
tie inside the five at 11 (question, K) of WixQA's (read 2026-10-28, without the gold).

## Checks before any number

Each stops the tool, and nothing is written.

1. **The runs:** the no-reranker point's checks (complete runs of `5e308fe`, five kept,
   expansion on, the archive its index receipt and the export name), and 20 a lane.
2. **K = 20 is the recorded path** on every question of the four bases: the recorded pool in
   order, the recorded five in order with their scores, and, with gold, the recorded expansion,
   text for text (the no-reranker point allowed five misses here and had none).
3. **The recount:** K = 20's points before and after expansion are the export's `points.ranked`
   and `points.expanded` (the no-reranker point's `recount`).
4. **The curve before expansion is stage 2's:** every K's five give the export's `k_curve`
   entry for that K, and its `k20_is_ranked` holds.

A point that cannot be read — a chunk of some K's expansion without a place in its document —
leaves the question out of every K, counted; more than five on a base make its comparison
`NOT_EVIDENCE`.

## How it is read — frozen before the count

For each K from 5 to 19, K against 20 at the expanded point, per base and pooled over the three,
on the primary metric: the questions read, the hits of each side, the discordant pairs — **b**,
gold at 20 only; **c**, gold at K only — and the exact two-sided McNemar p (binomial on b + c at
½, the no-reranker point's `mcnemar`); per base, the second metric's mean on each side.

- **loss** — b > c and p < 0.05: K candidates a lane lose gold that 20 keep;
- **gain** — c > b and p < 0.05;
- **no detected difference** — otherwise, with b and c given.

The expanded pair decides, because the model reads the expansion; the pair before it, the
candidates scored (median and range) and how many of the five are K = 20's stand beside.

**The smallest K without a detected loss** is the smallest K from which no K up to 19 reads
*loss*, on any base or pooled: a loss on one base vetoes its K (gold lost on one base is lost all
the same, as in the no-reranker point), a *gain* vetoes nothing. If K = 19 reads a loss it is 20,
the path of now; a base whose comparison is `NOT_EVIDENCE` makes it `NOT_EVIDENCE`. It is read
from the top because the curve is not monotone (stage 2's on WixQA: 0.66 at K = 9, 0.65 at 10).
It is the K the step's live timing measures.

No correction for the fifteen comparisons: it would only guard against a false *loss*, and a
false loss only raises K toward 20. *No detected loss* is not *no loss*: the test detects about
2.8·√(d/n) ([stage 2](stage2-four-corpora.md)) — 9 points on a base of 100 when a tenth of its
questions disagree, about 6 pooled over 250; D9's non-inferiority margin was withdrawn for want
of ≈ 1,960 pairs ([`PLAN.md`](../../PLAN.md)).

## What it does not say

- Which K enters the path: that needs its seconds, from the live timing (≈ 1.5 h), and «В путь
  рычаг входит по своим числам; настройки прода и рантайм реранкера — её словом (§8.3)»
  (stage 4). If K changes, step 6 answers the 100 aircargo questions again, judged by M1 and M3.
- Answer quality: gold after expansion is what the model can read, not what it answers.
- A search of K: the vector lane's first K approximate it, its HNSW search going deeper for a
  larger K (stage 2's spec); a K pool is scored in other batches than the 20-pool, where padding
  can move a score's last digits and a near-tie at the cut fall the other way.
- More than one stand and one run a base; MultiHop-RAG's pairs are small (gold in K = 20's five
  for 7 of its 70 questions, after expansion for 13).

**Forecast, written before the count** (from the published means, no question read): WixQA's
expansion joins only chunks of the seed's own source and its gold is an article, so its hits
after expansion are its curve before — 60 of 100 at K = 5, 63 at 6, 65–66 from 7 to 13, 68–69
from 14 (the export). From K = 6 they trail K = 20's 68 by at most 5, and a loss needs the sides
six apart (five apart, all one way, give p = 0.0625); at K = 5, eight behind, WixQA reads a loss.
ConditionalQA and MultiHop-RAG read no detected difference at any K. Pooled, K = 5 reads a loss
and no larger K does. **The smallest K without a detected loss: 6.**

## Records

- [`reports/k-curve/tools/k_curve.py`](../../reports/k-curve/tools/k_curve.py), run on the Mac in
  the gate checkout, writes `record.json` — the inputs, the tool and the measuring code by
  SHA-256, the settings, per base and pooled each K's pairs and what stands beside, the decision
  — and `rows.jsonl`, a question a line: id, base, index, stratum, the K whose expanded point
  could not be read, K = 20's points, per K the candidates, the five shared with K = 20 and the
  points before and after expansion. Ids, flags and numbers, never a text:
  `stage2_common.without_text` refuses a record that would hold one.
- `tests/test_k_curve_tool.py`: the selection through the product's code on a synthetic archive,
  the checks and the reading on hand-made rows. The record goes to `reports/k-curve/5e308fe/`
  with its artifact test, a capsule in `docs/evidence/` and a row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md).
