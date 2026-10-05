"""Repairs of rubric label-verification/v3 (plan step 1.3d): the request, the reply, the tool.

No model and no network. The corpus, the drafts and the scan are those of
tests/test_label_verification.py, taken as a set of v3 by the helpers of
tests/test_label_verification_v3.py; the repair author is a voice that answers from a script.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from evaluation import devset
from evaluation import devset_drafting as drafting
from evaluation import devset_repair as repair
from evaluation import isolated_request as isolated
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import JudgeUnavailable
from evaluation.devset_sources import corpus_directory, read_sources
from scripts import devset_label_repair as tool
from scripts import devset_label_verify as v
from scripts import devset_wide_scan as wide
from tests import test_label_verification as t
from tests import test_label_verification_v3 as w

ROOT = Path(__file__).resolve().parent.parent
CASES = {case["case_id"]: case for case in t.drafts_cases()}
M02, M04 = CASES["M-02"], CASES["M-04"]
# The pseudonyms of the verifier's requests: of M-02 with the scan of the v3 tests, and of M-04.
NAMES = {"D1": t.ALPHA, "D2": t.BETA, "D3": t.GAMMA, "D4": t.DELTA}
SUPPLIED = ["D1", "D2", "D4"]
NAMES_04 = {"D1": t.BETA, "D2": t.GAMMA}
SUPPLIED_04 = ["D1", "D2"]
FRAME = devset.source_frame(t.TEXTS)
FAMILIES = devset.document_families(t.REGISTER)
MASKER = lv.Masker(t.TEXTS)
VERSION = t.CORPUS["corpus_sha256"]
AUTHOR = lv.draft_author(w.OPUS)
RESERVE = frozenset({t.DELTA})
SHORT = "Нет: копии бета-накладной выдаются только при предъявлении доверенности."
REFUSAL_LINE = t.BODIES[t.BETA][3][2]
COUNT = {"operation": "count", "operands": ["a"], "scope": "s", "value": 1}
UNCHANGED = "the reply changes nothing: a repair changes the label"


def label(**changes: Any) -> dict[str, Any]:
    """The repair of M-02 to its seed document; `changes` replace fields of the reply."""
    base = {
        "primary_class": "single-doc",
        "trap_type": "false_premise",
        "expected_action": "correct_premise",
        "action_reason": "The premise contradicts the rule on copies.",
        "safety_critical": False,
        "wrong_answer_severity": "high",
        "complexity": "simple",
        "reference_answer": SHORT,
        "spans": [{"id": "S1"}],
        "evidence_groups": [["S1"]],
        "facts": [{"id": "F1", "critical": False}],
        "aggregation": None,
    }
    return {**base, **changes}


# M-02 as it was drafted, in the form of a reply, and the same label in another order.
AS_DRAFTED = label(
    primary_class="multi-doc",
    reference_answer=M02["reference_answer"],
    spans=[{"id": "S1"}, {"id": "S2"}],
    evidence_groups=[["S1"], ["S2"]],
    facts=[{"id": "F1", "critical": False}, {"id": "F2", "critical": False}],
)
REORDERED = {
    **AS_DRAFTED,
    "spans": [{"id": "S2"}, {"id": "S1"}],
    "evidence_groups": [["S2"], ["S1"]],
    "facts": [{"id": "F2", "critical": False}, {"id": "F1", "critical": False}],
}
# A span of the one document of the reserve, which the scan of M-02 supplies.
BARRED = label(
    primary_class="multi-doc",
    complexity="not_simple",
    spans=[{"id": "S1"}, {"id": "N1", "document": "D4", "text": t.BODIES[t.DELTA][3][1]}],
    evidence_groups=[["S1"], ["N1"]],
)
OUTSIDE_SEED = label(
    reference_answer="Срок хранения альфа-журнала составляет пять лет.",
    spans=[{"id": "S2"}],
    evidence_groups=[["S2"]],
    facts=[{"id": "F2", "critical": False}],
)


def narrowed() -> dict[str, Any]:
    """M-04 with its beta span cut to the one line the fact is quoted from."""
    return {
        "primary_class": "multi-doc",
        "trap_type": None,
        "expected_action": "answer",
        "action_reason": None,
        "safety_critical": True,
        "wrong_answer_severity": "critical",
        "complexity": "not_simple",
        "reference_answer": M04["reference_answer"],
        "spans": [{"id": "S1"}, {"id": "N1", "document": "D1", "text": REFUSAL_LINE}],
        "evidence_groups": [["S1"], ["N1"]],
        "facts": [{"id": "F1", "critical": True}, {"id": "F2", "critical": False}],
        "aggregation": None,
    }


def wider() -> dict[str, Any]:
    """M-02 with the alpha document left and a span of the gamma document brought in."""
    return label(
        primary_class="multi-doc",
        complexity="not_simple",
        reference_answer=SHORT[:-1]
        + ", а каждая форма гамма-перечня пересматривается владельцем процесса.",
        spans=[{"id": "S1"}, {"id": "N1", "document": "D3", "text": t.BODIES[t.GAMMA][3][1]}],
        evidence_groups=[["S1"], ["N1"]],
        facts=[{"id": "F1", "critical": False}, {**t.GAMMA_FACT, "critical": False}],
    )


def refusal() -> dict[str, Any]:
    """M-02 as a case the corpus cannot answer."""
    return label(
        primary_class=drafting.UNRESOLVABLE,
        trap_type="out_of_corpus",
        expected_action="refuse",
        action_reason="The supplied documents hold no rule on the storage term asked about.",
        complexity="not_simple",
        reference_answer="Отказ: в документах нет правила о годичном хранении журнала.",
        spans=[],
        evidence_groups=[],
        facts=[],
    )


def tight() -> dict[str, Any]:
    """The holdout case of the v3 tests with its span cut to the line of its fact."""
    return {
        "primary_class": "single-doc",
        "trap_type": None,
        "expected_action": "answer",
        "action_reason": None,
        "safety_critical": False,
        "wrong_answer_severity": "moderate",
        "complexity": "simple",
        "reference_answer": w.held_case()["reference_answer"],
        "spans": [{"id": "N1", "document": "D1", "text": t.BODIES[t.DELTA][3][1]}],
        "evidence_groups": [["N1"]],
        "facts": [{"id": "F1", "critical": False}],
        "aggregation": None,
    }


def said(value: Any, key: str = "repair") -> str:
    return json.dumps({key: value}, ensure_ascii=False)


def dropped(**declaration: Any) -> str:
    return said(declaration, "drop")


def passage(index: int) -> dict[str, str]:
    """One chunk of the fixture archive as a wide scan shows it."""
    chunk = t.CHUNKS[index]
    return {"source_id": chunk["metadata"]["source"], "text": chunk["page_content"]}


def shown(name: str, text: str) -> dict[str, str]:
    """A scan passage of a document that is no chunk of the fixture archive."""
    return {"source_id": name, "text": t.header(name) + text}


def places(*passages: Mapping[str, str]) -> list[dict[str, Any]]:
    return repair.passage_regions(passages, t.TEXTS)


# Where the scan of M-02 in the v3 tests stands: the rule lines of alpha, beta and delta.
SCAN_02 = places(*map(passage, sorted(w.SCANNED["M-02"])))


def built(
    given: Mapping[str, Any],
    case: Mapping[str, Any] = M02,
    names: Mapping[str, str] = NAMES,
    supplied: list[str] | None = None,
    scanned: Sequence[Mapping[str, Any]] = SCAN_02,
) -> dict[str, Any]:
    chosen = SUPPLIED if supplied is None else supplied
    return repair.build_case(
        given, case, names, chosen, t.TEXTS, t.REVISIONS, VERSION, FRAME, scanned
    )


def checked(
    fixed: dict[str, Any],
    case: Mapping[str, Any] = M02,
    names: Mapping[str, str] = NAMES,
    barred: frozenset[str] = RESERVE,
) -> None:
    repair.check_case(
        fixed, case, names, AUTHOR, barred, t.TEXTS, FRAME, t.REVISIONS, VERSION, FAMILIES, MASKER
    )


def request_of(case: Mapping[str, Any], scanned: tuple[int, ...] = ()) -> lv.Request:
    """The verifier's request of one case, its scan given by the numbers of its chunks."""
    passages = [passage(index) for index in sorted(scanned)]
    return lv.build_request(case, t.TEXTS, MASKER, passages or None)


# --- the prompt ----------------------------------------------------------------------------


def test_prompt_sha_is_the_one_registered_in_the_spec() -> None:
    spec = (ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    recorded = re.findall(r"Prompt SHA-256 \(repair devset-repair/v1\): `([0-9a-f]{64})`", spec)
    assert recorded == [repair.PROMPT_SHA256]
    assert repair.prompt_sha256() == repair.PROMPT_SHA256
    assert repair.REPAIR_VERSION == "devset-repair/v1"


def test_the_registered_sha_covers_every_fixed_text_of_a_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    texts = repair.registered_texts()
    assert texts == {
        "system_prompt": repair.SYSTEM_PROMPT,
        "prompt": repair.PROMPT_TEMPLATE,
        "reply_line": repair.REPLY_LINE,
        "supplement_line": repair.SUPPLEMENT_LINE,
        "closing": repair.PROMPT_CLOSING,
        "retry_frame": repair.RETRY_FRAME,
        "unquotable": drafting.UNQUOTABLE,
        "guide": drafting.GUIDE,
        "neutral_file": lv.NEUTRAL_FILE,
    }
    written = json.dumps(texts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert repair.prompt_sha256() == t.sha(written)
    # The prompt and its closing line are the text of the trial: no word of them changed.
    spec = (ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    tried = t.sha(repair.PROMPT_TEMPLATE + repair.PROMPT_CLOSING)
    assert f"they have the SHA-256 `{tried}`" in spec
    desk = Desk(tmp_path)
    # A change of any of them is another SHA-256, and no plan is made on it.
    changes: list[tuple[Any, str, Any]] = [
        (repair, "SYSTEM_PROMPT", repair.SYSTEM_PROMPT + " Be brief."),
        (repair, "PROMPT_TEMPLATE", repair.PROMPT_TEMPLATE + "Be brief.\n"),
        (repair, "REPLY_LINE", "REPLY OF THE VERIFIER"),
        (repair, "SUPPLEMENT_LINE", "ADDED"),
        (repair, "PROMPT_CLOSING", "Reply now."),
        (repair, "RETRY_FRAME", repair.RETRY_FRAME + "Try again.\n"),
        (drafting, "UNQUOTABLE", "the reply broke a rule"),
        (drafting, "GUIDE", {**drafting.GUIDE, "reference answer": "write less"}),
        (lv, "NEUTRAL_FILE", "[a file]"),
    ]
    for module, name, changed in changes:
        with monkeypatch.context() as patch:
            patch.setattr(module, name, changed)
            assert repair.prompt_sha256() != repair.PROMPT_SHA256
            with pytest.raises(ValueError, match="the repair prompt is not the registered one"):
                tool.build_plan(desk.inputs)
    assert repair.prompt_sha256() == repair.PROMPT_SHA256


def test_the_prompt_names_no_model_and_asks_for_the_keys_the_script_reads() -> None:
    prompt = repair.PROMPT_TEMPLATE
    written = (prompt + repair.PROMPT_CLOSING + repair.SYSTEM_PROMPT).lower()
    for word in ("gpt", "openai", "glm", "claude", "anthropic", "opus"):
        assert word not in written
    # A repair is checked again in a session that knows nothing of the first check.
    assert not re.search(r"\bround\b", written)
    skeleton = prompt[prompt.index('{"repair": {') : prompt.index("A drop gives its ground")]
    assert tuple(json.loads(skeleton)["repair"]) == repair.LABEL_KEYS
    for example, ground in (
        ('{"drop": {"ground": "repair_not_possible", "reason": "..."}}', lv.NO_REPAIR_DROP),
        ('{"drop": {"ground": "repair_needs_reserve", "documents": ["D3"]}}', lv.RESERVE_DROP),
    ):
        assert example in prompt
        assert repair.parse_reply(example)[1]["ground"] == ground
    assert prompt.endswith("\nVERIFIER REQUEST\n")
    # The system prompt is an argument of a command line: the route refuses what a shell rewrites.
    assert repair.SYSTEM_PROMPT in isolated.arguments(repair.SYSTEM_PROMPT)
    assert (repair.AUTHOR, repair.ATTEMPTS) == (lv.REPAIR_AUTHOR, 3)


# --- the request ---------------------------------------------------------------------------


def test_the_supplied_documents_are_those_a_text_of_which_is_sent() -> None:
    request = request_of(M02, tuple(w.SCANNED["M-02"]))
    assert request.pseudonyms == NAMES
    # The gamma document is only named by the alpha span: it has a pseudonym and no text.
    assert repair.supplied_documents(request.text) == SUPPLIED
    plain = request_of(M04)
    assert plain.pseudonyms == NAMES_04
    assert repair.supplied_documents(plain.text) == SUPPLIED_04


def test_the_supplement_gives_the_bounds_and_the_labels_the_request_does_not_show() -> None:
    packet = t.packet_of(request_of(M02, tuple(w.SCANNED["M-02"])).text)
    assert "complexity" not in packet and not any("group" in key for key in packet)
    assert repair.supplement(M02, NAMES, SUPPLIED, RESERVE, True) == {
        "seed_document": "D2",
        "barred_documents": ["D4"],
        "reserve_ground": True,
        "complexity": "simple",
        "evidence_groups": [["S1"], ["S2"]],
    }
    # A case of the holdout: every supplied document outside the reserve is barred.
    held = repair.supplement(M02, NAMES, SUPPLIED, {t.ALPHA, t.BETA, t.GAMMA}, False)
    assert (held["barred_documents"], held["reserve_ground"]) == (["D1", "D2"], False)
    assert repair.supplement(M04, NAMES_04, SUPPLIED_04, RESERVE, True)["barred_documents"] == []
    # The spans of a group are named as the verifier's request names them.
    alternatives = {"group_id": "M-02-G1", "alternatives": ["M-02-E2", "M-02-E1"]}
    grouped = {**M02, "required_evidence_groups": [alternatives]}
    added = repair.supplement(grouped, NAMES, SUPPLIED, RESERVE, True)
    assert added["evidence_groups"] == [["S2", "S1"]]


def test_a_request_is_the_prompt_the_verifiers_request_its_reply_and_the_supplement() -> None:
    added = {"seed_document": "D1", "barred_documents": [], "reserve_ground": True}
    text = repair.build_request('REQUEST\n{"a": "я"}\n\n', '  {"3": "reject"}\n', added)
    assert text == (
        repair.PROMPT_TEMPLATE
        + 'REQUEST\n{"a": "я"}\nVERIFIER REPLY\n{"3": "reject"}\nSUPPLEMENT\n'
        + '{"seed_document": "D1", "barred_documents": [], "reserve_ground": true}\n'
        + "Reply now with the one JSON object of the repair form: a `repair` or a `drop`.\n"
    )
    again = repair.retry_text(text, UNCHANGED, ' {"repair": {}} \n')
    assert again == (
        text
        + "SCRIPT REFUSAL\n"
        + f"The script refused your previous reply to this request: {UNCHANGED}\n"
        + 'Your previous reply:\n{"repair": {}}\n'
        + "Reply now with the one JSON object of the repair form: a `repair` or a `drop`.\n"
    )


# --- the reply -----------------------------------------------------------------------------


def test_reply_form_of_a_repair_and_of_a_drop() -> None:
    assert repair.parse_reply(said(label())) == ("repair", label())
    # A code fence or a sentence around the one object does not make the reply another.
    assert repair.parse_reply("```json\n" + said(label()) + "\n```") == ("repair", label())
    reason = "  The question\n joins two rules.  "
    assert repair.parse_reply(dropped(ground=lv.NO_REPAIR_DROP, reason=reason)) == (
        "drop",
        {"ground": lv.NO_REPAIR_DROP, "reason": "The question joins two rules."},
    )
    assert repair.parse_reply(dropped(ground=lv.RESERVE_DROP, documents=[" D4 "])) == (
        "drop",
        {"ground": lv.RESERVE_DROP, "documents": ["D4"]},
    )


NOT_ONE = "the reply is not one JSON object with `repair` or with `drop`"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("I cannot repair this label.", NOT_ONE),
        (said(label()) + said(label()), NOT_ONE),
        (json.dumps({"repair": label(), "drop": {"ground": lv.NO_REPAIR_DROP}}), NOT_ONE),
        ('{"repair": {}, "repair": {}}', "a key is given twice"),
        (said("a label"), "`repair` is an object"),
        (said("a ground", "drop"), "`drop` is an object"),
        (dropped(ground=lv.NO_REPAIR_DROP), "a drop on the ground repair_not_possible gives"),
        (dropped(ground="other"), "the ground of a drop is repair_needs_reserve or"),
        (dropped(ground=lv.RESERVE_DROP, documents=[]), "repair_needs_reserve names its doc"),
        (
            said({key: value for key, value in label().items() if key != "complexity"}),
            "the repair lacks complexity",
        ),
        (said(label(primary_class="other")), "`primary_class` is not a class of the prompt"),
        (said(label(reference_answer=" ")), "the reference answer is empty"),
        (said(label(trap_type="")), "`trap_type` is null or a trap of the prompt"),
        (said(label(expected_action=None)), "`expected_action` is missing"),
        (said(label(action_reason="")), "`action_reason` is null or a sentence"),
        (said(label(safety_critical="no")), "`safety_critical` is true or false"),
        (said(label(wrong_answer_severity="severe")), "is not a level of the scale"),
        (said(label(complexity="hard")), "`complexity` is simple or not_simple"),
        (said(label(spans=[{"id": "N1", "document": "D2"}])), "a span is kept by its `id` alone"),
        (said(label(spans=[{"id": "S1"}, {"id": "S1"}])), "two spans share an id"),
        (said(label(evidence_groups=[[]])), "`evidence_groups` is a list of lists of span ids"),
        (said(label(facts=["F1"])), "`facts` is a list of objects"),
        (said(label(facts=[{"id": "F1"}])), "a kept fact gives its `id` and its `critical` mark"),
        (said(label(aggregation="count")), "`aggregation` is null or an object"),
    ],
)
def test_a_reply_in_another_form_is_refused(text: str, message: str) -> None:
    with pytest.raises(lv.ReplyFormatError, match=re.escape(message)):
        repair.parse_reply(text)


# --- the repaired case ---------------------------------------------------------------------


def test_a_repair_to_one_document_is_the_case_its_author_would_write() -> None:
    fixed = built(label())
    assert fixed == t.repaired_m02()
    checked(fixed)
    # The alpha document lost its last span: its section and its authority entry leave with it.
    assert (fixed["partner_sections"], fixed["documents"]) == ([], [t.BETA])
    assert [entry["source_id"] for entry in fixed["authority_source"]] == [t.BETA]
    # The reply that keeps everything by its id rebuilds the case as it was.
    assert built(AS_DRAFTED) == M02


def test_a_span_is_narrowed_by_a_new_span_at_the_place_its_excerpt_stands() -> None:
    fixed = built(narrowed(), M04, NAMES_04, SUPPLIED_04)
    checked(fixed, M04, NAMES_04)
    kept, cut = fixed["evidence_spans"]
    assert kept == M04["evidence_spans"][0]
    assert t.TEXTS[t.BETA][cut["char_start"] : cut["char_end"]] == REFUSAL_LINE
    assert (cut["span_id"], cut["section_path"]) == ("M-04-E2", t.rule(t.BETA)["section_path"])
    assert (cut["text_sha256"], cut["source_revision"]) == (
        t.sha(REFUSAL_LINE),
        t.REVISIONS[t.BETA],
    )
    assert fixed["required_evidence_groups"] == [
        {"group_id": "M-04-G1", "alternatives": ["M-04-E1"]},
        {"group_id": "M-04-G2", "alternatives": ["M-04-E2"]},
    ]
    assert fixed["partner_sections"] == M04["partner_sections"]
    assert fixed["required_facts"] == [t.GAMMA_FACT, t.REFUSAL_FACT]
    assert fixed["critical_facts"] == [t.GAMMA_FACT]
    assert (fixed["complexity"], fixed["flags"]) == ("not_simple", M04["flags"])
    # The question, its date, its style and the seed section are never the reply's to give.
    assert all(fixed[key] == M04[key] for key in lv.KEPT_FIELDS)


def test_an_excerpt_is_taken_with_the_white_space_of_the_source() -> None:
    line = t.BODIES[t.BETA][3][0]
    loose = line.replace("бета-накладной ", "бета-накладной\n ").replace(" и ", "  и ")
    assert loose != line
    given = label(spans=[{"id": "N1", "document": "D2", "text": loose}], evidence_groups=[["N1"]])
    (span,) = built(given)["evidence_spans"]
    assert t.TEXTS[t.BETA][span["char_start"] : span["char_end"]] == line


def test_a_new_span_may_bring_in_a_document_the_scan_supplies() -> None:
    request = request_of(M02, (6,))
    names, supplied = request.pseudonyms, repair.supplied_documents(request.text)
    assert (names["D3"], supplied) == (t.GAMMA, ["D1", "D2", "D3"])
    fixed = built(wider(), M02, names, supplied, places(passage(6)))
    checked(fixed, M02, names)
    assert fixed["documents"] == [t.BETA, t.GAMMA]
    # The document comes with the section that holds its span.
    assert fixed["partner_sections"] == [
        {**t.rule(t.GAMMA), "selection_reason": repair.PARTNER_REASON}
    ]
    assert fixed["authority_source"] == [
        M02["authority_source"][1],
        {
            "source_id": t.GAMMA,
            "source_revision": t.REVISIONS[t.GAMMA],
            "scope": "Internal corpus document: Справочник гамма",
        },
    ]
    assert fixed["required_facts"] == [t.BETA_FACT, t.GAMMA_FACT]
    assert fixed["critical_facts"] == []


def test_a_passage_of_the_scan_is_placed_without_its_line_of_context() -> None:
    (region,) = places(passage(4))
    lines = "\n".join(t.BODIES[t.BETA][3])
    assert region == {
        "source_id": t.BETA,
        "char_start": t.TEXTS[t.BETA].index(lines),
        "char_end": t.TEXTS[t.BETA].index(lines) + len(lines),
    }
    # The line is the archive's, not the document's: with it the passage would have no place.
    assert passage(4)["text"] == t.header(t.BETA) + lines
    assert drafting.locate(passage(4)["text"], t.TEXTS[t.BETA]) is None
    # A passage that begins with its text is placed as it is, and the order is the scan's.
    bare = {"source_id": t.BETA, "text": REFUSAL_LINE}
    first, second = places(bare, passage(1))
    assert t.TEXTS[t.BETA][first["char_start"] : first["char_end"]] == REFUSAL_LINE
    assert second["source_id"] == t.ALPHA
    assert [region["source_id"] for region in SCAN_02] == [t.ALPHA, t.BETA, t.DELTA]
    assert places() == []
    # A text that is not of its document, or a line of context alone, gives no place to hold to.
    for text in (t.BODIES[t.GAMMA][3][0], ""):
        with pytest.raises(ValueError, match="a passage of the wide scan has no place in its doc"):
            places(shown(t.BETA, text))


def test_every_chunk_of_the_registered_archive_has_a_place_in_its_document() -> None:
    directory = corpus_directory()
    if not directory.is_dir():
        pytest.skip(f"AirCargo corpus absent at {directory}; set AIRCARGO_CORPUS_DIR")
    texts = read_sources(v.read_json(v.EVALUATION / "aircargo_corpus.manifest.json"), directory)
    scan = v.read_json(v.BASE / "wide-scan.json")
    chunks = wide.load_chunks(v.ARCHIVE.read_bytes(), scan["archive_sha256"])
    passages = [
        {"source_id": chunk["metadata"]["source"], "text": chunk["page_content"]}
        for chunk in chunks
    ]
    # No plan of a repair can be refused for a passage without a place: none is without one.
    regions = repair.passage_regions(passages, texts)
    assert len(regions) == len(chunks) == 5589
    assert all(
        0 <= region["char_start"] < region["char_end"] <= len(texts[region["source_id"]])
        for region in regions
    )


def test_a_new_span_stands_in_a_text_the_request_supplies() -> None:
    over = label(
        spans=[{"id": "N1", "document": "D2", "text": REFUSAL_LINE + "\n\n## Связанные документы"}],
        evidence_groups=[["N1"]],
    )
    # The document has these words, and no text supplied for it runs that far.
    with pytest.raises(drafting.DraftRefused, match="N1 is not an excerpt of a text supplied for"):
        built(over)
    # A passage of the scan may run over a heading; a span may not.
    tail = shown(t.BETA, REFUSAL_LINE + "\n\n" + t.related(t.BETA))
    with pytest.raises(drafting.DraftRefused, match="N1 runs over a heading: a span lies within"):
        built(over, scanned=places(tail))
    # The gamma lines are in the corpus and in no text of this request.
    with pytest.raises(drafting.DraftRefused, match="N1 is not an excerpt of a text supplied for"):
        built(wider(), supplied=["D1", "D2", "D3"])
    # A case whose request shows no scan supplies its spans and nothing else.
    aside = {
        **narrowed(),
        "spans": [{"id": "S1"}, {"id": "N1", "document": "D1", "text": "смежный документ"}],
    }
    assert "смежный документ" in t.TEXTS[t.BETA] and not lv.needs_scan(M04)
    for scanned in ((), places(shown(t.BETA, t.related(t.BETA)))):
        with pytest.raises(drafting.DraftRefused, match="N1 is not an excerpt of a text supplied"):
            built(aside, M04, NAMES_04, SUPPLIED_04, scanned)


def test_a_span_from_a_section_the_set_does_not_draw_on_brings_no_document_in() -> None:
    given = label(
        spans=[{"id": "S1"}, {"id": "N1", "document": "D4", "text": "смежный документ"}],
        evidence_groups=[["S1"], ["N1"]],
    )
    # The scan shows the passage, under a heading no case is drafted from.
    scanned = [*SCAN_02, *places(shown(t.DELTA, t.related(t.DELTA)))]
    with pytest.raises(drafting.DraftRefused) as refused:
        built(given, scanned=scanned)
    assert str(refused.value).startswith(
        "a span brings in a document from a section the set does not draw on"
    )


def test_a_repair_may_turn_a_case_into_a_refusal_and_keeps_its_sections() -> None:
    fixed = built(refusal())
    checked(fixed)
    assert fixed["primary_class"] == drafting.UNRESOLVABLE
    gold = ("evidence_spans", "required_evidence_groups", "required_facts", "critical_facts")
    assert all(fixed[key] == [] for key in gold)
    # With no span to follow, the sections and the documents stay the case's.
    assert fixed["partner_sections"] == M02["partner_sections"]
    assert (fixed["documents"], fixed["authority_source"]) == (
        M02["documents"],
        M02["authority_source"],
    )
    assert (fixed["expected_action"], fixed["flags"]["adversarial_unanswerable"]) == (
        "refuse",
        True,
    )


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (label(spans=[{"id": "S9"}]), "span S9 is not a span of the case: a new span needs"),
        (
            label(spans=[{"id": "S1", "document": "D2", "text": REFUSAL_LINE}]),
            "span S1: a new span takes an id of its own (N1, N2, ...)",
        ),
        (
            label(spans=[{"id": "N1", "document": "D3", "text": REFUSAL_LINE}]),
            "span N1 names a document no text of which is supplied",
        ),
        (
            label(spans=[{"id": "N1", "document": "D9", "text": REFUSAL_LINE}]),
            "span N1 names a document no text of which is supplied",
        ),
        (
            label(spans=[{"id": "N1", "document": "D2", "text": "Этого предложения нет."}]),
            "span N1 is not an excerpt of a text supplied for D2: copy it character for",
        ),
        (
            label(evidence_groups=[["S1"], ["S1"]]),
            "`evidence_groups` puts every span into exactly one group",
        ),
        (label(evidence_groups=[]), "`evidence_groups` puts every span into exactly one group"),
        (
            label(facts=[{"id": "F9", "critical": False}]),
            "fact F9 is not a fact of the case: a new fact is given in full, without an id",
        ),
        (
            label(facts=[{"id": "F1", "critical": False}, {"id": "F2", "critical": False}]),
            "fact F2 is kept, and its quote lies in no span of your reply",
        ),
        (
            label(facts=[{"id": "F1", "critical": False}, {"id": "F1", "critical": True}]),
            "fact F1 is given twice",
        ),
        (
            label(reference_answer="Нет: без доверенности копии не выдают."),
            "fact F1: the reference answer: silent fact miss - a plain fact stands word for word",
        ),
        (
            label(facts=[{**t.BETA_FACT, "source_quote": "Копии выдаются бесплатно"}]),
            "fact 1 of your reply: `source_quote` is not an excerpt of one of your spans",
        ),
        (
            label(facts=[{**t.BETA_FACT, "subject": ""}]),
            "fact 1 of your reply: `subject`, `text` and `polarity` are strings",
        ),
    ],
)
def test_a_label_the_script_cannot_build_is_refused(given: dict[str, Any], message: str) -> None:
    with pytest.raises(drafting.DraftRefused) as refused:
        built(given)
    assert str(refused.value).startswith(message)


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (AS_DRAFTED, UNCHANGED),
        (REORDERED, UNCHANGED),
        (BARRED, "the label cites a barred document: D4"),
        (OUTSIDE_SEED, "a single-doc label has all its spans in `seed_document`"),
        (
            label(primary_class="multi-doc", complexity="not_simple"),
            "a multi-doc or aggregation label has a span in `seed_document` and a span in at "
            "least one other document",
        ),
        (
            label(action_reason=None),
            "`action_reason` is null exactly when `expected_action` is answer",
        ),
        (
            label(aggregation=COUNT),
            "non-aggregation case - `aggregation` is null outside the class aggregation",
        ),
    ],
)
def test_a_repair_outside_its_limits_is_refused(given: dict[str, Any], message: str) -> None:
    with pytest.raises(drafting.DraftRefused) as refused:
        checked(built(given))
    assert str(refused.value) == message


def test_the_same_label_in_another_order_is_no_change() -> None:
    again = built(REORDERED)
    # The case differs, so its SHA-256 alone would take the reply for a repair.
    assert lv.case_sha256(again) != lv.case_sha256(M02)
    assert repair.label_content(again) == repair.label_content(M02)
    marked = {**AS_DRAFTED, "facts": [{"id": "F1", "critical": True}, AS_DRAFTED["facts"][1]]}
    assert repair.label_content(built(marked)) != repair.label_content(M02)
    regrouped = {**AS_DRAFTED, "evidence_groups": [["S1", "S2"]]}
    assert repair.label_content(built(regrouped)) != repair.label_content(M02)


def test_the_limits_of_a_repair_are_named_in_the_words_of_the_request() -> None:
    # A case of the holdout is bound the other way round: its repair stays in the reserve.
    outside = frozenset({t.ALPHA, t.BETA, t.GAMMA})
    with pytest.raises(drafting.DraftRefused, match="cites a barred document: D2$"):
        checked(built(label()), barred=outside)
    unnamed = {name: source for name, source in NAMES.items() if source != t.DELTA}
    with pytest.raises(drafting.DraftRefused, match="document: one that was not supplied$"):
        checked(built(BARRED), names=unnamed)
    # Outside the class single-doc the complexity is one value, as in a draft.
    plain = {**narrowed(), "complexity": "simple"}
    with pytest.raises(drafting.DraftRefused, match="`complexity` is not_simple outside"):
        checked(built(plain, M04, NAMES_04, SUPPLIED_04), M04, NAMES_04)


# --- a declared drop -----------------------------------------------------------------------


def test_a_declared_drop_names_its_documents_as_round_2_reads_them() -> None:
    added = repair.supplement(M02, NAMES, SUPPLIED, RESERVE, True)
    for_reserve = {"ground": lv.RESERVE_DROP, "documents": ["D4", "D4"]}
    assert repair.drop_of(for_reserve, "M-02", NAMES, added) == {
        "case_id": "M-02",
        "ground": lv.RESERVE_DROP,
        "documents": [t.DELTA],
    }
    no_repair = {"ground": lv.NO_REPAIR_DROP, "reason": "The question joins two rules."}
    assert repair.drop_of(no_repair, "M-02", NAMES, added) == {"case_id": "M-02", **no_repair}
    with pytest.raises(drafting.DraftRefused, match="not among `barred_documents`: D1, D3$"):
        repair.drop_of({**for_reserve, "documents": ["D1", "D4", "D3"]}, "M-02", NAMES, added)
    held = {**added, "reserve_ground": False}
    with pytest.raises(drafting.DraftRefused, match="the ground of a drop is repair_not_possible"):
        repair.drop_of(for_reserve, "M-02", NAMES, held)
    assert repair.drop_of(no_repair, "M-02", NAMES, held)["ground"] == lv.NO_REPAIR_DROP


def test_a_refusal_goes_back_without_a_file_name() -> None:
    message = f"a repair cites {t.BETA}, {t.GAMMA[:-3]} and MANIFEST.md"
    assert drafting.unnamed(message, t.TEXTS) == "a repair cites [file], [file] and MANIFEST.md"
    # With the masker of the set, whatever else would read as a file is replaced too.
    scrubbed = drafting.unnamed(message, t.TEXTS, MASKER)
    assert scrubbed == "a repair cites [file], [file] and [file]"
    assert MASKER.leaks(scrubbed) == []
    assert drafting.unnamed(UNCHANGED, t.TEXTS, MASKER) == UNCHANGED


# --- the tool ------------------------------------------------------------------------------

REJECTED = {"M-02": t.reply("high", t.REJECT_3), "M-04": t.reply("critical", t.REJECT_3)}
REPAIRS = {"M-02": said(label()), "M-04": said(narrowed())}
DONE = {
    "requests": 2,
    "repaired": 2,
    "dropped_by_declaration": 0,
    "dropped_without_valid_repair": 0,
    "dropped_without_request": 0,
    "pending": 0,
}
# A rejection that no repair of a case without spans answers: its authority documents stay.
NO_AUTHORITY = {"5b": {"verdict": "reject", "reason": "The card names another owner of the rule."}}


class Desk:
    """One set of v3 after its first round, with what the repair tool reads and writes."""

    def __init__(
        self,
        root: Path,
        cases: list[dict[str, Any]] | None = None,
        *,
        holdout: bool = False,
        rejected: Mapping[str, str] | None = None,
    ) -> None:
        self.world = w.v3_world(root, cases or t.drafts_cases(), holdout=holdout)
        w.first_round(self.world, REJECTED if rejected is None else rejected)
        self.inputs = tool.Inputs(self.world.drafts, self.world.inputs, self.world.round_1)
        self.out = root / "repair"
        self.repairs = root / "repairs.jsonl"
        self.drops = root / "drops.json"
        self.plan, self.texts, _ = tool.build_plan(self.inputs)
        v.write_plan(self.out, self.plan)

    @property
    def second(self) -> v.RoundInputs:
        return replace(self.world.second, repairs=self.repairs, drops=self.drops)

    def run(self, answers: Mapping[str, Any], **more: Any) -> tuple[dict[str, Any], w.Voice]:
        """Send the planned requests to a voice that answers the named cases."""
        limit = more.pop("limit", None)
        voice = w.Voice(self.texts, answers, **more)
        return tool.run_repairs(self.out, self.inputs, client=voice, limit=limit), voice

    def rows(self) -> list[dict[str, Any]]:
        return t.rows_of(self.out / tool.STORE)

    def rewrite(self, change: Callable[[list[dict[str, Any]]], None]) -> None:
        rows = self.rows()
        change(rows)
        (self.out / tool.STORE).write_bytes(v.jsonl(rows))

    def build(self) -> dict[str, Any]:
        return tool.build(self.out, self.inputs, self.repairs, self.drops)

    def check(self) -> dict[str, Any]:
        return tool.check(self.out, self.inputs, self.repairs, self.drops, self.world.round_2)

    def declared(self) -> list[dict[str, Any]]:
        drops: list[dict[str, Any]] = json.loads(self.drops.read_text(encoding="utf-8"))
        return drops


def nameless(text: str) -> bool:
    return not any(name in text or name[:-3] in text for name in t.BODIES)


def test_plan_binds_every_repair_to_round_1_and_holds_no_request_text(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    plan, texts = desk.plan, desk.texts
    first = v.load_round(desk.world.round_1, desk.world.drafts)
    assert {key: plan[key] for key in plan if key not in ("settings", "inputs", "requests")} == {
        "plan_version": 1,
        "repair_version": "devset-repair/v1",
        "prompt_sha256": repair.PROMPT_SHA256,
        "rubric_version": lv.RUBRIC_V3,
        "author": lv.REPAIR_AUTHOR,
        "route": isolated.ROUTE,
        "without_request": [],
    }
    assert plan["settings"] == json.loads(json.dumps(isolated.settings(repair.SYSTEM_PROMPT)))
    assert plan["inputs"] == {
        **{key: first.plan["inputs"][key] for key in v.BOUND_INPUTS},
        "round_1_plan_sha256": first.plan_sha256,
        "round_1_stores_sha256": first.store_sha256,
    }
    # Only the cases round 1 rejected are repaired.
    assert [row["case_id"] for row in plan["requests"]] == ["M-02", "M-04"]
    sent = t.requests(desk.world)
    supplement = {
        "seed_document": "D2",
        "barred_documents": ["D4"],
        "reserve_ground": True,
        "complexity": "simple",
        "evidence_groups": [["S1"], ["S2"]],
    }
    assert plan["requests"][0] == {
        "case_id": "M-02",
        "request_sha256": t.sha(texts["M-02"]),
        "characters": len(texts["M-02"]),
        "verifier_request_sha256": t.sha(sent["M-02"]),
        "verifier_reply_sha256": t.sha(REJECTED["M-02"]),
        "supplement": supplement,
    }
    assert plan["requests"][1]["supplement"] == {**supplement, "barred_documents": []}
    assert texts["M-02"] == repair.build_request(sent["M-02"], REJECTED["M-02"], supplement)
    written = (desk.out / "plan.json").read_text(encoding="utf-8")
    assert "VERIFIER REQUEST" not in written and "бета-накладной" not in written
    assert nameless(written) and all(nameless(text) for text in texts.values())
    # The same plan is accepted again; another one does not replace it.
    v.write_plan(desk.out, plan)
    with pytest.raises(ValueError, match="a different plan exists in this directory"):
        v.write_plan(desk.out, {**plan, "requests": plan["requests"][:1]})


def test_the_verifiers_reply_goes_into_the_request_without_a_file_name(tmp_path: Path) -> None:
    reason = f"The answer misreads {t.BETA} and {t.GAMMA[:-3]}."
    given = t.reply("high", {"3": {"verdict": "reject", "reason": reason, "element": "F1"}})
    desk = Desk(tmp_path, rejected={"M-02": given})
    assert [row["case_id"] for row in desk.plan["requests"]] == ["M-02"]
    assert "The answer misreads [file] and [file]." in desk.texts["M-02"]
    assert nameless(desk.texts["M-02"])
    # The plan binds the reply as the store of round 1 holds it.
    assert desk.plan["requests"][0]["verifier_reply_sha256"] == t.sha(given)


def test_plan_refuses_what_is_not_a_complete_first_round_of_v3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = Desk(tmp_path / "decided")
    under_v2 = replace(desk.inputs, drafts=replace(desk.world.drafts, rubric=lv.RUBRIC_VERSION))
    with pytest.raises(ValueError, match="a repair by request is of rubric label-verification/v3"):
        tool.build_plan(under_v2)
    scan = desk.world.write("other-scan.json", t.scan_of(t.drafts_cases(), t.SCANNED))
    rescanned = replace(desk.inputs, rounds=replace(desk.inputs.rounds, scan=scan))
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan of round 1"):
        tool.build_plan(rescanned)
    world = w.v3_world(tmp_path / "open", t.drafts_cases())
    v.plan_round(world.round_1, world.drafts, world.inputs)
    texts = t.requests(world)
    voice = w.Voice(texts, dict.fromkeys(texts, t.reply()))
    v.verify(world.round_1, w.OPUS, world.drafts, world.inputs, client=voice, limit=2)
    with pytest.raises(ValueError, match="round 1 is not complete: 2 cases have no valid verdict"):
        tool.build_plan(tool.Inputs(world.drafts, world.inputs, world.round_1))
    monkeypatch.setattr(repair, "PROMPT_CLOSING", "Reply now.")
    with pytest.raises(ValueError, match="the repair prompt is not the registered one"):
        tool.build_plan(desk.inputs)


def test_a_set_with_nothing_rejected_has_nothing_to_repair(tmp_path: Path) -> None:
    desk = Desk(tmp_path, rejected={})
    assert desk.plan["requests"] == []
    result, voice = desk.run({})
    assert (result["sent"], result["pending"], voice.texts) == (0, 0, [])
    desk.build()
    assert (desk.repairs.read_bytes(), desk.declared()) == (b"", [])
    assert desk.check()["status"] == "ok"


def test_a_case_without_spans_rejected_on_authority_is_dropped_without_a_request(
    tmp_path: Path,
) -> None:
    rejected = {
        "M-02": t.reply("high", {**t.REJECT_3, **NO_AUTHORITY}),
        "M-03": t.reply("moderate", {**t.REJECT_3, **NO_AUTHORITY}),
    }
    desk = Desk(tmp_path, rejected=rejected)
    # M-02 has spans, and its authority documents follow from them: it is asked for a repair.
    assert [row["case_id"] for row in desk.plan["requests"]] == ["M-02"]
    assert desk.plan["without_request"] == [{"case_id": "M-03", "rejecting_checks": ["3", "5b"]}]
    assert set(desk.texts) == {"M-02"}
    result, voice = desk.run({"M-02": REPAIRS["M-02"]})
    closed = {**DONE, "requests": 1, "repaired": 1, "dropped_without_request": 1}
    assert result == {**closed, "sent": 1, "unavailable": None}
    assert voice.texts == [desk.texts["M-02"]]
    assert desk.build() == closed
    drop = {"ground": lv.NO_REPAIR_DROP, "reason": "5a or 5b rejected on a case without spans"}
    assert desk.declared() == [{"case_id": "M-03", **drop}]
    summary = v.plan_round(desk.world.round_2, desk.world.drafts, desk.second)
    assert (summary["requests"], summary["declared_drops"]) == (1, 1)
    assert desk.check() == {"status": "ok", **closed}
    w.answer_round(desk.world, desk.world.round_2, desk.second, {})
    rows, register = t.apply(desk.world, desk.repairs)
    assert [row["case_id"] for row in rows] == ["M-01", "M-02", "M-04"]
    # The register keeps the reason: the capsule counts these drops apart by it.
    assert register["summary"]["dropped"] == [{"case_id": "M-03", **drop}]
    assert register["complete"]


@pytest.mark.parametrize("check", lv.AUTHORITY_CHECKS)
def test_only_a_rejection_of_authority_on_a_case_without_spans_spares_the_request(
    tmp_path: Path, check: str
) -> None:
    verdict = {"verdict": "reject", "reason": "The supplied card gives a later date."}
    desk = Desk(tmp_path, rejected={"M-03": t.reply("moderate", {check: verdict})})
    assert desk.plan["requests"] == []
    assert desk.plan["without_request"] == [{"case_id": "M-03", "rejecting_checks": [check]}]
    # Rejected on another check, the same case is asked for a repair like any other.
    other = Desk(tmp_path / "other", rejected={"M-03": t.reply("moderate", t.REJECT_3)})
    assert [row["case_id"] for row in other.plan["requests"]] == ["M-03"]
    assert other.plan["without_request"] == []
    # An authority that could not be verified is no rejection, and the case is confirmed.
    unverified = t.reply("moderate", {check: {"verdict": "unverifiable"}})
    third = Desk(tmp_path / "third", rejected={"M-03": unverified})
    assert (third.plan["requests"], third.plan["without_request"]) == ([], [])


def test_round_2_refuses_the_repair_of_a_case_that_has_none(tmp_path: Path) -> None:
    rejected = {"M-03": t.reply("moderate", {**t.REJECT_3, **NO_AUTHORITY})}
    desk = Desk(tmp_path, rejected=rejected)
    desk.build()
    # A repairs file written past the tool: the label changes, and the same check is drawn again.
    harsher = {**CASES["M-03"], "wrong_answer_severity": "high"}
    desk.repairs.write_bytes(v.jsonl([harsher]))
    desk.drops.write_bytes(v.dump([]))
    with pytest.raises(
        ValueError, match="a case without spans rejected on 5a or 5b has no repair: M-03"
    ):
        v.plan_round(desk.world.round_2, desk.world.drafts, desk.second)
    # Under v2 the repair author could name another authority document: nothing is refused.
    under_v2 = replace(desk.world.drafts, rubric=lv.RUBRIC_VERSION)
    first = v.load_round(desk.world.round_1, desk.world.drafts)
    v.refuse_unrepairable(first, under_v2, ["M-03"])
    with pytest.raises(ValueError, match="has no repair: M-03"):
        v.refuse_unrepairable(first, desk.world.drafts, ["M-03"])


def test_every_rejected_case_is_repaired_by_one_request_and_checked_in_round_2(
    tmp_path: Path,
) -> None:
    desk = Desk(tmp_path)
    result, voice = desk.run(REPAIRS)
    assert result == {**DONE, "sent": 2, "unavailable": None}
    assert voice.texts == [desk.texts["M-02"], desk.texts["M-04"]]
    for row, request in zip(desk.rows(), desk.plan["requests"], strict=True):
        assert {key: row[key] for key in row if key != "raw_reply"} == {
            "case_id": request["case_id"],
            "attempt": 1,
            "request_sha256": request["request_sha256"],
            "base_request_sha256": request["request_sha256"],
            "prompt_sha256": repair.PROMPT_SHA256,
            "repair_version": repair.REPAIR_VERSION,
            "status": "valid",
            "outcome": "repaired",
            "model": w.OPUS,
            # Only the registered counters of the usage are kept.
            "usage": {"output_tokens": 7},
            "session": w.SESSION,
            "elapsed_s": 0.25,
            "error": None,
        }
        assert row["raw_reply"] == REPAIRS[request["case_id"]]
    assert desk.build() == DONE
    narrow = built(narrowed(), M04, NAMES_04, SUPPLIED_04)
    assert t.rows_of(desk.repairs) == [t.repaired_m02(), narrow]
    assert desk.declared() == []
    assert desk.check() == {"status": "ok", **DONE}
    # A second run finds every case closed and asks nothing.
    again, silent = desk.run({})
    assert (again["sent"], silent.texts) == (0, [])
    # Round 2 is planned on the two files and checks every repair anew.
    summary = v.plan_round(desk.world.round_2, desk.world.drafts, desk.second)
    assert (summary["requests"], summary["declared_drops"]) == (2, 0)
    assert desk.check()["status"] == "ok"
    w.answer_round(desk.world, desk.world.round_2, desk.second, {})
    rows, register = t.apply(desk.world, desk.repairs)
    found = w.labels(rows)
    for case_id in ("M-02", "M-04"):
        assert found[case_id] == {
            "status": lv.SELF_CHECKED,
            "verifiers": [w.OPUS],
            "rubric_version": lv.RUBRIC_V3,
            "round": 2,
            "repair_author": lv.REPAIR_AUTHOR,
        }
    assert (found["M-01"]["round"], register["complete"]) == (1, True)
    assert rows[1] == {**t.repaired_m02(), **{key: rows[1][key] for key in lv.ADDED_FIELDS}}
    assert t.check(desk.world, desk.repairs)["status"] == "ok"


def test_check_refuses_files_and_a_round_2_that_are_not_of_the_store(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    desk.run(REPAIRS)
    desk.build()
    kept = desk.repairs.read_bytes()
    desk.repairs.write_bytes(v.jsonl([t.repaired_m02()]))
    with pytest.raises(ValueError, match="the repairs are not what the plan and the store give"):
        desk.check()
    desk.repairs.write_bytes(kept)
    no_repair = {"case_id": "M-04", "ground": lv.NO_REPAIR_DROP, "reason": "The label is right."}
    desk.drops.write_bytes(v.dump([no_repair]))
    with pytest.raises(ValueError, match="the declared drops are not what the plan and the store"):
        desk.check()
    desk.drops.write_bytes(v.dump([]))
    assert desk.check()["status"] == "ok"
    # A round 2 planned on one repair of the two is planned on another file.
    other = desk.world.write("other.jsonl", [t.repaired_m02()])
    v.plan_round(desk.world.round_2, desk.world.drafts, replace(desk.second, repairs=other))
    with pytest.raises(ValueError, match="round 2 is not planned on these repairs and declared"):
        desk.check()


def test_a_refused_reply_is_asked_again_with_its_refusal(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    result, voice = desk.run({"M-02": [said(AS_DRAFTED), said(label())], "M-04": REPAIRS["M-04"]})
    assert result == {**DONE, "sent": 3, "unavailable": None}
    first, second, _ = desk.rows()
    assert (first["attempt"], first["status"], first["outcome"]) == (1, "invalid", None)
    assert (first["error"], first["raw_reply"]) == (UNCHANGED, said(AS_DRAFTED))
    # The refused reply is kept with the record of its session, as a reply that counts is.
    assert first["session"] == w.SESSION
    again = repair.retry_text(desk.texts["M-02"], UNCHANGED, said(AS_DRAFTED))
    assert voice.texts[:2] == [desk.texts["M-02"], again]
    assert again.endswith(repair.PROMPT_CLOSING + "\n") and nameless(again)
    assert (second["attempt"], second["status"], second["outcome"]) == (2, "valid", "repaired")
    assert second["request_sha256"] == t.sha(again)
    assert second["base_request_sha256"] == first["request_sha256"] == t.sha(desk.texts["M-02"])
    desk.build()
    assert t.rows_of(desk.repairs)[0] == t.repaired_m02()


def test_a_refusal_of_the_script_goes_back_without_a_file_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = Desk(tmp_path)

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise drafting.DraftRefused(
            f"the label reads {t.BETA} beside {t.GAMMA[:-3]}, MANIFEST.md and C:/data/corpus"
        )

    monkeypatch.setattr(repair, "check_case", refuse)
    result, voice = desk.run(REPAIRS, limit=1)
    assert (result["sent"], result["dropped_without_valid_repair"]) == (3, 1)
    # A name of the corpus, a name the corpus only cites and a path: none goes back.
    assert {row["error"] for row in desk.rows()} == {
        "the label reads [file] beside [file], [file] and [file]"
    }
    assert all(nameless(text) for text in voice.texts)
    assert not any("MANIFEST" in text or "C:/data" in text for text in voice.texts[1:])


def test_a_refusal_that_still_names_a_file_goes_back_as_the_fixed_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = Desk(tmp_path)
    parse = repair.parse_reply
    named = f"the reply reads {t.BETA}"

    def refuse_first(text: str) -> Any:
        # A refusal of the form is stored as written, and this one names a file.
        if text == said(AS_DRAFTED):
            raise lv.ReplyFormatError(named)
        return parse(text)

    monkeypatch.setattr(repair, "parse_reply", refuse_first)
    answers = {"M-02": [said(AS_DRAFTED), said(label())], "M-04": REPAIRS["M-04"]}
    result, voice = desk.run(answers)
    assert result == {**DONE, "sent": 3, "unavailable": None}
    first, second, _ = desk.rows()
    assert (first["status"], first["error"]) == ("invalid", named)
    # The refusal stays in the store; the fixed sentence goes back in its place.
    again = repair.retry_text(desk.texts["M-02"], drafting.UNQUOTABLE, said(AS_DRAFTED))
    assert voice.texts[:2] == [desk.texts["M-02"], again]
    assert "previous reply to this request: the reply broke a rule the script cannot quote" in again
    assert nameless(again) and MASKER.leaks(drafting.UNQUOTABLE) == []
    assert (second["attempt"], second["status"]) == (2, "valid")
    assert second["request_sha256"] == t.sha(again)
    # The store is read back by the same rule, so the case is closed and not held for good.
    assert desk.build() == DONE
    assert desk.check()["status"] == "ok"


def test_a_new_span_is_held_to_the_texts_the_verifier_was_shown(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    _, _, held = tool.build_plan(desk.inputs)
    # M-04 is an answer without a trap: its request shows no scan, and its spans are all it has.
    assert held.scanned == {"M-02": SCAN_02, "M-04": []}
    elsewhere = label(
        spans=[{"id": "S1"}, {"id": "N1", "document": "D2", "text": "смежный документ"}],
        evidence_groups=[["S1"], ["N1"]],
    )
    answers = {"M-02": [said(elsewhere), said(BARRED), said(label())], "M-04": REPAIRS["M-04"]}
    result, _ = desk.run(answers)
    assert result == {**DONE, "sent": 4, "unavailable": None}
    first, second, third, _ = desk.rows()
    # The beta document has the words, in none of the texts the request supplies.
    assert first["error"].startswith("span N1 is not an excerpt of a text supplied for D2: ")
    # The delta lines are a passage of the scan: the span is found, and the bound refuses it.
    assert second["error"] == "the label cites a barred document: D4"
    assert (third["attempt"], third["status"], third["outcome"]) == (3, "valid", "repaired")


def test_three_refused_replies_drop_the_case(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    result, voice = desk.run({"M-02": REPAIRS["M-02"], "M-04": "There is nothing to repair."})
    assert result == {
        **DONE,
        "repaired": 1,
        "dropped_without_valid_repair": 1,
        "sent": 4,
        "unavailable": None,
    }
    rows = desk.rows()[1:]
    assert [(row["attempt"], row["status"], row["error"]) for row in rows] == [
        (number, "invalid", NOT_ONE) for number in (1, 2, 3)
    ]
    # Every later attempt carries the reply before it and no earlier one.
    header = f"\n{repair.REFUSAL_HEADER}\n"
    assert [text.count(header) for text in voice.texts] == [0, 0, 1, 1]
    # A fourth request is never sent.
    again, silent = desk.run({})
    assert (again["sent"], silent.texts) == (0, [])
    desk.build()
    assert desk.declared() == [
        {"case_id": "M-04", "ground": lv.NO_REPAIR_DROP, "reason": repair.NO_VALID_REPAIR}
    ]
    assert [row["case_id"] for row in t.rows_of(desk.repairs)] == ["M-02"]
    summary = v.plan_round(desk.world.round_2, desk.world.drafts, desk.second)
    assert (summary["requests"], summary["declared_drops"]) == (1, 1)
    assert desk.check()["dropped_without_valid_repair"] == 1


def test_a_declared_drop_is_kept_with_its_ground(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    reason = " The question joins\n two rules. "
    result, _ = desk.run(
        {
            "M-02": dropped(ground=lv.RESERVE_DROP, documents=["D4"]),
            "M-04": dropped(ground=lv.NO_REPAIR_DROP, reason=reason),
        }
    )
    assert result == {
        **DONE,
        "repaired": 0,
        "dropped_by_declaration": 2,
        "sent": 2,
        "unavailable": None,
    }
    assert [row["outcome"] for row in desk.rows()] == ["dropped", "dropped"]
    desk.build()
    assert desk.repairs.read_bytes() == b""
    # The documents of a drop are named as the register names them, not by their pseudonyms.
    assert desk.declared() == [
        {"case_id": "M-02", "ground": lv.RESERVE_DROP, "documents": [t.DELTA]},
        {"case_id": "M-04", "ground": lv.NO_REPAIR_DROP, "reason": "The question joins two rules."},
    ]
    summary = v.plan_round(desk.world.round_2, desk.world.drafts, desk.second)
    assert (summary["requests"], summary["declared_drops"]) == (0, 2)
    assert desk.check()["status"] == "ok"
    rows, _ = t.apply(desk.world, desk.repairs)
    assert [row["case_id"] for row in rows] == ["M-01", "M-03"]
    assert t.check(desk.world, desk.repairs)["status"] == "ok"


def test_a_drop_for_a_document_that_is_not_barred_is_refused(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    result, _ = desk.run(
        {"M-02": dropped(ground=lv.RESERVE_DROP, documents=["D1"]), "M-04": REPAIRS["M-04"]},
        limit=1,
    )
    assert (result["sent"], result["dropped_without_valid_repair"]) == (3, 1)
    assert desk.rows()[0]["error"] == "`documents` names what is not among `barred_documents`: D1"


def test_a_case_of_the_holdout_is_repaired_within_the_reserve(tmp_path: Path) -> None:
    rejected = {"H-01": t.reply("moderate", t.REJECT_3)}
    desk = Desk(tmp_path, [w.held_case()], holdout=True, rejected=rejected)
    # The beta document is named by the card of the reserve document and nothing of it is sent.
    assert desk.plan["requests"][0]["supplement"] == {
        "seed_document": "D1",
        "barred_documents": [],
        "reserve_ground": False,
        "complexity": "simple",
        "evidence_groups": [["S1"]],
    }
    for_reserve = dropped(ground=lv.RESERVE_DROP, documents=["D1"])
    result, voice = desk.run({"H-01": [for_reserve, said(tight())]})
    assert (result["repaired"], result["sent"]) == (1, 2)
    first, second = desk.rows()
    # The ground of the development split is not a ground of the holdout.
    assert (
        first["error"] == "`reserve_ground` is false: the ground of a drop is repair_not_possible"
    )
    assert (second["status"], second["outcome"]) == ("valid", "repaired")
    assert first["error"] in voice.texts[1]
    desk.build()
    (fixed,) = t.rows_of(desk.repairs)
    (span,) = fixed["evidence_spans"]
    assert t.TEXTS[t.DELTA][span["char_start"] : span["char_end"]] == t.BODIES[t.DELTA][3][1]
    assert fixed["documents"] == [t.DELTA]
    summary = v.plan_round(desk.world.round_2, desk.world.drafts, desk.second)
    assert (summary["requests"], summary["declared_drops"]) == (1, 0)


def test_an_unavailable_route_stops_the_run_and_takes_no_attempt(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    down = JudgeUnavailable("cli_missing", "Claude CLI is not installed")
    result, voice = desk.run({"M-02": down})
    assert (result["sent"], result["pending"], result["unavailable"]) == (1, 2, "cli_missing")
    assert len(voice.texts) == 1
    (row,) = desk.rows()
    assert (row["status"], row["error"], row["attempt"]) == ("unavailable", "cli_missing", 1)
    assert (row["raw_reply"], row["session"], row["outcome"]) == (None, None, None)
    with pytest.raises(ValueError, match="2 rejected cases have no reply yet"):
        desk.build()
    # The run resumes by case, and the case that was not answered is at its first attempt.
    result, _ = desk.run(REPAIRS)
    assert result == {**DONE, "sent": 2, "unavailable": None}
    assert [(row["case_id"], row["attempt"], row["status"]) for row in desk.rows()] == [
        ("M-02", 1, "unavailable"),
        ("M-02", 1, "valid"),
        ("M-04", 1, "valid"),
    ]
    assert desk.build() == DONE


@pytest.mark.parametrize(
    ("changes", "code", "model"),
    [
        ({"model": "another-model"}, "model_mismatch", "another-model"),
        ({"session": None}, "session_record", w.OPUS),
        ({"session": {**w.SESSION, "turns": 2}}, "session_record", w.OPUS),
    ],
)
def test_a_reply_the_route_does_not_vouch_for_is_no_repair(
    tmp_path: Path, changes: dict[str, Any], code: str, model: str
) -> None:
    desk = Desk(tmp_path)
    result, _ = desk.run(REPAIRS, **changes)
    assert (result["repaired"], result["sent"], result["unavailable"]) == (0, 1, code)
    (row,) = desk.rows()
    assert (row["status"], row["error"], row["model"]) == ("unavailable", code, model)
    # The reply is not kept: it is no reply of the registered route.
    assert (row["raw_reply"], row["session"]) == (None, None)


def test_limit_takes_up_that_many_cases(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    result, voice = desk.run({"M-02": [said(AS_DRAFTED), said(label())]}, limit=1)
    # A case is taken up with all its attempts.
    assert (result["sent"], result["repaired"], result["pending"]) == (2, 1, 1)
    assert len(voice.texts) == 2
    result, _ = desk.run({"M-04": REPAIRS["M-04"]}, limit=1)
    assert (result["sent"], result["pending"]) == (1, 0)


def other_request(rows: list[dict[str, Any]]) -> None:
    rows[0]["base_request_sha256"] = t.sha("another request")


def unknown_case(rows: list[dict[str, Any]]) -> None:
    rows[0]["case_id"] = "M-09"


def other_prompt(rows: list[dict[str, Any]]) -> None:
    rows[1]["prompt_sha256"] = t.sha("another prompt")


def odd_status(rows: list[dict[str, Any]]) -> None:
    rows[0]["status"] = "kept"


def later_attempt(rows: list[dict[str, Any]]) -> None:
    rows[0]["attempt"] = 2


def attempt_that_is_no_number(rows: list[dict[str, Any]]) -> None:
    rows[0]["attempt"] = True


def reply_after_a_valid_one(rows: list[dict[str, Any]]) -> None:
    rows.insert(1, dict(rows[0]))


def other_model(rows: list[dict[str, Any]]) -> None:
    rows[0]["model"] = "another-model"


def loaded_session(rows: list[dict[str, Any]]) -> None:
    rows[0]["session"] = {**w.SESSION, "loaded": {**w.SESSION["loaded"], "tools": ["Bash"]}}


def no_session(rows: list[dict[str, Any]]) -> None:
    del rows[1]["session"]


def other_text(rows: list[dict[str, Any]]) -> None:
    rows[1]["request_sha256"] = t.sha("another text")


def reply_that_does_not_pass(rows: list[dict[str, Any]]) -> None:
    rows[0]["raw_reply"] = said(AS_DRAFTED)


def outcome_of_another_reply(rows: list[dict[str, Any]]) -> None:
    rows[0]["outcome"] = "dropped"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (other_request, "the store holds a row that is not of this plan (M-02)"),
        (unknown_case, "the store holds a row that is not of this plan (M-09)"),
        (other_prompt, "the store holds a row that is not of this plan (M-04)"),
        (odd_status, "the store holds a row that is not of this plan (M-02)"),
        (later_attempt, "the store holds attempts that repair does not write: M-02"),
        (attempt_that_is_no_number, "the store holds attempts that repair does not write: M-02"),
        (reply_after_a_valid_one, "the store holds attempts that repair does not write: M-02"),
        (other_model, "a stored reply is not of the registered model: M-02"),
        (loaded_session, "a stored reply the route does not vouch for"),
        (no_session, "a stored reply the route does not vouch for"),
        (other_text, "a stored reply is not to the request of its row: M-04"),
        (
            reply_that_does_not_pass,
            f"a stored reply no longer passes the script: M-02 ({UNCHANGED})",
        ),
        (outcome_of_another_reply, "a stored reply is not what its row says: M-02"),
    ],
)
def test_a_store_that_repair_did_not_write_is_not_read(
    tmp_path: Path, change: Callable[[list[dict[str, Any]]], None], message: str
) -> None:
    desk = Desk(tmp_path)
    desk.run(REPAIRS)
    desk.build()
    desk.rewrite(change)
    with pytest.raises(ValueError, match=re.escape(message)):
        desk.build()
    with pytest.raises(ValueError, match=re.escape(message)):
        desk.check()


def test_a_refused_reply_cannot_be_edited_under_the_reply_that_followed_it(
    tmp_path: Path,
) -> None:
    desk = Desk(tmp_path)
    desk.run({"M-02": [said(AS_DRAFTED), said(label())], "M-04": REPAIRS["M-04"]})
    desk.build()
    kept = (desk.out / tool.STORE).read_bytes()

    def other_reply(rows: list[dict[str, Any]]) -> None:
        rows[0]["raw_reply"] = said(REORDERED)

    def other_refusal(rows: list[dict[str, Any]]) -> None:
        rows[0]["error"] = "the reply was fine"

    for change in (other_reply, other_refusal):
        desk.rewrite(change)
        # The second request held the first reply and its refusal: its SHA-256 no longer fits.
        with pytest.raises(ValueError, match="not to the request of its row: M-02"):
            desk.build()
        with pytest.raises(ValueError, match="not to the request of its row: M-02"):
            desk.run({})
        (desk.out / tool.STORE).write_bytes(kept)
    assert desk.check()["status"] == "ok"


def test_inputs_that_no_longer_give_the_plan_send_nothing(tmp_path: Path) -> None:
    desk = Desk(tmp_path)
    # The same drafts read as a set of the holdout: the bounds of every repair differ.
    held = replace(desk.inputs, drafts=replace(desk.world.drafts, holdout=True))
    voice = w.Voice(desk.texts, REPAIRS)
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan of these repairs"):
        tool.run_repairs(desk.out, held, client=voice)
    assert voice.texts == [] and not (desk.out / tool.STORE).exists()
    desk.run(REPAIRS)
    with pytest.raises(ValueError, match="the inputs no longer rebuild the plan of these repairs"):
        tool.build(desk.out, held, desk.repairs, desk.drops)
    assert not desk.repairs.exists() and not desk.drops.exists()


def another_version(plan: dict[str, Any]) -> None:
    plan["plan_version"] = 2


def another_repair_version(plan: dict[str, Any]) -> None:
    plan["repair_version"] = "devset-repair/v2"


def another_prompt(plan: dict[str, Any]) -> None:
    plan["prompt_sha256"] = t.sha("another prompt")


def no_requests(plan: dict[str, Any]) -> None:
    del plan["requests"]


def case_planned_twice(plan: dict[str, Any]) -> None:
    plan["requests"].append(plan["requests"][0])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (another_version, "plan_version is not supported"),
        (another_repair_version, "the plan is of another repair version"),
        (another_prompt, "the plan is of another prompt"),
        (no_requests, "plan.json does not hold a plan"),
        (case_planned_twice, "a case is planned twice"),
    ],
)
def test_a_plan_of_another_version_or_prompt_is_not_read(
    tmp_path: Path, change: Callable[[dict[str, Any]], None], message: str
) -> None:
    desk = Desk(tmp_path)
    plan = v.read_json(desk.out / "plan.json")
    change(plan)
    (desk.out / "plan.json").write_bytes(v.dump(plan))
    with pytest.raises(ValueError, match=message):
        desk.run(REPAIRS)
    assert not (desk.out / tool.STORE).exists()


def test_the_commands_of_a_set_read_and_write_its_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    desk = Desk(tmp_path)
    (desk.out / "plan.json").unlink()
    rounds = desk.world.inputs
    # The scan of a set is looked for under its own directory.
    (tmp_path / "wide-scan.json").write_bytes(rounds.scan.read_bytes())
    files = v.DraftSet(tmp_path, tmp_path / "verified.jsonl", tmp_path / "checks.json")
    monkeypatch.setitem(v.SETS, "development", files)
    monkeypatch.setattr(v, "load_set", lambda name: desk.world.drafts)
    voice = w.Voice(desk.texts, REPAIRS)
    asked: list[tuple[str, str]] = []

    def route(name: str, system_prompt: str) -> w.Voice:
        asked.append((name, system_prompt))
        return voice

    monkeypatch.setattr(v, "isolated_client", route)
    common = [
        "--set",
        "development",
        f"--corpus-dir={rounds.corpus_dir}",
        f"--archive={rounds.archive}",
    ]
    capsys.readouterr()
    assert tool.main(["build", *common]) == 2
    assert capsys.readouterr().out == "refused: a file cannot be read or written: plan.json\n"
    assert tool.main(["plan", *common]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "set": "development",
        "requests": 2,
        "without_request": 0,
        "characters": sum(map(len, desk.texts.values())),
    }
    # A run that leaves a case without a reply says so by its exit status.
    assert tool.main(["repair", *common, "--limit", "1"]) == 1
    assert tool.main(["repair", *common]) == 0
    # The route of a repair is the isolated one, with the system prompt of a repair.
    assert asked == [(w.OPUS, repair.SYSTEM_PROMPT)] * 2
    assert tool.main(["build", *common]) == 0
    assert t.rows_of(tmp_path / "repairs.jsonl")[0] == t.repaired_m02()
    assert json.loads((tmp_path / "drops.json").read_text(encoding="utf-8")) == []
    assert tool.main(["check", *common]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"status": "ok", **DONE}
    (tmp_path / "repairs.jsonl").write_bytes(b"")
    assert tool.main(["check", *common]) == 2
    refused = "refused: the repairs are not what the plan and the store give\n"
    assert capsys.readouterr().out == refused
    # The pilot was verified under v2: its repairs were not made by request.
    with pytest.raises(SystemExit):
        tool.main(["plan", "--set", "pilot"])
