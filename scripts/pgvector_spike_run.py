"""Independent measurement/acceptance driver for the GLM-authored Phase D helpers."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import time
from pathlib import Path

import chromadb
import numpy as np
from rank_bm25 import BM25Okapi

from scripts.pgvector_spike import _FUSED_SQL, chroma_search, pg_search, score_rows
from scripts.pgvector_spike_db import setup
from vectordb._base_manager import _tokenize_for_bm25


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("chunks", "vectors", "queries", "database", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--cases", action="append", required=True)
    args = parser.parse_args()
    chunks = json.loads(Path(args.chunks).read_text(encoding="utf-8"))["chunks"]
    texts = [c["page_content"] for c in chunks]
    digest = hashlib.sha256()
    for text in texts:
        value = text.encode("utf-8")
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    with np.load(args.vectors, allow_pickle=False) as cache:
        assert cache["chunk_text_digest"].item().decode() == digest.hexdigest()
        assert cache["embedding_model"].item().decode() == "BAAI/bge-m3"
        vectors = cache["embeddings"]
    cases, buckets = [], {}
    for filename in args.cases:
        rows = [json.loads(line) for line in Path(filename).read_text(encoding="utf-8").splitlines() if line.strip()]
        start = len(cases)
        cases.extend({"case_id": r["case_id"], "query": r["query"], "kws": r["expected"]["answer_contains"]} for r in rows)
        buckets[Path(filename).stem] = (start, len(cases))
    assert len({c["case_id"] for c in cases}) == len(cases)
    queries = np.load(args.queries, allow_pickle=False)
    assert vectors.shape == (len(texts), 1024) and queries.shape == (len(cases), 1024)
    assert np.isfinite(vectors).all() and np.isfinite(queries).all()
    print("validated inputs", len(texts), len(cases), flush=True)
    conn = setup(os.environ["SPIKE_ADMIN_DSN"], args.database, texts, vectors)
    rls = {}
    with conn.cursor() as cur:
        cur.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        assert cur.fetchone() == (False, False)
        for tenant, expected in (("", 0), ("aircargo", len(texts)), ("zzz_other", 1)):
            cur.execute("SELECT set_config('app.tenant_id',%s,true)", (tenant,))
            for table in ("spike_chunks", "kb_graph_nodes"):
                cur.execute(f"SELECT count(*) FROM public.{table}")
                count = cur.fetchone()[0]
                assert count == expected
                rls[f"{tenant or 'unset'}:{table}"] = count
                if tenant == "aircargo":
                    cur.execute(f"SELECT count(*) FROM public.{table} WHERE tenant_id='zzz_other'")
                    assert cur.fetchone()[0] == 0
            conn.commit()
        cur.execute("SELECT version()")
        postgres = cur.fetchone()[0]
        cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
        vector_version = cur.fetchone()[0]
    conn.commit()
    client = chromadb.EphemeralClient()
    collection = client.create_collection("d1_aircargo", metadata={"hnsw:space": "cosine"})
    for start in range(0, len(texts), 500):
        end = min(start + 500, len(texts))
        collection.add(ids=[str(i) for i in range(start, end)], embeddings=vectors[start:end].tolist())
    bm25 = BM25Okapi([_tokenize_for_bm25(t) for t in texts])
    print("database, RLS, Chroma and BM25 ready", flush=True)
    query_lists = queries.tolist()
    search = {
        "postgres": lambda v, q: pg_search(conn, v, q, "aircargo"),
        "chroma_bm25": lambda v, q: chroma_search(collection, bm25, texts, v, q),
    }
    for function in search.values():
        function(query_lists[0], cases[0]["query"])
        conn.commit()
    runs = []
    for repetition in range(3):
        run = {}
        for arm in (list(search) if repetition % 2 == 0 else list(reversed(search))):
            rankings, timings = [], []
            for case, vector in zip(cases, query_lists, strict=True):
                started = time.perf_counter()
                ranking = search[arm](vector, case["query"])
                timings.append(1000 * (time.perf_counter() - started))
                rankings.append(ranking)
                conn.commit()
            metrics = {}
            for bucket, (start, end) in buckets.items():
                metrics[bucket] = score_rows(cases[start:end], rankings[start:end], texts)
                metrics[bucket]["latency_p50_ms"] = float(np.percentile(timings[start:end], 50))
                metrics[bucket]["latency_p95_ms"] = float(np.percentile(timings[start:end], 95))
            run[arm] = {"rankings": rankings, "latency_ms": timings, "metrics": metrics}
        runs.append(run)
        print("repetition", repetition + 1, "complete", flush=True)
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id','aircargo',true)")
        vector = json.dumps(query_lists[0], separators=(",", ":"))
        cur.execute("EXPLAIN (FORMAT JSON) " + _FUSED_SQL,
                    (vector, "aircargo", vector, 20, cases[0]["query"], "aircargo", 20, 40))
        plan = cur.fetchone()[0]
    conn.close()
    inputs = [args.chunks, args.vectors, args.queries, *args.cases]
    sources = [__file__, "scripts/pgvector_spike.py", "scripts/pgvector_spike_db.py",
               "evaluation/ragas_eval.py", "vectordb/_base_manager.py"]
    report = {
        "code_base": "fa0146c", "database": args.database,
        "input_sha256": {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs},
        "source_sha256": {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources},
        "versions": {p: importlib.metadata.version(p) for p in ("numpy", "chromadb", "rank-bm25", "psycopg2-binary")},
        "python": platform.python_version(), "postgres": postgres, "pgvector": vector_version,
        "config": {"chunks": len(texts), "cases": len(cases), "top_k": 5, "context_chars": 6000,
                   "branch_limit": 20, "rrf_k": 60, "rrf_rank_base": 1, "repetitions": 3,
                   "reranker": False, "embedding_model": "BAAI/bge-m3",
                   "graph": "synthetic chunk membership only", "cold_start_ram": "not_measured"},
        "rls": rls, "explain": plan, "runs": runs,
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for arm, result in runs[0].items():
        for bucket, metric in result["metrics"].items():
            print(arm, bucket, {k: v for k, v in metric.items() if k != "rows"})
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
