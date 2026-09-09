# Roadmap — RAG_new

Status of every stream. Anything marked **frozen** stays frozen until its
unfreeze condition is met — not "until there is time", and not for
completeness. Source: [`plan_06_09_26.md`](plan_06_09_26.md) (supersedes
`archive/docs/plans/plan-2026-08-23.md`).

WIP limit: **one thread at a time**, except that phases A and B may run in
parallel (A does not wait on Julia; B does).

## Active

**Phase A is done.** A.1 + A.5 landed on 2026-08-25 and are the first
slice this repository has had under rule (a): a shipment-status question
through the real `/api/ask` leaves an evidence bundle in the trace, read back
out of the trace store. A.4 closed with it, and A.1b put the same evidence
into the resolution tables where it can be queried.

**A.2 and A.3 landed the same day.** A.2 is the second slice under rule (a): `/api/ask` takes a durable session turn behind
`SESSION_DURABLE_TURNS`, so a session answers one request at a time and its
message pair is written by the transaction that ends the turn; the
process-wide database cooldown became per-tenant and bounded with it. A.3 is
the third: `GET /api/admin/traces/{id}/evidence` and the Evidence tab beside
Raw JSON, where a reviewer reads the contract, the policy decision, each claim
next to the evidence under it with its age, and the replay receipt. Building
it found that the shipment-id extractor could not match any id the fixture TMS
holds, so every bundle behind `/api/ask` had been empty; fixed with an
end-to-end test that sees a completed journey.

Both of FIN-01's unwired halves — `resolution/` and `services/session.py` —
now have production callers.

**Phase A then gained an admission gate and a measured number** (2026-08-27).
The shipment-status journey now decides whether a request is its own before
it asks for an id (`6651964`), that decision is scored against
`label.journey` on the 100 labelled cases (`36d4269`), and the vocabulary
has a Russian half built as a translation of the English one (`bd82297`).
Over the 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved, admission recall is **0.0000**
([capsule](docs/evidence/a6-journey-admission-and-clarification.md)).
The shadow remains read-only. T-03 now lets `/api/ask` project only its
`CLARIFICATION_REQUIRED` terminal behind the independent, default-off
`RESOLUTION_CLARIFICATION_JOURNEYS` allowlist; both allowlists must name the
journey. Declines, other terminals and failures keep the legacy response.
T-04 makes the operator-visible side explicit: Evidence now distinguishes a
disabled shadow, a declined journey and producer failure while a decline still
calls neither source nor policy and never enters resolution persistence.

**Phase B has started, and B.1 changed the shape of the rest of it.** All 100
air-cargo cases carry a journey, an expected outcome and a root cause
([capsule](docs/evidence/b1-aircargo-journey-labels.md)). The corpus cannot
produce a verified-resolution number at all, now for **three independent
reasons** rather than one: no case names a shipment; the corpus is Russian
and the gate's vocabulary was English; and with the language removed, over
the 100 agent-authored-over-real-documents cases, still `agent_labelled`
and 0 approved, admission recall is still 0.0000 — the corpus contains no
case this journey should admit.
**B.2, B.3 and B.5 are blocked on data, not on work** — the brief's own
NO-GO check (§15) is what fired. The labels themselves stay `agent_labelled`
until a batch of 20 is approved (Q2); ADR 0008 decided that fallback in
advance and the code enforces it.

**Phase C.1 has a measured baseline** (2026-08-30). Qwen 2.5 7B completed
3 × 100 cases on the Mac with zero failures. LLM faithfulness is 0.8295,
NLI faithfulness 0.8919 and context precision 0.5067; the checked-in report
pins the corpus, cached contexts, source SHA, model digest and full config.
The baseline misses both phase-C thresholds, but it is not a model decision:
C.1 remains open for the two Qwen3 candidates under the same benchmark
contract.

Both inherited CI failures ([ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md))
are closed, and CI is green end to end through A.5 / the latest pushed
state: run 34374312654 on `53c24f5` finished `success`, 11 of 11 jobs. The chromadb CVE
ignores carry a **review date of 2026-09-24**.

| Phase | What | Acceptance |
|---|---|---|
| **0** | Freeze, publish, truth about gates | root ≤ 8 md, remote exists, CI status known, pricing/README/eval-gate claims true |
| **A** | Wire the shipment-status shadow into `/api/ask` | rule (a): E2E test on real endpoint behaviour + evidence bundle + replay receipt |
| **B** | 100 real labelled air-cargo cases | rule (b): corpus v1.0 at `evidence_class: real_labelled`, ≥40 double-annotated calibration routes. B.1 done (`agent_labelled`); B.2/B.3/B.5 blocked on data, now for three reasons rather than one |
| **C** | Quality leverage: Qwen3 benchmark, NLI second judge, claim-level compilation | rule (c): faithfulness ≥ 0.90 and precision ≥ 0.63 over 3 runs with a CI, **or** a NO-SHIP report with a cause |
| **GR** | Graph retrieval: structure graph (0 LLM calls) → entity graph → A/B → wired behind flags. Unfrozen 2026-09-06 | rule (c): published context precision / multi-hop coverage with provenance per step; rule (a): graph lane behind `RAG_GRAPH_RETRIEVAL` with an E2E test; `auto` default only after GR-3 |
| **D** | pgvector spike, ADR 0007 — now measured against the graph tables too | a table of numbers in the ADR; no migration without it |
| **E** | Public artefact: README-first, 3-minute demo, `resolution-contracts` sub-package | repo public, CI green, numbers in README |

Heavy runs (models, full suite, Docker) go to the iMac or Colab — never the
Windows laptop. See Q3 in the plan.

## Frozen

| Stream | Why frozen | Unfreeze condition |
|---|---|---|
| Trust Foundation steps 5–10 | Release machinery on synthetic fixtures; the missing input is real data, not more layers | Phase B produces 100 real labelled cases |
| G9+ | Same — G1–G8 already exceed what 17 synthetic scenarios can support | Phase C publishes real numbers |
| REL-03D (per-turn response replay) | Needed for a durable-HTTP story that has no consumer | A design partner asks for it |
| Durable HTTP semantics (`Idempotency-Key`, `ETag`/`If-Match`, 428/412/409/503), 2-replica floor | Enterprise DoD without an enterprise | A design partner appears |
| SSE as a projection of persisted events; removing the direct-stream path | Full FIN-04 close is a rewrite; the shadow path in phase A does not need it | Conditional track |
| Service accounts, forced RLS on legacy `sessions`/`messages`, JWT `iss/aud/iat/jti` + rotation | Full FIN-12; only the cheap Origin fix was in scope for phase 0 | Conditional track |
| Helm production hardening (encrypted backup fail-closed, restore drill, NetworkPolicy, PDB, digest pin, SBOM/SLSA) | FIN-15; no deployment target | A real deployment |
| MCP connectors, vector-DB swap, model swap, microservices/Kafka/OPA, new channels, new dashboards | Stop-list — none is on the critical path to a wired, measured, published system | Explicit decision by Julia |
| Framework-grade GraphRAG (LightRAG, MS GraphRAG, community summaries, Neo4j) | Still frozen. **GraphRAG as such was unfrozen on 2026-09-06 by Julia's decision** and scoped as stream GR — an in-repo structure + entity graph used to narrow and route retrieval ([`plan_06_09_26.md`](plan_06_09_26.md) §4–5). The reason is measured: the phase-C precision gate (0.5067 → ≥ 0.63) is computed over cached contexts and can only be moved by the retriever | ADR 0001 scale trigger (> 50 000 chunks per tenant) or a measured GR-3 failure on the `global` class |
| God-module refactor (FIN-16) | Large refactor before convergence loses more than it gains | After phases A–C converge |

## Conditional track

Everything in the "frozen / conditional track" rows above becomes live **only**
on an external trigger: a design partner, or a real deployment. Not on an
agent's judgement that the system would be more complete with it.

## How this file is used

An agent that wants to start work on a frozen stream has misread the state.
The answer is in [`CURRENT_STATE.md`](CURRENT_STATE.md) — take the next
action there instead.
