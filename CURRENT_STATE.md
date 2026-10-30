# Current state — RAG_new

2026-10-30 · The plan: [`PLAN.md`](PLAN.md), accepted by Julia on 2026-10-17 («принять») ·
now: stage 4 — items 0–5a read, each a record ([Next](#next)); none in the code yet: K = 14, num_ctx 3,584, the cache cap and INT8 of the reranker — it passed, but its five changes on 307 of the 400 — took her «да» as one package on 2026-10-30 (PLAN §8.1); the n-gram lever closed, read 2026-10-30 `NOT_EVIDENCE` ([record](docs/evidence/stage4-step5a-ngram-record.md)); INT8's short live series in the chat behind its setting (`81cd2ad`), registered in `3136fb8`, read 2026-10-30 `NOT_EVIDENCE` — stopped in its first block by another project's job on the shared Mac ([record](docs/evidence/stage4-step5a-live-record.md)); next, in a new session from [the handoff](docs/operations/session-handoff-2026-10-30-stage4-step5a-live.md): the slice that sets the package, the cache line on the Mac, stage 7 step 1's amendment and replay (registered in `8b922a1`, [spec](docs/specs/stage7-step1-arms-m3.md)), then the specs of items 6, 7 and stage 5 · previous version: [`archive/docs/state/current-state-through-2026-10-17.md`](archive/docs/state/current-state-through-2026-10-17.md).

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

Under every answer not already routed to a person, both say it was written automatically and
may be wrong, beside «Передать оператору» (stage 3, outcome C; Julia's «да», 2026-10-26).

Retrieval: BM25 + BGE-M3, 20 candidates each, RRF, CPU bge-reranker-v2-m3 keeps five — it earns
its place: without it the expanded five hold gold in 121 of 250 questions, not 141 ([no-reranker point](docs/evidence/no-rerank-point-record.md)).
Chunks: markdown sections, 800 characters/200 overlap; DOCX/HTML/PDF converted by loaders;
`[document › section]` headers, expansion up to two neighbours each side. English answer
instructions request the question's language; actual language is measured. V3 (`4ca5ddd`)
wrote stage 2's answers; V4 (`4f48fed`), adopted by stage 2b's record, is the code's prompt; V5, evidence first, was not adopted (stage 3б).

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
| Engineering | 6,258 passed, 123 skipped on `9b769f5`'s code, 2026-10-28; mypy, bandit and DEP-01 passed; pip-audit clean after `authlib` 1.9.1 | The Mac's unit suite; its venv is not built from the lock |
| Answer quality, chat path, V3 | M1 good: aircargo 69, ConditionalQA 31, WixQA 27, MultiHop-RAG 65 of 100; bad 14, 64, 63, 34 | [stage-2 record](docs/evidence/stage2-record.md); one model judges, no person; MultiHop-RAG's M2 `NOT_EVIDENCE` |
| Answer quality, V4 against V3 | M1 bad, paired: WixQA 63 → 51, ConditionalQA 64 → 57, aircargo 14 → 17; good 27 → 40, 31 → 35, 69 → 63 | [V4 record](docs/evidence/answer-prompt-v4-record.md): pooled bad −9.5 pp, detected; in sample |
| Answer quality, V5 against V4 | M1 bad, paired: WixQA 51 → 86, ConditionalQA 57 → 81, aircargo 17 → 89; good 40 → 4, 35 → 17, 63 → 8 | [V5 record](docs/evidence/answer-prompt-v5-record.md): not adopted, harm on WixQA; ConditionalQA's M1 and aircargo's plan `NOT_EVIDENCE`; in sample |
| Handover signals, V4 aircargo | of 17 bad answers: S2 and S6 catch 16 but mark 34 and 43 of 63 good; S3 catches 11, marks 28 good (in between); the cheap ones catch 0–4 | [record](docs/evidence/handover-signal-v4-aircargo.md): outcome C; one model judges, no person |
| Widget on the 4B, `/api/ask` | ten aircargo questions: auto 3, human 2, error_escalation 5; none of 7 retries finished inside the 24-call budget; median 31.1 min on a loaded Mac; production routes `human` (R1) | [record](docs/evidence/widget-4b-record.md): no judge; a fix is her word |
| Coverage beside quality, V3 → V4 | answered: WixQA 67 → 73, ConditionalQA 81 → 91, aircargo 98 → 100 of 100; CRAG score −0.020 → 0.105, −0.195 → −0.150, 0.655 → 0.560 | [coverage record](docs/evidence/coverage-metrics-record.md): unpaired, no model call; on ConditionalQA more wrong answers given out than right |

Stage 2's [retrieval baseline](docs/evidence/stage2-retrieval-baseline.md) (`7208ed2`): 415 questions,
no path break, aircargo prompt parity 100/100; MultiHop-RAG by the benchmark's own rule Hits@4 0.8714, above every published row ([record](docs/evidence/multihop-official-record.md)). Its [300 external answers](docs/evidence/stage2-external-answers.md):
no path break, all in the question's language, 84 routed to a person, median 266.9 s. Its [record](docs/evidence/stage2-record.md)
grades all 400: aircargo's good share above ConditionalQA's and WixQA's (+38.0, +42.0 pp, detected), not MultiHop-RAG's; M2 agrees ConditionalQA 43/80, WixQA 29/100.

## Stage 1 — closed 2026-10-18

The 25 findings, their outcomes and the live checks: [`docs/specs/stage1-fixes.md`](docs/specs/stage1-fixes.md);
records `reports/stage1/`, pinned by `tests/test_stage1_live_artifact.py`; one evidence row.

- Loaders, headers, tables, overlap, language instructions and BM25 restoration fixed
  (`8f94d84`…`4ca5ddd`); new indexes and V3 passed one live question a tenant; stage-2 tools `e5e135a`.
- **Left from the [audit of 2026-10-18](docs/operations/audit_fable_18_10_26.md):** the audit's keys bound by a test (later); S8 read in stage 3.

## Stage 2 — closed 2026-10-24

By [`docs/specs/stage2-four-corpora.md`](docs/specs/stage2-four-corpora.md) on stand `5e308fe`:
100 aircargo answers, retrieval on 415 questions, 300 external answers, the judge, the record. Part 3 uses GR-3's archives; live graph measurement is stage 7. Judge amendment: the spec.
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

1. [`PLAN.md`](PLAN.md) stage 3 — **outcome C** ([signal record](docs/evidence/handover-signal-v4-aircargo.md)): no signal worth wiring, S3 in between. Her «да» (2026-10-26): the handover line — done; no stage 2 for S3.
   Stage 3's encoder test read 2026-10-26: all three in between, none worth wiring; H catches 10 of 17 marking 8 of 63 ([record](docs/evidence/encoder-checkers-record.md)); its Amendment 1 read 2026-10-28: Horizon guard base in between too, 7 of 17 marking 7 of 63, and its read on V5's fresh answers `NOT_EVIDENCE` — stage 3 stays at outcome C. Step 4 read 2026-10-26: R1 confirmed, R2 not seen, no retry finished inside the call budget ([widget record](docs/evidence/widget-4b-record.md)). Stage 4's no-reranker point read 2026-10-26: the reranker stays.
2. Stage 3б closed 2026-10-28 — **V5 not adopted** ([record](docs/evidence/answer-prompt-v5-record.md)); V4 stays. [`PLAN.md`](PLAN.md) stage 4 with V4, each item a record and a row in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), none adopted — each lever her word (§8.3): step 0, the host prompt cache is the 4B's growth ([record](docs/evidence/stage4-step0-record.md)); step 1, contention yes, no lever ([record](docs/evidence/stage4-step1-record.md)); steps 2 and 2b, the continuation not held on the catches, the self-evaluation stays `classic` ([2](docs/evidence/stage4-step2-record.md), [2b](docs/evidence/stage4-step2b-record.md)); step 3, K = 14 the smallest K without a detected loss, its rerank a median 14.6 s faster ([curve](docs/evidence/k-curve-record.md), [timing](docs/evidence/stage4-step3-record.md)); item 4, num_ctx 3,584 the smallest window without a detected loss, its two prompts a median 24.7 s faster ([count](docs/evidence/stage4-step4-record.md), [timing](docs/evidence/stage4-step4b-record.md)), and the chat draws the answer before its suggested questions since `43874fc` ([index row](EVIDENCE_INDEX.md#slices)); item 5, the cap `cache-ram = 1024` holds the swap, −180.25 MiB from questions 6–10 to 26–30 ([record](docs/evidence/stage4-step5-record.md)); item 5a, INT8 of the reranker on stage 2's pools: `int8` passes — the gold holds, 141 → 144 of 250 after the expansion, and it reranks a median 12.0 s faster of 28.2 s (a ratio 1.75) — but its five differs from PyTorch's on 307 of the 400, so adopting it re-answers item 6 and stage 5; its short live series in the chat, registered in `3136fb8`, read 2026-10-30: `NOT_EVIDENCE`, stopped in its first block — the INT8 run failed step 7's look at the Mac again as `-r2`, another project's job at both its ends; nothing read, INT8's rerank printed at 21.6–34.1 s against PyTorch's 126.9–336.9 s ([record](docs/evidence/stage4-step5a-record.md), [live record](docs/evidence/stage4-step5a-live-record.md)); item 5a's n-gram decoding, registered in `5558ca8`, read 2026-10-30: `NOT_EVIDENCE`, seven of the thirteen readable, the seven leaning slower — the lever closes ([record](docs/evidence/stage4-step5a-ngram-record.md)). Stage 7: E stops ([record](docs/evidence/stage7-entity-probe-record.md)); step 1's arms replay, rewritten to PLAN's gate after [Julia's audit of 2026-10-30](docs/operations/audit_astra_30_10_26.md) and read cold, registered in `8b922a1` before the run ([spec](docs/specs/stage7-step1-arms-m3.md)). Research: [2026-10-29](docs/operations/research-2026-10-29/README.md), [2026-10-25](docs/operations/research-2026-10-25/analysis.md).
3. Pushed 2026-10-28 through `7caaf21` after ci_local PASS ([CI and pushes](#ci-and-pushes)); the 57 commits after it are local, the push her word; before it ci_local's full run again. pip-audit is clean since both locks moved `authlib` 1.7.0 → 1.9.1 (7 advisories).

## Julia's decisions in force

[`PLAN.md`](PLAN.md) §8.1: no human grading; the session does the work, no other model except
the authorized Codex second-opinion role; Qwen3-4B; production on Mac; external answers in
stage 2; indexes as new generations. A broken premise is resolved and reported (2026-10-19).
Pushes require her authorization. Claude, the registered judge, was unavailable 2026-10-21/22;
on 2026-10-23 Julia: «Да, запускай судью». No replacement judge. 2026-10-29: one subagent at a time; «cache-ram 1024: да» — item 5's series ran under the cap; the line was removed after it.

## Open for Julia

[`PLAN.md`](PLAN.md) §8.3, by stage: fixes of the widget's R1 (confirmed) and of its retry's call budget (stage 3); the
host-cache cap in production (her «да» for item 5's series 2026-10-29; under it the swap held, 2026-10-30), INT8 of the reranker (read 2026-10-30: it passes, its five changes on 307 of the 400), the SLO, K = 14, num_ctx 3,584 and INT8 in the answer path (stage 4; together one re-answer of item 6 and stage 5); the service on her Mac and whether it counts as a
deployment, the first release's composition and the share of bad `auto` answers a pilot accepts, with stages 4–5's numbers (stage 6); the locked parts (stage 7); publication (stage 8). Decided 2026-10-28:
the «Качество: N» badge stays, made faster (stage 4, step 2); stage 7 keeps P1b and the graph. Any time: GitHub billing; Q2b (`PLAN.md` writes Q2б) — 100 real shipment-bound
requests (without them phase B stays blocked); Mac hours a day for runs; frozen items whose condition is formally met ([`PLAN.md`](PLAN.md) §9).

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

- Last green GitHub CI: `45a417a`, 2026-10-03, 11/11 jobs; since `e81f0c5` (2026-10-16) billing
  prevents jobs starting. The gate since: ci_local, the workflows in a Linux container on the Mac.
- Run 34359692687 on `69a5140` verified the CVE-2026-9856 floor `transformers>=5.10.0` under
  `--require-hashes`, pip-audit clean; both locks still pin it.
- Pushed 2026-10-28 12:47 UTC at Julia's «да»: `43009ac..7caaf21`, 28 commits (the research analysis, coverage, the stage-3 record,
  the handover line, the no-reranker point, the encoders, the widget read, V5, `authlib` 1.9.1). ci_local on `7caaf21`'s tree: the full
  run PASS, 17 steps (lint, type-check, unit 3.11 and 3.13, integration ×2, pre-commit, security; the Linux lock installed), and `ci/helm`
  with its kind cluster PASS on master. Migrations and the docs-site build passed on `727b6e9`, which differs only in `tests/conftest.py`
  and two reports' spaces. Not covered: `ci/regression-eval` (`hashFiles()` at run time). The first run had failed on Python 3.13's `sum()`.
- Private remote: `brownjuly2003-code/RAG_new`; HTTPS command in [`CLAUDE.md`](CLAUDE.md).

## Links

- Plan — [`PLAN.md`](PLAN.md) · progress — [`ROADMAP.md`](ROADMAP.md) · evidence —
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) · documents map — [`docs/README.md`](docs/README.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md), [`AGENT_STATE.md`](AGENT_STATE.md) · queue for
  automation — [`BACKLOG.md`](BACKLOG.md) · module layout — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- Last session — [stage 4: item 5a read, the n-gram lever closed, INT8's live series `NOT_EVIDENCE`; stage 7 step 1 registered; her «да» to the package](docs/operations/session-handoff-2026-10-30-stage4-step5a-live.md)
