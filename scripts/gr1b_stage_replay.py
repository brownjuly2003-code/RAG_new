"""Recover GR-1b metadata and measure structural stages without model calls."""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter

from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_projection import project_structure_graph
from scripts.generator_benchmark import _truncate_contexts
from scripts.gr1b_controls import (
    DEFAULT_ARCHIVE,
    PROJECT_ROOT,
    _bucket_row,
    _score_texts,
    build_controls_report,
    paired_comparison,
    render_controls_table,
    sha256_file,
    write_bucket_report,
)
from vectordb._base_manager import Document, HybridRetriever, _rrf_document_key

POOL = PROJECT_ROOT / "evaluation/gr1b-4436d61-prerank-pool.json.gz"
CHUNKS = PROJECT_ROOT / "evaluation/gr1b-4436d61-graph-chunks.json.gz"
DEFAULT_REPORT = PROJECT_ROOT / "reports/gr/gr1b-stage-replay.json"


def legacy_expand_graph_sections(retriever: HybridRetriever, docs: list[Document]) -> list[Document]:
    """The section expansion GR-1b ran and archived: HybridRetriever._expand_graph_sections as it
    stood until stage 7's fix (PLAN.md stage 7), each side taking every sibling of the section
    in reach that fit, its header stripped, joined by blank lines. Kept here, so the published
    replay still reproduces its archive; the product's expansion is the retriever's own."""
    used_keys = {_rrf_document_key(doc, retriever._doc_key_chars) for doc in docs}
    expanded: list[Document] = []
    for doc in docs:
        doc_key = _rrf_document_key(doc, retriever._doc_key_chars)
        section = retriever._graph_chunk_sections.get(doc_key)
        section_docs = retriever._graph_section_chunks.get(section or "", [])
        positions = [index for index, candidate in enumerate(section_docs)
                     if _rrf_document_key(candidate, retriever._doc_key_chars) == doc_key]
        if not positions:
            expanded.append(doc)
            continue
        before: list[str] = []
        after: list[str] = []
        budget = retriever._parent_max_chars - len(doc.page_content)
        position = positions[0]
        for distance in range(1, len(section_docs)):
            for side, sibling_position in ((before, position - distance), (after, position + distance)):
                if sibling_position < 0 or sibling_position >= len(section_docs):
                    continue
                sibling = section_docs[sibling_position]
                sibling_key = _rrf_document_key(sibling, retriever._doc_key_chars)
                if sibling_key in used_keys:
                    continue
                text = retriever._strip_contextual_header(sibling.page_content).strip()
                if not text or len(text) > budget:
                    continue
                budget -= len(text)
                used_keys.add(sibling_key)
                side.append(text)
        if not before and not after:
            expanded.append(doc)
            continue
        parts = list(reversed(before)) + [doc.page_content] + after
        expanded.append(Document(page_content="\n\n".join(parts),
                                 metadata={**(doc.metadata or {}), "graph_section_expanded": True}))
    return expanded


def recover_ranked_docs(pool: dict, archived: dict) -> list[Document]:
    if (pool["cands"] != archived["prerank_cands"]
            or pool["cand_sources"] != archived["prerank_sources"]):
        raise ValueError("original pool differs from archived prerank input")
    mapping = {}
    for text, source, metadata in zip(pool["cands"], pool["cand_sources"], pool["cand_metadata"], strict=True):
        key = (text, source)
        if key in mapping and mapping[key] != metadata:
            raise ValueError("ambiguous metadata for candidate text/source")
        mapping[key] = metadata
    ranked_keys = list(zip(archived["reranked_cands"], archived["reranked_sources"], strict=True))
    if Counter(ranked_keys) != Counter(zip(pool["cands"], pool["cand_sources"], strict=True)):
        raise ValueError("reranked candidates are not a permutation of original pool")
    return [Document(page_content=text, metadata=dict(mapping[(text, source)])) for text, source in ranked_keys]


def build_stage_report():
    controls = build_controls_report()
    archived = json.loads(gzip.decompress(DEFAULT_ARCHIVE.read_bytes()))
    pools = json.loads(gzip.decompress(POOL.read_bytes()))
    if [row["case_id"] for row in pools] != [row["case_id"] for row in archived]:
        raise ValueError("original pool case identities/order differ")
    payload = json.loads(gzip.decompress(CHUNKS.read_bytes()))
    chunks = [Document(**row) for row in payload["chunks"]]
    projection = project_structure_graph(build_structural_graph(chunks, tenant_id=payload["tenant_id"]))
    retriever = HybridRetriever(vector_store=None, chunks=chunks, rerank_k=5, reranker=None,
                                use_bm25=False, parent_expansion_max_chars=3600,
                                graph_projection=projection)
    baseline = controls["arms"][0]["per_case"]
    variants = {name: [] for name in ("reranked_top_5", "coherence_only", "expansion_only", "g1_replay")}
    for pool, source, before in zip(pools, archived, baseline, strict=True):
        if source["rerank_k"] != 5 or source["case_id"] != before["case_id"]:
            raise ValueError("case identity or rerank limit differs")
        ranked = recover_ranked_docs(pool, source)[:5]
        coherent = retriever._apply_graph_coherence(ranked)
        replay = legacy_expand_graph_sections(retriever, coherent)
        if ([doc.page_content for doc in replay] != source["cands"]
                or [doc.metadata for doc in replay] != source["cand_metadata"]
                or [doc.metadata.get("source", "?") for doc in replay] != source["cand_sources"]):
            raise ValueError(f"{source['case_id']}: exact structural replay differs")
        for name, docs in zip(variants, (ranked, coherent, legacy_expand_graph_sections(retriever, ranked), replay), strict=True):
            texts = _truncate_contexts([doc.page_content for doc in docs], 6000)
            scored = dict(before, **_score_texts(source["query"], source["kws"], texts))
            scored["lost_keywords"] = sorted(set(before["matched_keywords"]) - set(scored["matched_keywords"]))
            variants[name].append(scored)
    arms = [dict(name=name, aggregate=_bucket_row("all cases", rows), per_case=rows,
                 comparison=paired_comparison(rows, baseline, samples=2000, seed=42)) for name, rows in variants.items()]
    provenance = controls["provenance"]
    provenance["recovered_inputs"] = {
        str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): dict(
            archive_sha256=sha256_file(path),
            uncompressed_sha256=hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest())
        for path in (POOL, CHUNKS)
    }
    for name in ("scripts/gr1b_stage_replay.py", "ingestion/structure_graph.py",
                 "ingestion/structure_graph_projection.py", "vectordb/_base_manager.py"):
        provenance["code"]["files"][name] = sha256_file(PROJECT_ROOT / name)
    provenance["config"]["stage_replay"] = dict(
        parent_expansion_max_chars=3600, context_chars=6000, rerank_k=5,
        recovery="exact text/source permutation, reject conflicting metadata",
        gate="all reconstructed G1 texts, sources and metadata equal archived output",
        limit="exact replay supports this configuration; original model/source attestation remains unavailable",
    )
    return dict(schema_version="gr1b-stage-replay/v1.0", evidence_class="measured",
                provenance=provenance, labels=controls["labels"], exact_replays=len(archived),
                graph_chunks=len(chunks), reference_arm="archived_g1", arms=arms)


if __name__ == "__main__":
    report = build_stage_report()
    write_bucket_report(report, DEFAULT_REPORT)
    print(render_controls_table(report), end="")
