"""Contracts for the offline D.3 rerank file runner and CLI."""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import pgvector_rerank_run as runner

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "scripts/pgvector_rerank.py",
    "scripts/pgvector_rerank_run.py",
    "scripts/pgvector_spike.py",
    "evaluation/ragas_eval.py",
    "vectordb/_base_manager.py",
)
FAKE_VERSIONS = {"sentence-transformers": "9.8.7", "torch": "6.5.4"}
CHUNK_TEXTS = ["naïve chunk one", "second chunk ünique"]
ARMS_SENTINEL = {
    "postgres": {"rankings": [[1], [0]]},
    "chroma_bm25": {"rankings": [[0], [1]]},
}


def _clock() -> float:
    return 1234.5


def _json_bytes(value: object, *, indent: int | None = None) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=indent, allow_nan=False) + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _factory(recorder: list[str], result: object) -> Callable[[str], object]:
    def factory(model_name: str) -> object:
        recorder.append(model_name)
        return result

    return factory


def _patch_core(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[Any, ...], dict]]:
    calls: list[tuple[tuple[Any, ...], dict]] = []

    def fake_core(*args: Any, **kwargs: Any) -> dict:
        calls.append((args, kwargs))
        return ARMS_SENTINEL

    monkeypatch.setattr(runner, "run_offline_rerank", fake_core)
    return calls


def _write_inputs(tmp_path: Path, *, bad_digest: str | None = None) -> SimpleNamespace:
    chunks_path = tmp_path / "chunks.json"
    alpha_path = tmp_path / "alpha.jsonl"
    beta_path = tmp_path / "beta.jsonl"
    d1_report_path = tmp_path / "d1_report.json"

    chunks_bytes = _json_bytes(
        {"chunks": [{"page_content": text} for text in CHUNK_TEXTS]}
    )
    alpha_bytes = _json_bytes(
        {
            "case_id": "alpha-1",
            "query": "naïve alpha query",
            "expected": {"answer_contains": ["alpha_kw"]},
        }
    )
    beta_bytes = _json_bytes(
        {
            "case_id": "beta-1",
            "query": "beta plain query",
            "expected": {"answer_contains": ["beta_kw", "two"]},
        }
    )
    chunks_path.write_bytes(chunks_bytes)
    alpha_path.write_bytes(alpha_bytes)
    beta_path.write_bytes(beta_bytes)

    input_digests = {
        chunks_path.name: _sha256(chunks_bytes),
        alpha_path.name: _sha256(alpha_bytes),
        beta_path.name: _sha256(beta_bytes),
    }
    if bad_digest is not None:
        input_digests[bad_digest] = "0" * 64
    arm = {
        "rankings": [[0], [1]],
        "latency_ms": [1.0, 2.0],
        "metrics": {},
    }
    run = {"postgres": arm, "chroma_bm25": arm}
    d1_report = {
        "input_sha256": input_digests,
        "config": {
            "chunks": 2,
            "cases": 2,
            "top_k": 1,
            "repetitions": 3,
            "branch_limit": 20,
            "reranker": False,
        },
        "runs": [run, run, run],
    }
    d1_bytes = _json_bytes(d1_report, indent=2)
    d1_report_path.write_bytes(d1_bytes)
    return SimpleNamespace(
        chunks=chunks_path,
        alpha=alpha_path,
        beta=beta_path,
        d1=d1_report_path,
        d1_report=d1_report,
        d1_sha256=_sha256(d1_bytes),
        input_digests=input_digests,
        cases=[
            {
                "case_id": "alpha-1",
                "query": "naïve alpha query",
                "kws": ["alpha_kw"],
            },
            {
                "case_id": "beta-1",
                "query": "beta plain query",
                "kws": ["beta_kw", "two"],
            },
        ],
    )


def _run_args(fixture: SimpleNamespace, output_path: Path) -> dict[str, Any]:
    return {
        "chunks_path": fixture.chunks,
        "d1_report_path": fixture.d1,
        "case_paths": [fixture.alpha, fixture.beta],
        "output_path": output_path,
        "model_name": "mock-model",
        "code_base": "main",
        "clock": _clock,
    }


def test_run_from_files_writes_full_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _write_inputs(tmp_path)
    output_path = tmp_path / "rerank_report.json"
    core_calls = _patch_core(monkeypatch)
    version_calls: list[str] = []

    def fake_version(package: str) -> str:
        version_calls.append(package)
        return FAKE_VERSIONS[package]

    monkeypatch.setattr(runner.importlib.metadata, "version", fake_version)
    factory_calls: list[str] = []
    reranker = SimpleNamespace(_target_device="mock-device")
    result = runner.run_from_files(
        **_run_args(fixture, output_path),
        reranker_factory=_factory(factory_calls, reranker),
    )

    assert factory_calls == ["mock-model"]
    assert core_calls == [
        (
            (
                reranker,
                fixture.d1_report,
                fixture.cases,
                CHUNK_TEXTS,
                {"alpha": (0, 1), "beta": (1, 2)},
            ),
            {"clock": _clock, "top_k": 1},
        )
    ]
    assert version_calls == ["sentence-transformers", "torch"]
    expected = {
        "code_base": "main",
        "input_sha256": {
            fixture.chunks.name: fixture.input_digests[fixture.chunks.name],
            fixture.d1.name: fixture.d1_sha256,
            fixture.alpha.name: fixture.input_digests[fixture.alpha.name],
            fixture.beta.name: fixture.input_digests[fixture.beta.name],
        },
        "source_sha256": {
            relative: _sha256((REPO_ROOT / relative).read_bytes())
            for relative in SOURCE_FILES
        },
        "versions": FAKE_VERSIONS,
        "python": platform.python_version(),
        "config": {
            "chunks": 2,
            "cases": 2,
            "top_k": 1,
            "reranker_model": "mock-model",
            "reranker_device": "mock-device",
            "reranker": True,
            "source_report": fixture.d1.name,
            "source_report_sha256": fixture.d1_sha256,
        },
        "buckets": {
            "alpha": {"start": 0, "end": 1},
            "beta": {"start": 1, "end": 2},
        },
        "arms": ARMS_SENTINEL,
    }
    assert result == expected
    assert list(result) == [
        "code_base",
        "input_sha256",
        "source_sha256",
        "versions",
        "python",
        "config",
        "buckets",
        "arms",
    ]
    assert list(result["source_sha256"]) == list(SOURCE_FILES)
    raw = output_path.read_bytes()
    assert raw == _json_bytes(result, indent=2)
    assert json.loads(raw) == result


def test_run_from_files_rejects_digest_mismatch_before_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _write_inputs(tmp_path, bad_digest="alpha.jsonl")
    output_path = tmp_path / "rerank_report.json"
    core_calls = _patch_core(monkeypatch)
    factory_calls: list[str] = []

    with pytest.raises(ValueError, match="SHA-256"):
        runner.run_from_files(
            **_run_args(fixture, output_path),
            reranker_factory=_factory(factory_calls, object()),
        )

    assert factory_calls == []
    assert core_calls == []
    assert not output_path.exists()


def test_run_from_files_refuses_existing_output_before_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _write_inputs(tmp_path)
    output_path = tmp_path / "rerank_report.json"
    output_path.write_bytes(b"pre-existing\n")
    core_calls = _patch_core(monkeypatch)
    factory_calls: list[str] = []

    with pytest.raises(FileExistsError):
        runner.run_from_files(
            **_run_args(fixture, output_path),
            reranker_factory=_factory(factory_calls, object()),
        )

    assert factory_calls == []
    assert core_calls == []
    assert output_path.read_bytes() == b"pre-existing\n"


def test_run_from_files_rejects_missing_reranker_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _write_inputs(tmp_path)
    output_path = tmp_path / "rerank_report.json"
    core_calls = _patch_core(monkeypatch)
    factory_calls: list[str] = []

    with pytest.raises(RuntimeError, match="reranker"):
        runner.run_from_files(
            **_run_args(fixture, output_path),
            reranker_factory=_factory(factory_calls, None),
        )

    assert factory_calls == ["mock-model"]
    assert core_calls == []
    assert not output_path.exists()


def test_main_forwards_cli_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = {
        name: tmp_path / name
        for name in ("chunks.json", "d1.json", "alpha.jsonl", "beta.jsonl", "out.json")
    }
    captured: dict[str, object] = {}

    def fake_run_from_files(**kwargs: object) -> dict:
        captured.update(kwargs)
        return {"arms": {}}

    monkeypatch.setattr(runner, "run_from_files", fake_run_from_files)
    exit_code = runner.main(
        [
            "--chunks",
            str(paths["chunks.json"]),
            "--d1-report",
            str(paths["d1.json"]),
            "--cases",
            str(paths["alpha.jsonl"]),
            "--cases",
            str(paths["beta.jsonl"]),
            "--output",
            str(paths["out.json"]),
            "--model",
            "mock-model",
            "--code-base",
            "main",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "chunks_path": paths["chunks.json"],
        "d1_report_path": paths["d1.json"],
        "case_paths": [paths["alpha.jsonl"], paths["beta.jsonl"]],
        "output_path": paths["out.json"],
        "model_name": "mock-model",
        "code_base": "main",
    }
    stdout = capsys.readouterr().out
    assert "DONE" in stdout
    assert str(paths["out.json"]) in stdout
