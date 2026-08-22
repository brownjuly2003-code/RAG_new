"""encrypt resolution evidence reference locator

Revision ID: 028
Revises: 027
"""

from __future__ import annotations

import os

import sqlalchemy as sa

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None

_PGCRYPTO_OPTIONS = "cipher-algo=aes256,compress-algo=0"
_SCHEMA = "public"
_TABLE_NAME = "evidence_snapshots"
_COLUMN_NAME = "reference_locator"
_CONSTRAINT_NAME = "ck_evidence_snapshots_protection_profile"
_PROFILE_CHECK = (
    "((reference_storage = 'development_file' AND "
    "(encryption_profile IS NULL OR encryption_profile = 'tenant-envelope-v1')) OR "
    "(reference_storage IN ('postgres_encrypted', 'object_store') AND "
    "encryption_profile IS NOT NULL AND "
    "encryption_profile = 'tenant-envelope-v1'))"
)


def _require_key() -> str:
    key = os.getenv("DB_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("DB_ENCRYPTION_KEY is required for evidence encryption migration")
    return key


def upgrade() -> None:
    connection = op.get_bind()
    key = _require_key()

    connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        _TABLE_NAME,
        _PROFILE_CHECK,
        schema=_SCHEMA,
    )
    connection.execute(
        sa.text(
            f"""
            ALTER TABLE "{_SCHEMA}"."{_TABLE_NAME}"
            ALTER COLUMN "{_COLUMN_NAME}" TYPE BYTEA
            USING pgp_sym_encrypt(
                "{_COLUMN_NAME}", :key, '{_PGCRYPTO_OPTIONS}'
            )
            """
        ),
        {"key": key},
    )


def downgrade() -> None:
    connection = op.get_bind()
    key = _require_key()

    op.drop_constraint(
        _CONSTRAINT_NAME,
        _TABLE_NAME,
        type_="check",
        schema=_SCHEMA,
    )
    connection.execute(
        sa.text(
            f"""
            ALTER TABLE "{_SCHEMA}"."{_TABLE_NAME}"
            ALTER COLUMN "{_COLUMN_NAME}" TYPE VARCHAR(512)
            USING pgp_sym_decrypt("{_COLUMN_NAME}", :key)
            """
        ),
        {"key": key},
    )
