"""Runner tests for the Mac-only Phase D.5 measurement, not production code."""

import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.pgvector_cold_start_run import (
    RunnerError,
    _cleanup,
    _load_inputs,
    _normalize_admin_url,
    _scratch_name,
    run_measurement,
)
from scripts.pgvector_cold_start_run import (
    main as runner_main,
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def write_inputs(tmp_path, chunks=3, cases=2):
    texts = [f"chunk {i}" for i in range(chunks)]
    payload = {"chunks": [{"page_content": text, "metadata": {"source": "test"}} for text in texts]}
    archive = tmp_path / "chunks.json.gz"
    raw = json.dumps(payload).encode()
    with gzip.open(archive, "wb") as stream:
        stream.write(raw)
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    vectors = tmp_path / "chunks.npz"
    np.savez(
        vectors,
        embeddings=np.ones((chunks, 1024), dtype="float32"),
        chunk_text_digest=np.bytes_(digest.hexdigest()),
        embedding_model=np.bytes_("BAAI/bge-m3"),
    )
    queries = tmp_path / "d1-queries.npy"
    np.save(queries, np.ones((cases, 1024), dtype="float32"))
    case_files = [
        tmp_path / "curated_cases_aircargo.jsonl",
        tmp_path / "curated_cases_aircargo_gr_multihop.jsonl",
    ]
    split = cases // 2
    for path, indices in zip(case_files, [range(split), range(split, cases)], strict=True):
        path.write_text(
            "".join(
                json.dumps({"case_id": f"c{i}", "query": f"query {i}"}) + "\n" for i in indices
            ),
            encoding="utf-8",
        )
    report = tmp_path / "d1.json"
    digests = {"ab_phase2_G2_graph_chunks.json": _sha(raw)}
    digests.update({path.name: _sha(path.read_bytes()) for path in [vectors, queries, *case_files]})
    report.write_text(
        json.dumps(
            {
                "input_sha256": digests,
                "runs": [
                    {
                        "chroma_bm25": {"rankings": [[0] for _ in range(cases)]},
                        "postgres": {"rankings": [[0] for _ in range(cases)]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return archive, vectors, queries, case_files, report


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner
        self.sql = ""

    def execute(self, sql, params=None):
        self.sql = str(sql)
        self.owner.calls.append(self.sql)

    def fetchone(self):
        if "pg_database" in self.sql or "pg_roles" in self.sql:
            return (False,)
        if "version()" in self.sql:
            return ("PostgreSQL 16",)
        if "extversion" in self.sql:
            return ("0.7",)
        if "current_setting" in self.sql:
            return ("128MB",)
        if "pg_database_size" in self.sql:
            return (1024,)
        if "TOAST" in self.sql or "toast" in self.sql:
            return (64,)
        return (0,)

    def fetchall(self):
        return [("public.spike_chunks", 512)]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls
        self.autocommit = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.calls.append("commit")

    def close(self):
        self.calls.append("close")


def _harness(tmp_path, monkeypatch, inputs, **overrides):
    calls = []
    url = "postgresql+psycopg2://runner_login:secret-db-password@localhost:55432/postgres"
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", url)
    archive, vectors, queries, case_files, d1 = inputs

    def spawn(args, **kwargs):
        calls.append(("spawn", args, kwargs))
        if "--build-collection" in args:
            Path(args[args.index("--chroma-dir") + 1], "store.bin").write_bytes(b"data")
            payload = {"build_ms": 1.0}
        else:
            arm = args[args.index("--trial") + 1]
            rankings = (
                {"chroma_fused": [[0] for _ in range(2)]}
                if arm == "chroma_bm25"
                else {
                    "postgres_fused": [[0] for _ in range(2)],
                    "postgres_hnsw": [[0] for _ in range(2)],
                }
            )
            payload = {
                "arm": arm,
                "import_ms": 1.0,
                "open_ms": 1.0,
                "first_query_ms": 1.0,
                "time_to_first_result_ms": 3.0,
                "workload_ms": 2.0,
                "baseline_rss_bytes": 1024,
                "rss_after_workload_bytes": 2048,
                "peak_rss_bytes": 4096,
                "rankings": rankings,
            }
            if arm == "postgres":
                payload.update(first_ann_ms=1.0, ann_workload_ms=2.0, backend_rss_bytes=2048)
            else:
                payload.update(restore_ms=1.0, bm25_ms=1.0)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload) + "\n", stderr="")

    def connection_factory(dsn, dbname):
        calls.append(("connect", dbname))
        return FakeConnection(calls)

    def setup_fn(dsn, database, texts, embeddings):
        calls.append(("setup", database))
        return FakeConnection(calls)

    def mkdir(path):
        calls.append(("mkdir", path.name))
        path.mkdir(exist_ok=False)

    def remove(path):
        calls.append(("rmtree", path.name))
        import shutil

        shutil.rmtree(path)

    params = dict(
        archive=archive,
        vectors_path=vectors,
        queries_path=queries,
        case_files=case_files,
        d1_report=d1,
        expected_chunks=3,
        expected_cases=2,
        trials=2,
        temp_dir=tmp_path,
        code_base_provider=lambda: "a" * 40,
        spawner=spawn,
        connection_factory=connection_factory,
        setup_fn=setup_fn,
        directory_creator=mkdir,
        remove_dir=remove,
        host_reader=lambda name: "17179869184" if name == "hw.memsize" else "0.0M",
        token_hex=lambda count: "0123456789abcdef",
        clock=iter(range(1000)).__next__,
        versions_provider=lambda: {},
        load_reader=lambda: "0, 0, 0",
    )
    params.update(overrides)
    return calls, url, params


def _assert_no_side_effects(calls):
    assert not any(item[0] in {"spawn", "setup", "mkdir", "connect"} for item in calls)


def test_an_input_d1_did_not_use(tmp_path, monkeypatch):
    """Scenario: an input D.1 did not use."""
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    _load_inputs(*inputs[:3], inputs[3], inputs[4], 3, 2)
    np.save(inputs[2], np.zeros((2, 1024), dtype="float32"))
    with pytest.raises(ValueError, match="d1-queries.npy"):
        run_measurement(tmp_path / "out.json", **params)
    _assert_no_side_effects(calls)


def test_a_text_digest_mismatch(tmp_path, monkeypatch):
    """Scenario: a text digest mismatch."""
    inputs = write_inputs(tmp_path)
    archive, vectors, queries, case_files, d1 = inputs
    with np.load(vectors, allow_pickle=False) as cache:
        embeddings = cache["embeddings"]
    np.savez(
        vectors,
        embeddings=embeddings,
        chunk_text_digest=np.bytes_("bad"),
        embedding_model=np.bytes_("BAAI/bge-m3"),
    )
    report = json.loads(d1.read_text(encoding="utf-8"))
    report["input_sha256"][vectors.name] = _sha(vectors.read_bytes())
    d1.write_text(json.dumps(report), encoding="utf-8")
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    with pytest.raises(ValueError, match="digest"):
        run_measurement(tmp_path / "out.json", **params)
    _assert_no_side_effects(calls)


def test_a_wrong_case_count(tmp_path, monkeypatch):
    """Scenario: a wrong case count."""
    inputs = write_inputs(tmp_path, cases=1)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    params["expected_cases"] = 2
    with pytest.raises(ValueError, match="1.*2|2.*1"):
        run_measurement(tmp_path / "out.json", **params)
    _assert_no_side_effects(calls)


def test_a_non_local_url_and_valid_control(tmp_path, monkeypatch):
    """Scenario: a non-local URL."""
    assert _normalize_admin_url("postgresql+psycopg2://u:p@localhost:55432/postgres") == (
        "postgresql://u:p@localhost:55432/postgres"
    )
    assert _normalize_admin_url("postgresql://u:p@127.0.0.1:55432/postgres")
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    monkeypatch.setenv(
        "RESOLUTION_ADMIN_DATABASE_URL",
        "postgresql://u:secret-db-password@db.example.com:55432/postgres",
    )
    with pytest.raises(ValueError) as error:
        run_measurement(tmp_path / "out.json", **params)
    assert "db.example.com" not in str(error.value)
    assert "secret-db-password" not in str(error.value)
    _assert_no_side_effects(calls)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_admin_url_accepts_local_driver_with_sslmode(host):
    url = f"postgresql+psycopg2://local_user:local_password@{host}:55432/postgres?sslmode=require"
    normalized = _normalize_admin_url(url)
    assert normalized.startswith("postgresql://")
    assert _normalize_admin_url(normalized) == normalized


def test_admin_url_accepts_local_query_credentials():
    url = (
        "postgresql+psycopg2://127.0.0.1:55432/postgres"
        "?user=review_user&password=review_secret&sslmode=disable"
    )
    normalized = _normalize_admin_url(url)
    if normalized != url.replace("postgresql+psycopg2://", "postgresql://", 1):
        pytest.fail("valid local query credentials were not normalized")


@pytest.mark.parametrize(
    "override",
    [
        "?host=db.example.com",
        "?port=5432",
        "?hostaddr=203.0.113.1",
        "?service=x",
    ],
)
def test_admin_url_rejects_effective_connection_overrides(tmp_path, monkeypatch, override):
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    monkeypatch.setenv(
        "RESOLUTION_ADMIN_DATABASE_URL",
        "postgresql+psycopg2://local_user:local_password@localhost:55432/postgres" + override,
    )
    with pytest.raises(ValueError, match="administrative URL"):
        run_measurement(tmp_path / "out.json", **params)
    _assert_no_side_effects(calls)


def test_admin_url_rejects_host_list(tmp_path, monkeypatch):
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    monkeypatch.setenv(
        "RESOLUTION_ADMIN_DATABASE_URL",
        "postgresql://local_user:local_password@localhost,db.example.com:55432/postgres",
    )
    with pytest.raises(ValueError, match="administrative URL"):
        run_measurement(tmp_path / "out.json", **params)
    _assert_no_side_effects(calls)


@pytest.mark.parametrize(
    "variable",
    ("PGHOST", "PGHOSTADDR", "PGPORT", "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR"),
)
def test_runner_rejects_libpq_environment_before_side_effects(tmp_path, monkeypatch, variable):
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    monkeypatch.setenv(variable, "untrusted-setting")
    with pytest.raises(ValueError, match=variable) as error:
        run_measurement(tmp_path / "out.json", **params)
    assert "untrusted-setting" not in str(error.value)
    _assert_no_side_effects(calls)


def test_an_existing_output(tmp_path, monkeypatch):
    """Scenario: an existing output."""
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    output = tmp_path / "out.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        run_measurement(output, **params)
    _assert_no_side_effects(calls)


def test_scratch_name_accepts_valid_and_rejects_invalid():
    assert _scratch_name(lambda count: "0123456789abcdef") == "rag_spike_d5_0123456789abcdef"
    with pytest.raises(ValueError):
        _scratch_name(lambda count: "nothex")


def test_existing_scratch_state_does_not_trigger_cleanup(tmp_path, monkeypatch):
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)

    class ExistingCursor(FakeCursor):
        def fetchone(self):
            if "pg_database" in self.sql:
                return (True,)
            return super().fetchone()

    class ExistingConnection(FakeConnection):
        def cursor(self):
            return ExistingCursor(self)

    params["connection_factory"] = lambda dsn, dbname: ExistingConnection(calls)
    with pytest.raises(ValueError, match="already exists"):
        run_measurement(tmp_path / "out.json", **params)
    assert not any(
        item[0] in {"spawn", "setup", "mkdir"} for item in calls if isinstance(item, tuple)
    )
    assert not any("DROP" in entry for entry in calls if isinstance(entry, str))


def test_the_url_stays_out_of_process_arguments(tmp_path, monkeypatch):
    """Scenario: the URL stays out of process arguments."""
    inputs = write_inputs(tmp_path)
    calls, url, params = _harness(tmp_path, monkeypatch, inputs)
    report = run_measurement(tmp_path / "out.json", **params)
    assert report["status"] == "measured"
    for kind, args, kwargs in (entry for entry in calls if entry[0] == "spawn"):
        assert kind == "spawn"
        assert all(
            url not in str(arg)
            and "secret-db-password" not in str(arg)
            and "runner_login" not in str(arg)
            for arg in args
        )
        assert ("SPIKE_ADMIN_DSN" in kwargs["env"]) == ("postgres" in args)
        assert kwargs["env"]["ANONYMIZED_TELEMETRY"] == "False"
    assert "secret-db-password" not in (tmp_path / "out.json").read_text(encoding="utf-8")


def test_a_failed_trial(tmp_path, monkeypatch):
    """Scenario: a failed trial."""
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    original = params["spawner"]

    def fail(args, **kwargs):
        if "--trial" in args:
            return SimpleNamespace(
                returncode=2, stdout='{"error":"query: ValueError"}\n', stderr="secret-db-password"
            )
        return original(args, **kwargs)

    params["spawner"] = fail
    with pytest.raises(RunnerError, match="chroma_bm25.*0.*query: ValueError") as error:
        run_measurement(tmp_path / "out.json", **params)
    assert (error.value.stage, error.value.arm, error.value.trial, error.value.detail) == (
        "trial",
        "chroma_bm25",
        0,
        "query: ValueError",
    )
    assert "secret-db-password" not in str(error.value)
    assert [entry[0] for entry in calls if entry[0] in {"rmtree"}] == ["rmtree"]
    assert any("DROP DATABASE" in entry for entry in calls if isinstance(entry, str))
    assert any("DROP ROLE" in entry for entry in calls if isinstance(entry, str))
    assert not (tmp_path / "out.json").exists()


def test_child_error_cannot_echo_admin_username(tmp_path, monkeypatch):
    inputs = write_inputs(tmp_path)
    _, _, params = _harness(tmp_path, monkeypatch, inputs)
    monkeypatch.setenv(
        "RESOLUTION_ADMIN_DATABASE_URL",
        "postgresql://runner_login:passphrase_9831@localhost:55432/postgres",
    )
    original_spawn = params["spawner"]

    def unsafe_child(args, **kwargs):
        if "--trial" in args:
            return SimpleNamespace(
                returncode=2, stdout='{"error": "runner_login: ValueError"}\n', stderr=""
            )
        return original_spawn(args, **kwargs)

    params["spawner"] = unsafe_child
    with pytest.raises(RunnerError) as error:
        run_measurement(tmp_path / "out.json", **params)
    if "runner_login" in str(error.value):
        pytest.fail("runner error leaked the administrative user name")
    assert error.value.detail == "exit code 2"


def test_an_unstable_ranking(tmp_path, monkeypatch):
    """Scenario: an unstable ranking."""
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    original = params["spawner"]
    seen = 0

    def change(args, **kwargs):
        nonlocal seen
        result = original(args, **kwargs)
        if "--trial" in args and args[args.index("--trial") + 1] == "chroma_bm25":
            seen += 1
            if seen == 2:
                payload = json.loads(result.stdout)
                payload["rankings"]["chroma_fused"][0] = [1]
                result.stdout = json.dumps(payload) + "\n"
        return result

    params["spawner"] = change
    with pytest.raises(RunnerError, match="ranking") as error:
        run_measurement(tmp_path / "out.json", **params)
    assert error.value.stage == "stability"
    assert "chroma_fused" in error.value.detail
    assert any(item[0] == "rmtree" for item in calls)
    assert not (tmp_path / "out.json").exists()


def test_a_cleanup_failure(tmp_path, monkeypatch):
    """Scenario: a cleanup failure."""
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)

    class FailedDrop(FakeCursor):
        def execute(self, sql, params=None):
            if str(sql).startswith("DROP DATABASE"):
                raise RuntimeError("cannot drop")
            super().execute(sql, params)

    class FailedConnection(FakeConnection):
        def cursor(self):
            return FailedDrop(self)

    params["connection_factory"] = lambda dsn, dbname: FailedConnection(calls)
    report = run_measurement(tmp_path / "out.json", **params)
    assert report["status"] == "cleanup_failed"
    assert report["database"] == "rag_spike_d5_0123456789abcdef"
    assert report["cleanup"]["database_dropped"] is False
    assert "secret-db-password" not in json.dumps(report)


def test_setup_failure_releases_scratch_connection_before_database_drop(tmp_path, monkeypatch):
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs)
    cleanup_flags = []

    class ScratchConnection:
        def close(self):
            calls.append("scratch closed")

        def __del__(self):
            calls.append("scratch closed")

    def failed_setup(dsn, database, texts, embeddings):
        connection = ScratchConnection()
        calls.append(("setup connected", database, connection is not None))
        raise ValueError("failed after connecting")

    def record_cleanup(*args, **kwargs):
        flags = _cleanup(*args, **kwargs)
        cleanup_flags.append(flags)
        return flags

    params["setup_fn"] = failed_setup
    params["cleanup_fn"] = record_cleanup
    with pytest.raises(RunnerError) as error:
        run_measurement(tmp_path / "out.json", **params)
    drop = next(index for index, call in enumerate(calls) if str(call).startswith("DROP DATABASE"))
    assert calls.index("scratch closed") < drop
    assert getattr(error.value, "stage", None) == "setup"
    assert cleanup_flags == [
        {"database_dropped": True, "role_dropped": True, "chroma_dir_removed": True}
    ]
    assert any(str(call).startswith("DROP ROLE") for call in calls)
    assert any(isinstance(call, tuple) and call[0] == "rmtree" for call in calls)
    assert not (tmp_path / "out.json").exists()


def test_cleanup_force_drop_sql_and_success_flags(tmp_path):
    calls = []
    directory = tmp_path / "scratch"
    directory.mkdir()
    flags = _cleanup(
        "postgresql://localhost:55432/postgres",
        "rag_spike_d5_0123456789abcdef",
        directory,
        True,
        connection_factory=lambda dsn, dbname: FakeConnection(calls),
        remove_dir=lambda path: calls.append("directory"),
    )
    assert flags == {"database_dropped": True, "role_dropped": True, "chroma_dir_removed": True}
    assert 'DROP DATABASE IF EXISTS "rag_spike_d5_0123456789abcdef" WITH (FORCE)' in calls


def test_cleanup_order_and_bounded_55006_retry(tmp_path):
    calls = []
    times = iter([0, 1, 2, 31])

    class BusyError(Exception):
        pgcode = "55006"

    class Cursor:
        def execute(self, sql):
            calls.append(str(sql))
            if str(sql).startswith("DROP DATABASE"):
                raise BusyError("busy")

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Connection:
        autocommit = False

        def cursor(self):
            return Cursor()

        def close(self):
            calls.append("close")

    directory = tmp_path / "scratch"
    directory.mkdir()
    flags = _cleanup(
        "postgresql://localhost:55432/postgres",
        "rag_spike_d5_0123456789abcdef",
        directory,
        True,
        connection_factory=lambda dsn, dbname: Connection(),
        remove_dir=lambda path: calls.append("directory"),
        clock=lambda: next(times),
        sleep=lambda seconds: calls.append("sleep"),
    )
    assert flags == {"database_dropped": False, "role_dropped": True, "chroma_dir_removed": True}
    assert calls.count("sleep") <= 3
    database_drop = next(i for i, call in enumerate(calls) if call.startswith("DROP DATABASE"))
    role_drop = next(i for i, call in enumerate(calls) if call.startswith("DROP ROLE"))
    assert database_drop < role_drop < calls.index("directory")


def test_cli_reports_failed_postgres_trial_with_safe_fields(tmp_path, monkeypatch, capsys):
    inputs = write_inputs(tmp_path)
    calls, _, params = _harness(tmp_path, monkeypatch, inputs, trials=4)
    original_spawn = params["spawner"]
    postgres_count = 0

    def fail_fourth_postgres(args, **kwargs):
        nonlocal postgres_count
        if "--trial" in args and args[args.index("--trial") + 1] == "postgres":
            postgres_count += 1
            if postgres_count == 4:
                return SimpleNamespace(
                    returncode=2,
                    stdout='{"error": "query: ValueError"}\n',
                    stderr="untrusted child output",
                )
        return original_spawn(args, **kwargs)

    params["spawner"] = fail_fourth_postgres

    def measurement(output, *, vectors_path, queries_path):
        return run_measurement(output, **params)

    assert (
        runner_main(
            [
                "--vectors",
                str(inputs[1]),
                "--queries",
                str(inputs[2]),
                "--output",
                str(tmp_path / "out.json"),
            ],
            measurement_fn=measurement,
        )
        == 2
    )
    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 1
    assert json.loads(captured.out) == {
        "error": "runner",
        "stage": "trial",
        "arm": "postgres",
        "trial": 3,
        "detail": "query: ValueError",
    }
    assert not captured.err
    assert not (tmp_path / "out.json").exists()
    assert any(str(call).startswith("DROP DATABASE") for call in calls)


def test_cli_reports_preflight_case_counts(tmp_path, monkeypatch, capsys):
    inputs = write_inputs(tmp_path, cases=114)
    _, _, params = _harness(tmp_path, monkeypatch, inputs, expected_cases=115)
    monkeypatch.setenv(
        "RESOLUTION_ADMIN_DATABASE_URL",
        "postgresql://runner_login:passphrase_9831@localhost:55432/postgres",
    )

    def measurement(output, *, vectors_path, queries_path):
        return run_measurement(output, **params)

    assert (
        runner_main(
            [
                "--vectors",
                str(inputs[1]),
                "--queries",
                str(inputs[2]),
                "--output",
                str(tmp_path / "out.json"),
            ],
            measurement_fn=measurement,
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out) == {
        "error": "runner: ValueError",
        "message": "case count 114 differs from 115",
    }


def test_cli_omits_exception_messages_containing_credentials(tmp_path, monkeypatch, capsys):
    url = "postgresql+psycopg2://runner_login:raw%2Dpassword@localhost:55432/postgres"
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", url)

    for sensitive in (
        url,
        url.replace("postgresql+psycopg2", "postgresql"),
        "raw%2Dpassword",
        "raw-password",
        "runner_login",
    ):

        def measurement(output, *, vectors_path, queries_path):
            raise ValueError("untrusted error contains " + sensitive)

        assert (
            runner_main(
                [
                    "--vectors",
                    "unused",
                    "--queries",
                    "unused",
                    "--output",
                    str(tmp_path / "out.json"),
                ],
                measurement_fn=measurement,
            )
            == 2
        )
        captured = capsys.readouterr()
        if any(
            value in captured.out + captured.err
            for value in (url, "raw%2Dpassword", "raw-password", "runner_login")
        ):
            pytest.fail("CLI leaked a credential")
        if "message" in json.loads(captured.out):
            pytest.fail("CLI included an unsafe exception message")


@pytest.mark.parametrize(
    ("password", "message_value"),
    [
        ("review_secret", "review_secret"),
        ("review_secret", "review_user"),
        ("p%40ss%2Fword", "p@ss/word"),
        ("p%40ss%2Fword", "p%40ss%2Fword"),
    ],
    ids=("password", "user", "decoded-password", "encoded-password"),
)
def test_cli_omits_query_credentials(tmp_path, monkeypatch, capsys, password, message_value):
    url = (
        "postgresql+psycopg2://127.0.0.1:55432/postgres"
        f"?user=review_user&password={password}&sslmode=disable"
    )
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", url)

    def measurement(output, *, vectors_path, queries_path):
        raise ValueError("untrusted error contains " + message_value)

    result = runner_main(
        ["--vectors", "unused", "--queries", "unused", "--output", str(tmp_path / "out.json")],
        measurement_fn=measurement,
    )
    captured = capsys.readouterr()
    if result != 2 or len(captured.out.splitlines()) != 1 or captured.err:
        pytest.fail("CLI did not print exactly one error JSON line")
    payload = json.loads(captured.out)
    if message_value in captured.out or "message" in payload:
        pytest.fail("CLI included a query credential in its error output")


def test_cli_keeps_safe_message_with_query_credentials(tmp_path, monkeypatch, capsys):
    url = (
        "postgresql+psycopg2://127.0.0.1:55432/postgres"
        "?user=review_user&password=review_secret&sslmode=disable"
    )
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", url)

    def measurement(output, *, vectors_path, queries_path):
        raise ValueError("case count 114 differs from 115")

    result = runner_main(
        ["--vectors", "unused", "--queries", "unused", "--output", str(tmp_path / "out.json")],
        measurement_fn=measurement,
    )
    captured = capsys.readouterr()
    if result != 2 or captured.err:
        pytest.fail("CLI did not return a clean error")
    if json.loads(captured.out) != {
        "error": "runner: ValueError",
        "message": "case count 114 differs from 115",
    }:
        pytest.fail("CLI suppressed a safe exception message")
