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
runs ABBA, the rerank's seconds paired a question at a time; registered before the first request.
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
- [Latest handoff: stage 4 — step 0 read, step 1 measured, step 3 registered](operations/session-handoff-2026-10-28-stage4-step1.md)
  — step 0's record, step 1's two runs and its reading (contention yes, net faster on a 2–2
  split), step 3's timing registered, stage 6 prepared. Before it:
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
- [Project audit of 2026-10-18](operations/audit_fable_18_10_26.md) (Fable 5.1) — the state
  against the plan, the status files' claims checked, findings F-1…F-10; kept in `operations/`
  because `docs/audits/` is publishable (earlier audits: `../archive/docs/audits/`).
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
