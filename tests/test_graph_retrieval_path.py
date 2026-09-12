from types import SimpleNamespace

import pytest

from agent import graph
from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from resolution.evidence_view import evidence_view
from tests.test_graph_retriever import _chunk
from vectordb import _base_manager as manager


def test_graph_path_records_actual_sections_and_expansion(monkeypatch):
    seed = _chunk("seed policy", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    neighbour = _chunk("required fact", source="policy.md", chunk_index=1, section="Rules", category="shipping")
    store = SimpleNamespace(similarity_search=lambda query, k: [seed])
    projection = project_structure_graph(build_structural_graph([seed, neighbour], tenant_id="default"))
    retriever = manager.HybridRetriever(vector_store=store, chunks=[seed, neighbour],
        use_bm25=False, graph_projection=projection)
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="graph"))
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    state = graph.make_retrieve_node(retriever)({"question": "policy", "complexity": "global"})
    assert state["retrieval_strategy_effective"] == "graph"
    path = state["retrieval_path"]
    assert path["prefilter_applied"] is False
    assert len(path["sections"]) == 1
    assert path["expanded_contexts"] == 1
    assert path["entities"] == [] and path["hops"] == 0
    assert "required fact" in state["context_docs"][0]["page_content"]
    view = evidence_view({"steps": [{"node": "retrieve", "state": state}]})
    assert view["retrieval_paths"][0]["path"] == path


def test_missing_projection_reports_hybrid_fallback(monkeypatch):
    retriever = manager.HybridRetriever(vector_store=SimpleNamespace(similarity_search=lambda query, k: []),
                                         chunks=[], use_bm25=False)
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="graph"))
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    state = graph.make_retrieve_node(retriever)({"question": "policy", "complexity": "global"})
    assert state["retrieval_strategy_effective"] == "hybrid"
    assert "retrieval_path" not in state


def test_default_hybrid_retrieve_state_keeps_legacy_shape(monkeypatch):
    retriever = manager.HybridRetriever(vector_store=SimpleNamespace(similarity_search=lambda query, k: []),
                                         chunks=[], use_bm25=False)
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="hybrid"))
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    initial = {"question": "policy", "complexity": "global"}
    assert graph.make_retrieve_node(retriever)(initial) == {
        **initial, "context_docs": [], "retrieval_strategy": "hybrid",
    }


@pytest.mark.parametrize("mode", ["off", "on", "auto"])
@pytest.mark.parametrize("source_docs", [False, True])
def test_runtime_factory_builds_projection_only_for_explicit_on(monkeypatch, mode, source_docs):
    import config.settings
    from vectordb import manager as runtime

    settings = SimpleNamespace(vector_backend="qdrant", graph_retrieval=mode,
        retrieval_strategy="graph", retrieval_top_k=5, rerank_top_k=5,
        hybrid_search=False, reranker_model="", parent_expansion=False, parent_child=False)
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(runtime, name, {})
    seed = _chunk("seed policy", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    store = SimpleNamespace(similarity_search=lambda query, k: [seed])
    if source_docs:
        store._source_docs = [seed]
        store._source_embeddings = object()
    retriever = runtime.get_retriever(vector_store=store,
        chunks=[seed], embeddings=object(), tenant_id="test-tenant")
    assert (getattr(retriever, "_graph_projection", None) is not None) == (mode == "on")
    if mode == "on":
        assert retriever._graph_projection.graph["tenant_id"] == "test-tenant"
