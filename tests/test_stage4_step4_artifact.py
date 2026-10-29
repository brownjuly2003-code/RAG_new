"""Stage 4, step 4: the answer prompt's window, the record read again from its rows and the
committed stage-2 export (docs/specs/stage4-step4-prompt-budget.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage4-step4/tools/prompt_budget.py"
RECORD = ROOT / "reports/stage4-step4/5e308fe/record.json"
ROWS = ROOT / "reports/stage4-step4/5e308fe/rows.jsonl"
CAPSULE = ROOT / "docs/evidence/stage4-step4-record.md"
K_CURVE = ROOT / "reports/k-curve/5e308fe/record.json"
NO_RERANK = ROOT / "reports/no-rerank/5e308fe/record.json"
# The prompts the count fitted under: agent/prompts.py's answer prompt at 5e308fe and at b192fb0.
STAGE2_PROMPT = "1fc83b5543492c5f10b34f02b6bee47fd9474a7529ee9a7f2a22b374cc09f107"
CODE_PROMPT = "9276aff5a3a44bc9ff1adb7a52b7b11a06e8f4b0f7fe79a5dc6b20262db3a515"


def _load():
    spec = importlib.util.spec_from_file_location("stage4_step4_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage4_step4_artifact"] = module
    spec.loader.exec_module(module)
    return module


pb = _load()
nr = pb.nr
record = json.loads(RECORD.read_text(encoding="utf-8"))
rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def test_every_number_of_the_record_is_read_again_from_its_rows():
    for base in nr.LABELS:
        own = [r for r in rows if r["base"] == base]
        assert _json(pb.summary(base, own)) == record["bases"][base]
    gold = [r for r in rows if r["base"] in nr.METRICS]
    assert _json(pb.pooled_windows(gold, not_evidence=False)) == record["pooled"]
    per_base = {b: record["bases"][b] for b in nr.METRICS}
    assert _json(pb.decision(per_base, record["pooled"])) == record["decision"]


def test_the_checks_passed_before_any_number():
    assert {b: record["bases"][b]["questions"] for b in nr.LABELS} == dict.fromkeys(nr.LABELS, 100)
    assert {b: record["bases"][b]["with_gold"] for b in nr.METRICS} == {
        "wixqa": 100,
        "conditionalqa": 80,
        "multihoprag": 70,
    }
    assert all(record["bases"][b]["unresolved"] == 0 for b in nr.METRICS)
    # Today's prompt at 4,096 is the prompt V4's live run sent, on every question of its bases.
    for base in pb.V4_BASES:
        assert record["bases"][base]["v4"] == {"same_retrieval": 100, "prompts_checked": 100}
    for base in nr.METRICS:
        assert all(p["excerpt_pieces_missed"] == 0 for p in record["bases"][base]["windows"])


def test_stage_2s_points_are_the_committed_exports():
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    assert (
        record["inputs"]["export_manifest_sha256"]
        == hashlib.sha256((nr.EXPORT / "manifest.json").read_bytes()).hexdigest()
    )
    by_case = {r["case_id"]: r for r in rows}
    for label in nr.LABELS.values():
        committed = nr.export_rows(label, manifest)
        own = [by_case[case_id] for case_id in committed]
        nr.recount(own, committed)
        pb.recount(own, committed)
    assert len(by_case) == len(rows) == 400


def test_every_prompt_fits_its_window_and_a_smaller_window_sends_no_more():
    for row in rows:
        assert [e["window"] for e in row["windows"]] == list(pb.WINDOWS)
        for entry in row["windows"]:
            assert entry["est_tokens"] <= pb.input_limit(entry["window"])
        for larger, smaller in zip(row["windows"], row["windows"][1:], strict=False):
            assert smaller["documents"] <= larger["documents"]
            assert smaller["est_tokens"] <= larger["est_tokens"]


def test_the_record_names_its_stand_tool_prompts_and_inputs():
    assert record["spec"] == pb.SPEC
    assert record["stand_code_sha"] == nr.CODE_SHA
    assert record["measured_at_head"].startswith("b192fb0")
    assert record["tool_sha256"] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert set(record["measure_code_sha256"]) == set(pb.MEASURE_CODE)
    assert record["output_budget"] == pb.OUTPUT_BUDGET == 1024
    assert record["windows"] == [
        {"window": w, "input_limit": pb.input_limit(w)} for w in pb.WINDOWS
    ]
    assert record["prompts"] == {
        "stage2": {"prompt_id": "QA_PROMPT_V3", "sha256": STAGE2_PROMPT},
        "code": {"prompt_id": "QA_PROMPT_V4", "sha256": CODE_PROMPT},
    }
    from agent.prompts import PROMPT_REGISTRY

    if PROMPT_REGISTRY["qa"]["prompt_id"] == "QA_PROMPT_V4":
        assert pb.digest(PROMPT_REGISTRY["qa"]["text"]) == CODE_PROMPT
    # The K curve's inputs, file by file, and V4's committed rows.
    k_curve = json.loads(K_CURVE.read_text(encoding="utf-8"))
    assert {k: v for k, v in record["inputs"].items() if k != "v4_rows"} == k_curve["inputs"]
    assert record["inputs"]["v4_rows"] == "reports/answer-prompt-v4/4f48fed"
    no_rerank = json.loads(NO_RERANK.read_text(encoding="utf-8"))
    for base, provenance in record["provenance"].items():
        assert provenance["label"] == nr.LABELS[base]
        assert provenance["code_sha"] == nr.CODE_SHA
        for key in ("tenant", "settings", "archive_sha256", "cases_file_sha256", "launch_sha256"):
            assert provenance[key] == no_rerank["provenance"][base][key]
        if base in pb.V4_BASES:
            v4_rows = ROOT / record["inputs"]["v4_rows"] / f"v4-{base}.cases.jsonl"
            assert provenance["v4_rows_sha256"] == hashlib.sha256(v4_rows.read_bytes()).hexdigest()


def test_the_rows_hold_ids_flags_and_numbers_only():
    keys = {
        "case_id",
        "base",
        "index",
        "v4_same_retrieval",
        "v4_prompt_checked",
        "windows",
        "stratum",
        "unresolved",
        "points",
        "excerpt_pieces_missed",
    }
    window_keys = {"window", "documents", "cut", "chars", "est_tokens", "sent"}
    for row in rows:
        assert set(row) <= keys
        assert row["case_id"].startswith(row["base"]) or row["base"] == "aircargo"
        assert set(row.get("points", {})) <= {"ranked", "expanded_ranked", "sent"}
        for entry in row["windows"]:
            assert set(entry) <= window_keys | {"excerpt_pieces_missed"}


def _n(value):
    return f"{value:,g}"


def _cell(got):
    text = f"{got['hits']['window']} ({got['b_today_only']}/{got['c_window_only']}, {got['p']:.3f})"
    return text + {"loss": " **loss**", "gain": " *gain*"}.get(got["reading"], "")


def sent_rows():
    first = [record["bases"][b]["windows"][1]["sent"] for b in nr.METRICS]
    first.append(record["pooled"][0]["sent"])
    top = f"| {_n(pb.TODAY)} ({_n(pb.input_limit(pb.TODAY))}) | "
    out = [top + " | ".join(f"{g['hits']['today']} of {g['n']}" for g in first) + " |"]
    for i, window in enumerate(pb.WINDOWS[1:], start=1):
        cells = [_cell(record["bases"][b]["windows"][i]["sent"]) for b in nr.METRICS]
        cells.append(_cell(record["pooled"][i - 1]["sent"]))
        out.append(f"| {_n(window)} ({_n(pb.input_limit(window))}) | " + " | ".join(cells) + " |")
    return out


def size_rows():
    out = []
    for i, window in enumerate(pb.WINDOWS):
        got = [record["bases"][b]["windows"][i] for b in nr.LABELS]
        documents = " / ".join(_n(g["documents"]["median"]) for g in got)
        tokens = " / ".join(_n(g["est_tokens"]["median"]) for g in got)
        saved = " / ".join(_n(g["est_tokens_saved"]["median"]) for g in got)
        cut = " / ".join(str(g["cut"]) for g in got)
        out.append(f"| {_n(window)} | {documents} | {tokens} | {saved} | {cut} |")
    return out


def stage2_rows():
    out = []
    for base, name in zip(nr.METRICS, ("WixQA", "ConditionalQA", "MultiHop-RAG"), strict=True):
        got = record["bases"][base]["stage2_against_today"]
        out.append(
            f"| {name} | {got['hits']['stage2']} of {got['n']} | {got['hits']['today']} | "
            f"{got['b_stage2_only']}/{got['c_today_only']}, {got['p']:.3f} |"
        )
    return out


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    for line in sent_rows() + size_rows() + stage2_rows():
        assert line in text, line
    smallest = record["decision"]["smallest_window_without_a_detected_loss"]
    limit = record["decision"]["its_input_limit"]
    assert (
        f"**The smallest window without a detected loss: {_n(smallest)}** "
        f"(input limit {_n(limit)})." in text
    )
