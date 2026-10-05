"""The external bases: their pinned files, their documents as Markdown and their gold.

``evaluation/external_bases.json`` registers each base: the revision of its source, the SHA-256
of every file read from it, its licence, and the tenant and collection of its index. Nothing of
a base is committed — no question, no evidence string, no document: ``convert`` derives them from
the pinned files on the host that runs them, and the registration and the capsules carry counts
and digests only.

``convert`` gives, for one base, its documents (``evaluation/external_convert.py``), its cases
and the counts of what the conversion met:

- **ConditionalQA.** A page is its title as the top heading and its elements below: the
  dataset's ``h1``…``h4`` one level deeper, ``p`` a paragraph, ``li`` a list item, ``tr`` a table
  row. A question's query is its scenario and its question. Each evidence string of a question is
  one evidence group; every element of the page equal to the string is an alternative of the
  group. An alternative carries the part (the dataset's ``h1``) and the section (the nearest
  heading) it stands in, and whether another evidence of the question, one with a single place,
  stands in the same.
- **WixQA.** An article is its title as the top heading and its ``html_content`` converted. A
  question's gold is the documents of its ``article_ids``.
- **MultiHop-RAG.** An article is one heading — source, date of publication, title — and the
  paragraphs of its body, so that the three reach every chunk through the heading path. Each
  evidence sentence is one evidence group; its alternatives are its places in the article body.

A place is a range of the document's visible characters (``evaluation/external_gold.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation import external_convert as convert
from evaluation import external_gold as gold
from evaluation.external_convert import Block

ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = ROOT / "evaluation" / "external_bases.json"

_ELEMENT = re.compile(r"(?s)<(\w+)>(.*)</\1>")
_HEADINGS = ("h1", "h2", "h3", "h4", "h5")
_PARAGRAPHS = re.compile(r"\n[ \t]*\n")


@dataclass(frozen=True)
class Document:
    """One document of a base: its file name, its id in the base and its Markdown."""

    name: str
    document_id: str
    markdown: str


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def registration(path: Path | None = None) -> dict[str, Any]:
    registered: dict[str, Any] = json.loads((path or REGISTRATION).read_text(encoding="utf-8"))
    if registered["converter_version"] != convert.CONVERTER_VERSION:
        raise ValueError("the registration names another converter version")
    if registered["match_rule"] != gold.MATCH_RULE:
        raise ValueError("the registration names another match rule")
    return registered


def read_raw(base: Mapping[str, Any], directory: Path) -> dict[str, bytes]:
    """The registered files of a base from a directory, each checked against its SHA-256."""
    raw = {}
    for entry in base["files"]:
        data = (directory / entry["path"]).read_bytes()
        if len(data) != entry["bytes"] or sha256(data) != entry["sha256"]:
            raise ValueError(f"file differs from the registration: {entry['path']}")
        raw[entry["path"]] = data
    return raw


def convert_base(
    name: str, raw: Mapping[str, bytes]
) -> tuple[list[Document], list[dict[str, Any]], dict[str, Any]]:
    """The documents of a base, its cases and the counts of the conversion."""
    converters = {"conditionalqa": _conditionalqa, "wixqa": _wixqa, "multihoprag": _multihoprag}
    if name not in converters:
        raise ValueError(f"unregistered base: {name}")
    documents, cases, counts = converters[name](raw)
    if len({document.name for document in documents}) != len(documents):
        raise ValueError("document names repeat")
    if any("\r" in document.markdown for document in documents):
        raise ValueError("a document holds a carriage return")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("case ids repeat")
    return documents, cases, counts


def _json(raw: Mapping[str, bytes], path: str) -> Any:
    return json.loads(raw[path].decode("utf-8"))


def _json_lines(raw: Mapping[str, bytes], path: str) -> list[Any]:
    return [json.loads(line) for line in raw[path].decode("utf-8").splitlines() if line.strip()]


def _conditionalqa(
    raw: Mapping[str, bytes],
) -> tuple[list[Document], list[dict[str, Any]], dict[str, Any]]:
    pages = _json(raw, "v1_0/documents.json")
    names = convert.file_names([page["title"] for page in pages], [page["url"] for page in pages])
    documents: list[Document] = []
    by_url: dict[str, dict[str, Any]] = {}
    tags: Counter[str] = Counter()
    unwritten = 0
    for page, name in zip(pages, names, strict=True):
        blocks = [Block("heading", page["title"], level=1)]
        part: list[int | None] = []
        section: list[int | None] = []
        elements: dict[str, list[int]] = {}
        for index, element in enumerate(page["contents"]):
            match = _ELEMENT.fullmatch(element)
            if match is None:
                raise ValueError(f"not an element: {page['url']} #{index}")
            tag, text = match[1], match[2]
            tags[tag] += 1
            elements.setdefault(element, []).append(index)
            heading = tag in _HEADINGS
            part.append(index if tag == "h1" else part[-1] if part else None)
            section.append(index if heading else section[-1] if section else None)
            if heading:
                blocks.append(Block("heading", text, level=int(tag[1]) + 1, key=index))
            elif tag == "li":
                blocks.append(Block("item", text, level=1, key=index))
            elif tag == "tr":
                blocks.append(Block("row", cells=tuple(text.split(" | ")), key=index))
            elif tag == "p":
                blocks.append(Block("para", text, key=index))
            else:
                raise ValueError(f"unregistered element tag: {tag}")
        markdown, spans = convert.render(blocks)
        source = gold.Source.read(name, markdown)
        places = {
            index: source.place(*span) for index, span in spans.items() if isinstance(index, int)
        }
        places = {index: place for index, place in places.items() if place[0] < place[1]}
        unwritten += len(page["contents"]) - len(places)
        documents.append(Document(name, page["url"], markdown))
        by_url[page["url"]] = {
            "name": name,
            "elements": elements,
            "places": places,
            "part": part,
            "section": section,
        }

    cases: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    evidence_tags: Counter[str] = Counter()
    ambiguous_strings: set[tuple[str, str]] = set()
    for split in ("train", "dev"):
        for row in _json(raw, f"v1_0/{split}.json"):
            page = by_url[row["url"]]
            strings = list(dict.fromkeys(row["evidences"]))
            counts["evidence_references"] += len(row["evidences"])
            counts["evidence_strings_repeated_in_a_question"] += len(row["evidences"]) - len(
                strings
            )
            groups: list[dict[str, Any]] = []
            unresolved = 0
            for string in strings:
                alternatives = [
                    {
                        "source_id": page["name"],
                        "start": page["places"][index][0],
                        "end": page["places"][index][1],
                        "element": index,
                        "tag": string[1 : string.index(">")],
                        "part": page["part"][index],
                        "section": page["section"][index],
                    }
                    for index in page["elements"].get(string, [])
                    if index in page["places"]
                ]
                if not alternatives:
                    unresolved += 1
                    continue
                evidence_tags[string[1 : string.index(">")]] += 1
                if len(alternatives) > 1:
                    ambiguous_strings.add((row["url"], string))
                groups.append({"alternatives": alternatives})
            _mark_neighbours(groups)
            answerable = not row["not_answerable"]
            cases.append(
                {
                    "case_id": f"conditionalqa-{row['id']}",
                    "base": "conditionalqa",
                    "split": split,
                    "stratum": "answerable" if answerable else "not_answerable",
                    "query": f"{row['scenario']} {row['question']}",
                    "document": page["name"],
                    "gold_sources": [page["name"]] if groups else [],
                    "evidence_groups": groups,
                    "unresolved_evidence": unresolved,
                    "reference_answers": [answer for answer, _ in row["answers"]],
                    "conditional": any(conditions for _, conditions in row["answers"]),
                }
            )
            ambiguous = [group for group in groups if len(group["alternatives"]) > 1]
            counts["questions"] += 1
            counts[f"questions_{split}"] += 1
            counts["questions_answerable"] += answerable
            counts["answerable_questions_without_evidence"] += answerable and not groups
            counts["not_answerable_questions_with_evidence"] += bool(groups) and not answerable
            counts["evidence_groups"] += len(groups)
            counts["evidence_unresolved"] += unresolved
            counts["evidence_groups_with_several_places"] += len(ambiguous)
            counts["alternatives"] += sum(len(group["alternatives"]) for group in groups)
            counts["several_places_one_beside_other_evidence"] += sum(
                sum(alternative["same_section"] for alternative in group["alternatives"]) == 1
                for group in ambiguous
            )
            counts["several_places_none_beside_other_evidence"] += sum(
                not any(alternative["same_section"] for alternative in group["alternatives"])
                for group in ambiguous
            )
            counts["questions_with_evidence_in_several_parts"] += _spread(groups, "part")
            counts["questions_with_evidence_in_several_sections"] += _spread(groups, "section")
            counts["questions_with_two_or_more_evidence_groups"] += len(groups) > 1
    return (
        documents,
        cases,
        {
            "documents": len(documents),
            "elements": dict(sorted(tags.items())),
            "elements_without_text": unwritten,
            **dict(sorted(counts.items())),
            "document_strings_with_several_places": len(ambiguous_strings),
            "evidence_groups_by_tag": dict(sorted(evidence_tags.items())),
            "documents_with_questions": len({case["document"] for case in cases}),
        },
    )


def _mark_neighbours(groups: list[dict[str, Any]]) -> None:
    """On each alternative of a several-place group: does single-place evidence stand beside it."""
    single = [group["alternatives"][0] for group in groups if len(group["alternatives"]) == 1]
    for group in groups:
        if len(group["alternatives"]) < 2:
            continue
        for alternative in group["alternatives"]:
            for level in ("section", "part"):
                alternative[f"same_{level}"] = any(
                    other[level] == alternative[level] for other in single
                )


def _spread(groups: list[dict[str, Any]], level: str) -> bool:
    """Whether the evidence of a question cannot be placed in one part (or section)."""
    common: set[Any] | None = None
    for group in groups:
        here = {alternative[level] for alternative in group["alternatives"]}
        common = here if common is None else common & here
    return common is not None and not common


def _wixqa(raw: Mapping[str, bytes]) -> tuple[list[Document], list[dict[str, Any]], dict[str, Any]]:
    articles = _json_lines(raw, "wix_kb_corpus/wix_kb_corpus.jsonl")
    names = convert.file_names(
        [article["title"] for article in articles], [article["id"] for article in articles]
    )
    documents: list[Document] = []
    name_of: dict[str, str] = {}
    kinds: Counter[str] = Counter()
    types: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    headings_in_html = headings_written = same_headings = same_text = 0
    for article, name in zip(articles, names, strict=True):
        body = convert.html_blocks(article["html_content"])
        markdown, _ = convert.render([Block("heading", article["title"], level=1), *body])
        documents.append(Document(name, article["id"], markdown))
        name_of[article["id"]] = name
        types[article["article_type"]] += 1
        kinds.update(block.kind for block in body)
        written = [" ".join(block.text.split()) for block in body if block.kind == "heading"]
        levels.update(f"level_{block.level}" for block in body if block.kind == "heading")
        expected = [
            " ".join(text.split()) for text in convert.html_headings(article["html_content"])
        ]
        headings_in_html += len(expected)
        headings_written += len(written)
        same_headings += written == expected
        text = article["title"] + "".join(block.text + "".join(block.cells) for block in body)
        same_text += gold.visible(text)[0] == gold.visible(article["contents"])[0]

    cases: list[dict[str, Any]] = []
    gold_sizes: dict[str, Counter[str]] = {}
    for stratum in ("expertwritten", "simulated"):
        sizes = gold_sizes.setdefault(stratum, Counter())
        for index, row in enumerate(_json_lines(raw, f"wixqa_{stratum}/test.jsonl")):
            sources = [name_of[article_id] for article_id in dict.fromkeys(row["article_ids"])]
            sizes[f"gold_articles_{len(sources)}"] += 1
            cases.append(
                {
                    "case_id": f"wixqa-{stratum}-{index:03d}",
                    "base": "wixqa",
                    "stratum": stratum,
                    "query": row["question"],
                    "gold_sources": sources,
                    "reference_answers": [row["answer"]],
                }
            )
    return (
        documents,
        cases,
        {
            "documents": len(documents),
            "documents_by_type": dict(sorted(types.items())),
            "blocks": dict(sorted(kinds.items())),
            "headings_in_html": headings_in_html,
            "headings_written": headings_written,
            "headings_written_by_level": dict(sorted(levels.items())),
            "documents_with_every_heading_in_order": same_headings,
            "documents_with_the_visible_text_of_contents": same_text,
            "questions": {
                stratum: {"questions": sum(sizes.values()), **dict(sorted(sizes.items()))}
                for stratum, sizes in gold_sizes.items()
            },
        },
    )


def _multihoprag(
    raw: Mapping[str, bytes],
) -> tuple[list[Document], list[dict[str, Any]], dict[str, Any]]:
    articles = _json(raw, "corpus.json")
    names = convert.file_names(
        [article["title"] for article in articles], [article["url"] for article in articles]
    )
    documents: list[Document] = []
    by_url: dict[str, tuple[gold.Source, gold.Range, str]] = {}
    for article, name in zip(articles, names, strict=True):
        heading = f"{article['source']}, {article['published_at'][:10]}: {article['title']}"
        paragraphs = _PARAGRAPHS.split(article["body"])
        blocks = [Block("heading", heading, level=1)]
        blocks += [Block("para", text, key=index) for index, text in enumerate(paragraphs)]
        markdown, spans = convert.render(blocks)
        source = gold.Source.read(name, markdown)
        body = (
            source.place(
                min(start for start, _ in spans.values()), max(end for _, end in spans.values())
            )
            if spans
            else (0, 0)
        )
        documents.append(Document(name, article["url"], markdown))
        by_url[article["url"]] = (source, body, article["body"])

    cases: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    strata: Counter[str] = Counter()
    documents_per_query: Counter[str] = Counter()
    for index, row in enumerate(_json(raw, "MultiHopRAG.json")):
        groups: list[dict[str, Any]] = []
        unresolved = 0
        evidence = list(dict.fromkeys((item["url"], item["fact"]) for item in row["evidence_list"]))
        counts["evidence_references"] += len(row["evidence_list"])
        for url, fact in evidence:
            source, body, text = by_url[url]
            places = source.occurrences(fact, within=body)
            counts["evidence_places_differ_from_verbatim_count"] += len(places) != text.count(fact)
            if not places:
                unresolved += 1
                continue
            groups.append(
                {
                    "alternatives": [
                        {"source_id": source.name, "start": start, "end": end}
                        for start, end in places
                    ]
                }
            )
        sources = sorted({by_url[url][0].name for url, _ in evidence})
        cases.append(
            {
                "case_id": f"multihoprag-{index:04d}",
                "base": "multihoprag",
                "stratum": row["question_type"],
                "query": row["query"],
                "evidence_groups": groups,
                "gold_sources": sources,
                "unresolved_evidence": unresolved,
                "reference_answers": [row["answer"]],
            }
        )
        strata[row["question_type"]] += 1
        documents_per_query[f"gold_documents_{len(sources)}"] += 1
        counts["questions"] += 1
        counts["evidence_groups"] += len(groups)
        counts["evidence_unresolved"] += unresolved
        counts["evidence_groups_with_several_places"] += sum(
            len(group["alternatives"]) > 1 for group in groups
        )
        counts["alternatives"] += sum(len(group["alternatives"]) for group in groups)
    return (
        documents,
        cases,
        {
            "documents": len(documents),
            **dict(sorted(counts.items())),
            "questions_by_type": dict(sorted(strata.items())),
            "questions_by_gold_documents": dict(sorted(documents_per_query.items())),
        },
    )
