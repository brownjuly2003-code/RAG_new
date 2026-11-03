"""Executed by the test shim, never imported by the application."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).parent
scenario = json.loads((root / "scenario.json").read_text(encoding="utf-8"))
record = {
    "argv": sys.argv[1:],
    "environment": dict(os.environ),
    "stdin": sys.stdin.buffer.read().decode("utf-8"),
    "cwd": os.getcwd(),
    "contents": os.listdir("."),
    "pid": os.getpid(),
    "pgid": os.getpgrp(),
    "started": time.monotonic(),
}
if scenario["child"]:
    # A child inherits the group and the pipes; killing only the leader would
    # leave both the child and communicate() alive. The delayed marker proves death.
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import pathlib,sys,time; time.sleep(3); pathlib.Path(sys.argv[1]).touch()",
            str(root / "child-survived"),
        ]
    )
    record["child_pid"] = child.pid
path = root / f"call-{os.getpid()}.json"
path.write_text(json.dumps(record), encoding="utf-8")
time.sleep(scenario["delay"])
events = scenario["events"]
for marker, prompt_events in scenario.get("prompt_events", {}).items():
    if marker in record["stdin"]:
        events = prompt_events
        break
for event in events:
    print(json.dumps(event), flush=True)
record["ended"] = time.monotonic()
path.write_text(json.dumps(record), encoding="utf-8")
sys.exit(scenario["exit"])
