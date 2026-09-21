"""Offline tests for scripts.pgvector_ann (red phase: module not implemented yet)."""

import pytest

from scripts.pgvector_ann import (
    ann_search,
    exact_search,
    explain_ann,
    plan_uses_hnsw,
    recall_at_k,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows, self.executed, self.params, self.closed = rows, [], [], False

    def execute(self, sql, params=None):
        self.executed.append(sql)
        self.params.append(params)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows):
        self.rows, self.cursors, self.commits, self.closed = rows, [], 0, False

    def cursor(self):
        self.cursors.append(FakeCursor(self.rows))
        return self.cursors[-1]

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def _flat_params(cur):
    return [v for p in cur.params for v in (p if isinstance(p, (list, tuple)) else (p,))]


def _setting(cur, name):
    return next(sql for sql in cur.executed if name in sql.lower()).lower()


@pytest.mark.parametrize(
    ("exact", "approx", "k", "expected"),
    [
        ([1, 2, 3, 4], [2, 4, 9, 8], 4, 0.5),
        ([1, 2, 3], [3, 1], 3, 2 / 3),
        ([1, 2], [5, 6], 3, 0.0),
        ([1, 2, 2], [2, 1, 3], 2, 1.0),
    ],
)
def test_recall_at_k_values(exact, approx, k, expected):
    assert recall_at_k(exact, approx, k) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("exact", "approx", "k"),
    [
        ([1, 2], [2, 1], 0),
        ([1, 2], [2, 1], -2),
        ([1, 2], [2, 1], True),
        ([1, 2], [2, 1], 2.0),
        ([1, 2], [2, 1], "3"),
        ([1, 2, 3], [3, 3, 1], 2),
        ([1, 1, 2], [2, 1], 2),
    ],
)
def test_recall_at_k_rejects_invalid(exact, approx, k):
    with pytest.raises((TypeError, ValueError)):
        recall_at_k(exact, approx, k)


@pytest.mark.parametrize(
    "plan",
    [
        {"Node Type": "Index Scan", "Index Name": "spike_chunks_embedding_idx"},
        {"Node Type": "Index Only Scan", "Index Name": "CHUNKS_HNSW_IDX"},
        [{"Plan": {"Node Type": "Index Scan", "Index Name": "hnsw_embedding_idx"}}],
    ],
)
def test_plan_uses_hnsw_true(plan):
    assert plan_uses_hnsw(plan) is True


@pytest.mark.parametrize(
    "plan",
    [
        {"Node Type": "Seq Scan", "Relation Name": "spike_chunks"},
        {"Node Type": "Index Scan", "Index Name": "spike_chunks_pkey"},
        {"Node Type": "Bitmap Index Scan", "Index Name": "embedding_bm_idx"},
    ],
)
def test_plan_uses_hnsw_false(plan):
    assert plan_uses_hnsw(plan) is False


def test_plan_uses_hnsw_recurses_into_nested_plans():
    def nested(index_name):
        scan = {"Node Type": "Index Only Scan", "Index Name": index_name}
        loop = {"Node Type": "Nested Loop", "Plans": [scan]}
        return [{"Plan": {"Node Type": "Limit", "Plans": [loop]}}]

    assert plan_uses_hnsw(nested("chunks_hnsw_idx")) is True
    assert plan_uses_hnsw(nested("EMBEDDING_probe_idx")) is True
    assert plan_uses_hnsw(nested("spike_chunks_pkey")) is False


@pytest.mark.parametrize(("force_index", "ef_search"), [(False, 100), (True, 64)])
def test_ann_search_settings_query_and_ids(force_index, ef_search):
    conn = FakeConnection(rows=[(4, 0.1), (2, 0.2), (9, 0.3)])
    vec = [0.25, 0.75]
    tenant = "tenant-4101"
    assert ann_search(conn, vec, tenant, 5, force_index, ef_search) == [4, 2, 9]
    cur = conn.cursors[0]
    assert cur.closed and conn.commits == 0 and len(conn.cursors) == 1
    assert not conn.closed
    joined = "\n".join(cur.executed).lower()
    assert "set_config('app.tenant_id'" in joined
    assert "set_config('hnsw.ef_search'" in joined
    assert "hnsw.ef_search" in joined and "hnsw.iterative_scan" in joined
    assert "strict_order" in joined
    seq = [sql for sql in cur.executed if "enable_seqscan" in sql.lower()]
    assert len(seq) == 1
    assert ("off" if force_index else "on") in seq[0].lower()
    assert "on" in _setting(cur, "enable_indexscan")
    assert "on" in _setting(cur, "enable_bitmapscan")
    flat = _flat_params(cur)
    assert tenant in flat and 5 in flat and "[0.25,0.75]" in flat
    assert flat.count("[0.25,0.75]") == 2
    assert "[0.25,0.75]" not in joined
    assert ef_search in flat or str(ef_search) in flat
    main = max(cur.executed, key=len).lower()
    assert "materialized" in main
    assert main.index("spike_chunks") < main.index("limit") < main.index("kb_graph_nodes")
    assert "<=>" in main and "'chunk'" in main and main.count("order by") >= 2
    assert "idx" in main[main.rindex("order by") :]


def test_exact_search_settings_query_and_ids():
    conn = FakeConnection(rows=[(8, 0.0), (5, 0.4)])
    assert exact_search(conn, [0, 1], "tenant-77", 2) == [8, 5]
    cur = conn.cursors[0]
    assert "off" in _setting(cur, "enable_indexscan")
    assert "off" in _setting(cur, "enable_bitmapscan")
    assert "on" in _setting(cur, "enable_seqscan")
    main = max(cur.executed, key=len).lower()
    assert "spike_chunks" in main and "<=>" in main and "kb_graph_nodes" not in main
    joined = "\n".join(cur.executed).lower()
    assert "set_config('app.tenant_id'" in joined
    flat = _flat_params(cur)
    assert "tenant-77" in flat and 2 in flat and "[0.0,1.0]" in flat
    assert cur.closed and conn.commits == 0 and len(conn.cursors) == 1


def test_explain_ann_uses_the_measured_candidate_query():
    plan = [{"Plan": {"Node Type": "Index Scan", "Index Name": "embedding_idx"}}]
    conn = FakeConnection(rows=[(plan,)])
    assert explain_ann(conn, [1, 0], "aircargo", 20, True, 100) == plan
    cur = conn.cursors[0]
    main = max(cur.executed, key=len).lower()
    assert main.startswith("explain (analyze, buffers, format json)")
    assert "materialized" in main and main.index("limit") < main.index("kb_graph_nodes")
    assert cur.closed and conn.commits == 0
