# Session handoff 2026-10-25 — stage 2b closed (V4 adopted), stage 3's signals running

Session `5ec44b60`, 2026-10-25 08:54 UTC – (open). The laptop's clock and Julia's times are EDT
(UTC−4); the Mac's clock is UTC+3; the logs write UTC. Previous handoff:
[V4 running unattended](session-handoff-2026-10-24-v4-running.md).

## Read this first

- **A measurement is running on the Mac with no session watching it** — stage 3's signals
  (`scripts/chat_signals.py run`) on V4's 100 aircargo answers, started 17:26:57 UTC, forecast
  about 10 h from the first five answers (median 383 s), so done about 04:00 UTC on 10-26.
  Check it first ([Next actions](#next-actions), step 1). It resumes after the last answer row
  if it dies: the same command again.
- **While it runs:** no `sync.py`, no `remote.py`, no tests on the Mac — the record publishes
  the seconds each signal adds, and they count only from an idle Mac. Never stop another
  project's process (an idle `main.py` of `/Users/julia/atv2` has run there since 10-23).
- **Nothing is pushed** since `8fdbfee`. Local: `3422244`, `4f48fed`, `c2c5a58`, and this
  session's six commits ([State](#state-now)). A push needs Julia's word, after the whole Mac
  suite, mypy, bandit and the dependency audits (the locks need an update first).
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
- 10:58 — «на 204 запуска судьи хватит одного 5-ти часового окна?» Answered: yes, about 0.003
  of the window a request, so about 0.63 of one window.
- 11:02 — «новый лимит будет доступен примерно через 3 часа, тогда нужно и перезапустить
  процесс». Answered: no restart needed — the judge driver waits for the window's reset by
  itself; it resumed at 13:59 UTC on its own.

## My choices, not hers

- S7's threshold rule (`f520cde`): the plan said the threshold "is chosen on stage 1" and named
  no rule. Written before S7's scores were set against the verdicts: every distinct top score
  a candidate; among those over-marking at most 1 of 3 good answers, the one catching the most
  targets, a tie to the lower; a best catching none is no threshold. Chosen on these answers it
  stays a candidate (the plan's own rule).
- The record tool's form (`reports/handover-signal/tools/signal_record.py`, uncommitted): the
  judge's classes from the committed export `v4-aircargo-judge.cases.jsonl`, not the private
  verdicts — checked equal on all 100 in this session; the reading on unrounded Wilson limits;
  added time 0 for the signals without a model call, the claim check's seconds for S2 and S3,
  the grader's for S4, both for S6.
- S5 and S8 were not changed after their counts were seen (S5 marks 0, S8 8 — see below).

## What happened

1. **V4's judge, 620 requests** (08:58 – 17:07 UTC, $116.15, median 63 s): the WixQA and
   ConditionalQA plans frozen in `410a642` before their first grade, aircargo's in `d5f6e91`;
   the five-hour window filled at 10:41 (287 requests for 0.89); the driver waited and resumed
   at 13:59. The chain on the Mac ended `CHAIN_DONE` at 15:06 UTC. All plans and the three
   bridges counted by the stability rule (bridge κ: aircargo 1.0, WixQA 0.96, ConditionalQA 0.69).
2. **Stage 2b's record, `df60777`:** adopted. Pooled external bad share 127 → 108 of 200
   (−9.5 pp; −15.7 to −3.1), detected; WixQA bad 63 → 51 and good 27 → 40 detected;
   ConditionalQA and aircargo moves not detected. Near the line, deciding nothing: ConditionalQA
   declines 4 of its 20 not answerable questions (V3 8; upper limit +0.4 pp); aircargo's nine
   good answers turned bad, eight by one or two unsupported claims. Mac: 99 passed.
3. **S8 in the signal tool, `d260d95`** (the plan asked for it before 1.3): the answer's script,
   by `tests/test_stage1_live_artifact.py`'s rule; tests in `tests/test_chat_signals.py`. Mac:
   39 passed with stage 1's artifact test and the three docs tests.
4. **The signal plan, `b7ad62a`:** `reports/handover-signal/d260d95/plan.json` (SHA-256
   `30e0a598…df16e`), built on the Mac from the stand's run folders, before the first model
   call; no text in it; every prompt's SHA-256 equal to the judge plan's.
5. **S7's rule, `f520cde`**, then the run, launched 17:26:57 UTC.

## What is already known (no model call needed)

17 of the 100 answers are targets — all bad, none declined (V4 declined no aircargo question)
— over the plan's minimum of 15, so the reading applies. Good, non-declining: 63; partial: 20.

| Signal | Marked | Caught of 17 | Over-marked of 63 | Reading |
|---|---|---|---|---|
| S1 self-score < 80 | 3 | 2 | 0 | useless |
| S1′ self-score < 100 | 14 | 3 | 4 | useless |
| S5 decline | 0 | 0 | 0 | useless |
| S7 rerank top < 0.981153 (the rule's) | 33 | 4 | 19 | useless |
| S8 answer's script | 8 | 3 | 4 | useless |

The reading (frozen): **worth wiring** — caught ≥ 2/3 with Wilson's lower limit ≥ 1/3 and
over-marked ≤ 1/3; **useless** — Wilson's upper limit of caught < 1/2, or over-marked > 1/2;
otherwise **in between**. Every cheap signal's upper limit is below 1/2, so **outcome A
cannot happen** on these answers; the outcome is B if S2, S3, S4 or S6 is worth wiring, C if
none, and an in-between signal sends the reading on to the open parts of WixQA and
ConditionalQA (`PLAN.md` stage 3 step 2, 5–17 h of the Mac a hundred).

Two things to say plainly in the record: S8 counts letters, not language — all 8 answers it
marks are Russian, dense with Latin terms (AWB, field names); and S5's phrases are V2's and
the widget's, while V4 declines in its own words, so S5 could not fire (the plan left S5's
wording to stage 3 — settle it before any further reading, not on these answers).

First five rows (each: grader s, claim check s, total s; all routed `retry` by S6, no node
errors): 145/202/347, 289/229/518, 302/81/383, 83/235/318, then total 403. The cap is now
3 × 383 = 1,149 s an answer.

## State now

- **Commits this session (local):** `410a642`, `d5f6e91` (plans' hashes), `df60777` (stage
  2b's record), `d260d95` (S8), `b7ad62a` (the signal plan), `f520cde` (S7's rule), `a383318`
  (this handoff), `b557082` (the locks refreshed: CI's pip-audit clean on `requirements.lock`,
  the npm gate DEP-01 PASS; filelock 3 → 4 and astro 7.2 → 7.3 are the risky moves).
- **Uncommitted, in the tree:** `reports/handover-signal/tools/signal_record.py` and
  `tests/test_handover_signal_record_artifact.py` — they wait for the rows; ruff clean, not yet
  run on real rows. Also untracked and not this session's: `demo/phase-e-raw.webm`,
  `reports/ask100/`.
- **The Mac:** workspace `/Users/julia/RAG_new_signals_d260d95` (a `git archive` of `d260d95`
  with `CODE_SHA`); the run reads the stand's folders
  `/Users/julia/RAG_new_chat_4f48fed/chatlive/runs/v4-aircargo-b01…b10`; it writes
  `signals/out.jsonl` and `signals/run.log`; interpreter
  `/Users/julia/RAG_Support_Assistant/.venv/bin/python`; under `caffeinate`, `nohup`.
- **Private, on the laptop only:** `D:/RAG_new_stage2_private/v4/` (runs and verdicts).
- **Backup:** the git-ignored `.tmp/v4/` scripts and the two uncommitted files in the local
  branch `wip/stage3-signals` (see Verification); nothing pushed.

## Next actions

1. **Check the run** (any time):
   `ssh deproject-mac 'tail -c 300 /Users/julia/RAG_new_signals_d260d95/signals/out.jsonl; grep -c "\"kind\": \"answer\"" /Users/julia/RAG_new_signals_d260d95/signals/out.jsonl; pgrep -f "chat_signals run"'`.
   A `stop` row means an answer passed the cap: read it before resuming. Dead without `end`:
   `ssh deproject-mac 'cd /Users/julia/RAG_new_signals_d260d95 && nohup caffeinate -dimsu /Users/julia/RAG_Support_Assistant/.venv/bin/python -m scripts.chat_signals run signals/plan.json signals/out.jsonl >> signals/run.log 2>&1 < /dev/null &'`
   — it resumes after the done items. Run it with the Bash tool's `run_in_background`, or the
   ssh channel stays open (the `&` list keeps ssh's output).
2. **After `end`:** copy the rows as they are —
   `scp deproject-mac:/Users/julia/RAG_new_signals_d260d95/signals/out.jsonl D:/RAG_new/reports/handover-signal/d260d95/signals.jsonl` —
   check that `node_errors` hold no answer text, then build the record:
   `python -I -X utf8 D:/RAG_new/reports/handover-signal/tools/signal_record.py D:/RAG_new/reports/handover-signal/d260d95`.
   Check the file has LF endings (the tool writes bytes).
3. **The capsule** `docs/evidence/handover-signal-v4-aircargo.md` (not the root): the table
   per signal (caught, over-marked, marked, added seconds, reading), R2 and R3 with their
   counts (`findings`), the grader's outcomes and failures (`PLAN.md` stage 3 step 4 asks for
   their share), the outcome, the S5 and S8 notes above, "no person graded an answer". Add a
   capsule test to `tests/test_handover_signal_record_artifact.py` that prints from the record.
4. **One row in `EVIDENCE_INDEX.md`**; `CURRENT_STATE.md` (at its 150-line cap — edit in place),
   `ROADMAP.md` row 3, `PLAN.md` under stage 3, `BACKLOG.md`, `docs/README.md`. Then on the
   Mac (idle now): the new test, `tests/test_chat_signals.py`, the three docs tests; ruff;
   one commit.
5. **Tell Julia the outcome** by the plan's «What each outcome means»: B — she chooses how a
   check of minutes is wired (wait for it, show the button later, or check some answers); C —
   no signal finds them on this Mac with the 4B, and her options (a line under every answer, a
   route by topic, a stronger checker elsewhere). R1 and R2 are widget defects fixed with a
   test on her word; `PLAN.md` stage 3 step 4 adds ten widget answers on the 4B.
6. **Before any push:** on the idle Mac, `b557082`'s guards (`tests/test_pip_audit_floors.py`,
   `test_npm_audit_floors.py`, `test_docs_site_npm_audit.py`) and the site build on astro 7.3
   (`npm ci && npm run check && npm run build` in `docs-site/`, Chromium from the Playwright
   folder); then the whole Mac suite, both CI mypy commands, bandit, pip-audit, npm audit — and
   ask. Only CI installs the Linux lock; say so when asking.

## Do not

- Change S5's phrases, S8's rule or S7's rule and read them again on these 100 answers.
- Read `archive/` for routing; push without her word; run anything heavy on the laptop.
- Run `sync.py`/`remote.py` or tests on the Mac before the run's `end`.

## Lessons

- **Laptop JSON writers write CRLF; git commits LF.** Stage 2b's record first failed its own
  input-SHA test: `judge_export.py` ran on the laptop. Normalize with `write_bytes`, then build.
- **Mac `tar` adds AppleDouble `._*` files** that match `*-stream.txt`; `COPYFILE_DISABLE=1`.
- **`ssh host 'a && nohup b > f &'` holds the channel:** the backgrounded list keeps ssh's
  output. Closing the local ssh was safe — `nohup` kept the run alive (checked at once).
- **Look before the reading is final, not after:** the cheap signals' counts were read once
  the plan was frozen; nothing about them was changed.

## Glossary

- **Target** — an answer that needs a person: the judge's *bad*, or any decline.
- **Caught / over-marked** — targets marked / all targets; good non-declining answers marked /
  all of them; Wilson 95 % limits.
- **S1…S8** — the plan's signals; S2, S3, S4, S6 need the 4B (the widget's claim check,
  grader and first-pass route); the others need no model call.
- **Stand** — a `git archive` of one commit on the Mac; **workspace** here is the same for the
  signal tool's commit.

## Verification

- `git log --oneline -7` shows `f520cde` on top; `git status` shows the two uncommitted files.
- `git rev-parse wip/stage3-signals` gives the backup commit; restore a file with
  `git show wip/stage3-signals:<path> > <path>`.
- `sha256sum reports/handover-signal/d260d95/plan.json` gives `30e0a598…df16e`.
