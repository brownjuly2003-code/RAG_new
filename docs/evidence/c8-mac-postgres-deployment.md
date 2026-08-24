# C8 Mac PostgreSQL deployment

## Goal

Provision the authorized Mac target with an isolated PostgreSQL cluster and a
least-privilege Resolution role topology without touching the existing server
on port `5432` or enabling API/runtime routing.

## Tasks

- [x] Capture read-only Mac/PostgreSQL inventory and reserve loopback port `55432` -> Verify: existing `5432` remains unchanged and target paths are absent or owned by this slice.
- [x] Add `scripts/resolution_role_ops.py` with focused tests for fixed role attributes, exact grants, verification, and revoke ordering -> Verify: tests fail before implementation and pass after it.
- [x] Create the dedicated cluster, secure credential files, and persistent user service -> Verify: restart succeeds on `127.0.0.1:55432` with secrets absent from Git and process arguments.
- [x] Create the target database/roles, migrate to Alembic head, and apply the minimum grant matrix -> Verify: schema owner, migrator, and runtime identities match the contract.
- [x] Exercise default-deny, own-/cross-tenant, append-only `55000`, legal case CAS, and revoke/restore rollback -> Verify: all expected SQL states and post-rollback grants match.
- [x] Run independent QA, update current handoff once, and create a scoped local commit -> Verify: focused tests, Ruff, MyPy where applicable, `git diff --check`, and clean expected status.

## Done when

- [x] The Mac target is restart-stable, the existing PostgreSQL service is untouched, runtime is non-owner/`NOSUPERUSER`/`NOBYPASSRLS`, and C8 evidence is reproducible without exposing credentials.

## Delivery record

- Exact delivery commit: `c78da01 feat(resolution): provision Mac runtime roles`.
- Baseline: clean `master` at `5719520`; delivery ended with clean `master` at
  `c78da01`, no configured remote and no push.
- Delivery scope: 9 files, 1,943 insertions and 44 deletions. Four new files
  contain this capsule, the operator runbook, provisioning CLI, and focused
  tests; five durable planning/handoff files were updated.
- Final local gate: **25 passed**, Ruff format/check, compileall, Bandit,
  LF/secret-pattern and staged `git diff --check` green. Project MyPy excludes
  `scripts/` and `tests/`, so no MyPy-green claim is made for C8.
- Live Mac evidence was collected during the delivery turn before `c78da01`.
  Later docs-only checkpoints must label it last-known-good unless they run a
  fresh read-only probe from the operator runbook.

## Closing evidence

- Baseline: existing PostgreSQL on `5432` was accepting connections; the C8
  paths and loopback port `55432` were free. The existing checkout and its two
  untracked files were not changed.
- Target: Homebrew PostgreSQL `16.15`, checksums and SCRAM enabled, data at
  `~/.local/share/rag-new/postgresql-16`, and LaunchAgent
  `com.rag-new.postgresql`. A macOS startup failure was traced to the locale
  guard and fixed with `LC_ALL=C`; forced restart then returned exit code `0`.
- Database: `ragnew_prod` is at the single Alembic head `028`. The non-login
  schema owner owns the database/schema/tables; migrator membership has no
  admin or inherit option; runtime is a direct non-owner login with the exact
  Resolution ACL only.
- Runtime: direct-login smoke proved populated-row default deny, tenant-A
  access, tenant-B invisibility and insert denial `42501`, legal case CAS,
  forbidden column/delete `42501`, pgcrypto round trip, owner-level append
  guard `55000`, and rollback with no retained smoke rows.
- Operations: `revoke-runtime` denied a new login, restore grants verified,
  and exact contract plus smoke passed again after a LaunchAgent restart.
- QA: the independent review found policy/ACL/settings/order gaps in the first
  implementation. Tests recorded the red state; the reconciled verifier then
  detected the old global default ACL before apply and passed only after the
  full safe-order correction. Focused tests now cover exact ACL, policy,
  membership, endpoint, identifier, password, and secret preflight contracts.
- Boundary: no legacy `DATABASE_URL`, API/runtime route, push, or remote Git
  state was changed. The unused Homebrew default cluster remains stopped.
