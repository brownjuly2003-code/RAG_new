"""File/CLI driver for the D.3 offline rerank experiment.

The driver verifies and reranks candidates already saved by D.1. It performs
no retrieval or embedding work.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from collections.abc import Callable
from pathlib import Path

from scripts.pgvector_rerank import run_offline_rerank, validate_d1_rankings

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "scripts/pgvector_rerank.py",
    "scripts/pgvector_rerank_run.py",
    "scripts/pgvector_spike.py",
    "evaluation/ragas_eval.py",
    "vectordb/_base_manager.py",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decode(path: Path, raw: bytes) -> str:
    if not raw.strip():
        raise ValueError(f"empty file: {path}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"file is not valid UTF-8: {path}") from exc


def _load_json(path: Path, raw: bytes) -> object:
    try:
        return json.loads(_decode(path, raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _load_rows(path: Path, raw: bytes) -> list[object]:
    rows: list[object] = []
    for line_number, line in enumerate(_decode(path, raw).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON on line {line_number} of {path}: {exc}"
            ) from exc
    return rows


def _normalize_case(path: Path, row: object) -> dict:
    if not isinstance(row, dict):
        raise TypeError(f"case row in {path} must be a JSON object")
    case_id = row.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError(f"case in {path} needs a non-empty string case_id")
    query = row.get("query")
    if not isinstance(query, str) or not query:
        raise ValueError(f"case {case_id!r} needs a non-empty string query")
    expected = row.get("expected")
    if not isinstance(expected, dict):
        raise TypeError(f"case {case_id!r} needs an 'expected' object")
    keywords = expected.get("answer_contains")
    if not isinstance(keywords, list) or any(
        not isinstance(keyword, str) for keyword in keywords
    ):
        raise TypeError(
            f"case {case_id!r} needs list[str] for expected.answer_contains"
        )
    return {"case_id": case_id, "query": query, "kws": keywords}


def _validate_config(config: object, *, chunk_count: int, case_count: int) -> int:
    if not isinstance(config, dict):
        raise TypeError("D.1 report config must be a dict")
    expected = {
        "chunks": chunk_count,
        "cases": case_count,
        "repetitions": 3,
        "branch_limit": 20,
    }
    for key, wanted in expected.items():
        actual = config.get(key)
        if isinstance(actual, bool) or not isinstance(actual, int):
            raise TypeError(f"D.1 config {key!r} must be an int")
        if actual != wanted:
            raise ValueError(f"D.1 config {key!r} must be {wanted}, got {actual!r}")
    if config.get("reranker") is not False:
        raise ValueError("D.1 report must contain pre-reranker rankings")
    top_k = config.get("top_k")
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("D.1 config 'top_k' must be an int")
    if top_k <= 0:
        raise ValueError("D.1 config 'top_k' must be positive")
    return top_k


def _source_sha256() -> dict[str, str]:
    return {
        relative: _sha256((REPO_ROOT / relative).read_bytes())
        for relative in SOURCE_PATHS
    }


def _versions() -> dict[str, str]:
    return {
        package: importlib.metadata.version(package)
        for package in ("sentence-transformers", "torch")
    }


def run_from_files(
    *,
    chunks_path: Path,
    d1_report_path: Path,
    case_paths: list[Path],
    output_path: Path,
    model_name: str,
    code_base: str,
    reranker_factory: Callable[[str], object] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, object]:
    """Rerank saved D.1 candidates and write one exclusive JSON report."""
    chunks_path = Path(chunks_path)
    d1_report_path = Path(d1_report_path)
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}")
    if not isinstance(model_name, str) or not model_name:
        raise ValueError("model_name must be a non-empty string")
    if not isinstance(code_base, str) or not code_base:
        raise ValueError("code_base must be a non-empty string")
    if not isinstance(case_paths, list):
        raise TypeError(f"case_paths must be a list, got {type(case_paths).__name__}")
    if not case_paths:
        raise ValueError("case_paths must contain at least one cases file")
    case_paths = [Path(path) for path in case_paths]

    names = [chunks_path.name, d1_report_path.name, *(path.name for path in case_paths)]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate input basenames: {names}")
    stems = [path.stem for path in case_paths]
    if len(stems) != len(set(stems)):
        raise ValueError(f"duplicate bucket stems: {stems}")

    chunks_raw = chunks_path.read_bytes()
    chunks_digest = _sha256(chunks_raw)
    chunks_document = _load_json(chunks_path, chunks_raw)
    if not isinstance(chunks_document, dict):
        raise TypeError(f"{chunks_path.name} must contain a JSON object")
    raw_chunks = chunks_document.get("chunks")
    if not isinstance(raw_chunks, list):
        raise TypeError(f"{chunks_path.name} must contain a 'chunks' list")
    if not raw_chunks:
        raise ValueError(f"{chunks_path.name} has an empty 'chunks' list")
    texts: list[str] = []
    for position, chunk in enumerate(raw_chunks):
        if not isinstance(chunk, dict):
            raise TypeError(f"chunk #{position} in {chunks_path.name} must be an object")
        text = chunk.get("page_content")
        if not isinstance(text, str) or not text:
            raise ValueError(
                f"chunk #{position} in {chunks_path.name} needs non-empty page_content"
            )
        texts.append(text)

    d1_raw = d1_report_path.read_bytes()
    d1_digest = _sha256(d1_raw)
    d1_report = _load_json(d1_report_path, d1_raw)
    if not isinstance(d1_report, dict):
        raise TypeError(f"{d1_report_path.name} must contain a JSON object")
    d1_inputs = d1_report.get("input_sha256")
    if not isinstance(d1_inputs, dict):
        raise TypeError(f"{d1_report_path.name} must contain an input_sha256 dict")

    cases: list[dict] = []
    buckets: dict[str, tuple[int, int]] = {}
    case_digests: dict[str, str] = {}
    seen_case_ids: set[str] = set()
    for path in case_paths:
        raw = path.read_bytes()
        case_digests[path.name] = _sha256(raw)
        start = len(cases)
        for row in _load_rows(path, raw):
            case = _normalize_case(path, row)
            case_id = case["case_id"]
            if case_id in seen_case_ids:
                raise ValueError(f"duplicate case_id: {case_id}")
            seen_case_ids.add(case_id)
            cases.append(case)
        buckets[path.stem] = (start, len(cases))

    current_inputs = {chunks_path.name: chunks_digest, **case_digests}
    for name, actual in current_inputs.items():
        recorded = d1_inputs.get(name)
        if recorded is None:
            raise ValueError(
                f"SHA-256 for {name} is missing from {d1_report_path.name}"
            )
        if recorded != actual:
            raise ValueError(
                f"SHA-256 mismatch for {name}: recorded {recorded!r}, actual {actual}"
            )

    top_k = _validate_config(
        d1_report.get("config"),
        chunk_count=len(texts),
        case_count=len(cases),
    )
    saved_rankings = validate_d1_rankings(
        d1_report,
        chunk_count=len(texts),
        case_count=len(cases),
        repetitions=3,
        candidate_limit=40,
    )
    if any(
        top_k > len(ranking)
        for arm_rankings in saved_rankings.values()
        for ranking in arm_rankings
    ):
        raise ValueError("D.1 top_k must not exceed any saved candidate ranking")
    source_digests = _source_sha256()

    factory = reranker_factory
    if factory is None:
        from vectordb._base_manager import get_reranker

        factory = get_reranker
    reranker = factory(model_name)
    if reranker is None:
        raise RuntimeError(f"reranker factory returned None for {model_name!r}")
    versions = _versions()

    arms = run_offline_rerank(
        reranker,
        d1_report,
        cases,
        texts,
        buckets,
        clock=clock,
        top_k=top_k,
    )
    report: dict[str, object] = {
        "code_base": code_base,
        "input_sha256": {
            chunks_path.name: chunks_digest,
            d1_report_path.name: d1_digest,
            **case_digests,
        },
        "source_sha256": source_digests,
        "versions": versions,
        "python": platform.python_version(),
        "config": {
            "chunks": len(texts),
            "cases": len(cases),
            "top_k": top_k,
            "reranker_model": model_name,
            "reranker": True,
            "source_report": d1_report_path.name,
            "source_report_sha256": d1_digest,
        },
        "buckets": {
            name: {"start": start, "end": end}
            for name, (start, end) in buckets.items()
        },
        "arms": arms,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    return report


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the experiment, and report the output path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--d1-report", type=Path, required=True)
    parser.add_argument("--cases", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--code-base", required=True)
    args = parser.parse_args(argv)
    run_from_files(
        chunks_path=args.chunks,
        d1_report_path=args.d1_report,
        case_paths=args.cases,
        output_path=args.output,
        model_name=args.model,
        code_base=args.code_base,
    )
    print(f"DONE {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
