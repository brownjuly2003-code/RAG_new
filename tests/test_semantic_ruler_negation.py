"""Conservative claim-window polarity regressions for T-58 repair pass 2."""

import pytest

from evaluation import semantic_ruler as ruler


@pytest.mark.parametrize(
    ("subject", "polarity", "unit", "context"),
    [
        ("cargo", "allowed", "kg", "cargo isn't allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo isn’t allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo isn‘t allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo isnʼt allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo is not, under any circumstances, allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo is never allowed 150 kg"),
        ("cargo", "allowed", "kg", "150 kg allowed except for cargo ..."),
        ("груз", "разрешено", "кг", "груз 150 кг никогда не разрешено"),
        ("груз", "разрешено", "кг", "груз 150 кг разрешено ... груз 150 кг не разрешено"),
        ("груз", "не более", "кг", "груз не более 150 кг"),
        ("груз", "не менее", "кг", "груз не менее 150 кг"),
        ("cargo", "allowed", "kg", "cargo allowed 150 kg. cargo not allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo not allowed 150 kg. cargo allowed 150 kg"),
        ("cargo", "allowed", "kg", "cargo allowed 150 kg. cargo forbidden 150 kg"),
        ("cargo", "allowed", "kg", "cargo allowed 150 kg. cargo 150 kg"),
    ],
)
def test_semantic_ruler_negation_and_mixed_windows_require_blind_judgment(
    subject, polarity, unit, context
):
    facts = [ruler.Fact(subject, polarity, "", 150, unit)]
    pending = []
    assert ruler.fact_coverage(facts, context, needs_blind_judgment=pending) == 0
    assert pending == [0]
    for judgment in (False, True):
        pending = []
        assert ruler.fact_coverage(
            facts, context, blind_judgments={0: judgment}, needs_blind_judgment=pending
        ) == float(judgment)
        assert pending == []


@pytest.mark.parametrize(
    "cue",
    [
        "not",
        "isn't",
        "no",
        "never",
        "neither",
        "nor",
        "cannot",
        "without",
        "except",
        "unless",
        "не",
        "нет",
        "ни",
        "никогда",
        "без",
        "кроме",
    ],
)
@pytest.mark.parametrize("position", ["before", "after"])
def test_semantic_ruler_every_negation_cue_is_ambiguous_anywhere_in_window(cue, position):
    claim = "cargo allowed 150 kg"
    distant_cue = f"{cue}, under any circumstances, with documentation"
    context = f"{distant_cue} {claim}" if position == "before" else f"{claim} {distant_cue}"
    pending = []
    assert (
        ruler.fact_coverage(
            [ruler.Fact("cargo", "allowed", "", 150, "kg")],
            context,
            needs_blind_judgment=pending,
        )
        == 0
    )
    assert pending == [0]


@pytest.mark.parametrize(
    ("subject", "polarity", "unit", "context"),
    [
        ("cargo", "allowed", "kg", "cargo allowed 150 kg"),
        ("груз", "разрешено", "кг", "груз 150 кг разрешено"),
        ("cargo", "allowed", "kg", "cargo allowed 150 kg. cargo permitted 150 kg"),
        ("cargo", "allowed", "kg", "cargo allowed 150 kg with notable normal exceptions"),
        ("груз", "разрешено", "кг", "груз 150 кг разрешено независимо"),
    ],
)
def test_semantic_ruler_positive_windows_and_negation_word_boundaries(
    subject, polarity, unit, context
):
    pending = []
    assert (
        ruler.fact_coverage(
            [ruler.Fact(subject, polarity, "", 150, unit)], context, needs_blind_judgment=pending
        )
        == 1
    )
    assert pending == []


def test_semantic_ruler_unknown_polarity_stays_ambiguous():
    pending = []
    assert (
        ruler.fact_coverage(
            [ruler.Fact("cargo", "unknown", "", 150, "kg")],
            "cargo allowed 150 kg",
            needs_blind_judgment=pending,
        )
        == 0
    )
    assert pending == [0]
