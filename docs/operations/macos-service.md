# The chat as a macOS service

Status 2026-10-28: **a draft, nothing is installed.** [`PLAN.md`](../../PLAN.md) stage 6
(«Прод работает»), items 1–3. The service goes on the shared Mac only on Julia's word, and only
after stage 4 names the memory policy (stage 4, item 5). Its files are in
[`deploy/macos/`](../../deploy/macos/), and none of them has run on the Mac yet. The throughput
measurement it waits for is [`stage6-throughput.md`](../specs/stage6-throughput.md).

## What runs

- **A LaunchAgent of the Mac user `julia`,** `gui/<uid>/com.rag-new.chat`. It runs while she is
  logged in, like the dedicated PostgreSQL cluster's agent `com.rag-new.postgresql`
  ([its runbook](resolution-postgres-roles.md)).
- **What the agent starts:** [`start.py`](../../deploy/macos/start.py) checks everything, then
  replaces itself with `uvicorn api.app:app` on `127.0.0.1:8002`, one worker.
- **The code defaults:** the model `qwen3:4b-instruct-2507-q4_K_M`, the 3,600-s limits,
  `RAG_DEVICE=cpu` and `RAG_ENV` `development`. The stage-4 package defaults are
  `RAG_RETRIEVAL_TOP_K=14`, `OLLAMA_CONTEXT_WINDOW=3584`, `RAG_RERANKER_RUNTIME=onnx`;
  the kept count stays 5. See [configuration](../CONFIGURATION.md) for the measurement records.
  `.ask100-runtime/env.json` pins qwen2.5:7b, so it is never read (item 2).
- **The environment:** start.py builds the API's environment from nothing. It holds the user's
  `HOME`, `USER`, `LOGNAME` and `TMPDIR`, the stands' `PYTHONPATH`, and the deployment keys of
  one file outside the repository, `~/.config/rag-new/chat-service.env`. No value of that file
  is printed or put on a command line.
  It sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, using the cached models without fetching.
- **Why `RAG_ENV` stays at the default:** `production` is not only a deployment switch. It makes
  judge independence and the calibration artifact required (`config/settings.py`), which moves
  the answer path, and it makes the auth cookies Secure-only. start.py applies production's
  secret rules (SEC-02) itself.

**start.py's checks, in order.** A refusal exits 0, and launchd leaves the service stopped.
"Not up yet" exits 1, and launchd runs start.py again after 60 s (`ThrottleInterval`).

| Check | Fails as |
|-------|----------|
| The env file: present, mode 600, UTF-8 with LF ends, one `KEY=VALUE` a line with no quotes, each key listed in `service.env.example` and set once | refusal |
| `RAG_SERVICE_MEMORY_POLICY` is a policy the service can hold ([below](#the-memory-policy)) | refusal |
| Port 8002 is free | refusal |
| Every required key is set and no `<placeholder>` is left. `JWT_SECRET` and `SESSION_SECRET_KEY` have at least 32 characters and `DB_ENCRYPTION_KEY` at least 16, none of them a known dev default. `ADMIN_PASSWORD_HASH` is a bcrypt hash. The index directory holds `chroma.sqlite3` | refusal |
| `RAG_RERANKER_ONNX` names a file whose SHA-256 matches the measured INT8 export; hashed in 1 MiB chunks before any API start | refusal |
| PostgreSQL accepts the service's login (`SELECT 1`). The TCP wait is ≤ 120 s, and SQLSTATE `57P03` means starting up | not up yet; any other error is a refusal |
| Ollama answers and has the code default's model (nothing is loaded) | not up yet; a missing model is a refusal |
| `Settings.validate()` | refusal |

**What start.py writes to `chat-service.err.log`:** the code SHA, Ollama's version and the
policy; the names of the settings off the code default; the settings that set an answer's time,
as JSON. A failed start writes one line, `chat-service: refused: …` or `chat-service: not up
yet: …`. That line names the cause, never a value.

## Files

| In the repository | On the Mac |
|-------------------|------------|
| `deploy/macos/com.rag-new.chat.plist` | `~/Library/LaunchAgents/com.rag-new.chat.plist` (0644) |
| `deploy/macos/start.py`, `deploy/macos/healthcheck.py` | run from the release checkout `S=/Users/julia/RAG_new_service` |
| `deploy/macos/service.env.example` | copied to `~/.config/rag-new/chat-service.env` (0600) and filled in there |
| none | data: `~/.local/share/rag-new/chat-service/` (the index copy, `traces.db`) |
| none | logs: `~/Library/Logs/RAG_new/chat-service.out.log` and `.err.log` |

`PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` is the stands' interpreter (3.11). The
plist names it and `S`; another user or path means editing the plist.

## One measurement at a time

The Mac has 8 GB, and only one measurement runs on it at a time. The service sits on the stands'
port 8002 on purpose: a stand refuses to start while the service holds the port
(`live_supervisor.py`), and start.py refuses while a stand holds it. The port alone does not free
the memory, though. The API process stays resident, and after the last answer Ollama keeps the
model loaded until its keep-alive runs out. The API sets no keep-alive, so Ollama's own setting
rules: 5 minutes unless `ollama serve` runs with `OLLAMA_KEEP_ALIVE`. So the service **stops for
any measurement** on the Mac: stage 4's steps, stage 7, any stand ([below](#before-a-measurement)).
The only measurement it stays up for is its own throughput measurement.

## Before install

1. **Stage 4's word on the memory policy** and, for `cache-ram`, on the path that sets it.
2. **A release checkout** at one commit `C`, made from the laptop the way `raise_stand.sh` makes a
   stand (`reports/answer-prompt-v4/tools/raise_stand.sh`):

       git -C D:/RAG_new archive $C | ssh deproject-mac "test ! -e /Users/julia/RAG_new_service && mkdir /Users/julia/RAG_new_service && tar -x -C /Users/julia/RAG_new_service && echo $C > /Users/julia/RAG_new_service/CODE_SHA"

3. **The service's own copy of the index.** This is the aircargo index V4 and stage 4's step 0
   read (`index/index-receipt.json` `2dcc80e7…`). It is a copy because the API opens its index
   for writing:

       IX=/Users/julia/RAG_new_external_s1/aircargo; D=$HOME/.local/share/rag-new/chat-service
       mkdir -p $D/index; cp -Rp $IX/index/chroma $D/index/chroma; diff -rq $IX/index/chroma $D/index/chroma && echo same

4. **A database of its own (Julia's yes or no):** a role and a database in the dedicated cluster
   on 55432. That cluster is always on, and the agent waits for it after a login. Run psql as the
   cluster's bootstrap role, with its credential from `postgres-secrets.env` as the C8 runbook
   uses it:

       /usr/local/opt/postgresql@16/bin/psql -h 127.0.0.1 -p 55432 -U ragnew_bootstrap -d postgres
       CREATE ROLE ragnew_chat LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
       \password ragnew_chat
       CREATE DATABASE ragnew_chat OWNER ragnew_chat;

   The other databases do not fit:
   - `ragnew_prod`'s runtime role has only the Resolution grants, and that runbook does not switch
     the application's `DATABASE_URL`.
   - 55433 is the stands' isolated test database, which each stand starts and stops.
   - 5432 is not ours.

   As the owner, the role lets the API's start-up `alembic upgrade head` (`AUTO_MIGRATE`) create
   the tables and the `pgcrypto` and `btree_gist` extensions, both trusted in PostgreSQL 13+.
5. **The env file:**

       mkdir -p ~/.config/rag-new; cp /Users/julia/RAG_new_service/deploy/macos/service.env.example ~/.config/rag-new/chat-service.env; chmod 600 ~/.config/rag-new/chat-service.env

   Fill it in with an editor:
   - each secret from `$PY -c "import secrets; print(secrets.token_urlsafe(48))"`;
   - the login's hash from `$PY -c "import getpass; from passlib.hash import bcrypt; print(bcrypt.hash(getpass.getpass()))"`;
   - `DATABASE_URL` with the role's password, percent-encoded where needed.

   `RAG_RERANKER_ONNX` is a required deployment path, default empty in code. The example names
   `/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`. This 570858625-byte file is not
   in the repository; `reports/stage4-step5a/tools/export_onnx.py` made the measured export.
   start.py requires SHA-256 `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`
   from `reports/stage4-step5a/onnx/manifest.json`. Missing, unreadable or different files refuse
   startup. Install the pinned `onnxruntime==1.23.2` from the regenerated dependency lock.
   `RAG_RERANKER_RUNTIME` remains a quality setting and is not accepted in the service env file:
   this service runs the measured ONNX default. Outside this service, explicit
   `RAG_RERANKER_RUNTIME=torch` opts out of the measured package; no automatic fallback exists.

   **Keep `DB_ENCRYPTION_KEY` for the database's whole life.** Messages are stored encrypted with
   it (pgcrypto, `db/crypto.py`), and a new key leaves the old rows unreadable.

## Install

    mkdir -p ~/Library/Logs/RAG_new
    cp /Users/julia/RAG_new_service/deploy/macos/com.rag-new.chat.plist ~/Library/LaunchAgents/
    chmod 644 ~/Library/LaunchAgents/com.rag-new.chat.plist
    plutil -lint ~/Library/LaunchAgents/com.rag-new.chat.plist
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rag-new.chat.plist

The first start takes the API's ≈ 30 s plus the migrations of an empty database. The model loads
at the first question, ≈ 51 s in V4.

## Check

- `$PY -I /Users/julia/RAG_new_service/deploy/macos/healthcheck.py` prints one JSON object and
  exits 0 when the service answers. The object holds:
  - launchd's state, pid and last exit;
  - liveness (`/api/health/live`) and readiness (`/api/health/ready`), by component status only;
  - the questions in flight, the orphaned work and the refusals by reason (`/metrics`);
  - the models Ollama holds, the swap used, and under `cache-ram` the limit llama-server last
    reported.

  It requires readiness 200 with the index and pipeline loaded and `postgres` `ok`. A
  non-critical component in error (`sqlite`, `redis`) makes readiness `degraded` and is not
  required.
- `launchctl print gui/$(id -u)/com.rag-new.chat | grep -E "state =|pid =|last exit code ="`.
- `tail -n 40 ~/Library/Logs/RAG_new/chat-service.err.log`: start.py's lines, then
  `alembic upgrade head: OK` and uvicorn's start-up.
- **From the laptop:** `ssh -N -L 8002:127.0.0.1:8002 deproject-mac`. Then log in at
  `http://127.0.0.1:8002/static/login.html` with `ADMIN_USERNAME` and the password, and ask one
  question in `/static/chat.html`.

## Stop, start, restart

    launchctl bootout gui/$(id -u)/com.rag-new.chat                                  # stop
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rag-new.chat.plist   # start
    launchctl kickstart -k gui/$(id -u)/com.rag-new.chat                             # restart

- **Stopping:** `bootout` sends SIGTERM, and after 60 s (`ExitTimeOut`) SIGKILL. A question in
  flight is lost, so stop when healthcheck.py shows `inflight_pipelines` 0.
- **Logins and crashes:** a stopped service comes back at Julia's next login (`RunAtLoad`), and a
  process that dies is restarted.
- **After a refusal:** fix the cause and run `launchctl kickstart gui/$(id -u)/com.rag-new.chat`.

## Before a measurement

1. healthcheck.py shows `inflight_pipelines` 0; else wait.
2. `launchctl disable gui/$(id -u)/com.rag-new.chat; launchctl bootout gui/$(id -u)/com.rag-new.chat`.
   `disable` keeps it off across logins until `enable`.
3. Unload the model: `curl -s http://localhost:11434/api/generate -d '{"model":"qwen3:4b-instruct-2507-q4_K_M","keep_alive":0}'`.
   `curl -s http://localhost:11434/api/ps` then reads `{"models":[]}`.
4. `lsof -nP -iTCP:8002 -sTCP:LISTEN` prints nothing, and `pgrep -f "[l]lama-server"` finds no
   process. Then come the measurement's own idle checks.

**After it:** `launchctl enable gui/$(id -u)/com.rag-new.chat`, the `bootstrap` above, and
healthcheck.py.

## Remove

    launchctl bootout gui/$(id -u)/com.rag-new.chat; rm ~/Library/LaunchAgents/com.rag-new.chat.plist

This leaves the env file, the data, the logs and the database. Removing them is a separate
decision, and for the database it is Julia's word: `DROP DATABASE ragnew_chat; DROP ROLE
ragnew_chat;` as the bootstrap role.

## Upgrade

1. Stop the service.
2. Move the old checkout aside, and archive the new commit to the same path as in "Before install".
3. Start the service. The migrations run at the start.

The env file, the data and the database stay. Going back means putting the old checkout back,
but the migrations are not run backwards. Whatever the API writes under the checkout's `data/`
does not carry over (`Settings.data_dir` is fixed to it).

## What the service keeps

- **The service's database:** sessions, messages (questions and answers, encrypted) and audit
  rows such as logins.
- **The traces:** `traces.db`, the pipeline's steps, PII-redacted by `tracing/service.py`.
- **The logs:** `chat-service.out.log` and `.err.log`, not rotated.

Item 5's journal of questions without personal data is something else, switched on by Julia's
word. While only Julia uses the chat over the tunnel, what is kept is her own. If visitors come,
what the store keeps of them is part of item 5's word.

## The memory policy

Stage 4 names it (PLAN.md stage 4, item 5). On 8 GB the 4B's host prompt cache grows with each
request until the Mac swaps (stage 4, step 0). It is set by `RAG_SERVICE_MEMORY_POLICY` in the
env file:

| Value | start.py | Still to build |
|-------|----------|----------------|
| `undecided` (the template's) | refuses | nothing |
| `none` | starts | nothing; the cache may grow to llama.cpp's 8,192-MiB default |
| `cache-ram:<MiB>` | starts, and says whether `~/.config/llama.cpp/config.ini` sets `cache-ram = <MiB>`; the other of PLAN's two paths, `LLAMA_ARG_CACHE_RAM=<MiB>` in the environment of `ollama serve`, is not read (PLAN: `ps eww` is not needed). healthcheck.py proves the cap: it compares the limit llama-server reports in Ollama's log (`RAG_SERVICE_OLLAMA_LOG`) and is unhealthy when they differ | nothing in the service; the path is Julia's word, because Ollama is shared |
| `unload-every:<N>` | refuses: not built | sending Ollama `keep_alive: 0` after every N-th answer while nothing is in flight, from an API hook or a watcher beside the service |
| `unload-at-swap:<MB>` | refuses: not built | the same, when `vm.swapusage`'s used swap passes `<MB>` |

Each unload costs the next question the model's load, ≈ 51 s.

## The session store's guard (item 3)

`_TenantDbCooldown` in `api/app.py` closes a tenant's session store for `DB_COOLDOWN_SEC`
(60 s). A call fails when it raises or runs past `DB_PERSIST_TIMEOUT_SEC` (2 s; 0.5 s on the
history, list and delete routes). The calls it watches are the session lookup and insert, the
end-of-answer message write, and those routes.

While the store is closed, a caller's session id that is not in memory gets 503 «Session store
temporarily unavailable». A new visitor's server-made id falls back to memory instead.

Before this change, one failure was enough to close the store. Swap tripped it, because the 2 s
include the paging of PostgreSQL's and the API's pages, and the answer's write lands at the
memory peak. So did a restart: the browsers keep their session ids while the memory has lost
them, and the first call opens a cold connection.

Now the store closes only after `DB_COOLDOWN_FAILURE_THRESHOLD` (3) failures of a tenant in a
row, with no success between them:
- A failed call still fails its own request.
- A dead database closes the store from its third failure on.
- After the window, the next failure closes the store again.

The tests are in `tests/test_db_cooldown_failure_count.py`.

## Limits of this draft

- **Not run on the Mac:** plutil, launchctl, and the bcrypt and SQLAlchemy paths have not run
  there. A laptop check covered the env file's parsing, the
  refusals and healthcheck.py's readers.
- **Parity with the stands is unconfirmed.** The stands' API got env.json's keys without the
  model choice, plus the standard limits. Of the Settings fields, only `db_encryption_key`,
  `tracing_db_path` and `vectordb_chroma_dir` were off the default in the stand record
  (`reports/chat-live-4b/19beeb1/runs.json`). Variables outside Settings, such as a model
  cache's location or a thread count, are not compared. A names-only comparison on the Mac
  settles it.
- **A hang is not restarted.** launchd restarts a process that ends, not one that hangs:
  healthcheck.py shows a hang as liveness without 200, and nothing acts on it.
- **Other open points:** the logs are not rotated, and `ProcessType` `Interactive` has not been
  measured.
