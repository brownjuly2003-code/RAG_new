# D.5 pgvector cold start and memory — measured slice

**Verdict:** On 2026-09-25, seven new-process trials per arm ran on one Mac with
D.1's pinned inputs. Median time to first fused result was 85.7 ms for
PostgreSQL + pgvector against 1494.7 ms for Chroma + BM25. Client resident set
after the workload was 68,644,864 against 310,738,944 bytes. The PostgreSQL
backend held 98,246,656 bytes of its own, recorded apart and never added.
PostgreSQL answered identically in every trial. Chroma's fused answers changed
between processes in 13 of the 115 cases, with each process re-inserting 589
write-ahead log records.
No runtime default changed; `RAG_GRAPH_RETRIEVAL` stays `off`. The storage
decision is to retain the current backend, as the decision record
`docs/adr/0007-pgvector-spike.md` explains.

## Numbers

Medians of the recorded trials are below. The first HNSW query followed the first
fused result and is outside time to first result. Resident sets are bytes and belong
to the named process.

| Observation | PostgreSQL + pgvector | Chroma + BM25 |
|---|---:|---:|
| Driver import, ms | 12.5 | 417.5 |
| Open, ms | 22.7 | 61.2 |
| Restore, ms | — | 703.2 |
| BM25 index, ms | — | 297.9 |
| First fused query, ms | 50.5 | 17.3 |
| First HNSW query, ms | 6.9 | — |
| Time to first fused result, ms (range) | 85.7 (84.8–90.0) | 1494.7 (1492.7–1998.2) |
| Fused workload, ms | 3568.8 | 1923.1 |
| HNSW workload, ms | 352.5 | — |
| Client resident set before timed steps, bytes | 58,163,200 | 57,131,008 |
| Client resident set after workload, bytes | 68,644,864 | 310,738,944 |
| Client peak resident set, bytes | 68,726,784 | 311,472,128 |
| Backend resident set, bytes; never added | 98,246,656 | — |
| Process wall time, ms | 4510.4 | 4562.7 |

## Answers across restarts

PostgreSQL fused and HNSW rankings were identical in all seven trials. Its fused
rankings equalled D.1's in 115 of 115 cases. Chroma fused rankings differed from
trial 0 as follows:

| Trial | Changed cases | Case indexes |
|---:|---:|---|
| 1 | 4 | 28, 51, 74, 93 |
| 2 | 7 | 4, 5, 12, 23, 28, 59, 74 |
| 3 | 6 | 7, 12, 23, 28, 72, 74 |
| 4 | 6 | 4, 12, 23, 28, 59, 74 |
| 5 | 4 | 12, 23, 28, 59 |
| 6 | 11 | 4, 5, 7, 12, 23, 28, 52, 59, 72, 73, 93 |

There were 13 distinct changed cases. The log's highest sequence id was 5589;
the vector segment persisted through 5000. Every new process re-inserted the
remaining 589 records from the write-ahead log into its in-memory index.

Chroma fused rankings equalled D.1's in 91 of 115 cases. D.1's harness built an
in-memory collection with `chromadb.EphemeralClient()` in one process. Its graph
never went through a reopen. This report does not establish the cause of the
cross-check mismatch.

The first run at `4b57562` stopped at the original Chroma stability gate. It
printed no timing or memory value and wrote no report: it is NOT_EVIDENCE.
The spec's amendment 1 in `docs/specs/pgvector-cold-start.md` records the
diagnostic. It was written after the first run and before this measured run;
PostgreSQL's ranking gate stayed in place.

## Setup

Chroma built the persisted collection in 11009.7 ms; its directory occupied
79,373,948 bytes. PostgreSQL setup took 8837.1 ms and its scratch database
occupied 95,068,687 bytes. The HNSW index `spike_chunks_embedding_idx` occupied
45,793,280 bytes and the `spike_chunks` TOAST data 30,998,528 bytes.

The server settings were `shared_buffers`: `128MB`, `work_mem`: `4MB`,
`maintenance_work_mem`: `64MB` and `effective_cache_size`: `4GB`. The host had
8,589,934,592 bytes of physical memory and 4 CPUs. Its recorded load averages
were `1.22998046875, 1.7841796875, 1.58154296875` before and
`1.458984375, 1.72314453125, 1.572265625` after. Swap usage was
`total = 1024.00M  used = 225.25M  free = 798.75M  (encrypted)` both before and
after.

## Provenance

- The run used a clean clone of `master` on `deproject-mac` at
  `ccec9ca5c13302016cd52abe478b6fd6abaa16b4`.
- Recorded source blob digests at that commit:
  - `scripts/pgvector_cold_start_run.py`:
    `bc8c5d182259c9a5b3c085dc3231fe02696417745ad2dc4dc9775e098ad007fb`;
  - `scripts/pgvector_cold_start.py`:
    `c07a1617aa89ff90dd38eaa701cfc7a27fe1e70f2b49d6d3e215f9fbffa8ca79`;
  - `scripts/pgvector_spike.py`:
    `474a64d9c51b125905b8d9a29e0fd01260fea10cbe83c46c2e628e3d366ab941`;
  - `scripts/pgvector_spike_db.py`:
    `5536b0d41ac2e8e825cc81379dc64b4701f4cd4abb98272eb4f8f15039203dbd`;
  - `scripts/pgvector_ann.py`:
    `64899026abd4393d82a0dbaa12b359a23526a62dce1f3e76060aed74134d6235`;
  - `vectordb/manager.py`:
    `496186fb3c9a1b11f9a987601b75f2f1bfc10f135b84a2fdc0bb17d297e07d01`;
  - `vectordb/_base_manager.py`:
    `dda045991a9724cbf0d916e901cea420294864b566f010aab8a01851961a54a1`.
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
- Versions: Python `3.11.15` on `darwin`; PostgreSQL
  `PostgreSQL 16.15 (Homebrew) on x86_64-apple-darwin22.6.0, compiled by Apple clang version 14.0.3 (clang-1403.0.22.14.1), 64-bit`;
  pgvector `0.8.1`; numpy `1.26.4`; chromadb `1.5.9`; rank-bm25 `0.2.2`;
  psycopg2-binary `2.9.12`.
- [Raw report](../../evaluation/d5-pgvector-cold-start.json): `142937` bytes,
  SHA-256 `a9f0277cdca82fabe6f62bf3eeb929d3bfd3db510984edaba41366719b8ec7d4`.

The command used D.1's `/Users/julia/RAG_Support_Assistant/.venv/bin/python` and
an output path outside the clone:

```sh
python -m scripts.pgvector_cold_start_run \
  --vectors /Users/julia/RAG_new_gr3_results_32de532/inputs/chunks.npz \
  --queries /Users/julia/d1-queries.npy \
  --output "<path outside the clone>"
```

The administrative URL came from `RESOLUTION_ADMIN_DATABASE_URL` in the Mac
secrets file and is recorded nowhere. The scratch database
`rag_spike_d5_d22162296c349788` was created and dropped during the run.

## Verification

`tests/test_pgvector_cold_start_artifact.py` pins the report bytes, D.1 inputs
and source blobs, replays summaries, ranking digests and the D.1 cross-check,
and checks the publication's numbers. This is an arithmetic and provenance
check, not another database measurement.

The D.5 unit tests passed in the clean clone before measurement. The database
acceptance test, `tests/test_pgvector_cold_start_db.py`, skips without
`RESOLUTION_ADMIN_DATABASE_URL`. It ran green on the Mac with that variable set,
on its synthetic fixture, during T-45's checks on 2026-09-25.

## Evidentiary limits

- This was one run of seven trials per arm on one host, without replication.
- Neither the operating system's file cache nor the PostgreSQL server was
  controlled; the report marks both not controlled. The PostgreSQL arm opened
  a new connection to a running server shared with other databases, not a
  server cold boot.
- Query vectors were precomputed. Neither arm loaded the embedding model or
  reranker that a production process also loads. These are storage and lexical
  cold starts, not endpoint cold starts.
- Resident sets are macOS `ps` values and `ru_maxrss`. A backend's resident set
  counts shared buffers that every backend shares, so it is never added to a
  client's.
- Chroma's start re-inserts the write-ahead log tail. Its length depends on
  corpus size and ingestion batching; another corpus leaves another tail.
- Each arm's trial 0 was its first process after setup and its slowest by time
  to first result. No trial was discarded.
- No retrieval quality was measured. D.1 and D.3 hold the quality numbers.
- Amendment 1 changed the Chroma gate after a run that printed no number.
  The arm and every other part of the protocol stayed as registered.
- The report hash detects mutation; it does not prove how the bytes were made.
  Code identity rests on the clean clone and source blob digests.

## Decision

Retain the current retrieval backend. The decision record
`docs/adr/0007-pgvector-spike.md` names what would reopen the decision.
