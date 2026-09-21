"""Pure helpers for the D.3 offline pgvector rerank stage.

``rerank_indices`` reorders candidate chunk indices produced by the D.1
retrieval benchmark using a production cross-encoder reranker, and
``validate_d1_rankings`` validates the saved D.1 report schema and
extracts a deep-independent copy of its per-arm rankings.

The module deliberately contains only this checkable core: no database,
network, model loading, CLI, re-retrieval or embeddings. The single
heavyweight interaction is the exactly-one ``reranker.predict`` call made
by ``rerank_indices``; model errors intentionally propagate untouched.
"""

from __future__ import annotations

import math

__all__ = ["rerank_indices", "validate_d1_rankings"]


def _check_query(query: object) -> None:
    if not isinstance(query, str):
        raise TypeError(f"query must be a str, got {type(query).__name__}")
    if not query:
        raise ValueError("query must be a non-empty str")


def _check_texts(texts: object) -> None:
    if not isinstance(texts, list):
        raise TypeError(f"texts must be a list, got {type(texts).__name__}")
    if not texts:
        raise ValueError("texts must be a non-empty list")
    for position, text in enumerate(texts):
        if not isinstance(text, str):
            raise TypeError(f"texts[{position}] must be a str, got {type(text).__name__}")
        if not text:
            raise ValueError(f"texts[{position}] must be a non-empty str")


def _check_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be a positive int, got {value!r}")


def _check_index_list(
    indices: object,
    *,
    upper: int,
    what: str,
    limit: int | None = None,
) -> None:
    if not isinstance(indices, list):
        raise TypeError(f"{what} must be a list, got {type(indices).__name__}")
    if not indices:
        raise ValueError(f"{what} must be a non-empty list")
    if limit is not None and len(indices) > limit:
        raise ValueError(f"{what} must contain at most {limit} indices, got {len(indices)}")
    seen: set[int] = set()
    for position, index in enumerate(indices):
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"{what}[{position}] must be an int, got {type(index).__name__}")
        if not 0 <= index < upper:
            raise ValueError(f"{what}[{position}] must satisfy 0 <= index < {upper}, got {index}")
        if index in seen:
            raise ValueError(f"{what} contains duplicate index {index}")
        seen.add(index)


def _finite_float(value: object, what: str) -> float:
    """Convert a real numeric scalar (int/float/NumPy-like) to a finite float."""
    if value is None or isinstance(value, (bool, str, bytes, complex)):
        raise TypeError(f"{what} must be a real numeric scalar, got {type(value).__name__}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(
            f"{what} must be convertible to float, got {type(value).__name__}"
        ) from exc
    if not math.isfinite(number):
        raise ValueError(f"{what} must be finite, got {number!r}")
    return number


def rerank_indices(
    reranker,
    query: str,
    ranking: list[int],
    texts: list[str],
    top_k: int = 5,
) -> list[int]:
    """Rerank candidate indices with ``reranker`` and return the best ``top_k`` ids.

    Contract (violations raise TypeError/ValueError before ``predict`` runs):
    ``query`` is a non-empty str; ``texts`` is a non-empty list of non-empty
    str; ``ranking`` is a non-empty list of unique non-bool ints with
    ``0 <= idx < len(texts)``; ``top_k`` is a positive non-bool int with
    ``top_k <= len(ranking)``. ``reranker.predict`` is called exactly once,
    positionally with ``[(query, texts[idx]), ...]`` in ``ranking`` order and
    without ``batch_size``; it must return exactly ``len(ranking)`` real,
    finite numeric scores. Scores are sorted descending; equal scores keep
    the original candidate order, and the ids of the first ``top_k``
    entries are returned.
    """
    _check_query(query)
    _check_texts(texts)
    _check_index_list(ranking, upper=len(texts), what="ranking")
    _check_positive_int(top_k, "top_k")
    if top_k > len(ranking):
        raise ValueError(f"top_k must not exceed len(ranking)={len(ranking)}, got {top_k}")

    pairs = [(query, texts[index]) for index in ranking]
    raw_scores = reranker.predict(pairs)

    try:
        score_count = len(raw_scores)
    except TypeError as exc:
        raise TypeError("reranker.predict() result must support len()") from exc
    if score_count != len(ranking):
        raise ValueError(
            f"reranker.predict() returned {score_count} scores, expected {len(ranking)}"
        )

    scores = [
        _finite_float(score, f"score[{position}]")
        for position, score in enumerate(raw_scores)
    ]
    # Ascending sort on negated scores == descending on scores; sort
    # stability preserves the original candidate order for equal scores.
    order = sorted(range(len(scores)), key=lambda position: -scores[position])
    return [ranking[position] for position in order[:top_k]]


def validate_d1_rankings(
    report: dict,
    *,
    chunk_count: int,
    case_count: int,
    repetitions: int = 3,
    candidate_limit: int = 40,
) -> dict[str, list[list[int]]]:
    """Validate a D.1 benchmark report and copy out the per-arm rankings.

    Structural contract: ``report`` is a dict containing ``runs`` (extra
    top-level keys are allowed); ``runs`` is a list of exactly
    ``repetitions`` run dicts with exactly the keys ``postgres`` and
    ``chroma_bm25``; each arm is a dict with exactly the keys ``rankings``,
    ``latency_ms`` and ``metrics`` (metrics content is not validated here);
    ``rankings`` and ``latency_ms`` are lists of length ``case_count``;
    every ranking is a non-empty list of at most ``candidate_limit`` unique
    non-bool ints with ``0 <= idx < chunk_count``; every latency is a real
    finite numeric scalar > 0; and each arm's rankings are value-identical
    across all repetitions (latencies and metrics may differ). Returns a
    deep-independent copy of the first run's rankings for both arms;
    mutating the return value never mutates ``report``.
    """
    _check_positive_int(chunk_count, "chunk_count")
    _check_positive_int(case_count, "case_count")
    _check_positive_int(repetitions, "repetitions")
    _check_positive_int(candidate_limit, "candidate_limit")

    if not isinstance(report, dict):
        raise TypeError(f"report must be a dict, got {type(report).__name__}")
    if "runs" not in report:
        raise ValueError("report must contain the key 'runs'")
    runs = report["runs"]
    if not isinstance(runs, list):
        raise TypeError(f"report['runs'] must be a list, got {type(runs).__name__}")
    if len(runs) != repetitions:
        raise ValueError(
            f"report['runs'] must contain exactly {repetitions} runs, got {len(runs)}"
        )

    arm_names = ("postgres", "chroma_bm25")
    arm_keys = {"rankings", "latency_ms", "metrics"}
    baseline: dict[str, list[list[int]]] | None = None

    for run_position, run in enumerate(runs):
        if not isinstance(run, dict):
            raise TypeError(f"run #{run_position} must be a dict, got {type(run).__name__}")
        if set(run) != set(arm_names):
            raise ValueError(
                f"run #{run_position} must have exactly the keys {list(arm_names)}, "
                f"got {sorted(run)}"
            )
        for arm_name in arm_names:
            arm = run[arm_name]
            if not isinstance(arm, dict):
                raise TypeError(
                    f"run #{run_position} arm {arm_name!r} must be a dict, "
                    f"got {type(arm).__name__}"
                )
            if set(arm) != arm_keys:
                raise ValueError(
                    f"run #{run_position} arm {arm_name!r} must have exactly the keys "
                    f"{sorted(arm_keys)}, got {sorted(arm)}"
                )

            rankings = arm["rankings"]
            if not isinstance(rankings, list):
                raise TypeError(
                    f"run #{run_position} arm {arm_name!r} rankings must be a list, "
                    f"got {type(rankings).__name__}"
                )
            if len(rankings) != case_count:
                raise ValueError(
                    f"run #{run_position} arm {arm_name!r} rankings must contain exactly "
                    f"{case_count} entries, got {len(rankings)}"
                )
            for case_position, ranking in enumerate(rankings):
                _check_index_list(
                    ranking,
                    upper=chunk_count,
                    what=f"run #{run_position} arm {arm_name!r} rankings[{case_position}]",
                    limit=candidate_limit,
                )

            latencies = arm["latency_ms"]
            if not isinstance(latencies, list):
                raise TypeError(
                    f"run #{run_position} arm {arm_name!r} latency_ms must be a list, "
                    f"got {type(latencies).__name__}"
                )
            if len(latencies) != case_count:
                raise ValueError(
                    f"run #{run_position} arm {arm_name!r} latency_ms must contain exactly "
                    f"{case_count} entries, got {len(latencies)}"
                )
            for case_position, latency in enumerate(latencies):
                value = _finite_float(
                    latency,
                    f"run #{run_position} arm {arm_name!r} latency_ms[{case_position}]",
                )
                if value <= 0:
                    raise ValueError(
                        f"run #{run_position} arm {arm_name!r} latency_ms[{case_position}] "
                        f"must be > 0, got {value!r}"
                    )

            if baseline is None:
                baseline = {name: list(run[name]["rankings"]) for name in arm_names}
            elif rankings != baseline[arm_name]:
                raise ValueError(
                    f"run #{run_position} arm {arm_name!r} rankings differ between repetitions"
                )

    first_run = runs[0]
    return {
        arm_name: [list(ranking) for ranking in first_run[arm_name]["rankings"]]
        for arm_name in arm_names
    }
