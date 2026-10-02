from __future__ import annotations

from typing import Any

import pytest

from evaluation.blinded_judge import quadratic_kappa
from scripts import generator_benchmark as benchmark


def record(key: str, raw: str | None = "0.5", *, truncated: bool = False) -> benchmark.JudgeScore:
    return benchmark.parse_judge_score(
        raw, request_text=key, context_length=3001 if truncated else 3000, answer_length=2000
    )


def test_valid_parser_records_are_accepted_and_truncated_pair_does_not_change_kappa() -> None:
    left = [record("a", "0.0"), record("b", "0.75"), record("c", "1.0")]
    right = [record("c", "1.0"), record("a", "0.25"), record("b", "0.5")]
    result = benchmark.deciding_kappa_sample(left, right)
    assert result == {
        "kappa": quadratic_kappa([0, 3, 3], [1, 2, 3]),
        "pair_count": 3,
        "exclusions": {"unpaired": 0, "absent": 0, "invalid": 0, "truncated": 0},
    }
    extended = benchmark.deciding_kappa_sample(
        left + [record("d", "0.0", truncated=True)], right + [record("d", "1.0")]
    )
    assert extended["kappa"] == result["kappa"]
    assert extended["pair_count"] == 3
    assert extended["exclusions"] == {"unpaired": 0, "absent": 0, "invalid": 0, "truncated": 1}


@pytest.mark.parametrize(
    ("score", "category"), [(0.0, 0), (0.249, 0), (0.25, 1), (0.5, 2), (0.75, 3), (1.0, 3)]
)
def test_registered_binning_edges(score: float, category: int) -> None:
    assert benchmark.generation_score_bin(score) == category


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf"), None, True])
def test_binning_refuses_scores_outside_the_unit_interval(score: Any) -> None:
    with pytest.raises(ValueError, match="unit-interval"):
        benchmark.generation_score_bin(score)


def test_exclusions_have_precedence_and_unpaired_counts_per_record() -> None:
    left = [
        record("left", None, truncated=True),
        record("absent", "bad", truncated=True),
        record("invalid", "bad", truncated=True),
        record("truncated", truncated=True),
    ]
    right = [record("right", "bad"), record("absent", None), record("invalid"), record("truncated")]
    result = benchmark.deciding_kappa_sample(left, right)
    assert result == {
        "kappa": None,
        "pair_count": 0,
        "exclusions": {"unpaired": 2, "absent": 1, "invalid": 1, "truncated": 1},
    }


@pytest.mark.parametrize("source", [0, 1])
def test_duplicate_request_hash_is_refused(source: int) -> None:
    sources = [[record("a")], [record("a")]]
    sources[source].append(record("a"))
    with pytest.raises(ValueError, match="duplicate"):
        benchmark.deciding_kappa_sample(*sources)


@pytest.mark.parametrize("stored", [None, False])
@pytest.mark.parametrize("source", [0, 1])
@pytest.mark.parametrize("truncated", [False, True])
def test_unknown_status_is_refused(stored: bool | None, source: int, truncated: bool) -> None:
    outcome: dict[str, Any] = dict(record("a", "0.0", truncated=truncated))
    outcome["status"] = "pending"
    if stored is None:
        outcome.pop("kappa_eligible")
    else:
        outcome["kappa_eligible"] = stored
    sources = [[dict(record("a", "1.0"))], [dict(record("a", "1.0"))]]
    sources[source] = [outcome]
    with pytest.raises(ValueError, match="unknown.*status"):
        benchmark.deciding_kappa_sample(*sources)


@pytest.mark.parametrize(
    ("raw", "truncated", "stored"),
    [("0.5", False, False), ("0.5", True, True), (None, False, True), ("bad", False, True)],
)
def test_contradictory_eligibility_is_refused_even_for_unpaired_record(
    raw: str | None, truncated: bool, stored: bool
) -> None:
    outcome = record("a", raw, truncated=truncated)
    outcome["kappa_eligible"] = stored
    with pytest.raises(ValueError, match="kappa_eligible"):
        benchmark.deciding_kappa_sample([outcome], [])


def test_aggregate_partition_and_markdown_preserve_existing_counters() -> None:
    outcomes = [
        record("valid"),
        record("truncated", truncated=True),
        record("invalid", "bad", truncated=True),
        record("absent", None, truncated=True),
        None,
    ]
    rows = []
    for index, outcome in enumerate(outcomes):
        rows.append(
            {
                "case_id": str(index),
                "generation_valid": True,
                "nli_valid": True,
                "llm_judge_valid": True,
                "judge_requests": {name: outcome for name in ("faithfulness", "answer_relevancy")}
                if outcome
                else {},
                "scores": {
                    "faithfulness": outcome["score"] if outcome else 0.5,
                    "answer_relevancy": outcome["score"] if outcome else 0.5,
                },
            }
        )
    run: dict[str, Any] = {"run_index": 1, "cases": rows}
    benchmark._aggregate_run(run)
    for counts in run["judge_summary"].values():
        assert counts["kappa_sample_size"] == 1
        assert counts["kappa_exclusions"] == {"absent": 2, "invalid": 1, "truncated": 1}
        assert counts["kappa_sample_size"] + sum(counts["kappa_exclusions"].values()) == len(rows)
        assert (counts["valid"], counts["invalid"], counts["absent"], counts["truncated"]) == (
            3,
            1,
            1,
            3,
        )
    report = {
        "provenance": {
            "config": {},
            **{key: "fixture" for key in (*benchmark.REQUIRED_PROVENANCE, "ollama_model")},
        },
        "evidence_class": "not_evidence",
        "created_at": "fixture",
        "runs": [run],
        "aggregate": {metric: {"mean": None} for metric in benchmark.RUN_METRICS},
    }
    markdown = benchmark._render_markdown(report)
    assert (
        "| Run | Metric | Kappa sample | Excluded absent | Excluded invalid | Excluded truncated |"
        in markdown
    )
    assert "| 1 | faithfulness | 1 | 2 | 1 | 1 |" in markdown
