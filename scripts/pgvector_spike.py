"""scripts/pgvector_spike.py -- D.1 preranker feasibility, offline measurement only.

Bounded helper for fused retrieval measurement (pgvector ANN + Russian FTS via
RRF in SQL), a chromadb/BM25 counterpart, and keyword-metric scoring. NOT
production; driven by an external Mac-only measured harness. D remains
incomplete.
"""
from __future__ import annotations

import json
import math

CONTEXT_CHAR_CAP = 6000


def _finite(value) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError("non-finite metric value")
    return out


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal-rank fusion; per-list dedupe; ties by ascending id."""
    if k < 0:
        raise ValueError("k must be non-negative")
    scores: dict[int, float] = {}
    for ranking in rankings:
        seen: set[int] = set()
        rank = 0
        for doc_id in ranking:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            rank += 1
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [doc_id for doc_id, _ in ordered]


_FUSED_SQL = """
WITH ann AS (
    SELECT c.idx AS idx,
           row_number() OVER (ORDER BY c.embedding <=> %s::vector) AS rnk
    FROM public.spike_chunks c
    JOIN public.kb_graph_nodes n
      ON n.tenant_id = c.tenant_id
     AND n.chunk_idx = c.idx
     AND n.kind = 'chunk'
    WHERE c.tenant_id = %s
    ORDER BY c.embedding <=> %s::vector
    LIMIT %s
),
fts AS (
    SELECT c.idx AS idx,
           row_number() OVER (ORDER BY ts_rank_cd(c.lex, q.tsq) DESC, c.idx ASC) AS rnk
    FROM public.spike_chunks c
    JOIN public.kb_graph_nodes n
      ON n.tenant_id = c.tenant_id
     AND n.chunk_idx = c.idx
     AND n.kind = 'chunk'
    CROSS JOIN (SELECT plainto_tsquery('russian', %s) AS tsq) AS q
    WHERE c.tenant_id = %s
      AND c.lex @@ q.tsq
    ORDER BY ts_rank_cd(c.lex, q.tsq) DESC, c.idx ASC
    LIMIT %s
),
fused AS (
    SELECT idx, rnk FROM ann
    UNION ALL
    SELECT idx, rnk FROM fts
)
SELECT idx, sum(1.0 / (60 + rnk)) AS score
FROM fused
GROUP BY idx
ORDER BY score DESC, idx ASC
LIMIT %s
"""


def pg_search(connection, vector: list[float], query: str, tenant: str,
              limit: int = 20) -> list[int]:
    """Fused ANN+FTS indices inside the caller's open transaction."""
    vec_param = json.dumps([float(x) for x in vector], separators=(",", ":"))
    cur = connection.cursor()
    try:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
        cur.execute(_FUSED_SQL, (vec_param, tenant, vec_param, limit,
                                 query, tenant, limit, 2 * limit))
        return [int(row[0]) for row in cur.fetchall()]
    finally:
        cur.close()


def chroma_search(collection, bm25, texts: list[str], query_vector: list[float],
                  query: str, limit: int = 20) -> list[int]:
    """Chroma ANN + positive-only BM25 fused via rrf. Runs BEFORE the reranker."""
    from vectordb._base_manager import _tokenize_for_bm25  # lazy heavy import

    result = collection.query(query_embeddings=[query_vector], n_results=limit)
    ann_ids = [int(doc_id) for doc_id in result["ids"][0]]
    query_tokens = _tokenize_for_bm25(query)
    scored = []
    for idx, raw_score in enumerate(bm25.get_scores(query_tokens)):
        score = float(raw_score)
        if score > 0.0:
            scored.append((-score, idx))
    scored.sort()
    lex_ids = [idx for _, idx in scored[:limit]]
    return rrf([ann_ids, lex_ids])


def score_rows(cases: list[dict], rankings: list[list[int]], texts: list[str],
               top_k: int = 5) -> dict:
    """Keyword metrics (context_precision / context_recall) over fused rankings."""
    from evaluation.ragas_eval import context_precision, context_recall  # lazy

    if not cases:
        raise ValueError("cases must be non-empty")
    if len(cases) != len(rankings):
        raise ValueError("cases and rankings must have equal lengths")
    case_ids = [case["case_id"] for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case_id values must be unique")
    rows = []
    for case, ranking in zip(cases, rankings, strict=True):
        for key in ("case_id", "query", "kws"):
            if key not in case:
                raise ValueError(f"case missing key: {key}")
        indices = []
        for value in ranking[:top_k]:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"invalid index {value!r}")
            if value < 0 or value >= len(texts):
                raise ValueError(f"index out of range {value!r}")
            indices.append(value)
        contexts = []
        used = 0
        for idx in indices:
            room = CONTEXT_CHAR_CAP - used
            if room <= 0:
                break
            chunk = texts[idx][:room]
            contexts.append(chunk)
            used += len(chunk)
        rows.append({
            "case_id": case["case_id"],
            "indices": indices,
            "context_precision": _finite(
                context_precision(case["query"], contexts, case["kws"])),
            "context_recall": _finite(
                context_recall(contexts, case["kws"])),
        })
    return {
        "rows": rows,
        "mean_context_precision": _finite(
            sum(r["context_precision"] for r in rows) / len(rows)),
        "mean_context_recall": _finite(
            sum(r["context_recall"] for r in rows) / len(rows)),
    }
