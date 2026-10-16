"""What Ollama 0.33.2 does with `think: false` (ROADMAP, thread M, step 3).

qwen2.5:7b cannot think (no `thinking` in /api/show capabilities), qwen3:1.7b can.
Behaviour only, not timing: another project's browser tests share the Mac. Run on the
Mac with the gate site on PYTHONPATH (langchain_ollama); unloads both models after.
"""

import json
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:11434"
PROMPT = "Ответь одним предложением: сколько дней длится испытательный срок по умолчанию?"


def post(path, body, timeout=600):
    request = urllib.request.Request(
        API + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def raw(model, think):
    body = {"model": model, "prompt": PROMPT, "stream": False,
            "options": {"temperature": 0, "num_predict": 256}}
    if think is not None:
        body["think"] = think
    started = time.monotonic()
    status, data = post("/api/generate", body)
    print(f"{model} think={think!r}: HTTP {status} in {time.monotonic() - started:.1f} s")
    if status != 200:
        print("  error:", data.get("error"))
        return
    print("  thinking chars:", len(data.get("thinking") or ""), "| output tokens:",
          data.get("eval_count"), "| <think> in response:", "<think>" in data.get("response", ""))
    print("  answer:", data.get("response", "")[:120].replace("\n", " "))


raw("qwen2.5:7b", False)
raw("qwen2.5:7b", True)
raw("qwen2.5:7b", None)
post("/api/generate", {"model": "qwen2.5:7b", "keep_alive": 0}, timeout=60)
raw("qwen3:1.7b", False)

from langchain_ollama import ChatOllama, OllamaLLM  # noqa: E402

for model in ("qwen3:1.7b", "qwen2.5:7b"):
    llm = OllamaLLM(model=model, base_url=API, temperature=0, num_predict=256, reasoning=False)
    try:
        generation = llm.generate([PROMPT]).generations[0][0]
        info = generation.generation_info or {}
        print(f"OllamaLLM(reasoning=False) {model}: thinking chars",
              len(info.get("thinking") or ""), "| output tokens:", info.get("eval_count"),
              "| <think> in text:", "<think>" in generation.text)
    except Exception as exc:  # noqa: BLE001
        print(f"OllamaLLM(reasoning=False) {model}: {type(exc).__name__}: {exc}")
    chat = ChatOllama(model=model, base_url=API, temperature=0, num_predict=64, reasoning=False)
    try:
        message = chat.invoke(PROMPT)
        print(f"ChatOllama(reasoning=False) {model}: reasoning_content",
              len((message.additional_kwargs or {}).get("reasoning_content") or ""),
              "| <think> in content:", "<think>" in str(message.content))
    except Exception as exc:  # noqa: BLE001
        print(f"ChatOllama(reasoning=False) {model}: {type(exc).__name__}: {exc}")
    post("/api/generate", {"model": model, "keep_alive": 0}, timeout=60)
print("unloaded")
