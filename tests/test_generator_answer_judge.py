from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from evaluation import isolated_request as isolated
from evaluation.blinded_judge_clients import JudgeUnavailable
from scripts import generator_answer_judge as judge
from scripts.generator_benchmark import PROMPT_VERSION

CASES = 100
SESSION = {
    "cli_version": "9.9.9",
    "model": "fixture-reported-model",
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}
GOOD = {
    "claims_total": 2,
    "claims_supported": 2,
    "context_has_answer": True,
    "answers_question": "full",
    "defect": "none",
    "note": "fine",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    dataset, contexts = tmp_path / "cases.jsonl", tmp_path / "contexts.json"
    rows = [
        {
            "case_id": f"case-{i:03d}",
            "query": f"Вопрос {i}?",
            "expected": {"answer_contains": [f"срок{i}"]},
        }
        for i in range(CASES)
    ]
    dataset.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), "utf-8")
    contexts.write_text(
        json.dumps(
            [
                {
                    "case_id": row["case_id"],
                    "query": row["query"],
                    "kws": row["expected"]["answer_contains"],
                    "cands": [f"Контекст {i}: срок{i} пять дней.", f"Второй фрагмент {i}."],
                    "rerank_k": 2,
                }
                for i, row in enumerate(rows)
            ],
            ensure_ascii=False,
        ),
        "utf-8",
    )
    return dataset, contexts


def _report(
    inputs: tuple[Path, Path], model: str, answer: str = "Срок пять дней [1].", **config: Any
) -> dict[str, Any]:
    dataset, contexts = inputs
    return {
        "provenance": {
            "dataset_sha256": _sha(dataset),
            "contexts_sha256": _sha(contexts),
            "ollama_model": model,
            "ollama_model_digest": f"digest-of-{model}",
            "code_sha": "c0de",
            "config": {"prompt_version": PROMPT_VERSION, "context_chars": 6000, **config},
        },
        "runs": [
            {
                "run_index": 1,
                "seed": 42,
                "aggregate": {"nli_faithfulness": 0.9},
                "cases": [
                    {
                        "case_id": f"case-{i:03d}",
                        "answer": answer,
                        "generation_valid": bool(answer),
                        "context_count": 2,
                        "latency_ms": 2000,
                        "ollama_timing": {"eval_count": 40, "eval_duration": 4_000_000_000},
                    }
                    for i in range(CASES)
                ],
            }
        ],
    }


def _plan(inputs: tuple[Path, Path], **reports: dict[str, Any]) -> dict[str, Any]:
    dataset, contexts = inputs
    return judge.build_plan(reports, dataset_path=dataset, contexts_path=contexts)


@dataclass
class FakeReply:
    text: str
    model: str = "claude-opus-5-5"
    usage: dict[str, Any] = field(default_factory=lambda: {"total_cost_usd": 0.25})
    elapsed_s: float = 3.0
    session: dict[str, Any] = field(default_factory=lambda: dict(SESSION))


class FakeSender:
    def __init__(self, *texts: str | Exception) -> None:
        self.texts = list(texts)
        self.messages: list[str] = []

    def __call__(self, system_prompt: str, message: str) -> FakeReply:
        assert system_prompt == judge.SYSTEM_PROMPT
        self.messages.append(message)
        text = self.texts.pop(0) if self.texts else json.dumps(GOOD)
        if isinstance(text, Exception):
            raise text
        return FakeReply(text)


def test_the_sample_is_thirty_cases_fixed_by_the_salt_whatever_the_order() -> None:
    ids = [f"case-{i:03d}" for i in range(CASES)]

    sample = judge.sample_case_ids(ids)

    assert len(sample) == judge.SAMPLE_SIZE == 30
    assert sample == judge.sample_case_ids(list(reversed(ids)))
    assert set(sample) <= set(ids)
    assert sample != ids[:30]


def test_a_verdict_must_have_the_registered_form() -> None:
    assert judge.parse_verdict(json.dumps(GOOD)) == GOOD
    assert judge.parse_verdict("```json\n" + json.dumps(GOOD) + "\n```") == GOOD
    for broken in (
        "Here it is: " + json.dumps(GOOD),
        json.dumps({**GOOD, "extra": 1}),
        json.dumps({key: value for key, value in GOOD.items() if key != "note"}),
        json.dumps({**GOOD, "claims_supported": 3}),
        json.dumps({**GOOD, "claims_total": True}),
        json.dumps({**GOOD, "claims_total": -1}),
        json.dumps({**GOOD, "context_has_answer": "yes"}),
        json.dumps({**GOOD, "answers_question": "mostly"}),
        json.dumps({**GOOD, "defect": "typo"}),
        "```json\n" + json.dumps(GOOD),
    ):
        with pytest.raises(judge.VerdictError):
            judge.parse_verdict(broken)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, "good"),
        ({"claims_total": 0, "claims_supported": 0}, "bad"),
        ({"claims_supported": 1}, "bad"),
        ({"defect": "cut_off"}, "bad"),
        ({"answers_question": "partial"}, "partial_ok"),
        ({"answers_question": "partial", "claims_supported": 1}, "bad"),
        ({"answers_question": "no"}, "bad"),
        (
            {
                "answers_question": "declined",
                "claims_total": 0,
                "claims_supported": 0,
                "context_has_answer": False,
            },
            "good",
        ),
        ({"answers_question": "declined", "claims_total": 0, "claims_supported": 0}, "bad"),
    ],
)
def test_classes_reward_complete_faithful_answers_and_right_declines(
    changes: dict[str, Any], expected: str
) -> None:
    assert judge.classify({**GOOD, **changes}) == expected


def test_the_plan_hides_the_generator_and_sends_what_the_generator_saw(inputs) -> None:
    plan = _plan(
        inputs,
        alpha=_report(inputs, "secret-model:1b"),
        beta=_report(inputs, "other-model:4b", answer=""),
    )

    asked = [item for item in plan["items"] if "message" in item]
    first = [item for item in asked if "retest_of" not in item]
    retests = [item for item in asked if "retest_of" in item]
    assert len(first) == judge.SAMPLE_SIZE and len(retests) == judge.RETEST_SIZE
    assert {item["retest_of"] for item in retests} <= {item["item_id"] for item in first}
    assert all(item["generator"] == "alpha" for item in asked)
    for item in asked:
        message = item["message"]
        assert not any(name in message for name in ("alpha", "beta", "secret-model", "qwen"))
        assert message.startswith(judge.INSTRUCTIONS)
        assert f"Контекст {int(item['case_id'][-3:])}: срок" in message
        assert message.rstrip().endswith("ANSWER:\nСрок пять дней [1].")
        assert item["message_sha256"] == hashlib.sha256(message.encode()).hexdigest()
    empty = [item for item in plan["items"] if item.get("empty_answer")]
    assert len(empty) == judge.SAMPLE_SIZE and all(item["generator"] == "beta" for item in empty)
    assert plan["route"] == isolated.settings(judge.SYSTEM_PROMPT)
    assert plan["checks"]["beta"]["empty"] == CASES
    assert plan["checks"]["alpha"]["answer_keyword_recall"] == 0.0
    assert plan["checks"]["alpha"]["median_output_tokens_per_s"] == 10.0
    assert plan["checks"]["alpha"]["latency_includes_self_judging"] is True
    order = [item["item_id"] for item in plan["items"]]
    assert order == [
        item["item_id"]
        for item in _plan(inputs, alpha=_report(inputs, "x"), beta=_report(inputs, "y", answer=""))[
            "items"
        ]
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_version": "another-prompt"},
        {"context_chars": 3000},
        {"top_k_override": 3},
        {"allow_short_contexts": True},
    ],
)
def test_the_plan_refuses_a_report_that_sent_another_prompt_or_context(inputs, changes) -> None:
    with pytest.raises(ValueError, match="another prompt or context"):
        _plan(inputs, alpha=_report(inputs, "m", **changes))


def test_the_plan_refuses_another_input_a_missing_case_or_another_seed(inputs) -> None:
    other = _report(inputs, "m")
    other["provenance"]["contexts_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="another dataset or cached contexts"):
        _plan(inputs, alpha=other)
    short = _report(inputs, "m")
    short["runs"][0]["cases"].pop()
    with pytest.raises(ValueError, match="every case once"):
        _plan(inputs, alpha=short)
    seed = _report(inputs, "m")
    seed["runs"][0]["seed"] = 43
    with pytest.raises(ValueError, match="no single run of seed 42"):
        _plan(inputs, alpha=seed)
    count = _report(inputs, "m")
    count["runs"][0]["cases"][0]["context_count"] = 1
    with pytest.raises(ValueError, match="another context"):
        _plan(inputs, alpha=count)


def test_run_retries_a_wrong_form_resumes_and_stops_where_the_route_refuses(
    inputs, tmp_path: Path
) -> None:
    plan = _plan(inputs, alpha=_report(inputs, "m"))
    sender = FakeSender("not json", json.dumps(GOOD))

    assert judge.run_plan(plan, tmp_path, sender, limit=1) == 1
    rows = judge._read_jsonl(tmp_path / "verdicts.jsonl")
    assert [(row["attempt"], row["status"]) for row in rows] == [(1, "invalid"), (2, "valid")]
    assert rows[1]["session"] == SESSION and rows[1]["usage"] == {"total_cost_usd": 0.25}

    refusing = FakeSender(json.dumps(GOOD), JudgeUnavailable("cli_exit", "exited with 1"))
    with pytest.raises(JudgeUnavailable):
        judge.run_plan(plan, tmp_path, refusing)
    rows = judge._read_jsonl(tmp_path / "verdicts.jsonl")
    assert [row["status"] for row in rows] == ["invalid", "valid", "valid", "unavailable"]
    asked = [item for item in plan["items"] if "message" in item]
    assert refusing.messages == [asked[1]["message"], asked[2]["message"]]

    assert judge.run_plan(plan, tmp_path, FakeSender()) == len(asked) - 2
    valid = [
        row["item_id"]
        for row in judge._read_jsonl(tmp_path / "verdicts.jsonl")
        if row["status"] == "valid"
    ]
    assert sorted(valid) == sorted(item["item_id"] for item in asked)


def test_summary_counts_vouched_verdicts_retests_and_empty_answers(inputs, tmp_path: Path) -> None:
    plan = _plan(inputs, alpha=_report(inputs, "m"), beta=_report(inputs, "n", answer=""))
    partial = json.dumps({**GOOD, "answers_question": "partial", "claims_supported": 1})
    judge.run_plan(plan, tmp_path, FakeSender(partial))
    verdicts = judge._read_jsonl(tmp_path / "verdicts.jsonl")

    summary = judge.summarize(plan, verdicts)

    alpha, beta = summary["generators"]["alpha"], summary["generators"]["beta"]
    assert summary["missing"] == 0
    first = next(item for item in plan["items"] if "message" in item)
    retested = any(item.get("retest_of") == first["item_id"] for item in plan["items"])
    assert alpha["classes"] == {"good": judge.SAMPLE_SIZE - 1, "partial_ok": 0, "bad": 1}
    assert alpha["with_unsupported_claim"] == 1
    assert beta == {
        "items": judge.SAMPLE_SIZE,
        "graded": judge.SAMPLE_SIZE,
        "empty_answers": judge.SAMPLE_SIZE,
        "classes": {"good": 0, "partial_ok": 0, "bad": judge.SAMPLE_SIZE},
        "supported_claim_rate": None,
        "with_unsupported_claim": 0,
        "answers": dict.fromkeys(judge.ANSWERS, 0),
        "defects": {**dict.fromkeys(judge.DEFECTS[1:], 0), "empty": judge.SAMPLE_SIZE},
    }
    assert summary["retest"]["pairs"] == judge.RETEST_SIZE
    assert summary["retest"]["same_class"] == judge.RETEST_SIZE - (1 if retested else 0)
    assert summary["context_has_answer"] == {"cases": 30, "same_for_every_answer": 30}
    assert summary["requests"]["cost_usd"] == round(
        0.25 * (judge.SAMPLE_SIZE + judge.RETEST_SIZE), 2
    )


def test_summary_refuses_a_verdict_without_a_clean_session_or_its_request(
    inputs, tmp_path: Path
) -> None:
    plan = _plan(inputs, alpha=_report(inputs, "m"))
    judge.run_plan(plan, tmp_path, FakeSender(), limit=1)
    row = judge._read_jsonl(tmp_path / "verdicts.jsonl")[0]

    loaded = {**row, "session": {**SESSION, "loaded": {**SESSION["loaded"], "tools": ["Bash"]}}}
    with pytest.raises(ValueError, match="not vouched for"):
        judge.summarize(plan, [loaded])
    with pytest.raises(ValueError, match="answers no planned request"):
        judge.summarize(plan, [{**row, "message_sha256": "0" * 64}])
    assert judge.summarize(plan, [row])["requests"]["valid"] == 1


def test_main_freezes_the_plan_once(inputs, tmp_path: Path) -> None:
    dataset, contexts = inputs
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report(inputs, "m"), ensure_ascii=False), "utf-8")
    out = tmp_path / "judge"
    argv = [
        "plan",
        "--report",
        f"alpha={report}",
        "--dataset",
        str(dataset),
        "--contexts",
        str(contexts),
        "--out",
        str(out),
    ]

    assert judge.main(argv) == 0
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["generators"]["alpha"]["report_sha256"] == _sha(report)
    with pytest.raises(SystemExit, match="frozen"):
        judge.main(argv)
