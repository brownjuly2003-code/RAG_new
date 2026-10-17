"""Does Ollama 0.33.2's runner grow per request, with no API around it? (stdin script, Mac)

Loads the 4B, reads the llama-server's footprint (top's MEM and CMPRS), sends eight of the
q30-r2 run's own stream prompts through /api/generate as the provider does (num_ctx 4096,
think false, a short output), reads it after each, then unloads. Refuses unless Ollama holds
no model and no live process runs.
"""

import json
import subprocess
import time
import urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PROMPTS = Path("/Users/julia/RAG_new_chat_19beeb1/chatlive/runs/qwen3-4b-instruct-q30-r2/prompts")


def call(path, payload=None, timeout=900):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(OLLAMA + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def runner():
    out = subprocess.run(["/usr/bin/top", "-l", "1", "-stats", "pid,command,mem,cmprs"],
                         capture_output=True, text=True, timeout=30).stdout
    rows = [line.split() for line in out.splitlines() if "llama-server" in line]
    swap = subprocess.run(["/usr/sbin/sysctl", "-n", "vm.swapusage"], capture_output=True,
                          text=True, timeout=10).stdout.strip()
    return {"runner": rows, "swap": swap[:42]}


assert call("/api/ps")["models"] == [], "Ollama holds a model"
assert subprocess.run(["/usr/bin/pgrep", "-f", "live_(supervisor|api|runner)"],
                      capture_output=True).returncode == 1, "a live process runs"
print("before", runner(), flush=True)
started = time.monotonic()
call("/api/generate", {"model": MODEL, "keep_alive": "30m"})
print("loaded", round(time.monotonic() - started, 1), "s", call("/api/ps")["models"][0]["size"],
      runner(), flush=True)
prompts = sorted(PROMPTS.glob("*-stream.txt"))[:8]
for path in prompts:
    started = time.monotonic()
    reply = call("/api/generate", {
        "model": MODEL, "prompt": path.read_text(encoding="utf-8"), "stream": False,
        "think": False, "keep_alive": "30m",
        "options": {"num_ctx": 4096, "num_predict": 48, "temperature": 0.0}})
    print(path.name, round(time.monotonic() - started, 1), "s prompt_eval",
          reply.get("prompt_eval_count"), "eval", reply.get("eval_count"), runner(), flush=True)
call("/api/generate", {"model": MODEL, "keep_alive": 0})
time.sleep(5)
print("unloaded", call("/api/ps")["models"], runner(), flush=True)
