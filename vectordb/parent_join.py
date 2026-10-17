"""How parent expansion joins a retrieved chunk with its neighbours (PLAN.md stage 1).

A section longer than a chunk is cut into pieces that overlap by up to ``chunk_overlap``
characters, so two neighbouring pieces of one section repeat the same text at their seam.
Until stage 1 expansion joined them as they were and the prompt read that text twice. Here two
pieces that stand next to each other in their document and belong to one section are joined
over their overlap; any other two pieces are joined with an empty line. The header line of the
retrieved chunk stands once, first (before stage 1 it stood wherever that chunk fell).

Since stage 1 the chunker records the seam: ``structural_split`` writes under ``SEAM_KEY`` how
many characters at the start of a piece repeat the piece before it in its section (0 for the
first piece of a section), so the join is exact. A collection cut before stage 1 has no such
record, and the seam is found by matching text, bounded by the splitter's overlap.

Pure text, no models: ``HybridRetriever._expand_parents`` joins with it, and the gold metric of
the external bases (``evaluation/external_gold.py``) reads a sent document back with it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from vectordb import contextual_header

#: Shorter repeats are taken for a coincidence: a word that ends one piece and starts the next.
MIN_OVERLAP = 20
#: The splitter's ``chunk_overlap`` default: it never repeats more than this at a seam, so a
#: longer repeat is the document's own text and stays.
MAX_OVERLAP = 200
#: The metadata key of the seam the chunker recorded.
SEAM_KEY = "seam_overlap"

Piece = tuple[int, str, "Mapping[str, Any] | None"]


def overlap(before: str, after: str, limit: int = MAX_OVERLAP) -> int:
    """How many characters at the start of ``after`` repeat the end of ``before``.

    Only a run of whole words from ``MIN_OVERLAP`` to ``limit`` characters counts: the repeated
    text starts ``before`` or follows a space in it, and it ends ``after`` or is followed by a
    space — the boundaries at which the character splitter cuts with its default separators.
    """
    for size in range(min(len(before), len(after), limit), 0, -1):
        if not before.endswith(after[:size]):
            continue
        starts_a_word = size == len(before) or before[-size - 1].isspace()
        ends_a_word = size == len(after) or after[size].isspace()
        if size >= MIN_OVERLAP and starts_a_word and ends_a_word:
            return size
    return 0


def seam(
    before: str, text: str, metadata: Mapping[str, Any] | None, limit: int = MAX_OVERLAP
) -> int:
    """How many characters at the start of ``text`` repeat what stands before it.

    The chunker's record when the piece has one; otherwise the text match of ``overlap``.
    """
    recorded = (metadata or {}).get(SEAM_KEY)
    if isinstance(recorded, int) and not isinstance(recorded, bool) and 0 <= recorded <= len(text):
        return recorded
    return overlap(before, text, limit)


def same_section(first: Mapping[str, Any] | None, second: Mapping[str, Any] | None) -> bool:
    """Whether two chunks of one document carry the same heading path."""
    return contextual_header.heading_path(first) == contextual_header.heading_path(second)


def join(header: str, pieces: Sequence[Piece], limit: int = MAX_OVERLAP) -> str:
    """The header line, then the pieces in document order, each seam joined once.

    ``limit`` is the ``chunk_overlap`` the pieces were cut with.
    """
    body = ""
    previous: Piece | None = None
    for piece in sorted(pieces, key=lambda item: item[0]):
        position, text, metadata = piece
        if previous is None:
            body = text
        elif position == previous[0] + 1 and same_section(previous[2], metadata):
            cut = seam(body, text, metadata, limit)
            body += text[cut:] if cut else "\n\n" + text
        else:
            body += "\n\n" + text
        previous = piece
    return f"{header}\n{body}" if header else body
