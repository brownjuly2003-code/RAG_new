"""Deterministic structural graph extraction for GR-1.

The builder consumes the metadata already produced by ingestion and performs
no model or embedding calls.  Persistence and the NetworkX projection are
separate layers; this module is the portable, unit-testable graph contract.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal
from uuid import UUID, uuid5

STRUCTURAL_GRAPH_BUILDER_VERSION = "gr1-structural-v1"

NodeKind = Literal["document", "section", "chunk", "category"]
EdgeKind = Literal["contains", "next", "same_section", "cross_ref", "category"]
ReferenceKind = Literal["file", "section", "order"]

_GRAPH_NAMESPACE = UUID("84a48f8c-d00b-5b10-a244-bc07a44dc331")
_HEADING_KEYS = ("h1", "h2", "h3", "h4")
_FILE_REFERENCE_RE = re.compile(
    r"(?iu)(?<![\w.-])([\w.-]+\.(?:md|pdf|docx|txt|json|csv|html?))(?!\w)"
)
_SECTION_REFERENCE_RE = re.compile(
    r"(?iu)\b(?:см\.\s*)?(?:п\.|пункт(?:а|е)?|раздел(?:а|е)?)\s*"
    r"(\d+(?:\.\d+)+)\b"
)
_HEADING_NUMBER_RE = re.compile(
    r"(?iu)^\s*(?:§\s*|п\.\s*|пункт\s+|раздел\s+)?(\d+(?:\.\d+)*)"
)
_QUOTED_REFERENCE_RE = re.compile(
    r"(?iu)\bсм\.\s*[^«»\"\n]{0,48}[«\"]([^»\"\n]{2,128})[»\"]"
)
_ORDER_REFERENCE_RE = re.compile(
    r"(?iu)\bприказ\s*№\s*[a-zа-яё0-9][\w./-]*"
)


@dataclass(frozen=True)
class StructuralGraphNode:
    node_id: str
    tenant_id: str
    kind: NodeKind
    natural_key: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuralGraphEdge:
    edge_id: str
    tenant_id: str
    kind: EdgeKind
    source_node_id: str
    target_node_id: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnresolvedCrossReference:
    source_node_id: str
    reference_kind: ReferenceKind
    raw_reference: str
    reason: Literal["not_found", "ambiguous"]


@dataclass(frozen=True)
class StructuralGraph:
    tenant_id: str
    builder_version: str
    nodes: tuple[StructuralGraphNode, ...]
    edges: tuple[StructuralGraphEdge, ...]
    unresolved_cross_refs: tuple[UnresolvedCrossReference, ...]


@dataclass(frozen=True)
class _ChunkRecord:
    input_index: int
    order: int
    document_key: str
    document_label: str
    heading_path: tuple[str, ...]
    categories: tuple[str, ...]
    content: str
    metadata: Mapping[str, Any]


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _lookup_key(value: str) -> str:
    normalized = value.casefold().replace("№", " ")
    return " ".join(re.findall(r"[a-zа-яё0-9]+", normalized, flags=re.IGNORECASE))


def _stable_id(tenant_id: str, kind: str, natural_key: str) -> str:
    return str(uuid5(_GRAPH_NAMESPACE, f"{tenant_id}\x1f{kind}\x1f{natural_key}"))


def _document_identity(metadata: Mapping[str, Any], input_index: int) -> tuple[str, str]:
    label = _clean_text(
        metadata.get("source")
        or metadata.get("doc_id")
        or metadata.get("file_name")
    )
    if not label:
        label = f"document-{input_index}"
    portable = label.replace("\\", "/")
    return portable.casefold(), portable


def _heading_path(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        heading
        for key in _HEADING_KEYS
        if (heading := _clean_text(metadata.get(key)))
    )


def _categories(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    raw_categories = metadata.get("categories")
    if not isinstance(raw_categories, (list, tuple, set, frozenset)):
        return ("uncategorized",)
    by_key: dict[str, str] = {}
    for raw_category in raw_categories:
        category = _clean_text(raw_category)
        if category:
            by_key.setdefault(category.casefold(), category)
    if not by_key:
        return ("uncategorized",)
    return tuple(by_key[key] for key in sorted(by_key))


def _chunk_order(metadata: Mapping[str, Any], input_index: int) -> int:
    raw_index = metadata.get("chunk_index")
    if isinstance(raw_index, int) and not isinstance(raw_index, bool) and raw_index >= 0:
        return raw_index
    if isinstance(raw_index, str) and raw_index.isdecimal():
        return int(raw_index)
    return input_index


def _records(chunks: Iterable[Any]) -> list[_ChunkRecord]:
    records: list[_ChunkRecord] = []
    for input_index, chunk in enumerate(chunks):
        raw_metadata = getattr(chunk, "metadata", None)
        metadata: Mapping[str, Any] = (
            raw_metadata if isinstance(raw_metadata, Mapping) else {}
        )
        document_key, document_label = _document_identity(metadata, input_index)
        records.append(
            _ChunkRecord(
                input_index=input_index,
                order=_chunk_order(metadata, input_index),
                document_key=document_key,
                document_label=document_label,
                heading_path=_heading_path(metadata),
                categories=_categories(metadata),
                content=str(getattr(chunk, "page_content", "") or ""),
                metadata=metadata,
            )
        )
    return records


def build_structural_graph(
    chunks: Iterable[Any],
    *,
    tenant_id: str = "default",
) -> StructuralGraph:
    """Build the GR-1 document/section/chunk graph from ingestion output."""
    tenant = _clean_text(tenant_id) or "default"
    records = _records(chunks)
    nodes: dict[tuple[NodeKind, str], StructuralGraphNode] = {}
    edges: dict[tuple[EdgeKind, str, str], StructuralGraphEdge] = {}
    chunk_nodes: dict[int, StructuralGraphNode] = {}
    section_nodes: dict[tuple[str, tuple[str, ...]], StructuralGraphNode] = {}
    document_nodes: dict[str, StructuralGraphNode] = {}

    document_labels: dict[str, str] = {}
    document_categories: dict[str, dict[str, str]] = defaultdict(dict)
    document_aliases: dict[str, set[str]] = defaultdict(set)
    for record in records:
        existing_label = document_labels.setdefault(
            record.document_key, record.document_label
        )
        if existing_label != record.document_label:
            raise ValueError(
                "Document sources differ only by case: "
                f"{existing_label!r} and {record.document_label!r}"
            )
        for category in record.categories:
            document_categories[record.document_key].setdefault(
                category.casefold(), category
            )
        for alias in (
            record.document_label,
            _clean_text(record.metadata.get("title")),
            record.heading_path[0] if record.heading_path else "",
        ):
            if normalized_alias := _lookup_key(alias):
                document_aliases[record.document_key].add(normalized_alias)

    for document_key in sorted(document_labels):
        label = document_labels[document_key]
        categories = [
            document_categories[document_key][key]
            for key in sorted(document_categories[document_key])
        ]
        document_node = StructuralGraphNode(
            node_id=_stable_id(tenant, "document", document_key),
            tenant_id=tenant,
            kind="document",
            natural_key=document_key,
            label=label,
            attributes={"source": label, "categories": categories},
        )
        nodes[("document", document_key)] = document_node
        document_nodes[document_key] = document_node

        for category in categories:
            category_key = category.casefold()
            category_node = nodes.get(("category", category_key))
            if category_node is None:
                category_node = StructuralGraphNode(
                    node_id=_stable_id(tenant, "category", category_key),
                    tenant_id=tenant,
                    kind="category",
                    natural_key=category_key,
                    label=category,
                )
                nodes[("category", category_key)] = category_node
            _add_edge(
                edges,
                tenant,
                "category",
                document_node,
                category_node,
            )

    chunk_identity_seen: set[tuple[str, int]] = set()
    records_by_document: dict[str, list[_ChunkRecord]] = defaultdict(list)
    records_by_section: dict[tuple[str, tuple[str, ...]], list[_ChunkRecord]] = (
        defaultdict(list)
    )
    for record in records:
        chunk_identity = (record.document_key, record.order)
        if chunk_identity in chunk_identity_seen:
            raise ValueError(
                "Duplicate chunk identity for source "
                f"{record.document_label!r}: chunk_index={record.order}"
            )
        chunk_identity_seen.add(chunk_identity)

        normalized_heading_path = tuple(
            heading.casefold() for heading in record.heading_path
        )
        section_key = (record.document_key, normalized_heading_path)
        section_node = section_nodes.get(section_key)
        if section_node is None:
            path_label = " › ".join(record.heading_path) or "(root)"
            section_natural_key = (
                f"{record.document_key}\x1f"
                + "\x1f".join(normalized_heading_path)
            )
            section_node = StructuralGraphNode(
                node_id=_stable_id(tenant, "section", section_natural_key),
                tenant_id=tenant,
                kind="section",
                natural_key=section_natural_key,
                label=f"{record.document_label} › {path_label}",
                attributes={
                    "source": record.document_label,
                    "heading_path": list(record.heading_path),
                    "synthetic": not record.heading_path,
                },
            )
            nodes[("section", section_natural_key)] = section_node
            section_nodes[section_key] = section_node
            _add_edge(
                edges,
                tenant,
                "contains",
                document_nodes[record.document_key],
                section_node,
                attributes={"level": "section"},
            )

        chunk_natural_key = f"{record.document_key}\x1f{record.order}"
        chunk_attributes: dict[str, Any] = {
            "source": record.document_label,
            "chunk_index": record.order,
            "heading_path": list(record.heading_path),
            "content_sha256": hashlib.sha256(record.content.encode("utf-8")).hexdigest(),
        }
        if record.metadata.get("page") is not None:
            chunk_attributes["page"] = record.metadata["page"]
        chunk_node = StructuralGraphNode(
            node_id=_stable_id(tenant, "chunk", chunk_natural_key),
            tenant_id=tenant,
            kind="chunk",
            natural_key=chunk_natural_key,
            label=f"{record.document_label}#chunk-{record.order}",
            attributes=chunk_attributes,
        )
        nodes[("chunk", chunk_natural_key)] = chunk_node
        chunk_nodes[record.input_index] = chunk_node
        _add_edge(
            edges,
            tenant,
            "contains",
            section_node,
            chunk_node,
            attributes={"level": "chunk"},
        )
        records_by_document[record.document_key].append(record)
        records_by_section[section_key].append(record)

    for document_records in records_by_document.values():
        ordered = sorted(document_records, key=lambda item: (item.order, item.input_index))
        for source_record, target_record in zip(ordered, ordered[1:], strict=False):
            _add_edge(
                edges,
                tenant,
                "next",
                chunk_nodes[source_record.input_index],
                chunk_nodes[target_record.input_index],
            )

    for section_records in records_by_section.values():
        ordered = sorted(section_records, key=lambda item: (item.order, item.input_index))
        for source_record, target_record in zip(ordered, ordered[1:], strict=False):
            _add_edge(
                edges,
                tenant,
                "same_section",
                chunk_nodes[source_record.input_index],
                chunk_nodes[target_record.input_index],
                attributes={"symmetric": True},
            )

    unresolved = _add_cross_references(
        records=records,
        tenant_id=tenant,
        document_nodes=document_nodes,
        document_aliases=document_aliases,
        section_nodes=section_nodes,
        chunk_nodes=chunk_nodes,
        edges=edges,
    )

    return StructuralGraph(
        tenant_id=tenant,
        builder_version=STRUCTURAL_GRAPH_BUILDER_VERSION,
        nodes=tuple(
            sorted(nodes.values(), key=lambda node: (node.kind, node.natural_key))
        ),
        edges=tuple(
            sorted(
                edges.values(),
                key=lambda edge: (
                    edge.kind,
                    edge.source_node_id,
                    edge.target_node_id,
                ),
            )
        ),
        unresolved_cross_refs=tuple(
            sorted(
                unresolved.values(),
                key=lambda item: (
                    item.source_node_id,
                    item.reference_kind,
                    item.raw_reference.casefold(),
                ),
            )
        ),
    )


def _add_edge(
    edges: dict[tuple[EdgeKind, str, str], StructuralGraphEdge],
    tenant_id: str,
    kind: EdgeKind,
    source: StructuralGraphNode,
    target: StructuralGraphNode,
    *,
    attributes: dict[str, Any] | None = None,
) -> None:
    key = (kind, source.node_id, target.node_id)
    edges.setdefault(
        key,
        StructuralGraphEdge(
            edge_id=_stable_id(
                tenant_id,
                "edge",
                f"{kind}\x1f{source.node_id}\x1f{target.node_id}",
            ),
            tenant_id=tenant_id,
            kind=kind,
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            attributes=attributes or {},
        ),
    )


def _add_cross_references(
    *,
    records: list[_ChunkRecord],
    tenant_id: str,
    document_nodes: Mapping[str, StructuralGraphNode],
    document_aliases: Mapping[str, set[str]],
    section_nodes: Mapping[tuple[str, tuple[str, ...]], StructuralGraphNode],
    chunk_nodes: Mapping[int, StructuralGraphNode],
    edges: dict[tuple[EdgeKind, str, str], StructuralGraphEdge],
) -> dict[tuple[str, ReferenceKind, str], UnresolvedCrossReference]:
    file_targets: dict[str, list[StructuralGraphNode]] = defaultdict(list)
    order_targets: dict[str, list[StructuralGraphNode]] = defaultdict(list)
    section_number_targets: dict[tuple[str, str], list[StructuralGraphNode]] = (
        defaultdict(list)
    )
    section_name_targets: dict[tuple[str, str], list[StructuralGraphNode]] = (
        defaultdict(list)
    )

    for document_key, document_node in document_nodes.items():
        basename = PurePosixPath(document_node.label.replace("\\", "/")).name.casefold()
        file_targets[basename].append(document_node)
        for alias in document_aliases.get(document_key, set()):
            order_targets[alias].append(document_node)

    for (document_key, _normalized_heading_path), section_node in section_nodes.items():
        heading_path = tuple(section_node.attributes.get("heading_path") or ())
        for heading in heading_path:
            heading_key = _lookup_key(heading)
            if heading_key:
                section_name_targets[(document_key, heading_key)].append(section_node)
            if number_match := _HEADING_NUMBER_RE.match(heading):
                section_number_targets[(document_key, number_match.group(1))].append(
                    section_node
                )

    unresolved: dict[
        tuple[str, ReferenceKind, str], UnresolvedCrossReference
    ] = {}
    for record in records:
        source_chunk = chunk_nodes[record.input_index]

        for match in _FILE_REFERENCE_RE.finditer(record.content):
            raw_reference = match.group(1)
            candidates = file_targets.get(raw_reference.casefold(), [])
            candidates = [
                candidate
                for candidate in candidates
                if candidate.node_id != document_nodes[record.document_key].node_id
            ]
            _resolve_reference(
                candidates,
                source_chunk,
                "file",
                raw_reference,
                tenant_id,
                edges,
                unresolved,
            )

        for match in _SECTION_REFERENCE_RE.finditer(record.content):
            raw_reference = match.group(0).strip()
            candidates = section_number_targets.get(
                (record.document_key, match.group(1)), []
            )
            if candidates or raw_reference.casefold().startswith("см."):
                _resolve_reference(
                    candidates,
                    source_chunk,
                    "section",
                    raw_reference,
                    tenant_id,
                    edges,
                    unresolved,
                )

        for match in _QUOTED_REFERENCE_RE.finditer(record.content):
            raw_reference = match.group(1).strip()
            candidates = section_name_targets.get(
                (record.document_key, _lookup_key(raw_reference)), []
            )
            _resolve_reference(
                candidates,
                source_chunk,
                "section",
                raw_reference,
                tenant_id,
                edges,
                unresolved,
            )

        for match in _ORDER_REFERENCE_RE.finditer(record.content):
            raw_reference = match.group(0).strip().rstrip(".,;:")
            lookup = _lookup_key(raw_reference)
            candidate_by_id: dict[str, StructuralGraphNode] = {}
            matched_self = False
            for alias, alias_targets in order_targets.items():
                if lookup and lookup in alias:
                    for candidate in alias_targets:
                        if candidate.node_id == document_nodes[record.document_key].node_id:
                            matched_self = True
                        else:
                            candidate_by_id[candidate.node_id] = candidate
            if matched_self and not candidate_by_id:
                continue
            _resolve_reference(
                list(candidate_by_id.values()),
                source_chunk,
                "order",
                raw_reference,
                tenant_id,
                edges,
                unresolved,
            )

    return unresolved


def _resolve_reference(
    candidates: list[StructuralGraphNode],
    source_chunk: StructuralGraphNode,
    reference_kind: ReferenceKind,
    raw_reference: str,
    tenant_id: str,
    edges: dict[tuple[EdgeKind, str, str], StructuralGraphEdge],
    unresolved: dict[
        tuple[str, ReferenceKind, str], UnresolvedCrossReference
    ],
) -> None:
    unique_candidates = {candidate.node_id: candidate for candidate in candidates}
    if len(unique_candidates) == 1:
        target = next(iter(unique_candidates.values()))
        _add_edge(
            edges,
            tenant_id,
            "cross_ref",
            source_chunk,
            target,
            attributes={
                "reference_kind": reference_kind,
                "raw_reference": raw_reference[:256],
            },
        )
        return

    clipped_reference = raw_reference[:256]
    key = (source_chunk.node_id, reference_kind, clipped_reference.casefold())
    unresolved.setdefault(
        key,
        UnresolvedCrossReference(
            source_node_id=source_chunk.node_id,
            reference_kind=reference_kind,
            raw_reference=clipped_reference,
            reason="ambiguous" if unique_candidates else "not_found",
        ),
    )
