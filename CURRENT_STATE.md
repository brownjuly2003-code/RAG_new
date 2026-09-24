# Current state — RAG_new

2026-09-24 · Plan: [`plan_06_09_26.md`](plan_06_09_26.md)
(mode B, adopted 2026-09-10) · Audit:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· Phase C source: `c06bdf5` · owner delegated commits and pushes (§1).

## Start here

### P1 adaptive-k — code ready, not measured

`a67f517` adds a label-free cut of the reranked top-5 on fresh `bge-reranker-v2-m3` scores
(archived order reproduced 100/100 on H, 15/15 on Hm). The rules were pre-registered in the
[plan](docs/specs/p1-adaptive-k-plan.md) before any score was seen; no grid cell has been
evaluated. A pass is unlikely: the label-using prefix oracle, 0.6505 (exploratory), bounds
any cut that keeps every fact. The verdict is H-relative: the phase-C harness has no
parent-window expansion, and production expanded top-5 measured 0.5768 / 0.980 on the Q1
pool. Next: end-to-end tests, the Mac report at a committed sha, capsule; then P1b over
production expansion and P2, a blinded relevance judge (choosing the judge is Julia's
data-governance call).

### GR-3 measured — NO-SHIP-to-default

Measured 2026-09-18/19 on `deproject-mac` ([capsule](docs/evidence/gr3-graph-lane-ab.md)): phase-C `G2` 0.5487
vs hybrid 0.5067, FULL 89 vs 87; multi-document bucket recall 0.5000 → 0.4000 and FULL 4 → 1
(both graph arms); retrieve p95 +8765.2 ms vs 200 ms — fail. Generation:
`not_evidence` (297/300 valid; excluded case in capsule).
`RAG_GRAPH_RETRIEVAL` stays `off`. **C.4 closed:** [NO-SHIP of Qwen3](docs/evidence/c4-generator-model-decision.md): faithfulness 0.8986 < 0.90; host RAM unknown.
Default: Qwen2.5, below gate. **C.3 done:** [HTTP](docs/evidence/c3-contract-shaped-response.md) and [copilot](docs/evidence/c3-copilot-contract-draft.md), off; 555 Mac tests. **D.3 measured:** [rerank](docs/evidence/d3-pgvector-rerank.md): final precision 0.4610/0.4729. **D.2 outlier closed as a bounded replay:** retained original index non-monotonic (ef_search 100 0.20; ef 40 and 200 both 20/20), fresh rebuild 20/20 across the measured grid, no pgvector/HNSW root cause claimed ([capsule](docs/evidence/d2-pgvector-ann.md)); D open for graph/evidence parity and cold-start/host RAM.

### Phase C.1a Qwen 2.5 7B baseline — measured on Mac

Mac: 3 × 100 valid generations, LLM-judge and NLI, zero failures.
[Raw report](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json): `measured`; SHA-256 guarded by `tests/test_phase_c_baseline_artifact.py`.

| Metric | Mean | Run-level 95% CI |
|---|---:|---:|
| LLM faithfulness | 0.8295 | [0.8295, 0.8295] |
| NLI faithfulness | 0.8919 | [0.8916, 0.8923] |
| Context precision | 0.5067 | [0.5067, 0.5067] |
| Context recall | 0.9050 | [0.9050, 0.9050] |
| Answer relevancy | 0.8960 | [0.8960, 0.8960] |
| Mean latency per case | 197.50 s | [192.10 s, 202.90 s] |

Pinned provenance: code `c06bdf5`, model
`qwen2.5:7b` at `845dbda0…`, dataset `3737d694…`, cached contexts `91ce1745…`,
NLI `8adb042d…`, seeds 42–44, temperature 0; NLI peak RSS 2.12 GB, loaded model
5.06 GB, neither total-host. Gates missed: faithfulness 0.90, precision 0.63.

**C.1b Qwen3 8B** (2026-09-11): 3 × 100 Mac cases, zero failures;
faithfulness 0.8986, NLI 0.9908, relevancy 0.8095, precision 0.506657,
latency 176.81 s. [Raw report](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json),
[provenance/limits](docs/evidence/c1b-qwen3-generator-benchmark.md): C.4 input; host peak RAM unknown.

### 1. Russian gate wired; resolution unmeasurable

T-01…T-09 closed: [commits/tests](docs/evidence/a6-journey-admission-and-clarification.md).
Authorized push:
`git -c credential.helper='!gh auth git-credential' push origin master`.

Resolution remains unmeasurable ([evidence](docs/evidence/a6-journey-admission-and-clarification.md)):
no case names a shipment; the original gate was English-only; the bilingual
gate has recall **0.0000**, with one `exception_escalation` false positive.
None of 100 `agent_labelled`, unapproved cases belongs to the journey.
B.2/B.3/B.5 need data; label approval alone cannot fix this.
Review: `python scripts/aircargo_labels.py report --batch 1`;
approve: `python scripts/aircargo_labels.py approve --batch 1 --approver julia`.

**Windows:** focused checks only; strict mypy needs numpy 2.4.4. PostgreSQL and
browser checks run on Mac.

## Current facts

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private, tag
  `freeze-2026-08-23` = `26866e9`. Pushes go over HTTPS (command in §1).
- **Phase A closed:** read-only shipment-status `/api/ask`; clarification projects
  only under both default-off allowlists. Disabled/declined/failed stay explicit.
- **Zero real labelled cases.** 100/100 labelled, 0 approved, 0 binding a
  shipment; all expect `verified`. 201 real documents; agent-written questions
  (`325d63c`, `6b7417d`,
  `32e841f`). Question classes live in a sidecar (`6cde0b1`) — 99 `single_hop`,
  1 `multi_hop`, 0 `aggregation`, 0 `global` (plan §5, GR-0.2).
- **Last successful CI: `386ee10`** (2026-09-10): run 34471656422 passed
  11 of 11 jobs. Run 34359692687 on `69a5140` verified the CVE-2026-9856 floor
  `transformers>=5.10.0` under `--require-hashes`, pip-audit clean.
- **GitHub Actions unavailable until early October 2026** (owner, 2026-09-21).
  Use Mac gates; no workflow retries or billing probes.
- **Executor:** [direct GLM 5.3 xhigh](docs/operations/direct-glm-5.3.md). Weekly quota
  (`1310`) until 2026-09-28 05:56 UTC+8; meanwhile Codex GPT-6-Sol (`cw` profile), owner's go-ahead.

## Accepted open risks

- **ChromaDB CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version.
  Ignored by id per ADR 0008. **Review 2026-09-24.**
- **The fixture TMS is a stand-in.** Every number measured through it is
  fixture-sourced and has to say so.
- **The integration job connects to Postgres as a superuser**, so RLS is
  inert unless the assertion uses a NOBYPASSRLS runtime role.

## Slice rule

Count only **(a)** `/api/ask` or UI change proven by E2E, **(b)** more real
labelled cases, or **(c)** published numbers with provenance. T-02/T-08/T-05: (c);
T-03: (a). B.1 remains preparation until approval.

## Phases 0/A done · GR required · B blocked (Q2)

| # | Item | Status |
|---|---|---|
| 0.1–0.3 | Freeze, publish, truth about gates | done |
| A.1–A.5 | Shadow + durable turn + evidence tables + Evidence tab | done, three slices under (a) |
| A.6 | Admission gate; 100 agent-authored cases, `agent_labelled`, 0 approved, recall 0.0000 | **done** (c) |
| A.7 | Opt-in clarification projection through `/api/ask` | **done** (a), default off |
| A.8 | Evidence distinguishes disabled, declined and failed producers | **done** (a) |
| B.1 | Labels on all 100 cases | **done**, `agent_labelled`, 0 approved |
| B.2 | Fixture TMS covering the cases | **blocked** — three reasons, not one |
| B.3 | First real numbers on the labelled cases | **blocked** — same |
| B.4 | Judge calibration 10 → ≥40 double-annotated routes | not started |
| B.5 | Corpus v1.0 at `real_labelled` | needs Q2 route 1 |
| GR-0.2 | Separate pinned bucket: 15 cases over 13 documents; 10 `multi_hop`, 5 `aggregation`; original phase-C dataset unchanged | **done as preparation**, not a measured slice |
| GR-0.3 | [Baseline](docs/evidence/gr0-bucket-baseline.md), `91ce1745…`: top-5 0.5067 / 0.9050; 99 single-hop 0.5063 / 0.9091, one multi-hop | **done** (c) |
| GR-0.4 | SGR adds question class, bounded entities, multi-hop flag and reason; default/legacy retrieval unchanged | **preparation**, graph explicit |
| GR-1a | Offline coherence: 0.5216 vs plain top-4 0.5214 at unchanged 87/7/6; 0.63 loses 16 FULL ([capsule](docs/evidence/gr1a-section-coherence.md)) | **done** (c) |
| GR-1b | [Mac](docs/evidence/gr1b-structure-graph.md): 0.5475 / 0.9200, 88/8/4. [Seed reservation](docs/evidence/gr1b-seed-expansion.md): no gain; diagnosis closed | **measured**, NO-SHIP |
| GR-4 | [Ask → SQLite → Evidence](docs/evidence/gr4-structural-product-wiring.md): 100 Mac tests, browser/export, strict mypy | **done** (a), synthetic; off/auto fallback |
| GR-2 entity | [Mac](docs/evidence/gr2-entity-graph-lane.md), `9ca8630`: 0.5487 / 0.9250, lane 6/100; bucket unchanged (lane 11/15). G1 matches GR-1b; 5589 cached / 0 rejected via pinned Qwen2.5 (`845dbda0…`) | **measured** (c), NO-SHIP at 0.63; off |
| GR-3 A/B | [Comparison](docs/evidence/gr3-graph-lane-ab.md), `32de532`: precision 0.5067 → 0.5487; bucket recall 0.5 → 0.4, FULL 4 → 1; p95 +8765.2 ms; generation `not_evidence`, 297/300 valid | **measured** (c), NO-SHIP-to-default; off |
| P1 | [Adaptive-k](docs/specs/p1-adaptive-k-plan.md), `a67f517`: pre-registered cut of the reranked top-5 on fresh scores, parity 100/100 and 15/15; no cell evaluated | **preparation**, not measured |

## Open questions for Julia

Q1 answered: private repo. Others block their phase:

- **Q2 (B):** approve labels in batches of 20 (§1); obtain 100 real shipment-bound
  support requests. B.2/B.3/B.5 stay blocked without them. Otherwise, all
  published resolution numbers must identify synthetic instances.
- **Q3 (phase C):** heavy runs on Colab or the iMac. **Q4 (phase E):** publish
  as `RAG_new` or rename.

## Links

- Frozen streams — [`ROADMAP.md`](ROADMAP.md)
- Evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Queue — [`BACKLOG.md`](BACKLOG.md)
- Conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · [`AGENT_STATE.md`](AGENT_STATE.md)
