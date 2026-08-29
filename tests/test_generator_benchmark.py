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
        "options": {
            "temperature": 0.0,
            "seed": 17,
            "num_ctx": 4096,
            "num_predict": 256,
        },
    }
    assert calls[1][2] == {"model": "qwen2.5:7b", "keep_alive": 0}


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


def test_build_final_report_rejects_missing_model_provenance() -> None:
    report = benchmark.build_final_report(
        runs=[],
        provenance={"code_sha": "a" * 40},
        expected_cases=100,
        required_runs=3,
    )

    assert report["evidence_class"] == "not_evidence"
    assert "missing provenance: dataset_sha256" in report["evidence_reasons"]
