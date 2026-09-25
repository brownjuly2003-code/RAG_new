# Capability: pgvector-graph-evidence

Phase D.4 measures, on a fresh local PostgreSQL scratch database migrated with the
repository's own Alembic chain, that the production structural graph survives the
production persistence path unchanged and that production evidence rows join it under
the production tenant policies. The runner is `scripts/pgvector_graph_evidence_run.py`;
the pure helpers and the report builder live in `scripts/pgvector_graph_evidence.py`.
D.4 supersedes only D.1's limitation, a simplified `kb_graph_nodes` membership table
under `app.tenant_id`. It changes no D.1–D.3 retrieval number, no product default, and
`RAG_GRAPH_RETRIEVAL` stays `off`. The schema stores no unresolved cross-reference, so
D.4 compares the persisted contract, the graph without them in a fixed order, and counts
the references it leaves out.

## Requirement: the input is the tracked chunk archive, pinned

The runner SHALL read the chunk document from the path it is given, which may be the
tracked gzip archive `evaluation/gr1b-4436d61-graph-chunks.json.gz` or the JSON it
decompresses to. It SHALL require exactly 5589 chunks, each with a nonempty string
`page_content` and an object `metadata`. The report SHALL record the SHA-256 of the
decompressed JSON bytes and, when given the archive, of the archive bytes.

### Scenario: the tracked archive

- **GIVEN** `evaluation/gr1b-4436d61-graph-chunks.json.gz`
- **WHEN** the runner loads it
- **THEN** it holds 5589 chunks, and the recorded digests equal the SHA-256 of the archive
  bytes and of the decompressed bytes

### Scenario: a wrong chunk count

- **GIVEN** a chunk document with 5588 chunks
- **WHEN** the runner loads it
- **THEN** it raises `ValueError` naming both counts, before any database connection

## Requirement: only a new local scratch database is touched

The runner SHALL accept an administrative database URL only with a PostgreSQL driver on
`localhost` or `127.0.0.1`, port 55432, read from `RESOLUTION_ADMIN_DATABASE_URL`. It
SHALL create a new database whose name fullmatches `rag_spike_[a-z0-9_]+` and fail if
that name exists. It SHALL migrate only that database, with the repository's Alembic
chain, to the head revision, and record that revision. Migration 028 refuses to run
without `DB_ENCRYPTION_KEY`; for the Alembic run only, the runner SHALL set it to a
random value generated in the run, never printed, stored or taken from the environment,
and restore the variable's previous state afterwards. The fresh database holds no row
for that key to encrypt. It
SHALL refuse to seed if any measured table already holds a row. It SHALL never drop,
alter or write a database it did not create in the same run. Neither the URL, its
password nor the migration key SHALL appear in output, exception messages or the
report.

### Scenario: a non-local URL

- **GIVEN** `RESOLUTION_ADMIN_DATABASE_URL` naming host `db.example.com`
- **WHEN** the runner starts
- **THEN** it raises `ValueError` before any connection, and the message holds no part of
  the URL

### Scenario: the scratch name exists

- **GIVEN** a database with the chosen scratch name already exists
- **WHEN** the runner starts
- **THEN** it fails without migrating, seeding or writing a report, and that database is
  unchanged

### Scenario: the migration key is per run

- **GIVEN** `DB_ENCRYPTION_KEY` set in the environment to `envkey`
- **WHEN** the runner migrates the scratch database
- **THEN** migration 028 runs with a different, randomly generated value, `envkey` is not
  used, and after the migration the variable holds its previous value again

### Scenario: the password stays secret

- **GIVEN** an administrative URL whose password is `topsecret`
- **WHEN** the runner completes, with any outcome
- **THEN** `topsecret` appears in neither stdout, stderr, any raised message nor the
  report

## Requirement: the graph round-trips through the production repository unchanged

The runner SHALL build the structural graph from all 5589 chunks with
`build_structural_graph`, for one fixed canonical UUID tenant. It SHALL persist it with
`StructuralGraphRepository.replace`, load it back with `.load`, and project both graphs
with `project_structure_graph`.

The persisted contract of a graph is the graph with three changes:

- `unresolved_cross_refs` is emptied;
- its nodes are ordered by `(kind, natural_key, node_id)`;
- its edges are ordered by `(kind, source_node_id, target_node_id, edge_id)`.

Both orders use Python code-point order. The persisted contract is what the migrated
schema stores and what production compares:

- `kb_graph_nodes` and `kb_graph_edges` have no place for an unresolved cross-reference;
- `.load` returns none;
- `ingestion/entity_graph_loading.py` matches a stored graph to the current one by node
  and edge id, not by order.

The report SHALL record:

- the node and edge counts;
- `structure_graph_digest` of the built graph as built;
- `structure_graph_digest` of the persisted contract of the built graph and of the
  reloaded graph;
- the built graph's unresolved cross-reference count, named as not persisted by the
  schema;
- whether `.load` returned the nodes and the edges in the built order;
- the result of `graph_parity`;
- `_traversal_mismatch_count` over every node.

Parity holds only when all three of these hold:

- the two persisted-contract digests are equal;
- `graph_parity` is identical, with zero node and edge mismatches;
- the traversal mismatch count is zero.

The unresolved cross-reference count and the order flag are diagnostics. Neither
gates parity.

### Scenario: an exact round trip

- **GIVEN** a reloaded graph whose persisted contract equals the built graph's
- **WHEN** the runner measures parity
- **THEN** the report records equal persisted-contract digests and zero node, edge and
  traversal mismatches

### Scenario: unresolved cross-references are not persisted

- **GIVEN** a built graph with at least one unresolved cross-reference, and its reload,
  which carries none
- **WHEN** the runner measures parity
- **THEN**:
  - the as-built digest differs from the reloaded graph's digest;
  - the persisted-contract digests are equal;
  - parity holds;
  - the report records the unresolved count as not persisted by the schema

### Scenario: the load order differs

- **GIVEN** a reload that returns the same nodes and edges in another order
- **WHEN** the runner measures parity
- **THEN** parity holds, and the report records that the order was not preserved

### Scenario: a reloaded edge drifts

- **GIVEN** a reload whose one edge carries a changed attribute
- **WHEN** the runner builds the report
- **THEN** `evidence_class` is `not_evidence`, a reason names the parity failure, and the
  CLI exits nonzero without printing `DONE`

## Requirement: production evidence rows join the graph

In the measurement transaction, the runner SHALL insert one `support_cases` row, its
version-1 `case_events` row, and for every reloaded chunk node exactly one knowledge
`evidence_snapshots` row and one `case_evidence_links` row. Each snapshot's `source_id`
SHALL equal the node's `natural_key`, and its `content_digest` the node's
`attributes.content_sha256`. The rows SHALL satisfy the migrated schema's constraints,
foreign keys and triggers as they are, without a schema change. The measurement uses no
encryption key: the snapshots take a storage and protection profile that the migrated
check constraints allow without one. Identities are deterministic UUID5 values and the
timestamp is one fixed UTC value.
`production_evidence_join_sql()`, run unchanged, SHALL return exactly one row per chunk
node. The report SHALL call the graph-to-evidence match a diagnostic semantic join,
not a schema foreign key.

### Scenario: every chunk joins once

- **GIVEN** the reloaded graph with N chunk nodes and the seeded evidence
- **WHEN** the runner counts chunk nodes, links and join rows in the database
- **THEN** all three counts equal N

### Scenario: a join count that disagrees

- **GIVEN** a join that returns one row fewer than the chunk-node count
- **WHEN** the runner builds the report
- **THEN** `evidence_class` is `not_evidence` and a reason names the counts

## Requirement: tenant isolation and append-only behaviour are observed

Inside the measurement transaction the runner SHALL create a disposable role that is
NOLOGIN, NOSUPERUSER and NOBYPASSRLS, whose name fullmatches a narrow fixed pattern,
with privileges only on `support_cases`, `case_events`, `kb_graph_nodes`,
`kb_graph_edges`, `evidence_snapshots` and `case_evidence_links`, and switch to it with
`SET LOCAL ROLE`. For each of `kb_graph_nodes`, `kb_graph_edges`, `evidence_snapshots`
and `case_evidence_links` the report SHALL record `relrowsecurity`,
`relforcerowsecurity`, the rows visible with `app.current_tenant_id` unset, under the
seeded tenant, and under a second UUID tenant, next to the seeded row count. It SHALL
record the active role's `rolsuper` and `rolbypassrls`. Under the seeded tenant, each
probe in its own savepoint, it SHALL record the SQLSTATE of a `kb_graph_nodes` insert
that carries the second tenant, and of an UPDATE and a DELETE of a seeded
`evidence_snapshots` row. Isolation holds only when both flags are true on all four
tables, the unset and second-tenant counts are zero, the seeded-tenant counts equal the
seeded rows, both role flags are false, and the SQLSTATEs are `42501`, `55000` and
`55000`.

### Scenario: the policies hold

- **GIVEN** the migrated schema and the seeded rows
- **WHEN** the disposable role reads and probes
- **THEN** the report records zero rows unset and cross-tenant, the seeded counts own-tenant,
  and SQLSTATEs `42501`, `55000`, `55000`

### Scenario: a probe that succeeds

- **GIVEN** a probe statement that raises no error
- **WHEN** the runner records it
- **THEN** `evidence_class` is `not_evidence`, and the reason names the probe but holds no
  SQL text or data value

## Requirement: the measurement leaves nothing behind

All seeding, role creation and probes SHALL run in one transaction on the scratch
database, and the runner SHALL roll it back on success and on failure, then dispose the
engine. After the rollback it SHALL check, and the report SHALL record, that the six
tables hold zero rows and that the disposable role does not exist. Then, on success and
on failure, it SHALL drop the scratch database it created in this run, and only that
one; the report names it and records that the drop succeeded.

### Scenario: a failure mid-seed

- **GIVEN** an insert that fails halfway through seeding
- **WHEN** the runner handles it
- **THEN** the transaction is rolled back, no role or row remains, the scratch database
  is dropped, and no `measured` report is written

## Requirement: the report is strict, pinned JSON

The runner SHALL write the report once, exclusively, as UTF-8 JSON with LF endings,
`allow_nan=False` and `schema_version` `d4-pgvector-graph-evidence-v1`, and refuse an
existing output path before any database work. The report SHALL record the code commit
(40 hex) and whether the working tree was clean; the SHA-256 of the input and of each
file in `SOURCE_FILES`; the Alembic head revision; the PostgreSQL `server_version`; the
`vector` extension version; the Python, SQLAlchemy, psycopg2 and NetworkX versions; the
scratch database name; and the limitations stated at the top of this file.
`evidence_class` SHALL be `measured` only when the tree was clean and parity, the
evidence join, isolation, the post-rollback checks and the scratch drop all hold; otherwise
`not_evidence`, with every failed condition named. The CLI SHALL exit 0 and print
`DONE` only for `measured`.

### Scenario: the output exists

- **GIVEN** an existing file at the output path
- **WHEN** the CLI runs
- **THEN** it raises `FileExistsError` before any database work, and the file is unchanged

### Scenario: no administrative URL

- **GIVEN** `RESOLUTION_ADMIN_DATABASE_URL` is unset
- **WHEN** the CLI runs
- **THEN** it fails closed before any database work

### Scenario: a dirty tree

- **GIVEN** a working tree with an uncommitted change
- **WHEN** an otherwise complete measurement finishes
- **THEN** `evidence_class` is `not_evidence`, and a reason names the dirty tree

## Requirement: unit tests need no database

Unit tests SHALL run without network access, PostgreSQL or models. A test that needs the
Mac PostgreSQL SHALL skip, naming the missing variable, unless
`RESOLUTION_ADMIN_DATABASE_URL` is set.

### Scenario: no database on the host

- **GIVEN** a host without `RESOLUTION_ADMIN_DATABASE_URL`
- **WHEN** the D.4 test files run
- **THEN** every unit test passes, and each database test is skipped with a message that
  names the variable
