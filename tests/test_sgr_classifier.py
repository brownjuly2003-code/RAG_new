"""GR-0.4: structured query classification without changing legacy routing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from agent.state import create_initial_state
from llm.providers import LLMResponse


def test_initial_state_has_safe_sgr_defaults() -> None:
    state = create_initial_state(question="Где мой груз?", trace_id="sgr-defaults")

    assert state["question_class"] == "unknown"
    assert state["entities"] == []
    assert state["needs_multi_hop"] is False
    assert state["reason_code"] == "NOT_CLASSIFIED"


def test_classifier_uses_complete_sgr_schema_and_persists_result(monkeypatch) -> None:
    import agent.graph as graph

    class _SchemaLLM:
        provider_id = "gracekelly"
        model_name = "mistral-small"
        supports_structured_output = True

        def __init__(self) -> None:
            self.last_response = None
            self.schema: dict[str, Any] | None = None

        def generate_with_schema(self, messages, schema, **kwargs):
            _ = messages, kwargs
            self.schema = schema
            response = LLMResponse(
                text='{"complexity":"complex","question_class":"multi_hop"}',
                provider=self.provider_id,
                model=self.model_name,
                structured_output={
                    "complexity": "complex",
                    "question_class": "multi_hop",
                    "entities": ["AWB", "перевозчик"],
                    "needs_multi_hop": True,
                    "reason_code": "MULTI_SOURCE_CHAIN",
                },
                input_tokens=12,
                output_tokens=8,
            )
            self.last_response = response
            return response

    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: SimpleNamespace(model_routing_enabled=True),
    )
    monkeypatch.setattr(graph, "trace_llm_call", lambda **kwargs: None)
    monkeypatch.setattr(graph, "log_step", lambda *args, **kwargs: None)

    llm = _SchemaLLM()
    result = graph.make_classify_complexity_node(llm)(
        create_initial_state(
            question="Как связать AWB с ответственностью перевозчика?",
            trace_id="sgr-schema",
        )
    )

    assert llm.schema is not None
    assert llm.schema["required"] == [
        "complexity",
        "question_class",
        "entities",
        "needs_multi_hop",
        "reason_code",
    ]
    properties = llm.schema["properties"]
    assert properties["question_class"]["enum"] == [
        "single_hop",
        "multi_hop",
        "aggregation",
        "global",
    ]
    assert result["complexity"] == "complex"
    assert result["question_class"] == "multi_hop"
    assert result["entities"] == ["AWB", "перевозчик"]
    assert result["needs_multi_hop"] is True
    assert result["reason_code"] == "MULTI_SOURCE_CHAIN"


def test_legacy_one_word_classifier_keeps_compatible_sgr_fields(monkeypatch) -> None:
    import agent.graph as graph

    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: SimpleNamespace(model_routing_enabled=True),
    )
    monkeypatch.setattr(graph, "trace_llm_call", lambda **kwargs: None)
    monkeypatch.setattr(graph, "log_step", lambda *args, **kwargs: None)

    llm = MagicMock()
    llm.invoke.return_value = "SIMPLE"
    result = graph.make_classify_complexity_node(llm)(
        create_initial_state(question="Где мой груз?", trace_id="sgr-legacy")
    )

    assert result["complexity"] == "simple"
    assert result["question_class"] == "single_hop"
    assert result["entities"] == []
    assert result["needs_multi_hop"] is False
    assert result["reason_code"] == "SINGLE_SOURCE"


def test_sgr_metadata_does_not_change_legacy_retrieval_routes(monkeypatch) -> None:
    import agent.graph as graph

    settings = SimpleNamespace(retrieval_strategy="hybrid")
    monkeypatch.setattr(graph, "get_settings", lambda: settings)

    assert graph._select_retrieval_strategy(
        {"complexity": "simple", "question_class": "single_hop"}
    ) == "vector"
    assert graph._select_retrieval_strategy(
        {
            "complexity": "complex",
            "question_class": "multi_hop",
            "needs_multi_hop": True,
        }
    ) == "hybrid"
    assert graph._select_retrieval_strategy(
        {"complexity": "global", "question_class": "global"}
    ) == "hybrid"

    settings.retrieval_strategy = "graph"
    assert graph._select_retrieval_strategy(
        {"complexity": "global", "question_class": "global"}
    ) == "graph"
