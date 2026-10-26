"""Coverage beside quality (docs/specs/coverage-metrics.md): the spec's definitions on hand-made
rows."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/coverage/tools/coverage_record.py"


def _load():
    spec = importlib.util.spec_from_file_location("coverage_record", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["coverage_record"] = module
    spec.loader.exec_module(module)
    return module


cov = _load()


def row(case, grade, answers="full", held=True, supported=2, total=2, ref=True, cluster="c1"):
    return {
        "case_id": case,
        "grade": grade,
        "answers_question": answers,
        "context_has_answer": held,
        "claims_supported": supported,
        "claims_total": total,
        "has_reference": ref,
        "cluster": cluster,
    }


def empty(case, ref=True, cluster="c1"):
    return {
        "case_id": case,
        "grade": "bad",
        "empty_answer": True,
        "has_reference": ref,
        "cluster": cluster,
    }


def test_kind_and_crag_follow_the_spec():
    good = row("a", "good")
    partial = row("b", "partial_ok", answers="partial")
    wrong = row("c", "bad", supported=1)
    right_decline = row("d", "good", answers="declined", held=False, supported=0, total=0)
    wrong_decline = row("e", "bad", answers="declined", supported=0, total=0)
    off_topic = row("f", "bad", answers="no")
    nothing = empty("g")
    assert [cov.kind(r) for r in (good, right_decline, nothing, off_topic)] == [
        "answered",
        "declined",
        "empty",
        "answered",
    ]
    # CRAG: a decline is «missing» whether right or wrong; an empty answer too.
    assert [cov.crag(r) for r in (good, partial, wrong, right_decline, wrong_decline)] == [
        1.0,
        0.5,
        -1.0,
        0.0,
        0.0,
    ]
    assert cov.crag(nothing) == 0.0
    assert cov.crag(off_topic) == -1.0


def test_matrix_counts_and_decline_precision_recall():
    rows = [
        row("a", "good", ref=True),
        row("b", "bad", answers="declined", held=True, supported=0, total=0, ref=True),
        row("c", "good", answers="declined", held=False, supported=0, total=0, ref=False),
        row("d", "bad", held=False, ref=False),
        empty("e", ref=False),
    ]
    by_ref = cov.matrix(rows, lambda r: r["has_reference"])
    assert by_ref["counts"] == {
        "true": {"declined": 1, "answered": 1, "empty": 0},
        "false": {"declined": 1, "answered": 1, "empty": 1},
    }
    assert by_ref["decline_precision"] == 0.5  # of 2 declines, 1 where the base has no answer
    assert by_ref["decline_recall"] == pytest.approx(0.3333)  # of 3 without, 1 declined
    assert cov.matrix([], lambda r: True)["decline_precision"] is None


def test_side_shares_leave_missing_out_and_name_both_quality_lines():
    rows = [
        row("a", "good", cluster="c1"),
        row("b", "partial_ok", answers="partial", cluster="c1"),
        row("c", "bad", supported=1, cluster="c2"),
        row("d", "good", answers="declined", held=False, supported=0, total=0, cluster="c2"),
        empty("e", cluster="c3"),
        {"case_id": "f", "grade": None, "missing": True, "has_reference": True, "cluster": "c3"},
    ]
    out = cov.side("wixqa", rows)
    assert out["missing"] == ["f"] and out["graded"] == 5
    assert out["kinds"] == {"answered": 3, "declined": 1, "empty": 1}
    assert (out["coverage"]["hits"], out["coverage"]["n"]) == (3, 5)
    assert out["good_among_answered"]["hits"] == 1
    assert out["good_or_partial_among_answered"]["hits"] == 2
    assert out["unsupported_among_answered"]["hits"] == 1
    assert out["crag"]["mean"] == pytest.approx((1 + 0.5 - 1 + 0 + 0) / 5)
    assert out["crag"]["levels"] == {"1": 1, "0.5": 1, "0": 2, "-1": 1}
    assert "cluster95" in out["coverage"] and "by_reference" in out
    # The empty answer has no verdict: it stays out of the context matrix.
    assert sum(sum(c.values()) for c in out["by_context"]["counts"].values()) == 4


def test_aircargo_has_no_reference_matrix_and_no_cluster_interval():
    rows = [row("a", "good"), row("b", "bad", supported=0)]
    for r in rows:
        r.pop("cluster")
    out = cov.side("aircargo", rows)
    assert "by_reference" not in out
    assert "cluster95" not in out["coverage"] and out["coverage"]["wilson95"]
    assert out["crag"]["clusters"] == 2  # each aircargo question its own cluster


def test_side_refuses_an_unnamed_grade_and_a_doubled_question():
    with pytest.raises(SystemExit):
        cov.side("wixqa", [row("a", "none")])
    with pytest.raises(SystemExit):
        cov.side("wixqa", [row("a", "good"), row("a", "bad")])
