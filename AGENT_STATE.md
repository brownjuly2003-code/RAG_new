# Agent State — digest

> **This file is a 100-line digest, not the entry point.**
> Sessions start at [`CURRENT_STATE.md`](CURRENT_STATE.md), then
> [`ROADMAP.md`](ROADMAP.md). Everything else is reached by link.
>
> The old update log is archived at
> [`archive/docs/state/agent-state-2026-03..08.md`](archive/docs/state/agent-state-2026-03..08.md).
> History only; not a work queue.
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

The other half remains blocked: every scenario is still synthetic, the journey
still uses a fixture TMS, and none of the 100 real labelled cases binds a shipment.
Phase B is what changes that.

## Where the numbers stand

| Claim | Reality |
|---|---|
| Resolution scenarios | 17, all synthetic; verified-resolution yield 1/17 |
| Real labelled cases | 100 — labelled 2026-08-25, approved by Julia 2026-09-25 (T-54), **none binding a shipment** |
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
2026-08-25 and was approved on 2026-09-25; B.2/B.3/B.5 wait on owner data
(Q2b), not on agent work.

**Stream GR is required work, not an optional enrichment.** Plan §2: context
precision is computed over cached contexts, so only the retriever moves it, and
the ≥ 0.63 gate (phase C's, carried by GR-1 in plan §5) cannot be met by
generation tuning. Measured over pool `91ce1745…`: baseline 0.5067 at top-5
([GR-0.3](docs/evidence/gr0-bucket-baseline.md)); section coherence as a
narrowing arm 0.5216, while plain top-4 gives 0.5214 at the same coverage — a
smaller `k`, not structure — and 0.63 only with FULL falling 87 → 71
([GR-1a](docs/evidence/gr1a-section-coherence.md)). The cheap structural arm
was tried and does not reach the gate; nor did GR-2/GR-3 (below).
Limit: the eval bucket is 99 `single_hop`, 1 `multi_hop`, 0 `aggregation`,
0 `global` (`6cde0b1`). GR-3 now measures the separate 15-case multi-hop /
aggregation bucket; recall and FULL fell under both graph arms.

**2026-09-21 — GR-3: NO-SHIP-to-default.** Pipeline wiring is
committed at `782f03f`, the retrieval lane at `6e23630`, and pool provenance
guards through `f9ba47a`. GR-1b: 100 cases, precision 0.5475, recall 0.9200,
FULL/PART/MISS 88/8/4; short-context fix `b2db542`. [Report, archived input and
provenance limits](docs/evidence/gr1b-structure-graph.md): NO-SHIP at 0.63,
prefilter 0/100. [Oracle](docs/evidence/gr1b-safe-subset-oracle.md): 0.6780 / 0.9250 with labels and G1 fallback. Query-only control: 0.6268 / 0.7250, NO-SHIP; [diagnosis](docs/evidence/gr1b-query-control.md) finds missing hits outside uncapped top-five. [Stage replay](docs/evidence/gr1b-stage-replay.md): metadata recovered, 100/100 exact; expansion alone 0.5125 / 0.9300, NO-SHIP. [Seed reservation](docs/evidence/gr1b-seed-expansion.md): 0.5472 / 0.9200 with coherence, no gain. [GR-4 structural wiring](docs/evidence/gr4-structural-product-wiring.md) passes HTTP, browser and strict type checks.
Windows: editing and focused checks. Models, full-suite tests,
PostgreSQL integration and containers run on the Mac; no WSL/Docker/VM here. Commits authorized; a push is the owner's decision, asked each time (plan 0′.3). GitHub Actions execute jobs again; CI went green on `45a417a` (2026-10-03, run 37157492007, [CURRENT_STATE](CURRENT_STATE.md)), which met the owner's order of that day — a green CI on HEAD before the quality thread's 2.5 chain; the commits after `f7416ca` were pushed up to `a7bf232` on 2026-10-15 at her word; CI on `a7bf232` went red; its fixes (`83a2158`, `9eb93c9`, `d5328d3`, `af6b905`) were pushed with `c3f0fff` at her word, and CI on `c3f0fff` is green (run 38723502525) ([session log](docs/operations/session-handoff-2026-10-14-small-generators.md)); the commits after it were pushed up to `8850d6a` at her word on 2026-10-15 ([session log](docs/operations/session-handoff-2026-10-15-judge-100.md)), and `9698e54` the same day; since her decisions of that day the active thread is the chat on the production Mac — the time limits lifted to a 3,600-s ceiling (`468224b`), then offer the operator on a timeout and on `human`, time qwen3:1.7b live — in the order [`ROADMAP.md`](ROADMAP.md) gives ([session log](docs/operations/session-handoff-2026-10-15-decisions.md)). Executor since the owner's D12 of 2026-10-04 («ты должен все делать сам»): the session's model, Claude Opus 5.5 — code, tests, documents and checks — with no model of another vendor in any role and MyFlow only when she names it; `CLAUDE.md` says so since 2026-10-05, when she asked to optimize the file, and the [direct GLM runbook](docs/operations/direct-glm-5.3.md) with its Codex fallback predates D12 and is not in force ([session log](docs/operations/session-handoff-2026-10-05-one-model-and-sizes.md)). Mistral's three keys answer 429 with a zero request limit from a Russian and from a Canadian exit alike (2026-09-25), so the owner is checking the account; her route for Mistral is the Mac under AdGuard VPN, her switch, which the Mac's HH job needs off. Leftovers of finished Mac runs were moved, not deleted, to `/Users/julia/RAG_new_archive/2026-09-25/` (`INDEX.md`; owner: «Ничего не удаляй, ненужное - в архив»). GR-2 [builder and extraction preparation](docs/operations/gr2-entity-builder-preparation.md) and [entity retrieval wiring](docs/evidence/gr2-entity-retrieval-wiring.md) verified on synthetic fixtures. Extraction finished 5589/5589 cached, 0 rejected, through digest-pinned local Ollama `qwen2.5:7b` (`845dbda0…`). [GR-2 measurement](docs/evidence/gr2-entity-graph-lane.md) published 2026-09-17: phase C 0.5475 → 0.5487, NO-SHIP at 0.63; graph default unchanged. [GR-3](docs/evidence/gr3-graph-lane-ab.md) measured 2026-09-18/19, published at `4cca363`: phase-C `G2` 0.5487 vs hybrid 0.5067 (FULL 89 vs 87); multi-document bucket recall 0.5000 → 0.4000, FULL 4 → 1; retrieve p95 +8765.2 ms (fail); generation half `not_evidence` (297/300 valid rows) — verdict NO-SHIP-to-default, `RAG_GRAPH_RETRIEVAL` stays `off`, `auto` gate unchanged. Quality gate remains open. **C.4 closed:** [NO-SHIP model decision](docs/evidence/c4-generator-model-decision.md), Qwen3 faithfulness 0.8986 < 0.90, host RAM unknown; default unchanged. **C.3 done:** [HTTP](docs/evidence/c3-contract-shaped-response.md) and [manual copilot](docs/evidence/c3-copilot-contract-draft.md), off; 555 Mac tests. **D.3:** [rerank](docs/evidence/d3-pgvector-rerank.md): final precision 0.4610/0.4729. **D.2 outlier closed** as a bounded replay: retained original index non-monotonic (ef_search 100 0.20; ef 40 and 200 both 20/20), fresh rebuild 20/20 across the measured grid, no pgvector/HNSW root cause claimed ([capsule](docs/evidence/d2-pgvector-ann.md)); retained scratch DB kept; **D.4 (2026-09-25): measured** — [capsule](docs/evidence/d4-pgvector-graph-evidence.md) published at `25c21e4`: 10300 nodes / 17327 edges reload with an identical persisted contract, 5589 chunk nodes join 5589 synthetic evidence rows, RLS forced on four tables with 0 cross-tenant rows; **D.5 (2026-09-25): measured** — [capsule](docs/evidence/d5-pgvector-cold-start.md) published at `e0c1b3c`: median first result 85.7 ms PostgreSQL vs 1494.7 ms Chroma/BM25, client resident set 68,644,864 vs 310,738,944 bytes (backend 98,246,656 apart), Chroma answers changed across restarts in 13 of 115 cases; Phase D measured, ADR 0007 accepted: retain the current backend. **Chroma restart (2026-09-25): measured** — [capsule](docs/evidence/chroma-restart-stability.md) published at `49db561`: production's write path leaves 128 of 5589 records to the write-ahead log; trials 0–4 and 6 answered all 115 cases as the build did, trial 5 changed case 93's candidate set; no default changed, the fix is a separate slice. **Chroma restart fix (2026-09-25): done** — `534612e`: `build_staged_collection` passes `collection_configuration={"hnsw": {"sync_threshold": 1}}`, proven by `tests/test_chroma_restart_e2e.py` (a second Python process returns the same whole candidate pool and the same `/api/ask` context and sources); [rerun capsule](docs/evidence/chroma-restart-stability-after-fix.md) published at `4e4273d`: log 5589, persisted 5589, tail 0; all seven trials answered all 115 cases as the build did. Collections built before `534612e` keep their tail until rebuilt. **P1 adaptive-k (2026-09-24): measured, NO_SHIP** — held-out H precision 0.5372 vs valid `top_k_5` control 0.5067, FULL/PART/MISS 86/6/8 vs 87/7/6; precision gate 0.63 not met; label-using oracle 0.6505 (not deployable). [Capsule](docs/evidence/p1-adaptive-k.md) published at `2edf19a`. H-relative exploratory on 100 agent-authored `agent_labelled` cases (0 approved), phase-C harness without parent-window expansion; P1 is offline and product behaviour is unchanged. **P1b (2026-09-24): measured, NO_SHIP** — under production expansion `rel_0.2+exp` 0.5975 vs expanded `top_k_5+exp` control 0.5768, FULL/PART/MISS 96/2/2 vs 97/2/1, one fact loss; gate 0.63 not met. [Capsule](docs/evidence/p1b-expanded-cut.md) published at `c5f1d31`; offline, no product change.

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
