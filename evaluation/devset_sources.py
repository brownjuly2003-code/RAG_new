"""Source-addressed section sampling and draft topic families (no model calls)."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[1]
SEED = 6413030
SECTION_VERSION = "markdown-heading-bodies-v1"
SAMPLING_ALGORITHM = (
    "Python random.Random(seed).sample without replacement over specificity-filtered "
    "heading bodies across all 201 manifest documents, "
    "sorted by (source_id, char_start)"
)


class SpecificityRule(TypedDict):
    version: str
    minimum_stripped_characters: int
    excluded_last_headings: list[str]
    normalization: str
    minimum_line_characters: int
    repeated_line_document_threshold: int
    maximum_repeated_line_fraction: str
    maximum_span_documents: int
    minimum_fact_characters: int
    maximum_fact_documents: int
    fact_specificity_field: str


SPECIFICITY_RULE: SpecificityRule = {
    "version": "document-specific-heading-bodies-v2",
    "minimum_stripped_characters": 180,
    "excluded_last_headings": [
        "История изменений",
        "Связанные документы",
        "Порядок пересмотра и актуализации",
    ],
    "normalization": "whitespace collapsed, lower-case",
    "minimum_line_characters": 8,
    "repeated_line_document_threshold": 3,
    "maximum_repeated_line_fraction": "1/3",
    "maximum_span_documents": 2,
    "minimum_fact_characters": 12,
    "maximum_fact_documents": 3,
    "fact_specificity_field": "source_quote",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus_directory() -> Path:
    override = os.environ.get("AIRCARGO_CORPUS_DIR")
    return (
        Path(override) if override else ROOT.parent / "RAG_Support_Assistant/data/uploads/aircargo"
    )


def read_sources(manifest: dict[str, Any], directory: Path) -> dict[str, str]:
    texts = {}
    for entry in manifest["files"]:
        data = (directory / entry["name"]).read_bytes()
        if sha256(data) != entry["sha256"]:
            raise ValueError(f"corpus file SHA mismatch: {entry['name']}")
        texts[entry["name"]] = data.decode("utf-8")
    return texts


def sections(source_id: str, text: str) -> list[dict[str, Any]]:
    headings = list(re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)\s*$", text))
    result = []
    chain: list[tuple[int, str]] = []
    for index, heading in enumerate(headings):
        level = len(heading[1])
        chain = [(depth, title) for depth, title in chain if depth < level]
        chain.append((level, heading[2].strip().rstrip("#").strip()))
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        if text[start:end].strip():
            result.append(
                {
                    "source_id": source_id,
                    "section_path": [title for _, title in chain],
                    "char_start": start,
                    "char_end": end,
                }
            )
    return result


def topic(source_id: str) -> str:
    suffix = re.sub(r"^(?:\d\d_(?:hr|legal|tlog|comp)_|external_)", "", source_id[:-3])
    rules = {
        "claims": (
            "claim",
            "reply",
            "demand",
            "arbitration",
            "debt_collection",
            "settlement",
            "dispute",
            "contract_breach",
        ),
        "confidentiality": ("confidential", "commercial_secret", "nda_", "contract_ndc"),
        "personal_data": (
            "pdp",
            "consent",
            "cookies",
            "cross_border_transfer",
            "data_destruction",
            "data_retention",
            "subject_rights",
            "video_surveillance",
            "breach_notification",
        ),
        "dismissal": ("dismissal", "resignation", "exit_interview"),
        "probation": ("probation",),
        "leave": ("leave", "childcare", "maternity"),
        "business_trip": ("business_trip", "relocation"),
        "compensation": ("salary", "bonus", "compensation", "social_package"),
        "hiring": ("hiring", "employment", "internship", "tk_rf_chapter_11"),
        "transfer": ("transfer", "position_change"),
        "remote_work": ("remote_work",),
        "working_time": (
            "attendance",
            "night_shift",
            "overtime",
            "part_time",
            "shift_schedule",
            "timesheet",
            "driver_hours",
        ),
        "anticorruption": ("corruption", "gifts", "conflict_interest", "nepotism", "whistleblower"),
        "material_liability": ("material_liability",),
        "customs": ("customs", "regulation_cross_border", "trade_compliance"),
        "expedition": (
            "expedition",
            "forwarder",
        ),
        "transport_road": (
            "transport_road",
            "driver_services",
            "driver_duty",
            "driver_pre_trip",
            "vehicle_inspection",
            "cmr",
            "waybill",
            "dispatch",
            "gps_tracking",
        ),
        "transport_rail": ("transport_rail",),
        "cargo_insurance": ("insurance_cargo", "cargo_insurance", "carrier_liability"),
        "warehouse": ("warehouse",),
        "fuel": ("fuel_supply", "supply_fuel"),
        "leasing_vehicle": ("leasing_vehicle", "leasing_truck"),
        "contract_lifecycle": (
            "contract_amendment",
            "contract_termination",
            "contract_supplement",
            "contract_approval",
            "contract_compliance",
            "contract_templates",
            "contract_framework",
            "tmp_add_agreement",
        ),
        "access_control": ("access_control", "it_access"),
        "performance": ("kpi", "performance_review", "talent_pool"),
        "training": ("training", "adaptation"),
        "references": ("references", "reference_letter"),
    }
    for name, markers in rules.items():
        if any(marker in suffix for marker in markers):
            return name
    return re.sub(
        r"^(?:pol_|tmp_|contract_|policy_|regulation_|instruction_|checklist_|faq_)", "", suffix
    )


def normalized(text: str) -> str:
    return " ".join(text.lower().split())


def eligible_sections(texts: dict[str, str]) -> list[dict[str, Any]]:
    line_documents: dict[str, set[str]] = defaultdict(set)
    for name, text in texts.items():
        for line in text.splitlines():
            line = normalized(line)
            if len(line) >= SPECIFICITY_RULE["minimum_line_characters"]:
                line_documents[line].add(name)
    candidates = []
    excluded = {normalized(h) for h in SPECIFICITY_RULE["excluded_last_headings"]}
    for name, text in texts.items():
        for section in sections(name, text):
            body = text[section["char_start"] : section["char_end"]]
            if len(body.strip()) < SPECIFICITY_RULE["minimum_stripped_characters"]:
                continue
            if normalized(section["section_path"][-1]) in excluded:
                continue
            lines = [normalized(line) for line in body.splitlines()]
            lines = [
                line for line in lines if len(line) >= SPECIFICITY_RULE["minimum_line_characters"]
            ]
            repeated = sum(
                len(line_documents[line]) >= SPECIFICITY_RULE["repeated_line_document_threshold"]
                for line in lines
            )
            if 3 * repeated <= len(lines):
                candidates.append(section)
    return sorted(
        candidates,
        key=lambda section: (section["source_id"], section["char_start"]),
    )


def sample_sections(texts: dict[str, str], seed: int) -> tuple[int, list[dict[str, Any]]]:
    candidates = eligible_sections(texts)
    return len(candidates), random.Random(seed).sample(candidates, 30)


def build_families(texts: dict[str, str]) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "_devset_structure_graph", ROOT / "ingestion/structure_graph.py"
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = builder
    spec.loader.exec_module(builder)
    parents = {name: name for name in texts}

    def find(name: str) -> str:
        while parents[name] != name:
            parents[name] = parents[parents[name]]
            name = parents[name]
        return name

    def union(left: str, right: str) -> None:
        parents[find(right)] = find(left)

    topics: dict[str, list[str]] = defaultdict(list)
    for name in sorted(texts):
        topics[topic(name)].append(name)
    for names in topics.values():
        for name in names[1:]:
            union(names[0], name)
    chunks = []
    for name, text in sorted(texts.items()):
        for index, section in enumerate(sections(name, text)):
            chunks.append(
                SimpleNamespace(
                    page_content=text[section["char_start"] : section["char_end"]],
                    metadata={
                        "source": name,
                        "chunk_index": index,
                        **{f"h{i + 1}": h for i, h in enumerate(section["section_path"][:4])},
                    },
                )
            )
    graph = builder.build_structural_graph(chunks)
    nodes = {node.node_id: node for node in graph.nodes}
    links = []
    for edge in graph.edges:
        if edge.kind != "cross_ref":
            continue
        left = nodes[edge.source_node_id].attributes["source"]
        right = nodes[edge.target_node_id].attributes["source"]
        if left != right:
            union(left, right)
            links.append({"source_id": left, "target_source_id": right, **edge.attributes})
    closure: dict[str, list[str]] = defaultdict(list)
    for name in sorted(texts):
        closure[find(name)].append(name)
    partners: dict[str, set[str]] = defaultdict(set)
    for link in links:
        partners[link["source_id"]].add(link["target_source_id"])
        partners[link["target_source_id"]].add(link["source_id"])
    families = []
    for names in sorted(topics.values()):
        families.append(
            {
                "family_id": "family-" + sha256("\n".join(names).encode())[:12],
                "topics": sorted({topic(name) for name in names}),
                "members": [
                    {
                        "source_id": name,
                        "basis": {
                            "topic": topic(name),
                            "cross_ref_partners": sorted(partners[name]),
                        },
                    }
                    for name in names
                ],
            }
        )
    return {
        "families": families,
        "cluster_unit": "topic only: devset_sources.topic()",
        "cross_ref_links": links,
        "structure_graph_version": graph.builder_version,
        "structure_graph_sha256": sha256((ROOT / "ingestion/structure_graph.py").read_bytes()),
        "cross_ref_closure_sensitivity_view": {
            "basis": "topic families transitively merged by cross_ref; not the cluster unit",
            "family_count": len(closure),
            "largest_family_size": max(map(len, closure.values())),
        },
        "coarse_sensitivity_view": {
            folder: [name for name in sorted(texts) if name.startswith(folder + "_")]
            for folder in (
                "01_hr",
                "02_hr",
                "03_legal",
                "04_legal",
                "05_tlog",
                "06_comp",
                "07_faq",
                "external",
            )
        },
    }


def development_footprint(
    family_map: dict[str, str], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    from evaluation.blinded_judge import _load_pool

    inputs = {}

    def read(name: str, expected_sha: str | None = None) -> bytes:
        raw = (ROOT / name).read_bytes()
        digest = sha256(raw)
        if expected_sha is not None and digest != expected_sha:
            raise ValueError(f"development input SHA mismatch: {name}")
        inputs[name] = digest
        return raw

    report_path = "reports/p2/p2-blinded-judge-glm+sonnet.json"
    report = json.loads(read(report_path))
    provenance = report["provenance"]["pools"]["H"]
    for key in ("dataset", "label_sidecar", "label_manifest"):
        read(provenance[key], provenance[key + "_sha256"])
    archive = provenance["archive_path"]
    rows = json.loads(gzip.decompress(read(archive, provenance["archive_sha256"])))
    pool = _load_pool(ROOT, "H", provenance)
    h_cases = {}
    matched = 0
    for case, row in zip(pool.cases, rows, strict=True):
        if case.case_id != row["case_id"] or list(case.documents) != row["cands"][:5]:
            raise ValueError("P2 H texts differ from phase-C top-5")
        sources = set()
        for text in case.documents:
            matches = {
                source
                for candidate, source in zip(row["cands"], row["cand_sources"], strict=True)
                if candidate == text
            }
            if len(matches) != 1:
                raise ValueError("ambiguous or missing P2 H exact-text source match")
            sources.update(matches)
            matched += 1
        h_cases[case.case_id] = sorted(sources)
    hm_path = report["provenance"]["pools"]["Hm"]["dataset"]
    hm_rows = [
        json.loads(line)
        for line in read(hm_path, report["provenance"]["pools"]["Hm"]["dataset_sha256"])
        .decode("utf-8")
        .splitlines()
    ]
    hm_cases = {row["case_id"]: sorted(row["source_documents"]) for row in hm_rows}

    def usage(documents: set[str], basis: str) -> dict[str, Any]:
        return {
            "documents": sorted(documents),
            "families": sorted({family_map[name] for name in documents}),
            "basis": basis,
        }

    h_docs = {name for names in h_cases.values() for name in names}
    hm_docs = {name for names in hm_cases.values() for name in names}
    pilot_docs = {
        section["source_id"]
        for case in cases
        for section in [case["seed_selected_source_section"]]
        + case["partner_sections"]
        + case["evidence_spans"]
    }
    used = {
        "H": {
            **usage(h_docs, "P2 graded phase-C top-5, exact text matched to cands/cand_sources"),
            "case_documents": h_cases,
            "matched_text_count": matched,
        },
        "Hm": {
            **usage(hm_docs, "source_documents of the curated Hm cases"),
            "case_documents": hm_cases,
        },
        "P1b/P2": usage(
            h_docs | hm_docs, "H/Hm footprint; P1b expansion stays inside seed documents"
        ),
        "loss_map_2.5": usage(h_docs | hm_docs, "Same H/Hm development footprint"),
        "pilot_T64": usage(pilot_docs, "Pilot source sections, partner sections and gold spans"),
    }
    pool_docs = set()
    for name, prov in report["provenance"]["pools"].items():
        pool_rows = (
            rows
            if name == "H"
            else json.loads(gzip.decompress(read(prov["archive_path"], prov["archive_sha256"])))
        )
        for row in pool_rows:
            pool_docs.update(row["cand_sources"])
            pool_docs.update(row.get("prerank_sources", []))
    read("evaluation/devset_pilot.jsonl")
    read("evaluation/aircargo_corpus.manifest.json")
    return {
        "development_used": used,
        "input_artifacts": [
            {"path": name, "sha256": digest} for name, digest in sorted(inputs.items())
        ],
        "retrieval_pool_sensitivity_view": {
            "document_count": len(pool_docs),
            "corpus_document_count": len(family_map),
            "family_count": len({family_map[name] for name in pool_docs}),
            "basis": "H/Hm candidate and pre-rerank pools; not the development footprint: retrieval scans the corpus on every query",
        },
    }
