"""Provenance manifest and rebuildable NetworkX structural-graph projection."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import networkx as nx

from ingestion.structure_graph import StructuralGraph

STRUCTURE_GRAPH_MANIFEST_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class StructuralGraphManifest:
    """Provenance and bounded inventory for one tenant graph build."""

    schema_version: int
    tenant_id: str
    corpus_sha256: str
    builder_version: str
    extraction_prompt_version: str | None
    extraction_model_digest: str | None
    graph_sha256: str
    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    unresolved_cross_ref_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "corpus_sha256": self.corpus_sha256,
            "builder_version": self.builder_version,
            "extraction_prompt_version": self.extraction_prompt_version,
            "extraction_model_digest": self.extraction_model_digest,
            "graph_sha256": self.graph_sha256,
            "node_counts": dict(self.node_counts),
            "edge_counts": dict(self.edge_counts),
            "unresolved_cross_ref_count": self.unresolved_cross_ref_count,
        }


def _validate_graph(graph: StructuralGraph) -> None:
    node_ids: set[str] = set()
    for node in graph.nodes:
        if node.tenant_id != graph.tenant_id:
            raise ValueError("Structural graph contains a node from another tenant")
        if node.node_id in node_ids:
            raise ValueError("Structural graph contains a duplicate node id")
        node_ids.add(node.node_id)

    edge_ids: set[str] = set()
    for edge in graph.edges:
        if edge.tenant_id != graph.tenant_id:
            raise ValueError("Structural graph contains an edge from another tenant")
        if edge.edge_id in edge_ids:
            raise ValueError("Structural graph contains a duplicate edge id")
        edge_ids.add(edge.edge_id)
        if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
            raise ValueError("Structural graph edge references a missing node")


def _graph_payload(graph: StructuralGraph) -> dict[str, Any]:
    return {
        "tenant_id": graph.tenant_id,
        "builder_version": graph.builder_version,
        "nodes": [
            {
                "node_id": node.node_id,
                "tenant_id": node.tenant_id,
                "kind": node.kind,
                "natural_key": node.natural_key,
                "label": node.label,
                "attributes": node.attributes,
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "edge_id": edge.edge_id,
                "tenant_id": edge.tenant_id,
                "kind": edge.kind,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "attributes": edge.attributes,
            }
            for edge in graph.edges
        ],
        "unresolved_cross_refs": [
            {
                "source_node_id": reference.source_node_id,
                "reference_kind": reference.reference_kind,
                "raw_reference": reference.raw_reference,
                "reason": reference.reason,
            }
            for reference in graph.unresolved_cross_refs
        ],
    }


def structure_graph_digest(graph: StructuralGraph) -> str:
    """Return a deterministic SHA-256 over the complete structural graph."""
    _validate_graph(graph)
    canonical = json.dumps(
        _graph_payload(graph),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_structure_graph_manifest(
    graph: StructuralGraph,
    *,
    corpus_sha256: str,
    extraction_prompt_version: str | None = None,
    extraction_model_digest: str | None = None,
) -> StructuralGraphManifest:
    """Pin graph provenance and inventory without adding wall-clock variance."""
    if _SHA256_RE.fullmatch(corpus_sha256) is None:
        raise ValueError("corpus_sha256 must be a lowercase SHA-256 digest")

    return StructuralGraphManifest(
        schema_version=STRUCTURE_GRAPH_MANIFEST_SCHEMA_VERSION,
        tenant_id=graph.tenant_id,
        corpus_sha256=corpus_sha256,
        builder_version=graph.builder_version,
        extraction_prompt_version=extraction_prompt_version,
        extraction_model_digest=extraction_model_digest,
        graph_sha256=structure_graph_digest(graph),
        node_counts=dict(sorted(Counter(node.kind for node in graph.nodes).items())),
        edge_counts=dict(sorted(Counter(edge.kind for edge in graph.edges).items())),
        unresolved_cross_ref_count=len(graph.unresolved_cross_refs),
    )


def project_structure_graph(graph: StructuralGraph) -> nx.MultiDiGraph:
    """Rebuild a lossless in-memory projection from the portable graph contract."""
    _validate_graph(graph)
    projection = nx.MultiDiGraph(
        tenant_id=graph.tenant_id,
        builder_version=graph.builder_version,
    )
    for node in graph.nodes:
        projection.add_node(
            node.node_id,
            tenant_id=node.tenant_id,
            kind=node.kind,
            natural_key=node.natural_key,
            label=node.label,
            attributes=dict(node.attributes),
        )
    for edge in graph.edges:
        projection.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            key=edge.edge_id,
            edge_id=edge.edge_id,
            tenant_id=edge.tenant_id,
            kind=edge.kind,
            attributes=dict(edge.attributes),
        )
    return projection


__all__ = [
    "STRUCTURE_GRAPH_MANIFEST_SCHEMA_VERSION",
    "StructuralGraphManifest",
    "build_structure_graph_manifest",
    "project_structure_graph",
    "structure_graph_digest",
]
