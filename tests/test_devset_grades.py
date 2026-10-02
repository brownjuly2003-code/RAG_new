from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import devset, judge_contract


@pytest.fixture
def grade_fixture(tmp_path: Path) -> tuple[Path, list[dict[str, Any]]]:
    set_path = tmp_path / "cases.jsonl"
    question = "  Exact question?\n"
    set_path.write_text(
        json.dumps({"case_id": "case-1", "question": question}) + "\n", encoding="utf-8"
    )
    request = judge_contract.build_request_v2(
        case_id="case-1",
        question=question,
        judge_version="fixture-v1",
        documents=[
            {
                "text": "Retrieved text outside the gold documents.",
                "address": {
                    "source_id": "retrieved",
                    "source_revision": "revision",
                    "section_path": "section",
                    "chunker_version": "v1",
                },
            }
        ],
    )
    records = judge_contract.make_grade_records(
        request, judge_contract.parse_grades_v2('{"grades":[{"doc":"D1","grade":3}]}', ["D1"])
    )
    return set_path, records


def test_valid_contract_records_round_trip(
    grade_fixture: tuple[Path, list[dict[str, Any]]],
) -> None:
    set_path, records = grade_fixture
    assert devset.grades_path(set_path) == set_path.with_name("cases.grades.jsonl")
    devset.write_devset_grades(set_path, records)
    assert judge_contract.read_grade_records(devset.grades_path(set_path)) == records
    assert devset.read_devset_grades(set_path) == records


@pytest.mark.parametrize(("field", "value"), [("case_id", "foreign"), ("question_hash", "0" * 64)])
def test_bad_binding_refused_before_writing_and_on_read(
    grade_fixture: tuple[Path, list[dict[str, Any]]], field: str, value: str
) -> None:
    set_path, records = grade_fixture
    bad = {**records[0], field: value}
    with pytest.raises(ValueError, match=field):
        devset.write_devset_grades(set_path, records + [bad])
    assert not devset.grades_path(set_path).exists()
    devset.write_devset_grades(set_path, records)
    before = devset.grades_path(set_path).read_bytes()
    with pytest.raises(ValueError, match=field):
        devset.write_devset_grades(set_path, records + [bad])
    assert devset.grades_path(set_path).read_bytes() == before
    judge_contract.write_grade_records(devset.grades_path(set_path), [bad])
    with pytest.raises(ValueError, match=field):
        devset.read_devset_grades(set_path)


def test_missing_grades_file_is_empty(grade_fixture: tuple[Path, list[dict[str, Any]]]) -> None:
    assert devset.read_devset_grades(grade_fixture[0]) == []
