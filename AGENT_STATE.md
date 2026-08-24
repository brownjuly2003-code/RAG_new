# Agent State — digest

> **This file is a 100-line digest, not the entry point.**
> Sessions start at [`CURRENT_STATE.md`](CURRENT_STATE.md), then
> [`ROADMAP.md`](ROADMAP.md). Everything else is reached by link.
>
> The 12 327-line update log that used to live here (Update-1 … Update-239,
> 2026-03 … 2026-08, 678 KB) is archived verbatim at
> [`docs/archive/agent-state-2026-03..08.md`](docs/archive/agent-state-2026-03..08.md).
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

**There is no git remote.** 909 commits exist in exactly one place.

## The single most important fact

The kernel is **not wired into the product**. As of 2026-08-24:

```
grep -rlE "from (resolution|knowledge|actions)|services\.session" api/ agent/   # empty
```

`/api/ask` has not changed since the fork. Every kernel slice so far is
proven by its own tests against synthetic fixtures, never by a user-visible
behaviour change. That inversion of the critical path is finding FIN-01/FIN-02
of [`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
and it is what the current plan exists to correct.

## Where the numbers stand

| Claim | Reality |
|---|---|
| Resolution scenarios | 17, all synthetic; verified-resolution yield 1/17 |
| Real labelled cases | 0 |
| Judge calibration set | 10 cases |
| Release machinery on top | 7 layers (G1–G8) |

Phase B of the plan is the correction: 100 real labelled air-cargo cases
before any further release machinery.

## Current work

Active plan: [`plan_23_08_2026.md`](plan_23_08_2026.md), mode B (evidence of
engineering maturity, then publication). Phase 0 in progress — see
[`CURRENT_STATE.md`](CURRENT_STATE.md) for the live status and
[`ROADMAP.md`](ROADMAP.md) for what is frozen.

**Slice acceptance rule (binding, including for autopilot):** a slice counts
only if it changes observable `/api/ask` or UI behaviour with an E2E test, or
adds real labelled cases, or changes a published quality number with
provenance. "Locally complete" is preparation, not a slice.

## Frozen

Trust Foundation steps 5–10, G9+, REL-03D, MCP connectors, GraphRAG,
enterprise DoD (2 replicas, SBOM, SOC2-shaped gates). Unfreeze conditions are
in [`ROADMAP.md`](ROADMAP.md). Do not restart them for completeness.

## History, if you need it

- Update log 2026-03 … 2026-08 — [`docs/archive/agent-state-2026-03..08.md`](docs/archive/agent-state-2026-03..08.md)
- Session handoff capsules — [`docs/SESSION_HANDOFF.md`](docs/SESSION_HANDOFF.md)
- Slice evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Audits — [`docs/audits/`](docs/audits/)
