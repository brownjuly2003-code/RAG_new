"""NetworkX-only evidence tests for structural graph projections."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import networkx as nx
import pytest

pytest.importorskip("langchain_core")

from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from scripts.pgvector_graph_evidence import (
    GraphParity,
    canonical_projection,
    graph_parity,
)

TENANT_ID = "tenant-7"
H1 = "Installation"


def _chunk(chunk_index: int, categories: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        page_content=f"# {H1}\n\nParagraph {chunk_index} of the guide.",
        metadata={
            "source": "guide.md",
            "chunk_index": chunk_index,
            "categories": categories,
            "h1": H1,
        },
    )


def _projection() -> nx.MultiDiGraph:
    structural = build_structural_graph(
        [_chunk(0, ["onboarding", "setup"]), _chunk(1, ["setup"])],
        tenant_id=TENANT_ID,
    )
    return project_structure_graph(structural)


def _pairs_of_kind(graph: nx.MultiDiGraph, kind: str) -> set[tuple[Any, Any]]:
    return {
        (source, target)
        for source, target, data in graph.edges(data=True)
        if data.get("kind") == kind
    }


def test_projection_keeps_parallel_next_and_same_section_edges() -> None:
    projection = _projection()

    assert isinstance(projection, nx.MultiDiGraph)
    assert projection.graph["tenant_id"] == TENANT_ID
    assert projection.graph["builder_version"]
    for _, data in projection.nodes(data=True):
        assert data["tenant_id"] == TENANT_ID
        assert {"kind", "natural_key", "label", "attributes"} <= set(data)

    parallel_pairs = _pairs_of_kind(projection, "next") & _pairs_of_kind(projection, "same_section")
    assert parallel_pairs
    source, target = min(parallel_pairs, key=lambda pair: (str(pair[0]), str(pair[1])))
    parallel = projection.get_edge_data(source, target)
    kinds = {data["kind"] for data in parallel.values()}
    assert {"next", "same_section"} <= kinds
    for key, data in parallel.items():
        assert data["edge_id"] == key
        assert data["tenant_id"] == TENANT_ID
        assert isinstance(data["attributes"], dict)


def test_canonical_projection_is_deterministic_json() -> None:
    projection = _projection()

    first = canonical_projection(projection)
    second = canonical_projection(projection)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert len(first["nodes"]) == projection.number_of_nodes()
    assert len(first["edges"]) == projection.number_of_edges()


def test_canonical_projection_ignores_insertion_order() -> None:
    projection = _projection()

    reordered = nx.MultiDiGraph()
    reordered.graph.update(copy.deepcopy(projection.graph))
    for node in reversed(list(projection.nodes)):
        reordered.add_node(node, **copy.deepcopy(projection.nodes[node]))
    for source, target, key in reversed(list(projection.edges(keys=True))):
        reordered.add_edge(
            source,
            target,
            key=key,
            **copy.deepcopy(projection.get_edge_data(source, target, key)),
        )

    assert canonical_projection(reordered) == canonical_projection(projection)
    assert graph_parity(projection, reordered).identical


def test_graph_parity_identical_for_equal_projections() -> None:
    projection = _projection()

    parity = graph_parity(projection, copy.deepcopy(projection))

    assert isinstance(parity, GraphParity)
    assert parity.identical
    assert parity.node_count == projection.number_of_nodes()
    assert parity.edge_count == projection.number_of_edges()
    assert parity.node_mismatch_count == 0
    assert parity.edge_mismatch_count == 0
    assert parity.node_mismatch_ids == ()
    assert parity.edge_mismatch_ids == ()
    with pytest.raises(AttributeError):
        parity.identical = False  # type: ignore[misc]


def test_graph_parity_reports_single_node_and_edge_mismatch() -> None:
    projection = _projection()
    mutated = copy.deepcopy(projection)

    node_id = min(mutated.nodes, key=str)
    mutated.nodes[node_id]["attributes"]["evidence_probe"] = "mutated"

    source, target, key = max(
        mutated.edges(keys=True),
        key=lambda edge: (str(edge[0]), str(edge[1]), str(edge[2])),
    )
    mutated.remove_edge(source, target, key=key)

    parity = graph_parity(projection, mutated)

    assert not parity.identical
    assert parity.node_count == projection.number_of_nodes()
    assert parity.edge_count == projection.number_of_edges()
    assert parity.node_mismatch_count == 1
    assert parity.edge_mismatch_count == 1
    assert parity.node_mismatch_ids == (str(node_id),)
    assert parity.edge_mismatch_ids == (f"{source}->{target}:{key}",)


def test_graph_parity_flags_graph_metadata_drift_only() -> None:
    projection = _projection()
    drifted = copy.deepcopy(projection)
    drifted.graph["builder_version"] = "0.0.0-test"

    parity = graph_parity(projection, drifted)

    assert not parity.identical
    assert parity.node_mismatch_count == 0
    assert parity.edge_mismatch_count == 0
    assert parity.node_mismatch_ids == ()
    assert parity.edge_mismatch_ids == ()
