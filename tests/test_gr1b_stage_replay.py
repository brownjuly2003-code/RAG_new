import json

import pytest

from scripts.gr1b_stage_replay import DEFAULT_REPORT, build_stage_report, recover_ranked_docs


def test_recovery_uses_text_and_source_not_postprocessed_metadata():
    pool = dict(cands=["same", "same"], cand_sources=["a", "b"],
                cand_metadata=[{"source": "a", "section": "one"}, {"source": "b", "section": "two"}])
    archived = dict(prerank_cands=pool["cands"], prerank_sources=pool["cand_sources"],
                    reranked_cands=["same", "same"], reranked_sources=["b", "a"])
    docs = recover_ranked_docs(pool, archived)
    assert [doc.metadata["section"] for doc in docs] == ["two", "one"]


def test_recovery_rejects_changed_pool_and_ambiguous_metadata():
    pool = dict(cands=["same", "same"], cand_sources=["a", "a"],
                cand_metadata=[{"section": "one"}, {"section": "two"}])
    archived = dict(prerank_cands=pool["cands"], prerank_sources=pool["cand_sources"],
                    reranked_cands=["same", "same"], reranked_sources=["a", "a"])
    with pytest.raises(ValueError, match="ambiguous"):
        recover_ranked_docs(pool, archived)
    archived["prerank_cands"] = ["changed"]
    with pytest.raises(ValueError, match="original pool"):
        recover_ranked_docs(pool, archived)


def test_published_stage_replay_reproduces_all_cases_and_inputs():
    published = json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))
    rebuilt = build_stage_report()
    for field in ("arms", "exact_replays", "graph_chunks", "labels"):
        assert rebuilt[field] == published[field]
    for field in ("archive_sha256", "pool_sha256", "dataset_sha256", "label_sidecar_sha256",
                  "label_manifest_sha256", "corpus", "config", "recovered_inputs"):
        assert rebuilt["provenance"][field] == published["provenance"][field]
    assert rebuilt["exact_replays"] == 100
    expansion = next(arm for arm in rebuilt["arms"] if arm["name"] == "expansion_only")
    assert expansion["comparison"]["lost_keyword_cases"] == []
    assert expansion["aggregate"]["context_recall"] == 0.93


def test_stage_measurement_refuses_a_nonidentical_baseline(monkeypatch):
    from scripts.gr1b_stage_replay import HybridRetriever

    monkeypatch.setattr(HybridRetriever, "_expand_graph_sections", lambda self, docs: [])
    with pytest.raises(ValueError, match="exact structural replay differs"):
        build_stage_report()
