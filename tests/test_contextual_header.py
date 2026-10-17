"""The contextual header of a chunk (PLAN.md stage 1, docs/specs/stage1-fixes.md rows 5–7).

Until stage 1 every chunk of every corpus began with the Russian phrase
«[Контекст: Из документа …, раздел: …]», cut at 200 characters from its end, which lost the
heading nearest to the text on 8–34 % of the chunks of the external bases and named a document
twice when its file was the slug of its title. The header is now ``[document › section]``, with
no word of any language; the old form is still read, so the collections built before stage 1
stay readable.
"""

from __future__ import annotations

import re

from vectordb import contextual_header as ch


def test_a_file_named_by_the_slug_of_its_title_stands_once():
    assert ch.header_parts("leave-and-pay.md", ["Leave and pay", "Overview"]) == [
        "Leave and pay",
        "Overview",
    ]
    # Accents and case do not make two titles of one.
    assert ch.header_parts("cafe-menu.md", ["Café Menu"]) == ["Café Menu"]


def test_the_longer_of_file_name_and_title_is_kept():
    # A slug with a disambiguating suffix holds more words than the title: the name stays.
    assert ch.header_parts("leave-and-pay-3f2a1b9c.md", ["Leave and pay", "Overview"]) == [
        "leave-and-pay-3f2a1b9c.md",
        "Overview",
    ]
    # A title that holds the file's words in a row — source, date, then the title.
    assert ch.header_parts("big-merger.md", ["Reuters, 2023-10-01, Big merger"]) == [
        "Reuters, 2023-10-01, Big merger"
    ]


def test_a_file_name_unlike_the_title_is_kept_beside_it():
    assert ch.header_parts(
        "01_hr_dismissal_procedure.md", ["Регламент увольнения", "Назначение"]
    ) == [
        "01_hr_dismissal_procedure.md",
        "Регламент увольнения",
        "Назначение",
    ]
    assert ch.header_parts("notes.txt", []) == ["notes.txt"]


def test_a_header_within_the_limit_is_the_whole_path():
    assert ch.compose(["a.md", "Part", "Section"]) == "a.md › Part › Section"


def test_outer_levels_go_first_and_the_nearest_heading_stays():
    parts = ["guide.md", "A" * 80, "B" * 80, "Nearest heading"]
    assert ch.compose(parts, 100) == "guide.md › … › Nearest heading"
    middle = ["guide.md", "A" * 50, "B" * 30, "Nearest heading"]
    assert ch.compose(middle, 70) == "guide.md › … › " + "B" * 30 + " › Nearest heading"


def test_a_document_and_a_nearest_heading_too_long_together_are_both_shortened():
    header = ch.compose(["d" * 150, "h" * 150], 200)
    assert len(header) == 200
    document, nearest = header.split(ch.SEPARATOR)
    assert document.endswith(ch.ELISION) and nearest.endswith(ch.ELISION)
    assert len(nearest) > len(document)
    assert ch.compose(["x" * 250], 200) == "x" * 199 + ch.ELISION


def test_the_header_of_a_chunk_has_no_word_of_its_own():
    metadata = {"source": "returns.md", "h1": "Returns", "h2": "Refund window", "page": 3}
    header = ch.for_chunk(metadata)
    assert header == "Returns › Refund window"
    assert not re.search(r"[А-Яа-яЁё]", ch.render(header))
    assert ch.for_chunk({}) == "unknown"


def test_split_finds_the_header_through_the_metadata():
    metadata = {"contextual_header": "a.md › Fees"}
    assert ch.split("[a.md › Fees]\nbody\nmore", metadata) == ("[a.md › Fees]", "body\nmore")
    assert ch.split("[a.md › Fees]", metadata) == ("[a.md › Fees]", "")
    assert ch.strip("[a.md › Fees]\nbody", metadata) == "body"


def test_a_chunk_that_begins_with_a_bracket_is_not_taken_for_a_header():
    text = "[Pricing](https://example.com/pricing) lists the plans.\nMore."
    assert ch.split(text) == ("", text)
    assert ch.split(text, {"contextual_header": "other.md"}) == ("", text)


def test_the_header_written_before_stage_1_is_still_read():
    legacy = "[Контекст: Из документа a.md, раздел: T]\nbody"
    assert ch.split(legacy) == ("[Контекст: Из документа a.md, раздел: T]", "body")
    # A legacy header with no line break is left as the readers left it.
    assert ch.split("[Контекст: only]") == ("", "[Контекст: only]")


def test_is_header_line():
    metadata = {"contextual_header": "a.md › Fees"}
    assert ch.is_header_line("  [a.md › Fees] \n", metadata)
    assert ch.is_header_line("[Контекст: Из документа a.md]")
    assert not ch.is_header_line("[a.md › Fees]")
    assert not ch.is_header_line("Fees are listed below.", metadata)
