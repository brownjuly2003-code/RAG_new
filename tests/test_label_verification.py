"""Label verification of development-set drafts (docs/specs/label-verification.md).

No model and no network: the verifiers are fakes that see only request texts. Every fixture
is built in tmp_path; the one test on the real pilot is skipped without the corpus.

The rubric registers one verifier (plan decision D12). The rules for several verifiers stay
in the tool, so most tests here run them with a second voice that exists only in this file;
the tests that take `one_voice` run the registry as it is registered.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from evaluation import devset
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import (
    JudgeUnavailable,
    RateLimited,
    Reply,
    TransportError,
)
from evaluation.devset_sources import corpus_directory, normalized, read_sources, sections
from scripts import devset_label_verify as v

ROOT = Path(__file__).resolve().parent.parent
ALPHA, BETA, GAMMA, DELTA = (
    "01_alpha_policy.md",
    "02_beta_rules.md",
    "03_gamma_guide.md",
    "04_delta_reserve.md",
)
SECOND, OPUS = "second-voice", "claude-opus-5-5"
REGISTERED = (lv.VERIFIERS, lv.VERIFIERS_BY_AUTHOR_VENDOR)
TWO_VOICES: dict[str, lv.Verifier] = {
    SECOND: {"model": SECOND, "vendor": "Second vendor", "route": "test double", "settings": {}},
    OPUS: lv.VERIFIERS[OPUS],
}
REPAIRER = {"model": OPUS, "vendor": "Anthropic"}
SCOPE = "Internal corpus document. Owner must confirm currency and applicability."
BODIES = {
    ALPHA: (
        "Политика альфа",
        "alpha_policy",
        "Правило хранения",
        [
            "Альфа-журнал хранения ведётся на складе временного хранения и сверяется с накладной.",
            "Срок хранения альфа-журнала составляет пять лет с даты закрытия рейса, затем архив.",
            "Выдача копий описана в 02_beta_rules.md, перечень лежит в docs/internal/"
            "03_gamma_guide.md и в MANIFEST.md.",
            "Код beta_rules пишут в сопроводительном листе, а слово guide остаётся словом.",
        ],
    ),
    BETA: (
        "Правила бета",
        "beta_rules",
        "Порядок выдачи",
        [
            "Копии бета-накладной выдаются только при предъявлении доверенности и паспорта.",
            "Выдача копий бета-накладной регистрируется в журнале выдачи в день обращения.",
            "Отказ в выдаче копии оформляется письменно и передаётся получателю за три дня.",
        ],
    ),
    GAMMA: (
        "Справочник гамма",
        "guide",
        "Формы актов",
        [
            "Гамма-перечень содержит действующие формы актов приёма и передачи груза на терминале.",
            "Каждая форма гамма-перечня пересматривается владельцем процесса один раз в год.",
            "Устаревшие формы гамма-перечня изымаются в день утверждения новой редакции формы.",
        ],
    ),
    DELTA: (
        "Резерв дельта",
        "delta_reserve",
        "Досмотр груза",
        [
            "Дельта-резерв описывает порядок досмотра опасных грузов перед погрузкой на борт.",
            "Досмотр по дельта-резерву проводит сертифицированный специалист службы безопасности.",
            "Результат досмотра по дельта-резерву вносится в акт и хранится вместе с накладной.",
        ],
    ),
}


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def front(name: str) -> str:
    title, doc_id, _, _ = BODIES[name]
    lines = [
        "---",
        f"doc_id: {doc_id}",
        f"title: {title}",
        "document_type: политика",
        "source_type: internal_controlled",
        'version: "1.0"',
        "effective_date: 2026-05-15",
        "owner_role: Compliance Officer",
    ]
    if name != BETA:
        lines += ["related_normative_sources:", "  - 152-ФЗ", "  - см. 02_beta_rules.md"]
    return "\n".join([*lines, "classification: internal-secret", "---"])


def related(name: str) -> str:
    other = BETA if name != BETA else ALPHA
    return f"## Связанные документы\n\n- {other} — смежный документ\n- MANIFEST.md\n"


def source(name: str) -> str:
    title, _, heading, lines = BODIES[name]
    body = "\n".join(lines)
    return f"{front(name)}\n# {title}\n\n## {heading}\n\n{body}\n\n{related(name)}"


TEXTS = {name: source(name) for name in BODIES}
CORPUS: dict[str, Any] = {
    "corpus_sha256": sha("".join(TEXTS.values())),
    "file_count": len(TEXTS),
    "files": [
        {"name": name, "sha256": sha(text), "bytes": len(text)} for name, text in TEXTS.items()
    ],
}
REVISIONS = {entry["name"]: entry["sha256"] for entry in CORPUS["files"]}
REGISTER = {
    "families": [
        {"family_id": "family-a", "members": [{"source_id": ALPHA}]},
        {"family_id": "family-b", "members": [{"source_id": BETA}, {"source_id": GAMMA}]},
        {"family_id": "family-r", "members": [{"source_id": DELTA}]},
    ],
    "holdout_reserve_documents": [DELTA],
}


def rule(name: str) -> dict[str, Any]:
    """The address of the one rule section of a fixture document."""
    return next(s for s in sections(name, TEXTS[name]) if s["section_path"][-1] == BODIES[name][2])


def span(case_id: str, index: int, name: str) -> dict[str, Any]:
    section = rule(name)
    text = TEXTS[name][section["char_start"] : section["char_end"]]
    return {
        **section,
        "span_id": f"{case_id}-E{index}",
        "source_revision": REVISIONS[name],
        "corpus_version": CORPUS["corpus_sha256"],
        "text_sha256": sha(text),
        "normalized_text": normalized(text),
    }


def fact(name: str, line: int, text: str, subject: str) -> dict[str, Any]:
    return {
        "subject": subject,
        "text": text,
        "polarity": "allowed",
        "value": None,
        "unit": "",
        "condition": "",
        "tolerance": 0.0,
        "source_quote": BODIES[name][3][line],
    }


def case(
    case_id: str,
    question: str,
    answer: str,
    seed: str,
    partners: tuple[str, ...] = (),
    facts: tuple[dict[str, Any], ...] = (),
    **labels: Any,
) -> dict[str, Any]:
    """One draft that passes the per-case rules and the source checks of evaluation.devset."""
    documents = sorted({seed, *partners})
    spanned = [seed, *partners] if facts else []
    spans = [span(case_id, index, name) for index, name in enumerate(spanned, 1)]
    return {
        "case_id": case_id,
        "question": question,
        "reference_answer": answer,
        "primary_class": "single-doc" if len(documents) == 1 else "multi-doc",
        "question_origin": "agent_style_A",
        "label_origin": "agent_labelled",
        "evidence_class": "agent_labelled",
        "status": "agent_labelled",
        "approved_by": None,
        "seed_selected_source_section": rule(seed),
        "partner_sections": [
            {**rule(name), "selection_reason": "shares the rule"} for name in partners
        ],
        "documents": documents,
        "flags": {
            "ru_to_en": False,
            "numeric": False,
            "safety_critical": False,
            "adversarial_unanswerable": False,
        },
        "trap_type": None,
        "expected_action": "answer",
        "complexity": "simple",
        "as_of": "2026-10-01",
        "authority_source": [
            {"source_id": name, "source_revision": REVISIONS[name], "scope": SCOPE}
            for name in documents
        ],
        "wrong_answer_severity": "moderate",
        "evidence_spans": spans,
        "required_evidence_groups": [
            {"group_id": f"{case_id}-G{index}", "alternatives": [item["span_id"]]}
            for index, item in enumerate(spans, 1)
        ],
        "required_facts": list(facts),
        "critical_facts": [],
        "action_reason": None,
        "aggregation": None,
        **labels,
    }


ALPHA_FACT = fact(ALPHA, 0, "Альфа-журнал хранения ведётся на складе временного хранения", "журнал")
TERM_FACT = fact(ALPHA, 1, "Срок хранения альфа-журнала составляет пять лет", "срок хранения")
BETA_FACT = fact(
    BETA, 0, "Копии бета-накладной выдаются только при предъявлении доверенности", "копии"
)
REFUSAL_FACT = fact(BETA, 2, "Отказ в выдаче копии оформляется письменно", "отказ")
GAMMA_FACT = fact(
    GAMMA, 1, "Каждая форма гамма-перечня пересматривается владельцем процесса", "формы"
)
TRAP_FLAGS = {
    "ru_to_en": False,
    "numeric": False,
    "safety_critical": False,
    "adversarial_unanswerable": True,
}


def drafts_cases() -> list[dict[str, Any]]:
    return [
        case(
            "M-01",
            "Где ведётся альфа-журнал хранения?",
            "Альфа-журнал хранения ведётся на складе временного хранения.",
            ALPHA,
            facts=(ALPHA_FACT,),
        ),
        case(
            "M-02",
            "Правда ли, что копии бета-накладной выдают без доверенности, а журнал хранят год?",
            "Нет: копии бета-накладной выдаются только при предъявлении доверенности, "
            "а срок хранения альфа-журнала составляет пять лет.",
            BETA,
            (ALPHA,),
            (BETA_FACT, TERM_FACT),
            trap_type="false_premise",
            expected_action="correct_premise",
            action_reason="The premise contradicts the rule on copies.",
            flags=TRAP_FLAGS,
            wrong_answer_severity="high",
        ),
        case(
            "M-03",
            "Как страхуют хрупкий груз по гамма-перечню?",
            "Отказ: в документах нет правила о страховании хрупкого груза.",
            GAMMA,
            primary_class="needs-refusal/clarification",
            trap_type="out_of_corpus",
            expected_action="refuse",
            action_reason="The corpus holds no rule on insuring fragile cargo.",
            flags=TRAP_FLAGS,
        ),
        case(
            "M-04",
            "Как пересматривают формы гамма-перечня и как оформляют отказ в копии?",
            "Каждая форма гамма-перечня пересматривается владельцем процесса, "
            "а отказ в выдаче копии оформляется письменно.",
            GAMMA,
            (BETA,),
            (GAMMA_FACT, REFUSAL_FACT),
            critical_facts=[GAMMA_FACT],
            flags={**TRAP_FLAGS, "safety_critical": True, "adversarial_unanswerable": False},
            wrong_answer_severity="critical",
        ),
    ]


def header(name: str) -> str:
    title, _, heading, _ = BODIES[name]
    return f"[Контекст: Из документа {name}, раздел: {title} › {heading}]\n"


def chunk(name: str, text: str) -> dict[str, Any]:
    return {"page_content": header(name) + text, "metadata": {"source": name}}


CHUNKS = [
    chunk(ALPHA, front(ALPHA)),
    chunk(ALPHA, "\n".join(BODIES[ALPHA][3])),
    chunk(ALPHA, related(ALPHA)),
    chunk(BETA, front(BETA)),
    chunk(BETA, "\n".join(BODIES[BETA][3])),
    chunk(GAMMA, front(GAMMA)),
    chunk(GAMMA, "\n".join(BODIES[GAMMA][3])),
    chunk(DELTA, "\n".join(BODIES[DELTA][3])),
]
ARCHIVE = gzip.compress(
    json.dumps({"tenant_id": "fixture", "chunks": CHUNKS}, ensure_ascii=False).encode("utf-8"),
    mtime=0,
)
# The scan lists its chunks out of archive order on purpose.
SCANNED = {"M-02": [4, 2, 1, 0], "M-03": [6, 5, 3]}


def scan_of(cases: list[dict[str, Any]], scanned: Mapping[str, list[int]]) -> dict[str, Any]:
    questions = {item["case_id"]: item["question"] for item in cases}
    return {
        "schema_version": "devset-wide-scan/v1",
        "archive_sha256": sha(ARCHIVE),
        "cases": [
            {
                "case_id": case_id,
                "question_sha256": sha(questions[case_id]),
                "chunks": [
                    {
                        "chunk_index": index,
                        "source_id": CHUNKS[index]["metadata"]["source"],
                        "text_sha256": sha(CHUNKS[index]["page_content"]),
                        "lexical_rank": rank,
                        "dense_rank": None,
                    }
                    for rank, index in enumerate(indexes, 1)
                ],
            }
            for case_id, indexes in scanned.items()
            if case_id in questions
        ],
    }


@dataclass
class World:
    """One fixture set: the drafts with their corpus, scan and archive, and two round dirs."""

    drafts: v.Drafts
    inputs: v.RoundInputs
    root: Path

    @property
    def round_1(self) -> Path:
        return self.root / "round-1"

    @property
    def round_2(self) -> Path:
        return self.root / "round-2"

    @property
    def second(self) -> v.RoundInputs:
        return replace(self.inputs, round=2, previous=self.round_1)

    def arguments(self, command: str, *more: str) -> list[str]:
        built = [
            f"--corpus-dir={self.inputs.corpus_dir}",
            f"--scan={self.inputs.scan}",
            f"--archive={self.inputs.archive}",
        ]
        rounds = [f"--round-1={self.round_1}", f"--round-2={self.round_2}"]
        rebuilds = command in ("plan", "verify") or "--rebuild" in more
        return [command, *rounds, *(built if rebuilds else []), *more]

    def write(self, name: str, value: Any) -> Path:
        path = self.root / name
        data = v.jsonl(value) if name.endswith(".jsonl") else v.dump(value)
        path.write_bytes(data)
        return path


def world_of(root: Path, cases: list[dict[str, Any]]) -> World:
    corpus_dir = root / "corpus"
    corpus_dir.mkdir()
    for name, text in TEXTS.items():
        (corpus_dir / name).write_bytes(text.encode("utf-8"))
    (root / "archive.json.gz").write_bytes(ARCHIVE)
    (root / "scan.json").write_bytes(v.dump(scan_of(cases, SCANNED)))

    def script(directory: Path) -> None:
        texts = read_sources(CORPUS, directory)
        frame = devset.source_frame(texts)
        families = devset.document_families(REGISTER)
        for item in cases:
            selected = item["seed_selected_source_section"]
            devset.validate_case(item, selected, REVISIONS, CORPUS["corpus_sha256"], families)
            devset.validate_case_sources(item, texts, frame)

    manifest = {
        "generator": "gpt-6.1-sol",
        "jsonl_sha256": sha(v.jsonl(cases)),
        "families_sha256": sha(v.dump(REGISTER)),
    }
    return World(
        drafts=v.Drafts(cases, manifest, REGISTER, CORPUS, script),
        inputs=v.RoundInputs(1, corpus_dir, root / "scan.json", root / "archive.json.gz"),
        root=root,
    )


@pytest.fixture(autouse=True)
def two_voices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register the second voice beside the registered verifier."""
    monkeypatch.setattr(lv, "VERIFIERS", TWO_VOICES)
    monkeypatch.setattr(lv, "VERIFIERS_BY_AUTHOR_VENDOR", {"OpenAI": (SECOND, OPUS)})


@pytest.fixture
def one_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry as it is registered: one verifier."""
    monkeypatch.setattr(lv, "VERIFIERS", REGISTERED[0])
    monkeypatch.setattr(lv, "VERIFIERS_BY_AUTHOR_VENDOR", REGISTERED[1])


@pytest.fixture
def world(tmp_path: Path) -> World:
    return world_of(tmp_path, drafts_cases())


def reply(level: str = "moderate", changes: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    """A reply in the form of the protocol: every check confirmed unless changed."""
    answer: dict[str, dict[str, Any]] = {
        check: {"verdict": "confirm", "reason": f"Check {check} holds.", "element": None}
        for check in lv.CONFIRM_CHECKS
    }
    for check in lv.AUTHORITY_CHECKS:
        answer[check] = {"verdict": "confirm", "reason": f"Check {check} holds."}
    answer["5c"] = {"level": level, "reason": "The level fits the scale."}
    for check, change in (changes or {}).items():
        answer[check] = {**answer[check], **change}
    return json.dumps({check: answer[check] for check in lv.CHECKS}, ensure_ascii=False)


REJECT_3 = {
    "3": {"verdict": "reject", "reason": "The answer leaves out the deadline.", "element": "F1"}
}
NO_REASON = {"2": {"verdict": "reject", "reason": None, "element": "F1"}}


class Fake:
    """A verifier that answers from a script. It is handed request texts and nothing else."""

    def __init__(
        self,
        model: str,
        answers: Callable[[str], Any] | None = None,
        failures: Mapping[int, Exception] | None = None,
    ) -> None:
        self.model = model
        self.answers = answers
        self.failures = failures or {}
        self.texts: list[str] = []

    def grade(self, request_text: str) -> Reply:
        self.texts.append(request_text)
        failure = self.failures.get(len(self.texts))
        if failure is not None:
            raise failure
        answer = self.answers(request_text) if self.answers else reply()
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer, self.model, {"output_tokens": 7}, 0.25)


def run_round(
    world: World,
    out: Path,
    inputs: v.RoundInputs,
    answers: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Fake]:
    """Plan one round and let a fake of every registered verifier answer it.

    `answers` gives, per case and verifier, one reply or the list of replies to successive
    attempts; a case that is not named is confirmed at its registered severity.
    """
    v.plan_round(out, world.drafts, inputs)
    plan, texts = v.build_round(world.drafts, inputs)
    case_of = {text: case_id for case_id, text in texts.items()}
    registered = {row["case_id"]: row["registered_severity"] for row in plan["requests"]}
    queues = {
        (case_id, name): list(given) if isinstance(given, list) else [given]
        for case_id, by_name in (answers or {}).items()
        for name, given in by_name.items()
    }
    clients = {}
    for name in plan["verifiers"]:

        def answer(text: str, name: str = name) -> Any:
            case_id = case_of[text]
            queue = queues.get((case_id, name))
            if not queue:
                return reply(registered[case_id])
            return queue.pop(0) if len(queue) > 1 else queue[0]

        clients[name] = Fake(name, answer)
        v.verify(out, name, world.drafts, inputs, client=clients[name])
    return clients


def packet_of(text: str) -> dict[str, Any]:
    assert text.startswith(lv.PROMPT_TEMPLATE)
    packet: dict[str, Any] = json.loads(text[len(lv.PROMPT_TEMPLATE) :])
    return packet


def requests(world: World) -> dict[str, str]:
    return v.build_round(world.drafts, world.inputs)[1]


def rows_of(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]


def repaired_m02() -> dict[str, Any]:
    """M-02 relabelled by its author: one document, the same question and seed section."""
    draft = drafts_cases()[1]
    fixed = case(
        "M-02",
        draft["question"],
        "Нет: копии бета-накладной выдаются только при предъявлении доверенности.",
        BETA,
        facts=(BETA_FACT,),
        trap_type="false_premise",
        expected_action="correct_premise",
        action_reason="The premise contradicts the rule on copies.",
        flags=TRAP_FLAGS,
        wrong_answer_severity="high",
    )
    assert fixed["primary_class"] == "single-doc" and draft["primary_class"] == "multi-doc"
    return fixed


def reject_m02(world: World, more: Mapping[str, Mapping[str, Any]] | None = None) -> None:
    """Round 1 in which M-02 is rejected on check 3 by one verifier; the rest is confirmed."""
    run_round(
        world,
        world.round_1,
        world.inputs,
        {"M-02": {SECOND: reply("high", REJECT_3)}, **(more or {})},
    )


# --- the prompt and the registry -----------------------------------------------------------


def test_prompt_sha_is_the_one_registered_in_the_spec() -> None:
    spec = (ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    recorded = re.findall(
        r"Prompt SHA-256 \(rubric label-verification/v2\): `([0-9a-f]{64})`", spec
    )
    assert recorded == [lv.PROMPT_SHA256]
    assert lv.prompt_sha256() == lv.PROMPT_SHA256


def test_prompt_names_no_author_no_verifier_and_no_round() -> None:
    prompt = lv.PROMPT_TEMPLATE.lower()
    for word in ("gpt", "openai", "glm", "z.ai", "claude", "anthropic", "opus", "round"):
        assert word not in prompt
    assert "draft author's note" in prompt and "not evidence for check 5a or 5b" in prompt
    assert "low < moderate < high < critical" in prompt and "registered_severity" in prompt
    # The flags the verify script computes from the label are neither described nor judged.
    for word in ("ru_to_en", "numeric", "adversarial_unanswerable", "`flags`", "latin"):
        assert word not in prompt
    assert "the primary class, `safety_critical`, the trap type and `expected_action`" in prompt
    assert lv.PROMPT_TEMPLATE.endswith("\nCASE\n")


def test_the_registered_verifier_is_one_model_of_another_vendor(one_voice: None) -> None:
    author = lv.draft_author("gpt-6.1-sol")
    verifiers = lv.registered_verifiers(author)
    assert author == {"model": "gpt-6.1-sol", "vendor": "OpenAI"}
    assert {name: entry["vendor"] for name, entry in verifiers.items()} == {OPUS: "Anthropic"}
    assert verifiers[OPUS]["settings"]["effort"] == "max"
    assert verifiers[OPUS]["settings"]["tools"] == "none"
    lv.check_vendors(author, verifiers)
    # No model of another vendor is registered in any role (plan decision D12).
    assert set(lv.VERIFIERS) == {OPUS} and lv.REPAIR_AUTHOR == REPAIRER
    # A check by one model is never given the word of a check by two vendors.
    assert lv.verified_status(verifiers) == "single_model_verified"
    assert lv.verified_status(TWO_VOICES) == "model_verified"
    with pytest.raises(ValueError, match="not registered"):
        lv.draft_author("another-model")
    # Drafts by the verifier's own vendor have no registered verifier.
    with pytest.raises(ValueError, match="no verifiers are registered for drafts by Anthropic"):
        lv.registered_verifiers(REPAIRER)


# --- the request ---------------------------------------------------------------------------


def test_document_card_is_the_seven_fields_and_no_other() -> None:
    card = lv.document_card(TEXTS[ALPHA])
    assert tuple(card) == lv.CARD_FIELDS
    assert card["title"] == "Политика альфа" and card["owner_role"] == "Compliance Officer"
    # Written as in the file: a version and a date stay strings.
    assert card["version"] == "1.0" and card["effective_date"] == "2026-05-15"
    assert card["related_normative_sources"] == ["152-ФЗ", "см. 02_beta_rules.md"]
    assert lv.document_card(TEXTS[BETA])["related_normative_sources"] is None
    assert lv.document_card("# No front matter\n") == dict.fromkeys(lv.CARD_FIELDS)
    with pytest.raises(ValueError, match="front matter is not YAML"):
        lv.document_card("---\ntitle: [unclosed\n---\n# Broken\n")


def test_masker_replaces_whatever_names_a_file() -> None:
    names: dict[str, str] = {}
    masker = lv.Masker(TEXTS)

    def pseudonym(name: str) -> str:
        return names.setdefault(name, f"D{len(names) + 1}")

    assert masker.mask("см. 02_beta_rules.md и 02_beta_rules.md.", pseudonym) == "см. D1 и D1."
    assert masker.mask("Z:/share/uploads/01_alpha_policy.md", pseudonym) == "D2"
    assert masker.mask("..\\docs\\03_gamma_guide.md, MANIFEST.md", pseudonym) == "D3, [file]"
    assert masker.mask("docs/other/NOTES.MD", pseudonym) == "[file]"
    # A doc_id line gives the document away; an id that no document has is hidden as well.
    assert masker.mask("---\ndoc_id: guide\ntitle: x", pseudonym) == "---\ndoc_id: D3\ntitle: x"
    assert masker.mask('doc_id: "unknown_id"', pseudonym) == "doc_id: [file]"
    # A stem or an id that is not a plain word is replaced anywhere; a plain word is a word.
    assert masker.mask("код beta_rules, файл 01_alpha_policy", pseudonym) == "код D1, файл D2"
    assert masker.mask("слово guide и beta_rules_v2", pseudonym) == "слово guide и beta_rules_v2"
    assert names == {BETA: "D1", ALPHA: "D2", GAMMA: "D3"}
    assert masker.leaks("см. D1 и [file]") == []
    assert masker.leaks("x01_alpha_policy.md и NOTES.md") == [
        ALPHA,
        "NOTES.md",
        "x01_alpha_policy.md",
    ]


def test_an_identifier_two_documents_share_is_hidden_without_a_pseudonym() -> None:
    twin = TEXTS[GAMMA].replace("doc_id: guide", "doc_id: beta_rules")
    masker = lv.Masker({**TEXTS, GAMMA: twin})
    assert masker.mask("код beta_rules", lambda name: "D9") == "код [file]"


def test_masker_hides_a_path_and_a_labelled_identifier() -> None:
    names: dict[str, str] = {}
    masker = lv.Masker(TEXTS)

    def pseudonym(name: str) -> str:
        return names.setdefault(name, f"D{len(names) + 1}")

    # A path is hidden whatever its last name is, and one with a space leaves no part behind.
    assert masker.mask("См. /private/config/settings.json; далее", pseudonym) == "См. [file]; далее"
    assert masker.mask("See Z:/Shared Docs/policy.md.", pseudonym) == "See [file] [file]."
    assert (
        masker.mask("лежит в Z:\\Shared\\Reports, и в ~/notes/todo", pseudonym)
        == "лежит в [file], и в [file]"
    )
    assert masker.mask("\\\\server\\share\\plan.xlsx", pseudonym) == "[file]"
    assert masker.mask("data/exports/list.csv и exports\\list.csv", pseudonym) == "[file] и [file]"
    # A path that holds an identifier is replaced whole: no pseudonym tells where it led.
    assert masker.mask("архив docs/alpha_policy/readme.txt", pseudonym) == "архив [file]"
    assert names == {}
    # A slash between words, a date, a ratio and a URL are not paths; nor is a lone file name.
    prose = (
        "AWB/MAWB/HAWB, и/или, 01/02/2026, 24/7, кг/м3, см. "
        "https://www.consultant.ru/document/cons_doc_LAW_34683/ и report.pdf."
    )
    assert masker.mask(prose, pseudonym) == prose and masker.leaks(prose) == []
    # The value of a doc_id or source_id label is hidden wherever the label stands.
    assert (
        masker.mask("See doc_id=guide; source_id: 'x-17', DOC_ID = beta_rules.", pseudonym)
        == "See doc_id=D1; source_id: [file], DOC_ID = D2."
    )
    assert (
        masker.mask('{"doc_id": "guide", "source_id": "02_beta_rules.md"}', pseudonym)
        == '{"doc_id": D1, "source_id": "D2"}'
    )
    assert names == {GAMMA: "D1", BETA: "D2"}
    leaked = (
        "Z:/Shared, /private/config/settings.json, data/list.csv, doc_id=guide, source_id: x-17"
    )
    assert masker.leaks(leaked) == [
        "/private/config/settings.json",
        "Z:/Shared",
        "data/list.csv",
        "doc_id=guide",
        "source_id: x-17",
    ]
    assert masker.leaks("doc_id: D1, source_id=D12, doc_id: [file], https://site.ru/a/b.html") == []


def test_request_carries_the_whole_case(world: World) -> None:
    draft = world.drafts.cases[3]
    packet = packet_of(requests(world)["M-04"])
    assert packet["question"] == draft["question"]
    assert packet["reference_answer"] == draft["reference_answer"]
    assert packet["as_of"] == "2026-10-01"
    assert packet["primary_class"] == "multi-doc" and packet["trap_type"] is None
    assert packet["expected_action"] == "answer" and packet["registered_reason"] is None
    assert packet["registered_severity"] == "critical"
    assert packet["safety_critical"] is True and draft["flags"]["safety_critical"] is True
    # The flags the verify script computes from the label are not sent.
    for text in requests(world).values():
        body = text[len(lv.PROMPT_TEMPLATE) :]
        for word in ("flags", "ru_to_en", "numeric", "adversarial_unanswerable"):
            assert word not in body
    assert [(item["id"], item["document"]) for item in packet["spans"]] == [
        ("S1", "D2"),
        ("S2", "D1"),
    ]
    assert packet["spans"][0]["section"] == ["Справочник гамма", "Формы актов"]
    assert "\n".join(BODIES[GAMMA][3]) in packet["spans"][0]["text"]
    assert [(item["id"], item["critical"]) for item in packet["facts"]] == [
        ("F1", True),
        ("F2", False),
    ]
    assert packet["facts"][0]["text"] == GAMMA_FACT["text"]
    assert packet["facts"][0]["source_quote"] == GAMMA_FACT["source_quote"]
    assert packet["facts"][1]["subject"] == "отказ" and packet["facts"][1]["polarity"] == "allowed"
    assert [item["document"] for item in packet["authority_documents"]] == ["D1", "D2"]
    assert packet["authority_documents"][0]["card"] == {
        **lv.document_card(TEXTS[BETA]),
        "related_normative_sources": None,
    }
    assert tuple(packet["authority_documents"][1]["card"]) == lv.CARD_FIELDS
    # An answer case is judged by its spans: no sections and no scan go out.
    assert "sections" not in packet and "scan" not in packet and "aggregation" not in packet


def test_trap_case_also_carries_its_sections_and_the_scan_in_archive_order(world: World) -> None:
    texts = requests(world)
    packet = packet_of(texts["M-02"])
    assert packet["trap_type"] == "false_premise" and packet["expected_action"] == "correct_premise"
    assert packet["registered_reason"] == "The premise contradicts the rule on copies."
    assert [(item["id"], item["role"], item["document"]) for item in packet["sections"]] == [
        ("X1", "seed-selected", "D2"),
        ("X2", "partner", "D1"),
    ]
    assert "\n".join(BODIES[BETA][3]) in packet["sections"][0]["text"]
    # The scan file lists chunks 4, 2, 1, 0; the request holds them as the archive does.
    assert [item["id"] for item in packet["scan"]] == ["P1", "P2", "P3", "P4"]
    assert [item["document"] for item in packet["scan"]] == ["D1", "D1", "D1", "D2"]
    assert "Срок хранения альфа-журнала" in packet["scan"][1]["text"]
    refusal = packet_of(texts["M-03"])
    assert refusal["spans"] == [] and refusal["facts"] == []
    assert refusal["registered_reason"] == "The corpus holds no rule on insuring fragile cargo."
    assert [item["role"] for item in refusal["sections"]] == ["seed-selected"]
    assert len(refusal["scan"]) == 3


def test_a_file_name_would_leave_the_machine(world: World) -> None:
    """Scenario: two source files, one lists the other under «Связанные документы»."""
    plan, texts = v.build_round(world.drafts, world.inputs)
    text = texts["M-02"]
    packet = packet_of(text)
    row = next(row for row in plan["requests"] if row["case_id"] == "M-02")
    # The gamma file is no source of the case: the alpha span names it, so it has a pseudonym.
    assert row["pseudonyms"] == {"D1": ALPHA, "D2": BETA, "D3": GAMMA}
    assert [item["document"] for item in packet["spans"]] == ["D2", "D1"]
    assert [item["document"] for item in packet["authority_documents"]] == ["D1", "D2"]
    listing = packet["scan"][2]
    assert listing["document"] == "D1"
    assert listing["text"].startswith("[Контекст: Из документа D1, раздел: Политика альфа")
    assert "- D2 — смежный документ\n- [file]" in listing["text"]
    assert packet["scan"][3]["text"].startswith("[Контекст: Из документа D2,")
    # The alpha span cites the beta file, a path to the gamma file and a file outside the corpus.
    assert "описана в D2, перечень лежит в D3 и в [file]." in packet["spans"][1]["text"]
    assert "Код D2 пишут" in packet["spans"][1]["text"]
    assert "doc_id: D1" in packet["scan"][0]["text"]
    assert packet["authority_documents"][0]["card"]["related_normative_sources"][1] == "см. D2"
    for name in BODIES:
        assert name not in text and name[:-3] not in text
    assert ".md" not in text.lower() and "alpha_policy" not in text and "beta_rules" not in text


def test_request_holds_no_scope_author_verifier_round_or_case_id(world: World) -> None:
    for case_id, text in requests(world).items():
        body = text[len(lv.PROMPT_TEMPLATE) :]
        lowered = text.lower()
        assert "Owner must confirm" not in text and "scope" not in body
        assert case_id not in text and "-E1" not in text and "selection_reason" not in body
        for word in ("gpt", "openai", "glm", "z.ai", "claude", "anthropic", "round", "agent_style"):
            assert word not in lowered
        # A card is the seven fields: a front-matter field beyond them stays out of it.
        cards = json.dumps(packet_of(text)["authority_documents"], ensure_ascii=False)
        assert "classification" not in cards and "internal-secret" not in cards


def test_a_fact_quote_that_cuts_a_file_name_is_refused(world: World) -> None:
    draft = copy.deepcopy(world.drafts.cases[0])
    texts = read_sources(CORPUS, world.inputs.corpus_dir)
    # A quote that ends on a whole identifier is masked as its span is.
    draft["required_facts"][0]["source_quote"] = "Выдача копий описана в 02_beta_rules"
    packet = packet_of(lv.build_request(draft, texts, lv.Masker(texts)).text)
    assert packet["facts"][0]["source_quote"] == "Выдача копий описана в D2"
    # A quote that ends inside a name would go out with a part of it.
    draft["required_facts"][0]["source_quote"] = "Выдача копий описана в 02_beta"
    with pytest.raises(ValueError, match="a fact quote cuts a file name"):
        lv.build_request(draft, texts, lv.Masker(texts))


def test_a_trap_case_needs_the_scan_of_its_question(world: World) -> None:
    texts = read_sources(CORPUS, world.inputs.corpus_dir)
    trap = world.drafts.cases[1]
    scan = scan_of(world.drafts.cases, SCANNED)
    with pytest.raises(ValueError, match="no wide scan made for the question of M-02"):
        lv.build_request(trap, texts, lv.Masker(texts))
    other = {**trap, "question": trap["question"] + " "}
    with pytest.raises(ValueError, match="no wide scan made for the question of M-02"):
        lv.scan_passages(other, scan, CHUNKS)
    with pytest.raises(ValueError, match="no wide scan made for the question of M-01"):
        lv.scan_passages(world.drafts.cases[0], scan, CHUNKS)
    passages = lv.scan_passages(trap, scan, CHUNKS)
    assert [item["source_id"] for item in passages] == [ALPHA, ALPHA, ALPHA, BETA]
    # Either sign makes a case one whose reason is held against the scan.
    assert lv.needs_scan({"expected_action": "answer", "trap_type": "false_premise"})
    assert lv.needs_scan({"expected_action": "clarify", "trap_type": None})
    assert not lv.needs_scan({"expected_action": "answer", "trap_type": None})


def test_a_name_the_masking_missed_stops_the_request(world: World) -> None:
    class Blind(lv.Masker):
        def mask(self, text: str, pseudonym: Callable[[str], str]) -> str:
            return text

    texts = read_sources(CORPUS, world.inputs.corpus_dir)
    with pytest.raises(
        ValueError, match=r"a file name would leave the machine: .*02_beta_rules\.md"
    ):
        lv.build_request(world.drafts.cases[0], texts, Blind(texts))


def test_a_path_or_a_labelled_identifier_in_a_case_text_does_not_go_out(world: World) -> None:
    texts = read_sources(CORPUS, world.inputs.corpus_dir)
    masker = lv.Masker(texts)
    draft = copy.deepcopy(world.drafts.cases[1])
    passages = lv.scan_passages(draft, scan_of(world.drafts.cases, SCANNED), CHUNKS)
    draft["action_reason"] = (
        "See Z:/Shared Docs/policy.md; /private/config/settings.json; doc_id=guide;"
    )
    packet = packet_of(lv.build_request(draft, texts, masker, passages).text)
    assert packet["registered_reason"] == "See [file] [file]; [file]; doc_id=D3;"
    # The request is checked string by string: in its JSON text a line break before a dotted
    # word would read as the backslash of a path.
    broken = "The scan holds no such rule\nwww.example.org is not a source."
    assert masker.leaks(broken) == [] and masker.leaks(json.dumps(broken)) != []
    draft["action_reason"] = broken
    packet = packet_of(lv.build_request(draft, texts, masker, passages).text)
    assert packet["registered_reason"] == broken

    class Blind(lv.Masker):
        def mask(self, text: str, pseudonym: Callable[[str], str]) -> str:
            return text

    draft["action_reason"] = "See /private/config/settings.json"
    with pytest.raises(
        ValueError, match="a file name would leave the machine: .*/private/config/settings.json"
    ):
        lv.build_request(draft, texts, Blind(texts), passages)


@pytest.mark.parametrize("named", ["gpt-6.1-sol", "Claude-Opus-5-5", "claude-opus-5-5"])
def test_a_case_that_names_a_model_of_the_verification_is_refused(world: World, named: str) -> None:
    texts = read_sources(CORPUS, world.inputs.corpus_dir)
    draft = copy.deepcopy(world.drafts.cases[0])
    draft["reference_answer"] += f" Drafted by {named}."
    message = "a model that drafts or verifies would be named in the request: "
    with pytest.raises(ValueError, match=message + re.escape(named.lower())):
        lv.build_request(draft, texts, lv.Masker(texts))
    assert set(lv.MODEL_IDS) == {"gpt-6.1-sol", OPUS}


# --- the plan ------------------------------------------------------------------------------


def test_plan_records_what_binds_a_request_and_no_request_text(world: World) -> None:
    summary = v.plan_round(world.round_1, world.drafts, world.inputs)
    texts = requests(world)
    raw = (world.round_1 / "plan.json").read_text(encoding="utf-8")
    plan = json.loads(raw)
    assert summary["requests"] == 4 and summary["declared_drops"] == 0
    assert plan["rubric_version"] == "label-verification/v2"
    assert plan["prompt_sha256"] == lv.PROMPT_SHA256 and plan["round"] == 1
    assert plan["draft_author"] == {"model": "gpt-6.1-sol", "vendor": "OpenAI"}
    assert plan["verifiers"] == json.loads(
        json.dumps(lv.registered_verifiers(plan["draft_author"]))
    )
    for entry in plan["verifiers"].values():
        assert set(entry) == {"model", "vendor", "route", "settings"}
    assert plan["inputs"]["drafts_sha256"] == world.drafts.manifest["jsonl_sha256"]
    assert plan["inputs"]["scan_sha256"] == sha(world.inputs.scan.read_bytes())
    assert plan["inputs"]["archive_sha256"] == sha(ARCHIVE)
    for row, draft in zip(plan["requests"], world.drafts.cases, strict=True):
        text = texts[row["case_id"]]
        assert row["case_id"] == draft["case_id"] and row["round"] == 1
        assert row["request_sha256"] == sha(text) and row["characters"] == len(text)
        assert row["case_sha256"] == lv.case_sha256(draft)
        assert row["corpus_texts"] == sum(row["corpus_text_counts"].values())
        assert set(row["pseudonyms"].values()) >= set(draft["documents"])
    counts = {row["case_id"]: row["corpus_text_counts"] for row in plan["requests"]}
    assert counts["M-01"] == {"spans": 1, "cards": 1, "sections": 0, "scan": 0}
    assert counts["M-02"] == {"spans": 2, "cards": 2, "sections": 2, "scan": 4}
    assert counts["M-03"] == {"spans": 0, "cards": 1, "sections": 1, "scan": 3}
    # The text of a request is in no file of the round: only its SHA-256 is.
    assert "альфа-журнал" not in raw.lower() and "Check 1" not in raw
    assert [path.name for path in world.round_1.iterdir()] == ["plan.json"]
    # The same plan may be written again; another plan in the same directory may not.
    v.plan_round(world.round_1, world.drafts, world.inputs)
    v.write_plan(world.round_1, plan)
    with pytest.raises(ValueError, match="a different plan exists"):
        v.write_plan(world.round_1, {**plan, "round": 2})


def test_both_verifiers_receive_the_same_text(world: World) -> None:
    clients = run_round(world, world.round_1, world.inputs)
    assert clients[SECOND].texts == clients[OPUS].texts == list(requests(world).values())


def refuse_prompt(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lv, "PROMPT_SHA256", "0" * 64)


def refuse_corpus(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    (world.inputs.corpus_dir / GAMMA).write_bytes((TEXTS[GAMMA] + "\n").encode("utf-8"))


def refuse_drafts(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.drafts.cases[0]["evidence_spans"][0]["text_sha256"] = "0" * 64


def refuse_no_scan(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.inputs.scan.write_bytes(v.dump(scan_of(world.drafts.cases, {"M-02": [4, 2, 1, 0]})))


def refuse_other_question(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    scan = scan_of(world.drafts.cases, SCANNED)
    scan["cases"][1]["question_sha256"] = sha("another question")
    world.inputs.scan.write_bytes(v.dump(scan))


def refuse_scan_text(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    scan = scan_of(world.drafts.cases, SCANNED)
    scan["cases"][0]["chunks"][1]["text_sha256"] = sha("another text")
    world.inputs.scan.write_bytes(v.dump(scan))


def refuse_scan_source(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    scan = scan_of(world.drafts.cases, SCANNED)
    scan["cases"][0]["chunks"][1]["source_id"] = GAMMA
    world.inputs.scan.write_bytes(v.dump(scan))


def refuse_scan_index(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    scan = scan_of(world.drafts.cases, SCANNED)
    scan["cases"][0]["chunks"][0]["chunk_index"] = len(CHUNKS)
    world.inputs.scan.write_bytes(v.dump(scan))


def refuse_scan_repeat(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    scan = scan_of(world.drafts.cases, SCANNED)
    scan["cases"][0]["chunks"].append(scan["cases"][0]["chunks"][0])
    world.inputs.scan.write_bytes(v.dump(scan))


def refuse_archive(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.inputs.archive.write_bytes(gzip.compress(b'{"chunks": [{"page_content": "x"}]}', mtime=0))


def refuse_scan_schema(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.inputs.scan.write_bytes(
        v.dump({**scan_of(world.drafts.cases, SCANNED), "schema_version": "v0"})
    )


def refuse_scan_not_json(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    world.inputs.scan.write_bytes(b"not a scan")


@pytest.mark.parametrize(
    ("spoil", "message"),
    [
        (refuse_prompt, "the prompt is not the registered one"),
        (refuse_corpus, "the corpus is not the registered version"),
        (refuse_drafts, "the drafts fail the verify script"),
        (refuse_no_scan, "no wide scan made for the question of M-03"),
        (refuse_other_question, "no wide scan made for the question of M-03"),
        (refuse_scan_text, "a scan text of M-02 does not match the chunk archive"),
        (refuse_scan_source, "a scan text of M-02 does not match the chunk archive"),
        (refuse_scan_index, "the scan of M-02 repeats a chunk or holds one outside the archive"),
        (refuse_scan_repeat, "the scan of M-02 repeats a chunk or holds one outside the archive"),
        (refuse_archive, "Corpus archive SHA-256 mismatch"),
        (refuse_scan_schema, "not a wide scan of the registered schema"),
        (refuse_scan_not_json, "not a wide scan of the registered schema"),
    ],
)
def test_plan_refuses_and_writes_nothing(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    spoil: Callable[[World, pytest.MonkeyPatch], None],
    message: str,
) -> None:
    spoil(world, monkeypatch)
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    with pytest.raises(ValueError, match=message):
        v.plan_round(world.round_1, world.drafts, world.inputs)
    assert v.main(world.arguments("plan", "--round=1")) == 2
    assert "refused: " in capsys.readouterr().out
    assert not world.round_1.exists()


@pytest.mark.parametrize(
    ("vendors", "message"),
    [
        (("OpenAI", "Anthropic"), "a verifier's vendor is the draft author's"),
        (("Z.ai", "openai"), "a verifier's vendor is the draft author's"),
        (("Anthropic", "Anthropic"), "two verifiers share a vendor"),
    ],
)
def test_plan_refuses_verifiers_that_are_not_of_other_vendors(
    world: World, vendors: tuple[str, str], message: str
) -> None:
    verifiers: dict[str, lv.Verifier] = {
        name: {**lv.VERIFIERS[name], "vendor": vendor}
        for name, vendor in zip((SECOND, OPUS), vendors, strict=True)
    }
    with pytest.raises(ValueError, match=message):
        v.build_round(world.drafts, world.inputs, verifiers)
    with pytest.raises(ValueError, match="label verification needs a verifier"):
        v.build_round(world.drafts, world.inputs, {})
    alone: dict[str, lv.Verifier] = {OPUS: {**lv.VERIFIERS[OPUS], "vendor": "OpenAI"}}
    with pytest.raises(ValueError, match="a verifier's vendor is the draft author's"):
        v.build_round(world.drafts, world.inputs, alone)


# --- round 2: a repair or a declared drop --------------------------------------------------


def test_round_2_plans_the_repair_and_records_the_declared_drop(world: World) -> None:
    reject_m02(world, {"M-03": {OPUS: reply("moderate", REJECT_3)}})
    repairs = world.write("repairs.jsonl", [repaired_m02()])
    drops = world.write(
        "drops.json", [{"case_id": "M-03", "ground": "repair_needs_reserve", "documents": [DELTA]}]
    )
    inputs = replace(world.second, repairs=repairs, drops=drops)
    summary = v.plan_round(world.round_2, world.drafts, inputs)
    plan = json.loads((world.round_2 / "plan.json").read_text(encoding="utf-8"))
    assert summary == {**summary, "round": 2, "requests": 1, "declared_drops": 1}
    assert [row["case_id"] for row in plan["requests"]] == ["M-02"]
    assert plan["requests"][0]["case_sha256"] == lv.case_sha256(repaired_m02())
    assert plan["requests"][0]["primary_class"] == "single-doc"
    assert plan["requests"][0]["documents"] == [BETA]
    assert plan["requests"][0]["families"] == ["family-b"]
    assert plan["declared_drops"] == [
        {"case_id": "M-03", "ground": "repair_needs_reserve", "documents": [DELTA]}
    ]
    assert plan["inputs"]["previous_plan_sha256"] == sha((world.round_1 / "plan.json").read_bytes())
    assert plan["inputs"]["repairs_sha256"] == sha(repairs.read_bytes())
    # The second check is made in full and with no trace of the first.
    text = v.build_round(world.drafts, inputs)[1]["M-02"]
    assert "leaves out the deadline" not in text and "round" not in text.lower()
    assert packet_of(text)["primary_class"] == "single-doc"
    assert [item["document"] for item in packet_of(text)["spans"]] == ["D1"]


def change_question(fixed: dict[str, Any]) -> None:
    fixed["question"] = "Выдают ли копии бета-накладной без доверенности?"


def change_as_of(fixed: dict[str, Any]) -> None:
    fixed["as_of"] = "2026-11-01"


def change_style(fixed: dict[str, Any]) -> None:
    fixed["question_origin"] = "agent_style_B"


def change_seed(fixed: dict[str, Any]) -> None:
    fixed.update(
        case("M-02", fixed["question"], ALPHA_FACT["text"] + ".", ALPHA, facts=(ALPHA_FACT,))
    )


def change_author(fixed: dict[str, Any]) -> None:
    # The agent that repairs is not the author of the draft.
    fixed["draft_author"] = dict(REPAIRER)


def change_corpus_version(fixed: dict[str, Any]) -> None:
    fixed["evidence_spans"][0]["corpus_version"] = "0" * 64


def reach_into_reserve(fixed: dict[str, Any]) -> None:
    fixed.update(
        case(
            "M-02",
            fixed["question"],
            fixed["reference_answer"],
            BETA,
            (DELTA,),
            (BETA_FACT,),
            trap_type="false_premise",
            expected_action="correct_premise",
            action_reason=fixed["action_reason"],
            flags=TRAP_FLAGS,
        )
    )


def break_case_rule(fixed: dict[str, Any]) -> None:
    fixed["wrong_answer_severity"] = "severe"


def break_source_check(fixed: dict[str, Any]) -> None:
    fixed["evidence_spans"][0]["normalized_text"] = "another text"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (change_question, "a repair changes question: M-02"),
        (change_as_of, "a repair changes as_of: M-02"),
        (change_style, "a repair changes question_origin: M-02"),
        (change_seed, "a repair changes seed_selected_source_section: M-02"),
        (change_author, "a repair changes the draft author: M-02"),
        (change_corpus_version, r"fails the rules of the verify script \(span source address\)"),
        (reach_into_reserve, "a repair cites the holdout reserve: 04_delta_reserve.md: M-02"),
        (break_case_rule, r"fails the rules of the verify script \(severity enum\): M-02"),
        (break_source_check, r"fails the rules of the verify script \(normalized span text\)"),
    ],
)
def test_round_2_refuses_a_repair_that_breaks_its_bounds(
    world: World, change: Callable[[dict[str, Any]], None], message: str
) -> None:
    """Scenarios: a repair that changes the question; a repair that reaches into the reserve."""
    reject_m02(world)
    fixed = repaired_m02()
    change(fixed)
    inputs = replace(world.second, repairs=world.write("repairs.jsonl", [fixed]))
    with pytest.raises(ValueError, match=message):
        v.plan_round(world.round_2, world.drafts, inputs)
    assert not world.round_2.exists()


def test_round_2_refuses_a_repair_that_names_a_verifier(world: World) -> None:
    """What a repair says of the first check in other words no script can tell; a model id can."""
    reject_m02(world)
    fixed = repaired_m02()
    fixed["action_reason"] = "Rejected in round 1 by claude-opus-5-5: the premise is false."
    inputs = replace(world.second, repairs=world.write("repairs.jsonl", [fixed]))
    with pytest.raises(ValueError, match="would be named in the request: claude-opus-5-5"):
        v.plan_round(world.round_2, world.drafts, inputs)
    assert not world.round_2.exists()


def test_round_2_refuses_a_repair_that_leaves_the_label_as_drafted(world: World) -> None:
    """A second request on an unchanged label would be a second draw of the same check."""
    reject_m02(world)
    draft = world.drafts.cases[1]
    returned = {
        **draft,
        "draft_author": {"model": "gpt-6.1-sol", "vendor": "OpenAI"},
        "label_check": {"status": "none"},
        "authority_unverified": False,
    }
    for same in (draft, returned):
        inputs = replace(world.second, repairs=world.write("repairs.jsonl", [same]))
        with pytest.raises(ValueError, match="a repair leaves the label as drafted: M-02"):
            v.plan_round(world.round_2, world.drafts, inputs)
    assert not world.round_2.exists()


def test_round_2_refuses_a_case_round_1_did_not_reject_or_one_given_twice(world: World) -> None:
    reject_m02(world)
    confirmed = world.write("confirmed.jsonl", [world.drafts.cases[0]])
    with pytest.raises(ValueError, match="a case was not rejected in round 1: M-01"):
        v.plan_round(world.round_2, world.drafts, replace(world.second, repairs=confirmed))
    drop = {"case_id": "M-02", "ground": "repair_needs_reserve", "documents": [DELTA]}
    both = replace(
        world.second,
        repairs=world.write("repairs.jsonl", [repaired_m02()]),
        drops=world.write("drops.json", [drop]),
    )
    with pytest.raises(ValueError, match="given both as a repair and as a declared drop: M-02"):
        v.plan_round(world.round_2, world.drafts, both)
    unknown = world.write("unknown.json", [{**drop, "case_id": "M-99"}])
    with pytest.raises(ValueError, match="a case was not rejected in round 1: M-99"):
        v.plan_round(world.round_2, world.drafts, replace(world.second, drops=unknown))
    nameless = world.write("nameless.json", [{**drop, "case_id": ["M-02"]}])
    with pytest.raises(ValueError, match="a repair or a declared drop names no case"):
        v.plan_round(world.round_2, world.drafts, replace(world.second, drops=nameless))
    assert not world.round_2.exists()


@pytest.mark.parametrize(
    ("drop", "message"),
    [
        ({"documents": []}, "a declared drop names no document: M-02"),
        ({"documents": [ALPHA]}, "names a document outside the holdout reserve: M-02"),
        ({"documents": [DELTA, BETA]}, "names a document outside the holdout reserve: M-02"),
        (
            {"ground": "too_hard"},
            "a declared drop needs the ground repair_needs_reserve or repair_not_possible: M-02",
        ),
        ({"ground": "repair_not_possible"}, "a declared drop gives no reason: M-02"),
        ({"ground": "repair_not_possible", "reason": "  "}, "gives no reason: M-02"),
        ({"ground": "repair_not_possible", "reason": ["none"]}, "gives no reason: M-02"),
    ],
)
def test_round_2_refuses_a_declared_drop_without_its_support(
    world: World, drop: dict[str, Any], message: str
) -> None:
    """Scenarios: a declared drop that names no reserve document, or one without a reason."""
    reject_m02(world)
    declared = {"case_id": "M-02", "ground": "repair_needs_reserve", "documents": [DELTA], **drop}
    inputs = replace(world.second, drops=world.write("drops.json", [declared]))
    with pytest.raises(ValueError, match=message):
        v.plan_round(world.round_2, world.drafts, inputs)
    assert not world.round_2.exists()


def test_round_2_is_planned_on_the_inputs_of_round_1(world: World) -> None:
    reject_m02(world)
    scan = scan_of(world.drafts.cases, {**SCANNED, "M-03": [6, 5]})
    world.inputs.scan.write_bytes(v.dump(scan))
    inputs = replace(world.second, repairs=world.write("repairs.jsonl", [repaired_m02()]))
    with pytest.raises(ValueError, match="round 2 is not planned on the inputs of round 1"):
        v.plan_round(world.round_2, world.drafts, inputs)
    with pytest.raises(ValueError, match="round 2 needs the directory of round 1"):
        v.plan_round(world.round_2, world.drafts, replace(inputs, previous=None))


# --- the stores ----------------------------------------------------------------------------


def test_store_keeps_the_reply_as_given_and_no_secret(world: World) -> None:
    clients = run_round(world, world.round_1, world.inputs)
    plan = json.loads((world.round_1 / "plan.json").read_text(encoding="utf-8"))
    raw = (world.round_1 / f"{SECOND}.jsonl").read_text(encoding="utf-8")
    rows = rows_of(world.round_1 / f"{SECOND}.jsonl")
    assert len(rows) == len(clients[SECOND].texts) == 4
    for row, planned in zip(rows, plan["requests"], strict=True):
        assert row == {
            "case_id": planned["case_id"],
            "round": 1,
            "verifier": SECOND,
            "attempt": 1,
            "request_sha256": planned["request_sha256"],
            "prompt_sha256": lv.PROMPT_SHA256,
            "rubric_version": "label-verification/v2",
            "status": "valid",
            "model": SECOND,
            "raw_reply": reply(planned["registered_severity"]),
            "usage": {"output_tokens": 7},
            "elapsed_s": 0.25,
            "error": None,
        }
    for secret in ("http", "api.z.ai", "settings", str(world.root)):
        assert secret not in raw
    # A request text is not stored either.
    assert "альфа-журнал" not in raw.lower()


class Chatty(Fake):
    """A route that reports more with its usage than a store may keep."""

    def grade(self, request_text: str) -> Reply:
        given = super().grade(request_text)
        usage = {
            **given.usage,
            "input_tokens": "12",
            "cache_read_input_tokens": True,
            "total_cost_usd": float("nan"),
            "endpoint": "https://judge.example.invalid/v1",
            "api_key": "sk-test-123",
            "settings_path": "/etc/judge/settings.json",
            "server_tool_use": {"web_search_requests": 0},
        }
        return Reply(given.text, given.model, usage, given.elapsed_s)


def test_a_store_keeps_only_the_registered_counters_of_usage(world: World) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=Chatty(SECOND))
    path = world.round_1 / f"{SECOND}.jsonl"
    assert [row["usage"] for row in rows_of(path)] == [{"output_tokens": 7}] * 4
    raw = path.read_text(encoding="utf-8")
    for secret in ("example.invalid", "sk-test-123", "settings.json", "NaN", "server_tool_use"):
        assert secret not in raw
    assert v.usage_counts(None) == {} and v.usage_counts(["output_tokens"]) == {}
    counted = {"output_tokens": 7, "total_cost_usd": 0.5, "input_tokens": float("inf")}
    assert v.usage_counts(counted) == {"output_tokens": 7, "total_cost_usd": 0.5}
    usage = {"output_tokens": 11, "service_tier": "standard", "iterations": [{"type": "message"}]}
    kept = v.parse_cli_envelope(envelope(usage=usage, total_cost_usd=None), OPUS)
    assert kept["usage"] == {"output_tokens": 11}
    assert v.parse_cli_envelope(envelope(usage="none"), OPUS)["usage"] == {"total_cost_usd": 0.5}


WRITTEN_BY_NO_VERIFY: list[list[tuple[Any, str]]] = [
    [(1, "invalid"), (2, "invalid"), (3, "invalid"), (4, "valid")],
    [(1, "invalid"), (2, "invalid"), (3, "invalid"), (3, "unavailable")],
    [(1, "valid"), (2, "valid")],
    [(1, "valid"), (1, "valid")],
    [(1, "valid"), (2, "unavailable")],
    [(2, "valid")],
    [(1, "invalid"), (1, "valid")],
    [(1, "unavailable"), (2, "valid")],
    [("1", "valid")],
    [(True, "valid")],
    [(None, "valid")],
]


@pytest.mark.parametrize("history", WRITTEN_BY_NO_VERIFY)
def test_a_store_holds_only_the_attempts_verify_writes(
    world: World, history: list[tuple[Any, str]]
) -> None:
    """A verdict on a fourth attempt, or a second verdict, is not one the rule counts."""
    run_round(world, world.round_1, world.inputs)
    path = world.round_1 / f"{SECOND}.jsonl"
    rows = rows_of(path)
    assert (rows[0]["case_id"], rows[0]["attempt"], rows[0]["status"]) == ("M-01", 1, "valid")
    written = [{**rows[0], "attempt": number, "status": status} for number, status in history]
    path.write_bytes(v.jsonl([*written, *rows[1:]]))
    message = f"the store of {SECOND} holds attempts that verify does not write: M-01"
    with pytest.raises(ValueError, match=message):
        v.decide(world.round_1, world.drafts)
    client = Fake(SECOND)
    with pytest.raises(ValueError, match=message):
        v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=client)
    assert client.texts == []


def test_a_store_as_verify_writes_it_is_read(world: World) -> None:
    """An unavailable verifier takes no attempt: the next row carries the same number."""
    run_round(world, world.round_1, world.inputs)
    path = world.round_1 / f"{SECOND}.jsonl"
    rows = rows_of(path)
    history = [
        (1, "unavailable"),
        (1, "invalid"),
        (2, "unavailable"),
        (2, "unavailable"),
        (2, "invalid"),
        (3, "valid"),
    ]
    written = [{**rows[0], "attempt": number, "status": status} for number, status in history]
    path.write_bytes(v.jsonl([*written, *rows[1:]]))
    assert v.decide(world.round_1, world.drafts)[0]["confirmed"] == 4


def test_no_request_is_sent_when_its_reply_cannot_be_kept(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    opened = Path.open

    def locked(self: Path, *arguments: Any, **options: Any) -> Any:
        if self.name == f"{SECOND}.jsonl":
            raise PermissionError(13, "Permission denied", str(self))
        return opened(self, *arguments, **options)

    monkeypatch.setattr(Path, "open", locked)
    client = Fake(SECOND)
    with pytest.raises(PermissionError):
        v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=client)
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    monkeypatch.setattr(v, "make_client", lambda name: client)
    capsys.readouterr()
    assert v.main(world.arguments("verify", "--round=1", f"--verifier={SECOND}")) == 2
    printed = capsys.readouterr().out.strip()
    assert printed == f"refused: a file cannot be read or written: {SECOND}.jsonl"
    assert client.texts == [] and not (world.round_1 / f"{SECOND}.jsonl").exists()


def thirty(root: Path) -> World:
    cases = [{**drafts_cases()[0], "case_id": f"Q-{index:02d}"} for index in range(1, 31)]
    return world_of(root, cases)


def test_one_verifier_is_out_of_quota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario: thirty requests, the tenth refused with a quota error, a rerun after the reset."""
    world = thirty(tmp_path)
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    assert v.main(world.arguments("plan", "--round=1")) == 0
    first = Fake(SECOND, failures={10: JudgeUnavailable("1308", "Judge rejected the request")})
    monkeypatch.setattr(v, "make_client", lambda name: first)
    arguments = world.arguments("verify", "--round=1", f"--verifier={SECOND}")
    assert v.main(arguments) == 1
    summary = json.loads(capsys.readouterr().out.strip().split("\n")[-1])
    assert summary == {
        "verifier": SECOND,
        "round": 1,
        "requests": 30,
        "valid": 9,
        "invalid": 0,
        "pending": 21,
        "sent": 10,
        "unavailable": "1308",
    }
    rows = rows_of(world.round_1 / f"{SECOND}.jsonl")
    assert [row["status"] for row in rows] == ["valid"] * 9 + ["unavailable"]
    assert rows[9]["case_id"] == "Q-10" and rows[9]["error"] == "1308"
    assert rows[9]["raw_reply"] is None and len(first.texts) == 10
    second = Fake(SECOND)
    monkeypatch.setattr(v, "make_client", lambda name: second)
    assert v.main(arguments) == 0
    assert len(second.texts) == 21
    rows = rows_of(world.round_1 / f"{SECOND}.jsonl")
    assert [row["case_id"] for row in rows if row["status"] == "valid"] == [
        f"Q-{index:02d}" for index in range(1, 31)
    ]


def test_a_rejection_without_a_reason_is_stored_invalid_and_sent_again(world: World) -> None:
    """Scenario: a reply rejects check 2 and gives no reason."""
    bad = reply("moderate", NO_REASON)
    clients = run_round(world, world.round_1, world.inputs, {"M-01": {SECOND: [bad, reply()]}})
    rows = [row for row in rows_of(world.round_1 / f"{SECOND}.jsonl") if row["case_id"] == "M-01"]
    assert [(row["attempt"], row["status"]) for row in rows] == [(1, "invalid"), (2, "valid")]
    assert rows[0]["raw_reply"] == bad and rows[0]["error"] == "check 2: no reason"
    assert len(clients[SECOND].texts) == 5 and clients[SECOND].texts[0] == clients[SECOND].texts[1]
    with pytest.raises(lv.ReplyFormatError, match="check 2: no reason"):
        lv.parse_reply(bad)


def test_a_request_is_sent_three_times_in_all(world: World) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    never = Fake(SECOND, lambda text: "I cannot judge this case.")
    result = v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=never, limit=1)
    assert result == {
        **result,
        "valid": 0,
        "invalid": 1,
        "pending": 3,
        "sent": 3,
        "unavailable": None,
    }
    rows = rows_of(world.round_1 / f"{SECOND}.jsonl")
    assert [(row["case_id"], row["attempt"], row["status"]) for row in rows] == [
        ("M-01", 1, "invalid"),
        ("M-01", 2, "invalid"),
        ("M-01", 3, "invalid"),
    ]
    # A rerun does not send the exhausted request a fourth time; it takes up the next ones.
    again = Fake(SECOND, lambda text: reply("high"))
    result = v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=again)
    assert result == {**result, "valid": 3, "invalid": 1, "pending": 0, "sent": 3}
    assert len(again.texts) == 3 and requests(world)["M-01"] not in again.texts


LEAKY = (
    "POST https://judge.example.invalid/v1 refused the key sk-test-123 of /etc/judge/settings.json"
)


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (JudgeUnavailable("1310", "Judge rejected the request"), "1310"),
        (JudgeUnavailable("credentials", LEAKY), "credentials"),
        (RateLimited(None), "rate_limited"),
        (TransportError(), "transport"),
    ],
)
def test_an_unavailable_verifier_stops_the_run_and_leaves_no_verdict(
    world: World, capsys: pytest.CaptureFixture[str], failure: Exception, code: str
) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    client = Fake(SECOND, failures={2: failure})
    result = v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=client)
    assert result == {**result, "valid": 1, "pending": 3, "sent": 2, "unavailable": code}
    rows = rows_of(world.round_1 / f"{SECOND}.jsonl")
    assert [row["status"] for row in rows] == ["valid", "unavailable"]
    assert rows[1] == {**rows[1], "model": None, "raw_reply": None, "usage": {}, "error": code}
    assert len(client.texts) == 2
    # Only the code of a failure is kept: no address, key or settings path in a store or a log.
    kept = (world.round_1 / f"{SECOND}.jsonl").read_text(encoding="utf-8") + capsys.readouterr().out
    for secret in ("https", "example.invalid", "sk-test-123", "settings.json"):
        assert secret not in kept


def test_a_reply_of_another_model_is_no_verdict(world: World) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    client = Fake("another-model")
    result = v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=client)
    assert result == {
        **result,
        "valid": 0,
        "pending": 4,
        "sent": 1,
        "unavailable": "model_mismatch",
    }
    rows = rows_of(world.round_1 / f"{SECOND}.jsonl")
    assert len(rows) == 1 and rows[0]["status"] == "unavailable"
    assert rows[0]["model"] == "another-model" and rows[0]["raw_reply"] is None
    decided = v.load_round(world.round_1, world.drafts)
    assert {decision["outcome"] for decision in decided.decisions.values()} == {"none"}


def test_limit_takes_up_that_many_requests(world: World) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    client = Fake(OPUS)
    result = v.verify(world.round_1, OPUS, world.drafts, world.inputs, client=client, limit=3)
    assert result == {**result, "valid": 3, "pending": 1, "sent": 3, "unavailable": None}
    result = v.verify(world.round_1, OPUS, world.drafts, world.inputs, client=client, limit=3)
    assert result == {**result, "valid": 4, "pending": 0, "sent": 1}
    assert client.texts == list(requests(world).values())


def test_verify_refuses_inputs_that_no_longer_give_the_plan(world: World) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    client = Fake(SECOND)
    with pytest.raises(ValueError, match="not a verifier of this plan: sonnet"):
        v.verify(world.round_1, "sonnet", world.drafts, world.inputs, client=client)
    path = world.round_1 / "plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    plan["requests"][0]["request_sha256"] = "0" * 64
    path.write_bytes(v.dump(plan))
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan of this round"):
        v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=client)
    assert client.texts == [] and not (world.round_1 / f"{SECOND}.jsonl").exists()


def envelope(**changes: Any) -> str:
    data = {
        "is_error": False,
        "terminal_reason": "completed",
        "result": reply(),
        "usage": {"output_tokens": 11},
        "total_cost_usd": 0.5,
        "modelUsage": {OPUS: {"canonicalModel": OPUS, "provider": "firstParty"}},
        **changes,
    }
    return json.dumps(data)


def test_claude_route_is_a_new_process_with_no_tools_and_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0, stdout=envelope(), stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    client = v.ClaudeCliClient("claude-test")
    first = client.grade("request one")
    client.grade("request two")
    assert first.text == reply() and first.model == OPUS
    assert first.usage == {"output_tokens": 11, "total_cost_usd": 0.5}
    assert [options["input"] for _, options in calls] == ["request one", "request two"]
    command, options = calls[0]
    assert command[0] == "claude-test" and command[1] == "-p"
    assert command[command.index("--model") + 1] == OPUS
    assert command[command.index("--effort") + 1] == "max"
    assert command[command.index("--tools") + 1] == ""
    assert "--no-session-persistence" in command and "--strict-mcp-config" in command
    assert command[command.index("--system-prompt") + 1] == lv.CLI_SYSTEM_PROMPT
    assert "--resume" not in command and "--continue" not in command
    assert options["cwd"] == tempfile.gettempdir() and options["timeout"] == v.CLI_TIMEOUT_S
    settings = lv.VERIFIERS[OPUS]["settings"]
    assert settings["system_prompt_sha256"] == sha(lv.CLI_SYSTEM_PROMPT)
    assert v.ClaudeCliClient.route == lv.VERIFIERS[OPUS]["route"]


@pytest.mark.parametrize(
    "changes",
    [
        {"is_error": True},
        {"terminal_reason": "max_turns"},
        {"modelUsage": {"claude-sonnet-5-5": {"canonicalModel": "claude-sonnet-5-5"}}},
        {"modelUsage": {OPUS: {"canonicalModel": OPUS}, "claude-haiku-4-5": {}}},
        {"modelUsage": {OPUS: {"canonicalModel": "claude-opus-5", "provider": "firstParty"}}},
        {"modelUsage": {OPUS: {"canonicalModel": OPUS, "provider": "bedrock"}}},
        {"result": "  "},
    ],
)
def test_claude_reply_counts_only_from_the_registered_model(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]
) -> None:
    assert v.parse_cli_envelope(envelope(), OPUS)["result"] == reply()
    with pytest.raises(ValueError, match="Claude CLI"):
        v.parse_cli_envelope(envelope(**changes), OPUS)
    with pytest.raises(ValueError, match="did not return JSON"):
        v.parse_cli_envelope("not json", OPUS)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **options: subprocess.CompletedProcess(command, 0, envelope(**changes), ""),
    )
    with pytest.raises(JudgeUnavailable) as caught:
        v.ClaudeCliClient("claude-test").grade("request")
    assert caught.value.code == "cli_response"


def test_claude_route_failures_are_unavailability(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(error: Exception | int) -> Callable[..., subprocess.CompletedProcess[str]]:
        def run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
            if isinstance(error, Exception):
                raise error
            return subprocess.CompletedProcess(command, error, stdout="", stderr="")

        return run

    for error, code in (
        (subprocess.TimeoutExpired("claude", 1.0), "cli_timeout"),
        (FileNotFoundError("claude"), "cli_missing"),
        (3, "cli_exit"),
    ):
        monkeypatch.setattr(subprocess, "run", failing(error))
        with pytest.raises(JudgeUnavailable) as caught:
            v.ClaudeCliClient("claude-test").grade("request")
        assert caught.value.code == code
    monkeypatch.setattr(v.shutil, "which", lambda name: None)
    with pytest.raises(JudgeUnavailable) as caught:
        v.ClaudeCliClient().grade("request")
    assert caught.value.code == "cli_missing"


def test_the_only_route_is_the_registered_verifier(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], one_voice: None
) -> None:
    monkeypatch.setenv("RAG_VERIFY_CLAUDE_CLI", "claude-test")
    claude = v.make_client(OPUS)
    assert isinstance(claude, v.ClaudeCliClient) and claude.executable == "claude-test"
    # No model of another vendor can be called: none has a route (plan decision D12).
    for name in ("glm-5.3", "gpt-6.1-sol", "sonnet", SECOND):
        with pytest.raises(ValueError, match="no route is registered"):
            v.make_client(name)
    assert not hasattr(v, "GlmClient")
    assert capsys.readouterr().out == ""


# --- the reply form ------------------------------------------------------------------------


def test_reply_form_of_the_protocol() -> None:
    verdict = lv.parse_reply(reply("high", {"5a": {"verdict": "unverifiable"}, **REJECT_3}))
    assert verdict["3"] == {
        "verdict": "reject",
        "reason": "The answer leaves out the deadline.",
        "element": "F1",
    }
    assert verdict["5a"] == {"verdict": "unverifiable", "reason": "Check 5a holds."}
    assert verdict["5c"] == {"level": "high", "reason": "The level fits the scale."}
    assert verdict["2"] == {"verdict": "confirm", "reason": "Check 2 holds.", "element": None}
    assert list(verdict) == list(lv.CHECKS)
    # Text around the one object and the case of a word do not make a reply invalid.
    fenced = "Here it is:\n```json\n" + reply("high").replace('"confirm"', '"Confirm"') + "\n```\n"
    assert lv.parse_reply(fenced)["2"]["verdict"] == "confirm"
    assert lv.parse_reply(reply("high", {"5c": {"level": " High ", "reason": None}}))["5c"] == {
        "level": "high",
        "reason": None,
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (reply("moderate", NO_REASON), "check 2: no reason"),
        (reply("moderate", {"2": {"reason": "  "}}), "check 2: no reason"),
        (reply("moderate", {"5b": {"reason": None}}), "check 5b: no reason"),
        (reply("moderate", {"3": {"verdict": "reject", "element": None}}), "names no element"),
        (reply("moderate", {"4": {"verdict": "unverifiable"}}), "check 4: the verdict is not one"),
        (reply("moderate", {"5d": {"verdict": "yes"}}), "check 5d: the verdict is not one"),
        (reply("moderate", {"5a": {"verdict": "maybe"}}), "check 5a: the verdict is not one"),
        (reply("severe"), "check 5c: no level of the scale"),
        (reply("moderate", {"5c": {"level": 3}}), "check 5c: no level of the scale"),
        (json.dumps({"2": {"verdict": "confirm", "reason": "ok"}}), "check 3: no answer"),
        (json.dumps({**json.loads(reply()), "5d": "confirm"}), "check 5d: no answer"),
        (reply() + "\n" + reply(), "not one JSON object keyed by the checks"),
        ("I cannot judge this case.", "not one JSON object keyed by the checks"),
        ('{"verdict": "confirm"}', "not one JSON object keyed by the checks"),
        (reply()[:-1] + ', "2": {"verdict": "reject", "reason": "x", "element": "F1"}}', "twice"),
    ],
)
def test_a_reply_in_another_form_is_invalid(text: str, message: str) -> None:
    with pytest.raises(lv.ReplyFormatError, match=message):
        lv.parse_reply(text)


# --- the decision --------------------------------------------------------------------------


def verdicts(first: str, second: str | None) -> dict[str, dict[str, dict[str, Any]] | None]:
    return {SECOND: lv.parse_reply(first), OPUS: lv.parse_reply(second) if second else None}


def test_decision_follows_the_order_of_the_protocol() -> None:
    confirmed = lv.decide("moderate", verdicts(reply(), reply()))
    assert confirmed == {
        "outcome": "confirmed",
        "missing": [],
        "authority_unverified": False,
        "rejecting_checks": [],
        "disagreements": [],
        "severity_differences": [],
    }
    # `none` comes first: one valid verdict decides nothing, whatever it says.
    lone = lv.decide("moderate", verdicts(reply("moderate", REJECT_3), None))
    assert lone["outcome"] == "none" and lone["missing"] == [OPUS]
    assert lone["rejecting_checks"] == []
    failed = lv.decide("moderate", verdicts(reply(), reply()), check_1=False)
    assert failed["outcome"] == "rejected"
    assert failed["rejecting_checks"] == [{"check": "1", "verdicts": {}}]
    for check in ("2", "4", "5d", "5a", "5b"):
        change = {check: {"verdict": "reject", "reason": "It does not hold.", "element": "S1"}}
        decision = lv.decide("moderate", verdicts(reply(), reply("moderate", change)))
        assert decision["outcome"] == "rejected" and not decision["authority_unverified"]
        assert [item["check"] for item in decision["rejecting_checks"]] == [check]
    with pytest.raises(ValueError, match="at least one verifier"):
        lv.decide("moderate", {})
    with pytest.raises(ValueError, match="not on the scale"):
        lv.decide("severe", verdicts(reply(), reply()))


def test_the_verifiers_disagree() -> None:
    """Scenario: one verifier confirms every check, the other rejects check 3."""
    decision = lv.decide("moderate", verdicts(reply(), reply("moderate", REJECT_3)))
    assert decision["outcome"] == "rejected"
    assert decision["disagreements"] == [
        {"check": "3", "answers": {OPUS: "reject", SECOND: "confirm"}}
    ]
    assert decision["rejecting_checks"] == [
        {
            "check": "3",
            "verdicts": {
                OPUS: {
                    "verdict": "reject",
                    "reason": "The answer leaves out the deadline.",
                    "element": "F1",
                },
                SECOND: {"verdict": "confirm", "reason": "Check 3 holds.", "element": None},
            },
        }
    ]


def test_currency_cannot_be_read_from_the_corpus() -> None:
    """Scenario: every check confirmed except 5a, where one verifier answers unverifiable."""
    unverifiable = reply("moderate", {"5a": {"verdict": "unverifiable", "reason": "No date."}})
    decision = lv.decide("moderate", verdicts(unverifiable, reply()))
    assert decision["outcome"] == "confirmed" and decision["authority_unverified"] is True
    assert decision["disagreements"] == [
        {"check": "5a", "answers": {OPUS: "confirm", SECOND: "unverifiable"}}
    ]
    for check in lv.AUTHORITY_CHECKS:
        both = reply("moderate", {check: {"verdict": "unverifiable"}})
        assert lv.decide("moderate", verdicts(both, both))["authority_unverified"] is True


def test_severity_differs_by_one_step() -> None:
    """Scenario: a case registered moderate that one verifier calls high."""
    decision = lv.decide("moderate", verdicts(reply("high"), reply("moderate")))
    assert decision["outcome"] == "confirmed"
    assert decision["severity_differences"] == [
        {
            "verifier": SECOND,
            "registered": "moderate",
            "named": "high",
            "steps": 1,
            "crosses_critical": False,
        }
    ]
    assert decision["disagreements"] == [
        {"check": "5c", "answers": {OPUS: "moderate", SECOND: "high"}}
    ]


def test_severity_crosses_the_critical_boundary() -> None:
    """Scenario: a case registered high that both verifiers call critical."""
    decision = lv.decide("high", verdicts(reply("critical"), reply("critical")))
    assert decision["outcome"] == "rejected"
    assert [item["check"] for item in decision["rejecting_checks"]] == ["5c"]
    assert decision["rejecting_checks"][0]["verdicts"][SECOND]["level"] == "critical"
    assert decision["disagreements"] == []
    assert all(item["crosses_critical"] for item in decision["severity_differences"])


@pytest.mark.parametrize(
    ("registered", "named", "outcome"),
    [
        ("low", "low", "confirmed"),
        ("low", "moderate", "confirmed"),
        ("moderate", "low", "confirmed"),
        ("high", "moderate", "confirmed"),
        ("low", "high", "rejected"),
        ("high", "low", "rejected"),
        ("low", "critical", "rejected"),
        ("critical", "high", "rejected"),
        ("high", "critical", "rejected"),
        ("critical", "critical", "confirmed"),
    ],
)
def test_severity_rule(registered: str, named: str, outcome: str) -> None:
    decision = lv.decide(registered, verdicts(reply(registered), reply(named)))
    assert decision["outcome"] == outcome


def test_case_state_over_the_rounds() -> None:
    assert lv.case_state("confirmed") == "verified"
    assert lv.case_state("rejected", "confirmed") == "verified"
    assert lv.case_state("rejected", "rejected") == "dropped"
    assert lv.case_state("rejected", declared_drop=True) == "dropped"
    assert lv.case_state("rejected") == "repair_pending"
    assert lv.case_state("rejected", "none") == "repair_pending"
    assert lv.case_state("none") == lv.case_state(None) == "unverified"
    assert lv.case_state("none", declared_drop=True) == "unverified"


def test_decide_recomputes_the_round_and_prints_the_reasons_of_both(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reject_m02(world, {"M-04": {OPUS: reply("critical", {"5b": {"verdict": "unverifiable"}})}})
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    capsys.readouterr()
    assert v.main(world.arguments("decide", "--round=1")) == 0
    printed = capsys.readouterr().out
    assert "M-02: rejected\n  check 3\n" in printed
    assert f"    {SECOND}: reject [F1] - The answer leaves out the deadline." in printed
    assert f"    {OPUS}: confirm - Check 3 holds." in printed
    assert json.loads(printed.strip().split("\n")[-1]) == {
        "round": 1,
        "confirmed": 3,
        "rejected": 1,
        "none": 0,
        "declared_drops": 0,
    }
    stored = json.loads((world.round_1 / "decisions.json").read_text(encoding="utf-8"))
    by_case = {item["case_id"]: item for item in stored["cases"]}
    assert stored["plan_sha256"] == sha((world.round_1 / "plan.json").read_bytes())
    assert stored["stores_sha256"][SECOND] == sha((world.round_1 / f"{SECOND}.jsonl").read_bytes())
    assert by_case["M-02"]["outcome"] == "rejected" and by_case["M-01"]["outcome"] == "confirmed"
    assert by_case["M-04"]["authority_unverified"] is True
    assert (
        by_case["M-02"]["verdicts"][SECOND]["3"]["reason"] == "The answer leaves out the deadline."
    )
    # The decision is the rule over the raw replies: the same stores give the same bytes.
    before = (world.round_1 / "decisions.json").read_bytes()
    v.decide(world.round_1, world.drafts)
    assert (world.round_1 / "decisions.json").read_bytes() == before


def test_decide_reports_a_round_that_is_not_decided(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    v.plan_round(world.round_1, world.drafts, world.inputs)
    v.verify(world.round_1, SECOND, world.drafts, world.inputs, client=Fake(SECOND))
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    capsys.readouterr()
    assert v.main(world.arguments("decide", "--round=1")) == 1
    assert json.loads(capsys.readouterr().out.strip().split("\n")[-1])["none"] == 4


@pytest.mark.parametrize(
    "change",
    [
        {"request_sha256": "0" * 64},
        {"prompt_sha256": "0" * 64},
        {"rubric_version": "label-verification/v0"},
        {"case_id": "M-99"},
        {"verifier": OPUS},
        {"case_id": ["M-02"]},
        {"round": 2},
        {"status": "confirmed"},
    ],
)
def test_decide_refuses_a_store_of_another_request_prompt_or_rubric(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: dict[str, Any],
) -> None:
    run_round(world, world.round_1, world.inputs)
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    path = world.round_1 / f"{SECOND}.jsonl"
    rows = rows_of(path)
    rows[1].update(change)
    path.write_bytes(v.jsonl(rows))
    with pytest.raises(ValueError, match="holds a row that is not of this plan"):
        v.decide(world.round_1, world.drafts)
    assert v.main(world.arguments("decide", "--round=1")) == 2
    assert f"refused: the store of {SECOND}" in capsys.readouterr().out
    assert not (world.round_1 / "decisions.json").exists()


def test_a_stored_verdict_counts_only_while_its_raw_reply_follows_the_form(world: World) -> None:
    run_round(world, world.round_1, world.inputs)
    path = world.round_1 / f"{SECOND}.jsonl"
    rows = rows_of(path)
    rows[0]["raw_reply"] = reply("moderate", NO_REASON)
    path.write_bytes(v.jsonl(rows))
    with pytest.raises(ValueError, match="a stored verdict does not follow the form: M-01"):
        v.decide(world.round_1, world.drafts)
    rows[0]["raw_reply"] = reply()
    rows[0]["model"] = "another-model"
    path.write_bytes(v.jsonl(rows))
    with pytest.raises(ValueError, match="a stored verdict is not of the registered model: M-01"):
        v.decide(world.round_1, world.drafts)


# --- the verified set and its register -----------------------------------------------------


def outputs(world: World) -> tuple[Path, Path]:
    return world.root / "verified.jsonl", world.root / "label_checks.json"


def apply(world: World, repairs: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    verified, register = outputs(world)
    v.apply(
        world.drafts,
        world.round_1,
        world.round_2,
        repairs=repairs,
        verified=verified,
        register=register,
    )
    return rows_of(verified), json.loads(register.read_text(encoding="utf-8"))


def check(
    world: World, repairs: Path | None = None, inputs: v.RoundInputs | None = None
) -> dict[str, Any]:
    verified, register = outputs(world)
    return v.check(
        world.drafts,
        world.round_1,
        world.round_2,
        repairs=repairs,
        verified=verified,
        register=register,
        inputs=inputs,
    )


def two_rounds(world: World) -> Path:
    """M-01 confirmed, M-02 rejected then repaired and confirmed, M-03 dropped by its author,
    M-04 confirmed with one severity step and an unverifiable authority."""
    reject_m02(
        world,
        {
            "M-03": {OPUS: reply("moderate", REJECT_3)},
            "M-04": {
                SECOND: reply("critical", {"5a": {"verdict": "unverifiable", "reason": "No date."}})
            },
        },
    )
    repairs = world.write("repairs.jsonl", [repaired_m02()])
    drops = world.write(
        "drops.json", [{"case_id": "M-03", "ground": "repair_needs_reserve", "documents": [DELTA]}]
    )
    inputs = replace(world.second, repairs=repairs, drops=drops)
    run_round(world, world.round_2, inputs, {"M-02": {OPUS: reply("moderate")}})
    return repairs


def test_verified_set_and_register_follow_from_the_decisions(world: World) -> None:
    repairs = two_rounds(world)
    rows, register = apply(world, repairs)
    author = {"model": "gpt-6.1-sol", "vendor": "OpenAI"}
    label = {
        "status": "model_verified",
        "verifiers": [OPUS, SECOND],
        "rubric_version": lv.RUBRIC_VERSION,
    }
    assert [row["case_id"] for row in rows] == ["M-01", "M-02", "M-04"]
    assert rows[0] == {
        **world.drafts.cases[0],
        "draft_author": author,
        "label_check": {**label, "round": 1},
        "authority_unverified": False,
    }
    # The repaired case is written in the revision its verdicts were given on.
    assert rows[1] == {
        **repaired_m02(),
        "draft_author": author,
        # The verdicts of round 2 were given on a label the verifier's own model wrote.
        "label_check": {**label, "round": 2, "repair_author": REPAIRER},
        "authority_unverified": False,
    }
    assert (
        rows[2]["label_check"] == {**label, "round": 1} and rows[2]["authority_unverified"] is True
    )
    assert {row["label_origin"] for row in rows} == {"agent_labelled"}
    assert register["label_origin"] == "agent_labelled"
    assert register["rubric_version"] == lv.RUBRIC_VERSION
    assert register["prompt_sha256"] == lv.PROMPT_SHA256 and register["draft_author"] == author
    assert register["repair_author"] == REPAIRER
    entries = {entry["case_id"]: entry for entry in register["cases"]}
    assert [entry["state"] for entry in register["cases"]] == [
        "verified",
        "verified",
        "dropped",
        "verified",
    ]
    repaired = entries["M-02"]
    assert repaired["rounds"]["1"]["outcome"] == "rejected"
    assert repaired["rounds"]["2"]["outcome"] == "confirmed"
    assert repaired["rounds"]["1"]["verdicts"][SECOND]["3"] == {
        "verdict": "reject",
        "reason": "The answer leaves out the deadline.",
        "element": "F1",
    }
    assert set(repaired["rounds"]["2"]["verdicts"][OPUS]) == set(lv.CHECKS)
    assert repaired["draft_sha256"] == lv.case_sha256(world.drafts.cases[1])
    assert repaired["repair"] == {
        "case_sha256": lv.case_sha256(repaired_m02()),
        "documents": [BETA],
        "families": ["family-b"],
    }
    assert (repaired["drafted_class"], repaired["class"]) == ("multi-doc", "single-doc")
    assert entries["M-03"]["drop"] == {"ground": "repair_needs_reserve", "documents": [DELTA]}
    assert entries["M-03"]["label_check"] is None and entries["M-03"]["repair"] is None
    assert entries["M-01"]["repair"] is None and entries["M-01"]["drop"] is None
    summary = register["summary"]
    assert summary["first_check_rejection_by_drafted_class"] == {
        "multi-doc": {"drafted": 2, "decided": 2, "rejected": 1, "share_rejected": 0.5},
        "needs-refusal/clarification": {
            "drafted": 1,
            "decided": 1,
            "rejected": 1,
            "share_rejected": 1.0,
        },
        "single-doc": {"drafted": 1, "decided": 1, "rejected": 0, "share_rejected": 0.0},
    }
    assert summary["repaired_cases"] == [
        {"case_id": "M-02", "class_before": "multi-doc", "class_after": "single-doc"}
    ]
    assert summary["verified_by_class"] == {"multi-doc": 1, "single-doc": 2}
    assert summary["verified_after_repair"] == ["M-02"]
    assert {
        "case_id": "M-02",
        "round": 1,
        "check": "3",
        "answers": {OPUS: "confirm", SECOND: "reject"},
    } in (summary["verifier_disagreements"])
    assert summary["severity_differences"] == [
        {
            "case_id": "M-02",
            "round": 2,
            "verifier": OPUS,
            "registered": "high",
            "named": "moderate",
            "steps": 1,
            "crosses_critical": False,
        }
    ]
    assert summary["authority_unverified"] == ["M-04"]
    assert summary["dropped"] == [
        {"case_id": "M-03", "ground": "repair_needs_reserve", "documents": [DELTA]}
    ]
    assert summary["safety_critical"] == {"verified": 1, "verified_without_authority_unverified": 0}
    assert summary["states"] == {"verified": 3, "repair_pending": 0, "dropped": 1, "unverified": 0}
    assert register["complete"] is True and summary["complete"] is True
    plans = {
        name: json.loads((path / "plan.json").read_text(encoding="utf-8"))
        for name, path in (("1", world.round_1), ("2", world.round_2))
    }
    characters = sum(row["characters"] for plan in plans.values() for row in plan["requests"])
    texts = sum(row["corpus_texts"] for plan in plans.values() for row in plan["requests"])
    assert register["sent"] == {
        name: {"requests": 5, "attempts": 5, "characters": characters, "corpus_texts": texts}
        for name in (OPUS, SECOND)
    }
    shas = register["sha256"]
    assert shas["drafts"] == world.drafts.manifest["jsonl_sha256"]
    assert shas["scan"] == sha(world.inputs.scan.read_bytes()) and shas["archive"] == sha(ARCHIVE)
    assert shas["plans"] == {
        "1": sha((world.round_1 / "plan.json").read_bytes()),
        "2": sha((world.round_2 / "plan.json").read_bytes()),
    }
    assert shas["stores"]["2"][OPUS] == sha((world.round_2 / f"{OPUS}.jsonl").read_bytes())
    assert shas["repairs"] == sha(repairs.read_bytes())
    assert shas["verified_set"] == sha(outputs(world)[0].read_bytes())
    assert check(world, repairs) == {
        "status": "ok",
        "cases": 4,
        "states": summary["states"],
        "verified_by_class": {"multi-doc": 1, "single-doc": 2},
        "authority_unverified": 1,
        "safety_critical": summary["safety_critical"],
        "complete": True,
    }


def test_a_case_that_only_a_reserve_document_could_repair(world: World) -> None:
    """Scenario: rejected in round 1, dropped by its author with one reserve document."""
    reject_m02(world)
    drops = world.write(
        "drops.json", [{"case_id": "M-02", "ground": "repair_needs_reserve", "documents": [DELTA]}]
    )
    clients = run_round(world, world.round_2, replace(world.second, drops=drops))
    assert clients[SECOND].texts == [] and clients[OPUS].texts == []
    assert v.decide(world.round_2, world.drafts)[0] == {
        "round": 2,
        "confirmed": 0,
        "rejected": 0,
        "none": 0,
        "declared_drops": 1,
    }
    rows, register = apply(world)
    entry = register["cases"][1]
    assert [row["case_id"] for row in rows] == ["M-01", "M-03", "M-04"]
    assert entry["state"] == "dropped" and "2" not in entry["rounds"]
    assert entry["drop"] == {"ground": "repair_needs_reserve", "documents": [DELTA]}
    assert register["complete"] is True
    assert check(world)["complete"] is True


def test_a_second_rejection_drops_the_case_with_its_rejecting_checks(world: World) -> None:
    reject_m02(world)
    repairs = world.write("repairs.jsonl", [repaired_m02()])
    inputs = replace(world.second, repairs=repairs)
    run_round(
        world,
        world.round_2,
        inputs,
        {"M-02": {SECOND: reply("low"), OPUS: reply("high", REJECT_3)}},
    )
    rows, register = apply(world, repairs)
    entry = register["cases"][1]
    assert "M-02" not in [row["case_id"] for row in rows]
    assert entry["state"] == "dropped"
    assert entry["drop"] == {"ground": "rejected_in_round_2", "rejecting_checks": ["3", "5c"]}
    assert entry["repair"]["case_sha256"] == lv.case_sha256(repaired_m02())
    assert register["complete"] is True and check(world, repairs)["status"] == "ok"


def test_a_case_seen_by_one_verifier(world: World) -> None:
    """Scenario: a valid verdict of one verifier only."""
    silent = ["no verdict"] * 3
    run_round(world, world.round_1, world.inputs, {"M-01": {OPUS: silent}})
    rows, register = apply(world)
    assert rows[0] == {
        **world.drafts.cases[0],
        "draft_author": {"model": "gpt-6.1-sol", "vendor": "OpenAI"},
        "label_check": {"status": "none"},
        "authority_unverified": False,
    }
    entry = register["cases"][0]
    assert entry["state"] == "unverified" and entry["rounds"]["1"]["outcome"] == "none"
    assert entry["rounds"]["1"]["missing"] == [OPUS]
    assert entry["rounds"]["1"]["verdicts"][OPUS] is None
    assert register["complete"] is False
    assert register["sent"][OPUS] == {**register["sent"][OPUS], "requests": 4, "attempts": 6}
    assert check(world)["complete"] is False


def test_a_case_waiting_for_its_repair(world: World) -> None:
    """Scenario: rejected in round 1 and no round 2 yet."""
    reject_m02(world)
    rows, register = apply(world)
    assert rows[1] == {
        **world.drafts.cases[1],
        "draft_author": {"model": "gpt-6.1-sol", "vendor": "OpenAI"},
        "label_check": {"status": "none"},
        "authority_unverified": False,
    }
    assert register["cases"][1]["state"] == "repair_pending"
    assert register["complete"] is False and register["sha256"]["plans"] == {
        "1": sha((world.round_1 / "plan.json").read_bytes())
    }
    # A round 2 that gives the case in neither form leaves it waiting, and so does a repair
    # that one verifier has not answered yet.
    repairs = world.write("repairs.jsonl", [repaired_m02()])
    inputs = replace(world.second, repairs=repairs)
    v.plan_round(world.round_2, world.drafts, inputs)
    v.verify(
        world.round_2, SECOND, world.drafts, inputs, client=Fake(SECOND, lambda text: reply("high"))
    )
    rows, register = apply(world, repairs)
    assert rows[1]["label_check"] == {"status": "none"}
    assert {key: rows[1][key] for key in world.drafts.cases[1]} == world.drafts.cases[1]
    assert register["cases"][1]["state"] == "repair_pending"
    assert register["cases"][1]["rounds"]["2"]["outcome"] == "none"
    assert check(world, repairs)["states"]["repair_pending"] == 1


def test_same_inputs_give_the_same_bytes_and_the_drafts_stay(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repairs = two_rounds(world)
    verified, register = outputs(world)
    apply(world, repairs)
    first = verified.read_bytes(), register.read_bytes()
    apply(world, repairs)
    assert (verified.read_bytes(), register.read_bytes()) == first
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    capsys.readouterr()
    arguments = [f"--verified={verified}", f"--register={register}"]
    assert v.main(world.arguments("apply", f"--repairs={repairs}", *arguments)) == 0
    assert (verified.read_bytes(), register.read_bytes()) == first
    assert v.main(world.arguments("check", f"--repairs={repairs}", *arguments)) == 0
    assert json.loads(capsys.readouterr().out.strip().split("\n")[-1])["status"] == "ok"
    # With --rebuild both plans are built again from the corpus, the scan, the repairs and the
    # declared drops; without the drops the plan of round 2 is not the one they give.
    rebuild = ["--rebuild", f"--repairs={repairs}", *arguments]
    assert v.main(world.arguments("check", *rebuild, f"--drops={world.root / 'drops.json'}")) == 0
    assert json.loads(capsys.readouterr().out.strip().split("\n")[-1])["status"] == "ok"
    assert v.main(world.arguments("check", *rebuild)) == 2
    assert "refused: the inputs no longer rebuild the plan of round 2" in capsys.readouterr().out
    # Round 2 checked a repaired case: neither command reads it without the repairs.
    assert v.main(world.arguments("check", *arguments)) == 2
    assert v.main(world.arguments("decide", "--round=2")) == 2
    assert capsys.readouterr().out.count("name their file with --repairs") == 2
    assert v.main(world.arguments("decide", "--round=2", f"--repairs={repairs}")) == 0
    # Neither output may be one of the drafts' own files.
    before = [path.read_bytes() for path in v.PROTECTED]
    for protected in v.PROTECTED:
        for targets in (
            {"verified": protected, "register": register},
            {"verified": verified, "register": protected},
        ):
            with pytest.raises(ValueError, match="do not replace the drafts"):
                v.apply(world.drafts, world.round_1, world.round_2, repairs=repairs, **targets)
    assert [path.read_bytes() for path in v.PROTECTED] == before
    with pytest.raises(ValueError, match="name their file with --repairs"):
        apply(world)
    other = world.write("other.jsonl", [repaired_m02(), world.drafts.cases[0]])
    with pytest.raises(ValueError, match="not the one round 2 was planned on"):
        apply(world, other)


def rewrite(world: World, change: Callable[[list[dict[str, Any]]], None]) -> None:
    path = outputs(world)[0]
    rows = rows_of(path)
    change(rows)
    path.write_bytes(v.jsonl(rows))


def promote(rows: list[dict[str, Any]]) -> None:
    rows[1]["label_check"] = {**rows[0]["label_check"]}


def edit_verified(rows: list[dict[str, Any]]) -> None:
    rows[0]["reference_answer"] += " И сверяется с накладной."


def edit_unverified(rows: list[dict[str, Any]]) -> None:
    rows[1]["wrong_answer_severity"] = "moderate"


def unknown_case(rows: list[dict[str, Any]]) -> None:
    rows.append({**rows[0], "case_id": "M-99"})


def repeated_case(rows: list[dict[str, Any]]) -> None:
    rows.append(rows[0])


def nameless_case(rows: list[dict[str, Any]]) -> None:
    rows.append({**rows[0], "case_id": ["M-01"]})


def lose_a_case(rows: list[dict[str, Any]]) -> None:
    del rows[2]


def clear_the_flag(rows: list[dict[str, Any]]) -> None:
    rows[3]["authority_unverified"] = False


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (promote, "not confirmed by a valid verdict of every verifier: M-02"),
        (edit_verified, "a verified case is not the revision its verdicts were given on: M-01"),
        (edit_unverified, "an unrepaired case differs from its draft: M-02"),
        (unknown_case, "the verified set holds an unknown or repeated case: M-99"),
        (repeated_case, "the verified set holds an unknown or repeated case: M-01"),
        (lose_a_case, "the verified set is not what the decisions give"),
        (clear_the_flag, "the verified set is not what the decisions give"),
        (nameless_case, "the verified set holds an unknown or repeated case"),
    ],
)
def test_check_refuses_a_verified_set_that_differs(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: Callable[[list[dict[str, Any]]], None],
    message: str,
) -> None:
    reject_m02(world, {"M-04": {SECOND: reply("critical", {"5b": {"verdict": "unverifiable"}})}})
    apply(world)
    assert check(world)["status"] == "ok"
    rewrite(world, change)
    with pytest.raises(ValueError, match=message):
        check(world)
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    verified, register = outputs(world)
    assert v.main(world.arguments("check", f"--verified={verified}", f"--register={register}")) == 2
    assert "refused: " in capsys.readouterr().out


def test_check_refuses_a_register_that_differs(world: World) -> None:
    run_round(world, world.round_1, world.inputs)
    apply(world)
    path = outputs(world)[1]
    register = json.loads(path.read_text(encoding="utf-8"))
    register["complete"] = False
    path.write_bytes(v.dump(register))
    with pytest.raises(ValueError, match="the register is not what the decisions give"):
        check(world)


def test_check_refuses_a_dropped_case_still_present(world: World) -> None:
    repairs = two_rounds(world)
    apply(world, repairs)
    rewrite(
        world,
        lambda rows: rows.insert(
            2,
            {
                **world.drafts.cases[2],
                **{
                    "draft_author": rows[0]["draft_author"],
                    "label_check": {"status": "none"},
                    "authority_unverified": False,
                },
            },
        ),
    )
    with pytest.raises(ValueError, match="a dropped case is still present: M-03"):
        check(world, repairs)


def replan(world: World, change: Callable[[dict[str, Any]], Any], out: Path | None = None) -> None:
    """Rewrite a plan by hand, as no command would: the one of round 2 unless another is named."""
    path = (out or world.round_2) / "plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    change(plan)
    path.write_bytes(v.dump(plan))


def forge_repair(world: World, fixed: dict[str, Any]) -> Path:
    """Put another revision of M-02 into a repairs file and make the plan of round 2 name it."""
    forged = world.write("forged.jsonl", [fixed])
    families = devset.document_families(REGISTER)

    def forge(plan: dict[str, Any]) -> None:
        plan["requests"][0].update(v.planned_fields(fixed, families))
        plan["inputs"]["repairs_sha256"] = sha(forged.read_bytes())

    replan(world, forge)
    return forged


def test_check_refuses_a_declared_drop_that_round_1_does_not_support(world: World) -> None:
    repairs = two_rounds(world)
    apply(world, repairs)
    original = (world.round_2 / "plan.json").read_bytes()
    replan(world, lambda plan: plan["declared_drops"][0].update(documents=[DELTA, ALPHA]))
    with pytest.raises(ValueError, match="names a document outside the holdout reserve: M-03"):
        check(world, repairs)
    (world.round_2 / "plan.json").write_bytes(original)
    replan(world, lambda plan: plan["declared_drops"][0].update(case_id="M-01"))
    with pytest.raises(ValueError, match="a case was not rejected in round 1: M-01"):
        check(world, repairs)
    (world.round_2 / "plan.json").write_bytes(original)
    replan(world, lambda plan: plan["inputs"].update(previous_plan_sha256="0" * 64))
    with pytest.raises(ValueError, match="the plan of round 2 is not planned on round 1"):
        check(world, repairs)
    (world.round_2 / "plan.json").write_bytes(original)
    assert check(world, repairs)["status"] == "ok"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (change_question, "a repair changes question: M-02"),
        (reach_into_reserve, "a repair cites the holdout reserve: 04_delta_reserve.md: M-02"),
        (break_case_rule, r"a repair fails the rules of the verify script \(severity enum\): M-02"),
    ],
)
def test_no_command_reads_a_repair_that_is_not_one(
    world: World, change: Callable[[dict[str, Any]], None], message: str
) -> None:
    """A set, a plan and a repairs file rewritten together: they agree, the repair is not one."""
    repairs = two_rounds(world)
    apply(world, repairs)
    fixed = repaired_m02()
    change(fixed)
    forged = forge_repair(world, fixed)
    rewrite(world, lambda rows: rows[1].update(fixed))
    reads: list[Callable[[], object]] = [
        lambda: check(world, forged),
        lambda: apply(world, forged),
        lambda: v.decide(world.round_2, world.drafts, forged),
    ]
    for read in reads:
        with pytest.raises(ValueError, match=message):
            read()


PLAN_ROW_CHANGES: list[dict[str, Any]] = [
    {"registered_severity": "critical"},
    {"primary_class": "single-doc"},
    {"safety_critical": True},
    {"documents": [BETA]},
    {"families": ["family-a"]},
    {"check_1": "failed"},
    {"case_sha256": "0" * 64},
]


@pytest.mark.parametrize("change", PLAN_ROW_CHANGES)
def test_a_row_of_a_plan_is_not_taken_on_its_word(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: dict[str, Any],
) -> None:
    """Both verifiers name `critical` for a case registered `high`: the case is rejected, and a
    severity rewritten in the plan does not turn the rejection into a confirmation."""
    run_round(
        world,
        world.round_1,
        world.inputs,
        {"M-02": {SECOND: reply("critical"), OPUS: reply("critical")}},
    )
    assert v.load_round(world.round_1, world.drafts).decisions["M-02"]["outcome"] == "rejected"
    apply(world)
    replan(world, lambda plan: plan["requests"][1].update(change), world.round_1)
    message = "the plan of round 1 is not of these drafts: M-02"
    reads: list[Callable[[], object]] = [
        lambda: v.decide(world.round_1, world.drafts),
        lambda: apply(world),
        lambda: check(world),
    ]
    for read in reads:
        with pytest.raises(ValueError, match=message):
            read()
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    capsys.readouterr()
    assert v.main(world.arguments("decide", "--round=1")) == 2
    assert capsys.readouterr().out.strip() == f"refused: {message}"
    assert not (world.round_1 / "decisions.json").exists()


def test_a_plan_of_another_author_or_other_verifiers_is_not_read(world: World) -> None:
    run_round(world, world.round_1, world.inputs)
    original = (world.round_1 / "plan.json").read_bytes()
    changes: list[Callable[[dict[str, Any]], Any]] = [
        lambda plan: plan["verifiers"][SECOND].update(model="another-model"),
        lambda plan: plan["verifiers"].pop(OPUS),
        lambda plan: plan["draft_author"].update(vendor="Anthropic"),
    ]
    for change in changes:
        replan(world, change, world.round_1)
        message = "the plan is not of the registered draft author and verifiers"
        with pytest.raises(ValueError, match=message):
            v.decide(world.round_1, world.drafts)
        (world.round_1 / "plan.json").write_bytes(original)
    replan(world, lambda plan: plan.update(verifiers=[SECOND, OPUS]), world.round_1)
    with pytest.raises(ValueError, match="plan.json does not hold a plan"):
        v.decide(world.round_1, world.drafts)
    (world.round_1 / "plan.json").write_bytes(original)
    assert v.decide(world.round_1, world.drafts)[0]["confirmed"] == 4


@pytest.mark.parametrize(
    "change",
    [
        {"registered_severity": "moderate"},
        {"primary_class": "multi-doc"},
        {"documents": [ALPHA, BETA]},
        {"case_sha256": "0" * 64},
    ],
)
def test_a_row_of_the_plan_of_round_2_is_held_against_the_repairs(
    world: World, change: dict[str, Any]
) -> None:
    repairs = two_rounds(world)
    apply(world, repairs)
    replan(world, lambda plan: plan["requests"][0].update(change))
    message = "the plan of round 2 is not of the repairs it was planned on: M-02"
    reads: list[Callable[[], object]] = [
        lambda: v.decide(world.round_2, world.drafts, repairs),
        lambda: apply(world, repairs),
        lambda: check(world, repairs),
    ]
    for read in reads:
        with pytest.raises(ValueError, match=message):
            read()


def test_check_rebuilds_every_plan_from_its_inputs(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repairs file and a plan row rewritten together name a revision that is a repair, so the
    rows agree; only the rebuild tells that the stored verdicts answered another request."""
    repairs = two_rounds(world)
    apply(world, repairs)
    inputs = replace(world.second, drops=world.root / "drops.json")
    assert check(world, repairs, inputs)["status"] == "ok"
    forged = forge_repair(world, {**repaired_m02(), "wrong_answer_severity": "moderate"})
    rows, _ = apply(world, forged)
    assert rows[1]["wrong_answer_severity"] == "moderate"
    assert rows[1]["label_check"]["status"] == "model_verified"
    assert check(world, forged)["status"] == "ok"
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan of round 2"):
        check(world, forged, inputs)
    # The declared drops are an input of round 2 as well.
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan of round 2"):
        check(world, forged, world.second)
    monkeypatch.setattr(v, "pilot_drafts", lambda: world.drafts)
    verified, register = outputs(world)
    arguments = [f"--verified={verified}", f"--register={register}", f"--repairs={forged}"]
    capsys.readouterr()
    assert v.main(world.arguments("check", *arguments)) == 0
    rebuild = ["--rebuild", f"--drops={world.root / 'drops.json'}"]
    assert v.main(world.arguments("check", *arguments, *rebuild)) == 2
    printed = capsys.readouterr().out.strip().split("\n")
    assert printed[-1] == "refused: the inputs no longer rebuild the plan of round 2"
    # Round 1 is rebuilt first: a corpus that is not the registered one stops the check there.
    other = replace(inputs, corpus_dir=world.root)
    with pytest.raises(ValueError, match="the corpus is not the registered version"):
        check(world, forged, other)


def test_set_level_rules_of_the_drafts_do_not_bind_the_verified_set(world: World) -> None:
    repairs = two_rounds(world)
    rows, register = apply(world, repairs)
    # Three of four drafts remain and a class changed: no quota, count or file SHA is checked.
    assert (
        len(rows) == 3
        and sha(outputs(world)[0].read_bytes()) != world.drafts.manifest["jsonl_sha256"]
    )
    report = check(world, repairs)
    assert report["verified_by_class"] == {"multi-doc": 1, "single-doc": 2} and report["cases"] == 4
    with pytest.raises(ValueError, match="the plan of round 1 is not of these drafts"):
        other = replace(world.drafts, manifest={**world.drafts.manifest, "jsonl_sha256": "0" * 64})
        v.check(
            other,
            world.round_1,
            world.round_2,
            verified=outputs(world)[0],
            register=outputs(world)[1],
        )


def test_summary_reports_the_share_only_over_decided_cases() -> None:
    entry = {
        "case_id": "A",
        "state": "unverified",
        "drafted_class": "single-doc",
        "class": "single-doc",
        "repair": None,
        "drop": None,
        "safety_critical": True,
        "authority_unverified": False,
        "rounds": {"1": {"outcome": "none", "disagreements": [], "severity_differences": []}},
    }
    summary = lv.summarise([entry])
    assert summary["first_check_rejection_by_drafted_class"] == {
        "single-doc": {"drafted": 1, "decided": 0, "rejected": 0, "share_rejected": None}
    }
    assert summary["safety_critical"] == {"verified": 0, "verified_without_authority_unverified": 0}
    assert summary["complete"] is False and summary["verified_by_class"] == {}
    assert summary["verified_after_repair"] == []


# --- the registered rubric: one verifier ---------------------------------------------------


def alone(text: str | None) -> dict[str, dict[str, dict[str, Any]] | None]:
    return {OPUS: lv.parse_reply(text) if text else None}


def test_one_verifier_decides_alone() -> None:
    """The decision of the registered rubric: one verdict, and nobody to disagree with it."""
    assert lv.decide("moderate", alone(reply())) == {
        "outcome": "confirmed",
        "missing": [],
        "authority_unverified": False,
        "rejecting_checks": [],
        "disagreements": [],
        "severity_differences": [],
    }
    silent = lv.decide("moderate", alone(None))
    assert silent["outcome"] == "none" and silent["missing"] == [OPUS]
    rejected = lv.decide("moderate", alone(reply("moderate", REJECT_3)))
    assert rejected["outcome"] == "rejected" and rejected["disagreements"] == []
    assert rejected["rejecting_checks"] == [{"check": "3", "verdicts": {OPUS: REJECT_3["3"]}}]
    flagged = lv.decide("moderate", alone(reply("moderate", {"5b": {"verdict": "unverifiable"}})))
    assert flagged["outcome"] == "confirmed" and flagged["authority_unverified"] is True
    step = lv.decide("moderate", alone(reply("high")))
    assert step["outcome"] == "confirmed" and step["disagreements"] == []
    assert [item["steps"] for item in step["severity_differences"]] == [1]
    crossing = lv.decide("high", alone(reply("critical")))
    assert [item["check"] for item in crossing["rejecting_checks"]] == ["5c"]
    assert lv.decide("moderate", alone(reply()), check_1=False)["outcome"] == "rejected"


NO_REPAIR = "The question joins two rules, and no label within the bounds of a repair covers both."


def test_a_set_checked_by_one_model_is_named_so(world: World, one_voice: None) -> None:
    """The registered rubric end to end: one store a round, the status of a check by one model,
    a repair marked with its author, and a case dropped because no repair answers its rejection."""
    clients = run_round(
        world,
        world.round_1,
        world.inputs,
        {
            "M-02": {OPUS: reply("high", REJECT_3)},
            "M-03": {OPUS: reply("moderate", REJECT_3)},
        },
    )
    assert list(clients) == [OPUS]
    assert sorted(path.name for path in world.round_1.iterdir()) == [f"{OPUS}.jsonl", "plan.json"]
    repairs = world.write("repairs.jsonl", [repaired_m02()])
    declared = {"case_id": "M-03", "ground": "repair_not_possible", "reason": NO_REPAIR}
    drops = world.write("drops.json", [{**declared, "documents": [DELTA], "note": "kept nowhere"}])
    inputs = replace(world.second, repairs=repairs, drops=drops)
    run_round(world, world.round_2, inputs)
    plan = json.loads((world.round_2 / "plan.json").read_text(encoding="utf-8"))
    assert list(plan["verifiers"]) == [OPUS] and plan["declared_drops"] == [declared]
    rows, register = apply(world, repairs)
    label = {
        "status": "single_model_verified",
        "verifiers": [OPUS],
        "rubric_version": "label-verification/v2",
    }
    assert [row["case_id"] for row in rows] == ["M-01", "M-02", "M-04"]
    assert rows[0]["label_check"] == {**label, "round": 1}
    assert rows[1]["label_check"] == {**label, "round": 2, "repair_author": REPAIRER}
    assert {row["label_origin"] for row in rows} == {"agent_labelled"}
    assert list(register["verifiers"]) == [OPUS] and register["repair_author"] == REPAIRER
    assert list(register["sent"]) == [OPUS] and register["sent"][OPUS]["requests"] == 5
    summary = register["summary"]
    assert summary["verified_after_repair"] == ["M-02"]
    assert summary["verifier_disagreements"] == []
    assert summary["dropped"] == [declared]
    assert register["cases"][2]["drop"] == {"ground": "repair_not_possible", "reason": NO_REPAIR}
    assert register["complete"] is True
    assert check(world, repairs, inputs)["status"] == "ok"
    # The word of a check by two vendors is not one this set may carry.
    rewrite(world, lambda rows: rows[0]["label_check"].update(status="model_verified"))
    with pytest.raises(ValueError, match="the verified set is not what the decisions give"):
        check(world, repairs)
    apply(world, repairs)
    replan(world, lambda plan: plan["declared_drops"][0].update(reason=" "))
    with pytest.raises(ValueError, match="a declared drop gives no reason: M-03"):
        check(world, repairs)


# --- the rules of one case, and the real pilot ---------------------------------------------


def test_per_case_rules_and_source_checks_apply_to_one_case(world: World) -> None:
    families = devset.document_families(REGISTER)
    fixed = repaired_m02()
    selected = fixed["seed_selected_source_section"]
    assert devset.validate_case(fixed, selected, REVISIONS, CORPUS["corpus_sha256"], families) == [
        "family-b"
    ]
    assert world.drafts.case_rules(world.drafts.cases[3], world.drafts.cases[3]) == ["family-b"]
    with pytest.raises(ValueError, match="seed-selected source"):
        devset.validate_case(fixed, rule(ALPHA), REVISIONS, CORPUS["corpus_sha256"], families)
    with pytest.raises(ValueError, match="span source address"):
        devset.validate_case(fixed, selected, REVISIONS, "0" * 64, families)
    frame = devset.source_frame(TEXTS)
    devset.validate_case_sources(fixed, TEXTS, frame)
    broken = copy.deepcopy(fixed)
    broken["evidence_spans"][0]["char_end"] -= 5
    with pytest.raises(ValueError, match="span text SHA mismatch"):
        devset.validate_case_sources(broken, TEXTS, frame)
    # One case is a valid input: the rules of the set of thirty are not asked of it.
    devset.validate_source_labels([fixed], TEXTS)


def test_pilot_drafts_are_the_registered_artifacts() -> None:
    drafts = v.pilot_drafts()
    assert len(drafts.cases) == 30 and drafts.author == {"model": "gpt-6.1-sol", "vendor": "OpenAI"}
    assert len(drafts.reserve) == 36 and drafts.reserve <= set(drafts.revisions)
    assert v.sha256_bytes(v.PROTECTED[0].read_bytes()) == drafts.manifest["jsonl_sha256"]


def test_pilot_requests_name_no_file(tmp_path: Path) -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    drafts = replace(v.pilot_drafts(), verify=lambda directory: None)
    archive = v.ARCHIVE.read_bytes()
    chunks = json.loads(gzip.decompress(archive))["chunks"]
    cards = [index for index, item in enumerate(chunks) if "\ndoc_id:" in item["page_content"]]
    scanned = {}
    for position, draft in enumerate(item for item in drafts.cases if lv.needs_scan(item)):
        own = [
            index
            for index, item in enumerate(chunks)
            if item["metadata"]["source"] in draft["documents"]
        ]
        scanned[draft["case_id"]] = sorted({*own[:6], *cards[position * 3 : position * 3 + 3]})
    scan = {
        "schema_version": "devset-wide-scan/v1",
        "archive_sha256": sha(archive),
        "cases": [
            {
                "case_id": draft["case_id"],
                "question_sha256": sha(draft["question"]),
                "chunks": [
                    {
                        "chunk_index": index,
                        "source_id": chunks[index]["metadata"]["source"],
                        "text_sha256": sha(chunks[index]["page_content"]),
                    }
                    for index in scanned[draft["case_id"]]
                ],
            }
            for draft in drafts.cases
            if draft["case_id"] in scanned
        ],
    }
    (tmp_path / "scan.json").write_bytes(v.dump(scan))
    inputs = v.RoundInputs(1, directory, tmp_path / "scan.json", v.ARCHIVE)
    plan, texts = v.build_round(drafts, inputs)
    sources = read_sources(drafts.corpus, directory)
    identifiers = {name[:-3] for name in sources}
    identifiers |= {str(lv.front_matter(text).get("doc_id")) for text in sources.values()}
    shaped = re.compile(
        "|".join(
            r"(?<![\w\-])" + re.escape(word) + r"(?![\w\-])"
            for word in sorted(identifiers)
            if not word.isalpha()
        )
    )
    assert len(plan["requests"]) == 30 and len(scanned) == 10
    for row in plan["requests"]:
        text = texts[row["case_id"]]
        body = text[len(lv.PROMPT_TEMPLATE) :]
        assert ".md" not in text.lower() and shaped.search(body) is None
        assert not [name for name in sources if name in text]
        assert "Owner must confirm" not in text and "T64-" not in text
        assert set(row["pseudonyms"].values()) >= set(drafts.by_id()[row["case_id"]]["documents"])
        packet = packet_of(text)
        assert ("scan" in packet) == (row["case_id"] in scanned)
        for card in packet["authority_documents"]:
            assert tuple(card["card"]) == lv.CARD_FIELDS and card["card"]["title"]
    front_matter_lines = [
        line
        for row in plan["requests"]
        for line in texts[row["case_id"]].split("\\n")
        if line.startswith("doc_id:")
    ]
    assert front_matter_lines and all(
        re.fullmatch(r"doc_id: D\d+", line) for line in front_matter_lines
    )
