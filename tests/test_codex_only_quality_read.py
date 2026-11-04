"""Synthetic offline reading contracts, for the Mac session's test run."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports/codex-only-quality/tools"))
import quality_read as reading  # noqa: E402


def evidence():
    old, new, measured, before, after, groups = {}, {}, {}, {}, {}, {}
    for key in reading.cv.KEYS:
        old[key], new[key], measured[key], groups[key] = {}, {}, {}, {}
        for n in range(100):
            cid = f"synthetic-{n:03}"
            old[key][cid] = {"case_id": cid, "grade": "good", "context_has_answer": True}
            new[key][cid] = dict(old[key][cid])
            measured[key][cid] = {"class": "accepted"}
            groups[key][cid] = [f"{key}:cluster:{n}"]
        if key != "aircargo":
            before[key] = {
                cid: {
                    "gold": key == "wixqa" or n < 80,
                    "hit": 1 if key == "wixqa" or n < 80 else None,
                    "fraction": 1.0 if key == "wixqa" or n < 80 else None,
                }
                for n, cid in enumerate(old[key])
            }
            after[key] = copy.deepcopy(before[key])
    return old, new, measured, before, after, groups


def test_q_good_requires_answer_and_terminal_failures_zero():
    args = evidence()
    args[1]["wixqa"]["synthetic-000"]["context_has_answer"] = False
    args[2]["wixqa"]["synthetic-001"]["class"] = "counted_out"
    args[2]["wixqa"]["synthetic-002"]["class"] = "product_failure"
    result = reading.analyze(*args)
    assert result["q"]["pooled"]["product_count"] == 297
    assert result["q"]["pooled"]["n"] == 300
    assert result["q"]["per_key"]["wixqa"]["product_count"] == 97


def test_pending_refuses_without_shrinking_denominator():
    args = evidence()
    args[2]["wixqa"]["synthetic-000"]["class"] = "pending"
    with pytest.raises(reading.cv.Refusal, match="whole"):
        reading.analyze(*args)
    assert reading.decision(None, None, ["key not whole"], False)["row"] == 1


def test_empty_r_context_and_no_gold():
    class Reader:
        def __init__(self):
            self.cases = {"gold": {}, "no-gold": {}}

        def saved_point(self, case, documents):
            raise AssertionError("historical instrument cannot accept an empty context")

    assert reading.sent_point(Reader(), "gold", [], {"gold": True}) == {
        "gold": True,
        "hit": 0,
        "fraction": 0.0,
    }
    assert reading.sent_point(Reader(), "no-gold", [], {"gold": False}) == {
        "gold": False,
        "hit": None,
        "fraction": None,
    }


@pytest.mark.parametrize("fall", ["q", "r", None])
def test_decision_rows_and_next_step(fall):
    holds = {"newcombe95": [-0.1, 0.1], "cluster95": [-0.1, 0.1]}
    falls = {"newcombe95": [-0.4, -0.1], "cluster95": [-0.5, -0.2]}
    result = reading.decision(
        falls if fall == "q" else holds, falls if fall == "r" else holds, [], False
    )
    assert result["row"] == (2 if fall else 3)
    if fall:
        assert ("context selection" if fall == "r" else "answer path") in result["next_step"]


def test_one_interval_below_zero_is_not_a_fall():
    result = reading.decision(
        {"newcombe95": [-1, -0.1], "cluster95": [-1, 0.1]},
        {"newcombe95": [-1, 0], "cluster95": [-1, 0]},
        [],
        False,
    )
    assert result["row"] == 3


def test_registration_old_side_mismatch():
    with pytest.raises(reading.cv.Refusal, match="baseline"):
        reading.match_baselines({"q_baseline": {"cases": [1]}, "r_gate": {}}, {"cases": [0]}, {})
    with pytest.raises(reading.cv.Refusal, match="R gate"):
        reading.match_baselines(
            {"q_baseline": {}, "r_gate": {"passed": True}}, {}, {"passed": False}
        )


def test_bootstrap_is_reproducible_and_registered():
    first = {str(i): int(i < 70) for i in range(100)}
    second = {str(i): int(i % 3 != 0) for i in range(100)}
    groups = {str(i): ["synthetic:" + str(i // 3)] for i in range(100)}
    a = reading.paired(first, second, groups)
    b = reading.paired(first, second, groups)
    assert a == b
    assert a["seed"] == 20261001 and a["resamples"] == 10000
    assert a["read95"] == [
        min(a["newcombe95"][0], a["cluster95"][0]),
        max(a["newcombe95"][1], a["cluster95"][1]),
    ]


@pytest.mark.parametrize("stopped", [False, True])
def test_incomplete_or_stopped_build_still_writes_reading(tmp_path, monkeypatch, stopped):
    args = SimpleNamespace(private=tmp_path / "private", records=tmp_path / "records", series="s")
    state = {
        "cases": {},
        "chunks": [],
        "stops": [{"code": 2, "reason": "request_clock"}] if stopped else [],
    }
    reading.cv.write(args.private / args.series / "state.json", state)

    def refuse(*args, **kwargs):
        raise reading.cv.Refusal("synthetic private text must not be published")

    monkeypatch.setattr(reading.d, "admit_chunk", refuse)
    result = reading.build(args)
    assert result["decision"]["row"] == 1
    assert result["decision"]["stop_fired"] is stopped
    assert result["diagnostics"]["per_key"]["pooled"]["pending"] == 300
    path = args.records / args.series / "reading.json"
    assert reading.cv.read(path) == result
    assert "synthetic private text" not in path.read_text(encoding="utf-8")
