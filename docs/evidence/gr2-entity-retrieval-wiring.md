# GR-2 entity retrieval wiring — synthetic evidence

The opt-in graph retriever now uses SGR entities for `multi_hop`, `aggregation`
and `global`. Canonical aliases and BM25 match graph entity names. Expansion
visits at most two co-occurrence hops, with a 50-entity frontier per hop and
at most 50 additional chunk candidates. Candidates respect the source filter,
enter a third RRF list at their original ranks, then use the shared reranker
and existing section coherence. Paths record matched names and actual hops.

With `graph_retrieval=on` and an explicit `DATABASE_URL`, the tenant retriever
loads persisted enrichment through `StructuralGraphRepository`. Every structural
node and edge must match the graph rebuilt from current chunks, including content
hashes. Missing enrichment, stale data or an unavailable database keeps structural
retrieval. Off/auto retain hybrid fallback. A changed stored graph requires the
existing tenant retriever cache to be reset before it is loaded again.

## Evidence

On 2026-09-12, Mac checkout `/Users/julia/RAG_new_gr2_20260912_build`, using
`/Users/julia/RAG_new_gr4_venv/bin/python`:

- 57 focused tests passed across `test_entity_graph_loading`, `test_entity_retrieval`,
  `test_graph_retrieval_path`, `test_graph_retriever`, `test_sgr_classifier`,
  `test_graph_helpers`, `test_provider_graph_integration`, `test_gr1b_stage_replay`.
- Six HTTP cases in `tests/integration/test_graph_lane_e2e.py` passed separately:
  structural/entity fixtures × on/off/auto. The real classifier, runtime retriever,
  conversation graph, `/api/ask`, SQLite trace and Evidence endpoint run together.
  On adds a second source via the entity; off/auto exclude it. The model/store
  and repository response are fixtures; this is not a live PostgreSQL acceptance.
- Both full CI mypy scopes passed: 136 main modules and 31 API/vectordb modules.
- `python -m ruff check .` and `git diff --check` passed on Windows.

The new behavior had failing tests before implementation: unsupported entity
arguments, missing classifier forwarding, wrong multi-hop routing and missing
persisted-graph loader. Unit checks cover aliases, lexical matching, two-hop and
50-chunk bounds, source filtering, request isolation, three-list RRF and stale
graph rejection.

## Limits

This proves product wiring on synthetic data, not retrieval quality. Live
extraction remains 0/5589 cached because Mistral returned HTTP 429. No provider
retry, embedding rebuild, deployment or push was performed. GR-2 quality
measurement and its acceptance gate remain open; GR-1b remains NO-SHIP.
