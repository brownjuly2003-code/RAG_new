# Production parity on H cases

## What was compared

The staged production pipeline was replayed through `ConversationSession.ask` (session replay), using saved provider replies.
The API's Chroma search was compared with the harness's exact-cosine search on the same pinned embeddings: vector results, pool and reranked lists, effective query and post-grading context hash.

Cases: 30, from H — the curated set `evaluation/curated_cases_aircargo.jsonl` at the run commit — all of tenant `aircargo`. Selection: `first 30 ascending sha256(case_id)`.
The case labels are not used by the comparison.

## Measurement

session_replay_matches: 60 (both arms of each selected case). In each arm the session, replaying the saved replies, gave the staged result in every compared field; a mismatch stops the run.

Cases whose two arms differ in the query stage, per field: query_effective: 0. query_transform: 0. query_transform_hash: 0.

Cases whose two arms differ in a list, per field:

| field | order | membership |
|---|---:|---:|
| `vector` | 8 | 8 |
| `pool` | 8 | 8 |
| `ranked` | 1 | 1 |

Order counts cases whose lists differ, including membership changes. Membership counts cases whose sets of ids differ.

context_hash_matches: 29 of 30. Divergent cases: 8. The divergences are published, not fixed.

| case | differing fields |
|---|---|
| `aircargo-matliab-check` | `vector`, `pool` |
| `aircargo-oversized-permit-route` | `vector`, `pool` |
| `aircargo-pdp-uncertain` | `vector`, `pool` |
| `aircargo-waybill-escalation-events` | `vector`, `pool` |
| `aircargo-road-driver-pdn` | `vector`, `pool`, `ranked`, `sent_context_sha256` |
| `aircargo-data-retention-required-fields` | `vector`, `pool` |
| `aircargo-cross-border-pdn-required-fields` | `vector`, `pool` |
| `aircargo-driver-dangerous-goods-refusal` | `vector`, `pool` |

Only `aircargo-road-driver-pdn` differs in the reranked list and in the sent context.

## Recorded outcomes

The cache summary counts the saved provider replies of the run:

- cache_records: 324.
- records_by_kind.embedding: 30.
- records_by_kind.llm: 256.
- records_by_kind.rerank: 38.
- llm_outcomes.response: 243.
- llm_outcomes.structured_output_invalid: 13.
- integrity_mismatches: 0.

A `structured_output_invalid` record is a completed reply that fails schema validation; it holds the error type, message and raw reply under the response integrity check. Production's own fallback runs identically in both arms and in the session replay. The cache summary does not identify the pipeline steps of these outcomes.

## Limits and baseline

- latency_evidence: false.
- Report limit: Saved staged session replay; no live HTTP latency, answers or quality verdict.
- Manifest limit: staged deterministic replay; no live API latency or generated answers.
- There are no answers and no quality verdict. This is one run, no repeat, on the selected cases of one tenant.
- Stage records (`grade/`, `verify/`) and the cache stay on the Mac. The stage records' SHA-256 values are listed under `input_sha256` in the report; the cache summary records its integrity check.
- Index receipt evidence_status: `preparation` is the status the index build recorded for itself.

The baseline collector runs the production Chroma arm, so its contexts are the production ones. This comparison records how often the exact-cosine harness would have seen a different context: 1 of 30 here.

## Provenance

The code SHA below is commit `c729b23` of this repository. The recorded `source_sha256` equals the digest recomputed from that commit's tree, and `dataset_sha256` equals the dataset file at that commit; the artifact test repeats both checks. The manifest records the Mac snapshot in its corpus path and the host runtime in `runtime`; it does not record a separate hostname.
The full config, runtime package versions and embedder manifest are retained below.

| field | recorded value |
|---|---|
| code_sha | `"c729b2360e1074ac4e6c1ca641a8d20c6b826d8f"` |
| source_sha256 | `"7bdc95b5406110216af31b4434cae5e906bdc59b348f01bb2ad9dab8ea7a78c4"` |
| dataset_sha256 | `"3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"` |
| corpus_sha256 | `"2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12"` |
| chunk_count | `5589` |
| index_receipt_sha256 | `"52f733a08d84fe238cbbc1f9ea6080db58c4f8d758a31a257c350278d47fa51c"` |
| checkpoint_sha256 | `"3903187e56dd4d8accf642f612910c6ca2082d1e7e55b7d67cd072ce0978fb5a"` |
| index build code_sha | `"72fbd722c62722aede7c870b6cf0dfa71227a4d2"` |
| embedder_manifest | `{"backend": "local", "dimension": 1024, "document_prompt": "", "model_id": "BAAI/bge-m3", "normalize": true, "query_prompt": "", "revision": "5617a9f61b028005a4858fdac845db406aefb181", "revision_source": "hf_snapshot", "schema_version": 1}` |
| reranker | `{"model": "BAAI/bge-reranker-v2-m3", "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"}` |
| llm | `{"digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e", "model": "qwen2.5:7b", "options": "production provider defaults plus graph role kwargs", "provider": "OllamaProvider"}` |
| config | `{"agentic_mode": false, "ask_budget_sec": 0, "embedding_backend": "local", "graph_retrieval": "off", "hyde": false, "llm_max_calls_per_request": 24, "llm_max_input_tokens_per_request": 48000, "llm_max_output_tokens_per_request": 8000, "llm_max_total_tokens_per_request": 50000, "llm_role_params_json": "", "model_routing_enabled": false, "parent_expansion": true, "parent_expansion_max_chars": 3600, "parent_expansion_window": 2, "rag_device": "cpu", "rerank_batch": 8, "rerank_top_k": 5, "retrieval_strategy": "hybrid", "retrieval_top_k": 20, "rrf_doc_key_chars": 200, "rrf_k": 60}` |
| runtime | `{"packages": {"chromadb": "1.5.9", "langchain-ollama": "1.1.0", "langgraph": "1.2.2", "numpy": "1.26.4", "rank-bm25": "0.2.2", "sentence-transformers": "2.7.0", "torch": "2.2.2", "transformers": "4.44.2"}, "platform": "macOS-13.7.8-x86_64-i386-64bit", "python": "3.11.15"}` |
| host snapshot corpus path | `"/Users/julia/RAG_new_t66_parity_b0e67e609e77/evaluation/gr1b-4436d61-graph-chunks.json.gz"` |
| index path | `"/Users/julia/RAG_new_t65_embeddings_2851e3811508/.tmp/t65-index-72fbd72"` |
| checkpoint path | `"/Users/julia/RAG_new_t65_embeddings_2851e3811508/.tmp/t65-verified-embeddings.npz"` |

| published file | bytes | SHA-256 |
|---|---:|---|
| [manifest.json](../../reports/parity/c729b23/manifest.json) | 29571 | `98b58484408e419fab244a2c7d9b3c3f99f178a2c4a7e823f6178c13dbdf50a3` |
| [comparison.json](../../reports/parity/c729b23/comparison.json) | 856 | `6dcc2aff88277dc781ed0adbfdc5074fae516163fee91725cc603b6bc710ae47` |
| [report.json](../../reports/parity/c729b23/report.json) | 133985 | `3fd4080eda5a7c2a435eb7404632d463780f6e43949b3ed809ad4807a7f3db90` |
| [cache-outcomes.json](../../reports/parity/c729b23/cache-outcomes.json) | 309 | `00a1999b63488a39489fcd64fed2703fed22cae5a1426d87d02747364c508e99` |
| [cache_outcomes.py](../../reports/parity/c729b23/cache_outcomes.py) | 1790 | `94ef2b0eb8e1fe9ee4a8707b81e29f81885a6275de49ebbc943597cd1d529f4b` |

[Artifact test](../../tests/test_production_parity_artifact.py) checks the published numbers, the identities, the source and the dataset against the run commit, and the cache counter on synthetic records written by the runner's cache writer.
