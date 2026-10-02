"""Build a separate Chroma baseline index from complete, verified cached vectors."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from vectordb.embedder_manifest import MANIFEST_METADATA_KEY, EmbedderManifest


def build_index(
    archive: Path, checkpoint: Path, output: Path, *, archive_sha256: str,
    expected_manifest: EmbedderManifest, code_sha: str,
    collection_name: str = "rag_docs_aircargo", batch_size: int = 256,
) -> dict[str, Any]:
    import numpy as np

    if output.exists():
        raise FileExistsError("Index output already exists; choose a new directory")
    if (
        expected_manifest.backend != "local"
        or expected_manifest.revision_source != "hf_snapshot"
        or not re.fullmatch(r"[0-9a-f]{40}", expected_manifest.revision or "")
        or expected_manifest.normalize is not True
        or type(expected_manifest.dimension) is not int
        or expected_manifest.dimension <= 0
        or expected_manifest.schema_version != 1
    ):
        raise ValueError("A verified, normalized local embedder manifest is required")
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or batch_size < 1:
        raise ValueError("A code SHA and a positive batch size are required")
    archive_bytes = archive.read_bytes()
    if hashlib.sha256(archive_bytes).hexdigest() != archive_sha256:
        raise ValueError("Corpus archive SHA-256 mismatch")
    chunks = json.loads(gzip.decompress(archive_bytes))["chunks"]
    if not chunks:
        raise ValueError("Corpus is empty")
    texts = [chunk["page_content"] for chunk in chunks]
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    checkpoint_bytes = checkpoint.read_bytes()
    with np.load(io.BytesIO(checkpoint_bytes), allow_pickle=False) as saved:
        if (
            saved["schema_version"].item() != 1
            or saved["corpus_sha256"].item() != archive_sha256
            or saved["texts_sha256"].item() != digest.hexdigest()
            or json.loads(saved["embedder_manifest"].item()) != expected_manifest.as_dict()
        ):
            raise ValueError("Checkpoint corpus, texts or embedder identity mismatch")
        matrix = np.asarray(saved["embeddings"], dtype=np.float32)
    if (
        matrix.shape != (len(chunks), expected_manifest.dimension)
        or not np.isfinite(matrix).all()
        or not np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-4, rtol=0)
    ):
        raise ValueError("Incomplete or invalid embedding matrix")

    import chromadb
    from chromadb.config import Settings

    output.mkdir(parents=True, exist_ok=False)
    client = chromadb.PersistentClient(
        path=str(output / "chroma"), settings=Settings(anonymized_telemetry=False),
    )
    configuration = {"hnsw": {"sync_threshold": 1}}
    collection = client.create_collection(
        collection_name, embedding_function=None, configuration=configuration,
        metadata={MANIFEST_METADATA_KEY: expected_manifest.canonical_json},
    )
    for start in range(0, len(chunks), batch_size):
        stop = min(start + batch_size, len(chunks))
        collection.add(
            ids=[f"chunk-{index:08d}" for index in range(start, stop)],
            documents=texts[start:stop], embeddings=matrix[start:stop].tolist(),
            metadatas=[dict(chunks[index]["metadata"], chunk_index=index)
                       for index in range(start, stop)],
        )
    if collection.count() != len(chunks):
        raise ValueError("Persisted collection count mismatch")
    report = {
        "schema_version": 1, "code_sha": code_sha,
        "corpus_sha256": archive_sha256, "texts_sha256": digest.hexdigest(),
        "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
        "embedder_manifest": expected_manifest.as_dict(),
        "collection_name": collection_name, "chunk_count": len(chunks),
        "configuration": configuration, "chromadb_version": chromadb.__version__,
        "evidence_status": "preparation",
    }
    with (output / "index-receipt.json").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="independently pinned expected embedder manifest JSON")
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--collection-name", default="rag_docs_aircargo")
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args(argv)
    report = build_index(
        args.archive, args.checkpoint, args.output, archive_sha256=args.archive_sha256,
        expected_manifest=EmbedderManifest(**json.loads(args.manifest.read_text(encoding="utf-8"))),
        code_sha=args.code_sha, collection_name=args.collection_name, batch_size=args.batch_size,
    )
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
