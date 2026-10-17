"""Gold of an external base read by source ranges (plan step 1.5): the range-coverage rule."""

import pytest

from evaluation import external_convert as convert
from evaluation import external_gold as gold
from evaluation.external_convert import Block
from vectordb import _base_manager as base_manager
from vectordb import manager, parent_join

HEADER = "[Контекст: Из документа a.md, раздел: T]\n"


def chunk(text: str, source: str = "a.md", *, header: bool = True) -> dict:
    return {"page_content": (HEADER if header else "") + text, "metadata": {"source": source}}


def test_visible_characters_are_the_coordinates_of_a_document() -> None:
    text, before = gold.visible("a b \n​c\t")

    # Whitespace of any kind and non-printable characters are not counted.
    assert text == "abc"
    assert before == [0, 1, 1, 2, 2, 2, 2, 3, 3]
    source = gold.Source.read("a.md", "# T\n\nab ab\n")
    assert source.text == "#Tabab"
    assert source.place(5, 10) == (2, 6)
    assert source.occurrences("a b") == [(2, 4), (4, 6)]
    assert source.occurrences("ab", within=(3, 6)) == [(4, 6)]
    assert gold.Source.read("b.md", "aaa").occurrences("aa") == [(0, 2), (1, 3)]
    assert source.occurrences(" \n") == []


def test_strip_header_mirrors_parent_expansion() -> None:
    for text in (HEADER + "body\nmore", "body", "[Контекст: no line break]"):
        expected = base_manager.HybridRetriever._strip_contextual_header(text)
        assert gold.strip_header(text) == expected


def test_a_chunk_stands_where_the_previous_one_ended_or_repeats_its_end() -> None:
    source = gold.Source.read("a.md", "Title\n\nintro Title one two\n\nTitle\n\nthree four\n")
    other = gold.Source.read("b.md", "three four\n")
    chunks = [
        chunk("Title  \nintro Title one"),
        chunk("one two"),  # repeats the end of the previous chunk
        chunk("Title"),  # a section that repeats an earlier text: not the first occurrence
        chunk("three four"),
        chunk("three four", "b.md", header=False),
        chunk("absent"),
        chunk("\n \n"),
        chunk("three", "c.md"),
    ]

    places = gold.locate_chunks(chunks, {"a.md": source, "b.md": other}, overlap=5)

    assert places == [(0, 18), (15, 21), (21, 26), (26, 35), (0, 9), None, None, None]
    assert gold.uncovered(len(source.text), [place for place in places[:4] if place]) == 0


def test_presence_is_coverage_by_the_union_of_places() -> None:
    assert gold.covered((5, 9), [(0, 6), (6, 12)])
    assert gold.covered((5, 9), [(7, 12), (0, 7)])
    assert not gold.covered((5, 9), [(0, 6), (7, 12)])
    assert not gold.covered((5, 9), [(6, 12)])
    assert not gold.covered((5, 5), [(0, 12)])
    assert gold.state((5, 9), [(0, 6), (4, 10)]) == "whole"
    assert gold.state((5, 9), [(0, 6), (6, 12)]) == "split"
    assert gold.state((5, 9), [(0, 6)]) == "lost"
    assert gold.state((5, 5), [(0, 12)]) == "lost"
    assert gold.uncovered(12, [(2, 5), (4, 7), (9, 10)]) == 2 + 2 + 2
    assert gold.uncovered(3, []) == 3


def test_expansion_members_of_hand_made_chunks() -> None:
    chunks = [chunk(text) for text in ("zero", "one", "two", "three", "four")]
    chunks.append(chunk("five", "b.md"))
    seed = chunks[2]["page_content"]

    assert gold.expansion_members(seed, 2, chunks, 2) == [2]
    assert gold.expansion_members("zero\n\none\n\n" + seed + "\n\nthree", 2, chunks, 2) == [
        0,
        1,
        2,
        3,
    ]
    # a neighbour inside the window may be left out
    assert gold.expansion_members("zero\n\n" + seed + "\n\nfour", 2, chunks, 2) == [0, 2, 4]
    # the window ends at the document's end
    assert gold.expansion_members("three\n\n" + chunks[4]["page_content"], 4, chunks, 2) == [3, 4]
    with pytest.raises(ValueError, match="not an expansion of chunk 4"):
        gold.expansion_members(chunks[4]["page_content"] + "\n\nfive", 4, chunks, 2)
    with pytest.raises(ValueError, match="not an expansion of chunk 2"):
        gold.expansion_members("one\n\nzero\n\n" + seed, 2, chunks, 2)


def _document() -> tuple[str, dict, list]:
    long_line = " ".join(f"word{index}" for index in range(140))  # one line longer than a chunk
    blocks = [Block("heading", "Guide", level=1)]
    blocks += [
        Block("para", f"Intro paragraph {index} " + "text " * 30, key=f"intro{index}")
        for index in range(4)
    ]
    blocks += [Block("heading", "Rules", level=2, key="rules")]
    blocks += [
        Block("item", f"rule {index} " + "detail " * 20, level=1, key=f"rule{index}")
        for index in range(8)
    ]
    blocks += [Block("para", long_line, key="long")]
    blocks += [Block("heading", "Rules", level=2, key="again"), Block("heading", "Empty", level=2)]
    blocks += [Block("para", "Guide", key="short")]
    text, spans = convert.render(blocks)
    document = base_manager.Document(page_content=text, metadata={"source": "guide.md"})
    split = base_manager.structural_split([document], max_chunk_size=800, chunk_overlap=200)
    return text, spans, manager.add_contextual_headers(split, [document], chunk_size=800)


def test_the_rule_reads_the_chunks_of_the_product_splitter() -> None:
    text, spans, documents = _document()
    source = gold.Source.read("guide.md", text)
    chunks = [{"page_content": d.page_content, "metadata": dict(d.metadata)} for d in documents]

    places = gold.locate_chunks(chunks, {"guide.md": source}, overlap=200)

    assert all(place is not None for place in places)
    found = [place for place in places if place is not None]
    assert found == sorted(found)
    # No visible character of the document is outside its chunks.
    assert gold.uncovered(len(source.text), found) == 0
    states = {key: gold.state(source.place(*span), found) for key, span in spans.items()}
    # A line longer than a chunk is cut: no chunk holds it whole, adjacent chunks hold it together.
    assert states.pop("long") == "split"
    assert set(states.values()) == {"whole"}
    # The second heading "Rules" and the short paragraph "Guide" repeat earlier texts of the
    # document; each is held by the chunk that stands at its own place.
    for key in ("again", "short"):
        target = source.place(*spans[key])
        holders = [place for place in found if place[0] <= target[0] and target[1] <= place[1]]
        assert holders and all(place[0] > source.place(*spans["long"])[0] for place in holders)


def test_expansion_members_read_what_parent_expansion_joined() -> None:
    _, _, documents = _document()
    chunks = [{"page_content": d.page_content, "metadata": dict(d.metadata)} for d in documents]
    retriever = base_manager.HybridRetriever.__new__(base_manager.HybridRetriever)
    retriever._chunks = documents
    retriever._doc_key_chars = 200
    retriever._parent_window = 2
    retriever._parent_max_chars = 3600
    retriever._chunk_positions = {}
    for index, document in enumerate(documents):
        retriever._chunk_positions.setdefault(base_manager._rrf_document_key(document, 200), index)
    last = len(documents) - 1
    seamed = 0

    for seeds in ([3], [0], [last], [2, 3], [1, 5], [0, last]):
        sent = retriever._expand_parents([documents[seed] for seed in seeds])
        taken: set[int] = set()
        for seed, document in zip(seeds, sent, strict=True):
            members = gold.expansion_members(document.page_content, seed, chunks, window=2)
            assert seed in members and members == sorted(members)
            assert all(abs(member - seed) <= 2 for member in members)
            # the members give the sent text back: the seed's header first, then the bodies
            # in document order, each seam once
            header = f"[{chunks[seed]['metadata']['contextual_header']}]"
            pieces = [
                (
                    member,
                    gold.strip_header(
                        chunks[member]["page_content"], chunks[member]["metadata"]
                    ).strip(),
                    chunks[member]["metadata"],
                )
                for member in members
            ]
            assert parent_join.join(header, pieces) == document.page_content
            seamed += sum(
                chunks[after]["metadata"][parent_join.SEAM_KEY]
                for before, after in zip(members, members[1:], strict=False)
                if after == before + 1
            )
            # a chunk is joined into one sent document only
            assert not taken & set(members)
            taken |= set(members)
        assert len(taken) > len(seeds)
    # The long section's pieces overlap: some joins above read a seam once.
    assert seamed > 0
