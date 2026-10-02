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

## Remaining T-65 work

1. Pin the Mac corpus/index, verified embedder manifest, model digests and runtime
   config. The Mac and local Ollama were reachable; no eligible baseline index
   has been established by this turn's checks.
2. Run the bounded real Chroma/exact comparison on 30 H cases and publish any
   divergence (T-62 acceptance boundary).
3. Collect H 100 + Hm 15 through the retrieval-only path, retain trace timings
   and exclude failed/ineligible runs. Record corpus SHA, code SHA and config.
4. Judge the new contexts, compute lexical/development metrics and the loss map,
   publish the capsule and evidence row. Keep `provisional_ruler` until D2 closes.

Human D2/D3 inputs remain pending. No retrieval default or quality gate changed.
