# E2 PostgreSQL temporal knowledge authority

## Goal

Persist the E1 temporal-knowledge contract in six tenant-owned PostgreSQL
tables and expose a fail-closed application seam that authorizes only exact,
projection-bound knowledge versions for Chroma retrieval.

## Tasks

- [x] Add RED unit and real-PostgreSQL tests for the six-table inventory,
  `028 -> 029 -> 028 -> 029`, composite tenant ownership, forced RLS,
  append/system-close guards, bitemporal exclusion, repository round trips,
  approved identities, and retrieval allowlisting.
- [x] Add revision `029` and matching SQLAlchemy metadata for knowledge
  objects, exact-five applicability, versions, supersessions, conflicts, and
  projection bindings with validated ordered source-version identities.
- [x] Add tenant-scoped repository/unit-of-work and application authorization
  seams that reuse E1 domain/projection validation and fail closed on identity,
  conflict, manifest, version, digest, or metadata drift.
- [x] Run focused unit and disposable PostgreSQL gates, then scoped Ruff,
  format, strict MyPy, restore-inventory regression, and `git diff --check`.
- [x] Apply one batched independent QA follow-up if needed, update current
  durable status once, and create one explicit-pathspec local commit.

## Done When

- [x] Head is `029`; exact inventory is 23 ORM / 29 public tables; all E2
  behavior and adjacent E1/C7/C8 safety floors have fresh green evidence.

## Boundaries

Use only disposable local PostgreSQL databases. Do not mutate Mac/production
roles or grants, switch legacy runtime routing, connect a live source, deploy,
push, start Slice F, or change Chroma manifest schema v1.
