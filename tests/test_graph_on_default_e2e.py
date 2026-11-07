"""Product defaults select the entity lane through both real HTTP ask paths."""

import json
import re
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from agent import graph
from auth.jwt_handler import create_access_token
from config.settings import Settings
from ingestion.entity_graph import add_entity_graph
from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_repository import StructuralGraphRepository
from llm.providers.base import LLMResponse
from tests.test_graph_retriever import _chunk
from tracing.sqlite_trace import get_trace_detail
from vectordb import manager

QUESTION = "How does AWB connect the policies?"
ANSWER = "The AWB links the shipment policy to the required transport document [1]."


class FixtureModel:
    supports_structured_output = True
    model_name = "fixture"
    provider_id = "fixture"

    def __init__(self):
        self.classifier_calls = 0
        self.grader_calls = 0
        self.verifier_calls = 0
        self.answer_prompts = []
        self.last_response = None

    def generate_with_schema(self, messages, schema, **kwargs):
        prompt = messages[0]["content"]
        properties = schema["properties"]
        if "complexity" in properties:
            self.classifier_calls += 1
            result = {
                # A simple verdict must not activate any routing shortcut.
                "complexity": "simple",
                "question_class": "multi_hop",
                "entities": ["AWB"],
                "needs_multi_hop": True,
                "reason_code": "MULTI_SOURCE_CHAIN",
            }
        elif "grades" in properties:
            self.grader_calls += 1
            indices = re.findall(r"^\[(\d+)\] source=", prompt, re.MULTILINE)
            assert indices, prompt
            result = {"grades": [{"index": int(i), "relevant": True} for i in indices]}
        elif "relevant" in properties:
            self.grader_calls += 1
            result = {"relevant": True}
        else:
            assert "supported" in properties, schema
            self.verifier_calls += 1
            result = {"supported": True, "evidence": "AWB links the shipment policy."}
        self.last_response = LLMResponse(
            text=json.dumps(result),
            provider=self.provider_id,
            model=self.model_name,
            structured_output=result,
            input_tokens=12,
            output_tokens=8,
        )
        return self.last_response

    def invoke(self, prompt, **kwargs):
        if "Поисковый запрос:" in prompt:
            return QUESTION
        if "atomic factual claims" in prompt:
            return "- AWB links the shipment policy to the required transport document [1]."
        if "You are a fact-checker" in prompt:
            self.verifier_calls += 1
            return "SUPPORTED: AWB links the shipment policy to the required transport document."
        if "rating the quality of assistant answers" in prompt:
            return "90"
        if "propose 3 short follow-up questions" in prompt:
            return "Which policy?\nWhich document?\nWho signs it?"
        assert "You are a support assistant" in prompt, prompt
        self.answer_prompts.append(prompt)
        return ANSWER

    async def generate_stream(self, messages, **kwargs):
        yield self.invoke(messages[0]["content"], **kwargs)


@pytest.fixture
def product(monkeypatch, client, tmp_path):
    import api.app as api_app
    import config.settings
    from api.routers import conversation
    from ingestion import jobs
    from tracing import _base_trace

    for name in ("RAG_RETRIEVAL_STRATEGY", "RAG_GRAPH_RETRIEVAL", "MODEL_ROUTING_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.retrieval_strategy == "graph"
    assert settings.graph_retrieval == "on"
    assert settings.model_routing_enabled is False
    settings.tracing_db_path = tmp_path / "traces.db"
    settings.vector_backend = "qdrant"  # fixture store, no persistent vector service
    settings.llm_provider_profile = "local-first"
    settings.agentic_mode = False
    settings.hyde = False
    settings.online_evaluators_enabled = False
    settings.fact_verification_enabled = True
    settings.streaming_rag_parity = False  # lane selection alone decides whether workflow is needed
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "get_settings", lambda: settings)
    _base_trace._init_db()
    for name in (
        "_retriever_cache",
        "_chunks_cache",
        "_store_cache",
        "_index_cache_keys",
        "_index_manifest_status",
    ):
        monkeypatch.setattr(manager, name, {})
    chunks = [
        _chunk(
            "AWB links the shipment policy.",
            source="policy.md",
            chunk_index=0,
            section="Rules",
            category="shipping",
        ),
        _chunk(
            "Keep the required transport document.",
            source="policy.md",
            chunk_index=1,
            section="Documents",
            category="shipping",
        ),
        _chunk(
            "AWB is the required transport document.",
            source="awb.md",
            chunk_index=0,
            section="Transport",
            category="shipping",
        ),
    ]
    stored = {}
    for tenant in ("with-entities", "without-entities"):
        structural = build_structural_graph(chunks, tenant_id=tenant)
        stored[tenant] = (
            add_entity_graph(
                structural,
                {node.node_id: ["awb"] for node in structural.nodes if node.kind == "chunk"},
            )
            if tenant == "with-entities"
            else structural
        )
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture")
    monkeypatch.setattr(jobs, "sync_session", lambda: nullcontext(object()))
    monkeypatch.setattr(StructuralGraphRepository, "load", lambda self, tenant: stored[tenant])
    retrievers = {
        tenant: manager.get_retriever(
            vector_store=SimpleNamespace(similarity_search=lambda query, k: [chunks[0]]),
            chunks=chunks,
            embeddings=object(),
            tenant_id=tenant,
        )
        for tenant in stored
    }
    models = {tenant: FixtureModel() for tenant in stored}

    async def session_factory(session_id, tenant_id="default"):
        # A fresh conversation also makes the explicit hybrid comparison independent of history.
        session = graph.ConversationSession(
            retrievers[tenant_id], models[tenant_id], max_iterations=0
        )
        return "11111111-2222-4333-8444-555555555555", session

    async def no_postgres(**kwargs):
        return None

    monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
    monkeypatch.setattr(api_app, "log_audit", no_postgres)
    monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
    monkeypatch.setattr("services.escalation.create_escalation", no_postgres)
    return settings, models


def _ask_result(client, endpoint, tenant):
    response = client.post(
        endpoint,
        json={"question": QUESTION},
        headers={"Authorization": f"Bearer {create_access_token('fixture', 'admin', tenant)}"},
    )
    assert response.status_code == 200, response.text
    if endpoint.endswith("/stream"):
        events = [
            json.loads(part[6:])
            for part in response.text.split("\n\n")
            if part.startswith("data: ")
        ]
        results = [event for event in events if event.get("type") == "result"]
        assert len(results) == 1, events
        body = results[0]
    else:
        body = response.json()
    assert body["answer"] == ANSWER, body
    assert body["route"] != "error", body
    return body


def _ask(client, endpoint, tenant):
    body = _ask_result(client, endpoint, tenant)
    if endpoint.endswith("/stream"):
        assert body["answer_source"] == "graph"
    trace = get_trace_detail(body["trace_id"], tenant_id=tenant)
    assert trace is not None and trace["finished_at"] is not None
    assert all(step["node"] != "handle_error" for step in trace["steps"])

    def state(node):
        found = [step["state"] for step in trace["steps"] if step["node"] == node]
        assert len(found) == 1, (node, trace)
        return found[0]

    assert state("grade_docs")["graded_docs"]
    assert state("verify_facts")["fact_verification_skipped"] is False
    generated = state("generate")
    assert generated["complexity"] == "unknown"
    return state("retrieval_route"), generated["generation_context_docs"]


@pytest.mark.parametrize(
    ("endpoint", "matched"),
    [
        pytest.param("/api/ask", True, id="ask-matched"),
        pytest.param("/api/ask", False, id="ask-no-entity-graph"),
        pytest.param("/api/ask/stream", True, id="stream-matched"),
    ],
)
def test_graph_on_defaults_use_entity_lane_only_when_available(client, product, endpoint, matched):
    settings, models = product
    tenant = "with-entities" if matched else "without-entities"
    model = models[tenant]
    route, sent = _ask(client, endpoint, tenant)
    assert route["configured"] == "graph"
    assert route["graph_retrieval"] == "on"
    assert route["complexity"] == "unknown"
    assert model.classifier_calls == int(matched)
    assert model.grader_calls > 0
    assert model.verifier_calls > 0
    assert len(model.answer_prompts) == 1
    if matched:
        assert route["selected"] == route["effective"] == "graph"
        assert route["selected_reason"] == "graph_eligible_class"
        assert route["classifier_reason_code"] == "MULTI_SOURCE_CHAIN"
        assert route["path"]["kind"] == "structural_entity"
        assert route["path"]["entity_graph_status"] == "matched"
        assert route["path"]["entities"] == ["awb"]
        assert route["path"]["candidates"]["entity"] > 0
    else:
        assert route["selected"] == route["effective"] == "hybrid"
        assert route["selected_reason"] == "graph_ineligible_class"
        assert route["classifier_reason_code"] == "ROUTING_DISABLED"
        assert route["question_class"] == "unknown" and route["entities"] == []
        settings.retrieval_strategy = "hybrid"
        hybrid_route, hybrid_sent = _ask(client, endpoint, tenant)
        assert hybrid_route["selected_reason"] == "configured_hybrid"
        assert sent == hybrid_sent
        assert model.answer_prompts[0] == model.answer_prompts[1]
        assert model.classifier_calls == 0


def test_graph_on_stream_without_entities_matches_hybrid(client, product, monkeypatch):
    settings, models = product
    tenant = "without-entities"
    model = models[tenant]
    result = _ask_result(client, "/api/ask/stream", tenant)
    assert result["answer_source"] == "stream"
    assert result["generation_source"] == "stream"
    assert model.classifier_calls == 0
    assert model.grader_calls == 0
    assert model.verifier_calls == 0
    assert len(model.answer_prompts) == 1
    prompt_bytes = model.answer_prompts[0].encode("utf-8")

    monkeypatch.setenv("RAG_RETRIEVAL_STRATEGY", "hybrid")
    settings.retrieval_strategy = Settings().retrieval_strategy
    assert settings.retrieval_strategy == "hybrid"
    hybrid_result = _ask_result(client, "/api/ask/stream", tenant)
    assert hybrid_result["answer_source"] == "stream"
    assert hybrid_result["generation_source"] == "stream"
    assert model.classifier_calls == 0
    assert model.grader_calls == 0
    assert model.verifier_calls == 0
    assert len(model.answer_prompts) == 2
    assert model.answer_prompts[1].encode("utf-8") == prompt_bytes
