"""Offline tests for the Phase D.2 ANN outlier diagnostic driver."""

import json

import pytest

from scripts import pgvector_ann_outlier_run as mod

CASE_ID = "aircargo-harassment-investigation-timeline"
SCHEMA = "d2-pgvector-ann-outlier-v1"
GRID = (40, 100, 200, 400, 800, 1000)
LABELS = ["exact"] + [f"ann-{ef}" for ef in GRID]
SOURCES = {
    "pgvector_ann_outlier_run.py",
    "pgvector_ann_outlier.py",
    "pgvector_ann_run.py",
    "pgvector_ann.py",
    "pgvector_spike_db.py",
}
INDEX_DEFINITION = (
    "CREATE INDEX spike_chunks_embedding_idx ON public.spike_chunks "
    "USING hnsw (embedding vector_cosine_ops)"
)


def _inputs(case_ids):
    cases = [{"case_id": case_id, "query": f"query-{case_id}"} for case_id in case_ids]
    return {
        "texts": ["chunk"],
        "vectors": [[0.1, 0.2]],
        "queries": [[0.5 + index, 0.25] for index in range(len(case_ids))],
        "cases": cases,
        "input_sha256": {"chunks.json": "a" * 64},
    }


def _rows(ids):
    return [[chunk_id, rank / 100.0] for rank, chunk_id in enumerate(ids)]


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return list(self.connection.rows)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.commits = 0
        self.closed = False
        self.cursors = []

    def cursor(self):
        cursor = _Cursor(self)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_constants():
    assert (mod.CASE_ID, mod.REPETITIONS, mod.SCHEMA_VERSION) == (CASE_ID, 3, SCHEMA)


def test_select_case_unique_missing_duplicate():
    index, case, vector = mod._select_case(_inputs(["other", CASE_ID]))
    assert index == 1
    assert case == {"case_id": CASE_ID, "query": f"query-{CASE_ID}"}
    assert vector == [1.5, 0.25]
    with pytest.raises(RuntimeError):
        mod._select_case(_inputs(["a", "b"]))
    with pytest.raises(RuntimeError):
        mod._select_case(_inputs([CASE_ID, CASE_ID]))


def _searches(calls, unstable=()):
    counts = {}

    def exact(_connection, _vector, _tenant, _limit):
        calls.append(("exact", None))
        return _rows(range(20))

    def ann(_connection, _vector, _tenant, _limit, ef_search):
        calls.append(("ann", ef_search))
        counts[ef_search] = counts.get(ef_search, 0) + 1
        ids = list(range(1, 21))
        if ef_search in unstable and counts[ef_search] > 1:
            ids = ids[1:] + [99]
        return _rows(ids)

    return exact, ann


def _clock(monkeypatch):
    ticks = iter(1.0 + 0.5 * index for index in range(500))
    monkeypatch.setattr(mod.time, "perf_counter", lambda: next(ticks))


def test_run_repetitions_order_commits_and_stability(monkeypatch):
    connection, calls = _Connection(), []
    exact, ann = _searches(calls)
    monkeypatch.setattr(mod, "ranked_exact_search", exact)
    monkeypatch.setattr(mod, "ranked_ann_search", ann)
    _clock(monkeypatch)

    runs = mod._run_repetitions(connection, [0.5, 0.25])

    ascending = [("exact", None)] + [("ann", ef) for ef in GRID]
    descending = [("ann", ef) for ef in reversed(GRID)] + [("exact", None)]
    assert calls == ascending + descending + ascending
    assert connection.commits == 21
    data = json.loads(json.dumps(runs))
    assert [run["order"] for run in data] == [LABELS, LABELS[::-1], LABELS]
    for run in data:
        assert set(run["rankings"]) == set(LABELS)
        for label in LABELS:
            ranking = run["rankings"][label]
            assert len(ranking) == 20 and len({row[0] for row in ranking}) == 20
            assert 0.0 < run["timings_ms"][label] < 1000.0
    for label in LABELS:
        assert data[1]["rankings"][label] == data[0]["rankings"][label]
        assert data[2]["rankings"][label] == data[0]["rankings"][label]


def test_run_repetitions_rejects_unstable_arm(monkeypatch):
    connection, calls = _Connection(), []
    exact, ann = _searches(calls, unstable=(200,))
    monkeypatch.setattr(mod, "ranked_exact_search", exact)
    monkeypatch.setattr(mod, "ranked_ann_search", ann)
    _clock(monkeypatch)
    with pytest.raises(RuntimeError, match="ann-200"):
        mod._run_repetitions(connection, [0.5])


def _summarized(hits):
    rankings = {"exact": _rows(range(20))}
    for ef_search, hit_count in hits.items():
        ids = list(range(hit_count)) + list(range(100, 120 - hit_count))
        rankings[f"ann-{ef_search}"] = _rows(ids)
    run = {
        "repetition": 1,
        "order": list(rankings),
        "timings_ms": {label: 1.0 for label in rankings},
        "rankings": rankings,
    }
    return mod._summarize([run])


def test_summarize_recall_monotonic_and_diagnosis():
    result = _summarized({40: 5, 100: 10, 200: 15, 400: 20, 800: 20, 1000: 20})
    assert result["exact"] == _rows(range(20))
    rows = {row["ef_search"]: row for row in result["ef_rows"]}
    assert set(rows) == set(GRID)
    assert rows[40]["recall_at_20"] == pytest.approx(0.25)
    assert rows[40]["recovered_exact_ids"] == list(range(5))
    assert rows[40]["missed_exact_ids"] == list(range(5, 20))
    assert rows[400]["missed_exact_ids"] == []
    assert result["summary"] == {
        "first_full_recall_ef_search": 400,
        "monotonic_nondecreasing_recall": True,
        "diagnosis": "recovered_by_higher_ef_search",
    }
    nonmonotonic = _summarized({40: 10, 100: 4, 200: 20, 400: 20, 800: 20, 1000: 20})
    assert nonmonotonic["summary"]["monotonic_nondecreasing_recall"] is False
    assert nonmonotonic["summary"]["first_full_recall_ef_search"] == 200


def test_index_definition_requires_exactly_one_hnsw_index():
    connection = _Connection([(INDEX_DEFINITION,)])
    assert mod._index_definition(connection) == INDEX_DEFINITION
    assert connection.cursors[-1].closed
    with pytest.raises(RuntimeError):
        mod._index_definition(_Connection())
    with pytest.raises(RuntimeError):
        mod._index_definition(_Connection([(INDEX_DEFINITION,), (INDEX_DEFINITION,)]))


RUN = {
    "repetition": 1,
    "order": LABELS,
    "timings_ms": {label: 0.5 for label in LABELS},
    "rankings": {label: _rows(range(20)) for label in LABELS},
}
SUMMARY = {
    "exact": _rows(range(20)),
    "ef_rows": [
        {
            "ef_search": ef_search,
            "ranking": _rows(range(20)),
            "recall_at_20": 1.0,
            "recovered_exact_ids": list(range(20)),
            "missed_exact_ids": [],
        }
        for ef_search in GRID
    ],
    "summary": {
        "first_full_recall_ef_search": 40,
        "monotonic_nondecreasing_recall": True,
        "diagnosis": "already_full_at_baseline",
    },
}


def _argv(output):
    return [
        "--chunks",
        "chunks.json",
        "--vectors",
        "vectors.npz",
        "--queries",
        "queries.npy",
        "--database",
        "rag_spike_test",
        "--output",
        str(output),
        "--cases",
        "cases.jsonl",
    ]


def _patch_main(monkeypatch, connection):
    state = {"setup": 0, "verify": 0, "explain": 0}

    def setup(*_args, **_kwargs):
        state["setup"] += 1
        return connection

    def verify(*_args, **_kwargs):
        state["verify"] += 1
        return {"ok": True}, "PostgreSQL 16.9", "0.8.0"

    def explain(*_args, **_kwargs):
        state["explain"] += 1
        return [{"Plan": {"Node Type": "Index Scan"}}]

    monkeypatch.setenv("SPIKE_ADMIN_DSN", "postgresql://local-redacted")
    monkeypatch.setattr(mod, "_git_code_base", lambda: "d" * 40)
    monkeypatch.setattr(mod, "_load_inputs", lambda _args: _inputs([CASE_ID]))
    monkeypatch.setattr(mod, "_sha256", lambda _path: "f" * 64)
    monkeypatch.setattr(mod, "setup", setup)
    monkeypatch.setattr(mod, "_verify_rls", verify)
    monkeypatch.setattr(mod, "_index_definition", lambda _connection: INDEX_DEFINITION)
    monkeypatch.setattr(mod, "explain_ann", explain)
    monkeypatch.setattr(mod, "plan_uses_hnsw", lambda _plan: True)
    monkeypatch.setattr(mod, "_run_repetitions", lambda _connection, _vector: [RUN, RUN, RUN])
    monkeypatch.setattr(mod, "_summarize", lambda _runs: SUMMARY)
    monkeypatch.setattr(mod.importlib.metadata, "version", lambda package: f"test-{package}")
    return state


def test_main_writes_provenance_report(tmp_path, monkeypatch, capsys):
    output, connection = tmp_path / "report.json", _Connection()
    state = _patch_main(monkeypatch, connection)

    assert mod.main(_argv(output)) in (None, 0)

    raw = output.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    payload = json.loads(raw.decode("utf-8"))
    assert (payload["schema_version"], payload["code_base"]) == (SCHEMA, "d" * 40)
    assert (payload["database"], payload["case_id"], payload["case_index"]) == (
        "rag_spike_test",
        CASE_ID,
        0,
    )
    assert payload["query"] == f"query-{CASE_ID}"
    assert payload["input_sha256"] == {"chunks.json": "a" * 64}
    assert set(payload["source_sha256"]) == SOURCES
    assert payload["python"] and payload["postgres"] == "PostgreSQL 16.9"
    assert payload["pgvector"] == "0.8.0"
    assert set(payload["versions"]) == {"numpy", "psycopg2-binary"}
    assert payload["index_definition"] == INDEX_DEFINITION
    config = payload["config"]
    assert config["chunks"] == 5589 and config["cases"] == 115
    assert config["top_k"] == 20 and config["ef_search_values"] == list(GRID)
    assert config["baseline_ef_search"] == 100 and config["repetitions"] == 3
    assert config["distance"] == "cosine" and config["reranker"] is False
    assert config["embedding_action"] == "reused_without_reembedding"
    assert payload["rls"] == {"ok": True}
    assert payload["planner"]["baseline_uses_hnsw"] is True
    assert payload["exact"] == SUMMARY["exact"]
    assert payload["ef_rows"] == SUMMARY["ef_rows"]
    assert payload["summary"] == SUMMARY["summary"]
    assert len(payload["runs"]) == 3
    assert state == {"setup": 1, "verify": 1, "explain": 1}
    assert connection.closed and "DONE" in capsys.readouterr().out


def test_main_refuses_existing_output_before_setup(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("keep", encoding="utf-8")
    connection = _Connection()
    state = _patch_main(monkeypatch, connection)
    with pytest.raises(FileExistsError):
        mod.main(_argv(output))
    assert state["setup"] == 0
    assert output.read_text(encoding="utf-8") == "keep"
