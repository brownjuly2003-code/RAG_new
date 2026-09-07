# Agent State — digest

> **This file is a 100-line digest, not the entry point.**
> Sessions start at [`CURRENT_STATE.md`](CURRENT_STATE.md), then
> [`ROADMAP.md`](ROADMAP.md). Everything else is reached by link.
>
> The 12 327-line update log that used to live here (Update-1 … Update-239,
> 2026-03 … 2026-08, 678 KB) is archived verbatim at
> [`archive/docs/state/agent-state-2026-03..08.md`](archive/docs/state/agent-state-2026-03..08.md).
> It is history, not routing: nothing should be planned from it.
>
> Kept at this path because `scripts/autopilot.ps1` reads it as planner
> context. Autopilot may write here; it may not grow this file back into a log.

## What this repository is

`D:\RAG_new` is a clone of `RAG_Support_Assistant` at `bd07179`, built to the
brief in `D:\New_steps\rag.md`. It carries the inherited RAG runtime as a
migration baseline plus a new deterministic resolution kernel
(`resolution/`, `knowledge/`, `actions/`, `services/session.py`, migrations
024–031).

**Remote since 2026-08-24:** `brownjuly2003-code/RAG_new`, private, with the
freeze tag `freeze-2026-08-23` on the state the audit describes.

## The single most important fact

Until 2026-08-24 the kernel was **not wired into the product** — the grep
below returned nothing, `/api/ask` had not changed since the fork, and every
kernel slice was proven by its own tests against synthetic fixtures rather
than by any user-visible behaviour change. That inversion of the critical path
is finding FIN-01/FIN-02 of
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md).

```
grep -rlE "from (resolution|knowledge|actions)|services\.session" api/   # api/routers/conversation.py
```

**Phase A has closed the wiring half** (2026-08-25): `/api/ask` runs the
shipment-status journey as a read-only shadow behind
`RESOLUTION_SHADOW_JOURNEYS`, off by default, and what it observes reaches both
the trace and the resolution tables. `services.session` is wired too, behind
`SESSION_DURABLE_TURNS` and also off by default — the endpoint takes a durable
turn around the request and the message pair is written by the transaction
that ends it (A.2). Both files the grep names now have production callers.

The other half is untouched: every scenario is still synthetic, the journey
still runs against a fixture TMS, and real labelled cases are still zero.
Phase B is what changes that.

## Where the numbers stand

| Claim | Reality |
|---|---|
| Resolution scenarios | 17, all synthetic; verified-resolution yield 1/17 |
| Real labelled cases | 0 — 100 labelled 2026-08-25, none approved, **none binding a shipment** |
| Judge calibration set | 10 cases |
| Release machinery on top | 7 layers (G1–G8) |

Phase B of the plan is the correction: 100 real labelled air-cargo cases
before any further release machinery. B.1 labelled all 100 on 2026-08-25 and
found that none of them names a shipment, so the corpus cannot start a journey
and cannot produce a resolution number — the remaining phase-B items are
blocked on data rather than on work. See `CURRENT_STATE.md` §1.

## Current work

Active plan: [`plan_06_09_26.md`](plan_06_09_26.md), mode B (evidence of
engineering maturity, then publication). Phase 0 and phase A are done — every
phase-A item landed on 2026-08-25 — and phase B is open: B.1 (labels) landed
the same day, B.2/B.3/B.5 are blocked on data. See
[`CURRENT_STATE.md`](CURRENT_STATE.md) for the live status and
[`ROADMAP.md`](ROADMAP.md) for what is frozen.

**Slice acceptance rule (binding, including for autopilot):** a slice counts
only if it changes observable `/api/ask` or UI behaviour with an E2E test, or
adds real labelled cases, or changes a published quality number with
provenance. "Locally complete" is preparation, not a slice.

## Frozen

Trust Foundation steps 5–10, G9+, REL-03D, MCP connectors, framework-grade
GraphRAG (LightRAG / MS GraphRAG / Neo4j), enterprise DoD (2 replicas, SBOM, SOC2-shaped gates). Unfreeze conditions are
in [`ROADMAP.md`](ROADMAP.md). Do not restart them for completeness.

## History, if you need it

- Update log 2026-03 … 2026-08 — [`archive/docs/state/agent-state-2026-03..08.md`](archive/docs/state/agent-state-2026-03..08.md)
- Session handoff capsules — [`archive/docs/sessions/`](archive/docs/sessions/)
- Slice evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Audits — [`docs/audits/`](docs/audits/)
