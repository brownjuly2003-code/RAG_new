"""Regression coverage for journey-admission report code provenance."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from evaluation.journey_admission import CODE_DIGEST_PATHS, code_provenance


def _run_git(project_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_report_sources(project_root: Path) -> None:
    for index, relative_path in enumerate(CODE_DIGEST_PATHS):
        destination = project_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(f"source-{index}\n".encode("ascii"))


def _create_git_repository(project_root: Path) -> None:
    _run_git(project_root, "init", "--quiet")
    _run_git(project_root, "config", "user.email", "tests@example.invalid")
    _run_git(project_root, "config", "user.name", "Journey Admission Tests")


def _framed_code_digest(project_root: Path) -> str:
    digest = hashlib.sha256()
    for relative_path in CODE_DIGEST_PATHS:
        path_bytes = relative_path.as_posix().encode("utf-8")
        contents = (project_root / relative_path).read_bytes()
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def test_code_provenance_marks_a_dirty_report_file_not_reproducible_from_head(
    tmp_path: Path,
) -> None:
    _write_report_sources(tmp_path)
    _create_git_repository(tmp_path)
    _run_git(tmp_path, "add", *(str(path) for path in CODE_DIGEST_PATHS))
    _run_git(tmp_path, "commit", "--quiet", "-m", "add report sources")
    dirty_path = tmp_path / CODE_DIGEST_PATHS[0]
    dirty_path.write_bytes(b"changed evaluator\n")

    provenance = code_provenance(project_root=tmp_path)

    assert provenance.head_sha != "unknown"
    assert provenance.reproducible_from_head is False
    assert provenance.code_digest == _framed_code_digest(tmp_path)


def test_code_provenance_handles_a_report_path_missing_at_head(tmp_path: Path) -> None:
    _write_report_sources(tmp_path)
    _create_git_repository(tmp_path)
    _run_git(tmp_path, "add", *(str(path) for path in CODE_DIGEST_PATHS[:2]))
    _run_git(tmp_path, "commit", "--quiet", "-m", "add partial report sources")

    provenance = code_provenance(project_root=tmp_path)

    assert provenance.head_sha != "unknown"
    assert provenance.reproducible_from_head is False


def test_code_provenance_marks_a_dirty_label_loader_not_reproducible_from_head(
    tmp_path: Path,
) -> None:
    _write_report_sources(tmp_path)
    label_loader = tmp_path / "evaluation" / "aircargo_labels.py"
    label_loader.write_bytes(b"original labels\n")
    _create_git_repository(tmp_path)
    _run_git(
        tmp_path,
        "add",
        *(str(path) for path in CODE_DIGEST_PATHS),
        str(label_loader.relative_to(tmp_path)),
    )
    _run_git(tmp_path, "commit", "--quiet", "-m", "add report sources and label loader")
    label_loader.write_bytes(b"changed labels\n")

    provenance = code_provenance(project_root=tmp_path)

    assert provenance.head_sha != "unknown"
    assert provenance.reproducible_from_head is False
