# C4 PostgreSQL append immutability guards

## Goal

Enforce database-level append-only behavior for resolution events, evidence snapshots, and case/evidence links without breaking legal `SupportCase` compare-and-swap updates.

## Tasks

- [x] Add focused real-PostgreSQL assertions for allowed appends, blocked `UPDATE`/`DELETE`, allowed case CAS, and downgrade behavior -> Verify the new contract fails against revision `025`.
- [x] Add additive Alembic revision `026` on top of `025` -> Verify the focused real-PostgreSQL contract passes under a non-owner, non-`BYPASSRLS` runtime role.
- [x] Run scoped Ruff/format, strict Resolution MyPy, Alembic single-head, the combined Resolution test band, and one migration round trip.
- [x] Reconcile the current handoff/state/backlog once and prepare the verified scoped result for an explicit-pathspec local commit.

## Done When

- [x] All three append-only tables allow inserts and reject runtime-role mutation/deletion, `support_cases` CAS still succeeds, downgrade removes only the C4 guards, temporary resources are removed, and all scoped gates are green.

## Notes

Do not add temporal exclusion, encryption/restore, API/runtime routing, production-role provisioning, push, deploy, or changes to the working `rag_assistant` database in this slice.
