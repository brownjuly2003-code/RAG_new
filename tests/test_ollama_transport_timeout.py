"""Transport regression checks; no Ollama server or model invocation."""
from __future__ import annotations

import unittest
from typing import ClassVar

from llm.providers.ollama import _instantiate_with_timeout


class OllamaTransportTimeoutTests(unittest.TestCase):
    def test_declared_client_kwargs_wins_over_silently_ignored_timeout(self):
        class Binding:
            model_fields: ClassVar[dict[str, object]] = {"model": object(), "client_kwargs": object()}

            def __init__(self, **kwargs):
                self.client_kwargs = kwargs.get("client_kwargs", {})

        binding = _instantiate_with_timeout(Binding, model="test", timeout_sec=15)
        self.assertEqual(binding.client_kwargs.get("timeout"), 15)

    def test_client_kwargs_preserves_existing_options(self):
        class Binding:
            model_fields: ClassVar[dict[str, object]] = {"client_kwargs": object()}

            def __init__(self, **kwargs):
                self.client_kwargs = kwargs.get("client_kwargs", {})

        options = {"headers": {"X-Test": "value"}, "timeout": 99}
        binding = _instantiate_with_timeout(
            Binding, timeout_sec=15, client_kwargs=options
        )
        self.assertEqual(binding.client_kwargs, {"headers": {"X-Test": "value"}, "timeout": 15})
        self.assertEqual(options["timeout"], 99)

    def test_legacy_declared_request_timeout_is_used(self):
        class Binding:
            __fields__: ClassVar[dict[str, object]] = {"request_timeout": object()}

            def __init__(self, **kwargs):
                self.request_timeout = kwargs.get("request_timeout")

        binding = _instantiate_with_timeout(Binding, timeout_sec=15)
        self.assertEqual(binding.request_timeout, 15)

    def test_strict_legacy_constructor_remains_supported(self):
        class Binding:
            def __init__(self, *, model, request_timeout):
                self.timeout = request_timeout

        binding = _instantiate_with_timeout(Binding, model="test", timeout_sec=15)
        self.assertEqual(binding.timeout, 15)

    def test_installed_llm_sync_and_async_clients_have_timeout(self):
        from langchain_ollama import OllamaLLM

        binding = _instantiate_with_timeout(OllamaLLM, model="test", timeout_sec=15)
        self.assertEqual(binding._client._client.timeout.read, 15)
        self.assertEqual(binding._async_client._client.timeout.read, 15)

    def test_installed_chat_sync_and_async_clients_have_timeout(self):
        from langchain_ollama import ChatOllama

        binding = _instantiate_with_timeout(ChatOllama, model="test", timeout_sec=15)
        self.assertEqual(binding._client._client.timeout.read, 15)
        self.assertEqual(binding._async_client._client.timeout.read, 15)

    def test_graph_compatibility_binding_also_has_timeout(self):
        from langchain_ollama import OllamaLLM

        from agent.graph import _instantiate_local_ollama

        binding = _instantiate_local_ollama(OllamaLLM, "test", 15)
        self.assertEqual(binding._client._client.timeout.read, 15)


if __name__ == "__main__":
    unittest.main()
