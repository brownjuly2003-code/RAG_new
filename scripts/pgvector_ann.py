"""Offline helpers for the Phase D.2 pgvector ANN measurement."""

import json
import math

_SET_TENANT = "SELECT set_config('app.tenant_id', %s, true)"
_SET_EF_SEARCH = "SELECT set_config('hnsw.ef_search', %s, true)"
_SET_ITERATIVE_SCAN = "SET LOCAL hnsw.iterative_scan = 'strict_order'"
_SET_INDEXSCAN_ON = "SET LOCAL enable_indexscan = on"
_SET_INDEXSCAN_OFF = "SET LOCAL enable_indexscan = off"
_SET_BITMAPSCAN_ON = "SET LOCAL enable_bitmapscan = on"
_SET_BITMAPSCAN_OFF = "SET LOCAL enable_bitmapscan = off"
_SET_SEQSCAN_ON = "SET LOCAL enable_seqscan = on"
_SET_SEQSCAN_OFF = "SET LOCAL enable_seqscan = off"

_ANN_SQL = """
WITH candidates AS MATERIALIZED (
    SELECT s.tenant_id, s.idx, s.embedding <=> %s::vector AS distance
    FROM public.spike_chunks AS s
    WHERE s.tenant_id = %s
    ORDER BY s.embedding <=> %s::vector
    LIMIT %s
)
SELECT n.chunk_idx
FROM candidates
JOIN public.kb_graph_nodes AS n
  ON n.tenant_id = candidates.tenant_id AND n.chunk_idx = candidates.idx
WHERE n.kind = 'chunk'
ORDER BY candidates.distance, candidates.idx
""".strip()

_EXPLAIN_ANN_SQL = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + _ANN_SQL

_EXACT_SQL = """
SELECT s.idx
FROM public.spike_chunks AS s
WHERE s.tenant_id = %s
ORDER BY s.embedding <=> %s::vector, s.idx
LIMIT %s
""".strip()


def _require_positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(name + " must be a non-bool int")
    if value <= 0:
        raise ValueError(name + " must be positive")
    return value


def _encode_vector(vector):
    if not isinstance(vector, list):
        raise TypeError("vector must be a list")
    encoded = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("vector entries must be non-bool ints or floats")
        try:
            number = float(value)
        except OverflowError:
            raise ValueError("vector entries must be finite") from None
        if not math.isfinite(number):
            raise ValueError("vector entries must be finite")
        encoded.append(number)
    return json.dumps(encoded, separators=(",", ":"))


def _prepare(vector, tenant, limit):
    if not isinstance(tenant, str):
        raise TypeError("tenant must be a str")
    _require_positive_int(limit, "limit")
    return _encode_vector(vector)


def _head_ids(ranking, k, name):
    if not isinstance(ranking, list):
        raise TypeError(name + " ranking must be a list")
    seen = set()
    for entry in ranking[:k]:
        if isinstance(entry, bool) or not isinstance(entry, int):
            raise TypeError(name + " ranking entries must be non-bool ints")
        if entry in seen:
            raise ValueError(name + " ranking has a duplicate id within the first " + str(k))
        seen.add(entry)
    return seen


def recall_at_k(exact: list[int], approximate: list[int], k: int) -> float:
    _require_positive_int(k, "k")
    exact_ids = _head_ids(exact, k, "exact")
    approx_ids = _head_ids(approximate, k, "approximate")
    return len(exact_ids & approx_ids) / k


def plan_uses_hnsw(plan) -> bool:
    if isinstance(plan, list):
        return any(plan_uses_hnsw(item) for item in plan)
    if not isinstance(plan, dict):
        return False
    node_type = plan.get("Node Type")
    if node_type in ("Index Scan", "Index Only Scan"):
        index_name = str(plan.get("Index Name") or "").lower()
        if "embedding" in index_name or "hnsw" in index_name:
            return True
    for value in plan.values():
        if isinstance(value, (dict, list)) and plan_uses_hnsw(value):
            return True
    return False


def _apply_ann_settings(cursor, tenant, ef_search, force_index):
    cursor.execute(_SET_TENANT, (tenant,))
    cursor.execute(_SET_EF_SEARCH, (str(ef_search),))
    cursor.execute(_SET_ITERATIVE_SCAN)
    cursor.execute(_SET_INDEXSCAN_ON)
    cursor.execute(_SET_BITMAPSCAN_ON)
    cursor.execute(_SET_SEQSCAN_OFF if force_index else _SET_SEQSCAN_ON)


def _apply_exact_settings(cursor, tenant):
    cursor.execute(_SET_TENANT, (tenant,))
    cursor.execute(_SET_INDEXSCAN_OFF)
    cursor.execute(_SET_BITMAPSCAN_OFF)
    cursor.execute(_SET_SEQSCAN_ON)


def ann_search(
    connection,
    vector: list[float],
    tenant: str,
    limit: int = 20,
    force_index: bool = False,
    ef_search: int = 100,
) -> list[int]:
    encoded = _prepare(vector, tenant, limit)
    _require_positive_int(ef_search, "ef_search")
    cursor = connection.cursor()
    try:
        _apply_ann_settings(cursor, tenant, ef_search, force_index)
        cursor.execute(_ANN_SQL, (encoded, tenant, encoded, limit))
        return [int(row[0]) for row in cursor.fetchall()]
    finally:
        cursor.close()


def exact_search(connection, vector: list[float], tenant: str, limit: int = 20) -> list[int]:
    encoded = _prepare(vector, tenant, limit)
    cursor = connection.cursor()
    try:
        _apply_exact_settings(cursor, tenant)
        cursor.execute(_EXACT_SQL, (tenant, encoded, limit))
        return [int(row[0]) for row in cursor.fetchall()]
    finally:
        cursor.close()


def explain_ann(
    connection,
    vector: list[float],
    tenant: str,
    limit: int = 20,
    force_index: bool = False,
    ef_search: int = 100,
):
    encoded = _prepare(vector, tenant, limit)
    _require_positive_int(ef_search, "ef_search")
    cursor = connection.cursor()
    try:
        _apply_ann_settings(cursor, tenant, ef_search, force_index)
        cursor.execute(_EXPLAIN_ANN_SQL, (encoded, tenant, encoded, limit))
        return cursor.fetchone()[0]
    finally:
        cursor.close()
