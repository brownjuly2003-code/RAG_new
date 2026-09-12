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

Adopted plan (owner's decision, 2026-09-10): [`plan_06_09_26.md`](plan_06_09_26.md),
mode B (evidence of engineering maturity, then publication). Phase 0 and phase
A are done — every phase-A item landed on 2026-08-25. The plan's work (§5, §10)
is **stream GR** and phase C. Phase B is not the front: B.1 (labels) landed on
2026-08-25, and B.2/B.3/B.5 wait on owner data (Q2), not on agent work.

**Stream GR is required work, not an optional enrichment.** Plan §2: context
precision is computed over cached contexts, so only the retriever moves it, and
the ≥ 0.63 gate (phase C's, carried by GR-1 in plan §5) cannot be met by
generation tuning. Measured over pool `91ce1745…`: baseline 0.5067 at top-5
([GR-0.3](docs/evidence/gr0-bucket-baseline.md)); section coherence as a
narrowing arm 0.5216, while plain top-4 gives 0.5214 at the same coverage — a
smaller `k`, not structure — and 0.63 only with FULL falling 87 → 71
([GR-1a](docs/evidence/gr1a-section-coherence.md)). The cheap structural arm
was tried and does not reach the gate; the remaining GR steps are what is left.
Limit: the eval bucket is 99 `single_hop`, 1 `multi_hop`, 0 `aggregation`,
0 `global` (`6cde0b1`), so a per-class A/B on the classes a graph should help
most needs a separate candidate pool for GR-0.2's prepared 15 multi-hop /
aggregation questions. "Needed" is measured; "will work" is not claimed.

**Resume point 2026-09-12 — GR-1b measured.** Pipeline wiring is
committed at `782f03f`, the retrieval lane at `6e23630`, and pool provenance
guards through `f9ba47a`. GR-1b: 100 cases, precision 0.5475, recall 0.9200,
FULL/PART/MISS 88/8/4; short-context fix `b2db542`. [Report, archived input and
provenance limits](docs/evidence/gr1b-structure-graph.md): NO-SHIP at 0.63,
prefilter 0/100. Do not regenerate embeddings. Next: GR-4/GR-2/GR-3.
Windows is for editing and focused checks only. Models, full-suite tests,
PostgreSQL integration and containers run on the Mac; no WSL/Docker/VM here, no push.

**Slice acceptance rule (binding, including for autopilot):** a slice counts
only if it changes observable `/api/ask` or UI behaviour with an E2E test, or
adds real labelled cases, or changes a published quality number with
provenance. "Locally complete" is preparation, not a slice.

## Frozen

Trust Foundation steps 5–10, G9+, REL-03D, MCP connectors, enterprise DoD
(2 replicas, SBOM, SOC2-shaped gates). Unfreeze conditions are in
[`ROADMAP.md`](ROADMAP.md). Do not restart them for completeness.

Graphs are two different things here, and only one is frozen. **Frozen:** the
framework-grade variant — LightRAG / MS GraphRAG / community summaries / Neo4j —
until the ADR 0001 trigger (> 50 000 chunks per tenant, or a measured GR-3
failure on the `global` class). **Live and needed:** stream GR, the in-repo
structure + entity graph of plan §4, unfrozen by the owner on 2026-09-06 and
required for the reason in the section above.

## History, if you need it

- Update log 2026-03 … 2026-08 — [`archive/docs/state/agent-state-2026-03..08.md`](archive/docs/state/agent-state-2026-03..08.md)
- Session handoff capsules — [`archive/docs/sessions/`](archive/docs/sessions/)
- Slice evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Audits — [`docs/audits/`](docs/audits/)
