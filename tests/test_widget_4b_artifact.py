"""The widget on the 4B: the record read again from its rows, the rows against the registered
tools and the spec's requests, the capsule's tables from the record
(docs/specs/widget-4b.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/widget-4b/tools"
OUT = ROOT / "reports/widget-4b/4f48fed"
CAPSULE = ROOT / "docs/evidence/widget-4b-record.md"
LIVE_API = ROOT / "reports/stage2/tools/live_api.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "widget_record_artifact", TOOLS / "widget_record.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["widget_record_artifact"] = module
    spec.loader.exec_module(module)
    return module


wr = _load()
record = json.loads((OUT / "record.json").read_text(encoding="utf-8"))
rows = wr.load_jsonl(OUT / "rows.jsonl")


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def test_every_number_of_the_record_is_read_again_from_its_rows():
    got = _json(wr.build(rows, wr.chat_classes()))
    assert {key: record[key] for key in got} == got
    assert record["rows_sha256"] == wr.sha256(OUT / "rows.jsonl")
    assert record["plan_sha256"] == wr.sha256(wr.PLAN)
    assert record["judge_sha256"] == wr.sha256(wr.JUDGE)


def test_the_runs_are_the_registered_tools_on_the_stand():
    files = {name: TOOLS / name for name in wr.TOOLS if name != "live_api.py"}
    files["live_api.py"] = LIVE_API
    starts = [row for row in rows if row["kind"] == "start"]
    assert [row["run"] for row in starts] == list(wr.RUNS)
    for row in starts:
        assert row["code_sha"] == wr.STAND and row["model"] == wr.MODEL
        assert row["tools_sha256"] == {
            name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()
        }
        assert row["planned"] == wr.RUNS[row["run"]][1]
    production, development = starts
    assert production["rag_env"] == "production" and development["rag_env"] is None
    assert set(production["production_names_set"]) <= {
        "RAG_ENV",
        "CORS_ORIGINS",
        "ADMIN_PASSWORD_HASH",
    }
    assert development["production_names_set"] == []


def test_the_answers_are_the_specs_questions_in_order():
    for run, (_, planned) in wr.RUNS.items():
        asked = [row["case_id"] for row in rows if row["kind"] == "answer" and row["run"] == run]
        assert asked == planned[: len(asked)]


def test_the_rows_hold_ids_labels_and_numbers_only():
    answer_keys = {
        "kind",
        "run",
        "env",
        "case_id",
        "http_status",
        "client_error",
        "delivered",
        "route",
        "ticket",
        "delivery_state",
        "quality_score",
        "cached",
        "citations",
        "sources",
        "seconds",
        "trace_found",
        "passes",
        "nodes",
        "model_calls",
    }
    for row in rows:
        if row["kind"] == "answer":
            assert set(row) == answer_keys
            for item in row["passes"]:
                assert set(item) == {"grade", "verify", "evaluate", "route", "knowledge_gap"}


def question_rows():
    out = []
    for item in record["ten"]["questions"]:
        out.append(
            f"| {item['case_id']} | {item['route']} | {'yes' if item['ticket'] else 'no'} | "
            f"{item['passes']} | {item['model_calls']} | {item['seconds'] / 60:.1f} | "
            f"{item['chat_grade'] or '—'} |"
        )
    return out


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in question_rows():
        assert line in text, line
    assert f"**R1: {record['r1']['reading']}.**" in text
    assert f"**R2: {record['r2']['reading']}.**" in text
    grader = record["grader"]
    assert f"{grader['defects']} of {grader['passes']} passes" in text
