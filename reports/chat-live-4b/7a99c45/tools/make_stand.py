"""Build the tools of the Qwen3-4B-Instruct live chat stand (ROADMAP, thread M, step 4).

Source: the published tools of the qwen3:1.7b record (reports/chat-live-qwen3/9e1fc9e/tools).
Changes:
- live_supervisor.py: DEFAULT_MODEL is the code default since step 4,
  qwen3:4b-instruct-2507-q4_K_M, and series.sh passes no MODEL=, so the API runs on the
  workspace's own config/providers.yml and no OLLAMA_MODEL_NAME — the default is what is
  served, not an override; the sampler also keeps the five largest processes by memory;
- analyze.py: the self-evaluation's score is read from the result event's quality_score
  (the 1.7b and 7B records read "quality", which the event does not carry, so their score
  is null); each question gets the memory measured while it ran (swap, free memory, the
  largest resident API and model);
- export.sh, watch.sh: the new stand's paths; series.sh and launch_series.py run the series
  1 -> 5 -> 30 detached from ssh, series_plan.json names every question and its forecast
  before the first launch, from the 4B's own record (reports/chat-live-small/33d4b42).
Output: the record's tools folder (argv[1]).
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("D:/RAG_new")
BASE = REPO / "reports/chat-live-qwen3/9e1fc9e/tools"
OUT = Path(sys.argv[1])
CODE_SHA = sys.argv[2]
STAND = f"/Users/julia/RAG_new_chat_{CODE_SHA[:7]}"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PREFIX = "qwen3-4b-instruct"
FORECAST = {"first_question_of_a_fresh_api": 343, "other_questions": 300}


def patch(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")


OUT.mkdir(parents=True, exist_ok=False)
for name in ("check_export.py", "defaults_diff.py", "index_digest.py",
             "launch.py", "live_api.py", "live_runner.py", "launch_series.py"):
    shutil.copyfile(BASE / name, OUT / name)
shutil.copyfile(Path(__file__), OUT / "make_stand.py")

export = (BASE / "export.py").read_text(encoding="utf-8")
export = patch(export, 'MODEL = "qwen2.5:7b"\n', f'MODEL = "{MODEL}"\n')
export = patch(
    export,
    '               "client_error", "route", "quality", "sources", "suggested", "events")\n',
    '               "client_error", "route", "quality", "quality_source", "sources", "suggested",\n'
    '               "memory", "events")\n',
)
write("export.py", export)

sup = (BASE / "live_supervisor.py").read_text(encoding="utf-8")
sup = patch(
    sup,
    "               defaults name it (PROVIDER_REGISTRY_PATH, the graph's calls); the code\n"
    "               defaults stay. Default qwen2.5:7b, the model of the code defaults.\n",
    "               defaults name it (PROVIDER_REGISTRY_PATH, the graph's calls); the code\n"
    "               defaults stay. Default qwen3:4b-instruct-2507-q4_K_M, the model of the\n"
    "               code defaults since step 4: without MODEL= nothing is overridden.\n",
)
sup = patch(sup, 'DEFAULT_MODEL = "qwen2.5:7b"\n', f'DEFAULT_MODEL = "{MODEL}"\n')
sup = patch(
    sup,
    "    procs = []\n    busiest = []\n",
    "    procs = []\n    busiest = []\n    largest = []\n",
)
sup = patch(
    sup,
    "        busiest.append(row)\n",
    "        busiest.append(row)\n        largest.append(row)\n",
)
sup = patch(
    sup,
    "    busiest = sorted(busiest, key=lambda row: row[1], reverse=True)[:5]\n",
    "    busiest = sorted(busiest, key=lambda row: row[1], reverse=True)[:5]\n"
    "    largest = sorted(largest, key=lambda row: row[2], reverse=True)[:5]\n",
)
sup = patch(
    sup,
    '            "busiest": busiest}\n',
    '            "busiest": busiest, "largest": largest}\n',
)
write("live_supervisor.py", sup)

analyze = (BASE / "analyze.py").read_text(encoding="utf-8")
analyze = patch(
    analyze,
    '                   if k in ("at", "type", "route", "quality", "quality_source", "detail", "status")}\n',
    '                   if k in ("at", "type", "route", "quality_score", "quality_source", "detail",\n'
    '                            "status")}\n',
)
analyze = patch(
    analyze,
    '            "quality": result.get("quality"), "sources": len(result.get("sources") or []),\n',
    '            "quality": result.get("quality_score"),\n'
    '            "quality_source": result.get("quality_source"),\n'
    '            "sources": len(result.get("sources") or []),\n'
    '            "t0_monotonic": case.get("t0_monotonic"),\n',
)
analyze = patch(
    analyze,
    '    report["memory"] = {"samples": len(resources),\n',
    '    # The memory each question ran in: samples between its request and its last byte.\n'
    '    for item in report["cases"]:\n'
    '        t0 = item.pop("t0_monotonic", None)\n'
    '        if t0 is None or item.get("total_sec") is None:\n'
    '            continue\n'
    '        window = [r for r in resources\n'
    '                  if r.get("monotonic") is not None and t0 <= r["monotonic"] <= t0 + item["total_sec"]]\n'
    '        swap_q = [swap_used_mb(r.get("swap")) for r in window if r.get("swap")]\n'
    '        free_q = [r["free_pages"] * 4096 / 2**20 for r in window if r.get("free_pages")]\n'
    '        rss_q = {}\n'
    '        for r in window:\n'
    '            for pid, cpu, size, comm in r.get("procs", []):\n'
    '                key = "ollama" if "ollama" in comm else ("postgres" if "postgres" in comm else "python")\n'
    '                rss_q[key] = max(rss_q.get(key, 0), size)\n'
    '        item["memory"] = {"samples": len(window),\n'
    '                          "swap_used_mb": [min(swap_q), max(swap_q)] if swap_q else None,\n'
    '                          "free_mb_min": round(min(free_q)) if free_q else None,\n'
    '                          "max_rss_mb": {k: round(v / 2**20) for k, v in rss_q.items()}}\n'
    '    report["memory"] = {"samples": len(resources),\n',
)
write("analyze.py", analyze)

for name in ("export.sh", "watch.sh"):
    text = (BASE / name).read_text(encoding="utf-8")
    text = text.replace("/Users/julia/RAG_new_chat_9e1fc9e", STAND)
    assert "9e1fc9e" not in text, name
    write(name, text)

cases = [json.loads(line)["case_id"]
         for line in (REPO / "evaluation/curated_cases_aircargo.jsonl").read_text(
             encoding="utf-8").splitlines() if line.strip()]
steps = [(f"{PREFIX}-q1", cases[:1]), (f"{PREFIX}-q5", cases[:5]),
         (f"{PREFIX}-q30", cases[:30])]
first, rest = FORECAST["first_question_of_a_fresh_api"], FORECAST["other_questions"]
plan = {
    "named": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "model": MODEL,
    "code_sha": CODE_SHA,
    "mode": "prod",
    "served_by": "the code defaults: series.sh passes no MODEL=, so the API gets no "
                 "OLLAMA_MODEL_NAME and no PROVIDER_REGISTRY_PATH",
    "forecast_sec": FORECAST,
    "forecast_basis": (
        "the same model on this path on 2026-10-14 (reports/chat-live-small/33d4b42/runs.json, "
        "code 33d4b42, 1,800-s limits, the rerank on the CPU): "
        "live-s2-qwen3-4b-instruct-floor1, one question on a fresh API, 343 s; "
        "live-s3-qwen3-4b-instruct-floor, five on a fresh API, 258, 303, 322, 297 and 297 s "
        "(the first of them the same question as the 343 s). The first question of each step "
        "gets 343 s, every other one 300 s, questions 6-30 included"
    ),
    "stop_rule": (
        "Julia, 2026-10-15: the series stops once a question runs past 3x its forecast; "
        "the session investigates at once"
    ),
    "client_cap_sec": f"{3 * first}/{3 * rest}",
    "cases_source": "evaluation/curated_cases_aircargo.jsonl, the first 30 in file order "
                    "(the first five are the five of 2026-10-14)",
    "recorded_per_question": "route, the self-evaluation's score and its source, time to the "
                             "first token and to the result, the memory while it ran",
    "steps": [{"label": label, "cases": ids} for label, ids in steps],
}
write("series_plan.json", json.dumps(plan, indent=2, ensure_ascii=False) + "\n")

series = (BASE / "series.sh").read_text(encoding="utf-8")
head, _, _ = series.partition("\nrun qwen3-1p7b-q1 ")
head = head.replace("qwen3:1.7b", MODEL).replace("/Users/julia/RAG_new_chat_9e1fc9e", STAND)
head = patch(head, "CAP=540/360\n", f"CAP={plan['client_cap_sec']}\n")
head = patch(head, ' "$CAP" "MODEL=qwen3:4b-instruct-2507-q4_K_M" >>', ' "$CAP" >>')
assert "9e1fc9e" not in head and "MODEL=" not in head
for label, ids in steps:
    head += (f'\nrun {label} "{",".join(ids)}" || '
             f'{{ echo "$(date -u +%FT%TZ) SERIES_STOP after {label}" >> $LOG; exit 1; }}')
head += '\necho "$(date -u +%FT%TZ) SERIES_DONE" >> $LOG\n'
write("series.sh", head)
print("built", OUT, "steps", [(label, len(ids)) for label, ids in steps])
