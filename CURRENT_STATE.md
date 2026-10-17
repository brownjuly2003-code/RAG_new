# Current state — RAG_new

2026-10-17 · The plan: [`PLAN.md`](PLAN.md), accepted by Julia on 2026-10-17 («принять») ·
next: its stage 1 · previous version of this file:
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

Retrieval: BM25 and BGE-M3 vectors merged by RRF, then the bge-reranker-v2-m3 cross-encoder on
the CPU picks 5 of 20 candidates. Documents are cut by their markdown sections (at most 800
characters, 200 overlap inside a long section), each chunk carries a header with its document
and section path, and parent expansion adds up to two neighbouring chunks on each side.

**Production is `deproject-mac`** (Julia, 2026-10-14: «прод на маке»): i5-7500, 4 cores, 8 GB,
Ollama 0.33.2 on the CPU. **The model is Qwen3-4B-Instruct-2507** (Julia, 2026-10-16; the code
default since `7a99c45`). No service runs between measurements yet: a stand of a commit is
brought up for each run ([`PLAN.md`](PLAN.md) stage 6 makes it a service).

**Corpora.** aircargo — ours: 201 Russian markdown documents, 5,589 chunks, 100 questions
written by an agent from the documents, labels approved by Julia on 2026-09-25 (the only real
labelled cases). Three external bases connected 2026-10-05/07 for universality: ConditionalQA
(13,778 chunks), WixQA (37,571), MultiHop-RAG (11,231); their questions are split into open and
locked parts (`evaluation/external_parts.json`). No quality run has used them yet.

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
| Engineering | 5,820 unit tests pass on the Mac on `3e52a02` | CI starts no job since `e81f0c5` (2026-10-16): GitHub reports the account's billing |

The first quality number on the customer's path does not exist yet: it is [`PLAN.md`](PLAN.md)
stage 2.

## Known defects — fixed by PLAN.md stage 1

Found 2026-10-17 by reading the code; none is measured on the chat path yet.

- **Loaders.** Section chunking works only for markdown: DOCX loses its headings and drops its
  tables, HTML is flattened to one line, PDF has no headings. aircargo is markdown and the
  external bases were converted to markdown by the connection script, so every measurement so
  far was the best case.
- **Chunk header.** A Russian phrase «[Контекст: Из документа …, раздел: …]» on every corpus;
  the heading path is cut at 200 characters from the wrong end (8–34 % of external chunks).
- **Long tables.** A continued table chunk has no column-header row.
- **Overlap.** Parent expansion glues neighbouring pieces with their 200-character overlap, so
  the prompt repeats text.
- **Answer language.** The prompts are Russian and do not set the answer's language; Julia
  decided 2026-10-17: answer in the question's language.
- **External tenants.** Not yet shown to run the same hybrid path as aircargo.

## Next

[`PLAN.md`](PLAN.md) stage 1 (Julia, 2026-10-17: the fixes «поставить в приоритет»): the audit
and the fixes above, each with a test; the indexes of the four corpora rebuilt as a new
generation beside the old (Julia agreed 2026-10-17; the old collections stay for rollback).
Then stage 2 measures all four corpora on the fixed code. Nothing else runs on the Mac first.
Step by step, with every code location, how to test on the Mac and how to bring up a stand:
[the last handoff, «Next actions»](docs/operations/session-handoff-2026-10-17-one-plan.md#next-actions--stage-1).

## Julia's decisions in force

The full list with dates is [`PLAN.md`](PLAN.md) §8.1. The ones that shape every step:
D11 (2026-10-03) — no person grades or approves anything in the process; D12 (2026-10-04) — the
session does all the work, no other model in any role; production on the Mac (2026-10-14);
Qwen3-4B (2026-10-16); the one plan accepted, external answers in stage 2 («Вариант B»), fixes
first, answers in the question's language, indexes as a new generation (all 2026-10-17).
A push is her decision, asked each time.

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
- **Last push:** `3e52a02` to `origin/master` at Julia's word, 2026-10-17 (suite on the Mac:
  5,820 passed, 123 skipped).
- Remote: `brownjuly2003-code/RAG_new`, private; pushes over HTTPS (command in
  [`CLAUDE.md`](CLAUDE.md)).

## How the project got here

Phases 0 and A (2026-08) built and wired a deterministic resolution kernel behind `/api/ask`;
phase B labelled 100 real aircargo cases (approved 2026-09-25) and is blocked on shipment data
(Q2b); phase C benchmarked generators; stream GR measured graph retrieval (NO-SHIP); phase E
prepared the public site locally; the quality campaign of `plan_03_10_26` was stopped by
[`PLAN.md`](PLAN.md) §7. Detail: [`ROADMAP.md`](ROADMAP.md), the evidence register
[`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), and this file's previous version (link at the top).

## Links

- Plan — [`PLAN.md`](PLAN.md) · progress — [`ROADMAP.md`](ROADMAP.md) · evidence —
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) · documents map — [`docs/README.md`](docs/README.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md), [`AGENT_STATE.md`](AGENT_STATE.md) · queue for
  automation — [`BACKLOG.md`](BACKLOG.md) · module layout — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- Last session — [`docs/operations/session-handoff-2026-10-17-one-plan.md`](docs/operations/session-handoff-2026-10-17-one-plan.md)
