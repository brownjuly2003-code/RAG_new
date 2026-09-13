"""Bounded, resumable GR-2 extraction from the archived GR-1 chunk payload."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filelock import FileLock  # noqa: E402

from ingestion.entity_extraction import (  # noqa: E402
    EXTRACT_SCHEMA,
    extract_entities,
    load_extraction_cache,
)
from llm.providers.pinned_ollama import PinnedOllamaChat, resolve_ollama_digest  # noqa: E402
from scripts.aircargo_ragas_free import FreeChatLLM  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--chunks-sha256", required=True)
    parser.add_argument("--corpus-sha256", required=True)
    parser.add_argument("--model", required=True, help="Pinned provider model ID; latest aliases are refused")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=0, help="Default 0 validates input/cache without API calls")
    parser.add_argument("--min-interval", type=float, default=4.0)
    parser.add_argument("--provider", choices=("mistral", "ollama"), default="mistral")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--on-invalid", choices=("stop", "record"), default="stop")
    args = parser.parse_args(argv)
    if args.model.endswith("latest"):
        parser.error("Use a pinned model ID instead of latest")
    name, _, tag = args.model.partition(":")
    if args.provider == "ollama" and (not name or not tag or tag == "latest"):
        parser.error("Ollama --model must be an explicit name:tag, not latest")
    if args.max_calls < 0 or args.min_interval < 1.0:
        parser.error("max-calls must be nonnegative and min-interval at least 1 second")
    raw = args.chunks.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.chunks_sha256:
        raise ValueError("Archived chunk payload SHA-256 mismatch")
    payload = json.loads(raw)
    chunks = [SimpleNamespace(page_content=row["page_content"], metadata=row["metadata"])
              for row in payload["chunks"]]
    llm = None
    pinned: PinnedOllamaChat | None = None
    model_digest: str | None = None
    generation: dict[str, Any] | None = None
    calls = 0

    def invoke(prompt: str) -> str:
        nonlocal llm, calls
        started = time.perf_counter()
        if args.provider == "ollama":
            assert pinned is not None
            result = pinned.chat(
                [{"role": "user", "content": prompt}], format_schema=EXTRACT_SCHEMA,
            )
            calls += 1
            print(f"provider_calls={calls} elapsed_s={time.perf_counter() - started:.1f}", flush=True)
            return result
        if llm is None:
            llm = FreeChatLLM("mistral", args.model, temperature=0.0,
                              min_interval_s=args.min_interval, max_retries=1)
        result = llm.invoke(prompt)
        print(f"provider_calls={llm.calls} elapsed_s={time.perf_counter() - started:.1f}", flush=True)
        return result

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(str(args.cache_dir / "extract.lock"), timeout=0):
        if args.provider == "ollama":
            model_digest = resolve_ollama_digest(args.base_url, args.model)
            pinned = PinnedOllamaChat(args.base_url, args.model, model_digest)
            generation = pinned.generation_record(EXTRACT_SCHEMA)
        extract_entities(
            chunks, tenant_id=payload["tenant_id"], corpus_sha256=args.corpus_sha256,
            model=args.model, cache_dir=args.cache_dir, invoke=invoke, max_calls=args.max_calls,
            provider=args.provider, model_digest=model_digest, generation=generation,
            on_invalid="record" if args.on_invalid == "record" else "raise",
        )
        cache = load_extraction_cache(
            args.cache_dir, chunks, tenant_id=payload["tenant_id"], require_complete=False,
        )
    complete = len(cache.entities) + len(cache.rejected) == cache.total
    print(json.dumps({
        "status": "complete" if complete else "partial",
        "chunks": cache.total,
        "cached": len(cache.entities),
        "rejected": len(cache.rejected),
        "provider": cache.manifest.get("provider", args.provider),
        "model_digest": cache.manifest.get("model_digest"),
    }), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
