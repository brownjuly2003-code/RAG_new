"""tenant-scoped structural knowledge graph

Revision ID: 032
Revises: 031
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None

_POLICY_NAME = "kb_structure_graph_tenant_isolation"
_TENANT_TABLES = ("kb_graph_nodes", "kb_graph_edges")
_TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')"


def upgrade() -> None:
    op.create_table(
        "kb_graph_nodes",
        sa.Column("tenant_id", sa.String(length=50), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("natural_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "node_id", name="pk_kb_graph_nodes"),
        sa.UniqueConstraint(
            "tenant_id",
            "kind",
            "natural_key",
            name="uq_kb_graph_nodes_tenant_kind_key",
        ),
        sa.CheckConstraint(
            "kind IN ('document', 'section', 'chunk', 'category')",
            name="ck_kb_graph_nodes_kind",
        ),
    )
    op.create_index(
        "ix_kb_graph_nodes_tenant_kind",
        "kb_graph_nodes",
        ["tenant_id", "kind"],
    )

    op.create_table(
        "kb_graph_edges",
        sa.Column("tenant_id", sa.String(length=50), nullable=False),
        sa.Column("edge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "edge_id", name="pk_kb_graph_edges"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_node_id"],
            ["kb_graph_nodes.tenant_id", "kb_graph_nodes.node_id"],
            name="fk_kb_graph_edges_source_node",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_node_id"],
            ["kb_graph_nodes.tenant_id", "kb_graph_nodes.node_id"],
            name="fk_kb_graph_edges_target_node",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "kind",
            "source_node_id",
            "target_node_id",
            name="uq_kb_graph_edges_tenant_kind_nodes",
        ),
        sa.CheckConstraint(
            "kind IN ('contains', 'next', 'same_section', 'cross_ref', 'category')",
            name="ck_kb_graph_edges_kind",
        ),
    )
    op.create_index(
        "ix_kb_graph_edges_tenant_kind_source",
        "kb_graph_edges",
        ["tenant_id", "kind", "source_node_id"],
    )
    op.create_index(
        "ix_kb_graph_edges_tenant_target",
        "kb_graph_edges",
        ["tenant_id", "target_node_id"],
    )

    for table_name in _TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                f'CREATE POLICY "{_POLICY_NAME}" ON "{table_name}" '
                f"AS PERMISSIVE FOR ALL TO PUBLIC USING ({_TENANT_EXPRESSION}) "
                f"WITH CHECK ({_TENANT_EXPRESSION})"
            )
        )


def downgrade() -> None:
    for table_name in reversed(_TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY "{_POLICY_NAME}" ON "{table_name}"'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))

    op.drop_table("kb_graph_edges")
    op.drop_table("kb_graph_nodes")
