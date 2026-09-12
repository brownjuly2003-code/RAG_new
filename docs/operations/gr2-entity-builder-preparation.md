# GR-2 entity builder — preparation

2026-09-12. This is preparation, not a completed slice or a quality measurement.

`ingestion/entity_graph.py` enriches a tenant structural graph from per-chunk
extraction results. It normalizes AWB/HAWB/MAWB/booking aliases, removes generic
terms, keeps entities occurring in at least two distinct documents, and adds
chunk-to-entity mentions plus bidirectional co-occurrence edges weighted by
the number of shared chunks. Unknown chunk IDs and mixed-tenant inputs fail.
The input graph is unchanged; IDs and output ordering are deterministic.

Normalization reuses the existing BM25 tokenizer. Contrary to plan §GR-2's
wording, that tokenizer does **not** stem words. No stemming dependency was
added. Exact identifier aliases are supported; inflection matching remains open.
Inputs are bounded to 12 normalized entities, each at most 128 characters.

Migration `033` extends the existing node/edge kind constraints. It preserves
tenant keys and RLS. Downgrade refuses populated entity graphs instead of
deleting their data. The repository restores the entity builder version, and
the fixture graph's digest survives a database round trip.

## Verification

- Windows: 27 tests passed across `test_entity_graph`, `test_entity_normalization`,
  and the four structural builder/projection/persistence/pipeline test modules.
  New behavior followed red-green tests, including kind constraints, builder
  version and digest after reload.
- Mac: both CI strict mypy commands passed (133 main modules, 31 API/vectordb).
- PostgreSQL on Mac: real migration 032 → 033, entity persistence, populated
  downgrade refusal, and empty downgrade/upgrade passed. The check ran in a
  unique temporary schema in the `postgres` database on port 55432, then rolled
  back the outer transaction. It did not migrate `ragnew_prod`.
- Reproduce the database check from the repository root on Mac:
  source `~/.config/rag-new/postgres-secrets.env` with exports enabled, then run
  `python scripts/qa/verify_entity_graph_postgres.py`.
  This admin connection tests schema behavior, not non-superuser RLS isolation.

Mac test checkout: `/Users/julia/RAG_new_gr2_20260912_build`; Python environment:
`/Users/julia/RAG_new_gr4_venv`. Full suite and live extraction were not run.

## Resume

Next: resumable extraction with corpus/prompt/model provenance; then entity
matching from SGR `entities[]`, bounded traversal and RRF integration, followed
by the GR-2 bucket measurement. No entity lane or default activation is claimed.
Reuse existing embeddings. The structural GR-1b NO-SHIP result is unchanged.
