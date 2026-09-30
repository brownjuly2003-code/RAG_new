# Current state — RAG_new

2026-09-30 · Plan: [`plan_06_09_26.md`](plan_06_09_26.md) (mode B, adopted 2026-09-10) · Quality thread after E: [`docs/specs/plan_final_30_09_26.md`](docs/specs/plan_final_30_09_26.md) (adopted and ratified by delegation 2026-09-30, decisions D1–D10 in its §2; final-plan audits [GLM](docs/audits/audit_glm_final_30_09_26.md) and [Astra](docs/audits/audit_astra_final_30_09_26.md) applied) ·
Audits: [Astra](docs/audits/audit_asta_30_09_26.md), [GLM](docs/audits/audit_glm_30_09_26_plan.md) and [Astra](docs/audits/audit_astra_30_09_26_plan.md) on the plan (2026-09-30) · Phase C source: `c06bdf5` · owner delegated commits and pushes (§1).

## Start here

### Quality thread — adopted and ratified by delegation 2026-09-30, nothing implemented yet

[`plan_final_30_09_26.md`](docs/specs/plan_final_30_09_26.md) is the thread after phase E. Its first executor slice, 2.1/2.2 route observability, is specified in its §5 with fields, fallback reasons, files and acceptance tests named; **no code has changed** — the executor (GLM 5.3, direct) implements it, Windows focused tests and the Mac gate prove it, and it counts under rule (a) only with the HTTP ask → trace → evidence test green. Development ruler pre-registered in [`semantic-precision-metrics.md`](docs/specs/semantic-precision-metrics.md); the official 0.63 gate is untouched. Waiting on Julia: D2 (10 blind P2 grades), D3 (dev-set batch approval). `RAG_GRAPH_RETRIEVAL` stays `off`.

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
Julia's blind grades are pending; Mistral returned `zero_limit`. No gate or default changed.

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
- **Last successful CI: `386ee10`** (2026-09-10): run 34471656422 passed
  11 of 11 jobs. Run 34359692687 on `69a5140` verified the CVE-2026-9856 floor
  `transformers>=5.10.0` under `--require-hashes`, pip-audit clean.
- **GitHub Actions unavailable until early October 2026** (owner, 2026-09-21).
  Use Mac gates; no workflow retries or billing probes.
- **Phase E:** `236f7c1` prepares **RAG assistant** for `/RAG_new/` locally:
  23 tests, `astro check`, 239-page build and five link checks passed.
  `236f7c1` is unpushed; the repository remains private. The [E.5 capsule](docs/evidence/e5-secret-scan.md)
  records the Mac full suite (3,763 unit + 93 integration passed) and the history scan on
  `c81de77`, rerun 2026-09-30 (late) on `b0386e9`: 3,722 unit + 36 e2e passed on the Mac, history
  scan 0 findings; the MyFlow full gate repeats it on the commit. CI is unavailable. E.4 needs public/deploy checks.
- **Executor:** [direct GLM 5.3 xhigh](docs/operations/direct-glm-5.3.md); fallback
  (narrowed retry for recoverable failures, Codex `cw` on quota) in `CLAUDE.md` and the runbook.

## Accepted open risks

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
| Q | Quality thread ([plan](docs/specs/plan_final_30_09_26.md)): 2.1/2.2 route observability **specified** in §5, not implemented, (a) once the HTTP test is green; 1.2 [development ruler](docs/specs/semantic-precision-metrics.md) pre-registered (preparation); 1.1/1.3 Julia's 10 blind P2 grades and dev-set pilot approval **waiting on Julia** (D2/D3) | adopted and ratified by delegation 2026-09-30 |

## Open questions for Julia

Q1, Q2a and Q4 answered; the rest block their phase:

- **Q2 (B):** label approval answered 2026-09-25 («Одобряю», all five batches). Open (Q2b):
  40 double-annotated calibration routes and 100 real shipment-bound support requests;
  B.2/B.3/B.5 stay blocked without them, and resolution numbers stay synthetic.
- **Q3 (phase C):** heavy runs on Colab or the iMac. **Q4 (phase E)** confirmed
  2026-09-30: publish current `brownjuly2003-code/RAG_new` as **RAG assistant**, Pages `/RAG_new/`.
- **D2 (quality thread):** grade the 10 blind cases in `reports/p2/human-sample.html` (50 documents, scale 0–3); until then the development ruler uses the P2 consensus ([decision](docs/specs/plan_final_30_09_26.md#2-точки-решения--приняты-2026-09-30-по-делегированию)). **D3:** approve dev-set batches when drafted.

## Links

- Frozen streams — [`ROADMAP.md`](ROADMAP.md)
- Evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Queue — [`BACKLOG.md`](BACKLOG.md)
- Conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · [`AGENT_STATE.md`](AGENT_STATE.md)
