import json
from types import SimpleNamespace

import pytest

from ingestion.entity_extraction import extract_entities


def chunks():
    return [SimpleNamespace(page_content=f"policy {i}", metadata={"source": f"{i}.md", "chunk_index": i})
            for i in range(3)]


def run(path, invoke, **kwargs):
    return extract_entities(chunks(), tenant_id="acme", corpus_sha256="a" * 64,
                            model="mistral-small-2506", cache_dir=path, invoke=invoke, **kwargs)


def test_resume_skips_successful_chunks_after_provider_failure(tmp_path):
    calls = []

    def interrupted(prompt):
        calls.append(prompt)
        if len(calls) == 2:
            raise RuntimeError("provider unavailable")
        return '["AWB", "air waybill"]'

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run(tmp_path, interrupted)
    resumed = []
    result = run(tmp_path, lambda prompt: resumed.append(prompt) or '["booking"]')
    assert len(resumed) == 2
    assert len(result) == 3
    assert sorted(result.values()) == [["awb"], ["booking"], ["booking"]]
    assert run(tmp_path, lambda _: pytest.fail("cached chunk called provider")) == result


@pytest.mark.parametrize("answer", ['nonsense', '{}', '[1]', '["' + 'x' * 129 + '"]'])
def test_invalid_answer_is_not_cached_as_success(tmp_path, answer):
    with pytest.raises(ValueError, match="entities"):
        run(tmp_path, lambda _: answer)
    rows = tmp_path / "entities.jsonl"
    assert not rows.exists() or rows.read_text() == ""


def test_valid_empty_array_is_cacheable(tmp_path):
    result = run(tmp_path, lambda _: '[]')
    assert len(result) == 3 and all(value == [] for value in result.values())


@pytest.mark.parametrize("change", ["corpus", "model", "text", "tenant"])
def test_changed_provenance_fails_before_provider_call(tmp_path, change):
    run(tmp_path, lambda _: '["awb"]')
    params = dict(tenant_id="acme", corpus_sha256="a" * 64, model="mistral-small-2506")
    input_chunks = chunks()
    if change == "text":
        input_chunks[0].page_content = "changed"
    else:
        params[{"corpus": "corpus_sha256", "model": "model", "tenant": "tenant_id"}[change]] = (
            "b" * 64 if change == "corpus" else "different")
    with pytest.raises(ValueError, match="provenance"):
        extract_entities(input_chunks, cache_dir=tmp_path, invoke=lambda _: pytest.fail("provider called"), **params)


def test_cache_tampering_fails_closed(tmp_path):
    run(tmp_path, lambda _: '["awb"]')
    path = tmp_path / "entities.jsonl"
    rows = path.read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[0])
    row["content_sha256"] = "b" * 64
    path.write_text(json.dumps(row) + "\n" + "\n".join(rows[1:]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cache"):
        run(tmp_path, lambda _: pytest.fail("provider called"))


def test_bounded_batch_and_manifest(tmp_path):
    result = run(tmp_path, lambda _: '["awb"]', max_calls=1)
    assert len(result) == 1
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["corpus_sha256"] == "a" * 64
    assert manifest["chunk_count"] == 3
    assert len(manifest["prompt_sha256"]) == 64
    assert manifest["model_digest"] is None


def test_incomplete_tail_fails_before_provider_call(tmp_path):
    run(tmp_path, lambda _: '["awb"]')
    path = tmp_path / "entities.jsonl"
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
    with pytest.raises(ValueError, match="cache"):
        run(tmp_path, lambda _: pytest.fail("provider called"))


def test_cli_dry_run_needs_no_provider_key(tmp_path, monkeypatch, capsys):
    import hashlib

    from scripts.extract_graph_entities import main

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    source = tmp_path / "chunks.json"
    source.write_text(json.dumps({"tenant_id": "acme", "chunks": [vars(c) for c in chunks()]}))
    args = ["--chunks", str(source), "--chunks-sha256", hashlib.sha256(source.read_bytes()).hexdigest(),
            "--corpus-sha256", "a" * 64, "--model", "mistral-small-2506",
            "--cache-dir", str(tmp_path / "cache")]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["cached"] == 0
    source.write_text("changed")
    with pytest.raises(ValueError, match="SHA-256"):
        main(args)


def test_extraction_ids_feed_the_entity_builder(tmp_path):
    from ingestion.entity_graph import add_entity_graph
    from ingestion.structure_graph import build_structural_graph

    graph = build_structural_graph(chunks(), tenant_id="acme")
    enriched = add_entity_graph(graph, run(tmp_path, lambda _: '["awb"]'))
    assert len([node for node in enriched.nodes if node.kind == "entity"]) == 1
    assert len([edge for edge in enriched.edges if edge.kind == "mentions"]) == 3
