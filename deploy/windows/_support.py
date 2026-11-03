"""Product paths and the isolated Windows process/ACL boundary."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

DEFAULT_ROOT = Path("D:/RAG_new_prod")


class DeploymentError(Exception):
    """A safe diagnostic, containing no command output or secret values."""


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def app(self) -> Path:
        return self.root / "app"

    @property
    def python(self) -> Path:
        return self.root / "venv/Scripts/python.exe"

    @property
    def launcher(self) -> Path:
        return self.app / "deploy/windows/start.py"

    @property
    def index(self) -> Path:
        return self.root / "data/aircargo/index/chroma"

    @property
    def onnx(self) -> Path:
        return self.root / "ort/bge-reranker-v2-m3/int8/model.onnx"

    @property
    def hf(self) -> Path:
        return self.root / "hf"

    @property
    def pgdata(self) -> Path:
        return self.root / "pgdata"

    @property
    def pglog(self) -> Path:
        return self.root / "pg.log"

    @property
    def secrets(self) -> Path:
        return self.root / "secrets"

    @property
    def pg_store(self) -> Path:
        return self.secrets / "pg.json"

    @property
    def service_store(self) -> Path:
        return self.secrets / "service.json"

    @property
    def service_log(self) -> Path:
        return self.root / "service.log"


def parser(description: str) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=description)
    result.add_argument(
        "--root",
        type=absolute_root,
        default=DEFAULT_ROOT,
        help="Product root (default: D:/RAG_new_prod)",
    )
    return result


def absolute_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("--root must be an absolute path")
    return path


def random_secret(length: int) -> str:
    return secrets.token_urlsafe(length)


def require_windows() -> None:
    if sys.platform != "win32":
        raise DeploymentError("This operation requires Windows; no changes were made")


def run(
    argv: Sequence[str | Path],
    *,
    env: dict[str, str] | None = None,
    input: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(arg) for arg in argv],
        input=input,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        shell=False,
        check=False,
    )
    if check and result.returncode:
        # PostgreSQL may echo SQL (including passwords) in its error output.
        raise DeploymentError(
            f"{Path(argv[0]).name} failed (exit {result.returncode}); output withheld"
        )
    return result


def restrict(path: Path) -> None:
    require_windows()
    rights = "(OI)(CI)F" if path.is_dir() else "F"
    run(["icacls", path, "/inheritance:r", "/grant:r", f"{os.environ['USERNAME']}:{rights}"])


def secret_store(path: Path, create: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    restrict(path.parent)
    if path.exists():
        restrict(path)
        return json.loads(path.read_text(encoding="utf-8"))
    values = create()
    # Exclusive creation prevents a second installer from replacing existing secrets.
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(values, indent=2) + "\n")
    restrict(path)
    return values


def windows_process_options(breakaway: bool) -> dict[str, Any]:
    require_windows()
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    if breakaway:
        flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB
    return {"creationflags": flags}


def detach(
    argv: list[str],
    *,
    cwd: Path | None = None,
    stdout: BinaryIO | int = subprocess.DEVNULL,
) -> subprocess.Popen[bytes]:
    """Use the laptop-proven no-window flags; try job breakaway first."""
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": stdout,
        "stderr": subprocess.STDOUT,
        "cwd": cwd,
        "close_fds": True,
        "shell": False,
    }
    try:
        return subprocess.Popen(argv, **kwargs, **windows_process_options(True))
    except OSError:
        # Some host jobs disallow explicit breakaway. Keep the other creation flags.
        return subprocess.Popen(argv, **kwargs, **windows_process_options(False))


def cli(action: Callable[[], int]) -> int:
    try:
        return action()
    except DeploymentError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        # Never expose JSON, HTTP bodies, SQL, subprocess argv or credentials in tracebacks.
        print(
            "Deployment helper failed; check paths, permissions and prepared resources",
            file=sys.stderr,
        )
    return 2
