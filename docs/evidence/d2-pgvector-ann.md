# D.2 pgvector HNSW ANN — measured slice

**Verdict:** On 2026-09-21, pgvector 0.8.1 HNSW cosine top-20 with
`ef_search=100` reached mean recall@20 0.9652 against exact cosine top-20 over
115 queries at warm p95 3.45–3.64 ms versus 21.10–23.24 ms exact. The sole
severe outlier, `aircargo-harassment-investigation-timeline`, is now measured
by two focused replays: it persists on the retained original index, where the
recall curve is non-monotonic, and does not occur on a fresh rebuild. The
evidence localizes the observed behaviour to the retained index state under
this controlled replay; no internal pgvector/HNSW root cause is established.
Phase D remains open for actual graph/NetworkX plus evidence-join parity and
cold-start/host RAM; no runtime default or migration decision changes.

## Numbers

| Query set | n | Mean recall@20 | Min recall@20 | Exact p95 (ms) | HNSW p95 (ms) |
|---|---:|---:|---:|---:|---:|
| All queries | 115 | 0.965217 | 0.20 | 21.10–23.24 | 3.45–3.64 |
| Phase-C cases | 100 | 0.960500 | 0.20 | 21.08–23.31 | 3.46–3.64 |
| Multi-hop/aggregation | 15 | 0.996667 | 0.95 | 21.19–22.06 | 3.36–3.58 |

- Recall@20 distribution: 76 at 1.00, 22 at 0.95, 10 at 0.90, 4 at
  0.85, 2 at 0.75 and 1 at 0.20.
- The sole severe outlier is `aircargo-harassment-investigation-timeline`,
  with 4/20 overlap at `ef_search=100`. The focused replays below measure
  this one case in isolation; no cause is asserted beyond the localization
  they support.

## Focused outlier replay

Two focused artifacts replay only this case at
`ef_search=40/100/200/400/800/1000` against the exact cosine top-20. Both
report exactly the same exact top-20 IDs as canonical D.2.

| Artifact | Index | ef 40 | ef 100 | ef 200 | ef 400 | ef 800 | ef 1000 |
|---|---|---:|---:|---:|---:|---:|---:|
| [Fresh rebuild](../../evaluation/d2-pgvector-ann-outlier.json) | rag_spike_d2_outlier_20260921_1aa662e | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| [Retained original](../../evaluation/d2-pgvector-ann-outlier-original-index.json) | rag_spike_d2_ann_20260921 | 1.00 | 0.20 | 1.00 | 1.00 | 1.00 | 1.00 |

- On the retained original index, `ef_search=100` exactly reproduces canonical
  D.2's HNSW ranking and 4/20 overlap; all three repetitions are stable.
  `ef_search=200` restores 20/20, but `ef_search=40` is also 20/20, so the
  curve is non-monotonic and must not be read as ordinary insufficient
  `ef_search`.
- The fresh rebuild is 20/20 across the whole measured grid, including
  `ef_search=100`, and does not reproduce the canonical ANN ranking there;
  its summary diagnosis is `already_full_at_baseline` with
  `monotonic_nondecreasing_recall` true, while the original-index artifact
  reads `recovered_by_higher_ef_search` with
  `monotonic_nondecreasing_recall` false.
- The evidence localizes the observed behaviour to the retained index state
  under this controlled replay. It does not establish an internal
  pgvector/HNSW root cause; no corruption, randomness, pgvector defect or
  proven mechanism is asserted.

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

### Focused-artifact provenance

- [Fresh-rebuild report](../../evaluation/d2-pgvector-ann-outlier.json):
  byte length 68679, SHA-256
  `59258f8175d266fc8315270037e379c2d76f3ad534893c01079d8f9f0efe0b15`,
  code base `1aa662eda3ce6368109d08d1baa0450b36982ef0`, scratch DB
  `rag_spike_d2_outlier_20260921_1aa662e`; generated before `database_mode`
  was added, so it carries no `database_mode` field.
- [Retained-original-index report](../../evaluation/d2-pgvector-ann-outlier-original-index.json):
  byte length 68807, SHA-256
  `ea8cd0f382c155c44b4cec8934a93a2f0b95d0f85b629684931f3c86c6aeb887`,
  code base `527af25b54eaaa59be18cc62ae4e9c7d80dedd1f`, scratch DB
  `rag_spike_d2_ann_20260921` with `config.database_mode: existing_index`.
  Commit `527af25` added `--reuse-existing-database` to
  `scripts.pgvector_ann_outlier_run`; the reuse path performs no setup, create
  or drop against the retained database and uses safe `SET ROLE`.

## Semantics and limitations

- ANN recall is overlap with exact vector top-20 only: not context
  precision/recall, final reranked quality or endpoint latency.
- Query timing excludes shared encoding, setup, scoring and commit; it is a
  warm, single-process scratch-DB measurement.
- `kb_graph_nodes` is synthetic one-node-per-chunk membership only. The actual
  NetworkX graph and edges, evidence joins and write policies are not tested.
- No reranker, cold-start RAM or total-host RAM was measured. This result does
  not close the phase-C 0.63 gate, replace GR-3 or change a production default.
- The focused replays measure one case on two index states only; they do not
  measure latency, cover the other 114 cases or establish an internal
  pgvector/HNSW root cause.

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

The two focused artifacts are pinned in the same way: do not overwrite or
regenerate either one, and do not delete the retained scratch database
`rag_spike_d2_ann_20260921`, which the original-index replay depends on.

## Verification

`tests/test_pgvector_ann_artifact.py` pins the full artifact SHA, code base,
D.1 input equality and tracked input/source hashes; checks RLS, plans and
config; recomputes all 115 recall rows and every latency p50/p95; and verifies
all three exact/HNSW ranking repetitions. `tests/test_pgvector_ann.py` covers
the SQL, settings and helpers. `tests/test_pgvector_ann_outlier_artifact.py`
pins both focused raw files by byte length and SHA-256, replays their
recall/recovered/missed IDs, validates three-run stability and provenance, and
checks exact top-20 equality with canonical D.2 plus the original-index
`ef_search=100` ranking equality. GitHub Actions is unavailable until early
October 2026, so final gates run on the Mac.

## Remaining Phase D

The severe-outlier diagnostic is measured and closed as a bounded
investigation (focused replay above). Remaining: complete actual
graph/NetworkX plus evidence-join parity and measure cold-start/host RAM
before any migration decision; D.3 already measured final reranking. See
[ADR 0007](../adr/0007-pgvector-spike.md).
