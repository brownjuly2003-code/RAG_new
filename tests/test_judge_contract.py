"""T-60 judge contracts: deterministic fixtures and pinned archived replies, no models."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pytest

from evaluation import blinded_judge as p2
from evaluation import judge_contract as judge
from scripts import generator_benchmark as benchmark

ROOT = Path(__file__).resolve().parents[1]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _documents(count: int) -> list[dict[str, Any]]:
    return [
        {
            "text": f"Policy text {i}: a shipment needs approval.",
            "address": {
                "source_id": f"HIDDEN_SOURCE_{i}",
                "source_revision": "HIDDEN_REVISION",
                "section_path": ["HIDDEN_SECTION"],
                "chunker_version": "HIDDEN_CHUNKER",
            },
            "rank": i,
            "expected_keyword": "HIDDEN_KEYWORD",
        }
        for i in range(count)
    ]


def _request(documents: list[dict[str, Any]], **kwargs: Any) -> Any:
    return judge.build_request_v2(
        case_id="case-1",
        question="Which policy applies?",
        documents=documents,
        judge_version=kwargs.pop("judge_version", "fake-model:temperature=0"),
        **kwargs,
    )


@pytest.mark.parametrize("count", [1, 5, 10])
def test_judge_contract_v2_blind_order_is_stable_and_independent_of_rank(count: int) -> None:
    documents = _documents(count)
    request = _request(documents)
    reordered = _request(list(reversed(documents)))
    assert request.text == reordered.text == _request(documents).text
    assert request.request_key == reordered.request_key
    assert request.request_version == 2
    assert request.question_hash == _sha("Which policy applies?")
    assert request.request_sha256 == _sha(request.text)
    hashes = sorted(_sha(doc["text"]) for doc in documents)
    random.Random("20260925:v2:case-1").shuffle(hashes)
    assert [doc["text_sha256"] for doc in request.documents] == hashes
    for position, document in enumerate(request.documents, 1):
        assert f"D{position}\n{document['text']}" in request.text
        assert document["text_sha256"] not in request.text
    assert "HIDDEN_" not in request.text
    assert "case-1" not in request.text
    assert "rank" not in request.text
    canonical = {
        "request_version": 2,
        "question_hash": request.question_hash,
        "text_sha256": hashes,
        "rubric_version": request.rubric_version,
        "judge_version": request.judge_version,
    }
    assert request.request_key == _sha(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


@pytest.mark.parametrize("count", [0, 11])
def test_judge_contract_v2_refuses_wrong_document_count(count: int) -> None:
    with pytest.raises(ValueError, match="1.*10"):
        _request(_documents(count))


def test_judge_contract_v2_refuses_duplicate_text_and_wrong_hash() -> None:
    documents = _documents(2)
    documents[1]["text"] = documents[0]["text"]
    with pytest.raises(ValueError, match="duplicate"):
        _request(documents)
    documents = _documents(1)
    documents[0]["text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="text_sha256"):
        _request(documents)


def test_judge_contract_v2_cache_pins_exact_text_rubric_judge_and_question() -> None:
    documents = _documents(2)
    original = _request(documents)
    assert _request(documents, rubric_version="new-rubric").request_key != original.request_key
    assert _request(documents, judge_version="another-route").request_key != original.request_key
    documents[0]["text"] += " "
    assert _request(documents).request_key != original.request_key
    changed_question = judge.build_request_v2(
        case_id="case-1",
        question="Which policy applies? ",
        documents=_documents(2),
        judge_version=original.judge_version,
    )
    assert changed_question.request_key != original.request_key


@pytest.mark.parametrize(
    ("reply", "status", "reason"),
    [
        (None, "absent", "empty_reply"),
        (" \n", "absent", "empty_reply"),
        ("No JSON", "invalid", "no_json"),
        ('{"grades": [{"doc": "D1", "grade": 2}]}', "invalid", "missing_label"),
        (
            '{"grades": [{"doc": "D1", "grade": 2}, {"doc": "D1", "grade": 1}]}',
            "invalid",
            "duplicate_label",
        ),
        (
            '{"grades": [{"doc": "D1", "grade": 2}, {"doc": "D3", "grade": 1}]}',
            "invalid",
            "extra_label",
        ),
        (
            '{"grades": [{"doc": "D1", "grade": 4}, {"doc": "D2", "grade": 1}]}',
            "invalid",
            "out_of_range",
        ),
        (
            '{"grades": [{"doc": "D1", "grade": true}, {"doc": "D2", "grade": 1}]}',
            "invalid",
            "non_integer",
        ),
        (
            '{"grades": [{"doc": "D1", "grade": 1.0}, {"doc": "D2", "grade": 1}]}',
            "invalid",
            "non_integer",
        ),
    ],
)
def test_judge_contract_v2_parser_never_grades_invalid_or_absent(
    reply: str | None,
    status: str,
    reason: str,
) -> None:
    result = judge.parse_grades_v2(reply, ("D1", "D2"))
    assert result.status == status
    assert result.reason == reason
    assert result.grades == {}


@pytest.mark.parametrize("wrapper", ["{}", "```json\n{}\n```", "Here is the result:\n{}"])
def test_judge_contract_v2_parser_false_reject_control(wrapper: str) -> None:
    body = '{"grades": [{"doc": "D1", "grade": 3}, {"doc": "D2", "grade": 0}]}'
    result = judge.parse_grades_v2(wrapper.format(body), ("D1", "D2"))
    assert result.status == "valid"
    assert result.grades == {"D1": 3, "D2": 0}


def test_judge_contract_v2_first_object_is_decisive() -> None:
    body = '{"grades": [{"doc": "D1", "grade": 3}]}'
    result = judge.parse_grades_v2('{"grades": []}\n' + body, ("D1",))
    assert result.status == "invalid"
    assert result.reason == "missing_label"


def test_judge_contract_grade_records_preserve_addresses_and_only_reuse_exact_key(
    tmp_path: Path,
) -> None:
    request = _request(_documents(2))
    parsed = judge.parse_grades_v2(
        '{"grades": [{"doc": "D1", "grade": 0}, {"doc": "D2", "grade": 3}]}',
        ("D1", "D2"),
    )
    records = judge.make_grade_records(request, parsed)
    path = tmp_path / "grades.jsonl"
    judge.write_grade_records(path, records)
    assert judge.read_grade_records(path, request_key=request.request_key) == records
    changed = _request(_documents(2), judge_version="changed-model")
    assert judge.read_grade_records(path, request_key=changed.request_key) == []
    for position, record in enumerate(records):
        judge.validate_grade_record(record)
        assert record["address"] == request.documents[position]["address"]
        assert record["text_sha256"] == request.documents[position]["text_sha256"]
        assert record["case_id"] == request.case_id
        assert record["question_hash"] == request.question_hash
        assert record["request_sha256"] == request.request_sha256
    invalid = judge.parse_grades_v2("bad", ("D1", "D2"))
    assert judge.make_grade_records(request, invalid) == []


@pytest.mark.parametrize(
    "field",
    [
        "case_id",
        "question_hash",
        "address",
        "text_sha256",
        "grade",
        "rubric_version",
        "judge_version",
        "request_key",
        "request_sha256",
    ],
)
def test_judge_contract_grade_schema_refuses_missing_fields(field: str) -> None:
    request = _request(_documents(1))
    parsed = judge.parse_grades_v2('{"grades": [{"doc": "D1", "grade": 2}]}', ("D1",))
    record = judge.make_grade_records(request, parsed)[0]
    del record[field]
    with pytest.raises(ValueError):
        judge.validate_grade_record(record)


@pytest.mark.parametrize("field", ["question_hash", "text_sha256", "request_key", "request_sha256"])
def test_judge_contract_grade_schema_refuses_malformed_hash(field: str) -> None:
    request = _request(_documents(1))
    parsed = judge.parse_grades_v2('{"grades": [{"doc": "D1", "grade": 2}]}', ("D1",))
    record = judge.make_grade_records(request, parsed)[0]
    record[field] = "not-a-hash"
    with pytest.raises(ValueError):
        judge.validate_grade_record(record)


def test_judge_contract_archived_p2_and_opus_replies_reproduce_both_parsers() -> None:
    report = json.loads(
        (ROOT / "reports/p2/p2-blinded-judge-glm+sonnet.json").read_text(encoding="utf-8")
    )
    stores = [ROOT / "reports/p2/opus-reference/replies.jsonl"]
    for name in ("glm", "sonnet"):
        pinned = report["provenance"]["judge_routes"][name]["reply_files"][0]
        path = ROOT / "reports" / pinned["path"].replace("\\", "/").split("/reports/", 1)[1]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pinned["sha256"]
        stores.append(path)
    cases = {case.case_id: case for pool in p2.load_inputs().pools.values() for case in pool.cases}
    count = 0
    for path in stores:
        for record in p2.read_store(path):
            if record["status"] != "graded":
                continue
            request = p2.build_request(cases[record["case_id"]])
            assert request.sha256 == record["request_sha256"]
            labels = tuple(f"D{i}" for i in range(1, 6))
            legacy = p2.parse_grades(record["raw_text"], labels)
            modern = judge.parse_grades_v2(record["raw_text"], labels)
            assert modern.status == "valid"
            assert modern.grades == legacy
            expected = [record["grades"][i] for i in request.order]
            assert [modern.grades[label] for label in labels] == expected
            count += 1
    assert count == 240  # GLM 115 + Sonnet 115 + Opus's blind 10.


class FakeLLM:
    def __init__(self, replies: list[str | Exception]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> str:
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.mark.parametrize(
    ("raw", "status", "score"),
    [
        ("0.0", "valid", 0.0),
        ("1.0", "valid", 1.0),
        (" \n0.75\t", "valid", 0.75),
        ("Score: 1.0", "invalid", None),
        ("1.2", "invalid", None),
        (None, "absent", None),
        (" ", "absent", None),
    ],
)
def test_generator_benchmark_judge_outcome_distinguishes_low_invalid_absent(
    raw: str | None,
    status: str,
    score: float | None,
) -> None:
    result = benchmark.parse_judge_score(raw, request_text="exact prompt")
    assert result["status"] == status
    assert result["score"] == score
    assert result["raw_text"] == raw
    assert result["request_sha256"] == _sha("exact prompt")
    if status == "invalid":
        assert result["reason"] == "parse_failure"


def test_generator_benchmark_judge_failure_keeps_the_other_prompt_and_truncation() -> None:
    llm = FakeLLM([TimeoutError("no reply"), "0.75"])
    scores = benchmark._judge_scores(
        llm,
        question="Which policy?",
        answer="a" * 2001,
        contexts=["c" * 3001],
        expected_keywords=["c"],
    )
    requests = scores["judge_requests"]
    assert scores["faithfulness"] is None
    assert scores["answer_relevancy"] == 0.75
    assert requests["faithfulness"]["status"] == "absent"
    assert requests["answer_relevancy"]["status"] == "valid"
    assert requests["faithfulness"]["truncated"] == {"context": True, "answer": True}
    assert requests["answer_relevancy"]["truncated"] == {"context": False, "answer": True}
    assert requests["faithfulness"]["original_lengths"] == {"context": 3001, "answer": 2001}
    assert not requests["answer_relevancy"]["kappa_eligible"]
    for name, prompt in zip(("faithfulness", "answer_relevancy"), llm.prompts, strict=True):
        assert requests[name]["request_sha256"] == _sha(prompt)


def _row(index: int, faithfulness: str, relevancy: str = "0.5") -> dict[str, Any]:
    judged = benchmark._judge_scores(
        FakeLLM([faithfulness, relevancy]),
        question="Which policy?",
        answer="Approval.",
        contexts=["Approval is needed."],
        expected_keywords=["approval"],
    )
    return {
        "case_id": f"case-{index}",
        "generation_valid": True,
        "nli_valid": True,
        "llm_judge_valid": all(o["status"] == "valid" for o in judged["judge_requests"].values()),
        "scores": {key: value for key, value in judged.items() if key != "judge_requests"},
        "judge_requests": judged["judge_requests"],
        "nli": {"nli_faithfulness": 1.0, "supported_claim_rate": 1.0},
        "latency_ms": 10,
    }


def test_generator_benchmark_aggregate_excludes_invalid_absent_per_metric() -> None:
    run = {"cases": [_row(1, "1.0"), _row(2, "Score: 1.0"), _row(3, "")]}
    benchmark._aggregate_run(run)
    assert run["aggregate"]["llm_faithfulness"] == 1.0
    assert run["aggregate"]["answer_relevancy"] == 0.5
    summary = run["judge_summary"]["faithfulness"]
    assert summary["valid"] == 1
    assert summary["invalid"] == 1
    assert summary["absent"] == 1
    assert summary["invalid_cases"] == ["case-2"]
    assert summary["absent_cases"] == ["case-3"]
    assert run["failed_cases"] == 0


@pytest.mark.parametrize(("invalid", "evidence"), [(2, "measured"), (3, "NOT_EVIDENCE")])
def test_generator_benchmark_invalid_rate_is_counted_and_gates_report(
    invalid: int,
    evidence: str,
) -> None:
    run = {"run_index": 1, "cases": [_row(i, "bad" if i < invalid else "1.0") for i in range(10)]}
    benchmark._aggregate_run(run)
    assert run["answer_metrics_evidence"] == evidence
    provenance = {field: "a" * 64 for field in benchmark.REQUIRED_PROVENANCE}
    report = benchmark.build_final_report(
        runs=[run],
        provenance=provenance,
        expected_cases=10,
        required_runs=1,
    )
    assert report["evidence_class"] == ("measured" if invalid == 2 else "not_evidence")
    if invalid == 3:
        assert any("invalid judge" in reason for reason in report["evidence_reasons"])


def test_generator_benchmark_no_valid_scores_are_missing_not_zero() -> None:
    run = {"cases": [_row(1, "bad", "")]}
    benchmark._aggregate_run(run)
    assert run["aggregate"]["llm_faithfulness"] is None
    assert run["aggregate"]["answer_relevancy"] is None


def test_generator_benchmark_archived_gr3_score_stays_invalid() -> None:
    report = json.loads(
        (ROOT / "evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    failed = [
        row
        for run in report["runs"]
        for row in run["cases"]
        if "'Score: 1.0'" in row.get("error", "")
    ]
    assert len(failed) == 3
    for row in failed:
        outcome = benchmark.parse_judge_score("Score: 1.0", request_text="archived grammar")
        assert outcome["status"] == "invalid"
        assert outcome["score"] is None
        assert not row["llm_judge_valid"]


def test_generator_benchmark_main_persists_separate_raw_replies_and_truncation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LocalLLM:
        calls = 0
        failed_calls = 0

        def __init__(self, **kwargs: Any) -> None:
            pass

        def model_metadata(self) -> dict[str, Any]:
            return {"digest": "d" * 64}

        def process_metadata(self) -> dict[str, Any]:
            return {}

        def unload(self) -> None:
            pass

        def invoke(self, prompt: str) -> str:
            self.calls += 1
            if "faithfulness score" in prompt:
                return "Score: 1.0"
            if "well the answer addresses" in prompt:
                return "0.75"
            return "Approval is needed."

    class LocalNLI:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def score(self, answer: str, contexts: list[str]) -> dict[str, Any]:
            return {"nli_faithfulness": 1.0, "supported_claim_rate": 1.0}

    dataset, contexts = tmp_path / "cases.jsonl", tmp_path / "contexts.json"
    dataset.write_text("", encoding="utf-8")
    contexts.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(benchmark, "OllamaLLM", LocalLLM)
    monkeypatch.setattr(benchmark, "MultilingualNLIScorer", LocalNLI)
    monkeypatch.setattr(
        benchmark, "_git_value", lambda *args: "a" * 40 if args == ("rev-parse", "HEAD") else ""
    )
    monkeypatch.setattr(
        benchmark,
        "load_benchmark_cases",
        lambda **kwargs: [
            {
                "case_id": "case-1",
                "query": "Which policy?",
                "contexts": ["c" * 3001],
                "expected_keywords": ["c"],
            }
        ],
    )
    assert (
        benchmark.main(
            [
                "--dataset",
                str(dataset),
                "--contexts",
                str(contexts),
                "--results-dir",
                str(tmp_path),
                "--run-id",
                "contract",
                "--runs",
                "3",
                "--expected-cases",
                "1",
            ]
        )
        == 1
    )
    report = json.loads(
        (tmp_path / "contract-phase-c-generator-benchmark.json").read_text(encoding="utf-8")
    )
    for run in report["runs"]:
        row = run["cases"][0]
        assert row["scores"]["faithfulness"] is None
        assert row["scores"]["answer_relevancy"] == 0.75
        assert row["judge_requests"]["faithfulness"]["raw_text"] == "Score: 1.0"
        assert row["judge_requests"]["answer_relevancy"]["raw_text"] == "0.75"
        assert run["judge_summary"]["faithfulness"]["truncated"] == 1
        assert run["judge_summary"]["answer_relevancy"]["truncated"] == 0
        assert run["answer_metrics_evidence"] == "NOT_EVIDENCE"
