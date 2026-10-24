"""The stand's environment, as V4's record reads it (v4_record.environment).

docs/specs/answer-prompt-v4.md, «The stand». On the Mac, by the stage's interpreter, before
V4's first batch and after each key's last, appended to the stand's journal:

  $PY reports/answer-prompt-v4/tools/stand_env.py >> $S/chatlive/v4-environment.jsonl

Prints one JSON line: the running Ollama server's version, its process and binary and when
each started or changed; the interpreter, a SHA-256 of its installed distributions
(name==version, sorted: the content of a pip freeze without pip), the newest of them by its
metadata folder's change time and the versions of those named ollama or langchain; the
change times of the files of the runtime folder the stand links (stat only, never read).
Names and times only.
"""

import hashlib
import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="seconds")


def ollama():
    out = {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=10) as reply:
            out["server_version"] = json.loads(reply.read()).get("version")
    except OSError as exc:
        out["server_version"] = None
        out["server_error"] = type(exc).__name__
    lines = subprocess.run(
        ["ps", "-axo", "pid=,lstart=,command="], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    serving = [line.split() for line in lines if line.rstrip().endswith("ollama serve")]
    out["servers"] = [
        {
            "pid": int(fields[0]),
            "started": datetime.strptime(" ".join(fields[1:6]), "%a %b %d %H:%M:%S %Y")
            .astimezone(timezone.utc)
            .isoformat(timespec="seconds"),
            "binary": fields[6],
            "binary_changed": stamp(os.stat(os.path.realpath(fields[6])).st_mtime),
        }
        for fields in serving
    ]
    plist = "/Applications/Ollama.app/Contents/Info.plist"
    if os.path.exists(plist):
        out["app_changed"] = stamp(os.stat(plist).st_mtime)
    return out


def distributions():
    found = {}
    newest = None
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        found[name.lower()] = dist.version
        folder = getattr(dist, "_path", None)
        if folder is None:
            continue
        changed = os.stat(folder).st_mtime
        if newest is None or changed > newest[1]:
            newest = (name, changed)
    lines = "".join(f"{name}=={found[name]}\n" for name in sorted(found))
    return {
        "count": len(found),
        "freeze_sha256": hashlib.sha256(lines.encode("utf-8")).hexdigest(),
        "newest": {"name": newest[0], "changed": stamp(newest[1])} if newest else None,
        "versions": {
            name: found[name] for name in sorted(found) if "ollama" in name or "langchain" in name
        },
    }


def runtime(folder="/Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime"):
    return {
        name: stamp(os.stat(os.path.join(folder, name)).st_mtime)
        for name in sorted(os.listdir(folder))
    }


def main():
    print(
        json.dumps(
            {
                "taken": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "python": sys.executable,
                "python_version": sys.version.split()[0],
                "ollama": ollama(),
                "distributions": distributions(),
                "runtime": runtime(),
            }
        )
    )


if __name__ == "__main__":
    main()
