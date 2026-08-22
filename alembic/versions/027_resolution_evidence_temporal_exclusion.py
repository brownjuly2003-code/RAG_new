"""resolution evidence temporal exclusion

Revision ID: 027
Revises: 026
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None

_SCHEMA = "public"
_TABLE_NAME = "evidence_snapshots"
_CONSTRAINT_NAME = "ex_evidence_snapshots_temporal_identity"


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    op.execute(
        sa.text(
            f"""
            ALTER TABLE "{_SCHEMA}"."{_TABLE_NAME}"
            ADD CONSTRAINT "{_CONSTRAINT_NAME}"
            EXCLUDE USING gist (
                tenant_id WITH =,
                logical_key WITH =,
                applicability_key WITH =,
                authority WITH =,
                tstzrange(valid_from, valid_to, '[)') WITH &&
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(f'ALTER TABLE "{_SCHEMA}"."{_TABLE_NAME}" DROP CONSTRAINT "{_CONSTRAINT_NAME}"')
    )
