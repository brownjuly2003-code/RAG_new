"""The shared capsule-honesty contract, pinned at its own boundary.

`tests/capsule_prose.py` states once what the number guard of every evidence
capsule enforces; `tests/test_gr_bucket_baseline.py` and
`tests/test_section_coherence_arm.py` run it over their own capsule and report,
and prove it there by mutation. These tests pin the contract itself, apart from
either capsule: which numbers it reads as claims and which it exempts, so that
widening it to close a hole cannot quietly swallow a version string or a stream
id, and narrowing it cannot quietly reopen the hole.

The hole this module was written for: T-12's guard ended its decimal pattern
with ``(?![\\d.])``, so a metric that ends a sentence — "precision over one case
is 0.5401." — matched nothing and a wrong value there passed. T-13 fixed only its
own copy, and its copy was blind to prose integers and to three of its four
tables until later passes. One matcher, one list of exemptions, one check.

Review passes then found shapes that fell out of every rule — ``1.2e-4``,
``1.234.567``, prose between two nested fences. They are not pinned here as a
list of known shapes: the invariant is that every maximal digit run lands in
exactly one of three buckets (claim, named exemption, unread defect), and it is
checked over generated shapes and over every short string of digits and
separators, so a shape nobody has thought of fails as unread instead of
vanishing.
"""

from __future__ import annotations

import re
from itertools import product
from pathlib import Path

import pytest

import tests.capsule_prose as capsule_prose
from tests.capsule_prose import (
    CLAIM,
    EXEMPT,
    EXEMPTIONS,
    NON_REPORT_PHRASES,
    UNREAD,
    Run,
    capsule_defects,
    capsule_tables,
    fence_defects,
    numeric_claims,
    prose_lines,
    read_numbers,
    unreported_numbers,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAPSULES = (
    PROJECT_ROOT / "docs" / "evidence" / "gr0-bucket-baseline.md",
    PROJECT_ROOT / "docs" / "evidence" / "gr1a-section-coherence.md",
)


@pytest.mark.parametrize(
    ("text", "claims"),
    [
        # The hole: a value that ends a sentence is still a value.
        ("precision over one case is 0.5401.", ["0.5401"]),
        ("the reranker's own order scored 0.6412.", ["0.6412"]),
        ("recall 0.5000, PART", ["0.5000"]),
        # A decimal is read whole at any precision and magnitude, never a prefix.
        ("at 3.94 documents per case", ["3.94"]),
        ("a value of 0.12345 here", ["0.12345"]),
        ("a value of 12.5 here", ["12.5"]),
        # Integers: the class T-12's guard never read and T-13 shipped wrong.
        ("11 of the 394 selected chunks", ["11", "394"]),
        ("keyword **87 / 7 / 6**.", ["87", "7", "6"]),
        ("a 6000-char context", ["6000"]),
        # A thousands separator groups one number; it does not hide it.
        ("7,692,098 bytes", ["7,692,098"]),
        # A printed sign is part of the claim.
        ("-0.0016", ["-0.0016"]),
        ("+0.0149", ["+0.0149"]),
        ("a range of 5-10", ["5", "10"]),
    ],
)
def test_every_shape_of_number_is_read_as_a_claim(text: str, claims: list[str]) -> None:
    assert numeric_claims(text) == claims


@pytest.mark.parametrize(
    "text",
    [
        # Version strings, mid-sentence and ending one.
        "schema 1.0.3 here",
        "the schema is 1.0.3.",
        "package 2.11.0",
        # Stream and slice ids, mid-sentence and ending one.
        "the finding of GR-0.3 follows GR-0.2's ask",
        "this follows GR-0.2.",
        "T-12 and T-13, GR-1b, v1.0",
        # A number glued to a name names the thing.
        "top-5 over BGE-M3 + bge-reranker-v2-m3",
        "sha256 and SHA-256, phase C.1a, п.3",
        "c1a-qwen25-7b-c06bdf5 and aircargo-warehouse-3pl-escalation",
        "gr0-bucket-baseline and plan_06_09_26",
        # Dates and code are not quotes of a measurement.
        "Date: 2026-09-09",
        "reports `null`, never `0.0000`",
    ],
)
def test_names_versions_dates_and_code_are_not_claims(text: str) -> None:
    assert numeric_claims(text) == []
    assert all(run.bucket == EXEMPT for run in read_numbers(text)), read_numbers(text)


def test_a_number_is_reported_only_as_the_report_renders_it() -> None:
    decimals = [0.5401, -0.0016, 3.94, 0.00012, 0.00003]
    integers = {394, 7692098, -3, 1234567}

    def unreported(line: str) -> list[str]:
        return unreported_numbers([line], decimals=decimals, integers=integers)

    # Prefix-rounding at the precision the capsule wrote it to, never a fixed one.
    assert unreported("0.5401, 0.540, 0.54 and 0.5 over one") == []
    assert unreported("0.64 over one") == ["0.64"]
    assert unreported("is 0.6401.") == ["0.6401"]
    assert unreported("at 3.94 documents") == []
    # An unsigned quote may state a magnitude; a printed sign must be the report's.
    assert unreported("the re-ordering loses 0.0016") == []
    assert unreported("-0.0016") == []
    assert unreported("+0.0016") == ["+0.0016"]
    assert unreported("FULL falls by 3") == []
    assert unreported("+3") == ["+3"]
    # Integers exactly, zero-padding included; a grouped number by its value.
    assert unreported("394 selected") == []
    assert unreported("494 selected") == ["494"]
    assert unreported("0394 selected") == ["0394"]
    assert unreported("7,692,098 bytes") == []
    assert unreported("7,692,099 bytes") == ["7,692,099"]
    assert unreported("1,234,567 chunks selected") == []
    # A number the guard cannot read is a defect, never a skip — even when the
    # report carries the value it would mean (0.00012, 0.00003, 1234567).
    assert unreported("7692,098 bytes") == ["7692,098"]
    assert unreported("at .5 precision") == [".5"]
    assert unreported("a delta of 1.2e-4 here") == ["1.2e-4"]
    assert unreported("at 3e-5 documents") == ["3e-5"]
    assert unreported("1.234.567 chunks selected") == ["1.234.567"]


def _bucket_label(run: Run) -> str:
    return run.why if run.bucket == EXEMPT else run.bucket


def _read_every_digit_run_once(text: str) -> list[Run]:
    """``read_numbers(text)``, checked against the three-bucket invariant.

    Every run is in exactly one bucket, an exemption names an ``EXEMPTIONS``
    rule and nothing else does, runs do not overlap, and every maximal run of
    digit characters in ``text`` lies whole inside exactly one run.
    """
    runs = read_numbers(text)
    for run in runs:
        assert run.bucket in (CLAIM, EXEMPT, UNREAD), (text, run)
        assert (run.bucket == EXEMPT) == (run.why in EXEMPTIONS), (text, run)
        assert any(char.isdigit() for char in text[run.start : run.end]), (text, run)
    for left, right in zip(runs, runs[1:], strict=False):
        assert left.end <= right.start, (text, left, right)
    for found in re.finditer(r"\w+", text):  # digit runs sit inside word characters
        index = found.start()
        while index < found.end():
            if not text[index].isdigit():
                index += 1
                continue
            end = index
            while end < found.end() and text[end].isdigit():
                end += 1
            owners = [run for run in runs if run.start < end and index < run.end]
            assert len(owners) == 1, (text, text[index:end], owners)
            assert owners[0].start <= index and end <= owners[0].end, (text, owners)
            index = end
    return runs


def _shapes() -> list[tuple[str, str]]:
    """Generated number shapes, each with the bucket label its runs must carry.

    The label is ``CLAIM``, ``UNREAD`` or the ``EXEMPTIONS`` rule that covers it.
    """
    shapes: list[tuple[str, str]] = []
    # plain, zero-padded, decimal at every precision, signed
    shapes += [(digits, CLAIM) for digits in ("0", "7", "394", "6000", "0394")]
    shapes += [
        (f"{whole}.{fraction}", CLAIM)
        for whole in ("0", "3", "12")
        for fraction in ("5", "54", "5401", "12345")
    ]
    shapes += [(sign + value, CLAIM) for sign in "-+−" for value in ("0.0016", "3")]
    # grouped by comma: a grouping, a misgrouping, a European decimal comma
    shapes += [(value, CLAIM) for value in ("1,000", "7,692,098", "12,345.5")]
    shapes += [(value, UNREAD) for value in ("7692,098", "1,2", "12,34,567", "12,5")]
    # grouped by dot, and a dot grouping with a decimal comma
    shapes += [(value, UNREAD) for value in ("1.234.567", "12.345.678", "1.000.000", "1.234,5")]
    # scientific, with and without a decimal mantissa, a signed exponent, a sign
    shapes += [
        (f"{sign}{mantissa}{e}{exponent_sign}{exponent}", UNREAD)
        for sign in ("", "-")
        for mantissa in ("1", "1.2", "12.5")
        for e in "eE"
        for exponent_sign in ("", "+", "-", "−")
        for exponent in ("4", "12")
    ]
    # version-like, date-like, id-like, glued to a letter
    shapes += [(value, "version") for value in ("1.0.3", "2.11.0", "10.2.1.4")]
    shapes += [("2026-09-09", "date"), ("1999-12-31", "date")]
    shapes += [(value, "identifier") for value in ("GR-0.3", "T-12", "top-5", "BGE-M3", "C.1a")]
    shapes += [(value, "identifier") for value in ("п.3", "7b", "3pl", "sha256", "v1.0", "plan_06")]
    # a leading dot, code, a named phrase, a digit outside 0-9
    shapes += [(value, UNREAD) for value in (".5", ".5401")]
    shapes += [(value, "code") for value in ("`0.0000`", "`1.2e-4`", "`1.234.567`")]
    shapes += [(phrase, "phrase") for phrase, _reason in NON_REPORT_PHRASES]
    shapes += [(value, UNREAD) for value in ("٣", "１２", "10⁴", "1٣")]
    return shapes


_NEUTRAL_BEFORE = ("", "at ", "(", "**")
_NEUTRAL_AFTER = ("", ".", ",", " cases", ")", "**", "%")
_GLUING = ("x", "_", "-", ".", ",", "e", "1", "`", "+")


@pytest.mark.parametrize(("shape", "label"), _shapes(), ids=lambda value: str(value))
def test_every_digit_run_lands_in_exactly_one_bucket(shape: str, label: str) -> None:
    """The invariant over a generated set of shapes, in every neutral context.

    In a sentence the shape lands in the bucket it is listed with; glued to any
    neighbour it may land elsewhere, but still in exactly one bucket.
    """
    for before, after in product(_NEUTRAL_BEFORE, _NEUTRAL_AFTER):
        text = f"{before}{shape}{after}"
        runs = _read_every_digit_run_once(text)
        assert runs and {_bucket_label(run) for run in runs} == {label}, (text, runs)
    for before, after in product(("", *_GLUING), ("", *_GLUING)):
        _read_every_digit_run_once(f"{before}{shape}{after}")


def test_no_short_string_of_digits_and_separators_escapes_the_buckets() -> None:
    """Every string of up to four characters from a number-making alphabet.

    This is the check a list of shapes cannot be: it holds for shapes nobody
    listed. Every claim it finds is also checked against a report, so a claim
    the renderer cannot parse fails here rather than in a capsule.
    """
    alphabet = ("1", "0", ".", ",", "-", "+", "−", "e", "a", "_", "`", " ", "٣")
    checked = 0
    for length in range(1, 5):
        for chars in product(alphabet, repeat=length):
            text = "".join(chars)
            runs = _read_every_digit_run_once(text)
            unread = [run.text for run in runs if run.bucket == UNREAD]
            found = unreported_numbers([text], decimals=[1.0, 0.1], integers={1, 10, 0})
            assert all(number in found for number in unread), (text, runs, found)
            checked += 1
    assert checked == sum(len(alphabet) ** length for length in range(1, 5))


def test_every_exemption_is_named_once_with_its_reason() -> None:
    """The docstring's list, ``EXEMPTIONS`` and the rules ``read_numbers`` applies agree."""
    listed = re.findall(r"^\* \*(\w+)\* —", capsule_prose.__doc__ or "", flags=re.MULTILINE)
    assert listed == list(EXEMPTIONS)
    assert all(reason.strip() for reason in EXEMPTIONS.values())
    applied = {
        run.why
        for shape, _label in _shapes()
        for run in read_numbers(shape)
        if run.bucket == EXEMPT
    }
    assert applied == set(EXEMPTIONS), "every named rule is exercised by a generated shape"


def test_an_exemption_never_takes_part_of_a_longer_number() -> None:
    """A phrase or a date that starts or ends inside a number exempts nothing of it."""
    for text, claims in (
        ("196 / 3 / 1: D2 measures", ["196", "3", "1"]),
        ("0.96 / 3 / 1: D2 measures", ["0.96", "3", "1"]),
        ("the 96 % does not", []),
        ("§4 п.3–45", ["4", "45"]),
        ("12026-09-09", ["12026", "09", "09"]),
    ):
        assert numeric_claims(text) == claims, text
        _read_every_digit_run_once(text)


def test_every_named_exemption_is_load_bearing_and_covers_only_its_own_phrase() -> None:
    """An exemption names the exact phrase, with its reason, in one place.

    It has to cover a phrase one of the capsules actually carries (otherwise it
    is dead weight), it has to exempt at least one number (otherwise it is
    decoration), and changing any digit in it has to drop the number back into
    the guard — so no exemption can cover a wrong number.
    """
    texts = [path.read_text(encoding="utf-8") for path in CAPSULES]
    for phrase, reason in NON_REPORT_PHRASES:
        assert reason.strip(), f"the exemption {phrase!r} carries no reason"
        assert any(phrase in text for text in texts), (
            f"the exemption {phrase!r} ({reason}) matches no capsule; delete it"
        )
        assert numeric_claims(phrase, phrases=()), f"{phrase!r} exempts no number"
        assert numeric_claims(phrase) == []
        for found in re.finditer(r"\d", phrase):
            digit = found.start()
            changed = phrase[:digit] + str((int(phrase[digit]) + 1) % 10) + phrase[digit + 1 :]
            assert numeric_claims(changed), f"{changed!r} is still exempt"


def test_the_contract_reads_prose_and_every_table_of_any_width() -> None:
    """One entry point: prose, a wide table and a two-column table alike."""
    capsule = "\n".join(
        [
            "# A capsule",
            "",
            "precision is 0.5401.",
            "",
            "| class | cases | precision |",
            "|---|---:|---:|",
            "| multi_hop | 1 | 0.5401 |",
            "",
            "| | |",
            "|---|---|",
            "| Pool | 7,692,098 bytes |",
            "",
            "```",
            "a literal 999 in a fenced block",
            "```",
        ]
    )
    decimals = [0.5401]
    integers = {1, 7692098}

    assert capsule_defects(capsule, decimals=decimals, integers=integers) == []
    for honest, wrong in (
        ("precision is 0.5401.", "precision is 0.6401."),
        ("| multi_hop | 1 | 0.5401 |", "| multi_hop | 2 | 0.5401 |"),
        ("| Pool | 7,692,098 bytes |", "| Pool | 7,692,099 bytes |"),
        ("precision is 0.5401.", "precision is 5.401e-1."),
        ("| Pool | 7,692,098 bytes |", "| Pool | 7.692.098 bytes |"),
    ):
        mutated = capsule.replace(honest, wrong)
        assert capsule_defects(mutated, decimals=decimals, integers=integers), wrong


_FENCED_CAPSULE = (
    "# A capsule",
    "",
    "precision is 0.5401.",
    "",
    "```",
    "a literal 999 in a fenced block",
    "```",
    "",
    "| class | cases |",
    "|---|---:|",
    "| multi_hop | 1 |",
    "",
    "the tail repeats 0.5401 over 1 case.",
)


def test_a_stray_fence_is_a_defect_never_an_exemption() -> None:
    """A fenced block is exempt only because it closes.

    The first form of this module toggled a flag on every fence line and never
    checked the count, so one stray fence made every prose line and table after
    it invisible: a tail quoting 9.9999 and 42 against a report carrying neither
    passed. A stray fence has to fail the capsule wherever it lands, whether or
    not what it would have hidden is honest.
    """
    decimals = [0.5401]
    integers = {1}
    honest = "\n".join(_FENCED_CAPSULE)
    wrong_tail = honest.replace("repeats 0.5401 over 1 case", "repeats 9.9999 over 42 cases")

    def defects(capsule: str) -> list[str]:
        return capsule_defects(capsule, decimals=decimals, integers=integers)

    # Balanced fences: the honest capsule passes and the wrong tail is caught.
    assert defects(honest) == []
    assert defects(wrong_tail) == [
        "prose quotes 9.9999, which the report does not carry",
        "prose quotes 42, which the report does not carry",
    ]
    # One stray fence at every position — before the tail, inside the block,
    # before the table, at either end — fails the capsule loudly.
    for capsule in (honest, wrong_tail):
        lines = capsule.splitlines()
        for at in range(len(lines) + 1):
            stray = "\n".join([*lines[:at], "```", *lines[at:]])
            found = defects(stray)
            assert len(found) == 1 and "ends inside a code fence" in found[0], (at, found)
            with pytest.raises(AssertionError, match="ends inside a code fence"):
                prose_lines(stray)
            with pytest.raises(AssertionError, match="ends inside a code fence"):
                capsule_tables(stray)


def _between_blocks(first: list[str], second: list[str]) -> str:
    return "\n".join(
        [
            "# A capsule",
            "",
            "precision is 0.5401.",
            "",
            *first,
            "",
            "the tail repeats 0.5401 over 1 case.",
            "",
            *second,
            "",
            "| class | cases |",
            "|---|---:|",
            "| multi_hop | 1 |",
        ]
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # Two four-backtick blocks, each quoting a three-backtick line: six lines
        # start with ``` (an even count), and a toggle on each dropped the tail.
        (
            ["````", "```", "an example 999", "````"],
            ["````markdown", "```", "an example 777", "````"],
        ),
        # Only one inner line: an odd count, which a toggle falsely rejected.
        (["````", "```", "an example 999", "````"], ["````", "an example 777", "````"]),
        # Tildes close tildes, and a backtick line inside them is a literal.
        (["~~~", "```", "an example 999", "~~~~"], ["```", "~~~", "an example 777", "```"]),
        # A line of inline code that starts with three backticks is not a fence.
        (["```x``` is inline code"], ["```y``` is inline code too"]),
    ],
)
def test_a_fence_closes_only_what_it_opened(first: list[str], second: list[str]) -> None:
    """Prose between two fenced blocks is prose, however the blocks nest."""
    decimals = [0.5401]
    integers = {1}
    honest = _between_blocks(first, second)
    wrong_tail = honest.replace("repeats 0.5401 over 1 case", "repeats 9.9999 over 42 cases")

    def defects(capsule: str) -> list[str]:
        return capsule_defects(capsule, decimals=decimals, integers=integers)

    assert fence_defects(honest) == []
    assert "the tail repeats 0.5401 over 1 case." in prose_lines(honest)
    assert list(capsule_tables(honest)) == ["class"]
    assert defects(honest) == []  # 999 and 777 are literals
    assert defects(wrong_tail) == [
        "prose quotes 9.9999, which the report does not carry",
        "prose quotes 42, which the report does not carry",
    ]


@pytest.mark.parametrize(
    "block",
    [
        ["````", "a literal", "```"],  # shorter than its opener
        ["~~~", "a literal", "```"],  # the other character
        ["```", "a literal", "```` not a closer"],  # a closing fence carries nothing else
    ],
)
def test_a_fence_that_does_not_close_what_it_opened_is_a_defect(block: list[str]) -> None:
    found = capsule_defects(_between_blocks(block, []), decimals=[0.5401], integers={1})
    assert len(found) == 1 and "ends inside a code fence" in found[0], found


@pytest.mark.parametrize("path", CAPSULES, ids=lambda path: path.name)
def test_both_published_capsules_close_every_fence(path: Path) -> None:
    """FALSE-REJECT CONTROL: the fence check rejects neither published capsule."""
    text = path.read_text(encoding="utf-8")
    assert fence_defects(text) == []
    assert prose_lines(text)
    assert capsule_tables(text)


@pytest.mark.parametrize("path", CAPSULES, ids=lambda path: path.name)
def test_both_published_capsules_leave_no_number_unread(path: Path) -> None:
    """FALSE-REJECT CONTROL: the invariant rejects no number either capsule publishes.

    Every raw line keeps the invariant, and no prose line or table cell carries
    a run the guard cannot read — their claims are checked against each report
    by the capsule's own test.
    """
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        _read_every_digit_run_once(line)
    cells = [cell for rows in capsule_tables(text).values() for row in rows for cell in row]
    unread = [
        (piece, run)
        for piece in [*prose_lines(text), *cells]
        for run in read_numbers(piece)
        if run.bucket == UNREAD
    ]
    assert unread == []
