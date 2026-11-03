# Session handoff — 2026-11-02 21:33 → 2026-11-03 ≈ 09:45 UTC: stage 5в answered whole, two keys graded, aircargo's judging paused

Previous: [session-handoff-2026-11-02-v6-record-publication.md](session-handoff-2026-11-02-v6-record-publication.md)
(its "After the handoff" section is where stage 5в begins).
Plan: [`PLAN.md`](../../PLAN.md) «Этап 5в». Spec: [`generator-ceiling.md`](../specs/generator-ceiling.md).
State: [`CURRENT_STATE.md`](../../CURRENT_STATE.md).

## Read this first

**The question.** The package — the 4B on the Mac with prompt V4 — gives few good answers on
the external bases, though the gold is often in the context it was sent. By M1 it gives 30
good of 100 on WixQA, 38 of 100 on ConditionalQA and 73 of 100 on aircargo. The gold is in
the sent context for 67 of 100, 58 of 80 and 99 of 100. So who loses the answers: the
generator or retrieval? Stage 5в answers it with a strong model given the **same** saved
prompts. Codex (profile cw, `gpt-6-astra`, effort `xhigh`) answers each of the 300 questions
once, in an isolated read-only task. The same judge as stage 5 (`claude-opus-5-5`, effort
max) grades the answers. The losses are then split by M3: gold in the context or not. This
is a diagnostic, not a production candidate. Production stays the 4B on the Mac until her
word.

**How the decision is read.** The registered primary is the pooled M1 **good** share among
the questions with the answer in the context: n = 67 + 58 + 99 = 224. The package has 120 of
them good. The difference is Codex minus the package. It is detected when the paired Newcombe
interval and the cluster-bootstrap interval both exclude zero on the same side. The spec's
table ("The reading"), first applicable row:

| Row | Outcome | What to tell Julia |
| --- | --- | --- |
| 1 | `NOT_EVIDENCE` — a key not answered whole, an arm stop, a missing, unstable or stopped plan or bridge, a refused hash | what fired; an amendment before any new request (Codex drafts it in `s1`, I review and commit it); only what it names is redone |
| 2 | the generator is the bottleneck — the primary share rises with Codex, detected | the next step is a strong model for the product; the host (GPU or an API instead of the Mac, D5) is hers; production stays the 4B until her word |
| 3 | the generator is not shown to be the bottleneck — all evidence counts and the rise is not detected | the next quality step is retrieval |

Row 3 also covers a detected **fall**: Codex below the package. Tell her that the strong
model answered no better on the same contexts, so the losses sit in retrieval or in the
contexts themselves. "Not detected" is not "no difference". The discordant fraction is
the share of the 224 questions where one side is good and the other is not; at 0.2 the
detectable difference is about 8.4 pp (spec, "Limits").

**Where the room is.** Among the 224, the package is not good on 48 of WixQA's 67, 30 of
ConditionalQA's 58 and 26 of aircargo's 99. So a rise, if any, comes mostly from the two
external bases. aircargo's "answer in context" is the package judge's `context_has_answer`
flag (item 6's M3 instrument), not a gold label as on the external bases.

**Where things stand.**

- **The arm is done.** 300 of 300 accepted: 0 redos, 0 counted out, 0 infrastructure
  failures, 2 language mismatches (the stop is at more than 5). Task median 25.8 s, p90
  34.7 s. Tokens: 5.43 M input (2.81 M cached), 125 k output, of them 85 k reasoning.
- **WixQA and ConditionalQA are graded and exported.**
  - Each key: M1 115/115, M2 115/115 and bridge 30/30 valid.
  - Bridge retest: WixQA quadratic kappa 0.923, agreement 13/15; ConditionalQA kappa 1.0,
    15/15. Both passed.
- **aircargo is half-started.** It has M1 and the bridge only, because it has no references.
  - bridge: 15 of 30 rows — the 15 saved grades of the package are in, and the 15 new
    requests are not yet made. M1: 8 of 115 valid, plus one `unavailable` row (`cli_exit`).
  - ≈ 122 requests remain: the bridge's 15 and M1's 107. That is about 1–1.5 h of foreground
    chunks: aircargo's M1 ran 24 s a request, WixQA's 46 s.
- **Nothing is read yet.** `ceiling_record.py` has not run, so there is no outcome.

**What to do first.** Resume aircargo's judging in foreground chunks ("Next actions"). Then
export aircargo and read. Then the record: Codex writes the capsule and its test in `s1`, I
write the status documents and commit locally.

## Julia's words in this session (UTC)

- 2026-11-02 21:33 — «Продолжи доработку, в качестве исполнителя  используй кодекс - astra 6 xhigh».
  The task was stage 5в, which she had approved at 21:15 with «да» (`cae46ee`). Codex wrote
  the spec, the tools and the tests in `s1`. I reviewed, ran the gates and the measurement,
  and committed.
- 2026-11-03 ≈ 09:30 — I reported the stop (below) and asked one yes/no: continue aircargo's
  grading in foreground chunks? Her answer: «давай продолжим в след сессии? важно ничего из
  сделанного не потерять».
  - **My reading:** a yes to resuming, deferred to the next session. The next session resumes
    aircargo's grading in foreground chunks after checking free memory, without asking again.
  - "Nothing lost" was done by this stop point: the receipts were committed, the private
    store and the helpers listed, and a local `wip/` branch built ("State at the end").

## What this session did (commit times UTC, all local, none pushed)

1. **Task 15 to Codex** (brief `D:/RAG_new_cx/briefs/s15-generator-ceiling.md`). Codex wrote
   five things:
   - the spec;
   - the tools `ceiling_common`, `ceiling_route`, `ceiling_answer`, `ceiling_judge` and
     `ceiling_record`, plus `wrapper.txt`, under `reports/generator-ceiling/tools/`;
   - `tests/test_generator_ceiling.py`.

   Repair round 1 came after my review. **`54a46e2`** (23:12) registered it all before the
   first request.
2. **The data-free probe** (series `attempt-01`) **stopped with code 5,** `cleanup_failure`.
   `TerminateProcess` returned error 5 on a `codex.exe` that was exiting by itself.
   - Repair rounds 2–3 (briefs `s15r2-repair.md`, `s15r3-repair.md`):
     - the cleanup counts a process whose handle has signalled as "exited by itself";
     - its second snapshot checks each candidate through its handle;
     - the tests got `raising=False` on `ctypes.get_last_error`, which is missing on macOS.
   - Mac gate: 504 passed. **`f93508a`** (23:32) is the amendment before the first corpus
     request. It refreshes the hash pins and keeps `attempt-01`'s receipts under
     `reports/generator-ceiling/attempt-01/`.
3. **Series `attempt-02`.**
   - Probe passed; pilot 20/20 accepted, p90 30.7 s, giving a task forecast of 60 s and a
     task stop of 180 s.
   - Then all 300, in background chunks of `ceiling_answer.py run … --budget 840`.
   - Plans frozen and committed before each key's first grade: **`e900f87`** WixQA 245
     requests, **`adb35a7`** ConditionalQA 245, **`3bb48dc`** aircargo 130.
4. **Grading.** WixQA ran 5 foreground and 16 background chunks, ConditionalQA 21 background
   chunks. Both are exported.
5. **aircargo stop** (09:25):
   - Claude Code reported the background grading loop killed for low laptop memory (2.1 GB
     free of 15.5); its processes ran on.
   - Chunk 1 had one `unavailable` request, and the judge persisted a 300-s `retry_at`.
   - My loop did not wait for it. Chunks 2–16 returned exit 3 within seconds and the loop
     ended at its cap.
   - Nothing is lost: verdicts are appended per reply. `.tmp/cx-exec/grade_chunk.py` now
     waits for `retry_at`.
6. **`31f29af`** commits the stop point's public receipts:
   - the arm summaries `arm.json` and `arm-<key>.json`;
   - WixQA's and ConditionalQA's metric, cases and bridge exports.

   All are text-free; the tools' public writers refuse question, answer, text, content,
   prompt and document fields. This handoff and its status lines are the next commit.

## My choices, not hers

- **The two language mismatches are kept and graded.** Both are aircargo:
  `aircargo-incident-response-bridge` and `aircargo-perishable-temperature-controls`. The
  questions are Russian with Latin product terms, so the letter count named them Latin by 3
  and by 2 letters, while the answers are Russian. The spec says «Keep and grade a language
  mismatch without redo. More than five among 300 stops the arm».
- **The cleanup amendment** went in before the first corpus request, as a registered
  amendment, rather than as a silent fix.
- **The receipts were committed at the stop point,** before the record. They will not
  change: the arm and both keys' judging are finished.
- **Foreground chunks for aircargo,** not a background loop: background jobs were reaped
  on low memory more than once in this stream (a Codex arm loop and aircargo's grading).

## Next actions (in order)

`$py` below is `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe`. Every tool command
runs under Git Bash with `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` and **without `-I`**: the tools
import their siblings (`ceiling_common` and others) from the script's folder, and `-I` drops
that folder from `sys.path`. `$args5v` is `--private D:/RAG_new_stage5v_private --series
attempt-02 --records D:/RAG_new/reports/generator-ceiling/attempt-02`. Always pass `--series
attempt-02`: `ceiling_record.py` defaults to `attempt-01`, the stopped probe.

1. **Check the laptop's free memory**: `powershell -NoProfile -File D:/RAG_new/.tmp/genscreen/procs.ps1`,
   whose first line is `free_mb=… total_mb=…`. The harness reaps background jobs, not
   foreground calls; the stop came at 2.1 GB free while the session sat idle. If `free_mb` is
   below ≈ 1,500, tell her before grading.
2. **Grade aircargo** with one chunk per tool call, foreground, `timeout` 1,200,000 ms:
   `$py -I -X utf8 D:/RAG_new/.tmp/cx-exec/grade_chunk.py aircargo`.
   - The helper may take `-I`: it imports nothing of the tools. It runs
     `$py D:/RAG_new/reports/generator-ceiling/tools/ceiling_judge.py grade aircargo $args5v --budget 600`
     with the right environment.
   - It prints `exit N | <the tool's last line>`, then `valid/rows` **written so far** per
     plan, not against the plan's size. `.tmp/cx-exec/judge_status.py`, run as
     `$py -I -X utf8 D:/RAG_new/.tmp/cx-exec/judge_status.py`, prints both.
   - It reads `D:/RAG_new_stage5v_private/attempt-02/aircargo/<plan>/retry.json`, whose
     `retry_at` is epoch seconds; this was checked on the live file. If that time lies ahead,
     the helper only waits and ends with exit 3. Run the next chunk.
   - Repeat until exit 0, about 10 chunks.
   - **Exit 5:** seven unavailable replies in a row. Look at the last rows' `reason` in
     `aircargo/<plan>/verdicts.jsonl`. `cli_exit` is the usual cause: the `claude` CLI exits,
     for example while Claude Code reinstalls itself. Check that one isolated probe answers;
     the stage 5 route is in the spec, "The arm", and in memory "CLI reinstall breaks a judge
     stream". Then resume with the tool directly:
     `$py D:/RAG_new/reports/generator-ceiling/tools/ceiling_judge.py grade aircargo $args5v --budget 600 --resume-unavailable`.
     That needs no word of hers: it is a resume, not a rule stop.
   - **Exit 2 — a rule stop:** a request clock or an unstable bridge. Do not grade again. The
     helper also prints `NOT_EVIDENCE <plan>` when the stop file exists. Go to steps 3–4: the
     outcome is row 1.
   - **Exit 1 — a refusal:** spec, tools or receipt changed in HEAD, or a hash differs.
     `git status` and `git log -1 -- docs/specs/generator-ceiling.md reports/generator-ceiling/tools`
     come first. Do not touch the spec or the tools until the record is committed. A Python
     traceback also gives exit 1; the helper prints the tool's stderr.
3. **Export aircargo**:
   `$py D:/RAG_new/reports/generator-ceiling/tools/ceiling_judge.py export aircargo $args5v`.
   It writes `ceiling-aircargo-judge-m1.{json,cases.jsonl}` and `ceiling-bridge-aircargo.json`
   into the records folder.
4. **Read**: `$py D:/RAG_new/reports/generator-ceiling/tools/ceiling_record.py $args5v`.
   - It writes `reading.json` into the records folder. The outcome is
     `reading.json["decision"]` (`row`, `outcome`); the primary numbers are
     `reading.json["primary"]`.
   - Exit 2 means row 1 with a stop fired. **Exit 0 does not mean row 2 or 3**: incomplete or
     refused evidence is row 1 with exit 0 too, so always read `decision.row`.
   - Commit the aircargo exports and `reading.json` as one receipts commit, the way `31f29af`
     was made.
5. **The record**, on the pattern of V6's `d60913d` and task 14's brief.
   - **No external-base ids or texts in `s1`.** The public exports and `reading.json` hold
     case ids, so they never enter the package. In their place goes
     `s1/.cx_inputs/ceiling-record-inputs.json`, untracked: the SHA-256 of every public file,
     the reading with ids and texts replaced by placeholders and per-case lists cut to one
     example, and the redacted shape of each export kind.
   - Build it on `.tmp/cx-exec/make_v6_inputs.py` and `redact_struct.py`, changing the paths to
     `reports/generator-ceiling/attempt-02/`.
   - Sync `s1` first with a copy of `.tmp/cx-exec/cx_sync_s15.py`. It copies only listed
     tracked files, by `git show HEAD:<path>`, then commits the sync in `s1`. List the status
     documents and any changed tools, not `reports/generator-ceiling/attempt-*`. `s1` is at
     `65052d7`, which is master's `f93508a`.
   - Brief a fresh Codex task: `--fresh`, because a stale job blocks `--resume-last`. Codex
     writes `docs/evidence/generator-ceiling-record.md` and
     `tests/test_generator_ceiling_record_artifact.py`. The test runs on the Mac in the full
     checkout and pins hashes and the capsule's numbers.
   - Copy the brief from `D:/RAG_new_cx/briefs/s14-v6-record.md`. It already carries the
     `.cx_inputs` rule, the capsule's shape and the "check every number" line.
   - Before the launch, read `C:/Users/uedom/.claude/skills_cold/codex-cw-runner/SKILL.md`. The
     launch is the companion `task --write --fresh --model gpt-6-astra --effort xhigh --cwd D:/RAG_new_cx/s1 --prompt-file <brief>`
     with `CODEX_HOME` set to the cw profile and the companion's endpoint variable unset. The
     brief gives our measured tokens/s (memory "Codex budget for research").
   - Review its diff, then copy the two files into RAG_new.
6. **Status documents** — mine:
   - `CURRENT_STATE.md` lines 4 and 150, in place at its 150-line cap;
   - one `EVIDENCE_INDEX.md` row with corpus, code and config provenance;
   - `PLAN.md` «Этап 5в» (the outcome) and `ROADMAP.md` row 5в;
   - `docs/README.md`.
7. **Mac gate.** Use the system `python` on the laptop, as in this session:
   - `python D:/RAG_new/.tmp/mf-mac/sync.py`;
   - `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py tests/test_generator_ceiling.py tests/test_generator_ceiling_record_artifact.py -q -p no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-ceiling-record --tb=short`.

   This session's run gave 126 passed in 29 s, without the new test. Then commit locally:
   the capsule, the test and the status documents.
8. **Tell Julia the outcome** and what it means for the next step. RAG_new is public since
   2026-11-02, so a push publishes. Ask one yes/no for the push. It needs both scans (secrets
   and external data, [stage 8 runbook](stage8-publication-runbook.md) §2 and §6) and a
   ci_local PASS.

## Do not

- Push without her word, and never push any `wip/*` branch.
- Run grading as a background loop, or restart a job stopped by the harness, without her word.
- Put external-base ids or texts into a Codex package: no public export, receipt or
  `reading.json` of `reports/generator-ceiling/attempt-*` enters `s1`. `.cx_inputs/` files
  are redacted and never committed; `ceiling-inputs.json` there is task 15's shape file.
- Commit `demo/phase-e-raw.webm` or `reports/ask100/`.
- Clear the stale companion job `task-mvxxv35t-nh4i5m` without asking her.
- Kill companion brokers by a list: the running ones include other projects' sessions
  (`D:/Dashs_astra`).
- Touch other projects' processes on the Mac.

## State at the end

- **Git.** `origin/master` is at `02b055a`. Local `master` is ahead by `cae46ee`, `0e266eb`,
  `54a46e2`, `f93508a`, `e900f87`, `adb35a7`, `3bb48dc`, `31f29af` and this handoff's
  commit; none is pushed.
- **The local backup branch `wip/stage5v-aircargo-judge-stop`** is built on that commit. It
  holds `.tmp/cx-exec/`'s helpers of this stream and a copy of the session LEDGER.
  `git log -1 wip/stage5v-aircargo-judge-stop` shows its SHA. It exists on the laptop only.
- **Private store** (outside git, never public, 81 MB): `D:/RAG_new_stage5v_private`. It
  holds:
  - `attempt-02/` — the arm's state, the runs and the judge folders `wixqa/`,
    `conditionalqa/` and `aircargo/{bridge,m1}`;
  - `companion-state/`, `attempt-01/` (the probe), `debug/`;
  - logs `arm-<key>.log` and `grade-<key>.log`.

  The inputs: `--s5 D:/RAG_new_stage5_private/2057ad0`, and `--i6
  D:/RAG_new_stage4_private/138f3b3` (a byte-exact copy of item 6's `runs/` and `judge/`).
- **Running jobs.** None in RAG_new: no grading, no Codex task, no monitor. Companion brokers
  run, some of them other projects'.
- **`s1`** is at `65052d7`, with `.cx_inputs/` untracked.

## Lessons

- **A loop around a judge with a persisted `retry_at` must wait for it.** Exit 3 means both
  "budget reached" and "pause ahead". The loop treated both as "go on": chunk 1 ran 09:21–09:25,
  and chunks 2–16 ended within 33 s.
- **Harness kills of background jobs on low memory recur.** The child processes survive, but
  nothing restarts them. Long grading belongs in foreground chunks; the single background
  slot is for Codex.
- **Windows process cleanup races with self-exit.** An access-denied error from
  `TerminateProcess` on a process whose handle has signalled means the process has already
  exited. Tests that patch Windows-only `ctypes` names need `raising=False`, or they fail on
  the Mac and in CI.
- **A diagnostic that searches command lines for a path finds itself** if that path is on its
  own command line. Build the pattern inside the script.

## Glossary

- **Arm** — the Codex answers, one isolated read-only task per question.
- **M1** — the judge's grade of an answer against its sent context: good, partial or bad,
  plus `context_has_answer`, claims and defects.
- **M2** — agreement with the reference; it needs references, so aircargo has none.
- **M3** — whether the gold is in the sent context: gold labels on WixQA and ConditionalQA,
  the judge's `context_has_answer` flag on aircargo.
- **Retest** — 15 of Codex's 100 answers graded a second time inside the M1 (and M2) plan:
  100 + 15 = 115 requests.
- **Bridge** — 15 of the package's saved M1 grades, plus 15 new grades of the same package
  answers made now. It checks that the judge grades as it did in stage 5. Stability, for both:
  at least 12 usable pairs and quadratic kappa ≥ 0.6, or agreement ≥ 13 of 15 with no
  two-step disagreement.
- **Plans receipt** — `plans-<key>.json`, hash-only and committed before the key's first grade.
- **Series** — one run of the arm and its judge, with its own private and public folders.
  `attempt-01` was the probe that stopped; `attempt-02` is the measurement.
- **s1** — `D:/RAG_new_cx/s1`, the data-free copy where Codex writes code.
- **cw** — the Codex profile `CODEX_HOME=C:/Users/uedom/.codex-work`.
- **Exit codes** — 0 done, 1 refusal, 2 rule stop, 3 budget or `retry_at`, 5 infrastructure.

## Verification

- `git -C D:/RAG_new log --oneline -10` shows the commits above; `git -C D:/RAG_new status --short` shows only
  `demo/phase-e-raw.webm` and `reports/ask100/`.
- `$py -I -X utf8 D:/RAG_new/.tmp/cx-exec/judge_status.py` should print:
  - WixQA and ConditionalQA: bridge 30/30, M1 115/115, M2 115/115;
  - aircargo: bridge 15/30, M1 8/115 with 9 rows.
- `$py -I -X utf8 D:/RAG_new/.tmp/cx-exec/arm_status.py D:/RAG_new_stage5v_private/attempt-02 D:/RAG_new/reports/generator-ceiling/attempt-02`
  should print `cases {'accepted': 300}`.
