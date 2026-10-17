"""Prepare an external base on a host: its files, its documents, its chunks, its losses, its parts.

Usage: python -m scripts.external_base <step> --base NAME [--raw DIR] --out DIR

    fetch     download the registered files of the base into <raw>/<base>/; every file is checked
              against its registered SHA-256, and a file already there and equal is kept
    convert   write <out>/corpus/*.md, corpus.manifest.json, cases.jsonl, convert-report.json
    chunks    split the corpus by the product's ingestion — loader, select_chunks, contextual
              headers — and write chunks.json.gz, the archive that
              scripts/production_embeddings.py and scripts/production_index.py read, and
              chunks-report.json
    preserve  read the corpus, the archive and the cases; write preserve-report.json — how much
              of the documents the chunks hold and how they hold every gold place — and
              preserve-cases.jsonl with the state of each case's evidence
    parts     hold the registered parts of the base (evaluation/external_parts.json) to its
              cases and write parts-report.json: the counts of every part and selection
    select    write selections/<selection>.questions.jsonl — the ids and the questions of one
              registered selection, in its order, for a run to read; a selection of a part
              that acceptance has not opened is refused

The reports hold counts and digests and may leave the host. The corpus, the cases, the archive,
preserve-cases.jsonl and the question files hold the texts of the base and stay on it
(evaluation/external_bases.json, "redistribution").
"""

from __future__ import annotations

import argparse
import gzip
import json
import statistics
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation import external_bases as bases
from evaluation import external_convert as convert
from evaluation import external_gold as gold
from evaluation import external_parts as parts
from scripts import corpus_manifest
from vectordb import contextual_header

HEADER_LIMIT = contextual_header.LIMIT  # add_contextual_headers shortens a header there
_LEVELS = ("h1", "h2", "h3", "h4")


def _write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_bytes(text.encode("utf-8"))


def _base(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    registered = bases.registration()
    if name not in registered["bases"]:
        raise SystemExit(f"unregistered base: {name}")
    return registered, registered["bases"][name]


def fetch(name: str, raw: Path) -> dict[str, Any]:
    _, base = _base(name)
    downloaded = 0
    for entry in base["files"]:
        target = raw / name / entry["path"]
        if target.is_file() and bases.sha256(target.read_bytes()) == entry["sha256"]:
            continue
        url = base["url"].format(revision=base["revision"], path=entry["path"])
        if not url.startswith("https://"):
            raise ValueError(f"not an https address: {url}")
        with urllib.request.urlopen(url, timeout=300) as response:
            data = response.read()
        if len(data) != entry["bytes"] or bases.sha256(data) != entry["sha256"]:
            raise ValueError(f"downloaded file differs from the registration: {entry['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        downloaded += 1
    return {"base": name, "files": len(base["files"]), "downloaded": downloaded}


def convert_step(name: str, raw: Path, out: Path) -> dict[str, Any]:
    registered, base = _base(name)
    documents, cases, counts = bases.convert_base(name, bases.read_raw(base, raw / name))
    corpus = out / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    wanted = {document.name for document in documents}
    stale = sorted(path.name for path in corpus.iterdir() if path.name not in wanted)
    if stale:
        raise ValueError(f"{len(stale)} files of another conversion stand in {corpus}")
    for document in documents:
        (corpus / document.name).write_bytes(document.markdown.encode("utf-8"))
    manifest = corpus_manifest.build_manifest(corpus, name=base["tenant"])
    corpus_manifest.write_manifest(out / "corpus.manifest.json", manifest)
    lines = [json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases]
    case_bytes = "".join(lines).encode("utf-8")
    (out / "cases.jsonl").write_bytes(case_bytes)
    report = {
        "base": name,
        "revision": base["revision"],
        "files": base["files"],
        "converter_version": registered["converter_version"],
        "match_rule": registered["match_rule"],
        "documents": manifest["file_count"],
        "corpus_sha256": manifest["corpus_sha256"],
        "corpus_bytes": sum(entry["bytes"] for entry in manifest["files"]),
        "cases": len(cases),
        "cases_sha256": bases.sha256(case_bytes),
        "counts": counts,
    }
    expected = base.get("converted")
    if expected is not None:
        actual = {key: report[key] for key in expected}
        if actual != expected:
            raise ValueError(f"the conversion differs from the registered one: {actual}")
    _write_json(out / "convert-report.json", report)
    return report


def _corpus(out: Path) -> tuple[dict[str, Any], dict[str, gold.Source]]:
    """The manifest of a converted corpus and its documents, checked against the manifest."""
    manifest = corpus_manifest.load_manifest(out / "corpus.manifest.json")
    difference = corpus_manifest.diff_corpus(manifest, out / "corpus")
    if not difference.ok():
        raise ValueError("the corpus differs from its manifest")
    sources = {}
    for entry in manifest["files"]:
        markdown = (out / "corpus" / entry["name"]).read_bytes().decode("utf-8")
        sources[entry["name"]] = gold.Source.read(entry["name"], markdown)
    return dict(manifest), sources


def chunks_step(name: str, out: Path) -> dict[str, Any]:
    registered, base = _base(name)

    from config.settings import get_settings
    from ingestion.loader import DocumentLoader
    from vectordb import manager
    from vectordb._base_manager import select_chunks

    settings = get_settings()
    chunking = {key: getattr(settings, key) for key in registered["chunking"]}
    if chunking != registered["chunking"]:
        raise ValueError(f"the settings differ from the registered chunking: {chunking}")
    manifest, _ = _corpus(out)
    revisions = {entry["name"]: entry["sha256"] for entry in manifest["files"]}

    started = time.perf_counter()
    documents = DocumentLoader(recursive=False).load_documents(str(out / "corpus"))
    loaded = time.perf_counter()
    if [document.metadata["source"] for document in documents] != sorted(revisions):
        raise ValueError("the loader did not read every document of the manifest once, in order")
    for document in documents:
        # The loader's facts about the host; they would give the archive a SHA per host.
        document.metadata["file_path"] = document.metadata["source"]
        document.metadata["mtime"] = registered["registered"] + "T00:00:00"
        if document.metadata["content_hash"] != revisions[document.metadata["source"]]:
            raise ValueError(f"the loader read another text: {document.metadata['source']}")
    split = select_chunks(
        list(documents), None, settings.chunk_size, settings.chunk_overlap, settings=settings
    )
    cut = time.perf_counter()
    headed = manager.add_contextual_headers(split, documents, chunk_size=settings.chunk_size)
    finished = time.perf_counter()

    payload = {
        "tenant_id": base["tenant"],
        "chunks": [
            {"page_content": chunk.page_content, "metadata": dict(chunk.metadata or {})}
            for chunk in headed
        ],
    }
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    archive = gzip.compress(data, compresslevel=9, mtime=0)
    (out / "chunks.json.gz").write_bytes(archive)
    report = {
        "base": name,
        "tenant": base["tenant"],
        "collection": base["collection"],
        "corpus_sha256": manifest["corpus_sha256"],
        "chunking": chunking,
        "documents": len(documents),
        "chunks": len(headed),
        "payload_sha256": bases.sha256(data),
        "archive_sha256": bases.sha256(archive),
        "archive_bytes": len(archive),
        "seconds": {
            "load": round(loaded - started, 3),
            "split": round(cut - loaded, 3),
            "headers": round(finished - cut, 3),
            "per_document": round((finished - started) / len(documents), 5),
        },
    }
    _write_json(out / "chunks-report.json", report)
    return report


def _spread(values: list[int]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "max": ordered[-1],
    }


def _headers(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """How the contextual headers carry the heading paths: whole, or shortened at the limit.

    A shortened header drops outer section levels and keeps the document and the heading
    nearest to the text (``vectordb.contextual_header``); the count says how many lost a level.
    """
    shortened = unlike = 0
    for chunk in chunks:
        metadata = chunk["metadata"]
        header_parts = contextual_header.header_parts(
            str(metadata["source"]), contextual_header.heading_path(metadata)
        )
        header = contextual_header.compose(header_parts, HEADER_LIMIT)
        unlike += metadata.get("contextual_header") != header or not chunk[
            "page_content"
        ].startswith(contextual_header.render(header) + "\n")
        shortened += len(contextual_header.SEPARATOR.join(header_parts)) > HEADER_LIMIT
    return {
        "chunks_with_a_heading_path": sum(
            any(chunk["metadata"].get(key) for key in _LEVELS) for chunk in chunks
        ),
        "chunks_whose_header_is_not_the_source_and_the_heading_path": unlike,
        "heading_paths_cut_by_the_header_limit": shortened,
    }


def _headings(markdown: dict[str, str], chunks: list[dict[str, Any]]) -> dict[str, int]:
    """Heading lines of the documents against the heading paths of their chunks."""
    paths: dict[str, set[tuple[int, str]]] = {name: set() for name in markdown}
    for chunk in chunks:
        metadata = chunk["metadata"]
        for depth, key in enumerate(_LEVELS, start=1):
            if metadata.get(key):
                paths[metadata["source"]].add((depth, gold.visible(str(metadata[key]))[0]))
    lines = absent = deeper = 0
    for name, text in markdown.items():
        for depth, heading in convert.markdown_headings(text):
            if depth > len(_LEVELS):
                deeper += 1
                continue
            lines += 1
            absent += (depth, gold.visible(heading)[0]) not in paths[name]
    return {
        "heading_lines_of_split_depth": lines,
        "heading_lines_absent_from_chunk_paths": absent,
        "heading_lines_deeper_than_the_splitter_reads": deeper,
    }


def preserve_step(name: str, out: Path) -> dict[str, Any]:
    registered, base = _base(name)
    manifest, sources = _corpus(out)
    markdown = {
        document: (out / "corpus" / document).read_bytes().decode("utf-8") for document in sources
    }
    archive = (out / "chunks.json.gz").read_bytes()
    payload = json.loads(gzip.decompress(archive))
    chunks = payload["chunks"]
    if payload["tenant_id"] != base["tenant"]:
        raise ValueError("the archive belongs to another tenant")
    places = gold.locate_chunks(chunks, sources, registered["chunking"]["chunk_overlap"])
    by_source: dict[str, list[gold.Range]] = {document: [] for document in sources}
    for chunk, place in zip(chunks, places, strict=True):
        if place is not None:
            by_source[chunk["metadata"]["source"]].append(place)
    missing = [
        gold.uncovered(len(source.text), by_source[document])
        for document, source in sources.items()
    ]

    alternatives: Counter[str] = Counter()
    groups: Counter[str] = Counter()
    questions: Counter[str] = Counter()
    by_tag: dict[str, Counter[str]] = {}
    held_by: Counter[str] = Counter()
    gold_documents: set[str] = set()
    details = []
    cases = [
        json.loads(line)
        for line in (out / "cases.jsonl").read_bytes().decode("utf-8").splitlines()
        if line
    ]
    for case in cases:
        gold_documents.update(case.get("gold_sources", []))
        states = []
        for group in case.get("evidence_groups", []):
            found = []
            for alternative in group["alternatives"]:
                target = (alternative["start"], alternative["end"])
                document = by_source[alternative["source_id"]]
                held = gold.state(target, document)
                found.append(held)
                alternatives[held] += 1
                if "tag" in alternative:
                    by_tag.setdefault(alternative["tag"], Counter())[held] += 1
                if held == "split":
                    touching = sum(low < target[1] and target[0] < high for low, high in document)
                    held_by[f"chunks_{touching}"] += 1
            best = min(found, key=gold.STATES.index)
            groups[best] += 1
            states.append({"state": best, "alternatives": found})
        if states:
            worst = max((entry["state"] for entry in states), key=gold.STATES.index)
            questions[f"worst_group_{worst}"] += 1
        details.append({"case_id": case["case_id"], "evidence_groups": states})
    detail_lines = [json.dumps(entry, sort_keys=True) + "\n" for entry in details]
    (out / "preserve-cases.jsonl").write_bytes("".join(detail_lines).encode("utf-8"))

    per_document = Counter(chunk["metadata"]["source"] for chunk in chunks)
    report = {
        "base": name,
        "match_rule": registered["match_rule"],
        "corpus_sha256": manifest["corpus_sha256"],
        "archive_sha256": bases.sha256(archive),
        "documents": len(sources),
        "chunks": len(chunks),
        "chunks_without_a_place": sum(place is None for place in places),
        "documents_without_chunks": sum(not per_document[document] for document in sources),
        "visible_characters": sum(len(source.text) for source in sources.values()),
        "visible_characters_in_no_chunk": sum(missing),
        "documents_with_characters_in_no_chunk": sum(count > 0 for count in missing),
        "chunks_per_document": _spread([per_document[document] for document in sources]),
        "chunk_characters": _spread([len(chunk["page_content"]) for chunk in chunks]),
        "chunks_longer_than_chunk_size": sum(
            len(chunk["page_content"]) > registered["chunking"]["chunk_size"] for chunk in chunks
        ),
        **_headers(chunks),
        **_headings(markdown, chunks),
        "cases": len(cases),
        "alternatives": {state: alternatives[state] for state in gold.STATES},
        "alternatives_by_tag": {
            tag: {state: counts[state] for state in gold.STATES}
            for tag, counts in sorted(by_tag.items())
        },
        "split_alternatives_by_chunks_touched": dict(sorted(held_by.items())),
        "evidence_groups": {state: groups[state] for state in gold.STATES},
        "questions_with_evidence": dict(sorted(questions.items())),
        "gold_documents": len(gold_documents),
        "gold_documents_without_chunks": sum(
            not per_document[document] for document in gold_documents
        ),
    }
    _write_json(out / "preserve-report.json", report)
    return report


def parts_step(name: str, out: Path) -> dict[str, Any]:
    _base(name)
    cases = parts.load_cases(out, name, bases.registration())
    report = parts.verify(parts.registration(), name, cases)
    _write_json(out / "parts-report.json", report)
    return report


def select_step(name: str, out: Path, selection: str) -> dict[str, Any]:
    _base(name)
    registered = parts.registration()
    if selection not in registered["selections"].get(name, {}):
        raise SystemExit(f"unregistered selection of {name}: {selection}")
    ids = parts.read(registered, name, selection=selection)
    cases = parts.load_cases(out, name, bases.registration())
    parts.verify(registered, name, cases)
    query = {case["case_id"]: case["query"] for case in cases}
    lines = [
        json.dumps({"case_id": case_id, "query": query[case_id]}, ensure_ascii=False) + "\n"
        for case_id in ids
    ]
    data = "".join(lines).encode("utf-8")
    target = out / "selections" / f"{selection}.questions.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    chosen = registered["selections"][name][selection]
    return {
        "base": name,
        "selection": selection,
        "part": chosen["rule"]["part"],
        "cases": len(ids),
        "cases_sha256": chosen["cases_sha256"],
        "questions_sha256": bases.sha256(data),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "step", choices=("fetch", "convert", "chunks", "preserve", "parts", "select")
    )
    parser.add_argument("--base", required=True)
    parser.add_argument("--raw", type=Path, help="directory that holds <base>/<registered path>")
    parser.add_argument("--out", type=Path, help="directory of the converted base")
    parser.add_argument("--selection", help="a registered selection of the base")
    args = parser.parse_args(argv)
    if args.step in ("fetch", "convert") and args.raw is None:
        parser.error("--raw is required")
    if args.step != "fetch" and args.out is None:
        parser.error("--out is required")
    if args.step == "select" and args.selection is None:
        parser.error("--selection is required")
    if args.step == "fetch":
        report = fetch(args.base, args.raw)
    elif args.step == "convert":
        report = convert_step(args.base, args.raw, args.out)
    elif args.step == "chunks":
        report = chunks_step(args.base, args.out)
    elif args.step == "preserve":
        report = preserve_step(args.base, args.out)
    elif args.step == "parts":
        report = parts_step(args.base, args.out)
    else:
        report = select_step(args.base, args.out, args.selection)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
