# Session handoff — 2026-10-17 — one plan, fixes first, the documents tidied

Session `ef520894` (continued after two context compactions), 2026-10-17, Claude Opus 5.5
alone (D12). The session before it:
[the production model served](session-handoff-2026-10-16-production-model-live.md). This
session wrote and got accepted the one plan of the project, [`PLAN.md`](../../PLAN.md), and then,
at Julia's request, tidied the documentation and the repository root. Julia ended it herself:
«Эта сессия тяжелая, стоит продолжить в следующей».

**Pushed:** `b351d29..3e52a02` at her word («пуш», 2026-10-17), after the whole unit suite on
the Mac: 5,820 passed, 123 skipped. **Not pushed:** the tidy-up — committed locally with this
log; a push waits for her word.

## What matters to understand

**There is now one plan, and it is accepted.** Until this session the order of work lived in
three places: `plan_06_09_26.md` (horizon 18.10), the quality thread's `plan_03_10_26.md`
(320 thousand characters), and the ROADMAP's thread M (the chat on the production Mac), which
no plan described. [`PLAN.md`](../../PLAN.md) (in Russian) replaces all three: why it was
rewritten (§1), what "done" means (§2), where the project is (§3), one measuring method (§4),
eight stages with Mac hours (§5), phase B (§6), what became of every earlier stream (§7),
Julia's decisions and what is still hers (§8), the frozen list (§9), risks (§10), rules (§11),
a glossary. Julia accepted it on 2026-10-17 («1. принять»).

**The product is the web chat, and no quality number exists for it yet.** Every answer-quality
number so far (4B: 67 good / 21 partial / 12 bad of 100) was measured on phase-C contexts, not
on the chat's own retrieval; the lexical precision ruler (0.5067, gate 0.63) does not track
meaning (P2). The first quality number of the product as a customer gets it is stage 2.

**Fixes come before any measurement** (Julia: «Нужно записать в план устранение косяков,
которые ты нашел. Думаю, это стоит поставить в приоритет»). Reading the ingestion and prompt
code for her questions about chunking found defects that make the system less universal than
it claims. Measuring first would measure a version about to be thrown away; so stage 1 fixes
them, and stage 2 measures all four corpora on the fixed code. The 70-question chat run the
previous plan had queued is cancelled; all 100 aircargo answers are taken anew in stage 2.

**The defects, all found by reading code, none measured yet** (detail in `PLAN.md` §5, stage 1):

| Defect | Where | Effect |
|---|---|---|
| DOCX keeps only paragraphs | `ingestion/loader.py` `_read_docx` | headings and tables are lost; section chunking cannot work |
| HTML text joined with spaces | `_read_html` | one flat line, no sections |
| PDF has no headings | `_read_pdf` | page text only |
| Chunk header is a Russian phrase | written by `add_contextual_headers` (`vectordb/_base_manager.py`, with its Russian LLM-header prompt; wrapper in `vectordb/manager.py`), `ingestion/pipeline.py` and `scripts/external_base.py`; parsed by its `[Контекст:` prefix in `_strip_contextual_header` (used by `_expand_parents`), `agent/context_window.py`, `agent/doc_grade.py`, `evaluation/external_gold.py` (M3), `scripts/production_baseline.py`, `scripts/ab_context_precision.py`; at least six test files pin the prefix | «[Контекст: Из документа …, раздел: …]» on English corpora too. Change the format at one site only and expansion, document grading and M3 break silently: change all at once |
| Header cut at 200 characters from the wrong end | the same writers, each with its own `[:200]` | the nearest heading is lost in 8–34 % of external chunks; the document title appears twice |
| Table continuation has no header row | `structural_split` | a continued table chunk has values without column names |
| Overlap repeated on expansion | `_expand_parents` | neighbours glued with their 200-character overlap; the prompt repeats text |
| Prompts are Russian and set no answer language | `agent/prompts.py` (resolved through `agent/prompt_registry.py`); `_format_context_block` labels the context in Russian («[Документ N | source=…]», «Контекст отсутствует…») | Julia: «логично отвечать на языке вопроса» |
| External tenants' path unproven | the chat path | not yet shown to run BM25 + BGE-M3, rerank and expansion as aircargo does |
| Graph patterns and entity prompt are Russian | `ingestion/structure_graph.py`, `ingestion/entity_extraction.py` | stage 7, not stage 1 |

Every measurement so far was the best case: aircargo is markdown, and the external bases were
converted to markdown by the connection's converter (`evaluation/external_convert.py`, e.g.
`html_blocks` for WixQA, run by `python -m scripts.external_base convert`), bypassing the
product's loaders.

**Indexes are rebuilt as a new generation beside the old** (Julia: «2. согласна»). The
indexes of the three external bases and the slice-2.5 aircargo index were built by the
measurement path — `scripts/production_embeddings.py`, then `scripts/production_index.py`,
each into a directory of its own ([how](../evidence/external-bases-connection.md), section
«How it was run»). A new generation is built the same way into a new directory; the old one
stays, so earlier numbers stay reproducible and rollback is one step. A stand serves the
directory of its `vectordb_chroma_dir` setting, and a run's record names it. The API's own
path — `build_vector_store_with_publication` / `rollback_vector_store` (`vectordb/manager.py`)
— is how production will update an index; that it yields the same chunks is for the audit.
aircargo ≈ 1 h of Mac time, the three external bases ≈ 10 h. Never rebuild in place.

## How the system cuts documents — the answer Julia asked for

Asked «чанки по разделам — это как? а если раздел очень большой? … overlap?»:

- `structural_split` cuts markdown by its headings h1–h4 (MarkdownHeaderTextSplitter); each
  chunk keeps its heading path in metadata.
- A section over 800 characters is cut inside itself by RecursiveCharacterTextSplitter (800
  characters, 200 overlap) — never across a section boundary, so overlap exists only inside a
  long section.
- Each chunk gets the contextual header (document, heading path, page), capped at 200
  characters, which is embedded with it.
- At answer time parent expansion adds up to two neighbouring chunks of the same document on
  each side, up to 3,600 characters — this is where the overlap repeats (the defect above).

Her other remembered item — «в метаданные был план вписать инфу про чанки и также в сами
чанки вписать данные про док и раздел» — is done: the metadata holds h1–h4 and the page, and
the header writes document and section into the chunk text.

## Julia's decisions this session

All are in `PLAN.md` §8.1.

- «Вариант B» — the 300 answers on the three external bases move from stage 5 into stage 2,
  on the current path; stage 5 re-measures them only if stage 4 changes the answer path.
- «поставить в приоритет» — the defects found are stage 1, before any measurement.
- «логично отвечать на языке вопроса» — the answer's language follows the question.
- «1. принять 2. согласна 3. пуш» — the plan accepted (with §8.2 and the stop of the
  `plan_03_10_26` campaign); the aircargo index rebuilt as a new generation; the plan pushed.
- «Давай максимально доку проекта приведем в порядок и корень. Все, что не нужно — в архив.
  Нужно, чтобы все было прозрачно и понятно» — the tidy-up below.

## Log

1. `cbbfe8d`, `eb5a0ae` — the handover-signal plan ([spec](../specs/handover-signal.md))
   tied into the project plan; B.4 of the 06.09 plan (double-annotated routes) replaced by it,
   since D11 rules out a second annotator.
2. `08c54fd` — `PLAN.md` written; `plan_06_09_26.md` to `archive/docs/plans/`.
3. `87ad3fb` — «Вариант B».
4. `36548f8` — stage 2 got a preparation part: the code made ready for foreign corpora.
5. `3e52a02` — the preparation became stage 1 and moved ahead of everything (her «в
   приоритет»); the known defects listed; the index rebuild as a new generation. Pushed with
   1–4.
6. The tidy-up (local commit with this log):
   - 83 documents moved into `archive/` with `git mv`, every relative link and path mention
     rewritten by a script — in documents, and in comments and docstrings of code, scripts and
     tests (`api/routers/conversation.py`, `config/settings.py`, `vectordb/`, `scripts/`,
     `tests/`; no executable line changed); the moves are summed up by folder in
     [`archive/README.md`](../../archive/README.md), file by file in
     `git show --stat -M` of the tidy-up commit;
   - `CURRENT_STATE.md`, `ROADMAP.md`, `AGENT_STATE.md`, `BACKLOG.md` rewritten short; their
     earlier versions copied to `archive/docs/state/*-through-2026-10-17.md`, links re-pointed;
   - `docs/README.md` rewritten as a map with one line per document;
   - `PLAN.md` records the acceptance; `README.md` and `CLAUDE.md` point to the map;
   - `.pre-commit-config.yaml`: the `docs/audits/audit_opus_*` exclude is covered by
     `archive/` now; `tests/test_precommit_config.py` follows;
   - `config/pricing_snapshot.json`: the `verified_by` path follows the audit into `archive/`.

## The tidy-up: what moved, what stayed, why

**Moved to `archive/`:** all of `docs/audits/`; from `docs/operations/` the dated logs of
2026-05…08, old runbooks and kickoffs (the direct GLM-5.3 runbook among them), and the session
handoffs up to 2026-10-16; from `docs/specs/` the three superseded plans, the six research
reports and seven finished-measurement plans; `docs/CHANGELOG.md`, `docs/AUTOPILOT.md`,
`docs/local-gate.md`, `docs/windows-test-workflow.md`; `docs/architecture/rag-new-architecture.md`
and `migration-plan.md` (the inherited system and the move away from it); `notebooks/`.

**Stayed, on purpose:**

- all of `docs/evidence/` — every capsule has a row in `EVIDENCE_INDEX.md`, many are read by
  tests;
- 21 specs — one in use (handover signal), four contracts the code keeps, the rest
  pre-registrations of finished measurements that their records and tests link; the map
  sorts them into these three groups;
- `docs/operations/`: the five runbooks, the GR-2 builder preparation (linked by evidence),
  the handoff of 2026-10-16 and this one;
- all nine root files: `AGENT_STATE.md` and `BACKLOG.md` are read by `scripts/autopilot.ps1`
  and tests; `DEPRECATIONS.md` is synced to the docs site.

**Not rewritten:** `reports/` (published records) and `scripts/p1b_expanded_cut.py`, whose
`Q1_SOURCE` is a provenance value written into records — both still name some documents by
their path before the move. Old fingerprints in `.gitleaksignore` keep their old paths: they
name a commit, and the moved file is a pure rename.

**Side effect:** the docs site (`docs-site/scripts/sync-docs.mjs`) publishes everything under
`docs/` except a kitchen list; what moved out — the audits, `CHANGELOG.md`, the moved specs and
the two architecture pages — is no longer published. Publication is Julia's
gate (stage 8); nothing is deployed.

**Link check:** a script compared every relative link in every markdown file now and at
`3e52a02`. Live documents: no broken link (the one to this file resolves once it is written).
Archive: no link broken by the move; the ≈ 225 broken links there were broken before it (audits
citing `file#L123` from the wrong directory and the like).

## State at the end

- `HEAD` — the local tidy-up commit on top of `3e52a02` (`origin/master`).
- Untracked and not the session's to touch: `demo/phase-e-raw.webm`, `reports/ask100/`.
- The Mac idle: no stand, no run. `ollama serve` and other projects' jobs left as found.
- CI starts no job (account billing, since `e81f0c5`): before a push the whole suite runs on
  the Mac, plus mypy, bandit and pip-audit.

## Next actions — stage 1

In this order; each fix is a commit with a unit test, and a change to the chat path also gets
an E2E test on one question per tenant (rule (a)). `PLAN.md` §5, stage 1, is the authority;
this list adds the code locations.

0. **The stage's spec first** (`PLAN.md` §11): `docs/specs/<name>.md`, at most two pages,
   written before the first request — what is audited and how, the forecast of Mac hours, the
   stop rule. The audit list with the outcome of each item is the stage's acceptance artefact;
   keep it in that spec.
1. **Audit, written so it can be repeated:** in the product code of loading and the chat path
   (loaders, chunking, headers, index, retrieval, prompts, API) list Cyrillic strings, regular
   expressions and word lists, domain names, the parsing of each file format; then one question
   per tenant through `/api/ask/stream` with its trace read (rule of 2026-10-13: one question
   first). Each finding is fixed universally — no hand-made dictionaries — or recorded as a
   limitation with a reason.
2. **Loaders** (`ingestion/loader.py`): DOCX — walk the body in order, headings by style to
   markdown `#`, tables to markdown tables; HTML — h1–h4 to markdown headings, block elements
   to paragraphs, tables kept; PDF — headings only as far as they can be recovered without a
   per-corpus rule, the rest a recorded limitation. Check: WixQA's raw HTML through the
   product's loader against the connection's conversion, by coverage of the reference evidence.
3. **Header:** a format with no natural-language words (document › section › subsection), cut
   from the outer end, the title not repeated — at every writer and parser in the table above,
   at once.
4. **Tables:** first count the continued table chunks; then the continuation repeats the
   header row (`structural_split`).
5. **Expansion:** neighbours joined without their overlap (`_expand_parents`).
6. **Prompts:** answer, self-evaluation and suggestions follow the question's language, by an
   instruction, no dictionaries; the context labels of `_format_context_block` too; check what
   they produce on an English corpus.
7. **External tenants:** prove on each that the chat runs BM25 + BGE-M3, rerank and expansion
   as on aircargo, after an API restart too.
8. **Indexes:** a new generation of the four corpora on the fixed code (≈ 11 h Mac), the old
   directories kept.
9. **Tools for stage 2:** a chat-answer runner for any tenant; the judge's adapter for chat
   answers (each answer brings its documents) with an English prompt, its own stability check
   and the [N] citation check; M2 against reference answers; the sample of ≈ 100 questions per
   external base from the open parts, by cluster, recorded before the first request; the
   signal tool (signal stage 1.0 of the [handover plan](../specs/handover-signal.md)).

Then stage 2 (`PLAN.md` §5). Julia's open items by stage are `PLAN.md` §8.3.

### Where things are

| What | Where |
|---|---|
| aircargo | tenant `aircargo`, collection `rag_docs_aircargo`, 5,589 chunks; the corpus on the Mac at `/Users/julia/RAG_Support_Assistant/data/uploads/aircargo` (201 files) |
| External bases | tenants `ext_conditionalqa`, `ext_wixqa`, `ext_multihoprag`; collections `rag_docs_ext_<base>`; receipts in [`reports/external/36f1167/connection.json`](../../reports/external/36f1167/connection.json); open and locked parts in `evaluation/external_parts.json` |
| E2E tests to extend | `tests/test_ask_stream_thinking_off_e2e.py`, `test_ask_stream_time_limits_e2e.py`, `test_production_model_default_e2e.py`, `test_ask_window_e2e.py`; browser: `test_chat_operator_offer_playwright.py`, `test_widget_operator_offer_playwright.py` |
| The last stand's tools | `reports/chat-live-4b/19beeb1/tools/` — `make_stand.py`, `launch.py`, `live_supervisor.py` (drops the model keys of the stand's `env.json`, so the code defaults choose the model), `live_runner.py`, `export.py`. A published record: **copy** them into the new record's folder, never edit them in place |

### How to test on the Mac

The scripts live in the git-ignored `.tmp/mf-mac/` on the laptop.

- `python D:/RAG_new/.tmp/mf-mac/sync.py` ships the working tree, uncommitted files included,
  to the gate checkout `/Users/julia/RAG_new_mf_gate` and prints `MAC SYNC OK`.
- `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <files> -q -p no:cacheprovider
  --tb=short` runs tests there with the gr4 venv plus the package overlay
  `/Users/julia/RAG_new_mf_gate_site`. The whole suite takes ≈ 8.5 min: run it in the
  background.
- Browser tests skip through `remote.py`; they run over ssh in the gate checkout with
  `PYTHONPATH=/Users/julia/RAG_new_mf_gate_site:/Users/julia/RAG_new_playwright_site`.
- Models and embeddings use another interpreter, `/Users/julia/RAG_Support_Assistant/.venv/bin/python`
  (sentence-transformers, langchain-chroma; no pytest).
- An idle Mac: no `llama-server`, a 5-minute load average below 2. No tests during a live run.

## Lessons

- **Read the code before planning a measurement.** The defects came from reading the loaders
  and the header code to answer her question, not from a metric; a plan of measurements on top
  of them would have measured a version due for replacement.
- **Name the path a number was measured on.** "4B: 67 good" is on phase-C contexts; quoting it
  as the chat's quality was the trap the previous plans fell into.
- **Moving documents is code work.** Tests pin paths (`test_precommit_config.py` still-fixed
  list), published records name paths, and a regex rewrite can turn a "still fixed" path into
  an excluded one. A script that moves, rewrites links against the old location, skips
  `reports/` and frozen provenance strings, prints what is left, and a link check against HEAD
  made 83 moves safe.
- **Snapshots need their links re-pointed.** A root file copied into `archive/docs/state/`
  keeps root-relative links until rewritten; anchors into the old root files point at the
  snapshot's own sibling copies.
- **A push needs the whole suite on the Mac** while CI cannot run; focused tests have missed
  CI failures before.

## Glossary

- **Chat path** — `/api/ask/stream`: retrieval, answer, self-evaluation, suggested questions;
  what a customer uses. **Widget path** — `/api/ask`: the agent graph with rewriting, grading
  and claim checks.
- **Phase-C contexts** — the cached retrieval contexts of the generator benchmark; not the
  chat's retrieval.
- **Stage** — a step of `PLAN.md` §5 (0–8). **Slice rule** — a slice counts only with (a) an
  E2E test of changed behaviour, (b) more real labelled cases, or (c) a published number with
  provenance.
- **M1–M5** — the plan's metrics: answer verdict (with citation check), correctness against a
  reference, retrieval, handover to a person, time and memory.
- **D11 / D12** — Julia's rules: no person in the quality process; the session does all the
  work, no other model in any role.
- **Q2b** (`PLAN.md` writes «Q2б», with a Cyrillic б — grep both) — the 100 real
  shipment-bound requests phase B needs from Julia.
- **Four different "B"s:** phase B (real labelled cases, blocked on Q2b); mode B (Julia,
  2026-09-10: one thread, honest numbers, publication); «Вариант B» (2026-10-17: external
  answers in stage 2); outcome B of the handover plan (only the claim check or the grader is
  worth wiring).
- **R1, R2** — suspected widget defects in the handover plan: R1, under `RAG_ENV=production`
  every widget answer goes to a person; R2, an answer with no factual claims counts as
  verified. Confirmed or refuted in stage 3.
- **Tenant** — one corpus with its own collection and index; a request names it
  (`tenant_id`). **Stand** — the API of one commit brought up on the Mac for a measurement,
  with the record's tools; production has no service yet (stage 6).
- **Trace** — the per-request record of retrieval, prompt, timings and route that the API
  writes; read through `/api/admin/traces/{trace_id}` ([runbook](../runbook.md)) or the
  record's export.
- **`plan.json`** — a measurement's pre-registration in its record folder: the questions,
  the forecast, the stop rule, committed before the first request.
- **DEP-01** — the docs site's npm-audit posture with dated exceptions by advisory id
  (ADR 0009); part of the pre-push checks.
- **New generation** — a new Chroma collection published beside the old, with rollback.
- **Contextual header** — the line prepended to each chunk and embedded with it.
- **Parent expansion** — neighbouring chunks of the same document added at answer time.
- **Open / locked parts** — the split of each external base's questions; locked parts are
  for confirmation only (`PLAN.md` §4.2).
- **NO-SHIP / `NOT_EVIDENCE`** — a measured mechanism not turned on; a run that did not happen.
