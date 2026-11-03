"""Compile the Windows/Python 3.11 lock using the Linux lock's pinned versions."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*==\s*([^\s;\\]+)")
OUTPUT = Path("deploy/windows/requirements-win.lock")
COMPILE_COMMAND = "python deploy/windows/make_win_lock.py"


def parse_pins(text: str) -> dict[str, str]:
    """Read exact pins, ignoring extras, markers, comments and hash continuations."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = PIN.match(line.strip())
        if match is None:
            continue
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        version = match[2]
        if name in found and found[name] != version:
            raise ValueError(f"conflicting versions for {name}")
        found[name] = version
    return found


@dataclass(frozen=True)
class Comparison:
    only_linux: tuple[str, ...]
    only_windows: tuple[str, ...]
    differing: tuple[tuple[str, str, str], ...]


def compare_pins(linux: Mapping[str, str], windows: Mapping[str, str]) -> Comparison:
    return Comparison(
        tuple(sorted(linux.keys() - windows.keys())),
        tuple(sorted(windows.keys() - linux.keys())),
        tuple(
            (name, linux[name], windows[name])
            for name in sorted(linux.keys() & windows.keys())
            if linux[name] != windows[name]
        ),
    )


def compile_lock(cache_dir: Path | None = None) -> int:
    if Path.cwd().resolve() != Path(__file__).resolve().parents[2]:
        raise ValueError("run from the repository root")
    linux = parse_pins(Path("requirements.lock").read_text(encoding="utf-8"))
    if not linux:
        raise ValueError("requirements.lock has no exact pins")
    env = dict(os.environ)
    if cache_dir is not None:
        env["UV_CACHE_DIR"] = str(cache_dir)
    with tempfile.TemporaryDirectory(prefix="rag-win-lock-") as temporary:
        constraints = Path(temporary) / "constraints.txt"
        constraints.write_text(
            "".join(f"{name}=={version}\n" for name, version in sorted(linux.items())),
            encoding="utf-8",
            newline="\n",
        )
        result = subprocess.run(
            [
                "uv",
                "pip",
                "compile",
                "requirements.txt",
                "--python-platform",
                "windows",
                "--python-version",
                "3.11",
                "-c",
                str(constraints),
                "-o",
                OUTPUT.as_posix(),
                "--generate-hashes",
                "--no-annotate",
                "--custom-compile-command",
                COMPILE_COMMAND,
            ],
            env=env,
            check=False,
        )
    if result.returncode:
        return result.returncode
    windows = parse_pins(OUTPUT.read_text(encoding="utf-8"))
    comparison = compare_pins(linux, windows)
    print("linux", len(linux), "windows", len(windows))
    print("only linux:", list(comparison.only_linux))
    print("only windows:", list(comparison.only_windows))
    print("version differs:", list(comparison.differing))
    return 1 if comparison.differing or not windows else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv-cache-dir", type=Path)
    args = parser.parse_args()
    try:
        return compile_lock(args.uv_cache_dir)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
