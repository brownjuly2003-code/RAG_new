# Current state — RAG_new

**The only entry point for a new session.** Read this, then [`ROADMAP.md`](ROADMAP.md);
follow other links only when needed.

Last updated: 2026-09-12 · Plan: [`plan_06_09_26.md`](plan_06_09_26.md)
(mode B, adopted by the owner 2026-09-10) · Audit of record:
[`docs/audits/audit_final_23_08_2026.md`](docs/audits/audit_final_23_08_2026.md)
· Phase C benchmark source: `c06bdf5` · push is the owner's call (§1)

## Start here

### Phase C.1a Qwen 2.5 7B baseline — measured on Mac

`c1a-qwen25-7b-c06bdf5` completed on `deproject-mac`: exactly 3 × 100 cases,
300 valid generations, LLM-judge and NLI results, and zero failures. The
checked-in [raw report](evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json)
is `measured`; sidecar SHA-256 is guarded by `tests/test_phase_c_baseline_artifact.py`.

| Metric | Mean | Run-level 95% CI |
|---|---:|---:|
| LLM faithfulness | 0.8295 | [0.8295, 0.8295] |
| NLI faithfulness | 0.8919 | [0.8916, 0.8923] |
| Context precision | 0.5067 | [0.5067, 0.5067] |
| Context recall | 0.9050 | [0.9050, 0.9050] |
| Answer relevancy | 0.8960 | [0.8960, 0.8960] |
| Mean latency per case | 197.50 s | [192.10 s, 202.90 s] |

The guarded report pins full provenance and config: code `c06bdf5`, model
`qwen2.5:7b` at `845dbda0…`, dataset `3737d694…`, cached contexts `91ce1745…`,
NLI `8adb042d…`, seeds 42–44, temperature 0. NLI peak RSS was 2.12 GB and the
loaded Ollama model 5.06 GB; neither is total-host peak RAM. Both the 0.90
faithfulness and 0.63 precision gates are missed. **Stream GR is required:**
only retrieval can move precision over fixed contexts. GR-0.3 measured 0.5067
at top-5; GR-1a measured 0.5216 versus plain top-4's 0.5214.

**C.1b `qwen3:8b` is published** (2026-09-11): 3 × 100 Mac cases,
zero failures, LLM faithfulness 0.8986, NLI 0.9908, relevancy 0.8095,
precision 0.506657 and mean latency 176.81 s. The guarded [raw report](evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json)
and [capsule](docs/evidence/c1b-qwen3-generator-benchmark.md) hold provenance and
limitations. This is C.4 input, not a model change; host peak RAM is unknown.

### 1. The gate can reach Russian traffic. The corpus still cannot measure it.

T-01…T-09 are closed; commits and tests are in the
[A.6–A.8 capsule](docs/evidence/a6-journey-admission-and-clarification.md).
Push remains the owner's call:
`git -c credential.helper='!gh auth git-credential' push origin master`.

The corpus cannot measure resolution for three independent reasons
([capsule](docs/evidence/a6-journey-admission-and-clarification.md)): no case
names a shipment; the original English-only gate could not measure the Russian
corpus; and the bilingual gate still has admission recall **0.0000** over 100
agent-written, `agent_labelled`, unapproved cases. Its sole admission is an
`exception_escalation` false positive; no case belongs to this journey.

B.2/B.3/B.5 stay blocked on data. Label review does not fix that:
`python scripts/aircargo_labels.py report --batch 1`, then
`python scripts/aircargo_labels.py approve --batch 1 --approver julia`.
The local corrective queue after T-09 is empty.

**This laptop:** deselect the headless-Chrome a11y test (CI runs it); strict
mypy needs locked numpy 2.4.4; Postgres integration tests do not run here.

## What is true right now

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private, tag
  `freeze-2026-08-23` = `26866e9`. Pushes go over HTTPS (command in §1).
- **Phase A closed:** `/api/ask` runs the shipment-status journey read-only.
  Only its clarification terminal may project when both default-off allowlists
  name it; disabled/declined/failed states remain explicit.
- **Zero real labelled cases.** 100/100 labelled, 0 approved, 0 binding a
  shipment, `expected_terminal` `verified` for all 100. The 201 source
  documents are real; questions were agent-written (`325d63c`, `6b7417d`,
  `32e841f`). Question classes live in a sidecar (`6cde0b1`) — 99 `single_hop`,
  1 `multi_hop`, 0 `aggregation`, 0 `global` (plan §5, GR-0.2).
- **On pushed `6cc810d`, both push-triggered workflows passed** (`CI`
  34461559172, 11/11; docs build 34461559218). Deploy skipped because the repo
  is private. Schedule/dispatch-only workflows were not run.

## Accepted open risks

- **Three chromadb CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version.
  Ignored by id per ADR 0008. **Review 2026-09-24.**
- **The fixture TMS is a stand-in.** Every number measured through it is
  fixture-sourced and has to say so.
- **The integration job connects to Postgres as a superuser**, so RLS is
  inert unless the assertion uses a NOBYPASSRLS runtime role.

## The rule that governs every slice

A slice counts only if **(a)** observable `/api/ask` or UI behaviour changed
with an E2E test proving it, **(b)** real labelled cases went up, or **(c)** a
published number changed with provenance. T-02/T-08/T-05 are (c); T-03 is (a).
B.1 is preparation until a batch is approved.

## Phases 0 and A — done · GR — required stream (plan §2) · B — waits on the owner (Q2)

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
| GR-0.3 | Retrieval baseline by class over pool `91ce1745…`: 0.5067 / 0.9050 at top-5 (= C.1a), `single_hop` 0.5063 / 0.9091 over 99 cases, `multi_hop` over 1, two classes empty — a ruler, not a comparison ([capsule](docs/evidence/gr0-bucket-baseline.md)) | **done** (c) |
| GR-0.4 | SGR schema adds `question_class`, bounded `entities`, `needs_multi_hop` and `reason_code`; default and legacy retrieval routes unchanged | **done as preparation**, graph still explicit |
| GR-1a | Offline coherence: 0.5216 vs plain top-4 0.5214 at unchanged 87/7/6; 0.63 loses 16 FULL ([capsule](docs/evidence/gr1a-section-coherence.md)) | **done** (c) |
| GR-1b | Recovered Mac pool validated: precision 0.5475, recall 0.9200, FULL/PART/MISS 88/8/4; prefilter 0/100. [Report and archived-input reproduction](docs/evidence/gr1b-structure-graph.md). **NO-SHIP** at 0.63; do not rerun embeddings. Next: planned GR-4/GR-2/GR-3. | **measured**, provenance limits in capsule |

## Open questions for Julia

Q1 is answered (separate private repo). Each blocks only its own phase:

- **Q2 (phase B), two questions.** (a) Approve proposed labels in batches of
  20 — command in §1. (b) Can 100 real support requests that name a shipment
  be obtained? Without them B.2/B.3/B.5 stay blocked. If no, record that the
  repository measures resolution on synthetic instances wherever a number is
  published.
- **Q3 (phase C):** heavy runs on Colab or the iMac. **Q4 (phase E):** publish
  as `RAG_new` or rename.

## Links

- Roadmap and what is frozen — [`ROADMAP.md`](ROADMAP.md)
- One row per slice, with evidence — [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md)
- Open work after T-04, plus the pre-audit queue — [`BACKLOG.md`](BACKLOG.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md) · removed surfaces —
  [`DEPRECATIONS.md`](DEPRECATIONS.md) · history — [`AGENT_STATE.md`](AGENT_STATE.md)
