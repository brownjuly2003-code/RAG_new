"""Measure pgvector HNSW recall against exact vector search on the Mac."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np

from scripts.pgvector_ann import (
    ann_search,
    exact_search,
    explain_ann,
    plan_uses_hnsw,
    recall_at_k,
)
from scripts.pgvector_spike_db import SENTINEL_TENANT, TENANT, setup

ROOT = Path(__file__).resolve().parents[1]
TOP_K = 20
EF_SEARCH = 100
REPETITIONS = 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_code_base() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError("tracked git worktree must be clean")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(revision) != 40:
        raise RuntimeError("unexpected git revision")
    return revision


def _load_inputs(args):
    input_paths = [Path(args.chunks), Path(args.vectors), Path(args.queries)]
    input_paths.extend(Path(filename) for filename in args.cases)
    names = [path.name for path in input_paths]
    if len(set(names)) != len(names):
        raise ValueError("input basenames must be unique")

    chunks = json.loads(input_paths[0].read_text(encoding="utf-8"))["chunks"]
    texts = [chunk["page_content"] for chunk in chunks]
    digest = hashlib.sha256()
    for text in texts:
        value = text.encode("utf-8")
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    with np.load(input_paths[1], allow_pickle=False) as cache:
        if cache["chunk_text_digest"].item().decode() != digest.hexdigest():
            raise ValueError("chunk text digest mismatch")
        if cache["embedding_model"].item().decode() != "BAAI/bge-m3":
            raise ValueError("unexpected embedding model")
        vectors = cache["embeddings"]

    cases = []
    buckets = {}
    case_buckets = []
    for path in input_paths[3:]:
        bucket = path.stem
        if bucket in buckets:
            raise ValueError("case bucket names must be unique")
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        start = len(cases)
        for row in rows:
            cases.append({"case_id": row["case_id"], "query": row["query"]})
            case_buckets.append(bucket)
        buckets[bucket] = {"start": start, "end": len(cases)}
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("case_id values must be unique")

    queries = np.load(input_paths[2], allow_pickle=False)
    if len(texts) != 5589 or len(cases) != 115:
        raise ValueError("canonical D.2 run requires 5589 chunks and 115 cases")
    if vectors.shape != (len(texts), 1024) or queries.shape != (len(cases), 1024):
        raise ValueError("unexpected embedding shapes")
    if not np.isfinite(vectors).all() or not np.isfinite(queries).all():
        raise ValueError("embeddings must be finite")
    return {
        "texts": texts,
        "vectors": vectors,
        "queries": queries.tolist(),
        "cases": cases,
        "case_buckets": case_buckets,
        "buckets": buckets,
        "input_sha256": {path.name: _sha256(path) for path in input_paths},
    }


def _verify_rls(connection, chunk_count: int) -> tuple[dict[str, int], str, str]:
    observations = {}
    postgres = ""
    pgvector = ""
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        if cursor.fetchone() != (False, False):
            raise RuntimeError("measurement role must be NOSUPERUSER and NOBYPASSRLS")
        for tenant, expected in (("", 0), (TENANT, chunk_count), (SENTINEL_TENANT, 1)):
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            for table in ("spike_chunks", "kb_graph_nodes"):
                cursor.execute(f"SELECT count(*) FROM public.{table}")
                count = int(cursor.fetchone()[0])
                if count != expected:
                    raise RuntimeError(f"unexpected RLS count for {tenant or 'unset'}:{table}")
                observations[f"{tenant or 'unset'}:{table}"] = count
                if tenant == TENANT:
                    cursor.execute(
                        f"SELECT count(*) FROM public.{table} WHERE tenant_id=%s",
                        (SENTINEL_TENANT,),
                    )
                    if cursor.fetchone()[0] != 0:
                        raise RuntimeError("cross-tenant row visible")
            connection.commit()
        cursor.execute("SELECT version()")
        postgres = cursor.fetchone()[0]
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
        pgvector = cursor.fetchone()[0]
    connection.commit()
    return observations, postgres, pgvector


def _call(connection, arm: str, vector: list[float]) -> list[int]:
    if arm == "exact":
        return exact_search(connection, vector, TENANT, TOP_K)
    return ann_search(connection, vector, TENANT, TOP_K, True, EF_SEARCH)


def _run_repetitions(connection, queries: list[list[float]]) -> list[dict]:
    runs = []
    for repetition in range(REPETITIONS):
        result = {}
        order = ("exact", "hnsw") if repetition % 2 == 0 else ("hnsw", "exact")
        for arm in order:
            rankings = []
            timings = []
            for vector in queries:
                started = time.perf_counter()
                ranking = _call(connection, arm, vector)
                elapsed = 1000 * (time.perf_counter() - started)
                connection.commit()
                if not np.isfinite(elapsed) or elapsed <= 0:
                    raise RuntimeError("invalid query timing")
                rankings.append(ranking)
                timings.append(float(elapsed))
            result[arm] = {"rankings": rankings, "latency_ms": timings}
        runs.append(result)
        print(f"repetition {repetition + 1} complete", flush=True)
    for arm in ("exact", "hnsw"):
        expected = runs[0][arm]["rankings"]
        if any(run[arm]["rankings"] != expected for run in runs[1:]):
            raise RuntimeError(f"{arm} rankings changed between repetitions")
    return runs


def _metrics(rows: list[dict], runs: list[dict], buckets: dict) -> dict:
    ranges = {"global": {"start": 0, "end": len(rows)}, **buckets}
    output = {}
    for name, bounds in ranges.items():
        start, end = bounds["start"], bounds["end"]
        recalls = [row["recall_at_20"] for row in rows[start:end]]
        latency_runs = []
        for run in runs:
            measured = {}
            for arm in ("exact", "hnsw"):
                timings = run[arm]["latency_ms"][start:end]
                measured[arm] = {
                    "latency_p50_ms": float(np.percentile(timings, 50)),
                    "latency_p95_ms": float(np.percentile(timings, 95)),
                }
            latency_runs.append(measured)
        output[name] = {
            "cases": end - start,
            "mean_recall_at_20": float(sum(recalls) / len(recalls)),
            "min_recall_at_20": float(min(recalls)),
            "latency_runs": latency_runs,
        }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("chunks", "vectors", "queries", "database", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--cases", action="append", required=True)
    args = parser.parse_args()
    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}")
    code_base = _git_code_base()
    inputs = _load_inputs(args)
    print("validated inputs 5589 115", flush=True)

    connection = setup(
        os.environ["SPIKE_ADMIN_DSN"], args.database, inputs["texts"], inputs["vectors"]
    )
    try:
        rls, postgres, pgvector = _verify_rls(connection, len(inputs["texts"]))
        first_vector = inputs["queries"][0]
        for arm in ("exact", "hnsw"):
            _call(connection, arm, first_vector)
            connection.commit()
        ann_search(connection, first_vector, TENANT, TOP_K, False, EF_SEARCH)
        connection.commit()
        default_plan = explain_ann(connection, first_vector, TENANT, TOP_K, False, EF_SEARCH)
        connection.commit()
        forced_plan = explain_ann(connection, first_vector, TENANT, TOP_K, True, EF_SEARCH)
        connection.commit()
        if not plan_uses_hnsw(forced_plan):
            raise RuntimeError("forced candidate plan did not use the HNSW embedding index")

        runs = _run_repetitions(connection, inputs["queries"])
        exact_rankings = runs[0]["exact"]["rankings"]
        hnsw_rankings = runs[0]["hnsw"]["rankings"]
        rows = []
        for case, bucket, exact, hnsw in zip(
            inputs["cases"],
            inputs["case_buckets"],
            exact_rankings,
            hnsw_rankings,
            strict=True,
        ):
            rows.append(
                {
                    "case_id": case["case_id"],
                    "bucket": bucket,
                    "exact_indices": exact,
                    "hnsw_indices": hnsw,
                    "recall_at_20": recall_at_k(exact, hnsw, TOP_K),
                }
            )
        sources = [
            Path(__file__),
            ROOT / "scripts/pgvector_ann.py",
            ROOT / "scripts/pgvector_spike_db.py",
        ]
        report = {
            "schema_version": "d2-pgvector-ann-v1",
            "code_base": code_base,
            "database": args.database,
            "input_sha256": inputs["input_sha256"],
            "source_sha256": {path.name: _sha256(path) for path in sources},
            "versions": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "psycopg2-binary")
            },
            "python": platform.python_version(),
            "postgres": postgres,
            "pgvector": pgvector,
            "config": {
                "chunks": len(inputs["texts"]),
                "cases": len(inputs["cases"]),
                "top_k": TOP_K,
                "hnsw_ef_search": EF_SEARCH,
                "hnsw_iterative_scan": "strict_order",
                "repetitions": REPETITIONS,
                "distance": "cosine",
                "default_plan_forced": False,
                "hnsw_plan_forced": True,
                "graph": "post-limit chunk-membership join",
                "cold_start_ram": "not_measured",
                "reranker": False,
            },
            "rls": rls,
            "planner": {
                "default_uses_hnsw": plan_uses_hnsw(default_plan),
                "forced_uses_hnsw": True,
                "default_explain": default_plan,
                "forced_explain": forced_plan,
            },
            "buckets": inputs["buckets"],
            "rows": rows,
            "runs": runs,
            "metrics": _metrics(rows, runs, inputs["buckets"]),
        }
        payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        with output_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        connection.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
