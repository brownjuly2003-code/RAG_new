# Roadmap — RAG_new

Status of every stream. Anything marked **frozen** stays frozen until its
unfreeze condition is met — not "until there is time", and not for
completeness. Source: [`plan_23_08_2026.md`](plan_23_08_2026.md).

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
now have production callers. **Next is phase B**, which needs Julia (Q2) and
has a decided fallback if she is unavailable.

Both inherited CI failures ([ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md))
are closed, and CI is green end to end for the first time. The chromadb CVE
ignores carry a **review date of 2026-09-24**.

| Phase | What | Acceptance |
|---|---|---|
| **0** | Freeze, publish, truth about gates | root ≤ 8 md, remote exists, CI status known, pricing/README/eval-gate claims true |
| **A** | Wire the shipment-status shadow into `/api/ask` | rule (a): E2E test on real endpoint behaviour + evidence bundle + replay receipt |
| **B** | 100 real labelled air-cargo cases | rule (b): corpus v1.0 at `evidence_class: real_labelled`, ≥40 double-annotated calibration routes |
| **C** | Quality leverage: Qwen3 benchmark, NLI second judge, claim-level compilation | rule (c): faithfulness ≥ 0.90 and precision ≥ 0.63 over 3 runs with a CI, **or** a NO-SHIP report with a cause |
| **D** | pgvector spike, ADR 0007 | a table of numbers in the ADR; no migration without it |
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
| MCP connectors, GraphRAG, vector-DB swap, model swap, microservices/Kafka/OPA, new channels, new dashboards | Stop-list — none is on the critical path to a wired, measured, published system | Explicit decision by Julia |
| God-module refactor (FIN-16) | Large refactor before convergence loses more than it gains | After phases A–C converge |

## Conditional track

Everything in the "frozen / conditional track" rows above becomes live **only**
on an external trigger: a design partner, or a real deployment. Not on an
agent's judgement that the system would be more complete with it.

## How this file is used

An agent that wants to start work on a frozen stream has misread the state.
The answer is in [`CURRENT_STATE.md`](CURRENT_STATE.md) — take the next
action there instead.
