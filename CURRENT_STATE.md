# Current state — RAG_new

2026-10-25 · The plan: [`PLAN.md`](PLAN.md), accepted by Julia on 2026-10-17 («принять») ·
now: stage 3 — the handover signals on V4's answers; stage 2b closed 2026-10-25, V4 adopted ·
previous version:
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
`[document › section]` headers, expansion up to two neighbours each side. English answer
instructions request the question's language; actual language is measured. V3 (`4ca5ddd`)
wrote stage 2's answers; V4 (`4f48fed`), adopted by stage 2b's record, is the code's prompt.

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
| Answer quality, chat path, V3 | M1 good: aircargo 69, ConditionalQA 31, WixQA 27, MultiHop-RAG 65 of 100; bad 14, 64, 63, 34 | [stage-2 record](docs/evidence/stage2-record.md); one model judges, no person; MultiHop-RAG's M2 `NOT_EVIDENCE` |
| Answer quality, V4 against V3 | M1 bad, paired: WixQA 63 → 51, ConditionalQA 64 → 57, aircargo 14 → 17; good 27 → 40, 31 → 35, 69 → 63 | [V4 record](docs/evidence/answer-prompt-v4-record.md): pooled bad −9.5 pp, detected; in sample |

Stage 2's [retrieval baseline](docs/evidence/stage2-retrieval-baseline.md) (`7208ed2`): 415
questions, no path break, aircargo prompt parity 100/100. Its [300 external answers](docs/evidence/stage2-external-answers.md):
no path break, all in the question's language, 84 routed to a person, median 266.9 s. Its
[record](docs/evidence/stage2-record.md) grades all 400: aircargo's good share above
ConditionalQA's and WixQA's (+38.0, +42.0 pp, detected), not MultiHop-RAG's; M2 agrees
ConditionalQA 43/80, WixQA 29/100.

## Stage 1 — closed 2026-10-18

The 25 findings, their outcomes and the live checks: [`docs/specs/stage1-fixes.md`](docs/specs/stage1-fixes.md);
records `reports/stage1/`, pinned by `tests/test_stage1_live_artifact.py`; one evidence row.

- Loaders, headers, tables, overlap, language instructions and BM25 restoration fixed
  (`8f94d84`…`4ca5ddd`); new indexes and V3 passed one live question a tenant; stage-2 tools `e5e135a`.
- **Left from the [audit of 2026-10-18](docs/operations/audit_fable_18_10_26.md):** S8, the
  answer's script, a signal candidate for stage 3; the audit's keys bound by a test (later).

## Stage 2 — closed 2026-10-24

By [`docs/specs/stage2-four-corpora.md`](docs/specs/stage2-four-corpora.md) on stand `5e308fe`:
100 aircargo answers, retrieval on 415 questions, 300 external answers, the judge, the record.
Part 3 uses GR-3's archives; live graph measurement is stage 7. Judge amendment: the spec.
**Done:** part 1 — 100 answers in ten batches (`p1-aircargo-b01`…`b10`), all complete, no path break; judge record and frozen-plan hash in `reports/stage2/5e308fe/` (115 requests, 15 retests).
**Done:** part 2 — all 415 questions completed 2026-10-20; immutable export `reports/stage2/retrieval-20261021/`, provenance/derivation tests passed on the Mac (41 focused checks including docs).
**Done:** part 4 — 300 external answers, 30 counted batches, completed 2026-10-23 04:32 UTC after the pause and resume of 2026-10-22; immutable export `reports/stage2/external-answers-20261023/`, raw answers private in `D:/RAG_new_stage2_private/p4/resume-20261022/` (1,356 hashes verified).
**Done:** the judge — part 2's context plan (130 requests) and part 4's six plans (M1 without the reference, M2 with it; [amendment](docs/specs/stage2-four-corpora.md#the-judge), `575e24f`), 690 requests 2026-10-23 15:15 – 10-24 02:05 UTC, $122.45, six streams paced by the five-hour usage window; `p4-multihoprag-judge-m2` failed the stability rule (13/15, κ 0.59) and is `NOT_EVIDENCE`. Private folder `D:/RAG_new_stage2_private/p4/judge/`.
**Done:** part 5 — `reports/stage2/5e308fe/stage2-record.json` by `stage2_record.py`, `tests/test_stage2_record_artifact.py`, the [capsule](docs/evidence/stage2-record.md) and its evidence row.

## Stage 2b — closed 2026-10-25: V4 adopted

V4 fixes three of V3's own instructions found in stage 2's bad answers: a decline when the
documents answer in part, advice to contact a specialist no document names, the placeholder
«[N]»; [`tests/test_chat_answer_prompt_e2e.py`](tests/test_chat_answer_prompt_e2e.py) proves the
path's prompt. By the [spec](docs/specs/answer-prompt-v4.md) registered in `4f48fed`: 300 V4
answers on stand `4f48fed`, no path break, paired with stage 2's; stage 2's judge, all eight
plans and bridges counted. The [record](docs/evidence/answer-prompt-v4-record.md): the pooled
external bad share 127 → 108 of 200 (−9.5 pp, detected) — **adopted**; «[N]» and the referral
gone. Close to the line, not harm by the table: ConditionalQA declines 4 of its 20 not
answerable questions (V3 8); aircargo's nine good answers turned bad, eight by an unsupported claim.

## Next

1. [`PLAN.md`](PLAN.md) stage 3 — the [handover plan](docs/specs/handover-signal.md)'s signals on V4's 100 aircargo answers:
   plan `b7ad62a`, on the Mac since 10-25 17:27 UTC, end about 02:40–03:30 UTC 10-26.
2. Julia's three web research runs (2026-10-25), each repeated by Codex as a second opinion, one at a time in each queue: all six done and compared — literature, not our measurement, with a proposal for her decision: [research](docs/operations/research-2026-10-25/README.md).
3. Before a push: the whole Mac suite, mypy, bandit and the audits; locks refreshed 2026-10-25, audits clean on the laptop, the site build waits ([`BACKLOG.md`](BACKLOG.md)).

## Julia's decisions in force

[`PLAN.md`](PLAN.md) §8.1: no human grading; the session does the work, no other model except
the authorized Codex second-opinion role; Qwen3-4B; production on Mac; external answers in
stage 2; indexes as new generations. A broken premise is resolved and reported (2026-10-19).
Pushes require her authorization. Claude, the registered judge, was unavailable 2026-10-21/22;
on 2026-10-23 Julia: «Да, запускай судью». No replacement judge.

## Open for Julia

[`PLAN.md`](PLAN.md) §8.3, by stage: the widget's suspected defects R1/R2 and outcome B of the
[handover plan](docs/specs/handover-signal.md) (stage 3); removing
self-evaluation with its «Качество: N» badge, an `ollama serve` restart, the SLO (stage 4);
the service on her Mac and whether it counts as a deployment (stage 6); the locked parts
(stage 7); publication (stage 8). Any time: GitHub billing; Q2b (`PLAN.md` writes Q2б) — 100 real shipment-bound
requests (without them phase B stays blocked); Mac hours a day for runs; frozen items whose
condition is formally met ([`PLAN.md`](PLAN.md) §9).

## Accepted open risks

- **npm advisory GHSA-ch52-4w7c-c8xp** (`http-cache-semantics`, high): its exception was removed
  2026-10-24 with the lock at 4.3.0 — outside the advisory's range, not a fix (the same
  `max-stale` code); Astro never calls that code ([ADR 0009](docs/adr/0009-npm-advisory-without-fix.md)'s log).
- **ChromaDB CVEs** (CVE-2026-45830 / 45833 / 45831), no fix version. Ignored by id per ADR
  0008. Reviewed 2026-10-24: no fixed release. **Next review 2026-11-24.**
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
- Pushed 2026-10-25 ≈19:25 UTC at Julia's word («закомить и запуш все, что сделано»): `8fdbfee`..this file's commit, without the Mac suite —
  the Mac was measuring stage 3. Passed on the laptop: CI's two mypy commands, `ruff check`, bandit, pip-audit on `requirements.lock`
  (5 ignored), DEP-01. Not run yet: the Mac suite (last: `4f48fed`, 6,016 passed, 123 skipped), `b557082`'s guards on the Mac, the
  docs-site build on astro 7.3, the Linux lock install (CI only; billing). The push before, `8fdbfee` (2026-10-24), had the Mac suite.
  Not pushed: `tests/test_handover_signal_record_artifact.py`, which needs the stage-3 record.
- Private remote: `brownjuly2003-code/RAG_new`; HTTPS command in [`CLAUDE.md`](CLAUDE.md).

## Links

- Plan — [`PLAN.md`](PLAN.md) · progress — [`ROADMAP.md`](ROADMAP.md) · evidence —
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) · documents map — [`docs/README.md`](docs/README.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md), [`AGENT_STATE.md`](AGENT_STATE.md) · queue for
  automation — [`BACKLOG.md`](BACKLOG.md) · module layout — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- Last session — [stage 2b closed, stage 3's signals running](docs/operations/session-handoff-2026-10-25-stage3-signals-running.md)
