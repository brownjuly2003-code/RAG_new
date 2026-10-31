# Cold read: stage 4 item 6 and item 7 drafts and tools, 2026-10-31

- Snapshot read: `D:/RAG_new_cx/s1` at commit `f356138b647b48a082c3792d85d6b621d1449ef8`. The working tree held only the untracked `CX_REPORT.md`.
- Under review: `docs/specs/stage4-item6-final-aircargo.md`, `docs/specs/stage4-item7-final-speed.md`, `reports/stage4-final/tools/*.py`, `tests/test_stage4_final_tools.py`, and `deploy/macos/start.py` plus `tests/test_macos_service_start.py` (diff against HEAD~1).
- Context read: the frozen tools they import (stage1 supervisor and runner, step 0 sampler, stage 2 live_api, answers_summary, stage2_common and judge_export, the answer and context judges, stage 7 arms_replay, item 5a reader, v4_record, step 4b window_timing).
- Published data compared: `D:/RAG_new/reports/answer-prompt-v4/4f48fed/`, `reports/stage2/5e308fe/` and `reports/chat-live-4b/19beeb1/`. Only keys, counts and ids were read.
- Method: read-only. No pytest, Mac, model or network was used. One local pure-math recomputation of `v4_record.newcombe` was run.

Severity counts: **blocking 2, should fix 5, minor 6**.

---

## F1 — blocking — the preload has no `num_ctx`, so question 1 reloads the model and item 7 is always NOT_EVIDENCE

- **Where:**
  - `reports/stage4-final/tools/run.py:247-248`: `sup.ollama("/api/generate", {"model": ..., "keep_alive": "30m"}, timeout=300)`, with no `options`.
  - `record.py:367-371`: `if len(pids) != 1: reasons.add("not one llama-server")`.
  - The item 7 spec at 22-23 says "Preload is timed separately" and at 45 defines "disturbed".
- **What is wrong:** The preload loads the runner at Ollama's default context, which is 4,096 here. The product calls with `num_ctx` 3,584 (`SETTINGS`, `llm/providers/ollama.py:125`). The repo's own comment at `ollama.py:225-226` says "another num_ctx reloads the model". So the first chat call of every API, which is question 1 of item 7 and of each item 6 batch, unloads the preloaded runner and starts a new `llama-server`.
  - The new runner starts only after retrieval and rerank, at least ~30 s into Q1.
  - Until then the old pid appears in the 5-second step 0 samples inside `[first t0, last end]`, so `memory()` sees two pids.
  - Item 7 is then marked disturbed and NOT_EVIDENCE every time, after ~1.7 h of Mac time. A rerun with a new OUT fails the same way.
- **Side effects:**
  - `ollama_load_sec` measures a load at the wrong window.
  - Q1's `first_token_sec` and `result_sec` (item 7, and the first question of each item 6 batch) include an unload and a reload. That contradicts "preload timed separately".
  - Earlier series (19beeb1; 5a at 4,096) did not hit this because their window equalled the default.
  - Step 4b avoided it by loading through the chat's own call at the block's window and reading `/api/ps` `context_length` (`reports/stage4-step4b/tools/window_timing.py:20-25, 414-428`).
- **Nothing catches it:** no test pins the preload payload.
- **Fix:**
  1. Preload with `"options": {"num_ctx": SETTINGS[...window...]}`.
  2. After the preload, require `/api/ps` to show one model with `context_length == 3584`, and record the `llama-server` pid in `launch.json`.
  3. Have `memory()` require that recorded pid to be the only pid.
  4. Add a test that fails when the preload payload lacks `num_ctx` 3,584.
  5. Cheap pre-flight before item 7: count distinct `llama-server` pids in item 6 b01's `samples.jsonl`. This also catches any other Ollama call path that omits `num_ctx`, for example the `LocalOllamaLLM(model_name=...)` fallback for suggestions at `api/routers/conversation.py:2694-2697`, which would reload on every question.

## F2 — blocking — M3 compares two instruments, and the old side is at ceiling: "M3 rises" is impossible and ~5 `none` verdicts publish "harm detected"

- **Where:**
  - `record.py:275-279`: old = p1 `context_has_answer`, new = context judge `full|partial`.
  - `record.py:159-166`: M3 falling counts as harm.
  - `judge.py:65-66`: the separate M3 context plan.
  - Item 6 spec at 18-23 and 151.
- **What is wrong:**
  - **The old side is at ceiling.** `p1-aircargo-judge.cases.jsonl` has `context_has_answer` True on 100 of 100, and V4's `v4-aircargo-judge` also has 100 of 100.
    - With every old value at 1, only discordant pairs of the "fall" kind are possible. "Rises" cannot occur.
    - Recomputing the frozen `newcombe` for n = 100 with b = k fall pairs gives an upper limit of +0.0043 at k = 4 and −0.0033 at k = 5.
    - The per-case cluster bootstrap excludes zero at the same k, since P(no fall pair in a resample) = 0.95^100 ≈ 0.006.
    - So **five `none` verdicts make `outcome()` print "harm detected"**.
  - **The instruments differ.** Stage 2 p2's aircargo context judge (a different prompt and salt from the answer judge) already gave `none` 1 of 115 and `partial` 6 on the V3 path. The new 2,176-token input limit can only send less.
  - The published headline would then be a harm that cannot be attributed to the package.
  - It also costs 115 extra judge requests (~4 laptop hours by the spec's pace).
- **Fix:**
  - Read M3 from the new **M1 plan's own** `context_has_answer` (`scripts/chat_answer_judge.py`, the same instrument as both p1 and V4), paired against V4 4f48fed's `context_has_answer`, not p1's. V4 is the M1 baseline and has the same retrieval.
  - Drop the separate context-judge plan for aircargo, which saves 115 requests.
  - State in the spec and the record that this M3 is one-sided at a ceiling of 100/100: it can show only a loss, and "gain" cannot come from M3.
  - If a graded M3 is still wanted, run the context judge on V4's private sent prompts as the paired old side, so both sides use one instrument.

## F3 — should fix — any foreign job at a batch boundary ends item 6; the item 7 spec says "wait", the code refuses

- **Where:** `run.py:151-153`. `require(not before["reasons"], "Mac is not idle; ...")` runs before every batch. `main()` at `run.py:321` allows no resume ("use a new OUT"). The item 7 spec at 36 says "If occupied, wait".
- **What is wrong:**
  - Item 6 is ~6.2 h on a shared Mac. One other project's `pytest`, one `limactl` or ci_local VM, or one Python process of 512 MiB or more seen at the start of any of batches 2–10 turns the whole base into NOT_EVIDENCE.
  - Item 6 spec 99-102 says "a new OUT ... all 100 again", so all 100 answers must be rerun, although an answer's quality does not depend on idleness.
  - Item 5a's live INT8 series already died this way (commit 18467bf).
  - `test_batch_refuses_before_starting_children` pins the refusal.
- **Fix:**
  - For item 6 batches 2–10 (and item 7's start), poll `idle_check` every ~60 s until clear, bounded by the series deadline.
  - Log each wait in `idle-before.json`. Count wait time outside question caps.
  - Step 4b's `IDLE_WAIT_SEC` is the precedent.
  - Keep refusal only for things that change the product path, such as a taken port, a resident other model, or a moved stand.

## F4 — should fix — 600-s question caps sit inside the measured tail: they kill a 6-hour quality run on one slow answer and censor item 7's p90

- **Where:** `record.py:50-52`, `runner.py:24`, `common.py` (`FIRST/REST` = 300/200), item 6 spec 85-94, item 7 spec 63-79.
- **What is wrong:** The forecast uses PLAN's 150–200 s estimate, but the same 100 questions measured slower.
  - V4 4f48fed: total median 296 s, p90 390 s, **max 581.6 s**, first of batch up to 559 s.
  - 19beeb1 r2: result median 319.6 s, p90 385 s, max 476 s.
  - INT8 saves roughly 70 s of rerank, which leaves the tail near the 600-s cap. On this shared Mac a single contended answer above 600 s makes the item 6 base NOT_EVIDENCE.
  - The cap applies to `total_sec`, which now includes the suggestions LLM call after the result (`conversation.py:2830-2852`). The forecast's 200 s does not include it.
  - For item 7 the cap is a selection rule: only series whose every question beats 600 s yield a p90 and an SLO proposal. The proposal is then conditional on "max < 600 s", and the spec does not say so.
- **Fix:**
  - Keep 3× the forecast, but base the forecast on the measured distribution: rest ≈ 300 s (V4 median, which includes the suggestions call), first ≈ 360 s. That gives caps of ~900/1,080 s, or at least 3× V4's p90.
  - Re-derive the series forecast: 100 × ~300 + 10 × 120 ≈ 31,000 s ≈ 8.6 h for item 6.
  - In item 7, either let a slow question stand as data (cap at the product's 3,600 s, with the series deadline as the stop), or state in the spec and record that an SLO proposal exists only for series with max below the cap.

## F5 — should fix — no judge bridge, unlike V4, which registered one for exactly this comparison

- **Where:** item 6 spec 108-128 and 164, which only names "judge drift" as a constraint. Compare `docs/specs/answer-prompt-v4.md:81-86`.
- **What is wrong:**
  - M1 is new answers graded now against V4's answers graded on an earlier date.
  - V4's spec required bridges: stage 2's 15 retested requests graded again and read by the stability rule, so that a moved judge (a new CLI build) would void the comparison rather than appear as a package effect.
  - Item 6 drops this. A 3-point shift in "bad", for example 17 to 20, is within what a judge change can produce and would be read as "harm detected", which holds stage 5 for Julia's yes/no.
- **Fix:**
  - Cut V4's aircargo M1 plan to its 15 retested requests with V4's replies (`reports/answer-prompt-v4/tools/bridge_plan.py` exists), grade them in item 6's window, and require the stability rule to pass.
  - That adds 15 requests, about 30–40 min and about $2–3.
  - Record `admitted_cli` on both sides in the quality record.

## F6 — should fix — `raise_stand.py` refuses on untracked files, which the registering checkout has

- **Where:** `reports/stage4-final/tools/raise_stand.py:19-21` runs `git status --porcelain` with untracked files included. Item 6 spec 170-174 runs it first.
- **What is wrong:**
  - `D:/RAG_new` has 2 porcelain lines now (`?? demo/phase-e-raw.webm`, `?? reports/ask100/`). The session's rules say these must never be committed.
  - The first command of the run refuses with "dirty checkout".
  - The stand is built by `git archive` of the commit, so untracked files cannot leak into it anyway.
- **Fix:** Use `git status --porcelain --untracked-files=no`, or check `git diff --quiet HEAD` and also confirm `HEAD == args.commit`.

## F7 — should fix — the judge's 3× stop is wall-clock and includes pauses; the post-call guard can throw away a paid reply

- **Where:** `reports/stage4-final/tools/judge.py:98-122`. The deadline is `time.time() + 3 × requests × 130`, persisted in `grade-clock.json`. `guard()` runs before and **after** `original()`.
- **What is wrong:**
  - The judge runs on the laptop for many hours and in parallel with item 7. Laptop sleep, a usage-window wait or a memory stop of the background stream (all seen in this project) count against the deadline.
  - A plan can be declared NOT_EVIDENCE, which forbids export, for idle time rather than slow requests.
  - The guard after a completed request raises after the reply was paid for. Whether the frozen sender has already journalled it is not visible here, so the reply may be lost.
- **Fix:**
  - Count elapsed time per request (the sum of request durations), or a request-count budget, rather than wall time.
  - Drop the post-call guard, or make it stop only before the next request.

## F8 — minor — `idle-after` is read right after an asynchronous unload; for item 7 its reasons count as disturbance

- **Where:** `run.py:287-302` (`keep_alive: 0`, then `pg_ctl stop`, monitor join, then `idle_check`) and `record.py:464-465` (idle-after reasons added to item 7's disturbance list).
- **What is wrong:**
  - Ollama returns from `keep_alive: 0` before the runner process exits.
  - If `/api/ps` still lists the model, or `ps` still shows `llama-server`, idle-after reports "a model is resident" or "another job" (the job regex matches `llama-server`), and item 7 is marked disturbed by its own model.
  - The same lingering runner can trip the next item 6 batch's idle-before.
- **Fix:** As step 4b's `unload()` does (`window_timing.py:431-454`), poll `/api/ps` and `ps` for up to ~60 s until both are empty, then take idle-after. Add a test.

## F9 — minor — the paired `result_sec` against 19beeb1 measures the whole path change, not "the package"

- **Where:** item 7 spec 80-100. The record wording comes from `speed_read`.
- **What is wrong:** 19beeb1 ran V3 with suggestions generated before the result (its `result_sec ≈ total_sec`, gap ≤ 0.08 s). The new path runs V4, moves suggestions after the result (stage 4 item 4), and adds the package. A "faster" reading combines all three.
- **Fix:** Name the comparison "final path (6c52b06 lineage) against 19beeb1's path". List the three changes, and do not attribute the difference to K, `num_ctx` or INT8.

## F10 — minor — the judge cost and time forecasts are about 40% high

- **Where:** item 6 spec 124-126.
- **What is wrong:**
  - Measured costs were $17.25 for 115 requests (V4 aircargo) and $17.55 for 115 (p1), about $0.15 a request against the spec's $0.21.
  - Stage 2's own spec (`stage2-four-corpora.md:68`) priced a context-judge request at 40 s and $0.10, against the 130 s used here.
  - The over-estimate does no harm to the stop rule, but the printed budget is wrong. It also drops by about half if F2's fix removes the M3 plan.
- **Fix:** Use the measured per-request cost and time, and recompute after F2 and F5.

## F11 — minor — the laptop steps need the aircargo corpus files, and the spec does not check for them before the 6-hour Mac run

- **Where:**
  - Item 6 spec 203-223: `$Data = Read-Host ...`.
  - `judge.py:45` → `record.answers` → `record.py:121-126` → `run.corpus`. This requires `$Data/aircargo/chunks.json.gz` matching `arms.ARCHIVES` and the three `SOURCE_FILES` matching the 5a reader's `CORPUS_SHA256`.
- **What is wrong:** The laptop's external root `D:/RAG_new/.tmp/external/bases` holds wixqa, conditionalqa and multihoprag, but no aircargo `chunks.json.gz` was found on D: within reasonable depth. If none exists, `judge.py plan` and `record.py quality` refuse only after the Mac run. That is recoverable, but it is late.
- **Fix:** Name the laptop path in the spec and hash-check it before raising the stand. Alternatively, `scp` the four files from the Mac with a hash check as a written step.

## F12 — minor — test gaps around the run's riskiest assumptions

- **Where:** `tests/test_stage4_final_tools.py`.
- **What is wrong:**
  - No test covers the preload payload or window (F1), the unload-then-idle-after order (F8), or the M3 ceiling.
  - `test_forecasts_caps_and_fixed_pin_lists` (951-963) pins the phrase "draft — to be cold-read and registered" in both specs. Registration must therefore edit the test, which changes the test's own SHA pinned in both specs. This is a two-step edit, not self-referential, but it is easy to get wrong in the registering commit.
- **Fix:** Add the three tests. Make the status-phrase assertion accept the registered form.

## F13 — minor — item 7 runs alongside the laptop judge, but nothing records what the laptop sent to the Mac

- **Where:** item 7 spec 25-29: "judge runs on the laptop in parallel with this run on the Mac".
- **What is wrong:** This is fine as long as no command touches the Mac. However, the spec's own laptop steps for item 6 include `scp` from the Mac (`final-answers.json`), and item 7's readable floor depends on "no other work".
- **Fix:** Say explicitly that every Mac-touching laptop step (`scp`, `ssh`) is finished before item 7 starts, or is deferred until after it.

---

## Checked and found sound

- **Forecast arithmetic:**
  - 22,200 s = 6.17 h; 6,220 s = 1.73 h; 7.89 h together.
  - The 3× stops: 66,600 s, 6,660 s per batch, 18,660 s.
  - The judge: 230 requests, 14,950 s a plan (115 × 130), 44,850 s.
- **Sign test:** a direction is first detected at 21 vs 9 (p = 0.043); 20 vs 10 gives p = 0.099. The formula matches the spec.
- **Exact order-statistic intervals at n = 30:**
  - The median uses [X10, X21] with coverage 0.957.
  - p90 is the 27th observation (30 × 0.9 = 27.0 exactly). Its upper rank is 31, so it is unbounded and encoded null.
  - The SLO proposal is `ceil(p90/30)*30`.
- **The 19beeb1 baseline adapter:**
  - It matches `runs.json`: schema `chat-live/v1`, code_sha 19beeb1, label `qwen3-4b-instruct-q30-r2`, `runner_exit` 0, model digest 0edcdef3…
  - Dataset SHA 3737d694… equals the current question file.
  - It has 30 cases, all HTTP 200, from `aircargo-probation-data` to `aircargo-road-seal`, with no timing-order violation.
  - It refuses the wrong rerun and missing times.
- **Old judge records:**
  - The route (model, effort, tools, session, system prompt SHA 5a0b99f2…), the salts and `instructions_sha256` fd015e74… equal current `evaluation/isolated_request.py` and the judges.
  - The reading-text hash 86b0b63b… matches.
  - V4 and p1 aircargo M1 cases have `has_reference` False on all 100, and the new M1 plan uses no references, so they are consistent.
  - All 100 ids are unique, with no clusters, and pair one to one.
- **Paired rule:** it reuses `v4_record.paired` unchanged, and "detected" requires both intervals on the same side.
- **API patch:** `api.py`'s `get_reranker` patch reaches the frozen stage 2 `live_api`, which wraps it at `main()` time through `getattr`.
- **V4 sent prompts:** the labelled-prompt regex reads them (labels 3–5). There is one prompt per case and five documents.
- **Stream path:** it has no LLM answer cache, so answers are not replayed from cache.
- **Item 6 case gates:** they cover HTTP, drain, one retrieval, both lanes at most 14, rerank ok, five documents and one labelled prompt after every question.
- **Data hygiene:**
  - The summary's retrieved contexts are ints.
  - `plans.json` and the receipt are text-free.
  - `judge_export.plain` and `without_text` are applied.
  - The private tar excludes chroma, and raw files stay on the Mac or under `.tmp/`.
- **Offline flags:** `deploy/macos/start.py` sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` in the service environment, with a test, and `stand.environment_gate` requires both.
- **Old env.json:** only `DEPLOYMENT_KEYS` survive it, so its old 7B model and old ceilings cannot leak in (`test_old_runtime_cannot_choose_model_settings_or_limits`).

## Disposition, 2026-10-31

Each finding was applied before registration, in the package copy's commit `62378bb` (the
executor's report names the lines); the orchestrator's own review had raised F2 before this
read arrived, and added R2.

- **F1** — the preload sends the product's own `num_ctx` (3,584, read from the API's settings);
  `/api/ps` must show that window before question 1; the llama-server pid is recorded at launch
  and every memory sample and the end must hold it. Tests refuse a preload without the window,
  another window and a pid change.
- **F2** — the context-judge plan is gone. M3 is the new M1 plan's `context_has_answer`, the
  instrument of `v4-aircargo-judge` and `p1-aircargo-judge`, paired with V4 on `4f48fed`. Both
  old sides are 100 of 100, so M3 reads one way: a detected fall is harm, and there is no «M3
  rises». The record prints the old ceiling.
- **F3** — before each batch of item 6, a wait of at most 30 min for an idle Mac, every reading
  logged; still busy, the batch runs and is marked `busy`. Item 7 waits the same way and does
  not start if the Mac stays busy.
- **F4** — no question stops below the product's 3,600-s ceiling. Item 6's forecast comes from
  V4's measured aircargo times (median 296 s, p90 390 s, max 581.6 s): 31,800 s, 8.83 h, stops
  at 3× a batch and the series. «Whole answer» is `result_sec`; `total_sec`, with the suggested
  questions, is printed beside it under its own name.
- **F5** — a judge bridge as V4's: `bridge_plan.py`, unchanged, cuts V4's aircargo plan to its
  15 retested requests with V4's replies; the copies are graded again in this item's window. A
  bridge that fails the stability rule makes the paired M1 and M3 `NOT_EVIDENCE`. It is in the
  receipt committed before the first grade.
- **F6** — `raise_stand.py` ignores untracked files and still refuses modified or staged ones.
- **F7** — the judge's 3× stop sums request durations, acts before the next request, and never
  discards a reply that arrived.
- **F8** — the reading after a batch waits until `/api/ps` lists no model and its process is gone.
- **F9** — the pairing with 19beeb1 is named as the whole path's change since then; it decides
  nothing.
- **F10** — the judge's cost is the measured range, $0.1775–0.2834 a request: 130 requests,
  $23.07–36.84 before retries.
- **F11** — the four aircargo corpus files are copied from the stand before the laptop steps;
  the first laptop command checks their presence and hashes, and the private V4 plan and
  replies against V4's published export.
- **F12** — tests for F1, F8, the M3 ceiling and each changed decision.
- **F13** — every copy between the laptop and the Mac happens before item 7 starts or after it
  ends; item 7's launch records the declaration that nothing else of ours runs on the Mac.
- **R2** (the orchestrator's) — item 7 keeps 30 of 30, but a question the foreign-job check
  marks disturbed — never its own time — is asked again once, in the same API, after question
  30; the repeat replaces it and the record keeps both. A second disturbance of a question, or
  more than six disturbed in the first pass, leaves the run `NOT_EVIDENCE`. The selection is
  by an outside criterion, not by the outcome.
