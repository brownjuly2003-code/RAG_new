# P1b — the frozen P1 cut under production expansion: pre-registration and plan

Status 2026-09-24: **measured — NO_SHIP**. [Capsule](../evidence/p1b-expanded-cut.md);
report `reports/p1b/p1b-expanded-cut.json` at `c5f1d31`, built once in a clean Mac
clone at the evaluator commit `d1adbbb`. This plan fixed the arms, the rulers and
the verdict on 2026-09-24, before any expanded-context metric existed for H or Hm.
Git shows the plan at `05f6799`, the evaluator at `d1adbbb` and the report built
afterwards. P1b is an offline evaluator; no product behaviour changed.

## Question

P1 ([plan](../../archive/docs/specs/p1-adaptive-k-plan.md), [capsule](../evidence/p1-adaptive-k.md)) measured its
cuts on the phase-C harness, which slices cached chunks and skips the parent-window
expansion that production applies to every selected chunk. Under that expansion, does
the frozen P1 rule `rel_0.2` beat the expanded top-5 control on H: context precision at
or above the 0.63 gate, with coverage and every individual fact kept?

`NO_SHIP` is the expected outcome. On a pool whose unexpanded top-5 row equals H's
control (0.5067 / 0.905 / 87-7-6), Q1 measured expanded top-5 at 0.5768 and expanded
top-3 at 0.6179 ([results](../../archive/docs/operations/2026-07-18-q1-context-precision-ab-results.md));
`rel_0.2` keeps 4.49 chunks on average, so its expanded precision is expected between
the two. The slice closes adaptive-k against production and leaves a fail-closed
expanded evaluator, since every later candidate has to be judged against expanded
production.

## Inputs

- **H:** `evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz`, pool `91ce1745…`, 100
  agent-authored cases, `agent_labelled`, 0 approved.
- **Hm:** `evaluation/gr3-32de532-bucket-Hm-candidates.json.gz`, pool `3a302079…`, 15
  multi-document cases, checked separately.
- **Scores:** P1's `evaluation/p1-511f3f9-H-rerank-scores.json` and
  `evaluation/p1-511f3f9-Hm-rerank-scores.json`, admitted by P1's own parity and
  model-pin checks. P1b runs no model.
- **P1 report:** `reports/p1/p1-adaptive-k.json`, pinned by
  `tests/test_p1_adaptive_k_artifact.py`. It supplies the per-case cross-validation
  cells and the aggregates that the unexpanded selections must reproduce.
- **Corpus:** `data/uploads/aircargo`, outside git. The build takes the corpus directory
  as an argument and refuses it unless it matches
  `evaluation/aircargo_corpus.manifest.json` file by file (201 files, `corpus_sha256`
  `c8562a64…`).
- **Chunks:** rebuilt from that corpus the way `ParentExpander` in
  `scripts/ab_context_precision.py` rebuilds them: structural chunking on and semantic
  chunking off, as `ParentExpander` sets them (structural takes precedence in
  `select_chunks` either way), and contextual headers on, the `config/settings.py`
  default. Each chunk then gets `metadata["chunk_index"]` in ingestion order, as
  `vectordb/manager.py` stamps it at ingestion, so the retriever keys every chunk by
  source and index, as production does. `ParentExpander` omits that stamp, so Q1's
  harness keyed chunks by text.
- **Disclosed pre-checks (2026-09-24, no metric computed):** in the Mac gate checkout at
  the tree of `1e45af4`, the corpus copies match the manifest and give 5589 chunks with
  5589 distinct texts, so on this corpus text keys and index keys pick out the same
  chunks. Every H candidate (3427 of 3427, 100 of 100 cases) and every Hm candidate
  (572 of 572, 15 of 15) equals the text of exactly one chunk from the same source
  file. No precision, recall or keyword status was computed.

## Rules (fixed 2026-09-24, before any expanded-context metric was computed)

Every arm starts from the fresh top-5 of the P1 scores, and rank 1 is always kept. No
arm is chosen, tuned or added on the expanded results.

| Arm | Kept before expansion | Role |
|---|---|---|
| `top_k_5+exp` | the fresh top-5 | control: production as served |
| `rel_0.2+exp` | ranks with probability ≥ 0.2 · p1 | primary: the frozen P1 rule |
| `p1_cv+exp` | each case's P1 cross-validation cell | held-out check, H only |
| `top_k_3+exp` | the fresh top-3 | diagnostic; never enters the verdict |

- **Frozen cells:** `rel_0.2` is the P1 report's `h.in_sample_best.cell`. `p1_cv+exp`
  takes each H case's cell from `h.cross_validation.per_case`: `rel_0.2` in folds 0, 1,
  2 and 4, `rel_0.7` in fold 3.
- **Expansion:** production's own `HybridRetriever._expand_parents`
  (`vectordb/_base_manager.py`) at the `config/settings.py` defaults, window 2 and 3600
  characters, over the index-stamped chunks; the build stops if two chunks share a
  retriever key. It runs once per case on the arm's kept set, in fresh rank order, so a
  neighbour that one kept chunk already took is not added to another. A cut can
  therefore change how its kept chunks expand, and an expanded cut is never read off the
  expanded top-5.
- **Parity, fail-closed:** the build stops, and writes no report, if any fresh top-5
  candidate of any H or Hm case does not equal the text of exactly one rebuilt chunk
  from the same source file. The raw-text fallback of `ParentExpander.expand`, which
  passes an unmatched text on unexpanded, is never used.
- **Ruler (primary):** P1's ruler path, `score_cases_by_class` with the dataset's
  questions and keywords: the official `evaluation/ragas_eval.py` context precision and
  recall and the keyword status, over the expanded texts in rank order, with no
  combined cap. Production's `_format_context_block` (`agent/prompts.py`) joins every
  selected document uncapped, and Q1 measured the same way. Aggregates and gates use
  exact sums of the per-case four-decimal values.
- **Ruler (diagnostic):** the same after P1's combined 6000-character cap. It shows how
  the phase-C harness would read expanded contexts and never enters the verdict.
- **Reproduction check:** the evaluator first rescores the unexpanded `top_k_5`,
  `rel_0.2` and cross-validation selections on H, and `top_k_5` and `rel_0.2` on Hm,
  with P1's ruler and cap. Every field of each aggregate must equal the P1 report's.
- **Headline:** `rel_0.2+exp` against `top_k_5+exp` on the 100 H cases: paired precision
  and recall deltas with a paired case bootstrap (10000 resamples, seed 20260923,
  percentile 95 %, linear quantiles, as in P1); FULL/PART/MISS transitions; named fact
  losses (keywords the control matched and the arm does not) and FULL regressions.
- **Verdict:** `INVALID_CONTROL` if a reproduction check fails. Otherwise
  `SHIP_CANDIDATE` iff all five conditions hold, and `NO_SHIP` if any fails:
  1. `rel_0.2+exp` precision on H ≥ 0.63;
  2. its recall, FULL and MISS on H no worse than `top_k_5+exp`, and no named fact loss;
  3. it meets the review floor on H: recall ≥ 0.92, FULL ≥ 88, MISS ≤ 4
     ([review](../../archive/docs/specs/precision-improvement-review.md));
  4. `p1_cv+exp` meets 1–3 too, so the result does not rest on `rel_0.2` having been
     chosen on these cases;
  5. on Hm, `rel_0.2+exp` recall, FULL and MISS no worse than Hm's `top_k_5+exp`, and no
     named fact loss. This holds by construction: in the P1 report `rel_0.2` keeps all
     five candidates on every Hm case, so both arms send the same contexts. It guards
     the inputs and adds no evidence.

  Scope: an H-relative exploratory verdict on agent-authored cases, not shipment
  approval. A `SHIP_CANDIDATE` would still need P2's blinded relevance judgment, a
  fresh-query confirmation and the owner's decision before any default changes.
- **Also reported:** per arm, the aggregate, mean kept before expansion, the number of
  kept chunks that expansion grew, mean context characters per case, and the paired
  bootstrap against the control (2000 resamples; the headline 10000); the
  diagnostic-ruler aggregates; the Hm arms. Also whether `top_k_5+exp` and
  `top_k_3+exp` equal Q1's rows: reported, not required, since Q1's pool file and
  corpus carry no pinned SHA. Q1 averaged unrounded per-case values and printed recall
  to three decimals, so equal means precision within 0.0001, recall within 0.001 and
  the same FULL/PART/MISS. Q1's rows are quoted as historical comparators and not
  re-run: expanded top-5 0.5768 / 0.980 / 97-2-1, top-3 0.6179 / 0.960 / 94-4-2, top-3
  with `grade_docs` 0.6478 / 0.945 / 92-5-3.

## Integrity record

- Known when these rules were written: every P1 number, all unexpanded; Q1's expanded
  rows on its own pool; the pre-checks above. No expanded-context precision, recall or
  keyword status existed for H or Hm.
- Condition 5 is known to hold: P1's report shows `rel_0.2` keeping all five
  candidates on every Hm case, so on Hm `rel_0.2+exp` equals `top_k_5+exp`. P1b
  therefore tests no cut on the multi-document bucket; a rule that cuts there needs its
  own Hm check.
- `rel_0.2` was chosen in P1 on all 100 H cases under the unexpanded ruler, so on H it is
  in-sample for the choice of rule and its number is optimistic. `p1_cv+exp` uses cells
  chosen without each case's own labels. Neither replaces a fresh-query confirmation.
- The bootstrap is conditional on this case set, and cases that share a source are not
  independent: a CI above zero is no proof that the population score clears 0.63.
- A new arm, threshold, window or character cap needs a new pre-registration.
- Executor: Codex GPT-6-Sol on the `cw` profile, the owner-authorized stand-in while
  GLM 5.3 is at weekly quota `1310` (reset 2026-09-28 05:56 UTC+8).
- The report was built once in a clean Mac clone at `d1adbbb`, after the
  evaluator and its 32 synthetic tests were committed there. Before that, no
  expanded-context precision, recall or keyword status existed for H or Hm.
  The evaluator did not change afterwards: the report's code digests equal
  the blobs at `d1adbbb`; the artifact test checks them and, when the corpus
  directory and `langchain_core` are present, rebuilds the whole report from
  the corpus.

## Next

1. **Done:** evaluator `scripts/p1b_expanded_cut.py` and its 32 synthetic tests at
   `d1adbbb`.
2. **Done:** report `reports/p1b/p1b-expanded-cut.json` at `c5f1d31`,
   [capsule](../evidence/p1b-expanded-cut.md), **NO_SHIP**.
3. P2, the blinded relevance judgment ([P1 plan](../../archive/docs/specs/p1-adaptive-k-plan.md) § Next item 3);
   the judge is Julia's data-governance call.
