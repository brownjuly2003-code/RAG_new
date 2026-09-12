"""Load persisted entity enrichment only for the current tenant and chunk graph."""

import logging
import os

from sqlalchemy.exc import SQLAlchemyError

from ingestion.structure_graph import StructuralGraph

logger = logging.getLogger(__name__)


def load_matching_entity_graph(structural: StructuralGraph) -> StructuralGraph:
    if not os.getenv("DATABASE_URL"):
        return structural
    from ingestion.jobs import sync_session
    from ingestion.structure_graph_repository import StructuralGraphRepository

    try:
        with sync_session() as session:
            stored = StructuralGraphRepository(session).load(structural.tenant_id)
    except SQLAlchemyError:
        logger.warning("Persisted entity graph unavailable; using current structural graph")
        return structural
    if not any(node.kind == "entity" for node in stored.nodes):
        return structural
    current_nodes = {node.node_id: node for node in structural.nodes}
    stored_nodes = {node.node_id: node for node in stored.nodes if node.kind != "entity"}
    current_edges = {edge.edge_id: edge for edge in structural.edges}
    stored_edges = {edge.edge_id: edge for edge in stored.edges if edge.kind not in {"mentions", "co_occurs"}}
    if (stored.tenant_id != structural.tenant_id or current_nodes != stored_nodes or
            current_edges != stored_edges):
        logger.warning("Persisted entity graph does not match current corpus; using structural graph")
        return structural
    from ingestion.structure_graph_projection import structure_graph_digest

    try:
        structure_graph_digest(stored)
    except ValueError:
        logger.warning("Persisted entity graph is invalid; using structural graph")
        return structural
    return stored
