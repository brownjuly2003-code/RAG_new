# Session handoff — 2026-10-14 — the web chat on the production Mac

Session `ef96201d`, 2026-10-14 09:12–⟨END⟩ UTC, Claude Opus 5.5 alone (D12). Code measured at
`33d4b42`; documents at the commit that adds this file. **Nothing is pushed:** `origin/master`
as last fetched is `f7416ca` (2026-10-04); master is ahead of it by the 35 commits of
2026-10-04…10-08 and by this session's.

## What matters to understand

**Julia's message.** Codex — another vendor's agent, outside this repository's sessions —
ran tests on the Mac on 2026-10-12/13 (its sessions are in
`C:/Users/uedom/.codex-work/sessions/2026/10/`). Julia asked this session what went wrong in
those runs; after its analysis she wrote (2026-10-14): «а как тогда раньше ответы за
секунды? прод на маке. продолжи работу. со всем согласна. за какое время ответ возможен?»
It holds five things:

- «а как тогда раньше ответы за секунды?» — why she remembers answers in seconds: answer 1.
- «прод на маке» — production runs on `deproject-mac`. That answers the deployment-target
  half of D5; the SLO half is still hers. Do not answer "buy other hardware"; a hosted model
  is a different matter — a model swap that only she can choose.
- «продолжи работу» — go on without asking.
- «со всем согласна» — she accepted the analysis's three recommendations: (1) decide what
  production runs on; (2) split the four real fixes out of the uncommitted Codex WIP and
  commit them with tests on the Mac, replacing the byte limit of prompts with a token count
  («Могу взять п. 2» — accepted); (3) the next test is the standard configuration on the
  web chat's path, 1 question → 5 → 100, the supervisor detached from ssh from its first
  launch.
- «за какое время ответ возможен?» — she wants a measured time, not a forecast: answers 2, 3.

**How the web chat answers.** `static/chat.inline.js` calls `/api/ask/stream` (or
`/api/chat/stream` when `STREAMING_ENABLED` is on; off by default); both run `ask_stream` in
`api/routers/conversation.py` (the legacy direct stream, `STREAMING_RAG_PARITY=false`). One request makes, in order:

1. retrieval — hybrid BM25 + BGE-M3 vectors, a cross-encoder rerank of 20 candidates,
   parent expansion;
2. one streaming call to the generator over the top five chunks (`generate` role, up to
   1,024 tokens out; the prompts of B2 were 2,101–2,377 tokens by the exact Qwen count);
3. self-eval over the same documents (2,314–2,616 tokens in, up to 128 out;
   `STREAMING_QUALITY_EVAL`, on by default). Its score also decides the route: `auto` at
   `QUALITY_THRESHOLD` or above, else `human`; without it a heuristic score decides;
4. suggested follow-up questions (`question_llm.invoke`, no role, so the default 512 tokens
   out; only when the route is `auto`);
5. the `result` event with quality, route, sources and suggestions.

`REQUEST_TIMEOUT_SEC` (code default 30 s) is the deadline of the whole request, the stream
included; `STREAMING_TIMEOUT_SEC` (120 s) bounds the token loop; `OLLAMA_REQUEST_TIMEOUT_SEC`
(60 s) bounds the transport, and since `cefd7c3` the transport also stops at the request
deadline. The deadline is cooperative: code checks it between steps. With
`RAG_RERANK_BATCH` unset the reranker scores all 20 pairs in one call that nothing
interrupts, so the per-batch check of `0dfd159` never runs and a slow rerank overruns the
30 s (B1's warm-up: 77.8 s).

**The machine.** `deproject-mac`: Intel Core i5-7500, 4 cores, 8 GB RAM, Radeon Pro 570
with 4 GB. Ollama 0.33.2 runs every model on the CPU. Bench of 2026-10-14 (num_ctx 4096,
`reports/chat-live/33d4b42/bench/`): qwen2.5:7b reads a prompt at 17–23 tokens/s and writes
4–5 tokens/s; qwen2.5:1.5b reads 113–128 and writes 20–25. Auto_try_v2 (HH automation,
PIDs 33002/33004/33007) and several PostgreSQL servers run on the same Mac all the time.

**Answer 1 — why «раньше секунды».** No record shows a real answer in seconds:

- the 2,178 traces of `D:/RAG_new/data/tracing/traces.db` (2026-08-23…10-04) take 0.01–8 s
  because they are tests with fake models;
- the phase-E demo (2026-09-29) answered in 113–224 s;
- the old RAG_Support_Assistant with hosted Mistral (38 requests, 2026-06-16…18) took
  29.6–711.3 s per answer, median 193.6 s. Its model steps took a median 1.2 s (0.3–142 s;
  generation 3.2 s), but each request retrieved one to several times (54 retrievals in 38
  requests) at 16–293 s each.

Fast model calls existed only with a hosted model; the whole answer was never seconds.

**Answer 2 — how long an answer takes now.** Record `reports/chat-live/33d4b42/runs.json`
(code SHA, index digest `b7cdcac1…` of the 5,589 chunks, dataset sha256, Ollama model
digest, every setting off the code default), its row in `EVIDENCE_INDEX.md`, test
`tests/test_chat_live_artifact.py`. Questions: five cases of
`evaluation/curated_cases_aircargo.jsonl` (`aircargo-probation-data`, `-probation-extend`,
`-probation-dismissal`, `-dismissal-check`, `-dismissal-lawyer`), sent as the web chat sends
them; a warm-up question outside the set, «Какие документы нужны для перевозки опасного
груза?», goes first where named.

- **Code defaults (B1): no answer.** The first case ended at 30.9 s with route `timeout` and
  not one token. Retrieval alone took 25.4 s of the 30 s: vector search 5.5 s, then 19.7 s
  of rerank that ended in "MPS backend out of memory", so the order fell back to
  unreranked; the stream had 4.6 s left and timed out before Ollama sent anything. The
  warm-up before it ended the same way at 77.8 s (retrieval 70.5 s, the rerank 63.3 s of it
  before its out-of-memory).
- **Limits raised to 1800 s, `RAG_DEVICE=cpu` (B2): five complete answers** — first token
  median 325 s (285–423 s), the whole answer (the `result` event) median 486 s (429–614 s).
  Per question: retrieval 214 s (vector 72 s, rerank 142 s), reading the 2,258-token prompt
  115 s, writing 4.0 tokens/s (answers of 53–95 tokens, 164–299 characters), self-eval 122 s,
  suggested questions another 21–33 s. No warm-up question: the supervisor loaded the model
  first (37.7 s), so the first case paid only the retrieval models' first pass. Swap grew
  from 0.6 to 4.0 GB and free memory fell to 3 MB: the 7B model (4.9 GB resident in Ollama)
  and the API with the embedder and the reranker do not fit 8 GB together, so later
  questions were no faster than the first. Auto_try_v2 started Chrome during case 3 (load
  average 9.97 on 4 cores at 11:49 UTC).
- **Retrieval alone, no model in Ollama (R1, R2),** a fresh process per placement. On the
  CPU: median 27.6 s (22–38 s) per question, the rerank 27.3 s of it, the vector search
  0.2 s; the first question after a start takes 100–120 s (the models' first pass). B2's
  retrieval was 8× slower by the medians — 5–6× on cases 1–2, before Chrome started — so
  swapping, not the foreign load, made most of it. On the GPU the reranker fails with MPS
  out of memory at the default batch even alone, and under the default `RAG_DEVICE=auto`
  (both models on the GPU) every rerank fails; after one or two failures of 27–66 s each,
  every later one failed within a second. At batch 4 it works but takes median 57.1 s
  (48–64 s), 2.1× the CPU; at batch 1 median 92.6 s (85–101 s); both models on the GPU at
  batch 4 median 55.8 s (48–71 s). The embedder alone on the GPU changes nothing (vector
  search 0.2–0.5 s either way). With no model loaded, R2's GPU runs still pushed swap to
  2.3 GB (R1: 0.75 GB).

**Answer 3 — what is possible on this Mac.** What each part costs, measured:

- **Reading the prompt** decides the first word. The 7B read 17–23 tokens/s in the bench
  and 16–21 in B2, so a chat prompt of 2,100–2,400 tokens takes 100–140 s before Ollama
  sends anything. The 30-s request limit covers retrieval and reading together, so no
  setting brings the 7B's first word under it. Its lower bound is about 2.4 min (retrieval
  27.6 s + reading ~115 s), reachable only without swap, which the 7B, the embedder and the
  reranker on 8 GB do not allow.
- **Writing** at 4 tokens/s: an answer of 53–95 tokens takes 13–24 s after its first word.
- **After the answer**, the `result` event waits for self-eval (another reading of the
  prompt, 107–156 s) and the suggested questions (21–33 s). Turning both off
  (`STREAMING_QUALITY_EVAL`, `SUGGESTED_QUESTIONS_ENABLED`) would take ~2.5 min off the whole
  answer and nothing off the first word; it cuts features and hands routing to the
  heuristic score.
- **Retrieval** is the rerank of 20 candidates: 22–38 s on the CPU, the vector search 0.2 s.
  The 4 GB GPU does not help: it fails at the default batch and is 2.1× slower than the CPU
  at batch 4, 3.4× at batch 1. Fewer candidates (`RAG_RETRIEVAL_TOP_K`) or a smaller reranker would
  cut it, at a cost in quality nobody has measured here.
- **A smaller local model** — qwen2.5:1.5b reads 113–128 tokens/s and writes 20–25; by
  arithmetic its first word would come at ~50 s (retrieval ~28 s + reading ~20 s). In the
  bench two of its three answers were a bare citation mark ("[1]", "[5]") and the third
  contradicted itself; in Codex's `seconds100-20261013` run (1.5B, 30 s) one question of 100
  ended `auto`. It is a model swap.
- **A hosted model** — in June its model steps took a median 1.2 s; the first word would
  then come at about the retrieval time, ~28 s on the CPU, less only with a cheaper rerank.
  It is a model swap, it sends retrieved corpus text off the Mac, and Mistral needs the
  Mac's VPN, which Auto_try_v2 needs off.

So answers in seconds on this Mac need a hosted (or much smaller) model and a cheaper rerank.
With the local 7B the measured times are ~5.5 min to the first word and ~8 min to the
whole answer, and under the code defaults there is no answer at all.

**What decides the next step:** which LLM serves production and what "seconds" means as an
SLO (first word or whole answer, at what share of questions). Both are Julia's.

## Julia's decisions in force

- D12, 2026-10-04: «ты должен все делать сам» — the session's model does every job and
  check; no other model in any role.
- D11, 2026-10-03: «люди участвовать в процессе не будут».
- 2026-10-14: «прод на маке»; «со всем согласна» (above).
- From 2026-10-13 (memory `chat-test-expectations`): a chat test uses the real path and the
  production limits; raising timeouts to minutes or cutting the pipeline to make a test
  look fast is «симуляция над симуляцией»; one question first, then five, before a hundred.

## What was the session's choice, not hers

- B2 raised the three limits to 1800 s. That is a measurement of how long a complete answer
  takes, never a fix and never "the chat works": under the code defaults it does not.
- B2 set `RAG_DEVICE=cpu`: B1 showed that the default `auto` puts the reranker on the 4 GB
  GPU, where it fails with MPS out of memory and the order stays unreranked.
- No 100-question run: one question in the standard configuration got no answer, so the
  gate stopped at step 1; B2 ran five questions as a measurement.
- Of the four fixes named in recommendation 2, three are on master — the Ollama timeout
  (`cefd7c3`), the context window (`2758be5`, `33d4b42`, by counted tokens instead of
  bytes), the escalations' event loop (`f355c31`) — plus the reranker's deadline check
  (`0dfd159`). The fourth, «model selection», was no code defect: a provider profile in
  `config/providers.yml` names the model and `OLLAMA_MODEL_NAME` does not override it; the
  WIP answered it with a new 1.5B profile `local-low-memory`, a model swap, so it stayed in
  the branch with the rest of the WIP.

## Log

- 09:12 UTC — analysis of the Codex runs; sent to Julia. Findings in short: the hardware
  times a chain of 4–15 sequential model calls made seconds impossible; the runs measured
  `/api/ask` while the web chat uses `/api/ask/stream`; "fast" came from cutting (1.5B,
  reranker off, rewrite off); the WIP limited prompts by UTF-8 bytes against a limit in
  tokens (Russian ≈ 5.1 bytes per token), so over 506 calls the model saw at most 898
  tokens of its 4,096-token window, median 453.
- 10:02–10:47 UTC — five commits on master, each red on its parent and green on the Mac:
  `cefd7c3` (Ollama transport bounded by the request deadline), `0dfd159` (reranker batches
  check the deadline), `f355c31` (graph escalations persisted on the API event loop),
  `2758be5` (stream prompt fitted to the Ollama window by tokens), `33d4b42` (every graph
  prompt fitted; the provider refuses a prompt above the window). Green on `33d4b42`: 943
  passed, 2 skipped in 78 files; red on `2758be5` for the new tests: 12 failed.
- The rest of the WIP (compact pipeline, the `local-low-memory` 1.5B profile, the
  query-transform switch, whole-answer verify, their documents) is kept byte for byte in
  branch `wip/ask100-latency-20261013` (`2949b02`, base `7cad79f`, before the five fixes)
  and in `D:/RAG_new/.tmp/ask100-split/wip-files/`. Restoring a whole file from the branch
  reverts the fixes in it: first `git -C D:/RAG_new diff 33d4b42 wip/ask100-latency-20261013
  -- <path>`; files the fixes did not touch can be restored with `git restore
  --source=wip/ask100-latency-20261013 --worktree -- <path>`, the others need a hand merge.
- Bench of Ollama on the Mac (`reports/chat-live/33d4b42/bench/`: script, the prompt
  builder it copied from `agent/prompts.py`, results).
- Run A (`live-a-prod`) took `env.json`'s limits by mistake (1800 s request, 120 s stream,
  `RAG_DEVICE=cpu`); stopped after one question; not published.
- 11:14–11:17 UTC — run B1 (`live-b1-prod`), code defaults: the warm-up and one case, both
  `timeout`, no token.
- 11:22–12:07 UTC — run B2 (`live-b2-floor`), 1800-s limits and `RAG_DEVICE=cpu`: five
  answers. At 11:47:37 Auto_try_v2 started Google Chrome; at 11:49 the load average was 9.97
  on 4 cores and swap 2.3 GB (`notes` of the run). B2's resource sampler recorded neither
  the load average nor foreign processes; it does since R1.
- The June traces of the old RAG_Support_Assistant (`/Users/julia/RAG_Support_Assistant/
  data/tracing/traces.db`) read again for answer 1 (`tools/old_prod_lat.py`).
- 12:08–12:21 UTC — run R1 (`live-r1-retrieval`): retrieval alone, the warm-up and the five
  cases, placements `auto`, `cpu`, the reranker on the GPU, the embedder on the GPU.
- 12:22–12:50 UTC — run R2 (`live-r2-rerank-gpu`): the reranker on the GPU with its error
  recorded, at batches 4 and 1, both models on the GPU at batch 4, and `auto` again.
- A fresh agent of the same model read this file cold; its points were fixed in place.
- ⟨REPORT⟩

## State at the end

- `master` (local): the five fixes `cefd7c3`…`33d4b42` and the commit that adds this file
  and the record; `origin/master` is still `f7416ca`. Nothing pushed.
- Committed (local, not published): `reports/chat-live/33d4b42/runs.json` with the tools
  that made it (`tools/`) and the bench (`bench/`), its row in `EVIDENCE_INDEX.md`, the test
  `tests/test_chat_live_artifact.py`, the subsection "Web chat on the production Mac" in
  `CURRENT_STATE.md`. Runs A and B1 ran earlier versions of `live_runner.py` and
  `live_supervisor.py` (no stop at the first case without an answer, no `SETTING=VALUE`
  argument; B1 asked one case of the set anyway), B2 a supervisor without load sampling, R1
  an earlier `live_retrieval.py` (no error text); the copies in `tools/` are the final
  versions.
- The Mac: the stand `/Users/julia/RAG_new_chat_33d4b42/` — the workspace is `git archive
  33d4b42` with `CODE_SHA`; `chatlive/` holds the tools and `runs/` the raw runs (API logs,
  stage logs, prompts, resource samples, `launch.json`, `analysis.json`). Its
  `.ask100-runtime` links to `/Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime`
  (the index, the test database on port 55433, `env.json`). After the last run ports 8002
  and 55433 were free, Ollama held no model and no `live_` process was left.
- Untracked and not this session's: `demo/phase-e-raw.webm`, `reports/ask100/`.

## The stand — how to run it

On the Mac (`ssh deproject-mac`, interpreter `/Users/julia/RAG_Support_Assistant/.venv/bin/
python`, called `$PY` here), in `/Users/julia/RAG_new_chat_33d4b42/chatlive/`:

- Before a run: `sysctl -n vm.loadavg vm.swapusage` and `ps -axo pid,pcpu,rss,comm -r | head`
  — nothing heavy of ours, Ollama holding no model. Auto_try_v2 may start Chrome at any
  time; write what you see into `runs/LABEL/notes.json` (the export carries it).
- `$PY launch.py LABEL MODE CASES CAP [RAG_DEVICE=cpu]` starts `live_supervisor.py` in its
  own session, so a dropped ssh does not kill the run. `CASES` is a comma list of case ids,
  `warmup:<question>` for a question outside the set; `CAP` is the client's limit per
  question in seconds. `MODE prod` loads `env.json` into the API's environment without
  printing it and puts back every setting `env.json` moved off the code default (its
  1800-s limits and `RAG_DEVICE=cpu`); `floor` is `prod` with the three limits at 1800 s;
  `retrieval` runs `live_retrieval.py` per placement (`LIVE_VARIANTS`, e.g.
  `rerank-mps-b4`) with no API, database or model. The supervisor refuses taken ports
  (8002, 55433) or a loaded model, starts PostgreSQL and the API, loads qwen2.5:7b and times
  it, runs `live_runner.py` (which stops at the first case without an answer), and stops
  what it started. Its log `runs/LABEL.supervisor.log` ends with `LIVE_DONE`.
- After: `analyze.py LABEL` or `analyze_retrieval.py LABEL`, then `export.sh` (labels
  inside) writes `runs.json` from a clean environment and `check_export.py` lists anything
  secret-like by path, never by value.
- Tests on the Mac (gate): `MSYS_NO_PATHCONV=1 timeout 600 python -I -X utf8
  D:/RAG_new/.tmp/ask100-split/sync_commit.py <rev>`, then `MSYS_NO_PATHCONV=1 timeout 1100
  python -I -X utf8 D:/RAG_new/.tmp/mf-mac/remote.py --site pytest <files> -q -p
  no:schemathesis -p no:cacheprovider --basetemp=.tmp/pytest-<name> --tb=line`. The 943
  of `33d4b42` were 78 files this way — the new tests and the suites around the changed
  code (list: `.tmp/ask100-split/c5-green-files.txt` on the laptop, git-ignored); the whole
  `tests/` (399 files) was not run in this session.

## Next actions

Once Julia decides:

1. **Which LLM serves production, and the SLO** — the open half of D5; the choices and what
   each costs are in answer 3. The limits then follow her SLO, never the other way round:
   raising them so that a test passes is what she called «симуляция над симуляцией». A
   hosted or smaller model is the model swap of the ROADMAP stop-list and needs her word.
2. **Then the gate 1 → 5 → 100** in that configuration with her limits, on the web chat's
   path (see the stand). State the per-question time before the 100.

Code that needs no decision of hers (red test first, rule (a)):

3. **`RAG_DEVICE=auto` silently drops the rerank on this Mac.** `_resolve_device` picks MPS
   whenever PyTorch offers it; on the 4 GB Radeon the reranker then fails with MPS out of
   memory, `_rerank_scored_with_status` logs a WARNING and returns the unreranked order,
   and every answer is built on that order with nothing shown to the user. Until the code
   handles it, production on this Mac needs `RAG_DEVICE=cpu` in its environment. A slice:
   `auto` must not give the reranker to MPS where it fails (for example, resolve the
   reranker to the CPU when a first MPS call fails, in a fresh model), proven through
   `/api/ask/stream` with a reranker that raises the MPS error. In the same place: with
   `RAG_RERANK_BATCH` unset the rerank cannot be interrupted by the request deadline.
4. **Audit writes lost under load:** B2's API log has "Audit DB write failed: action=ask
   error=TimeoutError" twice — two answers without their audit record on a swapping
   machine. Find the writer that times out and whether the request deadline cuts it.

Housekeeping: master's local commits wait for Julia's word to push; the WIP branch matters
only if she chooses a smaller model or a shorter pipeline.

## Do not

- Push without Julia's word (`git -c credential.helper='!gh auth git-credential' push origin
  master` when she gives it).
- Run 100 questions, or anything long, without a measured per-question time stated first.
- Read, print or copy `.ask100-runtime/env.json`: it holds secrets; the supervisor loads it
  into the API's environment and the API dumps its settings with secret-like fields masked.
- Kill processes you did not start on the Mac (Auto_try_v2, PostgreSQL servers, `ollama
  serve`), install anything there with brew, or rebuild the 5,589-chunk index.
- Touch `demo/phase-e-raw.webm` or `reports/ask100/` (untracked, not this session's).

## Lessons

- An environment file can carry a run's hacks: `env.json` of the ask100 snapshot held
  30-minute limits and `RAG_DEVICE=cpu`, so run A silently measured a non-standard
  configuration. Dump the effective settings and diff them against a clean `Settings()`
  before measuring (`tools/defaults_diff.py`).
- A client that stops reading does not stop the server: the executor thread finishes the
  self-eval. Wait until the API reports no pipeline in flight and every observed stage has
  ended before the next question.
- `cd D:/… && scp …` in one Bash call moved the shell's working directory for the rest of
  the session; use absolute paths only.
- The fastest retrieval of R1 was the broken one: under `auto` it took 0.1–0.2 s because the
  reranker failed at once. Read `reranker_ok` (in the API, the path's `rerank_status`) next
  to every retrieval time.
- One MPS out-of-memory poisons the process. R2 kept the errors: after two failures of
  27–51 s, the memory MPS reported as taken (allocated plus other allocations) stood at
  7.5–7.6 GB, above its 6.80 GB cap, so every later rerank failed within a second while
  asking for kilobytes. A device experiment needs a fresh process per placement, as
  `live_retrieval.py` runs.
- When five questions are no faster than the first, suspect memory before the model: B2's
  retrieval took 214 s, the same retrieval alone 27.6 s. Measure the parts apart before
  blaming the generator.
- Monitors over ssh: BSD `cut` and `sed` buffer when piped (`sed -l`, `grep
  --line-buffered`), and `kill $!` stops only the last process of a background pipeline —
  the `tail -F` of two monitors outlived them on the Mac until killed by PID.

## Glossary

- **A, B1, B2** — the live chat runs of this session (labels `live-a-prod`,
  `live-b1-prod`, `live-b2-floor` in `chatlive/runs/` on the Mac); **R1, R2** — its
  retrieval-only runs (`live-r1-retrieval`, `live-r2-rerank-gpu`), no model in Ollama.
- **Placement** — which device holds the embedder (BGE-M3, vector search) and the reranker
  (bge-reranker-v2-m3, a cross-encoder over 20 candidates). The product has one setting for
  both (`RAG_DEVICE`: `cpu`, `mps` or `auto`); R1 and R2 split them by patching
  `_resolve_device` per loader inside `live_retrieval.py`. **Batch** — the cross-encoder's
  pairs per call (`RAG_RERANK_BATCH`; unset = the library's 32, so all 20 pairs at once).
- **Standard configuration** — the code defaults of `config/settings.py` plus the
  deployment's paths and secrets from `env.json` (`MODE prod`).
- **Floor run** — B2: the standard configuration with the request, stream and Ollama limits
  raised to 1800 s, to learn how long a complete answer takes, here with `RAG_DEVICE=cpu`.
- **Route** — the verdict in the `result` event: `auto` (answered), `human` (handed to an
  operator), `timeout` (the request deadline hit), `error`. Unrelated to `RAG_DEVICE=auto`.
- **First token** — the first `token` SSE event the client received; **result** — the final
  `result` event; both in seconds from the request.
- **Self-eval** — the model's 0–100 score of its own answer (`build_self_eval_prompt`).
- **num_ctx** — Ollama's context window, 4,096 tokens here.
- **MPS** — PyTorch's Metal backend; on this Mac it runs on the 4 GB Radeon.
- **D5** — deployment target and SLO (owner's decision); **D11**, **D12** — above.
- **Gate 1 → 5 → 100** — a question passes when it gets a complete answer (tokens and the
  `result` event) within the production limits; one must pass before five, five before a
  hundred.

## Verification

⟨VERIFICATION⟩
