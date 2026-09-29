"""Replay the published Opus sample grades from the saved raw replies."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from evaluation import blinded_judge as p2
from scripts.p2_opus_reference import MODEL, select_sample

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports/p2/opus-reference"
STORE = OUT / "replies.jsonl"
STORE_SHA256 = "f17b1b973249365ba51a5e0c476024e7933de698ffeb2cf29b32ea1ff1aa3a8f"


def test_raw_replies_cover_the_exact_blind_sample() -> None:
    raw = STORE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == STORE_SHA256
    assert b"\r\n" not in raw
    rows = p2.read_store(STORE)
    sample = select_sample(p2.load_inputs())
    assert len(rows) == len(sample) == 10
    assert all(row["status"] == "graded" and row["model"] == MODEL for row in rows)
    for case, row in zip(sample, rows, strict=True):
        request = p2.build_request(case)
        assert (row["pool"], row["case_id"], row["request_sha256"]) == (
            case.pool,
            case.case_id,
            request.sha256,
        )
        parsed = p2.parse_grades(row["raw_text"], tuple(f"D{index}" for index in range(1, 6)))
        replayed = [0] * 5
        for position, original_index in enumerate(request.order, 1):
            replayed[original_index] = parsed[f"D{position}"]
        assert row["grades"] == replayed
        reply = p2._first_object(row["raw_text"])
        assert len(reply["grades"]) == 5
        assert all(
            isinstance(grade["reason"], str) and grade["reason"].strip()
            for grade in reply["grades"]
        )


def test_ratings_show_the_blind_d1_to_d5_order() -> None:
    rows = p2.read_store(STORE)
    ratings = json.loads((OUT / "ratings.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    assert summary["complete"] is True
    assert (summary["graded_cases"], summary["graded_documents"]) == (10, 50)
    assert summary["reply_store_sha256"] == STORE_SHA256
    assert summary["model"] == MODEL and summary["effort"] == "max"
    assert summary["instruction_sha256"] == p2.INSTRUCTION_SHA256
    assert len(ratings) == 10
    for row, rating in zip(rows, ratings, strict=True):
        parsed = p2.parse_grades(row["raw_text"], tuple(f"D{index}" for index in range(1, 6)))
        assert rating["grades"] == row["grades"]
        assert rating["presented_grades"] == [parsed[f"D{index}"] for index in range(1, 6)]
        assert rating["raw_text"] == row["raw_text"]
    distribution = Counter(grade for rating in ratings for grade in rating["grades"])
    assert {str(grade): count for grade, count in distribution.items()} == summary[
        "grade_distribution"
    ]


def test_evidence_capsule_replays_the_published_numbers() -> None:
    capsule = (ROOT / "docs/evidence/p2-opus-reference-sample.md").read_text(encoding="utf-8")
    ratings = json.loads((OUT / "ratings.json").read_text(encoding="utf-8"))
    table = []
    for line in capsule.splitlines():
        if line.startswith("| aircargo-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            table.append((cells[0], [int(grade) for grade in cells[1:]]))
    assert table == [(rating["case_id"], rating["presented_grades"]) for rating in ratings]

    distribution = Counter(grade for rating in ratings for grade in rating["grades"])
    assert "/".join(str(distribution[grade]) for grade in range(4)) in capsule
    assert f"{distribution[2] + distribution[3]}/50" in capsule
    assert f"{sum(3 in rating['grades'] for rating in ratings)}/10" in capsule
    for path in (STORE, OUT / "ratings.json", OUT / "summary.json"):
        assert hashlib.sha256(path.read_bytes()).hexdigest() in capsule

    case_ids = [rating["case_id"] for rating in ratings]
    opus = {rating["case_id"]: rating["grades"] for rating in ratings}
    for judge, label in (("sonnet", "Sonnet 5"), ("glm", "GLM 5.3")):
        other = {
            row["case_id"]: row["grades"]
            for row in p2.read_store(ROOT / f"reports/p2/replies/{judge}.jsonl")
            if row.get("pool") == "H" and row.get("status") == "graded"
        }
        assert set(case_ids) <= set(other)
        first = [grade for case_id in case_ids for grade in opus[case_id]]
        second = [grade for case_id in case_ids for grade in other[case_id]]
        kappa = p2.quadratic_kappa(first, second)
        assert kappa is not None
        assert f"{kappa:.4f} against {label}" in capsule
