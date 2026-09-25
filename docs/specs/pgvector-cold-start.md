# Capability: pgvector-cold-start

Phase D.5 measures the cold start and the memory of the two retrieval storage arms that
D.1 compared, on one host and D.1's pinned inputs, before any migration decision
(ADR 0007, "Next bounded Phase D experiment"). The Chroma + BM25 arm reopens a persisted
collection and rebuilds its lexical index the way production does after a process
restart. The PostgreSQL + pgvector arm opens a new connection to a database loaded by
D.1's loader. The runner is `scripts/pgvector_cold_start_run.py`; the trial process, the
summaries and the report builder live in `scripts/pgvector_cold_start.py`. D.5 computes
no retrieval quality metric and changes no D.1–D.4 number or artifact and no product
default; `RAG_GRAPH_RETRIEVAL` stays `off`. This file was written before the first run
and fixes its protocol. Amendment 1, under "every trial answers the same", was written
after the first run stopped at that gate and before any other run.

## Requirement: the inputs are D.1's, pinned

The runner SHALL read the tracked archive `evaluation/gr1b-4436d61-graph-chunks.json.gz`,
a vectors file, a query vectors file and the tracked case files
`evaluation/curated_cases_aircargo.jsonl` then
`evaluation/curated_cases_aircargo_gr_multihop.jsonl`. It SHALL require 5589 chunks, 115
cases with unique `case_id`, vectors of shape (5589, 1024) and query vectors of shape
(115, 1024), all finite, the vectors file's `embedding_model` equal to `BAAI/bge-m3`, and
its `chunk_text_digest` equal to the digest D.1 computes over the archive's
`page_content` values: SHA-256 over each text's UTF-8 length as 8 big-endian bytes
followed by its bytes. The SHA-256 of the vectors file, the query vectors file, each case
file and the archive's decompressed JSON SHALL equal the digest D.1 recorded for that
input in `input_sha256` of `evaluation/d1-pgvector-prererank.json`, where the
decompressed JSON is recorded as `ab_phase2_G2_graph_chunks.json`. The report SHALL
record the SHA-256 of every input file, of the archive's decompressed JSON and of the D.1
report. Every check SHALL pass before the runner creates a database, a directory or a
process.

### Scenario: an input D.1 did not use

- **GIVEN** a query vectors file whose SHA-256 differs from the one D.1 recorded
- **WHEN** the runner starts
- **THEN** it raises `ValueError` naming the file, before any side effect

### Scenario: a text digest mismatch

- **GIVEN** a vectors file whose `chunk_text_digest` differs from the archive's text digest
- **WHEN** the runner starts
- **THEN** it raises `ValueError` before it creates a database, a directory or a process

### Scenario: a wrong case count

- **GIVEN** case files holding 114 cases
- **WHEN** the runner starts
- **THEN** it raises `ValueError` naming both counts, before any side effect

## Requirement: every trial is a new process

Each trial SHALL run in a new Python process, started with the runner's interpreter,
that runs one arm and prints one JSON object as its last line of output. Before its first
timed step the process SHALL load the query vectors and case texts, import
`vectordb.manager` and `vectordb._base_manager`, which production imports whatever the
backend, and record its resident set size. Precomputed query vectors stand in for query
encoding: neither arm loads an embedding model or a reranker. Every process SHALL run
with `ANONYMIZED_TELEMETRY=False` in its environment. The administrative URL SHALL reach
a process only through its environment and only for the PostgreSQL arm; no process
argument SHALL hold any part of it.

### Scenario: the URL stays out of process arguments

- **GIVEN** a run whose processes are started through a recording stand-in
- **WHEN** the runner starts the trials of both arms
- **THEN** no recorded argument holds the URL or its password, and only PostgreSQL trials
  receive it, in their environment

## Requirement: the Chroma + BM25 arm reopens a persisted collection as production does

Before the first trial, a separate process SHALL build one persisted collection in a new
directory and exit. The collection holds every archive chunk under id `str(i)` with its
vector, its `page_content` as the document and its metadata with `chunk_index` set to
`i`, as production ingestion stamps it. It uses D.1's cosine space and no embedding
function and is added in batches of 500. The build time and the directory's size SHALL
be recorded. After its last batch the build process SHALL also record, from the
collection's `chroma.sqlite3`, the highest sequence id in the write-ahead log table
`embeddings_queue` and the sequence id that the vector segment, the only `segments` row
whose scope is `VECTOR`, has persisted in `max_seq_id`: 0 when that table holds no row
for the segment, which then has persisted nothing. The build SHALL fail when the log is
empty, when there is not exactly one vector segment or when a sequence id is not an
integer. The difference of the two is the number of log records that a new process
re-inserts into its in-memory index when it opens the collection (amendment 1). Each
Chroma trial SHALL time these steps in order:

1. `import chromadb`;
2. `chromadb.PersistentClient(path=...)` and `get_collection(name=...)`, the two calls
   `langchain_chroma` makes when it opens an existing collection;
3. the restore, `vectordb.manager._restore_chunks_from_store` on an object whose
   `_collection` is that collection;
4. the lexical index, `HybridRetriever` constructed over the restored chunks, which
   builds `BM25Okapi` over `_tokenize_for_bm25` of every chunk;
5. the first query, `chroma_search` from `scripts/pgvector_spike.py` for case 0 with the
   BM25 index of step 4.

It SHALL then answer all 115 cases once with `chroma_search`. Outside the timed steps it
SHALL require the client's settings to report telemetry disabled and the restored texts,
in order, to have the archive's text digest.

### Scenario: a restore out of order

- **GIVEN** restored chunks whose texts, in order, do not have the archive's text digest
- **WHEN** a Chroma trial checks them
- **THEN** the trial fails, and the run writes no report

### Scenario: a vector segment that has persisted nothing

- **GIVEN** a collection store whose log's highest sequence id is 40 and whose
  `max_seq_id` table holds a row for the metadata segment only
- **WHEN** the build process reads it after its last batch
- **THEN** it records 40 for the log and 0 for the vector segment

## Requirement: the PostgreSQL + pgvector arm opens a new connection

Before the first trial, the runner SHALL load a new scratch database with `setup` from
`scripts/pgvector_spike_db.py`, D.1's loader, and close that connection. Each PostgreSQL
trial SHALL time these steps in order:

1. `import psycopg2`;
2. the connection to the scratch database and `SET ROLE` to its disposable role;
3. the first fused query, `pg_search` from `scripts/pgvector_spike.py` for case 0;
4. the first HNSW query, `ann_search` from `scripts/pgvector_ann.py` for case 0 with 20
   results, the index forced and `ef_search` 100, as D.2 timed it.

It SHALL then answer all 115 cases once with `pg_search` and once with `ann_search`,
committing after every query as D.1 and D.2 did, and record the resident set size of its
server backend, found by `pg_backend_pid()`.

### Scenario: a commit after every query

- **GIVEN** a PostgreSQL trial run against a recording connection stand-in
- **WHEN** it answers the first queries and the workload
- **THEN** a commit follows every `pg_search` and every `ann_search` call, so no
  `SET LOCAL` of one query reaches the next, and the backend resident set is read for
  the process id that `pg_backend_pid()` returned

## Requirement: memory is recorded per process and never summed across the server

Every trial SHALL record in bytes its resident set size before its first timed step, its
resident set size after the workload and its peak resident set size (`ru_maxrss`, which
macOS reports in bytes). A PostgreSQL trial SHALL also record its backend's resident set
size after the workload. The run SHALL record once, before the first trial: the size of
the scratch database, of every table and index in its `public` schema and of the TOAST
data of `spike_chunks`; the server settings `shared_buffers`, `work_mem`,
`maintenance_work_mem` and `effective_cache_size`; and the host's physical memory and
CPU count. A backend's resident set counts the shared buffers it touched, which every
backend shares, so the report SHALL hold no field that adds a backend's resident set to a
client's.

### Scenario: resident set parsing

- **GIVEN** `ps -o rss=` output of `  51200` for a process
- **WHEN** the trial reads it
- **THEN** it records 52428800 bytes, and empty output fails the trial

## Requirement: the protocol is fixed before the run

The runner SHALL run seven trials per arm, a constant of the runner. Trial `i` starts the
Chroma arm first when `i` is even and the PostgreSQL arm first when `i` is odd. No trial is
discarded as warm-up: the report SHALL hold every trial's raw values and, for each arm and
recorded quantity, the minimum, median and maximum over its seven trials. The headline
figures are, per arm, the medians of the time to first result, from the start of the
first timed step to the end of the first fused query, and of the resident set size after
the workload. The runner SHALL neither purge the operating system's file cache nor
restart the PostgreSQL server, which other databases share, and the report SHALL record
both as not controlled, with the host's load average and swap usage before the first
trial and after the last.

### Scenario: order

- **GIVEN** seven trials per arm
- **WHEN** the runner schedules them
- **THEN** trials 0, 2, 4 and 6 start with the Chroma arm, and trials 1, 3 and 5 with the
  PostgreSQL arm

### Scenario: summaries

- **GIVEN** a quantity whose seven trial values are 7, 1, 6, 2, 5, 3 and 4
- **WHEN** the report is built
- **THEN** its summary is minimum 1, median 4 and maximum 7

## Requirement: every trial answers the same

For each PostgreSQL query path (fused and HNSW), every trial SHALL return the same 115
rankings; otherwise the run fails and writes no report. The Chroma fused path is compared
but not gated: the report SHALL record, for each trial from 1 to 6, the indexes of the
cases whose Chroma fused ranking differs from trial 0's, in ascending order, and the
number of distinct cases that differ in at least one trial. The report SHALL hold trial
0's rankings for each path and, as a diagnostic rather than a gate, record for each arm
whether its fused rankings equal those D.1 published in `runs[0]` of
`evaluation/d1-pgvector-prererank.json`, with the number of cases that match.

Amendment 1, 2026-09-25. As first written, this requirement gated the Chroma fused path
too. The first run, at commit `4b57562` on deproject-mac, stopped at that gate on the
Chroma fused path. It printed no timing or memory value, wrote no report and removed its
database, role and directory. A diagnostic outside the protocol, which is not evidence,
rebuilt the collection from the same vectors in the same batches and opened it in new
processes. Its persisted HNSW index covered sequence ids up to 5000 of 5589; the other 589
records stayed in Chroma's write-ahead log, and each new process re-inserted them into its
in-memory graph. Each later process's top-20 nearest-neighbour answers differed from the
first process's in 3 to 9 of the 115 cases, while a repeated query in the same process did
not change. Single-threaded insertion (`hnsw:num_threads` 1) did not remove the variation.
Raising the sync threshold and batch size to 5589, which are not production's settings,
persisted the whole index, and four processes then answered alike. Production's own
ingestion batching, upserts in batches of the client's maximum (5461 on this host) as
`langchain_chroma` does, left 128 records in the log, and 1 or 2 answers still differed.
With Chroma's default settings the variation is a property of the arm, not of the harness.
The arm is kept as specified above, and its variation is a recorded result. The PostgreSQL
gate is unchanged. The report's schema version becomes `d5-pgvector-cold-start-v2`.

### Scenario: an unstable PostgreSQL ranking

- **GIVEN** a trial whose PostgreSQL fused or HNSW ranking for one case differs from
  trial 0's
- **WHEN** the runner collects the trials
- **THEN** it raises, cleans up, and writes no report

### Scenario: a varying Chroma ranking

- **GIVEN** trials whose Chroma fused ranking differs from trial 0's for case 3 in trial
  2 and for cases 5 and 3 in trial 4, and PostgreSQL rankings that never differ
- **WHEN** the report is built
- **THEN** it records cases [3] for trial 2, [3, 5] for trial 4 and [] for trials 1, 3,
  5 and 6, and 2 distinct varying cases

## Requirement: scratch state is new, local and removed

The runner SHALL read the administrative URL from `RESOLUTION_ADMIN_DATABASE_URL`, accept
it only with a PostgreSQL driver on `localhost` or `127.0.0.1`, port 55432, and normalize
its driver in memory. It SHALL name the scratch database and its role `rag_spike_d5_`
followed by 16 lowercase hex digits drawn in the run, check that neither exists, and then
create both through `setup`, which fails if either exists. It SHALL create the
collection directory, under the same name in the system temporary directory, with a call
that fails if it exists. After the trials, and also when setup or a trial fails, it SHALL
drop only that database and role and remove only that directory, retrying the drop for
at most 30 seconds while the server reports the database in use (SQLSTATE `55006`), and
record whether each was removed. Neither the URL nor its password SHALL appear in output,
exception messages, process arguments or the report.

### Scenario: a failed trial

- **GIVEN** a trial process that exits non-zero
- **WHEN** the runner handles it
- **THEN** it drops the scratch database and role, removes the collection directory, and
  raises an error that names the arm and the trial but holds no part of the URL

### Scenario: a non-local URL

- **GIVEN** `RESOLUTION_ADMIN_DATABASE_URL` naming host `db.example.com`
- **WHEN** the runner starts
- **THEN** it raises `ValueError` before any connection, and the message holds no part of
  the URL

## Requirement: the report is written once, with provenance

The runner SHALL refuse an existing output path and a dirty tracked worktree before any
side effect, and write the report with exclusive creation. The report SHALL record the
schema version `d5-pgvector-cold-start-v2`, the full code commit, the input and source
SHA-256 digests, the versions of numpy, chromadb, rank-bm25 and psycopg2-binary, the
Python version, the platform, the PostgreSQL and pgvector versions and the protocol
constants, which name the gated ranking paths. Its sources SHALL include the runner, its
helper module, `scripts/pgvector_spike.py`, `scripts/pgvector_spike_db.py`,
`scripts/pgvector_ann.py`, `vectordb/manager.py` and `vectordb/_base_manager.py`. The
status SHALL be `measured` only when every trial completed and the database, the role and
the directory were all removed, and `cleanup_failed` otherwise, which is not evidence.

### Scenario: an existing output

- **GIVEN** an output path that already exists
- **WHEN** the runner starts
- **THEN** it raises before it creates a database, a directory or a process

### Scenario: a cleanup failure

- **GIVEN** a run whose trials completed but whose scratch database could not be dropped
- **WHEN** the report is built
- **THEN** its status is `cleanup_failed`, and it names the database but not the URL

## Requirement: the published report is pinned and quoted exactly

A committed D.5 report SHALL be guarded by a test that pins the report's SHA-256 and the
code commit it was built at, requires each recorded source digest to be the SHA-256 of
that file's blob at the code commit, and requires each recorded input digest to equal the
digest D.1 recorded for that input. From the report alone, the test SHALL recompute every
summary with the committed `summarize`, the digest of each trial-0 ranking with
`rankings_sha256` and the D.1 cross-check with `compare_d1`, and require the recorded
values. It SHALL require every trial's PostgreSQL ranking digests to equal trial 0's, and
a Chroma trial's digest to equal trial 0's exactly when the report records no differing
case for that trial. The evidence capsule, its `EVIDENCE_INDEX.md` row and the D.5
section of ADR 0007 SHALL quote no number that the report does not hold outside its
rankings, apart from the number of cases each trial changed and the log tail, the
difference of the two recorded sequence ids.

### Scenario: a mutated report

- **GIVEN** `evaluation/d5-pgvector-cold-start.json` altered by any byte
- **WHEN** the artifact test runs
- **THEN** it fails on the pinned SHA-256

### Scenario: a number the report does not hold

- **GIVEN** a number written in the capsule outside code spans
- **WHEN** the artifact test runs
- **THEN** it fails unless that number is a JSON number of the report outside its
  rankings (not a boolean), the number of cases a trial changed, or the log tail
