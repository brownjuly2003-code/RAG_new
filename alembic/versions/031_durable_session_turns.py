"""durable fenced session-turn admission

Revision ID: 031
Revises: 030
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

_POLICY_NAME = "session_turns_tenant_isolation"
_TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')"


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "turn_epoch",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_sessions_version_nonnegative",
        "sessions",
        "version >= 0",
    )
    op.create_check_constraint(
        "ck_sessions_turn_epoch_nonnegative",
        "sessions",
        "turn_epoch >= 0",
    )

    op.create_table(
        "session_turns",
        sa.Column("tenant_id", sa.String(length=50), nullable=False),
        sa.Column("turn_id", sa.String(length=128), nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("expected_version", sa.BigInteger(), nullable=False),
        sa.Column("turn_epoch", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_digest", sa.String(length=64), nullable=True),
        sa.Column("committed_version", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "turn_id",
            name="pk_session_turns",
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "tenant_id"],
            ["sessions.id", "sessions.tenant_id"],
            name="fk_session_turns_session_tenant",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "turn_epoch",
            name="uq_session_turns_tenant_session_epoch",
        ),
        sa.CheckConstraint(
            "tenant_id <> '' AND turn_id <> ''",
            name="ck_session_turns_identity_nonempty",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_session_turns_request_digest",
        ),
        sa.CheckConstraint(
            "result_digest IS NULL OR result_digest ~ '^[0-9a-f]{64}$'",
            name="ck_session_turns_result_digest",
        ),
        sa.CheckConstraint(
            "expected_version >= 0",
            name="ck_session_turns_expected_version_nonnegative",
        ),
        sa.CheckConstraint(
            "turn_epoch > 0",
            name="ck_session_turns_epoch_positive",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMMITTED', 'ABORTED', 'EXPIRED')",
            name="ck_session_turns_status",
        ),
        sa.CheckConstraint(
            "deadline_at > admitted_at",
            name="ck_session_turns_deadline_after_admission",
        ),
        sa.CheckConstraint(
            "terminal_at IS NULL OR terminal_at >= admitted_at",
            name="ck_session_turns_terminal_after_admission",
        ),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND terminal_at IS NULL "
            "AND result_digest IS NULL AND committed_version IS NULL) OR "
            "(status = 'COMMITTED' AND terminal_at IS NOT NULL "
            "AND result_digest IS NOT NULL "
            "AND committed_version = expected_version + 1) OR "
            "(status IN ('ABORTED', 'EXPIRED') AND terminal_at IS NOT NULL "
            "AND result_digest IS NULL AND committed_version IS NULL)",
            name="ck_session_turns_terminal_shape",
        ),
    )
    op.create_index(
        "uq_session_turns_one_running",
        "session_turns",
        ["tenant_id", "session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    op.create_index(
        "ix_session_turns_tenant_session_admitted",
        "session_turns",
        ["tenant_id", "session_id", "admitted_at"],
    )

    op.execute(sa.text('ALTER TABLE "session_turns" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text('ALTER TABLE "session_turns" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{_POLICY_NAME}" ON "session_turns" '
            f"AS PERMISSIVE FOR ALL TO PUBLIC USING ({_TENANT_EXPRESSION}) "
            f"WITH CHECK ({_TENANT_EXPRESSION})"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f'DROP POLICY "{_POLICY_NAME}" ON "session_turns"'))
    op.execute(sa.text('ALTER TABLE "session_turns" NO FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text('ALTER TABLE "session_turns" DISABLE ROW LEVEL SECURITY'))
    op.drop_index(
        "ix_session_turns_tenant_session_admitted",
        table_name="session_turns",
    )
    op.drop_index("uq_session_turns_one_running", table_name="session_turns")
    op.drop_table("session_turns")
    op.drop_constraint(
        "ck_sessions_turn_epoch_nonnegative",
        "sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_sessions_version_nonnegative",
        "sessions",
        type_="check",
    )
    op.drop_column("sessions", "turn_epoch")
    op.drop_column("sessions", "version")
