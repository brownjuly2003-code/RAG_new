"""A skipped evaluation run must not read as a passing one.

Audit 2026-08-24 (FIN-11): scripts/eval_gate.py answered an unavailable
pipeline with ``{metric: 1.0}`` for every metric, wrote those fabricated
perfect scores to evaluation/current_metrics.json, printed
"EVAL GATE: PASSED (graceful skip)" and exited 0. Anything reading the exit
code or the artefact would conclude the system had been measured and had
scored perfectly.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GATE_PATH = PROJECT_ROOT / "scripts" / "eval_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("_eval_gate_under_test", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _load_gate()
    monkeypatch.setattr(module, "CURRENT_FILE", tmp_path / "current_metrics.json")
    return module


def test_skipped_run_exits_non_zero_with_a_not_evidence_marker(
    gate: Any, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        gate, "load_test_cases", lambda: [{"question": "q"} for _ in range(10)]
    )
    monkeypatch.setattr(gate, "validate_test_cases", lambda cases: None)
    monkeypatch.setattr(
        gate, "run_live_evaluation", lambda cases: ({}, "Ollama unavailable")
    )
    monkeypatch.setattr(gate, "_load_baseline", lambda: {})

    exit_code = gate.main()

    assert exit_code != 0, "a run that never happened must not exit 0"
    out = capsys.readouterr().out
    assert "NOT_EVIDENCE" in out
    assert "PASSED" not in out


def test_skipped_run_never_writes_fabricated_scores(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        gate, "load_test_cases", lambda: [{"question": "q"} for _ in range(10)]
    )
    monkeypatch.setattr(gate, "validate_test_cases", lambda cases: None)
    monkeypatch.setattr(
        gate, "run_live_evaluation", lambda cases: ({}, "retriever is not initialized")
    )
    monkeypatch.setattr(gate, "_load_baseline", lambda: {})

    gate.main()

    payload = json.loads(gate.CURRENT_FILE.read_text(encoding="utf-8"))
    assert payload["skipped"] is True
    assert payload["evidence_class"] == "not_evidence"
    assert payload["aggregate"] == {}, "a skipped run has no scores to report"


def test_measured_run_is_marked_as_evidence(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    scores = {"context_precision": 0.8, "faithfulness": 0.9, "answer_relevancy": 0.8}
    monkeypatch.setattr(
        gate, "load_test_cases", lambda: [{"question": "q"} for _ in range(10)]
    )
    monkeypatch.setattr(gate, "validate_test_cases", lambda cases: None)
    monkeypatch.setattr(gate, "run_live_evaluation", lambda cases: (scores, None))
    monkeypatch.setattr(gate, "_load_baseline", lambda: {})

    assert gate.main() == 0

    payload = json.loads(gate.CURRENT_FILE.read_text(encoding="utf-8"))
    assert payload["skipped"] is False
    assert payload["evidence_class"] == "measured"
    assert payload["aggregate"] == scores


def test_unavailable_pipeline_yields_no_scores_rather_than_perfect_ones(
    gate: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        gate,
        "_load_pipeline_dependencies",
        lambda: (None, None, None, "Ollama unavailable at http://localhost:11434"),
    )

    scores, reason = gate.run_live_evaluation([{"question": "q"}])

    assert scores == {}
    assert reason and "Ollama unavailable" in reason
