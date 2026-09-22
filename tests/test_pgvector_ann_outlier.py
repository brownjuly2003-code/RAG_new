"""Tests for the focused Phase D.2 ANN outlier diagnostic helpers."""

import re

import pytest

from scripts import pgvector_ann_outlier as mod

VECTOR = [0.1, 0.2, 0.3]


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executed = []
        self.closed = False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self): ...

    def rollback(self): ...


def _values(params):
    if not params:
        return ()
    if isinstance(params, dict):
        return tuple(params.values())
    return tuple(params)


def _setting(executed, name):
    text = ";\n".join(sql for sql, _ in executed).lower()
    match = re.search(rf"{re.escape(name)}[^;]*?(?:=|to)\s*['\"]?(\w+)", text)
    assert match is not None, name
    raw = match.group(1)
    return {"true": "on", "1": "on", "false": "off", "0": "off"}.get(raw, raw)


def _main(executed):
    hits = [(sql, params) for sql, params in executed if "<=>" in sql]
    assert len(hits) == 1
    return hits[0]


def _diag_rows(recalls):
    return [
        {"ef_search": ef, "recall_at_20": recall}
        for ef, recall in zip(mod.EF_SEARCH_VALUES, recalls, strict=True)
    ]


def test_constants_and_valid_grid():
    assert mod.TOP_K == 20
    assert mod.EF_SEARCH_VALUES == (40, 100, 200, 400, 800, 1000)
    assert mod.BASELINE_EF_SEARCH == 100
    validated = mod.validate_ef_search_values(list(mod.EF_SEARCH_VALUES))
    assert isinstance(validated, tuple)
    assert validated == mod.EF_SEARCH_VALUES


@pytest.mark.parametrize(
    "values",
    [
        (),
        (40, 40, 100, 200, 400, 800),
        (1000, 800, 400, 200, 100, 40),
        (40, 200, 400, 800, 1000),
        (0, 100, 200, 400, 800, 1000),
        (40, True, 200, 400, 800, 1000),
        (40, 100.0, 200, 400, 800, 1000),
    ],
)
def test_invalid_grids_rejected(values):
    with pytest.raises((TypeError, ValueError)):
        mod.validate_ef_search_values(values)


def test_diagnosis_labels_boundaries():
    assert (
        mod.diagnosis_label(_diag_rows([0.4, 1.0, 1.0, 1.0, 1.0, 1.0]))
        == "already_full_at_baseline"
    )
    assert (
        mod.diagnosis_label(_diag_rows([0.4, 0.9, 1.0, 1.0, 1.0, 1.0]))
        == "recovered_by_higher_ef_search"
    )
    assert (
        mod.diagnosis_label(_diag_rows([0.3, 0.6, 0.7, 0.8, 0.9, 0.99]))
        == "not_recovered_at_max_ef_search"
    )


@pytest.mark.parametrize("recall", [-0.1, 1.5, float("nan"), True])
def test_diagnosis_invalid_recall(recall):
    rows = _diag_rows([0.5, recall, 1.0, 1.0, 1.0, 1.0])
    with pytest.raises((TypeError, ValueError)):
        mod.diagnosis_label(rows)


def test_diagnosis_requires_exact_grid_and_ef_key():
    rows = _diag_rows([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    del rows[3]["ef_search"]
    with pytest.raises((KeyError, TypeError, ValueError)):
        mod.diagnosis_label(rows)
    shifted = [{"ef_search": ef, "recall_at_20": 0.5} for ef in (40, 100, 300, 400, 800, 1000)]
    with pytest.raises((TypeError, ValueError)):
        mod.diagnosis_label(shifted)


def test_exact_search_settings_sql_params_and_result():
    cur = FakeCursor([(7, 0.12), (3, 0.25), (5, 0.31)])
    result = mod.ranked_exact_search(FakeConnection(cur), VECTOR, "tenant-a", limit=3)
    assert result == [(7, 0.12), (3, 0.25), (5, 0.31)]
    assert _setting(cur.executed, "enable_indexscan") == "off"
    assert _setting(cur.executed, "enable_bitmapscan") == "off"
    assert _setting(cur.executed, "enable_seqscan") == "on"
    sql, params = _main(cur.executed)
    assert "spike_chunks" in sql and "kb_graph_nodes" not in sql
    assert "ORDER BY" in sql.upper() and "LIMIT" in sql.upper()
    assert "tenant-a" in _values(params) and 3 in _values(params)
    assert "tenant-a" not in sql
    assert cur.closed


def test_ann_search_settings_sql_params_and_result():
    cur = FakeCursor([(11, 0.05), (2, 0.4), (9, 0.77)])
    result = mod.ranked_ann_search(FakeConnection(cur), VECTOR, "tenant-b", limit=3, ef_search=200)
    assert result == [(11, 0.05), (2, 0.4), (9, 0.77)]
    assert _setting(cur.executed, "enable_indexscan") == "on"
    assert _setting(cur.executed, "enable_bitmapscan") == "on"
    assert _setting(cur.executed, "enable_seqscan") == "off"
    assert _setting(cur.executed, "hnsw.iterative_scan") == "strict_order"
    ef_params = [params for sql, params in cur.executed if "hnsw.ef_search" in sql]
    assert ef_params
    assert any(200 in _values(params) or "200" in _values(params) for params in ef_params)
    sql, params = _main(cur.executed)
    assert sql.index("spike_chunks") < sql.index("kb_graph_nodes")
    assert "kind" in sql.lower()
    assert "ORDER BY" in sql.upper() and "LIMIT" in sql.upper()
    assert "tenant-b" in _values(params) and 3 in _values(params)
    assert "tenant-b" not in sql
    assert _values(params).count("[0.1,0.2,0.3]") == 2
    assert cur.closed


@pytest.mark.parametrize(
    "rows",
    [
        [(1, 0.1), (1, 0.2)],
        [(1, 0.2), (2, 0.1)],
        [(1, float("nan"))],
        [(1, 0.1, 0.2)],
        [(1, 0.1), (2, "x")],
    ],
)
def test_ranked_rejects_bad_rows(rows):
    with pytest.raises((TypeError, ValueError)):
        mod.ranked_ann_search(FakeConnection(FakeCursor(rows)), VECTOR, "t")
    with pytest.raises((TypeError, ValueError)):
        mod.ranked_exact_search(FakeConnection(FakeCursor(rows)), VECTOR, "t")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"vector": (0.1, 0.2), "tenant": "t"},
        {"vector": "abc", "tenant": "t"},
        {"vector": [0.1, True], "tenant": "t"},
        {"vector": [0.1, "x"], "tenant": "t"},
        {"vector": [0.1, float("nan")], "tenant": "t"},
        {"vector": VECTOR, "tenant": 7},
        {"vector": VECTOR, "tenant": "t", "limit": 0},
        {"vector": VECTOR, "tenant": "t", "limit": -2},
        {"vector": VECTOR, "tenant": "t", "limit": True},
    ],
)
def test_exact_rejects_invalid_inputs(kwargs):
    with pytest.raises((TypeError, ValueError)):
        mod.ranked_exact_search(FakeConnection(FakeCursor([])), **kwargs)


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"ef_search": True}, {"ef_search": -100}])
def test_ann_rejects_invalid_limit_and_ef(kwargs):
    with pytest.raises((TypeError, ValueError)):
        mod.ranked_ann_search(FakeConnection(FakeCursor([])), VECTOR, "t", **kwargs)
