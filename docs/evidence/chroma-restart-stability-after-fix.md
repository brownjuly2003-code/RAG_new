# Chroma restart stability after the persistence fix — measured slice

**Verdict:** On `2026-09-25`, at `534612e`, one build process and seven
new-process trials ran on one Mac. The vector segment persisted through the
write-ahead log's highest sequence id, 5589, leaving 0 records in the tail.
All seven trials answered all 115 cases exactly as the build did, on the
vector path and on the ordered RRF candidate path. [The first run](chroma-restart-stability.md)
found a differing candidate set after a restart and an unpersisted tail.
This slice changes no runtime default.

## Question and protocol

The run followed the same [protocol](../specs/chroma-restart-stability.md). Under
its amendment 1, the build process makes production's new write call from
[chroma-index-persistence](../specs/chroma-index-persistence.md).
Everything else is unchanged: D.1's pinned inputs, precomputed vectors in
place of the embedding model, the reranker off, the whole ordered RRF
candidate list, and an in-process repeat gate.

## Build

The embedding adapter received calls of 5461 and 128 documents. The build
counted and restored 5589 chunks. The log's highest sequence id and the
vector segment's persisted sequence id were both 5589, leaving a tail of 0.
Chroma reported HNSW space `l2`, ef_construction 100, ef_search 100,
max_neighbors 16, resize_factor 1.2 and sync_threshold 1. Production
settings were retrieval_top_k 20, rrf_k 60 and rrf_doc_key_chars 200.

## Answers across restarts

| Path | Trials differing from build | Distinct cases |
|---|---:|---:|
| vector (ordered) | none | 0 |
| candidates (ordered) | none | 0 |
| candidate set | none | 0 |

Trial 0's answers equal the build's, and no later trial recorded a difference.

## What it decides and its limits

This slice changes no runtime default. `534612e` changed how new collections
are written. A collection built before that commit keeps its unpersisted tail
until it is rebuilt. Per the protocol, with no case differing, the result
stands for this corpus, this host and these versions only. This is one run
of seven trials; the reranker's own scoring was not part of this measurement.
The NOT_EVIDENCE probes run before T-51 are not evidence and are not quoted.

## Provenance

- [Raw report](../../evaluation/chroma-restart-stability-after-fix.json):
  `217303` bytes; SHA-256
  `b3819a8d577f9f1f917b3b07e7bc9d413a1157e86ed1f1ccc8a6fceda3f897b3`.
- The clean measurement clone used code commit
  `534612eda228d90b2c5c4f2e92f432d738adecdf`.
- Runner command: the ML venv's Python invoked
  `scripts/chroma_restart_stability_run.py` with `--vectors`, `--queries` and
  `--output`; the recorded Python version is `3.11.15`.
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
    `1c8f8edca7a7d28c0a05ad20390029c67aac778d56d3047eeb67acf05e3bd2ba`;
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
    `cd47cd4f88d3fe43530171caa55cc266731585435681bdf9fafd3d8c8e16a696`;
  - `config/settings.py`:
    `3d9dbdbfe9bfb4b6f2cee7ff9200f2e1e92288bcdd4e154c9bf37edc355ecb75`.
- Versions: Python `3.11.15` on `darwin`; numpy `1.26.4`, chromadb
  `1.5.9`, langchain-chroma `1.1.0`, langchain-core `1.4.0` and
  rank-bm25 `0.2.2`.
- Host `iMac18,3`: 4 CPUs; `hw.memsize` `8589934592`.
- The run started at `2026-09-25T20:47:20.267328Z` and ended at
  `2026-09-25T20:48:32.660006Z`.

## Verification

`tests/test_chroma_restart_stability_after_fix_artifact.py` pins the report
bytes, inputs and source blobs, replays the comparisons, and guards this
capsule's and the index row's numbers. It is an offline check of the published
report, not another measurement. `tests/test_chroma_restart_e2e.py` is the
end-to-end proof of the fix.
