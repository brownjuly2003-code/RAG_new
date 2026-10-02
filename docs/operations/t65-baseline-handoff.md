# T-65 production baseline — preparation, 2026-10-02

T-65 remains open: no new quality measurement has been published.

## Implemented prerequisite

`scripts/ab_remote_contextual.py --stage production --retrieval-only` uses
`ConversationSession.ask` with the normal production graph and interrupts it
before `generate`. Classification, query transformation, retrieval, expansion,
reranking and the normal conditional grading path remain unchanged. Simple
queries still bypass grading, as they do in production.

The mode retains request budgets and tracing, refuses agentic mode, and writes
neither an answer nor a conversation-history entry. Answer evaluation and
auto-response verification do not run. Full production replay remains the CLI
default. Archived stages cannot use `--retrieval-only`.

Output: `production_retrieval_contexts.json`, with `execution_mode:
retrieval_only` on every row. An existing output is not overwritten. The
exported context is the post-grading input to generation; no answer was sent.

## Fresh verification

- Red: new regression tests failed because the session keyword and CLI flag
  did not exist (4 failed, 1 passed).
- Mac: `pytest tests/test_production_retrieval_only.py
  tests/test_harness_api_parity.py tests/test_ask_contract_route.py
  tests/test_session_version.py tests/test_session_serialize.py -q
  -p no:schemathesis --tb=short` — **285 passed**.
- Mac: the main strict mypy command from `.github/workflows/ci.yml` —
  **145 source files, no issues**. Ruff passed on the three changed Python files.
- Mac snapshot: `/Users/julia/RAG_new_t65_check_e876d3adaa54`; archive SHA-256
  `e876d3adaa5495c7523e3de8a177e606005dffea97c2854993c41c77b4235a5f`.
  Built from `1dc43a2` plus the three changed Python files, outside shared checkouts.
- Models were fixtures in these tests. This proves control flow, not model quality.

## Pinned embedding preparation — 2026-10-02

The inspected Mac production collections have no embedder manifest. The retained
`RAG_new_gr2m_results_9ca8630/chunks.npz` has 5589 × 1024 vectors but no HF
revision. Neither can establish the new baseline's embedding identity; do not
retroactively stamp them.

`scripts/production_embeddings.py` now computes a separate, cumulative NPZ
checkpoint. It binds the corpus archive SHA, ordered text SHA and the loaded
embedder's complete manifest. Every valid batch is saved atomically. Resume is
explicit; incompatible, unverified or invalid vectors are refused before encoding
or replacing the checkpoint. This prepares vectors only; it publishes no index
and changes no retrieval defaults. Use `python -m scripts.production_embeddings
--help` for the Mac CLI; `--max-batches` bounds a run, `--resume` continues it.

Fresh verification:

- Red: 16 tests failed on the absent module. Windows green: **16 passed**.
- Mac: `pytest tests/test_production_embeddings.py
  tests/test_production_retrieval_only.py tests/test_harness_api_parity.py
  -q -p no:schemathesis --tb=short` — **275 passed**; scoped Ruff passed.
- Snapshot: `/Users/julia/RAG_new_t65_embeddings_2851e3811508`, archive SHA-256
  `2851e38115082f2612ea5cfdd72cf5d8bdb2b6e6bc33d0ec96de1da9621d8092`
  (`07d9569` plus the new script and tests).
- Real Mac smoke: BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`,
  1024 dimensions, normalized, `hf_snapshot`; first run saved 1/5589 rows,
  resume saved 2/5589 and preserved the first row exactly. This is a model/cache
  check, not a retrieval-quality measurement. Machine-readable report:
  `.tmp/t65-embedding-smoke.json` in that snapshot and the Windows workspace.
- Corpus archive: `evaluation/gr1b-4436d61-graph-chunks.json.gz`, SHA-256
  `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12`.

The full embedding calculation **completed** at `2026-10-02T14:01:16Z`, exit 0,
after starting at `12:42:17Z` (Mac PID `74090`, batch size 8). All **5589 × 1024**
vectors are complete and validated. Do not re-encode this corpus. The snapshot's
`.tmp/t65-embedding-full-state.json` and `.tmp/t65-embedding-full.log` retain the
terminal result; checkpoint `.tmp/t65-verified-embeddings.npz` has SHA-256
`3903187e56dd4d8accf642f612910c6ca2082d1e7e55b7d67cd072ce0978fb5a`.

Executor: Codex fallback after GLM's initial request and one narrowed retry both
ended `incomplete/max_output_tokens`. No partial GLM response was applied.

## Isolated index builder — 2026-10-02

`python -m scripts.production_index --help` now exposes the next preparation
step. It requires the corpus archive, a complete checkpoint, an independently
pinned embedder manifest JSON and the source code SHA. It validates archive and
ordered-text hashes, manifest equality, vector count/dimension/normalization
before creating a new output directory. Existing output is refused. It builds
`<output>/chroma` with persisted HNSW adds and writes `index-receipt.json` only
after the expected count is present. No model is loaded or existing index changed.
The default collection is `rag_docs_aircargo`; point the isolated baseline's
Chroma setting at `<output>/chroma`. No production setting has been changed.

- Red: 12 tests failed on the absent builder module.
- Mac: `pytest tests/test_production_index.py tests/test_production_embeddings.py
  -q -p no:schemathesis --tb=short` — **28 passed**; scoped Ruff and CLI help passed.
  A fresh process reopened real Chroma and checked vectors, text, metadata,
  manifest and a vector query. Embeddings in this test are fixtures.
- Snapshot `/Users/julia/RAG_new_t65_index_a09cd1522d8b`, archive SHA-256
  `a09cd1522d8b3c641ec33eee296d1bd03710e378a53d4a7bd433a93da12cc563`:
  `6498d83` plus the new builder and tests. This is preparation, not a measurement.
- Executor: continued Codex fallback from the two incomplete GLM requests above.

### Real index verified

Built with `72fbd72`, ChromaDB 1.5.9; directory on Mac:
`/Users/julia/RAG_new_t65_embeddings_2851e3811508/.tmp/t65-index-72fbd72`.
`index-receipt.json` pins corpus, checkpoint, text order, embedder, code and build
configuration. A separate process verified all 5589 vectors **exactly**, all
texts and metadata against the inputs, and `check_collection_manifest` returned
`match` / `eligible`. Log sequence = persisted vector sequence = **5589** (tail 0).
Report: `reopen-verification.json` beside the receipt; local copy:
`.tmp/t65-index-reopen-verification.json`. This verifies storage, not quality.

Runtime for builder/verification: `/Users/julia/RAG_new_gr4_venv/bin/python`
with `PYTHONPATH=/Users/julia/RAG_new_mf_gate_site` (also used for the tests).
The first launcher lacked `psutil`; native macOS `kqueue` replaced it. The first
builder invocation omitted this package path and refused at the Chroma import,
before creating output. Using the verified test environment resolved it.

## Remaining T-65 work

1. Checkpoint and isolated index are verified; pin the remaining model digests
   and retrieval runtime config before the measurement. Use the existing index.
2. Run the bounded real Chroma/exact comparison on 30 H cases and publish any
   divergence (T-62 acceptance boundary).
3. Collect H 100 + Hm 15 through the retrieval-only path, retain trace timings
   and exclude failed/ineligible runs. Record corpus SHA, code SHA and config.
4. Judge the new contexts, compute lexical/development metrics and the loss map,
   publish the capsule and evidence row. Keep `provisional_ruler` until D2 closes.

Human D2/D3 inputs remain pending. No retrieval default or quality gate changed.
