"""scripts/chat_answer_judge.py: each chat answer graded against the documents it was given."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.prompts import build_qa_prompt
from evaluation import isolated_request as isolated
from llm.providers.base import flatten_messages
from scripts import chat_answer_judge as judge

SESSION = {
    "cli_version": "9.9.9",
    "model": "fixture-reported-model",
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}
DOCS = [
    {
        "page_content": "[Fees › Storage]\nStorage costs ten a day.",
        "metadata": {"source": "fees.md"},
    },
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
    "note": "ok",
}


def _run(folder: Path, cases: list[tuple[str, str, str, list]]) -> Path:
    """A stand's run record: one answer prompt per case, saved as live_api.py saves it."""
    (folder / "prompts").mkdir(parents=True)
    (folder / "cases").mkdir()
    (folder / "launch.json").write_text(
        json.dumps({"code_sha": "abc", "tenant": "toy", "model": "m"}), encoding="utf-8"
    )
    for index, (case_id, question, answer, docs) in enumerate(cases, start=1):
        prompt = flatten_messages([{"role": "user", "content": build_qa_prompt(question, docs)}])
        (folder / "prompts" / f"{2 * index - 1:03d}-stream.txt").write_text(prompt, "utf-8")
        (folder / "prompts" / f"{2 * index:03d}-generate.txt").write_text("self-eval", "utf-8")
        row = {
            "case_id": case_id,
            "question": question,
            "answer": answer,
            "events": [{"type": "result", "answer": answer, "route": "auto"}],
        }
        (folder / "cases" / f"{index:02d}-{case_id}.json").write_text(json.dumps(row), "utf-8")
    return folder


def test_the_saved_prompt_gives_back_the_question_and_the_numbered_documents() -> None:
    prompt = flatten_messages([{"role": "user", "content": build_qa_prompt("Fee?", DOCS)}])

    question, documents = judge.read_prompt(prompt)

    assert question == "Fee?"
    assert documents == [
        ("fees.md", "[Fees › Storage]\nStorage costs ten a day."),
        ("claims.md", "Claims are filed within 14 days."),
    ]
    empty = flatten_messages([{"role": "user", "content": build_qa_prompt("Fee?", [])}])
    assert judge.read_prompt(empty) == ("Fee?", [])
    with pytest.raises(ValueError, match="QA_PROMPT_V3"):
        judge.read_prompt("USER:\nsomething else")


def test_marks_that_name_no_listed_document_are_counted_apart() -> None:
    assert judge.marks("Ten a day [1]. Fourteen days [2, 5].", 2) == (2, 1)
    assert judge.marks("No marks.", 2) == (0, 0)


def test_a_planned_run_is_graded_summarised_and_retested(tmp_path: Path) -> None:
    run = _run(
        tmp_path / "toy-run",
        [
            ("q1", "How much is storage?", "Ten a day [1].", DOCS),
            ("q2", "How do I file a claim?", "", DOCS),
            ("warmup-3", "Hello?", "Hi.", DOCS),
        ],
    )
    plan = judge.build_plan({"toy": run}, {"q1": ["Storage is ten a day."]}, retest=1)

    asked = [item for item in plan["items"] if "message" in item]
    assert [item["case_id"] for item in asked] == ["q1", "q1"]
    assert asked[0]["marks_listed"] == 1 and asked[0]["has_reference"]
    assert "REFERENCE ANSWER:\nStorage is ten a day." in asked[0]["message"]
    assert "holds 1 reference marks" in asked[0]["message"]
    assert "[2] source=claims.md\nClaims are filed within 14 days." in asked[0]["message"]
    assert plan["runs"]["toy"]["tenant"] == "toy"

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        assert system_prompt == judge.SYSTEM_PROMPT
        return isolated.IsolatedReply(json.dumps(VERDICT), "m", {}, 1.0, SESSION)

    out = tmp_path / "judge"
    out.mkdir()
    assert judge.run_plan(plan, out, send) == 2
    summary = judge.summarize(plan, judge._read_jsonl(out / "verdicts.jsonl"))

    toy = summary["per_run"]["toy"]
    assert toy["answers"] == 2 and toy["graded"] == 2 and toy["missing"] == 0
    assert toy["classes"] == {"good": 1, "partial_ok": 0, "bad": 1}  # the empty answer is bad
    assert toy["marks_listed"] == 1 and toy["marks_supported"] == 1
    assert toy["reference"] == {"agrees": 1}
    assert summary["retest"] == {"pairs": 1, "same_class": 1, "quadratic_kappa": 1.0}


def test_a_verdict_must_fit_its_request() -> None:
    text = json.dumps(VERDICT)
    assert judge.parse_verdict(text, 1, True)["reference"] == "agrees"
    with pytest.raises(judge.VerdictError, match="citations_supported"):
        judge.parse_verdict(text, 0, True)
    with pytest.raises(judge.VerdictError, match="reference"):
        judge.parse_verdict(text, 1, False)
    no_reference = json.dumps({**VERDICT, "reference": "none"})
    assert judge.parse_verdict(no_reference, 1, False)["reference"] == "none"


def test_quadratic_kappa_reads_agreement_on_an_ordinal_scale() -> None:
    assert judge.quadratic_kappa([(0, 0), (1, 1), (2, 2)], 3) == 1.0
    assert judge.quadratic_kappa([], 3) is None
    assert judge.quadratic_kappa([(0, 2), (2, 0)], 3) < 0
