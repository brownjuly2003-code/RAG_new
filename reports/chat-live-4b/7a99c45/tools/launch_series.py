"""Start series.sh in its own session, detached from the ssh terminal; prints its pid."""

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
