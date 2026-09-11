"""GR-1 structural lane in ``HybridRetriever``."""

from __future__ import annotations

from typing import Any

import pytest

from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from vectordb import _base_manager as manager


def _chunk(
    text: str,
    *,
    source: str,
    chunk_index: int,
    section: str,
    category: str,
) -> manager.Document:
    return manager.Document(
        page_content=text,
        metadata={
            "source": source,
            "chunk_index": chunk_index,
            "categories": [category],
            "h1": "Policy",
            "h2": section,
        },
    )


def test_graph_lane_prefilters_promotes_and_expands_only_its_section() -> None:
    section_first = _chunk(
        "first supported chunk",
        source="shipping.md",
        chunk_index=0,
        section="Supported",
        category="shipping",
    )
    adjacent_other_section = _chunk(
        "adjacent but different section",
        source="shipping.md",
        chunk_index=1,
        section="Other",
        category="shipping",
    )
    section_second = _chunk(
        "second supported chunk",
        source="shipping.md",
        chunk_index=2,
        section="Supported",
        category="shipping",
    )
    section_tail = _chunk(
        "tail from the same section",
        source="shipping.md",
        chunk_index=3,
        section="Supported",
        category="shipping",
    )
    returns = _chunk(
        "returns-only vector hit",
        source="returns.md",
        chunk_index=4,
        section="Returns",
        category="returns",
    )
    weak_shipping = _chunk(
        "weak isolated shipping hit",
        source="weak.md",
        chunk_index=5,
        section="Weak",
        category="shipping",
    )
    chunks = [
        section_first,
        adjacent_other_section,
        section_second,
        section_tail,
        returns,
        weak_shipping,
    ]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="acme"))

    class _VectorStore:
        def __init__(self) -> None:
            self.filters: list[dict[str, Any] | None] = []

        def similarity_search(
            self,
            query: str,
            k: int,
            filter: dict[str, Any] | None = None,
        ) -> list[manager.Document]:
            assert query == "shipping question"
            self.filters.append(filter)
            ranked = [
                returns,
                adjacent_other_section,
                section_first,
                section_second,
                weak_shipping,
            ]
            if filter is not None:
                allowed = set(filter["source"]["$in"])
                ranked = [doc for doc in ranked if doc.metadata["source"] in allowed]
            return ranked[:k]

    store = _VectorStore()
    retriever = manager.HybridRetriever(
        store,
        chunks=chunks,
        use_bm25=False,
        rerank_k=5,
        graph_projection=projection,
    )

    legacy = retriever.get_relevant_documents("shipping question")
    graph_docs = retriever.get_graph_documents(
        "shipping question",
        categories=["shipping"],
    )

    assert legacy[0] is returns
    assert store.filters == [None, {"source": {"$in": ["shipping.md", "weak.md"]}}]
    assert graph_docs[0].page_content == ("first supported chunk\n\ntail from the same section")
    assert graph_docs[1] is section_second
    assert all("returns-only" not in doc.page_content for doc in graph_docs)
    assert all("adjacent but different" not in doc.page_content for doc in graph_docs[:2])
    assert all("weak isolated" not in doc.page_content for doc in graph_docs)


def test_graph_lane_masks_bm25_to_prefiltered_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shipping = _chunk(
        "shipping policy",
        source="shipping.md",
        chunk_index=0,
        section="Shipping",
        category="shipping",
    )
    returns = _chunk(
        "returns policy",
        source="returns.md",
        chunk_index=1,
        section="Returns",
        category="returns",
    )
    chunks = [shipping, returns]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="acme"))

    class _BM25:
        def __init__(self, tokenized_docs: list[list[str]]) -> None:
            assert len(tokenized_docs) == 2

        def get_scores(self, tokenized_query: list[str]) -> list[float]:
            assert tokenized_query == ["policy"]
            return [1.0, 100.0]

    class _VectorStore:
        def similarity_search(self, query: str, k: int, **kwargs: Any) -> list[manager.Document]:
            _ = query, k, kwargs
            return []

    monkeypatch.setattr(manager, "HAS_BM25", True)
    monkeypatch.setattr(manager, "BM25Okapi", _BM25)
    retriever = manager.HybridRetriever(
        _VectorStore(),
        chunks=chunks,
        graph_projection=projection,
    )

    assert retriever.get_graph_documents("policy", categories=["shipping"]) == [shipping]


def test_graph_lane_manually_masks_store_without_filter_support() -> None:
    shipping = _chunk(
        "shipping policy",
        source="shipping.md",
        chunk_index=0,
        section="Shipping",
        category="shipping",
    )
    returns = _chunk(
        "returns policy",
        source="returns.md",
        chunk_index=1,
        section="Returns",
        category="returns",
    )
    chunks = [shipping, returns]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="acme"))

    class _LegacyVectorStore:
        def similarity_search(self, query: str, k: int) -> list[manager.Document]:
            assert query == "policy"
            return [returns, shipping][:k]

    retriever = manager.HybridRetriever(
        _LegacyVectorStore(),
        chunks=chunks,
        use_bm25=False,
        graph_projection=projection,
    )

    assert retriever.get_graph_documents("policy", categories=["shipping"]) == [shipping]


def test_graph_lane_maps_builder_fallback_chunk_indices() -> None:
    first = manager.Document(
        page_content="first section chunk",
        metadata={"source": "shipping.md", "categories": ["shipping"], "h2": "Policy"},
    )
    second = manager.Document(
        page_content="second section chunk",
        metadata={"source": "shipping.md", "categories": ["shipping"], "h2": "Policy"},
    )
    chunks = [first, second]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="acme"))

    class _VectorStore:
        def similarity_search(self, query: str, k: int) -> list[manager.Document]:
            assert query == "policy"
            return [first][:k]

    retriever = manager.HybridRetriever(
        _VectorStore(),
        chunks=chunks,
        use_bm25=False,
        graph_projection=projection,
    )

    assert retriever.get_graph_documents("policy") == [
        manager.Document(
            page_content="first section chunk\n\nsecond section chunk",
            metadata={
                "source": "shipping.md",
                "categories": ["shipping"],
                "h2": "Policy",
                "graph_section_expanded": True,
            },
        )
    ]


def test_graph_lane_without_projection_is_exact_hybrid_fallback() -> None:
    expected = manager.Document(page_content="legacy result", metadata={})

    class _VectorStore:
        def similarity_search(self, query: str, k: int) -> list[manager.Document]:
            assert query == "question"
            return [expected]

    retriever = manager.HybridRetriever(
        _VectorStore(),
        chunks=[expected],
        use_bm25=False,
    )

    assert retriever.get_graph_documents("question", categories=["ignored"]) == [expected]
