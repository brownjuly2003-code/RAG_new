# Roadmap — RAG_new

Progress against [`PLAN.md`](PLAN.md) — the one plan since 2026-10-17, which alone sets the
order of work — and the register of frozen streams. What is true now:
[`CURRENT_STATE.md`](CURRENT_STATE.md). The full progress log of every earlier stream, with
links to each record, is the previous version of this file:
[`archive/docs/state/roadmap-through-2026-10-17.md`](archive/docs/state/roadmap-through-2026-10-17.md).

Anything marked **frozen** stays frozen until its unfreeze condition is met — not "until there
is time", and not for completeness.

## Progress against PLAN.md

A stage is closed only by the slice rule of [`CLAUDE.md`](CLAUDE.md) — (a) an E2E test of
changed behaviour, (b) more real labelled cases, or (c) a published number with provenance.
Closing a stage fills its row: the date, the commit and the [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) row.

| Stage | What | Mac, h | State |
|---|---|---|---|
| 0 | One plan | — | **done 2026-10-17** — `PLAN.md` pushed in `3e52a02`; accepted by Julia the same day («принять») |
| 1 | Fixes first (Julia: «поставить в приоритет»): a repeatable audit; the defects found — loaders, chunk header, table headers, overlap on expansion, answer in the question's language; external tenants proven on the hybrid path; the indexes of the four corpora rebuilt as a new generation; the tools of stage 2 | 12–15 | **done 2026-10-18** — audit, fixes and stage-2 tools `8f94d84`…`4ca5ddd`, [spec](docs/specs/stage1-fixes.md); the second index generation built at `e5e135a` (10 h 01 min); the check after the fixes passed on V3 (record `0636ea3`); [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) row «Stage 1 of `PLAN.md` closed» |
| 2 | Four corpora on the fixed code: 100 aircargo answers on the chat path, retrieval without generation on 400 questions, 300 judged answers on the three external bases («Вариант B»), the graph lane on aircargo | 41–49 | — |
| 3 | Handover signals on the 100, reading, one signal chosen and wired | 5–34 | — |
| 4 | Speed and memory on the Mac; the final path; time to first word; Julia's SLO | 14–17 | — |
| 5 | External answers again — only if stage 4 changed the answer path | 0–30 | — |
| 6 | Production as a service between measurements; capacity; the question log at her word | 3–5 | — |
| 7 | Retrieval mechanisms, the graph included, on end metrics | 3–70+ | — |
| 8 | Publication — Julia's gate | — | — |

## Earlier streams

Streams 0, A, B, C, D, E, GR, P1/P1b/P2, the quality thread Q and the chat thread M, and what
became of each: [`PLAN.md`](PLAN.md) §7. In one line each: 0 and A done (phase A wired a
deterministic resolution kernel behind `/api/ask`); B labelled 100 real aircargo cases and is
blocked on shipment data (Q2b, [`PLAN.md`](PLAN.md) §6); C benchmarked generators, the model is
Julia's choice of 2026-10-16; D closed by ADR 0007; E prepared the public site, publication is
stage 8; GR measured, NO-SHIP by default, re-measured in stages 2 and 7; Q stopped, its useful
parts reused; M steps 1–4 done, steps 5 and 6 are stages 2–4.

## Working limits

- **One measurement on the Mac at a time**; work without the Mac runs beside it
  ([`PLAN.md`](PLAN.md) §5). Time numbers count only from an idle Mac.
- **Heavy runs (models, the full suite, Docker) go to the Mac** — never the Windows laptop. No
  WSL, Docker or VMs on Windows (owner direction, 2026-09-12).

## Frozen

| Stream | Why frozen | Unfreeze condition |
|---|---|---|
| Trust Foundation steps 5–10 | Release machinery on synthetic fixtures; the missing input is real data, not more layers | Phase B produces 100 real labelled cases — literally met 2026-09-25; [`PLAN.md`](PLAN.md) §9 proposes a new condition, Julia's to decide |
| G9+ | Same — G1–G8 already exceed what 17 synthetic scenarios can support | Phase C publishes real numbers — literally met 2026-09-11; the same proposal |
| REL-03D (per-turn response replay) | Needed for a durable-HTTP story that has no consumer | A design partner asks for it |
| Durable HTTP semantics (`Idempotency-Key`, `ETag`/`If-Match`, 428/412/409/503), 2-replica floor | Enterprise DoD without an enterprise | A design partner appears |
| SSE as a projection of persisted events; removing the direct-stream path | Full FIN-04 close is a rewrite; the shadow path in phase A does not need it | Conditional track |
| Service accounts, forced RLS on legacy `sessions`/`messages`, JWT `iss/aud/iat/jti` + rotation | Full FIN-12; only the cheap Origin fix was in scope for phase 0 | Conditional track |
| Helm production hardening (encrypted backup fail-closed, restore drill, NetworkPolicy, PDB, digest pin, SBOM/SLSA) | FIN-15; no deployment target | A real deployment |
| MCP connectors, vector-DB swap, model swap, microservices/Kafka/OPA, new channels, new dashboards | Stop-list — none is on the critical path to a wired, measured, published system | Explicit decision by Julia |
| Framework-grade GraphRAG (LightRAG, MS GraphRAG, community summaries, Neo4j) | Still frozen. **GraphRAG as such was unfrozen on 2026-09-06 by Julia's decision** and scoped as stream GR — an in-repo structure + entity graph used to narrow and route retrieval ([`plan_06_09_26.md`](archive/docs/plans/plan_06_09_26.md) §4–5). The reason is measured: the phase-C precision gate (0.5067 → ≥ 0.63) is computed over cached contexts and can only be moved by the retriever | ADR 0001 scale trigger (> 50 000 chunks per tenant) or a measured GR-3 failure on the `global` class — neither can fire today (largest base 37,571 chunks; 0 `global` cases); [`PLAN.md`](PLAN.md) §9 proposes one |
| God-module refactor (FIN-16) | Large refactor before convergence loses more than it gains | After phases A–C converge — C never converged; [`PLAN.md`](PLAN.md) §9 proposes after stage 6 |


## Conditional track

Everything in the frozen rows above becomes live **only** on an external trigger: a design
partner, or a real deployment. Not on an agent's judgement that the system would be more
complete with it. Whether production on `deproject-mac` (Julia, 2026-10-14) is such a
deployment is hers to say ([`PLAN.md`](PLAN.md) stage 6); until she does, nothing here
unfreezes on it.

## How this file is used

An agent that wants to start work on a frozen stream has misread the state. The next action is
in [`CURRENT_STATE.md`](CURRENT_STATE.md) («Next») and [`PLAN.md`](PLAN.md) §5.
