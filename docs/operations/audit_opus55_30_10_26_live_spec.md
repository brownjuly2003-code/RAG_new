# Cold read: stage 4, item 5a, the short live series — spec, tools and test before registration

Frozen copy read: `D:/RAG_new/.tmp/coldread-live/`, matching its `MANIFEST.sha256`:

- `stage4-step5a-live.md` `b9ed090811ab9826adc6de867ecf28777049994dfb6c366f7453200c3b7cb9d7`
- `live5a_reader.py` `53f8913f62f5ab6d8356ee946dbfbe1e21e6225a764a7cde42e76ea3f785b2d1`
- `live_supervisor.py` `e903a1498aa1d48fb7ef6a9ba8cd2e4bd94e866433420fb132a6ab7179bd8e59`
- `raise_stand.sh` `6489520719823bc94bbd6c71e6e24718933025c13bf10aef3fca6c6305a5c110`
- `test_stage4_step5a_live_tools.py` `b725185d27ac00963c8f7bce55ec0d6f876b54c1275ee2ea9373ab9fec7f7360`
- `_base_manager.at_81cd2ad.py` `9f55703ba06be0740bce40c068a37c4bd8304ca30ffa78649f354969f7c0c27a`

This was a static reading; nothing was run. `spec:N`, `reader:N`, `supervisor:N`, `stand:N`, `test:N` and `base:N` are line numbers in the frozen copy (`base` is `_base_manager.at_81cd2ad.py`). Other files are cited as path:line in the live tree; `api/app.py`, `vectordb/manager.py` and `config/settings.py` were read at `81cd2ad` with `git show`. `reports/ask100/chat-pilot-20261013/stream-raw/stages.jsonl` ("the chat pilot") is an untracked run of older code (`7cad79f`), cited only for the shape of its rows.

Findings: 0 blocking, 3 should fix, 5 minor.

## Findings

### 1. Should fix: the reranker loads when the API starts, not in the warm-up's retriever build; the spec, two docstrings and the test's fixture describe a shape a real run never writes

- **Where:** spec:65–66, spec:96–97, spec:217, spec:271–272; reader:423–424; test:7–8, test:265–269, test:293–311, test:372–375, test:399, test:404.
- **What:**
  - The API's lifespan calls `initialize_vector_store()` synchronously (api/app.py:1718). `CHROMA` reaches the API as `VECTORDB_CHROMA_DIR` (supervisor:224–225), so the check at api/app.py:1379 sees the run's non-empty copy and builds tenant `default`'s retriever (api/app.py:1424–1425). That build calls `get_reranker()` whatever `chunks` is (base:2004–2006), which loads the model and caches it (base:409–417, base:427–430).
  - live_api patches `get_reranker` before uvicorn imports the app (reports/stage2/tools/live_api.py:259–266, 278–280). The call is therefore written to `stages.jsonl` before `/api/health/live` answers: before the supervisor's preload and its runner (supervisor:321–354), before any question.
  - The first question (tenant `aircargo`) misses the retriever cache and builds again. Its `get_reranker` returns the cached object at once (base:396–398). Later questions hit `_retriever_cache` (vectordb/manager.py:972–974) and call nothing.
  - A real run thus writes two `get_reranker` rows: the load at the API's start, and a ≈ 0-s call inside the warm-up's build. The chat pilot has exactly this shape:
    - a startup row with no trace id, 2.63 s (its lines 10–11);
    - then 0.0003 s inside the first question's build (its lines 18–19).
  - Step 1's record agrees (reports/stage4-step1/4f48fed/step1.json). Its first-question builds took 4.04 and 1.969 s, its later ones 0.001 s. Item 5a's PyTorch loads were 10.8–27.8 s, so no load fits in those builds.
  - The reader's values are still right:
    - `read_rows` collects every row in order (reader:158–190).
    - `reranker_load_sec` takes the first row, the startup load (reader:474–476).
    - `assign` drops the startup spans, which start before the first case.
    - Gate (vii) passes on two rows (reader:269–271).
  - The text is wrong:
    - spec:65–66 says the reranker loads "in the first question's retriever build", and spec:96–97 "inside the warm-up's retriever build".
    - spec:217 counts "its load" in the first question.
    - spec:271–272 says "its load sits in the warm-up".
    - reader:423–424 calls the warm-up's build "the reranker's load". In a real run that build will read ≈ 2–4 s.
  - The test fixture adds a `get_reranker` row inside every build: 12.5 s, then 0.001 s five times (test:293–311). It asserts six rows (test:372–375) and a load of 12.5 s (test:399). That 12.5-s call sits inside a warm-up build the test reads as 0.08 s (test:404). No fixture has a row before the first case.
- **Why it matters:**
  - A later reader would take the warm-up's build seconds for the load. They would also believe the load ran beside the resident model, when it runs before the preload with no model resident.
  - The two runtimes differ at that point too: item 5a read INT8's process at 1,426 MiB after its load against PyTorch's 549 MiB (spec:22–23). In INT8 runs that memory is already held when Ollama preloads the model. That is the runtime's own property, which the series measures, but the spec should say where it falls.
  - The cold first call still falls in the warm-up's rerank, so the warm-up design stands.
  - The test pins a shape real runs do not have. If the startup row went missing, `loads[0]` would be the ≈ 0-s call and would be printed as the load, and no test would notice.
- **Suggested change:**
  - Correct spec:65–66, 96–97, 217 and 271–272: the load happens in the API's start, before the preload, and is printed rather than paired; the warm-up pays the first call in its rerank.
  - Fix the docstrings at reader:423–424, test:7–8 and test:265–269.
  - Make the fixture write one startup row before the first case and one ≈ 0-s row in the first build only, and assert two rows.
  - Optionally, record each row's start relative to the first case's start, and have gate (vii) require the first row before the first case.

### 2. Should fix: "no detected difference" is read as "INT8 does not reach the chat, the package goes without it"; ten pairs give the test little power, and the noise argument counts only PyTorch's side

- **Where:** spec:76–81, spec:117–120, spec:125–128, spec:147–151; reader:392–403.
- **What:**
  - At ten readable pairs, "faster" needs 9 of 10 or better: 9/1 gives p = 0.0215, and 8/2 gives 0.109.
  - Let q be the chance that INT8 is below in a single pair. The chance of reading "faster" is then:
    - 0.914 at q = 0.95;
    - 0.736 at q = 0.9;
    - 0.544 at q = 0.85;
    - 0.376 at q = 0.8.
    A power of 0.8 needs q ≈ 0.92.
  - spec:78–80 argues that the ≈ 43-s saving "stands well clear of a pair's noise", since step 1's arm-A reranks ran 91.1–377.9 s, "so a pair flips only where PyTorch's ask runs far below its own median". A pair also flips when INT8's ask runs far above its own median. The spec expects INT8 to share the contention: "its peak is no lower, so the memory the chat contends for stays" (spec:148–150).
  - In step 1 (reports/stage4-step1/4f48fed/step1.json), three of these questions reranked in 33.5–41.3 s without the resident model (arm B: leave-compensation, leave-sources, leave-risk). Their pools hold 37–39 candidates in item 5a's rows (reports/stage4-step5a/d9f9fd8/rows.jsonl).
  - With the model resident (arm A), the same three took 155.6, 115.0 and 377.9 s; leave-sources and leave-risk both have 39-candidate pools. Most of arm A's 4.15× spread is therefore the contention, not the question.
  - For illustration, draw each side's factor independently from step 1's four arm-A reranks over their median (0.67, 0.85, 1.15, 2.79). At item 5a's ratio of 1.751, that flips 3 of the 16 combinations: q ≈ 0.81, power ≈ 0.4.
  - spec:125–128 nevertheless reads "No detected difference" as "it does not, and the package goes without INT8".
- **Why it matters:**
  - The series has a fair chance of reading "no detected difference" even when INT8 saves the 35–65 s the spec forecasts (spec:148).
  - The spec would then turn absence of evidence into the package decision. That decision is hers (spec:27–28), and it would rest on a reading that cannot carry it.
- **Suggested change:**
  - Read "no detected difference" as "not shown at ten pairs", with the median ratio and saving beside it (reader:404–405 already computes both).
  - Correct spec:78–80 so it names both sides' noise, and register the power line above.
  - If the budget allows, use ten paired questions a run: the next five of aircargo's registered order, which item 5a also scored. Twenty pairs read "faster" at 15 of 20 (p = 0.041), with power 0.989 / 0.933 / 0.804 at q = 0.9 / 0.85 / 0.8. That costs ≈ 30 more minutes a run, ≈ 2 h for the series.

### 3. Should fix: a disturbance during one run moves its block's five pairs together, and nothing detects, prints or rules on it

- **Where:** spec:173–176, spec:273–274; reader:307–321, reader:352–380, reader:383–389; reports/stage4-step0/tools/step0_sampler.py:44, 160.
- **What:**
  - The idle check runs only before a run (spec:173–176). Nothing looks during a run of ≈ 36–43 min (spec:219).
  - The sampler records `vm.loadavg` every 5 s (step0_sampler.py:44, 160), but neither reader uses it: `reports/stage4-step1/tools/step1_reader.py` has no `loadavg`, and `printed_of` has no load (reader:352–380).
  - A block's five pairs take their asks from the same two runs (reader:307–321). A foreign job during part of one run pushes several of that block's pairs the same way. The sign test (reader:383–389) counts them as five independent signs.
  - Item 5a had a rule for exactly this case (docs/specs/stage4-step5a-int8-reranker.md:125–127): a question is disturbed when, at its end, a process matching the idle pattern ran, Ollama held a model, or other processes took more than one core. This spec does not carry it over.
  - The Mac is shared, and such slowdowns are on record:
    - retrieval took 2.7× while other projects' tests ran (docs/evidence/answer-prompt-v4-record.md:133–134);
    - two other projects' pytest suites ran beside a series on 2026-10-29 (docs/operations/session-handoff-2026-10-29-stage4-step2-running.md:107).
  - spec:273–274 names the risk ("not a jump") but gives no way to see one.
- **Why it matters:**
  - One disturbed INT8 run can turn 10/0 into 5/5, which the spec reads as "no detected difference", and by finding 2 as "the package goes without INT8".
  - A disturbed PyTorch run errs the other way.
  - Either way, the record keeps no trace of why.
- **Suggested change:**
  - After each `LIVE_DONE`, before step 7's read, repeat step 3's checks and append their result to a file in the record. By then the supervisor has unloaded the model, so `[l]lama-server` should no longer match.
  - Have the reader print, deciding nothing:
    - each ask's maximum 1-minute load inside its rerank and inside its whole span, from the samples already taken;
    - each block's below/above counts.
  - Pre-register that a run with a foreign job, seen at its end or as a foreign `llama-server` pid in its samples (reader:274 already counts pids), is run again as `-r2`.

### 4. Minor: a sampler that refuses to start does not stop the run, and step 1 clears only `$T/*.py`

- **Where:** spec:164, spec:177, spec:185, spec:187–192; reports/stage4-step0/tools/step0_sampler.py:209–212; reader:489–491; stand:15.
- **What:**
  - The sampler refuses an existing samples file or stop file and exits 2 at once (step0_sampler.py:209–212). Step 5 starts the supervisor 6 s later regardless (spec:185).
  - Step 1 removes `$T/*.py` and asks that "`$T/runs` holds no run", with no command that checks it (spec:164). It says nothing of `*.samples.jsonl`, `*.stop`, `*.live5a.json` or `environment.jsonl`.
  - The stand already exists, with earlier copies of the drivers in `$T`; raise_stand.sh made `$T/runs` (stand:15).
  - A leftover samples file therefore gives a run with no samples:
    - In runs 1 and 2, step 6's read catches it during the second question, since arm A cannot be held without samples.
    - In runs 3 and 4 nothing reads early, so the loss shows only at step 7's gate (vi), after a whole run of ≈ 36–43 min. The `-r2` run then costs as much again.
  - A leftover `$T/$L.live5a.json` makes step 7's read refuse (reader:489–491).
  - The `>>` at spec:177 appends to an old `environment.jsonl`, whose first line would then not be this series' line before run 1.
- **Suggested change:**
  - In step 1, require `ls -A $T` to show only the six tools and an empty `runs`.
  - In step 5, start the supervisor only once the sampler has written: `… & sleep 6; test -s $T/$L.samples.jsonl && LIVE_VARIANTS=… nohup …`.

### 5. Minor: INT8's forecast warm-up and first question sit below its own later questions, and the first-question forecasts count a load that falls before the question

- **Where:** spec:147–155, spec:216–220.
- **What:**
  - spec:148 puts PyTorch's chat rerank at ≈ 100–135 s with a ratio of ≈ 1.5–2. That places INT8's later reranks at ≈ 50–90 s.
  - spec:155 forecasts INT8's warm-up rerank at ≈ 20–50 s, below its later reranks. Yet that rerank runs beside the same resident model (the preload precedes the runner, supervisor:341–354) and also pays the first call.
  - spec:218–219 likewise has INT8's first question (≈ 300 s) below its later ones (≈ 350 s), while PyTorch's first (≈ 480 s) is above its later ones (≈ 400 s).
  - spec:217 counts "its load" in the first question. By finding 1 the load falls in the API's start, which spec:220 forecasts separately (≈ 1.3 min).
  - Step 1's first arm-A rerank, 91.1 s, was the lowest of its four. That may be the basis, but the spec does not say so.
- **Why it matters:**
  - The outcome is set against the forecast, and a forecast that contradicts itself leaves "as forecast" open.
  - The caps and stops are not at risk. The caps come from PyTorch's forecasts (spec:208–209), and INT8's ≈ 108-min stop (spec:211) has room.
- **Suggested change:**
  - State why INT8's warm-up should be faster than its later reranks, or raise its forecast to their range.
  - Move the load from the first question's forecast to the API's start.

### 6. Minor: several conditions the spec states are checked by no tool, gate or named step

- **Where:** spec:43–46, spec:53–56, spec:135–145, spec:200–204; reader:208, reader:256, reader:482–487, reader:496–502.
- **What:**
  - **The two `stand_env.py` lines.** spec:54–56 says both must name Ollama 0.33.2 and the same server start, "or the series is `NOT_EVIDENCE`". No tool reads `environment.jsonl`: the reader takes no such argument (reader:482–487), and step 8 names no manual check (spec:200–204).
  - **The model digest** `0edcdef34593…` (spec:45). The reader keeps it (reader:208), but gate (i) compares the name only (reader:256).
  - **The corpus hashes** (spec:43–44). `--corpus` records them (reader:496–502) but compares nothing.
  - **The snapshot** `953dc6f6…` (spec:46). Nothing records which snapshot the API's CrossEncoder or the ONNX tokenizer loaded.
- **Why it matters:** a later reader may take these as gated, as `code_sha` is (reader:252). A different digest, index or Ollama would pass silently.
- **Suggested change:**
  - Gate the digest and the three corpus hashes as constants, like `ONNX_SHA256` (reader:73).
  - Read the two environment lines in step 8 under a stated rule.
  - Or name these checks as manual in the spec, with the step that does them.

### 7. Minor: Running-it has details that break a literal copy or waste a step

- **Where:** spec:159–204; supervisor:17, supervisor:217, supervisor:288–289; stand:15; reader:515–516.
- **What:**
  - **"the six of the list below"** (spec:169). The list has nine entries, two of them named `live_supervisor.py`: step 1's `915ffa9e…` (spec:251) and this series' `e903a149…` (spec:254).
  - **Commands wrap mid-argument outside code blocks** (spec:165–168, 170–171, 193–195, 200–203). Pasted from the raw file:
    - spec:167 alone runs `cp -p …/stage2/tools/live_api.py …/stage4-step1/tools/live_runner.py`, which writes V4's API driver over the stand's copy of the runner.
    - spec:170–171 puts a newline and an indent into the `-c` string, which Python rejects (`IndentationError`).
    - spec:193–194 leaves `touch` without its file, so the sampler runs on into the next run.
    - Step 5 already puts each command on one line in a code block (spec:184–185).
  - **The laptop shell is not named** (spec:165–166). supervisor:17 holds a non-ASCII character, and Windows PowerShell 5.1 re-encodes a native pipe and adds CRs. The `shasum` check (spec:169) catches this, but only after the copy.
  - **The `diff` check is not a gate.** `diff -rq … && echo same` (spec:184) does not stop the next line, which starts the run anyway.
  - **`LIVE_VARIANTS=cpu` does nothing here** (spec:185). It comes from step 1's command (docs/specs/stage4-step1-rerank-memory.md:195), and only mode `retrieval` reads it (supervisor:288–289).
  - **No step checks the stand.**
    - There is no `cat $S/CODE_SHA`, the file the supervisor records (supervisor:217). A wrong stand shows only at gate (i), after a whole run: at the q1 read, the launch gate is false anyway, since the status is `running`.
    - raise_stand.sh refuses an existing stand (stand:15) and takes `81cd2ad`'s full SHA, not `<c>`. The spec does not say whether the stand is raised anew or reused.
  - **Step 6's conditions are not printed.** The reader prints only the gates and the readings (reader:515–516). "Read", "arm A held", "the five" and "the load without an error" must be looked up in the JSON.
- **Suggested change:**
  - Put every command on one line in a code block, and name the six files by path and SHA.
  - Name Git Bash for the laptop side.
  - Chain the run onto `diff` with `&&`, or say to go on only after `same`.
  - Drop `LIVE_VARIANTS=cpu`.
  - Add `cat $S/CODE_SHA` to step 1.
  - Give step 6 a one-line `python -c` that prints its four fields.

### 8. Minor: spec:100 reads the settings "beside step 1's four"; step 1's reader reads three

- **Where:** spec:99–101; reports/stage4-step1/tools/step1_reader.py:70; reader:82–87, reader:262.
- **What:** step 1's `SETTINGS` holds `retrieval_top_k`, `rerank_top_k` and `rag_device` (step1_reader.py:70). This reader adds `reranker_model` (reader:86) and gates all four (reader:262; spec:138–139).
- **Suggested change:** "beside step 1's three and the reranker's model".

## Checked and found consistent

- **The frozen copy.** It matches `MANIFEST.sha256`, each file is byte-identical to its live-tree file, and none holds a CR byte.
- **The reused tools.** They hash to spec:248–252 at `81cd2ad` and are unchanged to HEAD. The curated file is `3737d694…` there and in the working tree.
- **The supervisor copy.** It differs from step 1's only in the marked lines: supervisor:61–70, 95–96, 104 and 206–211.
  - Every assert precedes `out.mkdir` (supervisor:212–213).
  - `RAG_RERANKER_ONNX` passes the path rule (supervisor:191–192) and reaches the overrides (supervisor:214).
  - `PY` is item 5a's interpreter (supervisor:85; docs/specs/stage4-step5a-int8-reranker.md:38–39).
  - The API's `PYTHONPATH` is step 2's (supervisor:86, 272).
- **The test traces as passing:**
  - p = 0.001953 at 10/0;
  - ratio 2.0 and saving 50.0;
  - the warm-up's 258.25 and 0.08 s;
  - each refusal and the line that raises it;
  - the run-gate cases and the Mac-path checks;
  - the imports from step 1's test;
  - the curated ids at positions 5–10;
  - the manifest's `int8/model.onnx` entry;
  - every spec phrase it asserts.
- **Real shapes:**
  - The rerank's end row holds the five kept, observed inside the rerank (reports/stage2/tools/live_api.py:209–229, 267–270).
  - The pool's SHA-256 does not depend on scores. Step 1's two runs gave each question the same pool, so the pool rule should not cost pairs.
  - `reranker_runtime` and `reranker_onnx_path` come from the environment (config/settings.py:496–503). They sit unmasked in the `all` snapshot (live_api.py:128–142). The path is `""` for PyTorch, as `expected_settings` expects (reader:118–120).
  - `launch.json` goes `running` → `complete`/`failed`, so the ONNX file is hashed only after its run (reader:233–236).
  - The ONNX branch of `get_reranker` raises rather than falling back (base:393–394, 409–417), so a failed INT8 load reaches gate (vii).
- **Paths and labels:**
  - The drivers sit two levels above a run (reader:232).
  - `--corpus $IX` matches `CORPUS_FILES` (step1_reader.py:103).
  - The labels match `RUNS` and `BLOCKS`, and `-r2` keeps its run's place (reader:215, 303).
  - The `pkill` pattern matches the runner's path.
  - The copy holds `chroma.sqlite3` (supervisor:196).
  - `CASE` and `LIVE_DONE` are printed where steps 6 and 7 look (live_runner.py:250; supervisor:389).
  - `--max-sec 8000` outlasts the ≈ 130-min stop.
  - Step 6's read falls on both runs of block 1 alike.
- **Arithmetic:**
  - 100 − 100/1.751 = 42.9 s.
  - The caps are 3× 480 and 400 s.
  - The stops are 3× 43 and 36 min.
  - Four runs take ≈ 158 min.
- **Facts against their sources:**
  - **Item 5a** (reports/stage4-step5a/d9f9fd8/record.json, rows.jsonl; reports/stage4-step5a/onnx/manifest.json):
    - 141 → 144 of 250, 30 of 30, the ratio 1.751, 12.0 of 28.2 s;
    - first questions of 133.1 / 129.5 s and 14.7 / 13.2 s;
    - 571 and 2,271 MB, with the peak and after-load memory;
    - the fives' basis for the forecast;
    - ONNX Runtime 1.23.2 and the snapshot.
  - **Step 1** (step1.json):
    - arm-A reranks of 91.1–377.9 s and wholes of 326.7–715.8 s, median 383 s;
    - 0.2594;
    - the digest and the corpus hashes.
  - **Elsewhere:**
    - 102 of 320 s (CURRENT_STATE.md:48);
    - the PLAN quotes, §8.3 item 2 and §9 (PLAN.md:617–621, 882–893);
    - ONNX Runtime's default threads on this 4-core CPU equal item 5a's 4.

## Disposition, 2026-10-30

Each finding was checked against the sources it cites; none is refuted. Line numbers below are in the edited files, not in the frozen copy: `spec` is `docs/specs/stage4-step5a-live.md`, `reader` `reports/stage4-step5a-live/tools/live5a_reader.py`, `test` `tests/test_stage4_step5a_live_tools.py`. The supervisor's copy and `raise_stand.sh` are the frozen copy's bytes (`e903a149…`, `64895207…`).

- **1. applied:** spec:25–27 and 71–75 put the reranker's load in the API's start — the lifespan builds the default tenant's retriever before the health check, the preload and any question — printed per run, never paired; spec:76–80 has the warm-up pay the first call in its rerank; spec:123–125 reads every `get_reranker` call in order, with whether it ended before the first question; spec:306–311 counts the load in the API's start, not in the first question, and spec:360–363 says so under Not said. The reader's docstring (reader:15–17), its comment (reader:265–266) and `warm_up`'s docstring (reader:499–501) say the same. The optional change is taken: gate (vii) wants the first call ended before the first question (reader:268–271, 330–333; spec:177–179), so a run whose startup row went missing fails its gate instead of printing the warm-up's ≈ 0-s call as the load. The fixture writes the load at the API's start, 12.5 s, and the cached return, 0.001 s, in the warm-up's build only (test:7–9, 302–304, 342–346); test:447–451 asserts the two rows and where each ended, test:700–701 fails a first call inside a question, test:857 reads the load while the run goes on.
- **2. applied, and taken further:** the finding's figures hold — at ten pairs 9 of 10 reads faster (p 0.021), and the power is 0.736 / 0.544 / 0.376 at q = 0.9 / 0.85 / 0.8. «No detected difference» now reads «not shown in the chat at twenty pairs»: the package question names INT8 with its idle numbers and this series' medians as not shown, and the choice stays hers; only «slower» leaves INT8 out (spec:155–160). spec:100–103 names both sides' noise. The suggested ten paired questions a run were not taken, because the noise comes by run, not by question: in the 30-question record's two runs of one code the same question at the same position reranked at a ratio of 0.17–1.97 between the runs, in stretches of neighbouring positions (spec:89–95, from `reports/chat-live-4b/19beeb1/runs.json`), so more questions in a run add pairs that share its state. The runs are doubled instead: eight, ABBA twice, four blocks of five pairs, twenty in all (spec:83–88). A reading needs every block to lean its way besides p below 0.05, and at least sixteen readable pairs (spec:145–150; `compare`, reader:458–497, the blocks' counts at reader:488; `MIN_PAIRS`, reader:115). With the block rule the power at q = 0.9 / 0.85 / 0.8 is 0.961 / 0.871 / 0.718, against 0.989 / 0.933 / 0.804 for the sign test alone (spec:96–100), for ≈ 5 h 30 min of runs (spec:306) against ≈ 4 h 45 min for ten questions in four runs. Tests: test:502–531 (15 of 20 reads faster, 14 does not), test:532–559 (16 of 20 one way with a block leaning the other reads «no detected difference»), test:562–571 (a tie), test:600–618 (an unread ask leaves its block unread).
- **3. applied:** after each run step 7 appends step 3's look at the run's end to `after-runs.txt` — the load, the pattern's matches, Ollama's models and the CI lock — and a match, a model or a lock runs the run again as `-r2` (spec:275–284). Gate (viii), `llama`, wants one `llama-server` pid in the run's samples (reader:334–336; spec:179–180), so a reload or a second server beside the resident model runs it again too (spec:284–285; test:705). The reader prints each ask's highest 1-minute load inside its rerank and inside its question (`load_max`, reader:221–236, 283–288; printed at reader:443–444 and as medians at reader:616–617; spec:118–119, 161–166) and each block's counts below and above (reader:488). The block rule of finding 2 keeps one disturbed run from carrying a reading. Item 5a's per-question rule is not carried over: in the chat Ollama holds the model and its server runs throughout, which that rule reads as disturbed, and step 0's sampler, unchanged, names no other process (spec:107–109). spec:364–368 says what these checks miss. Tests: test:647–661 (a load inside a rerank is printed and decides nothing), test:705.
- **4. applied:** step 1 moves what an earlier smoke left in `$T` out of it and wants `ls -A $T $T/runs` to print the six tools and an empty `runs` (spec:209–227), so no old samples, stop, read or environment file stays; step 5 starts the supervisor only after `test -s $T/$L.samples.jsonl` prints `sampling` (spec:257–262).
- **5. applied:** the load is out of the first question's forecast and in the API's start (spec:306–311). INT8's warm-up forecast is raised to ≈ 35–70 s and stays below its later reranks' ≈ 50–90 s for a stated reason: INT8 pays no cold first call — item 5a's first INT8 questions, 14.7 and 13.2 s, sat below its median — and a run's first rerank is its least pressed: step 1's first arm-A rerank, 91.1 s, was the lowest of its four, and item 5a's ratio puts INT8 at ≈ 52 s there (spec:192–197). INT8's first question is forecast at ≈ 350 s, no more than its later ones (spec:307–309).
- **6. applied:** the digest is a constant, `MODEL_DIGEST` (reader:87), in gate (i) (reader:317; spec:168–169; test:679). The corpus files' SHA-256 are constants, `CORPUS_SHA256` (reader:89–93), and `read_environment` (reader:516–546) reads the `stand_env.py` lines for a stand gate (`stand_gate`, reader:547–569; spec:182–184): V4's three corpus files, and two or more lines, each naming Ollama 0.33.2 (`OLLAMA_VERSION`, reader:94) and one server, with the same pid, start and distributions in every line. A stand that fails makes every reading `NOT_EVIDENCE` (reader:570–578; spec:61–63), and step 8 passes `--corpus` and `--environment` (spec:291). Tests: test:454–455, test:729–775 (each way the stand fails). The snapshot is a named manual check: step 4 writes `hf.txt` before run 1 and after the last, and it must name `953dc6f6…` alone — before run 1 else nothing runs, after the last else `NOT_EVIDENCE` (spec:51–52, 241–249).
- **7. applied:** every command of Running it is one line in a code block, and a step goes on only on what the one before printed (spec:205–206); the laptop's lines run in Git Bash (spec:206–207), and its copies go by `git show <c>:… | ssh … "cat > …"` (spec:216–217). Step 1 prints `cat $S/CODE_SHA` first (spec:211–213) and names the six tools by path and origin against the list's SHA-256 (spec:221–227). The `diff` is chained with `&& echo same`, and the sampler starts after `same` (spec:255–257). `LIVE_VARIANTS=cpu` is gone (spec:264). The stand is raised once and reused, since `raise_stand.sh` refuses an existing one (spec:35–39). Step 6 prints its conditions with one `python -c` line (spec:269–274).
- **8. applied:** spec:121–123 reads «beside step 1's three and the reranker's model».
