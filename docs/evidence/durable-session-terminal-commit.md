# REL-03C fenced terminal commit and durable history snapshot

## Goal

Add the PostgreSQL-owned terminal boundary decided by ADR 0006: an exact live
turn token commits one ordered user/assistant pair and advances the durable
session version once, while history readers receive a tenant-scoped,
versioned snapshot.

## Completion status — 2026-08-23

- Implementation delivered by `49bc966` (`feat(session): add fenced terminal
  commit`). The top CURRENT handoff documents runtime and replay gaps that are
  intentionally outside REL-03C.
- [x] Tests-first request-binding regression completed **1 failed -> 13 passed**
  on disposable PostgreSQL, including deterministic lock and rollback evidence.
- [x] Adjacent tests passed **12**; Ruff/format/diff and strict changed-source
  MyPy gates are green.
- [x] Independent QA batch and its only consolidated follow-up are complete.

## Tasks

- [x] Add RED disposable-PostgreSQL tests for exact commit, idempotent replay,
  concurrent duplicate commit, deadline/terminal/fence rejection, ordered
  history, and tenant-scoped reads.
- [x] Extend `SessionService` with a short fenced terminal transaction and a
  consistent history snapshot read; reuse revision `031` without changing the
  schema.
- [x] Run one independent QA batch, apply at most one consolidated follow-up,
  and pass focused PostgreSQL plus proportional adjacent/static gates.
- [x] Update durable state once and create one explicit-pathspec local commit.

## Done When

- [x] Only a still-`RUNNING`, unexpired turn whose expected version and epoch
  match its locked session inserts exactly two ordered messages, advances the
  version once, and becomes `COMMITTED` in the same transaction.
- [x] Identical concurrent/retried completion is a no-op replay; content drift,
  stale/foreign tokens, elapsed deadlines, and aborted/expired turns cannot
  mutate history or version.
- [x] History snapshots bind tenant, session version, and message order under a
  transactionally stable session lock.

## Boundaries

Use only disposable local PostgreSQL. Do not wire `/api/ask`, SSE, timeout
handling, compatibility state, live replicas, deploy, promotion, or push.
