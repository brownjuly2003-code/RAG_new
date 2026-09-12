from contextlib import nullcontext
from dataclasses import replace

import pytest

from ingestion.entity_graph import add_entity_graph
from ingestion.structure_graph import build_structural_graph
from vectordb._base_manager import Document


def fixture_graph():
    chunks = [Document(page_content=f"fact {i}", metadata={"source": f"{i}.md", "chunk_index": i})
              for i in range(2)]
    structural = build_structural_graph(chunks, tenant_id="acme")
    enriched = add_entity_graph(structural, {node.node_id: ["awb"] for node in structural.nodes
                                             if node.kind == "chunk"})
    return structural, enriched


@pytest.mark.parametrize("mismatch", [None, "tenant", "text", "missing"])
def test_only_matching_persisted_graph_is_loaded(monkeypatch, mismatch):
    from ingestion import entity_graph_loading, jobs, structure_graph_repository

    structural, stored = fixture_graph()
    if mismatch == "tenant":
        stored = replace(stored, tenant_id="other")
    elif mismatch == "text":
        stored = replace(stored, nodes=tuple(
            replace(node, attributes={**node.attributes, "content_sha256": "stale"})
            if node.kind == "chunk" else node for node in stored.nodes))
    elif mismatch == "missing":
        stored = replace(stored, nodes=tuple(node for node in stored.nodes if node.kind != "chunk"))
    calls = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture")
    monkeypatch.setattr(jobs, "sync_session", lambda: nullcontext(object()))
    monkeypatch.setattr(structure_graph_repository.StructuralGraphRepository, "load",
                        lambda self, tenant: calls.append(tenant) or stored)
    result = entity_graph_loading.load_matching_entity_graph(structural)
    assert result == (stored if mismatch is None else structural)
    assert calls == ["acme"]


def test_unconfigured_database_keeps_structural_graph(monkeypatch):
    from ingestion.entity_graph_loading import load_matching_entity_graph

    monkeypatch.delenv("DATABASE_URL", raising=False)
    structural, _ = fixture_graph()
    assert load_matching_entity_graph(structural) is structural


def test_database_failure_keeps_structural_graph_without_logging_credentials(monkeypatch, caplog):
    from sqlalchemy.exc import OperationalError

    from ingestion import entity_graph_loading, jobs

    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture")

    def unavailable():
        raise OperationalError("secret-password", {}, Exception("secret-password"))

    monkeypatch.setattr(jobs, "sync_session", unavailable)
    structural, _ = fixture_graph()
    assert entity_graph_loading.load_matching_entity_graph(structural) is structural
    assert "secret-password" not in caplog.text
    assert "unavailable" in caplog.text
