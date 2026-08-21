# ADR 0003 — PostgreSQL authority with rebuildable retrieval projections

- Status: Accepted for foundation
- Date: 2026-08-21
- Related: `docs/architecture/domain-data-model.md`

## Context

Contracts, business-valid time, system-known time, policy decisions, confirmations, side-effect identities, and verified outcomes require transactions, constraints, and durable relationships. Chroma is optimized for similarity retrieval and currently stores tenant-specific chunk projections; it is not an authority for temporal or transactional state. A graph database would add operational cost before a measured query gap exists.

## Decision

PostgreSQL is the system of record for support cases, contract versions, knowledge metadata, evidence, policy decisions, action runs, postcondition results, replay manifests, and transactional outbox events. Chroma remains a versioned, tenant-scoped, rebuildable projection of eligible knowledge versions. Redis remains an optional bounded cache/coordination layer, never the only copy of case state.

Business validity uses PostgreSQL range types and explicit authority/applicability data. RLS supplements application tenant predicates; the runtime connects as a non-owner role, and tenant tables use `FORCE ROW LEVEL SECURITY` where supported by the operational model.

## Consequences

- (+) One transaction can append evidence and advance a case version safely.
- (+) Temporal overlap, uniqueness, foreign keys, and idempotency are database-enforced.
- (+) Chroma can be rebuilt or replaced behind a retrieval port without losing audit truth.
- (-) PostgreSQL schema and index design become release-critical and need real migration/restore drills.
- (-) Large protected evidence payloads may later require an object-store adapter; PostgreSQL retains hashes, metadata, and references.

## Reconsider when

Adopt a graph store only after representative evidence queries miss an agreed SLO or relational traversal becomes the measured bottleneck. Replace Chroma only through the existing retrieval interface and an A/B plus rollback ADR.
