"""Prepare pinned, resumable embeddings on the Mac; never publish an index."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from vectordb.embedder_manifest import EmbedderManifest


def prepare_embeddings(
    texts: list[str], embeddings: Any, output: Path, *, corpus_sha256: str,
    batch_size: int = 8, max_batches: int | None = None, resume: bool = False,
) -> dict[str, Any]:
    import numpy as np

    manifest = getattr(embeddings, "manifest", None)
    if (
        not isinstance(manifest, EmbedderManifest)
        or manifest.backend != "local"
        or manifest.revision_source != "hf_snapshot"
        or not re.fullmatch(r"[0-9a-f]{40}", manifest.revision or "")
        or not isinstance(manifest.dimension, int)
        or manifest.dimension <= 0
        or manifest.normalize is not True
    ):
        raise ValueError("A verified, normalized local embedder manifest is required")
    if not re.fullmatch(r"[0-9a-f]{64}", corpus_sha256):
        raise ValueError("Invalid corpus SHA-256")
    if not texts or batch_size < 1 or (max_batches is not None and max_batches < 1):
        raise ValueError("Nonempty texts and positive batch limits are required")
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    identity = {
        "schema_version": 1,
        "corpus_sha256": corpus_sha256,
        "texts_sha256": digest.hexdigest(),
        "embedder_manifest": manifest.canonical_json,
    }

    def validate(matrix: Any, rows: int) -> None:
        if (
            matrix.shape != (rows, manifest.dimension)
            or not np.isfinite(matrix).all()
            or not np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-4, rtol=0)
        ):
            raise ValueError("Invalid embedding matrix shape, values or normalization")

    matrix = np.empty((0, manifest.dimension), dtype=np.float32)
    if output.exists():
        if not resume:
            raise FileExistsError("Checkpoint exists; explicit --resume is required")
        try:
            with np.load(output, allow_pickle=False) as saved:
                if any(saved[key].item() != value for key, value in identity.items()):
                    raise ValueError("Checkpoint corpus, texts or embedder identity mismatch")
                matrix = np.asarray(saved["embeddings"], dtype=np.float32)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid or incompatible embedding checkpoint") from exc
        if matrix.ndim != 2 or len(matrix) > len(texts):
            raise ValueError("Invalid checkpoint row count")
        validate(matrix, len(matrix))
    elif resume:
        raise ValueError("Cannot resume a missing checkpoint")

    batches = 0
    while len(matrix) < len(texts) and (max_batches is None or batches < max_batches):
        batch = texts[len(matrix):len(matrix) + batch_size]
        encoded_batch = np.asarray(embeddings.embed_documents(batch), dtype=np.float32)
        validate(encoded_batch, len(batch))
        matrix = np.concatenate((matrix, encoded_batch))
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{output.stem}.", suffix=".npz", dir=output.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            np.savez(temporary, embeddings=matrix, **identity)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
        batches += 1

    return {
        "completed_rows": len(matrix),
        "total_rows": len(texts),
        "complete": len(matrix) == len(texts),
        "checkpoint_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "embedder_manifest": manifest.as_dict(),
        "corpus_sha256": corpus_sha256,
        "texts_sha256": digest.hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("--revision must be an immutable 40-character HF commit")
    archive = args.archive.read_bytes()
    if hashlib.sha256(archive).hexdigest() != args.archive_sha256:
        raise ValueError("Corpus archive SHA-256 mismatch")
    if args.output.exists() and not args.resume:
        raise FileExistsError("Checkpoint exists; explicit --resume is required")
    texts = [chunk["page_content"] for chunk in json.loads(gzip.decompress(archive))["chunks"]]

    from config.settings import get_settings
    from vectordb._base_manager import get_embeddings

    settings = get_settings()
    settings.embedding_backend = "local"
    settings.embedding_model = args.model
    settings.embedding_model_revision = args.revision
    report = prepare_embeddings(
        texts, get_embeddings(), args.output, corpus_sha256=args.archive_sha256,
        batch_size=args.batch_size, max_batches=args.max_batches, resume=args.resume,
    )
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
