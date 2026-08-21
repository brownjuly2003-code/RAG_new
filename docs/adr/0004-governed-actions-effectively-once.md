# ADR 0004 — Governed actions with effectively-once product semantics

- Status: Accepted for foundation
- Date: 2026-08-21
- Related: `docs/architecture/security-reliability.md`, `docs/architecture/domain-data-model.md`

## Context

External systems cannot participate in the application database transaction. Network timeouts can occur after a remote mutation but before its response reaches the application, so exactly-once execution cannot be promised. Direct LLM tool calls also bypass uniform authorization, confirmation, credential, audit, and postcondition controls.

## Decision

Every connector operation passes through `ActionGateway`. A versioned manifest declares input/output schemas, risk class, scopes, timeout, idempotency support, confirmation rule, postcondition, and optional compensation. A unique tenant-scoped idempotency identity is persisted before dispatch. PostgreSQL outbox and leased workers provide at-least-once delivery; connector idempotency, reconciliation, and postcondition checks provide effectively-once business behavior.

Unknown outcomes move to `reconciliation_required`; they are never blindly retried as new actions and never reported as success. Irreversible actions remain human-approved until a separate risk-tier promotion proves otherwise.

## Consequences

- (+) Denied actions cannot reach connectors.
- (+) Retries, disconnects, and worker restarts reuse the same durable action identity.
- (+) The evidence bundle records policy, consent, request digest, remote identity, and verified end state.
- (-) Every write connector needs idempotency or a reconciliation adapter.
- (-) User-visible completion may wait for asynchronous postcondition verification.

## Reconsider when

No relaxation is allowed for production writes. A connector that cannot provide either idempotency or reliable reconciliation is restricted to read-only or human-operated use.
