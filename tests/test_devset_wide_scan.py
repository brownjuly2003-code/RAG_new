"""The wide scan covers the whole index with both lanes and refuses a broken index contract."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from scripts import devset_wide_scan
from scripts.production_embeddings import prepare_embeddings
from vectordb.embedder_manifest import EmbedderManifest

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = 50
CODE_SHA = "b" * 40
# Lexical: «альфа» is in chunks 2, 40 (twice) and 41. Dense: the vector points at chunk 0.
ALPHA = "Альфа?"
# Lexical: «общий» is in the 22 chunks 10..31, all of one length. Dense: points at chunk 49.
COMMON = "общий порядок"
# Lexical: no token of the question is in the archive. Dense: 1° past chunk 25.
ABSENT = "Зета — что это? "


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(revision: str = "a" * 40) -> EmbedderManifest:
    return EmbedderManifest(
        backend="local",
        model_id="fixture",
        revision=revision,
        revision_source="hf_snapshot",
        dimension=2,
        query_prompt="",
        document_prompt="",
        normalize=True,
    )


def direction(degrees: float, length: float = 1.0) -> list[float]:
    angle = math.radians(degrees)
    return [length * math.cos(angle), length * math.sin(angle)]


def chunk_vector(index: int) -> list[float]:
    # Chunk 6 repeats the vector of chunk 5: an exact tie in the dense lane.
    return direction(3 * (5 if index == 6 else index))


def chunk_text(index: int) -> str:
    words = [f"документ{index}", f"слово{index}"]
    if index in (2, 41):
        words.append("альфа")
    if index == 40:
        words += ["альфа", "альфа"]
    if 10 <= index <= 31:
        words.append("общий")
    return " ".join(words)


def chunk_source(index: int) -> str:
    return f"doc{index // 5}.md"


class Embedder:
    def __init__(self, revision: str = "a" * 40) -> None:
        self.manifest = manifest(revision)
        self.asked: list[str] = []
        # Query vectors are not unit length: the scan normalises them.
        self.queries = {
            ALPHA: direction(0, 3.0),
            COMMON: direction(3 * 49, 0.5),
            ABSENT: direction(3 * 25 + 1, 2.0),
        }

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [chunk_vector(index) for index in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        self.asked.append(text)
        return self.queries[text]


@dataclass
class Inputs:
    root: Path
    cases: Path
    archive: Path
    checkpoint: Path
    index: Path
    out: Path
    embedder: Embedder

    @property
    def receipt(self) -> Path:
        return self.index / "index-receipt.json"

    def scan(self, **changes: Any) -> dict[str, Any]:
        arguments: dict[str, Any] = dict(
            cases=self.cases,
            archive=self.archive,
            checkpoint=self.checkpoint,
            index=self.index,
            out=self.out,
            code_sha=CODE_SHA,
            embedder=self.embedder,
        )
        arguments.update(changes)
        return devset_wide_scan.wide_scan(**arguments)

    def files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def reseal(self) -> None:
        """Make the receipt name the checkpoint as it is now, so a later check is reached."""
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        receipt["checkpoint_sha256"] = sha(self.checkpoint.read_bytes())
        self.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    def refused(self, match: str, error: type[Exception] = ValueError, **changes: Any) -> None:
        before = self.files()
        with pytest.raises(error, match=match):
            self.scan(**changes)
        assert self.files() == before


@pytest.fixture
def inputs(tmp_path: Path) -> Inputs:
    chunks = [
        {"page_content": chunk_text(index), "metadata": {"source": chunk_source(index)}}
        for index in range(CHUNKS)
    ]
    archive = tmp_path / "chunks.json.gz"
    archive.write_bytes(
        gzip.compress(json.dumps({"chunks": chunks}, ensure_ascii=False).encode("utf-8"), mtime=0)
    )
    checkpoint = tmp_path / "vectors.npz"
    # The checkpoint is written by the production writer, the receipt has build_index's shape.
    prepared = prepare_embeddings(
        [chunk["page_content"] for chunk in chunks],
        Embedder(),
        checkpoint,
        corpus_sha256=sha(archive.read_bytes()),
        batch_size=CHUNKS,
    )
    index = tmp_path / "index"
    index.mkdir()
    receipt = {
        "schema_version": 1,
        "code_sha": "c" * 40,
        "corpus_sha256": prepared["corpus_sha256"],
        "texts_sha256": prepared["texts_sha256"],
        "checkpoint_sha256": prepared["checkpoint_sha256"],
        "embedder_manifest": manifest().as_dict(),
        "collection_name": "rag_docs_aircargo",
        "chunk_count": CHUNKS,
        "configuration": {"hnsw": {"sync_threshold": 1}},
        "chromadb_version": "fixture",
        "evidence_status": "preparation",
    }
    (index / "index-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    cases = tmp_path / "cases.jsonl"
    rows = [
        {"case_id": "case-alpha", "question": ALPHA, "expected_action": "answer"},
        {"case_id": "case-common", "question": COMMON, "expected_action": "clarify"},
        {"case_id": "case-absent", "question": ABSENT, "expected_action": "refuse"},
    ]
    cases.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    return Inputs(
        root=tmp_path,
        cases=cases,
        archive=archive,
        checkpoint=checkpoint,
        index=index,
        out=tmp_path / "scan" / "wide-scan.json",
        embedder=Embedder(),
    )


def damage_checkpoint(inputs: Inputs, damage: str) -> None:
    with np.load(inputs.checkpoint, allow_pickle=False) as saved:
        payload = dict(saved)
    if damage == "partial":
        payload["embeddings"] = payload["embeddings"][:-1]
    elif damage in {"corpus", "texts"}:
        payload[damage + "_sha256"] = "0" * 64
    elif damage == "schema":
        payload["schema_version"] = 2
    elif damage == "manifest":
        payload["embedder_manifest"] = manifest("c" * 40).canonical_json
    elif damage == "width":
        payload["embeddings"] = np.tile(np.array([1.0, 0.0, 0.0], dtype=np.float32), (CHUNKS, 1))
    elif damage == "nan":
        payload["embeddings"][0, 0] = float("nan")
    elif damage == "norm":
        payload["embeddings"][7] *= 2.0
    else:
        raise AssertionError(damage)
    np.savez(inputs.checkpoint, **payload)


def ranks(report: dict[str, Any], case_id: str) -> dict[int, tuple[int | None, int | None]]:
    (case,) = [case for case in report["cases"] if case["case_id"] == case_id]
    return {
        chunk["chunk_index"]: (chunk["lexical_rank"], chunk["dense_rank"])
        for chunk in case["chunks"]
    }


def test_a_chunk_of_one_lane_carries_that_rank_and_a_chunk_of_both_carries_both(
    inputs: Inputs,
) -> None:
    found = ranks(inputs.scan(), "case-alpha")

    assert sorted(found) == [*range(20), 40, 41]
    # Only the lexical lane: chunk 40 is far from the query vector.
    assert found[40] == (1, None)
    # Only the dense lane: chunk 0 has no token of the question.
    assert found[0] == (None, 1)
    # Both lanes: kept once, with both ranks.
    assert found[2] == (2, 3)


def test_a_zero_bm25_score_is_not_taken_and_the_lexical_lane_may_be_shorter(
    inputs: Inputs,
) -> None:
    report = inputs.scan()

    alpha = ranks(report, "case-alpha")
    assert {index: lane[0] for index, lane in alpha.items() if lane[0] is not None} == {
        40: 1,
        2: 2,
        41: 3,
    }
    absent = ranks(report, "case-absent")
    assert sorted(absent) == list(range(16, 36))
    assert all(lexical is None for lexical, _ in absent.values())
    assert (absent[25][1], absent[26][1], absent[24][1], absent[35][1]) == (1, 2, 3, 20)


def test_equal_scores_are_ordered_by_position_in_the_archive(inputs: Inputs) -> None:
    report = inputs.scan()

    alpha = ranks(report, "case-alpha")
    # Dense tie: chunks 5 and 6 hold the same vector.
    assert [alpha[index][1] for index in range(20)] == list(range(1, 21))
    # Lexical tie: chunks 2 and 41 hold «альфа» once in a text of one length.
    assert (alpha[2][0], alpha[41][0]) == (2, 3)
    # 22 chunks tie on «общий»: the lane takes the first 20 of the archive, not 30 and 31.
    common = ranks(report, "case-common")
    assert sorted(common) == list(range(10, 50))
    assert [common[index] for index in range(10, 30)] == [(rank, None) for rank in range(1, 21)]
    assert [common[index] for index in range(30, 50)] == [
        (None, 50 - index) for index in range(30, 50)
    ]


def test_every_case_is_scanned_with_its_question_as_written(inputs: Inputs) -> None:
    report = inputs.scan()

    assert inputs.embedder.asked == [ALPHA, COMMON, ABSENT]
    assert [(case["case_id"], case["question_sha256"]) for case in report["cases"]] == [
        ("case-alpha", sha(ALPHA.encode("utf-8"))),
        ("case-common", sha(COMMON.encode("utf-8"))),
        ("case-absent", sha(ABSENT.encode("utf-8"))),
    ]


def test_the_output_carries_the_registered_fields_and_nothing_else(inputs: Inputs) -> None:
    report = inputs.scan()

    assert json.loads(inputs.out.read_text(encoding="utf-8")) == report
    assert {key: value for key, value in report.items() if key != "cases"} == {
        "schema_version": "devset-wide-scan/v1",
        "lane_size": 20,
        "archive_sha256": sha(inputs.archive.read_bytes()),
        "checkpoint_sha256": sha(inputs.checkpoint.read_bytes()),
        "index_receipt_sha256": sha(inputs.receipt.read_bytes()),
        "cases_sha256": sha(inputs.cases.read_bytes()),
        "embedder_manifest": manifest().as_dict(),
        "code_sha": CODE_SHA,
        "script_sha256": sha(Path(devset_wide_scan.__file__).read_bytes()),
        "chunk_count": CHUNKS,
    }
    for case in report["cases"]:
        assert sorted(case) == ["case_id", "chunks", "question_sha256"]
        indexes = [chunk["chunk_index"] for chunk in case["chunks"]]
        assert indexes == sorted(set(indexes))
        for chunk in case["chunks"]:
            index = chunk["chunk_index"]
            assert chunk == {
                "chunk_index": index,
                "source_id": chunk_source(index),
                "text_sha256": sha(chunk_text(index).encode("utf-8")),
                "lexical_rank": chunk["lexical_rank"],
                "dense_rank": chunk["dense_rank"],
            }
            assert chunk["lexical_rank"] is not None or chunk["dense_rank"] is not None


def test_the_same_inputs_give_the_same_bytes_with_sorted_keys(inputs: Inputs) -> None:
    inputs.scan()
    second = inputs.root / "again.json"
    inputs.scan(out=second, embedder=Embedder())

    first = inputs.out.read_bytes()
    assert second.read_bytes() == first
    assert b"\r" not in first
    text = first.decode("utf-8")
    assert text == json.dumps(json.loads(text), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_an_existing_output_is_refused_and_left_as_it_was(inputs: Inputs) -> None:
    inputs.out.parent.mkdir()
    inputs.out.write_text("an earlier scan", encoding="utf-8")

    inputs.refused("exists", FileExistsError)
    assert inputs.embedder.asked == []


def test_another_archive_of_the_same_size_is_refused(inputs: Inputs) -> None:
    chunks = json.loads(gzip.decompress(inputs.archive.read_bytes()))["chunks"]
    chunks[3]["page_content"] += " правка"
    inputs.archive.write_bytes(
        gzip.compress(json.dumps({"chunks": chunks}, ensure_ascii=False).encode("utf-8"), mtime=0)
    )
    assert len(chunks) == json.loads(inputs.receipt.read_text(encoding="utf-8"))["chunk_count"]

    inputs.refused("archive")
    assert not inputs.out.exists() and inputs.embedder.asked == []


def test_another_checkpoint_is_refused(inputs: Inputs) -> None:
    # A well-formed checkpoint of the same archive that the receipt does not name.
    with np.load(inputs.checkpoint, allow_pickle=False) as saved:
        payload = dict(saved)
    payload["embeddings"][6] = np.asarray(direction(18), dtype=np.float32)
    np.savez(inputs.checkpoint, **payload)

    inputs.refused("[Cc]heckpoint SHA-256")
    assert not inputs.out.exists() and inputs.embedder.asked == []


@pytest.mark.parametrize(
    "damage", ["corpus", "texts", "schema", "manifest", "partial", "width", "nan", "norm"]
)
def test_a_checkpoint_that_breaks_the_index_contract_is_refused(
    inputs: Inputs, damage: str
) -> None:
    damage_checkpoint(inputs, damage)
    inputs.reseal()

    inputs.refused("identity" if damage in {"corpus", "texts", "schema", "manifest"} else "matrix")
    assert not inputs.out.exists() and inputs.embedder.asked == []


def test_an_embedder_with_another_manifest_is_refused(inputs: Inputs) -> None:
    other = Embedder(revision="c" * 40)

    inputs.refused("embedder", embedder=other)
    assert not inputs.out.exists() and other.asked == []


@pytest.mark.parametrize("vector", [[1.0, 0.0, 0.0], [float("nan"), 0.0], [0.0, 0.0]])
def test_a_query_vector_the_index_cannot_compare_is_refused(
    inputs: Inputs, vector: list[float]
) -> None:
    inputs.embedder.queries[COMMON] = vector

    inputs.refused("query vector")
    assert not inputs.out.exists()


@pytest.mark.parametrize("code_sha", ["b" * 39, "B" * 40, "master"])
def test_a_code_sha_that_is_not_forty_hex_digits_is_refused(inputs: Inputs, code_sha: str) -> None:
    inputs.refused("code SHA", code_sha=code_sha)
    assert not inputs.out.exists() and inputs.embedder.asked == []


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"case_id": "one", "question": "a"}, {"case_id": "one", "question": "b"}],
        [{"case_id": "one"}],
        [{"case_id": "", "question": "a"}],
    ],
)
def test_a_cases_file_without_unique_ids_and_questions_is_refused(
    inputs: Inputs, rows: list[dict[str, Any]]
) -> None:
    inputs.cases.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    inputs.refused("[Cc]ase")
    assert not inputs.out.exists() and inputs.embedder.asked == []


def test_the_command_loads_the_embedder_named_by_the_receipt(
    inputs: Inputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded: list[str | None] = []

    def get_embeddings(model_name: str | None = None) -> Embedder:
        loaded.append(model_name)
        return inputs.embedder

    monkeypatch.setattr("vectordb._base_manager.get_embeddings", get_embeddings)
    expected = inputs.root / "direct.json"
    inputs.scan(out=expected, embedder=Embedder())

    code = devset_wide_scan.main(
        [
            "--cases", str(inputs.cases),
            "--archive", str(inputs.archive),
            "--checkpoint", str(inputs.checkpoint),
            "--index", str(inputs.index),
            "--code-sha", CODE_SHA,
            "--out", str(inputs.out),
        ]
    )  # fmt: skip

    assert code == 0
    assert loaded == ["fixture"]
    assert inputs.out.read_bytes() == expected.read_bytes()


def test_the_module_imports_without_the_retrieval_stack() -> None:
    script = (
        "import sys\n"
        "import scripts.devset_wide_scan\n"
        "heavy = {'vectordb', 'rank_bm25', 'torch', 'sentence_transformers'} & set(sys.modules)\n"
        "assert not heavy, heavy\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_registered_pilot_cases_and_chunk_archive_are_accepted() -> None:
    """False-reject control: the real inputs pass the checks the scan adds of its own."""
    cases_bytes = (ROOT / "evaluation" / "devset_pilot.jsonl").read_bytes()
    cases = devset_wide_scan.load_cases(cases_bytes)
    rows = [json.loads(line) for line in cases_bytes.decode("utf-8").split("\n") if line.strip()]
    assert cases == [(row["case_id"], row["question"]) for row in rows]

    archive_bytes = (ROOT / "evaluation" / "gr1b-4436d61-graph-chunks.json.gz").read_bytes()
    chunks = devset_wide_scan.load_chunks(archive_bytes, sha(archive_bytes))
    assert len(chunks) == len(json.loads(gzip.decompress(archive_bytes))["chunks"])
