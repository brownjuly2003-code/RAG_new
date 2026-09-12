"""GR-2 graph construction over extracted entities, without model calls."""

from dataclasses import replace

import pytest

from ingestion.entity_graph import add_entity_graph
from ingestion.structure_graph_projection import structure_graph_digest
from tests.test_structure_graph_persistence import _graph


def _input():
    graph = _graph()
    chunks = sorted((n for n in graph.nodes if n.kind == "chunk"),
                    key=lambda n: n.attributes["chunk_index"])
    entities = {chunks[0].node_id: ["AWB", "booking", "document"],
                chunks[1].node_id: ["air waybill", "бронирование", "local"],
                chunks[2].node_id: ["авианакладная", "local"]}
    return graph, chunks, entities


def test_cross_document_entities_and_weighted_cooccurrence():
    graph, chunks, entities = _input()
    result = add_entity_graph(graph, entities)
    nodes = {n.label: n for n in result.nodes if n.kind == "entity"}
    assert set(nodes) == {"awb", "booking"}
    assert nodes["awb"].attributes["document_count"] == 2
    mentions = [e for e in result.edges if e.kind == "mentions"]
    assert len(mentions) == 5
    assert {e.source_node_id for e in mentions} == {n.node_id for n in chunks}
    pairs = [e for e in result.edges if e.kind == "co_occurs"]
    assert len(pairs) == 2
    assert {e.attributes["weight"] for e in pairs} == {2}
    assert all(node in result.nodes for node in graph.nodes)
    assert all(edge in result.edges for edge in graph.edges)


def test_build_is_deterministic_and_does_not_mutate_input():
    graph, _, entities = _input()
    before = structure_graph_digest(graph)
    result = add_entity_graph(graph, entities)
    shuffled = {key: list(reversed(values)) for key, values in reversed(list(entities.items()))}
    assert structure_graph_digest(result) == structure_graph_digest(add_entity_graph(graph, shuffled))
    assert structure_graph_digest(graph) == before


def test_rejects_unknown_or_foreign_chunk_instead_of_silent_loss():
    graph, _, entities = _input()
    entities["foreign-chunk"] = ["awb"]
    with pytest.raises(ValueError, match="chunk"):
        add_entity_graph(graph, entities)


def test_rejects_mixed_tenant_graph():
    graph, _, entities = _input()
    graph = replace(graph, nodes=(replace(graph.nodes[0], tenant_id="other"), *graph.nodes[1:]))
    with pytest.raises(ValueError, match="tenant"):
        add_entity_graph(graph, entities)


def test_rejects_second_enrichment():
    graph, _, entities = _input()
    with pytest.raises(ValueError, match="already"):
        add_entity_graph(add_entity_graph(graph, entities), entities)


def test_entity_graph_persists_with_existing_tenant_repository():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from db.models import KbGraphEdge, KbGraphNode
    from ingestion.structure_graph_repository import StructuralGraphRepository

    graph, _, entities = _input()
    enriched = add_entity_graph(graph, entities)
    engine = create_engine("sqlite://")
    KbGraphNode.__table__.create(engine)
    KbGraphEdge.__table__.create(engine)
    with Session(engine) as session:
        repo = StructuralGraphRepository(session)
        repo.replace(enriched)
        loaded = repo.load(graph.tenant_id)
        assert loaded.builder_version == enriched.builder_version
        assert structure_graph_digest(loaded) == structure_graph_digest(enriched)
        assert {n.node_id: n for n in loaded.nodes} == {n.node_id: n for n in enriched.nodes}
        assert {e.edge_id: e for e in loaded.edges} == {e.edge_id: e for e in enriched.edges}
