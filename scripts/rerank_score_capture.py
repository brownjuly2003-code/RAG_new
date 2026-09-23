"""Re-score an archived candidate pool with the project reranker, keeping raw scores
(slice P1: label-free adaptive-k)."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import re
import time
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from scripts.ab_context_precision import _code_digests, _git_commit, _stored_path, sha256_file

SCHEMA_VERSION = "p1-rerank-scores/v1.0"

CODE_PATHS = (
    "scripts/rerank_score_capture.py",
    "scripts/ab_remote_contextual.py",
    "vectordb/_base_manager.py",
    "config/settings.py",
)


def load_pool_archive(path: Path, expected_sha256: str) -> tuple[list[dict[str, Any]], str]:
    """Load, hash-verify and validate a gzipped pool archive of candidate rows."""
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ValueError("expected sha256 must be 64 lowercase hex chars")
    raw = gzip.decompress(path.read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"pool sha256 mismatch: expected {expected_sha256}, got {digest}")
    rows = json.loads(raw.decode("utf-8"))
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise ValueError("pool archive must be a non-empty list of JSON objects")
    seen: set[str] = set()
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("pool rows require a non-empty string case_id")
        if case_id in seen:
            raise ValueError(f"duplicate case_id in pool archive: {case_id}")
        seen.add(case_id)
        if not isinstance(row.get("query"), str) or not row["query"]:
            raise ValueError(f"case {case_id}: query must be a non-empty string")
        expanded = row.get("expanded_query")
        if expanded is not None and not isinstance(expanded, str):
            raise ValueError(f"case {case_id}: expanded_query must be absent, None or str")
        if "rerank_k" in row:
            k = row["rerank_k"]
            if isinstance(k, bool) or not isinstance(k, int) or k < 1:
                raise ValueError(f"case {case_id}: rerank_k must be absent or an int >= 1")
        prerank = row.get("prerank_cands")
        if (
            not isinstance(prerank, list)
            or not prerank
            or not all(isinstance(t, str) for t in prerank)
        ):
            raise ValueError(f"case {case_id}: prerank_cands must be a non-empty list of strings")
        cands = row.get("cands")
        if not isinstance(cands, list) or not all(isinstance(t, str) for t in cands):
            raise ValueError(f"case {case_id}: cands must be a list of strings")
        if Counter(cands) != Counter(prerank):
            raise ValueError(f"case {case_id}: cands must be a permutation of prerank_cands")
    return rows, digest


def rerank_query(row: dict[str, Any]) -> tuple[str, str]:
    """Return the rerank query text and the row field it was taken from."""
    if row.get("expanded_query"):
        return row["expanded_query"], "expanded_query"
    return row["query"], "query"


def probability_order(probabilities: Sequence[float]) -> list[int]:
    """Return indices ordered by descending probability."""
    return sorted(range(len(probabilities)), key=lambda j: probabilities[j], reverse=True)


def archive_order(prerank: Sequence[str], ranked: Sequence[str]) -> list[int]:
    """Map ranked texts back to the lowest unused index of each prerank text."""
    if len(ranked) != len(prerank):
        raise ValueError("ranked is not a permutation of prerank: length mismatch")
    available: dict[str, list[int]] = {}
    for index, text in enumerate(prerank):
        available.setdefault(text, []).append(index)
    result: list[int] = []
    for text in ranked:
        indices = available.get(text)
        if not indices:
            raise ValueError(f"ranked is not a permutation of prerank: no unused {text!r}")
        result.append(indices.pop(0))
    return result


def score_case(
    reranker: Any,
    row: dict[str, Any],
    *,
    batch_size: int,
    activation: Any,
    sigmoid: Callable[[list[float]], list[float]],
) -> dict[str, Any]:
    """Re-score one case's candidates and compare fresh vs archived ordering."""
    query, field = rerank_query(row)
    texts = list(row["prerank_cands"])
    started = time.perf_counter()
    result = reranker.predict(
        [(query, text) for text in texts],
        batch_size=batch_size,
        activation_fct=activation,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    logits = [float(x) for x in result]
    if len(logits) != len(texts):
        raise ValueError(
            f"case {row['case_id']}: reranker returned {len(logits)} logits "
            f"for {len(texts)} candidates"
        )
    if not all(math.isfinite(x) for x in logits):
        raise ValueError(f"case {row['case_id']}: reranker returned a non-finite logit")
    probabilities = [float(x) for x in sigmoid(logits)]
    if len(probabilities) != len(logits) or not all(
        math.isfinite(p) and 0.0 <= p <= 1.0 for p in probabilities
    ):
        raise ValueError(f"case {row['case_id']}: sigmoid returned invalid probabilities")
    fresh = probability_order(probabilities)
    archived = archive_order(texts, row["cands"])
    top_k = int(row.get("rerank_k") or 5)
    fresh_texts = [texts[j] for j in fresh]
    ranked = list(row["cands"])
    mismatch = next(
        (i for i, (a, b) in enumerate(zip(fresh_texts, ranked, strict=True)) if a != b), None
    )
    return {
        "case_id": row["case_id"],
        "rerank_query_field": field,
        "n_candidates": len(texts),
        "logits": logits,
        "probabilities": probabilities,
        "fresh_order": fresh,
        "archive_order": archived,
        "order_matches_archive": fresh_texts == ranked,
        "top_k": top_k,
        "top_k_matches_archive": fresh_texts[:top_k] == ranked[:top_k],
        "first_mismatch_rank": None if mismatch is None else mismatch + 1,
        "mismatch_probability_gap": (
            None
            if mismatch is None
            else probabilities[fresh[mismatch]] - probabilities[archived[mismatch]]
        ),
        "seconds": round(time.perf_counter() - started, 3),
    }


def build_scores_report(
    *,
    rows: list[dict[str, Any]],
    pool_sha256: str,
    archive_path: Path,
    reranker: Any,
    batch_size: int,
    activation: Any,
    sigmoid: Callable[[list[float]], list[float]],
    environment: dict[str, Any],
    code: dict[str, Any],
    limit: int | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Score archived pool rows and assemble the report dict in schema order."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be an int >= 1, not a bool")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be None or an int >= 1, not a bool")
    selected = rows if limit is None else rows[:limit]
    per_case: list[dict[str, Any]] = []
    for i, row in enumerate(selected, start=1):
        case = score_case(
            reranker, row, batch_size=batch_size, activation=activation, sigmoid=sigmoid
        )
        log(
            f"[scores] {i}/{len(selected)} {case['case_id']} {case['seconds']:.1f}s "
            f"order_match={case['order_matches_archive']}"
        )
        per_case.append(case)
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "measured",
        "complete": len(selected) == len(rows),
        "cases_total": len(rows),
        "cases_scored": len(selected),
        "parity": {
            "order_matches": sum(1 for c in per_case if c["order_matches_archive"]),
            "top_k_matches": sum(1 for c in per_case if c["top_k_matches_archive"]),
            "mismatched_case_ids": [
                c["case_id"] for c in per_case if not c["order_matches_archive"]
            ],
        },
        "provenance": {
            "archive_path": _stored_path(archive_path),
            "archive_sha256": sha256_file(archive_path),
            "pool_sha256": pool_sha256,
            "code": code,
            "reranker": environment,
            "config": {
                "batch_size": batch_size,
                "limit": limit,
                "scores": (
                    "logits via identity activation; probabilities = float32 sigmoid of "
                    "logits on the reranker device"
                ),
                "order_rule": "stable descending sort by probability (stage_rerank)",
                "rerank_query": "expanded_query or query (stage_rerank, arms other than F)",
            },
        },
        "timing": {"total_seconds": round(sum(c["seconds"] for c in per_case), 3)},
        "per_case": per_case,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    """Serialize the report, then write it to a brand-new file."""
    text = json.dumps(report, ensure_ascii=False, indent=1, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _environment(reranker: Any, model_name: str) -> dict[str, Any]:
    """Capture reranker configuration plus host and library versions."""
    import sentence_transformers
    import torch
    import transformers

    default_activation = getattr(reranker, "default_activation_function", None)
    return {
        "model": model_name,
        "model_commit": getattr(
            getattr(getattr(reranker, "model", None), "config", None), "_commit_hash", None
        ),
        "num_labels": getattr(getattr(reranker, "config", None), "num_labels", None),
        "default_activation": (
            None if default_activation is None else type(default_activation).__name__
        ),
        "max_length": getattr(reranker, "max_length", None),
        "device": str(getattr(reranker, "_target_device", None)),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "sentence_transformers": sentence_transformers.__version__,
        "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
        "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: rescore an archived pool and write an exclusive report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("RAG_RERANK_BATCH", "32")),
    )
    args = parser.parse_args(argv)
    if args.out.exists():
        print(f"refusing to overwrite {args.out}", flush=True)
        return 2
    rows, digest = load_pool_archive(args.archive, args.expected_sha256)
    from config.settings import get_settings
    from vectordb._base_manager import get_reranker

    reranker = get_reranker()
    model_name = get_settings().reranker_model
    if reranker is None:
        print(f"reranker unavailable for model {model_name!r}", flush=True)
        return 2
    environment = _environment(reranker, model_name)
    if environment["num_labels"] != 1 or environment["default_activation"] != "Sigmoid":
        print(
            f"refusing: num_labels={environment['num_labels']!r} "
            f"default_activation={environment['default_activation']!r} "
            "(probabilities would not match production scores)",
            flush=True,
        )
        return 2
    import torch

    activation = torch.nn.Identity()

    def sigmoid(values: list[float]) -> list[float]:
        logits = torch.tensor(values, dtype=torch.float32, device=reranker._target_device)
        return torch.sigmoid(logits).cpu().tolist()

    code = dict(_git_commit(), files=_code_digests(CODE_PATHS))
    report = build_scores_report(
        rows=rows,
        pool_sha256=digest,
        archive_path=args.archive,
        reranker=reranker,
        batch_size=args.batch_size,
        activation=activation,
        sigmoid=sigmoid,
        environment=environment,
        code=code,
        limit=args.limit,
        log=lambda line: print(line, flush=True),
    )
    write_report(args.out, report)
    print(
        f"[scores] done cases={report['cases_scored']}/{report['cases_total']} "
        f"order_matches={report['parity']['order_matches']} "
        f"top_k_matches={report['parity']['top_k_matches']} "
        f"seconds={report['timing']['total_seconds']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
