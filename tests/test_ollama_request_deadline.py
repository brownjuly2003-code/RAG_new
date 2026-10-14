"""Request expiry must bound local inference, including periodic token streams."""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from llm.providers.ollama import OllamaProvider, _instantiate_with_timeout
from utils import request_deadline as rd


class OllamaRequestDeadlineTests(unittest.TestCase):
    def tearDown(self):
        rd.clear_request_deadline()

    def test_transport_uses_remaining_request_budget(self):
        from langchain_ollama import OllamaLLM

        with patch.object(rd.time, "monotonic", return_value=100):
            rd.set_request_deadline(rd.RequestDeadline(expires_at=108, source="request"))
            binding = _instantiate_with_timeout(OllamaLLM, model="test", timeout_sec=60)
        self.assertEqual(binding._client._client.timeout.read, 8)
        self.assertEqual(binding._async_client._client.timeout.read, 8)

    def test_expired_request_does_not_construct_a_client(self):
        with patch.object(rd.time, "monotonic", return_value=100):
            rd.set_request_deadline(rd.RequestDeadline(expires_at=99, source="request"))
            with self.assertRaises(rd.RequestDeadlineExceeded):
                _instantiate_with_timeout(lambda **kwargs: self.fail("client created"), timeout_sec=60)

    def _provider(self):
        return OllamaProvider(model_name="qwen2.5:7b", base_url="http://ollama.test",
                              timeout_sec=60, input_price_per_1m_tokens=0,
                              output_price_per_1m_tokens=0)

    def test_periodic_tokens_cannot_keep_expired_request_alive(self):
        state = {"closed": False, "consumed": []}

        class Binding:
            def __init__(self, **kwargs):
                pass

            def invoke(self, prompt):
                return "late whole answer"

            def stream(self, prompt):
                try:
                    state["consumed"].append("first")
                    yield "first "
                    rd.set_request_deadline(rd.RequestDeadline(expires_at=0, source="tokens"))
                    state["consumed"].append("late")
                    yield "late"
                    state["consumed"].append("must-not-consume")
                    yield "extra"
                finally:
                    state["closed"] = True

        module = types.ModuleType("langchain_ollama")
        module.OllamaLLM = Binding
        rd.bind_request_deadline(30, source="tokens")
        with patch.dict(sys.modules, langchain_ollama=module):
            with self.assertRaises(rd.RequestDeadlineExceeded):
                self._provider().generate([{"role": "user", "content": "question"}])
        self.assertEqual(state["consumed"], ["first", "late"])
        self.assertTrue(state["closed"])

    def test_live_request_keeps_all_tokens_and_role_parameters(self):
        state = {}

        class Binding:
            def __init__(self, **kwargs):
                state.update(kwargs)

            def invoke(self, prompt):
                return "wrong invocation"

            def stream(self, prompt):
                yield "one "
                yield "two"

        module = types.ModuleType("langchain_ollama")
        module.OllamaLLM = Binding
        rd.bind_request_deadline(30, source="live")
        with patch.dict(sys.modules, langchain_ollama=module):
            result = self._provider().generate([{"role": "user", "content": "question"}],
                                               temperature=0.2, max_tokens=1024)
        self.assertEqual(result.text, "one two")
        self.assertEqual(state["temperature"], 0.2)
        self.assertEqual(state["num_predict"], 1024)


if __name__ == "__main__":
    unittest.main()
