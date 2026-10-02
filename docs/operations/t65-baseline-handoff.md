# T-65 production baseline — preparation, 2026-10-02

T-65 remains open: no new quality measurement has been published.

## Implemented prerequisite

`scripts/ab_remote_contextual.py --stage production --retrieval-only` uses
`ConversationSession.ask` with the normal production graph and interrupts it
before `generate`. Classification, query transformation, retrieval, expansion,
reranking and the normal conditional grading path remain unchanged. Simple
queries still bypass grading, as they do in production.

The mode retains budgets and tracing, refuses agentic mode, and writes no answer
or history. Answer evaluation is omitted. Full production replay remains the CLI
default; archived stages cannot use `--retrieval-only`.

Output: `production_retrieval_contexts.json`, every row marked `retrieval_only`;
existing output is not overwritten. Context is the post-grading generation input.

## Fresh verification

- Red: missing session keyword and CLI flag (4 failed, 1 passed).
- Mac: retrieval-only, harness parity, route, session version/serialize tests:
  **285 passed**; strict mypy **145 files**, scoped Ruff clean.
- Fixture models prove control flow, not quality.

## Pinned embedding preparation — 2026-10-02

The inspected Mac production collections have no embedder manifest. The retained
`RAG_new_gr2m_results_9ca8630/chunks.npz` has 5589 × 1024 vectors but no HF
revision. Neither can establish the new baseline's embedding identity; do not
retroactively stamp them.

`scripts/production_embeddings.py` saves a cumulative NPZ checkpoint atomically,
binding corpus/text hashes and the embedder manifest. Explicit `--resume` refuses
incompatible or invalid vectors. `--max-batches` bounds a run. No defaults changed.

Fresh verification:

- Red: 16 tests failed on the absent module. Windows green: **16 passed**.
- Mac: `pytest tests/test_production_embeddings.py
  tests/test_production_retrieval_only.py tests/test_harness_api_parity.py
  -q -p no:schemathesis --tb=short` — **275 passed**; scoped Ruff passed.
- Snapshot: `/Users/julia/RAG_new_t65_embeddings_2851e3811508`, archive SHA-256
  `2851e38115082f2612ea5cfdd72cf5d8bdb2b6e6bc33d0ec96de1da9621d8092`
  (`07d9569` plus the new script and tests).
- BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024 dimensions,
  normalized, `hf_snapshot`. Resume smoke preserved the first vector exactly;
  report: `.tmp/t65-embedding-smoke.json` in the snapshot and Windows workspace.
- Corpus archive: `evaluation/gr1b-4436d61-graph-chunks.json.gz`, SHA-256
  `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12`.

The full embedding calculation **completed** at `2026-10-02T14:01:16Z`, exit 0,
after starting at `12:42:17Z` (Mac PID `74090`, batch size 8). All **5589 × 1024**
vectors are complete and validated. Do not re-encode this corpus. The snapshot's
`.tmp/t65-embedding-full-state.json` and `.tmp/t65-embedding-full.log` retain the
terminal result; checkpoint `.tmp/t65-verified-embeddings.npz` has SHA-256
`3903187e56dd4d8accf642f612910c6ca2082d1e7e55b7d67cd072ce0978fb5a`.

Executor: Codex fallback after two GLM `incomplete/max_output_tokens` responses;
neither partial response was applied.

## Isolated index builder — 2026-10-02

`python -m scripts.production_index --help`: requires a complete checkpoint,
independent manifest and code SHA; checks corpus/text hashes, manifest, count,
dimension and normalization. Creates a new index only, persists HNSW adds, writes
`index-receipt.json`. Collection: `rag_docs_aircargo`. Production defaults unchanged.

- Red: 12 tests failed on the absent builder module.
- Mac: `pytest tests/test_production_index.py tests/test_production_embeddings.py
  -q -p no:schemathesis --tb=short` — **28 passed**; scoped Ruff and CLI help passed.
  Fresh-process reopen verified fixture vectors, text, metadata and manifest.
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

## Staged parity runner — c3d2909

`scripts/production_parity.py`: prepare → transform → embed → retrieve → grade
→ verify. Registers 30 H cases by ascending SHA-256(case_id), data/code/runtime
identities, model revisions and config before results. Uses production provider,
graph nodes and HybridRetriever; replays saved real calls through ConversationSession.
Compares vector/pool/ranked order, effective query and post-grading context hash.
Cache misses, corrupt records, model errors and replay mismatches refuse evidence.
Resume is explicit; `--limit 1` bounds the initial smoke. Replay is not API latency.

Mac: **17 passed** (`test_production_parity`, `test_production_retrieval_only`),
scoped Ruff clean. Real Chroma / fixture models; includes rejected-document,
missing-cache and replay-mismatch cases. Snapshot:
`/Users/julia/RAG_new_t65_parity_9216fc576828` (archive SHA starts `9216fc576828`).
All model stages use `/Users/julia/RAG_Support_Assistant/.venv/bin/python` with
the package path above; tests append the lightweight venv's site-packages for pytest.
Codex fallback continues. Real smoke completed at `2026-10-02T15:08:42Z`, exit 0.
Fresh inspection: `aircargo-matliab-check` differs in vector/pool order between
Chroma and exact; ranked order and post-grading context hash match (five documents).
Both arms replayed through ConversationSession. This is one case, not the full result.

Full 30-case comparison resumed with `--resume` on 2026-10-02; existing smoke
records passed integrity checks and are reused. Run: snapshot's `.tmp/parity-c3d2909`.
Supervisor state: `.tmp/parity-full-state.json`; logs: `.tmp/parity-full-*.log`.
Windows launcher `.tmp/t65_parity_full_resume.py` (PID `17156`) keeps one SSH
connection attached. Local output: `.tmp/t65-parity-full-launch.log` / `.err`.
Observed after the bounded wait: running `transform`; full result still pending.
Do not launch another writer while it is active. It stops on a failed stage or
timeout, records the terminal status, and emits `DONE`; no automatic retry.

Report preparation: `python -m scripts.production_parity_report --run <run>
--output <new.json>` checks all 30 grade/verify records, context hashes, replay
fields and the final summary; counts order, membership and context differences.
It retains manifest/input hashes and refuses overwrites. Run from a separate
checkout: do not change the active snapshot's source fingerprint. Red: 11 failed;
Windows and Mac: **11 passed**, Ruff clean. No new measurement published.

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
