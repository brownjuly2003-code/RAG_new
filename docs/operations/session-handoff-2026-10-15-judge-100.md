# Session handoff — 2026-10-15 — the judge on all 100 cases

Session `ef96201d`, continued after a context compaction, 2026-10-15 10:45–15:30 UTC, Claude
Opus 5.5 alone (D12). Commits: `30b1469` (the extension registered; the judge's sample size and
reuse step), `5861ffb` (its amendment: the user's CLI plugins off) and the commit with this text
(the record `judge-100/`, its test, the evidence row). **Pushed at Julia's word at 10:53:52:**
`a7bf232..c3f0fff`, the four CI fixes and the previous log; the three commits above are local.
The session before, on the same day: [session log](session-handoff-2026-10-14-small-generators.md)
(the screening on 30 cases, the red CI and its fixes).

## What matters to understand

**Julia's message of the day**, verbatim: «а какой сейчас % эскалации на оператора? По
вопросам: 1. Да  2. Да. 3. Это стоит сделать? Нужно твое мнение». It answers the three
questions of the 10:45 report: (1) push the six local commits — done at 10:53:52, CI green;
(2) extend the judge to all 100 cases, «Минимальный набор — Qwen3-4B-Instruct, 7B, 8B; можно
добавить qwen3-1.7b», 225–295 requests, ~$24–31, ~2.7–3.5 h — done, this log; (3) time
qwen3:1.7b in the live chat, which needs the production provider to send `think: false` — she
asked for the session's opinion; there is no decision, and the provider stays as it is.

**The escalation rate, as answered.** No reliable rate exists. Under the code-default limits
(30 s a request) every question ends as route `timeout`, and a ticket opens only for the routes
`human`, `error` and `error_escalation` (`_TERMINAL_ESCALATE_ROUTES`,
`api/routers/conversation.py`): on `timeout` the user gets an error and no operator learns of
it. The one sample above five questions is a run of 2026-10-13 that is not ours
(`reports/ask100/fixed-20261013/`, untracked; qwen2.5:7b, limits 1,200 s, `/api/ask`, broken
off at 39 of 100): auto 23, human 11 — 28 %, 95 % interval about 16–44 % — and timeout 5. The
live chat of 2026-10-14, five questions a model: qwen2.5:7b 0 of 5 to `human`, Qwen3-4B 0 of
5, qwen2.5:1.5b 4 of 5. The route is the generator grading its own answer against
`QUALITY_THRESHOLD` 80 (`config/settings.py`), so a model swap moves it too.

**The opinion on question 3, given before the run:** decide after the judge on 100 cases;
timing qwen3:1.7b in the chat is worth the provider change only if it stays at the 7B's level
there. That is why qwen3-1.7b joined the extension.

**How the judge works.** `scripts/generator_answer_judge.py` freezes a plan — one request per
answer: the rules, the question, the context the generator saw and its seed-42 answer, never
its name — and sends each request to claude-opus-5-5 at effort max in a stateless CLI session
(`evaluation/isolated_request.py`). A reply counts only as one JSON verdict from a session
record that loaded nothing (no tool, plugin, MCP server, skill, memory or hook) and only for a
planned request (its message hash). A verdict gives a class: **good**, **partial_ok** or
**bad** (Glossary). The extension's plan holds 415 requests (4 generators × 100 cases and 15
retests); 123 of them were byte-identical to requests of the 30-case plan, so their published
verdicts were copied (`reuse`), and 292 were sent.

**What the 100 cases show** (`reports/generator-screen/86df582/judge-100/`, EVIDENCE_INDEX):

| Generator | good / partial_ok / bad | good, 95 % Wilson | supported claims | answers with an unsupported claim |
|---|---|---|---|---|
| qwen3-1.7b | 50 / 27 / 23 | 0.40–0.60 | 0.92 | 17 |
| Qwen3-4B-Instruct | 67 / 21 / 12 | 0.57–0.75 | 0.95 | 11 |
| qwen2.5-7b (C.1a, the code default) | 56 / 29 / 15 | 0.46–0.65 | 0.96 | 12 |
| qwen3-8b (C.1b) | 66 / 29 / 5 | 0.56–0.75 | 0.98 | 3 |

Of the six pairs, registered as apart only below 0.05 / 6: qwen3-1.7b is behind
Qwen3-4B-Instruct (4 against 21 cases where only one of the two is good, p 0.001) and behind
qwen3-8b (3 against 19, p 0.001); it is not told apart from qwen2.5-7b (13 against 19,
p 0.38). Qwen3-4B-Instruct and qwen3-8b are not told apart (7 against 6). Qwen3-4B-Instruct
over qwen2.5-7b (17 against 6, p 0.035) and qwen3-8b over qwen2.5-7b (15 against 5, p 0.041)
point the same way but stay unsettled after the correction. The judge agreed with itself on 14
of 15 retests and on `context_has_answer` for all four answers in 100 of 100 cases.

**What it means for question 3.** By the criterion given before the run, timing qwen3:1.7b in
the chat is now worth it: on this judge it is not told apart from the code default, and its
benchmark generation is 15.8 s a case against the 4B's 36.7 s. Still: (a) "good" here is the
C.1 contract — the benchmark's prompt over cached retrieval — not the chat; (b) the chat answer
would still take minutes, not seconds (qwen2.5:1.5b, the nearest timed model, took a median
100 s, of it the rerank 49 s and the self-eval 24 s); (c) how qwen3:1.7b grades itself in the
chat is unknown, and qwen2.5:1.5b sent 4 of 5 to `human`. If quality is what she wants from a
small model, Qwen3-4B-Instruct is the one level with qwen3:8b, at a median 297 s a chat answer.
The provider change waits for her «да».

**Thirty cases overstated qwen3-1.7b:** 20 good of the registered 30, 30 of the other 70. The
30-case leader, Qwen3-4B-Instruct, went 23 of 30 and 44 of 70.

## Julia's decisions in force

- D12 (2026-10-04): the session does everything itself; no other model in any role; MyFlow only
  when she names it.
- Production runs on `deproject-mac` (2026-10-14); the production model is suspended («Давай
  подвесим вопрос»), and a model swap and alternative rerankers stay on the ROADMAP stop-list.
- A push is her decision, asked each time (plan 0′.3); her «Да» of this day covered the six
  commits up to `c3f0fff`.
- The 100-case extension: her «2. Да».

## What was the session's choice, not hers

- The extension's generators: the "minimal set" plus qwen3-1.7b, which the question offered;
  qwen2.5-1.5b left out (the most bad answers on 30 cases, 9, and 4 of 5 to `human` in the chat).
- The reading: Wilson intervals, six exact sign tests, apart only below 0.05 / 6.
- Reusing the 123 verdicts instead of sending them again (it saved ≈ $13).
- The amendment: a per-request override, not asking her to switch the plugin off (Lessons).
- Chunk size: two chunks of ten per call until 14:05, then one.

## Log

All times UTC, 2026-10-15.

- 10:45 report with the three questions; 10:53:52 push `a7bf232..c3f0fff` after «1. Да»; the
  docs-site deploy 38723502529 green at 10:55:31, CI 38723502525 at 11:04:04 — the site built
  on the new npm lock and the suite ran on the new Python pins for the first time.
- `--sample-size`, `reuse` and the reused count in the summary, with five tests; the
  registration in the spec ("Extension to 100 cases, registered 2026-10-15"); a dry count
  against the published record gave 415 requests, 123 reusable, 292 to send. Mac gate 57
  passed; `30b1469` at 11:08:13.
- 11:08:28 the plan frozen in `.tmp/genscreen-judge-100/`, 123 verdicts copied; 11:13 probe:
  five-hour window 0.31, weekly 0.24.
- 11:09–12:05 requests 1–69, all valid.
- 12:04:52 the marketplace `claude-plugins-official` added and 12:05:00 the plugin
  `figma@claude-plugins-official` installed and enabled for the user — not by the session.
  The 70th request, sent just after, was refused (`cli_response`), and so was its repeat at
  12:07:10 through a wrapper that keeps the refusal's message: "the session loaded more than
  the request: plugins". Two trivial probes: as is, the session loads `figma` and the route
  refuses; with `--settings` disabling the configuration's two plugins it holds the three
  registered built-ins and nothing else, and the route accepts ($0.003).
- 12:13:15 `5861ffb`: the amendment, the wrapper and the settings file published in the record
  and pinned (gate 57 passed); the run resumed through the published wrapper.
- 14:05:04 the second chunk of a call ran out of its time budget, and `timeout` killed the
  request in flight (CLI exit 143, row `5c20ead02f1e39b1` `cli_exit`, sent again); one chunk a
  call from then on.
- 15:06:24 the last of the 292 requests; 15:10 probe: five-hour 0.51 (reset 18:10), weekly
  0.33 (reset 2026-10-20 22:00).
- The record published with LF, its test extended, the evidence row, the spec's status,
  CURRENT_STATE and this log.

## State and next actions

The record `judge-100/` is complete and pinned: `plan.json`, `verdicts.jsonl` (418 rows: 123
copied first, then 292 sent with a verdict and 3 without — the 70th request refused twice, the
request killed at 14:05), `summary.json`, `refusals.log` (two lines; the first refusal predates
the wrapper) and `tools/` (the wrapper, the settings file). The working files stay git-ignored
in `.tmp/genscreen-judge-100/`. `judge-100/` sits inside the screening's record, as
registered; the record's test finds each evidence row by its exact link, not by a substring.
Nothing runs on the Mac or the laptop. Untracked and not ours: `demo/phase-e-raw.webm`,
`reports/ask100/`.

**What it cost.** 292 requests: $30.95 at API prices and 13,090 s of requests — mean $0.106
and 44.8 s, median 33 s, the longest 244 s — on Julia's subscription. Wall time 11:09–15:06
with the stop at 12:05. The weekly window went from 0.24 to 0.33; the stream alone accounts
for about 0.03 at the usual rate, and the window also holds the session's work and Julia's own
(she installed a plugin at 12:05), so the split is not known.

**The commands** (laptop, focused venv): `scripts/generator_answer_judge.py plan --report
NAME=PATH … --sample-size 100 --out DIR`; `reuse --from reports/generator-screen/86df582/judge
--out DIR`; then chunk by chunk, free memory checked between them,
`MSYS_NO_PATHCONV=1 PYTHONPATH=D:/RAG_new timeout 1150 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -X utf8 D:/RAG_new/reports/generator-screen/86df582/judge-100/tools/run100_logged.py 10`;
`summary --out DIR`. The scratch scripts `.tmp/genscreen/analyze100.py` (the registered
reading) and `.tmp/genscreen/publish_judge100.py` (LF copies and pins) are git-ignored.

**The gate** as in the previous log: `.tmp/mf-mac/sync.py` ships the working tree (or
`.tmp/ask100-split/sync_commit.py <rev>` one commit) to the Mac's gate tree, then
`.tmp/mf-mac/remote.py --site pytest <tests> …`.

Next, in order:

1. **The 503 inside a started stream** — still the one rule-(a) slice that needs no word of
   hers; the previous log's step 1 has the plan and the ROADMAP caveat.
2. **Julia's answers:** the push of `30b1469`, `5861ffb` and the commit with this text; question
   3, timing qwen3:1.7b in the chat (the session's opinion: now worth it, see above). Act on
   each only after her «да».
3. If she says yes to question 3: send `think: false` for qwen3 models through the provider
   (`reasoning=False` for `OllamaLLM` in `llm/providers/ollama.py`, and the chat's streaming
   path), checked against qwen2.5, with an E2E test; then the chat on the Mac as on 2026-10-14
   with 20–30 questions, to count the routes to `human` as well as the time.

**Waiting on Julia** (no step until she speaks):

- The production model and the SLO. Whole chat answer, limits raised: qwen2.5:1.5b 100 s,
  Qwen3-4B 297 s, qwen2.5:7b 486 s; qwen3:1.7b untimed.
- The levers beyond the model: the rerank (alternative rerankers are on the stop-list), the
  self-eval call after the answer, the limits.
- Optional, a slice of its own: make the isolated route disable the user's plugins itself,
  so a plugin she installs cannot stop a judge again (Lessons, 1).

## Do not

- Change Julia's Claude configuration (`~/.claude/settings.json`, installed plugins) to
  unblock a route: override per request and record it.
- Run more than one chunk under one time budget: its `timeout` kills the request in flight.
- Treat the benchmark's "good" as the chat's.
- Push, change the provider for qwen3:1.7b, or swap the default model without her word.
- Run tests on the laptop; read, print or copy `.ask100-runtime/env.json`; kill processes you
  did not start on the Mac; install anything there with brew; rebuild the 5,589-chunk index;
  touch `demo/phase-e-raw.webm` or `reports/ask100/`.

## Lessons

1. **A plugin from the official marketplace loads into a `--safe-mode` session.** `figma`
   did at 12:05; `codex@openai-codex`, from a directory marketplace and enabled since April,
   loaded in no earlier session of the route. The route's own check refused the first such
   reply, so no verdict came from a dirty session. When the route refuses with "loaded more
   than the request", read the `plugins` of the session's init event, and override per
   request.
2. **A row keeps only a refusal's code.** The cause took a wrapper that writes the message;
   keep it from the first request.
3. **A time budget kills the request in flight.** One chunk of ten per call (4–13 min) fits
   `timeout 1150` with room; two did not, once.
4. **Thirty cases mislead in both directions** (above). The registered rule — gaps of five or
   fewer unresolved, so extend — is what caught it.
5. **Count before registering.** The dry plan against the published record gave the exact
   numbers the registration states (415, 123, 292).

## Glossary

- **good / partial_ok / bad** — good: a full answer with every claim supported by the context
  and no defect, or a decline where the context holds no answer; partial_ok: a partial answer,
  every claim supported, no defect; bad: everything else.
- **Wilson interval** — the 95 % interval of a share; at 50 of 100 it is 0.40–0.60.
- **Exact sign test** — on the cases where only one of two generators is good (McNemar's exact
  test); "apart" means p < 0.05 / 6 over the six pairs, otherwise "not told apart".
- **Reuse** — copying a verdict of the 30-case plan whose request is byte-identical (same item
  id and message hash); each copy carries that plan's SHA-256 in `reused_from`.
- **Route refusal** — `JudgeUnavailable`: `cli_response` (the reply or its session is not
  vouched for), `cli_exit` (the CLI exited non-zero); the run stops at the first.
- **`--safe-mode`** — the CLI flag meant to load no instruction file, memory, hook, skill,
  plugin or MCP server; see Lessons, 1.

## Verification

- Mac gates: `c3f0fff`, six tests, 45 passed (owed from the previous log); `30b1469`, the
  judge's and the record's tests 34 passed, with the three docs tests 57; `5861ffb`, 57; the
  commit with this text, the same set and the two chat records' tests, 75 passed.
- CI on `c3f0fff`: CI 38723502525 success; Deploy docs site 38723502529 success.
- The record's test rebuilds the 100-case plan from the tracked inputs, checks that the 123
  copies equal the published rows, rebuilds the summary from the verdicts and recomputes every
  number of the evidence row, the sign tests included.
