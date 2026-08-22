"""temporal knowledge authority persistence

Revision ID: 029
Revises: 028
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None

_SCHEMA = "public"
_POLICY_NAME = "knowledge_tenant_isolation"
_TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
_TABLES = (
    "knowledge_objects",
    "knowledge_applicability",
    "knowledge_versions",
    "knowledge_supersessions",
    "knowledge_conflicts",
    "knowledge_projection_bindings",
)
_APPEND_ONLY_TABLES = (
    "knowledge_objects",
    "knowledge_applicability",
    "knowledge_supersessions",
    "knowledge_conflicts",
    "knowledge_projection_bindings",
)
_APPEND_FUNCTION = "knowledge_reject_append_only_mutation"
_VERSION_FUNCTION = "knowledge_guard_version_system_close"
_CONFLICT_FUNCTION = "knowledge_validate_conflict"
_PROJECTION_FUNCTION = "knowledge_validate_projection_binding"


def _safe_text_check(column_name: str) -> str:
    return f"{column_name} = trim({column_name}) AND {column_name} <> ''"


def _applicability_check(column_name: str) -> str:
    return f"{_safe_text_check(column_name)} AND {column_name} NOT LIKE '%*%'"


def upgrade() -> None:
    op.create_table(
        "knowledge_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logical_key", sa.String(length=256), nullable=False),
        sa.Column("source_id", sa.String(length=256), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("authority", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_knowledge_objects_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "source_id",
            "logical_key",
            name="uq_knowledge_objects_source_identity",
        ),
        sa.CheckConstraint(
            _safe_text_check("logical_key"),
            name="ck_knowledge_objects_logical_key",
        ),
        sa.CheckConstraint(
            _safe_text_check("source_id"),
            name="ck_knowledge_objects_source_id",
        ),
        sa.CheckConstraint(_safe_text_check("owner"), name="ck_knowledge_objects_owner"),
        sa.CheckConstraint(
            _safe_text_check("authority"),
            name="ck_knowledge_objects_authority",
        ),
    )

    op.create_table(
        "knowledge_applicability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("customer_plan", sa.String(length=128), nullable=False),
        sa.Column("cargo_type", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=128), nullable=False),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_knowledge_applicability_id_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "product",
            "region",
            "customer_plan",
            "cargo_type",
            "channel",
            name="uq_knowledge_applicability_exact_dimensions",
        ),
        sa.CheckConstraint(
            _applicability_check("product"),
            name="ck_knowledge_applicability_product",
        ),
        sa.CheckConstraint(
            _applicability_check("region"),
            name="ck_knowledge_applicability_region",
        ),
        sa.CheckConstraint(
            _applicability_check("customer_plan"),
            name="ck_knowledge_applicability_customer_plan",
        ),
        sa.CheckConstraint(
            _applicability_check("cargo_type"),
            name="ck_knowledge_applicability_cargo_type",
        ),
        sa.CheckConstraint(
            _applicability_check("channel"),
            name="ck_knowledge_applicability_channel",
        ),
    )

    op.create_table(
        "knowledge_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_revision", sa.String(length=256), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("system_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("system_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id", "tenant_id"],
            ["knowledge_objects.id", "knowledge_objects.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_versions_object_owner",
        ),
        sa.ForeignKeyConstraint(
            ["applicability_id", "tenant_id"],
            ["knowledge_applicability.id", "knowledge_applicability.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_versions_applicability_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_knowledge_versions_id_tenant"),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "object_id",
            name="uq_knowledge_versions_id_tenant_object",
        ),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "content_digest",
            name="uq_knowledge_versions_id_tenant_digest",
        ),
        sa.CheckConstraint(
            _safe_text_check("source_revision"),
            name="ck_knowledge_versions_source_revision",
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_versions_content_digest",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_knowledge_versions_valid_range",
        ),
        sa.CheckConstraint(
            "system_to IS NULL OR system_to > system_from",
            name="ck_knowledge_versions_system_range",
        ),
        sa.CheckConstraint(_safe_text_check("locale"), name="ck_knowledge_versions_locale"),
    )
    op.create_index(
        "ix_knowledge_versions_tenant_object",
        "knowledge_versions",
        ["tenant_id", "object_id"],
    )
    connection = op.get_bind()
    connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    op.execute(
        sa.text(
            """
            ALTER TABLE "public"."knowledge_versions"
            ADD CONSTRAINT "ex_knowledge_versions_bitemporal_identity"
            EXCLUDE USING gist (
                tenant_id WITH =,
                object_id WITH =,
                applicability_id WITH =,
                locale WITH =,
                tstzrange(valid_from, valid_to, '[)') WITH &&,
                tstzrange(system_from, system_to, '[)') WITH &&
            )
            """
        )
    )

    op.create_table(
        "knowledge_supersessions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "predecessor_version_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "successor_version_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["predecessor_version_id", "tenant_id", "object_id"],
            [
                "knowledge_versions.id",
                "knowledge_versions.tenant_id",
                "knowledge_versions.object_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_supersessions_predecessor_owner",
        ),
        sa.ForeignKeyConstraint(
            ["successor_version_id", "tenant_id", "object_id"],
            [
                "knowledge_versions.id",
                "knowledge_versions.tenant_id",
                "knowledge_versions.object_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_supersessions_successor_owner",
        ),
        sa.CheckConstraint(
            "predecessor_version_id <> successor_version_id",
            name="ck_knowledge_supersessions_distinct_versions",
        ),
        sa.CheckConstraint(_safe_text_check("reason"), name="ck_knowledge_supersessions_reason"),
    )

    op.create_table(
        "knowledge_conflicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fact_key", sa.String(length=256), nullable=False),
        sa.Column("left_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("right_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["left_version_id", "tenant_id"],
            ["knowledge_versions.id", "knowledge_versions.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_conflicts_left_owner",
        ),
        sa.ForeignKeyConstraint(
            ["right_version_id", "tenant_id"],
            ["knowledge_versions.id", "knowledge_versions.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_conflicts_right_owner",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_knowledge_conflicts_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "left_version_id",
            "right_version_id",
            name="uq_knowledge_conflicts_version_pair",
        ),
        sa.CheckConstraint(
            "left_version_id < right_version_id",
            name="ck_knowledge_conflicts_canonical_pair",
        ),
        sa.CheckConstraint(
            "status IN ('unresolved', 'resolved')",
            name="ck_knowledge_conflicts_status",
        ),
        sa.CheckConstraint(_safe_text_check("fact_key"), name="ck_knowledge_conflicts_fact_key"),
        sa.CheckConstraint(_safe_text_check("owner"), name="ck_knowledge_conflicts_owner"),
    )

    op.create_table(
        "knowledge_projection_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_collection", sa.String(length=63), nullable=False),
        sa.Column("manifest_generation", sa.Integer(), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("index_config_digest", sa.String(length=64), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_knowledge_projection_bindings_id_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "manifest_generation",
            name="uq_knowledge_projection_bindings_generation",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "digest",
            name="uq_knowledge_projection_bindings_digest",
        ),
        sa.CheckConstraint(
            "active_collection ~ '^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$'",
            name="ck_knowledge_projection_bindings_collection",
        ),
        sa.CheckConstraint(
            "manifest_generation >= 1",
            name="ck_knowledge_projection_bindings_generation",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_versions) = 'array' AND jsonb_array_length(source_versions) > 0",
            name="ck_knowledge_projection_bindings_sources",
        ),
        sa.CheckConstraint(
            _safe_text_check("embedding_model"),
            name="ck_knowledge_projection_bindings_embedding_model",
        ),
        sa.CheckConstraint(
            "embedding_dimension >= 1",
            name="ck_knowledge_projection_bindings_embedding_dimension",
        ),
        sa.CheckConstraint(
            "index_config_digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_projection_bindings_index_digest",
        ),
        sa.CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_projection_bindings_digest",
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
            CREATE FUNCTION "{_SCHEMA}"."{_VERSION_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            BEGIN
                IF TG_OP = 'UPDATE'
                    AND OLD.system_to IS NULL
                    AND NEW.system_to IS NOT NULL
                    AND NEW.system_to > OLD.system_from
                    AND NEW.id IS NOT DISTINCT FROM OLD.id
                    AND NEW.tenant_id IS NOT DISTINCT FROM OLD.tenant_id
                    AND NEW.object_id IS NOT DISTINCT FROM OLD.object_id
                    AND NEW.applicability_id IS NOT DISTINCT FROM OLD.applicability_id
                    AND NEW.source_revision IS NOT DISTINCT FROM OLD.source_revision
                    AND NEW.content_digest IS NOT DISTINCT FROM OLD.content_digest
                    AND NEW.valid_from IS NOT DISTINCT FROM OLD.valid_from
                    AND NEW.valid_to IS NOT DISTINCT FROM OLD.valid_to
                    AND NEW.system_from IS NOT DISTINCT FROM OLD.system_from
                    AND NEW.locale IS NOT DISTINCT FROM OLD.locale
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'knowledge version permits one system-time close only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION "{_SCHEMA}"."{_CONFLICT_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            DECLARE
                left_logical_key text;
                right_logical_key text;
                left_applicability uuid;
                right_applicability uuid;
                left_authority text;
                right_authority text;
                left_digest text;
                right_digest text;
            BEGIN
                SELECT left_object.logical_key, right_object.logical_key,
                       left_version.applicability_id, right_version.applicability_id,
                       left_object.authority, right_object.authority,
                       left_version.content_digest, right_version.content_digest
                INTO left_logical_key, right_logical_key,
                     left_applicability, right_applicability,
                     left_authority, right_authority, left_digest, right_digest
                FROM "{_SCHEMA}"."knowledge_versions" AS left_version
                JOIN "{_SCHEMA}"."knowledge_objects" AS left_object
                  ON left_object.id = left_version.object_id
                 AND left_object.tenant_id = left_version.tenant_id
                JOIN "{_SCHEMA}"."knowledge_versions" AS right_version
                  ON right_version.id = NEW.right_version_id
                 AND right_version.tenant_id = NEW.tenant_id
                JOIN "{_SCHEMA}"."knowledge_objects" AS right_object
                  ON right_object.id = right_version.object_id
                 AND right_object.tenant_id = right_version.tenant_id
                WHERE left_version.id = NEW.left_version_id
                  AND left_version.tenant_id = NEW.tenant_id;
                IF NOT FOUND THEN
                    RETURN NEW;
                END IF;
                IF left_logical_key IS DISTINCT FROM right_logical_key
                    OR left_applicability IS DISTINCT FROM right_applicability
                    OR left_authority IS NOT DISTINCT FROM right_authority
                    OR left_digest IS NOT DISTINCT FROM right_digest
                THEN
                    RAISE EXCEPTION 'knowledge conflict violates material cross-authority identity'
                        USING ERRCODE = '23514';
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
            CREATE FUNCTION "{_SCHEMA}"."{_PROJECTION_FUNCTION}"()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog
            AS $$
            DECLARE
                source_item jsonb;
                version_text text;
                digest_text text;
                previous_version text := NULL;
            BEGIN
                FOR source_item IN
                    SELECT value
                    FROM jsonb_array_elements(NEW.source_versions) WITH ORDINALITY AS items(value, position)
                    ORDER BY position
                LOOP
                    IF jsonb_typeof(source_item) <> 'array'
                        OR jsonb_array_length(source_item) <> 2
                        OR jsonb_typeof(source_item -> 0) <> 'string'
                        OR jsonb_typeof(source_item -> 1) <> 'string'
                    THEN
                        RAISE EXCEPTION 'projection source identity must be [uuid, digest]'
                            USING ERRCODE = '23514';
                    END IF;
                    version_text := source_item ->> 0;
                    digest_text := source_item ->> 1;
                    IF version_text !~ '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                        OR digest_text !~ '^[0-9a-f]{{64}}$'
                        OR (previous_version IS NOT NULL AND version_text <= previous_version)
                    THEN
                        RAISE EXCEPTION 'projection source identities must be unique and sorted'
                            USING ERRCODE = '23514';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM "{_SCHEMA}"."knowledge_versions"
                        WHERE tenant_id = NEW.tenant_id
                          AND id = version_text::uuid
                          AND content_digest = digest_text
                    ) THEN
                        RAISE EXCEPTION 'projection source version identity is not durable'
                            USING ERRCODE = '23503';
                    END IF;
                    previous_version := version_text;
                END LOOP;
                RETURN NEW;
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
            f'CREATE TRIGGER "trg_knowledge_versions_system_close" '
            f'BEFORE UPDATE OR DELETE ON "{_SCHEMA}"."knowledge_versions" '
            f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_VERSION_FUNCTION}"()'
        )
    )
    op.execute(
        sa.text(
            f'CREATE CONSTRAINT TRIGGER "trg_knowledge_conflicts_validate" '
            f'AFTER INSERT ON "{_SCHEMA}"."knowledge_conflicts" '
            f"DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW "
            f'EXECUTE FUNCTION "{_SCHEMA}"."{_CONFLICT_FUNCTION}"()'
        )
    )
    op.execute(
        sa.text(
            f'CREATE TRIGGER "trg_knowledge_projection_bindings_validate" '
            f'BEFORE INSERT ON "{_SCHEMA}"."knowledge_projection_bindings" '
            f'FOR EACH ROW EXECUTE FUNCTION "{_SCHEMA}"."{_PROJECTION_FUNCTION}"()'
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
            f'DROP TRIGGER "trg_knowledge_projection_bindings_validate" '
            f'ON "{_SCHEMA}"."knowledge_projection_bindings"'
        )
    )
    op.execute(
        sa.text(
            f'DROP TRIGGER "trg_knowledge_conflicts_validate" ON "{_SCHEMA}"."knowledge_conflicts"'
        )
    )
    op.execute(
        sa.text(
            f'DROP TRIGGER "trg_knowledge_versions_system_close" '
            f'ON "{_SCHEMA}"."knowledge_versions"'
        )
    )
    for table_name in reversed(_APPEND_ONLY_TABLES):
        op.execute(
            sa.text(f'DROP TRIGGER "trg_{table_name}_append_only" ON "{_SCHEMA}"."{table_name}"')
        )

    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_PROJECTION_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_CONFLICT_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_VERSION_FUNCTION}"()'))
    op.execute(sa.text(f'DROP FUNCTION "{_SCHEMA}"."{_APPEND_FUNCTION}"()'))

    op.drop_table("knowledge_projection_bindings")
    op.drop_table("knowledge_conflicts")
    op.drop_table("knowledge_supersessions")
    op.drop_index("ix_knowledge_versions_tenant_object", table_name="knowledge_versions")
    op.drop_table("knowledge_versions")
    op.drop_table("knowledge_applicability")
    op.drop_table("knowledge_objects")
