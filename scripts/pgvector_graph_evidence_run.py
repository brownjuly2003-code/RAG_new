"""Acceptance runner for the pgvector graph-evidence resolution stage."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import UUID, uuid5

import networkx as nx

from scripts.pgvector_graph_evidence import (
    Provenance,
    RlsObservation,
    RuntimeRole,
    build_evidence_report,
    graph_parity,
    production_evidence_join_sql,
)

if TYPE_CHECKING:
    from ingestion.structure_graph import StructuralGraph

EXPECTED_CHUNKS = 5589
SCHEMA_VERSION = "d4-pgvector-graph-evidence-v1"
SOURCE_FILES = (
    "scripts/pgvector_graph_evidence_run.py",
    "scripts/pgvector_graph_evidence.py",
    "ingestion/structure_graph.py",
    "ingestion/structure_graph_repository.py",
    "ingestion/structure_graph_projection.py",
)

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})
_LOCAL_PORT = 55432
_POSTGRES_DRIVER = re.compile(r"postgresql(?:\+[a-z0-9_.]+)?")
_ALLOWED_DATABASE_QUERY_KEYS = frozenset({"sslmode", "connect_timeout", "application_name"})
_DATABASE_URL_ERROR = (
    "database URL must use a PostgreSQL driver and must target localhost or 127.0.0.1 on port 55432"
)
_ROOT = Path(__file__).resolve().parent.parent
_TENANT_ID = "359dcdf9-4096-5229-a37c-4d78b7474f6a"
_OTHER_TENANT_ID = "90b95d76-4826-5cf6-a922-d8f832bdbca1"
_IDENTITY_NAMESPACE = UUID("c5935f2c-431f-5e72-9833-aeab769c269a")
_TIMESTAMP = datetime(2026, 9, 22, tzinfo=timezone.utc)
_SCRATCH_PATTERN = re.compile(r"rag_spike_d4_[0-9a-f]{16}")
_ROLE_PATTERN = re.compile(r"rag_d4_role_[0-9a-f]{16}")
_MEASURED_TABLES = (
    "support_cases",
    "case_events",
    "kb_graph_nodes",
    "kb_graph_edges",
    "evidence_snapshots",
    "case_evidence_links",
)
_RLS_TABLES = _MEASURED_TABLES[2:]

_KeyedEdges = dict[Any, dict[Any, dict[Any, dict[Any, Any]]]]


class _Chunk:
    """Plain carrier for the page_content/metadata chunk contract."""

    __slots__ = ("page_content", "metadata")

    def __init__(self, page_content: str, metadata: dict[str, Any]) -> None:
        self.page_content = page_content
        self.metadata = metadata


class _LoadedChunks:
    """Loaded chunks with compatible two-value unpacking and an optional archive hash."""

    __slots__ = ("chunks", "json_sha256", "archive_sha256")

    def __init__(self, chunks: list[_Chunk], json_sha256: str, archive_sha256: str | None) -> None:
        self.chunks = chunks
        self.json_sha256 = json_sha256
        self.archive_sha256 = archive_sha256

    def __iter__(self) -> Iterator[list[_Chunk] | str]:
        yield self.chunks
        yield self.json_sha256


def _persisted_graph_contract(graph: StructuralGraph) -> StructuralGraph:
    return replace(
        graph,
        nodes=tuple(
            sorted(graph.nodes, key=lambda node: (node.kind, node.natural_key, node.node_id))
        ),
        edges=tuple(
            sorted(
                graph.edges,
                key=lambda edge: (
                    edge.kind,
                    edge.source_node_id,
                    edge.target_node_id,
                    edge.edge_id,
                ),
            )
        ),
        unresolved_cross_refs=(),
    )


def _load_chunks(path: Path | str, expected_count: int) -> _LoadedChunks:
    """Load plain JSON or magic-byte gzip and hash both source and JSON bytes."""
    if isinstance(expected_count, bool) or not isinstance(expected_count, int):
        raise TypeError("expected_count must be an integer")
    if expected_count <= 0:
        raise ValueError("expected_count must be a positive integer")
    source = Path(path).read_bytes()
    archive_sha256 = None
    if source.startswith(b"\x1f\x8b"):
        archive_sha256 = hashlib.sha256(source).hexdigest()
        try:
            payload = gzip.decompress(source)
        except OSError:
            raise ValueError("invalid gzip chunk archive") from None
    else:
        payload = source
    try:
        document = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("chunk document must be UTF-8 encoded JSON") from error
    if not isinstance(document, Mapping):
        raise ValueError("chunk document must be a JSON object")
    rows = document.get("chunks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("chunk document must carry a nonempty 'chunks' list")
    chunks = [_chunk_from_row(row) for row in rows]
    if len(chunks) != expected_count:
        raise ValueError(f"chunk document holds {len(chunks)} rows, expected {expected_count}")
    return _LoadedChunks(chunks, hashlib.sha256(payload).hexdigest(), archive_sha256)


def _chunk_from_row(row: Any) -> _Chunk:
    """Validate one parsed row and copy it into an independent _Chunk."""
    if not isinstance(row, Mapping):
        raise TypeError("every chunk row must be a JSON object")
    if "page_content" not in row or "metadata" not in row:
        raise ValueError("every chunk row needs 'page_content' and 'metadata'")
    page_content = row["page_content"]
    metadata = row["metadata"]
    if not isinstance(page_content, str):
        raise TypeError("chunk 'page_content' must be a string")
    if not page_content:
        raise ValueError("chunk 'page_content' must not be empty")
    if not isinstance(metadata, Mapping):
        raise TypeError("chunk 'metadata' must be a JSON object")
    return _Chunk(page_content, copy.deepcopy(dict(metadata)))


def _traversal_mismatch_count(left: nx.MultiDiGraph, right: nx.MultiDiGraph) -> int:
    """Count node and keyed-edge drift between two traversals.

    Insertion order is irrelevant: canonical node payloads plus the outgoing
    and incoming keyed edge adjacency (edge attributes included) are compared,
    so any directed/key/attribute/node drift yields a deterministic count.
    """
    for graph in (left, right):
        if not isinstance(graph, nx.MultiDiGraph):
            raise TypeError("traversal comparison needs MultiDiGraph values")
    mismatches = 0
    for node in set(left.nodes) | set(right.nodes):
        if node not in left or node not in right:
            mismatches += 1
        elif left.nodes[node] != right.nodes[node]:
            mismatches += 1
    mismatches += _adjacency_mismatches(
        _keyed_adjacency(left, incoming=False),
        _keyed_adjacency(right, incoming=False),
    )
    mismatches += _adjacency_mismatches(
        _keyed_adjacency(left, incoming=True),
        _keyed_adjacency(right, incoming=True),
    )
    return mismatches


def _keyed_adjacency(graph: nx.MultiDiGraph, *, incoming: bool) -> _KeyedEdges:
    """Build the hub -> peer -> edge key -> attributes map for one direction."""
    adjacency: _KeyedEdges = {}
    for source, target, key, data in graph.edges(keys=True, data=True):
        hub, peer = (target, source) if incoming else (source, target)
        peers = adjacency.setdefault(hub, {})
        keyed = peers.setdefault(peer, {})
        keyed[key] = dict(data)
    return adjacency


def _adjacency_mismatches(left: _KeyedEdges, right: _KeyedEdges) -> int:
    """Count hubs whose keyed peer adjacency differs between both sides."""
    mismatches = 0
    for hub in left.keys() | right.keys():
        if left.get(hub) != right.get(hub):
            mismatches += 1
    return mismatches


def _validate_local_database_url(value: str) -> str:
    """Accept only the local acceptance PostgreSQL DSN; return it unchanged."""
    if not isinstance(value, str):
        raise TypeError("database URL must be a string")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError(_DATABASE_URL_ERROR) from None
    if not _POSTGRES_DRIVER.fullmatch(parsed.scheme):
        raise ValueError(_DATABASE_URL_ERROR)
    if hostname not in _LOCAL_HOSTS:
        raise ValueError(_DATABASE_URL_ERROR)
    if port != _LOCAL_PORT:
        raise ValueError(_DATABASE_URL_ERROR)
    return value


def _write_report(path: Path | str, report: Mapping[str, Any]) -> None:
    """Serialize strictly first, then create the target exclusively.

    Output is UTF-8 with LF endings and exactly one trailing newline. Existing
    targets are never modified and serialization failures create no target.
    """
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    with open(path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def _scratch_name(suffix: str | None = None) -> str:
    name = f"rag_spike_d4_{suffix if suffix is not None else secrets.token_hex(8)}"
    return _require_scratch_name(name)


def _require_scratch_name(name: str) -> str:
    if not isinstance(name, str) or _SCRATCH_PATTERN.fullmatch(name) is None:
        raise ValueError("invalid scratch database name")
    return name


def _role_name(suffix: str) -> str:
    name = f"rag_d4_role_{suffix}"
    if _ROLE_PATTERN.fullmatch(name) is None:
        raise ValueError("invalid disposable role name")
    return name


def _git_code_base() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise RuntimeError("cannot read code commit")
    return value


def _git_tree_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError("cannot read working tree status")
    return not result.stdout.strip()


def _source_digests() -> dict[str, str]:
    return {
        relative: hashlib.sha256((_ROOT / relative).read_bytes()).hexdigest()
        for relative in SOURCE_FILES
    }


@contextmanager
def _temporary_environment(values: Mapping[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


@contextmanager
def _migration_environment(scratch_url: Any) -> Iterator[None]:
    with _temporary_environment(
        {
            "DATABASE_URL": scratch_url.render_as_string(hide_password=False),
            "DB_ENCRYPTION_KEY": secrets.token_hex(32),
        }
    ):
        yield


def _maintenance_url(value: str) -> Any:
    from sqlalchemy.engine import make_url

    _validate_local_database_url(value)
    try:
        url = make_url(value)
    except Exception:
        raise ValueError(_DATABASE_URL_ERROR) from None
    if (
        set(url.query) - _ALLOWED_DATABASE_QUERY_KEYS
        or url.database != "postgres"
        or url.drivername
        not in (
            "postgresql",
            "postgresql+psycopg2",
        )
    ):
        raise ValueError("administrative URL must target local postgres maintenance database")
    return url


class _MeasurementFailure(RuntimeError):
    """A measurement failure whose message contains only runner-owned diagnostics."""


def _safe_failure_message(step: str, error: Exception) -> str:
    original = getattr(error, "orig", error)
    sqlstate = getattr(original, "pgcode", None)
    suffix = (
        f" sqlstate={sqlstate}"
        if isinstance(sqlstate, str) and re.fullmatch(r"[A-Z0-9]{5}", sqlstate)
        else ""
    )
    return f"scratch measurement failed at step={step}: {type(error).__name__}{suffix}"


def _database_exists(administrative_url: Any, name: str) -> bool:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    _require_scratch_name(name)
    engine = create_engine(
        administrative_url,
        hide_parameters=True,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with engine.connect() as connection:
            return bool(
                connection.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
                )
            )
    finally:
        engine.dispose()


def _create_scratch_database(administrative_url: Any, name: str) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    _require_scratch_name(name)
    engine = create_engine(
        administrative_url,
        hide_parameters=True,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with engine.connect() as connection:
            if connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            ):
                raise FileExistsError("scratch database already exists")
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        engine.dispose()


def _drop_scratch_database(administrative_url: Any, created_name: str) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    name = _require_scratch_name(created_name)
    engine = create_engine(
        administrative_url,
        hide_parameters=True,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
    finally:
        engine.dispose()


def _run_alembic_upgrade(config: Any) -> None:
    from alembic import command

    command.upgrade(config, "head")


def _migrate_scratch_database(scratch_url: Any) -> str:
    import sqlalchemy as sa
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        raise RuntimeError("Alembic head is unavailable")
    tracked_engines: list[Any] = []
    original_factory = sa.engine_from_config

    def tracking_factory(*args: Any, **kwargs: Any) -> Any:
        kwargs["hide_parameters"] = True
        engine = original_factory(*args, **kwargs)
        tracked_engines.append(engine)
        return engine

    try:
        with _migration_environment(scratch_url):
            with patch.object(sa, "engine_from_config", tracking_factory):
                _run_alembic_upgrade(config)
    finally:
        for engine in tracked_engines:
            engine.dispose()

    engine = create_engine(scratch_url, hide_parameters=True, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            actual = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    if actual != head:
        raise RuntimeError("scratch migration did not reach Alembic head")
    return head


def _post_rollback_checks(scratch_url: Any, role_name: str) -> tuple[dict[str, int], bool]:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    if _ROLE_PATTERN.fullmatch(role_name) is None:
        raise ValueError("invalid disposable role name")
    engine = create_engine(scratch_url, hide_parameters=True, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            counts = {
                table: int(connection.scalar(text(f"SELECT count(*) FROM public.{table}")))
                for table in _MEASURED_TABLES
            }
            role_absent = not bool(
                connection.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role_name}
                )
            )
        return counts, role_absent
    finally:
        engine.dispose()


def _set_tenant(connection: Any, tenant_id: str) -> None:
    from sqlalchemy import text

    connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )


def _assert_empty_tables(connection: Any) -> None:
    from sqlalchemy import text

    for table in _MEASURED_TABLES:
        if connection.scalar(text(f"SELECT count(*) FROM public.{table}")) != 0:
            raise RuntimeError("scratch measured table is not empty")


def _seed_graph(connection: Any, chunks: list[_Chunk]) -> tuple[Any, Any]:
    from sqlalchemy.orm import Session

    from ingestion.structure_graph import build_structural_graph
    from ingestion.structure_graph_repository import StructuralGraphRepository

    built = build_structural_graph(chunks, tenant_id=_TENANT_ID)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        repository = StructuralGraphRepository(session)
        repository.replace(built)
        reloaded = repository.load(_TENANT_ID)
        session.commit()
    return built, reloaded


def _identity(label: str) -> UUID:
    return uuid5(_IDENTITY_NAMESPACE, f"{_TENANT_ID}:{label}")


def _seed_evidence(connection: Any, reloaded: Any) -> UUID:
    from sqlalchemy import text

    _set_tenant(connection, _TENANT_ID)
    tenant = UUID(_TENANT_ID)
    case_id = _identity("case")
    event_id = _identity("case-event")
    correlation_id = _identity("correlation")
    connection.execute(
        text(
            """INSERT INTO public.support_cases
            (id, tenant_id, contract_id, contract_version, contract_digest,
             correlation_id, status, version, opened_at, effective_at, updated_at)
            VALUES (:id, :tenant, :contract_id, :contract_version, :contract_digest,
                    :correlation, :status, :version, :opened, :effective, :updated)"""
        ),
        {
            "id": case_id,
            "tenant": tenant,
            "contract_id": "d4-scratch-contract",
            "contract_version": "1",
            "contract_digest": hashlib.sha256(b"d4-scratch-contract").hexdigest(),
            "correlation": correlation_id,
            "status": "received",
            "version": 1,
            "opened": _TIMESTAMP,
            "effective": _TIMESTAMP,
            "updated": _TIMESTAMP,
        },
    )
    connection.execute(
        text(
            """INSERT INTO public.case_events
            (id, tenant_id, case_id, sequence, case_version, event_type, command_id,
             actor_id, correlation_id, from_status, to_status, reason_code,
             occurred_at, recorded_at)
            VALUES (:id, :tenant, :case_id, :sequence, :case_version, :event_type,
                    :command_id, :actor_id, :correlation_id, :from_status,
                    :to_status, :reason_code, :occurred_at, :recorded_at)"""
        ),
        {
            "id": event_id,
            "tenant": tenant,
            "case_id": case_id,
            "sequence": 1,
            "case_version": 1,
            "event_type": "case_opened",
            "command_id": _identity("command"),
            "actor_id": _identity("actor"),
            "correlation_id": correlation_id,
            "from_status": None,
            "to_status": "received",
            "reason_code": "CASE_OPENED",
            "occurred_at": _TIMESTAMP,
            "recorded_at": _TIMESTAMP,
        },
    )
    snapshot_sql = text(
        """INSERT INTO public.evidence_snapshots
        (id, tenant_id, logical_key, source_type, source_id, source_version,
         content_digest, valid_from, valid_to, recorded_at, authority,
         applicability_key, visibility, reference_storage, reference_locator,
         encryption_profile, redaction_profile, retention_class)
        VALUES (:id, :tenant, :logical_key, :source_type, :source_id,
                :source_version, :content_digest, :valid_from, :valid_to,
                :recorded_at, :authority, :applicability_key, :visibility,
                :reference_storage, :reference_locator, :encryption_profile,
                :redaction_profile, :retention_class)"""
    )
    link_sql = text(
        """INSERT INTO public.case_evidence_links
        (id, tenant_id, case_id, case_version, evidence_id, requirement_id,
         purpose, gathered_at, freshness)
        VALUES (:id, :tenant, :case_id, :case_version, :evidence_id,
                :requirement_id, :purpose, :gathered_at, :freshness)"""
    )
    first_evidence_id: UUID | None = None
    for node in reloaded.nodes:
        if node.kind != "chunk":
            continue
        if len(node.natural_key) > 256:
            raise ValueError("chunk natural key exceeds evidence source_id limit")
        evidence_id = _identity(f"evidence:{node.node_id}")
        link_id = _identity(f"link:{node.node_id}")
        if first_evidence_id is None:
            first_evidence_id = evidence_id
        connection.execute(
            snapshot_sql,
            {
                "id": evidence_id,
                "tenant": tenant,
                "logical_key": str(evidence_id),
                "source_type": "knowledge",
                "source_id": node.natural_key,
                "source_version": "1",
                "content_digest": node.attributes["content_sha256"],
                "valid_from": _TIMESTAMP,
                "valid_to": None,
                "recorded_at": _TIMESTAMP,
                "authority": "d4-scratch",
                "applicability_key": "d4-scratch",
                "visibility": "support_only",
                "reference_storage": "development_file",
                "reference_locator": f"d4://{node.node_id}".encode("utf-8"),
                "encryption_profile": None,
                "redaction_profile": "none",
                "retention_class": "scratch",
            },
        )
        connection.execute(
            link_sql,
            {
                "id": link_id,
                "tenant": tenant,
                "case_id": case_id,
                "case_version": 1,
                "evidence_id": evidence_id,
                "requirement_id": "D4_GRAPH_EVIDENCE",
                "purpose": "fact",
                "gathered_at": _TIMESTAMP,
                "freshness": "current",
            },
        )
    if first_evidence_id is None:
        raise ValueError("structural graph has no chunk nodes")
    return first_evidence_id


def _seed_evidence_checked(connection: Any, reloaded: Any) -> UUID:
    try:
        return _seed_evidence(connection, reloaded)
    except Exception as error:
        raise _MeasurementFailure(_safe_failure_message("seed_evidence", error)) from None


def _create_measurement_role(connection: Any, role_name: str) -> None:
    from sqlalchemy import text

    if _ROLE_PATTERN.fullmatch(role_name) is None:
        raise ValueError("invalid disposable role name")
    connection.execute(text(f'CREATE ROLE "{role_name}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
    connection.execute(text(f'GRANT "{role_name}" TO CURRENT_USER WITH SET TRUE'))
    connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role_name}"'))
    table_list = ", ".join(f"public.{table}" for table in _MEASURED_TABLES)
    connection.execute(
        text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table_list} TO "{role_name}"')
    )
    connection.execute(text(f'SET LOCAL ROLE "{role_name}"'))


def _rls_observations(
    connection: Any, expected_counts: Mapping[str, int]
) -> tuple[tuple[RlsObservation, ...], RuntimeRole]:
    from sqlalchemy import text

    role_row = connection.execute(
        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).one()
    runtime_role = RuntimeRole(bool(role_row.rolsuper), bool(role_row.rolbypassrls))
    observations = []
    for table in _RLS_TABLES:
        relation = connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE oid = to_regclass(:relation)"
            ),
            {"relation": f"public.{table}"},
        ).one()
        _set_tenant(connection, "")
        unset_rows = int(connection.scalar(text(f"SELECT count(*) FROM public.{table}")))
        _set_tenant(connection, _TENANT_ID)
        own_rows = int(connection.scalar(text(f"SELECT count(*) FROM public.{table}")))
        _set_tenant(connection, _OTHER_TENANT_ID)
        cross_rows = int(connection.scalar(text(f"SELECT count(*) FROM public.{table}")))
        observations.append(
            RlsObservation(
                table_name=table,
                force_rls=bool(relation.relforcerowsecurity),
                unset_visible_rows=unset_rows,
                own_tenant_rows=own_rows,
                expected_own_rows=expected_counts[table],
                cross_tenant_visible_rows=cross_rows,
                row_security=bool(relation.relrowsecurity),
            )
        )
    _set_tenant(connection, _TENANT_ID)
    return tuple(observations), runtime_role


def _probe_sqlstate(connection: Any, statement: str, params: Mapping[str, Any]) -> str | None:
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    savepoint = connection.begin_nested()
    try:
        connection.execute(text(statement), params)
    except DBAPIError as error:
        sqlstate = getattr(error.orig, "pgcode", None) or getattr(error.orig, "sqlstate", None)
        savepoint.rollback()
        return sqlstate
    except Exception:
        savepoint.rollback()
        raise RuntimeError("database probe failed") from None
    savepoint.rollback()
    return "00000"


def _run_probes(connection: Any, first_evidence_id: UUID) -> dict[str, str | None]:
    insert_state = _probe_sqlstate(
        connection,
        """INSERT INTO public.kb_graph_nodes
        (tenant_id, node_id, kind, natural_key, label, attributes)
        VALUES (:tenant, :node_id, :kind, :natural_key, :label, CAST(:attrs AS jsonb))""",
        {
            "tenant": _OTHER_TENANT_ID,
            "node_id": _identity("cross-tenant-probe"),
            "kind": "chunk",
            "natural_key": "d4-cross-tenant-probe",
            "label": "d4-cross-tenant-probe",
            "attrs": "{}",
        },
    )
    update_state = _probe_sqlstate(
        connection,
        """UPDATE public.evidence_snapshots SET content_digest = content_digest
        WHERE id = :evidence_id AND tenant_id = :tenant""",
        {"evidence_id": first_evidence_id, "tenant": UUID(_TENANT_ID)},
    )
    delete_state = _probe_sqlstate(
        connection,
        """DELETE FROM public.evidence_snapshots
        WHERE id = :evidence_id AND tenant_id = :tenant""",
        {"evidence_id": first_evidence_id, "tenant": UUID(_TENANT_ID)},
    )
    return {
        "cross_tenant_insert_sqlstate": insert_state,
        "evidence_update_sqlstate": update_state,
        "evidence_delete_sqlstate": delete_state,
    }


def _vector_extension_version(connection: Any) -> str:
    from sqlalchemy import text

    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    version = connection.scalar(
        text("SELECT extversion FROM pg_extension WHERE extname = :extension"),
        {"extension": "vector"},
    )
    if not isinstance(version, str) or not version:
        raise RuntimeError("vector extension version is unavailable")
    return version


def _seed_and_measure(connection: Any, chunks: list[_Chunk], role_name: str) -> dict[str, Any]:
    import psycopg2
    import sqlalchemy as sa
    from sqlalchemy import text

    from ingestion.structure_graph_projection import (
        project_structure_graph,
        structure_graph_digest,
    )

    _assert_empty_tables(connection)
    vector_version = _vector_extension_version(connection)
    built, reloaded = _seed_graph(connection, chunks)
    built_contract = _persisted_graph_contract(built)
    reloaded_contract = _persisted_graph_contract(reloaded)
    built_projection = project_structure_graph(built)
    reloaded_projection = project_structure_graph(reloaded)
    parity = graph_parity(built_projection, reloaded_projection)
    first_evidence_id = _seed_evidence_checked(connection, reloaded)
    chunk_node_count = int(
        connection.scalar(
            text(
                "SELECT count(*) FROM public.kb_graph_nodes "
                "WHERE kind = :kind AND tenant_id = :tenant"
            ),
            {"kind": "chunk", "tenant": _TENANT_ID},
        )
    )
    evidence_link_count = int(
        connection.scalar(text("SELECT count(*) FROM public.case_evidence_links"))
    )
    evidence_join_count = len(connection.execute(text(production_evidence_join_sql())).all())
    expected_counts = {
        table: int(connection.scalar(text(f"SELECT count(*) FROM public.{table}")))
        for table in _RLS_TABLES
    }
    server_version = str(connection.scalar(text("SHOW server_version")))
    _create_measurement_role(connection, role_name)
    observations, runtime_role = _rls_observations(connection, expected_counts)
    sqlstates = _run_probes(connection, first_evidence_id)
    return {
        "parity": parity,
        "traversal_mismatch_count": _traversal_mismatch_count(
            built_projection, reloaded_projection
        ),
        "chunk_node_count": chunk_node_count,
        "evidence_link_count": evidence_link_count,
        "evidence_join_count": evidence_join_count,
        "built_graph_digest": structure_graph_digest(built),
        "reloaded_graph_digest": structure_graph_digest(reloaded),
        "built_persisted_contract_digest": structure_graph_digest(built_contract),
        "reloaded_persisted_contract_digest": structure_graph_digest(reloaded_contract),
        "unresolved_cross_ref_count": len(built.unresolved_cross_refs),
        "load_preserved_node_order": tuple(node.node_id for node in built.nodes)
        == tuple(node.node_id for node in reloaded.nodes),
        "load_preserved_edge_order": tuple(edge.edge_id for edge in built.edges)
        == tuple(edge.edge_id for edge in reloaded.edges),
        "rls_observations": observations,
        "runtime_role": runtime_role,
        "server_version": server_version,
        "vector_version": vector_version,
        "versions": {
            "python": sys.version.split()[0],
            "sqlalchemy": sa.__version__,
            "psycopg2": psycopg2.__version__,
            "networkx": nx.__version__,
        },
        **sqlstates,
    }


def _measure_scratch_database(
    scratch_url: Any, chunks: list[_Chunk], role_name: str
) -> dict[str, Any]:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    engine = create_engine(scratch_url, hide_parameters=True, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                return _seed_and_measure(connection, chunks, role_name)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _run_lifecycle(administrative_url: Any, chunks: list[_Chunk]) -> dict[str, Any]:
    scratch_name = _scratch_name()
    role_name = _role_name(scratch_name.removeprefix("rag_spike_d4_"))
    scratch_url = administrative_url.set(database=scratch_name)
    try:
        _create_scratch_database(administrative_url, scratch_name)
    except FileExistsError:
        raise FileExistsError("scratch database already exists") from None
    except Exception as error:
        raise RuntimeError(_safe_failure_message("create", error)) from None

    measurement: dict[str, Any] | None = None
    head: str | None = None
    post_counts: dict[str, int] | None = None
    role_absent: bool | None = None
    failure: str | None = None
    dropped = False
    try:
        step = "migrate"
        try:
            head = _migrate_scratch_database(scratch_url)
            step = "measure"
            measurement = _measure_scratch_database(scratch_url, chunks, role_name)
        except _MeasurementFailure as error:
            failure = str(error)
        except Exception as error:
            failure = _safe_failure_message(step, error)
        try:
            post_counts, role_absent = _post_rollback_checks(scratch_url, role_name)
        except Exception as error:
            failure = failure or _safe_failure_message("post_rollback_checks", error)
    finally:
        try:
            _drop_scratch_database(administrative_url, scratch_name)
            dropped = True
        except Exception:
            dropped = False
    if failure is not None:
        raise RuntimeError(failure)
    if measurement is None or head is None or post_counts is None or role_absent is None:
        raise RuntimeError("scratch measurement is incomplete")
    return {
        "measurement": measurement,
        "alembic_head": head,
        "post_rollback_counts": post_counts,
        "role_absent": role_absent,
        "scratch_name": scratch_name,
        "scratch_dropped": dropped,
    }


def run_acceptance(
    chunks_path: Path | str,
    output_path: Path | str,
    database_url: str,
    code_base: str,
    *,
    expected_chunk_count: int = EXPECTED_CHUNKS,
) -> dict[str, Any]:
    """Measure one disposable PostgreSQL graph and write the strict report once."""
    if Path(output_path).exists():
        raise FileExistsError("output path already exists")
    administrative_url = _maintenance_url(database_url)
    loaded = _load_chunks(chunks_path, expected_chunk_count)
    if code_base != _git_code_base():
        raise ValueError("code commit does not match HEAD")
    clean_tree = _git_tree_clean()
    source_sha256 = _source_digests()
    lifecycle = _run_lifecycle(administrative_url, loaded.chunks)
    measurement = lifecycle["measurement"]
    input_sha256 = {"decompressed_json": loaded.json_sha256}
    if loaded.archive_sha256 is not None:
        input_sha256["gzip_archive"] = loaded.archive_sha256
    provenance = Provenance(
        code_base_sha=code_base,
        corpus_digest=loaded.json_sha256,
        input_sha256=input_sha256,
        source_sha256=source_sha256,
        clean_tree=clean_tree,
        alembic_head=lifecycle["alembic_head"],
        server_version=measurement["server_version"],
        vector_version=measurement["vector_version"],
        versions=measurement["versions"],
    )
    report = build_evidence_report(
        provenance=provenance,
        parity=measurement["parity"],
        traversal_mismatch_count=measurement["traversal_mismatch_count"],
        chunk_node_count=measurement["chunk_node_count"],
        evidence_link_count=measurement["evidence_link_count"],
        evidence_join_count=measurement["evidence_join_count"],
        rls_observations=measurement["rls_observations"],
        runtime_role=measurement["runtime_role"],
        cross_tenant_insert_sqlstate=measurement["cross_tenant_insert_sqlstate"],
        evidence_update_sqlstate=measurement["evidence_update_sqlstate"],
        evidence_delete_sqlstate=measurement["evidence_delete_sqlstate"],
        built_graph_digest=measurement["built_graph_digest"],
        reloaded_graph_digest=measurement["reloaded_graph_digest"],
        built_persisted_contract_digest=measurement["built_persisted_contract_digest"],
        reloaded_persisted_contract_digest=measurement["reloaded_persisted_contract_digest"],
        unresolved_cross_ref_count=measurement["unresolved_cross_ref_count"],
        load_preserved_node_order=measurement["load_preserved_node_order"],
        load_preserved_edge_order=measurement["load_preserved_edge_order"],
        post_rollback_counts=lifecycle["post_rollback_counts"],
        role_absent=lifecycle["role_absent"],
        scratch_name=lifecycle["scratch_name"],
        scratch_dropped=lifecycle["scratch_dropped"],
    )
    _write_report(output_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure D.4 graph and evidence parity")
    parser.add_argument("--chunks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("output path already exists")
    database_url = os.getenv("RESOLUTION_ADMIN_DATABASE_URL")
    if not database_url:
        raise ValueError("RESOLUTION_ADMIN_DATABASE_URL is required")
    report = run_acceptance(
        chunks_path=args.chunks,
        output_path=args.output,
        database_url=database_url,
        code_base=_git_code_base(),
    )
    if report.get("evidence_class") == "measured":
        print("DONE")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
