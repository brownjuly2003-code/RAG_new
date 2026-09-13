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

Resumable extraction is implemented in `scripts/extract_graph_entities.py`.
Default `--max-calls 0` verifies the pinned input and cache without credentials
or API calls. Explicit batches use the shared probe prompt, temperature zero,
a pinned model ID, strict JSON validation and a single-writer lock. Each completed
chunk is flushed to `entities.jsonl`; restart skips it. Changed corpus, prompt,
model or chunk text is rejected, as are corrupt/incomplete cache rows. A corrupt
tail requires inspection; the runner never silently truncates it.

Mac input: `ab_phase2_G1_graph_chunks.json`, 5,589 chunks, SHA-256
`5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`.
Corpus reference: `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`.
The CLI pins the supplied corpus reference and checks the chunk payload hash;
it does not rederive historical chunk provenance from source documents.
Cache is under `reports/kb_graph/<corpus_sha256>/` in the same Mac test checkout.
The external provider does not supply a weights digest: `model_digest` remains
explicitly null, so this is not full model-weight provenance.

A three-call smoke budget using `mistral-small-2506` produced zero cached chunks:
the first request failed, and one diagnostic request confirmed HTTP 429. No more
requests or key rotation were attempted. Resume live extraction only after the
provider limit is resolved. Keys were passed over SSH stdin, never logged or stored
in the checkout. Focused extraction tests cover resume, invalid output, cache/input
guards, no-key dry run, and compatibility with the entity builder. Both CI mypy
commands passed on Mac (134 main modules, 31 API/vectordb).

## Local route

2026-09-13. The Mistral free tier cannot finish the 5,589-chunk payload: it
answered HTTP 429 and does not report a weights digest. The Mac runs Ollama
0.33.2 with `qwen2.5:7b`, manifest digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, on CPU.

Benchmark on eight chunks at evenly spaced payload indices, the unchanged
`EXTRACT_PROMPT`, temperature 0, seed 42, `num_ctx` 4096:

- no response format: 5 of 8 answers valid (three had more than 12 entities),
  warm mean 23.2 s per chunk, about 36 h for the payload;
- JSON schema as Ollama's `format` (`EXTRACT_SCHEMA`, at most 12 strings of
  1–128 characters): 8 of 8 valid, warm mean 11.4 s per chunk, about 17.7 h.

Chunks are 176–973 characters (median 648) and prompts 292–460 tokens, so
`num_ctx` 4096 never truncates a prompt.

This is preparation, not a measurement. `--max-calls 0` verifies the server,
digest, inputs and cache without a generation request. `--min-interval` does
not throttle this route.

Give each provider/model its own cache directory. The 2026-09-12 Mistral smoke
already wrote a schema_version 1 `manifest.json` under
`reports/kb_graph/<corpus_sha256>/` (`mistral-small-2506`, no `provider` or
`generation`, zero cached chunks). After the schema bump, `extract_entities`
compares the whole manifest, so both `--provider ollama` and a Mistral rerun
against that directory stop with `Extraction cache provenance mismatch`.
Existing schema_version 1 caches are refused. The zero-row Mistral manifest may
be removed only after confirming there is no `entities.jsonl` beside it.

```
python scripts/extract_graph_entities.py \
  --provider ollama \
  --base-url http://127.0.0.1:11434 \
  --model qwen2.5:7b \
  --on-invalid record \
  --chunks ab_phase2_G1_graph_chunks.json \
  --chunks-sha256 5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94 \
  --corpus-sha256 c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343 \
  --cache-dir reports/kb_graph/c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343/ollama-qwen2.5-7b \
  --max-calls 0
```

Entity matching, bounded traversal, third-list RRF and opt-in runtime loading
are now covered by [synthetic HTTP evidence](../evidence/gr2-entity-retrieval-wiring.md).
Next: complete extraction when available, persist the enriched tenant graph,
reset its retriever cache, then run the GR-2 bucket measurement. No default activation.
Reuse existing embeddings. The structural GR-1b NO-SHIP result is unchanged.
