"""Mac: final-path answers in fresh batches, or a separate continuous speed series.

Only deployment keys survive the old ask100 env.json. The API, runner and frozen observers
use the service interpreter. This tool owns and cleans up only the children it starts.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from common import (
    HERE,
    MAX_REASK,
    MODEL_DIGEST,
    ONNX,
    PY,
    ROOT,
    SETTINGS,
    SITE,
    forecast,
    frozen,
    questions,
    read,
    require,
    sha,
    write,
)

IDLE_WAIT_SEC = 1800
UNLOAD_WAIT_SEC = 60


def foreign_jobs(sup, own_pids=()):
    # Inspect locally; retain pids, never command lines.
    jobs = []
    for line in sup.run(["/bin/ps", "-axo", "pid=,command="]).splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and int(fields[0]) not in own_pids:
            if re.search(
                r"pytest|llama-server|_supervisor|replay\.py|step[0-9]_|ngram_decode|limactl",
                fields[1],
            ):
                jobs.append(int(fields[0]))
    return jobs


def wait_idle(log, deadline, speed):
    end = min(deadline, time.monotonic() + IDLE_WAIT_SEC)
    readings = []
    while True:
        held = idle_check()
        readings.append(held)
        write(log, {"readings": readings})
        if not held["reasons"] or time.monotonic() >= end:
            break
        time.sleep(min(60, max(0, end - time.monotonic())))
    require(not speed or not held["reasons"], "Mac is still busy; read the wait log, start later")
    require("a model is resident" not in held["reasons"], "a model is resident; path cannot start")
    require(time.monotonic() < deadline, "3x series forecast during idle wait")
    return {**held, "busy": bool(held["reasons"]), "readings": readings}


def llama_pid(sampler):
    procs = sampler.sample(Path(sampler.LOG))["procs"]
    require(len(procs) == 1, "not one llama-server")
    return procs[0]["pid"]


def preload_gate(payload, models, window):
    require(payload.get("options", {}).get("num_ctx") == window, "preload lacks product num_ctx")
    require(len(models) == 1 and models[0].get("name") == payload["model"], "preload model differs")
    require(models[0].get("context_length") == window, "preload context_length differs")


def preload(sup, sampler, settings):
    window = settings["ollama_context_window"]
    require(window == SETTINGS["ollama_context_window"], "preload setting differs")
    payload = {
        "model": settings["ollama_model_name"],
        "keep_alive": "30m",
        "options": {"num_ctx": window},
    }
    started = time.monotonic()
    sup.ollama("/api/generate", payload, timeout=300)
    models = sup.ollama("/api/ps").get("models", [])
    preload_gate(payload, models, window)
    return {
        "ollama_load_sec": time.monotonic() - started,
        "preload": payload,
        "preload_models": models,
        "llama_pid": llama_pid(sampler),
    }


def unload(sup, sampler, model, log):
    end = time.monotonic() + UNLOAD_WAIT_SEC
    sup.ollama("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
    readings = []
    while True:
        models = sup.ollama("/api/ps").get("models", [])
        procs = sampler.sample(Path(sampler.LOG))["procs"]
        readings.append(
            {
                "at": sup.now(),
                "models": [m.get("name") for m in models],
                "pids": [p["pid"] for p in procs],
            }
        )
        write(log, readings)
        if not models and not procs:
            return
        require(time.monotonic() < end, "unload did not finish")
        time.sleep(min(1, max(0, end - time.monotonic())))


def api_environment(runtime, run, base, index, cases):
    sys.path.insert(0, str(ROOT))
    from deploy.macos.start import DEPLOYMENT_KEYS
    from deploy.macos.start import api_environment as service_env

    # env.json pins the old 7B and old ceilings: discard ALL non-deployment keys.
    deployment = {k: v for k, v in runtime.items() if k in DEPLOYMENT_KEYS}
    deployment.update(RAG_RERANKER_ONNX=ONNX, VECTORDB_CHROMA_DIR=str(index))
    env = service_env(deployment)
    env.update(
        PYTHONPATH=f"{ROOT}:{SITE}",
        CHAT_RUN_DIR=str(run),
        CHAT_TENANT="aircargo" if base == "aircargo" else "ext_" + base,
        CHAT_CASES_FILE=str(cases),
        TRACING_DB_PATH=str(run / "traces.db"),
    )
    return env


def idle(snapshot, models, locked, jobs, check_load=True, own_pids=()):
    load = frozen("sampler").parse_loadavg(snapshot["loadavg"])
    reasons = []
    if check_load and (load is None or load[1] >= 2):
        reasons.append("5-minute load is not below 2")
    if models:
        reasons.append("a model is resident")
    if locked:
        reasons.append("ci_local lock")
    if jobs:
        reasons.append("another job")
    for pid, _, rss, name in snapshot["procs"] + snapshot["largest"]:
        if pid in own_pids:
            continue
        if "python" in name.lower() and rss >= 512 * 2**20:
            reasons.append("large Python")
        if any(n in name.lower() for n in ("qemu", "limactl", "virtualization")):
            reasons.append("virtual machine")
    return sorted(set(reasons))


def idle_check(check_load=True):
    sup = frozen("supervisor")
    sample = sup.sample()
    # Command lines are inspected locally but never emitted. Do not stop another project.
    jobs = foreign_jobs(sup, (os.getpid(), os.getppid()))
    reasons = idle(
        sample,
        sup.ollama("/api/ps").get("models"),
        (Path.home() / "ci_local/.lock_ci-local").exists(),
        jobs,
        check_load,
        own_pids=(os.getpid(),),
    )
    return {
        "at": sup.now(),
        "reasons": reasons,
        "job_pids": jobs,
        "loadavg": sample["loadavg"],
        "swap": sample["swap"],
    }


def corpus(base, data):
    source = Path(data) / base
    arms = frozen("arms")
    require(sha(source / "chunks.json.gz") == arms.ARCHIVES[base], "corpus archive differs")
    common = __import__("stage2_common")
    held = {n: sha(source / n) for n in common.SOURCE_FILES}
    if base == "aircargo":
        live = __import__("common").load(
            "reports/stage4-step5a-live/tools/live5a_reader.py", "final_live5a"
        )
        require(held == live.CORPUS_SHA256, "aircargo generation differs")
    return held


def tree(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob("*")) if p.is_file()}


def code_check():
    held = read(ROOT / "STAND_FILES.json")
    require(held["code_sha"] == (ROOT / "CODE_SHA").read_text("utf-8").strip(), "stand SHA differs")
    require(bool(held["files"]), "empty stand manifest")
    require(
        all((ROOT / n).is_file() and sha(ROOT / n) == h for n, h in held["files"].items()),
        "stand file changed",
    )
    return held["code_sha"]


def terminate(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def batch(run, base, cases, ids, data, deadline, speed, before=None):
    sup, sampler = frozen("supervisor"), frozen("sampler")
    code = code_check()
    if before is None:
        before = wait_idle(run.parent / (run.name + "-idle-wait.json"), deadline, speed)
    require(all(sup.port_free(p) for p in (8002, 55433)), "a stand port is taken")
    run.mkdir(parents=True, exist_ok=False)
    write(run / "idle-before.json", before)
    generation = corpus(base, data)
    source, index = Path(data) / base / "index/chroma", run / "chroma"
    require((source / "chroma.sqlite3").is_file(), "no existing Chroma database")
    shutil.copytree(source, index)
    require(tree(source) == tree(index), "index copy differs")
    runtime = ROOT / ".ask100-runtime"
    env = api_environment(read(runtime / "env.json"), run, base, index, cases)
    launch = {
        "label": run.name,
        "code_sha": code,
        "tenant": env["CHAT_TENANT"],
        "model": SETTINGS["ollama_model_name"],
        "model_digest": MODEL_DIGEST,
        "cases": ids,
        "cases_file": str(cases),
        "cases_sha256": sha(cases),
        "chroma_dir": str(index),
        "corpus_sha256": generation,
        "index_sha256": tree(source),
        "started": sup.now(),
        "status": "starting",
        "ollama_models_before": [],
        "speed": speed,
        "busy": before["busy"],
        "exclusive_owned_work": speed,
        "supervisor_pid": os.getpid(),
    }
    write(run / "launch.json", launch)
    stop = threading.Event()

    def monitor():
        with (
            (run / "resources.jsonl").open("w", encoding="utf-8", newline="\n") as resources,
            (run / "samples.jsonl").open("w", encoding="utf-8", newline="\n") as samples,
        ):
            while not stop.is_set():
                try:
                    resource = sup.sample()
                    own = {
                        os.getpid(),
                        os.getppid(),
                        *(launch.get(k) for k in ("api_pid", "runner_pid", "llama_pid")),
                    }
                    resource["job_pids"] = foreign_jobs(sup, own)
                    resources.write(json.dumps(resource) + "\n")
                    samples.write(json.dumps(sampler.sample(Path(sampler.LOG))) + "\n")
                    resources.flush()
                    samples.flush()
                    checkpoint = run / "observation.tmp"
                    write(
                        checkpoint,
                        {
                            "monotonic": resource["monotonic"],
                            "resources": resources.tell(),
                            "samples": samples.tell(),
                        },
                    )
                    checkpoint.replace(run / "observation.json")
                except Exception:
                    launch["monitor_failed"] = True
                stop.wait(5)

    api = runner = None
    pg_started = model_owned = False
    monitoring = threading.Thread(target=monitor, daemon=True)
    pg_env = {**env, "LC_ALL": "C"}
    try:
        # Both children inherit ONLY the service recipe plus deployment/observation paths.
        sup.run(
            [
                sup.PG / "pg_ctl",
                "-D",
                runtime / "postgres",
                "-l",
                run / "postgres.log",
                "-w",
                "start",
            ],
            env=pg_env,
        )
        pg_started = True
        monitoring.start()
        with (run / "api.log").open("w", encoding="utf-8") as log:
            api = subprocess.Popen(
                [PY, "-u", str(HERE / "api.py")],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        launch["api_pid"] = api.pid
        write(run / "launch.json", launch)
        ready_by = min(deadline, time.monotonic() + 360)
        while True:
            require(api.poll() is None, "API failed its stand check or lifespan")
            try:
                import urllib.request

                with urllib.request.urlopen(
                    "http://127.0.0.1:8002/api/health/live", timeout=2
                ) as reply:
                    if reply.status == 200:
                        break
            except OSError:
                pass
            require(time.monotonic() < ready_by, "API startup cap")
            time.sleep(1)
        launch["api_ready"] = sup.now()
        model_owned = True
        launch.update(preload(sup, sampler, read(run / "effective_settings.json")["settings"]))
        write(run / "launch.json", launch)
        with (run / "progress.log").open("w", encoding="utf-8") as log:
            runner = subprocess.Popen(
                [PY, "-u", str(HERE / "runner.py"), ",".join(ids), str(deadline)],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            launch["runner_pid"] = runner.pid
            write(run / "launch.json", launch)
            launch["runner_exit"] = runner.wait(timeout=max(1, deadline - time.monotonic()))
        require(launch["runner_exit"] == 0, "batch path, question cap or stop file failed")
        from record import answer_run

        launch["llama_pid_after"] = llama_pid(sampler)
        require(launch["llama_pid_after"] == launch["llama_pid"], "llama-server pid changed")
        write(run / "launch.json", launch)
        answer_run(run, ids, completed=False, all_attempts=speed)
        # Re-check the whole recipe at the end, using the exact child environment.
        after = subprocess.check_output(
            [PY, str(HERE / "stand.py")], cwd=ROOT, env=env, text=True, timeout=180
        )
        write(run / "stand-after.json", json.loads(after))
        require(read(run / "stand-after.json") == read(run / "stand.json"), "environment moved")
        require(code_check() == code, "stand changed during batch")
        launch["status"] = "complete"
    except BaseException as error:
        launch.update(status="NOT_EVIDENCE", error_type=type(error).__name__)
        raise
    finally:
        terminate(runner)
        terminate(api)
        if pg_started:
            try:
                sup.run(
                    [sup.PG / "pg_ctl", "-D", runtime / "postgres", "-w", "stop", "-m", "fast"],
                    env=pg_env,
                )
            except Exception:
                launch["pg_stop_error"] = True
        if model_owned:
            try:
                unload(sup, sampler, launch["model"], run / "unload.json")
            except (Exception, SystemExit):
                launch["unload_error"] = True
        stop.set()
        if monitoring.ident is not None:
            monitoring.join(timeout=90)
            if monitoring.is_alive():
                launch["monitor_failed"] = True
        launch["finished"] = sup.now()
        if any(launch.get(k) for k in ("pg_stop_error", "unload_error", "monitor_failed")):
            launch["status"] = "NOT_EVIDENCE"
        write(run / "launch.json", launch)
        # Read again after all owned processes are gone; residual load is recorded too.
        write(run / "idle-after.json", idle_check(check_load=False))
        print("FINAL_DONE", run.name, launch["status"], flush=True)
    require(launch["status"] == "complete", "cleanup or monitor failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("answers", "speed", "idle"))
    parser.add_argument(
        "--base", choices=("aircargo", "wixqa", "conditionalqa", "multihoprag"), default="aircargo"
    )
    parser.add_argument("--data", type=Path, default=Path("/Users/julia/RAG_new_external_s1"))
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--exclusive-owned-work",
        action="store_true",
        help="all copies finished; only this run's owned processes on the Mac",
    )
    args = parser.parse_args()
    if args.mode == "idle":
        held = idle_check()
        print(json.dumps(held))
        require(not held["reasons"], "Mac is not idle")
        return
    require(args.out is not None and not args.out.exists(), "use a new OUT")
    cases, ids = questions(args.base, args.data)
    speed = args.mode == "speed"
    require(not speed or args.exclusive_owned_work, "confirm exclusive owned work before item 7")
    require(not speed or args.base == "aircargo", "item 7 is aircargo only")
    ids = ids[:30] if speed else ids
    batches = [ids] if speed else [ids[n : n + 10] for n in range(0, 100, 10)]
    seconds = forecast(len(ids), len(batches), MAX_REASK if speed else 0)
    deadline = time.monotonic() + 3 * seconds
    print("FORECAST", seconds, "seconds; stop", 3 * seconds, flush=True)
    for n, group in enumerate(batches, 1):
        require(not (args.out / "STOP").exists(), "operator stop")
        require(time.monotonic() < deadline, "3x series forecast")
        # A busy speed start leaves only this sibling log, never a run/launch.
        before = wait_idle(
            args.out.with_name(args.out.name + f"-b{n:02d}-idle-wait.json"), deadline, speed
        )
        batch(
            args.out / f"final-{args.mode}-{args.base}-b{n:02d}",
            args.base,
            cases,
            group,
            args.data,
            min(
                deadline, time.monotonic() + 3 * forecast(len(group), 1, MAX_REASK if speed else 0)
            ),
            speed,
            before=before,
        )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit("NOT_EVIDENCE: terminated"))
    main()
