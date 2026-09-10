"""The capsule-honesty contract, stated once for every evidence capsule.

An evidence capsule (``docs/evidence/*.md``) publishes a measurement whose
machine-readable record is a committed report (``reports/**.json``). Every
capsule guard imports this module, and the contract it enforces is:

    Every number in the capsule that is a claim about the measurement equals a
    number the committed report carries — in running prose or in any table of
    any width, at whatever precision it is written.

"Equals" means: an integer is exactly a report integer (``07`` does not render
the integer 7); a decimal is a report value rounded to the number of decimals
the capsule wrote (``0.5401``, ``0.540`` and ``0.54`` all render 0.5401, while
``0.64`` renders nothing and fails however few decimals it is written to); a
number printed with a sign has to match a signed report value, and an unsigned
one may quote a value's magnitude ("the re-ordering loses 0.0016").

Each capsule's own test decides which report values are in scope, because the
report schemas differ. This module decides what counts as a number and what is
exempt, so that two capsules can no longer carry two guards with one docstring.

**Three buckets, and no fourth.** Every maximal run of digits in the text lands
in exactly one of them, and ``read_numbers`` says which:

1. *claim* (``CLAIM``) — a plain, decimal or comma-grouped number, read whole
   with its printed sign, and checked against the report;
2. *exempt* (``EXEMPT``) — covered by one of the rules listed below, each named
   in ``EXEMPTIONS`` with its reason;
3. *unread* (``UNREAD``) — a run no rule reads: a leading-dot decimal (``.5``),
   separators that group no number (``7692,098``, ``1.234.567``), scientific
   notation (``1.2e-4``), a digit outside ``0-9``. It is a defect whatever the
   report carries, never a skip.

A run is a claim only when it has the claim shape and exempt only when a named
rule covers it; anything that reaches the end of the rules is unread, and a
final sweep puts any digit no reading reached into that bucket too. T-12's
guard matched ``\\d\\.\\d{1,4}`` followed by neither a digit nor a dot, so a
metric ending a sentence matched nothing; this module's own earlier form let a
number glued to an ``e`` or split by dots fall out of every bucket. Silence is
not a reading.

**Exempt, and why** — the whole list, the keys of ``EXEMPTIONS``; nothing else is:

* *code* — inline code spans and fenced blocks are literals (a path, a command,
  the producer's header format), not quotes of a measurement. "A zero-case class
  reports ``null``, never ``0.0000``" is true precisely because ``0.0000`` is not
  in the report. Digests and commit ids are published inside code spans.
  A fence closes only what it opened — a line of the same character, at least
  as long, carrying nothing else — so a three-backtick line inside a
  four-backtick block is a literal line, not a fence. A fence that never closes
  would turn the rest of the capsule into a literal, so it is a defect
  (``fence_defects``), never an exemption.
* *identifier* — a number glued to a name, directly or across a ``-`` or ``.``
  after a letter: ``GR-0.3``, ``T-12``, ``top-5``, ``BGE-M3``, ``sha256``,
  ``C.1a``, ``п.3``, ``7b``, ``3pl``. It names a thing; it states no value.
* *version* — two or more dots between parts of one or two digits, ``1.0.3``,
  ``2.11.0``: a schema or package version. A three-digit part (``1.234.567``)
  is a dot-grouped number, so it is unread, not a version.
* *date* — ``2026-09-09``.
* *phrase* — a number that is a claim about something other than the report:
  the plan's target, another arm's measurement, a precondition, a section
  number. Each is in ``NON_REPORT_PHRASES`` as the exact phrase it appears in,
  with its reason. Change a digit and the phrase stops matching, so the number
  falls back into the guard; an exemption cannot cover a wrong number in any
  other sentence, nor part of a longer number (``196 / 3 / 1: D2 measures``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

#: The numbers in a capsule that are claims about something other than its
#: report, as the exact phrase each appears in, with the reason it is not in the
#: JSON. `tests/test_capsule_prose.py` requires each to cover a phrase a capsule
#: actually carries and to stop covering it the moment a digit changes.
NON_REPORT_PHRASES: tuple[tuple[str, str], ...] = (
    ("§4 п.3–4", "a section number in plan_06_09_26.md"),
    ("±1 window", "the window shape the section-coherence arm replaces, not a count"),
    ("kw FULL vs 96 %", "the target plan_06_09_26.md:147 states, quoted verbatim"),
    ("the 96 % does not", "the same target, named as not being this measurement"),
    ("FULL is 96 in the", "the D2 arm's FULL, measured in another report"),
    ("96 / 3 / 1: D2 measures", "the D2 arm's FULL / PART / MISS, measured in another report"),
    ("window 2 / 3600 chars", "the D2 arm's expansion parameters"),
    ("≥ 15 new multi-hop", "GR-0.2's precondition — a requirement, not a result"),
)

CLAIM = "claim"
EXEMPT = "exempt"
UNREAD = "unread"

#: Every rule that may exempt a digit run, with its reason, in the order of the
#: module docstring's list. A run none of them covers is a claim or unread.
EXEMPTIONS: dict[str, str] = {
    "code": "a code span or fenced block is a literal, not a quote of a measurement",
    "identifier": "a number glued to a name names a thing and states no value",
    "version": "dotted parts of one or two digits are a schema or package version",
    "date": "an ISO date says when, not what was measured",
    "phrase": "a NON_REPORT_PHRASES phrase is a claim about something other than the report",
}


@dataclass(frozen=True)
class Run:
    """One number in the text and the bucket it landed in.

    ``start``/``end`` span its digits and separators; ``text`` is the number as
    written, a printed sign or a leading dot included; ``why`` is the
    ``EXEMPTIONS`` rule for ``EXEMPT``, what cannot be read for ``UNREAD``, and
    empty for ``CLAIM``.
    """

    start: int
    end: int
    text: str
    bucket: str
    why: str = ""


_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_ISO_DATE_RE = re.compile(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])")
#: A maximal run of digits with the points and separators inside it, and an
#: exponent when one follows that is not itself glued to a name.
_NUMBER_RE = re.compile(r"(?<![0-9])[0-9]+(?:[.,][0-9]+)*(?:[eE][-+−]?[0-9]+(?!\w))?")
_CLAIM_RE = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")
_VERSION_RE = re.compile(r"[0-9]{1,2}(?:\.[0-9]{1,2}){2,}")
_SCIENTIFIC_RE = re.compile(r".*[eE][-+−]?[0-9]+")
#: An opening fence: three or more backticks with no backtick after them (a
#: line like ```x``` is an inline code span), or three or more tildes.
_FENCE_OPEN_RE = re.compile(r"\s*(`{3,}(?=[^`]*$)|~{3,})")
_SIGNS = {"+": "+", "-": "-", "−": "-"}
_JOINERS = {"-", ".", "−"}


def _is_letter(char: str) -> bool:
    return char.isalpha() or char == "_"


def strip_code_spans(text: str) -> str:
    # A space, not nothing, so removing a span cannot glue a letter to a digit.
    return _CODE_SPAN_RE.sub(" ", text)


def _fenced(capsule: str) -> tuple[list[bool], int | None]:
    """Which lines are literal, and the line of a fence that never closes.

    A line is literal when it is a fence or sits inside a fenced block. A block
    closes only on a line of its opening fence's character, at least as long,
    with nothing else on it — not on the next line that merely starts with
    three backticks.
    """
    literal: list[bool] = []
    opened: tuple[str, int] | None = None  # the opening fence and its line number
    for number, line in enumerate(capsule.splitlines(), start=1):
        if opened is None:
            match = _FENCE_OPEN_RE.match(line)
            if match:
                opened = (match.group(1), number)
            literal.append(match is not None)
            continue
        literal.append(True)
        fence = line.strip()
        if len(fence) >= len(opened[0]) and set(fence) == {opened[0][0]}:
            opened = None
    return literal, opened[1] if opened else None


def fence_defects(capsule: str) -> list[str]:
    """An unclosed code fence, as a defect: the one way a literal could hide prose."""
    _, unclosed = _fenced(capsule)
    if unclosed is None:
        return []
    return [
        f"capsule ends inside a code fence: the fence opened on line {unclosed} never "
        "closes, so everything after it would be read as a literal"
    ]


def _require_closed_fences(capsule: str) -> None:
    unclosed = fence_defects(capsule)
    if unclosed:
        raise AssertionError(unclosed[0])


def prose_lines(capsule: str) -> list[str]:
    """The capsule's running prose: no table rows, no fenced blocks, no code spans."""
    _require_closed_fences(capsule)
    literal, _ = _fenced(capsule)
    return [
        strip_code_spans(line)
        for line, is_literal in zip(capsule.splitlines(), literal, strict=True)
        if not is_literal and not line.strip().startswith("|")
    ]


def capsule_tables(capsule: str) -> dict[str, list[list[str]]]:
    """Every markdown table in the capsule, keyed by its first header cell.

    Tables are found by their header, never by their width: T-13's first guard
    read only nine-cell rows and left three of four tables unpinned. Each value
    is the table's rows, header row first, alignment row dropped. A fenced block
    is skipped so that a literal is never read as a table.
    """
    _require_closed_fences(capsule)
    literal, _ = _fenced(capsule)
    tables: dict[str, list[list[str]]] = {}
    current: str | None = None
    for line, is_literal in zip(capsule.splitlines(), literal, strict=True):
        stripped = line.strip()
        if is_literal or not stripped.startswith("|"):
            current = None
            continue
        if set(stripped) <= set("|-: "):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if current is None:
            current = cells[0]
            if current in tables:
                raise AssertionError(
                    f"two capsule tables start with the header cell {current!r}; the "
                    "guard keys tables by that cell, so rename one of them"
                )
            tables[current] = [cells]
            continue
        tables[current].append(cells)
    return tables


def _digit_runs(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """The maximal runs of digit characters (any script) in ``text[start:end]``."""
    runs: list[tuple[int, int]] = []
    index = start
    while index < end:
        if text[index].isdigit():
            first = index
            while index < end and text[index].isdigit():
                index += 1
            runs.append((first, index))
        else:
            index += 1
    return runs


def _cuts_a_number(text: str, start: int, end: int) -> bool:
    """Whether ``text[start:end]`` would take part of a longer number with it."""
    if text[start : start + 1].isdigit():
        left = text[start - 1 : start] if start else ""
        if left.isdigit() or (left in {".", ","} and text[max(start - 2, 0) : start - 1].isdigit()):
            return True
    if text[end - 1 : end].isdigit():
        right = text[end : end + 1]
        if right.isdigit() or (right in {".", ","} and text[end + 1 : end + 2].isdigit()):
            return True
    return False


def _classify(text: str, start: int, end: int) -> Run:
    """The number ``text[start:end]`` in its bucket; the last line is ``UNREAD``."""
    body = text[start:end]
    before = text[start - 1] if start else ""
    before_that = text[start - 2] if start > 1 else ""
    after = text[end] if end < len(text) else ""
    if _is_letter(before) or _is_letter(after):
        return Run(start, end, body, EXEMPT, "identifier")  # glued: 7b, 3pl, sha256, BGE-M3
    if before in _JOINERS and _is_letter(before_that):
        return Run(start, end, body, EXEMPT, "identifier")  # joined: GR-0.3, T-12, C.1a, п.3
    if _VERSION_RE.fullmatch(body):
        return Run(start, end, body, EXEMPT, "version")  # 1.0.3, 2.11.0
    if before == ".":
        return Run(start, end, "." + body, UNREAD, "a leading-dot decimal")
    sign = _SIGNS.get(before, "") if not before_that.isalnum() else ""
    if _CLAIM_RE.fullmatch(body):
        return Run(start, end, sign + body, CLAIM)
    if _SCIENTIFIC_RE.fullmatch(body):
        return Run(start, end, sign + body, UNREAD, "scientific notation")
    return Run(start, end, sign + body, UNREAD, "separators that group no number")


def read_numbers(text: str, phrases: Iterable[tuple[str, str]] = NON_REPORT_PHRASES) -> list[Run]:
    """Every number in ``text`` with its bucket, in order; no digit is left out.

    Exempt regions (code spans, named phrases, dates) are blanked to spaces of
    the same length, so what surrounds a number is never changed by removing
    one; each digit run they cover is recorded under its rule. Every number left
    is classified by ``_classify``, and a final sweep reports any digit that no
    reading reached as ``UNREAD``.
    """
    runs: list[Run] = []
    masked = text

    def exempt(start: int, end: int, rule: str) -> None:
        nonlocal masked
        runs.extend(Run(a, b, text[a:b], EXEMPT, rule) for a, b in _digit_runs(text, start, end))
        masked = masked[:start] + " " * (end - start) + masked[end:]

    for found in _CODE_SPAN_RE.finditer(text):
        exempt(*found.span(), "code")
    for phrase, _reason in phrases:
        at = masked.find(phrase)
        while at >= 0:
            if not _cuts_a_number(masked, at, at + len(phrase)):
                exempt(at, at + len(phrase), "phrase")
            at = masked.find(phrase, at + 1)
    for found in _ISO_DATE_RE.finditer(masked):
        if not _cuts_a_number(masked, *found.span()):
            exempt(*found.span(), "date")
    for start, end in _digit_runs(masked, 0, len(masked)):
        if not masked[start:end].isascii():  # ٣, １２, 10⁴: read whole, as unread
            runs.append(Run(start, end, text[start:end], UNREAD, "a digit outside 0-9"))
            masked = masked[:start] + " " * (end - start) + masked[end:]
    runs.extend(_classify(masked, *found.span()) for found in _NUMBER_RE.finditer(masked))

    read = {index for run in runs for index in range(run.start, run.end)}
    unreached = "".join(char if index not in read else " " for index, char in enumerate(text))
    runs.extend(
        Run(start, end, text[start:end], UNREAD, "a digit no rule reads")
        for start, end in _digit_runs(unreached, 0, len(unreached))
    )
    return sorted(runs, key=lambda run: run.start)


def numeric_claims(text: str, phrases: Iterable[tuple[str, str]] = NON_REPORT_PHRASES) -> list[str]:
    """Every number in ``text`` that is a claim, as written, in order.

    ``phrases`` defaults to the named exemptions; the exemption test passes an
    empty tuple to show what each phrase would contribute without its exemption.
    """
    return [run.text for run in read_numbers(text, phrases) if run.bucket == CLAIM]


def _is_reported(claim: str, decimals: list[float], integers: set[int]) -> bool:
    sign = claim[0] if claim[0] in "+-" else ""
    body = claim[len(sign) :].replace(",", "")
    if "." in body:
        places = len(body.split(".", 1)[1])
        if sign:
            return any(f"{value:+.{places}f}" == claim for value in decimals)
        return any(f"{abs(value):.{places}f}" == body for value in decimals)
    if body != str(int(body)):
        return False  # zero-padded: 07 does not render the integer 7
    if sign:
        return int(sign + body) in integers
    return int(body) in {abs(value) for value in integers}


def _number_defects(text: str, decimals: list[float], integers: set[int]) -> list[tuple[str, str]]:
    """Each claim no report value renders to and each unread run, with why it fails."""
    defects: list[tuple[str, str]] = []
    for run in read_numbers(text):
        if run.bucket == UNREAD:
            defects.append((run.text, f"which the guard cannot read ({run.why})"))
        elif run.bucket == CLAIM and not _is_reported(run.text, decimals, integers):
            defects.append((run.text, "which the report does not carry"))
    return defects


def unreported_numbers(
    lines: Iterable[str], *, decimals: Iterable[float], integers: Iterable[int]
) -> list[str]:
    """The claims in ``lines`` no report value renders to, and every unread run, in order."""
    decimal_values = [float(value) for value in decimals]
    integer_values = {int(value) for value in integers}
    return [
        number
        for line in lines
        for number, _why in _number_defects(line, decimal_values, integer_values)
    ]


def table_defects(
    tables: dict[str, list[list[str]]], *, decimals: Iterable[float], integers: Iterable[int]
) -> list[str]:
    """Every number in every table cell, checked like prose — any table, any width."""
    decimal_values = [float(value) for value in decimals]
    integer_values = {int(value) for value in integers}
    return [
        f"table {key!r} row {index} cell {cell!r} quotes {number}, {why}"
        for key, rows in tables.items()
        for index, row in enumerate(rows)
        for cell in row
        for number, why in _number_defects(cell, decimal_values, integer_values)
    ]


def capsule_defects(
    capsule: str, *, decimals: Iterable[float], integers: Iterable[int]
) -> list[str]:
    """The whole contract over one capsule: its prose and every one of its tables."""
    unclosed = fence_defects(capsule)
    if unclosed:
        return unclosed  # no line after the stray fence can be trusted, so none passes
    decimal_values = [float(value) for value in decimals]
    integer_values = {int(value) for value in integers}
    prose = [
        f"prose quotes {number}, {why}"
        for line in prose_lines(capsule)
        for number, why in _number_defects(line, decimal_values, integer_values)
    ]
    return prose + table_defects(
        capsule_tables(capsule), decimals=decimal_values, integers=integer_values
    )


def row_defects(published: list[str], expected: list[str], where: str) -> list[str]:
    """A published table row against the row its report section renders."""
    if len(published) != len(expected):
        return [f"{where}: capsule row has {len(published)} cells, expected {len(expected)}"]
    return [
        f"{where}: capsule cell {index} is {cell!r}, report says {want!r}"
        for index, (cell, want) in enumerate(zip(published, expected, strict=True))
        if cell != want
    ]


def with_cell(rows: list[list[str]], row: int, column: int, value: str) -> list[list[str]]:
    """The same table with one cell changed, in memory; the capsule is untouched."""
    mutated = [list(cells) for cells in rows]
    assert mutated[row][column] != value, "the mutation has to change the cell it mutates"
    mutated[row][column] = value
    return mutated
