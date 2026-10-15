# Session handoff — 2026-10-14 — generators below 7B on the production Mac

Session `ef96201d`, 2026-10-14 13:15–20:50 and 2026-10-15 08:40–10:35 UTC, Claude Opus 5.5
alone (D12). Commits: `86df582` (screening registered), `cfb78ee` (its amendment),
`f470f03` (live chat record), `40ad172` (screening record without the verdicts, these
documents), `a7bf232` (verification); on 2026-10-15 `384f7df` (the verdicts), `83a2158`,
`9eb93c9`, `d5328d3`, `af6b905` (fixes of the red CI on `a7bf232`) and the commit with this
text. **Pushed on 2026-10-15 at Julia's word:** `f7416ca..a7bf232`, the 47 commits of
2026-10-04…10-14; later commits are local. The session before, measuring the web chat
with qwen2.5:7b: [session log](session-handoff-2026-10-14-chat-on-mac.md). Continued, the
judge on 100 cases: [session log](session-handoff-2026-10-15-judge-100.md).

## What matters to understand

**Julia's message.** After the 7B record (no answer under the code-default limits; ~5.5 min
to the first word and ~8 min to the whole answer with the limits raised) she wrote:
«Модель для прода. Давай подвесим вопрос. И посмотрим, как на тестах результаты на модели
< 7B. Что думаешь?» The session proposed a plan (screen the Apache-2.0 Qwen generators
below 7B against C.1a and C.1b on the C.1 contract, graded by the one judge, then time the
chat with them); she answered «согласна». On 2026-10-14 at 20:46 the session asked:
«1. Дозапустить судью? Осталось 66 запросов: примерно час и ~$7 в API-эквиваленте, идёт по
твоей подписке. …», «2. Push 47 коммитов в `origin/master`?» and «3. Модель для прода
остаётся подвешенной, как ты решила. Моё мнение: из малых лучше всех выглядит
Qwen3-4B-Instruct … Ответ за секунды на этом Mac одним выбором модели не получить: нужно
менять сам пайплайн (реранк, самооценку после ответа). Альтернативные реранкеры стоят в
стоп-листе, так что это тоже твоё решение.» On 2026-10-15 she wrote «1. Да 2. Да. 3. Давай
решим это позже»: the judge finished, the 47 commits are pushed, and the model and the
pipeline levers of question 3 wait. The 100-case extension was never asked: it follows
from the judge's classes, which came later.

**Two measurements, two questions.**

1. *The screening* ([plan](../specs/small-generator-screening.md), record
   `reports/generator-screen/86df582/`): which small model writes good answers from the
   contexts it is given. The C.1 benchmark (glossary), not the chat path; quality from the
   one judge on 30 cases shared by all five generators, deterministic checks on all 100
   answers, speed from Ollama's own timing of each generation.
2. *The live chat* (record `reports/chat-live-small/33d4b42/`): how long a user waits on
   this Mac. The 7B record's stand serving another model through `MODEL=` of its
   supervisor — the real API at `33d4b42`, the 5,589-chunk index, the questions sent
   through `/api/ask/stream` as the web chat sends them. Not under `reports/chat-live/`: the
   7B record's test finds its evidence row by the substring `reports/chat-live/33d4b42`.

A model can do well in (1) and badly in (2): the chat prompt is not the benchmark prompt.
qwen2.5:1.5b never answered with a bare reference in the screening, and did so in the chat
("[4]", routed `auto`).

**The screening** — the one judge on 30 shared cases; deterministic checks of all 100 answers:

| | qwen2.5-1.5b | qwen3-1.7b | qwen3-4b-instruct | qwen2.5-7b (C.1a) | qwen3-8b (C.1b) |
|---|---|---|---|---|---|
| judge: good / partial_ok / bad of 30 | 16 / 5 / 9 | 20 / 5 / 5 | 23 / 5 / 2 | 20 / 6 / 4 | 21 / 8 / 1 |
| judge: supported claims | 0.86 | 0.92 | 0.99 | 0.95 | 0.99 |
| keyword recall, 100 answers | 0.645 | 0.575 | 0.730 | 0.705 | 0.705 |
| NLI faithfulness (not ranked on) | 0.870 | 0.907 | 0.919 | 0.892 | 0.991 |
| answers without Cyrillic | 0 | 0 | 1 | 0 | 8 |
| median answer, characters | 171 | 167 | 165.5 | 236.5 | 153.5 |
| generation per case, median | 13.9 s | 15.8 s | 36.7 s | not comparable | not comparable |
| reading / writing, tokens/s | 126.5 / 20.4 | 108.9 / 14.0 | 45.3 / 6.7 | — | — |

The contexts hold 0.905 of the expected keywords, which bounds the recall. The C.1a and C.1b
latencies include two self-grading requests, and their reports carry no Ollama timings
(`ollama_timing` is new) — hence the dashes. The answers without Cyrillic are English
lists of field or document names.

**What the judge says.** It agreed with itself: the same class on 15 of 15 retests, the
same `context_has_answer` for all five answers in 30 of 30 cases. Thirty cases leave gaps
of five good answers or fewer unresolved (at 25 of 30 the 95 % Wilson interval is about
0.66–0.93). The only wider gap, qwen2.5-1.5b's 16 against Qwen3-4B-Instruct's 23, is not
settled either: the intervals overlap (0.36–0.70 and 0.59–0.88), and of the cases where
only one of the two is good, 1 goes to the 1.5B and 8 to the 4B — exact p ≈ 0.04 before
correcting for the ten pairs. The 1.5B has the most bad answers (9), and 8 of its 30 hold
an unsupported claim. Qwen3-4B-Instruct has the most good answers of the small generators
and is within five of C.1a and C.1b, not told apart from them, so the plan's reading calls
for the judge on all 100 cases of the generators concerned, under a new plan and on
Julia's word (State, below). qwen3-1.7b, last on keyword recall (0.575), has as many good
answers as C.1a (20); whether the two measures really part on it, 30 cases cannot say. All
165 verdicts were valid at the first attempt (their cost: State).

**The live chat** — run S3, the five B2 questions at the floor limits (1800 s) with
`RAG_DEVICE=cpu`, unless the row says otherwise:

| | qwen2.5:1.5b | Qwen3-4B-Instruct-2507 | qwen2.5:7b (7B record) |
|---|---|---|---|
| code-default limits (S1; 7B: B1) | no answer: warm-up timeout after 58 s, then `timeout` at 33 s | no answer: warm-up timeout after 231 s, then a stream with no result (the 503 below) | no answer: `timeout` |
| first token, median (range) | 77 s (64–143) | 198 s (175–224) | 325 s (285–423) |
| whole answer, median (range) | 100 s (92–168) | 297 s (258–322) | 486 s (429–614) |
| one question on a fresh API (S2): first token / whole answer | 147 / 170 s | 258 / 343 s | — |
| retrieval (the rerank of it) | 53 s (49) | 137 s (129) | 214 s (142) |
| reading the 2,258-token prompt | 22 s | 63 s | 115 s |
| writing | 17.7 tokens/s | 4.3 tokens/s | 4 tokens/s |
| self-eval | 24 s | 68 s | 122 s |
| routes | 4 `human`, 1 `auto` (the bare «[4]») | 5 `auto`, each with a reference | 5 `auto` |

The S2 question took longer than the same question opening S3 (77 / 100 s and 175 / 258 s):
its rerank took 115 s and 166 s against 49 s and 105 s; the record does not show why.

**Why no local model answers under the code-default limits.** With `RAG_DEVICE=auto` the
reranker runs on the 4 GB GPU, all 20 pairs in one call, because `RAG_RERANK_BATCH` is unset;
the request deadline is checked between batches only when that batch is set
(`vectordb/_base_manager.py`, ~1014), so nothing interrupts the call. In the 7B record
retrieval took 25.4 s of the 30 s, the reranker failing with MPS out of memory; beside the
1.5B the failing call ran 48 s, beside the 4B 3 min 33 s — hence warm-up timeouts after 58 s
and 231 s under a 30-s limit. On the CPU the rerank alone exceeds the limit: retrieval with
no model loaded takes 27.6 s, 27.3 s of it the rerank (7B record), and the rerank grows as the
model takes memory — 49 s beside the 1.5B, 129 s beside the 4B, 142 s beside the 7B. Even the
smallest model needs a median 100 s (about 1.7 min) for a whole answer, half of it the
rerank. Answers in seconds would take changes to the pipeline itself, not only a smaller
model — Julia's to decide (State, Waiting on Julia).

**The tag that was not what it said.** The plan registered `qwen3:4b`; Ollama now serves
that tag as Qwen3-4B-Thinking-2507 (manifest `359d7dd4bcda…`), which cannot stop thinking.
Sent `think: false`, it wrote its reasoning as the answer and stopped at the 384-token cap
in all six cases of its 1- and 5-case steps; the runner was stopped at 17:20:27 (the 5-case
step ran to its end), and no 100-case step ran. The replacement, Qwen3-4B-Instruct-2507
(`qwen3:4b-instruct-2507-q4_K_M`, `0edcdef34593…`), was fixed in `tools/run_screen2.sh`
before its download (17:25:14); the spec's amendment (`cfb78ee`) was committed at
17:31:22, about eight seconds after the replacement's first answer came back, unread. So
"before its first answer" holds for the decision and the runner, not for the commit; the
amendment says so. qwen3:1.7b is hybrid, and `think: false` works for it.

**qwen3:1.7b on the chat path thinks.** The provider (`llm/providers/ollama.py`) builds
`langchain_ollama.OllamaLLM` without `reasoning`; the library then sends `think: null`, and
Ollama 0.33.2 leaves a hybrid Qwen3 thinking: through the provider's own class it wrote 411
characters of reasoning and 130 output tokens for a one-sentence answer
(`tools/think_probe.out` of the chat record). The chat drops the reasoning but waits for it.

**Found on the way: a 503 inside a started stream.** In the 4B code-default run the
warm-up's messages failed to persist (`Failed to persist messages (stream_fallback)`, under
swap) and the session store went into its cooldown; the next question, sent with a fresh
`session_id` as the web chat sends it, was refused by `_get_or_create_session` with 503
«Session store temporarily unavailable» — by design (fail-closed for an unverified id,
`api/app.py` ~1233). But `event_generator` (`api/routers/conversation.py` ~1609) yields
its `status` event before that call (uvicorn: `response already started`), and the client
gets a stream that ends after `status` with neither `error` nor `result` — in the web
chat, an answer that never comes. Not fixed (outside the agreed plan); the notes of run
`live-s1-qwen3-4b-instruct-prod` keep it (`api_warnings` holds only JSON log lines). Each
run's first audit write timed out as the first request restored the BM25 index.

## Julia's decisions in force

- 2026-10-14 «прод на маке» — production is `deproject-mac`; do not answer "other hardware".
- 2026-10-14 «Модель для прода. Давай подвесим вопрос.» — the production model is suspended;
  the screening changes no default; a model swap (ROADMAP stop-list) and the SLO stay hers.
- 2026-10-15 «1. Да 2. Да. 3. Давай решим это позже» — restart the judge: done; push the 47
  commits: done, up to `a7bf232` (the approval named those 47; later commits wait for her
  word); the production model and the pipeline levers of question 3: later.
- D12 (2026-10-04, «ты должен все делать сам»): the session does everything itself; no other
  model in any role. D11: no person in the quality process — the judge is a model and is
  never called human. No MyFlow unless she names it.

## What was the session's choice, not hers

- Replacing the thinking tag by Qwen3-4B-Instruct-2507 (amendment in the spec).
- Timing in the chat only the two small models that need no code change there (qwen3:1.7b
  thinks on the chat path), through a copied stand (`MODEL=`, a copy of
  `config/providers.yml`) instead of a changed default.
- Sending the judge's requests one at a time as one stream (her global rule: no parallel
  work unasked), on the laptop while the chat runs used the Mac; restarting it in
  foreground chunks of ten with ~1.4 GB free, memory checked between chunks.
- Reporting the 503 inside the stream rather than fixing it; not writing the extension plan
  before Julia's word on its run.
- Deleting the backup branch `wip/genscreen-judge` once the verdicts were committed; keeping
  `red-genscreen`, the red check this log cites.
- Fixing the red CI on `a7bf232` in four local commits; capping multidict below 7; forcing
  katex 0.18 and postcss-selector-parser 7 by npm overrides past the lines their parents
  ask for (both build-time only) and leaving the site's build on them to CI.

## Log

All times UTC, 2026-10-14 unless dated; the screening's own log is
`reports/generator-screen/86df582/progress.log`.

- 15:30–15:55 — plan, runner changes and judge committed (`86df582`, 15:50); their tests red
  on `87c53f9` (the new tests on the parent `cf9504e`, branch `red-genscreen`), green on the
  Mac at `86df582`, 335 passed. Judge dry run: one request, 24.5 s, $0.056.
- 15:55–18:56 — 1 → 5 → 100 cases by `tools/run_screen.sh` in a clean clone of `86df582` on
  the Mac: qwen2.5:1.5b (its 1-case step by hand), qwen3:1.7b, `qwen3:4b` (reasoning
  instead of answers, stopped at 17:20:27, the tag identified by `tools/registry_tags.py`),
  Qwen3-4B-Instruct-2507 (`tools/run_screen2.sh`; the amendment `cfb78ee` at 17:31:22).
- 18:24 — probe of the subscription windows before the judge: five-hour 0, weekly 0.18.
- 18:56–19:54 — the chat timed with the two small models (`live_small.sh`). The first launch
  lost three runs: each supervisor started while the API before it still held port 8002;
  the script now waits for free ports, the empty run directories were removed.
- 18:56–20:16 — the judge: plan frozen at 18:56 (165 requests, no empty answer);
  `--limit 1` (180 s, $0.39, 18.7k output tokens), `--limit 4`, then at 19:10 the remaining
  160 in one background command, stopped at about 20:16 by the idle stop: 99 valid
  verdicts, $10.54, 4,288 s, the file intact, the request in flight lost.
- 19:55–20:05 — the think probe (its first version printed a wrong line and was redone);
  `f470f03` at 20:02, Mac gate 37 passed.
- 20:16–20:50 — a cold read and its fixes; the screening record without the verdicts, its
  test and evidence row, the spec's status, the state and this log in `40ad172` (20:42).
- 2026-10-15 08:44 — Julia's «1. Да 2. Да»: `git push` of `f7416ca..a7bf232` (47 ahead, 0
  behind). Windows: five-hour 0.01, weekly 0.21. Free memory on the laptop 1.5 GB of 15.9.
- 08:45–09:33 — the judge's remaining 66 requests in seven foreground chunks (`--limit 10`),
  all valid at the first attempt, 2,744 s and $6.87, free memory 1.4–1.6 GB; `summary`:
  missing 0.
- 09:33–09:41 — the verdicts published into the record (LF; `plan.json` unchanged) with the
  test, the evidence row, the spec's status and the state: `384f7df`, Mac gate 45 passed.
- 09:45–10:13 — CI on `a7bf232` red (State, CI); the causes fixed in `83a2158`, `9eb93c9`
  (09:58, Mac gate 575 passed), `d5328d3`, `af6b905` (10:13, 126 passed); the whole unit
  suite on the Mac, 5,781 passed.
- 10:15–10:35 — the second cold read's findings fixed here and in EVIDENCE_INDEX,
  CURRENT_STATE and AGENT_STATE; the report to Julia.

## State and next actions

The chat record and the screening record are complete and pinned, the judge's verdicts and
summary included (`judge/`); the judge's working files stay git-ignored on the laptop
(`.tmp/genscreen-judge/`), the record holds their LF copies. Nothing runs on the Mac or the
laptop. Untracked and not ours: `demo/phase-e-raw.webm`, `reports/ask100/`. The local branch
`red-genscreen` keeps `87c53f9`, the red check of `86df582`.

**CI.** The first runs since `f7416ca`, on `a7bf232` — CI 38707871645 and the docs-site
deploy 38707871632 — failed on five causes, each fixed in a local commit:

1. `grade_docs` (since `33d4b42`) built its prompt inside the `try` that turns any error
   into a rejected document, so a broken prompt rejected the document instead of failing
   the node. `83a2158`: a batch over the window is graded one document at a time; a prompt
   that cannot be built or fit is a node error, as in `generate`.
2. mypy on `api/routers/conversation.py` — `9eb93c9` types the stream LLM `Any`.
3. bandit B506 on the `BaseLoader` `yaml.load` in `evaluation/label_verification.py` —
   `9eb93c9`, `# nosec B506` with the reason.
4. An exact-float replay of the pilot's power sizes, off on Linux by ≤ 2.1e-15 — `9eb93c9`
   compares at `rel_tol` 1e-12.
5. Advisories published since 2026-10-03: pip-audit (fsspec, langgraph-sdk, multidict) —
   `d5328d3` raises the floors, caps multidict below 7 (7 drags aiohttp and yarl along) and
   regenerates both locks, three pins each (its message gives the docs-site run's number
   by mistake); npm DEP-01 (sharp, katex, postcss-selector-parser, smol-toml,
   source-map-js) — `af6b905`.

Not checked before CI: the site's build on the new npm lock (it needs Chromium: not on the
laptop, and the Mac has no Node) and the full suite on the new Python pins (the Mac's venv is
not built from the lock). What was checked is under Verification.

**What the judge costs.** The `total_cost_usd` the CLI reports per request is the API price
of its tokens; the requests run on Julia's subscription and count against its windows. 165
verdicts: $17.41 and 7,031 s — $0.106 and 42.6 s a request on average, median 29.9 s, the
longest 4 min 21 s. 166 requests were sent: the one in flight at the idle stop was lost and
sent again; it and the $0.056 dry run are not in the sums. The weekly window went from 0.18
to 0.21 over the first 99 requests and the session's own work, and to 0.24 by 10:34 on
2026-10-15 over the last 66 and the CI fixes (five-hour 0.25); it resets on 2026-10-20 at
22:00. At the stream-alone rate (0.01 of the week ≈ $10) the extension takes about 0.02–0.03.

**The judge's commands** (laptop): `scripts/generator_answer_judge.py plan --report
NAME=PATH … --out DIR` freezes the plan (`--dataset` and `--contexts` default to C.1's);
then chunk by chunk, free memory checked between them,
`MSYS_NO_PATHCONV=1 timeout 1150 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -X utf8 D:/RAG_new/scripts/generator_answer_judge.py run --out D:/RAG_new/.tmp/genscreen-judge --limit 10`;
`summary --out DIR` writes `summary.json`; `.tmp/genscreen/publish_judge.py` copies the plan,
verdicts and summary into the record with LF.

**The gate** for any commit — the laptop's git-ignored scripts make the Mac's gate tree that
commit and run pytest there:
`MSYS_NO_PATHCONV=1 timeout 600 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/.tmp/ask100-split/sync_commit.py <rev>`,
then `MSYS_NO_PATHCONV=1 timeout 1100 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <tests> -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`.
For these records: `tests/test_generator_screen_artifact.py`,
`tests/test_chat_live_small_artifact.py`, `tests/test_chat_live_artifact.py` and the three
docs tests. Before a push also the whole unit suite (`tests/ --ignore=tests/integration`,
~7 min, in the background) and CI's static checks: mypy (laptop), bandit (Mac), pip-audit
(`uvx`, laptop). No pytest on the laptop.

Next, in order:

1. **The 503 inside a started stream — the one rule-(a) slice that needs no word of hers.**
   Resolve the session before `StreamingResponse` starts (the client then sees a plain 503),
   or catch the refusal inside `event_generator` and send an SSE `error` event. E2E: trip the
   tenant's cooldown as `tests/test_pipeline_concurrency.py` does
   (`api_app._db_cooldown.trip("default")`, line 77; `tests/test_db_cooldown_per_tenant.py`
   injects its own `_cooldown()` instead, lines 226 and 314, and the latter also fakes
   `_get_or_create_session`), post `/api/ask/stream` with a fresh `session_id`, and require
   an `error` event or a 503 before the first byte. The ROADMAP freezes durable HTTP
   semantics (its 503 among them) and "SSE as a projection of persisted events; removing the
   direct-stream path"; this fix keeps the direct path and adds no status semantics — it
   makes the existing refusal visible. Say so in the commit.
2. **Julia's answers to the three questions of the 2026-10-15 report:** the 100-case
   extension (which generators, requests, price, hours, share of the weekly window),
   qwen3:1.7b in the chat, the push of the commits after `a7bf232`. Act on each only after
   her «да».
3. **The extension, on her word.** The plan does not define "the generators concerned".
   Read as the leading small generator and each reference within five of it, they are
   Qwen3-4B-Instruct (23), C.1a (20) and C.1b (21); qwen2.5-1.5b (16) is within five of
   C.1a, C.1b and qwen3-1.7b, and qwen3-1.7b (20) of all — Julia approves the set with the
   run. A new plan with the same judge, request rules,
   classes and retest, committed with its tests before any request. Traps: `judge.SAMPLE_SIZE`
   (30) is pinned by `tests/test_generator_screen_artifact.py` (lines 172, 189) and
   `tests/test_generator_answer_judge.py` (line 137) — make the sample size a parameter
   defaulting to 30. To reuse the 30 judged cases keep the same `NAME=` labels (an item's id
   is the first 16 hex of sha256("NAME:case"), unsalted), write to a new `--out` (a plan is
   frozen) and copy in only the non-retest rows of the generators kept: `_vouched` refuses a
   row off the plan. At the pace so far, reuse: 225–295 requests (3 or 4 generators × 70,
   plus 15 retests), $23.7–31.1, 2.7–3.5 h; sent again: 315–415, $33–44, 3.7–4.9 h.
4. Push the commits after `a7bf232` on her word:
   `git -c credential.helper='!gh auth git-credential' push origin master`; then watch CI
   and the docs-site build, which meet the new pins there for the first time.

**Waiting on Julia** (no step until she speaks):

- The production model — deferred again on 2026-10-15 — and the SLO, hers since 2026-10-14.
  On this Mac no local model answers within the code-default 30 s; with the limits raised the
  whole answer takes a median 100 s (qwen2.5:1.5b: 16 good of 30, the most bad answers),
  297 s (Qwen3-4B-Instruct: 23 good) or 486 s (qwen2.5:7b: 20 good). "Good" is the
  benchmark's, not the chat's (Do not).
- The levers beyond the model: the rerank (alternative rerankers are on the stop-list;
  switching it off is a quality question), the self-eval call after the answer, the limits.
- qwen3:1.7b in the chat: 20 good, 15.8 s a case in the benchmark against the 4B's 36.7 s,
  but it thinks on the chat path; timing it needs the provider to send `think: false`
  (`reasoning=False` for `OllamaLLM` in `llm/providers/ollama.py`, checked against models
  without thinking). Ask her with step 2; without her «да» the provider stays as it is.

## Do not

- Push without Julia's word, run the 100-case extension, or change the provider for
  qwen3:1.7b without it.
- Treat the screening's quality as the chat's: the chat prompt differs, and qwen2.5:1.5b
  answered "[4]" there.
- Register a model by its short Ollama tag without reading `/api/show` (`general.finetune`,
  `general.version`, `capabilities`): tags are moved to new releases.
- Put a record where its path contains another record's path (evidence rows are found by
  substring).
- Run tests on the laptop; read, print or copy `.ask100-runtime/env.json`; kill processes
  you did not start on the Mac (Auto_try_v2, PostgreSQL servers, `ollama serve`); install
  anything there with brew; rebuild the 5,589-chunk index; touch `demo/phase-e-raw.webm` or
  `reports/ask100/`.

## Lessons

- **A short tag is not a model.** `qwen3:4b` meant a hybrid Qwen3 when the plan was written
  and a thinking-only release when it ran. The step check now prints how many answers reach
  `num_predict` and the first answer's opening, which would have flagged it at once.
- **Commit a registered change before the run it governs.** The amendment was fixed in the
  runner before the download but committed after the replacement's first answer; the
  commit's time alone no longer proves the order.
- **A probe must read the payload, not guess it.** The first think probe searched the
  library's source for two spellings, found neither and printed `False`; the library does
  send `think` — as `null`.
- **Memory is the latency on 8 GB.** The CPU rerank takes 27.3 s with no model loaded and
  142 s beside the 7B; the 4B writes 6.7 tokens/s in the benchmark and 4.3 in the chat.
  Time a model where it will run.
- **Back-to-back runs race for their ports**: right after a run the API's socket can still
  hold 8002. Wait for the ports, not a fixed pause.
- **Windows writes CRLF**: `Path.write_text` on the laptop writes `\r\n`; normalise to LF
  before pinning hashes (git stores LF).
- **A judge request costs what the answer makes it think.** At effort max the dry run's
  request took 1.9k output tokens, the first real one 18.7k. Price a stream from several
  requests, not one.
- **Focused gates are not CI.** The 47 commits passed focused Mac gates; their first CI run
  failed on a `grade_docs` regression caught by a test no focused gate ran, a type error
  and a bandit finding no gate checks, a float replay exact on the Mac and off on Linux,
  and advisories published meanwhile. Before a push: the whole suite and CI's static
  checks.

## Glossary

- **C.1 contract** — `scripts/generator_benchmark.py` over the 100 curated cases and the
  cached contexts of arm C, prompt `aircargo-context-only-ru-v1`, temperature 0, `num_ctx`
  4096, `num_predict` 384, 6,000 characters of context, seed 42.
- **Arm C** — the retrieval arm whose candidates the C.1 benchmarks cache
  (`.tmp/ab_candidates_phase2_C.json`, the judge's default `--contexts`; tracked gzipped as
  `evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz`); cut as C.1 cuts them, the contexts
  hold 0.905 of the expected keywords.
- **C.1a / C.1b** — the published answers of qwen2.5:7b and qwen3:8b on that contract.
- **The one judge** — claude-opus-5-5 at effort max, one stateless request per answer through
  `evaluation.isolated_request`, blind to the generator (D12).
- **good / partial_ok / bad** — a full answer with every claim supported and no defect (or a
  right decline) / a partial one with every claim supported / everything else.
- **Stand** — `/Users/julia/RAG_new_chat_33d4b42/chatlive-small/` on the Mac: the 7B record's
  supervisor (starts the API with the run's model and limits), runner and export, adapted by
  `make_small_stand.py`, in an export of `33d4b42` (`CODE_SHA` names the commit) with the
  5,589-chunk index.
- **B1 / B2** — the question sets of the 7B record's runs `live-b1-prod` (the warm-up «Какие
  документы нужны для перевозки опасного груза?», then the case `aircargo-probation-data`)
  and `live-b2-floor` (the cases `aircargo-probation-data`, `-extend`, `-dismissal`,
  `aircargo-dismissal-check`, `aircargo-dismissal-lawyer`). Here **S1** is B1 at the code
  defaults, **S2** the first B2 case alone at the floor on a freshly started API, **S3** all
  five at the floor (labels `live-s1-<model>-prod`, `live-s2-…-floor1`, `live-s3-…-floor`).
- **First token / whole answer** — seconds from sending the question to the first streamed
  token / to the `result` event that closes the answer (after self-eval and suggested
  questions).
- **Code-default limits** — `REQUEST_TIMEOUT_SEC` 30, `STREAMING_TIMEOUT_SEC` 120,
  `OLLAMA_REQUEST_TIMEOUT_SEC` 60, `RAG_DEVICE=auto`; **floor** — the three limits at 1800 s,
  only to measure how long a complete answer takes, with `RAG_DEVICE=cpu`.
- **Route** — the verdict in the `result` event: `auto` (answered; suggested questions follow),
  `human` (handed to an operator: the self-eval scored the answer below `QUALITY_THRESHOLD`),
  `timeout` (the request deadline hit). Unrelated to `RAG_DEVICE=auto`.
- **Idle stop** — what stopped the judge's stream at 20:16: Claude Code stops a background
  task when the laptop runs low on memory while the session sits idle. Foreground chunks
  keep the session working instead.

## Verification

- Mac gates: `f470f03` (the two chat tests and the three docs tests) 37 passed; `40ad172`
  and `a7bf232` (the six tests of the records) 42 each; `384f7df` 45.
- The chat record: `runs.json` exported by `export.sh` from a clean environment;
  `check_export.py` found only hashes and the masked `db_encryption_key`; the stand's
  `tools/` are byte-identical to those that ran on the Mac (sha256), its unchanged tools equal
  the 7B record's.
- The screening record: the reports' sha256 equal the plan's `report_sha256`; no CR byte and
  no laptop path in any published file.
- The verdicts: no laptop path, user name, email or key in `verdicts.jsonl` or
  `summary.json`; every row valid at the first attempt, model `claude-opus-5-5`, CLI
  2.1.300. `summarize` re-reads each verdict from its raw reply and refuses one without a
  clean session's record or with a request hash off the plan. The record's test recomputes
  the paired figures (1 against 8, p ≈ 0.04) from the verdicts.
- The CI fixes: `83a2158` and `9eb93c9` on the Mac gate, 22 test files, 575 passed;
  `d5328d3` and `af6b905`, 6 files, 126 passed; the whole unit suite on the Mac at `af6b905`:
  5,781 passed, 121 skipped. Both mypy commands of `ci.yml` clean on the laptop (32 and 159
  files); bandit with CI's command on the Mac: no issue; pip-audit 2.10.0 with CI's flags:
  none found, 5 ignored; `docs-site/scripts/check-npm-audit.mjs`: DEP-01 PASS (one
  exception, http-cache-semantics, until 2026-11-03); the new Python locks install and
  import in a throwaway Python 3.11 venv.
- This commit's own gate goes into the next log.
- Cold reads by a fresh subagent on the session's model (D12 allows no other). The
  2026-10-14 version's gaps (the order of "Next", claims ahead of the judge, mixed-up
  rerank figures, missing commands and definitions) were fixed in `40ad172`. `384f7df`'s
  version drew 13 findings, fixed in the commit that carries this text: the extension
  before the 503 slice and Julia's decisions mixed into "Next"; no judge commands,
  extension traps or estimate basis; claims stronger than 30 cases bear; off timings and
  counts; the "generators concerned" rule unstated; the benchmark's "good" read as the
  chat's; her questions paraphrased; no "ask her first" for qwen3:1.7b; a wrong cooldown
  test; an ambiguous glossary entry and dates; CURRENT_STATE calling pushes delegated.
