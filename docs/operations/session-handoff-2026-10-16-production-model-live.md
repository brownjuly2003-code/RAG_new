# Session handoff — 2026-10-16 — the production model served, the operator share measured

Session `ef520894`, 2026-10-16 18:52 UTC – 2026-10-17 02:30 UTC, Claude Opus 5.5 alone (D12). The session
before it: [the chat's steps 1–3](session-handoff-2026-10-16-chat-steps-1-3.md). It carried out
step 4 of the ROADMAP's active thread M — Julia's production model — in commits
`7a99c45` to the one that adds this log, and answered her question of the session: how
often answers go to an operator. **Nothing pushed:** `origin/master` is `e81f0c5`; the
previous session's last log entry `26fcb4a` and this session's commits wait for her word. CI cannot run: GitHub starts no job on this account
(«recent account payments have failed or your spending limit needs to be increased», CI run
38841686267 on `e81f0c5`); the checks CI runs are run on the Mac instead (Verification).

## What matters to understand

**"The share handed to an operator" is two different numbers.** What the product hands over
by itself, and what the model marks `human`. The web chat (`/api/ask/stream`) hands nobody
over: on `human`, `timeout` and `error` it shows «Передать оператору», and the client presses
it or not. The widget (`/api/ask`) opens a ticket by itself on `human` and `error`. So the
chat's automatic share is 0 by design, and the question is what the model marks `human`.

**The chat's rule, measured on the production model: 2 of 100 `human`.** The chat routes
`auto` when the model's own score of its answer (0–100, `build_self_eval_prompt`) is 80 or more.
The session sent that self-evaluation, through the repository's code on a clean `Settings()`,
for the 100 answers the 4B wrote in the generator screening, which the judge had graded 67
good, 21 partial_ok, 12 bad: 2 `human` (Wilson 0.6–7.0 %), both declines where the context held
the answer; 10 of the 12 bad and all 21 partial answers go `auto`; no good answer goes to a
person. The model scores 89 of its 100 answers 100. The rule is precise but nearly blind: an
operator would see one answer in fifty while the judge finds one in eight bad. Two readings
of the session's, not published: at a threshold of 100, 11 go `human` (3 bad, 5 partial, 3
good); the screening's NLI (an entailment model's check of the answer against the context) below
0.8 flags 12 (3 bad, 1 partial, 8 good). Neither separates. An estimate
of the rule on the test set — the screening's prompt and the phase-C contexts, not the chat's
retrieval — [evidence row](../../EVIDENCE_INDEX.md), record `reports/chat-route-replay/7a99c45/`.

**The widget's rule is stricter and unmeasured on the 4B.** `route_or_retry` in
`agent/graph.py` routes `auto` only when the self-evaluation is 80 or more **and** the relevance
0.8 or more **and** the grounding is verified — the answer cut into atomic claims, each checked
against the context, a factuality floor; otherwise up to two retries, then `human`. The claim
check is the signal the chat lacks. A run of 2026-10-13 on qwen2.5:7b marked 11 of 39 `human`
(`reports/ask100/fixed-20261013/`, untracked, not this repository's: its code a patched
snapshot no commit names — NOT_EVIDENCE; [session log](session-handoff-2026-10-15-judge-100.md)). It cannot be replayed on the screening's 100 answers, which cite no `[N]`:
the claim check would refuse them all. It is measured on answers in the chat's own form under
[the handover plan](../specs/handover-signal.md) (Julia, 2026-10-17: «Давай сначала замерим»).

**The 4B serves by default since `7a99c45`.** `config/settings.py`, `config/providers.yml`
(listed — the runtime refuses an unlisted model — the Ollama defaults, `local-first`, the
GraceKelly fallback), `.env.example`, docker-compose's pull, the Helm values and the
quickstarts name `qwen3:4b-instruct-2507-q4_K_M`. The E2E test reads what a fake Ollama is asked.

**Two settings choose "the model", and the chat read both.** The stream writes the answer and
the self-evaluation with the provider profile's model (`config/providers.yml`, `local-first`),
but until `19beeb1` it asked `OLLAMA_MODEL_NAME` for the suggested questions. With clean
defaults both name the 4B, so the test of `7a99c45` passed; a deployment that pins
`OLLAMA_MODEL_NAME` — the ask100 runtime's `env.json`, which every live stand loads, pins
`qwen2.5:7b` — loaded the 7B (about 4.7 GB) beside the 4B after every answer. Since `19beeb1`
the suggestions follow the answer's model, as the self-evaluation already did. No API runs
on the Mac between measurements; the stands are its production path, and since `cf25593`
the live supervisor drops five model keys of `env.json` (`OLLAMA_MODEL_NAME`,
`OLLAMA_FAST_MODEL_NAME`, `MODEL_ROUTING_ENABLED`, `LLM_PROVIDER_PROFILE`,
`PROVIDER_REGISTRY_PATH`). `env.json` itself is not changed — the session does not read it —
so an API started from it some other way may serve another model: read its
`effective_settings.json` first.

**The first live series was therefore not the 4B's**, and is not published (20:12–21:12 UTC,
stand `/Users/julia/RAG_new_chat_7a99c45`): answers took 417–553 s, swap reached about 7 GB,
and its thirty stopped at question 2 on a 503 (next paragraph). Its runs stay on the Mac.

**The 503: the session store's cooldown.** A database write that misses
`DB_PERSIST_TIMEOUT_SEC` (2 s) — as under swap — puts the tenant's session store in a
`DB_COOLDOWN_SEC` (60 s) cooldown, in which the API refuses a caller-supplied session id it
cannot verify: 503 «Session store temporarily unavailable». The live client (the series' test
client, `tools/live_runner.py`) sent every question a new id of its own; the web chat sends none on a conversation's first question, so a new
visitor is not refused. A returning visitor whose session the API no longer holds in memory
(after a restart) would be, for up to 60 s. Fail-closed on purpose (tenant isolation); not
changed. Since `cf25593` the client asks as the web chat asks a first question.

**The live timing of the 4B (stand `19beeb1`).** 2026-10-16 21:27 – 10-17 01:48 UTC, at the
code defaults, `env.json`'s model choice dropped, every question sent as a conversation's first;
plan and forecasts in `cf25593`. One question: first token 198 s, result 281 s. Five: result
median 322 s (267–413 s). The thirty stopped at question 16 on HTTP 401: the client minted one
token per run, valid `JWT_ACCESS_TTL` = 3,600 s, and question 16 went 63 min in — a defect of
the test client; its 15 answers: result median 227 s. The rerun with a token per question
(`25ed888`), 30 of 30: first token median 223 s (110–381 s), result median 320 s (196–476 s).
Where an answer's time goes (medians): retrieval 134 s, of it the rerank on the CPU 102 s;
reading the 2,270-token prompt 67 s; writing at 4.2 tokens/s; the self-evaluation 68 s; the
suggested questions 13 s — and the `result` event comes only after them. The forecast held:
first questions 281, 267, 200 and 284 s against 340 s; 2 of 47 others past 400 s; none near
the stop at 3×. The forecasts came from the first stand's own 4B times, its suggestions
removed and 25 s added for the 4B's (`series_plan.json`, `forecast_basis`). All 51 answers
`auto` (49 scored 100, two 95): the live chat offered the operator to nobody, as the replay's
2 in 100 predicts — though the 51 are 30 distinct questions (each step starts at the file's
first question: the first asked four times, the next four three times, the next ten twice). The rerun's first 15 took median 291 s
against 227 s for the same 15 in the stopped run, nothing else busy on the Mac — not explained.
[Evidence row](../../EVIDENCE_INDEX.md), record `reports/chat-live-4b/19beeb1/`.

**Memory is the wall, not the ceiling.** Swap grew 600–700 MB a question in every run: 924 →
10,971 MB over the stopped thirty's 15; in the rerun 947 MB at 23:08 and 10,384 MB at 00:15,
then between 8.6 and 12.3 GB to its end, its peak 12,274 MB; back near 1 GB once the model
was unloaded. One audit write timed out under it (`Audit DB write failed … TimeoutError`, the
audit log, not the session store); no question failed. top gave llama-server — Ollama's
model runner — an 11-GB footprint, 7.6–11 GB of it compressed or swapped out (its resident
peak in the record is 3,782 MB), while `/api/ps` sized the model at 3,184,001,022 bytes. Alone, with no API (01:49–01:59 UTC, `tools/runner_memory.py`), the runner
grew from 2,977 to 5,473 MB over eight of the rerun's prompts — about 312 MB a request; a chat
answer makes three. Why it keeps the memory is not established (Ollama 0.33.2); unloading the
model frees it. A day of traffic would swap more than a thirty.

**Retrieval on the live stands is hybrid — a correction.** The previous session's log called
retrieval on the live stands vector-only, from the warning «retriever built WITHOUT BM25
index» in every run. That warning names the tenant `default`, built at startup; the questions'
tenant, `aircargo`, logs «Restored 5589 chunks … (BM25 + parent-expansion re-enabled)» at the
first question and no warning, and parent expansion ran in every question. Corrected in the
qwen3:1.7b evidence row and the ROADMAP; the index needs no rebuild.

## Julia's decisions

Verbatim, times UTC.

- 18:52: «продолжи работу. Что оцень важно понять - такущие метрики, в частности % передачи
  вопросов оператору».
- 20:52: «что-то происходит?» — answered with the state of the series.
- 2026-10-17, to the metrics report: «А не был настроен сигнал ответа человеку??? Давай
  сначала замерим. Меня очень печалит, насколько проект непродуман. Ты не можешь написать
  грамотный план?» — so the handover signal is measured before anything changes, under
  [the plan](../specs/handover-signal.md) (ROADMAP thread M, step 5).

In force from before: D12 and D11; production is `deproject-mac`; the 3,600-s ceiling and the
stop rule for every live run (3× each question's named forecast); a `human` answer gets the
operator button, not a ticket; her production model Qwen3-4B-Instruct-2507 (2026-10-16 02:11,
«Согласна с тобой»), and no SLO named.

## What was the session's choice, not hers

- Measuring the chat's rule by replaying the self-evaluation on the screening's 100 judged
  answers, not by 100 live chat questions (about 8 h of the Mac); its limits are in the row.
- The suggestions follow the answer's model (the profile's), not `OLLAMA_MODEL_NAME`.
- Not publishing the first series; rerunning on `19beeb1` with the stand fixed — the
  supervisor drops `env.json`'s model choice, the client sends no session id.
- After the 401 at question 16 of the second thirty (a token per run, 3,600 s), a token per
  question and a rerun of the thirty alone (`rerun_plan.json`, `25ed888`) rather than the
  whole series: each step runs on a fresh API.
- Forecasts 340 s and 400 s from the first stand's 4B-only times.
- Correcting the published qwen3:1.7b row's "vector-only".

## Waiting on Julia

1. **The reading of the handover plan** — the session's proposal stands unless she changes it
   before the pilot's `plan.json` is committed. Answered on 2026-10-17: measure first. The
   session's recommendation of 2026-10-16 — replay the widget's rule on the screening's
   answers — is withdrawn: those answers cite no `[N]`, so the claim check refuses them all.
2. **The push** of `e81f0c5..` HEAD — `26fcb4a` and this session's commits.
3. **GitHub billing:** CI starts no job until the account's payment or spending limit is
   fixed; only she can.
4. **An SLO** — none named and none proposed; the measured whole answer, median about
   300 s, is where one would start.

## The next session's order

1. Step 5 of the ROADMAP, [the handover plan](../specs/handover-signal.md): the pilot on
   the rerun's 30 answers (the judge's adapter, the signal tool, the reading frozen in its
   `plan.json`), then the other 70 answers, their verdicts and signals, the result on 100.
2. Step 6: fewer rerank candidates (20 reranked to 5 today), measured live as in this
   record and for quality as phase Q measures it; the count and the quality measure named
   in its plan. Julia agreed to this lever on 2026-10-16; it waits for the Mac, which
   takes one measurement at a time.
3. Before any series longer than thirty, or a day of traffic: why Ollama's model runner
   grows about 312 MB a request. `tools/runner_memory.py` of the record repeats the check
   in ten minutes on an idle Mac, stdlib only, reading its prompts from the stand
   (`/Users/julia/RAG_new_chat_19beeb1/chatlive/runs/qwen3-4b-instruct-q30-r2/prompts`):
   `ssh deproject-mac /Users/julia/RAG_Support_Assistant/.venv/bin/python - < <the file>`.
   `ollama serve` (pid 12377) is not the session's: changing its environment means
   restarting it, which waits for Julia's word, as any new install does.

## Do not

- Publish the first series (`/Users/julia/RAG_new_chat_7a99c45/chatlive/runs`): the 7B wrote
  its suggestions.
- Trust a live stand's model before reading `effective_settings.json` (`ollama_model_name`)
  and the Ollama runners in `resources.jsonl` after its first question.
- Run tests or anything heavy on the Mac while a live series runs.
- Read, print or copy `.ask100-runtime/env.json`.

## Lessons

1. **A docstring is not a check.** The supervisor said «without MODEL= nothing is overridden»;
   `env.json` overrode the model. The settings and the runner sizes said so at once — read
   after the stop, not before the series.
2. **A clean environment hides a second setting.** The E2E test of `7a99c45` ran with no model
   in the environment, where both settings agree; the defect needed a pinned one.
3. **Read which tenant a log line names.** "WITHOUT BM25" was the startup tenant's; the
   questions' tenant had BM25.
4. **A test client sends what the real client sends, and outlives the run.** Own session ids
   met a refusal no visitor meets; one token per run expired at 60 min.
5. **Watch memory as well as the clock.** The forecast held while swap reached 12 GB: the
   times alone would not have shown the wall a longer run meets.

## Glossary

- **Stand** — a `git archive` of one commit on the Mac, with the 5,589-chunk index linked
  in from the ask100 runtime (`.ask100-runtime`, an earlier measurement's environment and
  data); its `chatlive/` holds the tools and the runs.
- **Live supervisor / live client** — `tools/live_supervisor.py` starts a fresh API (a
  new process, no model loaded) per step at the code defaults and records it;
  `tools/live_runner.py` sends the questions as the web chat does.
- **One, five, thirty / the thirty** — a step's question count, the first 1, 5 or 30 of
  `evaluation/curated_cases_aircargo.jsonl` in file order; each step on a fresh API.
- **Generator screening** — candidate models answering the labelled cases over fixed
  contexts retrieved once (the phase-C generator benchmark's), for the judge: 30 cases on
  2026-10-14, 100 from 2026-10-15 ([spec](../specs/small-generator-screening.md)).
- **Route replay** — the chat's self-evaluation sent for answers already written and judged;
  measures the routing rule without regenerating answers.
- **Judge** — the session's model grading an answer `good` / `partial_ok` / `bad` against the
  question, the context and a reference (`scripts/generator_answer_judge.py`).
- **`auto` / `human`** — the route of an answer: shown as is, or marked for a person.
- **Grounding / claim check** — the graph's `verify_facts`: atomic claims of the answer, each
  checked against the context.
- **Provider profile** — `local-first` in `config/providers.yml`: the models the provider
  runtime builds; `OLLAMA_MODEL_NAME` is a separate, older setting.
- **Session-store cooldown** — 60 s in which a tenant's database paths are skipped after a
  failure.

## Log

UTC.

- 18:52 Julia's question. 19:11 `7a99c45` (the 4B the code default, E2E red on `26fcb4a`) and
  `da134d4` (the replay's and the live series' tools and plans, named before the runs).
- 19:12–20:12 the route replay: the chat's self-evaluation on the 4B's 100 judged answers.
- 20:12–21:12 the first live series, stand `7a99c45`: the thirty stopped at question 2 on the
  503; the runner sizes and `effective_settings.json` showed the 7B loaded for the suggestions.
- 21:26 `19beeb1` (the suggestions follow the answer's model, red on `da134d4`) and `cf25593`
  (the second stand's tools, `series_plan.json` named 21:26:32).
- 21:27–23:07 one, five and thirty on stand `19beeb1`; the thirty stopped at question 16 on the
  401 (23:06:52).
- 23:08 `25ed888` (a token per question, `rerun_plan.json` named 23:08:29); 23:08:39–01:48 the
  rerun, 30 of 30.
- 01:49–01:59 the runner alone (`tools/runner_memory.py`); notes written into each run; the
  export to `reports/chat-live-4b/19beeb1/`.
- 02:00–02:30 the record's test, its evidence row, the status files and this log; the gate.

## Verification

On the Mac, the gate checkout synced from the working tree (head `25ed888`, tree
`b3430dd50a`, 02:06 UTC), `remote.py --site pytest`:

- the record's and the session's tests — `test_chat_live_4b_artifact.py`,
  `test_chat_live_qwen3_artifact.py` (its row corrected), `test_chat_route_replay_artifact.py`,
  `test_production_model_default_e2e.py` — and the three docs tests: 43 passed;
- the whole unit suite, `tests/ --ignore=tests/integration`: 5,820 passed, 123 skipped, 516 s;
- bandit with CI's command: no medium or high finding.

On the laptop: CI's two mypy commands, no issues (159 and 32 files); pip-audit with CI's flags
on `requirements.lock`, no known vulnerability (5 ignored by CVE id, as CI does); DEP-01 PASS;
`ruff check` and `ruff format --check` on the new test. After this log's last edits: a re-sync
and the docs tests and the record's test again, passed. Out of reach: CI itself (billing), the
docs-site build, and the suite on the lock's exact pins — the Mac venv is not built from it.
