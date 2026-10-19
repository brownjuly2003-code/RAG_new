"""scripts/context_judge.py: whether the context a search sent holds the answer (M3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent.prompts import build_qa_prompt
from evaluation import isolated_request as isolated
from llm.providers.base import flatten_messages
from scripts import context_judge as judge

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
VERDICT = {"context_answer": "full", "documents_with_answer": [1], "note": "ok"}


def _run(folder: Path, cases: list[tuple[str, str, list]]) -> Path:
    """A retrieval run as live_retrieval.py writes one: the prompt the chat would send."""
    (folder / "retrieval").mkdir(parents=True)
    (folder / "launch.json").write_text(json.dumps({"code_sha": "abc", "tenant": "toy"}), "utf-8")
    for index, (case_id, question, docs) in enumerate(cases, start=1):
        prompt = flatten_messages([{"role": "user", "content": build_qa_prompt(question, docs)}])
        record = {
            "case_id": case_id,
            "index": index,
            "question": question,
            "prompt": {"sha256": hashlib.sha256(prompt.encode()).hexdigest(), "text": prompt},
        }
        (folder / "retrieval" / f"{index:03d}-{case_id}.json").write_text(
            json.dumps(record, ensure_ascii=False), "utf-8"
        )
    return folder


def test_a_planned_run_is_graded_summarised_and_retested(tmp_path: Path) -> None:
    run = _run(
        tmp_path / "toy-run",
        [("q1", "How much is storage?", DOCS), ("q2", "Where is the office?", [])],
    )
    plan = judge.build_plan({"toy": run}, retest=1)

    asked = [item for item in plan["items"] if "message" in item]
    assert [item["case_id"] for item in asked] == ["q1", "q1"]
    assert asked[0]["documents"] == 2
    assert "QUESTION:\nHow much is storage?" in asked[0]["message"]
    assert "[2] source=claims.md\nClaims are filed within 14 days." in asked[0]["message"]
    assert plan["runs"]["toy"]["tenant"] == "toy"

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        assert system_prompt == judge.SYSTEM_PROMPT
        return isolated.IsolatedReply(json.dumps(VERDICT), "m", {}, 1.0, SESSION)

    out = tmp_path / "judge"
    out.mkdir()
    assert judge.run_plan(plan, out, send) == 2
    summary = judge.summarize(plan, judge.answer_judge._read_jsonl(out / "verdicts.jsonl"))

    toy = summary["per_run"]["toy"]
    assert toy["contexts"] == 2 and toy["graded"] == 2 and toy["missing"] == 0
    # The context without documents holds nothing, and costs no request.
    assert toy["levels"] == {"none": 1, "partial": 0, "full": 1}
    assert toy["context_has_answer"] == 1 and toy["empty_contexts"] == 1
    assert summary["retest"] == {"pairs": 1, "same_level": 1, "quadratic_kappa": 1.0}
    assert [(c["case_id"], c["level"]) for c in summary["per_case"]] == [
        ("q1", "full"),
        ("q2", "none"),
    ]


def test_a_record_whose_prompt_is_not_its_hash_is_refused(tmp_path: Path) -> None:
    run = _run(tmp_path / "toy-run", [("q1", "How much is storage?", DOCS)])
    path = next((run / "retrieval").glob("*.json"))
    record = json.loads(path.read_text("utf-8"))
    record["prompt"]["sha256"] = "0" * 64
    path.write_text(json.dumps(record), "utf-8")
    with pytest.raises(ValueError, match="hash"):
        judge.build_plan({"toy": run})


def test_a_verdict_must_fit_its_request() -> None:
    assert judge.parse_verdict(json.dumps(VERDICT), 2)["context_answer"] == "full"
    fenced = "```json\n" + json.dumps(VERDICT) + "\n```"
    assert judge.parse_verdict(fenced, 2)["documents_with_answer"] == [1]
    none = {"context_answer": "none", "documents_with_answer": [], "note": "no"}
    assert judge.parse_verdict(json.dumps(none), 2)["context_answer"] == "none"
    for wrong, match in (
        ({**VERDICT, "documents_with_answer": [3]}, "names no listed"),
        ({**VERDICT, "documents_with_answer": [True]}, "names no listed"),
        ({**VERDICT, "documents_with_answer": []}, "does not fit"),
        ({**none, "documents_with_answer": [1]}, "does not fit"),
        ({**VERDICT, "documents_with_answer": [1, 1]}, "does not fit"),
        ({**VERDICT, "context_answer": "some"}, "registered value"),
        ({**VERDICT, "extra": 1}, "registered keys"),
    ):
        with pytest.raises(judge.VerdictError, match=match):
            judge.parse_verdict(json.dumps(wrong), 2)
