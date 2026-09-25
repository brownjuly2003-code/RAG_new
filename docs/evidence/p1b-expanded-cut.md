# P1b — the frozen P1 cut under production expansion

Measured 2026-09-24 in a clean clone at `d1adbbb727d788ce14b4c4dc8676a0bd20b36f86`,
over P1's fresh `BAAI/bge-reranker-v2-m3` scores captured at
`511f3f90d9bef29d8f1b393b94ba12324eef9937`. Every arm's kept chunks went through
production's own `HybridRetriever._expand_parents` at window 2 and 3600 characters.
The input was 5589 index-stamped chunks rebuilt from a manifest-checked corpus of
201 files. The arms, rulers and verdict were pre-registered on 2026-09-24 in the
[plan](../specs/p1b-expanded-cut-plan.md), before any expanded-context metric existed.
This is `measured` evidence over `agent_labelled` cases.

**NO_SHIP.** Under expansion, `rel_0.2+exp` gains precision over the expanded top five,
but stays below the 0.63 gate and loses one fact. The held-out `p1_cv+exp` fails too.

## Measurements

The rows cover 100 H and 15 Hm cases. They start from the fresh reranked top five,
always keep rank 1, and apply the uncapped primary ruler; deltas compare each arm with
its pool's expanded control. The table and verdict lines are the report's own
`render_table` output verbatim.

| pool | arm | precision | recall | FULL/PART/MISS | mean kept | mean context chars | precision delta | CI95 |
|---|---|---:|---:|---|---:|---:|---:|---|
| H | top_k_5+exp | 0.5768 | 0.9800 | 97/2/1 | 5.00 | 11161.26 | — | — |
| H | rel_0.2+exp | 0.5975 | 0.9700 | 96/2/2 | 4.49 | 10080.15 | +0.0207 | [0.0104, 0.0327] |
| H | p1_cv+exp | 0.6062 | 0.9550 | 94/3/3 | 4.30 | 9553.09 | +0.0294 | [0.0154, 0.0452] |
| H | top_k_3+exp | 0.6179 | 0.9600 | 94/4/2 | 3.00 | 6854.61 | +0.0410 | [0.0345, 0.0475] |
| Hm | top_k_5+exp | 0.3263 | 0.7333 | 7/8/0 | 5.00 | 13614.87 | — | — |
| Hm | rel_0.2+exp | 0.3263 | 0.7333 | 7/8/0 | 5.00 | 13614.87 | +0.0000 | [0.0000, 0.0000] |
| Hm | top_k_3+exp | 0.3339 | 0.5667 | 4/9/2 | 3.00 | 8349.40 | +0.0076 | [-0.0016, 0.0165] |

- Reproduces P1: True
- precision_gate_met: False
- review_floor_met: True
- coverage_and_facts_met: False
- held_out_check_met: False
- hm_check_met: True
**Decision: NO_SHIP**

## What the numbers say

- **The control is right.** Every unexpanded selection reproduces the P1 report.
  The expanded control equals Q1's expanded top-five row: precision 0.5768, recall
  0.9800 and FULL/PART/MISS 97/2/1. The diagnostic `top_k_3+exp` equals Q1's top-three
  row: 0.6179, 0.9600 and 94/4/2. This agreement holds across a different harness,
  key scheme and pool file. Equality is reported, not required by the verdict.
- **The headline.** `rel_0.2+exp` is compared with `top_k_5+exp` on H. Its
  precision 0.5975 against 0.5768 gives a paired delta of +0.0207 with CI95
  [0.0104, 0.0327]. Recall is 0.9700 against 0.9800, and FULL/PART/MISS is
  96/2/2 against 97/2/1. One FULL→MISS transition is
  `aircargo-customs-broker-escalation`: it keeps one chunk and loses
  `customs hold` and `sanctions hit`. The precision gate and coverage-and-facts
  condition fail; the review floor holds.
- **The held-out check.** `p1_cv+exp` reaches precision 0.6062, with a paired delta
  of +0.0294 and CI95 [0.0154, 0.0452], recall 0.9550 and FULL/PART/MISS 94/3/3.
  It loses facts on three cases: `aircargo-customs-special-cargo-manual-check`
  loses `ручную проверку`; `aircargo-employment-contract-special-form` loses
  `срочный трудовой договор` and `удаленным работником`; and
  `aircargo-customs-broker-escalation` loses `customs hold` and `sanctions hit`.
- **The diagnostic top three.** Plain truncation to three reaches 0.6179 with
  three fact losses. It is below 0.63 and never enters the verdict. No measured arm
  reaches the gate. Q1's top-three `grade_docs` row at 0.6478 is a historical
  comparator using an LLM grader; it was not re-run.
- **The diagnostic ruler.** Under the 6000-character cap, the control reads
  0.5795 / 0.9250 and `rel_0.2+exp` reads 0.5949 / 0.9250, both at 89/7/4.
  That phase-C reading hides the coverage cost. The primary ruler is uncapped,
  as production sends every selected document.
- **Size.** The cut sends fewer characters, with mean context 10080.15 against
  11161.26, and grows fewer chunks: 438 against 484.
- **Hm.** `rel_0.2+exp` keeps all five candidates on every Hm case, so its row
  equals the control by construction. The Hm condition holds but adds no evidence
  of a cut. On Hm, `top_k_3+exp` loses recall: 0.5667 against 0.7333.

## Scope and limits

The verdict's scope is an H-relative exploratory verdict on agent-authored cases;
it changes no default. A `SHIP_CANDIDATE` still needs P2's blinded relevance
judgment, a fresh-query confirmation and the owner's decision. The H and Hm cases
are `agent_labelled`, with 0 approvals; keyword coverage does not establish human
relevance or answer sufficiency.

The `rel_0.2` rule was chosen in P1 on these 100 H cases, so its estimate is
optimistic. The `p1_cv+exp` cells were chosen without each case's labels. The
headline bootstrap uses 10000 paired case resamples; other arms use 2000, with
seed 20260923. All intervals are conditional on this case set, and cases sharing
a source are not independent. Q1's expanded rows are quoted, not re-run. No
runtime default changes here; production adoption remains the owner's decision.

## Provenance

- [JSON report](../../reports/p1b/p1b-expanded-cut.json), SHA-256
  `6f48bb1957f67235792edb926cf44c4894b56439c9fd423feb6529a7a791bc8b`.
  Code commit `d1adbbb727d788ce14b4c4dc8676a0bd20b36f86` had `tree_clean` true;
  the artifact test checks its recorded file digests against those git blobs.
- P1 report SHA-256
  `30e55459e1787c134215597d5672293ec4b32ef051c8bc96e8d289dfa50cb65d`.
  Score-capture commit `511f3f90d9bef29d8f1b393b94ba12324eef9937`;
  H score SHA-256
  `3ced6d0259fdee8da1d4cbf7dcb1cea55fed7e4379003d23f327a25e331bb50b`;
  Hm score SHA-256
  `6789200b8a112d076ef7e7999cf8c261747131cab609dbd334abfc51dc06c03d`.
- H pool SHA-256
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
  Hm pool SHA-256
  `3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee`.
  Reranker `BAAI/bge-reranker-v2-m3`, model commit
  `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
- Corpus manifest SHA-256
  `2b2e9232e69b4f52a55237f3ee620f34c91d1900383877c2310ba616c6590444`;
  `corpus_sha256`
  `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`.
  The admitted corpus has `201` files and `5589` chunks. Chunking uses size `800`,
  overlap `200`, contextual headers on, structural chunking on and semantic
  chunking off.

## Reproduction

```
python -m scripts.p1b_expanded_cut --corpus <aircargo corpus dir>
python -m pytest tests/test_p1b_expanded_cut_artifact.py -q -p no:cacheprovider
```

The report command refuses a corpus differing from the manifest. The artifact
test checks all pins anywhere; it rebuilds the whole report and compares it
with the published JSON when the corpus directory (`P1B_CORPUS_DIR`, or the
sibling `RAG_Support_Assistant` checkout) and `langchain_core` are present.
