# Session handoff 2026-10-29, evening — stage 4: step 2 and step 2b read, the continuation not adopted; the probe ready to register

> **Superseded** by the next session's handoff,
> [stage 4: items 4 and 5 read; item 5a's INT8 registered, its block 1 passed, the series resumes at block 2](session-handoff-2026-10-30-stage4-step5a-block1.md),
> which keeps this file's model, glossary and «Do not» in force.

The session ran 2026-10-29 16:57 – ≈ 22:00 UTC. All times are UTC; the laptop's clock is EDT and
the Mac's UTC+3. The previous handoff
([step 2 running on the Mac; stage 7 and step 2b drafted](session-handoff-2026-10-29-stage4-step2-running.md))
still holds for its model, its glossary, its «Do not» and its «Once Julia answers», with two
changes. There `$T` is `$S/step2` and «Held» means the continuation scored 1–100; here `$T` is
`$S/step2b`, and held is a rule's verdict. Its «Once Julia answers» clauses on step 2b are spent:
step 2b ran without the cap, so her «да» or «нет» on the cap now concerns item 5 alone. Its next
actions are replaced by this file's.

## Read this first

- **Stage 4** cuts the chat's median answer of ≈ 320 s on the Mac with levers that lose no quality
  ([PLAN.md](../../PLAN.md) stage 4). Steps 0, 1 and 3 were read before; no lever or K is adopted.
- **Step 2 read: the continuation is faster.** The stream's self-evaluation, the badge
  «Качество: N» and the route, is today a request of its own, «the classic». Step 2 asked for the
  same score as the answer chat's next turn, «the continuation», which reuses the answer's tokens
  in llama-server's slot ([record](../evidence/stage4-step2-record.md)).
  - The first run, `s2-both`, stopped at its thirteenth question past its cap; its gate failed on
    its launch point alone. Amendment 1 (`c11696e`) made the rerun unload the model before each
    question.
  - The rerun `s2-both-r2` passed its gate. The continuation was faster on 13 of 13 (sign test
    p 0.000244): a median 8.635 s against the classic's 62.691 s, a median saving of 54.009 s
    (ratio 0.1408), with the model unloaded before each question, not at production's pace.
    Routes agree but one: `aircargo-probation-extend`, classic 60 (to a person) → continuation 90
    (`auto`). Scores held.
- **Step 2b read: not held, on the catches. The default stays `classic`**
  ([spec](../specs/stage4-step2b-continuation-labels.md), registered in `1e0600a`, amended in
  `45f7e51`, both before its first request; its reads in `reports/stage4-step2b/57420db/`).
  - **What it asked.** Step 2's thirteen answers are unlabelled, so step 2 could not see whether a
    faster badge is blind to a bad answer. Stage 3's 80 labelled V4 aircargo answers, 17 bad and
    63 good, are saved answers, so the continuation can score them only *cold*: the whole chat, a
    median 2,656 prompt tokens, read afresh. The bridge first asked whether cold routes are the
    warm ones, on step 2's 25 answers. The 80 then asked whether the continuation flags (a score
    under 80, the route to a person) at least what the classic flagged there: 2 of the 17 caught,
    0 of the 63 over-marked.
  - **The bridge held:** 25 readable; the cold route is the warm one on all 25 (`auto`); 24 equal
    scores and one lower (95 → 90). A cold route stands for the warm one here.
  - **The 80:** the gate passed, all 80 readable and scored. **Scores held** (none without a
    score, at most 6 allowed); **over-marks held** (0 of 63, the classic's 0); **catches not
    held:** 0 of 17, the classic's 2 — answers n = 2 and 6, which the classic scored 60 and 40
    and the continuation 90 and 100. **The signal: not held**, as the spec forecast it: «not held,
    on the catches, with low confidence».
  - **Why:** the continuation scored every one of the 80 at 90 or more; the 17 bad answers got
    100 × 16 and 90 × 1. Fast, and blind on these labels.
  - **What follows,** in the spec's words: «**not held** or `NOT_EVIDENCE`: the default stays
    `classic`». Step 2 closes with the classic, the badge keeps its ≈ 63 s, and stage 4 goes on
    to item 4. The record's capsule and the rest of its test are next action 1.
- **What to tell her.** Neither result reached her in this session's chat before its closing
  message, which gives both. In her terms: the continuation gives the badge in 8.6 s against
  62.7 s (medians, 13 questions, the model unloaded before each), but on the 80 labelled answers
  it flagged 0 of the 17 bad ones, the classic 2; the default stays classic. Once, as context and
  not as a task: the classic itself flags only 2 of the 17, so the badge is a weak detector
  either way.
- **The probe** ([below](#the-entity-extraction-cost-probe)), E's cost for stage 7, is ready to
  register: Codex's eight findings fixed, each with a test; its test passed on the Mac at 21:20,
  in a run of 383 passed; its open assumption checked at 21:22 — `/api/ps` names the loaded model
  by `/api/tags`'s digest, the spec's. Registration, then the run (≈ 5–11 min), come after step
  2b's record.
- **Not pushed:** 24 commits after `7caaf21`, this stop point's the last. The push needs her word
  and a full ci_local run, never during a live Mac measurement.
- **Open for her, one yes/no, unanswered since 2026-10-28:** `cache-ram = 1024`, item 5's
  host-cache cap. Step 2b did not need it: it unloaded and reloaded the model before answers
  n = 6, 11, …, 76 and left her configuration alone.

## Julia's words in this session (UTC)

- 16:57 «продолжи доработку» — the work in PLAN's order, from the previous handoff's next actions.
- 17:06, mid-turn: «важно - не запускай своих агентов параллельно» — at most one subagent at a time,
  serially; the leave of 2026-10-28 for three agents is void (memory `agents-one-at-a-time`).
- 19:05, mid-turn: «а что не так с маком?» — nothing: after the bridge's first answer the 5-minute
  load was 2.10, from our own cold read, so the launch waited for the idle rule; at 1.94 the
  bridge's rest started, 19:06.
- 19:27 «процесс живой?» — yes: 19 of the bridge's 25 lines written, all scored.
- 20:15, mid-turn: «сессия длинная. может стоит начать новую, что думаешь?» — my answer: yes, at the
  task boundary: the probe's fixes, this handoff and a wip backup. The 80 ended at 21:18, inside
  the session, so their end and read were taken here too; this file is that boundary.

## What this session did

- **Step 2:** Amendment 1 and `s2-both`'s record (`c11696e`, 17:12); the rerun, read; its reports
  (`2816247`, 18:59); the capsule [`stage4-step2-record.md`](../evidence/stage4-step2-record.md)
  and `tests/test_stage4_step2_artifact.py`, in the stop-point commit.
- **Step 2b:** the spec, its tools and their test registered (`1e0600a`, 18:59). The launch check
  stopped with exit 6, `not V4's: provider_registry_path`: V4's settings read the provider registry
  by a path of V4's stand. Amendment 1 (`45f7e51`, 19:03) passes
  `PROVIDER_REGISTRY_PATH=/Users/julia/RAG_new_chat_4f48fed/config/providers.yml` to each replay,
  a file byte-identical to the stand's (SHA-256 `a71571492…`). Then the bridge and the 80 ran, and
  `.tmp/s2run/end_80.sh` took the end at 21:18: the environment's third line, the read, the copies
  as bytes, their SHA-256 equal to the Mac's and pinned in `FILES` of
  `tests/test_stage4_step2b_artifact.py`. The four reads and that test, eight functions, are in
  the stop-point commit; the 80's tables, the readings' rows and the capsule's test are not
  written yet.
- **GR-1b's published replay broke under stage 7's S fix** of `_expand_graph_sections` (Mac,
  17:11: 1 failed, 178 passed). The old expansion is kept for that replay as
  `legacy_expand_graph_sections` in `scripts/gr1b_stage_replay.py`, used by
  `scripts/gr1b_seed_expansion.py`; `tests/test_gr1b_stage_replay.py` follows. Uncommitted.
- **The probe:** Codex's second pass, its eight findings fixed, the Mac test, the digest check.
- **Mac tests,** from the laptop by `.tmp/mf-mac/sync.py`, then `remote.py`:
  - 17:10: 86 passed, step 2's tools and the docs tests; the probe's test as it was then, 87; step
    2b's tools, 73 with the spec test deselected;
  - 18:17: 271 passed on `c11696e`'s sync, twelve files: stage 7 step 1's ten (GR-1b's replay
    test among them), `tests/test_gr1b_seed_expansion.py` and the probe's test as it was then;
  - 18:46: step 2b's tools, 4 failed, 135 passed — a keyword collision in `_phase()`, fixed before
    the registration; 18:58, 18:58 and 19:03: 162 passed each;
  - 21:20–21:22: 383 passed on `45f7e51` with the working tree — the probe's test, step 2's
    artifact and tools tests, step 2b's tools and artifact tests and the three docs tests
    (`.tmp/s2run/mac_tests_2118.log`);
  - after this file's last edit: see «Verification».
- **The digest check,** 21:22, on the idle Mac (`.tmp/s7probe/digest_check.sh`): the model loaded
  once without a prompt, `/api/ps` and `/api/tags` read, the model unloaded, 6.3 s in all; both
  digests `0edcdef3…`, the spec's.
- **Closed:** this session's Codex broker (`--cwd C:\Users\uedom\cxpkg\rag-s7probe2-20261029`),
  which outlived its task; its tree stopped by explicit pids at ≈ 20:42.
- **A cold read of this file's first version,** by one subagent on the session's model: 24
  findings, 3 blockers, 12 gaps and 9 nits. Those still in force are fixed here; the rest went moot
  with the 80's clean end (the whole cap, a resume, the `NOT_EVIDENCE` path, the default's change).

## Step 2b: the reading

**The rules, frozen before the first request** (the spec's «How it is read»):
- **a route:** −1 (no score) to the classic, which then decides; under 80 to a person; 80 and over
  to the answer as it stands. **Flagged:** a score under 80;
- **the bridge:** held with at least 10 of the 25 readable and the cold route the warm one on all
  but at most 1;
- the **effective score** is the continuation's where it scored 1–100, else the classic's saved
  one;
- **scores held:** at most 6 of the 80 without a score;
- **catches held:** at least the classic's 2 of the 17 flagged by the effective score;
- **over-marks held:** at most one of the 63 more than the classic's 0;
- **the signal:** held when the bridge and the three hold; not held when any is not held;
  `NOT_EVIDENCE` otherwise. The McNemar tests are printed beside them and decide nothing.

**What came,** `step2b.json`'s `readings`:

| | read | rule | verdict |
|---|---|---|---|
| the bridge | 25 readable, no route differs | ≥ 10, ≤ 1 | held |
| scores | 0 of 80 without a score | ≤ 6 | held |
| catches | 0 of 17; the classic's 2, n = 2 and 6 | ≥ 2 | **not held** |
| over-marks | 0 of 63; the classic's 0 | ≤ 1 | held |
| the signal | | | **not held** |

**Printed, deciding nothing:**
- the bridge: 24 equal scores, one lower (95 → 90); cold 100 × 23 and 90 × 2, warm 100 × 23, 95
  and 90; a median 8.962 s warm against 65.64 s cold, both reading 2,590 prompt tokens, warm in
  7.906 s and cold in 64.584 s;
- the 80's scores: the continuation's targets 100 × 16 and 90, goods 100 × 61, 95 and 90; the
  classic's targets 100 × 14, 95, 60 and 40, goods 100 × 59 and 95 × 4. Against the classic the
  continuation is higher on 5, lower on 1, the same on 74;
- under 100, S1′'s cut: catches the classic 3, the effective score 1; over-marks 4 and 2;
- McNemar: the catches' discordant pairs are the classic's two alone, exact p 0.5; the
  over-marks' none, p 1.0. Wilson's 95 % intervals of the share caught: the classic
  0.0329–0.3434, the effective score 0–0.1843;
- the 80's seconds: a median 68.165 s, the longest 91.007 s (the stop is 255 s), 5,560.141 s in
  all; the median counters 2,656 prompt tokens read in 67.181 s and 4 tokens generated; the
  estimated input a median 2,955.5 tokens, at most 3,363; every reply stopped by the model, 77 of
  three characters and 3 of two;
- the reloads before n = 6, 11, …, 76: a load a median 5.632 s (at most 7.14 s), an unload a
  median 0.248 s.

**The run:** the bridge in two segments, 19:03:24–19:04:53 (its first answer, read before the
rest) and 19:06:09–19:33:27; the 80 in one, 19:43:41–21:17:58, pid 6732. Three environment lines,
19:00:02, 19:33:49 and 21:18:45, each naming Ollama 0.33.2 and one server, pid 12377, started
2026-09-13T16:37:06, its binary of 2026-08-28T20:09:07 unchanged.

**Its record, on step 2's model** ([capsule](../evidence/stage4-step2-record.md)): the question,
the stand, both gates, the bridge, the four rules with their numbers, the forecast against the
outcome — the spec's forecasts quoted — what it says and «Not said». Not said, at least: no other
prompt for the continuation was tried; one corpus, one model and one stand; the 80 were scored
cold, and the warm score is inferred from the bridge's 25, whose scores sat at 90–100, far from
the line of 80.

## The self-evaluation's default, should it be revisited

Nothing changes now. The default lives in three places: `config/settings.py:776–778`
(`os.getenv("STREAMING_SELF_EVAL_MODE", "classic")`); `normalize_streaming_self_eval_mode`
(`config/settings.py:286–298`), which maps a blank or unknown value to `classic`, warning on an
unknown one; and the router's fallback, `api/routers/conversation.py:716–717`. Only the stream
route, `/ask/stream`, reads the mode, while step 2b's spec names `/api/ask` for the E2E test.
`tests/test_stream_self_eval_continuation.py:476` and `:900` pin `classic`; the E2E model test is
`tests/test_ask_stream_thinking_off_e2e.py`. Another continuation prompt would be a new spec,
read on the same 80.

## The entity-extraction cost probe

- **What it decides** (draft spec [`stage7-entity-probe.md`](../specs/stage7-entity-probe.md),
  untracked): E, the entity lane, needs a full extraction first. The probe times the product's own
  path, one JSON-schema `/api/chat` a chunk, on 100 MultiHop-RAG chunks. Gate G2 stops E if
  11,231 chunks × the upper bound of the mean's 95 % interval exceed 24 h (7.693 s a chunk), or if
  fewer than 95 of 100 outputs are valid. A broken or contended run must never read as a clean fail.
- **Codex's second pass** (`C:/Users/uedom/cxpkg/rag-s7probe2-20261029.out`, verdict "no-go until
  1, 2, 3 and 4"), each finding fixed, each with a test:
  1. **the runner's slots:** `context_length` in `/api/ps` does not show them, so `ps` reads the one
     `[l]lama-server`'s `-np` and `-c`; they must be 1 and 4096, else `stand`;
  2. **the warm-up's contention:** `_clean` reads every row, the warm-up's included, as a job seen
     after the warm-up may have run into the first measured chunk;
  3. **every request timed on the clock** — urllib's timeout bounds each socket operation, not the
     request; one that reaches its cap is a timeout;
  4. **the seconds:** each row's `chat_sec`, a cut exactly at 900 s, the load and the rows as spans
     of the run; their `math.fsum` is at most the run's seconds, which are under 3,000 s and at
     most the wall time;
  5. **`unload_sec`:** the model shown gone within the unload's bound, else `NOT_EVIDENCE`;
  6. **counters:** one present but not an integer 0..2⁶³−1 breaks the run, `counters`; one Ollama
     leaves out is null;
  7. **the 900-s edge** is reached at its value, with the spec's two exceptions;
  8. a test for each.
- **Files,** SHA-256 on disk, the first two in the spec's Records:
  - `reports/stage7/tools/entity_probe.py` `68f7e828277cd459a338633801026d36355cce85d0769f5161207c1df01d0c7f`;
  - `tests/test_stage7_entity_probe.py` `bf3bfc3502cdb20a5ef7ee4ffb39dd5c189fded67d7cf9e87c7de0ffbc911e4b`;
  - `docs/specs/stage7-entity-probe.md` `b43627772f7b74e1e1029b44f563d9ca70f59fbe3a2c184de56d9280089f3f2e`.

  Any edit to the first two means new SHA-256 in the spec's Records.
- **State:** ruff format and check, mypy (CI's way) and LF pass; the Mac test passed at 21:20 and
  the digest check at 21:22, on these bytes. Nothing is registered: the spec's Status says a draft.
- **Its outcomes, by the spec:**
  - **complete or stopped, its gate passed:** G2 is read. Passed: the projected hours are
    published and MultiHop-RAG's full extraction is next, under a spec of its own. Failed: E stops,
    the numbers are published, and stage 7 goes on with H, S and P;
  - **exit 3,** refused at the start (Ollama's version, the endpoint, the system or the machine
    differs): nothing written; its cause is read before anything else;
  - **broken (exit 5) or contended:** once more as `e1-r2` after the idle check; a second such run
    makes G2 `NOT_EVIDENCE`, published with the rows it has;
  - **any other failed gate:** a marked error fix — the change, its test, the new SHA-256, one
    commit — then a new run.

## Stage 7 step 1

Unchanged since the previous handoff, but for GR-1b's legacy copy. Its SHA-256 at 20:40:
`vectordb/_base_manager.py` `44cf16b6…`, `tests/test_graph_retriever.py` `49933e9d…`,
`reports/stage7/tools/arms_replay.py` `f1bde2e0…`, `tests/test_stage7_arms_replay.py` `78cb1f69…`,
`docs/specs/stage7-step1-arms-m3.md` `dac9b4b0…` — the same as the previous handoff's; and
`scripts/gr1b_stage_replay.py` `e5c987dc…`, `scripts/gr1b_seed_expansion.py` `5756955f…`,
`tests/test_gr1b_stage_replay.py` `9e3cfe14…`. **The S fix and GR-1b's three go in one commit**:
GR-1b's test fails without them. The 271 of 18:17 ran on these bytes.

## Next actions

The order: step 2b's record, the probe, PLAN items 4–7, and stage 7 step 1 after item 4.

1. **Step 2b's record** (the slice rule's (c)):
   - the capsule `docs/evidence/stage4-step2b-record.md`, on
     [step 2's](../evidence/stage4-step2-record.md) model, as [above](#step-2b-the-reading);
   - in `tests/test_stage4_step2b_artifact.py`, the 80's tables (scores by class, the paired
     flags), the readings' rows and the capsule's test, on `tests/test_stage4_step2_artifact.py`'s
     model;
   - the spec's Status line: read, not held; grep `tests/` for its pinned phrases first;
   - the row in `EVIDENCE_INDEX.md`, and the status lines: CURRENT_STATE 4 and 99, PLAN stage 4
     item 2, ROADMAP's row 4, BACKLOG's first item, docs/README's stage 4 sentence;
   - from the laptop, on an idle Mac, in the background, once:
     `python D:/RAG_new/.tmp/mf-mac/sync.py`, then
     `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q -p no:schemathesis -p no:cacheprovider --tb=short tests/test_stage4_step2b_artifact.py tests/test_stage4_step2b_tools.py tests/test_docs_hygiene.py tests/test_docs_quality.py tests/test_docs_publication.py`;
   - one commit, `evidence(stage4-step2b): …`.
2. **The probe:**
   1. Registration: the Status line says registered (keep «registered before the first request» on
      one line, as the spec's test pins it); the Mac tests of `tests/test_stage7_entity_probe.py`
      and the docs tests on those bytes; a commit of the probe, its test and the spec with `<c>`;
      then a commit filling `<c>` in, with the PLAN, docs/README and CURRENT_STATE lines.
   2. The run, the spec's «Running it», on an idle Mac: ≈ 5 min by its forecast, ≈ 11 min at 6 s a
      chunk. The digest check is not repeated unless Ollama or the model changed.
   3. The read, the copies as bytes into `reports/stage7/entity-probe/<c>/`, the record (capsule,
      test, row) and its outcome, as above.
3. **PLAN items 4, 5, 5a, 6 and 7.** Item 4 is «Промпт короче (67 с на 2 270 токенах) и подсказки
   (13 с) — ≈ 1 ч». Item 5 starts on her word on the cap.
4. **Stage 7 step 1, after item 4**, as the previous handoff's next action 6 says.
5. **The push**, only on her word: the previous handoff's «Once Julia answers».

**Do not**, beside the previous handoff's list:
- change the self-evaluation's default: step 2b closed it;
- commit the probe or stage 7 step 1 before their Mac tests on the bytes committed;
- start a second subagent while one runs;
- touch `/Users/julia/.config/llama.cpp/config.ini` without her «да».

## State at the end

- **Mac:** idle at 21:22: no model in Ollama, no job of this session. The stand
  `/Users/julia/RAG_new_chat_57420db` keeps `step2b/`, the 80's lines and logs among them; earlier
  stands keep their runs.
- **Committed at the stop point:** step 2's capsule and test, the step 2 spec's Status line, step
  2b's four reads and its artifact test, the status lines and both handoffs.
- **Laptop, not committed:** the probe's three files; stage 7 step 1's five and GR-1b's three;
  `.tmp/s2run/` (this session's scripts and logs), `.tmp/s7probe/`, `.tmp/s2cap/`, `.tmp/s2bcap/`,
  and `.tmp/cxpkg/`, the second pass's package.
- **Backup:** branch `wip/stage4-step2b-stop`, see «Verification».
- **No Monitor, agent, broker or background job** of this session runs after it closes.
- **Not this session's:** `demo/phase-e-raw.webm`, `reports/ask100/`.

## Glossary

The previous handoffs' glossaries hold, with this file's `$T` and held (see the top); these are
this session's terms.

- **Warm, cold** — a continuation scored in the slot that holds the answer's tokens (warm), or with
  the whole chat read afresh (cold), as for a saved answer.
- **The bridge** — step 2b's first phase: step 2's 25 answers scored cold and read against their
  warm scores by route: held with at least 10 readable and the cold route the warm one on all but
  at most 1.
- **The 80** — stage 3's labelled V4 aircargo answers: 17 targets (graded bad, or declined) and
  63 goods, with the classic's saved scores.
- **S1, S1′** — the classic's saved score under 80 and under 100: S1 caught 2 of the 17 targets and
  marked 0 of the 63 goods; S1′ caught 3 and marked 4
  ([the handover signals' record](../evidence/handover-signal-v4-aircargo.md)).
- **Flagged, effective score, the three rules, the signal** — see
  [the reading](#step-2b-the-reading).
- **`<g>`** — `1e0600a`, the commit that registered step 2b's spec; its tools copy step 2's records
  by `git show <g>:…`.
- **`<c>`** — in the probe's draft spec, the commit that will register it; a placeholder until then.
- **Launch point** — the reader's gate's first point: the run's `launch.json` against the spec
  (schema, spec, phase, code SHA, model and digest, the settings, the answers planned, status
  `complete` with as many answers). `s2-both` failed on it alone: `failed`, at its thirteenth.
- **Segment** — one launch of a phase's replay, from an idle Mac to its end or stop; a resume
  starts the next.
- **Reload** — step 2b's unload and load before answers n = 6, 11, …, so the host cache cannot grow
  for more than five answers without her cap.
- **`$S`, `$T`, `$D2`, `$R`, `$PLAN`, `$LABELS`, `$SITE`, `$PY`** — step 2's stand
  `/Users/julia/RAG_new_chat_57420db`; `$S/step2b`; `$T/step2`, step 2's records as committed;
  V4's runs `/Users/julia/RAG_new_chat_4f48fed/chatlive/runs`, each answer's saved prompt;
  `$S/reports/handover-signal/d260d95/plan.json`, each answer's files and SHA-256 and the
  classic's saved score; `$S/reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl`, the
  judge's grades; `/Users/julia/RAG_new_mf_gate_site`, the package site V5's runs put on
  `PYTHONPATH`; `/Users/julia/RAG_Support_Assistant/.venv/bin/python`.
- **`stand`** — the probe's broken reason when the runner is not the registered one: `/api/ps` not
  showing the model on the CPU with `context_length` 4096, or `ps` not finding one `llama-server`
  started with `-np 1` and `-c 4096`.
- **`chat_sec`, `unload_sec`** — the probe's seconds of a chunk's `/api/chat` alone, and from the
  unload's request to the reply that shows the model gone.
- **Runner, slots** — the llama-server Ollama starts for the model; `-np` its parallel slots,
  `-c` its context, `num_ctx` × slots.
- **Counters** — Ollama's `load_duration`, `prompt_eval_count`, `eval_count` and the like; in the
  probe one present but not an integer 0..2⁶³−1 breaks the run (`counters`), one left out is null.
- **The two exceptions** — a chunk cut at 900 s stops the probe by rule 2, G2 failed; but a cut
  that is the sixth invalid output is named by rule 1, and after the hundredth chunk no rule runs,
  so the run is complete and G2 fails it on its seconds.
- **GR-1b** — the published structural graph replay, «GR-1b structural replay: 100/100 exact» in
  [EVIDENCE_INDEX.md](../../EVIDENCE_INDEX.md); `legacy_expand_graph_sections` keeps the expansion
  it was published on, from before stage 7's S fix.

## Lessons

- **A faster check is read on labels before it is adopted.** Step 2's 13 of 13 said the
  continuation is faster and routes alike; step 2b's labels showed it scores every answer 90 or
  more. Speed and agreement on unlabelled answers say nothing of what a check catches.
- **A status-line rewrap can split a pinned phrase.** The probe's spec test failed when
  «registered before the first request» wrapped. Grep the tests before an edit, keep a pinned
  phrase on one line.
- **A fix of production code can break a published replay** that imports it. Run the replays'
  tests with the fix, not only the fix's own.
- **A test that runs a tool twice inherits the fake's state.** The first counters test leaked the
  fake's unload between two runs; one run a test.
- **urllib's timeout is a socket timeout.** A reply that drips slower than the timeout per read
  never times out; time the request on the clock.
- **A sum over floats depends on its order.** `math.fsum` and a running sum disagree at the stop
  line; the probe and its reader both use `fsum`, and a test pins the edge.
- **Commit the inputs a spec will `git show`.** Step 2b copies step 2's records from `<g>`, so they
  had to be committed before it, apart from step 2's capsule.
- **Check the brokers at the stop point.** The second pass's broker lived on after its task; stop
  only your own tree, by `--cwd`, with explicit pids.
- **A handoff written mid-run needs a cold read.** The first version of this file, written while
  the 80 ran, drew 24 findings, three of them blockers.

## Verification

- **Commits:** `git log` shows five after `e69aa15`, the stop point's the last;
  `git rev-list --count 7caaf21..HEAD` gives 24.
- **Step 2b's numbers:** every number above is `step2b.json`'s `readings` or `bridge`, read on the
  laptop with Python; the four reads' SHA-256 equal the Mac's `shasum -a 256` and the test's
  `FILES`.
- **Mac tests:** 383 passed at 21:20–21:22; then 246 passed at 21:35–21:36 on the stop point's
  tree — step 2's and step 2b's artifact and tools tests and the three docs tests
  (`.tmp/s2run/mac_tests_final.log`). This line came after it; the docs tests' plain functions
  passed again on the laptop pre-check (`.tmp/s2cap/precheck_any.py`) on the bytes committed.
- **The digest check:** 21:22, both digests the spec's, the model unloaded after.
- **The broker:** none left on `tasklist` after the stop.
- **The wip branch:** `wip/stage4-step2b-stop`, commit `b99261f7088ceae07943bcc36be2575099842df4`
  on `45f7e51`, built through a temporary index before the stop-point commit: 99 files, all that
  was uncommitted then but `demo/` and `reports/ask100/`, the git-ignored scripts and notes, and the
  second pass's package; none differs from disk. Local, never pushed. Restore only if the working
  tree lost them:
  `git -C D:/RAG_new diff --name-only wip/stage4-step2b-stop~1 wip/stage4-step2b-stop | xargs git -C D:/RAG_new restore --source=wip/stage4-step2b-stop --worktree --`.
