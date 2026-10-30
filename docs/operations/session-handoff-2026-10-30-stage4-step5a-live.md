# Session handoff 2026-10-30, third — item 5a read, the n-gram lever closed, INT8's live series `NOT_EVIDENCE`; stage 7 step 1 registered; the package question open

The session ran 2026-10-30 13:17 – ≈ 21:15 UTC from the
[block 6 handoff](session-handoff-2026-10-30-stage4-step5a-block6.md) and was compacted 18
times. All times are UTC; the laptop's clock is EDT (git's `-0400`), the Mac's UTC+3. The block 6
and [block 1](session-handoff-2026-10-30-stage4-step5a-block1.md) handoffs still hold for their
glossaries, the Mac's paths and their «Do not». Their next actions are done but three: the
package question, stage 7 step 1's run (now under her answer) and the push. This file's next
actions replace them.

## Read this first

- **Stage 4** cuts the chat's answer time on the Mac (i5-7500, 4 cores, 8 GB, shared with other
  projects; a median answer ≈ 320 s). Each lever is measured on its own, on the idle Mac, and
  recorded; none is adopted. Adopting them is Julia's word (PLAN §8.3, item 2), asked once, as
  one package.
- **Where the levers stand,** each a record and a row in `EVIDENCE_INDEX.md`:

| Lever | Speed, measured | Quality, measured | Record |
|---|---|---|---|
| K = 14: each lane's first 14, not 20 (the reranker scores a median 24–26 candidates, not 34–36) | the rerank a median 14.6 s less, 12 of 12 (new/old 0.528) | gold 136 of 250 against 141: no detected loss (p 0.125), not «no loss» | [curve](../evidence/k-curve-record.md), [timing](../evidence/stage4-step3-record.md) |
| num_ctx 3,584, not 4,096 | the two prompts a median 24.7 s less, 12 of 12 (new/old 0.792) | no detected loss; 3,328 loses (127 against 137 of 250, p 0.002) | [count](../evidence/stage4-step4-record.md), [timing](../evidence/stage4-step4b-record.md) |
| `cache-ram = 1024`, the host prompt cache's cap | its seconds not measured | changes no answer; the swap holds: −180.25 MiB from questions 6–10 to 26–30, against +4,452 MB without the cap | [record](../evidence/stage4-step5-record.md) |
| INT8 of the reranker (`81cd2ad`'s setting) | idle: faster on 30 of 30, a median 12.0 s less of 28.2 s (PyTorch/INT8 1.751); in the chat `NOT_EVIDENCE` | gold 141 → 144 of 250 (b 1, c 4); **its five differs on 307 of 400** | [idle](../evidence/stage4-step5a-record.md), [chat](../evidence/stage4-step5a-live-record.md) |
| n-gram decoding | `NOT_EVIDENCE`; the readable seven: slower on 6, faster on 1 (p 0.125), no reading | answers differ on 4 of 13 | [closed](../evidence/stage4-step5a-ngram-record.md) |

- **Why one package:** K, the window and INT8's changed fives each change the answer path, and
  any change of it costs the whole re-measure: item 6 (100 aircargo answers anew, ≈ 6–8 h of the
  Mac, the judge's M1 and M3) and stage 5 (300 external answers, ≈ 17–30 h, ≈ 330 judge
  requests). Three such levers together cost what one costs. The cap changes no answer. Items 6
  and 7 measure the adopted package at once: levers measured apart do not add up (PLAN, F4).
- **INT8's live series stopped in its first block: `NOT_EVIDENCE`, nothing read**
  ([below](#the-live-series)). Another project's job on the shared Mac ran at the end of both
  INT8 runs, and step 7's look at the Mac stopped the series, as registered. What it printed,
  deciding nothing: INT8's rerank 21.6–34.1 s against PyTorch's 126.9–336.9 s on block 1's five,
  one run a side. There is no successor series ([my choices](#my-choices-not-hers)).
- **Open for her, one yes/no:** the package. Asked in the stop point's closing message, after
  this file's commit; no answer when this file was written. The question as asked:

  > Включаем пакет одним решением — K = 14, num_ctx 3 584, `cache-ram = 1024` и INT8
  > реранкера — и перемеряем путь целиком (п. 6, п. 7, этап 5)?

  My recommendation is yes: K, the window and INT8 (idle) save seconds and the cap holds the
  swap, with no detected loss of the gold, and the re-measure that a yes costs is the number of
  the final path that PLAN needs anyway. K 14's five fewer gold questions are not a detected
  loss; item 6 and stage 5, which judge the answers themselves, are where a real loss would
  show.

## Once Julia decides

- **Yes, all four:**
  1. A slice sets the path, with an E2E test (rule (a)): `retrieval_top_k` 14,
     `ollama_context_window` 3,584, `RAG_RERANKER_RUNTIME=onnx` with `RAG_RERANKER_ONNX`
     (`config/settings.py:489–503`, `vectordb/onnx_reranker.py`). Its first decision is
     defaults in code or the stand's environment, and three facts bear on it:
     - the 571-MB export lives on the Mac at
       `/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`, not in the repository,
       and `onnx` raises where the file is absent (`config/settings.py:1427–1440`): CI, the
       laptop, a gate's checkout;
     - stage 7's guard sees code defaults only: `control()`
       (`reports/stage7/tools/arms_replay.py:591`) builds the settings in the replay's own
       process, without the stand's environment. On the environment route it still sees K 20,
       4,096 and `torch`, passes, and would replay the old H;
     - onnxruntime is not in `requirements.txt`; `requirements.lock` carries 1.25.0
       transitively, not the measured 1.23.2. The slice names the version.

     On the Mac, the line `cache-ram = 1024` in `~/.config/llama.cpp/config.ini`
     ([item 5's spec](../specs/stage4-step5-cache-cap-series.md), lines 29–54): Ollama 0.33.2
     passes no `--cache-ram`, and llama.cpp reads that file at every start, other projects'
     models too. Her yes is the word that file needs.
  2. Stage 7 step 1 takes an amendment, cold-read and registered before the replay
     ([its spec](../specs/stage7-step1-arms-m3.md), lines 15–23). Its tool freezes `KMAX = 20`,
     `WINDOW = 4096`, `LIMIT = 2636` and `torch` in `CONTROL` (`arms_replay.py:108–113`); the
     amendment sets 14, 3,584, 2,176 (the input limit at 3,584,
     [step 4's record](../evidence/stage4-step4-record.md)) and `onnx`. It brings INT8's scores
     for all 415 questions: item 5a's for stage 2's 400 lie on the Mac in
     `/Users/julia/RAG_new_s4p5a_runs/blocks/`; aircargo-gr's 15 need new scoring code. Then
     the replay, ≈ 10 min of the Mac.
  3. Item 6's spec, cold-read and registered before its first request, then its run; item 7's
     (30 questions, ≈ 2.5 h; then an SLO proposal, which she names); stage 5's. None of the three
     specs exists yet.

  The replay before item 6 is my order, not PLAN's: in minutes it shows whether stage 7 has a
  candidate at all. It changes nothing before item 6: an arm gets answers only paired against
  the published base (item 6 and stage 5), and is adopted only at stage 7's step 4, within the
  SLO.
- **No:** the path stays K 20, 4,096, PyTorch, no cap. The stage 7 replay runs as registered.
  Item 6 and stage 5 are skipped (PLAN: «если путь не менялся»), and the published base stays
  the current path's numbers. PLAN calls them «числа этапа 2», written before V4 replaced stage
  2's prompt: they are [V4's record](../evidence/answer-prompt-v4-record.md) for aircargo,
  WixQA and ConditionalQA, and [stage 2's](../evidence/stage2-record.md) for MultiHop-RAG,
  which V4 did not run — a V3 number on a V4 path, a gap to name beside it. Item 7 times
  today's path (its spec first).
- **Part of it:** as yes, with that part:
  - the cap alone changes no answer: the config file and item 7 only — no slice, no amendment,
    no item 6 or stage 5;
  - K or the window without INT8: the slice, an amendment without INT8's scores, item 6 and
    stage 5 whole;
  - INT8 without K or the window: the amendment keeps K 20, the window 4,096 and the limit
    2,636; item 6 and stage 5 whole.

## Julia's words in this session (UTC)

- 13:17 «продолжи доработку по handoff.md» — the block 6 handoff's next actions, in order.
- 20:02 «сессия длинная, поставь точку, где логично. и обнови доку» — this stop point. The live
  series' record was committed first, then this file, the status lines and the backup.

No other word of hers: no answer on the package, no push.

## What this session did

| UTC | Commits | What |
|---|---|---|
| 13:37 | `0861e88` | Item 5a's record: `int8` passes — the gold holds, faster on 30 of 30 — but its five differs on 307 of 400 (another set on 179, another order on 128). QUInt8, the fallback, did not run. |
| 13:42 | `04003fb` | The help page: «Качество» is the model's own self-evaluation, not calibrated (the audit's F2). A browser test, red before, green after. The widget's «пары секунд» waits for the SLO. |
| 14:16 | `81cd2ad` | `RAG_RERANKER_RUNTIME=onnx` with `RAG_RERANKER_ONNX`: the chat reranks with 5a's INT8 export; the default stays `torch`; an E2E test. |
| 14:34, 14:37 | `5558ca8`, `8e527fc` | The n-gram spec, its tool and test, registered after its cold read; `<c>`. |
| 14:38–16:58 | `3df2aef` | The n-gram series and its record: `NOT_EVIDENCE`, 7 of 13 readable where 10 are needed; jobs not ours disturbed six questions in blocks 2–4. The readable seven: slower on 6, faster on 1 (p 0.125). The lever closes. |
| 17:06, 17:10 | `3136fb8`, `29a352f` | The live series registered after its cold read (eight findings applied); `<c>`, and `81cd2ad`'s row in EVIDENCE_INDEX. |
| 17:14–19:29 | — | The live series: three runs, then the stop. |
| 19:41, 19:43 | `8b922a1`, `4a8957a` | Stage 7 step 1 registered after its cold read (fifteen findings applied); `<c>`. |
| 20:16 | `18467bf` | The live series' record: `NOT_EVIDENCE`. Its capsule, test and thirteen files; the spec's «Read» line; PLAN, ROADMAP, CURRENT_STATE, BACKLOG and docs/README. |

Each commit's files passed a gate on the Mac on its own tree. The record's gate ran
`tool_gate.py`: 536 passed, 10 skipped, tree `1bfd3b9b85`, equal to `git write-tree` before
the commit.

## The live series

- **What it asked:** is INT8 faster than PyTorch inside the chat, on one commit (`81cd2ad`),
  question by question? The design: eight runs ABBA twice, twenty pairs in four blocks; a
  reading by the exact sign test, p < 0.05, every block leaning its way, at least 16 of 20
  pairs readable. Spec: [`stage4-step5a-live.md`](../specs/stage4-step5a-live.md).
- **What happened:**
  - `s5a-torch-1` ran from 17:14; step 7's line after it held 0 matches.
  - `s5a-int8-1` ran from 18:12; its line held 2 matches. By step 7 it ran again as
    `s5a-int8-1-r2` from 18:51; its line held 2 again.
  - Step 7's rule: a rerun that fails again leaves its block's five pairs unread. At most 15
    of 20 could then be readable, below 16: `NOT_EVIDENCE`. The chain stopped at 19:29:36.
  - Step 4 (the stand's state after the last run) and step 8 (the reader over `s5a-torch-1`
    and `s5a-int8-1-r2`) were run by hand at 19:37:45, logged in the chain's `control.log`.
    The stand passed and every run passed its gate.
- **The cause, outside the record:** the supervisor's per-run process log on the Mac. A Python
  of another project's virtual environment ran at 72–100 % CPU at 17:26–17:39 (inside
  `s5a-torch-1`, gone before its line), 18:38–18:41 and 19:24–19:28 (each INT8 run's end). No
  model, no lock and no `llama-server` of ours after either INT8 run. Which process step 3's
  pattern matched, the line does not say. The capsule does not name the other project, and
  neither does this file.
- **Printed, deciding nothing,** on block 1's five: INT8's rerank below PyTorch's on 5 of 5
  (p 0.0625), a median ratio PyTorch/INT8 6.753; the whole question below on 4 of 5
  (p 0.375), a median 321.9 s against 542.1 s. PyTorch faulted back a median 2,279.906 MiB
  inside the rerank, INT8 595.395. One run a side, with the other job inside both: a pace, not
  a reading. In the chat's memory pressure INT8 may save far more than its idle 1.75×, but
  nothing here shows it.
- **The record's test, fixed before the gate** (the light check on the laptop found it; see
  [Lessons](#lessons)):
  - two samples lie 1 ms and 8 ms from a question's summed edge (`s5a-torch-1`'s second,
    `s5a-int8-1`'s sixth). The guard now asserts what matters: moving either edge 0.01 s
    either way leaves the question's load and the samples' cover as recorded;
  - one note, `top: no row for pid 1339`, is the rerun's `llama-server` exiting 7.6 s after
    its last question. Step 1's frozen reader keeps it quiet, and the test pins it there.

## Stage 7 step 1 — registered, waiting for the package

- **What:** do the retrieval arms S (the structural graph's section expansion) and P (P1b, H's
  five cut by the reranker's scores) raise M3 over H on stage 2's saved lists, without an
  answer? An arm goes on to answers only on an M3 gain larger than the MDE at ConditionalQA and
  WixQA pooled. Spec: [`stage7-step1-arms-m3.md`](../specs/stage7-step1-arms-m3.md); tool:
  `reports/stage7/tools/arms_replay.py`; test: `tests/test_stage7_arms_replay.py`; cold read:
  [`audit_opus55_30_10_26_stage7_gate.md`](audit_opus55_30_10_26_stage7_gate.md).
- **How to run:** the spec's «Running it on the Mac» — the idle Mac, `sync.py`, the named
  tests, then `remote.py --site reports.stage7.tools.arms_replay replay`: ≈ 10 min, stopped at
  30. A judge plan exists only for an arm that qualifies: at most 268 requests, $25–56,
  2.7–9.7 h of the laptop.
- **When:** after her answer. On no, as registered; on yes, after the amendment above.

## My choices, not hers

1. **No successor live series.** The disturbance came three times in two hours from a job not
   ours, which we never stop. A second series of ≈ 6 h would likely meet it again. Items 6–7
   measure the adopted package in the chat anyway, and that is the number that counts.
2. **The package recommendation: all four, INT8 on its idle numbers.** The live spec's outcome
   «no detected difference» would also have named INT8 with its idle numbers. `NOT_EVIDENCE`
   reads nothing, so the idle record is INT8's evidence.
3. **Stage 7 step 1 registered before her answer.** The block 6 handoff allowed it: «its cold
   read and registration need not wait for her answer; its run does».
4. **The replay before item 6** on a yes ([above](#once-julia-decides)).
5. **The record's test refined, not loosened,** where the data broke two of its assumptions.

## Next actions

1. **Her package answer** → [Once Julia decides](#once-julia-decides). If she asks something
   else first, answer it first.
2. **The push, only on her word.** 56 commits after `7caaf21` with this one. Before it, a full
   ci_local run with PASS, started once in the background, never during a Mac measurement:
   `python C:/Users/uedom/.claude/scripts/ci_local.py --repo D:/RAG_new`.
3. **Until she answers, nothing of stages 4–7 runs.** If her word is not an answer, do what it
   asks, then ask the question again as written. No job of ours runs on the Mac or the laptop.

**Do not.** The block 1 and block 6 lists hold. Also do not:
- start another live series of INT8 without a new registration: this one is recorded
  `NOT_EVIDENCE` and closed;
- delete `$O` (`/Users/julia/RAG_new_s4p5a_runs`, item 5a's blocks with INT8's scores) or `$M`
  (`/Users/julia/RAG_new_ort/bge-reranker-v2-m3`, the export) before the slice and stage 7's
  amendment have read them;
- edit the live series' tools (`reports/stage4-step5a-live/tools/`), item 5a's tool, its
  export or the step 1 reader they load;
- create `~/.config/llama.cpp/config.ini` on the Mac before her yes;
- run a Mac job of ours while any measurement series runs, or two of ours at once;
- commit `demo/phase-e-raw.webm` or `reports/ask100/` (not this work's), or push without her
  word.

## State at the end

- **The Mac,** read at 20:18:34: load 1.23, 1.19, 1.36; no pytest, `llama-server`, supervisor,
  replay, sampler or CI VM of ours; Ollama holds no model; no CI lock;
  `~/.config/llama.cpp/` does not exist.
  - The stand `/Users/julia/RAG_new_chat_81cd2ad` (code `81cd2ad`) is kept. Its `live5a/`,
    9.4 MB, holds the record's files, the samplers' files and the supervisor logs. The runs'
    index copies were removed after each run.
  - It may go now that the record is committed; nothing needs it gone.
- **The laptop:** HEAD is this stop point's commit, 56 commits after `7caaf21`, not pushed.
  Untracked and not this work's: `demo/phase-e-raw.webm`, `reports/ask100/`. This session's
  git-ignored scripts: `.tmp/s5a/` (the gates, the messages, `live_control/` with the chain
  that ran the series), `.tmp/coldread-live/`, `.tmp/ngram/`.
- **Backup:** the branch `wip/stage4-step5a-live-stop` ([Verification](#verification)).
- **No Monitor, agent or background job** of this session runs after it closes.

## Lessons

- **The shared Mac costs series.** Jobs not ours disturbed two series in one day: the n-gram's
  blocks 2–4 (six questions) and both INT8 runs of the live series. Before a series of hours,
  look at the Mac's process list over the previous hours, not only at its idle check.
- **A rule that stops on any foreign process stops at the first one.** Step 7's look is honest
  but all-or-nothing. A future spec can read disturbance from its own sampler, question by
  question, as the n-gram spec did, and keep the clean questions.
- **An artifact test written before its data goes through a light laptop check before the
  gate.** Calling its plain checks from a script found three failures at no cost of the Mac.
  Each was an assumption the data broke. The fix asserts what moves, never a looser threshold.
- **A tool that reads during a measurement touches no big file.** The live reader's first
  draft hashed the 571-MB export during the first-question read and would have filled the
  page cache beside the timed processes. The cold read caught it; the hash runs after a run.
- **Every number in a capsule comes from the test's printed rows.** The n-gram capsule's first
  draft gave a load maximum of disturbed samples as a block's.
- **Assertions that cannot fail:** an `or True`, refusal tests whose prefix differed from the
  positive test's. Write the expected value whole.
- **The Bash tool:** `cd` moved the working directory twice; a heredoc with apostrophes failed;
  scp with brace expansion failed (one scp a file); `grep -c $'\r'` counts every line (count CR
  by Python bytes); `Glob *.md` at the root matched 11,691 files (`ls`); a recursive grep over
  `D:/RAG_new` ran past 300 s (name directories).
- **Eighteen compactions in about eight hours.** Start the next session fresh from this file.

## Glossary

The block 1 and block 6 glossaries hold. New here:
- **The package:** K = 14, num_ctx 3,584, `cache-ram = 1024` and INT8, adopted together by one
  yes (PLAN §8.3, item 2).
- **Idle numbers:** a lever's seconds measured on the idle Mac without the chat, as item 5a's
  thirty; **in the chat:** inside `/api/ask/stream` with the answer model resident.
- **INT8, PyTorch (`torch`), ONNX:** the reranker `BAAI/bge-reranker-v2-m3` as an 8-bit export
  run by ONNX Runtime 1.23.2, against the model in PyTorch's CrossEncoder; chosen by
  `RAG_RERANKER_RUNTIME`.
- **The five:** the reranker's five documents sent to the answer model; **gold:** a labelled
  question's evidence among them after the parent expansion; **b, c:** questions where the gold
  holds under one side only.
- **A run, a block, a pair (the live series):** a run is one fresh API, database and
  `llama-server` answering six questions, the first a warm-up; a block is a PyTorch run and an
  INT8 run; a pair is a question at one position in both. **Readable:** a pair the reader
  counts.
- **Step 7's look, matches:** the line after each run — load, models, lock, and the count of
  step 3's process pattern (`matches`). A run failing it runs again as `-r2`; a rerun failing it
  leaves its block unread.
- **The stand, `$S`, `$T`:** the checkout `/Users/julia/RAG_new_chat_81cd2ad` and its
  `live5a/`.
- **The chain:** `.tmp/s5a/live_control/chain.sh`, which ran the series' steps on the Mac and
  stopped at the rerun's line.
- **Printed, deciding nothing:** the reader's medians and counts outside the reading rule.
- **Items 6 and 7, stage 5:** the final path's 100 aircargo answers, its speed on 30
  questions, and the 300 external answers; item 6 and stage 5 run only if the path changed,
  item 7 always.
- **M1, M2, M3 (PLAN):** M1, the judge's (`claude-opus-5-5`) verdict on an answer against the
  context it saw — good, partial, bad — and on its [N] citations; M2, correctness against the
  reference (external bases by the judge, aircargo by keywords); M3, retrieval — the answer in
  the sent context (aircargo, by the judge) or the gold evidence's coverage (external bases).
- **aircargo-gr:** stage 2's 15 aircargo questions that need several documents
  (`evaluation/curated_cases_aircargo_gr_multihop.jsonl`, run `p2-aircargo-gr`).
- **The supervisor:** `reports/stage4-step5a-live/tools/live_supervisor.py`, this series' copy
  of step 1's; it runs a run's API and logs the Mac's processes beside it. **The sampler:**
  step 0's `step0_sampler.py`, the Mac's paging, swap and `llama-server`'s memory every few
  seconds.
- **Faulted back:** page-ins plus decompressions (`reports/stage4-step1/tools/step1_reader.py`).
- **SLO:** the answer-time target Julia names after item 7.

## Verification

- **The record:** `git -C D:/RAG_new show --stat 18467bf`; its test on the Mac:
  `python D:/RAG_new/.tmp/mf-mac/sync.py`, then
  `python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q tests/test_stage4_step5a_live_artifact.py`.
- **The Mac's state:** the spec's step 3 line over ssh:
  `ssh deproject-mac 'sysctl -n vm.loadavg; pgrep -fl "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[01]_|[n]gram_decode|[l]imactl" || echo none; curl -s http://127.0.0.1:11434/api/ps; ls $HOME/ci_local/.lock_ci-local 2>/dev/null || echo "no lock"'`.
- **The commits:** `git -C D:/RAG_new rev-list --count 7caaf21..HEAD` gives 56 at this stop.
- **The stop point's commit:** its docs gate ran `docs_gate.TESTS` on the Mac on its bytes;
  the commit message gives the count.
- **This file:** read cold before its commit by one fresh agent on this session's model,
  read-only, on the file and the repository: eighteen findings, each checked against the
  repository and applied, one of them corrected (onnxruntime is in `requirements.lock`).
- **The wip branch:** `wip/stage4-step5a-live-stop`, built on the stop point's commit right
  after it, by `.tmp/s5a/make_wip_backup3.sh` through a temporary index. A commit cannot name
  what comes after it: `git log -1` and `git diff --name-only` of the branch give its SHA and
  files.
  - It holds the previous backup's git-ignored files that still exist, `.tmp/s5a/`,
    `.tmp/coldread-live/`, `.tmp/coldread-s7/`, `.tmp/coldread-ngram/`, `.tmp/s4p4/`'s gates
    and `.tmp/ngram/`'s notes.
  - The script compares each with disk by `git hash-object`. It is local and never pushed.
  - Restore only if the working tree lost them:
    `git -C D:/RAG_new diff --name-only wip/stage4-step5a-live-stop~1 wip/stage4-step5a-live-stop | xargs git -C D:/RAG_new restore --source=wip/stage4-step5a-live-stop --worktree --`.
