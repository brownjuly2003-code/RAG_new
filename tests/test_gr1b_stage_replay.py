import pytest

from scripts.gr1b_stage_replay import recover_ranked_docs


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
