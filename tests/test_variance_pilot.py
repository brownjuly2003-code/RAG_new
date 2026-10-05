"""The variance pilot on fixture runs; no model, no network, no real run."""

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import devset_split as split
from evaluation import power
from scripts import production_baseline as baseline
from scripts import production_parity as parity
from scripts import variance_pilot as pilot

CORPUS = "c" * 64
REFUSAL = "needs-refusal/clarification"
TEXT = {
    "a.md": "Смена принимает груз по накладной и сверяет число мест с манифестом.",
    "b.md": "Акт осмотра упаковки подписывает кладовщик склада.",
    "c.md": "Опасный груз хранят в отдельной зоне под замком.",
    "d.md": "Температурный груз выдают только по журналу холодной цепи.",
}
FILLER = "Журнал смены хранится у начальника смены три года."
# The index of the fixture: chunk 0 holds the span of a.md, chunk 1 is a.md without it, …
CHUNKS = [
    ("a.md", TEXT["a.md"]),
    ("a.md", FILLER),
    ("b.md", TEXT["b.md"]),
    ("c.md", TEXT["c.md"]),
    ("d.md", TEXT["d.md"]),
    ("e.md", FILLER),
]
FAMILIES = {
    "F1": ["a.md", "b.md"],
    "F2": ["c.md"],
    "F3": ["d.md"],
    "F4": ["e.md"],
    "F5": ["f.md", "g.md"],
    "F6": ["x.md"],
    "F7": ["y.md"],
    "F8": ["z.md"],
}


def revision(source: str) -> str:
    return baseline.text_sha(source)


def verified_case(case_id: str, primary_class: str, documents: list[str], critical=()) -> dict:
    spans, facts = [], []
    if primary_class != REFUSAL:
        for number, source in enumerate(documents, 1):
            spans.append(
                {
                    "span_id": f"{case_id}-E{number}",
                    "source_id": source,
                    "source_revision": revision(source),
                    "corpus_version": CORPUS,
                    "char_start": 0,
                    "char_end": len(TEXT[source]),
                    "normalized_text": TEXT[source],
                }
            )
            facts.append({"text": f"факт {source}", "source_quote": TEXT[source][6:30]})
    if primary_class == "aggregation":
        facts.append({"text": "итог по двум документам", "derived": True})
    return {
        "case_id": case_id,
        "question": f"Что сказано в правилах про {case_id}?",
        "primary_class": primary_class,
        "documents": documents,
        "evidence_spans": spans,
        "required_evidence_groups": [
            {"group_id": f"{case_id}-G{number}", "alternatives": [found["span_id"]]}
            for number, found in enumerate(spans, 1)
        ],
        "required_facts": facts,
        "critical_facts": [facts[index] for index in critical],
    }


PILOT = [
    verified_case("P1", "single-doc", ["a.md"]),
    verified_case("P2", "multi-doc", ["a.md", "b.md"], critical=[1]),
    verified_case("P3", "single-doc", ["c.md"]),
    verified_case("P4", "aggregation", ["c.md", "d.md"]),
    verified_case("P5", REFUSAL, ["e.md"]),
]


def place(position: int, primary_class: str, seed: str | None, partner: str | None = None) -> dict:
    return {
        "position": position,
        "primary_class": primary_class,
        "seed": {"source_id": seed} if seed else None,
        "partner": {"source_id": partner} if partner else None,
    }


# Development: {P1, P2}, {P3, P4}, {P5, position-1}, {position-2}.
# Holdout: {position-1, position-2}, {position-3, position-4}; position 5 found no section.
SPLIT = {
    "splits": {
        "development": {
            "positions": [place(1, "single-doc", "e.md"), place(2, "multi-doc", "f.md", "g.md")],
            "cluster_sizes": [2, 2, 2, 1],
        },
        "holdout": {
            "positions": [
                place(1, "multi-doc", "x.md", "y.md"),
                place(2, "single-doc", "x.md"),
                place(3, REFUSAL, "z.md"),
                place(4, "single-doc", "z.md"),
                place(5, "single-doc", None),
            ],
            "cluster_sizes": [2, 2],
        },
    }
}


def document(source: str, text: str, index: int, expanded: bool = False) -> dict:
    metadata: dict[str, Any] = {"source": source, "chunk_index": index}
    if expanded:
        metadata["parent_expanded"] = True
    return {"text": text, "text_sha256": baseline.text_sha(text), "metadata": metadata}


def row(pool: list[int], sent: list[dict]) -> dict:
    return {
        "status": "ok",
        "pool": pool,
        "ranked": pool[:5],
        "seed_documents": [],
        "documents": sent,
        "sent_context_sha256": baseline.text_sha("\n\n".join(d["text"] for d in sent)),
    }


A, B, C = (
    document(name, TEXT[name], index) for name, index in (("a.md", 0), ("b.md", 2), ("c.md", 3))
)
CONTROL_ROWS = {
    "P1": row([1, 5], [document("a.md", FILLER, 1)]),
    "P2": row([0, 2], [A, B]),
    "P3": row([3], [C]),
    "P4": row([3], [C]),
}
ROWS = {
    "control": CONTROL_ROWS,
    # A wider pool reaches the span of P1, which expansion then sends, and the second span of P4.
    "pool30": {
        **CONTROL_ROWS,
        "P1": row([1, 5, 0], [document("a.md", f"{FILLER}\n\n{TEXT['a.md']}", 1, expanded=True)]),
        "P4": row([3, 4], [C]),
    },
    # Fewer sent documents drop the second document of P2 with its critical fact.
    "sent3": {**CONTROL_ROWS, "P2": row([0, 2], [A])},
}


class World:
    """The registered files of a fixture pilot and the evidence directories of its arms."""

    def __init__(self, root: Path, chunks: list[tuple[str, str]] | None = None):
        self.root = root
        self.verified = root / "verified.jsonl"
        self.questions = root / "questions.jsonl"
        self.families = root / "families.json"
        self.registered = root / "split.json"
        self.archive = root / "chunks.json.gz"
        self.verified.write_text(
            "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in PILOT),
            encoding="utf-8",
        )
        self.questions.write_text(pilot.gold_questions(PILOT), encoding="utf-8", newline="\n")
        register = {
            "families": [
                {"family_id": family, "members": [{"source_id": name} for name in names]}
                for family, names in FAMILIES.items()
            ]
        }
        self.families.write_text(json.dumps(register), encoding="utf-8")
        self.registered.write_text(json.dumps(SPLIT), encoding="utf-8")
        packed = [
            {"page_content": text, "metadata": {"source": name}} for name, text in chunks or CHUNKS
        ]
        self.archive.write_bytes(gzip.compress(json.dumps({"chunks": packed}).encode(), mtime=0))
        self.directories: dict[str, Path] = {}

    def manifest(self, name: str, **changes: Any) -> dict:
        moved = pilot.ARMS[name]
        value = {
            "cases": [
                {"case_id": case["case_id"], "query": case["question"], "subset": pilot.SUBSET}
                for case in PILOT
                if case["evidence_spans"]
            ],
            "code_sha": "c0de",
            "source_sha256": "tree",
            "runtime": {"python": "3.11"},
            "index_receipt_sha256": "receipt",
            "source_manifest_sha256": "sources",
            "chunker_version": "fixture-chunker",
            "llm": {"model": "fixture-llm"},
            "reranker": {"model": "fixture-reranker"},
            # The host path of the case file is the run's own; only its hash is compared.
            "datasets": {
                pilot.SUBSET: {"path": f"/host/{name}/q.jsonl", "sha256": "q", "count": 4}
            },
            "config": {"retrieval_top_k": 20, "rerank_top_k": 5, "rrf_k": 60, **moved},
            "source_manifest": {
                "corpus_sha256": CORPUS,
                "files": [{"name": name, "sha256": revision(name)} for name in TEXT],
            },
            "index_receipt": {"corpus_sha256": parity.file_sha(self.archive)},
            "ledger_entry": {"task": pilot.TASK},
            **changes,
        }
        if moved and "config_overrides" not in changes:
            value["config_overrides"] = moved
        return value

    def arm(self, name: str, rows: dict[str, dict] | None = None, **changes: Any) -> Path:
        """Write a finished run of one arm and export it."""
        run = self.root / "runs" / name
        manifest = self.manifest(name, **changes)
        identity = parity.digest(manifest)
        parity.write_new(run / "manifest.json", manifest)
        parity.write_new(run / "registration.json", {"manifest_sha256": identity})
        parity.save_stage(run / "report.json", {"total_cases": len(manifest["cases"])}, identity)
        for case in manifest["cases"]:
            cid = case["case_id"]
            parity.save_stage(run / "grade" / f"{cid}.json", (rows or ROWS[name])[cid], identity)
        out = self.root / "evidence" / name
        pilot.export(run, out)
        self.directories[name] = out
        return out

    def inputs(self, **paths: Path) -> dict[str, Path]:
        return {
            "verified": self.verified,
            "questions": self.questions,
            "families": self.families,
            "registered": self.registered,
            "archive": self.archive,
            **paths,
        }

    def hashes(self, **paths: Path) -> dict[str, str]:
        """What the fixture registers: the files it measures on, as they are named."""
        inputs = self.inputs(**paths)
        return {
            "verified": parity.file_sha(inputs["verified"]),
            "questions": parity.file_sha(inputs["questions"]),
            "families": parity.file_sha(inputs["families"]),
            "split": parity.file_sha(inputs["registered"]),
        }

    def measure(self, sha256: dict[str, str] | None = None, **paths: Path) -> dict:
        return pilot.measure(
            self.directories, sha256=sha256 or self.hashes(**paths), **self.inputs(**paths)
        )


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


@pytest.fixture
def measured(world):
    for name in pilot.ARMS:
        world.arm(name)
    return world.measure()


def test_export_adds_the_pool_and_the_document_of_every_sent_text(world):
    out = world.arm("pool30")
    addresses = parity.read(out / "addresses.json")
    assert addresses["addresses_version"] == pilot.ADDRESSES_VERSION
    assert addresses["run_sha256"] == parity.digest(parity.read(out / "manifest.json"))
    first = addresses["cases"][0]
    assert first["case_id"] == "P1" and first["pool"] == [1, 5, 0] and first["ranked"] == [1, 5, 0]
    assert first["sent"] == [
        {
            "text_sha256": baseline.text_sha(f"{FILLER}\n\n{TEXT['a.md']}"),
            "source_id": "a.md",
            "chunk_index": 1,
            "parent_expanded": True,
        }
    ]
    assert {path.name for path in out.iterdir()} == {
        "manifest.json",
        "registration.json",
        "collector-report.json",
        "contexts.json.gz",
        "addresses.json",
    }
    # A second export of the same run changes nothing; another run in the directory is refused.
    before = (out / "addresses.json").read_bytes()
    pilot.export(world.root / "runs/pool30", out)
    assert (out / "addresses.json").read_bytes() == before
    with pytest.raises(FileExistsError):
        pilot.export(world.root / "runs/pool30", world.arm("control"))


def test_gold_metrics_of_every_case_and_arm(measured):
    def values(case_id: str, arm: str) -> list[float]:
        return [measured["cases"][case_id][arm][metric] for metric in pilot.gold.METRICS]

    assert values("P1", "control") == [0.0, 0.0, 0.0]
    assert values("P1", "pool30") == [1.0, 1.0, 1.0]
    assert values("P2", "control") == [1.0, 1.0, 1.0]
    assert values("P2", "sent3") == [1.0, 0.0, 0.5]
    assert values("P4", "control") == [0.5, 0.0, pytest.approx(1 / 3)]
    assert values("P4", "pool30") == [1.0, 0.0, pytest.approx(1 / 3)]
    assert measured["cases"]["P4"]["control"]["facts_in_context"] == [True, False, False]
    assert measured["cases"]["P1"]["pool30"]["spans_in_sent"] == ["P1-E1"]
    assert list(measured["cases"]) == ["P1", "P2", "P3", "P4"]
    assert measured["index_bound"] == {
        "spans": 6,
        "held_whole_by_a_chunk": 6,
        "held_by_no_chunk": [],
        "held_by_several_chunks": {},
    }


def test_spans_that_no_chunk_or_several_chunks_hold_are_named(tmp_path):
    # The text of a.md recurs in a seventh chunk; the chunk of b.md lost its text.
    chunks = [*CHUNKS, ("a.md", f"{FILLER} {TEXT['a.md']}")]
    chunks[2] = ("b.md", FILLER)
    world = World(tmp_path, chunks)
    for name in pilot.ARMS:
        world.arm(name)
    assert world.measure()["index_bound"] == {
        "spans": 6,
        "held_whole_by_a_chunk": 5,
        "held_by_no_chunk": ["P2-E2"],
        "held_by_several_chunks": {"P1-E1": [0, 6], "P2-E1": [0, 6]},
    }


def test_paired_differences_against_the_control(measured):
    wider = measured["pilot"]["pool30"]
    assert {key: wider[key] for key in wider if key != "metrics"} == {
        "pairs": 4,
        "lost_pairs": [],
        "cases_with_another_pool": 2,
        "cases_with_another_context": 1,
        "critical_facts_lost": 0,
        "cases_with_a_critical_fact_lost": 0,
        "variance_used": True,
        "variance_unused_because": [],
    }
    recall = wider["metrics"]["evidence_recall_pool"]
    assert recall["n"] == 4 and recall["clusters"] == 2 and recall["cluster_sizes"] == [2, 2]
    assert recall["mean"] == pytest.approx(0.375)
    assert recall["variance"] == pytest.approx(0.6875 / 3)
    assert (recall["control_mean"], recall["arm_mean"]) == (0.625, 1.0)
    assert (recall["differing_pairs"], recall["gains"], recall["losses"]) == (2, 2, 0)
    assert wider["metrics"]["all_evidence_coverage"]["variance"] == pytest.approx(0.25)

    fewer = measured["pilot"]["sent3"]
    assert fewer["cases_with_another_pool"] == 0 and fewer["cases_with_another_context"] == 1
    assert fewer["critical_facts_lost"] == 1 and fewer["cases_with_a_critical_fact_lost"] == 1
    assert fewer["metrics"]["evidence_recall_pool"]["differing_pairs"] == 0
    assert fewer["metrics"]["all_evidence_coverage"]["mean"] == pytest.approx(-0.25)
    assert fewer["metrics"]["fact_coverage"]["variance"] == pytest.approx(0.0625)
    assert fewer["metrics"]["fact_coverage"]["losses"] == 1


def test_cluster_sizes_of_every_population_follow_the_whole_split(measured):
    assert measured["cluster_sizes"] == {
        "development": {
            "all cases": [2, 2, 2, 1],
            "cases with gold evidence": [2, 2, 1, 1],
            "unresolvable cases": [1],
        },
        "holdout": {
            "all cases": [2, 2],
            "cases with gold evidence": [2, 1],
            "unresolvable cases": [1],
        },
    }
    assert measured["zero_loss_cases"] == power.cases_for_zero_loss_bound() == 149


def test_tables_read_the_grid_for_every_population_and_the_pilot_for_gold_evidence(measured):
    rows = measured["tables"]
    grid = [entry for entry in rows if entry["source"] == "grid"]
    # A population of one cluster has no interval and so no row.
    assert {(entry["split"], entry["population"]) for entry in grid} == {
        ("development", "all cases"),
        ("development", "cases with gold evidence"),
        ("holdout", "all cases"),
        ("holdout", "cases with gold evidence"),
    }
    assert {entry["variance"] for entry in grid} == set(pilot.SCENARIO_VARIANCES)
    first = next(
        entry
        for entry in grid
        if (entry["split"], entry["population"], entry["variance"], entry["correlation"])
        == ("development", "all cases", 0.05, "independent cases")
    )
    expected = power.scenario(0.05, [2, 2, 2, 1], 0.0, differing_share=0.05)
    assert {key: first[key] for key in expected} == expected
    together = next(
        entry
        for entry in grid
        if (entry["split"], entry["population"], entry["variance"], entry["intraclass_correlation"])
        == ("holdout", "all cases", 0.2, 1.0)
    )
    assert together["correlation"] == "a cluster moves as one case"
    assert together["design_effect"] == 2.0
    # Clusters that move as one case each are the sample: such a row takes the Student quantile.
    assert together == {
        "source": "grid",
        "split": "holdout",
        "population": "all cases",
        "correlation": "a cluster moves as one case",
        **power.scenario(0.2, [2, 2], 1.0, differing_share=0.2, student=True),
    }

    measured_rows = [entry for entry in rows if entry["source"] != "grid"]
    assert {entry["population"] for entry in measured_rows} == {"cases with gold evidence"}
    assert {(entry["source"], entry["metric"]) for entry in measured_rows} == {
        ("pilot:pool30", "evidence_recall_pool"),
        ("pilot:pool30", "all_evidence_coverage"),
        ("pilot:pool30", "fact_coverage"),
        # No pair of the sent3 arm differs in the pool: there is no spread to project.
        ("pilot:sent3", "all_evidence_coverage"),
        ("pilot:sent3", "fact_coverage"),
    }
    recall = next(
        entry
        for entry in measured_rows
        if (entry["source"], entry["metric"], entry["split"], entry["intraclass_correlation"])
        == ("pilot:pool30", "evidence_recall_pool", "holdout", 1.0)
    )
    variance = measured["pilot"]["pool30"]["metrics"]["evidence_recall_pool"]["variance"]
    assert recall == {
        "source": "pilot:pool30",
        "metric": "evidence_recall_pool",
        "split": "holdout",
        "population": "cases with gold evidence",
        "correlation": "a cluster moves as one case",
        **power.scenario(variance, [2, 1], 1.0, differing_share=0.5, student=True),
    }


def test_provenance_names_the_runs_the_inputs_and_the_rules(world, measured):
    provenance = measured["provenance"]
    assert provenance["code_sha"] == "c0de" and provenance["corpus_sha256"] == CORPUS
    assert provenance["config"] == {"retrieval_top_k": 20, "rerank_top_k": 5, "rrf_k": 60}
    assert provenance["verified_cases_sha256"] == parity.file_sha(world.verified)
    assert provenance["questions_sha256"] == parity.file_sha(world.questions)
    assert provenance["split_sha256"] == parity.file_sha(world.registered)
    assert provenance["families_sha256"] == parity.file_sha(world.families)
    assert provenance["match_rule"] == "verified-gold/text-containment-v1"
    assert provenance["fact_label_rule"] == "pilot-claim-quote-v2"
    assert set(provenance["measure_code_sha256"]) == set(pilot.CODE_FILES)
    assert measured["version"] == pilot.VERSION and measured["task"] == pilot.TASK
    arms = measured["arms"]
    assert {name: arm["moved"] for name, arm in arms.items()} == pilot.ARMS
    assert all(arm["collected"] == 4 and arm["excluded"] == [] for arm in arms.values())
    assert len({arm["run_sha256"] for arm in arms.values()}) == 3


def test_a_perturbation_with_a_lost_pair_is_described_and_not_used(world):
    excluded = {"status": "excluded", "exclusion": {"case_id": "P3", "stage": "grade"}}
    world.arm("control")
    world.arm("pool30")
    world.arm("sent3", rows={**ROWS["sent3"], "P3": excluded})
    document_ = world.measure()
    assert document_["arms"]["sent3"]["excluded"] == ["P3"]
    assert document_["cases"]["P3"]["sent3"] is None
    comparison = document_["pilot"]["sent3"]
    assert comparison["pairs"] == 3 and comparison["lost_pairs"] == ["P3"]
    assert comparison["metrics"]["all_evidence_coverage"]["n"] == 3
    assert comparison["variance_used"] is False
    assert comparison["variance_unused_because"] == [pilot.LOST_PAIR]
    assert document_["pilot"]["pool30"]["variance_used"] is True
    # Its spread gives no row of the tables and no variance of a registered MDE.
    assert {entry["source"] for entry in document_["tables"]} == {"grid", "pilot:pool30"}
    assert {entry["variance_source"] for entry in document_["registered_mde"]} == {
        "grid",
        "pilot:pool30",
    }


def test_a_match_that_finds_nothing_is_not_read_as_a_perturbation_that_moved_nothing(tmp_path):
    # The index names its documents another way than the labels do: no span is found anywhere.
    world = World(tmp_path, [(f"uploads/{name}", text) for name, text in CHUNKS])
    for name in pilot.ARMS:
        world.arm(name)
    document_ = world.measure()
    assert document_["index_bound"]["held_whole_by_a_chunk"] == 0
    for comparison in document_["pilot"].values():
        assert comparison["variance_used"] is False
        assert comparison["variance_unused_because"] == [
            pilot.NO_SPAN_IN_INDEX,
            pilot.NO_SPAN_IN_CONTROL,
        ]
    assert {entry["source"] for entry in document_["tables"]} == {"grid"}
    assert {entry["variance_source"] for entry in document_["registered_mde"]} == {"grid"}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"code_sha": "0ther"}, "not the control's code"),
        ({"reranker": {"model": "another"}}, "not the control's code"),
        ({"config": {"retrieval_top_k": 30, "rerank_top_k": 5, "rrf_k": 61}}, "not the control's"),
        ({"config_overrides": {"retrieval_top_k": 40}}, "does not move what the arm registers"),
        ({"config": {"retrieval_top_k": 20, "rerank_top_k": 5, "rrf_k": 60}}, "does not move"),
    ],
)
def test_an_arm_that_differs_in_more_than_its_registered_count_is_refused(world, changes, message):
    world.arm("control")
    world.arm("sent3")
    world.arm("pool30", **changes)
    with pytest.raises(ValueError, match=message):
        world.measure()


def test_the_pilot_is_the_control_and_both_registered_perturbations(world):
    message = "the control and its two registered perturbations"
    world.arm("pool30")
    world.arm("sent3")
    with pytest.raises(ValueError, match=message):
        world.measure()
    world.arm("control")
    world.directories["pool80"] = world.directories["pool30"]
    with pytest.raises(ValueError, match=message):
        world.measure()
    # One perturbation beside the control is not the pilot: the wider spread could be chosen.
    del world.directories["pool80"], world.directories["sent3"]
    with pytest.raises(ValueError, match=message):
        world.measure()


def test_a_file_other_than_the_registered_one_is_refused(world):
    for name in pilot.ARMS:
        world.arm(name)
    # Without hashes of its own the fixture is measured against the registered files.
    with pytest.raises(ValueError, match="verified: not the registered file"):
        pilot.measure(world.directories, **world.inputs())
    for name in ("verified", "questions", "families", "split"):
        with pytest.raises(ValueError, match=f"{name}: not the registered file"):
            world.measure(sha256={**world.hashes(), name: "0" * 64})


def test_the_registered_hashes_are_those_of_the_files_in_the_repository():
    assert pilot.REGISTERED_SHA256 == {
        "verified": parity.file_sha(pilot.VERIFIED),
        "questions": parity.file_sha(pilot.QUESTIONS),
        "families": parity.file_sha(pilot.FAMILIES),
        "split": parity.file_sha(split.REGISTERED),
    }


def test_addresses_of_another_run_or_of_other_contexts_are_refused(world):
    world.arm("control")
    out = world.arm("sent3")
    addresses = parity.read(out / "addresses.json")
    (out / "addresses.json").write_text(
        json.dumps({**addresses, "run_sha256": "0" * 64}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="belongs to another run"):
        world.measure()
    addresses["cases"][1]["sent"][0]["text_sha256"] = baseline.text_sha("another text")
    (out / "addresses.json").write_text(json.dumps(addresses), encoding="utf-8")
    with pytest.raises(ValueError, match="disagrees with the contexts of P2"):
        world.measure()
    addresses["cases"] = addresses["cases"][:-1]
    (out / "addresses.json").write_text(json.dumps(addresses), encoding="utf-8")
    with pytest.raises(ValueError, match="does not list the cases"):
        world.measure()


def test_labels_of_another_corpus_and_another_chunk_archive_are_refused(world, tmp_path):
    for name in pilot.ARMS:
        world.arm(name)
    moved = [json.loads(json.dumps(case)) for case in PILOT]
    moved[0]["evidence_spans"][0]["source_revision"] = "another revision"
    relabelled = tmp_path / "relabelled.jsonl"
    relabelled.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in moved), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="P1: labelled on another corpus"):
        world.measure(verified=relabelled)
    other = tmp_path / "other.json.gz"
    other.write_bytes(gzip.compress(json.dumps({"chunks": []}).encode(), mtime=0))
    with pytest.raises(ValueError, match="not the one the index was built from"):
        world.measure(archive=other)


def test_runs_over_other_questions_and_a_stale_question_file_are_refused(world, tmp_path):
    for name in pilot.ARMS:
        world.arm(name)
    stale = tmp_path / "stale.jsonl"
    stale.write_text(pilot.gold_questions(PILOT[:3]), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="not the verified cases with gold spans"):
        world.measure(questions=stale)
    fewer = tmp_path / "fewer.jsonl"
    fewer.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in PILOT[:3]),
        encoding="utf-8",
    )
    stale.write_text(pilot.gold_questions(PILOT[:3]), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="not the registered pilot"):
        world.measure(verified=fewer, questions=stale)


def test_a_run_of_another_task_is_refused(world):
    for name in pilot.ARMS:
        world.arm(name, ledger_entry={"task": "T-68/2.5a"})
    with pytest.raises(ValueError, match="not the registered pilot"):
        world.measure()


def test_clusters_that_differ_from_the_registered_split_are_refused(world, tmp_path):
    for name in pilot.ARMS:
        world.arm(name)
    changed = json.loads(json.dumps(SPLIT))
    changed["splits"]["holdout"]["cluster_sizes"] = [3, 1]
    other = tmp_path / "other-split.json"
    other.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="holdout: the clusters differ"):
        world.measure(registered=other)


def test_cli_exports_measures_and_refuses_to_overwrite_another_document(world, capsys, monkeypatch):
    arms = []
    for name in pilot.ARMS:
        out = world.arm(name)
        arms += ["--arm", f"{name}={out}"]
    run, again = world.root / "runs/control", world.root / "again"
    assert pilot.main(["export", "--run", str(run), "--out", str(again)]) == 0
    assert "addresses_sha256" in json.loads(capsys.readouterr().out)
    target = world.root / "pilot.json"
    command = ["measure", *arms, "--archive", str(world.archive), "--out", str(target)]
    # The command line names no registered file: the fixture pilot is refused as it stands.
    with pytest.raises(ValueError, match="not the registered pilot"):
        pilot.main(command)
    for option in ("--verified", "--questions", "--families", "--split"):
        with pytest.raises(SystemExit):
            pilot.main([*command, option, str(world.verified)])
    capsys.readouterr()
    # The registered files of the fixture stand in for those of the repository.
    monkeypatch.setattr(pilot, "VERIFIED", world.verified)
    monkeypatch.setattr(pilot, "QUESTIONS", world.questions)
    monkeypatch.setattr(pilot, "FAMILIES", world.families)
    monkeypatch.setattr(split, "REGISTERED", world.registered)
    monkeypatch.setattr(pilot, "REGISTERED_SHA256", world.hashes())
    assert pilot.main(command) == 0
    assert "pool30 evidence_recall_pool" in capsys.readouterr().out
    assert json.loads(target.read_text(encoding="utf-8")) == world.measure()
    assert pilot.main(command) == 0
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        pilot.main(command)
    with pytest.raises(SystemExit):
        pilot.main(["measure", "--arm", "control", "--out", str(target)])


def test_question_file_is_the_verified_cases_with_gold_spans():
    cases = pilot.read_lines(pilot.VERIFIED)
    text = pilot.QUESTIONS.read_text(encoding="utf-8")
    assert text == pilot.gold_questions(cases)
    rows = pilot.read_lines(pilot.QUESTIONS)
    assert len(rows) == 24 and all(set(entry) == {"case_id", "question"} for entry in rows)
    assert [entry["case_id"] for entry in rows] == [
        case["case_id"] for case in cases if case["evidence_spans"]
    ]
    assert pilot.main(["cases"]) == 0


def test_the_collector_accepts_the_question_file_and_the_arms():
    datasets, cases = baseline.case_file(pilot.QUESTIONS, pilot.SUBSET)
    assert datasets[pilot.SUBSET]["count"] == len(cases) == 24
    assert all(set(case) == {"case_id", "query", "subset"} for case in cases)
    assert pilot.ARMS[pilot.CONTROL] == {}
    for name, moved in pilot.ARMS.items():
        pairs = [f"{key}={value}" for key, value in moved.items()]
        assert baseline.given_settings(pairs) == moved, name
        assert len(moved) == (name != pilot.CONTROL)


def test_populations_of_the_registered_split():
    cases = pilot.read_lines(pilot.VERIFIED)
    graph, sizes = pilot.populations(
        parity.read(split.REGISTERED), split.family_index(parity.read(pilot.FAMILIES)), cases
    )
    shape = {
        name: {population: (sum(found), len(found)) for population, found in by_population.items()}
        for name, by_population in sizes.items()
    }
    assert shape == {
        "development": {
            "all cases": (60, 37),
            "cases with gold evidence": (48, 32),
            "unresolvable cases": (12, 11),
        },
        "holdout": {
            "all cases": (64, 18),
            "cases with gold evidence": (51, 18),
            "unresolvable cases": (13, 12),
        },
    }
    assert len(graph) == 60
    # The 24 pilot cases the arms run on, as the development split clusters them.
    ran = {entry["case_id"] for entry in pilot.read_lines(pilot.QUESTIONS)}
    clusters = [
        [case for case in cluster if case in ran] for cluster in pilot.ruler.family_clusters(graph)
    ]
    assert sorted((len(cluster) for cluster in clusters if cluster), reverse=True) == [
        *(4, 4, 2, 2, 2),
        *([1] * 10),
    ]


def test_registered_mde_is_the_upper_end_and_a_pilot_can_only_raise_it():
    gold_sizes, all_sizes = [2, 1, 1], [2, 2, 1]
    sizes = {
        "development": {
            "all cases": all_sizes,
            pilot.GOLD_EVIDENCE: gold_sizes,
            "unresolvable cases": [1],
        }
    }

    def stats(variance: float, icc: float | None) -> dict:
        return {"variance": variance, "intraclass_correlation": icc, "differing_share": 0.5}

    comparisons: dict[str, dict[str, Any]] = {
        "pool30": {
            "metrics": {
                "evidence_recall_pool": stats(0.04, 0.3),
                "all_evidence_coverage": stats(0.25, 0.3),
                "fact_coverage": None,
            }
        },
        "sent3": {
            "metrics": {
                "evidence_recall_pool": stats(0.09, None),
                "all_evidence_coverage": stats(0.25, None),
                "fact_coverage": None,
            }
        },
    }
    rows = {entry["metric"]: entry for entry in pilot.registered_mde(sizes, comparisons)}
    assert list(rows) == list(pilot.DECIDING)
    assert {entry["split"] for entry in rows.values()} == {"development"}

    # Variances below the grid value do not lower the MDE: the grid stands, and the row is the
    # scenario at correlation 1 with the Student quantile.
    recall = rows["evidence_recall_pool"]
    published = power.scenario(0.10, gold_sizes, 1.0, differing_share=0.10, student=True)
    assert recall["variance_source"] == "grid"
    assert {key: recall[key] for key in published} == published
    assert recall["mde_independent_cases"] == power.scenario(0.10, gold_sizes, 0.0)["mde"]
    assert recall["correlation_estimate"] == 0.3
    assert recall["mde_at_correlation_estimate"] == power.scenario(0.10, gold_sizes, 0.3)["mde"]
    assert recall["mde_independent_cases"] < recall["mde_at_correlation_estimate"] < recall["mde"]

    # A larger variance raises it. Two perturbations give one variance: the row names the one
    # with the larger correlation, and an absent estimate reads as 1.
    coverage = rows["all_evidence_coverage"]
    assert coverage["variance_source"] == "pilot:sent3"
    assert (coverage["variance"], coverage["differing_share"]) == (0.25, 0.5)
    assert coverage["correlation_estimate"] is None
    assert coverage["mde_at_correlation_estimate"] is None
    assert coverage["mde"] == power.scenario(0.25, gold_sizes, 1.0, student=True)["mde"]
    assert coverage["mde"] > recall["mde"]

    # A metric the pilot does not measure reads the grid on its own population.
    judged = rows["precision_at_5"]
    assert judged["variance_source"] == "grid" and (judged["n"], judged["clusters"]) == (5, 3)
    assert judged["mde"] == power.scenario(0.10, all_sizes, 1.0, student=True)["mde"]

    # One cluster gives no interval: the row says how many cases and clusters, and no MDE.
    alone = rows["abstention_correct"]
    assert (alone["n"], alone["clusters"]) == (1, 1) and "mde" not in alone

    # A perturbation whose numbers are not used gives no variance and no estimate.
    comparisons["sent3"]["variance_used"] = False
    rows = {entry["metric"]: entry for entry in pilot.registered_mde(sizes, comparisons)}
    assert rows["all_evidence_coverage"]["variance_source"] == "pilot:pool30"
    assert rows["all_evidence_coverage"]["correlation_estimate"] == 0.3
    assert rows["all_evidence_coverage"]["mde"] == coverage["mde"]


def test_registered_mde_of_the_fixture_pilot(measured):
    rows = {(entry["split"], entry["metric"]): entry for entry in measured["registered_mde"]}
    assert set(rows) == {
        (name, metric) for name in ("development", "holdout") for metric in pilot.DECIDING
    }
    recall = rows[("holdout", "evidence_recall_pool")]
    assert recall["variance_source"] == "pilot:pool30"
    assert recall["variance"] == pytest.approx(0.6875 / 3)
    assert recall["population"] == "cases with gold evidence" and recall["n"] == 3
    assert recall["intraclass_correlation"] == 1.0 and recall["critical"] == power.critical(2)
    assert rows[("development", "action_correct")]["variance_source"] == "grid"
    assert rows[("development", "action_correct")]["variance"] == pilot.REGISTERED_GRID_VARIANCE
    # A row over answered cases is registered at the largest denominator it can have.
    assert rows[("development", "faithfulness")]["population"] == "all cases"
    assert rows[("development", "answer_fact_coverage")]["population"] == pilot.GOLD_EVIDENCE


def test_spec_registers_what_the_pilot_applies():
    spec = (pilot.ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    section = spec[
        spec.index("## Variance pilot and sizes of plan step 1.3c") : spec.index(
            "## Acceptance contract (plan track 4)"
        )
    ]
    flat = " ".join(section.split())
    for digest in pilot.REGISTERED_SHA256.values():
        assert f"`{digest}`" in flat
    assert f"`{pilot.gold.MATCH_RULE}`" in flat
    for name, moved in pilot.ARMS.items():
        assert f"`{name}`" in flat
        for setting, count in moved.items():
            assert f"`{name}`, with `{setting}` {count} in place of" in flat
    assert " / ".join(f"{value:.2f}" for value in pilot.SCENARIO_VARIANCES) in flat
    assert f"the grid value {pilot.REGISTERED_GRID_VARIANCE:.2f}" in flat
    assert f"only from {power.cases_for_zero_loss_bound()} cases on" in flat
    for metric in pilot.DECIDING:
        assert f"`{metric}`" in flat

    # The sizes and the MDE registered before the pilot are what the code gives for the split.
    _, sizes = pilot.populations(
        parity.read(split.REGISTERED),
        split.family_index(parity.read(pilot.FAMILIES)),
        pilot.read_lines(pilot.VERIFIED),
    )
    assert "60 in 37 clusters in development, 64 in 18 in the holdout" in flat
    assert "48 in 32 and 51 in 18" in flat and "12 in 11 and 13 in 12" in flat
    rows = {
        (entry["split"], entry["population"]): entry for entry in pilot.registered_mde(sizes, {})
    }
    assert len(rows) == 6
    for (name, population), entry in rows.items():
        assert entry["variance_source"] == "grid" and entry["intraclass_correlation"] == 1.0
        line = (
            f"| {name} | {population} | {entry['n']} | {entry['clusters']} "
            f"| {entry['mde']:.3f} | {entry['mde_independent_cases']:.3f} |"
        )
        assert line in section, line
