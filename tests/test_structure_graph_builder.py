"""GR-1 structural graph builder: deterministic metadata-only extraction."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ingestion.structure_graph import build_structural_graph


def _chunk(content: str, **metadata: Any) -> SimpleNamespace:
    return SimpleNamespace(page_content=content, metadata=metadata)


def _nodes_by_kind(graph, kind: str):
    return [node for node in graph.nodes if node.kind == kind]


def _edge_labels(graph, kind: str) -> set[tuple[str, str]]:
    nodes = {node.node_id: node for node in graph.nodes}
    return {
        (nodes[edge.source_node_id].label, nodes[edge.target_node_id].label)
        for edge in graph.edges
        if edge.kind == kind
    }


def test_builder_creates_deterministic_document_section_chunk_tree() -> None:
    chunks = [
        _chunk(
            "# Guide\n## 1. Start\nFirst half",
            source="guide.md",
            chunk_index=0,
            categories=["shipping"],
            h1="Guide",
            h2="1. Start",
        ),
        _chunk(
            "Second half",
            source="guide.md",
            chunk_index=1,
            categories=["shipping"],
            h1="Guide",
            h2="1. START",
        ),
        _chunk(
            "## 2. Escalation\nEscalate",
            source="guide.md",
            chunk_index=2,
            categories=["shipping"],
            h1="Guide",
            h2="2. Escalation",
        ),
        _chunk(
            "# Carrier policy\nBody",
            source="carrier.md",
            chunk_index=3,
            categories=["shipping", "shipping"],
            h1="Carrier policy",
        ),
    ]

    graph = build_structural_graph(chunks, tenant_id="acme")

    assert graph.builder_version == "gr1-structural-v1"
    assert len(_nodes_by_kind(graph, "document")) == 2
    assert len(_nodes_by_kind(graph, "section")) == 3
    assert len(_nodes_by_kind(graph, "chunk")) == 4
    assert [node.label for node in _nodes_by_kind(graph, "category")] == ["shipping"]

    assert len([edge for edge in graph.edges if edge.kind == "contains"]) == 7
    assert _edge_labels(graph, "next") == {
        ("guide.md#chunk-0", "guide.md#chunk-1"),
        ("guide.md#chunk-1", "guide.md#chunk-2"),
    }
    assert _edge_labels(graph, "same_section") == {
        ("guide.md#chunk-0", "guide.md#chunk-1")
    }
    assert _edge_labels(graph, "category") == {
        ("guide.md", "shipping"),
        ("carrier.md", "shipping"),
    }
    assert graph == build_structural_graph(chunks, tenant_id="acme")


def test_builder_resolves_file_and_local_section_cross_references() -> None:
    chunks = [
        _chunk(
            "См. п. 2.2 и документ carrier_order_42.md.",
            source="guide.md",
            chunk_index=0,
            categories=["shipping"],
            h1="Guide",
            h2="1. Intake",
        ),
        _chunk(
            "## 2.2 Эскалация\nПорядок эскалации.",
            source="guide.md",
            chunk_index=1,
            categories=["shipping"],
            h1="Guide",
            h2="2.2 Эскалация",
        ),
        _chunk(
            "# Приказ № 42\nПравила перевозчика.",
            source="carrier_order_42.md",
            chunk_index=2,
            categories=["shipping"],
            h1="Приказ № 42",
        ),
    ]

    graph = build_structural_graph(chunks, tenant_id="acme")
    targets = {
        (nodes.kind, nodes.label)
        for nodes in (
            {node.node_id: node for node in graph.nodes}[edge.target_node_id]
            for edge in graph.edges
            if edge.kind == "cross_ref"
        )
    }

    assert targets == {
        ("document", "carrier_order_42.md"),
        ("section", "guide.md › Guide › 2.2 Эскалация"),
    }
    assert graph.unresolved_cross_refs == ()


def test_builder_records_only_explicit_unresolved_cross_references() -> None:
    graph = build_structural_graph(
        [
            _chunk(
                "См. missing_policy.md. Приказ № 999. "
                "Увольнение допускается по п. 5 ч. 1 ст. 81 ТК РФ.",
                source="guide.md",
                chunk_index=0,
                categories=["hr"],
                h1="Guide",
            )
        ],
        tenant_id="acme",
    )

    assert {
        (reference.reference_kind, reference.raw_reference)
        for reference in graph.unresolved_cross_refs
    } == {
        ("file", "missing_policy.md"),
        ("order", "Приказ № 999"),
    }


def test_builder_keeps_headingless_chunks_under_a_synthetic_section() -> None:
    graph = build_structural_graph(
        [
            _chunk(
                "Plain extracted page",
                source="scan.pdf",
                chunk_index=7,
                categories=[],
                page=3,
            )
        ],
        tenant_id="acme",
    )

    section = _nodes_by_kind(graph, "section")[0]
    assert section.label == "scan.pdf › (root)"
    assert section.attributes["heading_path"] == []
    assert section.attributes["synthetic"] is True
    assert _edge_labels(graph, "category") == {("scan.pdf", "uncategorized")}
