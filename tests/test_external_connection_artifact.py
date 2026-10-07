"""The connection of the external bases (plan slices 1.5, 1.5c, 1.5d): capsule against artifact.

The artifact holds counts, digests and times of the three bases and no text of any of them. The
tests hold it against the registrations, the capsule against it — every row of the capsule's
tables is computed here — and the counts the spec cites against it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "reports" / "external" / "36f1167" / "connection.json"
CAPSULE = ROOT / "docs" / "evidence" / "external-bases-connection.md"
REGISTRATION = ROOT / "evaluation" / "external_bases.json"
PARTS = ROOT / "evaluation" / "external_parts.json"
SPEC = ROOT / "docs" / "specs" / "semantic-precision-metrics.md"
BASES = ("conditionalqa", "wixqa", "multihoprag")
WITH_EVIDENCE = ("conditionalqa", "multihoprag")
STRUCTURAL = {"category", "contains", "next", "same_section"}


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registered() -> dict[str, Any]:
    return json.loads(REGISTRATION.read_text(encoding="utf-8"))


def count(value: int) -> str:
    return f"{value:,}"


def spread(values: dict[str, Any]) -> str:
    return " / ".join(count(round(values[key])) for key in ("median", "p95", "max"))


def strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def rows(document: dict[str, Any], registered: dict[str, Any]) -> dict[str, list[str]]:
    """Every row of the capsule's tables, by table."""
    found: dict[str, list[str]] = {
        "bases": [],
        "chunks": [],
        "evidence": [],
        "hosts": [],
        "graphs": [],
    }
    for base in BASES:
        block = document["bases"][base]
        title = registered["bases"][base]["title"]
        convert, chunks, kept = block["convert"], block["chunks"], block["preserve"]
        found["bases"].append(
            f"| {title} | {count(convert['documents'])} | {count(kept['gold_documents'])} "
            f"| {count(convert['cases'])} | {count(chunks['chunks'])} "
            f"| `{chunks['collection']}` | `{convert['revision'][:8]}` |"
        )
        found["chunks"].append(
            f"| {title} | {spread(kept['chunk_characters'])} | {spread(kept['chunks_per_document'])} "
            f"| {count(kept['chunks_longer_than_chunk_size'])} "
            f"| {count(kept['heading_paths_cut_by_the_header_limit'])} "
            f"| {count(kept['visible_characters_in_no_chunk'])} "
            f"| {count(kept['chunks_without_a_place'])} |"
        )
        if base in WITH_EVIDENCE:
            counts = convert["counts"]
            groups, places = kept["evidence_groups"], kept["alternatives"]
            found["evidence"].append(
                f"| {title} | {count(counts['evidence_groups'])} | {count(counts['alternatives'])} "
                f"| {count(counts['evidence_groups_with_several_places'])} "
                f"| {count(counts['evidence_unresolved'])} | {count(groups['whole'])} "
                f"| {count(groups['split'])} | {count(groups['lost'])} "
                f"| {count(places['whole'])} / {count(places['split'])} / {count(places['lost'])} |"
            )
        embed, index = block["embed"], block["index"]
        found["hosts"].append(
            f"| {title} | {count(embed['report']['total_rows'])} | {count(embed['seconds'])} "
            f"| {embed['seconds'] / embed['report']['total_rows']:.2f} "
            f"| {embed['seconds'] / convert['documents']:.1f} | {embed['attempts']} "
            f"| {embed['foreign_cpu_samples']} of {embed['samples']} "
            f"| {embed['peak_rss_kb'] / 1024 / 1024:.1f} | {count(index['seconds'])} |"
        )
        graph = block["structure_graph"]
        nodes, edges = graph["nodes"], graph["edges"]
        found["graphs"].append(
            f"| {title} | {count(nodes['document'])} | {count(nodes['section'])} "
            f"| {count(nodes['chunk'])} | {count(edges['contains'])} | {count(edges['next'])} "
            f"| {count(edges['same_section'])} | {count(sum(edges[kind] for kind in edges if kind not in STRUCTURAL))} "
            f"| `{graph['digest'][:12]}` |"
        )
    return found


def claims(document: dict[str, Any]) -> list[str]:
    """The sentences of the capsule that carry a count outside its tables."""
    blocks = [document["bases"][base] for base in BASES]
    conditional, wix, multihop = blocks
    counts, other = conditional["convert"]["counts"], multihop["convert"]["counts"]
    headings = wix["convert"]["counts"]
    kept = multihop["preserve"]["evidence_groups"]
    seconds = sum(block[step]["seconds"] for block in blocks for step in ("embed", "index"))
    cut = [
        (
            count(block["preserve"]["heading_paths_cut_by_the_header_limit"]),
            block["preserve"]["heading_paths_cut_by_the_header_limit"]
            / block["preserve"]["chunks"],
        )
        for block in blocks
    ]
    graph = conditional["structure_graph"]
    found = [
        f"{count(sum(block['convert']['documents'] for block in blocks))} documents in "
        f"{count(sum(block['chunks']['chunks'] for block in blocks))} chunks, in three collections",
        f"All {count(counts['evidence_groups'])} evidence groups of ConditionalQA lie whole in one "
        f"chunk; of the {count(other['evidence_groups'])} of MultiHop-RAG, {count(kept['whole'])} "
        f"do and {count(kept['split'])} lie across two chunks; none is lost.",
        f"{count(counts['evidence_groups_with_several_places'])} of the "
        f"{count(counts['evidence_groups'])} groups of ConditionalQA and "
        f"{count(other['evidence_groups_with_several_places'])} of the "
        f"{count(other['evidence_groups'])} of MultiHop-RAG stand in several places",
        f"{count(counts['evidence_references'])} references make {count(counts['evidence_groups'])} "
        f"groups: {count(counts['evidence_strings_repeated_in_a_question'])} repeat an element",
        f"({count(counts['document_strings_with_several_places'])} different strings)",
        f"number {count(counts['questions_with_evidence_in_several_sections'])} by the registered "
        "reading of a section",
        f"{count(headings['headings_in_html'])} headings stand in the HTML and "
        f"{count(headings['headings_written'])} are written",
        f"took {seconds / 3600:.1f} hours of the host",
        f"{cut[0][0]} chunks of ConditionalQA ({cut[0][1]:.1%}), {cut[1][0]} of WixQA "
        f"({cut[1][1]:.1%}) and {cut[2][0]} of MultiHop-RAG ({cut[2][1]:.1%}) have a header cut",
        f"ConditionalQA has {count(graph['nodes']['section'])} sections for "
        f"{count(graph['nodes']['chunk'])} chunks",
        f"only {count(graph['edges']['same_section'])} `same_section` edges exist",
    ]
    return found + [entry["sha256"] for entry in document["guarded"]["before"].values()]


def test_artifact_is_the_registered_bases_and_nothing_changed_beside_them(
    document: dict[str, Any], registered: dict[str, Any]
) -> None:
    assert document["version"] == "external-connection/v1"
    assert document["code_sha"].startswith("36f1167")
    assert document["registration_sha256"] == hashlib.sha256(REGISTRATION.read_bytes()).hexdigest()
    assert document["supervisor"]["status"] == "complete"
    # The aircargo corpus, the index of slice 2.5 and its checkpoint were hashed before the first
    # step and after the last.
    guarded = document["guarded"]
    assert guarded["unchanged"] is True and guarded["before"] == guarded["after"]
    assert len(guarded["before"]) == 3
    assert set(document["bases"]) == set(BASES) == set(registered["bases"])
    manifests = []
    for base in BASES:
        block, held = document["bases"][base], registered["bases"][base]
        convert, chunks, kept = block["convert"], block["chunks"], block["preserve"]
        assert convert["files"] == held["files"] and convert["revision"] == held["revision"]
        assert block["fetch"]["files"] == len(held["files"])
        assert {key: convert[key] for key in held["converted"]} == held["converted"]
        assert convert["converter_version"] == registered["converter_version"]
        assert convert["match_rule"] == kept["match_rule"] == registered["match_rule"]
        assert chunks["chunking"] == registered["chunking"]
        assert (chunks["collection"], chunks["tenant"]) == (held["collection"], held["tenant"])
        assert chunks["corpus_sha256"] == kept["corpus_sha256"] == convert["corpus_sha256"]
        assert chunks["archive_sha256"] == kept["archive_sha256"]
        total = chunks["chunks"]
        embed, index = block["embed"], block["index"]
        assert kept["chunks"] == embed["report"]["total_rows"] == total
        assert embed["report"]["complete"] is True and embed["exit_code"] == 0
        assert index["exit_code"] == 0
        receipt = index["report"]
        assert receipt["chunk_count"] == total
        assert receipt["collection_name"] == held["collection"]
        # The identity of an index is the archive it was built from and the checkpoint of its
        # vectors.
        assert (
            receipt["corpus_sha256"] == embed["report"]["corpus_sha256"] == chunks["archive_sha256"]
        )
        assert receipt["checkpoint_sha256"] == embed["report"]["checkpoint_sha256"]
        assert receipt["texts_sha256"] == embed["report"]["texts_sha256"]
        assert receipt["code_sha"] == document["code_sha"]
        manifests.append(receipt["embedder_manifest"])
        assert embed["report"]["embedder_manifest"] == receipt["embedder_manifest"]
        graph = block["structure_graph"]
        assert graph["payload_sha256"] == chunks["payload_sha256"] and graph["chunks"] == total
        assert graph["nodes"]["chunk"] == total
        assert graph["nodes"]["document"] == convert["documents"] == kept["documents"]
    assert manifests[0] == manifests[1] == manifests[2]


def test_every_document_is_whole_in_its_chunks_and_no_evidence_is_lost(
    document: dict[str, Any],
) -> None:
    for base in BASES:
        kept = document["bases"][base]["preserve"]
        assert kept["visible_characters_in_no_chunk"] == 0
        assert kept["documents_with_characters_in_no_chunk"] == 0
        assert kept["documents_without_chunks"] == kept["gold_documents_without_chunks"] == 0
        assert kept["chunks_without_a_place"] == 0
        assert kept["chunks_with_a_heading_path"] == kept["chunks"]
        assert kept["chunks_whose_header_is_not_the_source_and_the_heading_path"] == 0
        assert kept["heading_lines_absent_from_chunk_paths"] == 0
    for base in WITH_EVIDENCE:
        block = document["bases"][base]
        counts, kept = block["convert"]["counts"], block["preserve"]
        assert counts["evidence_unresolved"] == 0
        assert sum(kept["evidence_groups"].values()) == counts["evidence_groups"]
        assert sum(kept["alternatives"].values()) == counts["alternatives"]
        assert kept["evidence_groups"]["lost"] == kept["alternatives"]["lost"] == 0
    conditional = document["bases"]["conditionalqa"]["preserve"]
    assert conditional["evidence_groups"]["split"] == 0
    multihop = document["bases"]["multihoprag"]["preserve"]
    assert multihop["evidence_groups"]["split"] == 6
    assert multihop["split_alternatives_by_chunks_touched"] == {"chunks_2": 6}
    wix = document["bases"]["wixqa"]["convert"]["counts"]
    assert wix["headings_written"] == wix["headings_in_html"]
    assert (
        wix["documents_with_every_heading_in_order"]
        == wix["documents_with_the_visible_text_of_contents"]
        == wix["documents"]
    )


def test_artifact_holds_no_text_of_a_base(document: dict[str, Any]) -> None:
    # What can be checked without the bases: the document is short strings - names of counts,
    # digests, paths of the pinned files and of the hosts - and none of them is a sentence.
    parts = json.loads(PARTS.read_text(encoding="utf-8"))
    ids = {
        case_id
        for base in parts["bases"].values()
        for part in base["parts"].values()
        for case_id in part["case_ids"]
    }
    held = set(strings(document))
    assert not held & ids
    assert max(len(text.split()) for text in held) <= 12
    assert "per_case" not in held and "query" not in held


def test_capsule_tables_are_the_artifact(
    document: dict[str, Any], registered: dict[str, Any]
) -> None:
    capsule = CAPSULE.read_text(encoding="utf-8")
    for table, lines in rows(document, registered).items():
        for line in lines:
            assert line in capsule, (table, line)
    for base in BASES:
        block = document["bases"][base]
        for digest in (
            block["convert"]["corpus_sha256"],
            block["convert"]["cases_sha256"],
            block["chunks"]["archive_sha256"],
            block["chunks"]["payload_sha256"],
            block["embed"]["report"]["checkpoint_sha256"],
            block["structure_graph"]["digest"],
        ):
            assert digest in capsule, (base, digest)
    assert document["registration_sha256"] in capsule
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() in capsule
    flat = " ".join(capsule.split())
    assert registered["redistribution"] in flat
    for phrase in ("llm_labelled", "ONLY be used for NLP research", "not evidence of speed"):
        assert phrase in flat, phrase
    for phrase in claims(document):
        assert phrase in flat, phrase


def test_spec_cites_the_counts_of_the_conversion(document: dict[str, Any]) -> None:
    spec = " ".join(SPEC.read_text(encoding="utf-8").split())
    conditional = document["bases"]["conditionalqa"]["convert"]["counts"]
    multihop = document["bases"]["multihoprag"]["convert"]["counts"]
    assert (
        f"{count(conditional['evidence_groups_with_several_places'])} of the "
        f"{count(conditional['evidence_groups'])} evidence groups of ConditionalQA and "
        f"{multihop['evidence_groups_with_several_places']} of the "
        f"{count(multihop['evidence_groups'])} of MultiHop-RAG"
    ) in spec
    assert (
        f"{count(conditional['questions_with_evidence_in_several_sections'])} questions in the three parts"
        in spec
    )
    assert re.search(r"capsule of the connection of the bases \(plan slices 1\.5 and 1\.5d\)", spec)
