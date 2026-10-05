"""Gold metrics of a verified case on what one arm retrieved.

A verified case (``evaluation/devset.py``) carries gold spans, required evidence groups and
required facts. This module reads them against an arm's texts — the pool its reranker received
and the documents it sent to the generator — and gives the three gold metrics of
``docs/specs/semantic-precision-metrics.md``: ``evidence_recall_pool``,
``all_evidence_coverage`` and ``fact_coverage``.

A span is found by its text, never by offsets: these texts have none that describe them. A chunk
of the index carries its document and its headings and no offsets. A sent document is a seed
chunk with neighbouring sections joined to it (``HybridRetriever._expand_parents``): it carries
the address of its seed, and no single range of the source covers its text. So a text holds a
span when it comes from the span's document in the span's corpus version and contains the span's
normalised text whole. The pool is read by the same rule, so that a span found in the pool and a
span found in the sent context mean one thing. The rule cannot tell the labelled place of a span
from another place of its document that holds the same text; the pilot names the spans that
several chunks hold whole. A span that no chunk of the index holds whole is found in no pool: the
metric is bounded by the labels and by the chunking, equally for every arm.

Fact presence follows the rule the facts were labelled under (``pilot-claim-quote-v2``): a fact is
in a context when its ``source_quote`` is contained in the text of one sent document; a derived
fact, which no span states, when every required evidence group of its case is satisfied.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from evaluation import semantic_ruler as ruler

MATCH_RULE = "verified-gold/text-containment-v1"
METRICS = ("evidence_recall_pool", "all_evidence_coverage", "fact_coverage")


def gold_spans(case: Mapping[str, Any]) -> dict[str, ruler.GoldSpan]:
    """The gold spans of a case by id, without offsets: the matcher reads their text."""
    return {
        span["span_id"]: ruler.GoldSpan(
            span["source_id"], span["corpus_version"], None, None, span["normalized_text"]
        )
        for span in case["evidence_spans"]
    }


def evidence_texts(
    documents: Sequence[Mapping[str, Any]], corpus_version: str
) -> list[ruler.EvidenceChunk]:
    """An arm's texts as the matcher reads them; a text of no named document holds no span."""
    return [
        ruler.EvidenceChunk(str(document.get("source_id") or ""), corpus_version, document["text"])
        for document in documents
    ]


def quote_present(quote: str, sent: Sequence[ruler.EvidenceChunk]) -> bool:
    """The registered textual matcher, one sent document at a time."""
    probe = [ruler.Fact(subject="", polarity="", text=quote)]
    return any(ruler.fact_coverage(probe, document.text) == 1.0 for document in sent)


def case_metrics(
    case: Mapping[str, Any],
    pool: Sequence[ruler.EvidenceChunk],
    sent: Sequence[ruler.EvidenceChunk],
) -> dict[str, Any]:
    """The gold metrics of one case in one arm, with what was found behind each of them.

    A metric is None when the case has nothing to measure it on: no gold span, no evidence
    group, no fact.
    """
    spans = gold_spans(case)
    groups = [
        [spans[span_id] for span_id in group["alternatives"]]
        for group in case["required_evidence_groups"]
    ]
    coverage = ruler.all_evidence_coverage(groups, sent)

    def present(fact: Mapping[str, Any]) -> bool:
        if fact.get("derived"):
            return coverage == 1.0
        return quote_present(fact["source_quote"], sent)

    facts = [present(fact) for fact in case["required_facts"]]
    return {
        "evidence_recall_pool": ruler.evidence_recall_pool(list(spans.values()), pool),
        "all_evidence_coverage": coverage,
        "fact_coverage": sum(facts) / len(facts) if facts else None,
        "spans_in_pool": [
            span_id
            for span_id, span in spans.items()
            if ruler.evidence_recall_pool([span], pool) == 1.0
        ],
        "spans_in_sent": [
            span_id
            for span_id, span in spans.items()
            if ruler.evidence_recall_pool([span], sent) == 1.0
        ],
        "facts_in_context": facts,
        "critical_facts_in_context": [present(fact) for fact in case["critical_facts"]],
    }


def critical_fact_losses(control: Mapping[str, Any], arm: Mapping[str, Any]) -> int:
    """Critical facts of one case that the control's context holds and the arm's does not."""
    return sum(
        held and not kept
        for held, kept in zip(
            control["critical_facts_in_context"], arm["critical_facts_in_context"], strict=True
        )
    )
