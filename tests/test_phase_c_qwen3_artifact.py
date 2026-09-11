from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import generator_benchmark as benchmark

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    PROJECT_ROOT
    / "evaluation"
    / "c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json"
)
ARTIFACT_SHA256 = "1663ea598b769af2aee6464c5da90a001b9187f83114217f03f6552856a70f5f"


def test_qwen3_benchmark_is_complete_measured_evidence() -> None:
    raw = ARTIFACT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ARTIFACT_SHA256
    assert (
        ARTIFACT.with_suffix(ARTIFACT.suffix + ".sha256").read_text(encoding="utf-8")
        == f"{ARTIFACT_SHA256}  {ARTIFACT.name}\n"
    )

    report: dict[str, Any] = json.loads(raw)
    assert report["kind"] == "phase-c-generator-benchmark"
    assert report["evidence_class"] == "measured"
    assert report["evidence_reasons"] == []
    assert report["required_runs"] == 3
    assert report["expected_cases"] == 100

    provenance = report["provenance"]
    assert provenance["code_sha"] == "b8ecc8efb780d423a267595584ef0927ebb77cc5"
    assert provenance["code_tree_clean"] is True
    assert (
        provenance["dataset_sha256"]
        == "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
    )
    assert (
        provenance["contexts_sha256"]
        == "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10"
    )
    assert provenance["ollama_model"] == "qwen3:8b"
    assert (
        provenance["ollama_model_digest"]
        == "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
    )
    assert provenance["ollama_think"] is False
    assert provenance["nli_model"] == benchmark.DEFAULT_NLI_MODEL
    assert provenance["nli_revision"] == benchmark.DEFAULT_NLI_REVISION
    assert provenance["config"] == {
        "prompt_version": "aircargo-context-only-ru-v1",
        "runs": 3,
        "expected_cases": 100,
        "selected_cases": 100,
        "top_k_override": None,
        "context_chars": 6000,
        "seed_base": 42,
        "temperature": 0.0,
        "num_ctx": 4096,
        "num_predict": 384,
        "think": False,
        "nli_batch_size": 4,
        "nli_support_threshold": 0.5,
    }

    runs = report["runs"]
    assert len(runs) == 3
    reference_case_ids = runs[0]["case_ids"]
    for run_index, run in enumerate(runs, start=1):
        rows = run["cases"]
        assert run["run_index"] == run_index
        assert run["seed"] == 41 + run_index
        assert run["num_cases"] == len(rows) == 100
        assert run["failed_cases"] == 0
        assert run["case_ids"] == [row["case_id"] for row in rows]
        assert run["case_ids"] == reference_case_ids
        assert len(set(run["case_ids"])) == 100
        assert all(row["generation_valid"] for row in rows)
        assert all(row["llm_judge_valid"] for row in rows)
        assert all(row["nli_valid"] for row in rows)
        assert all(not row["error"] for row in rows)

        rebuilt_run = copy.deepcopy(run)
        benchmark._aggregate_run(rebuilt_run)
        assert rebuilt_run["failed_cases"] == run["failed_cases"]
        assert rebuilt_run["aggregate"] == pytest.approx(run["aggregate"])

    rebuilt_report = benchmark.build_final_report(
        runs=runs,
        provenance=provenance,
        expected_cases=100,
        required_runs=3,
    )
    assert rebuilt_report["evidence_class"] == "measured"
    assert rebuilt_report["evidence_reasons"] == []
    for metric in benchmark.RUN_METRICS:
        assert rebuilt_report["aggregate"][metric]["mean"] == pytest.approx(
            report["aggregate"][metric]["mean"]
        )
        assert rebuilt_report["aggregate"][metric]["ci_low"] == pytest.approx(
            report["aggregate"][metric]["ci_low"]
        )
        assert rebuilt_report["aggregate"][metric]["ci_high"] == pytest.approx(
            report["aggregate"][metric]["ci_high"]
        )
        assert rebuilt_report["aggregate"][metric]["n"] == 3
        assert rebuilt_report["aggregate"][metric]["ci_method"] == "student-t-95"
