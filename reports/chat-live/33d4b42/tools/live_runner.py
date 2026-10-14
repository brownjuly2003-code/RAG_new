"""Send chat questions through the web chat's path, POST /api/ask/stream, one at a time.

Every SSE event is kept with the second it arrived. After each answer the runner waits
until the API reports no pipeline in flight, so measured requests never overlap.
The first real case without a delivered answer stops the run (the 1 -> 5 -> 100 gate);
warmup questions do not gate.
Usage (by live_supervisor.py): live_runner.py CASE_IDS_COMMA_SEPARATED CLIENT_CAP_SEC
"""

import json
import os
import re
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))
RUN = Path(os.environ["CHAT_RUN_DIR"])
API = "http://127.0.0.1:8002"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def ask(question, cap_sec, token):
    payload = {"question": question, "session_id": str(uuid.uuid4()), "tenant_id": "aircargo"}
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


def main():
    from auth.jwt_handler import create_access_token

    case_ids = [c for c in sys.argv[1].split(",") if c]
    cap_sec = float(sys.argv[2])
    cases = {}
    for line in (WS / "evaluation/curated_cases_aircargo.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            cases[case["case_id"]] = case
    token = create_access_token("chat-live", role="admin", tenant="aircargo")
    (RUN / "cases").mkdir(exist_ok=True)
    for index, case_id in enumerate(case_ids, start=1):
        question = cases[case_id]["query"] if case_id in cases else case_id.split(":", 1)[1]
        name = case_id if case_id in cases else f"warmup-{index}"
        print("BEGIN", index, name, flush=True)
        row = {"case_id": name, "question": question, **ask(question, cap_sec, token)}
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
        if "drain_error" in row:
            print("STOP", row["drain_error"], flush=True)
            return 3
        if case_id in cases and not answered(row, result):
            print("STOP gate: case", name, "delivered no answer", flush=True)
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
