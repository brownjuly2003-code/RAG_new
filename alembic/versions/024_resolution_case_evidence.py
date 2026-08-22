"""resolution support-case and evidence persistence

Revision ID: 024
Revises: 023
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.String(length=128), nullable=False),
        sa.Column("contract_digest", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_support_cases_id_tenant"),
        sa.CheckConstraint("version >= 1", name="ck_support_cases_version_positive"),
    )
    op.create_index(
        "ix_support_cases_tenant_status",
        "support_cases",
        ["tenant_id", "status"],
    )

    op.create_table(
        "case_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["support_cases.id", "support_cases.tenant_id"],
            ondelete="RESTRICT",
            name="fk_case_events_case_owner",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "sequence",
            name="uq_case_events_tenant_case_sequence",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "case_version",
            name="uq_case_events_tenant_case_version",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "command_id",
            name="uq_case_events_tenant_case_command",
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_case_events_sequence_positive"),
        sa.CheckConstraint("case_version >= 1", name="ck_case_events_version_positive"),
        sa.CheckConstraint("sequence = case_version", name="ck_case_events_sequence_version"),
    )

    op.create_table(
        "evidence_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logical_key", sa.String(length=256), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("source_version", sa.String(length=256), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authority", sa.String(length=128), nullable=False),
        sa.Column("applicability_key", sa.String(length=256), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("reference_storage", sa.String(length=32), nullable=False),
        sa.Column("reference_locator", sa.String(length=512), nullable=False),
        sa.Column("encryption_profile", sa.String(length=128), nullable=True),
        sa.Column("redaction_profile", sa.String(length=128), nullable=False),
        sa.Column("retention_class", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_evidence_snapshots_id_tenant"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_evidence_snapshots_valid_range",
        ),
    )
    op.create_index(
        "ix_evidence_snapshots_tenant_logical_key",
        "evidence_snapshots",
        ["tenant_id", "logical_key", "applicability_key"],
    )

    op.create_table(
        "case_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("gathered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id", "case_version"],
            ["case_events.tenant_id", "case_events.case_id", "case_events.case_version"],
            ondelete="RESTRICT",
            name="fk_case_evidence_links_case_version_owner",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "tenant_id"],
            ["evidence_snapshots.id", "evidence_snapshots.tenant_id"],
            ondelete="RESTRICT",
            name="fk_case_evidence_links_evidence_owner",
        ),
        sa.CheckConstraint(
            "case_version >= 1",
            name="ck_case_evidence_links_version_positive",
        ),
    )
    op.create_index(
        "ix_case_evidence_links_tenant_case_version",
        "case_evidence_links",
        ["tenant_id", "case_id", "case_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_case_evidence_links_tenant_case_version",
        table_name="case_evidence_links",
    )
    op.drop_table("case_evidence_links")
    op.drop_index(
        "ix_evidence_snapshots_tenant_logical_key",
        table_name="evidence_snapshots",
    )
    op.drop_table("evidence_snapshots")
    op.drop_table("case_events")
    op.drop_index("ix_support_cases_tenant_status", table_name="support_cases")
    op.drop_table("support_cases")
