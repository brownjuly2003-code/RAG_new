"""Build the tools of the qwen3:1.7b live chat stand (ROADMAP, thread M, step 3).

Sources: the published tools of the 7B record (reports/chat-live/33d4b42/tools) with the
small-model stand's supervisor and export (reports/chat-live-small/33d4b42/tools). Changes:
- live_supervisor.py: MODE prod puts back the code defaults of the served workspace — since
  468224b the 3,600-s ceiling and RAG_DEVICE=cpu, not 30/60/120 s and auto;
- live_runner.py: the client's cap may be FIRST/REST (a fresh API's first question also
  loads the embedder and the reranker); Julia's stop rule (2026-10-15) sets it to 3x each
  question's named forecast, and the series stops at the first question past it;
- live_api.py and analyze.py: the rerank's status (reranker_ok) and its document count
  are recorded beside its time;
- export.sh, watch.sh: the new stand's paths; series.sh and launch_series.py run the series
  1 -> 5 -> 30 detached from ssh, series_plan.json names every question and its forecast
  before the first launch.
Output: the record's tools folder (argv[1]).
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("D:/RAG_new")
BASE = REPO / "reports/chat-live/33d4b42/tools"
SMALL = REPO / "reports/chat-live-small/33d4b42/tools"
OUT = Path(sys.argv[1])
CODE_SHA = sys.argv[2]
STAND = f"/Users/julia/RAG_new_chat_{CODE_SHA[:7]}"
MODEL = "qwen3:1.7b"


def patch(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")


OUT.mkdir(parents=True, exist_ok=False)
for name in ("analyze.py", "check_export.py", "defaults_diff.py", "index_digest.py",
             "launch.py", "live_api.py", "live_runner.py", "watch.sh"):
    shutil.copyfile(BASE / name, OUT / name)
for name in ("live_supervisor.py", "export.py", "export.sh"):
    shutil.copyfile(SMALL / name, OUT / name)
shutil.copyfile(Path(__file__), OUT / "make_stand.py")

sup = (OUT / "live_supervisor.py").read_text(encoding="utf-8")
sup = patch(
    sup,
    "               is put back (STANDARD below: its 1800 s limits and RAG_DEVICE=cpu);\n",
    "               is put back (STANDARD below: the code defaults of the workspace —\n"
    "               since 468224b the 3,600-s ceiling and RAG_DEVICE=cpu);\n",
)
sup = patch(
    sup,
    "  SETTING=VALUE - a deployment setting applied after MODE;",
    "  CLIENT_CAP_SEC - the client's limit per question, or FIRST/REST (the first question of\n"
    "               a fresh API, then the others). Julia's stop rule (2026-10-15): 3x each\n"
    "               question's named forecast; the runner stops the series at the first\n"
    "               question that runs past it.\n"
    "  SETTING=VALUE - a deployment setting applied after MODE;",
)
sup = patch(
    sup,
    '# Code defaults (config/settings.py, .env.example) that env.json overrides.\n'
    'STANDARD = {"REQUEST_TIMEOUT_SEC": "30", "OLLAMA_REQUEST_TIMEOUT_SEC": "60",\n'
    '            "STREAMING_TIMEOUT_SEC": "120", "RAG_DEVICE": "auto"}\n',
    '# Code defaults (config/settings.py, .env.example) that env.json overrides: since 468224b\n'
    '# the three limits default to the 3,600-s ceiling and the device to the CPU.\n'
    'STANDARD = {"REQUEST_TIMEOUT_SEC": "3600", "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",\n'
    '            "STREAMING_TIMEOUT_SEC": "3600", "RAG_DEVICE": "cpu"}\n',
)
write("live_supervisor.py", sup)

runner = (OUT / "live_runner.py").read_text(encoding="utf-8")
runner = patch(
    runner,
    "Usage (by live_supervisor.py): live_runner.py CASE_IDS_COMMA_SEPARATED CLIENT_CAP_SEC\n",
    "Usage (by live_supervisor.py): live_runner.py CASE_IDS_COMMA_SEPARATED CLIENT_CAP_SEC\n"
    "CLIENT_CAP_SEC is one cap or FIRST/REST. A question that reaches its cap stops the series\n"
    "(Julia's stop rule, 2026-10-15: the cap is 3x the question's named forecast).\n",
)
runner = patch(
    runner,
    "    cap_sec = float(sys.argv[2])\n",
    "    caps = [float(value) for value in sys.argv[2].split(\"/\")]\n"
    "    assert 1 <= len(caps) <= 2 and all(cap > 0 for cap in caps), caps\n",
)
runner = patch(
    runner,
    "        print(\"BEGIN\", index, name, flush=True)\n",
    "        cap_sec = caps[0] if index == 1 else caps[-1]\n"
    "        print(\"BEGIN\", index, name, \"cap\", cap_sec, flush=True)\n",
)
runner = patch(
    runner,
    "        if \"drain_error\" in row:\n",
    "        # A cap met inside the read surfaces as a TimeoutError, not as \"client cap\".\n"
    "        if \"client_error\" in row and row[\"total_sec\"] >= cap_sec - 1:\n"
    "            print(\"STOP rule: case\", name, \"ran past its cap of\", cap_sec, \"s\", flush=True)\n"
    "            return 5\n"
    "        if \"drain_error\" in row:\n",
)
write("live_runner.py", runner)

api = (OUT / "live_api.py").read_text(encoding="utf-8")
api = patch(
    api,
    "def observe(fn, stage):\n",
    "def observe(fn, stage, extra=None):\n",
)
api = patch(
    api,
    '        emit({"stage": stage, "event": "end", "wall_sec": time.monotonic() - started})\n'
    "        return result\n",
    '        emit({"stage": stage, "event": "end", "wall_sec": time.monotonic() - started,\n'
    "              **(extra(result) if extra else {})})\n"
    "        return result\n",
)
api = patch(
    api,
    "        setattr(base.HybridRetriever, name,\n"
    "                observe(getattr(base.HybridRetriever, name), \"hybrid.\" + name))\n",
    "        # The rerank returns (documents, ok): ok False means the unreranked order was used.\n"
    "        extra = ((lambda result: {\"reranker_ok\": bool(result[1]), \"docs\": len(result[0])})\n"
    "                 if name == \"_rerank_scored_with_status\" else None)\n"
    "        setattr(base.HybridRetriever, name,\n"
    "                observe(getattr(base.HybridRetriever, name), \"hybrid.\" + name, extra))\n",
)
write("live_api.py", api)

analyze = (OUT / "analyze.py").read_text(encoding="utf-8")
analyze = patch(
    analyze,
    '                        "prompt_est_tokens", "max_tokens", "prompt_file"):\n',
    '                        "prompt_est_tokens", "max_tokens", "prompt_file", "reranker_ok",\n'
    '                        "docs"):\n',
)
write("analyze.py", analyze)

for name in ("export.sh", "watch.sh"):
    text = (OUT / name).read_text(encoding="utf-8")
    text = text.replace("/Users/julia/RAG_new_chat_33d4b42/chatlive-small", f"{STAND}/chatlive")
    text = text.replace("/Users/julia/RAG_new_chat_33d4b42/chatlive", f"{STAND}/chatlive")
    text = text.replace("/Users/julia/RAG_new_chat_33d4b42", STAND)
    text = text.replace("chatlive-small/runs.json", "chatlive/runs.json")
    assert "33d4b42" not in text, name
    write(name, text)

cases = [json.loads(line)["case_id"]
         for line in (REPO / "evaluation/curated_cases_aircargo.jsonl").read_text(
             encoding="utf-8").splitlines() if line.strip()]
steps = [("qwen3-1p7b-q1", cases[:1]), ("qwen3-1p7b-q5", cases[:5]),
         ("qwen3-1p7b-q30", cases[:30])]
plan = {
    "named": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "model": MODEL,
    "code_sha": CODE_SHA,
    "mode": "prod",
    "forecast_sec": {"first_question_of_a_fresh_api": 180, "other_questions": 120},
    "forecast_basis": (
        "qwen2.5:1.5b, a model of the same size, on this path on 2026-10-14 "
        "(reports/chat-live-small/33d4b42/runs.json): live-s2-qwen25-1p5b-floor1, one question "
        "on a fresh API, 170 s; live-s3-qwen25-1p5b-floor, five on a fresh API, 100, 93, 92, "
        "118 and 168 s (median 100 s). The first question gets the slower of the two; "
        "qwen3:1.7b with thinking off (c2739af) wrote 21 tokens where qwen2.5:7b wrote 20 "
        "(reports/think-probe/2026-10-15)"
    ),
    "stop_rule": (
        "Julia, 2026-10-15: the series stops once a question runs past 3x its forecast; "
        "the session investigates at once"
    ),
    "client_cap_sec": "540/360",
    "cases_source": "evaluation/curated_cases_aircargo.jsonl, the first 30 in file order "
                    "(the first five are the five of 2026-10-14)",
    "steps": [{"label": label, "cases": ids} for label, ids in steps],
}
write("series_plan.json", json.dumps(plan, indent=2, ensure_ascii=False) + "\n")

series = f"""#!/bin/sh
# The live series of {MODEL} at the code defaults, 1 -> 5 -> 30 questions (series_plan.json):
# each step a fresh supervisor (API, database, model load timed apart); the next step only
# when the runner delivered every answer within its cap (exit 0). Started by launch_series.py.
CL={STAND}/chatlive
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
LOG=$CL/runs/series.log
API=http://127.0.0.1:11434
CAP={plan["client_cap_sec"]}
mkdir -p $CL/runs

free() {{  # both ports bind and Ollama holds no model, as live_supervisor.py requires
  $PY -c "import socket
for port in (8002, 55433):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))" 2>/dev/null &&
    [ "$(curl -s $API/api/ps | $PY -c "import json,sys; print(len(json.load(sys.stdin)['models']))")" = 0 ]
}}

run() {{  # label cases
  i=0
  until free; do i=$((i + 1)); [ $i -gt 36 ] && {{ echo "$(date -u +%FT%TZ) STOP $1: ports or model not free after 180 s" >> $LOG; exit 1; }}; sleep 5; done
  echo "$(date -u +%FT%TZ) START $1" >> $LOG
  {{ sysctl -n vm.loadavg vm.swapusage; ps -axo pid,pcpu,rss,comm -r | head -6; }} >> $LOG
  $PY -u $CL/live_supervisor.py "$1" prod "$2" "$CAP" "MODEL={MODEL}" >> $CL/runs/$1.supervisor.log 2>&1
  code=$?
  echo "$(date -u +%FT%TZ) $(tail -n 1 $CL/runs/$1.supervisor.log)" >> $LOG
  return $code
}}

"""
for label, ids in steps:
    series += f'run {label} "{",".join(ids)}" || {{ echo "$(date -u +%FT%TZ) SERIES_STOP after {label}" >> $LOG; exit 1; }}\n'
series += 'echo "$(date -u +%FT%TZ) SERIES_DONE" >> $LOG\n'
write("series.sh", series)

write("launch_series.py", '''"""Start series.sh in its own session, detached from the ssh terminal; prints its pid."""

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
(HERE / "runs").mkdir(exist_ok=True)
with (HERE / "runs" / "series.out").open("ab") as fh:
    child = subprocess.Popen(["/bin/sh", str(HERE / "series.sh")], stdin=subprocess.DEVNULL,
                             stdout=fh, stderr=subprocess.STDOUT, start_new_session=True,
                             cwd=HERE)
print(json.dumps({"series_pid": child.pid}))
''')
print("built", OUT, "steps", [(label, len(ids)) for label, ids in steps])
