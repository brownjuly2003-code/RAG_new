"""resolution tenant row-level security

Revision ID: 025
Revises: 024
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None

_POLICY_NAME = "resolution_tenant_isolation"
_TENANT_TABLES = (
    "support_cases",
    "case_events",
    "evidence_snapshots",
    "case_evidence_links",
)
_TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
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
