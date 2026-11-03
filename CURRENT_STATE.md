# Current state — RAG_new

2026-11-03 · The plan: [`PLAN.md`](PLAN.md), accepted by Julia on 2026-10-17 («принять») ·
now: stage 8 done 2026-11-02 — RAG_new public with its whole history, Pages on; stage 5в, the generator's ceiling, read 2026-11-03: **the generator is the bottleneck** (row 2) — on the same 300 saved prompts Codex (cw, `gpt-6-astra`, xhigh) answers good by M1 220 of the 224 questions with the answer in the context, the package 120, a detected rise; the pooled M2 agreement with the reference 0.45 → 0.55 of 180, not detected ([record](docs/evidence/generator-ceiling-record.md)); her word the same evening, «бюджета нет. испольхуй астру xhigh через кодекс»: Codex answers in the product on her subscription, the 4B its fallback — stage 6 item 0, in work ([Next](#next)); stage 5б read 2026-11-02 — **V6 not adopted** (harm: pooled M2 agreement with the reference 0.45 → 0.356 of 180, detected), the package stays ([record](docs/evidence/answer-prompt-v6-record.md)); stage 4 — items 0–5a read, each a record; the package — K = 14, num_ctx 3,584, the cache cap and INT8 of the reranker, her «да» of 2026-10-30 (PLAN §8.1) — is in: the line `cache-ram = 1024` on the Mac for good since 2026-10-30 23:57 UTC, the rest the code's defaults since `6c52b06` with its E2E test; stage 7 step 1's Amendment 1, the control the package, registered in the same commit, read 2026-10-31: **H stays**, stage 7 closed ([record](docs/evidence/stage7-step1-arms-record.md)); items 6 and 7 read 2026-10-31 on stand `138f3b3`: aircargo's M1 good 63 → 73 of 100 against V4, a detected gain ([record](docs/evidence/stage4-item6-final-aircargo-record.md)); the first word a median 89.3 s, the whole answer 170.2 s, the SLO proposal 270 s and 360 s, hers to name ([record](docs/evidence/stage4-item7-final-speed-record.md)); stage 5 read 2026-11-02: **holds**, the package's numbers published — the pooled WixQA + ConditionalQA M1 bad share 0.54 → 0.56 of 200, not detected; WixQA's M1 good share 0.40 → 0.30, a **detected fall**, outside the registered decision; MultiHop-RAG `NOT_EVIDENCE`, its bridge unstable ([record](docs/evidence/stage5-final-external-record.md)); V6 (stage 5б) registered 2026-11-02 with its pre-request amendment 1 (`4a5c36e`), its chain on the Mac since 02:22 UTC; RAG_new public with its history since 2026-11-02 — her «Да» to the scan report ([runbook](docs/operations/stage8-publication-runbook.md)); Codex (cw) the executor since her word of 2026-10-30 · previous version: [`archive/docs/state/current-state-through-2026-10-17.md`](archive/docs/state/current-state-through-2026-10-17.md).

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

Retrieval: BM25 + BGE-M3, 14 candidates each, RRF, bge-reranker-v2-m3 as INT8 in ONNX Runtime on the CPU keeps five (stage 4's package, `6c52b06`) — the reranker earns
its place: without it the expanded five hold gold in 121 of 250 questions, not 141 ([no-reranker point](docs/evidence/no-rerank-point-record.md)).
Chunks: markdown sections, 800 characters/200 overlap; DOCX/HTML/PDF converted by loaders;
`[document › section]` headers, expansion up to two neighbours each side. English answer
instructions request the question's language; actual language is measured. V3 (`4ca5ddd`)
wrote stage 2's answers; V4 (`4f48fed`), adopted by stage 2b's record, is the code's prompt, in a 3,584-token window since `6c52b06`; V5, evidence first, was not adopted (stage 3б).

**Production is `deproject-mac`** (Julia, 2026-10-14: «прод на маке»): i5-7500, 4 cores, 8 GB,
Ollama 0.33.2 on the CPU; llama-server's host prompt cache capped at 1,024 MiB (`cache-ram` in `~/.config/llama.cpp/config.ini`, since 2026-10-30). **The model is Qwen3-4B-Instruct-2507** (Julia, 2026-10-16; the code
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
| Earlier chat speed and memory, 4B | median 320 s; first token 223 s; rerank 102 s; swap up to 12,274 MB, runner +312 MB/request | [30-question idle-Mac record](reports/chat-live-4b/19beeb1/) |
| Final path, the package (items 6–7, stage 5) | aircargo M1 good 63 → 73 of 100 against V4, detected; bad 17 → 13 not detected; first word median 89.3 s, p90 255.6 s; whole answer median 170.2 s, p90 338.8 s; against stage 2's answers M1 bad WixQA 51 → 59, ConditionalQA 57 → 53, pooled not detected; good 40 → 30, a detected fall, and 35 → 38; MultiHop-RAG `NOT_EVIDENCE` | [item 6](docs/evidence/stage4-item6-final-aircargo-record.md), [item 7](docs/evidence/stage4-item7-final-speed-record.md): stand `138f3b3`, 100 and 30 questions, one day; [stage 5](docs/evidence/stage5-final-external-record.md): stand `2057ad0`, 100 per base |
| Retrieval alone | median 27.6 s, rerank 27.3 s | [record](reports/chat-live/33d4b42/); stage 4 investigates contention |
| Engineering | 7,889 passed, 125 skipped on `fcb4b5a`'s code with stage 5's tools, 2026-10-31; CI's mypy clean on `6c52b06`; bandit, DEP-01 and pip-audit last passed on `9b769f5`, 2026-10-28 | The Mac's unit suite; its venv is not built from the lock |
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
2. Stage 3б closed 2026-10-28 — **V5 not adopted** ([record](docs/evidence/answer-prompt-v5-record.md)); V4 stays. [`PLAN.md`](PLAN.md) stage 4 with V4, each item a record and a row in [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md), the package of K = 14, num_ctx 3,584, the cache cap and INT8 took her «да» 2026-10-30 and is in since `6c52b06`: step 0, the host prompt cache is the 4B's growth ([record](docs/evidence/stage4-step0-record.md)); step 1, contention yes, no lever ([record](docs/evidence/stage4-step1-record.md)); steps 2 and 2b, the continuation not held on the catches, the self-evaluation stays `classic` ([2](docs/evidence/stage4-step2-record.md), [2b](docs/evidence/stage4-step2b-record.md)); step 3, K = 14 the smallest K without a detected loss, its rerank a median 14.6 s faster ([curve](docs/evidence/k-curve-record.md), [timing](docs/evidence/stage4-step3-record.md)); item 4, num_ctx 3,584 the smallest window without a detected loss, its two prompts a median 24.7 s faster ([count](docs/evidence/stage4-step4-record.md), [timing](docs/evidence/stage4-step4b-record.md)), and the chat draws the answer before its suggested questions since `43874fc` ([index row](EVIDENCE_INDEX.md#slices)); item 5, the cap `cache-ram = 1024` holds the swap, −180.25 MiB from questions 6–10 to 26–30 ([record](docs/evidence/stage4-step5-record.md)); item 5a, INT8 of the reranker on stage 2's pools: `int8` passes — the gold holds, 141 → 144 of 250 after the expansion, and it reranks a median 12.0 s faster of 28.2 s (a ratio 1.75) — but its five differs from PyTorch's on 307 of the 400, so adopting it re-answers item 6 and stage 5; its short live series in the chat, registered in `3136fb8`, read 2026-10-30: `NOT_EVIDENCE`, stopped in its first block — the INT8 run failed step 7's look at the Mac again as `-r2`, another project's job at both its ends; nothing read, INT8's rerank printed at 21.6–34.1 s against PyTorch's 126.9–336.9 s ([record](docs/evidence/stage4-step5a-record.md), [live record](docs/evidence/stage4-step5a-live-record.md)); item 5a's n-gram decoding, registered in `5558ca8`, read 2026-10-30: `NOT_EVIDENCE`, seven of the thirteen readable, the seven leaning slower — the lever closes ([record](docs/evidence/stage4-step5a-ngram-record.md)). Stage 7: E stops ([record](docs/evidence/stage7-entity-probe-record.md)); step 1's arms replay, rewritten to PLAN's gate after [Julia's audit of 2026-10-30](docs/operations/audit_astra_30_10_26.md) and read cold, registered in `8b922a1` before the run ([spec](docs/specs/stage7-step1-arms-m3.md)); its Amendment 1, the control the package, registered in `6c52b06` after its [cold read](docs/operations/audit_opus55_31_10_26_stage7_amendment1.md); read 2026-10-31: **H stays** — parity 415 of 415, S stopped by a detected loss (125 → 99 of 180), P no detected difference, the stage closed ([record](docs/evidence/stage7-step1-arms-record.md)). Stage 5, the package on the external bases, registered 2026-10-31 ([spec](docs/specs/stage5-final-external.md)): 300 answers, ≈ 27 h of the Mac, each base graded while the Mac answers the next; answered from 2026-10-31 14:21 UTC, their plans frozen (`da0988a`, `bd18bce`, `42dcd1a`), 735 judge requests graded; read 2026-11-02: **holds** — the pooled M1 bad share 0.54 → 0.56 of 200, not detected; WixQA's M1 good 0.40 → 0.30, a detected fall; MultiHop-RAG `NOT_EVIDENCE`, its bridge 12 of 15 ([record](docs/evidence/stage5-final-external-record.md)). Stage 5б, answer V6, registered in `9f968bb` and its amendment 1 in `4a5c36e` before any request ([spec](docs/specs/answer-prompt-v6.md)); WixQA and ConditionalQA answered from 2026-11-02 02:22 UTC, their plans frozen (`d15fa87`, `a7202e4`); read 2026-11-02: **not adopted — harm**, row 1: the pooled M2 agreement with the reference 0.45 → 0.356 of 180, detected, outweighs the pooled M1 bad share's detected fall 0.56 → 0.425 of 200; aircargo `NOT_EVIDENCE` — her forced stop of the Mac's jobs, then the harm STOP at 70 of 100 ([record](docs/evidence/answer-prompt-v6-record.md)). The package stays. Stage 5в, the generator's ceiling, registered in `54a46e2` with its amendment `f93508a` ([spec](docs/specs/generator-ceiling.md)), read 2026-11-03: **the generator is the bottleneck** — M1 good 120 → 220 of 224 with the answer in the context, detected; per base 30 → 92, 38 → 92, 73 → 100 of 100; of the package's 159 not-good answers 100 the generator's losses, 9 retrieval's; M2 0.45 → 0.55 of 180, not detected ([record](docs/evidence/generator-ceiling-record.md)). Her word the same evening: Codex (cw, `gpt-6-astra`, xhigh) answers in the product on her subscription, the 4B its fallback — [`PLAN.md`](PLAN.md) stage 6 item 0, in work. Research: [2026-10-29](docs/operations/research-2026-10-29/README.md), [2026-10-25](docs/operations/research-2026-10-25/analysis.md).
3. Published 2026-11-02: RAG_new public, master pushed after ci_local's full run on `d60913d` ([CI and pushes](#ci-and-pushes)); every later push needs her word and both scans ([runbook](docs/operations/stage8-publication-runbook.md) §6). pip-audit is clean since both locks moved `authlib` 1.7.0 → 1.9.1 (7 advisories) and, on 2026-11-02, joserfc to 1.7.7 and pypdf to 6.21.4 (9 advisories, `985577f`).

## Julia's decisions in force

[`PLAN.md`](PLAN.md) §8.1: no human grading; the session does the work, no other model except
Codex (cw) — a second opinion since 2026-10-19, the executor since 2026-10-30; Qwen3-4B; production on Mac; external answers in
stage 2; indexes as new generations. A broken premise is resolved and reported (2026-10-19).
Pushes require her authorization. Claude, the registered judge, was unavailable 2026-10-21/22;
on 2026-10-23 Julia: «Да, запускай судью». No replacement judge. 2026-10-29: one subagent at a time; «cache-ram 1024: да» — item 5's series ran under the cap. 2026-10-30: «да» to stage 4's package — the cap's line back for good; K = 14, num_ctx 3,584 and INT8 the code's defaults (`6c52b06`). 2026-11-01: «да» — (replaced in the evening) stage 8's clean public repository right after stage 5's record, before stage 6, published on her word after she sees it locally; V6 (stage 5б) on the Mac in parallel. Evening: «Да, сделать приватным. А текущую историю - в RAG_new и сделать публичной» — the old repository private the same evening; RAG_new public with its whole history after a scan of it and her one yes/no on its report. 2026-11-02: «Да» to the scan report — the aircargo corpus may be public; the push, the `wip/*` branches' deletion, the switch and Pages in the runbook's order. 2026-11-03 evening: «бюджета нет. испольхуй астру xhigh через кодекс» — the product's answer from Codex (cw, `gpt-6-astra`, xhigh) on her subscription, the 4B the fallback (D5).

## Open for Julia

[`PLAN.md`](PLAN.md) §8.3, by stage: fixes of the widget's R1 (confirmed) and of its retry's call budget (stage 3); the
SLO — item 7's proposal 270 s to the first word, 360 s to the whole answer, or the session's 270 s / 420 s for 9 of 10, on the package now that V6 is not adopted (stage 4); the service on her Mac and whether it counts as a
deployment, the first release's composition and the share of bad `auto` answers a pilot accepts, with stages 4–5's numbers (stage 6); publication — done 2026-11-02 (stage 8) — the locked parts wait, stage 7 closed with H. Decided 2026-10-28:
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

- Last green GitHub CI: run 41681285267 on `591481f` (stage 5в's record), 2026-11-03, 11/11 jobs;
  before it 41518929372 on `02b055a`. The gate stays ci_local (Linux container, Mac).
- Run 34359692687 on `69a5140` verified the CVE-2026-9856 floor `transformers>=5.10.0` under
  `--require-hashes`, pip-audit clean; both locks still pin it.
- Published 2026-11-02 at her «Да»: the three `wip/*` branches deleted on GitHub, `weekly-report` disabled,
  visibility public, Pages built by workflow, master pushed on from `7caaf21` with the stage 5, V6 and CI-fix commits.
  ci_local's full run on `d60913d`: INCOMPLETE, 30 steps passed, 0 failed; uncovered only `ci/regression-eval`'s four `hashFiles()` steps, as before.
  GitHub Actions run free again on the public repository; ci_local stays the gate before each push; its
  defects met on the way are in [this session's handoff](docs/operations/session-handoff-2026-11-02-v6-record-publication.md).
- Public remote: `brownjuly2003-code/RAG_new`; HTTPS command in [`CLAUDE.md`](CLAUDE.md).

## Links

- Plan — [`PLAN.md`](PLAN.md) · progress — [`ROADMAP.md`](ROADMAP.md) · evidence —
  [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) · documents map — [`docs/README.md`](docs/README.md)
- Agent conventions — [`CLAUDE.md`](CLAUDE.md), [`AGENT_STATE.md`](AGENT_STATE.md) · queue for
  automation — [`BACKLOG.md`](BACKLOG.md) · module layout — [`DEPRECATIONS.md`](DEPRECATIONS.md)
- Last session — [stage 5в answered whole, two keys graded, aircargo's judging paused](docs/operations/session-handoff-2026-11-03-stage5v-arm-judge.md); before it — [stage 5 and V6 recorded (V6 not adopted, harm), RAG_new published](docs/operations/session-handoff-2026-11-02-v6-record-publication.md)
