# REL-03B durable session admission contract

## Goal

Add the PostgreSQL-backed admission and abort boundary decided by ADR 0006 so
two API replicas cannot admit conflicting turns for one tenant session, while
leaving the current ask, SSE, history, and compatibility paths unchanged.

## Completion status — 2026-08-23

- [x] Pure replay/session-binding and DB-clock regressions completed RED → GREEN.
- [x] Adjacent gate: 26 passed, 1 skipped; Ruff/format and Alembic head discovery
  are green.
- [x] Real PostgreSQL 14 gate: 6 passed across migration round-trip,
  concurrency, RLS, idempotency, expiry and exact abort.
- [x] Strict MyPy: 2 source files green under a Python 3.12 parser with project
  target 3.11; project-config `db.models` gate also green.

## Tasks

- [x] Add RED disposable-PostgreSQL tests for revision `031`, forced tenant
  RLS, idempotent admission, stale-version and active-turn rejection, overdue
  expiry, exact-token abort, and same/different-session concurrency.
- [x] Add revision `031` with non-negative `sessions.version`, monotonic
  `sessions.turn_epoch`, the constrained tenant-owned `session_turns` table,
  one-running-turn partial index, composite ownership, and forced RLS.
- [x] Add matching SQLAlchemy models and a transaction-scoped `SessionService`
  implementing admission/replay classification and exact-token abort with the
  PostgreSQL clock.
- [x] Run the focused database gate, one batched self-review/QA follow-up,
  proportional unit/restore, Ruff/format/strict MyPy, and diff/status checks.
- [x] Update durable handoff state once and create one explicit-pathspec local
  commit; do not start REL-03C in this turn.

## Done When

- [x] Two independent connections admit exactly one competing turn at the
  same session version, while different sessions admit independently.
- [x] Tenant isolation, stale versions, active live turns, expired admission,
  idempotency drift, and stale abort tokens fail closed without mutating
  message history or advancing `sessions.version`.

## Boundaries

Use only disposable local PostgreSQL. Do not wire `/api/ask` or SSE, add the
terminal message-pair commit primitive, remove compatibility ownership, call
external services, run a live/production migration, deploy, promote, or push.
Forced RLS in this slice applies to new `session_turns`; do not enable it on
legacy `sessions` until the later compatibility/API slice binds every existing
session read/write to a tenant GUC.
