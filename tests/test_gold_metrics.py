"""Gold metrics of a verified case: spans found by text, facts by their quotes."""

from typing import Any

from evaluation import gold_metrics as gold
from evaluation import semantic_ruler as ruler

CORPUS = "corpus-v1"
ACCEPT = "Смена принимает груз по накладной и сверяет число мест с манифестом."
ACT = "Акт осмотра упаковки подписывает кладовщик склада."
OTHER = "Журнал смены хранится у начальника смены три года."


def span(span_id: str, source: str, text: str) -> dict[str, Any]:
    return {
        "span_id": span_id,
        "source_id": source,
        "source_revision": "r1",
        "corpus_version": CORPUS,
        "char_start": 10,
        "char_end": 10 + len(text),
        "normalized_text": text,
    }


def fact(quote: str | None, **extra: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "subject": "смена",
        "text": "формулировка ответа",
        "polarity": "allowed",
        "value": None,
        "unit": "",
        "condition": "",
        "tolerance": 0.0,
        **extra,
    }
    if quote is not None:
        record["source_quote"] = quote
    return record


def case(**changes: Any) -> dict[str, Any]:
    accept, act = fact("принимает груз по накладной"), fact("подписывает кладовщик")
    record = {
        "case_id": "C1",
        "evidence_spans": [span("E1", "a.md", ACCEPT), span("E2", "b.md", ACT)],
        "required_evidence_groups": [
            {"group_id": "G1", "alternatives": ["E1"]},
            {"group_id": "G2", "alternatives": ["E2"]},
        ],
        "required_facts": [accept, act],
        "critical_facts": [act],
    }
    return {**record, **changes}


def texts(*documents: tuple[str | None, str], corpus: str = CORPUS) -> list[ruler.EvidenceChunk]:
    return gold.evidence_texts(
        [{"source_id": source, "text": text} for source, text in documents], corpus
    )


def test_a_span_is_found_by_its_text_in_its_own_document_and_corpus_version():
    spans = list(gold.gold_spans(case()).values())
    assert ruler.evidence_recall_pool(spans, texts(("a.md", ACCEPT), ("b.md", OTHER))) == 0.5
    # The same words in another document, or in another version of the corpus, are not the span.
    assert ruler.evidence_recall_pool(spans, texts(("c.md", ACCEPT), ("c.md", ACT))) == 0.0
    assert ruler.evidence_recall_pool(spans, texts(("a.md", ACCEPT), corpus="corpus-v2")) == 0.0
    # Case and white space do not matter; a part of the span is not the span.
    assert (
        ruler.evidence_recall_pool(spans, texts(("a.md", ACCEPT.upper().replace(" ", "\n")))) == 0.5
    )
    assert ruler.evidence_recall_pool(spans, texts(("a.md", ACCEPT[:40]))) == 0.0


def test_offsets_of_a_label_are_not_read():
    spans = gold.gold_spans(case())
    assert {(s.char_start, s.char_end) for s in spans.values()} == {(None, None)}
    assert spans["E1"].normalized_text == ACCEPT and spans["E2"].source_id == "b.md"


def test_an_expanded_document_holds_a_span_wherever_the_join_put_it():
    head, tail = ACCEPT[:33], ACCEPT[34:]
    assert ACCEPT == f"{head} {tail}"
    expanded = f"{OTHER}\n\n{head}\n\n{tail}\n\n{OTHER}"
    measured = gold.case_metrics(case(), texts(), texts(("a.md", expanded), ("b.md", ACT)))
    assert measured["spans_in_sent"] == ["E1", "E2"]
    assert measured["all_evidence_coverage"] == 1.0


def test_metrics_of_a_case_and_what_stands_behind_them():
    measured = gold.case_metrics(
        case(),
        texts(("a.md", OTHER), ("a.md", ACCEPT), ("b.md", OTHER)),
        texts(("a.md", f"{OTHER}\n\n{ACCEPT}")),
    )
    assert measured == {
        "evidence_recall_pool": 0.5,
        "all_evidence_coverage": 0.0,
        "fact_coverage": 0.5,
        "spans_in_pool": ["E1"],
        "spans_in_sent": ["E1"],
        "facts_in_context": [True, False],
        "critical_facts_in_context": [False],
    }


def test_a_group_is_satisfied_by_any_of_its_alternatives():
    either = case(
        required_evidence_groups=[{"group_id": "G1", "alternatives": ["E1", "E2"]}],
    )
    assert gold.case_metrics(either, texts(), texts(("b.md", ACT)))["all_evidence_coverage"] == 1.0
    assert (
        gold.case_metrics(either, texts(), texts(("b.md", OTHER)))["all_evidence_coverage"] == 0.0
    )


def test_a_quote_is_read_in_one_sent_document_at_a_time():
    quote = "по накладной и сверяет число мест"
    whole = texts(("a.md", ACCEPT))
    halves = texts(("a.md", ACCEPT[:33]), ("a.md", ACCEPT[34:]))
    assert gold.quote_present(quote, whole)
    assert not gold.quote_present(quote, halves)
    assert gold.quote_present(quote.upper(), texts((None, f"  {ACCEPT}  ")))


def test_a_text_of_no_named_document_holds_no_span_and_may_hold_a_quote():
    measured = gold.case_metrics(case(), texts((None, ACCEPT)), texts((None, ACCEPT)))
    assert measured["evidence_recall_pool"] == 0.0
    assert measured["spans_in_sent"] == []
    assert measured["facts_in_context"] == [True, False]


def test_a_derived_fact_is_present_when_every_group_is_satisfied():
    counted = fact(None, derived=True, value=2, unit="документа")
    aggregation = case(required_facts=[fact("принимает груз по накладной"), counted])
    both = texts(("a.md", ACCEPT), ("b.md", ACT))
    one = texts(("a.md", ACCEPT))
    assert gold.case_metrics(aggregation, both, both)["facts_in_context"] == [True, True]
    assert gold.case_metrics(aggregation, both, one)["facts_in_context"] == [True, False]
    assert gold.case_metrics(aggregation, both, one)["fact_coverage"] == 0.5


def test_a_case_without_gold_has_no_gold_metric():
    refusal = case(
        evidence_spans=[], required_evidence_groups=[], required_facts=[], critical_facts=[]
    )
    measured = gold.case_metrics(refusal, texts(("a.md", ACCEPT)), texts(("a.md", ACCEPT)))
    assert [measured[metric] for metric in gold.METRICS] == [None, None, None]
    assert measured["facts_in_context"] == [] and measured["spans_in_pool"] == []


def test_critical_fact_losses_count_what_the_control_held_and_the_arm_dropped():
    both = texts(("a.md", ACCEPT), ("b.md", ACT))
    one = texts(("a.md", ACCEPT))
    control = gold.case_metrics(case(), both, both)
    arm = gold.case_metrics(case(), both, one)
    assert control["critical_facts_in_context"] == [True]
    assert gold.critical_fact_losses(control, arm) == 1
    assert gold.critical_fact_losses(arm, control) == 0
    assert gold.critical_fact_losses(control, control) == 0
