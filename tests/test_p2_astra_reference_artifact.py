"""Replay the published Astra sample grades from the saved raw replies."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from evaluation import blinded_judge as p2
from scripts.p2_astra_reference import MODEL, select_sample

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports/p2/astra-reference"
STORE = OUT / "replies.jsonl"
SUMMARY = OUT / "summary.json"
STORE_SHA256 = "6411f772c57629cb04118ba3e9892d1956b8c31db448229628fdf874458e5164"

pytestmark = pytest.mark.skipif(not SUMMARY.is_file(), reason="Astra reference run not published")


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


def test_ratings_and_summary_replay_the_published_sample() -> None:
    rows = p2.read_store(STORE)
    ratings = json.loads((OUT / "ratings.json").read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["complete"] is True
    assert (summary["graded_cases"], summary["graded_documents"]) == (10, 50)
    assert summary["reply_store_sha256"] == STORE_SHA256
    assert summary["model"] == MODEL and summary["effort"] == "xhigh"
    assert summary["instruction_sha256"] == p2.INSTRUCTION_SHA256
    assert len(ratings) == 10
    for row, rating in zip(rows, ratings, strict=True):
        parsed = p2.parse_grades(row["raw_text"], tuple(f"D{index}" for index in range(1, 6)))
        assert rating["grades"] == row["grades"]
        assert rating["presented_grades"] == [parsed[f"D{index}"] for index in range(1, 6)]
        assert rating["raw_text"] == row["raw_text"]
        assert rating["thread_id"] == row["usage"]["thread_id"]
    distribution = Counter(grade for rating in ratings for grade in rating["grades"])
    assert {str(grade): count for grade, count in distribution.items()} == summary[
        "grade_distribution"
    ]


def test_evidence_capsule_replays_table_hashes_and_kappas() -> None:
    capsule = (ROOT / "docs/evidence/p2-astra-reference-sample.md").read_text(encoding="utf-8")
    ratings = json.loads((OUT / "ratings.json").read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    table = []
    for line in capsule.splitlines():
        if line.startswith("| aircargo-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            table.append((cells[0], [int(grade) for grade in cells[1:]]))
    assert table == [(rating["case_id"], rating["presented_grades"]) for rating in ratings]

    distribution = Counter(grade for rating in ratings for grade in rating["grades"])
    assert "/".join(str(distribution[grade]) for grade in range(4)) in capsule
    for path in (STORE, OUT / "ratings.json", SUMMARY):
        assert hashlib.sha256(path.read_bytes()).hexdigest() in capsule
    assert all(rating.get("thread_id") for rating in ratings)
    assert summary.get("codex_cli_version")
    assert summary["codex_cli_version"] in capsule
    assert all(rating["thread_id"] in capsule for rating in ratings)

    case_ids = [rating["case_id"] for rating in ratings]
    astra = {rating["case_id"]: rating["grades"] for rating in ratings}
    references = [
        (
            "sonnet",
            lambda: {
                row["case_id"]: row["grades"]
                for row in p2.read_store(ROOT / "reports/p2/replies/sonnet.jsonl")
                if row.get("pool") == "H" and row.get("status") == "graded"
            },
            "Sonnet 5",
        ),
        (
            "glm",
            lambda: {
                row["case_id"]: row["grades"]
                for row in p2.read_store(ROOT / "reports/p2/replies/glm.jsonl")
                if row.get("pool") == "H" and row.get("status") == "graded"
            },
            "GLM 5.3",
        ),
        (
            "opus",
            lambda: {
                row["case_id"]: row["grades"]
                for row in json.loads(
                    (ROOT / "reports/p2/opus-reference/ratings.json").read_text(encoding="utf-8")
                )
            },
            "Opus 5.5",
        ),
    ]
    for _, load_reference, label in references:
        other = load_reference()
        assert set(case_ids) <= set(other)
        first = [grade for case_id in case_ids for grade in astra[case_id]]
        second = [grade for case_id in case_ids for grade in other[case_id]]
        kappa = p2.quadratic_kappa(first, second)
        assert kappa is not None
        assert f"{kappa:.4f} against {label}" in capsule
