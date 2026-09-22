"""Measure higher-ef HNSW behaviour for the published D.2 recall outlier."""

import argparse
import importlib.metadata
import json
import math
import os
import platform
import re
import time
from pathlib import Path

import psycopg2
from psycopg2.sql import SQL, Identifier

from scripts.pgvector_ann import explain_ann, plan_uses_hnsw, recall_at_k
from scripts.pgvector_ann_outlier import (
    BASELINE_EF_SEARCH,
    EF_SEARCH_VALUES,
    TOP_K,
    diagnosis_label,
    ranked_ann_search,
    ranked_exact_search,
)
from scripts.pgvector_ann_run import _git_code_base, _load_inputs, _sha256, _verify_rls
from scripts.pgvector_spike_db import TENANT, setup

CASE_ID = "aircargo-harassment-investigation-timeline"
REPETITIONS = 3
SCHEMA_VERSION = "d2-pgvector-ann-outlier-v1"
ROOT = Path(__file__).resolve().parents[1]


def _select_case(inputs):
    """Return the unique outlier's index, case row and parallel query vector."""
    matches = [
        index for index, case in enumerate(inputs["cases"]) if case.get("case_id") == CASE_ID
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {CASE_ID!r} case, found {len(matches)}")
    index = matches[0]
    if index >= len(inputs["queries"]):
        raise RuntimeError("outlier case has no parallel query vector")
    return index, inputs["cases"][index], inputs["queries"][index]


def _json_ranking(ranking, label):
    if len(ranking) != TOP_K:
        raise RuntimeError(f"{label} returned {len(ranking)} rows, expected {TOP_K}")
    ids = [row[0] for row in ranking]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"{label} returned duplicate ids")
    return [[int(row[0]), float(row[1])] for row in ranking]


def _run_repetitions(connection, vector):
    """Run exact and every ef_search arm three times in alternating order."""
    ascending = list(EF_SEARCH_VALUES)
    descending = list(reversed(EF_SEARCH_VALUES))
    reference = None
    runs = []
    for repetition in range(1, REPETITIONS + 1):
        if repetition % 2:
            steps = [("exact", None)] + [(f"ann-{ef_search}", ef_search) for ef_search in ascending]
        else:
            steps = [(f"ann-{ef_search}", ef_search) for ef_search in descending] + [
                ("exact", None)
            ]

        timings = {}
        rankings = {}
        for label, ef_search in steps:
            started = time.perf_counter()
            if ef_search is None:
                ranking = ranked_exact_search(connection, vector, TENANT, TOP_K)
            else:
                ranking = ranked_ann_search(connection, vector, TENANT, TOP_K, ef_search)
            elapsed_ms = 1000 * (time.perf_counter() - started)
            connection.commit()
            if not math.isfinite(elapsed_ms) or elapsed_ms <= 0:
                raise RuntimeError(f"invalid latency for {label}")
            rankings[label] = _json_ranking(ranking, label)
            timings[label] = float(elapsed_ms)

        if reference is None:
            reference = rankings
        else:
            for label, ranking in rankings.items():
                if ranking != reference[label]:
                    raise RuntimeError(f"{label} ranking differs between repetitions")
        runs.append(
            {
                "repetition": repetition,
                "order": [label for label, _ in steps],
                "timings_ms": timings,
                "rankings": rankings,
            }
        )
        print(f"repetition {repetition} complete", flush=True)
    return runs


def _summarize(runs):
    """Build canonical rankings, recall rows and a bounded diagnosis."""
    if not runs:
        raise ValueError("at least one repetition is required")
    canonical = runs[0]["rankings"]
    exact = canonical["exact"]
    exact_ids = [row[0] for row in exact]
    rows = []
    for ef_search in EF_SEARCH_VALUES:
        ranking = canonical[f"ann-{ef_search}"]
        approximate_ids = [row[0] for row in ranking]
        approximate_set = set(approximate_ids)
        rows.append(
            {
                "ef_search": ef_search,
                "ranking": ranking,
                "recall_at_20": recall_at_k(exact_ids, approximate_ids, TOP_K),
                "recovered_exact_ids": [
                    chunk_id for chunk_id in exact_ids if chunk_id in approximate_set
                ],
                "missed_exact_ids": [
                    chunk_id for chunk_id in exact_ids if chunk_id not in approximate_set
                ],
            }
        )
    recalls = [row["recall_at_20"] for row in rows]
    first_full = next((row["ef_search"] for row in rows if row["recall_at_20"] == 1), None)
    return {
        "exact": exact,
        "ef_rows": rows,
        "summary": {
            "first_full_recall_ef_search": first_full,
            "monotonic_nondecreasing_recall": all(
                left <= right for left, right in zip(recalls, recalls[1:], strict=False)
            ),
            "diagnosis": diagnosis_label(rows),
        },
    }


def _index_definition(connection):
    """Return the single HNSW embedding index on the scratch chunk table."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname=%s AND tablename=%s "
            "AND indexdef ILIKE %s AND indexdef ILIKE %s "
            "ORDER BY indexname",
            ("public", "spike_chunks", "%USING hnsw%", "%embedding%"),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
    if len(rows) != 1:
        raise RuntimeError(f"expected one HNSW embedding index, found {len(rows)}")
    definition = rows[0][0]
    if not isinstance(definition, str) or not definition:
        raise RuntimeError("HNSW index definition must be a nonempty string")
    return definition


def _connect_existing(dsn, database):
    """Connect to an existing local spike database and assume its role."""
    if len(database) > 50 or re.fullmatch(r"rag_spike_[a-z0-9_]+", database) is None:
        raise ValueError(f"refusing unexpected database name: {database!r}")
    admin_fields = psycopg2.extensions.parse_dsn(dsn)
    if admin_fields.get("host") not in {"127.0.0.1", "localhost"}:
        raise ValueError(f"refusing non-local admin host: {admin_fields.get('host')!r}")
    if str(admin_fields.get("port")) != "55432":
        raise ValueError(f"refusing unexpected admin port: {admin_fields.get('port')!r}")
    admin_fields.pop("dbname", None)
    connection = psycopg2.connect(**admin_fields, dbname=database)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(SQL("SET ROLE {}").format(Identifier(database)))
        finally:
            cursor.close()
        connection.commit()
    except Exception:
        connection.close()
        raise
    return connection


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("chunks", "vectors", "queries", "database", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--cases", action="append", required=True)
    parser.add_argument(
        "--reuse-existing-database",
        action="store_true",
        default=False,
        help="Measure the existing source index instead of a fresh rebuild.",
    )
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}")

    code_base = _git_code_base()
    inputs = _load_inputs(args)
    case_index, case, vector = _select_case(inputs)
    print(
        f"validated inputs {len(inputs['texts'])} {len(inputs['cases'])}; "
        f"selected {CASE_ID} at {case_index}",
        flush=True,
    )

    if args.reuse_existing_database:
        connection = _connect_existing(os.environ["SPIKE_ADMIN_DSN"], args.database)
        database_mode = "existing_index"
    else:
        connection = setup(
            os.environ["SPIKE_ADMIN_DSN"], args.database, inputs["texts"], inputs["vectors"]
        )
        database_mode = "fresh_rebuild"
    try:
        rls, postgres, pgvector = _verify_rls(connection, len(inputs["texts"]))
        index_definition = _index_definition(connection)
        baseline_plan = explain_ann(connection, vector, TENANT, TOP_K, True, BASELINE_EF_SEARCH)
        connection.commit()
        if not plan_uses_hnsw(baseline_plan):
            raise RuntimeError("forced baseline plan did not use the HNSW index")
        runs = _run_repetitions(connection, vector)
        summarized = _summarize(runs)
    finally:
        connection.close()

    sources = [
        Path(__file__),
        ROOT / "scripts/pgvector_ann_outlier.py",
        ROOT / "scripts/pgvector_ann_run.py",
        ROOT / "scripts/pgvector_ann.py",
        ROOT / "scripts/pgvector_spike_db.py",
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "code_base": code_base,
        "database": args.database,
        "case_id": CASE_ID,
        "case_index": case_index,
        "query": case["query"],
        "input_sha256": inputs["input_sha256"],
        "source_sha256": {path.name: _sha256(path) for path in sources},
        "versions": {
            package: importlib.metadata.version(package) for package in ("numpy", "psycopg2-binary")
        },
        "python": platform.python_version(),
        "postgres": postgres,
        "pgvector": pgvector,
        "index_definition": index_definition,
        "config": {
            "chunks": 5589,
            "cases": 115,
            "top_k": TOP_K,
            "ef_search_values": list(EF_SEARCH_VALUES),
            "baseline_ef_search": BASELINE_EF_SEARCH,
            "repetitions": REPETITIONS,
            "distance": "cosine",
            "hnsw_iterative_scan": "strict_order",
            "hnsw_plan_forced": True,
            "graph": "post-limit synthetic chunk-membership join",
            "embedding_action": "reused_without_reembedding",
            "reranker": False,
            "database_mode": database_mode,
        },
        "rls": rls,
        "planner": {
            "baseline_ef_search": BASELINE_EF_SEARCH,
            "baseline_uses_hnsw": True,
            "baseline_explain": baseline_plan,
        },
        "exact": summarized["exact"],
        "ef_rows": summarized["ef_rows"],
        "runs": runs,
        "summary": summarized["summary"],
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
