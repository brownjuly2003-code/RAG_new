"""Coverage beside quality: the record derived again from the committed judge exports
(docs/specs/coverage-metrics.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/coverage/tools/coverage_record.py"
RECORD = ROOT / "reports/coverage/coverage-record.json"
CAPSULE = ROOT / "docs/evidence/coverage-metrics-record.md"
NAMES = {
    "aircargo": "aircargo",
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "multihoprag": "MultiHop-RAG",
}


def _load():
    spec = importlib.util.spec_from_file_location("coverage_record_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["coverage_record_artifact"] = module
    spec.loader.exec_module(module)
    return module


cov = _load()
record = json.loads(RECORD.read_text(encoding="utf-8"))


def rows(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_the_tool_rebuilds_the_record_from_the_committed_exports():
    rebuilt = json.loads(json.dumps(cov.build(), ensure_ascii=False, sort_keys=True))
    assert rebuilt == record


def test_each_input_is_named_by_its_sha256_and_the_tool_by_its_own():
    assert record["tool_sha256"] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert len(record["inputs"]) == 12
    for path, digest in record["inputs"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert record["stands"] == {
        "V3": "5e308fe48cca0955c3007057a574a425f71e2a6a",
        "V4": "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1",
    }


def test_kinds_and_crag_levels_counted_again_from_the_rows():
    for key, sides in cov.INPUTS.items():
        for name, path in sides.items():
            kinds = {"answered": 0, "declined": 0, "empty": 0}
            levels = {"1": 0, "0.5": 0, "0": 0, "-1": 0}
            for r in rows(path):
                assert r["grade"] is not None, f"{key} {name}: a missing row"
                if r.get("empty_answer"):
                    kinds["empty"] += 1
                    levels["0"] += 1
                elif r["answers_question"] == "declined":
                    kinds["declined"] += 1
                    levels["0"] += 1
                else:
                    kinds["answered"] += 1
                    levels[{"good": "1", "partial_ok": "0.5"}.get(r["grade"], "-1")] += 1
            side = record["keys"][key][name]
            assert side["kinds"] == kinds and side["crag"]["levels"] == levels
            mean = (levels["1"] + 0.5 * levels["0.5"] - levels["-1"]) / sum(levels.values())
            assert side["crag"]["mean"] == round(mean, 4)


def test_the_gold_counts_are_the_bases_own():
    without = {"wixqa": 0, "conditionalqa": 20, "multihoprag": 30}
    for key, sides in record["keys"].items():
        for name, side in sides.items():
            if key in without:
                assert sum(side["by_reference"]["counts"]["false"].values()) == without[key]
    # V4's record's guard row: ConditionalQA declines 4 of its 20 not answerable, V3 8.
    cqa = record["keys"]["conditionalqa"]
    assert cqa["V4"]["by_reference"]["counts"]["false"]["declined"] == 4
    assert cqa["V3"]["by_reference"]["counts"]["false"]["declined"] == 8


def _num(value):
    return f"{value:.3f}".replace("-", "−")


def _frac(s):
    return f"{s['hits']}/{s['n']}"


def test_every_capsule_table_row_is_built_from_the_record():
    capsule = CAPSULE.read_text(encoding="utf-8")
    for key, sides in record["keys"].items():
        for name, v in sides.items():
            lo, hi = v["crag"]["cluster95"]
            first = (
                f"| {NAMES[key]} | {name} | {_frac(v['coverage'])}"
                f" | {_frac(v['good_among_answered'])}"
                f" | {_frac(v['good_or_partial_among_answered'])}"
                f" | {_frac(v['unsupported_among_answered'])}"
                f" | {_num(v['crag']['mean'])} ({_num(lo)} to {_num(hi)}) |"
            )
            ref = v.get("by_reference")
            gold = "—"
            if ref:
                n = sum(ref["counts"]["false"].values())
                gold = f"{ref['counts']['false']['declined']}/{n}" if n else "— (0)"
            held = v["by_context"]["counts"]["true"]["declined"]
            second = f"| {NAMES[key]} | {name} | {v['kinds']['declined']} | {held} | {gold} |"
            assert first in capsule, first
            assert second in capsule, second
