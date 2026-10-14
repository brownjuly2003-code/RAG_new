"""Does qwen3:1.7b think on the chat path? One request each way, as the API's provider sends it.

The provider builds langchain_ollama.OllamaLLM (Ollama /api/generate) without a reasoning
flag; the library then puts `"think": None` into the payload, so Ollama gets `think: null`
and the model keeps its default. Prints the payload line, then for a raw request without
`think` and for the provider's class: the thinking returned beside the answer, the output
tokens and the answer's opening. Run on the Mac with the model venv and the gate site on
PYTHONPATH (where langchain_ollama lives), after the live runs, nothing else on Ollama.
"""

import inspect
import json
import time
import urllib.request

import langchain_ollama.llms
from langchain_ollama import OllamaLLM

API = "http://127.0.0.1:11434"
MODEL = "qwen3:1.7b"
PROMPT = "Ответь одним предложением: сколько дней длится испытательный срок по умолчанию?"


def ollama(path, body, timeout=600):
    request = urllib.request.Request(
        API + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


source = inspect.getsource(langchain_ollama.llms)
print("langchain_ollama.llms:", langchain_ollama.llms.__file__.split("site-packages/")[-1])
print("OllamaLLM.reasoning default:", OllamaLLM.model_fields["reasoning"].default)
print("payload carries think from reasoning:",
      '"think": kwargs.pop("reasoning", self.reasoning)' in source)

started = time.monotonic()
data = ollama("/api/generate", {"model": MODEL, "prompt": PROMPT, "stream": False,
                                "options": {"temperature": 0, "num_predict": 512}})
print("raw /api/generate, no think field: %.1f s (load %.1f s)"
      % (time.monotonic() - started, data.get("load_duration", 0) / 1e9))
print("  thinking chars:", len(data.get("thinking") or ""), "| output tokens:", data.get("eval_count"),
      "| <think> in response:", "<think>" in data.get("response", ""))
print("  answer:", data.get("response", "")[:160].replace("\n", " "))

started = time.monotonic()
llm = OllamaLLM(model=MODEL, base_url=API, temperature=0, num_predict=512)
generation = llm.generate([PROMPT]).generations[0][0]
info = generation.generation_info or {}
print("provider class OllamaLLM.generate: %.1f s" % (time.monotonic() - started))
print("  thinking chars:", len(info.get("thinking") or ""), "| output tokens:", info.get("eval_count"),
      "| <think> in text:", "<think>" in generation.text)
print("  answer:", generation.text[:160].replace("\n", " "))

ollama("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=60)
print("unloaded")
