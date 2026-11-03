# Session handoff — 2026-11-03 12:18 → ≈ 21:20 UTC: stage 5в recorded and pushed; D5 decided (Codex); the product moves to Julia's laptop, `codex-only`, no Ollama

## Read this first

- **Where we are.** All research stages are closed (0–5в, 7, 8). Only stage 6 is open: the
  chat runs as a product. This session decided its model and its host, both by Julia's word:
  - the answer comes from Codex (cw, `gpt-6-astra`) on her subscription;
  - the product runs on **her Windows laptop**, not on the Mac;
  - **no Ollama there**: every model call goes through Codex.
- **This is an exception to [`CLAUDE.md`](../../CLAUDE.md)'s «Nothing heavy on the Windows
  laptop»**, by her word «нужно делать все, значит, на этой машине». It covers the product and
  the measurements where Codex answers (OpenAI refuses the Mac). Tests still run on the Mac.
  CLAUDE.md, AGENT_STATE and PLAN item 0 say so since this session's last commit.
- **The code is written** by Codex in tasks 17, 17b, 17c and 17d and committed in `a8323be`.
  Its gate was **focused, not whole** (see *State at the end*): the whole unit suite, mypy,
  bandit, pip-audit and `ci_local` have not run on `a8323be`. They are due before any push.
  `codex-only` has not been live-tested on the laptop.
- **The first action of the next session** is the live run on the laptop with `codex-only`.
  The commands, the question and the stop rule are in *Next actions*.
- **Never start Ollama or any local LLM on the laptop.** On 2026-11-03 I did, through an
  `ollama pull` that auto-started the Ollama app. One answer took 1,090 s, the machine froze,
  and she had to kill Ollama herself.

## Julia's words in this session (UTC, verbatim)

- 12:18 «продолжи доработку» — stage 5в per the previous handoff.
- 17:08 «да» — push of 11 commits: `02b055a..591481f`. GitHub CI run 41681285267 passed
  11 of 11 jobs; Pages passed too.
- 17:56 «ты же про кодекс? а в чем именно вопрос???»
- 17:59 «бюджета нет. испольхуй астру xhigh через кодекс» — D5: Codex answers in the product.
- 18:32 «а зачем мак? почему нельзя тут?»
- 18:34 «да» — to running it on the Mac. From the Mac, OpenAI refuses unless a VPN is on, and
  the VPN breaks `hh.ru` (451) for another project of hers.
- 18:46 «нет, так не пойдет. нужно делать все, значит, на этой машине(» — the laptop is the host.
- 18:54 «продолжи».
- 20:04 «ollama на этой машине ты запустил?»; 20:13 «почему тебе нужна оллама, если кодекс
  используем. оллама переллизует работу этой машины((»; 20:14 «мне пришлось оллама убить»;
  20:15 «потому что иначе ничего не работает(((», «а зачем ты запустил оллама?» — no Ollama.
- 20:21 «может, стоит продолжить в новой сессии?» I advised finishing first; 20:38 she
  answered «конечно нужно завершить запущенные процессы». So this stop point let Codex
  finish, then stopped everything I started.
- 20:43 «есть шанс доделать проект?(((» — I answered yes. Only stage 6 is left, about
  2–3 sessions: the live run, a quality re-measurement on the new scheme, throughput, and
  the UI texts.

## What this session did

Commits in RAG_new, oldest first (times UTC):

| Commit | When | What |
| --- | --- | --- |
| `e166109` | 13:43 | Stage 5в: aircargo's judge exports and the reading |
| `591481f` | 14:10 | Stage 5в's record: the generator is the bottleneck (M1 120 → 220 of 224). Pushed. |
| `026ecf3` | 17:55 | CURRENT_STATE: last green CI is run 41681285267 |
| `6e0d980` | 18:06 | PLAN: D5 decided (Codex). Superseded in part by the laptop amendment below. |
| `a8323be` | 20:53 | Tasks 17, 17b, 17c, 17d: the provider, the profiles, the Windows launcher, the login fix |
| next commit | ≈ 21:20 | This handoff, PLAN, ROADMAP, CURRENT_STATE, AGENT_STATE, CLAUDE.md, docs/README.md: laptop, `codex-only`, no Ollama |

None after `591481f` is pushed.

Codex tasks: package `D:/RAG_new_cx/s1`, briefs in `D:/RAG_new_cx/briefs/`.

- **17** (`b6325c0` in s1):
  - provider `llm/providers/codex.py` runs `codex exec --json --ephemeral --sandbox read-only`,
    with 34 tool features disabled, a minimal environment and stdin input;
  - the gate accepts only `agent_message` and `reasoning` items;
  - stage 5в's wrapper `llm/codex_wrapper.txt` is byte-identical, sha `583b49ac…`;
  - profile `codex-answer`: only the answer goes to Codex, with the 4B as fallback;
  - the API reports `answer_provider` and `answer_model`;
  - Mac service keys.
- **17b** (`a2cd460`):
  - fixes a real defect: disabling `code_mode_host` made the CLI emit an `error` item, so the
    gate rejected every answer;
  - Windows support: a Job Object with KILL_ON_JOB_CLOSE, an environment allow-list, and an
    absolute `.exe` path (the npm `.cmd` shim cannot be spawned without a shell);
  - the launcher `deploy/windows/start.py` and `docs/operations/windows-service.md`.
- **17c** (`bcc5a07`):
  - profile `codex-only`: the answer at `xhigh`, the auxiliary calls at `low` with 60 s each;
  - judge, claim verification, suggestions and self-evaluation are off under this profile;
  - calls per question drop from 4–8 to 3 (simple) and 4 (complex);
  - a Codex failure gives an honest "unavailable" answer, with the 300-s outage cache;
  - no Ollama probe anywhere;
  - admin login fixed (below);
  - the launcher passes `USERPROFILE`;
  - fixes for the 10 Mac-gate failures of 17 + 17b, from two causes: the macOS temp path
    `/private/var` in `test_codex_provider.py`, and `RESULT_KEYS` in
    `test_stream_self_eval_continuation.py`.
- **17d** (`b209b41`): the environment assertion of `test_codex_provider.py` allows the keys
  `sh` and macOS add by themselves (`SHLVL`, `__CF_USER_TEXT_ENCODING`), and checks that a
  secret planted in the parent environment does not reach the child.

Defects found by the live run:

- **Admin login returned 500 on every platform.** passlib 1.7.4's bcrypt self-test hashes
  more than 72 bytes, and bcrypt 5.0.0 from the lock rejects that. Fixed with `bcrypt.checkpw`;
  passlib stays in the requirements, unused.
- **The launcher died at import** because `Path.home()` failed without `USERPROFILE`.

Live run 1, under `codex-answer` with Ollama on the laptop, question «В какой срок нужно сдать
авансовый отчёт после возвращения из командировки?» (tenant aircargo):

- 200, `answer_provider: codex`, `answer_model: gpt-6-astra`, `route: human`;
- 1,090 s in all, of which the online judge (`evaluate`) on the 4B took 331 s and ended with
  WinError 10054 when Ollama was killed;
- the answer was correct about the document: it said the deadline is a template placeholder.

`service.log` also warns that tenant `default` loaded an unstamped index (`NOT_EVIDENCE`) and
runs without BM25. Tenant aircargo, the one asked, restored its 5,589 chunks with BM25.

## Laptop product layout (outside the repo, `D:/RAG_new_prod`)

| Path | What |
| --- | --- |
| `venv/` | Python 3.11.13 (uv) from `locks/requirements-win.lock`, the Linux lock's versions, made by `locks/make_win_lock.py` |
| `data/aircargo/` | Copy of the Mac's `RAG_new_external_s1/aircargo`; the index is `data/aircargo/index/chroma` (5,589 chunks). The only index on the laptop: WixQA and ConditionalQA are on the Mac. |
| `ort/bge-reranker-v2-m3/int8/model.onnx` | sha `57335a9f…1343`, checked |
| `hf/` | `HF_HOME`; under `hf/hub/`: `bge-m3` snapshot `5617a9f6` in full; `bge-reranker-v2-m3` `953dc6f6`, tokenizer and config only (the ONNX file holds the weights) |
| `pgdata/` | Own PostgreSQL 16 cluster on 127.0.0.1:55432, role `rag_app`, database `rag_new`. The system PG service is untouched; its password is unknown. **Stopped at the stop point.** |
| `secrets/pg.json`, `secrets/service.json` | Generated passwords, user-only ACL. The admin login is `julia`. Never print them. |
| `%LOCALAPPDATA%/rag-new/chat-service.env` | The service env file, written by `setup/make_env.py`; profile `codex-only` |
| `setup/` | `pg_cluster.py` (create or start the cluster detached), `make_env.py`, `run_service.py` (start the launcher detached, log to `service.log`), `ask_live.py` (log in and run one `/api/ask`), `*_procs.ps1` (list processes) |

**The service runs from the dev checkout `D:/RAG_new`**: `run_service.py` starts
`deploy/windows/start.py` there, with `cwd` and `PYTHONPATH` on it. Keep the checkout on
committed `master` during a live run.

**`docs/operations/windows-service.md` describes another layout** (`app/`, `index/`,
`models/`, `hf-cache/`, `postgres/`, PostgreSQL 17). The real one is the table above. Align
the document with it (*Next actions*, 5).

Codex on the laptop:

- binary: `C:/Users/uedom/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe`
  (CLI 0.166.0);
- `CODEX_HOME=C:/Users/uedom/.codex-work`, shared with the executor. It is not copied:
  refresh-token rotation would break one of the copies.

The Ollama 4B model is still on disk (`C:/Users/uedom/.ollama`, 2.5 GB) but unused. Ollama is
not in autostart.

## My choices, not hers

- Profile `codex-only`:
  - auxiliary calls at effort `low`;
  - judge and suggestions off;
  - no local fallback.

  Why: her words exclude Ollama, and the product should answer in 1–2 minutes.
- **A consequence to decide by the product goal:** with the judge off, every answer routes
  `human` by design, so the UI shows «Маршрут: human» and escalates every answer. An operator
  queue that receives every answer is not a product. This is my decision to make, not hers
  (*Next actions*, 2).
- The figure of stage 5в (220 of 224) was measured with the old auxiliary steps.
  **A re-measurement is due**; it is not proven for `codex-only`.
- Questions and documents go to OpenAI, and the subscription has rate windows. She was told
  and accepted.
- The live run of `codex-only` is moved to the next session, at her stop point.

## Next actions (in order)

1. **Live run on the laptop.** No Codex executor task during it: both share `CODEX_HOME` and
   her rate windows. Bare `python` on the laptop is Anaconda 3.14; use the paths below.
   - Start PostgreSQL:
     `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I D:/RAG_new_prod/setup/pg_cluster.py`.
     It starts the existing cluster detached; a `pg_ctl` started inside the tool's console
     fails with 0xC0000142 once that console closes.
   - Start the service:
     `C:/Users/uedom/.venvs/rag_new-focused/Scripts/python.exe -I D:/RAG_new_prod/setup/run_service.py`.
     It prints the launcher's PID and logs to `D:/RAG_new_prod/service.log`.
   - Wait with one Monitor until-loop until
     `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8002/api/health/ready` gives
     `200`; `/health` returns 404. Read only the newest section of `service.log`: older
     sections hold old errors.
   - Check that no Ollama runs: `powershell -NoProfile -File D:/RAG_new_prod/setup/ollama_procs.ps1`
     must list nothing.
   - Ask the same question as run 1:
     `D:/RAG_new_prod/venv/Scripts/python.exe -I -X utf8 D:/RAG_new_prod/setup/ask_live.py "В какой срок нужно сдать авансовый отчёт после возвращения из командировки?"`
     (tenant aircargo by default). Run it in the background, once.
   - **Stop rule.** The forecast is 1–2 min: 3 Codex calls (the answer at `xhigh`, a median
     25.8 s in stage 5в), plus retrieval and the INT8 rerank on the CPU. At 3× the forecast,
     360 s, stop: the run is `NOT_EVIDENCE`, and the service is stopped before anything else.
   - Record: the time, `answer_provider` and `answer_model`, `route`, that no `ollama*`
     process appeared, and the CPU during the answer
     (`powershell -NoProfile -Command '(Get-CimInstance Win32_Processor).LoadPercentage'`).
   - **Stop the service by PID.** `powershell -NoProfile -File D:/RAG_new_prod/setup/service_procs.ps1`
     lists the candidates, but it also matches the focused venv's Pythons. Kill only the PIDs
     whose command line holds `deploy/windows/start.py` or `api.app:app`:
     `taskkill //PID <pid> //F`. Never `taskkill /T`.
   - Stop PostgreSQL:
     `"C:/Program Files/PostgreSQL/16/bin/pg_ctl.exe" -D D:/RAG_new_prod/pgdata stop -m fast`.
2. **The route under `codex-only`.** Find what sets it (17c: unmeasured quality routes to
   `human`) and choose by the product goal. Recommendation to try first: route on the signals
   that exist without the judge (retrieval scores, the answer's own refusal). A Codex task
   with an E2E test, so it counts by rule (a).
3. **Status docs.** Record the live result in PLAN stage 6, item 0, and in CURRENT_STATE. Add
   the stage 6 item 0 row to [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md), rule (a):
   `tests/test_codex_answer_e2e.py`, `tests/test_codex_only.py`, `a8323be`, the gate, the live
   run.
4. **Quality re-measurement under `codex-only`.** PLAN item 0 now allows measurements where
   Codex answers to run on the laptop (amended at this stop point). Only aircargo's index is
   here; WixQA and ConditionalQA are on the Mac. Write the spec first, with how those two
   bases get their contexts, and a cold read of it before any request.
5. **`windows-service.md`** aligned with the real layout (above).
6. Stage 6, the rest: throughput (questions per hour, a second client), the UI texts, the
   question log on her word.
7. **Push only on her word**, per
   [`stage8-publication-runbook.md`](stage8-publication-runbook.md) §6: gitleaks with
   `--log-opts="origin/master..master"`, the shingle scan over `origin/master..master`, and a
   full `ci_local` PASS — after the whole unit suite, mypy, bandit and pip-audit on the Mac.

**Executor procedure** (any Codex task):

- bring s1 to RAG_new's tracked files at `master` first, as a sync commit in s1 (as `2cc1199`
  did); s1's HEAD `b209b41` has the code of `a8323be` but none of the docs after it;
- read `~/.claude/skills_cold/codex-cw-runner/SKILL.md`, then run `.tmp/cx-exec/prep_cw.ps1`;
- the brief follows `D:/RAG_new_cx/briefs/s17d-env-assert.md`'s form and says «Do not run
  pytest here (tests run on the Mac); no network, no install, no commits»;
- launch with `--fresh`, in the background, once: the stale job `task-mvxxv35t-nh4i5m`
  blocks `--resume-last`;
- afterwards stop only my own broker, by PID (`setup/s1_broker_tree.ps1` lists it).

## Do not

- Start Ollama or any local LLM on the laptop. Run pytest on the laptop — tests go to the Mac
  (17c's executor ran 290 tests on the laptop, against this rule; say "no pytest here" in briefs).
- Push without her word; push `wip/*`.
- Put external-base data into s1.
- Commit `demo/phase-e-raw.webm` or `reports/ask100/`.
- Clear the stale companion job `task-mvxxv35t-nh4i5m`.
- Kill companion brokers by list. Broker 10312 (`--cwd D:/Auto_BI_new`) and its `codex.exe`
  belong to another project.
- Touch the system PostgreSQL service.
- Print credentials.

## State at the end

- **Stopped:**
  - PostgreSQL (`pg_ctl stop`);
  - the service;
  - Ollama (app and server);
  - my s1 brokers 8580 and 9508 and their trees, killed by PID.
- **Running:** nothing of mine.
- **Mac gate, focused:**
  - 17 + 17b: 380 passed, 10 failed (`.tmp/cx-exec/gate17.log`);
  - 17 + 17b + 17c: 514 passed, 1 failed, a macOS environment key in a test
    (`.tmp/cx-exec/gate17c.log`);
  - after 17d: `test_codex_provider.py`, `test_codex_only.py` and the three docs tests,
    114 passed; that output was not saved.
  - Not run on `a8323be`: the whole unit suite, mypy, bandit, pip-audit, `ci_local`.
- Local commits are not pushed.

## Lessons

- **A CLI can start a daemon.** `ollama pull` auto-launched the Ollama app and server.
- **Measure where the time goes before porting a scheme.** The 4B on the laptop's CPU cost
  minutes per call.
- **Servers started from the Bash tool must be detached.** Use CREATE_NO_WINDOW and break
  away from the job; otherwise new children fail with 0xC0000142.
- **Mocks hid a broken login.** Every login test mocked the hash check. 17c's test uses a
  real bcrypt hash.
- **A focused gate is not "green".** Say which files ran and what did not.

## Glossary

- **D5:** PLAN's decision on who answers in the product; decided this session: Codex.
- **5в (5v):** stage 5в, the generator's ceiling; "5v" in commit messages.
- **M1, M2:** the judge's measures. M1: an answer's grade (good, partial, bad). M2: agreement
  with the reference answer.
- **The 4B:** the local Ollama model `qwen3:4b-instruct-2507-q4_K_M`, the code's default for
  `local-first` on the Mac. Not on the laptop.
- **cw:** Julia's work Codex profile, `CODEX_HOME=C:/Users/uedom/.codex-work`.
- **`codex-answer`:** only the final answer goes to Codex; the rest runs on the 4B through
  Ollama, which is also the fallback. A Mac-era profile; do not use it on the laptop.
- **`codex-only`:** every model call goes to Codex; no Ollama.
- **Route:** the API's `route` field: `auto` answers the client, `human` hands the answer to
  an operator.
- **Base Python:** a venv's `python.exe` on Windows starts the base interpreter as a child, so
  each service process appears twice in a process list.
- **s1, the executor's package:** the copy of the repository's tracked files where Codex
  writes. Not to be confused with **the package** of stage 4 (K = 14, num_ctx 3,584, the
  cache cap, INT8), the production configuration.
- **Gate:** the Mac pytest run started from the laptop with `.tmp/mf-mac/sync.py` and
  `remote.py`.

## Verification

- Commits: `git log --oneline -8`.
- s1 commits: `b6325c0`, `a2cd460`, `bcc5a07`, `b209b41`.
- Gate logs: `.tmp/cx-exec/gate17.log`, `.tmp/cx-exec/gate17c.log`.
- Live run 1: `D:/RAG_new_prod/service.log`, from 19:56 to 20:14 UTC.
