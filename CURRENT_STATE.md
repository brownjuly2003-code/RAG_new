# Current state — RAG_new

2026-10-23 · The plan: [`PLAN.md`](PLAN.md), accepted by Julia on 2026-10-17 («принять») ·
now: stage 2 parts 1, 2 and 4 collected and published; grading waits for the judge · previous version:
[`archive/docs/state/current-state-through-2026-10-17.md`](archive/docs/state/current-state-through-2026-10-17.md).

Read this file for *what is true now*; [`PLAN.md`](PLAN.md) for *what happens next and why*;
[`ROADMAP.md`](ROADMAP.md) for *what each stage has delivered*; [`docs/README.md`](docs/README.md)
for *where every other document is*.

## What the product is

A support assistant that answers a customer's question from a company's documents and shows
its sources (RAG). Two answer paths:

- **the web chat** — `/api/ask/stream`: retrieval → answer → self-evaluation → suggested
  questions. This is what a customer uses, and what every measurement of the plan uses;
- **the widget** — `/api/ask`: an agent graph with query rewriting, document grading, claim
  checking, up to two retries and a ticket to a person.

Retrieval: BM25 + BGE-M3, 20 candidates each, RRF, CPU bge-reranker-v2-m3 keeps five.
Chunks: markdown sections, 800 characters/200 overlap; DOCX/HTML/PDF converted by loaders;
`[document › section]` headers, expansion up to two neighbours each side. English V3
instructions (`4ca5ddd`) request the question's language; actual language is measured.

**Production is `deproject-mac`** (Julia, 2026-10-14: «прод на маке»): i5-7500, 4 cores, 8 GB,
Ollama 0.33.2 on the CPU. **The model is Qwen3-4B-Instruct-2507** (Julia, 2026-10-16; the code
default since `7a99c45`). No service runs between measurements yet: a stand of a commit is
brought up for each run ([`PLAN.md`](PLAN.md) stage 6 makes it a service).

**Corpora.** aircargo: 201 documents/5,589 chunks, 100 agent-written questions with labels
approved 2026-09-25. ConditionalQA: 13,778 chunks; WixQA: 37,571; MultiHop-RAG: 11,231.
Open/locked selections: `evaluation/external_parts.json`; only open selections measured.
All use the second generation at `/Users/julia/RAG_new_external_s1/`, built at `e5e135a`;
the original indexes remain beside it.

## Numbers

Numbers from another path or model do not describe the chat. Earlier comparisons and their
limits: [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), [`PLAN.md`](PLAN.md) §3.

| What | Number | Record and limits |
|---|---|---|
| Earlier chat speed, 4B | median 320 s; first token 223 s; rerank 102 s | [30-question idle-Mac record](reports/chat-live-4b/19beeb1/) |
| Earlier memory | swap up to 12,274 MB; runner +312 MB/request | same record; stage 4 investigates |
| Retrieval alone | median 27.6 s, rerank 27.3 s | [record](reports/chat-live/33d4b42/); stage 4 investigates contention |
| Engineering | 5,885 passed, 124 skipped on `96ee4e6`; static/security checks passed | Historical full gate; current slice's focused checks below |

The stage-2 [retrieval baseline](docs/evidence/stage2-retrieval-baseline.md) is recorded at
`7208ed2`: 415 questions, no path break, aircargo prompt parity 100/100. The
[300 external answers](docs/evidence/stage2-external-answers.md): no path break, all in the
question's language, prompt parity 100/100 per base, 84 routed to a person, median 266.9 s.
External answer quality remains open: the judge is unavailable.

## Stage 1 — closed 2026-10-18

The 25 findings, their outcomes and the live checks: [`docs/specs/stage1-fixes.md`](docs/specs/stage1-fixes.md);
records `reports/stage1/`, pinned by `tests/test_stage1_live_artifact.py`; one evidence row.

- Loaders, headers, tables, overlap, language instructions and BM25 restoration fixed
  (`8f94d84`…`4ca5ddd`). Second-generation indexes and V3 passed one live question per tenant.
- Stage-2 runner, judge adapter, signal tool and external selections registered at `e5e135a`.
- **Left from the [audit of 2026-10-18](docs/operations/audit_fable_18_10_26.md):** S8, the
  answer's script, a signal candidate for stage 3; the audit's keys bound by a test (later).

## Next

[`PLAN.md`](PLAN.md) stage 2 by [`docs/specs/stage2-four-corpora.md`](docs/specs/stage2-four-corpora.md)
(`5e308fe`): 100 aircargo answers, retrieval on 415 questions, 300 external answers.
Part 3 uses GR-3's archives; live graph measurement is stage 7. Judge amendment: the spec.
**Done:** part 1 — 100 answers in ten batches (`p1-aircargo-b01`…`b10`), all complete, no path break; judge record and frozen-plan hash in `reports/stage2/5e308fe/` (115 requests, 15 retests).
**Done:** part 2 — all 415 questions completed 2026-10-20; immutable export `reports/stage2/retrieval-20261021/`, provenance/derivation tests passed on the Mac (41 focused checks including docs).
**Done:** part 4 — 300 external answers, 30 counted batches, completed 2026-10-23 04:32 UTC after the pause and resume of 2026-10-22; immutable export `reports/stage2/external-answers-20261023/`, raw answers private in `D:/RAG_new_stage2_private/p4/resume-20261022/` (1,356 hashes verified).
**Open:** part 2's aircargo context judge (plan frozen in `77795a3`) and part 4's answer judge — Claude, the registered judge, is unavailable; then part 5, the combined record. The Mac is free; no measurement runs.

## Julia's decisions in force

[`PLAN.md`](PLAN.md) §8.1: no human grading; the session does the work, no other model except
the authorized Codex second-opinion role; Qwen3-4B; production on Mac; external answers in
stage 2; indexes as new generations. A broken premise is resolved and reported (2026-10-19).
Pushes require her authorization. Claude, the registered judge, is unavailable (Julia,
2026-10-21, reaffirmed 2026-10-22); grading waits. Mac generation may continue; no replacement judge.

## Open for Julia

[`PLAN.md`](PLAN.md) §8.3, by stage: the widget's suspected defects R1/R2 and outcome B of the
[handover plan](docs/specs/handover-signal.md) (stage 3); removing
self-evaluation with its «Качество: N» badge, an `ollama serve` restart, the SLO (stage 4);
the service on her Mac and whether it counts as a deployment (stage 6); the locked parts
(stage 7); publication (stage 8). Any time: GitHub billing; Q2b (`PLAN.md` writes Q2б) — 100 real shipment-bound
requests (without them phase B stays blocked); Mac hours a day for runs; frozen items whose
condition is formally met ([`PLAN.md`](PLAN.md) §9).

## Accepted open risks

- **npm advisory GHSA-ch52-4w7c-c8xp** (`http-cache-semantics`, high), no fixed release. One
  dated exception by advisory id per [ADR 0009](docs/adr/0009-npm-advisory-without-fix.md),
  added 2026-10-03, expires 2026-11-03. **From 2026-11-04 the Pages build and the unit suite are
  red** until the entry is renewed or removed — intended. **Next review 2026-10-24**, with the
  ChromaDB ignores.
- **ChromaDB CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version. Ignored by id per ADR
  0008. Reviewed 2026-09-24: no fixed release. **Next review 2026-10-24.**
- **The fixture TMS is a stand-in.** Every shipment-resolution number measured through it is
  fixture-sourced and has to say so.
- **The integration job connects to Postgres as a superuser**, so RLS is inert unless the
  assertion uses a NOBYPASSRLS runtime role.
- **One Mac, 8 GB.** One measurement at a time; time numbers count only from an idle Mac.

## CI and pushes

- Last green CI: `45a417a`, 2026-10-03, 11/11 jobs. Since `e81f0c5` (2026-10-16), billing
  prevents jobs starting. Before a push: full Mac unit suite, mypy, bandit and dependency audits.
- Run 34359692687 on `69a5140` verified the CVE-2026-9856 floor `transformers>=5.10.0` under
  `--require-hashes`, pip-audit clean; both locks still pin it.
- Tracked `origin/master`: `172620f`, last pushed 2026-10-18. Later stage-2 commits, including
  `7208ed2` and `4fe4aaf`, are local. No push authorized this session.
- Private remote: `brownjuly2003-code/RAG_new`; HTTPS command in [`CLAUDE.md`](CLAUDE.md).

## Links

- Plan — [`PLAN.md`](PLAN.md) · progress — [`ROADMAP.md`](ROADMAP.md) · evidence —
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) · documents map — [`docs/README.md`](docs/README.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md), [`AGENT_STATE.md`](AGENT_STATE.md) · queue for
  automation — [`BACKLOG.md`](BACKLOG.md) · module layout — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- Last session — [stage 2 answers collected and published](docs/operations/session-handoff-2026-10-23-stage2-collected.md)
