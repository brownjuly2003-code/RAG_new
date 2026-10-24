"""scripts/chat_answer_judge.py: each chat answer graded against the documents it was given."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent.prompts import build_qa_prompt
from evaluation import isolated_request as isolated
from llm.providers.base import flatten_messages
from scripts import chat_answer_judge as judge

SESSION = {
    "cli_version": "9.9.9",
    "model": isolated.MODEL,
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


def test_a_saved_prompt_names_its_version_and_a_plan_reads_one() -> None:
    v4 = flatten_messages([{"role": "user", "content": build_qa_prompt("Fee?", DOCS)}])
    # V3, the prompt of stage 2's answers, differs from V4 in its instructions, not its frame.
    v3 = v4.replace(judge.PROMPT_IDS["QA_PROMPT_V4"], judge.PROMPT_IDS["QA_PROMPT_V3"])

    assert (judge.prompt_id(v4), judge.prompt_id(v3)) == ("QA_PROMPT_V4", "QA_PROMPT_V3")
    assert judge.read_prompt(v3) == judge.read_prompt(v4)
    assert judge.one_prompt(["QA_PROMPT_V4", "QA_PROMPT_V4"]) == "QA_PROMPT_V4"
    assert judge.one_prompt([]) is None
    with pytest.raises(ValueError, match="a plan reads one prompt"):
        judge.one_prompt(["QA_PROMPT_V3", "QA_PROMPT_V4"])
    with pytest.raises(ValueError, match="not an answer prompt"):
        judge.prompt_id(v4.replace(judge.PROMPT_IDS["QA_PROMPT_V4"], "add a mark,"))


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
    assert plan["prompt_id"] == "QA_PROMPT_V4"  # read from the saved prompts

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        assert system_prompt == judge.SYSTEM_PROMPT
        return isolated.IsolatedReply(json.dumps(VERDICT), isolated.MODEL, {}, 1.0, SESSION)

    out = tmp_path / "judge"
    out.mkdir()
    assert judge.run_plan(plan, out, send) == 2
    summary = judge.summarize(plan, judge._read_jsonl(out / "verdicts.jsonl"))

    toy = summary["per_run"]["toy"]
    assert toy["answers"] == 2 and toy["graded"] == 2 and toy["missing"] == 0
    assert toy["classes"] == {"good": 1, "partial_ok": 0, "bad": 1}  # the empty answer is bad
    assert toy["marks_listed"] == 1 and toy["marks_supported"] == 1
    assert toy["reference"] == {"agrees": 1}
    assert toy["answer_without_context"] == 0
    # One pair, both good: no disagreement to expect, so no kappa - the agreement decides.
    assert summary["retest"] == {"pairs": 1, "same_class": 1, "quadratic_kappa": None}


def test_a_plan_counts_only_as_this_judge_froze_it(tmp_path: Path) -> None:
    run = _run(tmp_path / "toy-run", [("q1", "How much is storage?", "Ten a day [1].", DOCS)])
    plan = judge.build_plan({"toy": run}, {}, retest=1)
    first, again = plan["items"]
    assert set(judge.check_plan(plan)) == {first["item_id"], again["item_id"]}

    edited = again["message"] + "!"
    for changed, match in (
        ({**plan, "salt": "another"}, "not frozen by this judge"),
        ({**plan, "instructions_sha256": "0" * 64}, "not frozen by this judge"),
        ({**plan, "route": {**plan["route"], "effort": "high"}}, "not frozen by this judge"),
        ({**plan, "items": [{**first, "message": first["message"] + "!"}, again]}, "hash names"),
        ({**plan, "items": [first, first]}, "twice"),
        ({**plan, "items": [first, again, {**again, "item_id": "x"}]}, "does not repeat"),
        ({**plan, "items": [first, {**again, "marks_listed": 0}]}, "does not repeat"),
        ({**plan, "items": [first, {**again, "has_reference": True}]}, "does not repeat"),
        (
            {
                **plan,
                "items": [
                    first,
                    {**again, "message": edited, "message_sha256": judge._digest(edited)},
                ],
            },
            "does not repeat",
        ),
    ):
        with pytest.raises(ValueError, match=match):
            judge.check_plan(changed)


def test_a_request_gets_six_replies_over_all_runs_and_a_verdict_counts_from_them(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path / "toy-run", [("q1", "How much is storage?", "Ten a day [1].", DOCS)])
    plan = judge.build_plan({"toy": run}, {}, retest=0)
    replies = iter(["not json"] * judge.REPLIES)

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        return isolated.IsolatedReply(next(replies), isolated.MODEL, {}, 1.0, SESSION)

    out = tmp_path / "judge"
    out.mkdir()
    assert judge.run_plan(plan, out, send) == 1
    assert judge.run_plan(plan, out, send) == 1
    assert judge.run_plan(plan, out, send) == 0  # six replies: no seventh request
    rows = judge._read_jsonl(out / "verdicts.jsonl")
    assert [row["status"] for row in rows] == ["invalid"] * judge.REPLIES

    valid = {**rows[0], "status": "valid", "raw_text": json.dumps({**VERDICT, "reference": "none"})}
    assert judge._vouched(plan, [*rows, valid]) == {}  # a seventh reply counts for nothing
    assert list(judge._vouched(plan, [valid])) == [rows[0]["item_id"]]  # a first one counts
    with pytest.raises(ValueError, match="plan's model"):
        judge._vouched(plan, [{**valid, "model": "another-model"}])
    with pytest.raises(ValueError, match="plan's model"):
        judge._vouched(plan, [{**valid, "session": {**SESSION, "model": "another-model"}}])
    with pytest.raises(ValueError, match="answers no planned request"):
        judge._vouched(plan, [{**valid, "item_id": "unplanned"}])
    # A resume refuses a row of a request the plan does not hold, whatever its status.
    stray = {**rows[0], "message_sha256": "0" * 64}
    (out / "verdicts.jsonl").write_text(json.dumps(stray) + "\n", "utf-8")
    with pytest.raises(ValueError, match="answers no planned request"):
        judge.run_plan(plan, out, send)


def test_a_resumed_run_asks_no_further_than_the_sixth_reply(tmp_path: Path) -> None:
    run = _run(tmp_path / "toy-run", [("q1", "How much is storage?", "Ten a day [1].", DOCS)])
    plan = judge.build_plan({"toy": run}, {}, retest=0)
    (item,) = plan["items"]
    prior = {"item_id": item["item_id"], "message_sha256": item["message_sha256"]}
    rows = [{**prior, "attempt": n, "status": "invalid"} for n in (1, 2, 3, 1, 2)]
    rows.append({**prior, "attempt": 3, "status": "unavailable", "reason": "cli_exit"})
    out = tmp_path / "judge"
    out.mkdir()
    (out / "verdicts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    sent: list[str] = []

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        sent.append(message)
        return isolated.IsolatedReply("not json", isolated.MODEL, {}, 1.0, SESSION)

    # Five replies so far - the refused route's row is none - leave one attempt.
    assert judge.run_plan(plan, out, send) == 1 and len(sent) == 1
    assert judge.run_plan(plan, out, send) == 0 and len(sent) == 1


def test_a_run_with_a_limit_skips_what_is_counted(tmp_path: Path) -> None:
    run = _run(
        tmp_path / "toy-run",
        [
            ("q1", "How much is storage?", "Ten a day [1].", DOCS),
            ("q2", "How do I file a claim?", "Within 14 days [2].", DOCS),
        ],
    )
    plan = judge.build_plan({"toy": run}, {}, retest=0)
    # "full" where the judge finds no answer in the documents: bad, and counted apart.
    unheld = json.dumps({**VERDICT, "reference": "none", "context_has_answer": False})

    def send(system_prompt: str, message: str) -> isolated.IsolatedReply:
        return isolated.IsolatedReply(unheld, isolated.MODEL, {}, 1.0, SESSION)

    out = tmp_path / "judge"
    out.mkdir()
    assert [judge.run_plan(plan, out, send, limit=1) for _ in range(3)] == [1, 1, 0]
    rows = judge._read_jsonl(out / "verdicts.jsonl")

    assert sorted(row["item_id"] for row in rows) == sorted(i["item_id"] for i in plan["items"])
    toy = judge.summarize(plan, rows)["per_run"]["toy"]
    assert toy["answer_without_context"] == 2
    assert toy["classes"] == {"good": 0, "partial_ok": 0, "bad": 2}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, "good"),
        ({"context_has_answer": False}, "bad"),  # "full" where the documents hold no answer
        ({"answers_question": "partial"}, "partial_ok"),
        ({"answers_question": "partial", "context_has_answer": False}, "bad"),
        (
            {
                "answers_question": "declined",
                "context_has_answer": False,
                "claims_total": 0,
                "claims_supported": 0,
            },
            "good",
        ),
        ({"answers_question": "declined", "claims_total": 0, "claims_supported": 0}, "bad"),
        ({"claims_supported": 0}, "bad"),
    ],
)
def test_full_and_partial_count_only_where_the_documents_hold_the_answer(
    changes: dict, expected: str
) -> None:
    assert judge.classify({**VERDICT, **changes}) == expected


def test_the_plan_names_its_references_file_and_the_file_each_question_once(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path / "toy-run", [("q1", "How much is storage?", "Ten a day [1].", DOCS)])
    references = tmp_path / "references.jsonl"
    references.write_text('{"case_id": "q1", "reference_answers": ["Ten a day."]}\n', "utf-8")
    out = tmp_path / "judge"

    command = ["plan", "--run", f"toy={run}", "--references", str(references), "--out", str(out)]
    assert judge.main(command) == 0

    plan = json.loads((out / "plan.json").read_text("utf-8"))
    assert plan["references_sha256"] == hashlib.sha256(references.read_bytes()).hexdigest()
    references.write_text(references.read_text("utf-8") * 2, "utf-8")
    with pytest.raises(ValueError, match="twice"):
        judge._references(references)


def test_a_plan_can_withhold_the_references_it_names(tmp_path: Path) -> None:
    run = _run(tmp_path / "toy-run", [("q1", "How much is storage?", "Ten a day [1].", DOCS)])
    references = tmp_path / "references.jsonl"
    references.write_text('{"case_id": "q1", "reference_answers": ["Ten a day."]}\n', "utf-8")
    withheld, carried = tmp_path / "withheld", tmp_path / "carried"
    command = ["plan", "--run", f"toy={run}", "--references", str(references)]

    assert judge.main([*command, "--withhold-references", "--out", str(withheld)]) == 0
    assert judge.main([*command, "--out", str(carried)]) == 0

    blind = json.loads((withheld / "plan.json").read_text("utf-8"))
    seen = json.loads((carried / "plan.json").read_text("utf-8"))
    digest = hashlib.sha256(references.read_bytes()).hexdigest()
    assert blind["references_sha256"] == seen["references_sha256"] == digest
    assert blind["references_withheld"] is True and seen["references_withheld"] is False
    # The same requests and the same retests, the reference alone told apart.
    assert [item["item_id"] for item in blind["items"]] == [
        item["item_id"] for item in seen["items"]
    ]
    assert all(not item["has_reference"] for item in blind["items"])
    assert all("REFERENCE ANSWER:\nnone\n" in item["message"] for item in blind["items"])
    assert all("REFERENCE ANSWER:\nTen a day.\n" in item["message"] for item in seen["items"])
    with pytest.raises(SystemExit, match="give --references"):
        judge.main(["plan", "--run", f"toy={run}", "--withhold-references", "--out", "x"])
    with pytest.raises(ValueError, match="withholds"):
        judge.build_plan(
            {"toy": run}, {"q1": ["Ten a day."]}, references_sha256=digest, withheld=True
        )


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
    assert judge.quadratic_kappa([(2, 2)] * 3, 3) is None  # one level: nothing to expect
    assert judge.quadratic_kappa([(0, 2), (2, 0)], 3) < 0
