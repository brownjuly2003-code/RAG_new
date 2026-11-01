# RAG_new documentation

The map of every maintained document. Start with the smallest one that answers the question.
History — superseded plans, audits, session handoffs, dated experiment logs — is in
[`../archive/`](../archive/README.md) and never drives current work.

## Where the project stands — the repository root

| File | What it answers |
|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | How an agent works here: who does what, machines, the slice rule |
| [`CURRENT_STATE.md`](../CURRENT_STATE.md) | What is true now: the product, its numbers, known defects, the next step |
| [`PLAN.md`](../PLAN.md) | The one plan (accepted 2026-10-17): stages, the measuring method, Julia's decisions |
| [`ROADMAP.md`](../ROADMAP.md) | Progress by stage of the plan; frozen streams and their unfreeze conditions |
| [`EVIDENCE_INDEX.md`](../EVIDENCE_INDEX.md) | Every published record with its provenance, one row each |
| [`AGENT_STATE.md`](../AGENT_STATE.md) | Working conventions and traps (read by the autopilot) |
| [`BACKLOG.md`](../BACKLOG.md) | The short queue and dated reviews (read by the autopilot) |
| [`README.md`](../README.md) | The project's front page: features, API, web UI |
| [`DEPRECATIONS.md`](../DEPRECATIONS.md) | Module layout and deprecated import paths |

## Running the service

| Need | Document |
|---|---|
| Run it locally | [Quickstart](QUICKSTART.md) |
| Providers, storage, auth, feature flags | [Configuration](CONFIGURATION.md) |
| Deploy or package it | [Deployment](DEPLOYMENT.md) |
| Evaluation commands and operating it | [Operations & evaluation](OPERATIONS.md) |
| Troubleshoot | [Runbook](runbook.md), [disaster recovery](disaster-recovery.md) |
| Backups | [Backup & restore](operations/backup-restore.md), [encryption at rest](operations/backup-encryption.md) |
| Resolution database roles | [PostgreSQL roles](operations/resolution-postgres-roles.md) |
| Helm chart | [Helm lint](operations/helm-lint.md) |
| A live GraceKelly smoke (explicit opt-in only) | [GraceKelly smoke](operations/gracekelly-smoke.md) |
| The chat as a launchd service on the Mac (a draft; installed only on Julia's word) | [macOS service](operations/macos-service.md) |

## How it is built — `architecture/` and `adr/`

The architecture set is the design baseline of 2026-08-21, written before the code: read it for
intent, and the code and [`CURRENT_STATE.md`](../CURRENT_STATE.md) for what runs.

| Document | What it describes |
|---|---|
| [Architecture baseline](architecture/README.md) | Entry to the architecture set |
| [System architecture](architecture/system-architecture.md) | Components and request paths |
| [Domain and data model](architecture/domain-data-model.md) | Entities of the resolution kernel and their storage |
| [Resolution contract v0.1](architecture/resolution-contract-schema-v0.1.md) | The schema of a resolution answer |
| [Security and reliability](architecture/security-reliability.md) | Tenancy, auth, failure handling |
| [Graph search, in plain words](architecture/graph-search.md) | The structure and entity graphs and what was measured (in Russian) |
| [`adr/`](adr/) 0001–0009 | Decisions: graph deferral (0001), modular monolith (0002), PostgreSQL authority (0003), governed actions (0004), LangGraph boundary (0005), durable turns (0006), retrieval storage stays (0007), inherited CI red jobs and the Chroma CVE ignores (0008), the npm advisory exception (0009) |

## Specs — `specs/`

**In use by the plan:** [handover signal](specs/handover-signal.md) — which answers go to a
person; run as [`PLAN.md`](../PLAN.md) stages 2 and 3; its
[record](evidence/handover-signal-v4-aircargo.md) on V4's answers: outcome C, S3 in between. [Stage 2](specs/stage2-four-corpora.md)
— the four corpora measured on the chat path: the stand, the questions, the stop rules, the
metrics and the judge, registered before the first request. [The answer prompt
V4](specs/answer-prompt-v4.md) — stage 2b: three defects of the answer prompt V3, the fix, and
its paired measurement against stage 2's answers, registered before the first request; its
[record](evidence/answer-prompt-v4-record.md): adopted 2026-10-25. [Coverage
metrics](specs/coverage-metrics.md) — coverage beside quality among the answered, the CRAG
score and the decline matrices, read from the committed judge records with no model call. [The
no-reranker point](specs/no-rerank-point.md) — the fused order's first five against the
reranker's, on stage 2's saved lists, with the product's own expansion and no model. [The
encoder checkers](specs/encoder-checkers.md) — three small models that read Russian, their
thresholds chosen on RusHallu-RAG and V4's English answers, read once on the 100 aircargo ones;
its [record](evidence/encoder-checkers-record.md): all three in between, none worth wiring;
Horizon guard base, its Amendment 1, in between too.
[The widget on the 4B](specs/widget-4b.md) — stage 3's step 4: R1 under `RAG_ENV=production`
and ten widget answers through `/api/ask`, their routes, passes and seconds. [The answer prompt
V5](specs/answer-prompt-v5.md) — stage 3b: evidence first, replayed on V4's saved contexts and
judged against V4's answers, registered before the first request; its
[record](evidence/answer-prompt-v5-record.md): not adopted 2026-10-28. [The K curve after
expansion](specs/k-curve-expanded.md) — stage 4's step 3: each lane's first K, 5 to 20, through
the product's fusion, rerank cut and expansion on stage 2's saved lists, against K = 20, with no
model; registered before the count; its [record](evidence/k-curve-record.md): the smallest K
without a detected loss is 14, 2026-10-28. [MultiHop-RAG's retrieval by the official
rule](specs/multihop-official-retrieval.md) — the recount by the published rules: the
benchmark's `retrieval_evaluate.py` on stage 2's lists, Hits@4, Hits@10, MRR@10 and MAP@10
beside stage 2's own and the published band, with no model; registered before the count; its
[record](evidence/multihop-official-record.md): all four above the band, 2026-10-28. [Stage 4,
step 0](specs/stage4-step0-diagnostics.md) — diagnostics before the levers: llama-server's host
prompt cache, the Mac's paging and the reused prefix over five aircargo answers on V4's stand,
read from the server's log and a sampler, nothing changed; registered before the first request; its
[record](evidence/stage4-step0-record.md): the cache is the 4B's growth, nothing restored, the weights
repacked, 2026-10-28. [Stage 4, step 1](specs/stage4-step1-rerank-memory.md) — where the rerank's
102 s go: four aircargo questions on V4's stand, each asked with the model resident (A) and with it
unloaded before the question (B), in two runs, BABA and ABAB, beside step 0's sampler; registered
before the first request; its [record](evidence/stage4-step1-record.md): contention yes, net faster
by its sign alone, no lever adopted, 2026-10-28. [Stage 4, step 3's timing](specs/stage4-step3-k-timing.md) — K = 14
against 20 with the retrieval alone: thirteen aircargo questions on V4's stand with no model, four
runs ABBA, the rerank's seconds paired a question at a time; registered before the first request;
its [record](evidence/stage4-step3-record.md): K = 14 faster on 12 of 12, a median 0.528 of K = 20's
rerank seconds (14.566 s less), no K adopted, 2026-10-28. [Stage 4, step 2](specs/stage4-step2-self-eval-continuation.md) —
the self-eval as the answer chat's next turn: thirteen aircargo questions on a stand of the
new code, mode both, the continuation's score and seconds paired with the classic's;
registered before the first request; its [record](evidence/stage4-step2-record.md): the continuation
faster on 13 of 13, a median 54.009 s saved (a ratio 0.1408), routes agree, the candidate the
continuation, no default changed, 2026-10-29. [Stage 4, step 2b](specs/stage4-step2b-continuation-labels.md) —
the continuation asked cold: first on step 2's 25 warm-scored answers, whose routes it must keep
(the bridge), then on stage 3's 80 labelled aircargo answers beside the classic's saved scores:
catches of the 17, over-marks of the 63, answers without a score; registered before the first
request, run because step 2's candidate is the continuation. Read 2026-10-29, not held: the
bridge held, the catches not — 0 of the 17 flagged, the classic's 2 — and the default stays
`classic`; its [record](evidence/stage4-step2b-record.md).
[Stage 7's entity probe](specs/stage7-entity-probe.md) — the entity extraction's cost: an
English prompt on 100 MultiHop-RAG chunks, the product's own JSON-schema call with the 4B; gate
G2 stops the entity lane if 11,231 chunks × the upper bound of the mean pass 24 h or fewer than
95 of the 100 outputs are valid; registered before the first request in `52dd160`. Read
2026-10-29: G2 failed at the first look, 25.1 h at the lower bound, and E stops; its
[record](evidence/stage7-entity-probe-record.md).
[Stage 7, step 1](specs/stage7-step1-arms-m3.md) — the retrieval arms at M3, without an
answer: H, S (the structural graph's sections, with S's expansion fix) and P (P1b) replayed
on stage 2's lists through the product's retrievers; an arm goes on to answers only on an M3
gain at ConditionalQA and WixQA pooled larger than the MDE, aircargo's context judge only
stopping it; registered before the run in `8b922a1`.
[Stage 4, step 4](specs/stage4-step4-prompt-budget.md) — a shorter answer prompt: stage 2's 400
questions fitted at num_ctx 4,096 down to 2,304 under today's `QA_PROMPT_V4`, without a model;
gold at «sent» against 4,096 by an exact McNemar, per base and pooled, and the smallest window
without a detected loss read from the top; registered before the count in `b192fb0`. Read
2026-10-29: 3,584, not the forecast's 3,328, and aircargo's prompt a median 456 estimated
tokens shorter there; its [record](evidence/stage4-step4-record.md).
[Stage 4, step 4b](specs/stage4-step4b-window-timing.md) — num_ctx 3,584 against 4,096,
timed: aircargo's first thirteen questions on step 4's documents, the chat's answer and its
classic self-evaluation in 26 blocks ABBA on the idle Mac, each begun with no model; the two
calls' prompt seconds by an exact sign test over the twelve pairs; registered before the
first request in `d1ef9e5`. Read 2026-10-30: faster on 12 of 12 pairs, a median 24.681 s
less, a ratio 0.792; its [record](evidence/stage4-step4b-record.md).
[Stage 4, item 5](specs/stage4-step5-cache-cap-series.md) — the host prompt cache capped at
1,024 MiB by one line, `cache-ram = 1024`, in llama.cpp's user config, on step 0's stand:
aircargo's first thirty questions, the swap's growth from questions 6–10 to 26–30 against
512 MiB; registered before the first request in `f214459`. Read 2026-10-30: the swap holds,
−180.25 MiB, where `19beeb1`'s rerun without the limit grew +4,452.125 MB; its
[record](evidence/stage4-step5-record.md).
[Stage 4, item 5a](specs/stage4-step5a-int8-reranker.md) — INT8 of the product's reranker
in ONNX Runtime against PyTorch, on the pools stage 2 recorded: the FP32 export's fidelity
and the speed on aircargo's first thirty, ABBA on the idle Mac by an exact sign test; the
fives and the gold on the 400 by an exact McNemar; registered before the first question
was scored in ONNX in `d9f9fd8`. Read 2026-10-30: `int8` passes, the gold holds and it reads
faster on 30 of 30, a ratio 1.751, but its five differs from PyTorch's on 307 of the 400; its
[record](evidence/stage4-step5a-record.md).
[Stage 4, item 5a's n-gram](specs/stage4-step5a-ngram-decoding.md) — n-gram decoding in the
answer model's own llama-server outside Ollama: block 0 through Ollama for the fidelity, then
base and `ngram-simple` ABBA on step 4b's thirteen at 4,096; the milliseconds a written token
by an exact sign test, and the answers' bytes; registered before the first request in
`5558ca8`. Read 2026-10-30: `NOT_EVIDENCE`, seven of the thirteen readable — the lever
closes; its [record](evidence/stage4-step5a-ngram-record.md).
[Stage 4, item 5a's live series](specs/stage4-step5a-live.md) — INT8 of the reranker in
the chat behind `81cd2ad`'s setting against PyTorch, on one commit with step 1's runner,
reader and sampler: eight runs ABBA twice, twenty pairs in four blocks, faster or slower
only by an exact sign test with every block leaning its way; registered before the first
request in `3136fb8`. Read 2026-10-30: `NOT_EVIDENCE`, stopped in its first block — the INT8
run failed step 7's look at the Mac again as `-r2`; its
[record](evidence/stage4-step5a-live-record.md).
[Stage 4, item 6](specs/stage4-item6-final-aircargo.md) — the final path's aircargo answers:
the package of `6c52b06` (K 14, window 3,584, INT8 reranker, cache cap 1,024) on the 100
questions, ten batches on one stand; M1 paired against V4's `4f48fed` with a judge bridge, M3
read one way only (its old side is 100 of 100); harm on M1 bad sends stage 5 back to Julia. Read
2026-10-31 on stand `138f3b3`: a gain, M1 good 63 → 73 of 100; its
[record](evidence/stage4-item6-final-aircargo-record.md).
[Stage 4, item 7](specs/stage4-item7-final-speed.md) — the final path's speed, measured apart
from item 6 on an idle Mac: the first 30 aircargo questions on one API, a disturbed question
asked once more after the thirtieth (at most six), and the SLO proposal from the p90. Read
2026-10-31: first word a median 89.3 s, whole answer 170.2 s, the proposal 270 s and 360 s;
its [record](evidence/stage4-item7-final-speed-record.md).
[Stage 5](specs/stage5-final-external.md) — the final path on WixQA, ConditionalQA and
MultiHop-RAG: item 6's product path on its own stand, 300 answers, M1 and M2 paired with
the published bases by the same judge, M3 at the sent point; one receipt a base, graded
while the Mac answers the next. Registered 2026-10-31.
[Stage 6, item 4](specs/stage6-throughput.md) — the
service's questions an hour and what a second client sees: a draft, registered with its tools once
the service is installed.

**Contracts the code keeps** — what the code must do, with tests behind each:

| Spec | Contract |
|---|---|
| [Corpus provenance](specs/corpus-provenance.md) | A corpus is pinned by its SHA; a number over an unidentified corpus is not evidence |
| [Embedder manifest](specs/embedder-manifest.md) | A Chroma collection records the embedder that made its vectors |
| [Chroma index persistence](specs/chroma-index-persistence.md) | A new collection persists its whole index, so a restarted process answers as the ingesting one did |
| [Request context isolation](specs/request-context-isolation.md) | Deadline and LLM budget do not leak between requests on the shared executor |

**Pre-registrations of finished or stopped measurements** — kept beside their records, which
link them and whose tests read them; stage 7 of the plan may reuse the graph rule:
[graph enablement policy](specs/graph-enablement-policy.md) and
[semantic precision metrics](specs/semantic-precision-metrics.md) (both of the stopped
`plan_03_10_26` campaign); [Chroma restart stability](specs/chroma-restart-stability.md);
pgvector [cold start](specs/pgvector-cold-start.md) and
[graph evidence](specs/pgvector-graph-evidence.md);
[entity-graph retrieval](specs/entity-graph-retrieval.md) and the
[GR-3 A/B](specs/graph-lane-ab.md); [retrieval buckets](specs/retrieval-buckets.md);
[production parity](specs/production-parity.md) (Chroma against exact search on 30 cases);
[evidence loss map](specs/evidence-loss-map.md);
[expanded cut overlay](specs/expanded-cut-overlay.md) and the
[P1b plan](specs/p1b-expanded-cut-plan.md); [label verification](specs/label-verification.md);
P2 reference samples ([Astra](specs/p2-astra-reference-sample.md),
[Opus](specs/p2-opus-reference-sample.md)); [small generators](specs/small-generator-screening.md).

## Evidence and sessions

- [`evidence/`](evidence/) — one write-up per measured slice; the register with provenance is
  [`EVIDENCE_INDEX.md`](../EVIDENCE_INDEX.md). The records themselves are in `../reports/`.
- [Latest handoff: items 6 and 7 read, stage 7 closed, stage 5 registered and running; WixQA's M1 and M2 graded, the judge resumes next session](operations/session-handoff-2026-11-01-stage5-running.md)
  — stage 5's decision table, the Mac and the laptop in a pipeline, the judge stopped by the
  laptop's memory and how to resume it. Before it:
  [stage 4 — item 5a read, the n-gram lever closed, INT8's live series `NOT_EVIDENCE`; stage 7 step 1 registered; her «да» to the package](operations/session-handoff-2026-10-30-stage4-step5a-live.md),
  [stage 4 — item 5a's blocks 2–5 passed and block 6 ran on; the audit of 2026-10-30 taken into PLAN](operations/session-handoff-2026-10-30-stage4-step5a-block6.md),
  [stage 4 — items 4 and 5 read; item 5a's INT8 registered, its block 1 passed, the series resumes at block 2](operations/session-handoff-2026-10-30-stage4-step5a-block1.md),
  [stage 4 — step 2 and step 2b read, the continuation not adopted; the probe ready to register](operations/session-handoff-2026-10-29-stage4-step2b-read.md),
  [stage 4 — step 2 running on the Mac; stage 7 and step 2b drafted](operations/session-handoff-2026-10-29-stage4-step2-running.md),
  [stage 4: step 0 read, step 1 measured, step 3 registered](operations/session-handoff-2026-10-28-stage4-step1.md),
  [V5 not adopted, the encoders' Amendment 1](operations/session-handoff-2026-10-28-v5-record.md),
  [the widget read, V5 running](operations/session-handoff-2026-10-27-v5-running.md),
  [four items under her «да», the widget running](operations/session-handoff-2026-10-26-widget-running.md),
  [stage 2b closed, stage 3's signals running](operations/session-handoff-2026-10-25-stage3-signals-running.md),
  [V4 running unattended](operations/session-handoff-2026-10-24-v4-running.md), the
  [stage 2 answers collected](operations/session-handoff-2026-10-23-stage2-collected.md), the
  [resume from 140 answers](operations/session-handoff-2026-10-22-stage2-resume.md) and the
  [pause checkpoint](operations/session-handoff-2026-10-22-stage2-paused.md), all preserved.
- [Web research of 2026-10-25](operations/research-2026-10-25/README.md) — five runs, each by
  Claude and by Codex, and two by Codex alone: our bases against published results, how to
  treat our failures, the state of RAG, a checker that reads Russian, a local generator, speed
  levers, faster retrieval models; literature, not our measurement, and a proposal for Julia's
  decision. Its [analysis](operations/research-2026-10-25/analysis.md) of 2026-10-26 reads
  every item against our own records and `PLAN.md`, and ranks them.
- [Web research of 2026-10-29](operations/research-2026-10-29/README.md) — five facts about
  Ollama 0.33.2 and its llama-server, read from the sources by Codex and partly checked: what
  `/api/ps` reports, cancellation on a closed connection, unloading, `LLAMA_ARG_CACHE_RAM`
  and the extraction output's bound; for the stage 7 probe, the host-cache cap and step 2.
- [Project audit of 2026-10-18](operations/audit_fable_18_10_26.md) (Fable 5.1) — the state
  against the plan, the status files' claims checked, findings F-1…F-10; kept in `operations/`
  because `docs/audits/` is publishable (earlier audits: `../archive/docs/audits/`).
- [Project audit of 2026-10-30](operations/audit_astra_30_10_26.md) (gpt-6-astra) — HEAD
  `83eac79` against the plan's definition of done, findings F1–F7; what `PLAN.md` took from it
  is marked «правка 30.10» there.
- [Cold read of the n-gram spec, 2026-10-30](operations/audit_opus55_30_10_26_ngram_spec.md) — one
  fresh subagent on the session's model read the spec, tool and test frozen before registration;
  verbatim, 1 blocking finding, 1 to fix, 10 minor, each applied or refuted there before it.
- [Cold read of the live series' spec, 2026-10-30](operations/audit_opus55_30_10_26_live_spec.md)
  — one fresh subagent on the session's model read the spec, reader, supervisor's copy, stand
  script and test frozen before registration; verbatim, 0 blocking, 3 should fix, 5 minor,
  each applied before registration, as its Disposition says.
- [Cold read of stage 7 step 1's spec, 2026-10-30](operations/audit_opus55_30_10_26_stage7_gate.md)
- [Cold read of stage 7 step 1's Amendment 1, the stage-4 package, 2026-10-31](operations/audit_opus55_31_10_26_stage7_amendment1.md)
  — one fresh subagent on the session's model read the spec, tool, test and S's fix frozen
  before registration; verbatim, 1 blocking, 4 should fix, 10 minor, each applied before
  registration, as its Disposition says.
- [Cold read of stage 4 items 6 and 7, 2026-10-31](operations/audit_opus55_31_10_26_stage4_items6_7.md)
  — one fresh subagent on the session's model read both specs, the tools and their test frozen
  before registration, and checked the adapters against the published artifacts; verbatim, 2
  blocking, 5 should fix, 6 minor, each applied before registration, as its Disposition says.
- [Cold read of stage 5's spec, the final path on the external bases, 2026-10-31](operations/audit_opus55_31_10_26_stage5.md)
  — one fresh subagent on the session's model read the spec, its tools and test frozen before
  registration, and ran the preflight on the real private files; 1 blocking, 4 should fix, 5
  minor, each applied before registration, as its Disposition says.
- [`operations/`](operations/) — besides the runbooks above: the
  [GR-2 entity builder preparation](operations/gr2-entity-builder-preparation.md) and the last
  session handoffs (the newest is linked from [`CURRENT_STATE.md`](../CURRENT_STATE.md)). Older
  handoffs move to `archive/docs/operations/`.
- [`a11y/`](a11y/) — the accessibility audit of the web UI.

Demo knowledge-base inputs (warranty, returns, E10–E30) are not documentation: they live in
[`../demo/docs/`](../demo/docs/) and are generated by `python -m demo.seed_docs`.

## Maintenance rules

- Update a maintained document before adding another status file; the root holds at most 9.
- Durable proof: a record in `reports/`, a test, a row in `EVIDENCE_INDEX.md`, and a write-up
  in `docs/evidence/` if it needs prose.
- Volatile status lives in `CURRENT_STATE.md`; anything superseded moves to `archive/` with its
  links rewritten, and gets a line in [`archive/README.md`](../archive/README.md).
- Relative links only; check them after any move.
- No secrets, host credentials or private runtime logs in docs.
