#!/usr/bin/env python3
"""Provision and verify the dedicated Resolution PostgreSQL role boundary."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor
from sqlalchemy.engine import make_url

EXIT_OK = 0
EXIT_OPERATION_FAILED = 1
EXIT_CONTRACT_FAILED = 2

DEFAULT_PORT = 55432
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_RESOLUTION_TABLES = (
    "support_cases",
    "case_events",
    "evidence_snapshots",
    "case_evidence_links",
)
_MIN_SERVER_VERSION_NUM = 160000
_TENANT_POLICY_NAME = "resolution_tenant_isolation"
_TENANT_POLICY_EXPRESSION = (
    "(tenant_id = (NULLIF(current_setting('app.current_tenant_id'::text, true), ''::text))::uuid)"
)
_ROUTING_QUERY_KEYS = frozenset({"host", "port", "service", "servicefile", "target_session_attrs"})

RUNTIME_TABLE_GRANTS = {
    "support_cases": frozenset({"SELECT", "INSERT"}),
    "case_events": frozenset({"SELECT", "INSERT"}),
    "evidence_snapshots": frozenset({"SELECT", "INSERT"}),
    "case_evidence_links": frozenset({"SELECT", "INSERT"}),
}
RUNTIME_COLUMN_GRANTS = {
    "support_cases": frozenset({"status", "version", "updated_at"}),
}
RUNTIME_FUNCTION_GRANTS = frozenset(
    {
        "pgp_sym_encrypt(text,text,text)",
        "pgp_sym_decrypt(bytea,text)",
    }
)


class RoleContractError(RuntimeError):
    """Raised when the target does not match the fail-closed C8 contract."""


@dataclass(frozen=True, slots=True)
class RoleNames:
    database: str = "ragnew_prod"
    schema_owner: str = "ragnew_schema_owner"
    migrator: str = "ragnew_migrator"
    runtime: str = "ragnew_resolution_runtime"


@dataclass(frozen=True, slots=True)
class AclSnapshot:
    """Direct runtime and PUBLIC ACLs that must equal the C8 allowlist."""

    database: frozenset[tuple[str, str]]
    schema: frozenset[tuple[str, str]]
    relations: frozenset[tuple[str, str, str, str]]
    columns: frozenset[tuple[str, str, str, str]]
    functions: frozenset[tuple[str, str, str]]
    defaults: frozenset[tuple[str, str, str, str]]


def _expected_memberships(names: RoleNames) -> set[tuple[str, str, bool, bool, bool]]:
    return {(names.migrator, names.schema_owner, False, False, True)}


def _expected_tenant_policy_rows() -> set[tuple[str, str, str, tuple[str, ...], str, str, str]]:
    return {
        (
            table_name,
            _TENANT_POLICY_NAME,
            "PERMISSIVE",
            ("public",),
            "ALL",
            _TENANT_POLICY_EXPRESSION,
            _TENANT_POLICY_EXPRESSION,
        )
        for table_name in _RESOLUTION_TABLES
    }


def _policy_contract_violations(
    rows: set[tuple[str, str, str, tuple[str, ...], str, str, str]],
) -> list[str]:
    if rows != _expected_tenant_policy_rows():
        return ["Resolution RLS policies differ from the exact tenant contract"]
    return []


def _expected_acl_snapshot(names: RoleNames) -> AclSnapshot:
    return AclSnapshot(
        database=frozenset({(names.runtime, "CONNECT")}),
        schema=frozenset({(names.runtime, "USAGE")}),
        relations=frozenset(
            (names.runtime, "table", table_name, privilege)
            for table_name, privileges in RUNTIME_TABLE_GRANTS.items()
            for privilege in privileges
        ),
        columns=frozenset(
            (names.runtime, table_name, column_name, "UPDATE")
            for table_name, columns in RUNTIME_COLUMN_GRANTS.items()
            for column_name in columns
        ),
        functions=frozenset(
            (names.runtime, function_signature, "EXECUTE")
            for function_signature in RUNTIME_FUNCTION_GRANTS
        ),
        defaults=frozenset(),
    )


def _acl_contract_violations(snapshot: AclSnapshot, names: RoleNames) -> list[str]:
    expected = _expected_acl_snapshot(names)
    violations: list[str] = []
    for field_name, message in (
        ("database", "runtime/PUBLIC database ACLs differ from CONNECT-only"),
        ("schema", "runtime/PUBLIC schema ACLs differ from USAGE-only"),
        ("relations", "runtime/PUBLIC relation ACLs differ from the minimum matrix"),
        ("columns", "runtime/PUBLIC column ACLs differ from the CAS-only matrix"),
        ("functions", "runtime/PUBLIC function ACLs differ from the minimum matrix"),
        ("defaults", "schema-owner default ACLs expose future objects"),
    ):
        if getattr(snapshot, field_name) != getattr(expected, field_name):
            violations.append(message)
    return violations


def validate_role_names(names: RoleNames) -> None:
    values = {
        "database": names.database,
        "schema owner": names.schema_owner,
        "migrator": names.migrator,
        "runtime": names.runtime,
    }
    for label, value in values.items():
        if _IDENTIFIER_PATTERN.fullmatch(value) is None:
            raise ValueError(f"{label} identifier is invalid")
    if len({names.schema_owner, names.migrator, names.runtime}) != 3:
        raise ValueError("PostgreSQL role identifiers must be distinct")


def validate_password(password: str, *, label: str = "role") -> None:
    if len(password) < 24:
        raise ValueError(f"{label} password must contain at least 24 characters")
    if len(password) > 512 or any(character in password for character in "\r\n\x00"):
        raise ValueError(f"{label} password must be a bounded single-line value")


def _postgres_dsn(raw_url: str, *, database: str) -> str:
    if not raw_url.strip():
        raise ValueError("an admin PostgreSQL URL is required")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("the admin URL must use PostgreSQL")
    return url.set(drivername="postgresql", database=database).render_as_string(hide_password=False)


def _connection_endpoint(raw_url: str, *, label: str) -> tuple[str, int]:
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RoleContractError(f"{label} URL must use PostgreSQL")
    query_keys = {str(key).lower() for key in url.query}
    if query_keys & _ROUTING_QUERY_KEYS:
        raise RoleContractError(f"{label} URL contains alternative routing parameters")
    host = (url.host or "").strip().lower()
    if not host or "," in host:
        raise RoleContractError(f"{label} URL must contain one explicit endpoint")
    return host, int(url.port or 5432)


def _validate_runtime_endpoint(
    admin_url: str,
    runtime_url: str,
    names: RoleNames,
) -> None:
    parsed_runtime_url = make_url(runtime_url)
    if (
        parsed_runtime_url.database != names.database
        or parsed_runtime_url.username != names.runtime
    ):
        raise RoleContractError("runtime URL identity does not match the C8 role contract")
    admin_endpoint = _connection_endpoint(admin_url, label="admin")
    runtime_endpoint = _connection_endpoint(runtime_url, label="runtime")
    if admin_endpoint != runtime_endpoint:
        raise RoleContractError("admin and runtime URLs do not share one endpoint")


@contextmanager
def _connect(
    admin_url: str,
    *,
    database: str,
    autocommit: bool = False,
) -> Iterator[PgConnection]:
    connection = psycopg2.connect(_postgres_dsn(admin_url, database=database))
    connection.autocommit = autocommit
    try:
        yield connection
    finally:
        connection.close()


def _target_facts(cursor: PgCursor[Any], *, include_data_directory: bool) -> dict[str, str]:
    cursor.execute("SHOW port")
    port = str(cursor.fetchone()[0])
    cursor.execute("SHOW listen_addresses")
    listen_addresses = str(cursor.fetchone()[0])
    data_directory = ""
    if include_data_directory:
        cursor.execute("SHOW data_directory")
        data_directory = str(cursor.fetchone()[0])
    cursor.execute("SHOW server_version")
    server_version = str(cursor.fetchone()[0])
    cursor.execute("SHOW server_version_num")
    server_version_num = str(cursor.fetchone()[0])
    return {
        "port": port,
        "listen_addresses": listen_addresses,
        "data_directory": data_directory,
        "server_version": server_version,
        "server_version_num": server_version_num,
    }


def _require_target(
    cursor: PgCursor[Any],
    *,
    expected_port: int,
    expected_data_directory: str,
) -> dict[str, str]:
    facts = _target_facts(
        cursor,
        include_data_directory=bool(expected_data_directory),
    )
    if facts["port"] != str(expected_port):
        raise RoleContractError(
            f"target port mismatch: expected {expected_port}, got {facts['port']}"
        )
    listeners = {
        value.strip().lower() for value in facts["listen_addresses"].split(",") if value.strip()
    }
    if not listeners or listeners - {"127.0.0.1", "localhost", "::1"}:
        raise RoleContractError("target PostgreSQL must listen only on loopback")
    if expected_data_directory and facts["data_directory"] != expected_data_directory:
        raise RoleContractError("target PostgreSQL data directory does not match the guard")
    if int(facts["server_version_num"]) < _MIN_SERVER_VERSION_NUM:
        raise RoleContractError("target PostgreSQL must be version 16 or newer")
    return facts


def _role_exists(cursor: PgCursor[Any], role_name: str) -> bool:
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (role_name,))
    return bool(cursor.fetchone()[0])


def _ensure_role(
    cursor: PgCursor[Any],
    role_name: str,
    *,
    login: bool,
    password: str | None = None,
) -> None:
    attributes = sql.SQL("LOGIN" if login else "NOLOGIN") + sql.SQL(
        " NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
    )
    command = "ALTER ROLE" if _role_exists(cursor, role_name) else "CREATE ROLE"
    statement = sql.SQL("{} {} ").format(sql.SQL(command), sql.Identifier(role_name)) + attributes
    parameters: tuple[str, ...] = ()
    if password is not None:
        statement += sql.SQL(" PASSWORD %s")
        parameters = (password,)
    cursor.execute(statement, parameters)
    cursor.execute(sql.SQL("ALTER ROLE {} RESET ALL").format(sql.Identifier(role_name)))


def _reconcile_memberships(cursor: PgCursor[Any], names: RoleNames) -> None:
    managed_roles = [names.schema_owner, names.migrator, names.runtime]
    cursor.execute(
        "SELECT member.rolname, granted.rolname, memberships.admin_option, "
        "memberships.inherit_option, memberships.set_option "
        "FROM pg_auth_members AS memberships "
        "JOIN pg_roles AS member ON member.oid = memberships.member "
        "JOIN pg_roles AS granted ON granted.oid = memberships.roleid "
        "WHERE member.rolname = ANY(%s) OR granted.rolname = ANY(%s)",
        (managed_roles, managed_roles),
    )
    memberships = cursor.fetchall()
    if any(
        member_name not in managed_roles
        for member_name, granted_name, _admin, _inherit, _set in memberships
        if granted_name in managed_roles
    ):
        raise RoleContractError("a foreign role is a member of a managed C8 role")
    for member_name, granted_name, _admin, _inherit, _set in memberships:
        if (member_name, granted_name) == (names.migrator, names.schema_owner):
            continue
        cursor.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(granted_name),
                sql.Identifier(member_name),
            )
        )
    cursor.execute(
        sql.SQL("GRANT {} TO {} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE").format(
            sql.Identifier(names.schema_owner),
            sql.Identifier(names.migrator),
        )
    )


def bootstrap(
    admin_url: str,
    names: RoleNames,
    *,
    migrator_password: str,
    runtime_password: str,
    expected_port: int,
    expected_data_directory: str,
) -> None:
    validate_role_names(names)
    validate_password(migrator_password, label="migrator")
    validate_password(runtime_password, label="runtime")

    with _connect(admin_url, database="postgres", autocommit=True) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            cursor.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (names.database,),
            )
            owner_row = cursor.fetchone()
            if owner_row is not None and owner_row[0] != names.schema_owner:
                raise RoleContractError("target database exists with an unexpected owner")

            _ensure_role(cursor, names.schema_owner, login=False)
            _ensure_role(
                cursor,
                names.migrator,
                login=True,
                password=migrator_password,
            )
            _ensure_role(
                cursor,
                names.runtime,
                login=False,
                password=runtime_password,
            )
            _reconcile_memberships(cursor, names)

            if owner_row is None:
                cursor.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0"
                    ).format(
                        sql.Identifier(names.database),
                        sql.Identifier(names.schema_owner),
                    )
                )

            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(names.database)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(
                    sql.Identifier(names.database),
                    sql.Identifier(names.runtime),
                )
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(names.database),
                    sql.Identifier(names.migrator),
                )
            )
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND usename = %s AND pid <> pg_backend_pid()",
                (names.database, names.runtime),
            )

    with _connect(admin_url, database=names.database, autocommit=True) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            cursor.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                    sql.Identifier(names.schema_owner)
                )
            )
            cursor.execute(
                sql.SQL("ALTER DATABASE {} RESET ALL").format(sql.Identifier(names.database))
            )
            for role_name in (names.schema_owner, names.migrator, names.runtime):
                cursor.execute(
                    sql.SQL("ALTER ROLE {} IN DATABASE {} RESET ALL").format(
                        sql.Identifier(role_name),
                        sql.Identifier(names.database),
                    )
                )
            cursor.execute("REVOKE ALL PRIVILEGES ON SCHEMA public FROM PUBLIC")
            for scope in (sql.SQL(""), sql.SQL(" IN SCHEMA public")):
                for object_kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                    for grantee in (sql.SQL("PUBLIC"), sql.Identifier(names.runtime)):
                        cursor.execute(
                            sql.SQL(
                                "ALTER DEFAULT PRIVILEGES FOR ROLE {}{} "
                                "REVOKE ALL PRIVILEGES ON {} FROM {}"
                            ).format(
                                sql.Identifier(names.schema_owner),
                                scope,
                                sql.SQL(object_kind),
                                grantee,
                            )
                        )


def _require_resolution_tables(cursor: PgCursor[Any], names: RoleNames) -> None:
    cursor.execute(
        "SELECT tablename, tableowner FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename = ANY(%s)",
        (list(_RESOLUTION_TABLES),),
    )
    actual = {table_name: owner_name for table_name, owner_name in cursor.fetchall()}
    missing = sorted(set(_RESOLUTION_TABLES) - set(actual))
    if missing:
        raise RoleContractError(f"Resolution tables are missing: {', '.join(missing)}")
    unexpected_owners = sorted(
        table_name for table_name, owner_name in actual.items() if owner_name != names.schema_owner
    )
    if unexpected_owners:
        raise RoleContractError(
            "Resolution tables have unexpected owners: " + ", ".join(unexpected_owners)
        )


def _disable_runtime(cursor: PgCursor[Any], names: RoleNames) -> None:
    cursor.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(sql.Identifier(names.runtime)))
    cursor.execute(
        sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(
            sql.Identifier(names.database),
            sql.Identifier(names.runtime),
        )
    )
    cursor.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND usename = %s AND pid <> pg_backend_pid()",
        (names.database, names.runtime),
    )


def _revoke_runtime_column_acl(cursor: PgCursor[Any], names: RoleNames) -> None:
    cursor.execute(
        "SELECT table_name, privilege_type, array_agg(column_name ORDER BY column_name) "
        "FROM information_schema.column_privileges "
        "WHERE grantee = %s AND table_schema = 'public' "
        "GROUP BY table_name, privilege_type",
        (names.runtime,),
    )
    for table_name, privilege, columns in cursor.fetchall():
        if privilege not in {"SELECT", "INSERT", "UPDATE", "REFERENCES"}:
            raise RoleContractError("unexpected runtime column privilege type")
        cursor.execute(
            sql.SQL("REVOKE {} ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(str(privilege)),
                sql.SQL(", ").join(sql.Identifier(str(column)) for column in columns),
                sql.Identifier(str(table_name)),
                sql.Identifier(names.runtime),
            )
        )


def apply_runtime_grants(
    admin_url: str,
    names: RoleNames,
    *,
    expected_port: int,
    expected_data_directory: str,
) -> None:
    validate_role_names(names)
    with _connect(admin_url, database=names.database, autocommit=True) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            _require_resolution_tables(cursor, names)

            _disable_runtime(cursor, names)
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(names.database)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(
                    sql.Identifier(names.database),
                    sql.Identifier(names.runtime),
                )
            )
            cursor.execute("REVOKE ALL PRIVILEGES ON SCHEMA public FROM PUBLIC")
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            cursor.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC")
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            _revoke_runtime_column_acl(cursor, names)

            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(names.runtime))
            )
            for table_name, privileges in RUNTIME_TABLE_GRANTS.items():
                cursor.execute(
                    sql.SQL("GRANT {} ON TABLE public.{} TO {}").format(
                        sql.SQL(", ").join(sql.SQL(privilege) for privilege in sorted(privileges)),
                        sql.Identifier(table_name),
                        sql.Identifier(names.runtime),
                    )
                )
            for table_name, columns in RUNTIME_COLUMN_GRANTS.items():
                cursor.execute(
                    sql.SQL("GRANT UPDATE ({}) ON TABLE public.{} TO {}").format(
                        sql.SQL(", ").join(sql.Identifier(column) for column in sorted(columns)),
                        sql.Identifier(table_name),
                        sql.Identifier(names.runtime),
                    )
                )
            cursor.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.pgp_sym_encrypt(text, text, text) TO {}"
                ).format(sql.Identifier(names.runtime))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.pgp_sym_decrypt(bytea, text) TO {}"
                ).format(sql.Identifier(names.runtime))
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
                    sql.Identifier(names.database),
                    sql.Identifier(names.migrator),
                    sql.Identifier(names.runtime),
                )
            )
            cursor.execute(sql.SQL("ALTER ROLE {} LOGIN").format(sql.Identifier(names.runtime)))


def revoke_runtime_access(
    admin_url: str,
    names: RoleNames,
    *,
    expected_port: int,
    expected_data_directory: str,
) -> None:
    validate_role_names(names)
    with _connect(admin_url, database="postgres", autocommit=True) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            _disable_runtime(cursor, names)

    with _connect(admin_url, database=names.database, autocommit=True) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM {}").format(
                    sql.Identifier(names.runtime)
                )
            )
            _revoke_runtime_column_acl(cursor, names)


def _expect_sqlstate(
    cursor: PgCursor[Any],
    statement: str,
    parameters: tuple[Any, ...],
    *,
    expected: str,
    savepoint: str,
) -> None:
    cursor.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(savepoint)))
    try:
        cursor.execute(statement, parameters)
    except psycopg2.Error as exc:
        cursor.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint)))
        cursor.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(savepoint)))
        if exc.pgcode != expected:
            raise RoleContractError(
                f"expected SQLSTATE {expected}, got {exc.pgcode or '<none>'}"
            ) from exc
        return
    cursor.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(savepoint)))
    raise RoleContractError(f"statement unexpectedly succeeded; expected SQLSTATE {expected}")


def smoke_runtime_contract(
    admin_url: str,
    runtime_url: str,
    names: RoleNames,
    *,
    encryption_key: str,
    expected_port: int,
    expected_data_directory: str,
) -> None:
    validate_role_names(names)
    validate_password(encryption_key, label="encryption key")
    _validate_runtime_endpoint(admin_url, runtime_url, names)

    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    case_id = str(uuid4())
    event_id = str(uuid4())
    evidence_id = str(uuid4())
    link_id = str(uuid4())
    correlation_id = str(uuid4())
    command_id = str(uuid4())
    actor_id = str(uuid4())
    now = datetime.now(timezone.utc)

    with _connect(admin_url, database=names.database) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )

    with _connect(runtime_url, database=names.database) as connection:
        try:
            with connection.cursor() as cursor:
                _require_target(
                    cursor,
                    expected_port=expected_port,
                    expected_data_directory="",
                )
                cursor.execute(
                    "SELECT session_user, current_user, rolsuper, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user"
                )
                identity = cursor.fetchone()
                if identity != (names.runtime, names.runtime, False, False):
                    raise RoleContractError("runtime is not a direct non-bypass login")

                for table_name in _RESOLUTION_TABLES:
                    cursor.execute(
                        sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table_name))
                    )
                    if int(cursor.fetchone()[0]) != 0:
                        raise RoleContractError(
                            "runtime default-deny failed without tenant context"
                        )

                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (tenant_a,),
                )
                cursor.execute(
                    "INSERT INTO public.support_cases "
                    "(id, tenant_id, contract_id, contract_version, contract_digest, "
                    "correlation_id, status, version, opened_at, effective_at, updated_at) "
                    "VALUES (%s::uuid, %s::uuid, 'shipment-status', '0.1.0', %s, "
                    "%s::uuid, 'open', 1, %s, %s, %s)",
                    (case_id, tenant_a, "a" * 64, correlation_id, now, now, now),
                )
                cursor.execute(
                    "INSERT INTO public.case_events "
                    "(id, tenant_id, case_id, sequence, case_version, event_type, command_id, "
                    "actor_id, correlation_id, from_status, to_status, reason_code, "
                    "occurred_at, recorded_at) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, 1, 1, 'opened', %s::uuid, "
                    "%s::uuid, %s::uuid, NULL, 'open', 'C8_SMOKE', %s, %s)",
                    (
                        event_id,
                        tenant_a,
                        case_id,
                        command_id,
                        actor_id,
                        correlation_id,
                        now,
                        now,
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.evidence_snapshots "
                    "(id, tenant_id, logical_key, source_type, source_id, source_version, "
                    "content_digest, valid_from, valid_to, recorded_at, authority, "
                    "applicability_key, visibility, reference_storage, reference_locator, "
                    "encryption_profile, redaction_profile, retention_class) "
                    "VALUES (%s::uuid, %s::uuid, 'shipment', 'database', 'smoke', '1', %s, "
                    "%s, NULL, %s, 'carrier', 'default', 'support_only', "
                    "'postgres_encrypted', "
                    "pgp_sym_encrypt('c8-smoke-locator', %s, "
                    "'cipher-algo=aes256,compress-algo=0'), "
                    "'tenant-envelope-v1', 'customer-safe-v1', 'support-case')",
                    (evidence_id, tenant_a, "b" * 64, now, now, encryption_key),
                )
                cursor.execute(
                    "INSERT INTO public.case_evidence_links "
                    "(id, tenant_id, case_id, case_version, evidence_id, requirement_id, "
                    "purpose, gathered_at, freshness) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, 1, %s::uuid, "
                    "'shipment_status', 'fact', %s, 'current')",
                    (link_id, tenant_a, case_id, evidence_id, now),
                )
                cursor.execute(
                    "SELECT pgp_sym_decrypt(reference_locator, %s) "
                    "FROM public.evidence_snapshots WHERE id = %s::uuid",
                    (encryption_key, evidence_id),
                )
                if cursor.fetchone()[0] != "c8-smoke-locator":
                    raise RoleContractError("runtime pgcrypto round trip failed")

                cursor.execute(
                    "UPDATE public.support_cases SET status = 'routed', version = 2, "
                    "updated_at = %s WHERE id = %s::uuid AND version = 1",
                    (now, case_id),
                )
                if cursor.rowcount != 1:
                    raise RoleContractError("runtime CAS update failed")

                smoke_rows = {
                    "support_cases": case_id,
                    "case_events": event_id,
                    "evidence_snapshots": evidence_id,
                    "case_evidence_links": link_id,
                }
                for tenant_context in ("", tenant_b):
                    cursor.execute(
                        "SELECT set_config('app.current_tenant_id', %s, true)",
                        (tenant_context,),
                    )
                    for table_name, row_id in smoke_rows.items():
                        cursor.execute(
                            sql.SQL("SELECT count(*) FROM public.{} WHERE id = %s::uuid").format(
                                sql.Identifier(table_name)
                            ),
                            (row_id,),
                        )
                        if int(cursor.fetchone()[0]) != 0:
                            raise RoleContractError(
                                "runtime exposed tenant rows outside their tenant context"
                            )
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (tenant_a,),
                )

                _expect_sqlstate(
                    cursor,
                    "UPDATE public.support_cases SET contract_id = contract_id WHERE id = %s::uuid",
                    (case_id,),
                    expected="42501",
                    savepoint="c8_forbidden_column",
                )
                _expect_sqlstate(
                    cursor,
                    "DELETE FROM public.case_events WHERE id = %s::uuid",
                    (event_id,),
                    expected="42501",
                    savepoint="c8_forbidden_delete",
                )
                _expect_sqlstate(
                    cursor,
                    "INSERT INTO public.support_cases "
                    "(id, tenant_id, contract_id, contract_version, contract_digest, "
                    "correlation_id, status, version, opened_at, effective_at, updated_at) "
                    "VALUES (%s::uuid, %s::uuid, 'shipment-status', '0.1.0', %s, "
                    "%s::uuid, 'open', 1, %s, %s, %s)",
                    (
                        str(uuid4()),
                        tenant_b,
                        "c" * 64,
                        str(uuid4()),
                        now,
                        now,
                        now,
                    ),
                    expected="42501",
                    savepoint="c8_cross_tenant",
                )
        finally:
            connection.rollback()

    owner_case_id = str(uuid4())
    owner_event_id = str(uuid4())
    with _connect(admin_url, database=names.database) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(names.schema_owner))
                )
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (tenant_a,),
                )
                cursor.execute(
                    "INSERT INTO public.support_cases "
                    "(id, tenant_id, contract_id, contract_version, contract_digest, "
                    "correlation_id, status, version, opened_at, effective_at, updated_at) "
                    "VALUES (%s::uuid, %s::uuid, 'shipment-status', '0.1.0', %s, "
                    "%s::uuid, 'open', 1, %s, %s, %s)",
                    (
                        owner_case_id,
                        tenant_a,
                        "d" * 64,
                        str(uuid4()),
                        now,
                        now,
                        now,
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.case_events "
                    "(id, tenant_id, case_id, sequence, case_version, event_type, command_id, "
                    "actor_id, correlation_id, from_status, to_status, reason_code, "
                    "occurred_at, recorded_at) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, 1, 1, 'opened', %s::uuid, "
                    "%s::uuid, %s::uuid, NULL, 'open', 'C8_OWNER_SMOKE', %s, %s)",
                    (
                        owner_event_id,
                        tenant_a,
                        owner_case_id,
                        str(uuid4()),
                        str(uuid4()),
                        str(uuid4()),
                        now,
                        now,
                    ),
                )
                _expect_sqlstate(
                    cursor,
                    "UPDATE public.case_events SET tenant_id = tenant_id WHERE id = %s::uuid",
                    (owner_event_id,),
                    expected="55000",
                    savepoint="c8_append_guard",
                )
        finally:
            connection.rollback()

    with _connect(admin_url, database=names.database) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.support_cases WHERE id = ANY(%s::uuid[])",
                ([case_id, owner_case_id],),
            )
            if int(cursor.fetchone()[0]) != 0:
                raise RoleContractError("C8 smoke rows were not rolled back")


def _membership_pairs(
    cursor: PgCursor[Any],
    names: RoleNames,
) -> set[tuple[str, str, bool, bool, bool]]:
    managed_roles = [names.schema_owner, names.migrator, names.runtime]
    cursor.execute(
        "SELECT member.rolname, granted.rolname, memberships.admin_option, "
        "memberships.inherit_option, memberships.set_option "
        "FROM pg_auth_members AS memberships "
        "JOIN pg_roles AS member ON member.oid = memberships.member "
        "JOIN pg_roles AS granted ON granted.oid = memberships.roleid "
        "WHERE member.rolname = ANY(%s) OR granted.rolname = ANY(%s)",
        (managed_roles, managed_roles),
    )
    return {
        (str(member), str(granted), bool(admin), bool(inherit), bool(can_set))
        for member, granted, admin, inherit, can_set in cursor.fetchall()
    }


def _collect_acl_snapshot(cursor: PgCursor[Any], names: RoleNames) -> AclSnapshot:
    cursor.execute(
        "SELECT CASE acl.grantee WHEN 0 THEN 'PUBLIC' "
        "ELSE pg_get_userbyid(acl.grantee) END, acl.privilege_type "
        "FROM pg_database AS databases "
        "CROSS JOIN LATERAL aclexplode(COALESCE(databases.datacl, "
        "acldefault('d', databases.datdba))) AS acl "
        "WHERE databases.datname = %s AND (acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s))",
        (names.database, names.runtime),
    )
    database = frozenset((str(grantee), str(privilege)) for grantee, privilege in cursor)

    cursor.execute(
        "SELECT CASE acl.grantee WHEN 0 THEN 'PUBLIC' "
        "ELSE pg_get_userbyid(acl.grantee) END, acl.privilege_type "
        "FROM pg_namespace AS schemas "
        "CROSS JOIN LATERAL aclexplode(COALESCE(schemas.nspacl, "
        "acldefault('n', schemas.nspowner))) AS acl "
        "WHERE schemas.nspname = 'public' AND (acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s))",
        (names.runtime,),
    )
    schema = frozenset((str(grantee), str(privilege)) for grantee, privilege in cursor)

    cursor.execute(
        "SELECT CASE acl.grantee WHEN 0 THEN 'PUBLIC' "
        "ELSE pg_get_userbyid(acl.grantee) END, "
        "CASE WHEN relations.relkind = 'S' THEN 'sequence' ELSE 'table' END, "
        "relations.relname, acl.privilege_type "
        "FROM pg_class AS relations "
        "JOIN pg_namespace AS schemas ON schemas.oid = relations.relnamespace "
        "CROSS JOIN LATERAL aclexplode(COALESCE(relations.relacl, "
        "CASE WHEN relations.relkind = 'S' "
        "THEN acldefault('S', relations.relowner) "
        "ELSE acldefault('r', relations.relowner) END)) AS acl "
        "WHERE schemas.nspname = 'public' "
        "AND relations.relkind IN ('r', 'p', 'v', 'm', 'S', 'f') "
        "AND (acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s))",
        (names.runtime,),
    )
    relations = frozenset(
        (str(grantee), str(kind), str(name), str(privilege))
        for grantee, kind, name, privilege in cursor
    )

    cursor.execute(
        "SELECT CASE acl.grantee WHEN 0 THEN 'PUBLIC' "
        "ELSE pg_get_userbyid(acl.grantee) END, relations.relname, "
        "attributes.attname, acl.privilege_type "
        "FROM pg_attribute AS attributes "
        "JOIN pg_class AS relations ON relations.oid = attributes.attrelid "
        "JOIN pg_namespace AS schemas ON schemas.oid = relations.relnamespace "
        "CROSS JOIN LATERAL aclexplode(attributes.attacl) AS acl "
        "WHERE schemas.nspname = 'public' AND attributes.attnum > 0 "
        "AND NOT attributes.attisdropped AND attributes.attacl IS NOT NULL "
        "AND (acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s))",
        (names.runtime,),
    )
    columns = frozenset(
        (str(grantee), str(table), str(column), str(privilege))
        for grantee, table, column, privilege in cursor
    )

    cursor.execute(
        "SELECT CASE acl.grantee WHEN 0 THEN 'PUBLIC' "
        "ELSE pg_get_userbyid(acl.grantee) END, functions.proname || '(' || "
        "replace(pg_get_function_identity_arguments(functions.oid), ', ', ',') || ')', "
        "acl.privilege_type "
        "FROM pg_proc AS functions "
        "JOIN pg_namespace AS schemas ON schemas.oid = functions.pronamespace "
        "CROSS JOIN LATERAL aclexplode(COALESCE(functions.proacl, "
        "acldefault('f', functions.proowner))) AS acl "
        "WHERE schemas.nspname = 'public' AND (acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s))",
        (names.runtime,),
    )
    functions = frozenset(
        (str(grantee), str(signature), str(privilege)) for grantee, signature, privilege in cursor
    )

    cursor.execute(
        "WITH owner_role AS (SELECT oid FROM pg_roles WHERE rolname = %s), "
        "object_kinds(objtype) AS (VALUES ('r'::\"char\"), ('S'::\"char\"), "
        "('f'::\"char\")) "
        "SELECT 'global', object_kinds.objtype::text, "
        "CASE acl.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(acl.grantee) END, "
        "acl.privilege_type FROM owner_role CROSS JOIN object_kinds "
        "LEFT JOIN pg_default_acl AS defaults ON defaults.defaclrole = owner_role.oid "
        "AND defaults.defaclnamespace = 0 "
        "AND defaults.defaclobjtype = object_kinds.objtype "
        "CROSS JOIN LATERAL aclexplode(COALESCE(defaults.defaclacl, "
        "acldefault(object_kinds.objtype, owner_role.oid))) AS acl "
        "WHERE acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s)",
        (names.schema_owner, names.runtime),
    )
    defaults = {
        (str(scope), str(kind), str(grantee), str(privilege))
        for scope, kind, grantee, privilege in cursor
    }
    cursor.execute(
        "SELECT 'public', defaults.defaclobjtype::text, "
        "CASE acl.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(acl.grantee) END, "
        "acl.privilege_type FROM pg_default_acl AS defaults "
        "JOIN pg_roles AS owner_role ON owner_role.oid = defaults.defaclrole "
        "JOIN pg_namespace AS schemas ON schemas.oid = defaults.defaclnamespace "
        "CROSS JOIN LATERAL aclexplode(defaults.defaclacl) AS acl "
        "WHERE owner_role.rolname = %s AND schemas.nspname = 'public' "
        "AND (acl.grantee = 0 OR acl.grantee = "
        "(SELECT oid FROM pg_roles WHERE rolname = %s))",
        (names.schema_owner, names.runtime),
    )
    defaults.update(
        (str(scope), str(kind), str(grantee), str(privilege))
        for scope, kind, grantee, privilege in cursor
    )

    return AclSnapshot(
        database=database,
        schema=schema,
        relations=relations,
        columns=columns,
        functions=functions,
        defaults=frozenset(defaults),
    )


def verify_contract(
    admin_url: str,
    names: RoleNames,
    *,
    expected_port: int,
    expected_data_directory: str,
) -> list[str]:
    validate_role_names(names)
    violations: list[str] = []

    with _connect(admin_url, database=names.database) as connection:
        with connection.cursor() as cursor:
            _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            cursor.execute(
                "SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, "
                "rolcanlogin, rolreplication, rolbypassrls FROM pg_roles "
                "WHERE rolname = ANY(%s)",
                ([names.schema_owner, names.migrator, names.runtime],),
            )
            actual_roles = {str(row[0]): tuple(bool(value) for value in row[1:]) for row in cursor}
            expected_roles = {
                names.schema_owner: (False, False, False, False, False, False, False),
                names.migrator: (False, False, False, False, True, False, False),
                names.runtime: (False, False, False, False, True, False, False),
            }
            if actual_roles != expected_roles:
                violations.append("role attributes differ from the C8 contract")

            cursor.execute(
                "SELECT rolname, rolconfig FROM pg_roles WHERE rolname = ANY(%s)",
                ([names.schema_owner, names.migrator, names.runtime],),
            )
            if any(role_config for _role_name, role_config in cursor.fetchall()):
                violations.append("managed roles retain unexpected role settings")

            memberships = _membership_pairs(cursor, names)
            expected_memberships = _expected_memberships(names)
            if memberships != expected_memberships:
                violations.append("role memberships differ from the C8 contract")

            cursor.execute(
                "SELECT count(*) FROM pg_db_role_setting AS settings "
                "LEFT JOIN pg_roles AS roles ON roles.oid = settings.setrole "
                "LEFT JOIN pg_database AS databases ON databases.oid = settings.setdatabase "
                "WHERE (roles.rolname = ANY(%s) AND "
                "(settings.setdatabase = 0 OR databases.datname = %s)) "
                "OR (settings.setrole = 0 AND databases.datname = %s)",
                (
                    [names.schema_owner, names.migrator, names.runtime],
                    names.database,
                    names.database,
                ),
            )
            if int(cursor.fetchone()[0]) != 0:
                violations.append("managed role/database settings are not empty")

            cursor.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (names.database,),
            )
            database_owner = cursor.fetchone()
            if database_owner is None or database_owner[0] != names.schema_owner:
                violations.append("target database is not owned by the schema owner")

            cursor.execute(
                "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'public'",
            )
            schema_row = cursor.fetchone()
            if schema_row is None or schema_row[0] != names.schema_owner:
                violations.append("public schema ownership is invalid")

            cursor.execute(
                "SELECT tablename, tableowner FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = ANY(%s)",
                (list(_RESOLUTION_TABLES),),
            )
            table_owners = {str(table): str(owner) for table, owner in cursor.fetchall()}
            if table_owners != {table: names.schema_owner for table in _RESOLUTION_TABLES}:
                violations.append("Resolution table ownership is invalid")

            cursor.execute(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace "
                "WHERE nspname = 'public' AND relname = ANY(%s)",
                (list(_RESOLUTION_TABLES),),
            )
            rls_state = {
                str(table): (bool(enabled), bool(forced))
                for table, enabled, forced in cursor.fetchall()
            }
            if rls_state != {table: (True, True) for table in _RESOLUTION_TABLES}:
                violations.append("Resolution RLS is not enabled and forced on every table")

            cursor.execute(
                "SELECT tablename, policyname, permissive, roles, cmd, qual, with_check "
                "FROM pg_policies WHERE schemaname = 'public' AND tablename = ANY(%s)",
                (list(_RESOLUTION_TABLES),),
            )
            policy_rows = {
                (
                    str(table_name),
                    str(policy_name),
                    str(permissive),
                    tuple(str(role) for role in roles),
                    str(command),
                    str(qualifier or ""),
                    str(check_expression or ""),
                )
                for (
                    table_name,
                    policy_name,
                    permissive,
                    roles,
                    command,
                    qualifier,
                    check_expression,
                ) in cursor.fetchall()
            }
            violations.extend(_policy_contract_violations(policy_rows))
            violations.extend(_acl_contract_violations(_collect_acl_snapshot(cursor, names), names))

            cursor.execute(
                "SELECT count(*) FROM pg_class JOIN pg_roles ON pg_roles.oid = pg_class.relowner "
                "WHERE pg_roles.rolname = %s",
                (names.runtime,),
            )
            if int(cursor.fetchone()[0]) != 0:
                violations.append("runtime owns relations")

    return violations


def inventory(
    admin_url: str,
    names: RoleNames,
    *,
    expected_port: int,
    expected_data_directory: str,
) -> dict[str, Any]:
    validate_role_names(names)
    with _connect(admin_url, database="postgres") as connection:
        with connection.cursor() as cursor:
            facts = _require_target(
                cursor,
                expected_port=expected_port,
                expected_data_directory=expected_data_directory,
            )
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s) ORDER BY rolname",
                ([names.schema_owner, names.migrator, names.runtime],),
            )
            roles = [str(row[0]) for row in cursor.fetchall()]
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = %s)",
                (names.database,),
            )
            database_exists = bool(cursor.fetchone()[0])
    return {
        "database_exists": database_exists,
        "data_directory_matches": (
            not expected_data_directory or facts["data_directory"] == expected_data_directory
        ),
        "listen_addresses": facts["listen_addresses"],
        "port": int(facts["port"]),
        "roles": roles,
        "server_version": facts["server_version"],
    }


def _role_names_from_args(args: argparse.Namespace) -> RoleNames:
    return RoleNames(
        database=args.database,
        schema_owner=args.schema_owner_role,
        migrator=args.migrator_role,
        runtime=args.runtime_role,
    )


def _add_common_arguments(parser: argparse.ArgumentParser, *, mutating: bool) -> None:
    parser.add_argument(
        "--admin-url",
        default=os.environ.get("RESOLUTION_ADMIN_DATABASE_URL", ""),
    )
    parser.add_argument("--database", default="ragnew_prod")
    parser.add_argument("--schema-owner-role", default="ragnew_schema_owner")
    parser.add_argument("--migrator-role", default="ragnew_migrator")
    parser.add_argument("--runtime-role", default="ragnew_resolution_runtime")
    parser.add_argument(
        "--expected-port",
        type=int,
        default=int(os.environ.get("RAG_NEW_POSTGRES_PORT", str(DEFAULT_PORT))),
    )
    parser.add_argument(
        "--expected-data-directory",
        default=os.environ.get("RAG_NEW_POSTGRES_DATA_DIR", ""),
    )
    if mutating:
        parser.add_argument("--confirm-target", default="")


def _require_mutation_confirmation(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    names: RoleNames,
) -> None:
    if not args.expected_data_directory:
        parser.error("--expected-data-directory is required for mutating operations")
    expected_confirmation = f"{names.database}@{args.expected_port}"
    if args.confirm_target != expected_confirmation:
        parser.error(f"--confirm-target must equal {expected_confirmation}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inventory", "verify"):
        _add_common_arguments(subparsers.add_parser(command), mutating=False)
    for command in ("bootstrap", "grant", "revoke-runtime", "smoke"):
        _add_common_arguments(subparsers.add_parser(command), mutating=True)
    args = parser.parse_args(argv)
    names = _role_names_from_args(args)

    if not args.admin_url.strip():
        parser.error("--admin-url or RESOLUTION_ADMIN_DATABASE_URL is required")

    if args.command == "bootstrap":
        migrator_password = os.environ.get("RAG_NEW_MIGRATOR_PASSWORD", "")
        runtime_password = os.environ.get("RAG_NEW_RUNTIME_PASSWORD", "")
        if not migrator_password or not runtime_password:
            parser.error("RAG_NEW_MIGRATOR_PASSWORD and RAG_NEW_RUNTIME_PASSWORD are required")
        _require_mutation_confirmation(parser, args, names)
    elif args.command in {"grant", "revoke-runtime", "smoke"}:
        _require_mutation_confirmation(parser, args, names)

    try:
        if args.command == "inventory":
            print(
                json.dumps(
                    inventory(
                        args.admin_url,
                        names,
                        expected_port=args.expected_port,
                        expected_data_directory=args.expected_data_directory,
                    ),
                    sort_keys=True,
                )
            )
        elif args.command == "bootstrap":
            bootstrap(
                args.admin_url,
                names,
                migrator_password=migrator_password,
                runtime_password=runtime_password,
                expected_port=args.expected_port,
                expected_data_directory=args.expected_data_directory,
            )
            print("C8 role/database bootstrap applied")
        elif args.command == "grant":
            apply_runtime_grants(
                args.admin_url,
                names,
                expected_port=args.expected_port,
                expected_data_directory=args.expected_data_directory,
            )
            print("C8 runtime grants applied")
        elif args.command == "revoke-runtime":
            revoke_runtime_access(
                args.admin_url,
                names,
                expected_port=args.expected_port,
                expected_data_directory=args.expected_data_directory,
            )
            print("C8 runtime access revoked")
        elif args.command == "smoke":
            runtime_url = os.environ.get("RESOLUTION_RUNTIME_DATABASE_URL", "")
            encryption_key = os.environ.get("DB_ENCRYPTION_KEY", "")
            if not runtime_url or not encryption_key:
                parser.error("RESOLUTION_RUNTIME_DATABASE_URL and DB_ENCRYPTION_KEY are required")
            smoke_runtime_contract(
                args.admin_url,
                runtime_url,
                names,
                encryption_key=encryption_key,
                expected_port=args.expected_port,
                expected_data_directory=args.expected_data_directory,
            )
            print("C8 direct-runtime smoke verified")
        else:
            violations = verify_contract(
                args.admin_url,
                names,
                expected_port=args.expected_port,
                expected_data_directory=args.expected_data_directory,
            )
            if violations:
                for violation in violations:
                    print(f"C8 contract violation: {violation}", file=sys.stderr)
                return EXIT_CONTRACT_FAILED
            print("C8 role contract verified")
    except (ValueError, RoleContractError, psycopg2.Error) as exc:
        print(f"C8 role operation failed: {exc}", file=sys.stderr)
        return EXIT_OPERATION_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
