"""Unit wiring for the GR-1 remote measurement arm."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import ab_remote_contextual as remote
from vectordb import _base_manager as manager


def _chunk(
    text: str,
    *,
    source: str,
    section: str,
    category: str = "shipping",
) -> manager.Document:
    return manager.Document(
        page_content=text,
        metadata={
            "source": source,
            "categories": [category],
            "h1": "Policy",
            "h2": section,
        },
    )


def test_g1_is_structural_and_uses_only_exact_available_case_tags(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("RAG_STRUCTURAL_CHUNKING", "false")

    remote._set_arm_env("G1")

    assert remote.os.environ["RAG_STRUCTURAL_CHUNKING"] == "true"
    assert remote._matching_graph_categories(
        {"tags": ["Shipping", "unknown", "shipping"]},
        ["returns", "shipping"],
    ) == ["shipping"]
    assert (
        remote._matching_graph_categories(
            {"tags": ["hr", "probation"]},
            ["HR internal policies and procedures"],
        )
        == []
    )


def test_cli_dispatches_g1_for_pool_and_rerank_stages(monkeypatch: Any, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _pools(
        arm: str,
        corpus: Path,
        cases: Path,
        out_dir: Path,
        expansions: dict[str, str] | None = None,
    ) -> int:
        _ = corpus, cases, out_dir
        assert expansions is None
        calls.append(("pools", arm))
        return 0

    def _rerank(arm: str, out_dir: Path) -> int:
        _ = out_dir
        calls.append(("rerank", arm))
        return 0

    monkeypatch.setattr(remote, "stage_pools", _pools)
    monkeypatch.setattr(remote, "stage_rerank", _rerank)

    assert (
        remote.main(
            ["--legacy-harness", "--stage", "pools", "--arm", "G1", "--out-dir", str(tmp_path)]
        )
        == 0
    )
    assert (
        remote.main(
            ["--legacy-harness", "--stage", "rerank", "--arm", "G1", "--out-dir", str(tmp_path)]
        )
        == 0
    )
    assert calls == [("pools", "G1"), ("rerank", "G1")]


def test_g1_rerank_applies_coherence_then_expands_from_graph_sidecar(
    monkeypatch: Any, tmp_path: Path
) -> None:
    first = _chunk(
        "first supported chunk",
        source="shipping.md",
        section="Supported",
    )
    adjacent = _chunk(
        "adjacent but different section",
        source="shipping.md",
        section="Other",
    )
    second = _chunk(
        "second supported chunk",
        source="shipping.md",
        section="Supported",
    )
    tail = _chunk(
        "tail from the same section",
        source="shipping.md",
        section="Supported",
    )
    weak = _chunk(
        "weak isolated shipping hit",
        source="weak.md",
        section="Weak",
    )
    # Since 8b922a1 each side stops at the next chunk outside its section; it cannot skip it.
    all_chunks = [first, tail, adjacent, second, weak]
    candidates = [adjacent, first, second, weak]

    pool = [
        {
            "case_id": "case-1",
            "query": "shipping question",
            "kws": [],
            "rerank_k": 5,
            "cands": [doc.page_content for doc in candidates],
            "cand_sources": [doc.metadata["source"] for doc in candidates],
            "cand_metadata": [dict(doc.metadata) for doc in candidates],
        }
    ]
    (tmp_path / "ab_phase2_G1_pool.json").write_text(json.dumps(pool), encoding="utf-8")
    (tmp_path / "ab_phase2_G1_graph_chunks.json").write_text(
        json.dumps(
            {
                "tenant_id": "aircargo",
                "chunks": [
                    {"page_content": doc.page_content, "metadata": dict(doc.metadata)}
                    for doc in all_chunks
                ],
            }
        ),
        encoding="utf-8",
    )

    class _Reranker:
        def predict(self, pairs: list[tuple[str, str]], batch_size: int) -> list[float]:
            _ = batch_size
            assert [text for _, text in pairs] == [doc.page_content for doc in candidates]
            return [4.0, 3.0, 2.0, 1.0]

    monkeypatch.setattr(manager, "get_reranker", lambda: _Reranker())

    assert remote.stage_rerank("G1", tmp_path) == 0

    rows = json.loads((tmp_path / "ab_candidates_phase2_G1.json").read_text(encoding="utf-8"))
    assert rows[0]["cands"][0] == ("first supported chunk\n\ntail from the same section")
    assert rows[0]["cands"][1] == "second supported chunk"
    assert all("adjacent but different section" not in text for text in rows[0]["cands"][:2])
    assert all("weak isolated" not in text for text in rows[0]["cands"])
    assert rows[0]["graph_postprocessed"] is True
