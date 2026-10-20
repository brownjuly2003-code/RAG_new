# Current state — RAG_new

2026-10-19 · The plan: [`PLAN.md`](PLAN.md), accepted by Julia on 2026-10-17 («принять») ·
now: stage 2 registered at `5e308fe`, part 1 running (2026-10-19) · previous version of this file:
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

Retrieval: BM25 and BGE-M3 vectors, 20 candidates each, merged by RRF; the bge-reranker-v2-m3
cross-encoder on the CPU keeps 5 of them. Documents are cut by their markdown sections (DOCX, HTML and
PDF are read into markdown first; at most 800 characters, 200 overlap inside a long section),
each chunk opens with a header `[document › section]` (indexes built before stage 1 carry the
old Russian one, still read), and parent expansion adds up to two neighbouring chunks on each
side. The chat answers in the question's language (since `ffae1c2`); its instructions are
English (V3, `4ca5ddd`).

**Production is `deproject-mac`** (Julia, 2026-10-14: «прод на маке»): i5-7500, 4 cores, 8 GB,
Ollama 0.33.2 on the CPU. **The model is Qwen3-4B-Instruct-2507** (Julia, 2026-10-16; the code
default since `7a99c45`). No service runs between measurements yet: a stand of a commit is
brought up for each run ([`PLAN.md`](PLAN.md) stage 6 makes it a service).

**Corpora.** aircargo — ours: 201 Russian markdown documents, 5,589 chunks, 100 questions
written by an agent from the documents, labels approved by Julia on 2026-09-25 (the only real
labelled cases). Three external bases connected 2026-10-05/07 for universality: ConditionalQA
(13,778 chunks), WixQA (37,571), MultiHop-RAG (11,231); their questions are split into open and
locked parts (`evaluation/external_parts.json`). No quality run has used them yet. The chat
reads the second generation of all four indexes, built in stage 1 at `e5e135a` into
`/Users/julia/RAG_new_external_s1/` (10 h 01 min on the Mac); the first stays beside it.

## Numbers

Each number has a record; numbers on another path or model are history, not the product.

| What | Number | Record and limits |
|---|---|---|
| Chat answer time, 4B | median 320 s (196–476), first token 223 s; retrieval 134 s (rerank 102 s), prompt reading 67 s, self-evaluation 68 s, suggestions 13 s | [`reports/chat-live-4b/19beeb1/`](reports/chat-live-4b/19beeb1/): 30 questions, idle Mac |
| Memory | swap up to 12,274 MB over 30 questions; Ollama's runner +312 MB a request, freed only by unloading | same record; cause unknown |
| Retrieval alone, no model loaded | median 27.6 s, rerank 27.3 s of it | [`reports/chat-live/33d4b42/`](reports/chat-live/33d4b42/); the gap to 102 s is a hypothesis (memory contention), tested in stage 4 |
| Handover to a person, chat | the chat's rule replayed on 100 judged answers: 2 handovers, 2 of 12 bad answers caught | [`reports/chat-route-replay/7a99c45/`](reports/chat-route-replay/7a99c45/): an estimate of the rule, not a chat run |
| Answer quality, judge, 100 questions | 4B 67 good / 21 partial / 12 bad; 8B 66/29/5; 7B 56/29/15; 1.7B 50/27/23 | phase-C contexts, not the chat's retrieval; the judge is the session's model |
| Retrieval, lexical ruler | precision 0.5067, recall 0.905 | the ruler does not track meaning (P2, τ_b 0.156) — no longer a threshold |
| Graph lane (GR-3) | precision 0.5067 → 0.5487, +8.8 s to p95; recall on 15 multi-document questions 0.5 → 0.4 | NO-SHIP on the 200-ms budget; the generation half produced no evidence ([capsule](docs/evidence/gr3-graph-lane-ab.md)) |
| Shipment binding | admission recall 0.0000 | none of the 100 questions names a shipment (phase B, Q2b) |
| Engineering | 5,885 unit tests pass on the Mac on `96ee4e6` (124 skipped); CI's mypy, bandit, pip-audit and npm-audit gates pass, run by hand | CI starts no job since `e81f0c5` (2026-10-16): GitHub reports the account's billing |

The first quality number on the customer's path does not exist yet: it is [`PLAN.md`](PLAN.md)
stage 2.

## Stage 1 — closed 2026-10-18

The 25 findings, their outcomes and the live checks: [`docs/specs/stage1-fixes.md`](docs/specs/stage1-fixes.md);
records `reports/stage1/`, pinned by `tests/test_stage1_live_artifact.py`; one evidence row.

- **Fixed, a commit and a unit test each** (`8f94d84`…`4ca5ddd`): DOCX, HTML and PDF keep
  headings, lists and tables; a header with no words, the nearest section kept; a continued
  table piece repeats its column header; expansion reads each seam once; English instructions
  asking for the question's language, labels `[N | source=…]`; BM25 restored at any size.
- **Proven live**, one question per tenant on a fresh API: before the fixes WixQA ran on
  vectors alone after a restart, two of the three English questions got Russian answers, every
  prompt carried Russian labels; on the second generation and V3 every tenant hybrid, every
  answer in its question's script, no Cyrillic letter in an external prompt.
- **Also done:** the API's upload path cuts the chunks the measurements index (a test); the
  stage-2 tools — chat runner, judge's adapter with M2, signal tool, ≈ 100 questions per
  external base registered before any request (`e5e135a`). Limits and reasons: the spec.
- **Left from the [audit of 2026-10-18](docs/operations/audit_fable_18_10_26.md):** S8, the
  answer's script, a signal candidate for stage 3; the audit's keys bound by a test (later).

## Next

[`PLAN.md`](PLAN.md) stage 2 by [`docs/specs/stage2-four-corpora.md`](docs/specs/stage2-four-corpora.md)
(`5e308fe`): 100 aircargo answers, retrieval on 415 questions, 300 external answers; the graph lane amended 2026-10-19 — GR-3's archives counted, the live lane in stage 7; the judge amended before its first grade on Codex's second opinion (the spec, «The judge»).
**Done:** part 1 — 100 answers in ten batches (`p1-aircargo-b01`…`b10`), every case complete, no path break; batch 1 3,329 s, batches 2–10 28,749 s against a forecast of 36,540 s. Its judge's `plan.json`, frozen before the first grade: SHA-256 `1212f74a4e7b20844f02bd92bdcbe0c153f7c8cee00e153791b611061cea2593` (115 requests, 15 retests; private folder).
**Running:** part 2, retrieval on 415 questions in five runs, one at a time (forecast 17,300 s); stand `S=/Users/julia/RAG_new_chat_5e308fe`, chain log `$S/chatlive/runs/p2-chain.out`, each run's `$S/chatlive/runs/p2-KEY.log`.
Stop before the next run: `touch $S/chatlive/runs/p2-chain.stop`; at once: `pkill -f p2-chain.sh`, `pkill -f "stage2.sh retrieval p2"`, then `pkill -f "$S/chatlive/live_retrieval.py"`.

## Julia's decisions in force

The full list with dates is [`PLAN.md`](PLAN.md) §8.1. The ones that shape every step:
D11 (2026-10-03) — no person grades or approves anything in the process; D12 (2026-10-04) — the
session does all the work, no other model in any role but Codex's second opinion (2026-10-19); production on the Mac (2026-10-14);
Qwen3-4B (2026-10-16); the one plan accepted, external answers in stage 2 («Вариант B»), fixes
first, answers in the question's language, indexes as a new generation (all 2026-10-17).
When a plan's premise breaks, the session decides by the best final product and reports (2026-10-19). A push is her decision, asked each time.

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

- **Last green CI: `45a417a`** (2026-10-03, run 37157492007, 11 of 11 jobs; Pages run
  37157492017 built the site, `deploy` skipped: the repository is private). Run 34359692687 on
  `69a5140` verified the CVE-2026-9856 floor `transformers>=5.10.0` under `--require-hashes`,
  pip-audit clean.
- **Since `e81f0c5` (2026-10-16) CI starts no job** — GitHub's annotation names failed account
  payments. Until Julia settles it, a push is checked by the whole unit suite on the Mac.
- **Last push:** the last session's handoff to `origin/master`, 2026-10-18 about 15:45 UTC, at
  Julia's «да»; before it `b0bd87c` (stage 1 closed, 27 commits from `8f94d84`), 14:58 UTC, at her
  «пуш». CI and Pages runs fail in 3–4 s (billing). Nothing is left unpushed.
- Remote: `brownjuly2003-code/RAG_new`, private; pushes over HTTPS (command in
  [`CLAUDE.md`](CLAUDE.md)).

## How the project got here

Phases 0 and A (2026-08) wired a resolution kernel behind `/api/ask`; phase B labelled 100 real
aircargo cases (2026-09-25), blocked on shipment data (Q2b); phase C benchmarked generators;
stream GR measured graph retrieval (NO-SHIP); phase E prepared the public site locally;
[`PLAN.md`](PLAN.md) §7 stopped the quality campaign of `plan_03_10_26`. Detail:
[`ROADMAP.md`](ROADMAP.md), [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), this file's previous version.

## Links

- Plan — [`PLAN.md`](PLAN.md) · progress — [`ROADMAP.md`](ROADMAP.md) · evidence —
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) · documents map — [`docs/README.md`](docs/README.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md), [`AGENT_STATE.md`](AGENT_STATE.md) · queue for
  automation — [`BACKLOG.md`](BACKLOG.md) · module layout — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- Last session — [`docs/operations/session-handoff-2026-10-18-stage1-closed.md`](docs/operations/session-handoff-2026-10-18-stage1-closed.md)
