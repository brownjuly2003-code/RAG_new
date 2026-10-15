# Session handoff — 2026-10-14 — generators below 7B on the production Mac

Session `ef96201d` (continued after context compactions), 2026-10-14 13:15–20:50 UTC and
2026-10-15 08:40–10:00 UTC, Claude Opus 5.5 alone (D12). Commits: `86df582` (the screening
registered), `cfb78ee` (its amendment), `f470f03` (the live chat record), `40ad172` (the
screening record without the judge's verdicts, and these documents), `a7bf232` (its
verification); on 2026-10-15 the commit that publishes the verdicts and the one that fills
its verification. **Pushed on 2026-10-15 at Julia's word:** `f7416ca..a7bf232`, the 47
commits of 2026-10-04…10-14; the commits after `a7bf232` are local. The session before this
one, on 2026-10-14, measured the web chat with qwen2.5:7b:
[session log](session-handoff-2026-10-14-chat-on-mac.md).

## What matters to understand

**Julia's message.** After the 7B record (no answer under the code-default limits; ~5.5 min
to the first word and ~8 min to the whole answer with the limits raised) she wrote:
«Модель для прода. Давай подвесим вопрос. И посмотрим, как на тестах результаты на модели
< 7B. Что думаешь?» — the choice of the production model is suspended, and she wants to see
how models below 7B do in tests. The session proposed a plan (screen the Apache-2.0 Qwen
generators below 7B against C.1a and C.1b on the C.1 contract, graded by the one judge, then
time the chat with them); she answered «согласна». On 2026-10-15, asked whether to restart
the judge (stopped for low memory), whether to push, and about the model, she wrote «1. Да
2. Да. 3. Давай решим это позже»: the judge finished, the 47 commits are pushed, and the
choice of the model waits.

**Two measurements, two questions.**

1. *The screening* ([plan](../specs/small-generator-screening.md), record
   `reports/generator-screen/86df582/`) asks which small model writes good answers from the
   contexts it is given. It is the C.1 benchmark — its own prompt
   `aircargo-context-only-ru-v1` over the cached retrieval of arm C, 100 cases, temperature
   0, seed 42 — not the chat path. Quality comes from the one judge (claude-opus-5-5, effort
   max, stateless requests) on 30 cases shared by all five generators; deterministic checks
   cover all 100 answers. Speed is Ollama's own timing of each generation.
2. *The live chat* (record `reports/chat-live-small/33d4b42/`) asks how long a user waits on
   this Mac. It is the stand of the 7B record (`reports/chat-live/33d4b42/`) serving another
   model through `MODEL=` of its supervisor: the real API at `33d4b42`, the 5,589-chunk index,
   the questions sent through `/api/ask/stream` as the web chat sends them, with the chat's
   own prompt, self-eval and suggested questions. The record is not under `reports/chat-live/`
   because the 7B record's test finds its evidence row by the substring
   `reports/chat-live/33d4b42`, which `33d4b42-small` would also contain.

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
latencies include two self-grading requests and are not comparable, and their reports carry
no Ollama timings (`ollama_timing` was added for this screening) — hence the dashes. The
answers without Cyrillic are English lists: qwen3-8b's 8 name fields, a right answer to a
field question; Qwen3-4B-Instruct's one names documents («AWB/HAWB, cargo manifest, …», case
`aircargo-cargo-loss-evidence-bundle`).

**What the judge says.** It agreed with itself: the same class on 15 of 15 retests, the
same `context_has_answer` for all five answers in 30 of 30 cases. Thirty cases tell apart
only gaps of more than five good answers (at 25 of 30 the 95 % Wilson interval is about
0.66–0.93): of all pairs only qwen2.5-1.5b and Qwen3-4B-Instruct are told apart. The 1.5B
has the most bad answers (9) and 8 of its 30 hold an unsupported claim. Qwen3-4B-Instruct
leads the small generators and is within five good answers of C.1a and C.1b, so the plan's
reading extends the judge to all 100 cases of the generators concerned under a new plan
(State, below). qwen3-1.7b, last on keyword recall, is level with C.1a on good answers: the
keyword measure and the judge disagree on it, and the judge is the plan's measure. The
stream was stopped once by low memory on the laptop (99 verdicts) and finished on
2026-10-15; 165 requests, all valid at the first attempt, $17.41, 7,031 s.

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
smallest model needs about a minute and a half for a whole answer, half of it the rerank.
Answers in seconds on this Mac would take changes to the pipeline itself (the rerank, the
self-eval call after the answer), not only a smaller model — and those are Julia's:
alternative rerankers are on the ROADMAP stop-list, and the SLO is hers.

**The tag that was not what it said.** The plan registered `qwen3:4b`. Ollama now serves
that tag as Qwen3-4B-Thinking-2507 (registry manifest `359d7dd4bcda…`, the same as
`qwen3:4b-thinking-2507-q4_K_M`), a model with no mode without thinking. Sent
`think: false`, it wrote its reasoning as the answer («Хорошо, мне нужно ответить на вопрос
пользователя…») and stopped at the 384-token cap in all six cases of its 1- and 5-case steps,
69–125 s a case. The session stopped the runner at 17:20:27, during the 5-case step, which
ran to its end; no 100-case step ran for that tag. The replacement, Qwen3-4B-Instruct-2507
(`qwen3:4b-instruct-2507-q4_K_M`, `0edcdef34593…`), was fixed in `tools/run_screen2.sh`
before its download began at 17:25:14. The spec's amendment (`cfb78ee`) was written while the
replacement's 1-case step ran and committed at 17:31:22 — about eight seconds after that
case's answer came back (start 17:30:31 plus 42.5 s), without reading it: the step's summary
line reached the log after the commit. So "before its first answer" holds for the decision
and the runner, not for the commit's time; the spec's amendment now says so. qwen3:1.7b is a
hybrid model, and `think: false` works for it.

**qwen3:1.7b on the chat path thinks.** The provider (`llm/providers/ollama.py`) builds
`langchain_ollama.OllamaLLM` without `reasoning`; the library then sends `think: null`, and
Ollama 0.33.2 leaves a hybrid Qwen3 thinking: through the provider's own class it wrote 411
characters of reasoning and 130 output tokens for a one-sentence answer
(`tools/think_probe.out` of the chat record). The chat drops the reasoning but waits for it.

**Found on the way: a 503 inside a started stream.** In the 4B code-default run the
warm-up's messages failed to persist (`Failed to persist messages (stream_fallback)`, under
swap), the session store went into its cooldown, and the next question — sent, as the web
chat sends it, with a fresh caller-supplied `session_id` — was refused by
`_get_or_create_session` with 503 «Session store temporarily unavailable». The refusal is by
design (fail-closed for an unverified id, `api/app.py` ~1233), but `event_generator` in
`api/routers/conversation.py` (~1609) yields its `status` event first and calls
`_get_or_create_session` after: uvicorn logs `Caught handled exception, but response already
started`, and the client gets a stream that ends after `status` with neither `error` nor
`result` — in the web chat, an answer that never comes. Not fixed (outside the agreed plan);
the notes of run `live-s1-qwen3-4b-instruct-prod` keep it, because `api_warnings` holds only
the JSON log lines. Every run's first audit write also timed out (`Audit DB write failed:
action=ask error=TimeoutError`) just as the first request restored the BM25 index.

## Julia's decisions in force

- 2026-10-14 «прод на маке» — production is `deproject-mac`; do not answer "other hardware".
- 2026-10-14 «Модель для прода. Давай подвесим вопрос.» — the production model is suspended;
  the screening informs her choice and changes no default. A model swap stays on the ROADMAP
  stop-list until she decides; the same holds for the SLO.
- 2026-10-15 «1. Да 2. Да. 3. Давай решим это позже» — restart the judge: done; push the 47
  commits: done, up to `a7bf232` (the approval named those 47; later commits wait for her
  word); the production model: later.
- D12 (2026-10-04, «ты должен все делать сам»): the session does everything itself; no other
  model in any role. D11: no person in the quality process — the judge is a model and is
  never called human. No MyFlow unless she names it. Push only on her word.

## What was the session's choice, not hers

- Replacing the thinking tag by Qwen3-4B-Instruct-2507 (amendment in the spec).
- Timing in the chat only the two small models that need no code change there, and leaving
  qwen3:1.7b out (it thinks on the chat path).
- Serving the models through a copied stand (`MODEL=`, a copy of `config/providers.yml`)
  instead of changing a default.
- Sending the judge's 165 requests as one stream — `run` sends them one at a time — rather
  than several at once (her global rule: no parallel work without asking). It ran on the
  laptop while the chat runs used the Mac — different machines.
- Reporting the 503 inside the stream rather than fixing it.
- Restarting the judge in foreground chunks of ten while the laptop had ~1.4 GB free (other
  applications held most of the memory), with memory checked between chunks.
- Not writing the 100-case extension plan before Julia's word on its run.
- Deleting the backup branch `wip/genscreen-judge` once the verdicts were committed, and
  keeping `red-genscreen`, whose commit this log cites as the red check.

## Log

All times UTC, 2026-10-14; the screening's own log is `reports/generator-screen/86df582/
progress.log`.

- 15:30–15:55 — plan, runner changes and judge committed (`86df582`, 15:50). Their tests red
  on a scratch commit `87c53f9` that put the new tests on the parent `cf9504e` (branch
  `red-genscreen`), green on the Mac at `86df582`, 335 passed. Dry run of the judge: one
  request, 24.5 s, $0.056.
- 15:55–16:36 — qwen2.5:1.5b: the 1-case step by hand (26.8 s), then 5 and 100 cases by
  `tools/run_screen.sh` in a clean clone of `86df582` on the Mac.
- 16:36–17:13 — qwen3:1.7b, 1 → 5 → 100.
- 17:13–17:25 — `qwen3:4b`: reasoning instead of answers; the runner stopped at 17:20:27
  (its 5-case step ran to its end), the tag identified in the registry
  (`tools/registry_tags.py`).
- 17:25–18:56 — Qwen3-4B-Instruct-2507 downloaded (`tools/run_screen2.sh`), 1 → 5 → 100;
  the amendment committed at 17:31:22 (`cfb78ee`; its timing above), docs tests green on the
  Mac.
- 18:24 — probe of the subscription windows before the judge: five-hour window 0, weekly 0.18.
- 18:56–19:54 — the chat timed with the two small models (`live_small.sh`). The first launch
  lost three runs: each supervisor started while the API before it still held port 8002 and
  refused; the script now waits for free ports, the three empty run directories were
  removed.
- 18:56–20:16 — the judge: plan frozen over the five reports at 18:56 (165 requests, no
  empty answer); `--limit 1` (180 s, $0.39, 18.7k output tokens), `--limit 4`, then at 19:10
  the remaining 160 in one background command. At about 20:16, while the session was idle,
  Claude Code stopped it because the laptop ran low on memory: 99 valid verdicts, $10.54,
  4,288 s of requests, the file intact; the request in flight was lost.
- 19:55–20:05 — the think probe (its first version printed a wrong line from a string search
  and was redone), analysis, export; `f470f03` committed at 20:02; Mac gate 37 passed.
- 20:16–20:50 — a cold read of this log and its fixes; the screening record without the
  verdicts (the reports, the steps of the thinking tag, the frozen plan) with its test and
  evidence row, the spec's status, the state and this log, in one commit (`40ad172`, 20:42);
  Mac gate below. The judge's files and the drafts backed up to a local branch (State).
- 2026-10-15 08:44 — Julia's «1. Да 2. Да»: `git push` of `f7416ca..a7bf232` (origin had not
  moved: 47 ahead, 0 behind). Probe of the windows: five-hour 0.01, weekly 0.21. Free memory
  on the laptop 1.5 GB of 15.9.
- 08:45–09:33 — the judge's remaining 66 requests in seven foreground chunks (`--limit 10`),
  all valid at the first attempt, 2,744 s and $6.87; free memory stayed at 1.4–1.6 GB.
  `summary`: missing 0.
- 09:33–10:00 — the verdicts and the summary published into the record (LF; `plan.json`
  unchanged), the test extended, the evidence row, the spec's status, CURRENT_STATE and this
  log updated; commit and Mac gate below.

## State and next actions

The chat record and the screening record are complete and pinned, the judge's verdicts and
summary included (`judge/`). The judge's working files stay git-ignored on the laptop
(`.tmp/genscreen-judge/`); the record holds their LF copies. Nothing runs on the Mac (no model
loaded, no live or screening process) or on the laptop. Untracked and not ours:
`demo/phase-e-raw.webm`, `reports/ask100/`.

**Branches (local).** `red-genscreen` keeps `87c53f9`, the red check of `86df582` this log
cites. `wip/genscreen-judge`, the backup of the judge's files and the drafts, was deleted once
the verdicts were committed.

**What the judge costs.** The `total_cost_usd` the CLI reports per request is the API price
of its tokens; the requests run on Julia's subscription and count against its windows. The
whole judge: 165 requests, $17.41, 43 s a request on average (median 28 s, up to 4.5 min).
Claude Code stops a background stream when the laptop runs low on memory while the session
sits idle, and asks that it not be restarted unasked; the restart ran in foreground chunks.

**The gate** for any commit: the laptop's git-ignored scripts make the Mac's gate tree that
commit and run pytest there —
`MSYS_NO_PATHCONV=1 timeout 600 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/.tmp/ask100-split/sync_commit.py <rev>`,
then `MSYS_NO_PATHCONV=1 timeout 1100 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <tests> -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`.
For these records the tests are `tests/test_generator_screen_artifact.py`,
`tests/test_chat_live_small_artifact.py`, `tests/test_chat_live_artifact.py` and the three
docs tests (`test_docs_hygiene.py`, `test_docs_quality.py`, `test_docs_publication.py`).
No pytest on the laptop.

Next, in order:

1. **The 100-case extension, owed by the plan's reading** — Qwen3-4B-Instruct came within
   five good answers of C.1a and C.1b. On Julia's word the session writes a new plan with the
   same rules (judge, request rules, classes, retest), commits it with its tests before any
   request, and runs it. The generators concerned: Qwen3-4B-Instruct, C.1a and C.1b, and
   qwen3-1.7b, level with C.1a, is worth adding. About 70 more cases each: 225–295 requests
   with a retest, ~$24–31 and ~3 h at the pace so far. `build_plan` takes the first 30 cases
   by a salted hash (`judge.SAMPLE_SIZE`); the plan must say whether the 30 judged verdicts are
   reused (their request hashes would match) or sent again.
2. **Julia** chooses the production model and the SLO — later, by her word of 2026-10-15 —
   with these numbers: on this Mac no local model answers within the code-default 30 s; with
   the limits raised the whole answer takes ~1.5 min (qwen2.5:1.5b: 16 good of 30, the most bad
   answers), ~5 min (Qwen3-4B-Instruct: 23 good, level with the 7B and the 8B on 30 cases) or
   ~8 min (qwen2.5:7b: 20 good). qwen3-1.7b (20 good) is not timed in the chat (item 5). A
   model swap and the limits are hers.
3. If she wants it faster on this Mac, the levers beyond the model are hers too: the rerank
   (alternative rerankers are on the stop-list; switching the rerank off is a quality
   question), the self-eval call after the answer, the limits.
4. **A rule-(a) slice that needs no decision of hers: the 503 inside a started stream.**
   Resolve the session before `StreamingResponse` starts (the client then sees a plain 503),
   or catch the refusal inside `event_generator` and send an SSE `error` event. E2E: trip the
   tenant's cooldown (`api.app._db_cooldown.trip("default")`, as
   `tests/test_db_cooldown_per_tenant.py` does), post `/api/ask/stream` with a fresh
   `session_id`, and require an `error` event or a 503 before the first byte. The ROADMAP
   freezes durable HTTP semantics (its 503 among them) and "SSE as a projection of persisted
   events; removing the direct-stream path"; this fix keeps the direct path and adds no new
   status semantics — it makes the existing refusal visible. Say so in the commit.
5. **qwen3:1.7b in the chat, now worth asking Julia about**: level with C.1a on good answers
   and 2.3× faster than the 4B a case in the benchmark (15.8 s against 36.7 s), but it thinks
   on the chat path. Timing it needs the provider to send `think: false` (`reasoning=False`
   for `OllamaLLM` in `llm/providers/ollama.py`, checked against models without thinking) —
   a change to the production provider; hers to ask for.
6. Push the commits after `a7bf232` on her word:
   `git -c credential.helper='!gh auth git-credential' push origin master`.

## Do not

- Push without Julia's word, or run the 100-case extension without it.
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
  `num_predict` and the opening of the first answer — both would have flagged it at the
  1-case step instead of a person reading the log.
- **Commit a registered change before the run it governs.** The amendment was fixed in the
  runner before the download, but committed eight seconds after the replacement's first
  answer came back; the commit's time alone no longer proves the order.
- **A probe must read the payload, not guess it.** The first think probe searched the
  library's source for two spellings, found neither and printed `False`; the library does
  send `think` — as `null`. The second probe checks the exact line and reads the reasoning
  the provider's own class returns.
- **A deadline checked between batches does not bound one batch.** With `RAG_RERANK_BATCH`
  unset the reranker scores all pairs in one call, and a 30-s request ran 58 s and 231 s.
- **Memory is the latency on 8 GB.** On the CPU the rerank takes 27.3 s with no model loaded
  and 142 s beside the 7B; the 4B writes 6.7 tokens/s in the benchmark and 4.3 in the chat,
  where the embedder and the reranker share the memory. Time a model where it will run.
- **A background command over ssh must be the only command of its list.** `a && b && nohup c
  > log 2>&1 < /dev/null &` puts the whole list in the background, and the list keeps the ssh
  channel open for as long as `c` runs; start the detached command on its own.
- **Back-to-back runs race for their ports.** The supervisor checks that 8002 and 55433 bind;
  right after a run the API's socket can still hold 8002. Wait for the ports, not a fixed
  pause.
- **Windows writes CRLF.** `Path.write_text` on the laptop writes `\r\n`; the judge's files
  were normalised to LF before their hashes were pinned (git stores LF, `.gitattributes`).
- **A judge request costs what the answer makes it think.** At effort max the dry run's
  request took 1.9k output tokens, the first real one 18.7k. Price a stream from several
  requests, not one.

## Glossary

- **C.1 contract** — `scripts/generator_benchmark.py` over the 100 curated cases and the
  cached contexts of arm C, prompt `aircargo-context-only-ru-v1`, temperature 0, `num_ctx`
  4096, `num_predict` 384, 6,000 characters of context.
- **Arm C** — the retrieval arm whose candidates the C.1 benchmarks cache
  (`.tmp/ab_candidates_phase2_C.json`, `91ce1745…`, tracked gzipped as
  `evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz`); cut as C.1 cuts them, the contexts
  hold 0.905 of the expected keywords.
- **C.1a / C.1b** — the published seed-42 answers of qwen2.5:7b and qwen3:8b on that contract.
- **The one judge** — claude-opus-5-5 at effort max, one stateless request per answer through
  `evaluation.isolated_request`, blind to the generator (D12).
- **good / partial_ok / bad** — a full answer with every claim supported and no defect (or a
  right decline) / a partial one with every claim supported / everything else.
- **Stand** — `/Users/julia/RAG_new_chat_33d4b42/chatlive-small/` on the Mac: the 7B record's
  supervisor, runner and export, adapted by `make_small_stand.py`, inside an export of
  `33d4b42` (not a git checkout; its `CODE_SHA` file names the commit) with the 5,589-chunk
  index. The supervisor starts the API with the run's model and limits; the runner sends the
  questions as the web chat does.
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
- **Idle stop** — what ended the judge at 20:16: Claude Code stops a background task when
  the laptop runs low on memory while the session sits idle. Foreground chunks keep the
  session working instead.

## Verification

- `f470f03` on the Mac gate (`sync_commit.py f470f03`, then `remote.py --site pytest`):
  `tests/test_chat_live_small_artifact.py`, `tests/test_chat_live_artifact.py` and the three
  docs tests, 37 passed.
- The chat record: `runs.json` exported by `export.sh` from a clean environment;
  `check_export.py` (`reports/chat-live/33d4b42/tools/`) found only hashes and the masked
  `db_encryption_key` (`<empty>`/`<set>`). The stand's files in `tools/` are byte-identical to
  those that ran on the Mac (sha256 compared); `make_small_stand.py` ran on the laptop and
  makes the changed ones from the 7B record's tools, and the stand's unchanged tools equal the
  7B record's.
- The screening record: the reports' sha256 equal the `report_sha256` of the judge's plan;
  no CR byte and no laptop path in any published file.
- `40ad172`, the commit that adds this log, on the Mac gate (`sync_commit.py 40ad172`, then
  `remote.py --site pytest`): `tests/test_generator_screen_artifact.py`,
  `tests/test_chat_live_small_artifact.py`, `tests/test_chat_live_artifact.py` and the three
  docs tests, 42 passed; `a7bf232` likewise, 42 passed.
- The verdicts: no laptop path, user name, email or key in `verdicts.jsonl` or
  `summary.json` (scanned before publication); every row valid at the first attempt, model
  `claude-opus-5-5`, CLI 2.1.300. `summarize` re-reads each verdict from its raw reply and
  refuses one without a clean session's record or with a request hash off the plan.
- The commit that publishes the verdicts: ⟨GATE3⟩
- Cold read of the 2026-10-15 version: ⟨COLD2⟩
- Cold read: a fresh subagent on the session's model (D12 allows no other) read the previous
  version of this log cold. It found: "Next" put Julia's choice of the model before the
  judge's classes that should inform it, and said the 4B answers were "close to the 7B" with
  the judge pending; the 25.4 s / 27.6 s / 27.3 s figures mixed up — as was the chat
  record's evidence row, which gave 27.6 s for the rerank alone (now 27.3 s); the timeouts of
  58 s and 231 s under a 30-s limit unexplained; the red commit, the end of the thinking
  tag's 5-case step and the amendment's commit time stated loosely; "as registered" for the
  judge's single stream, which the plan does not say (`run` simply sends one request at a
  time); the window probe, the meaning of the dollars and the reason the restart waited for
  Julia missing; no definitions of idle stop, B1/B2, arm C or the stand; no commands for the
  judge, the gate or the backup branch; no files or test route for the 503 slice. All of it
  was fixed in `40ad172`.
