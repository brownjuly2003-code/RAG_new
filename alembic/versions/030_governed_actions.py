"""governed action execution persistence

Revision ID: 030
Revises: 029
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None

_SCHEMA = "public"
_POLICY_NAME = "action_tenant_isolation"
_TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
_TABLES = (
    "action_manifests",
    "policy_decisions",
    "action_runs",
    "action_confirmations",
    "action_attempts",
    "action_outbox_events",
    "action_postcondition_results",
    "action_kill_switches",
)
_APPEND_ONLY_TABLES = (
    "action_manifests",
    "policy_decisions",
    "action_postcondition_results",
    "action_kill_switches",
)
_APPEND_FUNCTION = "action_reject_append_only_mutation"
_RUN_FUNCTION = "action_guard_run_transition"
_CONFIRMATION_FUNCTION = "action_guard_confirmation_transition"
_ATTEMPT_FUNCTION = "action_guard_attempt_transition"
_OUTBOX_FUNCTION = "action_guard_outbox_transition"


def upgrade() -> None:
    op.create_table(
        "action_manifests",
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manifest_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("schema_digest", sa.String(length=64), nullable=False),
        sa.Column("risk", sa.String(length=32), nullable=False),
        sa.Column(
            "required_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("input_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("confirmation_ttl_seconds", sa.Integer(), nullable=True),
        sa.Column("postcondition_id", sa.String(length=128), nullable=False),
        sa.Column("postcondition_version", sa.String(length=64), nullable=False),
        sa.Column("compensation_manifest_id", sa.String(length=128), nullable=True),
        sa.Column("max_reconciliation_attempts", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("record_id", "tenant_id", name="uq_action_manifests_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "manifest_id",
            "version",
            name="uq_action_manifests_identity",
        ),
        sa.CheckConstraint(
            "manifest_id = trim(manifest_id) AND manifest_id <> ''",
            name="ck_action_manifests_id",
        ),
        sa.CheckConstraint(
            "version = trim(version) AND version <> ''",
            name="ck_action_manifests_version",
        ),
        sa.CheckConstraint(
            "schema_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_manifests_schema_digest",
        ),
        sa.CheckConstraint(
            "risk IN ('read', 'reversible_write', 'irreversible_write')",
            name="ck_action_manifests_risk",
        ),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 300",
            name="ck_action_manifests_timeout",
        ),
        sa.CheckConstraint(
            "confirmation_ttl_seconds IS NULL OR confirmation_ttl_seconds BETWEEN 1 AND 86400",
            name="ck_action_manifests_confirmation_ttl",
        ),
        sa.CheckConstraint(
            "max_reconciliation_attempts BETWEEN 1 AND 20",
            name="ck_action_manifests_reconciliation_attempts",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(required_scopes) = 'array' AND jsonb_array_length(required_scopes) > 0",
            name="ck_action_manifests_required_scopes",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(input_fields) = 'array' AND jsonb_array_length(input_fields) > 0",
            name="ck_action_manifests_input_fields",
        ),
    )

    op.create_table(
        "policy_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_adapter", sa.String(length=128), nullable=False),
        sa.Column("policy_revision", sa.String(length=128), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["support_cases.id", "support_cases.tenant_id"],
            ondelete="RESTRICT",
            name="fk_policy_decisions_case_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_policy_decisions_id_tenant"),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_policy_decisions_action_digest",
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name="ck_policy_decisions_input_digest",
        ),
        sa.CheckConstraint(
            "evidence_digest ~ '^[0-9a-f]{64}$'",
            name="ck_policy_decisions_evidence_digest",
        ),
        sa.CheckConstraint(
            "result IN ('allow', 'deny', 'escalate')",
            name="ck_policy_decisions_result",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array' AND jsonb_array_length(reason_codes) > 0",
            name="ck_policy_decisions_reason_codes",
        ),
        sa.CheckConstraint("expires_at > decided_at", name="ck_policy_decisions_expiry"),
    )

    op.create_table(
        "action_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manifest_id", sa.String(length=128), nullable=False),
        sa.Column("manifest_version", sa.String(length=64), nullable=False),
        sa.Column("manifest_schema_digest", sa.String(length=64), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("operation_key_digest", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("policy_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("downstream_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("input_payload", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("confirmation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outbox_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_token", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remote_operation_id", sa.String(length=256), nullable=True),
        sa.Column("remote_resource_id", sa.String(length=256), nullable=True),
        sa.Column("result_digest", sa.String(length=64), nullable=True),
        sa.Column("compensation_of_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["support_cases.id", "support_cases.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_runs_case_owner",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "manifest_id", "manifest_version"],
            [
                "action_manifests.tenant_id",
                "action_manifests.manifest_id",
                "action_manifests.version",
            ],
            ondelete="RESTRICT",
            name="fk_action_runs_manifest_owner",
        ),
        sa.ForeignKeyConstraint(
            ["policy_decision_id", "tenant_id"],
            ["policy_decisions.id", "policy_decisions.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_runs_policy_owner",
        ),
        sa.ForeignKeyConstraint(
            ["compensation_of_run_id", "tenant_id"],
            ["action_runs.id", "action_runs.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_runs_compensation_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_action_runs_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "operation_key_digest",
            name="uq_action_runs_operation_key",
        ),
        sa.UniqueConstraint("tenant_id", "action_digest", name="uq_action_runs_action_digest"),
        sa.UniqueConstraint(
            "tenant_id",
            "downstream_idempotency_key",
            name="uq_action_runs_downstream_key",
        ),
        sa.CheckConstraint(
            "operation_key_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_runs_operation_digest",
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_runs_input_digest",
        ),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_runs_action_digest",
        ),
        sa.CheckConstraint(
            "evidence_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_runs_evidence_digest",
        ),
        sa.CheckConstraint(
            "result_digest IS NULL OR result_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_runs_result_digest",
        ),
        sa.CheckConstraint(
            "state IN ('awaiting_confirmation', 'ready', 'dispatched', 'succeeded', "
            "'failed', 'outcome_unknown', 'reconciling', 'postcondition_passed', "
            "'postcondition_failed', 'escalated', 'cancelled', 'expired')",
            name="ck_action_runs_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_action_runs_attempt_count"),
        sa.CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="ck_action_runs_lease_pair",
        ),
        sa.CheckConstraint(
            "compensation_of_run_id IS NULL OR compensation_of_run_id <> id",
            name="ck_action_runs_compensation_distinct",
        ),
    )
    op.create_index("ix_action_runs_tenant_state", "action_runs", ["tenant_id", "state"])

    op.create_table(
        "action_confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=256), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["action_runs.id", "action_runs.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_confirmations_run_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_action_confirmations_id_tenant"),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_action_confirmations_run"),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_confirmations_digest",
        ),
        sa.CheckConstraint(
            "decision IN ('pending', 'approved', 'denied', 'expired')",
            name="ck_action_confirmations_decision",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_action_confirmations_expiry",
        ),
        sa.CheckConstraint(
            "(decision = 'pending' AND decided_at IS NULL) OR "
            "(decision <> 'pending' AND decided_at IS NOT NULL)",
            name="ck_action_confirmations_decided_at",
        ),
    )

    op.create_table(
        "action_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transport_outcome", sa.String(length=32), nullable=True),
        sa.Column("response_digest", sa.String(length=64), nullable=True),
        sa.Column("remote_operation_id", sa.String(length=256), nullable=True),
        sa.Column("remote_resource_id", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["action_runs.id", "action_runs.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_attempts_run_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_action_attempts_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "attempt_number",
            name="uq_action_attempts_run_number",
        ),
        sa.CheckConstraint("attempt_number >= 1", name="ck_action_attempts_number"),
        sa.CheckConstraint(
            "kind IN ('dispatch', 'reconcile')",
            name="ck_action_attempts_kind",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_attempts_request_digest",
        ),
        sa.CheckConstraint(
            "response_digest IS NULL OR response_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_attempts_response_digest",
        ),
        sa.CheckConstraint(
            "transport_outcome IS NULL OR transport_outcome IN "
            "('succeeded', 'rejected', 'timed_out', 'identity_mismatch', "
            "'not_found', 'unavailable')",
            name="ck_action_attempts_transport_outcome",
        ),
        sa.CheckConstraint(
            "(finished_at IS NULL AND transport_outcome IS NULL) OR "
            "(finished_at IS NOT NULL AND transport_outcome IS NOT NULL)",
            name="ck_action_attempts_finished_pair",
        ),
    )

    op.create_table(
        "action_outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["action_runs.id", "action_runs.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_outbox_events_run_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_action_outbox_events_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "sequence",
            name="uq_action_outbox_events_run_sequence",
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_action_outbox_events_sequence"),
        sa.CheckConstraint(
            "kind IN ('dispatch', 'reconcile')",
            name="ck_action_outbox_events_kind",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'leased', 'delivered')",
            name="ck_action_outbox_events_state",
        ),
        sa.CheckConstraint(
            "payload_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_outbox_events_payload_digest",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_action_outbox_events_attempts"),
        sa.CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="ck_action_outbox_events_lease_pair",
        ),
        sa.CheckConstraint(
            "(state = 'delivered') = (delivered_at IS NOT NULL)",
            name="ck_action_outbox_events_delivered_at",
        ),
    )
    op.create_index(
        "ix_action_outbox_events_claim",
        "action_outbox_events",
        ["tenant_id", "state", "available_at"],
    )

    op.create_table(
        "action_postcondition_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checker_id", sa.String(length=128), nullable=False),
        sa.Column("checker_version", sa.String(length=64), nullable=False),
        sa.Column("observation_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "tenant_id"],
            ["action_runs.id", "action_runs.tenant_id"],
            ondelete="RESTRICT",
            name="fk_action_postcondition_results_run_owner",
        ),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_action_postconditions_id_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "checker_id",
            "checker_version",
            name="uq_action_postconditions_run_checker",
        ),
        sa.CheckConstraint(
            "observation_digest ~ '^[0-9a-f]{64}$'",
            name="ck_action_postconditions_observation_digest",
        ),
        sa.CheckConstraint(
            "status IN ('pass', 'fail', 'unknown')",
            name="ck_action_postconditions_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array' AND jsonb_array_length(reason_codes) > 0",
            name="ck_action_postconditions_reason_codes",
        ),
    )

    op.create_table(
        "action_kill_switches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_action_kill_switches_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "environment",
            "connector_id",
            "action_id",
            "version",
            name="uq_action_kill_switches_scope_version",
        ),
        sa.CheckConstraint("version >= 1", name="ck_action_kill_switches_version"),
        sa.CheckConstraint(
            "environment = trim(environment) AND environment <> ''",
            name="ck_action_kill_switches_environment",
        ),
        sa.CheckConstraint(
            "connector_id = trim(connector_id) AND connector_id <> ''",
            name="ck_action_kill_switches_connector",
        ),
        sa.CheckConstraint(
            "action_id = trim(action_id) AND action_id <> ''",
            name="ck_action_kill_switches_action",
        ),
        sa.CheckConstraint(
            "reason_code = trim(reason_code) AND reason_code <> ''",
            name="ck_action_kill_switches_reason",
        ),
    )

    _create_guard_functions()
    _create_guard_triggers()
    _enable_tenant_rls()


def _create_guard_functions() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_APPEND_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            BEGIN
                RAISE EXCEPTION 'relation %.% is append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_RUN_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            DECLARE
                transition_allowed boolean;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'action runs cannot be deleted' USING ERRCODE = '55000';
                END IF;
                IF NEW.id IS DISTINCT FROM OLD.id
                    OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                    OR NEW.case_id IS DISTINCT FROM OLD.case_id
                    OR NEW.manifest_id IS DISTINCT FROM OLD.manifest_id
                    OR NEW.manifest_version IS DISTINCT FROM OLD.manifest_version
                    OR NEW.manifest_schema_digest IS DISTINCT FROM OLD.manifest_schema_digest
                    OR NEW.connector_id IS DISTINCT FROM OLD.connector_id
                    OR NEW.action_id IS DISTINCT FROM OLD.action_id
                    OR NEW.operation_key_digest IS DISTINCT FROM OLD.operation_key_digest
                    OR NEW.input_digest IS DISTINCT FROM OLD.input_digest
                    OR NEW.action_digest IS DISTINCT FROM OLD.action_digest
                    OR NEW.evidence_digest IS DISTINCT FROM OLD.evidence_digest
                    OR NEW.policy_decision_id IS DISTINCT FROM OLD.policy_decision_id
                    OR NEW.downstream_idempotency_key IS DISTINCT FROM OLD.downstream_idempotency_key
                    OR NEW.input_payload IS DISTINCT FROM OLD.input_payload
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at
                    OR NEW.confirmation_id IS DISTINCT FROM OLD.confirmation_id
                    OR NEW.compensation_of_run_id IS DISTINCT FROM OLD.compensation_of_run_id
                    OR NEW.attempt_count < OLD.attempt_count
                THEN
                    RAISE EXCEPTION 'action run identity is immutable' USING ERRCODE = '55000';
                END IF;
                transition_allowed :=
                    (OLD.state = 'awaiting_confirmation' AND NEW.state IN ('ready', 'cancelled', 'expired'))
                    OR (OLD.state = 'ready' AND NEW.state = 'dispatched')
                    OR (OLD.state = 'dispatched' AND NEW.state IN ('succeeded', 'failed', 'outcome_unknown', 'escalated'))
                    OR (OLD.state = 'outcome_unknown' AND NEW.state = 'reconciling')
                    OR (OLD.state = 'reconciling' AND NEW.state IN ('succeeded', 'outcome_unknown', 'escalated'))
                    OR (OLD.state = 'succeeded' AND NEW.state IN ('postcondition_passed', 'postcondition_failed', 'escalated'));
                IF NOT transition_allowed OR NEW.updated_at < OLD.updated_at THEN
                    RAISE EXCEPTION 'illegal action run state transition % -> %', OLD.state, NEW.state
                        USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_CONFIRMATION_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            BEGIN
                IF TG_OP = 'UPDATE'
                    AND OLD.decision = 'pending'
                    AND NEW.decision IN ('approved', 'denied', 'expired')
                    AND NEW.id IS NOT DISTINCT FROM OLD.id
                    AND NEW.tenant_id IS NOT DISTINCT FROM OLD.tenant_id
                    AND NEW.run_id IS NOT DISTINCT FROM OLD.run_id
                    AND NEW.action_digest IS NOT DISTINCT FROM OLD.action_digest
                    AND NEW.expires_at IS NOT DISTINCT FROM OLD.expires_at
                    AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
                    AND NEW.decided_at IS NOT NULL
                    AND NEW.decided_at >= OLD.created_at
                    AND (
                        (NEW.decision = 'expired' AND NEW.decided_at >= OLD.expires_at)
                        OR (NEW.decision <> 'expired' AND NEW.decided_at < OLD.expires_at)
                    )
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'confirmation permits one bounded decision only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_ATTEMPT_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            BEGIN
                IF TG_OP = 'UPDATE'
                    AND OLD.finished_at IS NULL
                    AND OLD.transport_outcome IS NULL
                    AND NEW.finished_at IS NOT NULL
                    AND NEW.transport_outcome IS NOT NULL
                    AND NEW.id IS NOT DISTINCT FROM OLD.id
                    AND NEW.tenant_id IS NOT DISTINCT FROM OLD.tenant_id
                    AND NEW.run_id IS NOT DISTINCT FROM OLD.run_id
                    AND NEW.attempt_number IS NOT DISTINCT FROM OLD.attempt_number
                    AND NEW.kind IS NOT DISTINCT FROM OLD.kind
                    AND NEW.request_digest IS NOT DISTINCT FROM OLD.request_digest
                    AND NEW.started_at IS NOT DISTINCT FROM OLD.started_at
                    AND NEW.finished_at >= OLD.started_at
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'action attempt permits one completion only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_OUTBOX_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            BEGIN
                IF TG_OP = 'UPDATE'
                    AND NEW.id IS NOT DISTINCT FROM OLD.id
                    AND NEW.tenant_id IS NOT DISTINCT FROM OLD.tenant_id
                    AND NEW.run_id IS NOT DISTINCT FROM OLD.run_id
                    AND NEW.sequence IS NOT DISTINCT FROM OLD.sequence
                    AND NEW.kind IS NOT DISTINCT FROM OLD.kind
                    AND NEW.payload_digest IS NOT DISTINCT FROM OLD.payload_digest
                    AND NEW.available_at IS NOT DISTINCT FROM OLD.available_at
                    AND (
                        (
                            OLD.state = 'pending'
                            AND NEW.state = 'leased'
                            AND NEW.attempts = OLD.attempts + 1
                            AND NEW.lease_token IS NOT NULL
                            AND NEW.lease_expires_at IS NOT NULL
                            AND NEW.delivered_at IS NULL
                        )
                        OR (
                            OLD.state = 'leased'
                            AND NEW.state = 'delivered'
                            AND NEW.attempts = OLD.attempts
                            AND NEW.lease_token IS NULL
                            AND NEW.lease_expires_at IS NULL
                            AND NEW.delivered_at IS NOT NULL
                        )
                    )
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'illegal action outbox transition' USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )


def _create_guard_triggers() -> None:
    for table_name in _APPEND_ONLY_TABLES:
        op.execute(
            sa.text(
                f'CREATE TRIGGER "trg_{table_name}_append_only" '
                f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."{table_name}" '
                f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_APPEND_FUNCTION}"()'
            )
        )
    op.execute(
        sa.text(
            f'CREATE TRIGGER "trg_action_runs_transition" '
            f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."action_runs" '
            f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_RUN_FUNCTION}"()'
        )
    )
    op.execute(
        sa.text(
            f'CREATE TRIGGER "trg_action_confirmations_transition" '
            f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."action_confirmations" '
            f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_CONFIRMATION_FUNCTION}"()'
        )
    )
    op.execute(
        sa.text(
            f'CREATE TRIGGER "trg_action_attempts_transition" '
            f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."action_attempts" '
            f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_ATTEMPT_FUNCTION}"()'
        )
    )
    op.execute(
        sa.text(
            f'CREATE TRIGGER "trg_action_outbox_events_transition" '
            f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."action_outbox_events" '
            f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_OUTBOX_FUNCTION}"()'
        )
    )


def _enable_tenant_rls() -> None:
    for table_name in _TABLES:
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
    for table_name in reversed(_TABLES):
        op.execute(sa.text(f'DROP POLICY "{_POLICY_NAME}" ON "{table_name}"'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))

    op.execute(
        sa.text(
            f'DROP TRIGGER "trg_action_outbox_events_transition" '
            f'ON "{_SCHEMA}"."action_outbox_events"'
        )
    )
    op.execute(
        sa.text(f'DROP TRIGGER "trg_action_attempts_transition" ON "{_SCHEMA}"."action_attempts"')
    )
    op.execute(
        sa.text(
            f'DROP TRIGGER "trg_action_confirmations_transition" '
            f'ON "{_SCHEMA}"."action_confirmations"'
        )
    )
    op.execute(sa.text(f'DROP TRIGGER "trg_action_runs_transition" ON "{_SCHEMA}"."action_runs"'))
    for table_name in reversed(_APPEND_ONLY_TABLES):
        op.execute(
            sa.text(f'DROP TRIGGER "trg_{table_name}_append_only" ON "{_SCHEMA}"."{table_name}"')
        )

    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_OUTBOX_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_ATTEMPT_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_CONFIRMATION_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_RUN_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_APPEND_FUNCTION}"()'))

    op.drop_table("action_kill_switches")
    op.drop_table("action_postcondition_results")
    op.drop_index("ix_action_outbox_events_claim", table_name="action_outbox_events")
    op.drop_table("action_outbox_events")
    op.drop_table("action_attempts")
    op.drop_table("action_confirmations")
    op.drop_index("ix_action_runs_tenant_state", table_name="action_runs")
    op.drop_table("action_runs")
    op.drop_table("policy_decisions")
    op.drop_table("action_manifests")
