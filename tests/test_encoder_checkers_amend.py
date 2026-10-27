"""Amendment 1 of docs/specs/encoder-checkers.md: B added to a copy of the registered tool, Part 1's
score wrapper and record over the four, and Part 2's fresh read - its inputs, its writer, its
frozen reading, its tie to the judge's plan and its outcome - on hand-made rows and the committed
rows of 4f48fed."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/encoder-checkers/tools"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


am = _load("encoder_checkers_amend", TOOLS / "encoder_checkers_amend.py")
ec = am.ec


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_the_registered_tool_runs_unchanged_and_b_is_added_to_its_copy_only():
    registered = hashlib.sha256((TOOLS / "encoder_checkers.py").read_bytes()).hexdigest()
    assert registered == am.REGISTERED_SHA256
    first = json.loads((am.FIRST / "record.json").read_text(encoding="utf-8"))
    assert first["tool_sha256"] == am.REGISTERED_SHA256
    am.check_registered()
    assert ec.__name__ == "encoder_checkers_registered"
    assert Path(ec.__file__).resolve() == (TOOLS / "encoder_checkers.py").resolve()
    other = _load("encoder_checkers_untouched", TOOLS / "encoder_checkers.py")
    assert list(other.CHECKERS) == ["H", "L", "N"] and "B" not in other.SCORERS
    assert list(ec.CHECKERS) == ["H", "L", "N", "B"]
    named = sys.modules.get("encoder_checkers")
    assert named is None or "B" not in named.CHECKERS


def test_b_is_horizon_guard_base_at_its_pinned_revision_scored_as_h():
    assert ec.CHECKERS["B"]["repo"] == "Horizon-Labs/hallucination-guard-base"
    assert ec.CHECKERS["B"]["revision"] == "f0aaaac7c39073b4528191261e874d9664f14254"
    assert ec.CHECKERS["B"]["forecast_min"] == 200
    assert ec.SCORERS["B"] is ec.score_h
    assert am.FRESH_FORECAST_MIN == {"H": 25, "L": 15, "N": 50, "B": 80}


# --- Part 1 ------------------------------------------------------------------------------------


def _parity(tmp_path, weights, passed=True):
    sha = hashlib.sha256(weights.read_bytes()).hexdigest() if weights.is_file() else "0" * 64
    _write(tmp_path / "parity-B.json", {"passed": passed, "B": {"weights_sha256": sha}})


@pytest.fixture
def scoring(tmp_path, monkeypatch):
    """The wrapper's world: B's weights, and a registered score loop that only notes its call."""
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"weights of B")
    calls = []
    monkeypatch.setattr(am, "weights_b", lambda: weights)
    monkeypatch.setattr(am.ec, "score", lambda name, out: calls.append((name, out)))
    return weights, calls


def test_part_one_scores_b_by_the_registered_loop_after_a_row_naming_the_amendment(
    tmp_path, scoring
):
    weights, calls = scoring
    _parity(tmp_path, weights)
    am.score(tmp_path)
    rows = ec.load_jsonl(tmp_path / "scores-B.jsonl")
    assert calls == [("B", tmp_path)]
    assert [row["kind"] for row in rows] == ["amendment"]
    assert rows[0]["registered_sha256"] == am.REGISTERED_SHA256
    assert rows[0]["amendment_sha256"] == am.tools()["amendment_sha256"]


@pytest.mark.parametrize(
    ("spoil", "message"),
    [
        (lambda path, weights: (path / "parity-B.json").unlink(), "has not run"),
        (lambda path, weights: _parity(path, weights, passed=False), "has not passed"),
        (lambda path, weights: weights.write_bytes(b"other weights"), "not the ones"),
        (lambda path, weights: weights.unlink(), "not the ones"),
        (
            lambda path, weights: _write_jsonl(
                path / "scores-B.jsonl", [{"kind": "end", "stopped": True}]
            ),
            "not resumed",
        ),
    ],
)
def test_part_one_refuses_before_it_writes_a_row(tmp_path, scoring, spoil, message):
    weights, calls = scoring
    _parity(tmp_path, weights)
    spoil(tmp_path, weights)
    before = ec.load_jsonl(tmp_path / "scores-B.jsonl")
    with pytest.raises(SystemExit, match=message):
        am.score(tmp_path)
    assert calls == [] and ec.load_jsonl(tmp_path / "scores-B.jsonl") == before


def _b_rows():
    """B's rows as the registered loop would write them, H's committed scores standing in."""
    rows = []
    for row in ec.load_jsonl(am.FIRST / "scores-H.jsonl"):
        if row["kind"] == "start":
            rows.append({"kind": "amendment", **am.tools(), "at": "2026-10-27T00:00:00+00:00"})
            row = {**row, "checker": "B", **{k: ec.CHECKERS["B"][k] for k in ("repo", "revision")}}
        rows.append(row)
    return rows


def _first_h():
    first = json.loads((am.FIRST / "record.json").read_text(encoding="utf-8"))
    return first["checkers"]["H"]


def test_part_one_reads_b_by_the_registered_rules_and_the_outcome_over_the_four(tmp_path):
    _write_jsonl(tmp_path / "scores-B.jsonl", _b_rows())
    _write(tmp_path / "parity-B.json", {"passed": True})
    got = am.base(tmp_path)
    held = {k: v for k, v in _first_h().items() if k not in ("repo", "revision")}
    assert {k: v for k, v in got["checkers"]["B"].items() if k not in ("repo", "revision")} == held
    assert got["decision"] == "in between: H, L, N, B" and got["worth_wiring"] is None
    assert got["amendments"] == [am.tools()["amendment_sha256"]]
    assert got["orphan_amendment_rows"] == 0 and got["proposes"] is False
    assert got["part"] == 1 and got["registered_sha256"] == am.REGISTERED_SHA256
    assert json.loads((tmp_path / "record.json").read_text(encoding="utf-8")) == json.loads(
        json.dumps(got, ensure_ascii=False)
    )


def test_part_one_reads_a_resumed_file_past_a_launch_that_broke_before_its_start(tmp_path):
    rows = _b_rows()
    start = next(row for row in rows if row["kind"] == "start")
    middle = len(rows) // 2
    amendment = {"kind": "amendment", **am.tools(), "at": "2026-10-27T01:00:00+00:00"}
    rows[middle:middle] = [
        {"kind": "end", "stopped": False, "seconds_spent": 1.0, "peak_rss_bytes": 1, "load": []},
        amendment,
        amendment,
        {**start, "resumed_after": middle},
    ]
    _write_jsonl(tmp_path / "scores-B.jsonl", rows)
    _write(tmp_path / "parity-B.json", {"passed": True})
    got = am.base(tmp_path)
    assert got["amendments"] == [am.tools()["amendment_sha256"]] * 2
    assert got["orphan_amendment_rows"] == 1
    assert got["checkers"]["B"]["segments"] == 2
    for key in ("threshold", "reading", "calibration", "auroc", "reached"):
        assert got["checkers"]["B"][key] == _first_h()[key]


@pytest.mark.parametrize(
    ("spoil", "message"),
    [
        (lambda rows: [row for row in rows if row["kind"] != "amendment"], "not run by this"),
        (lambda rows: [rows[0], {**rows[1], "tool_sha256": "0" * 64}, *rows[2:]], "another tool"),
        (lambda rows: [rows[0], {**rows[1], "inputs_sha256": "0" * 64}, *rows[2:]], "inputs_sha"),
        (lambda rows: [rows[0], {**rows[1], "rushallu_commit": "0" * 40}, *rows[2:]], "rushallu"),
        (lambda rows: [row for row in rows if row["kind"] != "start"], "not run by|no segment"),
    ],
)
def test_part_one_refuses_a_segment_not_the_amendments_or_not_on_hs_answers(
    tmp_path, spoil, message
):
    _write(tmp_path / "parity-B.json", {"passed": True})
    _write_jsonl(tmp_path / "scores-B.jsonl", spoil(_b_rows()))
    with pytest.raises(SystemExit, match=message):
        am.base(tmp_path)


# --- Part 2: the inputs ------------------------------------------------------------------------


def _v5_world(tmp_path, monkeypatch, size=3):
    """A replay summary, V5's judge rows and the answers found in the runs, SIZE of each."""
    monkeypatch.setattr(am, "FRESH_PLANNED", size)
    monkeypatch.setattr(am, "V5_SUMMARY", tmp_path / "v5-aircargo")
    monkeypatch.setattr(am, "V5_JUDGE", tmp_path / "v5-aircargo-judge")
    summary, judged, found = [], [], {}
    for index in range(size):
        run, case = f"v5-aircargo-b{index % 2 + 1:02d}", f"case-{index}"
        prompt = f"{index:064x}"
        summary.append({"run": run, "case_id": case, "v5_prompt_sha256": prompt})
        grade = ("bad", "good", "partial_ok")[index % 3]
        judged.append(
            {
                "run": run,
                "case_id": case,
                "item_id": f"item-{index}",
                "prompt_sha256": prompt,
                "missing": False,
                "grade": grade,
                "answers_question": "full",
            }
        )
        found[(run, case)] = {
            "case_id": case,
            "question": f"Вопрос {index}?",
            "prompt_sha256": prompt,
            "answer": f"Ответ {index} [1]. «Цитата» [2].",
            "documents": [("[1]", f"Документ {index}"), ("[2]", "Второй")],
        }
    _write_jsonl(tmp_path / "v5-aircargo.cases.jsonl", summary)
    _write_jsonl(tmp_path / "v5-aircargo-judge.cases.jsonl", list(reversed(judged)))
    return summary, judged, found


def _message(answer):
    return ec.digest(
        ec.judge.build_message(answer["question"], answer["documents"], answer["answer"], None)
    )


def test_the_fresh_answers_are_v5s_in_the_replays_order_with_v5s_judges_classes(
    tmp_path, monkeypatch
):
    summary, _, found = _v5_world(tmp_path, monkeypatch)
    got = am.fresh_inputs(found)
    assert [row["id"] for row in got] == [f"{row['run']}/{row['case_id']}" for row in summary]
    assert [row["class"] for row in got] == ["target", "good", None]
    assert [row["item_id"] for row in got] == ["item-0", "item-1", "item-2"]
    assert {row["set"] for row in got} == {"fresh"}
    assert got[0]["answer"] == "Ответ 0. «Цитата»."
    assert got[0]["documents"] == ["Документ 0", "Второй"]
    first = found[("v5-aircargo-b01", "case-0")]
    assert got[0]["answer_sha256"] == ec.digest(first["answer"])
    assert got[0]["message_sha256"] == _message(first)
    assert [row["verdict_missing"] for row in got] == [False, False, False]


def test_an_empty_answer_is_a_target_and_a_missing_verdict_unclassed(tmp_path, monkeypatch):
    summary, judged, found = _v5_world(tmp_path, monkeypatch)
    judged[1] = {**judged[1], "missing": True, "grade": None}
    del judged[1]["answers_question"]
    judged[2] = {**judged[2], "empty_answer": True, "grade": "bad"}
    del judged[2]["answers_question"]
    found[(summary[2]["run"], summary[2]["case_id"])]["answer"] = ""
    _write_jsonl(tmp_path / "v5-aircargo-judge.cases.jsonl", judged)
    got = am.fresh_inputs(found)
    assert [row["class"] for row in got] == ["target", None, "target"]
    assert [row["verdict_missing"] for row in got] == [False, True, False]
    assert got[2]["message_sha256"] is None and got[2]["answer"] == ""


@pytest.mark.parametrize(
    ("spoil", "message"),
    [
        (lambda s, j, f: f.pop(next(iter(f))), "differ in size"),
        (lambda s, j, f: j.append(dict(j[0])), "differ in size"),
        (lambda s, j, f: j[2].update(prompt_sha256="f" * 64), "another prompt"),
        (lambda s, j, f: s[0].update(v5_prompt_sha256="e" * 64), "another prompt"),
        (lambda s, j, f: j[0].update(empty_answer=True), "empty answer is not the run's"),
        (lambda s, j, f: j[0].update(case_id="case-9"), "no answer, or no judge row"),
    ],
)
def test_the_fresh_answers_refuse_what_is_not_the_replays_or_its_judges(
    tmp_path, monkeypatch, spoil, message
):
    summary, judged, found = _v5_world(tmp_path, monkeypatch)
    spoil(summary, judged, found)
    _write_jsonl(tmp_path / "v5-aircargo.cases.jsonl", summary)
    _write_jsonl(tmp_path / "v5-aircargo-judge.cases.jsonl", judged)
    with pytest.raises(SystemExit, match=message):
        am.fresh_inputs(found)


def test_the_fresh_answers_are_every_answer_of_v5s_aircargo_runs_once(tmp_path, monkeypatch):
    for name in ("v5-aircargo-b01", "v5-aircargo-b02", "v5-wixqa-b01"):
        (tmp_path / name).mkdir()
    (tmp_path / "v5-aircargo-b03").write_text("not a run", encoding="utf-8")
    seen = []

    def answers(run):
        seen.append(run.name)
        return [{"case_id": f"{run.name}-a"}, {"case_id": "shared"}]

    monkeypatch.setattr(am.ec.judge, "run_answers", answers)
    got = am.v5_answers(tmp_path)
    assert seen == ["v5-aircargo-b01", "v5-aircargo-b02"] and len(got) == 4
    monkeypatch.setattr(am.ec.judge, "run_answers", lambda run: [{"case_id": "x"}] * 2)
    with pytest.raises(SystemExit, match="two answers"):
        am.v5_answers(tmp_path)


@pytest.mark.parametrize(
    ("summary", "judged", "why"),
    [
        (None, {"status": "counted"}, "no V5 aircargo answers"),
        ({"whole": False}, {"status": "counted"}, "not whole"),
        ({"whole": True}, None, "no V5 aircargo judge record"),
        ({"whole": True}, {"status": ec.NOT_EVIDENCE}, "plan is not counted"),
        ({"whole": True}, {"status": "counted"}, None),
    ],
)
def test_part_two_reads_only_whole_answers_under_a_counted_plan(
    tmp_path, monkeypatch, summary, judged, why
):
    monkeypatch.setattr(am, "V5_SUMMARY", tmp_path / "v5-aircargo")
    monkeypatch.setattr(am, "V5_JUDGE", tmp_path / "v5-aircargo-judge")
    if summary is not None:
        _write(tmp_path / "v5-aircargo.json", summary)
    if judged is not None:
        _write(tmp_path / "v5-aircargo-judge.json", judged)
    got = am.readable()
    assert got == why if why is None else why in got


# --- Part 2: the writer ------------------------------------------------------------------------


class _Clock:
    """perf_counter for the writer: every answer takes STEP seconds."""

    def __init__(self, step):
        self.now, self.step, self.calls = 0.0, step, 0

    def perf_counter(self):
        self.calls += 1
        if self.calls % 2 == 0:
            self.now += self.step
        return self.now


@pytest.fixture
def writer(tmp_path, monkeypatch):
    """fresh()'s world: four answers to score, a fake model, a clock of 40 s an answer."""
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "model.safetensors").write_bytes(b"weights")
    todo = [
        {
            "set": "fresh",
            "base": "aircargo",
            "id": f"run/case-{index}",
            "class": ("target", "good", None, "target")[index],
            "answer": "" if index == 3 else f"Ответ {index}. Второе.",
            "documents": [f"Документ {index}"],
            "item_id": f"item-{index}",
            "verdict_missing": index == 2,
            "answer_sha256": f"{index:064x}",
            "message_sha256": None if index == 3 else f"{index + 10:064x}",
        }
        for index in range(4)
    ]
    scored = []

    def scorer(tokenizer, model, documents, text):
        scored.append(text)
        return (0.25 if text else None), 2, 50, 0

    monkeypatch.setattr(am, "readable", lambda: None)
    monkeypatch.setattr(am, "fresh_inputs", lambda: todo)
    monkeypatch.setattr(am, "fresh_hashes", lambda: {"judge": "j" * 64})
    monkeypatch.setattr(am, "versions", lambda: {"torch": "t", "transformers": "x"})
    monkeypatch.setattr(am, "time", _Clock(40.0))
    monkeypatch.setattr(am.ec, "snapshot", lambda name: snapshot)
    monkeypatch.setattr(am.ec, "load", lambda name: (None, None))
    monkeypatch.setattr(am.ec, "git_head", lambda: "head")
    monkeypatch.setitem(am.ec.SCORERS, "H", scorer)
    return todo, scored


def test_the_fresh_writer_scores_each_answer_once_and_ties_it_to_its_request(tmp_path, writer):
    todo, scored = writer
    am.fresh("H", tmp_path / "out")
    rows = ec.load_jsonl(tmp_path / "out/fresh-H.jsonl")
    assert [row["kind"] for row in rows] == ["start", "answer", "answer", "answer", "answer", "end"]
    start, answers = rows[0], rows[1:5]
    assert start["checker"] == "H" and start["planned"] == 4 and start["resumed_after"] == 0
    assert start["forecast_min"] == 25 and start["inputs"] == {"judge": "j" * 64}
    assert start["registered_sha256"] == am.REGISTERED_SHA256
    assert start["inputs_sha256"] == ec.digest(json.dumps(todo, ensure_ascii=False, sort_keys=True))
    for row, entry in zip(answers, todo, strict=True):
        for key in ("id", "class", "item_id", "verdict_missing", "answer_sha256", "message_sha256"):
            assert row[key] == entry[key]
    assert [row["score"] for row in answers] == [0.25, 0.25, 0.25, None]
    assert all(row["seconds"] == 40.0 for row in answers) and rows[-1]["stopped"] is False
    assert len(scored) == 4


def test_the_fresh_writer_resumes_a_file_and_stops_at_three_times_its_forecast(
    tmp_path, monkeypatch, writer
):
    todo, scored = writer
    out = tmp_path / "out"
    out.mkdir()
    done = {"kind": "answer", "id": todo[0]["id"], "seconds": 40.0}
    _write_jsonl(out / "fresh-H.jsonl", [{"kind": "start"}, done])
    monkeypatch.setitem(am.FRESH_FORECAST_MIN, "H", 1)  # stop past 180 s
    am.fresh("H", out)
    rows = ec.load_jsonl(out / "fresh-H.jsonl")
    assert rows[2]["kind"] == "start" and rows[2]["resumed_after"] == 1
    assert [row["id"] for row in rows[3:] if row["kind"] == "answer"] == [
        todo[1]["id"],
        todo[2]["id"],
        todo[3]["id"],
    ]
    monkeypatch.setitem(am.FRESH_FORECAST_MIN, "H", 0.5)  # stop past 90 s: 80 then 120 spent
    _write_jsonl(out / "fresh-H.jsonl", [{"kind": "start"}, done])
    am.fresh("H", out)
    rows = ec.load_jsonl(out / "fresh-H.jsonl")
    assert rows[-1] == {**rows[-1], "kind": "end", "stopped": True}
    assert sum(1 for row in rows if row["kind"] == "answer") == 3
    with pytest.raises(SystemExit, match="not resumed"):
        am.fresh("H", out)


def test_the_fresh_writer_scores_nothing_when_part_two_cannot_read(tmp_path, monkeypatch, writer):
    monkeypatch.setattr(am, "readable", lambda: "no V5 aircargo answers")
    with pytest.raises(SystemExit, match="NOT_EVIDENCE: no V5 aircargo answers"):
        am.fresh("H", tmp_path / "out")
    assert not (tmp_path / "out").exists()


# --- Part 2: the record ------------------------------------------------------------------------


def _fresh_rows(name, targets, goods, caught, over, planned=None, inputs=None):
    """A checker's fresh rows: TARGETS and GOODS answers, the first CAUGHT and OVER scoring low,
    and one unclassed answer whose verdict is missing."""
    answers = []
    for index in range(targets):
        answers.append(("target", 0.1 if index < caught else 0.9))
    for index in range(goods):
        answers.append(("good", 0.1 if index < over else 0.9))
    answers.append((None, 0.1))
    start = {
        "kind": "start",
        "checker": name,
        "revision": ec.CHECKERS[name]["revision"],
        **am.tools(),
        "weights_sha256": "b" * 64,
        "inputs": {} if inputs is None else inputs,
        "inputs_sha256": "c" * 64,
        "planned": len(answers) if planned is None else planned,
        "load": [1.0, 1.0, 1.0],
    }
    rows = [start]
    for index, (cls, score) in enumerate(answers):
        rows.append(
            {
                "kind": "answer",
                "set": "fresh",
                "base": "aircargo",
                "id": f"run/case-{index}",
                "class": cls,
                "item_id": f"item-{index}",
                "verdict_missing": cls is None,
                "answer_sha256": "d" * 64,
                "message_sha256": f"{index:064x}",
                "score": score,
                "sentences": 2,
                "units": 2,
                "tokens": 100,
                "truncated": 0,
                "seconds": 1.0 + index % 3,
            }
        )
    rows.append({"kind": "end", "stopped": False, "peak_rss_bytes": 10**9, "load": [1, 1, 1]})
    return rows


def test_the_fresh_read_is_the_frozen_reading_at_the_frozen_threshold():
    got = am.fresh_record(_fresh_rows("H", 15, 60, 12, 10), 0.5)
    assert got["reading"] == {
        "caught": 12,
        "target": 15,
        "over_marked": 10,
        "good_not_declining": 60,
        "reading": "worth wiring",
    }
    # Goods above targets: 50 high over 12 low; ties a half: 10 low with 12 low, 50 high with 3.
    assert got["auroc"] == pytest.approx((50 * 12 + 0.5 * (10 * 12 + 50 * 3)) / (60 * 15))
    assert got["threshold"] == 0.5 and got["not_evidence_because"] == []
    assert got["unclassed"] == 1 and got["verdict_missing"] == 1 and got["reached"] == 76
    assert am.fresh_record(_fresh_rows("H", 15, 60, 12, 10), 0.05)["reading"]["caught"] == 0
    assert am.fresh_record(_fresh_rows("H", 15, 60, 12, 10), None)["reading"]["reading"] == (
        "useless"
    )


@pytest.mark.parametrize(
    ("rows", "because"),
    [
        (_fresh_rows("L", 9, 60, 8, 0), "fewer than 10 targets or 30 good"),
        (_fresh_rows("L", 15, 29, 12, 0), "fewer than 10 targets or 30 good"),
        (_fresh_rows("L", 15, 60, 12, 0, planned=100), "did not reach every answer"),
    ],
)
def test_the_fresh_read_is_not_evidence_when_short_or_not_every_answer_scored(rows, because):
    got = am.fresh_record(rows, 0.5)
    assert got["reading"] == ec.NOT_EVIDENCE
    assert any(because in reason for reason in got["not_evidence_because"])


def _read(caught, over, reading, median=2.0):
    return {
        "reading": {"caught": caught, "over_marked": over, "reading": reading},
        "seconds": {"median": median},
    }


def test_worth_wiring_needs_the_fresh_read_and_a_v4_read_neither_useless_nor_missing():
    v4 = {
        "H": {"reading": "in between"},
        "L": {"reading": "useless"},
        "N": {"reading": "in between"},
        "B": ec.NOT_EVIDENCE,
    }
    fresh = {
        "H": _read(12, 9, "worth wiring", 3.0),
        "L": _read(14, 5, "worth wiring"),
        "N": _read(12, 9, "worth wiring", 2.0),
        "B": _read(15, 1, "worth wiring"),
    }
    assert am.confirm_outcome(fresh, v4) == {
        "decision": "worth wiring: N",
        "worth_wiring": "N",
        "held_back": ["L", "B"],
    }
    fresh["N"] = _read(12, 10, "worth wiring", 1.0)
    assert am.confirm_outcome(fresh, v4)["worth_wiring"] == "H"
    only = {"H": _read(5, 3, "in between"), "L": _read(14, 5, "worth wiring")}
    assert am.confirm_outcome(only, v4) == {
        "decision": "in between: H, L",
        "worth_wiring": None,
        "held_back": ["L"],
    }
    missing = {"H": _read(5, 3, "in between"), "N": {"reading": ec.NOT_EVIDENCE}}
    assert am.confirm_outcome(missing, v4)["decision"] == f"{ec.NOT_EVIDENCE}: N"
    none = {"H": _read(1, 3, "useless"), "N": _read(0, 0, "useless")}
    assert am.confirm_outcome(none, v4) == {
        "decision": "none worth wiring",
        "worth_wiring": None,
        "held_back": [],
    }


@pytest.fixture
def confirming(tmp_path, monkeypatch):
    """Part 2's committed world: the first record, a base record holding B at 0.42, V5's summary
    and judge records, the judge's plan, and the four checkers' fresh rows."""
    base = tmp_path / "base"
    base.mkdir()
    b_entry = {"threshold": {"threshold": 0.42}, "reading": {"reading": "in between"}}
    _write(base / "record.json", {"checkers": {"B": b_entry}})
    monkeypatch.setattr(am, "BASE", base)
    _v5_world(tmp_path, monkeypatch)
    rows = _fresh_rows("H", 15, 60, 12, 10)
    items = [
        {"item_id": row["item_id"], "run": "run", "case_id": row["id"].split("/")[1]}
        | {"message_sha256": row["message_sha256"]}
        for row in rows
        if row["kind"] == "answer"
    ]
    items.append({**items[0], "item_id": "item-0-retest", "retest_of": "item-0"})
    plan = tmp_path / "plan.json"
    _write(plan, {"items": items})
    _write(tmp_path / "v5-aircargo.json", {"whole": True})
    _write(
        tmp_path / "v5-aircargo-judge.json",
        {"status": "counted", "provenance": {"plan_sha256": ec.sha256(plan)}},
    )
    out = tmp_path / "fresh"
    out.mkdir()
    inputs = am.fresh_hashes()
    for name in am.FOUR:
        _write_jsonl(out / f"fresh-{name}.jsonl", _fresh_rows(name, 15, 60, 12, 10, inputs=inputs))
    return out, plan, items


def test_part_two_reads_each_checker_at_the_threshold_its_record_froze(confirming):
    out, plan, _ = confirming
    first = json.loads((am.FIRST / "record.json").read_text(encoding="utf-8"))
    got = am.confirm(out, plan)
    for name in ("H", "L", "N"):
        assert (
            got["checkers"][name]["threshold"] == first["checkers"][name]["threshold"]["threshold"]
        )
        assert got["v4_reading"][name] == first["checkers"][name]["reading"]
    assert got["checkers"]["B"]["threshold"] == 0.42
    assert got["decision"].startswith("worth wiring: ") and got["plan_linked"] is True
    assert got["inputs"]["first record"] == ec.sha256(am.FIRST / "record.json")
    assert got["part"] == 2 and got["amendment"] == 1
    assert json.loads((out / "record.json").read_text(encoding="utf-8")) == json.loads(
        json.dumps(got, ensure_ascii=False)
    )


def _spoil_start(out, name, **change):
    rows = ec.load_jsonl(out / f"fresh-{name}.jsonl")
    rows[0] = {**rows[0], **change}
    _write_jsonl(out / f"fresh-{name}.jsonl", rows)


def _spoil_answer(out, name, **change):
    rows = ec.load_jsonl(out / f"fresh-{name}.jsonl")
    rows[3] = {**rows[3], **change}
    _write_jsonl(out / f"fresh-{name}.jsonl", rows)


@pytest.mark.parametrize(
    ("spoil", "message"),
    [
        (lambda out, plan: (out / "fresh-N.jsonl").unlink(), "no fresh scores of N"),
        (lambda out, plan: _spoil_start(out, "L", checker="H"), "another checker or tool"),
        (lambda out, plan: _spoil_start(out, "B", registered_sha256="0" * 64), "another checker"),
        (lambda out, plan: _spoil_start(out, "H", inputs={"judge": "0" * 64}), "other inputs"),
        (lambda out, plan: _spoil_start(out, "B", inputs_sha256="0" * 64), "different answers"),
        (lambda out, plan: _spoil_answer(out, "N", message_sha256="0" * 64), "another answer"),
        (lambda out, plan: _spoil_answer(out, "N", item_id="item-99"), "not a request"),
        (lambda out, plan: _spoil_answer(out, "H", id="run/case-7"), "not a request"),
        (lambda out, plan: plan.write_text("{}", encoding="utf-8"), "not the plan"),
    ],
)
def test_part_two_refuses_rows_not_on_the_records_inputs_or_the_judges_requests(
    confirming, spoil, message
):
    out, plan, _ = confirming
    spoil(out, plan)
    with pytest.raises(SystemExit, match=message):
        am.confirm(out, plan)
    assert not (out / "record.json").exists()


def test_part_two_is_not_evidence_without_whole_answers_under_a_counted_plan(confirming, tmp_path):
    out, plan, _ = confirming
    for path in out.iterdir():
        path.unlink()
    _write(tmp_path / "v5-aircargo-judge.json", {"status": ec.NOT_EVIDENCE})
    got = am.confirm(out, plan)
    assert got["decision"] == f"{ec.NOT_EVIDENCE}: V5's aircargo judge plan is not counted"
    assert got["worth_wiring"] is None and "checkers" not in got
    assert json.loads((out / "record.json").read_text(encoding="utf-8")) == got


def test_the_spec_registers_the_amendment_as_the_tool_holds_it():
    spec = " ".join((ROOT / ec.SPEC).read_text(encoding="utf-8").split())
    assert "## Amendment 1, 2026-10-26: Horizon guard base, then fresh answers" in spec
    assert "Registered before B's first call and before V5's first aircargo answer" in spec
    assert f"`{am.REGISTERED_SHA256}`" in spec
    amendment = hashlib.sha256((TOOLS / "encoder_checkers_amend.py").read_bytes()).hexdigest()
    assert f"`{amendment}`" in spec
    assert ec.CHECKERS["B"]["repo"] in spec and ec.CHECKERS["B"]["revision"][:8] in spec
    assert "fewer than 10 targets or 30 good" in spec
    assert "neither useless nor NOT_EVIDENCE" in spec and "held back" in spec
    assert "an empty answer is a target" in spec and "a missing verdict leaves it unclassed" in spec
    assert "H ≈ 25 min, L ≈ 15, N ≈ 50, B ≈ 80" in spec
    assert "B's forecast 200 min (stop at 600)" in spec
    assert "encoder_checkers_amend.py" in spec and "tests/test_encoder_checkers_amend.py" in spec
