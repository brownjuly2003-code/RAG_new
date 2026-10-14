"""Local-model input window: token estimate, num_ctx and the oversized-prompt warning.

No Ollama server or model is needed: the langchain binding is replaced by a
recording fake. The pinned counts below are exact Qwen2.5 token counts of the
samples, measured on 2026-10-14 with the tokenizer.json of Qwen/Qwen2.5-7B-Instruct
(HF snapshot a09a35458c702b33eeacc393d103063234e8bc28) on deproject-mac.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import types
from unittest.mock import patch

import pytest

from llm.providers.base import ProviderBackedLLM, estimate_window_tokens, window_input_limit
from llm.providers.ollama import OllamaProvider

SAMPLES = {
    "ru_policy": (
        "Работодатель не вправе расторгнуть трудовой договор с беременной женщиной по своей "
        "инициативе, за исключением случаев ликвидации организации либо прекращения "
        "деятельности индивидуальным предпринимателем. Если срок срочного трудового договора "
        "истекает в период беременности, работодатель обязан по письменному заявлению женщины "
        "продлить его до окончания беременности, а при предоставлении отпуска по беременности "
        "и родам — до окончания такого отпуска."
    ),
    "en_policy": (
        "Shipments containing lithium batteries must be declared before acceptance. The shipper "
        "provides the UN number, the packing instruction and the state of charge for each "
        "consignment. Cargo that arrives without the declaration is held at the terminal until "
        "the documents are corrected, and the delay is recorded against the booking."
    ),
    "table_digits": "| 2026-10-14 | AWB 176-12345675 | 1250.50 kg | 3 pcs | 14:35 |\n" * 6,
    "json_record": json.dumps(
        {"case_id": "aircargo-0042", "weight_kg": 1250.5, "pieces": 3, "flags": ["DGR", "CAO"]},
        ensure_ascii=False,
    ),
    "zh_sentence": "这是一个用于测试分词器的中文句子，包含常见的汉字和标点符号。",
}
QWEN25_TOKENS = {
    "ru_policy": 134,
    "en_policy": 58,
    "table_digits": 300,
    "json_record": 43,
    "zh_sentence": 18,
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_estimate_stays_near_exact_qwen_count(name):
    exact = QWEN25_TOKENS[name]
    estimate = estimate_window_tokens(SAMPLES[name])
    # Never more than 20% low (the window keeps a margin for that) and, for
    # prose, far below the fivefold UTF-8 byte count it replaces.
    assert estimate >= 0.8 * exact
    assert estimate <= 1.7 * exact


def test_byte_bound_would_overcount_russian_fivefold():
    text = SAMPLES["ru_policy"]
    assert len(text.encode("utf-8")) / QWEN25_TOKENS["ru_policy"] > 4.5
    assert estimate_window_tokens(text) / QWEN25_TOKENS["ru_policy"] < 1.3


def test_window_limit_keeps_output_reserve_and_margin():
    assert window_input_limit(4096, 1024) == int(3072 * 0.9) - 128
    assert window_input_limit(512, 1024) == 0


def _recording_binding(state):
    class Binding:
        def __init__(self, **kwargs):
            state["kwargs"] = kwargs

        def invoke(self, prompt):
            state["prompt"] = prompt
            return "ответ"

        def stream(self, prompt):
            state["prompt"] = prompt
            yield "ответ"

        async def astream(self, prompt):
            state["prompt"] = prompt
            yield "отв"
            yield "ет"

    module = types.ModuleType("langchain_ollama")
    module.OllamaLLM = Binding
    return module


def _provider(window=4096):
    return OllamaProvider(
        model_name="qwen2.5:7b",
        base_url="http://ollama.test",
        timeout_sec=60,
        input_price_per_1m_tokens=0,
        output_price_per_1m_tokens=0,
        context_window=window,
    )


def _five_chunk_prompt():
    # About 4.5k characters / 9k UTF-8 bytes of Russian, the size of a real
    # five-chunk prompt (1,447–1,681 Qwen tokens on the aircargo corpus).
    return "\n\n".join([SAMPLES["ru_policy"]] * 11)


def test_generate_sends_window_and_output_budget():
    state = {}
    with patch.dict(sys.modules, langchain_ollama=_recording_binding(state)):
        result = _provider().generate(
            [{"role": "user", "content": _five_chunk_prompt()}], temperature=0.2, max_tokens=1024
        )
    assert result.text == "ответ"
    assert state["kwargs"]["num_ctx"] == 4096
    assert state["kwargs"]["num_predict"] == 1024
    assert state["kwargs"]["temperature"] == 0.2


def test_realistic_russian_prompt_fits_where_the_byte_bound_refused():
    prompt = _five_chunk_prompt()
    assert len(prompt.encode("utf-8")) > 4096 - 1024 - 128
    state = {}
    with patch.dict(sys.modules, langchain_ollama=_recording_binding(state)):
        _provider().generate([{"role": "user", "content": prompt}], max_tokens=1024)
    assert state["prompt"].endswith(prompt)


def test_oversized_prompt_is_logged_with_its_estimate(caplog):
    state = {}
    prompt = "\n\n".join([SAMPLES["ru_policy"]] * 40)
    with patch.dict(sys.modules, langchain_ollama=_recording_binding(state)):
        with caplog.at_level(logging.WARNING, logger="llm.providers.ollama"):
            _provider().generate([{"role": "user", "content": prompt}], max_tokens=1024)
    assert "exceeds the 2636-token input limit of num_ctx=4096" in caplog.text
    assert state["kwargs"]["num_ctx"] == 4096


def test_fitting_prompt_logs_nothing(caplog):
    state = {}
    with patch.dict(sys.modules, langchain_ollama=_recording_binding(state)):
        with caplog.at_level(logging.WARNING, logger="llm.providers.ollama"):
            _provider().generate(
                [{"role": "user", "content": _five_chunk_prompt()}], max_tokens=1024
            )
    assert "exceeds" not in caplog.text


def test_stream_sends_window_and_output_budget():
    state = {}

    async def collect(prompt):
        return [
            chunk
            async for chunk in _provider().generate_stream(
                [{"role": "user", "content": prompt}], max_tokens=1024, temperature=0.2
            )
        ]

    with patch.dict(sys.modules, langchain_ollama=_recording_binding(state)):
        assert asyncio.run(collect(_five_chunk_prompt())) == ["отв", "ет"]
    assert state["kwargs"]["num_ctx"] == 4096
    assert state["kwargs"]["num_predict"] == 1024
    assert state["kwargs"]["temperature"] == 0.2


def test_runtime_wrapper_reports_the_smaller_window_of_primary_and_fallback():
    llm = ProviderBackedLLM(_provider(8192), fallback_provider=_provider(4096))
    assert llm.context_window == 4096
    assert (
        ProviderBackedLLM(types.SimpleNamespace(provider_id="x", model_name="y")).context_window
        is None
    )


def test_runtime_passes_configured_window_to_ollama(monkeypatch):
    from config.settings import Settings
    from llm.providers.runtime import _instantiate_provider

    monkeypatch.setenv("OLLAMA_CONTEXT_WINDOW", "8192")
    provider = _instantiate_provider(Settings(), "ollama", "qwen2.5:7b")
    assert provider.context_window == 8192
