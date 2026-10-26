"""Detached supervisor of one live widget measurement on deproject-mac.

Copied from reports/stage1/tools/live_supervisor.py for stage 3, step 4
(docs/specs/widget-4b.md): its MODE prod only, the runner widget_runner.py (POST /api/ask),
and one name more, ENV. Names after CLIENT_CAP_SEC, each optional:
  TENANT=<id>        - the tenant the runner's token names (default aircargo);
  CHROMA=<abs path>  - VECTORDB_CHROMA_DIR, the index directory the API reads;
  CASES_FILE=<abs path> - the questions, JSON lines with case_id and query;
  ENV=production     - RAG_ENV=production. That mode refuses to start without explicit
               CORS_ORIGINS and an ADMIN_PASSWORD_HASH: the first is set to the stand's own
               address, the second to a bcrypt hash of a random secret made for this run and
               never written anywhere; the other secrets are env.json's. Without ENV the API
               runs with RAG_ENV unset, as every measured run did.
launch.json names the tenant, the index directory, the questions file, RAG_ENV, the names
this supervisor set for production (never their values) and the SHA-256 of the tools.

Usage: widget_supervisor.py LABEL prod CASES CLIENT_CAP_SEC [NAME=VALUE,...]
  prod       - the standard configuration: env.json supplies the deployment (database,
               secrets, index path), and every setting it moved off the code default
               is put back (STANDARD below: the code defaults of the workspace —
               since 468224b the 3,600-s ceiling and RAG_DEVICE=cpu); the model choice
               env.json makes (MODEL_CHOICE) is dropped and the code defaults choose it.
  CASES      - comma-separated case ids of the questions file.
  CLIENT_CAP_SEC - the client's limit per question; the runner stops the series at the
               first question that runs past it or delivers no response.

Reuses the ready index and the isolated test database of the ask100 snapshot through the
.ask100-runtime link; env.json is loaded into the API's environment, never printed.
Starts PostgreSQL on 55433 and the API on 8002, refuses to start when either port is
taken or Ollama already holds a model, and always stops what it started.
"""

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parent
RUNTIME = WS / ".ask100-runtime"
PY = "/Users/julia/RAG_Support_Assistant/.venv/bin/python"
SITE = "/Users/julia/RAG_new_mf_gate_site"
PG = Path("/usr/local/opt/postgresql@16/bin")
OLLAMA = "http://127.0.0.1:11434"
# Code defaults (config/settings.py, .env.example) that env.json overrides: since 468224b
# the three limits default to the 3,600-s ceiling and the device to the CPU.
STANDARD = {
    "REQUEST_TIMEOUT_SEC": "3600",
    "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
    "STREAMING_TIMEOUT_SEC": "3600",
    "RAG_DEVICE": "cpu",
}
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
# What chooses the model; env.json (the ask100 deployment) pins qwen2.5:7b.
MODEL_CHOICE = (
    "OLLAMA_MODEL_NAME",
    "OLLAMA_FAST_MODEL_NAME",
    "MODEL_ROUTING_ENABLED",
    "LLM_PROVIDER_PROFILE",
    "PROVIDER_REGISTRY_PATH",
)
TARGET = {"TENANT", "CHROMA", "CASES_FILE"}
TARGET_PATHS = {"CHROMA", "CASES_FILE"}
TOOLS = ("widget_supervisor.py", "widget_runner.py", "widget.sh", "widget_record.py", "live_api.py")
ORIGIN = "http://127.0.0.1:8002"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(args, timeout=60, env=None):
    return subprocess.run(
        [str(a) for a in args], capture_output=True, text=True, timeout=timeout, check=True, env=env
    ).stdout


def ollama(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        OLLAMA + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def port_free(port):
    import socket

    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def sample():
    vm = run(["/usr/bin/vm_stat"], timeout=10)
    pages = {k: int(v) for k, v in re.findall(r"^([^:]+):\s+(\d+)\.", vm, re.M)}
    swap = run(["/usr/sbin/sysctl", "-n", "vm.swapusage"], timeout=10).strip()
    procs = []
    busiest = []
    largest = []
    for line in run(["/bin/ps", "-axo", "pid,pcpu,rss,comm"], timeout=10).splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) != 4:
            continue
        row = [int(parts[0]), float(parts[1]), int(parts[2]) * 1024, parts[3][-40:]]
        if any(n in parts[3] for n in ("python", "ollama", "postgres", "llama")):
            procs.append(row)
        busiest.append(row)
        largest.append(row)
    busiest = sorted(busiest, key=lambda row: row[1], reverse=True)[:5]
    largest = sorted(largest, key=lambda row: row[2], reverse=True)[:5]
    load = run(["/usr/sbin/sysctl", "-n", "vm.loadavg"], timeout=10).strip()
    return {
        "at": now(),
        "monotonic": time.monotonic(),
        "free_pages": pages.get("Pages free"),
        "inactive_pages": pages.get("Pages inactive"),
        "swapins": pages.get("Swapins"),
        "swapouts": pages.get("Swapouts"),
        "swap": swap,
        "loadavg": load,
        "procs": procs,
        "busiest": busiest,
        "largest": largest,
    }


def production(env):
    """RAG_ENV=production and the two names that mode needs; returns the names it set."""
    import bcrypt

    env["RAG_ENV"] = "production"
    env["CORS_ORIGINS"] = ORIGIN
    env.pop("ALLOW_DEV_ADMIN_LOGIN", None)
    made = ["RAG_ENV", "CORS_ORIGINS"]
    if not env.get("ADMIN_PASSWORD_HASH"):
        secret = secrets.token_urlsafe(32).encode()
        env["ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(secret, bcrypt.gensalt()).decode()
        made.append("ADMIN_PASSWORD_HASH")
    return made


def main():
    label, mode, cases, cap = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    extra = dict(item.split("=", 1) for item in sys.argv[5].split(",")) if len(sys.argv) > 5 else {}
    assert re.fullmatch(r"[a-z0-9-]+", label) and mode == "prod"
    assert float(cap) > 0
    assert set(extra) <= TARGET | {"ENV"}
    assert extra.get("ENV", "production") == "production"
    assert all(
        re.fullmatch(r"[A-Za-z0-9:._-]+", v) for k, v in extra.items() if k not in TARGET_PATHS
    )
    assert all(
        re.fullmatch(r"/Users/julia/[A-Za-z0-9._/-]+", v) and ".." not in v and Path(v).exists()
        for k, v in extra.items()
        if k in TARGET_PATHS
    )
    # A directory without a database is opened as a new empty one: the API answers from
    # nothing and writes into the folder (2026-10-18).
    assert "CHROMA" not in extra or (Path(extra["CHROMA"]) / "chroma.sqlite3").is_file()
    rag_env = extra.pop("ENV", None)
    target = {name: extra.pop(name) for name in TARGET if name in extra}
    tenant = target.get("TENANT", "aircargo")
    out = HERE / "runs" / label
    out.mkdir(parents=True, exist_ok=False)
    launch = {
        "label": label,
        "mode": mode,
        "cases": cases.split(","),
        "client_cap_sec": cap,
        "started": now(),
        "supervisor_pid": os.getpid(),
        "workspace": str(WS),
        "code_sha": (WS / "CODE_SHA").read_text(encoding="utf-8").strip(),
        "overrides": STANDARD,
        "model": MODEL,
        "tenant": tenant,
        "rag_env": rag_env,
        "production_names_set": [],
        "chroma_dir": target.get("CHROMA", "env.json"),
        "cases_file": target.get("CASES_FILE", "evaluation/curated_cases_aircargo.jsonl"),
        "tools_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in TOOLS
        },
    }
    save(out / "launch.json", launch)
    chosen = {"CHAT_TENANT": tenant}
    if "CHROMA" in target:
        chosen["VECTORDB_CHROMA_DIR"] = target["CHROMA"]
    if "CASES_FILE" in target:
        chosen["CHAT_CASES_FILE"] = target["CASES_FILE"]
    stop = threading.Event()

    def monitor():
        with (out / "resources.jsonl").open("a", encoding="utf-8") as fh:
            while not stop.is_set():
                try:
                    fh.write(json.dumps(sample()) + "\n")
                except Exception as exc:
                    fh.write(json.dumps({"monitor_error": type(exc).__name__}) + "\n")
                fh.flush()
                stop.wait(3)

    api = None
    pg_started = False
    exit_code = 2
    loaded_models = []
    try:
        for port in (8002, 55433):
            if not port_free(port):
                raise RuntimeError(f"port {port} is taken; refuse a competing run")
        prior = [m.get("name") for m in ollama("/api/ps").get("models", [])]
        launch["ollama_models_before"] = prior
        if prior:
            raise RuntimeError("Ollama already holds a model; refuse a competing run")
        threading.Thread(target=monitor, daemon=True).start()

        env = json.loads((RUNTIME / "env.json").read_text(encoding="utf-8"))
        env.update(
            {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/Users/julia"),
                "PYTHONPATH": f"{WS}:{SITE}",
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "CHAT_RUN_DIR": str(out),
                "TRACING_DB_PATH": str(out / "traces.db"),
                "CHAT_IDLE_LIMIT_SEC": "600",
                **STANDARD,
                **chosen,
            }
        )
        for name in MODEL_CHOICE:
            env.pop(name, None)
        env.pop("RAG_ENV", None)
        if rag_env == "production":
            launch["production_names_set"] = production(env)
        launch["model_digest"] = next(
            (
                m.get("digest")
                for m in ollama("/api/tags").get("models", [])
                if m.get("name") == MODEL
            ),
            None,
        )
        if not launch["model_digest"]:
            raise RuntimeError(f"Ollama does not hold {MODEL}")

        pg_env = {**os.environ, "LC_ALL": "C"}
        run(
            [PG / "pg_ctl", "-D", RUNTIME / "postgres", "-l", out / "postgres.log", "-w", "start"],
            timeout=60,
            env=pg_env,
        )
        pg_started = True
        launch["db_tickets_before"] = run(
            [
                PG / "psql",
                "-X",
                "-A",
                "-t",
                "-h",
                "127.0.0.1",
                "-p",
                "55433",
                "-U",
                "julia",
                "-d",
                "ask100",
                "-c",
                "SELECT count(*) FROM escalated_tickets;",
            ],
            env=pg_env,
        ).strip()

        with (out / "api.log").open("w") as log:
            api = subprocess.Popen(
                [PY, "-u", str(HERE / "live_api.py")],
                cwd=WS,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        launch.update(api_pid=api.pid, status="starting_api")
        save(out / "launch.json", launch)
        deadline = time.monotonic() + 240
        while True:
            if api.poll() is not None:
                raise RuntimeError(f"API exited during startup with {api.returncode}")
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:8002/api/health/live", timeout=2
                ) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("API not live within 240 s")
            time.sleep(1)
        launch.update(status="api_ready", api_ready=now())

        # The served model stays resident between questions, as Ollama keeps it in
        # service; its cold load is timed here, apart from the questions.
        started = time.monotonic()
        ollama("/api/generate", {"model": MODEL, "keep_alive": "30m"}, timeout=300)
        launch["ollama_load_sec"] = round(time.monotonic() - started, 3)
        save(out / "launch.json", launch)

        with (out / "progress.log").open("w") as log:
            runner = subprocess.Popen(
                [PY, "-u", str(HERE / "widget_runner.py"), cases, cap],
                cwd=WS,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            launch.update(runner_pid=runner.pid, status="running")
            save(out / "launch.json", launch)
            exit_code = runner.wait()
        launch["ollama_models_after"] = [m.get("name") for m in ollama("/api/ps").get("models", [])]
        launch["db_tickets_after"] = run(
            [
                PG / "psql",
                "-X",
                "-A",
                "-t",
                "-h",
                "127.0.0.1",
                "-p",
                "55433",
                "-U",
                "julia",
                "-d",
                "ask100",
                "-c",
                "SELECT count(*) FROM escalated_tickets;",
            ],
            env=pg_env,
        ).strip()
        launch.update(status="complete" if exit_code == 0 else "failed", runner_exit=exit_code)
    except Exception as exc:
        launch.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        if api is not None and api.poll() is None:
            api.terminate()
            try:
                api.wait(timeout=15)
            except subprocess.TimeoutExpired:
                api.kill()
                api.wait()
                launch["api_killed"] = True
        if pg_started:
            try:
                run(
                    [PG / "pg_ctl", "-D", RUNTIME / "postgres", "-w", "stop", "-m", "fast"],
                    timeout=60,
                    env={**os.environ, "LC_ALL": "C"},
                )
            except Exception as exc:
                launch["pg_stop_error"] = f"{type(exc).__name__}: {exc}"
        try:
            for model in ollama("/api/ps").get("models", []):
                name = model.get("name")
                if name not in launch.get("ollama_models_before", [None]):
                    ollama("/api/generate", {"model": name, "keep_alive": 0}, timeout=30)
                    loaded_models.append(name)
        except Exception as exc:
            launch["unload_error"] = f"{type(exc).__name__}: {exc}"
        launch["unloaded_models"] = loaded_models
        stop.set()
        launch["finished"] = now()
        save(out / "launch.json", launch)
        print("LIVE_DONE", label, launch.get("status"), "exit", exit_code, flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
