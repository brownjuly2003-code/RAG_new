# D.3 pgvector final-rerank comparison — measured slice

**Verdict:** On 2026-09-21, one offline CPU pass of
`BAAI/bge-reranker-v2-m3` improved the saved PostgreSQL candidate arm more than
the saved Chroma + BM25 arm, but did not reverse their ordering. Over all 115
agent-authored cases, post-rerank keyword context precision / recall is
0.460985 / 0.847826 for PostgreSQL and 0.472891 / 0.852174 for Chroma + BM25.
This bounded result does not justify a backend migration or change a runtime
default. Phase D remains open.

## Numbers

The run reranks the byte-pinned D.1 candidate lists; it performs no retrieval
or embedding work.

| Bucket / saved arm | Pre-rerank precision | Rerank precision | Delta | Pre-rerank recall | Rerank recall | Delta |
|---|---:|---:|---:|---:|---:|---:|
| 100 phase-C / PostgreSQL | 0.456188 | 0.495865 | +0.039678 | 0.840000 | 0.905000 | +0.065000 |
| 100 phase-C / Chroma + BM25 | 0.501882 | 0.505916 | +0.004034 | 0.830000 | 0.905000 | +0.075000 |
| 15 multi-hop/aggregation / PostgreSQL | 0.204128 | 0.228451 | +0.024323 | 0.422222 | 0.466667 | +0.044444 |
| 15 multi-hop/aggregation / Chroma + BM25 | 0.264656 | 0.252723 | -0.011933 | 0.477778 | 0.500000 | +0.022222 |

On the 100-case bucket, reranking narrows the precision gap from 0.045694 to
0.010050; it does not remove it. Every full candidate order changed in both
arms. The top-five set changed for 112/115 PostgreSQL cases and 114/115
Chroma + BM25 cases; mean rank-order correlation with D.1 is 0.4617 and
0.3631 respectively. This rules out a silent identity ordering in the stored
artifact, but scores were not stored, so it does not prove that the model
produced those orders.

| Saved arm, all 115 | Candidate depth | Rerank p50 | Rerank p95 |
|---|---:|---:|---:|
| PostgreSQL | 20 each | 14115.76 ms | 21885.67 ms |
| Chroma + BM25 | 23–40; mean 34.85 | 28418.78 ms | 40548.97 ms |

These timings are one wall-time observation around each `predict` call, in
fixed arm order. The arms do not have equal candidate depth, so the table is
not a backend latency comparison.

## Provenance

- Clean detached source clone at
  `1e64ee3a3b4913f133d46b441a178ddc47039b69`; the report records `1e64ee3`
  plus SHA-256 for the five imported source files.
- [Raw report](../../evaluation/d3-pgvector-rerank.json), 268015 bytes,
  SHA-256 `4e8450b2d3a59543e6799f9395cb999fb64ca60ee64a197e4609f4592ddc4345`.
- D.1 report SHA-256
  `4c53f805964992fba2f785822a01623f20724b619bf9df6779867918bd5a48c7`;
  corpus JSON `5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`;
  case files `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`
  and `0949d7563983b96500074e61f10274b28cb9341612206e02733a59b5c7968f5f`.
- `deproject-mac`, Intel i5-7500, 8 GiB, macOS 13.7.8; Python 3.11.15,
  sentence-transformers 2.7.0 and torch 2.2.2; `RAG_DEVICE=cpu` and
  `HF_HUB_OFFLINE=1`.
- Model name `BAAI/bge-reranker-v2-m3`. Immediately after the run, the offline
  cache's `main` ref was
  `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; that revision is not stored or
  verified by the report itself.
- One model load, then exactly 230 saved lists in fixed order: 115 PostgreSQL,
  then 115 Chroma + BM25. The report stores every resulting order, every
  per-list latency and all global/bucket metric rows.

## Verification

`tests/test_pgvector_rerank_artifact.py` pins the entire report SHA, tracked
inputs and source bytes; checks exact buckets, permutations, changed-order
counts, device and versions; and recomputes all top-five rows, means and
latency percentiles. It uses no model, network, database, retrieval or
embedding work. The D.3 core and file driver have separate unit tests.

## Evidentiary limits

- Both datasets are agent-authored and unapproved. The metrics are keyword
  proxies, not endpoint quality, and cannot close the Phase-C 0.63 gate.
- This is one unreplicated top-five run over one corpus. There is no confidence
  interval or significance test.
- The report stores orders, not reranker scores or invocation counters. It
  cannot independently prove model-origin, score monotonicity, input pairing
  or one-call accounting.
- Weight/tokenizer hashes, revision, `max_length`, truncation, padding, batch
  size, dtype, thread count and seed are absent from the report. The observed
  cache ref above is operator provenance, not artifact-bound replay data.
- Metric replay calls the same deterministic `score_rows` implementation. It
  proves byte integrity and internal arithmetic, not independent semantics.
- Latency excludes model load, retrieval, embedding, scoring, serialization
  and total-host RAM. It is not comparable across hosts or runs; fixed arm
  order and unequal candidate depth also prevent a clean cross-arm claim.
- The report hash closes mutation detection, but does not prove how the bytes
  were generated. Code identity is supported by the clean-clone preflight and
  source hashes, not independently established inside the JSON.

## Remaining Phase D

Diagnose the D.2 recall outlier, complete actual graph/NetworkX and evidence
join parity, and measure cold-start/host RAM before any migration decision.
See [ADR 0007](../adr/0007-pgvector-spike.md).
