# Session handoff 2026-10-29 — stage 4: step 2 running on the Mac; stage 7 and step 2b drafted

> **Superseded** by the next session's handoff,
> [step 2 and step 2b read, the continuation not adopted; the probe ready to register](session-handoff-2026-10-29-stage4-step2b-read.md),
> which keeps this file's model, glossary, «Do not» and «Once Julia answers» in force.

The session ran 2026-10-28 22:12 UTC – 2026-10-29 ≈ 10:10 UTC. All times are UTC; the laptop's
clock is EDT and the Mac's UTC+3. The previous handoff
([stage 4: step 0 read, step 1 measured, step 3 registered](session-handoff-2026-10-28-stage4-step1.md))
still holds for its model, its glossary and its «Do not». Its next actions 1 and 2, step 1's
record and step 3's runs, are done here. Its 3 and 4, step 4 and items 5–7, still wait.

## Read this first

- **What stage 4 asks.** The chat answers a question in a median of 320 s on the Mac. Stage 4
  finds where the time goes and cuts it with levers that lose no quality
  ([PLAN.md](../../PLAN.md) stage 4). Read so far, records linked from CURRENT_STATE: step 0,
  the 4B's growth is llama-server's host prompt cache; step 1, the rerank waits on the resident
  model's memory; step 3, K = 14 reranks a median 14.6 s faster than K = 20. No lever or K is
  adopted.
- **Step 2 is running on the Mac, unattended. Nothing of this session watches it.**
  - **What it asks.** The chat's self-evaluation, the badge «Качество: N» and the route, takes
    68 s. Today it is a request of its own, «the classic», which reads ≈ 2,400 prompt tokens
    from scratch. Step 2 asks for the same score as the answer chat's next turn, «the
    continuation», so llama-server can keep the answer's tokens in its slot. Is it faster, and
    does it route the same? Her word on the badge, 2026-10-28: «Оставить, но ускорить».
  - **The run.** `s2-both` started at 08:37:29 on stand `57420db` ([spec](../specs/stage4-step2-self-eval-continuation.md),
    registered in `f532c96`): 13 aircargo questions, each answer scored both ways.
  - **The first question read clean.** The continuation held, at 9.035 s against the classic's
    66.487 s (0.136), so the run went on. At 09:34, 4 of 13 were done.
  - **Contended from 09:00 to before 09:34.** Two pytest suites of other projects ran beside
    it ([below](#step-2-the-run-and-its-first-question)). Question 3 took 847.5 s and question
    4 1,165.4 s, near its 1,365-s cap, against question 2's 527.6 s. Nothing was stopped: the
    spec has no contention rule, and a pair's two sides share one answer a minute apart. But
    time numbers count only from an idle Mac (CURRENT_STATE's risks), so the seconds told to
    her name questions 3 and 4 as contended.
  - **Its end.** About 10:50–11:30; the spec's forecast was 10:02–10:22. Next action 1 reads
    it.
- **What step 2 decides, and what to tell her.** The reading gives a *candidate*, never a
  default. The default stays `classic` until step 2b reads.
  - **Continuation:** faster by the sign test, a median saving of at least 30 s, routes agreeing
    and scores held. Tell her the saving a question and the route agreement. Step 2b follows:
    the continuation re-scores the 80 labelled answers of stage 3. Its tools are drafted, its
    spec is not written (next action 3).
  - **Classic:** say which of the four rules failed. The badge keeps its 68 s, step 2 closes
    and item 4 is next.
  - **`NOT_EVIDENCE`:** fewer than ten readable pairs (ten compared, for the routes), the
    reader's gate failing twice, or two environment lines that differ. A 3× stop makes its
    unread questions `NOT_EVIDENCE`. Give her the measured pace and no verdict: the default
    stays `classic`, step 2b does not run, and another run needs an amendment of the spec,
    registered before its first request.
- **Stage 7, both arms by her «P1b и граф», is drafted on the laptop; nothing is registered or
  run.** The entity-extraction cost probe prices the full extraction the graph's entity lane E
  needs; revised after Codex's no-go, its second pass prepared, not launched. Step 1, the arms
  at M3 on stage 2's saved lists: a fix of S's section expansion, the replay tool, its test and
  a draft spec, which changes PLAN's gate for answers ([below](#stage-7-step-1-the-arms-at-m3)).
- **Research of 2026-10-29** ([README](research-2026-10-29/README.md)): five facts about
  Ollama 0.33.2 and its llama-server, read from the sources. They feed the probe's checks,
  item 5's cache cap and step 2.
- **Not pushed:** 19 commits after `7caaf21`, this handoff's the last. The push needs her word
  and ci_local's full run, which must not run during a live Mac measurement.
- **Open for her:**
  - **Asked at the end, one yes/no:** the host-cache cap of item 5, the one line
    `cache-ram = 1024` in `/Users/julia/.config/llama.cpp/config.ini`, for step 2b and the
    30-question series.
    - No restart of `ollama serve`: each llama-server reads the file when it starts. But the
      line acts on every llama.cpp program of her user, and a typo in it stops them all.
    - Why: step 0 found the cache is the 4B's growth and restored no state, so a cap loses no
      reuse, and the slot keeps its own prefix under any cap. 1024 MiB holds two or three states
      of ≈ 333–450 MiB, the answer's among them if a request comes between it and its score; 0
      is the floor if the series still swaps (`.tmp/agents/b_cache_ram.md`, from the source).
    - Step 2b needs it most: 80 cold continuations in a row fill the default 8,192 MiB after
      ≈ 20 ([below](#step-2b-the-80-labelled-answers)).
  - **Not asked:** the push; K, where I advise keeping 20 (14.6 s is ≈ 5 % of 320 s, and a new
    K reopens item 6 and stage 5: ≈ 23–38 h of the Mac, ≈ 330 judge requests; PLAN item 3); the
    SLO; stage 6's service; the widget's R1 and retry fixes.

## Julia's words in this session (UTC)

- 2026-10-28 22:15 «продолжи доработку. Что важно - закончить проект быстрее, но без потери
  качества. Можешь запускать трех своих субагентов параллельно. Кодекс сейчас доступен - можно
  тратить»: PLAN's order goes on, with three agents on the session's model at most; Codex
  (profile cw) gives second opinions and does web research, writes no code, grades nothing and
  gets no data of an external base ([CLAUDE.md](../../CLAUDE.md)).
- 22:30, her answers to my two questions:
  - the self-evaluation: «Оставить, но ускорить»;
  - stage 7: «P1b и граф», both arms, with the entity extraction's cost measured first.
- During my turns: «параллельно» (three times) and «продолжи», then «продолжи» again at 08:36.
- 08:59 «сессия очень длинная. поставь точку, где логично и обнови доку». The point: step 2
  runs on by itself after a clean first question, the drafts stop where they are and are backed
  up, the documents are updated. Step 2's end is the next session's first action.

## What this session did

| UTC | What |
|---|---|
| 22:21–23:12 | step 3's four runs, unattended; all four gates passed, its record read |
| 22:40–01:55 | an agent wrote the continuation's code; Codex read step 2's design (fix first, taken into the spec's «A second opinion») and the code («go»); a stage 7 survey, `.tmp/agents/stage7_survey.md` |
| 00:53 | `ec7984a`: step 1's record; 89 tests passed on the Mac |
| 02:27–02:32 | `1a793a4` step 3's record; `57420db` the continuation behind `STREAMING_SELF_EVAL_MODE`; `f532c96` step 2 registered; 177 tests passed on the Mac |
| 02:33 | stand `57420db` raised, its tools' SHA-256 matched; agents on step 2b's tools and stage 7 step 1 |
| 02:33–08:37 | the Mac busy with other projects (ci_local's VM, then two pytest suites); step 2 waited |
| 03:38–08:43 | the entity probe drafted; Codex: 12 findings, no-go; another agent revised it |
| by 04:44 | Codex's web research filed in `research-2026-10-29/` |
| 08:37:29 | step 2 launched by `.tmp/s2run/launch.sh` once the idle rule passed (load5 0.92) |
| 08:51 | its first question read: held, 0.136 |
| 09:00–09:34 | two other projects' pytest suites beside it |
| 09:00–10:10 | this stop point: the handoff, its cold read (19 findings, fixed), `close.sh`, the backup |

The network dropped at 00:38, 03:11 and 05:57–06:21; stopped agents were resumed with
SendMessage.

## Step 2: the run and its first question

- **On the Mac:**
  - `S=/Users/julia/RAG_new_chat_57420db`, `T=$S/step2`, `PY` and `IX` as in the
    [glossary](#glossary);
  - the run directory is `$T/runs/s2-both`, the supervisor's log `$T/runs/s2-both.supervisor.log`;
  - `nohup`, supervisor pid 59221;
  - `$T/environment.jsonl` holds the line written before the run.
- **How to look, light and safe during the run:**
  `ssh deproject-mac "bash -s -- 57420db s2-both" < D:/RAG_new/.tmp/s2run/q1_wait.sh`.
  - It prints `cases=<n> done=<0|1> alive=<n> last=<the log's last line>`.
  - `done=1` means a `LIVE_DONE` line, which the supervisor prints however the run ends. A
    complete run shows `last=LIVE_DONE s2-both complete exit 0`; `failed` is a stopped run.
  - `alive=0` with `done=0` is a run that ended without it: read the supervisor log's tail.
- **Its stops** ([spec «Stops»](../specs/stage4-step2-self-eval-continuation.md#stops)):
  - The supervisor stops a question past its cap by itself: 2,010 s for the first question,
    1,365 s for the others. It then stops the API and the database and unloads the model.
  - A run without `LIVE_DONE` at 3× its forecast, about 13:52, is stopped by hand:
    `pkill -f "[R]AG_new_chat_57420db/step2/live_runner.py"`, then closed as next action 1
    closes it. Its unread questions are `NOT_EVIDENCE`.
- **The first question,** `aircargo-probation-data`, read by `step2_reader.py` into
  `$T/s2-both.q1.step2.json`. Its stop is false and it gives no reasons.

| | Continuation | Classic |
|---|---|---|
| Seconds | 9.035 | 66.487 |
| Score | 100 | 100 |
| Prompt tokens / seconds | 2,660 / 8.10 | null |
| Generated tokens / seconds | 4 / 0.76 | null |

- The classic's counters are null because its call reports none (`_self_eval_entry`'s docstring
  in `api/routers/conversation.py`).
- Over the ask, the swap went from 1,938.5 to 2,170.25 MiB. llama-server's largest RSS was
  3,682.1 MiB.
- **My reading of the counters.** Ollama counted 2,660 prompt tokens and spent 8.10 s on them.
  At step 0's ≈ 28 ms a token that is ≈ 290 tokens read: the instruction and the turn markers.
  So the slot kept the answer's prefix, as the spec's «Why» predicts. Step 0's classic read
  2,377–2,690 tokens in 65–105 s.
- **The contention, seen at 09:14.**
  - `sqlplus_e2e`'s pytest has run since 09:00:46 (pids 63022, 63023).
  - `NL_SQL_new_glm_cli`'s pytest with coverage has run since 09:09:29 (pids 68246, 68255).
  - The load was 3.32 / 7.59 / 6.40; the swap used 3,811.75 of 4,608 MiB at 09:17.
  - Questions 2, 3 and 4 took 527.6, 847.5 and 1,165.4 s, their first tokens at 367.0, 574.3
    and 1,010.7 s.
  - At 09:34 neither suite ran any more, and the load was 3.12 / 5.51 / 5.31.
  - The samples, `resources.jsonl` every 3 s, which `step2.json` names by SHA-256, hold the
    load and, by pid, each `python`, `ollama`, `postgres` and `llama` process, with the five
    busiest by CPU and the five largest by RSS. A name is its path's last 40 characters, so a
    pytest shows as its interpreter, known by the pids above. The overlap marks are read from
    the samples' load and these pids, outside the frozen reading, and decide nothing.

## Next actions

The order: step 2's close, the tests that waited for the Mac, then step 2b if the continuation
wins. The probe is independent and short, so any idle gap fits it. Then PLAN items 4–7, and
stage 7 step 1 after item 4 (its reason is in 6).

1. **Close step 2** ([spec «Running it» 6, «Records»](../specs/stage4-step2-self-eval-continuation.md#records)),
   once `q1_wait.sh` prints `done=1`. Every number of the capsule comes from the copied
   `step2.json`, not from this handoff.
   1. `ssh deproject-mac "bash -s -- 57420db s2-both" < D:/RAG_new/.tmp/s2run/close.sh`. It
      refuses without `LIVE_DONE`, while the supervisor lives or over an existing `step2.json`;
      removes `$T/runs/s2-both.chroma`, appends the environment line after the run, runs the
      reader into `$T/step2.json` and prints what steps 2–4 read.
   2. The reader's gate must pass. A failed point follows the spec's step 6: a marked error fix
      and a new read, with `step2.json` moved aside, since the reader refuses an existing
      output; or the rerun `s2-both-r2`. Each script in `.tmp/s2run/` takes the label as its
      second argument, and `close.sh` then writes `step2.s2-both-r2.json`.
   3. The reader does not compare the environment lines: both must name Ollama 0.33.2 and one
      server, the same pid and start. Otherwise step 2 is `NOT_EVIDENCE`.
   4. `mkdir -p D:/RAG_new/reports/stage4-step2/57420db`, then copy the three files as bytes, a
      literal path each:
      `ssh deproject-mac "cat /Users/julia/RAG_new_chat_57420db/step2/step2.json" > D:/RAG_new/reports/stage4-step2/57420db/step2.json`,
      the same for `s2-both.q1.step2.json` and `environment.jsonl`. Compare `sha256sum` with
      `close.sh`'s `shasum -a 256`.
   5. Write the capsule `docs/evidence/stage4-step2-record.md`, modelled on step 3's: the
      question, the stand, the gate, the four rules with their numbers, the forecast against
      the outcome and «Not said». Beside the reading, deciding nothing: the asks that
      overlapped the other projects' pytest, and the reading without them.
   6. `tests/test_stage4_step2_artifact.py`, modelled on step 3's, and the `EVIDENCE_INDEX.md`
      row. The spec's Status line keeps «registered before the first request» on one line
      (`tests/test_stage4_step2_tools.py` pins it). PLAN item 2, ROADMAP's stage 4 row,
      CURRENT_STATE, BACKLOG and docs/README.
   7. Ruff on the laptop; on the Mac the artifact test, the tools test and the three docs tests.
      Commit as `evidence(stage4-step2): …`, then tell her as [Read this first](#read-this-first)
      says.
2. **The Mac tests that waited for the Mac**, once step 2 is closed and the Mac is idle. First
   `python D:/RAG_new/.tmp/mf-mac/sync.py`, then `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q -p no:schemathesis -p no:cacheprovider --tb=short <tests>`
   with:
   - the docs tests on this handoff's commit: `tests/test_docs_hygiene.py`,
     `tests/test_docs_quality.py`, `tests/test_docs_publication.py`;
   - the probe: `tests/test_stage7_entity_probe.py`;
   - step 2b: `tests/test_stage4_step2b_tools.py` with
     `--deselect tests/test_stage4_step2b_tools.py::test_the_spec_names_the_tools_and_the_readings_as_they_stand`
     until its spec exists;
   - stage 7 step 1: the ten files in section 4 of `.tmp/agents/e_stage7_step1_report.md`.
3. **Step 2b, only if step 2's candidate is the continuation.** Write its spec from
   `.tmp/agents/s2b_report.md`: the sections, the pinned phrases (each on one line), the SHA
   list, the paths and the order. Its host cache follows her yes/no («Once Julia answers»).
   Registration edits what its test pins as a draft («a draft», «`<the stand's commit>`», the
   module docstring), fills the reader's `CODE_SHA` and refreshes the SHA list. Then the Mac
   tests and the commit, before its first request.
4. **The probe** ([below](#the-entity-extraction-cost-probe)):
   1. Codex's second pass. Copy the three revised files into its package, scrubbed as the first
      pass's were. Launch it as `~/.claude/skills_cold/codex-cw-runner/SKILL.md` says, after a
      check for a live broker on that cwd.
   2. Its findings. Then the registration commit with `<c>`, then `<c>` filled in, with the
      PLAN, docs/README and CURRENT_STATE lines.
   3. Before its first run, on an idle Mac: load the model once, compare `/api/ps`'s digest with
      `/api/tags`'s, then unload it. A mismatch is a marked error fix of the probe, not a run.
   4. The run: ≈ 5 min of the Mac by the spec's forecast, ≈ 11 min if ≈ 6 s a chunk holds.
5. **PLAN items 4, 5, 5a, 6 and 7.** Item 5 starts on her word on the cap.
6. **Stage 7 step 1, after item 4.** Its replay builds V4's prompts and keeps V4's answers where
   a prompt does not change, and item 4 may shorten that prompt.
   1. Read the S fix and the spec draft.
   2. Run the Mac tests.
   3. On the Mac, show S's before and after on one stage-2 question, in the session only.
   4. Register in one commit: the fix, the tool, the test, the spec and PLAN's gate line, with
      the lines the agent lists. Registration edits the test's «**a draft, not registered**»
      and refreshes the SHA list. Tell her the gate's change in the same message.
   5. The replay, ≈ 10 min of the Mac, stopped at 30.
   6. The judge plan, ≤ 262 requests.

**Do not:**
- start a measurement on the Mac unless its spec's idle rule holds, or run tests or another
  heavy job there while a measurement is live;
- stop another project's process;
- stop step 2's run except by its spec's stops;
- open `.ask100-runtime/env.json` or any `.env`, or print `ollama serve`'s environment beyond
  its `OLLAMA_` and `LLAMA_` names;
- commit `demo/phase-e-raw.webm` or `reports/ask100/`, which are not this session's;
- commit an agent's draft unread or untested on the Mac;
- push without her word;
- reword a sentence an artifact test pins without a grep first.

**Once Julia answers:**
- **The cap, «да»:** the first spec to run under it, step 2b's or else item 5's, adds the line
  before its first request. If `/Users/julia/.config/llama.cpp/config.ini` exists, it is read
  first and only the line is added. A runner already in memory keeps 8,192 MiB until it
  unloads. The proof is `cache state … (limits: 1024.000 MiB …)` in the serve log,
  `/Users/julia/gr2_bench/ollama_serve.log`. The line goes after item 5's series unless she
  keeps it.
- **The cap, «нет»:** item 5 measures the other policy, unloading every N requests or at a swap
  threshold. Step 2b keeps production's cache or unloads between answers, ≈ 10–60 s a reload by
  the agent's estimate, and says which in «Not said».
- **The push:** ci_local tests the working tree as `git add -A` would commit it, so the drafts
  are registered first, or moved out and restored from the backup after. Then its full run
  (`python C:/Users/uedom/.claude/scripts/ci_local.py --repo D:/RAG_new`, in the background,
  once, never during a live Mac run) and the HTTPS push in [CLAUDE.md](../../CLAUDE.md).
- **K:** a new K is a change of the answer path: item 6 and stage 5 reopen.

## The entity-extraction cost probe

- **What it decides** (spec draft `docs/specs/stage7-entity-probe.md`, uncommitted). E reads
  entities a chunk. The probe times the product's own extraction path, `PinnedOllamaChat` with
  one JSON-schema `/api/chat` call a chunk, on 100 MultiHop-RAG chunks with an English prompt.
  - **Gate G2:** stop E if 11,231 chunks × the upper bound of the mean's 95 % interval exceed
    24 h (7.693 s a chunk), or if fewer than 95 of 100 outputs are valid.
  - The spec's forecast is ≈ 15–55 s a chunk, so G2 fails at the first look. GR-2's 7B, at
    11.4 s, argues for faster; the probe settles it.
  - A run that is broken or contaminated must not read as a clean fail: that would kill a
    retrieval mechanism.
- **Files,** untracked, SHA-256 on disk at the stop point:
  - `reports/stage7/tools/entity_probe.py`
    `25d48c9279371091e77b90b8a62ebe0676935faac2cf16b6b7340e6de47a9a9a`;
  - `tests/test_stage7_entity_probe.py`
    `78cfb61e5d1cd1485c51980821535bd6ce46897d5408888991b3624dfa9cbbc9`;
  - `docs/specs/stage7-entity-probe.md`, a draft with `<c>` placeholders.
- **What the revision changed,** after Codex's 12 findings: a 900-s cap a chat and a 3,000-s
  run cap, a cut chunk counted invalid; an early refusal (exit 3) on the stand; the idle rule at
  the start and contention checks after each chunk, our model alone in `/api/ps` by digest;
  stricter row and end checks. The spec's «A second opinion» has each change.
- **Its state:** ruff, mypy, compile and LF pass on the laptop; pytest has not run.
  - Codex's first review: `C:/Users/uedom/cxpkg/rag-s7probe-20261029.out`, lines 31–93; its
    finding 4, the hashes, came from the package's home-path scrub.
  - The second pass, `C:/Users/uedom/cxpkg/rag-s7probe2-20261029/`, holds `BRIEF.md`, the four
    product files, `previous_review.md` and `ollama_facts.md`.
  - To add to it: `entity_probe.py`, `test_stage7_entity_probe.py` and the spec as
    `spec_stage7_entity_probe.md`. Copy each and run
    `sed -i 's#/Users/julia#/Users/<user>#g; s/Julia/the owner/g'` on it.
- **Two assumptions:** `/api/ps`'s digest equals `/api/tags`'s (`0edcdef34593…`), unverified,
  next action 4.3; a missing `load_duration` reads as 0, since Ollama omits empty fields.

## Stage 7 step 1: the arms at M3

- **What** (spec draft `docs/specs/stage7-step1-arms-m3.md`, uncommitted). It replays stage 2's
  saved lists for three arms, scored by M3 on the sent context with no answer model: H, the
  hybrid; S, the structural graph route; P, P1b's extended cut. E follows later, behind its
  probe and G2. A parity gate must first reproduce stage 2's H byte for byte, its prompts and
  V4's 300 saved prompts. One break stops the run with exit 3.
- **The gate for answers, changed by the draft.** PLAN opens answers «только для лучшей руки и
  только если М3 выросла больше MDE». The draft opens them on no detected M3 loss, only on the
  questions whose prompt changes, by her word of 19.10 («Прими решения сам из цели — лучший
  продукт в финале»): aircargo's M3 is at its ceiling, the answer in 114 of 115 contexts, so no
  gain can show, while PLAN's decision needs the end metric only answers give.
- **S's fix** is production code, `vectordb/_base_manager.py` `_expand_graph_sections`, of the
  graph lane the web chat's stream does not call. Adjacency is now position in the chunk list,
  a run joined with one header and each seam once; the old code repeated headers and seams and
  joined over chunks already in the context.
- **Files,** SHA-256 on disk:
  - `vectordb/_base_manager.py` (M) `44cf16b6eeaa9bd73507d303266e1428808f0fce9bd8b921ced935eda2350fe8`;
  - `tests/test_graph_retriever.py` (M) `49933e9de6668ec16de9a07aaa5214091df94dc50cdcdd1138cf0d3702899041`;
  - `reports/stage7/tools/arms_replay.py` `f1bde2e0161d8ccd6400c0651f80cb3a3f3aeeb48ff7f0cea025ea67dceb2d2f`;
  - `tests/test_stage7_arms_replay.py` `78cb1f69fce6201c4b3f976c2f8044935481c198ad282d28d2bf2cdb9bd63885`, 58 tests;
  - `docs/specs/stage7-step1-arms-m3.md` `dac9b4b0f4f448c19ff9d04e14877540f1fd4ec835d079a71feb519c1c4561c8`.
- **State:** ruff and LF pass on the laptop; mypy reports only `_base_manager.py`'s two old
  errors, lines 156 and 581. The agent's stub runner last passed 57 of 58, all but the spec's
  test, before the spec existed, and not since the test file's format; pytest has not run. No
  ruff format on `_base_manager.py`: a whole-file format would rewrite legacy blocks.
- **The agent's report:** `.tmp/agents/e_stage7_step1_report.md`, verbatim: the replay's
  inputs, the parity gate, the judge plan's cost ($24.6–55.0, 2.6–9.5 h of the laptop), the
  lines for other files and four open questions, among them one arm or two to answers.

## Step 2b: the 80 labelled answers

- **What.** The continuation re-scores stage 3's 80 labelled V4 answers, 17 bad and 63 good,
  beside the classic's 2 of 17 caught and 0 of 63 marked. The flag is a score under 80.
  - **«No loss»** needs all three: at most 6 of the 80 without a score; at least 2 of the 17
    caught; at most one of the 63 over the classic's 0.
  - **What follows:** «no loss» beside a continuation candidate makes `continuation` the
    default, in its own commit with an E2E test, rule (a); else `classic` stays.
  - **Forecast:** ≈ 1 h 50 min – 2 h 30 min of the Mac.
- **Files,** SHA-256 on disk:
  - `reports/stage4-step2b/tools/step2b_replay.py` `41665e9e82a8551a65068df0105634f825c23f9b6b9dc7ccca60d89ada338f36`;
  - `reports/stage4-step2b/tools/step2b_reader.py` `15a685a32681e1356a3fcbd3c708f738f8fdba34a23326d400f65938e5dd460b`;
  - `tests/test_stage4_step2b_tools.py` `057b9814079127b1e658b602ea55669880cdeccafc5516cd6d5df40ee3e58a6a`.

  The spec `docs/specs/stage4-step2b-continuation-labels.md` is not written.
- **State:**
  - ruff, mypy and LF pass on the laptop;
  - only the reader's tests ran, 44 of 44 through a stub harness. The replay's tests import the
    chat router and have never run.
- **The host cache, the agent's open question 1.** Each cold continuation saves a state of
  ≈ 350–450 MiB. The cache reaches its 8,192-MiB default after ≈ 20, and the process then nears
  11 GiB on the 8-GB Mac. The scores do not move, since no state is restored, but the pace may
  pass the 255-s answer stop. Hence the yes/no on the cap now.

## State at the end

- **Mac:** step 2's run alone, detached. At its end the supervisor stops the API and the
  database and unloads the model. The stand keeps `step2/`; the earlier stands keep their runs.
- **Laptop, not committed:** the drafts of the three sections above; `.tmp/s2run/`, step 2's
  launch, wait, read and close scripts and this stop point's helpers; `.tmp/agents/`, the stage 7
  survey, the cache-cap notes and the three agents' reports.
- **Codex:** packages in `C:/Users/uedom/cxpkg/`; the backup holds the second pass's own files
  and the first review. No broker of this session runs.
- **Backup:** `wip/stage4-step2-stop`, `f49a9d4`, 52 files, built on `f532c96` through a
  temporary index; each file matched `hash-object`.
  - It is local, not pushed, and not for merging.
  - Restore only if the tree lost the files:
    `git -C D:/RAG_new diff --name-only wip/stage4-step2-stop~1 wip/stage4-step2-stop | xargs git -C D:/RAG_new restore --source=wip/stage4-step2-stop --worktree --`.
  - Left out: the earlier sessions' external downloads in `.tmp/agents/c-*`.
- **No Monitor, agent or background job** of this session runs.
- **Not this session's:** `demo/phase-e-raw.webm`, `reports/ask100/`.

## Glossary

The previous handoff's glossary holds; these are this session's terms.

- **Classic** — the stream's self-evaluation before step 2: its own request with V3's rubric
  (`SELF_EVAL_PROMPT_V3`), the question, the five documents and the answer.
- **Continuation** — one `/api/chat` call: the answer's prompt as sent, the answer as streamed,
  then `SELF_EVAL_CONTINUATION_V1`. A reply that is not one integer of 1–100 gives no score, and
  the code falls back to the classic.
- **`STREAMING_SELF_EVAL_MODE`** — `classic` (the default), `continuation` or `both`; in `both`
  the continuation drives the badge and the route, the classic runs after it on the same answer,
  and the result carries `self_eval_both`.
- **Held** — the continuation scored 1–100, and the result's quality and route are its own.
- **Pair, cost, saving** — a pair is a read ask of a run whose gate passed. Its cost is the
  continuation's seconds, with the classic's added where it did not hold. Its saving is the
  classic's seconds less the cost.
- **H, S, P, E** — stage 7's arms: today's hybrid, the structural graph route, P1b's extended
  context cut, the entity lane.
- **M3** — the end metric on the sent context, scored without an answer model (PLAN stage 7).
- **Host prompt cache** — llama-server's store of saved prompt states in RAM, 8,192 MiB by
  default; `cache-ram` caps it. The prefix a slot keeps is apart from it.
- **Idle rule** — step 0's four checks before a run: the 5-minute load below 2; no `pytest`,
  `llama-server`, `_supervisor`, `replay.py`, `step[0-3]_` or `limactl` process; `/api/ps`
  empty; no `$HOME/ci_local/.lock_ci-local`.
- **`$S`, `$T`, `$PY`, `$IX`** — step 2's stand `/Users/julia/RAG_new_chat_57420db`;
  `$S/step2`; the interpreter `/Users/julia/RAG_Support_Assistant/.venv/bin/python`; the index
  `/Users/julia/RAG_new_external_s1/aircargo`.

## Lessons

- **An idle Mac can be most of a session's wait.** Step 2 waited 6 h for other projects' CI and
  tests. A launcher that refuses unless the idle rule holds, a Monitor that retries it and laptop
  work beside it, the three drafts, made the wait cheap.
- **The first question's read is the continuation's real test.** Only a live read could show
  the template's prefix match; registered as a stop, it protected the 13-question run.
- **A scrubbed package changes the SHA-256.** Codex flagged hashes it could not match, so the
  second brief says the scrub was made.
- **A Monitor's loop must end inside its timeout.** Ssh checks under load ran past 30 min at 27
  attempts and printed nothing; 24 fit.
- **An agent's report is the only record of its design.** Save it to a file at once, as
  `.tmp/agents/` now holds them, and read its SHA-256 against the disk before quoting them.
- **Have the handoff read cold, and write the close as a script.** The cold read found a done
  line read as success, a wrong sampler filter and a cache route needing a restart where PLAN
  names one that does not.

## Verification

- **Mac tests before this session's commits:** 89 before `ec7984a`; 177 before `1a793a4`,
  `57420db` and `f532c96`, the registration tests included.
- **The stand:** step 2's four tools on the Mac matched the spec's SHA-256 before the launch.
- **The first question:** `$T/s2-both.q1.step2.json` on the Mac, by `.tmp/s2run/q1_read.sh`;
  the numbers above are its fields.
- **The drafts:** laptop checks only. The ten SHA-256 above were read from the disk with
  `sha256sum` at 09:08 and again by the cold read.
- **The scripts:** `bash -n` passes on each `.tmp/s2run/*.sh`; `close.sh` has not run.
- **This handoff's commit:** no docs tests on the Mac, which was measuring (next action 2). On
  the laptop: CURRENT_STATE ≤ 150 lines, BACKLOG ≤ 60, root `.md` ≤ 9, no CR or mojibake, and
  every relative link in the touched files resolves.
- **The cold read:** a fresh subagent on the session's model read this handoff against the
  status files, specs, tools and reports; its 19 findings were checked at their sources and
  fixed.
- **The wip branch:** each of its files matched `hash-object`.
