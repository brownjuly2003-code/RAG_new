# Session handoff — 2026-10-15 — Julia's decisions on the chat, and the next session's order

Session `ef96201d`, continued, 2026-10-15 15:59–17:50 UTC, Claude Opus 5.5 alone (D12). The
part before it, the same day: [the judge on all 100 cases](session-handoff-2026-10-15-judge-100.md).
**Pushed at Julia's word at 16:17:40:** `c3f0fff..8850d6a` — the judge's extension, its record
`judge-100/`, the 503 fix (`54ffdb2`) and the corrections of their records; CI on `8850d6a` is
green (run 38767774555). This part changed no code and ran no measurement. Its documents are in
two commits: `9698e54`, pushed at her word at 17:19:06, and the one that records her answers of
17:15, which waits for her word.

**Continued in** [the 2026-10-16 log](session-handoff-2026-10-16-chat-steps-1-3.md): steps
1–3 done and pushed, and her production model, Qwen3-4B-Instruct-2507.

## What matters to understand

**Where the product stands.** Production is `deproject-mac` (Julia, 2026-10-14: «прод на
маке»). Under the code-default limits (request 30 s) the web chat answers no question there: no
local model finishes in time — the CPU rerank alone takes about 27 s, and reading the prompt
takes the 7B about 2 minutes. With the limits raised the whole answer takes a median 486 s
(qwen2.5:7b), 297 s (Qwen3-4B-Instruct) or 100 s (qwen2.5:1.5b)
([chat log](session-handoff-2026-10-14-chat-on-mac.md),
[small models](session-handoff-2026-10-14-small-generators.md)).

**What the client sees, and who reaches an operator** — checked against the code and the
2026-10-14 records after this log's cold read; the reply of 16:06 had the first two wrong:

- *On a timeout* every measured question ended with a `result` event, not an `error`: the
  stream fails at the deadline and falls back to the whole-pipeline call
  (`api/routers/conversation.py`, from line 2505), which returns `_timed_out_state`
  (`agent/graph.py`, line 4214) — the answer «Извините, обработка запроса заняла слишком много
  времени и была прервана. Пожалуйста, повторите попытку или обратитесь к специалисту
  поддержки.», route `timeout`, quality 0. The chat shows it as an ordinary answer with the
  badges «Качество: 0» and «Маршрут: timeout» and a copy button: no «Повторить», no operator
  button on it. «Потоковая передача прервана…» with «Повторить» is what an SSE `error` event
  gets (`static/chat.inline.js`, lines 81–86 and 490–494); the measured runs sent none.
- *No route of the web chat opens a ticket.* Only `/api/ask` creates one, for `human`, `error`
  and `error_escalation` (`_TERMINAL_ESCALATE_ROUTES`; lines 1368 and 1443); the stream shows
  the route as a badge. qwen2.5:1.5b's four `human` answers left the ticket count at 94. The
  client's way to a person is the chat's own button «Связаться с оператором»
  (`static/chat.html`, line 998), which they have to press.
- *Two routing rules.* The chat's stream, with `STREAMING_RAG_PARITY` off as by default, says
  `auto` when the model's own score of its answer is at least 80 (`QUALITY_THRESHOLD`; 70 for a
  heuristic score when the model gives no number) and `human` otherwise — no relevance, no
  grounding check, no retry (`api/routers/conversation.py`, lines 2345–2352). `/api/ask` uses
  the graph's node: quality and relevance thresholds, the grounding check and retries
  (`agent/graph.py`, lines 2895–2928).

So the honest figure: in the web chat no one is handed to an operator automatically, in any
configuration. How often the model marks an answer `human`: on `/api/ask`, qwen2.5:7b 11 of 39
in a run of 2026-10-13 (28 %, Wilson 17–44 %; NOT_EVIDENCE, a patched snapshot of `7cad79f`);
in the chat, five questions a model, 0 with qwen2.5:7b, 0 with Qwen3-4B, 4 with qwen2.5:1.5b —
and five questions fit 0–43 % even at 0 of 5. These are test-set questions, not customer
traffic. The reply of 16:06 told Julia "about a quarter, 15–45 %" and that `human` reaches an
operator; the session's next reply corrects both.

**Her question, then her decisions.** At 15:58 she asked: «Какой % по переводу на оператора я
могу хотя приблизительно держать в голове? Что стоит дальше делать по проекту?» The reply
(16:06) ended with four questions: (1) push the five local commits; (2) time qwen3:1.7b in the
live chat, with the provider change it needs; (3) on a timeout, have the chat say the answer did
not come in time and offer «Передать оператору»; (4) the target answer time, to settle after the
1.7b run. At 16:12, verbatim: «Давай снимем ограничение на ограничение для ответа. Зафиксируй
все в плане по проекту, чтобы в следующей сессии все было понятно. Ответы от меня 1. да 2. да
3. да 4. Пока стоит вообще снять ограничения. Что думаешь? Я предлагаю в этой сессии никаких
тестов уже не делать, а принять основные решения и обновить доку. Что думаешь?» «Ограничение
для ответа» is read as the time limit on an answer, as her point 4 says — the session's reading.

**The session's opinion, given in reply.** Lift the limits to a ceiling rather than to none:
1,800 s for the request, the Ollama call and the stream. Every answer of the 2026-10-14 chat
runs finished under it, the slowest in 614 s; in the 2026-10-13 `/api/ask` run 5 of 39 reached
its 1,200-s limit. A ceiling makes a hung model call end and reach the operator offer of step 2.
With the limits the reranker goes to the CPU (`RAG_DEVICE=cpu`): on the Mac's 4 GB GPU it fails
on memory, and under `auto` the answer is then silently built on the unreranked order. Both were
proposals put to her; at 17:15 she agreed («2. да»). What lifting means on
this Mac: with the default qwen2.5:7b an answer takes about 8 minutes, and questions asked
together wait in one queue. It names no SLO, so the quality thread's rule — research acceptance
on the Mac is not product acceptance, no default flip before deployment target and SLO — still
holds, and the plan's product acceptance 4.2 stays undated. No tests in this part: agreed,
because the next runs measure a configuration these decisions change; CI's two mypy commands
still ran before the push, and the docs tests after the documents, as `CLAUDE.md` asks.

## Julia's decisions in force

- D12 (2026-10-04): the session does everything itself, no other model in any role, MyFlow only
  when she names it. D11: no person in the quality process.
- 2026-10-14: production is `deproject-mac`; the production model is suspended.
- 2026-10-15, 16:12: the time limits are to be lifted for now (step 1; the code still holds
  30 s) and no SLO is named; qwen3:1.7b is to be timed in the live chat with the provider change;
  on a timeout the chat is to offer the operator; no tests in that part of the session.
- 2026-10-15, 17:15, verbatim: «Ответы 1. да 2. да 3. показывать ту же кнопку. ** В следующей
  сессии все будет понятно и по порядку действий?» — to the session's three questions: push
  `9698e54` (done, 17:19:06); the 1,800-s ceiling with the reranker on the CPU: yes; a `human`
  answer in the chat gets the same «Передать оператору» button as a timeout, not a ticket.
- A push is hers, asked each time (plan 0′.3): her «1. да» of 16:12 covered the five commits up
  to `8850d6a`, that of 17:15 the commit `9698e54`; the commit recording her 17:15 answers waits
  for her word.
- On the ROADMAP stop-list until she decides: a hosted LLM or another production model (model
  swap) and alternative rerankers.

## What was the session's choice, not hers

- Proposing the 1,800-s ceiling instead of no limit, and `RAG_DEVICE=cpu` with it; since 17:15
  both are hers.
- The order below: she said yes to lifting the limits and to steps 2 and 3, not to an order.
- Recommending the code defaults as the place of the new limits: the repository has no
  production environment of the Mac (only `deploy/helm`), and the Mac's stands start from the
  code's values plus `.ask100-runtime/env.json`.
- Counting the self-evaluation after the answer as hers to decide: the client would see an
  answer before its verdict.
- Running CI's mypy and the docs tests in a part she asked to keep free of tests.

## Waiting on Julia

- After step 3: the production model and the SLO. Later: the self-evaluation after the answer.
- Whether production on `deproject-mac` is the "real deployment" that unfreezes the ROADMAP's
  conditional track; nothing unfreezes before her word.
- The push of the commit recording her answers of 17:15.

## The next session's order

The same five steps, with acceptance, stand in [ROADMAP](../../../ROADMAP.md#active). What each
needs:

1. **Lift the time limits (rule (a)).** Recommended in the code defaults: in
   `config/settings.py` `REQUEST_TIMEOUT_SEC` (30, line 1201), `OLLAMA_REQUEST_TIMEOUT_SEC` (60,
   line 1183) and `STREAMING_TIMEOUT_SEC` (120, line 746); `.env.example` (lines 210–214); the
   rows of `docs/CONFIGURATION.md` (lines 17, 125 and 126). The `getattr` fallbacks that repeat
   the old values (`api/routers/conversation.py` lines 459, 1096, 1105, 1652, 1733, 2176 and
   2236; `agent/graph.py` line 519; `llm/providers/runtime.py` line 55) apply only when the
   settings object lacks the field: bring them in step, so no reader takes them for the served
   value. `RAG_DEVICE` (`auto`, settings line 469, `.env.example` line 71; `CONFIGURATION.md`
   has no row for it): `cpu` is what the 2026-10-14 runs measured — the embedder and the
   reranker both on the CPU, vector search 0.2 s; an `auto` that keeps only the reranker off
   MPS is unmeasured. The session picks and says why. Grep the tests that pin the old defaults
   first (`tests/test_ollama_timeout.py` pins 60). The live tools put the old values back in
   their `prod` mode (`STANDARD` in `reports/chat-live/33d4b42/tools/live_supervisor.py`,
   line 46, and in its small-model copy, line 51): change it in the next run's tools. The
   Mac's `.ask100-runtime/env.json` may set these four; never read it — check the values the
   API serves in the run's recorded `settings`. Proof, red on `8850d6a`, no environment set:
   an E2E test through `/api/ask/stream`, the web chat's path, in which a fake model's answer
   slower than the largest old limit (120 s, so about two minutes of test time) arrives
   instead of `timeout` — or one test per limit — and a check that the reranker runs on the CPU
   by default. One row in `EVIDENCE_INDEX.md`, as the 503 fix has.
2. **Offer the operator on a timeout and on `human` (rule (a)).** Handle the `result` whose
   route is `timeout` — the apology above, rendered by `static/chat.inline.js` lines 546–579 —
   and the `error` events (lines 490–494; the server sends them with `route: "timeout"` at
   lines 1816, 1950 and 2099 of `api/routers/conversation.py`): say that the answer did not
   come in time and offer «Передать оператору» beside «Повторить». A `result` routed `human`
   gets the same button and no ticket (Julia, 17:15). The button can reuse the operator flow
   behind `escalateBtn` (`static/chat.html` line 998; `static/chat.inline.js` from line 363,
   its request to `/escalate` at line 382). The browser test drives both through the real
   stream — a slow fake model that reaches a deadline during generation under a short limit
   the test sets (after step 1 the default is 1,800 s), not an injected event, and one that
   scores its answer below 80 — and runs with `-rs`:
   `tests/test_widget_e2e_playwright.py`, the precedent, skips without Playwright or Chromium,
   and a skip is NOT_EVIDENCE. The widget (`static/widget.inline.js`, line 185) calls `/api/ask`,
   not the stream: check what its timeout shows. One row in `EVIDENCE_INDEX.md`.
3. **Thinking off, then qwen3:1.7b in the live chat (rule (a), then (c)).** Pass
   `reasoning=False`, for models that can think, where every builder meets:
   `_instantiate_with_timeout` (`llm/providers/ollama.py`, line 29), used by the provider's whole
   answer (line 141), its tool calls (`ChatOllama`, line 201), its stream (line 293) and,
   through `_instantiate_local_ollama` (`agent/graph.py`, line 490), the graph's own model
   (suggested questions and the graph fallback). First check what
   Ollama 0.33.2 does with `think: false` for qwen2.5:7b, which cannot think (`capabilities` in
   `/api/show`). That qwen3:1.7b thinks on this path:
   `reports/chat-live-small/33d4b42/tools/think_probe.out`. An E2E test that reads the payload.
   Then the live run at the new limits, as on 2026-10-14: the tools in
   `reports/chat-live-small/33d4b42/tools/`, the supervisor's `MODEL=`, a free port before each
   supervisor, the supervisor detached from ssh from its first launch; 1 → 5 → 30 questions —
   the five of 2026-10-14 first (their case ids are in its `runs.json`), all 30 named before the
   first question. Expect about 1.5–2 min a question (qwen2.5:1.5b took 100 s, the rerank 49 s
   of it), so 30 take about an hour. Count the time (first token, whole answer, stages), the
   rerank's status (the small-model tools do not keep `reranker_ok` yet) and the routes; pin the
   code SHA, the index, the model digest and the served configuration; a record beside the
   2026-10-14 ones, its test, one evidence row. The judge's bad answers do not predict the
   chat's `human`: Qwen3-4B (12 bad) and qwen2.5:7b (15) both gave 0 of 5. The 7B has only
   those five questions in the chat; a 7B run on the 30 would take about 4 h.
4. **Julia decides on those numbers:** the production model and the SLO.
5. **Then the speed levers, one at a time, each measured:** fewer rerank candidates (not another
   reranker), a shorter prompt (the 7B reads its 2,258 tokens in about 2 minutes), and — hers to
   decide — the self-evaluation after the answer is shown (122 s with the 7B, today before the
   answer's verdict).

The quality thread resumes after this one (the ROADMAP's WIP limit: one thread); its open items
stand as CURRENT_STATE lists them.

**The gate** for any change — the laptop's git-ignored scripts ship the working tree to the
Mac's gate tree and run pytest there:
`MSYS_NO_PATHCONV=1 timeout 600 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/.tmp/mf-mac/sync.py`,
then
`MSYS_NO_PATHCONV=1 timeout 1100 C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <tests> -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`.
Before asking for a push: the whole unit suite (`tests/ --ignore=tests/integration`, about
7 min, in the background); CI's two mypy commands (laptop) and bandit (Mac) exactly as
`.github/workflows/ci.yml` gives them (lines 136–137 and 278); pip-audit with its flags
(lines 280–307; `uvx` on the laptop); the docs site's npm audit and DEP-01
(`tests/test_docs_site_npm_audit.py`, `tests/test_npm_audit_floors.py`). No pytest on the
laptop.

## Do not

- Push, swap the production model, call a hosted model or another reranker, or move the
  self-evaluation after the answer without Julia's word.
- Report a run without the configuration it served, or a skipped browser test as a pass.
- Run tests on the laptop; read, print or copy `.ask100-runtime/env.json`; kill processes you
  did not start on the Mac; install anything there with brew; rebuild the 5,589-chunk index;
  touch `demo/phase-e-raw.webm` or `reports/ask100/`.

## Lessons

1. **Read the client's path in the records before describing it.** The reply of 16:06 took the
   chat's branch for an SSE `error` event as what a timeout shows, and the routes of
   `_TERMINAL_ESCALATE_ROUTES` as tickets the chat opens. The records' events (`status`,
   `token_start`, `result`) and ticket counts (94 before and after) said otherwise; the cold
   read found it.
2. **A route is a label until something acts on it.** In the chat `human` is a badge; only
   `/api/ask` turns it into a ticket.
3. **"No limit" still needs a ceiling.** On one machine with one queue, a call that never ends
   holds every later question.

## Glossary

- **Limits** — the request deadline (`REQUEST_TIMEOUT_SEC`), the Ollama call's
  (`OLLAMA_REQUEST_TIMEOUT_SEC`) and the stream's token loop (`STREAMING_TIMEOUT_SEC`).
- **Ceiling** — a limit high enough that no measured chat answer reaches it (1,800 s against the
  slowest 614 s), kept only to end a hung call.
- **Route** — the verdict on a question: `auto` (answered), `human` (a person should answer: a
  ticket on `/api/ask`, a badge in the chat), `timeout` (no answer in time; the chat shows an
  apology), `error`.
- **Stream and `/api/ask`** — the web chat calls `/api/ask/stream`, which sends tokens as they
  come; `/api/ask` returns the whole answer at once and is what the widget and the 2026-10-13
  run used.
- **SLO** — the answer time production promises (plan D5); not named.

## Log

All times UTC, 2026-10-15.

- 15:58 her question; 16:06 the reply, from the 2026-10-14 records' routes and a reading of the
  web chat's error branch (wrong, Lessons 1).
- 16:12 her decisions. 16:15 CI's two mypy commands on `8850d6a`: no issues (32 and 159 files).
  16:17:40 push `c3f0fff..8850d6a`; docs site run 38767774528 succeeded (build passed, deploy
  skipped on the private repository); CI run 38767774555 succeeded at 16:32:22.
- The documents: ROADMAP (the order, phase M, the Q row, a line under Conditional track),
  CURRENT_STATE, AGENT_STATE, BACKLOG, the D5 row of [`plan_03_10_26.md`](../specs/plan_03_10_26.md),
  this log, and in the judge's log its push status, next steps and ticket sentence.
- 16:26–16:45 a cold read of the documents by a subagent on the session's model: 2 high, 7
  medium and 6 low findings. The two high ones — what a timeout shows and the chat's tickets —
  were checked against the code and the records and corrected here; the rest applied.
- 16:53–17:00 the corrections elsewhere: ROADMAP (what a timeout shows, what she said yes to,
  steps 1–3, row M, the line under Conditional track), CURRENT_STATE (the operator share, CI on
  `8850d6a`), BACKLOG (two stale lines: 1.3d with the external bases, and B.4's human grades,
  which D11 rules out), the D5 row and the judge's log (its ticket sentence). Then the docs
  tests on the Mac (Verification) and a local commit; no push.
- Then the reply to her; 17:15 her answers (decisions above). 17:19:06 push `8850d6a..9698e54`.
  Then her answers in ROADMAP, CURRENT_STATE, AGENT_STATE, BACKLOG, the D5 row and this log,
  and a read of the documents as the next session would start them, by a subagent on the
  session's model (Verification).
- 17:29:11 CI on `9698e54` succeeded (run 38776325555; docs site run 38776325603, 17:20:24).
- The read as the next session would start, on `92a088d` (about 11 minutes): nothing blocking —
  it named the first action, the order and her decisions as written — and eight minor
  findings, checked against the files. Applied: the `STANDARD` line, the `RAG_DEVICE` choice,
  step 1's proof for all three limits with the `getattr` fallbacks, step 2's short test limit,
  the evidence rows, the pre-push commands, and CURRENT_STATE's "read it first" on the
  2026-10-06 log, now for the quality thread. Left: two wordings that change no work
  (AGENT_STATE's paragraph on the plan of 2026-09-06; ROADMAP's two phrasings of the no-flip
  rule). The fixes went into the same local commit.

## Verification

- Before the push: CI's two mypy commands on `8850d6a`, no issues; the judge's log records the
  whole unit suite on its last revision: 5,794 passed, 121 skipped. CI on `8850d6a`: success.
- `9698e54`'s tree, on the Mac: the three docs tests and every test that reads a changed file
  (`test_backlog_docs`, `test_gr2_artifact`, `test_gr_bucket_baseline`, `test_precommit_config`,
  `test_session_turn_wiring`, `test_transformers_cve_floor`, `test_autopilot_runner`): 110
  passed, 9 skipped — the nine are `autopilot.ps1` tests, which need Windows PowerShell 5.1.
  Line caps: CURRENT_STATE 140 of 150, AGENT_STATE 119 of 120, BACKLOG 59 of 60. Before its
  push, the 30 further test files that scan the docs folders: 936 passed, 3 skipped. CI on
  `9698e54`: success.
- The second commit's tree, on the Mac: the same 40 test files, 1046 passed, 12 skipped (the
  nine `autopilot.ps1` tests and three of the 30).
