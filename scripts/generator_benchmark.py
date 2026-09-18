#!/usr/bin/env python3
"""Phase C generator benchmark over the cached 100-case aircargo contexts.

The heavy path is intended for the project Mac, not the Windows laptop. Ollama
generation/LLM judging finishes first and explicitly unloads the model before
the multilingual NLI scorer is loaded, keeping the two model peaks separate on
an 8 GiB host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeGuard

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.ragas_eval import context_precision, context_recall  # noqa: E402

SCHEMA_VERSION = 1
PROMPT_VERSION = "aircargo-context-only-ru-v1"
DEFAULT_NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
DEFAULT_NLI_REVISION = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"
DEFAULT_DATASET = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
DEFAULT_CONTEXTS = PROJECT_ROOT / ".tmp" / "ab_candidates_phase2_C.json"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "reports" / "ragas"

QUALITY_METRICS = (
    "llm_faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "nli_faithfulness",
    "nli_supported_claim_rate",
)
RUN_METRICS = (*QUALITY_METRICS, "mean_latency_ms")
REQUIRED_PROVENANCE = (
    "code_sha",
    "dataset_sha256",
    "contexts_sha256",
    "ollama_model_digest",
    "nli_model",
    "nli_revision",
)

RequestJson = Callable[[str, str, dict[str, Any] | None, float], dict[str, Any]]


class BenchmarkInputError(ValueError):
    """Raised when an input cannot support an honest benchmark claim."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkInputError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise BenchmarkInputError(f"row {line_number} in {path} is not an object")
        rows.append(row)
    return rows


def _expected_keywords(row: Mapping[str, Any]) -> list[str]:
    expected = row.get("expected")
    if not isinstance(expected, Mapping):
        return []
    keywords = [str(item) for item in expected.get("answer_contains", []) if item]
    for alternatives in expected.get("answer_contains_any", []) or []:
        if not isinstance(alternatives, Sequence) or isinstance(alternatives, str):
            continue
        representative = next((str(item) for item in alternatives if item), "")
        if representative:
            keywords.append(representative)
    return keywords


def _unique_by_case_id(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if not case_id:
            raise BenchmarkInputError(f"{source} contains a row without case_id")
        if case_id in indexed:
            raise BenchmarkInputError(f"{source} contains duplicate case_id={case_id}")
        indexed[case_id] = row
    return indexed


def _truncate_contexts(contexts: Sequence[str], max_chars: int) -> list[str]:
    if max_chars <= 0:
        return [str(item) for item in contexts]
    remaining = max_chars
    selected: list[str] = []
    for context in contexts:
        if remaining <= 0:
            break
        text = str(context)
        if not text:
            continue
        selected.append(text[:remaining])
        remaining -= len(selected[-1])
    return selected


def load_benchmark_cases(
    *,
    dataset_path: Path,
    contexts_path: Path,
    expected_cases: int = 100,
    top_k: int | None = None,
    context_chars: int = 6000,
    allow_short_contexts: bool = False,
) -> list[dict[str, Any]]:
    """Load dataset/context rows and fail closed on identity or ordering drift."""
    dataset_rows = _read_jsonl(Path(dataset_path))
    raw_context_rows = json.loads(Path(contexts_path).read_text(encoding="utf-8"))
    if not isinstance(raw_context_rows, list) or not all(
        isinstance(item, dict) for item in raw_context_rows
    ):
        raise BenchmarkInputError("contexts artifact must be a JSON array of objects")
    if len(dataset_rows) != expected_cases:
        raise BenchmarkInputError(
            f"dataset case count={len(dataset_rows)} != expected_cases={expected_cases}"
        )
    if len(raw_context_rows) != expected_cases:
        raise BenchmarkInputError(
            f"context case count={len(raw_context_rows)} != expected_cases={expected_cases}"
        )

    dataset_by_id = _unique_by_case_id(dataset_rows, source="dataset")
    contexts_by_id = _unique_by_case_id(raw_context_rows, source="contexts")
    if set(dataset_by_id) != set(contexts_by_id):
        missing = sorted(set(dataset_by_id) - set(contexts_by_id))
        foreign = sorted(set(contexts_by_id) - set(dataset_by_id))
        raise BenchmarkInputError(
            f"dataset/context case ids differ: missing={missing[:5]} foreign={foreign[:5]}"
        )

    cases: list[dict[str, Any]] = []
    for dataset_row in dataset_rows:
        case_id = str(dataset_row["case_id"])
        context_row = contexts_by_id[case_id]
        query = str(dataset_row.get("query") or "")
        if query != str(context_row.get("query") or ""):
            raise BenchmarkInputError(f"query mismatch for case_id={case_id}")
        keywords = _expected_keywords(dataset_row)
        context_keywords = [str(item) for item in context_row.get("kws", []) if item]
        if keywords != context_keywords:
            raise BenchmarkInputError(f"keyword mismatch for case_id={case_id}")
        candidates = context_row.get("cands")
        if not isinstance(candidates, list) or not all(
            isinstance(item, str) for item in candidates
        ):
            raise BenchmarkInputError(f"invalid contexts for case_id={case_id}")
        selected_k = top_k if top_k is not None else int(context_row.get("rerank_k") or 0)
        if selected_k <= 0 or (selected_k > len(candidates) and not allow_short_contexts):
            raise BenchmarkInputError(
                f"invalid top_k={selected_k} for case_id={case_id} with {len(candidates)} contexts"
            )
        cases.append(
            {
                "case_id": case_id,
                "query": query,
                "expected_keywords": keywords,
                "contexts": _truncate_contexts(candidates[:selected_k], context_chars),
                "top_k": selected_k,
            }
        )
    return cases


def _default_request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    response = httpx.request(method, url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"non-object JSON response from {url}")
    return data


class OllamaLLM:
    """Small deterministic Ollama client used for generation and strict judging."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        seed: int,
        temperature: float,
        num_ctx: int,
        num_predict: int,
        timeout_sec: float,
        keep_alive: str,
        think: bool | None = None,
        request_json: RequestJson = _default_request_json,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.seed = seed
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout_sec = timeout_sec
        self.keep_alive = keep_alive
        self.think = think
        self._request_json = request_json
        self.calls = 0
        self.failed_calls = 0

    def invoke(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        if self.think is not None:
            payload["think"] = self.think
        try:
            data = self._request_json(
                "POST",
                f"{self.base_url}/api/generate",
                payload,
                self.timeout_sec,
            )
            answer = data.get("response")
            if not isinstance(answer, str):
                raise RuntimeError("Ollama response is missing string field 'response'")
            self.calls += 1
            return answer.strip()
        except Exception:
            self.failed_calls += 1
            raise

    def unload(self) -> None:
        self._request_json(
            "POST",
            f"{self.base_url}/api/generate",
            {"model": self.model, "keep_alive": 0},
            self.timeout_sec,
        )

    def model_metadata(self) -> dict[str, Any]:
        data = self._request_json(
            "GET",
            f"{self.base_url}/api/tags",
            None,
            self.timeout_sec,
        )
        models = data.get("models")
        if not isinstance(models, list):
            raise RuntimeError("Ollama /api/tags response is missing models")
        for item in models:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or item.get("model") or "")
            if name == self.model:
                return {
                    "name": name,
                    "digest": str(item.get("digest") or ""),
                    "size_bytes": int(item.get("size") or 0),
                    "modified_at": item.get("modified_at"),
                    "details": dict(item.get("details") or {}),
                }
        raise RuntimeError(f"Ollama model is not installed: {self.model}")

    def process_metadata(self) -> dict[str, Any]:
        data = self._request_json(
            "GET",
            f"{self.base_url}/api/ps",
            None,
            self.timeout_sec,
        )
        models = data.get("models")
        if not isinstance(models, list):
            return {}
        for item in models:
            if isinstance(item, Mapping) and str(item.get("name") or "") == self.model:
                return {
                    "size_bytes": int(item.get("size") or 0),
                    "size_vram_bytes": int(item.get("size_vram") or 0),
                    "expires_at": item.get("expires_at"),
                }
        return {}


def _answer_prompt(question: str, contexts: Sequence[str]) -> str:
    context = "\n\n---\n\n".join(contexts)
    return (
        "Ты — ассистент поддержки. Ответь на вопрос пользователя СТРОГО на основе "
        "приведённого контекста. Если в контексте нет ответа — честно скажи, что "
        "информации недостаточно. Отвечай кратко и по делу, на русском.\n\n"
        f"КОНТЕКСТ:\n{context}\n\n"
        f"ВОПРОС: {question}\n\nОТВЕТ:"
    )


def parse_unit_interval_score(raw: str) -> float:
    """Parse only a bare decimal in [0, 1]; judge prose is not evidence."""
    text = raw.strip()
    if re.fullmatch(r"(?:0(?:\.\d+)?|1(?:\.0+)?)", text) is None:
        raise BenchmarkInputError(f"judge did not return a strict unit-interval score: {text!r}")
    value = float(text)
    if not 0.0 <= value <= 1.0:
        raise BenchmarkInputError(f"judge did not return a strict unit-interval score: {text!r}")
    return value


def _judge_scores(
    llm: OllamaLLM,
    *,
    question: str,
    answer: str,
    contexts: Sequence[str],
    expected_keywords: Sequence[str],
) -> dict[str, float]:
    context_text = "\n".join(contexts)
    faithfulness_prompt = (
        "You are an evaluation expert. Given a context and an answer, determine "
        "what fraction of claims in the answer are supported by the context.\n\n"
        f"CONTEXT:\n{context_text[:3000]}\n\n"
        f"ANSWER:\n{answer[:2000]}\n\n"
        "Respond with ONLY a decimal number between 0.0 and 1.0 representing "
        "the faithfulness score (1.0 = fully faithful, 0.0 = completely "
        "hallucinated).\nScore:"
    )
    relevancy_prompt = (
        "You are an evaluation expert. Given a question and an answer, rate how "
        "well the answer addresses the question.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"ANSWER:\n{answer[:2000]}\n\n"
        "Respond with ONLY a decimal number between 0.0 and 1.0 "
        "(1.0 = perfectly relevant, 0.0 = completely irrelevant).\nScore:"
    )
    docs = [{"page_content": item} for item in contexts]
    return {
        "faithfulness": parse_unit_interval_score(llm.invoke(faithfulness_prompt)),
        "answer_relevancy": parse_unit_interval_score(llm.invoke(relevancy_prompt)),
        "context_precision": round(
            context_precision(question, docs, list(expected_keywords)),
            4,
        ),
        "context_recall": round(context_recall(docs, list(expected_keywords)), 4),
    }


def split_material_claims(answer: str) -> list[str]:
    """Split Russian/English prose and Markdown lists into NLI hypotheses."""
    claims: list[str] = []
    for line in re.split(r"[\r\n]+", answer.strip()):
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if not cleaned:
            continue
        for part in re.split(r"(?<=[.!?])\s+", cleaned):
            claim = part.strip()
            if claim:
                claims.append(claim)
    return claims


def summarize_nli_claims(
    claims: Sequence[Mapping[str, Any]],
    *,
    support_threshold: float,
) -> dict[str, Any]:
    best_scores: list[float] = []
    materialized: list[dict[str, Any]] = []
    for item in claims:
        scores = [float(value) for value in item.get("entailment_scores", [])]
        best = max(scores, default=0.0)
        best_scores.append(best)
        materialized.append(
            {
                "claim": str(item.get("claim") or ""),
                "entailment_scores": [round(value, 6) for value in scores],
                "best_entailment": round(best, 6),
                "supported": best >= support_threshold,
            }
        )
    n_claims = len(best_scores)
    supported = sum(score >= support_threshold for score in best_scores)
    return {
        "n_claims": n_claims,
        "n_supported_claims": supported,
        "supported_claim_rate": supported / n_claims if n_claims else 0.0,
        "nli_faithfulness": statistics.fmean(best_scores) if best_scores else 0.0,
        "claims": materialized,
    }


class MultilingualNLIScorer:
    """Pinned multilingual NLI scorer; model imports stay out of light paths."""

    def __init__(
        self,
        *,
        model_name: str,
        revision: str,
        batch_size: int,
        device: str,
        support_threshold: float,
    ) -> None:
        try:
            import torch
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )
        except ImportError as exc:
            raise RuntimeError(
                "NLI scoring requires torch and transformers on the Mac runtime"
            ) from exc

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            revision=revision,
        )
        self._device = torch.device(device)
        self._model.to(self._device)
        self._model.eval()
        self._batch_size = batch_size
        self._support_threshold = support_threshold
        id2label = {
            int(key): str(value).lower() for key, value in self._model.config.id2label.items()
        }
        matches = [index for index, label in id2label.items() if label == "entailment"]
        if len(matches) != 1:
            raise RuntimeError(f"NLI model has no unique entailment label: {id2label}")
        self._entailment_index = matches[0]

    def score(self, answer: str, contexts: Sequence[str]) -> dict[str, Any]:
        claims = split_material_claims(answer)
        scored: list[dict[str, Any]] = []
        for claim in claims:
            entailment_scores: list[float] = []
            for start in range(0, len(contexts), self._batch_size):
                premises = list(contexts[start : start + self._batch_size])
                hypotheses = [claim] * len(premises)
                encoded = self._tokenizer(
                    premises,
                    hypotheses,
                    padding=True,
                    truncation="only_first",
                    max_length=512,
                    return_tensors="pt",
                )
                encoded = {key: value.to(self._device) for key, value in encoded.items()}
                with self._torch.inference_mode():
                    logits = self._model(**encoded).logits
                    probabilities = self._torch.softmax(logits, dim=-1)
                entailment_scores.extend(
                    float(row[self._entailment_index].item()) for row in probabilities
                )
            scored.append({"claim": claim, "entailment_scores": entailment_scores})
        return summarize_nli_claims(scored, support_threshold=self._support_threshold)


def _student_t_95(values: Sequence[float], *, clamp_unit: bool) -> dict[str, Any]:
    numbers = [float(value) for value in values]
    if not numbers:
        return {
            "mean": None,
            "ci_low": None,
            "ci_high": None,
            "n": 0,
            "ci_method": "student-t-95",
        }
    mean = statistics.fmean(numbers)
    if len(numbers) == 1:
        low = high = mean
    else:
        # The Phase-C gate requires exactly three runs (df=2).
        critical = 4.302652729911275 if len(numbers) == 3 else 1.96
        half_width = critical * statistics.stdev(numbers) / math.sqrt(len(numbers))
        low, high = mean - half_width, mean + half_width
    if clamp_unit:
        low, high = max(0.0, low), min(1.0, high)
    return {
        "mean": mean,
        "ci_low": low,
        "ci_high": high,
        "n": len(numbers),
        "ci_method": "student-t-95",
    }


def _finite_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def build_final_report(
    *,
    runs: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
    expected_cases: int,
    required_runs: int,
) -> dict[str, Any]:
    """Build the report and fail closed unless the complete measured contract holds."""
    reasons: list[str] = []
    for field in REQUIRED_PROVENANCE:
        if not str(provenance.get(field) or "").strip():
            reasons.append(f"missing provenance: {field}")
    if len(runs) < required_runs:
        reasons.append(f"run_count={len(runs)} < required_runs={required_runs}")
    elif len(runs) > required_runs:
        reasons.append(f"run_count={len(runs)} > required_runs={required_runs}")

    reference_ids: list[str] | None = None
    for run in runs:
        run_index = int(run.get("run_index") or 0)
        if int(run.get("num_cases") or 0) != expected_cases:
            reasons.append(
                f"run {run_index} num_cases={run.get('num_cases')} != expected_cases={expected_cases}"
            )
        if int(run.get("failed_cases") or 0) != 0:
            reasons.append(f"run {run_index} failed_cases={run.get('failed_cases')}")
        case_ids = [str(item) for item in run.get("case_ids", [])]
        if len(case_ids) != len(set(case_ids)):
            reasons.append(f"run {run_index} has duplicate case ids")
        if reference_ids is None:
            reference_ids = case_ids
        elif case_ids != reference_ids:
            reasons.append(f"run {run_index} case order differs")
        aggregate = run.get("aggregate")
        if not isinstance(aggregate, Mapping):
            reasons.append(f"run {run_index} has no aggregate")
            continue
        for metric in RUN_METRICS:
            if not _finite_number(aggregate.get(metric)):
                reasons.append(f"run {run_index} missing finite metric: {metric}")

    aggregate_out: dict[str, Any] = {}
    for metric in RUN_METRICS:
        values = [
            float(run["aggregate"][metric])
            for run in runs
            if isinstance(run.get("aggregate"), Mapping)
            and _finite_number(run["aggregate"].get(metric))
        ]
        aggregate_out[metric] = _student_t_95(
            values,
            clamp_unit=metric != "mean_latency_ms",
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "phase-c-generator-benchmark",
        "created_at": _utc_now_iso(),
        "evidence_class": "measured" if not reasons else "not_evidence",
        "evidence_reasons": reasons,
        "required_runs": required_runs,
        "expected_cases": expected_cases,
        "provenance": dict(provenance),
        "aggregate": aggregate_out,
        "runs": [dict(run) for run in runs],
    }


def _aggregate_run(run: dict[str, Any]) -> None:
    rows = run.get("cases", [])
    totals: dict[str, list[float]] = {metric: [] for metric in QUALITY_METRICS}
    latencies: list[float] = []
    failed = 0
    for row in rows:
        valid = bool(row.get("generation_valid")) and bool(row.get("llm_judge_valid"))
        valid = valid and bool(row.get("nli_valid"))
        if not valid:
            failed += 1
        scores = row.get("scores") or {}
        nli = row.get("nli") or {}
        metric_values = {
            "llm_faithfulness": scores.get("faithfulness"),
            "answer_relevancy": scores.get("answer_relevancy"),
            "context_precision": scores.get("context_precision"),
            "context_recall": scores.get("context_recall"),
            "nli_faithfulness": nli.get("nli_faithfulness"),
            "nli_supported_claim_rate": nli.get("supported_claim_rate"),
        }
        for metric, value in metric_values.items():
            totals[metric].append(float(value) if _finite_number(value) else 0.0)
        latencies.append(float(row.get("latency_ms") or 0.0))
    run["num_cases"] = len(rows)
    run["failed_cases"] = failed
    run["case_ids"] = [str(row.get("case_id") or "") for row in rows]
    run["aggregate"] = {
        metric: statistics.fmean(values) if values else 0.0 for metric, values in totals.items()
    }
    run["aggregate"]["mean_latency_ms"] = statistics.fmean(latencies) if latencies else 0.0


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _max_rss_bytes() -> int:
    if sys.platform == "win32":
        return 0
    import resource

    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _checkpoint_for(
    *,
    run_id: str,
    provenance: Mapping[str, Any],
    config: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "provenance": dict(provenance),
        "config": dict(config),
        "runs": [dict(run) for run in runs],
    }


def _load_checkpoint(
    path: Path,
    *,
    run_id: str,
    provenance: Mapping[str, Any],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("run_id") != run_id:
        raise BenchmarkInputError("checkpoint run_id differs")
    if data.get("provenance") != dict(provenance):
        raise BenchmarkInputError("checkpoint provenance differs")
    if data.get("config") != dict(config):
        raise BenchmarkInputError("checkpoint config differs")
    runs = data.get("runs")
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise BenchmarkInputError("checkpoint runs are invalid")
    return runs


def _render_markdown(report: Mapping[str, Any]) -> str:
    allow_short = bool(report["provenance"]["config"].get("allow_short_contexts", False))
    lines = [
        "# Phase C generator benchmark",
        "",
        f"- Evidence class: `{report['evidence_class']}`",
        f"- Created: `{report['created_at']}`",
        f"- Code SHA: `{report['provenance']['code_sha']}`",
        f"- Dataset SHA-256: `{report['provenance']['dataset_sha256']}`",
        f"- Contexts SHA-256: `{report['provenance']['contexts_sha256']}`",
        f"- Short context lists allowed: `{'true' if allow_short else 'false'}`",
        f"- Ollama model: `{report['provenance']['ollama_model']}` "
        f"(`{report['provenance']['ollama_model_digest']}`)",
        f"- NLI: `{report['provenance']['nli_model']}` @ `{report['provenance']['nli_revision']}`",
        "",
        "The corpus is agent-labelled and the contexts are a cached, hash-pinned "
        "RRF/rerank artifact. This is generator-quality evidence, not a real "
        "shipment-resolution metric.",
        "",
        "## Aggregate across runs",
        "",
        "| Metric | Mean | 95% CI | n |",
        "|---|---:|---:|---:|",
    ]
    for metric in RUN_METRICS:
        summary = report["aggregate"][metric]
        if summary["mean"] is None:
            lines.append(f"| {metric} | n/a | n/a | 0 |")
            continue
        lines.append(
            f"| {metric} | {summary['mean']:.4f} | "
            f"[{summary['ci_low']:.4f}, {summary['ci_high']:.4f}] | {summary['n']} |"
        )
    if report.get("evidence_reasons"):
        lines.extend(["", "## Evidence blockers", ""])
        lines.extend(f"- {reason}" for reason in report["evidence_reasons"])
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--contexts", type=Path, default=DEFAULT_CONTEXTS)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--ollama-base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--expected-cases", type=int, default=100)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--context-chars", type=int, default=6000)
    parser.add_argument("--allow-short-contexts", action="store_true")
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--num-predict", type=int, default=384)
    parser.add_argument("--timeout-sec", type=float, default=600.0)
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--think", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--nli-model", default=DEFAULT_NLI_MODEL)
    parser.add_argument("--nli-revision", default=DEFAULT_NLI_REVISION)
    parser.add_argument("--nli-device", default="cpu")
    parser.add_argument("--nli-batch-size", type=int, default=4)
    parser.add_argument("--nli-support-threshold", type=float, default=0.5)
    parser.add_argument("--skip-nli", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or datetime.now(UTC).strftime("c1a-%Y%m%dT%H%M%SZ")
    if args.runs <= 0 or args.expected_cases <= 0:
        raise BenchmarkInputError("runs and expected_cases must be positive")
    if args.nli_batch_size <= 0:
        raise BenchmarkInputError("nli_batch_size must be positive")

    cases = load_benchmark_cases(
        dataset_path=args.dataset,
        contexts_path=args.contexts,
        expected_cases=args.expected_cases,
        top_k=args.top_k,
        context_chars=args.context_chars,
        allow_short_contexts=args.allow_short_contexts,
    )
    for case in cases:
        if not case["contexts"]:
            raise BenchmarkInputError(f"no contexts for case_id={case['case_id']}")
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    probe = OllamaLLM(
        base_url=args.ollama_base_url,
        model=args.model,
        seed=args.seed_base,
        temperature=args.temperature,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
        timeout_sec=args.timeout_sec,
        keep_alive=args.keep_alive,
        think=args.think,
    )
    model_metadata = probe.model_metadata()
    config = {
        "prompt_version": PROMPT_VERSION,
        "runs": args.runs,
        "expected_cases": args.expected_cases,
        "selected_cases": len(cases),
        "top_k_override": args.top_k,
        "context_chars": args.context_chars,
        "allow_short_contexts": args.allow_short_contexts,
        "seed_base": args.seed_base,
        "temperature": args.temperature,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "think": args.think,
        "nli_batch_size": args.nli_batch_size,
        "nli_support_threshold": args.nli_support_threshold,
    }
    provenance = {
        "code_sha": _git_value("rev-parse", "HEAD"),
        "code_tree_clean": not bool(_git_value("status", "--porcelain")),
        "dataset_path": str(Path(args.dataset).resolve()),
        "dataset_sha256": _sha256_path(args.dataset),
        "contexts_path": str(Path(args.contexts).resolve()),
        "contexts_sha256": _sha256_path(args.contexts),
        "ollama_model": args.model,
        "ollama_model_digest": model_metadata["digest"],
        "ollama_model_metadata": model_metadata,
        "ollama_think": args.think,
        "nli_model": args.nli_model,
        "nli_revision": args.nli_revision,
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "config": config,
    }
    if not provenance["code_tree_clean"]:
        raise BenchmarkInputError("benchmark source tree must be clean")
    if not provenance["ollama_model_digest"]:
        raise BenchmarkInputError("Ollama model digest is empty")
    checkpoint_provenance = dict(provenance)

    checkpoint_path = args.results_dir / f"{run_id}-checkpoint.json"
    if args.resume:
        if not checkpoint_path.exists():
            raise BenchmarkInputError(f"checkpoint does not exist: {checkpoint_path}")
        runs = _load_checkpoint(
            checkpoint_path,
            run_id=run_id,
            provenance=checkpoint_provenance,
            config=config,
        )
    elif checkpoint_path.exists():
        raise BenchmarkInputError(
            f"checkpoint already exists: {checkpoint_path}; pass --resume or another --run-id"
        )
    else:
        runs = []

    llms_by_seed: dict[int, OllamaLLM] = {}

    def save_checkpoint() -> None:
        _atomic_write_json(
            checkpoint_path,
            _checkpoint_for(
                run_id=run_id,
                provenance=checkpoint_provenance,
                config=config,
                runs=runs,
            ),
        )

    for run_index in range(1, args.runs + 1):
        run = next((item for item in runs if item.get("run_index") == run_index), None)
        if run is None:
            run = {"run_index": run_index, "seed": args.seed_base + run_index - 1, "cases": []}
            runs.append(run)
        completed = {str(item.get("case_id")) for item in run["cases"]}
        seed = int(run["seed"])
        llm = OllamaLLM(
            base_url=args.ollama_base_url,
            model=args.model,
            seed=seed,
            temperature=args.temperature,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            timeout_sec=args.timeout_sec,
            keep_alive=args.keep_alive,
            think=args.think,
        )
        llms_by_seed[seed] = llm
        for case_number, case in enumerate(cases, 1):
            if case["case_id"] in completed:
                continue
            started = time.perf_counter()
            generation_valid = True
            llm_judge_valid = False
            error = ""
            try:
                answer = llm.invoke(_answer_prompt(case["query"], case["contexts"]))
                if not answer:
                    raise RuntimeError("empty generated answer")
            except Exception as exc:
                generation_valid = False
                answer = ""
                error = f"generation: {type(exc).__name__}: {exc}"

            failed_before_judge = llm.failed_calls
            calls_before_judge = llm.calls
            if generation_valid:
                try:
                    scores = _judge_scores(
                        llm,
                        question=case["query"],
                        answer=answer,
                        contexts=case["contexts"],
                        expected_keywords=case["expected_keywords"],
                    )
                    llm_judge_valid = (
                        llm.failed_calls == failed_before_judge
                        and llm.calls - calls_before_judge == 2
                    )
                except Exception as exc:
                    docs = [{"page_content": item} for item in case["contexts"]]
                    scores = {
                        "faithfulness": 0.0,
                        "answer_relevancy": 0.0,
                        "context_precision": round(
                            context_precision(
                                case["query"],
                                docs,
                                case["expected_keywords"],
                            ),
                            4,
                        ),
                        "context_recall": round(
                            context_recall(docs, case["expected_keywords"]),
                            4,
                        ),
                    }
                    error = (error + "; " if error else "") + f"judge: {type(exc).__name__}: {exc}"
            else:
                scores = {
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "context_recall": 0.0,
                }
            latency_ms = int((time.perf_counter() - started) * 1000)
            run["cases"].append(
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "answer": answer,
                    "latency_ms": latency_ms,
                    "generation_valid": generation_valid,
                    "llm_judge_valid": llm_judge_valid,
                    "nli_valid": False,
                    "error": error,
                    "scores": scores,
                    "context_count": len(case["contexts"]),
                }
            )
            save_checkpoint()
            print(
                f"[generate run {run_index}/{args.runs} case {case_number}/{len(cases)}] "
                f"{case['case_id']} {latency_ms}ms",
                flush=True,
            )

    ollama_runtime: dict[str, Any] = {}
    for llm in llms_by_seed.values():
        if not ollama_runtime:
            ollama_runtime = llm.process_metadata()
        llm.unload()
    provenance["ollama_runtime"] = ollama_runtime

    case_by_id = {str(case["case_id"]): case for case in cases}
    scorer: MultilingualNLIScorer | None = None
    if not args.skip_nli:
        scorer = MultilingualNLIScorer(
            model_name=args.nli_model,
            revision=args.nli_revision,
            batch_size=args.nli_batch_size,
            device=args.nli_device,
            support_threshold=args.nli_support_threshold,
        )
    for run in runs:
        for case_number, row in enumerate(run["cases"], 1):
            if row.get("nli_valid"):
                continue
            if scorer is not None and row.get("generation_valid"):
                case = case_by_id[str(row["case_id"])]
                try:
                    row["nli"] = scorer.score(str(row["answer"]), case["contexts"])
                    row["nli_valid"] = True
                except Exception as exc:
                    row["nli"] = {
                        "nli_faithfulness": 0.0,
                        "supported_claim_rate": 0.0,
                        "claims": [],
                    }
                    row["error"] = (
                        str(row.get("error") or "") + f"; nli: {type(exc).__name__}: {exc}"
                    ).strip("; ")
            save_checkpoint()
            print(
                f"[nli run {run['run_index']}/{args.runs} case {case_number}/{len(cases)}] "
                f"{row['case_id']}",
                flush=True,
            )
        _aggregate_run(run)
    provenance["nli_process_peak_rss_bytes"] = _max_rss_bytes() if scorer else None

    report = build_final_report(
        runs=runs,
        provenance=provenance,
        expected_cases=args.expected_cases,
        required_runs=3,
    )
    json_path = args.results_dir / f"{run_id}-phase-c-generator-benchmark.json"
    markdown_path = args.results_dir / f"{run_id}-phase-c-generator-benchmark.md"
    _atomic_write_json(json_path, report)
    markdown_path.write_text(
        _render_markdown(report),
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "evidence_class": report["evidence_class"],
                "report_json": str(json_path),
                "report_markdown": str(markdown_path),
                "aggregate": report["aggregate"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if report["evidence_class"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
