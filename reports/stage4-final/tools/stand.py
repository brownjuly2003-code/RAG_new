"""Check the final path without loading a model; also run inside the observed API."""

import os
import sys
from pathlib import Path

from common import CACHE, INT8, MODEL_DIGEST, ONNX, PROMPT, PY, ROOT, SETTINGS, frozen, require, sha


def effective(values, prompt, limit):
    for key, wanted in SETTINGS.items():
        require(values.get(key) == wanted, "effective setting differs: " + key)
    require(values.get("reranker_onnx_path") == ONNX, "effective ONNX path differs")
    require(prompt == PROMPT and limit == 2176, "prompt or input limit differs")


def files(onnx, cache):
    for path, digest, label in ((onnx, INT8, "INT8 export"), (cache, CACHE, "cache config")):
        require(Path(path).is_file(), label + " absent")
        require(sha(path) == digest, label + " digest differs")


def environment():
    arms = frozen("arms")
    held = arms.environment()
    environment_gate(held)
    arms.package_batch()  # RAG_RERANK_BATCH must be unset, effective batch 32.
    return held


def environment_gate(held):
    arms = frozen("arms")
    require(held["executable"] == PY, "use the service interpreter")
    require(held["versions"]["tokenizers"] == "0.19.1", "tokenizers differs")
    require(held["versions"]["transformers"] == arms.TRANSFORMERS_VERSION, "transformers differs")
    require(
        held["ort_version"] == held["versions"]["onnxruntime"] == arms.ORT_VERSION, "ORT differs"
    )
    require(held["tokenizer_snapshot"] == arms.TOKENIZER_SNAPSHOT, "snapshot differs")
    require(
        held["offline"] == {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        "offline flags differ",
    )
    require(held["ort_intra_op_num_threads"] == 0, "ORT threads differ")


def check():
    sys.path.insert(0, str(ROOT))
    from agent.context_window import prompt_input_limit
    from agent.prompts import build_qa_prompt
    from config.settings import get_settings
    from scripts.chat_answer_judge import prompt_id

    require(not (ROOT / ".env").exists(), "a stand must not have a .env")
    held = environment()
    files(os.getenv("RAG_RERANKER_ONNX", ""), Path.home() / ".config/llama.cpp/config.ini")
    settings = get_settings()
    # The same owner and budget call as stage 7's Builder; no inference or model load.
    from types import SimpleNamespace

    owner = SimpleNamespace(context_window=settings.ollama_context_window)
    values = {key: getattr(settings, key) for key in SETTINGS}
    values["reranker_onnx_path"] = str(settings.reranker_onnx_path)
    prompt = prompt_id(build_qa_prompt("synthetic question", []))
    limit = prompt_input_limit(owner, "generate")
    effective(values, prompt, limit)
    supervisor = frozen("supervisor")
    require(supervisor.ollama("/api/version").get("version") == "0.33.2", "Ollama version differs")
    tags = supervisor.ollama("/api/tags").get("models", [])
    require(
        any(
            m.get("name") == SETTINGS["ollama_model_name"] and m.get("digest") == MODEL_DIGEST
            for m in tags
        ),
        "the code-default model tag must name the measured 4B digest",
    )
    server = (
        __import__("common")
        .load("reports/answer-prompt-v4/tools/stand_env.py", "final_server")
        .ollama()
    )
    require(len(server["servers"]) == 1, "not one Ollama server")
    return {
        "environment": held,
        "settings": values,
        "prompt_id": prompt,
        "input_limit": limit,
        "export_sha256": INT8,
        "cache_sha256": CACHE,
        "ollama": "0.33.2",
        "model_digest": MODEL_DIGEST,
        "server": server,
        "rerank_batch": None,
        "batch_size": 32,
    }


if __name__ == "__main__":
    import contextlib
    import json

    # Imported product diagnostics must not corrupt the receipt read by the supervisor.
    with contextlib.redirect_stdout(sys.stderr):
        receipt = check()
    print(json.dumps(receipt, indent=2))
