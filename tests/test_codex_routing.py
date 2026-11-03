"""Answer-only routing, fallback, subscription spend and configurable settings."""

from config.provider_schema import load_provider_registry
from config.settings import Settings
from llm.providers import runtime


def test_profile_keeps_both_auxiliary_tiers_local_and_never_checks_paid_spend(monkeypatch):
    settings = Settings()
    settings.llm_provider_profile = "codex-answer"
    settings.daily_cost_limit_usd = 0.000001

    def forbidden(*args, **kwargs):
        raise AssertionError("A subscription answer is not paid API spend")

    monkeypatch.setattr(runtime, "_daily_paid_cost_usd", forbidden)
    built = runtime.build_provider_runtime(settings)
    assert built.answer is not None
    assert built.answer.provider_id == "codex"
    assert built.answer.model_name == "gpt-6-astra"
    assert built.answer.context_window == 3584
    assert built.answer.supports_streaming
    assert not built.answer.supports_tool_use
    for llm in (built.fast, built.strong, built.answer._fallback_provider):
        assert (llm.provider_id, llm.model_name) == ("ollama", "qwen3:4b-instruct-2507-q4_K_M")
    assert runtime.build_provider_runtime(settings) is built
    registry = load_provider_registry(settings.provider_registry_path)
    assert registry.get_provider("codex").kind == "subscription"
    assert registry.get_provider("codex").models[0].input_price_per_1m_tokens == 0
    assert registry.get_provider("codex").models[0].output_price_per_1m_tokens == 0


def test_other_profiles_do_not_gain_an_answer_override():
    registry = load_provider_registry()
    assert registry.default_profile == "local-first"
    for name, profile in registry.routing_profiles.items():
        if name not in {"codex-answer", "codex-only"}:
            assert profile.answer is None


def test_codex_settings_are_environment_overridable(monkeypatch):
    values = {
        "CODEX_BINARY": "/service/bin/codex",
        "CODEX_HOME": "/service/codex-home",
        "CODEX_MODEL": "fixture-model",
        "CODEX_REASONING_EFFORT": "high",
        "CODEX_TIMEOUT_SEC": "7.5",
        "CODEX_MAX_CONCURRENT_CALLS": "2",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    settings = Settings()
    settings.llm_provider_profile = "codex-answer"
    built = runtime.build_provider_runtime(settings)
    assert settings.codex_binary == values["CODEX_BINARY"]
    assert settings.codex_home == values["CODEX_HOME"]
    assert built.answer.model_name == "fixture-model"
    assert built.answer.stream_provider._effort == "high"
    assert built.answer.stream_provider._timeout_sec == 7.5
    assert settings.codex_max_concurrent_calls == 2


def test_answer_cache_identity_tracks_model_and_effort():
    from cache.namespace import resolve_model_identity

    settings = Settings()
    settings.llm_provider_profile = "local-first"
    local = resolve_model_identity(settings=settings)
    assert (
        local
        == "profile=local-first|fast=ollama:qwen3:4b-instruct-2507-q4_K_M|strong=ollama:qwen3:4b-instruct-2507-q4_K_M|routing=0"
    )
    settings.llm_provider_profile = "codex-answer"
    codex = resolve_model_identity(settings=settings)
    assert codex != local
    settings.codex_reasoning_effort = "high"
    assert resolve_model_identity(settings=settings) != codex
    settings.codex_reasoning_effort = "xhigh"
    settings.codex_model = "fixture-other-model"
    assert resolve_model_identity(settings=settings) != codex


def test_answer_profile_cannot_bypass_v4_via_agentic_tool_generation(monkeypatch):
    from agent import graph

    settings = Settings()
    settings.llm_provider_profile = "codex-answer"
    settings.agentic_mode = True
    monkeypatch.setattr(graph, "get_settings", lambda: settings)
    session = graph.ConversationSession(None, None)
    assert session._select_agentic_llm() is None
