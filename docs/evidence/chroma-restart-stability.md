# Chroma restart stability on production's write path — measured slice

**Verdict:** On `2026-09-25`, one build process and seven new-process trials
ran on one Mac. The build left 128 of 5589 records to the write-ahead log.
Six trials answered all 115 cases as the build did. Trial 5 changed case
93's last vector result and with it that case's candidate set. This slice
changes no runtime default; `RAG_GRAPH_RETRIEVAL` stays `off`.

**Rerun after the fix:** [chroma-restart-stability-after-fix](chroma-restart-stability-after-fix.md).

## Question and protocol

The [protocol](../specs/chroma-restart-stability.md) asks whether a
restarted process serves the same retrieval candidates as the process that
wrote the collection. The runner used production's exact write and reopen
calls, guarded by AST source pins, and D.1's pinned inputs with precomputed
vectors in place of the embedding model. It recorded the vector path and
ordered RRF candidate list with the reranker off, and required an in-process
repeat gate. [D.5's earlier observation](d5-pgvector-cold-start.md) asked
a related question under a different write path.

## Build

The embedding adapter received calls of 5461 and 128 documents, totaling
5589. The build counted and restored 5589 chunks. The log's highest sequence
id was 5589; the vector segment persisted through 5461, leaving an
unpersisted tail of 128 records in the write-ahead log. Chroma reported HNSW
space `l2`, ef_construction 100, ef_search 100, max_neighbors 16,
resize_factor 1.2 and sync_threshold 1000. Production settings were
retrieval_top_k 20, rrf_k 60 and rrf_doc_key_chars 200.

## Answers across restarts

| Path | Trials differing from build | Case | Distinct cases |
|---|---:|---:|---:|
| vector (ordered) | 5 | 93 | 1 |
| candidates (ordered) | 5 | 93 | 1 |
| candidate set | 5 | 93 | 1 |

In case 93, the vector lists agree except in their last place, the 20th:
the build has chunk `4575` and trial 5 has `5558`. The build item came from
the first embed call; the new item came from the second embed call, one of
the 128 records the log held. The candidate lists have equal length; their
sets differ only by this swap.

Measured against trial 0 instead of the build, only trial 5 differed:
case 93 on both the vector and candidate paths. Restarted processes
therefore differed among themselves as well as from the process that built
the collection.

## What this decides

A restarted production process can hand the reranker a different candidate
set than the ingesting process did. This slice changes no runtime default.
Changing production's write path or Chroma settings is a separate slice,
proven by an end-to-end test; the measurement is then rerun under the same
spec at the new commit.

## Evidentiary limits

- This is one host, one corpus and these versions. The tail depends on the
  corpus size and the client's batch size, 5461 on this host.
- One differing trial in seven is an observation, not a rate.
- The reranker did not run, so whether case 93's final answer would change
  is unknown.
- The new item came from the tail, but the measurement does not isolate why
  its re-insertion differed in one process.
- Precomputed vectors put the embedding model out of scope.
- The synthetic pre-flight was NOT_EVIDENCE and is not published.

## Provenance

- [Raw report](../../evaluation/chroma-restart-stability.json): `218560`
  bytes; SHA-256
  `590fc711e6ddf9db3cc61178bd37f6c3b6d62fadb25201a96e46e15f38ed304d`.
- The clean measurement clone used code commit
  `5e7037a985249d47dfb6b1ae88056d508b961b91`.
- Recorded input digests:
  - `gr1b-4436d61-graph-chunks.json.gz`:
    `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12`;
  - `chunks.npz`:
    `3fcfaf2803187b73d42f0d25256dfbea5b4997bce28d2c4ad47fbe0985b2ab33`;
  - `d1-queries.npy`:
    `7ff1a1224fa11e8d5579cefcbfde327253ae3c503c5e4676caec65cfebbde5c8`;
  - `curated_cases_aircargo.jsonl`:
    `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`;
  - `curated_cases_aircargo_gr_multihop.jsonl`:
    `0949d7563983b96500074e61f10274b28cb9341612206e02733a59b5c7968f5f`;
  - decompressed `ab_phase2_G2_graph_chunks.json`:
    `5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`;
  - `d1-pgvector-prererank.json`:
    `4c53f805964992fba2f785822a01623f20724b619bf9df6779867918bd5a48c7`.
- Recorded source blob digests at that commit:
  - `scripts/chroma_restart_stability.py`:
    `d0cad51b4425f4e9b780a0ec97d43e0c9257d54671a0d56d462554342c89f24e`;
  - `scripts/chroma_restart_stability_run.py`:
    `120dba7e61cada7844c7cdb84dffff86fc16bcb9580cda2a444c3c0ff0dd89ec`;
  - `scripts/pgvector_cold_start.py`:
    `c07a1617aa89ff90dd38eaa701cfc7a27fe1e70f2b49d6d3e215f9fbffa8ca79`;
  - `scripts/pgvector_cold_start_run.py`:
    `bc8c5d182259c9a5b3c085dc3231fe02696417745ad2dc4dc9775e098ad007fb`;
  - `vectordb/manager.py`:
    `496186fb3c9a1b11f9a987601b75f2f1bfc10f135b84a2fdc0bb17d297e07d01`;
  - `vectordb/_base_manager.py`:
    `dda045991a9724cbf0d916e901cea420294864b566f010aab8a01851961a54a1`;
  - `vectordb/index_staging.py`:
    `4c69c94aa5ac0ffd2e2825b9b13c466edb75333f340ce170eb422c4fb1ed042d`;
  - `config/settings.py`:
    `3d9dbdbfe9bfb4b6f2cee7ff9200f2e1e92288bcdd4e154c9bf37edc355ecb75`.
- Versions: Python `3.11.15` on `darwin`; numpy `1.26.4`, chromadb
  `1.5.9`, langchain-chroma `1.1.0`, langchain-core `1.4.0` and
  rank-bm25 `0.2.2`.
- Host `iMac18,3`: 4 CPUs; `hw.memsize` `8589934592`.
- The run started at `2026-09-25T18:16:08.988228Z` and ended at
  `2026-09-25T18:17:17.647678Z`.

## Verification

`tests/test_chroma_restart_stability_artifact.py` pins the report bytes,
inputs and source blobs, replays the comparisons, and guards this capsule's
and the index row's numbers. It is an offline check of the published report,
not another measurement.
