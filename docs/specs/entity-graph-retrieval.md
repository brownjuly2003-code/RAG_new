# Capability: Entity-graph retrieval lane (GR-2)

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

Stream GR's second layer adds per-chunk entities to the structural graph and a
bounded entity lane to opt-in graph retrieval (`plan_06_09_26.md` §4 item 5,
§GR-2). Its product wiring is proven on synthetic fixtures
([evidence](../evidence/gr2-entity-retrieval-wiring.md)). What remains is a
quality claim, and a quality claim about this lane is only worth publishing if
three inputs cannot drift underneath it: the extracted entities, the query
routing, and the offline arm that stands in for the product lane.

## Requirement: extraction results are pinned to the model that produced them

An entity extraction cache SHALL record the corpus digest, the chunk payload
digest, the prompt digest, the provider, the pinned model identifier and the
generation options in its manifest, and SHALL record the model weights digest
whenever the provider reports one (`null` only for providers that expose none).
A run SHALL refuse a cache whose manifest differs from its own inputs, a moving
model alias, and a provider that reports a different weights digest for the same
model identifier than the manifest pins. Only rows that pass validation are
written as entities; an answer that fails validation SHALL either stop the run
or, when the run opts in, be recorded as a rejection with its chunk and content
digests. A resumed run SHALL NOT resend a cached or rejected chunk.

### Scenario: a local model is pinned by its weights digest

- **GIVEN** a local model server that reports a weights digest for the requested model
- **WHEN** an extraction run creates its cache
- **THEN** the manifest records that digest, and a later run against a server
  reporting a different digest for the same model identifier is refused before
  any chunk is sent

### Scenario: a hosted provider without a digest says so

- **GIVEN** a hosted provider that exposes no weights digest
- **WHEN** an extraction run creates its cache
- **THEN** the manifest records the provider and the pinned model identifier with
  `model_digest` explicitly `null`

### Scenario: an interrupted run resumes without repeating work

- **GIVEN** a cache holding validated rows for some chunks
- **WHEN** the run restarts with the same inputs
- **THEN** only the missing chunks reach the provider, and a corrupt or
  incomplete row stops the run instead of being truncated silently

### Scenario: an invalid answer is recorded, not cached

- **GIVEN** a run that records invalid answers and a model answer that fails validation
- **WHEN** the run reaches that chunk
- **THEN** a rejection row is written instead of entities, the next chunk is
  processed, and a resumed run sends neither the cached nor the rejected chunk

## Requirement: measurement routing comes from the production classifier, never from labels

An offline GR-2 measurement SHALL take each case's routed question class and
query entities from the production `classify_complexity` node, run over a pinned
model at temperature zero and cached with the dataset digest, the model identity
and the prompt and schema digests. Labelled question classes SHALL only group
reported metrics; they SHALL NOT decide whether the entity lane runs. A
transport failure SHALL NOT be cached as a classification.

### Scenario: the label and the classifier disagree

- **GIVEN** a case labelled `single_hop` that the cached classification routes as `multi_hop`
- **WHEN** the entity arm builds that case's candidate pool
- **THEN** the entity lane runs for it, and the report shows the case under its
  labelled class with its routed class beside it

### Scenario: the classifier was unreachable

- **GIVEN** a model server that fails during a classification call
- **WHEN** the classification run stops
- **THEN** no row is written for that case, and a restart classifies it again

### Scenario: the dataset changed after classification

- **GIVEN** a classification cache built for one dataset digest
- **WHEN** the entity arm is run with a dataset whose digest or query text differs
- **THEN** the arm refuses to build a pool and names the mismatch

## Requirement: the pools embeddings cache is keyed on the encoder actually in use

An offline pools run that writes `--embeddings-cache` SHALL record the identity
of the embedding backend `get_embeddings()` builds from the same settings
object: backend `local` records `embedding_model`; backend `remote` records
`embedding_remote_model` and the remote endpoint. A later pools run SHALL
refuse, with exit 2, a cache whose identity differs from its own encoder or
that lacks those identity fields, naming the mismatch or the missing field, and
SHALL NOT encode chunks against that cache. A later run whose identity matches
SHALL reuse the cached matrix.

### Scenario: a local matrix is not reused under the remote backend

- **GIVEN** a pools embeddings cache written with the local embedding backend
- **WHEN** a later pools run uses `embedding_backend="remote"` over the same chunks
- **THEN** the run exits 2, names the identity mismatch, and does not call the encoder

### Scenario: a remote matrix is not reused under the local backend

- **GIVEN** a pools embeddings cache written with the remote embedding backend
- **WHEN** a later pools run uses the local backend over the same chunks
- **THEN** the run exits 2, names the identity mismatch, and does not call the encoder

### Scenario: a matching backend reuses the cache

- **GIVEN** a pools embeddings cache written for one backend and model
- **WHEN** a later pools run uses the same backend, model and endpoint
- **THEN** the cached matrix is reused and the encoder is not called

### Scenario: a different remote model or endpoint is refused

- **GIVEN** a pools embeddings cache written with the remote embedding backend
- **WHEN** a later pools run uses the same backend but a different remote model or endpoint
- **THEN** the run exits 2, names the model or endpoint mismatch, and does not call the encoder

### Scenario: a cache written before identity fields is refused

- **GIVEN** a pools embeddings cache that lacks the backend identity fields
- **WHEN** a pools run reads that cache
- **THEN** the run exits 2, names the missing field, and does not call the encoder

## Requirement: the offline entity arm reproduces the product lane

The offline `G2` arm SHALL assemble each case's contexts in the same order as
`HybridRetriever.get_graph_documents_with_path` for the same chunks, projection,
routed class, query entities and reranker: vector and lexical candidates, at most
50 entity candidates from at most two co-occurrence hops as a third RRF list for
`multi_hop`, `aggregation` and `global` only, then reranking, section coherence
and section expansion. A case routed as `single_hop` SHALL yield exactly the
structural `G1` result.

### Scenario: parity on a synthetic fixture

- **GIVEN** a synthetic corpus, an entity-enriched projection and a deterministic reranker
- **WHEN** a `multi_hop` case goes through the `G2` pool and rerank stages, and
  separately through `get_graph_documents_with_path`
- **THEN** both produce the same contexts in the same order

### Scenario: single-hop routing changes nothing

- **GIVEN** a case the classifier routes as `single_hop`
- **WHEN** it goes through `G1` and through `G2`
- **THEN** both arms produce identical candidate pools and identical final contexts

## Requirement: GR-2 is published against GR-1 on the same cases

A GR-2 report SHALL compare `G2` with `G1` over the same cases for the
supplemental multi-document bucket and for the phase-C dataset, per labelled
question class with case counts, with keyword FULL/PART/MISS, context precision
and recall, paired per-case transitions and keyword losses, the routed-class
counts, entity-search latency, rerank time per case and peak resident memory. It
SHALL pin the pool digests, the extraction and classification manifests, the
corpus digest, the code commit and the configuration, and SHALL NOT change the
graph retrieval default.

### Scenario: a single-hop regression cannot hide behind a multi-hop gain

- **GIVEN** a `single_hop` case whose keyword status falls from FULL to PART under `G2`
- **WHEN** the report is read
- **THEN** that transition is listed with its case id, and the single-hop
  precision delta against `G1` is printed next to the multi-hop delta

### Scenario: the report reproduces from archived inputs

- **GIVEN** the archived `G1` and `G2` pools with their digests
- **WHEN** the report is rebuilt twice without models or network access
- **THEN** every case, class and aggregate is identical and matches the published report
