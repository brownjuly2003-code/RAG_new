"""Stage 4, item 5a: INT8 of the same reranker — the record read again from its rows with the
committed tool, its provenance and its blocks (docs/specs/stage4-step5a-int8-reranker.md,
«Records»). The blocks' files, with their scores and seconds, stay on the Mac: the gold and the
fives are read again from the rows, the speed from the record's own counts. Every table row of
docs/evidence/stage4-step5a-record.md is built from the record, and so is every number of its
prose that comes from the record."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage4-step5a/tools/int8_reranker.py"
EXPORT_TOOL = ROOT / "reports/stage4-step5a/tools/export_onnx.py"
MANIFEST = ROOT / "reports/stage4-step5a/onnx/manifest.json"
RECORDS = ROOT / "reports/stage4-step5a/d9f9fd8"
SPEC = ROOT / "docs/specs/stage4-step5a-int8-reranker.md"
CAPSULE = ROOT / "docs/evidence/stage4-step5a-record.md"
NO_RERANK = ROOT / "reports/no-rerank/5e308fe/record.json"
K_CURVE = ROOT / "reports/k-curve/5e308fe/record.json"
# The commit that registered the spec, the tool and its test: the worktree the blocks ran in.
REGISTERED = "d9f9fd8c2171c66bccb0cf9ee7adb414ea6ea6ba"
MODELS = "/Users/julia/RAG_new_ort/bge-reranker-v2-m3"
NAMES = {
    "wixqa": "WixQA",
    "conditionalqa": "ConditionalQA",
    "multihoprag": "MultiHop-RAG",
    "aircargo": "aircargo",
}


def _load():
    spec = importlib.util.spec_from_file_location("int8_reranker_artifact", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["int8_reranker_artifact"] = module
    spec.loader.exec_module(module)
    return module


ir = _load()
nr = ir.nr
record = json.loads((RECORDS / "record.json").read_text(encoding="utf-8"))
rows = [
    json.loads(line)
    for line in (RECORDS / "rows.jsonl").read_text(encoding="utf-8").splitlines()
    if line
]


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def when(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def numbers():
    return sorted(int(n) for n in record["blocks"])


def test_every_reading_of_the_record_is_read_again_from_its_rows():
    fidelity = ir.beside(rows, ir.FIDELITY)
    fidelity |= {
        "tolerance": ir.TOLERANCE["fp32"],
        "reading": "holds" if fidelity["max_abs_diff"]["max"] <= ir.TOLERANCE["fp32"] else "fails",
    }
    seconds = record["fidelity"].pop("pytorch_over_fp32_sec_median")
    try:
        assert _json(fidelity) == record["fidelity"]
    finally:
        record["fidelity"]["pytorch_over_fp32_sec_median"] = seconds
    for base in nr.LABELS:
        mine = [r for r in rows if r["base"] == base]
        got = {str(n): ir.beside(mine, n) for n in numbers()}
        assert _json({n: v for n, v in got.items() if v}) == record["by_base"][base]
    for variant in ir.VARIANTS:
        assert _json(ir.quality(rows, variant)) == record["variants"][variant]["quality"]
    assert _json(ir.outcome(record["fidelity"], record["variants"])) == record["outcome"]


def test_the_speed_reading_follows_from_its_counts_by_the_sign_test():
    for variant, plan in ir.VARIANTS.items():
        pace = record["variants"][variant]["speed"]
        timing = [str(n) for n in plan["timing"]]
        if pace is None:
            assert not set(timing) & set(record["blocks"])
            continue
        thirty = sorted(r["case_id"] for r in rows if timing[0] in r["blocks"])
        assert pace["questions"] == len(thirty) == ir.THIRTY
        assert set(pace["disturbed"]) <= set(thirty)
        assert pace["readable"] == pace["questions"] - len(pace["disturbed"])
        # A question is disturbed when it is in any of the four blocks.
        counts = [record["blocks"][n]["disturbed"] for n in timing]
        assert max(counts) <= len(pace["disturbed"]) <= sum(counts)
        faster, slower = pace["faster"], pace["slower"]
        assert faster + slower <= pace["readable"]
        p = nr.mcnemar(faster, slower)
        assert pace["p"] == round(p, 6)
        if pace["readable"] < ir.MIN_READABLE:
            want = ir.NOT_EVIDENCE
        elif p < nr.ALPHA and faster > slower:
            want = "faster"
        elif p < nr.ALPHA and slower > faster:
            want = "slower"
        else:
            want = "no detected difference"
        assert pace["reading"] == want
        for n in timing:
            got = pace["block_sec_median"][n]
            assert abs(got - record["blocks"][n]["seconds"]["median"]) <= 1e-3


def test_the_pytorch_blocks_are_stage_2s_reranker_and_the_rows_stage_2s_fives():
    pytorch = [str(n) for n in numbers() if ir.SCHEDULE[n][0] == "pytorch"]
    assert pytorch
    for row in rows:
        for n in pytorch:
            if n in row["blocks"]:
                got = row["blocks"][n]
                assert got["max_abs_diff"] <= ir.TOLERANCE["pytorch"]
                assert (got["shared_of_five"], got["same_five"], got["same_order"]) == (
                    5,
                    True,
                    True,
                )
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    by_case = {r["case_id"]: r for r in rows}
    for label in nr.LABELS.values():
        committed = nr.export_rows(label, manifest)
        own = [by_case[case_id] for case_id in committed]
        nr.recount(own, committed)
        for row in own:
            assert row["pool_size"] == len(committed[row["case_id"]]["pool"])
    assert len(by_case) == len(rows) == 400


def test_the_checks_passed_before_any_number():
    assert record["outcome"] != "pending" or record["variants"]["int8"]["quality"] is not None
    for base in nr.LABELS:
        mine = [r for r in rows if r["base"] == base]
        assert len(mine) == 100
        assert all(r["reranker_ok"] for r in mine)
    gold = {b: [r for r in rows if r["base"] == b and "points" in r] for b in nr.METRICS}
    assert {b: len(v) for b, v in gold.items()} == {
        "wixqa": 100,
        "conditionalqa": 80,
        "multihoprag": 70,
    }
    for variant, plan in ir.VARIANTS.items():
        got = record["variants"][variant]["quality"]
        if got is None:
            continue
        assert all(str(plan["quality"]) in r["blocks"] for r in rows)
        for base, entry in got["bases"].items():
            assert entry["with_gold"] == len(gold[base])
            assert entry["unresolved"] <= ir.MAX_UNREAD


def test_the_record_names_its_stand_tool_export_and_inputs():
    listed = dict(re.findall(r"- `([^`]+)` `([0-9a-f]{64})`", SPEC.read_text(encoding="utf-8")))
    assert record["tool_sha256"] == sha(TOOL) == listed[str(TOOL.relative_to(ROOT).as_posix())]
    assert (record["spec"], record["stand_code_sha"], record["measured_at_head"]) == (
        ir.SPEC,
        nr.CODE_SHA,
        REGISTERED,
    )
    measured = record["measure_code_sha256"]
    assert set(measured) == set(ir.MEASURE_CODE)
    assert measured["reports/stage4-step5a/tools/export_onnx.py"] == sha(EXPORT_TOOL)
    assert sha(EXPORT_TOOL) == listed["reports/stage4-step5a/tools/export_onnx.py"]
    no_rerank = json.loads(NO_RERANK.read_text(encoding="utf-8"))
    k_curve = json.loads(K_CURVE.read_text(encoding="utf-8"))
    assert measured["reports/no-rerank/tools/no_rerank_point.py"] == no_rerank["tool_sha256"]
    assert measured["reports/k-curve/tools/k_curve.py"] == k_curve["tool_sha256"]
    inputs = record["inputs"]
    assert {k: inputs[k] for k in no_rerank["inputs"]} == no_rerank["inputs"]
    assert inputs["models"] == MODELS
    assert inputs["export_onnx_manifest_sha256"] == ir.MANIFEST_SHA256 == sha(MANIFEST)
    assert inputs["export_manifest_sha256"] == sha(nr.EXPORT / "manifest.json")
    assert record["provenance"] == no_rerank["provenance"]


def test_the_blocks_ran_the_schedule_in_order_each_once():
    assert numbers() == list(range(1, len(numbers()) + 1))
    assert len(numbers()) in (6, 11)
    assert record["attempts"] == {str(n): 1 for n in numbers()}
    assert record["rejected"] == []
    previous = None
    for n in numbers():
        got = record["blocks"][str(n)]
        assert (got["arm"], got["kind"]) == ir.SCHEDULE[n]
        assert re.fullmatch(r"[0-9a-f]{64}", got["file_sha256"])
        start, end = when(got["started_at"]), when(got["ended_at"])
        assert start < end
        assert previous is None or previous <= start
        previous = end
        assert got["seconds"]["n"] == (ir.THIRTY if got["kind"] == "thirty" else 400)
        # transformers' tokenizer imports torch, so an ONNX block holds it too.
        assert got["torch_imported"] is True


def test_the_rows_hold_ids_flags_and_numbers_only():
    keys = {
        "case_id",
        "base",
        "index",
        "pool_size",
        "reranker_ok",
        "blocks",
        "stratum",
        "points",
        "unresolved",
    }
    points = {"ranked", "expanded_ranked"}
    for variant in ir.VARIANTS:
        points |= {variant, f"expanded_{variant}"}
    for row in rows:
        assert set(row) <= keys
        assert row["case_id"].startswith(row["base"]) or row["base"] == "aircargo"
        assert set(row["blocks"]) <= {str(n) for n in numbers()}
        for entry in row["blocks"].values():
            assert set(entry) == {"max_abs_diff", "shared_of_five", "same_five", "same_order"}
        assert set(row.get("points", {})) <= points
        assert set(row.get("unresolved", [])) <= set(ir.VARIANTS)


# --- The capsule's tables and prose, built from the record.
FILES = ("record.json", "rows.jsonl")
QUALITY = ir.VARIANTS["int8"]["quality"]


def minutes(n):
    got = record["blocks"][str(n)]
    return (when(got["ended_at"]) - when(got["started_at"])).total_seconds() / 60


def largest(n):
    return max(r["blocks"][str(n)]["max_abs_diff"] for r in rows if str(n) in r["blocks"])


def pytorch_blocks():
    return [n for n in numbers() if ir.SCHEDULE[n][0] == "pytorch"]


def blocks_of(arm, kind="thirty"):
    return [n for n in numbers() if ir.SCHEDULE[n] == (arm, kind)]


def peaks(arm):
    return [record["blocks"][str(n)]["rss_peak_mib"] for n in blocks_of(arm)]


def and_join(values):
    values = list(values)
    return (
        " and ".join(values) if len(values) <= 2 else ", ".join(values[:-1]) + " and " + values[-1]
    )


def mib(values):
    return and_join(f"{v:,}" for v in values)


def held(ok):
    return "yes" if ok else "no"


def near(value, forecast):
    """«≈» in the spec's forecast, read as within 5 % of it: the capsule's rule, not the spec's.
    A share of the 400 is read by its other part, the questions forecast to differ."""
    return abs(value - forecast) <= 0.05 * forecast


def signed(value):
    return f"{value:+}".replace("-", "−")


def the_400():
    """Block 6 over the four bases at once, as the tool reads one base."""
    return ir.beside(rows, QUALITY)


def at_least_four(rows_=None, n=QUALITY):
    return sum(
        1
        for r in (rows if rows_ is None else rows_)
        if str(n) in r["blocks"] and r["blocks"][str(n)]["shared_of_five"] >= 4
    )


def outcome_text():
    got = record["outcome"]
    if not isinstance(got, dict):
        return got
    if got["variant"] is None:
        return "no INT8 file passes"
    if got["passes"]:
        return f"{got['variant']} passes, {got['ratio_median']:.3f}×"
    return f"{got['variant']} does not pass: {got['speed']}"


def reading_rows():
    fid, int8 = record["fidelity"], record["variants"]["int8"]
    pace, gold = int8["speed"], int8["quality"]
    pooled = gold["pooled"]["expanded"]
    torch_max = max(largest(n) for n in pytorch_blocks())
    # The record rounds p to six places; the sign test's own value is printed.
    p = nr.mcnemar(pace["faster"], pace["slower"])
    return [
        f"| PyTorch's blocks: stage 2's scores | to 1e-6 | the largest difference {torch_max:.3e} |",
        f"| FP32's block 1: the export's fidelity | to 1e-3 | the largest difference"
        f" {fid['max_abs_diff']['max']:.3e}: **{fid['reading']}** |",
        f"| int8's speed on aircargo's thirty | faster on more, sign test p < 0.05, 25 readable"
        f" | {pace['readable']} readable, faster on {pace['faster']}, slower on {pace['slower']},"
        f" p {p:.3g}: **{pace['reading']}** |",
        f"| int8's gold after the expansion | a loss: b > c at p < 0.05, or pooled b − c above 2"
        f" | pooled b {pooled['b_pytorch_only']}, c {pooled['c_variant_only']}, p {pooled['p']}:"
        f" **{gold['reading']}** |",
        f"| The outcome | int8 holds the gold and reads faster | **{outcome_text()}** |",
    ]


def pair_row(name, with_gold, unread, pair):
    if not isinstance(pair, dict):
        return f"| {name} | {with_gold} | {unread} | {pair} | | | | | | |"
    return (
        f"| {name} | {with_gold} | {unread} | {pair['n']} | {pair['hits']['pytorch']}"
        f" | {pair['hits']['int8']} | {pair['b_pytorch_only']} | {pair['c_variant_only']}"
        f" | {pair['p']} | {pair['reading']} |"
    )


def gold_rows(point):
    gold = record["variants"]["int8"]["quality"]
    out = [
        pair_row(NAMES[base], got["with_gold"], got["unresolved"], got[point])
        for base, got in gold["bases"].items()
    ]
    total = sum(got["with_gold"] for got in gold["bases"].values())
    unread = sum(got["unresolved"] for got in gold["bases"].values())
    out.append(pair_row("The three pooled", total, unread, gold["pooled"][point]))
    return out


def fives_row(name, label, got, four):
    diff = got["max_abs_diff"]
    return (
        f"| {name} | {label} | {got['questions']} | {got['same_five']} | {got['same_order']}"
        f" | {four} | {got['shared_of_five_mean']} | {diff['median']:.3e} | {diff['max']:.3e} |"
    )


def fives_rows():
    out = []
    for base in nr.LABELS:
        mine = [r for r in rows if r["base"] == base]
        for n, got in sorted(record["by_base"][base].items(), key=lambda kv: int(kv[0])):
            arm = ir.SCHEDULE[int(n)][0]
            if arm == "pytorch":
                continue
            out.append(fives_row(NAMES[base], f"{n}, {arm}", got, at_least_four(mine, int(n))))
    out.append(fives_row("The four pooled", f"{QUALITY}, int8", the_400(), at_least_four()))
    return out


def block_rows():
    out = []
    for n in numbers():
        got = record["blocks"][str(n)]
        sec = got["seconds"]
        out.append(
            f"| {n} | {got['arm']} | {sec['n']} | {got['started_at'][11:16]}–"
            f"{got['ended_at'][11:16]} | {minutes(n):.1f} | {got['load_sec']}"
            f" | {got['warm_up_sec']} | {sec['median']} | {got['seconds_sum']:,}"
            f" | {got['rss_after_load_mib']:,} | {got['rss_peak_mib']:,} | {got['disturbed']}"
            f" | {got['others_cpu_max']} | {got['swap_mb']['median']:,} |"
        )
    return out


def forecast_rows():
    fid, int8 = record["fidelity"], record["variants"]["int8"]
    pace, gold = int8["speed"], int8["quality"]
    pooled = gold["pooled"]["expanded"]
    gap = pooled["b_pytorch_only"] - pooled["c_variant_only"]
    every, four = the_400(), at_least_four()
    torch_max = max(largest(n) for n in pytorch_blocks())
    fp32 = fid["max_abs_diff"]["max"]
    once = record["attempts"] == {str(n): 1 for n in numbers()} and not record["rejected"]
    torch_min = [minutes(n) for n in blocks_of("pytorch")]
    int8_min = [minutes(n) for n in blocks_of("int8")]
    fp32_min = minutes(blocks_of("fp32")[0])
    hours = minutes(QUALITY) / 60
    passes = isinstance(record["outcome"], dict) and record["outcome"]["passes"]
    return [
        f"| The six blocks pass their gates | {len(numbers())} of 6, each at its first attempt"
        f" | {held(once and len(numbers()) == 6)} |",
        f"| PyTorch gives stage 2's scores to the last bit | the largest difference"
        f" {torch_max:.3e} | {held(torch_max == 0)} |",
        f"| FP32 differs by less than 1e-6 | {fp32:.3e} | {held(fp32 < 1e-6)} |",
        f"| `int8` reads faster, on 30 of 30 | {pace['reading']}, on {pace['faster']} of"
        f" {pace['readable']} | {held(pace['reading'] == 'faster' and pace['faster'] == 30)} |",
        f"| The ratio ≈ 1.8 | {pace['ratio_median']:.3f}"
        f" | {held(near(pace['ratio_median'], 1.8))} |",
        f"| The saving ≈ 11–12 s a question | {pace['saved_sec_median']:.3f} s"
        f" | {held(near(pace['saved_sec_median'], 11) or near(pace['saved_sec_median'], 12))} |",
        f"| PyTorch's ≈ 26 s a question | {pace['pytorch_sec_median']:.3f} s"
        f" | {held(near(pace['pytorch_sec_median'], 26))} |",
        f"| `int8`'s scores move by about a thousandth | the largest difference a question: a"
        f" median {every['max_abs_diff']['median']}, at most {every['max_abs_diff']['max']:.3f}"
        f" | {held(near(every['max_abs_diff']['median'], 0.001))} |",
        f"| Its five stage 2's set on ≈ 85 % of the 400 | {every['same_five']} of 400,"
        f" {every['same_five'] / 4:g} % | {held(near(400 - every['same_five'], 400 * 0.15))} |",
        f"| It shares at least four on ≈ 99 % | {four} of 400, {four / 4:g} %"
        f" | {held(near(400 - four, 400 * 0.01))} |",
        f"| The gold holds, pooled b − c within ± 2 | {gold['reading']}; b"
        f" {pooled['b_pytorch_only']}, c {pooled['c_variant_only']}, b − c {signed(gap)}"
        f" | the gold {held(gold['reading'] == 'holds')}; ± 2 {held(abs(gap) <= 2)} |",
        f"| `int8` passes; blocks 7–11 do not run | {outcome_text()}; blocks 7–11"
        f" {'did not run' if len(numbers()) == 6 else 'ran'}"
        f" | {held(passes and len(numbers()) == 6)} |",
        f"| An INT8 block's peak not below a PyTorch block's: ≈ 3.1–3.2 GB against ≈ 2.9 GB"
        f" | on the thirty {mib(peaks('int8'))} MiB against {mib(peaks('pytorch'))} MiB"
        f" | {held(min(peaks('int8')) >= max(peaks('pytorch')))} |",
        f"| A PyTorch block ≈ 14.5 min | {and_join(f'{m:.1f}' for m in torch_min)} min"
        f" | {held(all(near(m, 14.5) for m in torch_min))} |",
        f"| FP32's block ≈ 13 min | {fp32_min:.1f} min | {held(near(fp32_min, 13))} |",
        f"| An INT8 block on the thirty ≈ 8 min | {and_join(f'{m:.1f}' for m in int8_min)} min"
        f" | {held(all(near(m, 8) for m in int8_min))} |",
        f"| Block 6 ≈ 1.75 h | {hours:.2f} h | {held(near(hours, 1.75))} |",
    ]


def file_rows():
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def test_the_capsule_tables_are_the_records():
    text = CAPSULE.read_text(encoding="utf-8")
    built = reading_rows() + gold_rows("expanded") + gold_rows("ranked") + fives_rows()
    for line in built + block_rows() + forecast_rows() + file_rows():
        assert line in text, line
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)


def prose_phrases():
    """The prose's numbers that come from the record, as the capsule writes them."""
    fid, int8 = record["fidelity"], record["variants"]["int8"]
    pace, pooled = int8["speed"], int8["quality"]["pooled"]["expanded"]
    every, four = the_400(), at_least_four()
    blocks = record["blocks"]
    first, last = blocks["1"], blocks[str(numbers()[-1])]

    def warm(arm):
        return and_join(str(blocks[str(n)]["warm_up_sec"]) for n in blocks_of(arm))

    def after(arm):
        return mib(blocks[str(n)]["rss_after_load_mib"] for n in blocks_of(arm))

    return [
        f"block 1 {first['started_at'][11:16]}–{first['ended_at'][11:16]} UTC, then blocks 2–6"
        f" {blocks['2']['started_at'][11:16]}–{last['ended_at'][11:16]} UTC",
        f"PyTorch's five hold gold on {pooled['hits']['pytorch']} and `int8`'s on"
        f" {pooled['hits']['int8']}, b {pooled['b_pytorch_only']} and c"
        f" {pooled['c_variant_only']}",
        f"faster on {pace['faster']} of {pace['readable']}, a median"
        f" {pace['saved_sec_median']:.3f} s saved of {pace['pytorch_sec_median']:.3f} s, a ratio"
        f" {pace['ratio_median']:.3f}",
        f"`int8`'s five is PyTorch's set on {every['same_five']} of the 400 and PyTorch's list,"
        f" in its order, on {every['same_order']}; it shares at least four on {four}",
        f"differs on {400 - every['same_order']} of the 400 questions: by its set on"
        f" {400 - every['same_five']}, by its order alone on"
        f" {every['same_five'] - every['same_order']}",
        f"FP32's largest difference {fid['max_abs_diff']['max']:.3e}",
        f"a median {every['max_abs_diff']['median']} on the 400, at most"
        f" {every['max_abs_diff']['max']:.3f}",
        f"`int8` peaked at {mib(peaks('int8'))} MiB, PyTorch at {mib(peaks('pytorch'))} MiB",
        f"PyTorch's warm-up took {warm('pytorch')} s, `int8`'s {warm('int8')} s",
        f"after the load PyTorch held {after('pytorch')} MiB, `int8` {after('int8')} MiB",
    ]


def test_the_capsule_prose_is_the_records():
    flat = " ".join(CAPSULE.read_text(encoding="utf-8").split())
    for phrase in prose_phrases():
        assert phrase in flat, phrase
    # what the prose says of those numbers: ONNX scored the thirty the same in blocks 3 and 4
    thirty = [r for r in rows if "3" in r["blocks"]]
    assert len(thirty) == ir.THIRTY
    assert all(r["blocks"]["3"] == r["blocks"]["4"] for r in thirty)
    assert record["by_base"]["aircargo"]["3"] == record["by_base"]["aircargo"]["4"]
    # the five changes: «эталон держится», not «ответы те же» (PLAN, item 5a, F4)
    assert the_400()["same_order"] < 400
    assert "эталон держится" in flat and "ответы те же" in flat
