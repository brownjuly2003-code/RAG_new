"""reports/stage2/tools/judge_export.py: the judge's references, reading and committed record."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from agent.prompts import build_qa_prompt
from evaluation import isolated_request as isolated
from llm.providers.base import flatten_messages
from scripts import chat_answer_judge as judge

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage2" / "tools"
SESSION = {
    "cli_version": "9.9.9",
    "model": "fixture-reported-model",
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}
DOCS = [
    {"page_content": "Storage costs ten a day.", "metadata": {"source": "fees.md"}},
    {"page_content": "Claims are filed within 14 days.", "metadata": {"source": "claims.md"}},
]
VERDICT = {
    "claims_total": 1,
    "claims_supported": 1,
    "context_has_answer": True,
    "answers_question": "full",
    "citations_supported": 1,
    "reference": "agrees",
    "defect": "none",
    "note": "the judge's own sentence",
}


@pytest.fixture(scope="module")
def export():
    spec = importlib.util.spec_from_file_location("judge_export", TOOLS / "judge_export.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.path[:] = [p for p in sys.path if p != str(TOOLS)]


def _run(folder: Path, tenant: str, cases: list[tuple[str, str, str]]) -> Path:
    """A stand's answers run: one stream prompt per case, saved as live_api.py saves it."""
    (folder / "prompts").mkdir(parents=True)
    (folder / "cases").mkdir()
    (folder / "launch.json").write_text(
        json.dumps({"code_sha": "abc", "tenant": tenant, "model": "m"}), encoding="utf-8"
    )
    for index, (case_id, question, answer) in enumerate(cases, start=1):
        prompt = flatten_messages([{"role": "user", "content": build_qa_prompt(question, DOCS)}])
        (folder / "prompts" / f"{index:03d}-stream.txt").write_text(prompt, "utf-8")
        row = {
            "case_id": case_id,
            "question": question,
            "answer": answer,
            "events": [{"type": "result", "answer": answer, "route": "auto"}],
        }
        (folder / "cases" / f"{index:02d}-{case_id}.json").write_text(json.dumps(row), "utf-8")
    return folder


def _reply(verdict: dict) -> isolated.IsolatedReply:
    return isolated.IsolatedReply(json.dumps(verdict), "m", {"total_cost_usd": 0.1}, 1.0, SESSION)


def test_the_references_hold_an_answer_only_where_the_question_has_one(export) -> None:
    cases = [
        {"case_id": "m1", "stratum": "inference_query", "gold_sources": ["a", "b"]},
        {"case_id": "m2", "stratum": "inference_query", "gold_sources": ["b"]},
        {"case_id": "m3", "stratum": "inference_query", "gold_sources": ["c"]},
        {"case_id": "m4", "stratum": "null_query", "gold_sources": []},
    ]
    for case in cases:
        case["reference_answers"] = [f"answer of {case['case_id']}"]

    rows = {row["case_id"]: row for row in export.reference_rows("multihoprag", cases)}

    assert rows["m1"]["reference_answers"] == ["answer of m1"]
    assert rows["m4"]["reference_answers"] == []  # the dataset's answer is no reference
    assert rows["m1"]["cluster"] == rows["m2"]["cluster"]  # joined by the gold document b
    assert len({rows[c]["cluster"] for c in ("m1", "m3", "m4")}) == 3
    with pytest.raises(SystemExit, match="no reference"):
        export.reference_rows("multihoprag", [{**cases[0], "reference_answers": [" "]}])
    with pytest.raises(SystemExit, match="external"):
        export.reference_rows("aircargo", cases)


def test_conditionalqa_clusters_by_document_and_keeps_the_condition_flag(export) -> None:
    def case(case_id, stratum, document, conditional=False):
        answerable = stratum == "answerable"
        return {
            "case_id": case_id,
            "stratum": stratum,
            "document": document,
            "gold_sources": [document] if answerable else [],
            "evidence_groups": [{"alternatives": []}] if answerable else [],
            "unresolved_evidence": 0,
            "reference_answers": ["yes"] if answerable else [],
            "conditional": conditional,
        }

    rows = {
        row["case_id"]: row
        for row in export.reference_rows(
            "conditionalqa",
            [
                case("c1", "answerable", "doc-a", conditional=True),
                case("c2", "answerable", "doc-a"),
                case("c3", "not_answerable", "doc-a"),
            ],
        )
    }

    assert rows["c1"]["cluster"] == rows["c2"]["cluster"] != rows["c3"]["cluster"]
    assert rows["c1"]["conditional"] and not rows["c2"]["conditional"]
    assert rows["c3"]["reference_answers"] == []


def test_the_reading_is_the_handover_plans_section_and_lands_before_any_reply(
    export, tmp_path: Path
) -> None:
    text = (ROOT / "docs" / "specs" / "handover-signal.md").read_text(encoding="utf-8")
    section = export.reading_text(text)
    assert section.startswith("In the chat a marked answer is still shown")
    assert "**worth wiring:**" in section and "\n## " not in section

    run = _run(tmp_path / "p1-aircargo-b01", "aircargo", [("q1", "Fee?", "Ten [1].")])
    plan_dir = tmp_path / "judge"
    plan_dir.mkdir()
    plan = judge.build_plan({"p1-aircargo-b01": run}, {}, retest=0)
    (plan_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")

    frozen = export.add_reading(plan_dir, text, "f" * 40)

    assert frozen["commit"] == "f" * 40 and frozen["text"] == section
    assert json.loads((plan_dir / "plan.json").read_text("utf-8"))["reading"] == frozen
    with pytest.raises(SystemExit, match="already"):
        export.add_reading(plan_dir, text, "f" * 40)
    (plan_dir / "verdicts.jsonl").write_text('{"item_id": "x", "status": "valid"}\n')
    with pytest.raises(SystemExit, match="replies"):
        export.add_reading(plan_dir, text, "f" * 40)


def test_a_request_counts_from_its_first_six_replies(export) -> None:
    rows = [{"item_id": "a", "status": "invalid"} for _ in range(6)]
    rows += [{"item_id": "a", "status": "unavailable"}, {"item_id": "a", "status": "valid"}]
    rows += [{"item_id": "b", "status": "valid"}]

    kept, past = export.counted(rows)

    assert past == 1
    assert [row["status"] for row in kept if row["item_id"] == "a"].count("valid") == 0
    assert {"item_id": "b", "status": "valid"} in kept


@pytest.mark.parametrize(
    ("pairs", "passed", "by_kappa", "by_agreement"),
    [
        ([(2, 2)] * 14 + [(2, 1)], True, False, True),  # kappa 0.0 at 14 of 15
        ([(2, 2)] * 5 + [(1, 1)] * 5 + [(0, 0)] * 5, True, True, True),
        ([(2, 2)] * 13 + [(2, 0), (1, 1)], False, False, False),  # one pair two steps apart
        ([(2, 2)] * 11, False, True, True),  # fewer than 12 pairs
    ],
)
def test_the_stability_rule_reads_kappa_or_agreement_on_enough_pairs(
    export, pairs, passed, by_kappa, by_agreement
) -> None:
    scale = ("bad", "partial_ok", "good")
    items, valid = [], {}
    for number, (a, b) in enumerate(pairs):
        items.append({"item_id": f"i{number}", "run": "r", "case_id": f"q{number}"})
        items.append({"item_id": f"i{number}-retest", "retest_of": f"i{number}"})
        for item_id, level in ((f"i{number}", a), (f"i{number}-retest", b)):
            valid[item_id] = {
                **VERDICT,
                "answers_question": ("no", "partial", "full")[level],
                "claims_supported": 1 if level else 0,
            }
    graded = export.judge_of({"salt": judge.SALT})

    result = export.stability(graded, {"items": items}, valid)

    assert [scale[a] for a, _ in result["pairs_list"]] == [scale[a] for a, _ in pairs]
    assert result["passed"] is passed
    assert result["passes_by_kappa"] is by_kappa
    assert result["passes_by_agreement"] is by_agreement


def test_the_record_holds_ids_classes_and_the_m2_split_but_no_text(export, tmp_path: Path) -> None:
    run = _run(
        tmp_path / "p4-multihoprag-b01",
        "ext_multihoprag",
        [
            ("m1", "Who bought the startup?", "Acme did [1]."),
            ("m2", "Which fee applies?", "I cannot say."),
            ("m3", "Was it announced?", ""),
        ],
    )
    references = tmp_path / "references.jsonl"
    references.write_text(
        "".join(
            json.dumps(row) + "\n"
            for row in (
                {
                    "case_id": "m1",
                    "stratum": "inference_query",
                    "cluster": 0,
                    "reference_answers": ["Acme."],
                },
                {"case_id": "m2", "stratum": "null_query", "cluster": 1, "reference_answers": []},
                {
                    "case_id": "m3",
                    "stratum": "inference_query",
                    "cluster": 0,
                    "reference_answers": ["Yes."],
                },
            )
        )
    )
    plan = judge.build_plan({"p4-multihoprag-b01": run}, judge._references(references), retest=1)
    plan_dir = tmp_path / "judge"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        if "REFERENCE ANSWER:\nnone\n" not in message:
            return _reply(VERDICT)
        return _reply(
            {
                **VERDICT,
                "answers_question": "declined",
                "reference": "none",
                "context_has_answer": False,
                "claims_total": 0,
                "claims_supported": 0,
                "citations_supported": 0,
            }
        )

    judge.run_plan(plan, plan_dir, send)
    out = tmp_path / "out"

    record = export.export(
        plan_dir, "p4-multihoprag-judge", out, {"p4-multihoprag-b01": run}, references
    )

    rows = {
        row["case_id"]: row
        for row in map(json.loads, (out / "p4-multihoprag-judge.cases.jsonl").open())
    }
    assert rows["m1"]["grade"] == "good" and rows["m1"]["m2"] == "agrees"
    assert rows["m2"]["m2"] == "right"  # no reference: a decline is right
    assert rows["m3"]["grade"] == "bad" and rows["m3"]["m2"] == "empty_answer"
    assert all("note" not in row for row in rows.values())
    assert record["m2"]["without_reference"]["right"]["n"] == 1
    assert record["m2"]["with_reference"]["agrees"]["hits"] == 1
    assert record["shares"]["good"]["clusters"] == 2
    assert record["retest"]["pairs"] == 1 and record["replies"]["cost_usd"] > 0
    text = (out / "p4-multihoprag-judge.json").read_text("utf-8")
    assert "Acme" not in text and "Who bought" not in text and "fees.md" not in text
