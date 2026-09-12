import json

from scripts.generator_benchmark import _truncate_contexts
from scripts.gr1b_seed_expansion import DEFAULT_REPORT, build_seed_report, reserve_seed_contexts


def test_expansion_cannot_displace_later_seed_under_global_cap():
    result = reserve_seed_contexts(["alpha", "beta"], ["xxxalphayyy", "betazzz"], 12)
    assert result == ["xxxalpha", "beta"]
    assert sum(map(len, result)) == 12


def test_over_budget_seeds_keep_original_truncation_and_no_expansion():
    assert reserve_seed_contexts(["alpha", "beta"], ["xxxalpha", "betazzz"], 7) == ["alpha", "be"]


def test_prefix_is_kept_nearest_to_seed_and_suffix_uses_remaining_space():
    assert reserve_seed_contexts(["seed"], ["farnear seedsuffix".replace("near ", "near")], 7) == ["earseed"]
    assert reserve_seed_contexts(["seed"], ["xxseedsuffix"], 9) == ["xxseedsuf"]


def test_all_caps_preserve_capped_seed_text_and_rank():
    seeds = ["alpha", "", "beta", "gamma"]
    expanded = ["beforealphaafter", "", "beforebetaafter", "beforegammaafter"]
    for cap in range(1, 60):
        actual = reserve_seed_contexts(seeds, expanded, cap)
        baseline = _truncate_contexts(seeds, cap)
        assert len(actual) == len(baseline)
        assert sum(map(len, actual)) <= cap
        assert all(seed in text for seed, text in zip(baseline, actual, strict=True))


def test_published_seed_control_reproduces_every_case_and_provenance():
    published = json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))
    rebuilt = build_seed_report()
    for field in ("arms", "baseline", "exact_replays", "labels"):
        assert rebuilt[field] == published[field]
    for field in ("archive_sha256", "pool_sha256", "dataset_sha256", "label_sidecar_sha256",
                  "label_manifest_sha256", "corpus", "config", "recovered_inputs"):
        assert rebuilt["provenance"][field] == published["provenance"][field]
    assert [arm["ordinary_seed_loss_cases"] for arm in rebuilt["arms"]] == [11, 1]
    assert all(arm["comparison"]["lost_keyword_cases"] == [] for arm in rebuilt["arms"])
