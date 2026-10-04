"""Wide scan of the whole index for development-set cases; run where the embedder is.

Plan step 1.3b, G38 question а: per case, the union of the 20 best chunks by the
production lexical scorer and the 20 nearest chunks by exact cosine similarity.
No query transform, fusion, cap, rerank or expansion.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "devset-wide-scan/v1"
LANE_SIZE = 20


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_cases(data: bytes) -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    # Not splitlines(): it also breaks on separators JSON leaves unescaped inside a string.
    for line in data.decode("utf-8").split("\n"):
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("case_id") if isinstance(row, dict) else None
        question = row.get("question") if isinstance(row, dict) else None
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Every case needs a case id")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Case {case_id} has no question")
        cases.append((case_id, question))
    if not cases or len({case_id for case_id, _ in cases}) != len(cases):
        raise ValueError("Cases file needs at least one case and unique case ids")
    return cases


def load_chunks(archive_bytes: bytes, archive_sha256: str) -> list[dict[str, Any]]:
    if sha256(archive_bytes) != archive_sha256:
        raise ValueError("Corpus archive SHA-256 mismatch")
    chunks: list[dict[str, Any]] = json.loads(gzip.decompress(archive_bytes))["chunks"]
    if not chunks:
        raise ValueError("Corpus is empty")
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk.get("page_content"), str) or not isinstance(
            (chunk.get("metadata") or {}).get("source"), str
        ):
            raise ValueError(f"Chunk {index} of the archive has no text or no source")
    return chunks


def load_matrix(
    checkpoint_bytes: bytes, receipt: dict[str, Any], archive_sha256: str, texts: list[str]
) -> Any:
    """The contract of scripts/production_index.py (build_index) for the cached vectors."""
    import numpy as np

    if sha256(checkpoint_bytes) != receipt["checkpoint_sha256"]:
        raise ValueError("Checkpoint SHA-256 mismatch")
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    with np.load(io.BytesIO(checkpoint_bytes), allow_pickle=False) as saved:
        if (
            saved["schema_version"].item() != 1
            or saved["corpus_sha256"].item() != archive_sha256
            or saved["texts_sha256"].item() != digest.hexdigest()
            or json.loads(saved["embedder_manifest"].item()) != receipt["embedder_manifest"]
        ):
            raise ValueError("Checkpoint corpus, texts or embedder identity mismatch")
        matrix = np.asarray(saved["embeddings"], dtype=np.float32)
    if (
        matrix.shape != (len(texts), receipt["embedder_manifest"]["dimension"])
        or not np.isfinite(matrix).all()
        or not np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-4, rtol=0)
    ):
        raise ValueError("Incomplete or invalid embedding matrix")
    return matrix


def best(scores: list[float]) -> list[int]:
    """Positions of the highest scores, equal scores in archive order."""
    return sorted(range(len(scores)), key=lambda index: (-scores[index], index))[:LANE_SIZE]


def build_scan(
    cases: Path,
    archive: Path,
    checkpoint: Path,
    index: Path,
    *,
    code_sha: str,
    embedder: Any | None = None,
) -> dict[str, Any]:
    """Check every input, then scan; ``embedder`` defaults to the production one."""
    import numpy as np

    if not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("A full code SHA is required")
    receipt_bytes = (index / "index-receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    try:
        archive_sha256 = receipt["corpus_sha256"]
        manifest = receipt["embedder_manifest"]
        model_id, dimension = manifest["model_id"], manifest["dimension"]
        receipt["checkpoint_sha256"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Index receipt lacks the corpus, checkpoint or embedder identity") from exc
    chunks = load_chunks(archive.read_bytes(), archive_sha256)
    texts = [chunk["page_content"] for chunk in chunks]
    matrix = load_matrix(checkpoint.read_bytes(), receipt, archive_sha256, texts)
    cases_bytes = cases.read_bytes()
    questions = load_cases(cases_bytes)

    from vectordb import _base_manager as production

    if not production.HAS_BM25:
        raise RuntimeError("rank_bm25 is required for the lexical lane")
    if embedder is None:
        embedder = production.get_embeddings(model_id)
    loaded = getattr(embedder, "manifest", None)
    if loaded is None or loaded.as_dict() != manifest:
        raise ValueError("Loaded query embedder mismatch")

    # Production indexes page_content with this tokenizer (HybridRetriever.__init__).
    bm25 = production.BM25Okapi([production._tokenize_for_bm25(text) for text in texts])
    rows = matrix.astype(np.float64)
    rows /= np.linalg.norm(rows, axis=1, keepdims=True)
    addresses = [
        {
            "chunk_index": position,
            "source_id": chunk["metadata"]["source"],
            "text_sha256": sha256(chunk["page_content"].encode("utf-8")),
        }
        for position, chunk in enumerate(chunks)
    ]
    scanned = []
    for case_id, question in questions:
        lexical_scores = bm25.get_scores(production._tokenize_for_bm25(question)).tolist()
        lexical = [position for position in best(lexical_scores) if lexical_scores[position] > 0]
        vector = np.asarray(embedder.embed_query(question), dtype=np.float64)
        if (
            vector.shape != (dimension,)
            or not np.isfinite(vector).all()
            or not np.linalg.norm(vector) > 0
        ):
            raise ValueError(f"Invalid query vector for case {case_id}")
        dense = best((rows @ (vector / np.linalg.norm(vector))).tolist())
        lexical_rank = {position: rank for rank, position in enumerate(lexical, 1)}
        dense_rank = {position: rank for rank, position in enumerate(dense, 1)}
        scanned.append(
            {
                "case_id": case_id,
                "question_sha256": sha256(question.encode("utf-8")),
                "chunks": [
                    {
                        **addresses[position],
                        "lexical_rank": lexical_rank.get(position),
                        "dense_rank": dense_rank.get(position),
                    }
                    for position in sorted(lexical_rank.keys() | dense_rank.keys())
                ],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "lane_size": LANE_SIZE,
        "archive_sha256": archive_sha256,
        "checkpoint_sha256": receipt["checkpoint_sha256"],
        "index_receipt_sha256": sha256(receipt_bytes),
        "cases_sha256": sha256(cases_bytes),
        "embedder_manifest": manifest,
        "code_sha": code_sha,
        "script_sha256": sha256(Path(__file__).read_bytes()),
        "chunk_count": len(chunks),
        "cases": scanned,
    }


def wide_scan(
    cases: Path,
    archive: Path,
    checkpoint: Path,
    index: Path,
    out: Path,
    *,
    code_sha: str,
    embedder: Any | None = None,
) -> dict[str, Any]:
    if out.exists():
        raise FileExistsError("Scan output already exists; choose a new file")
    report = build_scan(cases, archive, checkpoint, index, code_sha=code_sha, embedder=embedder)
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation" / "devset_pilot.jsonl")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = wide_scan(
        args.cases, args.archive, args.checkpoint, args.index, args.out, code_sha=args.code_sha
    )
    summary = {
        "cases": len(report["cases"]),
        "chunk_count": report["chunk_count"],
        "out_sha256": sha256(args.out.read_bytes()),
    }
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
