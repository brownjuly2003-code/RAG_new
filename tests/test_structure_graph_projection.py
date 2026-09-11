"""GR-1 manifest provenance and rebuildable NetworkX projection."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import networkx as nx
import pytest

from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import (
    build_structure_graph_manifest,
    project_structure_graph,
)

CORPUS_SHA256 = "a" * 64


def _graph():
    return build_structural_graph(
        [
            SimpleNamespace(
                page_content="First half",
                metadata={
                    "source": "guide.md",
                    "chunk_index": 0,
                    "categories": ["shipping"],
                    "h1": "Guide",
                },
            ),
            SimpleNamespace(
                page_content="Second half",
                metadata={
                    "source": "guide.md",
                    "chunk_index": 1,
                    "categories": ["shipping"],
                    "h1": "Guide",
                },
            ),
        ],
        tenant_id="acme",
    )


def test_manifest_pins_graph_provenance_counts_and_digest() -> None:
    graph = _graph()

    manifest = build_structure_graph_manifest(
        graph,
        corpus_sha256=CORPUS_SHA256,
        extraction_prompt_version=None,
        extraction_model_digest=None,
    )

    assert manifest.schema_version == 1
    assert manifest.tenant_id == "acme"
    assert manifest.corpus_sha256 == CORPUS_SHA256
    assert manifest.builder_version == "gr1-structural-v1"
    assert manifest.extraction_prompt_version is None
    assert manifest.extraction_model_digest is None
    assert manifest.node_counts == {
        "category": 1,
        "chunk": 2,
        "document": 1,
        "section": 1,
    }
    assert manifest.edge_counts == {
        "category": 1,
        "contains": 3,
        "next": 1,
        "same_section": 1,
    }
    assert manifest.unresolved_cross_ref_count == 0
    assert len(manifest.graph_sha256) == 64
    assert manifest == build_structure_graph_manifest(
        graph,
        corpus_sha256=CORPUS_SHA256,
    )

    changed_node = replace(graph.nodes[0], label="changed")
    changed_graph = replace(graph, nodes=(changed_node, *graph.nodes[1:]))
    assert build_structure_graph_manifest(
        changed_graph,
        corpus_sha256=CORPUS_SHA256,
    ).graph_sha256 != manifest.graph_sha256


def test_projection_preserves_parallel_edge_kinds_and_metadata() -> None:
    graph = _graph()

    projection = project_structure_graph(graph)

    assert isinstance(projection, nx.MultiDiGraph)
    assert projection.graph == {
        "tenant_id": "acme",
        "builder_version": "gr1-structural-v1",
    }
    assert projection.number_of_nodes() == len(graph.nodes)
    assert projection.number_of_edges() == len(graph.edges)
    assert {data["kind"] for _, _, data in projection.edges(data=True)} == {
        edge.kind for edge in graph.edges
    }

    chunk = next(node for node in graph.nodes if node.kind == "chunk")
    assert projection.nodes[chunk.node_id] == {
        "tenant_id": "acme",
        "kind": "chunk",
        "natural_key": chunk.natural_key,
        "label": chunk.label,
        "attributes": chunk.attributes,
    }

    parallel_pairs = {
        (source, target)
        for source, target in projection.edges()
        if projection.number_of_edges(source, target) > 1
    }
    assert parallel_pairs
    source, target = next(iter(parallel_pairs))
    assert {
        data["kind"] for data in projection.get_edge_data(source, target).values()
    } == {"next", "same_section"}


def test_projection_rejects_an_edge_with_a_missing_endpoint() -> None:
    graph = _graph()
    broken_edge = replace(graph.edges[0], target_node_id=str(uuid4()))

    with pytest.raises(ValueError, match="missing node"):
        project_structure_graph(replace(graph, edges=(broken_edge, *graph.edges[1:])))
