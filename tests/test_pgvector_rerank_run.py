"""Contracts for the D.3 offline rerank runner core."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from scripts.pgvector_rerank import run_offline_rerank

TEXTS = ["doc zero", "doc one", "doc two", "doc three"]
CASES = [
    {"case_id": "c1", "query": "alpha one", "kws": ["one"]},
    {"case_id": "c2", "query": "beta two", "kws": ["two"]},
]
BUCKETS = {"first": (0, 1), "second": (1, 2)}
SCORES = {
    "doc zero": 0.0,
    "doc one": 1.0,
    "doc two": 2.0,
    "doc three": 3.0,
}
POSTGRES_SAVED = [[2, 0, 1, 3], [1, 3, 0, 2]]
CHROMA_SAVED = [[0, 1], [3, 2]]
CLOCK_VALUES = (0.0, 0.001, 0.010, 0.012, 0.100, 0.103, 0.200, 0.201)


class FakeReranker:
    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.calls.append(list(pairs))
        return [SCORES[text] for _, text in pairs]


class BoomReranker:
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        raise RuntimeError("boom")


class SequenceClock:
    def __init__(self, values: tuple[float, ...] = CLOCK_VALUES) -> None:
        self._values = iter(values)
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return next(self._values)


def make_report() -> dict[str, Any]:
    run = {
        "postgres": {
            "rankings": copy.deepcopy(POSTGRES_SAVED),
            "latency_ms": [1.0, 2.0],
            "metrics": {},
        },
        "chroma_bm25": {
            "rankings": copy.deepcopy(CHROMA_SAVED),
            "latency_ms": [1.5, 2.5],
            "metrics": {},
        },
    }
    return {
        "config": {
            "chunks": len(TEXTS),
            "cases": len(CASES),
            "repetitions": 3,
            "branch_limit": 20,
            "reranker": False,
        },
        "runs": [copy.deepcopy(run) for _ in range(3)],
    }


def make_args(reranker: Any | None = None) -> dict[str, Any]:
    return {
        "reranker": reranker or FakeReranker(),
        "d1_report": make_report(),
        "cases": copy.deepcopy(CASES),
        "texts": list(TEXTS),
        "buckets": dict(BUCKETS),
        "clock": SequenceClock(),
        "top_k": 2,
    }


def test_run_offline_rerank_happy_path() -> None:
    reranker = FakeReranker()
    args = make_args(reranker)

    result = run_offline_rerank(**args)

    assert list(result) == ["postgres", "chroma_bm25"]
    assert reranker.calls == [
        [("alpha one", TEXTS[index]) for index in POSTGRES_SAVED[0]],
        [("beta two", TEXTS[index]) for index in POSTGRES_SAVED[1]],
        [("alpha one", TEXTS[index]) for index in CHROMA_SAVED[0]],
        [("beta two", TEXTS[index]) for index in CHROMA_SAVED[1]],
    ]
    assert args["clock"].calls == 8

    expected = {
        "postgres": ([[3, 2, 1, 0], [3, 2, 1, 0]], [1.0, 2.0]),
        "chroma_bm25": ([[1, 0], [3, 2]], [3.0, 1.0]),
    }
    for arm_name, (rankings, latencies) in expected.items():
        arm = result[arm_name]
        assert set(arm) == {"rankings", "latency_ms", "metrics"}
        assert arm["rankings"] == rankings
        assert arm["latency_ms"] == pytest.approx(latencies)
        assert list(arm["metrics"]) == ["global", "first", "second"]
        assert [row["indices"] for row in arm["metrics"]["global"]["rows"]] == [
            row[:2] for row in rankings
        ]
        assert arm["metrics"]["global"]["cases"] == 2
        assert arm["metrics"]["global"]["latency_p50_ms"] == pytest.approx(
            sum(latencies) / 2
        )
        assert arm["metrics"]["global"]["latency_p95_ms"] == pytest.approx(
            min(latencies) + 0.95 * (max(latencies) - min(latencies))
        )
        for position, bucket_name in enumerate(("first", "second")):
            metric = arm["metrics"][bucket_name]
            assert metric["cases"] == 1
            assert [row["indices"] for row in metric["rows"]] == [rankings[position][:2]]
            assert metric["latency_p50_ms"] == pytest.approx(latencies[position])
            assert metric["latency_p95_ms"] == pytest.approx(latencies[position])


INVALID_MUTATIONS: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("config-missing", lambda args: args["d1_report"].pop("config")),
    ("config-chunks", lambda args: args["d1_report"]["config"].update(chunks=99)),
    ("config-reranker", lambda args: args["d1_report"]["config"].update(reranker=True)),
    ("duplicate-case", lambda args: args["cases"][1].update(case_id="c1")),
    ("case-extra-key", lambda args: args["cases"][0].update(extra="x")),
    ("case-bad-kws", lambda args: args["cases"][0].update(kws="one")),
    ("empty-text", lambda args: args["texts"].__setitem__(1, "")),
    ("bucket-gap", lambda args: args.update(buckets={"first": (0, 1)})),
    (
        "bucket-overlap",
        lambda args: args.update(buckets={"first": (0, 2), "second": (1, 2)}),
    ),
    (
        "bucket-not-tuple",
        lambda args: args.update(buckets={"first": [0, 1], "second": (1, 2)}),
    ),
    ("buckets-empty", lambda args: args.update(buckets={})),
    ("zero-elapsed", lambda args: args.update(clock=lambda: 1.0)),
]


@pytest.mark.parametrize(
    "mutate",
    [mutation for _, mutation in INVALID_MUTATIONS],
    ids=[name for name, _ in INVALID_MUTATIONS],
)
def test_run_offline_rerank_rejects_invalid_inputs(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    args = make_args()
    mutate(args)

    with pytest.raises((TypeError, ValueError)):
        run_offline_rerank(**args)


@pytest.mark.parametrize("top_k", [3, 0, True, 2.0])
def test_run_offline_rerank_rejects_bad_top_k_before_predict(top_k: Any) -> None:
    reranker = FakeReranker()
    args = make_args(reranker)
    args["top_k"] = top_k

    with pytest.raises((TypeError, ValueError)):
        run_offline_rerank(**args)
    assert reranker.calls == []


def test_run_offline_rerank_does_not_mask_reranker_errors() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        run_offline_rerank(**make_args(BoomReranker()))
