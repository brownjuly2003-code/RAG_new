# Capability: chroma-restart-stability

D.5 found that Chroma's fused answers changed between new processes that opened the
same persisted collection: in 13 of 115 cases, at least one of six later processes
answered differently from the first ([capsule](../evidence/d5-pgvector-cold-start.md)). D.5 built its collection in batches
of 500 with D.1's cosine space, which is not how production writes one. This measurement
asks the question for production's own write path and settings: after a process
restarts, does the same question get the same retrieval candidates? It builds one
collection with the call production makes, records the answers of the process that wrote
it, then reopens the collection in seven new processes the way production does after a
restart. The runner is `scripts/chroma_restart_stability_run.py`; the build and trial
processes, the comparison and the report builder live in
`scripts/chroma_restart_stability.py`. The measurement changes no product default and
no D.1–D.5 number or artifact; `RAG_GRAPH_RETRIEVAL` stays `off`. This file was written
before the first run and fixes its protocol.

## Requirement: the inputs are D.1's, pinned

The runner SHALL load its inputs with D.5's loader, `_load_inputs` in
`scripts/pgvector_cold_start_run.py`, called unchanged with the tracked archive
`evaluation/gr1b-4436d61-graph-chunks.json.gz`, a vectors file, a query vectors file,
the tracked case files `evaluation/curated_cases_aircargo.jsonl` then
`evaluation/curated_cases_aircargo_gr_multihop.jsonl`, and
`evaluation/d1-pgvector-prererank.json`. Every check of that loader SHALL pass before the
runner creates a directory or a process, and the report SHALL record the input digests
it returns.

### Scenario: an input D.1 did not use

- **GIVEN** a query vectors file whose SHA-256 differs from the one D.1 recorded
- **WHEN** the runner starts
- **THEN** it raises `ValueError` naming the file, before any side effect

## Requirement: precomputed vectors stand in for the embedding model

No process SHALL load an embedding model or a reranker. Each process SHALL serve vectors
through one adapter with production's embedding interface: `embed_documents(texts)`
returns, for each text, the row of the vectors file at that text's position in the
archive, and `embed_query(text)` returns the row of the query vectors file at that
query's position in the case files. A text or query the inputs do not hold SHALL raise
`KeyError`. The adapter SHALL record the length of every `embed_documents` call, in
order.

### Scenario: an unknown query

- **GIVEN** the adapter
- **WHEN** it is asked to embed a query that no case holds
- **THEN** it raises `KeyError`

## Requirement: the build process writes the collection as production does

Before the first trial, a separate process SHALL create one collection in a new directory
with production's write call, the one `build_staged_collection` in
`vectordb/index_staging.py` makes:
`langchain_chroma.Chroma.from_documents(documents=..., embedding=..., persist_directory=..., collection_name=...)`,
with no collection metadata, no collection configuration and no client settings, so
Chroma's defaults apply. The documents are the archive's chunks in archive order, each
with its `page_content` and its archive metadata plus `chunk_index` set to its position,
as `_build_vector_store_result` in `vectordb/manager.py` stamps it. A test SHALL fail if
the production call site passes any other keyword argument, so that this requirement
cannot silently stop describing production.

After the build the process SHALL record the build time, the lengths of the
`embed_documents` calls, the collection's count (which SHALL be 5589), the `hnsw` section
of the collection's configuration as Chroma reports it (null if it reports none), and,
from the collection's SQLite file, the highest write-ahead-log sequence id and the
sequence id up to which the vector segment is persisted, read as D.5's
`read_log_positions` reads them.

### Scenario: production passes a collection setting

- **GIVEN** a `build_staged_collection` whose `from_documents` call also passes
  `collection_metadata`
- **WHEN** the source pin test runs
- **THEN** it fails

## Requirement: the build process records the answers it serves

After the log read, and still in the build process, the runner SHALL record the build
process's answers to the 115 cases, in case order, on two paths through
`vectordb._base_manager.HybridRetriever`. The retriever is built over the store that
`from_documents` returned and the chunks `_restore_chunks_from_store` in
`vectordb/manager.py` restores from it, with production's `retrieval_top_k`, `rrf_k` and
`rrf_doc_key_chars` read from `config.settings`, `use_bm25` true, `parent_expansion`
false, no reranker, and a `rerank_k` of 1000000, so that nothing is truncated:

- `vector`: the `chunk_index` values of `get_vector_documents(query)`, in order;
- `candidates`: the `chunk_index` values of `get_relevant_documents(query)`, in order.
  This is the whole list production's reranker would receive.

The settings values used SHALL be recorded. `HybridRetriever` answers an empty vector
list when its vector search raises, so every `vector` answer SHALL hold exactly
`retrieval_top_k` distinct chunk indexes, and every `candidates` answer SHALL hold each
of them; otherwise the run fails.

### Scenario: a vector search that raises

- **GIVEN** a store whose similarity search raises, so that `get_vector_documents`
  returns an empty list
- **WHEN** the build process answers the cases
- **THEN** the run fails and writes no report

## Requirement: every trial is a new process that reopens the collection as production does

After the build process exits, the runner SHALL run seven trials, numbered 0 to 6, one
after another. Each trial SHALL run in a new Python process, started with the runner's
interpreter, that prints one JSON object as its last line of output. It SHALL open the
collection as `get_retriever` in `vectordb/manager.py` does,
`langchain_chroma.Chroma(persist_directory=..., embedding_function=..., collection_name=...)`,
restore its chunks with `_restore_chunks_from_store`, and record both paths with a
retriever built exactly as the build process built its own. It SHALL require 5589
restored chunks whose text digest equals the archive's. Every process SHALL run with
`ANONYMIZED_TELEMETRY=False` in its environment, and SHALL fail if its Chroma client
reports telemetry enabled.

### Scenario: telemetry enabled in a trial

- **GIVEN** a trial whose Chroma client reports `anonymized_telemetry` true
- **WHEN** the trial runs
- **THEN** it fails, and the run writes no report

## Requirement: a process answers the same when asked twice

Every trial, and the build process, SHALL answer all 115 cases on both paths a second
time and compare the two passes. If any answer differs within one process, the run SHALL
fail and write no report: the measurement is of variation between processes, and a
process that disagrees with itself makes that comparison meaningless.

### Scenario: a process that disagrees with itself

- **GIVEN** a trial whose second pass returns a different `vector` ranking for one case
- **WHEN** the runner reads that trial's output
- **THEN** the run fails, writes no report and still removes its directory

## Requirement: the report records the variation against the answers served before a restart

For each path the report SHALL hold the build process's answers and, for each trial 0 to
6, the ascending indexes of the cases whose answer differs from the build process's, and
the number of distinct cases that differ in at least one trial. For each path it SHALL
also hold, for each trial 1 to 6, the ascending indexes of the cases whose answer differs
from trial 0's, and the number of distinct such cases. For `candidates` it SHALL further
hold, for each trial 0 to 6, the ascending indexes of the cases whose candidate set,
ignoring order, differs from the build process's, and the number of distinct such cases:
a reranker scores each candidate on its own, so only a changed set can change the answer
it returns. No difference is a failure; each is a recorded result.

The report SHALL record the build facts, the unpersisted tail (the log's highest sequence
id minus the persisted one), and each trial's restored chunk count.

### Scenario: a reordered candidate list

- **GIVEN** a trial whose `candidates` answer for one case holds the build's candidates
  in another order
- **WHEN** the report is built
- **THEN** that case is listed as differing from the build in order, and not in its
  candidate set

## Requirement: provenance and cleanup

The runner SHALL refuse to run unless the platform is macOS and `ANONYMIZED_TELEMETRY`
is `False`, and unless the tracked git worktree is clean, recording `HEAD` as the code
commit, as D.5's `_git_code_base` does. The report SHALL record the schema version
`chroma-restart-stability-v1`, the code commit, the input digests, the SHA-256 of the
runner's source files at that commit, the Python version, the versions of `numpy`,
`chromadb`, `langchain-chroma`, `langchain-core` and `rank-bm25`, the platform, the CPU
count, `hw.model` and `hw.memsize`, the load average at the start, and the start and end
times in UTC. A process that runs longer than 900 seconds SHALL fail the run.

The collection's directory SHALL be a new directory named `chroma_restart_<16 hex>` under
the system temporary directory, removed after the last trial whether the run succeeded
or not. The report's `status` SHALL be `measured` if the directory was removed, and
`cleanup_failed` otherwise; a `cleanup_failed` report is NOT_EVIDENCE. A failed run
SHALL write no report. The runner SHALL refuse to overwrite an existing output file.

### Scenario: the directory cannot be removed

- **GIVEN** a run whose trials all succeed and whose directory removal fails
- **WHEN** the runner writes the report
- **THEN** its `status` is `cleanup_failed`

## Requirement: what the measurement decides

The measurement decides no default. If the build process's candidate set differs from a
restarted process's in any case, a restarted production process can hand the reranker a
different set of candidates for the same question than the process that ingested the
collection did; changing production's write path or Chroma settings for that is its own
slice, proven by an end-to-end test, and this measurement is then rerun under this file
at the new commit. If no case differs, the result stands for this corpus, this host and
these versions only: the unpersisted tail depends on the corpus size and on the client's
batch size.

### Scenario: a changed candidate set

- **GIVEN** a `measured` report in which one case's candidate set differs from the
  build's in one trial
- **WHEN** the result is published
- **THEN** the publishing slice changes no runtime default, and names the fix as a
  separate slice

## Requirement: the published report is pinned and quoted exactly

A committed report of this measurement SHALL be guarded by a test that pins the report's
SHA-256 and the code commit it was built at, requires each recorded source digest to be
the SHA-256 of that file's blob at the code commit, and requires each recorded input
digest to equal the digest D.1 recorded for that input. From the report alone, the test
SHALL rebuild every trial's answers, trial 0's as recorded and each later trial's as the
build's with that trial's recorded differences applied, recompute the comparison with the
committed `compare_answers`, and require the recorded comparison. It SHALL require the
unpersisted tail to equal the difference of the two recorded sequence ids. The evidence
capsule and its `EVIDENCE_INDEX.md` row SHALL quote no number that the report does not
hold outside its answers, apart from the number of cases a trial changed on a path.

### Scenario: a mutated report

- **GIVEN** the published report altered by any byte
- **WHEN** the artifact test runs
- **THEN** it fails on the pinned SHA-256

### Scenario: a number the report does not hold

- **GIVEN** a number written in the capsule outside code spans
- **WHEN** the artifact test runs
- **THEN** it fails unless that number is a JSON number of the report outside its
  answers (not a boolean), or the number of cases a trial changed on a path

## Requirement: amendment 1, the rerun makes production's new write call

The orchestrator wrote this requirement on 2026-09-25, after the first report was published
at `49db561` and before any rerun. The fix
([chroma-index-persistence](chroma-index-persistence.md)) makes `build_staged_collection`
pass `collection_configuration={"hnsw": {"sync_threshold": 1}}` to `from_documents`. From
the commit that makes that change on, the build process SHALL make production's call with
the same `collection_configuration`. The words "with no collection metadata, no collection
configuration and no client settings" above then no longer describe production, and stop
applying. The source pin SHALL accept exactly the keywords `documents`, `embedding`,
`persist_directory`, `collection_name` and `collection_configuration`, with that literal
value, and SHALL fail on any other keyword or value. Every other requirement of this file
holds unchanged, the schema version included.

The first report, `evaluation/chroma-restart-stability.json`, stays as published and
pinned. The rerun's report SHALL be published as
`evaluation/chroma-restart-stability-after-fix.json`, under the previous requirement, with
its own artifact test, its own capsule and its own `EVIDENCE_INDEX.md` row.

### Scenario: another threshold

- **GIVEN** a `build_staged_collection` whose `collection_configuration` holds a
  `sync_threshold` other than 1
- **WHEN** the source pin test runs
- **THEN** it fails

### Scenario: the configuration dropped

- **GIVEN** a `build_staged_collection` whose `from_documents` call passes only
  `documents`, `embedding`, `persist_directory` and `collection_name`
- **WHEN** the source pin test runs
- **THEN** it fails
