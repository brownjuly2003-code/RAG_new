# GR-1b — bounded safe-subset oracle

Measured 2026-09-12; diagnostic only, **not deployable**. This completes the
bounded subset step of the [Astra/Fable review](../specs/precision-improvement-review.md).
The [ordinary top-k controls](gr1b-same-pool-controls.md) failed joint coverage
and precision acceptance. Label-informed selection has room to improve them:

| scope | cases | precision | recall | FULL/PART/MISS |
|---|---:|---:|---:|---|
| G1 | 100 | 0.5475 | 0.9200 | 88/8/4 |
| Feasible subsets only | 97 | 0.6890 | 0.9278 | 87/6/4 |
| Oracle with G1 fallback | 100 | 0.6780 | 0.9250 | 89/7/4 |

There are 88 strictly improved selections and 12 G1 fallbacks. No original
FULL case regresses; no previously matched keyword is lost. The paired
precision delta is 0.130473, bootstrap CI95 [0.112445, 0.149158]; recall delta
0.005000, CI95 [0.000000, 0.015000]. These are exploratory case-bootstrap
intervals (2000 draws, seed 42), not held-out confirmation.

## Search contract

Enumerate 31 nonempty subsets of the original reranked top-five, retain their
original order, apply the 6000-character cap, then score with the existing
keyword-based metrics. Preserve both raw and recall-normalised keyword
identities found in capped G1. Maximise four-decimal precision, breaking ties
by fewer retained contexts then candidate indices. Keep G1 unless a feasible
subset strictly improves precision. Labels are used in both selection and
fallback: neither is a production algorithm.

No feasible subset exists for `aircargo-dangerous-goods-clearance`,
`aircargo-waybill-first-mile-fields`, or `aircargo-cross-border-required-fields`.
Their G1 evidence cannot be preserved by these top-five subsets under this
cap. This alone does not isolate expansion from truncation effects.
The 97-case score is conditional on feasibility, not a whole-dataset ceiling.
The 100-case result is also bounded to this search and fallback; it is not a
global optimum over retrieval, orderings or expansion.

## Provenance and reproduction

[JSON report](../../reports/gr/gr1b-oracle.json): source `715193c`, clean tree
at measurement, corpus/dataset/sidecar/archive hashes and full configuration.
Input is the committed [G1 archive](../../evaluation/gr1b-4436d61-candidates.json.gz);
original producer attribution retains the [GR-1b limits](gr1b-structure-graph.md).
The 100 questions remain agent-written, unapproved and repeatedly inspected.
Keyword preservation is not independently judged semantic sufficiency.

```powershell
python scripts/ab_context_precision.py --structural-oracle
python -m pytest tests/test_gr1b_controls.py tests/test_docs_hygiene.py -q -p no:schemathesis --basetemp=.tmp/pytest-gr1b-oracle-published
```

The reproduction test compares every case, aggregate, interval and input
provenance. No models, network or new embeddings are required.

## Next work

Implement an offline query-only selection control with no expected-keyword
access. Evaluate it against G1, including individual fact losses; do not tune
to the oracle choices. Investigate the three infeasible cases before removing
expansion. A deployable improvement still needs held-out and independent
semantic confirmation; current runtime G1 remains NO-SHIP at precision 0.63.
