# C6 protected evidence encryption/redaction

**Status:** not started. Last reconciled 2026-08-22 after C5 implementation
commit `98c2f09`; a later docs-only commit may be the Actual Git HEAD.

## Goal

Turn the existing protected-reference metadata into one executable,
tests-first encryption/redaction contract without adding runtime/API routing or
claiming that all of Slice C is complete.

## Verified starting surface

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

## Open decisions — do not assume silently

- Which value is protected in this slice: the locator, an inline payload, or a
  separately owned reference record. Do not add a new payload table or object
  store adapter without repository evidence and a bounded contract.
- How `encryption_profile` maps to the existing key abstraction, including
  unknown-profile and missing-key behavior. A metadata string alone is not
  encryption.
- Which non-API boundary executes `redaction_profile` while Slice D/API wiring
  remains out of scope. Unknown profiles and restricted evidence must not fall
  back to raw output.
- Whether migration `028` is appropriate. Resolve this from fresh `alembic
  heads`; `027` is the current head only at baseline `98c2f09`.

## Candidate owner files

Inspect before editing; this list is a boundary, not permission to change every
file:

- `resolution/domain/evidence.py`
- `resolution/adapters/postgres.py`
- `db/models.py` and `db/crypto.py`
- the next additive Alembic revision, only if storage changes require it
- `tests/test_encryption.py`, `tests/test_resolution_case_domain.py`, and the
  focused Resolution PostgreSQL integration contract

## Required verification

- Demonstrate a focused failing test before implementation and retain the red
  evidence.
- Prove the selected durable value is not stored as plaintext and round-trips
  only through the intended key/profile contract; missing or unknown protection
  configuration fails closed without leaking the value.
- Prove deterministic redaction for the selected safe boundary and no raw
  fallback for restricted/unknown profiles.
- If schema changes, run a real-PostgreSQL upgrade/downgrade catalog contract,
  preserve C3 RLS, C4 immutability, and C5 temporal exclusion, then run the full
  migration round trip on a disposable database.
- Run scoped Ruff/format, strict MyPy, schema/head checks, the focused tests,
  and one proportional independent Resolution/docs gate. Remove every
  disposable database, role, and keepalive afterward.

## Non-goals

- Restore smoke or backup policy changes
- Production runtime-role provisioning or grants
- API/runtime/export endpoint wiring or Slice D
- Object-store rollout, retention deletion, or knowledge-plane tables
- Working `rag_assistant` mutation, push, deploy, or live-provider calls

## Done when

- [ ] One explicit protected-reference value and one named redaction boundary
  have tests-first, fail-closed behavior backed by real PostgreSQL evidence.
- [ ] Existing C3–C5 database guarantees remain green, temporary resources are
  removed, and handoff truth distinguishes local C6 completion from the still
  open root Slice C.
