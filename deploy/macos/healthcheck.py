"""One look at the chat service on the Mac (PLAN.md stage 6, item 1: the health check).

Run on the Mac with the API's interpreter: ``$PY -I deploy/macos/healthcheck.py``. It prints one
JSON object - states, numbers and names, never a value of the service's env file, a log line, a
question or an answer - and exits 0 when the service answers: liveness and readiness 200, the
index and the pipeline loaded, the session store's database up and, under the cache-ram policy,
the limit llama-server last reported equal to the policy's. Otherwise it exits 1.

launchd restarts the service when its process ends, not when it hangs: a hung service shows
here as liveness without 200 while launchd still reports it running.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LABEL = "com.rag-new.chat"
API = "http://127.0.0.1:8002"
OLLAMA = "http://localhost:11434"  # OLLAMA_BASE_URL's code default
SERVICE_ENV = Path.home() / ".config" / "rag-new" / "chat-service.env"
OWN_KEYS = ("RAG_SERVICE_MEMORY_POLICY", "RAG_SERVICE_OLLAMA_LOG")
LOG_TAIL_BYTES = 4 * 1024 * 1024
NUM = r"(-?\d+(?:\.\d+)?)"
# llama-server's line after a request (stage 4, step 0's reader reads the same shape).
CACHE_STATE = re.compile(rf"- cache state: (\d+) prompts, {NUM} MiB \(limits: {NUM} MiB")
METRIC = re.compile(
    r"^(rag_inflight_pipelines|rag_orphan_work_inflight|rag_pipeline_rejections_total)"
    r'(?:\{reason="([^"]*)"\})?\s+(\S+)$'
)


def fetch(url: str, timeout: float) -> tuple[int | None, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (OSError, ValueError):
        return None, b""


def parse(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def launchd() -> dict[str, Any]:
    done = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        return {"loaded": False}
    out: dict[str, Any] = {"loaded": True}
    shapes = (
        ("state", r"^\s*state = (\S+)"),
        ("pid", r"^\s*pid = (\d+)"),
        ("last_exit", r"^\s*last exit code = (.+?)\s*$"),
    )
    for key, pattern in shapes:
        found = re.search(pattern, done.stdout, re.MULTILINE)
        out[key] = found.group(1) if found else None
    return out


def readiness() -> dict[str, Any]:
    """The API's readiness: each component's status only, never its detail."""
    code, body = fetch(f"{API}/api/health/ready", 60.0)
    data = parse(body)
    components = data.get("components") or {}
    return {
        "code": code,
        "status": data.get("status"),
        "components": {
            name: (item or {}).get("status") for name, item in sorted(components.items())
        },
        "vector_store_loaded": data.get("vector_store_loaded"),
        "pipeline_available": data.get("pipeline_available"),
    }


def metrics() -> dict[str, Any]:
    """Questions in flight, work orphaned by a closed client, refusals by reason."""
    code, body = fetch(f"{API}/metrics", 10.0)
    out: dict[str, Any] = {
        "code": code,
        "inflight_pipelines": None,
        "orphan_work_inflight": None,
        "rejections": {},
    }
    for line in body.decode("utf-8", "replace").splitlines():
        found = METRIC.match(line)
        if found is None:
            continue
        name, reason, value = found.groups()
        try:
            number = float(value)
        except ValueError:
            continue
        if name == "rag_pipeline_rejections_total":
            out["rejections"][reason or ""] = number
        elif name == "rag_inflight_pipelines":
            out["inflight_pipelines"] = number
        else:
            out["orphan_work_inflight"] = number
    return out


def ollama() -> dict[str, Any]:
    code, body = fetch(f"{OLLAMA}/api/ps", 10.0)
    models = parse(body).get("models") if code == 200 else None
    _, version = fetch(f"{OLLAMA}/api/version", 10.0)
    return {
        "code": code,
        "models": None if models is None else [item.get("name") for item in models],
        "version": parse(version).get("version"),
    }


def own_keys(path: Path) -> dict[str, str]:
    """This script's two keys of the service's env file; no other line is kept."""
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return out
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key in OWN_KEYS:
            out[key] = value.strip()
    return out


def cache_limit(log: str | None) -> dict[str, Any]:
    """The cache limit llama-server last reported, from the tail of Ollama's server log.

    The line follows a request, so before the first answer after a model load the last line
    can be an older process's.
    """
    if not log:
        return {"read": False, "why": "RAG_SERVICE_OLLAMA_LOG is not set"}
    path = Path(log)
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - LOG_TAIL_BYTES))
            tail = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        return {"read": False, "why": type(exc).__name__}
    for line in reversed(tail.splitlines()):
        found = CACHE_STATE.search(line)
        if found is not None:
            return {
                "read": True,
                "prompts": int(found.group(1)),
                "mib": float(found.group(2)),
                "limit_mib": float(found.group(3)),
            }
    return {"read": False, "why": "no cache state line in the log's tail"}


def swap_used_mb() -> float | None:
    done = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, check=False
    )
    found = re.search(r"used = ([\d.]+)M", done.stdout)
    return float(found.group(1)) if found else None


def main() -> int:
    own = own_keys(SERVICE_ENV)
    policy = own.get("RAG_SERVICE_MEMORY_POLICY")
    live, _ = fetch(f"{API}/api/health/live", 10.0)
    ready = readiness()
    report: dict[str, Any] = {
        "launchd": launchd(),
        "live": live,
        "ready": ready,
        "metrics": metrics(),
        "ollama": ollama(),
        "policy": {"name": policy},
        "swap_used_mb": swap_used_mb(),
    }
    policy_holds = True
    if policy and policy.startswith("cache-ram:"):
        limit = cache_limit(own.get("RAG_SERVICE_OLLAMA_LOG"))
        report["policy"]["cache"] = limit
        if limit["read"]:
            policy_holds = limit["limit_mib"] == float(policy.split(":", 1)[1])
            report["policy"]["holds"] = policy_holds
    healthy = (
        live == 200
        and ready["code"] == 200
        and ready["vector_store_loaded"] is True
        and ready["pipeline_available"] is True
        and ready["components"].get("postgres") == "ok"
        and policy_holds
    )
    report["healthy"] = healthy
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
