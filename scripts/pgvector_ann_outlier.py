"""Focused helpers for the Phase D.2 pgvector ANN outlier diagnosis."""

import json
import math

TOP_K = 20
EF_SEARCH_VALUES = (40, 100, 200, 400, 800, 1000)
BASELINE_EF_SEARCH = 100

_SET_TENANT_SQL = "SELECT set_config('app.tenant_id', %s, true)"
_SET_EF_SEARCH_SQL = "SELECT set_config('hnsw.ef_search', %s, true)"

_EXACT_SEARCH_SQL = """
SELECT s.idx, s.embedding <=> %s::vector AS distance
FROM public.spike_chunks AS s
WHERE s.tenant_id = %s
ORDER BY distance, s.idx
LIMIT %s
""".strip()

_ANN_SEARCH_SQL = """
WITH candidates AS MATERIALIZED (
    SELECT s.tenant_id, s.idx, s.embedding <=> %s::vector AS distance
    FROM public.spike_chunks AS s
    WHERE s.tenant_id = %s
    ORDER BY s.embedding <=> %s::vector
    LIMIT %s
)
SELECT n.chunk_idx, candidates.distance
FROM candidates
JOIN public.kb_graph_nodes AS n
  ON n.tenant_id = candidates.tenant_id AND n.chunk_idx = candidates.idx
WHERE n.kind = 'chunk'
ORDER BY candidates.distance, candidates.idx
""".strip()


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_ef_search_values(values) -> tuple[int, ...]:
    """Validate an increasing ef_search sweep containing the D.2 baseline."""
    try:
        items = tuple(values)
    except TypeError as exc:
        raise TypeError("ef_search values must be iterable") from exc
    if not items:
        raise ValueError("ef_search values must not be empty")
    for item in items:
        if not _is_int(item):
            raise TypeError("ef_search values must be non-bool ints")
        if item <= 0:
            raise ValueError("ef_search values must be positive")
    if len(set(items)) != len(items):
        raise ValueError("ef_search values must be unique")
    if any(left >= right for left, right in zip(items, items[1:], strict=False)):
        raise ValueError("ef_search values must be strictly increasing")
    if BASELINE_EF_SEARCH not in items:
        raise ValueError(f"ef_search values must include {BASELINE_EF_SEARCH}")
    return items


def diagnosis_label(rows) -> str:
    """Classify whether greater ef_search recovers the baseline miss."""
    if isinstance(rows, (str, bytes, dict)):
        raise TypeError("rows must be an iterable of dicts")
    try:
        row_list = list(rows)
    except TypeError as exc:
        raise TypeError("rows must be iterable") from exc
    if len(row_list) != len(EF_SEARCH_VALUES):
        raise ValueError("rows must cover EF_SEARCH_VALUES exactly")

    recalls = {}
    for row, expected_ef in zip(row_list, EF_SEARCH_VALUES, strict=True):
        if not isinstance(row, dict):
            raise TypeError("each row must be a dict")
        ef_search = row["ef_search"]
        recall = row["recall_at_20"]
        if not _is_int(ef_search):
            raise TypeError("row ef_search must be a non-bool int")
        if ef_search != expected_ef:
            raise ValueError("rows must match EF_SEARCH_VALUES in order")
        if not _is_number(recall):
            raise TypeError("recall_at_20 must be a non-bool number")
        recall_value = float(recall)
        if not math.isfinite(recall_value):
            raise ValueError("recall_at_20 must be finite")
        if not 0 <= recall_value <= 1:
            raise ValueError("recall_at_20 must be within [0, 1]")
        recalls[ef_search] = recall_value

    if recalls[BASELINE_EF_SEARCH] == 1:
        return "already_full_at_baseline"
    if any(
        recalls[ef_search] == 1 for ef_search in EF_SEARCH_VALUES if ef_search > BASELINE_EF_SEARCH
    ):
        return "recovered_by_higher_ef_search"
    return "not_recovered_at_max_ef_search"


def _validate_positive_int(value, name: str) -> int:
    if not _is_int(value):
        raise TypeError(f"{name} must be a non-bool int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _encode_vector(vector) -> str:
    if not isinstance(vector, list):
        raise TypeError("vector must be a list")
    encoded = []
    for value in vector:
        if not _is_number(value):
            raise TypeError("vector entries must be non-bool numbers")
        try:
            number = float(value)
        except OverflowError:
            raise ValueError("vector entries must be finite") from None
        if not math.isfinite(number):
            raise ValueError("vector entries must be finite")
        encoded.append(number)
    return json.dumps(encoded, separators=(",", ":"))


def _prepare(vector, tenant, limit) -> str:
    if not isinstance(tenant, str):
        raise TypeError("tenant must be a str")
    _validate_positive_int(limit, "limit")
    return _encode_vector(vector)


def _normalize_rows(rows) -> list[tuple[int, float]]:
    normalized = []
    seen = set()
    for row in rows:
        if isinstance(row, (str, bytes, dict)):
            raise ValueError("each result row must contain id and distance")
        try:
            fields = list(row)
        except TypeError as exc:
            raise ValueError("each result row must contain id and distance") from exc
        if len(fields) != 2:
            raise ValueError("each result row must contain id and distance")
        chunk_idx, distance = fields
        if not _is_int(chunk_idx):
            raise TypeError("chunk id must be a non-bool int")
        if not _is_number(distance):
            raise TypeError("distance must be a non-bool number")
        try:
            distance_value = float(distance)
        except OverflowError:
            raise ValueError("distance must be finite") from None
        if not math.isfinite(distance_value):
            raise ValueError("distance must be finite")
        if chunk_idx in seen:
            raise ValueError("ranked result contains duplicate ids")
        seen.add(chunk_idx)
        normalized.append((chunk_idx, distance_value))
    if any(
        (right[1], right[0]) < (left[1], left[0])
        for left, right in zip(normalized, normalized[1:], strict=False)
    ):
        raise ValueError("ranked result must be ordered by distance then id")
    return normalized


def ranked_exact_search(
    connection, vector: list[float], tenant: str, limit: int = TOP_K
) -> list[tuple[int, float]]:
    """Run exact cosine ranking with vector indexes disabled."""
    encoded = _prepare(vector, tenant, limit)
    cursor = connection.cursor()
    try:
        cursor.execute(_SET_TENANT_SQL, (tenant,))
        cursor.execute("SET LOCAL enable_indexscan = off")
        cursor.execute("SET LOCAL enable_bitmapscan = off")
        cursor.execute("SET LOCAL enable_seqscan = on")
        cursor.execute(_EXACT_SEARCH_SQL, (encoded, tenant, limit))
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return _normalize_rows(rows)


def ranked_ann_search(
    connection,
    vector: list[float],
    tenant: str,
    limit: int = TOP_K,
    ef_search: int = BASELINE_EF_SEARCH,
) -> list[tuple[int, float]]:
    """Run the D.2 HNSW candidate query and return distances."""
    encoded = _prepare(vector, tenant, limit)
    _validate_positive_int(ef_search, "ef_search")
    cursor = connection.cursor()
    try:
        cursor.execute(_SET_TENANT_SQL, (tenant,))
        cursor.execute(_SET_EF_SEARCH_SQL, (str(ef_search),))
        cursor.execute("SET LOCAL hnsw.iterative_scan = 'strict_order'")
        cursor.execute("SET LOCAL enable_indexscan = on")
        cursor.execute("SET LOCAL enable_bitmapscan = on")
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute(_ANN_SEARCH_SQL, (encoded, tenant, encoded, limit))
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return _normalize_rows(rows)
