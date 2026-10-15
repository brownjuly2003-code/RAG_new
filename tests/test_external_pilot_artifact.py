"""The published external pilot preserves its provenance and registered sizing rule."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from evaluation import external_parts as parts
from scripts import external_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/external/64a72e5/pilot"
CAPSULE = ROOT / "docs/evidence/external-bases-pilot.md"
BASES = {"conditionalqa": (50, 25), "wixqa": (40, 33)}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def mismatches(rebuilt: object, published: object, path: str = "") -> list[str]:
    """Paths where two JSON values differ, floats compared to a relative 1e-12.

    The power terms go through ``statistics.NormalDist`` (``math.erfc``,
    ``math.log``), whose last bits differ between the Mac that published the
    sizes and the Linux runners of CI.
    """
    if isinstance(rebuilt, float) and isinstance(published, float):
        return [] if math.isclose(rebuilt, published, rel_tol=1e-12) else [path]
    if isinstance(rebuilt, dict) and isinstance(published, dict):
        if rebuilt.keys() != published.keys():
            return [f"{path} keys"]
        return [
            gap
            for key in published
            for gap in mismatches(rebuilt[key], published[key], f"{path}/{key}")
        ]
    if isinstance(rebuilt, list) and isinstance(published, list):
        if len(rebuilt) != len(published):
            return [f"{path} length"]
        return [
            gap
            for index, (left, right) in enumerate(zip(rebuilt, published, strict=True))
            for gap in mismatches(left, right, f"{path}/{index}")
        ]
    return [] if rebuilt == published else [path]


@pytest.fixture(scope="module")
def aggregates() -> dict:
    return {base: read(RUN / f"{base}.aggregates.json") for base in BASES}


def test_transfer_binds_both_aggregates_to_the_completed_measure(aggregates):
    receipt = read(RUN / "receipt.json")
    assert receipt["status"] == "complete"
    assert receipt["finished"] == "2026-10-07T00:25:03+00:00"
    assert set(receipt["bases"]) == set(BASES)
    for base, document in aggregates.items():
        held = receipt["bases"][base]
        payload = (RUN / f"{base}.aggregates.json").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == held["aggregates_sha256"]
        assert document["measure_sha256"] == held["measure_sha256"]
        assert held["exit_code"] == 0
        assert held["aggregate_matches_full_projection"] is True
        assert "per_case" not in document
        assert not (RUN / f"{base}.json").exists()
    assert hashlib.sha256((RUN / "sizes.json").read_bytes()).hexdigest() == receipt["sizes_sha256"]


def test_pilot_has_all_registered_pairs_and_the_connected_indexes(aggregates):
    registration = parts.registration()
    connection = read(ROOT / "reports/external/36f1167/connection.json")
    for base, (cases, clusters) in BASES.items():
        document = aggregates[base]
        provenance = document["provenance"]
        selection = registration["selections"][base]["pilot"]
        index = connection["bases"][base]["index"]["report"]
        assert document["cases"] == selection["cases"] == cases
        assert document["clusters"]["count"] == clusters
        assert document["gold_in_index"] == {"cases": cases, "of": cases}
        assert document["chunks_without_a_place"] == (0 if base == "conditionalqa" else None)
        assert provenance["base"]["cases_sha256"] == selection["cases_sha256"]
        assert provenance["archive_sha256"] == index["corpus_sha256"]
        assert provenance["checkpoint_sha256"] == index["checkpoint_sha256"]
        assert provenance["embedder"] == index["embedder_manifest"]
        assert provenance["code_sha"] == "64a72e551c349913132ff880666e7ceaf8ae04dd"
        assert provenance["runs"]["control"]["config_overrides"] == {}
        assert provenance["runs"]["pool30"]["config_overrides"] == {"retrieval_top_k": 30}
        assert provenance["context_budget"] == {
            "rerank_top_k": 5,
            "parent_expansion": True,
            "parent_expansion_window": 2,
            "parent_expansion_max_chars": 3600,
        }
        pair = document["pairs"]["pool30"]
        assert pair["pairs"] == cases and pair["lost"] == []
        assert pair["primary"]["used"] is True
        assert pair["primary"]["not_used_because"] is None
        for arm in document["arms"].values():
            assert arm["measured"] == cases and arm["excluded"] == {}


def test_primary_variances_follow_binary_pair_counts(aggregates):
    for document in aggregates.values():
        pair = document["pairs"]["pool30"]
        primary = pair["primary"]
        point, metric = primary["point"], primary["metric"]
        means = [document["arms"][arm]["points"][point][metric] for arm in pilot.ARMS]
        assert primary["mean"] == pytest.approx(means[1] - means[0])
        assert means[0] > 0
        for row in (primary, *pair["primary_by_stratum"].values()):
            # For d in {-1, 0, 1}, sum(d**2) is exactly the number of nonzero pairs.
            expected = (row["differing_pairs"] - row["n"] * row["mean"] ** 2) / (row["n"] - 1)
            assert row["variance"] == pytest.approx(expected)
    assert aggregates["conditionalqa"]["pairs"]["pool30"]["primary"]["variance"] == pytest.approx(0.02)
    assert aggregates["wixqa"]["pairs"]["pool30"]["primary"]["variance"] == pytest.approx(0.025)


def test_sizes_replay_and_do_not_lower_the_registered_variance(aggregates):
    published = read(RUN / "sizes.json")
    rebuilt = pilot.sizes(parts.registration(), aggregates)
    assert rebuilt.pop("code") == {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in pilot.CODE_FILES
    }
    published_code = published.pop("code")
    assert set(published_code) == set(pilot.CODE_FILES)
    for document in aggregates.values():
        assert published_code == document["provenance"]["measure_code"]
    assert mismatches(rebuilt, published) == []
    assert len(published["rows"]) == 124
    for strata in published["variances"].values():
        for row in strata.values():
            assert row["variance"] == max(row["candidates"].values()) == 0.10
            assert row["source"] == "grid"


def test_step_one_uses_control_stage_seconds_and_fits_both_bases(aggregates):
    sizes = read(RUN / "sizes.json")
    step = sizes["step_1"]
    assert step["ceiling_seconds"] == 8 * 8 * 3600
    for base, stages in {
        "conditionalqa": ("transform", "embed", "retrieve", "grade"),
        "wixqa": ("transform", "embed", "retrieve"),
    }.items():
        seconds = aggregates[base]["arms"]["control"]["seconds"]
        assert step["seconds_per_question"][base] == pytest.approx(
            math.fsum(seconds[stage]["mean"] for stage in stages)
        )
    assert step["wixqa"]["questions"] == 200
    wix_seconds = 2 * 200 * step["seconds_per_question"]["wixqa"]
    assert step["wixqa"]["seconds_of_two_arms"] == pytest.approx(wix_seconds)
    for stratum, pages in {"primary": 165, "several_sections": 145}.items():
        row = step["conditionalqa"][stratum]
        assert row["pages_read"] == row["pages_with_a_question"] == pages
        seconds = 2 * pages * step["seconds_per_question"]["conditionalqa"]
        assert row["seconds_of_two_arms"] == pytest.approx(seconds)
        assert seconds + wix_seconds <= step["ceiling_seconds"]
        assert row["registered"]["intraclass_correlation"] == 1
        assert row["registered"]["standard_error"] == pytest.approx(math.sqrt(0.10 / pages))
        assert row["registered"]["critical"] > 1.96


def test_capsule_reports_the_measured_counts_and_the_two_alternative_budgets(aggregates):
    capsule = CAPSULE.read_text(encoding="utf-8")
    sizes = read(RUN / "sizes.json")
    for base, document in aggregates.items():
        pair = document["pairs"]["pool30"]["primary"]
        expected = (
            f"| {base} | {document['cases']} | {document['clusters']['count']} | "
            f"{pair['differing_pairs']} | {pair['variance']:.4f} | 0.1000 |"
        )
        assert expected in capsule
    step = sizes["step_1"]
    for stratum in ("primary", "several_sections"):
        row = step["conditionalqa"][stratum]
        hours = (row["seconds_of_two_arms"] + step["wixqa"]["seconds_of_two_arms"]) / 3600
        registered = row["registered"]
        assert (
            f"| {stratum} | {row['pages_read']} | {registered['mde']:.3f} | "
            f"{registered['effect_for_rule']:.3f} | {hours:.2f} | {hours / 8:.2f} |"
        ) in capsule
    assert "external-bases-pilot.md" in (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
