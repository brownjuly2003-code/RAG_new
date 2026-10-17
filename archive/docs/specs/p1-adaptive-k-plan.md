# P1 — label-free adaptive-k on fresh reranker scores: pre-registration and plan

Status 2026-09-24: **measured — NO_SHIP**. [Capsule](../../../docs/evidence/p1-adaptive-k.md);
report `reports/p1/p1-adaptive-k.json` published at `2edf19a`, built once in a clean
Mac clone at `4999ea3`. This plan records the grid, ruler, CV selection rule and
verdict thresholds as fixed on 2026-09-23, before any score was seen. Git shows
the plan committed together with the score artifacts in `a67f517`, and the report
built afterwards at `4999ea3`; the rules are visibly older than the result.
The verdict is H-relative exploratory on 100 agent-authored `agent_labelled` cases
(0 approved) in the phase-C harness without parent-window expansion. P1 is an
offline evaluator; no product behaviour changed.

## Question

Can a label-free cut of the reranked top-5 (always keeping rank 1) raise context
precision on the phase-C H pool to the 0.63 gate without losing coverage against the
same pool's top-5 control? The label-using best-prefix oracle on the same pool is
0.6505 (exploratory, see below), so a NO_SHIP is the expected outcome; the slice exists
to measure how much of that headroom a deployable rule captures.

## Inputs

- **H:** `evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz`, pool `91ce1745…`,
  100 agent-authored cases, `agent_labelled`, 0 approved. Control `top_k_5`
  reproduces the published baseline 0.5067 / 0.905 / 87-7-6
  ([GR-0.3](../../../docs/evidence/gr0-bucket-baseline.md)).
- **Hm:** `evaluation/gr3-32de532-bucket-Hm-candidates.json.gz`, pool `3a302079…`,
  15 multi-document cases (transfer check only).
- **Scores:** `scripts/rerank_score_capture.py` at `511f3f9` re-scored every case's
  full pre-rerank list with `BAAI/bge-reranker-v2-m3` on `deproject-mac` (raw logits and
  float32 sigmoid probabilities, device `mps`, model commit `953dc6f6…`). Precondition:
  the fresh order reproduces the archived order — observed 100/100 (H) and 15/15 (Hm),
  full order and top-k. Artifacts: `evaluation/p1-511f3f9-H-rerank-scores.json`,
  `evaluation/p1-511f3f9-Hm-rerank-scores.json`.

## Rules (fixed 2026-09-23, before any score was seen)

Cuts act on the fresh top-5; rank 1 is always kept.

| Family | Grid | Rule |
|---|---|---|
| `top_k` | 1, 2, 3, 4, 5 | keep exactly k; `top_k_5` is the control |
| `abs` (primary) | 0, .01, .05, .1, .2, .3, .5, .7, .9 | keep ranks with probability ≥ τ |
| `rel` (primary) | 0, .1, .2, .3, .5, .7, .9 | keep ranks with probability ≥ ρ · p1 |
| `gap_prob` (primary) | ∞, .5, .4, .3, .2, .1, .05, 0 | cut after the first largest adjacent gap when it is > 0 and ≥ g; ∞ never cuts |
| `gap_logit` (secondary) | ∞, 6, 4, 3, 2, 1, .5, 0 | the same on raw logits; reported, never selected |

- **Ruler:** the official `evaluation/ragas_eval.py` context precision / recall and
  keyword status, 6000-character context cap, through `score_cases_by_class`.
- **Headline:** 5-fold CV grouped by the dataset's tag tuple (groups by descending size,
  then name, each to the fold with the fewest cases). Per fold, among the 24 primary
  cells, pick the maximum exact train precision (sum of per-case four-decimal values)
  subject to train recall (exact sum), FULL and MISS no worse than `top_k_5` on the same
  cases; ties go to more kept documents, then grid order. The chosen cell is applied to
  the held-out fold; the headline aggregates the 100 held-out rows.
- **Verdict:** `INVALID_CONTROL` if the control does not reproduce the published
  numbers; `SHIP_CANDIDATE` iff held-out precision ≥ 0.63 (exact sum) and held-out
  recall / FULL / MISS no worse than the control; otherwise `NO_SHIP`. Scope: an
  H-relative exploratory verdict — not shipment approval. The review floor (recall
  ≥ 0.92, FULL ≥ 88, MISS ≤ 4, [review](precision-improvement-review.md)) is reported but
  unreachable by construction: a cut of the control's top five cannot add keywords.
- **Also reported:** every cell's aggregate and paired case bootstrap against the
  control (2000 resamples; headline 10000; seed 20260923); named fact losses and FULL
  regressions; the in-sample best cell (optimistic); the label-using best-prefix oracle
  (not deployable); the in-sample best cell's transfer to Hm.

## Integrity record

- Disclosed pre-check (2026-09-23, archive-order pseudo-scores, so only fixed-k cells
  are exact): control reproduces the baseline; top-4 0.5214 at 87-7-6; oracle 0.6505.
- Every code change after the rules were fixed was decided before any real-score
  number existed. Review 1 (Claude Opus subagent, 2026-09-23) led to exact integer sums
  instead of rounded means in selection and verdict, a stable-tie-order check, an oracle
  that may not worsen keyword status, a FULL-regressions column, label paths in
  provenance and a complete `CODE_PATHS`. Review 2 (Codex GPT-6-Sol, 2026-09-24) led to
  enforced parity and model pin (`check_parity`), a fail-closed `INVALID_CONTROL`
  decision, named fact losses (`fact_losses`), the rules stated in the report and a
  review-floor success-path test. `gap_prob` at g = 0 keeps the pre-registered
  "> 0 and ≥ g" reading: a zero gap (ties) never cuts.
- Executors: GLM 5.3 direct (requests 006–014c, 009a) until its weekly quota ran out
  (`1310`, reset 2026-09-28 05:56 UTC+8); then Codex GPT-6-Sol on the owner's go-ahead.
- The report was built once in a clean Mac clone at `4999ea3`, after the X2 tests
  were committed there. Up to that commit, this plan's status recorded the real
  score artifacts as not measured. The evaluator code did not change afterwards;
  the report's code digests equal the blobs at `4999ea3`, as the artifact test checks.

## Exploratory diagnostics (Codex GPT-6-Sol, 2026-09-24; not evidence)

Recomputed from the H archive with the official ruler; no committed report backs them.

- Mean coverage at ranks 1–5: 0.6403 / 0.4545 / 0.3848 / 0.3618 / 0.3528. The weak tail
  dominates: ranks 2–5 pull 0.6403 down to 0.5067; the best reordering of the same five
  reaches only 0.5251; the best single top-5 chunk averages 0.6828 (whole pool 0.6962).
- Best fact-preserving prefix (labels): 0.6505 at 1.53 chunks.
- The ruler is mostly question echo: of 0.5067, question-only terms give 0.3931,
  keyword-only terms 0.1077, shared 0.0059. Merging chunks by source reads 0.6251,
  stripping contextual headers 0.4575, a Snowball-stemmed ruler 0.6114 — measurement-unit
  effects, not relevance gains.
- **The phase-C harness is not the production path.** Production expands each selected
  chunk by a parent window (`config/settings.py`: on, window 2, 3600 characters);
  `scripts/generator_benchmark.py` only slices cached chunks. The Q1 run
  ([results](../operations/2026-07-18-q1-context-precision-ab-results.md), its own pool)
  measured expanded top-5 at 0.5768 / 0.980 / 97-2-1. A P1 result is therefore H-relative
  and cannot justify a default change by itself.

## Next

1. **P1 done** — [report](../../../reports/p1/p1-adaptive-k.json) at `2edf19a`,
   [capsule](../../../docs/evidence/p1-adaptive-k.md), **NO_SHIP**.
2. **P1b done** — frozen `rel_0.2` over production expansion, **NO_SHIP**;
   [capsule](../../../docs/evidence/p1b-expanded-cut.md) at `c5f1d31`, [plan](../../../docs/specs/p1b-expanded-cut-plan.md).
3. **P2** — an independent, blinded per-document relevance/sufficiency judgment beside
   the frozen official ruler: question and source text only, keywords and arm hidden,
   randomized order, a stratified human-adjudicated sample, agreement reported, Hm
   separate. The judge (local Qwen on the Mac vs an external API such as GLM) is a
   data-governance decision for the owner.
4. Later candidates, ranked by the consultation: document-first retrieval for routed
   single-hop questions; section-level small-to-big; evidence-span reranking; Russian
   lexical fusion in BM25; alternative rerankers one at a time on the 8 GB Mac (a model
   swap: on the ROADMAP stop-list, so only by the owner's decision).
