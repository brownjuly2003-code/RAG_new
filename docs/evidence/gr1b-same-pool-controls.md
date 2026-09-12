# GR-1b — same-pool top-k controls

Measured 2026-09-12 following the
[Astra/Fable review](../specs/precision-improvement-review.md).
**NO-SHIP:** none of the ordinary top-k controls reaches precision 0.63 while
preserving current G1 recall 0.9200 and FULL/PART/MISS 88/8/4.

## Measurements

All controls use the same archived G1 cases and original reranker ordering.
The cap is 6000 characters after top-k selection, identical to G1. The
pre-rerank control uses the original stored candidate order, not BM25-only.
Intervals are paired differences **control minus G1**, not absolute-score CIs.

| arm | precision | recall | FULL/PART/MISS | precision delta CI95 | FULL losses | fact-loss cases |
|---|---:|---:|---|---|---:|---:|
| g1 | 0.5475 | 0.9200 | 88/8/4 | [0.000000, 0.000000] | 0 | 0 |
| reranked_top_1 | 0.6403 | 0.7200 | 65/14/21 | [0.070586, 0.114663] | 23 | 26 |
| reranked_top_2 | 0.5784 | 0.8400 | 79/10/11 | [0.021322, 0.040283] | 9 | 10 |
| reranked_top_3 | 0.5432 | 0.8850 | 84/9/7 | [-0.010530, 0.002383] | 4 | 5 |
| reranked_top_4 | 0.5214 | 0.9050 | 87/7/6 | [-0.033022, -0.018962] | 2 | 3 |
| reranked_top_5 | 0.5067 | 0.9050 | 87/7/6 | [-0.048316, -0.033230] | 2 | 3 |
| prerank_top_5 | 0.4989 | 0.8350 | 79/8/13 | [-0.063934, -0.032131] | 13 | 14 |

`FULL losses` counts original G1 FULL cases that cease to be FULL.
`fact-loss cases` counts cases losing any recall-normalised expected keyword,
even if another keyword is gained and the recall fraction is unchanged.
The report includes every case, matched-keyword set, retained character count,
class aggregate, status-transition count and both precision and recall CIs.

## Interpretation

- Top-1 clears the precision threshold but loses 23 original FULL cases and
  lowers recall to 0.7200. It fails the coverage gate.
- G1 versus ordinary top-3 has a small precision difference whose paired CI
  includes zero. G1 nevertheless retains more facts: recall 0.9200 versus
  0.8850, with five cases losing keyword evidence in the top-3 control.
- Consequently, G1 is not interchangeable with simple top-3 on coverage.
  This experiment does not separate coherence from section expansion; their
  individual contribution remains unmeasured.
- Ordinary top-5 reproduces the old baseline aggregate. Equal aggregates
  alone do not establish byte-identical candidates or per-case equivalence.
- The next diagnostic is a bounded, oracle-only search over subsets of the
  original top-5, preserving the keyword facts present in G1. It tests whether
  safe selection within those candidates has enough room to reach the target.

## Provenance and limits

The [JSON report](../../reports/gr/gr1b-controls.json) pins dataset, sidecar,
corpus, archive and decompressed-pool SHA-256 plus source file digests.
Source commit: `9994cbb`; pending publication/test work makes tree_clean false.
Input: [exact G1 gzip archive](../../evaluation/gr1b-4436d61-candidates.json.gz).
The original Mac producer attribution remains subject to the
[GR-1b provenance limits](gr1b-structure-graph.md).

Bootstrap uses 2000 resamples of 100 paired cases, seed 42, with linear
percentile bounds. It is deterministic, exploratory, conditional on this
repeatedly inspected dataset, and does not model shared-source dependence.
These intervals are not held-out confirmation or simultaneous intervals for
the entire set of comparisons. No width was assumed in advance.

Labels remain agent_labelled and unapproved. Keyword coverage does not establish
human relevance or semantic answer sufficiency. This changes no runtime default,
does not train a selector and makes no model-improvement claim.

## Reproduction

```powershell
python scripts/ab_context_precision.py --structural-controls
python -m pytest tests/test_gr1b_controls.py -q -p no:schemathesis --basetemp=.tmp/pytest-gr1b-controls
```

No models, network, embeddings, Docker or WSL. The test reproduces all cases,
intervals and the published table from the archived bytes.
