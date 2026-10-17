"""Parent expansion joins a chunk with its neighbours once (docs/specs/stage1-fixes.md row 9).

A long section is cut into pieces that overlap by up to 200 characters; until stage 1
expansion glued neighbouring pieces with their overlap, so the prompt read the seam twice, and
the retrieved chunk's header stood in the middle of the joined text when neighbours came
before it.
"""

from __future__ import annotations

import pytest

from vectordb import parent_join

SECTION = {"h1": "Guide", "h2": "Fees"}


def test_two_pieces_of_one_section_are_joined_over_their_overlap():
    seam = "the fee is charged once a month"
    first = "Plans differ in price, and " + seam
    second = seam + " on the day the plan started."
    joined = parent_join.join("", [(4, first, SECTION), (5, second, SECTION)])
    assert joined == "Plans differ in price, and " + seam + " on the day the plan started."
    assert joined.count(seam) == 1


def test_the_header_stands_once_and_first():
    joined = parent_join.join(
        "[guide.md › Fees]",
        [(6, "after", SECTION), (4, "before", SECTION), (5, "retrieved", SECTION)],
    )
    assert joined == "[guide.md › Fees]\nbefore\n\nretrieved\n\nafter"


def test_pieces_of_different_sections_or_apart_are_not_trimmed():
    seam = "a sentence long enough to be an overlap"
    first, second = "One. " + seam, seam + " two."
    other = {"h1": "Guide", "h2": "Refunds"}
    assert parent_join.join("", [(1, first, SECTION), (2, second, other)]) == (
        first + "\n\n" + second
    )
    assert parent_join.join("", [(1, first, SECTION), (3, second, SECTION)]) == (
        first + "\n\n" + second
    )


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        # 19 characters repeat: shorter than MIN_OVERLAP, a coincidence.
        ("alpha beta gamma delta epsilon", "gamma delta epsilon zeta", 0),
        ("one two three four five six seven", "three four five six seven eight", 25),
        ("xx four five six seven eight", "four five six seven eight nine", 25),
        # The repeat starts inside a word of the first piece, or ends inside one of the second.
        ("prefix-four five six seven eight", "four five six seven eight nine", 0),
        ("ends four five six seven eight", "four five six seven eightieth", 0),
    ],
)
def test_overlap_counts_only_runs_of_whole_words(before, after, expected):
    assert parent_join.overlap(before, after) == expected


#: Every word different, so text that repeats is only a seam.
WORDS = [f"w{(index * 37) % 9973}" for index in range(1_800)]


def test_the_real_splitter_loses_no_word_and_repeats_none_by_text_match():
    """A collection cut before stage 1 has no seam record: the text match finds the seams."""
    splitters = pytest.importorskip("langchain_text_splitters")
    splitter = splitters.RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    # Long one-line paragraphs: the splitter cuts them between words, repeating up to 200
    # characters at each cut.
    text = "\n\n".join(" ".join(WORDS[start : start + 300]) for start in range(0, 1_800, 300))
    pieces = splitter.split_text(text)
    assert len(pieces) > 10
    joined = parent_join.join("", [(index, piece, SECTION) for index, piece in enumerate(pieces)])
    naive = "\n\n".join(pieces)
    assert joined.split() == text.split()
    assert len(naive) - len(text) > 2_000


def test_the_chunker_records_each_seam_it_cut():
    pytest.importorskip("langchain_text_splitters")
    from vectordb._base_manager import Document, structural_split

    page = "# Guide\n\n## Fees\n\n" + " ".join(WORDS[:600]) + "\n\n## Refunds\n\nShort."
    chunks = structural_split([Document(page_content=page, metadata={"source": "g.md"})], 800, 200)
    fees = [chunk for chunk in chunks if chunk.metadata.get("h2") == "Fees"]
    refunds = [chunk for chunk in chunks if chunk.metadata.get("h2") == "Refunds"]
    assert len(fees) > 3 and len(refunds) == 1
    assert fees[0].metadata[parent_join.SEAM_KEY] == 0
    assert refunds[0].metadata[parent_join.SEAM_KEY] == 0
    # The heading lines are a piece of their own, and the next piece repeats nothing of it.
    sizes = [chunk.metadata[parent_join.SEAM_KEY] for chunk in fees[1:]]
    assert all(0 <= size <= 200 for size in sizes) and sum(size > 0 for size in sizes) >= 3
    for before, after in zip(fees, fees[1:], strict=False):
        size = after.metadata[parent_join.SEAM_KEY]
        assert before.page_content.endswith(after.page_content[:size])
    joined = parent_join.join(
        "", [(index, chunk.page_content, chunk.metadata) for index, chunk in enumerate(fees)]
    )
    assert [word for word in joined.split() if word.startswith("w")] == WORDS[:600]
