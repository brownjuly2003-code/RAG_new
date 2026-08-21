# ADR 0002 — Deterministic resolution kernel in a modular monolith

- Status: Accepted for foundation
- Date: 2026-08-21
- Related: `docs/architecture/system-architecture.md`, `D:\New_steps\rag.md`

## Context

The inherited runtime concentrates conversation, retrieval, generation, safety, tool use, and routing in `GraphState` and a 4,133-line `agent/graph.py`. The new product needs durable case state, immutable procedures, deterministic policy enforcement, confirmations, action reconciliation, and business postconditions. Adding those as more graph fields and branches would make a probabilistic orchestration object the owner of transactional business semantics.

The current deployment is one FastAPI process plus Celery workers, PostgreSQL, Redis, Chroma, and observability components. There is no measured independent-scaling or organizational boundary that justifies distributed services.

## Decision

Create a deterministic `resolution` kernel with domain types and ports, packaged in the existing deployable application. Keep transport, LLM/RAG, storage, policy, and connector implementations outside the domain package. The kernel owns legal state transitions and returns commands/events; adapters perform I/O.

Initial modules are `resolution`, `knowledge`, `policies`, `actions`, and `evaluation/resolution`. They share one PostgreSQL transaction boundary where consistency requires it. Extraction to a service requires a measured SLO, ownership, isolation, or deployment need and a new ADR.

## Consequences

- (+) Case, evidence, policy, and action state can be changed atomically.
- (+) Unit and scenario tests run without an LLM, network, Chroma, or Celery.
- (+) Existing API and agent paths can be adapted gradually in shadow mode.
- (+) A later service split has named ports and event contracts.
- (-) The deployable remains larger and shares process resources; capacity budgets must isolate reasoning and action workers.
- (-) Module boundaries require import checks and review discipline because Python cannot enforce them alone.

## Reconsider when

Extract a module only when production measurements show independent scaling, fault isolation, data sovereignty, or team ownership that cannot be met inside the modular monolith.
