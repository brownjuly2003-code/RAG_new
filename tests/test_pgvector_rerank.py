"""Contract tests for the future scripts.pgvector_rerank module (D.3 offline rerank)."""
from __future__ import annotations

from collections.abc import Callable
from operator import setitem
from typing import Any

import numpy as np
import pytest

from scripts.pgvector_rerank import rerank_indices, validate_d1_rankings

TEXTS4 = ["t0", "t1", "t2", "t3"]


class FakeReranker:
    """Test double: records predict(pairs) calls, replays scripted scores."""

    def __init__(self, scores: list[Any]) -> None:
        self.scores = list(scores)
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs: Any) -> list[Any]:
        self.calls.append([tuple(pair) for pair in pairs])
        return list(self.scores)


# --------------------------------------------------------------- rerank_indices


@pytest.mark.parametrize(
    "scores",
    [
        [0.2, 0.9, 0.9, -1.0],
        [1, 4, 4, 0],
        list(np.array([0.2, 0.9, 0.9, -1.0])),
    ],
    ids=["float", "int", "numpy-scalars"],
)
def test_rerank_indices_orders_pairs_ties_and_calls_predict_once(scores: list[Any]) -> None:
    fake = FakeReranker(scores)

    assert rerank_indices(fake, "query", [2, 0, 3, 1], TEXTS4, top_k=3) == [0, 3, 2]

    assert fake.calls == [
        [("query", "t2"), ("query", "t0"), ("query", "t3"), ("query", "t1")]
    ]


@pytest.mark.parametrize(
    "scores",
    [
        [0.1, 0.2, 0.3],
        [0.1, 0.2, 0.3, 0.4, 0.5],
        [0.1, True, 0.3, 0.4],
        [0.1, float("nan"), 0.3, 0.4],
        [0.1, float("inf"), 0.3, 0.4],
        [0.1, float("-inf"), 0.3, 0.4],
        [0.1, "high", 0.3, 0.4],
        [0.1, None, 0.3, 0.4],
    ],
    ids=["short", "long", "bool", "nan", "inf", "neg-inf", "str", "none"],
)
def test_rerank_indices_rejects_bad_scores(scores: list[Any]) -> None:
    with pytest.raises((TypeError, ValueError)):
        rerank_indices(FakeReranker(scores), "q", [0, 1, 2, 3], TEXTS4, top_k=2)


@pytest.mark.parametrize("query", ["", 7, None, b"q"], ids=["empty", "int", "none", "bytes"])
def test_rerank_indices_rejects_bad_query(query: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        rerank_indices(FakeReranker([0.3, 0.1]), query, [0, 1], ["t0", "t1"], top_k=1)


@pytest.mark.parametrize(
    "top_k", [0, -1, True, 2.0, "1", 5],
    ids=["zero", "negative", "bool", "float", "str", "over-len"],
)
def test_rerank_indices_rejects_bad_top_k(top_k: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        rerank_indices(FakeReranker([0.1, 0.2, 0.3, 0.4]), "q", [0, 1, 2, 3], TEXTS4, top_k=top_k)


@pytest.mark.parametrize(
    "ranking",
    [[], [0, 0, 1], [0, True, 1], [0, 1, "2"], [0, 1, 4], [0, -1], (0, 1), "01"],
    ids=["empty", "duplicate", "bool-id", "str-id", "out-of-range", "negative", "tuple", "str"],
)
def test_rerank_indices_rejects_bad_ranking(ranking: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        rerank_indices(FakeReranker([0.4, 0.3, 0.2, 0.1]), "q", ranking, TEXTS4, top_k=1)


@pytest.mark.parametrize(
    ("texts", "ranking"),
    [([], [0]), (["t0", ""], [0, 1]), (["t0", 3], [0, 1]), (("t0", "t1"), [0, 1])],
    ids=["empty-texts", "empty-string-entry", "int-entry", "tuple-not-list"],
)
def test_rerank_indices_rejects_bad_texts(texts: Any, ranking: list[int]) -> None:
    with pytest.raises((TypeError, ValueError)):
        rerank_indices(FakeReranker([0.2, 0.1]), "q", ranking, texts, top_k=1)


# ---------------------------------------------------------- validate_d1_rankings


def make_report(repetitions: int = 2) -> dict[str, Any]:
    runs = []
    for _ in range(repetitions):
        runs.append(
            {
                "postgres": {
                    "rankings": [[0, 3, 1], [4, 2]],
                    "latency_ms": [12.5, 7.0],
                    "metrics": {"recall@5": 0.9},
                },
                "chroma_bm25": {
                    "rankings": [[1, 0], [3, 2, 4]],
                    "latency_ms": [9.0, 6.5],
                    "metrics": {"recall@5": 0.8},
                },
            }
        )
    return {"runs": runs}


def test_validate_d1_rankings_happy_path_returns_deep_independent_copy() -> None:
    report = make_report()

    out = validate_d1_rankings(
        report, chunk_count=5, case_count=2, repetitions=2, candidate_limit=4
    )

    assert out == {"postgres": [[0, 3, 1], [4, 2]], "chroma_bm25": [[1, 0], [3, 2, 4]]}
    out["postgres"][0].append(99)
    out["chroma_bm25"][1][0] = -5
    assert report["runs"][0]["postgres"]["rankings"] == [[0, 3, 1], [4, 2]]
    assert report["runs"][0]["chroma_bm25"]["rankings"] == [[1, 0], [3, 2, 4]]
    assert report["runs"][1]["postgres"]["rankings"] == [[0, 3, 1], [4, 2]]


def _set_rank(report: dict[str, Any], run: int, arm: str, i: int, value: Any) -> None:
    setitem(report["runs"][run][arm]["rankings"], i, value)


def _set_latency(report: dict[str, Any], run: int, arm: str, i: int, value: Any) -> None:
    setitem(report["runs"][run][arm]["latency_ms"], i, value)


MUTATIONS: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("runs-short", lambda r: r["runs"].pop()),
    ("runs-long", lambda r: r["runs"].append(make_report(1)["runs"][0])),
    ("runs-not-list", lambda r: setitem(r, "runs", {"postgres": None})),
    ("arm-missing", lambda r: r["runs"][0].pop("chroma_bm25")),
    ("arm-extra", lambda r: setitem(r["runs"][1], "duckdb", r["runs"][0]["postgres"])),
    ("arm-not-dict", lambda r: setitem(r["runs"][1], "chroma_bm25", [1, 2])),
    ("data-key-missing", lambda r: r["runs"][0]["postgres"].pop("metrics")),
    ("data-key-extra", lambda r: setitem(r["runs"][0]["postgres"], "notes", "x")),
    ("rankings-length", lambda r: setitem(r["runs"][0]["postgres"], "rankings", [[0, 1]])),
    ("latency-length", lambda r: setitem(r["runs"][0]["postgres"], "latency_ms", [3.0])),
    ("ranking-empty", lambda r: _set_rank(r, 0, "postgres", 1, [])),
    ("ranking-too-long", lambda r: _set_rank(r, 0, "postgres", 0, [0, 1, 2, 3, 4])),
    ("ranking-duplicate", lambda r: _set_rank(r, 0, "chroma_bm25", 0, [1, 1])),
    ("ranking-bool-id", lambda r: _set_rank(r, 0, "postgres", 0, [True, 0, 1])),
    ("ranking-out-of-range", lambda r: _set_rank(r, 0, "postgres", 0, [5, 0])),
    ("ranking-negative", lambda r: _set_rank(r, 0, "postgres", 0, [-1, 0])),
    ("ranking-not-list", lambda r: _set_rank(r, 0, "chroma_bm25", 0, (1, 0))),
    ("latency-zero", lambda r: _set_latency(r, 0, "postgres", 0, 0.0)),
    ("latency-negative", lambda r: _set_latency(r, 0, "chroma_bm25", 1, -2.0)),
    ("latency-inf", lambda r: _set_latency(r, 1, "postgres", 0, float("inf"))),
    ("latency-nan", lambda r: _set_latency(r, 1, "postgres", 0, float("nan"))),
    ("latency-bool", lambda r: _set_latency(r, 0, "postgres", 0, True)),
    ("latency-str", lambda r: _set_latency(r, 0, "chroma_bm25", 0, "9")),
    ("unstable-rankings", lambda r: _set_rank(r, 1, "postgres", 0, [3, 0, 1])),
]


@pytest.mark.parametrize("mutate", [fn for _, fn in MUTATIONS], ids=[n for n, _ in MUTATIONS])
def test_validate_d1_rankings_rejects_invalid_reports(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    report = make_report()
    mutate(report)

    with pytest.raises((TypeError, ValueError)):
        validate_d1_rankings(
            report, chunk_count=5, case_count=2, repetitions=2, candidate_limit=4
        )
