"""The real API for a live chat measurement, with observation-only timing wrappers.

Run by live_supervisor.py with the workspace first on PYTHONPATH. Wrappers record
start/end (and first chunk for streams) to CHAT_RUN_DIR/stages.jsonl and save every
model prompt to CHAT_RUN_DIR/prompts/ for an exact token count afterwards; arguments,
results and exceptions pass through unchanged.
"""

import dataclasses
import functools
import itertools
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))
RUN = Path(os.environ["CHAT_RUN_DIR"])
LOCK = threading.Lock()
PROMPT_SEQ = itertools.count(1)


def emit(row):
    row["monotonic"] = time.monotonic()
    row["thread"] = threading.get_ident()
    with LOCK, (RUN / "stages.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def observe(fn, stage, extra=None):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        started = time.monotonic()
        emit({"stage": stage, "event": "start"})
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            emit({"stage": stage, "event": "end", "wall_sec": time.monotonic() - started,
                  "error": type(exc).__name__})
            raise
        emit({"stage": stage, "event": "end", "wall_sec": time.monotonic() - started,
              **(extra(result) if extra else {})})
        return result

    return wrapped


def save_prompt(stage, messages, kwargs):
    from llm.providers.base import estimate_window_tokens, flatten_messages

    prompt = flatten_messages(messages)
    seq = next(PROMPT_SEQ)
    name = f"{seq:03d}-{stage}.txt"
    (RUN / "prompts" / name).write_text(prompt, encoding="utf-8")
    return {"prompt_file": name, "prompt_chars": len(prompt),
            "prompt_est_tokens": estimate_window_tokens(prompt),
            "max_tokens": kwargs.get("max_tokens")}


def observe_generate(fn):
    @functools.wraps(fn)
    def wrapped(self, messages, tools=None, **kwargs):
        info = save_prompt("generate", messages, kwargs)
        started = time.monotonic()
        emit({"stage": "ollama.generate", "event": "start", **info})
        try:
            response = fn(self, messages, tools=tools, **kwargs)
        except BaseException as exc:
            emit({"stage": "ollama.generate", "event": "end", **info,
                  "wall_sec": time.monotonic() - started, "error": type(exc).__name__,
                  "detail": str(exc)[:300]})
            raise
        emit({"stage": "ollama.generate", "event": "end", **info,
              "wall_sec": time.monotonic() - started,
              "output_chars": len(getattr(response, "text", "") or "")})
        return response

    return wrapped


def observe_stream(fn):
    @functools.wraps(fn)
    async def wrapped(self, messages, **kwargs):
        info = save_prompt("stream", messages, kwargs)
        started = time.monotonic()
        first = None
        chunks = 0
        chars = 0
        error = None
        emit({"stage": "ollama.generate_stream", "event": "start", **info})
        try:
            async for chunk in fn(self, messages, **kwargs):
                if first is None:
                    first = time.monotonic() - started
                chunks += 1
                chars += len(chunk)
                yield chunk
        except BaseException as exc:
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
            raise
        finally:
            emit({"stage": "ollama.generate_stream", "event": "end", **info,
                  "wall_sec": time.monotonic() - started, "first_chunk_sec": first,
                  "chunks": chunks, "output_chars": chars, "error": error})

    return wrapped


SECRET_HINT = re.compile(r"key|token|secret|passw|dsn|url|credential|auth", re.I)


def settings_snapshot(settings):
    """Every Settings field; secret-like names and values only as set/empty."""
    out = {}
    for item in dataclasses.fields(settings):
        value = getattr(settings, item.name, None)
        if SECRET_HINT.search(item.name):
            out[item.name] = "<set>" if value else "<empty>"
        elif value is None or isinstance(value, (str, int, float, bool)):
            out[item.name] = "<set>" if isinstance(value, str) and SECRET_HINT.search(value) else value
        elif isinstance(value, Path):
            out[item.name] = str(value)
        else:
            text = repr(value)
            out[item.name] = "<complex>" if SECRET_HINT.search(text) else text[:300]
    return out


PUBLIC_SETTINGS = (
    "llm_provider_profile ollama_model_name ollama_fast_model_name model_routing_enabled "
    "ollama_context_window embedding_model embedding_backend reranker_model rag_device "
    "vector_backend hybrid_search retrieval_strategy retrieval_top_k rerank_top_k hyde "
    "graph_retrieval parent_expansion self_rag_max_iterations fact_verification_enabled "
    "streaming_enabled streaming_rag_parity streaming_quality_eval streaming_timeout_sec "
    "request_timeout_sec ollama_request_timeout_sec quality_threshold "
    "suggested_questions_enabled llm_max_calls_per_request online_evaluators_enabled "
    "max_concurrent_pipelines support_sink_backend tracing_db_path vectordb_chroma_dir"
).split()


def main():
    (RUN / "prompts").mkdir(exist_ok=True)
    from config.settings import get_settings

    settings = get_settings()
    public = {name: getattr(settings, name, None) for name in PUBLIC_SETTINGS}
    public = {k: (str(v) if isinstance(v, Path) else v) for k, v in public.items()}
    import agent.context_window as context_window

    code = {
        "workspace": str(WS),
        "code_sha": (WS / "CODE_SHA").read_text(encoding="utf-8").strip(),
        "context_window_file": context_window.__file__,
        "has_fit_all_context_docs": hasattr(context_window, "fit_all_context_docs"),
    }
    if not code["context_window_file"].startswith(str(WS)) or not code["has_fit_all_context_docs"]:
        raise SystemExit("API would not serve the workspace code: " + json.dumps(code))
    (RUN / "effective_settings.json").write_text(
        json.dumps({"settings": public, "code": code, "all": settings_snapshot(settings)},
                   indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    if os.environ.get("CHAT_DUMP_ONLY") == "1":
        return

    import vectordb._base_manager as base
    import vectordb.manager as manager
    from llm.providers.ollama import OllamaProvider

    for module, names in ((manager, ("get_retriever", "get_embeddings")),
                          (base, ("get_embeddings", "get_reranker"))):
        for name in names:
            setattr(module, name, observe(getattr(module, name), f"{module.__name__}.{name}"))
    for name in ("get_relevant_documents_with_path", "_vector_search",
                 "_rerank_scored_with_status", "_expand_parents"):
        # The rerank returns (documents, ok): ok False means the unreranked order was used.
        extra = ((lambda result: {"reranker_ok": bool(result[1]), "docs": len(result[0])})
                 if name == "_rerank_scored_with_status" else None)
        setattr(base.HybridRetriever, name,
                observe(getattr(base.HybridRetriever, name), "hybrid." + name, extra))
    OllamaProvider.generate = observe_generate(OllamaProvider.generate)
    OllamaProvider.generate_stream = observe_stream(OllamaProvider.generate_stream)

    import uvicorn

    uvicorn.run("api.app:app", host="127.0.0.1", port=8002, workers=1)


if __name__ == "__main__":
    main()
