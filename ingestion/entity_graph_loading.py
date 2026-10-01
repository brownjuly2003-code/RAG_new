"""Load persisted entity enrichment only for the current tenant and chunk graph."""

import logging
import os

from sqlalchemy.exc import SQLAlchemyError

from ingestion.structure_graph import StructuralGraph

logger = logging.getLogger(__name__)


# Bounded, non-secret reasons why the entity lane is or is not available. They
# travel into the retrieval path so a fallback to the structural graph is visible
# in the trace instead of being a log line only (audit 2026-09-30, F4).
ENTITY_GRAPH_MATCHED = "matched"
ENTITY_GRAPH_NO_DATABASE = "no_database"
ENTITY_GRAPH_UNAVAILABLE = "unavailable"
ENTITY_GRAPH_ABSENT = "absent"
ENTITY_GRAPH_MISMATCH = "mismatch"
ENTITY_GRAPH_INVALID = "invalid"


def load_matching_entity_graph_with_status(
    structural: StructuralGraph,
) -> tuple[StructuralGraph, str]:
    """Return the graph to project and a bounded status naming why."""
    if not os.getenv("DATABASE_URL"):
        return structural, ENTITY_GRAPH_NO_DATABASE
    from ingestion.jobs import sync_session
    from ingestion.structure_graph_repository import StructuralGraphRepository

    try:
        with sync_session() as session:
            stored = StructuralGraphRepository(session).load(structural.tenant_id)
    except SQLAlchemyError:
        logger.warning("Persisted entity graph unavailable; using current structural graph")
        return structural, ENTITY_GRAPH_UNAVAILABLE
    if not any(node.kind == "entity" for node in stored.nodes):
        return structural, ENTITY_GRAPH_ABSENT
    current_nodes = {node.node_id: node for node in structural.nodes}
    stored_nodes = {node.node_id: node for node in stored.nodes if node.kind != "entity"}
    current_edges = {edge.edge_id: edge for edge in structural.edges}
    stored_edges = {edge.edge_id: edge for edge in stored.edges if edge.kind not in {"mentions", "co_occurs"}}
    if (stored.tenant_id != structural.tenant_id or current_nodes != stored_nodes or
            current_edges != stored_edges):
        logger.warning("Persisted entity graph does not match current corpus; using structural graph")
        return structural, ENTITY_GRAPH_MISMATCH
    from ingestion.structure_graph_projection import structure_graph_digest

    try:
        structure_graph_digest(stored)
    except ValueError:
        logger.warning("Persisted entity graph is invalid; using structural graph")
        return structural, ENTITY_GRAPH_INVALID
    return stored, ENTITY_GRAPH_MATCHED


def load_matching_entity_graph(structural: StructuralGraph) -> StructuralGraph:
    return load_matching_entity_graph_with_status(structural)[0]
