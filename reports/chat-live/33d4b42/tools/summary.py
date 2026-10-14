"""Compact view of one run's analysis.json (written by analyze.py).

Usage (Mac): summary.py LABEL
"""

import json
import sys
from pathlib import Path

run = Path(__file__).resolve().parent / "runs" / sys.argv[1]
data = json.loads((run / "analysis.json").read_text(encoding="utf-8"))
head = ("status", "error", "ollama_load_sec", "tickets", "models_after", "unloaded", "memory")
print({key: data.get(key) for key in head})
fields = ("first_token_sec", "last_token_sec", "result_sec", "error_sec", "total_sec", "route",
          "quality", "sources", "tokens", "drain_sec", "client_error")
for case in data["cases"]:
    print("==", case["case"], {key: case.get(key) for key in fields})
    for event in case["events"]:
        print("  ev", event)
    for stage in case["timeline"]:
        print("  st", stage)
