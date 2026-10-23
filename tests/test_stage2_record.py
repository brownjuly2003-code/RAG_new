"""reports/stage2/tools/stage2_record.py: part 5's combined record, its reading of the records."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage2" / "tools"
RETEST = {
    "planned": 15,
    "pairs": 15,
    "agree": 15,
    "two_steps_apart": 0,
    "quadratic_kappa": 1.0,
    "ci95": [1.0, 1.0],
    "passed": True,
}


@pytest.fixture()
def tool():
    spec = importlib.util.spec_from_file_location("stage2_record", TOOLS / "stage2_record.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.path[:] = [p for p in sys.path if p != str(TOOLS)]


def answer(case, grade, stratum="answerable", cluster="c1", **fields):
    row = {
        "case_id": case,
        "grade": grade,
        "stratum": stratum,
        "cluster": cluster,
        "marks_listed": 2,
        "marks_unlisted": 0,
        "citations_supported": 2,
        "claims_total": 3,
        "claims_supported": 3,
        "defect": "none",
        "answers_question": "full",
        "context_has_answer": True,
    }
    row.update(fields)
    return row


def test_newcombe_gives_the_published_interval_and_reads_zero_as_not_detected(tool):
    from scripts.chat_signals import wilson

    # Newcombe (1998), method 10: 56/70 against 48/80, the difference 0.2 in [0.0524, 0.3339].
    first = {"share": round(56 / 70, 4), "read95": wilson(56, 70)}
    second = {"share": 0.6, "read95": wilson(48, 80)}
    assert tool.newcombe(first, second) == {
        "difference": 0.2,
        "ci95": [0.0524, 0.3339],
        "detected": True,
    }
    close = tool.newcombe(
        {"share": 0.69, "read95": wilson(69, 100)}, {"share": 0.6, "read95": wilson(60, 100)}
    )
    assert close["difference"] == 0.09 and close["ci95"][0] < 0 < close["ci95"][1]
    assert close["detected"] is False


def test_the_read_interval_is_the_wider_of_wilsons_and_the_clusters(tool):
    assert tool.read95({"wilson95": [0.4, 0.6], "cluster95": [0.35, 0.62]}) == [0.35, 0.62]
    assert tool.read95({"wilson95": [0.4, 0.6], "cluster95": [0.45, 0.55]}) == [0.4, 0.6]
    assert tool.read95({"wilson95": [0.4, 0.6]}) == [0.4, 0.6]


def test_marks_are_a_share_of_marks_each_answer_a_cluster(tool):
    marks = tool.ratio({"a": (1, 2), "b": (2, 2)}, None)
    assert (marks["n"], marks["hits"], marks["share"], marks["answers"]) == (4, 3, 0.75, 2)
    assert marks["clusters"] == 2 and marks["read95"] in (marks["wilson95"], marks["cluster95"])
    joined = tool.ratio({"a": (1, 2), "b": (2, 2)}, {"a": ["cluster:x"], "b": ["cluster:x"]})
    assert joined["clusters"] == 1
    with pytest.raises(SystemExit):
        tool.ratio({"a": (3, 2)}, None)


def test_m1_counts_its_other_parts_from_the_rows_and_splits_two_strata(tool):
    rows = [
        answer("q1", "good"),
        answer("q2", "partial_ok", citations_supported=1, claims_supported=2),
        answer("q3", "bad", defect="copied_context", marks_unlisted=2),
        answer(
            "q4",
            "bad",
            stratum="not_answerable",
            cluster="c4",
            answers_question="partial",
            context_has_answer=False,
            marks_listed=0,
            citations_supported=0,
        ),
        answer("q5", "good", stratum="not_answerable", cluster="c5", answers_question="declined"),
        {
            "case_id": "q6",
            "grade": None,
            "stratum": "answerable",
            "cluster": "c1",
            "marks_listed": 0,
            "marks_unlisted": 0,
        },
    ]
    record = {"plan": "p", "status": "counted", "questions": 6, "missing": ["q6"]}
    record["retest"] = {**RETEST, "pairs_list": [], "field_agreement": {}}
    families = {row["case_id"]: [f"cluster:{row['cluster']}"] for row in rows}
    out = tool.m1(record, rows, families)
    assert out["graded"] == 5 and out["missing"] == ["q6"]
    assert {name: entry["hits"] for name, entry in out["classes"].items()} == {
        "good": 2,
        "partial_ok": 1,
        "bad": 2,
    }
    assert out["classes"]["good"]["n"] == 5 and out["classes"]["good"]["clusters"] == 3
    assert (out["marks_supported"]["hits"], out["marks_supported"]["n"]) == (7, 8)
    assert out["marks_supported"]["answers"] == 4
    assert (out["claims_supported"]["hits"], out["claims_supported"]["n"]) == (14, 15)
    assert out["marks_unlisted"] == {"marks": 2, "answers": 1}
    assert out["with_defect"]["hits"] == 1 and out["with_defect"]["n"] == 5
    assert out["defects"] == {"copied_context": 1, "none": 4}
    assert out["answer_without_context"] == 1
    assert out["retest"] == RETEST
    split = out["by_stratum"]
    assert split["answerable"]["good"]["n"] == 3 and split["not_answerable"]["good"]["hits"] == 1


def test_the_sway_table_holds_the_answers_both_plans_graded(tool):
    first = [
        answer("a", "good"),
        answer("b", "good"),
        answer("c", "bad"),
        answer("d", "partial_ok"),
        answer("e", None),
        answer("f", "bad", empty_answer=True),
    ]
    grades = {"a": "good", "b": "partial_ok", "c": "good", "d": "partial_ok", "e": "good"}
    second = [answer(case, grade) for case, grade in grades.items()] + [answer("f", "bad")]
    out = tool.sway(first, second)
    assert out["answers"] == 4 and out["agree"] == 2 and out["two_steps_apart"] == 1
    assert out["m1_by_m2"]["good"] == {"good": 1, "partial_ok": 1, "bad": 0}
    assert out["m1_by_m2"]["bad"]["good"] == 1
    assert out["quadratic_kappa"] is not None
    with pytest.raises(SystemExit):
        tool.sway(first, second[:-1])


def test_the_collection_refuses_a_path_break_and_another_stand(tool):
    record = {"key": "k", "aggregate": {"path_breaks": {}}, "provenance": {"code_sha": [tool.CODE]}}
    rows = [{"path_breaks": []}]
    same = [{"path_breaks": [], "answer_prompt_same": True}]
    assert tool.collection(record, rows, same) == {
        "answers": 1,
        "path_breaks": 0,
        "parity": {"same": 1, "of": 1},
    }
    with pytest.raises(SystemExit):
        tool.collection(record, [{"path_breaks": ["rerank"]}], same)
    with pytest.raises(SystemExit):
        tool.collection(record, rows, [{"path_breaks": ["bm25"], "answer_prompt_same": True}])
    other = {**record, "provenance": {"code_sha": ["0" * 40]}}
    with pytest.raises(SystemExit):
        tool.collection(other, rows, same)


def test_coverage_reads_the_questions_with_gold_at_each_point(tool):
    def question(case, gold, hit, recall):
        points = {point: {"gold_article": hit, "gold_articles": recall} for point in tool.POINTS}
        return {
            "case_id": case,
            "gold": gold,
            "gold_in_index": gold,
            "unresolved": None,
            "points": points if gold else {},
        }

    rows = [
        question("a", True, 1.0, 1.0),
        question("b", True, 0.0, 0.5),
        question("c", False, 0, 0),
    ]
    families = {case: [f"cluster:{case}"] for case in "abc"}
    out = tool.coverage(rows, ("gold_article", "gold_articles"), families)
    assert (out["with_gold"], out["without_gold"], out["gold_in_index"]) == (2, 1, 2)
    sent = out["points"]["sent"]
    assert (sent["gold_article"]["hits"], sent["gold_article"]["n"]) == (1, 2)
    assert sent["gold_articles"]["mean"] == 0.75 and sent["gold_articles"]["clusters"] == 2
    rows[1]["points"]["sent"]["gold_article"] = 0.5
    with pytest.raises(SystemExit):
        tool.coverage(rows, ("gold_article", "gold_articles"), families)
