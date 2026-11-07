"""Graph classification must never enable the simple model-routing shortcuts."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent import graph
from agent.state import create_initial_state
from llm.providers.base import LLMResponse
from vectordb import manager


def _cached(tenant="tenant-a", status="matched"):
    return SimpleNamespace(
        _graph_projection=SimpleNamespace(
            graph={"tenant_id": tenant, "entity_graph_status": status}
        )
    )


@pytest.mark.parametrize("routing", [False, True])
@pytest.mark.parametrize("verdict", ["simple", "complex", "global"])
@pytest.mark.parametrize("question_class", ["multi_hop", "aggregation", "global", "single_hop"])
def test_matched_graph_classification_preserves_routing_contract(
    monkeypatch, routing, verdict, question_class
):
    settings = SimpleNamespace(model_routing_enabled=routing, retrieval_strategy="graph")
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "_retriever_cache", {"tenant-a": _cached()})
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    monkeypatch.setattr(graph, "trace_llm_call", lambda **kwargs: None)
    response = LLMResponse(
        text=verdict,
        provider="fixture",
        model="classifier",
        structured_output={
            "complexity": verdict,
            "question_class": question_class,
            "entities": ["AWB"],
            "needs_multi_hop": question_class != "single_hop",
            "reason_code": "MULTI_SOURCE_CHAIN",
        },
        input_tokens=12,
        output_tokens=8,
    )
    llm = SimpleNamespace(
        supports_structured_output=True,
        generate_with_schema=Mock(return_value=response),
        last_response=response,
    )
    state = graph.make_classify_complexity_node(llm)(
        create_initial_state("How does AWB connect the policies?", tenant_id="tenant-a")
    )
    llm.generate_with_schema.assert_called_once()
    assert state["complexity"] == (verdict if routing else "unknown")
    assert state["question_class"] == question_class
    assert state["entities"] == ["AWB"]
    assert state["reason_code"] == "MULTI_SOURCE_CHAIN"
    assert state["usage_node"] == "classify_complexity"
    assert state["prompt_tokens"] == 12
    assert state["completion_tokens"] == 8
    if not routing:
        assert graph._route_after_retrieve(state) == "grade"
        assert graph._route_after_generate(state) == "verify"
        assert graph._select_retrieval_strategy(state) == (
            "hybrid" if question_class == "single_hop" else "graph"
        )
        fast = SimpleNamespace(invoke=Mock())
        strong = SimpleNamespace(invoke=Mock(return_value="The policies connect through AWB."))
        generated = graph.make_generate_node(fast, strong)(state)
        strong.invoke.assert_called_once()
        fast.invoke.assert_not_called()
        assert not generated.get("fact_verification_skipped")


@pytest.mark.parametrize(
    "strategy,status",
    [
        ("hybrid", "matched"),
        ("vector", "matched"),
        ("factcard", "matched"),
        ("invalid", "matched"),
        ("graph", "absent"),
        ("graph", "mismatch"),
        ("graph", "invalid"),
        ("graph", "unavailable"),
        ("graph", "no_database"),
        ("graph", None),
    ],
)
def test_routing_off_otherwise_never_calls_classifier(monkeypatch, strategy, status):
    settings = SimpleNamespace(model_routing_enabled=False, retrieval_strategy=strategy)
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    monkeypatch.setattr(manager, "_retriever_cache", {"tenant-a": _cached(status=status)})
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    llm = Mock()
    state = graph.make_classify_complexity_node(llm)(
        create_initial_state("Question", tenant_id="tenant-a")
    )
    assert state["complexity"] == state["question_class"] == "unknown"
    assert state["entities"] == []
    assert state["needs_multi_hop"] is False
    assert state["reason_code"] == "ROUTING_DISABLED"
    assert llm.mock_calls == []


def test_cached_graph_probe_is_tenant_scoped_read_only_and_fails_closed(monkeypatch):
    class BrokenRetriever:
        @property
        def _graph_projection(self):
            raise RuntimeError("Unavailable")

    cache = {
        "tenant-a": _cached(),
        "wrong-tenant": _cached(),
        "broken": BrokenRetriever(),
        "no-projection": SimpleNamespace(),
        "malformed": SimpleNamespace(_graph_projection=SimpleNamespace(graph=[])),
    }
    monkeypatch.setattr(manager, "_retriever_cache", cache)
    build = Mock(side_effect=AssertionError("Probe must not build a retriever"))
    monkeypatch.setattr(manager, "get_retriever", build)
    assert manager.has_cached_matched_entity_graph("tenant-a") is True
    for tenant in ("missing", "wrong-tenant", "broken", "no-projection", "malformed"):
        assert manager.has_cached_matched_entity_graph(tenant) is False
    build.assert_not_called()
    assert manager._retriever_cache == cache


def test_graph_only_codex_json_keeps_unknown_complexity(monkeypatch):
    settings = SimpleNamespace(
        model_routing_enabled=False, retrieval_strategy="graph", llm_provider_profile="codex-only"
    )
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    monkeypatch.setattr(manager, "_retriever_cache", {"tenant-a": _cached()})
    monkeypatch.setattr(graph, "log_step", lambda *args: None)
    monkeypatch.setattr(graph, "trace_llm_call", lambda **kwargs: None)
    llm = SimpleNamespace(supports_structured_output=False, invoke=Mock())
    llm.invoke.return_value = json.dumps(
        {
            "complexity": "simple",
            "question_class": "multi_hop",
            "entities": ["AWB"],
            "reason_code": "MULTI_SOURCE_CHAIN",
        }
    )
    state = graph.make_classify_complexity_node(llm)(
        create_initial_state("Question", tenant_id="tenant-a")
    )
    llm.invoke.assert_called_once()
    assert state["complexity"] == "unknown"
    assert state["question_class"] == "multi_hop"
    assert state["entities"] == ["AWB"]
    assert state["reason_code"] == "MULTI_SOURCE_CHAIN"
