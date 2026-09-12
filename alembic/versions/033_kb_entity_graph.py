"""Allow entity nodes and weighted entity edges in the tenant graph.

Revision ID: 033
Revises: 032
"""

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_kb_graph_nodes_kind", "kb_graph_nodes", type_="check")
    op.create_check_constraint("ck_kb_graph_nodes_kind", "kb_graph_nodes",
                               "kind IN ('document', 'section', 'chunk', 'category', 'entity')")
    op.drop_constraint("ck_kb_graph_edges_kind", "kb_graph_edges", type_="check")
    op.create_check_constraint("ck_kb_graph_edges_kind", "kb_graph_edges",
                               "kind IN ('contains', 'next', 'same_section', 'cross_ref', 'category', 'mentions', 'co_occurs')")


def downgrade() -> None:
    # Existing entity data blocks downgrade; never delete it to fit the old schema.
    op.drop_constraint("ck_kb_graph_edges_kind", "kb_graph_edges", type_="check")
    op.create_check_constraint("ck_kb_graph_edges_kind", "kb_graph_edges",
                               "kind IN ('contains', 'next', 'same_section', 'cross_ref', 'category')")
    op.drop_constraint("ck_kb_graph_nodes_kind", "kb_graph_nodes", type_="check")
    op.create_check_constraint("ck_kb_graph_nodes_kind", "kb_graph_nodes",
                               "kind IN ('document', 'section', 'chunk', 'category')")
