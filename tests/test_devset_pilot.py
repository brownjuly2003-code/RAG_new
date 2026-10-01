"""Reference acceptance and integrity checks for the unapproved pilot drafts."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from evaluation.devset import (
    ANSWER_LANGUAGE_REQUEST,
    RU_TO_EN_RULE,
    load_artifacts,
    parse_fact,
    ru_to_en,
    validate_claim,
    validate_fact_coverage,
    validate_governing_cue,
    validate_metadata,
    validate_source_labels,
    verify,
)
from evaluation.devset_sources import (
    ROOT,
    SEED,
    corpus_directory,
    development_footprint,
    eligible_sections,
    normalized,
    read_sources,
    sample_sections,
    sections,
    sha256,
)
from evaluation.semantic_ruler import Fact, fact_coverage


def test_devset_valid_reference_control() -> None:
    result = verify(metadata_only=True)
    assert result["cases"] == 30
    assert result["quotas"] == {
        "single-doc": 10,
        "multi-doc": 10,
        "aggregation": 4,
        "needs-refusal/clarification": 6,
    }
    assert result["styles"] == {"agent_style_A": 15, "agent_style_B": 15}
    assert result["adversarial_unanswerable"] == 10
    assert result["ru_to_en"] == 10
    assert result["families"] == 84
    assert result["singleton_families"] == 57
    assert result["pilot_families"] == 23
    assert result["case_family_components"] == 19
    assert result["case_family_component_sizes"] == [1] * 14 + [2, 2, 3, 4, 5]
    assert result["historical_H_families"] == 41
    assert result["historical_H_Hm_families"] == 42
    assert result["pilot_added_families"] == 7
    assert result["holdout_reserve_families"] == 35
    assert result["holdout_reserve_documents"] == 36
    assert result["corpus_check"] == "not_checked"


def test_devset_ru_to_en_false_reject_control() -> None:
    cases, manifest, register, corpus = load_artifacts()
    case = cases[10]
    assert "terminal shortage act" in case["required_facts"][0]["text"]
    assert "terminal shortage act" not in case["question"].casefold()
    assert ru_to_en(case) and case["flags"]["ru_to_en"]
    assert not ANSWER_LANGUAGE_REQUEST.search(case["question"])
    assert validate_metadata(cases, manifest, register, corpus)["ru_to_en"] == 10


@pytest.mark.parametrize(
    "question,text,expected",
    [
        ("Как оформить отчёт о недостаче?", "shortage report", True),
        ("Как оформить SHORTAGE REPORT?", "shortage report", False),
        ("How to file the document?", "shortage report", False),
        ("Как оформить акт?", "акт RU", False),
        ("Как оформить акт?", "акт AWB", True),
        ("Как оформить акт?", "только русские слова", False),
        ("҂ document?", "shortage report", False),
    ],
)
def test_devset_ru_to_en_derived_rule(question: str, text: str, expected: bool) -> None:
    assert ru_to_en({"question": question, "required_facts": [{"text": text}]}) is expected


def test_devset_ru_to_en_uses_only_required_facts() -> None:
    assert not ru_to_en(
        {"question": "Как оформить акт?", "required_facts": [], "critical_facts": [{"text": "AWB"}]}
    )


@pytest.mark.parametrize("index", [0, 10])
def test_devset_incorrect_ru_to_en_flag_is_rejected(index: int) -> None:
    cases, manifest, register, corpus = load_artifacts()
    cases[index]["flags"]["ru_to_en"] = not cases[index]["flags"]["ru_to_en"]
    with pytest.raises(ValueError, match="derived RU→EN flag"):
        validate_metadata(cases, manifest, register, corpus)


@pytest.mark.parametrize(
    "language_request",
    [
        "Ответ на английском.",
        "ответьте НА АНГЛИЙСКОМ языке",
        "ответ нужен по-английски",
        "Ответьте на англ.",
        "Please answer in English.",
    ],
)
def test_devset_answer_language_request_is_rejected(language_request: str) -> None:
    cases, manifest, register, corpus = load_artifacts()
    cases[0]["question"] += " " + language_request
    with pytest.raises(ValueError, match="answer-language request"):
        validate_metadata(cases, manifest, register, corpus)


def test_devset_english_qualification_question_remains_valid() -> None:
    cases, manifest, register, corpus = load_artifacts()
    assert "Уровень английского" in cases[1]["question"]
    assert not ANSWER_LANGUAGE_REQUEST.search(cases[1]["question"])
    validate_metadata(cases, manifest, register, corpus)


def test_devset_ru_to_en_registration_is_checked() -> None:
    cases, manifest, register, corpus = load_artifacts()
    assert manifest["ru_to_en_rule"] == RU_TO_EN_RULE
    manifest["ru_to_en_count"] += 1
    with pytest.raises(ValueError, match="registered RU→EN count"):
        validate_metadata(cases, manifest, register, corpus)
    manifest["ru_to_en_count"] -= 1
    manifest["ru_to_en_rule"]["version"] = "unregistered"
    with pytest.raises(ValueError, match="registered RU→EN rule"):
        validate_metadata(cases, manifest, register, corpus)


def test_devset_facts_construct_ruler_fact() -> None:
    cases, _, _, _ = load_artifacts()
    numeric = []
    for case in cases:
        for raw in case["required_facts"] + case["critical_facts"]:
            fact = parse_fact(raw)
            if fact.value is not None:
                numeric.append(fact)
                assert fact.unit and isinstance(fact.condition, str)
        if case["primary_class"] == "needs-refusal/clarification":
            assert not case["evidence_spans"] and not case["required_facts"]
            assert case["action_reason"]
    assert {fact.value for fact in numeric} >= {1, 2, 3, 5, 12, 28, 100}


def test_devset_numeric_own_gold_spans_have_no_silent_misses() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    cases, _, _, corpus = load_artifacts()
    texts = read_sources(corpus, directory)
    for case in cases:
        context = "\n".join(
            texts[s["source_id"]][s["char_start"] : s["char_end"]] for s in case["evidence_spans"]
        )
        validate_fact_coverage(
            [
                f
                for f in case["required_facts"] + case["critical_facts"]
                if f["value"] is not None and not f.get("derived")
            ],
            context,
            case["case_id"],
        )


def test_devset_numeric_correct_answer_controls() -> None:
    cases, _, _, _ = load_artifacts()
    answers = {
        "T64-06": "Оплата больничного листа в размере 100 % среднего заработка (независимо от стажа).",
        "T64-07": "Для старшего логиста — от 3 лет; владение TMS, Excel, 1С.",
        "T64-12": (
            "3–5 KPI, привязанных к стратегии подразделения; 2–3 OKR на квартал; "
            "результатов последнего performance review (оценка не ниже 3);"
        ),
        "T64-17": "Заполняется руководителем подразделения не позднее чем за 3 рабочих дня до окончания испытательного срока и согласовывается с HR-отделом.",
        "T64-19": "Ежегодный основной оплачиваемый отпуск — 28 календарных дней в рабочем году. Рабочий год — 12 месяцев непрерывной работы с одним и тем же работодателем.",
        "T64-21": "В пересечении 1 вид: AWB/HAWB.",
        "T64-22": (
            "Руководитель подразделения в течение 3 рабочих дней рассматривает заявление. "
            "HR-отдел издает приказ об отпуске не позднее чем за 3 дня до начала отпуска. "
            "Заполняется руководителем подразделения не позднее чем за 3 рабочих дня до окончания испытательного срока. "
            "Итого 3 обязанности со сроком."
        ),
        "T64-23": "2 подразделения: Бухгалтерия, Юридический отдел.",
        "T64-24": "Итого 5 документов: приказ о смене должности, приказ о переводе, личная карточка Т-2, трудовая книжка и акт передачи.",
    }
    for case in cases:
        numeric = [f for f in case["required_facts"] if f["value"] is not None]
        if numeric:
            validate_fact_coverage(numeric, answers[case["case_id"]], case["case_id"])
    # The source's unitless review score uses the registered textual path.
    score = parse_fact(cases[11]["required_facts"][2])
    assert score.value is None
    assert fact_coverage([score], answers["T64-12"]) == 1.0


def test_devset_all_minimal_reference_answers_cover_only_requested_claims() -> None:
    cases, _, _, _ = load_artifacts()
    for case in cases:
        assert case["reference_answer"].strip() and len(case["reference_answer"]) <= 700
        validate_fact_coverage(
            case["required_facts"] + case["critical_facts"],
            case["reference_answer"],
            case["case_id"],
        )
    assert [f["text"] for f in cases[8]["required_facts"]] == [
        "flight_record_category",
        "hold_condition",
        "system_of_record",
    ]
    assert [f["text"] for f in cases[20]["required_facts"]] == [
        "AWB/HAWB",
        "В пересечении 1 вид: AWB/HAWB.",
    ]
    assert [f["text"] for f in cases[22]["required_facts"]] == [
        "бухгалтерия",
        "юридический отдел",
        "2 подразделения: Бухгалтерия, Юридический отдел.",
    ]
    assert all(len(case["required_facts"]) == 2 for case in (cases[13], cases[17]))


@pytest.mark.parametrize("index", [13, 17, 22, 23])
def test_devset_claim_quote_false_reject_controls(index: int) -> None:
    cases, _, _, _ = load_artifacts()
    case = cases[index]
    for raw in case["required_facts"]:
        validate_claim(raw)
    validate_fact_coverage(case["required_facts"], case["reference_answer"], "valid reference")
    if index == 22:
        # Names are answer claims; specific table rows supply their evidence.
        assert (
            fact_coverage(
                [parse_fact(f) for f in case["required_facts"][:2]],
                "2 подразделения: Бухгалтерия, Юридический отдел.",
            )
            == 1.0
        )
        assert "Передача документов" in case["required_facts"][0]["source_quote"]
        assert "Передача документов" not in case["reference_answer"]
    if index == 23:
        derived = case["required_facts"][-1]
        assert derived["derived"] is True and "source_quote" not in derived


def test_devset_editorial_claim_not_grounded_in_quote_is_rejected() -> None:
    cases, _, _, _ = load_artifacts()
    raw = {**cases[0]["required_facts"][0], "text": "Компания оплачивает всю релокацию"}
    with pytest.raises(ValueError, match="fact claim grounding"):
        validate_claim(raw)


def test_devset_numeric_claim_text_not_grounded_in_quote_is_rejected() -> None:
    cases, manifest, register, corpus = load_artifacts()
    case = next(case for case in cases if case["case_id"] == "T64-06")
    raw = case["required_facts"][0]
    assert raw["value"] == 100 and not raw.get("derived")
    raw["text"] = "The company guarantees 999 % compensation forever"
    with pytest.raises(ValueError, match="fact claim grounding"):
        validate_claim(raw)
    with pytest.raises(ValueError, match="fact claim grounding"):
        validate_metadata(cases, manifest, register, corpus)


@pytest.mark.parametrize(
    "text", ["первый\nвторой", "- пункт", "первый - второй", "поле | значение", "а" * 161]
)
def test_devset_non_atomic_claim_is_rejected(text: str) -> None:
    cases, _, _, _ = load_artifacts()
    with pytest.raises(ValueError, match="fact claim atomicity"):
        validate_claim({**cases[0]["required_facts"][0], "text": text})


def test_devset_claim_beyond_reference_answer_is_rejected() -> None:
    cases, manifest, register, corpus = load_artifacts()
    extra = {
        **cases[0]["required_facts"][0],
        "text": "сроки выхода на новое место работы",
        "source_quote": "сроки выхода на новое место работы;",
    }
    validate_claim(extra)  # Grounded, but not asked for by the question.
    cases[0]["required_facts"].append(extra)
    with pytest.raises(ValueError, match="reference-answer coverage"):
        validate_metadata(cases, manifest, register, corpus)


@pytest.mark.parametrize("answer", ["", "x" * 701])
def test_devset_refusal_requires_nonempty_russian_reference_answer(answer: str) -> None:
    cases, manifest, register, corpus = load_artifacts()
    cases[25]["reference_answer"] = answer
    with pytest.raises(ValueError, match="reference answer"):
        validate_metadata(cases, manifest, register, corpus)


def test_devset_generic_governing_cues_have_no_case_fitted_phrases() -> None:
    from evaluation.devset import GOVERNING_CUES

    assert "требующем письменного согласия" not in sum(GOVERNING_CUES.values(), [])
    assert "должно быть" not in GOVERNING_CUES["only_if"]
    cases, _, _, _ = load_artifacts()
    assert cases[7]["required_facts"][0]["polarity"] == "allowed"
    assert cases[13]["required_facts"][1]["polarity"] == "required"


def test_devset_fact_rules_false_reject_controls() -> None:
    raw = {
        "subject": "груз",
        "text": "Груз не более 150 кг только при проверке.",
        "polarity": "не более",
        "value": 150,
        "unit": "кг",
        "condition": "при проверке",
        "tolerance": 0.0,
    }
    validate_fact_coverage([raw], raw["text"], "valid numeric reference")
    pending: list[int] = []
    assert fact_coverage([Fact(**raw)], raw["text"], needs_blind_judgment=pending) == 0.0
    assert pending == [0]  # The published matcher sends negation to blind judgment.
    validate_governing_cue({**raw, "polarity": "только при"})
    validate_governing_cue({**raw, "text": "Запрещается выпуск груза.", "polarity": "запрещено"})
    validate_governing_cue(
        {**raw, "text": "Работник обязан пройти проверку.", "polarity": "required"}
    )
    allowed = {**raw, "text": "Груз разрешено 150 кг при проверке.", "polarity": "разрешено"}
    validate_fact_coverage([allowed], allowed["text"], "valid permitted reference")
    assert fact_coverage([Fact(**allowed)], allowed["text"]) == 1.0


def test_devset_editorial_numeric_subject_is_rejected() -> None:
    cases, _, _, _ = load_artifacts()
    raw = {**cases[5]["required_facts"][0], "subject": "редакторская формулировка"}
    with pytest.raises(ValueError, match="silent fact miss"):
        validate_fact_coverage([raw], cases[5]["required_facts"][0]["text"], "numeric span")


def test_devset_prohibition_opposite_statement_is_not_covered() -> None:
    cases, _, _, _ = load_artifacts()
    fact = parse_fact(cases[17]["required_facts"][1])
    assert fact_coverage([fact], fact.text) == 1.0
    assert (
        fact_coverage(
            [fact], "Разрешено требование быть на связи вне согласованного графика без компенсации."
        )
        == 0.0
    )


def test_devset_missing_governing_cue_is_rejected() -> None:
    cases, manifest, register, corpus = load_artifacts()
    raw = cases[17]["required_facts"][1]
    raw["text"] = "требование быть на связи вне согласованного графика без компенсации."
    with pytest.raises(ValueError, match="fact governing cue"):
        validate_metadata(cases, manifest, register, corpus)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_action", "invent"),
        ("complexity", "complex"),
        ("trap_type", "other"),
        ("label_origin", "real_labelled"),
        ("approved_by", "Julia"),
        ("question", ""),
        ("primary_class", "multi-doc"),
        ("as_of", "invalid-date"),
    ],
)
def test_devset_invalid_metadata_is_rejected(field: str, value: object) -> None:
    cases, manifest, register, corpus = load_artifacts()
    cases[0][field] = value
    with pytest.raises(ValueError):
        validate_metadata(cases, manifest, register, corpus)


def test_families_holdout_cannot_include_development_family() -> None:
    cases, manifest, register, corpus = load_artifacts()
    register["holdout_reserve_families"] = [register["development_used"]["H"]["families"][0]]
    with pytest.raises(ValueError, match="dev/holdout family separation"):
        validate_metadata(cases, manifest, register, corpus)


def test_devset_explicit_alternatives_cannot_reference_unknown_span() -> None:
    cases, manifest, register, corpus = load_artifacts()
    cases[0]["required_evidence_groups"][0]["alternatives"] = ["unknown-span"]
    with pytest.raises(ValueError, match="explicit evidence alternatives"):
        validate_metadata(cases, manifest, register, corpus)


def test_families_historical_sources_are_manifest_pinned() -> None:
    cases, _, register, _ = load_artifacts()
    family_map = {
        member["source_id"]: family["family_id"]
        for family in register["families"]
        for member in family["members"]
    }
    regenerated = development_footprint(family_map, cases)
    for key, value in regenerated.items():
        assert register[key] == value
    for artifact in register["input_artifacts"]:
        assert sha256((ROOT / artifact["path"]).read_bytes()) == artifact["sha256"]
    assert register["development_used"]["H"]["matched_text_count"] == 500
    assert len(register["development_used"]["H"]["documents"]) == 117
    assert len(register["development_used"]["Hm"]["documents"]) == 13
    assert register["retrieval_pool_sensitivity_view"]["document_count"] == 200


def test_families_cross_ref_is_only_a_sensitivity_view() -> None:
    _, _, register, _ = load_artifacts()
    mapping = {
        member["source_id"]: family["family_id"]
        for family in register["families"]
        for member in family["members"]
    }
    assert len(register["cross_ref_links"]) == 560
    assert any(
        mapping[link["source_id"]] != mapping[link["target_source_id"]]
        for link in register["cross_ref_links"]
    )
    closure = register["cross_ref_closure_sensitivity_view"]
    assert closure["family_count"] == 24
    assert closure["largest_family_size"] == 171
    reserve = set(register["holdout_reserve_families"])
    assert not any(
        family["family_id"] in reserve
        for family in register["families"]
        if set(family["topics"]) & {"claims", "customs", "dangerous_goods"}
    )


def test_families_reserve_dependence_is_reproduced() -> None:
    _, _, register, _ = load_artifacts()
    mapping = {
        member["source_id"]: family["family_id"]
        for family in register["families"]
        for member in family["members"]
    }
    reserve = set(register["holdout_reserve_documents"])
    links = [
        link
        for link in register["cross_ref_links"]
        if (link["source_id"] in reserve) != (link["target_source_id"] in reserve)
    ]
    linked = {
        mapping[name]
        for link in links
        for name in (link["source_id"], link["target_source_id"])
        if name in reserve
    }
    remaining = set(register["holdout_reserve_families"]) - linked
    documents = sorted(name for name, family in mapping.items() if family in remaining)
    dependence = register["cross_ref_dependence"]
    assert len(links) == dependence["development_reserve_link_count"] == 105
    assert len(linked) == dependence["linked_reserve_family_count"] == 25
    assert sorted(linked) == dependence["linked_reserve_families"]
    assert len(remaining) == dependence["unlinked_reserve_family_count"] == 10
    assert len(documents) == dependence["unlinked_reserve_document_count"] == 10
    assert sorted(remaining) == dependence["unlinked_reserve_families"]
    assert documents == dependence["unlinked_reserve_documents"]
    assert sum(name.startswith("01_hr_pol_") for name in documents) == 9
    assert "02_hr_tmp_job_description_accountant.md" in documents
    from evaluation.semantic_ruler import family_clusters

    literal = family_clusters(
        {
            name: [family, "_".join(name.split("_")[:2])]
            + [
                mapping[partner]
                for family_entry in register["families"]
                for member in family_entry["members"]
                if member["source_id"] == name
                for partner in member["basis"]["cross_ref_partners"]
            ]
            for name, family in mapping.items()
        }
    )
    assert len(literal) == dependence["literal_folder_topic_cross_ref_family_count"] == 1


def test_devset_historical_footprint_changes_are_detected() -> None:
    cases, manifest, register, corpus = load_artifacts()
    register["development_used"]["H"]["matched_text_count"] = 499
    with pytest.raises(ValueError, match="recomputed development footprint"):
        validate_metadata(cases, manifest, register, corpus)


def test_families_pin_changes_are_detected() -> None:
    cases, manifest, register, corpus = load_artifacts()
    register["input_artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="recomputed development footprint"):
        validate_metadata(cases, manifest, register, corpus)


def test_devset_source_reader_accepts_valid_utf8_and_rejects_changed_bytes(tmp_path: Path) -> None:
    raw = "# Источник\r\n## Правило\r\nНельзя подставлять массу по догадке.\r\n".encode()
    path = tmp_path / "reference.md"
    path.write_bytes(raw)
    manifest = {"files": [{"name": path.name, "sha256": sha256(raw)}]}
    texts = read_sources(manifest, tmp_path)
    assert texts[path.name].encode() == raw
    section = sections(path.name, texts[path.name])[0]
    assert section["section_path"] == ["Источник", "Правило"]
    assert "Нельзя" in texts[path.name][section["char_start"] : section["char_end"]]
    path.write_bytes(raw + b"changed")
    with pytest.raises(ValueError, match="corpus file SHA mismatch"):
        read_sources(manifest, tmp_path)


def test_devset_full_source_verification() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(
            f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR; metadata verified separately"
        )
    result = verify(directory=directory)
    assert result["corpus_check"] == "verified"
    assert result["spans"] == 38


def test_devset_changed_source_revision_is_not_a_migration() -> None:
    cases, manifest, register, corpus = load_artifacts()
    cases = copy.deepcopy(cases)
    cases[0]["evidence_spans"][0]["source_revision"] = "0" * 64
    with pytest.raises(ValueError, match="span source address"):
        validate_metadata(cases, manifest, register, corpus)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("text_sha256", "0" * 64, "span text SHA mismatch"),
        ("char_start", 1, "source section address/offsets"),
        ("normalized_text", "wrong source text", "normalized span text"),
    ],
)
def test_devset_corrupted_source_span_rejected(field: str, value: object, reason: str) -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    cases, _, _, corpus = load_artifacts()
    texts = read_sources(corpus, directory)
    validate_source_labels(cases, texts)
    cases[0]["evidence_spans"][0][field] = value
    with pytest.raises(ValueError, match=reason):
        validate_source_labels(cases, texts)


def _specificity_reference() -> tuple[dict[str, str], dict[str, Any], str]:
    shared = "Shared template requires the generic approval of the process owner."
    texts = {
        f"reference-{index}.md": (
            "# Reference\n## Operational rule\n"
            f"Shipment {index} uses its individually assigned inspection register and terminal control procedure before release.\n"
            f"Dispatch {index} records its own custody timeline and reconciles the airport-specific delivery receipt with the warehouse ledger.\n"
            + shared
            + "\n"
        )
        for index in range(4)
    }
    section = sections("reference-0.md", texts["reference-0.md"])[0]
    text = texts["reference-0.md"][section["char_start"] : section["char_end"]]
    span = {
        **section,
        "text_sha256": sha256(text.encode()),
        "normalized_text": normalized(text),
    }
    case = {
        "seed_selected_source_section": section,
        "partner_sections": [],
        "evidence_spans": [span],
        "required_facts": [
            {
                "subject": "shipment",
                "text": text.splitlines()[1],
                "source_quote": text.splitlines()[1],
                "polarity": "allowed",
                "value": None,
                "unit": "",
                "condition": "",
                "tolerance": 0.0,
            }
        ],
        "critical_facts": [],
    }
    return texts, case, shared


def test_devset_document_specific_false_reject_control() -> None:
    texts, case, _ = _specificity_reference()
    # Exactly one of three lines is shared: the section and its specific passage are valid.
    validate_source_labels([case], texts)
    section = case["seed_selected_source_section"]
    assert section in eligible_sections(texts)


def test_devset_template_anchored_span_is_rejected() -> None:
    texts, case, shared = _specificity_reference()
    span = case["evidence_spans"][0]
    start = texts[span["source_id"]].index(shared)
    span.update(
        char_start=start,
        char_end=start + len(shared),
        text_sha256=sha256(shared.encode()),
        normalized_text=normalized(shared),
    )
    case["required_facts"][0].update(text=shared, source_quote=shared)
    with pytest.raises(ValueError, match="template-anchored evidence span"):
        validate_source_labels([case], texts)


@pytest.mark.parametrize("documents,accepted", [(3, True), (4, False)])
def test_devset_fact_document_specificity_boundary(documents: int, accepted: bool) -> None:
    texts, case, shared = _specificity_reference()
    texts = dict(list(texts.items())[:documents])
    case["required_facts"][0].update(text=shared, source_quote=shared)
    case["critical_facts"] = copy.deepcopy(case["required_facts"])
    if accepted:
        validate_source_labels([case], texts)
    else:
        with pytest.raises(ValueError, match="template-anchored fact"):
            validate_source_labels([case], texts)


def test_devset_identical_span_in_two_documents_is_accepted() -> None:
    texts, case, _ = _specificity_reference()
    texts = {"reference-0.md": texts["reference-0.md"], "copy.md": texts["reference-0.md"]}
    validate_source_labels([case], texts)


def test_devset_common_name_with_specific_quote_is_accepted() -> None:
    texts, case, _ = _specificity_reference()
    raw = case["required_facts"][0]
    raw["text"] = "inspection register"
    assert sum(raw["text"] in text for text in texts.values()) == 4
    validate_source_labels([case], texts)
    validate_fact_coverage([raw], "inspection register", "valid name")


def test_devset_quote_must_be_contiguous_verbatim_own_span_text() -> None:
    texts, case, _ = _specificity_reference()
    raw = case["required_facts"][0]
    raw["text"] = "inspection register"
    raw["source_quote"] = raw["source_quote"].replace("Shipment 0", "Shipment 1")
    validate_claim(raw)
    with pytest.raises(ValueError, match="fact supporting quote"):
        validate_source_labels([case], texts)


def test_devset_derived_fact_without_quote_passes_source_checks() -> None:
    texts, case, _ = _specificity_reference()
    raw = {
        "subject": "documents",
        "text": "Итого 4 documents",
        "polarity": "allowed",
        "value": 4,
        "unit": "documents",
        "condition": "",
        "tolerance": 0.0,
        "derived": True,
    }
    case["required_facts"].append(raw)
    validate_source_labels([case], texts)
    validate_fact_coverage([raw], raw["text"], "valid derived")
    with pytest.raises(ValueError, match="derived fact has no quote"):
        validate_claim({**raw, "source_quote": "irrelevant"})


def test_devset_eligible_frame_excludes_meta_and_line_templates() -> None:
    texts, case, shared = _specificity_reference()
    section = case["seed_selected_source_section"]
    body = texts["reference-0.md"][section["char_start"] : section["char_end"]]
    for title in ("История изменений", "Связанные документы", "Порядок пересмотра и актуализации"):
        texts["reference-0.md"] += "\n## " + title + "\n" + body
    assert eligible_sections(texts) == [
        sections(name, text)[0] for name, text in sorted(texts.items())
    ]
    for name in texts:
        texts[name] += "\n## Repeated content\n" + (
            "  SHARED   TEMPLATE requires the generic approval of the process owner.\n" * 3
        )
    assert all(s["section_path"][-1] != "Repeated content" for s in eligible_sections(texts))
    assert normalized(shared) == normalized(
        "  SHARED   TEMPLATE requires the generic approval of the process owner."
    )


def test_devset_seed_section_must_be_eligible() -> None:
    texts, case, shared = _specificity_reference()
    for name in texts:
        texts[name] = "# Reference\n## Operational rule\n" + (shared + "\n") * 3
    case["seed_selected_source_section"] = sections("reference-0.md", texts["reference-0.md"])[0]
    with pytest.raises(ValueError, match="section not in eligible frame"):
        validate_source_labels([case], texts)


def test_devset_filtered_draw_replays_from_corpus() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    cases, manifest, _, corpus = load_artifacts()
    texts = read_sources(corpus, directory)
    count, drawn = sample_sections(texts, SEED)
    assert count == manifest["sampling"]["candidate_count"] == 982
    assert drawn == manifest["sampling"]["drawn_sections"]
    assert drawn == [c["seed_selected_source_section"] for c in cases]
    frame = eligible_sections(texts)
    assert all(
        {k: section[k] for k in ("source_id", "section_path", "char_start", "char_end")} in frame
        for case in cases
        for section in [case["seed_selected_source_section"]] + case["partner_sections"]
    )
