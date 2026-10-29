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
| 2 | Four corpora on the fixed code: 100 aircargo answers on the chat path, retrieval without generation on 400 questions, 300 judged answers on the three external bases («Вариант B»), the graph lane on aircargo (amended 2026-10-19: GR-3's archives counted, the live lane in stage 7) | 41–49 | **done 2026-10-24** — registered 2026-10-19 before the first request ([spec](docs/specs/stage2-four-corpora.md)); 100 aircargo and 300 external answers, 415 retrieval questions, the judge's eight plans (935 requests; `p4-multihoprag-judge-m2` `NOT_EVIDENCE`), the [record](docs/evidence/stage2-record.md) `5d91f47`; [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) row «Stage 2, part 5» |
| 2b | The answer prompt V4 (amended 2026-10-24): three defects of V3 found by stage 2's judge — a decline when the documents answer in part, advice to contact a specialist that no document holds, the placeholder «[N]» — fixed and measured paired against stage 2's answers on WixQA, ConditionalQA and aircargo | 25–34 | **done 2026-10-25, V4 adopted** — [spec](docs/specs/answer-prompt-v4.md) registered in `4f48fed` before the first request; the prompt's E2E test; 300 V4 answers on stand `4f48fed` (≈ 26 h Mac, no path break), 620 judge requests, all eight plans and bridges counted; the [record](docs/evidence/answer-prompt-v4-record.md): the pooled external bad share −9.5 pp, detected; [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) row «Stage 2b» |
| 3 | Handover signals on the 100 (V4's, while V4 stays), reading, one signal chosen and wired | 5–34 | steps 1–3 read 2026-10-26: **outcome C**, S3 in between — the [record](docs/evidence/handover-signal-v4-aircargo.md) (11.5 h of the Mac). Her word on C («да», 2026-10-26): every chat and widget answer carries a handover line with the operator button — done, the operator E2E tests; no stage 2 for S3. The encoder test read 2026-10-26: all three in between, none worth wiring — the [record](docs/evidence/encoder-checkers-record.md) (3.6 h of the Mac). Step 4, the widget on the 4B, read 2026-10-26: R1 confirmed, R2 not seen; of ten answers auto 3, human 2, error_escalation 5 — no retry finished inside the 24-call budget (the [record](docs/evidence/widget-4b-record.md), 5.2 h of the Mac). The encoders' Amendment 1, read 2026-10-28: Horizon guard base in between too — 7 of 17 caught, 7 of 63 over-marked (2.0 h of the Mac); its read on V5's fresh answers `NOT_EVIDENCE`, nothing scored — V5's aircargo judge plan is not counted. Stage 3 stays at outcome C; open: the widget's R1 and retry-budget fixes, her word ([`PLAN.md`](PLAN.md) §8.3, item 1) |
| 3б | An evidence-first answer prompt V5, paired against V4's answers (her «да», 2026-10-26) | 12–18 | **done 2026-10-28, V5 not adopted** — [spec](docs/specs/answer-prompt-v5.md) registered in `47e2d71` before the first request; the 300 answers on stand `4f48fed` (9.8 h of the Mac), the judge graded whole on her word (620 requests, $175.71). The [record](docs/evidence/answer-prompt-v5-record.md): harm on WixQA — bad 51 → 86 of 100, good 40 → 4; three of five plans `NOT_EVIDENCE`, the judge wavering on the visible scaffold; V4 stays, stage 4 goes on with V4 |
| 4 | Speed and memory on the Mac; the final path; time to first word; Julia's SLO (amended 2026-10-26: a diagnostic step 0 and research 6's levers) | 20–28 | step 3's no-reranker point, read 2026-10-26 on stage 2's saved lists: the reranker stays — without it the expanded five hold gold in 121 of 250 questions, not 141 (p 0.004; the [record](docs/evidence/no-rerank-point-record.md)); step 3's K curve, read 2026-10-28 on the same lists without a model: the smallest K without a detected loss is 14, not the forecast's 6 — pooled 136 of 250 against 141 at K = 20 (p 0.125), a median of 24–26 candidates scored instead of 34–36 (the [record](docs/evidence/k-curve-record.md)); step 0, read 2026-10-28 on V4's stand: the host prompt cache is the 4B's growth, 280.69 MiB a request with no state restored in 15, generation does not wait on memory, the weights repacked (the [record](docs/evidence/stage4-step0-record.md)); step 1, measured 2026-10-28 on V4's stand: with the model unloaded the rerank takes a median 0.26 of its time with the model resident (4 pairs, contention yes), net faster by the sign alone (a median −47 s, within the spec's 90 s of zero; a 2–2 split), no lever adopted (the [record](docs/evidence/stage4-step1-record.md)); step 3's live timing of K = 14 against 20, without a model, read 2026-10-28: K = 14 reranks faster on 12 of 12 questions (p 0.000488), a median 14.566 s less, a ratio 0.528, no K adopted (the [record](docs/evidence/stage4-step3-record.md)); step 2, the self-eval as the answer's next turn (her «Оставить, но ускорить», 2026-10-28), read 2026-10-29 on stand `57420db`: the continuation faster on 13 of 13 (p 0.000244), a median 54.009 s saved (8.635 s against 62.691 s), routes agree, scores held — the candidate is the continuation, no default changed (the [record](docs/evidence/stage4-step2-record.md)); step 2b, the continuation cold on stage 3's 80 labelled answers, registered before its first request ([spec](docs/specs/stage4-step2b-continuation-labels.md)), run 19:03–21:18 UTC 2026-10-29 and read: not held, on the catches (0 of 17 flagged, the classic's 2; the continuation scored all 80 at 90 or more), the default stays `classic` (the [record](docs/evidence/stage4-step2b-record.md)); item 5's host-cache cap, `cache-ram = 1024`, her «да» 2026-10-29 |
| 5 | External answers again — only if stage 4 changed the answer path | 0–30 | — |
| 6 | Production as a service between measurements; capacity; the question log at her word | 3–5 | prepared 2026-10-28, nothing installed: a tenant's session store closes after three failures in a row (`3f7b33d`); drafts of the launchd service and of the throughput spec (`1d8558a`), installed and registered on her word |
| 7 | Retrieval mechanisms, the graph included, on end metrics | 3–70+ | her word 2026-10-28, «P1b и граф»: both arms, the entity extraction's cost first. The cost probe registered 2026-10-29 in `52dd160` after Codex's two passes ([spec](docs/specs/stage7-entity-probe.md)), its run next; drafted on the laptop, not registered: step 1's arms replay, H, S and P at M3 on stage 2's lists, with S's expansion fix (uncommitted drafts, the [handoff](docs/operations/session-handoff-2026-10-29-stage4-step2-running.md)) |
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
