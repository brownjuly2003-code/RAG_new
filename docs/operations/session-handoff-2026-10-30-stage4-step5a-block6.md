# Session handoff 2026-10-30, second — item 5a's blocks 2–5 passed and block 6 ran on; the audit of 2026-10-30 taken into PLAN; n-gram and stage 7 prepared for registration

> **Superseded** by the next session's handoff,
> [item 5a read, the n-gram lever closed, INT8's live series `NOT_EVIDENCE`; stage 7 step 1 registered; the package question open](session-handoff-2026-10-30-stage4-step5a-live.md),
> which keeps this file's glossary, the Mac's paths and «Do not» in force. Its next actions
> replace this file's.

The session ran 2026-10-30 10:03 – ≈ 13:25 UTC and was compacted six times. All times are
UTC; the laptop's clock is EDT (git's `-0400`) and the Mac's UTC+3. The previous handoff,
[block 1 passed](session-handoff-2026-10-30-stage4-step5a-block1.md), still holds for item 5a's
model, the series' exits, the record's steps, its glossary and its «Do not». Its next actions
1.1–1.3 are done. This file's next actions replace the rest.

## Read this first

- **Stage 4** cuts the chat's median answer of ≈ 320 s on the Mac (i5-7500, 4 cores, 8 GB).
  Its levers must lose no quality. Each is measured on the idle Mac and recorded, and none is
  adopted: that is Julia's word (PLAN §8.3; the reranker's runtime §9).
- **Item 5a's series, INT8 of the reranker, ran unattended to its end.**
  - Blocks 2–5, the speed ABBA on aircargo's thirty, passed their gates 10:03–10:54, each at
    its first attempt. PyTorch's blocks 2 and 5 gave stage 2's scores exactly: the largest
    difference was 0.
  - Block 6, `int8` on the 400 for the fives and the gold, ran 10:54:12–12:40:25. The series
    then ended with `SERIES_DONE`, and none of its processes is left on the Mac.
  - **No reading exists yet.** The speed, the fives and the gold come only from the tool's `read`.
- **Julia's audit of 2026-10-30,** [`audit_astra_30_10_26.md`](audit_astra_30_10_26.md), was
  read and checked against the files. It is gpt-6-astra's audit of HEAD `83eac79` against PLAN's
  definition of done, with findings F1–F7. What held went into PLAN as 8 edits, each changed
  place marked «правка 30.10» ([below](#the-audit-in-plan)).
- **Prepared, not committed:** the n-gram lever's spec, tool and test, cold-read (1 blocking
  finding, 1 to fix, 10 minor); stage 7 step 1, rewritten to PLAN's gate, its cold read packed;
  the help page's badge text (F2) and its browser test, the gate not run; the 5a record's
  builders, capsule skeleton and gate scripts.
- **Committed at the stop point,** after the docs gate on the Mac: PLAN's audit edits with the
  audit, the n-gram cold read, this file, block 1's superseded note, the status lines and
  docs/README ([State at the end](#state-at-the-end)).
- **Not pushed:** 44 commits after `7caaf21`. A push needs her word and a full
  ci_local run, and never runs during a live Mac measurement.
- **Open for her: one question, not yet asked — the lever package** (PLAN §8.3 item 2). Ask it
  once 5a and n-gram are read, before stage 7's replay runs. Since the audit, PLAN ties two
  more things to it:
  - INT8, already a lever «с её настройкой», also joins K 14 and 3,584 in the one re-answer
    (item 6 and stage 5) if its five changes on any question (F4);
  - items 6–7 measure the whole adopted package at once.

  At 10:46 I told her that the first release's composition would go into that one question.
  That was wrong: PLAN §8.3 item 3 asks it at stage 6, with stages 4–5's numbers, which do not
  exist when the package is asked. The package question stays one yes/no on one recommended
  package.

## Julia's words in this session (UTC)

- 10:03 «продолжи с docs/operations/session-handoff-2026-10-30-stage4-step5a-block1.md, Next
  actions по порядку». Next action 1 began: the series' start, then the wait.
- 10:40 «продолжи работу. docs/operations/audit_astra_30_10_26.md - изучи этот файл, есть ли в
  нем что-то ценное». My answer at 10:46: it is valuable, and its claims match the files.
  - **Taken** into PLAN ([below](#the-audit-in-plan)): F5, stage 7's draft opening answers on
    no detected loss, which at aircargo's ceiling opens almost always; F4, INT8's five changing
    while the gold holds is not «the same answers», and the package was never measured
    together; F2, `help.html:321`, fixed now, while `widget.html:377`'s «пары секунд» waits for
    the SLO; F7, CURRENT_STATE's line 99 alone is 5.5 KB of 20.9, shortened by 5a's record.
  - **Known or planned already:** the service, a push's fresh ci_local run, README's old
    numbers, the 17 bad answers' signals, mypy's memory guard. **Hers to weigh:** no acceptable
    quality for К yet; 15 of the 17 bad aircargo answers go `auto`; half the widget's questions
    end in `error_escalation` (one cause `agent/judge_policy.py`'s `no_independent_judge`);
    ≈ 33–52 h of the Mac to a limited pilot, ≈ 63 h more for stage 7's generative comparison.
- 10:53, mid-turn: «а план по ценному из ценного по аудиту ты проапдейтил?» It was not. PLAN
  got the 8 edits by 10:58.
- 11:33, mid-turn: «сессия длинная. поставь точку, где логично и обнови доку» — this stop point,
  at block 6's end, my choice. Earlier, the docs gate had no idle Mac, and at 10:58 I had told
  her PLAN's edits would be committed after `SERIES_DONE`. Later, the read starts the record's
  work: new work, best begun from this file.

## What this session did

No commits before the stop point.
- **10:03,** the series resumed (`rm $O/stop`, `bash -s 6`); **10:40–10:58,** the audit read,
  PLAN's 8 edits and docs/README's entry.
- **Laptop work beside the series:** the n-gram lever's spec, tool and test, frozen in
  `.tmp/coldread-ngram/` and cold-read; stage 7 step 1 rewritten to PLAN's gate, frozen with S's
  fix in `.tmp/coldread-s7/` with its brief `PROMPT.md`; `static/help.html:321` and its new
  test; 5a's record builders and the gate scripts in `.tmp/s5a/`.
- **12:12–12:48,** this file's cold read, one subagent: 19 findings, 1 blocking, all applied.

## Item 5a at the stop

`$O/series.log` since block 1:

```
2026-10-30T10:03:53+00:00 block 2 pytorch thirty, attempt 1
2026-10-30T10:22:00+00:00 block 2 read: largest difference from the record 0.000e+00
2026-10-30T10:22:00+00:00 block 3 int8 thirty, attempt 1
2026-10-30T10:30:25+00:00 block 3 read: largest difference from the record 1.754e-01
2026-10-30T10:30:25+00:00 block 4 int8 thirty, attempt 1
2026-10-30T10:38:26+00:00 block 4 read: largest difference from the record 1.754e-01
2026-10-30T10:38:26+00:00 block 5 pytorch thirty, attempt 1
2026-10-30T10:54:12+00:00 block 5 read: largest difference from the record 0.000e+00
2026-10-30T10:54:12+00:00 block 6 int8 all, attempt 1
2026-10-30T12:40:25+00:00 block 6 read: largest difference from the record 2.752e-01
2026-10-30T12:40:25+00:00 SERIES_DONE
```

- **Minutes against the forecast:**
  - PyTorch's blocks 2 and 5 took 18.1 and 15.8, against ≈ 14.5;
  - `int8`'s blocks 3 and 4 took 8.4 and 8.0, against ≈ 8;
  - block 6 took 1.77 h, against ≈ 1.75.
- **`1.754e-01`** on blocks 3 and 4, and `2.752e-01` on block 6, are `int8`'s largest score
  differences from stage 2's PyTorch scores, on the thirty and on the 400. No gate reads them:
  the fidelity gates FP32 at 1e-3 and PyTorch at 1e-6. `int8` is read by its five and its gold.
  Moves this large may change some fives; only the read counts them.
- **What the record must now say** (PLAN item 5a, «Правка 30.10», F4):
  - on how many of the 400 `int8`'s five is not PyTorch's, by both counts in
    `by_base[<base>]["6"]` (block 11 for `int8_u8u8`) against `questions`: `same_five`, the
    same set, and `same_order`, the same list (`int8_reranker.py:643–644`). F4 reads
    `same_order`, unless the code that builds the prompt is shown not to depend on the order;
  - if any differs, the conclusion is «эталон держится», not «ответы те же», and INT8 then
    changes the answer's path: item 6 and stage 5, like K and the window;
  - the table builders and `print_tables.py` read `variants.int8` only: if the fallback
    passes, give them the variant as a parameter.
- **Prepared for the record** in `.tmp/s5a/`, git-ignored and in the wip branch:
  - **`test_stage4_step5a_artifact.py`,** the artifact test's draft on
    `tests/test_k_curve_artifact.py`'s model: the provenance checks, a builder for each capsule
    table from `record.json` (`reading_rows`, `pair_row`, `gold_rows`, `fives_rows`, `block_rows`,
    `file_rows`) and `test_the_capsule_tables_are_the_records`. The forecast rows and the prose
    phrases wait for the numbers; it moves to `tests/` with the record.
  - **`print_tables.py`** prints those tables. The 5a tool imports `resource`, which is Unix
    only, so the tables are made on the Mac in the gate checkout:
    - first `cp D:/RAG_new/.tmp/s5a/test_stage4_step5a_artifact.py D:/RAG_new/tests/`, then
      ship the record and the test there:
      `python D:/RAG_new/.tmp/s4p4/tool_gate.py s5atables reports/stage4-step5a/d9f9fd8/record.json reports/stage4-step5a/d9f9fd8/rows.jsonl tests/test_stage4_step5a_artifact.py -- tests/test_stage4_step5a_tools.py`.
      Not `rec_gate.py`: its first file, the capsule, does not exist yet, and `tool_gate.py`
      stops on a missing file;
    - then run
      `ssh deproject-mac 'cd /Users/julia/RAG_new_mf_gate; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/julia/RAG_new_mf_gate_site /Users/julia/RAG_new_gr4_venv/bin/python - tests/test_stage4_step5a_artifact.py' < D:/RAG_new/.tmp/s5a/print_tables.py`.
  - **`capsule_draft.md`,** the capsule's skeleton on step 5's model, with `{{…}}` slots.
  - **`state_lines.md`,** CURRENT_STATE line 4 and line 99 rewritten short (F7), with slots.
  - **`rec_gate.py`,** the record's Mac gate, 1.8's gate. Skip block 1's copy from
    `ev4b_gate.py`, which would overwrite it:
    - FILES: the capsule, the spec, the two record files, the artifact test, CURRENT_STATE,
      EVIDENCE_INDEX, PLAN, ROADMAP, BACKLOG and docs/README;
    - TESTS: `docs_gate.TESTS` (35 files) plus both 5a tests.

## The audit in PLAN

The 8 edits; each changed place carries «правка 30.10» in PLAN:

| Where in PLAN | What it says now |
|---|---|
| §2, criterion К | Beside the quality: the share of bad answers among `auto`; the level a pilot accepts is hers to name (F1). |
| Stage 4, item 5a, INT8 | The record names on how many questions INT8's five differs; if any, «эталон держится», and INT8 changes the path (F4). |
| Stage 4, item 5a, n-gram | The gain's ceiling is the decode: ≈ 19 of the answer call's ≈ 77 s (step 4b's medians). |
| Stage 4, items 6–7; stage 5 | Item 6's re-answer and stage 5's skip condition name K, the window, the prompt and INT8's changed fives; items 6 and 7 measure the adopted package at once, since levers measured apart do not add up (F4). |
| Stage 6, item 6 | `help.html`'s badge hint names the number the model's uncalibrated self-evaluation; this edit does not wait for the SLO (F2). |
| Stage 7, steps 1–2 | The replay takes minutes; its control is stage 4's adopted path, INT8's fives included. With no arm gaining more than the MDE, steps 2–3 do not run and the stage closes «остаётся H» (F4, F5). |
| §8.3, her decisions | Item 2: INT8, already a lever «с её настройкой», joins K 14 and 3,584 in the one re-answer if it changes fives (F4). Item 3, stage 6: the first release's composition and the share of bad `auto` answers a pilot accepts, with stages 4–5's numbers (F1, F3). |
| §11, rules | An experiment ends with a decision, and «leave it as it is» is an outcome. CURRENT_STATE holds the final configuration, the open decisions and the next checkable result (audit §5, F7). |

PLAN already held the rest of what the audit says: the widget's «пары секунд», the widget's R1
and the service. Those were not repeated.

## The n-gram lever

- **What the spec freezes,**
  [`stage4-step5a-ngram-decoding.md`](../specs/stage4-step5a-ngram-decoding.md):
  - the answer model's own runner (Ollama 0.33.2's `llama-server`, its arguments and its
    environment read from `ps`) started outside Ollama;
  - two arms, `base` and `ngram`, the latter with `--spec-type ngram-simple` at its defaults;
  - step 4b's thirteen aircargo prompts at num_ctx 4,096 and one warm-up, `seed` 1030 on every
    call;
  - five blocks: block 0, the chat's own call through Ollama on the warm-up and the first three
    questions, gives the fidelity; blocks 1–4 run `base`, `ngram`, `ngram`, `base` (ABBA).
- **What decides:**
  - **the speed:** per question, the milliseconds per written token, by the exact sign test;
  - **the answers:** are their bytes equal?
  - **the outcome:**
    - faster and byte-equal: a lever «с её настройкой», set by `LLAMA_ARG_SPEC_TYPE=ngram-simple`
      in `ollama serve`'s environment;
    - faster with different answers: it changes the path, like K;
    - not faster: the lever closes.
- **The forecast:** byte-equal, faster on 11–12 of 13, a ratio ≈ 1.15. The spec's «≈ 3 s
  saved» of the ≈ 18 s written is ≈ 2.3 s at that ratio (cold read finding 7), ≈ 3 % of the
  call. The run takes ≈ 1.5 h of the idle Mac.
- **The files,** untracked: the spec `f187cd8a…`,
  `reports/stage4-step5a-ngram/tools/ngram_decode.py` `b28bf03a…` and
  `tests/test_stage4_step5a_ngram_tools.py` `960a7e4d…`. The spec's SHA list names the last
  two; its Status reads «registered before the first request … in `<c>`», true only once the
  commit lands.
- **The cold read,**
  [`audit_opus55_30_10_26_ngram_spec.md`](audit_opus55_30_10_26_ngram_spec.md), kept verbatim
  and committed at the stop point, found twelve:
  - **1, blocking:** block 0's gate never passes: each runner Ollama starts gets a new random
    `LLAMA_MEDIA_MARKER`, and `runner_same` compares the whole environment with the one `inputs`
    read. The series would end 8, 8, 9, unread; the test's stand-in returns one runner twice.
  - **2, to fix:** an Ollama or `ps` error in `sample` or `idle` ends a block (8, then 9) or the
    series; the spec keeps such a question, marked disturbed.
  - **3–12, minor:** a direct call's prompt checks; an outcome case the spec leaves to the
    tool; the renderer and the parser; an empty environment accepted; the forecast's
    arithmetic and its reproduction; a clean worktree; the peak's sampling; two untested speed
    boundaries; the logs the Stops name.
  - **Each finding is applied or refuted** in writing in that file. Then change the tool, the
    test and the spec, run `ruff format` and `ruff check`, and only then recompute the SHA
    list: bytes changed after it fail the test's pin and cost a Mac round trip.
  - **Sources:** the files it cites are in `.tmp/ngram/src/` and `src2/`, Ollama v0.33.2 and
    llama.cpp `d222767c7`, downloaded and read as text only. My design notes are
    `.tmp/ngram/NOTES.md`.
- **Then:**
  1. `.tmp/s5a/ngram_gate.py` runs the n-gram test and the docs tests on the bytes to commit:
     the spec, the tool, the test and the cold read's file.
  2. Commit the registration, `spec(stage4-step5a-ngram): …`.
  3. A follow-up commit writes `<c>` into the spec and names the registration in PLAN,
     ROADMAP, docs/README and CURRENT_STATE, as `ee0226a` did for 5a, and reconciles PLAN's
     «≈ 19 из ≈ 77 с» with the spec's 17.8 of 74.5 s. It has its own docs gate: a script on
     `stop_gate2.py`'s model, with FILES the spec and the four files.
  4. Run the spec's «Running it» 1–5 on the idle Mac, after 5a's series, any fallback, 1.10's
     live series and the help gate have ended.
  5. The record.

## Stage 7 step 1

- **The model:** the [earlier handoff](session-handoff-2026-10-29-stage4-step2-running.md),
  «Stage 7 step 1: the arms at M3». It holds except for the gate, which now reads as follows.
- **G1, rewritten after F5 to PLAN's stage 7 step 2:**
  - an arm stops on a detected loss at any stop reading;
  - else a `NOT_EVIDENCE` leaves it `NOT_EVIDENCE`;
  - else it is open, and it qualifies with a detected gain at a stop reading. The stop readings
    are ConditionalQA, WixQA and their two pooled; MultiHop-RAG is advisory;
  - one arm goes to answers: the one qualifying alone, or of two, the larger pooled c − b at
    the two deciding bases, P on a tie;
  - an arm left `NOT_EVIDENCE` does not hold back one that qualifies;
  - none qualifying reads «H stays», or `NOT_EVIDENCE` while an arm without a loss is unread;
  - the replay decides when no arm qualifies on the external bases. Else aircargo's context
    judge is planned for each arm with a detected external gain and no detected loss, and the
    decision waits for `judged`.
- **Why aircargo cannot open the gate alone:** its M3 is at a ceiling. Under V3 at most 7 of its
  contexts are not «full», and a detected gain needs six of the seven turned and none lost
  (p = 0.031).
- **The control** is K 20, num_ctx 4,096 and PyTorch's fives today; PLAN wants stage 4's
  adopted path. So the replay runs after her package answer. If the package adopts K 14, 3,584
  or INT8 with changed fives, the spec and the tool take a registered amendment first: they fix
  K at 20 and the input limit at 2,636 (spec lines 55 and 150).
- **SHA-256 on disk:**
  - unchanged since the last handoff: S's fix `vectordb/_base_manager.py` `44cf16b6…` and
    `tests/test_graph_retriever.py` `49933e9d…`; GR-1b's `scripts/gr1b_stage_replay.py`
    `e5c987dc…`, `scripts/gr1b_seed_expansion.py` `5756955f…` and
    `tests/test_gr1b_stage_replay.py` `9e3cfe14…`;
  - rewritten this session: `reports/stage7/tools/arms_replay.py` `44bf47fe…`,
    `tests/test_stage7_arms_replay.py` `cfe43f1c…` and `docs/specs/stage7-step1-arms-m3.md`
    `86efa70c…`. These equal the frozen copies in `.tmp/coldread-s7/`.
- **Next:**
  1. Spec line 14 first: INT8's fives join what changes H, and a rerun needs an amendment.
     Copy the spec into `.tmp/coldread-s7/` again and rewrite its `MANIFEST.sha256`. Then the
     cold read: one subagent, briefed by `.tmp/coldread-s7/PROMPT.md`, writes
     `docs/operations/audit_opus55_<date>_stage7_gate.md`. Apply or refute each finding there.
  2. The registration edits, in this order:
     - the tool's docstring loses «(a draft, not registered)»;
     - the Status line becomes «registered…», and the test's pinned phrase follows it;
     - the spec's Records line 168 names the SHA list used;
     - `ruff format` and `ruff check`;
     - last, the SHA list of the tool and the test, which the test checks like the n-gram
       test. `vectordb/_base_manager.py`'s SHA goes into `record.json`, not into a test pin.
  3. `.tmp/s5a/s7_gate.py` on the free Mac: the spec's ten tests and `docs_gate.TESTS` on the
     bytes to commit, the cold read's file among them.
  4. One commit, `spec(stage7-step1): …`, of s7_gate's nine files: the spec, the tool, its test,
     S's fix with its test, GR-1b's three and the cold read. GR-1b's test fails without the fix.
  5. The follow-up commit with `<c>`, and the cold read's row in docs/README.
  6. After her package answer and the n-gram series, on the free Mac:
     `python D:/RAG_new/.tmp/mf-mac/sync.py`, then
     `python D:/RAG_new/.tmp/mf-mac/remote.py --site reports.stage7.tools.arms_replay replay`.
  7. The record.

## The help page's badge (F2)

- **The fix:** `static/help.html:321` (LF) now calls «Качество: 85» the model's own
  self-evaluation, not calibrated and not a probability of a right answer; a high number can be
  wrong as well; it names the «Передать оператору» button. The old line promised «Чем выше
  число, тем безопаснее автоматический ответ», while the classic self-evaluation flagged 2 of
  the 17 bad aircargo answers ([record](../evidence/handover-signal-v4-aircargo.md)).
- **The test:** `tests/test_help_quality_badge_playwright.py` opens the page in Chromium from a
  live uvicorn of `api.app`. It reads the badge's paragraph, then checks the new phrases and
  that the old claim is gone.
- **The gate,** on the free Mac:
  1. `sh D:/RAG_new/.tmp/s5a/help_gate.sh red tests/test_help_quality_badge_playwright.py` must
     fail on HEAD's page, on the test's own assertion (a new phrase missing or the old claim
     present), not on Chromium's or the server's start: read the failure line.
  2. `sh D:/RAG_new/.tmp/s5a/help_gate.sh green static/help.html tests/test_help_quality_badge_playwright.py`
     must print `BROWSER EXIT 0`, with no skip under `-rs`.

  Each run ships HEAD plus the files and first runs `test_admin_ui.py` and `test_a11y.py`
  through `remote.py`.
- **Then** one commit and a row in EVIDENCE_INDEX's Slices, rule (a): the UI changed, proven by
  an E2E test. The row touches a root file, so the docs tests run too: a script on
  `stop_gate2.py`'s model, with FILES the page, its test and `EVIDENCE_INDEX.md`.
- **Not touched:** the widget's «Обычно отвечаем в течение пары секунд»
  (`static/widget.html:377`). PLAN stage 6 item 6 replaces it with the SLO's promise.

## Next actions

1. **Item 5a.**
   1. Check the state:
      `ssh deproject-mac 'pgrep -fl "[i]nt8_reranker" || echo none; tail -n 3 /Users/julia/RAG_new_s4p5a_runs/series.log'`.
      Expect `none` and `SERIES_DONE` last; read the last line against the
      [block 1 handoff](session-handoff-2026-10-30-stage4-step5a-block1.md)'s exits table, 1.4.
   2. That file's 1.5–1.10, in order:
      - 1.5, the read;
      - 1.6, the fallback, only on `int8`'s gold loss;
      - 1.7, the copy;
      - 1.8, the record, with F4's sentence ([above](#item-5a-at-the-stop)) and line 99
        shortened from `state_lines.md`; its gate is the prepared `rec_gate.py`;
      - 1.9, tell her the outcome. If any five differs, that file's template gains: «эталон
        держится», not «ответы те же»; INT8 joins K and the window in the one re-answer, item
        6 (≈ 6–8 h of the Mac) and stage 5 (≈ 17–30 h). It adds nothing if K 14 or 3,584 is
        adopted anyway, and costs all ≈ 23–38 h if INT8 is the only path change. That file's
        «They reopen neither item 6 nor stage 5» is overturned by PLAN's F4 edit;
      - 1.10, after a pass, the short live series.

      `"pending"` after blocks 1–6 is the trap: read `variants.int8.quality.reading`.
2. **The help slice** ([above](#the-help-pages-badge-f2)), about 5 min of the Mac.
3. **The n-gram lever** ([above](#the-n-gram-lever)).
4. **The package question,** one yes/no, once 5a and n-gram are read
   ([above](#read-this-first)).
5. **Stage 7 step 1** ([above](#stage-7-step-1)): its cold read and registration need not wait
   for her answer; its run does.
6. **The push,** only on her word, after a full ci_local run.

**Do not.** The block 1 handoff's list holds. Also do not:
- run any Mac test, gate, ship or other job of ours while any measurement series runs: 5a's,
  its fallback, 1.10's live series, the n-gram series. A gate's pytest inside the n-gram series
  marks its questions disturbed; fewer than 10 readable of 13 is `NOT_EVIDENCE`, and the lever
  closes;
- run two of our Mac jobs at once: the n-gram series, the replay and the help gate each wait
  for the others;
- commit the n-gram or stage 7 files before their cold reads are applied and their Mac gates
  pass on the bytes committed;
- change the widget's promise before the SLO.

## State at the end

- **The Mac,** read at 12:41:
  - the series ended with `SERIES_DONE` at 12:40:25, unread. `$O/blocks/01.jsonl`–`06.jsonl`
    are kept, `$O/rejected/` is empty and there is no `$O/stop`;
  - no 5a process runs; Ollama holds no model; `~/.config/llama.cpp/` does not exist;
  - the worktree `$W` is at `d9f9fd8`, clean;
  - scratch that may go: `/Users/julia/RAG_new_s4p5a_dry` and
    `/Users/julia/RAG_new_ort/precheck`.
- **Committed at the stop point,** one commit:
  - PLAN's eight edits and the audit file;
  - the n-gram cold read's file, verbatim;
  - this file, and the superseded note in the block 1 handoff;
  - CURRENT_STATE lines 4, 99, 100 and 150, and BACKLOG's first item;
  - docs/README's entries for the audit and the n-gram cold read, and its latest handoff.
- **On the laptop, not committed:** stage 7 step 1's five files and GR-1b's three; the n-gram
  lever's three; the help page and its test; `.tmp/s5a/`, `.tmp/coldread-s7/`,
  `.tmp/coldread-ngram/`; `.tmp/ngram/` (`NOTES.md`, `copy_spans.py` for the forecast's count,
  and, kept out of the backup, the downloaded sources in `src/` and `src2/` and step 4b's files
  from the Mac in `s4p4b/`); from earlier sessions, `.tmp/s4p4/` (`tool_gate.py`,
  `docs_gate.py`) and `.tmp/ask100-split/sync_commit.py`.
- **Backup:** the branch `wip/stage4-step5a-block6-stop` ([Verification](#verification)).
- **No Monitor, agent or background job** of this session runs after it closes.
- **Not this session's:** `demo/phase-e-raw.webm` and `reports/ask100/`.

## Glossary

The block 1 handoff's glossary holds. New here:
- **The audit, F1–F7:** Julia's file `audit_astra_30_10_26.md`, gpt-6-astra's findings of
  2026-10-30:
  - F1: quality has no acceptable level;
  - F2: the self-evaluation does not secure the handover;
  - F3: the widget is a separate, unfinished path;
  - F4: separate speed-ups do not prove the final path;
  - F5: stage 7's draft widened the entry to costly measurements;
  - F6: the engineering checks are incomplete;
  - F7: the documents and the product's claims diverge.
- **H, S, P:**
  - H, today's hybrid path: BM25 and BGE-M3 → RRF → reranker → five → parent expansion;
  - S, the structural graph's section expansion;
  - P, P1b: H's five cut adaptively by the reranker's scores.
- **M3:** the gold evidence is in the context sent to the answer model («sent»,
  `retrieval_summary.coverage`).
- **MDE:** the smallest effect a sample can detect (PLAN §4.4). «М3 выросла больше MDE» reads
  as a detected gain: c > b at p < 0.05.
- **Stop reading, advisory:** a reading that can stop or open an arm (ConditionalQA, WixQA and
  their two pooled), against one that is only printed (MultiHop-RAG, the three pooled).
- **G1:** stage 7's gate from the replay to the answers. **«H stays»:** stage 7 closes with no
  arm.
- **The cold read:** a fresh subagent on this session's model reads a frozen copy of a rule I
  wrote before its registration; its findings stay verbatim in
  `docs/operations/audit_<model>_<date>_<topic>.md`, each applied or refuted there.
- **`<c>`:** the registering commit's SHA, written into a spec by the commit after it.
- **From earlier handoffs:** V3, V4, the answer prompts behind stage 2's answers
  (`QA_PROMPT_V3`) and the adopted fix (`QA_PROMPT_V4`); «full», «full or partial», the
  aircargo context judge's verdicts, the context holding all of the answer's evidence or part
  of it; R1, the widget's evaluation failing closed in production (the 4B has no independent
  judge), so every widget answer goes to a person; `auto`, the route on which an answer goes out
  without a person; S's fix, `vectordb/_base_manager.py`'s `_expand_graph_sections` rewritten
  for stage 7's S; GR-1b, the published structural graph replay, kept on the old expansion by
  `legacy_expand_graph_sections`.
- **b, c in stage 7:** questions where M3 holds under H only, under the arm only. The deciding
  bases are ConditionalQA and WixQA.
- **`judged`:** the tool's step that reads the aircargo context judge's verdicts into
  `judged.json`.
- **F4's sentence:** the record's count of changed fives and, if any, «эталон держится».
- **The docs gate:** `docs_gate.TESTS`, the 35 doc test files run on the Mac after a root `.md`
  changes.
- **n-gram's arms and blocks:**
  - `base` is the runner as Ollama starts it; `ngram` the same with
    `--spec-type ngram-simple`;
  - block 0 is the chat's own call through Ollama;
  - byte-equal means each base–ngram pair of blocks gives the same text on all thirteen.

## Lessons

- **What an audit is worth goes into PLAN in the turn that answers it.** I answered «ценное
  есть» with a list and edited nothing. She had to ask «ты проапдейтил?».
- **After rewriting a spec, grep each phrase its test pins.** The stage 7 test still pinned «E is
  a later step, behind its own probe and gate G2», which the spec had lost.
- **GNU tar reads `D:` as a host.** Pack on the laptop with Python's `tarfile`.
- **A gate I write quotes PLAN's rule, not my own reading of it.** The draft opened answers on
  no detected loss and broke ties by the prompts an arm changes. PLAN says «только если М3
  выросла больше MDE». The audit caught it (F5), not I.
- **Long preparation beside a running block fills the context.** This session was compacted
  six times in under three hours. Start the next one fresh from this file.
- **The wip branch goes on top of the stop commit.** Built before it, as at block 1, its restore
  command writes the stop point's docs back at their bytes before the gate.

## Verification

- **The series:** `series.log`'s lines above. At 11:37:15, `06.partial.jsonl` held 176 lines.
  At 12:41:26 the state above; `$O/blocks/01.jsonl`–`06.jsonl` had SHA-256 `3b6d2952…`,
  `009fce8c…`, `664119ab…`, `cfff1a88…`, `15d287da…` and `0dd0d8d2…`, the same at 12:58, when
  `06.jsonl` held 403 lines.
- **PLAN's edits:** `git diff -U0 PLAN.md` showed 11 changed places for the eight edits,
  each carrying «правка 30.10» or «Правка 30.10».
- **The drafts:** the SHA-256 above, by `sha256sum` at ≈ 11:40.
- **The stop point's commit:** `.tmp/s5a/stop_gate2.py` ran `docs_gate.TESTS` (35 files) on
  the Mac on its bytes. The commit message gives the count.
- **The wip branch:** `wip/stage4-step5a-block6-stop`, built on the stop point's commit right
  after it, by `.tmp/s5a/make_wip_backup2.sh` through a temporary index. A commit cannot name
  what comes after it: `git log -1` and `git diff --name-only` of the branch give its SHA and
  files.
  - It holds the drafts above, the previous backup's git-ignored files that still exist,
    `.tmp/s5a/`, `.tmp/coldread-s7/`, `.tmp/coldread-ngram/`, `.tmp/ask100-split/sync_commit.py`
    and `.tmp/ngram/`'s two.
  - The script compares each with disk by `git hash-object`. It is local and never pushed.
  - Restore only if the working tree lost them:
    `git -C D:/RAG_new diff --name-only wip/stage4-step5a-block6-stop~1 wip/stage4-step5a-block6-stop | xargs git -C D:/RAG_new restore --source=wip/stage4-step5a-block6-stop --worktree --`.
