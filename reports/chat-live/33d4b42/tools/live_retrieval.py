"""Time retrieval alone, as the API's retriever runs it, under one device placement.

Run by live_supervisor.py (mode retrieval) with no model held by Ollama, so the numbers
are the floor that retrieval sets for any generator on this Mac; nothing is generated.
Usage: live_retrieval.py VARIANT CASES
  VARIANT cpu        - embedder and reranker on the CPU;
          auto       - both where RAG_DEVICE=auto puts them (MPS on this Mac);
          rerank-mps - the reranker alone on the GPU (MPS), the embedder on the CPU;
          embed-mps  - the embedder alone on the GPU, the reranker on the CPU;
          any of them with "-b<N>" - the same with RAG_RERANK_BATCH=N (cross-encoder batch).
  CASES   comma-separated case ids; "warmup:<question>" as in live_runner.py.
Writes CHAT_RUN_DIR/retrieval-VARIANT.json: model loads, and per question the walls of
retrieval, vector search and rerank, whether the reranker succeeded (with the error the
retriever logged when it did not), the effective batch, the top documents. A variant
without a batch also writes effective_settings.json.
"""

import inspect
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))
RUN = Path(os.environ["CHAT_RUN_DIR"])
PLACEMENT = {"cpu": ("cpu", "cpu"), "auto": ("auto", "auto"),
             "rerank-mps": ("cpu", "mps"), "embed-mps": ("mps", "cpu")}


def main():
    variant, case_arg = sys.argv[1], sys.argv[2]
    placement, batch = re.fullmatch(r"([a-z-]+?)(?:-b(\d+))?", variant).groups()
    embed_device, rerank_device = PLACEMENT[placement]
    if batch:
        # Read by Settings and by the retriever factory (vectordb._effective_rerank_batch).
        os.environ["RAG_RERANK_BATCH"] = batch
    sys.path.insert(1, str(Path(__file__).resolve().parent))
    from live_api import PUBLIC_SETTINGS, settings_snapshot

    from config.settings import get_settings

    settings = get_settings()
    public = {name: getattr(settings, name, None) for name in PUBLIC_SETTINGS}
    if not batch:
        (RUN / "effective_settings.json").write_text(
            json.dumps({"settings": {k: (str(v) if isinstance(v, Path) else v)
                                     for k, v in public.items()},
                        "all": settings_snapshot(settings)}, indent=2, ensure_ascii=False,
                       default=str) + "\n", encoding="utf-8")
    import vectordb._base_manager as base
    import vectordb.manager as manager

    resolve = base._resolve_device
    devices = {"get_embeddings": embed_device, "get_reranker": rerank_device}
    loads = {}
    walls = {}

    def resolve_for_caller(value=None):
        # Both loaders call _resolve_device() from their own body (vectordb/_base_manager.py).
        caller = inspect.currentframe().f_back.f_code.co_name
        chosen = resolve(devices.get(caller, value))
        loads[caller] = chosen
        return chosen

    class LoadLog(logging.Handler):
        def emit(self, record):
            message = record.getMessage()
            if "loaded in" in message:
                loads.setdefault("messages", []).append(message)
            elif "Reranker error" in message:
                walls.setdefault("reranker_errors", []).append(message[:400])

    logging.getLogger(base.__name__).addHandler(LoadLog())
    logging.getLogger(base.__name__).setLevel(logging.INFO)
    base._resolve_device = resolve_for_caller

    def timed(fn, name):
        def wrapped(*args, **kwargs):
            started = time.monotonic()
            result = fn(*args, **kwargs)
            walls[name] = round(time.monotonic() - started, 2)
            if name == "rerank":
                walls["reranker_ok"] = bool(result[1])
            return result
        return wrapped

    base.HybridRetriever._vector_search = timed(base.HybridRetriever._vector_search, "vector")
    base.HybridRetriever._rerank_scored_with_status = timed(
        base.HybridRetriever._rerank_scored_with_status, "rerank")

    cases = {}
    for line in (WS / "evaluation/curated_cases_aircargo.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            cases[case["case_id"]] = case["query"]
    started = time.monotonic()
    retriever = manager.get_retriever(tenant_id="aircargo")
    out = {"variant": variant, "placement": {"embedder": embed_device, "reranker": rerank_device},
           "rerank_batch_env": batch,
           "retriever_build_sec": round(time.monotonic() - started, 2), "questions": []}
    for index, case_id in enumerate(c for c in case_arg.split(",") if c):
        question = cases[case_id] if case_id in cases else case_id.split(":", 1)[1]
        name = case_id if case_id in cases else f"warmup-{index + 1}"
        walls.clear()
        started = time.monotonic()
        docs, path = retriever.get_relevant_documents_with_path(question)
        row = {"case": name, "retrieval_sec": round(time.monotonic() - started, 2), **walls,
               "rerank_batch_effective": path.get("rerank_batch_effective"),
               "top": [[(d.metadata or {}).get("source"), (d.metadata or {}).get("chunk_index")]
                       for d in docs[:5]]}
        out["questions"].append(row)
        print("Q", variant, name, row["retrieval_sec"], walls, flush=True)
    out["loads"] = loads
    (RUN / f"retrieval-{variant}.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
