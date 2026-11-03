"""Windows boundary contracts, simulated on CI except for the native Job Object test."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from llm.providers import codex
from llm.providers.base import ProviderUnavailable

BINARY = "C:/native/codex.exe"
MESSAGES = [{"role": "user", "content": "A small offline question."}]
SUCCESS = b"\n".join(
    json.dumps(event).encode()
    for event in (
        {"type": "thread.started", "thread_id": "test-thread"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Accepted."}},
        {"type": "turn.completed"},
    )
)


@pytest.fixture
def windows(monkeypatch):
    calls = []
    environment = {
        "PATH": "C:/Windows/System32",
        "SystemRoot": "C:/Windows",
        "CODEX_HOME": "C:/profile",
        "TEMP": "C:/temp",
        "TMP": "C:/tmp",
        "HOME": "do-not-forward-home",
        "LANG": "do-not-forward-lang",
        "LC_ALL": "do-not-forward-locale",
        "TMPDIR": "do-not-forward-tempdir",
        "DATABASE_URL": "do-not-forward-database",
        "OPENAI_API_KEY": "do-not-forward-auth",
    }
    # Replace module references, not global os.name/sys.platform (pathlib and pytest use them).
    monkeypatch.setattr(
        codex,
        "os",
        SimpleNamespace(
            name="nt", environ=environment, path=SimpleNamespace(isfile=lambda path: path == BINARY)
        ),
    )
    monkeypatch.setattr(codex, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(codex.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)

    class Process:
        returncode = 0
        stdin = io.BytesIO()
        stdout = io.BytesIO()

        def communicate(self, **kwargs):
            calls.append(("communicate", kwargs))
            if state.failure == "timeout":
                raise subprocess.TimeoutExpired("private", 1)
            if state.failure == "io":
                raise OSError("private")
            if state.failure == "cancel":
                raise KeyboardInterrupt
            return (b"invalid-json" if state.failure == "json" else SUCCESS), None

        def kill(self):
            calls.append(("kill",))

        def wait(self):
            calls.append(("wait",))
            return self.returncode

    class Job:
        def __init__(self):
            calls.append(("create-job",))
            if state.failure == "create":
                raise OSError("private")

        def assign(self, process):
            calls.append(("assign", process))
            if state.failure == "assign":
                raise OSError("private")

        def close(self):
            calls.append(("close-job",))

    def popen(argv, **kwargs):
        calls.append(("spawn", argv, kwargs))
        if state.failure == "missing":
            raise FileNotFoundError("private")
        if state.failure == "spawn":
            raise OSError("private")
        return state.process

    state = SimpleNamespace(calls=calls, environment=environment, failure=None, process=Process())
    monkeypatch.setattr(codex, "_WindowsJob", Job, raising=False)
    monkeypatch.setattr(codex.subprocess, "Popen", popen)
    monkeypatch.setattr(codex, "_kill_group", lambda _: pytest.fail("POSIX kill on Windows"))
    return state


@pytest.mark.parametrize("home", [None, "C:/explicit-profile"])
def test_windows_request_environment_binary_argv_and_job_order(windows, home):
    result = codex.CodexProvider(binary=BINARY, codex_home=home).generate(MESSAGES)
    assert result.text == "Accepted."
    assert [call[0] for call in windows.calls] == [
        "create-job",
        "spawn",
        "assign",
        "communicate",
        "close-job",
        "wait",
    ]
    _, argv, kwargs = windows.calls[1]
    assert argv[0] == BINARY
    assert "code_mode_host" not in argv and "code_mode_interrupt" not in argv
    assert kwargs["creationflags"] == 0x200
    assert kwargs["start_new_session"] is False
    assert kwargs.get("shell", False) is False
    assert kwargs["env"] == {
        key: (home or windows.environment[key]) if key == "CODEX_HOME" else windows.environment[key]
        for key in ("PATH", "SystemRoot", "CODEX_HOME", "TEMP", "TMP")
    }
    assert windows.process.stdin.closed and windows.process.stdout.closed


@pytest.mark.parametrize(
    "binary",
    [
        "codex",
        "codex.exe",
        "C:codex.exe",
        "/codex.exe",
        "C:/native/codex.cmd",
        "C:/missing.exe",
        "C:/directory.exe",
    ],
)
def test_windows_rejects_binary_before_spawn(windows, binary):
    with pytest.raises(ProviderUnavailable, match="^codex_missing_binary$"):
        codex.CodexProvider(binary=binary).generate(MESSAGES)
    assert windows.calls == []


@pytest.mark.parametrize(
    "failure,reason",
    [
        ("create", "codex_job"),
        ("assign", "codex_job"),
        ("spawn", "codex_start"),
        ("missing", "codex_missing_binary"),
        ("timeout", "codex_timeout"),
        ("io", "codex_io"),
        ("json", "codex_json"),
    ],
)
def test_windows_failures_release_job_and_slot(windows, failure, reason):
    windows.failure = failure
    provider = codex.CodexProvider(binary=BINARY)
    with pytest.raises(ProviderUnavailable, match=f"^{reason}$"):
        provider.generate(MESSAGES)
    names = [call[0] for call in windows.calls]
    assert names.count("close-job") == (0 if failure == "create" else 1)
    assert ("kill" in names) == (failure == "assign")
    assert ("wait" in names) == (failure not in {"create", "spawn", "missing"})
    assert provider._slots.acquire(blocking=False)
    provider._slots.release()


def test_windows_cancellation_still_closes_job(windows):
    windows.failure = "cancel"
    with pytest.raises(KeyboardInterrupt):
        codex.CodexProvider(binary=BINARY).generate(MESSAGES)
    assert [call[0] for call in windows.calls][-2:] == ["close-job", "wait"]


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows Job Object integration")
@pytest.mark.parametrize("terminate", [True, False])
def test_native_job_ends_descendants_and_spares_other_processes(terminate):
    import ctypes
    from ctypes import wintypes

    # The child waits for stdin so it cannot spawn before assignment to the job.
    script = (
        "import subprocess, sys; sys.stdin.readline(); "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "print(p.pid, flush=True)"
    )
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = codex._WindowsJob()
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    process = None
    descendant = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        job.assign(process)
        process.stdin.write(b"go\n")
        process.stdin.flush()
        descendant_pid = int(process.stdout.readline())
        descendant = kernel.OpenProcess(0x00100000, False, descendant_pid)  # SYNCHRONIZE
        assert descendant
        process.wait(timeout=10)
        if terminate:
            job.close()
        else:
            # Prove KILL_ON_JOB_CLOSE independently of explicit TerminateJobObject.
            assert kernel.CloseHandle(job._handle)
            job._handle = None
        assert kernel.WaitForSingleObject(descendant, 5000) == 0
        assert unrelated.poll() is None
    finally:
        job.close()
        if descendant:
            kernel.CloseHandle(descendant)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            process.stdin.close()
            process.stdout.close()
        unrelated.kill()
        unrelated.wait(timeout=10)
