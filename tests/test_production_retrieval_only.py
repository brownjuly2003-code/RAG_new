"""T-65 baseline stops the production graph before answer generation."""

from __future__ import annotations

import json

import pytest

from scripts import ab_remote_contextual as remote


@pytest.mark.parametrize("grade", ["YES", "NO"])
@pytest.mark.parametrize("simple", [False, True])
def test_retrieval_only_keeps_graded_context_without_generating(monkeypatch, grade, simple):
    import config.settings
    from agent import graph
    from config.settings import Settings
    from tests.test_ask_contract_route import _SIMPLE_CLASSIFICATION, _fixture_model, _policy_seed

    settings = Settings()
    settings.agentic_mode = False
    settings.ask_budget_sec = 0
    settings.model_routing_enabled = simple
    settings.hyde = False
    settings.online_evaluators_enabled = True
    monkeypatch.setattr(config.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    calls = []
    monkeypatch.setattr(graph, "log_step", lambda _, node, state: calls.append(node))

    def forbidden(*args, **kwargs):
        pytest.fail("retrieval-only replay called an answer-stage operation")

    monkeypatch.setattr(graph, "build_qa_prompt", forbidden)
    monkeypatch.setattr(graph, "run_online_evaluators", forbidden)
    monkeypatch.setattr(graph, "_record_auto_response_verification", forbidden)

    class Retriever:
        def get_relevant_documents(self, query):
            return [_policy_seed()]

    session = graph.ConversationSession(
        Retriever(), _fixture_model(["policy", grade], _SIMPLE_CLASSIFICATION if simple else None)
    )
    result = remote.production_case(
        {"case_id": "one", "query": "policy"}, session,
        tenant_id="aircargo", retrieval_only=True,
    )
    assert not result["state"].get("error")
    assert ("grade_docs" in calls) is not simple
    assert "generate" not in calls
    assert result["cands"] == (["Seed policy."] if simple or grade == "YES" else [])
    assert not result["state"].get("answer")
    assert session.history == []


def test_retrieval_only_refuses_agentic_mode(monkeypatch):
    from agent import graph
    from config.settings import get_settings

    monkeypatch.setattr(get_settings(), "agentic_mode", True)
    session = graph.ConversationSession(None)
    with pytest.raises(ValueError, match="agentic"):
        session.ask("policy", retrieval_only=True)
    assert session.history == []


def test_retrieval_only_stage_records_mode(monkeypatch, tmp_path):
    from agent import graph
    from vectordb import manager

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({"case_id": "one", "query": "policy"}), encoding="utf-8")
    calls = []

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        def ask(self, question, **kwargs):
            calls.append(kwargs)
            return {"question": question, "context_docs": []}

    monkeypatch.setattr(graph, "ConversationSession", Session)
    monkeypatch.setattr(manager, "get_retriever", lambda **kwargs: None)
    output = tmp_path / "output"
    assert remote.main([
        "--cases", str(cases), "--out-dir", str(output), "--retrieval-only",
    ]) == 0
    rows = json.loads((output / "production_retrieval_contexts.json").read_text(encoding="utf-8"))
    assert calls == [{"tenant_id": "aircargo", "retrieval_only": True}]
    assert rows[0]["execution_mode"] == "retrieval_only"


def test_retrieval_only_cli_rejects_legacy_stage(capsys):
    with pytest.raises(SystemExit, match="2"):
        remote.main(["--stage", "report", "--retrieval-only"])
    assert "--retrieval-only requires --stage production" in capsys.readouterr().err
