"""Gold of an external base, read by ranges of the source document.

Our verified cases are read by text (``evaluation/gold_metrics.py``): a text holds a span when it
contains the span's normalised text whole. Gold of an external base is another kind of object: an
element of a document chosen by an annotator (ConditionalQA) or a sentence of an article
(MultiHop-RAG). Text containment fails it in three ways. A short element — a list item of two
words, a heading — is contained in many texts of its document that are not its place. An element
cut by the chunker is whole in no chunk, though two adjacent chunks hold it. And a sent document
joins a seed chunk with its neighbours, repeating the overlap between them, so the text of an
element that lies across two chunks is not contiguous in it. So gold of an external base is read
by where a text comes from, by the rule ``MATCH_RULE``:

- **Coordinates.** A document is the sequence of its visible characters — printable and not
  whitespace. Chunking re-joins the lines of a section, strips them, deletes invisible characters
  and puts a header line before the body; the visible characters and their order it leaves. A
  place in a document is a range of that sequence.
- **Gold.** An element's place is given by the conversion that wrote the document
  (``evaluation/external_convert.render``); a sentence's places are all the occurrences of its
  visible characters in the article body. An element or sentence that stands in several places
  of its document has every place as an alternative: nothing says which one the annotator meant,
  the first is not preferred, and a text at any of them is credited.
- **Chunks.** The place of a chunk is the place of its body's visible characters in its
  document, found in the order of the archive (``locate_chunks``).
- **Presence.** A gold place is present in a set of texts when the union of the texts' places in
  its document covers it. The texts are chunks of the index (a pool) or sent documents, each
  resolved into the chunks it was joined from (``expansion_members``). An evidence group is
  satisfied when one of its alternatives is present.

The rule credits an element that only two retrieved chunks hold together, and credits no text for
an element it merely repeats outside the places of that element. Among those places it cannot
tell which one the annotator meant. Our own verified cases keep
``verified-gold/text-containment-v1``: their spans were labelled as text, without places of the
kind this rule needs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

MATCH_RULE = "external-gold/range-coverage-v1"
STATES = ("whole", "split", "lost")

Range = tuple[int, int]


def visible(text: str) -> tuple[str, list[int]]:
    """The visible characters of a text and, for each offset, how many of them stand before it."""
    kept: list[str] = []
    before = [0] * (len(text) + 1)
    for offset, char in enumerate(text):
        before[offset] = len(kept)
        if char.isprintable() and not char.isspace():
            kept.append(char)
    before[len(text)] = len(kept)
    return "".join(kept), before


def strip_header(text: str, metadata: Mapping[str, Any] | None = None) -> str:
    """A chunk's text without its contextual header line, as parent expansion strips it."""
    from vectordb import contextual_header

    return contextual_header.strip(text, metadata)


@dataclass(frozen=True)
class Source:
    """One converted document in the coordinates of its visible characters."""

    name: str
    text: str
    before: Sequence[int]

    @classmethod
    def read(cls, name: str, markdown: str) -> Source:
        text, before = visible(markdown)
        return cls(name, text, before)

    def place(self, start: int, end: int) -> Range:
        """A character range of the document as a range of its visible characters."""
        return self.before[start], self.before[end]

    def occurrences(self, fragment: str, within: Range | None = None) -> list[Range]:
        """Every place where the fragment's visible characters stand, overlapping ones too."""
        needle = visible(fragment)[0]
        low, high = within if within is not None else (0, len(self.text))
        found: list[Range] = []
        if not needle:
            return found
        position = self.text.find(needle, low, high)
        while position != -1:
            found.append((position, position + len(needle)))
            position = self.text.find(needle, position + 1, high)
        return found


def locate_chunks(
    chunks: Sequence[Mapping[str, Any]], sources: Mapping[str, Source], overlap: int
) -> list[Range | None]:
    """The place of every chunk's body in its document; None for a chunk that has none.

    Chunks of a document stand in the archive in the order of the document. A chunk continues
    the document where the previous chunk of it ended — a new section, or a cut without a repeat
    — or repeats the end of that chunk, ``overlap`` characters at most. So its place is the end
    of the previous chunk when its text stands there, and otherwise its first occurrence that
    starts after the previous chunk's start and not earlier than ``overlap`` characters before
    its end. An equal text elsewhere in the document cannot take the place. A chunk put wrongly
    leaves characters of its document in no chunk, and ``uncovered`` counts them.
    """
    places: list[Range | None] = []
    last: dict[str, Range] = {}
    for chunk in chunks:
        name = str(chunk["metadata"].get("source") or "")
        source = sources.get(name)
        needle = visible(strip_header(chunk["page_content"], chunk["metadata"]))[0]
        if source is None or not needle:
            places.append(None)
            continue
        start, end = last.get(name, (-1, 0))
        if source.text.startswith(needle, end):
            position = end
        else:
            position = source.text.find(needle, max(start + 1, end - overlap))
        if position == -1:
            places.append(None)
            continue
        last[name] = (position, position + len(needle))
        places.append(last[name])
    return places


def covered(target: Range, places: Iterable[Range]) -> bool:
    """Whether the union of the places covers the target; an empty target is covered by none."""
    start, end = target
    if start >= end:
        return False
    reach = start
    for low, high in sorted(places):
        if low > reach:
            break
        reach = max(reach, high)
        if reach >= end:
            return True
    return False


def state(target: Range, places: Sequence[Range]) -> str:
    """How a set of chunks holds a gold place: one of them whole, several together, or not."""
    if (
        any(low <= target[0] and target[1] <= high for low, high in places)
        and target[0] < target[1]
    ):
        return "whole"
    return "split" if covered(target, places) else "lost"


def uncovered(length: int, places: Iterable[Range]) -> int:
    """Visible characters of a document of that length that stand in none of the places."""
    missing = 0
    reach = 0
    for low, high in sorted(places):
        if low > reach:
            missing += low - reach
        reach = max(reach, high)
    return missing + max(length - reach, 0)


def expansion_members(
    text: str, seed: int, chunks: Sequence[Mapping[str, Any]], window: int
) -> list[int]:
    """The chunks a sent document was joined from: its seed and the neighbours added to it.

    ``HybridRetriever._expand_parents`` joins, with an empty line between them, the stripped
    bodies of neighbours that stand before the seed, the seed's own text and the stripped bodies
    of neighbours after it. A neighbour inside the window may be left out — it was used by
    another document of the context, or it did not fit the budget. The members are found by
    trying the subsets of the window's neighbours, the smaller first: the first subset that
    gives exactly the text. No subset gives it — the text is not an expansion of this seed.
    """
    own = chunks[seed]["page_content"]
    if text == own:
        return [seed]
    source = chunks[seed]["metadata"].get("source")

    def side(positions: Iterable[int]) -> list[int]:
        return [
            position
            for position in positions
            if 0 <= position < len(chunks) and chunks[position]["metadata"].get("source") == source
        ]

    def body(position: int) -> str:
        return strip_header(chunks[position]["page_content"], chunks[position]["metadata"]).strip()

    before = side(range(seed - 1, seed - window - 1, -1))
    after = side(range(seed + 1, seed + window + 1))
    start = text.find(own)
    while start != -1:
        head, tail = text[:start], text[start + len(own) :]
        for taken_before in _subsets(before):
            if "".join(body(position) + "\n\n" for position in sorted(taken_before)) != head:
                continue
            for taken_after in _subsets(after):
                if "".join("\n\n" + body(position) for position in sorted(taken_after)) == tail:
                    return sorted([*taken_before, seed, *taken_after])
        start = text.find(own, start + 1)
    raise ValueError(f"the text is not an expansion of chunk {seed}")


def _subsets(positions: Sequence[int]) -> Iterable[tuple[int, ...]]:
    for size in range(len(positions) + 1):
        yield from combinations(positions, size)
