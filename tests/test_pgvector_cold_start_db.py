"""Database acceptance for the Mac-only Phase D.5 measurement, not production code."""

import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from scripts.pgvector_cold_start_run import _connect_admin, _normalize_admin_url, run_measurement
from scripts.pgvector_spike_db import setup


def _tiny_corpus(tmp_path):
    rng = np.random.default_rng(44)
    vectors = rng.normal(size=(40, 1024)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    texts = [f"document {i} text" for i in range(40)]
    raw = json.dumps(
        {"chunks": [{"page_content": text, "metadata": {"source": "test"}} for text in texts]}
    ).encode()
    archive = tmp_path / "chunks.json.gz"
    with gzip.open(archive, "wb") as stream:
        stream.write(raw)
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    vector_path = tmp_path / "chunks.npz"
    np.savez(
        vector_path,
        embeddings=vectors,
        chunk_text_digest=np.bytes_(digest.hexdigest()),
        embedding_model=np.bytes_("BAAI/bge-m3"),
    )
    queries = tmp_path / "d1-queries.npy"
    np.save(queries, vectors[:3])
    case_files = [
        tmp_path / "curated_cases_aircargo.jsonl",
        tmp_path / "curated_cases_aircargo_gr_multihop.jsonl",
    ]
    for path, ids in zip(case_files, ([0, 1], [2]), strict=True):
        path.write_text(
            "".join(json.dumps({"case_id": str(i), "query": f"document {i}"}) + "\n" for i in ids),
            encoding="utf-8",
        )
    d1 = tmp_path / "d1.json"
    inputs = {"ab_phase2_G2_graph_chunks.json": hashlib.sha256(raw).hexdigest()}
    inputs.update(
        {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [vector_path, queries, *case_files]
        }
    )
    d1.write_text(
        json.dumps(
            {
                "input_sha256": inputs,
                "runs": [
                    {
                        "chroma_bm25": {"rankings": [[0]] * 3},
                        "postgres": {"rankings": [[0]] * 3},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return archive, vector_path, queries, case_files, d1


def _require_database_gate():
    if not os.getenv("RESOLUTION_ADMIN_DATABASE_URL"):
        pytest.skip("RESOLUTION_ADMIN_DATABASE_URL is unset")
    for package in ("chromadb", "psycopg2", "rank_bm25", "langchain_core"):
        pytest.importorskip(package)


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac-only database acceptance")
def test_database_acceptance_on_tiny_corpus(tmp_path):
    """Real scratch lifecycle leaves no database or role behind."""
    _require_database_gate()
    archive, vector_path, queries, case_files, d1 = _tiny_corpus(tmp_path)
    report = run_measurement(
        tmp_path / "out.json",
        archive=archive,
        vectors_path=vector_path,
        queries_path=queries,
        case_files=case_files,
        d1_report=d1,
        expected_chunks=40,
        expected_cases=3,
        trials=2,
        code_base_provider=lambda: "a" * 40,
    )
    assert report["status"] == "measured"
    assert report["schema_version"] == "d5-pgvector-cold-start-v2"
    assert report["setup"]["chroma_log_max_seq_id"] == 40
    assert report["setup"]["chroma_vector_persisted_seq_id"] == 0
    assert report["chroma_fused_variation"]["trials"][0]["trial"] == 1
    assert all(report["cleanup"].values())
    assert len(report["trials"]) == 4
    for record in report["trials"]:
        for key in (
            "import_ms",
            "open_ms",
            "time_to_first_result_ms",
            "workload_ms",
            "baseline_rss_bytes",
            "rss_after_workload_bytes",
            "peak_rss_bytes",
        ):
            assert record[key] > 0
        if record["arm"] == "postgres":
            assert record["backend_rss_bytes"] > 0
    for path, ranking in report["rankings"].items():
        assert len(ranking) == 3, path
    dsn = _normalize_admin_url(os.environ["RESOLUTION_ADMIN_DATABASE_URL"])
    connection = _connect_admin(dsn, "postgres")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'rag_spike_d5_%'")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'rag_spike_d5_%'")
            assert cursor.fetchone()[0] == 0
    finally:
        connection.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac-only database acceptance")
def test_setup_failure_after_scratch_connect_removes_all_state(tmp_path):
    """A failed INSERT after scratch connection still permits complete cleanup."""
    _require_database_gate()
    archive, vector_path, queries, case_files, d1 = _tiny_corpus(tmp_path)
    names = []

    def failed_setup(dsn, name, texts, vectors):
        names.append(name)
        extra_vectors = np.concatenate((vectors, vectors[:1]), axis=0)
        return setup(dsn, name, [*texts, "\x00"], extra_vectors)

    output = tmp_path / "failed-out.json"
    with pytest.raises(RuntimeError) as error:
        run_measurement(
            output,
            archive=archive,
            vectors_path=vector_path,
            queries_path=queries,
            case_files=case_files,
            d1_report=d1,
            expected_chunks=40,
            expected_cases=3,
            trials=2,
            code_base_provider=lambda: "a" * 40,
            setup_fn=failed_setup,
        )
    assert getattr(error.value, "stage", None) == "setup"
    assert len(names) == 1
    assert not output.exists()
    assert not (Path(tempfile.gettempdir()) / names[0]).exists()
    dsn = _normalize_admin_url(os.environ["RESOLUTION_ADMIN_DATABASE_URL"])
    connection = _connect_admin(dsn, "postgres")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (names[0],))
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (names[0],))
            assert cursor.fetchone()[0] == 0
    finally:
        connection.close()
