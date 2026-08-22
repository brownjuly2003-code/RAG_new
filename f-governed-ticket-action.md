# Slice F governed ticket action

## Goal

Wrap the existing ticket-creation capability in a tenant-scoped governed
action gateway that persists authorization and execution truth before any
connector call and never duplicates an ambiguous external write.

## Tasks

- [x] Add RED domain/application tests for pinned manifests, PDP binding,
  exact confirmation, kill switches, canonical idempotency, timeout-to-unknown,
  reconciliation, verified remote identity, postconditions, and independently
  governed compensation.
- [x] Add RED real-PostgreSQL tests for revision `030`, eight action tables,
  composite tenant ownership, forced RLS, append/transition guards,
  transactional outbox, worker leases, and `029 -> 030 -> 029 -> 030`.
- [x] Implement the `actions` domain, registry/ports, gateway/worker state
  machine, and a pinned adapter over the existing escalation ticket service
  without switching the legacy runtime route.
- [x] Add matching SQLAlchemy models, revision `030`, and tenant-scoped
  PostgreSQL repository/unit-of-work with exact replay/conflict semantics.
- [x] Run focused unit and disposable PostgreSQL gates, one independent QA
  follow-up, scoped Ruff/format/strict MyPy, restore inventory, and diff checks.
- [x] Create one explicit-pathspec local commit for the verified Slice F;
  resolve its SHA through Actual Git, and do not start Slice G in this turn.

## Done When

- [x] Denial cannot call a connector; same logical key and canonical input
  reuse one run, changed input conflicts, and timeout/disconnect/restart paths
  reconcile the same downstream identity without a second create.
- [x] Ticket success requires a validated source-system identity and a passing
  deterministic postcondition; compensation is a separate authorized run.

## Boundaries

Use only fakes and disposable local PostgreSQL. Do not call Bitrix or another
external connector, change production/Mac grants, route legacy traffic through
the new gateway, deploy, push, start canary, or start Slice G.

## Current handoff — 2026-08-22

Slice F is locally complete in the explicit-pathspec commit containing this
plan, based on baseline `18d47e6`. The implementation, both behavioral Done
When clauses and all scoped verification are green. Resolve the delivery SHA
through Actual Git; Slice G must not start in this turn.

Current evidence:

- real PostgreSQL: 4 passed, including `029 -> 030 -> 029 -> 030`, forced RLS,
  transition guards, exact replay/postcondition and timeout reconciliation
  without a second create; this gate was not repeated because the final diff
  was type/format-only;
- focused strict MyPy: green across 6 source files after type-only fixes;
- scoped Ruff lint: green. The initial format check found only the new Slice F
  additions in `db/models.py` needed formatting; the formatter was applied,
  the final scoped format check reported 13 files already formatted, and
  `db/models.py` lint is green;
- unit/restore: 18 passed, 1 skipped, with one known Starlette/httpx2 warning;
  `git diff --check` is green;
- inventory: 31 ORM / 37 public at head `030`;
- temporary `rag_actions_f_*` databases and roles: none after cleanup;
- QA follow-up 1/1 remains exhausted and produced no findings; do not launch a
  replacement for this slice.

The legacy runtime route, external connectors, production/Mac databases and
grants, push and deploy were not changed or exercised. Do not repeat green
gates or start Slice G in this turn.
