# The no-reranker point: the fused order's first five against the reranker's, on stage 2's lists

Status 2026-10-26: **registered before the count**, with the tool that reads it and its test
([Records](#records)), in `f7492d5`; read the same day — **the reranker earns its place**
([record](../evidence/no-rerank-point-record.md)). [`PLAN.md`](../../PLAN.md) stage 4, step 3: «по тем же сохранённым
спискам, без модели, — точка «без реранка»» (the amendment of 2026-10-26); §8.3, item 14; the
[research analysis](../operations/research-2026-10-25/analysis.md), item 6b (i). No model
call, no new retrieval; Julia's «да» of 2026-10-26 took it as a free check.

## Why

The CPU reranker (`BAAI/bge-reranker-v2-m3`) scores about 33 fused candidates a question and
keeps five: 27–102 s of an answer and ≈ 2.27 GB beside the 4B on an 8-GB Mac. Stage 2's export
shows that it also drops gold the pool holds — on WixQA 16 of the 84 questions whose gold
article is among the candidates. Without it the code keeps the fused order's first five
(`HybridRetriever.get_relevant_documents_with_path`: `merged_before_rerank[: self._rerank_k]`)
and expands them as now. Whether those five hold more gold or less is the largest speed and
memory question of the plan, and the saved lists answer it without a model.

## Inputs

Stage 2's retrieval runs on stand `5e308fe` — the retrieval V4's answers had — on the Mac:
`/Users/julia/RAG_new_chat_5e308fe/chatlive/runs/<label>/retrieval/NNN-<case>.json`, written by
`reports/stage2/tools/live_retrieval.py`, for the labels `p2-wixqa`, `p2-conditionalqa` and
`p2-multihoprag`; each record holds the pool in its fused order, the five kept and their
expansion. The corpora: the second generation, `/Users/julia/RAG_new_external_s1/<base>/`
(chunk archive, documents, the registration of the gold). The committed export of the same runs,
`reports/stage2/retrieval-20261021/`, is named by its manifest's SHA-256.

aircargo has no gold documents — its labels hold answer terms — so it gets no reading here: its
run's records (`p2-aircargo`) give only how many of the five the two orders share.

## The points

For every question with gold:

- **ranked** — the reranker's five, as recorded;
- **fused** — the pool's first five in its recorded fused order (RRF, k = 60);
- **expanded, ranked** — the recorded expansion of the ranked five;
- **expanded, fused** — the product's `HybridRetriever._expand_parents` run on the fused five
  over the base's chunk archive, with the run's window, character budget and chunk overlap
  (`effective_settings.json`); each chunk's `chunk_index` is its archive position, as the index
  stamps it.

The metrics are stage 2's, read by `scripts/external_pilot.read_gold` (and
`Places.members` for an expansion): WixQA — `gold_article` (primary) and `gold_articles`;
ConditionalQA and MultiHop-RAG — `all_evidence_coverage` (primary) and `evidence_recall`. The
prompt fitting after expansion (`sent`) is not simulated.

## Checks before any number

1. **The recount.** `ranked` and `expanded, ranked` read again from the records must equal the
   committed export's `points.ranked` and `points.expanded` for every question; a difference
   stops the tool.
2. **The expansion is the product's.** `_expand_parents` on the ranked five must give exactly
   the recorded expansion texts, in order. A question where it does not is counted and left
   out of the expanded comparison; more than five such questions on a base make that base's
   expanded comparison `NOT_EVIDENCE`.
3. **The pool's order.** The recorded pool's first five are the fused order the code keeps
   when no reranker is configured; a pool shorter than five is counted and left out.
4. **A point that cannot be read** — a chunk of the fused five or of its expansion without a
   place in its document — leaves the question out of that pair, counted.

## How it is read — frozen before the count

Per base, and pooled over the three, for each pair (ranked against fused; expanded against
expanded) on the primary metric: the questions read at both, the hits of each side, the
discordant pairs — **b**, gold only with the reranker; **c**, gold only without it — and the
exact two-sided McNemar p (binomial on b + c at ½); the mean of the second metric on each side.

- **loss** — b > c and p < 0.05: the reranker keeps gold the fused order loses;
- **gain** — c > b and p < 0.05;
- **no detected difference** — otherwise, with b and c given.

The expanded pair decides, because both paths expand before the model reads. **The fused five
keep the gold** if no base reads *loss* there and the pooled pair is not *loss*; otherwise the
reranker earns its place on these bases. A base whose expanded pair is `NOT_EVIDENCE` (check 2)
makes the decision `NOT_EVIDENCE`. Either way the reranker's own seconds on the same runs (the
records' `walls.rerank`, median per base) and how many of the five the two orders share stand
beside it.

What it does not decide: answer quality. A removal changes the path: it goes to a live check of
answers in stage 4 and to Julia's word (§8.3, item 14). MultiHop-RAG, advisory in stage 2,
counts here: a loss of gold there is a loss all the same; its gold is in the pool for 22 of its
70 questions with gold, so its pairs are small.

**Forecast, written before the count:** on WixQA at the ranked point the fused five hold fewer
gold articles than the reranker's 68 (a *loss*); after expansion on ConditionalQA no detected
difference, as the expansion already restores what the rerank drops there.

## Records

- Tool: [`reports/no-rerank/tools/no_rerank_point.py`](../../reports/no-rerank/tools/no_rerank_point.py),
  run on the Mac in the gate checkout; it writes `record.json` and `rows.jsonl` — ids, flags,
  counts, never a text of a question or a document.
- Tests: `tests/test_no_rerank_point.py` (the reading on hand-made rows);
  `tests/test_no_rerank_point_artifact.py` (the record read again from its rows and the export).
- The record: `reports/no-rerank/5e308fe/`, its capsule in `docs/evidence/`, one row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md).
