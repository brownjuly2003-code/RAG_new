# C7 Resolution restore smoke

## Goal

Prove on disposable PostgreSQL that a head-`028` snapshot restores the exact
C1-C6 schema and representative Resolution data without touching
`rag_assistant`, production roles, runtime routing, or deploy surfaces.

## Tasks

- [x] Capture tests-first red for the stale restore table inventory (`18` vs actual `23`).
- [x] Make restore verification compare the exact expected public-table set, including migration-owned tables and `alembic_version`.
- [x] Retain a portable Resolution restore contract for case/evidence data, locator ciphertext, RLS, append guards, temporal exclusion, and protection profile.
- [x] Run a real `pg_dump -Fc` source-to-target restore on two disposable PostgreSQL databases and verify head `028` plus the C1-C6 guarantees.
- [x] Remove every disposable database, role, dump, report, and keepalive; then run focused and proportional gates.

## Done when

- [x] The real restore and exact inventory/data/catalog checks pass with fresh evidence.
- [x] C7 is recorded as local-only; production runtime-role operations and root Slice C remain open.

## Verification evidence

- The focused gate passed **16 tests**, with **2 skipped** and **1 deselected**;
  scoped Ruff check/format and `git diff --check` passed.
- An optional MyPy probe stopped before C7 analysis on known local environment
  drift (NumPy 2.5.1 stubs use Python 3.12 `type`, while the MyPy target is
  Python 3.11 and the lock pins NumPy 2.4.4). `scripts/` is outside the required
  project MyPy gate, so C7 does not claim MyPy green.
- A PostgreSQL 14 WSL smoke migrated a disposable source from `base` to `028`,
  seeded one case, event, evidence snapshot, and evidence link, created a
  custom-format dump, and restored it into a separate disposable target.
- The target had revision `028`, the exact **23-table** public inventory
  (**17 ORM + 5 migration-owned + `alembic_version`**), and all four seeded
  rows. The locator remained ciphertext and decrypted with the test key.
- Restored RLS default-deny/tenant isolation, append guards (`55000`), temporal
  exclusion (`23P01`), and the protection constraint (`23514`) all passed.
- Cleanup left zero disposable databases and roles; the dump and verifier were
  absent and the PostgreSQL keepalive was stopped.

## Boundaries

Never run `pg_restore --clean` against `rag_assistant` or any working/production
DSN. C7 does not include production grants, API/runtime routing, Slice D,
push, deploy, or live-provider calls.
