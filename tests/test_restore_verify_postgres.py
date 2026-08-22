from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import backup_snapshot, restore_verify

_MIGRATION_OWNED_TABLES = {
    "review_queue",
    "trace_evaluations",
    "experiment_deployments",
    "experiment_assignments",
    "curated_case_status",
}


def _build_source_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    (project_root / "data" / "tracing").mkdir(parents=True)
    (project_root / "data" / "uploads").mkdir(parents=True)
    (project_root / "data" / "vectordb" / "chroma").mkdir(parents=True)
    (project_root / "alembic" / "versions").mkdir(parents=True)
    (project_root / "alembic" / "versions" / "017_curated_case_status.py").write_text(
        "# migration",
        encoding="utf-8",
    )

    db_path = project_root / "data" / "tracing" / "traces.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS sample (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    (project_root / "data" / "uploads" / "hello.txt").write_text("upload", encoding="utf-8")
    (project_root / "data" / "vectordb" / "chroma" / "marker").write_text(
        "chroma", encoding="utf-8"
    )
    return project_root


def _produce_snapshot_with_postgres(tmp_path: Path) -> Path:
    project_root = _build_source_project(tmp_path)
    snapshot_dir = tmp_path / "snapshot"
    backup_snapshot.create_snapshot(
        out_dir=snapshot_dir,
        project_root=project_root,
        database_url=None,
        skip_chroma=False,
    )
    dump_path = snapshot_dir / "postgres" / "postgres.dump"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_bytes(b"PGDMP")

    manifest_path = snapshot_dir / "snapshot_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["components"].append(
        {
            "name": "postgres",
            "status": "ok",
            "path": "postgres/postgres.dump",
            "size_bytes": dump_path.stat().st_size,
            "sha256": None,
            "detail": None,
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    return snapshot_dir


def _verify_postgres_with_tables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    table_names: set[str],
) -> tuple[restore_verify.StepResult, list[str], list[tuple[list[str], dict]]]:
    queries: list[str] = []
    restore_runs: list[tuple[list[str], dict]] = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, query):
            rendered = str(query)
            queries.append(rendered)
            if "alembic_version" in rendered:
                self._row = ("028",)
                self._rows = []
            elif "information_schema.tables" in rendered:
                self._row = (len(table_names),)
                self._rows = [(name,) for name in sorted(table_names)]
            else:
                self._row = None
                self._rows = []

        def fetchone(self):
            return self._row

        def fetchall(self):
            return self._rows

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def cursor(self):
            return _Cursor()

    fake_psycopg2 = SimpleNamespace(
        connect=lambda _url: _Connection(),
        sql=SimpleNamespace(SQL=lambda value: value, Identifier=lambda value: value),
    )
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)

    def _run_restore(command, **kwargs):
        restore_runs.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        restore_verify.subprocess,
        "run",
        _run_restore,
    )

    result = restore_verify._verify_postgres(
        tmp_path / "postgres.dump",
        {"alembic_revision": "028"},
        "postgresql://rag:super-secret@localhost:5432/rag_restore_test",
    )
    return result, queries, restore_runs


def test_verify_postgres_accepts_exact_head_table_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected_tables = (
        set(restore_verify.EXPECTED_MODEL_TABLES) | _MIGRATION_OWNED_TABLES | {"alembic_version"}
    )

    result, queries, _restore_runs = _verify_postgres_with_tables(
        monkeypatch, tmp_path, expected_tables
    )

    assert len(expected_tables) == 29
    assert result.passed is True
    assert "tables=29" in result.detail
    model_selects = [query for query in queries if query.startswith("SELECT * FROM public.")]
    assert len(model_selects) == len(restore_verify.EXPECTED_MODEL_TABLES)


@pytest.mark.parametrize("difference", ["missing", "extra", "missing_and_extra"])
def test_verify_postgres_rejects_inexact_head_table_set_without_leaking_dsn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    difference: str,
) -> None:
    expected_tables = (
        set(restore_verify.EXPECTED_MODEL_TABLES) | _MIGRATION_OWNED_TABLES | {"alembic_version"}
    )
    missing_table = sorted(restore_verify.EXPECTED_MODEL_TABLES)[0]
    actual_tables = set(expected_tables)
    if difference in {"missing", "missing_and_extra"}:
        actual_tables.remove(missing_table)
    if difference in {"extra", "missing_and_extra"}:
        actual_tables.add("unexpected_restore_table")

    result, _queries, _restore_runs = _verify_postgres_with_tables(
        monkeypatch, tmp_path, actual_tables
    )

    assert result.passed is False
    if difference in {"missing", "missing_and_extra"}:
        assert f"missing={missing_table}" in result.detail
    if difference in {"extra", "missing_and_extra"}:
        assert "extra=unexpected_restore_table" in result.detail
    assert "super-secret" not in result.detail
    assert "postgresql://" not in result.detail


def test_verify_postgres_uses_safe_restore_binary_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected_tables = set(restore_verify.EXPECTED_PUBLIC_TABLES)
    restore_binary = tmp_path / "PostgreSQL 16" / "pg_restore.exe"
    monkeypatch.setenv("PG_RESTORE_PATH", str(restore_binary))

    result, _queries, restore_runs = _verify_postgres_with_tables(
        monkeypatch, tmp_path, expected_tables
    )

    command, kwargs = restore_runs[0]
    assert result.passed is True
    assert command[0] == str(restore_binary)
    assert "postgresql://rag:super-secret@localhost:5432/rag_restore_test" not in command
    assert all("super-secret" not in argument for argument in command)
    assert kwargs["env"]["PGPASSWORD"] == "super-secret"


def test_verify_postgres_redacts_pg_restore_failure_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    postgres_url = "postgresql://rag:super-secret@localhost:5432/rag_restore_test"
    password_free_url, _password = backup_snapshot._normalize_postgres_dsn(postgres_url)

    def _pg_restore_fail(command, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            stderr=f"connection failed: {postgres_url}; target={password_free_url}",
        )

    monkeypatch.setattr(restore_verify.subprocess, "run", _pg_restore_fail)

    result = restore_verify._verify_postgres(
        tmp_path / "postgres.dump",
        {"alembic_revision": "028"},
        postgres_url,
    )

    assert result.passed is False
    assert "pg_restore" in result.detail
    assert "super-secret" not in result.detail
    assert "postgresql://" not in result.detail


def test_verify_postgres_redacts_connection_exception_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    postgres_url = "postgresql://rag:super-secret@localhost:5432/rag_restore_test"

    def _connect(_url):
        raise RuntimeError(f"connection failed for {postgres_url}")

    fake_psycopg2 = SimpleNamespace(
        connect=_connect,
        sql=SimpleNamespace(SQL=lambda value: value, Identifier=lambda value: value),
    )
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)
    monkeypatch.setattr(
        restore_verify.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    result = restore_verify._verify_postgres(
        tmp_path / "postgres.dump",
        {"alembic_revision": "028"},
        postgres_url,
    )

    assert result.passed is False
    assert "postgres verify failed" in result.detail
    assert "super-secret" not in result.detail
    assert "postgresql://" not in result.detail


def test_verify_postgres_redacts_invalid_dsn_without_invoking_restore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _unexpected_restore(*_args, **_kwargs):
        raise AssertionError("pg_restore must not run for an invalid DSN")

    monkeypatch.setattr(restore_verify.subprocess, "run", _unexpected_restore)

    result = restore_verify._verify_postgres(
        tmp_path / "postgres.dump",
        {"alembic_revision": "028"},
        "super-secret-without-a-scheme",
    )

    assert result.passed is False
    assert result.detail == "postgres configuration invalid: ValueError"
    assert "super-secret" not in result.detail


def test_verify_snapshot_returns_postgres_exit_code_when_restore_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot_dir = _produce_snapshot_with_postgres(tmp_path)

    def _pg_restore_fail(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=kwargs.get("args") or args[0])

    monkeypatch.setattr(restore_verify.subprocess, "run", _pg_restore_fail)

    report = restore_verify.verify_snapshot(
        snapshot_dir,
        target_root=tmp_path / "restore",
        postgres_url="postgresql://rag:rag_test@localhost:5432/rag_restore_test",
    )

    assert report.exit_code == restore_verify.EXIT_POSTGRES_VERIFY_FAILED
    postgres_step = next(step for step in report.steps if step.name == "postgres")
    assert postgres_step.passed is False
    assert "pg_restore" in postgres_step.detail


@pytest.mark.integration
def test_restore_verify_integration_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("docker")
    missing = [
        tool
        for tool in ("docker", "pg_dump", "pg_restore", "alembic")
        if shutil.which(tool) is None
    ]
    if missing:
        pytest.skip(f"missing required tools: {', '.join(missing)}")

    from scripts import restore_verify_integration

    compose_base = restore_verify_integration._compose_base()
    project_root = _build_source_project(tmp_path)
    snapshot_dir = tmp_path / "snapshot"
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "restore-verify-test-key")

    try:
        restore_verify_integration._run_compose(
            compose_base,
            ["up", "-d", restore_verify_integration.POSTGRES_SERVICE],
        )
        restore_verify_integration._wait_for_pg_ready(compose_base)
        port = restore_verify_integration._resolve_host_port(compose_base)
        database_url = (
            "postgresql://"
            f"{restore_verify_integration.POSTGRES_USER}:"
            f"{restore_verify_integration.POSTGRES_PASSWORD}@localhost:{port}/"
            f"{restore_verify_integration.POSTGRES_DB}"
        )

        env = os.environ.copy()
        env["DATABASE_URL"] = database_url
        env["DB_ENCRYPTION_KEY"] = "restore-verify-test-key"
        subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
            env=env,
        )

        backup_snapshot.create_snapshot(
            out_dir=snapshot_dir,
            project_root=project_root,
            database_url=database_url,
            skip_chroma=False,
        )
    finally:
        restore_verify_integration._run_compose(compose_base, ["down", "-v"], check=False)

    try:
        rc = restore_verify_integration.main(
            [
                "--snapshot",
                str(snapshot_dir),
            ]
        )
        assert rc == 0
    finally:
        restore_verify_integration._run_compose(compose_base, ["down", "-v"], check=False)

    ps = restore_verify_integration._run_compose(
        compose_base,
        ["ps", "-q", restore_verify_integration.POSTGRES_SERVICE],
        check=False,
    )
    assert ps.stdout.strip() == ""
