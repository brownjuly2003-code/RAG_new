"""The encoder checkers (docs/specs/encoder-checkers.md): the spec's frozen rules on hand-made
rows - the splitting, the windows, the classes, the threshold, the reading and the outcome."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/encoder-checkers/tools/encoder_checkers.py"


def _load():
    spec = importlib.util.spec_from_file_location("encoder_checkers", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["encoder_checkers"] = module
    spec.loader.exec_module(module)
    return module


ec = _load()


def test_an_answer_loses_its_reference_marks_and_the_spaces_before_them():
    assert ec.strip_marks("Срок три месяца [1]. Продление нельзя [2, 3].") == (
        "Срок три месяца. Продление нельзя."
    )
    assert ec.strip_marks("No marks here.") == "No marks here."


def test_sentences_split_after_end_marks_and_at_line_breaks_and_drop_wordless_pieces():
    text = "Первое. Второе!  Третье?\n- \n- пункт без точки\nПоследнее"
    assert ec.sentences(text) == [
        "Первое.",
        "Второе!",
        "Третье?",
        "- пункт без точки",
        "Последнее",
    ]
    assert ec.sentences("  \n - \n") == []
    assert ec.sentences("A 2.5 kg box.") == ["A 2.5 kg box."]


def test_windows_cover_the_tokens_and_share_fifty_with_the_next():
    assert ec.windows(0) == []
    assert ec.windows(10) == [(0, 10)]
    assert ec.windows(400) == [(0, 400)]
    assert ec.windows(800) == [(0, 400), (350, 750), (700, 800)]
    assert ec.windows(500, size=300) == [(0, 300), (250, 500)]


def test_the_judge_classes_are_the_handover_plans():
    def row(grade, answers="full"):
        return {"grade": grade, "answers_question": answers}

    assert ec.judge_class(row("bad")) == "target"
    assert ec.judge_class(row("good", "declined")) == "target"
    assert ec.judge_class(row("good")) == "good"
    assert ec.judge_class(row("partial_ok", "partial")) is None


def test_rushallu_good_is_only_the_type_none_and_its_targets_are_grouped():
    assert ec.rushallu_class([{"type": None, "span": ""}]) == (
        "good",
        {"grounding": False, "other": False},
    )
    assert ec.rushallu_class([{"type": "Unconfirmed", "span": "x"}]) == (
        "target",
        {"grounding": True, "other": False},
    )
    assert ec.rushallu_class([{"type": "Missing"}, {"type": "Contradiction"}]) == (
        "target",
        {"grounding": True, "other": True},
    )
    assert ec.rushallu_class([{"type": "Oversight"}])[1] == {"grounding": False, "other": True}


def test_the_rushallu_sample_is_seeded_sized_and_mixed():
    rows = {"sberquad-rag": [{}] * 655, "ruscibench-rag": [{}] * 345}
    first, second = ec.rushallu_sample(rows), ec.rushallu_sample(rows)
    assert first == second
    assert len(first) == len(set(first)) == 300
    names = [name for name, _ in first]
    assert names.count("sberquad-rag") == 200 and names.count("ruscibench-rag") == 100
    assert names[:100].count("ruscibench-rag") > 10, "the two files are shuffled together"


def _rows(half, good, target):
    return [{"set": half, "class": "good", "score": s} for s in good] + [
        {"set": half, "class": "target", "score": s} for s in target
    ]


def test_the_threshold_weighs_ru_and_en_equally_and_over_marks_at_most_a_third():
    # RU: 6 good, 3 targets; EN: 3 good, 3 targets. Below 0.6 marks EN's goods 0.3 and 0.5:
    # over-marking (0 + 2/3) / 2 = 1/3, catching (2/3 + 1) / 2. Below 0.7 also marks RU's 0.6:
    # (1/6 + 2/3) / 2 > 1/3. Unweighted, 0.7 would over-mark 3 of 9 and catch all six.
    rows = _rows("RU", [0.6, 0.7, 0.8, 0.9, 0.95, 0.99], [0.1, 0.1, 0.65])
    rows += _rows("EN", [0.3, 0.5, 0.9], [0.4, 0.55, 0.55])
    got = ec.threshold(rows)
    assert got["threshold"] == 0.6
    assert got["over_marked_share"] == pytest.approx(1 / 3)
    assert got["caught_share"] == pytest.approx(5 / 6)


def test_the_threshold_takes_the_lowest_candidate_on_a_tie_and_none_when_it_catches_nothing():
    rows = _rows("RU", [0.5, 0.6, 0.7], [0.1]) + _rows("EN", [0.5, 0.6, 0.7], [0.1])
    got = ec.threshold(rows)
    # Candidates 0.5 and 0.6 both catch every target; 0.5 marks no good answer.
    assert got["threshold"] == 0.5
    assert got["caught_share"] == 1.0 and got["over_marked_share"] == 0.0
    flat = _rows("RU", [0.2, 0.3], [0.5]) + _rows("EN", [0.2, 0.3], [0.5])
    assert ec.threshold(flat)["threshold"] is None


def test_a_threshold_below_the_scores_marks_nothing_and_unscored_answers_count_unmarked():
    rows = _rows("RU", [0.9, 0.8, 0.7], [None, 0.2]) + _rows("EN", [0.9, 0.8, 0.7], [0.3])
    got = ec.threshold(rows)
    assert got["threshold"] == 0.7
    assert ec.counts(rows, 0.7) == {
        "caught": 2,
        "target": 3,
        "over_marked": 0,
        "good_not_declining": 6,
    }
    assert not ec.marks(None, 0.5)


def test_the_reading_is_the_handover_plans_frozen_one():
    rows = [{"class": "target", "score": 0.1}] * 12 + [{"class": "target", "score": 0.9}] * 5
    rows += [{"class": "good", "score": 0.1}] * 21 + [{"class": "good", "score": 0.9}] * 42
    assert ec.reading(rows, 0.5)["reading"] == "worth wiring"
    over = (
        rows[:17] + [{"class": "good", "score": 0.1}] * 22 + [{"class": "good", "score": 0.9}] * 41
    )
    assert ec.reading(over, 0.5)["reading"] == "in between"
    weak = [{"class": "target", "score": 0.1}] * 4 + [{"class": "target", "score": 0.9}] * 13
    weak += [{"class": "good", "score": 0.9}] * 63
    assert ec.reading(weak, 0.5)["reading"] == "useless"
    assert ec.reading(rows, None) == {
        "caught": 0,
        "target": 17,
        "over_marked": 0,
        "good_not_declining": 63,
        "reading": "useless",
    }


def test_auroc_is_the_chance_a_good_answer_scores_above_a_target():
    rows = _rows("x", [0.9, 0.5], [0.5, 0.1])
    assert ec.auroc(rows) == pytest.approx((1 + 1 + 0.5 + 1) / 4)
    assert ec.auroc(_rows("x", [0.9], [])) is None


def _checker(reading, caught=0, over=0, median=1.0):
    entry = (
        reading
        if reading == ec.NOT_EVIDENCE
        else {"reading": reading, "caught": caught, "over_marked": over}
    )
    return {"reading": entry, "seconds": {"reading": {"median": median}}}


def test_the_outcome_names_the_best_checker_worth_wiring_then_not_evidence_then_in_between():
    got = ec.outcome(
        {
            "H": _checker("worth wiring", 12, 20, 3.0),
            "L": _checker("worth wiring", 13, 21, 4.0),
            "N": _checker(ec.NOT_EVIDENCE),
        }
    )
    assert got == {"decision": "worth wiring: L", "worth_wiring": "L"}
    tie = ec.outcome(
        {"H": _checker("worth wiring", 12, 20, 3.0), "L": _checker("worth wiring", 12, 20, 2.0)}
    )
    assert tie["worth_wiring"] == "L"
    assert ec.outcome({"H": _checker("in between"), "N": _checker(ec.NOT_EVIDENCE)}) == {
        "decision": "NOT_EVIDENCE: N",
        "worth_wiring": None,
    }
    assert ec.outcome({"H": _checker("in between"), "L": _checker("useless")})["decision"] == (
        "in between: H"
    )
    assert ec.outcome({"H": _checker("useless")})["decision"] == "none worth wiring"


def _score_rows(reading=100, en=(30, 15), ru=(30, 15)):
    start = {
        "kind": "start",
        "checker": "H",
        "repo": "r",
        "revision": "v",
        "tool_sha256": "t",
        "weights_sha256": "w",
        "inputs_sha256": "i",
        "planned": {"reading": 100, "EN": 183, "RU": 300},
        "load": [1.0, 1.0, 1.0],
    }
    rows = [start]

    def add(half, cls, count, value):
        rows.extend(
            {
                "kind": "answer",
                "set": half,
                "class": cls,
                "score": value,
                "seconds": 2.0,
                "truncated": 0,
            }
            for _ in range(count)
        )

    add("reading", "target", min(reading, 17), 0.1)
    add("reading", "good", max(0, reading - 17), 0.9)
    for half, (goods, targets) in (("EN", en), ("RU", ru)):
        add(half, "good", goods, 0.9)
        add(half, "target", targets, 0.1)
    rows.append({"kind": "end", "stopped": False, "peak_rss_bytes": 10, "load": [2.0, 2.0, 2.0]})
    return rows


def test_a_checker_reads_not_evidence_when_its_reading_set_or_a_half_is_short():
    whole = ec.checker_record(_score_rows())
    assert whole["reading"]["reading"] == "worth wiring"
    assert whole["not_evidence_because"] == []
    assert ec.checker_record(_score_rows(reading=99))["reading"] == ec.NOT_EVIDENCE
    short = ec.checker_record(_score_rows(ru=(29, 15)))
    assert short["reading"] == ec.NOT_EVIDENCE
    assert short["not_evidence_because"] == ["RU good"]


def test_a_resumed_segment_must_be_the_same_run():
    rows = _score_rows()
    rows.insert(5, {**rows[0], "tool_sha256": "other"})
    with pytest.raises(SystemExit):
        ec.checker_record(rows)


def test_the_tool_holds_the_specs_constants():
    spec = (ROOT / ec.SPEC).read_text(encoding="utf-8")
    assert "registered before the first checker call" in spec
    for checker in ec.CHECKERS.values():
        assert checker["repo"] in spec and checker["revision"][:8] in spec
    assert {name: c["forecast_min"] for name, c in ec.CHECKERS.items()} == {
        "H": 30,
        "L": 30,
        "N": 80,
    }
    assert (ec.SEED, ec.STOP_FACTOR, ec.MIN_GOOD, ec.MIN_TARGET) == (20261026, 3, 30, 15)
    assert ec.RUSHALLU_FILES == {"sberquad-rag": 200, "ruscibench-rag": 100}
    assert (ec.H_MAX, ec.L_MAX, ec.N_WINDOW, ec.N_SHARED) == (2048, 4096, 400, 50)
    assert ec.PARITY_TOLERANCE == 0.01 and len(ec.parity_pairs()) == 12
    assert ec.RUSHALLU_COMMIT.startswith("345907f9") and "345907f9" in spec
