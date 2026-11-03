"""Portable Windows lock contracts; never invoke uv or access the network."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy.windows import make_win_lock as lock

ROOT = Path(__file__).resolve().parents[1]


def test_parser_handles_hashes_extras_markers_and_canonical_names():
    text = (
        "# uv output\n"
        "Example_Package[fast,secure]==1.2.3 ; python_version >= '3.11' \\\n"
        "    --hash=sha256:" + "a" * 64 + " \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n"
        "Other.Pkg==2.0rc1+cpu --hash=sha256:" + "c" * 64 + "\n"
        "example-package==1.2.3; sys_platform == 'win32'\n"
    )
    assert lock.parse_pins(text) == {"example-package": "1.2.3", "other-pkg": "2.0rc1+cpu"}


def test_conflicting_marker_pins_are_not_silently_overwritten():
    with pytest.raises(ValueError, match="conflicting versions"):
        lock.parse_pins("pkg==1; sys_platform == 'linux'\npkg==2; sys_platform == 'win32'\n")


def test_comparison_reports_platform_packages_and_version_drift():
    result = lock.compare_pins(
        {"common": "1", "changed": "2", "linux-only": "3"},
        {"common": "1", "changed": "1", "windows-only": "4"},
    )
    assert result.only_linux == ("linux-only",)
    assert result.only_windows == ("windows-only",)
    assert result.differing == (("changed", "2", "1"),)
    assert lock.compare_pins({"same": "1"}, {"same": "1"}) == lock.Comparison((), (), ())


@pytest.mark.parametrize("windows_version,expected", [("1.2.3", 0), ("1.2.2", 1)])
def test_generator_uses_relative_inputs_temporary_constraints_and_clean_header(
    tmp_path, monkeypatch, capsys, windows_version, expected
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lock, "__file__", str(tmp_path / "deploy/windows/make_win_lock.py"))
    (tmp_path / "requirements.lock").write_text("pkg[extra]==1.2.3\n", encoding="utf-8")
    (tmp_path / "requirements.txt").touch()
    output = tmp_path / lock.OUTPUT
    output.parent.mkdir(parents=True)
    constraints_seen = []

    def compile_fake(argv, **kwargs):
        constraints = Path(argv[argv.index("-c") + 1])
        constraints_seen.append(constraints)
        assert constraints.read_bytes() == b"pkg==1.2.3\n"
        assert argv == [
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
            "deploy/windows/requirements-win.lock",
            "--generate-hashes",
            "--no-annotate",
            "--custom-compile-command",
            "python deploy/windows/make_win_lock.py",
        ]
        assert kwargs["env"]["UV_CACHE_DIR"] == str(tmp_path / "cache")
        output.write_text(f"pkg=={windows_version}\nwindows-only==4\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(lock.subprocess, "run", compile_fake)
    assert lock.compile_lock(tmp_path / "cache") == expected
    assert constraints_seen and not constraints_seen[0].exists()
    printed = capsys.readouterr().out
    assert "linux 1 windows 2" in printed
    assert "only windows: ['windows-only']" in printed
    if expected:
        assert "('pkg', '1.2.3', '1.2.2')" in printed


def test_repository_windows_lock_has_hashes_and_linux_versions():
    windows_path = ROOT / lock.OUTPUT
    if not windows_path.exists():
        pytest.skip(
            "Windows lock is absent: owner must run python deploy/windows/make_win_lock.py after review"
        )
    text = windows_path.read_text(encoding="utf-8")
    windows = lock.parse_pins(text)
    assert windows, "Windows lock must contain pinned packages"
    # Join continuations so a hash cannot accidentally be borrowed from the next package.
    entries = text.replace("\\\n", " ").splitlines()
    for entry in entries:
        if lock.PIN.match(entry.strip()):
            assert re.search(r"--hash=sha256:[0-9a-fA-F]{64}(?=\s|$)", entry), entry.split("==")[0]
    linux = lock.parse_pins((ROOT / "requirements.lock").read_text(encoding="utf-8"))
    assert linux, "Linux lock must contain pinned packages"
    assert not lock.compare_pins(linux, windows).differing
