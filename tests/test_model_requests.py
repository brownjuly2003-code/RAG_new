"""`scripts/model_requests.py`: what a run asked the model, read from a replay cache."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import model_requests as tool

IDENTITY = {"digest": "d1", "model": "grader", "provider": "Recorded"}
ROLE = {"max_tokens": 256, "temperature": 0.0, "tools": None}
BATCH_SCHEMA = {"type": "object", "properties": {"grades": {"type": "array"}}}
DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {"relevant": {"type": "boolean"}, "reason": {"type": "string"}},
}
ONE_GRADE = {"grades": [{"index": 1, "relevant": True, "reason": "about"}]}
BATCH = (
    "Вопрос: срок\n[1] source=a.md\nпервый текст\n[2] source=b.md\nвторой текст\n"
    "[3] source=c.md\nтретий текст\n[4] source=d.md\nещё текст\nВерни только JSON"
)
FIRST, SECOND, THIRD, FOURTH, FIFTH = (f"Вопрос: срок\nДокумент: {n}" for n in range(1, 6))
REWRITE = "Перепиши вопрос: срок"


def _entry(
    prompt: str,
    *,
    schema: dict[str, Any] | None = None,
    text: str = "",
    structured: Any = None,
    invalid: bool = False,
    latency: float = 1000.0,
) -> dict[str, Any]:
    """One entry of a replay cache, as the collector's recorded provider writes it."""
    reply = {"text": text, "latency_ms": latency}
    value: dict[str, Any]
    if invalid:
        value = {
            "outcome": "structured_output_invalid",
            "error": {"message": "the reply is not JSON"},
            "raw_response": reply,
        }
    else:
        value = {"outcome": "response", "response": {**reply, "structured_output": structured}}
    return {
        "request": {
            "identity": IDENTITY,
            "method": "generate_with_schema" if schema else "generate",
            "messages": [{"role": "user", "content": prompt}],
            "schema": schema,
            "kwargs": {} if schema else ROLE,
        },
        "value": value,
    }


def _cache(folder: Path, entries: list[dict[str, Any]], *, manifest: bool = True) -> Path:
    cache = folder / "cache"
    cache.mkdir(parents=True)
    for number, entry in enumerate(entries):
        text = json.dumps(entry, ensure_ascii=False)
        (cache / f"llm-{number:02d}.json").write_text(text, encoding="utf-8")
    # A cache holds entries of other kinds too; they are not model requests.
    (cache / "rerank-00.json").write_text("{}", encoding="utf-8")
    if manifest:
        (folder / "manifest.json").write_text('{"run": "first"}', encoding="utf-8")
    return cache


def _first() -> list[dict[str, Any]]:
    """A context of four documents: the batch gives one grade twice, then each is asked."""
    return [
        _entry(
            BATCH,
            schema=BATCH_SCHEMA,
            text=json.dumps(ONE_GRADE),
            structured=ONE_GRADE,
            latency=2000.0,
        ),
        _entry(BATCH, text=f"```json\n{json.dumps(ONE_GRADE)}\n```", latency=1500.0),
        # A structured verdict.
        _entry(
            FIRST,
            schema=DOCUMENT_SCHEMA,
            text='{"relevant": true, "reason": "r"}',
            structured={"relevant": True, "reason": "r"},
        ),
        # A reply that is not JSON, and the document asked again as text.
        _entry(SECOND, schema=DOCUMENT_SCHEMA, text="NO", invalid=True),
        _entry(SECOND, text="NO", latency=500.0),
        # JSON without a verdict, and the document asked again as text.
        _entry(
            THIRD,
            schema=DOCUMENT_SCHEMA,
            text='{"relevant": "yes"}',
            structured={"relevant": "yes"},
        ),
        _entry(THIRD, text=" yes, the document answers", latency=500.0),
        # No verdict and no repeat: the grading of the document failed.
        _entry(FOURTH, schema=DOCUMENT_SCHEMA, text="", invalid=True),
        _entry(REWRITE, text="срок оплаты", latency=300.0),
    ]


def _second() -> list[dict[str, Any]]:
    """Another run on the same question: three of its documents are those of the first."""
    return [
        _entry(BATCH, schema=BATCH_SCHEMA, text="{}", structured={}),
        _entry(BATCH, text=f"```json\n{json.dumps(ONE_GRADE)}\n```"),
        _entry(
            FIRST,
            schema=DOCUMENT_SCHEMA,
            text='{"relevant": false, "reason": "r"}',
            structured={"relevant": False, "reason": "r"},
        ),
        _entry(SECOND, schema=DOCUMENT_SCHEMA, text="NO", invalid=True),
        _entry(SECOND, text="YES"),
        _entry(
            THIRD,
            schema=DOCUMENT_SCHEMA,
            text='{"relevant": true}',
            structured={"relevant": True},
        ),
        _entry(
            FIFTH,
            schema=DOCUMENT_SCHEMA,
            text='{"relevant": true}',
            structured={"relevant": True},
        ),
        _entry(REWRITE, text="срок оплаты"),
    ]


def _row(rows: list[dict[str, Any]], asks: str, route: str, prompt: str) -> dict[str, Any]:
    (found,) = [
        row
        for row in rows
        if (row["asks"], row["route"], row["prompt_sha256"]) == (asks, route, tool.digest(prompt))
    ]
    return found


def test_extract_gives_one_row_a_request_without_the_texts(tmp_path):
    cache = _cache(tmp_path / "run", _first())
    document = tool.extract(cache)
    rows = document["rows"]
    assert document["version"] == tool.VERSION and document["models"] == [IDENTITY]
    manifest = (tmp_path / "run" / "manifest.json").read_bytes()
    assert document["run_manifest_sha256"] == hashlib.sha256(manifest).hexdigest()
    assert len(rows) == 9
    assert rows == sorted(rows, key=lambda row: (row["asks"], row["route"], row["prompt_sha256"]))
    written = tool.write(document)
    for text in ("текст", "срок", "source=", "answers", "about"):
        assert text not in written
    batch = _row(rows, "batch", "schema", BATCH)
    assert (batch["documents"], batch["grades"], batch["options"]) == (4, 1, {})
    assert batch["prompt_chars"] == len(BATCH) and batch["latency_ms"] == 2000.0
    again = _row(rows, "batch", "text", BATCH)
    # As text the grades are read from the JSON inside the reply.
    assert (again["documents"], again["grades"], again["options"]) == (4, 1, ROLE)
    assert _row(rows, "document", "schema", FIRST)["relevant"] is True
    refused = _row(rows, "document", "schema", SECOND)
    assert refused["outcome"] == "structured_output_invalid" and refused["relevant"] is None
    # The reply that was not JSON is still in the row, by its digest and its seconds.
    assert refused["reply_sha256"] == tool.digest("NO") and refused["latency_ms"] == 1000.0
    assert _row(rows, "document", "schema", THIRD)["relevant"] is None
    assert _row(rows, "document", "text", SECOND)["yes"] is False
    assert _row(rows, "document", "text", THIRD)["yes"] is True
    rewrite = _row(rows, "other", "text", REWRITE)
    assert rewrite["reply_sha256"] == tool.digest("срок оплаты")
    assert not {"documents", "grades", "relevant", "yes"} & set(rewrite)


def test_a_cache_without_a_manifest_or_without_requests(tmp_path):
    cache = _cache(tmp_path / "run", _first(), manifest=False)
    assert tool.extract(cache)["run_manifest_sha256"] is None
    empty = tmp_path / "empty" / "cache"
    empty.mkdir(parents=True)
    with pytest.raises(ValueError, match="no model request"):
        tool.extract(empty)


def test_a_batch_prompt_counts_its_own_opening_lines():
    assert tool._documents(BATCH) == 4
    # A line of a document that looks like an opening line is not counted out of turn.
    quoted = "[1] source=a.md\nсм. ниже\n[7] source=x.md\n[2] source=b.md\nтекст"
    assert tool._documents(quoted) == 2
    assert tool._documents("Перепиши вопрос") == 0


@pytest.mark.parametrize(
    "reply, grades",
    [
        ({"grades": [1, 2, 3]}, 3),
        ({"documents": [1]}, 1),
        ([1, 2], 2),
        ({"grades": "none"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_the_grades_of_a_batch_reply(reply, grades):
    assert tool._grades(reply) == grades


def test_the_file_is_read_back_as_it_was_written(tmp_path):
    document = tool.extract(_cache(tmp_path / "run", _first()))
    written = tool.write(document)
    assert json.loads(written) == document
    # One row a line, so that two files compare line by line.
    assert len(written.splitlines()) == len(document["rows"]) + 2
    path = tmp_path / "requests.json"
    path.write_text(written, encoding="utf-8")
    assert tool.read(path) == document["rows"]
    path.write_text(json.dumps({"version": "another", "rows": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a file of"):
        tool.read(path)


def test_the_verdicts_are_read_as_the_product_reads_the_replies(tmp_path):
    rows = tool.extract(_cache(tmp_path / "run", _first()))["rows"]
    assert tool.verdicts(rows) == {
        tool.digest(FIRST): {"kept": True, "route": "schema"},
        tool.digest(SECOND): {"kept": False, "route": "text"},
        tool.digest(THIRD): {"kept": True, "route": "text"},
        # Fail-closed: a document whose grading gave nothing is dropped.
        tool.digest(FOURTH): {"kept": False, "route": None},
    }


def test_summary_counts_the_steps_of_the_grading(tmp_path):
    rows = tool.extract(_cache(tmp_path / "run", _first()))["rows"]
    assert tool.summary(rows) == {
        "requests": {
            "batch/schema": 1,
            "batch/text": 1,
            "document/schema": 4,
            "document/text": 2,
            "other/text": 1,
        },
        "seconds": {
            "batch/schema": 2.0,
            "batch/text": 1.5,
            "document/schema": 4.0,
            "document/text": 1.0,
            "other/text": 0.3,
        },
        "options": {"schema": ["{}"], "text": [tool.dump(ROLE)]},
        "batches": 1,
        "batches_asked_again_as_text": 1,
        "batch_documents": 4,
        "batch_documents_by_count": {"4": 1},
        "batch_replies_by_grades": {"schema": {"1": 1}, "text": {"1": 1}},
        "batches_with_a_grade_a_document": 0,
        "documents_asked_one_by_one": 4,
        "documents_with_a_structured_verdict": 1,
        "documents_asked_again_as_text": 2,
        "documents_kept": 2,
        "documents_dropped": 2,
    }


def test_summary_sees_a_batch_that_gave_a_grade_a_document(tmp_path):
    four = {"grades": [{"index": n, "relevant": n < 3} for n in range(1, 5)]}
    by_schema = [_entry(BATCH, schema=BATCH_SCHEMA, text=json.dumps(four), structured=four)]
    found = tool.summary(tool.extract(_cache(tmp_path / "schema", by_schema))["rows"])
    assert found["batches_with_a_grade_a_document"] == 1
    assert found["batch_replies_by_grades"] == {"schema": {"4": 1}, "text": {}}
    assert (found["batches_asked_again_as_text"], found["documents_asked_one_by_one"]) == (0, 0)
    by_text = [
        _entry(BATCH, schema=BATCH_SCHEMA, text="grades follow", invalid=True),
        _entry(BATCH, text=json.dumps(four)),
    ]
    found = tool.summary(tool.extract(_cache(tmp_path / "text", by_text))["rows"])
    assert found["batches_with_a_grade_a_document"] == 1
    assert found["batch_replies_by_grades"] == {"schema": {"none": 1}, "text": {"4": 1}}


def test_compare_counts_shared_requests_and_changed_verdicts(tmp_path):
    first = tool.extract(_cache(tmp_path / "first", _first()))["rows"]
    second = tool.extract(_cache(tmp_path / "second", _second()))["rows"]
    found = tool.compare(first, second)
    assert found["requests"] == [
        {
            "asks": "batch",
            "route": "schema",
            "first": 1,
            "second": 1,
            "shared": 1,
            "same_reply": 0,
            "same_options": 1,
        },
        {
            "asks": "batch",
            "route": "text",
            "first": 1,
            "second": 1,
            "shared": 1,
            "same_reply": 1,
            "same_options": 1,
        },
        {
            "asks": "document",
            "route": "schema",
            "first": 4,
            "second": 4,
            "shared": 3,
            "same_reply": 1,
            "same_options": 3,
        },
        {
            "asks": "document",
            "route": "text",
            "first": 2,
            "second": 1,
            "shared": 1,
            "same_reply": 0,
            "same_options": 1,
        },
        {
            "asks": "other",
            "route": "text",
            "first": 1,
            "second": 1,
            "shared": 1,
            "same_reply": 1,
            "same_options": 1,
        },
    ]
    assert found["documents"] == {
        "shared": 3,
        "same_verdict": 1,
        "kept_by_the_first_only": 1,
        "kept_by_the_second_only": 1,
        "kept_by_the_first": 2,
        "kept_by_the_second": 2,
        "by_route": [
            {"verdict": "first", "first_route": "schema", "second_route": "schema", "documents": 1},
            {"verdict": "same", "first_route": "text", "second_route": "schema", "documents": 1},
            {"verdict": "second", "first_route": "text", "second_route": "text", "documents": 1},
        ],
    }
    # A run compared with itself shares everything and changes nothing.
    itself = tool.compare(first, first)
    assert all(row["shared"] == row["first"] == row["same_reply"] for row in itself["requests"])
    assert itself["documents"]["same_verdict"] == itself["documents"]["shared"] == 4


def test_the_commands(tmp_path, capsys):
    first = _cache(tmp_path / "first", _first())
    second = _cache(tmp_path / "second", _second())
    one, two = tmp_path / "first.json", tmp_path / "second.json"
    assert tool.main(["extract", "--cache", str(first), "--out", str(one)]) == 0
    assert tool.main(["extract", "--cache", str(second), "--out", str(two)]) == 0
    assert capsys.readouterr().out == ""
    assert one.read_bytes() == tool.write(tool.extract(first)).encode("utf-8")
    # Without a file the rows go to the standard output: a run on another host is read so.
    assert tool.main(["extract", "--cache", str(first)]) == 0
    assert capsys.readouterr().out == tool.write(tool.extract(first))
    assert tool.main(["summary", "--file", str(one)]) == 0
    assert json.loads(capsys.readouterr().out) == tool.summary(tool.read(one))
    assert tool.main(["compare", "--first", str(one), "--second", str(two)]) == 0
    assert json.loads(capsys.readouterr().out) == tool.compare(tool.read(one), tool.read(two))
