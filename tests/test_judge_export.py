"""reports/stage2/tools/judge_export.py: the judge's references, reading and committed record."""

from __future__ import annotations

import hashlib
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
    "model": isolated.MODEL,
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
    return isolated.IsolatedReply(
        json.dumps(verdict), isolated.MODEL, {"total_cost_usd": 0.1}, 1.0, SESSION
    )


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
    assert export.REPLIES == judge.REPLIES  # the export counts what the adapter sends
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
        ([(2, 2)] * 11, False, False, True),  # fewer than 12 pairs; one level, so no kappa
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


def test_a_bootstrap_on_one_level_has_no_interval(export) -> None:
    from evaluation.semantic_ruler import RESAMPLES

    interval = export.kappa_interval([(2, 2)] * 3, 3)

    assert interval == {"ci95": None, "resamples_undefined": RESAMPLES}


def test_a_row_holds_identifiers_and_registered_values_only(export) -> None:
    row = {"item_id": "0f", "case_id": "wixqa-simulated-074", "grade": "partial_ok", "cluster": 3}
    assert export.plain(row) == row
    with pytest.raises(SystemExit, match="route holds more than an identifier"):
        export.plain({**row, "route": "Acme bought the startup"})


def test_part_ones_plan_round_trips_takes_its_reading_and_counts(export, tmp_path: Path) -> None:
    cases = [(f"q{n:02d}", f"Question number {n}?", f"Answer {n} [1].") for n in range(1, 13)]
    run = _run(tmp_path / "p1-aircargo-b01", "aircargo", cases)
    plan_dir = tmp_path / "judge"
    planned = ["plan", "--run", f"p1-aircargo-b01={run}", "--retest", "12", "--out", str(plan_dir)]
    assert judge.main(planned) == 0
    text = (ROOT / "docs" / "specs" / "handover-signal.md").read_text(encoding="utf-8")
    export.add_reading(plan_dir, text, "f" * 40)
    plan = json.loads((plan_dir / "plan.json").read_text("utf-8"))  # as `run` reads it
    no_reference = {**VERDICT, "reference": "none"}

    assert judge.run_plan(plan, plan_dir, lambda system, message: _reply(no_reference)) == 24
    out = tmp_path / "out"
    exported = ["export", str(plan_dir), "p1-aircargo-judge", str(out)]
    assert export.main([*exported, "--run", f"p1-aircargo-b01={run}"]) == 0

    record = json.loads((out / "p1-aircargo-judge.json").read_text("utf-8"))
    assert record["status"] == "counted" and record["retest"]["pairs"] == 12
    assert record["retest"]["passes_by_agreement"] and record["retest"]["quadratic_kappa"] is None
    assert record["provenance"]["reading"]["commit"] == "f" * 40
    assert record["provenance"]["references_sha256"] is None
    # A seventh row of a request, with another request's hash: the export reads it and refuses.
    rows = judge._read_jsonl(plan_dir / "verdicts.jsonl")
    extra = [{**rows[0], "status": "invalid"}] * 5
    extra.append({**rows[0], "status": "invalid", "message_sha256": "0" * 64})
    with (plan_dir / "verdicts.jsonl").open("a", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in extra)
    with pytest.raises(ValueError, match="answers no planned request"):
        export.export(plan_dir, "p1-aircargo-judge", out, {"p1-aircargo-b01": run})


def test_the_reference_agreement_is_read_on_the_pairs_of_a_question_with_one(export) -> None:
    items, valid = [], {}
    for number, has_reference in enumerate((True, False)):
        item = {"item_id": f"i{number}", "run": "r", "case_id": f"q{number}"}
        item["has_reference"] = has_reference
        items += [item, {**item, "item_id": f"i{number}-retest", "retest_of": f"i{number}"}]
        verdict = {**VERDICT, "reference": "agrees" if has_reference else "none"}
        valid[f"i{number}"] = valid[f"i{number}-retest"] = verdict

    result = export.stability(export.judge_of({"salt": judge.SALT}), {"items": items}, valid)

    assert result["field_agreement"]["reference"] == {"agree": 1, "of": 1}
    assert result["field_agreement"]["answers_question"] == {"agree": 2, "of": 2}


def test_the_record_holds_ids_classes_and_the_m2_split_but_no_text(export, tmp_path: Path) -> None:
    run = _run(
        tmp_path / "p4-multihoprag-b01",
        "ext_multihoprag",
        [
            ("m1", "Who bought the startup?", "Acme did [1]."),
            ("m2", "Which fee applies?", "I cannot say."),
            ("m3", "Was it announced?", ""),
            ("m4", "Who sold it?", ""),
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
                {"case_id": "m4", "stratum": "null_query", "cluster": 2, "reference_answers": []},
            )
        )
    )
    plan = judge.build_plan(
        {"p4-multihoprag-b01": run},
        judge._references(references),
        retest=1,
        references_sha256=hashlib.sha256(references.read_bytes()).hexdigest(),
    )
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
    assert rows["m4"]["grade"] == "bad" and rows["m4"]["m2"] == "wrong"  # empty: no decline
    assert all("note" not in row for row in rows.values())
    without = record["m2"]["without_reference"]
    assert without["right"]["n"] == 2 and without["right"]["hits"] == without["wrong"]["hits"] == 1
    assert record["m2"]["with_reference"]["agrees"]["hits"] == 1
    assert record["shares"]["good"]["clusters"] == 3
    assert record["retest"]["pairs"] == 1 and record["replies"]["cost_usd"] > 0
    # One retest pair of the 12 the rule needs: the plan's numbers are not evidence.
    assert record["status"] == "NOT_EVIDENCE"
    text = (out / "p4-multihoprag-judge.json").read_text("utf-8")
    assert "Acme" not in text and "Who bought" not in text and "fees.md" not in text

    command = ["export", str(plan_dir), "p4-multihoprag-judge", str(out)]
    command += ["--run", f"p4-multihoprag-b01={run}", "--references", str(references)]
    assert export.main(command) == 3
    other = tmp_path / "other.jsonl"
    other.write_text(references.read_text("utf-8") + "\n", "utf-8")
    with pytest.raises(SystemExit, match="frozen with"):
        export.export(plan_dir, "x", out, {"p4-multihoprag-b01": run}, other)
    other.write_text(references.read_text("utf-8") * 2, "utf-8")
    with pytest.raises(SystemExit, match="twice"):
        export.export(plan_dir, "x", out, {"p4-multihoprag-b01": run}, other)
    # The file's hash matches, the plan's own word on a reference does not: refused.
    edited = json.loads((plan_dir / "plan.json").read_text("utf-8"))
    for item in edited["items"]:
        if item["case_id"] == "m3":  # the empty answer: no request reads its reference
            item["has_reference"] = False
    (plan_dir / "plan.json").write_text(json.dumps(edited), "utf-8")
    with pytest.raises(SystemExit, match="disagree"):
        export.export(plan_dir, "x", out, {"p4-multihoprag-b01": run}, references)


def test_a_plan_that_withheld_its_references_gives_m1_and_no_m2(export, tmp_path: Path) -> None:
    run = _run(
        tmp_path / "p4-multihoprag-b01",
        "ext_multihoprag",
        [
            ("m1", "Who bought the startup?", "Acme did [1]."),
            ("m2", "Which fee applies?", "Ten [2]."),
        ],
    )
    references = tmp_path / "references.jsonl"
    references.write_text(
        json.dumps(
            {
                "case_id": "m1",
                "stratum": "inference_query",
                "cluster": 0,
                "reference_answers": ["X."],
            }
        )
        + "\n"
        + json.dumps(
            {"case_id": "m2", "stratum": "null_query", "cluster": 1, "reference_answers": []}
        )
        + "\n"
    )
    plan = judge.build_plan(
        {"p4-multihoprag-b01": run},
        {},
        retest=1,
        references_sha256=hashlib.sha256(references.read_bytes()).hexdigest(),
        withheld=True,
    )
    plan_dir = tmp_path / "judge"
    plan_dir.mkdir()
    (plan_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
    sent = []

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        sent.append(message)
        return _reply({**VERDICT, "reference": "none"})

    judge.run_plan(plan, plan_dir, send)
    out = tmp_path / "out"

    record = export.export(plan_dir, "m1", out, {"p4-multihoprag-b01": run}, references)

    assert len(sent) == 3 and all("REFERENCE ANSWER:\nnone\n" in m for m in sent)
    rows = {row["case_id"]: row for row in map(json.loads, (out / "m1.cases.jsonl").open())}
    assert rows["m1"]["grade"] == rows["m2"]["grade"] == "good"
    assert rows["m1"]["stratum"] == "inference_query" and rows["m2"]["cluster"] == 1
    assert not any(row["has_reference"] or "m2" in row for row in rows.values())
    assert "m2" not in record and record["provenance"]["references_withheld"] is True
    assert record["retest"]["field_agreement"]["reference"]["of"] == 0
    # A plan that says it carried the file's references must hold them in its requests.
    edited = json.loads((plan_dir / "plan.json").read_text("utf-8"))
    edited["references_withheld"] = False
    (plan_dir / "plan.json").write_text(json.dumps(edited), "utf-8")
    with pytest.raises(SystemExit, match="disagree"):
        export.export(plan_dir, "x", out, {"p4-multihoprag-b01": run}, references)
