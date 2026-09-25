# D.4 pgvector graph and evidence parity — measured slice

**Verdict:** On 2026-09-25, a fresh local PostgreSQL scratch database was migrated
with the repository's Alembic chain. The production structural graph built from the
tracked aircargo archive round-tripped through `StructuralGraphRepository` with an
identical persisted contract. Production evidence rows joined every chunk node. Under
a disposable non-superuser role, tenant isolation held: a cross-tenant insert was
rejected with `42501` by RLS. The append-only evidence rule held: evidence update and
delete were rejected with `55000` by immutability triggers. There is no migration decision.
The runtime default stays the same: `RAG_GRAPH_RETRIEVAL` remains `off`. Phase D remains
open for cold-start and host RAM.

## Numbers

The measured graph had 10300 nodes and 17327 edges, including 5589 chunk nodes.
Its as-built form also held 5877 unresolved cross-references.

| Observation | Recorded result |
|---|---|
| Graph round trip | 10300 nodes and 17327 edges; identical persisted contract |
| Parity mismatches | 0 traversal, node and edge |
| Contract digest | `39a998494c5cfbd9b755f69ab0ec67b890939ac0b0903927489e8a13d967c395` |
| Unresolved cross-references | 5877 as built; not persisted by the schema |
| Load order | Node and edge order both preserved in this run; diagnostic only |
| Evidence join | 5589 chunk nodes, 5589 links and 5589 join rows |
| `kb_graph_nodes` RLS | Enabled and forced; 10300 own-tenant rows; 0 unset and cross-tenant rows |
| `kb_graph_edges` RLS | Enabled and forced; 17327 own-tenant rows; 0 unset and cross-tenant rows |
| `evidence_snapshots` RLS | Enabled, forced; own 5589; unset 0; cross-tenant 0 |
| `case_evidence_links` RLS | Enabled, forced; own 5589; unset 0; cross-tenant 0 |
| Runtime role flags | `superuser` false; `bypassrls` false |
| Write probes | Cross-tenant insert `42501`; evidence update `55000`; evidence delete `55000` |
| After rollback | 0 rows across six measured tables; disposable role absent |
| Scratch database | `rag_spike_d4_4922dcac21bfbee4` dropped |

All four RLS tables returned the seeded own-tenant count and no rows with the tenant
unset or a cross-tenant predicate. The report's graph-to-evidence match is a
diagnostic semantic join, not a schema foreign key.

## What the persisted contract leaves out

The as-built digest
`92d2fdd920ffc9bdf58c7f16193cd9fa3db00c8d1d6339b5768f4f1aada206c6`
differs from the reload because of the 5877 unresolved cross-references.
`kb_graph_nodes` and `kb_graph_edges` have no place for them, and `.load` returns none.
Production matches a stored graph by node id and edge id in
`ingestion/entity_graph_loading.py`. Parity therefore compares the persisted contract;
the load-order flags are diagnostics. The report records no collation. Both flags were
true in this run. Because `.load` orders by text columns, another collation could
reorder nodes and edges without changing the persisted contract.

## Provenance

- The run used a clean clone of `master` on `deproject-mac` at
  `67a9dbc9814b8baa4e291158c9fd9a924fce92ab`.
- Recorded source blob digests at that commit:
  - `scripts/pgvector_graph_evidence_run.py`:
    `9d820cda370e28b8919a35fdecbf6dee4ced244aee735a5432e3a14da9c388a4`;
  - `scripts/pgvector_graph_evidence.py`:
    `eb3aebbfd7fd8cec3371b64ef4ef9e3d83b5a82207d32f1a2bb7533c842bca0a`;
  - `ingestion/structure_graph.py`:
    `2ba6d606f3dbee759d78f4766c7ad43160dc3b047d5f98ba7245c033da8937fc`;
  - `ingestion/structure_graph_repository.py`:
    `c01833571f3a08e8dc9e010439ade03d2f2d42a7193658c246eaac8a0931c123`;
  - `ingestion/structure_graph_projection.py`:
    `0ed54c99a552cc79dae834f7ff31c583b477ffb82073a8a4fe2b74caa9635641`.
- Input digests: tracked gzip archive
  `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12`;
  decompressed JSON
  `5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`.
- Alembic head `033`; PostgreSQL `16.15 (Homebrew)`; `vector` `0.8.1`.
  Recorded packages: Python `3.11.15`, SQLAlchemy `2.0.52`, psycopg2
  `2.9.13 (dt dec pq3 ext lo64)` and NetworkX `3.5`.
- [Raw report](../../evaluation/d4-pgvector-graph-evidence.json): `4411` bytes,
  SHA-256 `63ee3b5ec9f8d9638e84ce122c5e41a2fc5e1ae0595f8ca97006e43517f10d7b`.

The command ran with the output path outside the clone:

```sh
python -m scripts.pgvector_graph_evidence_run \
  --chunks evaluation/gr1b-4436d61-graph-chunks.json.gz \
  --output "<path outside the clone>"
```

The administrative URL came from `RESOLUTION_ADMIN_DATABASE_URL` in the Mac secrets
file and is recorded nowhere. The scratch database
`rag_spike_d4_4922dcac21bfbee4` was created and dropped during the run.

An earlier diagnostic run on the same archive in the MyFlow gate checkout produced
the same digests and counts before the runner was committed. It is NOT_EVIDENCE:
MyFlow sync commits the working tree there, so that report names a synthetic commit.
It was never published and is not an input to this evidence.

## Verification

`tests/test_pgvector_graph_evidence_artifact.py` pins report bytes, tracked input and
source blobs at the recorded commit. It replays recorded observations through the
committed builder and checks that this capsule, the index and ADR quote only recorded
numbers. This is an arithmetic replay, not a second database measurement.

The D.4 unit tests passed in the clean clone before measurement. The PostgreSQL
acceptance test `tests/test_pgvector_graph_evidence_db.py` skips when
`RESOLUTION_ADMIN_DATABASE_URL` is absent; it ran green on the Mac with that variable
set, on its synthetic fixture, during `T-41`'s checks on 2026-09-25.

## Evidentiary limits

- This is one run on one corpus and one host, with no replication.
- Evidence rows are synthetic: one support case, plus one knowledge snapshot and one
  link per chunk node, stored as `development_file` with no encryption key. The
  graph-to-evidence match (`source_id = natural_key`, `content_digest =
  content_sha256`) is a diagnostic semantic join, not a schema foreign key.
- The persisted contract excludes unresolved cross-references. By the schema's design,
  a reload cannot reproduce the as-built digest.
- Isolation switches to a disposable `NOLOGIN` role with `SET LOCAL ROLE` inside the
  administrative role's transaction. It does not log in as the production runtime
  role. The report records only the disposable role's flags. The disposable role
  exists because an administrative connection may be a superuser or hold `BYPASSRLS`;
  either bypasses RLS.
- `vector` `0.8.1` is created inside the rolled-back transaction only to record its
  version. D.4 exercises no vector column.
- No retrieval quality, latency, cold-start or host RAM was measured, and there is no
  migration decision.
- The report hash detects mutation; it does not prove how the bytes were made. Code
  identity rests on the clean clone and source blob digests.

## Remaining Phase D

Measure cold-start and host RAM before any migration decision. See the decision record,
`docs/adr/0007-pgvector-spike.md`.
