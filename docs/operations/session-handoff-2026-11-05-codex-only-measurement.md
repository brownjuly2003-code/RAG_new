# Session handoff — 2026-11-03 21:18 → 2026-11-05 ≈ 14:45 UTC: the codex-only measurement answered whole (attempt-06, 300/300), judging next

Times are UTC. Git prints laptop-local time, UTC−5: `git log` shows 05:06 for `86a6ab4`,
which this file gives as 10:06. The session's first part, up to the spec and the
`codex-only` route fix (`8fc8cb5`), is in
[its earlier handoff](session-handoff-2026-11-03-codex-only-live.md). This file covers
the run that came after it.

## Read this first

- **What this is.** This is stage 6 item 0's quality re-measurement under `codex-only`,
  specified in [`docs/specs/codex-only-quality.md`](../specs/codex-only-quality.md). The
  product runs on her laptop. Every model call goes to Codex (cw, `gpt-6-astra`): the
  answer at `xhigh`, the auxiliary calls at `low`. It answers 300 real labelled questions
  (WixQA, ConditionalQA, AirCargo, 100 each). An isolated Claude judge grades them, and
  the reading compares the result with stage 5в's Codex arm.
- **Where it stands.** Series `attempt-06` answered all 300 questions. All three keys
  are frozen and committed: wixqa `32ff420`, conditionalqa `86a6ab4`, aircargo `4bf203a`.
  Nothing has been graded. Next come judging, the export, the reader, then the status
  documents.
- **How to start.** In the new session she types «продолжи по handoff замера codex-only».
  Do [Next actions](#next-actions-in-order) in order.
- **The open risk: grading speed.** The grade code has never run in any series. Each grade
  chunk first re-hashes the whole copy (offline admission, no stat cache), and **that time
  counts against `--budget 600`** (`quality_freeze.grade` and `admitted`). attempt-04's full
  admission took 691 s. The first chunk measures the cost; step 2 gives the decision rule.
- **The one tool for judging** is `.tmp/cx-exec/grade_a06.py`. It is git-ignored and was
  written at the end of this session:
  - it runs one foreground grade chunk with the judge environment;
  - it honours the persisted `retry_at`;
  - it prints the driver's last line, the chunk's seconds, new verdict rows and
    valid/planned per plan.

  If `.tmp/` is lost, rebuild it from step 2.
- **Nothing is pushed.** Local `master` is 36 commits ahead of `origin/master`, this
  handoff's commit included. A push needs her word and every gate in
  [`CLAUDE.md`](../../CLAUDE.md) and the global rules.
- **The laptop is shared and short of memory.** She runs another Claude session she
  needs. Heavy work goes to the Mac (`.tmp/mf-mac/sync.py` + `remote.py`), never pytest
  here. Ollama or any local LLM must never start on this machine.

## Julia's words in this session (UTC)

- 11-03 21:18 «продолжи работу». The session continued the previous handoff: the live
  run, the route fix, the spec. All of that is in the earlier file.
- 11-04 09:01 «то есть тест на кодекс ты так и не прогнал???». This set the goal: run
  the codex-only measurement to the end — registration, probe, pilot, 300 questions,
  freeze, grade, export, `quality_read`, status documents.
- 11-04 10:55 «вероятно стоит продолжить работу в след сессии, когда кодекс закончит
  работу текущую?», then 10:57 «хорошо, остаемся тут».
- 11-04 19:14 «ты периодически запускаешь пайтон скрипты, они здорово едят память. Они все
  нужны? Я поясню - нужно запустить еще сессию». At 19:23: «сейчас норм все.», «и твоя
  работа очень важна». At 19:24: «я только про оптимизацию, если она возможна».
- 11-04 21:45 «Можно ли как-то снизить нагрузку на систему? есть еще одна сессия на клоде,
  но она мне очень нужна, больше я тебе никак не мешаю». This brought the stand stop
  between chunks and the background mode for offline hashing (see My choices).
- 11-04 22:15 «эта сессия очень длинная. нет смысла начать новую? ты работаешь на xhigh
  effort. вероятно стоило запустить работу на max?»
- 11-04 23:19 «запиши ответ на мой вопрос в файл answer.txt на диск D». Her question was
  what the admission cache does; the answer is `D:/answer.txt`.
- 11-05 00:50 «убей процессы орфаны в системе, если есть такме». Only my own four
  `tail`/`grep` were orphans; nothing else was killed.
- 11-05 01:00 «постгрес... 8 процессов - это точно нужно???». They belong to the product's
  own PostgreSQL; it was left alone.
- 11-05 01:02 «машина работает на пределе памяти(( и крайне вероятно потому тормозит».
- 11-05 01:17 «продолжай. сейчас закончится лимит кодекс - тут просто дай знать, у меня есть
  ресет для кодекса - я его использую». At 01:25: «я ресетнула лимит колекс». **Standing
  rule: on a Codex usage limit, tell her; she resets it.**
- 11-05 07:51 «28 bp 100 за 6 часов????», 07:52 «это же ненормально». My answer: most of
  the lost hours came from my instrument's false overlap stop (attempt-05, below) and the
  rule-bound re-run. The product's own answer takes 55–80 s.
- 11-05 09:22 «а сейчас графовый поиск используется?». No: `RAG_GRAPH_RETRIEVAL` defaults
  to `off` (`config/settings.py`) and is unset in the stand environments. PLAN stage 4
  gives why it stays off.
- 11-05 11:02 «после того как процесс текущий завершится, имеет смысл начать новую
  сессию?». I said yes, once AirCargo is frozen and committed, with this handoff first.
- 11-05 11:08 «у сессии продолжительность почти 38 часов и всего 8 сжатий...???». My
  answer: compaction fires on context size (about 250k tokens), not on time. Most of
  those hours were long chunk waits with short outputs.

## What this session did (commit times UTC, all local, none pushed)

**Tools, written by Codex as executor** (her word of 2026-10-30), reviewed and committed
by the session:

| Commit | Time | What |
| --- | --- | --- |
| `f1bd756` | 11-04 10:01 | Capture shim (19b-1) |
| `7084860` | 10:36 | Copy admission and offline registration (19b-2) |
| `19ecbbb` | 12:00 | Request driver (19b-3) |
| `3c0c72c` | 12:45 | Freeze, grade, export and the reader (19b-4) |

**Fixes made in the series, written by the session.** No Codex task runs beside live
chunks. Each fix was synced to `D:/RAG_new_cx/s1`:

| Commit | What it fixed |
| --- | --- |
| `5b7e71f` | A CRLF working copy of `mistral.py` |
| `559a54c` | The process-watch exit race (`python_command_unreadable`) |
| `f3bcf3a` | An outside `codex.exe` is recorded, not a stop; the orphan rule for a reused PID |
| `e919df8`, `ef41caf` | A stat cache for request-chunk admission; `copy_verify` unchanged |
| `6d4e32f` | The kernel's exit time for a killed call |

**Series.** Each stop by rule means a new registration, and no answer carries over:

| Series | Registered | Outcome | Cause | Records |
| --- | --- | --- | --- | --- |
| attempt-01 | `6f272f2`, `5b7e71f` | code 5 twice, then retired | Watch race: her other session's short-lived pythons | `9530861` |
| attempt-02 | `9530861` | code 2 before any request | attempt-01's call records in the shared capture root | `616798d` |
| attempt-03 | `616798d` | pilot 20/20 (`b366a0c`); wixqa frozen (`53a701a`); code 2 at 11-04 19:33:46 | `outside_codex`: her second Claude session started Codex | `e31c8c3` |
| attempt-04 | `e31c8c3` | pilot 20/20 (`215d96a`); closed by me, no stop | Chunk admission re-hashed the whole tree: 691 s | `97062cd` |
| attempt-05 | `97062cd` | pilot (`11c99b5`); wixqa frozen (`42e559e`, one Codex-limit retry); code 2 at 11-05 03:36:31 on conditionalqa | False capture overlap | `4d37906` |
| **attempt-06** | `5a2d2fe` | **whole: 300/300** | — | below |

**Why attempt-05's stop was false.** The product killed a `low` call at its 60-s
timeout; by the kernel, the call was dead at 03:35:48.78. The driver's drain wrote the
time of its own check (03:36:31.82) as the call's end, so the next call, started at
03:35:47.48, "overlapped" it. The fix (`6d4e32f`):

- `Watch` holds a handle on every stand process it sees. This keeps the exit time
  readable and blocks PID reuse.
- `Runtime.exit_utc` takes the latest kernel exit of the shim's family, plus one clock
  tick (15.625 ms).
- The drain writes that exit, with reason `kernel_exit_time; …`.

The overlap rule stays strict. The Mac suite passed: 362 + 100. The spec amendment
(dated 2026-11-05) and the registration are in `5a2d2fe`.

**attempt-06**, per key:

| Commit | Time | Key | Result |
| --- | --- | --- | --- |
| `2f07562` | 11-05 05:12 | probe, pilot | Probe 19.9 s; pilot 20/20, route auto |
| `32ff420` | 07:19 | wixqa | 100/100 accepted (auto 96, human 4); none over 180 s; no stop; freeze 695 s |
| `86a6ab4` | 10:06 | conditionalqa | 100/100 (auto 93, human 7); none over 180 s; no stop; freeze 712 s |
| `4bf203a` | 13:54 | aircargo | 100/100 (auto 96, human 4); freeze 784 s; see below |

AirCargo's record also shows:

- **one infrastructure attempt** (`other 1`, 442 s, the only one over 180 s);
- **two stops**, both resolved and resumed;
- **three language mismatches.** This is a script-count heuristic, printed and deciding
  nothing.

At 11:17:59 Windows Update stalled the machine:

1. An embedding batch took 26 s instead of 0.3 s.
2. One question hung after its `low` call and reached the 420-s ceiling.
3. The stand stop's 10-s wait timed out, giving code 5 `verified_stop_failed` plus
   `state_stop`.
4. I diagnosed it and resumed: `chunk.sh run --key aircargo --resume-infrastructure`.
5. The question was asked again and accepted.

The stops list is series-wide, so every record file of attempt-06 repeats it.

One later chunk gave code 1 `ollama_observed`: Ollama's own updater had relaunched it
(08:01 laptop time). It was gone when I checked. Nothing was killed, and the next chunk
ran.

## My choices, not hers

- **Stand stop between chunks.** The stand holds about 6.8 GB at its peak. Stopping it
  between chunks frees memory for her other session. The cost is about 20 % more time,
  because each chunk's first question is cold.
- **Offline hashing in background mode.** Copy verification, registration and freeze ran
  through `D:/RAG_new_cx/ops/lowprio.py`, Windows background mode, outside the
  repository. They take about twice as long: attempt-06's registration took 46 min.
  Request chunks and grade chunks never run this way: it would double admission inside
  the budget.
- **Closing attempt-04 without a rule stop** for slow admission, and the stat cache. The
  cache uses git's index rule (size, mtime, file id). I kept frozen work — and so grade,
  export and the reader — on full hashing. That is the grading-speed risk above.
- **Fixing attempt-05's cause in the instrument**, not in the rule. The overlap check
  stays strict; only the time it reads is the true one.
- **No Codex executor during the series.** A Codex process on the laptop beside live
  chunks is what stopped attempt-03, and it costs memory. The in-series fixes were mine,
  reviewed on the Mac.
- **Recommending a new session** for judging, when she asked at 11:02.

## Next actions (in order)

Spell every command out with absolute paths. Shell variables do not persist between
Bash calls, and `--records` resolves against the working directory. `PY` below is
`D:/RAG_new_prod/venv/Scripts/python.exe`; always pass it `-B`. `COMMON` is:

```
--config D:/RAG_new_codex_quality_private/config-attempt-06.json --private D:/RAG_new_codex_quality_private --series attempt-06 --records D:/RAG_new/reports/codex-only-quality
```

1. **Preflight**, before the first grade chunk. The judge's route probe is one-shot: a
   failed probe is saved as `passed: false` with only an exception class as `reason`, and
   every later grade of attempt-06 then returns 5. So rule out the known causes first:
   - **Ask her one yes/no**: hold Claude Code updates until `reading.json` is committed
     (`DISABLE_AUTOUPDATER=1` in `~/.claude/settings.json` `env`; edit only on her yes).
     - Admission never compares `claude.exe` with the registration; before the probe,
       the manual check below is the only guard.
     - After the probe, a changed binary gives code 5 on every grade, and the reader
       refuses (row 1). Auto-update was not disabled on 11-05.
   - **The judge's binary.** Run
     `sha256sum C:/Users/uedom/AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe`.
     It must equal `6099672ebe5dcb518b67d1d32dde1e3360bc6bee1dae7f8d28a69c49acc7c865`,
     which is `reports/codex-only-quality/attempt-06/registration.json:401`, key
     `private_artifacts.claude_executable.sha256`. The file is dated 2026-10-27 and matched
     on 11-05. The `@anthropic-ai/claude-code` folder's mtime must not be recent (no
     update running). Re-check before each sitting.
   - **Plugins.** In `~/.claude/settings.json`, read only `enabledPlugins`: no
     `@claude-plugins-official` plugin may be `true`. On 11-05 figma was `false`. See the
     memory "Official plugins pass --safe-mode".
   - **The route and her usage windows.** Run
     `PY -B D:/RAG_new/.tmp/stage2/s2_route_probe.py`, one tiny request. It must say
     accepted.
     - The judge spends her Claude subscription, shared with this and her other session.
       390 requests at $69–110 is about 1–1.6 five-hour windows.
     - A refused or limit reply is written `unavailable`. Seven in a row give code 5.
     - Re-run the probe every ~10 chunks. At five-hour ≥ 0.85, or near her weekly line,
       stop the chunks and tell her.
     - Keep the laptop on mains with the lid open: a sleep mid-request is also an
       unavailable reply.
   - **The machine.**
     - `git status --short`: only `demo/phase-e-raw.webm` and `reports/ask100/` may be
       untracked; never commit them.
     - Free memory: `powershell -NoProfile -File D:/RAG_new/.tmp/cx-exec/mem.ps1`. Below
       about 1.5 GB, tell her.
     - `tasklist | grep -i ollama` must be empty.
     - No surviving `quality_driver.py`: the series lock does not wait, so a live one
       gives code 1.
     - `attempt-06/stand.json` holds `null` and nothing listens on port 8002; judging
       needs no stand.
2. **Grade wixqa**: `PY -I -X utf8 D:/RAG_new/.tmp/cx-exec/grade_a06.py wixqa`.
   - Run it in the foreground, one chunk per tool call, with `timeout` 1,200,000 ms.
     Background loops were reaped on low memory in stage 5в. Never use `lowprio.py`.
   - What the helper runs:
     `RAG_JUDGE_CLAUDE_CLI=<claude.exe above> PY -B -X utf8 D:/RAG_new/reports/codex-only-quality/tools/quality_driver.py grade COMMON --key wixqa --budget 600`,
     with cwd `D:/RAG_new` and `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` and
     `PYTHONDONTWRITEBYTECODE=1`.
   - If `attempt-06/<key>/<plan>/retry.json` holds a future `retry_at` (epoch s), the
     helper only waits and exits 3.
   - Status without a request: `grade_a06.py <key> --status`. On 11-05, wixqa showed m1
     0/115 and bridge 15/30. The bridge's 15 valid rows are stage 5в's vouched originals;
     its 15 retests are pending.
   - **Read the first chunk's seconds and new rows; that is the decision.** A request takes
     about 93–130 s. Requests start only while the 600 s, admission included, are not
     spent; one started may run on, so a chunk can outlast the tool's 20 min. If a call
     times out, wait until no `quality_driver.py` survives before the next.
     - Admission ≤ ~300 s (three or more requests a chunk): carry on. Grading takes about
       23 h over all keys.
     - Admission ≥ ~450 s (one or two requests a chunk): grading would take 36–72 h.
       - The better product path is a new series, attempt-07: grade admission on the
         request chunks' stat cache, export and the reader keeping the full hash, written
         with a test.
       - That costs about 9 h of answers (attempt-06: 04:44 → 13:54) plus about 13 h of
         grading, so ≈ 23 h in all.
       - Decide by the product goal, tell her the choice and why, and go on.
     - `3 foreground budget reached` with no new row and ≥ 600 s means admission ate the
       budget. Two such chunks in a row: stop and tell her.
   - **After the first chunk**, commit the public
     `reports/codex-only-quality/attempt-06/judge-route.json`. Every later grade and the
     reader check it.
   - Exit codes (`quality_freeze.grade`, stage 5в's `ceiling_judge.grade`):
     - **0**: key graded; go to export.
     - **3**: budget or `retry_at`; run the next chunk.
     - **5**: seven unavailable replies, the route refused, or the route receipt no
       longer admits (a changed `claude.exe`). Diagnose. `grade` has no
       `--resume-unavailable`. The only path that keeps attempt-06 is a hand reset of the
       private `<plan>/retry.json`: `consecutive_failures` 0, `retry_at` 0, `journal_rows`
       equal to the journal's row count. That equals stage 5в's flag
       (`ceiling_judge.py:407–409`). Do it only after the cause is gone, and record it
       as an operator action.
     - **2**: the judge clock (3 × 130 s × requests), or an unstable or missing plan.
       A `NOT_EVIDENCE.json` under any key stops **all** judging of attempt-06; every
       key then returns 2. Export the stopped key, skip the other grades, and run the
       reader (row 1).
     - **1**: refusal. Check for a surviving driver, then `git status --short`, then
       the registered files' hashes:
       `PY -I -B -c "import json,hashlib;r=json.load(open('D:/RAG_new/reports/codex-only-quality/attempt-06/registration.json',encoding='utf-8'));print([k for k,v in r['files'].items() if hashlib.sha256(open('D:/RAG_new/'+k,'rb').read()).hexdigest()!=v])"`.
       It printed `[]` on 11-05. A non-unavailable exception mid-grade also exits 1.
3. **Export wixqa**:
   `PY -B -X utf8 D:/RAG_new/reports/codex-only-quality/tools/quality_driver.py export COMMON --key wixqa`.
   It runs a full admission first (minutes) and writes `codex-only-wixqa-judge-m1.json`,
   `codex-only-wixqa-judge-m1.cases.jsonl` and `codex-only-wixqa-judge-bridge.json` under
   `reports/codex-only-quality/attempt-06/`. Commit them.
4. **conditionalqa, then aircargo**, as steps 2–3.
5. **The reader**: `PY -B -X utf8 D:/RAG_new/reports/codex-only-quality/tools/quality_read.py COMMON`.
   - Run it once with `run_in_background`, stdout to a file. It runs four full admissions,
     the R gate and seven 10,000-resample bootstraps, likely longer than 20 min.
   - It writes `reports/codex-only-quality/attempt-06/reading.json`; commit it.
   - Read `decision.row`, `q.pooled` and `r.pooled`, not the exit code. It exits 0 even
     on «NOT_EVIDENCE: invalid arguments or unavailable output/instruments».
   - Rows, from the spec's "The reading": 1 `NOT_EVIDENCE`, 2 below stage 5в's Codex
     reading, 3 holds.
6. **Status documents.**
   - New evidence is a new record-artifact test plus one `EVIDENCE_INDEX.md` row, as
     stage 5в's `591481f`.
   - The test goes in a **new** file; editing a registered test breaks admission. Under
     her word of 2026-10-30, Codex (cw) writes it after grading.
   - Update: a record in `docs/evidence/`, PLAN stage 6 item 0, `CURRENT_STATE.md` (in
     place, 150-line cap) and ROADMAP.
   - Provenance: release `19ecbbb`, registration `5a2d2fe`, and `config_sha256` and
     `copy_receipt_sha256` from `registration.json`.
   - Rule (c) holds for rows 2–3; row 1 is recorded as `NOT_EVIDENCE`.
   - Then the Mac docs tests (`test_docs_hygiene`, `test_docs_quality`,
     `test_docs_publication`) and a local commit.
7. **Push only on her word**: gitleaks and the shingle scan, a full `ci_local` PASS, and
   the Mac whole suite, mypy, bandit and pip-audit.

## Do not

- Start Ollama or any local LLM. Her words: «оллама парализует работу этой машины((».
- Run pytest or heavy work on the laptop.
- Push without her word.
- Commit `demo/phase-e-raw.webm` or `reports/ask100/`.
- Kill, unless you are sure they are yours:
  - other Claude sessions and their processes;
  - Codex brokers or app-servers (Informatica's are not ours);
  - the product's PostgreSQL (its data directory is under `D:/RAG_new_prod`) or her
    system PostgreSQL service.

  PIDs change after a reboot; identify a process by its command line. Never use
  `taskkill /T`; kill only by PID after an identity re-check.
- Print secrets: `D:/RAG_new_prod/secrets/*`, the stand `service*.env` values, auth files.
- Edit any path listed in `registration.json` `files`. There are 149, in `agent`, `api`,
  `config`, `deploy`, `evaluation`, `llm`, `resolution`, `scripts`, `static`, `vectordb`,
  `reports` (the tools, stage 4/5 records) and `docs` (the spec, generator-ceiling's spec
  and record, `windows-service.md`), plus eight tests. Also leave the
  stand clones (clean at `19ecbbb`) and the release venv alone. Any edit, a spec amendment
  included, ends attempt-06: grade, export and the reader then refuse (code 1), and the
  only way on is a new series.
- Restart a background job reaped for memory without her word.
- Run more than one agent at a time; always name its model. No MyFlow unless she names
  it.
- Clear the zombie job `task-mvxxv35t-nh4i5m`.

## State at the end

- HEAD is this handoff's commit, on top of the aircargo commit `4bf203a`. The tree is
  clean apart from the two untracked paths above.
- No background job, no stand, nothing on port 8002. The product service is not running;
  start it with `deploy/windows/start.py` only when she wants the product.
- Private series: `D:/RAG_new_codex_quality_private/attempt-06/`, holding `state.json`,
  `processes.jsonl`, `stat-cache.json`, `<key>/{m1,bridge}/plan.json` and
  `verdicts.jsonl`. Earlier series are kept as evidence of their stops.
- The operator scripts in `.tmp/cx-exec/` are git-ignored and outside the registration:
  - `chunk.sh`, `precheck.py`, `stop_stand.py`, `progress.py` and `grade_a06.py`;
  - logs `step4-a06.log` and `freeze-*-a06.out`.
- `D:/RAG_new_cx/s1` sits at `affd9c6`, in sync with `6d4e32f`. Its untracked
  `.cx_inputs/` stays.

## Lessons

- **A rule stop caused by my own instrument costs a whole series.** attempt-05 lost
  wixqa 100 and conditionalqa 78. A test that times a killed process must read the
  kernel's exit, not the observer's clock. Python 3.11 on this laptop lagged the kernel
  by 7.7 ms.
- **Time every phase under its real budget before registering.** Grade admission inside
  `--budget 600` was never run. This file's cold read found it after 300 answers.
- **Her other sessions are part of the environment.** Their short-lived pythons
  (attempt-01) and their Codex (attempt-03) both met rules written for an idle machine.
- **Admission cost scales with the tree.** Re-hashing took about 10 min; the stat cache
  brought request chunks to 31–90 s.
- **The laptop's own updaters act on their own.** Windows Update stalled a chunk into
  code 5, and Ollama's updater relaunched Ollama (code 1). Diagnose and resume.
- **Background mode doubles offline time but keeps her session usable.** Use it for
  hashing and freezing only.
- **Hook timestamps are UTC; `git log` is local, UTC−5.**

## Glossary

- **Series / attempt-NN**: one registration. A rule stop retires it; a new one starts
  with no carried answers.
- **Probe, pilot 1/5/20**: gates before the 300 questions. The *route probe* is the
  judge's one-shot check in the first grade chunk.
- **Request chunk**: one driver call, `--budget 1080`, about 7–10 questions. Codes: 0
  done, 1 refusal, 2 rule stop, 3 repeat, 5 infrastructure.
- **Grade chunk**: one `grade --budget 600` call, a full admission included.
- **Stand**: a verified copy of the product, started by the driver on port 8002.
- **Capture shim**: `capture_shim.exe` wraps every Codex call; the driver binds each call
  to its question.
- **Drain**: the driver's wait for a call's process tree to end.
- **Freeze**: writes `plans-<key>.json`, the judge plans: M1 115 (100 + 15 retests) and
  bridge 30 (15 vouched + 15 retests).
- **M1**: the judge's grade of an answer: good, partial_ok or bad.
- **Bridge**: re-grading of stage 5в's originals, for judge stability.
- **`retry_at`**: the judge's persisted 300-s pause after an unavailable reply.
- **Q**: answered good with context. **R**: gold coverage of the sent context.
- **`NOT_EVIDENCE`**: a stopped or unstable plan; it counts for nothing.
- **lowprio.py**: Windows background-mode launcher.

## Verification

- At 11-05 ≈ 14:00, `python -I -X utf8 D:/RAG_new/.tmp/cx-exec/progress.py` printed all
  three keys at accepted 100, whole True, retry_at None.
- `git log --oneline -2` shows this handoff on top of `4bf203a`.
- `grade_a06.py wixqa --status` gave m1 0/115 and bridge 15/30.
- The claude.exe SHA matched; the registered-files check printed `[]`.
- One cold read by an agent on the session's model checked this file against the code.
  It found the grading-speed risk, the one-shot probe, the usage windows, the
  series-wide code 2 and the reader's output; all of them are folded in above.
