"""Production evidence joins, RLS evidence, and fail-closed reporting tests."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from scripts.pgvector_graph_evidence import (
    GraphParity,
    Provenance,
    RlsObservation,
    RuntimeRole,
    build_evidence_report,
    production_evidence_join_sql,
)

HEX40 = "a" * 40
HEX64 = "b" * 64
OTHER64 = "c" * 64
TABLES = ("kb_graph_nodes", "kb_graph_edges", "evidence_snapshots", "case_evidence_links")
OWN_COUNTS = {
    "kb_graph_nodes": 12,
    "kb_graph_edges": 24,
    "evidence_snapshots": 12,
    "case_evidence_links": 12,
}


def _parity(node_mismatches=0, edge_mismatches=0, node_ids=(), edge_ids=()):
    return GraphParity(
        identical=node_mismatches == 0 and edge_mismatches == 0,
        node_count=12,
        edge_count=24,
        node_mismatch_count=node_mismatches,
        edge_mismatch_count=edge_mismatches,
        node_mismatch_ids=tuple(node_ids),
        edge_mismatch_ids=tuple(edge_ids),
    )


def _rls(**per_table):
    observations = []
    for table in TABLES:
        fields = {
            "table_name": table,
            "row_security": True,
            "force_rls": True,
            "unset_visible_rows": 0,
            "own_tenant_rows": OWN_COUNTS[table],
            "expected_own_rows": OWN_COUNTS[table],
            "cross_tenant_visible_rows": 0,
        }
        fields.update(per_table.get(table, {}))
        observations.append(RlsObservation(**fields))
    return tuple(observations)


def _provenance():
    return Provenance(
        HEX40,
        HEX64,
        {"inputs/evidence.json": HEX64},
        {"src/evidence.rs": OTHER64},
        clean_tree=True,
        alembic_head="033",
        server_version="16.4",
        vector_version="0.7.4",
        versions={
            "python": "3.11",
            "sqlalchemy": "2.0",
            "psycopg2": "2.9",
            "networkx": "3.0",
        },
    )


def _inputs(**overrides):
    params = {
        "provenance": _provenance(),
        "parity": _parity(),
        "traversal_mismatch_count": 0,
        "chunk_node_count": 12,
        "evidence_link_count": 12,
        "evidence_join_count": 12,
        "rls_observations": _rls(),
        "runtime_role": RuntimeRole(superuser=False, bypassrls=False),
        "cross_tenant_insert_sqlstate": "42501",
        "evidence_update_sqlstate": "55000",
        "evidence_delete_sqlstate": "55000",
        "built_graph_digest": HEX64,
        "reloaded_graph_digest": HEX64,
        "built_persisted_contract_digest": HEX64,
        "reloaded_persisted_contract_digest": HEX64,
        "unresolved_cross_ref_count": 0,
        "load_preserved_node_order": True,
        "load_preserved_edge_order": True,
        "post_rollback_counts": dict.fromkeys(("support_cases", "case_events", *TABLES), 0),
        "role_absent": True,
        "scratch_name": "rag_spike_d4_0123456789abcdef",
        "scratch_dropped": True,
    }
    params.update(overrides)
    return params


FAIL_CASES = [
    pytest.param({"parity": _parity(node_mismatches=1, node_ids=("node-7",))}, id="node-mismatch"),
    pytest.param({"parity": _parity(edge_mismatches=2, edge_ids=("edge-4",))}, id="edge-mismatch"),
    pytest.param({"traversal_mismatch_count": 1}, id="traversal-mismatch"),
    pytest.param({"evidence_join_count": 5}, id="link-join-count-mismatch"),
    pytest.param({"chunk_node_count": 0}, id="zero-chunk-nodes"),
    pytest.param({"rls_observations": _rls()[:3]}, id="force-rls-incomplete"),
    pytest.param(
        {"rls_observations": _rls(kb_graph_edges={"force_rls": False})}, id="force-rls-false"
    ),
    pytest.param(
        {"rls_observations": _rls(kb_graph_nodes={"unset_visible_rows": 1})},
        id="unset-row-visibility",
    ),
    pytest.param(
        {"rls_observations": _rls(evidence_snapshots={"cross_tenant_visible_rows": 2})},
        id="cross-tenant-row-visibility",
    ),
    pytest.param(
        {"rls_observations": _rls(case_evidence_links={"own_tenant_rows": 5})},
        id="own-count-mismatch",
    ),
    pytest.param(
        {"runtime_role": RuntimeRole(superuser=True, bypassrls=False)}, id="superuser-role"
    ),
    pytest.param(
        {"runtime_role": RuntimeRole(superuser=False, bypassrls=True)}, id="bypassrls-role"
    ),
    pytest.param({"cross_tenant_insert_sqlstate": "00000"}, id="insert-sqlstate-wrong"),
    pytest.param({"cross_tenant_insert_sqlstate": None}, id="insert-sqlstate-missing"),
    pytest.param({"evidence_update_sqlstate": "42501"}, id="update-sqlstate-wrong"),
    pytest.param({"evidence_delete_sqlstate": None}, id="delete-sqlstate-missing"),
    pytest.param(
        {"provenance": replace(_provenance(), code_base_sha="a" * 39)},
        id="code-base-malformed",
    ),
    pytest.param(
        {"provenance": replace(_provenance(), corpus_digest="z" * 64)},
        id="corpus-digest-malformed",
    ),
    pytest.param(
        {"provenance": replace(_provenance(), input_sha256={"inputs/evidence.json": "not-hex"})},
        id="input-sha-malformed",
    ),
    pytest.param(
        {"provenance": replace(_provenance(), source_sha256={})},
        id="source-sha-missing",
    ),
    pytest.param({"provenance": None}, id="provenance-missing"),
    pytest.param({"parity": None}, id="parity-missing"),
    pytest.param(
        {"parity": replace(_parity(node_mismatches=1), identical=True)},
        id="parity-contradictory",
    ),
    pytest.param({"chunk_node_count": True}, id="bool-chunk-node-count"),
    pytest.param({"evidence_link_count": False}, id="bool-evidence-link-count"),
    pytest.param({"traversal_mismatch_count": -1}, id="negative-traversal-mismatch"),
    pytest.param({"evidence_join_count": -3}, id="negative-join-count"),
    pytest.param({"provenance": replace(_provenance(), clean_tree=False)}, id="dirty-tree"),
    pytest.param({"reloaded_persisted_contract_digest": OTHER64}, id="graph-digest-drift"),
    pytest.param(
        {"rls_observations": _rls(kb_graph_nodes={"row_security": False})}, id="rls-disabled"
    ),
    pytest.param({"role_absent": False}, id="role-remains"),
    pytest.param({"scratch_dropped": False}, id="scratch-remains"),
    pytest.param(
        {"post_rollback_counts": {**_inputs()["post_rollback_counts"], "case_events": 1}},
        id="row-remains",
    ),
    pytest.param({"rls_observations": _rls() + (_rls()[0],)}, id="duplicate-rls-observation"),
    pytest.param(
        {"rls_observations": _rls() + (replace(_rls()[0], table_name="kb_extra_table"),)},
        id="unexpected-rls-observation",
    ),
    pytest.param(
        {"runtime_role": RuntimeRole(superuser=1, bypassrls=False)}, id="superuser-not-bool"
    ),
]


def test_clean_inputs_yield_measured_json_report_with_exact_observations():
    report = build_evidence_report(**_inputs())
    assert report["schema_version"] == "d4-pgvector-graph-evidence-v1"
    assert report["evidence_class"] == "measured"
    assert report["reasons"] == []
    provenance = report["provenance"]
    assert provenance["code_base_sha"] == HEX40
    assert provenance["corpus_digest"] == HEX64
    assert provenance["input_sha256"] == {"inputs/evidence.json": HEX64}
    assert provenance["source_sha256"] == {"src/evidence.rs": OTHER64}
    counts = report["counts"]
    assert counts["node_count"] == 12
    assert counts["edge_count"] == 24
    assert counts["chunk_node_count"] == 12
    assert counts["evidence_link_count"] == 12
    assert counts["evidence_join_count"] == 12
    assert counts["traversal_mismatch_count"] == 0
    assert counts["node_mismatch_count"] == counts["edge_mismatch_count"] == 0
    assert report["graph"]["built_persisted_contract_digest"] == HEX64
    assert report["graph"]["reloaded_persisted_contract_digest"] == HEX64
    assert report["graph"]["unresolved_cross_refs"]["built_count"] == 0
    assert report["graph"]["load_preserved_node_order"] is True
    assert report["graph"]["load_preserved_edge_order"] is True
    assert report["rls_observations"] == {obs.table_name: asdict(obs) for obs in _rls()}
    assert set(report["rls_observations"]) == set(TABLES)
    assert report["runtime_role"] == {"superuser": False, "bypassrls": False}
    sqlstates = report["sqlstates"]
    assert sqlstates["cross_tenant_insert"] == "42501"
    assert sqlstates["evidence_update"] == "55000"
    assert sqlstates["evidence_delete"] == "55000"
    json.dumps(report)
    assert report == build_evidence_report(**_inputs())


def test_persisted_contract_parity_ignores_raw_digest_and_order_diagnostics():
    report = build_evidence_report(
        **_inputs(
            built_graph_digest=OTHER64,
            reloaded_graph_digest=HEX64,
            built_persisted_contract_digest=HEX64,
            reloaded_persisted_contract_digest=HEX64,
            unresolved_cross_ref_count=4,
            load_preserved_node_order=False,
            load_preserved_edge_order=False,
        )
    )
    assert report["evidence_class"] == "measured"
    assert report["graph"]["built_digest"] == OTHER64
    assert report["graph"]["built_persisted_contract_digest"] == HEX64
    assert report["graph"]["reloaded_persisted_contract_digest"] == HEX64
    assert report["graph"]["unresolved_cross_refs"] == {
        "built_count": 4,
        "persistence": "not persisted by the schema",
    }
    assert report["graph"]["load_preserved_node_order"] is False
    assert report["graph"]["load_preserved_edge_order"] is False


def test_persisted_contract_digest_drift_names_parity_failure():
    report = build_evidence_report(**_inputs(reloaded_persisted_contract_digest=OTHER64))
    assert report["evidence_class"] == "not_evidence"
    assert any(
        "parity persisted-contract digest mismatch" in reason for reason in report["reasons"]
    )


def _report_for_structural_graph_pair(built, reloaded):
    pytest.importorskip("langchain_core")
    from ingestion.structure_graph_projection import (
        project_structure_graph,
        structure_graph_digest,
    )
    from scripts import pgvector_graph_evidence_run as runner
    from scripts.pgvector_graph_evidence import graph_parity

    built_projection = project_structure_graph(built)
    reloaded_projection = project_structure_graph(reloaded)
    return build_evidence_report(
        **_inputs(
            parity=graph_parity(built_projection, reloaded_projection),
            traversal_mismatch_count=runner._traversal_mismatch_count(
                built_projection, reloaded_projection
            ),
            built_graph_digest=structure_graph_digest(built),
            reloaded_graph_digest=structure_graph_digest(reloaded),
            built_persisted_contract_digest=structure_graph_digest(
                runner._persisted_graph_contract(built)
            ),
            reloaded_persisted_contract_digest=structure_graph_digest(
                runner._persisted_graph_contract(reloaded)
            ),
            unresolved_cross_ref_count=len(built.unresolved_cross_refs),
            load_preserved_node_order=tuple(node.node_id for node in built.nodes)
            == tuple(node.node_id for node in reloaded.nodes),
            load_preserved_edge_order=tuple(edge.edge_id for edge in built.edges)
            == tuple(edge.edge_id for edge in reloaded.edges),
        )
    )


def test_unresolved_cross_references_are_not_persisted_but_parity_holds():
    pytest.importorskip("langchain_core")
    from ingestion.structure_graph import build_structural_graph
    from ingestion.structure_graph_projection import structure_graph_digest

    chunk = SimpleNamespace(
        page_content="Refer to missing.md for the missing procedure.",
        metadata={"source": "alpha.md", "chunk_index": 0, "h1": "Section"},
    )
    built = build_structural_graph([chunk], tenant_id="359dcdf9-4096-5229-a37c-4d78b7474f6a")
    reloaded = replace(built, unresolved_cross_refs=())

    assert len(built.unresolved_cross_refs) >= 1
    assert structure_graph_digest(built) != structure_graph_digest(reloaded)
    report = _report_for_structural_graph_pair(built, reloaded)
    assert report["evidence_class"] == "measured"
    assert (
        report["graph"]["built_persisted_contract_digest"]
        == report["graph"]["reloaded_persisted_contract_digest"]
    )
    assert report["graph"]["unresolved_cross_refs"]["built_count"] >= 1


def test_reversed_load_order_keeps_parity_and_records_both_flags():
    pytest.importorskip("langchain_core")
    from ingestion.structure_graph import build_structural_graph

    chunks = [
        SimpleNamespace(
            page_content=f"Chunk {index}.",
            metadata={"source": source, "chunk_index": index, "h1": "Section"},
        )
        for source, index in (("alpha.md", 0), ("beta.md", 0))
    ]
    built = build_structural_graph(chunks, tenant_id="359dcdf9-4096-5229-a37c-4d78b7474f6a")
    reloaded = replace(
        built,
        nodes=tuple(reversed(built.nodes)),
        edges=tuple(reversed(built.edges)),
        unresolved_cross_refs=(),
    )

    assert len(built.nodes) > 1 and len(built.edges) > 1
    report = _report_for_structural_graph_pair(built, reloaded)
    assert report["evidence_class"] == "measured"
    assert report["graph"]["load_preserved_node_order"] is False
    assert report["graph"]["load_preserved_edge_order"] is False


def test_reloaded_edge_attribute_drift_still_fails_parity():
    pytest.importorskip("langchain_core")
    from ingestion.structure_graph import build_structural_graph

    chunk = SimpleNamespace(
        page_content="Chunk 0.",
        metadata={"source": "alpha.md", "chunk_index": 0, "h1": "Section"},
    )
    built = build_structural_graph([chunk], tenant_id="359dcdf9-4096-5229-a37c-4d78b7474f6a")
    drifted_edge = replace(built.edges[0], attributes={"drift": True})
    reloaded = replace(built, edges=(drifted_edge, *built.edges[1:]), unresolved_cross_refs=())

    report = _report_for_structural_graph_pair(built, reloaded)
    assert report["evidence_class"] == "not_evidence"
    assert any("parity" in reason for reason in report["reasons"])


def test_input_mappings_are_copied_so_later_mutation_cannot_alter_report():
    input_sha256 = {"inputs/evidence.json": HEX64}
    source_sha256 = {"src/evidence.rs": OTHER64}
    provenance = Provenance(HEX40, HEX64, input_sha256, source_sha256)
    report = build_evidence_report(**_inputs(provenance=provenance))
    input_sha256["inputs/evidence.json"] = "f" * 64
    input_sha256["tampered.txt"] = "0" * 64
    source_sha256.clear()
    assert report["provenance"]["input_sha256"] == {"inputs/evidence.json": HEX64}
    assert report["provenance"]["source_sha256"] == {"src/evidence.rs": OTHER64}
    json.dumps(report)


@pytest.mark.parametrize("overrides", FAIL_CASES)
def test_fail_closed_inputs_are_never_measured(overrides):
    report = build_evidence_report(**_inputs(**overrides))
    assert report["evidence_class"] == "not_evidence"
    reasons = report["reasons"]
    assert isinstance(reasons, list) and reasons
    assert all(isinstance(reason, str) and reason for reason in reasons)
    repeat = build_evidence_report(**_inputs(**overrides))
    assert repeat["reasons"] == reasons
    assert repeat["evidence_class"] == "not_evidence"
    assert "measured" not in report["evidence_class"]
    json.dumps(report)


@pytest.mark.parametrize(
    ("field", "invalid", "reason_field"),
    [
        ("code_base_sha", "a" * 39, "code_base_sha"),
        ("corpus_digest", "z" * 64, "corpus_digest"),
        ("input_sha256", {"inputs/evidence.json": "not-hex"}, "input_sha256"),
        ("source_sha256", {}, "source_sha256"),
    ],
)
def test_invalid_provenance_reason_names_its_field(field, invalid, reason_field):
    provenance = replace(_provenance(), **{field: invalid})
    report = build_evidence_report(**_inputs(provenance=provenance))
    assert report["evidence_class"] == "not_evidence"
    assert any(reason_field in reason for reason in report["reasons"])
    assert len(report["reasons"]) == 1


def test_report_reasons_name_parity_join_probe_dirty_tree_and_cleanup() -> None:
    report = build_evidence_report(
        **_inputs(
            provenance=replace(_provenance(), clean_tree=False),
            parity=_parity(edge_mismatches=1, edge_ids=("edge-1",)),
            evidence_join_count=11,
            cross_tenant_insert_sqlstate="00000",
            role_absent=False,
            scratch_dropped=False,
        )
    )
    assert report["evidence_class"] == "not_evidence"
    reasons = " ".join(report["reasons"])
    for required in ("dirty", "parity", "counts", "cross_tenant_insert", "role", "scratch"):
        assert required in reasons
    assert "SELECT" not in reasons
    assert "topsecret" not in reasons


def test_non_finite_measurements_normalize_to_none_and_fail_closed_strict_json():
    overrides = {
        "chunk_node_count": float("nan"),
        "evidence_link_count": float("inf"),
        "evidence_join_count": float("-inf"),
        "provenance": Provenance(
            HEX40,
            HEX64,
            {"inputs/evidence.json": float("nan")},
            {"src/evidence.rs": float("inf")},
        ),
    }
    report = build_evidence_report(**_inputs(**overrides))
    assert report["evidence_class"] == "not_evidence"
    assert report["reasons"]
    counts = report["counts"]
    assert counts["chunk_node_count"] is None
    assert counts["evidence_link_count"] is None
    assert counts["evidence_join_count"] is None
    provenance = report["provenance"]
    assert provenance["input_sha256"] == {"inputs/evidence.json": None}
    assert provenance["source_sha256"] == {"src/evidence.rs": None}
    json.dumps(report, allow_nan=False)


def test_rls_observation_order_does_not_change_json_or_table_key_order():
    forward = build_evidence_report(**_inputs())
    reverse = build_evidence_report(**_inputs(rls_observations=tuple(reversed(_rls()))))
    assert forward["evidence_class"] == reverse["evidence_class"] == "measured"
    assert json.dumps(forward, allow_nan=False) == json.dumps(reverse, allow_nan=False)
    assert list(forward["rls_observations"]) == list(TABLES)
    assert list(reverse["rls_observations"]) == list(TABLES)


@pytest.mark.parametrize(
    "rls_observations",
    [
        pytest.param("kb_graph_nodes", id="string-container"),
        pytest.param(b"kb_graph_nodes", id="bytes-container"),
        pytest.param(bytearray(b"kb_graph_nodes"), id="bytearray-container"),
        pytest.param({"kb_graph_nodes": _rls()[0]}, id="mapping-container"),
    ],
)
def test_malformed_rls_containers_fail_closed_and_stay_strict_json(rls_observations):
    report = build_evidence_report(**_inputs(rls_observations=rls_observations))
    assert report["evidence_class"] == "not_evidence"
    assert isinstance(report["reasons"], list) and report["reasons"]
    json.dumps(report, allow_nan=False)


def test_unexpected_rls_order_is_deterministic_across_fail_closed_reports():
    first = replace(_rls()[0], table_name="kb_extra_alpha")
    second = replace(_rls()[0], table_name="kb_extra_beta")
    forward = build_evidence_report(**_inputs(rls_observations=_rls() + (first, second)))
    reverse = build_evidence_report(**_inputs(rls_observations=_rls() + (second, first)))
    assert forward["evidence_class"] == "not_evidence"
    assert reverse["evidence_class"] == "not_evidence"
    assert forward["reasons"] == reverse["reasons"]
    assert json.dumps(forward, allow_nan=False) == json.dumps(reverse, allow_nan=False)
    expected_keys = [*TABLES, *sorted(["kb_extra_beta", "kb_extra_alpha"])]
    assert list(forward["rls_observations"]) == expected_keys
    assert list(reverse["rls_observations"]) == expected_keys


def _normalized_sql():
    return re.sub(r"\s+", " ", production_evidence_join_sql()).strip().lower()


def test_sql_starts_from_links_and_joins_snapshots_on_evidence_id_and_tenant():
    sql = _normalized_sql()
    from_clause = re.search(r"\bfrom\s+(.*?)(?=\s+join\b)", sql)
    assert from_clause and from_clause.group(1).startswith("public.case_evidence_links")
    snapshot = re.search(
        r"\bjoin\s+public\.evidence_snapshots\s+(?:as\s+)?(\w+)\s+on\s+(.*?)"
        r"(?=\s+join\b|\bwhere\b|\bgroup\b|\border\b|\Z)",
        sql,
    )
    assert snapshot
    alias, join_on = snapshot.group(1), snapshot.group(2)
    assert re.search(rf"\b{alias}\.id\s*=\s*\w+\.evidence_id", join_on)
    assert re.search(rf"\b{alias}\.tenant_id\s*=\s*\w+\.tenant_id", join_on)


def test_sql_joins_chunk_nodes_on_tenant_natural_key_and_content_digest():
    sql = _normalized_sql()
    node = re.search(
        r"\bjoin\s+public\.kb_graph_nodes\s+(?:as\s+)?(\w+)\s+on\s+(.*?)"
        r"(?=\s+join\b|\bwhere\b|\bgroup\b|\border\b|\Z)",
        sql,
    )
    assert node
    alias, join_on = node.group(1), node.group(2)
    assert re.search(rf"\b{alias}\.tenant_id\s*=\s*\w+\.tenant_id", join_on)
    assert re.search(rf"\b{alias}\.tenant_id\s*=\s*\w+\.tenant_id\s*::\s*text", join_on)
    assert not re.search(rf"\b{alias}\.tenant_id\s*::\s*uuid", join_on)
    assert not re.search(rf"\bcast\s*\(\s*{alias}\.tenant_id\s+as\s+uuid\s*\)", join_on)
    assert re.search(rf"\b{alias}\.natural_key\s*=\s*\w+\.source_id", join_on)
    assert re.search(
        rf"\b{alias}\.attributes\s*->>\s*'content_sha256'\s*=\s*\w+\.content_digest", join_on
    )
    assert re.search(rf"\b{alias}\.kind\s*=\s*'chunk'", sql)


def test_sql_selects_stable_ids_and_orders_deterministically_without_spike_schema():
    sql = _normalized_sql()
    select_list = sql.split(" from ", 1)[0]
    assert "node_id" in select_list and "evidence_id" in select_list
    order_by = re.search(r"\border\s+by\s+(.+)\Z", sql)
    assert order_by and ("node_id" in order_by.group(1) or "natural_key" in order_by.group(1))
    assert "random" not in sql
    assert "spike_chunks" not in sql and "chunk_idx" not in sql
