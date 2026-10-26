"""Stage 3: the handover signals on V4's 100 aircargo answers, derived again from the committed
records (docs/specs/handover-signal.md, 1.4)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/handover-signal/tools/signal_record.py"
RECORD_DIR = ROOT / "reports/handover-signal/d260d95"
RECORD = RECORD_DIR / "record.json"
JUDGE_CASES = ROOT / "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl"
QUESTIONS = ROOT / "evaluation/curated_cases_aircargo.jsonl"
CAPSULE = ROOT / "docs/evidence/handover-signal-v4-aircargo.md"
# The plan as committed before its first model call (b7ad62a), the code it ran at and the
# stand whose answers it reads.
PLAN_SHA = "30e0a598e6f6edabd7d72ac64b4ce4923655ed9845c5852f02107e345e9df16e"
CODE_SHA = "d260d95b749913d98193a89fb181490865ca42c4"
STAND_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
NO_MODEL = ("S1", "S1p", "S5", "S7", "S8")


def tool():
    spec = importlib.util.spec_from_file_location("signal_record", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def plan() -> dict:
    return json.loads((RECORD_DIR / "plan.json").read_text(encoding="utf-8"))


def answers() -> dict[int, dict]:
    return {
        row["item"]: row for row in load(RECORD_DIR / "signals.jsonl") if row["kind"] == "answer"
    }


def classes() -> dict[tuple[str, str], tuple[str, bool]]:
    return {
        (row["run"], row["case_id"]): (row["grade"], row["answers_question"] == "declined")
        for row in load(JUDGE_CASES)
    }


def wilson(hits: int, n: int) -> tuple[float, float]:
    z = 1.96
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mark(name: str, item: dict, row: dict, threshold: float | None) -> bool | None:
    if name == "S7":
        if threshold is None or item["S7"]["status"] != "ok":
            return None
        return item["S7"]["top_score"] < threshold
    if name in NO_MODEL:
        return item[name]
    return row[name]["marked"]


def test_the_record_is_the_tools_output_of_the_committed_records() -> None:
    built = tool().build(RECORD_DIR)
    assert built == record()
    for name, digest in record()["inputs"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    assert record()["inputs"]["reports/handover-signal/d260d95/plan.json"] == PLAN_SHA


def test_the_run_read_the_frozen_plan_at_its_code_with_the_4b() -> None:
    frozen, run = record()["plan"], record()["run"]
    assert (frozen["code_sha"], frozen["model"], frozen["answers_code_sha"]) == (
        CODE_SHA,
        MODEL,
        [STAND_SHA],
    )
    assert (run["code_sha"], run["served"], run["rag_env"]) == ([CODE_SHA], [MODEL], ["None"])
    assert run["answers"] == frozen["items"] == 100
    # One stop: answer 100 passed the cap under another project's load; resumed once, it
    # answered under the same cap (the plan's rule: one resume, the cap unchanged).
    assert [(stop["item"], stop["elapsed_sec"] > stop["cap_sec"]) for stop in run["stops"]] == [
        (100, True)
    ]
    rows = load(RECORD_DIR / "signals.jsonl")
    starts = [row["resumed_after"] for row in rows if row["kind"] == "start"]
    assert starts == [0, 99] and rows[-1]["kind"] == "end"
    assert answers()[100]["seconds"]["total"] < run["stops"][0]["cap_sec"]
    assert sorted(answers()) == list(range(1, 101))
    judged = {(row["run"], row["case_id"]): row["prompt_sha256"] for row in load(JUDGE_CASES)}
    assert {(i["run"], i["case_id"]): i["prompt_sha256"] for i in plan()["items"]} == judged


def test_the_rows_hold_no_question_or_answer_text() -> None:
    text = (RECORD_DIR / "signals.jsonl").read_text(encoding="utf-8")
    text += (RECORD_DIR / "plan.json").read_text(encoding="utf-8")
    for case in load(QUESTIONS):
        assert case["query"] not in text, case["case_id"]
    assert not any(row["node_errors"] for row in answers().values())


def test_each_signal_is_counted_again_from_the_rows() -> None:
    judged, rows = classes(), answers()
    threshold = record()["signals"]["S7"]["threshold"]
    for name, entry in record()["signals"].items():
        marks = [
            (
                judged[(item["run"], item["case_id"])],
                mark(name, item, rows[item["item"]], threshold),
            )
            for item in plan()["items"]
        ]
        known = [(cls, m) for cls, m in marks if m is not None]
        target = [m for (grade, declined), m in known if grade == "bad" or declined]
        good = [m for (grade, declined), m in known if grade == "good" and not declined]
        assert (entry["computed"], entry["marked"]) == (len(known), sum(m for _, m in known)), name
        assert (entry["target"], entry["caught"]) == (len(target), sum(target)), name
        assert (entry["good_not_declining"], entry["over_marked"]) == (len(good), sum(good)), name


def test_s7s_threshold_is_the_rules_choice() -> None:
    judged = classes()
    scored = [
        (item["S7"]["top_score"], judged[(item["run"], item["case_id"])])
        for item in plan()["items"]
    ]
    goods = sum(1 for _, (grade, declined) in scored if grade == "good" and not declined)
    table = []
    for threshold in sorted({score for score, _ in scored}):
        marked = [cls for score, cls in scored if score < threshold]
        caught = sum(1 for grade, declined in marked if grade == "bad" or declined)
        over = sum(1 for grade, declined in marked if grade == "good" and not declined)
        if 3 * over <= goods:
            table.append((-caught, threshold))
    best_caught, best = min(table)
    s7 = record()["signals"]["S7"]
    assert s7["threshold"] == (best if best_caught < 0 else None)
    assert s7["chosen_on_these_answers"]


def test_the_reading_is_applied_as_frozen() -> None:
    rec = record()
    assert rec["judged"]["target"] >= 15
    for name, entry in rec["signals"].items():
        if entry["computed"] == 0:
            assert entry["reading"] == "no threshold"
            continue
        low, high = wilson(entry["caught"], entry["target"])
        caught = entry["caught"] / entry["target"]
        over = entry["over_marked"] / entry["good_not_declining"]
        if caught >= 2 / 3 and low >= 1 / 3 and over <= 1 / 3:
            expected = "worth wiring"
        elif high < 1 / 2 or over > 1 / 2:
            expected = "useless"
        else:
            expected = "in between"
        assert entry["reading"] == expected, name
    for name in NO_MODEL:
        assert rec["signals"][name]["added_seconds_median"] == 0.0


def test_r2_and_r3_are_counted_on_the_claim_check() -> None:
    rows = list(answers().values())
    found = record()["findings"]
    vacuous = [
        row
        for row in rows
        if not row["S3"]["claims"]
        and row["S2"]["grounding_status"] == "verified"
        and row["S2"]["factuality"] == 0
    ]
    assert found["R2"]["verified_with_factuality_0"] == len(vacuous)
    assert found["R2"]["routed_not_auto"] == sum(row["S6"]["route"] != "auto" for row in vacuous)
    claims = [claim for row in rows for claim in row["S3"]["claims"]]
    assert (found["R3"]["claims"], found["R3"]["cited"]) == (
        len(claims),
        sum(bool(claim["cited"]) for claim in claims),
    )


LABELS = {
    "S1": "S1 self-score below 80",
    "S1p": "S1′ self-score below 100",
    "S2": "S2 the widget's claim check",
    "S3": "S3 the claim check's verdicts",
    "S4": "S4 the widget's relevance",
    "S5": "S5 a decline",
    "S6": "S6 the widget's first pass",
    "S7": "S7 rerank top below {threshold}",
    "S8": "S8 the answer's script",
}


def test_every_capsule_table_row_is_built_from_the_record() -> None:
    capsule = CAPSULE.read_text(encoding="utf-8")
    rec = record()
    for name, entry in rec["signals"].items():
        low, high = wilson(entry["caught"], entry["target"])
        seconds = entry["added_seconds_median"]
        added = "0" if seconds == 0 else f"{seconds:.1f}"
        label = LABELS[name].format(threshold=entry.get("threshold"))
        line = (
            f"| {label} | {entry['marked']} | {entry['caught']} ({low:.3f}–{high:.3f})"
            f" | {entry['over_marked']} | {added} | {entry['reading']} |"
        )
        assert line in capsule, line
    assert rec["outcome"] == {
        "outcome": "C",
        "worth_wiring": [],
        "candidates_for_stage_2": ["S3"],
        "in_between": ["S3"],
    }
    assert "**Outcome C.**" in capsule and "**in between** — S3" in capsule
    found = rec["findings"]
    assert f"{found['R3']['claims']} claims, {found['R3']['supported']} supported" in capsule
    assert f"{found['R3']['answers_marked_for_want_of_a_citation']} answers were marked" in capsule
    assert (rec["judged"]["target"], rec["judged"]["good_not_declining"]) == (17, 63)
