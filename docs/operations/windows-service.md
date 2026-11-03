# The chat on the Windows 11 laptop

The owner's 16 GB laptop runs Python 3.11, PostgreSQL 16 and native Codex with the
owner's signed-in profile. The Mac and Linux CI run tests; the [Mac service](macos-service.md)
remains a draft. The laptop reaches OpenAI directly; the Mac needs a VPN that disrupts
another project. **The chat answers only while the laptop, API and PostgreSQL are running.**
Sleep and shutdown interrupt availability. The laptop uses `codex-only`: never run Ollama
for this product. Embedding and ONNX reranking remain local and do not use Ollama.

## Runtime layout

All four helpers in `deploy/windows/` accept `--root` (default `D:/RAG_new_prod`).
Product paths derive from that root; the external env file and installed binaries/profile
are exceptions. The service runs only from the release copy, never a development checkout.

| Purpose | Default path or address |
| --- | --- |
| Release copy: plain local Git clone, detached at the release commit | `D:/RAG_new_prod/app/` |
| Python 3.11 venv, installed from the release's `deploy/windows/requirements-win.lock` | `D:/RAG_new_prod/venv/` |
| Aircargo data, embedding manifest and sidecars | `D:/RAG_new_prod/data/aircargo/` |
| Writable index, including `chroma.sqlite3` | `D:/RAG_new_prod/data/aircargo/index/chroma/` |
| Measured INT8 reranker | `D:/RAG_new_prod/ort/bge-reranker-v2-m3/int8/model.onnx` |
| Offline Hugging Face cache (`HF_HOME`) | `D:/RAG_new_prod/hf/` |
| Own PostgreSQL 16 cluster; role `rag_app`, database `rag_new` | `D:/RAG_new_prod/pgdata/`, `127.0.0.1:55432` |
| PostgreSQL log | `D:/RAG_new_prod/pg.log` |
| Generated secrets, user-only ACL | `D:/RAG_new_prod/secrets/pg.json`, `D:/RAG_new_prod/secrets/service.json` |
| External env file | `%LOCALAPPDATA%/rag-new/chat-service.env` |
| Launcher/API log; trace database | `D:/RAG_new_prod/service.log`; `D:/RAG_new_prod/traces.db` |
| API and chat | `http://127.0.0.1:8002` |

## First install and release changes

Run these commands as the owner in PowerShell. Python 3.11, PostgreSQL 16 binaries,
native Codex and its signed-in profile must already exist. No helper installs software,
downloads model files or logs in to Codex.

1. Create the Python 3.11 venv. Populate it from the release's Windows lock after
   selecting the release in step 2. The release contains
   `deploy/windows/requirements-win.lock`, generated with
   `python deploy/windows/make_win_lock.py` before the release commit.

   ```powershell
   $productRoot = 'D:/RAG_new_prod'
   $developmentRepo = 'D:/RAG_new'
   $releaseCommit = 'FULL_RELEASE_COMMIT'
   py -3.11 -m venv "$productRoot/venv"
   ```

2. Make a plain local release clone (not a worktree or symlink). Select a committed
   release containing these helpers; uncommitted development changes are not copied.

   ```powershell
   git clone --no-hardlinks "$developmentRepo" "$productRoot/app"
   git -C "$productRoot/app" checkout --detach "$releaseCommit"
   git -C "$productRoot/app" rev-parse HEAD
   & "$productRoot/venv/Scripts/python.exe" -m pip install --require-hashes -r "$productRoot/app/deploy/windows/requirements-win.lock"
   ```

   After each `requirements.lock` change, regenerate from the development repository
   root with `python deploy/windows/make_win_lock.py` (requires uv and network access;
   optional `--uv-cache-dir D:/RAG_new_prod/uv-cache`). It constrains Windows/Python 3.11
   to the Linux versions, prints counts/platform-only packages/version differences,
   and fails on any shared-package version difference. Temporary constraints are removed;
   the lock header contains only the repository-relative generator command. Review and
   include the generated lock in the release. The Mac lock test requires SHA-256 hashes
   for every pin and equal versions in both locks; it skips only while the file is absent.

   For a new release, first stop the launcher/API as below. Check
   `git -C "$productRoot/app" status --short` is empty; preserve unexpected changes.
   Set `$releaseCommit` to the new full commit, run `git -C "$productRoot/app" fetch origin`
   (origin is the local development repository), then `checkout --detach` and `rev-parse`
   as above. Install that release's lock with `--require-hashes` if dependencies changed;
   for an exact dependency reset, recreate the stopped product's venv. Rerun env writing,
   start, readiness and smoke checks. Data and secrets stay beside `app/`.
3. Copy the approved Aircargo dataset to `data/aircargo/`, including a consistent
   `index/chroma/`, embedding manifest and sidecars. Stop the source index while copying
   or use a consistent snapshot. The recorded laptop index had 5,589 chunks; WixQA and
   ConditionalQA remain on the Mac. The launcher's presence check prevents an accidental
   empty index, but does not prove contents or completeness.
4. Copy the measured ONNX file to `ort/bge-reranker-v2-m3/int8/model.onnx`. Verify with
   `Get-FileHash -Algorithm SHA256 "$productRoot/ort/bge-reranker-v2-m3/int8/model.onnx"`:
   `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`.
5. Copy prepared HF snapshots to `hf/`. Under `hf/hub/`, `BAAI/bge-m3` snapshot beginning
   `5617a9f6` includes weights; `BAAI/bge-reranker-v2-m3` snapshot beginning `953dc6f6`
   includes tokenizer/config (ONNX supplies weights). Preserve blobs, snapshots, refs
   and link targets. `HF_HOME` must exist. Startup forces `HF_HUB_OFFLINE=1` and
   `TRANSFORMERS_OFFLINE=1`; a live smoke question must check cache completeness.
6. Create/start the own PostgreSQL 16 cluster; the system PostgreSQL service is untouched:

   ```powershell
   & "$productRoot/venv/Scripts/python.exe" -I "$productRoot/app/deploy/windows/prepare_postgres.py" --root "$productRoot"
   ```

   `--pg-bin` defaults to `C:/Program Files/PostgreSQL/16/bin`. Cluster, role and database
   are created only when missing; `secrets/pg.json` is reused and the app login checked.
   An existing cluster without its secrets store refuses; restore the store first.
7. Write the external env file. `--admin-username` has no default and is required when
   `secrets/service.json` does not exist. With an existing store, the argument is ignored
   and the stored admin username and credentials are retained.

   ```powershell
   & "$productRoot/venv/Scripts/python.exe" -I "$productRoot/app/deploy/windows/write_env.py" --root "$productRoot" --admin-username '<admin-name>'
   ```

   `--codex-exe` supplies a native `.exe`; otherwise the glob
   `%APPDATA%/npm/node_modules/@openai/codex/**/codex.exe` must match exactly one file.
   Zero/multiple matches refuse; npm's `.cmd` shim is unsupported. `--codex-home` defaults
   to `%USERPROFILE%/.codex-work`. Use the existing signed-in profile; do not copy its
   credentials (refresh-token rotation can invalidate another copy).
   `--env-file` overrides the default; pass the same override to `run_detached.py`.
   Secrets are generated once, secured with `icacls` and reused. The stored admin password
   is bcrypt-hashed; the writer validates with the launcher and prints key names only.
   No password is an argument or printed. [service.env.example](../../deploy/windows/service.env.example)
   is a format reference, not an install-ready file.
8. Start the release, wait for readiness after cold startup, then ask an indexed question:

   ```powershell
   & "$productRoot/venv/Scripts/python.exe" -I "$productRoot/app/deploy/windows/run_detached.py" --root "$productRoot"
   Invoke-RestMethod 'http://127.0.0.1:8002/api/health/ready'
   & "$productRoot/venv/Scripts/python.exe" -I "$productRoot/app/deploy/windows/smoke_ask.py" --root "$productRoot" 'В какой срок нужно сдать авансовый отчёт после возвращения из командировки?' --tenant aircargo
   ```

   `GET /health` returns 404. Under `codex-only`, readiness and `/api/health` inspect Codex
   binary/home configuration without calling a model; they do not prove login or remote
   availability. Smoke reads the admin password from `secrets/service.json`, never prints
   it, reports `seconds`, `answer_provider`, `answer_model`, `route`, `ticket_id`,
   `delivery_state` and `quality_score` (API null under `codex-only`, printed as `None`),
   and exits nonzero on a non-200 login or ask. Inspect metadata: a 200
   alone is not proof of an automatic Codex answer. The detached helper prints a PID,
   not a readiness claim.

## Daily start and stop

Run `prepare_postgres.py`, `run_detached.py`, then readiness above. The launcher command is
`<root>/venv/Scripts/python.exe -I <root>/app/deploy/windows/start.py`, cwd `<root>/app`;
logs append to `service.log`. Both `pg_ctl` and the launcher use the laptop-proven
`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` flags plus `CREATE_BREAKAWAY_FROM_JOB`,
with no `STARTUPINFO`. On `OSError`, they retry without breakaway, retaining the two base
flags. This is the combination verified on the laptop against `0xC0000142` when a temporary
parent console closes; do not use `-NoNewWindow`. `start.py` itself does not start or
reconfigure PostgreSQL.

Stop only the launcher and its uvicorn child by verified PID. Inspect
`Get-CimInstance Win32_Process` for `ProcessId`, `ParentProcessId`, `ExecutablePath` and
`CommandLine`: confirm this release's launcher and its uvicorn `api.app:app` child (the
venv may add a Python redirector between them). Record both PIDs first. Set `$launcherPid`
and `$uvicornPid` to those verified numbers, then:

```powershell
Stop-Process -Id $uvicornPid
# Recheck the launcher's identity if it has not already exited with uvicorn.
Stop-Process -Id $launcherPid -ErrorAction SilentlyContinue
& 'C:/Program Files/PostgreSQL/16/bin/pg_ctl.exe' -D "$productRoot/pgdata" stop -m fast
```

The launcher normally exits after uvicorn; recheck identity before stopping a remaining
PID. Confirm the API port is no longer listening. Never use `taskkill /T`: process-tree
termination can reach other sessions' processes. Never kill by image name.

## Launcher contract and routing

The launcher requires the `<product root>/app` layout: the checkout directory must be
named `app`. Any other name refuses with exit code 2 and a layout diagnostic before
reading the env file or creating directories. Runtime data stays in the checkout's
parent (`DATA = ROOT.parent`); run the launcher only from the release copy.

The launcher accepts at most one env-file argument. It must be absolute and resolve outside
the checkout, including through symlinks. UTF-8 without BOM, LF and unquoted `KEY=VALUE`
are required: no `export`, padding, duplicates, unknown keys or `<placeholders>`. User-only
Windows ACLs protect secrets; POSIX `chmod 600` is not a Windows access check. The writer
percent-encodes URL credentials and sets these allowed keys except optional `AUTO_MIGRATE`:
`DATABASE_URL`, `VECTORDB_CHROMA_DIR`, `RAG_RERANKER_ONNX`, `JWT_SECRET`, `SESSION_SECRET_KEY`,
`DB_ENCRYPTION_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `ADMIN_DEFAULT_TENANT`,
`CORS_ORIGINS`, `AUTO_MIGRATE`, `LLM_PROVIDER_PROFILE`, `CODEX_BINARY`, `CODEX_HOME`, `HF_HOME`.

The Mac's production secret, bcrypt, index and streaming SHA-256 checks are reused.
JWT/session secrets need at least 32 characters; encryption needs 16. Development defaults
are refused; an absent/empty session secret falls back to JWT. Required keys are the Mac's
required deployment keys plus `HF_HOME`; Codex paths are required for `codex-only` and
`codex-answer`, and checked when supplied for `local-first`. Pre-flight checks the free
port, PostgreSQL `SELECT 1` (up to 60 seconds) and `Settings.validate()`. With `codex-only`,
neither pre-flight nor settings validation probes Ollama. One uvicorn worker listens on
`127.0.0.1:8002`; its exit code is forwarded. Exit 2 is a configuration refusal; exit 1 is
a dependency pre-flight failure. Only the failed check name is logged, never env values or
exception payloads. The API inherits `USERPROFILE` for Chroma's `Path.home()`.

Quality/model/timeout settings keep code defaults; inherited tuning, shell env files and
`.ask100-runtime/env.json` are discarded. `RAG_ENV` keeps its code default but production
secret rules apply. `RAG_SERVICE_MEMORY_POLICY` and `RAG_SERVICE_OLLAMA_LOG` are refused.
The switch accepts `local-first|codex-answer|codex-only`; omission means `local-first`,
but this laptop must use `codex-only`.

Task 18: an error-free Codex answer with retrieval context and no knowledge gap routes
`auto` and the chat offers **«Передать оператору»**. Codex outage, no context, fewer than
two documents, a knowledge gap or an error routes `human`; `/api/ask` opens a ticket.
Response safety keeps its veto. There is no retry or fallback model. `quality_score` is
null and the chat shows no quality badge. Online quality judges, claim-verification
telemetry, suggestions and continuation self-evaluation are disabled. Document grading
uses one batch and fails closed if it cannot grade the batch.

`answer_provider=codex` / `answer_model=gpt-6-astra` identify the subscription answer.
The final answer uses `xhigh` and the stage 5v wrapper; auxiliaries use `low` with 60-second
timeouts. Timeout, login/connectivity/usage failure, invalid stream, tool/warning item,
invalid binary or Job Object failure rejects the result: no partial answer escapes.
Failed answers have null provider/model. The 300-second outage cache prevents repeated
answer attempts; auxiliary failures are cached separately from the longer answer target.
After expiry a later request may try again. `codex-answer` retains local auxiliaries/4B
fallback and `local-first` remains the default; neither is the laptop profile.

Each Windows Codex child starts in a new process group and is assigned to an unnamed Job
Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Success, failure and timeout terminate
the job and close its handle, ending assigned descendants even after the leader exits.
Isolation failure refuses the call; an unassigned child is killed directly. Other Codex
sessions and Ollama are never targeted. The child receives only `PATH`, `SystemRoot`,
`CODEX_HOME`, `TEMP` and `TMP` when present.

Known task 18 limitation: `UnverifiedAutoResponse` in `monitoring/alert_rules.yml` would
count every codex-only auto answer as unverified. No Prometheus runs on the laptop;
the monitoring rule has not been changed.

## Optional autostart at logon

After a successful manual start, the owner may create a Task Scheduler task for her own
account: **At log on**, **Run only when user is logged on**. Program: venv `python.exe`;
arguments: `-I`, quoted `start.py` and optional env-file paths; **Start in**:
`D:/RAG_new_prod/app`. Choose **Do not start a new instance**; the launcher refuses an
occupied port. Start detached PostgreSQL first, or use a logon delay and bounded restart
policy for dependency failures. Do not run as SYSTEM: the owner holds the Codex login.
No helper creates a scheduled task, service, firewall rule or power policy. Autostart is
optional and cannot keep a sleeping or powered-off laptop online.
