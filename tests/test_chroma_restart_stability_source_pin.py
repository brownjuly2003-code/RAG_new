"""AST pins for the production Chroma calls measured by this experiment."""

from pathlib import Path

import pytest

from scripts.chroma_restart_stability import (
    assert_chunk_index_stamp,
    assert_reopen_call,
    assert_staged_build_call,
)

ROOT = Path(__file__).resolve().parents[1]


def test_valid_production_source_is_accepted():
    assert_staged_build_call((ROOT / "vectordb/index_staging.py").read_text(encoding="utf-8"))
    assert_reopen_call((ROOT / "vectordb/manager.py").read_text(encoding="utf-8"))
    assert_chunk_index_stamp((ROOT / "vectordb/manager.py").read_text(encoding="utf-8"))


def test_added_collection_metadata_is_rejected_by_build_pin():
    source = (ROOT / "vectordb/index_staging.py").read_text(encoding="utf-8")
    changed = source.replace(
        '            collection_configuration={"hnsw": {"sync_threshold": 1}},\n        )\n        persist',
        '            collection_configuration={"hnsw": {"sync_threshold": 1}},\n'
        "            collection_metadata={},\n        )\n        persist",
        1,
    )
    assert changed != source
    with pytest.raises(ValueError, match="from_documents"):
        assert_staged_build_call(changed)


def test_other_sync_threshold_is_rejected_by_build_pin():
    source = (ROOT / "vectordb/index_staging.py").read_text(encoding="utf-8")
    target = 'collection_configuration={"hnsw": {"sync_threshold": 1}}'
    assert target in source
    changed = source.replace(target, 'collection_configuration={"hnsw": {"sync_threshold": 2}}', 1)
    with pytest.raises(ValueError, match="from_documents"):
        assert_staged_build_call(changed)


@pytest.mark.parametrize("threshold", [True, 1.0])
def test_non_integer_sync_threshold_is_rejected_by_build_pin(threshold):
    source = (ROOT / "vectordb/index_staging.py").read_text(encoding="utf-8")
    target = 'collection_configuration={"hnsw": {"sync_threshold": 1}}'
    assert target in source
    changed = source.replace(
        target, target.replace('"sync_threshold": 1', f'"sync_threshold": {threshold!r}'), 1
    )
    with pytest.raises(ValueError, match="from_documents"):
        assert_staged_build_call(changed)


def test_missing_configuration_is_rejected_by_build_pin():
    source = (ROOT / "vectordb/index_staging.py").read_text(encoding="utf-8")
    target = '            collection_configuration={"hnsw": {"sync_threshold": 1}},\n'
    assert target in source
    changed = source.replace(target, "", 1)
    with pytest.raises(ValueError, match="from_documents"):
        assert_staged_build_call(changed)


def test_added_collection_metadata_is_rejected_by_reopen_pin():
    source = (ROOT / "vectordb/manager.py").read_text(encoding="utf-8")
    target = "collection_name=active_collection,"
    assert target in source
    changed = source.replace(target, target + " collection_metadata={},", 1)
    with pytest.raises(ValueError, match="chroma_cls"):
        assert_reopen_call(changed)


def test_changed_chunk_stamp_is_rejected():
    source = (ROOT / "vectordb/manager.py").read_text(encoding="utf-8")
    target = 'metadata["chunk_index"] = index'
    assert target in source
    with pytest.raises(ValueError, match="chunk_index"):
        assert_chunk_index_stamp(source.replace(target, 'metadata["chunk_id"] = index', 1))
