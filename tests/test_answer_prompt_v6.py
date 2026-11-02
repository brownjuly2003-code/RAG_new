"""V6 registration: synthetic inputs only; never contacts a model or reads a base."""

import asyncio
import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/answer-prompt-v6/tools"


@pytest.fixture(scope="module")
def synthetic_tmp():
    # Windows sandbox identities cannot reopen pytest's mode-0700 directories.
    # Ordinary inherited permissions suffice for these entirely synthetic files.
    import shutil

    parent = Path(tempfile.gettempdir()).resolve()
    root = parent / ("answer-v6-synthetic-" + uuid.uuid4().hex)
    root.mkdir()

    def make(name="case"):
        path = root / (name + "-" + uuid.uuid4().hex)
        path.mkdir()
        return path

    yield make
    assert root.parent == parent and root.name.startswith("answer-v6-synthetic-")
    shutil.rmtree(root)


@pytest.fixture
def tmp_path(synthetic_tmp):
    return synthetic_tmp()


@pytest.fixture
def registered_unicode(monkeypatch):
    # The Mac test interpreter has a newer regex; exercise registered metadata
    # synthetically here. Production chain/plan compare the actual runtime.
    monkeypatch.setattr(__import__("regex"), "__version__", "2026.5.9")
    monkeypatch.setattr(__import__("unicodedata"), "unidata_version", "14.0.0")


@pytest.fixture(scope="module")
def v6():
    before = sys.path[:]
    sys.path.insert(0, str(TOOLS))
    modules = {}
    for name in (
        "shown_text",
        "v6_common",
        "v6_replay",
        "v6_judge",
        "v6_record",
        "v6_chain",
        "v6_key",
    ):
        spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    yield modules
    sys.path[:] = before


@pytest.mark.parametrize(
    "raw,text,flags",
    [
        ("<evidence>secret</evidence><answer>Shown.</answer>secret", "Shown.", []),
        ("<ANSWER> first </AnSwEr><answer>second</answer>", "first", []),
        ("<answer>first<evidence>secret", "first", []),
        ("<answer>tail", "tail", []),
        ("<answer> </answer><answer>later</answer>", "", ["parse"]),
        ("no answer", "", ["parse"]),
    ],
)
def test_parse(v6, raw, text, flags):
    assert v6["shown_text"].shown_text(raw, "Q?") == {"text": text, "flags": flags}


@pytest.mark.parametrize(
    "text",
    [
        "1. First item.\n2. Second item.\n1. Third item.",
        "Use e.g. here. Another e.g. there. Final e.g. example.",
        "Это т.е. пример. Другой т.е. случай. Третий т.е. вариант.",
        "Value 3.5 here. Value 3.5 there. Value 3.5 elsewhere.",
        "a b c d e f g x a b c d e f g y a b c d e f g z",
        "A short line. A short line.",
        "literal <custom> stays here",
    ],
)
def test_f1_ordinary_reuse_and_f12_literal_spans(v6, text):
    assert v6["shown_text"].shown_text("<answer>" + text, "?") == {"text": text, "flags": []}


@pytest.mark.parametrize("length", [4, 5, 6, 7])
def test_f1_shared_phrases_across_items(v6, length):
    phrase = " ".join("one two three four five six seven".split()[:length])
    text = f"1. First item: {phrase} x, {phrase} y.\n2. Second item: {phrase} z."
    assert v6["shown_text"].shown_text("<answer>" + text, "?") == {"text": text, "flags": []}


def test_r0_r1_r2_r5_and_chunk_monotonicity(v6):
    show = v6["shown_text"].shown_text
    raw = "<evidence>hidden</evidence><answer>" + "a" * 40 + ". Next unit. tail</answer>"
    previous = ""
    for index in range(len(raw) + 1):
        got = show(raw[:index], "abcdefghijkl", finished=False)
        assert got["text"].startswith(previous)
        previous = got["text"]
    assert previous == show(raw, "abcdefghijkl")["text"]
    assert show("<answer>open", "?", finished=False)["text"] == ""
    assert show("<answer>short. ", "abcdefghijkl", finished=False)["text"] == ""
    assert show("<answer>short. ", "?", finished=False)["text"] == "short."


def test_r2_early_language_and_r3_no_retraction(v6):
    show = v6["shown_text"].shown_text
    first = "a" * 40 + ". "
    mismatch = "я" * 100 + ". "
    assert show("<answer>" + mismatch, "abcdefghijkl", finished=False)["flags"] == ["language"]
    got = show("<answer>" + first + mismatch + "tail", "abcdefghijkl")
    assert got == {"text": first.strip(), "flags": ["language_after_release"]}


def test_r1_cjk_boundaries_and_r4_would_be_cut(v6):
    show = v6["shown_text"].shown_text
    assert show("<answer>第一句。第二句", "?", finished=False)["text"] == "第一句。"
    gram = "one two three four five six seven eight"
    raw = f"<answer>{gram} x {gram} y {gram} z</answer>"
    assert show(raw, "?")["flags"] == ["repeat"]


@pytest.mark.parametrize(
    "codes",
    ["ABC DEF GHI", "АБВ ГДЕ ЖЗИ", "camelCase otherCode", "snake_case other_name", "abc123 def456"],
)
def test_f5_identifier_tokens_ignored_on_both_sides(v6, codes):
    show = v6["shown_text"].shown_text
    question = "Как получить нужную информацию " + codes
    assert show("<answer>Доступна следующая информация " + codes, question)["flags"] == []
    assert show("<answer>abcdefghijkl", question)["flags"] == ["language"]


@pytest.mark.parametrize(
    "sentence",
    [
        "A truly useful sentence",
        "Это действительно нужное предложение",
        "Αυτή είναι χρήσιμη πρόταση",
    ],
)
def test_sentence_repeat_first_occurrence_and_normalisation(v6, sentence):
    show = v6["shown_text"].shown_text
    assert show(f"<answer>{sentence}. Unique.</answer>", "?")["flags"] == []
    got = show(f"<answer>{sentence}. {sentence.upper()}! Lost.</answer>", "?")
    assert got == {"text": sentence + ".", "flags": ["repeat"]}


@pytest.mark.parametrize(
    "gram",
    [
        "one two three four five six seven eight",
        "один два три четыре пять шесть семь восемь",
        "ένα δύο τρία τέσσερα πέντε έξι επτά οκτώ",
    ],
)
def test_ngram_second_repeat_edge(v6, gram):
    show = v6["shown_text"].shown_text
    assert show(f"<answer>{gram} x {gram}</answer>", "?")["flags"] == []
    got = show(f"<answer>{gram} x {gram} y {gram} z</answer>", "?")
    assert got == {"text": f"{gram} x {gram} y", "flags": ["repeat"]}


@pytest.mark.parametrize("question,answer", [("a", "я"), ("я", "α"), ("α", "a")])
def test_language_minimum_dominance_quotes_and_citations(v6, question, answer):
    show = v6["shown_text"].shown_text
    assert show(f"<answer>{answer * 12}</answer>", question * 11)["flags"] == []
    assert show(f"<answer>{answer * 11}</answer>", question * 12)["flags"] == []
    assert show(f"<answer>{answer * 12}</answer>", question * 12)["flags"] == ["language"]
    # Exactly 60% is dominant; below it abstains. Both sides use all letters as denominator.
    mixed = answer * 12 + question * 8
    assert show(f"<answer>{mixed}</answer>", question * 12)["flags"] == ["language"]
    assert show(f"<answer>{mixed}{question}</answer>", question * 12)["flags"] == []
    assert (
        show(f'<answer>{question * 12} "{answer * 40}" [12]</answer>', question * 12)["flags"] == []
    )
    assert show(f"<answer>«{answer * 40}»</answer>", question * 12)["flags"] == []


def test_fallback_is_a_fresh_package_call_and_stream_does_not_leak(v6):
    class Model:
        def __init__(self):
            self.calls = []

        async def generate_stream(self, messages, **kwargs):
            self.calls.append((messages, kwargs))
            tokens = ["<evidence>private</evidence>"] if len(self.calls) == 1 else [" package "]
            for token in tokens:
                yield token

    model = Model()
    result = asyncio.run(
        v6["v6_replay"].answer(model, "V6", "PACKAGE", "Question?", {"max_tokens": 1024})
    )
    assert result["answer"] == " package "
    assert result["flags"] == ["parse"]
    assert [c[0][0]["content"] for c in model.calls] == ["V6", "PACKAGE"]
    assert model.calls[0][1] == model.calls[1][1] == {"max_tokens": 1024}
    assert result["first_shown_sec"] >= result["v6_stream_sec"]
    assert result["fallback_stream_sec"] >= 0


def test_stream_does_not_cut_on_an_unfinished_word(v6):
    class Model:
        async def generate_stream(self, messages, **kwargs):
            for token in (
                "<answer>one two three four five six seven eight x one two three four five six seven eight y one two three four five six seven eight",
                "een.</answer>",
            ):
                yield token

    result = asyncio.run(v6["v6_replay"].answer(Model(), "V6", "PACKAGE", "?", {}))
    assert result["answer"].endswith("eighteen.")
    assert result["flags"] == []


def test_stream_does_not_cut_an_unfinished_sentence(v6):
    class Model:
        async def generate_stream(self, messages, **kwargs):
            for token in ("<answer>This is one line. This is one line ", "with more.</answer>"):
                yield token

    result = asyncio.run(v6["v6_replay"].answer(Model(), "V6", "PACKAGE", "?", {}))
    assert result["answer"] == "This is one line. This is one line with more."


def test_multiline_quoted_passages_do_not_determine_script(v6):
    got = v6["shown_text"].shown_text(
        '<answer>abcdefghijkl "яяяяяяяяяяяя\nяяяяяяяяяяяя"</answer>', "abcdefghijkl"
    )
    assert got["flags"] == []


def test_newlines_are_sentence_boundaries(v6):
    assert v6["shown_text"].shown_text(
        "<answer>Same complete line here\nSame complete line here\nLost</answer>", "?"
    ) == {
        "text": "Same complete line here",
        "flags": ["repeat"],
    }


def test_repeat_preserves_the_preceding_sentences_citation(v6):
    assert v6["shown_text"].shown_text(
        "<answer>This is the sentence. [1] This is the sentence. [2]</answer>", "?"
    ) == {
        "text": "This is the sentence. [1]",
        "flags": ["repeat"],
    }


def test_private_output_cannot_overwrite_tool_library(v6):
    with pytest.raises(SystemExit, match="outside"):
        v6["v6_common"].outside(TOOLS)


def test_record_requires_both_primary_bases_and_admitted_plans(v6):
    decide = v6["v6_record"].decision
    corpora = {
        k: {"bad": {"direction": "falls"}, "good": {"direction": "not detected"}}
        for k in ("wixqa", "conditionalqa", "aircargo")
    }
    got = decide(
        {"keys": ["wixqa"], "direction": "falls"}, None, corpora, list(corpora), list(corpora), {}
    )
    assert got["decision"] == "NOT_EVIDENCE"


@pytest.mark.parametrize(
    "kind",
    ["bad", "good", "declines", "pooled", "recall", "uncounted", "missing", "gain", "no_gain"],
)
def test_every_decision_row(v6, kind):
    module = v6["v6_record"]
    keys = list(v6["v6_common"].KEYS)
    corpora = {
        k: {"bad": {"direction": "not detected"}, "good": {"direction": "not detected"}}
        for k in keys
    }
    primary = {"keys": keys[:2], "direction": "falls"}
    recall, not_counted = None, {}
    if kind == "bad":
        corpora["aircargo"]["bad"]["direction"] = "rises"
    if kind == "good":
        corpora["wixqa"]["good"]["direction"] = "falls"
    if kind == "declines":
        corpora["conditionalqa"]["declines_without_answer"] = {"direction": "falls"}
    if kind == "pooled":
        primary["direction"] = "rises"
    if kind == "recall":
        recall = {"direction": "falls"}
    if kind == "uncounted":
        not_counted = {"wixqa": ["m2"]}
    if kind == "missing":
        keys = keys[:2]
    if kind == "no_gain":
        primary["direction"] = "not detected"
    got = module.decision(primary, recall, corpora, keys, keys, not_counted)
    expected = (
        "adopted"
        if kind == "gain"
        else "NOT_EVIDENCE"
        if kind in ("uncounted", "missing")
        else "not adopted"
    )
    assert got["decision"] == expected


def test_form_stop_strict_majority(v6):
    gate = v6["v6_replay"].form_stop
    assert not gate([{"flags": ["parse"]}] * 5 + [{"flags": ["language"]}] * 5)
    assert gate([{"flags": ["parse"]}] * 6 + [{"flags": []}] * 4)
    with pytest.raises(SystemExit):
        gate([{"flags": ["parse"]}] * 9)


@pytest.mark.parametrize("fault", ["missing", "setting", "model", "provider", "fallback"])
def test_settings_refusals(v6, fault):
    replay = v6["v6_replay"]
    values = {**dict.fromkeys(replay.v5.SETTINGS, "registered"), **replay.final.SETTINGS}
    settings = SimpleNamespace(**values)
    llm = SimpleNamespace(_provider=type("OllamaProvider", (), {})(), model_name=replay.MODEL)
    recorded = values.copy()
    replay.settings_gate(settings, recorded, llm)
    if fault == "missing":
        recorded.pop("llm_role_params_json")
    if fault == "setting":
        settings.ollama_context_window = 4096
    if fault == "model":
        llm.model_name = "other"
    if fault == "provider":
        llm._provider = object()
    if fault == "fallback":
        llm._fallback_provider = object()
    with pytest.raises(SystemExit):
        replay.settings_gate(settings, recorded, llm)


def test_parity_counts_document_excerpt_and_refuses_before_call(v6):
    replay = v6["v6_replay"]
    docs = [("toy", "a short passage")]
    prompt = "CONTEXT:\n[1 | source=toy]\na short passage\n--------------------\n\nQUESTION:\nSynthetic?\n\nWhen you rely on"

    class Builder:
        v4, v5 = "package", "v6"

        def build(self, template, question, documents):
            fitted = replay.v5.as_docs(docs if template == self.v4 else [("toy", "a short")])
            return template, prompt if template == self.v4 else "V6", fitted

    item = {"case_id": "toy-id", "batch": 1, "saved": prompt, "question": "Synthetic?"}
    got = replay.parity(Builder(), [item])
    assert len(got) == 1 and got[0]["parity"] and not got[0]["same_context"]
    assert got[0]["documents_v6"] == got[0]["documents_package"] == 1
    with pytest.raises(SystemExit):
        replay.parity(Builder(), [{**item, "saved": prompt + " changed"}])


def test_decision_rows_and_early_harm(v6):
    decide = v6["v6_record"].decision
    primary = {"keys": ["wixqa", "conditionalqa"], "direction": "falls"}
    corpora = {
        k: {"bad": {"direction": "not detected"}, "good": {"direction": "not detected"}}
        for k in ("wixqa", "conditionalqa", "aircargo")
    }
    assert decide(primary, None, corpora, list(corpora), list(corpora), {})["v6_replaces_package"]
    assert decide(
        {**primary, "direction": "not detected"}, None, corpora, list(corpora), list(corpora), {}
    )["reasons"] == ["no gain"]
    assert decide(primary, None, corpora, ["wixqa"], ["wixqa"], {})["decision"] == "NOT_EVIDENCE"
    corpora["wixqa"]["bad"]["direction"] = "rises"
    got = decide(primary, None, corpora, ["wixqa"], ["wixqa"], {"wixqa": ["missing-m2"]})
    assert got["decision"] == "not adopted" and got["harm"]


def test_spec_pins_every_new_tool_and_test(v6):
    text = (ROOT / "docs/specs/answer-prompt-v6.md").read_text("utf-8")
    pins = dict(re.findall(r"^- `([^`]+)` `([0-9a-f]{64})`", text, re.M))
    paths = [p for p in TOOLS.iterdir() if p.is_file()] + [Path(__file__)]
    for path in paths:
        assert b"\r" not in path.read_bytes()
        relative = path.relative_to(ROOT).as_posix()
        assert pins[relative] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert any(
        status in text
        for status in (
            "draft — to be cold-read and registered",
            "registered before V6's first request",
        )
    )
    assert pins["scripts/chat_answer_judge.py"] == v6["v6_common"].JUDGE_SHA
    for path in v6["v6_common"].FROZEN:
        assert pins[path] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "raw,question,flags,shown",
    [
        ("<evidence>hidden</evidence><answer>Visible.</ansWER>hidden", "?", [], "Visible."),
        (
            "<answer>This is the sentence. This is the sentence. More",
            "?",
            ["repeat"],
            "This is the sentence.",
        ),
        ("<answer>яяяяяяяяяяяя.</answer>", "abcdefghijkl", ["language"], " package "),
        (
            f"<answer>{'я' * 12}. {'я' * 12}.</answer>",
            "abcdefghijkl",
            ["language"],
            " package ",
        ),
    ],
)
def test_stream_guards_close_and_select_fallback(v6, raw, question, flags, shown):
    class Model:
        calls = 0
        closed = 0

        async def generate_stream(self, messages, **kwargs):
            self.calls += 1
            try:
                for token in (raw,) if self.calls == 1 else (" package ",):
                    yield token
            finally:
                self.closed += 1

    model = Model()
    result = asyncio.run(v6["v6_replay"].answer(model, "V6", "PACKAGE", question, {}))
    assert result["flags"] == flags and result["answer"] == shown
    assert model.calls == model.closed == (2 if "language" in flags else 1)


def test_stalled_stream_is_bounded_and_closed(v6):
    class Model:
        closed = False

        async def generate_stream(self, messages, **kwargs):
            try:
                await asyncio.sleep(10)
                yield "unreachable"
            finally:
                self.closed = True

    model = Model()
    got = asyncio.run(v6["v6_replay"].collect(model, "synthetic", {}, budget=0.01))
    assert got["timeline"]["end_state"] == "ceiling"
    assert model.closed


def test_replay_timeline_releases_before_end_and_recomputes(v6, monkeypatch):
    class Model:
        async def generate_stream(self, messages, **kwargs):
            for token in ("<answer>", "a" * 40 + ". ", "Last unit", "</answer>"):
                yield token

    replay = v6["v6_replay"]
    ticks = [0]

    def clock():
        ticks[0] += 0.001
        return ticks[0]

    monkeypatch.setattr(replay.time, "monotonic", clock)
    got = asyncio.run(replay.answer(Model(), "V6", "PACKAGE", "abcdefghijkl", {}))
    assert got["first_shown_sec"] < got["full_buffer_sec"] <= got["total_sec"]
    assert len(got["timeline"]["v6"]["chunks"]) == 4
    checked = replay.stream_reading(got["raw"], "abcdefghijkl", got["timeline"]["v6"])
    assert checked["text"] == got["answer"]
    assert checked["first_shown_sec"] == got["first_shown_sec"]


def test_stream_timeline_fallback_units_and_observed_answer_end(v6):
    reading = v6["v6_replay"].stream_reading
    raw = "<answer>Visible.</answer>"
    trace = {"chunks": [{"chars": len(raw), "sec": 1}], "end_sec": 3, "end_state": "answer_tag"}
    assert reading(raw, "?", trace)["full_buffer_sec"] == 1
    raw = "One. Second"
    trace = {
        "chunks": [{"chars": 4, "sec": 1}, {"chars": len(raw), "sec": 2}],
        "end_sec": 3,
        "end_state": "eos",
    }
    result = reading(raw, "", trace, tagged=False)
    assert result["first_shown_sec"] == 1
    assert result["unit_seconds"] == [2, 3]
    assert result["answer_open_sec"] is None


def test_stream_timeline_refuses_wrong_stop_kind(v6):
    raw = "<answer>Visible.</answer>"
    trace = {"chunks": [{"chars": len(raw), "sec": 1}], "end_sec": 1, "end_state": "policy"}
    with pytest.raises(SystemExit, match="end state"):
        v6["v6_replay"].stream_reading(raw, "?", trace)


@pytest.mark.parametrize("existing", [False, True, "partial"])
def test_key_receipt_recovers_public_summary_before_commit(v6, tmp_path, monkeypatch, existing):
    common, driver = v6["v6_common"], v6["v6_key"]
    args = SimpleNamespace(
        key="wixqa",
        private=tmp_path / "private",
        records=tmp_path / "records",
        runs=tmp_path / "runs",
        spec=tmp_path / "spec",
        config=tmp_path / "config",
        mac_stop=str(tmp_path / "STOP"),
        budget=840,
    )
    common.write(args.runs / "v6-wixqa.json", {"synthetic": True})
    common.write(args.config, {"wixqa": {}})
    receipt = args.records / "2057ad0/plans-wixqa.json"
    pin = {"answer_files": {"v6-wixqa.json": common.sha(args.runs / "v6-wixqa.json")}}
    if existing:
        common.write(receipt, pin)
    if existing == "partial":
        (args.private / "wixqa/judge.partial").mkdir(parents=True)
    freezes = []

    def freeze(*args):
        freezes.append(1)
        common.write(receipt, pin)

    monkeypatch.setattr(driver.grading, "freeze", freeze)
    monkeypatch.setattr(
        common.protocol, "committed", lambda p: common.require(False, "uncommitted")
    )
    code, status = driver.execute(args)
    assert code == 4 and str(receipt) in status
    assert common.read(receipt.parent / "v6-wixqa.json") == {"synthetic": True}
    assert not Path(args.mac_stop).exists()
    assert len(freezes) == (0 if existing is True else 1)


def test_stand_receipt_ignores_only_process_identity(v6):
    receipt = {
        "server": {"servers": [{"pid": 1, "started": "old", "binary": "same"}]},
        "settings": {"version": "same"},
        "cache_sha256": "same",
    }
    new = copy.deepcopy(receipt)
    new["server"]["servers"][0].update(pid=2, started="new")
    normalize = v6["v6_common"].stand_receipt
    assert normalize(receipt) == normalize(new)
    new["server"]["servers"][0]["binary"] = "changed"
    assert normalize(receipt) != normalize(new)


def test_chain_selected_keys_and_existing_stop(v6, tmp_path):
    chain = v6["v6_chain"]
    assert chain.selected_keys("aircargo,wixqa") == ["wixqa", "aircargo"]
    with pytest.raises(SystemExit):
        chain.selected_keys("wixqa,wixqa")
    stop = tmp_path / "STOP"
    stop.write_bytes(b"parse-majority")
    chain.failure_stop(tmp_path, "wixqa")
    assert stop.read_bytes() == b"parse-majority"


def test_regex_version_gate(v6, registered_unicode):
    import unicodedata

    import regex

    versions = {"regex_version": regex.__version__, "unidata_version": unicodedata.unidata_version}
    assert v6["v6_judge"].regex_gate(versions) == versions
    with pytest.raises(SystemExit, match="regex"):
        v6["v6_judge"].regex_gate({**versions, "regex_version": "different"})


def test_old_export_requires_lf_even_when_committed(v6, tmp_path, monkeypatch):
    path = tmp_path / "old.json"
    path.write_bytes(b"{}\r\n")
    path.with_suffix(".cases.jsonl").write_bytes(b"{}\n")
    monkeypatch.setattr(v6["v6_common"].protocol, "committed", lambda p: None)
    with pytest.raises(SystemExit, match="UTF-8/LF"):
        v6["v6_judge"].old_export(path, "wixqa", "m1")


def test_registered_keys_ignores_receipt_awaiting_commit(v6, tmp_path, monkeypatch):
    common = v6["v6_common"]
    for key in ("wixqa", "aircargo"):
        common.write(tmp_path / common.STANDS[key] / f"plans-{key}.json", {})
    monkeypatch.setattr(
        common.protocol,
        "committed",
        lambda p: common.require("aircargo" not in str(p), "not committed"),
    )
    assert v6["v6_key"].registered_keys(tmp_path) == ["wixqa"]


@pytest.mark.parametrize("fault", [None, "stand", "kwargs", "regex", "unidata"])
def test_check_runs_all_gates_without_generation_or_wait(
    v6, tmp_path, monkeypatch, capsys, fault, registered_unicode
):
    replay = v6["v6_replay"]
    if fault in ("regex", "unidata"):
        module, field = (
            ("regex", "__version__") if fault == "regex" else ("unicodedata", "unidata_version")
        )
        monkeypatch.setattr(__import__(module), field, "different")
    calls = []
    monkeypatch.setitem(
        sys.modules, "config.settings", SimpleNamespace(get_settings=lambda: object())
    )
    monkeypatch.setitem(
        sys.modules,
        "llm.providers.runtime",
        SimpleNamespace(build_provider_runtime=lambda s: SimpleNamespace(strong=object())),
    )
    monkeypatch.setitem(
        sys.modules,
        "llm.role_params",
        SimpleNamespace(
            generation_kwargs_for_role=lambda role: {
                "max_tokens": 1 if fault == "kwargs" else 1024,
                "temperature": 0.2,
            }
        ),
    )
    monkeypatch.setattr(replay, "registration", lambda p: "registered")
    monkeypatch.setattr(replay, "BATCHES", 1)
    monkeypatch.setattr(replay, "cases", lambda *a: [])
    monkeypatch.setattr(replay, "settings_gate", lambda *a: calls.append("settings"))
    monkeypatch.setattr(replay, "Builder", lambda owner: object())
    monkeypatch.setattr(replay, "parity", lambda *a: calls.append("parity") or [])
    driver = SimpleNamespace(
        code_check=lambda: "2057ad0-full",
        idle_check=lambda: calls.append("idle") or {"reasons": []},
        wait_idle=lambda *a, **k: pytest.fail("check waited"),
    )
    stand = SimpleNamespace(check=lambda: calls.append("stand") or {"binary": "same"})
    monkeypatch.setattr(
        replay, "load", lambda path, name: driver if path.endswith("run.py") else stand
    )
    batch = tmp_path / "source/final-answers-wixqa-b01"
    replay.write(batch / "effective_settings.json", {"all": {}})
    replay.write(batch / "launch.json", {"code_sha": "2057ad0-full"})
    replay.write(batch / "stand.json", {"binary": "other" if fault == "stand" else "same"})
    if fault:
        with pytest.raises(SystemExit):
            replay.run("wixqa", batch.parent, tmp_path / "out", tmp_path / "spec", True)
    else:
        replay.run("wixqa", batch.parent, tmp_path / "out", tmp_path / "spec", True)
        assert calls == ["settings", "parity", "stand", "idle"]
        assert __import__("regex").__version__ in capsys.readouterr().out
        assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "body,question,flag",
    [
        ("a" * 20 + "я" * 20 + ". tail", "abcdefghijkl", None),
        ("one two three four. one two three four. dropped", "?", "repeat"),
        ("one two three four five six seven eight x " * 3, "?", "repeat"),
        ("a" * 40 + ". " + "я" * 100 + ". dropped", "abcdefghijkl", "language_after_release"),
        ("я" * 40 + ". " + "a" * 100, "abcdefghijkl", "language"),
        ("第一 个 测试 句子。第一 个 测试 句子。", "?", "repeat"),
    ],
)
def test_every_prefix_matches_finished_policy(v6, body, question, flag):
    raw = "<answer>" + body + "</answer>"
    show = v6["shown_text"].shown_text
    previous = ""
    for index in [*range(0, len(raw), 3), len(raw)]:
        got = show(raw[:index], question, finished=False)
        assert got["text"].startswith(previous)
        previous = got["text"]
    final = show(raw, question)
    assert final["text"] == previous
    assert final["flags"] == ([flag] if flag else [])


def test_r4_cut_inside_already_released_text(v6):
    # The third 8-gram begins in unit two but completes only in unit three.
    raw = "<answer>a b c d e f g h x a b c d e f g h y a b c d. e f g h tail</answer>"
    result = v6["shown_text"].shown_text(raw, "?", details=True)
    assert result["flags"] == ["repeat"]
    assert result["text"].endswith("a b c d.")
    assert result["cut_at"] < len(result["text"])


def synthetic_runs(v6, root, version="package"):
    """Real judge layout, 100 invented cases, no product/runtime or corpus imports."""
    common = v6["v6_common"]
    from scripts import chat_answer_judge as judge

    template = (TOOLS / "qa_prompt_v6.txt").read_text("utf-8")
    if version == "package":
        template = template.replace(
            judge.PROMPT_IDS["QA_PROMPT_V5"], judge.PROMPT_IDS["QA_PROMPT_V4"]
        )
    runs, refs = {}, []
    for batch in range(1, 11):
        label = f"{'final-answers' if version == 'package' else 'v6'}-wixqa-b{batch:02d}"
        folder = root / label
        runs[label] = folder
        ids, streams = [], []
        for offset in range(10):
            number = (batch - 1) * 10 + offset
            case_id, question = f"case-{number:03d}", f"Synthetic question {number}?"
            ids.append(case_id)
            prompt = template.format(
                context_block="[1 | source=toy]\nAn invented passage.", question=question
            )
            name = f"{offset + 1:03d}-stream.txt"
            (folder / "prompts").mkdir(parents=True, exist_ok=True)
            (folder / "prompts" / name).write_bytes(prompt.encode("utf-8"))
            common.write(
                folder / "cases" / f"{offset:02d}.json",
                {
                    "case_id": case_id,
                    "question": question,
                    "answer": "An invented answer [1].",
                    "events": [{"type": "result", "answer": "An invented answer [1]."}],
                },
            )
            streams.append(
                {
                    "stage": common.v5.STAGE,
                    "event": "end",
                    "prompt_file": name,
                    "wall_sec": 1,
                    "first_chunk_sec": 0.1,
                    "chunks": 5,
                }
            )
            refs.append(
                {
                    "case_id": case_id,
                    "stratum": "answerable",
                    "cluster": f"toy-{number // 2}",
                    "reference_answers": ["An invented answer."],
                }
            )
        common.write(
            folder / "launch.json",
            {
                "code_sha": "2057ad0" + "0" * 33,
                "status": "complete",
                "cases": ids,
                "model": common.MODEL,
                "model_digest": common.DIGEST,
                "tenant": "ext_wixqa",
            },
        )
        common.public_rows(folder / "stages.jsonl", streams)
    common.public_rows(root / "references.jsonl", refs)
    return runs


@pytest.fixture(scope="module")
def package(v6, synthetic_tmp):
    root = synthetic_tmp("v6-package")
    return root, synthetic_runs(v6, root)


def test_saved_cases_use_real_unchanged_judge_parser(v6, package):
    found = v6["v6_replay"].cases(package[0], "wixqa")
    assert len(found) == 100 and found[0]["documents"] == [("toy", "An invented passage.")]


@pytest.mark.parametrize(
    "fault",
    [
        "incomplete",
        "stand",
        "model",
        "order",
        "missing",
        "duplicate",
        "cr",
        "timing",
        "chunks",
        "appledouble",
    ],
)
def test_saved_case_refusals(v6, package, tmp_path, fault):
    import shutil

    root = tmp_path / "runs"
    shutil.copytree(package[0], root)
    common = v6["v6_common"]
    folder = root / "final-answers-wixqa-b01"
    launch = common.read(folder / "launch.json")
    if fault == "incomplete":
        launch["status"] = "running"
    if fault == "stand":
        launch["code_sha"] = "another"
    if fault == "model":
        launch["model_digest"] = "another"
    if fault == "order":
        launch["cases"].reverse()
    common.write(folder / "launch.json", launch)
    if fault == "missing":
        (folder / "cases/00.json").unlink()
    if fault == "duplicate":
        shutil.copyfile(folder / "cases/00.json", folder / "cases/extra.json")
    if fault == "cr":
        prompt = folder / "prompts/001-stream.txt"
        prompt.write_bytes(prompt.read_bytes().replace(b"\n", b"\r\n"))
    if fault in ("timing", "chunks"):
        streams = common.rows(folder / "stages.jsonl")
        streams[0]["wall_sec" if fault == "timing" else "chunks"] = -1
        common.public_rows(folder / "stages.jsonl", streams)
    if fault == "appledouble":
        (folder / "._launch.json").write_bytes(b"sidecar")
    with pytest.raises((SystemExit, ValueError)):
        v6["v6_replay"].cases(root, "wixqa")


def synthetic_sender(system, message):
    from evaluation import isolated_request as isolated

    verdict = {
        "claims_total": 1,
        "claims_supported": 1,
        "context_has_answer": True,
        "answers_question": "full",
        "citations_supported": 1,
        "defect": "none",
        "note": "synthetic",
        "reference": "none" if message.endswith("REFERENCE ANSWER:\nnone\n") else "agrees",
    }
    session = {
        "cli_version": "9.9.9",
        "model": isolated.MODEL,
        "loaded": {k: [] for k in isolated.LOADED},
        "builtin": {"plugins": [], "agents": []},
        "turns": 1,
        "context_tokens": 100,
    }
    return isolated.IsolatedReply(json.dumps(verdict), isolated.MODEL, {}, 1.0, session)


@pytest.fixture(scope="module")
def planned(v6, synthetic_tmp):
    from scripts import chat_answer_judge as judge

    root = synthetic_tmp("v6-plans")
    runs = synthetic_runs(v6, root / "runs", "v6")
    common = v6["v6_common"]
    refs = root / "runs/references.jsonl"
    private = root / "judge"
    private.mkdir()
    (private / "references.jsonl").write_bytes(refs.read_bytes())
    plans, records, data = {}, {}, {}
    for metric in ("m1", "m2"):
        plan = judge.build_plan(
            runs,
            {} if metric == "m1" else judge._references(refs),
            retest=15,
            references_sha256=common.sha(refs),
            withheld=metric == "m1",
        )
        plans[metric] = plan
        folder = private / metric
        common.write(folder / "plan.json", plan)
        assert judge.run_plan(plan, folder, synthetic_sender) == 115
        records[metric] = common.final.frozen("export").export(
            folder, common.plan_name("wixqa", metric), root / "public", runs, refs
        )
        data[metric] = common.unique(
            common.rows(root / "public" / (common.plan_name("wixqa", metric) + ".cases.jsonl"))
        )
    pin = {"plans": {m: common.sha(private / m / "plan.json") for m in plans}}
    measured = {c: {"v6_prompt_sha256": r["prompt_sha256"]} for c, r in data["m1"].items()}
    return SimpleNamespace(
        root=root,
        private=private,
        plans=plans,
        records=records,
        data=data,
        pin=pin,
        measured=measured,
    )


def test_real_frozen_judge_plan_and_export_contract(v6, planned):
    for metric in ("m1", "m2"):
        assert v6["v6_judge"].counts(planned.plans[metric], metric) == 115
        assert planned.plans[metric]["prompt_id"] == "QA_PROMPT_V5"
        v6["v6_judge"].export_gate(
            "wixqa",
            metric,
            planned.private,
            planned.pin,
            planned.records[metric],
            planned.data[metric],
            planned.measured,
        )


@pytest.mark.parametrize(
    "fault",
    ["status", "retest", "provenance", "grade", "cluster", "prompt", "missing", "m2", "empty"],
)
def test_public_export_cannot_change_frozen_measurement(v6, planned, fault):
    record, data = copy.deepcopy(planned.records["m2"]), copy.deepcopy(planned.data["m2"])
    row = data["case-000"]
    if fault == "status":
        record["status"] = "NOT_EVIDENCE"
    if fault == "retest":
        record["retest"]["agree"] -= 1
    if fault == "provenance":
        record["provenance"]["verdicts_sha256"] = "0" * 64
    if fault == "grade":
        row["grade"] = "bad"
    if fault == "cluster":
        row["cluster"] = "another"
    if fault == "prompt":
        row["prompt_sha256"] = "0" * 64
    if fault == "missing":
        record["missing"] = ["case-000"]
    if fault == "m2":
        row["m2"] = "disagrees"
    if fault == "empty":
        row["empty_answer"] = True
    with pytest.raises(SystemExit):
        v6["v6_judge"].export_gate(
            "wixqa", "m2", planned.private, planned.pin, record, data, planned.measured
        )


def test_chain_original_stands_sources_and_clean_environment(v6, tmp_path):
    common, chain = v6["v6_common"], v6["v6_chain"]
    assert common.KEYS == ("wixqa", "conditionalqa", "aircargo")
    for key in common.KEYS:
        stand, env, argv = chain.command(key, tmp_path, tmp_path / "spec", True)
        assert str(stand).replace("\\", "/").endswith(common.STANDS[key])
        assert env["V6_PRODUCT_ROOT"] == str(stand)
        assert "check" in argv and argv[argv.index("--runs") + 1] == common.SOURCE_RUNS[key]
        assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
    assert common.SOURCE_RUNS["aircargo"] == "/Users/julia/RAG_new_chat_138f3b3/final-answers"


@pytest.mark.parametrize("fault", [None, "draft", "missing", "changed", "judge"])
def test_registration_bytes_before_any_call(v6, tmp_path, fault):
    common = v6["v6_common"]
    paths = [*common.FROZEN, "tests/test_answer_prompt_v6.py"]
    paths += ["reports/answer-prompt-v6/tools/" + p.name for p in TOOLS.iterdir() if p.is_file()]
    held = {p: common.sha(ROOT / p) for p in paths}
    if fault == "missing":
        held.pop(common.FROZEN[0])
    if fault == "changed":
        held[paths[-1]] = "0" * 64
    if fault == "judge":
        held[common.FROZEN[0]] = "0" * 64
    status = (
        "draft — to be cold-read and registered"
        if fault == "draft"
        else "registered before V6's first request"
    )
    spec = tmp_path / "registered.md"
    spec.write_bytes(
        (f"Status: **{status}**\n" + "".join(f"- `{p}` `{h}`\n" for p, h in held.items())).encode()
    )
    if fault:
        with pytest.raises(SystemExit):
            common.registration(spec)
    else:
        assert common.registration(spec) == common.sha(spec)


@pytest.mark.parametrize(
    "fault", [None, "flags", "missing_fallback", "shown", "clock", "ceiling", "release", "units"]
)
def test_raw_shown_binding_and_fallback_times(v6, tmp_path, fault):
    common = v6["v6_common"]
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/001-stream.txt.raw").write_bytes(b"<evidence>private</evidence>")
    fallback = tmp_path / "raw/001-stream.txt.fallback"
    fallback.write_bytes(b" package ")
    entry = {"prompt_file": "001-stream.txt", "question": "Synthetic?", "answer": "package"}
    row = {
        "flags": ["parse"],
        "fallback": True,
        "shown_sha256": common.digest("package"),
        "v6_stream_sec": 2,
        "fallback_stream_sec": 3,
        "total_sec": 5,
        "package_stream_sec": 1,
    }
    synthetic_timeline(v6, tmp_path, entry, row)
    if fault in ("release", "units"):
        path = tmp_path / "raw/001-stream.txt.timeline.json"
        trace = common.read(path)
        trace["fallback"]["first_shown_sec" if fault == "release" else "unit_seconds"] = (
            1 if fault == "release" else [1]
        )
        common.write(path, trace)
    if fault == "flags":
        row["flags"] = ["language"]
    if fault == "missing_fallback":
        fallback.unlink()
    if fault == "shown":
        entry["answer"] = "another"
    if fault == "clock":
        row["total_sec"] = 6
    if fault == "ceiling":
        row["fallback_stream_sec"] = 3601
    if fault:
        with pytest.raises(SystemExit):
            v6["v6_judge"].shown_gate(tmp_path, entry, row)
    else:
        v6["v6_judge"].shown_gate(tmp_path, entry, row)


def test_source_bridge_retains_only_fifteen_admitted_originals(v6, planned, tmp_path):
    common, module = v6["v6_common"], v6["v6_judge"]
    old = {
        "provenance": {
            name + "_sha256": common.sha(planned.private / "m1" / (name + ext))
            for name, ext in (("plan", ".json"), ("verdicts", ".jsonl"))
        }
    }
    source = module.source_gate(planned.private / "m1", old)
    bridge = tmp_path / "bridge"
    common.load("reports/answer-prompt-v4/tools/bridge_plan.py", "v6_test_bridge").main(
        [str(planned.private / "m1"), str(bridge)]
    )
    plan = common.read(bridge / "plan.json")
    assert len(plan["items"]) == 30 and module.counts(plan, "bridge") == 15
    seed = common.protocol.prefix(bridge / "verdicts.jsonl")
    common.protocol.seed_gate(bridge / "verdicts.jsonl", seed)
    from scripts import chat_answer_judge as judge

    assert judge.run_plan(plan, bridge, synthetic_sender) == 15
    common.protocol.seed_gate(bridge / "verdicts.jsonl", seed)
    assert len(common.rows(bridge / "verdicts.jsonl")) == 30
    old["provenance"]["plan_sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="source hashes"):
        module.source_gate(planned.private / "m1", old)
    pin = {"plans": {"bridge": common.sha(bridge / "plan.json")}, "source": source}
    legacy = common.load("reports/stage4-final/tools/judge.py", "v6_test_legacy_judge")
    record = legacy.bridge_export(bridge, {"inputs": {"v4": source}}, tmp_path / "bridge.json")
    module.export_gate("wixqa", "bridge", tmp_path, pin, record)
    with (bridge / "verdicts.jsonl").open("r+b") as stream:
        stream.write(b" ")
    with pytest.raises(SystemExit):
        common.protocol.seed_gate(bridge / "verdicts.jsonl", seed)


@pytest.mark.parametrize("fault", ["salt", "route", "message", "retests", "cases"])
def test_plan_refuses_changed_request_or_count(v6, planned, fault):
    plan = copy.deepcopy(planned.plans["m1"])
    if fault == "salt":
        plan["salt"] = "different"
    if fault == "route":
        plan["route"]["effort"] = "high"
    if fault == "message":
        plan["items"][0]["message"] += "changed"
    if fault == "retests":
        plan["items"].pop()
    if fault == "cases":
        plan["items"][0]["case_id"] = plan["items"][1]["case_id"]
    with pytest.raises((ValueError, SystemExit)):
        v6["v6_judge"].counts(plan, "m1")


def test_missing_and_unstable_readings_cannot_pass(v6):
    counted = v6["v6_record"].counted
    good = {"status": "counted", "retest": {"passed": True}, "missing": []}
    data = {"case": {"grade": "good"}}
    assert counted(good, data)
    assert not counted({**good, "status": "NOT_EVIDENCE"}, data)
    assert not counted({**good, "retest": {"passed": False}}, data)
    assert not counted({**good, "missing": ["case"]}, data)
    assert not counted(good, {"case": {"grade": None}})


def test_reader_pairs_contexts_clusters_and_m2(v6):
    reader = v6["v6_record"]
    before = {
        f"case-{i}": {
            "grade": "bad",
            "cluster": "one",
            "stratum": "answerable",
            "context_has_answer": True,
            "claims_total": 1,
            "claims_supported": 0,
            "answers_question": "full",
            "defect": "other",
        }
        for i in range(20)
    }
    after = {
        c: {**r, "grade": "good", "claims_supported": 1, "defect": "none"}
        for c, r in before.items()
    }
    measured = {
        c: {
            "same_context": i < 10,
            "package_quoted": False,
            "v6_quoted": True,
            "package_chunks": 5,
            "chunks": 10,
            "package_stream_sec": 1,
            "v6_stream_sec": 2,
            "flags": ["repeat"] if i == 0 else (["parse"] if i >= 10 else []),
            "fallback": i >= 10,
            "fallback_chunks": 2 if i >= 10 else None,
            "answer_chars": 20,
            "package_answer_chars": 10,
            "first_shown_sec": 2 if i < 10 else 4,
            "package_first_sec": 0.1,
            "fallback_stream_sec": 3 if i >= 10 else None,
            "total_sec": 5 if i >= 10 else 2,
            "full_buffer_sec": 4 if i >= 10 else 2,
            "idle_clean": i < 10,
            "prefix_whole_disagreement": i == 0,
        }
        for i, c in enumerate(before)
    }
    numbers, pairs, same, families = reader.compare("wixqa", before, after, measured)
    assert len(pairs) == 20 and len(same) == 10
    assert numbers["bad"]["direction"] == "falls" and numbers["guards"]["repeat"] == 1
    assert numbers["timing"]["all_batches"]["first_shown_sec"]["median"] == 3
    assert numbers["timing"]["clean_batches"]["first_shown_sec"]["median"] == 2
    assert numbers["full_buffer_sec"]["median"] == 3
    assert numbers["timing"]["all_batches"]["full_buffer_sec"]["median"] == 3
    assert numbers["timing"]["clean_batches"]["full_buffer_sec"]["median"] == 2
    assert numbers["prefix_whole_disagreements"] == 1
    assert set(sum(families.values(), [])) == {"wixqa:cluster:one"}
    air = reader.compare("aircargo", before, after, measured)[3]
    assert len(set(sum(air.values(), []))) == 20
    old_m2 = {
        c: {"has_reference": i < 18, "m2": "agrees" if i < 18 else "right"}
        for i, c in enumerate(before)
    }
    m2, ids = reader.v5_record.m2("wixqa", old_m2, old_m2, families)
    assert len(ids) == 18 and m2["without_reference"]["right"] == {"v4": 2, "v5": 2}
    after["case-0"]["cluster"] = "other"
    with pytest.raises(SystemExit):
        reader.compare("wixqa", before, after, measured)


def test_public_records_reject_known_text(v6, tmp_path):
    with pytest.raises((ValueError, SystemExit)):
        v6["v6_common"].public(
            tmp_path / "record.json",
            {"answer": "secret synthetic question"},
            questions=["secret synthetic question"],
        )


def test_receipt_commit_gate_and_all_frozen_inputs(
    v6, planned, tmp_path, monkeypatch, registered_unicode
):
    """Fake only Git's committed-file boundary; use actual plans, hashes and bridge seed."""
    import shutil

    common, module = v6["v6_common"], v6["v6_judge"]
    private = tmp_path / "judge"
    shutil.copytree(planned.private, private)
    common.load("reports/answer-prompt-v4/tools/bridge_plan.py", "v6_receipt_bridge").main(
        [str(planned.private / "m1"), str(private / "bridge")]
    )
    paths = [*common.FROZEN, "tests/test_answer_prompt_v6.py"]
    paths += ["reports/answer-prompt-v6/tools/" + p.name for p in TOOLS.iterdir() if p.is_file()]
    spec = tmp_path / "spec.md"
    spec.write_bytes(
        (
            "Status: **registered before V6's first request**\n"
            + "".join(f"- `{p}` `{common.sha(ROOT / p)}`\n" for p in paths)
        ).encode()
    )
    pin = {
        "key": "wixqa",
        "regex_version": __import__("regex").__version__,
        "unidata_version": __import__("unicodedata").unidata_version,
        "replay_versions": {
            "regex_version": __import__("regex").__version__,
            "unidata_version": __import__("unicodedata").unidata_version,
        },
        "spec": common.SPEC,
        "spec_sha256": common.sha(spec),
        "tools": common.tool_hashes(),
        "plans": {m: common.sha(private / m / "plan.json") for m in ("m1", "m2", "bridge")},
        "requests": {"m1": 115, "m2": 115, "bridge": 15},
        "bridge_seed": common.protocol.prefix(private / "bridge/verdicts.jsonl"),
        "references_sha256": common.sha(private / "references.jsonl"),
        "old": {},
    }
    # Historical export admission is separately exercised below; this unit isolates receipt bytes.
    receipt = tmp_path / "receipt.json"
    common.write(receipt, pin)
    committed = {spec: spec.read_bytes()}

    def git_boundary(path):
        common.require(
            committed.get(Path(path)) == Path(path).read_bytes(),
            "public input is not committed unchanged",
        )

    monkeypatch.setattr(common.protocol, "committed", git_boundary)
    with pytest.raises(SystemExit, match="not committed"):
        module.admitted("wixqa", private, receipt, spec)
    committed[receipt] = receipt.read_bytes()
    assert module.admitted("wixqa", private, receipt, spec) == pin
    for target in (
        private / "m1/plan.json",
        private / "m2/plan.json",
        private / "references.jsonl",
        private / "bridge/verdicts.jsonl",
    ):
        original = target.read_bytes()
        target.write_bytes(b" " + original)
        with pytest.raises(SystemExit):
            module.admitted("wixqa", private, receipt, spec)
        target.write_bytes(original)
    common.write(receipt, {**pin, "key": "aircargo"})
    with pytest.raises(SystemExit, match="not committed"):
        module.admitted("wixqa", private, receipt, spec)
    committed[receipt] = receipt.read_bytes()
    with pytest.raises(SystemExit, match="key/spec"):
        module.admitted("wixqa", private, receipt, spec)


def test_old_export_refuses_wrong_prompt_route_stand_and_references(
    v6, planned, tmp_path, monkeypatch
):
    common, module = v6["v6_common"], v6["v6_judge"]
    record = copy.deepcopy(planned.records["m1"])
    record["provenance"]["prompt_id"] = "QA_PROMPT_V4"
    path = tmp_path / "old.json"
    common.public_rows(path.with_suffix(".cases.jsonl"), list(planned.data["m1"].values()))
    monkeypatch.setattr(common.protocol, "committed", lambda p: common.sha(p))
    common.write(path, record)
    assert len(module.old_export(path, "wixqa", "m1")[1]) == 100
    for field, value in (
        ("prompt_id", "QA_PROMPT_V5"),
        ("salt", "other"),
        ("references_withheld", False),
        ("adapter_sha256", "0" * 64),
        ("runs", {"toy": {"code_sha": "other"}}),
    ):
        changed = copy.deepcopy(record)
        changed["provenance"][field] = value
        common.write(path, changed)
        with pytest.raises(SystemExit):
            module.old_export(path, "wixqa", "m1")


def test_forecast_includes_fresh_fallbacks_and_ten_preloads(v6):
    import math

    v5_medians = (103.4, 100.5, 104.0)
    package_proxy = (85.3, 76.5, 85.7)
    expected = {
        key: 900 * math.ceil((100 * old + 10 * fallback + 10 * 120) / 900)
        for key, old, fallback in zip(v6["v6_common"].KEYS, v5_medians, package_proxy, strict=True)
    }
    assert v6["v6_common"].FORECAST == expected


@pytest.mark.parametrize("freeze_fault", [None, "bridge", "receipt", "rename"])
def test_synthetic_freeze_grade_export_and_early_read(
    v6, package, tmp_path, monkeypatch, freeze_fault, registered_unicode
):
    """Whole one-key path; only the model sender and Git boundary are synthetic."""
    from scripts import chat_answer_judge as judge

    common, module, reader = v6["v6_common"], v6["v6_judge"], v6["v6_record"]
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(reader, "ROOT", tmp_path)
    monkeypatch.setattr(common.protocol, "committed", lambda p: common.sha(p))
    refs = package[0] / "references.jsonl"
    old_public = tmp_path / "old-public"
    config = {"references": str(refs), "source": str(tmp_path / "old-judge/m1")}
    export = common.final.frozen("export")
    for metric in ("m1", "m2"):
        plan = judge.build_plan(
            package[1],
            {} if metric == "m1" else judge._references(refs),
            retest=15,
            references_sha256=common.sha(refs),
            withheld=metric == "m1",
        )
        folder = tmp_path / "old-judge" / metric
        common.write(folder / "plan.json", plan)
        assert judge.run_plan(plan, folder, synthetic_sender) == 115
        export.export(folder, "package-" + metric, old_public, package[1], refs)
        # Model the newly required committed LF input, without changing the frozen exporter.
        for suffix in (".json", ".cases.jsonl"):
            path = old_public / ("package-" + metric + suffix)
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        config["old_" + metric] = str(old_public / ("package-" + metric + ".json"))
    paths = [*common.FROZEN, "tests/test_answer_prompt_v6.py"]
    paths += ["reports/answer-prompt-v6/tools/" + p.name for p in TOOLS.iterdir() if p.is_file()]
    spec = tmp_path / "spec.md"
    spec.write_bytes(
        (
            "Status: **registered before V6's first request**\n"
            + "".join(f"- `{p}` `{common.sha(ROOT / p)}`\n" for p in paths)
        ).encode()
    )
    private = tmp_path / "private"
    runs = private / "wixqa/runs"
    new_runs = synthetic_runs(v6, runs, "v6")
    old_entries = {
        e["case_id"]: e for folder in package[1].values() for e in judge.run_answers(folder)
    }
    measured, parity = [], []
    for batch, folder in enumerate(new_runs.values(), 1):
        (folder / "raw").mkdir()
        for entry in judge.run_answers(folder):
            raw = "<evidence>hidden</evidence><answer>" + entry["answer"] + "</answer>"
            (folder / "raw" / (entry["prompt_file"] + ".raw")).write_bytes(raw.encode())
            row = {
                "case_id": entry["case_id"],
                "batch": batch,
                "parity": True,
                "same_context": True,
                "documents_package": 1,
                "documents_v6": 1,
                "package_prompt_sha256": old_entries[entry["case_id"]]["prompt_sha256"],
                "v6_prompt_sha256": entry["prompt_sha256"],
            }
            parity.append(row.copy())
            row.update(
                flags=[],
                fallback=False,
                shown_sha256=common.digest(entry["answer"]),
                v6_stream_sec=2,
                fallback_stream_sec=None,
                total_sec=2,
                package_stream_sec=1,
                package_chunks=5,
                chunks=5,
                package_quoted=False,
                v6_quoted=False,
                fallback_chunks=None,
                answer_chars=len(entry["answer"]),
                package_answer_chars=len(entry["answer"]),
                first_shown_sec=2,
                package_first_sec=0.1,
            )
            synthetic_timeline(v6, folder, entry, row)
            measured.append(row)
    summary = {
        "key": "wixqa",
        "whole": True,
        "code_sha": "2057ad0" + "0" * 33,
        "spec_sha256": common.sha(spec),
        "tools": common.tool_hashes(),
        "prompt_template_sha256": common.sha(TOOLS / "qa_prompt_v6.txt"),
        "regex_version": __import__("regex").__version__,
        "unidata_version": __import__("unicodedata").unidata_version,
        "idle": [{"batch": n, "busy": False, "readings": []} for n in range(1, 11)],
        "environment_before": {},
        "environment_after": {},
        "started": "2026-01-01",
        "finished": "2026-01-02",
        "rows": measured,
        "parity": parity,
    }
    common.write(runs / "v6-wixqa.json", summary)
    common.write(runs / "COMPLETE", {"summary_sha256": common.sha(runs / "v6-wixqa.json")})
    records = tmp_path / "reports/answer-prompt-v6"
    public = records / "2057ad0"
    common.write(public / "v6-wixqa.json", summary)
    receipt, work = public / "plans-wixqa.json", private / "wixqa/judge"
    if freeze_fault:
        with monkeypatch.context() as patch:

            def fail(*args, **kwargs):
                common.require(False, "synthetic mid-freeze refusal")

            if freeze_fault == "bridge":
                patch.setattr(module, "load", lambda *a: SimpleNamespace(main=fail))
            elif freeze_fault == "rename":
                patch.setattr(Path, "rename", fail)
            else:
                original_public = module.public

                def interrupted_public(path, *args, **kwargs):
                    original_public(path, *args, **kwargs)
                    fail()

                patch.setattr(module, "public", interrupted_public)
            with pytest.raises(SystemExit, match="mid-freeze"):
                module.freeze("wixqa", config, runs, work, receipt, spec)
        assert not work.exists() and work.with_name(work.name + ".partial").exists()
    pin = module.freeze("wixqa", config, runs, work, receipt, spec)
    assert not work.with_name(work.name + ".partial").exists()
    assert pin["replay_versions"] == {k: pin[k] for k in ("regex_version", "unidata_version")}
    assert pin["requests"] == {"m1": 115, "m2": 115, "bridge": 15}
    assert module.admitted("wixqa", work, receipt, spec) == pin
    for metric in ("m1", "bridge", "m2"):
        assert (
            judge.run_plan(
                common.read(work / metric / "plan.json"), work / metric, synthetic_sender
            )
            == pin["requests"][metric]
        )
        module.export_one("wixqa", metric, work, runs, pin, public)
        if metric == "bridge":
            early = reader.build(private, records, spec, ["wixqa"])
            assert early["primary"]["n"] == 100
            assert early["decision"]["decision"] == "NOT_EVIDENCE"
            assert "m2" not in early["corpora"]["wixqa"]
    reading = reader.build(private, records, spec, ["wixqa"])
    assert reading["decision"]["decision"] == "NOT_EVIDENCE"
    assert reading["primary"]["n"] == 100 and reading["same_context"]["n"] == 100
    assert reading["corpora"]["wixqa"]["guards"] == {
        "parse": 0,
        "repeat": 0,
        "language": 0,
        "language_after_release": 0,
    }
    assert all(b"\r" not in p.read_bytes() for p in public.iterdir() if p.is_file())


def synthetic_timeline(v6, folder, entry, row):
    """One-chunk synthetic stream with real display-derived receipt fields."""
    prefix = folder / "raw" / entry["prompt_file"]
    traces = {}
    for kind, suffix, seconds in (
        ("v6", ".raw", row["v6_stream_sec"]),
        ("fallback", ".fallback", row["fallback_stream_sec"]),
    ):
        if seconds is None:
            traces[kind] = None
            continue
        raw = Path(str(prefix) + suffix).read_text("utf-8")
        policy = v6["shown_text"].shown_text(raw, entry["question"], finished=False, details=True)
        trace = {
            "chunks": [{"chars": len(raw), "sec": seconds}],
            "end_sec": seconds,
            "end_state": (
                ("policy" if policy["flags"] else "answer_tag")
                if kind == "v6" and policy["stop"]
                else "eos"
            ),
        }
        got = v6["v6_replay"].stream_reading(raw, entry["question"], trace, kind == "v6")
        trace.update({k: got[k] for k in ("answer_open_sec", "unit_seconds", "first_shown_sec")})
        if kind == "v6":
            row.update(
                {k: got[k] for k in ("full_buffer_sec", "cut_at", "prefix_whole_disagreement")}
            )
            row["first_shown_sec"] = got["first_shown_sec"]
        else:
            row["first_shown_sec"] = row["v6_stream_sec"] + got["first_shown_sec"]
            row["full_buffer_sec"] = row["first_shown_sec"]
        traces[kind] = trace
    row.update(chunks=1, fallback_chunks=1 if traces["fallback"] else None, idle_clean=True)
    v6["v6_common"].write(Path(str(prefix) + ".timeline.json"), traces)


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("complete", 0),
        ("budget", 3),
        ("commit", 4),
        ("unavailable", 3),
        ("resume_unavailable", 5),
        ("resume_flag_budget", 3),
        ("m2_resume", 3),
        ("cross_stand_harm", 2),
        ("touch_failure", 6),
        ("grade_refusal", 1),
        ("foreign_exception", 1),
        ("stop", 2),
        ("harm", 2),
        ("refusal", 1),
        ("retry_reset", 0),
        ("kill", 0),
        ("partial_export", 0),
    ],
)
def test_key_driver_exits_and_retry(v6, package, tmp_path, monkeypatch, scenario, code):
    from scripts import chat_answer_judge as judge

    driver = v6["v6_key"]
    common, grading, reader = v6["v6_common"], v6["v6_judge"], v6["v6_record"]
    args = SimpleNamespace(
        key="wixqa",
        private=tmp_path / "private",
        records=tmp_path / "records",
        runs=tmp_path / "runs",
        spec=tmp_path / "spec",
        config=tmp_path / "config",
        mac_stop=str(tmp_path / "STOP"),
        budget=1 if scenario == "budget" else 840,
    )
    receipt = args.records / "2057ad0/plans-wixqa.json"
    pin = {"plans": {}, "requests": dict.fromkeys(("m1", "bridge", "m2"), 2)}
    work = args.private / "wixqa/judge"
    for metric in pin["requests"]:
        plan = judge.build_plan(package[1], {}, retest=0)
        plan["items"] = plan["items"][:2]
        common.write(work / metric / "plan.json", plan)
        pin["plans"][metric] = common.sha(work / metric / "plan.json")
    common.write(receipt, pin)
    common.write(receipt.parent / "v6-wixqa.json", {})
    monkeypatch.setattr(grading, "admitted", lambda *a: pin)
    monkeypatch.setattr(
        common.protocol, "committed", lambda p: common.require(scenario != "commit", "uncommitted")
    )

    def export(key, metric, private, runs, held, out):
        path = out / (common.plan_name(key, metric) + ".json")
        common.write(path, {})
        if metric != "bridge":
            common.write(path.with_suffix(".cases.jsonl"), {})

    monkeypatch.setattr(grading, "export_one", export)
    if scenario == "partial_export":
        common.write(receipt.parent / "v6-wixqa-judge-m1.json", {})
    reads = []

    def reading(*a):
        reads.append((work / "m2/verdicts.jsonl").exists())
        return {"decision": {"harm": ["synthetic"] if scenario == "harm" else []}}

    monkeypatch.setattr(reader, "build", reading)
    ticks, calls, sleeps = [0], [], []
    monkeypatch.setattr(driver.time, "time", lambda: ticks[0])

    def sleep(seconds):
        sleeps.append(seconds)
        ticks[0] += seconds

    def sender(system, message):
        calls.append(message)
        ticks[0] += 2
        if scenario in ("unavailable", "resume_unavailable", "resume_flag_budget") or (
            scenario == "retry_reset" and len(calls) in (1, 3)
        ):
            from evaluation.blinded_judge_clients import JudgeUnavailable

            raise JudgeUnavailable("synthetic", "never print me")
        return synthetic_sender(system, message)

    if scenario == "kill":
        # Kill after a journaled success, before the driver's retry-state write.
        grading.grade_one(work, "m1", pin, limit=1, sender=sender)
        common.write(
            work / "m1/retry.json", {"consecutive_failures": 6, "journal_rows": 0, "retry_at": 0}
        )
    if scenario == "stop":
        common.write(work / "m1/NOT_EVIDENCE.json", {})
    if scenario == "refusal":
        monkeypatch.setattr(grading, "admitted", lambda *a: common.require(False, "refused"))
    if scenario == "resume_unavailable":
        args.budget = 10000
    if scenario == "resume_flag_budget":
        args.resume_unavailable = True
    if scenario == "cross_stand_harm":
        args.key = "aircargo"
        common.write(args.records / "138f3b3/plans-aircargo.json", pin)
        common.write(args.records / "138f3b3/v6-aircargo.json", {})
        common.write(
            receipt.parent / "reading-wixqa-after-bridge.json",
            {"decision": {"harm": ["synthetic"]}},
        )
    if scenario == "touch_failure":
        common.write(work / "m1/NOT_EVIDENCE.json", {})
        monkeypatch.setattr(
            driver, "touch_stop", lambda target: common.require(False, "cannot touch")
        )
    if scenario in ("grade_refusal", "foreign_exception"):

        def fail_grade(*args, **kwargs):
            if scenario == "grade_refusal":
                common.require(False, "synthetic gate " + "x" * 250)
            raise ValueError("synthetic private message; never print")

        monkeypatch.setattr(grading, "grade_one", fail_grade)
    if scenario == "m2_resume":
        for metric in ("m1", "bridge"):
            while driver.pending(work / metric):
                grading.grade_one(work, metric, pin, limit=1, sender=synthetic_sender)
        args.budget = 1
    code_got, status = driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)
    assert code_got == code
    assert Path(args.mac_stop).exists() is (scenario in ("stop", "harm", "cross_stand_harm"))
    if scenario == "unavailable":
        assert len(calls) == 3 and sleeps == [300, 300]
        held = common.read(work / "m1/retry.json")
        assert held == {"consecutive_failures": 3, "journal_rows": 3, "retry_at": ticks[0] + 300}
        ticks[0] = held["retry_at"] + 1
        args.budget = 1
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 3
        assert len(calls) == 4 and sleeps == [300, 300]
        assert common.read(work / "m1/retry.json")["consecutive_failures"] == 4
    if scenario == "resume_unavailable":
        assert len(calls) == 7
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 5
        assert len(calls) == 7
        args.resume_unavailable = True
        assert (
            driver.execute(args, sender=synthetic_sender, clock=lambda: ticks[0], sleep=sleep)[0]
            == 0
        )
        assert common.read(work / "m1/retry.json")["consecutive_failures"] == 0
    if scenario == "resume_flag_budget":
        held = common.read(work / "m1/retry.json")
        assert held["consecutive_failures"] == 3 and len(calls) == 3
        # Leaving the flag on preserves both the count and pending backoff below seven.
        args.budget = 300
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 3
        assert common.read(work / "m1/retry.json") == held and len(calls) == 3
        args.budget = 10000
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 5
        assert common.read(work / "m1/retry.json")["consecutive_failures"] == 7
        assert len(calls) == 7
    if scenario == "m2_resume":
        assert reads == [False]
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 3
        assert reads == [False]  # No second bridge build before the next M2 grade.
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 0
        assert reads == [False, True]
    if scenario == "touch_failure":
        assert "stop detected, Mac STOP not written" in status and args.mac_stop in status
    if scenario in ("grade_refusal", "foreign_exception"):
        assert not calls and not sleeps and not (work / "m1/retry.json").exists()
        log = args.private / "wixqa/driver.log"
        assert str(log) in status and "Traceback" in log.read_text("utf-8")
        assert re.search(r"^\d{4}-\d\d-\d\dT.*\+00:00$", log.read_text("utf-8"), re.M)
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 1
        assert log.read_text("utf-8").count("Traceback (most recent call last)") == 2
        if scenario == "grade_refusal":
            assert ("NOT_EVIDENCE: synthetic gate " + "x" * 250)[:200] in status
            assert "x" * 201 not in status
        else:
            assert "ValueError" in status and "synthetic private message" not in status
            assert "synthetic private message" in log.read_text("utf-8")
    if scenario == "complete":
        assert reads == [False, True]
        assert len(calls) == 6
    if scenario == "partial_export":
        assert (receipt.parent / "v6-wixqa-judge-m1.cases.jsonl").exists()
    if scenario in ("retry_reset", "kill"):
        assert common.read(work / "m1/retry.json")["consecutive_failures"] == 0
        assert len(calls) == (8 if scenario == "retry_reset" else 6)
    if scenario == "budget":
        args.budget = 840
        assert driver.execute(args, sender=sender, clock=lambda: ticks[0], sleep=sleep)[0] == 0
        assert len(calls) == 6  # The first journaled verdict is never resent.


@pytest.mark.parametrize("latin", [61, 65, 89, 90, 100])
def test_c1_prefix_stop_requires_ninety_percent(v6, latin):
    show = v6["shown_text"].shown_text
    question = "я" * 12
    prefix = "<answer>" + "a" * latin + " " + "я" * (100 - latin) + ". "
    early = show(prefix, question, finished=False, details=True)
    if latin >= 90:
        assert early["stop"] and early["flags"] == ["language"]
    else:
        assert early["text"] == "" and not early["stop"] and not early["flags"]
        final = show(prefix + "я" * 200, question, details=True)
        assert final["text"] == prefix[8:].strip() + " " + "я" * 200
        assert not final["flags"] and not final["prefix_whole_disagreement"]
    release = show("<answer>" + "я" * 24 + " " + "a" * 16 + ". ", question, finished=False)
    assert release["text"] and release["flags"] == []


@pytest.mark.parametrize("tag", ["<answer>", "</answer>", "<evidence>", "</evidence>"])
def test_c15_finished_partial_template_tag_is_hidden(v6, tag):
    for end in range(1, len(tag)):
        assert v6["shown_text"].shown_text("<answer>Shown. " + tag[:end].upper(), "?") == {
            "text": "Shown.",
            "flags": [],
        }
    assert v6["shown_text"].shown_text("<answer>Shown. <custom", "?")["text"] == "Shown. <custom"


def test_11e_f2_partial_close_after_bare_less_than(v6):
    assert v6["shown_text"].shown_text("<answer>Keep 1 < 2 here. Tail </ans", "?") == {
        "text": "Keep 1 < 2 here. Tail",
        "flags": [],
    }


@pytest.mark.parametrize(
    "body,question",
    [
        ("<answer>" + "a" * 40 + ". Next unit.</answer>", "a" * 12),
        ("<answer>unfinished tail</ans", "?"),
        ("<answer>" + "a" * 40 + ". never shown", "я" * 12),
        ("<answer>" + "a" * 40 + ". " + "я" * 100 + ". never shown", "a" * 12),
        ("<answer>one two three four. one two three four. never shown", "?"),
        ("<answer>one two three four.\none two three four [1,\n2] never shown</answer>", "?"),
    ],
)
def test_c2_chunk_gate_matches_every_chunk(v6, monkeypatch, body, question):
    replay = v6["v6_replay"]
    original = replay.shown_text
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    class Model:
        async def generate_stream(self, *args, **kwargs):
            for char in body:
                yield char  # Splits ASCII lookahead and every template tag.

    monkeypatch.setattr(replay, "shown_text", counted)
    ticks = [0]

    def clock():
        ticks[0] += 0.001
        return ticks[0]

    monkeypatch.setattr(replay.time, "monotonic", clock)
    gated = asyncio.run(replay.collect(Model(), "synthetic", {}, tagged=True, question=question))
    gated_calls = len(calls)
    calls.clear()
    ticks[0] = 0
    monkeypatch.setattr(
        replay,
        "policy_chunk",
        lambda raw, question, previous, result: counted(
            raw, question, finished=False, details=True
        ),
    )
    ungated = asyncio.run(replay.collect(Model(), "synthetic", {}, tagged=True, question=question))
    assert gated == ungated  # Includes stop chunk, all times, shown text and flags.
    assert gated_calls < len(calls)
    if "[1,\n2]" in body:
        assert gated["raw"].endswith("]")
        assert gated["display"]["flags"] == ["repeat"]


@pytest.mark.parametrize("private_kind", ["repository", "ancestor", "library"])
def test_11e_f5_invalid_private_path_has_no_log(v6, tmp_path, monkeypatch, private_kind):
    common, driver = v6["v6_common"], v6["v6_key"]
    repository = tmp_path / "repository"
    library = tmp_path / "library"
    monkeypatch.setattr(common, "ROOT", repository)
    monkeypatch.setattr(common, "LIBRARY", library)
    private = {
        "repository": repository / "private",
        "ancestor": tmp_path,
        "library": library / "private",
    }[private_kind]
    args = SimpleNamespace(private=private, runs=tmp_path / "runs", budget=840, key="wixqa")
    code, status = driver.execute(args)
    assert code == 1
    assert "private folder must be outside repository/stand/library" in status
    assert not (private / args.key).exists()
    assert "log:" not in status and "driver.log" not in status


@pytest.mark.parametrize("mismatch", [None, "regex_version", "unidata_version"])
def test_11e_f6_registration_command_checks_versions(v6, monkeypatch, mismatch):
    versions = v6["v6_common"].REGISTERED_VERSIONS
    monkeypatch.setattr(
        __import__("regex"),
        "__version__",
        "different" if mismatch == "regex_version" else versions["regex_version"],
    )
    monkeypatch.setattr(
        __import__("unicodedata"),
        "unidata_version",
        "different" if mismatch == "unidata_version" else versions["unidata_version"],
    )
    spec = (ROOT / "docs/specs/answer-prompt-v6.md").read_text("utf-8")
    command = re.search(r"^Checked \$V6Py -c '(.*regex.*)'$", spec, re.M)[1].replace("''", "'")
    if mismatch:
        with pytest.raises(SystemExit) as exc:
            exec(command, {})
        assert exc.value.code != 0
    else:
        with pytest.raises(SystemExit) as exc:
            exec(command, {})
        assert exc.value.code == 0


@pytest.mark.parametrize("side", ["laptop", "replay", "both"])
@pytest.mark.parametrize("field", ["regex_version", "unidata_version"])
def test_c6_plan_refuses_either_unicode_mismatch(
    v6, monkeypatch, tmp_path, side, field, registered_unicode
):
    module = v6["v6_judge"]
    versions = {"regex_version": "2026.5.9", "unidata_version": "14.0.0"}
    if side in ("laptop", "both"):
        library, attr = (
            ("regex", "__version__")
            if field == "regex_version"
            else ("unicodedata", "unidata_version")
        )
        monkeypatch.setattr(__import__(library), attr, "different")
    if side in ("replay", "both"):
        versions[field] = "different"
    monkeypatch.setattr(module, "registration", lambda p: "synthetic")
    monkeypatch.setattr(module.protocol, "committed", lambda p: None)
    runs = tmp_path / "runs"
    module.write(runs / "v6-wixqa.json", versions)
    with pytest.raises(SystemExit, match=field):
        module.freeze(
            "wixqa",
            {"source": tmp_path / "source", "references": tmp_path / "refs"},
            runs,
            tmp_path / "private",
            tmp_path / "receipt",
            tmp_path / "spec",
        )
    assert not (tmp_path / "private").exists() and not (tmp_path / "receipt").exists()


@pytest.mark.parametrize(
    "module,field", [("regex", "__version__"), ("unicodedata", "unidata_version")]
)
def test_c6_chain_check_refuses_before_child(
    v6, monkeypatch, tmp_path, module, field, registered_unicode
):
    monkeypatch.setattr(__import__(module), field, "different")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "v6_chain.py",
            "--check",
            "--out",
            str(tmp_path / "out"),
            "--spec",
            str(tmp_path / "spec"),
        ],
    )
    monkeypatch.setattr(
        v6["v6_chain"].subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("started a child on version mismatch"),
    )
    with pytest.raises(SystemExit, match="differs from registration"):
        v6["v6_chain"].main()


def test_c10_remote_stop_has_bounded_noninteractive_ssh(v6, monkeypatch):
    calls = []
    monkeypatch.setattr(v6["v6_key"].subprocess, "run", lambda *a, **k: calls.append((a, k)))
    v6["v6_key"].touch_stop("synthetic-mac:/synthetic/STOP")
    assert calls == [
        (
            (
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=20",
                    "synthetic-mac",
                    "touch",
                    "/synthetic/STOP",
                ],
            ),
            {"check": True, "capture_output": True, "timeout": 60},
        )
    ]


def test_c14_fallback_full_buffer_includes_first_chunk(v6, monkeypatch):
    replay = v6["v6_replay"]
    ticks = [0]

    def clock():
        ticks[0] += 0.001
        return ticks[0]

    monkeypatch.setattr(replay.time, "monotonic", clock)

    class Model:
        async def generate_stream(self, messages, **kwargs):
            yield "missing tags" if messages[0]["content"] == "V6" else "package"

    got = asyncio.run(replay.answer(Model(), "V6", "PACKAGE", "?", {}))
    assert got["fallback"]
    expected = got["v6_stream_sec"] + got["timeline"]["fallback"]["first_shown_sec"]
    assert got["full_buffer_sec"] == got["first_shown_sec"] == expected
    assert got["full_buffer_sec"] > got["v6_stream_sec"]
