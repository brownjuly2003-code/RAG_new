"""Start live_supervisor.py in its own session, detached from the ssh terminal.

Usage: launch.py LABEL MODE CASES CLIENT_CAP_SEC  (prints the supervisor pid and log)
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
label = sys.argv[1]
log = HERE / "runs" / f"{label}.supervisor.log"
log.parent.mkdir(exist_ok=True)
with log.open("ab") as fh:
    child = subprocess.Popen(
        [sys.executable, "-u", str(HERE / "live_supervisor.py"), *sys.argv[1:]],
        stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
        start_new_session=True, cwd=HERE,
    )
print(json.dumps({"supervisor_pid": child.pid, "log": str(log)}))
