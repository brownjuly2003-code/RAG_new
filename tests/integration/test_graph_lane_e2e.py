"""HTTP -> real session/graph -> SQLite -> Evidence, with fixture model/store.

Postgres session persistence and live model quality are outside this contract.
"""

from types import SimpleNamespace

import pytest

from agent import graph
from config.settings import Settings
from tests.test_graph_retriever import _chunk
from vectordb import manager


@pytest.mark.parametrize("mode", ["on", "off", "auto"])
@pytest.mark.parametrize("entity_lane", [False, True])
def test_ask_persists_structural_path_only_when_enabled(monkeypatch, client, tmp_path, mode, entity_lane):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from tracing.sqlite_trace import get_trace_detail

    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.retrieval_strategy = "graph"
    settings.graph_retrieval = mode
    settings.vector_backend = "qdrant"
    settings.hybrid_search = False
    settings.parent_expansion = False
    settings.reranker_model = ""
    settings.model_routing_enabled = True
    settings.fact_verification_enabled = False
    settings.hyde = False
    settings.agentic_mode = False
    settings.online_evaluators_enabled = False
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    from tracing import _base_trace

    _base_trace._init_db()
    for name in ("_retriever_cache", "_chunks_cache", "_store_cache", "_index_cache_keys"):
        monkeypatch.setattr(manager, name, {})
    seed = _chunk("Seed policy.", source="policy.md", chunk_index=0, section="Rules", category="shipping")
    neighbour = _chunk("Required neighbouring fact.", source="policy.md", chunk_index=1,
                       section="Rules", category="shipping")
    chunks = [seed, neighbour]
    if entity_lane:
        from contextlib import nullcontext

        from ingestion import jobs
        from ingestion.entity_graph import add_entity_graph
        from ingestion.structure_graph import build_structural_graph
        from ingestion.structure_graph_repository import StructuralGraphRepository

        chunks.append(_chunk("Linked AWB requirement.", source="awb.md", chunk_index=0,
                             section="AWB", category="shipping"))
        structural = build_structural_graph(chunks, tenant_id="default")
        enriched = add_entity_graph(structural, {node.node_id: ["awb"] for node in structural.nodes
                                                 if node.kind == "chunk"})
        monkeypatch.setenv("DATABASE_URL", "postgresql://fixture")
        monkeypatch.setattr(jobs, "sync_session", lambda: nullcontext(object()))
        monkeypatch.setattr(StructuralGraphRepository, "load", lambda self, tenant: enriched)
    retriever = manager.get_retriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: [seed]),
        chunks=chunks, embeddings=object(), tenant_id="default",
    )

    class FixtureModel:
        def __init__(self):
            self.supports_structured_output = entity_lane
            if not entity_lane:
                self.generate_with_schema = None
            self.answers = iter([
                *([] if entity_lane else ["GLOBAL"]), "policy",
                ('{"grades":[{"index":1,"relevant":true},{"index":2,"relevant":true},'
                 '{"index":3,"relevant":true}]}' if entity_lane and mode == "on" else "YES"),
                "Seed policy [1].",
                '{"score": 90, "reason": "Fixture answer"}', "[]",
            ])

        def invoke(self, prompt):
            return next(self.answers, "[]")

        def generate_with_schema(self, messages, schema, **kwargs):
            from llm.providers.base import LLMResponse

            assert "complexity" in schema["properties"]
            self.supports_structured_output = False
            self.generate_with_schema = None
            return LLMResponse(text="GLOBAL", provider="fixture", model="fixture",
                               structured_output={"complexity": "global", "question_class": "aggregation",
                                                  "entities": ["air waybill"], "needs_multi_hop": True,
                                                  "reason_code": "MULTI_SOURCE_CHAIN"})

    session = graph.ConversationSession(retriever, FixtureModel(), max_iterations=0)

    async def session_factory(*args, **kwargs):
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)
    response = client.post("/api/ask", json={"question": "Summarize the policy"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["route"] != "error", body
    assert body["answer"] == "Seed policy [1].", body
    trace = get_trace_detail(body["trace_id"], tenant_id="default")
    assert trace is not None
    assert trace["finished_at"] is not None
    assert all(step["node"] != "handle_error" for step in trace["steps"])
    retrieved = [step["state"] for step in trace["steps"] if step["node"] == "retrieve"]
    assert len(retrieved) == 1, trace
    state = retrieved[0]
    assert state["retrieval_strategy_effective"] == ("graph" if mode == "on" else "hybrid")
    evidence_response = client.get(f'/api/admin/traces/{body["trace_id"]}/evidence')
    assert evidence_response.status_code == 200
    evidence = evidence_response.json()
    if mode == "on":
        assert evidence["retrieval_paths"][0]["path"] == state["retrieval_path"]
        if entity_lane:
            assert state["retrieval_path"]["kind"] == "structural_entity"
            assert state["retrieval_path"]["entities"] == ["awb"]
            assert any("Linked AWB requirement." in doc["page_content"] for doc in state["context_docs"])
            assert any("Required neighbouring fact." in doc["page_content"] for doc in state["context_docs"])
        else:
            assert state["retrieval_path"]["expanded_contexts"] == 1
            assert "Required neighbouring fact." in state["context_docs"][0]["page_content"]
    else:
        assert "retrieval_paths" not in evidence
        assert "retrieval_path" not in state
        assert state["context_docs"][0]["page_content"] == "Seed policy."
