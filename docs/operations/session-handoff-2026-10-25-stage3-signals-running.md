# Session handoff 2026-10-25 — stage 2b closed (V4 adopted), stage 3's signals running

Session `5ec44b60`, 2026-10-25 08:54 UTC – (open). The laptop's clock and Julia's times are EDT
(UTC−4); the Mac's clock is UTC+3; the logs write UTC. Previous handoff:
[V4 running unattended](session-handoff-2026-10-24-v4-running.md).

## Read this first

- **A measurement is running on the Mac with no session watching it** — stage 3's signals
  (`scripts/chat_signals.py run`) on V4's 100 aircargo answers, started 17:26:57 UTC; 19
  answers by 19:11 UTC (≈ 5.5 min each, read with step 1's command), so done about 02:40–03:30
  UTC on 10-26. Check it first ([Next actions](#next-actions), step 1). If it dies it resumes
  after the last answer row: the same command again.
- **Web research, two queues side by side, one run at a time in each** (Julia, 18:41–19:06
  UTC): three research runs by a Claude subagent, each repeated by Codex (profile cw,
  `gpt-6-astra`, effort `xhigh`) as a second opinion. Claude's three and Codex's research 1
  and 2 are done, in [their own document](research-2026-10-25/README.md); what runs and what
  is next: [Research](#research-three-runs-each-twice).
- **While the signal run measures:** no `sync.py`, no `remote.py`, no tests on the Mac — the
  record publishes the seconds each signal adds, and they count only from an idle Mac. Never
  stop another project's process. At 19:13 UTC the Mac ran only our `llama-server` (373 % CPU,
  all four cores; no pytest; 72 % memory free), so nothing makes this run faster without
  changing its frozen conditions (Julia asked at ≈19:14; answered so).
- **Pushed ≈19:25 UTC at Julia's word** («закомить и запуш все, что сделано», 19:20), up to
  this file's commit, **without the Mac suite** (the Mac was measuring); laptop checks passed.
  Step 6 lists what still has to run on the Mac once the signal run ends.
- **Stage 2b is closed: V4 adopted** ([record](../evidence/answer-prompt-v4-record.md)). Stage 3
  reads V4's answers by the [handover plan](../specs/handover-signal.md) — its «Reading» is
  frozen since 2026-10-17 (Julia: «давай так»), S7's threshold rule since `f520cde`.

## Why this stage exists

On 2026-10-16 Julia asked for «% передачи вопросов оператору»; replaying the chat's rule, 2 of
100 answers went to a person and 10 of 12 bad answers went to the client unmarked. Her words
of 2026-10-17: «А не был настроен сигнал ответа человеку??? Давай сначала замерим.» The handover
plan measures which signal marks the answers that need a person (every bad answer and every
decline), how many good answers it marks with them, and what time it adds. Stage 3 of
`PLAN.md` runs it on the 100 aircargo answers of the prompt the code now holds — V4's, since
stage 2b adopted it today.

## Julia's words in this session (UTC)

- 08:54 — «продолжи доработку».
- 10:58 — «на 204 запуска судьи хватит одного 5-ти часового окна?» (her number; 333 requests
  were left after the window filled at 10:41). Answered: about 0.003 of the window a request,
  so 204 take about 0.63 of one window.
- 11:02 — «новый лимит будет доступен примерно через 3 часа, тогда нужно и перезапустить
  процесс». Answered: no restart needed — the judge driver waits for the window's reset by
  itself; it resumed at 13:59 UTC on its own.
- 18:28 — «можно ли сейчас вывести текущие метрики по проекту?» Answered from the committed
  records (the V4 table in [Research](#research-three-runs-each-twice)).
- 18:37 — «а почему передача опреатору так хромает?» Answered: the self-score is the chat's
  only signal and it does not see the main error, an unsupported claim; its thresholds were
  never calibrated; the strict claim check exists only in the widget and takes minutes.
- 18:41 — «текущие проблемы нужно же как-то лечить((( над этим стоит думать только после
  полного прогона. И по трем базам результат очень низкий - с этим же тоже стоит что-то
  делать. Вероятно стоит запустить 2 рисеча - на предмет, как лкчить текущие проблемы и какие
  метрики по RAG актуальны на текущий момент.» Answered: agreed, one after another, the
  metrics run first (it tells whether «низкий» is low against others on the same bases).
- 18:48 — «Найдутся ли результаты по RAG именно на найденных базах? … Я бы тогда еще один
  общий ресерч запустила - общие метрики по RAG, которые достигаются на момент октября 2026
  года и методы. … Если согласен, запусти последовательно. Вероятно решение о3-ем рисерче
  стоит принять перед его запуском.» Answered: yes, each base has a paper with baselines, not
  directly comparable (other models, metrics, subsets); research 1 launched at 18:51.
- ≈18:52 — «и вероятно все это стоит оставить для следующей сессии … стоит все прописать в
  доке - про текущий запуск на маке и про рисерчи». This file is that record.
- ≈18:53 — «вижу, что ты уже запустил первый рисерч - конечно не останавливай его».
- 19:06 — «что думаешь, если в этой сессии сделать все три рисерча + их дубль на кодекс (модель
  gpt astra 6 xhigh)? если согласен - нагрузи кодекс, тоже по одному рисерчу последовательно».
  Agreed; this replaces «оставить для следующей сессии» for the research. Research 2 now runs
  before stage 3's outcome — the literature does not depend on it; the brief asks each option
  to be rated for both outcomes, and the choice of a treatment still waits for the outcome
  (her 18:41 words).
- ≈19:14 — «а можно как-то ускорить процесс на маке?» Answered: no, see «Read this first».
- ≈19:20 — «закомить и запуш все, что сделано». Done: the record tool committed (`5049430`),
  its test held back (it fails until the record exists), the laptop's checks run (CI's two
  mypy commands, `ruff check`, bandit, pip-audit, DEP-01 — all clean), pushed. The Mac suite
  could not run: the signal run measures there.

## My choices, not hers

- S7's threshold rule (`f520cde`): the plan said the threshold "is chosen on stage 1" and named
  no rule. Committed at 17:30 UTC, three minutes after the run started (the run does not read
  the verdicts) and before S7's scores were set against the verdicts: every distinct top score
  a candidate; among those over-marking at most 1 of 3 good answers, the one catching the most
  targets, a tie to the lower; a best catching none is no threshold. Chosen on these answers it
  stays a candidate (the plan's own rule).
- The record tool's form (`reports/handover-signal/tools/signal_record.py`, uncommitted): the
  judge's classes from the committed export `v4-aircargo-judge.cases.jsonl`, not the private
  verdicts (an inline comparison in this session found them equal on all 100); the reading on
  unrounded Wilson limits; added time 0 for the signals without a model call, the claim
  check's seconds for S2 and S3, the grader's for S4, both for S6.
- S5 and S8 were not changed after their counts were seen (S5 marks 0, S8 8 — see below).
- The two research queues side by side (Claude's and Codex's), one run at a time in each — my
  reading of «тоже по одному рисерчу последовательно».

## What happened

1. **V4's judge, 620 requests** (08:58 – 17:07 UTC, $116.15, median 63 s): the WixQA and
   ConditionalQA plans frozen in `410a642` before their first grade, aircargo's in `d5f6e91`;
   the five-hour window filled at 10:41 (287 requests used 0.89 of it by the usage probe, and
   the driver paused); it resumed at 13:59. The Mac's answer chain ended `CHAIN_DONE` at 15:06
   UTC. All plans and the three bridges passed the stability rule (bridge κ: aircargo 1.0,
   WixQA 0.96, ConditionalQA 0.69).
2. **Stage 2b's record, `df60777`:** adopted. Pooled external bad share 127 → 108 of 200
   (−9.5 pp; −15.7 to −3.1), detected; WixQA bad 63 → 51 and good 27 → 40 detected;
   ConditionalQA and aircargo moves not detected. Near the line, deciding nothing: ConditionalQA
   declines 4 of its 20 not answerable questions (V3 8; upper limit +0.4 pp); aircargo's nine
   good answers turned bad, eight by one or two unsupported claims. Mac: 99 passed (the
   record's tests through `remote.py`; output not kept).
3. **S8 in the signal tool, `d260d95`** (the handover plan asked for it before its step 1.3):
   the answer's script, by `tests/test_stage1_live_artifact.py`'s rule; tests in
   `tests/test_chat_signals.py`. Mac: 39 passed with stage 1's artifact test and the three docs
   tests (`remote.py`; output not kept).
4. **The signal plan, `b7ad62a`** (committed 17:26:42 UTC):
   `reports/handover-signal/d260d95/plan.json` (SHA-256 `30e0a598…df16e`), built on the Mac
   from the stand's run folders, before the first model call; no text in it; every prompt's
   SHA-256 equal to the judge plan's (`.tmp/v4/check_signal_plan.py`: «prompts equal judge
   plan: True»).
5. **The run**, launched 17:26:57 UTC; then **S7's rule, `f520cde`**, 17:30:17 UTC.
6. **Locks, `b557082`:** six Python floors and five npm floors past the advisories of
   2026-10-24/25; CI's pip-audit command on `requirements.lock` «No known vulnerabilities
   found, 5 ignored», npm audit 0, DEP-01 PASS — all on the laptop.
7. **Research 1–3** and the second-opinion runs — [Research](#research-three-runs-each-twice).

## What is already known (no model call needed)

17 of the 100 answers are targets — all bad, none declined (V4 declined no aircargo question)
— over the plan's minimum of 15, so the reading applies. Good, non-declining: 63; partial: 20.
Counted in this session by an inline script from `plan.json` and the verdicts; the record tool
counts every one again from the rows, and its test counts each signal a third way — the record,
not this table, is the evidence.

| Signal | Marked | Caught of 17 | Over-marked of 63 | Reading |
|---|---|---|---|---|
| S1 self-score < 80 | 3 | 2 | 0 | useless |
| S1′ (`S1p` in the files) self-score < 100 | 14 | 3 | 4 | useless |
| S5 decline | 0 | 0 | 0 | useless |
| S7 rerank top < 0.981153 (the rule's) | 33 | 4 | 19 | useless |
| S8 answer's script | 8 | 3 | 4 | useless |

The reading (frozen): **worth wiring** — caught ≥ 2/3 with Wilson's lower limit ≥ 1/3 and
over-marked ≤ 1/3; **useless** — Wilson's upper limit of caught < 1/2, or over-marked > 1/2;
otherwise **in between**. Every cheap signal's upper limit is below 1/2, so **outcome A
cannot happen** on these answers; the outcome is B if S2, S3, S4 or S6 is worth wiring, C if
none; an in-between signal goes on to stage 2 of the handover plan (step 5 below).

Two things to say plainly in the record: S8 counts letters, not language — all 8 answers it
marks are Russian, dense with Latin terms such as AWB and field names (read with
`.tmp/v4/s8_look.py`); and S5's phrases are those of V2 (the answer prompt before V3) and the
widget, while V4 declines in its own words, so S5 could not fire (the plan left S5's wording to
stage 3 — settle it before any further reading, not on these answers).

First five rows (each: grader s, claim check s, total s; all routed `retry` by S6, no node
errors): 145/202/347, 289/229/518, 302/81/383, 83/235/318, then total 403. The cap is now
3 × 383 = 1,149 s an answer.

## Research: three runs, each twice

**Why.** V4's answers, judged by M1 ([V4 record](../evidence/answer-prompt-v4-record.md);
MultiHop-RAG was not in V4's run, its row is V3's from [stage 2](../evidence/stage2-record.md)):

| Base | Good | Partial | Bad | Claims supported | Routed to a person | Median / p90 s |
|---|---|---|---|---|---|---|
| aircargo | 63 | 20 | 17 | 96.7 % | 3 | 296 / 390 |
| WixQA | 40 | 9 | 51 | 90.5 % | 14 | 301 / 471 |
| ConditionalQA | 35 | 8 | 57 | 79.2 % | 17 | 249 / 339 |
| MultiHop-RAG (V3) | 65 | 1 | 34 | — | — | — |

Where the bad answers come from, by the judge's per-answer fields
(`reports/answer-prompt-v4/4f48fed/*-judge.cases.jsonl`):

| Base | Bad | The context held the answer | With an unsupported claim | Declined though the context answered |
|---|---|---|---|---|
| aircargo | 17 | 17 | 14 | 0 |
| WixQA | 51 | 48 | 32 | 22 |
| ConditionalQA | 57 | 54 | 50 | 6 |

Retrieval by the gold documents ([stage 2's baseline](../evidence/stage2-retrieval-baseline.md),
the same retrieval as V4's): ConditionalQA all evidence in the context 60/80, WixQA a gold
article 68/100, MultiHop-RAG all evidence 10/70. **Reading (mine):** the main loss is the 4B's
generation — it adds claims the documents do not hold, and on WixQA declines what they answer;
retrieval is the second loss, worst on multi-hop questions. The handover problem has the same
root: the cheap signals do not see an unsupported claim, so a claim check could both route an
answer to a person and repair it — that is the question research 2 has to answer at this
Mac's cost.

**The runs and what they found** are in their own document,
[web research of 2026-10-25](research-2026-10-25/README.md): the three briefs, Claude's and
Codex's reports, how they were made (Claude: a `deep-researcher` subagent on the session's
model; Codex: profile cw, `gpt-6-astra`, `xhigh`, read-only, in a package folder holding only
the brief — the second-opinion role of `PLAN.md` §8.1), where they agree and differ, and a
proposal for Julia's decision. In short:

1. **Research 1** (our bases, the metrics in use): nothing published matches our setup, so
   «низкий» is not shown to be low; three metrics to add from what we record — claim-level
   faithfulness, nugget recall in the answer and in the context, decline quality. Claude's
   report misread MultiHop-RAG's Hits@K: the official `retrieval_evaluate.py` (read with
   WebFetch ≈19:30 UTC) counts a hit when *any one* gold fact is in a top-K chunk, so our 10/70
   and 0.49 are stricter and not comparable until recomputed by that rule.
2. **Research 2** («как лечить»): first the free recompute, then an answer flag and a second
   pass for declines only (WixQA's 22), then a claim check as the router; the seconds-fast
   checkers read English only.
3. **Research 3** (the state of RAG; its scope decided ≈19:28 UTC after reading 1 and 2, as her
   18:48 words asked): the levels by system size, the method families that transfer to a 4B on
   a CPU, how production support measures the handover — nobody publishes escalation precision
   and recall; its reading of our gap as a retrieval loss conflicts with the table above.

Codex's queue: research 1 done (thread `01a17478-…`, 19:10–19:28 UTC), research 2 done
(`01a17489-…`, 19:29–19:49), research 3 running since ≈19:50 UTC (stream
`.tmp/research/cx-r3-stream.txt`); each report is saved by step 7's command and compared in
that document.

## State now

- **Commits since the push `8fdbfee`, all pushed ≈19:25 UTC:** before this session `3422244`
  (risk review), `4f48fed` (V4), `c2c5a58` (handoff); this session `410a642`, `d5f6e91`
  (plans' hashes), `df60777` (stage 2b's record), `d260d95` (S8), `b7ad62a` (the signal plan),
  `f520cde` (S7's rule), `b557082` (the locks; the risky moves are filelock's major version
  3 → 4 and astro 7.2 → 7.3, whose site build has not run), `5049430` (the record tool), and
  the handoff commits `a383318`, `8047d40`, `d3e165c`, `6c9e51a` and this file's.
- **Uncommitted, in the tree:** `tests/test_handover_signal_record_artifact.py` — it waits for
  the rows (it reads `signals.jsonl` and `record.json`); the tool it tests is committed, ruff
  clean, not yet run on real rows. Also untracked and not this session's:
  `demo/phase-e-raw.webm`, `reports/ask100/`.
- **The Mac:** workspace `/Users/julia/RAG_new_signals_d260d95` (a `git archive` of `d260d95`
  with `CODE_SHA`); the run reads the stand's folders
  `/Users/julia/RAG_new_chat_4f48fed/chatlive/runs/v4-aircargo-b01…b10`; it writes
  `signals/out.jsonl` and `signals/run.log`; interpreter
  `/Users/julia/RAG_Support_Assistant/.venv/bin/python`; under `caffeinate`, `nohup`.
- **Private, on the laptop only:** `D:/RAG_new_stage2_private/v4/` (runs and verdicts).
- **Backup:** the git-ignored `.tmp/v4/`, `.tmp/locks/` and `.tmp/research/` scripts, briefs
  and reports and the two uncommitted files in the local branch `wip/stage3-signals` (see
  Verification); nothing pushed.

## Next actions

1. **Check the run** (any time; `[r]` keeps the pattern from matching its own shell):
   `ssh deproject-mac 'W=/Users/julia/RAG_new_signals_d260d95/signals; grep -c "\"kind\": \"answer\"" $W/out.jsonl; ps -axo pid,etime,command | grep "chat_signals [r]un"; tail -c 200 $W/out.jsonl; grep -c Traceback $W/run.log'`.
   Alive: a `python -m scripts.chat_signals run` line. Done: the last row's `kind` is `end`.
   - **A `stop` row** (an answer passed 1,149 s; the tool exits 3): look at the Mac
     (`uptime`, `ps -axo pcpu,comm -r | head`). Resume once with the command below — it retries
     that answer under the same cap. If it stops again on that answer, do not raise the cap or
     drop the answer (both change the frozen plan): tell Julia and wait.
   - **Dead without `end`:** `ssh deproject-mac 'cd /Users/julia/RAG_new_signals_d260d95 && nohup caffeinate -dimsu /Users/julia/RAG_Support_Assistant/.venv/bin/python -m scripts.chat_signals run signals/plan.json signals/out.jsonl >> signals/run.log 2>&1 < /dev/null &'`
     with the Bash tool's `run_in_background` (the `&` list keeps ssh's output); it resumes
     after the done answers. If Ollama does not answer
     (`ssh deproject-mac 'curl -s localhost:11434/api/version'`), ask Julia before starting it.
2. **After `end`:** copy the rows as they are —
   `scp deproject-mac:/Users/julia/RAG_new_signals_d260d95/signals/out.jsonl D:/RAG_new/reports/handover-signal/d260d95/signals.jsonl`.
   Node errors are `str(exception)[:300]`; list them with
   `python -I -X utf8 -c "import json; [print(r['item'], r['node_errors']) for r in map(json.loads, open('D:/RAG_new/reports/handover-signal/d260d95/signals.jsonl', encoding='utf-8')) if r.get('node_errors')]"`.
   If one quotes a question, an answer or a document, replace that string with the exception's
   class name before the commit and say so in the capsule; any node error is a failed signal
   for that answer — count it in the capsule and make the test check the count (it now
   asserts none). Then build the record with the laptop's focused venv:
   `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I -X utf8 D:/RAG_new/reports/handover-signal/tools/signal_record.py D:/RAG_new/reports/handover-signal/d260d95`
   (the tool puts the repository on `sys.path` itself). Check `record.json` has LF endings.
3. **The capsule** `docs/evidence/handover-signal-v4-aircargo.md` (not the root): the table
   per signal (caught, over-marked, marked, added seconds, reading), R2 and R3 with their
   counts (the record's `findings`), **R1 «not checked here»** — the run sets no `RAG_ENV`
   (`rag_env` None) and no record of the spec's 1.0 check exists; `PLAN.md` stage 3 step 4
   checks it — the grader's outcomes and failures (`PLAN.md` stage 3 step 4 asks for their
   share), the outcome, the S5 and S8 notes above, "no person graded an answer". Add a capsule
   test to `tests/test_handover_signal_record_artifact.py` that prints from the record.
4. **The status files and the gate.** One row in `EVIDENCE_INDEX.md`; `CURRENT_STATE.md` (at
   its 150-line cap — edit in place): the number row and Next; `ROADMAP.md` row 3; `PLAN.md`
   under stage 3; `BACKLOG.md`: the stage-3 item (lines 9–12) becomes the outcome's next step;
   `docs/README.md`. On the laptop:
   `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -m ruff format` and `-m ruff check`
   on the two new files. Idle Mac check (no `llama-server`, 5-minute load below 2):
   `ssh deproject-mac 'uptime; ps -axo command | grep -c "[l]lama-server"; ps -axo command | grep -c "[p]ytest"'`.
   Then `python D:/RAG_new/.tmp/mf-mac/sync.py` and
   `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest tests/test_handover_signal_record_artifact.py tests/test_chat_signals.py tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-stage3 --tb=short`;
   one commit.
5. **Tell Julia the outcome** by the plan's «What each outcome means»: **B** — she chooses how a
   check of minutes is wired (wait for it, show the button later, or check some answers);
   **C** — no signal finds them on this Mac with the 4B, and her options (a line under every
   answer, a route by topic, a stronger checker elsewhere); **an in-between signal** (the
   record lists it under `in_between` and `candidates_for_stage_2`, the letter staying B or
   C) — the handover plan's stage 2: a plan of its own, named before its first request, on the
   open parts `PLAN.md` stage 3 step 2 names (WixQA's and ConditionalQA's; the spec says
   WixQA's 142 tuning questions), with an English judge prompt and its own retest and English
   decline wording for S5 (the spec); 4–12 h of the Mac a hundred by the spec, 5–17 h by
   `PLAN.md` — tell her the hours before it starts. Then `PLAN.md` stage 3 step 4: ten widget
   answers on the 4B on the idle Mac (its time and routes; R1 by one widget request under each
   `RAG_ENV`, production also needing `CORS_ORIGINS`; R2) — checking needs no word, a fix needs
   hers and a test.
6. **What the push of 2026-10-25 skipped** — run after the signal run's `end` and step 4, and
   before the next push: on the idle Mac after `sync.py`, `b557082`'s guards
   (`remote.py --site pytest tests/test_pip_audit_floors.py tests/test_npm_audit_floors.py tests/test_docs_site_npm_audit.py -q -p no:cacheprovider`)
   and the site build on astro 7.3 over ssh in `/Users/julia/RAG_new_mf_gate/docs-site`
   (`node -v` first; `npm ci && npm run check && npm run build`; Chromium is Playwright's cached
   build in `~/Library/Caches/ms-playwright`); the whole suite
   (`remote.py --site pytest tests/ -q --ignore=tests/integration -p no:cacheprovider`, ~10 min,
   in the background); both mypy commands of `.github/workflows/ci.yml` (lines 136–137) through
   `remote.py` without `--site`; on the laptop bandit as CI runs it (ci.yml line 278), CI's
   pip-audit command (ci.yml lines 280–307) and `npm run audit:deps` in `docs-site/` — then ask.
   Only CI installs the Linux lock; say so when asking.
7. **Research** ([above](#research-three-runs-each-twice)), independent of steps 1–6.
   - Claude's three runs are done. When a Codex run ends (the stream ends with `EXIT 0`):
     `python -I -X utf8 D:/RAG_new/.tmp/research/save_cx_report.py D:/RAG_new/.tmp/research/cx-<run>-stream.txt D:/RAG_new/.tmp/research/cx-<run>-….md`
     saves the final message and prints the rollout's model, effort and sandbox (they must say
     `gpt-6-astra`, `xhigh`, `read-only`); copy it to the research folder as `codex-<n>-….md`
     and add its comparison there. Then launch the next:
     `python -I -X utf8 D:/RAG_new/.tmp/research/build_cx_brief.py D:/RAG_new/.tmp/research/brief-<run>.md D:/cx-research-rag/<run>/BRIEF.md`,
     then in the background
     `env -u CODEX_COMPANION_APP_SERVER_ENDPOINT CODEX_HOME='C:\Users\uedom\.codex-work' CLAUDE_PLUGIN_DATA='D:\RAG_new\.tmp\cx-work-state' node "C:/Users/uedom/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" task --cwd "D:/cx-research-rag/<run>" --model gpt-6-astra --effort xhigh --prompt-file "D:/cx-research-rag/<run>/BRIEF.md" > D:/RAG_new/.tmp/research/cx-<run>-stream.txt 2>&1`
     (first `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File 'C:/Users/uedom/.codex/scripts/codex-account-launcher.ps1' work -PrepareOnly` once a session).
   - Research 3's brief is built (`D:/cx-research-rag/r3/BRIEF.md`). After the last report:
     the comparison of each pair in the research folder (where they agree, where they differ,
     which sources only one found), and at the session's end the companion brokers of `D:/cx-research-rag/*` stopped (only
     those trees, by an explicit list — never `taskkill /T`).

## Do not

- Change S5's phrases, S8's rule or S7's rule and read them again on these 100 answers.
- Read `archive/` for routing; push without her word; run anything heavy on the laptop.
- Run `sync.py`/`remote.py` or tests on the Mac before the run's `end`.
- Run two Claude research agents at once, or two Codex runs at once; give Codex a file of the
  repository or of a base.

## Lessons

- **Laptop JSON writers write CRLF; git commits LF.** Stage 2b's record first failed its own
  input-SHA test: `judge_export.py` ran on the laptop. Normalize with `write_bytes`, then build.
- **Mac `tar` adds AppleDouble `._*` files** that match `*-stream.txt`; `COPYFILE_DISABLE=1`.
- **`ssh host 'a && nohup b > f &'` holds the channel:** the backgrounded list keeps ssh's
  output. Closing the local ssh was safe — `nohup` kept the run alive (checked at once).
- **`pgrep -f "<pattern>"` over ssh finds its own shell:** the remote `sh -c` carries the
  pattern, so «alive» is always printed. Write the pattern so it does not match itself
  (`chat_signals [r]un`) and read the process line.
- **Look before the reading is final, not after:** the cheap signals' counts were read once
  the plan was frozen; nothing about them was changed.
- **A cold read finds what the writer cannot:** this file's first version had a stale commit
  count, an unfixed pgrep check and no rule for a `stop` row; a fresh agent's read found them.

## Glossary

- **Target** — an answer that needs a person: the judge's *bad*, or any decline.
- **Caught / over-marked** — targets marked / all targets; good non-declining answers marked /
  all of them; Wilson 95 % limits.
- **S1…S8** — the plan's signals; S2, S3, S4, S6 need the 4B (the widget's claim check,
  grader and first-pass route); the others need no model call. **S1′** is `S1p` in the files.
- **R1, R2, R3** — the [handover plan](../specs/handover-signal.md)'s suspected widget defects
  (R1: production routes every answer `human`; R2: an answer with no claims becomes a gap; R3:
  a claim counts only with a cited `[N]`); not the research runs.
- **Research 1–3** — the web research Julia asked for on 2026-10-25
  ([Research](#research-three-runs-each-twice)).
- **M1 / M2** — the judge's two grades: M1 without the reference answer (good / partial / bad
  by the retrieved documents), M2 with it (does the answer agree with the gold answer).
- **Stability rule, bridge, κ** — a judge plan counts when its 15 retest pairs agree: quadratic
  κ ≥ 0.6, or at least 13 of 15 equal and none two classes apart
  ([stage 2 spec](../specs/stage2-four-corpora.md#the-judge)); a bridge is stage 2's 15
  retested requests graded again in V4's window, read by the same rule, to catch a judge that
  moved ([V4 spec](../specs/answer-prompt-v4.md)).
- **Chain, `CHAIN_DONE`, judge driver** — the Mac's script that answered the questions batch
  after batch and wrote `CHAIN_DONE` at its end; the laptop script that sent the judge's
  requests and waited out the usage window.
- **The cap** — the time an answer may take before the tool stops: 3 × the median of the first
  five answers, here 1,149 s.
- **Handover plan steps 1.0–1.4, stage 2** — the plan's own numbering, inside `PLAN.md`'s stage 3.
- **`node_errors`, `findings`** — per row, the errors of the widget's nodes; in the record, the
  R2 and R3 counts.
- **Simulated** — WixQA's subset of generated questions; its open part comes from it.
- **DEP-01** — the npm audit gate (`docs-site/scripts/check-npm-audit.mjs`, ADR 0009).
- **Nuggets, RAGChecker, CRAG-style score** — nugget evaluation scores an answer by the key
  facts of the reference it holds; RAGChecker is a claim-level faithfulness and recall
  framework; the CRAG score gives +1 right, 0 decline, −1 wrong.
- **Stand** — a `git archive` of one commit on the Mac; **workspace** here is the same for the
  signal tool's commit.

## Verification

- `git log --oneline -3` shows this handoff's commit on top; `git status` shows the two
  uncommitted files (and the untracked `demo/phase-e-raw.webm`, `reports/ask100/`).
- `ls .tmp/research/` shows the briefs and the reports that are done.
- `git rev-parse wip/stage3-signals` gives the backup commit; restore a file with
  `git show wip/stage3-signals:<path> > <path>`.
- `sha256sum reports/handover-signal/d260d95/plan.json` gives `30e0a598…df16e`.
