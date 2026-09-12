from scripts.gr1b_query_control import select_query_subset


def test_selection_preserves_query_terms_and_original_order():
    assert select_query_subset(
        query="alpha beta", candidates=["alpha", "noise", "beta", "noise", "noise"],
        context_chars=6000,
    ) == [0, 2]


def test_selection_scores_after_cap_and_falls_back_without_query_signal():
    assert select_query_subset(
        query="beta", candidates=["noise beta", "beta", "noise", "noise", "noise"],
        context_chars=4,
    ) == [1]
    assert select_query_subset(
        query="", candidates=["a", "b", "c", "d", "e"], context_chars=6000,
    ) == [0, 1, 2, 3, 4]
