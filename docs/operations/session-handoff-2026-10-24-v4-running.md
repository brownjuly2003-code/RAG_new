# Session handoff 2026-10-24 — stage 2b: V4 registered, its answers running unattended

Session `5685352c`, 2026-10-24 09:24 – 19:55 UTC. The laptop's clock and Julia's times are EDT
(UTC−4); the Mac's clock is UTC+3; the logs write UTC. Previous handoff:
[stage 2 collected](session-handoff-2026-10-23-stage2-collected.md).

## Read this first

- **A measurement is running on the Mac with no session watching it.** WixQA's V4 answers run
  under stage 2's driver; a chain script then runs ConditionalQA and aircargo by itself. Check
  it before anything else (the first of [Next actions](#next-actions)).
- **While it runs:** no `sync.py`, no `remote.py`, no tests on the Mac; one measurement at a
  time; never stop another project's process (other sessions run `sqlplus_e2e` and
  `NL_SQL_new_glm_cli` tests there). Reading the run folders over ssh is fine.
- **Nothing is pushed** since `8fdbfee`: `3422244`, `4f48fed` and this handoff's commit are
  local. A push needs Julia's word; CI cannot start (GitHub billing).
- **The plan of record** is [`docs/specs/answer-prompt-v4.md`](../specs/answer-prompt-v4.md),
  registered in `4f48fed` before V4's first request. Its decision table, the bridges, the
  environment check and the six pinned SHA-256 bind; a change is a marked error fix only.

## Why this stage exists

Stage 2 (closed 2026-10-24, [record](../evidence/stage2-record.md)) graded the chat's answers:
M1 bad 14, 64, 63 and 34 of 100 on aircargo, ConditionalQA, WixQA and MultiHop-RAG. Julia asked
«а почему результат такой ужасный????», then «надо разбираться и что-то решать» (2026-10-24,
the session before this one). The judge's notes found three of the answer prompt V3's own
instructions in the bad answers: decline when the documents answer only in part; refer the
customer to «a support specialist», whom no document names; cite with the placeholder «[N]».
Under her rule of 2026-10-19 («Прими решения сам из цели - лучший продукт в финале») the
session wrote `QA_PROMPT_V4` and registered a paired measurement: V4's answers to stage 2's
questions on stage 2's stand code and judge, question by question against V3's answers.
`PLAN.md` was amended the same day: stage 2b before stage 3. Stage 3 (the handover signals)
reads V4's answers if V4 stays, stage 2's otherwise. A model change stays hers, with numbers.

## Julia's words in this session (UTC)

- 09:24 — `/model` → Opus 5.5, effort max; «продолжи доработку».
- Before 11:06 — «запусти трех агентов параллельно, если есть задачи»: the Mac gates, the
  record tools, the accepted-risk review (→ `3422244`); a fourth agent, the spec's cold read.
- 12:41 — «продолжи работу», after a usage-limit stop.
- 17:30 — «процесс живой? можно ускорить?» Answered: alive; the slowness is the shared Mac,
  not V4 (see [Lessons](#lessons)); freeing the Mac is hers to decide.
- 18:38 — «можно закрыть сессию?» → her choice «Автозапуск на Mac (Recommended)»: after WixQA
  the Mac goes on by itself; the next session judges and builds the records.

## My choices, not hers

V4's wording; the paired design; the decision table (harm first, then `NOT_EVIDENCE`, adopted,
kept, not adopted); the bridges; the environment check; the judge driver's limits — at 0.90 of
the five-hour window it waits for the reset, at 0.85 of the week it stops (part 4's driver ran
to 0.99 after her «стоит их потратить» of 2026-10-23 — that was a window's rest, not a standing
rule); the chain's idle rule (stage 2's check, so another project's pytest makes it wait, up to
6 h a launch, then it stops).

## State at the end (2026-10-24 19:48 UTC)

**Commits** (local): `3422244` risk review; `4f48fed` V4's registration, 17 files — the prompt
(`agent/prompts.py`), both judges (`scripts/chat_answer_judge.py`, `scripts/context_judge.py`),
the E2E test and the judge test, the five tools in `reports/answer-prompt-v4/tools/` and their
test, the spec, `PLAN.md`, `ROADMAP.md`, `BACKLOG.md`, `CURRENT_STATE.md`, `docs/README.md`.
Gates on its tree: the Mac's focused set 203 passed; the whole unit suite 6,016 passed, 123
skipped; mypy (CI's two commands) and ruff clean. This handoff's commit adds `v4_chain.sh` and
the CURRENT_STATE lines. The docs tests did not run, because the Mac is measuring;
`.tmp/v4/docs_check.py` stood in on the laptop (line caps, root count, mojibake markers, links).
`tests/test_docs_hygiene.py`, `test_docs_quality.py` and `test_docs_publication.py` run on the
Mac once the chain is done, before any push.

**The stand:** `S=/Users/julia/RAG_new_chat_4f48fed` (`CODE_SHA` `4f48fed5d8d1…`), raised by
`raise_stand.sh`: its product diff against `5e308fe` holds only the files the spec allows (the
prompt, both judges, two CI files' comments). Environment line 1 (13:12:15Z): Ollama 0.33.2,
one server (pid 12377, since 2026-09-13), 170 distributions, the freeze SHA the spec's, the
newest package 2026-05-30.

**WixQA** (`$S/chatlive/runs/v4-wixqa.log`; every row complete, path check clean):

| Batch | Start – end (UTC) | Note |
|---|---|---|
| b01, alone | 13:12:53 – 14:18:49 | ten stream prompts V4's; no «[N]», no «specialist» in them |
| b02 | 14:32:30 – 15:31:08 | |
| b03 | 15:31:16 – 16:40:09 | |
| b04 | 16:40:41 – 17:37:32 | one prompt with four context labels, not five |
| b05 | 17:38:03 – 18:44:50 | one prompt with four context labels |
| b06 | 18:45:21 – 19:46:08 | one prompt with four context labels |
| b07–b10 | from 19:46:38 | ≈ 62 min a batch → end ≈ 00:00 UTC 10-25 (20:00 EDT) |

The check's `labels` counts the documents in the answer prompt. Four means a question's
context held four documents; the longer V4 template (+61 tokens) can leave room for fewer. It
is part of what V4 does; the record's pairing shows on which questions V4 read V3's context.

**The chain** (Julia's «Автозапуск на Mac»): `reports/answer-prompt-v4/tools/v4_chain.sh`; a
copy runs from `C=/Users/julia/RAG_new_v4_control_20261024/` since 18:50:17 UTC (pid 37280),
log `$C/v4-chain.log`. It waits for WixQA's driver to end. Then it checks that WixQA is whole
(each batch's `LIVE_DONE … complete exit 0` and `CHECK … path_breaks {}`) and writes an
environment line. ConditionalQA and aircargo go the same way, one base after the other:

1. wait for an idle Mac, run batch 1 alone, check that its ten prompts are V4's;
2. wait for an idle Mac again, run batches 2–10;
3. check the base whole, write an environment line.

Any failure writes `CHAIN_STOP <reason>` and ends the chain. A failed batch is rerun by a
session only (stage 2's rule: once, `SUFFIX=-r2`, on an idle Mac).

Forecast at today's pace: ConditionalQA ≈ 10–11 h after WixQA, aircargo ≈ 9–11 h after it; the
last answer ≈ 20:00–23:00 UTC 10-25 (16:00–19:00 EDT). A free Mac makes it sooner; the idle
wait makes it later.

To stop: `touch $S/chatlive/runs/v4-<key>.stop` for the running base and for each base not yet
run (`stage2.sh` reads its file before every batch, the first included), and
`touch $C/v4-chain.stop`. The chain reads its own file only before its idle wait, so that file
alone can let the next base start.

**On the laptop, untracked, in `.tmp/v4/`:**

- the scripts: `run_v4_judge.py` (the judge driver, adapted from part 4's — one stream a plan,
  the plans in parallel, a plan's cap 3× its forecast; it calls
  `.tmp/stage2/s2_route_probe.py`), `v4_judge_plan.sh` (freezes a key's plans),
  `v4_copy_runs.sh` (copies a base's runs to the laptop);
- the dry runs: `smoke_record.py` with `smoke/` (v4_record.py on stage 2's records as a toy V4
  stand) and `marks/` (V3 marks for it — make the record's marks again with the committed
  `answer_marks.py`); `bridge-dry/` (dry exports of the three bridges);
- V4's times per question: `v4-wixqa-times.txt`, `v4-wixqa-stages.txt`.

These files, `docs_check.py` (the laptop's stand-in for the docs tests) and
`.tmp/stage2/s2_route_probe.py` are backed up in the local branch `wip/v4-judge-prep`, a commit
on this handoff's; it exists on the laptop only.
Restore:
`git diff --name-only wip/v4-judge-prep~1 wip/v4-judge-prep | xargs git restore --source=wip/v4-judge-prep --worktree --`.

**Private:** the bridges `D:/RAG_new_stage2_private/v4/judge/bridge-{aircargo,wixqa,
conditionalqa}/`, frozen; their SHA-256 are in the spec.

## Next actions

Laptop commands take absolute paths (the Bash tool keeps no `cd`). `$PY` is the laptop venv,
`C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe`.

1. **Status**, one ssh:
   `ssh deproject-mac 'tail -5 /Users/julia/RAG_new_v4_control_20261024/v4-chain.log; for k in wixqa conditionalqa aircargo; do f=/Users/julia/RAG_new_chat_4f48fed/chatlive/runs/v4-$k.log; [ -f $f ] && grep -HE "PART|LIVE_DONE|STOP" $f | tail -3; done; ps ax | grep "[v]4_chain"'`.
   No `v4_chain` process and no `CHAIN_DONE` in its log means the chain died; a killed chain
   writes no `CHAIN_STOP`.
2. **A `CHAIN_STOP` or a dead chain:** read the log it names, apply stage 2's rules
   ([spec](../specs/stage2-four-corpora.md#outcomes-and-what-julia-is-told)) and tell Julia.
   Do not start the chain again: it would begin anew with WixQA's check and ConditionalQA's
   batch 1. Go on by hand, one part at a time:
   - wait until `ssh deproject-mac 'sh /Users/julia/RAG_new_v4_control_20261024/v4_chain.sh check 10'`
     prints «idle»;
   - launch: `ssh deproject-mac "nohup sh /Users/julia/RAG_new_chat_4f48fed/chatlive/stage2.sh answers v4 KEY /Users/julia/RAG_new_external_s1 FROM TO >> /Users/julia/RAG_new_chat_4f48fed/chatlive/runs/v4-KEY.out 2>&1 </dev/null &"`.
     A new base runs batch 1 alone first; check its ten stream prompts as the chain's
     `v4prompts()` does. A failed batch reruns once, with `SUFFIX=-r2` before `sh` and
     FROM = TO. The copy and the plan then take `v4-KEY-bNN-r2` in its batch's place: edit the
     label in `v4_copy_runs.sh` and `v4_judge_plan.sh`;
   - after a base, write its environment line:
     `ssh deproject-mac '/Users/julia/RAG_Support_Assistant/.venv/bin/python /Users/julia/RAG_new_chat_4f48fed/reports/answer-prompt-v4/tools/stand_env.py >> /Users/julia/RAG_new_chat_4f48fed/chatlive/v4-environment.jsonl'`.
3. **WixQA's judge, once WixQA is whole.** It runs on the laptop while the Mac answers the next
   base.
   - `sh D:/RAG_new/.tmp/v4/v4_copy_runs.sh 4f48fed wixqa` copies the cases and stream prompts
     to `D:/RAG_new_stage2_private/v4/runs/`.
   - `sh D:/RAG_new/.tmp/v4/v4_judge_plan.sh wixqa` freezes the plans
     `D:/RAG_new_stage2_private/v4/judge/wixqa-m1` (references withheld) and `…/wixqa-m2`, and
     prints each `PLAN_SHA256`. Commit them in a commit message before the first grade, as
     stage 2 did in `8d827e5`. Use `git commit --allow-empty -F <msg>`, so that no root `.md`
     changes while the Mac measures.
   - Tell Julia the forecast: 245 requests (115 + 115 + the bridge's 15), ≈ 3 h at stage 2's
     90 s a request, ≈ $45 at its cost a request. Then run
     `$PY D:/RAG_new/.tmp/v4/run_v4_judge.py wixqa-m1 wixqa-m2 bridge-wixqa` in the background,
     with a Monitor on `D:/RAG_new/.tmp/v4/v4-judge.log`. The driver reads the usage windows
     itself. It ends with `ALL_PLANS_DONE` or `STREAMS_ENDED {codes}`. A stream's
     `STREAM_END <plan> exit N` means:
     - 2 — the route refused: read why in the log, then run the plan again; it resumes;
     - 4 — the plan is past 3× its forecast: tell Julia the pace;
     - 5 — the week reached 0.85: stop and tell her.
   - Export each plan into the stand's folder:
     `PYTHONPATH=D:/RAG_new $PY D:/RAG_new/reports/stage2/tools/judge_export.py export PLAN_DIR NAME D:/RAG_new/reports/answer-prompt-v4/4f48fed --run LABEL=DIR … --references D:/RAG_new_stage2_private/references/wixqa.jsonl`.
     `PLAN_DIR` is `D:/RAG_new_stage2_private/v4/judge/<plan>`. The plans `wixqa-m1` and
     `wixqa-m2` export as `v4-wixqa-judge-m1` and `v4-wixqa-judge-m2`, with the ten
     `v4-wixqa-bNN=D:/RAG_new_stage2_private/v4/runs/v4-wixqa-bNN`. The plan `bridge-wixqa`
     exports as `v4-bridge-wixqa`, with stage 2's ten
     `p4-wixqa-bNN=D:/RAG_new_stage2_private/p4/runs/p4-wixqa-bNN`; the dry bridge exports read
     the same copies. The export writes `NAME.json` and `NAME.cases.jsonl`.
   - Exit 3 from the export means the plan is not counted. Read `missing` and `retest` in what
     it prints. If verdicts are missing, run the driver again, then export again. If a V4 M1
     plan or a bridge fails the stability rule, row 2 holds unless harm shows on the counted
     keys, so V4 cannot stay. Tell Julia at once; the bases left can only add a harm read. An
     M2 plan that fails it decides nothing.
4. **WixQA's interim record**, in `D:/RAG_new/reports/answer-prompt-v4/4f48fed/` (`mkdir -p`
   it first):
   - the answers summary, made on the Mac, and the environment lines:
     `ssh deproject-mac '/Users/julia/RAG_Support_Assistant/.venv/bin/python /Users/julia/RAG_new_chat_4f48fed/chatlive/answers_summary.py v4-wixqa /Users/julia/RAG_new_external_s1 /Users/julia/RAG_new_v4_control_20261024/out'`,
     then
     `ssh deproject-mac 'tar cf - -C /Users/julia/RAG_new_v4_control_20261024/out v4-wixqa.json v4-wixqa.cases.jsonl -C /Users/julia/RAG_new_chat_4f48fed/chatlive v4-environment.jsonl' | tar xf - -C D:/RAG_new/reports/answer-prompt-v4/4f48fed`.
     The summary reads the generation's files for its provenance, so mind the base running
     beside it;
   - the marks of both sides, on the laptop:
     `$PY D:/RAG_new/reports/answer-prompt-v4/tools/answer_marks.py D:/RAG_new/reports/answer-prompt-v4/4f48fed/v4-wixqa.marks.jsonl $(for n in 01 02 03 04 05 06 07 08 09 10; do printf ' --run v4-wixqa-b%s=D:/RAG_new_stage2_private/v4/runs/v4-wixqa-b%s' $n $n; done)`,
     and `v3-wixqa.marks.jsonl` the same way over
     `p4-wixqa-bNN=D:/RAG_new_stage2_private/p4/runs/p4-wixqa-bNN`.

   Then
   `PYTHONPATH=D:/RAG_new $PY D:/RAG_new/reports/answer-prompt-v4/tools/v4_record.py D:/RAG_new/reports/answer-prompt-v4/4f48fed D:/RAG_new/.tmp/v4/interim-wixqa.json --keys wixqa`.
   Its inputs must be inside the repository; they need not be committed.
   - **Harm stops early** (the spec). Harm shows as a non-empty `harm`. Touch the stop files
     as «The chain» says and tell Julia. V3 returns, and the final record takes the judged
     keys only.
   - Without harm, an interim record prints `NOT_EVIDENCE` («not run whole, no harm read: …»).
     That is expected while bases are left.
5. ConditionalQA, then aircargo, the same way. Aircargo's plan `aircargo` exports as
   `v4-aircargo-judge`, with no `-m1`: that is the name `v4_record.py` reads. Its bridge
   `bridge-aircargo` exports as `v4-bridge-aircargo`, over
   `p1-aircargo-bNN=D:/RAG_new_stage2_private/p1/runs/p1-aircargo-bNN`. Neither takes
   `--references`.
6. **The final record** on the keys run whole → `reports/answer-prompt-v4/4f48fed/v4-record.json`;
   a test that derives each published number from it; a row in `EVIDENCE_INDEX.md` (rule (c));
   the decision: V4 stays (stage 3 on V4's answers), or a commit returns V3 with its E2E test.
7. **Before any push:** the docs tests, the whole suite, bandit, the dependency audits. The
   locks need an update: pip-audit and npm audit failed on `fc74f04` (2026-10-23) on advisories
   newer than the locks.

## Lessons

- **The shared Mac, not V4, makes the answers slow.** On b01–b03's 30 questions against stage
  2's same questions, the medians were:

  | Stage | V3 | V4 |
  |---|---|---|
  | retrieval | 68.6 s | 186.6 s |
  | rerank (part of retrieval) | 39.0 s | 114.0 s |
  | vector search (part of retrieval) | 30.2 s | 70.8 s |
  | model before its first token | 58.3 s | 68.3 s |
  | model after its first token | 92.3 s | 107.2 s |
  | tokens | 64 | 77 |

  Retrieval is the same code, so the cause is the machine. During the run its swap rose from
  1.4 GB to 8.9 GB used of 9.7 GB, with other projects' tests, Chrome, Yandex and Telemost
  open. At 19:00 UTC the load was 18.5/14.6/9.9, though the stand's python was the only busy
  process: the Mac was waiting on its disk. The answers stay valid: retrieval is
  deterministic, the path checks are clean, and time decides nothing. Do not compare V4's
  times with stage 2's; the record says so.
- **Idle is checked at launch, not between batches.** Between batches the driver waits only
  for free ports and an empty Ollama (up to 180 s). The chain adds stage 2's whole idle check
  before each base.
- **`pgrep -f` over ssh can find itself.** A compound remote command keeps its shell alive, and
  that shell's command line holds the pattern. Use `ps ax | grep "[v]4_chain"`.

## Glossary

- **V3, V4**: the answer prompt behind stage 2's answers (`QA_PROMPT_V3`) and its fix
  (`QA_PROMPT_V4`).
- **M1, M2**: the judge's grade without the gold reference, which decides, and with it, which
  is printed beside.
- **Plan**: a frozen list of judge requests (100 answers + 15 retests). **Retest**: a request
  repeated to test the judge's stability (kappa ≥ 0.6, or 13 of 15 agreeing with none two
  steps apart). A plan that fails it is `NOT_EVIDENCE`.
- **Bridge**: stage 2's 15 retested M1 requests of a key, graded again while V4's plans are
  graded. The stability rule then checks that the judge has not moved between the two sides.
- **Stand**: a `git archive` of one commit on the Mac. **Batch**: ten questions under one
  supervisor run. **Chain**: `v4_chain.sh`.
- **Driver**: `stage2.sh`, which runs a base's batches. **Judge driver**: `run_v4_judge.py`.
  **Part**: in stage 2, one of its five work items (part 4: the external bases' answers); in
  the driver's log (`PART`), one run of the driver.
- **Path check**: `answers_summary.py check`, run by the driver after each batch (the `CHECK`
  line). **Stream prompt**: the answer prompt the chat path sent, saved as
  `prompts/*-stream.txt`.
- **Harm**: row 1 of the spec's table. It holds when a base's bad share rises; when its good
  share falls and its bad share does not; when ConditionalQA declines fewer of the questions
  its gold says are not answerable; or when the pooled bad share rises.

## Verification at the end

At 19:48 UTC: `git log` shows `4f48fed` (09:11:35 EDT) on `3422244`. The stand's
environment line 1 reads as above. WixQA b01–b06 read as in the table, and b07 has started.
The chain's log holds `CHAIN_START` at 18:50:17Z, and `ps` shows pid 37280 running
`sh …/v4_chain.sh`. The chain's dry check on the Mac (`sh v4_chain.sh check 3`) printed
«wixqa batches 1-3 whole» and «v4-wixqa-b01: ten V4 prompts»; `sh -n` passes. The Mac's copy
of `v4_chain.sh` has the committed file's SHA-256 (`51b2f55f…`). The six pinned files' SHA-256,
in HEAD and in the tree, equal the spec's. The branch `wip/v4-judge-prep` is built after this
commit; `git log -1 wip/v4-judge-prep` shows it.
