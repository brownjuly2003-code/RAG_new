"""GR-3 harness: short context lists in the generator benchmark, hybrid pool timings."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from scripts import ab_remote_contextual as remote
from scripts import generator_benchmark as benchmark
from tests.test_ab_remote_contextual_entity_arm import (
    FakeEmbeddings,
    FakeReranker,
    _case,
    _install_pool_fakes,
    _register_arm_env,
    _write_cases,
    synthetic_chunks,
)

HYBRID_C_CANDS = [
    "Confirm the booking after the AWB is issued.",
    "AWB customs clearance uses the same air waybill.",
    "Customs cargo holds at the warehouse.",
    "AWB booking rules cover the air waybill.",
]
HYBRID_C_SOURCES = ["booking.md", "customs.md", "cargo.md", "booking.md"]
G1_POOL_CANDS = list(HYBRID_C_CANDS)
G1_POOL_SOURCES = list(HYBRID_C_SOURCES)
# FakeReranker scores are 0, -1, -2, -3; coherence keeps all four in that order (k=5).
G1_RERANK_CANDS = [
    "Confirm the booking after the AWB is issued.",
    "AWB customs clearance uses the same air waybill.",
    "Customs cargo holds at the warehouse.",
    "AWB booking rules cover the air waybill.",
]
G1_RERANK_SOURCES = ["booking.md", "customs.md", "cargo.md", "booking.md"]


@pytest.fixture(autouse=True)
def restore_arm_env(monkeypatch: Any) -> Iterator[None]:
    _register_arm_env(monkeypatch)
    yield


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_dataset_and_contexts(
    tmp_path: Path,
    *,
    cases: list[dict[str, Any]],
) -> tuple[Path, Path]:
    dataset = tmp_path / "cases.jsonl"
    contexts = tmp_path / "contexts.json"
    _write_jsonl(
        dataset,
        [
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "expected": {"answer_contains": case["kws"]},
            }
            for case in cases
        ],
    )
    contexts.write_text(
        json.dumps(
            [
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "kws": case["kws"],
                    "rerank_k": case["rerank_k"],
                    "cands": case["cands"],
                }
                for case in cases
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return dataset, contexts


def _short_pool_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "case-full",
            "query": "Полный вопрос?",
            "kws": ["полный"],
            "rerank_k": 5,
            "cands": [f"полный-{index}" for index in range(5)],
        },
        {
            "case_id": "case-short",
            "query": "Короткий вопрос?",
            "kws": ["короткий"],
            "rerank_k": 5,
            "cands": ["короткий-a", "короткий-b", "короткий-c"],
        },
    ]


def _full_pool_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "case-a",
            "query": "Первый вопрос?",
            "kws": ["первый"],
            "rerank_k": 5,
            "cands": [f"a-{index}" for index in range(6)],
        },
        {
            "case_id": "case-b",
            "query": "Второй вопрос?",
            "kws": ["второй"],
            "rerank_k": 4,
            "cands": [f"b-{index}" for index in range(4)],
        },
    ]


def _markdown_report(*, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_class": "measured",
        "created_at": "2026-01-01T00:00:00Z",
        "provenance": {
            "code_sha": "a" * 40,
            "dataset_sha256": "b" * 64,
            "contexts_sha256": "c" * 64,
            "ollama_model": "qwen2.5:7b",
            "ollama_model_digest": "d" * 64,
            "nli_model": benchmark.DEFAULT_NLI_MODEL,
            "nli_revision": benchmark.DEFAULT_NLI_REVISION,
            "config": config,
        },
        "aggregate": {metric: {"mean": None} for metric in benchmark.RUN_METRICS},
    }


def _patch_benchmark_runtime(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, Any],
) -> None:
    captured["llm_inits"] = 0
    captured["llm_invokes"] = 0

    class FakeOllamaLLM:
        def __init__(self, **kwargs: Any) -> None:
            captured["llm_inits"] += 1
            self.calls = 0
            self.failed_calls = 0

        def invoke(self, prompt: str) -> str:
            captured["llm_invokes"] += 1
            self.calls += 1
            if "ONLY a decimal number" in prompt:
                return "0.5"
            return "ответ"

        def model_metadata(self) -> dict[str, Any]:
            return {"digest": "d" * 64}

        def process_metadata(self) -> dict[str, Any]:
            return {}

        def unload(self) -> None:
            return None

    def capture_report(**kwargs: Any) -> dict[str, Any]:
        captured["provenance"] = kwargs["provenance"]
        captured["runs"] = kwargs["runs"]
        return {"evidence_class": "not_evidence", "aggregate": {}}

    monkeypatch.setattr(benchmark, "OllamaLLM", FakeOllamaLLM)
    monkeypatch.setattr(
        benchmark,
        "_git_value",
        lambda *args: "a" * 40 if args == ("rev-parse", "HEAD") else "",
    )
    monkeypatch.setattr(benchmark, "build_final_report", capture_report)
    monkeypatch.setattr(benchmark, "_render_markdown", lambda _report: "report\n")


def test_load_benchmark_cases_refuses_short_pool_without_flag(tmp_path: Path) -> None:
    dataset, contexts = _write_dataset_and_contexts(tmp_path, cases=_short_pool_cases())

    with pytest.raises(
        benchmark.BenchmarkInputError,
        match=r"invalid top_k=5 for case_id=case-short with 3 contexts",
    ):
        benchmark.load_benchmark_cases(
            dataset_path=dataset,
            contexts_path=contexts,
            expected_cases=2,
        )


def test_load_benchmark_cases_keeps_short_list_when_allowed(tmp_path: Path) -> None:
    dataset, contexts = _write_dataset_and_contexts(tmp_path, cases=_short_pool_cases())

    cases = benchmark.load_benchmark_cases(
        dataset_path=dataset,
        contexts_path=contexts,
        expected_cases=2,
        allow_short_contexts=True,
    )

    by_id = {case["case_id"]: case for case in cases}
    assert by_id["case-short"]["contexts"] == ["короткий-a", "короткий-b", "короткий-c"]
    assert by_id["case-full"]["contexts"] == [f"полный-{index}" for index in range(5)]


def test_load_benchmark_cases_keeps_empty_cands_when_allowed(tmp_path: Path) -> None:
    dataset, contexts = _write_dataset_and_contexts(
        tmp_path,
        cases=[
            {
                "case_id": "case-empty",
                "query": "Пустой вопрос?",
                "kws": ["пустой"],
                "rerank_k": 5,
                "cands": [],
            }
        ],
    )

    cases = benchmark.load_benchmark_cases(
        dataset_path=dataset,
        contexts_path=contexts,
        expected_cases=1,
        allow_short_contexts=True,
    )

    assert cases[0]["case_id"] == "case-empty"
    assert cases[0]["contexts"] == []


def _empty_generation_argv(
    tmp_path: Path,
    dataset: Path,
    contexts: Path,
    *,
    run_id: str,
) -> list[str]:
    return [
        "--dataset",
        str(dataset),
        "--contexts",
        str(contexts),
        "--results-dir",
        str(tmp_path),
        "--run-id",
        run_id,
        "--runs",
        "1",
        "--expected-cases",
        "1",
        "--skip-nli",
        "--allow-short-contexts",
    ]


def test_main_refuses_empty_cands_even_when_short_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, contexts = _write_dataset_and_contexts(
        tmp_path,
        cases=[
            {
                "case_id": "case-empty",
                "query": "Пустой вопрос?",
                "kws": ["пустой"],
                "rerank_k": 5,
                "cands": [],
            }
        ],
    )
    captured: dict[str, Any] = {}
    _patch_benchmark_runtime(monkeypatch, captured)

    with pytest.raises(
        benchmark.BenchmarkInputError,
        match=r"no contexts for case_id=case-empty",
    ):
        benchmark.main(_empty_generation_argv(tmp_path, dataset, contexts, run_id="empty-cands"))

    assert captured["llm_inits"] == 0
    assert captured["llm_invokes"] == 0
    assert "provenance" not in captured


def test_main_refuses_blank_cands_even_when_short_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, contexts = _write_dataset_and_contexts(
        tmp_path,
        cases=[
            {
                "case_id": "case-blank",
                "query": "Пустой вопрос?",
                "kws": ["пустой"],
                "rerank_k": 5,
                "cands": ["", "", ""],
            }
        ],
    )
    captured: dict[str, Any] = {}
    _patch_benchmark_runtime(monkeypatch, captured)

    with pytest.raises(
        benchmark.BenchmarkInputError,
        match=r"no contexts for case_id=case-blank",
    ):
        benchmark.main(_empty_generation_argv(tmp_path, dataset, contexts, run_id="blank-cands"))

    assert captured["llm_inits"] == 0
    assert captured["llm_invokes"] == 0
    assert "provenance" not in captured


def test_parse_args_allow_short_contexts_defaults_false() -> None:
    assert benchmark.parse_args([]).allow_short_contexts is False
    assert benchmark.parse_args(["--allow-short-contexts"]).allow_short_contexts is True


def test_main_passes_allow_short_contexts_into_loader_and_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = tmp_path / "cases.jsonl"
    contexts = tmp_path / "contexts.json"
    dataset.write_text("", encoding="utf-8")
    contexts.write_text("[]", encoding="utf-8")
    captured: dict[str, Any] = {}

    def capture_load(**kwargs: Any) -> list[dict[str, Any]]:
        captured["load_kwargs"] = kwargs
        return []

    _patch_benchmark_runtime(monkeypatch, captured)
    monkeypatch.setattr(benchmark, "load_benchmark_cases", capture_load)

    argv = [
        "--dataset",
        str(dataset),
        "--contexts",
        str(contexts),
        "--results-dir",
        str(tmp_path),
        "--runs",
        "1",
        "--expected-cases",
        "1",
        "--skip-nli",
    ]
    assert benchmark.main([*argv, "--run-id", "short-off"]) == 1
    assert captured["load_kwargs"]["allow_short_contexts"] is False
    assert captured["provenance"]["config"]["allow_short_contexts"] is False

    assert benchmark.main([*argv, "--run-id", "short-on", "--allow-short-contexts"]) == 1
    assert captured["load_kwargs"]["allow_short_contexts"] is True
    assert captured["provenance"]["config"]["allow_short_contexts"] is True


def test_full_pool_selects_identical_contexts_with_and_without_flag(tmp_path: Path) -> None:
    dataset, contexts = _write_dataset_and_contexts(tmp_path, cases=_full_pool_cases())
    kwargs = {
        "dataset_path": dataset,
        "contexts_path": contexts,
        "expected_cases": 2,
    }
    without_flag = benchmark.load_benchmark_cases(**kwargs)
    with_flag = benchmark.load_benchmark_cases(**kwargs, allow_short_contexts=True)

    assert [case["contexts"] for case in without_flag] == [case["contexts"] for case in with_flag]
    assert without_flag[0]["contexts"] == [f"a-{index}" for index in range(5)]
    assert without_flag[1]["contexts"] == [f"b-{index}" for index in range(4)]


def test_main_records_context_count_after_truncation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, contexts = _write_dataset_and_contexts(
        tmp_path,
        cases=[
            {
                "case_id": "case-trunc",
                "query": "Обрезанный вопрос?",
                "kws": ["первый"],
                "rerank_k": 3,
                "cands": ["первый " + "x" * 2993, "y" * 3000, "z" * 3000],
            }
        ],
    )
    captured: dict[str, Any] = {}
    _patch_benchmark_runtime(monkeypatch, captured)

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
                "trunc-count",
                "--runs",
                "1",
                "--expected-cases",
                "1",
                "--skip-nli",
            ]
        )
        == 1
    )
    row = captured["runs"][0]["cases"][0]
    assert row["case_id"] == "case-trunc"
    assert row["context_count"] == 2
    loaded = benchmark.load_benchmark_cases(
        dataset_path=dataset,
        contexts_path=contexts,
        expected_cases=1,
    )
    assert len(loaded[0]["contexts"]) == 2
    assert loaded[0]["top_k"] == 3


def test_main_records_short_context_count_when_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, contexts = _write_dataset_and_contexts(tmp_path, cases=_short_pool_cases())
    captured: dict[str, Any] = {}
    _patch_benchmark_runtime(monkeypatch, captured)

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
                "short-count",
                "--runs",
                "1",
                "--expected-cases",
                "2",
                "--skip-nli",
                "--allow-short-contexts",
            ]
        )
        == 1
    )
    assert captured["provenance"]["config"]["allow_short_contexts"] is True
    by_id = {row["case_id"]: row for row in captured["runs"][0]["cases"]}
    assert by_id["case-short"]["context_count"] == 3
    assert by_id["case-full"]["context_count"] == 5


def test_render_markdown_prints_short_context_flag() -> None:
    enabled = benchmark._render_markdown(_markdown_report(config={"allow_short_contexts": True}))
    missing = benchmark._render_markdown(_markdown_report(config={}))
    sha_line = f"- Contexts SHA-256: `{'c' * 64}`"
    enabled_lines = enabled.splitlines()
    missing_lines = missing.splitlines()
    sha_index = enabled_lines.index(sha_line)
    assert enabled_lines[sha_index + 1] == "- Short context lists allowed: `true`"
    assert missing_lines[missing_lines.index(sha_line) + 1] == (
        "- Short context lists allowed: `false`"
    )


def test_hybrid_arm_c_records_timing_ms_and_keeps_candidates(
    monkeypatch: Any, tmp_path: Path
) -> None:
    chunks = synthetic_chunks()
    cases_path = tmp_path / "cases.jsonl"
    _write_cases(cases_path, [_case()])
    _install_pool_fakes(
        monkeypatch,
        chunks=chunks,
        embeddings=FakeEmbeddings(),
        reranker=FakeReranker(),
    )
    out_dir = tmp_path / "out"

    assert remote.stage_pools("C", tmp_path / "corpus", cases_path, out_dir) == 0
    pool = json.loads((out_dir / "ab_phase2_C_pool.json").read_text(encoding="utf-8"))[0]
    timing = pool["timing_ms"]
    assert set(timing) == {"vector", "bm25"}
    assert isinstance(timing["vector"], float) and timing["vector"] >= 0.0
    assert isinstance(timing["bm25"], float) and timing["bm25"] >= 0.0
    assert pool["cands"] == HYBRID_C_CANDS
    assert pool["cand_sources"] == HYBRID_C_SOURCES

    assert remote.stage_rerank("C", out_dir) == 0
    reranked = json.loads((out_dir / "ab_candidates_phase2_C.json").read_text(encoding="utf-8"))[0]
    assert reranked["timing_ms"] == timing
    assert isinstance(reranked["rerank_s"], float)
    assert reranked["cands"] == HYBRID_C_CANDS
    assert reranked["cand_sources"] == HYBRID_C_SOURCES


def _assert_graph_timing_ms(row: dict[str, Any], *, entity: float) -> None:
    timing = row["timing_ms"]
    assert set(timing) == {"vector", "bm25", "entity"}
    assert isinstance(timing["vector"], float) and timing["vector"] >= 0.0
    assert isinstance(timing["bm25"], float) and timing["bm25"] >= 0.0
    assert isinstance(timing["entity"], float) and timing["entity"] == entity


def test_g1_arm_records_timing_ms_and_keeps_candidates(monkeypatch: Any, tmp_path: Path) -> None:
    chunks = synthetic_chunks()
    cases_path = tmp_path / "cases.jsonl"
    _write_cases(cases_path, [_case()])
    _install_pool_fakes(
        monkeypatch,
        chunks=chunks,
        embeddings=FakeEmbeddings(),
        reranker=FakeReranker(),
    )
    out_dir = tmp_path / "out"

    assert remote.stage_pools("G1", tmp_path / "corpus", cases_path, out_dir) == 0
    pool = json.loads((out_dir / "ab_phase2_G1_pool.json").read_text(encoding="utf-8"))[0]
    _assert_graph_timing_ms(pool, entity=0.0)
    assert pool["cands"] == G1_POOL_CANDS
    assert pool["cand_sources"] == G1_POOL_SOURCES

    assert remote.stage_rerank("G1", out_dir) == 0
    reranked = json.loads((out_dir / "ab_candidates_phase2_G1.json").read_text(encoding="utf-8"))[0]
    assert reranked["timing_ms"] == pool["timing_ms"]
    assert isinstance(reranked["rerank_s"], float)
    _assert_graph_timing_ms(reranked, entity=0.0)
    assert reranked["cands"] == G1_RERANK_CANDS
    assert reranked["cand_sources"] == G1_RERANK_SOURCES
