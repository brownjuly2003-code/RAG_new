"""Offline POSIX Codex executable; scenario control never uses the child environment."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "codex"
ANSWER = "Submit the damage claim in writing [1]."


class FakeCodex:
    def __init__(self, root: Path):
        self.root = root
        self.binary = root / "codex"
        script = root / "replay.py"
        script.write_bytes((FIXTURES / "replay.py").read_bytes())
        self.binary.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -I {shlex.quote(str(script))} "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        self.binary.chmod(0o700)
        self.configure()

    def configure(self, *, fixture="ok", events=None, exit_code=0, delay=0, child=False):
        if events is None:
            events = [
                json.loads(line)
                for line in (FIXTURES / f"{fixture}.jsonl").read_text(encoding="utf-8").splitlines()
            ]
        (self.root / "scenario.json").write_text(
            json.dumps({"events": events, "exit": exit_code, "delay": delay, "child": child}),
            encoding="utf-8",
        )

    def records(self):
        return [
            json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("call-*.json"))
        ]


@pytest.fixture
def fake_codex(tmp_path):
    if os.name != "posix":
        pytest.skip("Codex service subprocess contract targets macOS and Linux")
    root = tmp_path / "fake-codex"
    root.mkdir()
    return FakeCodex(root)
