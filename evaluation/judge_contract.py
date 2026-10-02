"""Version 2 relevance requests and labels; the archived P2 v1 source stays pinned."""

from __future__ import annotations

import json
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from evaluation.blinded_judge import (
    INSTRUCTION,
    SEED,
    ParseFailure,
    _append_store,
    _first_object,
    _sha256_text,
    read_store,
)


@dataclass(frozen=True)
class RequestV2:
    case_id: str
    text: str
    documents: tuple[dict[str, Any], ...]
    question_hash: str
    rubric_version: str
    judge_version: str
    request_key: str
    request_sha256: str
    request_version: int = 2


@dataclass(frozen=True)
class GradeOutcome:
    status: Literal["valid", "invalid", "absent"]
    grades: dict[str, int]
    reason: str = ""


def _validate_chunk_address(address: object) -> Mapping[str, Any]:
    if not isinstance(address, Mapping):
        raise ValueError("chunk address must be an object")
    for field in ("source_id", "source_revision", "chunker_version"):
        if not isinstance(address.get(field), str) or not address[field].strip():
            raise ValueError(f"chunk address requires {field}")
    section = address.get("section_path")
    if section is not None:
        if isinstance(section, str) and section.strip():
            return address
        if (
            isinstance(section, list)
            and section
            and all(isinstance(part, str) and part.strip() for part in section)
        ):
            return address
        raise ValueError("chunk address has invalid section_path")
    start, end = address.get("char_start"), address.get("char_end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise ValueError("chunk address requires section_path or char_start/char_end")
    return address


def build_request_v2(
    *,
    case_id: str,
    question: str,
    documents: Sequence[Mapping[str, Any]],
    judge_version: str,
    rubric_version: str = "p2-0-3-v1",
) -> RequestV2:
    if not 1 <= len(documents) <= 10:
        raise ValueError("a v2 request must present 1 to 10 documents")
    if not case_id.strip() or not rubric_version.strip() or not judge_version.strip():
        raise ValueError("case, rubric and judge versions must be nonempty")
    prepared: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for document in documents:
        text = document.get("text")
        if not isinstance(text, str):
            raise ValueError("document text must be a string")
        text_hash = _sha256_text(text)
        if "text_sha256" in document and document["text_sha256"] != text_hash:
            raise ValueError("document text_sha256 does not match the exact text")
        if text_hash in hashes:
            raise ValueError("duplicate document text_sha256")
        hashes.add(text_hash)
        address = _validate_chunk_address(document.get("address"))
        prepared.append({"text": text, "text_sha256": text_hash, "address": dict(address)})
    prepared.sort(key=lambda document: document["text_sha256"])
    random.Random(f"{SEED}:v2:{case_id}").shuffle(prepared)
    instruction = INSTRUCTION.replace(
        "five objects with doc (D1 through D5)",
        f"{len(prepared)} objects with doc (D1 through D{len(prepared)})",
    )
    prompt = (
        instruction
        + "\n\nQuestion\n"
        + question
        + "\n\n"
        + "\n\n".join(
            f"D{position}\n{document['text']}" for position, document in enumerate(prepared, 1)
        )
    )
    question_hash = _sha256_text(question)
    key_fields = {
        "request_version": 2,
        "question_hash": question_hash,
        "text_sha256": [document["text_sha256"] for document in prepared],
        "rubric_version": rubric_version,
        "judge_version": judge_version,
    }
    request_key = _sha256_text(
        json.dumps(key_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return RequestV2(
        case_id,
        prompt,
        tuple(prepared),
        question_hash,
        rubric_version,
        judge_version,
        request_key,
        _sha256_text(prompt),
    )


def parse_grades_v2(text: str | None, labels: Sequence[str]) -> GradeOutcome:
    if text is None or not text.strip():
        return GradeOutcome("absent", {}, "empty_reply")
    try:
        obj = _first_object(text)
    except ParseFailure:
        return GradeOutcome("invalid", {}, "no_json")
    if not isinstance(obj, dict) or not isinstance(obj.get("grades"), list):
        return GradeOutcome("invalid", {}, "missing_label")
    result: dict[str, int] = {}
    expected = set(labels)
    for row in obj["grades"]:
        if not isinstance(row, dict) or not isinstance(row.get("doc"), str):
            return GradeOutcome("invalid", {}, "missing_label")
        label, grade = row["doc"], row.get("grade")
        if label not in expected:
            return GradeOutcome("invalid", {}, "extra_label")
        if label in result:
            return GradeOutcome("invalid", {}, "duplicate_label")
        if type(grade) is not int:
            return GradeOutcome("invalid", {}, "non_integer")
        if not 0 <= grade <= 3:
            return GradeOutcome("invalid", {}, "out_of_range")
        result[label] = grade
    if set(result) != expected:
        return GradeOutcome("invalid", {}, "missing_label")
    return GradeOutcome("valid", result)


def validate_grade_record(record: Mapping[str, Any]) -> None:
    required = {
        "case_id",
        "question_hash",
        "address",
        "text_sha256",
        "grade",
        "rubric_version",
        "judge_version",
        "request_key",
        "request_sha256",
    }
    if required - record.keys():
        raise ValueError("grade record is missing required fields")
    for field in ("question_hash", "text_sha256", "request_key", "request_sha256"):
        value = record[field]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError(f"grade record has malformed {field}")
    for field in ("case_id", "rubric_version", "judge_version"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f"grade record has invalid {field}")
    grade = record["grade"]
    if type(grade) is not int or not 0 <= grade <= 3:
        raise ValueError("grade record requires an integer grade in 0..3")
    _validate_chunk_address(record["address"])


def make_grade_records(request: RequestV2, outcome: GradeOutcome) -> list[dict[str, Any]]:
    if outcome.status != "valid":
        return []
    labels = [f"D{position}" for position in range(1, len(request.documents) + 1)]
    if set(outcome.grades) != set(labels):
        raise ValueError("grades do not match the presented labels")
    records = [
        {
            "case_id": request.case_id,
            "question_hash": request.question_hash,
            "address": document["address"],
            "text_sha256": document["text_sha256"],
            "grade": outcome.grades[label],
            "rubric_version": request.rubric_version,
            "judge_version": request.judge_version,
            "request_key": request.request_key,
            "request_sha256": request.request_sha256,
        }
        for label, document in zip(labels, request.documents, strict=True)
    ]
    for record in records:
        validate_grade_record(record)
    return records


def write_grade_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    for record in records:
        validate_grade_record(record)
    for record in records:
        _append_store(path, record)


def read_grade_records(path: Path, *, request_key: str | None = None) -> list[dict[str, Any]]:
    records = read_store(path)
    for record in records:
        validate_grade_record(record)
    return [
        record for record in records if request_key is None or record["request_key"] == request_key
    ]
