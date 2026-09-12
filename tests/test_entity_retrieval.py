from types import SimpleNamespace

import pytest

from ingestion.entity_graph import add_entity_graph
from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from vectordb._base_manager import Document, HybridRetriever


def entity_fixture(count=5):
    chunks = [Document(page_content=f"policy fact {i}", metadata={"source": f"{i}.md", "chunk_index": i})
              for i in range(count)]
    graph = build_structural_graph(chunks, tenant_id="acme")
    labels = [["awb"], ["awb", "booking"], ["booking", "customs"],
              ["customs", "cargo"], ["cargo"]]
    extracted = {node.node_id: labels[node.attributes["chunk_index"]] if count == 5 else ["awb"]
                 for node in graph.nodes if node.kind == "chunk"}
    return chunks, project_structure_graph(add_entity_graph(graph, extracted))


@pytest.mark.parametrize("question_class", ["multi_hop", "aggregation", "global"])
def test_entity_candidates_reach_shared_reranker_with_two_hop_limit(question_class):
    chunks, projection = entity_fixture()
    seen = []
    reranker = SimpleNamespace(predict=lambda pairs: seen.extend(pairs) or [1.0] * len(pairs))
    retriever = HybridRetriever(SimpleNamespace(similarity_search=lambda query, k: [chunks[0]]),
                                chunks, graph_projection=projection, use_bm25=False, reranker=reranker)
    docs, path = retriever.get_graph_documents_with_path(
        "unrelated wording", question_class=question_class, entities=["air waybill"])
    assert {text for _, text in seen} == {chunk.page_content for chunk in chunks[:4]}
    assert path["entities"] == ["awb"]
    assert path["hops"] == 2
    assert path["kind"] == "structural_entity"
    assert docs


@pytest.mark.parametrize("question_class", ["single_hop", "unknown"])
def test_non_entity_classes_keep_structural_result(question_class):
    chunks, projection = entity_fixture()
    retriever = HybridRetriever(SimpleNamespace(similarity_search=lambda query, k: [chunks[0]]),
                                chunks, graph_projection=projection, use_bm25=False)
    expected = retriever.get_graph_documents_with_path("question")
    assert retriever.get_graph_documents_with_path(
        "question", question_class=question_class, entities=["awb"]) == expected


def test_entity_candidates_are_capped_before_reranker():
    chunks, projection = entity_fixture(65)
    seen = []
    retriever = HybridRetriever(SimpleNamespace(similarity_search=lambda query, k: []), chunks,
                                graph_projection=projection, use_bm25=False,
                                reranker=SimpleNamespace(predict=lambda pairs: seen.extend(pairs) or [1.0] * len(pairs)))
    retriever.get_graph_documents_with_path("q", question_class="global", entities=["awb"])
    assert len(seen) == 50


def test_retrieve_node_forwards_sgr_fields(monkeypatch):
    from agent import graph

    calls = []
    retriever = SimpleNamespace(get_graph_documents_with_path=lambda query, **kwargs: (calls.append(kwargs) or [], {}))
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="graph"))
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    graph.make_retrieve_node(retriever)({"question": "q", "complexity": "global",
                                       "question_class": "aggregation", "entities": ["awb"]})
    assert calls == [{"question_class": "aggregation", "entities": ["awb"]}]


def test_entity_search_filters_sources_and_does_not_retain_request_state():
    from ingestion.entity_retrieval import EntityIndex

    chunks, projection = entity_fixture()
    mapped = {key: chunks[data["attributes"]["chunk_index"]]
              for key, data in projection.nodes(data=True) if data["kind"] == "chunk"}
    index = EntityIndex(projection, mapped)
    docs, matched, hops = index.search(["awb"], sources=["2.md"])
    assert docs == [chunks[2]]
    assert matched == ["awb"]
    assert hops == 2
    assert index.search(["unmatchedxyz"]) == ([], [], 0)
    assert index.search([]) == ([], [], 0)
    lexical_docs, lexical_matches, _ = index.search(["customs clearance"])
    assert lexical_matches == ["customs"]
    assert chunks[3] in lexical_docs


def test_rrf_uses_original_ranks_for_all_three_lists():
    chunks, projection = entity_fixture()
    retriever = HybridRetriever(SimpleNamespace(), chunks, graph_projection=projection, use_bm25=False)
    result = retriever._rrf_merge([chunks[0], chunks[1]], [chunks[2], chunks[1]],
                                  [chunks[3], chunks[1]])
    assert result == [chunks[1], chunks[0], chunks[2], chunks[3]]


@pytest.mark.parametrize("question_class", ["multi_hop", "aggregation"])
def test_complex_sgr_entity_questions_select_graph(monkeypatch, question_class):
    from agent import graph

    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="graph"))
    assert graph._select_retrieval_strategy({"complexity": "complex", "question_class": question_class}) == "graph"
