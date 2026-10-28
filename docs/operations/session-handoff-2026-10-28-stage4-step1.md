# Session handoff 2026-10-28 — stage 4: step 0 read, step 1 measured, step 3 registered

The session ran 2026-10-27 13:40 – 2026-10-28 ≈ 21:30 UTC. This handoff covers its last part,
from ≈ 15:00 UTC on 2026-10-28, after the previous handoff's «After the report». All times are
UTC; the laptop's clock is EDT and the Mac's UTC+3. The previous handoff
([V5 not adopted, the encoders' Amendment 1](session-handoff-2026-10-28-v5-record.md)) still
holds for its model and glossary. Its next actions 1 and 3, step 0 and step 3's timing, are done
or registered here.

## Read this first

- **What stage 4 asks.** The chat answers a question in a median of 320 s on the Mac: first token
  at 223 s, and the rerank alone takes 102 s of it. With the retrieval alone, no model loaded, the
  same rerank takes 27 s
  ([PLAN.md](../../PLAN.md) stage 4, §3). Stage 4 finds where the time goes, then cuts it with
  levers that do not lose quality. The final path's quality (item 6) and speed (item 7) are
  measured last, and Julia names the SLO.
- **Step 0 is read** ([record](../evidence/stage4-step0-record.md), `31c06b2`). The 4B's growth is
  llama-server's host prompt cache: 280.69 MiB a request, and none of 15 requests restored a state
  from it. A cap on the cache therefore loses no reuse. Generation does not wait on memory, and
  the weights are already repacked, so that lever is closed. From its 15 requests (mine, from
  `step0.json`):
  - the prompt is read at 24–42 tokens/s; answers are generated at 2.1–4.0 tokens/s, the record's
    own figure;
  - the self-evaluation reads 2,377–2,690 tokens to write 3–4, in 65–105 s;
  - a run's first request reused no cached tokens and the later ones 5–7, so the answer's and the
    self-evaluation's prompts share nothing.
- **Step 1 is measured and its record read on the Mac: contention yes, net faster.** Both are the
  forecast's verdicts; the ratio, 0.2594, is below the forecast's ≈ 0.3–0.45. The step asks where
  the rerank's 102 s go: does the resident model's memory slow the rerank? Its spec is
  [stage4-step1-rerank-memory.md](../specs/stage4-step1-rerank-memory.md), registered in
  `44fd650` before the first request. The design:
  - four aircargo questions, each asked with the model resident (arm A) and with it unloaded
    before the question (arm B);
  - two runs, `s1-baba` and `s1-abab`, beside step 0's sampler.

  Both gates passed. The record, the spec's step 7, was read at ≈ 20:50 and is on the Mac:
  `$T/step1.json`, SHA-256 `c3b5ad317fcfea93e807a3651011bbceea692514c14424bbb601bf17cf7c762b`.
  - **Contention yes:** B's rerank over A's, a median of 0.2594 on 4 readable pairs.
  - **Net faster, by the sign alone:** B's whole seconds less A's, a median of −47.009 s. That is
    within the spec's 90 s of zero, where the rule reads the sign and not the size, and it rests
    on a 2–2 split (below).

  Its copy, capsule and test are next action 1.
- **Step 3's live timing is registered** (`3fc8ce7`, before the first request). It measures
  K = 14 against K = 20 with the retrieval alone and no model: thirteen aircargo questions in
  four runs, ABBA. The step reads the rerank's compute alone, because with the model resident its
  seconds also hold the memory's wait, which is step 1's question. About 35 min of an idle Mac.
  [Spec](../specs/stage4-step3-k-timing.md).
- **Stage 6 is prepared, nothing is installed.**
  - `3f7b33d`: a tenant's session store closes after three failures in a row, not one
    (`DB_COOLDOWN_FAILURE_THRESHOLD`; a failed call still refuses its own request).
  - `1d8558a`: drafts of the launchd service ([macOS service](macos-service.md), `deploy/macos/`)
    and of the throughput spec ([stage6-throughput.md](../specs/stage6-throughput.md)). They are
    installed and registered only on her word.
- **Not pushed:** 14 commits after `7caaf21`, this handoff's the last. A push needs her word and
  ci_local's full run, which must not run during a live Mac measurement.
- **Open for her, one yes/no each, none answered:**
  - at ≈ 15:35 I offered to cut stage 7 to P1b alone (below);
  - the push;
  - at step 5, the cache cap's route;
  - at step 2, the self-evaluation's badge;
  - at stage 6, the service's installation and its DB role;
  - from before this part: the fixes of the widget's R1 and of its retry's call budget (stage 3).

## Julia's words in this part (UTC)

- 15:27 «есть ощущение, что задача без конца((( сколько еще дней нужно на завершение? все
  метрики завалены?»
  - My answer: not all of them failed. Retrieval is strong: MultiHop-RAG is above the published
    band. Quality is measured on four bases. Speed and memory are weak.
  - My estimate: ≈ 7–9 working days, or ≈ 4 if stage 4 leaves the answer path as it is, because
    stage 5 is then skipped.
  - My offer, one yes/no: stage 7 measures only P1b, the extended context cut (+0.0207
    precision, once rejected only by the 0.63 ruler), and drops the graph lane's live
    measurement. No answer yet.
- 15:51 «А почему V4, был же еще V5?» — my answer: V5 was measured and not adopted on 2026-10-28,
  so V5 was never the product's prompt. Stage 4 runs on V4's stand.
- 16:05 «есть шаги, которые сейчас можно отдать агентам параллельно?» — three agents in parallel:
  step 1's spec and tools, a source read on capping the cache, and stage 6's drafts. I told her
  what cannot run in parallel: measurements on the Mac (one at a time), a record's read and step
  3's live timing, and step 2, which waits for her word on the badge.
- Later «продолжи», after all three agents stopped on network errors (each was resumed), and
  «продолжи работу», sent mid-turn ≈ 19:58.
- ≈ 20:27 «Сессия очень длинная. Поставь точку, где логично. И обнови доку». The point I chose: run 2
  ends by itself, its gate is read, step 3 is registered, the documents are updated, then stop.
  Nothing of this session runs after it.

## What this part did

| UTC | What |
|---|---|
| 15:36 | `ab8be4b` — step 0's spec, sampler, log reader and test, registered (the morning's agent A drafted them; reviewed and tested on the Mac) |
| ≈ 15:40–16:50 | step 0's two runs, 49 min of the Mac; after run 1, `1d21173` (15:59) fixed the reader for the `build` and `system_info` lines Ollama tags |
| 16:06 | three agents on her word: step 1's spec and tools; the cache-ram agent's source read of `--cache-ram` (`.tmp/agents/b_cache_ram.md`, git-ignored, now in PLAN item 5); stage 6's drafts |
| 17:16 | `31c06b2` — step 0's record |
| 19:03 | `3f7b33d`, `1d8558a` — stage 6's fix and drafts |
| 19:25 | `44fd650` — step 1's spec, tools and test registered; 98 focused tests passed on the Mac |
| 19:27–20:00 | run 1 `s1-baba`, unattended by `.tmp/s1control/run.sh`; its gate passed |
| 19:52–19:58 | a load spike, seen live with `ps` and `sysctl` and in no record: macOS's own daemons (`backupd`, `suggestd`, `biomesyncd` and others), load 26.3, swap 2,853 of 4,096 MB; nothing stopped |
| 20:04–20:18 | run 2 waited for the 5-minute load to fall below 2 |
| 20:18–20:44 | run 2 `s1-abab`; its gate passed |
| ≈ 20:50 | step 1's record read on the Mac (the spec's step 7): contention yes, net faster |
| 20:57 | `3fc8ce7` — step 3's spec, reader and test registered; 66 focused tests passed on the Mac (a first run failed one: a pinned phrase split by a line break, rewrapped before the commit) |
| 21:00–21:30 | this handoff and the status files; its cold read (18 points, three blockers, all fixed); the wip branch |

## Step 1: what the runs show, and how to read the record

The runs, read by each run's own gate (`s1-baba.step1.json`, `s1-abab.step1.json` on the Mac):

| Run | Ask | Question | Arm | Retrieval | Vector | Rerank | Whole |
|---|---|---|---|---|---|---|---|
| s1-baba | 1 | dismissal-order | B | 225.0 | 104.0 | 120.9 | 478.5 |
| s1-baba | 2 | leave-sources | A | 186.4 | 70.5 | 115.0 | 342.0 |
| s1-baba | 3 | leave-compensation | B | 100.2 | 66.7 | 33.5 | 282.1 |
| s1-baba | 4 | leave-risk | A | 475.7 | 97.7 | 377.9 | 715.8 |
| s1-abab | 1 | dismissal-order | A | 143.5 | 52.4 | 91.1 | 326.7 |
| s1-abab | 2 | leave-sources | B | 100.4 | 65.4 | 34.9 | 389.8 |
| s1-abab | 3 | leave-compensation | A | 214.1 | 58.0 | 155.6 | 423.9 |
| s1-abab | 4 | leave-risk | B | 112.4 | 70.9 | 41.3 | 291.3 |

Seconds; «whole» is the ask's wall from the action before it to its end.

- **Run 1's fourth ask fell on the load spike:** its rerank of 377.9 s is 2.4–4.1× the other three
  A asks (91.1–155.6 s). The registered rules read it as it is, and the reader reads no load. The
  capsule may print, deciding nothing, the samples' 1-minute `vm.loadavg` inside each ask's
  rerank, read from the copied `.samples.jsonl` after the record: a confound beside the reading,
  not a reason to drop the pair. The daemons' names are in no record.
- **The vector search is slow in both arms** (52.4–104.0 s; the record's median B over A is
  1.038), against 0.2 s with the retrieval alone and 4.8–22.6 s in V4's series for the same
  questions. My reading, deciding nothing: the previous answer pushed the API's pages out, and
  unloading the model does not page them back in. It weighs on «net».
- **The answer is two rules,** both registered and quoted from the spec:
  - **contention yes** when the median of B's rerank seconds over A's is at most 0.5, with at
    least three readable pairs; **no** above it;
  - **net faster** when the median of B's whole seconds less A's is below zero; «within 90 s of
    zero it is the sign alone».

  With fewer than three readable pairs either rule is `NOT_EVIDENCE`. The forecast was contention
  yes (a ratio of ≈ 0.3–0.45) and net faster.
- **The record's pairs** (seconds; B over A for the rerank, B less A for the whole):

  | Question | Rerank B/A | Whole B − A |
  |---|---|---|
  | dismissal-order | 1.3281 | +151.784 |
  | leave-sources | 0.3037 | +47.792 |
  | leave-compensation | 0.2151 | −141.810 |
  | leave-risk | 0.1093 | −424.565 |

  Printed beside them, deciding nothing:
  - inside the reranks the Mac faulted back a median of 2,508.6 MiB in A against 152.9 in B (16.1
    against 4.3 MiB/s); these are whole-Mac counters, a window's by its time, not by process;
  - llama-server held a median of 3,842 MiB at A's rerank;
  - B's first token, timed from the question's start, came a median of 66.9 s earlier. Its answer
    call's first chunk, timed from that call's start and so holding B's model load, came 22.4 s
    later.
- **How far each reading goes** (mine, for the capsule; the rules stand as read). Leaving one pair
  out at a time, in the table's order:
  - **contention** gives 0.2151, 0.2151, 0.3037 and 0.3037: yes each time. The faults are
    consistent with contention, but the spec's «Not said» leaves the mechanism open: the counters
    are the whole Mac's, and step 1 tells neither which encoder waits nor the weights' share from
    the prompt cache's;
  - **net** gives −141.810, −141.810, +47.792 and +47.792: its sign flips when either faster pair
    is left out. A median of four is the mean of the middle two, so four pairs do not settle the
    reload's cost against the rerank's gain;
  - **dismissal-order was each run's first question, in both arms.** It is the only pair where
    B's rerank was the slower.
- **What to tell Julia.** The spec's «Not said» binds: no lever is adopted on four pairs, and the
  reading holds at A's young footprint, not for V4's long series.
  - At step 1's footprint, with the model unloaded, the rerank took a median of about a quarter
    of its time with the model resident.
  - Whether unloading pays for its reload is the open half: faster by the rule's sign alone, on a
    2–2 split.
  - Item 5 measures both candidates in its 30-question series: unloading before each question,
    and the cache cap, which keeps the model loaded (her word on the route).

## Next actions

1. **Step 1's record** ([spec, «Running it» step 7 and «Records»](../specs/stage4-step1-rerank-memory.md)).
   The record is written: do not run `step1_reader.py` again. Every number of the capsule comes
   from the copied `step1.json`, not from this handoff's rounded tables. Then:
   1. `ssh deproject-mac "shasum -a 256 /Users/julia/RAG_new_chat_4f48fed/step1/step1.json"` must
      give the SHA-256 above. A different one: stop and find why.
   2. `mkdir -p D:/RAG_new/reports/stage4-step1/4f48fed`, then copy into it as bytes:
      `step1.json`, `s1-baba.step1.json`, `s1-abab.step1.json`, `s1-baba.q1.step1.json`, the two
      `.samples.jsonl` and `environment.jsonl`, all from `/Users/julia/RAG_new_chat_4f48fed/step1/`.
      Use `ssh deproject-mac "cat /Users/julia/RAG_new_chat_4f48fed/step1/<file>" > <dest>` with
      the literal path (a `$T` inside the quotes would expand on the laptop). Then compare
      `shasum -a 256` with `sha256sum`.
   3. Write the capsule `docs/evidence/stage4-step1-record.md`, by step 0's
      ([record](../evidence/stage4-step0-record.md)) as the model: the question, the stand, the
      gates, the table, both rules with their numbers (net by its sign), the forecast against the
      outcome, the leave-one-out medians and the load spike beside the reading, and «Not said».
   4. Write an artifact test that reads the record again (step 0's `tests/test_stage4_step0_artifact.py`
      is the model). Add a row to `EVIDENCE_INDEX.md`. Then update:
      - the spec's Status line, as `31c06b2` did step 0's. Keep «registered before the first
        request» on one line: `tests/test_stage4_step1_tools.py` pins it;
      - PLAN stage 4 item 1, ROADMAP's stage 4 row, CURRENT_STATE (150 lines, edit in place),
        BACKLOG's queue and docs/README's step 1 sentence.
   5. Run ruff and mypy on the laptop first. Then on the Mac: `python D:/RAG_new/.tmp/mf-mac/sync.py`,
      then `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <tests> -q -p no:schemathesis -p
      no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=short`. Pass it the artifact test,
      `tests/test_stage4_step1_tools.py` and the three docs tests ([`CLAUDE.md`](../../CLAUDE.md)).
      Then commit as `evidence(stage4-step1): …`.
2. **Step 3's runs** ([spec «Running it»](../specs/stage4-step3-k-timing.md)), once the Mac is idle
   and nothing else of ours runs. The spec defines `S`, `PY`, `CL`, `T=$S/step3`, `IX` and `Q`.
   `L` is a run's label, and `KX` its K setting: empty for K = 20, `,RAG_RETRIEVAL_TOP_K=14` for 14.
   - copy four tools from `3fc8ce7`, the spec's `<c>` (its step 1), and `live_api.py` from `$CL`;
     the five SHA-256 must match the spec's list;
   - the four runs in order: `s3-k20-1`, `s3-k14-1`, `s3-k14-2`, `s3-k20-2`;
   - the first question's read in run 1, each run's gate before the next run, then the record.

   A control script modelled on `.tmp/s1control/run.sh` would run them unattended. Its changes:
   - `T=$S/step3`, and a new control folder for `$C`;
   - mode `retrieval`, with the cap 1400 and `KX`. Drop the sampler, the `stand_env.py` lines and
     the `live_runner.py` pkill: the supervisor's own cap ends a run;
   - the idle pgrep pattern `[s]tep[0-3]_`;
   - the first-question trigger becomes the first file in `$T/runs/s3-k20-1/retrieval/`. In this
     mode `progress.log` gets `Q n …` lines and never `CASE`, so run.sh's trigger would not fire;
   - step 3's reader in place of step 1's;
   - run.sh does one run a call and checks no gate. A chain of the four must stop unless the run
     before it passed its gate.

   Copy it to the Mac with the CRs stripped. Then the record the same way as step 1's: capsule,
   artifact test and row. K in production stays her word (§8.3).
3. **Step 4, the shorter prompt and the hints** (PLAN item 4), no Mac at first. My notes, the
   design so far:
   - **The lever.** The prompt's length is set by the fitting, not by the expansion.
     `agent/context_window.fit_context_docs` keeps the leading expanded documents whole while they
     fit `window_input_limit(num_ctx 4096, max_tokens 1024)` (`llm/providers/base.py`), about
     2,636 estimated tokens. It cuts the first one that does not fit to the paragraphs closest to
     the question and drops the rest. On stage 2's export
     (`reports/stage2/retrieval-20261021/p2-*.json`) aircargo was cut in 98 of 100 questions, at a
     median of 2,589.5 estimated tokens and a maximum of 2,636: always at the limit. So the lever
     is a lower input budget for the answer.
   - **The self-evaluation shortens with it:** it fits from the answer's already-fitted documents
     (`api/routers/conversation.py`: the answer's fit, `_fit_stream_prompt`, ≈ line 2168; the
     self-evaluation's ≈ line 2321).
   - **The method is the K curve's:** on stage 2's saved lists, with no model, run the product's
     own fitting at budgets below today's. Read the gold at «sent» by `excerpt_places`
     (`reports/stage2/tools/retrieval_summary.py`) and `read_gold` (`scripts/external_pilot.py`).
     Test with McNemar against today's limit, per base and pooled, and take the smallest budget
     without a detected loss. aircargo has no gold, so only its sent documents and tokens are
     read. Register before the count.
   - **The hints** (13 s) run after the answer's last token; moving them changes the time to the
     badge, not to the answer. That is a UI/API change, rule (a), with an E2E test.
   - **Item 2's experiment, already in PLAN item 2:** the self-evaluation as a continuation of the
     answer's own messages would let llama-server reuse ≈ 2,300 cached tokens, ≈ 55–90 s a
     question by step 0's rates. It changes the score's prompt, so only if the badge stays, and
     that is her word.
4. **Then items 5, 5a, 6 and 7** as PLAN orders them. Item 5's first candidate is the cache cap:
   the line `cache-ram = N` in `~/.config/llama.cpp/config.ini`, or `LLAMA_ARG_CACHE_RAM` with a
   restart of `ollama serve`. The cache-ram agent's reasoned N is 1024 (`.tmp/agents/b_cache_ram.md`,
   now on the wip branch); step 5's spec sets it. Both routes change her shared Mac, so both are
   her word. The agent's source read is in PLAN item 5.

**Do not:**
- run anything on the Mac while another measurement or another project's heavy job runs (the idle
  rule in each spec);
- stop another project's process;
- open `.ask100-runtime/env.json` or any `.env`;
- commit `demo/phase-e-raw.webm` or `reports/ask100/`, which are not this session's;
- push without her word;
- reword a sentence an artifact test pins without a grep first.

**Once Julia answers:**
- **«да» on stage 7:** amend PLAN stage 7 to P1b alone, with her quote and date, then rerun
  ROADMAP's estimate.
- **The push:** ci_local's full run on master
  (`python C:/Users/uedom/.claude/scripts/ci_local.py --repo D:/RAG_new`, in the background, once,
  never during a live Mac run), then push over HTTPS as [`CLAUDE.md`](../../CLAUDE.md) says.
- **The cache cap's route:** step 5's spec, registered before its 30-question series; the line
  is removed after the series unless she keeps it.

## State at the end

- Mac: no process of this session; the stand `/Users/julia/RAG_new_chat_4f48fed` keeps its runs.
  - step 0: `step0/`;
  - step 1: `step1/`, with `runs/s1-baba` and `runs/s1-abab`, their samples, reads,
    `environment.jsonl` and the record `step1.json`;
  - step 1's control folder: `/Users/julia/RAG_new_s1control_20261028`, holding `run.sh`, `q1.py`
    and `control.log`.
- Laptop: the control scripts in `.tmp/s1control/` and the step 4 notes in `.tmp/s4/notes.md`
  (both git-ignored; the notes' content is in this handoff, the scripts are not), and in
  `.tmp/agents/` the agents' briefs and the cache-ram agent's report.
  - **Backup:** these, with `.tmp/mf-mac/sync.py` and `remote.py`, are on the local branch
    `wip/stage4-step1-stop`, `b4ceecd`, built on `3fc8ce7` through a temporary index: 15 files,
    each checked against `hash-object`. It is not pushed and exists on the laptop only.
  - It is not for merging. Restore only if the tree lost them: `git -C D:/RAG_new diff
    --name-only wip/stage4-step1-stop~1 wip/stage4-step1-stop | xargs git -C D:/RAG_new restore
    --source=wip/stage4-step1-stop --worktree --`.
  - Left out: the MultiHop-RAG agent's downloaded external files (`.tmp/agents/c-mmrag`,
    `c-official`, `c-paper`), which are untrusted data.
- Untracked and not this session's: `demo/phase-e-raw.webm`, `reports/ask100/`.

## Glossary

- **Arm A / arm B** — step 1's two orders. In A the model stays resident: the runner re-sends the
  preload with `keep_alive` 30m before each question. In B it is unloaded before the question
  (`keep_alive` 0, then polled until neither Ollama nor `ps` lists it), and the answer's call loads
  it again.
- **BABA / ABAB** — the arms' order over the four questions in run 1 and run 2, so that each
  question is asked once in each arm, at the same position.
- **Readable pair** — a question's A ask and B ask, both read, both arms held, the same position
  and the same candidate pool (by SHA-256), from runs whose gates passed.
- **Contention** — the rerank waiting for memory the resident model holds; read as B's rerank over
  A's.
- **Net** — B's whole seconds less A's: whether unloading pays for its reload.
- **Retrieval-only mode** — the supervisor's mode `retrieval`: stage 2's `live_retrieval.py`, the
  API's retriever with no API, database or model; a file per question with its walls, lanes,
  pool and the five kept.
- **K** — `RAG_RETRIEVAL_TOP_K`, the candidates each lane gives the fusion (20 today). It is read
  when the process starts, so it changes between runs, never between questions.
- **ABBA** — step 3's run order, K = 20, 14, 14, 20, which puts a drift over the hour on both K
  alike.
- **Host prompt cache** — llama-server's in-memory store of prompt states (`--cache-ram`, default
  8192 MiB), step 0's cause of the growth.
- **P1b** — the extended context cut of the earlier measurements, +0.0207 precision, rejected only
  by the 0.63 ruler; one of stage 7's two candidates, beside the graph lane.
- **0.63 ruler** — the old gate of 0.63 lexical context precision, a ruler that does not track
  meaning; retired (PLAN §8.2).
- **Step N, item N** — PLAN stage 4's item N; the specs of items 0, 1 and 3 call them steps.
- **Gate** — a run's own checks in its read (launch, settings, drivers, asks and the like); a run
  counts only when its gate passed.
- **Capsule** — a record's write-up in `docs/evidence/`, with its row in `EVIDENCE_INDEX.md`.
- **Badge** — «Качество: N», the self-evaluation's score the client sees.
- **DB role** — `ragnew_chat`, the database role the service would log in as
  ([macOS service](macos-service.md)).
- **First chunk, first token** — an answer call's first chunk is timed from that call's start, so
  B's holds its model load; the first token is timed from the question's start.
- **The agents' letters** — the morning's three (A: step 0's tools; B: the K curve; C:
  MultiHop-RAG) are the previous handoff's. Of the three at 16:06 this handoff names one by its
  task, the cache-ram agent; its report's file is still `b_cache_ram.md`.
- **`$S`, `$T`, `$C`, `$PY`, `$IX`, `$CL`** — the stand `/Users/julia/RAG_new_chat_4f48fed`; a
  step's tool folder (`$S/step1`, `$S/step3`); step 1's control folder; the interpreter
  `/Users/julia/RAG_Support_Assistant/.venv/bin/python`; the index
  `/Users/julia/RAG_new_external_s1/aircargo`; `$S/chatlive`.

## Lessons

- **An idle Mac at a run's start does not keep it idle.** macOS's daemons started at ≈ 19:52 with
  nothing of ours or of other projects involved and tripled one rerank. A run's record reads the
  load per ask from its samples, and a spec names that confound in advance.
- **mypy before the SHA is frozen.** A tool's SHA-256 goes into its spec at registration, so the
  type check and the format come first. A fix after that is a marked error fix with a new SHA.
- **A setting read at start is a run's arm, not a question's.** K cannot alternate within a run;
  the design is runs in ABBA. The question-level pairing comes from asking the same questions at
  the same positions.
- **Measure the cause you mean without the cause you don't.** Step 3 reads K's rerank seconds
  without a model, because with the model resident the spread was 0.30–2.18 between the same arm's
  series. A third less work would not have shown through it.
- **Agents stop on network errors.** The three agents of 16:06 all stopped once. Resuming each with
  SendMessage kept its context, so check an agent's end before you count on its files.
- **A median of four can turn on one pair.** Step 1's net reading is the mean of its middle two
  pairs; without the load-spike pair its sign flips. A spec with four pairs should print the
  leave-one-out medians beside its reading. Step 3 has twelve pairs and a sign test.
- **A pinned phrase must sit on one line.** The step 3 test checks `phrase in spec`, and a line
  break inside «at least 10 of 12» failed it on the Mac. The phrase loop stops at its first
  failure, so check every phrase with a laptop one-liner before the Mac run.

## Verification

- `3fc8ce7`: `tests/test_stage4_step3_tools.py` and the three docs tests passed on the Mac, 66
  tests; step 1's tools test passed in the run before.
- The cold read: a fresh subagent on the session's model read this handoff against the status
  files, the two specs and the code. It found 18 points, three of them blockers: the net rule's
  sign, two claims beyond step 1's «Not said», and run.sh's first-question trigger. Each was
  checked against its source and fixed here, in CURRENT_STATE and in ROADMAP.
- This handoff's commit: the three docs tests passed on the Mac after the fixes, 23 tests.
- Step 1's record: both gates `passed`, the readings as above, read from `$T/step1.json` on the
  Mac. Its SHA-256 is printed above.
- The wip branch: 15 files, 0 mismatches against `hash-object`.
- The Mac at the end: no process of this session, no model loaded (`/api/ps` empty).
