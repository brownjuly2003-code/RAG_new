# Capability: embedder-manifest

The mandatory part of quality-plan 2.3 ([plan](../../archive/docs/specs/plan_final_30_09_26.md), G25)
binds a Chroma collection to the embedder that produced its vectors. Equal
vector dimensions alone do not establish that identity. The contract applies
to vector, hybrid and graph retrieval, and to collection writes.

## Requirement: persist the embedding identity before the first write

A manifest SHALL contain schema version, backend, model id, loaded revision
and its source, dimension, query/document prompts and normalization. Its JSON
SHALL be canonical, with a SHA-256 computed from that JSON. Local revision
resolution SHALL use the loaded HF snapshot rather than a moving reference;
`RAG_EMBEDDING_MODEL_REVISION` MAY pin the requested revision. Remote identity
SHALL contain no credentials and SHALL identify an unversioned revision.

A new collection SHALL receive the manifest at creation. An existing empty,
unstamped collection SHALL receive it before adding vectors. A collection
that already contains vectors SHALL never acquire a retrospective stamp.
Writes into a stamped collection SHALL check every manifest field before
adding records. Publication and rollback SHALL preserve the collection stamp.

### Scenario: a new or empty collection receives its stamp

- **GIVEN** an identified embedder and a new or empty unstamped collection
- **WHEN** ingestion, legacy build, staged build or KB publication writes vectors
- **THEN** the manifest is present before the first write
- **AND** staged creation retains the persistence contract in
  [chroma-index-persistence](chroma-index-persistence.md)

### Scenario: an existing legacy collection remains unstamped

- **GIVEN** a collection containing vectors without a manifest
- **WHEN** records are added or the collection is loaded
- **THEN** it remains unstamped and usable
- **AND** its status is `unstamped`, with `evidence_status: NOT_EVIDENCE`
- **AND** measurements require a rebuild before being eligible evidence

### Scenario: a fact-card rebuild replaces the old collection

- **GIVEN** a fact-card collection with any prior manifest or legacy state
- **WHEN** its existing delete-then-rebuild operation runs
- **THEN** the replacement contains only the new records and the current stamp
- **AND** the tenant index lock covers deletion, creation and writing

## Requirement: refuse incompatible indexes before retrieval or writing

Loading SHALL compare all manifest fields before restoring chunks or caching
a retriever. A difference SHALL refuse the load, even for equal dimensions.
An explicit substitute supplied with a cached retriever SHALL be checked.
Manifest status and cache invalidation SHALL be tenant-scoped and SHALL work
with a plain vector retriever without assigning attributes to that retriever.

### Scenario: a same-dimension model substitution is refused

- **GIVEN** a collection stamped for one model and another configured model
  with the same vector width
- **WHEN** `/api/ask` loads its retriever, including after a startup refusal
- **THEN** it returns HTTP 503 with `reason: embedder_manifest_mismatch`
  and a `trace_id`
- **AND** the tenant-scoped trace contains an `index_manifest` refusal with
  stored/configured identities, mismatched fields and `NOT_EVIDENCE`
- **AND** another tenant's retriever and trace access remain isolated

### Scenario: a write into an incompatible collection is refused

- **GIVEN** an existing collection with an incompatible stamp
- **WHEN** a build appends records to it
- **THEN** the mismatch is raised before any vector is added
- **AND** the existing records and stamp are preserved

### Scenario: incompatible KB publication leaves the draft pending

- **GIVEN** a pending KB draft and an incompatible destination collection
- **WHEN** its publish endpoint checks the manifest under the tenant index lock
- **THEN** it returns HTTP 409 with `reason: embedder_manifest_mismatch`
  and a tenant-scoped refusal `trace_id`
- **AND** neither records nor the draft's publication state change

## Requirement: distinguish proven identity from an unverified revision

`match` with `evidence_status: eligible` SHALL require every field equal and
both revisions resolved as `hf_snapshot` with a 40-hex commit. Equal manifests
whose revisions are unresolved SHALL allow loading as `unverified`, with
`NOT_EVIDENCE` and reason `revision_unresolved` or `remote_unversioned`.
A resolved commit on only one side SHALL remain a mismatch.

### Scenario: a verified match reaches trace and Evidence

- **GIVEN** identical manifests with resolved HF revisions
- **WHEN** `/api/ask` retrieves context
- **THEN** it logs `index_manifest` with `match` and `eligible` before
  `retrieval_route`
- **AND** the Evidence endpoint exposes that status and both identities

### Scenario: equal unresolved revisions remain unverified

- **GIVEN** equal local unresolved or remote unversioned manifests
- **WHEN** `/api/ask` retrieves context
- **THEN** retrieval is allowed and trace/Evidence show `unverified`, its
  reason and `NOT_EVIDENCE`
- **AND** neither an absent revision nor dimension equality proves identity

For unidentified embedders the status is `unidentified`; Qdrant is
`unsupported_backend`. Both are `NOT_EVIDENCE`. This capability does not
measure retrieval quality or implement the conditional graph-lifecycle part
of plan 2.3.
