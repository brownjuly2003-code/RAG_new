"""Cache production SGR query classifications for GR-2 evaluation datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filelock import FileLock  # noqa: E402

from evaluation.query_classification import (  # noqa: E402
    PinnedOllamaClassifier,
    classify_cases,
)
from llm.providers.pinned_ollama import PinnedOllamaChat, resolve_ollama_digest  # noqa: E402


def _load_cases(raw: bytes) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Cases file row is not a JSON object")
        cases.append(row)
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--cases-sha256", required=True)
    parser.add_argument("--model", required=True, help="Pinned Ollama name:tag; latest is refused")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument(
        "--max-calls",
        type=int,
        default=0,
        help="Default 0 validates input/digest/cache without generation requests",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args(argv)
    if args.model.endswith("latest"):
        parser.error("Use a pinned model ID instead of latest")
    name, _, tag = args.model.partition(":")
    if not name or not tag or tag == "latest":
        parser.error("Ollama --model must be an explicit name:tag, not latest")
    if args.max_calls < 0:
        parser.error("max-calls must be nonnegative")
    raw = args.cases.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != args.cases_sha256:
        raise ValueError(f"Cases file SHA-256 mismatch: {digest} != {args.cases_sha256}")
    cases = _load_cases(raw)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(str(args.cache_dir / "classify.lock"), timeout=0):
        model_digest = resolve_ollama_digest(args.base_url, args.model)
        pinned = PinnedOllamaChat(args.base_url, args.model, model_digest)
        classifier = PinnedOllamaClassifier(
            pinned, model_name=args.model, model_digest=model_digest
        )
        cached = classify_cases(
            cases,
            dataset_sha256=args.cases_sha256,
            classifier=classifier,
            cache_dir=args.cache_dir,
            max_calls=args.max_calls,
        )
    counts = Counter(str(row["question_class"]) for row in cached.values())
    print(
        json.dumps(
            {
                "status": "complete" if len(cached) == len(cases) else "partial",
                "cases": len(cases),
                "cached": len(cached),
                "model_digest": model_digest,
                "question_class": dict(counts),
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
