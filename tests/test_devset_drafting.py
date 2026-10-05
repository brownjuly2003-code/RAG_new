"""Drafts of plan step 1.3d (docs/specs/semantic-precision-metrics.md, «Drafts of plan step 1.3d»).

No model and no network: the generator is a fake that is handed request texts and nothing
else. The corpus is four documents built here; the tests on the registered split read the
split file alone and need no corpus.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from evaluation import devset, devset_split
from evaluation import devset_drafting as drafting
from evaluation import isolated_request as isolated
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import JudgeUnavailable
from evaluation.devset_sources import corpus_directory, eligible_sections, normalized, sections
from scripts import devset_draft as tool

ROOT = Path(__file__).resolve().parent.parent
OPUS = drafting.AUTHOR["model"]
REFUSAL = drafting.UNRESOLVABLE
ALPHA, BETA, GAMMA, DELTA = (
    "01_alpha_storage.md",
    "02_beta_issue.md",
    "03_gamma_forms.md",
    "04_delta_check.md",
)
BODIES = {
    ALPHA: (
        "Хранение альфа",
        "alpha_storage",
        "Сроки хранения",
        [
            "Альфа-журнал хранения ведётся на складе временного хранения и сверяется с накладной.",
            "Срок хранения альфа-журнала составляет 5 лет с даты закрытия рейса, затем журнал "
            "сдают в архив.",
            "Запрещается выносить альфа-журнал за пределы склада без письменного разрешения "
            "начальника смены.",
        ],
    ),
    BETA: (
        "Выдача бета",
        "beta_issue",
        "Порядок выдачи",
        [
            "Копии бета-накладной выдаются только при предъявлении доверенности и паспорта "
            "получателя.",
            "Выдача копий бета-накладной регистрируется в журнале выдачи в день обращения "
            "получателя.",
            "Отказ в выдаче копии бета-накладной оформляется письменно и передаётся получателю "
            "за 3 дня.",
        ],
    ),
    GAMMA: (
        "Формы гамма",
        "gamma_forms",
        "Перечень форм",
        [
            "В гамма-перечень входят следующие формы актов:",
            "- акт приёма груза на терминал;",
            "- акт передачи груза перевозчику;",
            "- акт о расхождениях при приёмке груза.",
            "Каждая форма гамма-перечня пересматривается владельцем процесса один раз в год.",
        ],
    ),
    DELTA: (
        "Досмотр дельта",
        "delta_check",
        "Досмотр груза",
        [
            "Дельта-досмотр опасных грузов проводится перед погрузкой на борт воздушного судна.",
            "Досмотр проводит сертифицированный специалист службы безопасности, порядок описан "
            "в 01_alpha_storage.md.",
            "Результат дельта-досмотра вносится в акт досмотра и хранится вместе с накладной.",
        ],
    ),
}
# The record of a session that loaded nothing: what the isolated route keeps beside a reply.
SESSION = {
    "cli_version": "9.9.9",
    "model": OPUS,
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def source(name: str) -> str:
    title, doc_id, heading, lines = BODIES[name]
    front = [
        "---",
        f"doc_id: {doc_id}",
        f"title: {title}",
        "document_type: регламент",
        'version: "1.0"',
        "effective_date: 2026-05-15",
        "owner_role: Process Owner",
        "---",
    ]
    body = "\n".join(lines)
    related = "## Связанные документы\n\n- смежные документы названы в реестре процесса\n"
    return "\n".join(front) + f"\n# {title}\n\n## {heading}\n\n{body}\n\n{related}"


TEXTS = {name: source(name) for name in BODIES}
CORPUS: dict[str, Any] = {
    "corpus_sha256": sha("".join(TEXTS.values())),
    "file_count": len(TEXTS),
    "files": [
        {"name": name, "sha256": sha(text), "bytes": len(text.encode("utf-8"))}
        for name, text in TEXTS.items()
    ],
}
REVISIONS = {entry["name"]: entry["sha256"] for entry in CORPUS["files"]}
REGISTER = {
    "families": [
        {"family_id": "family-a", "members": [{"source_id": ALPHA}]},
        {"family_id": "family-b", "members": [{"source_id": BETA}, {"source_id": GAMMA}]},
        {"family_id": "family-d", "members": [{"source_id": DELTA}]},
    ]
}
FAMILIES = devset.document_families(REGISTER)
MASKER = lv.Masker(TEXTS)


def line(name: str, index: int) -> str:
    return BODIES[name][3][index]


def rule(name: str) -> dict[str, Any]:
    """The address of the one rule section of a fixture document."""
    return next(s for s in sections(name, TEXTS[name]) if s["section_path"][-1] == BODIES[name][2])


def body(name: str) -> str:
    section = rule(name)
    return TEXTS[name][section["char_start"] : section["char_end"]]


def place(
    position: int, primary_class: str, seed: str, partner: str | None = None
) -> dict[str, Any]:
    """One position as the registered split holds it."""
    return {
        "position": position,
        "primary_class": primary_class,
        "block_id": "block-01",
        "seed": rule(seed),
        "partner": rule(partner) if partner else None,
    }


# A place is taken as given: that two of these share a section does not matter to a draft.
PLACES = [
    place(1, "single-doc", ALPHA),
    place(2, "multi-doc", BETA, GAMMA),
    place(3, "aggregation", GAMMA, BETA),
    place(4, REFUSAL, BETA),
]
BRIEFS = drafting.briefs("development", PLACES)
ITEMS = "\n".join(line(GAMMA, index) for index in (1, 2, 3))
PLAIN = {"value": None, "unit": "", "condition": "", "tolerance": 0}
COPIES = {
    "subject": "копии бета-накладной",
    "text": "Копии бета-накладной выдаются только при предъявлении доверенности и паспорта "
    "получателя",
    "polarity": "only_if",
    **PLAIN,
    "source_quote": line(BETA, 0),
    "critical": True,
}
LABELS: dict[int, dict[str, Any]] = {
    1: {
        "question": "Сколько лет хранят альфа-журнал после закрытия рейса?",
        "reference_answer": "Срок хранения альфа-журнала составляет 5 лет с даты закрытия рейса.",
        "trap_type": None,
        "expected_action": "answer",
        "action_reason": None,
        "safety_critical": False,
        "wrong_answer_severity": "moderate",
        "complexity": "simple",
        "spans": [{"id": "S1", "document": "D1", "text": line(ALPHA, 1)}],
        "evidence_groups": [["S1"]],
        "facts": [
            {
                "subject": "срок хранения альфа-журнала",
                "text": "Срок хранения альфа-журнала составляет 5 лет с даты закрытия рейса",
                "polarity": "allowed",
                "value": 5,
                "unit": "лет",
                "condition": "с даты закрытия рейса",
                "tolerance": 0,
                "source_quote": line(ALPHA, 1),
                "critical": False,
            }
        ],
        "aggregation": None,
    },
    2: {
        "question": "Что предъявить для копии бета-накладной и как часто пересматривают формы "
        "гамма-перечня?",
        "reference_answer": "Копии бета-накладной выдаются только при предъявлении доверенности "
        "и паспорта получателя. Каждая форма гамма-перечня пересматривается владельцем "
        "процесса один раз в год.",
        "trap_type": None,
        "expected_action": "answer",
        "action_reason": None,
        "safety_critical": False,
        "wrong_answer_severity": "high",
        "complexity": "not_simple",
        "spans": [
            {"id": "S1", "document": "D1", "text": line(BETA, 0)},
            {"id": "S2", "document": "D2", "text": line(GAMMA, 4)},
        ],
        "evidence_groups": [["S1"], ["S2"]],
        "facts": [
            COPIES,
            {
                "subject": "формы гамма-перечня",
                "text": "Каждая форма гамма-перечня пересматривается владельцем процесса один "
                "раз в год",
                "polarity": "allowed",
                **PLAIN,
                "source_quote": line(GAMMA, 4),
                "critical": False,
            },
        ],
        "aggregation": None,
    },
    3: {
        "question": "Сколько всего позиций дают формы актов гамма-перечня вместе с документами "
        "для копии бета-накладной?",
        "reference_answer": "Всего 5 позиций: 3 формы актов гамма-перечня и 2 документа "
        "получателя. Копии бета-накладной выдаются только при предъявлении доверенности и "
        "паспорта получателя.",
        "trap_type": None,
        "expected_action": "answer",
        "action_reason": None,
        "safety_critical": False,
        "wrong_answer_severity": "moderate",
        "complexity": "not_simple",
        "spans": [
            {"id": "S1", "document": "D1", "text": ITEMS},
            {"id": "S2", "document": "D2", "text": line(BETA, 0)},
        ],
        "evidence_groups": [["S1"], ["S2"]],
        "facts": [
            {
                "subject": "всего",
                "text": "Всего 5 позиций: 3 формы актов гамма-перечня и 2 документа получателя",
                "polarity": "allowed",
                "value": 5,
                "unit": "позиций",
                "condition": "",
                "tolerance": 0,
                "derived": True,
                "critical": False,
            },
            {**COPIES, "polarity": "allowed", "critical": False},
        ],
        "aggregation": {
            "operation": "count",
            "scope": "Формы актов гамма-перечня и документы для копии бета-накладной.",
            "operands": [
                "акт приёма груза на терминал",
                "акт передачи груза перевозчику",
                "акт о расхождениях при приёмке груза",
                "доверенность",
                "паспорт получателя",
            ],
            "value": 5,
        },
    },
    4: {
        "question": "Выдадут ли мне копию бета-накладной по моей отправке на этой неделе?",
        "reference_answer": "Уточните номер накладной и кто обращается за копией: без этих "
        "данных ответить нельзя.",
        "trap_type": None,
        "expected_action": "clarify",
        "action_reason": "The question does not say which shipment it is about or who asks.",
        "safety_critical": False,
        "wrong_answer_severity": "low",
        "complexity": "not_simple",
        "spans": [],
        "evidence_groups": [],
        "facts": [],
        "aggregation": None,
    },
}
FALSE_PREMISE = {
    "question": "Правда ли, что альфа-журнал хранят 1 год после закрытия рейса?",
    "reference_answer": "Нет. Срок хранения альфа-журнала составляет 5 лет с даты закрытия рейса.",
    "trap_type": "false_premise",
    "expected_action": "correct_premise",
    "action_reason": "The section gives five years, not the one year the question assumes.",
}


TRAP_ASKED = {"requested_trap": "false_premise", "requested_action": "correct_premise"}


def label(position: int, **changes: Any) -> dict[str, Any]:
    return {**copy.deepcopy(LABELS[position]), **changes}


def facts(position: int, index: int = 0, **changes: Any) -> list[dict[str, Any]]:
    """The facts of a label with one of them changed; None drops a field."""
    given = copy.deepcopy(LABELS[position]["facts"])
    given[index] = {
        key: value for key, value in {**given[index], **changes}.items() if value is not None
    }
    return given


def said(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def built(position: int, given: Mapping[str, Any] | None = None, **asked: Any) -> dict[str, Any]:
    """The case a label gives at a position, held to the brief and to the rules of the set."""
    brief = {**BRIEFS[position - 1], **asked}
    spot = PLACES[position - 1]
    version = CORPUS["corpus_sha256"]
    case = drafting.build_case(
        drafting.parse_reply(said(given or LABELS[position])),
        brief,
        spot,
        TEXTS,
        REVISIONS,
        version,
    )
    drafting.check_case(
        case, brief, TEXTS, devset.source_frame(TEXTS), REVISIONS, version, FAMILIES, MASKER
    )
    return case


# --- the brief -----------------------------------------------------------------------------


def test_prompt_sha_is_the_one_registered_in_the_spec() -> None:
    spec = (ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    recorded = re.findall(
        r"Prompt SHA-256 \(generator devset-generator/v1\): `([0-9a-f]{64})`", spec
    )
    assert recorded == [drafting.PROMPT_SHA256]
    assert drafting.prompt_sha256() == drafting.PROMPT_SHA256
    assert drafting.GENERATOR_VERSION == "devset-generator/v1"


def test_the_registered_sha_covers_every_fixed_text_of_a_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    texts = drafting.registered_texts()
    assert texts == {
        "system_prompt": drafting.SYSTEM_PROMPT,
        "prompt": drafting.PROMPT_TEMPLATE,
        "styles": drafting.STYLES,
        "retry_frame": drafting.RETRY_FRAME,
        "unquotable": drafting.UNQUOTABLE,
        "guide": drafting.GUIDE,
        "neutral_file": lv.NEUTRAL_FILE,
    }
    written = json.dumps(texts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert drafting.prompt_sha256() == sha(written)
    # The prompt alone is the text of the trials: what is hashed was widened, no word changed.
    spec = (ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    assert f"alone it has the SHA-256 `{sha(drafting.PROMPT_TEMPLATE)}`" in spec
    # A change of any of them is another SHA-256, and no plan is made on it.
    changes: list[tuple[Any, str, Any]] = [
        (drafting, "SYSTEM_PROMPT", drafting.SYSTEM_PROMPT + " Be brief."),
        (drafting, "PROMPT_TEMPLATE", drafting.PROMPT_TEMPLATE + "Be brief.\n"),
        (drafting, "STYLES", {**drafting.STYLES, "agent_style_A": "a formal question"}),
        (drafting, "RETRY_FRAME", drafting.RETRY_FRAME + "Try again.\n"),
        (drafting, "UNQUOTABLE", "the reply broke a rule"),
        (drafting, "GUIDE", {**drafting.GUIDE, "reference answer": "write less"}),
        (lv, "NEUTRAL_FILE", "[a file]"),
    ]
    for module, name, changed in changes:
        with monkeypatch.context() as patch:
            patch.setattr(module, name, changed)
            assert drafting.prompt_sha256() != drafting.PROMPT_SHA256
            with pytest.raises(ValueError, match="the generator prompt is not the registered one"):
                tool.build_plan(inputs_of())
    assert drafting.prompt_sha256() == drafting.PROMPT_SHA256


def test_the_prompt_names_no_model_and_asks_for_the_keys_the_script_reads() -> None:
    prompt = drafting.PROMPT_TEMPLATE
    for word in ("gpt", "openai", "glm", "claude", "anthropic", "opus"):
        assert word not in (prompt + drafting.SYSTEM_PROMPT).lower()
    skeleton = prompt[prompt.index('{\n "question"') : prompt.index("When the line SCRIPT REFUSAL")]
    assert tuple(json.loads(skeleton)) == drafting.LABEL_KEYS
    assert prompt.endswith("\nBRIEF\n")
    # The system prompt is an argument of a command line: the route refuses what a shell rewrites.
    assert drafting.SYSTEM_PROMPT in isolated.arguments(drafting.SYSTEM_PROMPT)


def test_the_positions_of_a_class_take_styles_and_traps_in_turn() -> None:
    places = [{"position": number, "primary_class": "single-doc"} for number in range(1, 8)]
    places.insert(2, {"position": 20, "primary_class": REFUSAL})
    asked = drafting.briefs("holdout", places)
    single = [brief for brief in asked if brief["primary_class"] == "single-doc"]
    assert [brief["question_origin"][-1] for brief in single] == list("ABABABA")
    assert [brief["requested_trap"] for brief in single] == [
        None,
        "false_premise",
        None,
        None,
        "outdated_rule",
        None,
        "false_premise",
    ]
    assert {brief["requested_action"] for brief in single if brief["requested_trap"]} == {
        "correct_premise"
    }
    # A class counts its own positions: the one between them starts the cycle of its class.
    assert asked[2] == {
        "position": 20,
        "case_id": "HO-20",
        "primary_class": REFUSAL,
        "question_origin": "agent_style_A",
        "requested_trap": None,
        "requested_action": "clarify",
        "plain_allowed": True,
        "numeric_requested": False,
    }
    assert [brief["case_id"] for brief in single][:2] == ["HO-01", "HO-02"]
    assert all(brief["plain_allowed"] for brief in asked)
    # Of every three positions of a class that is asked for quantities, the first is.
    assert [brief["numeric_requested"] for brief in single] == [True, False, False] * 2 + [True]
    several = [{"position": number, "primary_class": "multi-doc"} for number in range(1, 4)]
    assert [b["numeric_requested"] for b in drafting.briefs("holdout", several)] == [
        True,
        False,
        False,
    ]
    for other in ("aggregation", REFUSAL):
        rest = [{"position": number, "primary_class": other} for number in range(1, 7)]
        assert not any(brief["numeric_requested"] for brief in drafting.briefs("holdout", rest))
    assert drafting.case_id("development", 7, replacement=True) == "DV-07R"


def test_a_replacement_is_asked_for_what_the_dropped_draft_was() -> None:
    places = [place(7, "single-doc", ALPHA), place(12, REFUSAL, BETA)]
    dropped = {
        7: {
            **built(1, label(1, **FALSE_PREMISE), **TRAP_ASKED),
            "question_origin": "agent_style_B",
        },
        12: built(4),
        30: built(2),
    }
    # The dropped draft of position 7 held a quantity; its replacement is asked for none: the
    # registered request of a replacement steers four fields.
    assert dropped[7]["flags"]["numeric"]
    assert drafting.BRIEF_RULE["replacement"].endswith("it is not asked for a quantity")
    asked = drafting.replacement_briefs("development", places, dropped)
    assert asked == [
        {
            "position": 7,
            "case_id": "DV-07R",
            "primary_class": "single-doc",
            "question_origin": "agent_style_B",
            "requested_trap": "false_premise",
            "requested_action": "correct_premise",
            "plain_allowed": False,
            "numeric_requested": False,
        },
        {
            "position": 12,
            "case_id": "DV-12R",
            "primary_class": REFUSAL,
            "question_origin": "agent_style_A",
            "requested_trap": None,
            "requested_action": "clarify",
            "plain_allowed": False,
            "numeric_requested": False,
        },
    ]
    # Nothing else of the dropped draft reaches the request of its replacement.
    request = drafting.build_request(asked[0], places[0], TEXTS, MASKER)
    packet = json.loads(request.text[len(drafting.PROMPT_TEMPLATE) :])
    assert packet["plain_allowed"] is False and packet["requested_trap"] == "false_premise"
    assert packet["numeric_requested"] is False
    assert dropped[7]["question"] not in request.text
    assert dropped[7]["reference_answer"] not in request.text
    with pytest.raises(ValueError, match="a replacement changes the class of position 7"):
        drafting.replacement_briefs("development", places, {**dropped, 7: built(2)})


@pytest.mark.parametrize(
    ("split", "styles", "traps", "quantities", "crossed"),
    [
        (
            "development",
            {"agent_style_A": 15, "agent_style_B": 15},
            {
                "conflicting_documents": 2,
                "dangerous_goods": 2,
                "false_premise": 4,
                "out_of_corpus": 2,
                "outdated_rule": 1,
            },
            {"multi-doc": 4, "single-doc": 3},
            (18, 7, 2),
        ),
        (
            "holdout",
            {"agent_style_A": 33, "agent_style_B": 31},
            {
                "conflicting_documents": 5,
                "dangerous_goods": 4,
                "false_premise": 8,
                "out_of_corpus": 4,
                "outdated_rule": 3,
            },
            {"multi-doc": 9, "single-doc": 5},
            (41, 16, 5),
        ),
    ],
)
def test_what_the_rule_asks_of_the_registered_split(
    split: str,
    styles: dict[str, int],
    traps: dict[str, int],
    quantities: dict[str, int],
    crossed: tuple[int, int, int],
) -> None:
    registered = json.loads((ROOT / "evaluation/devset_split.json").read_text(encoding="utf-8"))
    asked = drafting.briefs(split, registered["splits"][split]["positions"])
    assert dict(Counter(brief["question_origin"] for brief in asked)) == styles
    requested = Counter(brief["requested_trap"] for brief in asked if brief["requested_trap"])
    assert dict(sorted(requested.items())) == traps
    numeric = Counter(brief["primary_class"] for brief in asked if brief["numeric_requested"])
    assert dict(sorted(numeric.items())) == quantities
    # The positions of the classes asked for quantities, those of them asked for a trap, and
    # the quantity requests that fall on a position asked for a trap.
    open_to = [brief for brief in asked if brief["primary_class"] in drafting.NUMERIC_CLASSES]
    assert crossed == (
        len(open_to),
        sum(1 for brief in open_to if brief["requested_trap"]),
        sum(1 for brief in open_to if brief["requested_trap"] and brief["numeric_requested"]),
    )
    # Every trap type is asked for in both splits, and every one of them in both styles.
    assert set(requested) == devset.TRAPS
    assert all(
        len({b["question_origin"] for b in asked if b["requested_trap"] == trap}) == 2
        for trap in ("false_premise", "conflicting_documents", "out_of_corpus", "dangerous_goods")
    )
    for brief in asked:
        pair = (brief["requested_trap"], brief["requested_action"])
        assert pair in drafting.TRAP_CYCLES[brief["primary_class"]]


def test_a_request_is_the_registered_prompt_and_the_brief() -> None:
    request = drafting.build_request(BRIEFS[1], PLACES[1], TEXTS, MASKER)
    assert request.text.startswith(drafting.PROMPT_TEMPLATE)
    assert request.sha256 == sha(request.text) and request.characters == len(request.text)
    packet = json.loads(request.text[len(drafting.PROMPT_TEMPLATE) :])
    assert {key: value for key, value in packet.items() if key != "sections"} == {
        "primary_class": "multi-doc",
        "question_style": "formal operator question",
        "requested_trap": None,
        "requested_action": "answer",
        "plain_allowed": True,
        "numeric_requested": True,
        "as_of": "2026-10-01",
    }
    seed, partner = packet["sections"]
    assert (seed["role"], seed["document"]) == ("seed", "D1")
    assert (partner["role"], partner["document"]) == ("partner", "D2")
    # A section goes out as the document has it: a span is copied from it.
    assert seed["text"] == body(BETA) and partner["text"] == body(GAMMA)
    assert seed["headings"] == ["Выдача бета", "Порядок выдачи"]
    assert tuple(seed["card"]) == lv.CARD_FIELDS and seed["card"]["title"] == "Выдача бета"
    assert request.pseudonyms == {"D1": BETA, "D2": GAMMA}
    for name in BODIES:
        assert name not in request.text and BODIES[name][1] not in request.text


def test_a_section_that_names_a_file_is_not_sent() -> None:
    spot = place(5, "single-doc", DELTA)
    brief = drafting.briefs("development", [spot])[0]
    with pytest.raises(ValueError, match="a section names a file: position 5"):
        drafting.build_request(brief, spot, TEXTS, MASKER)


def test_a_later_attempt_carries_the_refusal_and_the_refused_reply() -> None:
    text = drafting.retry_text("BASE\n", "fact F1: no `source_quote`", ' {"question": 1} \n')
    assert text == (
        "BASE\n\nSCRIPT REFUSAL\n"
        "The script refused your previous reply to this brief: fact F1: no `source_quote`\n"
        'Your previous reply:\n{"question": 1}\n'
    )
    assert text == "BASE\n" + drafting.RETRY_FRAME.format(
        refusal="fact F1: no `source_quote`", previous='{"question": 1}'
    )
    # What a refusal or a reply holds in braces is its text, not a field of the frame.
    assert drafting.retry_text("B", "{previous}", "{refusal} {0}").endswith(
        "this brief: {previous}\nYour previous reply:\n{refusal} {0}\n"
    )


def test_a_text_goes_back_without_a_file_name() -> None:
    stem = BETA.rsplit(".", 1)[0]
    message = f"the label cites {ALPHA}, {stem}, notes/extra.md and C:/data/corpus"
    # A file name of the corpus and its stem, whoever wrote the text.
    assert drafting.unnamed(message, TEXTS) == (
        "the label cites [file], [file], notes/extra.md and C:/data/corpus"
    )
    # In a sentence of the script, whatever else reads as naming a file as well.
    cleared = drafting.unnamed(message, TEXTS, MASKER)
    assert cleared == "the label cites [file], [file], [file] and [file]"
    assert MASKER.leaks(cleared) == []
    plain = "`evidence_groups` puts every span into exactly one group"
    assert drafting.unnamed(plain, TEXTS, MASKER) == plain


def test_no_advice_of_the_script_reads_as_a_file_name() -> None:
    # A refusal that read as one could not go back: the attempt after it would not be sent.
    for advice in drafting.GUIDE.values():
        assert MASKER.leaks(advice) == []


# --- the reply -----------------------------------------------------------------------------


def test_a_reply_in_the_form_of_the_prompt_is_read() -> None:
    assert drafting.parse_reply(said(LABELS[2])) == LABELS[2]
    # Prose or a fence around the object costs no attempt.
    assert drafting.parse_reply("```json\n" + said(LABELS[4]) + "\n```") == LABELS[4]


def dropped(key: str) -> dict[str, Any]:
    return {name: value for name, value in LABELS[1].items() if name != key}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("No case can be drafted.", "not one JSON object"),
        (said(LABELS[1]) + said(LABELS[1]), "not one JSON object"),
        (said(dropped("aggregation")), "the reply lacks aggregation"),
        (said(label(1, question=" ")), "the question or the reference answer is empty"),
        (said(label(1, trap_type="")), "`trap_type` is null or a trap"),
        (said(label(1, action_reason=3)), "`action_reason` is null or a sentence"),
        (said(label(1, safety_critical="no")), "`safety_critical` is true or false"),
        (said(label(1, wrong_answer_severity="severe")), "not a level of the scale"),
        (said(label(1, complexity="hard")), "`complexity` is simple or not_simple"),
        (said(label(1, spans=[{"id": "S1", "document": "D1"}])), "a span needs"),
        (said(label(2, spans=LABELS[2]["spans"][:1] * 2)), "two spans share an id"),
        (said(label(1, evidence_groups=["S1"])), "a list of lists of span ids"),
        (said(label(1, facts=["a fact"])), "`facts` is a list of objects"),
        (said(label(1, aggregation="count")), "`aggregation` is null or an object"),
    ],
)
def test_a_reply_in_another_form_is_refused(text: str, message: str) -> None:
    with pytest.raises(lv.ReplyFormatError, match=re.escape(message)):
        drafting.parse_reply(text)


def test_an_excerpt_is_found_as_written_or_with_the_white_space_of_the_text() -> None:
    text = "Первая строка правила.\nВторая  строка\tправила."
    assert drafting.locate("строка правила.", text) == (7, 22)
    start, end = drafting.locate("правила. Вторая строка правила", text) or (0, 0)
    assert text[start:end] == "правила.\nВторая  строка\tправила"
    assert drafting.locate("третья строка", text) is None
    assert drafting.locate("  ", text) is None


# --- the case ------------------------------------------------------------------------------


@pytest.mark.parametrize("position", [1, 2, 3, 4])
def test_a_reply_gives_a_case_that_passes_the_rules_of_the_set(position: int) -> None:
    case = built(position)
    spot = PLACES[position - 1]
    assert case["case_id"] == f"DV-0{position}"
    assert case["primary_class"] == spot["primary_class"]
    assert case["question_origin"] == "agent_style_A" and case["as_of"] == "2026-10-01"
    assert case["seed_selected_source_section"] == spot["seed"]
    assert [section["selection_reason"] for section in case["partner_sections"]] == (
        [drafting.PARTNER_REASON] if spot["partner"] else []
    )
    assert case["label_origin"] == case["status"] == "agent_labelled"
    # A draft has the fields of a pilot draft, in their order, and none a verification adds.
    with (ROOT / "evaluation/devset_pilot.jsonl").open(encoding="utf-8") as handle:
        assert list(case) == list(json.loads(handle.readline()))
    for number, span in enumerate(case["evidence_spans"], 1):
        text = TEXTS[span["source_id"]][span["char_start"] : span["char_end"]]
        assert span["span_id"] == f"{case['case_id']}-E{number}"
        assert span["text_sha256"] == sha(text) and span["normalized_text"] == normalized(text)
    assert [group["group_id"] for group in case["required_evidence_groups"]] == [
        f"{case['case_id']}-G{number}" for number in range(1, len(case["evidence_spans"]) + 1)
    ]
    assert case["flags"] == {
        "ru_to_en": False,
        "numeric": position in (1, 3),
        "safety_critical": False,
        "adversarial_unanswerable": position == 4,
    }
    assert [fact["text"] for fact in case["critical_facts"]] == (
        [COPIES["text"]] if position == 2 else []
    )
    assert all("critical" not in fact for fact in case["required_facts"])


def test_spans_and_quotes_are_stored_as_the_source_writes_them() -> None:
    loose = label(3)
    loose["spans"][0]["text"] = ITEMS.replace("\n", "  ")
    loose["facts"][1]["source_quote"] = line(BETA, 0).replace(" ", "\n", 2)
    case = built(3, loose)
    span = case["evidence_spans"][0]
    assert TEXTS[GAMMA][span["char_start"] : span["char_end"]] == ITEMS
    assert case["required_facts"][1]["source_quote"] == line(BETA, 0)
    assert case == built(3)


def test_a_requested_trap_is_written_or_falls_back_to_the_plain_pair() -> None:
    plain = built(1, **TRAP_ASKED)
    assert (plain["trap_type"], plain["expected_action"]) == (None, "answer")
    trap = built(1, label(1, **FALSE_PREMISE), **TRAP_ASKED)
    assert (trap["trap_type"], trap["expected_action"]) == ("false_premise", "correct_premise")
    assert trap["flags"]["adversarial_unanswerable"] is True
    assert trap["action_reason"] == FALSE_PREMISE["action_reason"]
    refuse = {"requested_trap": "out_of_corpus", "requested_action": "refuse"}
    assert built(4, **refuse)["expected_action"] == "clarify"
    with pytest.raises(drafting.DraftRefused, match="the requested pair or the plain pair"):
        built(1, label(1, **FALSE_PREMISE))
    with pytest.raises(drafting.DraftRefused, match="the requested pair or the plain pair"):
        built(4, label(4, expected_action="escalate"), **refuse)


def test_a_replacement_is_written_with_the_requested_pair_or_not_at_all() -> None:
    fixed = {**TRAP_ASKED, "plain_allowed": False}
    assert built(1, label(1, **FALSE_PREMISE), **fixed)["trap_type"] == "false_premise"
    with pytest.raises(drafting.DraftRefused, match="the requested pair and no other"):
        built(1, **fixed)
    assert built(1, plain_allowed=False)["trap_type"] is None
    with pytest.raises(drafting.DraftRefused, match="the requested pair and no other"):
        built(4, requested_trap="out_of_corpus", requested_action="refuse", plain_allowed=False)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "NO CASE: the two sections share no countable items.",
            "the two sections share no countable items.",
        ),
        (
            "\n NO CASE\nThe section gives no rule\nthat a premise could contradict.\n",
            "The section gives no rule that a premise could contradict.",
        ),
        ("NO CASE", "no reason given"),
        ("NO CASE. " + said(LABELS[1]), said(LABELS[1])),
    ],
)
def test_a_reply_that_begins_with_no_case_declares_one(text: str, reason: str) -> None:
    assert drafting.declined(text) == reason


@pytest.mark.parametrize(
    "text", [said(LABELS[1]), "There is NO CASE here.", "no case", "NO CASES fit.", ""]
)
def test_any_other_reply_declares_nothing(text: str) -> None:
    assert drafting.declined(text) is None


Change = Callable[[], dict[str, Any]]
REFUSALS: list[tuple[int, Change, str]] = [
    (
        1,
        lambda: label(1, spans=[{"id": "S1", "document": "D2", "text": line(ALPHA, 1)}]),
        "span S1 names a document that is not in the brief",
    ),
    (
        1,
        lambda: label(1, spans=[{"id": "S1", "document": "D1", "text": line(BETA, 1)}]),
        "span S1 is not an excerpt of the section of D1: copy it character for character",
    ),
    (2, lambda: label(2, evidence_groups=[["S1"]]), "puts every span into exactly one group"),
    (
        2,
        lambda: label(2, evidence_groups=[["S1", "S2"], ["S2"]]),
        "puts every span into exactly one group",
    ),
    (
        1,
        lambda: label(1, facts=facts(1, source_quote=line(ALPHA, 0))),
        "fact F1: `source_quote` is not an excerpt of one of your spans",
    ),
    (1, lambda: label(1, facts=facts(1, source_quote=None)), "fact F1: no `source_quote`"),
    (
        1,
        lambda: label(1, facts=facts(1, value="5")),
        "fact F1: `subject`, `text` and `polarity` are strings",
    ),
    (
        2,
        lambda: label(2, facts=facts(2, 1, text="Формы пересматривают раз в год")),
        "fact F2: fact claim grounding - a fact `text` is a phrase of its `source_quote`",
    ),
    (
        2,
        lambda: label(2, facts=facts(2, 1, polarity="required")),
        "fact F2: fact governing cue - a fact with the polarity required",
    ),
    (
        2,
        lambda: label(2, reference_answer="Нужны доверенность и паспорт получателя."),
        "fact F1: the reference answer: silent fact miss - a plain fact stands word for word",
    ),
    (
        1,
        lambda: label(1, facts=facts(1, condition="с даты выдачи груза")),
        "fact F1: the reference answer: silent fact miss",
    ),
    (
        1,
        lambda: label(
            1,
            spans=[{"id": "S1", "document": "D1", "text": "Срок хранения альфа-журнала"}],
            facts=facts(1, source_quote="Срок хранения альфа-журнала", text="Срок хранения"),
        ),
        "numeric span self-coverage: silent fact miss",
    ),
    (
        1,
        lambda: label(1, action_reason="The section answers the question."),
        "`action_reason` is null exactly when `expected_action` is answer",
    ),
    (2, lambda: label(2, complexity="simple"), "`complexity` is not_simple outside"),
    (
        2,
        lambda: label(
            2,
            spans=[
                {"id": "S1", "document": "D1", "text": line(BETA, 0)},
                {"id": "S2", "document": "D1", "text": line(BETA, 1)},
            ],
            facts=facts(2)[:1],
            reference_answer=COPIES["text"] + ".",
        ),
        "a case of two documents needs a span from each of them",
    ),
    (
        1,
        lambda: label(1, question="Сколько лет хранят альфа-журнал по документу D1?"),
        "name no pseudonym",
    ),
    (
        4,
        lambda: label(4, spans=LABELS[2]["spans"][:1], evidence_groups=[["S1"]]),
        "missing-answer gold - a case of the class needs-refusal/clarification has no spans",
    ),
    (
        4,
        lambda: label(4, expected_action="answer", action_reason=None),
        "the requested pair or the plain pair",
    ),
    (
        3,
        lambda: label(3, aggregation={**LABELS[3]["aggregation"], "value": 4}),
        "derived aggregation claim - a derived fact belongs to the class aggregation",
    ),
    (
        3,
        lambda: label(3, aggregation={**LABELS[3]["aggregation"], "operation": "sum"}),
        "aggregation operation - `aggregation.operation` is count",
    ),
    (
        1,
        lambda: label(1, reference_answer=LABELS[1]["reference_answer"] + " Drafted by " + OPUS),
        "a model that drafts or verifies would be named in the request",
    ),
    (
        1,
        lambda: label(1, question="How long is the alpha journal kept? Ответьте на английском."),
        "answer-language request",
    ),
]


@pytest.mark.parametrize(
    ("position", "change", "message"), REFUSALS, ids=[row[2][:40] for row in REFUSALS]
)
def test_a_reply_that_breaks_a_rule_is_refused_in_the_words_of_the_prompt(
    position: int, change: Change, message: str
) -> None:
    with pytest.raises(drafting.DraftRefused, match=re.escape(message)) as refusal:
        built(position, change())
    # What goes back to the generator names no case and no file.
    assert "DV-0" not in str(refusal.value)
    assert not any(name in str(refusal.value) for name in TEXTS)
    assert MASKER.leaks(str(refusal.value)) == []


def test_summary_counts_what_was_asked_and_what_was_written() -> None:
    plan = {
        "requests": [
            {"case_id": "DV-01", "requested_trap": "false_premise", "numeric_requested": True},
            {"case_id": "DV-02", "requested_trap": None, "numeric_requested": True},
            {"case_id": "DV-03", "requested_trap": None, "numeric_requested": False},
            {"case_id": "DV-04", "requested_trap": "out_of_corpus", "numeric_requested": False},
            {"case_id": "DV-05", "requested_trap": "false_premise", "numeric_requested": True},
        ]
    }
    asked = {"requested_trap": "false_premise", "requested_action": "correct_premise"}
    cases = [built(1, label(1, **FALSE_PREMISE), **asked), built(2), built(3), built(4)]
    assert drafting.summary(plan, cases, [5]) == {
        "positions": 5,
        "drafted": 4,
        "empty_positions": [5],
        "class_counts": {"aggregation": 1, "multi-doc": 1, REFUSAL: 1, "single-doc": 1},
        "style_counts": {"agent_style_A": 4},
        "action_counts": {"answer": 2, "clarify": 1, "correct_premise": 1},
        "traps_requested": {"None": 2, "false_premise": 2, "out_of_corpus": 1},
        "traps_written_as_requested": {"None": 2, "false_premise": 1},
        "trap_counts": {"false_premise": 1},
        # Asked of three positions; one of them holds a quantity, one holds none, one is empty.
        "numeric_requested": 3,
        "numeric_written_as_requested": 1,
        "flags": {"ru_to_en": 0, "numeric": 2, "safety_critical": 0, "adversarial_unanswerable": 2},
    }


# --- the tool ------------------------------------------------------------------------------


def inputs_of() -> tool.Inputs:
    return tool.Inputs(
        split="development",
        texts=dict(TEXTS),
        corpus=CORPUS,
        register=REGISTER,
        places=copy.deepcopy(PLACES),
        briefs=copy.deepcopy(BRIEFS),
        bound={
            "split_sha256": sha("split"),
            "corpus_sha256": CORPUS["corpus_sha256"],
            "families_sha256": sha(said(REGISTER)),
        },
    )


@dataclass
class World:
    """One planned split in tmp_path: the plan directory and where the drafts are written."""

    inputs: tool.Inputs
    out: Path
    texts: dict[str, str]
    drafts: Path
    manifest: Path

    @property
    def store(self) -> Path:
        return self.out / tool.STORE

    def rows(self) -> list[dict[str, Any]]:
        return [json.loads(row) for row in self.store.read_text(encoding="utf-8").splitlines()]

    def rewrite(self, rows: list[dict[str, Any]]) -> None:
        self.store.write_bytes(tool.jsonl(rows))

    def build(self) -> dict[str, Any]:
        return tool.build(self.out, self.inputs, self.drafts, self.manifest)


@pytest.fixture
def world(tmp_path: Path) -> World:
    inputs = inputs_of()
    plan, texts = tool.build_plan(inputs)
    tool.write_plan(tmp_path / "plan", plan)
    return World(
        inputs, tmp_path / "plan", texts, tmp_path / "drafts.jsonl", tmp_path / "manifest.json"
    )


class Fake:
    """A generator that answers from a script. It is handed request texts and nothing else.

    `answers` gives, per case, one reply or the replies to successive attempts; a case that is
    not named gets the label of its position.
    """

    def __init__(
        self,
        world: World,
        answers: Mapping[str, Any] | None = None,
        *,
        model: str = OPUS,
        session: Any = SESSION,
    ) -> None:
        self.bases = world.texts
        self.queues = {
            identity: list(given) if isinstance(given, list) else [given]
            for identity, given in (answers or {}).items()
        }
        self.model = model
        self.session = session
        self.texts: list[str] = []

    def send(self, text: str) -> isolated.IsolatedReply:
        self.texts.append(text)
        identity = next(name for name, base in self.bases.items() if text.startswith(base))
        queue = self.queues.get(identity)
        if queue:
            answer = queue.pop(0) if len(queue) > 1 else queue[0]
        else:
            answer = said(LABELS[int(identity[-2:])])
        if isinstance(answer, Exception):
            raise answer
        usage = {"output_tokens": 7, "service_tier": "standard"}
        return isolated.IsolatedReply(answer, self.model, usage, 0.25, self.session)


NO_SPAN = said(label(1, spans=[{"id": "S1", "document": "D1", "text": "Журнал хранят вечно."}]))
NO_SPAN_ERROR = "span S1 is not an excerpt of the section of D1: copy it character for character"
IDS = ["DV-01", "DV-02", "DV-03", "DV-04"]


def test_plan_records_what_binds_a_request_and_no_request_text(world: World) -> None:
    plan = tool.load_plan(world.out)
    assert [request["case_id"] for request in plan["requests"]] == IDS
    assert plan["prompt_sha256"] == drafting.PROMPT_SHA256
    assert plan["generator_version"] == drafting.GENERATOR_VERSION
    assert plan["author"] == {"model": OPUS, "vendor": "Anthropic"}
    assert plan["route"] == isolated.ROUTE
    assert plan["settings"] == isolated.settings(drafting.SYSTEM_PROMPT)
    assert plan["brief_rule"]["cycles"]["aggregation"] == [[None, "answer"]]
    assert plan["inputs"] == world.inputs.bound
    assert plan["unseated_positions"] == []
    for request, spot in zip(plan["requests"], PLACES, strict=True):
        assert request["request_sha256"] == sha(world.texts[request["case_id"]])
        assert (request["seed"], request["partner"]) == (spot["seed"], spot["partner"])
        assert request["characters"] == len(world.texts[request["case_id"]])
    written = (world.out / "plan.json").read_text(encoding="utf-8")
    assert not any(row in written for name in BODIES for row in BODIES[name][3])
    # The plan is written once; the same plan again is accepted, another is not.
    tool.write_plan(world.out, plan)
    with pytest.raises(ValueError, match="a different plan exists"):
        tool.write_plan(world.out, {**plan, "as_of": "2026-10-02"})


def test_a_position_without_a_section_is_listed_and_not_asked_for(tmp_path: Path) -> None:
    inputs = inputs_of()
    inputs.places[1]["seed"] = inputs.places[1]["partner"] = None
    plan, texts = tool.build_plan(inputs)
    assert [request["case_id"] for request in plan["requests"]] == ["DV-01", "DV-03", "DV-04"]
    assert sorted(texts) == ["DV-01", "DV-03", "DV-04"]
    # The order had no section left for it: the plan and the manifest say so.
    assert plan["unseated_positions"] == [2]
    out = tmp_path / "plan"
    tool.write_plan(out, plan)
    world = World(inputs, out, texts, tmp_path / "drafts.jsonl", tmp_path / "manifest.json")
    tool.draft(out, inputs, client=Fake(world))
    report = world.build()
    manifest = json.loads(world.manifest.read_text(encoding="utf-8"))
    assert report["unseated_positions"] == manifest["unseated_positions"] == [2]
    assert (manifest["positions"], manifest["drafted"], manifest["empty_positions"]) == (3, 3, [])


def test_a_changed_prompt_is_not_planned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drafting, "PROMPT_TEMPLATE", drafting.PROMPT_TEMPLATE + "Be brief.\n")
    with pytest.raises(ValueError, match="the generator prompt is not the registered one"):
        tool.build_plan(inputs_of())


def test_a_pass_keeps_every_reply_with_its_session_and_the_drafts_follow(world: World) -> None:
    client = Fake(world)
    result = tool.draft(world.out, world.inputs, client=client)
    assert result == {
        "split": "development",
        "requests": 4,
        "valid": 4,
        "empty": 0,
        "pending": 0,
        "sent": 4,
        "unavailable": None,
    }
    assert client.texts == [world.texts[identity] for identity in IDS]
    for row, identity in zip(world.rows(), IDS, strict=True):
        assert row["case_id"] == identity and row["attempt"] == 1 and row["status"] == "valid"
        assert row["raw_reply"] == said(LABELS[int(identity[-2:])])
        assert row["request_sha256"] == row["base_request_sha256"] == sha(world.texts[identity])
        assert (row["model"], row["session"]) == (OPUS, SESSION)
        # Only the registered counters of the route's usage are kept.
        assert row["usage"] == {"output_tokens": 7}
    report = world.build()
    assert report["drafted"] == 4 and report["empty_positions"] == []
    cases = [json.loads(row) for row in world.drafts.read_text(encoding="utf-8").splitlines()]
    assert cases == [built(position) for position in (1, 2, 3, 4)]
    manifest = json.loads(world.manifest.read_text(encoding="utf-8"))
    assert manifest["generator"] == OPUS and manifest["label_check"] == "none"
    assert manifest["jsonl_sha256"] == sha(world.drafts.read_bytes())
    assert manifest["families_sha256"] == world.inputs.bound["families_sha256"]
    assert manifest["plan_sha256"] == sha((world.out / "plan.json").read_bytes())
    assert manifest["store_sha256"] == sha(world.store.read_bytes())
    assert manifest["replies"] == {
        "sent": 4,
        "refused_by_script": 0,
        "no_case": 0,
        "unavailable": 0,
        "cases_by_attempts": {"1": 4},
    }
    assert manifest["no_case_positions"] == {"1": [], "2": [], "3": []}
    assert manifest["unseated_positions"] == report["unseated_positions"] == []
    assert tool.check(world.out, world.inputs, world.drafts, world.manifest)["status"] == "ok"
    # A finished split asks for nothing more.
    again = Fake(world)
    assert tool.draft(world.out, world.inputs, client=again)["sent"] == 0 and again.texts == []


def test_a_refused_reply_is_asked_for_again_with_the_refusal(world: World) -> None:
    client = Fake(world, {"DV-01": [NO_SPAN, said(LABELS[1])]})
    result = tool.draft(world.out, world.inputs, client=client, limit=1)
    assert (result["valid"], result["pending"], result["sent"]) == (1, 3, 2)
    again = drafting.retry_text(world.texts["DV-01"], NO_SPAN_ERROR, NO_SPAN)
    assert client.texts == [world.texts["DV-01"], again]
    first, second = world.rows()
    assert (first["attempt"], first["status"], first["error"]) == (1, "invalid", NO_SPAN_ERROR)
    assert first["raw_reply"] == NO_SPAN and first["session"] == SESSION
    assert (second["attempt"], second["status"], second["error"]) == (2, "valid", None)
    assert second["request_sha256"] == sha(again) != second["base_request_sha256"]
    tool.draft(world.out, world.inputs, client=Fake(world))
    world.build()
    assert json.loads(world.manifest.read_text(encoding="utf-8"))["replies"] == {
        "sent": 5,
        "refused_by_script": 1,
        "no_case": 0,
        "unavailable": 0,
        "cases_by_attempts": {"1": 3, "2": 1},
    }


def test_a_refusal_goes_back_to_the_generator_without_a_file_name(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    stem = BETA.rsplit(".", 1)[0]
    refused: list[str] = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        if not refused:
            refused.append("DV-01")
            raise drafting.DraftRefused(f"the label cites {ALPHA}, {stem} and notes/extra.md")

    monkeypatch.setattr(drafting, "check_case", refuse)
    client = Fake(world)
    tool.draft(world.out, world.inputs, client=client, limit=1)
    first, second = world.rows()
    assert first["error"] == "the label cites [file], [file] and [file]"
    assert (second["attempt"], second["status"]) == (2, "valid")
    added = client.texts[1][len(world.texts["DV-01"]) :]
    assert "the label cites [file], [file] and [file]\n" in added
    assert ALPHA not in added and stem not in added and "extra.md" not in added


def test_a_refusal_that_still_names_a_file_goes_back_as_the_fixed_sentence(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    parse = drafting.parse_reply
    named = f"the reply cites {ALPHA}"

    def refuse_first(text: str) -> Any:
        # A refusal of the form is stored as written, and this one names a file.
        if text == NO_SPAN:
            raise lv.ReplyFormatError(named)
        return parse(text)

    monkeypatch.setattr(drafting, "parse_reply", refuse_first)
    client = Fake(world, {"DV-01": [NO_SPAN, said(LABELS[1])]})
    result = tool.draft(world.out, world.inputs, client=client, limit=1)
    assert (result["valid"], result["sent"]) == (1, 2)
    first, second = world.rows()
    assert (first["status"], first["error"]) == ("invalid", named)
    # The refusal stays in the store; the fixed sentence goes back in its place.
    again = drafting.retry_text(world.texts["DV-01"], drafting.UNQUOTABLE, NO_SPAN)
    assert client.texts == [world.texts["DV-01"], again]
    assert "previous reply to this brief: the reply broke a rule the script cannot quote" in again
    assert ALPHA not in again and MASKER.leaks(drafting.UNQUOTABLE) == []
    assert (second["attempt"], second["status"]) == (2, "valid")
    assert second["request_sha256"] == sha(again)
    # The store is read back by the same rule, so the position is closed and not held for good.
    tool.draft(world.out, world.inputs, client=Fake(world))
    world.build()
    assert tool.check(world.out, world.inputs, world.drafts, world.manifest)["status"] == "ok"


def test_a_refusal_is_quoted_unless_it_reads_as_naming_a_file() -> None:
    assert drafting.quoted_refusal(NO_SPAN_ERROR, MASKER) == NO_SPAN_ERROR
    for named in (f"span S1 is no excerpt of {ALPHA}", "the label reads notes/extra.md"):
        assert drafting.quoted_refusal(named, MASKER) == drafting.UNQUOTABLE
    assert drafting.UNQUOTABLE == "the reply broke a rule the script cannot quote here"


def test_three_refused_replies_leave_the_position_empty(world: World) -> None:
    client = Fake(world, {"DV-04": ["No case fits this section.", NO_SPAN, "{}"]})
    result = tool.draft(world.out, world.inputs, client=client)
    assert (result["valid"], result["empty"], result["pending"], result["sent"]) == (3, 1, 0, 6)
    mine = [row for row in world.rows() if row["case_id"] == "DV-04"]
    assert [(row["attempt"], row["status"]) for row in mine] == [
        (1, "invalid"),
        (2, "invalid"),
        (3, "invalid"),
    ]
    # Each attempt answers the refusal of the one before it.
    assert client.texts[-1] == drafting.retry_text(
        world.texts["DV-04"], mine[1]["error"], mine[1]["raw_reply"]
    )
    report = world.build()
    assert report["drafted"] == 3 and report["empty_positions"] == [4]
    again = Fake(world)
    assert tool.draft(world.out, world.inputs, client=again)["sent"] == 0 and again.texts == []


def test_a_reply_that_declares_no_case_leaves_the_position_empty_at_once(world: World) -> None:
    declared = "NO CASE: the two sections hold no items that one count could cover."
    client = Fake(world, {"DV-03": [NO_SPAN.replace("D1", "D9"), declared, said(LABELS[3])]})
    result = tool.draft(world.out, world.inputs, client=client)
    assert (result["valid"], result["empty"], result["pending"], result["sent"]) == (3, 1, 0, 5)
    mine = [row for row in world.rows() if row["case_id"] == "DV-03"]
    assert [(row["attempt"], row["status"], row["error"]) for row in mine][1] == (
        2,
        "declined",
        None,
    )
    assert mine[1]["raw_reply"] == declared and mine[1]["session"] == SESSION
    world.build()
    manifest = json.loads(world.manifest.read_text(encoding="utf-8"))
    # The declaration followed a refused reply: the manifest gives it by its attempt.
    assert manifest["empty_positions"] == [3]
    assert manifest["no_case_positions"] == {"1": [], "2": [3], "3": []}
    assert manifest["replies"]["no_case"] == 1 and manifest["drafted"] == 3
    # The position is closed: no later pass asks for it, and no row may follow the declaration.
    again = Fake(world)
    assert tool.draft(world.out, world.inputs, client=again)["sent"] == 0 and again.texts == []
    rows = world.rows()
    world.rewrite([*rows, {**mine[1], "attempt": 2, "status": "valid"}])
    with pytest.raises(ValueError, match="attempts that draft does not write: DV-03"):
        world.build()
    # A row cannot be turned into a declaration its reply does not make.
    rows[0]["status"] = "declined"
    world.rewrite(rows)
    with pytest.raises(ValueError, match="declares no case and does not say so: DV-01"):
        world.build()


def test_an_unavailable_route_stops_the_pass_and_takes_no_attempt(world: World) -> None:
    down = JudgeUnavailable("cli_timeout", "the request ran out of time")
    client = Fake(world, {"DV-02": [NO_SPAN.replace("D1", "D9"), down]})
    result = tool.draft(world.out, world.inputs, client=client)
    assert (result["valid"], result["pending"], result["unavailable"]) == (1, 3, "cli_timeout")
    assert len(client.texts) == 3
    last = world.rows()[-1]
    assert (last["case_id"], last["attempt"], last["status"]) == ("DV-02", 2, "unavailable")
    assert (last["raw_reply"], last["session"], last["error"]) == (None, None, "cli_timeout")
    with pytest.raises(ValueError, match="3 positions have no reply yet"):
        world.build()
    # The next pass sends the same attempt again, with the refusal it answers.
    again = Fake(world)
    assert tool.draft(world.out, world.inputs, client=again)["pending"] == 0
    assert again.texts[0] == client.texts[-1] != world.texts["DV-02"]
    assert [row["attempt"] for row in world.rows() if row["case_id"] == "DV-02"] == [1, 2, 2]
    assert world.build()["drafted"] == 4


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"model": "another-model"}, "model_mismatch"),
        ({"session": {**SESSION, "turns": 2}}, "session_record"),
        (
            {"session": {**SESSION, "loaded": {**SESSION["loaded"], "tools": ["Bash"]}}},
            "session_record",
        ),
        ({"session": None}, "session_record"),
    ],
)
def test_a_reply_the_route_does_not_vouch_for_is_not_kept(
    world: World, changes: dict[str, Any], code: str
) -> None:
    result = tool.draft(world.out, world.inputs, client=Fake(world, **changes))
    assert (result["valid"], result["sent"], result["unavailable"]) == (0, 1, code)
    (row,) = world.rows()
    assert (row["status"], row["error"], row["raw_reply"], row["model"]) == (
        "unavailable",
        code,
        None,
        None,
    )


def test_limit_takes_up_that_many_positions(world: World) -> None:
    result = tool.draft(world.out, world.inputs, client=Fake(world), limit=2)
    assert (result["valid"], result["pending"], result["sent"]) == (2, 2, 2)
    result = tool.draft(world.out, world.inputs, client=Fake(world), limit=1)
    assert (result["valid"], result["pending"], result["sent"]) == (3, 1, 1)


def edit_reply(rows: list[dict[str, Any]]) -> None:
    rows[0]["raw_reply"] = NO_SPAN


def edit_request(rows: list[dict[str, Any]]) -> None:
    rows[1]["request_sha256"] = sha("another request")


def edit_base(rows: list[dict[str, Any]]) -> None:
    rows[1]["base_request_sha256"] = sha("another request")


def edit_session(rows: list[dict[str, Any]]) -> None:
    rows[2]["session"] = {**SESSION, "turns": 2}


def edit_model(rows: list[dict[str, Any]]) -> None:
    rows[2]["model"] = "another-model"


def edit_attempt(rows: list[dict[str, Any]]) -> None:
    rows[0]["attempt"] = 2


def edit_status(rows: list[dict[str, Any]]) -> None:
    rows[3]["status"] = "accepted"


def answer_twice(rows: list[dict[str, Any]]) -> None:
    rows.append({**rows[0], "attempt": 2})


def answer_another_case(rows: list[dict[str, Any]]) -> None:
    rows.append({**rows[0], "case_id": "DV-09"})


def answer_another_prompt(rows: list[dict[str, Any]]) -> None:
    rows[0]["prompt_sha256"] = sha("another prompt")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (edit_reply, "a stored reply no longer passes the script: DV-01"),
        (edit_request, "a stored reply is not to the request of its row: DV-02"),
        (edit_base, "a row that is not of this plan (DV-02)"),
        (edit_session, "a stored reply the route does not vouch for"),
        (edit_model, "a stored reply is not of the registered model: DV-03"),
        (edit_attempt, "attempts that draft does not write: DV-01"),
        (edit_status, "a row that is not of this plan (DV-04)"),
        (answer_twice, "attempts that draft does not write: DV-01"),
        (answer_another_case, "a row that is not of this plan (DV-09)"),
        (answer_another_prompt, "a row that is not of this plan (DV-01)"),
    ],
)
def test_a_store_that_draft_did_not_write_gives_no_drafts(
    world: World, change: Callable[[list[dict[str, Any]]], None], message: str
) -> None:
    tool.draft(world.out, world.inputs, client=Fake(world))
    world.build()
    rows = world.rows()
    change(rows)
    world.rewrite(rows)
    with pytest.raises(ValueError, match=re.escape(message)):
        tool.check(world.out, world.inputs, world.drafts, world.manifest)
    if change is edit_reply:
        # A pass reads no reply it has counted; the drafts are what holds a reply to the rules.
        return
    client = Fake(world)
    with pytest.raises(ValueError, match=re.escape(message.split(":")[0])):
        tool.draft(world.out, world.inputs, client=client)
    assert client.texts == []


def test_a_refused_reply_that_was_edited_breaks_the_chain(world: World) -> None:
    tool.draft(world.out, world.inputs, client=Fake(world, {"DV-01": [NO_SPAN, said(LABELS[1])]}))
    rows = world.rows()
    rows[0]["raw_reply"] = NO_SPAN.replace("вечно", "всегда")
    world.rewrite(rows)
    with pytest.raises(ValueError, match="not to the request of its row: DV-01"):
        world.build()


def test_check_refuses_files_that_are_not_what_the_store_gives(world: World) -> None:
    tool.draft(world.out, world.inputs, client=Fake(world))
    world.build()
    drafts, manifest = world.drafts.read_bytes(), world.manifest.read_bytes()
    world.drafts.write_bytes(drafts.replace("Сколько лет".encode(), "Сколько месяцев".encode()))
    with pytest.raises(ValueError, match="the drafts are not what the plan and the store give"):
        tool.check(world.out, world.inputs, world.drafts, world.manifest)
    world.drafts.write_bytes(drafts)
    world.manifest.write_bytes(manifest.replace(b'"label_check": "none"', b'"label_check": "done"'))
    with pytest.raises(ValueError, match="the manifest is not what the plan and the store give"):
        tool.check(world.out, world.inputs, world.drafts, world.manifest)


def other_style(inputs: tool.Inputs) -> tool.Inputs:
    briefs = copy.deepcopy(inputs.briefs)
    briefs[0]["question_origin"] = "agent_style_B"
    return replace(inputs, briefs=briefs)


def other_text(inputs: tool.Inputs) -> tool.Inputs:
    texts = {name: text.replace("5 лет", "6 лет") for name, text in inputs.texts.items()}
    return replace(inputs, texts=texts)


def other_split(inputs: tool.Inputs) -> tool.Inputs:
    return replace(inputs, bound={**inputs.bound, "split_sha256": sha("another split")})


@pytest.mark.parametrize("change", [other_style, other_text, other_split])
def test_inputs_that_no_longer_give_the_plan_send_nothing(
    world: World, change: Callable[[tool.Inputs], tool.Inputs]
) -> None:
    client = Fake(world)
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan"):
        tool.draft(world.out, change(world.inputs), client=client)
    assert client.texts == [] and not world.store.exists()


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("plan_version", 2, "plan_version is not supported"),
        ("generator_version", "devset-generator/v0", "another generator version"),
        ("prompt_sha256", sha("another prompt"), "the plan is of another prompt"),
        ("requests", [{"case_id": "DV-01"}, {"case_id": "DV-01"}], "a position is planned twice"),
        ("requests", [{"position": 1}], "plan.json does not hold a plan"),
    ],
)
def test_a_plan_of_another_generator_is_not_read(
    world: World, key: str, value: Any, message: str
) -> None:
    plan = json.loads((world.out / "plan.json").read_text(encoding="utf-8"))
    (world.out / "plan.json").write_bytes(tool.dump({**plan, key: value}))
    with pytest.raises(ValueError, match=message):
        tool.load_plan(world.out)


def test_the_command_refuses_a_corpus_that_is_not_the_registered_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "plan"
    code = tool.main(["plan", "--split", "holdout", f"--corpus-dir={tmp_path}", f"--out={out}"])
    assert code == 2 and not out.exists()
    assert capsys.readouterr().out.strip() == (
        "refused: the corpus is not the registered version: a file is missing"
    )


# --- the replacements ----------------------------------------------------------------------


def test_the_replacements_of_a_split_are_kept_apart_from_its_drafts() -> None:
    assert tool.drafts_path("holdout").name == "devset_holdout_drafts.jsonl"
    assert tool.drafts_path("holdout", True).name == "devset_holdout_replacements.jsonl"
    assert tool.manifest_path("holdout", True).name == "devset_holdout_replacements.manifest.json"
    assert tool.checks_path("holdout").name == "devset_holdout_label_checks.json"
    assert tool.out_dir("holdout") == tool.BASE / "holdout"
    assert tool.out_dir("holdout", True) == tool.BASE / "holdout-replacements"


def test_the_outcomes_of_a_split_are_read_from_its_first_verification() -> None:
    unseated = {**place(5, "single-doc", ALPHA), "seed": None, "partner": None}
    places = [*copy.deepcopy(PLACES), unseated]
    drafts = {identity: built(position) for position, identity in enumerate(IDS[:3], 1)}
    states = ("verified", "dropped", "verified")
    checks = {
        "complete": True,
        "cases": [
            {"case_id": identity, "state": state}
            for identity, state in zip(IDS, states, strict=False)
        ],
    }
    left, dropped = tool.outcomes("development", places, drafts, checks)
    # The fourth position was left empty by the generator; the fifth was never seated.
    assert left == {1: "confirmed", 2: "dropped", 3: "confirmed", 4: "empty"}
    assert dropped == {2: drafts["DV-02"]}
    with pytest.raises(ValueError, match="the first verification of the split is not complete"):
        tool.outcomes("development", places, drafts, {**checks, "complete": False})
    fewer = {**checks, "cases": checks["cases"][:2]}
    with pytest.raises(ValueError, match="the register of the first verification is not of these"):
        tool.outcomes("development", places, drafts, fewer)


PILOT_CHECKS = {"complete": True, "cases": [{"case_id": "T64-01", "state": "verified"}]}


@dataclass
class Verified:
    """One split after its first verification, in a directory that stands for evaluation/."""

    split: str
    corpus_dir: Path
    registered: dict[str, Any]
    families: bytes
    drafts: bytes
    checks: dict[str, Any]
    seated: list[Any]
    again: list[dict[str, Any]]

    def load(self) -> tool.Inputs:
        return tool.load_inputs(self.split, self.corpus_dir, replacement=True)


def verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, split: str) -> Verified:
    """Three drafts of a split, the second dropped, and a rule that seats its replacement."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for name, text in TEXTS.items():
        (corpus_dir / name).write_bytes(text.encode("utf-8"))
    families = tool.dump(REGISTER)
    registered = {
        "inputs": {"corpus_sha256": CORPUS["corpus_sha256"], "families_sha256": sha(families)},
        "splits": {split: {"positions": copy.deepcopy(PLACES)}},
    }
    ids = [drafting.case_id(split, position) for position in (1, 2, 3)]
    drafts = tool.jsonl(
        [{**built(position), "case_id": ids[position - 1]} for position in (1, 2, 3)]
    )
    checks = {
        "complete": True,
        "sha256": {"drafts": sha(drafts)},
        "cases": [
            {"case_id": identity, "state": state}
            for identity, state in zip(ids, ("verified", "dropped", "verified"), strict=True)
        ],
    }
    monkeypatch.setattr(tool, "EVALUATION", tmp_path)
    (tmp_path / "aircargo_corpus.manifest.json").write_bytes(tool.dump(CORPUS))
    (tmp_path / "document_families.json").write_bytes(families)
    (tmp_path / "devset_split.json").write_bytes(tool.dump(registered))
    tool.drafts_path(split).write_bytes(drafts)
    tool.checks_path(split).write_bytes(tool.dump(checks))
    seated: list[Any] = []
    again = [place(2, "multi-doc", ALPHA, GAMMA)]

    def reseat(
        name: str, split_file: Mapping[str, Any], texts: Mapping[str, str], left: Mapping[int, str]
    ) -> list[dict[str, Any]]:
        seated.append((name, split_file, texts, left))
        return again

    monkeypatch.setattr(tool.devset_split, "replacements", reseat)
    return Verified(split, corpus_dir, registered, families, drafts, checks, seated, again)


def test_the_replacements_of_a_split_are_planned_from_its_drafts_and_their_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given = verified(tmp_path, monkeypatch, "development")
    tool.checks_path("pilot_v3").write_bytes(tool.dump(PILOT_CHECKS))
    inputs = given.load()
    # The rule of the registered split seats again what the first verification left.
    left = {1: "confirmed", 2: "dropped", 3: "confirmed", 4: "empty"}
    assert given.seated == [("development", given.registered, TEXTS, left)]
    assert (inputs.replacement, inputs.places) == (True, given.again)
    assert inputs.briefs == drafting.replacement_briefs("development", given.again, {2: built(2)})
    assert inputs.bound == {
        "split_sha256": sha(tool.dump(given.registered)),
        "corpus_sha256": CORPUS["corpus_sha256"],
        "families_sha256": sha(given.families),
        "drafts_sha256": sha(given.drafts),
        "label_checks_sha256": sha(tool.dump(given.checks)),
        "pilot_v3_label_checks_sha256": sha(tool.dump(PILOT_CHECKS)),
    }
    plan, texts = tool.build_plan(inputs)
    (request,) = plan["requests"]
    assert (plan["replacement"], plan["inputs"]) == (True, inputs.bound)
    assert (request["case_id"], request["plain_allowed"]) == ("DV-02R", False)
    # The position was asked for a quantity; its replacement is not.
    assert BRIEFS[1]["numeric_requested"] is True and request["numeric_requested"] is False
    assert list(texts) == ["DV-02R"]
    # The first drafts of the split are planned from the registered positions alone.
    first = tool.load_inputs("development", given.corpus_dir)
    assert (first.replacement, first.places, first.briefs) == (False, PLACES, BRIEFS)
    assert sorted(first.bound) == ["corpus_sha256", "families_sha256", "split_sha256"]
    assert tool.build_plan(first)[0]["replacement"] is False
    # A register of other drafts gives no replacements.
    tool.drafts_path("development").write_bytes(given.drafts + b"\n")
    with pytest.raises(ValueError, match="the register of the first verification is not of these"):
        given.load()


def test_the_replacements_of_development_wait_for_the_register_of_pilot_v3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given = verified(tmp_path, monkeypatch, "development")
    register = tool.checks_path("pilot_v3")
    assert register.name == "devset_pilot_v3_label_checks.json"
    # A dropped case of pilot-v3 is replaced with the dropped drafts of development.
    with pytest.raises(ValueError, match="pilot-v3 is not complete: no register"):
        given.load()
    register.write_bytes(tool.dump({**PILOT_CHECKS, "complete": False}))
    with pytest.raises(ValueError, match="the verification of pilot-v3 is not complete$"):
        given.load()
    cases = [
        {"case_id": "T64-07", "state": "dropped"},
        {"case_id": "T64-02", "state": "verified"},
        {"case_id": "T64-05", "state": "dropped"},
    ]
    register.write_bytes(tool.dump({"complete": True, "cases": cases}))
    with pytest.raises(ValueError, match="registered and not written: T64-05, T64-07"):
        given.load()
    # Nothing was seated while the register stood in the way.
    assert given.seated == []
    register.write_bytes(tool.dump(PILOT_CHECKS))
    assert given.load().bound["pilot_v3_label_checks_sha256"] == sha(tool.dump(PILOT_CHECKS))


def test_the_replacements_of_the_holdout_do_not_read_the_register_of_pilot_v3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given = verified(tmp_path, monkeypatch, "holdout")
    assert not tool.checks_path("pilot_v3").exists()
    inputs = given.load()
    assert [brief["case_id"] for brief in inputs.briefs] == ["HO-02R"]
    assert sorted(inputs.bound) == [
        "corpus_sha256",
        "drafts_sha256",
        "families_sha256",
        "label_checks_sha256",
        "split_sha256",
    ]


def test_the_manifest_says_whether_its_drafts_are_replacements(tmp_path: Path) -> None:
    inputs = replace(inputs_of(), replacement=True)
    plan, texts = tool.build_plan(inputs)
    out = tmp_path / "plan"
    tool.write_plan(out, plan)
    world = World(inputs, out, texts, tmp_path / "drafts.jsonl", tmp_path / "manifest.json")
    tool.draft(out, inputs, client=Fake(world))
    world.build()
    manifest = json.loads(world.manifest.read_text(encoding="utf-8"))
    assert (plan["replacement"], manifest["replacement"]) == (True, True)
    # The same inputs read as the first drafts of the split are another plan.
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan"):
        tool.check(out, inputs_of(), world.drafts, world.manifest)


def test_no_section_of_a_registered_draw_order_names_a_file() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    inputs = tool.load_inputs("development")
    texts = dict(inputs.texts)
    masker = lv.Masker(texts)
    registered = json.loads((tool.EVALUATION / "devset_split.json").read_bytes())
    frame = eligible_sections(texts)
    eligible = {devset_split.key(section): section for section in frame}
    idf = devset_split.weights(devset_split.eligible_text(texts, frame))
    found = {}
    for name in ("development", "holdout"):
        part = registered["splits"][name]
        order = [eligible[tuple(pair)] for pair in part["order"]]
        seating = devset_split.Seating(order, part["blocks"], texts, idf, None)
        named = []
        refused = []
        for number, section in enumerate(order, 1):
            body = texts[section["source_id"]][section["char_start"] : section["char_end"]]
            if masker.mask(body, lambda source: "D9") != body or masker.leaks(body):
                named.append(devset_split.key(section))
            # The request of the section as a seed, with the partner the rule gives it: a
            # heading or a card that would still name a file is refused there, not here.
            partner = seating.partner(section)
            spot = {
                "position": number,
                "primary_class": "single-doc" if partner is None else "multi-doc",
                "seed": section,
                "partner": partner,
            }
            try:
                drafting.build_request(drafting.briefs(name, [spot])[0], spot, texts, masker)
            except ValueError as exc:
                refused.append((devset_split.key(section), str(exc)))
        found[name] = (len(order), named, refused)
    # A seed and a partner, of a first draft or of a replacement, are sections of the order,
    # and the partner of a seed is the one the rule gives it: no request of either split can
    # be refused for a section, a heading or a card that names a file.
    assert found == {"development": (814, [], []), "holdout": (128, [], [])}
