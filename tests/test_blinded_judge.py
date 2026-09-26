"""P2's blinded, offline grading contract; all judge calls are fakes."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest

from evaluation import blinded_judge as p2
from evaluation import blinded_judge_clients as clients
from evaluation.blinded_judge_clients import JudgeUnavailable, RateLimited, Reply, TransportError


def _case(case_id: str = "case-1", *, pool: str = "H") -> p2.Case:
    return p2.Case(
        pool=pool,
        case_id=case_id,
        question="Which policy applies?",
        documents=tuple(f"Header {j}\nPolicy document {j}" for j in range(5)),
        keywords=("SENTINEL_NEVER_SHOWN",),
    )


def _reply(grades: tuple[int, ...] = (0, 1, 2, 3, 2), *, key: str = "") -> Reply:
    text = json.dumps(
        {
            "grades": [
                {"doc": f"D{j + 1}", "grade": grade, "reason": "ok"}
                for j, grade in enumerate(grades)
            ]
        }
    )
    return Reply(text=text, model="fake-model", usage={"output_tokens": 4}, elapsed_s=0.25)


class FakeJudge:
    def __init__(self, outcomes: list[Reply | Exception] | None = None) -> None:
        self.outcomes = list(outcomes or [])
        self.requests: list[str] = []

    def grade(self, request_text: str) -> Reply:
        self.requests.append(request_text)
        result = self.outcomes.pop(0) if self.outcomes else _reply()
        if isinstance(result, Exception):
            raise result
        return result


def test_request_is_blind_deterministic_and_identical_for_every_judge(tmp_path: Path) -> None:
    case = _case()
    first = p2.build_request(case)
    assert first == p2.build_request(case)
    order = list(range(5))
    random.Random(f"20260925:{case.case_id}").shuffle(order)
    assert first.order == tuple(order)
    assert [case.documents[index] for index in order] == [
        first.text.split(f"D{position + 1}\n", 1)[1].split("\n\nD", 1)[0] for position in range(5)
    ]
    assert first.sha256 == hashlib.sha256(first.text.encode("utf-8")).hexdigest()
    assert "SENTINEL_NEVER_SHOWN" not in first.text
    for forbidden in ("rank", "score", "arm", "source path", "case-1"):
        assert forbidden not in first.text.lower()
    first_judge = FakeJudge()
    second_judge = FakeJudge()
    p2.run_judge("sonnet", first_judge, [case], tmp_path / "sonnet.jsonl")
    p2.run_judge("glm", second_judge, [case], tmp_path / "glm.jsonl")
    assert first_judge.requests == second_judge.requests == [first.text]


@pytest.mark.parametrize(
    "grades",
    [
        [{"doc": "D1", "grade": 0}],
        [{"doc": "D1", "grade": 0}, {"doc": "D1", "grade": 1}],
        [{"doc": "D1", "grade": 0}, {"doc": "D2", "grade": 1}, {"doc": "D6", "grade": 2}],
        [{"doc": "D1", "grade": 4}, {"doc": "D2", "grade": 1}],
        [{"doc": "D1", "grade": 1.0}, {"doc": "D2", "grade": 1}],
        [{"doc": "D1", "grade": True}, {"doc": "D2", "grade": 1}],
        [{"doc": "D1", "grade": "1"}, {"doc": "D2", "grade": 1}],
    ],
)
def test_parser_rejects_missing_repeated_extra_or_noninteger_grades(grades: list[dict]) -> None:
    with pytest.raises(p2.ParseFailure):
        p2.parse_grades(json.dumps({"grades": grades}), ("D1", "D2"))


def test_parser_takes_first_balanced_object_inside_prose_or_fence() -> None:
    body = '{"grades":[{"doc":"D1","grade":3},{"doc":"D2","grade":1}]}'
    assert p2.parse_grades(f"Here:\n```json\n{body}\n```", ("D1", "D2")) == {"D1": 3, "D2": 1}
    with pytest.raises(p2.ParseFailure):
        p2.parse_grades('{"grades":[]}\n' + body, ("D1", "D2"))


def test_parse_failure_retries_twice_then_records_missing(tmp_path: Path) -> None:
    judge = FakeJudge([_reply((4, 0, 0, 0, 0))] * 3)
    result = p2.run_judge("glm", judge, [_case()], tmp_path / "glm.jsonl", sleep=lambda _: None)
    assert len(judge.requests) == 3
    assert result["missing"] == 1
    assert result["graded"] == 0
    assert [row["status"] for row in p2.read_store(tmp_path / "glm.jsonl")] == [
        "parse_failure",
        "parse_failure",
        "missing",
    ]


def test_rate_reset_and_transport_backoff_use_injected_clock(tmp_path: Path) -> None:
    now = [100.0]
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    judge = FakeJudge([RateLimited(105.0), TransportError(), _reply()])
    result = p2.run_judge(
        "glm", judge, [_case()], tmp_path / "glm.jsonl", clock=lambda: now[0], sleep=sleep
    )
    assert result["graded"] == 1
    assert waits[0] == 5.0
    assert waits[1] > 0
    assert len(judge.requests) == 3


def test_unavailable_is_preserved_and_control_prevents_any_call(tmp_path: Path) -> None:
    judge = FakeJudge([JudgeUnavailable("zero_limit", "No requests allowed")])
    store = tmp_path / "mistral.jsonl"
    with pytest.raises(p2.InvalidControl, match="INVALID_CONTROL"):
        p2.run_judge("mistral", judge, [_case()], store, control_precision=0.4)
    assert judge.requests == []
    assert not store.exists()
    result = p2.run_judge("mistral", judge, [_case()], store)
    assert result["status"] == "unavailable"
    assert result["code"] == "zero_limit"
    assert result["message"] == "No requests allowed"
    assert p2.read_store(store)[0]["status"] == "unavailable"


def test_resume_changed_request_and_merge_two_stores(tmp_path: Path) -> None:
    cases = [_case(f"case-{j}") for j in range(115)]
    first_path = tmp_path / "machine-a.jsonl"
    first = FakeJudge()
    p2.run_judge("sonnet", first, cases, first_path, limit=40)
    assert len(first.requests) == 40
    second = FakeJudge()
    p2.run_judge("sonnet", second, cases, first_path)
    assert len(second.requests) == 75
    changed = list(cases)
    changed[0] = p2.Case("H", "case-0", "A changed question", cases[0].documents, ())
    third = FakeJudge()
    p2.run_judge("sonnet", third, changed, first_path)
    assert len(third.requests) == 1
    other_path = tmp_path / "machine-b.jsonl"
    p2.run_judge("glm", FakeJudge(), cases[:2], other_path)
    merged = p2.merge_stores([first_path, other_path])
    assert set(merged) == {"sonnet", "glm"}
    assert len(merged["sonnet"]) == 115
    assert len(merged["glm"]) == 2
    assert "FAKE_SECRET_KEY_12345678901234567890" not in first_path.read_text(encoding="utf-8")


def test_resume_reuses_matching_reply_after_an_obsolete_request(tmp_path: Path) -> None:
    original = _case()
    changed = p2.Case("H", original.case_id, "A different question", original.documents, ())
    path = tmp_path / "sonnet.jsonl"
    p2.run_judge("sonnet", FakeJudge(), [original], path)
    p2.run_judge("sonnet", FakeJudge(), [changed], path)

    resumed = FakeJudge()
    result = p2.run_judge("sonnet", resumed, [original], path)
    assert result["reused"] == 1
    assert resumed.requests == []


def test_lower_median_and_missing_threshold_are_pool_specific() -> None:
    assert p2.lower_median([3, 1]) == 1
    assert p2.lower_median([3, 2, 0]) == 2
    ids = [f"c{j}" for j in range(100)]
    grades = {
        "a": {case_id: (3,) * 5 for case_id in ids},
        "b": {case_id: (1,) * 5 for case_id in ids[:94]},
    }
    consensus, excluded = p2.consensus_grades(ids, grades)
    assert excluded == ["b"]
    assert consensus["c0"] == (3,) * 5
    grades["b"]["c94"] = (1,) * 5
    consensus, excluded = p2.consensus_grades(ids, grades)
    assert excluded == []
    assert consensus["c0"] == (1,) * 5


def test_hand_built_metrics_and_ruler_equivalence() -> None:
    grades = {"a": (3, 2, 0, 0, 0), "b": (0, 2, 0, 0, 0)}
    metrics = p2.arm_metrics(grades, {"a": 2, "b": 2})
    assert metrics["judged_precision"] == pytest.approx(0.75)
    assert metrics["ruler_shaped_judged_precision"] == pytest.approx((8 / 9 + 2 / 9) / 2)
    assert metrics["answerability"] == {"FULL": 1, "PART": 1, "MISS": 0}
    from evaluation.ragas_eval import context_precision

    assert metrics["ruler_shaped_judged_precision"] == pytest.approx(
        (
            context_precision("alpha beta gamma", ["alpha beta gamma", "alpha beta"])
            + context_precision("alpha beta gamma", ["none", "alpha beta"])
        )
        / 2
    )


def test_statistics_match_hand_calculation_and_bootstrap_is_seeded() -> None:
    assert p2.kendall_tau_b([1, 1, 2, 3], [1, 2, 2, 3]) == pytest.approx(0.8)
    assert p2.quadratic_kappa([0, 0, 2, 2], [0, 1, 2, 2]) == pytest.approx(6 / 7)
    # Four units, two raters. Ordinal distances: d01=d12=6.25, d02=25.
    assert p2.krippendorff_alpha_ordinal([[0, 0], [0, 1], [1, 2], [2, 2]]) == pytest.approx(17 / 24)
    values = [0.0, 0.0, 1.0, 1.0]
    assert p2.bootstrap_mean_ci(values, samples=10_000) == p2.bootstrap_mean_ci(
        values, samples=10_000
    )
    assert p2.bootstrap_mean_ci(values, samples=10_000) == (0.0, 1.0)


@pytest.mark.parametrize(
    ("alpha", "human_kappa", "ci", "judges", "expected"),
    [
        (0.666, None, (0.5, 0.7), 2, "JUDGE_UNRELIABLE"),
        (0.8, 0.59, (0.5, 0.7), 2, "JUDGE_UNRELIABLE"),
        (0.8, 0.7, (0.4, 0.7), 2, "RULER_TRACKS"),
        (0.8, 0.7, (-0.1, 0.399), 2, "RULER_DOES_NOT_TRACK"),
        (0.8, 0.7, (0.39, 0.6), 2, "INCONCLUSIVE"),
        (None, None, (0.4, 0.7), 1, "PROVISIONAL_RULER_TRACKS"),
        (None, None, None, 0, "JUDGE_UNRELIABLE"),
    ],
)
def test_verdict_branches(alpha, human_kappa, ci, judges, expected) -> None:
    assert p2.verdict(ci, judge_count=judges, alpha=alpha, human_kappa=human_kappa) == expected


def test_human_sample_page_and_import_are_blind_and_exact(tmp_path: Path) -> None:
    cases = [_case(f"case-{j}") for j in range(100)]
    ruler = {case.case_id: j / 100 for j, case in enumerate(cases)}
    sample = p2.draw_human_sample(cases, ruler)
    assert sample == p2.draw_human_sample(cases, ruler)
    assert len(sample) == 10
    assert all(
        len({case.case_id for case in sample if int(case.case_id[5:]) // 20 == group}) == 2
        for group in range(5)
    )
    page = tmp_path / "sample.html"
    p2.write_human_page(sample, page)
    html = page.read_text(encoding="utf-8")
    assert "<script src=" not in html
    assert "http:" not in html and "https:" not in html
    assert "SENTINEL_NEVER_SHOWN" not in html
    assert "rank" not in html.lower() and "score" not in html.lower()
    grades_path = tmp_path / "grades.json"
    grades = [
        {"case_id": case.case_id, "doc": f"D{j}", "grade": (j - 1) % 4}
        for case in sample
        for j in range(1, 6)
    ]
    grades_path.write_text(json.dumps({"grades": grades}), encoding="utf-8")
    imported = p2.import_human_grades(grades_path, sample, "Julia", "2026-09-26")
    assert len(imported["grades"]) == 50
    assert imported["grader"] == "Julia" and imported["date"] == "2026-09-26"
    grades.pop()
    grades_path.write_text(json.dumps({"grades": grades}), encoding="utf-8")
    with pytest.raises(ValueError):
        p2.import_human_grades(grades_path, sample, "Julia", "2026-09-26")
    grades.append({"case_id": sample[-1].case_id, "doc": "D5", "grade": True})
    grades_path.write_text(json.dumps({"grades": grades}), encoding="utf-8")
    with pytest.raises(ValueError):
        p2.import_human_grades(grades_path, sample, "Julia", "2026-09-26")


def test_real_inputs_control_counts_and_arm_alignment() -> None:
    inputs = p2.load_inputs()
    assert inputs.control_precision == 0.5067
    assert [
        (name, len(pool.cases), pool.shortened_units) for name, pool in inputs.pools.items()
    ] == [("H", 100, 0), ("Hm", 15, 0)]
    assert all(len(case.documents) == 5 for pool in inputs.pools.values() for case in pool.cases)
    assert len(inputs.arms["H"]) == 39
    assert len(inputs.arms["Hm"]) == 37
    assert all(
        len(counts) == len(inputs.pools["H"].cases) and set(counts.values()) <= set(range(1, 6))
        for counts in inputs.arms["H"].values()
    )


def test_h_label_manifest_must_match_applied_approvals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest_name = "evaluation/curated_cases_aircargo.manifest.json"
    manifest = json.loads((p2.PROJECT_ROOT / manifest_name).read_text(encoding="utf-8"))
    manifest["summary"]["real_labelled_count"] = 0
    altered_manifest = tmp_path / "altered-manifest.json"
    altered_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    original_path = p2._path_from_report

    def path_with_altered_manifest(root: Path, name: object) -> Path:
        if name == manifest_name:
            return altered_manifest
        return original_path(root, name)

    monkeypatch.setattr(p2, "_path_from_report", path_with_altered_manifest)
    with pytest.raises(ValueError, match="H label manifest.*summary"):
        p2.load_inputs()


def test_recomputed_real_control_drift_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    score_selection = p2.p1.score_selection

    def changed_control(*args, **kwargs):
        rows, approved = score_selection(*args, **kwargs)
        rows[0]["context_precision"] = 0.0
        return rows, approved

    monkeypatch.setattr(p2.p1, "score_selection", changed_control)
    judge = FakeJudge()
    with pytest.raises(p2.InvalidControl, match="INVALID_CONTROL"):
        p2.load_inputs()
    assert judge.requests == []


def test_pairwise_reliability_uses_units_all_judges_graded() -> None:
    grades = {
        "a": {"c1": (0,) * 5, "c2": (3,) * 5},
        "b": {"c1": (0,) * 5, "c2": (2,) * 5},
        "c": {"c1": (1,) * 5},
    }
    pairwise = p2._pairwise_kappas(grades)
    assert {row["shared_units"] for row in pairwise.values()} == {5}


def test_unavailable_judge_is_unavailable_for_both_pools(tmp_path: Path) -> None:
    inputs = p2.load_inputs()
    case = inputs.pools["H"].cases[0]
    store = tmp_path / "mistral.jsonl"
    p2.run_judge(
        "mistral", FakeJudge([JudgeUnavailable("zero_limit", "No requests")]), [case], store
    )
    _grades, info = p2._current_grades(inputs, p2.merge_stores([store]))
    assert info["mistral"]["pools"]["H"]["unavailable_units"] == 500
    assert info["mistral"]["pools"]["Hm"]["unavailable_units"] == 75


def test_report_without_grades_writes_nothing(tmp_path: Path) -> None:
    inputs = p2.load_inputs()
    with pytest.raises(p2.NotEvidence, match="NOT_EVIDENCE"):
        p2.build_report(inputs, [], out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_sonnet_route_payload_and_failure_code(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, dict, dict]] = []

    def fake_post(url: str, payload: dict, headers: dict) -> dict:
        sent.append((url, payload, headers))
        return {
            "output_text": _reply().text,
            "model": {"id": "claude-sonnet-5"},
            "usage": {"output_tokens": 17},
        }

    monkeypatch.setattr(clients, "_post_json", fake_post)
    reply = clients.SonnetClient().grade("the same blind request")
    assert reply.model == "claude-sonnet-5"
    assert sent[0] == (
        "http://127.0.0.1:8011/api/v1/orchestrate",
        {
            "prompt": "the same blind request",
            "model": "claude-sonnet-5",
            "adapter_hint": "browser",
            "reasoning": True,
            "decompose": False,
        },
        {},
    )
    monkeypatch.setattr(clients, "_post_json", lambda *_: {"failure_code": "model_auth_required"})
    with pytest.raises(JudgeUnavailable) as error:
        clients.SonnetClient().grade("blind")
    assert error.value.code == "model_auth_required"


def test_mistral_route_reads_first_key_at_call_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key_file = tmp_path / "keys.txt"
    key_file.write_text("A" * 32 + "\n" + "B" * 32, encoding="utf-8")
    seen: list[tuple[str, dict, dict]] = []

    def fake_post(url: str, payload: dict, headers: dict) -> dict:
        seen.append((url, payload, headers))
        return {
            "model": "mistral-medium-2604",
            "choices": [{"message": {"content": _reply().text}}],
            "usage": {},
        }

    monkeypatch.setattr(clients, "_post_json", fake_post)
    client = clients.MistralClient(key_file)
    assert client.grade("blind").model == "mistral-medium-2604"
    assert seen[0][0] == "https://api.mistral.ai/v1/chat/completions"
    assert seen[0][1] == {
        "model": "mistral-medium-2604",
        "temperature": 0,
        "random_seed": 20260925,
        "response_format": {"type": "json_object"},
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": "blind"}],
    }
    assert seen[0][2]["Authorization"] == "Bearer " + "A" * 32
    key_file.write_text("B" * 32, encoding="utf-8")
    client.grade("blind")
    assert seen[1][2]["Authorization"] == "Bearer " + "B" * 32


def test_glm_route_sse_model_check_and_token_read_at_call_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
                    "ANTHROPIC_AUTH_TOKEN": "FAKE_SECRET_TOKEN",
                }
            }
        ),
        encoding="utf-8",
    )
    seen: list[object] = []
    model = ["glm-5.3"]

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def __iter__(self):
            for event in (
                {"type": "message_start", "message": {"model": model[0], "usage": {}}},
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": _reply().text},
                },
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
                {"type": "message_stop"},
            ):
                yield ("data: " + json.dumps(event) + "\n").encode("utf-8")

    def fake_open(request):
        seen.append(request)
        return FakeStream()

    monkeypatch.setattr(clients, "_open", fake_open)
    reply = clients.GlmClient(settings).grade("blind")
    assert reply.model == "glm-5.3"
    request = seen[0]
    assert request.full_url == "https://api.z.ai/api/anthropic/v1/messages"
    assert request.get_header("X-api-key") == "FAKE_SECRET_TOKEN"
    assert json.loads(request.data) == {
        "model": "glm-5.3",
        "max_tokens": 48000,
        "thinking": {"type": "enabled", "budget_tokens": 8000},
        "output_config": {"effort": "xhigh"},
        "stream": True,
        "messages": [{"role": "user", "content": "blind"}],
    }
    model[0] = "other-model"
    with pytest.raises(JudgeUnavailable) as error:
        clients.GlmClient(settings).grade("blind")
    assert error.value.code == "model_mismatch"


def test_http_unavailable_rate_reset_and_secret_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    for status in (401, 403):
        with pytest.raises(JudgeUnavailable) as error:
            clients._error(status, {}, b'{"error":{"message":"FAKE_SECRET_KEY"}}')
        assert "FAKE_SECRET_KEY" not in str(error.value)
    with pytest.raises(JudgeUnavailable) as error:
        clients._error(429, {"x-ratelimit-limit-req-minute": "0"}, b"")
    assert error.value.code == "zero_limit"
    with pytest.raises(JudgeUnavailable) as error:
        clients._error(429, {}, b'{"error":{"code":"1310"}}')
    assert error.value.code == "1310"
    monkeypatch.setattr(clients.time, "time", lambda: 100.0)
    with pytest.raises(RateLimited) as error:
        clients._error(429, {"retry-after": "5"}, b"")
    assert error.value.reset_at == 105.0


def test_http_rate_limit_code_still_waits_for_named_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clients.time, "time", lambda: 100.0)
    with pytest.raises(RateLimited) as error:
        clients._error(
            429,
            {"retry-after": "5"},
            b'{"error":{"code":"rate_limit_exceeded"}}',
        )
    assert error.value.reset_at == 105.0


def test_fake_stores_merge_into_pinned_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inputs = p2.load_inputs()
    cases = [case for pool in inputs.pools.values() for case in pool.cases]
    stores = [tmp_path / "sonnet.jsonl", tmp_path / "glm.jsonl"]
    for judge, path in zip(("sonnet", "glm"), stores, strict=True):
        assert p2.run_judge(judge, FakeJudge(), cases, path)["graded"] == 115
    mean_ci = p2.bootstrap_mean_ci
    tau_ci = p2.bootstrap_tau_ci
    monkeypatch.setattr(p2, "bootstrap_mean_ci", lambda values: mean_ci(values, samples=20))
    monkeypatch.setattr(p2, "bootstrap_tau_ci", lambda x, y: tau_ci(x, y, samples=20))
    path, report = p2.build_report(inputs, stores, out_dir=tmp_path)
    assert path.name == "p2-blinded-judge-glm+sonnet.json"
    assert report["control"] == {"H_top_k_5": 0.5067, "valid": True}
    assert report["provenance"]["instruction_sha256"] == p2.INSTRUCTION_SHA256
    assert report["provenance"]["pools"]["H"]["pool_sha256"] == p2.p1.H_POOL_SHA256
    h_labels = report["provenance"]["H_labels"]
    manifest = json.loads(
        (p2.PROJECT_ROOT / "evaluation/curated_cases_aircargo.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert h_labels["summary"] == manifest["summary"]
    assert len(h_labels["cases"]) == 100
    assert {row["case_id"] for row in h_labels["cases"]} == {
        case.case_id for case in inputs.pools["H"].cases
    }
    first_label = h_labels["cases"][0]["label"]
    assert h_labels["cases"][0]["case_id"] == "aircargo-probation-data"
    assert first_label["journey"] == "out_of_scope"
    assert first_label["approved_by"] == "julia"
    assert first_label["evidence_class"] == "real_labelled"
    assert len(report["provenance"]["judge_routes"]["glm"]["reply_files"]) == 1
    assert report["metrics"]["H"]["consensus"]["arms"]["top_k_5"]["metrics"]["graded_cases"] == 100
    assert report["metrics"]["Hm"]["consensus"]["arms"]["top_k_5"]["metrics"]["graded_cases"] == 15
    assert report["verdict"]["judge_count"] == 2
