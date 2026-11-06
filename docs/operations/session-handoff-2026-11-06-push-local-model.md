# Session handoff — 2026-11-05 14:45 → 2026-11-06 ≈ 13:40 UTC: the codex-only record, a push held by two failing tests, Codex's limit, a small model for her laptop, graph search on

Times are UTC. Git prints laptop-local time, UTC−5: `git log` shows 01:30 for `5995042`, which this
file gives as 06:30. The session took over from
[the measurement handoff](session-handoff-2026-11-05-codex-only-measurement.md) and did its Next
actions 1–6. That file is closed.

## Read this first

- **What this session closed.** The quality measurement of stage 6 item 0: the product under
  `codex-only` on her laptop. Item 0 itself stays in work. The [record](../evidence/codex-only-quality-record.md) holds as row 3:
  - "answered good" went from 268 to 279 of 300, a detected rise;
  - gold in the sent context went from 125 to 116 of 180, not detected.
  - The README publishes it (`5995042`).
- **What came after.**
  - Her «пуш» and the push gates.
  - Three ci_local runs. Two failed on our own leftovers in the CI VM, which led to a fix in
    ci_local itself ([ci_local's leftovers](#ci_locals-leftovers)); the third found two failing
    unit tests.
  - Two questions of hers about Qwen and Codex's limit, answered with a usage estimate.
  - Her decision to keep a local model line.
  - [Research 8](research-2026-11-06/README.md): a small model on her laptop.
- **Her decisions of 2026-11-06 are not in `PLAN.md` yet.** Next action 1 puts them there,
  graph search included; Next action 2 records Codex's runs, and Next action 3 starts turning
  graph search on.
- **The push did not happen.** ci_local run 3 found two real failures in the unit tests, in code
  of 11-03…11-06, and both fail on the Mac too. A fix is a new commit outside her «пуш», so its
  push needs her word: [Next action 0](#next-actions-in-order).
- **The old session** wrote this file and edits nothing after the commit that adds it. It may stay
  open until run 3 ends by itself, about 14:00–14:30 UTC. Its Codex broker is stopped.
- **How to start.** In a new session she types «продолжи» or «продолжи по handoff 06.11»;
  the status at the top of `CURRENT_STATE.md` points here. First run
  `git -C D:/RAG_new log --oneline -2` and `git -C D:/RAG_new status --short`. The top commit
  should add this file on top of `5995042`, and only `demo/phase-e-raw.webm` and `reports/ask100/`
  should be untracked. If this file shows as untracked, the old session has not committed yet:
  wait, and stage none of its files. Then do [Next actions](#next-actions-in-order) in order.

## Julia's words in this session (UTC)

- 2026-11-05, during the judging:
  - 14:45 «продолжи работу»; 16:05 «лимит есть»; 16:06 «важно задачу качественно завершить»;
  - 17:56 «точно все нормально???»; 17:58 «нужно максимально процесс отладить»;
  - 19:04 «что -то не так?»; 19:35 «продолжи работу»; 20:25 «что-то явно не так? нет?»;
  - 20:36 «как тебе помочь?»; 20:38 «сделай это сам. авто режим отключила»;
  - 21:24 «лимит есть», «нужно качественно задачу сделать»;
  - 22:16 «как я могу закрыть диспетчер задач??? и что это??? сделай это сам. авто режим выключила»;
  - 22:39 «продолжи».
- 2026-11-06:
  - 08:42 «а какой итог-то нескольких дней?»; 08:49 «а что мы по сути получили?»
  - 08:56 «а план для дальнейщей работы понятен? пуш». This is **her word to push** the range
    `591481f..5995042`, 43 commits, and only that range.
  - 09:14 «мы дельше будем использовать qwen? кодекса не хватит, и мы делалали небольшой эксперимент»
  - 09:30 «получается, что qwen - это совсем плохо и не вариант?»
  - 09:49 «нет, ничего не заводим. И с чего такой вопрос? Мы не оставляем историю про qwen. Может,
    стоит поискать маленькую, более эффективную модель? Вероятно позже стоит запустить на этой
    машине маленькую модель?» I had asked whether to open a separate Codex account for the product.
  - 10:10 «твой ci - он еще надолго?»
  - 10:34 «вероятно есть смысл закрыть эту сессию?» The answer: yes, right after the push. This
    handoff was written while the CI ran.
  - 11:57 «в следующей сессии все будет понятно? сессия будет искать новую модель маленькую для
    локального запуска? кстати, нужно и графовый поиск включить. это все отражено? Запуски на
    кодекс отражены в проекте? Они очень важны для понимания статистики и возможностей моделей»
    Two of these are new decisions: graph search is to be turned on, and the Codex runs are to be
    recorded in the repository. Next actions 1 and 2 carry them.
  - 12:07 «графовый поиск нужно включить. Почему запуски на Codex записаны только наполовину? Нужно
    это поправить в след сессии». Graph search on is decided, not a measurement's outcome (Next
    actions 1 and 3). The Codex runs are fixed in the next session (Next action 2); why only half was
    recorded is in [Lessons](#lessons).
  - 12:32 «а новую сессию можно запустить?» The answer: yes, once this file is committed. Run 3
    then failed (Next action 0), so the old session pushes nothing.

## What this session did

- **The record.** The 11-05 handoff's Next actions 1–6:
  - `e2845c9` (11-05 14:58): the judge route receipt;
  - `557c2d0` (01:21), `cd1223d` (03:42) and `8c0014e` (05:32): the three keys graded and exported;
  - `090dcd1` (05:39): the reading, row 3, holds;
  - `3dc49a4` (06:30): the record capsule, its test and the status documents;
  - `5995042` (06:30): the README under `codex-only`.

  Stage 6 item 0 of `PLAN.md` gives the judging run's lesson.
- **Push gates.**
  - gitleaks: 272 findings, all false positives (SHA-256 values keyed by file paths).
  - The shingle scan: clean.
  - ci_local, run 1, 08:57–10:27: failed in `ci/helm` and was stopped (see
    [ci_local's leftovers](#ci_locals-leftovers)).
  - ci_local, run 2, 10:27–11:21: failed on disk space in the CI VM. The cause was a leftover of
    run 1's stop, in the same section.
  - ci_local, run 3, from 11:33 (`RAG_new_20261106-063247`): two unit tests failed; see
    [State at the end](#state-at-the-end).
- **Codex usage.** An estimate from the rollouts, below.
- **Research 8.** Moved from `.tmp` into
  [`docs/operations/research-2026-11-06/`](research-2026-11-06/README.md), with its brief and a README.
- **The SLO, 09:05.** I proposed one to her: the whole answer within 90 s for 9 of 10 questions. The
  record's p90 is 83.3 s; the rule of `PLAN.md` §8.3 item 2 rounds it up to a multiple of 30 s,
  83.3 → 90 s. **She has not
  answered.**

## Codex usage (cw), from the rollouts

- **Source.**
  - The `token_count` events in `%USERPROFILE%/.codex-work/sessions/2026/11/` carry `rate_limits`.
  - `.tmp/cx-exec/codex_windows.py` prints only numbers and times, because the rollouts hold
    external-base text.
  - Only a **weekly** window shows (10,080 min); there is no five-hour window.
- **The product's share.** It costs about **0.03 % of the week per question**. Each question is two
  `low` calls and one `xhigh` call, through `codex exec --ephemeral`.
  - 11-05 03:13→14:56: 7 → 17 % over ≈ 340 questions.
  - 11-04 14:27→19:33: 89 → 94 % over ≈ 150 questions.
  - Other work ran in the same hours, so this is an upper bound.
  - That is ≈ 3,000 questions a week if the account served the product alone.
- **The account is shared.** All her projects and RAG_new's executor use it.
  - It reached 100 % on 11-01 at 23:13 and on 11-05 at 01:21; both times a reset followed.
  - On 11-06 at 06:24 it stood at 39 % of the window in force; that window resets on 11-12 at 01:25.
  - On a Codex limit the product routes every question to `human`. The error `codex_usage_limit` is
    raised in `llm/providers/codex.py` (about line 195); `_generation_provider_fail_closed` in
    `agent/graph.py` (about line 2071) turns it into the route.
- **Her answer to a separate account: «нет, ничего не заводим».** Capacity comes from efficiency:
  fewer Codex calls and a small local model for the helpers.

## A small model on her laptop

- **What research 8 found.** It is in its [README](research-2026-11-06/README.md).
  - The laptop's Arc iGPU (through OpenVINO) should run a 4B-class model in seconds per call. This
    is the report's estimate from Intel's 155H figures, not measured. Its CPU through Ollama took
    minutes.
  - The NPU fits short prompts only.
  - A threshold on the reranker score may replace role 2, document grading, with no model at all.
  - The answer, role 3, stays with Codex.
- **The order** is the report's, not her choice:
  - 0, the reranker threshold, offline;
  - A, Qwen3-4B-Instruct-2507 INT4 on the iGPU;
  - B, Qwen3.5-2B on the iGPU;
  - C, Qwen3-1.7B on the NPU, role 1 only.
- **Rules that stand.**
  - No local model starts on her laptop without her word for that run.
  - Never Ollama on the CPU.
  - A first test is short and stoppable, with the watchdog of the research README.
  - A model swap needs her decision with numbers (`PLAN.md` §9).

## ci_local's leftovers

- **What failed first.** Run 1's `ci/helm` failed in `helm/kind-action` with "node(s) already exist for a
  cluster with the name chart-testing".
- **Why.**
  - ci_local never runs an action's post step.
  - Our own full run of 2026-11-03 left the container `chart-testing-control-plane` in the colima VM
    `ci-local` on imac-julia. The container was created 2026-11-03 14:52 UTC.
  - The VM restarts it with docker, and the next run collides with it.
  - The leftover control plane also loads the VM's 3 CPUs and 4 GB. That is probably why run 1's
    postgres service started too slowly and `ci/migrations` came out incomplete; on 11-03 it started
    in 12 s.
- **What the session did.** A helm FAIL makes the verdict FAIL, so run 1 could not stamp.
  - It removed the stale container and run 1's own runner container (both ours), and run 1 ended
    with rc 4.
  - Run 2 started at once, about an hour sooner than waiting out run 1's other nine jobs.
- **It happened again.** Run 2's helm job left the cluster behind too, created 10:58 UTC. Another
  project's run had the VM up at 11:45, so the session removed it then. The second `docker rm -f`
  was needed: the first one said "did not receive an exit event".
  - Root fix, Next action 5: a cleanup in ci_local. It went in at 11:47, while run 3 waited for the
    VM; run 3 itself still uses the old launcher.
  - The launcher stops the VM after the run that started it, so between runs the container sits in
    a stopped VM. Never start the shared VM by hand to clean it.
  - Do not remove it by hand. If the VM is up, a run holds it, possibly another project's helm
    job: DE_project and DE_project_new use `helm/kind-action` too, and their cluster is named
    `chart-testing` as well. `kind_down` removes stale clusters at the start of the next linux
    run, under the lock.
  - The one exception: the fix is rolled back, and our own run holds the VM and fails at
    `ci/helm` on a stale cluster. Then remove the container on imac-julia,
    `ssh imac-julia 'PATH=/usr/local/bin:$PATH DOCKER_HOST=unix://$HOME/.colima/ci-local/docker.sock docker rm -f chart-testing-control-plane'`,
    stop the run, remove its directory as below, and rerun.
- **Run 2 then ran out of disk.**
  - `ci/test-unit (python-version=3.11)` failed after 620 s while installing the lock, torch with
    its CUDA wheels: `[Errno 28] No space left on device`. Every later job failed in 0 s, because
    its directory could not be created. The verdict: FAIL, 10 passed, 6 failed, 6 uncovered.
  - The cause was run 1's stop. Removing a runner container by hand skips the container's own last
    command, the `sudo rm -rf` of its run directory. Run 1's jobs and venvs, 7.97 GB, stayed in
    `/var/tmp/ci_local/RAG_new_20261106-035748` inside the VM.
  - In the VM, `/var/tmp` sits on the 19 GiB root disk, not on the 60 GiB data disk. Run 2 had
    about 9 GB of it. On 11-03 the same jobs had about 17 GB and passed.
  - The session removed that directory, ours; the root disk then had 17 GB free. Run 3 started at
    11:33.
- **The VM's docker disk is nearly full.** `/var/lib/docker` holds every project's images: 49 of
  59 GB used, 7 GB free, at 11:30. It is not ours to clean. If a run fails on space inside docker,
  read `docker system df` and leave other projects' images alone.

## My choices, not hers

- **I stopped run 1 at its helm failure** instead of waiting out its other nine jobs, and removed both
  containers of ours from the shared VM. That cost run 2 (see above), and I removed run 1's
  directory from the VM.
- **I made the ci_local fix in this session**, not the next. Run 3 waited for the VM anyway. Each
  leftover cluster restarts with the VM and loads its 3 CPUs and 4 GB, and every project's runs
  share that VM.
- **I did not stop run 3 at its first failure.** Its other jobs show whether more fails before the
  rerun, and a run stopped by hand leaves its directory in the VM. Another project's run waits
  behind it for about 45 minutes longer.
- **Research 8 ran as one subagent on the session's model** (D12), not on Codex. This kept Codex's
  shared weekly window for the product.
- **I moved research 8 into `docs/operations/`.** The repository is public, and the report names her
  laptop's hardware and nothing personal.
- **The 0 → A → B → C order and the 90-s SLO** are proposals. She has not chosen.

## Next actions (in order)

0. **Fix the two failing tests, rerun CI, then ask her about the push.**
   - **What failed.** ci_local run 3, `ci/test-unit (python-version=3.11)`, «Run unit tests»: 2
     failed, 8,950 passed, 58 skipped. Both fail the same way on the Mac (`sync.py`, then
     `remote.py`, about 13:20):
     - `tests/test_llm_response_cache.py::test_cache_miss_invokes_pipeline_and_stores`. The stored
       response now carries `answer_model` and `answer_provider`, both `None` there, and the test
       compares the whole dict. The keys came with the codex-only work:
       `git -C D:/RAG_new log -S answer_provider --oneline 591481f..5995042` lists four commits.
       Decide whether a cached answer keeps them, then fix the test or the code.
     - `tests/test_lightweight_gracekelly_smoke.py::test_direct_cli_resolves_project_imports`.
       `scripts/lightweight_gracekelly_smoke.py` must finish within the test's `timeout=15`. In
       the VM it was killed with no output; on the Mac it took 20.18 s. The script has not changed
       since `591481f`, but the code it imports has (`llm/providers/`, `config/settings.py`,
       `agent/graph.py`). Find where the time goes, `python -X importtime` first, and fix that;
       do not raise the timeout.
   - **Run 3's other jobs.** Run 3 goes on by itself and ends at about 14:00–14:30 UTC. Never stop
     it or the run queued behind it by hand ([ci_local's leftovers](#ci_locals-leftovers)). Read
     its other jobs before the rerun, and put any further failure into the same fix:
     - if the old session lived to the end, the `VERDICT:` line and the list above it at the end
       of `.tmp/cx-exec/ci-local-push3.log`;
     - else the logs on imac-julia, `~/ci_local/RAG_new_20261106-063247/state/logs/`. `jN_M.log` is
       job N, step M, and `plan.sh` there names the jobs.
   - **Who fixes.** Codex (cw) writes the fix in its package (Next action 2 names it). The session
     reviews the diff, runs the two tests and then the whole unit suite on the Mac, and commits.
   - **The rerun.** Run the full ci_local once, in the background, on a clean clone at the fix
     commit, not on `D:/RAG_new`. A run packs the working tree, untracked files included, and run 3
     packed `reports/ask100/`, the webm and this file's draft. `git clone D:/RAG_new D:/RAG_new_ci`,
     check out the fix commit, look at `ci_local.py --repo D:/RAG_new_ci --list` first, then run it
     without `--list`.
   - **The push.** It needs a PASS on that run, or INCOMPLETE with the uncovered steps named to
     her. It also needs both scans of the public repository, gitleaks and the shingle scan
     ([stage 8 runbook](stage8-publication-runbook.md) §6), and her yes, because the fix is outside
     her «пуш». Ask her one yes/no and name the fix. Then push the tested commit:
     `git -C D:/RAG_new -c credential.helper='!gh auth git-credential' push origin <tested sha>:master`.
     This handoff's commit rides along: it is an ancestor and `.md` only.
   - **After the push**, run `gh run list -R brownjuly2003-code/RAG_new -L 3`.
     - Green: `CURRENT_STATE.md` line 133, "Last green GitHub CI", gets that run and its commit,
       edited in place (the 150-line cap).
     - Every job failed in about 3 s: that is her GitHub billing, not the code. Tell her.
     - Red otherwise: read why before fixing.
1. **`PLAN.md`, one pass.** Mark each changed place «правка 06.11» and put her 11-06 words in
   verbatim.
   - **Stage 6, item 0.**
     - It calls her laptop "16 ГБ, только CPU". It has an Arc iGPU and an NPU; the memory is
       15.5 GB.
     - Add the local line: a small model for the helpers, later, on the iGPU or NPU, her word for each
       run.
     - Add «ничего не заводим».
   - **§8.3, item 15, the generator pilot.** Retarget it from the Mac's CPU to her laptop's helpers.
     Research 8's order, 0 → A → B → C, goes in as a proposal she has not chosen, and bundle A runs
     only on her word. The answer stays with Codex: a swap is her decision with numbers (§9), on
     the same 300 prompts against Codex's 2 bad answers of 300.
     - Research 8 was the search she asked for. Besides Qwen it weighed Gemma 4, LFM2.5 and LFM3,
       Phi-4-mini, Granite 4 and Llama 3.2. It did not cover entity extraction (the graph item
       below): add that role to the first laptop test.
   - **Stage 7, the graph lane: her words of 11:57 and 12:07, «нужно и графовый поиск включить»,
     «графовый поиск нужно включить».** Today it is off (`RAG_GRAPH_RETRIEVAL=off`, since GR-3),
     and stage 7 is closed. On 31.10 it ended «остаётся H», because the structural arm S lost
     gold in the sent context on the deciding bases, 125 → 99 of 180, a detected loss
     ([record](../evidence/stage7-step1-arms-record.md)). Her words reopen it. Write in her
     decision: graph search is turned on. That loss is the first defect to fix on the way, not a
     reason to keep H, and step 4 «Решение» no longer decides whether it goes on. The plan's
     conditions become the way there:
     - universality first: the structural graph finds links between documents by Russian words,
       entities are normalised by hand-made synonyms, and the web chat's stream calls hybrid
       search, not the graph;
     - the external bases need the entity graph, stopped on 29.10: extraction on the Mac's local
       model took 9.7 s a fragment, 25.1 h for MultiHop-RAG's 11,231 fragments, against the gate
       G2 of 24 h;
     - extraction is a batch job at indexing time, not part of an answer: a fourth role for a
       small local model, or Codex at a cost to its weekly window. Count that cost before choosing;
     - "on" means the chat's stream and `/api/ask` use it, proven by an E2E test, rule (a). The
       measurement on the same questions publishes its effect, rule (c). If the answers get worse,
       that is a defect of the route to fix, not a reason to leave it off; tell her the numbers.
   - **§9, "Смена модели".** Its state "решено 16.10: 4B" is stale: since 03.11 the product's model
     is Codex (stage 6 item 0).
   - **Stage 7's closed state, wherever it reads as final.** In `PLAN.md`: «Сейчас» (line 15 on),
     «Почему без графового поиска» (line 86), lines 971 and 983, step 4 «Решение» (her decision
     replaces the on-if-better rule) and §8.3 item 4 (line 1240). Also wherever `ROADMAP.md` and
     `CURRENT_STATE.md` call stage 7 closed; edit those in place (line caps). The 31.10 reads, the
     record and its spec stay as history: tests pin their sentences.
   - **Her 11-06 words verbatim in §8.1**, «В силе — слова Юли». The 90-s SLO in §8.3 item 2, as a
     proposal she has not answered.
   - **Stage 6, items 2, 4, 6 and 7 for the laptop.**
     - Item 2: is the qwen2.5:7b pin still read?
     - Item 4: throughput — a median of 66 s, and Codex's weekly window as computed above.
     - Item 6: the widget's «Обычно отвечаем в течение пары секунд» (`static/widget.html:377`) is
       false; it waits for the SLO.
     - Item 7: the E2E test against the running service, rule (a).
   - **Done:** `tests/test_docs_hygiene.py`, `tests/test_docs_quality.py` and
     `tests/test_docs_publication.py` pass on the Mac; one local commit; no push.
2. **Codex's runs into the repository, in the session that reads this: her words of 11:57 and
   12:07.** Why only half is recorded is in [Lessons](#lessons). The sources are intact, in three
   places:
   - The product's and the measurement's calls run `codex exec --ephemeral`, which leaves no Codex
     log. Their per-call files are in the private capture root `D:/RAG_new_codex_quality_private/`,
     1,952 calls: `attempt-01|03|04|05/capture/calls` and, for attempt-06, `capture/calls` (902).
     Each call has `start.json`, `end.json`, `spawned.json`, `alive.log` and `stdout.bin`. The usage
     in `stdout.bin` has `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`,
     `output_tokens` and `reasoning_output_tokens`.
   - Stage 5в's calls are committed with their tokens and timing:
     `reports/generator-ceiling/attempt-02/arm-*.json`.
   - The executor's and stage 5в's Codex tasks, and the window's `rate_limits`, are in Codex's
     logs, `%USERPROFILE%\.codex-work\sessions\YYYY\MM\DD\rollout-*.jsonl`, from 2026-06-09 on, for
     all her projects; `codex_sessions_by_cwd.py` picks RAG_new's by working folder.

   The quality side is there:
   - `reports/codex-only-quality/attempt-01…06`: per arm, chunks, stops, retries and routes, and
     the judge's grade per question;
   - `reports/generator-ceiling/`, stage 5в;
   - the [record](../evidence/codex-only-quality-record.md) with its latency, and
     `EVIDENCE_INDEX.md` rows 53, 54 and 79.

   The cost side is not:
   - tokens per call (input, cached, output, reasoning) and each call's duration, except stage 5в's;
   - the weekly window's share per question (about 0.03 %), the capacity (about 3,000 questions a
     week), and the two times the window ran out (11-01, 11-05). Today these are only in this
     handoff;
   - the tools that computed them, `.tmp/cx-exec/codex_windows.py` and `codex_sessions_by_cwd.py`,
     are git-ignored.

   The work:
   - **What to make.** A numbers-only table from those three sources, one row per call: date,
     series, role where it can be told, model and effort, tokens, duration, and the window's
     percentage before and after where a Codex log gives it. Codex's runs as the executor, writing
     code since 10-30, go in marked as such. No paths: a call's working folder names her user.
     Then a short capsule in `docs/evidence/`, its test and one `EVIDENCE_INDEX.md` row, rule (c).
   - **So the next measurement is whole.** `_parse_answer` in `llm/providers/codex.py` keeps only
     `input_tokens` and `output_tokens`. Make it, and the measurement's export, keep every usage
     key.
   - **Who does what.** Codex (cw) writes the extractor on tracked files. The session runs it,
     because the capture files and the Codex logs hold external-base text; the brief names the
     keys, never their values. Before the commit, the session checks that the output holds numbers
     only: the repository is public.
   - **Codex's package** is `D:/RAG_new_cx/s1`. It sits at `5352d12`, a sync of `090dcd1`, with
     task s20's leftovers: `CX_REPORT.md` modified, `.cx_inputs/` and the record's two files
     untracked. Sync it to `HEAD` with a copy of the last per-task sync script,
     `.tmp/cx-exec/cx_sync_s20.py`, and apply Codex's diff with `.tmp/cx-exec/cx_apply_s1.py`.
     Start tasks with `--fresh` ([Do not](#do-not)); read
     `~/.claude/skills_cold/codex-cw-runner/SKILL.md` before the first one. Next actions 0, 3 and 4
     use the same package.
3. **Graph search on: the first slice.** Her decision, Next action 1. `PLAN.md` stage 7 and
   [the architecture note](../architecture/graph-search.md) describe the lane.
   - **Switches**, all off by default in `config/settings.py`: `MODEL_ROUTING_ENABLED`,
     `RAG_RETRIEVAL_STRATEGY` (`hybrid`; `graph` for the lane) and `RAG_GRAPH_RETRIEVAL` (`off`).
     The automatic mode stays off below `RAG_GRAPH_MIN_CHUNKS`, 20,000 chunks.
     `tests/test_graph_activation.py` pins the defaults, and the laptop's
     `deploy/windows/service.env.example` sets none of them. "On" for the product means either the
     service's environment or new defaults with that test changed.
   - **Order.** First the plumbing, which changes nothing while the switches are off: the chat's
     stream calls `session._retriever.get_relevant_documents` directly
     (`api/routers/conversation.py`, about line 2407), so make it and `/api/ask` go through the
     lane choice. Then the 31.10 loss: find why S lost 125 → 99 of 180 and fix it, with links
     between documents found without Russian words. Then the switches on, with an E2E test, rule
     (a), and the measured effect on the same questions, rule (c). Then entities without hand-made
     synonyms, and the entity graph for the external bases.
   - **Side effects to count.** Routing adds a classifier call, under `codex-only` a fourth Codex
     call per question. `_select_retrieval_strategy` (`agent/graph.py`, about line 1559) sends
     `simple` questions to vector-only search, not hybrid. Count the measurement's share of
     Codex's weekly window before the run ([Codex usage](#codex-usage-cw-from-the-rollouts)).
   - **Extraction** goes to the cheapest model that passes gate G2, 24 h for MultiHop-RAG's 11,231
     fragments: the laptop test (Next action 6), or Codex with its cost counted by Next action 2.
     `scripts/extract_graph_entities.py` offers only `mistral` and `ollama` today; Codex would need
     a provider there.
   - Codex (cw) writes the code in its package; the session reviews it, runs the Mac's gates and
     commits.
4. **Bundle 0, offline.** It loads nothing, so the count needs no word of hers.
   - **The count is preparation.** It becomes a slice only when a threshold replaces the grading
     call: an E2E test, rule (a), or a re-measured number, rule (c).
   - **Who does what.** Codex (cw) writes the script on tracked files. The session runs it, because
     the pools hold external-base text.
   - **Where to start.** A lead, unchecked: `reports/answer-prompt-v4/4f48fed/v4-*.cases.jsonl` carry
     a rerank-score field. Check first whether they hold a score per candidate and the gold.
5. **ci_local's cleanup: done in this session, check its first runs.** The session edited the tool
   itself, because it is outside the repository: `~/.claude/scripts/ci_local.py`, used by every
   project and not under git. The copy from before the edit is
   `.tmp/ci_local-fix/ci_local.py.orig-20261101`, git-ignored.
   - **What changed**, all in `LINUX_LAUNCHER`:
     - a function `kind_down` removes the containers labelled `io.x-k8s.kind.cluster`, retrying
       `docker rm -f` once;
     - it runs right after the colima start block, under the lock;
     - after `docker run` returns, the launcher removes the run's own directory in the VM,
       `colima ssh -p "$P" -- sudo rm -rf <run root>`, and calls `kind_down` again.
   - **Why that is safe.** Removing every kind cluster is the one exception to "only our own
     leftovers". The lock allows one linux run at a time, so under it any cluster is stale. The
     directory removed is only the run's own; other runs' directories are left alone, because a
     stale-lock takeover could leave an orphan container still using one.
   - **Checked.** `bash -n` passed on the rendered launcher, in Git Bash and in the iMac's bash
     3.2. The new commands ran dry on the iMac: `kind_down` with printing in place of removal, and
     `colima ssh … sudo rm -rf` on a path that does not exist (rc 0, no password prompt).
     `ci_local.py --repo D:/RAG_new --list` plans as before.
   - **Not yet exercised in a real run.** The first one is queued: `grafana-clickhouse-monitoring`'s
     linux run, started at 11:53, after the fix, waits for the VM behind run 3. It is another
     project's run: leave it alone. The cleanup prints nothing, so judge it by two things:
     - that run must not end with the launcher's infrastructure error (rc 4, a `state/infra` file in
       `%TEMP%/ci_local/grafana-clickhouse-monitoring_20261106-065335/`);
     - the next time a run has the VM up, its directory
       `/var/tmp/ci_local/grafana-clickhouse-monitoring_20261106-065335` must be gone, and no kind
       container older than the current run may be listed:
       `ssh imac-julia 'PATH=/usr/local/bin:$PATH; colima ssh -p ci-local -- ls /var/tmp/ci_local'` and
       `ssh imac-julia 'PATH=/usr/local/bin:$PATH DOCKER_HOST=unix://$HOME/.colima/ci-local/docker.sock docker ps -a --filter label=io.x-k8s.kind.cluster'`.

     Restore the copy only if the launcher itself fails, not if that project's own checks fail.
     That run also removes run 3's cluster.
6. **The laptop test of bundle A**, only on her word for that run, at a time she picks.
7. **This handoff's commit** goes with Next action 0's push, on her word for it.
   - It is `.md` only, so it needs no ci_local run of its own; the run on the fix commit covers it.
   - Push a commit, never `master` by name, unless
     `git -C D:/RAG_new diff --stat <tested sha> master -- . ':(exclude)*.md'` prints nothing: code
     from Next actions 2–4 needs its own full ci_local PASS first.

## Do not

- Start Ollama or any local model server on her laptop without her word for that run.
- Propose buying or opening accounts or subscriptions.
- Push without her word. The «пуш» of 11-06 covered `591481f..5995042` only.
- Stop run 3, or another project's run queued behind it, by hand (Next action 0).
- Push anything without a full ci_local PASS on the commit you push, both scans and her word.
- Clear the zombie companion job `task-mvxxv35t-nh4i5m`. It blocks `--resume-last`, so start Codex
  tasks with `--fresh`. Every handoff since 11-03 leaves it alone.
- Commit `demo/phase-e-raw.webm` or `reports/ask100/`: they are untracked and not this work's.
- Touch other projects' ci_local runs, containers or VMs. Remove only our own leftovers.

## State at the end

At the commit that adds this file, about 13:40 UTC:
- **ci_local run 3** (`RAG_new_20261106-063247`, log `.tmp/cx-exec/ci-local-push3.log`) started at
  11:33 with `--max-minutes 300`. It got the VM's lock at about 12:05, after another project's run.
  - `ci/helm`, its stale cluster removed at 11:45, passed, and so did `ci/lint` and `ci/type-check`.
  - `ci/test-unit (python-version=3.11)` installed the lock in 801 s on the freed disk, then failed
    at 13:13 in «Run unit tests»: 2 failed, 8,950 passed, 58 skipped, in 41 min 45 s. Both
    failures repeat on the Mac (Next action 0). The verdict will be FAIL: no stamp, no push.
  - At 13:20 the 3.13 unit job was running. The run ends by itself at about 14:00–14:30.
  - The old session's local process writes the `VERDICT:` line. If that session closes first, the
    run on imac-julia goes on, and its logs stay there (Next action 0).
  - Run 3 packed the working tree of 11:33. That tree also held the untracked
    `demo/phase-e-raw.webm` and `reports/ask100/`, which are not ignored, and this file's draft.
  - Run 3's helm job leaves a kind cluster again: its launcher was made at 11:33, before the fix.
    The next linux run removes it (Next action 5).
  - `grafana-clickhouse-monitoring`'s linux run waits for the VM behind run 3 (Next action 5).
- **The docs tests on the Mac passed** on this text before the commit; the counts are in the
  commit's message.
- **`origin/master`** is `591481f`. Local `master` is the commit that adds this file, on top of
  `5995042`; it goes with Next action 0's push.
- **The commit that adds this file** holds this handoff, research 8's folder and the
  `docs/README.md` and `CURRENT_STATE.md` links.
- **The old session's Codex broker** (`--cwd D:/RAG_new_cx/s1`, nine processes) was stopped at 12:42.
  A broker on that folder after that is yours.
- **Git-ignored tools** in `.tmp/cx-exec/`:
  - `codex_windows.py`: usage windows from the rollouts, numbers only;
  - `codex_sessions_by_cwd.py`: rollout counts by day and project;
  - `hw_info.ps1`: the laptop's CPU, memory, GPU and NPU;
  - `stop_my_broker.ps1`: how that broker was stopped, by its tree built child by child, never
    `taskkill /T`.

## Lessons

- **A model's cost is evidence too, not only its quality.** At 12:07 she asked why Codex's runs
  are recorded only by half. The reasons:
  - the measurement's spec registered quality and latency only, so its tools exported those;
  - the product's calls run `--ephemeral` and leave no Codex log. Their usage reached only the
    private capture files, and the export kept only quality and latency. Codex's own logs cover
    the executor and stage 5в. Both hold external-base text, so they cannot be committed as they
    are, and a numbers-only extractor was never written;
  - this session counted the window by hand to answer her, and left the count in this handoff and
    the scripts in `.tmp`. That was my omission: the count is evidence, so it belongs in the
    repository with its provenance.
- **Run the whole unit suite on the Mac before a full ci_local run.** It takes about 7 minutes,
  and it would have found both failures at 09:00. Instead, three ci_local runs took from 08:57 to
  13:13, and the first two failed on leftovers before they reached the tests. The focused gates of
  11-03…11-06 never ran these two tests.
- **ci_local does not clean up after actions.** A cluster or service an action starts outlives the
  run and the VM's restart. A failed helm job mid-run means the verdict is FAIL: stop and rerun.
- **A run stopped by hand leaves its directory in the VM.** Removing its runner container skips the
  container's cleanup, and the next run runs out of the VM's root disk. After such a stop, also
  remove `/var/tmp/ci_local/<name>_<run id>`: on imac-julia,
  `colima ssh -p ci-local -- sudo rm -rf /var/tmp/ci_local/<name>_<run id>` (PATH needs
  `/usr/local/bin`).
- **Read `rate_limits` before naming Codex's limits.** I told her there were five-hour and weekly
  windows; the rollouts show only the weekly one.
- **A question about buying or opening something wastes her one question.** «И с чего такой
  вопрос?» Look for efficiency first.
- **Subagents here cannot write files.** They return text, and the session saves it. Check the saved
  file against the hand-back text.

## Glossary

- **cw** — the Codex profile `CODEX_HOME=%USERPROFILE%\.codex-work`, the account shared by all her
  projects.
- **`codex-only`** — the product's profile on her laptop: every model call goes to Codex. BGE-M3
  embeddings and the ONNX reranker run locally.
- **Roles 1–3** — query transformation, batched document grading, the answer.
- **Bundles 0, A, B, C** — research 8's candidates for a first test.
- **iGPU, NPU** — the laptop's Arc graphics and its Intel AI Boost neural unit. Both share its memory.
- **kind, `chart-testing`** — Kubernetes in docker, and the cluster name `helm/kind-action` uses in
  `ci/helm`.
- **Stamp** — ci_local's record in `.git/ci_local/` of a full run that passed (PASS or INCOMPLETE). A
  push needs it, except for `.md`-only changes.

## Verification

- `git -C D:/RAG_new log --oneline -2` shows the commit that adds this file on top of `5995042`.
- After `git -C D:/RAG_new fetch origin`, `git -C D:/RAG_new log --oneline -1 origin/master` shows
  `591481f` until Next action 0's push.
- `ls D:/RAG_new/.git/ci_local/` holds no stamp newer than `91bf094…` (591481f's tree): run 3
  failed.
- `docs/operations/research-2026-11-06/` holds the brief, the report and the README.
