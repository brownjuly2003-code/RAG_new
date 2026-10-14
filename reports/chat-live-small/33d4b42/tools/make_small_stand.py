"""Build the tools of the small-model stand from the published 33d4b42 tools.

Only live_supervisor.py, export.py and export.sh change: the stand may serve another local
model (MODEL=<tag>) for a measurement, through OLLAMA_MODEL_NAME and a copy of
config/providers.yml whose local-first profile names it; the export reads the model of
each run from its launch.json. Output: D:/RAG_new/.tmp/chat-live/small-stand/.
"""

import shutil
from pathlib import Path

SRC = Path("D:/RAG_new/reports/chat-live/33d4b42/tools")
OUT = Path("D:/RAG_new/.tmp/chat-live/small-stand")


def patch(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
for path in SRC.iterdir():
    if path.is_file() and path.name not in ("r2.sh", "watch.sh", "old_prod_lat.py", "summary.py"):
        shutil.copy2(path, OUT / path.name)

sup = (OUT / "live_supervisor.py").read_text(encoding="utf-8")
sup = patch(
    sup,
    "  SETTING=VALUE - a deployment setting applied after MODE; only DEPLOYMENT names are\n"
    "               allowed (on this Mac RAG_DEVICE=auto puts the reranker on the 4 GB GPU\n"
    "               next to the embedder, where it fails with MPS out of memory: run B1).\n",
    "  SETTING=VALUE - a deployment setting applied after MODE; only DEPLOYMENT names are\n"
    "               allowed (on this Mac RAG_DEVICE=auto puts the reranker on the 4 GB GPU\n"
    "               next to the embedder, where it fails with MPS out of memory: run B1).\n"
    "  MODEL=<tag>  - serve another local model, for the measurement only: the API gets\n"
    "               OLLAMA_MODEL_NAME (the stream's generation and self-evaluation) and a\n"
    "               copy of config/providers.yml whose local-first profile and Ollama\n"
    "               defaults name it (PROVIDER_REGISTRY_PATH, the graph's calls); the code\n"
    "               defaults stay. Default qwen2.5:7b, the model of the code defaults.\n",
)
sup = patch(
    sup,
    'DEPLOYMENT = {"RAG_DEVICE"}\n',
    'DEPLOYMENT = {"RAG_DEVICE"}\nDEFAULT_MODEL = "qwen2.5:7b"\n',
)
sup = patch(
    sup,
    "    assert set(extra) <= DEPLOYMENT and all(re.fullmatch(r\"[a-z0-9:]+\", v) for v in extra.values())\n",
    "    assert set(extra) <= DEPLOYMENT | {\"MODEL\"}\n"
    "    assert all(re.fullmatch(r\"[A-Za-z0-9:._-]+\", v) for v in extra.values())\n"
    "    model = extra.pop(\"MODEL\", DEFAULT_MODEL)\n",
)
sup = patch(
    sup,
    '              "overrides": overrides}\n',
    '              "overrides": overrides, "model": model}\n',
)
sup = patch(
    sup,
    "                    **overrides})\n\n        if mode == \"retrieval\":\n",
    "                    **overrides})\n"
    "        if model != DEFAULT_MODEL:\n"
    "            env.update({\"OLLAMA_MODEL_NAME\": model,\n"
    "                        \"PROVIDER_REGISTRY_PATH\": str(registry_for(model, out))})\n"
    "        launch[\"model_digest\"] = next(\n"
    "            (m.get(\"digest\") for m in ollama(\"/api/tags\").get(\"models\", [])\n"
    "             if m.get(\"name\") == model), None)\n"
    "        if not launch[\"model_digest\"]:\n"
    "            raise RuntimeError(f\"Ollama does not hold {model}\")\n\n"
    "        if mode == \"retrieval\":\n",
)
sup = patch(
    sup,
    '        ollama("/api/generate", {"model": "qwen2.5:7b", "keep_alive": "30m"}, timeout=300)\n',
    '        ollama("/api/generate", {"model": model, "keep_alive": "30m"}, timeout=300)\n',
)
sup = patch(
    sup,
    "def main():\n",
    "def registry_for(model, out):\n"
    "    \"\"\"config/providers.yml with the local-first profile and Ollama's defaults on MODEL.\"\"\"\n"
    "    import yaml\n\n"
    "    data = yaml.safe_load((WS / \"config\" / \"providers.yml\").read_text(encoding=\"utf-8\"))\n"
    "    provider = next(item for item in data[\"providers\"] if item[\"id\"] == \"ollama\")\n"
    "    provider[\"default_models\"] = {\"fast\": model, \"strong\": model}\n"
    "    if all(item[\"name\"] != model for item in provider[\"models\"]):\n"
    "        provider[\"models\"].append({\"name\": model, \"aliases\": [],\n"
    "                                   \"input_price_per_1m_tokens\": 0.0,\n"
    "                                   \"output_price_per_1m_tokens\": 0.0})\n"
    "    profile = data[\"routing_profiles\"][\"local-first\"]\n"
    "    profile[\"fast\"][\"model\"] = profile[\"strong\"][\"model\"] = model\n"
    "    path = out / \"providers.yml\"\n"
    "    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding=\"utf-8\")\n"
    "    return path\n\n\n"
    "def main():\n",
)
(OUT / "live_supervisor.py").write_text(sup, encoding="utf-8", newline="\n")

exp = (OUT / "export.py").read_text(encoding="utf-8")
exp = patch(
    exp,
    '    model = next(m for m in ollama("/api/tags")["models"] if m["name"] == MODEL)\n',
    '    digests = {m["name"]: m["digest"] for m in ollama("/api/tags")["models"]}\n',
)
exp = patch(
    exp,
    '        "ollama": {"version": ollama("/api/version")["version"], "model": MODEL,\n'
    '                   "digest": model["digest"]},\n',
    '        "ollama": {"version": ollama("/api/version")["version"]},\n',
)
exp = patch(
    exp,
    '            "ollama_load_sec": launch.get("ollama_load_sec"),\n',
    '            "model": launch.get("model", MODEL),\n'
    '            "model_digest": launch.get("model_digest") or digests[launch.get("model", MODEL)],\n'
    '            "ollama_models_before": launch.get("ollama_models_before"),\n'
    '            "ollama_models_after": launch.get("ollama_models_after"),\n'
    '            "ollama_load_sec": launch.get("ollama_load_sec"),\n',
)
exp = patch(
    exp,
    "Usage (Mac, model venv, clean environment, CHAT_RUN_DIR set to any scratch directory,\n"
    "after analyze.py of every label): export.py OUT_JSON LABEL...\n",
    "Usage (Mac, model venv, clean environment, CHAT_RUN_DIR set to any scratch directory,\n"
    "after analyze.py of every label): export.py OUT_JSON LABEL...\n"
    "Each run names the model it served (MODEL of live_supervisor.py) and its digest.\n",
)
(OUT / "export.py").write_text(exp, encoding="utf-8", newline="\n")

(OUT / "export.sh").write_text(
    """#!/bin/bash
# Export the given runs into chatlive-small/runs.json from a clean environment (no env.json:
# the clean Settings() must hold the code defaults), then scan it for secret-like strings.
# Usage: export.sh LABEL...
set -euo pipefail
CL=/Users/julia/RAG_new_chat_33d4b42/chatlive-small
WS=/Users/julia/RAG_new_chat_33d4b42
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
if pgrep -f "live_(supervisor|retrieval|api|runner)" >/dev/null; then
  echo "a live_ process is running; refuse"; exit 3
fi
SCRATCH=$(mktemp -d /tmp/chatlive-export.XXXXXX)
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/julia CHAT_RUN_DIR="$SCRATCH" \\
  PYTHONPATH="$WS:/Users/julia/RAG_new_mf_gate_site" PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 \\
  "$PY" -u "$CL/export.py" "$CL/runs.json" "$@"
"$PY" -I "$CL/check_export.py" "$CL/runs.json"
ls -A "$SCRATCH"
rm -rf "${SCRATCH:?}"
shasum -a 256 "$CL/runs.json"
""",
    encoding="utf-8",
    newline="\n",
)
print(sorted(path.name for path in OUT.iterdir()))
