"""D.4 runner boundary tests and the optional PostgreSQL acceptance check."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import pgvector_graph_evidence_run as runner


def test_gzip_input_keeps_plain_json_digest_and_records_archive_digest(tmp_path: Path) -> None:
    payload = json.dumps(
        {"chunks": [{"page_content": "one", "metadata": {"source": "a.md"}}]}
    ).encode("utf-8")
    archive = gzip.compress(payload)
    path = tmp_path / "chunks.bin"
    path.write_bytes(archive)

    loaded = runner._load_chunks(path, 1)

    chunks, digest = loaded
    assert chunks[0].page_content == "one"
    assert digest == hashlib.sha256(payload).hexdigest()
    assert loaded.archive_sha256 == hashlib.sha256(archive).hexdigest()


def test_tracked_archive_has_pinned_count_and_digests() -> None:
    archive_path = (
        Path(__file__).resolve().parents[1] / "evaluation" / "gr1b-4436d61-graph-chunks.json.gz"
    )
    archive_bytes = archive_path.read_bytes()
    json_bytes = gzip.decompress(archive_bytes)

    loaded = runner._load_chunks(archive_path, runner.EXPECTED_CHUNKS)

    assert len(loaded.chunks) == 5589
    assert loaded.archive_sha256 == hashlib.sha256(archive_bytes).hexdigest()
    assert loaded.json_sha256 == hashlib.sha256(json_bytes).hexdigest()
    assert loaded.archive_sha256 == (
        "2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12"
    )
    assert loaded.json_sha256 == (
        "5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94"
    )


def test_scratch_name_guard_accepts_only_own_generated_shape() -> None:
    name = runner._scratch_name("0123456789abcdef")
    assert name == "rag_spike_d4_0123456789abcdef"
    runner._require_scratch_name(name)
    for unsafe in ("ragnew_prod", "rag_spike_other", 'rag_spike_d4_abc"; DROP DATABASE x;'):
        with pytest.raises(ValueError, match="scratch"):
            runner._require_scratch_name(unsafe)


def test_wrong_chunk_count_names_actual_and_expected_before_database(tmp_path: Path) -> None:
    path = tmp_path / "chunks.json"
    path.write_text(
        json.dumps({"chunks": [{"page_content": "one", "metadata": {}}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"1 rows, expected 5589"):
        runner._load_chunks(path, 5589)


def test_wrong_count_stops_run_before_scratch_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "chunks.json"
    path.write_text(
        json.dumps({"chunks": [{"page_content": "one", "metadata": {}}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "_run_lifecycle",
        lambda *_args: pytest.fail("database lifecycle was started"),
    )
    with pytest.raises(ValueError, match=r"1 rows, expected 5589"):
        runner.run_acceptance(
            path,
            tmp_path / "report.json",
            "postgresql://postgres:topsecret@localhost:55432/postgres",
            "0" * 40,
        )


def test_url_query_cannot_override_local_connection_target() -> None:
    with pytest.raises(ValueError) as excinfo:
        runner._maintenance_url(
            "postgresql://postgres:topsecret@localhost:55432/postgres?host=db.example.com"
        )
    assert "topsecret" not in str(excinfo.value)
    assert "db.example.com" not in str(excinfo.value)


def test_url_query_accepts_safe_connection_options() -> None:
    url = runner._maintenance_url(
        "postgresql+psycopg2://postgres:topsecret@127.0.0.1:55432/postgres"
        "?sslmode=disable&connect_timeout=5&application_name=d4"
    )
    assert dict(url.query) == {
        "sslmode": "disable",
        "connect_timeout": "5",
        "application_name": "d4",
    }
    assert dict(url.set(database="rag_spike_d4_0123456789abcdef").query) == dict(url.query)


@pytest.mark.parametrize("query", ["hostaddr=10.0.0.1", "options=-csecret", "unknown=secret"])
def test_url_query_rejects_disallowed_options_without_leaking(query: str) -> None:
    url = f"postgresql://postgres:topsecret@localhost:55432/postgres?{query}"
    with pytest.raises(ValueError) as excinfo:
        runner._maintenance_url(url)
    message = str(excinfo.value)
    assert "topsecret" not in message
    assert query not in message
    assert url not in message


def test_seed_failure_message_keeps_only_step_class_and_sqlstate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class IntegrityError(Exception):
        orig = SimpleNamespace(pgcode="23514")

    def fail(_connection: object, _graph: object) -> None:
        raise IntegrityError("INSERT INTO evidence_snapshots VALUES (topsecret)")

    monkeypatch.setattr(runner, "_seed_evidence", fail)
    with pytest.raises(RuntimeError) as excinfo:
        runner._seed_evidence_checked(None, None)
    assert str(excinfo.value) == (
        "scratch measurement failed at step=seed_evidence: IntegrityError sqlstate=23514"
    )


def test_migration_key_is_new_and_environment_is_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "envkey")
    monkeypatch.setenv("DATABASE_URL", "previous-database")
    scratch_url = SimpleNamespace(
        render_as_string=lambda **kwargs: "postgresql://user:topsecret@localhost:55432/scratch"
    )
    with runner._migration_environment(scratch_url):
        key = os.environ["DB_ENCRYPTION_KEY"]
        assert key != "envkey"
        assert len(key) == 64
        assert all(character in "0123456789abcdef" for character in key)
    assert os.environ["DB_ENCRYPTION_KEY"] == "envkey"
    assert os.environ["DATABASE_URL"] == "previous-database"


class _FakeUrl:
    def set(self, *, database: str) -> str:
        return database


@pytest.mark.parametrize("fail_measurement", [False, True])
def test_lifecycle_orders_cleanup_and_drops_only_created_name(
    monkeypatch: pytest.MonkeyPatch, fail_measurement: bool
) -> None:
    sqlalchemy = pytest.importorskip("sqlalchemy")
    name = "rag_spike_d4_0123456789abcdef"
    calls: list[tuple[str, str]] = []
    seeded_rows: list[str] = []
    monkeypatch.setattr(runner, "_scratch_name", lambda: name)

    def create(_admin: object, created_name: str) -> None:
        calls.append(("create", created_name))

    def migrate(scratch_name: str) -> str:
        calls.append(("migrate", scratch_name))
        return "033"

    def seed(_connection: object, _chunks: object, _role: str) -> dict[str, str]:
        calls.append(("measure", name))
        seeded_rows.append("support_cases")
        if fail_measurement:
            raise RuntimeError("topsecret must not escape")
        return {"ok": "yes"}

    class FakeTransaction:
        def rollback(self) -> None:
            calls.append(("rollback", name))
            seeded_rows.clear()

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def begin(self) -> FakeTransaction:
            return FakeTransaction()

    class FakeEngine:
        def connect(self) -> FakeConnection:
            return FakeConnection()

        def dispose(self) -> None:
            calls.append(("dispose", name))

    def create_engine(scratch_name: str, *, hide_parameters: bool, poolclass: object) -> FakeEngine:
        assert scratch_name == name
        assert hide_parameters is True
        assert poolclass is sqlalchemy.pool.NullPool
        return FakeEngine()

    def checks(scratch_name: str, _role: str) -> tuple[dict[str, int], bool]:
        calls.append(("checks", scratch_name))
        assert seeded_rows == []
        return {table: 0 for table in runner._MEASURED_TABLES}, True

    def drop(_admin: object, created_name: str) -> None:
        calls.append(("drop", created_name))

    monkeypatch.setattr(runner, "_create_scratch_database", create)
    monkeypatch.setattr(runner, "_migrate_scratch_database", migrate)
    monkeypatch.setattr(runner, "_seed_and_measure", seed)
    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)
    monkeypatch.setattr(runner, "_post_rollback_checks", checks)
    monkeypatch.setattr(runner, "_drop_scratch_database", drop)
    if fail_measurement:
        with pytest.raises(RuntimeError, match="scratch measurement failed") as excinfo:
            runner._run_lifecycle(_FakeUrl(), [])
        assert "step=measure: RuntimeError" in str(excinfo.value)
        assert "topsecret" not in str(excinfo.value)
    else:
        result = runner._run_lifecycle(_FakeUrl(), [])
        assert result["scratch_name"] == name
        assert result["scratch_dropped"] is True
    assert calls == [
        (step, name)
        for step in ("create", "migrate", "measure", "rollback", "dispose", "checks", "drop")
    ]


def test_existing_scratch_name_is_never_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(runner, "_scratch_name", lambda: "rag_spike_d4_0123456789abcdef")

    def create(_admin: object, _name: str) -> None:
        calls.append("create")
        raise FileExistsError("already exists")

    monkeypatch.setattr(runner, "_create_scratch_database", create)
    monkeypatch.setattr(runner, "_drop_scratch_database", lambda *_args: calls.append("drop"))
    with pytest.raises(FileExistsError, match="scratch database already exists"):
        runner._run_lifecycle(_FakeUrl(), [])
    assert calls == ["create"]


def test_role_grant_is_limited_and_set_membership_is_explicit() -> None:
    pytest.importorskip("sqlalchemy")
    statements: list[str] = []
    connection = SimpleNamespace(execute=lambda statement: statements.append(str(statement)))
    runner._create_measurement_role(connection, "rag_d4_role_0123456789abcdef")
    assert "NOLOGIN NOSUPERUSER NOBYPASSRLS" in statements[0]
    assert "TO CURRENT_USER WITH SET TRUE" in statements[1]
    assert "GRANT USAGE ON SCHEMA public" in statements[2]
    assert all(f"public.{table}" in statements[3] for table in runner._MEASURED_TABLES)
    assert statements[4].startswith("SET LOCAL ROLE")


def test_vector_extension_version_is_installed_in_scratch_transaction() -> None:
    pytest.importorskip("sqlalchemy")
    statements: list[str] = []

    def execute(statement: object) -> None:
        statements.append(str(statement))

    def scalar(statement: object, params: object) -> str:
        statements.append(str(statement))
        assert params == {"extension": "vector"}
        return "0.8.1"

    connection = SimpleNamespace(execute=execute, scalar=scalar)
    assert runner._vector_extension_version(connection) == "0.8.1"
    assert statements == [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "SELECT extversion FROM pg_extension WHERE extname = :extension",
    ]


def test_probe_success_and_unexpected_error_are_secret_free() -> None:
    pytest.importorskip("sqlalchemy")

    class Savepoint:
        rolled_back = False

        def rollback(self) -> None:
            self.rolled_back = True

    point = Savepoint()
    connection = SimpleNamespace(
        begin_nested=lambda: point,
        execute=lambda *_args: None,
    )
    assert runner._probe_sqlstate(connection, "SELECT 1", {}) == "00000"
    assert point.rolled_back is True

    def fail(*_args: object) -> None:
        raise ValueError("topsecret")

    connection.execute = fail
    with pytest.raises(RuntimeError, match="database probe failed") as excinfo:
        runner._probe_sqlstate(connection, "SELECT topsecret", {})
    assert "topsecret" not in str(excinfo.value)


def test_probe_records_database_sqlstate_and_rolls_back_savepoint() -> None:
    sqlalchemy = pytest.importorskip("sqlalchemy")

    class OriginalError(Exception):
        pgcode = "42501"

    point = SimpleNamespace(rolled_back=False)

    def rollback() -> None:
        point.rolled_back = True

    point.rollback = rollback

    def fail(*_args: object) -> None:
        raise sqlalchemy.exc.DBAPIError(
            "INSERT topsecret", {"password": "topsecret"}, OriginalError()
        )

    connection = SimpleNamespace(begin_nested=lambda: point, execute=fail)
    assert runner._probe_sqlstate(connection, "INSERT topsecret", {}) == "42501"
    assert point.rolled_back is True


def test_database_acceptance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.getenv("RESOLUTION_ADMIN_DATABASE_URL")
    if not database_url:
        pytest.skip("RESOLUTION_ADMIN_DATABASE_URL is required for the PostgreSQL test")
    pytest.importorskip("langchain_core")
    monkeypatch.setattr(runner, "_git_tree_clean", lambda: True)
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "envkey")
    payload = {
        "chunks": [
            *(
                {
                    "page_content": f"# Section\n\nSynthetic chunk {index}.",
                    "metadata": {"source": source, "chunk_index": index, "h1": "Section"},
                }
                for source, index in (("alpha.md", 0), ("alpha.md", 1), ("beta.md", 0))
            ),
            {
                "page_content": "# Section\n\nSee missing.md for the missing procedure.",
                "metadata": {"source": "alpha.md", "chunk_index": 2, "h1": "Section"},
            },
            {
                "page_content": "# Введение\n\nСинтетический фрагмент.",
                "metadata": {"source": "beta.md", "chunk_index": 1, "h1": "Введение"},
            },
        ],
    }
    chunk_count = len(payload["chunks"])
    assert chunk_count == 5
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "report.json"

    report = runner.run_acceptance(
        chunks_path=chunks_path,
        output_path=output_path,
        database_url=database_url,
        code_base=runner._git_code_base(),
        expected_chunk_count=chunk_count,
    )

    assert report["evidence_class"] == "measured"
    assert report["counts"]["chunk_node_count"] == chunk_count
    assert report["counts"]["evidence_link_count"] == chunk_count
    assert report["counts"]["evidence_join_count"] == chunk_count
    assert report["graph"]["unresolved_cross_refs"]["built_count"] >= 1
    assert type(report["graph"]["load_preserved_node_order"]) is bool
    assert type(report["graph"]["load_preserved_edge_order"]) is bool
    assert report["sqlstates"] == {
        "cross_tenant_insert": "42501",
        "evidence_update": "55000",
        "evidence_delete": "55000",
    }
    assert report["scratch"]["dropped"] is True
    assert (
        runner._database_exists(runner._maintenance_url(database_url), report["scratch"]["name"])
        is False
    )
    assert os.environ["DB_ENCRYPTION_KEY"] == "envkey"
    assert "envkey" not in output_path.read_text(encoding="utf-8")
    assert json.loads(output_path.read_text(encoding="utf-8")) == report
