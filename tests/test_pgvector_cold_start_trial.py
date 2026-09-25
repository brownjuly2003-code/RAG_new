"""Trial tests for the Mac-only Phase D.5 measurement, not production code."""

import gzip
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.pgvector_cold_start import (
    main,
    run_chroma_trial,
    run_postgres_trial,
    text_digest,
)


def test_tenant_matches_loader_and_imports_leave_drivers_unloaded():
    import scripts.pgvector_cold_start as cold_start
    from scripts.pgvector_spike_db import TENANT as loader_tenant

    assert cold_start.TENANT == loader_tenant
    code = (
        "import json, sys\n"
        "import scripts.pgvector_cold_start\n"
        "import scripts.pgvector_spike\n"
        "import scripts.pgvector_ann\n"
        "print(json.dumps({name: name in sys.modules "
        "for name in ('psycopg2', 'chromadb')}))\n"
    )
    child = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(child.stdout.splitlines()[-1]) == {"psycopg2": False, "chromadb": False}


def _trial_inputs(tmp_path):
    queries = tmp_path / "queries.npy"
    np.save(queries, np.ones((2, 1024), dtype="float32"))
    case_files = [tmp_path / "one.jsonl", tmp_path / "two.jsonl"]
    for index, path in enumerate(case_files):
        path.write_text(
            json.dumps({"case_id": str(index), "query": "text"}) + "\n", encoding="utf-8"
        )
    return queries, case_files


def test_restore_out_of_order_and_telemetry(tmp_path):
    """Scenario: a restore out of order."""
    pytest.importorskip("langchain_core")
    pytest.importorskip("rank_bm25")
    queries, case_files = _trial_inputs(tmp_path)
    texts = ["first text", "second text"]

    class Collection:
        def __init__(self, ordered):
            self.ordered = ordered

        def get(self, include):
            assert include == ["documents", "metadatas"]
            metadata = [{"chunk_index": i} for i in self.ordered]
            return {"documents": [texts[i] for i in self.ordered], "metadatas": metadata}

        def query(self, **kwargs):
            return {"ids": [["0", "1"]]}

    class Client:
        def __init__(self, ordered, telemetry=False):
            self.collection = Collection(ordered)
            self.telemetry = telemetry

        def get_collection(self, name):
            assert name == "test"
            return self.collection

        def get_settings(self):
            return SimpleNamespace(anonymized_telemetry=self.telemetry)

    client = Client([1, 0])

    def fake_import(name):
        if name == "chromadb":
            return SimpleNamespace(PersistentClient=lambda path: client)
        return importlib.import_module(name)

    result = run_chroma_trial(
        tmp_path,
        "test",
        queries,
        case_files,
        text_digest(texts),
        importer=fake_import,
        rss_reader=lambda pid: 1024,
        clock=iter(range(100)).__next__,
        peak_reader=lambda: 2048,
        module_loaded=lambda name: False,
    )
    assert result["rankings"]["chroma_fused"] == [[0, 1], [0, 1]]
    assert result["baseline_rss_bytes"] == 1024
    with pytest.raises(ValueError, match="digest"):

        def out_of_order_import(name):
            if name == "chromadb":
                return SimpleNamespace(PersistentClient=lambda path: Client([1, 1]))
            return importlib.import_module(name)

        run_chroma_trial(
            tmp_path,
            "test",
            queries,
            case_files,
            text_digest(texts),
            importer=out_of_order_import,
            rss_reader=lambda pid: 1024,
            clock=iter(range(100)).__next__,
            peak_reader=lambda: 2048,
            module_loaded=lambda name: False,
        )
    with pytest.raises(ValueError, match="telemetry"):

        def telemetry_import(name):
            if name == "chromadb":
                return SimpleNamespace(PersistentClient=lambda path: Client([0, 1], True))
            return importlib.import_module(name)

        run_chroma_trial(
            tmp_path,
            "test",
            queries,
            case_files,
            text_digest(texts),
            importer=telemetry_import,
            rss_reader=lambda pid: 1024,
            clock=iter(range(100)).__next__,
            peak_reader=lambda: 2048,
            module_loaded=lambda name: False,
        )


def test_commit_after_every_query_and_backend_pid(tmp_path):
    """Scenario: a commit after every query."""
    queries, case_files = _trial_inputs(tmp_path)
    calls = []

    class Cursor:
        def execute(self, sql, params=None):
            calls.append(("execute", str(sql)))

        def fetchone(self):
            return (9876,)

        def close(self):
            calls.append(("cursor_close",))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            calls.append(("commit",))

        def close(self):
            calls.append(("close",))

    def fused(connection, vector, query, tenant, limit):
        calls.append(("pg_search",))
        return [0]

    def ann(connection, vector, tenant, limit, force_index, ef_search):
        calls.append(("ann_search", force_index, ef_search))
        return [1]

    def rss(pid):
        calls.append(("rss", pid))
        return 4096

    result = run_postgres_trial(
        "rag_spike_d5_0123456789abcdef",
        queries,
        case_files,
        importer=lambda name: SimpleNamespace(),
        connection_factory=lambda module, dsn, database: Connection(),
        admin_dsn="postgresql://localhost:55432/postgres",
        pg_search_fn=fused,
        ann_search_fn=ann,
        rss_reader=rss,
        clock=iter(range(100)).__next__,
        peak_reader=lambda: 8192,
        module_loaded=lambda name: False,
    )
    sequence = [x[0] for x in calls if x[0] in ("commit", "pg_search", "ann_search")]
    assert sequence == [
        "commit",
        "pg_search",
        "commit",
        "ann_search",
        "commit",
        "pg_search",
        "commit",
        "pg_search",
        "commit",
        "ann_search",
        "commit",
        "ann_search",
        "commit",
    ]
    assert ("rss", 9876) in calls
    assert result["backend_rss_bytes"] == 4096
    assert result["rankings"]["postgres_fused"] == [[0], [0]]
    assert result["rankings"]["postgres_hnsw"] == [[1], [1]]


def test_chroma_trial_rejects_preloaded_driver_before_timing(tmp_path):
    queries, case_files = _trial_inputs(tmp_path)
    calls = []

    def importer(name):
        calls.append(("import", name))
        return SimpleNamespace()

    with pytest.raises(ValueError, match="chromadb already loaded"):
        run_chroma_trial(
            tmp_path,
            "test",
            queries,
            case_files,
            "digest",
            importer=importer,
            rss_reader=lambda pid: 1024,
            clock=lambda: calls.append(("clock",)),
            chroma_search_fn=lambda *args, **kwargs: [],
            module_loaded=lambda name: name == "chromadb",
        )
    assert ("clock",) not in calls
    assert ("import", "chromadb") not in calls


def test_postgres_trial_rejects_preloaded_driver_before_timing(tmp_path):
    queries, case_files = _trial_inputs(tmp_path)
    calls = []

    def importer(name):
        calls.append(("import", name))
        return SimpleNamespace()

    with pytest.raises(ValueError, match="psycopg2 already loaded"):
        run_postgres_trial(
            "rag_spike_d5_0123456789abcdef",
            queries,
            case_files,
            importer=importer,
            connection_factory=lambda module, dsn, database: None,
            admin_dsn="postgresql://localhost:55432/postgres",
            rss_reader=lambda pid: 1024,
            clock=lambda: calls.append(("clock",)),
            pg_search_fn=lambda *args, **kwargs: [],
            ann_search_fn=lambda *args, **kwargs: [],
            module_loaded=lambda name: name == "psycopg2",
        )
    assert ("clock",) not in calls
    assert ("import", "psycopg2") not in calls


def test_real_mode_refuses_non_mac_and_telemetry(monkeypatch, capsys):
    """Real mode refusal before the first timed step."""
    argv = [
        "pgvector_cold_start",
        "--trial",
        "chroma_bm25",
        "--chroma-dir",
        "x",
        "--collection",
        "x",
        "--queries",
        "x",
        "--cases",
        "x",
        "--cases",
        "y",
        "--text-digest",
        "x",
    ]
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
    assert main(argv[1:]) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["error"].startswith("preflight:")
    assert main(["--trial", "invalid"]) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {
        "error": "preflight: ValueError"
    }
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    assert main(argv[1:]) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["error"].startswith("preflight:")


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac-only Chroma process acceptance")
def test_real_chroma_trial_child_process(tmp_path):
    """A persisted Chroma collection can be reopened by a fresh trial process."""
    pytest.importorskip("chromadb")
    pytest.importorskip("rank_bm25")
    pytest.importorskip("langchain_core")
    rng = np.random.default_rng(44)
    vectors = rng.normal(size=(30, 1024)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    texts = [f"document {i} text" for i in range(30)]
    archive = tmp_path / "chunks.json.gz"
    with gzip.open(archive, "wt", encoding="utf-8") as stream:
        json.dump(
            {"chunks": [{"page_content": text, "metadata": {"source": "test"}} for text in texts]},
            stream,
        )
    vector_path = tmp_path / "vectors.npz"
    np.savez(vector_path, embeddings=vectors)
    queries, case_files = _trial_inputs(tmp_path)
    chroma_dir = tmp_path / "chroma"
    env = {**os.environ, "ANONYMIZED_TELEMETRY": "False", "PYTHONDONTWRITEBYTECODE": "1"}
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.pgvector_cold_start",
            "--build-collection",
            "--chroma-dir",
            str(chroma_dir),
            "--collection",
            "test",
            "--archive",
            str(archive),
            "--vectors",
            str(vector_path),
            "--text-digest",
            text_digest(texts),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert build.returncode == 0, build.stdout[-500:]
    assert json.loads(build.stdout.splitlines()[-1])["build_ms"] > 0
    command = [
        sys.executable,
        "-m",
        "scripts.pgvector_cold_start",
        "--trial",
        "chroma_bm25",
        "--chroma-dir",
        str(chroma_dir),
        "--collection",
        "test",
        "--queries",
        str(queries),
        "--cases",
        str(case_files[0]),
        "--cases",
        str(case_files[1]),
        "--text-digest",
        text_digest(texts),
    ]
    runs = [
        subprocess.run(command, capture_output=True, text=True, timeout=120, env=env)
        for _ in range(2)
    ]
    assert all(run.returncode == 0 for run in runs), [run.stdout[-500:] for run in runs]
    records = [json.loads(run.stdout.splitlines()[-1]) for run in runs]
    assert records[0]["rankings"] == records[1]["rankings"]
    assert all(record["time_to_first_result_ms"] > 0 for record in records)
    assert all(record["rss_after_workload_bytes"] > 0 for record in records)
