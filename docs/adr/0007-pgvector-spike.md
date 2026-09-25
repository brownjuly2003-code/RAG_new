# ADR 0007 — retrieval storage spike

Status: **accepted: retain the current retrieval backend; D.1–D.5 measured**. 2026-09-25.

Decision: retain the current retrieval backend. D.1–D.5 measured a controlled
pre-reranker comparison, ANN behaviour, one offline final-rerank pass, production
graph/evidence parity and tenant policies on a migrated scratch database, and the
cold start and memory of both arms. The PostgreSQL arm reaches its first result
sooner, its client holds less memory and its answers did not change across
restarts. Its server holds memory of its own, and its keyword-proxy precision
was lower than Chroma + BM25's in every D.1 and D.3 bucket, before and after
the rerank. The measured differences do not justify a migration. Final product
quality remains unmeasured.

## D.1 numbers

Native Mac PostgreSQL 16.15 + pgvector 0.8.1 versus Chroma 1.5.9 + BM25 0.2.2.
Both receive the same 5589 BGE-M3 chunk vectors and 115 query vectors. Top-20 per
branch, one-based RRF k=60, top-5, aggregate 6000-character context cap.

| Bucket / arm | Keyword context precision | Keyword context recall | Warm p95 ms, range of 3 runs |
|---|---:|---:|---:|
| 100 phase-C / PostgreSQL | 0.456188 | 0.840000 | 31.42–34.06 |
| 100 phase-C / Chroma + BM25 | 0.501882 | 0.830000 | 17.99–18.28 |
| 15 multi-hop/aggregation / PostgreSQL | 0.204128 | 0.422222 | 31.11–32.79 |
| 15 multi-hop/aggregation / Chroma + BM25 | 0.264656 | 0.477778 | 23.86–25.01 |

Quality is identical across all three repetitions. These are keyword proxies,
not document precision/recall@k. Datasets are agent-authored and unapproved.
PostgreSQL uses Russian `plainto_tsquery` (AND semantics) and `ts_rank_cd`;
the comparison therefore changes the lexical algorithm as well as storage.

The captured first-query EXPLAIN uses sequential chunk scans, **not HNSW or
GIN**, despite both indexes existing. Window ranking and the membership join
are part of this measured SQL. No claim about optimized pgvector ANN performance
follows. Chroma runs its actual collection query; this is not the old NumPy
dense-pool baseline. Timings include query retrieval/fusion, exclude shared
encoding, setup, scoring and PostgreSQL commit; they are not endpoint latency.

## D.2 ANN numbers

The index-friendly vector candidate query now reaches the HNSW
`spike_chunks_embedding_idx` under both default and force-index EXPLAIN. The
timed arm forces HNSW with `ef_search=100` and `strict_order`, then performs
the synthetic chunk-membership join after the top-20 limit. Exact vector
top-20 disables index scans.

| Bucket | Cases | Mean recall@20 | Min recall@20 | Exact warm p95 ms | HNSW warm p95 ms |
|---|---:|---:|---:|---:|---:|
| All | 115 | 0.965217 | 0.20 | 21.10–23.24 | 3.45–3.64 |
| Phase C | 100 | 0.960500 | 0.20 | 21.08–23.31 | 3.46–3.64 |
| Multi-hop/aggregation | 15 | 0.996667 | 0.95 | 21.19–22.06 | 3.36–3.58 |

Rankings are stable across three alternating-order repetitions. Of 115 cases,
76 have recall 1.00 and 22 have 0.95. The sole severe outlier,
`aircargo-harassment-investigation-timeline`, overlaps exact search at only
4/20. Two focused replays (2026-09-21) close the diagnostic as a bounded
investigation. Both match canonical D.2's exact top-20 IDs. On the retained
original index, `ef_search=100` exactly reproduces the canonical HNSW ranking
and the 4/20 overlap across three stable repetitions, `ef_search=200`
restores 20/20 while `ef_search=40` is also 20/20, so the curve is
non-monotonic and is not ordinary insufficient `ef_search`; a fresh rebuild
is 20/20 across the whole measured grid, including `ef_search=100`, and does
not reproduce the canonical ANN ranking there. The evidence localizes the
behaviour to the retained index state under this controlled replay; it does
not establish an internal pgvector/HNSW root cause, and no corruption,
randomness or pgvector defect is asserted. Recall here is ANN overlap with
exact vector top-20, not context quality or final reranked quality. Raw
artifacts: `evaluation/d2-pgvector-ann-outlier.json` and
`evaluation/d2-pgvector-ann-outlier-original-index.json`.

## D.3 final-rerank numbers

One offline CPU pass reranks the byte-pinned D.1 candidate lists with
`BAAI/bge-reranker-v2-m3`; it does not retrieve or embed again.

| Bucket / saved arm | Pre-rerank precision | Rerank precision | Pre-rerank recall | Rerank recall |
|---|---:|---:|---:|---:|
| 100 phase-C / PostgreSQL | 0.456188 | 0.495865 | 0.840000 | 0.905000 |
| 100 phase-C / Chroma + BM25 | 0.501882 | 0.505916 | 0.830000 | 0.905000 |
| 15 multi-hop/aggregation / PostgreSQL | 0.204128 | 0.228451 | 0.422222 | 0.466667 |
| 15 multi-hop/aggregation / Chroma + BM25 | 0.264656 | 0.252723 | 0.477778 | 0.500000 |

Across all 115 cases, post-rerank precision / recall is 0.460985 / 0.847826
for PostgreSQL and 0.472891 / 0.852174 for Chroma + BM25. Every full order
changed; the top-five set changed in 112 and 114 cases respectively. The
reranker narrows but does not reverse the precision gap. This is a bounded
keyword-proxy result, not a migration decision or the Phase-C quality gate.

PostgreSQL reranks exactly 20 candidates per case at global p50/p95
14115.76/21885.67 ms. Chroma + BM25 reranks 23–40 (mean 34.85) at
28418.78/40548.97 ms. These single-run `predict` timings use fixed arm order
and unequal work; they do not establish a cross-arm performance difference.

## D.4 graph and evidence numbers

On 2026-09-25, the tracked aircargo graph round-tripped through the production
repository on a fresh migrated PostgreSQL scratch database. Synthetic evidence rows
joined the production graph schema; a disposable role observed tenant isolation through
a cross-tenant insert rejected by RLS and append-only evidence through evidence update
and delete probes rejected by immutability triggers.

| Observation | Measured result |
|---|---|
| Graph round trip | 10300 nodes, 17327 edges; identical persisted contract |
| Mismatches | 0 traversal, node and edge |
| Unresolved references | 5877 as built, not persisted by the schema |
| Evidence join | 5589 chunk nodes, 5589 links, 5589 join rows |
| RLS | Forced on 4 tables; own rows 10300, 17327, 5589, 5589; unset and cross-tenant 0 |
| Write probes | Cross-tenant insert `42501`; evidence update `55000`; evidence delete `55000` |
| Cleanup | 0 rows in 6 measured tables; disposable role absent; scratch database dropped |

## D.5 cold-start and memory numbers

On 2026-09-25, seven new-process trials per arm on one Mac reopened a persisted
Chroma collection and opened new connections to a PostgreSQL scratch database
loaded by D.1's loader. Both used D.1's pinned inputs and precomputed query vectors.

| Median observation | PostgreSQL + pgvector | Chroma + BM25 |
|---|---:|---:|
| Time to first fused result, ms (range) | 85.7 (84.8–90.0) | 1494.7 (1492.7–1998.2) |
| Driver import, ms | 12.5 | 417.5 |
| Open, ms | 22.7 | 61.2 |
| Restore, ms | — | 703.2 |
| BM25 index, ms | — | 297.9 |
| First fused query, ms | 50.5 | 17.3 |
| Client resident set after workload, bytes | 68,644,864 | 310,738,944 |
| Backend resident set, bytes; never added | 98,246,656 | — |
| Answers across trials | Fused and HNSW identical in all seven | Fused changed in 13 of 115 cases |

The collection's persisted index covered 5000 of its 5589 records, so each new
process re-inserted 589 from the write-ahead log. The spec's amendment 1 records
why Chroma's answers are compared, not gated.

## Isolation and limits

The scratch databases have FORCE RLS on retrieval and synthetic graph
membership tables. A non-owner NOSUPERUSER/NOBYPASSRLS role sees 5589 aircargo
rows, one other-tenant sentinel only in that tenant context, and zero without
context. Explicit cross-tenant predicates return zero. The D.1 integration
acceptance also checks ranked retrieval for aircargo, sentinel and nonexistent
tenants; D.2 records the same six RLS counts in its artifact.

D.1–D.3 used synthetic graph membership. D.4 measured the production
`kb_graph_nodes` and `kb_graph_edges` schema, NetworkX traversal parity, the
production evidence join, tenant isolation (a cross-tenant insert rejected with
`42501` by the RLS policy), and append-only evidence (update and delete rejected with
`55000` by immutability triggers) on a fresh migrated scratch database with synthetic
evidence rows. Chroma/BM25 is a single-tenant collection
for this run; the experiment does not prove its application-level isolation.

D.5 measured cold start and resident memory with precomputed query vectors and
no model load, against a running PostgreSQL server shared with other databases
and an uncontrolled file cache; a backend's resident set is recorded apart
from the client's and never added to it. D.1 RRF uses rank 1 for both arms;
production currently starts at rank 0. D.3 stores orders but not reranker
scores or a fully pinned inference configuration, and its arithmetic replay
is not an independent semantic check. These numbers must not replace GR-3
final reranked numbers or close the 0.63 gate. No runtime defaults changed.

## When to revisit

Phase D is measured, and no further bounded experiment is planned. The decision
reopens if one of these becomes a requirement:

- Storage-level tenant isolation, which PostgreSQL row-level security gave in D.1
  and D.4 and the Chroma/BM25 collection does not.
- Answers that do not change across process restarts, which the Chroma arm did not
  give under its default settings.
- A per-process memory or start-up budget that the Chroma arm's client does not meet.
- A PostgreSQL lexical arm that matches Chroma/BM25 quality.

Do not rerun or re-embed the unchanged corpus, do not overwrite the pinned D.2
artifacts, and do not delete the retained scratch database.

Full provenance, reproduction and acceptance: [D.1](../evidence/d1-pgvector-prererank.md),
[D.2](../evidence/d2-pgvector-ann.md),
[D.3](../evidence/d3-pgvector-rerank.md) and
[D.4](../evidence/d4-pgvector-graph-evidence.md) and
[D.5](../evidence/d5-pgvector-cold-start.md) evidence.
