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
    # Chunk 1 is another section's, so chunk 0's run ends at once, and chunk 3 joins
    # chunk 2, the chunk before it (until stage 7 it joined chunk 0 across the gap).
    assert graph_docs[0] is section_first
    assert graph_docs[1].page_content == "second supported chunk\n\ntail from the same section"
    assert graph_docs[1].metadata["graph_section_expanded"] is True
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


def _rules_chunk(core: str, chunk_index: int, *, seam: int = 0) -> manager.Document:
    """A chunk of one section as the chunker writes it: header line, recorded seam."""
    header = "rules.md › Policy › Rules"
    return manager.Document(
        page_content=f"[{header}]\n{core}",
        metadata={
            "source": "rules.md",
            "chunk_index": chunk_index,
            "h1": "Policy",
            "h2": "Rules",
            "contextual_header": header,
            "seam_overlap": seam,
        },
    )


def _section_retriever(
    chunks: list[manager.Document], max_chars: int = 2400
) -> manager.HybridRetriever:
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="acme"))
    return manager.HybridRetriever(
        None,
        chunks=chunks,
        use_bm25=False,
        graph_projection=projection,
        parent_expansion_max_chars=max_chars,
    )


def test_section_expansion_joins_each_seam_once_under_one_header() -> None:
    chunks = [
        _rules_chunk("Alpha opens the rule. Seam one words", 0),
        _rules_chunk("Seam one words carry on. Seam two words", 1, seam=14),
        _rules_chunk("Seam two words close it.", 2, seam=14),
    ]

    [expanded] = _section_retriever(chunks)._expand_graph_sections([chunks[1]])

    # Until stage 7: the header three times, the seed's mid-text, and each seam twice.
    assert expanded.page_content == (
        "[rules.md › Policy › Rules]\n"
        "Alpha opens the rule. Seam one words carry on. Seam two words close it."
    )
    assert expanded.metadata["graph_section_expanded"] is True


def test_section_expansion_side_ends_at_a_chunk_over_the_budget() -> None:
    chunks = [
        _rules_chunk("Seed text.", 0),
        _rules_chunk("x" * 300, 1),
        _rules_chunk("Short text that would fit.", 2),
    ]

    # Chunk 2 fits the budget, but it is not joined to chunk 0 across chunk 1.
    assert _section_retriever(chunks, max_chars=200)._expand_graph_sections([chunks[0]]) == [
        chunks[0]
    ]


def test_section_expansion_side_ends_at_a_chunk_of_the_context() -> None:
    chunks = [
        _rules_chunk("First seed.", 0),
        _rules_chunk("Second seed.", 1),
        _rules_chunk("Tail of the section.", 2),
    ]

    first, second = _section_retriever(chunks)._expand_graph_sections(chunks[:2])

    assert first is chunks[0]
    assert second.page_content == (
        "[rules.md › Policy › Rules]\nSecond seed.\n\nTail of the section."
    )


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
