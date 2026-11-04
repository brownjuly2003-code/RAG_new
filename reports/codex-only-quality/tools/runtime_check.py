"""Opt-in Windows native proof; no product, database or model requests.

runtime_check.py --private DIR [--python RELEASE_VENV_PYTHON] [--shim BUILT_EXE]
The optional shim is copied/configured privately to forward only to a sleeping
Python worker. Its installed configuration is never changed. Omission prints SKIP.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess  # nosec B404 # Fixed local dummy workers only; no shell.
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stand_runtime as sr  # noqa: E402 # Dummy workers use isolated Python (-I).


def dummy_tree(worker: str, ready: Path) -> None:
    if worker == "listener":
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            sr.atomic(ready, {"pid": os.getpid(), "port": listener.getsockname()[1]})
            time.sleep(300)
        return
    next_worker = "child" if worker == "parent" else "listener"
    child = subprocess.Popen(  # nosec B603 # Only this file's dummy branches.
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--dummy",
            next_worker,
            "--ready",
            str(ready),
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        time.sleep(300)
    finally:
        child.wait(timeout=1)


def check_shim(system: sr.WindowsSystem, private: Path, python: Path, shim: Path) -> None:
    folder = private / "shim-proof"
    folder.mkdir()
    executable = folder / "capture_shim.exe"
    shutil.copyfile(shim, executable)
    capture = folder / "capture"
    sr.atomic(folder / "capture_shim.json", {"real_exe": str(python), "capture_root": str(capture)})
    parent = system.launch(
        [str(executable), "-I", str(Path(__file__).resolve()), "--dummy", "sleeper"],
        folder,
        folder / "shim.log",
    )
    observed: dict[tuple[int, int], sr.Process] = {}
    try:
        deadline = time.monotonic() + 15
        start = None
        while time.monotonic() < deadline:
            family = sr.descendants([*observed.values(), *system.snapshot()], [parent])
            observed.update({(p.pid, p.created): p for p in family})
            records = list(capture.glob("calls/*/start.json"))
            if len(records) == 1 and (records[0].parent / "spawned.json").exists():
                try:
                    start = json.loads(records[0].read_bytes())
                except ValueError:
                    pass  # The durable writer may still be flushing the record.
                else:
                    break
            if not system.alive(parent):
                break
            time.sleep(0.1)
        if not start or start["shim_pid"] != parent.pid or not system.alive(parent):
            raise sr.Stop(5, "live shim start record unavailable")
        # CaptureShim.Stamp(self.StartTime) is DateTime.ToUniversalTime().ToString("o").
        # WindowsSystem.launch obtained parent.created directly from GetProcessTimes.
        delta = parent.created - sr.filetime(start["process_start_utc"])
        sr.atomic(
            folder / "identity-proof.json",
            {
                "exact": delta == 0,
                "delta_ticks": delta,
                "native_filetime": parent.created,
                "record_filetime": sr.filetime(start["process_start_utc"]),
            },
        )
        if abs(delta) > 10_000:
            raise sr.Stop(5, "shim creation differs by more than 1 ms")
        runtime = sr.Runtime({}, folder / "runtime", system)
        call = SimpleNamespace(start=start, process_started=True, spawned=None)
        if runtime.call_gone(call):
            raise sr.Stop(5, "live shim incorrectly classified gone")
        if delta:
            print(f"DIFF .NET StartTime/GetProcessTimes: {delta} ticks; PASS bounded 1 ms identity")
        else:
            print("PASS .NET StartTime round-trip equals GetProcessTimes FILETIME exactly")
    finally:
        sr.stop_tree(system, [parent], list(observed.values()))


def check(private: Path, python: Path, shim: Path | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    from deploy.windows._support import detach

    system = sr.WindowsSystem(detach)
    if not private.is_absolute() or private.resolve().is_relative_to(root):
        raise sr.Stop(1, "check directory must be absolute and private")
    if not python.is_absolute() or not python.is_file():
        raise sr.Stop(1, "python must be an absolute executable path")
    private = private / ("native-" + uuid.uuid4().hex)
    private.mkdir(parents=True)
    ready = private / "listener.json"
    parent = system.launch(
        [
            str(python),
            "-I",
            str(Path(__file__).resolve()),
            "--dummy",
            "parent",
            "--ready",
            str(ready),
        ],
        private,
        private / "dummy.log",
    )
    observed: dict[tuple[int, int], sr.Process] = {}
    try:
        deadline = time.monotonic() + 15
        listener = None
        while time.monotonic() < deadline:
            family = sr.descendants([*observed.values(), *system.snapshot()], [parent])
            observed.update({(p.pid, p.created): p for p in family})
            if ready.exists():
                metadata = json.loads(ready.read_bytes())
                listener = next((p for p in family if p.pid == metadata["pid"]), None)
                if listener and listener.parent != parent.pid:
                    runtime = sr.Runtime({}, private, system, sr.HTTP(metadata["port"]))
                    runtime.stand = {"key": "dummy", "processes": [parent.record()]}
                    runtime.watch.observed.update(observed)
                    if listener not in runtime.listener_processes():
                        raise sr.Stop(5, "dummy listener not a verified launcher descendant")
                    break
            time.sleep(0.1)
        else:
            raise sr.Stop(5, "dummy descendant listener timeout")
        print("PASS redirector-aware launcher/descendants/listener identities on free local port")
        if system.terminate(replace(parent, created=parent.created + 1)) or not system.alive(
            parent
        ):
            raise sr.Stop(5, "creation mismatch protection failed")
        print("PASS mismatched creation time refuses termination")
        family = [parent, *observed.values()]
        order = sr.stop_tree(system, [parent], list(observed.values()))
        positions = {pid: index for index, pid in enumerate(order)}
        # A venv redirector exits by itself once its child is stopped, so the
        # launcher may be gone before its turn; every member must still be dead.
        if (
            not listener
            or listener.pid not in positions
            or any(system.alive(p) for p in family)
            or any(
                positions[p.pid] >= positions[p.parent]
                for p in family
                if p.pid in positions and p.parent in positions
            )
        ):
            raise sr.Stop(5, "leaf-first exit verification failed")
        print("PASS verified leaf-first termination and exits")
    finally:
        sr.stop_tree(system, [parent], list(observed.values()))
    try:
        if not system.inhibit(True):
            raise sr.Stop(5, "sleep inhibition failed")
    finally:
        cleared = system.inhibit(False)
    if not cleared:
        raise sr.Stop(5, "sleep clear failed")
    print("PASS sleep hold and clear")
    first = system.clock_pair()
    time.sleep(0.02)
    second = system.clock_pair()
    if not all(b >= a > 0 for a, b in zip(first, second, strict=True)):
        raise sr.Stop(5, "native clocks failed")
    print("PASS suspend-inclusive and unbiased clocks")
    if shim is None:
        print("SKIP .NET shim StartTime identity proof: --shim absent")
    else:
        check_shim(system, private, python, shim)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--shim", type=Path)
    parser.add_argument(
        "--dummy", choices=("parent", "child", "listener", "sleeper"), help=argparse.SUPPRESS
    )
    parser.add_argument("--ready", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.dummy == "sleeper":
        time.sleep(300)
        return 0
    if args.dummy:
        if args.ready is None:
            parser.error("dummy tree requires --ready")
        dummy_tree(args.dummy, args.ready)
        return 0
    if args.private is None:
        parser.error("--private is required")
    try:
        return check(args.private, args.python, args.shim)
    except Exception:
        print("FAIL native runtime check (no private details printed)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
