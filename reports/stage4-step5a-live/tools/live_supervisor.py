"""Detached supervisor of one live chat measurement on deproject-mac.

Copied from reports/chat-live-4b/19beeb1/tools for the stage-1 audit (PLAN.md stage 1, items
1 and 3): one question per tenant through /api/ask/stream, the external bases' tenants
included. Three more names after MODE, each optional:
  TENANT=<id>        - the tenant the runner's token names (default aircargo);
  CHROMA=<abs path>  - VECTORDB_CHROMA_DIR, the index directory the API reads: each external
               base and each index generation sits in its own (default: env.json's, the
               aircargo index of the ask100 runtime);
  CASES_FILE=<abs path> - the questions, JSON lines with case_id and query (default
               evaluation/curated_cases_aircargo.jsonl).
launch.json names the tenant, the index directory and the questions file.

Usage: live_supervisor.py LABEL MODE CASES CLIENT_CAP_SEC [SETTING=VALUE,...]
  MODE prod  - the standard configuration: env.json supplies the deployment (database,
               secrets, index path), and every setting it moved off the code default
               is put back (STANDARD below: the code defaults of the workspace —
               since 468224b the 3,600-s ceiling and RAG_DEVICE=cpu);
  MODE floor - the same, with the request, stream and Ollama limits raised to 1800 s
               only to measure how long a complete answer takes on this machine;
  MODE dump  - write the effective settings of MODE prod and stop (starts nothing).
  MODE retrieval - retrieval alone (live_retrieval.py) in MODE prod settings, once per
               device placement in RETRIEVAL_VARIANTS (or in the comma list of the
               environment variable LIVE_VARIANTS, each optionally with "-b<N>"), with
               no model in Ollama and no API or database started; CLIENT_CAP_SEC bounds
               each placement.
  CASES      - comma-separated case ids of evaluation/curated_cases_aircargo.jsonl;
               "warmup:<question>" sends a synthetic question that is not in the set.
  CLIENT_CAP_SEC - the client's limit per question, or FIRST/REST (the first question of
               a fresh API, then the others). Julia's stop rule (2026-10-15): 3x each
               question's named forecast; the runner stops the series at the first
               question that runs past it.
  SETTING=VALUE - a deployment setting applied after MODE; only DEPLOYMENT names are
               allowed (on this Mac RAG_DEVICE=auto puts the reranker on the 4 GB GPU
               next to the embedder, where it fails with MPS out of memory: run B1).
  MODEL=<tag>  - serve another local model, for the measurement only: the API gets
               OLLAMA_MODEL_NAME (the stream's generation and self-evaluation) and a
               copy of config/providers.yml whose local-first profile and Ollama
               defaults name it (PROVIDER_REGISTRY_PATH, the graph's calls); the code
               defaults stay. Default qwen3:4b-instruct-2507-q4_K_M, the model of the
               code defaults since step 4: without MODEL= the model choice env.json
               makes (MODEL_CHOICE) is dropped and the code defaults choose it.

Reuses the ready index and the isolated test database of the ask100 snapshot through the
.ask100-runtime link; env.json is loaded into the API's environment, never printed.
Starts PostgreSQL on 55433 and the API on 8002, refuses to start when either port is
taken or Ollama already holds a model, and always stops what it started.
"""

# stage4-step1: begin
# fmt: off
# Stage 4, step 1 (docs/specs/stage4-step1-rerank-memory.md): a copy of V4's driver,
# reports/stage1/tools/live_supervisor.py (32e5a405...), run from $S/step1 beside V4's
# live_api.py. The lines marked "stage4-step1" are its changes; without the two names below
# it runs as the original ("fmt: off" keeps the original's layout, so only they differ):
#   ARM=<A or B for each case, in order> - step 1's arm of each question, kept in launch.json
#                for live_runner.py: A, the model stays resident; B, it is unloaded before
#                the question, so retrieval runs with no model and the answer's call loads it;
#   RAG_RETRIEVAL_TOP_K=<1-99> - a DEPLOYMENT setting, the rerank's candidates (step 3).
# stage4-step1: end
# stage4-step5a-live: begin
# Stage 4, item 5a's short live series (docs/specs/stage4-step5a-live.md): a copy of step 1's
# copy, reports/stage4-step1/tools/live_supervisor.py (915ffa9e...), run from $S/live5a beside
# V4's live_api.py and step 1's live_runner.py. The lines marked "stage4-step5a-live" are its
# changes; without the two names below it runs as step 1's:
#   RAG_RERANKER_RUNTIME=<torch or onnx> - a DEPLOYMENT setting, the reranker's runtime
#                (PLAN.md stage 4, item 5a), read once by the API's process;
#   RAG_RERANKER_ONNX=<abs path> - a DEPLOYMENT setting, the ONNX file the onnx runtime loads:
#                a file under the Mac user's home, given with onnx and only with it.
# stage4-step5a-live: end
import json
import os
import re
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
STANDARD = {"REQUEST_TIMEOUT_SEC": "3600", "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
            "STREAMING_TIMEOUT_SEC": "3600", "RAG_DEVICE": "cpu"}
FLOOR_LIMITS = {"REQUEST_TIMEOUT_SEC": "1800", "STREAMING_TIMEOUT_SEC": "1800",
                "OLLAMA_REQUEST_TIMEOUT_SEC": "1800"}
DEPLOYMENT = {"RAG_DEVICE", "RAG_RETRIEVAL_TOP_K", "RAG_RERANKER_RUNTIME",  # stage4-step5a-live
              "RAG_RERANKER_ONNX"}  # stage4-step5a-live
DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
# What chooses the model; env.json (the ask100 deployment) pins qwen2.5:7b.
MODEL_CHOICE = ("OLLAMA_MODEL_NAME", "OLLAMA_FAST_MODEL_NAME", "MODEL_ROUTING_ENABLED",
                "LLM_PROVIDER_PROFILE", "PROVIDER_REGISTRY_PATH")
RETRIEVAL_VARIANTS = ("auto", "cpu", "rerank-mps", "embed-mps")
# The stage-1 names: the tenant, and two absolute paths under the Mac user's home.
TARGET = {"TENANT", "CHROMA", "CASES_FILE"}
TARGET_PATHS = {"CHROMA", "CASES_FILE", "RAG_RERANKER_ONNX"}  # stage4-step5a-live


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(args, timeout=60, env=None):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          timeout=timeout, check=True, env=env).stdout


def ollama(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(OLLAMA + path, data=data,
                                     headers={"Content-Type": "application/json"})
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
    return {"at": now(), "monotonic": time.monotonic(), "free_pages": pages.get("Pages free"),
            "inactive_pages": pages.get("Pages inactive"), "swapins": pages.get("Swapins"),
            "swapouts": pages.get("Swapouts"), "swap": swap, "loadavg": load, "procs": procs,
            "busiest": busiest, "largest": largest}


def registry_for(model, out):
    """config/providers.yml with the local-first profile and Ollama's defaults on MODEL."""
    import yaml

    data = yaml.safe_load((WS / "config" / "providers.yml").read_text(encoding="utf-8"))
    provider = next(item for item in data["providers"] if item["id"] == "ollama")
    provider["default_models"] = {"fast": model, "strong": model}
    if all(item["name"] != model for item in provider["models"]):
        provider["models"].append({"name": model, "aliases": [],
                                   "input_price_per_1m_tokens": 0.0,
                                   "output_price_per_1m_tokens": 0.0})
    profile = data["routing_profiles"]["local-first"]
    profile["fast"]["model"] = profile["strong"]["model"] = model
    path = out / "providers.yml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def main():
    label, mode, cases, cap = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    extra = dict(item.split("=", 1) for item in sys.argv[5].split(",")) if len(sys.argv) > 5 else {}
    assert re.fullmatch(r"[a-z0-9-]+", label) and mode in ("prod", "floor", "dump", "retrieval")
    assert set(extra) <= DEPLOYMENT | {"MODEL", "ARM"} | TARGET  # stage4-step1
    assert all(re.fullmatch(r"[A-Za-z0-9:._-]+", v) for k, v in extra.items()
               if k not in TARGET_PATHS)
    assert all(re.fullmatch(r"/Users/julia/[A-Za-z0-9._/-]+", v) and ".." not in v
               and Path(v).exists() for k, v in extra.items() if k in TARGET_PATHS)
    # A directory without a database is opened as a new empty one: the API answers from
    # nothing and writes into the folder (2026-10-18, <base>/index named instead of
    # <base>/index/chroma, where scripts/production_index.py puts it).
    assert "CHROMA" not in extra or (Path(extra["CHROMA"]) / "chroma.sqlite3").is_file()
    model = extra.pop("MODEL", DEFAULT_MODEL)
    target = {name: extra.pop(name) for name in TARGET if name in extra}
    tenant = target.get("TENANT", "aircargo")
    # stage4-step1: begin
    arm = extra.pop("ARM", None)
    assert arm is None or (re.fullmatch(r"[AB]+", arm) and len(arm) == len(cases.split(","))
                           and mode in ("prod", "floor")), arm
    assert re.fullmatch(r"[1-9][0-9]?", extra.get("RAG_RETRIEVAL_TOP_K", "20"))
    # stage4-step1: end
    # stage4-step5a-live: begin
    runtime = extra.get("RAG_RERANKER_RUNTIME", "torch")
    assert runtime in ("torch", "onnx"), runtime
    assert (runtime == "onnx") == ("RAG_RERANKER_ONNX" in extra), runtime
    assert "RAG_RERANKER_ONNX" not in extra or Path(extra["RAG_RERANKER_ONNX"]).is_file()
    # stage4-step5a-live: end
    out = HERE / "runs" / label
    out.mkdir(parents=True, exist_ok=False)
    overrides = {**STANDARD, **(FLOOR_LIMITS if mode == "floor" else {}), **extra}
    launch = {"label": label, "mode": mode, "cases": cases.split(","), "client_cap_sec": cap,
              "started": now(), "supervisor_pid": os.getpid(), "workspace": str(WS),
              "code_sha": (WS / "CODE_SHA").read_text(encoding="utf-8").strip(),
              "overrides": overrides, "model": model, "tenant": tenant,
              "chroma_dir": target.get("CHROMA", "env.json"),
              "cases_file": target.get("CASES_FILE", "evaluation/curated_cases_aircargo.jsonl")}
    launch.update({"arm": arm} if arm else {})  # stage4-step1
    save(out / "launch.json", launch)
    chosen = {"CHAT_TENANT": tenant}
    if "CHROMA" in target:
        chosen["VECTORDB_CHROMA_DIR"] = target["CHROMA"]
    if "CASES_FILE" in target:
        chosen["CHAT_CASES_FILE"] = target["CASES_FILE"]
    if mode == "dump":
        env = json.loads((RUNTIME / "env.json").read_text(encoding="utf-8"))
        env.update({"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": os.environ.get("HOME", "/Users/julia"),
                    "PYTHONPATH": f"{WS}:{SITE}", "PYTHONUTF8": "1",
                    "PYTHONDONTWRITEBYTECODE": "1", "CHAT_RUN_DIR": str(out),
                    "TRACING_DB_PATH": str(out / "traces.db"), "CHAT_DUMP_ONLY": "1",
                    **overrides, **chosen})
        done = subprocess.run([PY, str(HERE / "live_api.py")], cwd=WS, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
        launch.update(status="complete" if done.returncode == 0 else "failed",
                      exit=done.returncode, finished=now())
        save(out / "launch.json", launch)
        print("LIVE_DONE", label, launch["status"], "exit", done.returncode, flush=True)
        return done.returncode
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
        env.update({"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": os.environ.get("HOME", "/Users/julia"),
                    "PYTHONPATH": f"{WS}:{SITE}", "PYTHONUTF8": "1",
                    "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                    "CHAT_RUN_DIR": str(out), "TRACING_DB_PATH": str(out / "traces.db"),
                    "CHAT_IDLE_LIMIT_SEC": "1800" if mode == "floor" else "600",
                    **overrides, **chosen})
        for name in MODEL_CHOICE:
            env.pop(name, None)
        if model != DEFAULT_MODEL:
            env.update({"OLLAMA_MODEL_NAME": model,
                        "PROVIDER_REGISTRY_PATH": str(registry_for(model, out))})
        launch["model_digest"] = next(
            (m.get("digest") for m in ollama("/api/tags").get("models", [])
             if m.get("name") == model), None)
        if not launch["model_digest"]:
            raise RuntimeError(f"Ollama does not hold {model}")

        if mode == "retrieval":
            variants = os.environ.get("LIVE_VARIANTS", ",".join(RETRIEVAL_VARIANTS)).split(",")
            pattern = "(" + "|".join(RETRIEVAL_VARIANTS) + r")(-b[1-9][0-9]?)?"
            assert all(re.fullmatch(pattern, v) for v in variants), variants
            launch.update(status="running", variants={}, variant_order=variants)
            save(out / "launch.json", launch)
            with (out / "progress.log").open("w") as log:
                for variant in variants:
                    try:
                        done = subprocess.run(
                            [PY, "-u", str(HERE / "live_retrieval.py"), variant, cases],
                            cwd=WS, env=env, stdin=subprocess.DEVNULL, stdout=log,
                            stderr=subprocess.STDOUT, timeout=float(cap))
                        launch["variants"][variant] = done.returncode
                    except subprocess.TimeoutExpired:
                        launch["variants"][variant] = "timeout"
                    log.write(f"VARIANT {variant} exit {launch['variants'][variant]}\n")
                    log.flush()
                    save(out / "launch.json", launch)
            launch["ollama_models_after"] = [m.get("name")
                                             for m in ollama("/api/ps").get("models", [])]
            exit_code = 0 if all(v == 0 for v in launch["variants"].values()) else 1
            launch.update(status="complete" if exit_code == 0 else "failed")
            return exit_code

        pg_env = {**os.environ, "LC_ALL": "C"}
        run([PG / "pg_ctl", "-D", RUNTIME / "postgres", "-l", out / "postgres.log", "-w", "start"],
            timeout=60, env=pg_env)
        pg_started = True
        launch["db_tickets_before"] = run(
            [PG / "psql", "-X", "-A", "-t", "-h", "127.0.0.1", "-p", "55433", "-U", "julia",
             "-d", "ask100", "-c", "SELECT count(*) FROM escalated_tickets;"], env=pg_env).strip()

        with (out / "api.log").open("w") as log:
            api = subprocess.Popen([PY, "-u", str(HERE / "live_api.py")], cwd=WS, env=env,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        launch.update(api_pid=api.pid, status="starting_api")
        save(out / "launch.json", launch)
        deadline = time.monotonic() + 240
        while True:
            if api.poll() is not None:
                raise RuntimeError(f"API exited during startup with {api.returncode}")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8002/api/health/live", timeout=2) as r:
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
        ollama("/api/generate", {"model": model, "keep_alive": "30m"}, timeout=300)
        launch["ollama_load_sec"] = round(time.monotonic() - started, 3)
        save(out / "launch.json", launch)

        with (out / "progress.log").open("w") as log:
            runner = subprocess.Popen([PY, "-u", str(HERE / "live_runner.py"), cases, cap],
                                      cwd=WS, env=env, stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=subprocess.STDOUT)
            launch.update(runner_pid=runner.pid, status="running")
            save(out / "launch.json", launch)
            exit_code = runner.wait()
        launch["ollama_models_after"] = [m.get("name") for m in ollama("/api/ps").get("models", [])]
        launch["db_tickets_after"] = run(
            [PG / "psql", "-X", "-A", "-t", "-h", "127.0.0.1", "-p", "55433", "-U", "julia",
             "-d", "ask100", "-c", "SELECT count(*) FROM escalated_tickets;"], env=pg_env).strip()
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
                run([PG / "pg_ctl", "-D", RUNTIME / "postgres", "-w", "stop", "-m", "fast"],
                    timeout=60, env={**os.environ, "LC_ALL": "C"})
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
