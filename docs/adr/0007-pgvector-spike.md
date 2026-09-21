# ADR 0007 — retrieval storage spike

Status: **provisional; D.1 measured, Phase D incomplete**. 2026-09-21.

Decision: retain the current retrieval backend. This first experiment does not
justify migration. It measures a controlled pre-reranker comparison, not final
product quality or the full graph/evidence trust boundary.

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

## Isolation and limits

The scratch database has FORCE RLS on retrieval and synthetic graph membership
tables. A non-owner NOSUPERUSER/NOBYPASSRLS role sees 5589 aircargo rows, one
other-tenant sentinel only in that tenant context, and zero without context.
Explicit cross-tenant predicates return zero. The integration acceptance also
checks ranked retrieval for aircargo, sentinel and nonexistent tenants.

This is **synthetic membership**, not production `kb_graph_nodes` schema or
NetworkX traversal parity. Production graph edges, evidence joins and write
policies are untested. Chroma/BM25 is a single-tenant collection for this run;
the experiment does not prove its application-level isolation.

No cold-start RAM or final reranked quality was measured. RRF uses rank 1 for
both arms; production currently starts at rank 0. These numbers must not replace
GR-3 final reranked numbers or close the 0.63 gate. No runtime defaults changed.

## Next bounded Phase D experiment

Use an index-friendly vector candidate subquery, record its real EXPLAIN and
ANN recall against exact vector top-k, then compare final reranked quality.
Complete actual graph/NetworkX and evidence-join parity plus cold-start RAM
before a migration decision. Do not rerun or re-embed the unchanged corpus.

Full provenance, reproduction and acceptance: [D.1 evidence](../evidence/d1-pgvector-prererank.md).
