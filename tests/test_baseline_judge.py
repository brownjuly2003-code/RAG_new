"""Judge v2 regrading of baseline contexts: plan, split, runner, consensus and ruler adapter.

Runs are fixtures written with the baseline collector's own helpers; judges are fakes. The
registry names one judge (plan decision D12); the consensus rules are tested with two fake
voices, `alpha` and `beta`, and the registered mode by the tests that ask for `one_judge`.
"""

import copy
import hashlib
import itertools
import json
import math
import random
import re
import shutil
from pathlib import Path
from typing import ClassVar

import pytest

from evaluation import isolated_request as isolated
from evaluation.blinded_judge import quadratic_kappa, read_store
from evaluation.blinded_judge_clients import JudgeUnavailable, Reply
from evaluation.judge_consensus import consensus_v2, retest_stability, ruler_cases, store_grades
from evaluation.judge_contract import build_request_v2, make_grade_records, parse_grades_v2
from evaluation.semantic_ruler import ndcg_at_5, precision_at_5, sent_precision
from scripts import baseline_judge as runner
from scripts import p2_opus_reference as reference
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from scripts import relevance_judge_v2 as v2

REGISTERED = runner.JUDGES
VOICES = ("alpha", "beta")
# The record of a session that loaded nothing: what the clean route keeps beside a reply.
SESSION = {
    "cli_version": "9.9.9",
    "model": "fixture-reported-model",
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}


@pytest.fixture(autouse=True)
def two_voices(monkeypatch):
    monkeypatch.setattr(runner, "JUDGES", VOICES)


@pytest.fixture
def one_judge(monkeypatch):
    monkeypatch.setattr(runner, "JUDGES", REGISTERED)


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
        return isolated.IsolatedReply(
            text, "fixture-reported-model", {"tokens": 10}, 0.125, SESSION
        )


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
        "session": SESSION,
    }


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def test_consensus_two_disagreeing_judges_give_lower_median():
    unit = ("case", baseline.text_sha("text"))
    result = consensus_v2([unit], {"alpha": {unit: 3}, "beta": {unit: 1}})
    assert result.grades == {unit: 1}


@pytest.mark.parametrize("a,b", list(itertools.product(range(4), repeat=2)))
def test_consensus_false_reject_control_all_valid_pairs_are_accepted(a, b):
    unit = ("case", baseline.text_sha("text"))
    result = consensus_v2([unit], {"alpha": {unit: a}, "beta": {unit: b}})
    assert result.included == ("alpha", "beta")
    assert result.grades == {unit: min(a, b)}
    assert result.unjudged == {}
    assert result.graded_by == {unit: ("alpha", "beta")}


def test_consensus_judge_missing_more_than_five_percent_is_excluded():
    units = [("case", baseline.text_sha(str(i))) for i in range(20)]
    full = dict.fromkeys(units, 3)
    result = consensus_v2(units, {"alpha": full, "beta": dict.fromkeys(units[2:], 1)})
    assert result.excluded == {"beta": 0.1}
    assert result.missing == {"alpha": 0, "beta": 2}
    assert result.included == ("alpha",)
    assert result.grades == full
    assert result.graded_by == dict.fromkeys(units, ("alpha",))


def test_consensus_judge_missing_exactly_five_percent_stays_included():
    units = [("case", baseline.text_sha(str(i))) for i in range(20)]
    result = consensus_v2(
        units, {"alpha": dict.fromkeys(units, 3), "beta": dict.fromkeys(units[1:], 1)}
    )
    assert result.included == ("alpha", "beta")
    assert result.excluded == {}
    assert result.missing == {"alpha": 0, "beta": 1}
    assert result.grades == {units[0]: 3, **dict.fromkeys(units[1:], 1)}
    assert result.graded_by[units[0]] == ("alpha",)


def test_consensus_unit_without_valid_grade_is_unjudged_not_zero():
    units = [("case", baseline.text_sha(str(i))) for i in range(20)]
    partial = dict.fromkeys(units[1:], 2)
    result = consensus_v2(units, {"alpha": partial, "beta": partial})
    assert result.included == ("alpha", "beta")
    assert result.unjudged == {units[0]: "no_valid_grade"}
    assert units[0] not in result.grades
    assert units[0] not in result.graded_by


def test_consensus_all_judges_excluded_produces_no_grades():
    unit = ("case", baseline.text_sha("text"))
    result = consensus_v2([unit], {"alpha": {}, "beta": {}})
    assert result.grades == {}
    assert result.included == ()
    assert result.excluded == {"alpha": 1.0, "beta": 1.0}
    assert result.unjudged == {unit: "no_included_judge"}


def test_consensus_refuses_duplicate_unit():
    unit = ("case", baseline.text_sha("text"))
    with pytest.raises(ValueError, match="duplicate unit"):
        consensus_v2([unit, unit], {"alpha": {unit: 3}})


def test_consensus_refuses_grade_outside_pool():
    with pytest.raises(ValueError, match="outside the pool"):
        consensus_v2([("case", "planned")], {"alpha": {("case", "foreign"): 3}})


@pytest.mark.parametrize("grade", [True, False, -1, 4, 2.0, "2", None])
def test_consensus_refuses_non_integer_or_out_of_range_grade(grade):
    with pytest.raises(ValueError, match="integers 0-3"):
        consensus_v2([("case", "text")], {"alpha": {("case", "text"): grade}})


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
        "retest_cases": 1,
        "retest_requests": 1,
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
    alpha, beta = FakeJudge(), FakeJudge()
    runner.judge(out, "alpha", client=alpha)
    runner.judge(out, "beta", client=beta)
    assert alpha.prompts == beta.prompts
    prompt = alpha.prompts[0]
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
    failed = runner.judge(out, "alpha", client=FakeJudge("invalid reply"))
    request = plan["requests"][0]
    one = {"calls": 1, "texts": 3, "characters": request["prompt_characters"]}
    assert failed["outbound"] == one
    retried = runner.judge(out, "alpha", client=FakeJudge())
    assert retried["outbound"] == {key: 2 * value for key, value in one.items()}
    cached = FakeJudge()
    resumed = runner.judge(out, "alpha", client=cached)
    assert cached.prompts == []
    assert resumed["outbound"] == retried["outbound"]


def test_a_request_is_not_sent_again_after_three_replies_of_a_wrong_form(finished_run):
    _, out, _ = finished_run()
    for _ in range(runner.FORM_ATTEMPTS):
        failed = runner.judge(out, "alpha", client=FakeJudge("invalid reply"))
        assert failed["invalid"] == 1 and failed["exhausted"] == 0
    silent = FakeJudge()
    stopped = runner.judge(out, "alpha", client=silent)
    assert silent.prompts == []
    assert stopped["exhausted"] == 1 and stopped["valid"] == stopped["pending"] == 0
    assert len(read_store(out / "alpha.jsonl")) == runner.FORM_ATTEMPTS


def test_a_request_without_a_reply_is_not_an_attempt(finished_run):
    _, out, _ = finished_run()

    class Down(FakeJudge):
        def grade(self, prompt):
            self.prompts.append(prompt)
            raise JudgeUnavailable("cli_exit", "Claude CLI exited with 1")

    for _ in range(runner.FORM_ATTEMPTS + 1):
        assert runner.judge(out, "alpha", client=Down())["absent"] == 1
    answered = runner.judge(out, "alpha", client=FakeJudge())
    assert answered["valid"] == 1 and answered["exhausted"] == 0


def test_outbound_rebind_row_is_not_an_external_call(finished_run):
    _, out, plan = finished_run()
    first = runner.judge(out, "alpha", client=FakeJudge())
    plan["requests"][0]["documents"][0]["address"]["source_revision"] = "new-revision"
    _write_json(out / "plan.json", plan)
    client = FakeJudge()
    resumed = runner.judge(out, "alpha", client=client)
    assert resumed["reused"] == 1 and client.prompts == []
    assert resumed["outbound"] == first["outbound"]
    assert len(read_store(out / "alpha.jsonl")) == 2
    assert read_store(out / "alpha.jsonl")[-1]["reused"] is True


def test_outbound_refuses_attempt_with_request_sha_outside_plan(finished_run):
    _, _, plan = finished_run()
    with pytest.raises(ValueError, match="outside the plan"):
        runner.outbound([{"request_version": 2, "request_sha256": "a" * 64}], plan)


def test_judge_persists_raw_reply_hashes_outcomes_and_resumes_by_request_key(finished_run):
    _, out, plan = finished_run()
    client = FakeJudge()
    result = runner.judge(out, "alpha", client=client)
    assert result == {
        "judge": "alpha",
        "valid": 1,
        "invalid": 0,
        "absent": 0,
        "reused": 0,
        "pending": 0,
        "exhausted": 0,
        "outbound": {"calls": 1, "texts": 3, "characters": len(client.prompts[0])},
    }
    store = out / "alpha.jsonl"
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
        judge_version=v2.judge_version("alpha", client),
    )
    assert row["request_key"] == built.request_key
    assert all(record["request_key"] == built.request_key for record in row["records"])
    before = store.read_bytes()
    cached = FakeJudge()
    resumed = runner.judge(out, "alpha", client=cached)
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
    result = runner.judge(out, "alpha", client=client, limit=1)
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
    args = ["judge", "--out", str(out), "--judge", "alpha"]
    if limit is not None:
        args += ["--limit", str(limit)]
    assert runner.main(args) == 1
    assert json.loads(capsys.readouterr().out)[status] == 1


def test_judge_cli_returns_zero_when_all_requests_are_valid(finished_run, monkeypatch, capsys):
    _, out, _ = finished_run()
    monkeypatch.setattr(runner, "make_client", lambda name: FakeJudge())
    assert runner.main(["judge", "--out", str(out), "--judge", "alpha"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] == 1


def test_judge_version_is_exact_compact_sorted_json_literal():
    assert v2.judge_version("alpha", FakeJudge()) == (
        '{"judge":"alpha","parameters":{"model":"fixture","temperature":0},"route":"fixture"}'
    )


def test_judge_version_hashes_endpoint_without_trailing_slash():
    endpoint = "https://fixture.invalid/path"
    version = json.loads(v2.judge_version("beta", FakeJudge(), endpoint + "///"))
    assert version == {
        "judge": "beta",
        "route": "fixture",
        "parameters": {"model": "fixture", "temperature": 0},
        "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
    }
    assert v2.judge_version("beta", FakeJudge(), endpoint) == v2.judge_version(
        "beta", FakeJudge(), endpoint + "/"
    )


def test_consensus_full_valid_stores_write_ruler_input_accepted_by_metrics(finished_run, capsys):
    _, out, plan = finished_run()
    runner.judge(out, "alpha", client=FakeJudge(grade=3))
    runner.judge(out, "beta", client=FakeJudge(grade=2))
    assert runner.main(["consensus", "--out", str(out)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ok"
    assert summary["units"] == 3
    assert summary["included_judges"] == ["alpha", "beta"]
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
    assert summary["stores"] == {"alpha": None, "beta": None}
    assert summary["included_judges"] == []
    assert not (out / "ruler-input.json").exists()
    assert runner.main(["consensus", "--out", str(out)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "NOT_EVIDENCE"
    assert not (out / "ruler-input.json").exists()


def test_consensus_missing_judge_is_excluded_and_other_judge_alone_forms_grades(finished_run):
    _, out, _ = finished_run()
    runner.judge(out, "alpha", client=FakeJudge(grade=1))
    summary = runner.consensus(out)
    assert summary["status"] == "ok"
    assert summary["excluded_judges"] == {"beta": 1.0}
    assert summary["included_judges"] == ["alpha"]
    assert summary["missing"] == {"alpha": 0, "beta": 3}
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
    store = out / "alpha.jsonl"
    v2.run_judge_v2(FakeJudge(), plan["requests"], store, judge_version="version-A")
    v2.run_judge_v2(FakeJudge(reply), plan["requests"], store, judge_version="version-B")
    assert [row["status"] for row in read_store(store)] == ["valid", status]
    with pytest.raises(ValueError, match="one reply store mixes judge versions"):
        runner.consensus(out)
    assert not (out / "ruler-input.json").exists()


@pytest.mark.parametrize("change", ["parameters", "route"])
@pytest.mark.parametrize("reply", [None, "invalid", ""])
def test_judge_refuses_changed_version_before_sending_and_preserves_store(
    finished_run, change, reply
):
    _, out, _ = finished_run()
    client = FakeJudge() if reply is None else FakeJudge(reply)
    runner.judge(out, "beta", client=client)
    store = out / "beta.jsonl"
    before = store.read_bytes()
    changed = FakeJudge()
    if change == "parameters":
        changed.parameters = {"model": "other-model", "temperature": 0}
    else:
        changed.route = "another route"
    with pytest.raises(ValueError) as error:
        runner.judge(out, "beta", client=changed)
    assert str(error.value) == (
        "the store holds attempts of another judge version; use a new judge directory"
    )
    assert changed.prompts == []
    assert store.read_bytes() == before


def test_judge_false_reject_control_resumes_same_version_with_all_attempt_outcomes(finished_run):
    _, out, _ = finished_run([(_case(f"case-{i}"), _grade_row([_document(i)])) for i in range(3)])
    runner.judge(out, "beta", client=FakeJudge(_reply(1), "invalid", ""))
    store = out / "beta.jsonl"
    assert [row["status"] for row in read_store(store)] == ["valid", "invalid", "absent"]
    assert runner.consensus(out)["status"] == "NOT_EVIDENCE"
    resumed = FakeJudge()
    result = runner.judge(out, "beta", client=resumed)
    assert result["reused"] == 1 and result["valid"] == 2
    assert len(resumed.prompts) == 2
    assert runner.consensus(out)["status"] == "ok"


def test_outbound_and_consensus_refuse_foreign_case_with_planned_prompt_hash(finished_run):
    _, out, plan = finished_run()
    foreign = {**plan["requests"][0], "case_id": "foreign"}
    v2.run_judge_v2(FakeJudge(), [foreign], out / "alpha.jsonl", judge_version="fixture")
    rows = read_store(out / "alpha.jsonl")
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


class TextJudge(FakeJudge):
    """Grades every presented document by a rule on its text, whatever the order of requests."""

    def __init__(self, rule):
        super().__init__()
        self.rule = rule

    def grade(self, prompt):
        self.prompts.append(prompt)
        blocks = re.split(r"^D\d+$", prompt, flags=re.MULTILINE)[1:]
        grades = [{"doc": f"D{i}", "grade": self.rule(block)} for i, block in enumerate(blocks, 1)]
        return isolated.IsolatedReply(
            json.dumps({"grades": grades}), "fixture-reported-model", {"tokens": 10}, 0.125, SESSION
        )


def _chunk_number(block):
    return int(re.search(r"Exact policy chunk (\d+)\.", block).group(1))


def _retest_run(finished_run, h=12, hm=3):
    pairs = [(_case(f"h-{i:02d}"), _grade_row([_document(i)])) for i in range(h)]
    pairs += [(_case(f"m-{i}", "Hm"), _grade_row([_document(100 + i)])) for i in range(hm)]
    return finished_run(pairs)


def _retest_order(case_ids):
    return sorted(
        case_ids,
        key=lambda case_id: hashlib.sha256(f"20260925:retest:{case_id}".encode()).hexdigest(),
    )


def test_registered_judge_is_opus_alone_on_the_clean_route_with_the_prompt_of_the_p2_reference(
    one_judge,
):
    assert runner.JUDGES == ("opus",)
    client = runner.make_client("opus")
    assert isinstance(client, runner.OpusCliClient)
    assert client.arguments == isolated.arguments(reference.SYSTEM_PROMPT)
    assert client.arguments[1] == "--safe-mode"
    assert client.arguments[client.arguments.index("--model") + 1] == "claude-opus-5-5"
    assert client.arguments[client.arguments.index("--effort") + 1] == "max"
    assert client.arguments[client.arguments.index("--tools") + 1] == ""
    assert "--no-session-persistence" in client.arguments
    prompt_sha = hashlib.sha256(reference.SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert json.loads(v2.judge_version("opus", client)) == {
        "judge": "opus",
        "parameters": {
            "effort": "max",
            "model": "claude-opus-5-5",
            "session": isolated.SESSION,
            "system_prompt_sha256": prompt_sha,
            "tools": "none",
        },
        "route": "Claude Code CLI in safe mode, first-party provider",
    }
    # The judge is not the collection it took its prompt from: that one went by another route.
    assert client.arguments != reference.CLI_ARGS and "--safe-mode" not in reference.CLI_ARGS
    spec = " ".join(
        (Path(__file__).resolve().parents[1] / "docs/specs/semantic-precision-metrics.md")
        .read_text(encoding="utf-8")
        .split()
    )
    assert prompt_sha in spec
    assert isolated.ROUTE in spec and isolated.SESSION in spec
    assert runner.RETEST_RULE.split(";")[0].replace("'", "`") in spec


@pytest.mark.parametrize("name", ["glm", "sonnet", "mistral", "alpha", "claude-sonnet-5", ""])
def test_no_route_exists_for_a_model_outside_the_registry(finished_run, one_judge, name):
    with pytest.raises(ValueError, match="no route is registered for the judge"):
        runner.make_client(name)
    _, out, _ = finished_run()
    with pytest.raises(ValueError, match="unknown judge"):
        runner.judge(out, name, client=FakeJudge())
    with pytest.raises(SystemExit) as error:
        runner.main(["judge", "--out", str(out), "--judge", name])
    assert error.value.code == 2
    assert not list(out.glob("*.jsonl"))
    assert not hasattr(runner, "GlmClient") and not hasattr(runner, "SonnetClient")


def test_a_registered_name_without_a_route_is_refused():
    with pytest.raises(ValueError, match="no route is registered for the judge alpha"):
        runner.make_client("alpha")
    with pytest.raises(ValueError, match="no route is registered for the judge opus"):
        runner.make_client("opus")


def test_make_client_takes_the_cli_path_from_the_environment(one_judge, monkeypatch):
    monkeypatch.setenv("RAG_JUDGE_CLAUDE_CLI", " C:/HIDDEN/claude.cmd ")
    assert runner.make_client("opus").executable == "C:/HIDDEN/claude.cmd"
    monkeypatch.delenv("RAG_JUDGE_CLAUDE_CLI")
    assert runner.make_client("opus").executable is None


def _stream(described=None, **changes):
    """The event stream of one clean request, as the CLI prints it: one JSON event a line."""
    events = [
        {
            "type": "system",
            "subtype": "init",
            "cwd": "HIDDEN_DIRECTORY",
            "tools": [],
            "mcp_servers": [],
            "slash_commands": [],
            "skills": [],
            "plugins": [],
            "agents": [],
            "model": "claude-opus-5-5",
            "claude_code_version": "9.9.9",
            **(described or {}),
        },
        {
            "type": "assistant",
            "parent_tool_use_id": None,
            "message": {
                "id": "msg_1",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": _reply(1)}],
            },
        },
        {
            "type": "result",
            "is_error": False,
            "terminal_reason": "completed",
            "stop_reason": "end_turn",
            "num_turns": 1,
            "result": _reply(1),
            "modelUsage": {
                "claude-opus-5-5": {"canonicalModel": "claude-opus-5-5", "provider": "firstParty"}
            },
            "usage": {
                "input_tokens": 3,
                "output_tokens": 7,
                "output_tokens_details": {"thinking_tokens": 5},
                "service_tier": "HIDDEN_TIER",
                "iterations": [],
            },
            "total_cost_usd": 0.25,
            "session_id": "HIDDEN_SESSION",
            **changes,
        },
    ]
    return "\n".join(json.dumps(event) for event in events) + "\n"


@pytest.fixture
def request_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(isolated.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path / isolated.DIRECTORY


def test_opus_client_sends_the_prompt_on_stdin_and_keeps_only_the_registered_counters(
    monkeypatch, request_directory
):
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return runner.subprocess.CompletedProcess(command, 0, _stream(), "")

    monkeypatch.setattr(runner.subprocess, "run", run)
    reply = runner.OpusCliClient("HIDDEN_CLI", timeout_s=5).grade("the prompt")
    assert reply.text == _reply(1) and reply.model == "claude-opus-5-5"
    assert reply.usage == {"input_tokens": 3, "output_tokens": 7, "total_cost_usd": 0.25}
    assert reply.session["cli_version"] == "9.9.9" and reply.session["context_tokens"] == 3
    isolated.check_record(reply.session)
    assert "HIDDEN" not in json.dumps(reply.session)
    ((command, options),) = calls
    assert command == ["HIDDEN_CLI", *isolated.arguments(reference.SYSTEM_PROMPT)]
    assert options["input"] == "the prompt" and options["timeout"] == 5
    assert options["cwd"] == request_directory and not any(request_directory.iterdir())


@pytest.mark.parametrize(
    "stdout,code,reason",
    [
        ("not json", 0, "cli_response"),
        (json.dumps({"is_error": False, "result": _reply(1)}), 0, "cli_response"),
        (_stream(is_error=True), 0, "cli_response"),
        (_stream(terminal_reason="max_turns"), 0, "cli_response"),
        (_stream(stop_reason="max_tokens"), 0, "cli_response"),
        (_stream(num_turns=2), 0, "cli_response"),
        (_stream(result=" "), 0, "cli_response"),
        (_stream({"skills": ["HIDDEN_SKILL"]}), 0, "cli_response"),
        (_stream({"memory_paths": {"auto": "C:/HIDDEN/memory"}}), 0, "cli_response"),
        (_stream({"tools": ["Read"]}), 0, "cli_response"),
        (
            _stream(
                modelUsage={
                    "claude-sonnet-5": {
                        "canonicalModel": "claude-sonnet-5",
                        "provider": "firstParty",
                    }
                }
            ),
            0,
            "cli_response",
        ),
        (
            _stream(
                modelUsage={
                    "claude-opus-5-5": {
                        "canonicalModel": "claude-opus-5-5",
                        "provider": "firstParty",
                    },
                    "claude-haiku-4-5": {
                        "canonicalModel": "claude-haiku-4-5",
                        "provider": "firstParty",
                    },
                }
            ),
            0,
            "cli_response",
        ),
        (
            _stream(
                modelUsage={
                    "claude-opus-5-5": {"canonicalModel": "claude-opus-5-5", "provider": "bedrock"}
                }
            ),
            0,
            "cli_response",
        ),
        (_stream(), 3, "cli_exit"),
    ],
)
def test_opus_client_refuses_a_reply_it_cannot_attribute_to_the_judge(
    monkeypatch, request_directory, stdout, code, reason
):
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **options: runner.subprocess.CompletedProcess(command, code, stdout, ""),
    )
    with pytest.raises(JudgeUnavailable) as error:
        runner.OpusCliClient("HIDDEN_CLI").grade("the prompt")
    assert error.value.code == reason
    assert "HIDDEN" not in str(error.value)


def test_a_graded_reply_without_the_record_of_a_clean_session_is_not_read(finished_run, one_judge):
    class Bare(FakeJudge):
        def grade(self, prompt):
            reply = super().grade(prompt)
            return Reply(reply.text, reply.model, reply.usage, reply.elapsed_s)

    class Loaded(FakeJudge):
        def grade(self, prompt):
            reply = super().grade(prompt)
            loaded = {**SESSION["loaded"], "skills": ["one"]}
            return isolated.IsolatedReply(
                reply.text, reply.model, reply.usage, reply.elapsed_s, {**SESSION, "loaded": loaded}
            )

    _, planned, _ = _retest_run(finished_run, h=2, hm=0)
    for number, client in enumerate((Bare(), Loaded())):
        out = planned.with_name(f"judges-{number}")
        shutil.copytree(planned, out)
        runner.judge(out, "opus", client=client)
        assert all("session" in row for row in read_store(out / "opus.jsonl")) == bool(number)
        with pytest.raises(ValueError, match="graded reply the route does not vouch for"):
            runner.consensus(out)
        assert not (out / "ruler-input.json").exists()
        runner.judge(out, "opus", client=client, retest=True)
        with pytest.raises(ValueError, match="graded reply the route does not vouch for"):
            runner.retest(out, "opus")
        assert not (out / "opus-retest.json").exists()


def test_a_reply_the_judge_did_not_grade_needs_no_session_record(finished_run, one_judge):
    _, out, _ = _retest_run(finished_run, h=2, hm=0)

    class Down(FakeJudge):
        def grade(self, prompt):
            raise JudgeUnavailable("cli_response", "the session loaded more than the request")

    runner.judge(out, "opus", client=Down())
    assert [row["status"] for row in read_store(out / "opus.jsonl")] == ["absent"]
    assert runner.consensus(out)["status"] == "NOT_EVIDENCE"


def test_opus_client_reports_a_timeout_and_a_missing_cli(monkeypatch, request_directory):
    def timeout(command, **options):
        raise runner.subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    with pytest.raises(JudgeUnavailable) as error:
        runner.OpusCliClient("HIDDEN_CLI").grade("the prompt")
    assert error.value.code == "cli_timeout"
    monkeypatch.setattr(isolated.shutil, "which", lambda name: None)
    with pytest.raises(JudgeUnavailable) as error:
        runner.OpusCliClient().grade("the prompt")
    assert error.value.code == "cli_missing"


def test_an_unavailable_judge_ends_the_run_with_the_rest_pending(finished_run, one_judge):
    _, out, _ = _retest_run(finished_run, h=3, hm=0)

    class Down(FakeJudge):
        def grade(self, prompt):
            self.prompts.append(prompt)
            raise JudgeUnavailable("cli_exit", "Claude CLI exited with 1")

    client = Down()
    result = runner.judge(out, "opus", client=client)
    assert len(client.prompts) == 1
    assert result["absent"] == 1 and result["pending"] == 2 and result["unavailable"] == "cli_exit"
    assert runner.consensus(out)["status"] == "NOT_EVIDENCE"


def test_one_judge_grades_alone_and_the_summary_says_single_judge(finished_run, one_judge, capsys):
    _, out, plan = finished_run()
    runner.judge(out, "opus", client=TextJudge(_chunk_number))
    assert runner.main(["consensus", "--out", str(out)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ok"
    assert summary["grade_source"] == "single_judge"
    assert summary["included_judges"] == ["opus"] and summary["excluded_judges"] == {}
    assert summary["stores"] == {"opus": parity.file_sha(out / "opus.jsonl")}
    assert summary["units_by_grade_count"] == {"1": 3}
    payload = parity.read(out / "ruler-input.json")
    assert payload["grade_source"] == "single_judge"
    (case,) = payload["ruler"]["cases"]
    by_text = {
        doc["text_sha256"]: _chunk_number(doc["text"]) for doc in plan["requests"][0]["documents"]
    }
    assert case["grades"] == by_text


def test_one_judge_missing_more_than_five_percent_is_not_evidence(finished_run, one_judge):
    _, out, _ = _retest_run(finished_run, h=10, hm=0)
    replies = [_reply(1)] * 9 + ["invalid"]
    runner.judge(out, "opus", client=FakeJudge(*replies))
    summary = runner.consensus(out)
    assert summary["status"] == "NOT_EVIDENCE"
    assert summary["grade_source"] is None
    assert summary["excluded_judges"] == {"opus": 0.1}
    assert not (out / "ruler-input.json").exists()


def test_grade_source_names_a_consensus_only_when_two_voices_are_included(finished_run):
    _, out, _ = finished_run()
    assert runner.consensus(out)["grade_source"] is None
    runner.judge(out, "alpha", client=FakeJudge(grade=1))
    assert runner.consensus(out)["grade_source"] == "single_judge"
    runner.judge(out, "beta", client=FakeJudge(grade=3))
    assert runner.consensus(out)["grade_source"] == "consensus"


def test_retest_draw_takes_ten_cases_of_each_subset_by_the_registered_hash(finished_run):
    pairs = [(_case(f"h-{i:02d}"), _grade_row([_document(i)])) for i in range(12)]
    pairs += [(_case(f"m-{i}", "Hm"), _grade_row([_document(100 + i)])) for i in range(3)]
    pairs.append((_case("h-unaddressed"), _grade_row([_document(200, addressed=False)])))
    pairs.append((_case("h-excluded"), _grade_row([], status="excluded")))
    _, _, plan = finished_run(pairs)
    drawn = runner.retest_cases(plan)
    assert drawn == _retest_order([f"h-{i:02d}" for i in range(12)])[:10] + _retest_order(
        [f"m-{i}" for i in range(3)]
    )
    assert "h-unaddressed" not in drawn and "h-excluded" not in drawn
    assert runner.RETEST_RULE == (
        "per subset, the planned cases that have a request, sorted by the SHA-256 of "
        "'20260925:retest:<case_id>', the first 10; every request of a drawn case is sent "
        "again as <request id>~retest into a store of its own"
    )
    assert runner.RETEST_RULE in " ".join(runner.__doc__.replace('"', "").split())


def test_retest_draw_does_not_depend_on_the_order_of_the_plan(finished_run):
    _, _, plan = _retest_run(finished_run)
    shuffled = {**plan, "cases": list(reversed(plan["cases"]))}
    assert runner.retest_cases(shuffled) == runner.retest_cases(plan)


def test_retest_requests_rebuild_under_their_own_ids_and_blind_order(finished_run):
    docs = [_document(i) for i in range(23)]
    _, _, plan = finished_run([(_case("split"), _grade_row(docs[:5], docs))])
    requests = runner.retest_requests(plan)
    assert [request["case_id"] for request in requests] == [
        "split#1~retest",
        "split#2~retest",
        "split#3~retest",
    ]
    differing = 0
    for original, again in zip(plan["requests"], requests, strict=True):
        assert again["baseline_case_id"] == "split"
        assert (
            again["documents"] == original["documents"]
            and again["question"] == original["question"]
        )
        built = build_request_v2(
            case_id=again["case_id"],
            question=again["question"],
            documents=again["documents"],
            judge_version="plan",
        )
        assert again["request_sha256"] == built.request_sha256
        assert again["prompt_characters"] == len(built.text)
        ordered = sorted(again["documents"], key=lambda doc: doc["text_sha256"])
        random.Random(f"20260925:v2:{again['case_id']}").shuffle(ordered)
        assert [doc["text_sha256"] for doc in built.documents] == [
            doc["text_sha256"] for doc in ordered
        ]
        differing += again["request_sha256"] != original["request_sha256"]
    assert differing == 3


def test_retest_pass_has_its_own_store_and_reuses_no_reply(finished_run, one_judge):
    _, out, plan = _retest_run(finished_run)
    first = TextJudge(lambda block: _chunk_number(block) % 4)
    runner.judge(out, "opus", client=first)
    before = (out / "opus.jsonl").read_bytes()
    second = TextJudge(lambda block: _chunk_number(block) % 4)
    result = runner.judge(out, "opus", client=second, retest=True)
    assert result["retest"] is True
    assert result["valid"] == 13 and result["reused"] == 0 and result["pending"] == 0
    assert len(second.prompts) == 13 and len(first.prompts) == 15
    assert result["outbound"]["calls"] == 13 and result["outbound"]["texts"] == 13
    assert (out / "opus.jsonl").read_bytes() == before
    rows = read_store(out / "opus-retest.jsonl")
    assert sorted(row["case_id"] for row in rows) == sorted(
        case_id + "~retest" for case_id in runner.retest_cases(plan)
    )
    again = TextJudge(lambda block: 0)
    resumed = runner.judge(out, "opus", client=again, retest=True)
    assert resumed["reused"] == 13 and again.prompts == []


def test_retest_of_a_judge_that_repeats_itself_clears_the_rule(finished_run, one_judge, capsys):
    _, out, plan = _retest_run(finished_run)
    for retest in (False, True):
        runner.judge(
            out, "opus", client=TextJudge(lambda block: _chunk_number(block) % 4), retest=retest
        )
    assert runner.main(["retest", "--out", str(out), "--judge", "opus"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {
        "status": "ok",
        "verdict": "single_judge",
        "units": 13,
        "missing": {"first": 0, "second": 0},
        "quadratic_kappa": 1.0,
        "ci95": [1.0, 1.0],
    }
    report = parity.read(out / "opus-retest.json")
    assert report["judge"] == "opus" and report["rule"] == runner.RETEST_RULE
    assert report["judge_version"] == v2.judge_version("opus", FakeJudge())
    assert report["cases"] == runner.retest_cases(plan) and report["requests"] == 13
    assert report["threshold"] == 0.7 and report["missing_share_limit"] == 0.05
    assert report["bootstrap"] == {"seed": 20260925, "resamples": 10_000, "cluster": "case"}
    assert report["stores"] == {
        "first": parity.file_sha(out / "opus.jsonl"),
        "second": parity.file_sha(out / "opus-retest.jsonl"),
    }
    assert report["plan_sha256"] == parity.file_sha(out / "plan.json")
    assert report["all"]["cases"] == 13 and report["all"]["exact_agreement"] == 13
    assert report["all"]["relevance_flips"] == 0
    assert {subset: part["cases"] for subset, part in report["by_subset"].items()} == {
        "H": 10,
        "Hm": 3,
    }
    assert report["outbound"]["calls"] == 13


def test_retest_of_a_judge_that_contradicts_itself_leaves_the_ruler_provisional(
    finished_run, one_judge
):
    _, out, _ = _retest_run(finished_run)
    runner.judge(out, "opus", client=TextJudge(lambda block: _chunk_number(block) % 4))
    runner.judge(
        out, "opus", client=TextJudge(lambda block: 3 - _chunk_number(block) % 4), retest=True
    )
    report = runner.retest(out, "opus")
    assert report["status"] == "ok" and report["verdict"] == "provisional_ruler"
    assert report["all"]["quadratic_kappa"] < 0 and report["all"]["ci95"][0] < 0.7
    assert report["all"]["relevance_flips"] == 13 and report["all"]["exact_agreement"] == 0


@pytest.mark.parametrize("passes", [(), (False,), (True,)])
def test_retest_without_both_passes_is_not_evidence(finished_run, one_judge, capsys, passes):
    _, out, _ = _retest_run(finished_run)
    for retest in passes:
        runner.judge(out, "opus", client=FakeJudge(), retest=retest)
    assert runner.main(["retest", "--out", str(out), "--judge", "opus"]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "NOT_EVIDENCE" and printed["verdict"] == "NOT_EVIDENCE"
    assert printed["quadratic_kappa"] is None and printed["ci95"] is None
    assert printed["missing"] == {
        "first": 0 if False in passes else 13,
        "second": 0 if True in passes else 13,
    }


def test_retest_missing_more_than_five_percent_of_a_pass_is_not_evidence(finished_run, one_judge):
    _, out, _ = _retest_run(finished_run)
    runner.judge(out, "opus", client=TextJudge(lambda block: _chunk_number(block) % 4))
    replies = ["invalid"] + [_reply(1)] * 12
    runner.judge(out, "opus", client=FakeJudge(*replies), retest=True)
    report = runner.retest(out, "opus")
    assert report["missing"] == {"first": 0, "second": 1}
    assert report["status"] == "NOT_EVIDENCE" and report["all"]["units"] == 12


def test_retest_refuses_passes_of_two_judge_versions(finished_run, one_judge):
    _, out, _ = _retest_run(finished_run)
    runner.judge(out, "opus", client=FakeJudge())
    changed = FakeJudge()
    changed.parameters = {"model": "other-model", "temperature": 0}
    runner.judge(out, "opus", client=changed, retest=True)
    with pytest.raises(
        ValueError, match="the two passes were graded under different judge versions"
    ):
        runner.retest(out, "opus")
    assert not (out / "opus-retest.json").exists()


def test_retest_stability_matches_a_hand_loop():
    pairs = {
        "a": [(3, 3), (1, 2), (0, 0)],
        "b": [(2, 2), (2, 3)],
        "c": [(0, 1), (3, 3), (1, 1), (2, 0)],
        "empty": [],
    }
    result = retest_stability(pairs, samples=200, seed=7)
    flat = [pair for case_id in ("a", "b", "c") for pair in pairs[case_id]]
    assert result["cases"] == 3 and result["units"] == 9
    assert result["quadratic_kappa"] == quadratic_kappa([a for a, _ in flat], [b for _, b in flat])
    assert result["exact_agreement"] == 5 and result["relevance_flips"] == 2
    assert result["cross_table"]["2"] == {"0": 1, "1": 0, "2": 1, "3": 1}
    assert sum(sum(row.values()) for row in result["cross_table"].values()) == 9
    rng = random.Random(7)
    draws = []
    for _ in range(200):
        chosen = [("a", "b", "c")[rng.randrange(3)] for _ in range(3)]
        sample = [pair for case_id in chosen for pair in pairs[case_id]]
        value = quadratic_kappa([a for a, _ in sample], [b for _, b in sample])
        if value is not None:
            draws.append(value)
    draws.sort()

    def percentile(p):
        position = (len(draws) - 1) * p
        low, high = math.floor(position), math.ceil(position)
        return draws[low] + (draws[high] - draws[low]) * (position - low)

    assert result["ci95"] == [percentile(0.025), percentile(0.975)]
    assert result["resamples_used"] == len(draws)
    assert result["resamples_undefined"] == 200 - len(draws)


def test_retest_stability_without_pairs_has_no_kappa():
    result = retest_stability({"a": []})
    assert result["quadratic_kappa"] is None and result["ci95"] is None
    assert result["cases"] == 0 and result["units"] == 0 and result["resamples_used"] == 0


@pytest.mark.parametrize("pair", [(4, 0), (0, -1), (True, 1), (1.0, 1), (1,), (1, 2, 3)])
def test_retest_stability_refuses_anything_but_two_grades(pair):
    with pytest.raises(ValueError, match="grades must be integers 0-3"):
        retest_stability({"a": [pair]})


class DescribedJudge(FakeJudge):
    def describe(self):
        return {"cli_version": "9.9.9 (fixture)"}


def test_judge_logs_each_invocation_with_the_reported_cli_version(finished_run, one_judge):
    _, out, _ = _retest_run(finished_run, h=2, hm=0)
    runner.judge(out, "opus", client=DescribedJudge(), limit=1)
    runner.judge(out, "opus", client=DescribedJudge())
    runner.judge(out, "opus", client=FakeJudge(), retest=True)
    first, second, third = read_store(out / runner.RUN_LOG)
    assert (first["store"], first["valid"], first["pending"]) == ("opus.jsonl", 1, 1)
    assert (second["valid"], second["reused"], second["pending"]) == (1, 1, 0)
    assert first["environment"] == second["environment"] == {"cli_version": "9.9.9 (fixture)"}
    assert (third["store"], third["environment"]) == ("opus-retest.jsonl", {})
    for row in (first, second, third):
        assert row["judge"] == "opus"
        assert row["started"] <= row["finished"] and row["started"].endswith("+00:00")
        assert "outbound" not in row


@pytest.mark.parametrize(
    "stdout,code,expected",
    [
        ("2.1.289 (Claude Code)\n", 0, "2.1.289 (Claude Code)"),
        ("", 0, "N/A: Claude CLI did not report a version"),
        ("2.1.289 (Claude Code)\n", 1, "N/A: Claude CLI did not report a version"),
    ],
)
def test_opus_client_describes_the_cli_build_and_never_its_path(
    monkeypatch, stdout, code, expected
):
    calls = []

    def run(command, **options):
        calls.append(command)
        return runner.subprocess.CompletedProcess(command, code, stdout, "")

    monkeypatch.setattr(runner.subprocess, "run", run)
    described = runner.OpusCliClient("C:/HIDDEN/claude.cmd").describe()
    assert described == {"cli_version": expected}
    assert calls == [["C:/HIDDEN/claude.cmd", "--version"]]
    assert "HIDDEN" not in json.dumps(described)


def test_opus_client_describes_a_missing_or_silent_cli(monkeypatch):
    def timeout(command, **options):
        raise runner.subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    assert runner.OpusCliClient("HIDDEN_CLI").describe() == {
        "cli_version": "N/A: Claude CLI did not report a version"
    }
    monkeypatch.setattr(isolated.shutil, "which", lambda name: None)
    assert runner.OpusCliClient().describe() == {"cli_version": "N/A: Claude CLI is not installed"}
