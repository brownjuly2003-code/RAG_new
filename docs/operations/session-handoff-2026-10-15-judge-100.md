# Session handoff — 2026-10-15 — the judge on all 100 cases

Session `ef96201d`, continued after context compactions, 2026-10-15 10:45–16:04 UTC, Claude
Opus 5.5 alone (D12). Commits: `30b1469` (the extension registered; the judge's sample size and
reuse step), `5861ffb` (its amendment: two CLI plugins of the user's configuration off),
`928c124` (the record `judge-100/`, its test, the evidence row), `54ffdb2` (the 503 inside a
started stream, fixed) and the commit with this revision (the cold read's corrections, the
503's records). **Pushed at Julia's word at 10:53:52:** `a7bf232..c3f0fff` — `384f7df` (the
30-case verdicts the extension reuses), the four CI fixes and the previous log; the five
commits above are local. The same session before this part, the same day:
[session log](session-handoff-2026-10-14-small-generators.md) (the screening on 30 cases,
the red CI and its fixes).

## What matters to understand

**Julia's message after the 10:45 report**, verbatim (her first of the day, «1. Да  2. Да.
3. Давай решим это позже», is in the previous log): «а какой сейчас % эскалации на
оператора? По вопросам: 1. Да  2. Да. 3. Это стоит сделать? Нужно твое мнение». It answers
the three questions of the 10:45 report: (1) push the six local commits — done at 10:53:52,
CI green; (2) extend the judge to all 100 cases, «Минимальный набор — Qwen3-4B-Instruct, 7B,
8B; можно добавить qwen3-1.7b», 225–295 requests, ~$24–31, ~2.7–3.5 h — done, this log;
(3) time qwen3:1.7b in the live chat, which needs the production provider to send
`think: false` — she asked for the session's opinion; there is no decision, and the provider
stays as it is.

**Why the extension ran.** On the registered 30 cases the leading small generator,
Qwen3-4B-Instruct, came within five good answers of C.1a and C.1b (23 against 20 and 21);
the [plan's reading](../specs/small-generator-screening.md#reading) calls such gaps
unresolved and extends the judge to all 100 cases
([extension](../specs/small-generator-screening.md#extension-to-100-cases-registered-2026-10-15),
[its amendment](../specs/small-generator-screening.md#amendment-of-the-extension-2026-10-15);
the record's row in [EVIDENCE_INDEX](../../EVIDENCE_INDEX.md) is the one linking `judge-100/`).

**The escalation rate, as answered.** No reliable rate exists. Under the code-default limits
(30 s a request) every question ends without an answer — route `timeout`, or, in the 4B's
run, a stream cut by a 503 (fixed since, `54ffdb2`) — and a ticket opens only for the routes
`human`, `error` and `error_escalation` (`_TERMINAL_ESCALATE_ROUTES`,
`api/routers/conversation.py`): on `timeout` the user gets an error and no operator learns of
it. The one sample above five questions is a run of 2026-10-13 that is not ours
(`reports/ask100/fixed-20261013/`, untracked; qwen2.5:7b, limits 1,200 s, `/api/ask`, broken
off at 39 of 100), its code a patched snapshot of `7cad79f`, the patched files known only by
their hashes — no commit names what ran: NOT_EVIDENCE. It gave auto 23, human 11 and
timeout 5: `human` 11 of 39, 28 %, 95 % Wilson 16.5–43.8 %. The live chat of 2026-10-14,
five questions a model: qwen2.5:7b 0 of 5 to `human`, Qwen3-4B 0 of 5, qwen2.5:1.5b 4 of 5.
The chat's route is the generator grading its own answer against `QUALITY_THRESHOLD` 80
(`config/settings.py`), so a model swap moves it too.

**The opinion on question 3, given before the run:** decide after the judge on 100 cases;
timing qwen3:1.7b in the chat is worth the provider change only if it stays at the 7B's level
there. That is why qwen3-1.7b joined the extension. "The 7B's level" was never made precise
— the spec registers only whether "its answers hold" — so the reading below is the
session's, not the plan's.

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
both favour the Qwen3 model over the code default but stay unsettled after the correction.
The judge agreed with itself on 14 of 15 retests and on `context_has_answer` for all four
answers in 100 of 100 cases.

**What it means for question 3.** qwen3-1.7b is not shown to differ from the code default at
this sample, and that is not parity: 6 fewer good answers (50 against 56), 8 more bad (23
against 15), 5 more with an unsupported claim (17 against 12); a paired difference anywhere
from 17 points behind to 5 ahead fits the data (95 %, Wald; not part of the registered
reading). The session's opinion, not a result: timing it in the chat is still worth the
provider change — it is the one small model never timed there, its benchmark generation is
15.8 s a case against the 4B's 36.7 s, and only the chat shows what the rerank and the
self-eval leave of that. Still: (a) "good" here is the C.1 contract — the benchmark's prompt
over cached retrieval — not the chat; (b) the chat answer would still take minutes, not
seconds (qwen2.5:1.5b, the nearest timed model, took a median 100 s, of it the rerank 49 s
and the self-eval 24 s); (c) how qwen3:1.7b grades itself in the chat is unknown, and
qwen2.5:1.5b sent 4 of 5 to `human`. If quality is what she wants from a small model,
Qwen3-4B-Instruct is not told apart from qwen3:8b on good answers (67 against 66), though it
gives more bad ones (12 against 5; the cases where only one of the two is bad, 10 against 3,
p 0.09, not registered) and more with an unsupported claim (11 against 3); a median 297 s a
chat answer. The provider change waits for her «да».

**The first 30 cases were easier for all four.** Good answers on the registered 30 and on the
other 70: qwen3-1.7b 20 and 30 (0.67 and 0.43), Qwen3-4B-Instruct 23 and 44 (0.77 and 0.63),
qwen2.5-7b 20 and 36 (0.67 and 0.51), qwen3-8b 21 and 45 (0.70 and 0.64). Against qwen2.5-7b
the gaps changed: qwen3-1.7b went from level (20 against 20) to 6 behind on the 70,
Qwen3-4B-Instruct and qwen3-8b from 3 and 1 ahead to 8 and 9 ahead.

**The 503 inside a started stream, fixed (`54ffdb2`).** `/api/ask/stream` sent its `status`
event before it looked the session up, so a refusal — 404 for a session of another tenant,
503 when the session store is in cooldown and cannot verify the caller's id — found the
response started, and the client got a 200 stream that ended after `status`. The route now
resolves the session first, and the refusal is the plain JSON error `/api/ask` returns; the
web chat already handles a 503 from it. Rule (a): `tests/test_ask_stream_session_refusal.py`,
red on `928c124` (4 of 4), green with the fix.

## Julia's decisions in force

- D12 (2026-10-04): the session does everything itself; no other model in any role; MyFlow only
  when she names it.
- Production runs on `deproject-mac` (2026-10-14); the production model is suspended («Давай
  подвесим вопрос»), and a model swap and alternative rerankers stay on the ROADMAP stop-list.
- A push is her decision, asked each time (plan 0′.3); her «1. Да» after the 10:45 report
  covered the six commits up to `c3f0fff`; the commits after it wait for her word.
- The 100-case extension: her «2. Да».

## What was the session's choice, not hers

- The extension's generators: the "minimal set" plus qwen3-1.7b, which the question offered;
  qwen2.5-1.5b left out (the most bad answers on 30 cases, 9, and 4 of 5 to `human` in the chat).
- The reading: Wilson intervals, six exact sign tests, apart only below 0.05 / 6.
- Reusing the 123 verdicts instead of sending them again (it saved ≈ $13).
- The amendment: a per-request override, not asking her to switch the plugin off (Lessons).
- Chunks per call — a call is one tool call of the session under one `timeout`: two chunks of
  ten until 14:05, then one.
- Reading "not told apart" as reason enough to time qwen3:1.7b in the chat (question 3).
- Taking the 503 inside a started stream as a slice that needs no word of hers — a reading of
  the ROADMAP freeze: no status semantics added, the direct-stream path kept — and fixing it by
  resolving the session before the stream rather than by an SSE `error` event.

## Log

All times UTC, 2026-10-15.

- 10:45 report with the three questions; 10:53:52 push `a7bf232..c3f0fff` after «1. Да»; the
  docs-site run 38723502529 green at 10:55:31 (its build passed; the deploy job is skipped on
  the private repository), CI 38723502525 at 11:04:04 — the site built on the new npm lock and
  the suite ran on the new Python pins for the first time.
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
  12:07:10 through a first, unpublished wrapper — no `--settings` yet — that keeps the
  refusal's message: "the session loaded more than the request: plugins". Two trivial probes:
  as is, the session loads `figma` and the route refuses; with `--settings` disabling the
  configuration's two plugins it holds only what the route registers as built in (`BUILTIN`
  in `evaluation/isolated_request.py`: the plugins `cc-plugin-agents-md`,
  `cc-plugin-plugin-authoring` and `cc-plugin-telemetry`, and four agent types), and the route
  accepts ($0.003).
- 12:13:15 `5861ffb`: the amendment, the wrapper and the settings file published in the record
  and pinned (gate 57 passed); the run resumed through the published wrapper.
- 14:05:04 the second chunk of a call ran out of its time budget, and `timeout` killed the
  request in flight (CLI exit 143, row `5c20ead02f1e39b1` `cli_exit`, sent again); one chunk a
  call from then on.
- 15:06:24 the last of the 292 requests; 15:10 probe: five-hour 0.51 (reset 18:10), weekly
  0.33 (reset 2026-10-20 22:00).
- The record published with LF, its test extended, the evidence row, the spec's status,
  CURRENT_STATE and this log; `928c124`.
- 15:24 the checks owed before asking for a push, on `928c124`: the whole unit suite on the Mac
  5,790 passed, 121 skipped; CI's two mypy commands, no issues; bandit with CI's command, no
  issue; pip-audit with CI's flags, no known vulnerability (5 ignored by those flags); the docs
  site's npm audit, DEP-01 PASS. Out of reach here: the site's build and the suite on the
  lock's exact pins.
- The 503 inside a started stream (the previous log's step 1): its test red on `928c124`, 4 of
  4 — a 200 stream of one `status` event — and green with the fix; `54ffdb2` at 15:36:42.
- The cold read of `928c124`, by a subagent on the session's model: every number matches; 3
  high, 8 medium and 6 low findings on reading and wording, corrected in this revision (the
  spec gets an erratum; its registered text stays).

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
and 44.8 s, median 33 s, the longest 244 s — on Julia's subscription; these are the rows with
usage, and the two refused replies, the killed request and the probes keep none, so they are
not counted. Wall time 11:09–15:06 with the stop at 12:05. The subscription's weekly usage
window — the share of the week's allowance spent, 0 to 1, which a probe request reads — went
from 0.24 to 0.33. At the rate measured on 2026-10-06, 0.01 of the week for about $10 at API
prices, the stream is an estimated 0.03; the window also holds the session's work and Julia's
own (she installed a plugin at 12:05), so the split is not known.

**The commands**, on the laptop with `PYTHONPATH=D:/RAG_new`; `py` stands for
`C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -X utf8` and `DIR` for
`D:/RAG_new/.tmp/genscreen-judge-100`, which the wrapper hard-codes as its `OUT`:

```
py D:/RAG_new/scripts/generator_answer_judge.py plan --sample-size 100 --out DIR \
  --report qwen3-1.7b=D:/RAG_new/reports/generator-screen/86df582/reports/gs-qwen3-1p7b-n100-phase-c-generator-benchmark.json \
  --report qwen3-4b-instruct=D:/RAG_new/reports/generator-screen/86df582/reports/gs-qwen3-4b-instruct-n100-phase-c-generator-benchmark.json \
  --report qwen2.5-7b=D:/RAG_new/evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json \
  --report qwen3-8b=D:/RAG_new/evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json
py D:/RAG_new/scripts/generator_answer_judge.py reuse --from D:/RAG_new/reports/generator-screen/86df582/judge --out DIR
MSYS_NO_PATHCONV=1 timeout 1150 py D:/RAG_new/reports/generator-screen/86df582/judge-100/tools/run100_logged.py 10
py D:/RAG_new/scripts/generator_answer_judge.py summary --out DIR
```

The wrapper's line is one chunk of ten, one per call, free memory checked between calls. The
names and their order are the record test's `EXTENDED` (its `SCREENED` and `REFERENCE` give
the reports): an item's id hashes its name, so other names break the reuse. `--contexts`
defaults to the git-ignored `.tmp/ab_candidates_phase2_C.json`, which must be the gunzipped
`evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz` (SHA-256 `91ce1745…`, as it is on this
laptop). The scratch scripts `.tmp/genscreen/analyze100.py` (the registered reading) and
`.tmp/genscreen/publish_judge100.py` (LF copies and pins) are git-ignored.

**The gate** as in the previous log: `.tmp/mf-mac/sync.py` ships the working tree (or
`.tmp/ask100-split/sync_commit.py <rev>` one commit) to the Mac's gate tree, then
`.tmp/mf-mac/remote.py --site pytest <tests> …`.

Next, in order:

1. **Julia's answers:** the push of `30b1469`, `5861ffb`, `928c124`, `54ffdb2` and the commit
   with this revision (the checks before asking: Log and Verification); question 3, timing
   qwen3:1.7b in the chat (the session's opinion: worth it, see above — a reading of its own).
   Act on each only after her «да».
2. If she says yes to question 3: send `think: false` for qwen3 models through the provider
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
- Treat the benchmark's "good" as the chat's, or "not told apart" as "level".
- Push, change the provider for qwen3:1.7b, or swap the default model without her word.
- Run tests on the laptop; read, print or copy `.ask100-runtime/env.json`; kill processes you
  did not start on the Mac; install anything there with brew; rebuild the 5,589-chunk index;
  touch `demo/phase-e-raw.webm` or `reports/ask100/`.

## Lessons

1. **A plugin from the official marketplace loaded into a `--safe-mode` session** — one case
   so far. `figma` did at 12:05; `codex@openai-codex`, from a directory marketplace and
   enabled since April, loaded in no earlier session of the route. The route's own check
   refused the first such reply, so no verdict came from a dirty session. When the route
   refuses with "loaded more than the request", read the `plugins` of the session's init
   event, and override per request.
2. **A row keeps only a refusal's code.** The cause took a wrapper that writes the message;
   keep it from the first request.
3. **A time budget kills the request in flight.** One chunk of ten per call (4–13 min) fits
   `timeout 1150` with room; two did not, once.
4. **Thirty cases moved the gaps both ways.** All four did worse on the other 70; against
   qwen2.5-7b, qwen3-1.7b fell from level to 6 behind while the 4B and the 8B rose from 3 and 1
   ahead to 8 and 9 (above). The registered rule — gaps of five or fewer unresolved, so
   extend — is what caught it.
5. **Count before registering.** The dry plan against the published record gave the exact
   numbers the registration states (415, 123, 292).
6. **Not told apart is not level.** A paired test that finds no difference on 100 cases
   still fits a gap of 17 points; say what the data fit, and list the reading of an
   unregistered criterion among the session's choices.
7. **What can refuse goes before the first byte.** A streaming response is started by its
   first event; an HTTP error raised after it cannot reach the client and only cuts the
   stream.

## Glossary

- **good / partial_ok / bad** — good: a full answer with every claim supported by the context
  and no defect, or a decline where the context holds no answer; partial_ok: a partial answer,
  every claim supported, no defect; bad: everything else.
- **Wilson interval** — the 95 % interval of a share; at 50 of 100 it is 0.40–0.60.
- **Exact sign test** — on the cases where only one of two generators is good (McNemar's exact
  test); "apart" means p < 0.05 / 6 over the six pairs, otherwise "not told apart".
- **Reuse** — copying a verdict of the 30-case plan whose request is byte-identical (same item
  id and message hash); each copy carries that plan's SHA-256 in `reused_from`.
- **Route** — two things here: the chat's verdict on a question (`auto`, `human`, `timeout`,
  …) and the judge's CLI route, the stateless session of `evaluation/isolated_request.py`.
- **Call, chunk** — a call is one tool call of the session under one `timeout`; a chunk is
  ten requests.
- **Route refusal** — `JudgeUnavailable`: `cli_response` (the reply or its session is not
  vouched for), `cli_exit` (the CLI exited non-zero); the run stops at the first.
- **`--safe-mode`** — the CLI flag meant to load no instruction file, memory, hook, skill,
  plugin or MCP server; see Lessons, 1.

## Verification

- Mac gates: `c3f0fff`, six tests, 45 passed (owed from the previous log); `30b1469`, the
  judge's and the record's tests 34 passed, with the three docs tests 57; `5861ffb`, 57;
  `928c124`, the same set and the two chat records' tests, 75 passed; `54ffdb2`, the new test
  and 17 stream, session and cooldown test files, 125 passed; this revision, the same set
  and the new stream test, 79 passed.
- Before asking for a push, on `928c124`: the whole unit suite, mypy, bandit, pip-audit and
  the npm audit (Log, 15:24); the whole suite again on this revision, 5,794
  passed, 121 skipped.
- CI on `c3f0fff`: CI 38723502525 success; Deploy docs site 38723502529 success (build
  passed, deploy skipped).
- The record's test rebuilds the 100-case plan from the tracked inputs, checks that the 123
  copies equal the published rows, rebuilds the summary from the verdicts and recomputes every
  count, interval and sign test of the evidence row; its minutes, median and longest request
  were checked by hand.
