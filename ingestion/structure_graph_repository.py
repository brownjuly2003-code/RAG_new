"""Transactional persistence for tenant-owned structural graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from db.models import KbGraphEdge, KbGraphNode
from ingestion.structure_graph import (
    STRUCTURAL_GRAPH_BUILDER_VERSION,
    EdgeKind,
    NodeKind,
    StructuralGraph,
    StructuralGraphEdge,
    StructuralGraphNode,
)


@dataclass(frozen=True)
class StructuralGraphWriteReceipt:
    tenant_id: str
    node_count: int
    edge_count: int


class StructuralGraphRepository:
    """Replace and load one tenant graph inside the caller's transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(self, graph: StructuralGraph) -> StructuralGraphWriteReceipt:
        self._validate_graph(graph)
        self._set_tenant_context(graph.tenant_id)

        self._session.execute(
            delete(KbGraphEdge).where(KbGraphEdge.tenant_id == graph.tenant_id)
        )
        self._session.execute(
            delete(KbGraphNode).where(KbGraphNode.tenant_id == graph.tenant_id)
        )

        node_rows = [
            KbGraphNode(
                tenant_id=node.tenant_id,
                node_id=UUID(node.node_id),
                kind=node.kind,
                natural_key=node.natural_key,
                label=node.label,
                attributes=dict(node.attributes),
            )
            for node in graph.nodes
        ]
        self._session.add_all(node_rows)
        self._session.flush()

        edge_rows = [
            KbGraphEdge(
                tenant_id=edge.tenant_id,
                edge_id=UUID(edge.edge_id),
                kind=edge.kind,
                source_node_id=UUID(edge.source_node_id),
                target_node_id=UUID(edge.target_node_id),
                attributes=dict(edge.attributes),
            )
            for edge in graph.edges
        ]
        self._session.add_all(edge_rows)
        self._session.flush()

        return StructuralGraphWriteReceipt(
            tenant_id=graph.tenant_id,
            node_count=len(node_rows),
            edge_count=len(edge_rows),
        )

    def load(self, tenant_id: str) -> StructuralGraph:
        self._set_tenant_context(tenant_id)
        node_rows = self._session.execute(
            select(
                KbGraphNode.node_id,
                KbGraphNode.kind,
                KbGraphNode.natural_key,
                KbGraphNode.label,
                KbGraphNode.attributes,
            )
            .where(KbGraphNode.tenant_id == tenant_id)
            .order_by(KbGraphNode.kind, KbGraphNode.natural_key)
        ).all()
        edge_rows = self._session.execute(
            select(
                KbGraphEdge.edge_id,
                KbGraphEdge.kind,
                KbGraphEdge.source_node_id,
                KbGraphEdge.target_node_id,
                KbGraphEdge.attributes,
            )
            .where(KbGraphEdge.tenant_id == tenant_id)
            .order_by(
                KbGraphEdge.kind,
                KbGraphEdge.source_node_id,
                KbGraphEdge.target_node_id,
            )
        ).all()

        return StructuralGraph(
            tenant_id=tenant_id,
            builder_version=STRUCTURAL_GRAPH_BUILDER_VERSION,
            nodes=tuple(
                StructuralGraphNode(
                    node_id=str(row.node_id),
                    tenant_id=tenant_id,
                    kind=cast(NodeKind, row.kind),
                    natural_key=row.natural_key,
                    label=row.label,
                    attributes=dict(row.attributes or {}),
                )
                for row in node_rows
            ),
            edges=tuple(
                StructuralGraphEdge(
                    edge_id=str(row.edge_id),
                    tenant_id=tenant_id,
                    kind=cast(EdgeKind, row.kind),
                    source_node_id=str(row.source_node_id),
                    target_node_id=str(row.target_node_id),
                    attributes=dict(row.attributes or {}),
                )
                for row in edge_rows
            ),
            unresolved_cross_refs=(),
        )

    def _set_tenant_context(self, tenant_id: str) -> None:
        bind = getattr(self._session, "bind", None)
        if bind is None:
            bind = self._session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            self._session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": tenant_id},
            )

    @staticmethod
    def _validate_graph(graph: StructuralGraph) -> None:
        node_ids = {node.node_id for node in graph.nodes}
        if any(node.tenant_id != graph.tenant_id for node in graph.nodes):
            raise ValueError("Structural graph contains a node from another tenant")
        if any(edge.tenant_id != graph.tenant_id for edge in graph.edges):
            raise ValueError("Structural graph contains an edge from another tenant")
        if any(
            edge.source_node_id not in node_ids or edge.target_node_id not in node_ids
            for edge in graph.edges
        ):
            raise ValueError("Structural graph edge references a missing node")
