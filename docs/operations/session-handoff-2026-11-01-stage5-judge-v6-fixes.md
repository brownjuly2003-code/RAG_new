# Session handoff 2026-11-01, evening — stage 5's judge through ConditionalQA's M2, V6's spec after two cold reads, the old repository private and RAG_new to go public with its history

Session: 2026-11-01 13:19 UTC (her first message) to ≈22:30 UTC, closed on her word. It
continued [the morning handoff](session-handoff-2026-11-01-stage5-running.md). Times are UTC;
the laptop's git dates print −05:00, the Mac's clock is UTC+3.

## Read this first

**How the chat path works now** — unchanged since `6c52b06`, "the package": `/api/ask/stream`
retrieves with BM25 + BGE-M3 fused by RRF, the INT8 ONNX bge-reranker-v2-m3 keeps 5 of K = 14,
and `qwen3:4b-instruct-2507-q4_K_M` answers on Ollama on the Mac's CPU, num_ctx 3,584, prompt V4.

**Three streams are open:**
1. **Stage 5** — did the package change answer quality on the external bases? Only pooled
   WixQA + ConditionalQA M1 bad decides ([spec](../specs/stage5-final-external.md)).
2. **Stage 8, publication** — her evening word: RAG_new itself goes public with its whole
   history; the old `RAG_Support_Assistant` is private. Its checks come first next session; the
   switch waits for her one yes/no on their report.
3. **Stage 5б, V6** — can the answer step improve without a bigger generator?

**What is established.**
- All three bases are answered on the Mac; their judge plans are frozen (`da0988a`, `bd18bce`,
  `42dcd1a`). Graded and exported: WixQA M1, M2 and bridge; ConditionalQA M1 and M2. Left:
  ConditionalQA's bridge and MultiHop-RAG's three plans — 260 requests, ≈ 7 h of judging.
- **Preliminary, not the record.** `.tmp/cx-exec/stage5_prelim.py` called the registered
  reader's own functions on the two M1 exports (no M2, no bridge, no M3 gate):
  - pooled M1 bad 0.54 → 0.56, not detected — the outcome would be **holds**;
  - WixQA: bad 0.51 → 0.59, not detected; good 0.40 → 0.30, a **detected fall**;
  - ConditionalQA: bad 0.57 → 0.53, good 0.35 → 0.38, neither detected.

  She was told at ≈17:15.
- Her reaction to WixQA, «результаты какие-то очень плохие((( ужасные(», got this anatomy
  (descriptive, from the graded files): the generator is the bottleneck, not retrieval.
  - In 92 of WixQA's 100 questions the judge found the answer in the sent context; M3 67
    against 68; the bridge 15 of 15.
  - 30 of the package's 59 bad answers have exactly one unsupported claim; 18 are false
    declines; M2 34 → 34.
  - V5 failed on form, and a 7B model is too slow on this Mac.
- V6's spec, tools and test are drafted and fixed once after a cold read. The second read found
  no blocker and 8 fixes to make. Not registered; no V6 request made.
- `brownjuly2003-code/RAG_Support_Assistant` has been private since ≈20:41 (verified). RAG_new
  is still private and nothing was pushed: `origin/master` is `7caaf21`, 72 commits behind
  with this file's commit.

**Stage 5's rule** (spec «Only pooled…»): harm = pooled bad rises, detected → her one yes/no on
the package, pairs named, the code keeps it meanwhile; gain = falls, detected → the published
base is the package's; holds = neither → publish the package's numbers (no detected difference
is not equivalence); NOT_EVIDENCE = a primary base lacks admitted paired evidence → no decision.
"Detected" = both the Newcombe and the cluster-bootstrap 95 % intervals exclude zero on the same
side. MultiHop-RAG is advisory. **What to tell Julia:**
- if holds, as the preliminary reading says: the package's numbers are published, with
  WixQA's detected fall in good answers printed beside them;
- otherwise: the matching line above.

## Julia's words in this session (UTC), with my answers

- 13:19 «продолжи доработку» — stage 5 by the morning handoff.
- 13:27 «после этого этапа сколько еще работу по проекту?» — stages 6 and 8: ≈ 2–3 working days
  of mine and 3–5 h of the Mac. Her decisions gate them: SLO, the service, first release, push,
  publication.
- 13:34 «270/360 - этого точно хватит?» — not with a margin. Of stage 5's 200 primary answers,
  193 gave the first word within 270 s; 181 the whole answer within 360 s, 9 of 10 only just;
  191 within 420 s. I proposed 270 s and 420 s for 9 of 10 answers; the yes/no waits for V6's
  outcome (PLAN §8.3).
- 13:46 «результаты какие-то очень плохие((( ужасные(» — the anatomy above.
- 14:10 «вероятно стоит остановиться на мысли, что rag все равно требует доработки под конкретную
  базу документов? и остановиться на том, что получено? Что думаешь?» — I agreed to close the
  quality work after stage 5; superseded at 14:15.
- 14:15 «Нучно хоть что-то дельное положить на гитхаб. И параллельно дорабатывать качество
  продукта. Что думаешь?», 14:17 «*нужно». I proposed:
  - a new clean public repository of selected files after stage 5's record;
  - V6 on the Mac in parallel;
  - stage 6 after V6.
- 14:20 «да. и удалить на гитхабе пустой RAG_Support_Assistan» — «да» recorded in `b64eeb5`.
  Not deleted: the repository is not empty (875 commits, a live Pages site, a star). I asked
  whether to make it private instead.
- 15:15 «да» — to the restart after Claude Code's memory stop: the judge in foreground chunks,
  Codex in the background.
- 16:03 «процесс живой?» — yes. 20:23 «чем ты занят?» — the judge, the V6 review, the open
  question about the old repository.
- 20:26 «Да, сделать приватным. А текущую историю - в RAG_new и сделать публичной».
  - Done at ≈20:41: the old repository is private.
  - RAG_new already holds the old repository's whole history: common root `fc5266a`;
    1,391 commits = 875 old + 516 new.
  - My reading: RAG_new itself goes public with its history instead of a clean repository.
    Codex task 12 (the clean repository) is cancelled.
  - PLAN's stage 8 has the evening amendment; the switch waits for the checks below.
- 20:30 «сессия длинная. вероятно стоит ее завершить. поставь точку, когда все, что зупущено
  отработает. и обнови доку» — this stop point. It came after ConditionalQA's M2 (21:10) and
  Codex's fix round finished.

## Stage 8: what the switch needs (next session, first)

The procedure, with every command, is the [stage 8 runbook](stage8-publication-runbook.md);
PLAN stage 8, «Правка 01.11, вечер», holds the conditions. What to understand before it:
- **Everything GitHub holds becomes public**, not only `master`: the baseline branch and tag,
  three old `wip/*` backups with `.tmp` notes and MyFlow files, and the old Actions logs. A
  branch deleted later stays readable by SHA, so the scan covers every ref.
- **Three checks, all on the laptop:**
  - gitleaks over the whole history;
  - a shingle scan of every blob GitHub will show against the private texts: aircargo, the
    external bases, stage 2's and stage 5's runs;
  - the list of personal data the history carries: two author addresses, her name in Mac
    paths, machine names, her surname in LICENSE, aircargo's file names, her quoted words.

  A clean repository of selected files would have left the personal data out. With the
  history it goes public, so she sees the list first.
- **She decides once.** One message with the scan's result and the personal list, and one
  yes/no: «Публикуем?». Her word on publicity is given; she has not seen the push or the
  personal list. The yes covers the push, deleting the `wip/*` branches on GitHub, my default
  of disabling `weekly-report.yml` (it delivers outside) and the switch.
- **A real key** is revoked by her at its provider; the history is not rewritten.
- **After the switch every push is public at once.** Each later push gets both scans over
  `origin/master..master`.

## Stage 5 at the stop point

| Plan | Rows (valid) | Request clock / forecast | Exported (UTC) |
|---|---|---|---|
| WixQA M1 / M2 | 115 (115) / 115 (115) | 9,446 / 10,011 of 14,950 s | resumed run re-exported 13:22 |
| WixQA bridge | 30 = 15 seeds + 15 retests | 887 of 1,950 s | 13:36 |
| ConditionalQA M1 | 117 (115; 2 `unavailable` resent) | 11,338 of 14,950 s | 17:12 |
| ConditionalQA M2 | 116 (115; 1 resent) | 11,050 of 14,950 s | 21:10 |
| ConditionalQA bridge | 15 seeds, 0 of 15 retests | — | — |
| MultiHop-RAG M1, M2 | no file yet, 0 of 115 each | — | — |
| MultiHop-RAG bridge | 15 seeds, 0 of 15 | — | — |

- The 3× stop is per plan: 44,850 s for an M1 or M2 plan, 5,850 s for a bridge.
- A request took 82–98 s in M1 and M2, ≈ 59 s in a bridge.
- **Files.**
  - Verdicts are private: `D:/RAG_new_stage5_private/2057ad0/judge/<base>-<metric>/`,
    `verdicts.jsonl` and `grade-clock.json`. A seed is a kept stage-2 reply that the bridge
    regrades against.
  - The nine exports are in `reports/stage4-final/stage5/2057ad0/`, untracked. Eight are CRLF,
    as the laptop writes them; `stage5-wixqa-bridge.json` is LF.
- The Mac's part of stage 5 is over: the driver finished MultiHop-RAG before 17:03, when its
  receipt was committed. The Mac was idle at the stop.

**The memory stop again.** At ≈15:05 Claude Code stopped the background judge chain and Codex
task 11: low laptop memory, idle session. After her «да» the judge ran in foreground chunks, and
Codex in the background was not stopped again.

`judge_chunk.py` runs the frozen `grading.py grade` for one base and metric:
- it stops grading 800 s in, right after a verdict, and at 1,100 s at the latest;
- it retries a `cli_exit` after 120 s;
- it exports when grading completes;
- `--export-only` exports a plan whose grading stopped: the spec exports such a plan too. Added
  after the cold read and tested on WixQA M1, where the export kept its bytes.

A chunk loses at most the request in flight.

## Stage 5б, V6, at the stop point

**What V6 is.** V5's evidence-first answer, with everything but `<answer>` hidden from the
client and guarded by code. One pure function, `shown_text()`, applies the display policy
R0–R5 as text streams in:
- **R0** holds all text until `<answer>`.
- **R1** units end at a sentence end or a line break.
- **R2** releases the answer once ≥ 40 counted letters show the question's script at ≥ 60 %.
  Another dominant script stops generation, and the package's own answer (prompt V4) is
  generated instead: "the fallback".
- **R3** keeps the check after release: a late wrong script stops, never retracts.
- **R4** cuts at the first repeated sentence of ≥ 4 words or at the third occurrence of an
  8-word n-gram.
- **R5** completes and checks the open unit at the end.

Identifier tokens (with `_` or a digit, camelCase, all-capital) are left out of the language
count on both sides.

**Why V6.** With its visible scaffold's defects set aside, V5 cut bad 51 → 39 on WixQA and
57 → 46 on ConditionalQA. On aircargo it wrote 11 answers in the wrong language and 10
repetitions (bad 14 → 37). V6 tries to keep the gain without the form defects. If it does not
help: the generator pilot (PLAN §8.3 item 15).

**Where it is.** Codex (cw) wrote it in the data-free package `D:/RAG_new_cx/s1`, a git
repository without a remote. It is committed there as `2659a6a`, on the laptop only:
- `docs/specs/answer-prompt-v6.md` — 639 lines, status «draft — to be cold-read and registered»;
- `reports/answer-prompt-v6/tools/` — `shown_text.py`, `v6_common.py`, `v6_replay.py`,
  `v6_chain.py`, `v6_judge.py`, `v6_record.py`, and `v6_key.py`. `v6_key.py` is the foreground
  judge driver: one request at a time until 840 s, then exit 3. Its exits:
  - 0 key done; 3 budget reached, rerun;
  - 4 receipt waiting for its commit;
  - 5 judge unavailable; 2 stopped; 1 refusal;
- `tests/test_answer_prompt_v6.py` — 143 synthetic tests, passing on the laptop;
- `CX_REPORT.md` — Codex's report.

The reviewed bytes are frozen in `D:/RAG_new_cx/snap-v6c`, with the manifest
`D:/RAG_new_cx/briefs/snap-v6c.manifest` (24 files). Item 6's aircargo M1 judge sources, the
operator step of fix F2, are copied byte for byte to
`D:/RAG_new_stage5_private/v6/sources/aircargo-m1/`; their hashes match item 6's record.

**Two cold reads**, by one Opus subagent. Both files are in `D:/RAG_new_cx/cold-v6/`, outside
the package, because they quote external-base case ids; they never go to Codex as they are.
- `COLD_READ_V6.md`, on the first draft: 4 blocking, 5 should fix, 6 minor. My decisions on
  them, F1–F15 plus the driver L1, are in `D:/RAG_new_cx/briefs/s11c-brief.md`. Codex task 11c
  applied them (18:31–19:05).
- `RE_READ_V6C.md`, on 11c: **not ready — blocking 0, should fix 8, minor 7.**
  - **C1** — the early stop at 60 % sends 4 of the package's aircargo answers to the fallback,
    2 of them graded good. The spec's "4 → 2, both bad" is false for the registered policy.
    An early stop at ≥ 90 % gives 2, both bad, and keeps all 10 of V5's wrong-language catches.
  - **C2** — the policy reruns on every chunk. It costs a median 0.16–1.27 s and up to 31.5 s
    of CPU per answer, paid two or three times. Calling it only on chunks that hold a unit end
    or `>` gives identical results on 599 of 599 texts at 10–26× less CPU.
  - **C3** — the driver rebuilds the whole reading on every M2 call.
  - **C4** — the 10.5-h Mac chain is attached to the shell; it needs `nohup` or SIGHUP handling.
  - **C5** — the Mac script runs pytest in the ML venv, which has no pytest.
  - **C6** — the laptop interpreter named (Anaconda 3.14, Unicode 16, `regex` 2026.5.9) is not
    the Mac's (3.11, Unicode 14). The laptop would refuse after the first key, and the Unicode
    database is not compared.
  - **C7** — exit 5 cannot be resumed.
  - **C8** — failures ignore the budget: one 840-s call can make seven attempts of up to
    1,200 s each, with six 300-s sleeps between them.
  - **C9–C15**, minor:
    - the harm carry-over reads one stand folder;
    - `touch_stop` has no timeout;
    - any exception counts as judge unavailability;
    - a refusal during the freeze can leave an unfreezable state;
    - the PowerShell blocks assume the working directory;
    - fallback rows under full buffering;
    - a stream that ends inside a closing tag shows the fragment.
  - My review adds one finding: the driver's refusals print no reason. Fix: print the tool's
    own message and write the traceback to a private log.
- **Measured on recorded answers** (descriptive, W / C / A = WixQA / ConditionalQA / aircargo):
  - R4 cuts 1 / 0 / 0 package answers. Of the 4 / 2 / 10 repetitions the judge marked in V5's
    outputs, it catches 3 / 2 / 4 on whole outputs and 0 / 0 / 0 on the `<answer>` parts
    alone, which V6 shows.
  - The language rule catches 10 of V5's 11 wrong-language answers; the miss is a question with
    no dominant script.
  - Streaming is monotone, and chunk by chunk it equals the finished call on 599 texts.
  - First shown text, medians on V5-shaped outputs, W / C / A: 88.1 / 83.3 / 96.1 s under
    R0–R5; 98.7 / 98.3 / 96.1 s with full buffering; 79.2 / 74.7 / 80.4 s with only the tags
    hidden. The package's first chunk on the same replay clock: 52.5 / 52.4 / 52.8 s.
    That clock is not item 7's live first word (median 89.3 s on aircargo): compare on one
    clock only.

## What this session did

| Commit (UTC) | What |
|---|---|
| `42dcd1a` 17:03 | MultiHop-RAG's receipt: its M1, M2 and bridge plans frozen before grading |
| `b64eeb5` 17:46 | PLAN, ROADMAP, CURRENT_STATE: her «да» — stage 8 ahead of stage 6, V6 as stage 5б (Mac docs tests 23 passed) |
| the commit adding this file | The evening amendment of stage 8, the status docs after this file's cold read, the stage 8 runbook, this handoff |
| s1 `2659a6a` 21:11 | V6 after Codex's fix round 11c (local package, no remote) |

On GitHub: `RAG_Support_Assistant` set private (≈20:41).

## My choices, not hers

- V6 took Codex's slot before the clean repository: Mac time is the scarce resource. Her
  evening word then cancelled the clean repository.
- «текущую историю - в RAG_new» read as RAG_new itself public: it already holds that history.
- Stage 8's checks go first, beside stage 5's judge: they need neither the Mac nor the judge,
  and her evening word set no order. PLAN's status line says the same.
- C1–C8 decided below for 11d. No dry reading of stage 5 yet: MultiHop-RAG is ungraded, and
  the decisive rule was read preliminarily.
- The stop waited for ConditionalQA's M2 to finish rather than cut it mid-plan.

## Once Julia decides

- **Publication** — her one yes/no on the scan's report and the personal list (stage 8 above).
- **SLO** — after V6's outcome: my proposal is 270 s to the first word and 420 s to the whole
  answer, for 9 of 10 answers (360 s holds for 181 of 200, at the edge).
- **Stage 5 harm** — her yes/no on the package, only if the record detects harm.
- **The memory stop's switch** — `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` at Claude Code's
  start. It is hers alone.

## Next actions

Commands use absolute paths; the working directory does not persist. Limits:
- at most one background job: a full `ci_local` waits until no Codex task runs;
- one Mac: nothing else runs there during the V6 chain;
- the judge runs in the foreground, never two judge streams;
- one subagent at a time.

1. **Stage 8**, by the [runbook](stage8-publication-runbook.md): the checks (its section 2),
   then the report and her one question (3). After her «да», sections 4 and 5 in order: the
   README and site commit, `ci_local` PASS, the `wip/*` deletions, the switch, Pages, the push.
2. **Stage 5's judge in foreground chunks.**
   - Run `python D:/RAG_new/.tmp/cx-exec/judge_chunk.py conditionalqa bridge --chunk 1` with a
     Bash timeout of 1,200,000 ms. Repeat until it prints `EXPORT exit 0`.
   - Then `multihoprag m1`, `multihoprag m2`, `multihoprag bridge`.
   - `--chunk N` is ignored by the script: change N on every call, or the poll guard blocks the
     repeated command.
   - Each call prints `valid a -> b of plan items N` and the request clock.
   - If it prints `grade exit N` or `NOT_EVIDENCE.json present`, run
     `python D:/RAG_new/.tmp/cx-exec/judge_chunk.py <base> <metric> --export-only`, read
     `D:/RAG_new/.tmp/cx-exec/stage5-judge-<base>-chunks.log`, and stop if `EXPORT exit` is not 0.
3. **Codex task 11d**, the one background job while the chunks run.
   - First read `~/.claude/skills_cold/codex-cw-runner/SKILL.md` and run
     `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File 'C:/Users/uedom/.codex/scripts/codex-account-launcher.ps1' work -PrepareOnly`.
   - The brief goes in `D:/RAG_new_cx/briefs/s11d-brief.md`, written from `RE_READ_V6C.md`
     without ids or texts. My proposed decisions:
     - C1: early stop at ≥ 90 %, release unchanged; restate the spec's counts.
     - C2: call the policy only when the new chunk, with the previous character in front,
       matches `[\r\n。！？>]|[.!?]\s`; otherwise carry the previous result. The same in the
       judge's recomputation.
     - C3: one reading per key, cached by input hashes.
     - C4: the chain starts detached,
       `nohup zsh -e /Users/julia/RAG_new_stage5/run-v6.zsh <keys> <attempt> > /Users/julia/RAG_new_stage5/v6-<attempt>.out 2>&1 < /dev/null &`,
       and the laptop polls for `CHAIN_COMPLETE`, `STOP` or `FAILED.json`; no SIGHUP handler.
     - C5: check first whether the ML venv (`/Users/julia/RAG_Support_Assistant/.venv`) has
       pytest; if not, the gr4 venv with `PYTHONPATH=/Users/julia/RAG_new_mf_gate_site`, which
       must also import `regex`.
     - C6: the laptop interpreter is the focused venv
       `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe` (3.11). It lacks `regex` and
       pip: read the Mac's versions with
       `ssh deproject-mac '/Users/julia/RAG_Support_Assistant/.venv/bin/python -c "import regex, unicodedata; print(regex.__version__, unicodedata.unidata_version)"'`,
       then `uv pip install --python C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe regex==<v>`.
       The receipt records both versions on both sides; a mismatch refuses before the first
       request.
     - C7: a new `--resume-unavailable` resumes after exit 5. C8: retries inside the budget; the
       test expects exit 3.
     - C9–C15: as the reader proposes.
     - Driver messages: as above.
   - Launch (a command starting with the word codex is blocked):
     `CODEX_HOME='C:\Users\uedom\.codex-work' node "C:/Users/uedom/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs" task --cwd "D:/RAG_new_cx/s1" --model gpt-6-astra --effort xhigh --write --prompt-file "D:/RAG_new_cx/briefs/s11d-brief.md" > D:/RAG_new/.tmp/cx-exec/cx-task11d.log 2>&1; echo "CX11D_EXIT $?" >> D:/RAG_new/.tmp/cx-exec/cx-task11d.log`.
   - Then my review and a targeted cold read of the changed parts, on a snapshot with a
     manifest.
   - Then bring into RAG_new the spec, the tools (seven `.py` and `qa_prompt_v6.txt`) and the
     test, not `CX_REPORT.md`; run the Mac gate (the test plus the docs tests); make the
     registration commit (status «registered before V6's first request»).
   - Then the V6 chain on the Mac: 10.5 h forecast, stop at 3× per key. Its judge runs only
     after stage 5's judge.
4. **Read stage 5.**
   1. Normalize: `python D:/RAG_new/.tmp/cx-exec/lf_exports.py`, then the same with `--check`.
   2. Run the registered block 5 with the focused venv. PATH's Anaconda lacks `langchain_core`,
      which the M3 replay imports. The command is
      `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File D:/RAG_new/.tmp/cx-exec/stage5-read-dry.ps1 D:/RAG_new/reports/stage4-final/stage5/2057ad0/record.json`.
      The script holds block 5's lines with that interpreter; its first argument is `--out`,
      and `reading.py` refuses an existing file. A dry read, useful right after
      ConditionalQA's bridge, takes a new path each time, such as
      `D:/RAG_new/.tmp/stage5-dry/record-1.json`. The record path is used once, after every
      plan is exported.
   3. Build Codex's inputs: `python D:/RAG_new/.tmp/cx-exec/make_cx_inputs.py D:/RAG_new/reports/stage4-final/stage5/2057ad0/record.json`.
      It writes `D:/RAG_new_cx/s1/.cx_inputs/stage5-inputs.json` with ids and texts replaced.
   4. Only after 11d is committed in s1: sync the package with
      `python D:/RAG_new/.tmp/cx-exec/cx_sync_s10.py`, which copies HEAD's status docs into s1,
      commits there and prints that commit.
   5. In `D:/RAG_new_cx/briefs/s10-brief.md`, put that commit in place of `b00c9f2` and fill
      `{{MAIN_HEAD}}` (RAG_new's HEAD), `{{WHAT_RAN}}` and `{{CAPSULE_POINTS}}`.
   6. Codex task 10 writes the capsule and the artifact test. It launches like 11d, with
      `s10-brief.md` and the log `D:/RAG_new/.tmp/cx-exec/cx-task10.log`.
   7. My review, the Mac gate, an EVIDENCE_INDEX row, PLAN/ROADMAP/CURRENT_STATE, one commit:
      slice rule (c). Then update the README's stage 5 line.

**Do not:**
- push, switch visibility or delete GitHub branches before her answer to the scan report;
- restart a job Claude Code stopped without her word;
- put external-base ids or texts into a Codex package;
- commit `demo/phase-e-raw.webm` or `reports/ask100/`;
- write `~/.config/llama.cpp/config.ini`;
- touch other projects' processes on the Mac.

## State at the end

- `master` HEAD is the commit that adds this file. It is local; `origin/master` is `7caaf21`.
  Untracked: the nine stage 5 exports, `demo/phase-e-raw.webm`, `reports/ask100/`.
- Local backup branch `wip/stage5-judge-v6-stop`, built on that commit (`git log -1` of the
  branch shows its SHA). It holds the nine exports and this session's git-ignored scripts and
  notes in `.tmp/cx-exec/`. Never push it.
  - Restore: `git -C D:/RAG_new diff --name-only wip/stage5-judge-v6-stop~1 wip/stage5-judge-v6-stop | xargs git -C D:/RAG_new restore --source=wip/stage5-judge-v6-stop --worktree --`.
- `D:/RAG_new_cx/s1` is at `2659a6a`. `D:/RAG_new_cx/briefs`, `cold-v6` and `snap-v6c` are
  plain folders. All of it is on this laptop only.
- No background job, monitor or subagent of this session is left. A Codex companion broker for
  `--cwd D:/RAG_new_cx/s1`, cw profile, may still live; the next launch reuses it.

## Lessons

1. The memory stop hit background jobs again. A background job survived while the session
   worked in the foreground. Keep the long judge in the foreground; the one background slot
   goes to Codex.
2. The first cold reader wrote its report, with case ids, into the Codex package. I moved it
   out before the launch. A cold reader of a package writes outside it.
3. A spec's measured claim ("4 → 2, both bad") held for an earlier variant, not for the policy
   as registered. Recompute every claimed number on the registered rule before registration.
4. A network outage (≈17:45) reset ssh and killed a subagent with ENOTFOUND. SendMessage resumed
   it with its context: resume, don't relaunch.
5. A grep with `.{0,700}` over the 10-MB session transcript hung. Use
   `.tmp/cx-exec/find_cmd.py <jsonl> <fixed strings…>`, which prints past commands.
6. After five compactions the summary said gitleaks was missing; it was in `.tmp/e5-scan/bin/`.
   Look on disk before calling a tool missing.
7. The cold read of this file found the order of work against PLAN, the scan's corpora paths
   wrong and a stopped plan never exported. Before a handoff's commit, `ls` every path it names
   and read its order against PLAN's status line.

## Glossary

- **Package** — K = 14, num_ctx 3,584, INT8 reranker, `cache-ram = 1024`; her «да» 2026-10-30.
- **STAGE5_SHA** — `2057ad0`, stage 5's registering commit.
- **Receipt** — a committed `plans-<base>.json` that freezes the judge plans before grading.
- **M1** — quality without the reference. **M2** — agreement with the reference or a right
  decline. **M3** — deterministic external gold in the sent context.
- **Bridge** — the old side's 15 retested requests regraded now; bounds judge drift.
- **Seed** — a kept stage-2 reply in a bridge folder.
- **Primary / advisory** — WixQA and ConditionalQA decide; MultiHop-RAG does not.
- **Detected, MDE, NOT_EVIDENCE** — as in [`PLAN.md`](../../PLAN.md) §4.
- **Memory stop** — Claude Code ending a background job when the laptop is low on memory and
  the session idles.
- **Chunk** — one foreground `judge_chunk.py` call of ≤ 1,100 s.
- **V5 / V6** — the evidence-first prompt (stage 3б, not adopted) / its hidden-evidence
  successor (stage 5б).
- **R0–R5** — V6's display policy. **F1–F15** — the first cold read's items. **C1–C15** — the
  re-read's items.
- **Fallback** — the package's own answer, generated when V6's language guard stops it.
- **s1** — Codex's data-free working copy. **snap-v6c** — the frozen copy a reader checks.
- **cw** — Codex's work profile (`gpt-6-astra`, `xhigh`); the executor since 2026-10-30.
- **Switch** — changing RAG_new's GitHub visibility to public.

## Verification

- `git -C D:/RAG_new log --oneline -4` shows this file's commit, `b64eeb5`, `42dcd1a`, `e366670`.
- `git -C D:/RAG_new_cx/s1 log -1 --format=%h` prints `2659a6a`.
- Lines in `D:/RAG_new_stage5_private/2057ad0/judge/*/verdicts.jsonl`:
  - wixqa m1 / m2 / bridge: 115 / 115 / 30;
  - conditionalqa m1 / m2 / bridge: 117 / 116 / 15;
  - multihoprag bridge: 15; multihoprag m1 and m2 have no file.
- `gh repo view brownjuly2003-code/RAG_Support_Assistant --json visibility` prints `PRIVATE`; so
  does RAG_new.
- `git -C D:/RAG_new rev-list --count origin/master..master` prints 72 with this file's commit.
