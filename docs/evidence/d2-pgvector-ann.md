# D.2 pgvector HNSW ANN — measured slice

**Verdict:** On 2026-09-21, pgvector 0.8.1 HNSW cosine top-20 with
`ef_search=100` reached mean recall@20 0.9652 against exact cosine top-20 over
115 queries at warm p95 3.45–3.64 ms versus 21.10–23.24 ms exact, with one
severe outlier still requiring diagnosis. Phase D remains open; no runtime
default or migration decision changes.

## Numbers

| Query set | n | Mean recall@20 | Min recall@20 | Exact p95 (ms) | HNSW p95 (ms) |
|---|---:|---:|---:|---:|---:|
| All queries | 115 | 0.965217 | 0.20 | 21.10–23.24 | 3.45–3.64 |
| Phase-C cases | 100 | 0.960500 | 0.20 | 21.08–23.31 | 3.46–3.64 |
| Multi-hop/aggregation | 15 | 0.996667 | 0.95 | 21.19–22.06 | 3.36–3.58 |

- Recall@20 distribution: 76 at 1.00, 22 at 0.95, 10 at 0.90, 4 at
  0.85, 2 at 0.75 and 1 at 0.20.
- The sole severe outlier is `aircargo-harassment-investigation-timeline`,
  with 4/20 overlap at `ef_search=100`. No cause is asserted. Higher-`ef`
  behaviour remains unmeasured and must be diagnosed before selecting an
  operating value.

## Provenance

- Run date 2026-09-21; native Mac PostgreSQL 16.15, pgvector 0.8.1, Python
  3.11.15, NumPy 1.26.4 and psycopg2-binary 2.9.13.
- Code base `5c1075c9306eabc467b4f3349328c38e65652a5e`; clean, pushed preparation
  commit.
- [Raw report](../../evaluation/d2-pgvector-ann.json), SHA-256
  `93d5b2da4c82abecf645be00501ee6b5aa054addbe4cfdaa703b1ca8b88fad45`.
- Inputs are byte-identical to D.1: 5589 BGE-M3 chunk vectors and 115 query
  vectors (100 phase-C plus 15 multi-hop/aggregation). Full hashes are in the
  report and replay test. Both datasets remain agent-authored and unapproved.
- Scratch DB `rag_spike_d2_ann_20260921`; non-owner
  NOSUPERUSER/NOBYPASSRLS measurement role; FORCE RLS. Counts in both tables:
  unset 0, `aircargo` 5589, `zzz_other` 1; cross-tenant rows are invisible.
- Exact cosine top-20 disables index scans. ANN cosine top-20 materializes
  index-friendly vector candidates first, then performs the synthetic
  chunk-membership join post-limit. HNSW uses `ef_search=100` and
  `hnsw.iterative_scan=strict_order`. Default and force-index EXPLAIN both use
  `spike_chunks_embedding_idx`; the timed HNSW arm forces the index. Rankings
  are stable across three alternating-order warm repetitions.

## Semantics and limitations

- ANN recall is overlap with exact vector top-20 only: not context
  precision/recall, final reranked quality or endpoint latency.
- Query timing excludes shared encoding, setup, scoring and commit; it is a
  warm, single-process scratch-DB measurement.
- `kb_graph_nodes` is synthetic one-node-per-chunk membership only. The actual
  NetworkX graph and edges, evidence joins and write policies are not tested.
- No reranker, cold-start RAM or total-host RAM was measured. This result does
  not close the phase-C 0.63 gate, replace GR-3 or change a production default.

## Reproduction

Do not overwrite or rerun the unchanged canonical output. From
`/Users/julia/RAG_new_d2_5c1075c`, run
`/Users/julia/RAG_new_gr4_venv/bin/python -m scripts.pgvector_ann_run` with:

- chunks: `/Users/julia/RAG_new_gr3_results_32de532/phase_c/ab_phase2_G2_graph_chunks.json`;
- vectors: `/Users/julia/RAG_new_gr3_results_32de532/inputs/chunks.npz`;
- queries: `/Users/julia/d1-queries.npy`;
- both `--cases evaluation/curated_cases_aircargo.jsonl` and
  `--cases evaluation/curated_cases_aircargo_gr_multihop.jsonl`;
- a fresh `--database rag_spike_UNIQUE_LOWERCASE_NAME` and output path.

Set `SPIKE_ADMIN_DSN` privately from
`~/.config/rag-new/postgres-secrets.env`, normalizing its driver in memory;
never print it.

## Verification

`tests/test_pgvector_ann_artifact.py` pins the full artifact SHA, code base,
D.1 input equality and tracked input/source hashes; checks RLS, plans and
config; recomputes all 115 recall rows and every latency p50/p95; and verifies
all three exact/HNSW ranking repetitions. `tests/test_pgvector_ann.py` covers
the SQL, settings and helpers. GitHub Actions is unavailable until early
October 2026, so final gates run on the Mac.

## Remaining Phase D

Diagnose the recall outlier, compare final reranked quality, complete actual
graph/NetworkX and evidence-join parity, and measure cold-start/host RAM before
any migration decision. See [ADR 0007](../adr/0007-pgvector-spike.md).
