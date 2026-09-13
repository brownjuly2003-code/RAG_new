import hashlib
import http.client
import io
import json
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from ingestion.entity_extraction import EXTRACT_SCHEMA, extract_entities, load_extraction_cache
from llm.providers.pinned_ollama import (
    OllamaUnreachable,
    PinnedOllamaChat,
    resolve_ollama_digest,
)

MODEL = "qwen2.5:7b"
DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
OTHER = "b" * 64
CORPUS = "a" * 64
BASE = "http://127.0.0.1:11434"


def chunks():
    return [
        SimpleNamespace(
            page_content=f"policy {i}", metadata={"source": f"{i}.md", "chunk_index": i}
        )
        for i in range(3)
    ]


class FakeResponse:
    def __init__(self, payload):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class FakeOllama:
    def __init__(self, digest, *, model=MODEL, answers=None, errors=None, tag_errors=None):
        self.digest = digest
        self.model = model
        self.answers = list(answers if answers is not None else ['["awb"]'])
        self.errors = list(errors or [])
        self.tag_errors = list(tag_errors or [])
        self.requests = []
        self._chat_i = 0

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        url = request.full_url
        if url.endswith("/api/tags"):
            if self.tag_errors:
                raise self.tag_errors.pop(0)
            return FakeResponse({"models": [{"name": self.model, "digest": self.digest}]})
        if url.endswith("/api/chat"):
            if self.errors:
                raise self.errors.pop(0)
            answer = self.answers[min(self._chat_i, len(self.answers) - 1)]
            self._chat_i += 1
            return FakeResponse({"message": {"content": answer}})
        raise AssertionError(url)


def http_error(code):
    return HTTPError(f"{BASE}/api/chat", code, "error", EmailMessage(), io.BytesIO(b""))


def chat_requests(fake):
    return [item for item in fake.requests if item.full_url.endswith("/api/chat")]


def client(fake, digest=DIGEST, **kwargs):
    params = dict(opener=fake, sleeper=lambda _delay: None, timeout=1.0, backoff_s=10.0)
    params.update(kwargs)
    return PinnedOllamaChat(BASE, MODEL, digest, **params)


def run_ollama(path, fake, **kwargs):
    pinned = kwargs.pop("pinned", None) or client(fake)
    return extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=path,
        invoke=lambda prompt: pinned.chat(
            [{"role": "user", "content": prompt}],
            format_schema=EXTRACT_SCHEMA,
        ),
        provider="ollama",
        model_digest=kwargs.pop("digest", DIGEST),
        generation=pinned.generation_record(EXTRACT_SCHEMA),
        **kwargs,
    )


def format_sha256():
    return hashlib.sha256(
        json.dumps(EXTRACT_SCHEMA, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    ).hexdigest()


def cli_args(tmp_path, source, **extra):
    args = [
        "--chunks",
        str(source),
        "--chunks-sha256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
        "--corpus-sha256",
        CORPUS,
        "--model",
        extra.pop("model", MODEL),
        "--cache-dir",
        str(tmp_path / "cache"),
    ]
    for key, value in extra.items():
        args.extend([f"--{key.replace('_', '-')}", str(value)])
    return args


def write_chunks(path):
    path.write_text(
        json.dumps({"tenant_id": "acme", "chunks": [vars(item) for item in chunks()]}),
        encoding="utf-8",
    )
    return path


def test_manifest_pins_provider_digest_and_generation(tmp_path):
    fake = FakeOllama(DIGEST)
    run_ollama(tmp_path, fake, max_calls=1)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["provider"] == "ollama"
    assert manifest["model_digest"] == DIGEST
    assert manifest["generation"]["temperature"] == 0
    assert manifest["generation"]["seed"] == 42
    assert manifest["generation"]["num_ctx"] == 4096
    assert manifest["generation"]["format_sha256"] == format_sha256()


def test_rerun_with_different_digest_is_refused_before_chat(tmp_path, monkeypatch, capsys):
    from scripts.extract_graph_entities import main

    source = write_chunks(tmp_path / "chunks.json")
    fake = FakeOllama(DIGEST)
    monkeypatch.setattr("llm.providers.pinned_ollama._urlopen", fake)
    assert main(cli_args(tmp_path, source, provider="ollama", max_calls=1)) == 0
    first = len(chat_requests(fake))
    assert first == 1
    fake.digest = OTHER
    with pytest.raises(ValueError, match="provenance"):
        main(cli_args(tmp_path, source, provider="ollama", max_calls=1))
    assert len(chat_requests(fake)) == first


def test_digest_change_after_chat_writes_nothing(tmp_path):
    fake = FakeOllama(DIGEST)
    original = fake.__call__
    sleeps = []

    def swap_after_chat(request, timeout=None):
        response = original(request, timeout)
        if request.full_url.endswith("/api/chat"):
            fake.digest = OTHER
        return response

    pinned = client(swap_after_chat, digest=DIGEST, sleeper=sleeps.append)
    with pytest.raises(RuntimeError, match="digest"):
        run_ollama(tmp_path, fake, pinned=pinned, digest=DIGEST)
    rows = tmp_path / "entities.jsonl"
    assert not rows.exists() or rows.read_text(encoding="utf-8") == ""
    assert chat_requests(fake)
    assert sleeps == []


def test_chat_request_body(tmp_path):
    fake = FakeOllama(DIGEST)
    run_ollama(tmp_path, fake, max_calls=1)
    body = json.loads(chat_requests(fake)[0].data.decode("utf-8"))
    assert body["format"] == EXTRACT_SCHEMA
    assert body["options"] == {"temperature": 0, "seed": 42, "num_ctx": 4096}
    assert body["stream"] is False
    assert body["keep_alive"] == "30m"


def test_retry_http_503_then_success(tmp_path):
    fake = FakeOllama(DIGEST, errors=[http_error(503)])
    sleeps = []
    run_ollama(tmp_path, fake, pinned=client(fake, sleeper=sleeps.append), max_calls=1)
    assert len(chat_requests(fake)) == 2
    assert sleeps == [10.0]
    rows = (tmp_path / "entities.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert len(json.loads(rows[0])["entities"]) == 1


def test_digest_recheck_retries_tags_without_regenerating(tmp_path):
    fake = FakeOllama(DIGEST, tag_errors=[URLError("tags down")])
    sleeps = []
    run_ollama(tmp_path, fake, pinned=client(fake, sleeper=sleeps.append), max_calls=1)
    assert len(chat_requests(fake)) == 1
    assert sleeps == [10.0]
    tags = [item for item in fake.requests if item.full_url.endswith("/api/tags")]
    assert len(tags) == 2
    rows = (tmp_path / "entities.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1


def test_retry_incomplete_read_then_success(tmp_path):
    fake = FakeOllama(DIGEST, errors=[http.client.IncompleteRead(b"[")])
    sleeps = []
    run_ollama(tmp_path, fake, pinned=client(fake, sleeper=sleeps.append), max_calls=1)
    assert len(chat_requests(fake)) == 2
    assert sleeps == [10.0]
    rows = (tmp_path / "entities.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1


def test_http_400_is_not_retried(tmp_path):
    fake = FakeOllama(DIGEST, errors=[http_error(400)])
    sleeps = []
    with pytest.raises(RuntimeError):
        run_ollama(tmp_path, fake, pinned=client(fake, sleeper=sleeps.append), max_calls=1)
    assert len(chat_requests(fake)) == 1
    assert sleeps == []
    rows = tmp_path / "entities.jsonl"
    assert not rows.exists() or rows.read_text(encoding="utf-8") == ""


def test_tags_http_404_is_not_retried_after_chat(tmp_path):
    fake = FakeOllama(DIGEST, tag_errors=[http_error(404)])
    sleeps = []
    with pytest.raises(RuntimeError) as excinfo:
        run_ollama(
            tmp_path,
            fake,
            pinned=client(fake, sleeper=sleeps.append, max_attempts=5),
            max_calls=1,
        )
    assert type(excinfo.value) is RuntimeError
    assert not isinstance(excinfo.value, OllamaUnreachable)
    assert MODEL in str(excinfo.value)
    tags = [item for item in fake.requests if item.full_url.endswith("/api/tags")]
    assert len(tags) == 1
    assert len(chat_requests(fake)) == 1
    assert sleeps == []
    rows = tmp_path / "entities.jsonl"
    assert not rows.exists() or rows.read_text(encoding="utf-8") == ""


def test_connection_errors_exhaust_attempts(tmp_path):
    fake = FakeOllama(DIGEST, errors=[URLError("refused")] * 5)
    with pytest.raises(RuntimeError):
        run_ollama(tmp_path, fake, pinned=client(fake, max_attempts=5), max_calls=1)
    assert len(chat_requests(fake)) == 5
    rows = tmp_path / "entities.jsonl"
    assert not rows.exists() or rows.read_text(encoding="utf-8") == ""


def test_empty_content_writes_nothing(tmp_path):
    fake = FakeOllama(DIGEST, answers=[""])
    with pytest.raises(RuntimeError, match="empty"):
        run_ollama(tmp_path, fake, max_calls=1)
    rows = tmp_path / "entities.jsonl"
    assert not rows.exists() or rows.read_text(encoding="utf-8") == ""
    assert len(chat_requests(fake)) == 1


def test_on_invalid_record_records_surrogate_answer(tmp_path):
    answers = ['["awb"]', json.loads('"[\\ud800]"'), '["booking"]']

    def invoke(prompt):
        return answers.pop(0)

    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=invoke,
        on_invalid="record",
    )
    cache = load_extraction_cache(tmp_path, chunks(), tenant_id="acme")
    assert len(cache.entities) == 2
    assert len(cache.rejected) == 1
    assert cache.total == 3
    row = json.loads((tmp_path / "rejected.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert len(row["answer_sha256"]) == 64
    assert len(row["answer_prefix"]) <= 200
    row["answer_prefix"].encode("utf-8")
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=lambda _: pytest.fail("cached or rejected chunk called provider"),
        on_invalid="record",
    )


def test_on_invalid_record_continues_and_resume_skips(tmp_path):
    answers = ['["awb"]', "nonsense", '["booking"]']

    def invoke(prompt):
        return answers.pop(0)

    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=invoke,
        on_invalid="record",
    )
    cache = load_extraction_cache(tmp_path, chunks(), tenant_id="acme")
    assert len(cache.entities) == 2
    assert len(cache.rejected) == 1
    assert cache.total == 3
    rejected = (tmp_path / "rejected.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rejected) == 1
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=lambda _: pytest.fail("cached or rejected chunk called provider"),
        on_invalid="record",
    )
    again = load_extraction_cache(tmp_path, chunks(), tenant_id="acme")
    assert len(again.entities) == 2 and len(again.rejected) == 1 and again.total == 3


def test_false_reject_control_boundary_answers_are_cached(tmp_path):
    twelve = [chr(ord("a") + index) * 128 for index in range(12)]

    def invoke(prompt):
        return json.dumps(twelve) if "policy 0" in prompt else "[]"

    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=invoke,
        on_invalid="record",
    )
    rejected = tmp_path / "rejected.jsonl"
    assert not rejected.exists() or rejected.read_text(encoding="utf-8") == ""
    cache = load_extraction_cache(tmp_path, chunks(), tenant_id="acme")
    assert list(cache.entities.values()) == [twelve, [], []]
    assert cache.rejected == {}
    assert all(len(item) == 128 for item in cache.entities[next(iter(cache.entities))])


def test_load_extraction_cache_refuses_missing_chunk(tmp_path):
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=lambda _: '["awb"]',
        max_calls=2,
    )
    with pytest.raises(ValueError, match=r"cached=2.*rejected=0.*total=3"):
        load_extraction_cache(tmp_path, chunks(), tenant_id="acme")


def test_load_extraction_cache_refuses_changed_chunk_text(tmp_path):
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=lambda _: '["awb"]',
    )
    changed = chunks()
    changed[0].page_content = "changed"
    with pytest.raises(ValueError):
        load_extraction_cache(tmp_path, changed, tenant_id="acme")


def test_load_extraction_cache_refuses_missing_manifest(tmp_path):
    (tmp_path / "entities.jsonl").write_text(
        json.dumps({"chunk_id": "x", "content_sha256": "a" * 64, "entities": ["awb"]}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="manifest"):
        load_extraction_cache(tmp_path, chunks(), tenant_id="acme")


def test_load_extraction_cache_refuses_tampered_rejection(tmp_path):
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model=MODEL,
        cache_dir=tmp_path,
        invoke=lambda prompt: "nonsense" if "policy 0" in prompt else '["awb"]',
        on_invalid="record",
    )
    path = tmp_path / "rejected.jsonl"
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    row["content_sha256"] = OTHER
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_extraction_cache(tmp_path, chunks(), tenant_id="acme")


@pytest.mark.parametrize("model", ["qwen2.5", "qwen2.5:latest"])
def test_cli_ollama_model_must_be_tagged(tmp_path, model):
    from scripts.extract_graph_entities import main

    with pytest.raises(SystemExit):
        main(
            [
                "--provider",
                "ollama",
                "--chunks",
                str(tmp_path / "missing.json"),
                "--chunks-sha256",
                CORPUS,
                "--corpus-sha256",
                CORPUS,
                "--model",
                model,
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )


def test_cli_ollama_dry_run_resolves_digest_without_chat(tmp_path, monkeypatch, capsys):
    from scripts.extract_graph_entities import main

    source = write_chunks(tmp_path / "chunks.json")
    fake = FakeOllama(DIGEST)
    monkeypatch.setattr("llm.providers.pinned_ollama._urlopen", fake)
    assert main(cli_args(tmp_path, source, provider="ollama", max_calls=0)) == 0
    assert chat_requests(fake) == []
    assert any(item.full_url.endswith("/api/tags") for item in fake.requests)
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "ollama"
    assert payload["model_digest"] == DIGEST
    assert payload["rejected"] == 0


def test_cli_mistral_dry_run_records_null_digest(tmp_path, monkeypatch, capsys):
    from scripts.extract_graph_entities import main

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    source = write_chunks(tmp_path / "chunks.json")
    assert main(cli_args(tmp_path, source, model="mistral-small-2506")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "mistral"
    assert payload["model_digest"] is None
    manifest = json.loads((tmp_path / "cache" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider"] == "mistral"
    assert manifest["model_digest"] is None


def test_resolve_names_the_model_when_missing():
    fake = FakeOllama(DIGEST, model="other:tag")
    with pytest.raises(RuntimeError, match=MODEL):
        resolve_ollama_digest(BASE, MODEL, opener=fake)


@pytest.mark.parametrize("digest", ["sha256:" + DIGEST, DIGEST.upper(), DIGEST[:63], None])
def test_resolve_refuses_malformed_digest(digest):
    with pytest.raises(RuntimeError, match=MODEL):
        resolve_ollama_digest(BASE, MODEL, opener=FakeOllama(digest))


def test_resolve_refuses_unreachable_server():
    def refused(request, timeout=None):
        raise URLError("refused")

    with pytest.raises(RuntimeError, match=MODEL):
        resolve_ollama_digest(BASE, MODEL, opener=refused)


def test_resolve_wraps_incomplete_read():
    def cut(request, timeout=None):
        raise http.client.IncompleteRead(b"[")

    with pytest.raises(RuntimeError, match=MODEL) as caught:
        resolve_ollama_digest(BASE, MODEL, opener=cut)
    assert not isinstance(caught.value, http.client.IncompleteRead)


def test_non_json_chat_body_is_not_retried(tmp_path):
    fake = FakeOllama(DIGEST)
    original = fake.__call__

    def garbage(request, timeout=None):
        if request.full_url.endswith("/api/chat"):
            fake.requests.append(request)
            return FakeResponse(b"<html>")
        return original(request, timeout)

    with pytest.raises(RuntimeError, match="non-JSON"):
        run_ollama(tmp_path, fake, pinned=client(garbage), max_calls=1)
    assert len(chat_requests(fake)) == 1
    assert not (tmp_path / "entities.jsonl").exists()


def test_invalid_model_digest_argument_is_refused(tmp_path):
    with pytest.raises(ValueError, match="digest"):
        extract_entities(
            chunks(),
            tenant_id="acme",
            corpus_sha256=CORPUS,
            model=MODEL,
            cache_dir=tmp_path,
            invoke=lambda _: pytest.fail("provider called"),
            provider="ollama",
            model_digest="abc",
        )


def test_schema_v1_cache_is_refused_before_provider(tmp_path):
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model="mistral-small-2506",
        cache_dir=tmp_path,
        invoke=lambda _: pytest.fail("provider called"),
        max_calls=0,
    )
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.pop("provider")
    manifest.pop("generation")
    manifest["schema_version"] = 1
    path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    with pytest.raises(ValueError, match="provenance"):
        extract_entities(
            chunks(),
            tenant_id="acme",
            corpus_sha256=CORPUS,
            model=MODEL,
            cache_dir=tmp_path,
            invoke=lambda _: pytest.fail("provider called"),
            provider="ollama",
            model_digest=DIGEST,
        )


def test_schema_version_only_mismatch_is_named(tmp_path):
    extract_entities(
        chunks(),
        tenant_id="acme",
        corpus_sha256=CORPUS,
        model="mistral-small-2506",
        cache_dir=tmp_path,
        invoke=lambda _: pytest.fail("provider called"),
        max_calls=0,
    )
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.pop("provider")
    manifest.pop("generation")
    manifest["schema_version"] = 1
    path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    with pytest.raises(ValueError, match="schema_version"):
        extract_entities(
            chunks(),
            tenant_id="acme",
            corpus_sha256=CORPUS,
            model="mistral-small-2506",
            cache_dir=tmp_path,
            invoke=lambda _: pytest.fail("provider called"),
        )


def test_local_route_docs_use_per_model_cache_dir():
    text = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "operations"
        / "gr2-entity-builder-preparation.md"
    ).read_text(encoding="utf-8")
    assert "ollama-qwen2.5-7b" in text
    assert "schema_version 1 caches are refused" in text
    assert "--cache-dir reports/kb_graph/" in text
    assert text.index("ollama-qwen2.5-7b") > text.index("## Local route")


def test_cli_ollama_empty_tag_is_usage_error(tmp_path):
    from scripts.extract_graph_entities import main

    with pytest.raises(SystemExit):
        main(
            [
                "--provider",
                "ollama",
                "--chunks",
                str(tmp_path / "missing.json"),
                "--chunks-sha256",
                CORPUS,
                "--corpus-sha256",
                CORPUS,
                "--model",
                "qwen2.5:",
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )
