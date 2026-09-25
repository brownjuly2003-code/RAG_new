"""Offline checks of the committed D.4 graph-evidence report.

The measurement needs the Mac PostgreSQL, so this test does not re-run it. It pins
the report bytes, tracked input and source blobs at the measurement commit, replays
recorded observations through the committed builder, and holds the capsule, index row
and ADR section to the report's numbers.
"""

import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts import pgvector_graph_evidence as pge
from scripts import pgvector_graph_evidence_run as runner
from tests.capsule_prose import capsule_defects, numeric_claims, prose_lines

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "evaluation" / "d4-pgvector-graph-evidence.json"
CAPSULE = ROOT / "docs" / "evidence" / "d4-pgvector-graph-evidence.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
ADR = ROOT / "docs" / "adr" / "0007-pgvector-spike.md"
ARCHIVE = ROOT / "evaluation" / "gr1b-4436d61-graph-chunks.json.gz"
REPORT_SHA256 = "63ee3b5ec9f8d9638e84ce122c5e41a2fc5e1ae0595f8ca97006e43517f10d7b"
CODE_COMMIT = "67a9dbc9814b8baa4e291158c9fd9a924fce92ab"
ARCHIVE_SHA256 = "2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12"
JSON_SHA256 = "5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94"
ALEMBIC_HEAD = "033"
RLS_TABLES = ("kb_graph_nodes", "kb_graph_edges", "evidence_snapshots", "case_evidence_links")
MEASURED_TABLES = ("support_cases", "case_events", *RLS_TABLES)


@pytest.fixture(scope="module")
def published():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _report_numbers(published) -> tuple[list[float], set[int]]:
    decimals: list[float] = []
    integers: set[int] = set()

    def collect(value):
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, float):
            decimals.append(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            integers.add(value)

    collect(published)
    # The capsule may say how many RLS and post-rollback tables it observed.
    integers.update((len(RLS_TABLES), len(MEASURED_TABLES)))
    return decimals, integers


def test_report_bytes_are_pinned(published):
    raw = REPORT.read_bytes()
    assert _sha256(raw) == REPORT_SHA256
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")

    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    assert json.loads(raw, parse_constant=reject_constant) == published
    assert published["schema_version"] == runner.SCHEMA_VERSION
    assert published["evidence_class"] == "measured"
    assert published["reasons"] == []


def test_input_is_the_tracked_archive(published):
    provenance = published["provenance"]
    archive_bytes = ARCHIVE.read_bytes()
    assert provenance["input_sha256"] == {
        "decompressed_json": JSON_SHA256,
        "gzip_archive": ARCHIVE_SHA256,
    }
    assert _sha256(archive_bytes) == ARCHIVE_SHA256
    assert _sha256(gzip.decompress(archive_bytes)) == JSON_SHA256
    assert provenance["corpus_digest"] == JSON_SHA256
    assert published["counts"]["chunk_node_count"] == runner.EXPECTED_CHUNKS


def test_source_digests_are_the_blobs_at_the_measurement_commit(published):
    provenance = published["provenance"]
    assert provenance["code_base_sha"] == CODE_COMMIT
    assert provenance["clean_tree"] is True
    source_digests = provenance["source_sha256"]
    assert list(source_digests) == list(runner.SOURCE_FILES)
    for relative in runner.SOURCE_FILES:
        blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{relative}"], cwd=ROOT)
        assert b"\r\n" not in blob
        assert source_digests[relative] == _sha256(blob)


def test_recorded_schema_and_versions(published):
    provenance = published["provenance"]
    assert provenance["alembic_head"] == ALEMBIC_HEAD
    paths = subprocess.check_output(
        ["git", "ls-tree", "--name-only", CODE_COMMIT, "alembic/versions/"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    names = [Path(path).name for path in paths]
    assert len([name for name in names if name.startswith("033_")]) == 1
    assert not any(name.startswith("034_") for name in names)
    assert provenance["server_version"].startswith("16.")
    assert provenance["vector_version"] == "0.8.1"
    assert provenance["versions"] == {
        "python": "3.11.15",
        "sqlalchemy": "2.0.52",
        "psycopg2": "2.9.13 (dt dec pq3 ext lo64)",
        "networkx": "3.5",
    }


def test_report_replays_through_the_committed_builder(published):
    provenance = published["provenance"]
    graph = published["graph"]
    counts = published["counts"]
    sqlstates = published["sqlstates"]
    parity = graph["parity"]
    # Arithmetic replay of the verdict under the committed builder, not a second measurement.
    rebuilt = pge.build_evidence_report(
        provenance=pge.Provenance(**provenance),
        parity=pge.GraphParity(
            identical=parity["identical"],
            node_count=counts["node_count"],
            edge_count=counts["edge_count"],
            node_mismatch_count=counts["node_mismatch_count"],
            edge_mismatch_count=counts["edge_mismatch_count"],
            node_mismatch_ids=tuple(parity["node_mismatch_ids"]),
            edge_mismatch_ids=tuple(parity["edge_mismatch_ids"]),
        ),
        traversal_mismatch_count=counts["traversal_mismatch_count"],
        chunk_node_count=counts["chunk_node_count"],
        evidence_link_count=counts["evidence_link_count"],
        evidence_join_count=counts["evidence_join_count"],
        rls_observations=[
            pge.RlsObservation(**row) for row in published["rls_observations"].values()
        ],
        runtime_role=pge.RuntimeRole(**published["runtime_role"]),
        cross_tenant_insert_sqlstate=sqlstates["cross_tenant_insert"],
        evidence_update_sqlstate=sqlstates["evidence_update"],
        evidence_delete_sqlstate=sqlstates["evidence_delete"],
        built_graph_digest=graph["built_digest"],
        reloaded_graph_digest=graph["reloaded_digest"],
        built_persisted_contract_digest=graph["built_persisted_contract_digest"],
        reloaded_persisted_contract_digest=graph["reloaded_persisted_contract_digest"],
        unresolved_cross_ref_count=graph["unresolved_cross_refs"]["built_count"],
        load_preserved_node_order=graph["load_preserved_node_order"],
        load_preserved_edge_order=graph["load_preserved_edge_order"],
        post_rollback_counts=published["post_rollback"]["table_counts"],
        role_absent=published["post_rollback"]["role_absent"],
        scratch_name=published["scratch"]["name"],
        scratch_dropped=published["scratch"]["dropped"],
    )
    assert rebuilt == published


def test_observations_meet_the_spec_thresholds(published):
    graph = published["graph"]
    persisted = graph["built_persisted_contract_digest"]
    assert re.fullmatch(r"[0-9a-f]{64}", persisted)
    assert graph["reloaded_persisted_contract_digest"] == persisted
    assert graph["reloaded_digest"] == persisted
    assert re.fullmatch(r"[0-9a-f]{64}", graph["built_digest"])
    assert graph["built_digest"] != persisted
    assert graph["unresolved_cross_refs"] == {
        "built_count": 5877,
        "persistence": "not persisted by the schema",
    }
    assert graph["load_preserved_node_order"] is True
    assert graph["load_preserved_edge_order"] is True
    assert graph["parity"] == {
        "identical": True,
        "node_mismatch_ids": [],
        "edge_mismatch_ids": [],
    }
    assert graph["evidence_match"] == "diagnostic semantic join, not a schema foreign key"
    assert published["counts"] == {
        "node_count": 10300,
        "edge_count": 17327,
        "chunk_node_count": 5589,
        "evidence_link_count": 5589,
        "evidence_join_count": 5589,
        "traversal_mismatch_count": 0,
        "node_mismatch_count": 0,
        "edge_mismatch_count": 0,
    }
    observations = published["rls_observations"]
    assert list(observations) == list(RLS_TABLES)
    for table, expected in zip(RLS_TABLES, (10300, 17327, 5589, 5589), strict=True):
        row = observations[table]
        assert row["table_name"] == table
        assert row["row_security"] is True
        assert row["force_rls"] is True
        assert row["unset_visible_rows"] == 0
        assert row["cross_tenant_visible_rows"] == 0
        assert row["own_tenant_rows"] == row["expected_own_rows"] == expected
    assert published["runtime_role"] == {"superuser": False, "bypassrls": False}
    assert published["sqlstates"] == {
        "cross_tenant_insert": "42501",
        "evidence_update": "55000",
        "evidence_delete": "55000",
    }
    assert published["post_rollback"] == {
        "table_counts": {table: 0 for table in MEASURED_TABLES},
        "role_absent": True,
    }
    assert list(published["post_rollback"]["table_counts"]) == list(MEASURED_TABLES)
    assert re.fullmatch(r"rag_spike_d4_[0-9a-f]{16}", published["scratch"]["name"])
    assert published["scratch"]["dropped"] is True


def test_capsule_quotes_only_report_numbers(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert capsule_defects(capsule, decimals=decimals, integers=integers) == []
    claims = numeric_claims("\n".join(prose_lines(capsule)))
    prose_integers = {int(claim) for claim in claims if claim.isdecimal()}
    assert {10300, 17327, 5589, 5877} <= prose_integers


def test_capsule_number_check_rejects_an_unreported_number(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert "10300" in "\n".join(prose_lines(capsule))
    changed = capsule.replace("10300", "10301", 1)
    assert "10301" in "\n".join(prose_lines(changed))
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any("prose quotes 10301," in defect for defect in defects)

    unreported = next(value for value in range(21, max(integers) + 2) if value not in integers)
    changed = capsule + f"\nThe unrelated count is {unreported}.\n"
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any(f"prose quotes {unreported}," in defect for defect in defects)


def test_capsule_names_digests_and_limits(published):
    capsule = CAPSULE.read_text(encoding="utf-8")

    allowed_digests = {REPORT_SHA256}

    def collect_digest_leaves(value):
        if isinstance(value, dict):
            for item in value.values():
                collect_digest_leaves(item)
        elif isinstance(value, list):
            for item in value:
                collect_digest_leaves(item)
        elif isinstance(value, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
            allowed_digests.add(value)

    collect_digest_leaves(published)
    capsule_digests = set(re.findall(r"(?<![0-9a-f])[0-9a-f]{40,}(?![0-9a-f])", capsule))
    assert capsule_digests - allowed_digests == set()
    for digest in published["provenance"]["source_sha256"].values():
        assert digest in capsule

    for value in (
        REPORT_SHA256,
        CODE_COMMIT,
        ARCHIVE_SHA256,
        JSON_SHA256,
        published["graph"]["built_persisted_contract_digest"],
        published["graph"]["built_digest"],
    ):
        assert value in capsule
    for phrase in (
        "persisted contract",
        "not persisted",
        "diagnostic semantic join",
        "NOT_EVIDENCE",
        "cold-start",
        "no migration decision",
    ):
        assert phrase in capsule


def test_evidence_index_row_points_at_capsule_report_and_test(published):
    rows = [
        line
        for line in INDEX.read_text(encoding="utf-8").splitlines()
        if "docs/evidence/d4-pgvector-graph-evidence.md" in line
    ]
    assert len(rows) == 1
    row = rows[0]
    assert "evaluation/d4-pgvector-graph-evidence.json" in row
    assert "tests/test_pgvector_graph_evidence_artifact.py" in row
    assert "measured" in row
    decimals, integers = _report_numbers(published)
    assert capsule_defects(row, decimals=decimals, integers=integers) == []


def test_adr_d4_section_quotes_the_report(published):
    adr = ADR.read_text(encoding="utf-8")
    heading = "## D.4 graph and evidence numbers"
    assert len(re.findall(r"(?m)^## D\.4 graph and evidence numbers$", adr)) == 1
    section = adr.split(heading, 1)[1].split("\n## ", 1)[0]
    decimals, integers = _report_numbers(published)
    assert capsule_defects(section, decimals=decimals, integers=integers) == []
    for number in (10300, 17327, 5589, 5877):
        assert str(number) in section
    status = next(line for line in adr.splitlines() if line.startswith("Status:"))
    assert "D.1–D.4 measured" in status
    assert "../evidence/d4-pgvector-graph-evidence.md" in adr


def test_publication_separates_tenant_isolation_and_append_only():
    capsule = CAPSULE.read_text(encoding="utf-8")
    verdict = capsule.split("## Numbers", 1)[0]
    adr = ADR.read_text(encoding="utf-8")
    d4 = adr.split("## D.4 graph and evidence numbers", 1)[1].split("\n## ", 1)[0]
    limits = adr.split("## Isolation and limits", 1)[1].split("\n## ", 1)[0]

    assert "tenant isolation" in verdict
    assert "append-only evidence" in verdict
    assert "tenant policies held" not in verdict
    assert "tenant isolation" in d4
    assert "append-only evidence" in d4
    assert "cross-tenant insert" in d4
    assert "evidence update and delete" in " ".join(d4.split())
    assert "tenant isolation" in limits
    assert "append-only evidence" in limits
    assert "tenant write policies" not in adr


def test_capsule_acceptance_run_names_its_fixture_without_a_count():
    capsule = CAPSULE.read_text(encoding="utf-8")
    verification = capsule.split("## Verification", 1)[1].split("\n## ", 1)[0]
    acceptance = next(
        paragraph for paragraph in verification.split("\n\n") if "acceptance test" in paragraph
    )

    assert "`tests/test_pgvector_graph_evidence_db.py`" in acceptance
    assert "RESOLUTION_ADMIN_DATABASE_URL" in acceptance
    assert "Mac" in acceptance
    assert "synthetic fixture" in acceptance
    assert "T-41" in acceptance
    assert "2026-09-25" in acceptance
    assert not re.search(r"\b(?:five|5)\b", acceptance, flags=re.IGNORECASE)
