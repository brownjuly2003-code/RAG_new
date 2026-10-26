"""The encoder checkers: the record read again from its rows, the rows against the committed
plan and judge records, the capsule's tables from the record (docs/specs/encoder-checkers.md,
«Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/encoder-checkers/tools/encoder_checkers.py"
OUT = ROOT / "reports/encoder-checkers/4f48fed"
CAPSULE = ROOT / "docs/evidence/encoder-checkers-record.md"
NAMES = {"H": "Horizon guard small", "L": "LettuceDetect v2 mmBERT", "N": "mDeBERTa NLI"}


def _load():
    spec = importlib.util.spec_from_file_location("encoder_checkers_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["encoder_checkers_artifact"] = module
    spec.loader.exec_module(module)
    return module


ec = _load()
record = json.loads((OUT / "record.json").read_text(encoding="utf-8"))
scores = {name: ec.load_jsonl(OUT / f"scores-{name}.jsonl") for name in ec.CHECKERS}


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def _answers(name):
    return [row for row in scores[name] if row["kind"] == "answer"]


def test_every_number_of_the_record_is_read_again_from_its_rows():
    per_checker = {name: ec.checker_record(rows) for name, rows in scores.items()}
    assert _json(per_checker) == record["checkers"]
    assert _json(ec.outcome(per_checker)) == {
        "decision": record["decision"],
        "worth_wiring": record["worth_wiring"],
    }


def test_the_loading_path_was_checked_before_any_score():
    parity = record["parity"]
    assert parity == json.loads((OUT / "parity.json").read_text(encoding="utf-8"))
    assert parity["passed"] and parity["pairs"] == 12
    for name in ("H", "N"):
        assert parity[name]["max_abs_difference"] <= ec.PARITY_TOLERANCE
        assert parity[name]["same_top_label"]
    assert parity["L"] == {"config_matches_file": True}


def test_the_rows_are_the_registered_tools_on_the_pinned_weights():
    tool = hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert record["tool_sha256"] == tool
    for name, rows in scores.items():
        starts = [row for row in rows if row["kind"] == "start"]
        assert starts and all(row["tool_sha256"] == tool for row in starts)
        assert all(row["revision"] == ec.CHECKERS[name]["revision"] for row in starts)
        inputs = starts[0]["inputs"]
        assert inputs["plan"] == ec.sha256(ec.PLAN)
        for base, path in ec.JUDGE.items():
            assert inputs[f"judge {base}"] == ec.sha256(path)
        assert starts[0]["rushallu_commit"] == ec.RUSHALLU_COMMIT


def test_the_three_checkers_scored_the_same_answers_in_the_specs_order():
    plan = json.loads(ec.PLAN.read_text(encoding="utf-8"))
    order = [f"{item['run']}/{item['case_id']}" for item in plan["items"]]
    first = [(row["set"], row["id"], row["class"]) for row in _answers("H")]
    for name in ec.CHECKERS:
        rows = _answers(name)
        assert [(row["set"], row["id"], row["class"]) for row in rows] == first
        assert [row["id"] for row in rows if row["set"] == "reading"] == order
        assert [row["set"] for row in rows] == sorted(
            (row["set"] for row in rows), key=["reading", "EN", "RU"].index
        )


def test_the_classes_are_the_committed_judges():
    judged = {
        f"{row['run']}/{row['case_id']}": ec.judge_class(row)
        for path in ec.JUDGE.values()
        for row in ec.load_jsonl(path)
    }
    rows = [row for row in _answers("H") if row["set"] in ("reading", "EN")]
    assert all(row["class"] == judged[row["id"]] for row in rows)
    reading = [row["class"] for row in rows if row["set"] == "reading"]
    assert (reading.count("target"), reading.count("good"), reading.count(None)) == (17, 63, 20)
    en = [row for row in rows if row["set"] == "EN"]
    assert len(en) == 183 and None not in {row["class"] for row in en}
    ru = [row for row in _answers("H") if row["set"] == "RU"]
    assert len(ru) == 300
    assert all((row["class"] == "target") == (any(row["groups"].values())) for row in ru)


def test_the_rows_hold_ids_labels_and_numbers_only():
    answer_keys = {
        "kind",
        "set",
        "base",
        "id",
        "class",
        "score",
        "sentences",
        "units",
        "tokens",
        "truncated",
        "seconds",
        "groups",
    }
    for name in ec.CHECKERS:
        for row in _answers(name):
            assert set(row) <= answer_keys
            assert row["base"] in {"aircargo", "wixqa", "conditionalqa", *ec.RUSHALLU_FILES}
            assert row["score"] is None or 0.0 <= row["score"] <= 1.0


def _share(value):
    return f"{value:.3f}" if value is not None else "—"


def threshold_rows():
    out = []
    for name, entry in record["checkers"].items():
        cut = entry["threshold"]["threshold"]
        cells = [NAMES[name], "none" if cut is None else f"{cut:.4f}"]
        for half in ("EN", "RU"):
            got = entry["calibration"][half]
            cells.append(f"{got['caught']} of {got['target']}")
            cells.append(f"{got['over_marked']} of {got['good_not_declining']}")
        cells += [_share(entry["auroc"]["EN"]), _share(entry["auroc"]["RU"])]
        out.append("| " + " | ".join(cells) + " |")
    return out


def reading_rows():
    out = []
    for name, entry in record["checkers"].items():
        got, seconds = entry["reading"], entry["seconds"]["reading"]
        if got == ec.NOT_EVIDENCE:
            cells = [NAMES[name], "—", "—", ec.NOT_EVIDENCE]
        else:
            cells = [NAMES[name], str(got["caught"]), str(got["over_marked"]), got["reading"]]
        cells += [
            _share(entry["auroc"]["reading"]),
            f"{seconds['median']:.1f} ({seconds['p90']:.1f})",
            f"{entry['peak_rss_bytes'] / 1e9:.2f}",
        ]
        out.append("| " + " | ".join(cells) + " |")
    return out


def type_rows():
    out = []
    for name, entry in record["checkers"].items():
        got = entry["ru_types"]
        out.append(
            f"| {NAMES[name]} | {got['grounding']['caught']} of {got['grounding']['target']} | "
            f"{got['other']['caught']} of {got['other']['target']} | "
            f"{entry['truncated']['reading']} / {entry['truncated']['EN']} / "
            f"{entry['truncated']['RU']} |"
        )
    return out


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in threshold_rows() + reading_rows() + type_rows():
        assert line in text, line
    assert f"**Outcome: {record['decision']}.**" in text
