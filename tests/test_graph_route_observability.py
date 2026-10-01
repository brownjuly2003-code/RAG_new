"""The graph lane's route is observable end to end.

What was requested, what ran and why it fell back live in the retrieve state
and the Evidence view; the retrieval path names what each source contributed,
what section coherence dropped, what the reranker scored, how long each stage
took and which graph answered. Audit 2026-09-30 (F3, F4, F5, F7);
plan_final_30_09_26 slices 2.1 and 2.2.
"""

from types import SimpleNamespace

import pytest

from agent import graph
from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from resolution.evidence_view import evidence_view
from tests.test_graph_retriever import _chunk
from vectordb import _base_manager as manager


def _graph_settings(monkeypatch):
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="graph"))
    monkeypatch.setattr(graph, "log_step", lambda *args: None)


def _projection(chunks, **graph_attrs):
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id="default"))
    projection.graph.update(graph_attrs)
    return projection


def _corpus():
    rules_a = _chunk("rule one", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    rules_b = _chunk("rule two", source="policy.md", chunk_index=1, section="Rules", category="shipping")
    lone = _chunk("lone appendix fact", source="appendix.md", chunk_index=0,
                  section="Appendix", category="customs")
    return rules_a, rules_b, lone


class _Reranker:
    def __init__(self, scores):
        self.scores = scores
        self.batch_sizes: list[int | None] = []

    def predict(self, pairs, batch_size=None):
        self.batch_sizes.append(batch_size)
        return self.scores[: len(pairs)]


class _BrokenReranker:
    def predict(self, pairs):
        raise RuntimeError("rerank failed")


def test_path_reports_candidates_scores_drops_timings_and_graph_provenance():
    rules_a, rules_b, lone = _corpus()
    chunks = [rules_a, rules_b, lone]
    store = SimpleNamespace(similarity_search=lambda query, k: [rules_a, rules_b, lone])
    reranker = _Reranker([0.9, 0.8, 0.1])
    retriever = manager.HybridRetriever(
        vector_store=store, chunks=chunks, use_bm25=False, reranker=reranker, rerank_k=3,
        graph_projection=_projection(chunks, digest="a" * 64, entity_graph_status="absent"),
    )
    docs, path = retriever.get_graph_documents_with_path("rules", question_class="single_hop")

    assert [doc.page_content for doc in docs] == ["rule one", "rule two"]
    assert path["candidates"] == {"vector": 3, "bm25": 0, "entity": 0, "merged": 3}
    assert path["retrieved_contexts"] == 3 and path["retained_contexts"] == 2
    assert path["rerank_status"] == "ok"
    assert path["rerank_scores"] == [0.9, 0.8]
    assert reranker.batch_sizes == [None]
    assert path["categories"] == []
    # The weak singleton appendix section is dropped, and the drop says so.
    assert len(path["dropped"]) == 1
    drop = path["dropped"][0]
    assert drop["rank"] == 2 and drop["source"] == "appendix.md" and drop["chunk_index"] == 0
    assert drop["reason"] == "weak_singleton_section"
    assert drop["relative_strength"] == pytest.approx(0.2222, abs=1e-4)
    assert isinstance(drop["section"], str) and drop["section"]
    assert drop["section"] not in path["sections"]
    assert set(path["timings_ms"]) == {"pools", "rerank", "coherence_expand", "total"}
    assert all(value >= 0 for value in path["timings_ms"].values())
    assert path["graph_version"] == "a" * 64
    assert path["entity_graph_status"] == "absent"


def test_reranker_error_is_a_named_fallback_not_a_silent_success():
    rules_a, rules_b, lone = _corpus()
    chunks = [rules_a, rules_b, lone]
    store = SimpleNamespace(similarity_search=lambda query, k: [rules_a, rules_b, lone])
    retriever = manager.HybridRetriever(
        vector_store=store, chunks=chunks, use_bm25=False, reranker=_BrokenReranker(), rerank_k=3,
        graph_projection=_projection(chunks),
    )
    docs, path = retriever.get_graph_documents_with_path("rules")
    assert [doc.page_content for doc in docs] == ["rule one", "rule two"]
    assert path["rerank_status"] == "fallback:reranker_error"
    assert path["rerank_scores"] == [None, None]
    assert path["graph_version"] is None and path["entity_graph_status"] is None


@pytest.mark.parametrize("batch", [None, 8])
def test_rerank_batch_setting_reaches_the_runtime_reranker_and_keeps_document_identity(batch):
    rules_a, rules_b, lone = _corpus()
    chunks = [rules_a, rules_b, lone]
    store = SimpleNamespace(similarity_search=lambda query, k: [rules_a, rules_b, lone])
    reranker = _Reranker([0.1, 0.9, 0.5])
    retriever = manager.HybridRetriever(
        vector_store=store, chunks=chunks, use_bm25=False, reranker=reranker, rerank_k=2,
        rerank_batch=batch,
    )
    docs = retriever.get_relevant_documents("rules")
    assert reranker.batch_sizes == [batch]
    # Legacy contract: the same objects come back, nothing is copied or annotated.
    assert docs[0] is rules_b and docs[1] is lone
    assert "rerank_score" not in (docs[0].metadata or {})


def test_runtime_factory_forwards_rerank_batch(monkeypatch):
    import config.settings
    from vectordb import manager as runtime

    settings = SimpleNamespace(
        vector_backend="qdrant", graph_retrieval="off", retrieval_strategy="hybrid",
        retrieval_top_k=5, rerank_top_k=5, hybrid_search=False, reranker_model="x",
        parent_expansion=False, parent_child=False, rerank_batch=16,
    )
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_reranker", lambda: _Reranker([0.5]))
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(runtime, name, {})
    seed = _chunk("seed", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    retriever = runtime.get_retriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed], embeddings=object(), tenant_id="batch-tenant",
    )
    assert retriever._rerank_batch == 16


def test_categories_from_state_reach_the_prefilter(monkeypatch):
    _graph_settings(monkeypatch)
    rules_a, rules_b, lone = _corpus()
    chunks = [rules_a, rules_b, lone]
    seen: list[dict] = []

    def similarity_search(query, k, filter=None):
        seen.append(dict(filter or {}))
        return [rules_a, rules_b, lone]

    retriever = manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=similarity_search), chunks=chunks,
        use_bm25=False, rerank_k=3, graph_projection=_projection(chunks),
    )
    state = graph.make_retrieve_node(retriever)(
        {"question": "rules", "complexity": "global", "categories": [" Shipping ", ""]}
    )
    path = state["retrieval_path"]
    assert path["prefilter_applied"] is True
    assert path["categories"] == ["Shipping"]
    assert seen == [{"source": {"$in": ["policy.md"]}}]
    assert {doc["metadata"]["source"] for doc in state["context_docs"]} == {"policy.md"}
    assert state["retrieval_strategy_requested"] == "graph"
    assert state["retrieval_strategy_effective"] == "graph"
    assert "retrieval_fallback_reason" not in state


def test_missing_projection_names_the_fallback_in_state_and_evidence(monkeypatch):
    _graph_settings(monkeypatch)
    retriever = manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: []), chunks=[], use_bm25=False,
    )
    state = graph.make_retrieve_node(retriever)({"question": "policy", "complexity": "global"})
    assert state["retrieval_strategy_requested"] == "graph"
    assert state["retrieval_strategy_effective"] == "hybrid"
    assert state["retrieval_fallback_reason"] == "graph_projection_missing"
    assert "retrieval_path" not in state
    view = evidence_view({"steps": [{"node": "retrieve", "state": state}]})
    assert view["retrieval_paths"] == [{
        "strategy": "hybrid", "path": None, "requested": "graph",
        "fallback_reason": "graph_projection_missing",
    }]


def test_retriever_without_a_graph_lane_names_the_fallback(monkeypatch):
    _graph_settings(monkeypatch)
    retriever = SimpleNamespace(get_relevant_documents=lambda query: [])
    state = graph.make_retrieve_node(retriever)({"question": "policy", "complexity": "global"})
    assert state["retrieval_strategy_effective"] == "hybrid"
    assert state["retrieval_fallback_reason"] == "retriever_without_graph_lane"


def test_retriever_error_names_the_fallback_and_returns_no_documents(monkeypatch):
    _graph_settings(monkeypatch)

    class _Failing:
        def get_graph_documents_with_path(self, query, **kwargs):
            raise RuntimeError("boom")

    state = graph.make_retrieve_node(_Failing())({"question": "policy", "complexity": "global"})
    assert state["context_docs"] == []
    assert state["retrieval_strategy_effective"] == "graph"
    assert state["retrieval_fallback_reason"] == "retriever_error"


def test_hybrid_route_keeps_its_legacy_state_shape(monkeypatch):
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="hybrid"))
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    retriever = manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: []), chunks=[], use_bm25=False,
    )
    initial = {"question": "policy", "complexity": "global"}
    assert graph.make_retrieve_node(retriever)(initial) == {
        **initial, "context_docs": [], "retrieval_strategy": "hybrid",
    }
    assert "retrieval_paths" not in evidence_view(
        {"steps": [{"node": "retrieve", "state": graph.make_retrieve_node(retriever)(initial)}]}
    )


def test_runtime_factory_records_entity_graph_status_and_digest(monkeypatch):
    import config.settings
    from vectordb import manager as runtime

    settings = SimpleNamespace(
        vector_backend="qdrant", graph_retrieval="on", retrieval_strategy="graph",
        retrieval_top_k=5, rerank_top_k=5, hybrid_search=False, reranker_model="",
        parent_expansion=False, parent_child=False,
    )
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(runtime, name, {})
    seed = _chunk("seed policy", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    retriever = runtime.get_retriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed], embeddings=object(), tenant_id="status-tenant",
    )
    attrs = retriever._graph_projection.graph
    assert attrs["entity_graph_status"] == "no_database"
    assert len(attrs["digest"]) == 64 and set(attrs["digest"]) <= set("0123456789abcdef")
    assert retriever._entity_graph_status == "no_database"
    assert retriever._graph_version == attrs["digest"]
    _, path = retriever.get_graph_documents_with_path("policy")
    assert path["entity_graph_status"] == "no_database"
    assert path["graph_version"] == attrs["digest"]
