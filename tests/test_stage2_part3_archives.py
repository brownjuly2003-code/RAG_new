"""Stage 2, part 3 (amended 2026-10-19): what GR-3's committed archives show of the graph lane.

docs/specs/stage2-four-corpora.md, «Part 3»: the entity lane is measured by counting GR-3's
arms, not by a new run. Each archive holds, per question, the candidates an arm handed on
(``cands`` with ``cand_sources``): the hybrid ``Hm`` in reranked order, its context the first
five; the structural route ``G1m`` and the structural + entity route ``G2m`` after their rerank
and section handling. GR-3 scores every arm through one function with one top-k and one
context cap, so equal candidates give equal contexts.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
# docs/evidence/gr3-graph-lane-ab.md, «Archives»: SHA-256 of the uncompressed bytes.
ARCHIVES = {
    ("phase-c", "Hm"): "0e93f6e82edc2830269baa803fab8f677fe3fda0803c5afccdfb5289960c2d55",
    ("phase-c", "G1m"): "cd139b0b113ce642613d955914e34d104a1eb74d258b56f311aae084e80feb7d",
    ("phase-c", "G2m"): "fb7a22613514434042695a531f85dae8b319c150e5c3ef25e50bdbf47745792e",
    ("bucket", "Hm"): "3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee",
    ("bucket", "G1m"): "955c74d810e86282cf88a61c670ee9c241f0434763dad7d8206164e093370c93",
    ("bucket", "G2m"): "df4486ffe45a3244cf1d2254b3859570e8cb046258983326d0b43e05c3ba505d",
}


@pytest.fixture(scope="module")
def arms() -> dict[tuple[str, str], dict[str, dict]]:
    out = {}
    for (part, arm), digest in ARCHIVES.items():
        path = EVALUATION / f"gr3-32de532-{part}-{arm}-candidates.json.gz"
        data = gzip.decompress(path.read_bytes())
        assert hashlib.sha256(data).hexdigest() == digest, path.name
        out[(part, arm)] = {row["case_id"]: row for row in json.loads(data)}
    return out


def _handed_on(row: dict) -> tuple[list[str], list[str]]:
    return row["cands"], row["cand_sources"]


@pytest.mark.parametrize(("part", "cases", "differ"), [("phase-c", 100, 2), ("bucket", 15, 0)])
def test_the_entity_lane_changes_what_is_handed_on_on_two_of_115_questions(
    arms, part, cases, differ
) -> None:
    hybrid, structural, entity = (arms[(part, arm)] for arm in ("Hm", "G1m", "G2m"))
    assert len(hybrid) == cases and set(hybrid) == set(structural) == set(entity)
    changed = [c for c in structural if _handed_on(structural[c]) != _handed_on(entity[c])]
    assert len(changed) == differ
    # The two changes lie where the entity lane found an entity of the question.
    assert all(entity[c].get("matched_entities") for c in changed)


@pytest.mark.parametrize(
    ("part", "matched", "classes"),
    [
        ("phase-c", 5, {"single_hop": 94, "global": 5, "multi_hop": 1}),
        ("bucket", 11, {"multi_hop": 9, "single_hop": 4, "global": 1, "aggregation": 1}),
    ],
)
def test_the_entity_lane_is_routed_and_matched_where_the_spec_says(
    arms, part, matched, classes
) -> None:
    entity, structural = arms[(part, "G2m")], arms[(part, "G1m")]
    assert sum(bool(row.get("matched_entities")) for row in entity.values()) == matched
    assert Counter(row.get("routed_question_class") for row in entity.values()) == classes
    assert not any(row.get("matched_entities") for row in structural.values())


@pytest.mark.parametrize(
    ("part", "handed_on", "subset_g1", "subset_g2"),
    [("phase-c", 305, 59, 57), ("bucket", 45, 5, 5)],
)
def test_the_graph_route_hands_on_fewer_documents_mostly_the_hybrids_own(
    arms, part, handed_on, subset_g1, subset_g2
) -> None:
    hybrid = arms[(part, "Hm")]
    assert all(len(row["cands"]) >= 5 for row in hybrid.values())
    for arm, subset in (("G1m", subset_g1), ("G2m", subset_g2)):
        graph = arms[(part, arm)]
        assert sum(len(row["cands"]) for row in graph.values()) == handed_on
        assert all(len(row["cands"]) <= 5 for row in graph.values())
        within = [c for c in graph if all(t in hybrid[c]["cands"][:5] for t in graph[c]["cands"])]
        assert len(within) == subset


@pytest.mark.parametrize("part", ["phase-c", "bucket"])
def test_only_the_entity_lane_brings_a_source_from_outside_the_hybrids_five(arms, part) -> None:
    hybrid, structural, entity = (arms[(part, arm)] for arm in ("Hm", "G1m", "G2m"))

    def outside(graph: dict[str, dict]) -> set[str]:
        return {
            c
            for c, row in graph.items()
            if not set(row["cand_sources"]) <= set(hybrid[c]["cand_sources"][:5])
        }

    changed = {c for c in structural if _handed_on(structural[c]) != _handed_on(entity[c])}
    assert outside(structural) == set()
    assert outside(entity) == changed
