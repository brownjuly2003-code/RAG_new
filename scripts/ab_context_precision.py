#!/usr/bin/env python3
"""Q1 offline A/B: context_precision knob grid on the 100-case aircargo harness.

Audit `docs/audits/audit_grok_16_07_26.md` (Q1 / §7.2 / §7.3): the free-RAGAS baseline
(`reports/ragas/20260605T214926Z-e728353a-aircargo-ragas.md`) measures
context_precision ~0.51 (weak звено — top-k шумит) while context_recall ~0.92
(отлично). The audit's product bet is a *measured* A/B over the three retrieval
knobs it named — rerank top-k, parent-window expansion (chars), and the
grade_docs CRAG filter — on the SAME 100 cases, to cut top-k noise WITHOUT
losing recall. This is NOT a new retrieval strategy.

Design — the expensive stage runs ONCE:
  * the BGE-M3 embed + bge-reranker-v2-m3 rerank pass is produced by the existing
    `scripts/ab_remote_contextual.py --stage pools/rerank --arm C` (production
    chunking: structural + contextual headers). Its output
    `.tmp/ab_candidates_phase2_C.json` is the full reranked candidate pool per
    case (retrieval_top_k in reranked order).
  * every grid arm is then CHEAP post-processing over that single pool:
      - rerank_k  -> slice `cands[:k]`;
      - parent-window (window, max_chars) -> reuse the production
        `HybridRetriever._expand_parents` (pure text, no models);
      - grade_docs on/off -> reuse the production `agent.graph.make_grade_docs_node`
        (LLM CRAG filter; external-mistral, opt-in via --with-grade).
  * metrics reuse the existing RAGAS code path
    (`evaluation.ragas_eval.context_precision` / `context_recall`) plus the cheap
    keyword FULL/PART/MISS regression guard (`ab_remote_contextual._kw_status`).

So the DEFAULT sweep needs NO LLM at all — only the one embed+rerank pass is
heavy. The external-mistral key is required only for the opt-in grade arms
(--with-grade) and the opt-in faithfulness/answer_relevancy judge (--with-judge),
following the same external-mistral convention the RAGAS baseline used.

All project imports are lazy (module import loads nothing heavy). Nothing here
downloads or runs a model on its own; the heavy embed+rerank happens only in the
`ab_remote_contextual` subprocess launched by --build-pool (Mac/Colab only).

GR-0.3 (stream GR baseline) reuses the same pool and the same metric code path
to report context precision / recall and the FULL/PART/MISS keyword status per
question class, joined onto the T-11 sidecar. It changes no retrieval
behaviour — it is measurement of the pool as it already is — and runs on
Windows with no model and no network:
  python scripts/ab_context_precision.py --buckets

Smoke (Windows, no models):
  python scripts/ab_context_precision.py --mock --stub-grade \
      --results-dir .tmp/q1_smoke

Heavy run — ONE command on Mac (see the run-doc
`docs/operations/2026-07-18-q1-context-precision-ab-plan.md`):
  set -a && . /tmp/mk.env && set +a && \
  RAG_DEVICE=mps RAG_EMBED_BATCH=8 RAG_RERANK_BATCH=8 \
  LLM_PROVIDER_PROFILE=external-mistral OLLAMA_REQUEST_TIMEOUT_SEC=120 \
  .venv/bin/python scripts/ab_context_precision.py --build-pool \
      --with-grade --with-judge --results-dir reports/ragas
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Grid definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Arm:
    """One A/B arm = a knob combination applied to the shared reranked pool."""

    name: str
    rerank_k: int
    window: int          # parent-expansion sections per side (0 = expansion off)
    max_chars: int       # parent-expansion text cap
    grade: bool          # apply the grade_docs CRAG filter (external-mistral)
    note: str = ""

    @property
    def expand_key(self) -> tuple[int, int]:
        return (self.window, self.max_chars)


# Production defaults (config/settings.py): rerank_top_k=5, parent_expansion on
# window=2 / max_chars=3600, grade_docs is the Level-2 CRAG node. Arm "prod" ==
# the D2 baseline (FULL 96 / PART 3 / MISS 1 on the keyword metric).
#
# Grid = one-factor-at-a-time around prod + two combined-precision arms + two
# opt-in grade arms (8 total; the 6 deterministic arms always run, the 2 grade
# arms only with --with-grade). Rationale: rerank_k↓ and expansion↓ both drop
# low-rank / diluting text -> precision↑, with recall as the guard rail.
DEFAULT_GRID: list[Arm] = [
    Arm("prod",            rerank_k=5, window=2, max_chars=3600, grade=False,
        note="current production baseline (D2)"),
    Arm("k3",              rerank_k=3, window=2, max_chars=3600, grade=False,
        note="tighter top-k: fewer docs, precision up, recall risk"),
    Arm("k8",              rerank_k=8, window=2, max_chars=3600, grade=False,
        note="wider top-k: recall headroom check"),
    Arm("no-expand",       rerank_k=5, window=0, max_chars=0,    grade=False,
        note="expansion off: isolates the precision cost of parent-window"),
    Arm("light-expand",    rerank_k=5, window=1, max_chars=2400, grade=False,
        note="conservative expansion (settings rollback config)"),
    Arm("k3-light-expand", rerank_k=3, window=1, max_chars=2400, grade=False,
        note="combined precision play"),
    Arm("grade",           rerank_k=5, window=2, max_chars=3600, grade=True,
        note="CRAG grade_docs on top of prod (opt-in, external-mistral)"),
    Arm("k3-grade",        rerank_k=3, window=2, max_chars=3600, grade=True,
        note="tighter k + CRAG (opt-in, external-mistral)"),
]

BASELINE_ARM = "prod"


def build_grid(*, with_grade: bool) -> list[Arm]:
    return [a for a in DEFAULT_GRID if with_grade or not a.grade]


# ---------------------------------------------------------------------------
# Row loading (reranked candidate pool from ab_remote_contextual rerank stage)
# ---------------------------------------------------------------------------

def load_rerank_rows(path: Path) -> list[dict[str, Any]]:
    """Load `ab_candidates_phase2_*.json` rows (query, cands, cand_sources, kws)."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected a JSON list of rows")
    return rows


def mock_rows() -> list[dict[str, Any]]:
    """Tiny deterministic pool for the Windows smoke — no models, no corpus.

    Three cases with hand-made reranked candidates so the metrics and the
    FULL/PART/MISS guard exercise every branch. One candidate carries the
    "IRRELEVANT" sentinel so the --stub-grade path can demonstrate filtering
    of a non-top document.
    """
    return [
        {
            "case_id": "mock-full",
            "query": "какие поля нужны для допуска груза",
            "kws": ["поля", "допуск"],
            "cands": [
                "Для допуска груза нужны поля: маркировка и допуск отправителя.",
                "IRRELEVANT кадровый регламент отпусков и больничных листов.",
                "Общие сведения о складской логистике без конкретики.",
                "Дополнительный контекст про поля допуска и проверки.",
            ],
            "cand_sources": ["doc_a.md", "doc_b.md", "doc_c.md", "doc_a.md"],
        },
        {
            "case_id": "mock-part",
            "query": "когда нужен юрист по претензии",
            "kws": ["юрист", "эскалаци"],
            "cands": [
                "Юрист подключается при крупной претензии клиента.",
                "Порядок первичного ответа на претензию без эскалации.",
                "Справочная информация о договорах перевозки.",
            ],
            "cand_sources": ["doc_d.md", "doc_d.md", "doc_e.md"],
        },
        {
            "case_id": "mock-miss",
            "query": "таможенное оформление авиагруза данные",
            "kws": ["таможен", "декларац"],
            "cands": [
                "Складские операции и хранение груза на терминале.",
                "Общие правила приёмки груза без оформления и проверок.",
            ],
            "cand_sources": ["doc_f.md", "doc_g.md"],
        },
    ]


# ---------------------------------------------------------------------------
# Parent-window expansion — reuses production HybridRetriever._expand_parents
# ---------------------------------------------------------------------------

class ParentExpander:
    """Reproduces the arm-C chunk list from the corpus and reuses the production
    `HybridRetriever._expand_parents` to expand top-k candidate texts.

    The chunk reproduction mirrors `ab_remote_contextual.stage_expand`: same
    `select_chunks` + `add_contextual_headers` pipeline, verified 1:1 against the
    Kaggle/Mac stack in the residual-miss diagnosis. No models are loaded here —
    expansion is a pure ingestion-order text lookup.
    """

    def __init__(self, corpus: Path) -> None:
        import os

        # Match the arm-C (production) chunking env before settings are read.
        os.environ.setdefault("RAG_SEMANTIC_CHUNKING", "false")
        os.environ.setdefault("RAG_STRUCTURAL_CHUNKING", "true")

        from config.settings import get_settings
        from ingestion.loader import DocumentLoader
        from vectordb import manager
        from vectordb._base_manager import select_chunks

        settings = get_settings()
        docs = DocumentLoader(recursive=False).load_documents(str(corpus))
        if not docs:
            raise RuntimeError(f"no documents under {corpus}")
        chunks = select_chunks(
            list(docs), None, settings.chunk_size, settings.chunk_overlap, settings=settings
        )
        if getattr(settings, "contextual_headers", False):
            chunks = manager.add_contextual_headers(chunks, docs, chunk_size=settings.chunk_size)
        self._chunks = chunks
        self._text_to_pos: dict[str, int] = {}
        for idx, chunk in enumerate(chunks):
            self._text_to_pos.setdefault(chunk.page_content, idx)
        self._retriever_cache: dict[tuple[int, int], Any] = {}
        self._doc_cls = None
        print(f"[expander] corpus -> {len(chunks)} chunks (arm-C reproduction)", flush=True)

    def _retriever(self, window: int, max_chars: int) -> Any:
        key = (window, max_chars)
        cached = self._retriever_cache.get(key)
        if cached is not None:
            return cached
        from vectordb._base_manager import HybridRetriever

        retriever = HybridRetriever(
            vector_store=None,
            chunks=self._chunks,
            reranker=None,
            use_bm25=False,
            parent_expansion=True,
            parent_expansion_window=window,
            parent_expansion_max_chars=max_chars,
        )
        self._retriever_cache[key] = retriever
        return retriever

    def expand(self, texts: Sequence[str], sources: Sequence[str],
               window: int, max_chars: int) -> list[str]:
        if window <= 0:
            return list(texts)
        from vectordb._base_manager import Document

        selected: list[Any] = []
        for i, text in enumerate(texts):
            pos = self._text_to_pos.get(text)
            if pos is None:
                src = sources[i] if i < len(sources) else "?"
                selected.append(Document(page_content=text, metadata={"source": src}))
            else:
                selected.append(self._chunks[pos])
        expanded = self._retriever(window, max_chars)._expand_parents(selected)
        return [d.page_content for d in expanded]


class NullExpander:
    """Smoke / no-corpus expander: expansion is a no-op (window ignored)."""

    def expand(self, texts: Sequence[str], sources: Sequence[str],
               window: int, max_chars: int) -> list[str]:
        return list(texts)


# ---------------------------------------------------------------------------
# grade_docs CRAG filter — reuses production agent.graph.make_grade_docs_node
# ---------------------------------------------------------------------------

class _StubGradeLLM:
    """Deterministic offline stand-in for the --stub-grade smoke.

    Forces the per-document branch (the batch verdict is left unparseable) and
    marks a document irrelevant only when it carries the IRRELEVANT sentinel, so
    the smoke proves the state->graded_docs plumbing and one real filter drop.
    """

    def __init__(self) -> None:
        self._first = True

    def invoke(self, prompt: str) -> str:
        if self._first:
            self._first = False
            return ""  # unparseable batch verdict -> node falls back to per-doc
        return "NO" if "IRRELEVANT" in prompt else "YES"


class DocGrader:
    """Applies the production grade_docs node to a case's context docs."""

    def __init__(self, llm_factory: Callable[[], Any], tenant_id: str = "aircargo") -> None:
        self._llm_factory = llm_factory
        self._tenant_id = tenant_id

    def grade(self, query: str, texts: Sequence[str], sources: Sequence[str]) -> list[str]:
        from agent.graph import make_grade_docs_node

        context_docs = [
            {
                "page_content": t,
                "metadata": {"source": sources[i] if i < len(sources) else "?"},
            }
            for i, t in enumerate(texts)
        ]
        node = make_grade_docs_node(self._llm_factory())
        state: dict[str, Any] = {
            "question": query,
            "context_docs": context_docs,
            "trace_id": f"q1-ab-grade-{uuid.uuid4().hex[:8]}",
            "tenant_id": self._tenant_id,
        }
        out = node(state)
        graded = out.get("graded_docs") or []
        return [d.get("page_content", "") if isinstance(d, dict) else str(d) for d in graded]


def make_mistral_llm() -> Any:
    """external-mistral judge/grader LLM (same convention as the RAGAS baseline)."""
    from scripts.aircargo_ragas_free import FreeChatLLM

    return FreeChatLLM("mistral", "mistral-small-latest", min_interval_s=1.0)


# ---------------------------------------------------------------------------
# Per-arm evaluation — reuses evaluation.ragas_eval + ab_remote._kw_status
# ---------------------------------------------------------------------------

def final_texts_for_case(
    row: dict[str, Any],
    arm: Arm,
    expander: Any,
    grader: Optional[DocGrader],
) -> list[str]:
    """rerank -> slice top-k -> parent-expand -> (optional) grade filter."""
    cands = list(row.get("cands", []))
    sources = list(row.get("cand_sources", []))
    top_texts = cands[: arm.rerank_k]
    top_sources = sources[: arm.rerank_k]
    expanded = expander.expand(top_texts, top_sources, arm.window, arm.max_chars)
    if arm.grade and grader is not None:
        graded = grader.grade(row.get("query", ""), expanded, top_sources)
        # An empty grade result (LLM failure / everything filtered) would zero the
        # metrics unfairly; keep the pre-grade docs in that degenerate case.
        if graded:
            return graded
    return expanded


def evaluate_arm(
    rows: Sequence[dict[str, Any]],
    arm: Arm,
    expander: Any,
    grader: Optional[DocGrader],
) -> dict[str, Any]:
    from evaluation.ragas_eval import context_precision, context_recall
    from scripts.ab_remote_contextual import _kw_status

    per_case: list[dict[str, Any]] = []
    counts = {"FULL": 0, "PART": 0, "MISS": 0}
    prec_sum = 0.0
    rec_sum = 0.0
    for row in rows:
        query = row.get("query", "")
        kws = list(row.get("kws", []))
        texts = final_texts_for_case(row, arm, expander, grader)
        prec = context_precision(query, texts, kws)
        rec = context_recall(texts, kws)
        status = _kw_status(kws, texts)
        counts[status] += 1
        prec_sum += prec
        rec_sum += rec
        per_case.append({
            "case_id": row.get("case_id"),
            "n_docs": len(texts),
            "context_precision": round(prec, 4),
            "context_recall": round(rec, 4),
            "kw_status": status,
        })
    n = max(len(rows), 1)
    return {
        "arm": arm.name,
        "rerank_k": arm.rerank_k,
        "window": arm.window,
        "max_chars": arm.max_chars,
        "grade": arm.grade,
        "note": arm.note,
        "aggregate": {
            "context_precision": round(prec_sum / n, 4),
            "context_recall": round(rec_sum / n, 4),
            "FULL": counts["FULL"],
            "PART": counts["PART"],
            "MISS": counts["MISS"],
            "num_cases": len(rows),
        },
        "per_case": per_case,
    }


# ---------------------------------------------------------------------------
# SHIP verdict
# ---------------------------------------------------------------------------

@dataclass
class ShipCriteria:
    min_precision_gain: float = 0.05  # absolute mean context_precision lift vs baseline
    recall_floor: float = 0.90        # context_recall must not drop below this
    full_floor: int = 96              # keyword FULL must not regress below D2's 96
    max_miss: int = 1                 # keyword MISS must not exceed D2's 1
    metrics: list[str] = field(default_factory=list)


def verdict_for_arm(
    arm_result: dict[str, Any],
    baseline: dict[str, Any],
    crit: ShipCriteria,
) -> tuple[str, str]:
    if arm_result["arm"] == baseline["arm"]:
        return ("BASELINE", "reference arm")
    agg = arm_result["aggregate"]
    base = baseline["aggregate"]
    gain = agg["context_precision"] - base["context_precision"]
    reasons: list[str] = []
    ok = True
    if gain < crit.min_precision_gain:
        ok = False
        reasons.append(f"precision +{gain:.3f} < +{crit.min_precision_gain:.2f}")
    if agg["context_recall"] < crit.recall_floor:
        ok = False
        reasons.append(f"recall {agg['context_recall']:.3f} < {crit.recall_floor:.2f}")
    if agg["FULL"] < crit.full_floor:
        ok = False
        reasons.append(f"FULL {agg['FULL']} < {crit.full_floor}")
    if agg["MISS"] > crit.max_miss:
        ok = False
        reasons.append(f"MISS {agg['MISS']} > {crit.max_miss}")
    if ok:
        return ("SHIP-CANDIDATE", f"precision +{gain:.3f}, recall {agg['context_recall']:.3f}")
    return ("no-ship", "; ".join(reasons))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Q1 context_precision A/B — {report['run_id']}",
        "",
        f"- Created at: `{report['created_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Rerank pool: `{report['rerank_artifact']}`",
        f"- Cases: `{report['num_cases']}`",
        f"- Baseline arm: `{report['baseline_arm']}`",
        "",
        "SHIP criteria: context_precision gain ≥ "
        f"{report['ship_criteria']['min_precision_gain']:.2f} vs baseline; "
        f"context_recall ≥ {report['ship_criteria']['recall_floor']:.2f}; "
        f"keyword FULL ≥ {report['ship_criteria']['full_floor']}; "
        f"MISS ≤ {report['ship_criteria']['max_miss']}. NO-SHIP is a valid outcome.",
        "",
        "| arm | rerank_k | window/max_chars | grade | ctx_precision | Δ vs base | ctx_recall | FULL | PART | MISS | verdict |",
        "|---|---:|---|:---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    base_prec = report["arms"][0]["aggregate"]["context_precision"]
    for arm in report["arms"]:
        agg = arm["aggregate"]
        delta = agg["context_precision"] - base_prec
        win = f"{arm['window']}/{arm['max_chars']}" if arm["window"] else "off"
        lines.append(
            f"| {arm['arm']} | {arm['rerank_k']} | {win} | "
            f"{'on' if arm['grade'] else '—'} | {agg['context_precision']:.4f} | "
            f"{delta:+.4f} | {agg['context_recall']:.4f} | {agg['FULL']} | "
            f"{agg['PART']} | {agg['MISS']} | {arm['verdict']} ({arm['verdict_reason']}) |"
        )
    lines.extend(["", "## Notes per arm", ""])
    for arm in report["arms"]:
        lines.append(f"- **{arm['arm']}** — {arm['note']}")
    if report.get("judge"):
        lines.extend(["", "## Judge (external-mistral, opt-in)", ""])
        lines.append("| arm | faithfulness | answer_relevancy |")
        lines.append("|---|---:|---:|")
        for name, jr in report["judge"].items():
            lines.append(f"| {name} | {jr['faithfulness']:.4f} | {jr['answer_relevancy']:.4f} |")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(report: dict[str, Any], results_dir: Path) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{report['run_id']}-q1-context-precision-ab"
    json_path = results_dir / f"{stem}.json"
    md_path = results_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


# ---------------------------------------------------------------------------
# Optional judge layer (faithfulness / answer_relevancy) — opt-in, mistral
# ---------------------------------------------------------------------------

def run_judge(
    rows: Sequence[dict[str, Any]],
    arm: Arm,
    expander: Any,
    grader: Optional[DocGrader],
    llm: Any,
) -> dict[str, float]:
    """Generate answers from the arm's contexts and judge them (reuses the
    RAGAS baseline generator + RAGEvaluator, external-mistral)."""
    from evaluation.ragas_eval import RAGEvaluator
    from evaluation.ragas_eval import TestCase as RAGTestCase
    from scripts.aircargo_ragas_free import _generate_answer

    rag_cases: list[Any] = []
    answers: list[str] = []
    contexts: list[list[dict[str, Any]]] = []
    for row in rows:
        texts = final_texts_for_case(row, arm, expander, grader)
        try:
            ans = _generate_answer(llm, row.get("query", ""), texts)
        except Exception:  # noqa: BLE001 - one bad case must not kill the judge
            ans = ""
        rag_cases.append(RAGTestCase(
            question=row.get("query", ""), expected_keywords=list(row.get("kws", [])),
            category="aircargo",
        ))
        answers.append(ans)
        contexts.append([{"page_content": t, "metadata": {}} for t in texts])
    result = RAGEvaluator(eval_llm=llm).evaluate_batch(rag_cases, answers=answers,
                                                       context_docs_list=contexts)
    agg = result["aggregate"]
    return {"faithfulness": agg["faithfulness"], "answer_relevancy": agg["answer_relevancy"]}


# ---------------------------------------------------------------------------
# Heavy embed+rerank pool build (Mac/Colab only) via ab_remote_contextual
# ---------------------------------------------------------------------------

def build_pool(out_dir: Path, arm: str = "C") -> Path:
    """Run the existing two-process embed+rerank stages (models never co-resident)."""
    script = str(PROJECT_ROOT / "scripts" / "ab_remote_contextual.py")
    for stage in ("pools", "rerank"):
        cmd = [sys.executable, script, "--stage", stage, "--arm", arm, "--out-dir", str(out_dir)]
        print(f"[build-pool] $ {' '.join(cmd)}", flush=True)
        rc = subprocess.run(cmd, check=False).returncode
        if rc != 0:
            raise RuntimeError(f"ab_remote_contextual --stage {stage} failed (rc={rc})")
    artifact = out_dir / f"ab_candidates_phase2_{arm}.json"
    if not artifact.exists():
        raise RuntimeError(f"expected rerank artifact missing: {artifact}")
    return artifact


# ---------------------------------------------------------------------------
# GR-0.3 — the phase C baseline, split by question class
# ---------------------------------------------------------------------------
#
# `docs/specs/retrieval-buckets.md` asks for one retrieval number per question
# class over a pinned pool. Nothing here changes retrieval: it post-processes
# the same reranked pool the phase C.1a benchmark consumed, through the same
# code path (`scripts.generator_benchmark.load_benchmark_cases` slices the pool
# and caps the context; `evaluation.ragas_eval` computes the two metrics), and
# joins the T-11 question-class sidecar onto it by `case_id`. The aggregate is
# therefore expected to reproduce the published 0.5067 / 0.9050 exactly; if it
# does not, the harness is not measuring what phase C measured.

BUCKET_REPORT_SCHEMA_VERSION = "gr-bucket-baseline/v1.0"
STRUCTURAL_GRAPH_REPORT_SCHEMA_VERSION = "gr-structure-graph-retrieval/v1.0"
ENTITY_GRAPH_REPORT_SCHEMA_VERSION = "gr-entity-graph-retrieval/v1.0"
DEFAULT_BUCKET_REPORT_PATH = PROJECT_ROOT / "reports" / "gr" / "gr0-bucket-baseline.json"
DEFAULT_GR2_REPORT_PATH = PROJECT_ROOT / "reports" / "gr" / "gr2-entity-graph.json"
DEFAULT_DATASET_PATH = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
DEFAULT_SIDECAR_PATH = PROJECT_ROOT / "evaluation" / "curated_cases_question_class.jsonl"
DEFAULT_LABEL_MANIFEST_PATH = (
    PROJECT_ROOT / "evaluation" / "curated_cases_question_class.manifest.json"
)
DEFAULT_CORPUS_MANIFEST_PATH = PROJECT_ROOT / "evaluation" / "aircargo_corpus.manifest.json"
DEFAULT_MULTI_DOC_DATASET_PATH = (
    PROJECT_ROOT / "evaluation" / "curated_cases_aircargo_gr_multihop.jsonl"
)
DEFAULT_MULTI_DOC_SIDECAR_PATH = (
    PROJECT_ROOT / "evaluation" / "curated_cases_aircargo_gr_multihop_question_class.jsonl"
)
DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH = (
    PROJECT_ROOT / "evaluation" / "curated_cases_aircargo_gr_multihop_question_class.manifest.json"
)

#: Phase C.1a sliced each pool row at its own `rerank_k` (5 for all 100 cases)
#: and capped the joined context at 6000 characters, with no parent expansion.
#: Those two numbers are what make this report the same ruler.
PHASE_C_TOP_K = 5
PHASE_C_CONTEXT_CHARS = 6000

#: Every file that decides the published number. Their digests travel with the
#: report, so it stays verifiable independently of which commit is HEAD.
BUCKET_CODE_PATHS: tuple[str, ...] = (
    "scripts/ab_context_precision.py",
    "scripts/generator_benchmark.py",
    "scripts/ab_remote_contextual.py",
    "evaluation/ragas_eval.py",
    "evaluation/question_class_labels.py",
)

STRUCTURAL_GRAPH_CODE_PATHS: tuple[str, ...] = (
    *BUCKET_CODE_PATHS,
    "vectordb/_base_manager.py",
    "ingestion/structure_graph.py",
    "ingestion/structure_graph_projection.py",
)

ENTITY_GRAPH_CODE_PATHS: tuple[str, ...] = (
    *STRUCTURAL_GRAPH_CODE_PATHS,
    "ingestion/entity_extraction.py",
    "ingestion/entity_normalization.py",
    "ingestion/entity_graph.py",
    "ingestion/entity_retrieval.py",
    "llm/providers/pinned_ollama.py",
    "evaluation/query_classification.py",
)

_EMPTY_CELL = "—"

_BASELINE_POOL_PRODUCER = (
    "scripts/ab_remote_contextual.py --stage pools/rerank --arm C "
    "(BGE-M3 + bge-reranker-v2-m3, production chunking)"
)
_STRUCTURAL_GRAPH_POOL_PRODUCER = (
    "scripts/ab_remote_contextual.py --stage pools/rerank --arm G1 "
    "(BGE-M3 + bge-reranker-v2-m3, structural chunking + exact category "
    "prefilter + structural graph coherence/expansion)"
)
_ENTITY_GRAPH_POOL_PRODUCER = (
    "scripts/ab_remote_contextual.py --stage pools/rerank --arm G2 "
    "(BGE-M3 + bge-reranker-v2-m3, structural graph + entity graph lane)"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _stored_path(path: Path) -> str:
    """Repo-relative POSIX path, or a stable placeholder for anything outside.

    An absolute path on this laptop is not provenance; it is noise that makes
    two machines disagree byte for byte.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return f"<external>/{resolved.name}"


def _git_commit() -> dict[str, Any]:
    """HEAD and whether the tree was clean when the report was produced."""
    def _git(*args: str) -> Optional[str]:
        try:
            out = subprocess.run(
                ["git", "-C", str(PROJECT_ROOT), *args],
                check=False, capture_output=True, text=True,
            )
        except OSError:
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "commit": commit or "unknown",
        "tree_clean": None if status is None else status == "",
    }


def _code_digests(paths: Sequence[str] = BUCKET_CODE_PATHS) -> dict[str, str]:
    return {
        rel: sha256_file(PROJECT_ROOT / rel)
        for rel in paths
        if (PROJECT_ROOT / rel).is_file()
    }


def score_cases_by_class(
    *,
    pool_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    expected_cases: int,
    top_k: int,
    context_chars: int,
    allow_short_contexts: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """One scored row per case, carrying its question class, plus the approval count.

    The join goes through `load_classified_cases`, so the run refuses to start
    when the sidecar's pinned dataset digest disagrees with the dataset.
    """
    from evaluation.question_class_labels import load_classified_cases
    from evaluation.ragas_eval import context_precision, context_recall
    from scripts.ab_remote_contextual import _kw_status
    from scripts.generator_benchmark import load_benchmark_cases

    classified = load_classified_cases(
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        manifest_path=label_manifest_path,
    )
    class_by_case = {case.case_id: case.label.question_class.value for case in classified}
    approved = sum(1 for case in classified if case.label.approved_by is not None)

    cases = load_benchmark_cases(
        dataset_path=dataset_path,
        contexts_path=pool_path,
        expected_cases=expected_cases,
        top_k=top_k,
        context_chars=context_chars,
        allow_short_contexts=allow_short_contexts,
    )

    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        texts = list(case["contexts"])
        docs = [{"page_content": text} for text in texts]
        keywords = list(case["expected_keywords"])
        rows.append({
            "case_id": case_id,
            "question_class": class_by_case[case_id],
            "n_docs": len(texts),
            "context_precision": round(context_precision(case["query"], docs, keywords), 4),
            "context_recall": round(context_recall(docs, keywords), 4),
            "kw_status": _kw_status(keywords, texts),
        })
    return rows, approved


def _bucket_row(question_class: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Metrics for one class. A class with no cases reports null, never 0.0."""
    counts = {status: 0 for status in ("FULL", "PART", "MISS")}
    for row in rows:
        counts[row["kw_status"]] += 1
    n = len(rows)
    return {
        "question_class": question_class,
        "num_cases": n,
        "context_precision": (
            round(sum(r["context_precision"] for r in rows) / n, 4) if n else None
        ),
        "context_recall": (
            round(sum(r["context_recall"] for r in rows) / n, 4) if n else None
        ),
        "FULL": counts["FULL"],
        "PART": counts["PART"],
        "MISS": counts["MISS"],
    }


def _label_block(approved: int) -> dict[str, Any]:
    return {
        "evidence_class": "agent_labelled",
        "approved": approved,
        "case_source": "agent_authored_over_real_documents",
        "note": (
            "The questions were agent-authored over real documents and the "
            "question classes are agent-assigned; no human has approved either."
        ),
    }


def _provenance_block(
    *,
    pool_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    corpus_manifest_path: Path,
    code_commit: str | None,
    config: dict[str, Any],
    pool_produced_by: str = _BASELINE_POOL_PRODUCER,
    code_paths: Sequence[str] = BUCKET_CODE_PATHS,
) -> dict[str, Any]:
    """Everything that pins a published number, minus the number itself.

    Shared by the GR-0.3 bucket baseline and the GR-1a arm so the two reports
    cannot describe the same pool in two different vocabularies. Only ``config``
    differs between them.
    """
    corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    code = _git_commit() if code_commit is None else {"commit": code_commit, "tree_clean": None}
    code["files"] = _code_digests(code_paths)
    return {
        "pool_path": _stored_path(pool_path),
        "pool_sha256": sha256_file(pool_path),
        "pool_bytes": pool_path.stat().st_size,
        "pool_produced_by": pool_produced_by,
        "dataset": _stored_path(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "label_sidecar": _stored_path(sidecar_path),
        "label_sidecar_sha256": sha256_file(sidecar_path),
        "label_manifest": _stored_path(label_manifest_path),
        "label_manifest_sha256": sha256_file(label_manifest_path),
        "corpus": {
            "manifest": _stored_path(corpus_manifest_path),
            "manifest_sha256": sha256_file(corpus_manifest_path),
            "name": corpus_manifest.get("name"),
            "root": corpus_manifest.get("root"),
            "corpus_sha256": corpus_manifest.get("corpus_sha256"),
            "file_count": corpus_manifest.get("file_count"),
        },
        "code": code,
        "config": config,
    }


def _bucket_rows_by_class(scored: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per known question class, in a fixed order, empty classes included."""
    from evaluation.question_class_labels import QUESTION_CLASSES

    by_class: dict[str, list[dict[str, Any]]] = {name: [] for name in sorted(QUESTION_CLASSES)}
    for row in scored:
        by_class.setdefault(row["question_class"], []).append(row)
    return [_bucket_row(name, by_class[name]) for name in sorted(by_class)]


def _g2_case_id(row: dict[str, Any]) -> str:
    return str(row.get("case_id") or "?")


def _numeric_pool_value(value: Any, *, field: str, case_id: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"G2 pool has invalid {field} for case {case_id}")
    return value


def _load_g2_pool_meta(
    *,
    pool_meta_path: Path | None,
    dataset_path: Path,
    pool_rows: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Read T-24's sidecar and prove it belongs to these routed pool rows."""
    if pool_meta_path is None:
        raise ValueError("G2 pool requires pool_meta_path")
    meta = json.loads(pool_meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError("G2 pool meta must be a JSON object")

    dataset_digest = sha256_file(dataset_path)
    meta_digest = meta.get("cases_sha256")
    if meta_digest != dataset_digest:
        raise ValueError(
            "G2 pool meta cases_sha256="
            f"{meta_digest!r} differs from dataset_sha256={dataset_digest!r}"
        )

    routed_counts: dict[str, int] = {}
    for row in pool_rows:
        routed = row.get("routed_question_class")
        if not isinstance(routed, str) or not routed:
            raise ValueError(f"G2 pool requires routed_question_class for case {_g2_case_id(row)}")
        routed_counts[routed] = routed_counts.get(routed, 0) + 1
    routed_counts = dict(sorted(routed_counts.items()))
    meta_counts = meta.get("routed_class_counts")
    if meta_counts != routed_counts:
        raise ValueError(
            "G2 pool meta routed_class_counts="
            f"{meta_counts!r} differs from pool routed_class_counts={routed_counts!r}"
        )
    return meta, routed_counts


def _validate_g2_pool_rows(pool_rows: Sequence[dict[str, Any]]) -> None:
    for row in pool_rows:
        case_id = _g2_case_id(row)
        if row.get("graph_postprocessed") is not True:
            raise ValueError(f"G2 pool requires graph_postprocessed=true for case {case_id}")
        routed = row.get("routed_question_class")
        if not isinstance(routed, str) or not routed:
            raise ValueError(f"G2 pool requires routed_question_class for case {case_id}")
        candidates = _numeric_pool_value(
            row.get("entity_candidates"),
            field="entity_candidates",
            case_id=case_id,
        )
        if int(candidates) != candidates or candidates < 0 or candidates > 50:
            raise ValueError(
                "G2 pool entity_candidates must be an integer from 0 to 50 for case "
                f"{case_id}: {candidates}"
            )
        hops = _numeric_pool_value(row.get("entity_hops"), field="entity_hops", case_id=case_id)
        if int(hops) != hops or hops < 0 or hops > 2:
            raise ValueError(
                f"G2 pool entity_hops must be an integer from 0 to 2 for case {case_id}: {hops}"
            )
        timing = row.get("timing_ms")
        if not isinstance(timing, dict):
            raise ValueError(f"G2 pool requires timing_ms for case {case_id}")
        for timing_field in ("vector", "bm25", "entity"):
            _numeric_pool_value(
                timing.get(timing_field),
                field=f"timing_ms.{timing_field}",
                case_id=case_id,
            )
        rerank_s = row.get("rerank_s")
        if isinstance(rerank_s, bool) or not isinstance(rerank_s, (int, float)):
            raise ValueError(f"rerank_s missing for case {case_id} arm G2")


def _nearest_rank(
    values: Sequence[float | int], *, numerator: int, denominator: int
) -> float | int:
    """Nearest-rank percentile; every selected value is an input pool value."""
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, ((len(ordered) * numerator + denominator - 1) // denominator) - 1)
    return ordered[index]


def _g2_latency(
    pool_rows: Sequence[dict[str, Any]],
) -> dict[str, dict[str, float | int | None]]:
    from scripts.ab_remote_contextual import _ENTITY_QUESTION_CLASSES

    entity_lane_ms = [
        row["timing_ms"]["entity"]
        for row in pool_rows
        if row["routed_question_class"] in _ENTITY_QUESTION_CLASSES
    ]
    retrieve_ms = [
        round(
            row["timing_ms"]["vector"] + row["timing_ms"]["bm25"] + row["timing_ms"]["entity"],
            4,
        )
        for row in pool_rows
    ]
    rerank_s = [row["rerank_s"] for row in pool_rows]

    def _summary(values: Sequence[float | int]) -> dict[str, float | int]:
        return {
            "cases": len(values),
            "p50": _nearest_rank(values, numerator=1, denominator=2),
            "p95": _nearest_rank(values, numerator=19, denominator=20),
            "max": max(values) if values else 0,
        }

    return {
        "entity_lane_ms": {
            "cases": len(entity_lane_ms),
            "p50": _nearest_rank(entity_lane_ms, numerator=1, denominator=2)
            if entity_lane_ms
            else None,
            "p95": _nearest_rank(entity_lane_ms, numerator=19, denominator=20)
            if entity_lane_ms
            else None,
            "max": max(entity_lane_ms) if entity_lane_ms else None,
        },
        "retrieve_ms": _summary(retrieve_ms),
        "rerank_s": _summary(rerank_s),
    }


def _g2_meta_provenance(pool_meta_path: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """Copy T-24's stable names verbatim, plus the digest of the sidecar itself."""
    required = (
        "cases_sha256",
        "graph_chunks_sha256",
        "entities_manifest_sha256",
        "classifications_manifest_sha256",
        "structure_graph_digest",
        "node_counts",
        "edge_counts",
        "projection_build_s",
        "peak_rss_bytes",
        "routed_class_counts",
        "rejected_chunk_ids",
        "rejected_count",
    )
    missing = [field for field in required if field not in meta]
    if missing:
        raise ValueError(f"G2 pool meta missing required field(s): {', '.join(missing)}")
    return {
        "pool_meta_path": _stored_path(pool_meta_path),
        "pool_meta_sha256": sha256_file(pool_meta_path),
        **{field: meta[field] for field in required},
    }


def build_bucket_report(
    *,
    pool_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    corpus_manifest_path: Path,
    expected_cases: int = 100,
    top_k: int = PHASE_C_TOP_K,
    context_chars: int = PHASE_C_CONTEXT_CHARS,
    code_commit: str | None = None,
    pool_arm: str = "C",
    pool_meta_path: Path | None = None,
) -> dict[str, Any]:
    """The GR-0.3 report: per-class and aggregate retrieval metrics over a pinned pool.

    Deterministic by construction — the body carries no timestamp, so two runs
    over the same inputs are byte-identical.
    """
    if pool_arm not in {"C", "G1", "G2"}:
        raise ValueError(f"unsupported retrieval pool arm: {pool_arm!r}")

    scored, approved = score_cases_by_class(
        pool_path=pool_path,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path,
        expected_cases=expected_cases,
        top_k=top_k,
        context_chars=context_chars,
        allow_short_contexts=pool_arm in {"G1", "G2"},
    )

    pool_rows = json.loads(pool_path.read_text(encoding="utf-8"))
    pool_diagnostics: dict[str, Any] | None = None
    g2_meta: dict[str, Any] | None = None
    routed_counts: dict[str, int] | None = None
    if pool_arm == "G1":
        unprocessed = [
            str(row.get("case_id") or "?")
            for row in pool_rows
            if row.get("graph_postprocessed") is not True
        ]
        if unprocessed:
            raise ValueError(
                "G1 pool requires graph_postprocessed=true for every row; "
                f"missing for {len(unprocessed)} case(s): {unprocessed[:5]}"
            )
        pool_diagnostics = {
            "row_count": len(pool_rows),
            "graph_postprocessed_count": len(pool_rows),
            "graph_prefiltered_count": sum(
                row.get("graph_prefiltered") is True for row in pool_rows
            ),
        }
    elif pool_arm == "G2":
        from scripts.ab_remote_contextual import _ENTITY_QUESTION_CLASSES

        _validate_g2_pool_rows(pool_rows)
        g2_meta, routed_counts = _load_g2_pool_meta(
            pool_meta_path=pool_meta_path,
            dataset_path=dataset_path,
            pool_rows=pool_rows,
        )
        routed_by_case = {_g2_case_id(row): str(row["routed_question_class"]) for row in pool_rows}
        for row in scored:
            row["routed_question_class"] = routed_by_case[row["case_id"]]
        pool_diagnostics = {
            "row_count": len(pool_rows),
            "graph_postprocessed_count": len(pool_rows),
            "graph_prefiltered_count": sum(
                row.get("graph_prefiltered") is True for row in pool_rows
            ),
            "routed_class_counts": routed_counts,
            "entity_lane_cases": sum(
                row["routed_question_class"] in _ENTITY_QUESTION_CLASSES for row in pool_rows
            ),
            "entity_candidates_max": max(
                (row["entity_candidates"] for row in pool_rows),
                default=0,
            ),
            "entity_hops_max": max((row["entity_hops"] for row in pool_rows), default=0),
        }

    config: dict[str, Any] = {
        "top_k": top_k,
        "pool_rerank_k": sorted({int(row.get("rerank_k") or 0) for row in pool_rows}),
        "context_chars": context_chars,
        "parent_expansion": False,
        "grade_docs": False,
        "context_builder": "scripts.generator_benchmark.load_benchmark_cases",
        "metrics": (
            "evaluation.ragas_eval.context_precision / context_recall "
            "(keyword, the phase C code path)"
        ),
        "kw_status": "scripts.ab_remote_contextual._kw_status",
        "rounding": "per case to 4 decimals, then the mean, then 4 decimals",
    }
    if pool_arm == "G1":
        config.update(
            {
                "pool_arm": "G1",
                "allow_short_contexts": True,
                "category_prefilter": "exact available case labels",
                "section_coherence": "production structural graph",
                "section_expansion": "same-section structural graph boundary",
            }
        )
    elif pool_arm == "G2":
        config.update(
            {
                "pool_arm": "G2",
                "allow_short_contexts": True,
                "entity_candidates_limit": 50,
                "entity_hops_limit": 2,
                "section_coherence": "production structural graph",
                "section_expansion": "same-section structural graph boundary",
            }
        )

    report = {
        "schema_version": (
            ENTITY_GRAPH_REPORT_SCHEMA_VERSION
            if pool_arm == "G2"
            else (
                STRUCTURAL_GRAPH_REPORT_SCHEMA_VERSION
                if pool_arm == "G1"
                else BUCKET_REPORT_SCHEMA_VERSION
            )
        ),
        "kind": (
            "gr-entity-graph-retrieval"
            if pool_arm == "G2"
            else (
                "gr-structure-graph-retrieval"
                if pool_arm == "G1"
                else "gr-retrieval-bucket-baseline"
            )
        ),
        "evidence_class": "measured",
        "labels": _label_block(approved),
        "provenance": _provenance_block(
            pool_path=pool_path,
            dataset_path=dataset_path,
            sidecar_path=sidecar_path,
            label_manifest_path=label_manifest_path,
            corpus_manifest_path=corpus_manifest_path,
            code_commit=code_commit,
            config=config,
            pool_produced_by=(
                _ENTITY_GRAPH_POOL_PRODUCER
                if pool_arm == "G2"
                else (
                    _STRUCTURAL_GRAPH_POOL_PRODUCER if pool_arm == "G1" else _BASELINE_POOL_PRODUCER
                )
            ),
            code_paths=(
                ENTITY_GRAPH_CODE_PATHS
                if pool_arm == "G2"
                else (STRUCTURAL_GRAPH_CODE_PATHS if pool_arm == "G1" else BUCKET_CODE_PATHS)
            ),
        ),
        "buckets": _bucket_rows_by_class(scored),
        "aggregate": _bucket_row("all cases", scored) | {"question_class": "all cases"},
        "per_case": scored,
    }
    if pool_diagnostics is not None:
        report["pool_diagnostics"] = pool_diagnostics
    if pool_arm == "G2":
        assert g2_meta is not None and pool_meta_path is not None
        report["provenance"]["pool_meta"] = _g2_meta_provenance(pool_meta_path, g2_meta)
        report["latency"] = _g2_latency(pool_rows)
    return report


def _metric_cell(value: Optional[float]) -> str:
    return _EMPTY_CELL if value is None else f"{value:.4f}"


def render_bucket_table(report: dict[str, Any]) -> str:
    """The printed table. Every class row carries its case count, always."""
    provenance = report["provenance"]
    title = (
        "GR-2 entity graph retrieval by question class"
        if report["kind"] == "gr-entity-graph-retrieval"
        else (
            "GR-1b structural graph retrieval by question class"
            if report["kind"] == "gr-structure-graph-retrieval"
            else "GR-0.3 retrieval baseline by question class"
        )
    )
    lines = [
        title,
        f"Pool: {provenance['pool_path']} sha256 {provenance['pool_sha256']}",
        f"Corpus: {provenance['corpus']['corpus_sha256']} "
        f"({provenance['corpus']['file_count']} files)",
        f"Dataset: {provenance['dataset_sha256']}",
        f"Labels: {report['labels']['evidence_class']}, "
        f"{report['labels']['approved']} approved",
        f"Config: top_k={provenance['config']['top_k']} "
        f"context_chars={provenance['config']['context_chars']} "
        f"parent_expansion={provenance['config']['parent_expansion']}",
        "",
        "| question class | cases | ctx precision | ctx recall | FULL | PART | MISS |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in [*report["buckets"], report["aggregate"]]:
        lines.append(
            f"| {row['question_class']} | {row['num_cases']} | "
            f"{_metric_cell(row['context_precision'])} | "
            f"{_metric_cell(row['context_recall'])} | "
            f"{row['FULL']} | {row['PART']} | {row['MISS']} |"
        )
    return "\n".join(lines) + "\n"


def write_bucket_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def run_bucket_report(args: argparse.Namespace) -> int:
    report = build_bucket_report(
        pool_path=Path(args.rerank_artifact),
        dataset_path=Path(args.dataset),
        sidecar_path=Path(args.sidecar),
        label_manifest_path=Path(args.label_manifest),
        corpus_manifest_path=Path(args.corpus_manifest),
        expected_cases=args.expected_cases,
        top_k=args.top_k,
        context_chars=args.context_chars,
        pool_arm=args.pool_arm,
        pool_meta_path=Path(args.pool_meta) if args.pool_meta else None,
    )
    out = write_bucket_report(report, Path(args.bucket_report))
    print(render_bucket_table(report), end="", flush=True)
    print(
        json.dumps(
            {
                "status": "ok",
                "report_json": _stored_path(out),
                "num_cases": report["aggregate"]["num_cases"],
                "context_precision": report["aggregate"]["context_precision"],
                "context_recall": report["aggregate"]["context_recall"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def _comparison_rows_by_case(report: dict[str, Any], *, arm: str) -> dict[str, dict[str, Any]]:
    rows = report.get("per_case")
    if not isinstance(rows, list):
        raise ValueError(f"{arm} report has no per_case rows")
    by_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id") or "?")
        if case_id in by_case:
            raise ValueError(f"{arm} report repeats case id {case_id}")
        by_case[case_id] = row
    return by_case


def _comparison_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    bucket = _bucket_row("", rows)
    return {
        "context_precision": bucket["context_precision"],
        "context_recall": bucket["context_recall"],
        "FULL": bucket["FULL"],
        "PART": bucket["PART"],
        "MISS": bucket["MISS"],
    }


def _metric_delta(g1: float | None, g2: float | None) -> float | None:
    return round(g2 - g1, 4) if g1 is not None and g2 is not None else None


def _comparison_bucket(
    *,
    question_class: str,
    g1_rows: Sequence[dict[str, Any]],
    g2_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    g1 = _comparison_metrics(g1_rows)
    g2 = _comparison_metrics(g2_rows)
    return {
        "question_class": question_class,
        "num_cases": len(g1_rows),
        "G1": g1,
        "G2": g2,
        "context_precision_delta": _metric_delta(
            g1["context_precision"],
            g2["context_precision"],
        ),
        "context_recall_delta": _metric_delta(g1["context_recall"], g2["context_recall"]),
    }


def _comparison_same_input(g1_report: dict[str, Any], g2_report: dict[str, Any]) -> None:
    if g1_report.get("kind") != "gr-structure-graph-retrieval":
        raise ValueError(f"G1 report kind differs: {g1_report.get('kind')!r}")
    if g2_report.get("kind") != "gr-entity-graph-retrieval":
        raise ValueError(f"G2 report kind differs: {g2_report.get('kind')!r}")
    g1_provenance = g1_report["provenance"]
    g2_provenance = g2_report["provenance"]
    checks = (
        ("dataset digest", g1_provenance["dataset_sha256"], g2_provenance["dataset_sha256"]),
        (
            "label sidecar digest",
            g1_provenance["label_sidecar_sha256"],
            g2_provenance["label_sidecar_sha256"],
        ),
        (
            "corpus digest",
            g1_provenance["corpus"]["corpus_sha256"],
            g2_provenance["corpus"]["corpus_sha256"],
        ),
        (
            "top_k",
            g1_provenance["config"]["top_k"],
            g2_provenance["config"]["top_k"],
        ),
        (
            "context_chars",
            g1_provenance["config"]["context_chars"],
            g2_provenance["config"]["context_chars"],
        ),
    )
    for name, g1_value, g2_value in checks:
        if g1_value != g2_value:
            raise ValueError(f"{name} differs: G1={g1_value!r} G2={g2_value!r}")


def _require_rerank_seconds(
    *,
    values: dict[str, float | int] | None,
    case_ids: Sequence[str],
    arm: str,
) -> dict[str, float | int]:
    if values is None:
        raise ValueError(f"rerank_s missing for case {case_ids[0] if case_ids else '?'} arm {arm}")
    checked: dict[str, float | int] = {}
    for case_id in case_ids:
        value = values.get(case_id)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"rerank_s missing for case {case_id} arm {arm}")
        checked[case_id] = value
    return checked


def build_arm_comparison(
    g1_report: dict[str, Any],
    g2_report: dict[str, Any],
    *,
    g1_rerank_s: dict[str, float | int] | None = None,
    g2_rerank_s: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    """Compare the two graph arms after proving that their ruler is identical."""
    _comparison_same_input(g1_report, g2_report)
    g1_by_case = _comparison_rows_by_case(g1_report, arm="G1")
    g2_by_case = _comparison_rows_by_case(g2_report, arm="G2")
    if set(g1_by_case) != set(g2_by_case):
        raise ValueError(
            "case ids differ: "
            f"only G1={sorted(set(g1_by_case) - set(g2_by_case))[:5]} "
            f"only G2={sorted(set(g2_by_case) - set(g1_by_case))[:5]}"
        )
    case_ids = sorted(g1_by_case)
    g1_rerank = _require_rerank_seconds(values=g1_rerank_s, case_ids=case_ids, arm="G1")
    g2_rerank = _require_rerank_seconds(values=g2_rerank_s, case_ids=case_ids, arm="G2")

    report_classes = [str(row["question_class"]) for row in g1_report.get("buckets", [])]
    classes = list(dict.fromkeys(report_classes))
    for question_class in sorted({str(row["question_class"]) for row in g1_by_case.values()}):
        if question_class not in classes:
            classes.append(question_class)
    buckets: list[dict[str, Any]] = []
    for question_class in classes:
        g1_rows = [
            g1_by_case[case_id]
            for case_id in case_ids
            if g1_by_case[case_id]["question_class"] == question_class
        ]
        g2_rows = [g2_by_case[row["case_id"]] for row in g1_rows]
        buckets.append(
            _comparison_bucket(
                question_class=question_class,
                g1_rows=g1_rows,
                g2_rows=g2_rows,
            )
        )

    transitions: dict[str, dict[str, Any]] = {}
    downgrades: list[dict[str, str]] = []
    keyword_losses: list[str] = []
    downgrade_transitions = {"FULL->PART", "FULL->MISS", "PART->MISS"}
    for case_id in case_ids:
        g1_row = g1_by_case[case_id]
        g2_row = g2_by_case[case_id]
        transition = f"{g1_row['kw_status']}->{g2_row['kw_status']}"
        entry = transitions.setdefault(transition, {"count": 0, "case_ids": []})
        entry["count"] += 1
        entry["case_ids"].append(case_id)
        if g2_row["context_recall"] < g1_row["context_recall"]:
            keyword_losses.append(case_id)
        if transition in downgrade_transitions:
            downgrades.append(
                {
                    "case_id": case_id,
                    "question_class": str(g1_row["question_class"]),
                    "routed_question_class": str(g2_row["routed_question_class"]),
                    "transition": transition,
                }
            )

    aggregate = _comparison_bucket(
        question_class="all cases",
        g1_rows=[g1_by_case[case_id] for case_id in case_ids],
        g2_rows=[g2_by_case[case_id] for case_id in case_ids],
    )
    by_class = {row["question_class"]: row for row in buckets}
    rerank_deltas = [round(g2_rerank[case_id] - g1_rerank[case_id], 4) for case_id in case_ids]
    g2_meta = g2_report["provenance"]["pool_meta"]
    return {
        "buckets": buckets,
        "aggregate": aggregate,
        "keyword_transitions": dict(sorted(transitions.items())),
        "keyword_loss_case_ids": keyword_losses,
        "downgrades": downgrades,
        "precision_deltas": {
            "single_hop": by_class.get("single_hop", {}).get("context_precision_delta"),
            "multi_hop": by_class.get("multi_hop", {}).get("context_precision_delta"),
        },
        "cost": {
            "G2_entity_search_ms": {
                "cases": g2_report["latency"]["entity_lane_ms"]["cases"],
                "p50": g2_report["latency"]["entity_lane_ms"]["p50"],
                "p95": g2_report["latency"]["entity_lane_ms"]["p95"],
            },
            "paired_rerank_s_delta": {
                "p50": _nearest_rank(rerank_deltas, numerator=1, denominator=2),
                "p95": _nearest_rank(rerank_deltas, numerator=19, denominator=20),
            },
            "G2_peak_rss_bytes": g2_meta["peak_rss_bytes"],
        },
    }


def _rerank_seconds_from_pool(pool_path: Path, *, arm: str) -> dict[str, float | int]:
    rows = json.loads(pool_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{arm} pool must be a JSON array")
    values: dict[str, float | int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{arm} pool has a non-object row")
        case_id = _g2_case_id(row)
        value = row.get("rerank_s")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"rerank_s missing for case {case_id} arm {arm}")
        values[case_id] = value
    return values


def _non_lane_parity(g1_pool_path: Path, g2_pool_path: Path) -> dict[str, Any]:
    """List G2's non-lane candidate differences without rejecting a report."""
    from scripts.ab_remote_contextual import _ENTITY_QUESTION_CLASSES

    g1_rows = json.loads(g1_pool_path.read_text(encoding="utf-8"))
    g2_rows = json.loads(g2_pool_path.read_text(encoding="utf-8"))
    g1_by_case = {str(row["case_id"]): row for row in g1_rows}
    non_lane_rows = [
        row for row in g2_rows if row["routed_question_class"] not in _ENTITY_QUESTION_CLASSES
    ]
    divergent_case_ids = sorted(
        str(row["case_id"])
        for row in non_lane_rows
        if g1_by_case[str(row["case_id"])].get("cands") != row.get("cands")
    )
    return {"cases": len(non_lane_rows), "divergent_case_ids": divergent_case_ids}


def _gr2_pair(
    *,
    g1_pool_path: Path,
    g2_pool_path: Path,
    g2_pool_meta_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    corpus_manifest_path: Path,
    expected_cases: int,
    top_k: int,
    context_chars: int,
    code_commit: str | None,
) -> dict[str, Any]:
    g1 = build_bucket_report(
        pool_path=g1_pool_path,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path,
        corpus_manifest_path=corpus_manifest_path,
        expected_cases=expected_cases,
        top_k=top_k,
        context_chars=context_chars,
        code_commit=code_commit,
        pool_arm="G1",
    )
    g2 = build_bucket_report(
        pool_path=g2_pool_path,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path,
        corpus_manifest_path=corpus_manifest_path,
        expected_cases=expected_cases,
        top_k=top_k,
        context_chars=context_chars,
        code_commit=code_commit,
        pool_arm="G2",
        pool_meta_path=g2_pool_meta_path,
    )
    comparison = build_arm_comparison(
        g1,
        g2,
        g1_rerank_s=_rerank_seconds_from_pool(g1_pool_path, arm="G1"),
        g2_rerank_s=_rerank_seconds_from_pool(g2_pool_path, arm="G2"),
    )
    comparison["non_lane_parity"] = _non_lane_parity(g1_pool_path, g2_pool_path)
    return {
        "G1": g1,
        "G2": g2,
        "comparison": comparison,
    }


def _gr2_inputs_provenance(pair: dict[str, Any]) -> dict[str, Any]:
    g1 = pair["G1"]["provenance"]
    g2 = pair["G2"]["provenance"]
    return {
        "G1": {"pool_path": g1["pool_path"], "pool_sha256": g1["pool_sha256"]},
        "G2": {
            "pool_path": g2["pool_path"],
            "pool_sha256": g2["pool_sha256"],
            "pool_meta": g2["pool_meta"],
        },
        "dataset_sha256": g1["dataset_sha256"],
        "label_sidecar_sha256": g1["label_sidecar_sha256"],
        "label_manifest_sha256": g1["label_manifest_sha256"],
        "corpus": g1["corpus"],
    }


def build_gr2_report(
    *,
    g1_pool_path: Path,
    g2_pool_path: Path,
    g2_pool_meta_path: Path,
    bucket_g1_pool_path: Path,
    bucket_g2_pool_path: Path,
    bucket_g2_pool_meta_path: Path,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    sidecar_path: Path = DEFAULT_SIDECAR_PATH,
    label_manifest_path: Path = DEFAULT_LABEL_MANIFEST_PATH,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    bucket_dataset_path: Path = DEFAULT_MULTI_DOC_DATASET_PATH,
    bucket_sidecar_path: Path = DEFAULT_MULTI_DOC_SIDECAR_PATH,
    bucket_label_manifest_path: Path = DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH,
    bucket_corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    expected_cases: int = 100,
    bucket_expected_cases: int = 15,
    top_k: int = PHASE_C_TOP_K,
    context_chars: int = PHASE_C_CONTEXT_CHARS,
    code_commit: str | None = None,
) -> dict[str, Any]:
    """Bundle phase C and the supplemental multi-document GR-2 comparisons."""
    phase_c = _gr2_pair(
        g1_pool_path=g1_pool_path,
        g2_pool_path=g2_pool_path,
        g2_pool_meta_path=g2_pool_meta_path,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path,
        corpus_manifest_path=corpus_manifest_path,
        expected_cases=expected_cases,
        top_k=top_k,
        context_chars=context_chars,
        code_commit=code_commit,
    )
    multi_doc_bucket = _gr2_pair(
        g1_pool_path=bucket_g1_pool_path,
        g2_pool_path=bucket_g2_pool_path,
        g2_pool_meta_path=bucket_g2_pool_meta_path,
        dataset_path=bucket_dataset_path,
        sidecar_path=bucket_sidecar_path,
        label_manifest_path=bucket_label_manifest_path,
        corpus_manifest_path=bucket_corpus_manifest_path,
        expected_cases=bucket_expected_cases,
        top_k=top_k,
        context_chars=context_chars,
        code_commit=code_commit,
    )
    code = _git_commit() if code_commit is None else {"commit": code_commit, "tree_clean": None}
    code["files"] = _code_digests(ENTITY_GRAPH_CODE_PATHS)
    return {
        "schema_version": ENTITY_GRAPH_REPORT_SCHEMA_VERSION,
        "kind": "gr-entity-graph-retrieval",
        "evidence_class": "measured",
        "provenance": {
            "phase_c": _gr2_inputs_provenance(phase_c),
            "multi_doc_bucket": _gr2_inputs_provenance(multi_doc_bucket),
            "code": code,
            "config": {
                "top_k": top_k,
                "context_chars": context_chars,
                "graph_retrieval_default": "unchanged",
            },
        },
        "phase_c": phase_c,
        "multi_doc_bucket": multi_doc_bucket,
    }


def write_gr2_report(report: dict[str, Any], path: Path) -> Path:
    return write_bucket_report(report, path)


def _render_gr2_comparison(name: str, pair: dict[str, Any]) -> list[str]:
    comparison = pair["comparison"]
    lines = [
        f"GR-2 entity graph retrieval comparison: {name}",
        "| labelled class | cases | G1 precision | G2 precision | delta | G1 recall | G2 recall | delta | G1 FULL/PART/MISS | G2 FULL/PART/MISS |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in [*comparison["buckets"], comparison["aggregate"]]:
        g1 = row["G1"]
        g2 = row["G2"]
        lines.append(
            f"| {row['question_class']} | {row['num_cases']} | "
            f"{_metric_cell(g1['context_precision'])} | {_metric_cell(g2['context_precision'])} | "
            f"{_metric_cell(row['context_precision_delta'])} | "
            f"{_metric_cell(g1['context_recall'])} | {_metric_cell(g2['context_recall'])} | "
            f"{_metric_cell(row['context_recall_delta'])} | "
            f"{g1['FULL']}/{g1['PART']}/{g1['MISS']} | "
            f"{g2['FULL']}/{g2['PART']}/{g2['MISS']} |"
        )
    for arm, arm_report in (("G1", pair["G1"]), ("G2", pair["G2"])):
        count = arm_report["pool_diagnostics"]["graph_prefiltered_count"]
        total = arm_report["pool_diagnostics"]["row_count"]
        lines.append(f"{arm} graph_prefiltered=true: {count}/{total}")
        if count:
            lines.append(
                "NOTE: /api/ask passes no categories to the graph lane; these cases differ "
                "from the product call."
            )
    g2_diagnostics = pair["G2"]["pool_diagnostics"]
    lines.append(f"G2 routed class counts: {g2_diagnostics['routed_class_counts']}")
    lines.append(
        "G2 entity lane: "
        f"{g2_diagnostics['entity_lane_cases']} cases, "
        f"candidates max={g2_diagnostics['entity_candidates_max']}, "
        f"hops max={g2_diagnostics['entity_hops_max']}"
    )
    cost = comparison["cost"]
    entity_search = cost["G2_entity_search_ms"]
    if entity_search["cases"] == 0:
        entity_search_text = "no entity-lane cases"
    else:
        entity_search_text = (
            f"{entity_search['cases']} lane cases, p50={entity_search['p50']} ms "
            f"p95={entity_search['p95']} ms"
        )
    lines.append(
        "Cost: G2 entity-search "
        f"{entity_search_text}; paired rerank_s delta "
        f"p50={cost['paired_rerank_s_delta']['p50']} s "
        f"p95={cost['paired_rerank_s_delta']['p95']} s"
    )
    peak_rss_bytes = cost["G2_peak_rss_bytes"]
    if peak_rss_bytes is None:
        lines.append("G2 peak_rss_bytes: null (MiB unavailable)")
    else:
        lines.append(
            f"G2 peak_rss_bytes: {peak_rss_bytes} ({peak_rss_bytes / (1024 * 1024):.2f} MiB)"
        )
    non_lane_parity = comparison["non_lane_parity"]
    divergent_case_ids = non_lane_parity["divergent_case_ids"]
    lines.append(
        "G2 non-lane parity with G1: "
        f"{len(divergent_case_ids)} divergent of {non_lane_parity['cases']} cases"
    )
    if divergent_case_ids:
        lines.append(f"G2 non-lane divergent case ids: {', '.join(divergent_case_ids)}")
    transitions = comparison["keyword_transitions"]
    lines.append(
        "Keyword transitions: "
        + ", ".join(
            f"{transition}: {details['count']}"
            for transition, details in sorted(transitions.items())
        )
    )
    keyword_losses = comparison["keyword_loss_case_ids"]
    lines.append(
        "Keyword loss case ids: " + (", ".join(keyword_losses) if keyword_losses else "none")
    )
    if comparison["downgrades"]:
        lines.append("Keyword downgrades:")
        for item in comparison["downgrades"]:
            lines.append(
                f"- {item['case_id']}: {item['transition']} "
                f"(labelled={item['question_class']}, routed={item['routed_question_class']})"
            )
    return lines


def render_gr2_table(report: dict[str, Any]) -> str:
    """Render both comparisons for the GR-2 capsule without adding a timestamp."""
    lines = _render_gr2_comparison("phase_c", report["phase_c"])
    lines.append("")
    lines.extend(_render_gr2_comparison("multi_doc_bucket", report["multi_doc_bucket"]))
    return "\n".join(lines) + "\n"


def run_gr2_report(args: argparse.Namespace) -> int:
    report = build_gr2_report(
        g1_pool_path=Path(args.g1_pool),
        g2_pool_path=Path(args.g2_pool),
        g2_pool_meta_path=Path(args.g2_pool_meta),
        bucket_g1_pool_path=Path(args.bucket_g1_pool),
        bucket_g2_pool_path=Path(args.bucket_g2_pool),
        bucket_g2_pool_meta_path=Path(args.bucket_g2_pool_meta),
        dataset_path=Path(args.dataset),
        sidecar_path=Path(args.sidecar),
        label_manifest_path=Path(args.label_manifest),
        corpus_manifest_path=Path(args.corpus_manifest),
        bucket_dataset_path=Path(args.bucket_dataset),
        bucket_sidecar_path=Path(args.bucket_sidecar),
        bucket_label_manifest_path=Path(args.bucket_label_manifest),
        bucket_corpus_manifest_path=Path(args.bucket_corpus_manifest),
        expected_cases=args.expected_cases,
        bucket_expected_cases=args.bucket_expected_cases,
        top_k=args.top_k,
        context_chars=args.context_chars,
    )
    out = write_gr2_report(report, Path(args.gr2_out))
    print(render_gr2_table(report), end="", flush=True)
    print(
        json.dumps(
            {
                "status": "ok",
                "report_json": _stored_path(out),
                "graph_retrieval_default": "unchanged",
            },
            ensure_ascii=False,
        )
    )
    return 0


# ---------------------------------------------------------------------------
# GR-1a — section coherence as a narrowing arm over the same pinned pool
# ---------------------------------------------------------------------------
#
# `plan_06_09_26.md` §4 п.3–4: candidates are grouped by document and section
# (the heading path); a chunk whose section is already represented in the top is
# promoted over an isolated semantic neighbour; the isolated neighbour below a
# threshold is dropped rather than re-ranked; parent-expansion follows the
# section boundary instead of a fixed ±1 window.
#
# The structural signal is already in the pool: every candidate string starts
# with the contextual header the production ingest wrote
# (`vectordb.manager.add_contextual_headers` -> the no-LLM fallback in
# `vectordb._base_manager.add_contextual_headers`), so the arm is post-processing
# over the T-12 pool and needs no model and no corpus.

SECTION_COHERENCE_SCHEMA_VERSION = "gr-section-coherence-arm/v1.0"
DEFAULT_SECTION_COHERENCE_REPORT_PATH = (
    PROJECT_ROOT / "reports" / "gr" / "gr1a-section-coherence.json"
)

#: The producer's format, one constant per separator. These mirror
#: `vectordb._base_manager.add_contextual_headers`, which writes
#: ``[Контекст: Из документа <source>, раздел: <h1> › <h2>…, стр. <page>]\n<body>``
#: and clamps the header to 200 characters. `tests/test_section_coherence_arm.py`
#: builds its fixtures by calling that producer, so a drift in either direction
#: fails there rather than quietly changing what this arm measures.
CONTEXT_HEADER_PREFIX = "[Контекст: "
CONTEXT_HEADER_SUFFIX = "]"
HEADER_DOCUMENT_PREFIX = "Из документа "
HEADER_SECTION_SEPARATOR = ", раздел: "
HEADER_HEADING_JOINER = " › "
HEADER_PAGE_SEPARATOR = ", стр. "

#: The producer's own clamp: `vectordb._base_manager.add_contextual_headers` cuts
#: the header to this many characters before wrapping it in the prefix/suffix. A
#: clamped header still *parses* — the wrapper always appends the suffix — but its
#: heading path is cut mid-text, so two sections of one document that share a
#: 200-character prefix would group as one. That is invisible in the section key,
#: so it is counted and reported instead.
CONTEXT_HEADER_CLAMP = 200

#: The swept parameter. A singleton section survives when its strength — its
#: reciprocal-rank score over the neighbourhood, divided by the strongest
#: section's — is at least this. 0.00 drops nothing and is the control.
SECTION_COHERENCE_THRESHOLDS: tuple[float, ...] = (0.00, 0.10, 0.25, 0.50, 0.75)

#: How deep into the reranked pool "the top" reaches when section support is
#: counted. 5 is the published top-k itself (the arm may only re-order and
#: drop); 10 is twice it (the arm may also pull a supported chunk up into the
#: top-5). Both are published; neither is chosen after seeing the result.
SECTION_COHERENCE_NEIGHBOURHOODS: tuple[int, ...] = (5, 10)

#: A cell qualifies when it costs no keyword coverage; among those, the headline
#: is the one with the highest context precision. Stated before the run, and
#: applied to the whole grid — the grid is published either way.
SECTION_COHERENCE_SELECTION_RULE = (
    "the grid cell with the highest aggregate context precision among the cells "
    "whose keyword FULL is not below the baseline's and whose MISS is not above "
    "it; if no cell qualifies, there is no headline and the grid is the result"
)

_KW_STATUS_ORDER = {"FULL": 2, "PART": 1, "MISS": 0}


@dataclass(frozen=True)
class SectionRef:
    """The (document, heading path) pair the contextual header names."""

    document: str
    heading_path: tuple[str, ...]

    def label(self) -> str:
        path = HEADER_HEADING_JOINER.join(self.heading_path)
        return f"{self.document} :: {path}" if path else f"{self.document} :: <no heading>"


def parse_contextual_header(text: str) -> Optional[SectionRef]:
    """Read the producer's header off a candidate, or return ``None``.

    ``None`` means "this candidate does not carry the header the production
    ingest writes" — an LLM-authored header, a chunk from another pipeline, or a
    truncated string. It never means "sectionless": a chunk from a document with
    no markdown headings parses fine and gets an empty heading path.
    """
    if not text.startswith(CONTEXT_HEADER_PREFIX):
        return None
    newline = text.find("\n")
    if newline == -1:
        return None
    header = text[len(CONTEXT_HEADER_PREFIX) : newline]
    if not header.endswith(CONTEXT_HEADER_SUFFIX):
        return None
    header = header[: -len(CONTEXT_HEADER_SUFFIX)]
    if not header.startswith(HEADER_DOCUMENT_PREFIX):
        return None
    body = header[len(HEADER_DOCUMENT_PREFIX) :]
    # The producer appends the page marker last, so it is stripped from the
    # right — and only when what follows it cannot be a heading: no further
    # heading joiner, and a tail that can actually *be* a page number, because
    # the producer writes the marker only for a chunk whose metadata carries a
    # page (`vectordb/_base_manager.py`: ``if page:``). Without the digit test a
    # heading of the producer's own like "Приложение 2, стр. 12 и далее" loses
    # its tail and gets a silently wrong section key. The one case the header
    # format cannot resolve is a last heading ending in the separator plus bare
    # digits: that string is byte-identical to one the producer writes with page
    # metadata, so the page reading wins — see the fixture in
    # `tests/test_section_coherence_arm.py`.
    head, page_sep, tail = body.rpartition(HEADER_PAGE_SEPARATOR)
    if page_sep and head and HEADER_HEADING_JOINER not in tail and tail.strip().isdigit():
        body = head
    document, section_sep, section = body.partition(HEADER_SECTION_SEPARATOR)
    if not section_sep:
        return SectionRef(document=document.strip(), heading_path=())
    path = tuple(part.strip() for part in section.split(HEADER_HEADING_JOINER) if part.strip())
    return SectionRef(document=document.strip(), heading_path=path)


def header_is_clamped(text: str) -> bool:
    """True when the candidate's header sits exactly on the producer's clamp.

    The clamp truncates the header body, never the wrapper, so the length that
    identifies it is the body's — ``CONTEXT_HEADER_CLAMP`` characters between the
    prefix and the suffix. A header that long parses, but its heading path may be
    cut mid-text, and the section key is then a truncated path.
    """
    if not text.startswith(CONTEXT_HEADER_PREFIX):
        return False
    newline = text.find("\n")
    if newline == -1:
        return False
    header = text[len(CONTEXT_HEADER_PREFIX) : newline]
    if not header.endswith(CONTEXT_HEADER_SUFFIX):
        return False
    return len(header) - len(CONTEXT_HEADER_SUFFIX) == CONTEXT_HEADER_CLAMP


def group_candidates_by_section(
    candidates: Sequence[str],
) -> tuple[dict[SectionRef, list[int]], list[int]]:
    """Group candidate ranks by (document, section); return the unreadable ranks too.

    Two chunks of one section of one document land in one group; two same-named
    sections of different documents stay apart, because the document is part of
    the key. Candidates whose header cannot be read are returned separately and
    are in no group — merging them would invent a section that does not exist.
    """
    groups: dict[SectionRef, list[int]] = {}
    unparsed: list[int] = []
    for rank, text in enumerate(candidates):
        ref = parse_contextual_header(str(text))
        if ref is None:
            unparsed.append(rank)
            continue
        groups.setdefault(ref, []).append(rank)
    return groups, unparsed


@dataclass(frozen=True)
class CoherenceParams:
    """Every knob of the arm, named. None of them has a default in the report."""

    neighbourhood: int = 10
    singleton_threshold: float = 0.25
    top_k: int = PHASE_C_TOP_K
    expand_to_section: bool = True
    context_chars: int = PHASE_C_CONTEXT_CHARS

    def as_dict(self) -> dict[str, Any]:
        return {
            "neighbourhood": self.neighbourhood,
            "singleton_threshold": round(self.singleton_threshold, 4),
            "top_k": self.top_k,
            "expand_to_section": self.expand_to_section,
            "context_chars": self.context_chars,
        }


@dataclass(frozen=True)
class CoherenceOutcome:
    """What the arm selected, and what it did to get there."""

    texts: list[str]
    promoted: int  # candidates in a section with support in the neighbourhood
    demoted: int  # isolated neighbours kept, but below the supported ones
    dropped: int  # isolated neighbours below the threshold
    unparsed: int  # headers the producer's format does not explain
    sectionless: int  # chunks of a document with no markdown headings
    expanded: int  # selected chunks joined to a sibling from their section
    not_expandable: int  # selected chunks whose section has no sibling in the pool
    rank0_dropped: bool  # the reranker's first choice did not survive


def _strip_contextual_header(text: str) -> str:
    """The production strip, so a joined section is not a wall of headers."""
    from vectordb._base_manager import HybridRetriever

    return HybridRetriever._strip_contextual_header(text)


def apply_section_coherence(candidates: Sequence[str], params: CoherenceParams) -> CoherenceOutcome:
    """Narrow a case's candidate pool by section coherence. Pure function.

    Ordering is ordinal, not a weighted score: a candidate whose section is
    represented more than once in the neighbourhood outranks one whose header
    could not be read, which outranks an isolated neighbour. Inside each tier
    the reranker's own order is preserved — the arm narrows the top, it does not
    re-score it.
    """
    pool = [str(text) for text in candidates]
    neighbourhood = pool[: params.neighbourhood]
    groups, unparsed_ranks = group_candidates_by_section(neighbourhood)
    unparsed = set(unparsed_ranks)
    ref_by_rank: dict[int, SectionRef] = {
        rank: ref for ref, ranks in groups.items() for rank in ranks
    }

    # A section's pull on the top: reciprocal rank summed over its members, so
    # two chunks at ranks 1 and 2 outweigh one chunk at rank 4.
    scores = {ref: sum(1.0 / (1 + rank) for rank in ranks) for ref, ranks in groups.items()}
    strongest = max(scores.values(), default=0.0)

    tier_supported, tier_unreadable, tier_isolated = 0, 1, 2
    ordered: list[tuple[int, int]] = []
    promoted = demoted = dropped = 0
    rank0_dropped = False
    for rank in range(len(neighbourhood)):
        if rank in unparsed:
            ordered.append((tier_unreadable, rank))
            continue
        ref = ref_by_rank[rank]
        if len(groups[ref]) > 1:
            promoted += 1
            ordered.append((tier_supported, rank))
            continue
        strength = scores[ref] / strongest if strongest else 0.0
        if strength < params.singleton_threshold:
            dropped += 1
            rank0_dropped = rank0_dropped or rank == 0
            continue
        demoted += 1
        ordered.append((tier_isolated, rank))
    ordered.sort()
    selected = [rank for _, rank in ordered][: params.top_k]

    texts, expanded, not_expandable = _expand_to_section_boundary(
        pool, neighbourhood, selected, ref_by_rank, params
    )
    return CoherenceOutcome(
        texts=texts,
        promoted=promoted,
        demoted=demoted,
        dropped=dropped,
        unparsed=len(unparsed),
        sectionless=sum(1 for ref in ref_by_rank.values() if not ref.heading_path),
        expanded=expanded,
        not_expandable=not_expandable,
        rank0_dropped=rank0_dropped,
    )


def _expand_to_section_boundary(
    pool: Sequence[str],
    neighbourhood: Sequence[str],
    selected: Sequence[int],
    ref_by_rank: dict[int, SectionRef],
    params: CoherenceParams,
) -> tuple[list[str], int, int]:
    """Join each selected chunk to the rest of its section, as far as the pool has it.

    The pool holds only what retrieval returned, so "the section boundary" is
    reachable exactly when a sibling chunk of the same (document, section) was
    itself retrieved. Where it was not, the chunk is left alone and counted in
    ``not_expandable`` — this arm cannot read the corpus, and pretending it can
    would be the ±1 window under another name.
    """
    if not params.expand_to_section:
        return [neighbourhood[rank] for rank in selected], 0, 0

    pool_refs = [parse_contextual_header(text) for text in pool]
    # The neighbourhood is a prefix of the pool, so a selected rank indexes both.
    taken = set(selected)
    used: set[int] = set()
    texts: list[str] = []
    expanded = not_expandable = 0
    for rank in selected:
        text = neighbourhood[rank]
        ref = ref_by_rank.get(rank)
        if ref is None:
            texts.append(text)
            continue
        siblings = [
            index
            for index, candidate_ref in enumerate(pool_refs)
            if candidate_ref == ref and index not in used and index not in taken
        ]
        if not siblings:
            not_expandable += 1
            texts.append(text)
            continue
        used.update(siblings)
        expanded += 1
        parts = [text] + [_strip_contextual_header(pool[index]).strip() for index in siblings]
        texts.append("\n\n".join(part for part in parts if part))
    return texts, expanded, not_expandable


def _score_arm_cases(
    cases: Sequence[dict[str, Any]],
    class_by_case: dict[str, str],
    params: CoherenceParams,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Run the arm over every case and score it with the phase C metric code path."""
    from evaluation.ragas_eval import context_precision, context_recall
    from scripts.ab_remote_contextual import _kw_status
    from scripts.generator_benchmark import _truncate_contexts

    rows: list[dict[str, Any]] = []
    diagnostics = {
        "promoted": 0,
        "demoted": 0,
        "dropped": 0,
        "expanded": 0,
        "not_expandable": 0,
        "cases_with_a_drop": 0,
        "cases_with_the_top_candidate_dropped": 0,
        # No section in this case's neighbourhood holds more than one candidate,
        # so the arm has no structural signal to promote on and can only drop.
        # This is the property of the pool that decides how much the arm can move
        # at all, and the capsule quotes it, so it is a reported number.
        "cases_with_all_singleton_sections": 0,
        # `_truncate_contexts` spends ONE shared character budget in order, so for
        # a case whose selected chunks reach that budget the arm's re-ordering
        # decides what survives — re-ordering alone can then move keyword coverage.
        # The control cell's equality with the baseline rests on this count being
        # zero, so it is a reported number and not an assumption: a pool where a
        # case does reach the budget makes it non-zero and fails the control test
        # instead of quietly invalidating the reasoning behind it.
        "cases_at_the_truncation_budget": 0,
        "docs_selected": 0,
    }
    for case in cases:
        outcome = apply_section_coherence(case["contexts"], params)
        texts = _truncate_contexts(outcome.texts, params.context_chars)
        at_budget = (
            params.context_chars > 0
            and sum(len(text) for text in outcome.texts) > params.context_chars
        )
        docs = [{"page_content": text} for text in texts]
        keywords = list(case["expected_keywords"])
        case_id = str(case["case_id"])
        rows.append(
            {
                "case_id": case_id,
                "question_class": class_by_case[case_id],
                "n_docs": len(texts),
                "context_precision": round(context_precision(case["query"], docs, keywords), 4),
                "context_recall": round(context_recall(docs, keywords), 4),
                "kw_status": _kw_status(keywords, texts),
                "dropped": outcome.dropped,
            }
        )
        diagnostics["promoted"] += outcome.promoted
        diagnostics["demoted"] += outcome.demoted
        diagnostics["dropped"] += outcome.dropped
        diagnostics["expanded"] += outcome.expanded
        diagnostics["not_expandable"] += outcome.not_expandable
        diagnostics["cases_with_a_drop"] += 1 if outcome.dropped else 0
        diagnostics["cases_with_the_top_candidate_dropped"] += 1 if outcome.rank0_dropped else 0
        diagnostics["cases_with_all_singleton_sections"] += 1 if outcome.promoted == 0 else 0
        diagnostics["cases_at_the_truncation_budget"] += 1 if at_budget else 0
        diagnostics["docs_selected"] += len(texts)
    diagnostics["mean_docs"] = round(diagnostics["docs_selected"] / max(len(cases), 1), 4)
    return rows, diagnostics


def _naive_top_k_reference(
    *,
    pool_path: Path,
    dataset_path: Path,
    class_by_case: dict[str, str],
    expected_cases: int,
    top_k: int,
    context_chars: int,
) -> list[dict[str, Any]]:
    """The cheapest narrowing there is: keep the first k, drop the rest.

    Section coherence has to be measured against this and not only against the
    baseline, because an arm that ends up with four documents per case must not
    be credited for a gain that "take the top four" already produces. Same pool,
    same cases, same metric code path.
    """
    from evaluation.ragas_eval import context_precision, context_recall
    from scripts.ab_remote_contextual import _kw_status
    from scripts.generator_benchmark import load_benchmark_cases

    reference: list[dict[str, Any]] = []
    for k in range(1, top_k + 1):
        cases = load_benchmark_cases(
            dataset_path=dataset_path,
            contexts_path=pool_path,
            expected_cases=expected_cases,
            top_k=k,
            context_chars=context_chars,
        )
        rows: list[dict[str, Any]] = []
        docs_selected = 0
        for case in cases:
            texts = list(case["contexts"])
            docs = [{"page_content": text} for text in texts]
            keywords = list(case["expected_keywords"])
            case_id = str(case["case_id"])
            docs_selected += len(texts)
            rows.append(
                {
                    "case_id": case_id,
                    "question_class": class_by_case[case_id],
                    "n_docs": len(texts),
                    "context_precision": round(context_precision(case["query"], docs, keywords), 4),
                    "context_recall": round(context_recall(docs, keywords), 4),
                    "kw_status": _kw_status(keywords, texts),
                }
            )
        reference.append(
            {
                "top_k": k,
                "mean_docs": round(docs_selected / max(len(cases), 1), 4),
                "aggregate": _bucket_row("all cases", rows) | {"question_class": "all cases"},
            }
        )
    return reference


def _delta(arm: Optional[float], base: Optional[float]) -> Optional[float]:
    if arm is None or base is None:
        return None
    return round(arm - base, 4)


def _keyword_regressions(
    arm_rows: Sequence[dict[str, Any]], baseline_by_case: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Every case whose FULL/PART/MISS status got worse, named."""
    regressions: list[dict[str, Any]] = []
    for row in arm_rows:
        before = baseline_by_case[row["case_id"]]["kw_status"]
        after = row["kw_status"]
        if _KW_STATUS_ORDER[after] < _KW_STATUS_ORDER[before]:
            regressions.append(
                {
                    "case_id": row["case_id"],
                    "question_class": row["question_class"],
                    "from": before,
                    "to": after,
                }
            )
    return regressions


def build_section_coherence_report(
    *,
    pool_path: Path,
    dataset_path: Path,
    sidecar_path: Path,
    label_manifest_path: Path,
    corpus_manifest_path: Path,
    expected_cases: int = 100,
    top_k: int = PHASE_C_TOP_K,
    context_chars: int = PHASE_C_CONTEXT_CHARS,
    neighbourhoods: Sequence[int] = SECTION_COHERENCE_NEIGHBOURHOODS,
    thresholds: Sequence[float] = SECTION_COHERENCE_THRESHOLDS,
    code_commit: str | None = None,
) -> dict[str, Any]:
    """The GR-1a report: the whole threshold grid beside the GR-0.3 baseline.

    Deterministic by construction, exactly like the baseline it is measured
    against: no timestamp, no run id, no ordering that depends on a dict.
    """
    from scripts.generator_benchmark import load_benchmark_cases

    # `docs/specs/retrieval-buckets.md` requires the published grid to contain a
    # control cell in which the arm provably drops nothing and adds nothing —
    # neighbourhood equal to the reported top-k, threshold 0.0, no expansion. The
    # neighbourhood grid therefore *derives* one value from `top_k` instead of
    # hoping the caller asked for a `top_k` that happens to sit in the declared
    # pair, and a threshold grid without the 0.0 control value is refused loudly
    # rather than published with nothing to prove the arm rejects nothing. With
    # the declared defaults (top_k 5, neighbourhoods 5 and 10) this changes
    # nothing: 5 is already in the grid.
    neighbourhood_grid = sorted({*(int(n) for n in neighbourhoods), int(top_k)})
    threshold_grid = sorted(float(t) for t in thresholds)
    if not any(threshold == 0.0 for threshold in threshold_grid):
        raise ValueError(
            "the threshold grid must contain 0.0: docs/specs/retrieval-buckets.md "
            "requires a published control cell in which the arm provably drops "
            f"nothing and adds nothing, and {threshold_grid} has no such cell"
        )

    baseline_rows, approved = score_cases_by_class(
        pool_path=pool_path,
        dataset_path=dataset_path,
        sidecar_path=sidecar_path,
        label_manifest_path=label_manifest_path,
        expected_cases=expected_cases,
        top_k=top_k,
        context_chars=context_chars,
    )
    baseline_by_case = {row["case_id"]: row for row in baseline_rows}
    class_by_case = {row["case_id"]: row["question_class"] for row in baseline_rows}
    baseline_aggregate = _bucket_row("all cases", baseline_rows) | {"question_class": "all cases"}

    # The arm reads deeper than the published top-5, so the candidates are loaded
    # once at the deepest neighbourhood in the grid and untruncated; the 6000-char
    # cap is applied by the arm afterwards, through the same helper phase C used.
    cases = load_benchmark_cases(
        dataset_path=dataset_path,
        contexts_path=pool_path,
        expected_cases=expected_cases,
        top_k=max(neighbourhood_grid),
        context_chars=0,
    )

    header_parse = _header_parse_stats(cases)

    grid: list[dict[str, Any]] = []
    for neighbourhood in neighbourhood_grid:
        for threshold in threshold_grid:
            for expand in (False, True):
                params = CoherenceParams(
                    neighbourhood=neighbourhood,
                    singleton_threshold=threshold,
                    top_k=top_k,
                    expand_to_section=expand,
                    context_chars=context_chars,
                )
                arm_rows, diagnostics = _score_arm_cases(cases, class_by_case, params)
                aggregate = _bucket_row("all cases", arm_rows) | {"question_class": "all cases"}
                grid.append(
                    {
                        "parameters": params.as_dict(),
                        "is_control": (neighbourhood == top_k and threshold == 0.0 and not expand),
                        "buckets": _bucket_rows_by_class(arm_rows),
                        "aggregate": aggregate,
                        "delta": {
                            "context_precision": _delta(
                                aggregate["context_precision"],
                                baseline_aggregate["context_precision"],
                            ),
                            "context_recall": _delta(
                                aggregate["context_recall"],
                                baseline_aggregate["context_recall"],
                            ),
                            "FULL": aggregate["FULL"] - baseline_aggregate["FULL"],
                            "PART": aggregate["PART"] - baseline_aggregate["PART"],
                            "MISS": aggregate["MISS"] - baseline_aggregate["MISS"],
                        },
                        "diagnostics": diagnostics,
                        "keyword_regressions": _keyword_regressions(arm_rows, baseline_by_case),
                        "per_case": arm_rows,
                    }
                )

    headline = _select_headline(grid, baseline_aggregate)

    # Twenty per-case tables of the same 100 cases is noise, not evidence. The
    # two cells a reader actually audits keep theirs — the control, which proves
    # nothing was rejected, and the headline. Every other cell keeps its full
    # regression list and is reproducible with one command.
    for cell in grid:
        if not cell["is_control"] and cell["parameters"] != headline["parameters"]:
            cell.pop("per_case")

    return {
        "schema_version": SECTION_COHERENCE_SCHEMA_VERSION,
        "kind": "gr-section-coherence-arm",
        "evidence_class": "measured",
        "labels": _label_block(approved),
        "provenance": _provenance_block(
            pool_path=pool_path,
            dataset_path=dataset_path,
            sidecar_path=sidecar_path,
            label_manifest_path=label_manifest_path,
            corpus_manifest_path=corpus_manifest_path,
            code_commit=code_commit,
            config={
                "arm": "section coherence (plan_06_09_26.md §4 п.3–4)",
                "baseline_arm": "GR-0.3 phase C contexts at top-5, no expansion",
                "baseline_report": _stored_path(DEFAULT_BUCKET_REPORT_PATH),
                "top_k": top_k,
                "context_chars": context_chars,
                "neighbourhoods": neighbourhood_grid,
                "thresholds": [round(threshold, 4) for threshold in threshold_grid],
                "expansion": ["off", "section boundary as far as the pool carries it"],
                "grouping": "(document, heading path) parsed from the production contextual header",
                "header_producer": (
                    "vectordb.manager.add_contextual_headers -> "
                    "vectordb._base_manager.add_contextual_headers (no-LLM fallback)"
                ),
                "ordering": (
                    "supported section > unreadable header > isolated neighbour; "
                    "the reranker's order is kept inside each tier"
                ),
                "section_strength": (
                    "sum of 1/(1+rank) over the section's members in the "
                    "neighbourhood, divided by the strongest section's"
                ),
                "context_builder": "scripts.generator_benchmark.load_benchmark_cases",
                "metrics": (
                    "evaluation.ragas_eval.context_precision / context_recall "
                    "(keyword, the phase C code path)"
                ),
                "kw_status": "scripts.ab_remote_contextual._kw_status",
                "rounding": "per case to 4 decimals, then the mean, then 4 decimals",
            },
        ),
        "header_parse": header_parse,
        "baseline": {
            "source": _stored_path(DEFAULT_BUCKET_REPORT_PATH),
            "buckets": _bucket_rows_by_class(baseline_rows),
            "aggregate": baseline_aggregate,
            "per_case": baseline_rows,
        },
        "naive_top_k": {
            "note": (
                "Fixed truncation of the same pool, as the reference every "
                "narrowing arm has to beat: an arm that ends with four documents "
                "per case is not an improvement if 'keep the first four' is. "
                "top_k equal to the baseline's reproduces the baseline exactly."
            ),
            "rows": _naive_top_k_reference(
                pool_path=pool_path,
                dataset_path=dataset_path,
                class_by_case=class_by_case,
                expected_cases=expected_cases,
                top_k=top_k,
                context_chars=context_chars,
            ),
        },
        "grid": grid,
        "headline": headline,
    }


def _header_parse_stats(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """How much of the pool the producer's format actually explains.

    A candidate the parser cannot read is counted here and named by case; it is
    never folded into the sectionless bucket and never dropped by the arm. A
    candidate whose header sits on the producer's clamp is counted too: it parses,
    so it is not 'unparsed', but its heading path may be truncated and its section
    key with it.
    """
    candidates = unparsed = sectionless = clamped = 0
    unparsed_cases: list[str] = []
    for case in cases:
        for text in case["contexts"]:
            candidates += 1
            if header_is_clamped(str(text)):
                clamped += 1
            ref = parse_contextual_header(str(text))
            if ref is None:
                unparsed += 1
                if str(case["case_id"]) not in unparsed_cases:
                    unparsed_cases.append(str(case["case_id"]))
            elif not ref.heading_path:
                sectionless += 1
    return {
        "candidates": candidates,
        "unparsed": unparsed,
        "sectionless": sectionless,
        "clamped": clamped,
        "clamp": CONTEXT_HEADER_CLAMP,
        "unparsed_cases": unparsed_cases,
        "note": (
            "'unparsed' is a header this arm cannot read and therefore does not "
            "group, demote or drop; 'sectionless' is a chunk of a document with "
            "no markdown headings, which is a section of its own; 'clamped' is a "
            "header the producer cut at 'clamp' characters, whose heading path — "
            "and therefore whose section key — may be truncated mid-text."
        ),
    }


def _select_headline(
    grid: Sequence[dict[str, Any]], baseline_aggregate: dict[str, Any]
) -> dict[str, Any]:
    """Apply the stated selection rule to the published grid."""
    qualifying = [
        cell
        for cell in grid
        if cell["aggregate"]["FULL"] >= baseline_aggregate["FULL"]
        and cell["aggregate"]["MISS"] <= baseline_aggregate["MISS"]
    ]
    if not qualifying:
        return {
            "selection_rule": SECTION_COHERENCE_SELECTION_RULE,
            "parameters": None,
            "outcome": (
                "no grid cell held keyword coverage at the baseline, so the arm "
                "has no headline row on this pool"
            ),
        }
    best = max(qualifying, key=lambda cell: cell["aggregate"]["context_precision"])
    return {
        "selection_rule": SECTION_COHERENCE_SELECTION_RULE,
        "parameters": best["parameters"],
        "qualifying_cells": len(qualifying),
        "context_precision": best["aggregate"]["context_precision"],
        "context_recall": best["aggregate"]["context_recall"],
        "delta": best["delta"],
        "outcome": (
            "the best cell that costs no keyword coverage; the whole grid is published beside it"
        ),
    }


def render_section_coherence_table(report: dict[str, Any]) -> str:
    """The printed grid. Precision and coverage never travel apart."""
    provenance = report["provenance"]
    baseline = report["baseline"]["aggregate"]
    lines = [
        "GR-1a section coherence arm over the pinned pool",
        f"Pool: {provenance['pool_path']} sha256 {provenance['pool_sha256']}",
        f"Corpus: {provenance['corpus']['corpus_sha256']} "
        f"({provenance['corpus']['file_count']} files)",
        f"Baseline (GR-0.3): {_metric_cell(baseline['context_precision'])} / "
        f"{_metric_cell(baseline['context_recall'])} "
        f"FULL/PART/MISS {baseline['FULL']}/{baseline['PART']}/{baseline['MISS']}",
        f"Headers: {report['header_parse']['candidates']} candidates, "
        f"{report['header_parse']['unparsed']} unparsed, "
        f"{report['header_parse']['sectionless']} sectionless",
        "",
        "| n | threshold | expand | ctx precision | Δ prec | ctx recall | FULL | PART | MISS |",
        "|---:|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in report["grid"]:
        parameters = cell["parameters"]
        aggregate = cell["aggregate"]
        delta = cell["delta"]["context_precision"]
        lines.append(
            f"| {parameters['neighbourhood']} | "
            f"{parameters['singleton_threshold']:.2f} | "
            f"{'on' if parameters['expand_to_section'] else 'off'} | "
            f"{_metric_cell(aggregate['context_precision'])} | "
            f"{'—' if delta is None else f'{delta:+.4f}'} | "
            f"{_metric_cell(aggregate['context_recall'])} | "
            f"{aggregate['FULL']} | {aggregate['PART']} | {aggregate['MISS']} |"
        )
    lines.extend(
        [
            "",
            "| naive top-k | mean docs | ctx precision | ctx recall | FULL | PART | MISS |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["naive_top_k"]["rows"]:
        aggregate = row["aggregate"]
        lines.append(
            f"| {row['top_k']} | {row['mean_docs']:.2f} | "
            f"{_metric_cell(aggregate['context_precision'])} | "
            f"{_metric_cell(aggregate['context_recall'])} | "
            f"{aggregate['FULL']} | {aggregate['PART']} | {aggregate['MISS']} |"
        )
    headline = report["headline"]
    lines.extend(["", f"Headline: {headline['parameters']}", headline["outcome"]])
    return "\n".join(lines) + "\n"


def run_section_coherence_report(args: argparse.Namespace) -> int:
    report = build_section_coherence_report(
        pool_path=Path(args.rerank_artifact),
        dataset_path=Path(args.dataset),
        sidecar_path=Path(args.sidecar),
        label_manifest_path=Path(args.label_manifest),
        corpus_manifest_path=Path(args.corpus_manifest),
        expected_cases=args.expected_cases,
        top_k=args.top_k,
        context_chars=args.context_chars,
    )
    out = write_bucket_report(report, Path(args.coherence_report))
    print(render_section_coherence_table(report), end="", flush=True)
    print(
        json.dumps(
            {
                "status": "ok",
                "report_json": _stored_path(out),
                "cells": len(report["grid"]),
                "baseline_context_precision": report["baseline"]["aggregate"]["context_precision"],
                "headline": report["headline"]["parameters"],
            },
            ensure_ascii=False,
        )
    )
    return 0


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(
    rows: Sequence[dict[str, Any]],
    *,
    grid: Sequence[Arm],
    expander: Any,
    with_grade: bool,
    stub_grade: bool,
    with_judge: bool,
    mode: str,
    rerank_artifact: str,
) -> dict[str, Any]:
    grader: Optional[DocGrader] = None
    if with_grade:
        if stub_grade:
            grader = DocGrader(_StubGradeLLM)
        else:
            shared = make_mistral_llm()
            grader = DocGrader(lambda: shared)

    arm_results: list[dict[str, Any]] = []
    for arm in grid:
        print(f"[arm] {arm.name} k={arm.rerank_k} win={arm.window}/{arm.max_chars} "
              f"grade={arm.grade}", flush=True)
        arm_results.append(evaluate_arm(rows, arm, expander, grader))

    baseline = next((a for a in arm_results if a["arm"] == BASELINE_ARM), arm_results[0])
    crit = ShipCriteria()
    # baseline first in the table
    arm_results.sort(key=lambda a: (a["arm"] != baseline["arm"], a["arm"]))
    for a in arm_results:
        v, reason = verdict_for_arm(a, baseline, crit)
        a["verdict"] = v
        a["verdict_reason"] = reason

    started = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "run_id": f"{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        "created_at": started.isoformat(),
        "mode": mode,
        "rerank_artifact": rerank_artifact,
        "num_cases": len(rows),
        "baseline_arm": baseline["arm"],
        "ship_criteria": {
            "min_precision_gain": crit.min_precision_gain,
            "recall_floor": crit.recall_floor,
            "full_floor": crit.full_floor,
            "max_miss": crit.max_miss,
        },
        "arms": arm_results,
    }

    if with_judge and not stub_grade:
        llm = make_mistral_llm()
        judge: dict[str, dict[str, float]] = {}
        # judge only the baseline and the best SHIP-candidate (bounded LLM cost)
        candidates = [a for a in arm_results if a["verdict"] == "SHIP-CANDIDATE"]
        best = max(candidates, key=lambda a: a["aggregate"]["context_precision"], default=None)
        judged_arms = [baseline] + ([best] if best is not None else [])
        arm_by_name = {a.name: a for a in grid}
        for a in judged_arms:
            arm = arm_by_name[a["arm"]]
            print(f"[judge] {arm.name}", flush=True)
            judge[arm.name] = run_judge(rows, arm, expander, grader, llm)
        report["judge"] = judge

    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Q1 context_precision knob A/B (offline)")
    p.add_argument("--rerank-artifact",
                   default=str(PROJECT_ROOT / ".tmp" / "ab_candidates_phase2_C.json"),
                   help="reranked candidate pool from ab_remote_contextual for --pool-arm")
    p.add_argument("--corpus", default=str(PROJECT_ROOT / "data" / "uploads" / "aircargo"),
                   help="aircargo corpus dir for parent-window expansion")
    p.add_argument("--build-pool", action="store_true",
                   help="run the heavy embed+rerank stages first (Mac/Colab only)")
    p.add_argument("--out-dir", default=str(PROJECT_ROOT / ".tmp"),
                   help="dir for the built rerank pool (--build-pool)")
    p.add_argument("--with-grade", action="store_true",
                   help="add grade_docs CRAG arms (external-mistral LLM)")
    p.add_argument("--with-judge", action="store_true",
                   help="also compute faithfulness/answer_relevancy on baseline+winner (mistral)")
    p.add_argument("--mock", action="store_true",
                   help="Windows smoke: tiny in-memory pool, no models, no corpus")
    p.add_argument("--stub-grade", action="store_true",
                   help="smoke: use a deterministic offline grade stub instead of mistral")
    p.add_argument("--results-dir", default=str(PROJECT_ROOT / "reports" / "ragas"))

    buckets = p.add_argument_group("GR-0.3 bucket baseline (no models, no network)")
    buckets.add_argument("--buckets", action="store_true",
                         help="report the pinned pool per question class instead of the knob grid")
    buckets.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    buckets.add_argument("--sidecar", default=str(DEFAULT_SIDECAR_PATH),
                         help="question-class sidecar (T-11)")
    buckets.add_argument("--label-manifest", default=str(DEFAULT_LABEL_MANIFEST_PATH),
                         help="sidecar manifest pinning the dataset digest")
    buckets.add_argument("--corpus-manifest", default=str(DEFAULT_CORPUS_MANIFEST_PATH),
                         help="corpus manifest (T-10) naming the measured corpus")
    buckets.add_argument("--bucket-report", default=str(DEFAULT_BUCKET_REPORT_PATH))
    buckets.add_argument(
        "--pool-arm",
        choices=("C", "G1", "G2"),
        default="C",
        help="producer arm recorded in the bucket report provenance",
    )
    buckets.add_argument(
        "--pool-meta", help="ab_phase2_G2_pool_meta.json required when --pool-arm G2"
    )
    buckets.add_argument("--expected-cases", type=int, default=100)
    buckets.add_argument("--top-k", type=int, default=PHASE_C_TOP_K)
    buckets.add_argument("--context-chars", type=int, default=PHASE_C_CONTEXT_CHARS)

    gr2 = p.add_argument_group(
        "GR-2 entity graph report (no models, no network; bucket run uses --out-dir .tmp/gr2_bucket)"
    )
    gr2.add_argument(
        "--gr2-report",
        action="store_true",
        help="compare reranked G2 pools against G1 on both GR-2 datasets",
    )
    gr2.add_argument(
        "--g1-pool", default=str(PROJECT_ROOT / ".tmp" / "ab_candidates_phase2_G1.json")
    )
    gr2.add_argument(
        "--g2-pool", default=str(PROJECT_ROOT / ".tmp" / "ab_candidates_phase2_G2.json")
    )
    gr2.add_argument(
        "--g2-pool-meta", default=str(PROJECT_ROOT / ".tmp" / "ab_phase2_G2_pool_meta.json")
    )
    gr2.add_argument(
        "--bucket-g1-pool",
        default=str(PROJECT_ROOT / ".tmp" / "gr2_bucket" / "ab_candidates_phase2_G1.json"),
    )
    gr2.add_argument(
        "--bucket-g2-pool",
        default=str(PROJECT_ROOT / ".tmp" / "gr2_bucket" / "ab_candidates_phase2_G2.json"),
    )
    gr2.add_argument(
        "--bucket-g2-pool-meta",
        default=str(PROJECT_ROOT / ".tmp" / "gr2_bucket" / "ab_phase2_G2_pool_meta.json"),
    )
    gr2.add_argument("--bucket-dataset", default=str(DEFAULT_MULTI_DOC_DATASET_PATH))
    gr2.add_argument("--bucket-sidecar", default=str(DEFAULT_MULTI_DOC_SIDECAR_PATH))
    gr2.add_argument("--bucket-label-manifest", default=str(DEFAULT_MULTI_DOC_LABEL_MANIFEST_PATH))
    gr2.add_argument("--bucket-corpus-manifest", default=str(DEFAULT_CORPUS_MANIFEST_PATH))
    gr2.add_argument("--bucket-expected-cases", type=int, default=15)
    gr2.add_argument("--gr2-out", default=str(DEFAULT_GR2_REPORT_PATH))

    coherence = p.add_argument_group("GR-1a section coherence arm (no models, no network)")
    coherence.add_argument("--section-coherence", action="store_true",
                           help="run the section-coherence narrowing arm over the same pool "
                                "and report the whole threshold grid against the GR-0.3 "
                                "baseline (reuses the --buckets arguments)")
    coherence.add_argument("--coherence-report",
                           default=str(DEFAULT_SECTION_COHERENCE_REPORT_PATH))
    controls = p.add_argument_group("GR-1b same-pool controls (no models, no network)")
    controls.add_argument("--structural-controls", action="store_true")
    controls.add_argument("--structural-oracle", action="store_true")
    controls.add_argument("--oracle-report",
                          default=str(PROJECT_ROOT / "reports/gr/gr1b-oracle.json"))
    controls.add_argument("--controls-archive",
                          default=str(PROJECT_ROOT / "evaluation/gr1b-4436d61-candidates.json.gz"))
    controls.add_argument("--controls-report",
                          default=str(PROJECT_ROOT / "reports/gr/gr1b-controls.json"))
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.structural_controls or args.structural_oracle:
        from scripts.gr1b_controls import run_controls_report

        return run_controls_report(args)

    if args.section_coherence:
        return run_section_coherence_report(args)

    if args.gr2_report:
        return run_gr2_report(args)

    if args.buckets:
        return run_bucket_report(args)

    # Mock mode must never touch the network: grade always uses the offline stub
    # and the mistral judge is disabled regardless of flags.
    stub_grade = args.stub_grade or args.mock
    with_judge = args.with_judge and not args.mock

    if args.mock:
        rows = mock_rows()
        expander: Any = NullExpander()
        mode = "mock"
        artifact_label = "mock"
        with_grade = args.with_grade or args.stub_grade
    else:
        if args.build_pool:
            artifact = build_pool(Path(args.out_dir))
        else:
            artifact = Path(args.rerank_artifact)
        if not artifact.exists():
            print(json.dumps({
                "status": "error",
                "detail": f"rerank artifact not found: {artifact}; run with --build-pool "
                          "or point --rerank-artifact at ab_remote_contextual output",
            }, ensure_ascii=False))
            return 2
        rows = load_rerank_rows(artifact)
        expander = ParentExpander(Path(args.corpus))
        mode = "live"
        artifact_label = str(artifact)
        with_grade = args.with_grade

    grid = build_grid(with_grade=with_grade)
    report = run(
        rows,
        grid=grid,
        expander=expander,
        with_grade=with_grade,
        stub_grade=stub_grade,
        with_judge=with_judge,
        mode=mode,
        rerank_artifact=artifact_label,
    )

    json_path, md_path = write_outputs(report, Path(args.results_dir))
    ship = [a["arm"] for a in report["arms"] if a["verdict"] == "SHIP-CANDIDATE"]
    print(json.dumps({
        "status": "ok",
        "run_id": report["run_id"],
        "mode": mode,
        "num_cases": report["num_cases"],
        "arms": len(report["arms"]),
        "ship_candidates": ship,
        "report_markdown": str(md_path),
        "report_json": str(json_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
