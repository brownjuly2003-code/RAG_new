"""Manual Windows laptop check, with the release venv's Python; never invoke in pytest.

Uses only that Python executable as the child, never Codex or an application/database.
The temporary ACL denial is confined to this check's disposable capture directory.
"""

from __future__ import annotations

import csv
import ctypes
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_shim import build, sha256
from capture_journal import read_heartbeats, utc

ROOT = Path(__file__).resolve().parents[3]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def configure(shim: Path, capture: Path) -> None:
    result = subprocess.run(
        [str(shim), "--configure", "--real-exe", sys.executable, "--capture-root", str(capture)],
        capture_output=True,
        check=False,
        timeout=15,
    )
    require(result.returncode == 0, "shim configuration failed")


def one_call(capture: Path) -> Path:
    calls = list((capture / "calls").iterdir())
    require(len(calls) == 1 and calls[0].is_dir(), "expected exactly one call directory")
    return calls[0]


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    require(isinstance(value, dict), "record is not an object")
    return value


def echo(shim: Path, capture: Path) -> dict[str, Any]:
    configure(shim, capture)
    data = os.urandom(200 * 1024)
    code = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"
    result = subprocess.run(
        [str(shim), "-c", code],
        input=data,
        capture_output=True,
        check=False,
        timeout=30,
    )
    folder = one_call(capture)
    records = {name: read(folder / (name + ".json")) for name in ("start", "spawned", "end")}
    require((folder / "stdin.bin").read_bytes() == data, "stdin bytes changed")
    require(
        result.stdout == data and result.returncode == 0 and result.stderr == b"",
        "echo forwarding failed",
    )
    require((folder / "stdout.bin").read_bytes() == data, "stdout capture changed")
    require((folder / "stderr.bin").read_bytes() == b"", "stderr capture changed")
    require(records["start"]["schema"] == "codex-capture-shim/1", "wrong start schema")
    require(records["start"]["argv"] == ["-c", code], "argv changed")
    require(records["start"]["stdin_sha256"] == sha256(folder / "stdin.bin"), "stdin hash mismatch")
    require(records["start"]["stdin_length"] == len(data), "stdin length mismatch")
    require(records["spawned"]["child_pid"] > 0, "child pid missing")
    end = records["end"]
    require(end["capture_ok"] is True and end["exit_code"] == 0, "echo capture failed")
    require((folder / "alive.log").is_file(), "echo heartbeat log missing")
    heartbeats = read_heartbeats(folder / "alive.log")
    require(bool(heartbeats), "echo heartbeat missing")
    require(heartbeats[-1] <= utc(end["utc"]), "heartbeat after shim end")
    for name in ("stdout", "stderr"):
        path = folder / (name + ".bin")
        require(end[name + "_length"] == path.stat().st_size, name + " length mismatch")
        require(end[name + "_sha256"] == sha256(path), name + " hash mismatch")
    return {"passed": True, "bytes": len(data), "records": 4}


def job_kill(shim: Path, capture: Path) -> dict[str, Any]:
    from ctypes import wintypes

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from llm.providers.codex import _WindowsJob

    configure(shim, capture)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SystemRoot", "CODEX_HOME", "TEMP", "TMP")
        if key in os.environ
    }
    job = _WindowsJob()
    process = None
    child_handle = None
    closed = False
    try:
        # Match the provider's critical order, flags, pipes and allow-list exactly.
        process = subprocess.Popen(
            [str(shim), "-c", "import time; time.sleep(60)"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=capture,
            env=environment,
            start_new_session=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        job.assign(process)
        assert process.stdin is not None
        process.stdin.write(b"job ownership check")
        process.stdin.close()
        time.sleep(3)
        folder = one_call(capture)
        spawned = read(folder / "spawned.json")
        # Retain a handle BEFORE killing, so PID reuse cannot make this check pass.
        child_handle = kernel.OpenProcess(0x00100000, False, spawned["child_pid"])
        require(bool(child_handle), "could not open captured child process")
        require(kernel.WaitForSingleObject(child_handle, 0) == 258, "child exited before job close")
        require(process.poll() is None, "shim exited before job close")
        closed_at = datetime.now(timezone.utc)
        job.close()
        closed = True
        process.wait(timeout=10)
        require(kernel.WaitForSingleObject(child_handle, 10000) == 0, "child survived job close")
        require((folder / "start.json").is_file(), "start record missing after kill")
        require(not (folder / "end.json").exists(), "killed shim unexpectedly wrote end")
        heartbeats = read_heartbeats(folder / "alive.log")
        require(len(heartbeats) >= 2, "fewer than two heartbeats before job close")
        require(
            abs((closed_at - heartbeats[-1]).total_seconds()) <= 2,
            "last heartbeat is not within 2 s of job close",
        )
        return {"passed": True, "shim_gone": True, "child_gone": True, "missing_end": True}
    finally:
        try:
            if not closed:
                job.close()
        finally:
            if child_handle:
                kernel.CloseHandle(child_handle)
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
                for pipe in (process.stdin, process.stdout):
                    if pipe is not None:
                        pipe.close()


def capture_failure(shim: Path, capture: Path) -> dict[str, Any]:
    configure(shim, capture)
    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    require(identity.returncode == 0, "cannot resolve current SID")
    rows = list(csv.reader(io.StringIO(identity.stdout.strip())))
    require(
        len(rows) == 1 and len(rows[0]) == 2 and rows[0][1].startswith("S-1-"),
        "invalid current SID",
    )
    sid = "*" + rows[0][1]
    marker = capture.parent / "unexpected-child"
    try:
        denied = subprocess.run(
            ["icacls", str(capture), "/deny", sid + ":(OI)(CI)(W)"],
            capture_output=True,
            check=False,
            timeout=10,
        )
        require(denied.returncode == 0, "cannot deny capture directory writes")
        code = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_bytes(b'spawned')"
        result = subprocess.run(
            [str(shim), "-c", code],
            input=b"must not spawn",
            capture_output=True,
            check=False,
            timeout=15,
        )
        require(result.returncode == 1, "capture failure did not exit 1")
        require(b"capture preflight" in result.stderr, "failure was not before spawn")
        require(not marker.exists(), "real child ran after capture failure")
        require(
            not list(capture.rglob("spawned.json")), "spawn record exists after capture failure"
        )
        return {"passed": True, "exit_code": 1, "child_started": False}
    finally:
        restored = subprocess.run(
            ["icacls", str(capture), "/remove:d", sid],
            capture_output=True,
            check=False,
            timeout=10,
        )
        require(restored.returncode == 0, "cannot restore disposable capture ACL")


def main() -> int:
    results: dict[str, Any] = {"schema": "codex-capture-shim-check/1"}
    try:
        require(sys.platform == "win32", "laptop check requires Windows")
        require(sys.prefix != sys.base_prefix, "run with the release venv's Python")
        with tempfile.TemporaryDirectory(prefix="capture-shim-check-") as temporary:
            root = Path(temporary)
            shim = root / "capture_shim.exe"
            results["build"] = build(shim)
            for name, check in (
                ("echo", echo),
                ("job_kill", job_kill),
                ("capture_failure", capture_failure),
            ):
                try:
                    results[name] = check(shim, root / name)
                except Exception as error:
                    results[name] = {
                        "passed": False,
                        "error": type(error).__name__,
                        "reason": str(error),
                    }
        results["passed"] = all(
            results[name]["passed"] for name in ("echo", "job_kill", "capture_failure")
        )
    except Exception as error:
        results.update(passed=False, error=type(error).__name__, reason=str(error))
    print(json.dumps(results, sort_keys=True))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
