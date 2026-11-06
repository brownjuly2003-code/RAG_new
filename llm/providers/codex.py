"""Subscription-backed final answers through the tool-free Codex CLI."""

from __future__ import annotations

import asyncio
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path, PureWindowsPath
from typing import Any

from llm.providers.base import LLMResponse, Message, ProviderUnavailable, flatten_messages

# CLI 0.166.0: enabled tool surfaces and their discovery/execution helpers.
# Keep the ordered list explicit: a CLI upgrade requires reviewing its features.
# Task 17b fact 1: disabling code_mode_host/code_mode_interrupt emits a gate-rejected warning.
DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "apps",
    "auth_elicitation",
    "browser_annotation_api",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "goals",
    "hooks",
    "image_generation",
    "in_app_browser",
    "in_app_chat",
    "in_app_dictation",
    "in_app_local_automation",
    "in_app_voice",
    "incremental_tools",
    "multi_agent",
    "plugin_discovery_prefetch",
    "plugin_sharing",
    "plugins",
    "prediction_preserve_parent_tools",
    "remote_plugin",
    "shell_snapshot",
    "skill_mcp_dependency_install",
    "skill_search",
    "sleep_tool",
    "tool_call_mcp_elicitation",
    "tool_suggest",
    "unified_exec_tty",
    "view_image",
    "workspace_dependencies",
    "write_stdin_approval",
)
_ENV_KEYS = ("PATH", "HOME", "CODEX_HOME", "LANG", "LC_ALL", "TMPDIR")
_WINDOWS_ENV_KEYS = ("PATH", "SystemRoot", "CODEX_HOME", "TEMP", "TMP")
_WRAPPER = Path(__file__).resolve().parents[1] / "codex_wrapper.txt"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

    class _WindowsJob:
        """An unnamed, non-inherited job owns only this call's process tree."""

        def __init__(self) -> None:
            self._handle: int | None = _kernel32.CreateJobObjectW(None, None)
            if not self._handle:
                raise OSError("job creation failed")
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            if not _kernel32.SetInformationJobObject(
                self._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):  # JobObjectExtendedLimitInformation
                self.close()
                raise OSError("job limits failed")

        def assign(self, process: subprocess.Popen[bytes]) -> None:
            handle = _kernel32.OpenProcess(0x0101, False, process.pid)  # SET_QUOTA | TERMINATE
            if not handle:
                raise OSError("process handle failed")
            try:
                if not _kernel32.AssignProcessToJobObject(self._handle, handle):
                    raise OSError("job assignment failed")
            finally:
                _kernel32.CloseHandle(handle)

        def close(self) -> None:
            if self._handle is not None:
                # Closing also kills descendants if explicit termination fails.
                _kernel32.TerminateJobObject(self._handle, 1)
                if not _kernel32.CloseHandle(self._handle):
                    raise OSError("job close failed")
                self._handle = None


def _windows_binary_exists(binary: str) -> bool:
    path = PureWindowsPath(binary)
    return path.is_absolute() and path.suffix.lower() == ".exe" and os.path.isfile(binary)


def _unavailable(reason: str) -> ProviderUnavailable:
    # Never attach CLI output, subprocess exceptions, prompts or environment values.
    return ProviderUnavailable(reason, provider_id="codex", reason=reason)


def _parse_answer(stdout: bytes, returncode: int, model: str) -> LLMResponse:
    completed = failed = error = forbidden_item = usage_limit = False
    answer = ""
    usage: dict[str, Any] = {}
    try:
        for line in stdout.decode("utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError
            kind = event["type"]
            if kind in {"turn.failed", "error"}:
                failed |= kind == "turn.failed"
                error |= kind == "error"
                detail = event.get("error") if kind == "turn.failed" else event
                message = str(detail.get("message", "") if isinstance(detail, dict) else "").lower()
                usage_limit |= "usage limit" in message or "usage_limit" in message
            elif kind == "turn.completed":
                completed = True
                usage = event.get("usage") or {}
                if not isinstance(usage, dict):
                    raise ValueError
            elif kind.startswith("item."):
                item = event.get("item")
                if not isinstance(item, dict):
                    raise ValueError
                item_type = item.get("type")
                forbidden_item |= item_type not in {"agent_message", "reasoning"}
                if item_type == "agent_message":
                    text = item.get("text", "")
                    if not isinstance(text, str):
                        raise ValueError
                    answer = text.strip()
    except (UnicodeError, ValueError, TypeError):
        raise _unavailable("codex_json") from None

    # A diagnostic warning item is forbidden too. Prefer the terminal failure's
    # actionable reason when present; a warning followed by success still rejects.
    for condition, reason in (
        (usage_limit, "codex_usage_limit"),
        (failed, "codex_turn_failed"),
        (error, "codex_error"),
        (forbidden_item, "codex_tool_use"),
        (returncode != 0, "codex_exit"),
        (not completed, "codex_incomplete"),
        (not answer, "codex_empty"),
    ):
        if condition:
            raise _unavailable(reason)
    counts = [usage.get(name, 0) for name in ("input_tokens", "output_tokens")]
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in counts):
        raise _unavailable("codex_json")
    return LLMResponse(
        text=answer,
        provider="codex",
        model=model,
        input_tokens=counts[0],
        output_tokens=counts[1],
        cost_usd=0.0,
        finish_reason="stop",
        metadata={
            "usage": {
                key: value
                for key, value in usage.items()
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            }
        },
    )


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class CodexProvider:
    provider_id = "codex"
    supports_tool_use = False
    supports_structured_output = False
    supports_streaming = True
    supports_batch = False
    # ProviderBackedLLM must run its normal failover/accounting path, then emit
    # one chunk. No partial CLI text may escape before the acceptance gate.
    streams_whole_response = True

    def __init__(
        self,
        *,
        binary: str = "codex",
        codex_home: str | None = None,
        model_name: str = "gpt-6-astra",
        effort: str = "xhigh",
        timeout_sec: float = 180.0,
        max_concurrent_calls: int = 1,
        context_window: int = 3584,
    ) -> None:
        if not math.isfinite(timeout_sec) or timeout_sec <= 0 or max_concurrent_calls < 1:
            raise ValueError("Codex timeout and concurrency must be positive")
        self.model_name = model_name
        self.context_window = context_window
        self._binary = binary
        self._codex_home = codex_home
        self._effort = effort
        self._timeout_sec = timeout_sec
        self._slots = threading.BoundedSemaphore(max_concurrent_calls)

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if tools:
            raise _unavailable("codex_tool_use")
        if os.name not in {"posix", "nt"}:
            raise _unavailable("codex_platform")
        if os.name == "nt" and not _windows_binary_exists(self._binary):
            raise _unavailable("codex_missing_binary")
        started = time.monotonic()
        deadline = started + self._timeout_sec
        if not self._slots.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise _unavailable("codex_timeout")
        try:
            keys = _WINDOWS_ENV_KEYS if os.name == "nt" else _ENV_KEYS
            environment = {key: os.environ[key] for key in keys if key in os.environ}
            if self._codex_home is not None:
                environment["CODEX_HOME"] = self._codex_home
            prompt = flatten_messages(messages).encode("utf-8")
            wrapped = _WRAPPER.read_bytes().replace(b"{prompt}", prompt, 1)
            with tempfile.TemporaryDirectory(prefix="rag-codex-") as cwd:
                argv = [
                    self._binary,
                    "exec",
                    "--json",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--sandbox",
                    "read-only",
                ]
                for feature in DISABLED_FEATURES:
                    argv += ["--disable", feature]
                argv += [
                    "-m",
                    self.model_name,
                    "-c",
                    f"model_reasoning_effort={json.dumps(self._effort)}",
                    "-C",
                    cwd,
                    "-",
                ]
                if time.monotonic() >= deadline:
                    raise _unavailable("codex_timeout")
                process: subprocess.Popen[bytes] | None = None
                close_job: Callable[[], None] | None = None
                try:
                    creationflags = 0
                    if sys.platform == "win32":
                        try:
                            job = _WindowsJob()
                        except OSError:
                            raise _unavailable("codex_job") from None
                        close_job = job.close
                        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                    try:
                        process = subprocess.Popen(
                            argv,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            cwd=cwd,
                            env=environment,
                            start_new_session=os.name == "posix",
                            creationflags=creationflags,
                        )
                    except FileNotFoundError:
                        raise _unavailable("codex_missing_binary") from None
                    except OSError:
                        raise _unavailable("codex_start") from None
                    if sys.platform == "win32":
                        try:
                            job.assign(process)
                        except OSError:
                            process.kill()
                            raise _unavailable("codex_job") from None
                    stdout, _ = process.communicate(
                        input=wrapped, timeout=max(0.0, deadline - time.monotonic())
                    )
                except subprocess.TimeoutExpired:
                    raise _unavailable("codex_timeout") from None
                except OSError:
                    raise _unavailable("codex_io") from None
                finally:
                    # Also reap descendants after an early leader exit or cancellation.
                    try:
                        if close_job is not None:
                            close_job()
                        elif process is not None:
                            _kill_group(process)
                    finally:
                        if process is not None:
                            if sys.platform == "win32":
                                process.wait()
                                for pipe in (process.stdin, process.stdout):
                                    if pipe is not None:
                                        pipe.close()
                            else:
                                process.communicate()
                response = _parse_answer(stdout, process.returncode, self.model_name)
                response.latency_ms = int((time.monotonic() - started) * 1000)
                return response
        except OSError:
            # Includes wrapper/temp-directory/cleanup errors; never expose paths.
            raise _unavailable("codex_io") from None
        finally:
            self._slots.release()

    async def generate_stream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str]:
        response = await asyncio.to_thread(self.generate, messages, **kwargs)
        yield response.text
