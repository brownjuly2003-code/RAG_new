# Current state — RAG_new

**The only entry point for a new session.** Read this, then
[`ROADMAP.md`](ROADMAP.md). Everything else is reached by link, on demand.

Last updated: 2026-09-10 · Plan: [`plan_06_09_26.md`](plan_06_09_26.md)
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

Provenance: code `c06bdf5721b434eff32dcf5b9991221d5b2a15f8`; model `qwen2.5:7b`
at `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`; dataset
`3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`; cached
contexts `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
NLI `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`. Config: seeds 42–44,
temperature 0, `num_ctx=4096`, `num_predict=384`, context cap 6000. NLI peak
RSS 2,124,476,416 bytes; Ollama loaded size 5,062,566,870 bytes; neither is
total-host peak RAM. Misses faithfulness 0.90 and context precision 0.63; that
does not authorize a model change or a NO-SHIP decision. **Stream GR is required, not optional:** precision is computed over these cached contexts, so only the retriever moves it (plan §2), and the cheap structural arm is measured short of the ≥ 0.63 gate (phase C's, GR-1's target in plan §5) — GR-0.3 0.5067 at top-5, GR-1a 0.5216 against plain top-4's 0.5214 (rows GR-0.3/GR-1a below).

**C.1b `qwen3:8b` finished on the Mac 2026-09-08 03:55 MSK — measured there,
not published here.** The 2026-09-02 attempt died with `/tmp`; rebuilt under
`$HOME`, 3 × 100 (seeds 42–44, code `b8ecc8e`) ended `FULL_VALIDATION_OK` at
faithfulness 0.8986, NLI 0.9908, precision 0.5067, recall 0.9050, relevancy
0.8095, 176.8 s per case. Checking the report in with a sha guard and an index
row is what remains; paths in [`plan_06_09_26.md`](plan_06_09_26.md) §0.

### 1. The gate can reach Russian traffic. The corpus still cannot measure it.

T-01…T-09 are closed: measured bilingual admission, opt-in clarification,
operator-visible shadow outcomes and pinned report provenance. Exact commits
and tests live in the [A.6–A.8 capsule](docs/evidence/a6-journey-admission-and-clarification.md).
Push remains the owner's call:
`git -c credential.helper='!gh auth git-credential' push origin master`.

The corpus cannot measure resolution, for three independent reasons
([capsule](docs/evidence/a6-journey-admission-and-clarification.md)): (1) no
case names a shipment (B.1); (2) the corpus is Russian and the gate's
vocabulary was English — `contains_both_domain_noun_and_status_cue: 0`, so
over the 100 agent-authored-over-real-documents cases, still `agent_labelled`
and 0 approved, `recall 0.0000` said nothing about the predicate; (3) with
the language removed, over those 100 cases, still `agent_labelled` and 0
approved, admission recall is still **0.0000**. Reachability moved from
`both 0` to `both 1`; the one admission is a false positive on a case labelled
`exception_escalation`. The corpus contains no case this journey should admit.

B.2/B.3/B.5 stay blocked on data. Label review does not fix that:
`python scripts/aircargo_labels.py report --batch 1`, then
`python scripts/aircargo_labels.py approve --batch 1 --approver julia`.
The local corrective queue after T-09 is empty.

**This laptop:** `tests/test_a11y.py::test_axe_has_no_serious_or_critical_findings`
drives headless Chrome and hangs the whole run (deselect it; CI runs it);
local mypy --strict is red on numpy stubs unless the installed numpy matches
the lock (2.4.4, not 2.5.1); Postgres integration tests still do not run here.

### 2. Housekeeping with a date on it

**Review 2026-09-24:** the three chromadb CVE ignores. If a fixed release
exists by then, upgrade and delete them from all four places the guard
requires them to match.

## What is true right now

- **Remote exists** (2026-08-24): `brownjuly2003-code/RAG_new`, private, tag
  `freeze-2026-08-23` = `26866e9`. Pushes go over HTTPS (command in §1).
- **Phase A closed:** `/api/ask` runs the shipment-status journey as a
  read-only shadow. T-03 may project only its clarification terminal when both
  allowlists name it; T-04 makes disabled/declined/failed observation explicit.
  All resolution/session flags default off; shadow-only remains byte-identical.
- **Zero real labelled cases.** 100/100 labelled, 0 approved, 0 binding a
  shipment, `expected_terminal` `verified` for all 100. The 201 source
  documents are real; questions were agent-written (`325d63c`, `6b7417d`,
  `32e841f`). Question classes live in a sidecar (`6cde0b1`) — 99 `single_hop`,
  1 `multi_hop`, 0 `aggregation`, 0 `global` (plan §5, GR-0.2).
- **On `6cc810d` (T-17, pushed) both push-triggered workflows ended `success` — two of five; docs-site deployed nothing.**
  `CI` run 34461559172: 11 of 11 jobs; run 34359692687 on `69a5140` verified the CVE-2026-9856 floor `transformers>=5.10.0` under
  `--require-hashes`, pip-audit clean. Docs-site run 34461559218: `build` (with `npm audit --audit-level=high`) succeeded, `deploy` skipped by `docs-site.yml:89` (repo private) — the second docs-site green in a row.
  The first was `0aacb7b` (T-18, run 34408840657) after four failures since 2026-08-25, so T-18's npm floors are confirmed; `d026804` (T-19) touched no `docs-site.yml:6-17` path and got `CI` 34449244275 alone.

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
| GR-0.3 | Retrieval baseline by class over pool `91ce1745…`: 0.5067 / 0.9050 at top-5 (= C.1a), `single_hop` 0.5063 / 0.9091 over 99 cases, `multi_hop` over 1, two classes empty — a ruler, not a comparison ([capsule](docs/evidence/gr0-bucket-baseline.md)) | **done** (c) |
| GR-1a | Section coherence as a narrowing arm over the same pool: 0.5216 / 0.9050 with 87/7/6 held, but plain top-4 gives 0.5214 with the same coverage — the gain is a smaller `k`, not structure. 0.63 only by losing 16 FULL cases ([capsule](docs/evidence/gr1a-section-coherence.md)) | **done** (c) |

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
