"""Node- and view-level units for route observability (plan_final_30_09_26, 2.1/2.2).

In-process only: no network, no HTTP. The HTTP contract lives in
``tests/test_ask_contract_route.py``; these pin the shapes underneath it — the
``retrieval_route`` trace step the retrieve node logs, the generator's token
count, the Evidence projection of both, and the digest guard in the runtime
retriever factory.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent import graph
from agent.state import create_initial_state
from llm.providers.base import estimate_tokens
from resolution.evidence_view import evidence_view
from tests.test_graph_retriever import _chunk
from tests.test_graph_route_observability import _corpus, _graph_settings, _projection
from tracing.service import TraceService
from vectordb import _base_manager as manager

_TS = "2026-10-01T00:00:00+00:00"


def _capture_log(monkeypatch) -> list[tuple[str, str, dict]]:
    calls: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(
        graph, "log_step", lambda trace_id, node, state: calls.append((trace_id, node, state))
    )
    return calls


def _route_record(calls) -> dict:
    return next(state for _, node, state in calls if node == "retrieval_route")


def _trace(*steps: tuple[str, dict]) -> dict:
    return {
        "trace_id": "t",
        "started_at": _TS,
        "steps": [
            {"order": index, "node": node, "state": state, "ts": _TS}
            for index, (node, state) in enumerate(steps)
        ],
        "feedback": [],
    }


def _record(**overrides) -> dict:
    record = {
        "configured": "hybrid",
        "selected": "hybrid",
        "selected_reason": "configured_hybrid",
        "question_class": None,
        "complexity": "unknown",
        "classifier_reason_code": None,
        "confidence": None,
        "entities": [],
        "effective": "hybrid",
        "fallback_reason": None,
        "query_original": "policy",
        "query_effective": "policy",
        "query_transform": "none",
        "query_transform_hash": None,
        "graph_retrieval": "off",
        "path": {"kind": "hybrid", "candidates": {"vector": 1, "bm25": 0, "merged": 1}},
        "num_docs": 1,
    }
    record.update(overrides)
    return record


# --- retrieve node -----------------------------------------------------------


def test_retrieve_node_logs_the_route_record_without_touching_the_legacy_state(monkeypatch):
    """The route is a separate trace step; the hybrid state keeps its two legacy keys."""
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(retrieval_strategy="hybrid", graph_retrieval="off"),
    )
    calls = _capture_log(monkeypatch)
    rules_a, _, _ = _corpus()
    retriever = manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [rules_a]),
        chunks=[rules_a],
        use_bm25=False,
    )
    out = graph.make_retrieve_node(retriever)(
        {"question": "policy", "complexity": "unknown", "trace_id": "t-route"}
    )
    assert out == {
        "question": "policy",
        "complexity": "unknown",
        "trace_id": "t-route",
        "context_docs": out["context_docs"],
        "retrieval_strategy": "hybrid",
    }
    assert [node for _, node, _ in calls] == ["retrieval_route", "retrieve"]
    assert {trace_id for trace_id, _, _ in calls} == {"t-route"}
    record = _route_record(calls)
    assert record == _record(path=record["path"])
    assert record["path"]["kind"] == "hybrid"
    assert record["path"]["candidates"] == {"vector": 1, "bm25": 0, "merged": 1}


def test_retrieve_node_route_record_without_a_lane_path(monkeypatch):
    """A retriever without the path API yields a route with no path and zero documents."""
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(retrieval_strategy="hybrid", graph_retrieval="off"),
    )
    calls = _capture_log(monkeypatch)
    retriever = SimpleNamespace(get_relevant_documents=lambda query: [])
    out = graph.make_retrieve_node(retriever)({"question": "policy", "trace_id": "t-none"})
    assert out["context_docs"] == []
    record = _route_record(calls)
    assert record["path"] is None
    assert record["num_docs"] == 0
    assert record["effective"] == "hybrid"
    assert record["fallback_reason"] is None


def test_retrieve_node_route_record_for_the_graph_lane(monkeypatch):
    """A configured graph lane with an eligible class records the structural path itself."""
    _graph_settings(monkeypatch)
    calls = _capture_log(monkeypatch)
    chunks = list(_corpus())
    retriever = manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: chunks),
        chunks=chunks,
        use_bm25=False,
        graph_projection=_projection(chunks),
    )
    out = graph.make_retrieve_node(retriever)(
        {"question": "rules", "complexity": "global", "trace_id": "t-graph"}
    )
    assert out["retrieval_strategy_effective"] == "graph"
    record = _route_record(calls)
    assert record["configured"] == "graph"
    assert record["selected"] == "graph"
    assert record["selected_reason"] == "graph_eligible_class"
    assert record["effective"] == "graph"
    assert record["fallback_reason"] is None
    assert record["path"] == out["retrieval_path"]
    assert record["num_docs"] == len(out["context_docs"])
    assert record["graph_retrieval"] is None  # the fixture settings carry no graph_retrieval


def test_retrieve_node_ignores_a_lane_path_attribute_that_is_not_the_contract(monkeypatch):
    """A mock answers every attribute; only a real (docs, path) pair counts as the lane API."""
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(retrieval_strategy="hybrid", graph_retrieval="off"),
    )
    calls = _capture_log(monkeypatch)
    rules_a, _, _ = _corpus()
    retriever = MagicMock()
    retriever.get_relevant_documents.return_value = [rules_a]
    out = graph.make_retrieve_node(retriever)({"question": "policy", "trace_id": "t-mock"})
    assert [doc["page_content"] for doc in out["context_docs"]] == ["rule one"]
    retriever.get_relevant_documents.assert_called_once_with("policy")
    record = _route_record(calls)
    assert record["path"] is None
    assert record["num_docs"] == 1


# --- generate node -----------------------------------------------------------


def test_generate_node_counts_the_tokens_of_the_context_it_sends():
    """generation_context_tokens is the provider estimate over the joined graded docs."""
    llm_fast = MagicMock()
    llm_fast.invoke.return_value = "Ответ [1]."
    llm_strong = MagicMock()
    state = create_initial_state(question="Как восстановить доступ?", trace_id="tok-1")
    state["complexity"] = "simple"
    state["graded_docs"] = [
        {"page_content": "Первый документ.", "metadata": {"doc_id": "a", "source": "a.md"}},
        {"page_content": "Второй документ.", "metadata": {"file_name": "b.pdf"}},
    ]
    out = graph.make_generate_node(llm_fast, llm_strong)(state)
    expected = estimate_tokens("\n\n".join(doc["page_content"] for doc in state["graded_docs"]))
    assert out["generation_context_tokens"] == expected
    assert isinstance(out["generation_context_tokens"], int)
    assert out["generation_context_tokens"] > 0


def test_generate_node_counts_zero_tokens_without_context():
    """No graded documents means no context was sent: the count is 0, still an int."""
    llm_fast = MagicMock()
    llm_fast.invoke.return_value = "Нет данных."
    llm_strong = MagicMock()
    state = create_initial_state(question="Что дальше?", trace_id="tok-2")
    state["complexity"] = "simple"
    state["graded_docs"] = []
    out = graph.make_generate_node(llm_fast, llm_strong)(state)
    assert out["generation_context_tokens"] == 0


# --- evidence view -----------------------------------------------------------


def test_evidence_view_lifts_the_hybrid_path_and_projects_the_route():
    """The hybrid path rides the route step into retrieval_paths; the route keeps every field."""
    record = _record()
    view = evidence_view(
        _trace(
            ("retrieval_route", record),
            ("retrieve", {"retrieval_strategy": "hybrid", "context_docs": []}),
            ("generate", {"generation_context_tokens": 12}),
        )
    )
    assert view["retrieval_paths"] == [{"strategy": "hybrid", "path": record["path"]}]
    expected = {key: value for key, value in record.items() if key != "path"}
    expected["generation_context_tokens"] = 12
    assert view["retrieval_route"] == expected
    assert set(view["retrieval_route"]) == {
        "configured",
        "selected",
        "selected_reason",
        "question_class",
        "complexity",
        "classifier_reason_code",
        "confidence",
        "entities",
        "effective",
        "fallback_reason",
        "query_original",
        "query_effective",
        "query_transform",
        "query_transform_hash",
        "graph_retrieval",
        "num_docs",
        "generation_context_tokens",
    }
    # null fields survive the projection — they are not coerced to "".
    assert view["retrieval_route"]["question_class"] is None
    assert view["retrieval_route"]["query_transform_hash"] is None


def test_evidence_view_prefers_the_retrieve_states_own_path_and_keeps_fallback_fields():
    """A graph lane path in the retrieve state wins over the route; fallbacks keep their reason."""
    structural = {
        "kind": "structural",
        "candidates": {"vector": 2, "bm25": 0, "entity": 0, "merged": 2},
    }
    ran = evidence_view(
        _trace(
            (
                "retrieval_route",
                _record(selected="graph", effective="graph", path={"kind": "hybrid"}),
            ),
            (
                "retrieve",
                {
                    "retrieval_strategy": "graph",
                    "retrieval_strategy_requested": "graph",
                    "retrieval_strategy_effective": "graph",
                    "retrieval_path": structural,
                },
            ),
        )
    )
    assert ran["retrieval_paths"] == [
        {"strategy": "graph", "path": structural, "requested": "graph"}
    ]
    fell_back = evidence_view(
        _trace(
            (
                "retrieval_route",
                _record(selected="graph", fallback_reason="graph_projection_missing", path=None),
            ),
            (
                "retrieve",
                {
                    "retrieval_strategy": "hybrid",
                    "retrieval_strategy_requested": "graph",
                    "retrieval_strategy_effective": "hybrid",
                    "retrieval_fallback_reason": "graph_projection_missing",
                },
            ),
        )
    )
    assert fell_back["retrieval_paths"] == [
        {
            "strategy": "hybrid",
            "path": None,
            "requested": "graph",
            "fallback_reason": "graph_projection_missing",
        }
    ]
    assert fell_back["retrieval_route"]["fallback_reason"] == "graph_projection_missing"


def test_evidence_view_of_an_old_trace_is_unchanged():
    """A trace without a route step gets neither retrieval_paths nor retrieval_route."""
    view = evidence_view(_trace(("retrieve", {"retrieval_strategy": "hybrid", "context_docs": []})))
    assert "retrieval_paths" not in view
    assert "retrieval_route" not in view


def test_evidence_view_route_without_a_generate_step_has_no_token_count():
    """A route logged before generation ran reports generation_context_tokens as null."""
    view = evidence_view(
        _trace(
            ("retrieval_route", _record()),
            ("retrieve", {"retrieval_strategy": "hybrid", "context_docs": []}),
        )
    )
    assert view["retrieval_route"]["generation_context_tokens"] is None


# --- runtime factory ---------------------------------------------------------


def test_runtime_factory_survives_a_digest_failure_and_marks_the_graph_invalid(monkeypatch):
    """A broken structural digest never breaks retriever construction; provenance says so."""
    import config.settings
    from vectordb import manager as runtime

    settings = SimpleNamespace(
        vector_backend="qdrant",
        graph_retrieval="on",
        retrieval_strategy="graph",
        retrieval_top_k=5,
        rerank_top_k=5,
        hybrid_search=False,
        reranker_model="",
        parent_expansion=False,
        parent_child=False,
    )
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(runtime, name, {})

    def _broken_digest(structural_graph):
        raise ValueError("bad graph")

    monkeypatch.setattr(
        "ingestion.structure_graph_projection.structure_graph_digest", _broken_digest
    )
    seed = _chunk(
        "seed policy", source="policy.md", chunk_index=0, section="Rules", category="shipping"
    )
    retriever = runtime.get_retriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed],
        embeddings=object(),
        tenant_id="digest-tenant",
    )
    attrs = retriever._graph_projection.graph
    assert attrs["digest"] is None
    assert attrs["entity_graph_status"] == "invalid"
    _, path = retriever.get_graph_documents_with_path("policy")
    assert path["graph_version"] is None
    assert path["entity_graph_status"] == "invalid"


# --- trace service -----------------------------------------------------------


def test_trace_service_redacts_text_leaves_and_keeps_numeric_scores():
    """Sixteen fractional digits are not a card number; text is still redacted (F-T-59-1)."""
    recorded: list[tuple[str, str, dict]] = []

    class _Backend:
        def _state_to_dict(self, state):
            return dict(state)

        def start_trace(self, trace_id=None, tenant_id="default", *, correlation_id=None):
            return trace_id or "t"

        def log_step(self, trace_id, node_name, state):
            recorded.append((trace_id, node_name, state))

        def finish_trace(self, trace_id, final_state):
            return None

    service = TraceService(_Backend())
    service.log_step(
        "t-pii",
        "retrieval_route",
        {
            "path": {
                "rerank_scores": [0.8999999761581421, None],
                "timings_ms": {"total": 1234567890123456.5},
            },
            "query_original": "pay with 4111 1111 1111 1111 please",
            "entities": ["card 4111-1111-1111-1111"],
            "num_docs": 1,
        },
    )
    ((_, node, state),) = recorded
    assert node == "retrieval_route"
    assert state["path"]["rerank_scores"] == [0.8999999761581421, None]
    assert state["path"]["timings_ms"]["total"] == 1234567890123456.5
    assert state["num_docs"] == 1
    assert "4111 1111 1111 1111" not in state["query_original"]
    assert state["query_original"].startswith("pay with ")
    assert "4111-1111-1111-1111" not in state["entities"][0]
