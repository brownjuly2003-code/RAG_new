"""Offline expansion control reserving capped seed text before neighbours."""
from __future__ import annotations

import gzip
import json

from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from scripts.generator_benchmark import _truncate_contexts
from scripts.gr1b_controls import (
    DEFAULT_ARCHIVE,
    PROJECT_ROOT,
    _bucket_row,
    _score_texts,
    paired_comparison,
    render_controls_table,
    sha256_file,
    write_bucket_report,
)
from scripts.gr1b_stage_replay import (
    CHUNKS,
    POOL,
    build_stage_report,
    legacy_expand_graph_sections,
    legacy_graph_coherence,
    recover_ranked_docs,
)
from vectordb._base_manager import Document, HybridRetriever

DEFAULT_REPORT = PROJECT_ROOT / "reports/gr/gr1b-seed-expansion.json"


def reserve_seed_contexts(seeds: list[str], expanded: list[str], cap: int) -> list[str]:
    if cap < 1:
        raise ValueError("positive context cap required")
    pairs = [(seed, text) for seed, text in zip(seeds, expanded, strict=True) if seed]
    selected = _truncate_contexts([seed for seed, _ in pairs], cap)
    remaining = cap - sum(map(len, selected))
    for index, (seed, text) in enumerate(pairs[:len(selected)]):
        if not remaining:
            break
        if text.count(seed) != 1:
            raise ValueError("expanded text must contain one unambiguous seed")
        position = text.index(seed)
        prefix, suffix = text[:position], text[position + len(seed):]
        before_count = min(len(prefix), remaining)
        before = prefix[-before_count:] if before_count else ""
        remaining -= before_count
        after = suffix[:remaining]
        remaining -= len(after)
        selected[index] = before + seed + after
    return selected


def build_seed_report():
    stages = build_stage_report()
    baseline = stages["arms"][-1]["per_case"]
    archived = json.loads(gzip.decompress(DEFAULT_ARCHIVE.read_bytes()))
    pools = json.loads(gzip.decompress(POOL.read_bytes()))
    payload = json.loads(gzip.decompress(CHUNKS.read_bytes()))
    chunks = [Document(**row) for row in payload["chunks"]]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id=payload["tenant_id"]))
    retriever = HybridRetriever(vector_store=None, chunks=chunks, rerank_k=5, reranker=None,
                                use_bm25=False, parent_expansion_max_chars=3600,
                                graph_projection=projection)
    variants = {name: [] for name in ("seed_reserved_top5", "seed_reserved_coherent")}
    for pool, source, before in zip(pools, archived, baseline, strict=True):
        ranked = recover_ranked_docs(pool, source)[:5]
        for name, docs in zip(
            variants, (ranked, legacy_graph_coherence(retriever, ranked)), strict=True
        ):
            seeds = [doc.page_content for doc in docs]
            expanded = [doc.page_content for doc in legacy_expand_graph_sections(retriever, docs)]
            texts = reserve_seed_contexts(seeds, expanded, 6000)
            capped_seeds = _truncate_contexts(seeds, 6000)
            if len(texts) != len(capped_seeds) or any(seed not in text for seed, text in zip(capped_seeds, texts, strict=True)):
                raise ValueError("reserved seed text was lost")
            scored = dict(before, **_score_texts(source["query"], source["kws"], texts))
            scored["lost_keywords"] = sorted(set(before["matched_keywords"]) - set(scored["matched_keywords"]))
            scored["seed_chars"] = sum(map(len, capped_seeds))
            scored["added_chars"] = sum(map(len, texts)) - scored["seed_chars"]
            ordinary = _truncate_contexts(expanded, 6000)
            scored["changed_from_ordinary_expansion"] = texts != ordinary
            scored["ordinary_expansion_lost_seed"] = any(
                index >= len(ordinary) or seed not in ordinary[index]
                for index, seed in enumerate(capped_seeds)
            )
            variants[name].append(scored)
    provenance = stages["provenance"]
    provenance["code"]["files"]["scripts/gr1b_seed_expansion.py"] = sha256_file(PROJECT_ROOT / "scripts/gr1b_seed_expansion.py")
    provenance["config"]["seed_reservation"] = dict(
        cap=6000, expansion_budget=3600,
        policy="reserve capped seeds; remaining chars by seed rank, nearest preceding text then following text",
        order="original text order within each expanded context; partial neighbour text allowed",
        scope="two prespecified controls, with and without coherence; no label/query access in allocation",
    )
    arms = [dict(name=name, aggregate=_bucket_row("all cases", rows), per_case=rows,
                 changed_cases=sum(row["changed_from_ordinary_expansion"] for row in rows),
                 ordinary_seed_loss_cases=sum(row["ordinary_expansion_lost_seed"] for row in rows),
                 comparison=paired_comparison(rows, baseline, samples=2000, seed=42)) for name, rows in variants.items()]
    return dict(schema_version="gr1b-seed-expansion/v1.0", evidence_class="measured",
                provenance=provenance, labels=stages["labels"], exact_replays=stages["exact_replays"],
                baseline=stages["arms"][-1]["aggregate"], reference_arm="archived_g1", arms=arms)


if __name__ == "__main__":
    report = build_seed_report()
    write_bucket_report(report, DEFAULT_REPORT)
    print(render_controls_table(report), end="")
    print(json.dumps({arm["name"]: arm["changed_cases"] for arm in report["arms"]}))
