"""The column-header rows of a markdown table that a chunk continues (PLAN.md stage 1).

A section longer than a chunk is cut into pieces; a long table is cut between its rows, and
every piece after the first began with bare rows — the model read numbers without the names
of their columns (docs/specs/stage1-fixes.md row 8). ``structural_split`` now starts such a
piece with the table's header row and separator row, and records how many characters it put
there under ``PREFIX_KEY``, so parent expansion drops them when it joins the piece back to the
one before it (``vectordb.parent_join``). ``scripts/table_continuations.py`` counts the pieces
this applies to on a corpus with the same rule.

Markdown's own table syntax, no word of any language.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

#: A markdown table's separator row: cells of dashes, colons for alignment.
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
#: The metadata key of the header rows a piece was given.
PREFIX_KEY = "table_header_prefix"


def _is_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def header_rows(content: str, offset: int) -> str:
    """The header row and separator row of the table the row at ``offset`` continues.

    Empty when the text at ``offset`` is not a table row, or the rows above it in ``content``
    reach no header (a header row directly followed by a separator row) without leaving the
    table, or the row at ``offset`` is the header row or the separator row itself.
    """
    if not _is_row(content[offset:].split("\n", 1)[0]):
        return ""
    lines = content[:offset].split("\n")
    if lines and lines[-1].strip() == "":
        lines.pop()
    for index in range(len(lines) - 1, 0, -1):
        line = lines[index]
        if not _is_row(line):
            return ""
        if SEPARATOR_ROW.match(line) and _is_row(lines[index - 1]):
            return lines[index - 1].rstrip() + "\n" + line.rstrip()
    return ""


def prefix(text: str, metadata: Mapping[str, Any] | None) -> int:
    """How many first characters of a chunk's body are header rows the chunker put there."""
    recorded = (metadata or {}).get(PREFIX_KEY)
    if isinstance(recorded, int) and not isinstance(recorded, bool) and 0 < recorded <= len(text):
        return recorded
    return 0
