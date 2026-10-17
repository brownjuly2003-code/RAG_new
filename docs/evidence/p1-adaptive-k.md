# P1 — adaptive-k cut of the reranked top five

Measured 2026-09-24 in a clean clone at
`4999ea3a5665155648858ce226ff18d5b27ab0c5`, using fresh
`BAAI/bge-reranker-v2-m3` scores captured at
`511f3f90d9bef29d8f1b393b94ba12324eef9937`. The
[plan](../../archive/docs/specs/p1-adaptive-k-plan.md) records the grid, the ruler, the
cross-validated selection rule and the verdict thresholds as
pre-registered on 2026-09-23, before any score was seen. The report's
`config.preregistered` records the grid, the CV rule and the verdict as fixed
on 2026-09-23, before any score was seen. Git shows the plan was committed
together with the score artifacts in `a67f517`, and the report was built
afterwards at `4999ea3`, once the tests were committed. This is `measured`
evidence over `agent_labelled` cases.

**NO_SHIP.** The cross-validated cut gains precision but loses facts.
No tested cut reaches the 0.63 precision gate without losing FULL cases.

## Measurements

The rows cover 100 H cases with fresh reranked top five candidates; rank 1
is always kept and each context has a 6000-character cap. The table and its
bullets are the report's own `render_table` output verbatim; their fact-loss
and FULL-regression counts are the lengths of named lists in the report.

### H grid (fresh top-5, n = 100)

| cell | role | precision | recall | FULL/PART/MISS | mean kept | precision delta CI95 | fact-loss cases | FULL regressions |
|---|---|---:|---:|---|---:|---|---:|---:|
| top_k_1 | fixed_k | 0.6403 | 0.7200 | 65/14/21 | 1.00 | [0.1079, 0.1586] | 24 | 22 |
| top_k_2 | fixed_k | 0.5784 | 0.8400 | 79/10/11 | 2.00 | [0.0604, 0.0832] | 9 | 8 |
| top_k_3 | fixed_k | 0.5432 | 0.8850 | 84/9/7 | 3.00 | [0.0303, 0.0427] | 4 | 3 |
| top_k_4 | fixed_k | 0.5214 | 0.9050 | 87/7/6 | 4.00 | [0.0121, 0.0174] | 0 | 0 |
| top_k_5 | control | 0.5067 | 0.9050 | 87/7/6 | 5.00 | [0.0000, 0.0000] | 0 | 0 |
| abs_0 | primary | 0.5067 | 0.9050 | 87/7/6 | 5.00 | [0.0000, 0.0000] | 0 | 0 |
| abs_0.01 | primary | 0.5069 | 0.9050 | 87/7/6 | 4.99 | [0.0000, 0.0007] | 0 | 0 |
| abs_0.05 | primary | 0.5127 | 0.9050 | 87/7/6 | 4.79 | [0.0022, 0.0106] | 0 | 0 |
| abs_0.1 | primary | 0.5218 | 0.9050 | 87/7/6 | 4.64 | [0.0063, 0.0258] | 0 | 0 |
| abs_0.2 | primary | 0.5286 | 0.8950 | 86/7/7 | 4.46 | [0.0113, 0.0342] | 1 | 1 |
| abs_0.3 | primary | 0.5345 | 0.8950 | 86/7/7 | 4.31 | [0.0152, 0.0424] | 1 | 1 |
| abs_0.5 | primary | 0.5587 | 0.8800 | 85/6/9 | 3.85 | [0.0342, 0.0713] | 3 | 2 |
| abs_0.7 | primary | 0.5702 | 0.8800 | 85/6/9 | 3.53 | [0.0439, 0.0842] | 3 | 2 |
| abs_0.9 | primary | 0.6048 | 0.8600 | 83/6/11 | 2.71 | [0.0732, 0.1232] | 5 | 4 |
| rel_0 | primary | 0.5067 | 0.9050 | 87/7/6 | 5.00 | [0.0000, 0.0000] | 0 | 0 |
| rel_0.1 | primary | 0.5208 | 0.9050 | 87/7/6 | 4.68 | [0.0055, 0.0248] | 0 | 0 |
| rel_0.2 | primary | 0.5278 | 0.9050 | 87/7/6 | 4.49 | [0.0109, 0.0329] | 0 | 0 |
| rel_0.3 | primary | 0.5333 | 0.8950 | 86/7/7 | 4.34 | [0.0146, 0.0409] | 1 | 1 |
| rel_0.5 | primary | 0.5591 | 0.8950 | 86/7/7 | 3.91 | [0.0346, 0.0707] | 1 | 1 |
| rel_0.7 | primary | 0.5697 | 0.8900 | 86/6/8 | 3.59 | [0.0436, 0.0836] | 2 | 1 |
| rel_0.9 | primary | 0.6043 | 0.8700 | 84/6/10 | 2.89 | [0.0737, 0.1220] | 4 | 3 |
| gap_prob_inf | primary | 0.5067 | 0.9050 | 87/7/6 | 5.00 | [0.0000, 0.0000] | 0 | 0 |
| gap_prob_0.5 | primary | 0.5408 | 0.8950 | 86/7/7 | 4.47 | [0.0175, 0.0530] | 1 | 1 |
| gap_prob_0.4 | primary | 0.5481 | 0.8950 | 86/7/7 | 4.21 | [0.0235, 0.0603] | 1 | 1 |
| gap_prob_0.3 | primary | 0.5569 | 0.8950 | 86/7/7 | 4.01 | [0.0321, 0.0691] | 1 | 1 |
| gap_prob_0.2 | primary | 0.5671 | 0.8950 | 86/7/7 | 3.70 | [0.0414, 0.0797] | 1 | 1 |
| gap_prob_0.1 | primary | 0.5790 | 0.8800 | 85/6/9 | 3.28 | [0.0531, 0.0936] | 3 | 2 |
| gap_prob_0.05 | primary | 0.5864 | 0.8800 | 85/6/9 | 3.03 | [0.0605, 0.1005] | 3 | 2 |
| gap_prob_0 | primary | 0.6057 | 0.8350 | 79/9/12 | 1.96 | [0.0785, 0.1203] | 9 | 8 |
| gap_logit_inf | secondary | 0.5067 | 0.9050 | 87/7/6 | 5.00 | [0.0000, 0.0000] | 0 | 0 |
| gap_logit_6 | secondary | 0.5480 | 0.9050 | 87/7/6 | 4.48 | [0.0215, 0.0636] | 0 | 0 |
| gap_logit_4 | secondary | 0.5861 | 0.8950 | 86/7/7 | 3.79 | [0.0544, 0.1050] | 1 | 1 |
| gap_logit_3 | secondary | 0.5992 | 0.8950 | 86/7/7 | 3.52 | [0.0669, 0.1202] | 1 | 1 |
| gap_logit_2 | secondary | 0.6119 | 0.8850 | 85/7/8 | 3.10 | [0.0795, 0.1319] | 2 | 2 |
| gap_logit_1 | secondary | 0.6293 | 0.8650 | 82/9/9 | 2.22 | [0.0979, 0.1477] | 5 | 5 |
| gap_logit_0.5 | secondary | 0.6368 | 0.8350 | 79/9/12 | 1.78 | [0.1062, 0.1547] | 9 | 8 |
| gap_logit_0 | secondary | 0.6406 | 0.8200 | 77/10/13 | 1.48 | [0.1094, 0.1580] | 11 | 10 |

- CV held-out (cells per fold: rel_0.2, rel_0.2, rel_0.2, rel_0.7, rel_0.2): precision 0.5372, recall 0.8900, 86/6/8, mean kept 4.30; precision delta +0.0306 CI95 [0.0167, 0.0468]; fact-loss cases 2; FULL regressions 1
- Held-out fact losses: `aircargo-customs-special-cargo-manual-check` (fold 3, `rel_0.7`, PART->MISS): `dangerous goods`; `aircargo-employment-contract-special-form` (fold 3, `rel_0.7`, FULL->MISS): `срочный трудовой договор`, `удаленным работником`
- In-sample best (rel_0.2, optimistic): precision 0.5278, recall 0.9050, 87/7/6, mean kept 4.49
- Oracle best prefix (labels; not deployable): precision 0.6505, recall 0.9050, 87/7/6, mean kept 1.53
- Hm transfer (rel_0.2) vs Hm control: precision 0.2527, recall 0.5000, 4/7/4, mean kept 5.00 vs precision 0.2527, recall 0.5000, 4/7/4, mean kept 5.00; fact-loss cases 0; FULL regressions 0
- Hm transfer fact losses: none
**Decision: NO_SHIP** (precision gate not met; H-relative constraints not met; review floor not met)

## What the numbers say

- In the 5-fold grouped cross-validation, each cell was chosen on training
  cases and applied only to its held-out fold. Held-out precision is 0.5372
  against the control's 0.5067, a paired delta of +0.0306 with CI95
  [0.0167, 0.0468]. Recall falls to 0.8900 from 0.9050; FULL/PART/MISS
  changes from 87/7/6 to 86/6/8. The held-out gain therefore fails the
  H-relative coverage constraints despite a positive precision interval.
- The folds select `rel_0.2` except fold 3 (folds are numbered from 0),
  which selects `rel_0.7`.
  Both held-out fact losses occur in that fold:
  `aircargo-customs-special-cargo-manual-check` loses `dangerous goods`
  and changes from PART to MISS;
  `aircargo-employment-contract-special-form` loses
  `срочный трудовой договор` and `удаленным работником` and changes
  from FULL to MISS. These case-level losses explain the aggregate
  recall, FULL and MISS regressions.
- The in-sample best `rel_0.2` has precision 0.5278, recall 0.9050,
  FULL/PART/MISS 87/7/6, and mean kept 4.49. It was selected on all
  100 cases, so that estimate is optimistic. Plain `top_k_4` reaches
  0.5214 at the same 0.9050 recall and 87/7/6 coverage; this pool
  gives little evidence of a distinctive gain from the threshold rule.
- Every cell meeting the 0.63 gate has FULL regressions:
  `top_k_1` reaches 0.6403 with 22 FULL regressions, `gap_logit_0.5`
  0.6368 with 8, and `gap_logit_0` 0.6406 with 10. A higher precision
  score from a shorter context
  therefore cannot be treated as a coverage-preserving ship decision.
- The label-using best-prefix oracle reaches precision 0.6505 while
  keeping recall 0.9050 and FULL/PART/MISS 87/7/6. It chooses a prefix
  using the expected keywords and is not deployable. Its result is a
  ceiling for any prefix cut of these five candidates that keeps every
  fact, not the result of a
  label-free selector; the selected `rel_0.2` remains at 0.5278
  in-sample.
- On the Hm transfer, the H choice `rel_0.2` keeps all five candidates
  on every one of the 15 Hm cases. It exactly matches the Hm control:
  precision 0.2527, recall 0.5000, FULL/PART/MISS 4/7/4 and mean kept
  5.00. No multi-document fact loss or gain is measured here.
- The review floor asks for recall 0.9200, 88 FULL and at most 4 MISS.
  The control already has 0.9050, 87 FULL and 6 MISS. As the verdict's
  scope states, no cut of the control's top five can reach that floor.

## Scope and limits

The report's verdict is an "H-relative exploratory verdict on the phase-C
harness, without parent-window expansion"; it is not shipment approval.
Production expansion is not measured in this report and belongs to P1b.
The H and Hm cases are `agent_labelled` and have 0 approvals; keyword
coverage does not establish human relevance or answer sufficiency.

The headline interval uses 10000 paired case resamples; each grid cell
uses 2000, with seed 20260923. The reported percentile intervals describe
this exploratory run. They are not held-out confirmation of a family of
comparisons, and the training-selected in-sample cell has an optimistic
estimate. The fold choices make the headline held-out within this dataset,
while shared source and repeated inspection still limit generalization.

No runtime default changes here. Even a `SHIP_CANDIDATE` verdict would
leave production adoption to the owner; this report's decision is
`NO_SHIP`.

## Provenance

- [JSON report](../../reports/p1/p1-adaptive-k.json), SHA-256
  `30e55459e1787c134215597d5672293ec4b32ef051c8bc96e8d289dfa50cb65d`;
  code commit `4999ea3a5665155648858ce226ff18d5b27ab0c5` with
  `tree_clean` true. The artifact test verifies the recorded source digests
  against that commit's git blobs.
- Score-capture commit `511f3f90d9bef29d8f1b393b94ba12324eef9937`;
  H score SHA-256
  `3ced6d0259fdee8da1d4cbf7dcb1cea55fed7e4379003d23f327a25e331bb50b`;
  Hm score SHA-256
  `6789200b8a112d076ef7e7999cf8c261747131cab609dbd334abfc51dc06c03d`.
  Both captures report complete ranking parity with their archives.
- H pool SHA-256
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
  Hm pool SHA-256
  `3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee`.
- Reranker `BAAI/bge-reranker-v2-m3`, model commit
  `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; corpus manifest
  SHA-256
  `2b2e9232e69b4f52a55237f3ee620f34c91d1900383877c2310ba616c6590444`.

## Reproduction

```powershell
python -m scripts.p1_adaptive_k --h-scores evaluation/p1-511f3f9-H-rerank-scores.json --hm-scores evaluation/p1-511f3f9-Hm-rerank-scores.json
python -m pytest tests/test_p1_adaptive_k_artifact.py -q -p no:cacheprovider
```

In a clean clone at `4999ea3a5665155648858ce226ff18d5b27ab0c5`, the report
command reproduces the JSON byte for byte; a dirty tree records `tree_clean`
false. The artifact test rebuilds the whole report from committed inputs
without models or network.
