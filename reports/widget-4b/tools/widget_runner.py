"""Send questions through the widget's path, POST /api/ask, one at a time.

Copied from reports/stage1/tools/live_runner.py for stage 3, step 4 (docs/specs/widget-4b.md):
the request is the widget's, a new conversation's first question with no session_id, and the
reply is one JSON body instead of a stream. The tenant is CHAT_TENANT and the questions are
CHAT_CASES_FILE (JSON lines with case_id and query), both set by widget_supervisor.py.

The reply is kept with the seconds it took. After each answer the runner waits until the API
reports no pipeline in flight, so measured requests never overlap. The first case without a
delivered response (an HTTP error, a timeout or error route, the client cap) stops the run.
Usage (by widget_supervisor.py): widget_runner.py CASE_IDS_COMMA_SEPARATED CLIENT_CAP_SEC
"""

import json
import os
import re
import sys
import time
import urllib.error
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
    # A new conversation's first question, as the widget sends it: no session_id.
    payload = {"question": question, "tenant_id": TENANT}
    request = urllib.request.Request(
        API + "/api/ask",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    row = {"started": now(), "reply": None}
    before = time.monotonic()
    row["t0_monotonic"] = before
    try:
        with urllib.request.urlopen(request, timeout=cap_sec) as response:
            row["http_status"] = response.status
            row["reply"] = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        row["http_status"] = exc.code
        row["client_error"] = f"HTTPError: {exc.code}"
    except Exception as exc:
        row["client_error"] = f"{type(exc).__name__}: {exc}"
    row["total_sec"] = round(time.monotonic() - before, 3)
    row["finished"] = now()
    return row


def answered(row):
    """HTTP 200 with a reply whose route is neither a timeout nor an error."""
    reply = row.get("reply") or {}
    return (
        row.get("http_status") == 200
        and "client_error" not in row
        and reply.get("route") not in (None, "timeout", "error")
    )


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
    assert case_ids and cap_sec > 0, (case_ids, cap_sec)
    cases = {}
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            cases[case["case_id"]] = case
    assert all(case_id in cases for case_id in case_ids), "every case is a real question"
    (RUN / "cases").mkdir(exist_ok=True)
    for index, case_id in enumerate(case_ids, start=1):
        question = cases[case_id]["query"]
        print("BEGIN", index, case_id, "cap", cap_sec, flush=True)
        # A token per question: one per run expired after JWT_ACCESS_TTL (3,600 s) and
        # stopped the thirty of 2026-10-16 at question 16 with a 401.
        token = create_access_token("widget-live", role="admin", tenant=TENANT)
        row = {"case_id": case_id, "question": question, **ask(question, cap_sec, token)}
        try:
            row["drain_sec"] = drain()
        except Exception as exc:
            row["drain_error"] = f"{type(exc).__name__}: {exc}"
        save(RUN / "cases" / f"{index:02d}-{case_id}.json", row)
        reply = row.get("reply") or {}
        print(
            "CASE",
            index,
            case_id,
            "seconds",
            row["total_sec"],
            "http",
            row.get("http_status"),
            "route",
            reply.get("route"),
            "ticket",
            bool(reply.get("ticket_id")),
            "drain",
            row.get("drain_sec"),
            "client",
            row.get("client_error"),
            flush=True,
        )
        if "client_error" in row and row["total_sec"] >= cap_sec - 1:
            print("STOP rule: case", case_id, "ran past its cap of", cap_sec, "s", flush=True)
            return 5
        if "drain_error" in row:
            print("STOP", row["drain_error"], flush=True)
            return 3
        if not answered(row):
            print("STOP gate: case", case_id, "delivered no response", flush=True)
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
