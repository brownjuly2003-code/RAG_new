"""Chunk any corpus directory by the product's ingestion into the archive the index tools read.

Usage: python -m scripts.corpus_chunks --corpus DIR --manifest FILE --tenant ID
           --collection NAME --dated YYYY-MM-DD --out DIR

The step ``chunks`` of ``scripts/external_base.py`` without the registration of an external
base: aircargo's corpus (evaluation/aircargo_corpus.manifest.json) is chunked the same way for
the new index generation of PLAN.md stage 1, item 4. The corpus must equal its manifest; the
loader (``ingestion.loader.DocumentLoader``), ``select_chunks`` and the contextual headers at the
settings in force cut it, and every document's text must be the bytes the manifest names.
Writes <out>/chunks.json.gz, which scripts/production_embeddings.py and
scripts/production_index.py read, and <out>/chunks-report.json.

``--dated`` stands for each document's modification time, as the external bases' registration
date does: the loader's facts about the host would give the archive a SHA per host.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from scripts import corpus_manifest

CHUNKING = ("chunk_size", "chunk_overlap", "structural_chunking", "contextual_headers")


def build(
    corpus: Path, manifest_path: Path, tenant: str, collection: str, dated: str, out: Path
) -> dict[str, Any]:
    from config.settings import get_settings
    from ingestion.loader import DocumentLoader
    from vectordb import manager
    from vectordb._base_manager import select_chunks

    settings = get_settings()
    manifest = corpus_manifest.load_manifest(manifest_path)
    if not corpus_manifest.diff_corpus(manifest, corpus).ok():
        raise ValueError("the corpus differs from its manifest")
    revisions = {entry["name"]: entry["sha256"] for entry in manifest["files"]}

    started = time.perf_counter()
    documents = DocumentLoader(recursive=False).load_documents(str(corpus))
    loaded = time.perf_counter()
    if [document.metadata["source"] for document in documents] != sorted(revisions):
        raise ValueError("the loader did not read every document of the manifest once, in order")
    for document in documents:
        document.metadata["file_path"] = document.metadata["source"]
        document.metadata["mtime"] = dated + "T00:00:00"
        if document.metadata["content_hash"] != revisions[document.metadata["source"]]:
            raise ValueError(f"the loader read another text: {document.metadata['source']}")
    split = select_chunks(
        list(documents), None, settings.chunk_size, settings.chunk_overlap, settings=settings
    )
    cut = time.perf_counter()
    headed = manager.add_contextual_headers(split, documents, chunk_size=settings.chunk_size)
    finished = time.perf_counter()

    payload = {
        "tenant_id": tenant,
        "chunks": [
            {"page_content": chunk.page_content, "metadata": dict(chunk.metadata or {})}
            for chunk in headed
        ],
    }
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    archive = gzip.compress(data, compresslevel=9, mtime=0)
    out.mkdir(parents=True, exist_ok=True)
    (out / "chunks.json.gz").write_bytes(archive)
    report = {
        "tenant": tenant,
        "collection": collection,
        "corpus_sha256": manifest["corpus_sha256"],
        "chunking": {key: getattr(settings, key) for key in CHUNKING},
        "documents": len(documents),
        "chunks": len(headed),
        "payload_sha256": hashlib.sha256(data).hexdigest(),
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "archive_bytes": len(archive),
        "seconds": {
            "load": round(loaded - started, 3),
            "split": round(cut - loaded, 3),
            "headers": round(finished - cut, 3),
        },
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (out / "chunks-report.json").write_bytes(text.encode("utf-8"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--dated", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build(args.corpus, args.manifest, args.tenant, args.collection, args.dated, args.out)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
