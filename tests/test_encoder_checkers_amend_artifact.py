"""Amendment 1 of the encoder checkers: Part 1's record read again from B's rows by the
amendment's tool, Part 2's from the committed V5 aircargo judge record, the capsule's rows from
the records (docs/specs/encoder-checkers.md, Amendment 1)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/encoder-checkers/tools/encoder_checkers_amend.py"
BASE = ROOT / "reports/encoder-checkers/4f48fed-base"
FRESH = ROOT / "reports/encoder-checkers/4f48fed-fresh"
JUDGE = ROOT / "reports/answer-prompt-v5/4f48fed/v5-aircargo-judge.json"
CAPSULE = ROOT / "docs/evidence/encoder-checkers-record.md"
NAME = "Horizon guard base"


def _load():
    spec = importlib.util.spec_from_file_location("encoder_checkers_amend_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["encoder_checkers_amend_artifact"] = module
    spec.loader.exec_module(module)
    return module


am = _load()
ec = am.ec
part1 = json.loads((BASE / "record.json").read_text(encoding="utf-8"))
part2 = json.loads((FRESH / "record.json").read_text(encoding="utf-8"))
b = part1["checkers"]["B"]


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def test_part_one_is_the_tools_output_of_bs_rows(tmp_path):
    for name in ("parity-B.json", "scores-B.jsonl"):
        shutil.copy(BASE / name, tmp_path / name)
    assert _json(am.base(tmp_path)) == part1
    assert (tmp_path / "record.json").read_bytes() == (BASE / "record.json").read_bytes()


def test_b_was_scored_whole_on_its_checked_weights_by_the_registered_tool():
    parity = part1["parity"]
    assert parity["passed"] and parity["pairs"] == 12
    assert parity["B"]["max_abs_difference"] <= ec.PARITY_TOLERANCE
    assert parity["B"]["same_top_label"] and parity["B"]["config_matches_file"]
    assert part1["registered_sha256"] == am.REGISTERED_SHA256
    assert (b["repo"], b["revision"]) == (am.B["repo"], am.B["revision"])
    assert b["reached"] == b["planned"] and b["segments"] == 1 and not b["stopped"]
    assert part1["orphan_amendment_rows"] == 0 and part1["proposes"] is False
    assert b["seconds_total"] < 60 * am.B["forecast_min"] * ec.STOP_FACTOR


def test_part_two_has_nothing_to_score_the_aircargo_plan_not_counted(tmp_path):
    judged = json.loads(JUDGE.read_text(encoding="utf-8"))
    test = judged["retest"]
    kappa = test["quadratic_kappa"]
    passes = (kappa is not None and kappa >= 0.6) or (
        test["agree"] >= 13 and test["two_steps_apart"] == 0
    )
    assert judged["status"] == "NOT_EVIDENCE" and not passes and not test["passed"]
    assert am.readable() == "V5's aircargo judge plan is not counted"
    assert _json(am.confirm(tmp_path, tmp_path / "unread-plan.json")) == part2
    assert part2["decision"] == f"{ec.NOT_EVIDENCE}: V5's aircargo judge plan is not counted"
    assert part2["worth_wiring"] is None
    assert sorted(path.name for path in FRESH.iterdir()) == ["record.json"]


def _share(value):
    return f"{value:.3f}" if value is not None else "—"


def b_rows():
    """B's rows of the capsule's three tables, as the first record's rows are printed."""
    cut = b["threshold"]["threshold"]
    cells = [NAME, "none" if cut is None else f"{cut:.4f}"]
    for half in ("EN", "RU"):
        got = b["calibration"][half]
        cells += [f"{got['caught']} of {got['target']}"]
        cells += [f"{got['over_marked']} of {got['good_not_declining']}"]
    cells += [_share(b["auroc"]["EN"]), _share(b["auroc"]["RU"])]
    threshold = "| " + " | ".join(cells) + " |"
    got, seconds = b["reading"], b["seconds"]["reading"]
    reading = (
        f"| {NAME} | {got['caught']} | {got['over_marked']} | {got['reading']} "
        f"| {_share(b['auroc']['reading'])} | {seconds['median']:.1f} ({seconds['p90']:.1f}) "
        f"| {b['peak_rss_bytes'] / 1e9:.2f} |"
    )
    types, cut_pairs = b["ru_types"], b["truncated"]
    kinds = (
        f"| {NAME} | {types['grounding']['caught']} of {types['grounding']['target']} | "
        f"{types['other']['caught']} of {types['other']['target']} | "
        f"{cut_pairs['reading']} / {cut_pairs['EN']} / {cut_pairs['RU']} |"
    )
    return [threshold, reading, kinds]


def test_the_capsule_prints_both_parts():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in b_rows():
        assert line in text, line
    assert f"**Part 1: {part1['decision']}.**" in text
    assert f"**Part 2: {part2['decision']}.**" in text
