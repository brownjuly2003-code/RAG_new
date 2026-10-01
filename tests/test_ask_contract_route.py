"""HTTP contract tests for /api/ask with a fixture LLM and a fixture store.

The tests run the real session/graph through FastAPI TestClient with fixture
model answers and a fixture vector store, then read the SQLite trace and the
admin evidence endpoint. A fixture answer says nothing about model quality:
these are deterministic contract checks of the response, trace and evidence
shapes only.
"""

from __future__ import annotations

import importlib
import json
import re
from types import SimpleNamespace

from agent import graph
from auth.jwt_handler import create_access_token
from config.settings import Settings
from llm.providers.base import LLMResponse, estimate_tokens
from tests.test_graph_retriever import _chunk
from tracing.sqlite_trace import get_trace_detail
from vectordb import _base_manager as manager_base
from vectordb import manager

api_app = importlib.import_module("api.app")

_DEFAULT_ANSWERS = [
    "policy",
    "YES",
    "Seed policy [1].",
    '{"score": 90, "reason": "Fixture"}',
    "[]",
]
# Fact verification on: the claim extractor answers NONE (vacuously verified).
_VERIFIED_ANSWERS = [
    "policy",
    "YES",
    "Seed policy [1].",
    "NONE",
    '{"score": 90, "reason": "Fixture"}',
    "[]",
]
_SIMPLE_CLASSIFICATION = {
    "complexity": "simple",
    "question_class": "single_hop",
    "entities": [],
    "needs_multi_hop": False,
    "reason_code": "LEGACY_COMPLEXITY_ONLY",
}
_GRAPH_CLASSIFICATION = {
    "complexity": "global",
    "question_class": "aggregation",
    "entities": ["air waybill"],
    "needs_multi_hop": True,
    "reason_code": "MULTI_SOURCE_CHAIN",
}
_CITATION = {"index": 1, "doc_id": "policy.md", "title": "policy.md", "excerpt": "Seed policy."}


def _policy_seed():
    return _chunk(
        "Seed policy.", source="policy.md", chunk_index=0, section="Rules", category="shipping"
    )


def _fixture_model(answers: list[str], classification: dict | None = None):
    """Fixture LLM popping scripted replies; one structured call when routing is on."""

    class FixtureModel:
        def __init__(self) -> None:
            self.supports_structured_output = classification is not None
            if classification is None:
                self.generate_with_schema = None
            self.answers = iter(answers)

        def invoke(self, prompt):
            return next(self.answers, "[]")

        def generate_with_schema(self, messages, schema, **kwargs):
            assert "complexity" in schema["properties"]
            self.supports_structured_output = False
            self.generate_with_schema = None
            return LLMResponse(
                text="GLOBAL",
                provider="fixture",
                model="fixture",
                structured_output=classification,
            )

    return FixtureModel()


def _pipeline(
    monkeypatch,
    client,
    tmp_path,
    *,
    retrieval_strategy="hybrid",
    graph_retrieval="off",
    model_routing=False,
    classification=None,
    answers,
    retriever=None,
    chunks=None,
    fact_verification=False,
):
    """Template setup: fixture settings, caches, retriever, session, HTTP stubs."""
    import config.settings
    from api.routers import conversation
    from tracing import _base_trace

    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.retrieval_strategy = retrieval_strategy
    settings.graph_retrieval = graph_retrieval
    settings.vector_backend = "qdrant"
    settings.hybrid_search = False
    settings.parent_expansion = False
    settings.reranker_model = ""
    settings.model_routing_enabled = model_routing
    settings.fact_verification_enabled = fact_verification
    settings.hyde = False
    settings.agentic_mode = False
    settings.online_evaluators_enabled = False
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    _base_trace._init_db()
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    monkeypatch.delenv("DATABASE_URL", raising=False)
    seed = _policy_seed()
    neighbour = _chunk(
        "Required neighbouring fact.",
        source="policy.md",
        chunk_index=1,
        section="Rules",
        category="shipping",
    )
    resolved_chunks = [seed, neighbour] if chunks is None else chunks
    if retriever is None:
        retriever = manager.get_retriever(
            vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
            chunks=resolved_chunks,
            embeddings=object(),
            tenant_id="default",
        )
    session = graph.ConversationSession(
        retriever, _fixture_model(answers, classification), max_iterations=0
    )

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)
    return session, settings


def _ask(client_fixture, question: str = "Summarize the policy") -> dict:
    response = client_fixture.post("/api/ask", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def _evidence(client_fixture, trace_id: str) -> dict:
    response = client_fixture.get(f"/api/admin/traces/{trace_id}/evidence")
    assert response.status_code == 200, response.text
    return response.json()


def _default_ask(monkeypatch, client, tmp_path, **pipeline_kwargs) -> dict:
    answers = pipeline_kwargs.pop("answers", list(_DEFAULT_ANSWERS))
    _pipeline(monkeypatch, client, tmp_path, answers=answers, **pipeline_kwargs)
    return _ask(client)


def _graph_ask(monkeypatch, client, tmp_path, retriever) -> tuple[dict, dict]:
    body = _default_ask(
        monkeypatch,
        client,
        tmp_path,
        retrieval_strategy="graph",
        model_routing=True,
        classification=_GRAPH_CLASSIFICATION,
        retriever=retriever,
    )
    return body, _evidence(client, body["trace_id"])


def _parse_events(payload: str) -> list[dict]:
    events: list[dict] = []
    for chunk in payload.split("\n\n"):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


def _auth(tenant: str = "default", role: str = "admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token('u-' + tenant, role, tenant)}"}


def test_ask_contract_sources_and_citations(monkeypatch, client, tmp_path):
    """Citations map to graded docs; sources carry the page content."""
    body = _default_ask(monkeypatch, client, tmp_path)
    assert body["citations"] == [_CITATION]
    assert body["sources"] == [{"source": "policy.md", "page_content": "Seed policy."}]


def test_ask_contract_orphan_citation_ignored(monkeypatch, client, tmp_path):
    """Citation indices beyond the graded docs are dropped, answer text unchanged."""
    answers = [
        "policy",
        "YES",
        "Seed policy [1] and nothing [3].",
        '{"score": 90, "reason": "Fixture"}',
        "[]",
    ]
    body = _default_ask(monkeypatch, client, tmp_path, answers=answers)
    assert body["answer"] == "Seed policy [1] and nothing [3]."
    assert len(body["citations"]) == 1
    assert body["citations"][0]["index"] == 1


def test_ask_contract_numeric_fields(monkeypatch, client, tmp_path):
    """Score/route flags and trace id follow the AskResponse contract."""
    body = _default_ask(monkeypatch, client, tmp_path)
    assert body["quality_score"] == 90
    assert isinstance(body["quality_score"], int)
    # Fact verification is off in this fixture: the grounding gate is fail-closed
    # (plan §5 / RAG-02), so even a score of 90 is handed to a human.
    assert body["route"] == "human"
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    states = {step["node"]: step["state"] for step in trace["steps"]}
    assert states["verify_facts"]["grounding_status"] != "verified"
    assert body["requires_confirmation"] is False
    assert body["cached"] is False
    assert isinstance(body["trace_id"], str) and body["trace_id"]


def test_ask_contract_verified_single_doc_answer_still_routes_to_human(
    monkeypatch, client, tmp_path
):
    """Vacuous verification does not reach auto: one graded doc is a knowledge gap."""
    body = _default_ask(
        monkeypatch, client, tmp_path, answers=list(_VERIFIED_ANSWERS), fact_verification=True
    )
    assert body["quality_score"] == 90
    assert body["route"] == "human"
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    states = {step["node"]: step["state"] for step in trace["steps"]}
    assert states["verify_facts"]["grounding_status"] == "verified"
    assert states["verify_facts"]["claims"] == []
    # _is_knowledge_gap: fewer than two graded docs (and factuality 0 < 50).
    assert states["route_or_retry"]["knowledge_gap"] is True
    assert states["route_or_retry"]["judge_status"] == "ok"


def test_ask_contract_low_score_routes_to_human(monkeypatch, client, tmp_path):
    """A weak judge score routes to a human; no retry budget with max_iterations=0."""
    answers = [
        "policy",
        "YES",
        "Seed policy [1].",
        '{"score": 20, "reason": "weak"}',
        "[]",
    ]
    body = _default_ask(monkeypatch, client, tmp_path, answers=answers)
    assert body["route"] == "human"
    assert body["quality_score"] == 20
    assert body["answer"] == "Seed policy [1]."


def test_ask_contract_empty_retrieval(monkeypatch, client, tmp_path):
    """Empty retrieval still answers 200 with empty citations and a graded outcome."""
    body = _default_ask(
        monkeypatch,
        client,
        tmp_path,
        retriever=SimpleNamespace(get_relevant_documents=lambda query: []),
    )
    assert body["citations"] == []
    assert body["sources"] == []
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    states = {step["node"]: step["state"] for step in trace["steps"]}
    assert states["grade_docs"]["doc_grade_outcome"] == "empty_retrieval"
    assert states["retrieve"]["context_docs"] == []


def test_ask_stream_final_event_matches_synchronous_contract(monkeypatch, client, tmp_path):
    """With parity on, the terminal SSE event mirrors the /api/ask contract."""
    _pipeline(monkeypatch, client, tmp_path, answers=list(_DEFAULT_ANSWERS))
    monkeypatch.setattr(api_app.get_settings(), "streaming_rag_parity", True, raising=False)
    response = client.post(
        "/api/ask/stream",
        json={"question": "Summarize the policy"},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200, response.text
    events = _parse_events(response.text)
    result_index = next(i for i, event in enumerate(events) if event["type"] == "result")
    final = events[result_index]
    assert final["answer"] == "Seed policy [1]."
    assert final["citations"] == [_CITATION]
    assert final["quality_score"] == 90
    assert final["route"] == "human"
    assert final["answer_source"] == "graph"
    assert isinstance(final["trace_id"], str) and final["trace_id"]
    assert any(event["type"] == "status" for event in events[:result_index])
    assert not any(event["type"] == "error" for event in events)


def test_ask_route_record_defaults(monkeypatch, client, tmp_path):
    """Routing disabled + configured hybrid yields the full default route record."""
    body = _default_ask(monkeypatch, client, tmp_path)
    evidence = _evidence(client, body["trace_id"])
    route = evidence["retrieval_route"]
    assert route == {
        "configured": "hybrid",
        "selected": "hybrid",
        "selected_reason": "configured_hybrid",
        "question_class": "unknown",
        "complexity": "unknown",
        "classifier_reason_code": "ROUTING_DISABLED",
        "confidence": None,
        "entities": [],
        "effective": "hybrid",
        "fallback_reason": None,
        "query_original": "Summarize the policy",
        "query_effective": "policy",
        "query_transform": "rewrite",
        "query_transform_hash": route["query_transform_hash"],
        "graph_retrieval": "off",
        "num_docs": 1,
        "generation_context_tokens": estimate_tokens("Seed policy."),
    }
    assert re.fullmatch(r"[0-9a-f]{64}", route["query_transform_hash"])
    assert "retrieval_paths" not in evidence
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    nodes = [step["node"] for step in trace["steps"]]
    assert nodes.index("retrieval_route") == nodes.index("retrieve") - 1
    generate = [step["state"] for step in trace["steps"] if step["node"] == "generate"]
    assert generate[0]["generation_context_tokens"] == estimate_tokens("Seed policy.")


def test_ask_hybrid_lane_path_reaches_evidence(monkeypatch, client, tmp_path):
    """A hybrid lane path from HybridRetriever is visible in the evidence."""
    seed = _policy_seed()
    retriever = manager_base.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed],
        use_bm25=False,
    )
    body = _default_ask(monkeypatch, client, tmp_path, retriever=retriever)
    evidence = _evidence(client, body["trace_id"])
    paths = evidence["retrieval_paths"]
    assert len(paths) == 1
    assert set(paths[0]) == {"strategy", "path"}
    assert paths[0]["strategy"] == "hybrid"
    path = paths[0]["path"]
    assert path["kind"] == "hybrid"
    assert path["candidates"] == {"vector": 1, "bm25": 0, "merged": 1}
    assert path["rerank_status"] == "not_configured"
    assert path["graph_version"] is None


def test_ask_with_a_float_rerank_score_keeps_the_trace_readable(monkeypatch, client, tmp_path):
    """A sixteen-digit float score survives trace persistence; the route is not an error."""

    class _Scores:
        def predict(self, pairs, batch_size=None):
            return [0.8999999761581421][: len(pairs)]

    seed = _policy_seed()
    retriever = manager_base.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed],
        use_bm25=False,
        reranker=_Scores(),
        rerank_k=1,
    )
    body = _default_ask(monkeypatch, client, tmp_path, retriever=retriever)
    assert body["route"] != "error", body
    assert body["answer"] == "Seed policy [1]."
    evidence = _evidence(client, body["trace_id"])
    path = evidence["retrieval_paths"][0]["path"]
    assert path["rerank_status"] == "ok"
    assert path["rerank_scores"] == [0.8999999761581421]
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    nodes = [step["node"] for step in trace["steps"]]
    assert nodes[nodes.index("retrieval_route") + 1] == "retrieve"
    assert all(step["node"] != "handle_error" for step in trace["steps"])


def test_ask_configured_graph_with_unknown_class_stays_hybrid(monkeypatch, client, tmp_path):
    """Configured graph but unknown class selects hybrid with a bounded reason."""
    body = _default_ask(monkeypatch, client, tmp_path, retrieval_strategy="graph")
    evidence = _evidence(client, body["trace_id"])
    route = evidence["retrieval_route"]
    assert route["selected"] == "hybrid"
    assert route["selected_reason"] == "graph_ineligible_class"
    assert route["effective"] == "hybrid"
    assert route["fallback_reason"] is None
    assert route["configured"] == "graph"
    assert "retrieval_paths" not in evidence


def test_ask_simple_complexity_selects_vector_lane(monkeypatch, client, tmp_path):
    """A simple classification routes to the vector lane."""
    seed = _policy_seed()
    retriever = manager_base.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed],
        use_bm25=False,
    )
    body = _default_ask(
        monkeypatch,
        client,
        tmp_path,
        model_routing=True,
        classification=_SIMPLE_CLASSIFICATION,
        retriever=retriever,
    )
    assert body["route"] != "error"
    evidence = _evidence(client, body["trace_id"])
    route = evidence["retrieval_route"]
    assert route["selected"] == "vector"
    assert route["selected_reason"] == "complexity_simple"
    assert route["effective"] == "vector"
    assert route["complexity"] == "simple"


def test_ask_graph_retriever_error_falls_back_with_reason(monkeypatch, client, tmp_path):
    """A raising graph retriever is visible as retriever_error with zero docs."""

    def boom(query, **kwargs):
        raise RuntimeError("boom")

    body, evidence = _graph_ask(
        monkeypatch, client, tmp_path, SimpleNamespace(get_graph_documents_with_path=boom)
    )
    assert evidence["retrieval_paths"] == [
        {
            "strategy": "graph",
            "path": None,
            "requested": "graph",
            "fallback_reason": "retriever_error",
        }
    ]
    route = evidence["retrieval_route"]
    assert route["effective"] == "graph"
    assert route["num_docs"] == 0


def test_ask_graph_projection_missing_falls_back_to_hybrid(monkeypatch, client, tmp_path):
    """A graph lane without a projection degrades to hybrid with a bounded reason."""
    seed = _policy_seed()
    retriever = manager_base.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=[seed],
        use_bm25=False,
    )
    body, evidence = _graph_ask(monkeypatch, client, tmp_path, retriever)
    assert evidence["retrieval_paths"] == [
        {
            "strategy": "hybrid",
            "path": None,
            "requested": "graph",
            "fallback_reason": "graph_projection_missing",
        }
    ]
    route = evidence["retrieval_route"]
    assert route["selected"] == "graph"
    assert route["effective"] == "hybrid"


def test_ask_retriever_without_graph_lane_reports_reason(monkeypatch, client, tmp_path):
    """A plain retriever with no graph lane is reported, not silently ignored."""
    seed = _policy_seed()
    body, evidence = _graph_ask(
        monkeypatch,
        client,
        tmp_path,
        SimpleNamespace(get_relevant_documents=lambda query: [seed]),
    )
    assert evidence["retrieval_paths"] == [
        {
            "strategy": "hybrid",
            "path": None,
            "requested": "graph",
            "fallback_reason": "retriever_without_graph_lane",
        }
    ]


def test_ask_legacy_graph_lane_without_path(monkeypatch, client, tmp_path):
    """A legacy get_graph_documents lane runs graph without a path or fallback."""
    seed = _policy_seed()
    retriever = SimpleNamespace(
        get_graph_documents=lambda query: [seed],
        get_relevant_documents=lambda query: [seed],
    )
    body, evidence = _graph_ask(monkeypatch, client, tmp_path, retriever)
    assert evidence["retrieval_paths"] == [
        {"strategy": "graph", "path": None, "requested": "graph"}
    ]
    route = evidence["retrieval_route"]
    assert route["effective"] == "graph"
    assert route["fallback_reason"] is None


def test_ask_evidence_is_tenant_scoped(monkeypatch, client, tmp_path):
    """Evidence of the default tenant is unreadable with a foreign tenant JWT."""
    body = _default_ask(monkeypatch, client, tmp_path)
    url = f"/api/admin/traces/{body['trace_id']}/evidence"
    assert client.get(url, headers=_auth("acme")).status_code == 404
    assert client.get(url).status_code == 200
