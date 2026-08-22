# C6 protected evidence encryption/redaction

**Status:** complete locally in the current scoped slice over baseline HEAD
`1b57427`. The final implementation/docs SHA must be read from Actual Git.
This is not a production/release-ready claim.

## Goal

Implement one executable, tests-first encryption/redaction contract for the
existing protected-reference abstraction without adding runtime/API routing or
claiming that all of Slice C is complete.

## Tests-first baseline

- `resolution/domain/evidence.py` defines `ProtectedEvidenceReference` with
  `storage`, `locator`, `encryption_profile`, `redaction_profile`, and
  `retention_class`. Durable storage rejects a missing `encryption_profile`;
  `DEVELOPMENT_FILE` is the explicit development exception.
- `db/models.py` and revision `024` store `reference_locator` as plaintext
  `String(512)`. The two profile fields are metadata strings. Revision `027`
  changes only temporal exclusion behavior.
- `resolution/adapters/postgres.py` maps the locator and profile fields to and
  from the ORM record without encryption or profile execution.
- `db/crypto.py` provides the existing PostgreSQL `pgcrypto`-backed
  `EncryptedText`, obtaining `DB_ENCRYPTION_KEY` through settings. Existing
  tests cover other sensitive columns, not evidence references.
- `utils/pii.py` provides a generic pattern-based PII masker. It does not
  dispatch named Resolution `redaction_profile` values, and no Resolution
  evidence export/profile executor exists in the current C1–C5 surface.

The baseline-red was captured in a detached worktree before implementation:

- two domain unknown-profile tests failed with `DID NOT RAISE`;
- the ORM locator contract failed once because it found `String` instead of
  `EncryptedText`;
- redaction test collection failed with `ModuleNotFoundError`.

The detached worktree was removed after preserving this evidence.

## Delivered contract

- C6 protects only `evidence_snapshots.reference_locator`. It uses the
  existing PostgreSQL `pgcrypto`-backed `EncryptedText` and
  `DB_ENCRYPTION_KEY`; no new evidence payload table or object-store adapter
  was added.
- Domain validation accepts only
  `encryption_profile=tenant-envelope-v1` for durable storage. Unknown
  profiles fail closed.
- Additive revision `028` migrates
  `reference_locator VARCHAR(512) -> BYTEA`, restores
  `BYTEA -> VARCHAR(512)` on downgrade, and adds a fail-closed
  protection-profile `CHECK`.
- The non-API `customer-safe-v1` application boundary emits exactly
  `id`, `digest`, `visibility`, and `profile`. Unknown profiles,
  `restricted`, and `support-only` evidence fail closed without exposing
  the locator.

## Verification evidence

- Implementation-focused gate: **22 passed**; Ruff, format, and diff check
  green.
- Primary independent behavior/docs/PostgreSQL batch: **46 passed**.
  A non-overlapping contract-schema coverage append added **13 passed**, for
  **59 passed** total. The only warning was the existing Starlette warning.
  Coverage for `resolution` was **81.91%**, above the 72% gate.
- Strict MyPy passed for **18 source files**; Ruff/format passed for **11
  files**; schema check passed; Alembic reported the single head `028`.
- A full disposable PostgreSQL
  `base -> 028 -> base -> 028` round trip passed and retained exactly **23
  tables**. C3 RLS, C4 append immutability, and C5 temporal constraints
  remained green.
- Cleanup finished with `DB_COUNT=0`, `ROLE_COUNT=0`, and the keepalive
  stopped. `rag_assistant` and production were untouched.
- The QA writer was stopped at its 6/6 poll limit without code changes or
  final findings. One precisely identified leftover disposable QA DB/role was
  then removed.

## Non-goals

- Restore smoke or backup policy changes
- Production runtime-role provisioning or grants
- API/runtime/export endpoint wiring or Slice D
- Object-store rollout, retention deletion, or knowledge-plane tables
- Working `rag_assistant` mutation, push, deploy, or live-provider calls

## Done when

- [x] One explicit protected-reference value and one named redaction boundary
  have tests-first, fail-closed behavior backed by real PostgreSQL evidence.
- [x] Existing C3–C5 database guarantees remain green, temporary resources are
  removed, and handoff truth distinguishes local C6 completion from the still
  open root Slice C.

## Next routing

C6 is complete locally, but root Slice C remains open. The next one atomic
slice is **C7 Resolution restore smoke on disposable PostgreSQL**. Production
runtime-role provisioning/grants remain later work outside C7. Do not fold
API/runtime routing, Slice D, push, deploy, or production mutation into C7.
