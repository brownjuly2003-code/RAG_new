"""resolution append-only mutation guards

Revision ID: 026
Revises: 025
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None

_SCHEMA = "public"
_FUNCTION_NAME = "resolution_reject_append_only_mutation"
_APPEND_ONLY_TABLES = (
    "case_events",
    "evidence_snapshots",
    "case_evidence_links",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_FUNCTION_NAME}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            BEGIN
                RAISE EXCEPTION 'relation %.% is append-only',
                    TG_TABLE_SCHEMA, TG_TABLE_NAME
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table_name in _APPEND_ONLY_TABLES:
        op.execute(
            sa.text(
                f'CREATE TRIGGER "trg_{table_name}_append_only" '
                f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."{table_name}" '
                f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_FUNCTION_NAME}"()'
            )
        )


def downgrade() -> None:
    for table_name in reversed(_APPEND_ONLY_TABLES):
        op.execute(
            sa.text(f'DROP TRIGGER "trg_{table_name}_append_only" ON "{_SCHEMA}"."{table_name}"')
        )
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_FUNCTION_NAME}"()'))
