"""Count the chunks that continue a markdown table without its column-header row.

Usage: python -m scripts.table_continuations DIR [DIR ...]

PLAN.md stage 1 (docs/specs/stage1-fixes.md row 8): before the continuation of a long table
gets its header row repeated, count how many chunks need it. Each DIR is a corpus of markdown
files, cut as the product cuts it (``structural_split`` with the settings' chunk size and
overlap). A chunk counts when its section was cut into pieces, it is not the first piece, it
begins with a table row, and the table's header row and its separator row stand before it in
the section (``vectordb.table_header.header_rows``, the rule the chunker applies). Prints one
JSON line a corpus with its digest (the SHA-256 of the sorted list of its files, each with its
own SHA-256), so a count names the corpus it was taken on.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def corpus_digest(directory: Path) -> str:
    lines = [
        f"{path.relative_to(directory).as_posix()} {hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in sorted(directory.rglob("*.md"))
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def count(directory: Path) -> dict[str, Any]:
    from config.settings import get_settings
    from vectordb._base_manager import _build_text_splitter, plain_whitespace
    from vectordb.table_header import header_rows

    settings = get_settings()
    size, overlap = int(settings.chunk_size), int(settings.chunk_overlap)
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    headers = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers=False)
    char_splitter = _build_text_splitter(size, overlap)
    chunks = continued = documents_with_one = 0
    for path in sorted(directory.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        found = 0
        for section in md_splitter.split_text(plain_whitespace(text)):
            content = section.page_content
            if len(content) <= size:
                chunks += 1
                continue
            pieces = char_splitter.split_text(content)
            chunks += len(pieces)
            start = -1
            for index, piece in enumerate(pieces):
                start = content.find(piece, start + 1)
                if index and start > 0 and piece.lstrip().startswith("|"):
                    if header_rows(content, start):
                        continued += 1
                        found += 1
        documents_with_one += found > 0
    return {
        "corpus": str(directory),
        "corpus_digest": corpus_digest(directory),
        "chunk_size": size,
        "chunk_overlap": overlap,
        "chunks": chunks,
        "continued_table_chunks_without_header": continued,
        "documents_with_one": documents_with_one,
    }


def main(argv: list[str]) -> int:
    for directory in argv:
        print(json.dumps(count(Path(directory)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
