"""The v2 consumer uses exact requests, persisted replies and addressed grades."""

import json
from typing import ClassVar

import pytest

from evaluation.blinded_judge import read_store
from evaluation.blinded_judge_clients import (
    JudgeUnavailable,
    RateLimited,
    Reply,
    SonnetClient,
    TransportError,
)
from evaluation.judge_contract import validate_grade_record


def _case(count=2):
    return {
        "case_id": "case-1",
        "question": "Which policy applies?",
        "documents": [
            {
                "text": f"Policy {i} requires approval.",
                "address": {
                    "source_id": f"HIDDEN_SOURCE_{i}",
                    "source_revision": "revision-1",
                    "section_path": "Policy",
                    "chunker_version": "v1",
                },
            }
            for i in range(count)
        ],
    }


class Client:
    route = "fixture"
    parameters: ClassVar[dict] = {"model": "fixture", "temperature": 0}

    def __init__(self, *replies):
        self.replies = iter(replies)
        self.prompts = []

    def grade(self, prompt):
        self.prompts.append(prompt)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return Reply(reply, "fixture", {"tokens": 10}, 0.1)


def _reply(count=2):
    return json.dumps({"grades": [{"doc": f"D{i}", "grade": 0} for i in range(1, count + 1)]})


@pytest.mark.parametrize("count", [1, 2, 10])
def test_consumer_persists_raw_reply_and_exact_addressed_grades(tmp_path, count):
    from scripts.relevance_judge_v2 import run_judge_v2

    client = Client(_reply(count))
    store = tmp_path / "replies.jsonl"
    result = run_judge_v2(client, [_case(count)], store, judge_version="fixture:v1")
    assert result == {"valid": 1, "invalid": 0, "absent": 0, "reused": 0, "pending": 0}
    (row,) = read_store(store)
    assert row["raw_text"] == _reply(count)
    assert row["request_version"] == 2
    assert row["model"] == "fixture"
    assert row["usage"] == {"tokens": 10}
    assert len(row["records"]) == count
    for record in row["records"]:
        validate_grade_record(record)
        assert record["grade"] == 0
        assert record["request_key"] == row["request_key"]
    assert "HIDDEN_SOURCE" not in client.prompts[0]


def test_resume_uses_exact_key_and_reparses_raw_reply(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    case = _case()
    run_judge_v2(Client(_reply()), [case], store, judge_version="fixture:v1")
    original = store.read_bytes()
    case["documents"].reverse()
    assert run_judge_v2(Client(), [case], store, judge_version="fixture:v1")["reused"] == 1
    assert store.read_bytes() == original
    changed = Client(_reply())
    run_judge_v2(changed, [case], store, judge_version="fixture:v2")
    assert len(changed.prompts) == 1
    assert len(read_store(store)) == 2
    case["documents"][0]["text"] += " Updated."
    changed_text = Client(_reply())
    run_judge_v2(changed_text, [case], store, judge_version="fixture:v2")
    assert len(changed_text.prompts) == 1


@pytest.mark.parametrize(
    "reply,status", [("bad", "invalid"), ("", "absent"), (TransportError(), "absent")]
)
def test_invalid_or_absent_never_becomes_zero_or_a_cached_success(tmp_path, reply, status):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    result = run_judge_v2(Client(reply), [_case()], store, judge_version="fixture:v1")
    assert result[status] == 1
    (row,) = read_store(store)
    assert row["status"] == status
    assert row["records"] == []
    result = run_judge_v2(Client(_reply()), [_case()], store, judge_version="fixture:v1")
    assert result["valid"] == 1 and result["reused"] == 0


def test_corrupt_cached_success_is_not_reused(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    run_judge_v2(Client(_reply()), [_case()], store, judge_version="fixture:v1")
    (row,) = read_store(store)
    row["raw_text"] = "bad"
    store.write_text(json.dumps(row) + "\n", encoding="utf-8")
    client = Client(_reply())
    assert run_judge_v2(client, [_case()], store, judge_version="fixture:v1")["reused"] == 0
    assert len(client.prompts) == 1


def test_cached_reply_rebinds_current_source_revision_without_call(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    case = _case()
    run_judge_v2(Client(_reply()), [case], store, judge_version="fixture:v1")
    case["documents"][0]["address"]["source_revision"] = "revision-2"
    result = run_judge_v2(Client(), [case], store, judge_version="fixture:v1")
    assert result["reused"] == 1
    records = read_store(store)[-1]["records"]
    assert (
        next(r for r in records if r["address"]["source_id"] == "HIDDEN_SOURCE_0")["address"][
            "source_revision"
        ]
        == "revision-2"
    )


def test_input_validation_precedes_any_request(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    client = Client(_reply())
    bad = _case(0)
    bad["case_id"] = "bad"
    with pytest.raises(ValueError):
        run_judge_v2(client, [_case(), bad], tmp_path / "replies.jsonl", judge_version="v1")
    assert not client.prompts


def test_unavailable_stops_without_grading_remaining_cases(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    second = _case()
    second["case_id"] = "case-2"
    client = Client(JudgeUnavailable("1310", "quota"))
    result = run_judge_v2(client, [_case(), second], tmp_path / "replies.jsonl", judge_version="v1")
    assert len(client.prompts) == 1
    assert result["absent"] == 1 and result["pending"] == 1
    assert result["unavailable"] == "1310"


def test_explicit_cli_runs_consumer_and_reports_incomplete(tmp_path, monkeypatch, capsys):
    from scripts import relevance_judge_v2 as runner

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps(_case()) + "\n", encoding="utf-8")
    client = Client("bad")
    monkeypatch.setattr(runner, "_client", lambda args: client)
    assert (
        runner.main(
            ["--judge", "glm", "--cases", str(cases), "--store", str(tmp_path / "replies.jsonl")]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["invalid"] == 1


def test_limit_counts_new_requests_and_can_reuse_after_limit(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    cached = _case()
    run_judge_v2(Client(_reply()), [cached], store, judge_version="v1")
    pending = _case()
    pending["case_id"] = "pending"
    result = run_judge_v2(Client(), [pending, cached], store, judge_version="v1", limit=0)
    assert result["pending"] == 1 and result["reused"] == 1


def test_cli_requires_mistral_key_path_before_request(tmp_path):
    from scripts import relevance_judge_v2 as runner

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps(_case()) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        runner.main(
            [
                "--judge",
                "mistral",
                "--cases",
                str(cases),
                "--store",
                str(tmp_path / "replies.jsonl"),
            ]
        )
    assert error.value.code == 2


def test_cli_cache_includes_sonnet_endpoint(tmp_path, monkeypatch):
    from scripts import relevance_judge_v2 as runner

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps(_case()) + "\n", encoding="utf-8")
    store = tmp_path / "replies.jsonl"
    endpoints = []

    def grade(client, prompt):
        endpoints.append(client.base)
        return Reply(_reply(), "fixture", {}, 0.1)

    monkeypatch.setattr(SonnetClient, "grade", grade)
    args = ["--judge", "sonnet", "--cases", str(cases), "--store", str(store)]
    assert runner.main([*args, "--gk-base", "http://127.0.0.1:8011"]) == 0
    assert runner.main([*args, "--gk-base", "http://127.0.0.1:8012"]) == 0
    assert endpoints == ["http://127.0.0.1:8011", "http://127.0.0.1:8012"]
    assert read_store(store)[0]["request_key"] != read_store(store)[1]["request_key"]


def test_malformed_stored_grade_is_refused_before_request(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    run_judge_v2(Client(_reply()), [_case()], store, judge_version="v1")
    (row,) = read_store(store)
    row["records"][0]["text_sha256"] = "bad"
    store.write_text(json.dumps(row) + "\n", encoding="utf-8")
    client = Client(_reply())
    with pytest.raises(ValueError, match="malformed text_sha256"):
        run_judge_v2(client, [_case()], store, judge_version="v1")
    assert not client.prompts


def test_rate_limit_is_saved_without_retry_or_grading_remaining_cases(tmp_path):
    from scripts.relevance_judge_v2 import run_judge_v2

    store = tmp_path / "replies.jsonl"
    second = _case()
    second["case_id"] = "case-2"
    client = Client(RateLimited(2000000000.0))
    result = run_judge_v2(client, [_case(), second], store, judge_version="v1")
    assert len(client.prompts) == 1
    assert result == {
        "valid": 0,
        "invalid": 0,
        "absent": 1,
        "reused": 0,
        "pending": 1,
        "unavailable": "rate_limit",
    }
    (row,) = read_store(store)
    assert row["reason"] == "rate_limit" and row["reset_at"] == 2000000000.0
    assert row["records"] == []
