"""Shared, data-free contracts for stage 4's final-path runs and later bases."""

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PY = "/Users/julia/RAG_Support_Assistant/.venv/bin/python"
SITE = "/Users/julia/RAG_new_mf_gate_site"
ONNX = "/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx"
INT8 = "57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343"
CACHE = "c75f44912ea2c7f54ea0cf0e9ffea8f05466ae447961d99c8f12d716589b4e6c"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
PROMPT = "QA_PROMPT_V4"
SETTINGS = {
    "retrieval_top_k": 14,
    "ollama_context_window": 3584,
    "reranker_runtime": "onnx",
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    "rerank_top_k": 5,
    "rerank_batch": None,
    "rag_device": "cpu",
    "ollama_model_name": "qwen3:4b-instruct-2507-q4_K_M",
    "streaming_self_eval_mode": "classic",
    "hybrid_search": True,
    "parent_expansion": True,
    "model_routing_enabled": False,
    "llm_provider_profile": "local-first",
    "streaming_timeout_sec": 3600,
    "request_timeout_sec": 3600,
    "ollama_request_timeout_sec": 3600,
}
BASES = ("aircargo", "wixqa", "conditionalqa", "multihoprag")
FIRST, REST, START = 360, 300, 120
MAX_REASK = 6
NOT_EVIDENCE = "NOT_EVIDENCE"


def require(ok, message):
    if not ok:
        raise SystemExit("NOT_EVIDENCE: " + message)


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def frozen(name):
    sys.path.insert(0, str(ROOT / "reports/stage2/tools"))
    sys.path.insert(0, str(ROOT))
    paths = {
        "arms": "reports/stage7/tools/arms_replay.py",
        "v4": "reports/answer-prompt-v4/tools/v4_record.py",
        "summary": "reports/stage2/tools/answers_summary.py",
        "export": "reports/stage2/tools/judge_export.py",
        "cases": "reports/stage2/tools/stage2_cases.py",
        "supervisor": "reports/stage1/tools/live_supervisor.py",
        "sampler": "reports/stage4-step0/tools/step0_sampler.py",
    }
    return load(paths[name], "final_frozen_" + name)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text("utf-8").splitlines() if line]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def positive(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def questions(base, data):
    require(base in BASES, "unknown base")
    path = (
        ROOT / "evaluation/curated_cases_aircargo.jsonl"
        if base == "aircargo"
        else Path(data) / base / "cases.jsonl"
    )
    module = frozen("cases")
    module.AIRCARGO["aircargo"] = ROOT / "evaluation/curated_cases_aircargo.jsonl"
    ids = module.registered(base, path)
    require(len(ids) == 100 and len(set(ids)) == 100, "the base must hold the registered 100")
    return path, ids


def forecast(count, batches, reasks=0):
    return batches * (START + FIRST) + (count - batches + reasks) * REST
