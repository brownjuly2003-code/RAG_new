# Current state — RAG_new

2026-10-05 · Plan: [`plan_06_09_26.md`](plan_06_09_26.md) (mode B, adopted 2026-09-10) · Quality thread after E: [`docs/specs/plan_03_10_26.md`](docs/specs/plan_03_10_26.md) (2026-10-03 revision of [`plan_final_30_09_26.md`](docs/specs/plan_final_30_09_26.md), which was adopted and ratified by delegation 2026-09-30; decisions D1–D10 in §2, where the owner's D11 of 2026-10-03 — no human work in the plan — changed D2, D3 and D10, and her D12 of 2026-10-04 — the session's model does every job and check, no other vendor's model is called — changed who verifies and judges; final-plan audits [GLM](docs/audits/audit_glm_final_30_09_26.md) and [Astra](docs/audits/audit_astra_final_30_09_26.md) applied to the 2026-09-30 text, the revision itself is unaudited) ·
Audits: [Astra](docs/audits/audit_asta_30_09_26.md), [GLM](docs/audits/audit_glm_30_09_26_plan.md) and [Astra](docs/audits/audit_astra_30_09_26_plan.md) on the plan (2026-09-30) · Phase C source: `c06bdf5` · owner delegated commits and pushes (§1).

## Start here

### Quality thread — adopted and ratified by delegation 2026-09-30, plan revised 2026-10-03

[`plan_03_10_26.md`](docs/specs/plan_03_10_26.md) is the thread after phase E; it supersedes `plan_final_30_09_26.md` (slice status in its §1, changes in its §6: BM25 token normalisation is candidate H11, frozen outside the first campaign with H6–H10 — gap G36; the exploratory lexical-lane study behind it is not evidence and stays outside the repository, in `D:/Rag_research`). Its first executor slice, 2.1/2.2 route observability, is **implemented** (T-59, 2026-10-01; executor GLM 5.3 direct in five one-file requests over the draft patch): `/api/ask` logs a `retrieval_route` trace step (configured/selected/effective strategy with a bounded reason, classifier fields, query transform fingerprint, documents, generation context tokens), the hybrid lane reports its path, and the Evidence endpoint and tab show both — rule (a) by `tests/test_ask_contract_route.py` (HTTP ask → trace → Evidence, 16 cases on a fixture model). T-61 adds the mandatory 2.3 embedder manifest: stamped Chroma collections are checked at load; match/refusal reaches trace and Evidence, same-width substitutions return traced 503, legacy unstamped indexes and unverified revisions are NOT_EVIDENCE; **implemented** 2026-10-02 (T-61, rule (a) on a fixture embedder: `tests/test_ask_embedder_manifest.py`). Development ruler pre-registered in [`semantic-precision-metrics.md`](docs/specs/semantic-precision-metrics.md); the official 0.63 gate is untouched. **Order (owner, 2026-10-03): phase E first — a green CI on HEAD (plan slice 0.1b). That is met: `45a417a`, run 37157492007, 2026-10-03. The 2.5 chain is under way: T-69, the v2 re-judging tooling, is done (no judge called yet); T-67 published the 30-case parity run ([capsule](docs/evidence/production-parity-30-cases.md)); T-70 gave the loss map its baseline mode ([requirement](docs/specs/evidence-loss-map.md)) — no map yet, it is built from the T-65 run; T-65's collection ended on the Mac on 2026-10-05 — 115 cases, none excluded — and its judging by the one judge is part done: 48 of 115 requests answered, stopped at the stop point of 2026-10-05, no process running ([state and resume](docs/operations/t65-baseline-handoff.md)).** **Nothing waits on Julia (her decision D11, 2026-10-03: «люди участвовать в процессе не будут»):** D2 is now κ of the P2 consensus to the Astra and Opus model references (slice 1.1, T-57 — done 2026-10-04); D3 is verification of the 30 [T-64 pilot drafts](docs/evidence/devset-pilot-drafts.md) by a model. **Since the owner's D12 of 2026-10-04 («ты должен все делать сам») one model — the session's Claude Opus 5.5, in stateless requests — does every job and every check; no model of another vendor is called in any role (plan §2, record D12).** Since 2026-10-05 each such request goes by a route that loads nothing beside the registered prompt and keeps a record of its session (`evaluation/isolated_request.py`); a probe showed the earlier route also carrying the owner's instruction file and hook output, which the T-78 and P2 Opus capsules now say. **Slice 1.3b is done (T-78, 2026-10-04, preparation):** [30 verified, 0 dropped](docs/evidence/devset-pilot-label-verification.md) — 25 at the first check, 5 after a repair by the same model, counted apart; status `single_model_verified`. **Step 1.3c is registered (`323ce00`, 2026-10-05, preparation); its variance pilot has not run:** split [`devset_split.json`](evaluation/devset_split.json), development 60 cases in 37 clusters, holdout 64 in 18; the registered MDE of the deciding metrics is 0.17–0.30 — above the +0.05 the decision rule asks for, and the corpus has no more independent families — so the campaign is registered as checking effects of that size, and a mechanism that is neutral on a row is expected to end `INCONCLUSIVE` (spec, «Variance pilot and sizes of plan step 1.3c»). **On the owner's word of 2026-10-05 («пропиши базы в плане, в конкретных слайсах») the plan connects the three external bases of D7 next — slices 1.5 ConditionalQA, 1.5c WixQA, 1.5d MultiHop-RAG, on the Mac right after the 1.3c pilot — and uses them in the tests: parts, a pilot and the role in new slice 1.6, a baseline in new slice 1.7, every comparison of mechanisms on the tuning parts, and the gain line of acceptance 4.1 on a locked part before our holdout opens (plan §2, D7 «Редакция 05.10»). None is connected yet; the deciding role is the agent's reading of her words and takes force only with the spec's eleventh revision; what the bases do not solve is plan gap G39.** For 2.5 the one judge of new texts is Opus 5.5 (`single_judge`, with a stability retest), and the rules and the builder of the baseline report were registered and written before the first grade (`scripts/baseline_report.py`). The P2 ruler is `model-cross-checked`, never `human-validated`; work done after D12 gets neither `model-cross-checked` nor `model_verified`; the drafts stay `agent_labelled`. What replaced what, and what the plan no longer claims: plan §2, record D11; the eight design questions a cold read left open (plan G38) are closed in the spec — the last five in its tenth revision, for one model, chosen by the agent under D12 and read cold twice by new sessions of the same model (the 20 findings of the second read and the 15 of one closed check of the repairs applied), by no other vendor. Session logs: [2026-10-05](docs/operations/session-handoff-2026-10-05-one-model-and-sizes.md) — read it first: what one model can and cannot claim, what the registered sizes can show, and that the commits after `f7416ca` are local and not pushed — and [2026-10-03](docs/operations/session-handoff-2026-10-03-plan-revision.md). `RAG_GRAPH_RETRIEVAL` stays `off`.

### P1 / P1b adaptive-k — measured, NO_SHIP

[P1b capsule](docs/evidence/p1b-expanded-cut.md), `c5f1d31`: on H, `rel_0.2+exp` 0.5975 vs
expanded `top_k_5+exp` 0.5768, delta +0.0207, CI95 [0.0104, 0.0327]; recall 0.9700 vs
0.9800, 96/2/2 vs 97/2/1. One FULL→MISS fact loss: `aircargo-customs-broker-escalation`.
**NO_SHIP:** 0.63 precision gate, coverage-and-facts and held-out (`p1_cv+exp` 0.6062)
fail; no measured arm reaches 0.63. Review floor and Hm (all five kept) hold. Unexpanded
selections reproduce P1; expanded control and `top_k_3+exp` equal Q1's expanded rows.
[P1 capsule](docs/evidence/p1-adaptive-k.md), `2edf19a`: held-out 0.5372 vs control
0.5067 on the phase-C harness without expansion, **NO_SHIP**; label-using oracle for a
cut that keeps every fact at 0.6505 (not deployable). Both are H-relative exploratory on
100 agent-authored `agent_labelled` cases (0 approved), offline with no product change.
**P2 measured:** [GLM + Sonnet blinded judgment](docs/evidence/p2-blinded-relevance-judgment.md), 115/115 cases each; H α 0.8566, primary τ_b 0.1561 (CI95 [0.0197, 0.2880]): `RULER_DOES_NOT_TRACK`.
Model references on the blind ten-case sample: [Opus 5.5 max](docs/evidence/p2-opus-reference-sample.md) and [Astra xhigh](docs/evidence/p2-astra-reference-sample.md) (κ 0.9727 to each other, 0.88–0.91 to GLM/Sonnet). No human grades will be collected (plan D11, 2026-10-03); Mistral returned `zero_limit`. No gate or default changed. **Ruler check without people (slice 1.1, T-57, 2026-10-04):** [κ of the GLM + Sonnet consensus to the references](docs/evidence/p2-model-reference-kappa.md) is 0.9333 to Astra (CI95 [0.8511, 0.9859]) and 0.9604 to Opus (CI95 [0.9087, 1.0000]), bootstrap clustered by case. Both intervals lie entirely above 0.7 — branch 3 of the registered rule: the development ruler is `model-cross-checked`. That is a check by models, never `human-validated`: an error the models share stays undetected. It covers the sample's question classes and the unexpanded top-5 contexts of P2; new classes and expanded contexts need a reference sub-sample of at least 10 cases per class first, so the T-65 baseline stays `provisional_ruler`.

### GR-3 measured — NO-SHIP-to-default

Measured 2026-09-18/19 on `deproject-mac` ([capsule](docs/evidence/gr3-graph-lane-ab.md)): phase-C `G2` 0.5487
vs hybrid 0.5067, FULL 89 vs 87; multi-document bucket recall 0.5000 → 0.4000 and FULL 4 → 1
(both graph arms); retrieve p95 +8765.2 ms vs 200 ms — fail. Generation:
`not_evidence` (297/300 valid; excluded case in capsule).
`RAG_GRAPH_RETRIEVAL` stays `off`. **C.4 closed:** [NO-SHIP of Qwen3](docs/evidence/c4-generator-model-decision.md): faithfulness 0.8986 < 0.90; host RAM unknown.
Default: Qwen2.5, below gate. **C.3 done:** [HTTP](docs/evidence/c3-contract-shaped-response.md) and [copilot](docs/evidence/c3-copilot-contract-draft.md), off; 555 Mac tests. **D.3 measured:** [rerank](docs/evidence/d3-pgvector-rerank.md): final precision 0.4610/0.4729. **D.2 outlier closed as a bounded replay:** retained original index non-monotonic (ef_search 100 0.20; ef 40 and 200 both 20/20), fresh rebuild 20/20 across the measured grid, no pgvector/HNSW root cause claimed ([capsule](docs/evidence/d2-pgvector-ann.md)); **D.4 measured:** [graph/evidence parity](docs/evidence/d4-pgvector-graph-evidence.md), `25c21e4`: 10300 nodes / 17327 edges reload with an identical persisted contract, 5589 chunk nodes join 5589 synthetic evidence rows, RLS forced on four tables with 0 cross-tenant rows; **D.5 measured:** [cold start and memory](docs/evidence/d5-pgvector-cold-start.md), `e0c1b3c`: median first result 85.7 ms PostgreSQL vs 1494.7 ms Chroma/BM25, client resident set 68,644,864 vs 310,738,944 bytes (backend 98,246,656 apart), Chroma answers changed across restarts in 13 of 115 cases; Phase D measured, [ADR 0007](docs/adr/0007-pgvector-spike.md) accepted: retain the current backend. **Chroma restart measured:** [capsule](docs/evidence/chroma-restart-stability.md), `49db561`: production's write path left 128 of 5589 records to the write-ahead log; six of seven restarted processes answered all 115 cases as the building process did, and one changed one case's candidate set; no default changed, the fix is a separate slice. **Chroma restart fixed:** `534612e` persists the whole vector index at ingestion, proven by an end-to-end restart test; the [rerun](docs/evidence/chroma-restart-stability-after-fix.md), published at `4e4273d`, left 0 of 5589 records to the write-ahead log, and all seven restarted processes answered all 115 cases as the build did. Collections built before `534612e` keep their tail until rebuilt.

### Phase C.1a / C.1b generator baselines — measured on Mac

C.1a Qwen2.5 7B (`c06bdf5`; 3 × 100 valid generations, LLM-judge and NLI, zero
failures): LLM faithfulness 0.8295, NLI 0.8919, context precision 0.5067, recall
0.9050, answer relevancy 0.8960, 197.5 s/case; gates missed: faithfulness 0.90,
precision 0.63. [Raw report](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json)
(`measured`; SHA-256 guarded by `tests/test_phase_c_baseline_artifact.py`) carries the
pinned provenance: model `845dbda0…`, dataset `3737d694…`, cached contexts `91ce1745…`,
NLI `8adb042d…`, seeds 42–44, temperature 0; NLI peak RSS 2.12 GB, loaded model 5.06 GB.
**C.1b Qwen3 8B** (2026-09-11): 3 × 100 Mac cases, zero failures; faithfulness 0.8986,
NLI 0.9908, relevancy 0.8095, precision 0.506657, latency 176.81 s.
[Raw report](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json),
[provenance/limits](docs/evidence/c1b-qwen3-generator-benchmark.md): C.4 input; host peak RAM unknown.

### 1. Russian gate wired; resolution unmeasurable

T-01…T-09 closed: [commits/tests](docs/evidence/a6-journey-admission-and-clarification.md).
Authorized push:
`git -c credential.helper='!gh auth git-credential' push origin master`.

Resolution remains unmeasurable ([evidence](docs/evidence/a6-journey-admission-and-clarification.md)):
no case names a shipment; the original gate was English-only; the bilingual
gate has recall **0.0000**, with one `exception_escalation` false positive.
None of the 100 cases belongs to the journey; their labels are `real_labelled` since
Julia approved all five batches on 2026-09-25 (T-54, `73b13b9`). B.2/B.3/B.5 need
data, which the approval cannot supply. Check: `python scripts/aircargo_labels.py verify`.

**Windows:** focused checks only; strict mypy needs numpy 2.4.4. PostgreSQL and
browser checks run on Mac.

## Current facts

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private, tag
  `freeze-2026-08-23` = `26866e9`. Pushes go over HTTPS (command in §1).
- **Phase A closed:** read-only shipment-status `/api/ask`; clarification projects
  only under both default-off allowlists. Disabled/declined/failed stay explicit.
- **100 real labelled cases, none bound to a shipment.** 100/100 approved 2026-09-25,
  0 binding a shipment; all expect `verified`. 201 real documents; agent-written questions
  (`325d63c`, `6b7417d`,
  `32e841f`). Question classes live in a sidecar (`6cde0b1`) — 99 `single_hop`,
  1 `multi_hop`, 0 `aggregation`, 0 `global` (plan §5, GR-0.2).
- **First green CI after the red period: `45a417a`** (2026-10-03): run 37157492007 passed 11 of 11 jobs; Pages run 37157492017 on the same commit built the site (`build` passed; `deploy` skipped: the repository is private, nothing is published). The next push, `1fbbf65`, was green as well (run 37160903526; Pages run 37160903511). A document cannot record the run of its own commit: the status of later commits is on GitHub Actions.
  Run 34359692687 on `69a5140` verified the CVE-2026-9856 floor
  `transformers>=5.10.0` under `--require-hashes`, pip-audit clean.
- **CI was red from `70d272c` (run 37093493571) to `df1bf47` (run 37137697604; Pages run 37137697647)** — observed 2026-10-03, when GitHub Actions executed jobs again. Fixed by T-71…T-74 (`22bb68a`, `f197481`, `ebc343b`, `45a417a`); causes in [plan §1](docs/specs/plan_03_10_26.md).
- **Phase E:** `236f7c1` prepares **RAG assistant** for `/RAG_new/` locally:
  23 tests, `astro check`, 239-page build and five link checks passed.
  `236f7c1` is pushed (in `origin/master`); the repository remains private. The [E.5 capsule](docs/evidence/e5-secret-scan.md)
  records the Mac full suite (3,763 unit + 93 integration passed) and the history scan on
  `c81de77`, rerun 2026-09-30 (late) on `b0386e9`: 3,722 unit + 36 e2e passed on the Mac, history
  scan 0 findings; the MyFlow full gate repeats it on the commit. CI is green on `45a417a` (run 37157492007, above). What is left of E.4 is the public/deploy checks; they are the owner's gate and do not hold the quality thread (plan D11).
- **Executor:** since the owner's D12 (2026-10-04) the session's model, Claude Opus 5.5, with no model of another vendor in any role (plan §2, record D12).
  The `CLAUDE.md` line «Executor: GLM 5.3», its [runbook](docs/operations/direct-glm-5.3.md) and the Codex fallback predate D12 and are not in force; the file is the owner's, and the line waits for her word.

## Accepted open risks

- **npm advisory GHSA-ch52-4w7c-c8xp** (`http-cache-semantics`, high), no fixed release. One dated exception by advisory id per [ADR 0009](docs/adr/0009-npm-advisory-without-fix.md), added 2026-10-03, expires 2026-11-03. **From 2026-11-04 the Pages build and the unit suite are red** until the entry is renewed or removed — intended. **Next review 2026-10-24**, with the ChromaDB ignores.
- **ChromaDB CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version.
  Ignored by id per ADR 0008. Reviewed 2026-09-24: no fixed release.
  **Next review 2026-10-24.**
- **The fixture TMS is a stand-in.** Every number measured through it is
  fixture-sourced and has to say so.
- **The integration job connects to Postgres as a superuser**, so RLS is
  inert unless the assertion uses a NOBYPASSRLS runtime role.

## Slice rule

Count only **(a)** `/api/ask` or UI change proven by E2E, **(b)** more real
labelled cases, or **(c)** published numbers with provenance. T-02/T-08/T-05: (c);
T-03: (a). B.1: (b) since the 2026-09-25 approval, real labelled 0 → 100 (T-54).

## Phases 0/A done · GR required · B blocked on data (Q2b)

| # | Item | Status |
|---|---|---|
| 0.1–0.3 | Freeze, publish, truth about gates | done |
| A.1–A.5 | Shadow + durable turn + evidence tables + Evidence tab | done, three slices under (a) |
| A.6 | Admission gate; 100 agent-authored cases, `agent_labelled`, 0 approved, recall 0.0000 | **done** (c) |
| A.7 | Opt-in clarification projection through `/api/ask` | **done** (a), default off |
| A.8 | Evidence distinguishes disabled, declined and failed producers | **done** (a) |
| B.1 | Labels on all 100 cases | **done** (b), `real_labelled`: approved 2026-09-25 (T-54) |
| B.2 | Fixture TMS covering the cases | **blocked** — three reasons, not one |
| B.3 | First real numbers on the labelled cases | **blocked** — same |
| B.4 | Judge calibration 10 → ≥40 double-annotated routes | not started |
| B.5 | Corpus v1.0 at `real_labelled` | labels approved; **blocked** on shipment-bound data (Q2b) |
| GR-0.2 | Separate pinned bucket: 15 cases over 13 documents; 10 `multi_hop`, 5 `aggregation`; original phase-C dataset unchanged | **done as preparation**, not a measured slice |
| GR-0.3 | [Baseline](docs/evidence/gr0-bucket-baseline.md), `91ce1745…`: top-5 0.5067 / 0.9050; 99 single-hop 0.5063 / 0.9091, one multi-hop | **done** (c) |
| GR-0.4 | SGR adds question class, bounded entities, multi-hop flag and reason; default/legacy retrieval unchanged | **preparation**, graph explicit |
| GR-1a | Offline coherence: 0.5216 vs plain top-4 0.5214 at unchanged 87/7/6; 0.63 loses 16 FULL ([capsule](docs/evidence/gr1a-section-coherence.md)) | **done** (c) |
| GR-1b | [Mac](docs/evidence/gr1b-structure-graph.md): 0.5475 / 0.9200, 88/8/4. [Seed reservation](docs/evidence/gr1b-seed-expansion.md): no gain; diagnosis closed | **measured**, NO-SHIP |
| GR-4 | [Ask → SQLite → Evidence](docs/evidence/gr4-structural-product-wiring.md): 100 Mac tests, browser/export, strict mypy | **done** (a), synthetic; off/auto fallback |
| GR-2 entity | [Mac](docs/evidence/gr2-entity-graph-lane.md), `9ca8630`: 0.5487 / 0.9250, lane 6/100; bucket unchanged (lane 11/15). G1 matches GR-1b; 5589 cached / 0 rejected via pinned Qwen2.5 (`845dbda0…`) | **measured** (c), NO-SHIP at 0.63; off |
| GR-3 A/B | [Comparison](docs/evidence/gr3-graph-lane-ab.md), `32de532`: precision 0.5067 → 0.5487; bucket recall 0.5 → 0.4, FULL 4 → 1; p95 +8765.2 ms; generation `not_evidence`, 297/300 valid | **measured** (c), NO-SHIP-to-default; off |
| P1 | [Adaptive-k](docs/evidence/p1-adaptive-k.md), `2edf19a`: H-relative exploratory held-out precision 0.5372 vs control 0.5067, 86/6/8; label-using oracle 0.6505; offline only | **measured** (c), NO_SHIP |
| P1b | [Expanded cut](docs/evidence/p1b-expanded-cut.md), `c5f1d31`: H-relative exploratory `rel_0.2+exp` 0.5975 vs expanded control 0.5768, 96/2/2 vs 97/2/1, one fact loss; offline only | **measured** (c), NO_SHIP |
| Q | Quality thread ([plan](docs/specs/plan_03_10_26.md), revised 2026-10-03: H11/G36 frozen with H6–H10, slice status in its §1): 2.1/2.2 route observability **implemented** 2026-10-01 (T-59, rule (a): `tests/test_ask_contract_route.py`); 2.3 embedder manifest **implemented** 2026-10-02 (T-61, rule (a) on a fixture embedder: `tests/test_ask_embedder_manifest.py`); unverified revisions are NOT_EVIDENCE; 2.4 harness/API parity prepared (T-62, `tests/test_harness_api_parity.py`): H 100 + Hm 15, hybrid/graph, shared exact-cosine store and fake models; production session, graded-context hash and query transform; phase-C/GR/P1/P1b paths require `--legacy-harness`; the real Chroma/exact comparison on 30 H cases is [published](docs/evidence/production-parity-30-cases.md) (T-67, rule (c)): both arms of all 30 replay through the session, 8 cases differ in vector candidates and pool, one of them also in the reranked list and the sent context, 29 of 30 sent contexts identical; no latency, answers or quality verdict; 1.2/2.7 judge contract v2 and relevance consumer prepared (T-60, `evaluation/judge_contract.py`, `scripts/relevance_judge_v2.py`, `tests/test_relevance_judge_v2.py`): blind addressed 1–10-document requests, exact cache keys, strict grade records and explicit resume with raw replies; generation invalid/absent replies are excluded per metric, >10% invalid is NOT_EVIDENCE, truncation is recorded and excluded from deciding κ; archived formats preserved, no new quality measurement; 1.4 [P2 development baseline](docs/evidence/semantic-ruler-p2-baseline.md) published (T-58, rule (c)), H/Hm precision 0.6080/0.8400, `provisional_ruler`, unexpanded contexts, provisional clusters; 2.5 [preliminary archive loss map](docs/evidence/evidence-loss-map-prelim.md) published (T-63, rule (c)): 100 H / 200 term occurrences, hybrid first losses 4 cases by pool + 9 between pool and sent context (stage unknown), no missing index-proxy terms; G2/G3 limits explicit, ledger started, full gold/API baseline pending; 1.3a [pilot drafts](docs/evidence/devset-pilot-drafts.md) prepared (T-64): 30 agent_labelled, quotas 10/10/4/6, derived RU→EN 10, 0 approved; specificity-filtered frame 982 sections; 84 draft topic families (57 singletons), 19 pilot case–family components; H/Hm use 42 families, pilot adds 7; holdout reserve 35 families / 36 documents, skewed toward HR/legal templates with no claims/customs/dangerous goods; 105 cross_ref links to development families, 25 reserve families linked, leaving 10 unlinked HR families / 10 documents; F-T-64-2/3/4 repaired with numeric self-coverage, atomic claim + source_quote and 30 minimal reference answers; 1.1 ruler check **done** 2026-10-04 (T-57, rule (c)): [κ of the consensus to the two model references](docs/evidence/p2-model-reference-kappa.md) 0.9333 / 0.9604, both CI95 entirely above 0.7 → `model-cross-checked` (by models, not people) for the sample's question classes and unexpanded top-5 contexts, 1.1b not needed; 1.3b **done** 2026-10-04 (T-78, preparation; D11: no person approves a case; D12: one model): rule [«Label verification»](docs/specs/semantic-precision-metrics.md), rubric `label-verification/v2` — one verifier, Claude Opus 5.5 in stateless requests, for drafts by an OpenAI model, five checks, a repair changes the label and never the question (v1, with GLM 5.3 and Opus 5.5, was registered in T-76 and [audited by GPT-6-Astra](docs/audits/audit_astra_04_10_26_label_verification.md), 22 findings applied; no v1 verdict is counted); G38 а and б closed (wide scan of the whole index instead of the control's pool, `gold_error` in the 4.1 contract, a fifth check of currency, authority, severity and critical facts); family map and holdout reserve registered with leakage and skew stated; tool `scripts/devset_label_verify.py` over `evaluation/label_verification.py` ([requirement](docs/specs/label-verification.md), T-77), scan by `scripts/devset_wide_scan.py`; [result](docs/evidence/devset-pilot-label-verification.md), replayed by `tests/test_devset_label_checks_artifact.py`: 30 verified, 0 dropped — 25 at the first check, 5 after a repair of severity and critical facts by the same model (a consistency check, counted apart); first-check rejections single-doc 4 of 10 and multi-doc 1 of 10, all on severity or critical facts, whose definitions postdate the drafts; `single_model_verified`, origin stays `agent_labelled`, rule (b) not met; 2.5: one judge of new texts, Opus 5.5 (`single_judge`, stability retest), and the rules and builder of the baseline report registered and written before the first grade (`scripts/baseline_report.py`, `tests/test_baseline_report.py`); the T-65 collection is complete (2026-10-05: 115 cases, none excluded) and its judging is part done (48 of 115 requests answered); 1.3c **registered** 2026-10-05 (`323ce00`, preparation; the variance pilot has not run): split `evaluation/devset_split.json`, development 60 cases in 37 clusters, holdout 64 in 18, registered MDE 0.17–0.30 against the rule's +0.05 (`tests/test_devset_split.py`, `tests/test_variance_pilot.py`); external bases (owner, 2026-10-05): in the plan as slices 1.5 / 1.5c / 1.5d (connection, next on the Mac), 1.6 and 1.7 — none connected, no number | adopted and ratified by delegation 2026-09-30; plan revised 2026-10-03 |

## Open questions for Julia

Q1, Q2a and Q4 answered, D2/D3 closed; the rest block their phase:

- **Q2 (B):** label approval answered 2026-09-25 («Одобряю», all five batches). Open (Q2b):
  40 double-annotated calibration routes and 100 real shipment-bound support requests;
  B.2/B.3/B.5 stay blocked without them, and resolution numbers stay synthetic.
- **Q3 (phase C):** heavy runs on Colab or the iMac. **Q4 (phase E)** confirmed
  2026-09-30: publish current `brownjuly2003-code/RAG_new` as **RAG assistant**, Pages `/RAG_new/`.
- **D2/D3 (quality thread): closed 2026-10-03 by Julia's decision D11 — «люди участвовать в процессе не будут».** No one grades the 10 blind cases in `reports/p2/human-sample.html`, and no one approves the 30 drafts in `evaluation/devset_pilot.jsonl` or the 84-family `evaluation/document_families.json`: a model checks them — since her D12 of 2026-10-04 one model, the session's Opus 5.5, and the drafts are checked (T-78) — and the plan claims neither `human-validated` nor `real_labelled` for that work ([D11 and its replacement table](docs/specs/plan_03_10_26.md#2-точки-решения--приняты-2026-09-30-по-делегированию)). The reserve question (35 families / 36 documents skewed toward HR/legal templates, 105 cross_ref links to development families, 10 unlinked HR families) no longer waits either: registered 2026-10-04 in the development ruler (T-76) — topic independence with that leakage and skew published and the 4.1 conclusion narrowed, because new source documents can come only from the owner. Still Julia's, and not awaited by the plan: deployment target and SLO (D5), repository publicity, the stop-list, the exclusion list for external models, new source documents, and whether a locked part of an external base decides the gain line of acceptance 4.1 (written into the plan on 2026-10-05 as the agent's reading of her words — plan D7). **Also answered 2026-10-03** ([plan §2 addendum](docs/specs/plan_03_10_26.md#2-точки-решения--приняты-2026-09-30-по-делегированию)): order — phase E first (a green CI on HEAD), then the 2.5 chain; the lexical-lane research stays in `D:/Rag_research`, with no note in the repository, so the input's item П4 (priors for H6–H8) is not in the plan; the "Actions unavailable until October" rule is removed from `CLAUDE.md`.

## Links

- Frozen streams — [`ROADMAP.md`](ROADMAP.md)
- Evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Queue — [`BACKLOG.md`](BACKLOG.md)
- Conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · [`AGENT_STATE.md`](AGENT_STATE.md)
