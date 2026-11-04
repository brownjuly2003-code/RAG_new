"""Windows boundary for the quality driver; importing this module does no work.

Process identities use integer Windows FILETIME ticks (100 ns since 1601).
Only WindowsSystem touches native APIs. Runtime accepts a synthetic System on
macOS/Linux. HTTP is loopback-only, without proxy discovery or redirects.
"""

from __future__ import annotations

import contextlib
import ctypes
import http.client
import io
import json
import os
import socket
import struct
import sys
import threading
import time
from collections.abc import Callable, Sequence
from ctypes import wintypes as w
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit


class Stop(RuntimeError):
    def __init__(self, code: int, reason: str):
        super().__init__(reason)
        self.code, self.reason = code, reason


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name == "posix":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def filetime(value: str) -> int:
    # Preserve the seventh fractional digit emitted by DateTime.ToString("o").
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    delta = parsed - datetime(1601, 1, 1, tzinfo=timezone.utc)
    fraction = value.split(".", 1)[1][:7] if "." in value else ""
    extra = int(fraction[6]) if len(fraction) == 7 and fraction[6].isdigit() else 0
    return (delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10 + extra


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int
    image: str
    created: int
    command: str = ""

    def record(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k != "command"}


class System(Protocol):
    def snapshot(self) -> list[Process]: ...
    def alive(self, process: Process) -> bool: ...
    def terminate(self, process: Process) -> bool: ...
    def clock_pair(self) -> tuple[float, float]: ...
    def inhibit(self, enabled: bool) -> bool: ...
    def launch(self, argv: list[str], cwd: Path, log: Path) -> Process: ...
    def listeners(self, port: int) -> list[int]: ...


def descendants(processes: list[Process], roots: list[Process]) -> list[Process]:
    """Creation ordering prevents a reused parent PID from claiming older children."""
    found = {(p.pid, p.created): p for p in roots}
    newest = {
        pid: max(p.created for p in processes if p.pid == pid) for pid in {p.pid for p in processes}
    }
    ordered: list[Process] = []
    while True:
        added = [
            p
            for p in processes
            if (p.pid, p.created) not in found
            and any(
                p.parent == r.pid
                and p.created >= r.created
                and newest.get(r.pid, r.created) == r.created
                for r in found.values()
            )
        ]
        if not added:
            return ordered
        ordered.extend(added)
        found.update({(p.pid, p.created): p for p in added})


def stop_tree(system: System, roots: list[Process], observed: Sequence[Process] = ()) -> list[int]:
    """Leaf first, always re-verifying the creation time on the terminating handle."""
    historical = descendants(list(observed), roots)
    family = descendants([*observed, *system.snapshot()], [*roots, *historical])
    ordered = list(reversed(family)) + list(reversed(historical)) + list(reversed(roots))
    seen: set[tuple[int, int]] = set()
    stopped = []
    for process in ordered:
        identity = (process.pid, process.created)
        if identity in seen:
            continue
        seen.add(identity)
        if process.image.lower().startswith("ollama") and process.image.lower().endswith(".exe"):
            continue  # Observe Ollama only, including an unexpected stand descendant.
        if system.alive(process):
            if not system.terminate(process):
                raise Stop(5, "verified_stop_failed")
            stopped.append(process.pid)
        if system.alive(process):
            raise Stop(5, "verified_exit_failed")
    return stopped


def port_taken(port: int = 8002) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0


class WindowsSystem:
    """Toolhelp + process handles, never WMI, taskkill or image-name termination."""

    def __init__(self, detach: Callable[..., Any]):
        if sys.platform != "win32":
            raise Stop(1, "windows_runtime_required")
        self.detach = detach
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        signatures = {
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "GetProcessTimes": ([w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)], w.BOOL),
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
            "Process32FirstW": ([w.HANDLE, ctypes.c_void_p], w.BOOL),
            "Process32NextW": ([w.HANDLE, ctypes.c_void_p], w.BOOL),
            "GetTickCount64": ([], ctypes.c_ulonglong),
            "QueryUnbiasedInterruptTime": ([ctypes.POINTER(ctypes.c_ulonglong)], w.BOOL),
            "SetThreadExecutionState": ([w.DWORD], w.DWORD),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = arguments, result
        self.ntdll.NtQueryInformationProcess.argtypes = [
            w.HANDLE,
            w.ULONG,
            ctypes.c_void_p,
            w.ULONG,
            ctypes.POINTER(w.ULONG),
        ]
        self.ntdll.NtQueryInformationProcess.restype = w.LONG
        self.children: list[Any] = []

    def _created(self, handle: Any) -> int:
        stamps = [w.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in stamps)):
            raise Stop(5, "process_time_unreadable")
        return (stamps[0].dwHighDateTime << 32) | stamps[0].dwLowDateTime

    def _command(self, handle: Any) -> str:
        class UnicodeString(ctypes.Structure):
            _fields_ = [("length", w.USHORT), ("maximum", w.USHORT), ("buffer", ctypes.c_void_p)]

        size = w.ULONG()
        query = self.ntdll.NtQueryInformationProcess
        query(handle, 60, None, 0, ctypes.byref(size))
        if not 0 < size.value < 1024 * 1024:
            raise Stop(5, "python_command_unreadable")
        buffer = ctypes.create_string_buffer(size.value)
        if query(handle, 60, buffer, size.value, ctypes.byref(size)) < 0:
            raise Stop(5, "python_command_unreadable")
        value = UnicodeString.from_buffer(buffer)
        return ctypes.wstring_at(value.buffer, value.length // 2)

    def snapshot(self) -> list[Process]:
        class Entry(ctypes.Structure):
            _fields_ = [
                ("size", w.DWORD),
                ("usage", w.DWORD),
                ("pid", w.DWORD),
                ("heap", ctypes.c_size_t),
                ("module", w.DWORD),
                ("threads", w.DWORD),
                ("parent", w.DWORD),
                ("priority", w.LONG),
                ("flags", w.DWORD),
                ("image", w.WCHAR * 260),
            ]

        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise Stop(5, "snapshot_failed")
        result = []
        try:
            entry = Entry()
            entry.size = ctypes.sizeof(entry)
            more = self.kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while more:
                image = entry.image.lower()
                handle = self.kernel.OpenProcess(0x1000, False, entry.pid)
                created, command = 0, ""
                if handle:
                    try:
                        created = self._created(handle)
                        if image.startswith("python"):
                            command = self._command(handle)
                    finally:
                        self.kernel.CloseHandle(handle)
                elif image.startswith("python") or image == "codex.exe":
                    # A process may exit between the snapshot and OpenProcess.
                    if ctypes.get_last_error() != 87:
                        raise Stop(5, "watched_process_unreadable")
                result.append(Process(entry.pid, entry.parent, entry.image, created, command))
                more = self.kernel.Process32NextW(snapshot, ctypes.byref(entry))
            return result
        finally:
            self.kernel.CloseHandle(snapshot)

    def alive(self, process: Process) -> bool:
        handle = self.kernel.OpenProcess(0x1000, False, process.pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            raise Stop(5, "process_identity_unreadable")
        try:
            code = w.DWORD()
            if not self.kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise Stop(5, "process_exit_unreadable")
            return self._created(handle) == process.created and code.value == 259
        finally:
            self.kernel.CloseHandle(handle)

    def terminate(self, process: Process) -> bool:
        handle = self.kernel.OpenProcess(0x1000 | 0x100000 | 1, False, process.pid)
        if not handle:
            return False
        try:
            if not process.created or self._created(handle) != process.created:
                return False
            if not self.kernel.TerminateProcess(handle, 1):
                return False
            return self.kernel.WaitForSingleObject(handle, 10000) == 0
        finally:
            self.kernel.CloseHandle(handle)

    def clock_pair(self) -> tuple[float, float]:
        unbiased = ctypes.c_ulonglong()
        if not self.kernel.QueryUnbiasedInterruptTime(ctypes.byref(unbiased)):
            raise Stop(5, "suspend_clock_failed")
        return self.kernel.GetTickCount64() / 1000, unbiased.value / 10_000_000

    def inhibit(self, enabled: bool) -> bool:
        return bool(self.kernel.SetThreadExecutionState(0x80000000 | (1 if enabled else 0)))

    def listeners(self, port: int) -> list[int]:
        class Row(ctypes.Structure):
            _fields_ = [
                (name, w.DWORD)
                for name in ("state", "address", "port", "remote", "remote_port", "pid")
            ]

        helper = ctypes.WinDLL("iphlpapi", use_last_error=True)
        query = helper.GetExtendedTcpTable
        query.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(w.DWORD),
            w.BOOL,
            w.ULONG,
            w.ULONG,
            w.ULONG,
        ]
        query.restype = w.DWORD
        size = w.DWORD()
        query(None, ctypes.byref(size), False, socket.AF_INET, 3, 0)  # TCP_TABLE_OWNER_PID_LISTENER
        buffer = ctypes.create_string_buffer(size.value)
        if query(buffer, ctypes.byref(size), False, socket.AF_INET, 3, 0):
            raise Stop(5, "listener_snapshot_failed")
        count = w.DWORD.from_buffer(buffer).value
        result = []
        for index in range(count):
            row = Row.from_buffer(buffer, ctypes.sizeof(w.DWORD) + index * ctypes.sizeof(Row))
            address = socket.inet_ntoa(struct.pack("<I", row.address))
            if socket.ntohs(row.port & 0xFFFF) == port and address in {"0.0.0.0", "127.0.0.1"}:  # nosec B104 # Observing existing listeners; this does not bind a socket.
                result.append(row.pid)
        return result

    def launch(self, argv: list[str], cwd: Path, log: Path) -> Process:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("ab") as output:
            child = self.detach(argv, cwd=cwd, stdout=output)
        self.children.append(child)  # Retain the Popen handle for this invocation.
        handle = self.kernel.OpenProcess(0x1000, False, child.pid)
        if not handle:
            raise Stop(5, "launcher_identity_unavailable")
        try:
            return Process(child.pid, os.getpid(), "python.exe", self._created(handle))
        finally:
            self.kernel.CloseHandle(handle)


class Watch:
    def __init__(self, system: System, path: Path, roots: Callable[[], list[Process]]):
        self.system, self.path, self.roots = system, path, roots
        self.baseline: set[tuple[int, int]] | None = None
        self.previous: dict[int, dict[str, Any]] = {}
        self.observed: dict[tuple[int, int], Process] = {}
        self.pair: tuple[float, float] | None = None
        self.failure: Stop | None = None
        self.events: list[dict[str, Any]] = []
        self.ollama: set[tuple[int, int]] = set()
        self.done = threading.Event()
        self.mutex = threading.RLock()
        self.thread: threading.Thread | None = None

    def tick(self) -> None:
        with self.mutex:
            try:
                pair = self.system.clock_pair()
                if self.pair and (pair[0] - self.pair[0]) - (pair[1] - self.pair[1]) > 30:
                    self.events.append({"kind": "suspend", "utc": utc()})
                    raise Stop(5, "suspend_detected")
                self.pair = pair
                processes = self.system.snapshot()
                identities = {(p.pid, p.created) for p in processes}
                initial = self.baseline is None
                if initial:
                    self.baseline = identities
                current = {p.pid: p.record() for p in processes}
                changes = [v for pid, v in current.items() if self.previous.get(pid) != v]
                removed = sorted(set(self.previous) - set(current))
                if changes or removed or initial:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("ab") as stream:
                        stream.write(
                            (
                                json.dumps(
                                    {
                                        "utc": utc(),
                                        "processes": changes,
                                        "exited": removed,
                                        "initial": initial,
                                    }
                                )
                                + "\n"
                            ).encode()
                        )
                        stream.flush()
                        os.fsync(stream.fileno())
                self.previous = current
                roots = self.roots()
                family = descendants([*self.observed.values(), *processes], roots)
                self.observed.update({(p.pid, p.created): p for p in [*roots, *family]})
                owned = set(self.observed)
                self.ollama.update(
                    (p.pid, p.created)
                    for p in processes
                    if p.image.lower().startswith("ollama") and p.image.lower().endswith(".exe")
                )
                allowed_pids = {p.pid for p in processes if (p.pid, p.created) in owned}
                if any(pid not in allowed_pids for pid in self.system.listeners(8002)):
                    raise Stop(1 if initial else 2, "outside_product_listener")
                for p in processes:
                    identity = (p.pid, p.created)
                    image, command = p.image.lower(), p.command.lower().replace("\\", "/")
                    if image.startswith("ollama") and image.endswith(".exe"):
                        self.ollama.add(identity)
                        raise Stop(1 if initial else 2, "ollama_observed")
                    if (
                        image == "codex.exe"
                        and identity not in (self.baseline or set())
                        and identity not in owned
                    ):
                        raise Stop(2, "outside_codex")
                    if (
                        image.startswith("python")
                        and identity not in owned
                        and "deploy/windows/start.py" in command
                    ):
                        raise Stop(1 if initial else 2, "second_product_launcher")
            except Stop as error:
                if self.failure is None:
                    self.failure = error
            except Exception:
                self.failure = self.failure or Stop(5, "process_watch_failed")

    def check(self) -> None:
        if self.failure:
            raise self.failure

    def start(self) -> None:
        self.tick()
        self.check()

        def worker() -> None:
            while not self.done.wait(2):
                self.tick()

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.done.set()
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                self.failure = self.failure or Stop(5, "watch_join_failed")


class HTTP:
    def __init__(self, port: int = 8002):
        self.port = port

    def json(self, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(
                "GET" if body is None else "POST",
                path,
                None if body is None else json.dumps(body).encode(),
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
        finally:
            connection.close()

    def ready(self) -> bool:
        try:
            return self.json("/api/health/ready")[0] == 200
        except (OSError, ValueError, http.client.HTTPException):
            return False

    def stream(
        self,
        question: str,
        token: str,
        path: Path,
        ceiling: float,
        check: Callable[[], None],
        halt: Callable[[], None],
    ) -> dict[str, Any]:
        """A supervising deadline bounds even a peer that trickles endless bytes."""
        started = time.monotonic()
        outcome: dict[str, Any] = {"dispatch_utc": utc(), "http_status": None, "result": None}
        done = threading.Event()
        aborted = threading.Event()
        persistence_lock = threading.Lock()
        # The supervisor below enforces the ceiling; a socket timeout equal to it
        # could fire first and turn a hung stand into a plain transport error.
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=ceiling + 5)

        def worker() -> None:
            try:
                connection.request(
                    "POST",
                    "/api/ask/stream",
                    json.dumps({"question": question}).encode(),
                    {"Content-Type": "application/json", "Authorization": "Bearer " + token},
                )
                response = connection.getresponse()
                outcome["http_status"] = response.status
                data: list[str] = []
                with path.open("ab") as stream:
                    while True:
                        line = response.readline()
                        if not line:
                            if data:
                                raise ValueError("unterminated SSE event")
                            break
                        stream.write(line)
                        stream.flush()
                        os.fsync(stream.fileno())
                        try:
                            text = line.decode("utf-8").rstrip("\r\n")
                            if text == "":
                                if data:
                                    event = json.loads("\n".join(data))
                                    if not isinstance(event, dict):
                                        raise ValueError("invalid SSE object")
                                    if event.get("type") == "result":
                                        if outcome["result"] is not None:
                                            raise ValueError("duplicate result")
                                        outcome["result"] = event
                                        outcome["elapsed_s"] = time.monotonic() - started
                                        outcome["result_utc"] = utc()
                                    data = []
                            elif text.startswith("data:"):
                                data.append(text[5:].lstrip(" "))
                            elif not text.startswith((":", "event:", "id:", "retry:")):
                                raise ValueError("broken SSE")
                        except ValueError:
                            # Malformed events do not cancel the running graph.
                            # Retain and drain bytes until EOF or the full ceiling.
                            outcome["error"] = "broken_stream"
                            data = []
                if outcome["result"] is None:
                    outcome["error"] = "missing_result"
            except Exception:
                outcome["error"] = "broken_stream"
            finally:
                if outcome.get("error"):
                    outcome["elapsed_s"] = time.monotonic() - started
                outcome.setdefault("elapsed_s", time.monotonic() - started)
                outcome.setdefault("result_utc", utc())
                # Recovery can finish an ended stream even if the driver dies
                # between transport completion and reduction of its attempt.
                with persistence_lock:
                    if not aborted.is_set():
                        try:
                            atomic(path.parent / "response.json", outcome)
                        except OSError:
                            outcome["error"] = "response_persistence_failed"
                done.set()

        threading.Thread(target=worker, daemon=True).start()
        try:
            while not done.wait(0.05):
                check()
                if time.monotonic() - started >= ceiling:
                    with persistence_lock:
                        aborted.set()
                    halt()
                    result = dict(outcome)
                    result.update(
                        error="hung_stand",
                        immediate=True,
                        elapsed_s=time.monotonic() - started,
                        result_utc=utc(),
                    )
                    return result
            check()
            return dict(outcome)
        except Stop:
            with persistence_lock:
                aborted.set()
            halt()
            raise
        finally:
            connection.close()


class Runtime:
    def __init__(
        self, config: dict[str, Any], folder: Path, system: System, http: HTTP | None = None
    ):
        self.config, self.folder, self.system = config, folder, system
        self.http = http or HTTP()
        self.path = folder / "stand.json"
        self.stand = json.loads(self.path.read_bytes()) if self.path.exists() else None
        self.token: str | None = None
        probe_path = folder / "probe-process.json"
        held = json.loads(probe_path.read_bytes()) if probe_path.exists() else None
        self.probe_process: Process | None = Process(**held) if held else None
        self.watch = Watch(system, folder / "processes.jsonl", self.roots)
        # Recover verified descendants observed in earlier chunks, including a
        # child whose parent has since exited. Incomplete crash tails are ignored.
        if self.watch.path.exists():
            previous: dict[int, Process] = {}
            with self.watch.path.open("rb") as stream:
                for line in stream:
                    if not line.endswith(b"\n"):
                        break
                    event = json.loads(line)
                    for pid in event["exited"]:
                        previous.pop(pid, None)
                    previous.update({p["pid"]: Process(**p) for p in event["processes"]})
                    family = descendants(
                        [*self.watch.observed.values(), *previous.values()], self.roots()
                    )
                    self.watch.observed.update({(p.pid, p.created): p for p in family})

    def roots(self) -> list[Process]:
        # The listener is evidence, never an independent root of ownership.
        roots = (
            [Process(**self.stand["processes"][0])]
            if self.stand and self.stand["processes"]
            else []
        )
        return roots + ([self.probe_process] if self.probe_process else [])

    def listener_processes(self) -> list[Process]:
        """Verify all listener owners through the launcher, including venv redirectors."""
        if not self.stand or not self.stand["processes"]:
            return []
        launcher = Process(**self.stand["processes"][0])
        if not self.system.alive(launcher):
            return []
        owners = set(self.system.listeners(self.http.port))
        processes = self.system.snapshot()
        with self.watch.mutex:
            family = descendants([*self.watch.observed.values(), *processes], [launcher])
            self.watch.observed.update({(p.pid, p.created): p for p in family})
        identities = {(p.pid, p.created) for p in family}
        listeners = [
            p
            for p in processes
            if p.pid in owners and (p.pid, p.created) in identities and self.system.alive(p)
        ]
        return listeners if owners and {p.pid for p in listeners} == owners else []

    def preflight(self) -> None:
        # Persist the initial snapshot before readiness/login or any request.
        self.watch.tick()
        self.watch.check()
        if (
            self.system.listeners(self.http.port) or port_taken(self.http.port)
        ) and not self.listener_processes():
            raise Stop(1, "unknown_listener_8002")

    def begin(self) -> None:
        if not self.system.inhibit(True):
            self.watch.events.append({"kind": "sleep_failed", "utc": utc()})
            raise Stop(5, "sleep_inhibition_failed")
        self.watch.events.append({"kind": "sleep_held", "utc": utc()})
        self.watch.start()

    def end(self) -> None:
        self.watch.close()
        if not self.system.inhibit(False):
            raise Stop(5, "sleep_clear_failed")
        self.watch.events.append({"kind": "sleep_cleared", "utc": utc()})
        self.watch.check()

    def stop(self) -> None:
        with self.watch.mutex:
            stop_tree(self.system, self.roots(), list(self.watch.observed.values()))
            self.stand, self.token, self.probe_process = None, None, None
            atomic(self.path, None)
            atomic(self.folder / "probe-process.json", None)

    def ensure(self, key: str) -> bool:
        if self.stand:
            launcher = Process(**self.stand["processes"][0])
            if (
                sum(
                    p.parent == launcher.pid
                    and p.created >= launcher.created
                    and p.image.lower().startswith("python")
                    for p in self.system.snapshot()
                )
                > 1
            ):
                raise Stop(5, "multiple_direct_python_children")
            listeners = self.listener_processes()
            if self.stand["key"] == key and listeners and self.http.ready():
                self.stand["processes"] = [
                    self.stand["processes"][0],
                    *(p.record() for p in listeners),
                ]
                atomic(self.path, self.stand)
                return bool(self.stand.get("cold", False))
            self.stop()
        if port_taken(self.http.port):
            raise Stop(2, "listener_appeared_after_admission")
        app = Path(self.config["stands"][key]["app"])
        with self.watch.mutex:
            try:
                launcher = self.system.launch(
                    [
                        self.config["release"]["python"],
                        "-I",
                        str(app / "deploy/windows/start.py"),
                        self.config["stands"][key]["env"],
                    ],
                    app,
                    self.folder / (key + "-launcher.log"),
                )
            except Exception as error:
                raise Stop(5, "stand_launch_failed") from error
            self.stand = {"key": key, "cold": True, "processes": [launcher.record()]}
            atomic(self.path, self.stand)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            self.watch.tick()
            self.watch.check()
            children = [
                p
                for p in self.system.snapshot()
                if p.parent == launcher.pid
                and p.created >= launcher.created
                and p.image.lower().startswith("python")
            ]
            if len(children) > 1:
                raise Stop(5, "multiple_direct_python_children")
            listeners = self.listener_processes()
            if listeners and self.http.ready() and time.monotonic() < deadline:
                self.stand["processes"] = [launcher.record(), *(p.record() for p in listeners)]
                atomic(self.path, self.stand)
                return True
            if not self.system.alive(launcher):
                break
            self.watch.done.wait(0.25)
        self.stop()
        raise Stop(5, "readiness_timeout")

    def login(self, key: str) -> None:
        if self.token is None:
            try:
                auth = json.loads(Path(self.config["stands"][key]["auth_file"]).read_bytes())
                status, body = self.http.json(
                    "/api/auth/login",
                    {"username": auth["admin_username"], "password": auth["admin_password"]},
                )
            except Exception as error:
                raise Stop(5, "login_failed") from error
            if (
                status != 200
                or not isinstance(body, dict)
                or not isinstance(body.get("access_token"), str)
                or not body["access_token"]
            ):
                raise Stop(5, "login_failed")
            self.token = body["access_token"]

    def ask(self, question: str, path: Path, ceiling: float) -> dict[str, Any]:
        if self.stand:
            self.stand["cold"] = False
            atomic(self.path, self.stand)
        return self.http.stream(
            question, self.token or "", path, ceiling, self.watch.check, self.stop
        )

    def call_gone(self, call: Any) -> bool:
        if not call.start or not call.process_started:
            return False
        shim = Process(
            call.start["shim_pid"], 0, "capture_shim.exe", filetime(call.start["process_start_utc"])
        )
        processes = self.system.snapshot()
        candidates = [
            p
            for p in [*self.watch.observed.values(), *processes]
            if p.pid == shim.pid and abs(p.created - shim.created) <= 10_000
        ]
        if candidates:
            actual = min(
                candidates, key=lambda p: (p not in processes, abs(p.created - shim.created))
            )
            delta = actual.created - shim.created
            if delta and not any(
                e.get("kind") == "shim_creation_delta"
                and e.get("pid") == shim.pid
                and e.get("recorded_created") == shim.created
                for e in self.watch.events
            ):
                self.watch.events.append(
                    {
                        "kind": "shim_creation_delta",
                        "pid": shim.pid,
                        "recorded_created": shim.created,
                        "delta_ticks": delta,
                        "utc": utc(),
                    }
                )
            # All subsequent liveness/termination checks still use exact native ticks.
            shim = actual
        family = descendants([*self.watch.observed.values(), *processes], [shim])
        if self.system.alive(shim) or any(self.system.alive(p) for p in family):
            return False
        if call.spawned:
            # spawned.json has no creation time. A matching live PID must have
            # been observed in the verified tree, or absence cannot be proved.
            for p in processes:
                if p.pid == call.spawned["child_pid"]:
                    if p.created <= filetime(call.spawned["utc"]):
                        return False
        return True

    def tickets(self, key: str, session_id: str | None) -> dict[str, Any]:
        if not session_id:
            return {"count": 0, "rows": [], "session_absent": True}
        import psycopg2
        from psycopg2.extensions import make_dsn

        from deploy.windows import start

        env = start.read_service_env(Path(self.config["stands"][key]["env"]))
        url = urlsplit(env["DATABASE_URL"])
        if url.scheme not in {"postgresql", "postgresql+asyncpg", "postgresql+psycopg2"}:
            raise Stop(5, "database_scheme_invalid")
        dsn = make_dsn(
            host=url.hostname,
            port=url.port or 5432,
            user=unquote(url.username or ""),
            password=unquote(url.password or ""),
            dbname=unquote(url.path.lstrip("/")),
            connect_timeout=5,
        )
        with psycopg2.connect(dsn) as connection:
            connection.set_session(readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = 5000")
                cursor.execute(
                    "SELECT id, delivery_state, status FROM escalated_tickets WHERE session_id = %s ORDER BY id",
                    (session_id,),
                )
                rows = [
                    {"id": str(row[0]), "delivery_state": row[1], "status": row[2]}
                    for row in cursor.fetchall()
                ]
        return {"count": len(rows), "rows": rows}

    def probe(self, key: str, path: Path, ceiling: float) -> dict[str, Any]:
        app = Path(self.config["stands"][key]["app"])
        started, dispatched = time.monotonic(), utc()
        with self.watch.mutex:
            self.probe_process = self.system.launch(
                [
                    self.config["release"]["python"],
                    "-I",
                    "-B",
                    str(Path(__file__).resolve()),
                    "--probe-worker",
                    str(app),
                    self.config["stands"][key]["env"],
                ],
                app,
                path,
            )
            atomic(self.folder / "probe-process.json", self.probe_process.record())
        while self.system.alive(self.probe_process):
            self.watch.check()
            if time.monotonic() - started >= ceiling:
                self.stop()
                return {
                    "error": "hung_stand",
                    "immediate": True,
                    "result": None,
                    "dispatch_utc": dispatched,
                    "result_utc": utc(),
                    "elapsed_s": time.monotonic() - started,
                }
            self.watch.done.wait(0.05)
        try:
            result = json.loads(path.read_bytes())
        except (ValueError, OSError):
            result = {}
        worker_error = not isinstance(result, dict) or not result or bool(result.get("error"))
        return {
            "result": result,
            "error": "probe_worker_error" if worker_error else None,
            "http_status": None,
            "dispatch_utc": dispatched,
            "result_utc": utc(),
            "elapsed_s": time.monotonic() - started,
        }


def probe_worker(app: Path, env_file: Path) -> int:
    """The only model call in this module; reached only by explicit probe argv."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sys.path.insert(0, str(app))
            from deploy.windows import start

            deployment = start.read_service_env(env_file)
            environment = start.api_environment(deployment)
            os.environ.clear()
            os.environ.update(environment)
            start.check_values(deployment)
            from config.provider_schema import load_provider_registry
            from config.settings import Settings, _apply_deployed_settings
            from llm.providers.runtime import _instantiate_provider

            settings = Settings()
            _apply_deployed_settings(settings)
            target = (
                load_provider_registry(settings.provider_registry_path)
                .get_profile("codex-only")
                .answer
            )
            if target is None or settings.llm_provider_profile != "codex-only":
                raise ValueError("answer profile")
            provider = _instantiate_provider(
                settings,
                target.provider,
                target.model,
                effort=target.effort,
                target_timeout_sec=target.timeout_sec,
            )
            response = provider.generate([{"role": "user", "content": "Reply with exactly OK."}])
            value = {"text": response.text, "provider": response.provider, "model": response.model}
        print(json.dumps(value))
        return 0
    except Exception:
        print(
            json.dumps({"text": "", "provider": None, "model": None, "error": "probe_worker_error"})
        )
        return 5


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--probe-worker":
        raise SystemExit(probe_worker(Path(sys.argv[2]), Path(sys.argv[3])))
    raise SystemExit(1)
