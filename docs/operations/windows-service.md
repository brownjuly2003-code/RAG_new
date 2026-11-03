# The chat on the Windows 11 laptop

The owner's 16 GB laptop runs the product: Python 3.11, PostgreSQL,
and the native Codex CLI using the signed-in `C:/Users/uedom/.codex-work` profile.
The Mac and Linux CI run tests. The [Mac service](macos-service.md) remains a draft.
The Mac's OpenAI connection requires a VPN which disrupts another project; the laptop
can reach OpenAI directly. **The chat answers only while the laptop is on and the API,
and PostgreSQL are running.** Sleep and shutdown interrupt availability.
The laptop uses `codex-only`: Ollama is not needed and must not run for the product.
Embedding and ONNX reranking remain local; neither uses Ollama.

## Runtime layout

Keep production data separate from development checkouts. The deployment layout under
`D:/RAG_new_prod` is:

| Purpose | Path or address |
| --- | --- |
| Release checkout | `D:/RAG_new_prod/app` |
| Python 3.11 virtual environment | `D:/RAG_new_prod/venv` |
| Service's writable index copy | `D:/RAG_new_prod/index/chroma` (includes `chroma.sqlite3`) |
| Measured INT8 reranker | `D:/RAG_new_prod/models/bge-reranker-v2-m3/int8/model.onnx` |
| Prepared embedding and reranker tokenizer caches | `D:/RAG_new_prod/hf-cache` |
| PostgreSQL data | `D:/RAG_new_prod/postgres/data`, listening on `127.0.0.1:55432` |
| Service env file, using the explicit argument | `D:/RAG_new_prod/chat-service.env` |
| Default env file, when no argument is given | `%LOCALAPPDATA%/rag-new/chat-service.env` |
| Trace database | `D:/RAG_new_prod/traces.db` |
| API and chat | `http://127.0.0.1:8002` |

The launcher uses the interpreter that invokes it and derives the checkout from its own
location; it does not install a venv, copy data, download caches or initialize PostgreSQL.
Prepare those resources before first start. The index must be a separate, consistent copy
of the approved index, including its embedding manifest and sidecars. The presence check
prevents an accidental empty index; it does not prove the copy's contents or completeness.

## Configuration and first start

1. Place the release and its prepared Python environment at the paths above. Prepare the
   index, ONNX file, and complete Hugging Face snapshots for both the embedding model and
   reranker tokenizer. `HF_HOME` must be an existing absolute directory. Both
   `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are forced: missing cache files cannot
   be downloaded at startup. The orchestrator must verify cache completeness live.
2. Start the service's PostgreSQL cluster on port 55432, with its own database and login.
   Start it detached: run `pg_ctl` from a process with its own hidden console, as shown
   below. PostgreSQL is not started or reconfigured by the launcher.
3. Copy [service.env.example](../../deploy/windows/service.env.example) outside the checkout
   to `D:/RAG_new_prod/chat-service.env`, and fill it in with an editor. Use UTF-8 without
   BOM and LF line endings. Restrict its Windows ACL to the owner and necessary system
   administrators; POSIX `chmod 600` is not a Windows access check. No `export`, quotes,
   spaces around `=`, duplicate keys or `<placeholders>` are accepted. Password characters
   with URL meaning must be percent-encoded in `DATABASE_URL`. Generate independent random
   secrets; use a bcrypt password hash for the admin login.
4. For `codex-only`, set the existing native `.exe` path from the example and the absolute
   `CODEX_HOME` directory. The `codex` command on PATH is an npm `.cmd` shim and cannot be
   used. No shell is invoked. The launcher verifies the file and directory; it neither logs
   in nor reads credentials nor makes a Codex pre-flight request.
5. Start from a normal PowerShell terminal that stays open, or Task Scheduler, using the
   prepared environment:

   ```powershell
   & 'D:/RAG_new_prod/venv/Scripts/python.exe' -I 'D:/RAG_new_prod/app/deploy/windows/start.py' 'D:/RAG_new_prod/chat-service.env'
   ```

   Omit the final argument to use the default env location. More than one argument refuses
   startup. The env file must resolve outside the checkout, including through symlinks.
   The launcher checks deployment values, the free API port, a PostgreSQL `SELECT 1`
   (up to 60 seconds), Codex binary/home presence, and `Settings.validate()`.
   Under `codex-only` neither pre-flight nor settings validation probes Ollama.
   It starts `uvicorn api.app:app` on `127.0.0.1:8002` with exactly one worker as a child
   and forwards its exit code. Exit 2 means a launch/configuration refusal; exit 1 means
   a dependency pre-flight failed. No env-file values or exception payloads are logged;
   the failing check's name is reported. Fix the cause before restarting.

The explicit allowed keys are `DATABASE_URL`, `VECTORDB_CHROMA_DIR`, `RAG_RERANKER_ONNX`,
`JWT_SECRET`, `SESSION_SECRET_KEY`, `DB_ENCRYPTION_KEY`, `ADMIN_USERNAME`,
`ADMIN_PASSWORD_HASH`, `ADMIN_DEFAULT_TENANT`, `CORS_ORIGINS`, `AUTO_MIGRATE`,
`LLM_PROVIDER_PROFILE`, `CODEX_BINARY`, `CODEX_HOME`, and `HF_HOME`.

`JWT_SECRET` and `SESSION_SECRET_KEY` require at least 32 characters; `DB_ENCRYPTION_KEY`
requires at least 16. Known development defaults are refused by the shared production secret
rules. An absent/empty session secret uses the JWT secret, as in the Mac launcher. Required
keys are the Mac's required deployment keys plus `HF_HOME`; both Codex paths are additionally
required for `codex-only` and `codex-answer`, and checked whenever supplied with `local-first`.
The launcher imports the Mac's secret, bcrypt, index and streaming SHA-256 checks unchanged.
The required ONNX SHA-256 is:

```text
57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343
```

Every quality, model and timeout setting keeps its code default. Inherited tuning variables
are discarded; `.ask100-runtime/env.json` and shell env files are never loaded. The sole
provider switch is `LLM_PROVIDER_PROFILE=local-first|codex-answer|codex-only`; omission keeps
`local-first`. `RAG_ENV` keeps the code default, while production secret rules still apply.

There is no launchd or memory-policy key here. The laptop must use `codex-only`.
`RAG_SERVICE_MEMORY_POLICY` and `RAG_SERVICE_OLLAMA_LOG` are refused.

The API child also inherits `USERPROFILE`, required by `Path.home()` during Chroma imports.
Readiness is `GET http://127.0.0.1:8002/api/health/ready`; `GET /health` returns 404.
Under `codex-only`, readiness and `/api/health` report Codex binary/home configuration
without calling a model. This does not prove login or remote model availability.

Closing a temporary parent console can make PostgreSQL backends and similar children fail
with `0xC0000142`. Use a separate hidden console for `pg_ctl`, not `-NoNewWindow`:

```powershell
Start-Process -FilePath 'C:/Program Files/PostgreSQL/17/bin/pg_ctl.exe' -ArgumentList @('start', '-D', 'D:/RAG_new_prod/postgres/data', '-l', 'D:/RAG_new_prod/postgres/server.log', '-w') -WindowStyle Hidden -Wait
```

Adjust the installed PostgreSQL binary path. PowerShell starts this Windows console process
with its own console; its hidden console is independent of the terminal running this command.
The API launcher itself should run in a persistent normal terminal or Task Scheduler.

## Which model answered and how fallback works

Inspect `answer_provider` and `answer_model` in the chat API response (or its final streaming
result): `codex` / `gpt-6-astra` identifies the subscription answer. With `codex-only`, the
final answer uses `xhigh` and the unchanged stage 5v wrapper. Auxiliary calls use `low` with
a 60-second timeout each. Online quality judges, claim-verification telemetry, suggested
questions and continuation self-evaluation are disabled for this profile; unmeasured quality
never claims an auto route.
Document grading uses one batch and fails closed if that batch cannot be graded.

A timeout, login/connectivity/usage failure, invalid stream, tool or warning item, invalid
binary, or Job Object failure rejects the Codex result. No partial answer escapes the gate.
Under `codex-only` there is no fallback model. A failed answer returns the existing unavailable
answer with both `answer_provider` and `answer_model` null. The 300-second outage cache
prevents repeated answer attempts during that interval. Short auxiliary failures are cached
separately from the longer answer target. After expiry the next request may try again.
The older `codex-answer` profile retains local auxiliaries and its 4B fallback; `local-first`
remains the code default. These profiles are not the laptop deployment profile.

On Windows each Codex child starts in a new process group and is immediately assigned to an
unnamed Job Object configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. The job is terminated
and its handle closed after success, failure or timeout, ending assigned descendants even if
the leader already exited. Failure to set up isolation refuses the call; an unassigned child
is killed directly. Other Codex sessions and Ollama are never targeted. The child receives
only `PATH`, `SystemRoot`, `CODEX_HOME`, `TEMP` and `TMP` when present.

## Optional autostart at logon

After a successful manual start, the owner may create a Task Scheduler task for her own
Windows account with **At log on** and **Run only when user is logged on**. Use the venv's
`python.exe` as the program, `-I` followed by the quoted launcher and env-file paths as the
arguments, and `D:/RAG_new_prod/app` as **Start in**. Select **Do not start a new instance**;
the launcher also refuses an occupied port. Start the detached PostgreSQL cluster before this task,
or configure a logon delay and a bounded restart policy for dependency startup failures.
Do not run it as SYSTEM: the owner profile holds the Codex login.

The launcher creates no scheduled task, service, firewall rule or power policy. Task Scheduler
autostart is an optional owner action; it does not keep a sleeping or powered-off laptop online.
