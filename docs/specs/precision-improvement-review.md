# Precision improvement — Astra and Fable review

Decision recorded 2026-09-12 after the owner's request for independent
**Astra xhigh** and **Claude Fable xhigh** opinions, then documentation and
continued implementation. Fable CLI resolved to `claude-fable-5-1`.
This document records advice and the accepted experiment order, not new evidence.

## Fixed baseline and target

GR-1b measures precision **0.5475**, recall **0.9200**, FULL/PART/MISS
**88/8/4**, over 100 agent-written questions with 0 approved labels.
The old C pool measured 0.5067 / 0.9050 / 87/7/6. Different pools prevent
attributing that difference to the graph. See the
[GR-1b capsule](../evidence/gr1b-structure-graph.md) for input and provenance.

Keep the existing metric and **0.63** target. A candidate must preserve
recall >=0.92, FULL >=88 and MISS <=4, with individual fact losses and
FULL regressions reported even when aggregate counts compensate for them.
These conditions are necessary, not sufficient for changing the default.

## What both reviewers agreed on

`evaluation/ragas_eval.py::context_precision` measures per-document substring
coverage of the union of question words (length >=3) and expected keywords,
averaged with weight 1/rank. It is neither judged relevance nor the fraction
of relevant documents. Recall checks expected-keyword coverage in joined text.
FULL therefore does not prove that the answer is semantically sufficient.

Shortening the list, merging chunks, repeating question words and ordering
documents can raise the score without improving support quality. Substring
matches and Russian morphology add measurement error. Keep this ruler for
historical comparisons, and add independent relevance/sufficiency review.
Never feed expected keywords, answers or case labels to a production selector.

Both reviewers identified these concrete investigation points:

- `_apply_graph_coherence` removes ranks 4 and 5 when the five documents map
  to different sections: their relative strengths are 0.25 and 0.20 and the
  cutoff is <=0.25. That yields top-3. Whether this explains the observed
  88 three-context outputs is a hypothesis until measured on the same pool.
- Multi-document sections are promoted ahead of singletons irrespective of
  the reranker preference. A relevant singleton can lose rank or disappear.
- `_expand_graph_sections` adds neighbours without query relevance scoring.
  It can consume the 6000-character budget, prepend text before the retrieved
  evidence and skip a neighbour that does not fit while adding a farther one.
- Category prefilter matches are 0/100. The producer compares case
  categories/tags to graph categories by exact case-insensitive equality.
  Investigate taxonomy and metadata; do not fix it with evaluation-only labels
  that the real request cannot supply.
- Semantic reranker ordering and this lexical metric can disagree. That is a
  diagnostic question, not proof that the reranker is wrong.

## Astra's emphasis

First compare G1 with plain top-1 through top-5 from its own archived
`reranked_cands`, and include a pre-rerank control. Report paired differences,
coverage transitions, context count and character budget use.

Next, use an oracle only as diagnosis: enumerate the 31 nonempty subsets of
the original top-5 in preserved order and check attainable precision while
preserving G1 keyword hits. Expansion may have supplied facts absent from all
those subsets. Any bound applies only to the searched candidates and rules.

Then consider a query-only selector, evidence-preserving expansion, and soft
category routing. The archive lacks numeric reranker scores and replaces the
original candidate metadata with postprocessed metadata. Score-gap calibration
and exact structural ablations need additional recoverable inputs.

If the planned entity lane changes only the single multi-hop question and
leaves 99 single-hop cases unchanged, even a perfect multi-hop precision gives
at most +0.005673, approximately **0.5532** overall. GR-2 cannot alone close
this dataset's 0.63 gate under that routing contract. Evaluate it separately
on the prepared 15-question multi-hop/aggregation bucket.

## Fable's emphasis and qualifications

Fable prioritised stage decomposition plus diagnostic attainable scores and
rank/category error profiles before spending more Mac time. It also proposed
BM25/reranker fusion, category routing and controlled section expansion.
Potentially absent expected keywords need source inspection, not automatic
relabelling: absence from a candidate pool does not prove a bad label.

Some suggestions are deliberately not adopted as established facts:

- No assumed bootstrap width of +/-0.03; compute uncertainty from paired data.
- No 70%-of-gain rule or rank-relevance 0.3 cutoff without justification.
- No weakened acceptance at recall 0.90 / FULL 87; retain current GR-1b coverage.
- A best score over top-10 subsets is not a global ceiling for the entire pool.
  Ordering optima also depend on character truncation and subset constraints.
- The cause of GR-1b's gain, and a harmful effect of entity expansion on
  single-hop, remain hypotheses, not measured conclusions.

## Accepted execution order

1. **Same-pool controls now:** G1 versus original reranked top-1...5 and
   pre-rerank top-5. Use identical identities, metric and character cap;
   retain case-level changes and deterministic paired bootstrap intervals.
2. **Diagnostic attainable scores:** bounded oracle search and missing-fact
   localisation. Keep oracle outputs separate from deployable recommendations.
3. **Choose the diagnosed stage:** query-only ordering/selection, preservation
   of singleton evidence, or bounded expansion. Restore required metadata first.
4. **Category experiment:** align taxonomy and infer categories from the query;
   try soft routing before hard filtering. Filtering an old pool cannot stand
   in for a new category-restricted ANN retrieval with candidate replenishment.
5. **Confirmation:** tune on development data, evaluate once on held-out data,
   independently inspect relevance and answer sufficiency. These 100 cases
   have already been inspected repeatedly and are not a fresh holdout.

Bootstrap over paired cases estimates exploratory uncertainty conditional on
this case set; shared-source cases require cluster-aware confirmation. A CI
for improvement is not proof that the population score exceeds 0.63. Generator
seeds over fixed contexts do not provide independent retrieval measurements.

Steps 1 and 2 are measured: [controls](../evidence/gr1b-same-pool-controls.md)
fail joint gates; the [bounded oracle](../evidence/gr1b-safe-subset-oracle.md)
reaches 0.6780 / 0.9250 with labels and G1 fallback, without keyword losses.
The [query-only control](../evidence/gr1b-query-control.md) is also measured:
0.6268 / 0.7250, 22 FULL regressions; it fails acceptance. The three infeasible
cases have G1 hits absent from uncapped top-five. Next: recover source metadata
for evidence-preserving expansion. Neither experiment establishes deployable quality.

This work reuses the exact gzip archive, without embeddings, model calls
or deployment. Windows runs focused checks only; models, full suites and
containers belong on the Mac. GR-4/GR-2/GR-3 remain planned after this diagnosis.
