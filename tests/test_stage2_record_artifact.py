"""Stage 2's part 5: the combined record of the four corpora, derived again from the records."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/stage2/tools"
JUDGE = ROOT / "reports/stage2/5e308fe"
RETRIEVAL = ROOT / "reports/stage2/retrieval-20261021"
EXTERNAL = ROOT / "reports/stage2/external-answers-20261023"
RECORD = JUDGE / "stage2-record.json"
CAPSULE = ROOT / "docs/evidence/stage2-record.md"
CODE = "5e308fe48cca0955c3007057a574a425f71e2a6a"
BASES = ("conditionalqa", "wixqa", "multihoprag")
CORPORA = ("aircargo", *BASES)
NAMES = {
    "aircargo": "aircargo",
    "conditionalqa": "ConditionalQA",
    "wixqa": "WixQA",
    "multihoprag": "MultiHop-RAG",
}
CLASSES = ("good", "partial_ok", "bad")
# The judge's plans: (record, requests, status). One fails the stability rule.
PLANS = {
    "p1-aircargo-judge": (115, "counted"),
    "p2-aircargo-context-judge": (130, "counted"),
    "p4-conditionalqa-judge-m1": (115, "counted"),
    "p4-wixqa-judge-m1": (115, "counted"),
    "p4-multihoprag-judge-m1": (115, "counted"),
    "p4-conditionalqa-judge-m2": (115, "counted"),
    "p4-wixqa-judge-m2": (115, "counted"),
    "p4-multihoprag-judge-m2": (115, "NOT_EVIDENCE"),
}


def load(folder, name):
    record = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (folder / f"{name}.cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return record, rows


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def capsule():
    return CAPSULE.read_text(encoding="utf-8")


def pct(value):
    return f"{100 * value:.1f}"


def cell(entry):
    """A share as the capsule prints it: hits/n (share %; the read 95 % interval)."""
    low, high = entry["read95"]
    return f"{entry['hits']}/{entry['n']} ({pct(entry['share'])} %; {pct(low)}–{pct(high)})"


def retest(entry):
    return (
        f"{entry['agree']}/{entry['pairs']} agree, {entry['two_steps_apart']} two steps apart, "
        f"κ {entry['quadratic_kappa']:.2f}"
    )


def difference(entry):
    low, high = entry["ci95"]
    found = "detected" if entry["detected"] else "not detected"
    return f"{100 * entry['difference']:+.1f} pp ({100 * low:+.1f} to {100 * high:+.1f}), {found}"


def table_lines(record):
    """Every table row of the capsule, built from the record."""
    corpora = record["corpora"]
    lines = []
    for corpus in CORPORA:
        m1 = corpora[corpus]["m1"]
        classes = " | ".join(cell(m1["classes"][name]) for name in CLASSES)
        lines.append(f"| {NAMES[corpus]} | {classes} | {retest(m1['retest'])} |")
    for corpus in CORPORA:
        m1 = corpora[corpus]["m1"]
        unlisted = m1["marks_unlisted"]
        lines.append(
            f"| {NAMES[corpus]} | {cell(m1['marks_supported'])} | {cell(m1['claims_supported'])} "
            f"| {cell(m1['with_defect'])} | {unlisted['marks']} in {unlisted['answers']} "
            f"| {m1['answer_without_context']} |"
        )
    for base in ("conditionalqa", "multihoprag"):
        for stratum, classes in corpora[base]["m1"]["by_stratum"].items():
            counts = " | ".join(str(classes[name]["hits"]) for name in CLASSES)
            lines.append(
                f"| {NAMES[base]} | `{stratum}` | {classes['good']['n']} | {counts} "
                f"| {cell(classes['good'])} |"
            )
    for base in BASES:
        against = record["aircargo_against"][base]
        compared = " | ".join(difference(against[name]) for name in CLASSES)
        lines.append(f"| {NAMES[base]} | {compared} |")
    keywords = corpora["aircargo"]["m2_keywords"]
    lines.append(
        "| aircargo, keywords (weak gold) | 100 | "
        + ", ".join(f"{name} {keywords[name]['hits']}" for name in ("FULL", "PART", "MISS"))
        + f" | {cell(keywords['FULL'])} | — |"
    )
    for base in ("conditionalqa", "wixqa"):
        m2 = corpora[base]["m2"]
        held = m2["with_reference"]
        named = ("agrees", "partial", "disagrees", "declined")
        counts = ", ".join(f"{name} {held[name]['hits']}" for name in named)
        without = m2["without_reference"]
        right = (
            f"right {without['right']['hits']}/{without['right']['n']}"
            if without["right"]["n"]
            else "—"
        )
        lines.append(
            f"| {NAMES[base]} | {held['agrees']['n']} | {counts} | {cell(held['agrees'])} "
            f"| {right} |"
        )
    for group in ("conditional", "not_conditional"):
        split = corpora["conditionalqa"]["m2"][group]
        lines.append(
            f"| ConditionalQA, {group.replace('_', ' ')} | {split['questions']} | "
            + ", ".join(
                f"{name} {split['m2'][name]['hits']}"
                for name in ("agrees", "partial", "disagrees", "declined")
            )
            + f" | {cell(split['m2']['agrees'])} | — |"
        )
    for base in ("conditionalqa", "wixqa"):
        sway = corpora[base]["sway"]
        table = sway["m1_by_m2"]
        rows = " / ".join(" · ".join(str(table[a][b]) for b in CLASSES) for a in CLASSES)
        lines.append(
            f"| {NAMES[base]} | {sway['answers']} | {sway['agree']} | {sway['two_steps_apart']} "
            f"| {sway['quadratic_kappa']:.2f} | {rows} |"
        )
    m3 = corpora["aircargo"]["m3"]
    for run in ("aircargo", "aircargo-gr"):
        levels = m3[run]["levels"]
        lines.append(
            f"| {run} | {m3[run]['questions']} | "
            + " | ".join(str(levels[name]["hits"]) for name in ("full", "partial", "none"))
            + f" | {cell(m3[run]['holds_the_answer'])} |"
        )
    coverage = {"conditionalqa": "all_evidence_coverage", "wixqa": "gold_article"}
    coverage["multihoprag"] = "all_evidence_coverage"
    for base in BASES:
        points = corpora[base]["m3"]["points"]
        metric = coverage[base]
        lines.append(
            f"| {NAMES[base]} | `{metric}` | {corpora[base]['m3']['with_gold']} | "
            + " | ".join(cell(points[point][metric]) for point in ("pool", "ranked", "sent"))
            + " |"
        )
    for corpus in CORPORA:
        m4, m5 = corpora[corpus]["m4"], corpora[corpus]["m5"]["all"]
        lines.append(
            f"| {NAMES[corpus]} | {cell(m4['human'])} | {m5['total_sec']['median']:.1f} "
            f"| {m5['first_token_sec']['median']:.1f} | {corpora[corpus]['parity']['same']}/"
            f"{corpora[corpus]['parity']['of']} |"
        )
    for name in PLANS:
        plan = json.loads((JUDGE / f"{name}.json").read_text(encoding="utf-8"))
        lines.append(
            f"| `{name}` | {plan['requests_valid']} | ${plan['replies']['cost_usd']:.2f} "
            f"| {retest(plan['retest'])} | {plan['status']} |"
        )
    return lines


def test_the_record_is_the_tools_output_of_the_committed_records(record):
    spec = importlib.util.spec_from_file_location("stage2_record", TOOLS / "stage2_record.py")
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(tool)
        assert tool.build() == record
    finally:
        sys.path[:] = [p for p in sys.path if p not in (str(TOOLS), str(ROOT))]
    assert record["stand"] == CODE
    for path, digest in record["inputs"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert set(record["corpora"]) == set(CORPORA)


def test_each_plan_is_counted_or_not_evidence_by_the_stability_rule():
    for name, (requests, status) in PLANS.items():
        plan, rows = load(JUDGE, name)
        test = plan["retest"]
        assert plan["status"] == status and plan["requests_valid"] == requests
        assert plan["replies"]["models"] == {"claude-opus-5-5": requests}
        assert plan["missing"] == [] and all(not row["missing"] for row in rows)
        pairs = test["pairs_list"]
        assert test["pairs"] == len(pairs) == test["planned"] == 15
        agree = sum(first == second for first, second in pairs)
        apart = sum(abs(first - second) == 2 for first, second in pairs)
        assert (test["agree"], test["two_steps_apart"]) == (agree, apart)
        kappa = test["quadratic_kappa"]
        by_agreement = agree >= 13 and apart == 0
        assert test["passed"] is ((kappa is not None and kappa >= 0.6) or by_agreement)
        assert (status == "counted") is test["passed"]
        if name.startswith("p4-"):
            assert plan["provenance"]["references_withheld"] is name.endswith("-m1")


def test_no_counted_question_has_a_path_break():
    for name in ("p1-aircargo", "p2-aircargo"):
        record, rows = load(RETRIEVAL, name)
        assert not record["aggregate"]["path_breaks"]
        assert all(not row["path_breaks"] for row in rows)
    for base in BASES:
        for part in ("p2", "p4"):
            record, rows = load(EXTERNAL, f"{part}-{base}")
            assert not record["aggregate"]["path_breaks"]
            assert len(rows) == 100 and all(not row["path_breaks"] for row in rows)


@pytest.mark.parametrize("corpus", CORPORA)
def test_m1_and_its_other_parts_are_counted_from_the_rows(record, corpus):
    name = "p1-aircargo-judge" if corpus == "aircargo" else f"p4-{corpus}-judge-m1"
    _, rows = load(JUDGE, name)
    m1 = record["corpora"][corpus]["m1"]
    graded = [row for row in rows if row["grade"] is not None]
    assert len(graded) == m1["graded"] == 100
    assert {k: v["hits"] for k, v in m1["classes"].items()} == {
        name: sum(row["grade"] == name for row in graded) for name in CLASSES
    }
    marks = m1["marks_supported"]
    assert marks["hits"] == sum(row["citations_supported"] for row in graded)
    assert marks["n"] == sum(row["marks_listed"] for row in graded)
    claims = m1["claims_supported"]
    assert claims["hits"] == sum(row["claims_supported"] for row in graded)
    assert claims["n"] == sum(row["claims_total"] for row in graded)
    assert m1["defects"] == dict(Counter(row["defect"] for row in graded))
    assert m1["with_defect"]["hits"] == sum(row["defect"] != "none" for row in graded)
    assert m1["marks_unlisted"] == {
        "marks": sum(row["marks_unlisted"] for row in rows),
        "answers": sum(row["marks_unlisted"] > 0 for row in rows),
    }
    assert m1["answer_without_context"] == sum(
        row["grade"] == "bad"
        and row["answers_question"] in ("full", "partial")
        and not row["context_has_answer"]
        for row in graded
    )


@pytest.mark.parametrize("base", BASES)
def test_m2_and_the_sway_are_counted_from_the_rows(record, base):
    _, first = load(JUDGE, f"p4-{base}-judge-m1")
    _, second = load(JUDGE, f"p4-{base}-judge-m2")
    m2 = record["corpora"][base]["m2"]
    held = Counter(row["m2"] for row in second if row["has_reference"])
    without = Counter(row["m2"] for row in second if not row["has_reference"])
    assert {k: v["hits"] for k, v in m2["with_reference"].items() if v["hits"]} == dict(held)
    assert {k: v["hits"] for k, v in m2["without_reference"].items() if v["hits"]} == dict(without)
    assert all(row.get("m2") is None and not row["has_reference"] for row in first)
    sway = record["corpora"][base]["sway"]
    grades = {row["case_id"]: row["grade"] for row in second}
    pairs = Counter((row["grade"], grades[row["case_id"]]) for row in first)
    assert {(a, b): sway["m1_by_m2"][a][b] for a in CLASSES for b in CLASSES if pairs[a, b]} == {
        key: value for key, value in pairs.items()
    }
    assert sway["agree"] == sum(pairs[name, name] for name in CLASSES)
    assert sway["status"] == ("NOT_EVIDENCE" if base == "multihoprag" else "counted")
    assert m2["status"] == sway["status"]


def test_aircargo_against_each_external_base_reads_the_intervals(record):
    for base in BASES:
        for name in CLASSES:
            entry = record["aircargo_against"][base][name]
            low, high = entry["ci95"]
            assert entry["detected"] is (low > 0 or high < 0)
            mine = record["corpora"]["aircargo"]["m1"]["classes"][name]["share"]
            theirs = record["corpora"][base]["m1"]["classes"][name]["share"]
            assert entry["difference"] == round(mine - theirs, 4)
            assert entry["status"] == "counted"


def test_the_capsule_prints_the_record(record, capsule):
    lines = set(capsule.splitlines())
    missing = [line for line in table_lines(record) if line not in lines]
    assert not missing, missing
    flat = " ".join(capsule.split())
    for phrase in (
        "`p4-multihoprag-judge-m2` failed the stability rule",
        "MultiHop-RAG's M2 and the reference's sway there are `NOT_EVIDENCE`",
        "One of MultiHop-RAG's 45 clusters holds 49 of its 100 questions",
        "No person graded an answer",
    ):
        assert phrase in flat
