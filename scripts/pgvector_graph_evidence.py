"""Deterministic, NetworkX-only evidence for structural graph projections."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import networkx as nx

__all__ = [
    "GraphParity",
    "Provenance",
    "RlsObservation",
    "RuntimeRole",
    "build_evidence_report",
    "canonical_projection",
    "graph_parity",
    "production_evidence_join_sql",
]


def _jsonable(value: Any) -> Any:
    """Coerce attribute values into deterministic, JSON-compatible types."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(item) for item in value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)


def _node_payload(node: Any, data: dict[str, Any]) -> dict[str, Any]:
    payload = {str(key): _jsonable(value) for key, value in data.items()}
    payload["id"] = str(node)
    return payload


def _edge_payload(source: Any, target: Any, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    payload = {str(attr): _jsonable(value) for attr, value in data.items()}
    payload["source"] = str(source)
    payload["target"] = str(target)
    payload["key"] = str(key)
    return payload


def _edge_identifier(payload: dict[str, Any]) -> str:
    return f"{payload['source']}->{payload['target']}:{payload['key']}"


def canonical_projection(graph: nx.MultiDiGraph) -> dict[str, Any]:
    """Return a deterministic, JSON-serializable snapshot of ``graph``."""
    return {
        "graph": {str(key): _jsonable(value) for key, value in graph.graph.items()},
        "nodes": sorted(
            (_node_payload(node, data) for node, data in graph.nodes(data=True)),
            key=lambda payload: payload["id"],
        ),
        "edges": sorted(
            (
                _edge_payload(source, target, key, data)
                for source, target, key, data in graph.edges(keys=True, data=True)
            ),
            key=lambda payload: (
                payload["source"],
                payload["target"],
                payload["key"],
            ),
        ),
    }


@dataclass(frozen=True, slots=True)
class GraphParity:
    """Immutable parity report between two structural graph projections."""

    identical: bool
    node_count: int
    edge_count: int
    node_mismatch_count: int
    edge_mismatch_count: int
    node_mismatch_ids: tuple[str, ...]
    edge_mismatch_ids: tuple[str, ...]


def graph_parity(left: nx.MultiDiGraph, right: nx.MultiDiGraph) -> GraphParity:
    """Compare two projections by their complete canonical payloads."""
    left_canonical = canonical_projection(left)
    right_canonical = canonical_projection(right)
    left_nodes = {payload["id"]: payload for payload in left_canonical["nodes"]}
    right_nodes = {payload["id"]: payload for payload in right_canonical["nodes"]}
    left_edges = {_edge_identifier(payload): payload for payload in left_canonical["edges"]}
    right_edges = {_edge_identifier(payload): payload for payload in right_canonical["edges"]}

    node_mismatch_ids = tuple(
        node_id
        for node_id in sorted(left_nodes.keys() | right_nodes.keys())
        if left_nodes.get(node_id) != right_nodes.get(node_id)
    )
    edge_mismatch_ids = tuple(
        edge_id
        for edge_id in sorted(left_edges.keys() | right_edges.keys())
        if left_edges.get(edge_id) != right_edges.get(edge_id)
    )

    return GraphParity(
        identical=(
            left_canonical["graph"] == right_canonical["graph"]
            and not node_mismatch_ids
            and not edge_mismatch_ids
        ),
        node_count=len(left_nodes),
        edge_count=len(left_edges),
        node_mismatch_count=len(node_mismatch_ids),
        edge_mismatch_count=len(edge_mismatch_ids),
        node_mismatch_ids=node_mismatch_ids,
        edge_mismatch_ids=edge_mismatch_ids,
    )


_HEX_DIGITS = frozenset("0123456789abcdef")
_RLS_TABLES = (
    "kb_graph_nodes",
    "kb_graph_edges",
    "evidence_snapshots",
    "case_evidence_links",
)
_MEASURED_TABLES = ("support_cases", "case_events", *_RLS_TABLES)
_SCRATCH_NAME = re.compile(r"rag_spike_d4_[0-9a-f]{16}")
LIMITATIONS = (
    "D.4 supersedes only D.1's limitation, a simplified `kb_graph_nodes` membership "
    "table under `app.tenant_id`. It changes no D.1–D.3 retrieval number, no product "
    "default, and `RAG_GRAPH_RETRIEVAL` stays `off`. The schema stores no unresolved "
    "cross-reference, so D.4 compares the persisted contract, the graph without them in "
    "a fixed order, and counts the references it leaves out."
)


@dataclass(frozen=True, slots=True)
class Provenance:
    """Immutable build and corpus provenance for collected evidence."""

    code_base_sha: str
    corpus_digest: str
    input_sha256: Mapping[str, str]
    source_sha256: Mapping[str, str]
    clean_tree: bool = False
    alembic_head: str = ""
    server_version: str = ""
    vector_version: str = ""
    versions: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class RlsObservation:
    """Immutable row-level-security observation for one table."""

    table_name: str
    force_rls: bool
    unset_visible_rows: int
    own_tenant_rows: int
    expected_own_rows: int
    cross_tenant_visible_rows: int
    row_security: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeRole:
    """Immutable snapshot of the database role collecting evidence."""

    superuser: bool
    bypassrls: bool


def production_evidence_join_sql() -> str:
    """Return the deterministic production join between evidence and nodes."""
    return """SELECT nodes.node_id, evidence.id AS evidence_id, links.id AS link_id,
       nodes.natural_key,
       nodes.attributes ->> 'content_sha256' AS content_sha256,
       evidence.content_digest
FROM public.case_evidence_links AS links
JOIN public.evidence_snapshots AS evidence
  ON evidence.id = links.evidence_id
 AND evidence.tenant_id = links.tenant_id
JOIN public.kb_graph_nodes AS nodes
  ON nodes.tenant_id = evidence.tenant_id::text
 AND nodes.natural_key = evidence.source_id
 AND nodes.attributes ->> 'content_sha256' = evidence.content_digest
WHERE nodes.kind = 'chunk'
ORDER BY nodes.node_id, evidence.id, links.id"""


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _digest(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in _HEX_DIGITS for character in value)
    )


def _field(source: Any, name: str) -> Any:
    try:
        if isinstance(source, Mapping):
            return source.get(name)
        return getattr(source, name, None)
    except Exception:
        return None


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    try:
        return {str(key): _jsonable(item) for key, item in value.items()}
    except Exception:
        return {}


def _digest_map(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        pairs = list(value.items())
    except Exception:
        return False
    if not pairs:
        return False
    return all(isinstance(key, str) and key != "" and _digest(item, 64) for key, item in pairs)


def _rls_snapshot(observation: Any) -> dict[str, Any]:
    return {
        "table_name": _scalar(_field(observation, "table_name")),
        "row_security": _scalar(_field(observation, "row_security")),
        "force_rls": _scalar(_field(observation, "force_rls")),
        "unset_visible_rows": _scalar(_field(observation, "unset_visible_rows")),
        "own_tenant_rows": _scalar(_field(observation, "own_tenant_rows")),
        "expected_own_rows": _scalar(_field(observation, "expected_own_rows")),
        "cross_tenant_visible_rows": _scalar(_field(observation, "cross_tenant_visible_rows")),
    }


def build_evidence_report(
    *,
    provenance: Any,
    parity: Any,
    traversal_mismatch_count: Any,
    chunk_node_count: Any,
    evidence_link_count: Any,
    evidence_join_count: Any,
    rls_observations: Any,
    runtime_role: Any,
    cross_tenant_insert_sqlstate: Any,
    evidence_update_sqlstate: Any,
    evidence_delete_sqlstate: Any,
    built_graph_digest: Any = None,
    reloaded_graph_digest: Any = None,
    built_persisted_contract_digest: Any = None,
    reloaded_persisted_contract_digest: Any = None,
    unresolved_cross_ref_count: Any = None,
    load_preserved_node_order: Any = None,
    load_preserved_edge_order: Any = None,
    post_rollback_counts: Any = None,
    role_absent: Any = None,
    scratch_name: Any = None,
    scratch_dropped: Any = None,
) -> dict[str, Any]:
    """Return a defensive, JSON-compatible graph-evidence report."""
    reasons: list[str] = []

    code_base_sha = _field(provenance, "code_base_sha")
    corpus_digest = _field(provenance, "corpus_digest")
    input_sha256 = _field(provenance, "input_sha256")
    source_sha256 = _field(provenance, "source_sha256")
    clean_tree = _field(provenance, "clean_tree")
    alembic_head = _field(provenance, "alembic_head")
    server_version = _field(provenance, "server_version")
    vector_version = _field(provenance, "vector_version")
    versions = _field(provenance, "versions")
    if not isinstance(provenance, Provenance):
        reasons.append("provenance is not a Provenance instance")
    if not _digest(code_base_sha, 40):
        reasons.append("provenance code_base_sha is not a lowercase 40-hex digest")
    if not _digest(corpus_digest, 64):
        reasons.append("provenance corpus_digest is not a lowercase 64-hex digest")
    if not _digest_map(input_sha256):
        reasons.append("provenance input_sha256 is not a nonempty digest mapping")
    if not _digest_map(source_sha256):
        reasons.append("provenance source_sha256 is not a nonempty digest mapping")
    if clean_tree is not True:
        reasons.append("working tree is dirty or cleanliness is unknown")
    for label, value in (
        ("alembic_head", alembic_head),
        ("server_version", server_version),
        ("vector_version", vector_version),
    ):
        if not isinstance(value, str) or not value:
            reasons.append(f"provenance {label} is missing")
    expected_versions = ("python", "sqlalchemy", "psycopg2", "networkx")
    if not isinstance(versions, Mapping) or any(
        not isinstance(versions.get(name), str) or not versions.get(name)
        for name in expected_versions
    ):
        reasons.append("provenance runtime versions are incomplete")

    if not _digest(built_graph_digest, 64):
        reasons.append("as-built graph digest is missing or malformed")
    if not _digest(reloaded_graph_digest, 64):
        reasons.append("reloaded graph digest is missing or malformed")
    if not _digest(built_persisted_contract_digest, 64) or not _digest(
        reloaded_persisted_contract_digest, 64
    ):
        reasons.append("persisted-contract graph digest is missing or malformed")
    elif built_persisted_contract_digest != reloaded_persisted_contract_digest:
        reasons.append("graph parity persisted-contract digest mismatch")
    if not (_plain_int(unresolved_cross_ref_count) and unresolved_cross_ref_count >= 0):
        reasons.append("unresolved_cross_ref_count is not a nonnegative int")
    if not isinstance(load_preserved_node_order, bool):
        reasons.append("load_preserved_node_order is not a bool")
    if not isinstance(load_preserved_edge_order, bool):
        reasons.append("load_preserved_edge_order is not a bool")

    identical = _field(parity, "identical")
    node_count = _field(parity, "node_count")
    edge_count = _field(parity, "edge_count")
    node_mismatch_count = _field(parity, "node_mismatch_count")
    edge_mismatch_count = _field(parity, "edge_mismatch_count")
    node_mismatch_ids = _field(parity, "node_mismatch_ids")
    edge_mismatch_ids = _field(parity, "edge_mismatch_ids")
    if not isinstance(parity, GraphParity):
        reasons.append("parity is not a GraphParity instance")
    if identical is not True:
        reasons.append("parity identical is not True")
    if not (_plain_int(node_count) and node_count >= 0):
        reasons.append("parity node_count is not a nonnegative int")
    if not (_plain_int(edge_count) and edge_count >= 0):
        reasons.append("parity edge_count is not a nonnegative int")
    if not (
        _plain_int(node_mismatch_count) and node_mismatch_count == 0 and node_mismatch_ids == ()
    ):
        reasons.append("parity node_mismatch_count does not match empty ids")
    if not (
        _plain_int(edge_mismatch_count) and edge_mismatch_count == 0 and edge_mismatch_ids == ()
    ):
        reasons.append("parity edge_mismatch_count does not match empty ids")
    if not (_plain_int(traversal_mismatch_count) and traversal_mismatch_count == 0):
        reasons.append("traversal_mismatch_count is not the int zero")

    chunk_ok = _plain_int(chunk_node_count) and chunk_node_count > 0
    link_ok = _plain_int(evidence_link_count)
    join_ok = _plain_int(evidence_join_count)
    if not chunk_ok:
        reasons.append("chunk_node_count is not a positive int")
    if not link_ok:
        reasons.append("evidence_link_count is not an int")
    if not join_ok:
        reasons.append("evidence_join_count is not an int")
    if not (
        chunk_ok
        and link_ok
        and join_ok
        and chunk_node_count == evidence_link_count == evidence_join_count
    ):
        reasons.append("chunk, link, and join counts disagree")

    if isinstance(rls_observations, (str, bytes, bytearray, Mapping)):
        observations = None
    else:
        try:
            observations = None if rls_observations is None else list(rls_observations)
        except Exception:
            observations = None
    if observations is None:
        reasons.append("rls_observations is not an iterable of RlsObservation")
    rls_output: dict[str, dict[str, Any]] = {}
    observed_tables: set[str] = set()
    unexpected_tables: set[str] = set()
    for observation in observations or ():
        if not isinstance(observation, RlsObservation):
            reasons.append("rls observation is not an RlsObservation instance")
        table_name = _field(observation, "table_name")
        if not isinstance(table_name, str) or not table_name:
            reasons.append("rls observation table_name is not a nonempty string")
            continue
        if table_name in observed_tables:
            reasons.append(f"rls observation duplicated for {table_name}")
            continue
        observed_tables.add(table_name)
        rls_output[table_name] = _rls_snapshot(observation)
        if table_name not in _RLS_TABLES:
            unexpected_tables.add(table_name)
    rls_output = {
        table: rls_output[table]
        for table in (*_RLS_TABLES, *sorted(unexpected_tables))
        if table in rls_output
    }
    for table in _RLS_TABLES:
        if table not in observed_tables:
            reasons.append(f"rls observation missing for {table}")
    if unexpected_tables:
        reasons.append(
            "rls observations include unexpected tables: " + ", ".join(sorted(unexpected_tables))
        )
    for table in _RLS_TABLES:
        snapshot = rls_output.get(table)
        if snapshot is None:
            continue
        row_counts = (
            snapshot["unset_visible_rows"],
            snapshot["own_tenant_rows"],
            snapshot["expected_own_rows"],
            snapshot["cross_tenant_visible_rows"],
        )
        if snapshot["force_rls"] is not True:
            reasons.append(f"{table} force_rls is not True")
        if snapshot["row_security"] is not True:
            reasons.append(f"{table} row_security is not True")
        if not all(_plain_int(row_count) and row_count >= 0 for row_count in row_counts):
            reasons.append(f"{table} rls row counts are not nonnegative ints")
            continue
        if row_counts[0] != 0:
            reasons.append(f"{table} exposes rows without rls")
        if row_counts[3] != 0:
            reasons.append(f"{table} exposes cross-tenant rows")
        if row_counts[1] != row_counts[2]:
            reasons.append(f"{table} own-tenant rows do not match expected")

    superuser = _field(runtime_role, "superuser")
    bypassrls = _field(runtime_role, "bypassrls")
    if not isinstance(runtime_role, RuntimeRole):
        reasons.append("runtime_role is not a RuntimeRole instance")
    if superuser is not False:
        reasons.append("runtime role superuser is not the bool False")
    if bypassrls is not False:
        reasons.append("runtime role bypassrls is not the bool False")

    insert_sqlstate = _scalar(cross_tenant_insert_sqlstate)
    update_sqlstate = _scalar(evidence_update_sqlstate)
    delete_sqlstate = _scalar(evidence_delete_sqlstate)
    if insert_sqlstate != "42501":
        reasons.append("cross_tenant_insert_sqlstate is not 42501")
    if update_sqlstate != "55000":
        reasons.append("evidence_update_sqlstate is not 55000")
    if delete_sqlstate != "55000":
        reasons.append("evidence_delete_sqlstate is not 55000")

    if not isinstance(post_rollback_counts, Mapping) or set(post_rollback_counts) != set(
        _MEASURED_TABLES
    ):
        reasons.append("post-rollback table counts are incomplete")
        rollback_counts: dict[str, Any] = {}
    else:
        rollback_counts = {
            table: _scalar(post_rollback_counts[table]) for table in _MEASURED_TABLES
        }
        for table, count in rollback_counts.items():
            if not (_plain_int(count) and count == 0):
                reasons.append(f"post-rollback {table} count is not zero")
    if role_absent is not True:
        reasons.append("disposable role remains after rollback")
    if not isinstance(scratch_name, str) or _SCRATCH_NAME.fullmatch(scratch_name) is None:
        reasons.append("scratch database name is invalid")
    if scratch_dropped is not True:
        reasons.append("scratch database was not dropped")

    ordered_reasons = list(dict.fromkeys(reasons))
    return {
        "schema_version": "d4-pgvector-graph-evidence-v1",
        "evidence_class": "measured" if not ordered_reasons else "not_evidence",
        "reasons": ordered_reasons,
        "provenance": {
            "code_base_sha": _scalar(code_base_sha),
            "corpus_digest": _scalar(corpus_digest),
            "input_sha256": _copy_mapping(input_sha256),
            "source_sha256": _copy_mapping(source_sha256),
            "clean_tree": _scalar(clean_tree),
            "alembic_head": _scalar(alembic_head),
            "server_version": _scalar(server_version),
            "vector_version": _scalar(vector_version),
            "versions": _copy_mapping(versions),
        },
        "graph": {
            "built_digest": _scalar(built_graph_digest),
            "reloaded_digest": _scalar(reloaded_graph_digest),
            "built_persisted_contract_digest": _scalar(built_persisted_contract_digest),
            "reloaded_persisted_contract_digest": _scalar(reloaded_persisted_contract_digest),
            "unresolved_cross_refs": {
                "built_count": _scalar(unresolved_cross_ref_count),
                "persistence": "not persisted by the schema",
            },
            "load_preserved_node_order": _scalar(load_preserved_node_order),
            "load_preserved_edge_order": _scalar(load_preserved_edge_order),
            "parity": {
                "identical": _scalar(identical),
                "node_mismatch_ids": list(node_mismatch_ids or ()),
                "edge_mismatch_ids": list(edge_mismatch_ids or ()),
            },
            "evidence_match": "diagnostic semantic join, not a schema foreign key",
        },
        "counts": {
            "node_count": _scalar(node_count),
            "edge_count": _scalar(edge_count),
            "chunk_node_count": _scalar(chunk_node_count),
            "evidence_link_count": _scalar(evidence_link_count),
            "evidence_join_count": _scalar(evidence_join_count),
            "traversal_mismatch_count": _scalar(traversal_mismatch_count),
            "node_mismatch_count": _scalar(node_mismatch_count),
            "edge_mismatch_count": _scalar(edge_mismatch_count),
        },
        "rls_observations": rls_output,
        "runtime_role": {
            "superuser": _scalar(superuser),
            "bypassrls": _scalar(bypassrls),
        },
        "sqlstates": {
            "cross_tenant_insert": insert_sqlstate,
            "evidence_update": update_sqlstate,
            "evidence_delete": delete_sqlstate,
        },
        "post_rollback": {"table_counts": rollback_counts, "role_absent": _scalar(role_absent)},
        "scratch": {"name": _scalar(scratch_name), "dropped": _scalar(scratch_dropped)},
        "limitations": LIMITATIONS,
    }
