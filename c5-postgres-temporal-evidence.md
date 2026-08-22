# C5 PostgreSQL temporal evidence constraints

## Goal

Reject overlapping evidence validity windows for the same tenant, logical fact, applicability, and authority while preserving adjacent windows and explicit cross-authority conflicts.

## Tasks

- [x] Add real-PostgreSQL assertions for same-authority overlap rejection, adjacent and cross-authority acceptance, catalog identity, and downgrade behavior -> Verify the focused contract passes on revision `027`; no unretained tests-first red is claimed.
- [x] Add additive Alembic revision `027` and matching PostgreSQL-only ORM metadata -> Verify the exclusion constraint preserves C3 RLS and C4 immutability.
- [x] Run scoped Ruff/format, strict MyPy, Alembic single-head, the combined Resolution test band, one migration round trip, and structural PostgreSQL/SQLite DDL checks.
- [x] Reconcile handoff/state/backlog once and hand the verified scoped result off for an explicit-pathspec local commit.

## Done When

- [x] PostgreSQL rejects overlapping `[valid_from, valid_to)` ranges for the same tenant/logical key/applicability/authority even when `source_id` changes; boundary-adjacent, different-authority, and different-applicability evidence is accepted; downgrade removes only the named C5 constraint while retaining shared `btree_gist`; temporary resources are removed and all scoped gates are green.

## Notes

Do not add knowledge-plane tables, Slice D/runtime/API routing, encryption/restore, production-role provisioning, push, deploy, or changes to the working `rag_assistant` database in this slice.
