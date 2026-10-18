"""The BM25 corpus comes back from a collection of any size after a restart, a page at a time."""

from __future__ import annotations

import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from vectordb import manager


class _PagedCollection:
    """A collection that refuses a read of more rows than a page, as SQLite refuses a call that
    binds one variable per row past its limit."""

    def __init__(self, rows: int, limit: int) -> None:
        self.rows = [(f"chunk {index}", {"chunk_index": index}) for index in range(rows)]
        random.Random(7).shuffle(self.rows)
        self.limit = limit
        self.calls: list[dict[str, object]] = []

    def get(self, *, include: list[str], limit: int | None = None, offset: int = 0) -> dict:
        self.calls.append({"limit": limit, "offset": offset})
        if limit is None or limit > self.limit:
            raise RuntimeError("too many SQL variables")
        page = self.rows[offset : offset + limit]
        return {"documents": [text for text, _ in page], "metadatas": [meta for _, meta in page]}


def test_a_collection_larger_than_one_call_is_restored_whole_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "RESTORE_PAGE", 4)
    collection = _PagedCollection(rows=10, limit=4)

    chunks = manager._restore_chunks_from_store(SimpleNamespace(_collection=collection), "t")

    assert chunks is not None
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(10))
    assert [chunk.page_content for chunk in chunks] == [f"chunk {i}" for i in range(10)]
    assert collection.calls == [
        {"limit": 4, "offset": 0},
        {"limit": 4, "offset": 4},
        {"limit": 4, "offset": 8},
    ]


def test_an_exact_multiple_of_the_page_ends_on_an_empty_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "RESTORE_PAGE", 5)
    collection = _PagedCollection(rows=10, limit=5)

    chunks = manager._restore_chunks_from_store(SimpleNamespace(_collection=collection), "t")

    assert chunks is not None and len(chunks) == 10
    assert [call["offset"] for call in collection.calls] == [0, 5, 10]
    empty = _PagedCollection(rows=0, limit=5)
    assert manager._restore_chunks_from_store(SimpleNamespace(_collection=empty), "t") is None


def test_real_chroma_pages_return_every_chunk_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    chromadb = pytest.importorskip("chromadb")
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.create_collection("rag_docs_t")
    order = list(range(23))
    random.Random(3).shuffle(order)
    collection.add(
        ids=[f"id-{index}" for index in order],
        documents=[f"chunk {index}" for index in order],
        metadatas=[{"chunk_index": index, "source": "a.md"} for index in order],
        embeddings=[[float(index), 1.0] for index in order],
    )
    monkeypatch.setattr(manager, "RESTORE_PAGE", 6)

    chunks = manager._restore_chunks_from_store(SimpleNamespace(_collection=collection), "t")

    assert chunks is not None
    assert [chunk.page_content for chunk in chunks] == [f"chunk {i}" for i in range(23)]
