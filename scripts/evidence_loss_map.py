"""Deterministic archive-only H term-loss map; no models or network."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.devset import RU_TO_EN_RULE, ru_to_en
from evaluation.devset_sources import read_sources
from evaluation.ragas_eval import context_precision, context_recall
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from scripts.ab_remote_contextual import _kw_status
from scripts.generator_benchmark import _truncate_contexts

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = "evaluation/evidence-loss-map-prelim.json"
CAPSULE = "docs/evidence/evidence-loss-map-prelim.md"
INPUTS = {
    "dataset": "evaluation/curated_cases_aircargo.jsonl",
    "chunks": "evaluation/gr1b-4436d61-graph-chunks.json.gz",
    "hybrid": "evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz",
    "graph_pool": "evaluation/gr1b-4436d61-prerank-pool.json.gz",
    "graph": "evaluation/gr1b-4436d61-candidates.json.gz",
    "replay": "reports/gr/gr1b-stage-replay.json",
    "p1b": "reports/p1b/p1b-expanded-cut.json",
    "p1_scores": "evaluation/p1-511f3f9-H-rerank-scores.json",
    "corpus_manifest": "evaluation/aircargo_corpus.manifest.json",
    "phase_c": "evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json",
}
CODE_FILES = (
    "scripts/evidence_loss_map.py",
    "scripts/ab_remote_contextual.py",
    "scripts/generator_benchmark.py",
    "evaluation/ragas_eval.py",
)
STAGES = ("index", "initial_pool", "after_caps_dedup", "sent_context")
LOSS_ORDER = (
    "index_absent_proxy",
    "index_to_after_caps_unknown",
    "pool_to_sent_unknown",
    "no_observed_loss",
)
STRATUM = (
    "Cyrillic letter in query and ASCII Latin letter in at least one required term; "
    "case-level lexical RU-to-EN proxy, registered before counting"
)
BASELINE_STAGES = (
    "index",
    "initial_pool",
    "caps_dedup",
    "rerank",
    "expansion",
    "packing",
    "grading",
)
BASELINE_LOSSES = (
    "index",
    "index_to_pool_unknown",
    "caps_dedup",
    "rerank",
    "expansion",
    "packing",
    "grading",
    "no_observed_loss",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(name: str) -> Any:
    path = ROOT / INPUTS[name]
    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
    return json.loads(data)


def _by_id(rows: list[dict[str, Any]], ids: list[str]) -> dict[str, Any]:
    found = {row["case_id"]: row for row in rows}
    if len(found) != len(rows) or list(found) != ids:
        raise ValueError("archive case identities/order differ from H")
    return found


def _hits(terms: list[str], texts: list[str]) -> list[str]:
    # A singleton FULL reuses the exact status matcher, including its separator.
    return [term for term in terms if _kw_status([term], texts) == "FULL"]


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    terms = [term for row in rows for term in row["terms"]]
    stages = {}
    for stage in STAGES:
        if stage == "initial_pool":
            stages[stage] = {
                "observability": "not observable",
                "cases_observed": 0,
                "terms_observed": 0,
                "cases_missing_any": None,
                "terms_missing": None,
                "FULL": None,
                "PART": None,
                "MISS": None,
            }
        else:
            statuses = Counter(row["status"][stage] for row in rows)
            stages[stage] = {
                "observability": "observable",
                "cases_observed": len(rows),
                "terms_observed": len(terms),
                "cases_missing_any": sum(
                    any(not term["presence"][stage] for term in row["terms"]) for row in rows
                ),
                "terms_missing": sum(not term["presence"][stage] for term in terms),
                **{status: statuses[status] for status in ("FULL", "PART", "MISS")},
            }
    return {
        "case_denominator": len(rows),
        "term_denominator": len(terms),
        "stages": stages,
        "first_loss_cases": {
            loss: sum(row["first_observed_loss"] == loss for row in rows) for loss in LOSS_ORDER
        },
        "first_loss_terms": {
            loss: sum(term["first_observed_loss"] == loss for term in terms) for loss in LOSS_ORDER
        },
    }


def _transition(
    before: list[dict[str, Any]], after: list[dict[str, Any]], term_denominator: int
) -> dict[str, Any]:
    losses, gains = [], []
    for left, right in zip(before, after, strict=True):
        if left["case_id"] != right["case_id"]:
            raise ValueError("transition case mismatch")
        old, new = set(left["matched_keywords"]), set(right["matched_keywords"])
        for target, difference in ((losses, old - new), (gains, new - old)):
            if difference:
                target.append({"case_id": left["case_id"], "terms": sorted(difference)})
    return {
        "case_denominator": len(before),
        "term_denominator": term_denominator,
        "present_before_term_denominator": sum(len(row["matched_keywords"]) for row in before),
        "lost_cases": len(losses),
        "lost_terms": sum(len(row["terms"]) for row in losses),
        "gained_cases": len(gains),
        "gained_terms": sum(len(row["terms"]) for row in gains),
        "losses": losses,
        "gains": gains,
    }


def build_report() -> dict[str, Any]:
    data = {name: _load(name) for name in INPUTS}
    dataset = data["dataset"]
    ids = [case["case_id"] for case in dataset]
    term_denominator = sum(len(case["expected"]["answer_contains"]) for case in dataset)
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("expected the historical 100 H cases")
    chunks = data["chunks"]["chunks"]
    maps, caps = {}, {}
    corpus_missing = []
    for lane, pool_name, sent_name, pool_field in (
        ("hybrid", "hybrid", "hybrid", "prerank_cands"),
        ("graph", "graph_pool", "graph", "cands"),
    ):
        pool_rows = _by_id(data[pool_name], ids)
        sent_rows = _by_id(data[sent_name], ids)
        rows, before_cap, after_cap = [], [], []
        precisions, recalls = [], []
        for case in dataset:
            case_id = case["case_id"]
            terms = case["expected"]["answer_contains"]
            pool, archived = pool_rows[case_id], sent_rows[case_id]
            if pool["kws"] != terms or archived["kws"] != terms:
                raise ValueError("archive required terms differ from dataset")
            if pool["query"] != case["query"] or archived["query"] != case["query"]:
                raise ValueError("archive query differs from dataset")
            if lane == "hybrid":
                if Counter(pool[pool_field]) != Counter(archived["cands"]):
                    raise ValueError("hybrid prerank/ranked pool mismatch")
            elif pool["cands"] != archived["prerank_cands"]:
                raise ValueError("graph prerank archive mismatch")
            uncapped = archived["cands"][:5]
            sent = _truncate_contexts(uncapped, 6000)
            pool_hits, sent_hits = _hits(terms, pool[pool_field]), _hits(terms, sent)
            term_rows = []
            index_hits = []
            for term in terms:
                witness = next(
                    (
                        i
                        for i, chunk in enumerate(chunks)
                        if _kw_status([term], [chunk["page_content"]]) == "FULL"
                    ),
                    None,
                )
                indexed = witness is not None
                if indexed:
                    index_hits.append(term)
                elif lane == "hybrid":
                    corpus_missing.append(
                        {
                            "case_id": case_id,
                            "term": term,
                            "classification": "index absence; label/corpus unknown",
                        }
                    )
                presence = dict(
                    index=indexed,
                    initial_pool=None,
                    after_caps_dedup=term in pool_hits,
                    sent_context=term in sent_hits,
                )
                loss = (
                    LOSS_ORDER[0]
                    if not indexed
                    else LOSS_ORDER[1]
                    if term not in pool_hits
                    else LOSS_ORDER[2]
                    if term not in sent_hits
                    else LOSS_ORDER[3]
                )
                term_rows.append(
                    {
                        "term": term,
                        "presence": presence,
                        "first_observed_loss": loss,
                        "index_witness": None
                        if witness is None
                        else {
                            "chunk_ordinal": witness,
                            "source": chunks[witness]["metadata"].get("source"),
                            "text_sha256": sha256(chunks[witness]["page_content"].encode("utf-8")),
                        },
                    }
                )
            statuses = {}
            for stage, hits in (
                ("index", index_hits),
                ("after_caps_dedup", pool_hits),
                ("sent_context", sent_hits),
            ):
                statuses[stage] = "FULL" if len(hits) == len(terms) else "PART" if hits else "MISS"
            # Assert the singleton decomposition preserves the harness status.
            if statuses["sent_context"] != _kw_status(terms, sent):
                raise ValueError("term decomposition differs from harness")
            rows.append(
                {
                    "case_id": case_id,
                    "ru_to_en": bool(re.search("[А-Яа-яЁё]", case["query"]))
                    and any(re.search("[A-Za-z]", term) for term in terms),
                    "terms": term_rows,
                    "status": dict(statuses, initial_pool="not observable"),
                    "first_observed_loss": min(
                        (term["first_observed_loss"] for term in term_rows), key=LOSS_ORDER.index
                    ),
                    "pool_candidates": len(pool[pool_field]),
                    "sent_text_sha256": [sha256(text.encode("utf-8")) for text in sent],
                }
            )
            before_cap.append({"case_id": case_id, "matched_keywords": _hits(terms, uncapped)})
            after_cap.append({"case_id": case_id, "matched_keywords": sent_hits})
            precisions.append(round(context_precision(case["query"], sent, terms), 4))
            recalls.append(round(context_recall(sent, terms), 4))
        maps[lane] = {
            "summary": _summary(rows),
            "ru_to_en": _summary([row for row in rows if row["ru_to_en"]]),
            "official_lexical": {
                "context_precision": round(sum(precisions) / len(rows), 4),
                "context_recall": round(sum(recalls) / len(rows), 4),
                "case_denominator": len(rows),
                "target": 0.63,
            },
            "per_case": rows,
        }
        caps[lane] = _transition(before_cap, after_cap, term_denominator)

    replay = {arm["name"]: arm for arm in data["replay"]["arms"]}
    before = replay["reranked_top_5"]["per_case"]
    after = replay["expansion_only"]["per_case"]
    _by_id(before, ids)
    _by_id(after, ids)
    expansion = _transition(before, after, term_denominator)
    p1b = {}
    for name, arm in data["p1b"]["h"]["arms"].items():
        _by_id(arm["per_case"], ids)
        p1b[name] = {
            "case_denominator": arm["aggregate"]["num_cases"],
            "term_denominator": term_denominator,
            "uncapped": arm["aggregate"],
            "capped": arm["diagnostic_aggregate"],
            "selection_vs_expanded_control_losses": arm.get("fact_losses", []),
            "expansion_only_term_losses": "not observable",
            "cap_only_term_losses": "not observable",
            "reason": "P1b archive has aggregates/selection losses, not expanded texts or capped per-case hits",
        }
    pins = {}
    for name, path in INPUTS.items():
        raw = (ROOT / path).read_bytes()
        pins[name] = {"path": path, "sha256": sha256(raw)}
        if path.endswith(".gz"):
            pins[name]["uncompressed_sha256"] = sha256(gzip.decompress(raw))
    config = {
        "required_terms": "expected.answer_contains (case-term occurrences, not unique vocabulary)",
        "matcher": "scripts.ab_remote_contextual._kw_status singleton FULL; lowercase substring",
        "index_match": "term present in at least one individual archived chunk; no cross-chunk joins",
        "initial_pool": "not observable; no per-source text archive before caps",
        "after_caps_dedup": "hybrid prerank_cands; graph original pool cands; reranker input",
        "sent_context": "cached top-5 with scripts.generator_benchmark._truncate_contexts at 6000 chars",
        "ru_to_en_definition": STRATUM,
        "replay_matcher": "archived normalized matched_keywords, distinct from raw FULL/PART/MISS",
        "index_source": INPUTS["chunks"],
        "index_scope": "shared arm-C chunking snapshot used by GR-1b; not attested as the C.1a index",
        "top_k": 5,
        "context_chars": 6000,
        "unobservable": ["rerank", "selection", "coherence", "grading", "answer"],
    }
    config_hash = sha256(json.dumps({"config": config, "inputs": pins}, sort_keys=True).encode())
    code_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=60
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, timeout=60
    ).strip()
    phase_c = data["phase_c"]["provenance"]
    return {
        "schema_version": "evidence-loss-map-prelim/v1",
        "date": "2026-10-01",
        "slice": "2.5 preliminary / T-63",
        "evidence_class": "measured_archive_term_proxy",
        "gold_spans": "not available; not semantic evidence_recall_pool/fact_coverage",
        "config": config,
        "config_sha256": config_hash,
        "provenance": {
            "code_sha": code_sha,
            "tree_clean": not bool(dirty),
            "code_files": {name: sha256((ROOT / name).read_bytes()) for name in CODE_FILES},
            "inputs": pins,
            "corpus": data["corpus_manifest"],
            "chunk_count": len(chunks),
            "historical_phase_c": phase_c,
            "historical_p1_reranker": data["p1_scores"]["provenance"],
            "embedder": {
                "model": "BAAI/bge-m3",
                "revision": "unknown",
                "index_manifest": "not observable",
                "dimension": "not observable",
                "prompts": "not observable",
                "normalisation": "not observable",
                "scope": "historical producer names BGE-M3, same model id as current default; no current rerun",
            },
            "ingestion_snapshot_id": "archived GR-1b chunks + corpus manifest hashes",
            "chunker_version": "unknown; historical structural/contextual 800/200 configuration",
            "effective_query": "archived query; no expanded_query in these inputs",
            "graph_digest": "not observable",
            "entity_graph_status": "N/A: structural G1",
            "judge": "N/A",
            "bootstrap": "N/A: descriptive counts",
            "residency_and_peak_host_rss": "N/A: no model run",
            "label_migration": "N/A: no rechunking or label migration",
            "campaign_baseline": "NOT_EVIDENCE: preliminary archive diagnostic, not a new campaign run",
        },
        "maps": maps,
        "index_stage_losses": corpus_missing,
        "label_problem_candidates": corpus_missing,
        "g3": {
            "section_expansion_plus_cap": expansion,
            "section_scope": "expansion_only vs reranked_top_5, both capped; not uncapped expansion attribution",
            "evaluation_cap_raw_terms": caps,
            "p1b_archived_arms": p1b,
        },
    }


def render_capsule(report: dict[str, Any]) -> str:
    p = report["provenance"]
    lines = [
        "# Preliminary H evidence-loss map — slice 2.5 (T-63)",
        "",
        "**Evidence proxy, not gold:** H has no gold spans. Required terms are the agent-authored",
        "`expected.answer_contains` labels; existing phase-C/P1 `_kw_status` is reused",
        "(lowercase substring, including underscores/punctuation). This is not semantic",
        "`evidence_recall_pool`, `all_evidence_coverage` or `fact_coverage` and proves no",
        "answer sufficiency. An absent corpus term could be a label problem, not pipeline loss.",
        "",
        f"Registered before counting — G2 RU→EN definition: {STRATUM}.",
        "This does not establish the evidence document's language or multilingual semantic recall.",
        "",
        "## Stages and scope",
        "",
        "Index uses the archived GR-1b chunk set because it exists; no external corpus directory",
        "is needed. It shares arm-C structural/contextual chunking, but no archived index manifest",
        "attests byte identity with the older C.1a index. Its coverage is a snapshot proxy.",
        "A term must match inside one chunk. Initial per-source candidates before caps are",
        "**not observable**. `prerank_cands` (hybrid) and original G1 pool `cands` are already",
        "after RRF/caps/dedup, exactly the reranker input. P1 score files contain scores aligned",
        "to that pool, not another earlier pool. Hybrid sent context is phase-C cached top-five",
        "under the evaluation cap. G1 is a separate diagnostic lane with structural processing.",
        "",
        "First loss is the earliest absent required term at an observed stage; later recovery",
        "does not erase it. Index→pool losses span retrieval and caps/dedup: their cause is unknown.",
        "Pool→sent losses are **between pool and sent context — stage unknown**",
        "(rerank / selection / coherence not observable). No loss is attributed to rerank.",
        "Grading, answer and API parity remain unknown. These archived contexts are harness",
        "contexts, not an attestation of production `/api/ask` packing.",
        "",
        "Counts below use case-term occurrences. Missing-at-stage counts can overlap; first-loss",
        "counts partition the population. RU→EN rows include all required terms of selected cases.",
        "",
        "| lane / stratum | stage | observed cases / denominator | missing-any cases | observed terms / denominator | missing terms | FULL/PART/MISS |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for lane, block in report["maps"].items():
        for stratum in ("summary", "ru_to_en"):
            summary = block[stratum]
            for stage, row in summary["stages"].items():
                n, t = summary["case_denominator"], summary["term_denominator"]
                if row["observability"] == "not observable":
                    lines.append(
                        f"| {lane}/{stratum} | {stage}: not observable | 0/{n} | N/A | 0/{t} | N/A | N/A |"
                    )
                else:
                    lines.append(
                        f"| {lane}/{stratum} | {stage} | {n}/{n} | {row['cases_missing_any']} | {t}/{t} | {row['terms_missing']} | {row['FULL']}/{row['PART']}/{row['MISS']} |"
                    )
    lines += [
        "",
        "| lane / stratum | first observed loss | cases / denominator | terms / denominator |",
        "|---|---|---:|---:|",
    ]
    for lane, block in report["maps"].items():
        for stratum in ("summary", "ru_to_en"):
            summary = block[stratum]
            for loss in LOSS_ORDER:
                lines.append(
                    f"| {lane}/{stratum} | {loss} | {summary['first_loss_cases'][loss]}/{summary['case_denominator']} | {summary['first_loss_terms'][loss]}/{summary['term_denominator']} |"
                )
    lines += [
        "",
        "Official lexical ruler beside the proxy (target is diagnostic here):",
        "",
        "| lane | cases | context precision | context recall | phase-C target |",
        "|---|---:|---:|---:|---:|",
    ]
    for lane, block in report["maps"].items():
        m = block["official_lexical"]
        lines.append(
            f"| {lane} | {m['case_denominator']} | {m['context_precision']:.4f} | {m['context_recall']:.4f} | {m['target']} |"
        )
    lines += [
        "",
        "## G3: expansion and evaluation-cap diagnostics",
        "",
        "The replay contrast uses its **archived normalized hits**, distinct from the raw",
        "FULL/PART/MISS matcher above. `expansion_only` vs `reranked_top_5` changes section",
        "expansion and then applies the same evaluation cap; uncapped section losses cannot",
        "be separated from cap losses in that report. It is outside the main causal map.",
        "",
        "| diagnostic | case denominator | term denominator | present-before terms | lost cases | lost terms | gained cases | gained terms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    transitions = {
        "section expansion + cap (normalized)": report["g3"]["section_expansion_plus_cap"],
        **{
            f"{lane} cap only (raw)": value
            for lane, value in report["g3"]["evaluation_cap_raw_terms"].items()
        },
    }
    for name, row in transitions.items():
        lines.append(
            f"| {name} | {row['case_denominator']} | {row['term_denominator']} | {row['present_before_term_denominator']} | {row['lost_cases']} | {row['lost_terms']} | {row['gained_cases']} | {row['gained_terms']} |"
        )
    lines += [
        "",
        "P1b parent-expanded arms archive aggregate rulers and selection losses, not expanded",
        "texts or per-case capped hits. Expansion-only and cap-only term losses are **not",
        "observable**. Uncapped→capped status totals below are marginals, not paired transitions;",
        "selection-vs-expanded-control losses are not attributed to parent expansion.",
        "Selection-loss terms use P1b's archived normalized matches. Lost-term denominators",
        "are the present-before terms for paired contrasts; gained-term denominators are",
        "the remaining required terms. P1b selection losses use all required terms because",
        "the expanded control's per-case matched terms are not archived.",
        "",
        "| P1b H arm | case denominator | term denominator | uncapped FULL/PART/MISS | capped FULL/PART/MISS | selection-loss cases | selection-loss terms |",
        "|---|---:|---:|---|---|---:|---:|",
    ]
    for name, arm in report["g3"]["p1b_archived_arms"].items():
        u, c = arm["uncapped"], arm["capped"]
        losses = arm["selection_vs_expanded_control_losses"]
        lines.append(
            f"| {name} | {arm['case_denominator']} | {arm['term_denominator']} | {u['FULL']}/{u['PART']}/{u['MISS']} | {c['FULL']}/{c['PART']}/{c['MISS']} | {len(losses)} | {sum(len(row['lost_keywords']) for row in losses)} |"
        )
    lines += [
        "",
        "## Index-stage losses — fix before the 2.5 baseline",
        "",
        f"Absent-index term occurrences: {len(report['index_stage_losses'])}.",
        "Every required term has an individual archived-chunk witness (ordinal, source, text SHA",
        "in JSON). No ingestion/index loss or absent-corpus label problem is demonstrated by",
        "this proxy. Gold-span cuts and incorrect labels can still be missed. No ingestion fix",
        "is made in this slice; any later proven loss requires a separate fix before baseline.",
        "",
        "## Per-case first observation",
        "",
        "`initial_pool` is not observable for every case. Term-level presence at each stage,",
        "index witnesses and sent-text hashes are in the linked JSON. Main hybrid and G1",
        "results remain separate; `unknown` never names a hidden mechanism.",
        "",
        "| H case | RU→EN | hybrid first loss | graph first loss |",
        "|---|---|---|---|",
    ]
    for h, g in zip(
        report["maps"]["hybrid"]["per_case"], report["maps"]["graph"]["per_case"], strict=True
    ):
        lines.append(
            f"| `{h['case_id']}` | {'yes' if h['ru_to_en'] else 'no'} | {h['first_observed_loss']} | {g['first_observed_loss']} |"
        )
    lines += [
        "",
        "## Provenance and development ledger",
        "",
        f"Extraction date `{report['date']}`; code SHA `{p['code_sha']}`;",
        f"`tree_clean`: `{str(p['tree_clean']).lower()}`. Working-tree code digests in JSON",
        "pin the uncommitted extractor; its publishing commit later anchors those digests.",
        f"Config SHA-256 `{report['config_sha256']}`.",
        f"Corpus SHA-256 `{p['corpus']['corpus_sha256']}`;",
        f"archived chunks: {p['chunk_count']}; corpus files: {p['corpus']['file_count']}.",
        "",
        "| input artifact | SHA-256 of stored bytes |",
        "|---|---|",
    ]
    for pin in p["inputs"].values():
        lines.append(f"| [{pin['path']}](../../{pin['path']}) | `{pin['sha256']}` |")
    lines += [
        "",
        "Compressed inputs also carry decompressed hashes in JSON. Historical producer code",
        "SHAs, reranker revision/batch and phase-C generator fingerprint/config are retained",
        "verbatim there. Archived embedder id is BGE-M3, matching the current default model id;",
        "HF revision, prompts and index-manifest attestation are unknown. This is **not a",
        "rerun on today's embedder/index**. Chunker version and graph digest are unknown;",
        "historical structural/contextual chunk settings are described by the producer.",
        "",
        "New-campaign baseline provenance is `NOT_EVIDENCE`: no current manifest check, API",
        "parity, gold, judges, latency or model run. Non-applicable judge/bootstrap/host-model",
        "fields are N/A in JSON. Historical H is agent-authored; later journey-label approval",
        "does not create gold spans. No mechanism is selected on this incomplete causal map;",
        "the complete map follows gold and parity slices. Runtime defaults are unchanged.",
        "",
        "[JSON artifact](../../evaluation/evidence-loss-map-prelim.json) ·",
        "[extractor](../../scripts/evidence_loss_map.py) ·",
        "[reproducibility test](../../tests/test_evidence_loss_map.py) ·",
        "[development ledger](../../evaluation/dev_ledger.jsonl). The ledger's first entry",
        "registers this diagnostic as H development use with config and artifact hashes.",
        "No holdout was read.",
        "",
    ]
    return "\n".join(lines)


def _baseline_term(term: str, document: str | None, stages: dict[str, Any]) -> dict[str, Any]:
    presence = {
        stage: any(
            _hits([term], [text])
            for text, source in stages[stage]
            if document is None or source == document
        )
        for stage in BASELINE_STAGES
    }
    if presence["grading"]:
        first = last = "no_observed_loss"
    else:
        first = (
            "index"
            if not presence["index"]
            else "index_to_pool_unknown"
            if not presence["initial_pool"]
            else next(stage for stage in BASELINE_STAGES if not presence[stage])
        )
        held = [i for i, stage in enumerate(BASELINE_STAGES) if presence[stage]]
        last = (
            "index"
            if not held
            else "index_to_pool_unknown"
            if max(held) == 0
            else BASELINE_STAGES[max(held) + 1]
        )
    return {
        "term": term,
        **({"document": document} if document is not None else {}),
        "presence": presence,
        "first_loss": first,
        "last_loss": last,
    }


def _baseline_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [row for row in rows if row["first_loss"] != "unknown"]
    terms = [term for row in counted for term in row["terms"]]
    stages = {}
    for i, stage in enumerate(BASELINE_STAGES):
        previous = BASELINE_STAGES[i - 1] if i else None
        stages[stage] = {
            "case_denominator": len(counted),
            "term_denominator": len(terms),
            "terms_held": sum(t["presence"][stage] for t in terms),
            "terms_not_held": sum(not t["presence"][stage] for t in terms),
            "cases_all_held": sum(all(t["presence"][stage] for t in r["terms"]) for r in counted),
            "previous_stage": previous,
            "terms_lost": sum(t["presence"][previous] and not t["presence"][stage] for t in terms)
            if previous
            else None,
            "terms_gained": sum(not t["presence"][previous] and t["presence"][stage] for t in terms)
            if previous
            else None,
            "cases_with_lost_term": sum(
                any(t["presence"][previous] and not t["presence"][stage] for t in r["terms"])
                for r in counted
            )
            if previous
            else None,
        }
    distributions = {}
    for name, items in (("cases", counted), ("terms", terms)):
        counts = Counter(item["first_loss"] for item in items)
        distributions["first_loss_" + name] = {
            loss: {"count": counts[loss], "share": counts[loss] / len(items) if items else None}
            for loss in BASELINE_LOSSES
        }
    return {
        "cases": {
            "total": len(rows),
            "counted": len(counted),
            "unknown_by_reason": dict(
                Counter(r["reason"] for r in rows if r["first_loss"] == "unknown")
            ),
        },
        "case_denominator": len(counted),
        "term_denominator": len(terms),
        "stages": stages,
        **distributions,
    }


def _baseline_case(
    case: dict[str, Any],
    retrieve: dict[str, Any],
    grade: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    gold: list[tuple[str, str | None]] = (
        list(case.get("answer_sources", {}).items())
        if case["subset"] == "Hm"
        else [(term, None) for term in case.get("expected", {}).get("answer_contains", [])]
    )
    row = {
        "case_id": case["case_id"],
        "subset": case["subset"],
        "query_effective": retrieve.get("query_effective", grade.get("query_effective")),
        "query_transform": retrieve.get("query_transform", grade.get("query_transform")),
        "ru_to_en": ru_to_en(
            {"question": case["query"], "required_facts": [{"text": term} for term, _ in gold]}
        ),
        "archive_proxy": bool(re.search("[А-Яа-яЁё]", case["query"]))
        and any(re.search("[A-Za-z]", term) for term, _ in gold),
        "terms": [],
    }
    if grade["status"] == "excluded":
        return {
            **row,
            "first_loss": "unknown",
            "reason": "excluded",
            "exclusion": grade["exclusion"],
        }
    if not gold:
        return {**row, "first_loss": "unknown", "reason": "no_gold"}
    indexed = [(chunk["page_content"], chunk["metadata"].get("source")) for chunk in chunks]
    stages = {
        "index": indexed,
        "initial_pool": [indexed[i] for i in retrieve["vector"] + retrieve["pool"]],
        "caps_dedup": [indexed[i] for i in retrieve["pool"]],
    }
    for stage, documents in (
        ("rerank", retrieve["seed_documents"]),
        ("expansion", retrieve["expanded_documents"]),
        ("packing", retrieve["documents"]),
        ("grading", grade["documents"]),
    ):
        stages[stage] = [(d["text"], d["metadata"].get("source")) for d in documents]
    terms = [_baseline_term(term, document, stages) for term, document in gold]
    row.update(
        terms=terms, first_loss=min((t["first_loss"] for t in terms), key=BASELINE_LOSSES.index)
    )
    if case["subset"] == "Hm":
        row["source_documents_present"] = {
            stage: [
                source
                for source in case["source_documents"]
                if any(name == source for _, name in texts)
            ]
            for stage, texts in stages.items()
        }
    return row


def _baseline_g3(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [r for r in rows if r["first_loss"] != "unknown"]
    hits = {
        stage: [
            {
                "case_id": r["case_id"],
                "matched_keywords": [
                    str(i) for i, t in enumerate(r["terms"]) if t["presence"][stage]
                ],
            }
            for r in counted
        ]
        for stage in ("rerank", "expansion", "grading")
    }
    denominator = sum(len(r["terms"]) for r in counted)
    expansion = _transition(hits["rerank"], hits["expansion"], denominator)
    sent = _transition(hits["rerank"], hits["grading"], denominator)
    by_id = {r["case_id"]: r["terms"] for r in counted}
    for transition in (expansion, sent):
        for change in transition["losses"] + transition["gains"]:
            change["terms"] = sorted(
                by_id[change["case_id"]][int(i)]["term"] for i in change["terms"]
            )
    return {
        "rerank_to_expansion": expansion,
        "rerank_to_grading": sent,
        "expansion_gains": {
            key: expansion[key]
            for key in (
                "case_denominator",
                "term_denominator",
                "gained_cases",
                "gained_terms",
                "gains",
            )
        },
    }


def _baseline_index_losses(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    directory: Path,
    files: dict[tuple[str, str], dict[str, str]],
    run: Path,
) -> list[dict[str, Any]]:
    losses = [
        {
            "case_id": row["case_id"],
            "subset": row["subset"],
            "term": term["term"],
            **({"document": term["document"]} if "document" in term else {}),
        }
        for row in rows
        if row["first_loss"] != "unknown"
        for term in row["terms"]
        if not term["presence"]["index"]
    ]
    if not losses:
        return losses
    texts: dict[str, str] = {}
    reason = None
    try:
        texts = read_sources(manifest["source_manifest"], directory)
    except (OSError, ValueError, UnicodeError) as exc:
        reason = f"{type(exc).__name__}: source texts unavailable or integrity check failed"
    for entry in manifest["source_manifest"]["files"]:
        path = directory / entry["name"]
        try:
            _baseline_pin(files, path, run, "sources", entry["name"])
        except OSError:
            pass
    for loss in losses:
        source_texts = (
            ([texts[loss["document"]]] if loss.get("document") in texts else [])
            if "document" in loss
            else list(texts.values())
        )
        if reason or ("document" in loss and loss["document"] not in texts):
            loss.update(kind="unknown", reason=reason or "gold document not in source manifest")
        else:
            loss["kind"] = (
                "split_by_chunking"
                if any(_hits([loss["term"]], [text]) for text in source_texts)
                else "absent_from_sources"
            )
    return losses


def _baseline_pin(
    files: dict[tuple[str, str], dict[str, str]],
    path: Path,
    run: Path,
    root: str = "run",
    reference: str | None = None,
) -> None:
    if reference is None:
        reference = path.resolve().relative_to(run.resolve()).as_posix()
    files[(root, reference)] = {
        "root": root,
        "path": reference,
        "sha256": parity.file_sha(path),
    }


def build_baseline_map(
    run: Path,
    chunks: Path | None = None,
    sources: Path | None = None,
) -> dict[str, Any]:
    manifest = baseline.load_manifest(run)
    identity = parity.digest(manifest)
    baseline.require_no_aborts(run, baseline.STAGES)
    parity.load_stage(run / "report.json", identity)
    archive = chunks if chunks is not None else Path(manifest["corpus"])
    if parity.file_sha(archive) != manifest["index_receipt"]["corpus_sha256"]:
        raise baseline.IntegrityError("Chunk archive differs from indexed corpus SHA-256")
    corpus = json.loads(gzip.decompress(archive.read_bytes()))["chunks"]
    files: dict[tuple[str, str], dict[str, str]] = {}
    for path in (run / "manifest.json", run / "registration.json", run / "report.json"):
        _baseline_pin(files, path, run)
    _baseline_pin(files, archive, run, "chunk_archive", archive.name)
    rows = []
    modes = set()
    for case in manifest["cases"]:
        records = {}
        for stage in baseline.STAGES:
            path = run / stage / (case["case_id"] + ".json")
            record = baseline.load_case(path, identity, run)
            _baseline_pin(files, path, run)
            for call in record.get("model_calls", []):
                _baseline_pin(files, run / call["cache_file"], run)
            if stage != "prepare":
                modes.add(record.get("routing_mode"))
            records[stage] = record
        rows.append(_baseline_case(case, records["retrieve"], records["grade"], corpus))
    if len(modes) != 1:
        raise baseline.IntegrityError("Expected one routing_mode in baseline records")
    mode = next(iter(modes))
    if not isinstance(mode, str) or "graph off" not in mode:
        raise baseline.IntegrityError("Baseline routing_mode must contain graph off")
    index_losses = _baseline_index_losses(
        rows,
        manifest,
        sources if sources is not None else Path(manifest["source_directory"]),
        files,
        run,
    )
    return {
        "schema_version": "evidence-loss-map-baseline/v1",
        "manifest_sha256": identity,
        "files": [files[name] for name in sorted(files)],
        "chunk_archive": {
            "name": archive.name,
            "sha256": manifest["index_receipt"]["corpus_sha256"],
        },
        "routing_mode": mode,
        "observability": {
            "answer": {"status": "unknown", "reason": "no generation in this mode"},
            "graph_caps": {"status": "not_observable", "reason": "graph off"},
            "coherence": {"status": "not_observable", "reason": "graph off"},
            "bm25_candidates": {
                "status": "not_observable",
                "reason": "BM25 candidate ids are not recorded",
            },
            "query_transform": {"status": "reference_only", "reason": "no loss attributed"},
        },
        "summary": {
            subset: _baseline_summary(
                rows if subset == "all" else [r for r in rows if r["subset"] == subset]
            )
            for subset in ("H", "Hm", "all")
        },
        "per_case": rows,
        "g2": {
            name: {
                "rule": rule,
                "label": label,
                "subsets": {
                    subset: {
                        side: _baseline_summary(
                            [
                                r
                                for r in rows
                                if (subset == "all" or r["subset"] == subset) and r[field] == inside
                            ]
                        )
                        for side, inside in (("inside", True), ("outside", False))
                    }
                    for subset in ("H", "Hm", "all")
                },
            }
            for name, field, rule, label in (
                ("registered", "ru_to_en", RU_TO_EN_RULE, "registered RU-to-EN stratum"),
                (
                    "archive_proxy",
                    "archive_proxy",
                    STRATUM,
                    "archive proxy for preliminary-map comparison",
                ),
            )
        },
        "g3": {
            subset: _baseline_g3([r for r in rows if r["subset"] == subset])
            for subset in ("H", "Hm")
        },
        "index_stage_losses": index_losses,
        "index_loss_policy": "An index loss needs a code fix before the baseline is published.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--capsule", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--baseline-run", type=Path)
    parser.add_argument("--chunks", type=Path)
    parser.add_argument("--sources", type=Path)
    args = parser.parse_args()
    if args.baseline_run is None and (args.chunks is not None or args.sources is not None):
        parser.error("--chunks and --sources require --baseline-run")
    if args.baseline_run is not None:
        if args.out is None or args.capsule is not None or args.ledger is not None:
            parser.error("--baseline-run requires --out and forbids --capsule and --ledger")
        report = build_baseline_map(args.baseline_run, args.chunks, args.sources)
        serialized = (
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        )
        args.out.write_text(serialized, encoding="utf-8", newline="\n")
        print(json.dumps(report["summary"], sort_keys=True))
        print(f"Index losses: {len(report['index_stage_losses'])}")
        return 0
    if args.out is None:
        args.out = ROOT / ARTIFACT
    report = build_report()
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.out.write_text(serialized, encoding="utf-8", newline="\n")
    if args.capsule:
        args.capsule.write_text(render_capsule(report), encoding="utf-8", newline="\n")
    if args.ledger:
        if args.ledger.exists():
            raise ValueError("refusing to overwrite the development ledger")
        entry = {
            "entry": 1,
            "date": report["date"],
            "slice": report["slice"],
            "config_sha256": report["config_sha256"],
            "artifact": ARTIFACT,
            "artifact_sha256": sha256(serialized.encode("utf-8")),
            "families_touched": ["H"],
            "verdict": "preliminary_archive_diagnostic",
        }
        args.ledger.write_text(
            json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    print(json.dumps({lane: block["summary"] for lane, block in report["maps"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
