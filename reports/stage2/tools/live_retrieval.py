"""Retrieval alone, as the web chat's path runs it, for any tenant (PLAN.md stage 2, item 2).

Run by live_supervisor.py in mode retrieval: no model held by Ollama, no API, no database;
nothing is generated. The tenant is CHAT_TENANT, the questions CHAT_CASES_FILE and the index
VECTORDB_CHROMA_DIR, as live_supervisor.py sets them for the answer runs.

Usage: live_retrieval.py VARIANT CASES
  VARIANT cpu - the only placement: the code default (RAG_DEVICE=cpu);
  CASES   comma-separated case ids of CHAT_CASES_FILE.

The retriever is the API's: vectordb.manager.get_retriever(tenant_id=...), the function the
chat's session takes it from, and each question goes through get_relevant_documents_with_path
as the chat's get_relevant_documents does. The chat then hands the first five documents to
_fit_stream_prompt with the window of the provider it streams from; this runner calls the
same function on the same documents with the provider build_provider_runtime gives (the
chat's session holds no model of its own), so it writes the prompt the chat would send.

Per question it writes CHAT_RUN_DIR/retrieval/NNN-<case>.json. That file holds the question
and the texts of the documents, so it stays on the host (evaluation/external_bases.json,
"redistribution"):
  walls     - retrieval, vector search and rerank, in seconds; reranker_ok;
  path      - the path dict the retriever returns (candidates, rerank status, timings);
  lanes     - the vector and the BM25 candidates in rank order, (source, chunk_index);
  pool      - every fused candidate in its fused order with its cross-encoder score;
  ranked    - the five the rerank kept, with their scores;
  expanded  - the documents the retriever returns (seed source and chunk_index, text);
  sent      - the documents of the fitted prompt, each with whether the fitting cut it;
  prompt    - the prompt as live_api.py saves one (the flattened user message), its SHA-256
              and size: the SHA-256 is comparable with the answer prompt of the same question,
              the text is what scripts/context_judge.py reads.
The lanes and the pool come from the wrappers of live_api.py (OBSERVED there), which hand
the product's calls through unchanged.

The question is stripped, as the chat's handler strips it. The retriever's own lines
(vectordb.manager: the BM25 restore, or its failure) go to stderr, which the supervisor writes
into the run's progress.log, as the API's log holds them for an answers run:
retrieval_summary.py reads stage 1's restore test from there. A question whose path breaks
(stage2_common.path_breaks: an empty lane, a rerank status other than ok, fewer than five
documents) ends the series with exit 6: the work stops and Julia is told first.

Stop rule (Julia, 2026-10-15: 3x a question's named forecast): CAPS - 3x the forecasts of
120 s for the first question, which loads the embedder and the reranker (120.35 s, the cpu
placement of reports/chat-live/33d4b42; 122.0 s on the smoke of 2026-10-19), and 40 s for the
others (24.0-44.1 s on the four bases in that smoke, 27.6 s on 33d4b42). A question past its
cap ends the series with exit 5; the supervisor's own timeout bounds the whole run.
"""

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))
RUN = Path(os.environ["CHAT_RUN_DIR"])
TENANT = os.environ.get("CHAT_TENANT", "aircargo")
CASES = Path(os.environ.get("CHAT_CASES_FILE", WS / "evaluation/curated_cases_aircargo.jsonl"))
TOP = 5
CAPS = (360.0, 120.0)


def window_owner():
    """The provider the chat streams from: the runtime's strong, then fast, model."""
    from types import SimpleNamespace

    from config.settings import get_settings
    from llm.providers.runtime import build_provider_runtime

    settings = get_settings()
    runtime = build_provider_runtime(settings)
    for candidate in (runtime.strong, runtime.fast):
        if callable(getattr(candidate, "generate_stream", None)):
            return candidate, "provider"
    # The chat's raw Ollama fallback sends num_ctx from settings.
    return SimpleNamespace(context_window=int(settings.ollama_context_window)), "settings"


def described(docs):
    return [
        {
            "source": (d.metadata or {}).get("source"),
            "chunk_index": (d.metadata or {}).get("chunk_index"),
            "text": d.page_content,
        }
        for d in docs
    ]


def main():
    variant, case_arg = sys.argv[1], sys.argv[2]
    if variant != "cpu":
        raise SystemExit("stage 2 measures the code default placement only: cpu")
    first_cap, rest_cap = CAPS
    sys.path.insert(1, str(Path(__file__).resolve().parent))
    from live_api import PUBLIC_SETTINGS, observe_lanes, observe_pool, settings_snapshot
    from stage2_common import path_breaks

    from api.routers.conversation import _fit_stream_prompt
    from config.settings import get_settings
    from llm.providers.base import estimate_window_tokens, flatten_messages

    settings = get_settings()
    public = {name: getattr(settings, name, None) for name in PUBLIC_SETTINGS}
    (RUN / "effective_settings.json").write_text(
        json.dumps(
            {
                "settings": {k: (str(v) if isinstance(v, Path) else v) for k, v in public.items()},
                "all": settings_snapshot(settings),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    import vectordb._base_manager as base
    import vectordb.manager as manager

    rows = []
    base.HybridRetriever._rrf_merge = observe_lanes(base.HybridRetriever._rrf_merge, rows.append)
    base.HybridRetriever._rerank_scored_with_status = observe_pool(
        base.HybridRetriever._rerank_scored_with_status, rows.append
    )
    walls = {}

    def timed(fn, name):
        def wrapped(*args, **kwargs):
            started = time.monotonic()
            result = fn(*args, **kwargs)
            walls[name] = round(time.monotonic() - started, 3)
            return result

        return wrapped

    base.HybridRetriever._vector_search = timed(base.HybridRetriever._vector_search, "vector")
    base.HybridRetriever._rerank_scored_with_status = timed(
        base.HybridRetriever._rerank_scored_with_status, "rerank"
    )

    cases = {}
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            cases[case["case_id"]] = case["query"]
    owner, owner_kind = window_owner()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    manager.logger.addHandler(handler)
    manager.logger.setLevel(logging.INFO)
    manager.logger.propagate = False
    started = time.monotonic()
    retriever = manager.get_retriever(tenant_id=TENANT)
    out = {
        "variant": variant,
        "tenant": TENANT,
        "cases_file": str(CASES),
        "retriever_build_sec": round(time.monotonic() - started, 3),
        "window": {"owner": owner_kind, "context_window": getattr(owner, "context_window", None)},
        "caps": [first_cap, rest_cap],
        "questions": [],
    }
    (RUN / "retrieval").mkdir(exist_ok=True)
    exit_code = 0
    for index, case_id in enumerate((c for c in case_arg.split(",") if c), start=1):
        question = cases[case_id].strip()
        rows.clear()
        walls.clear()
        began = time.monotonic()
        docs, path = retriever.get_relevant_documents_with_path(question)
        walls["retrieval"] = round(time.monotonic() - began, 3)
        plain = [{"page_content": d.page_content, "metadata": d.metadata or {}} for d in docs[:TOP]]
        prompt, fitted = _fit_stream_prompt(owner, question, plain, [])
        flat = flatten_messages([{"role": "user", "content": prompt}])
        lanes = next(
            (r for r in rows if r["stage"] == "hybrid.lanes" and r["event"] == "end"), None
        )
        pool = next(
            (r for r in rows if r["stage"] == "hybrid.rerank_pool" and r["event"] == "end"), None
        )
        record = {
            "case_id": case_id,
            "index": index,
            "question": question,
            "walls": dict(walls),
            "path": path,
            "lanes": None if lanes is None else {"vector": lanes["vector"], "bm25": lanes["bm25"]},
            "pool": None if pool is None else pool["pool"],
            "reranker_ok": None if pool is None else pool["reranker_ok"],
            "ranked": [
                [*ident, score]
                for ident, score in zip(
                    [
                        [(d.metadata or {}).get("source"), (d.metadata or {}).get("chunk_index")]
                        for d in docs
                    ],
                    path.get("rerank_scores") or [None] * len(docs),
                    strict=True,
                )
            ],
            "expanded": described(docs),
            "sent": [
                {
                    "source": d["metadata"].get("source"),
                    "chunk_index": d["metadata"].get("chunk_index"),
                    "text": d["page_content"],
                    "cut": d["page_content"] != plain[i]["page_content"],
                }
                for i, d in enumerate(fitted)
            ],
            "prompt": {
                "sha256": hashlib.sha256(flat.encode("utf-8")).hexdigest(),
                "chars": len(flat),
                "est_tokens": estimate_window_tokens(flat),
                "text": flat,
            },
        }
        (RUN / "retrieval" / f"{index:03d}-{case_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        cap = first_cap if index == 1 else rest_cap
        out["questions"].append(
            {
                "case": case_id,
                **walls,
                "reranker_ok": record["reranker_ok"],
                "pool": len(record["pool"] or []),
                "sent": len(fitted),
                "cap": cap,
            }
        )
        print(
            "Q",
            index,
            case_id,
            walls,
            "pool",
            len(record["pool"] or []),
            "sent",
            len(fitted),
            flush=True,
        )
        breaks = path_breaks(path.get("candidates"), path.get("rerank_status"), len(docs))
        if breaks:
            print("STOP path break: case", case_id, breaks, flush=True)
            exit_code = 6
            break
        if walls["retrieval"] > cap:
            print("STOP rule: case", case_id, "ran past its cap of", cap, "s", flush=True)
            exit_code = 5
            break
    (RUN / f"retrieval-{variant}.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
