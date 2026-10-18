"""A continued table chunk starts with its table's header rows (docs/specs/stage1-fixes.md row 8)."""

from __future__ import annotations

import pytest

from vectordb import parent_join, table_header

TABLE = "| Code | Fee |\n|---|---:|\n" + "\n".join(f"| C{i} | {i * 3} |" for i in range(1, 6))


def test_the_rows_of_a_table_find_their_header() -> None:
    content = "Fees by code:\n\n" + TABLE + "\n\nAfter the table."
    offset = content.index("| C3 |")
    assert table_header.header_rows(content, offset) == "| Code | Fee |\n|---|---:|"
    # The first data row continues the table too.
    assert table_header.header_rows(content, content.index("| C1 |")) == (
        "| Code | Fee |\n|---|---:|"
    )


@pytest.mark.parametrize(
    "start",
    ["| Code |", "|---|", "After the table.", "Fees by code"],
)
def test_the_header_rows_and_text_outside_the_table_get_nothing(start: str) -> None:
    content = "Fees by code:\n\n" + TABLE + "\n\nAfter the table."
    assert table_header.header_rows(content, content.index(start)) == ""


def test_rows_with_no_header_above_get_nothing() -> None:
    content = "Text.\n| a | b |\n| c | d |"
    assert table_header.header_rows(content, content.index("| c |")) == ""


WIDE = "| Code | Fee | Note |\n|---|---|---|\n" + "\n".join(
    f"| C{i} | {i * 3} | paid within {i} days of the inspection |" for i in range(1, 60)
)


def _sections_of(page: str) -> list:
    pytest.importorskip("langchain_text_splitters")
    from vectordb._base_manager import Document, structural_split

    return structural_split([Document(page_content=page, metadata={"source": "f.md"})], 800, 200)


def test_the_chunker_repeats_the_header_rows_in_each_continued_piece() -> None:
    chunks = _sections_of("# Fees\n\n" + WIDE + "\n")
    assert len(chunks) > 3
    for chunk in chunks:
        lines = chunk.page_content.split("\n")
        rows = [line for line in lines if line.startswith("| C")]
        assert rows, chunk.page_content
        assert "| Code | Fee | Note |" in lines and "|---|---|---|" in lines
    continued = [chunk for chunk in chunks if table_header.PREFIX_KEY in chunk.metadata]
    assert len(continued) == len(chunks) - 1
    for chunk in continued:
        prefix = chunk.metadata[table_header.PREFIX_KEY]
        assert chunk.page_content[:prefix] == "| Code | Fee | Note |\n|---|---|---|\n"


def test_expansion_joins_continued_pieces_with_the_header_rows_once() -> None:
    chunks = _sections_of("# Fees\n\n" + WIDE + "\n")
    joined = parent_join.join(
        "", [(index, chunk.page_content, chunk.metadata) for index, chunk in enumerate(chunks)]
    )
    assert joined.count("| Code | Fee | Note |") == 1
    rows = [line for line in joined.split("\n") if line.startswith("| C")]
    assert rows == [line for line in WIDE.split("\n") if line.startswith("| C")]
