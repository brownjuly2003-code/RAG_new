"""GR-1a: section coherence as a narrowing arm over the pinned candidate pool.

`docs/specs/retrieval-buckets.md` requires a narrowing arm to be reported
against the arm it replaces, on the same pool and the same cases, with keyword
coverage beside context precision and recall. `plan_06_09_26.md` §4 п.3 defines
the arm itself: candidates are grouped by document and section (the heading
path), chunks from sections already represented in the top are promoted,
isolated neighbours are demoted, and the isolated ones below a threshold are
dropped rather than re-ranked.

These tests are the gate for the arm in `scripts/ab_context_precision.py`:

* the header parser agrees with the *producer* that wrote the headers in the
  pool — the metadata branch of `add_contextual_headers` before stage 1
  replaced the header (`docs/specs/stage1-fixes.md` row 5), copied below from
  commit 99cd15f — so the parser cannot drift into measuring itself;
* a header the producer did not write is **counted**, never silently treated as
  a sectionless chunk, and never dropped (a parse failure must not reject a
  candidate the reranker admitted);
* grouping joins two chunks of one section and keeps two same-named sections of
  different documents apart;
* the arm is a pure function of (pool, parameters);
* the regression this arm can cause — dropping a singleton section that holds
  the answer — happens only above the threshold, and the control cell
  (neighbourhood = top-k, threshold 0.0, no expansion) drops nothing and adds
  nothing, so keyword coverage cannot move at all;
* the numbers in `docs/evidence/gr1a-section-coherence.md` are the numbers in
  the committed `reports/gr/gr1a-section-coherence.json`, prose and every table
  included, under the capsule contract shared with T-12
  (`tests/capsule_prose.py`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts.ab_context_precision import (
    CONTEXT_HEADER_CLAMP,
    HEADER_PAGE_SEPARATOR,
    SECTION_COHERENCE_NEIGHBOURHOODS,
    SECTION_COHERENCE_THRESHOLDS,
    CoherenceParams,
    SectionRef,
    apply_section_coherence,
    build_section_coherence_report,
    group_candidates_by_section,
    header_is_clamped,
    parse_contextual_header,
    write_bucket_report,
)
from tests.capsule_prose import (
    NON_REPORT_PHRASES,
    capsule_defects,
    capsule_tables,
    numeric_claims,
    prose_lines,
    row_defects,
    table_defects,
    unreported_numbers,
    with_cell,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT = PROJECT_ROOT / "reports" / "gr" / "gr1a-section-coherence.json"
CAPSULE = PROJECT_ROOT / "docs" / "evidence" / "gr1a-section-coherence.md"
BASELINE_REPORT = PROJECT_ROOT / "reports" / "gr" / "gr0-bucket-baseline.json"
POOL = PROJECT_ROOT / ".tmp" / "ab_candidates_phase2_C.json"

FAKE_COMMIT = "0" * 40


# ---------------------------------------------------------------------------
# Fixtures built by the production producer, not by a hand-written string
# ---------------------------------------------------------------------------


def _produced(body: str, source: str, *headings: str, page: str = "") -> str:
    """One chunk as the ingest wrote it when the pool was taken, header included.

    Stage 1 replaced the live header with a language-free one; the pool and the arm keep
    the old form. This is the old producer's metadata branch, as it stood at 99cd15f in
    ``vectordb/_base_manager.py::add_contextual_headers``.
    """
    header = f"Из документа {source}"
    heading_path = [str(heading).strip() for heading in headings if heading]
    if heading_path:
        header += ", раздел: " + " › ".join(heading_path)
    if page:
        header += f", стр. {page}"
    if len(header) > 200:
        header = header[:200]
    return f"[Контекст: {header}]\n{body}"


# ---------------------------------------------------------------------------
# The parser agrees with the producer
# ---------------------------------------------------------------------------


def test_the_parser_recovers_what_the_producer_wrote() -> None:
    text = _produced(
        "## Вопросы и ответы  \n### Вопрос 1.",
        "07_faq_probation.md",
        "FAQ по испытательному сроку",
        "Вопросы и ответы",
        "Вопрос 1. Какие данные нужны?",
    )

    ref = parse_contextual_header(text)

    assert ref == SectionRef(
        document="07_faq_probation.md",
        heading_path=(
            "FAQ по испытательному сроку",
            "Вопросы и ответы",
            "Вопрос 1. Какие данные нужны?",
        ),
    )


def test_the_parser_handles_the_producers_optional_parts() -> None:
    """A chunk with no headings, and one with the producer's page marker."""
    headingless = parse_contextual_header(_produced("body", "99_plain.md"))
    assert headingless == SectionRef(document="99_plain.md", heading_path=())

    paged = parse_contextual_header(
        _produced("body", "12_scan.md", "Раздел A", "Раздел B", page="7")
    )
    assert paged == SectionRef(document="12_scan.md", heading_path=("Раздел A", "Раздел B"))


def test_a_heading_that_contains_the_page_marker_keeps_its_full_heading_path() -> None:
    """``, стр. `` inside a heading is not the producer's page marker.

    The producer appends the marker last and only when the chunk's metadata
    carries a page (``_produced`` above: ``if page:``), so a heading
    that contains the separator itself has to survive parsing. Stripping from the
    right on the separator alone loses it: the tail has to be something that can
    actually *be* a page number.
    """
    inner = parse_contextual_header(
        _produced("body", "22_annex.md", "Приложение 2, стр. 12", "Обязательные поля")
    )
    assert inner == SectionRef(
        document="22_annex.md",
        heading_path=("Приложение 2, стр. 12", "Обязательные поля"),
    )

    trailing = parse_contextual_header(
        _produced("body", "22_annex.md", "Обязательные поля", "Приложение 2, стр. 12 и далее")
    )
    assert trailing == SectionRef(
        document="22_annex.md",
        heading_path=("Обязательные поля", "Приложение 2, стр. 12 и далее"),
    )

    # The false-reject control: a header the producer *did* write with page
    # metadata still loses exactly that marker and nothing else.
    paged = parse_contextual_header(_produced("body", "12_scan.md", "Обязательные поля", page="7"))
    assert paged == SectionRef(document="12_scan.md", heading_path=("Обязательные поля",))

    # And the boundary the header format itself cannot resolve, recorded rather
    # than claimed away: a *last* heading ending in the separator plus digits is
    # byte-identical to a heading path the producer wrote with page metadata, so
    # the page reading wins and nothing in the header can tell the two apart.
    ambiguous = _produced("body", "22_annex.md", "Приложение 2, стр. 12")
    assert ambiguous == _produced("body", "22_annex.md", "Приложение 2", page="12")
    assert parse_contextual_header(ambiguous) == SectionRef(
        document="22_annex.md", heading_path=("Приложение 2",)
    )


@pytest.mark.skipif(not POOL.is_file(), reason="the pinned pool is gitignored")
def test_no_pool_candidate_carries_the_page_marker_at_all() -> None:
    """The control that says the page-marker rule cannot move a published number.

    Requiring a digit tail before stripping is a change to parsing, so it needs
    the same false-reject control as every other tightening in this slice: the
    separator occurs in none of the pool's headers, so every section key of the
    published grid is the key it was before the rule was narrowed.
    """
    rows = json.loads(POOL.read_text(encoding="utf-8"))
    carriers = [
        f"{row['case_id']}:{text.split(chr(10), 1)[0][:80]}"
        for row in rows
        for text in row["cands"]
        if HEADER_PAGE_SEPARATOR in text.split("\n", 1)[0]
    ]

    assert carriers == [], (
        f"{len(carriers)} pool headers carry the page separator, so the digit-tail "
        "rule can change a section key; re-run the report before trusting the grid"
    )


@pytest.mark.parametrize(
    "text",
    [
        "no header at all, just chunk body",
        "[Контекст: сгенерированный LLM заголовок без структуры]\nbody",
        "[Контекст: Из документа a.md, раздел: A › B]",  # header with no body line
        "",
    ],
)
def test_a_header_the_producer_did_not_write_is_not_parsed(text: str) -> None:
    assert parse_contextual_header(text) is None


def test_a_malformed_header_is_counted_and_never_swallowed() -> None:
    """Unparseable candidates are reported, kept, and are not "sectionless".

    A chunk whose header cannot be read is not known to be isolated, so the arm
    may not demote it into the drop set; treating it as a sectionless chunk
    would also merge every such chunk into one bogus group.
    """
    candidates = [
        _produced("a", "doc_a.md", "Раздел", "Первый"),
        "IRRELEVANT chunk with no contextual header",
        _produced("b", "doc_a.md", "Раздел", "Второй"),
        _produced("c", "doc_b.md"),  # genuinely sectionless: no headings
    ]

    groups, unparsed = group_candidates_by_section(candidates)

    assert unparsed == [1]
    assert SectionRef("doc_b.md", ()) in groups, "a headingless chunk still has a group"
    assert all(1 not in ranks for ranks in groups.values())

    outcome = apply_section_coherence(
        candidates,
        CoherenceParams(neighbourhood=4, singleton_threshold=1.0, top_k=4),
    )
    assert outcome.unparsed == 1
    assert candidates[1] in outcome.texts, "an unreadable header must not be dropped"


def test_grouping_joins_one_section_and_separates_same_named_sections() -> None:
    candidates = [
        _produced("a", "doc_a.md", "Обязательные поля"),
        _produced("b", "doc_b.md", "Обязательные поля"),
        _produced("c", "doc_a.md", "Обязательные поля"),
    ]

    groups, unparsed = group_candidates_by_section(candidates)

    assert unparsed == []
    assert groups[SectionRef("doc_a.md", ("Обязательные поля",))] == [0, 2]
    assert groups[SectionRef("doc_b.md", ("Обязательные поля",))] == [1]


def test_a_clamped_header_is_recognised_and_still_admitted() -> None:
    """The producer's 200-character clamp cuts the heading path, not the wrapper.

    Such a header parses — so it is not 'unparsed' — but its section key is a
    truncated path, and two sections of one document sharing a long prefix then
    group as one. The arm cannot repair that from the pool; it counts it.
    """
    clamped = _produced("body", "doc_long.md", "Р" * 300)
    ordinary = _produced("body", "doc_short.md", "Обязательные поля")

    assert header_is_clamped(clamped)
    assert not header_is_clamped(ordinary), "the control: a normal header is not clamped"
    assert len(clamped.split("\n", 1)[0]) == len("[Контекст: ") + CONTEXT_HEADER_CLAMP + len("]")

    # It parses, and the arm treats it like any other candidate — recognising the
    # clamp must not become a reason to reject a candidate the reranker admitted.
    assert parse_contextual_header(clamped) is not None
    outcome = apply_section_coherence(
        [clamped, ordinary], CoherenceParams(neighbourhood=2, singleton_threshold=0.0, top_k=2)
    )
    assert outcome.unparsed == 0
    assert clamped in outcome.texts


def test_two_sections_sharing_a_clamped_prefix_group_as_one() -> None:
    """The failure the count makes visible, written down rather than assumed away."""
    prefix = "Р" * 300
    first = _produced("a", "doc_long.md", prefix + " первый")
    second = _produced("b", "doc_long.md", prefix + " второй")

    groups, unparsed = group_candidates_by_section([first, second])

    assert unparsed == []
    assert header_is_clamped(first) and header_is_clamped(second)
    assert len(groups) == 1, (
        "two distinct sections merged into one group because the producer clamped "
        "both headings to the same 200 characters; this is why 'clamped' is a "
        "reported count and not an assumption"
    )


# ---------------------------------------------------------------------------
# The arm itself
# ---------------------------------------------------------------------------


def _pool_case() -> list[str]:
    """Ten candidates: one supported section, the rest isolated neighbours."""
    return [
        _produced("ноль", "doc_a.md", "Правила", "Первый"),
        _produced("один", "doc_b.md", "Поля", "Обязательные"),
        _produced("два", "doc_b.md", "Поля", "Обязательные"),
        *[_produced(f"шум {i}", f"doc_{i}.md", "Прочее", f"Секция {i}") for i in range(3, 10)],
    ]


def test_a_supported_section_is_promoted_over_isolated_neighbours() -> None:
    outcome = apply_section_coherence(
        _pool_case(),
        CoherenceParams(neighbourhood=10, singleton_threshold=0.0, top_k=3),
    )

    refs = [parse_contextual_header(text) for text in outcome.texts]
    assert refs[0] == SectionRef("doc_b.md", ("Поля", "Обязательные"))
    assert refs[1] == SectionRef("doc_b.md", ("Поля", "Обязательные"))
    # The rank-0 singleton is demoted below the supported pair but not dropped
    # at threshold 0.0.
    assert refs[2] == SectionRef("doc_a.md", ("Правила", "Первый"))
    assert outcome.promoted == 2
    assert outcome.dropped == 0


def test_the_arm_is_a_pure_function_of_the_pool_and_the_parameters() -> None:
    candidates = _pool_case()
    params = CoherenceParams(neighbourhood=10, singleton_threshold=0.3, top_k=5)

    first = apply_section_coherence(candidates, params)
    second = apply_section_coherence(list(candidates), CoherenceParams(**vars(params)))

    assert first == second
    assert candidates == _pool_case(), "the arm must not mutate the pool it reads"


def test_the_arm_always_returns_at_least_one_candidate() -> None:
    """The strongest section is normalised to 1.0, so it survives any threshold."""
    for threshold in (*SECTION_COHERENCE_THRESHOLDS, 1.0):
        outcome = apply_section_coherence(
            _pool_case(),
            CoherenceParams(neighbourhood=10, singleton_threshold=threshold, top_k=5),
        )
        assert outcome.texts, f"threshold {threshold} emptied the context"


def test_a_singleton_answer_section_is_dropped_only_above_the_threshold() -> None:
    """The regression this arm can cause, isolated in one test.

    ``doc_answer.md`` holds the only chunk that carries the answer and no other
    candidate points at its section, so the arm sees it as an isolated
    neighbour. Below the threshold it survives and the case still reads FULL;
    above it, the arm drops the answer — a precision gain bought by losing the
    case, which is exactly what the grid has to make visible.
    """
    answer = _produced("срок хранения груза — трое суток", "doc_answer.md", "Сроки")
    supported = [
        _produced("общие сведения", "doc_bulk.md", "Прочее", "Раздел"),
        _produced("ещё сведения", "doc_bulk.md", "Прочее", "Раздел"),
        _produced("и ещё", "doc_bulk.md", "Прочее", "Раздел"),
    ]
    candidates = [*supported, answer]

    # Section scores: doc_bulk 1/1 + 1/2 + 1/3 = 1.8333, doc_answer 1/4 = 0.25,
    # so the answer's section strength is 0.25 / 1.8333 = 0.1364.
    kept = apply_section_coherence(
        candidates, CoherenceParams(neighbourhood=4, singleton_threshold=0.10, top_k=5)
    )
    assert answer in kept.texts
    assert kept.dropped == 0

    lost = apply_section_coherence(
        candidates, CoherenceParams(neighbourhood=4, singleton_threshold=0.20, top_k=5)
    )
    assert answer not in lost.texts
    assert lost.dropped == 1


def test_the_control_cell_drops_nothing_and_adds_nothing(tmp_path: Path) -> None:
    """FALSE-REJECT CONTROL: the arm must still accept every baseline candidate.

    With the neighbourhood equal to the top-k, threshold 0.0 and expansion off,
    the arm may reorder but may not remove a candidate the reranker admitted or
    add text the baseline did not carry — the set of texts is the baseline's.

    That set equality does **not** by itself keep keyword coverage fixed:
    `_truncate_contexts` spends one shared character budget in order, so once a
    case's selected chunks exceed the budget, re-ordering changes which text
    survives and FULL / PART / MISS can move without a single candidate being
    rejected. What holds coverage fixed is the measured condition that no case
    reaches that budget, asserted here for the fixture and, over the pool the
    published numbers come from, through the reported
    ``cases_at_the_truncation_budget`` diagnostic.
    """
    candidates = _pool_case()
    params = CoherenceParams(
        neighbourhood=5, singleton_threshold=0.0, top_k=5, expand_to_section=False
    )

    outcome = apply_section_coherence(candidates, params)

    assert sorted(outcome.texts) == sorted(candidates[:5])
    assert outcome.dropped == 0
    assert outcome.expanded == 0
    assert sum(len(text) for text in outcome.texts) <= params.context_chars, (
        "this fixture reaches the shared truncation budget, so the set equality "
        "above no longer implies unchanged keyword coverage"
    )


def test_expansion_reaches_the_section_boundary_only_when_the_pool_carries_it() -> None:
    """Section expansion joins the sibling chunk the pool already holds."""
    sibling = _produced("вторая половина секции", "doc_b.md", "Поля", "Обязательные")
    candidates = [
        _produced("ноль", "doc_a.md", "Правила", "Первый"),
        _produced("первая половина секции", "doc_b.md", "Поля", "Обязательные"),
        *[_produced(f"шум {i}", f"doc_{i}.md", "Прочее", f"Секция {i}") for i in range(2, 6)],
        sibling,  # rank 6: outside the neighbourhood, inside the pool
    ]
    params = CoherenceParams(
        neighbourhood=6, singleton_threshold=0.0, top_k=2, expand_to_section=True
    )

    outcome = apply_section_coherence(candidates, params)

    joined = "\n".join(outcome.texts)
    assert "вторая половина секции" in joined, "the section boundary was not reached"
    assert outcome.expanded == 1
    # doc_a's section has no other chunk anywhere in the pool: not expandable.
    assert outcome.not_expandable == 1
    # Expansion strips the sibling's own header rather than repeating it.
    assert joined.count("[Контекст: Из документа doc_b.md") == 1


# ---------------------------------------------------------------------------
# The parser against the real pool (the artifact the numbers come from)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not POOL.is_file(), reason="the pinned pool is gitignored")
def test_the_parser_agrees_with_the_pool_on_every_candidate() -> None:
    """Control over the real artifact: the parsed document is the pool's own."""
    rows = json.loads(POOL.read_text(encoding="utf-8"))
    unparsed: list[str] = []
    disagreed: list[str] = []
    for row in rows:
        for text, source in zip(row["cands"], row["cand_sources"], strict=True):
            ref = parse_contextual_header(text)
            if ref is None:
                unparsed.append(f"{row['case_id']}:{text[:60]}")
            elif ref.document != source:
                disagreed.append(f"{row['case_id']}:{ref.document}!={source}")

    assert not unparsed, f"{len(unparsed)} pool candidates the parser cannot read"
    assert not disagreed, f"parser and pool disagree on the document: {disagreed[:5]}"


# ---------------------------------------------------------------------------
# The report over a synthetic pool
# ---------------------------------------------------------------------------


def _fixture(root: Path) -> dict[str, Path]:
    """A four-case dataset + pool + sidecar, headers written by the producer."""
    from tests.test_gr_bucket_baseline import _write_fixture

    paths = _write_fixture(root, top_k=2)
    pool = json.loads(paths["pool"].read_text(encoding="utf-8"))
    for index, row in enumerate(pool):
        document = f"doc_{index}.md"
        row["cands"] = [
            _produced(text, document, "Раздел", f"Пункт {position}")
            for position, text in enumerate(row["cands"])
        ]
        row["rerank_k"] = 2
    paths["pool"].write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8", newline="\n")
    return paths


def _report_for(paths: dict[str, Path], **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "pool_path": paths["pool"],
        "dataset_path": paths["dataset"],
        "sidecar_path": paths["sidecar"],
        "label_manifest_path": paths["label_manifest"],
        "corpus_manifest_path": paths["corpus_manifest"],
        "expected_cases": 4,
        "top_k": 2,
        "neighbourhoods": (2,),
        "thresholds": (0.0, 0.5),
        "code_commit": FAKE_COMMIT,
    }
    kwargs.update(overrides)
    return build_section_coherence_report(**kwargs)


def test_the_report_carries_the_whole_grid_and_the_baseline_beside_it(
    tmp_path: Path,
) -> None:
    report = _report_for(_fixture(tmp_path))

    assert report["baseline"]["aggregate"]["num_cases"] == 4
    # 1 neighbourhood x 2 thresholds x expansion off/on
    assert len(report["grid"]) == 4
    for cell in report["grid"]:
        assert set(cell["parameters"]) >= {
            "neighbourhood",
            "singleton_threshold",
            "top_k",
            "expand_to_section",
            "context_chars",
        }
        assert cell["aggregate"]["num_cases"] == 4
        assert len(cell["buckets"]) == 4
        for key in ("FULL", "PART", "MISS"):
            assert isinstance(cell["aggregate"][key], int)
        assert isinstance(cell["keyword_regressions"], list)


def test_the_control_cell_of_the_report_matches_the_baseline_coverage(
    tmp_path: Path,
) -> None:
    """The published grid contains a cell that provably rejects nothing."""
    report = _report_for(_fixture(tmp_path))
    control = next(cell for cell in report["grid"] if cell["is_control"])
    baseline = report["baseline"]["aggregate"]

    assert control["parameters"]["singleton_threshold"] == 0.0
    assert control["parameters"]["expand_to_section"] is False
    assert control["parameters"]["neighbourhood"] == control["parameters"]["top_k"]
    for key in ("FULL", "PART", "MISS", "context_recall"):
        assert control["aggregate"][key] == baseline[key], key
    assert control["keyword_regressions"] == []
    # The condition that condition rests on: the shared truncation budget is
    # spent in order, so equality of the *set* of texts only implies equality of
    # coverage while no case reaches the budget.
    assert control["diagnostics"]["cases_at_the_truncation_budget"] == 0


def test_a_grid_for_any_top_k_still_carries_a_control_cell(tmp_path: Path) -> None:
    """The control cell is derived from top_k, not assumed to be in the pair.

    `docs/specs/retrieval-buckets.md` requires a published control cell. With the
    neighbourhood grid fixed at {5, 10}, any other `--top-k` produced a grid in
    which no cell had `neighbourhood == top_k` — the scenario was then silently
    unsatisfied rather than failing.
    """
    report = _report_for(_fixture(tmp_path), top_k=1, neighbourhoods=(2,))
    controls = [cell for cell in report["grid"] if cell["is_control"]]

    assert len(controls) == 1, "a published grid without exactly one control cell"
    assert controls[0]["parameters"]["neighbourhood"] == 1
    assert controls[0]["parameters"]["top_k"] == 1
    assert sorted({cell["parameters"]["neighbourhood"] for cell in report["grid"]}) == [1, 2]
    assert report["provenance"]["config"]["neighbourhoods"] == [1, 2]
    # …and the derived cell is a real control: it rejects nothing at k = 1.
    baseline = report["baseline"]["aggregate"]
    for key in ("FULL", "PART", "MISS", "context_recall"):
        assert controls[0]["aggregate"][key] == baseline[key], key


def test_a_grid_that_cannot_hold_a_control_cell_is_refused_loudly(tmp_path: Path) -> None:
    """A threshold grid with no 0.0 cell cannot prove the arm rejects nothing."""
    with pytest.raises(ValueError, match="control cell"):
        _report_for(_fixture(tmp_path), thresholds=(0.1, 0.5))


def test_the_declared_grid_is_unchanged_by_the_control_derivation() -> None:
    """FALSE-REJECT CONTROL: the published parameters are still accepted as-is.

    Deriving a neighbourhood from `top_k` must not alter the declared grid the
    committed report was produced with — with top_k 5 and neighbourhoods 5 and
    10, the derived value is already there.
    """
    report = _committed()

    assert report["provenance"]["config"]["neighbourhoods"] == sorted(
        SECTION_COHERENCE_NEIGHBOURHOODS
    )
    assert report["provenance"]["config"]["thresholds"] == sorted(SECTION_COHERENCE_THRESHOLDS)
    assert (
        len(report["grid"])
        == len(SECTION_COHERENCE_NEIGHBOURHOODS) * len(SECTION_COHERENCE_THRESHOLDS) * 2
    )


def test_a_case_that_reaches_the_truncation_budget_is_counted(tmp_path: Path) -> None:
    """The budget diagnostic is not vacuous: shrink the budget and it counts.

    Proving the guard both ways — at the published 6000 characters no fixture
    case reaches the budget and the count is 0; at a budget small enough to bite,
    the same cases are counted, so a pool where re-ordering could move keyword
    coverage cannot pass unnoticed.
    """
    paths = _fixture(tmp_path)

    roomy = _report_for(paths)
    assert all(cell["diagnostics"]["cases_at_the_truncation_budget"] == 0 for cell in roomy["grid"])

    cramped = _report_for(paths, context_chars=40)
    assert any(
        cell["diagnostics"]["cases_at_the_truncation_budget"] > 0 for cell in cramped["grid"]
    )


def test_only_the_control_and_the_headline_carry_a_per_case_table(
    tmp_path: Path,
) -> None:
    """The per-case detail every cell keeps is its regression list, not 100 rows."""
    report = _report_for(_fixture(tmp_path))
    headline = report["headline"]["parameters"]

    for cell in report["grid"]:
        audited = cell["is_control"] or cell["parameters"] == headline
        assert ("per_case" in cell) is audited, cell["parameters"]
        assert "keyword_regressions" in cell


def test_the_naive_top_k_reference_reproduces_the_baseline_at_its_own_k(
    tmp_path: Path,
) -> None:
    """The arm is measured against fixed truncation as well as against the baseline.

    The reference is only trustworthy if its last row *is* the baseline: same
    pool, same cases, same metric path, k equal to the published top-k.
    """
    report = _report_for(_fixture(tmp_path))
    rows = report["naive_top_k"]["rows"]

    assert [row["top_k"] for row in rows] == [1, 2]
    assert rows[-1]["aggregate"] == report["baseline"]["aggregate"]


def test_the_committed_naive_reference_reproduces_the_committed_baseline() -> None:
    report = _committed()
    rows = report["naive_top_k"]["rows"]

    assert [row["top_k"] for row in rows] == [1, 2, 3, 4, 5]
    assert rows[-1]["aggregate"] == report["baseline"]["aggregate"]


def test_two_runs_over_the_same_inputs_produce_identical_json(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    first = write_bucket_report(_report_for(paths), tmp_path / "out" / "a.json")
    second = write_bucket_report(_report_for(paths), tmp_path / "out" / "b.json")

    assert first.read_bytes() == second.read_bytes()
    body = first.read_text(encoding="utf-8")
    assert "created_at" not in body
    assert "timestamp" not in body


def test_the_report_counts_unreadable_headers_rather_than_hiding_them(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    pool = json.loads(paths["pool"].read_text(encoding="utf-8"))
    pool[0]["cands"][1] = "a candidate with no contextual header at all"
    paths["pool"].write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8", newline="\n")

    report = _report_for(paths)

    assert report["header_parse"]["unparsed"] == 1
    assert report["header_parse"]["candidates"] == 8
    assert report["header_parse"]["sectionless"] == 0
    assert report["header_parse"]["unparsed_cases"] == ["syn-one"]


def test_the_report_counts_headers_the_producer_clamped(tmp_path: Path) -> None:
    """A clamped header is a truncated section key, and the report says how many.

    It parses, so it is not 'unparsed'; it is not sectionless either. Nothing
    about it is visible in the section key, which is the whole reason it has to
    be counted: two sections sharing a long prefix would group as one.
    """
    paths = _fixture(tmp_path)
    pool = json.loads(paths["pool"].read_text(encoding="utf-8"))
    pool[0]["cands"][1] = _produced("body", "doc_long.md", "Р" * 300)
    paths["pool"].write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8", newline="\n")

    report = _report_for(paths)

    assert report["header_parse"]["clamped"] == 1
    assert report["header_parse"]["clamp"] == CONTEXT_HEADER_CLAMP
    # The false-reject control: counting it changed no admission decision.
    assert report["header_parse"]["unparsed"] == 0
    assert report["header_parse"]["candidates"] == 8


# ---------------------------------------------------------------------------
# The committed artifact, and the prose over it
# ---------------------------------------------------------------------------


def _committed() -> dict[str, Any]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_committed_baseline_block_is_the_gr03_baseline() -> None:
    """The arm is measured against the published ruler, not a private copy."""
    published = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    mine = _committed()["baseline"]

    assert mine["aggregate"] == published["aggregate"]
    assert mine["buckets"] == published["buckets"]
    assert _committed()["provenance"]["pool_sha256"] == published["provenance"]["pool_sha256"]
    assert (
        _committed()["provenance"]["dataset_sha256"] == (published["provenance"]["dataset_sha256"])
    )


def test_the_committed_grid_is_the_whole_declared_grid() -> None:
    report = _committed()
    cells = report["grid"]

    expected = len(SECTION_COHERENCE_NEIGHBOURHOODS) * len(SECTION_COHERENCE_THRESHOLDS) * 2
    assert len(cells) == expected, "the published grid is not the declared grid"
    assert sorted({cell["parameters"]["singleton_threshold"] for cell in cells}) == sorted(
        SECTION_COHERENCE_THRESHOLDS
    )
    assert sorted({cell["parameters"]["neighbourhood"] for cell in cells}) == sorted(
        SECTION_COHERENCE_NEIGHBOURHOODS
    )
    assert sum(1 for cell in cells if cell["is_control"]) == 1
    # Both movements travel together in every cell, as the spec requires.
    for cell in cells:
        for key in ("context_precision", "context_recall", "FULL", "PART", "MISS"):
            assert key in cell["aggregate"]


def test_the_committed_control_cell_did_not_reject_a_baseline_candidate() -> None:
    report = _committed()
    control = next(cell for cell in report["grid"] if cell["is_control"])
    baseline = report["baseline"]["aggregate"]

    for key in ("FULL", "PART", "MISS", "context_recall"):
        assert control["aggregate"][key] == baseline[key], key
    assert control["keyword_regressions"] == []
    # Why that equality is a false-reject control and not a coincidence of
    # ordering: `_truncate_contexts` spends one shared budget in order, so on a
    # pool where a case reached it the control cell could move coverage by
    # re-ordering alone. On this pool no cell has such a case, and the assertion
    # is over the whole grid so a future pool fails here rather than silently
    # invalidating the reasoning.
    for cell in report["grid"]:
        assert cell["diagnostics"]["cases_at_the_truncation_budget"] == 0, cell["parameters"]


def test_the_committed_headline_follows_the_stated_selection_rule() -> None:
    """The headline is a rule applied to the grid, not the luckiest cell."""
    report = _committed()
    baseline = report["baseline"]["aggregate"]
    qualifying = [
        cell
        for cell in report["grid"]
        if cell["aggregate"]["FULL"] >= baseline["FULL"]
        and cell["aggregate"]["MISS"] <= baseline["MISS"]
    ]
    headline = report["headline"]

    assert "selection_rule" in headline
    if not qualifying:
        assert headline["parameters"] is None
        return
    best = max(qualifying, key=lambda cell: cell["aggregate"]["context_precision"])
    assert headline["parameters"] == best["parameters"]


def test_the_capsule_names_the_base_it_compares_against() -> None:
    """The plan's 96 % FULL is not the measurement on this pool, and says so."""
    capsule = CAPSULE.read_text(encoding="utf-8")
    baseline = _committed()["baseline"]["aggregate"]

    assert "96" in capsule, "the capsule must name the target the plan states"
    assert "plan_06_09_26.md" in capsule
    assert f"{baseline['FULL']} / {baseline['PART']} / {baseline['MISS']}" in capsule
    assert "gr0-bucket-baseline" in capsule


def _capsule() -> str:
    return CAPSULE.read_text(encoding="utf-8")


def _reported_metric_values(report: dict[str, Any]) -> list[float]:
    """Every decimal value the report carries, in the roles the capsule quotes.

    Metrics per class and in aggregate, the signed deltas against the baseline
    (the grid prints their sign; an unsigned quote in prose matches their
    magnitude), the mean document count of a cell and the swept thresholds. A
    decimal in the capsule has to be one of these; anything else is a number
    the report does not support.
    """
    values: list[float] = []
    rows = [
        *report["baseline"]["buckets"],
        report["baseline"]["aggregate"],
    ]
    for cell in report["grid"]:
        rows.extend(cell["buckets"])
        rows.append(cell["aggregate"])
    rows.extend(row["aggregate"] for row in report["naive_top_k"]["rows"])
    for row in rows:
        for key in ("context_precision", "context_recall"):
            value = row.get(key)
            if value is not None:
                values.append(float(value))
    for cell in report["grid"]:
        for key in ("context_precision", "context_recall"):
            delta = cell["delta"][key]
            if delta is not None:
                values.append(float(delta))
        values.append(float(cell["diagnostics"]["mean_docs"]))
        values.append(float(cell["parameters"]["singleton_threshold"]))
    values.extend(float(row["mean_docs"]) for row in report["naive_top_k"]["rows"])
    return values


def test_the_capsule_prose_quotes_only_numbers_that_are_in_the_report() -> None:
    """Every number in the narrative is a value the report carries.

    Decimals at any precision, and integers: the first attempt at this capsule
    shipped "11 of the 494 selected chunks … the other 483 had none" against
    diagnostics of 394 and 383 — an off-by-100 in running prose, invisible to a
    guard that only matched ``\\d\\.\\d{1,4}``. A count in the narrative is a
    claim like a metric, checked under the contract shared with T-12 in
    `tests/capsule_prose.py`, and the report carries the diagnostics that make
    the checkable version writable.
    """
    report = _committed()
    lines = prose_lines(_capsule())

    unreported = unreported_numbers(
        lines, decimals=_reported_metric_values(report), integers=_reported_integer_values(report)
    )
    assert not unreported, (
        f"docs/evidence/gr1a-section-coherence.md quotes {unreported} in its prose, "
        "which reports/gr/gr1a-section-coherence.json does not carry. Quote a report "
        "field, or — if the number is a claim about something else — add its exact "
        "phrase with the reason to NON_REPORT_PHRASES in tests/capsule_prose.py."
    )
    quoted = [claim for line in lines for claim in numeric_claims(line)]
    metrics = [claim for claim in quoted if "." in claim]
    assert len(metrics) >= 4 and len(quoted) - len(metrics) >= 10, (
        "the capsule no longer quotes metrics and counts in its prose; the narrative "
        "is then unpinned and this test would pass vacuously"
    )


def test_a_wrong_prose_quote_fails_however_few_decimals_it_is_written_to() -> None:
    """The guard is proven by mutating a prose number, on an in-memory copy.

    Including the hole T-12's first pattern left, which this capsule actually
    exercises: "loses precision**, 0.5051 against 0.5067." ends a sentence, and a
    wrong value in that position matched nothing under T-12's ``(?![\\d.])``.
    """
    report = _committed()
    decimals = _reported_metric_values(report)
    integers = _reported_integer_values(report)
    capsule = _capsule()

    def prose_defects(text: str) -> list[str]:
        return unreported_numbers(prose_lines(text), decimals=decimals, integers=integers)

    anchor = f"{report['baseline']['aggregate']['context_precision']:.4f}"
    occurrences = sum(line.count(anchor) for line in prose_lines(capsule))
    assert occurrences, (
        f"this test mutates the baseline precision quote {anchor}; the capsule "
        "no longer carries it, so re-anchor the mutation before trusting it"
    )
    assert prose_defects(capsule) == []
    assert prose_defects(capsule.replace(anchor, "0.6412")) == ["0.6412"] * occurrences
    assert prose_defects(capsule.replace(anchor, anchor[: len(anchor) - 1])) == []

    # The sentence-final quote, mutated where the capsule itself puts it.
    final = f"against {anchor}."
    assert final in capsule, "the capsule no longer ends a sentence on a metric; re-anchor"
    assert prose_defects(capsule.replace(final, "against 0.6412.")) == ["0.6412"]
    # …while a stream id or a version string ending a sentence is still not a claim.
    assert prose_defects(f"{capsule}\nthis follows GR-0.2.\nthe schema is 1.0.3.\n") == []


def _reported_integer_values(report: dict[str, Any]) -> set[int]:
    """Every integer the report carries, in the roles the capsule quotes.

    Keyword coverage and case counts, the parse census, the per-cell diagnostics
    (``docs_selected``, ``expanded``, ``not_expandable``, ``dropped``,
    ``cases_with_all_singleton_sections`` …), the swept parameters, the length of
    each cell's regression list, the corpus file count and the pool size in
    bytes. An integer in the capsule has to be one of these.
    """
    values: set[int] = set()
    header = report["header_parse"]
    values.update(
        int(header[key]) for key in ("candidates", "unparsed", "sectionless", "clamped", "clamp")
    )
    values.add(int(report["labels"]["approved"]))
    values.add(int(report["headline"]["qualifying_cells"]))
    values.add(int(report["provenance"]["corpus"]["file_count"]))
    values.add(int(report["provenance"]["pool_bytes"]))
    # The configuration the provenance table prints: the swept parameters are
    # numbers the report carries, and the capsule quotes them there.
    config = report["provenance"]["config"]
    values.add(int(config["top_k"]))
    values.add(int(config["context_chars"]))
    values.update(int(value) for value in config["neighbourhoods"])

    rows: list[dict[str, Any]] = [*report["baseline"]["buckets"], report["baseline"]["aggregate"]]
    for cell in report["grid"]:
        rows.extend(cell["buckets"])
        rows.append(cell["aggregate"])
        values.update(
            int(value) for value in cell["diagnostics"].values() if isinstance(value, int)
        )
        values.add(int(cell["parameters"]["neighbourhood"]))
        values.add(int(cell["parameters"]["top_k"]))
        values.add(len(cell["keyword_regressions"]))
        values.update(abs(int(cell["delta"][key])) for key in ("FULL", "PART", "MISS"))
    for naive in report["naive_top_k"]["rows"]:
        rows.append(naive["aggregate"])
        values.add(int(naive["top_k"]))
    for row in rows:
        values.add(int(row["num_cases"]))
        values.update(int(row[key]) for key in ("FULL", "PART", "MISS"))
    return values


def test_a_wrong_prose_integer_fails_while_a_non_metric_integer_passes() -> None:
    """The boundary of the integer guard, proven both ways on an in-memory copy.

    Mutating a quoted count fails; the integers that are not measurements — the
    plan's target, the D2 arm's FULL, GR-0.2's precondition, the date, the
    section number — still pass, so the guard is not bought by dragging every
    digit in the document into the report. That each named exemption covers a
    phrase a capsule carries, and nothing once a digit changes, is pinned once
    for both capsules in `tests/test_capsule_prose.py`.
    """
    report = _committed()
    decimals = _reported_metric_values(report)
    integers = _reported_integer_values(report)
    capsule = _capsule()

    def prose_defects(text: str) -> list[str]:
        return unreported_numbers(prose_lines(text), decimals=decimals, integers=integers)

    headline = next(
        cell for cell in report["grid"] if cell["parameters"] == report["headline"]["parameters"]
    )
    anchor = str(headline["diagnostics"]["docs_selected"])
    assert any(anchor in line for line in prose_lines(capsule)), (
        f"this test mutates the selected-chunk count {anchor}; the capsule no "
        "longer carries it, so re-anchor the mutation before trusting it"
    )
    # The exact defect this guard was written for: 394 -> 494.
    assert "4" + anchor[1:] in prose_defects(capsule.replace(anchor, "4" + anchor[1:]))

    # …and the honest number passes.
    assert prose_defects(capsule) == []

    # The exemptions are not decoration: without them the plan's target and the
    # D2 arm's parameters would be flagged, because the report does not carry
    # them — that is precisely why they are named rather than silently allowed.
    outside = {
        claim
        for phrase, _reason in NON_REPORT_PHRASES
        if phrase in capsule
        for claim in numeric_claims(phrase, phrases=())
        if int(claim) not in integers
    }
    assert {"96", "3600"} <= outside
    for token in outside:
        assert prose_defects(f"a sentence with {token} in it") == [token]

    # A date is not a count; a bare wrong count is.
    assert prose_defects("Date: 2026-09-09") == []
    assert prose_defects("the other 483 had none") == ["483"]


# ---------------------------------------------------------------------------
# The capsule's tables — every one of them, each against its own report section
#
# The first form of this guard filtered table rows by width and read only the
# nine-cell grid. Two of the capsule's tables are seven cells wide and one is
# three, so three of the four were pinned by nothing while the capsule claimed
# all of them were: corrupting a naive-top-k or a by-class cell left every test
# passing. Tables are therefore located by their header, never by their width,
# and each has a defect function of (rows, report) so the mutation proof can run
# the same check over an in-memory copy.
# ---------------------------------------------------------------------------

#: The em dash the capsule prints for a metric the report carries as ``null`` —
#: a class with no cases reports nothing, never ``0.0000``.
_NO_VALUE = "—"

#: The arrow the capsule prints between a case's keyword status before and after.
_TO = "→"


def _metric_cell(value: float | None) -> str:
    return _NO_VALUE if value is None else f"{value:.4f}"


def _grid_table_defects(rows: list[list[str]], report: dict[str, Any]) -> list[str]:
    """Every published grid cell carries its own committed numbers."""
    defects: list[str] = []
    published = {(row[0], row[1], row[2]): row[3:] for row in rows[1:]}
    seen: set[tuple[str, str, str]] = set()
    for cell in report["grid"]:
        parameters = cell["parameters"]
        aggregate = cell["aggregate"]
        key = (
            str(parameters["neighbourhood"]),
            f"{parameters['singleton_threshold']:.2f}",
            "on" if parameters["expand_to_section"] else "off",
        )
        if key not in published:
            defects.append(f"grid cell {key} is missing from the capsule")
            continue
        seen.add(key)
        defects += row_defects(
            published[key],
            [
                f"{aggregate['context_precision']:.4f}",
                f"{cell['delta']['context_precision']:+.4f}",
                f"{aggregate['context_recall']:.4f}",
                str(aggregate["FULL"]),
                str(aggregate["PART"]),
                str(aggregate["MISS"]),
            ],
            f"grid {key}",
        )
    for extra in sorted(set(published) - seen):
        defects.append(f"the capsule publishes a grid row {extra} the report does not carry")
    return defects


def _naive_table_defects(rows: list[list[str]], report: dict[str, Any]) -> list[str]:
    """Every row of the naive top-k reference is that row of the report."""
    defects: list[str] = []
    published = {row[0]: row[1:] for row in rows[1:]}
    for naive in report["naive_top_k"]["rows"]:
        key = str(naive["top_k"])
        aggregate = naive["aggregate"]
        if key not in published:
            defects.append(f"naive top-{key} is missing from the capsule")
            continue
        defects += row_defects(
            published.pop(key),
            [
                f"{naive['mean_docs']:.2f}",
                _metric_cell(aggregate["context_precision"]),
                _metric_cell(aggregate["context_recall"]),
                str(aggregate["FULL"]),
                str(aggregate["PART"]),
                str(aggregate["MISS"]),
            ],
            f"naive top-{key}",
        )
    for extra in sorted(published):
        defects.append(f"the capsule publishes a naive row top-{extra} the report does not carry")
    return defects


def _class_table_defects(rows: list[list[str]], report: dict[str, Any]) -> list[str]:
    """The by-class table is the baseline's and the headline cell's own buckets.

    A class with cases has to appear for both bases — a precision gain whose
    coverage is not shown beside it is what `docs/specs/retrieval-buckets.md`
    refuses. A class with no cases reports the same nothing under either base, so
    the capsule may publish it once.
    """
    defects: list[str] = []
    headline = next(
        cell for cell in report["grid"] if cell["parameters"] == report["headline"]["parameters"]
    )
    accepted: dict[str, list[str]] = {}
    required: list[tuple[str, tuple[str, ...]]] = []
    for base, block in (("baseline", report["baseline"]), ("headline", headline)):
        for bucket in [*block["buckets"], block["aggregate"]]:
            expected = [
                str(bucket["num_cases"]),
                _metric_cell(bucket["context_precision"]),
                _metric_cell(bucket["context_recall"]),
                str(bucket["FULL"]),
                str(bucket["PART"]),
                str(bucket["MISS"]),
            ]
            label = f"{bucket['question_class']} ({base})"
            accepted[label] = expected
            if bucket["num_cases"]:
                required.append((label, (label,)))
                continue
            # An empty class carries no metric under either base, so one row for
            # it is honest — under whichever of the three labels the capsule uses.
            bare = str(bucket["question_class"])
            accepted[bare] = expected
            required.append((bare, (bare, f"{bare} (baseline)", f"{bare} (headline)")))

    published = {row[0]: row[1:] for row in rows[1:]}
    for label, cells in published.items():
        if label not in accepted:
            defects.append(f"the by-class table publishes {label!r}, which is not a report bucket")
            continue
        defects += row_defects(cells, accepted[label], f"by class {label!r}")
    for name, alternatives in required:
        if not any(alternative in published for alternative in alternatives):
            defects.append(f"the by-class table does not publish {name!r}")
    return defects


def _regression_table_defects(rows: list[list[str]], report: dict[str, Any]) -> list[str]:
    """Every from→to pair is the pair the matching cell's report entry carries.

    The thresholds are read out of the header, so a cell that starts regressing a
    case at a threshold the table has no column for is a defect rather than a
    silent omission.
    """
    defects: list[str] = []
    columns: list[float] = []
    for heading in rows[0][1:]:
        found = re.search(r"\d\.\d+", heading)
        if found is None:
            defects.append(f"the regression column {heading!r} names no threshold")
            continue
        columns.append(float(found.group()))

    expected: dict[float, dict[str, str]] = {}
    for threshold in columns:
        pairs: dict[str, set[str]] = {}
        for cell in report["grid"]:
            if cell["parameters"]["singleton_threshold"] != threshold:
                continue
            for regression in cell["keyword_regressions"]:
                pairs.setdefault(str(regression["case_id"]), set()).add(
                    f"{regression['from']} {_TO} {regression['to']}"
                )
        for case_id, seen in sorted(pairs.items()):
            if len(seen) > 1:
                defects.append(
                    f"the cells at threshold {threshold} disagree on {case_id}: {sorted(seen)}; "
                    "one column cannot publish two different pairs"
                )
        expected[threshold] = {case_id: sorted(seen)[0] for case_id, seen in pairs.items()}

    regressing = {
        cell["parameters"]["singleton_threshold"]
        for cell in report["grid"]
        if cell["keyword_regressions"]
    }
    for threshold in sorted(regressing - set(columns)):
        defects.append(
            f"threshold {threshold} regresses a case and the capsule table has no column for it"
        )

    published = {row[0].strip("`"): row[1:] for row in rows[1:]}
    for case_id, cells in published.items():
        defects += row_defects(
            cells,
            [expected[threshold].get(case_id, _NO_VALUE) for threshold in columns],
            f"regression {case_id}",
        )
    for threshold in columns:
        for case_id in sorted(expected[threshold]):
            if case_id not in published:
                defects.append(
                    f"{case_id} regressed at threshold {threshold} and the capsule does not name it"
                )
    return defects


#: The tables the capsule publishes with a structural guard, and the report
#: section that decides each, keyed by the table's first header cell. The
#: provenance table's header row is blank, so it is keyed by its first row
#: (``Pool``); it has no structural guard, and the shared contract alone pins it.
_TABLE_GUARDS: dict[str, Any] = {
    "n": _grid_table_defects,
    "naive top-k": _naive_table_defects,
    "question class": _class_table_defects,
    "case": _regression_table_defects,
}


def test_the_capsule_publishes_every_grid_cell_with_its_own_numbers() -> None:
    """The whole grid is in the capsule — not only the cell that won.

    Cell by cell, precision, the delta, recall and the FULL / PART / MISS triple
    all have to be the committed cell's own: choosing the best cell and
    publishing only it is how a harness starts fitting itself to 100 cases, and
    a table that drifts from the artifact is the same failure one edit later.
    """
    report = _committed()

    defects = _grid_table_defects(capsule_tables(_capsule())["n"], report)

    assert defects == []
    assert len(capsule_tables(_capsule())["n"]) - 1 == len(report["grid"])


def test_the_capsule_publishes_the_naive_reference_the_report_measured() -> None:
    """The reference that decides what the gain is worth is pinned like the grid.

    Its 0.5214 at k = 4 against the headline's 0.5216 *is* the finding of this
    slice; a table cell nobody checks is the one place that finding could quietly
    invert.
    """
    report = _committed()

    defects = _naive_table_defects(capsule_tables(_capsule())["naive top-k"], report)

    assert defects == []
    assert len(capsule_tables(_capsule())["naive top-k"]) - 1 == len(report["naive_top_k"]["rows"])


def test_the_capsule_by_class_table_is_the_baseline_and_the_headline_buckets() -> None:
    """Per-class case counts, metrics and coverage, both bases, one table."""
    report = _committed()

    defects = _class_table_defects(capsule_tables(_capsule())["question class"], report)

    assert defects == []


def test_the_capsule_regression_table_carries_the_reports_own_pairs() -> None:
    """Naming the case is half of it; the status it fell from and to is the rest."""
    report = _committed()

    defects = _regression_table_defects(capsule_tables(_capsule())["case"], report)

    assert defects == []


def test_every_number_in_every_capsule_table_is_a_number_the_report_carries() -> None:
    """The completeness half of the table guard, under the shared contract.

    The four tables above are checked structurally; this routes *all* table
    cells — the provenance table included, and any table a later edit adds —
    through the same contract as the prose, so a fifth unpinned table cannot
    appear.
    """
    report = _committed()
    tables = capsule_tables(_capsule())

    decimals = _reported_metric_values(report)
    integers = _reported_integer_values(report)
    assert table_defects(tables, decimals=decimals, integers=integers) == []
    assert set(_TABLE_GUARDS) <= set(tables), (
        f"the capsule no longer carries {sorted(set(_TABLE_GUARDS) - set(tables))}; "
        "a renamed table would leave its own guard reading nothing"
    )
    quoted = sum(
        len(numeric_claims(cell)) for rows in tables.values() for row in rows for cell in row
    )
    assert quoted >= 100, (
        f"only {quoted} numbers were read out of the capsule's tables; the tables are "
        "then unpinned and this test would pass vacuously"
    )


def test_the_committed_capsule_passes_the_shared_contract_unchanged() -> None:
    """FALSE-REJECT control: the published capsule, prose and every table, as committed.

    The contract was widened — sentence-final decimals, grouped numbers, signed
    deltas read with their sign. A widening that rejected an honest number here
    would be a defect of the guard, not of the capsule.
    """
    report = _committed()

    assert (
        capsule_defects(
            _capsule(),
            decimals=_reported_metric_values(report),
            integers=_reported_integer_values(report),
        )
        == []
    )


def test_a_wrong_cell_in_any_capsule_table_fails_and_a_non_metric_cell_does_not() -> None:
    """One mutation per table, the way T-12's closing pass proved its own guard.

    The two mutations named here are the ones that survived the width-9 guard:
    the naive-top-k cell 0.5214 and the by-class cell 0.4267, which is the whole
    reason this test exists. The provenance table has no structural guard — the
    shared contract alone pins its numbers — so its mutations go that route.
    """
    report = _committed()
    decimals = _reported_metric_values(report)
    integers = _reported_integer_values(report)
    tables = capsule_tables(_capsule())

    mutations = {
        "n": (5, 3, "0.9216"),  # the headline row's precision
        "naive top-k": (4, 2, "0.9314"),  # top-4's 0.5214 — the finding's own example
        "question class": (4, 2, "0.9967"),  # multi_hop (headline)'s 0.4267
        "case": (1, 1, f"FULL {_TO} MISS"),  # a status pair the report does not carry
    }
    for key, (row, column, value) in mutations.items():
        rows = tables[key]
        wrong = with_cell(rows, row, column, value)
        assert _TABLE_GUARDS[key](rows, report) == [], f"{key} is not honest to begin with"
        assert _TABLE_GUARDS[key](wrong, report), (
            f"a wrong cell in the {key!r} table is not caught by its own guard"
        )
        # …and the same drift is caught by the contract, except where the
        # mutation is a keyword status rather than a number.
        if value.replace(".", "").isdigit():
            assert table_defects({key: wrong}, decimals=decimals, integers=integers), (
                f"a wrong number in the {key!r} table passes the shared contract"
            )

    # The provenance table's header row is blank, so it is keyed by its first row.
    provenance = tables["Pool"]
    for label, honest, wrong_text in (
        ("Pool", "7,692,098 bytes", "7,692,099 bytes"),
        ("Corpus", "201 files", "202 files"),
    ):
        index = next(index for index, cells in enumerate(provenance) if cells[0] == label)
        assert honest in provenance[index][1], f"re-anchor the {label} mutation"
        mutated = with_cell(provenance, index, 1, provenance[index][1].replace(honest, wrong_text))
        assert table_defects({"Pool": mutated}, decimals=decimals, integers=integers), wrong_text

    # A row the report does not carry at all, and a missing row, are both defects.
    invented = [*tables["naive top-k"], ["6", "6.00", "0.5067", "0.9050", "87", "7", "6"]]
    assert _naive_table_defects(invented, report)
    assert _regression_table_defects(tables["case"][:-1], report)

    # The boundary: a cell that is not a measurement stays out of the guard, so
    # the tables are not pinned by dragging every character into the report.
    non_metric = {
        "question class": [
            ["question class", "cases", "ctx precision"],
            [f"single_hop (baseline) {_NO_VALUE}", "GR-0.3", "T-12"],
        ]
    }
    assert table_defects(non_metric, decimals=decimals, integers=integers) == []
    # …while a bare wrong count in the same position is not.
    assert table_defects(
        {"question class": [["cases"], ["483"]]}, decimals=decimals, integers=integers
    )


def test_the_capsule_quotes_the_provenance_digests_of_the_report() -> None:
    report = _committed()
    capsule = CAPSULE.read_text(encoding="utf-8")
    provenance = report["provenance"]

    for digest in (
        provenance["pool_sha256"],
        provenance["dataset_sha256"],
        provenance["corpus"]["corpus_sha256"],
        provenance["code"]["commit"],
    ):
        assert digest in capsule, f"capsule does not quote {digest}"

    # The shared contract makes any number the capsule quotes honest; these two
    # assertions are what make the pool size and the file count quoted at all.
    assert f"{provenance['pool_bytes']:,} bytes" in capsule
    assert f"{provenance['corpus']['file_count']} files" in capsule


def test_the_capsule_names_every_case_whose_keyword_status_regressed() -> None:
    """With 100 cases the regression list is short enough to be read in full.

    Every cell of the published grid, not only the headline: the cells that buy
    precision by dropping the answer are exactly the ones whose cost has to be
    readable by name.
    """
    report = _committed()
    capsule = CAPSULE.read_text(encoding="utf-8")
    regressed = {
        (regression["case_id"], regression["from"], regression["to"])
        for cell in report["grid"]
        for regression in cell["keyword_regressions"]
    }
    if not regressed:
        assert "no case" in capsule.lower(), (
            "no cell regressed a case; the capsule has to say so explicitly"
        )
        return
    for case_id, before, after in sorted(regressed):
        assert case_id in capsule, (
            f"{case_id} regressed {before}->{after} in a published grid cell "
            "and is not named in the capsule"
        )
