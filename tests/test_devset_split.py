"""The split of plan step 1.3c: blocks, draw order, class sequence, seats, the registered file."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from typing import Any

import pytest

from evaluation import devset_split as split
from evaluation.devset_sources import corpus_directory
from evaluation.devset_sources import sections as heading_bodies

PROSE = (
    "Смена принимает {word} по накладной, сверяет число мест с манифестом и отмечает "
    "расхождения в журнале до конца своей смены. Журнал {word} хранится у начальника "
    "смены три года и предъявляется по запросу службы качества."
)
ITEMS = (
    "Для {word} смена готовит:\n"
    "- накладную с отметкой склада о приёме {word};\n"
    "- акт осмотра упаковки {word}, подписанный кладовщиком;\n"
    "- фотографии повреждений {word}, если они есть.\n"
    "Без этих документов {word} остаётся на складе до решения начальника смены."
)


def corpus(**bodies: Sequence[str]) -> tuple[dict[str, str], dict[str, list[dict[str, Any]]]]:
    """One document per name, one section per body; the sections by document."""
    texts, by_document = {}, {}
    for name, parts in bodies.items():
        source_id = f"{name}.md"
        texts[source_id] = "".join(
            f"## Раздел {number}\n{body}\n" for number, body in enumerate(parts, 1)
        )
        by_document[name] = heading_bodies(source_id, texts[source_id])
        assert len(by_document[name]) == len(parts)
    return texts, by_document


def block(block_id: str, *names: str) -> dict[str, Any]:
    return {"block_id": block_id, "documents": [f"{name}.md" for name in names]}


def every_token(texts: dict[str, str]) -> dict[str, float]:
    return {token: 1.0 for text in texts.values() for token in split.TOKEN.findall(text.casefold())}


def test_a_family_of_several_documents_is_a_block_and_the_rest_pair_by_similarity() -> None:
    families = {
        "family-several": ["m1.md", "m2.md", "m3.md"],
        "family-p": ["p.md"],
        "family-q": ["q.md"],
        "family-r": ["r.md"],
        "family-s": ["s.md"],
        "family-t": ["t.md"],
    }
    vectors = {
        "p.md": {"u": 1.0},
        "q.md": {"u": 0.9},
        "r.md": {"u": 0.7, "w": 0.5},
        "s.md": {"w": 0.6},
        "t.md": {"k": 1.0},
    }
    blocks = {tuple(b["documents"]): b for b in split.build_blocks(families, vectors)}
    assert set(blocks) == {
        ("m1.md", "m2.md", "m3.md"),
        ("p.md", "q.md"),
        ("r.md", "s.md"),
        ("t.md",),
    }
    assert blocks["m1.md", "m2.md", "m3.md"]["basis"] == "family"
    # r is closest to p (0.7), but p went to q (0.9): r takes what is left, s (0.3).
    assert blocks["p.md", "q.md"]["similarity"] == 0.9
    assert blocks["r.md", "s.md"] == {
        "documents": ["r.md", "s.md"],
        "families": ["family-r", "family-s"],
        "basis": "pair",
        "similarity": 0.3,
        "block_id": "block-" + hashlib.sha256(b"r.md|s.md").hexdigest()[:12],
    }
    assert blocks["t.md",]["basis"] == "single" and blocks["t.md",]["families"] == ["family-t"]


def test_equal_similarities_pair_by_document_name() -> None:
    families = {f"family-{name}": [f"{name}.md"] for name in "cab"}
    vectors = {f"{name}.md": {name: 1.0} for name in "cab"}
    blocks = split.build_blocks(families, vectors)
    assert sorted(b["documents"] for b in blocks) == [["a.md", "b.md"], ["c.md"]]


def test_similarity_is_the_cosine_of_tf_idf_vectors() -> None:
    texts = {
        "a.md": "Груз груз весы, склад 2026!",
        "b.md": "ГРУЗ и терминал",
        "c.md": "отпуск и склад",
    }
    idf = split.weights(texts)
    # «и» and «2026» are not tokens; «груз» and «склад» are in two documents of three.
    assert set(idf) == {"груз", "весы", "склад", "терминал", "отпуск"}
    assert idf["груз"] == pytest.approx(0.405465108) and idf["весы"] == pytest.approx(1.098612289)
    a, b, c = (split.vector(texts[name], idf) for name in ("a.md", "b.md", "c.md"))
    assert sum(value * value for value in a.values()) == pytest.approx(1.0)
    assert split.similarity(a, a) == 1.0 and split.similarity(a, b) == split.similarity(b, a)
    assert split.similarity(b, c) == 0.0 < split.similarity(a, c) < split.similarity(a, b)
    assert split.vector("и 2026", idf) == {}


def test_the_draw_goes_round_the_blocks_and_leaves_pilot_blocks_for_last() -> None:
    _, sections = corpus(a=["a1", "a2"], b=["b1"], c=["c1", "c2", "c3"], d=["d1"])
    blocks = [block("block-ab", "a", "b"), block("block-c", "c"), block("block-d", "d")]
    frame = [section for name in "abcd" for section in sections[name]]
    order = split.draw_order("holdout", blocks, frame, {"block-c": 2})
    assert sorted(order, key=split.key) == sorted(frame, key=split.key)
    owner = {
        s["source_id"]: b["block_id"]
        for b in blocks
        for s in frame
        if s["source_id"] in b["documents"]
    }
    rounds = [owner[section["source_id"]] for section in order]
    # Three sections each in block-ab and block-c, one in block-d; block-c holds pilot cases.
    assert rounds[2] == "block-c" and set(rounds[:2]) == {"block-ab", "block-d"}
    assert rounds[3:] == ["block-ab", "block-c", "block-ab", "block-c"]
    assert rounds[:2] == sorted(rounds[:2], key=lambda name: split.rank("holdout", "block", name))
    for name in ("block-ab", "block-c"):
        own = [section for section in order if owner[section["source_id"]] == name]
        assert own == sorted(own, key=lambda s: split.rank("holdout", "section", *split.key(s)))
    assert order != split.draw_order("development", blocks, frame, {"block-c": 2})


def test_the_rank_is_the_hash_of_the_seed_and_the_named_parts() -> None:
    text = "20260925:holdout:section:a.md:17"
    assert split.rank("holdout", "section", "a.md", 17) == hashlib.sha256(text.encode()).hexdigest()


def test_quotas_are_the_largest_remainders_of_the_registered_shares() -> None:
    assert split.quotas(split.HOLDOUT_SHARES, 100) == split.HOLDOUT_SHARES
    # 15.36 / 25.6 / 10.24 / 12.8: the two places left go to the remainders .8 and .6.
    assert split.quotas(split.HOLDOUT_SHARES, 64) == {
        "single-doc": 15,
        "multi-doc": 26,
        "aggregation": 10,
        "needs-refusal/clarification": 13,
    }
    # Equal remainders (.5 four times): the places go in class order.
    assert split.quotas(dict.fromkeys(split.CLASSES, 25), 2) == {
        "multi-doc": 1,
        "single-doc": 1,
        "aggregation": 0,
        "needs-refusal/clarification": 0,
    }


@pytest.mark.parametrize("counts", [split.DEV_NEW, split.quotas(split.HOLDOUT_SHARES, 64)])
def test_the_class_sequence_holds_each_quota_and_lets_no_class_run_ahead(
    counts: dict[str, int],
) -> None:
    sequence = split.class_sequence(counts)
    total = sum(counts.values())
    assert Counter(sequence) == Counter(counts)
    for position in range(1, total + 1):
        placed = Counter(sequence[:position])
        for name in split.CLASSES:
            assert placed[name] * total < counts[name] * position + total
    assert sequence[0] == "multi-doc"


def test_list_items_are_bullets_numbered_lines_and_table_rows() -> None:
    body = "Вводная строка - не пункт.\n- первый\n  * второй\n3. третий\n4) четвёртый\n| a | b |\n-без пробела\n"
    assert split.list_items(body) == 5
    assert split.list_items(PROSE.format(word="груз")) == 0
    assert split.list_items(ITEMS.format(word="груз")) == split.AGGREGATION_ITEMS


def test_a_position_of_one_document_takes_the_first_free_section() -> None:
    texts, sections = corpus(a=["первый раздел", "второй раздел"])
    order = [sections["a"][1], sections["a"][0]]
    positions = split.seat(
        ["single-doc", "needs-refusal/clarification", "single-doc"],
        order,
        [block("block-a", "a")],
        texts,
        every_token(texts),
        None,
    )
    assert [place["seed"] for place in positions] == [*order, None]
    assert [place["block_id"] for place in positions] == ["block-a", "block-a", None]
    assert all(place["partner"] is None for place in positions)
    assert [place["position"] for place in positions] == [1, 2, 3]


def test_a_position_of_several_documents_needs_a_second_document_in_its_block() -> None:
    texts, sections = corpus(solo=["груз весы"], a=["груз склад"], b=["груз терминал"])
    blocks = [block("block-solo", "solo"), block("block-ab", "a", "b")]
    order = [sections["solo"][0], sections["a"][0], sections["b"][0]]
    (place,) = split.seat(["multi-doc"], order, blocks, texts, every_token(texts), None)
    assert place["seed"] == sections["a"][0] and place["partner"] == sections["b"][0]
    assert place["block_id"] == "block-ab"


def test_the_partner_is_the_most_similar_section_of_the_other_documents() -> None:
    texts, sections = corpus(
        a=["груз весы склад", "ещё один раздел про весы"],
        b=["отпуск заявление кадры", "груз весы терминал"],
        c=["груз весы склад"],
    )
    blocks = [block("block-ab", "a", "b"), block("block-c", "c")]
    order = [
        sections["a"][0],
        sections["b"][0],
        sections["b"][1],
        sections["a"][1],
        sections["c"][0],
    ]
    (place,) = split.seat(["multi-doc"], order, blocks, texts, every_token(texts), None)
    # Not its own document's section, not the identical text of another block.
    assert place["seed"] == sections["a"][0] and place["partner"] == sections["b"][1]


def test_a_pair_of_sections_serves_one_position() -> None:
    texts, sections = corpus(a=["груз весы склад"], b=["груз весы терминал"])
    order = [sections["a"][0], sections["b"][0]]
    first, second = split.seat(
        ["multi-doc", "multi-doc"],
        order,
        [block("block-ab", "a", "b")],
        texts,
        every_token(texts),
        None,
    )
    assert first["seed"] == sections["a"][0] and first["partner"] == sections["b"][0]
    # The only partner of the section left is the seed of the first position.
    assert second["seed"] is None and second["partner"] is None and second["block_id"] is None


def test_aggregation_needs_three_list_items_in_the_seed_section() -> None:
    texts, sections = corpus(
        a=[PROSE.format(word="груз"), ITEMS.format(word="груз")], b=[PROSE.format(word="почту")]
    )
    order = [sections["a"][0], sections["b"][0], sections["a"][1]]
    blocks = [block("block-ab", "a", "b")]
    idf = every_token(texts)
    (place,) = split.seat(["aggregation"], order, blocks, texts, idf, None)
    assert place["seed"] == sections["a"][1] and place["partner"] == sections["b"][0]
    # The sections passed over stay free, and so does the pair the list section did not take.
    places = split.seat(["aggregation", "multi-doc", "single-doc"], order, blocks, texts, idf, None)
    assert [place["seed"] for place in places] == [
        sections["a"][1],
        sections["a"][0],
        sections["b"][0],
    ]


def test_the_cap_passes_over_a_block_that_holds_its_share() -> None:
    texts, sections = corpus(a=["первый", "второй", "третий"], b=["четвёртый"])
    blocks = [block("block-a", "a"), block("block-b", "b")]
    order = [sections["a"][0], sections["b"][0], sections["a"][1], sections["a"][2]]
    sequence = ["single-doc"] * 3
    idf = every_token(texts)
    capped = split.seat(sequence, order, blocks, texts, idf, 1)
    assert [place["seed"] for place in capped] == [sections["a"][0], sections["b"][0], None]
    free = split.seat(sequence, order, blocks, texts, idf, None)
    assert [place["seed"] for place in free] == order[:3]


def test_a_replacement_takes_the_first_section_that_was_the_seed_of_no_draft() -> None:
    texts, sections = corpus(a=["первый", "второй", "третий", "четвёртый"])
    order, blocks, idf = sections["a"], [block("block-a", "a")], every_token(texts)
    positions = split.seat(
        ["single-doc", "needs-refusal/clarification"], order, blocks, texts, idf, None
    )
    assert [place["seed"] for place in positions] == order[:2]
    # The section of the dropped draft is not taken again, and neither is that of the kept one.
    (place,) = split.reseat(
        positions, {1: "dropped", 2: "confirmed"}, order, blocks, texts, idf, None
    )
    assert place == {
        "position": 1,
        "primary_class": "single-doc",
        "block_id": "block-a",
        "seed": order[2],
        "partner": None,
    }
    # In ascending number, each on the state the replacement before it left; the class is kept.
    first, second = split.reseat(
        positions[::-1], {2: "dropped", 1: "dropped"}, order, blocks, texts, idf, None
    )
    assert (first["position"], first["seed"]) == (1, order[2])
    assert (second["position"], second["seed"]) == (2, order[3])
    assert second["primary_class"] == "needs-refusal/clarification"
    assert (
        split.reseat(positions, {1: "confirmed", 2: "confirmed"}, order, blocks, texts, idf, None)
        == []
    )


def test_a_position_that_had_no_draft_bars_nothing_and_is_not_replaced() -> None:
    texts, sections = corpus(a=["первый", "второй", "третий"])
    order, blocks, idf = sections["a"], [block("block-a", "a")], every_token(texts)
    positions = split.seat(["single-doc"] * 2, order, blocks, texts, idf, None)
    (place,) = split.reseat(positions, {1: "empty", 2: "dropped"}, order, blocks, texts, idf, None)
    # The section of position 1 was the seed of no draft: the replacement of position 2 takes it.
    assert (place["position"], place["seed"]) == (2, order[0])


def test_a_replacement_passes_the_test_of_its_class_and_no_used_pair_serves_again() -> None:
    texts, sections = corpus(a=["груз весы склад", "груз весы ангар"], b=["груз весы терминал"])
    order = [sections["a"][0], sections["b"][0], sections["a"][1]]
    blocks, idf = [block("block-ab", "a", "b")], every_token(texts)
    positions = split.seat(["multi-doc"], order, blocks, texts, idf, None)
    assert positions[0]["seed"] == sections["a"][0] and positions[0]["partner"] == sections["b"][0]
    (place,) = split.reseat(positions, {1: "dropped"}, order, blocks, texts, idf, None)
    # b0 would take a0 for its partner, the pair of the dropped draft; a1 takes b0: the partner
    # is looked for among all sections of the other document, a partner of a draft included.
    assert place["seed"] == sections["a"][1] and place["partner"] == sections["b"][0]
    # A second drop finds no pair left, and the place stays empty.
    seated = [*positions, {**place, "position": 2}]
    (empty,) = split.reseat(seated, {1: "confirmed", 2: "dropped"}, order, blocks, texts, idf, None)
    assert (empty["position"], empty["seed"], empty["partner"], empty["block_id"]) == (
        2,
        None,
        None,
        None,
    )


def test_the_cap_counts_confirmed_drafts_and_replacements_and_no_dropped_draft() -> None:
    texts, sections = corpus(a=["первый", "второй", "третий", "четвёртый"], b=["пятый", "шестой"])
    a, b = sections["a"], sections["b"]
    blocks, idf = [block("block-a", "a"), block("block-b", "b")], every_token(texts)
    order = [a[0], b[0], a[1], a[2], a[3], b[1]]
    positions = split.seat(["single-doc"] * 3, order, blocks, texts, idf, 2)
    assert [place["seed"] for place in positions] == [a[0], b[0], a[1]]
    # Block a holds one confirmed draft and one dropped: the dropped one leaves its seat free.
    (place,) = split.reseat(
        positions, {1: "dropped", 2: "confirmed", 3: "confirmed"}, order, blocks, texts, idf, 2
    )
    assert place["seed"] == a[2] and place["block_id"] == "block-a"
    # The replacement of position 1 fills block a, and that of position 2 is passed on to b.
    first, second = split.reseat(
        positions, {1: "dropped", 2: "dropped", 3: "confirmed"}, order, blocks, texts, idf, 2
    )
    assert (first["seed"], second["seed"]) == (a[2], b[1])
    # Without a cap the order alone decides.
    first, second = split.reseat(
        positions, {1: "dropped", 2: "dropped", 3: "confirmed"}, order, blocks, texts, idf, None
    )
    assert (first["seed"], second["seed"]) == (a[2], a[3])


@pytest.mark.parametrize(
    "outcomes",
    [{1: "dropped"}, {1: "dropped", 2: "confirmed", 3: "confirmed"}, {1: "dropped", 2: "kept"}],
)
def test_the_outcomes_are_those_of_the_seated_positions(outcomes: dict[int, str]) -> None:
    texts, sections = corpus(a=["первый", "второй"])
    order, blocks, idf = sections["a"], [block("block-a", "a")], every_token(texts)
    positions = split.seat(["single-doc"] * 3, order, blocks, texts, idf, None)
    assert positions[2]["seed"] is None
    with pytest.raises(ValueError, match="not those of the seated positions"):
        split.reseat(positions, outcomes, order, blocks, texts, idf, None)


def synthetic() -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]]]:
    words = {
        "a1": ["груз", "багаж"],
        "a2": ["почту", "посылку"],
        "b": ["контейнер", "поддон"],
        "c": ["животных", "растения"],
        "x": ["лекарства", "вакцины"],
        "y": ["запчасти", "двигатель"],
    }
    texts, sections = corpus(
        **{
            name: [PROSE.format(word=first), ITEMS.format(word=second)]
            for name, (first, second) in words.items()
        }
    )
    families = {"family-a": ["a1", "a2"], "family-b": ["b"], "family-c": ["c"]}
    reserve = {"family-x": ["x"], "family-y": ["y"]}
    register = {
        "families": [
            {"family_id": family, "members": [{"source_id": f"{name}.md"} for name in names]}
            for family, names in {**families, **reserve}.items()
        ],
        "holdout_reserve_families": sorted(reserve),
    }
    pilot = [
        {
            "case_id": "PILOT-1",
            "documents": ["a1.md"],
            "seed_selected_source_section": sections["a1"][0],
            "partner_sections": [sections["a2"][0]],
        }
    ]
    return texts, register, pilot


def test_the_build_keeps_the_splits_apart_and_the_pilot_sections_out() -> None:
    texts, register, pilot = synthetic()
    built = split.build(texts, register, pilot)
    assert built["version"] == split.VERSION and built["seed"] == split.SEED
    assert built["rules"] == split.RULES
    assert built["frame_sections"] == {"eligible": 12, "used_by_pilot": 2}
    development, holdout = built["splits"]["development"], built["splits"]["holdout"]
    assert (development["families"], development["documents"], development["frame_sections"]) == (
        3,
        4,
        6,
    )
    assert (holdout["families"], holdout["documents"], holdout["frame_sections"]) == (2, 2, 4)
    assert {
        tuple(b["documents"]): (b["basis"], b["frame_sections"], b["pilot_cases"])
        for b in development["blocks"]
    } == {
        ("a1.md", "a2.md"): ("family", 2, 1),
        ("b.md", "c.md"): ("pair", 4, 0),
    }
    assert [(b["documents"], b["basis"], b["pilot_cases"]) for b in holdout["blocks"]] == [
        (["x.md", "y.md"], "pair", 0)
    ]
    used = {
        split.key(s)
        for s in (pilot[0]["seed_selected_source_section"], *pilot[0]["partner_sections"])
    }
    for name, summary, documents in (
        ("development", development, {"a1.md", "a2.md", "b.md", "c.md"}),
        ("holdout", holdout, {"x.md", "y.md"}),
    ):
        seated = [place for place in summary["positions"] if place["seed"] is not None]
        named = [s for place in seated for s in (place["seed"], place["partner"]) if s is not None]
        assert {section["source_id"] for section in named} <= documents, name
        assert not used & {split.key(section) for section in named}, name
        assert not used & {tuple(entry) for entry in summary["order"]}, name
        seeds = [split.key(place["seed"]) for place in seated]
        assert len(seeds) == len(set(seeds)) and set(seeds) <= {tuple(e) for e in summary["order"]}
        assert summary["seated"] == dict(Counter(place["primary_class"] for place in seated))
        assert summary["empty_positions"] == [
            p["position"] for p in summary["positions"] if p["seed"] is None
        ]
    # The holdout has four frame sections in one block: four positions, one of each class.
    assert holdout["quotas"] == dict.fromkeys(split.CLASSES, 1)
    assert len(holdout["positions"]) == 4 and holdout["clusters"] == 1
    assert holdout["cases"] == 4 - len(holdout["empty_positions"])
    # Development asks for its registered 30 and seats what six sections allow.
    assert development["quotas"] == split.DEV_NEW and len(development["positions"]) == 30
    assert (
        development["cases"]
        == len(development["positions"]) - len(development["empty_positions"]) + 1
    )
    assert (
        development["clusters"] == 2 and sum(development["cluster_sizes"]) == development["cases"]
    )


def test_the_build_does_not_depend_on_the_order_of_its_inputs() -> None:
    texts, register, pilot = synthetic()
    shuffled = {name: texts[name] for name in sorted(texts, reverse=True)}
    turned = {**register, "families": register["families"][::-1]}
    assert split.dump(split.build(shuffled, turned, pilot)) == split.dump(
        split.build(texts, register, pilot)
    )


def test_replacements_of_a_built_split_take_what_its_order_has_left() -> None:
    texts, register, pilot = synthetic()
    # The file as it is registered: sections and order as JSON gives them.
    built = json.loads(split.dump(split.build(texts, register, pilot)))
    holdout = built["splits"]["holdout"]
    seated = [place for place in holdout["positions"] if place["seed"] is not None]
    kept = {place["position"]: "confirmed" for place in seated}
    assert split.replacements("holdout", built, texts, kept) == []
    order = [tuple(entry) for entry in holdout["order"]]
    seeds = {split.key(place["seed"]) for place in seated}
    single = next(place for place in seated if place["primary_class"] == "single-doc")
    other = next(place for place in seated if place is not single)

    def replaced(**outcomes: str) -> tuple[str, int] | None:
        given = {**kept, **{int(number[1:]): outcome for number, outcome in outcomes.items()}}
        (place,) = split.replacements("holdout", built, texts, given)
        assert place["position"] == single["position"] and place["primary_class"] == "single-doc"
        return split.key(place["seed"]) if place["seed"] is not None else None

    # A class of one document takes the first section of the order that was no seed, if any.
    free = [entry for entry in order if entry not in seeds]
    assert replaced(**{f"p{single['position']}": "dropped"}) == (free[0] if free else None)
    # A position that had no draft frees its section for the replacement of another.
    freed = [entry for entry in order if entry not in seeds - {split.key(other["seed"])}]
    assert (
        replaced(**{f"p{single['position']}": "dropped", f"p{other['position']}": "empty"})
        == freed[0]
    )
    with pytest.raises(ValueError, match="the registered order is not of this corpus"):
        split.replacements("holdout", built, {**texts, "x.md": "## Раздел 1\nкоротко\n"}, kept)


def test_a_block_whose_sections_were_all_seeds_gives_no_replacement() -> None:
    texts, sections = corpus(a=["первый", "второй"])
    order, blocks, idf = sections["a"], [block("block-a", "a")], every_token(texts)
    positions = split.seat(["single-doc"] * 2, order, blocks, texts, idf, None)
    (place,) = split.reseat(
        positions, {1: "confirmed", 2: "dropped"}, order, blocks, texts, idf, None
    )
    assert place == {
        "position": 2,
        "primary_class": "single-doc",
        "block_id": None,
        "seed": None,
        "partner": None,
    }


def registered() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(split.REGISTERED.read_text(encoding="utf-8"))
    return value


def test_the_registered_split_names_the_inputs_it_was_built_from() -> None:
    evaluation = split.ROOT / "evaluation"
    manifest = json.loads(
        (evaluation / "aircargo_corpus.manifest.json").read_text(encoding="utf-8")
    )
    assert registered()["inputs"] == {
        "corpus_sha256": manifest["corpus_sha256"],
        "corpus_manifest_sha256": split.sha256(evaluation / "aircargo_corpus.manifest.json"),
        "families_sha256": split.sha256(evaluation / "document_families.json"),
        "pilot_verified_sha256": split.sha256(evaluation / "devset_pilot_verified.jsonl"),
    }


def test_the_registered_split_follows_its_rules() -> None:
    value = registered()
    assert (value["version"], value["seed"], value["rules"]) == (
        split.VERSION,
        split.SEED,
        split.RULES,
    )
    evaluation = split.ROOT / "evaluation"
    register = json.loads((evaluation / "document_families.json").read_text(encoding="utf-8"))
    pilot = [
        json.loads(line)
        for line in (evaluation / "devset_pilot_verified.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    reserve = set(register["holdout_reserve_families"])
    family_of = {m["source_id"]: f["family_id"] for f in register["families"] for m in f["members"]}
    used = {
        split.key(section)
        for case in pilot
        for section in [case["seed_selected_source_section"], *case["partner_sections"]]
    }
    assert value["frame_sections"] == {"eligible": 982, "used_by_pilot": len(used)}
    seen: set[str] = set()
    for name, summary in value["splits"].items():
        documents = {document for b in summary["blocks"] for document in b["documents"]}
        assert (
            sum(len(b["documents"]) for b in summary["blocks"])
            == len(documents)
            == summary["documents"]
        )
        assert not documents & seen
        seen |= documents
        assert all(
            (family_of[document] in reserve) == (name == "holdout") for document in documents
        )
        block_of = {
            document: b["block_id"] for b in summary["blocks"] for document in b["documents"]
        }
        order = [tuple(entry) for entry in summary["order"]]
        assert len(order) == len(set(order)) == summary["frame_sections"] and not used & set(order)
        assert {document for document, _ in order} <= documents
        assert summary["empty_positions"] == []
        assert [place["primary_class"] for place in summary["positions"]] == split.class_sequence(
            summary["quotas"]
        )
        seeds = [split.key(place["seed"]) for place in summary["positions"]]
        assert len(seeds) == len(set(seeds)) and set(seeds) <= set(order)
        pairs = set()
        for place in summary["positions"]:
            assert place["block_id"] == block_of[place["seed"]["source_id"]]
            several = place["primary_class"] in split.SEVERAL_DOCUMENTS
            assert (place["partner"] is not None) == several
            if several:
                assert block_of[place["partner"]["source_id"]] == place["block_id"]
                assert place["partner"]["source_id"] != place["seed"]["source_id"]
                assert split.key(place["partner"]) in order
                pairs.add(frozenset((split.key(place["seed"]), split.key(place["partner"]))))
        assert len(pairs) == sum(
            p["primary_class"] in split.SEVERAL_DOCUMENTS for p in summary["positions"]
        )
    assert len(seen) == len(family_of) == 201

    development, holdout = value["splits"]["development"], value["splits"]["holdout"]
    assert development["quotas"] == split.DEV_NEW
    assert (development["cases"], development["clusters"]) == (len(pilot) + 30, 37)
    assert development["cluster_sizes"] == [5, 4, 3, 3, *[2] * 12, *[1] * 21]
    assert sum(b["pilot_cases"] for b in holdout["blocks"]) == 0
    assert (holdout["families"], holdout["documents"]) == (len(reserve), 36)
    per_block = Counter(place["block_id"] for place in holdout["positions"])
    assert max(per_block.values()) == split.HOLDOUT_ROUNDS
    assert per_block == {
        b["block_id"]: min(split.HOLDOUT_ROUNDS, b["frame_sections"]) for b in holdout["blocks"]
    }
    assert holdout["quotas"] == split.quotas(split.HOLDOUT_SHARES, 64)
    assert (holdout["cases"], holdout["clusters"]) == (64, 18)
    assert holdout["cluster_sizes"] == [*[4] * 12, *[3] * 4, *[2] * 2]


def test_the_registered_split_is_a_rebuild_of_its_inputs() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    assert split.dump(split.rebuilt()) == split.REGISTERED.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["development", "holdout"])
def test_replacements_on_the_registered_split_follow_the_rule(name: str) -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    texts = split.load_inputs()[0]
    value = registered()
    positions = value["splits"][name]["positions"]
    dropped = {place["position"] for place in positions if place["position"] % 5 == 0}
    outcomes = {
        place["position"]: "dropped" if place["position"] in dropped else "confirmed"
        for place in positions
    }
    places = split.replacements(name, value, texts, outcomes)
    assert [place["position"] for place in places] == sorted(dropped)
    by_number = {place["position"]: place for place in positions}
    order = {tuple(entry) for entry in value["splits"][name]["order"]}
    seeds = {split.key(place["seed"]) for place in positions}
    pairs = {
        frozenset((split.key(place["seed"]), split.key(place["partner"])))
        for place in positions
        if place["partner"] is not None
    }
    per_block = Counter(by_number[number]["block_id"] for number in set(by_number) - dropped)
    seated = [place for place in places if place["seed"] is not None]
    for place in seated:
        assert place["primary_class"] == by_number[place["position"]]["primary_class"]
        assert split.key(place["seed"]) in order - seeds
        seeds.add(split.key(place["seed"]))
        several = place["primary_class"] in split.SEVERAL_DOCUMENTS
        assert (place["partner"] is not None) == several
        if several:
            pair = frozenset((split.key(place["seed"]), split.key(place["partner"])))
            assert pair not in pairs and place["partner"]["source_id"] != place["seed"]["source_id"]
            pairs.add(pair)
        per_block[place["block_id"]] += 1
    if name == "holdout":
        assert max(per_block.values()) <= split.HOLDOUT_ROUNDS
        # Twelve drops free twelve seats; the tests of the classes leave four of them empty.
        assert [place["position"] for place in places if place["seed"] is None] == [35, 50, 55, 60]
    else:
        assert len(seated) == len(dropped) == 6
    assert split.main([]) == 0
