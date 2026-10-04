"""Judge v2 regrading of baseline contexts: plan, split, runner, consensus and ruler adapter.

Runs are fixtures written with the baseline collector's own helpers; judges are fakes.
"""

import copy
import hashlib
import itertools
import json
import math
import random
import re
from typing import ClassVar

import pytest

from evaluation.blinded_judge import read_store
from evaluation.blinded_judge_clients import Reply
from evaluation.judge_consensus import consensus_v2, ruler_cases, store_grades
from evaluation.judge_contract import build_request_v2, make_grade_records, parse_grades_v2
from evaluation.semantic_ruler import ndcg_at_5, precision_at_5, sent_precision
from scripts import baseline_judge as runner
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from scripts import relevance_judge_v2 as v2


class FakeJudge:
    route = "fixture"
    parameters: ClassVar[dict] = {"model": "fixture", "temperature": 0}

    def __init__(self, *replies, grade=3):
        self.replies = iter(replies)
        self.default_grade = grade
        self.prompts = []

    def grade(self, prompt):
        self.prompts.append(prompt)
        count = len(re.findall(r"^D\d+$", prompt, re.MULTILINE))
        text = next(self.replies, _reply(count, self.default_grade))
        return Reply(text, "fixture-reported-model", {"tokens": 10}, 0.125)


def _reply(count, grade=3):
    return json.dumps({"grades": [{"doc": f"D{i}", "grade": grade} for i in range(1, count + 1)]})


def _document(index, *, text=None, addressed=True):
    source = f"HIDDEN_SOURCE_{index}.pdf"
    revision = baseline.text_sha(f"HIDDEN_REVISION_{index}")
    book = baseline.AddressBook(
        {"files": [{"name": source, "sha256": revision}]}, {}, "HIDDEN_CHUNKER"
    )
    metadata = {
        "source": source,
        "content_hash": revision,
        "h1": f"HIDDEN_SECTION_{index}",
        "tenant": "HIDDEN_TENANT",
        "path": "D:/HIDDEN_DIRECTORY/secret-file.pdf",
        "reranker_score": "HIDDEN_SCORE",
        "rank": f"HIDDEN_RANK_{index}",
    }
    if not addressed:
        del metadata["content_hash"]
    return book.document(
        {
            "page_content": text if text is not None else f"Exact policy chunk {index}.",
            "metadata": metadata,
        }
    )


def _request_document(document):
    return {
        "text": document["text"],
        "text_sha256": document["text_sha256"],
        "address": document["chunk_address"],
    }


def _case(case_id="case-1", subset="H"):
    return {"case_id": case_id, "query": f"Which policy applies to {case_id}?", "subset": subset}


def _grade_row(seeds, sent=None, status="ok"):
    return {"status": status, "seed_documents": seeds, "documents": seeds if sent is None else sent}


@pytest.fixture
def finished_run(tmp_path):
    def create(pairs=None):
        if pairs is None:
            pairs = [(_case(), _grade_row([_document(i) for i in range(3)]))]
        run = tmp_path / "baseline"
        manifest = {"cases": [case for case, _ in pairs]}
        identity = parity.digest(manifest)
        parity.write_new(run / "manifest.json", manifest)
        parity.write_new(run / "registration.json", {"manifest_sha256": identity})
        parity.save_stage(run / "report.json", {"status": "FINISHED"}, identity)
        for case, row in pairs:
            parity.save_stage(run / "grade" / f"{case['case_id']}.json", row, identity)
        out = tmp_path / "judges"
        plan = runner.build_plan(run)
        runner.write_plan(out, plan)
        return run, out, plan

    return create


def _valid_row(case_id="case-1", *, version="fixture:v1", grade=3):
    request = build_request_v2(
        case_id=case_id,
        question="Which policy applies?",
        documents=[_request_document(_document(0))],
        judge_version=version,
    )
    raw = _reply(1, grade)
    return {
        "request_version": 2,
        "case_id": case_id,
        "status": "valid",
        "raw_text": raw,
        "request_key": request.request_key,
        "request_sha256": request.request_sha256,
        "judge_version": version,
        "records": make_grade_records(request, parse_grades_v2(raw, ["D1"])),
    }


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def test_consensus_two_disagreeing_judges_give_lower_median():
    unit = ("case", baseline.text_sha("text"))
    result = consensus_v2([unit], {"glm": {unit: 3}, "sonnet": {unit: 1}})
    assert result.grades == {unit: 1}


@pytest.mark.parametrize("a,b", list(itertools.product(range(4), repeat=2)))
def test_consensus_false_reject_control_all_valid_pairs_are_accepted(a, b):
    unit = ("case", baseline.text_sha("text"))
    result = consensus_v2([unit], {"glm": {unit: a}, "sonnet": {unit: b}})
    assert result.included == ("glm", "sonnet")
    assert result.grades == {unit: min(a, b)}
    assert result.unjudged == {}
    assert result.graded_by == {unit: ("glm", "sonnet")}


def test_consensus_judge_missing_more_than_five_percent_is_excluded():
    units = [("case", baseline.text_sha(str(i))) for i in range(20)]
    full = dict.fromkeys(units, 3)
    result = consensus_v2(units, {"glm": full, "sonnet": dict.fromkeys(units[2:], 1)})
    assert result.excluded == {"sonnet": 0.1}
    assert result.missing == {"glm": 0, "sonnet": 2}
    assert result.included == ("glm",)
    assert result.grades == full
    assert result.graded_by == dict.fromkeys(units, ("glm",))


def test_consensus_judge_missing_exactly_five_percent_stays_included():
    units = [("case", baseline.text_sha(str(i))) for i in range(20)]
    result = consensus_v2(
        units, {"glm": dict.fromkeys(units, 3), "sonnet": dict.fromkeys(units[1:], 1)}
    )
    assert result.included == ("glm", "sonnet")
    assert result.excluded == {}
    assert result.missing == {"glm": 0, "sonnet": 1}
    assert result.grades == {units[0]: 3, **dict.fromkeys(units[1:], 1)}
    assert result.graded_by[units[0]] == ("glm",)


def test_consensus_unit_without_valid_grade_is_unjudged_not_zero():
    units = [("case", baseline.text_sha(str(i))) for i in range(20)]
    partial = dict.fromkeys(units[1:], 2)
    result = consensus_v2(units, {"glm": partial, "sonnet": partial})
    assert result.included == ("glm", "sonnet")
    assert result.unjudged == {units[0]: "no_valid_grade"}
    assert units[0] not in result.grades
    assert units[0] not in result.graded_by


def test_consensus_all_judges_excluded_produces_no_grades():
    unit = ("case", baseline.text_sha("text"))
    result = consensus_v2([unit], {"glm": {}, "sonnet": {}})
    assert result.grades == {}
    assert result.included == ()
    assert result.excluded == {"glm": 1.0, "sonnet": 1.0}
    assert result.unjudged == {unit: "no_included_judge"}


def test_consensus_refuses_duplicate_unit():
    unit = ("case", baseline.text_sha("text"))
    with pytest.raises(ValueError, match="duplicate unit"):
        consensus_v2([unit, unit], {"glm": {unit: 3}})


def test_consensus_refuses_grade_outside_pool():
    with pytest.raises(ValueError, match="outside the pool"):
        consensus_v2([("case", "planned")], {"glm": {("case", "foreign"): 3}})


@pytest.mark.parametrize("grade", [True, False, -1, 4, 2.0, "2", None])
def test_consensus_refuses_non_integer_or_out_of_range_grade(grade):
    with pytest.raises(ValueError, match="integers 0-3"):
        consensus_v2([("case", "text")], {"glm": {("case", "text"): grade}})


@pytest.mark.parametrize("request_version,status", [(1, "valid"), (2, "invalid"), (2, "absent")])
def test_store_grades_ignores_non_valid_or_non_v2_attempts(request_version, status):
    valid = _valid_row()
    ignored = _valid_row("other", grade=0)
    ignored.update(request_version=request_version, status=status)
    grades, version = store_grades(
        [valid, ignored], {"case-1": valid["request_sha256"], "other": ignored["request_sha256"]}
    )
    assert grades == {("case-1", valid["records"][0]["text_sha256"]): 3}
    assert version == "fixture:v1"


def test_store_grades_ignores_record_for_unplanned_case():
    assert store_grades([_valid_row("foreign")], {"case-1": "a" * 64}) == ({}, "fixture:v1")


def test_store_grades_ignores_record_with_different_request_sha():
    assert store_grades([_valid_row()], {"case-1": "a" * 64}) == ({}, "fixture:v1")


def test_store_grades_refuses_two_counted_judge_versions():
    first = _valid_row()
    second = _valid_row(version="fixture:v2")
    assert first["request_sha256"] == second["request_sha256"]
    with pytest.raises(ValueError, match="mixes judge versions"):
        store_grades([first, second], {"case-1": first["request_sha256"]})


def test_store_grades_refuses_conflicting_grade_for_same_unit():
    first = _valid_row(grade=3)
    with pytest.raises(ValueError, match="conflicting grades"):
        store_grades([first, _valid_row(grade=1)], {"case-1": first["request_sha256"]})


def test_store_grades_accepts_same_grade_repeated_by_rebind():
    row = _valid_row()
    rebound = copy.deepcopy(row)
    rebound["reused"] = True
    rebound["records"][0]["address"]["source_revision"] = "new-revision"
    grades, version = store_grades([row, rebound], {"case-1": row["request_sha256"]})
    assert grades == {("case-1", row["records"][0]["text_sha256"]): 3}
    assert version == "fixture:v1"


def test_store_grades_returns_no_version_when_no_v2_attempt_exists():
    row = _valid_row()
    row["request_version"] = 1
    assert store_grades([row], {}) == ({}, None)


@pytest.mark.parametrize("status", ["invalid", "absent"])
def test_store_grades_returns_version_of_attempts_without_counted_grades(status):
    row = _valid_row()
    row.update(status=status, records=[])
    assert store_grades([row], {}) == ({}, "fixture:v1")


@pytest.mark.parametrize("version", [None, "", " ", 2])
def test_store_grades_refuses_attempt_without_nonempty_version(version):
    row = _valid_row()
    row.update(status="invalid", records=[], judge_version=version)
    with pytest.raises(ValueError, match="judge_version"):
        store_grades([row], {})


@pytest.mark.parametrize("status", ["valid", "invalid", "absent"])
def test_store_grades_refuses_record_version_different_from_its_attempt(status):
    row = _valid_row()
    row["status"] = status
    row["records"][0]["judge_version"] = "fixture:v2"
    with pytest.raises(ValueError, match="version"):
        store_grades([row], {})


def test_ruler_kept_case_matches_hand_computed_metrics():
    case = {
        "case_id": "case",
        "subset": "H",
        "seeds": ["a", "b", "c", "a", "d"],
        "sent": ["c", "e"],
    }
    grades = {
        ("case", key): value for key, value in {"a": 3, "b": 1, "c": 2, "d": 0, "e": 3}.items()
    }
    result = ruler_cases([case], grades, {})
    kept = result["cases"][0]
    assert kept["seeds"] == case["seeds"] and kept["sent"] == case["sent"]
    assert precision_at_5(kept["seeds"], kept["grades"]) == 2 / 5
    assert sent_precision(kept["sent"], kept["grades"]) == 1
    expected = (3 + 1 / math.log2(3) + 2 / 2) / (3 + 3 / math.log2(3) + 2 / 2 + 1 / math.log2(5))
    assert ndcg_at_5(kept["seeds"], kept["grades"]) == pytest.approx(expected)
    assert result["excluded_count"] == 0


@pytest.mark.parametrize("population", ["seeds", "sent"])
def test_ruler_excludes_case_with_unjudged_deciding_text_without_substituting_zero(population):
    bad = {"case_id": "bad", "subset": "Hm", "seeds": ["known"], "sent": ["known"]}
    bad[population].append("unknown")
    good = {"case_id": "good", "subset": "H", "seeds": ["known"], "sent": ["known"]}
    grades = {("bad", "known"): 3, ("good", "known"): 3}
    result = ruler_cases([bad, good], grades, {("bad", "unknown"): "no_valid_grade"})
    assert [case["case_id"] for case in result["cases"]] == ["good"]
    assert result["excluded"][0]["unjudged"] == {"unknown": "no_valid_grade"}
    assert "grades" not in result["excluded"][0]
    assert ("bad", "unknown") not in grades
    assert result["excluded_count"] == 1
    assert result["excluded_by_subset"] == {"H": 0, "Hm": 1}
    assert result["kept_by_subset"] == {"H": 1, "Hm": 0}
    if population == "seeds":
        for metric in (precision_at_5, ndcg_at_5):
            with pytest.raises(ValueError, match="unjudged"):
                metric(bad["seeds"], {"known": 3})
    else:
        with pytest.raises(ValueError, match="unjudged"):
            sent_precision(bad["sent"], {"known": 3})


def test_ruler_ungraded_seed_below_rank_five_does_not_exclude_case():
    case = {"case_id": "case", "subset": "H", "seeds": list("abcdefg"), "sent": ["a"]}
    result = ruler_cases([case], {("case", key): 3 for key in "abcde"}, {})
    kept = result["cases"][0]
    assert kept["seeds"] == list("abcdefg")
    assert result["excluded_count"] == 0
    assert precision_at_5(kept["seeds"], kept["grades"]) == 1
    assert ndcg_at_5(kept["seeds"], kept["grades"]) == 1


@pytest.mark.parametrize(
    "count,sizes", [(10, [10]), (11, [6, 5]), (21, [7, 7, 7]), (25, [9, 8, 8])]
)
def test_split_documents_is_balanced_sorted_and_independent_of_input_order(count, sizes):
    documents = [_request_document(_document(i)) for i in range(count)]
    parts = runner.split_documents("case", documents)
    assert [len(docs) for _, docs in parts] == sizes
    assert [case_id for case_id, _ in parts] == (
        ["case"] if count <= 10 else [f"case#{i}" for i in range(1, len(sizes) + 1)]
    )
    assert [doc["text_sha256"] for _, docs in parts for doc in docs] == sorted(
        doc["text_sha256"] for doc in documents
    )
    random.Random(123).shuffle(documents)
    assert runner.split_documents("case", documents) == parts


def test_split_documents_refuses_duplicate_hashes():
    doc = _request_document(_document(0))
    with pytest.raises(ValueError, match="unique text_sha256"):
        runner.split_documents("case", [doc, doc])


def test_case_plan_unions_top_five_and_sent_deduplicating_by_exact_hash():
    seeds = [_document(i) for i in range(6)]
    same_text_other_source = _document(100, text=seeds[0]["text"])
    sent = [same_text_other_source, _document(6)]
    entry, requests = runner.case_plan(_case(), _grade_row(seeds, sent))
    docs = requests[0]["documents"]
    assert {doc["text_sha256"] for doc in docs} == {doc["text_sha256"] for doc in seeds[:5] + sent}
    assert len(docs) == 6
    assert seeds[5]["text_sha256"] not in {doc["text_sha256"] for doc in docs}
    first = next(doc for doc in docs if doc["text_sha256"] == seeds[0]["text_sha256"])
    assert first["address"] == seeds[0]["chunk_address"]
    assert entry["seeds"] == [doc["text_sha256"] for doc in seeds[:5]]
    assert entry["sent"] == [doc["text_sha256"] for doc in sent]


def test_case_plan_keeps_rank_six_seed_when_it_was_sent():
    seeds = [_document(i) for i in range(6)]
    _, requests = runner.case_plan(_case(), _grade_row(seeds, [seeds[5]]))
    assert seeds[5]["text_sha256"] in {doc["text_sha256"] for doc in requests[0]["documents"]}


def test_case_plan_unaddressed_text_is_omitted_and_retains_reason():
    missing = _document(1, addressed=False)
    entry, requests = runner.case_plan(_case(), _grade_row([_document(0), missing]))
    assert entry["unaddressed"] == {missing["text_sha256"]: "address_unresolved"}
    assert all(
        doc["text_sha256"] != missing["text_sha256"] for r in requests for doc in r["documents"]
    )


def test_case_plan_uses_first_addressed_occurrence_after_unaddressed_duplicate():
    missing = _document(1, addressed=False)
    addressed = _document(2, text=missing["text"])
    later = _document(3, text=missing["text"])
    entry, requests = runner.case_plan(_case(), _grade_row([missing], [addressed, later]))
    assert entry["unaddressed"] == {}
    assert requests[0]["documents"] == [_request_document(addressed)]


def test_build_plan_reads_finished_baseline_and_omits_collection_exclusions(finished_run):
    run, _, plan = finished_run(
        [
            (_case(), _grade_row([_document(0)])),
            (_case("excluded", "Hm"), _grade_row([], status="excluded")),
        ]
    )
    assert plan["collection_excluded"] == ["excluded"]
    assert [case["case_id"] for case in plan["cases"]] == ["case-1"]
    assert [request["case_id"] for request in plan["requests"]] == ["case-1"]
    assert plan["run_sha256"] == parity.digest(parity.read(run / "manifest.json"))
    assert plan["baseline_report_sha256"] == parity.file_sha(run / "report.json")
    assert plan["split_rule"] == runner.SPLIT_RULE


def test_plan_cli_writes_the_plan_and_prints_counts(finished_run, tmp_path, capsys):
    run, _, plan = finished_run()
    out = tmp_path / "second"
    assert runner.main(["plan", "--run", str(run), "--out", str(out)]) == 0
    assert parity.read(out / "plan.json") == plan
    assert json.loads(capsys.readouterr().out) == {
        "cases": 1,
        "requests": 1,
        "collection_excluded": 0,
        "unaddressed": 0,
    }


def test_build_plan_refuses_run_without_report(finished_run):
    run, _, _ = finished_run()
    (run / "report.json").unlink()
    with pytest.raises(FileNotFoundError):
        runner.build_plan(run)


def test_build_plan_refuses_run_with_open_abort(finished_run):
    run, _, _ = finished_run()
    parity.write_new(run / "grade.abort.json", {"reason": "stopped"})
    with pytest.raises(baseline.IntegrityError, match="Open abort at grade"):
        runner.build_plan(run)


def test_build_plan_refuses_grade_row_of_another_run(finished_run):
    run, _, _ = finished_run()
    target = run / "grade" / "case-1.json"
    record = parity.read(target)
    record["run_sha256"] = "a" * 64
    _write_json(target, record)
    with pytest.raises(baseline.IntegrityError, match="Stage record integrity mismatch"):
        runner.build_plan(run)


def test_case_without_addressed_text_has_no_request_and_run_is_not_evidence(finished_run):
    missing = _document(0, addressed=False)
    _, out, plan = finished_run([(_case(), _grade_row([missing]))])
    assert plan["requests"] == []
    assert plan["cases"][0]["requests"] == []
    assert plan["cases"][0]["unaddressed"] == {missing["text_sha256"]: "address_unresolved"}
    summary = runner.consensus(out)
    assert summary["status"] == "NOT_EVIDENCE"
    assert summary["unjudged_units"] == {"address_unresolved": 1}
    assert summary["judged_precision_cases"] == 0
    assert summary["judged_precision_excluded"] == 1
    assert summary["excluded_by_subset"] == {"H": 1}
    assert summary["kept_by_subset"] == {"H": 0}
    assert summary["repeated_sent_texts"] == 0
    assert not (out / "ruler-input.json").exists()


def test_write_plan_accepts_identical_plan_twice(finished_run):
    _, out, plan = finished_run()
    original = (out / "plan.json").read_bytes()
    runner.write_plan(out, copy.deepcopy(plan))
    assert (out / "plan.json").read_bytes() == original


def test_write_plan_refuses_different_plan(finished_run):
    _, out, plan = finished_run()
    changed = copy.deepcopy(plan)
    changed["run_sha256"] = "a" * 64
    with pytest.raises(FileExistsError):
        runner.write_plan(out, changed)
    assert parity.read(out / "plan.json") == plan


def test_load_plan_false_reject_control_accepts_real_builder_output(finished_run):
    _, out, plan = finished_run()
    assert runner.load_plan(out) == plan


@pytest.mark.parametrize(
    "change,reason",
    [
        ("request_sha256", "request_sha256"),
        ("prompt_characters", "prompt_characters"),
        ("duplicate", "duplicate request id"),
        ("foreign", "outside the planned cases"),
        ("case_list", "case request lists disagree"),
    ],
)
def test_load_plan_refuses_inconsistent_request_rows(finished_run, change, reason):
    _, out, plan = finished_run()
    request = plan["requests"][0]
    if change == "request_sha256":
        request[change] = "a" * 64
    elif change == "prompt_characters":
        request[change] += 1
    elif change == "duplicate":
        plan["requests"].append(copy.deepcopy(request))
    elif change == "foreign":
        request["baseline_case_id"] = "foreign"
    else:
        plan["cases"][0]["requests"] = []
    _write_json(out / "plan.json", plan)
    with pytest.raises(ValueError, match=reason):
        runner.load_plan(out)


def test_fake_judge_receives_exact_text_and_question_without_hidden_metadata(finished_run):
    docs = [
        _document(i, text=f"[Контекст: Из документа Public {i}]\nExact text {i}.\n")
        for i in range(3)
    ]
    case = _case()
    _, out, plan = finished_run([(case, _grade_row(docs))])
    glm, sonnet = FakeJudge(), FakeJudge()
    runner.judge(out, "glm", client=glm)
    runner.judge(out, "sonnet", client=sonnet)
    assert glm.prompts == sonnet.prompts
    prompt = glm.prompts[0]
    assert case["query"] in prompt
    for doc in docs:
        assert doc["text"] in prompt
        assert doc["text_sha256"] not in prompt
        for value in doc["metadata"].values():
            assert value not in prompt
        for value in doc["chunk_address"].values():
            for marker in value if isinstance(value, list) else [value]:
                assert marker not in prompt
    for field in (
        "source_id",
        "source_revision",
        "section_path",
        "chunker_version",
        "tenant",
        "rank",
    ):
        assert field not in prompt
    request = plan["requests"][0]
    ordered = sorted(request["documents"], key=lambda doc: doc["text_sha256"])
    random.Random("20260925:v2:case-1").shuffle(ordered)
    assert [prompt.index(doc["text"]) for doc in ordered] == sorted(
        prompt.index(doc["text"]) for doc in ordered
    )


def test_outbound_counts_invalid_then_valid_attempt_and_resume_adds_nothing(finished_run):
    _, out, plan = finished_run()
    failed = runner.judge(out, "glm", client=FakeJudge("invalid reply"))
    request = plan["requests"][0]
    one = {"calls": 1, "texts": 3, "characters": request["prompt_characters"]}
    assert failed["outbound"] == one
    retried = runner.judge(out, "glm", client=FakeJudge())
    assert retried["outbound"] == {key: 2 * value for key, value in one.items()}
    cached = FakeJudge()
    resumed = runner.judge(out, "glm", client=cached)
    assert cached.prompts == []
    assert resumed["outbound"] == retried["outbound"]


def test_outbound_rebind_row_is_not_an_external_call(finished_run):
    _, out, plan = finished_run()
    first = runner.judge(out, "glm", client=FakeJudge())
    plan["requests"][0]["documents"][0]["address"]["source_revision"] = "new-revision"
    _write_json(out / "plan.json", plan)
    client = FakeJudge()
    resumed = runner.judge(out, "glm", client=client)
    assert resumed["reused"] == 1 and client.prompts == []
    assert resumed["outbound"] == first["outbound"]
    assert len(read_store(out / "glm.jsonl")) == 2
    assert read_store(out / "glm.jsonl")[-1]["reused"] is True


def test_outbound_refuses_attempt_with_request_sha_outside_plan(finished_run):
    _, _, plan = finished_run()
    with pytest.raises(ValueError, match="outside the plan"):
        runner.outbound([{"request_version": 2, "request_sha256": "a" * 64}], plan)


def test_judge_persists_raw_reply_hashes_outcomes_and_resumes_by_request_key(finished_run):
    _, out, plan = finished_run()
    client = FakeJudge()
    result = runner.judge(out, "glm", client=client)
    assert result == {
        "judge": "glm",
        "valid": 1,
        "invalid": 0,
        "absent": 0,
        "reused": 0,
        "pending": 0,
        "outbound": {"calls": 1, "texts": 3, "characters": len(client.prompts[0])},
    }
    store = out / "glm.jsonl"
    (row,) = read_store(store)
    assert row["raw_text"] == _reply(3)
    assert row["model"] == "fixture-reported-model"
    assert row["usage"] == {"tokens": 10} and row["elapsed_s"] == 0.125
    assert row["request_sha256"] == baseline.text_sha(client.prompts[0])
    request = plan["requests"][0]
    built = build_request_v2(
        case_id=request["case_id"],
        question=request["question"],
        documents=request["documents"],
        judge_version=v2.judge_version("glm", client),
    )
    assert row["request_key"] == built.request_key
    assert all(record["request_key"] == built.request_key for record in row["records"])
    before = store.read_bytes()
    cached = FakeJudge()
    resumed = runner.judge(out, "glm", client=cached)
    assert resumed["reused"] == 1 and resumed["valid"] == 0
    assert cached.prompts == []
    assert store.read_bytes() == before


def test_judge_limit_leaves_remaining_requests_pending(finished_run):
    _, out, _ = finished_run(
        [
            (_case("first"), _grade_row([_document(0)])),
            (_case("second"), _grade_row([_document(1)])),
        ]
    )
    client = FakeJudge()
    result = runner.judge(out, "glm", client=client, limit=1)
    assert result["valid"] == 1 and result["pending"] == 1
    assert len(client.prompts) == 1
    assert result["outbound"]["calls"] == 1


@pytest.mark.parametrize(
    "reply,limit,status", [("invalid", None, "invalid"), ("", None, "absent"), (None, 0, "pending")]
)
def test_judge_cli_returns_one_for_any_incomplete_outcome(
    finished_run, monkeypatch, capsys, reply, limit, status
):
    _, out, _ = finished_run()
    client = FakeJudge() if reply is None else FakeJudge(reply)
    monkeypatch.setattr(runner, "make_client", lambda name: client)
    args = ["judge", "--out", str(out), "--judge", "glm"]
    if limit is not None:
        args += ["--limit", str(limit)]
    assert runner.main(args) == 1
    assert json.loads(capsys.readouterr().out)[status] == 1


def test_judge_cli_returns_zero_when_all_requests_are_valid(finished_run, monkeypatch, capsys):
    _, out, _ = finished_run()
    monkeypatch.setattr(runner, "make_client", lambda name: FakeJudge())
    assert runner.main(["judge", "--out", str(out), "--judge", "glm"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] == 1


def test_sonnet_make_client_requires_endpoint_environment(monkeypatch):
    monkeypatch.delenv("RAG_JUDGE_GK_BASE", raising=False)
    with pytest.raises(ValueError, match="RAG_JUDGE_GK_BASE is required"):
        runner.make_client("sonnet")


def test_sonnet_cli_without_endpoint_exits_before_client_or_request(finished_run, monkeypatch):
    _, out, _ = finished_run()
    monkeypatch.delenv("RAG_JUDGE_GK_BASE", raising=False)
    client = FakeJudge()
    created = []

    def factory(name):
        created.append(name)
        return client

    monkeypatch.setattr(runner, "make_client", factory)
    with pytest.raises(SystemExit) as error:
        runner.main(["judge", "--out", str(out), "--judge", "sonnet"])
    assert error.value.code == 2
    assert created == [] and client.prompts == []
    assert not (out / "sonnet.jsonl").exists()


def test_sonnet_endpoint_is_used_but_never_printed_or_stored(finished_run, monkeypatch, capsys):
    _, out, _ = finished_run()
    endpoint = "https://HIDDEN_ENDPOINT.invalid/private/"
    monkeypatch.setenv("RAG_JUDGE_GK_BASE", endpoint)
    client = FakeJudge()
    configured = []

    def factory(base):
        configured.append(base)
        return client

    monkeypatch.setattr(runner, "SonnetClient", factory)
    assert runner.main(["judge", "--out", str(out), "--judge", "sonnet"]) == 0
    assert configured == [endpoint]
    output = capsys.readouterr()
    assert endpoint not in output.out + output.err
    store = out / "sonnet.jsonl"
    assert endpoint not in store.read_text(encoding="utf-8")
    version = json.loads(read_store(store)[0]["judge_version"])
    assert version["endpoint_sha256"] == baseline.text_sha(endpoint.rstrip("/"))


@pytest.mark.parametrize("settings", [None, "HIDDEN_GLM_SETTINGS.json"])
def test_glm_settings_use_environment_or_default_without_real_client(monkeypatch, settings):
    if settings is None:
        monkeypatch.delenv("RAG_JUDGE_GLM_SETTINGS", raising=False)
    else:
        monkeypatch.setenv("RAG_JUDGE_GLM_SETTINGS", settings)
    seen = []
    client = FakeJudge()

    def factory(path):
        seen.append(path)
        return client

    monkeypatch.setattr(runner, "GlmClient", factory)
    assert runner.make_client("glm") is client
    assert [str(path) if path is not None else None for path in seen] == [settings]


def test_judge_version_is_exact_compact_sorted_json_literal():
    assert v2.judge_version("glm", FakeJudge()) == (
        '{"judge":"glm","parameters":{"model":"fixture","temperature":0},"route":"fixture"}'
    )


def test_judge_version_hashes_endpoint_without_trailing_slash():
    endpoint = "https://fixture.invalid/path"
    version = json.loads(v2.judge_version("sonnet", FakeJudge(), endpoint + "///"))
    assert version == {
        "judge": "sonnet",
        "route": "fixture",
        "parameters": {"model": "fixture", "temperature": 0},
        "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
    }
    assert v2.judge_version("sonnet", FakeJudge(), endpoint) == v2.judge_version(
        "sonnet", FakeJudge(), endpoint + "/"
    )


@pytest.mark.parametrize("name", ["glm", "sonnet"])
def test_both_clis_store_identical_judge_version_for_same_client_and_endpoint(
    finished_run, tmp_path, monkeypatch, name
):
    _, out, plan = finished_run()
    endpoint = "https://fixture.invalid/"
    monkeypatch.setenv("RAG_JUDGE_GK_BASE", endpoint)
    client = FakeJudge()
    monkeypatch.setattr(v2, "_client", lambda args: client)
    cases = tmp_path / "cases.jsonl"
    _write_json(
        cases, {key: plan["requests"][0][key] for key in ("case_id", "question", "documents")}
    )
    store = tmp_path / "explicit.jsonl"
    assert (
        v2.main(
            ["--judge", name, "--cases", str(cases), "--store", str(store), "--gk-base", endpoint]
        )
        == 0
    )
    runner.judge(out, name, client=client)
    explicit = read_store(store)[0]
    baseline_row = read_store(out / f"{name}.jsonl")[0]
    assert explicit["judge_version"] == baseline_row["judge_version"]
    assert explicit["request_key"] == baseline_row["request_key"]


def test_consensus_full_valid_stores_write_ruler_input_accepted_by_metrics(
    finished_run, monkeypatch, capsys
):
    _, out, plan = finished_run()
    monkeypatch.delenv("RAG_JUDGE_GK_BASE", raising=False)
    runner.judge(out, "glm", client=FakeJudge(grade=3))
    runner.judge(out, "sonnet", client=FakeJudge(grade=2))
    assert runner.main(["consensus", "--out", str(out)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ok"
    assert summary["units"] == 3
    assert summary["included_judges"] == ["glm", "sonnet"]
    assert summary["excluded_judges"] == {}
    assert summary["stores"] == {
        name: parity.file_sha(out / f"{name}.jsonl") for name in runner.JUDGES
    }
    assert summary["run_sha256"] == plan["run_sha256"]
    assert summary["units_by_grade_count"] == {"2": 3}
    payload = parity.read(out / "ruler-input.json")
    for key in (
        "judged_precision_cases",
        "judged_precision_excluded",
        "excluded_by_subset",
        "kept_by_subset",
        "repeated_sent_texts",
    ):
        assert payload[key] == summary[key]
    assert payload["ruler"]["repeated_sent_texts"] == summary["repeated_sent_texts"] == 0
    (case,) = payload["ruler"]["cases"]
    assert case["grades"] == {doc["text_sha256"]: 2 for doc in plan["requests"][0]["documents"]}
    assert precision_at_5(case["seeds"], case["grades"]) == 3 / 5
    assert sent_precision(case["sent"], case["grades"]) == 1
    assert ndcg_at_5(case["seeds"], case["grades"]) == 1


def test_consensus_without_stores_is_not_evidence_and_writes_no_ruler_input(finished_run, capsys):
    _, out, _ = finished_run()
    summary = runner.consensus(out)
    assert summary["status"] == "NOT_EVIDENCE"
    assert summary["stores"] == {"glm": None, "sonnet": None}
    assert summary["included_judges"] == []
    assert not (out / "ruler-input.json").exists()
    assert runner.main(["consensus", "--out", str(out)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "NOT_EVIDENCE"
    assert not (out / "ruler-input.json").exists()


def test_consensus_missing_judge_is_excluded_and_other_judge_alone_forms_grades(finished_run):
    _, out, _ = finished_run()
    runner.judge(out, "glm", client=FakeJudge(grade=1))
    summary = runner.consensus(out)
    assert summary["status"] == "ok"
    assert summary["excluded_judges"] == {"sonnet": 1.0}
    assert summary["included_judges"] == ["glm"]
    assert summary["missing"] == {"glm": 0, "sonnet": 3}
    assert summary["units_by_grade_count"] == {"1": 3}
    assert set(parity.read(out / "ruler-input.json")["ruler"]["cases"][0]["grades"].values()) == {1}


def test_consensus_split_request_grades_map_back_to_baseline_case(finished_run):
    docs = [_document(i) for i in range(11)]
    _, out, plan = finished_run([(_case(), _grade_row(docs[:5], docs))])
    assert [request["case_id"] for request in plan["requests"]] == ["case-1#1", "case-1#2"]
    for name in runner.JUDGES:
        runner.judge(out, name, client=FakeJudge(grade=2))
        assert {row["case_id"] for row in read_store(out / f"{name}.jsonl")} == {
            "case-1#1",
            "case-1#2",
        }
    summary = runner.consensus(out)
    assert summary["status"] == "ok" and summary["units"] == 11
    (case,) = parity.read(out / "ruler-input.json")["ruler"]["cases"]
    assert case["case_id"] == "case-1"
    assert case["grades"] == {doc["text_sha256"]: 2 for doc in docs}


def test_consensus_unaddressed_text_excludes_precision_case_with_address_reason(finished_run):
    missing = _document(0, addressed=False)
    _, out, _ = finished_run(
        [
            (_case("bad", "Hm"), _grade_row([missing, _document(1)])),
            (_case("good", "H"), _grade_row([_document(2)])),
        ]
    )
    for name in runner.JUDGES:
        runner.judge(out, name, client=FakeJudge())
    summary = runner.consensus(out)
    assert summary["status"] == "ok"
    assert summary["judged_precision_excluded"] == 1
    assert summary["judged_precision_cases"] == 1
    assert summary["unjudged_units"] == {"address_unresolved": 1}
    assert summary["excluded_by_subset"] == {"H": 0, "Hm": 1}
    assert summary["kept_by_subset"] == {"H": 1, "Hm": 0}
    ruler = parity.read(out / "ruler-input.json")["ruler"]
    assert ruler["excluded"][0]["unjudged"] == {missing["text_sha256"]: "address_unresolved"}
    assert [case["case_id"] for case in ruler["cases"]] == ["good"]


def test_ruler_deduplicates_sent_texts_but_preserves_plan_and_repeated_seeds():
    relevant = _document(0)
    repeated = _document(1, text=relevant["text"])
    irrelevant = _document(2)
    entry, _ = runner.case_plan(
        _case(), _grade_row([relevant, repeated, irrelevant], [relevant, repeated, irrelevant])
    )
    first, other = relevant["text_sha256"], irrelevant["text_sha256"]
    assert repeated["chunk_address"] != relevant["chunk_address"]
    result = ruler_cases([entry], {("case-1", first): 3, ("case-1", other): 0}, {})
    (kept,) = result["cases"]
    assert entry["sent"] == [first, first, other]
    assert kept["sent"] == [first, other]
    assert sent_precision(kept["sent"], kept["grades"]) == 1 / 2
    assert result["repeated_sent_texts"] == 1
    assert kept["seeds"] == entry["seeds"] == [first, first, other]
    assert precision_at_5(kept["seeds"], kept["grades"]) == 1 / 5


def test_ruler_counts_repeated_sent_texts_in_excluded_cases_too():
    cases = [
        {"case_id": "kept", "subset": "H", "seeds": ["a"], "sent": ["a", "a"]},
        {"case_id": "excluded", "subset": "Hm", "seeds": [], "sent": ["b", "b", "b"]},
    ]
    result = ruler_cases(cases, {("kept", "a"): 2}, {})
    assert result["repeated_sent_texts"] == 3
    assert result["excluded_count"] == 1


@pytest.mark.parametrize("reply,status", [("invalid", "invalid"), ("", "absent")])
def test_consensus_refuses_store_mixing_valid_and_failed_attempt_versions(
    finished_run, reply, status
):
    _, out, plan = finished_run()
    store = out / "glm.jsonl"
    v2.run_judge_v2(FakeJudge(), plan["requests"], store, judge_version="version-A")
    v2.run_judge_v2(FakeJudge(reply), plan["requests"], store, judge_version="version-B")
    assert [row["status"] for row in read_store(store)] == ["valid", status]
    with pytest.raises(ValueError, match="one reply store mixes judge versions"):
        runner.consensus(out)
    assert not (out / "ruler-input.json").exists()


@pytest.mark.parametrize("change", ["parameters", "endpoint"])
@pytest.mark.parametrize("reply", [None, "invalid", ""])
def test_judge_refuses_changed_version_before_sending_and_preserves_store(
    finished_run, monkeypatch, change, reply
):
    _, out, _ = finished_run()
    monkeypatch.setenv("RAG_JUDGE_GK_BASE", "https://first.invalid/")
    client = FakeJudge() if reply is None else FakeJudge(reply)
    runner.judge(out, "sonnet", client=client)
    store = out / "sonnet.jsonl"
    before = store.read_bytes()
    changed = FakeJudge()
    if change == "parameters":
        changed.parameters = {"model": "other-model", "temperature": 0}
    else:
        monkeypatch.setenv("RAG_JUDGE_GK_BASE", "https://second.invalid/")
    with pytest.raises(ValueError) as error:
        runner.judge(out, "sonnet", client=changed)
    assert str(error.value) == (
        "the store holds attempts of another judge version; use a new judge directory"
    )
    assert changed.prompts == []
    assert store.read_bytes() == before


def test_judge_false_reject_control_resumes_same_version_with_all_attempt_outcomes(
    finished_run, monkeypatch
):
    _, out, _ = finished_run([(_case(f"case-{i}"), _grade_row([_document(i)])) for i in range(3)])
    monkeypatch.setenv("RAG_JUDGE_GK_BASE", "https://same.invalid/")
    runner.judge(out, "sonnet", client=FakeJudge(_reply(1), "invalid", ""))
    store = out / "sonnet.jsonl"
    assert [row["status"] for row in read_store(store)] == ["valid", "invalid", "absent"]
    assert runner.consensus(out)["status"] == "NOT_EVIDENCE"
    resumed = FakeJudge()
    result = runner.judge(out, "sonnet", client=resumed)
    assert result["reused"] == 1 and result["valid"] == 2
    assert len(resumed.prompts) == 2
    assert runner.consensus(out)["status"] == "ok"


def test_outbound_and_consensus_refuse_foreign_case_with_planned_prompt_hash(finished_run):
    _, out, plan = finished_run()
    foreign = {**plan["requests"][0], "case_id": "foreign"}
    v2.run_judge_v2(FakeJudge(), [foreign], out / "glm.jsonl", judge_version="fixture")
    rows = read_store(out / "glm.jsonl")
    assert rows[0]["request_sha256"] == plan["requests"][0]["request_sha256"]
    with pytest.raises(ValueError, match="reply store holds an attempt outside the plan"):
        runner.outbound(rows, plan)
    with pytest.raises(ValueError, match="reply store holds an attempt outside the plan"):
        runner.consensus(out)
    assert not (out / "ruler-input.json").exists()


def test_outbound_false_reject_control_counts_two_planned_cases_with_identical_prompts(
    finished_run, tmp_path
):
    cases = [_case("first"), _case("second")]
    for case in cases:
        case["query"] = "The same question?"
    _, _, plan = finished_run([(case, _grade_row([_document(0)])) for case in cases])
    first, second = plan["requests"]
    assert first["request_sha256"] == second["request_sha256"]
    rows = []
    for request in plan["requests"]:
        store = tmp_path / f"{request['case_id']}.jsonl"
        v2.run_judge_v2(FakeJudge(), [request], store, judge_version="fixture")
        rows.extend(read_store(store))
    assert runner.outbound(rows, plan) == {
        "calls": 2,
        "texts": 2,
        "characters": first["prompt_characters"] + second["prompt_characters"],
    }


@pytest.mark.parametrize("reply", ["invalid", ""])
def test_consensus_failed_stores_report_exclusion_counts_without_ruler_input(finished_run, reply):
    _, out, _ = finished_run(
        [
            (_case("first", "H"), _grade_row([_document(0)], [_document(0), _document(0)])),
            (_case("second", "Hm"), _grade_row([_document(1)])),
        ]
    )
    for name in runner.JUDGES:
        runner.judge(out, name, client=FakeJudge(reply, reply))
    summary = runner.consensus(out)
    assert summary["status"] == "NOT_EVIDENCE"
    assert summary["judged_precision_cases"] == 0
    assert summary["judged_precision_excluded"] == 2
    assert summary["excluded_by_subset"] == {"H": 1, "Hm": 1}
    assert summary["kept_by_subset"] == {"H": 0, "Hm": 0}
    assert summary["repeated_sent_texts"] == 1
    assert not (out / "ruler-input.json").exists()
