"""Exploratory query-only subset control on the frozen GR-1b pool."""
from __future__ import annotations

import gzip
import json
import re

from evaluation.ragas_eval import _normalise, context_precision
from scripts.generator_benchmark import _truncate_contexts
from scripts.gr1b_controls import (
    DEFAULT_ARCHIVE,
    PROJECT_ROOT,
    _bucket_row,
    _score_texts,
    build_controls_report,
    paired_comparison,
    sha256_file,
    write_bucket_report,
)

DEFAULT_REPORT = PROJECT_ROOT / "reports/gr/gr1b-query-control.json"


def select_query_subset(*, query: str, candidates: list[str], context_chars: int) -> list[int]:
    """Preserve capped top-five query hits; maximise query-only lexical precision."""
    if context_chars < 1 or len(candidates) < 5:
        raise ValueError("positive cap and five candidates required")
    terms = {word for word in re.findall(r"\w+", _normalise(query)) if len(word) >= 3}
    baseline = _normalise("\n".join(_truncate_contexts(candidates[:5], context_chars)))
    required = {word for word in terms if word in baseline}
    if not terms:
        return list(range(5))
    feasible = []
    for mask in range(1, 32):
        indices = [i for i in range(5) if mask & (1 << i)]
        texts = _truncate_contexts([candidates[i] for i in indices], context_chars)
        blob = _normalise("\n".join(texts))
        if all(word in blob for word in required):
            feasible.append((context_precision(query, texts, []), indices))
    best = min(feasible, key=lambda item: (-item[0], len(item[1]), item[1]))
    return best[1] if best[0] > 0 else list(range(5))


def build_query_report():
    controls = build_controls_report()
    sources = {row["case_id"]: row for row in json.loads(gzip.decompress(DEFAULT_ARCHIVE.read_bytes()))}
    baseline = controls["arms"][0]["per_case"]
    selected = []
    for before in baseline:
        source = sources[before["case_id"]]
        indices = select_query_subset(query=source["query"], candidates=source["reranked_cands"], context_chars=6000)
        texts = _truncate_contexts([source["reranked_cands"][i] for i in indices], 6000)
        after = dict(before, **_score_texts(source["query"], source["kws"], texts), candidate_indices=indices)
        after["lost_keywords"] = sorted(set(before["matched_keywords"]) - set(after["matched_keywords"]))
        selected.append(after)
    provenance = controls["provenance"]
    provenance["code"]["files"]["scripts/gr1b_query_control.py"] = sha256_file(PROJECT_ROOT / "scripts/gr1b_query_control.py")
    provenance["config"]["query_control"] = dict(
        subsets=31, order="original", context_chars=6000,
        preservation="query terms present in capped original top-five",
        objective="query-only context_precision; ties fewer indices then original indices",
        fallback="original top-five when no positive query signal",
        tuning="single prespecified exploratory control, no label-based selection or fallback",
    )
    return dict(schema_version="gr1b-query-control/v1.0", evidence_class="measured",
                provenance=provenance, labels=controls["labels"],
                baseline=controls["arms"][0]["aggregate"],
                aggregate=_bucket_row("all cases", selected), per_case=selected,
                comparison=paired_comparison(selected, baseline, samples=2000, seed=42))


if __name__ == "__main__":
    report = build_query_report()
    write_bucket_report(report, DEFAULT_REPORT)
    print(json.dumps({key: report[key] for key in ("aggregate", "comparison")}, indent=2))
