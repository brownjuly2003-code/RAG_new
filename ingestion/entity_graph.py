"""Enrich a tenant structural graph from cached per-chunk extraction results."""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import combinations

from ingestion.entity_normalization import normalize_entities
from ingestion.structure_graph import (
    ENTITY_GRAPH_BUILDER_VERSION,
    StructuralGraph,
    StructuralGraphEdge,
    StructuralGraphNode,
    _stable_id,
)
from ingestion.structure_graph_projection import structure_graph_digest


def add_entity_graph(
    graph: StructuralGraph, extracted: Mapping[str, Sequence[object]],
) -> StructuralGraph:
    structure_graph_digest(graph)
    if any(node.kind == "entity" for node in graph.nodes):
        raise ValueError("Graph already contains entity enrichment")
    chunks = {node.node_id: node for node in graph.nodes if node.kind == "chunk"}
    if set(extracted) - chunks.keys():
        raise ValueError("Extraction references an unknown chunk")
    documents: dict[str, set[str]] = defaultdict(set)
    normalized = {key: normalize_entities(values) for key, values in extracted.items()}
    for chunk_id, entities in normalized.items():
        source = str(chunks[chunk_id].attributes["source"]).replace("\\", "/").casefold()
        for entity in entities:
            documents[entity].add(source)
    retained = sorted(entity for entity, sources in documents.items() if len(sources) >= 2)
    if not retained:
        return graph
    nodes = tuple(
        StructuralGraphNode(
            node_id=_stable_id(graph.tenant_id, "entity", entity),
            tenant_id=graph.tenant_id, kind="entity", natural_key=entity, label=entity,
            attributes={"document_count": len(documents[entity])},
        ) for entity in retained
    )
    entity_ids = {node.label: node.node_id for node in nodes}
    edges: list[StructuralGraphEdge] = []
    pairs: Counter[tuple[str, str]] = Counter()
    for chunk_id in sorted(normalized):
        entities = sorted(set(normalized[chunk_id]) & entity_ids.keys())
        for entity in entities:
            target = entity_ids[entity]
            edges.append(StructuralGraphEdge(
                edge_id=_stable_id(graph.tenant_id, "mentions", f"{chunk_id}\x1f{target}"),
                tenant_id=graph.tenant_id, kind="mentions",
                source_node_id=chunk_id, target_node_id=target,
            ))
        pairs.update(combinations(entities, 2))
    for (left, right), weight in sorted(pairs.items()):
        for source, target in ((entity_ids[left], entity_ids[right]), (entity_ids[right], entity_ids[left])):
            edges.append(StructuralGraphEdge(
                edge_id=_stable_id(graph.tenant_id, "co_occurs", f"{source}\x1f{target}"),
                tenant_id=graph.tenant_id, kind="co_occurs",
                source_node_id=source, target_node_id=target, attributes={"weight": weight},
            ))
    return replace(graph, builder_version=f"{graph.builder_version}+{ENTITY_GRAPH_BUILDER_VERSION}",
                   nodes=tuple(sorted(graph.nodes + nodes, key=lambda node: (node.kind, node.natural_key))),
                   edges=tuple(sorted(graph.edges + tuple(edges),
                                      key=lambda edge: (edge.kind, edge.source_node_id, edge.target_node_id))))
