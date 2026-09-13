"""GR-2 production classifier cache: routing comes from classify_complexity, not labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from agent.graph import _CLASSIFY_COMPLEXITY_SCHEMA
from agent.prompts import build_classify_complexity_prompt
from llm.providers import LLMResponse
from llm.providers.pinned_ollama import PinnedOllamaChat

MODEL = "qwen2.5:7b"
DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
OTHER = "b" * 64
DATASET = "a" * 64
BASE = "http://127.0.0.1:11434"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096}
SCHEMA_OK = {
    "complexity": "complex",
    "question_class": "multi_hop",
    "entities": ["AWB", "перевозчик"],
    "needs_multi_hop": True,
    "reason_code": "MULTI_SOURCE_CHAIN",
}
CLASS_ANSWERS = (
    {
        "complexity": "simple",
        "question_class": "single_hop",
        "entities": ["AWB"],
        "needs_multi_hop": False,
        "reason_code": "SINGLE_SOURCE",
    },
    SCHEMA_OK,
    {
        "complexity": "complex",
        "question_class": "aggregation",
        "entities": ["рейс", "груз"],
        "needs_multi_hop": True,
        "reason_code": "MULTI_SOURCE_AGGREGATION",
    },
    {
        "complexity": "global",
        "question_class": "global",
        "entities": ["процесс"],
        "needs_multi_hop": True,
        "reason_code": "CORPUS_GLOBAL",
    },
)


def sample_cases() -> list[dict[str, object]]:
    return [
        {"case_id": "c1", "query": "Где AWB 123?", "question_class": "single_hop"},
        {"case_id": "c2", "query": "Свяжи AWB и перевозчика"},
        {"case_id": "c3", "query": "Какие темы повторяются по корпусу?"},
    ]


class FakeClassifier:
    provider_id = "ollama"
    model_name = MODEL
    model_digest = DIGEST
    supports_structured_output = True
    options = OPTIONS

    def __init__(self, answers: list[dict[str, object]] | None = None) -> None:
        self.answers = list(answers if answers is not None else [SCHEMA_OK])
        self.calls: list[tuple[object, object]] = []
        self.failures: list[BaseException] = []
        self.last_response: LLMResponse | None = None
        self._index = 0
        self.fail_on: int | None = None

    def generate_with_schema(self, messages, schema, **kwargs):
        _ = kwargs
        self.calls.append((messages, schema))
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            exc = RuntimeError("provider unavailable")
            self.failures.append(exc)
            raise exc
        payload = self.answers[min(self._index, len(self.answers) - 1)]
        self._index += 1
        response = LLMResponse(
            text=json.dumps(payload, ensure_ascii=False),
            provider=self.provider_id,
            model=self.model_name,
            structured_output=payload,
        )
        self.last_response = response
        return response


class FakeResponse:
    def __init__(self, payload: object) -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeOllama:
    def __init__(
        self,
        digest: str,
        *,
        model: str = MODEL,
        answers: list[str] | None = None,
        errors: list[BaseException] | None = None,
        error_after: int = 0,
    ) -> None:
        self.digest = digest
        self.model = model
        self.answers = list(answers if answers is not None else [json.dumps(SCHEMA_OK)])
        self.errors = list(errors or [])
        self.error_after = error_after
        self.requests: list[object] = []
        self._chat_i = 0

    def __call__(self, request, timeout=None):
        _ = timeout
        self.requests.append(request)
        url = request.full_url
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": self.model, "digest": self.digest}]})
        if url.endswith("/api/chat"):
            if self.errors and self._chat_i >= self.error_after:
                raise self.errors.pop(0)
            answer = self.answers[min(self._chat_i, len(self.answers) - 1)]
            self._chat_i += 1
            return FakeResponse({"message": {"content": answer}})
        raise AssertionError(url)


def chat_requests(fake: FakeOllama) -> list[object]:
    return [item for item in fake.requests if item.full_url.endswith("/api/chat")]


def rows_path(cache_dir: Path) -> Path:
    return cache_dir / "classifications.jsonl"


def read_rows(cache_dir: Path) -> list[dict[str, object]]:
    path = rows_path(cache_dir)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def classify(cache_dir: Path, classifier=None, cases=None, **kwargs):
    from evaluation.query_classification import classify_cases

    return classify_cases(
        cases if cases is not None else sample_cases(),
        dataset_sha256=kwargs.pop("dataset_sha256", DATASET),
        classifier=classifier or FakeClassifier(),
        cache_dir=cache_dir,
        **kwargs,
    )


def adapter(fake: FakeOllama, **kwargs):
    from evaluation.query_classification import PinnedOllamaClassifier

    params = dict(opener=fake, sleeper=lambda _delay: None, timeout=1.0, max_attempts=1)
    params.update(kwargs)
    chat = PinnedOllamaChat(BASE, MODEL, DIGEST, **params)
    return PinnedOllamaClassifier(chat, model_name=MODEL, model_digest=DIGEST)


def patch_manifest(cache_dir: Path, **updates: object) -> None:
    path = cache_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(updates)
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_cases(path: Path, cases: list[dict[str, object]]) -> Path:
    path.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    return path


def cli_args(tmp_path: Path, source: Path, **extra: object) -> list[str]:
    args = [
        "--cases",
        str(source),
        "--cases-sha256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
        "--model",
        str(extra.pop("model", MODEL)),
        "--cache-dir",
        str(tmp_path / "cache"),
    ]
    for key, value in extra.items():
        args.extend([f"--{key.replace('_', '-')}", str(value)])
    return args


def test_schema_conforming_response_is_cached_with_every_field(tmp_path: Path) -> None:
    cached = classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    row = cached["c1"]
    assert row["case_id"] == "c1"
    assert row["query_sha256"] == hashlib.sha256("Где AWB 123?".encode("utf-8")).hexdigest()
    assert row["complexity"] == "complex"
    assert row["question_class"] == "multi_hop"
    assert row["entities"] == ["AWB", "перевозчик"]
    assert row["needs_multi_hop"] is True
    assert row["reason_code"] == "MULTI_SOURCE_CHAIN"
    stored = read_rows(tmp_path)
    assert stored == [row]


def test_dataset_question_class_does_not_influence_cached_classification(tmp_path: Path) -> None:
    cases = sample_cases()[:1]
    assert cases[0]["question_class"] == "single_hop"
    cached = classify(tmp_path, FakeClassifier(), cases=cases)
    assert cached["c1"]["question_class"] == "multi_hop"
    assert cached["c1"]["question_class"] != cases[0]["question_class"]


def test_transport_failure_keeps_first_row_and_resume_skips_cached(tmp_path: Path) -> None:
    first = FakeClassifier()
    first.fail_on = 2
    with pytest.raises(RuntimeError, match="provider unavailable"):
        classify(tmp_path, first)
    stored = read_rows(tmp_path)
    assert [row["case_id"] for row in stored] == ["c1"]
    assert len(first.calls) == 2

    resumed = FakeClassifier()
    cached = classify(tmp_path, resumed)
    assert [row["case_id"] for row in read_rows(tmp_path)] == ["c1", "c2", "c3"]
    assert len(resumed.calls) == 2
    assert set(cached) == {"c1", "c2", "c3"}


def test_load_classifications_names_dataset_digest_mismatch(tmp_path: Path) -> None:
    from evaluation.query_classification import load_classifications

    classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    with pytest.raises(ValueError, match="dataset_sha256") as excinfo:
        load_classifications(tmp_path, cases=sample_cases()[:1], dataset_sha256=OTHER)
    assert DATASET in str(excinfo.value)
    assert OTHER in str(excinfo.value)


def test_load_classifications_names_changed_query_text(tmp_path: Path) -> None:
    from evaluation.query_classification import load_classifications

    cases = sample_cases()[:1]
    classify(tmp_path, FakeClassifier(), cases=cases)
    changed = [{"case_id": "c1", "query": "changed query"}]
    with pytest.raises(ValueError, match="query_sha256") as excinfo:
        load_classifications(tmp_path, cases=changed, dataset_sha256=DATASET)
    assert "c1" in str(excinfo.value)


def test_manifest_digest_mismatch_is_refused_before_any_request(tmp_path: Path) -> None:
    classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["model_digest"] = OTHER
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    spy = FakeClassifier()
    with pytest.raises(ValueError, match="model_digest"):
        classify(tmp_path, spy, cases=sample_cases()[:1])
    assert spy.calls == []


def test_cli_max_calls_zero_sends_no_generation_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts.classify_eval_queries import main

    source = write_cases(tmp_path / "cases.jsonl", sample_cases())
    fake = FakeOllama(DIGEST)
    monkeypatch.setattr("llm.providers.pinned_ollama._urlopen", fake)
    args = cli_args(tmp_path, source, max_calls=0)
    assert main(args) == 0
    assert chat_requests(fake) == []
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "partial"
    assert summary["cases"] == 3
    assert summary["cached"] == 0
    assert summary["model_digest"] == DIGEST
    assert summary["question_class"] == {}
    source.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        main(args)
    assert chat_requests(fake) == []


def test_production_node_sends_resolved_prompt_and_schema(tmp_path: Path) -> None:
    question = "Как связать AWB с ответственностью перевозчика?"
    fake = FakeOllama(DIGEST)
    classify(
        tmp_path,
        adapter(fake),
        cases=[{"case_id": "c1", "query": question, "question_class": "single_hop"}],
    )
    chats = chat_requests(fake)
    assert len(chats) == 1
    body = json.loads(chats[0].data.decode("utf-8"))
    assert body["format"] == _CLASSIFY_COMPLEXITY_SCHEMA
    assert body["messages"][0]["content"] == build_classify_complexity_prompt(question)
    assert body["options"] == OPTIONS
    row = read_rows(tmp_path)[0]
    assert row["question_class"] == "multi_hop"
    assert row["entities"] == ["AWB", "перевозчик"]


def test_routing_flag_does_not_outlive_the_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import config.settings as settings_mod

    sentinel = SimpleNamespace(model_routing_enabled=False)
    monkeypatch.setattr(settings_mod, "get_settings", lambda: sentinel)
    classifier = FakeClassifier()
    cached = classify(tmp_path, classifier, cases=sample_cases()[:1])
    assert classifier.calls
    assert cached["c1"]["question_class"] == "multi_hop"
    assert settings_mod.get_settings() is sentinel
    assert settings_mod.get_settings().model_routing_enabled is False


def test_incomplete_tail_is_not_truncated(tmp_path: Path) -> None:
    classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    path = rows_path(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
    spy = FakeClassifier()
    with pytest.raises(ValueError, match="incomplete"):
        classify(tmp_path, spy, cases=sample_cases()[:1])
    assert spy.calls == []
    assert not path.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize("payload", CLASS_ANSWERS, ids=lambda item: str(item["question_class"]))
def test_schema_conforming_answer_for_each_question_class_is_cached(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    cached = classify(tmp_path, FakeClassifier([payload]), cases=sample_cases()[:1])
    row = cached["c1"]
    for field in ("complexity", "question_class", "entities", "needs_multi_hop", "reason_code"):
        assert row[field] == payload[field]
    assert read_rows(tmp_path) == [row]


def test_duplicate_or_oversized_entities_are_dropped_but_row_is_cached(tmp_path: Path) -> None:
    payload = {
        **SCHEMA_OK,
        "entities": ["AWB", "AWB", "x" * 200, "перевозчик"],
    }
    cached = classify(tmp_path, FakeClassifier([payload]), cases=sample_cases()[:1])
    assert cached["c1"]["entities"] == ["AWB", "перевозчик"]
    assert cached["c1"]["question_class"] == "multi_hop"
    assert cached["c1"]["reason_code"] == "MULTI_SOURCE_CHAIN"
    assert cached["c1"]["needs_multi_hop"] is True
    assert read_rows(tmp_path) == [cached["c1"]]


@pytest.mark.parametrize("content", ["[]", "{}"])
def test_empty_json_answer_is_not_cached_and_restart_retries(tmp_path: Path, content: str) -> None:
    fake = FakeOllama(DIGEST, answers=[content])
    with pytest.raises(RuntimeError):
        classify(tmp_path, adapter(fake), cases=sample_cases()[:1])
    assert read_rows(tmp_path) == []
    resumed = FakeOllama(DIGEST, answers=[json.dumps(SCHEMA_OK)])
    classify(tmp_path, adapter(resumed), cases=sample_cases()[:1])
    assert [row["case_id"] for row in read_rows(tmp_path)] == ["c1"]
    assert len(chat_requests(resumed)) == 1


@pytest.mark.parametrize("field,value", [("reason_code", "NOPE"), ("question_class", "NOPE")])
def test_node_result_outside_sgr_enums_is_not_cached(
    tmp_path: Path, field: str, value: str
) -> None:
    payload = dict(SCHEMA_OK)
    payload[field] = value
    spy = FakeClassifier([payload])
    with pytest.raises(ValueError, match="c1"):
        classify(tmp_path, spy, cases=sample_cases()[:1])
    assert read_rows(tmp_path) == []
    assert spy.calls


def test_load_classifications_refuses_unknown_question_class_row(tmp_path: Path) -> None:
    from evaluation.query_classification import load_classifications

    classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    row = read_rows(tmp_path)[0]
    row["question_class"] = "unknown"
    rows_path(tmp_path).write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="question_class"):
        load_classifications(tmp_path, cases=sample_cases()[:1], dataset_sha256=DATASET)


def test_load_classifications_refuses_invalid_reason_code_row(tmp_path: Path) -> None:
    from evaluation.query_classification import load_classifications

    classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    row = read_rows(tmp_path)[0]
    row["reason_code"] = "SCHEMA_FIELDS_INVALID"
    rows_path(tmp_path).write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reason_code"):
        load_classifications(tmp_path, cases=sample_cases()[:1], dataset_sha256=DATASET)


def test_manifest_options_match_transport_request(tmp_path: Path) -> None:
    custom = {"temperature": 0.7, "seed": 1, "num_ctx": 8192}
    fake = FakeOllama(DIGEST)
    classify(tmp_path, adapter(fake, options=custom), cases=sample_cases()[:1])
    chats = chat_requests(fake)
    assert len(chats) == 1
    body = json.loads(chats[0].data.decode("utf-8"))
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"] == body["options"] == custom


def test_classifier_without_options_is_refused_before_any_call(tmp_path: Path) -> None:
    spy = FakeClassifier()
    spy.options = None
    with pytest.raises(ValueError, match="options"):
        classify(tmp_path, spy, cases=sample_cases()[:1])
    assert spy.calls == []
    assert not rows_path(tmp_path).exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", 99),
        ("prompt_template_sha256", OTHER),
        ("schema_sha256", OTHER),
    ],
)
def test_load_classifications_refuses_stale_code_manifest_key(
    tmp_path: Path, key: str, value: object
) -> None:
    from evaluation.query_classification import load_classifications

    classify(tmp_path, FakeClassifier(), cases=sample_cases()[:1])
    patch_manifest(tmp_path, **{key: value})
    with pytest.raises(ValueError, match=key) as excinfo:
        load_classifications(tmp_path, cases=sample_cases()[:1], dataset_sha256=DATASET)
    assert key in str(excinfo.value)


def test_cli_refuses_changed_weights_digest_before_chat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.classify_eval_queries import main

    source = write_cases(tmp_path / "cases.jsonl", sample_cases())
    first = FakeOllama(DIGEST)
    monkeypatch.setattr("llm.providers.pinned_ollama._urlopen", first)
    assert main(cli_args(tmp_path, source, max_calls=1)) == 0
    assert len(chat_requests(first)) == 1

    second = FakeOllama(OTHER)
    monkeypatch.setattr("llm.providers.pinned_ollama._urlopen", second)
    with pytest.raises(ValueError, match="model_digest"):
        main(cli_args(tmp_path, source, max_calls=3))
    assert chat_requests(second) == []


def test_http_transport_failure_on_second_case_is_not_cached(tmp_path: Path) -> None:
    fake = FakeOllama(
        DIGEST,
        answers=[json.dumps(SCHEMA_OK)] * 3,
        errors=[URLError("refused")],
        error_after=1,
    )
    with pytest.raises(RuntimeError):
        classify(tmp_path, adapter(fake), cases=sample_cases())
    assert [row["case_id"] for row in read_rows(tmp_path)] == ["c1"]
    resumed = FakeOllama(DIGEST, answers=[json.dumps(SCHEMA_OK)] * 3)
    classify(tmp_path, adapter(resumed), cases=sample_cases())
    assert [row["case_id"] for row in read_rows(tmp_path)] == ["c1", "c2", "c3"]
    assert len(chat_requests(resumed)) == 2
