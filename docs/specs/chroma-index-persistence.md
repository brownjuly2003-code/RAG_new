# Capability: chroma-index-persistence

The [restart measurement](../evidence/chroma-restart-stability.md) found that production's
write path left 128 of 5589 records in Chroma's write-ahead log. Chroma persists a
collection's vector index at the end of an add call only once the records it has not yet
persisted reach the index's `sync_threshold`, 1000 by default. langchain-chroma added the
corpus in two calls, and the second one, of 128 records, stayed below that threshold. Every
new process re-inserts such records into its own index. One restarted process then handed
the reranker a different candidate set, in one of 115 cases, than the process that
ingested the collection did. This capability makes a restarted production process answer
as the ingesting process did. It changes how new collections are written, and nothing
else. A collection built before this change keeps its unpersisted records until it is
rebuilt.

## Requirement: the staged build leaves no unpersisted record

`build_staged_collection` in `vectordb/index_staging.py` SHALL pass
`collection_configuration={"hnsw": {"sync_threshold": 1}}` to `Chroma.from_documents`, and
add nothing else to that call. With a threshold of 1, Chroma persists the vector index at
the end of every add call. When production's ingestion has built and published a collection, that
collection's vector segment SHALL be persisted up to the highest write-ahead-log sequence
id among the collection's records.

### Scenario: a corpus smaller than the default threshold

- **GIVEN** a corpus of fewer than 1000 chunks, which Chroma's default configuration would
  leave entirely in the write-ahead log
- **WHEN** production's ingestion builds and publishes it with real Chroma
- **THEN** the collection's vector segment is persisted through its last record

### Scenario: the configuration is dropped

- **GIVEN** the same ingestion, with `collection_configuration` removed from the build call
- **WHEN** it builds and publishes the collection
- **THEN** records remain above the persisted sequence id, and the check that guards the
  first scenario fails

## Requirement: a restarted process answers as the ingesting process did

An end-to-end test SHALL prove this requirement with real Chroma and real langchain-chroma,
a real second Python process, and deterministic stand-ins only for the embedding model and
the language model. The first process SHALL build and publish a collection through
production's ingestion. It SHALL then answer queries with the retriever that
`vectordb.manager.get_retriever` returns in that process. A second process, started after
the build, SHALL open the published collection the same way, as production does after a
restart.

- For every query of the test, both processes SHALL return the same `chunk_index` values in
  the same order, from `get_relevant_documents`. That list is the whole candidate list that
  production's reranker receives.
- A question sent to `/api/ask` in each process SHALL be answered from the same retrieved
  context, with the same sources.

### Scenario: a restart after ingestion

- **GIVEN** a collection that production's ingestion built and published in one process
- **WHEN** a new process opens it and both processes answer the same queries and the same
  `/api/ask` question
- **THEN** the candidate lists, the retrieved context and the sources are identical
