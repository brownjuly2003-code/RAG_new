"""Mac-only Phase D.5 cold-start and memory measurement; not production code."""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import importlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

TENANT = "aircargo"
SCHEMA_VERSION = "d5-pgvector-cold-start-v2"
GATED_PATHS = ("postgres_fused", "postgres_hnsw")


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid arguments")


def text_digest(texts: list[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def trial_order(count: int):
    for trial in range(count):
        first = ("chroma_bm25", "postgres") if trial % 2 == 0 else ("postgres", "chroma_bm25")
        for position, arm in enumerate(first):
            yield trial, arm, position


def summarize(values: list[int | float]) -> dict[str, int | float]:
    import statistics

    if not values or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        for value in values
    ):
        raise ValueError("summary requires non-empty finite non-negative numbers")
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def parse_rss(output: str) -> int:
    value = output.strip()
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("invalid ps RSS output")
    return int(value) * 1024


def read_rss(pid: int, *, runner=subprocess.run) -> int:
    completed = runner(
        ["ps", "-o", "rss=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return parse_rss(completed.stdout)


def _peak_rss() -> int:
    import resource

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def rankings_sha256(rankings: list[list[int]]) -> str:
    encoded = json.dumps(rankings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare_d1(actual: list[list[int]], d1: list[list[int]]) -> dict[str, int | bool]:
    return {
        "equal": actual == d1,
        "matching_cases": sum(left == right for left, right in zip(actual, d1, strict=False)),
    }


def ranking_variation(records: list[dict], path: str, trials: int) -> dict:
    by_trial = {}
    for record in records:
        trial = record["trial"]
        if trial in by_trial:
            raise ValueError("duplicate trial")
        by_trial[trial] = record["rankings"][path]
    if set(by_trial) != set(range(trials)):
        raise ValueError("incomplete trials")
    first = by_trial[0]
    changed = set()
    trial_variation = []
    for trial in range(1, trials):
        rows = by_trial[trial]
        if len(rows) != len(first):
            raise ValueError("ranking case count mismatch")
        differing_cases = [
            index
            for index, (left, right) in enumerate(zip(rows, first, strict=True))
            if left != right
        ]
        changed.update(differing_cases)
        trial_variation.append({"trial": trial, "differing_cases": differing_cases})
    return {"trials": trial_variation, "distinct_cases": len(changed)}


def read_log_positions(chroma_dir) -> dict[str, int]:
    database_uri = (Path(chroma_dir) / "chroma.sqlite3").resolve().as_uri() + "?mode=ro"
    with contextlib.closing(sqlite3.connect(database_uri, uri=True)) as connection:
        log_seq_id = connection.execute("SELECT MAX(seq_id) FROM embeddings_queue").fetchone()[0]
        segments = connection.execute("SELECT id FROM segments WHERE scope = 'VECTOR'").fetchall()
        if len(segments) != 1:
            raise ValueError("expected one vector segment")
        row = connection.execute(
            "SELECT seq_id FROM max_seq_id WHERE segment_id = ?", (segments[0][0],)
        ).fetchone()
        vector_seq_id = row[0] if row is not None else 0
    if (
        type(log_seq_id) is not int
        or type(vector_seq_id) is not int
        or log_seq_id < 0
        or vector_seq_id < 0
        or vector_seq_id > log_seq_id
    ):
        raise ValueError("invalid Chroma sequence ids")
    return {
        "chroma_log_max_seq_id": log_seq_id,
        "chroma_vector_persisted_seq_id": vector_seq_id,
    }


_COMMON_FIELDS = {
    "import_ms",
    "open_ms",
    "first_query_ms",
    "time_to_first_result_ms",
    "workload_ms",
    "baseline_rss_bytes",
    "rss_after_workload_bytes",
    "peak_rss_bytes",
}
_ARM_FIELDS = {
    "chroma_bm25": {"restore_ms", "bm25_ms"},
    "postgres": {"first_ann_ms", "ann_workload_ms", "backend_rss_bytes"},
}
_PATHS = {
    "chroma_bm25": {"chroma_fused"},
    "postgres": {"postgres_fused", "postgres_hnsw"},
}


def validate_trial_record(record: dict, arm: str, case_count: int) -> dict:
    if arm not in _PATHS or record.get("arm") != arm:
        raise ValueError("trial arm mismatch")
    if not _COMMON_FIELDS | _ARM_FIELDS[arm] <= record.keys():
        raise ValueError("trial numeric field missing")
    rankings = record.get("rankings")
    if not isinstance(rankings, dict) or set(rankings) != _PATHS[arm]:
        raise ValueError("trial ranking paths mismatch")
    for path, rows in rankings.items():
        if not isinstance(rows, list) or len(rows) != case_count:
            raise ValueError(f"{path} ranking count mismatch")
        for row in rows:
            if not isinstance(row, list) or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in row
            ):
                raise ValueError(f"{path} ranking is invalid")
    for name, value in record.items():
        if name in ("arm", "rankings"):
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"invalid trial numeric field: {name}")
    return record


def build_report(context: dict, records: list[dict], cleanup: dict[str, bool]) -> dict:
    if not records:
        raise ValueError("no trials")
    expected_trials = context.get("trials", 7)
    if (
        isinstance(expected_trials, bool)
        or not isinstance(expected_trials, int)
        or expected_trials < 1
    ):
        raise ValueError("invalid trial count")
    first_rankings = {}
    report_records = []
    summary: dict[str, dict] = {arm: {} for arm in _PATHS}
    for arm in _PATHS:
        arm_records = [record for record in records if record["arm"] == arm]
        if len(arm_records) != expected_trials or {
            record["trial"] for record in arm_records
        } != set(range(expected_trials)):
            raise ValueError(f"incomplete {arm} trials")
        numeric = set(arm_records[0]) - {"arm", "rankings", "trial", "position"}
        if any(
            set(record) - {"arm", "rankings", "trial", "position"} != numeric
            for record in arm_records
        ):
            raise ValueError("inconsistent trial numeric fields")
        summary[arm] = {
            name: summarize([record[name] for record in arm_records]) for name in sorted(numeric)
        }
        trial_zero = next((record for record in arm_records if record["trial"] == 0), None)
        if trial_zero is None:
            raise ValueError("trial 0 missing")
        first_rankings.update(trial_zero["rankings"])
    for record in records:
        reduced = {key: value for key, value in record.items() if key != "rankings"}
        reduced["rankings_sha256"] = {
            path: rankings_sha256(rows) for path, rows in record["rankings"].items()
        }
        report_records.append(reduced)
    config = {
        "trials": context.get("trials", 7),
        "gated_ranking_paths": list(GATED_PATHS),
        "order": "chroma_bm25 first on even trials; postgres first on odd trials",
        "top_k": 20,
        "rrf_k": 60,
        "ef_search": 100,
        "force_index": True,
        "chroma_space": "cosine",
        "chroma_batch": 500,
        "collection": context.get("collection", "d5_aircargo"),
        "tenant": context.get("tenant", "aircargo"),
        "chunks": context["chunks"],
        "cases": context["cases"],
        "embedding_model": "BAAI/bge-m3",
        "query_vectors": "precomputed",
        "reranker": False,
        "embedding_model_loaded": False,
        "os_file_cache": "not_controlled",
        "postgres_restart": "not_controlled",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "measured" if all(cleanup.values()) and len(cleanup) == 3 else "cleanup_failed",
        "code_base": context["code_base"],
        "database": context["database"],
        "input_sha256": context["input_sha256"],
        "source_sha256": context["source_sha256"],
        "versions": context["versions"],
        "python": context["python"],
        "platform": context["platform"],
        "host": context["host"],
        "postgres": context["postgres"],
        "pgvector": context["pgvector"],
        "server_settings": context["server_settings"],
        "config": config,
        "setup": context["setup"],
        "host_load": context["host_load"],
        "trials": report_records,
        "summary": summary,
        "rankings": first_rankings,
        "chroma_fused_variation": ranking_variation(
            [record for record in records if record["arm"] == "chroma_bm25"],
            "chroma_fused",
            expected_trials,
        ),
        "d1_cross_check": context["d1_cross_check"],
        "cleanup": cleanup,
    }


def _load_trial_inputs(queries_path, case_files, importer, rss_reader):
    queries = np.load(queries_path, allow_pickle=False)
    cases = [
        json.loads(line)["query"]
        for path in case_files
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if queries.shape != (len(cases), 1024) or not np.isfinite(queries).all() or not cases:
        raise ValueError("trial query inputs are invalid")
    manager = importer("vectordb.manager")
    base_manager = importer("vectordb._base_manager")
    baseline = rss_reader(os.getpid())
    return queries.tolist(), cases, manager, base_manager, baseline


def _client(chromadb, chroma_dir):
    return chromadb.PersistentClient(path=str(chroma_dir))


def run_chroma_trial(
    chroma_dir,
    collection_name,
    queries_path,
    case_files,
    expected_digest,
    *,
    importer=importlib.import_module,
    client_factory=_client,
    rss_reader=read_rss,
    clock=time.perf_counter,
    peak_reader=_peak_rss,
    chroma_search_fn=None,
    module_loaded=lambda name: name in sys.modules,
) -> dict:
    queries, cases, manager, base_manager, baseline = _load_trial_inputs(
        queries_path, case_files, importer, rss_reader
    )
    if chroma_search_fn is None:
        from scripts.pgvector_spike import chroma_search as chroma_search_fn

    if module_loaded("chromadb"):
        raise ValueError("chromadb already loaded before timed import")
    first_start = clock()
    chromadb = importer("chromadb")
    imported = clock()
    client = client_factory(chromadb, chroma_dir)
    collection = client.get_collection(name=collection_name)
    opened = clock()
    vector_store = SimpleNamespace(_collection=collection)
    chunks = manager._restore_chunks_from_store(vector_store, TENANT)
    restored = clock()
    if not chunks:
        raise ValueError("restore returned no chunks")
    retriever = base_manager.HybridRetriever(vector_store=vector_store, chunks=chunks)
    bm25_done = clock()
    if retriever._bm25 is None:
        raise ValueError("BM25 index is absent")
    texts = [chunk.page_content for chunk in chunks]
    chroma_search_fn(collection, retriever._bm25, texts, queries[0], cases[0], limit=20)
    first_done = clock()
    workload_start = clock()
    rankings = [
        chroma_search_fn(collection, retriever._bm25, texts, vector, query, limit=20)
        for vector, query in zip(queries, cases, strict=True)
    ]
    workload_done = clock()
    after_rss = rss_reader(os.getpid())
    peak = peak_reader()
    if client.get_settings().anonymized_telemetry is not False:
        raise ValueError("telemetry is enabled")
    if len(texts) != len(collection.get(include=["documents", "metadatas"])["documents"]):
        raise ValueError("restored chunk count mismatch")
    if text_digest(texts) != expected_digest:
        raise ValueError("restored text digest mismatch")
    return {
        "arm": "chroma_bm25",
        "import_ms": 1000 * (imported - first_start),
        "open_ms": 1000 * (opened - imported),
        "restore_ms": 1000 * (restored - opened),
        "bm25_ms": 1000 * (bm25_done - restored),
        "first_query_ms": 1000 * (first_done - bm25_done),
        "time_to_first_result_ms": 1000 * (first_done - first_start),
        "workload_ms": 1000 * (workload_done - workload_start),
        "baseline_rss_bytes": baseline,
        "rss_after_workload_bytes": after_rss,
        "peak_rss_bytes": peak,
        "rankings": {"chroma_fused": rankings},
    }


def _pg_connection(module, dsn, database):
    parsed = module.extensions.parse_dsn(dsn)
    parsed.pop("dbname", None)
    return module.connect(**parsed, dbname=database)


def run_postgres_trial(
    database,
    queries_path,
    case_files,
    *,
    admin_dsn=None,
    importer=importlib.import_module,
    connection_factory=_pg_connection,
    rss_reader=read_rss,
    clock=time.perf_counter,
    peak_reader=_peak_rss,
    pg_search_fn=None,
    ann_search_fn=None,
    module_loaded=lambda name: name in sys.modules,
) -> dict:
    if not re.fullmatch(r"rag_spike_d5_[0-9a-f]{16}", database):
        raise ValueError("invalid scratch database name")
    queries, cases, _, _, baseline = _load_trial_inputs(
        queries_path, case_files, importer, rss_reader
    )
    if pg_search_fn is None:
        from scripts.pgvector_spike import pg_search as pg_search_fn
    if ann_search_fn is None:
        from scripts.pgvector_ann import ann_search as ann_search_fn
    dsn = admin_dsn if admin_dsn is not None else os.environ["SPIKE_ADMIN_DSN"]
    if module_loaded("psycopg2"):
        raise ValueError("psycopg2 already loaded before timed import")
    first_start = clock()
    psycopg2 = importer("psycopg2")
    imported = clock()
    connection = connection_factory(psycopg2, dsn, database)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'SET ROLE "{database}"')
        connection.commit()
        opened = clock()
        pg_search_fn(connection, queries[0], cases[0], TENANT, limit=20)
        connection.commit()
        first_done = clock()
        ann_search_fn(connection, queries[0], TENANT, 20, True, 100)
        connection.commit()
        first_ann_done = clock()
        workload_start = clock()
        fused_rankings = []
        for vector, query in zip(queries, cases, strict=True):
            fused_rankings.append(pg_search_fn(connection, vector, query, TENANT, limit=20))
            connection.commit()
        workload_done = clock()
        ann_start = clock()
        ann_rankings = []
        for vector in queries:
            ann_rankings.append(ann_search_fn(connection, vector, TENANT, 20, True, 100))
            connection.commit()
        ann_done = clock()
        after_rss = rss_reader(os.getpid())
        peak = peak_reader()
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            backend_pid = int(cursor.fetchone()[0])
        backend_rss = rss_reader(backend_pid)
    finally:
        connection.close()
    return {
        "arm": "postgres",
        "import_ms": 1000 * (imported - first_start),
        "open_ms": 1000 * (opened - imported),
        "first_query_ms": 1000 * (first_done - opened),
        "first_ann_ms": 1000 * (first_ann_done - first_done),
        "time_to_first_result_ms": 1000 * (first_done - first_start),
        "workload_ms": 1000 * (workload_done - workload_start),
        "ann_workload_ms": 1000 * (ann_done - ann_start),
        "baseline_rss_bytes": baseline,
        "rss_after_workload_bytes": after_rss,
        "peak_rss_bytes": peak,
        "backend_rss_bytes": backend_rss,
        "rankings": {"postgres_fused": fused_rankings, "postgres_hnsw": ann_rankings},
    }


def build_collection(
    chroma_dir,
    collection_name,
    archive,
    vectors_path,
    expected_digest,
    *,
    importer=importlib.import_module,
    client_factory=_client,
    clock=time.perf_counter,
    log_reader=read_log_positions,
) -> dict:
    with gzip.open(archive, "rb") as stream:
        chunks = json.loads(stream.read())["chunks"]
    texts = [chunk["page_content"] for chunk in chunks]
    if text_digest(texts) != expected_digest:
        raise ValueError("archive text digest mismatch")
    with np.load(vectors_path, allow_pickle=False) as cache:
        vectors = cache["embeddings"]
    if vectors.shape != (len(texts), 1024) or not np.isfinite(vectors).all():
        raise ValueError("collection vectors are invalid")
    started = clock()
    chromadb = importer("chromadb")
    client = client_factory(chromadb, chroma_dir)
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )
    for start in range(0, len(texts), 500):
        end = min(start + 500, len(texts))
        collection.add(
            ids=[str(index) for index in range(start, end)],
            documents=texts[start:end],
            metadatas=[
                {**chunks[index]["metadata"], "chunk_index": index} for index in range(start, end)
            ],
            embeddings=vectors[start:end].tolist(),
        )
    build_ms = 1000 * (clock() - started)
    return {"build_ms": build_ms, **log_reader(chroma_dir)}


def _require_real_mode():
    if sys.platform != "darwin":
        raise ValueError("Mac-only measurement")
    if os.environ.get("ANONYMIZED_TELEMETRY") != "False":
        raise ValueError("telemetry must be disabled")


def main(argv=None) -> int:
    parser = _ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-collection", action="store_true")
    mode.add_argument("--trial", choices=("chroma_bm25", "postgres"))
    for option in (
        "chroma-dir",
        "collection",
        "archive",
        "vectors",
        "text-digest",
        "database",
        "queries",
    ):
        parser.add_argument("--" + option)
    parser.add_argument("--cases", action="append")
    step = "preflight"
    try:
        args = parser.parse_args(argv)
        _require_real_mode()
        if args.build_collection:
            step = "build"
            if not all(
                (args.chroma_dir, args.collection, args.archive, args.vectors, args.text_digest)
            ):
                raise ValueError("build arguments missing")
            result = build_collection(
                args.chroma_dir, args.collection, args.archive, args.vectors, args.text_digest
            )
        elif args.trial == "chroma_bm25":
            step = "chroma_bm25"
            if not all(
                (args.chroma_dir, args.collection, args.queries, args.cases, args.text_digest)
            ):
                raise ValueError("trial arguments missing")
            result = run_chroma_trial(
                args.chroma_dir, args.collection, args.queries, args.cases, args.text_digest
            )
        else:
            step = "postgres"
            if not all((args.database, args.queries, args.cases)):
                raise ValueError("trial arguments missing")
            result = run_postgres_trial(args.database, args.queries, args.cases)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{step}: {type(exc).__name__}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
