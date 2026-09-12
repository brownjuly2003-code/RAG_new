from scripts.gr1b_seed_expansion import reserve_seed_contexts


def test_expansion_cannot_displace_later_seed_under_global_cap():
    result = reserve_seed_contexts(["alpha", "beta"], ["xxxalphayyy", "betazzz"], 12)
    assert result == ["xxxalpha", "beta"]
    assert sum(map(len, result)) == 12


def test_over_budget_seeds_keep_original_truncation_and_no_expansion():
    assert reserve_seed_contexts(["alpha", "beta"], ["xxxalpha", "betazzz"], 7) == ["alpha", "be"]


def test_prefix_is_kept_nearest_to_seed_and_suffix_uses_remaining_space():
    assert reserve_seed_contexts(["seed"], ["farnear seedsuffix".replace("near ", "near")], 7) == ["earseed"]
    assert reserve_seed_contexts(["seed"], ["xxseedsuffix"], 9) == ["xxseedsuf"]
