"""One step of the screening: print what it measured; exit 0 when the next step may start.

A step of 1 or 5 cases must answer every case; the 100-case step records failures and goes on.
The runner exits 1 for any run short of 100 complete cases, so its code is only reported.
Answers that reach num_predict are counted, and the first answer's opening is shown: a
thinking model that ignores think=false writes its reasoning there.
"""

import json
import statistics
import sys


def median(values):
    return round(statistics.median(values), 1) if values else None


path, cases, code = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
try:
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
except (OSError, ValueError) as exc:
    print(f"  no report ({type(exc).__name__}), runner exit {code}")
    sys.exit(1)
rows = report["runs"][0]["cases"]
failed = [r["case_id"] for r in rows if not r.get("generation_valid") or not r.get("nli_valid")]
timing = [r.get("ollama_timing") or {} for r in rows]
write = [t["eval_count"] / t["eval_duration"] * 1e9 for t in timing if t.get("eval_duration")]
read = [
    t["prompt_eval_count"] / t["prompt_eval_duration"] * 1e9
    for t in timing
    if t.get("prompt_eval_duration")
]
latency = median([r["latency_ms"] / 1000 for r in rows])
cap = report.get("provenance", {}).get("config", {}).get("num_predict", 384)
capped = sum(1 for t in timing if (t.get("eval_count") or 0) >= cap)
first = " ".join((rows[0].get("answer") or "").split())[:90] if rows else ""
print(
    f"  cases {len(rows)}/{cases} runner exit {code} failed {len(failed)} {failed[:5]}; "
    f"median latency {latency} s, read {median(read)} tok/s, write {median(write)} tok/s; "
    f"at num_predict {capped}; first answer {first!r}"
)
sys.exit(0 if len(rows) == cases and (cases == 100 or not failed) else 1)
