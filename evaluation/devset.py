"""Verify the T-64 pilot drafts; this does not approve labels or open a gate."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from evaluation.devset_sources import (
    ROOT,
    SAMPLING_ALGORITHM,
    SECTION_VERSION,
    SEED,
    SPECIFICITY_RULE,
    build_families,
    corpus_directory,
    development_footprint,
    eligible_sections,
    normalized,
    read_sources,
    sample_sections,
    sections,
    sha256,
    topic,
)
from evaluation.semantic_ruler import (
    POLARITY_LEXICON,
    Fact,
    _normalized,
    fact_coverage,
    family_clusters,
)

QUOTAS = {"single-doc": 10, "multi-doc": 10, "aggregation": 4, "needs-refusal/clarification": 6}
ACTIONS = {"answer", "correct_premise", "clarify", "refuse", "escalate"}
TRAPS = {
    "false_premise",
    "out_of_corpus",
    "outdated_rule",
    "conflicting_documents",
    "dangerous_goods",
}
STYLES = {"agent_style_A": 15, "agent_style_B": 15}
FACT_FIELDS = {"subject", "text", "polarity", "value", "unit", "condition", "tolerance"}
GOVERNING_CUES = {
    "forbidden": [
        "запрещается",
        "запрещено",
        "запрещает",
        "не допускается",
        "недопустимо",
        "нельзя",
        "не вправе",
        "не может",
        "не применяется",
    ],
    "required": [
        "обязан",
        "обязана",
        "обязаны",
        "обязательно",
        "должен",
        "должна",
        "должны",
        "должно",
        "должно быть",
        "необходимо",
        "требуется",
        "не позднее",
    ],
    "only_if": ["только при", "только если", "только после", "при условии", "если", "в случае"],
}
FACT_LABEL_RULE = {
    "version": "pilot-claim-quote-v2",
    "matcher": "evaluation.semantic_ruler.fact_coverage",
    "claim_normalization": "casefold plus whitespace collapse; punctuation retained",
    "claim": "atomic: no newline, list marker or table pipe; at most 160 characters",
    "grounding": "text claim is quote substring or generic governing cue + space/colon-space + quote substring",
    "source_quote": "contiguous verbatim excerpt of an own gold span; at most 300 characters",
    "presence": "context presence (2.5) matches source_quote in the sent context; answer presence matches text in the answer",
    "specificity_change": "The fact clause moved from text to source_quote: claims are answer wording (e.g. department names); specificity belongs to evidence.",
    "numeric_span_coverage": "1.0 or explicit needs_blind_judgment; derived claims excluded",
    "reference_answer": "Russian minimal answer to exactly the question; at most 700 characters; all claims covered or explicit needs_blind_judgment",
    "derived": "numeric aggregation result absent from source spans",
    "governing_cues": GOVERNING_CUES,
}
CASE_FIELDS = {
    "case_id",
    "question",
    "reference_answer",
    "primary_class",
    "question_origin",
    "label_origin",
    "evidence_class",
    "status",
    "approved_by",
    "seed_selected_source_section",
    "partner_sections",
    "documents",
    "flags",
    "trap_type",
    "expected_action",
    "complexity",
    "as_of",
    "authority_source",
    "wrong_answer_severity",
    "evidence_spans",
    "required_evidence_groups",
    "required_facts",
    "critical_facts",
    "action_reason",
    "aggregation",
}
FLAGS = {"ru_to_en", "numeric", "safety_critical", "adversarial_unanswerable"}
FOLDERS = {"01_hr", "02_hr", "03_legal", "04_legal", "05_tlog", "06_comp", "07_faq", "external"}
RU_TO_EN_RULE = {
    "version": "cyrillic-query-missing-latin-fact-token-v1",
    "question_contains": "Cyrillic letter",
    "fact_scope": "required_facts.text",
    "latin_token_pattern": "[A-Za-z]{3,}",
    "token_absence": "case-insensitive substring absent from question",
}
ANSWER_LANGUAGE_REQUEST = re.compile(
    r"на\s+английском\b|по[\s-]*английски\b|на\s+англ\.|\bin\s+English\b", re.IGNORECASE
)


def ru_to_en(case: dict[str, Any]) -> bool:
    question = case["question"]
    return any("\u0400" <= char <= "\u04ff" and char.isalpha() for char in question) and any(
        token.casefold() not in question.casefold()
        for fact in case["required_facts"]
        for token in re.findall(RU_TO_EN_RULE["latin_token_pattern"], fact["text"])
    )


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_fact(raw: dict[str, Any]) -> Fact:
    return Fact(**{key: raw[key] for key in FACT_FIELDS})


def validate_governing_cue(raw: dict[str, Any]) -> None:
    polarity = next(
        (key for key, markers in POLARITY_LEXICON.items() if raw["polarity"] in markers),
        raw["polarity"],
    )
    if polarity in GOVERNING_CUES:
        require(
            any(
                re.search(r"(?<!\w)" + re.escape(cue) + r"(?!\w)", normalized(raw["text"]))
                for cue in GOVERNING_CUES[polarity]
            ),
            "fact governing cue",
        )


def validate_fact_coverage(facts: list[dict[str, Any]], context: str, label: str) -> None:
    for raw in facts:
        pending: list[int] = []
        score = fact_coverage([parse_fact(raw)], context, needs_blind_judgment=pending)
        require(score == 1.0 or pending == [0], label + ": silent fact miss")


def validate_claim(raw: dict[str, Any]) -> None:
    text = raw["text"]
    require(
        isinstance(text, str)
        and text.strip()
        and len(text) <= 160
        and not any(marker in text for marker in ("\n", "\r", "|", "- "))
        and not re.match(r"\s*(?:[*+•]\s|\d+[.)]\s)", text),
        "fact claim atomicity",
    )
    validate_governing_cue(raw)
    if raw.get("derived"):
        require("source_quote" not in raw, "derived fact has no quote")
        return
    quote = raw.get("source_quote", "")
    require(isinstance(quote, str) and quote.strip() and len(quote) <= 300, "fact source quote")
    claim, evidence = _normalized(text), _normalized(quote)
    grounded = claim in evidence
    for cues in GOVERNING_CUES.values():
        for cue in cues:
            for separator in (" ", ": "):
                prefix = cue + separator
                if claim.startswith(prefix) and claim[len(prefix) :].strip():
                    grounded |= (
                        re.search(r"(?<!\w)" + re.escape(cue) + r"(?!\w)", evidence) is not None
                        and claim[len(prefix) :] in evidence
                    )
    require(grounded, "fact claim grounding")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _section(section: dict[str, Any], revisions: dict[str, str]) -> None:
    require(section["source_id"] in revisions, "unregistered section document")
    require(
        isinstance(section["section_path"], list)
        and section["section_path"]
        and all(isinstance(h, str) and h.strip() for h in section["section_path"]),
        "section heading path",
    )
    require(
        type(section["char_start"]) is int
        and type(section["char_end"]) is int
        and 0 <= section["char_start"] < section["char_end"],
        "section offsets",
    )


def validate_metadata(
    cases: list[dict[str, Any]],
    manifest: dict[str, Any],
    register: dict[str, Any],
    corpus: dict[str, Any],
) -> dict[str, Any]:
    revisions = {f["name"]: f["sha256"] for f in corpus["files"]}
    require(len(revisions) == corpus["file_count"] == 201, "corpus manifest count")
    require(manifest["schema_version"] == "devset-pilot-v2", "schema version")
    require(manifest["generator"] == "gpt-6.1-sol", "registered generator")
    require(manifest["seed"] == SEED, "registered seed")
    require(
        manifest["sampling"]["algorithm"] == SAMPLING_ALGORITHM
        and manifest["sampling"]["section_parser"] == SECTION_VERSION,
        "sampling algorithm",
    )
    require(manifest["sampling"]["eligibility_rule"] == SPECIFICITY_RULE, "specificity rule")
    require(manifest["ru_to_en_rule"] == RU_TO_EN_RULE, "registered RU→EN rule")
    require(manifest["fact_label_rule"] == FACT_LABEL_RULE, "registered fact label rule")
    require(
        register["status"]
        == "draft — owner confirms with the first approved batch (spec: document family)",
        "draft family status",
    )
    require(
        register["corpus_sha256"] == manifest["corpus_sha256"] == corpus["corpus_sha256"],
        "corpus version",
    )
    require(register["excluded_from_judges"] == manifest["excluded_from_judges"] == [], "D10")
    family_map = {}
    family_ids = set()
    registered_topics: set[str] = set()
    require(register["cluster_unit"] == "topic only: devset_sources.topic()", "topic cluster unit")
    partners: dict[str, set[str]] = {name: set() for name in revisions}
    for link in register["cross_ref_links"]:
        left, right = link["source_id"], link["target_source_id"]
        require(left in revisions and right in revisions and left != right, "cross_ref sources")
        partners[left].add(right)
        partners[right].add(left)
    for family in register["families"]:
        require(family["family_id"] not in family_ids and family["members"], "family identity")
        family_ids.add(family["family_id"])
        names = [member["source_id"] for member in family["members"]]
        topics = {topic(name) for name in names}
        require(len(topics) == 1 and not topics & registered_topics, "one family per topic")
        registered_topics.update(topics)
        require(
            family["topics"] == sorted(topics)
            and names == sorted(names)
            and family["family_id"] == "family-" + sha256("\n".join(names).encode())[:12],
            "deterministic topic family identity",
        )
        for member in family["members"]:
            name = member["source_id"]
            require(name in revisions and name not in family_map, "unique family membership")
            require(member["basis"]["topic"] == topic(name), "topic membership basis")
            require(
                member["basis"]["cross_ref_partners"] == sorted(partners[name]),
                "cross_ref partner basis",
            )
            family_map[name] = family["family_id"]
    require(set(family_map) == set(revisions), "family corpus coverage")
    closure = family_clusters(
        {name: [family_map[name]] + [family_map[p] for p in partners[name]] for name in revisions}
    )
    require(
        register["cross_ref_closure_sensitivity_view"]
        == {
            "basis": "topic families transitively merged by cross_ref; not the cluster unit",
            "family_count": len(closure),
            "largest_family_size": max(map(len, closure)),
        },
        "cross_ref closure sensitivity",
    )
    coarse = register["coarse_sensitivity_view"]
    require(set(coarse) == FOLDERS, "eight-folder sensitivity view")
    for folder, names in coarse.items():
        require(
            names == sorted(n for n in revisions if n.startswith(folder + "_")),
            "coarse sensitivity membership",
        )
    dev_families = set()
    require(
        {"H", "Hm", "P1b/P2", "loss_map_2.5", "pilot_T64"} <= set(register["development_used"]),
        "historical development register",
    )
    for usage in register["development_used"].values():
        require(set(usage["families"]) <= family_ids, "unknown development family")
        if "documents" in usage:
            require(set(usage["documents"]) <= set(revisions), "unknown historical document")
            require(
                set(usage["families"]) == {family_map[n] for n in usage["documents"]},
                "historical family mapping",
            )
        dev_families.update(usage["families"])
    reserve = register["holdout_reserve_families"]
    require(set(reserve) == family_ids - dev_families, "dev/holdout family separation")
    require(not set(reserve) & dev_families, "holdout contamination")
    reserve_documents = sorted(name for name, family in family_map.items() if family in reserve)
    require(register["holdout_reserve_documents"] == reserve_documents, "holdout reserve documents")
    require(
        manifest["holdout_reserve_status"] == register["holdout_reserve_status"],
        "holdout reserve status",
    )
    drawn = manifest["sampling"]["drawn_sections"]
    require(len(cases) == len(drawn) == 30, "30 drafts and draws")
    require(len({c["case_id"] for c in cases}) == 30, "unique case ids")
    mapping = {}
    polarities = {p for markers in POLARITY_LEXICON.values() for p in markers} | set(GOVERNING_CUES)
    for case, selected in zip(cases, drawn, strict=True):
        require(CASE_FIELDS <= case.keys(), "required case fields")
        require(isinstance(case["question"], str) and case["question"].strip(), "question")
        answer = case["reference_answer"]
        require(
            isinstance(answer, str)
            and answer.strip()
            and len(answer) <= 700
            and re.search(r"[А-Яа-яЁё]", answer),
            "reference answer",
        )
        require(not ANSWER_LANGUAGE_REQUEST.search(case["question"]), "answer-language request")
        require(
            case["primary_class"] in QUOTAS and case["expected_action"] in ACTIONS,
            "class/action enum",
        )
        require(case["question_origin"] in STYLES, "question origin")
        require(
            all(
                case[key] == "agent_labelled"
                for key in ("label_origin", "evidence_class", "status")
            )
            and case["approved_by"] is None,
            "unapproved agent draft",
        )
        require(case["complexity"] in {"simple", "not_simple"}, "complexity enum")
        require(
            case["wrong_answer_severity"] in {"low", "moderate", "high", "critical"},
            "severity enum",
        )
        date.fromisoformat(case["as_of"])
        require(case["trap_type"] is None or case["trap_type"] in TRAPS, "trap enum")
        require(
            set(case["flags"]) == FLAGS and all(type(v) is bool for v in case["flags"].values()),
            "boolean subset flags",
        )
        require(case["seed_selected_source_section"] == selected, "seed-selected source")
        chosen = [selected] + case["partner_sections"]
        for section in chosen:
            _section(section, revisions)
        for section in case["partner_sections"]:
            require(
                isinstance(section["selection_reason"], str)
                and section["selection_reason"].strip(),
                "partner selection reason",
            )
        documents = {s["source_id"] for s in chosen}
        require(case["documents"] == sorted(documents), "case document list")
        mapping[case["case_id"]] = sorted({family_map[n] for n in documents})
        authority = case["authority_source"]
        require({a["source_id"] for a in authority} == documents, "rule authority sources")
        require(
            all(
                a["source_revision"] == revisions[a["source_id"]] and a["scope"] for a in authority
            ),
            "rule authority revisions/scope",
        )
        for raw in case["required_facts"] + case["critical_facts"]:
            require(
                FACT_FIELDS <= raw.keys() <= FACT_FIELDS | {"derived", "source_quote"},
                "Fact field names",
            )
            parsed = parse_fact(raw)
            validate_claim(raw)
            if "derived" in raw:
                require(
                    raw["derived"] is True
                    and case["primary_class"] == "aggregation"
                    and parsed.value == case["aggregation"]["value"],
                    "derived aggregation claim",
                )
            require(
                parsed.subject and parsed.text and parsed.polarity in polarities,
                "Fact text/subject/polarity",
            )
            require(
                type(parsed.tolerance) in (int, float)
                and math.isfinite(parsed.tolerance)
                and parsed.tolerance >= 0,
                "fact tolerance",
            )
            if parsed.value is not None:
                require(
                    type(parsed.value) in (int, float)
                    and math.isfinite(parsed.value)
                    and parsed.unit
                    and isinstance(parsed.condition, str),
                    "numeric claim",
                )
        require(
            all(f in case["required_facts"] for f in case["critical_facts"]), "critical fact subset"
        )
        validate_fact_coverage(
            case["required_facts"] + case["critical_facts"],
            answer,
            "reference-answer coverage: " + case["case_id"],
        )
        require(
            case["flags"]["numeric"] == any(f["value"] is not None for f in case["required_facts"]),
            "numeric subset flag",
        )
        require(case["flags"]["ru_to_en"] == ru_to_en(case), "derived RU→EN flag")
        unresolvable = case["primary_class"] == "needs-refusal/clarification"
        require(
            case["flags"]["adversarial_unanswerable"] == bool(case["trap_type"] or unresolvable),
            "adversarial/unanswerable flag",
        )
        if unresolvable:
            require(
                case["expected_action"] in {"clarify", "refuse", "escalate"}
                and isinstance(case["action_reason"], str)
                and case["action_reason"].strip(),
                "missing-answer action/reason",
            )
            require(
                not case["evidence_spans"]
                and not case["required_evidence_groups"]
                and not case["required_facts"]
                and not case["critical_facts"],
                "missing-answer gold",
            )
        else:
            require(
                case["evidence_spans"]
                and case["required_evidence_groups"]
                and case["required_facts"],
                "answerable gold",
            )
            require(
                len(documents) == 1
                if case["primary_class"] == "single-doc"
                else len(documents) >= 2,
                "primary class document count",
            )
            span_ids = set()
            for span in case["evidence_spans"]:
                _section(span, revisions)
                require(span["span_id"] not in span_ids, "unique span id")
                span_ids.add(span["span_id"])
                require(
                    span["source_id"] in documents
                    and span["source_revision"] == revisions[span["source_id"]]
                    and span["corpus_version"] == corpus["corpus_sha256"],
                    "span source address",
                )
                require(_sha(span["text_sha256"]) and span["normalized_text"], "span text identity")
            groups = case["required_evidence_groups"]
            require(len({g["group_id"] for g in groups}) == len(groups), "unique evidence group")
            require(
                all(g["alternatives"] and set(g["alternatives"]) <= span_ids for g in groups),
                "explicit evidence alternatives",
            )
            require(
                {s for g in groups for s in g["alternatives"]} == span_ids,
                "gold span group coverage",
            )
        if case["primary_class"] == "aggregation":
            agg = case["aggregation"]
            require(agg and agg["scope"] and agg["operands"], "aggregation scope/operands")
            if agg["operation"] == "count":
                value = len(agg["operands"])
            elif agg["operation"] == "count_distinct":
                value = len(set(agg["operands"]))
            else:
                require(agg["operation"] == "intersection_count", "aggregation operation")
                value = len(set.intersection(*(set(v) for v in agg["operands"])))
            require(
                agg["value"] == value and any(f["value"] == value for f in case["required_facts"]),
                "aggregation result",
            )
        else:
            require(case["aggregation"] is None, "non-aggregation case")
    counts = dict(Counter(c["primary_class"] for c in cases))
    styles = dict(Counter(c["question_origin"] for c in cases))
    traps = dict(Counter(c["trap_type"] for c in cases if c["trap_type"]))
    adversarial = sum(c["flags"]["adversarial_unanswerable"] for c in cases)
    ru_to_en_count = sum(ru_to_en(c) for c in cases)
    require(ru_to_en_count == manifest["ru_to_en_count"], "registered RU→EN count")
    components = [list(c) for c in family_clusters(mapping)]
    require(counts == manifest["quotas"] == QUOTAS, "exact class quotas")
    require(styles == manifest["style_counts"] == STYLES, "15/15 styles")
    require(set(manifest["question_styles"]) == set(STYLES), "registered styles")
    require(set(traps) == TRAPS and traps == manifest["trap_counts"], "five trap types")
    require(
        adversarial >= 6 and adversarial == manifest["adversarial_unanswerable_count"],
        "20% adversarial quota",
    )
    require(
        mapping == register["pilot_case_families"] and components == register["pilot_components"],
        "case-family components",
    )
    require(
        len(components) == manifest["case_family_component_count"]
        and len(family_ids) == manifest["family_count"]
        and manifest["case_count"] == len(cases),
        "registered counts",
    )
    regenerated = development_footprint(family_map, cases)
    for key, value in regenerated.items():
        require(register[key] == value, "recomputed development footprint: " + key)
    return {
        "cases": len(cases),
        "quotas": counts,
        "styles": styles,
        "traps": traps,
        "adversarial_unanswerable": adversarial,
        "ru_to_en": ru_to_en_count,
        "families": len(family_ids),
        "singleton_families": sum(len(f["members"]) == 1 for f in register["families"]),
        "pilot_families": len(register["development_used"]["pilot_T64"]["families"]),
        "case_family_components": len(components),
        "case_family_component_sizes": sorted(map(len, components)),
        "holdout_reserve_families": len(reserve),
        "holdout_reserve_documents": len(reserve_documents),
        "historical_H_families": len(register["development_used"]["H"]["families"]),
        "historical_H_Hm_families": len(register["development_used"]["P1b/P2"]["families"]),
        "pilot_added_families": len(
            set(register["development_used"]["pilot_T64"]["families"])
            - set(register["development_used"]["P1b/P2"]["families"])
        ),
        "spans": sum(len(c["evidence_spans"]) for c in cases),
    }


def load_artifacts() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    def load(name: str) -> dict[str, Any]:
        return json.loads((ROOT / "evaluation" / name).read_text(encoding="utf-8"))

    manifest = load("devset_pilot.manifest.json")
    raw = (ROOT / "evaluation/devset_pilot.jsonl").read_bytes()
    require(sha256(raw) == manifest["jsonl_sha256"], "case file SHA mismatch")
    require(
        sha256((ROOT / "evaluation/document_families.json").read_bytes())
        == manifest["families_sha256"],
        "family file SHA mismatch",
    )
    return (
        [json.loads(line) for line in raw.decode("utf-8").splitlines()],
        manifest,
        load("document_families.json"),
        load("aircargo_corpus.manifest.json"),
    )


def verify(*, metadata_only: bool = False, directory: Path | None = None) -> dict[str, Any]:
    cases, manifest, register, corpus = load_artifacts()
    summary = validate_metadata(cases, manifest, register, corpus)
    summary["corpus_check"] = "not_checked" if metadata_only else "verified"
    if metadata_only:
        return summary
    texts = read_sources(corpus, directory if directory is not None else corpus_directory())
    regenerated = build_families(texts)
    for key in (
        "families",
        "cross_ref_links",
        "structure_graph_version",
        "structure_graph_sha256",
        "cluster_unit",
        "coarse_sensitivity_view",
        "cross_ref_closure_sensitivity_view",
    ):
        require(register[key] == regenerated[key], "recomputed topic/cross_ref families")
    count, drawn = sample_sections(texts, manifest["seed"])
    require(
        count == manifest["sampling"]["candidate_count"]
        and drawn == manifest["sampling"]["drawn_sections"],
        "replayed section sampling",
    )
    validate_source_labels(cases, texts)
    return summary


def validate_source_labels(cases: list[dict[str, Any]], texts: dict[str, str]) -> None:
    all_sections = {name: sections(name, text) for name, text in texts.items()}
    eligible = eligible_sections(texts)
    normalized_documents = [normalized(text) for text in texts.values()]
    for case in cases:
        for section in [case["seed_selected_source_section"]] + case["partner_sections"]:
            address = {
                k: section[k] for k in ("source_id", "section_path", "char_start", "char_end")
            }
            require(address in all_sections[section["source_id"]], "source section address/offsets")
            require(address in eligible, "section not in eligible frame")
        for span in case["evidence_spans"]:
            require(
                any(
                    section["section_path"] == span["section_path"]
                    and section["char_start"]
                    <= span["char_start"]
                    < span["char_end"]
                    <= section["char_end"]
                    for section in all_sections[span["source_id"]]
                ),
                "source section address/offsets",
            )
            text = texts[span["source_id"]][span["char_start"] : span["char_end"]]
            require(sha256(text.encode("utf-8")) == span["text_sha256"], "span text SHA mismatch")
            require(normalized(text) == span["normalized_text"], "normalized span text")
            require(
                sum(span["normalized_text"] in doc for doc in normalized_documents)
                <= SPECIFICITY_RULE["maximum_span_documents"],
                "template-anchored evidence span",
            )
        span_texts = [
            texts[s["source_id"]][s["char_start"] : s["char_end"]] for s in case["evidence_spans"]
        ]
        context = "\n".join(span_texts)
        validate_fact_coverage(
            [
                f
                for f in case["required_facts"] + case["critical_facts"]
                if f.get("value") is not None and not f.get("derived")
            ],
            context,
            "numeric span self-coverage",
        )
        for fact in case["required_facts"] + case["critical_facts"]:
            validate_claim(fact)
            if fact.get("derived"):
                continue
            quote = fact["source_quote"]
            require(any(quote in text for text in span_texts), "fact supporting quote")
            text = normalized(quote)
            if len(text) >= SPECIFICITY_RULE["minimum_fact_characters"]:
                require(
                    sum(text in doc for doc in normalized_documents)
                    <= SPECIFICITY_RULE["maximum_fact_documents"],
                    "template-anchored fact",
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify"])
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(metadata_only=args.metadata_only), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
