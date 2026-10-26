"""The widget on the 4B (docs/specs/widget-4b.md): the spec's frozen reading on hand-made rows -
the passes cut from a trace, the API log's evaluate line, R1, R2, the grader and the ten."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/widget-4b/tools"


def _load():
    spec = importlib.util.spec_from_file_location("widget_record", TOOLS / "widget_record.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["widget_record"] = module
    spec.loader.exec_module(module)
    return module


wr = _load()


def _step(node, ts, **state):
    return {"node": node, "ts": f"2026-10-26T10:00:{ts:02d}+00:00", "state": state}


def _trace(*, retry=False, no_claim=False, judge="ok", reason=None):
    claims = [] if no_claim else [{"supported": True}, {"supported": False}]
    verify = {
        "claims": claims,
        "grounding_status": "verified" if no_claim else "partial",
        "factuality_score": 0 if no_claim else 50,
        "fact_verification_skipped": False,
    }
    one = [
        _step("retrieve", 5),
        _step(
            "grade_docs",
            10,
            doc_grade_outcome="grader_error",
            graded_docs=[1, 2],
            context_docs=[1] * 5,
        ),
        _step("generate", 20),
        _step("verify_facts", 30, **verify),
        _step("evaluate", 35, judge_status=judge, judge_reason=reason, quality_score=0),
        _step("route_or_retry", 36, route="retry" if retry else "human", knowledge_gap=no_claim),
    ]
    if not retry:
        return one
    two = [
        _step("grade_docs", 40, doc_grade_outcome="ok", graded_docs=[1] * 4, context_docs=[1] * 5),
        _step("generate", 50),
        _step("verify_facts", 55, **verify),
        _step("evaluate", 58, judge_status=judge, judge_reason=reason, quality_score=90),
        _step("route_or_retry", 59, route="human", knowledge_gap=no_claim),
        _step("suggest_questions", 59),
    ]
    return one + two


def test_a_trace_is_cut_into_passes_after_each_route():
    got = wr.passes(_trace(retry=True))
    assert [p["route"] for p in got] == ["retry", "human"]
    assert got[0]["grade"] == {"outcome": "grader_error", "kept": 2, "documents": 5}
    assert got[1]["grade"]["outcome"] == "ok"
    assert got[0]["verify"]["claims"] == 2 and got[0]["verify"]["supported"] == 1
    assert not got[0]["verify"]["no_claim"]
    assert got[1]["evaluate"]["quality"] == 90
    tail = wr.passes(_trace()[:4])
    assert len(tail) == 1 and tail[0]["route"] is None and tail[0]["evaluate"] is None


def test_node_seconds_count_from_the_previous_logged_step():
    got = wr.node_seconds("2026-10-26T10:00:00+00:00", _trace(retry=True))
    assert got["retrieve"] == 5.0
    assert got["grade_docs"] == 5.0 + 4.0
    assert got["generate"] == 10.0 + 10.0
    assert got["suggest_questions"] == 0.0


def test_no_claim_is_the_extractors_none():
    assert wr.no_claim({"claims": [], "grounding_status": "verified", "factuality_score": 0})
    assert not wr.no_claim(
        {
            "claims": [],
            "grounding_status": "verified",
            "factuality_score": 0,
            "fact_verification_skipped": True,
        }
    )
    assert not wr.no_claim({"claims": [{}], "grounding_status": "verified", "factuality_score": 0})


def test_the_api_logs_evaluate_line_is_read_from_json_or_plain_lines():
    lines = [
        json.dumps(
            {
                "msg": "[evaluate] boundary=start monotonic=1.0 provider=ollama "
                "model=qwen3 independent=False require=True"
            }
        ),
        "INFO: other",
        "[evaluate] boundary=start monotonic=2.0 provider=- model=- independent=True require=False",
    ]
    assert wr.evaluate_lines(lines) == [
        {"independent": False, "require": True},
        {"independent": True, "require": False},
    ]


def test_model_calls_are_the_wrappers_ends_inside_the_request():
    stages = [
        {"stage": "ollama.generate", "event": "start", "monotonic": 10.0},
        {"stage": "ollama.generate", "event": "end", "monotonic": 12.0, "wall_sec": 2.0},
        {"stage": "ollama.generate", "event": "end", "monotonic": 30.0, "wall_sec": 5.0},
        {"stage": "hybrid._vector_search", "event": "end", "monotonic": 11.0, "wall_sec": 1.0},
    ]
    assert wr.model_calls(stages, 10.0, 15.0) == {"calls": 1, "seconds": 2.0}


def _row(run, case_id, trace, route="human", ticket=True, seconds=600.0):
    return {
        "kind": "answer",
        "run": run,
        "case_id": case_id,
        "route": route,
        "ticket": ticket,
        "seconds": seconds,
        "delivered": True,
        "passes": wr.passes(trace),
        "model_calls": {"calls": 9, "seconds": 500.0},
    }


PRODUCTION_LINES = {"production": [{"independent": False, "require": True}]}


def test_r1_is_confirmed_only_by_the_fail_closed_production_request():
    prod = [_row("widget-production", "p", _trace(judge="unavailable", reason=wr.NO_JUDGE))]
    dev = [_row("widget-development", "d", _trace())]
    assert wr.r1(prod, dev, PRODUCTION_LINES)["reading"] == "confirmed"
    assert (
        wr.r1(prod, dev, {"production": [{"independent": False, "require": False}]})["reading"]
        == "not settled"
    )
    assert wr.r1(prod, dev, {})["reading"] == "not settled"
    dev_no_judge = [
        _row("widget-development", "d", _trace(judge="unavailable", reason=wr.NO_JUDGE))
    ]
    assert wr.r1(prod, dev_no_judge, PRODUCTION_LINES)["reading"] == "not settled"
    auto = [
        _row(
            "widget-production", "p", _trace(judge="unavailable", reason=wr.NO_JUDGE), route="auto"
        )
    ]
    assert wr.r1(auto, dev, PRODUCTION_LINES)["reading"] == "not settled"
    judged = [_row("widget-production", "p", _trace(judge="ok"))]
    assert wr.r1(judged, dev, PRODUCTION_LINES)["reading"] == "refuted"
    assert wr.r1([], dev, PRODUCTION_LINES)["reading"] == "not settled"


def test_r2_is_a_no_claim_answer_sent_to_a_person_as_a_gap():
    seen = [
        _row("widget-development", "a", _trace(no_claim=True)),
        _row("widget-development", "b", _trace()),
    ]
    assert wr.r2(seen) == {"reading": "seen", "cases": ["a"]}
    auto = [_row("widget-development", "a", _trace(no_claim=True), route="auto")]
    assert wr.r2(auto)["reading"] == "not seen on these ten"


def test_the_grader_counts_its_failed_passes_and_the_ten_their_routes():
    rows = [
        _row("widget-development", "a", _trace(retry=True), seconds=900.0),
        _row("widget-development", "b", _trace(), route="auto", ticket=False, seconds=500.0),
        _row("widget-development", "c", _trace(), seconds=700.0),
    ]
    assert wr.grader(rows) == {
        "passes": 4,
        "defects": 3,
        "outcomes": {"grader_error": 3, "ok": 1},
    }
    classes = {"a": {"chat_grade": "good", "chat_class": "good"}}
    got = wr.ten(rows, classes)
    assert got["routes"] == {"auto": 1, "human": 2}
    assert (got["tickets"], got["retries"]) == (2, 1)
    assert got["seconds"] == {"median": 700.0, "max": 900.0}
    assert got["questions"][0]["chat_grade"] == "good"
    assert got["questions"][1]["chat_class"] is None


def test_the_judge_class_is_the_handover_plans():
    assert wr.judge_class({"grade": "bad", "answers_question": "full"}) == "target"
    assert wr.judge_class({"grade": "good", "answers_question": "declined"}) == "target"
    assert wr.judge_class({"grade": "good", "answers_question": "full"}) == "good"
    assert wr.judge_class({"grade": "partial_ok", "answers_question": "partial"}) is None


def test_the_tools_hold_the_specs_requests():
    spec = (ROOT / wr.SPEC).read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    plan = json.loads(wr.PLAN.read_text(encoding="utf-8"))
    order = [item["case_id"] for item in plan["items"]]
    assert wr.RUNS["widget-development"][1] == order[:10]
    assert wr.RUNS["widget-production"][1] == [order[10]]
    chain = (TOOLS / "widget.sh").read_text(encoding="utf-8")
    assert "TEN=" + ",".join(order[:10]) in chain
    assert "PRODUCTION=" + order[10] in chain
    assert chain.index("run widget-production") < chain.index("run widget-development")
    assert "CAP=4200" in chain and "4,200 s" in spec
    supervisor = (TOOLS / "widget_supervisor.py").read_text(encoding="utf-8")
    for name in wr.TOOLS:
        assert f'"{name}"' in supervisor
