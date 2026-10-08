"""The pilot on the external bases: the measure on two small bases whose runs are written by hand."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from evaluation import external_bases as bases
from evaluation import external_gold as gold
from evaluation import external_parts as parts
from evaluation import power
from scripts import corpus_manifest, external_base, variance_pilot
from scripts import external_pilot as pilot
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from tests import test_external_parts as small

PILOT_RULES = {
    "conditionalqa": {"part": "tuning", "stratum": "primary", "documents": 2, "per_document": 2},
    "wixqa": {"part": "tuning", "questions": 3},
}
BODIES = ("Alpha {n} one.", "Alpha {n} two.", "Beta {n} one. Beta {n} two.", "Gamma {n} one.")
SPLIT, TWO = "split", "two"
WIX = ("d.md", "e.md", "f.md", "g.md")
BEFORE_GRADING = {
    "transform": 1500.0,
    "embed": 250.0,
    "pools": 300.0,
    "rerank": 900.0,
    "total": 1200.0,
    "expansion": 2.0,
    "retrieve": 1300.0,
}
GRADE = (10_000.0, 20_000.0, 30_000.0, 40_000.0)
# What each arm had for a question of ConditionalQA, by the place of its page in the selection
# and its kind. Chunks are numbered inside the page; a context document is (seed, before, after).
CONTROL_PLAN = {
    (0, SPLIT): {
        "vector": (0, 1),
        "bm25": (),
        "ranked": (1,),
        "expanded": ((1, (0,), ()),),
        "sent": ((1, (0,), ()),),
    },
    (0, TWO): {
        "vector": (0,),
        "bm25": (3,),
        "ranked": (0, 3),
        "expanded": ((0, (), ()), (3, (), ())),
        "sent": ((0, (), ()),),
    },
    (1, SPLIT): {
        "vector": (1, 2),
        "bm25": (2,),
        "ranked": (1,),
        "expanded": ((1, (), (2,)),),
        "sent": ((1, (), (2,)),),
    },
    (1, TWO): {
        "vector": (0,),
        "bm25": (),
        "ranked": (0,),
        "expanded": ((0, (), ()),),
        "sent": ((0, (), ()),),
    },
}
PLANS = {
    "control": CONTROL_PLAN,
    "pool30": {
        **CONTROL_PLAN,
        (0, SPLIT): {
            "vector": (0, 1, 2),
            "bm25": (),
            "ranked": (1, 2),
            "expanded": ((1, (), ()), (2, (), ())),
            "sent": ((1, (), ()), (2, (), ())),
        },
        (1, SPLIT): {
            "vector": (1, 2, 3),
            "bm25": (2,),
            "ranked": (3,),
            "expanded": ((3, (), ()),),
            "sent": ((3, (), ()),),
        },
    },
}
# The same for WixQA, by the gold articles of the question; chunk k is the one of WIX[k].
WIX_PLANS = {
    "control": {
        ("d.md",): {"vector": (3,), "bm25": (0,), "ranked": (3,)},
        ("d.md", "e.md"): {"vector": (0, 1, 3), "bm25": (), "ranked": (1, 3)},
        ("f.md",): {"vector": (3,), "bm25": (), "ranked": (3,)},
    },
    "pool30": {
        ("d.md",): {"vector": (3, 0), "bm25": (0,), "ranked": (0,)},
        ("d.md", "e.md"): {"vector": (0, 1, 3), "bm25": (), "ranked": (3,)},
        ("f.md",): {"vector": (3, 2), "bm25": (), "ranked": (2,)},
    },
}


def page(number: int) -> str:
    return f"# Page {number}\n\n" + " ".join(body.format(n=number) for body in BODIES) + "\n"


def conditional_cases() -> list[dict]:
    """Six pages with two primary questions each: one element two chunks hold, and two elements."""
    cases = []
    for number in range(6):
        name = f"page-{number}.md"
        source = gold.Source.read(name, page(number))

        def group(fragment: str, section: int, source=source, name=name, number=number) -> dict:
            ((start, end),) = source.occurrences(fragment.format(n=number))
            place = {"source_id": name, "start": start, "end": end, "section": section, "part": 0}
            return {"alternatives": [place]}

        kinds = (
            [group("Alpha {n} two. Beta {n} one.", 1)],
            [group("Alpha {n} one.", 1), group("Gamma {n} one.", 3)],
        )
        for position, groups in enumerate(kinds):
            cases.append(
                {
                    "case_id": f"conditionalqa-train-{2 * number + position}",
                    "base": "conditionalqa",
                    "stratum": "answerable",
                    "query": f"scenario and question {2 * number + position}",
                    "document": name,
                    "gold_sources": [name],
                    "evidence_groups": groups,
                    "unresolved_evidence": 0,
                }
            )
    return cases


CASES = {
    "conditionalqa": conditional_cases(),
    "wixqa": [
        small._wix("expertwritten", 0, "a.md"),
        small._wix("simulated", 0, "d.md"),
        small._wix("simulated", 1, "d.md", "e.md"),
        small._wix("simulated", 2, "f.md"),
    ],
    "multihoprag": small.MULTIHOPRAG,
}
DOCUMENTS = {
    "conditionalqa": {f"page-{number}.md": page(number) for number in range(6)},
    "wixqa": {name: f"# {name}\n\ntext of {name}\n" for name in WIX},
}


def chunk_texts(base: str) -> list[tuple[str, str]]:
    if base == "wixqa":
        return [(name, f"text of {name}") for name in WIX]
    return [(f"page-{number}.md", body.format(n=number)) for number in range(6) for body in BODIES]


def kind(case: dict) -> str:
    return SPLIT if len(case["evidence_groups"]) == 1 else TWO


def context(chunks: list[dict], seed: int, before: tuple[int, ...], after: tuple[int, ...]) -> dict:
    """A document of a context as the collector stores it: a seed joined with neighbours."""

    def body(position: int) -> str:
        return gold.strip_header(chunks[position]["page_content"]).strip()

    text = (
        "".join(body(position) + "\n\n" for position in before)
        + chunks[seed]["page_content"]
        + "".join("\n\n" + body(position) for position in after)
    )
    return {
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "metadata": {**chunks[seed]["metadata"], "chunk_index": seed},
    }


def conditional_row(world: SimpleNamespace, arm: str, case: dict, position: int) -> dict:
    chunks = world.chunks["conditionalqa"]
    first = 4 * int(case["document"].removeprefix("page-").removesuffix(".md"))
    plan = PLANS[arm][(world.pages.index(case["document"]), kind(case))]

    def documents(entries: tuple) -> list[dict]:
        return [
            context(
                chunks,
                first + seed,
                tuple(first + k for k in before),
                tuple(first + k for k in after),
            )
            for seed, before, after in entries
        ]

    vector = [first + k for k in plan["vector"]]
    lexical = [first + k for k in plan["bm25"]]
    return {
        "status": "ok",
        "vector": vector,
        "bm25": lexical,
        "pool": list(dict.fromkeys([*vector, *lexical])),
        "ranked": [first + k for k in plan["ranked"]],
        "expanded_documents": documents(plan["expanded"]),
        "documents": documents(plan["sent"]),
        "timings_ms": {**BEFORE_GRADING, "grade": GRADE[position]},
    }


def wix_row(world: SimpleNamespace, arm: str, case: dict, position: int) -> dict:
    plan = WIX_PLANS[arm][tuple(case["gold_sources"])]
    return {
        "status": "ok",
        "vector": list(plan["vector"]),
        "bm25": list(plan["bm25"]),
        "pool": list(dict.fromkeys([*plan["vector"], *plan["bm25"]])),
        "ranked": list(plan["ranked"]),
        "timings_ms": dict(BEFORE_GRADING),
    }


def start(world: SimpleNamespace, base: str, arm: str, name: str | None = None, **changes) -> Path:
    """Register a run of an arm as the collector does; the stage records are written apart."""
    run = world.root / "runs" / (name or f"{base}-{arm}")
    args = SimpleNamespace(
        run=run,
        index=world.index[base],
        checkpoint=world.checkpoint[base],
        code_sha="b" * 40,
        resume=False,
        base=base,
        base_dir=world.folder[base],
        selection="pilot",
        task="plan 1.6 pilot",
        settings=[f"{key}={value}" for key, value in pilot.ARMS[arm].items()],
    )
    for key, value in changes.items():
        setattr(args, key, value)
    baseline.prepare(args)
    return run


def record(world: SimpleNamespace, base: str, arm: str, run: Path, **replaced: dict) -> None:
    """Write the last stage record of every question of a run; ``replaced`` gives others by id."""
    manifest = parity.read(run / "manifest.json")
    identity = parity.digest(manifest)
    row = conditional_row if base == "conditionalqa" else wix_row
    by_id = {case["case_id"]: case for case in CASES[base]}
    for position, listed in enumerate(manifest["cases"]):
        case_id = listed["case_id"]
        result = replaced.get(case_id) or row(world, arm, by_id[case_id], position)
        target = run / pilot.BASES[base]["last_stage"] / f"{case_id}.json"
        parity.save_stage(target, {"case_id": case_id, **result}, identity)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Two small converted bases, their registrations, their indexes and the two arms of each."""
    monkeypatch.setattr(parts, "PILOT", PILOT_RULES)
    monkeypatch.setattr(parity, "runtime_identity", lambda: {"platform": "fixture"})
    monkeypatch.chdir(tmp_path)
    files = {base: small._file(cases) for base, cases in CASES.items()}
    converted = json.loads(bases.REGISTRATION.read_text(encoding="utf-8"))
    for base, data in files.items():
        converted["bases"][base]["converted"]["cases_sha256"] = bases.sha256(data)
    registered = parts.build(CASES, {base: bases.sha256(data) for base, data in files.items()})
    it = SimpleNamespace(
        root=tmp_path, folder={}, index={}, checkpoint={}, chunks={}, registered=registered
    )
    for base, documents in DOCUMENTS.items():
        folder = tmp_path / "data" / base
        (folder / "corpus").mkdir(parents=True)
        for name, markdown in documents.items():
            (folder / "corpus" / name).write_bytes(markdown.encode("utf-8"))
        corpus = corpus_manifest.build_manifest(folder / "corpus", name=f"ext_{base}")
        corpus_manifest.write_manifest(folder / "corpus.manifest.json", corpus)
        converted["bases"][base]["converted"]["corpus_sha256"] = corpus["corpus_sha256"]
        (folder / "cases.jsonl").write_bytes(files[base])
        revision = {entry["name"]: entry["sha256"] for entry in corpus["files"]}
        chunks = [
            {
                "page_content": f"[Контекст: Из документа {name}]\n{body}",
                "metadata": {"source": name, "content_hash": revision[name], "h1": name},
            }
            for name, body in chunk_texts(base)
        ]
        payload = {"tenant_id": f"ext_{base}", "chunks": chunks}
        (folder / "chunks.json.gz").write_bytes(gzip.compress(json.dumps(payload).encode()))
        checkpoint = tmp_path / f"{base}.npz"
        checkpoint.write_bytes(base.encode())
        receipt = {
            "corpus_sha256": parity.file_sha(folder / "chunks.json.gz"),
            "checkpoint_sha256": parity.file_sha(checkpoint),
            "collection_name": f"rag_docs_ext_{base}",
            "embedder_manifest": {"revision": "a" * 40},
        }
        parity.write_new(tmp_path / f"{base}-index" / "index-receipt.json", receipt)
        it.folder[base], it.index[base] = folder, tmp_path / f"{base}-index"
        it.checkpoint[base], it.chunks[base] = checkpoint, chunks
    (tmp_path / "bases.json").write_text(json.dumps(converted), encoding="utf-8")
    (tmp_path / "parts.json").write_bytes(parts.dump(registered))
    monkeypatch.setattr(bases, "REGISTRATION", tmp_path / "bases.json")
    monkeypatch.setattr(parts, "REGISTRATION", tmp_path / "parts.json")
    it.runs = {}
    it.ids = {}
    for base in DOCUMENTS:
        external_base.select_step(base, it.folder[base], "pilot")
        it.ids[base] = registered["selections"][base]["pilot"]["case_ids"]
    by_id = {case["case_id"]: case for case in CASES["conditionalqa"]}
    it.pages = list(dict.fromkeys(by_id[cid]["document"] for cid in it.ids["conditionalqa"]))
    for base in DOCUMENTS:
        it.runs[base] = {}
        for arm in pilot.ARMS:
            it.runs[base][arm] = start(it, base, arm)
            record(it, base, arm, it.runs[base][arm])
    return it


def measured(world: SimpleNamespace, base: str) -> dict[str, Any]:
    return pilot.measure(base, world.folder[base], world.runs[base])


def of(world: SimpleNamespace, report: dict, place: int, which: str, arm: str) -> dict:
    """The record of the ConditionalQA question of that page and kind in one arm."""
    by_id = {case["case_id"]: case for case in CASES["conditionalqa"]}
    for entry in report["per_case"]:
        case = by_id[entry["case_id"]]
        if world.pages.index(case["document"]) == place and kind(case) == which:
            return entry["arms"][arm]
    raise AssertionError("no such question in the selection")


def coverage(record: dict) -> dict[str, tuple[float, float]]:
    return {
        point: (values["all_evidence_coverage"], values["evidence_recall"])
        for point, values in record["points"].items()
    }


def test_the_arms_are_the_control_and_pool30_of_the_variance_pilot() -> None:
    assert pilot.ARMS == {name: variance_pilot.ARMS[name] for name in ("control", "pool30")}
    assert pilot.CONTROL == variance_pilot.CONTROL
    assert not set(pilot.BUDGET) & {key for moved in pilot.ARMS.values() for key in moved}
    assert set(pilot.BASES) == set(parts.PILOT) and pilot.SELECTION == "pilot"


def test_conditionalqa_is_read_by_ranges_at_six_points(world: SimpleNamespace) -> None:
    report = measured(world, "conditionalqa")
    assert report["match_rule"] == "external-gold/range-coverage-v1" and report["top"] == 5
    assert report["primary"] == {"point": "sent", "metric": "all_evidence_coverage"}
    assert [entry["case_id"] for entry in report["per_case"]] == world.ids["conditionalqa"]
    # An element that two chunks hold together is found only where both are present, and a
    # neighbour joined by parent expansion counts as present.
    assert coverage(of(world, report, 0, SPLIT, "control")) == {
        point: (0.0, 0.0) for point in ("vector", "bm25", "pool", "ranked", "expanded", "sent")
    }
    assert coverage(of(world, report, 1, SPLIT, "control")) == {
        "vector": (1.0, 1.0),
        "bm25": (0.0, 0.0),
        "pool": (1.0, 1.0),
        "ranked": (0.0, 0.0),
        "expanded": (1.0, 1.0),
        "sent": (1.0, 1.0),
    }
    # Two elements: each lane holds one, the pool both, and grading drops one.
    assert coverage(of(world, report, 0, TWO, "control")) == {
        "vector": (0.0, 0.5),
        "bm25": (0.0, 0.5),
        "pool": (1.0, 1.0),
        "ranked": (1.0, 1.0),
        "expanded": (1.0, 1.0),
        "sent": (0.0, 0.5),
    }
    assert coverage(of(world, report, 1, TWO, "control"))["sent"] == (0.0, 0.5)
    assert coverage(of(world, report, 0, SPLIT, "pool30"))["sent"] == (1.0, 1.0)
    assert coverage(of(world, report, 1, SPLIT, "pool30")) == {
        "vector": (1.0, 1.0),
        "bm25": (0.0, 0.0),
        "pool": (1.0, 1.0),
        "ranked": (0.0, 0.0),
        "expanded": (0.0, 0.0),
        "sent": (0.0, 0.0),
    }
    means = {
        arm: {
            point: values["all_evidence_coverage"]
            for point, values in report["arms"][arm]["points"].items()
        }
        for arm in pilot.ARMS
    }
    assert means["control"] == {
        "vector": 0.25,
        "bm25": 0.0,
        "pool": 0.5,
        "ranked": 0.25,
        "expanded": 0.5,
        "sent": 0.25,
    }
    assert means["pool30"] == {
        "vector": 0.5,
        "bm25": 0.0,
        "pool": 0.75,
        "ranked": 0.5,
        "expanded": 0.5,
        "sent": 0.25,
    }
    assert report["arms"]["control"]["points"]["sent"]["evidence_recall"] == 0.5
    assert report["gold_in_index"] == {"cases": 4, "of": 4}
    assert all(entry["gold_in_index"] for entry in report["per_case"])
    assert report["chunks_without_a_place"] == 0
    # The questions with two elements have them in two sections: a stratum of its own, whose
    # pairs did not move here.
    assert report["strata"] == {"several_sections": 2}
    stratum = report["pairs"]["pool30"]["primary_by_stratum"]["several_sections"]
    assert (stratum["n"], stratum["clusters"], stratum["variance"]) == (2, 2, 0.0)


def test_paired_differences_of_conditionalqa_by_document(world: SimpleNamespace) -> None:
    report = measured(world, "conditionalqa")
    assert report["clusters"] == {"unit": "document", "count": 2, "sizes": [2, 2]}
    assert {entry["cluster"] for entry in report["per_case"]} == {0, 1}
    pairs = report["pairs"]["pool30"]
    assert pairs["pairs"] == 4 and pairs["lost"] == []
    primary = pairs["primary"]
    assert primary == {**pairs["points"]["sent"]["all_evidence_coverage"], **primary}
    assert (primary["point"], primary["metric"]) == ("sent", "all_evidence_coverage")
    assert primary["used"] is True and primary["not_used_because"] is None
    # +1 and 0 on the first page, −1 and 0 on the second.
    assert primary["n"] == 4 and primary["clusters"] == 2 and primary["cluster_sizes"] == [2, 2]
    assert primary["mean"] == 0.0
    assert primary["variance"] == pytest.approx(2 / 3)
    assert primary["effective_variance"] == pytest.approx(1.0)
    assert primary["design_effect"] == pytest.approx(1.5)
    assert primary["differing_pairs"] == 2 and primary["nonzero_clusters"] == 2
    assert pairs["points"]["pool"]["all_evidence_coverage"]["mean"] == 0.25
    assert pairs["points"]["bm25"]["evidence_recall"]["variance"] == 0.0
    assert pairs["chunks_differ"] == {
        "vector": 2,
        "bm25": 0,
        "pool": 2,
        "ranked": 2,
        "expanded": 2,
        "sent": 2,
    }


def test_sizes_and_seconds_of_every_arm(world: SimpleNamespace) -> None:
    report = measured(world, "conditionalqa")
    control = report["arms"]["control"]
    assert control["cases"] == control["measured"] == 4 and control["excluded"] == {}
    assert control["seconds"]["grade"] == {
        "n": 4,
        "mean": 25.0,
        "p50": 25.0,
        "p95": pytest.approx(38.5),
        "total": 100.0,
    }
    assert control["seconds"]["transform"]["mean"] == 1.5
    assert sorted(control["seconds"]) == sorted([*BEFORE_GRADING, "grade"])
    assert control["candidates"]["pool"]["mean"] == 1.75
    assert report["arms"]["pool30"]["candidates"]["pool"]["mean"] == 2.25
    assert control["sent_documents"]["mean"] == 1.0
    assert report["arms"]["pool30"]["sent_documents"]["mean"] == 1.25
    # The characters of the sent contexts, by arm and as a paired difference.
    chunks = world.chunks["conditionalqa"]
    first = {place: 4 * int(name[5]) for place, name in enumerate(world.pages)}

    def characters(arm: str) -> float:
        return sum(
            len(context(chunks, first[place] + seed, *neighbours(place, before, after))["text"])
            for (place, _), plan in PLANS[arm].items()
            for seed, before, after in plan["sent"]
        )

    def neighbours(place: int, before: tuple, after: tuple) -> tuple[tuple, tuple]:
        return (
            tuple(first[place] + k for k in before),
            tuple(first[place] + k for k in after),
        )

    assert control["sent_characters"]["total"] == characters("control")
    assert report["arms"]["pool30"]["sent_characters"]["total"] == characters("pool30")
    difference = report["pairs"]["pool30"]["sent_characters"]
    assert difference["mean"] * 4 == pytest.approx(characters("pool30") - characters("control"))
    budget = report["provenance"]["context_budget"]
    assert budget == {key: parity.CONFIG[key] for key in pilot.BUDGET}


def test_wixqa_is_read_by_gold_articles_at_the_lanes(world: SimpleNamespace) -> None:
    report = measured(world, "wixqa")
    assert report["primary"] == {"point": "ranked", "metric": "gold_article"}
    by_gold = {
        tuple(case["gold_sources"]): case["case_id"]
        for case in CASES["wixqa"]
        if case["stratum"] == "simulated"
    }
    assert sorted(by_gold.values()) == sorted(world.ids["wixqa"])
    arms = {entry["case_id"]: entry["arms"] for entry in report["per_case"]}
    two = arms[by_gold[("d.md", "e.md")]]
    assert two["control"]["points"] == {
        "vector": {"gold_article": 1.0, "gold_articles": 1.0},
        "bm25": {"gold_article": 0.0, "gold_articles": 0.0},
        "pool": {"gold_article": 1.0, "gold_articles": 1.0},
        "ranked": {"gold_article": 1.0, "gold_articles": 0.5},
    }
    assert two["pool30"]["points"]["ranked"] == {"gold_article": 0.0, "gold_articles": 0.0}
    one = arms[by_gold[("d.md",)]]
    assert one["control"]["points"]["bm25"]["gold_article"] == 1.0
    assert one["control"]["points"]["ranked"]["gold_article"] == 0.0
    assert "sent_characters" not in one["control"] and "grade" not in one["control"]["seconds"]
    assert report["arms"]["control"]["points"]["ranked"]["gold_article"] == pytest.approx(1 / 3)
    assert report["arms"]["pool30"]["points"]["ranked"]["gold_article"] == pytest.approx(2 / 3)
    assert report["arms"]["control"]["points"]["pool"]["gold_article"] == pytest.approx(2 / 3)
    # The two questions that share an article are one cluster.
    assert report["clusters"] == {"unit": "gold-article set", "count": 2, "sizes": [2, 1]}
    primary = report["pairs"]["pool30"]["primary"]
    assert primary["used"] is True
    assert primary["n"] == 3 and primary["clusters"] == 2
    assert primary["mean"] == pytest.approx(1 / 3)
    assert primary["variance"] == pytest.approx(4 / 3)
    assert primary["effective_variance"] == pytest.approx(16 / 27)
    assert report["pairs"]["pool30"]["chunks_differ"] == {
        "vector": 2,
        "bm25": 0,
        "pool": 1,
        "ranked": 3,
    }
    assert report["gold_in_index"] == {"cases": 3, "of": 3}
    # Articles are read by their names: the places of chunks are not needed and not counted.
    assert report["chunks_without_a_place"] is None
    assert report["strata"] == {} and report["pairs"]["pool30"]["primary_by_stratum"] == {}


def test_the_index_ceiling_of_wixqa_is_one_gold_article_with_a_chunk(
    world: SimpleNamespace,
) -> None:
    chunks = world.chunks["wixqa"]
    places = pilot.Places(chunks, None, 200, 2)
    case = {"gold_sources": ["d.md", "absent.md"]}
    assert pilot.reachable("wixqa", case, places) is True
    assert pilot.read_gold("wixqa", case, [0], places) == {
        "gold_article": 1.0,
        "gold_articles": 0.5,
    }
    assert pilot.reachable("wixqa", {"gold_sources": ["absent.md"]}, places) is False


def test_a_chunk_without_a_place_stops_the_measure() -> None:
    name = "page-0.md"
    sources = {name: gold.Source.read(name, page(0))}
    chunks = [
        {"page_content": f"[Контекст: Из документа {name}]\n{body}", "metadata": {"source": name}}
        for body in ("Alpha 0 one.", "A text of no page.")
    ]
    places = pilot.Places(chunks, sources, 200, 2)
    assert places.without_place == 1 and places.places[1] is None
    assert places.by_document([0, 0]) == {name: [places.places[0]]}
    with pytest.raises(ValueError, match="has no place in its document"):
        places.by_document([0, 1])
    assert pilot.Places(chunks, None, 200, 2).without_place is None


def test_what_is_written_holds_no_text_no_document_and_no_path(world: SimpleNamespace) -> None:
    for base in DOCUMENTS:
        text = pilot.dump(measured(world, base))
        for hidden in ("Alpha", "Gamma", "page-", ".md", "text of", "scenario", "how do I"):
            assert hidden not in text, hidden
        assert str(world.root) not in text and world.root.name not in text
        assert all(case_id in text for case_id in world.ids[base])


def test_a_document_that_would_carry_text_of_the_base_is_refused(world: SimpleNamespace) -> None:
    """The measure copies a stage and an error type of a run; neither may be text of the base."""
    lost = world.ids["conditionalqa"][0]
    case = {case["case_id"]: case for case in CASES["conditionalqa"]}[lost]
    for number, leaked in enumerate((f"Error: {case['query']}", case["document"])):
        run = start(world, "conditionalqa", "pool30", f"leak-{number}")
        row = excluded(lost)
        row["exclusion"]["error_type"] = leaked
        record(world, "conditionalqa", "pool30", run, **{lost: row})
        runs = {**world.runs["conditionalqa"], "pool30": run}
        with pytest.raises(ValueError, match="would carry text of the base"):
            pilot.measure("conditionalqa", world.folder["conditionalqa"], runs)
    document = {"a": [{"b": "c"}, ("d", 1)], "e": None}
    assert sorted(pilot.strings(document)) == ["a", "b", "c", "d", "e"]


def test_provenance_names_the_runs_the_base_and_the_measuring_code(world: SimpleNamespace) -> None:
    report = measured(world, "conditionalqa")
    provenance = report["provenance"]
    manifests = {
        arm: parity.read(run / "manifest.json") for arm, run in world.runs["conditionalqa"].items()
    }
    assert provenance["code_sha"] == "b" * 40
    assert provenance["runs"]["pool30"] == {
        "run_sha256": parity.digest(manifests["pool30"]),
        "config_sha256": parity.digest(manifests["pool30"]["config"]),
        "config_overrides": {"retrieval_top_k": 30},
        "task": "plan 1.6 pilot",
    }
    assert provenance["runs"]["control"]["config_overrides"] == {}
    assert provenance["config"] == parity.CONFIG
    pilot_rows = world.registered["selections"]["conditionalqa"]["pilot"]
    assert provenance["base"]["cases_sha256"] == pilot_rows["cases_sha256"]
    assert provenance["base"]["tenant"] == "ext_conditionalqa"
    assert provenance["base"]["selection"] == "pilot" and provenance["base"]["part"] == "tuning"
    assert "directory" not in provenance["base"]
    archive = world.folder["conditionalqa"] / "chunks.json.gz"
    assert provenance["archive_sha256"] == parity.file_sha(archive)
    assert provenance["registrations_of_the_measure"] == {
        "bases.json": parity.file_sha(world.root / "bases.json"),
        "parts.json": parity.file_sha(world.root / "parts.json"),
    }
    assert provenance["registrations_of_the_runs"] == provenance["registrations_of_the_measure"]
    assert set(provenance["measure_code"]) == set(pilot.CODE_FILES)
    assert all((pilot.ROOT / name).is_file() for name in pilot.CODE_FILES)


def excluded(case_id: str) -> dict:
    return {
        "status": "excluded",
        "exclusion": {
            "case_id": case_id,
            "subset": "pilot",
            "stage": "grade",
            "reason": "Grader error invalidates measurement: scenario and question",
            "error_type": "ValueError",
        },
        "timings_ms": dict(BEFORE_GRADING),
    }


def test_a_lost_pair_is_listed_and_too_many_leave_the_variance_unused(
    world: SimpleNamespace,
) -> None:
    lost = world.ids["conditionalqa"][0]
    run = start(world, "conditionalqa", "pool30", "lossy")
    record(world, "conditionalqa", "pool30", run, **{lost: excluded(lost)})
    runs = {**world.runs["conditionalqa"], "pool30": run}
    report = pilot.measure("conditionalqa", world.folder["conditionalqa"], runs)
    arm = report["arms"]["pool30"]
    assert arm["measured"] == 3
    assert arm["excluded"] == {lost: {"stage": "grade", "error_type": "ValueError"}}
    assert "scenario" not in pilot.dump(report)
    pairs = report["pairs"]["pool30"]
    assert pairs["pairs"] == 3 and pairs["lost"] == [lost]
    assert pairs["primary"]["n"] == 3
    assert pairs["primary"]["used"] is False
    assert pairs["primary"]["not_used_because"] == pilot.LOST_PAIRS
    # A tenth of the pairs may be lost: the variance of the others can only raise the registered.
    records = {str(n): {"status": "ok", "points": {"p": {"m": 1.0}}} for n in range(10)}
    compared = {"pairs": 9, "lost": ["9"]}
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(pilot.BASES, "tiny", {"primary": ("p", "m")})
        assert pilot.usable("tiny", compared, records, 10) is None
        assert pilot.usable("tiny", {"pairs": 8, "lost": ["8", "9"]}, records, 10) == (
            pilot.LOST_PAIRS
        )
        assert pilot.usable("tiny", compared, records, 0) == pilot.NO_GOLD_IN_INDEX
        nothing = {key: {"status": "ok", "points": {"p": {"m": 0.0}}} for key in records}
        assert pilot.usable("tiny", compared, nothing, 10) == pilot.NO_GOLD_IN_CONTROL


def test_a_control_that_finds_nothing_gives_no_variance(world: SimpleNamespace) -> None:
    run = start(world, "wixqa", "control", "blind")
    manifest = parity.read(run / "manifest.json")
    empty = {
        listed["case_id"]: {
            "status": "ok",
            "vector": [3],
            "bm25": [],
            "pool": [3],
            "ranked": [3],
            "timings_ms": dict(BEFORE_GRADING),
        }
        for listed in manifest["cases"]
    }
    record(world, "wixqa", "control", run, **empty)
    runs = {**world.runs["wixqa"], "control": run}
    primary = pilot.measure("wixqa", world.folder["wixqa"], runs)["pairs"]["pool30"]["primary"]
    assert primary["used"] is False and primary["not_used_because"] == pilot.NO_GOLD_IN_CONTROL
    assert primary["mean"] == pytest.approx(2 / 3)


def test_arms_that_are_not_the_registered_two_are_refused(world: SimpleNamespace) -> None:
    folder, runs = world.folder["conditionalqa"], world.runs["conditionalqa"]
    with pytest.raises(ValueError, match="the control and its registered perturbation"):
        pilot.measure("conditionalqa", folder, {"control": runs["control"]})
    with pytest.raises(ValueError, match="does not move what the arm registers"):
        pilot.measure("conditionalqa", folder, {**runs, "pool30": runs["control"]})
    more = start(
        world, "conditionalqa", "pool30", "more", settings=["retrieval_top_k=30", "rerank_top_k=3"]
    )
    with pytest.raises(ValueError, match="does not move what the arm registers"):
        pilot.measure("conditionalqa", folder, {**runs, "pool30": more})
    other = start(world, "conditionalqa", "pool30", "other-code", code_sha="c" * 40)
    with pytest.raises(ValueError, match="not the control's code, cases, index, models"):
        pilot.measure("conditionalqa", folder, {**runs, "pool30": other})
    with pytest.raises(ValueError, match="not a run on the registered selection of the base"):
        pilot.measure("conditionalqa", folder, world.runs["wixqa"])
    with pytest.raises(ValueError, match="not registered for the base"):
        pilot.measure("multihoprag", folder, runs)


def test_a_run_that_stopped_or_did_not_finish_is_refused(world: SimpleNamespace) -> None:
    folder = world.folder["conditionalqa"]
    unfinished = start(world, "conditionalqa", "pool30", "unfinished")
    runs = {**world.runs["conditionalqa"], "pool30": unfinished}
    with pytest.raises(ValueError, match="has not finished the stage grade"):
        pilot.measure("conditionalqa", folder, runs)
    record(world, "conditionalqa", "pool30", unfinished)
    assert pilot.measure("conditionalqa", folder, runs)["pairs"]["pool30"]["pairs"] == 4
    parity.write_new(unfinished / "retrieve.abort.json", {"stage": "retrieve", "reason": "stop"})
    with pytest.raises(baseline.IntegrityError, match="Open abort at retrieve: stop"):
        pilot.measure("conditionalqa", folder, runs)


def test_inputs_other_than_those_of_the_runs_are_refused(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, runs = world.folder["wixqa"], world.runs["wixqa"]
    questions = folder / "selections" / "pilot.questions.jsonl"
    kept = questions.read_bytes()
    rows = [json.loads(line) for line in kept.decode("utf-8").splitlines()]
    questions.write_text(
        "".join(json.dumps(row, indent=None, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ValueError, match="the runs read another question file"):
        pilot.measure("wixqa", folder, runs)
    questions.write_bytes(b"".join(reversed(kept.splitlines(keepends=True))))
    with pytest.raises(baseline.IntegrityError, match="not the registered selection"):
        pilot.measure("wixqa", folder, runs)
    questions.write_bytes(kept)
    archive = folder / "chunks.json.gz"
    held = archive.read_bytes()
    payload = json.loads(gzip.decompress(held))
    archive.write_bytes(gzip.compress(json.dumps({**payload, "extra": 1}).encode()))
    with pytest.raises(ValueError, match="not the one the index was built from"):
        pilot.measure("wixqa", folder, runs)
    archive.write_bytes(held)
    assert pilot.measure("wixqa", folder, runs)["cases"] == 3

    def locked(*args: Any, **kwargs: Any) -> list[str]:
        raise parts.Locked("wixqa: the part 'tuning' is locked until acceptance 4.1 opens it")

    monkeypatch.setattr(parts, "read", locked)
    with pytest.raises(baseline.IntegrityError, match="locked until acceptance 4.1"):
        pilot.measure("wixqa", folder, runs)


def test_a_context_that_is_no_expansion_of_its_seed_stops_the_measure(
    world: SimpleNamespace,
) -> None:
    case_id = world.ids["conditionalqa"][0]
    run = start(world, "conditionalqa", "pool30", "foreign")
    by_id = {case["case_id"]: case for case in CASES["conditionalqa"]}
    row = conditional_row(world, "pool30", by_id[case_id], 0)
    row["documents"] = [{**row["documents"][0], "text": "a text of no chunk"}]
    record(world, "conditionalqa", "pool30", run, **{case_id: row})
    runs = {**world.runs["conditionalqa"], "pool30": run}
    with pytest.raises(ValueError, match="not an expansion of chunk"):
        pilot.measure("conditionalqa", world.folder["conditionalqa"], runs)


def test_cli_writes_the_document_once_and_names_both_arms(
    world: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = world.runs["wixqa"]
    out = world.root / "out" / "wixqa.json"
    arguments = [
        "measure",
        "--base",
        "wixqa",
        "--base-dir",
        str(world.folder["wixqa"]),
        "--arm",
        f"control={runs['control']}",
        "--arm",
        f"pool30={runs['pool30']}",
        "--out",
        str(out),
    ]
    assert pilot.main(arguments) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["base"] == "wixqa" and printed["cases"] == 3 and printed["clusters"] == 2
    assert printed["pairs"] == {"pool30": 3} and printed["primary"]["pool30"]["used"] is True
    assert json.loads(out.read_text(encoding="utf-8")) == measured(world, "wixqa")
    with pytest.raises(FileExistsError, match="wixqa.json exists; refusing to measure again"):
        pilot.main(arguments)
    out.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="wixqa.json exists; refusing to measure again"):
        pilot.main(arguments)
    for broken in (arguments[:7], [*arguments[:7], "--arm", "sent3=x", *arguments[9:]]):
        with pytest.raises(SystemExit):
            pilot.main([*broken, "--out", str(out)] if "--out" not in broken else broken)
    with pytest.raises(SystemExit):
        pilot.main([*arguments, "--pilot", f"wixqa={out}"])


@pytest.mark.parametrize("base", ["conditionalqa", "wixqa"])
@pytest.mark.parametrize("existing", ["measure", "aggregates"])
def test_measure_refuses_existing_outputs_before_reading_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], base: str, existing: str
) -> None:
    out = tmp_path / "measure.json"
    slim = tmp_path / "aggregates.json"
    target = out if existing == "measure" else slim
    target.write_bytes(b"saved result\n")
    arguments = ["measure", "--base", base, "--base-dir", str(tmp_path / "absent-base")]
    arguments += ["--arm", f"control={tmp_path / 'absent-control'}"]
    arguments += ["--arm", f"pool30={tmp_path / 'absent-pool30'}"]
    arguments += ["--out", str(out), "--aggregates", str(slim)]

    with pytest.raises(FileExistsError, match=f"{target.name} exists; refusing to measure again"):
        pilot.main(arguments)

    assert target.read_bytes() == b"saved result\n"
    assert not (slim if target == out else out).exists()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("alias", [False, True])
def test_measure_refuses_shared_output_paths_before_reading_inputs(
    tmp_path: Path, alias: bool
) -> None:
    out = tmp_path / "measure.json"
    nested = tmp_path / "nested"
    nested.mkdir()
    slim = nested / ".." / out.name if alias else out
    arguments = ["measure", "--base", "wixqa", "--base-dir", str(tmp_path / "absent-base")]
    arguments += ["--arm", f"control={tmp_path / 'absent-control'}"]
    arguments += ["--arm", f"pool30={tmp_path / 'absent-pool30'}"]
    arguments += ["--out", str(out), "--aggregates", str(slim)]

    with pytest.raises(SystemExit) as stopped:
        pilot.main(arguments)

    assert stopped.value.code == 2
    assert not out.exists()


def test_what_leaves_the_host_is_the_document_without_the_rows_of_questions(
    world: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = world.runs["conditionalqa"]
    out = world.root / "out" / "conditionalqa.json"
    slim = world.root / "out" / "conditionalqa.aggregates.json"
    arguments = ["measure", "--base", "conditionalqa", "--base-dir"]
    arguments += [str(world.folder["conditionalqa"]), "--arm", f"control={runs['control']}"]
    arguments += ["--arm", f"pool30={runs['pool30']}", "--out", str(out)]
    assert pilot.main([*arguments, "--aggregates", str(slim)]) == 0
    capsys.readouterr()
    full = json.loads(out.read_text(encoding="utf-8"))
    kept = json.loads(slim.read_text(encoding="utf-8"))
    assert "per_case" in full and "per_case" not in kept
    assert kept.pop("measure_sha256") == parity.file_sha(out)
    assert kept == {key: value for key, value in full.items() if key != "per_case"}
    # The sizes need nothing of a single question: both documents give the same.
    registered = parts.registration()
    sized = pilot.sizes(registered, {"conditionalqa": kept})
    assert sized == pilot.sizes(registered, {"conditionalqa": full})
    assert sized["pilot_runs"] == {
        "conditionalqa": {
            name: run["run_sha256"] for name, run in full["provenance"]["runs"].items()
        }
    }
    assert set(sized["pilot_runs"]["conditionalqa"]) == set(pilot.ARMS)
    with pytest.raises(SystemExit):
        pilot.main(["sizes", "--aggregates", str(slim), "--out", str(out)])


def test_designs_are_the_whole_part_and_its_selections_by_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pilot, "DOCUMENTS", (2, 3))
    monkeypatch.setattr(pilot, "PER_DOCUMENT", (1, 2))
    block = {
        "primary_by_document": [3, 0, 2, 5, 1],
        "several_sections_by_document": [0, 0, 1, 2, 0],
    }
    # The grid, and with one question each every page that carries one: four of the five here.
    assert pilot.designs("conditionalqa", block, "primary") == [
        (None, [5, 3, 2, 1]),
        ({"documents": 2, "per_document": 1}, [1, 1]),
        ({"documents": 3, "per_document": 1}, [1, 1, 1]),
        ({"documents": 4, "per_document": 1}, [1, 1, 1, 1]),
        ({"documents": 2, "per_document": 2}, [2, 2]),
        ({"documents": 3, "per_document": 2}, [2, 2, 2]),
    ]
    assert pilot.designs("conditionalqa", block, "several_sections") == [
        (None, [2, 1]),
        ({"documents": 2, "per_document": 1}, [1, 1]),
    ]
    nothing = {"primary_by_document": [0, 0], "several_sections_by_document": [0, 0]}
    assert pilot.designs("conditionalqa", nothing, "primary") == [(None, [])]
    articles = {"cluster_sizes": {"1": 2, "3": 1}}
    assert pilot.designs("wixqa", articles, "all") == [(None, [3, 1, 1])]


def test_sizes_of_the_registered_parts_stand_on_the_grid_before_a_pilot() -> None:
    registered = parts.registration()
    document = pilot.sizes(registered, {})
    assert document["version"] == "external-sizes/v1" and document["grid_variance"] == 0.10
    assert document["registration_sha256"] == parity.file_sha(parts.REGISTRATION)
    assert document["seconds_per_question"] == {} and document["step_1"] is None
    rows = document["rows"]
    assert {row["base"] for row in rows} == {"conditionalqa", "wixqa"}
    assert all(row["variance"] == 0.10 and row["variance_source"] == "grid" for row in rows)
    assert not any("hours_of_two_arms" in row or "at_pilot_correlation" in row for row in rows)
    whole = {
        (row["base"], row["part"], row["stratum"]): row for row in rows if row["selection"] is None
    }
    assert sorted(whole) == [
        ("conditionalqa", "locked", "primary"),
        ("conditionalqa", "locked", "several_sections"),
        ("conditionalqa", "reserve", "primary"),
        ("conditionalqa", "reserve", "several_sections"),
        ("conditionalqa", "tuning", "primary"),
        ("conditionalqa", "tuning", "several_sections"),
        ("wixqa", "excluded", "all"),
        ("wixqa", "locked", "all"),
        ("wixqa", "tuning", "all"),
    ]
    locked = whole["conditionalqa", "locked", "primary"]
    pages = registered["bases"]["conditionalqa"]["parts"]["locked"]
    clusters = sorted((size for size in pages["primary_by_document"] if size), reverse=True)
    assert (locked["n"], locked["clusters"], locked["access"]) == (823, 165, "locked")
    assert locked["largest_cluster"] == clusters[0] == 12
    expected = power.scenario(0.10, clusters, 1.0, student=True)
    assert {key: locked["registered"][key] for key in expected} == expected
    assert locked["independent"]["design_effect"] == 1.0
    # Clusters that move as one: the interval is the stricter threshold, and the rule needs the
    # MDE. Independent questions: the minimally useful effect is, and the rule needs more.
    held, free = locked["registered"], locked["independent"]
    assert held["critical"] * held["standard_error"] > power.MUE
    assert held["effect_for_rule"] == pytest.approx(held["mde"])
    assert free["critical"] * free["standard_error"] < power.MUE
    assert free["effect_for_rule"] == pytest.approx(0.05 + 0.8416212 * free["standard_error"])
    assert free["effect_for_rule"] > free["mde"]
    several = whole["conditionalqa", "locked", "several_sections"]
    assert (several["n"], several["clusters"]) == (390, 145)
    articles = whole["wixqa", "locked", "all"]
    assert (articles["n"], articles["clusters"], articles["largest_cluster"]) == (200, 154, 11)
    by_documents = {
        (row["selection"]["documents"], row["selection"]["per_document"]): row
        for row in rows
        if row["selection"] and (row["part"], row["stratum"]) == ("locked", "primary")
    }
    # 129 documents of the locked part carry four primary questions or more, and all 165 one.
    offered = {(n, m) for n in pilot.DOCUMENTS for m in pilot.PER_DOCUMENT}
    assert set(by_documents) == (offered - {(150, 4)}) | {(165, 1)}
    row = by_documents[100, 2]
    assert (row["n"], row["clusters"], row["largest_cluster"]) == (200, 100, 2)
    assert row["registered"]["design_effect"] == 2.0
    assert row["registered"]["mde"] == pytest.approx(by_documents[100, 1]["registered"]["mde"])
    assert row["independent"]["mde"] < by_documents[100, 1]["independent"]["mde"]
    # One question on every page: the rows the selection of step 1 is read from. On all 165
    # pages +0.05 becomes the stricter threshold, and there alone the rule needs more than the
    # registered MDE.
    every = by_documents[165, 1]
    assert (every["n"], every["clusters"], every["largest_cluster"]) == (165, 165, 1)
    assert every["registered"]["mde"] < locked["registered"]["mde"]
    more = [
        row
        for row in rows
        if row["registered"]["effect_for_rule"] > row["registered"]["mde"] + 1e-9
    ]
    assert {(row["base"], row["stratum"], row["n"]) for row in more} == {
        ("conditionalqa", "primary", 165)
    }
    assert sorted(row["part"] for row in more) == ["locked", "reserve", "tuning"]
    assert all(row["selection"] == {"documents": 165, "per_document": 1} for row in more)
    of_stratum = {
        row["selection"]["documents"]
        for row in rows
        if row["selection"] and (row["part"], row["stratum"]) == ("locked", "several_sections")
    }
    assert 145 in of_stratum and several["clusters"] == 145


def test_a_pilot_raises_the_variance_and_gives_the_hours(world: SimpleNamespace) -> None:
    pilots = {base: measured(world, base) for base in DOCUMENTS}
    document = pilot.sizes(parts.registration(), pilots)
    assert document["variances"]["conditionalqa"]["primary"] == {
        "variance": pytest.approx(2 / 3),
        "source": "pilot pool30",
        "candidates": {"grid": 0.10, "pilot pool30": pytest.approx(2 / 3)},
        "differing_share": 0.5,
        "correlation": pytest.approx(1 / 3),
    }
    several = document["variances"]["conditionalqa"]["several_sections"]
    assert several["source"] == "pilot pool30" and several["variance"] == pytest.approx(2 / 3)
    assert several["candidates"]["pilot pool30, several_sections"] == 0.0
    assert document["variances"]["wixqa"]["all"]["variance"] == pytest.approx(4 / 3)
    rows = {
        (row["base"], row["part"], row["stratum"]): row
        for row in document["rows"]
        if row["selection"] is None
    }
    # Two pages of two primary questions a part; a part of one cluster or of none gives no row.
    assert sorted(rows) == [
        *(
            ("conditionalqa", part, stratum)
            for part in ("locked", "reserve", "tuning")
            for stratum in ("primary", "several_sections")
        ),
        ("wixqa", "tuning", "all"),
    ]
    row = rows["conditionalqa", "tuning", "primary"]
    assert (row["n"], row["clusters"], row["variance_source"]) == (4, 2, "pilot pool30")
    assert row["registered"]["variance"] == pytest.approx(2 / 3)
    assert row["registered"]["differing_share"] == 0.5
    assert row["at_pilot_correlation"]["intraclass_correlation"] == pytest.approx(1 / 3)
    seconds = 1.5 + 0.25 + 1.3 + 25.0
    assert row["hours_of_two_arms"] == pytest.approx(2 * 4 * seconds / 3600)
    assert rows["wixqa", "tuning", "all"]["hours_of_two_arms"] == pytest.approx(2 * 3 * 3.05 / 3600)
    assert document["seconds_per_question"]["wixqa"]["retrieve"]["mean"] == 1.3

    with pytest.raises(ValueError, match="not the pilot of the base: wixqa"):
        pilot.sizes(parts.registration(), {"wixqa": pilots["conditionalqa"]})


def test_a_pilot_cannot_lower_the_variance_and_one_set_aside_can_still_raise_it(
    world: SimpleNamespace,
) -> None:
    usable = measured(world, "conditionalqa")
    primary = usable["pairs"]["pool30"]["primary"]
    assert primary["used"] is True and primary["variance"] == pytest.approx(2 / 3)

    def changed(**values: Any) -> dict[str, Any]:
        other = json.loads(json.dumps(usable))
        other["pairs"]["pool30"]["primary"].update(values)
        return other

    # Below the grid a usable pilot leaves the grid, and its share and correlation are taken.
    low = pilot.registered_variance(changed(variance=0.01), "primary")
    assert low == {
        "variance": 0.10,
        "source": "grid",
        "candidates": {"grid": 0.10, "pilot pool30": 0.01},
        "differing_share": 0.5,
        "correlation": pytest.approx(1 / 3),
    }
    # A pilot whose variance is not used: above the grid it raises the registered variance all
    # the same, below it changes nothing; its share and correlation are not taken.
    aside = changed(used=False, not_used_because=pilot.LOST_PAIRS)
    raised = pilot.registered_variance(aside, "several_sections")
    assert raised == {
        "variance": pytest.approx(2 / 3),
        "source": "pilot pool30, not usable",
        "candidates": {
            "grid": 0.10,
            "pilot pool30, not usable": pytest.approx(2 / 3),
            "pilot pool30, not usable, several_sections": 0.0,
        },
        "differing_share": None,
        "correlation": None,
    }
    row = pilot.sizes(parts.registration(), {"conditionalqa": aside})["rows"][0]
    assert (row["base"], row["variance_source"]) == ("conditionalqa", "pilot pool30, not usable")
    assert row["variance"] == pytest.approx(2 / 3)
    assert "at_pilot_correlation" not in row and "hours_of_two_arms" in row
    kept = pilot.registered_variance(changed(used=False, variance=0.01), "primary")
    assert (kept["variance"], kept["source"], kept["correlation"]) == (0.10, "grid", None)
    assert pilot.registered_variance(None, "primary")["candidates"] == {"grid": 0.10}


def test_the_timing_of_the_entity_graph_stops_at_the_share_of_the_ceiling() -> None:
    # 100 documents with 2,000 of the 10,000 chunks of a base may take a fifth of three nights.
    assert pilot.graph_timing_limit(2000, 10000) == pytest.approx(3 * 8 * 3600 / 5)
    assert pilot.graph_timing_limit(10000, 10000) == pilot.GRAPH_NIGHTS * pilot.NIGHT_SECONDS
    for sample, base in ((0, 10), (11, 10)):
        with pytest.raises(ValueError, match="not a part of the base"):
            pilot.graph_timing_limit(sample, base)


def test_step_one_reads_one_question_a_page_under_the_ceiling(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    pilots = {base: measured(world, base) for base in DOCUMENTS}
    registered = parts.registration()
    assert pilot.STEP_ONE_NIGHTS == 8 and pilot.NIGHT_SECONDS == 8 * 3600
    # Both pilots are needed: the step reads both bases.
    assert pilot.sizes(registered, {"conditionalqa": pilots["conditionalqa"]})["step_1"] is None
    step = pilot.sizes(registered, pilots)["step_1"]
    pages, articles = 28.05, 3.05
    assert step["ceiling_seconds"] == 8 * 8 * 3600
    assert step["seconds_per_question"] == {
        "conditionalqa": pytest.approx(pages),
        "wixqa": pytest.approx(articles),
    }
    # The locked part of the small WixQA holds one question; that of ConditionalQA two pages.
    assert step["wixqa"] == {"questions": 1, "seconds_of_two_arms": pytest.approx(2 * articles)}
    assert sorted(step["conditionalqa"]) == ["primary", "several_sections"]
    for stratum, read in step["conditionalqa"].items():
        assert (read["pages_with_a_question"], read["pages_read"]) == (2, 2), stratum
        assert read["seconds_of_two_arms"] == pytest.approx(2 * 2 * pages)
        assert read["variance"] == pytest.approx(2 / 3)
        assert read["variance_source"] == "pilot pool30"
        expected = pilot.scenario(2 / 3, [1, 1], 1.0, 0.5, student=True)
        assert read["registered"] == pytest.approx(expected)
    # A pilot whose variance is not used gives its seconds to the count all the same.
    aside = json.loads(json.dumps(pilots))
    aside["conditionalqa"]["pairs"]["pool30"]["primary"].update(
        used=False, not_used_because=pilot.LOST_PAIRS
    )
    set_aside = pilot.step_one(registered, aside)
    assert set_aside["seconds_per_question"] == step["seconds_per_question"]
    for stratum, read in set_aside["conditionalqa"].items():
        assert read["pages_read"] == step["conditionalqa"][stratum]["pages_read"], stratum
        assert read["variance_source"] == "pilot pool30, not usable"
    # A ceiling that two arms on every page exceed cuts the pages to those that fit, and neither
    # a variance nor a correlation of the pilot moves that count.
    monkeypatch.setattr(pilot, "NIGHT_SECONDS", 10)
    cut = pilot.step_one(registered, pilots)
    assert cut["ceiling_seconds"] == 80
    assert int((80 - 2 * articles) // (2 * pages)) == 1
    for read in cut["conditionalqa"].values():
        assert read["pages_read"] == 1 and "registered" not in read
        assert read["seconds_of_two_arms"] == pytest.approx(2 * pages)
    moved = json.loads(json.dumps(pilots))
    moved["conditionalqa"]["pairs"]["pool30"]["primary"].update(
        variance=0.5, intraclass_correlation=0.0, mean=0.9
    )
    again = pilot.step_one(registered, moved)["conditionalqa"]
    assert {name: read["pages_read"] for name, read in again.items()} == {
        "primary": 1,
        "several_sections": 1,
    }
    monkeypatch.setattr(pilot, "NIGHT_SECONDS", 0)
    assert pilot.step_one(registered, pilots)["conditionalqa"]["primary"]["pages_read"] == 0


def test_cli_prints_the_sizes_from_the_registration_and_the_pilots(
    world: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    out = world.root / "out" / "sizes.json"
    assert pilot.main(["sizes", "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out) == {"rows": 13, "pilots": []}
    assert json.loads(out.read_text(encoding="utf-8")) == pilot.sizes(parts.registration(), {})
    measured_file = world.root / "out" / "wixqa.json"
    measured_file.write_text(pilot.dump(measured(world, "wixqa")), encoding="utf-8")
    with pytest.raises(FileExistsError, match="A different sizes.json exists"):
        pilot.main(["sizes", "--pilot", f"wixqa={measured_file}", "--out", str(out)])
    other = world.root / "out" / "sizes-pilot.json"
    assert pilot.main(["sizes", "--pilot", f"wixqa={measured_file}", "--out", str(other)]) == 0
    assert json.loads(capsys.readouterr().out) == {"rows": 13, "pilots": ["wixqa"]}
    for broken in (
        ["sizes", "--base", "wixqa", "--out", str(other)],
        ["sizes", "--pilot", "multihoprag=x", "--out", str(other)],
        ["sizes", "--pilot", f"wixqa={measured_file}", "--pilot", "wixqa=y", "--out", str(other)],
    ):
        with pytest.raises(SystemExit):
            pilot.main(broken)


TITLES = {"conditionalqa": "ConditionalQA", "wixqa": "WixQA", "multihoprag": "MultiHop-RAG"}
# The rows of the sizes table of the spec: base, part, stratum, and the design — the whole part
# or so many pages with so many questions each.
SPEC_ROWS: tuple[tuple[str, str, str, tuple[int, int] | None], ...] = (
    ("conditionalqa", "locked", "primary", None),
    ("conditionalqa", "locked", "several_sections", None),
    ("conditionalqa", "locked", "primary", (165, 1)),
    ("conditionalqa", "locked", "several_sections", (145, 1)),
    ("conditionalqa", "locked", "primary", (150, 1)),
    ("conditionalqa", "locked", "primary", (100, 1)),
    ("conditionalqa", "locked", "primary", (100, 2)),
    ("conditionalqa", "locked", "primary", (50, 2)),
    ("conditionalqa", "tuning", "primary", None),
    ("conditionalqa", "tuning", "several_sections", None),
    ("conditionalqa", "reserve", "primary", None),
    ("conditionalqa", "reserve", "several_sections", None),
    ("wixqa", "locked", "all", None),
    ("wixqa", "tuning", "all", None),
)


def size_line(row: dict[str, Any]) -> str:
    chosen = row["selection"]
    design = (
        "whole" if chosen is None else f"{chosen['documents']} pages × {chosen['per_document']}"
    )
    stratum = f"`{row['stratum']}`" if row["stratum"] == "several_sections" else row["stratum"]
    held, free = row["registered"], row["independent"]
    return (
        f"| {TITLES[row['base']]} | `{row['part']}` | {stratum} | {design} | {row['n']} "
        f"| {row['clusters']} | {held['mde']:.3f} | {held['effect_for_rule']:.3f} "
        f"| {held['power_rule_at_mue']:.2f} | {held['power_noninferiority_at_zero']:.2f} "
        f"| {free['mde']:.3f} | {free['effect_for_rule']:.3f} |"
    )


def effective(clusters: list[int]) -> float:
    """What clusters of these sizes count as when their questions move as one: n²/Σm²."""
    return sum(clusters) ** 2 / sum(size * size for size in clusters)


def test_spec_registers_what_the_parts_and_the_pilot_apply() -> None:
    spec = (pilot.ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    section = spec[
        spec.index("## External bases: parts and pilot of plan slice 1.6") : spec.index(
            "## Acceptance contract (plan track 4)"
        )
    ]
    flat = " ".join(section.split())
    registered = parts.registration()
    for path in (parts.REGISTRATION, bases.REGISTRATION):
        assert f"SHA-256 `{parity.file_sha(path)}`" in flat
    assert f"the seed {parts.SEED}" in flat and f"`{gold.MATCH_RULE}`" in flat
    assert registered["opened"] == [] and "The list `opened` of the registration is empty" in flat

    # The parts and the selection of the pilot, as the registration counts them.
    for base, block in registered["bases"].items():
        for name, part in block["parts"].items():
            largest = max(int(size) for size in part["cluster_sizes"])
            line = (
                f"| {TITLES[base]} | `{name}` | {part['access']} | {part['cases']} "
                f"| {part['clusters']} | {largest} |"
            )
            assert line in section, line
    for name, part in registered["bases"]["conditionalqa"]["parts"].items():
        line = (
            f"| `{name}` | {part['documents']} | {part['cases']} | {part['not_answerable']} "
            f"| {part['primary']} | {part['primary_with_evidence_in_several_sections']} "
            f"| {part['clusters_with_a_several_section_question']} |"
        )
        assert line in section, line
    converted = bases.registration()["bases"]
    for base, phrase in (
        ("conditionalqa", "{cases:,} questions on {documents:,} pages"),
        ("wixqa", "{cases:,} questions over {documents:,} articles"),
        ("multihoprag", "{cases:,} questions over {documents:,} articles"),
    ):
        assert phrase.format(**converted[base]["converted"]) in flat
    pages = registered["selections"]["conditionalqa"]["pilot"]
    articles = registered["selections"]["wixqa"]["pilot"]
    assert pages["rule"]["per_document"] == 2
    assert (
        f"the first {pages['rule']['documents']} pages of `tuning` with two primary questions or "
        f"more, two of each: {pages['cases']} questions in {pages['clusters']} clusters, "
        f"{pages['primary_with_evidence_in_several_sections']} of them of the stratum "
        f"`several_sections`, on {pages['clusters_with_a_several_section_question']} pages"
    ) in flat
    assert (
        f"the first {articles['cases']} questions of `tuning`: {articles['clusters']} clusters"
    ) in flat
    assert articles["cluster_sizes"] == {"1": 29, "2": 1, "3": 3}
    assert "29 of one question, one of two and three of three" in flat

    # The tool: its arms, points, metrics, budget and thresholds.
    assert parity.CONFIG["retrieval_top_k"] == 20
    for name, moved in pilot.ARMS.items():
        assert f"`{name}`" in flat
        for setting, count in moved.items():
            assert f"`{name}`, with `{setting}` {count} in place of 20" in flat
    for point in pilot.BASES["conditionalqa"]["points"]:
        assert f"`{point}`" in flat
    for read in pilot.BASES.values():
        point, metric = read["primary"]
        assert f"Primary metric: `{metric}` at `{point}`" in flat
        assert all(f"`{name}`" in flat for name in read["metrics"])
    assert pilot.TOP == 5 and "of which the first five are read" in flat
    budget = [f"`{name}`" for name in pilot.BUDGET]
    assert f"{', '.join(budget[:-1])} and {budget[-1]}" in flat
    assert f"up to {parity.CONFIG['parent_expansion_max_chars']:,} characters" in flat
    assert pilot.MAX_LOST_SHARE == 0.10 and "at most a tenth of the pairs are lost" in flat
    assert f"the grid value {pilot.GRID_VARIANCE:.2f}" in flat
    offered = ", ".join(str(count) for count in pilot.DOCUMENTS[:-1])
    each = ", ".join(str(count) for count in pilot.PER_DOCUMENT[:-1])
    assert (
        f"{offered} or {pilot.DOCUMENTS[-1]} pages with {each} or {pilot.PER_DOCUMENT[-1]} "
        "questions of the stratum each"
    ) in flat

    # The sizes before the pilot are what the code gives for the registered parts.
    rows = {
        (
            row["base"],
            row["part"],
            row["stratum"],
            row["selection"] and (row["selection"]["documents"], row["selection"]["per_document"]),
        ): row
        for row in pilot.sizes(registered, {})["rows"]
    }
    for key in SPEC_ROWS:
        assert size_line(rows[key]) in section, key
    printed = [
        line
        for line in section.splitlines()
        if line.startswith(tuple(f"| {t} |" for t in TITLES.values()))
    ]
    assert len(printed) == 7 + len(SPEC_ROWS)
    assert all(row["registered"]["mde"] > power.MUE for row in rows.values())
    locked = [rows[key] for key in SPEC_ROWS if key[1] == "locked" and key[3] is None]
    held = [row["registered"] for row in locked]
    free = [row["independent"] for row in locked]
    assert (
        "{:.3f} on the locked part of ConditionalQA, {:.3f} on its stratum `several_sections`, "
        "{:.3f} on ExpertWritten".format(*(row["mde"] for row in held))
    ) in flat
    passing = [row["power_rule_at_mue"] for row in held]
    assert f"with probability {min(passing):.2f} to {max(passing):.2f}" in flat
    needed = [row["effect_for_rule"] for row in free]
    assert f"a true gain of {min(needed):.3f} to {max(needed):.3f}" in flat
    zero = [row["power_noninferiority_at_zero"] for row in held]
    assert (
        f"{min(zero):.2f} to {max(zero):.2f} in the registered reading on the locked parts" in flat
    )
    best = max(row["power_noninferiority_at_zero"] for row in free)
    assert f"and {best:.2f} at best for independent questions" in flat
    whole = rows["conditionalqa", "locked", "primary", None]
    single = rows["conditionalqa", "locked", "primary", (150, 1)]
    assert (
        f"{single['registered']['mde']:.3f} against {whole['registered']['mde']:.3f}, at "
        f"{single['n']} questions in place of {whole['n']}"
    ) in flat
    assert (
        f"the whole part has {whole['independent']['mde']:.3f} against "
        f"{single['independent']['mde']:.3f}"
    ) in flat

    # The selection of step 1, fixed before the pilot: one question a page under a ceiling.
    locked_pages = registered["bases"]["conditionalqa"]["parts"]["locked"]
    locked_articles = registered["bases"]["wixqa"]["parts"]["locked"]
    by_page = [size for size in locked_pages["primary_by_document"] if size]
    by_article = [
        int(size) for size, count in locked_articles["cluster_sizes"].items() for _ in range(count)
    ]
    assert f"about {effective(by_page):.0f} pages of its {len(by_page)}" in flat
    assert f"about {effective(by_article):.0f} clusters of its {len(by_article)}" in flat
    every = rows["conditionalqa", "locked", "primary", (165, 1)]
    of_stratum = rows["conditionalqa", "locked", "several_sections", (145, 1)]
    assert every["n"] == locked_pages["clusters"]
    assert of_stratum["n"] == locked_pages["clusters_with_a_several_section_question"]
    assert (
        f"{every['n']} pages for all primary questions, {of_stratum['n']} for `several_sections`"
    ) in flat
    assert f"a true gain of {every['registered']['effect_for_rule']:.3f} on 165 pages" in flat
    assert f"the registered MDE is {every['registered']['mde']:.3f}" in flat
    assert (
        f"of {of_stratum['registered']['effect_for_rule']:.3f} on the 145 pages of the stratum"
    ) in flat
    expert = rows["wixqa", "locked", "all", None]
    single_articles = pilot.scenario(
        pilot.GRID_VARIANCE, [1] * len(by_article), 1.0, None, student=True
    )
    assert (
        f"a registered MDE of {single_articles['mde']:.3f} against {expert['registered']['mde']:.3f}"
    ) in flat
    assert pilot.STEP_ONE_NIGHTS == 8 and pilot.NIGHT_SECONDS == 8 * 3600
    assert "eight nights of eight hours" in flat
    # The ceiling at the seconds of our own corpus: close at the means of the control of step
    # 1.3c, with room at the medians of slice 2.5.
    ceiling = pilot.STEP_ONE_NIGHTS * pilot.NIGHT_SECONDS
    at_means = 2 * every["n"] * 627 + 2 * expert["n"] * 59
    assert at_means > ceiling
    assert (
        f"take {at_means / 3600:.2f} hours, and "
        f"{(ceiling - 2 * expert['n'] * 59) // (2 * 627)} pages fit"
    ) in flat
    assert round((2 * every["n"] * 546 + 2 * expert["n"] * 39) / 3600) == 54
    assert "at the medians of slice 2.5 they take about 54" in flat
    assert (
        "Moved before a pilot is measured, it is the registered ceiling; moved after, it is a "
        "deviation"
    ) in flat
    assert "This narrows plan row 1.6" in flat
    assert "Once the document is written the pilot is not run or measured again" in flat
    assert "`reserve` and `excluded` are read by no run of this campaign" in flat
    simulated = registered["bases"]["wixqa"]["parts"]["tuning"]["cases"]
    assert f"reads the {simulated} questions of `tuning`" in flat
    # What step 1 reads: one question a page of ConditionalQA, and ExpertWritten whole.
    step_rows = [every["registered"], of_stratum["registered"], expert["registered"]]

    def span(name: str, digits: int) -> str:
        values = [row[name] for row in step_rows]
        return f"{min(values):.{digits}f} to {max(values):.{digits}f}"

    assert (
        f"the registered MDE is {span('mde', 3)}, the rule needs a true gain of "
        f"{span('effect_for_rule', 3)} and passes at a true +0.05 with probability "
        f"{span('power_rule_at_mue', 2)}"
    ) in flat
    assert (
        f"the two numbers are {span('power_noninferiority_at_zero', 2)} and "
        f"{span('effect_for_noninferiority', 3)}"
    ) in flat
    assert pilot.GRAPH_NIGHTS == 3
    assert (
        "A base gets its entity graph when that cost is at most three nights of eight hours" in flat
    )
    assert "the experiment arm of the branch is this lane" in flat
    confirmed = [row["effect_for_noninferiority"] for row in held]
    assert f"{min(confirmed):.3f} to {max(confirmed):.3f} on the whole locked parts" in flat

    # Hours of two arms at the seconds of our own corpus: the medians of the collection of slice
    # 2.5 and the means of the control of step 1.3c, up to the reranked list and through grading.
    def hours(questions: int, seconds: int) -> float:
        return 2 * questions * seconds / 3600

    assert "39 s a question up to the reranked list, 546 s through grading" in flat
    assert (
        f"about {hours(every['n'], 546):.0f} hours for {every['n']} questions and "
        f"{hours(of_stratum['n'], 546):.0f} for {of_stratum['n']}"
    ) in flat
    stratum = rows["conditionalqa", "locked", "several_sections", None]
    assert (
        f"about {hours(whole['n'], 546):.0f} hours and its stratum {hours(stratum['n'], 546):.0f}"
    ) in flat
    assert f"cost about {hours(expert['n'], 39):.0f} hours" in flat
    assert round(hours(pages["cases"], 546) + hours(articles["cases"], 39)) == 16
    assert round(hours(pages["cases"], 627) + hours(articles["cases"], 59)) == 19
    assert "about sixteen hours" in flat and "about nineteen at the means" in flat

    # Counts of the parts and of the pilot's selection that the prose gives.
    reserve = registered["bases"]["conditionalqa"]["parts"]["reserve"]
    assert reserve["cases"] == reserve["not_answerable"] + reserve["primary"] + 1
    assert f"{reserve['cases']} = {reserve['not_answerable']} + {reserve['primary']} + 1" in flat
    several = sum(
        part["primary_with_evidence_in_several_sections"]
        for part in registered["bases"]["conditionalqa"]["parts"].values()
    )
    assert f"{several:,} questions in the three parts" in flat
    of_pilot = Counter(pages["several_sections_by_document"])
    assert sorted(of_pilot) == [0, 1, 2]
    assert f"{of_pilot[2]} clusters of two questions and {of_pilot[1]} of one" in flat
    # The registered MDE of our own holdout, which the section sets the bases against.
    for line in (
        "| holdout | all cases | 64 | 18 | 0.224 |",
        "| holdout | cases with gold evidence | 51 | 18 | 0.229 |",
    ):
        assert line in spec
    assert "The registered MDE of our own holdout is 0.224 to 0.229" in flat
