"""Unit tests for route observability, plan_final_30_09_26 slices 2.1/2.2.

Pure in-process tests: rerank score bookkeeping (NaN/Inf, duplicate keys),
`rerank_batch_effective` plumbing, the hybrid path contract, strategy
selection reasons, query-transform fingerprints and RAG_RERANK_BATCH parsing.
No network, no HTTP, no filesystem writes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent import graph
from config.settings import Settings, _parse_rerank_batch
from tests.test_graph_retriever import _chunk
from tests.test_graph_route_observability import _corpus, _projection, _Reranker
from vectordb import _base_manager as manager


def _retriever(chunks, *, reranker=None, rerank_k=3, rerank_batch=None, graph_projection=None):
    """Deterministic hybrid retriever over an in-memory fake vector store."""
    documents = list(chunks)
    return manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: documents),
        chunks=documents,
        use_bm25=False,
        reranker=reranker,
        rerank_k=rerank_k,
        graph_projection=graph_projection,
        rerank_batch=rerank_batch,
    )


def _assert_hex64(value):
    """Assert value is a 64-character lowercase hex string (sha256 hexdigest)."""
    assert isinstance(value, str)
    assert len(value) == 64
    assert value == value.lower()
    assert all(char in "0123456789abcdef" for char in value)


def test_rerank_scored_nan_inf_become_none_and_status_partial():
    """Finite scores sort first descending; NaN/Inf turn into None, keep input order, status partial."""
    docs = [
        _chunk(f"doc {name}", source=f"{name}.md", chunk_index=0, section="S", category="c")
        for name in ("alpha", "beta", "gamma", "delta")
    ]
    retriever = manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: docs),
        chunks=docs,
        use_bm25=False,
        reranker=_Reranker([0.2, float("nan"), 0.9, float("inf")]),
        rerank_k=4,
    )
    scored = retriever._rerank_scored("q", docs)
    expected = [(docs[2], 0.9), (docs[0], 0.2), (docs[1], None), (docs[3], None)]
    assert len(scored) == len(expected)
    for (doc, score), (want_doc, want_score) in zip(scored, expected, strict=True):
        assert doc is want_doc
        if want_score is None:
            assert score is None
        else:
            assert score == pytest.approx(want_score)
    assert retriever.get_relevant_documents_with_path("q")[1]["rerank_status"] == "partial"


def test_duplicate_document_key_dropped_and_max_score_wins():
    """A repeated _rrf_document_key yields one duplicate_key drop; the max finite score wins."""
    duplicate_a = _chunk(
        "repeated rule", source="policy.md", chunk_index=0, section="Rules", category="c"
    )
    duplicate_b = _chunk(
        "repeated rule", source="policy.md", chunk_index=0, section="Rules", category="c"
    )
    distinct = _chunk(
        "distinct rule", source="appendix.md", chunk_index=0, section="Appendix", category="c"
    )
    retriever = _retriever(
        [duplicate_a, duplicate_b, distinct], reranker=_Reranker([0.5, 0.7, 0.1]), rerank_k=3
    )
    path = retriever.get_relevant_documents_with_path("rules")[1]
    assert len(path["dropped"]) == 1
    drop = path["dropped"][0]
    assert drop["reason"] == "duplicate_key"
    assert drop["relative_strength"] is None
    assert drop["section"] is None
    assert path["rerank_scores"] == [pytest.approx(0.7), pytest.approx(0.7), pytest.approx(0.1)]
    assert path["rerank_status"] == "ok"


def test_rerank_batch_effective_reported_on_both_paths():
    """rerank_batch is echoed as rerank_batch_effective on hybrid and graph lanes; None when unset."""
    chunks = list(_corpus())
    retriever = _retriever(
        chunks,
        reranker=_Reranker([0.9, 0.8, 0.1]),
        rerank_k=2,
        rerank_batch=8,
        graph_projection=_projection(chunks),
    )
    assert retriever.get_relevant_documents_with_path("rules")[1]["rerank_batch_effective"] == 8
    assert retriever.get_graph_documents_with_path("rules")[1]["rerank_batch_effective"] == 8
    plain = _retriever(
        chunks,
        reranker=_Reranker([0.9, 0.8, 0.1]),
        rerank_k=2,
        graph_projection=_projection(chunks),
    )
    assert plain.get_relevant_documents_with_path("rules")[1]["rerank_batch_effective"] is None
    assert plain.get_graph_documents_with_path("rules")[1]["rerank_batch_effective"] is None


def test_hybrid_path_contract_with_reranker():
    """The hybrid path dict is exactly the documented shape (bar timings) with same objects returned."""
    rules_a, rules_b, lone = _corpus()
    retriever = _retriever(
        [rules_a, rules_b, lone], reranker=_Reranker([0.1, 0.9, 0.5]), rerank_k=2
    )
    docs, path = retriever.get_relevant_documents_with_path("rules")
    assert docs == retriever.get_relevant_documents("rules")
    assert docs[0] is rules_b
    assert docs[1] is lone
    expected = {
        "kind": "hybrid",
        "candidates": {"vector": 3, "bm25": 0, "merged": 3},
        "rerank_status": "ok",
        "rerank_scores": [pytest.approx(0.9), pytest.approx(0.5)],
        "rerank_batch_effective": None,
        "retrieved_contexts": 3,
        "retained_contexts": 2,
        "dropped": [],
        "graph_version": None,
        "entity_graph_status": None,
    }
    assert set(path) == {*expected, "timings_ms"}
    for key, value in expected.items():
        assert path[key] == value, key
    timings = path["timings_ms"]
    assert set(timings) == {"pools", "rerank", "total"}
    assert all(value >= 0 for value in timings.values())


def test_hybrid_path_contract_without_reranker():
    """Without a reranker: not_configured, no scores, zero rerank time, plain top-k retention."""
    retriever = _retriever(list(_corpus()), reranker=None, rerank_k=2)
    _, path = retriever.get_relevant_documents_with_path("rules")
    assert path["rerank_scores"] == []
    assert path["rerank_status"] == "not_configured"
    assert path["timings_ms"]["rerank"] == 0.0
    assert path["retained_contexts"] == 2


@pytest.mark.parametrize(
    ("configured", "complexity", "question_class", "expected_strategy", "expected_reason"),
    [
        ("vector", "unknown", "unknown", "vector", "configured_vector"),
        ("factcard", "unknown", "unknown", "factcard", "configured_factcard"),
        ("hybrid", "simple", "unknown", "vector", "complexity_simple"),
        ("graph", "global", "unknown", "graph", "graph_eligible_class"),
        ("graph", "complex", "multi_hop", "graph", "graph_eligible_class"),
        ("graph", "unknown", "unknown", "hybrid", "graph_ineligible_class"),
        ("graph", "complex", "single_hop", "hybrid", "graph_ineligible_class"),
        ("hybrid", "complex", "single_hop", "hybrid", "configured_hybrid"),
    ],
)
def test_select_retrieval_strategy_reason_matrix(
    configured, complexity, question_class, expected_strategy, expected_reason, monkeypatch
):
    """Selection returns (selected, configured, reason) and the thin wrapper returns the strategy."""
    monkeypatch.setattr(
        graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy=configured)
    )
    state = {"complexity": complexity, "question_class": question_class}
    assert graph._select_retrieval_strategy_with_reason(state) == (
        expected_strategy,
        configured,
        expected_reason,
    )
    assert graph._select_retrieval_strategy(state) == expected_strategy


def test_query_transform_fingerprint_names_and_hashes():
    """Fingerprint names none/hyde/rewrite; each rewrite variant hashes a distinct stable template."""
    fingerprint = graph._query_transform_fingerprint
    assert fingerprint({"question": "q"}) == ("none", None)
    assert fingerprint({"question": "q", "search_query": "q"}) == ("none", None)

    name, hyde_hash = fingerprint({"question": "q", "hyde_query": "hypothetical"})
    assert name == "hyde"
    _assert_hex64(hyde_hash)

    plain_state = {"question": "q", "search_query": "q rewritten"}
    name, plain_hash = fingerprint(plain_state)
    assert name == "rewrite"
    _assert_hex64(plain_hash)

    history_state = {
        "question": "q",
        "search_query": "q rewritten",
        "chat_history": [{"role": "user", "content": "earlier"}],
    }
    name, history_hash = fingerprint(history_state)
    assert name == "rewrite"
    _assert_hex64(history_hash)

    iteration_state = {"question": "q", "search_query": "q rewritten", "iteration": 1}
    name, iteration_hash = fingerprint(iteration_state)
    assert name == "rewrite"
    _assert_hex64(iteration_hash)

    assert len({hyde_hash, plain_hash, history_hash, iteration_hash}) == 4
    assert fingerprint({"question": "q", "hyde_query": "hypothetical"}) == ("hyde", hyde_hash)
    assert fingerprint(plain_state) == ("rewrite", plain_hash)
    assert fingerprint(history_state) == ("rewrite", history_hash)
    assert fingerprint(iteration_state) == ("rewrite", iteration_hash)


def test_parse_rerank_batch_and_settings_field(monkeypatch):
    """RAG_RERANK_BATCH parsing: blank -> None, positive int -> int, anything else -> ValueError."""
    for blank in (None, "", "  "):
        assert _parse_rerank_batch(blank) is None
    assert _parse_rerank_batch("16") == 16
    assert _parse_rerank_batch(" 8 ") == 8
    for invalid in ("0", "-3", "abc", "1.5"):
        with pytest.raises(ValueError):
            _parse_rerank_batch(invalid)

    monkeypatch.setenv("RAG_RERANK_BATCH", "16")
    assert Settings().rerank_batch == 16
    monkeypatch.delenv("RAG_RERANK_BATCH", raising=False)
    assert Settings().rerank_batch is None


def test_all_nan_rerank_reply_is_partial_not_a_reranker_error():
    """predict() succeeded but returned only NaN/Inf: partial, scores None, no fallback (F-T-59-3)."""
    rules_a, rules_b, _ = _corpus()
    docs = [rules_a, rules_b]
    retriever = _retriever(docs, reranker=_Reranker([float("nan"), float("inf")]), rerank_k=2)
    _, path = retriever.get_relevant_documents_with_path("rules")
    assert path["rerank_status"] == "partial"
    assert path["rerank_scores"] == [None, None]
    graph_retriever = _retriever(
        docs,
        reranker=_Reranker([float("nan"), float("inf")]),
        rerank_k=2,
        graph_projection=_projection(docs),
    )
    _, graph_path = graph_retriever.get_graph_documents_with_path("rules")
    assert graph_path["rerank_status"] == "partial"


def test_reranker_exception_is_the_only_reranker_error_status():
    """The exception fallback keeps input order, scores None and names the fallback."""

    class _Broken:
        def predict(self, pairs, batch_size=None):
            raise RuntimeError("rerank failed")

    rules_a, rules_b, _ = _corpus()
    retriever = _retriever([rules_a, rules_b], reranker=_Broken(), rerank_k=2)
    docs, path = retriever.get_relevant_documents_with_path("rules")
    assert docs[0] is rules_a and docs[1] is rules_b
    assert path["rerank_status"] == "fallback:reranker_error"
    assert path["rerank_scores"] == [None, None]
    scored, ok = retriever._rerank_scored_with_status("rules", [rules_a, rules_b])
    assert ok is False and [score for _, score in scored] == [None, None]
    assert retriever._rerank_scored("rules", [rules_a, rules_b]) == scored


def _runtime_settings(rerank_batch):
    return SimpleNamespace(
        vector_backend="qdrant",
        graph_retrieval="off",
        retrieval_strategy="hybrid",
        retrieval_top_k=5,
        rerank_top_k=5,
        hybrid_search=False,
        reranker_model="x",
        parent_expansion=False,
        parent_child=False,
        rerank_batch=rerank_batch,
    )


def test_runtime_factory_rereads_rerank_batch_on_rebuild(monkeypatch):
    """RAG_RERANK_BATCH changed at runtime applies to the next build only (F-T-59-2)."""
    import config.settings
    from vectordb import manager as runtime

    settings = _runtime_settings(8)
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_reranker", lambda: _Reranker([0.5]))
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(runtime, name, {})
    seed = _chunk("seed", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    store = SimpleNamespace(similarity_search=lambda query, k: [seed])

    def _build():
        return runtime.get_retriever(
            vector_store=store, chunks=[seed], embeddings=object(), tenant_id="batch-rebuild"
        )

    monkeypatch.setenv("RAG_RERANK_BATCH", "8")
    first = _build()
    assert first._rerank_batch == 8
    monkeypatch.setenv("RAG_RERANK_BATCH", "16")
    cached = _build()
    assert cached is first and cached._rerank_batch == 8
    runtime.reset_retriever_cache("batch-rebuild")
    rebuilt = _build()
    assert rebuilt is not first and rebuilt._rerank_batch == 16
    monkeypatch.setenv("RAG_RERANK_BATCH", "zero")
    runtime.reset_retriever_cache("batch-rebuild")
    with pytest.raises(ValueError):
        _build()
    monkeypatch.delenv("RAG_RERANK_BATCH", raising=False)
    runtime.reset_retriever_cache("batch-rebuild")
    assert _build()._rerank_batch == 8
    settings.rerank_batch = None
    runtime.reset_retriever_cache("batch-rebuild")
    assert _build()._rerank_batch is None


def test_selection_reason_inverts_the_rule_table_and_follows_a_replaced_selector(monkeypatch):
    """The route record follows the module-level selector (full gate: a test double for
    _select_retrieval_strategy in tests/test_factcard_store.py must still route)."""
    assert graph._selection_reason("vector", "vector") == "configured_vector"
    assert graph._selection_reason("vector", "graph") == "complexity_simple"
    assert graph._selection_reason("factcard", "factcard") == "configured_factcard"
    assert graph._selection_reason("graph", "graph") == "graph_eligible_class"
    assert graph._selection_reason("hybrid", "graph") == "graph_ineligible_class"
    assert graph._selection_reason("hybrid", "hybrid") == "configured_hybrid"
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(retrieval_strategy="hybrid"))
    monkeypatch.setattr(graph, "_select_retrieval_strategy", lambda state: "factcard")
    assert graph._select_retrieval_strategy_with_reason({"complexity": "unknown"}) == (
        "factcard",
        "hybrid",
        "configured_factcard",
    )
