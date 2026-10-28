"""Send chat questions through the web chat's path, POST /api/ask/stream, one at a time.

Copied from reports/chat-live-4b/19beeb1/tools for the stage-1 audit (PLAN.md stage 1, item
1): the tenant is CHAT_TENANT and the questions are CHAT_CASES_FILE (JSON lines with case_id
and query), both set by live_supervisor.py; before, both were aircargo's. The token names the
tenant: the stream route takes the tenant from it, not from the body.

Every SSE event is kept with the second it arrived. After each answer the runner waits
until the API reports no pipeline in flight, so measured requests never overlap.
The first real case without a delivered answer stops the run (the 1 -> 5 -> 100 gate);
warmup questions do not gate.
Usage (by live_supervisor.py): live_runner.py CASE_IDS_COMMA_SEPARATED CLIENT_CAP_SEC
CLIENT_CAP_SEC is one cap or FIRST/REST. A question that reaches its cap stops the series
(Julia's stop rule, 2026-10-15: the cap is 3x the question's named forecast).
"""

# stage4-step1: begin
# fmt: off
# Stage 4, step 1 (docs/specs/stage4-step1-rerank-memory.md): a copy of V4's driver,
# reports/stage1/tools/live_runner.py (fd5f7d7b...), started by this folder's
# live_supervisor.py. The lines marked "stage4-step1" are its changes; with no "arm" in the
# run's launch.json it runs as the original ("fmt: off" keeps the original's layout). With
# one, a letter a case, arm_action() below acts on Ollama before each question: A renews the
# resident model's keep-alive, B unloads it and waits until /api/ps is empty and ps lists no
# llama-server. The action's model names, counts and seconds go into the case file as
# "arm_action"; an action that fails stops the series with exit code 6, before the question
# is asked.
# stage4-step1: end
import json
import os
import re
import subprocess  # stage4-step1
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))
RUN = Path(os.environ["CHAT_RUN_DIR"])
API = "http://127.0.0.1:8002"
TENANT = os.environ.get("CHAT_TENANT", "aircargo")
CASES = Path(os.environ.get("CHAT_CASES_FILE", WS / "evaluation/curated_cases_aircargo.jsonl"))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def ask(question, cap_sec, token):
    # A new conversation's first question, as the web chat sends it: no session_id.
    payload = {"question": question, "tenant_id": TENANT}
    request = urllib.request.Request(
        API + "/api/ask/stream",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    row = {"started": now(), "events": [], "answer": ""}
    before = time.monotonic()
    row["t0_monotonic"] = before
    try:
        with urllib.request.urlopen(request, timeout=cap_sec) as response:
            row["http_status"] = response.status
            while True:
                remaining = before + cap_sec - time.monotonic()
                if remaining <= 0:
                    row["client_error"] = f"client cap {cap_sec}s reached"
                    break
                response.fp.raw._sock.settimeout(remaining)
                line = response.readline()
                if not line:
                    break
                if not line.startswith(b"data: "):
                    continue
                event = json.loads(line[6:])
                at = round(time.monotonic() - before, 3)
                kind = event.get("type")
                if kind == "token":
                    row["answer"] += event.get("token", "")
                    row.setdefault("first_token_sec", at)
                    row["last_token_sec"] = at
                    row["tokens"] = row.get("tokens", 0) + 1
                    continue
                row["events"].append({"at": at, **event})
                if kind == "result":
                    row["result_sec"] = at
                if kind == "error":
                    row["error_sec"] = at
    except Exception as exc:
        row["client_error"] = f"{type(exc).__name__}: {exc}"
    row["total_sec"] = round(time.monotonic() - before, 3)
    row["finished"] = now()
    return row


def answered(row, result):
    """Streamed tokens and a result event that is not a timeout, without any error."""
    return (row.get("tokens", 0) > 0 and "result_sec" in row and result.get("route") != "timeout"
            and "client_error" not in row and "error_sec" not in row)


def open_stages():
    """Stages started and not yet ended (a model call outlives a closed stream)."""
    balance = {}
    path = RUN / "stages.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            step = 1 if row["event"] == "start" else -1
            balance[row["stage"]] = balance.get(row["stage"], 0) + step
    return sorted(stage for stage, count in balance.items() if count > 0)


def drain():
    """Wait until no pipeline is in flight and no observed stage is still running."""
    limit_sec = float(os.environ.get("CHAT_IDLE_LIMIT_SEC", "600"))
    started = time.monotonic()
    while True:
        with urllib.request.urlopen(API + "/metrics", timeout=5) as response:
            text = response.read().decode("utf-8")
        match = re.search(r"^rag_inflight_pipelines ([0-9.eE+-]+)$", text, re.M)
        if match is None:
            raise RuntimeError("no rag_inflight_pipelines gauge; refuse unmeasured overlap")
        busy = open_stages()
        if float(match.group(1)) == 0 and not busy:
            return round(time.monotonic() - started, 3)
        if time.monotonic() - started > limit_sec:
            raise TimeoutError(f"still busy {limit_sec}s after the answer: {busy}")
        time.sleep(1)


# stage4-step1: begin
OLLAMA = "http://127.0.0.1:11434"
UNLOAD_LIMIT_SEC = 120  # B: how long a model or its process may outlast the unload
POLL_SEC = 0.5
PS = ("/bin/ps", "-axo", "pid=,rss=,comm=")  # step0_sampler.py's own listing


def ollama(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(OLLAMA + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def resident():
    """The names of the models Ollama holds."""
    return [model.get("name") for model in ollama("/api/ps").get("models", [])]


def llama_servers():
    """How many processes ps lists whose executable's base name is llama-server, as the
    sampler tells them (no path or argument is kept); a failed ps raises."""
    done = subprocess.run(PS, capture_output=True, text=True, timeout=20, check=True)
    rows = [line.split(None, 2) for line in done.stdout.splitlines()]
    return sum(1 for row in rows if len(row) == 3 and row[0].isdigit() and row[1].isdigit()
               and row[2].strip().rsplit("/", 1)[-1] == "llama-server")


def arm_action(arm, model):
    """Step 1's arm before a question; model names, counts and seconds only.

    A: the supervisor's own load request again, a no-op on a resident model that renews its
    30-min keep-alive, so the model stays resident through a retrieval however long, whatever
    keep-alive the server gives the product's calls (they send none). B: the served model is
    unloaded (keep_alive 0), then /api/ps and ps are read every POLL_SEC s until Ollama holds
    no model and no llama-server process is left, the process the reader's samples look for;
    another model is never unloaded, and Ollama holding one stops the series.
    """
    started = time.monotonic()
    action = {"arm": arm, "polls": 0}
    try:
        action["ps_before"] = resident()
        if arm == "A":
            ollama("/api/generate", {"model": model, "keep_alive": "30m"}, timeout=300)
            action["ps_after"] = resident()
        else:
            others = [name for name in action["ps_before"] if name != model]
            if others:
                raise RuntimeError(f"Ollama holds another model: {others}")
            if model in action["ps_before"]:
                ollama("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
            while True:
                action["polls"] += 1
                action["ps_after"] = resident()
                action["llama_servers"] = llama_servers()
                if not action["ps_after"] and not action["llama_servers"]:
                    break
                if time.monotonic() - started > UNLOAD_LIMIT_SEC:
                    raise TimeoutError(f"a model or a llama-server {UNLOAD_LIMIT_SEC} s after "
                                       "the unload")
                time.sleep(POLL_SEC)
    except Exception as exc:
        action["error"] = f"{type(exc).__name__}: {exc}"
    action["sec"] = round(time.monotonic() - started, 3)
    action["done_monotonic"] = time.monotonic()
    return action


# stage4-step1: end
def main():
    from auth.jwt_handler import create_access_token

    case_ids = [c for c in sys.argv[1].split(",") if c]
    caps = [float(value) for value in sys.argv[2].split("/")]
    assert 1 <= len(caps) <= 2 and all(cap > 0 for cap in caps), caps
    cases = {}
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            cases[case["case_id"]] = case
    (RUN / "cases").mkdir(exist_ok=True)
    # stage4-step1: begin
    launch = json.loads((RUN / "launch.json").read_text(encoding="utf-8"))
    arms, model = launch.get("arm"), launch.get("model")
    assert arms is None or len(arms) == len(case_ids), arms
    # stage4-step1: end
    for index, case_id in enumerate(case_ids, start=1):
        question = cases[case_id]["query"] if case_id in cases else case_id.split(":", 1)[1]
        name = case_id if case_id in cases else f"warmup-{index}"
        cap_sec = caps[0] if index == 1 else caps[-1]
        print("BEGIN", index, name, "cap", cap_sec, flush=True)
        # A token per question: one per run expired after JWT_ACCESS_TTL (3,600 s) and
        # stopped the thirty of 2026-10-16 at question 16 with a 401.
        token = create_access_token("chat-live", role="admin", tenant=TENANT)
        # stage4-step1: begin
        action = arm_action(arms[index - 1], model) if arms else None
        if action is not None and "error" in action:
            print("STOP arm: case", name, json.dumps(action), flush=True)
            return 6
        # stage4-step1: end
        row = {"case_id": name, "question": question, **ask(question, cap_sec, token)}
        if action is not None:  # stage4-step1
            row["arm_action"] = action  # stage4-step1
        try:
            row["drain_sec"] = drain()
        except Exception as exc:
            row["drain_error"] = f"{type(exc).__name__}: {exc}"
        save(RUN / "cases" / f"{index:02d}-{name}.json", row)
        result = next((e for e in row["events"] if e.get("type") == "result"), {})
        print("CASE", index, name, "first_token", row.get("first_token_sec"),
              "result", row.get("result_sec"), "error", row.get("error_sec"),
              "tokens", row.get("tokens", 0), "route", result.get("route"),
              "drain", row.get("drain_sec"), "client", row.get("client_error"), flush=True)
        # A cap met inside the read surfaces as a TimeoutError, not as "client cap".
        if "client_error" in row and row["total_sec"] >= cap_sec - 1:
            print("STOP rule: case", name, "ran past its cap of", cap_sec, "s", flush=True)
            return 5
        if "drain_error" in row:
            print("STOP", row["drain_error"], flush=True)
            return 3
        if case_id in cases and not answered(row, result):
            print("STOP gate: case", name, "delivered no answer", flush=True)
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
