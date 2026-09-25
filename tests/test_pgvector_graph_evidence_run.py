"""Contract tests for scripts.pgvector_graph_evidence_run; red until production code exists."""

import copy
import hashlib
import json
from pathlib import Path

import networkx as nx
import pytest

from scripts import pgvector_graph_evidence_run as runner


def test_module_constants():
    assert runner.EXPECTED_CHUNKS == 5589
    assert runner.SCHEMA_VERSION == "d4-pgvector-graph-evidence-v1"
    assert runner.SOURCE_FILES == (
        "scripts/pgvector_graph_evidence_run.py",
        "scripts/pgvector_graph_evidence.py",
        "ingestion/structure_graph.py",
        "ingestion/structure_graph_repository.py",
        "ingestion/structure_graph_projection.py",
    )


def _chunk(page_content, metadata):
    return {"page_content": page_content, "metadata": metadata}


def _encode(obj):
    return json.dumps(obj).encode("utf-8")


def _doc(rows):
    return _encode({"chunks": rows})


def _two_chunks():
    return _doc([_chunk("one", {}), _chunk("two", {})])


def test_load_chunks_happy_path(tmp_path):
    document = {
        "chunks": [
            {
                "page_content": "Gráfo de evidência — nó ùnico",
                "metadata": {"page": 1, "labels": {"kind": "causa", "tags": ["a"]}},
            },
            {
                "page_content": "Résumé 日本語 ✓ segundo",
                "metadata": {"page": 2, "labels": {"kind": "efeito", "tags": ["b", "c"]}},
            },
        ]
    }
    payload = json.dumps(document, ensure_ascii=False).encode("utf-8")
    path = tmp_path / "chunks.json"
    path.write_bytes(payload)
    before = copy.deepcopy(document)

    chunks, digest = runner._load_chunks(path, 2)

    assert digest == hashlib.sha256(payload).hexdigest()
    rows = document["chunks"]
    assert [c.page_content for c in chunks] == [r["page_content"] for r in rows]
    assert [c.metadata for c in chunks] == [r["metadata"] for r in rows]

    chunks[0].metadata["labels"]["tags"].append("mutated")
    chunks[1].metadata["page"] = -1
    assert document == before


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param(_two_chunks(), True, id="bool-expected-count"),
        pytest.param(_two_chunks(), 0, id="zero-expected-count"),
        pytest.param(_doc([_chunk("one", {})]), 2, id="wrong-count"),
        pytest.param(b"[]", 1, id="non-object-top-level"),
        pytest.param(_doc([]), 1, id="empty-chunks"),
        pytest.param(_doc([42]), 1, id="non-object-row"),
        pytest.param(_doc([_chunk(7, {})]), 1, id="non-string-page-content"),
        pytest.param(_doc([_chunk("", {})]), 1, id="empty-page-content"),
        pytest.param(_doc([_chunk("x", ["meta"])]), 1, id="non-mapping-metadata"),
    ],
)
def test_load_chunks_rejects_invalid_input(tmp_path, payload, expected):
    path = tmp_path / "chunks.json"
    path.write_bytes(payload)
    with pytest.raises((TypeError, ValueError)):
        runner._load_chunks(path, expected)


def _base_graph():
    graph = nx.MultiDiGraph()
    graph.add_node("left", role="source")
    graph.add_node("hub", role="center")
    graph.add_node("right", role="sink")
    graph.add_node("spare", role="isolated")
    graph.add_edge("left", "hub", kind="causa")
    graph.add_edge("hub", "right", kind="efeito")
    return graph


def _reversed_graph():
    graph = nx.MultiDiGraph()
    graph.add_node("spare", role="isolated")
    graph.add_node("right", role="sink")
    graph.add_node("hub", role="center")
    graph.add_node("left", role="source")
    graph.add_edge("hub", "right", kind="efeito")
    graph.add_edge("left", "hub", kind="causa")
    return graph


def test_traversal_mismatch_count_ignores_insertion_order():
    assert runner._traversal_mismatch_count(_base_graph(), _reversed_graph()) == 0


def _rekey_left_edge(graph):
    data = graph.get_edge_data("left", "hub")[0]
    graph.remove_edge("left", "hub")
    graph.add_edge("left", "hub", key=7, **data)


@pytest.mark.parametrize(
    "drift",
    [
        pytest.param(lambda g: g["left"]["hub"][0].update(kind="outro"), id="edge-kind-changed"),
        pytest.param(_rekey_left_edge, id="edge-key-replaced"),
        pytest.param(lambda g: g.remove_edge("left", "hub"), id="incoming-edge-removed"),
        pytest.param(lambda g: g.remove_edge("hub", "right"), id="outgoing-edge-removed"),
        pytest.param(lambda g: g.remove_node("spare"), id="node-removed"),
    ],
)
def test_traversal_mismatch_count_positive_and_stable_for_drift(drift):
    right = _base_graph()
    drift(right)
    count = runner._traversal_mismatch_count(_base_graph(), right)
    assert isinstance(count, int) and not isinstance(count, bool)
    assert count > 0
    assert runner._traversal_mismatch_count(_base_graph(), right) == count


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("postgresql://postgres@localhost:55432/graph", id="localhost"),
        pytest.param("postgresql://postgres@127.0.0.1:55432/graph", id="ipv4"),
        pytest.param("postgresql+psycopg2://postgres@localhost:55432/graph", id="psycopg2"),
    ],
)
def test_validate_local_database_url_accepts_and_returns_input(url):
    assert runner._validate_local_database_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(None, id="absent"),
        pytest.param("", id="empty"),
        pytest.param("mysql://postgres@localhost:55432/graph", id="wrong-driver"),
        pytest.param("postgresql:///graph", id="missing-host"),
        pytest.param("postgresql://postgres@example.com:55432/graph", id="wrong-host"),
        pytest.param("postgresql://postgres@localhost/graph", id="missing-port"),
        pytest.param("postgresql://postgres@localhost:5432/graph", id="wrong-port"),
    ],
)
def test_validate_local_database_url_rejects(url):
    with pytest.raises((TypeError, ValueError)):
        runner._validate_local_database_url(url)


def test_validate_local_database_url_redacts_password():
    url = "postgresql://postgres:topsecret@example.com:5432/graph"
    with pytest.raises((TypeError, ValueError)) as excinfo:
        runner._validate_local_database_url(url)
    assert "topsecret" not in str(excinfo.value)


def test_write_report_unicode_strict_json(tmp_path):
    report = {"título": "café — ✓", "rows": [1, {"k": None}]}
    path = tmp_path / "report.json"
    runner._write_report(path, report)
    text = path.read_bytes().decode("utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\r" not in text
    assert "café" in text
    assert json.loads(text) == report


def test_write_report_refuses_existing_path(tmp_path):
    path = tmp_path / "report.json"
    original = b'{"old": true}\n'
    path.write_bytes(original)
    with pytest.raises(FileExistsError):
        runner._write_report(path, {"novo": 1})
    assert path.read_bytes() == original


def test_write_report_rejects_nan_and_writes_nothing(tmp_path):
    path = tmp_path / "report.json"
    with pytest.raises(ValueError):
        runner._write_report(path, {"v": float("nan")})
    assert not path.exists()


_CLI_DSN = "postgresql://postgres:topsecret@localhost:55432/graph"
_CLI_CODE_BASE = "0123456789abcdef0123456789abcdef01234567"


def _cli_argv(tmp_path):
    chunks = tmp_path / "chunks.json"
    chunks.write_bytes(_two_chunks())
    return ["--chunks", str(chunks), "--output", str(tmp_path / "report.json")]


def _cli_run_acceptance(recorded, evidence_class="measured"):
    def _accept(**kwargs):
        recorded.append(kwargs)
        return {"evidence_class": evidence_class}

    return _accept


def test_main_measured_forwards_arguments_without_leaking_password(tmp_path, capsys, monkeypatch):
    recorded = []
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", _CLI_DSN)
    monkeypatch.setattr(runner, "_git_code_base", lambda: _CLI_CODE_BASE)
    monkeypatch.setattr(runner, "run_acceptance", _cli_run_acceptance(recorded))

    assert runner.main(_cli_argv(tmp_path)) == 0

    (forwarded,) = recorded
    assert set(forwarded) == {"chunks_path", "output_path", "database_url", "code_base"}
    assert Path(forwarded["chunks_path"]) == tmp_path / "chunks.json"
    assert Path(forwarded["output_path"]) == tmp_path / "report.json"
    assert forwarded["database_url"] == _CLI_DSN
    assert forwarded["code_base"] == _CLI_CODE_BASE
    captured = capsys.readouterr()
    assert "DONE" in captured.out
    assert "topsecret" not in captured.out + captured.err


def test_main_not_evidence_returns_nonzero_without_done(tmp_path, capsys, monkeypatch):
    recorded = []
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", _CLI_DSN)
    monkeypatch.setattr(runner, "_git_code_base", lambda: _CLI_CODE_BASE)
    monkeypatch.setattr(runner, "run_acceptance", _cli_run_acceptance(recorded, "not_evidence"))

    assert runner.main(_cli_argv(tmp_path)) != 0
    assert "DONE" not in capsys.readouterr().out


def test_main_without_database_url_fails_closed(tmp_path, monkeypatch):
    recorded = []
    monkeypatch.delenv("RESOLUTION_ADMIN_DATABASE_URL", raising=False)
    monkeypatch.setattr(runner, "_git_code_base", lambda: _CLI_CODE_BASE)
    monkeypatch.setattr(runner, "run_acceptance", _cli_run_acceptance(recorded))

    with pytest.raises((TypeError, ValueError)):
        runner.main(_cli_argv(tmp_path))

    assert recorded == []


def test_main_refuses_existing_output_file(tmp_path, monkeypatch):
    recorded = []
    monkeypatch.setenv("RESOLUTION_ADMIN_DATABASE_URL", _CLI_DSN)
    monkeypatch.setattr(runner, "_git_code_base", lambda: _CLI_CODE_BASE)
    monkeypatch.setattr(runner, "run_acceptance", _cli_run_acceptance(recorded))

    argv = _cli_argv(tmp_path)
    original = b'{"old": true}\n'
    output = tmp_path / "report.json"
    output.write_bytes(original)

    with pytest.raises(FileExistsError):
        runner.main(argv)

    assert recorded == []
    assert output.read_bytes() == original
