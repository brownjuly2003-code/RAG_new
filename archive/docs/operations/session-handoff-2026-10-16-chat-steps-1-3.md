# Session handoff — 2026-10-16 — the chat's steps 1–3 done, and Julia's production model

Session `0c7b3bb6`, 2026-10-15 21:56 UTC – 2026-10-16 about 02:40 UTC, Claude Opus 5.5 alone
(D12). The session before it: [Julia's decisions on the chat](session-handoff-2026-10-15-decisions.md).
It carried out steps 1–3 of the ROADMAP's active thread M — the chat on the production Mac — in
commits `468224b..5dcdd5a`, and closed on Julia's choice of the production model.
**Pushed at her word:** `f4818eb..147db65` (22:45, CI run 38819211605 green),
`147db65..9e1fc9e` (00:08, CI run 38827775370 green) and, at her «1. Пуш» of 02:11,
`9e1fc9e..e81f0c5` (02:41). **CI did not run on `e81f0c5`:** GitHub started no job — «The job
was not started because recent account payments have failed or your spending limit needs to
be increased» (CI run 38841686267, docs site run 38841686396, both "failure" in 3 s). That is
Julia's account, not the code: the checks CI runs passed on `5dcdd5a` on the Mac and the
laptop (Verification), and `e81f0c5` changes documents only. This note is a later local
commit, pushed with the next push.

## What matters to understand

**Where the product stands.** Production is `deproject-mac` (Intel i5, 4 cores, 8 GB, no GPU
Ollama uses). Since `468224b` the code defaults let a chat answer take up to 3,600 s and run the
reranker on the CPU, so the web chat now answers there — slowly: with qwen3:1.7b the whole answer
takes about 200 s (139–352 s), with Qwen3-4B-Instruct about 300 s (the 2026-10-14 record, then
at 1,800-s limits). The 3,600 s is a ceiling to end a hung call, not a promise; no SLO is named.

**Where the time goes.** Not the model: qwen3:1.7b reads its 2,264-token prompt in about 28 s,
writes 9 tokens/s and evaluates its answer in 29 s. The rerank — 20 candidates scored by
`BAAI/bge-reranker-v2-m3` on the CPU, 5 kept — takes a median 120 s (61–271 s) beside a loaded
model, against 27 s with no model loaded (2026-10-14). The same questions are slowest in every
run, so part of it is the candidates' length, and part is memory: the rerank slows as the model
takes RAM. Hence step 5's first lever, fewer candidates.

**The memory wall.** The 8-GB Mac holds the API (embedder and reranker, about 3 GB resident) and
qwen3:1.7b (about 2 GB) only for a while: over the thirty-question series swap grew from 764 MB to
4,117 MB, the API's resident memory fell from 3,167 MB to 900 MB and the model's from 2,057 MB to
14 MB (paged out), and question 9's vector search — 0.2 s on a quiet machine — took 147 s. The
stop rule ended the series there. Qwen3-4B-Instruct is larger (2.33 GB of weights), so its
series is likely to meet the wall sooner. Other processes on the Mac (Auto_try_v2's headless Chrome, `softwareupdated`)
were not recorded and may share the blame. This is a fact about production, not about the test.

**What the client sees now.** In the web chat, an answer routed `timeout`, a stream `error` and
an answer routed `human` carry «Передать оператору» (with «Повторить» for the first two); the
button opens the operator dialog and sends `/api/escalate` (`056844d`). The embeddable widget,
which calls `/api/ask`, now says that the answer did not come instead of «Не удалось
подключиться к сервису…», and offers the same two buttons (`4977582`). Neither opens a ticket by
itself on a timeout; `/api/ask` still opens one on `human` (`source=human_route`). The widget's
subtitle «Обычно отвечаем в течение пары секунд» stays untrue on this Mac until an SLO is named.

**Thinking.** qwen3:1.7b thought for 130–155 tokens before a one-sentence answer on the chat
path. Since `c2739af` every model call of the chat sends `think: false`; Ollama 0.33.2 accepts it
from qwen2.5:7b, which cannot think. Qwen3-4B-Instruct-2507 does not think either; that it
accepts `think: false` is unchecked (the 2026-10-14 run sent `think: null`).

**A finding left open: retrieval runs vector-only on the live stands.** Every live run, of
2026-10-14 and of this session, logged «retriever built WITHOUT BM25 index while hybrid search is
enabled — retrieval degraded to vector-only. Usually means the chunk cache is empty» and
«unstamped index: NOT_EVIDENCE». The chat's quality on the Mac is therefore that of vector
search plus the rerank, not of the hybrid retrieval the benchmarks measured. Not fixed:
rebuilding the 5,589-chunk index is forbidden; whether the chunk cache can be restored without it
is the question to answer first.

## Julia's decisions

Verbatim, times UTC.

- 2026-10-15 21:56: «Продолжи шаг 1 из ROADMAP, сначала прочитай .tmp/m1-limits/FINDINGS.md» —
  the git-ignored findings of the session she had stopped, written before any code.
- 2026-10-15 22:44, to «Пушить `468224b` и `147db65` в `origin/master`?»: «да и продолжи
  работу».
- 2026-10-16 00:08, to a report of steps 2 and 3's first half, the push question and whether the
  widget should offer the operator too: «Реши, как оптимальнее. Пуш».
- 2026-10-16 about 01:48, mid-turn: «а почему же на старом коде-то тесты работают?(((». They did
  not: on `30e97bd` the widget's three tests failed, as a red run should; the «1 failed, 35
  passed» she saw came from the new code, where one test assumed the wrong route (Lessons 2).
- 2026-10-16 02:11, to the closing report — push `9e1fc9e..5dcdd5a`?, and the session's opinion
  on step 4: the production model Qwen3-4B-Instruct-2507, then fewer rerank candidates as step
  5's first lever, and «SLO и модель решаете вы» (the session's words): «1. Пуш 2. Согласна с тобой. Нужно завершить
  сессию. Сделай все нужные шаги. Напиши, когда можно закрыть сессию».

In force from before: D12 and D11; production is `deproject-mac` (2026-10-14); the 3,600-s
ceiling and the stop rule for every live run (2026-10-15, «давай 3600 с и стоп-кран»); a
`human` answer gets the operator button, not a ticket (17:15, «показывать ту же кнопку»); and,
at the start of step 1 in the session she stopped, «1. согласна с тобой. 2. поставь» (git-ignored
`.tmp/m1-limits/FINDINGS.md`): the 2-minute real-time test stays in the regular suite, CI
included, with no marker, and Python Playwright goes on the Mac by pip into a folder of its own —
never brew, never the stand's venv.

## What was the session's choice, not hers

- The production model: the session recommended Qwen3-4B-Instruct-2507 — the judge (the
  session's model at effort max, blind to the generator) gave it 67 good answers of 100
  (qwen3:1.7b 50, qwen2.5:7b 56, qwen3:8b 66) at about 300 s an answer, against qwen3:1.7b's
  200 s. After correcting for six pairs it is ahead of qwen3:1.7b only, not told apart from
  qwen2.5:7b or qwen3:8b, and has 12 bad answers to qwen3:8b's 5
  ([evidence row](../../../EVIDENCE_INDEX.md)); qwen3:8b is larger than qwen2.5:7b, which already
  swapped on the Mac beside the API. Since 02:11 the choice is hers — the explicit decision the ROADMAP's stop-list asks of
  a model swap, for this one model. The same for fewer rerank candidates first.
- Step 1: all three limits, their `getattr` fallbacks and the raw stream's hard-coded 120 s at
  3,600 s in the code defaults, and `RAG_DEVICE` `cpu` by default.
- Step 2: the stream's `error` events get the buttons as well; she named a timeout and `human`.
- Step 3: `reasoning=False` only where a langchain binding declares the field.
- The live series' plan, named at 00:26 before the first question: the first 30 cases of
  `evaluation/curated_cases_aircargo.jsonl` in file order (the first five are those of
  2026-10-14), a fresh API for each step, forecasts 180 s for a fresh API's first question and
  120 s for the others, taken from qwen2.5:1.5b's times — the wrong basis (Lessons 3).
- The widget, on «Реши, как оптимальнее»: done as a slice of step 2 before closing, with
  `route=error` for failures other than a timeout and one new token on a 401; its subtitle left
  as it is, since any number in it is an SLO.
- Not restarting the thirty after the stop: its cause was memory, which a restart hides.

## Waiting on Julia

- The SLO; with it the widget's subtitle and what "fast enough" means for step 5.
- The self-evaluation after the answer is shown (step 5's third lever).
- Whether production on `deproject-mac` is the "real deployment" that unfreezes the ROADMAP's
  conditional track; nothing unfreezes before her word.
- Every push: hers, asked each time.
- GitHub Actions billing: no CI job starts until the account's payment or spending limit is
  fixed; then `gh run rerun 38841686267` (and 38841686396) checks `e81f0c5`.

## The next session's order

The steps, with acceptance, stand in [ROADMAP](../../../ROADMAP.md#active). First check CI on
`origin/master` (`gh run list --branch master --limit 2`): if its jobs still do not start
(billing, above), tell Julia and rely on the Mac gate and the laptop's checks meanwhile.

1. **Serve Qwen3-4B-Instruct-2507 (step 4; rule (a), then (c)).** The tag
   `qwen3:4b-instruct-2507-q4_K_M` (digest `0edcdef34593…`, 2.33 GB) is already in the Mac's
   Ollama. The default `qwen2.5:7b` stands in `config/settings.py` line 358
   (`OLLAMA_MODEL_NAME`), `.env.example` line 16, `config/providers.yml` lines 10, 11, 22, 132,
   135 and 147, `docker-compose.yml`, `deploy/helm/values.yaml`, `docs/CONFIGURATION.md`,
   `docs/QUICKSTART.md`, `README.md` and `docs-site/src/content/docs/ru/guides/quickstart.md`.
   The new tag must be listed under `models:` of the `ollama` provider in `providers.yml`:
   `llm/providers/runtime.py` (lines 52–54) raises `KeyError` for a model it does not list.
   Leave `scripts/production_parity.py` and `scripts/generator_benchmark.py` alone — they pin
   the 7B with its digest for the quality thread's records. About thirty test files name
   `qwen2.5:7b`; most use it as a fixture — grep, and change only those that pin the default.
   Leave `OLLAMA_FAST_MODEL_NAME` (`llama3.2:3b`): routing is off. Proof, red on the head before
   the change, on a real `Settings()` with no environment and a fake Ollama that records the
   `model` of each request: through `/api/ask/stream` (the web chat — the answer, the
   self-evaluation, the suggestions) and through `/api/ask` (the widget — the provider runtime
   and the graph's own model, `agent/graph.py` line 3191). Before the live run, one raw request
   to the real 4B with `think: false`, recorded in a new folder (not in a pinned capsule,
   Lessons 1); Ollama reports a thinking capability for this tag, though the model does not
   think (`docs/specs/small-generator-screening.md`, lines 66–67), and the screening ran it
   with `--no-think`.
   **The live chat 1 → 5 → 30.** How a stand is built and run: the 2026-10-14 log's section
   [The stand — how to run it](session-handoff-2026-10-14-chat-on-mac.md#the-stand--how-to-run-it)
   (the workspace is a `git archive` of the commit). Copy the tools of
   `reports/chat-live-qwen3/9e1fc9e/tools/` into the new record's own `tools/` and change what
   names qwen3:1.7b or forecasts its times: `live_supervisor.py` line 62 `DEFAULT_MODEL` to the
   4B tag; `series.sh` line 25 without `MODEL=…` — that argument sets `OLLAMA_MODEL_NAME` and a
   patched `providers.yml`, an override that would not prove the new default; its `CAP`;
   `make_stand.py` lines 30 and 163 (the model and the forecasts; it builds from the
   `33d4b42` tools). Then check in the run's recorded `settings` that the served
   `ollama_model_name` is the 4B and no `OLLAMA_MODEL_NAME` or `PROVIDER_REGISTRY_PATH` is set.
   Name every question and its forecast before the first launch, from the 4B's own record
   (`reports/chat-live-small/33d4b42/runs.json`, five questions only): a fresh API's first
   question 343 s (258 s in the five-question step, the same question), the others 297–322 s —
   so 343 s for each step's first question and 300 s for every other one, questions 6–30
   included, and the stop at about 1,030 s and 900 s. The three steps take about 3 h if memory
   holds. The supervisor already samples swap and resident memory per step (`runs.json`,
   `memory`); add the values at each question, and the largest processes by memory (its
   sampler keeps the five busiest by CPU). A stop on the 3× rule is a measured result: record
   it and investigate, as this session did.
2. **Fewer rerank candidates (step 5's first lever; rule (c)).** `RAG_RETRIEVAL_TOP_K`
   (`config/settings.py` line 494, 20 candidates; `RAG_RERANK_TOP_K` keeps 5). Register the
   values, the quality measure and the threshold before the first run; time in the live chat,
   quality on the curated cases with the repository's existing retrieval harness. Not another
   reranker (the stop-list).
3. **The BM25 finding** (above): read why the stand's chunk cache is empty and whether it can be
   restored without rebuilding the index; a fix that changes retrieval is a slice of its own,
   with the before and after measured.

**The gate** for any change: `.tmp/mf-mac/sync.py`, then `.tmp/mf-mac/remote.py --site pytest
<tests> -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`
(both with the laptop's `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8`,
and `MSYS_NO_PATHCONV=1`). Browser
tests over ssh in `/Users/julia/RAG_new_mf_gate` with
`PYTHONPATH=/Users/julia/RAG_new_mf_gate_site:/Users/julia/RAG_new_playwright_site` and
`/Users/julia/RAG_new_gr4_venv/bin/python -m pytest … -rs`. A red run on an older commit:
`.tmp/ask100-split/sync_commit.py <rev>`, then copy the new test in, run it, remove it. Before
asking for a push: the whole unit suite on the Mac (about 9 min, 5,806 passed and 123 skipped on
`5dcdd5a`), CI's two mypy commands, bandit, pip-audit and DEP-01 (the docs site's npm audit)
as `.github/workflows/ci.yml` gives them.

## Do not

- Push, call a hosted model or another reranker, or move the self-evaluation after the answer
  without Julia's word. The model is hers and named: Qwen3-4B-Instruct-2507, no other.
- Report a run without its served configuration, or a skipped browser test as a pass; start a
  live series without every question's forecast named.
- Run tests on the laptop; read, print or copy `.ask100-runtime/env.json`; kill processes you
  did not start on the Mac (Auto_try_v2, another project's jobs; PostgreSQL; `ollama serve`);
  install anything there with brew; rebuild the 5,589-chunk index; touch
  `demo/phase-e-raw.webm` or `reports/ask100/`.
- Add a file to a published record's folder: tests pin their file sets.

## Lessons

1. **A published record's folder is closed.** The think probe went into
   `reports/chat-live-small/33d4b42/tools/`, whose test pins every file; the suite failed, and the
   probe moved to `reports/think-probe/2026-10-15/` (`e924868`).
2. **A fake model behind `/api/ask` routes `human`.** The graph's relevance, grounding and judge
   checks send a fake answer to `human`, and `/api/ask` then opens a ticket itself — unlike the
   stream, where a self-evaluation of 85 gives `auto`. The widget's test assumed `auto` for the
   retried answer and failed on the new code; it now reads the route and counts tickets with
   `source == "manual"`.
3. **Forecast from the same model, on the same machine, per question.** The plan took
   qwen2.5:1.5b's times for qwen3:1.7b: right for a fresh API's first question (185, 177, 163 s
   against 180), wrong for all 11 others (median 215 s against 120), because the rerank varies
   61–271 s by question and grows with memory. The 4B's own record exists — use it.
4. **One watcher per series, with its own state.** A second Monitor over the same event file,
   sharing the first's seen-file after it expired, swallowed lines the session never saw. The
   record comes from the stand's files, not from the watcher, so only the session's view was lost.
5. **Memory is part of the measurement on an 8-GB machine.** A long series is not N repeats of
   one question: swap grows, and the last questions measure paging. Record memory beside time.

## Glossary

- **Thread M / steps 1–5** — the ROADMAP's active thread, the chat on the production Mac.
- **Ceiling** — the 3,600-s limit (request, Ollama call, stream): ends a hung call; not an SLO.
- **Stop rule (стоп-кран)** — each question's forecast named before the launch; the supervisor
  stops the series once a question runs past 3× it; the session investigates at once.
- **Stand** — a `git archive` of one commit on the Mac with its record folder
  (`/Users/julia/RAG_new_chat_9e1fc9e`), run by the shared
  `/Users/julia/RAG_Support_Assistant/.venv/bin/python`; **series** — 1, then 5, then 30
  questions, each step on a fresh API; **supervisor** — the detached process that runs a step and enforces the
  stop rule.
- **Route** — `auto` (answered), `human` (a badge in the chat, a ticket on `/api/ask`),
  `timeout`, `error`.
- **Rerank candidates** — `RAG_RETRIEVAL_TOP_K` (20) chunks retrieved and scored by the reranker,
  of which `RAG_RERANK_TOP_K` (5) reach the prompt.
- **Chat and widget** — the web chat calls `/api/ask/stream`; the embeddable widget calls
  `/api/ask`.
- **NOT_EVIDENCE** — a run or index without provenance; never a pass.
- **Stop-list** — the ROADMAP's frozen row of changes that need Julia's explicit decision: a
  model swap, another reranker, a hosted model and others.
- **The judge** — the session's model at effort max grading answers blind to the generator
  (good / partial_ok / bad), D11 and D12.

## Log

All times UTC.

- 2026-10-15 21:56 her message; the findings read; step 1 written: `468224b` at 22:23 (the
  real-time test: a fake model silent 65 s, then streaming to 129 s — the answer arrives in
  129.3 s on the Mac, against an `httpx.ReadTimeout` at 30.2 s on `f4818eb`), its record
  `147db65` at 22:27. 22:44 her «да»; push at 22:45; CI green at 23:00.
- Step 2: `056844d` at 23:26 (red on `147db65`, 4 failed; green with `-rs`), `8464732` at 23:29.
- Step 3's first half: `c2739af` at 23:51; the probe put in a pinned folder failed that folder's
  test (Lessons 1), fixed by `e924868`; `9e1fc9e` at 00:06. 00:08 her «Реши, как оптимальнее.
  Пуш»; push at 00:08; CI green at 00:24.
- 00:26 the series plan named and `30e97bd` committed; the series ran 00:26–01:28: one question
  185 s, five a median 211 s, the thirty stopped at question 9 (Lessons 3–5).
- Meanwhile the widget: red on `30e97bd` (3 failed: no button), then green 3/3 after the route
  fix (Lessons 2), screenshots checked; `4977582` at 01:53. About 01:48 her question, answered.
- `5dcdd5a` at 02:05: the record `reports/chat-live-qwen3/9e1fc9e/` (`runs.json`, 48,815 bytes,
  sha256 `31045ef9…c8a8`), its test, two evidence rows, ROADMAP, CURRENT_STATE, AGENT_STATE and
  BACKLOG. Before the question to her: the checks under Verification.
- 02:11 her answer. Then her decision in ROADMAP (step 4, step 5, row M), CURRENT_STATE,
  AGENT_STATE, BACKLOG and the previous log; this log; a cold read of it by a subagent on the
  session's model; the docs tests on the Mac; the commit `e81f0c5`; the push at 02:41; CI
  started no job (billing, above).

## Verification

- On `5dcdd5a`'s tree, on the Mac: the whole unit suite, 5,806 passed, 123 skipped, 0 failed
  (519 s); the docs and record tests, 43 passed. On the laptop: CI's two mypy commands, no
  issues; `ruff check .` clean. pip-audit: no known vulnerabilities, 5 ignored as CI ignores
  them; DEP-01 passed; bandit: no findings.
- The widget's test with `-rs` on the Mac: 3 passed, no skip (37 s); red on `30e97bd`.
- The live record's served configuration — code SHA, model digest `8f68893c…30e7`, Ollama
  0.33.2, index digest `b7cdcac1…4b57`, the API's settings — is in its `runs.json`, pinned by
  `tests/test_chat_live_qwen3_artifact.py`.
- This log's tree, on the Mac: the three docs tests, the three chat-live record tests and the 18
  other test files that read the root documents or scan the docs folders: 489 passed, 10 skipped
  (nine `autopilot.ps1` tests, which need Windows PowerShell 5.1, and the static JS check, which
  needs `node` on the gate's path). Line caps:
  CURRENT_STATE 140 of 150, AGENT_STATE 119 of 120, BACKLOG 59 of 60.
- The cold read of this log by a subagent on the session's model, before the commit: one high
  finding (the live tools still name qwen3:1.7b, and `MODEL=` is an override that would not
  prove the default), several medium (how to build a stand; `/api/ask` and `providers.yml`'s
  `models:`; the scripts that pin the 7B; forecasts for questions 6–30; CURRENT_STATE and the
  stop-list against step 4; her words told apart from the session's) and low ones — checked
  against the files and applied. Not applied: that `f4818eb..147db65` should read
  `9698e54..147db65` — CI ran on a push of `f4818eb` at 17:49, so it was already on
  `origin`; and the 2026-10-15 evidence row's "stays suspended", true on its date.
