# ADR 0005 — LangGraph is a bounded reasoning runtime, not the resolution authority

- Status: Accepted for foundation
- Date: 2026-08-21
- Related: `agent/graph.py`, `services/pipeline.py`, `docs/architecture/system-architecture.md`

## Context

LangGraph supports persistent checkpoints and human-in-the-loop interrupts, but resumed nodes may replay work and therefore require idempotent side effects. The inherited graph has no durable case aggregate and currently owns answer routing through a broad `GraphState`. Resolution policy and external side effects need stronger invariants than graph execution order.

## Decision

The resolution kernel calls LangGraph through a `ReasoningPort` for bounded tasks such as intent candidates, field extraction, retrieval planning, claim drafting, and response phrasing. Inputs and outputs are typed, budgeted, and treated as untrusted proposals. The kernel persists the authoritative case version before and after the call.

No connector write, policy allow/deny, confirmation transition, or postcondition decision occurs inside an LLM node. LangGraph checkpoints may later support resumable conversational work, but PostgreSQL case/action records remain authoritative and all pre-interrupt side effects must be idempotent.

## Consequences

- (+) Reasoning models and graph topology can change without changing business state semantics.
- (+) Deterministic scenarios can replace `ReasoningPort` with fixtures.
- (+) Current graph functionality can be reused while the hotspot is decomposed gradually.
- (-) Some graph state is duplicated as normalized case/evidence data; explicit mapping is required.
- (-) The response path adds validation and compilation stages after generation.

## Reconsider when

LangGraph may own more orchestration only if its durable store, replay behavior, and concurrency semantics are proven equivalent to the case aggregate invariants. It still must not become the policy enforcement point or connector trust boundary.
