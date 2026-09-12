"""Bounded, resumable GR-2 extraction from the archived GR-1 chunk payload."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filelock import FileLock  # noqa: E402

from ingestion.entity_extraction import extract_entities  # noqa: E402
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
    args = parser.parse_args(argv)
    if args.model.endswith("latest"):
        parser.error("Use a pinned model ID instead of latest")
    if args.max_calls < 0 or args.min_interval < 1.0:
        parser.error("max-calls must be nonnegative and min-interval at least 1 second")
    raw = args.chunks.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.chunks_sha256:
        raise ValueError("Archived chunk payload SHA-256 mismatch")
    payload = json.loads(raw)
    chunks = [SimpleNamespace(page_content=row["page_content"], metadata=row["metadata"])
              for row in payload["chunks"]]
    llm = None

    def invoke(prompt: str) -> str:
        nonlocal llm
        if llm is None:
            llm = FreeChatLLM("mistral", args.model, temperature=0.0,
                              min_interval_s=args.min_interval, max_retries=1)
        result = llm.invoke(prompt)
        print(f"provider_calls={llm.calls}", flush=True)
        return result

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(str(args.cache_dir / "extract.lock"), timeout=0):
        extracted = extract_entities(
            chunks, tenant_id=payload["tenant_id"], corpus_sha256=args.corpus_sha256,
            model=args.model, cache_dir=args.cache_dir, invoke=invoke, max_calls=args.max_calls,
        )
    complete = len(extracted) == len(chunks)
    print(json.dumps({"status": "complete" if complete else "partial", "chunks": len(chunks),
                      "cached": len(extracted), "model_digest": None}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
