from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import generator_benchmark as benchmark


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_load_benchmark_cases_uses_rerank_k_and_exact_dataset_identity(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "cases.jsonl"
    contexts = tmp_path / "contexts.json"
    _write_jsonl(
        dataset,
        [
            {
                "case_id": "case-1",
                "query": "Первый вопрос?",
                "expected": {"answer_contains": ["первый"]},
            },
            {
                "case_id": "case-2",
                "query": "Второй вопрос?",
                "expected": {"answer_contains": ["второй"]},
            },
        ],
    )
    contexts.write_text(
        json.dumps(
            [
                {
                    "case_id": "case-1",
                    "query": "Первый вопрос?",
                    "kws": ["первый"],
                    "rerank_k": 2,
                    "cands": ["doc-1", "doc-2", "doc-3"],
                },
                {
                    "case_id": "case-2",
                    "query": "Второй вопрос?",
                    "kws": ["второй"],
                    "rerank_k": 1,
                    "cands": ["doc-a", "doc-b"],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = benchmark.load_benchmark_cases(
        dataset_path=dataset,
        contexts_path=contexts,
        expected_cases=2,
    )

    assert [case["case_id"] for case in cases] == ["case-1", "case-2"]
    assert cases[0]["contexts"] == ["doc-1", "doc-2"]
    assert cases[1]["contexts"] == ["doc-a"]

    contexts_rows = json.loads(contexts.read_text(encoding="utf-8"))
    contexts_rows[1]["query"] = "Другой вопрос"
    contexts.write_text(json.dumps(contexts_rows, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(benchmark.BenchmarkInputError, match="query mismatch"):
        benchmark.load_benchmark_cases(
            dataset_path=dataset,
            contexts_path=contexts,
            expected_cases=2,
        )


def test_ollama_llm_sends_pinned_deterministic_generation_options() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None, float]] = []

    def request_json(
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        calls.append((method, url, payload, timeout))
        return {"response": "готово"}

    llm = benchmark.OllamaLLM(
        base_url="http://127.0.0.1:11434",
        model="qwen2.5:7b",
        seed=17,
        temperature=0.0,
        num_ctx=4096,
        num_predict=256,
        timeout_sec=90.0,
        keep_alive="15m",
        think=False,
        request_json=request_json,
    )

    assert llm.invoke("Вопрос") == "готово"
    llm.unload()

    generate_payload = calls[0][2]
    assert calls[0][:2] == (
        "POST",
        "http://127.0.0.1:11434/api/generate",
    )
    assert generate_payload == {
        "model": "qwen2.5:7b",
        "prompt": "Вопрос",
        "stream": False,
        "keep_alive": "15m",
        "think": False,
        "options": {
            "temperature": 0.0,
            "seed": 17,
            "num_ctx": 4096,
            "num_predict": 256,
        },
    }
    assert calls[1][2] == {"model": "qwen2.5:7b", "keep_alive": 0}


def test_no_think_is_recorded_in_benchmark_config_and_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "cases.jsonl"
    contexts = tmp_path / "contexts.json"
    dataset.write_text("", encoding="utf-8")
    contexts.write_text("[]", encoding="utf-8")
    captured: dict[str, Any] = {"llm_kwargs": []}

    class FakeOllamaLLM:
        calls = 0
        failed_calls = 0

        def __init__(self, **kwargs: Any) -> None:
            captured["llm_kwargs"].append(kwargs)

        def model_metadata(self) -> dict[str, Any]:
            return {"digest": "d" * 64}

        def process_metadata(self) -> dict[str, Any]:
            return {}

        def unload(self) -> None:
            return None

    def capture_report(**kwargs: Any) -> dict[str, Any]:
        captured["provenance"] = kwargs["provenance"]
        return {"evidence_class": "not_evidence", "aggregate": {}}

    monkeypatch.setattr(benchmark, "OllamaLLM", FakeOllamaLLM)
    monkeypatch.setattr(benchmark, "load_benchmark_cases", lambda **_kwargs: [])
    monkeypatch.setattr(
        benchmark,
        "_git_value",
        lambda *args: "a" * 40 if args == ("rev-parse", "HEAD") else "",
    )
    monkeypatch.setattr(benchmark, "build_final_report", capture_report)
    monkeypatch.setattr(benchmark, "_render_markdown", lambda _report: "report\n")

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
                "no-think-test",
                "--runs",
                "1",
                "--expected-cases",
                "1",
                "--skip-nli",
                "--no-think",
            ]
        )
        == 1
    )
    assert all(item["think"] is False for item in captured["llm_kwargs"])
    assert captured["provenance"]["ollama_think"] is False
    assert captured["provenance"]["config"]["think"] is False


def test_summarize_nli_claims_uses_best_supporting_context_per_claim() -> None:
    summary = benchmark.summarize_nli_claims(
        [
            {"claim": "Первый факт.", "entailment_scores": [0.2, 0.9]},
            {"claim": "Второй факт.", "entailment_scores": [0.6, 0.1]},
        ],
        support_threshold=0.5,
    )

    assert summary["n_claims"] == 2
    assert summary["n_supported_claims"] == 2
    assert summary["supported_claim_rate"] == pytest.approx(1.0)
    assert summary["nli_faithfulness"] == pytest.approx(0.75)


def test_parse_unit_interval_score_rejects_judge_prose_and_out_of_range() -> None:
    assert benchmark.parse_unit_interval_score(" 0.75\n") == pytest.approx(0.75)
    with pytest.raises(benchmark.BenchmarkInputError, match="strict unit-interval"):
        benchmark.parse_unit_interval_score("Score: 0.75")
    with pytest.raises(benchmark.BenchmarkInputError, match="strict unit-interval"):
        benchmark.parse_unit_interval_score("1.2")


def test_build_final_report_fails_closed_until_three_complete_runs() -> None:
    provenance = {
        "code_sha": "a" * 40,
        "dataset_sha256": "b" * 64,
        "contexts_sha256": "c" * 64,
        "ollama_model_digest": "d" * 64,
        "nli_model": benchmark.DEFAULT_NLI_MODEL,
        "nli_revision": benchmark.DEFAULT_NLI_REVISION,
    }

    def run(index: int, nli: float) -> dict[str, Any]:
        return {
            "run_index": index,
            "num_cases": 2,
            "failed_cases": 0,
            "case_ids": ["case-1", "case-2"],
            "aggregate": {
                "llm_faithfulness": 0.8,
                "answer_relevancy": 0.9,
                "context_precision": 0.6,
                "context_recall": 0.95,
                "nli_faithfulness": nli,
                "nli_supported_claim_rate": 0.75,
                "mean_latency_ms": 1000.0,
            },
            "cases": [],
        }

    incomplete = benchmark.build_final_report(
        runs=[run(1, 0.7)],
        provenance=provenance,
        expected_cases=2,
        required_runs=3,
    )
    assert incomplete["evidence_class"] == "not_evidence"
    assert "run_count=1 < required_runs=3" in incomplete["evidence_reasons"]

    complete = benchmark.build_final_report(
        runs=[run(1, 0.7), run(2, 0.8), run(3, 0.9)],
        provenance=provenance,
        expected_cases=2,
        required_runs=3,
    )
    assert complete["evidence_class"] == "measured"
    assert complete["aggregate"]["nli_faithfulness"]["mean"] == pytest.approx(0.8)
    assert complete["aggregate"]["nli_faithfulness"]["n"] == 3
    assert complete["aggregate"]["nli_faithfulness"]["ci_method"] == "student-t-95"


def test_ollama_llm_keeps_the_timing_of_its_last_generation() -> None:
    timing = {
        "total_duration": 9_000_000_000,
        "load_duration": 1_000_000_000,
        "prompt_eval_count": 2300,
        "prompt_eval_duration": 6_000_000_000,
        "eval_count": 120,
        "eval_duration": 2_000_000_000,
    }

    def request_json(
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        return {"response": "ответ", "model": "qwen3:4b", "done": True, **timing}

    llm = benchmark.OllamaLLM(
        base_url="http://127.0.0.1:11434",
        model="qwen3:4b",
        seed=42,
        temperature=0.0,
        num_ctx=4096,
        num_predict=384,
        timeout_sec=60.0,
        keep_alive="5m",
        request_json=request_json,
    )

    assert llm.last_timing == {}
    assert llm.invoke("Вопрос") == "ответ"
    assert llm.last_timing == timing


def test_no_llm_judge_measures_one_run_without_the_generator_judging_itself(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "cases.jsonl"
    contexts = tmp_path / "contexts.json"
    dataset.write_text("{}\n", encoding="utf-8")
    contexts.write_text("[]", encoding="utf-8")
    cases = [
        {
            "case_id": f"case-{index}",
            "query": f"Вопрос {index}?",
            "contexts": [f"Контекст {index}."],
            "expected_keywords": ["контекст"],
        }
        for index in (1, 2)
    ]
    timing = {
        "prompt_eval_count": 40,
        "prompt_eval_duration": 2_000_000_000,
        "eval_count": 8,
        "eval_duration": 1_000_000_000,
    }
    prompts: list[str] = []

    class FakeOllamaLLM:
        calls = 0
        failed_calls = 0

        def __init__(self, **kwargs: Any) -> None:
            self.last_timing: dict[str, Any] = {}

        def invoke(self, prompt: str) -> str:
            prompts.append(prompt)
            self.last_timing = dict(timing)
            return "Ответ по контексту."

        def model_metadata(self) -> dict[str, Any]:
            return {"digest": "d" * 64}

        def process_metadata(self) -> dict[str, Any]:
            return {}

        def unload(self) -> None:
            return None

    class FakeScorer:
        def __init__(self, **kwargs: Any) -> None:
            return None

        def score(self, answer: str, contexts: list[str]) -> dict[str, Any]:
            return {"nli_faithfulness": 0.9, "supported_claim_rate": 1.0, "claims": []}

    monkeypatch.setattr(benchmark, "OllamaLLM", FakeOllamaLLM)
    monkeypatch.setattr(benchmark, "MultilingualNLIScorer", FakeScorer)
    monkeypatch.setattr(benchmark, "load_benchmark_cases", lambda **_kwargs: cases)
    monkeypatch.setattr(
        benchmark,
        "_git_value",
        lambda *args: "a" * 40 if args == ("rev-parse", "HEAD") else "",
    )

    code = benchmark.main(
        [
            "--dataset",
            str(dataset),
            "--contexts",
            str(contexts),
            "--results-dir",
            str(tmp_path),
            "--run-id",
            "screen",
            "--runs",
            "1",
            "--required-runs",
            "1",
            "--expected-cases",
            "2",
            "--no-llm-judge",
        ]
    )

    report = json.loads(
        (tmp_path / "screen-phase-c-generator-benchmark.json").read_text(encoding="utf-8")
    )
    assert (code, report["evidence_class"]) == (0, "measured"), report["evidence_reasons"]
    # One generation per case and no judging prompt: the generator never grades itself.
    assert len(prompts) == 2
    assert report["required_runs"] == 1
    assert report["provenance"]["config"]["llm_judge"] is False
    assert report["provenance"]["config"]["required_runs"] == 1
    (run,) = report["runs"]
    assert run["answer_metrics_evidence"] == "not_requested"
    assert all(row["ollama_timing"] == timing and row["error"] == "" for row in run["cases"])
    assert report["aggregate"]["llm_faithfulness"]["mean"] is None
    assert report["aggregate"]["answer_relevancy"]["mean"] is None
    assert report["aggregate"]["nli_faithfulness"]["mean"] == pytest.approx(0.9)


def test_build_final_report_without_llm_judge_still_requires_every_other_metric() -> None:
    provenance = {
        "code_sha": "a" * 40,
        "dataset_sha256": "b" * 64,
        "contexts_sha256": "c" * 64,
        "ollama_model_digest": "d" * 64,
        "nli_model": benchmark.DEFAULT_NLI_MODEL,
        "nli_revision": benchmark.DEFAULT_NLI_REVISION,
    }
    run = {
        "run_index": 1,
        "num_cases": 2,
        "failed_cases": 0,
        "case_ids": ["case-1", "case-2"],
        "answer_metrics_evidence": "not_requested",
        "aggregate": {
            "llm_faithfulness": None,
            "answer_relevancy": None,
            "context_precision": 0.6,
            "context_recall": 0.95,
            "nli_faithfulness": 0.9,
            "nli_supported_claim_rate": 0.75,
            "mean_latency_ms": 1000.0,
        },
        "cases": [],
    }

    def build(*, llm_judge: bool) -> dict[str, Any]:
        return benchmark.build_final_report(
            runs=[run],
            provenance=provenance,
            expected_cases=2,
            required_runs=1,
            llm_judge=llm_judge,
        )

    assert build(llm_judge=False)["evidence_class"] == "measured"
    judged = build(llm_judge=True)
    assert judged["evidence_class"] == "not_evidence"
    assert "run 1 missing finite metric: llm_faithfulness" in judged["evidence_reasons"]
    run["aggregate"]["nli_faithfulness"] = None
    unjudged = build(llm_judge=False)
    assert unjudged["evidence_class"] == "not_evidence"
    assert "run 1 missing finite metric: nli_faithfulness" in unjudged["evidence_reasons"]


def test_build_final_report_rejects_missing_model_provenance() -> None:
    report = benchmark.build_final_report(
        runs=[],
        provenance={"code_sha": "a" * 40},
        expected_cases=100,
        required_runs=3,
    )

    assert report["evidence_class"] == "not_evidence"
    assert "missing provenance: dataset_sha256" in report["evidence_reasons"]
