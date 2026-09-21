# D.1 — native Mac pre-reranker storage feasibility

Measured 2026-09-21. [ADR 0007](../adr/0007-pgvector-spike.md) records the table,
decision and limitations. Phase D remains open; runtime unchanged.

## Provenance

- Source base `fa0146c`; exact SHA-256 of all three spike implementation/driver
  files and imported scoring/tokenization modules is in the
  [raw report](../../evaluation/d1-pgvector-prererank.json).
- Core retrieval and scratch database helpers: direct GLM 5.3, requested
  `output_config.effort=xhigh`, successful `end_turn`; coordinator reviewed,
  wrote independent tests/measurement driver and corrected three reproduced
  defects (SQL binding, BM25 API, INSERT tuple width).
- Corpus JSON SHA `5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`.
  Exactly the decompressed checked-in
  `evaluation/gr1b-4436d61-graph-chunks.json.gz`, 5589 chunks.
- Chunk NPZ SHA `3fcfaf2803187b73d42f0d25256dfbea5b4997bce28d2c4ad47fbe0985b2ab33`:
  `/Users/julia/RAG_new_gr3_results_32de532/inputs/chunks.npz`.
  Length-prefixed text digest checked before import; BAAI/bge-m3, 1024 dimensions.
- Query NPY SHA `7ff1a1224fa11e8d5579cefcbfde327253ae3c503c5e4676caec65cfebbde5c8`:
  `/Users/julia/d1-queries.npy`. Encoded once on Mac with cached BAAI/bge-m3,
  normalized, batch 8, `HF_HUB_OFFLINE=1`. Phase-C cases followed by multi-hop.
- Dataset SHAs `3737d694…` (100) and `0949d756…` (15), full hashes in report.
  Both remain agent-labelled, unapproved.
- Python 3.11.15, NumPy 1.26.4; all DB/library versions in report.
  pgvector v0.8.1 source `778dacf20c07caf904557a88705142631818d8cb`, native
  Homebrew PostgreSQL 16.15 on `deproject-mac`, loopback port 55432.
- Scratch DB/role `rag_spike_d1_20260921`; no existing database schema modified.
  Separate tiny `rag_spike_test_*` databases retain acceptance-test evidence.

## Reproduction

On Mac, from the source snapshot `/Users/julia/RAG_new_d1_20260921`, use
`/Users/julia/RAG_Support_Assistant/.venv/bin/python -m scripts.pgvector_spike_run`:

```text
--chunks /Users/julia/RAG_new_gr3_results_32de532/phase_c/ab_phase2_G2_graph_chunks.json
--vectors /Users/julia/RAG_new_gr3_results_32de532/inputs/chunks.npz
--queries /Users/julia/d1-queries.npy
--cases evaluation/curated_cases_aircargo.jsonl
--cases evaluation/curated_cases_aircargo_gr_multihop.jsonl
--database rag_spike_UNIQUE_LOWERCASE_NAME
--output /Users/julia/d1-new-report.json
```

Set `SPIKE_ADMIN_DSN` privately to the native psycopg2 `postgresql://` form of
the Mac admin URL. The setup refuses existing database names; never target a
production database. Cached vectors stay on Mac; metric replay below uses only
checked-in text and rankings and needs no database/model.

Three measured repetitions alternate arm order, with one warm-up query per arm.
Raw rankings, individual timings, per-case scores, RLS counts and first-query
EXPLAIN are in the report. The sequential-scan plan is evidence, not an ANN pass.

## Verification

Mac unit red/green: 2 expected failures → 8 passes. Native DB insertion regression:
tuple-width failure → acceptance pass, including non-owner FORCE RLS and ranked
cross-tenant checks. Independent acceptance command, with private DSN set:

```text
/Users/julia/RAG_new_gr4_venv/bin/python -m pytest scripts/pgvector_spike_acceptance.py -q
/Users/julia/RAG_new_gr4_venv/bin/python -m pytest tests/test_pgvector_spike.py tests/test_pgvector_spike_artifact.py tests/test_docs_hygiene.py -q
```

Final Mac gates: **38 passed** (new tests, scoring/generator regressions and
documentation), **1 native PostgreSQL acceptance passed**, Ruff clean.
The artifact test checks corpus/dataset/source hashes and recomputes all 690
per-case metric rows and latency percentiles. Ruff covers all added Python.
No API/UI behavior changed. Slice acceptance is published measurement with
provenance, not completion of Phase D. GitHub Actions remains unavailable.
