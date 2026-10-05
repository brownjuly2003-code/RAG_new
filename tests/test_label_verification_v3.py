"""Label verification under rubric label-verification/v3 (plan step 1.3d).

No model and no network. The corpus, the drafts and the scan are those of
tests/test_label_verification.py; here they are a set of v3: one verifier, the model of the
session, asked by the isolated route, and every reply kept with the record of its session.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from evaluation import isolated_request as isolated
from evaluation import label_verification as lv
from evaluation.blinded_judge_clients import JudgeUnavailable
from scripts import devset_draft as draft_tool
from scripts import devset_label_verify as v
from tests import test_label_verification as t

OPUS = isolated.MODEL
SOL = "gpt-6.1-sol"
# The record of a session that loaded nothing: what the isolated route keeps beside a reply.
SESSION = {
    "cli_version": "9.9.9",
    "model": OPUS,
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}
# The scan of M-02 holds a passage of the reserve document.
SCANNED = {"M-02": [7, 4, 1], "M-03": [6, 5, 3]}
HELD_FACT = t.fact(
    t.DELTA, 1, "Досмотр по дельта-резерву проводит сертифицированный специалист", "досмотр"
)


def held_case() -> dict[str, Any]:
    """A case of the holdout: it is drafted from the one document of the reserve."""
    return t.case(
        "H-01",
        "Кто проводит досмотр по дельта-резерву?",
        "Досмотр по дельта-резерву проводит сертифицированный специалист службы безопасности.",
        t.DELTA,
        facts=(HELD_FACT,),
    )


class Voice:
    """The model of the session, answering from a script; every reply carries its session.

    `texts` are the request texts by case: a request is of the case whose text it begins
    with. `answers` gives, per case, one reply or the replies to successive attempts.
    """

    def __init__(
        self,
        texts: Mapping[str, str],
        answers: Mapping[str, Any],
        *,
        model: str = OPUS,
        session: Any = SESSION,
    ) -> None:
        self.bases = dict(texts)
        self.queues = {
            identity: list(given) if isinstance(given, list) else [given]
            for identity, given in answers.items()
        }
        self.model = model
        self.session = session
        self.texts: list[str] = []

    def grade(self, text: str) -> isolated.IsolatedReply:
        self.texts.append(text)
        identity = next(name for name, base in self.bases.items() if text.startswith(base))
        queue = self.queues[identity]
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, Exception):
            raise answer
        usage = {"output_tokens": 7, "service_tier": "standard"}
        return isolated.IsolatedReply(answer, self.model, usage, 0.25, self.session)


def v3_world(
    root: Path, cases: list[dict[str, Any]], *, generator: str = OPUS, holdout: bool = False
) -> t.World:
    """The fixture set of the verification tests as a set of rubric v3."""
    root.mkdir(exist_ok=True)
    world = t.world_of(root, cases)
    world.write("scan.json", t.scan_of(cases, SCANNED))
    drafts = replace(
        world.drafts,
        manifest={**world.drafts.manifest, "generator": generator},
        rubric=lv.RUBRIC_V3,
        holdout=holdout,
    )
    return replace(world, drafts=drafts)


def answer_round(
    world: t.World, out: Path, inputs: v.RoundInputs, given: Mapping[str, str]
) -> Voice:
    """Plan one round and answer it: the named cases get the given reply, the rest are
    confirmed at their registered severity."""
    v.plan_round(out, world.drafts, inputs)
    plan, texts = v.build_round(world.drafts, inputs)
    answers = {
        row["case_id"]: given.get(row["case_id"]) or t.reply(row["registered_severity"])
        for row in plan["requests"]
    }
    voice = Voice(texts, answers)
    v.verify(out, OPUS, world.drafts, inputs, client=voice)
    return voice


def first_round(world: t.World, rejected: Mapping[str, str]) -> Voice:
    return answer_round(world, world.round_1, world.inputs, rejected)


def store(world: t.World) -> Path:
    return world.round_1 / f"{OPUS}.jsonl"


def labels(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["case_id"]: row["label_check"] for row in rows}


# --- the verifier and its route ------------------------------------------------------------


def test_the_prompt_of_v3_is_that_of_v2_and_is_registered_in_the_spec() -> None:
    spec = (t.ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    recorded = re.findall(
        r"Prompt SHA-256 \(rubric label-verification/v3\): `([0-9a-f]{64})`", spec
    )
    assert recorded == [lv.PROMPT_SHA256]
    assert lv.prompt_sha256() == lv.PROMPT_SHA256


def test_the_system_prompt_of_the_verifier_is_registered_in_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = (t.ROOT / "docs/specs/semantic-precision-metrics.md").read_text(encoding="utf-8")
    recorded = re.findall(
        r"System prompt SHA-256 \(rubric label-verification/v3\): `([0-9a-f]{64})`", spec
    )
    assert recorded == [lv.CLI_SYSTEM_PROMPT_SHA256]
    assert t.sha(lv.CLI_SYSTEM_PROMPT) == lv.CLI_SYSTEM_PROMPT_SHA256
    settings = isolated.settings(lv.CLI_SYSTEM_PROMPT)
    assert settings["system_prompt_sha256"] == lv.CLI_SYSTEM_PROMPT_SHA256
    # It is the text the two rounds of the pilot were sent with under v2.
    for number in (1, 2):
        plan = t.ROOT / f"reports/devset/label-verification/round-{number}/plan.json"
        sent = re.findall(r'"system_prompt_sha256": "([0-9a-f]{64})"', plan.read_text("utf-8"))
        assert sent == [lv.CLI_SYSTEM_PROMPT_SHA256]
    # A plan is not made with another one.
    world = v3_world(tmp_path, t.drafts_cases())
    monkeypatch.setattr(lv, "CLI_SYSTEM_PROMPT", lv.CLI_SYSTEM_PROMPT + " Be brief.")
    with pytest.raises(ValueError, match="the system prompt is not the registered one"):
        v.build_round(world.drafts, world.inputs)


def test_a_set_of_v3_is_checked_by_the_model_of_the_session_on_the_isolated_route(
    tmp_path: Path,
) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    registered = {
        OPUS: {
            "model": OPUS,
            "vendor": "Anthropic",
            "route": isolated.ROUTE,
            "settings": isolated.settings(lv.CLI_SYSTEM_PROMPT),
        }
    }
    assert world.drafts.verifiers() == registered
    plan, _ = v.build_round(world.drafts, world.inputs)
    # The drafts are by the verifier's own vendor: v2 has no verifier for them, v3 registers
    # the check of a label by its author.
    assert plan["draft_author"] == {"model": OPUS, "vendor": "Anthropic"}
    assert (plan["rubric_version"], plan["verifiers"]) == (lv.RUBRIC_V3, registered)
    assert plan["prompt_sha256"] == lv.PROMPT_SHA256
    with pytest.raises(ValueError, match="no verifiers are registered for drafts by Anthropic"):
        v.build_round(replace(world.drafts, rubric=lv.RUBRIC_VERSION), world.inputs)


def test_a_plan_is_read_only_under_the_rubric_of_its_set(tmp_path: Path) -> None:
    world = v3_world(tmp_path, t.drafts_cases(), generator=SOL)
    v.plan_round(world.round_1, world.drafts, world.inputs)
    under_v2 = replace(world.drafts, rubric=lv.RUBRIC_VERSION)
    with pytest.raises(ValueError, match="not of the rubric these drafts are verified under"):
        v.load_round(world.round_1, under_v2)
    plan = v.read_json(world.round_1 / "plan.json")
    (world.round_1 / "plan.json").write_bytes(
        v.dump({**plan, "rubric_version": "label-verification/v4"})
    )
    with pytest.raises(ValueError, match="the plan is of another rubric version"):
        v.load_plan(world.round_1)


def test_a_verdict_of_v3_is_kept_with_the_record_of_its_session(tmp_path: Path) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    voice = first_round(world, {})
    rows = t.rows_of(store(world))
    assert [row["case_id"] for row in rows] == ["M-01", "M-02", "M-03", "M-04"]
    assert all(row["status"] == "valid" and row["session"] == SESSION for row in rows)
    assert all(row["rubric_version"] == lv.RUBRIC_V3 and row["model"] == OPUS for row in rows)
    # Only the registered counters of the usage are kept.
    assert all(row["usage"] == {"output_tokens": 7} for row in rows)
    assert len(voice.texts) == 4
    summary, _ = v.decide(world.round_1, world.drafts)
    assert (summary["confirmed"], summary["rejected"], summary["none"]) == (4, 0, 0)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"model": "another-model"}, "model_mismatch"),
        ({"session": None}, "session_record"),
        ({"session": {**SESSION, "turns": 2}}, "session_record"),
        (
            {"session": {**SESSION, "loaded": {**SESSION["loaded"], "tools": ["Bash"]}}},
            "session_record",
        ),
    ],
)
def test_a_reply_the_route_does_not_vouch_for_is_no_verdict(
    tmp_path: Path, changes: dict[str, Any], code: str
) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    v.plan_round(world.round_1, world.drafts, world.inputs)
    _, texts = v.build_round(world.drafts, world.inputs)
    voice = Voice(texts, dict.fromkeys(texts, t.reply()), **changes)
    result = v.verify(world.round_1, OPUS, world.drafts, world.inputs, client=voice)
    assert (result["valid"], result["sent"], result["unavailable"]) == (0, 1, code)
    (row,) = t.rows_of(store(world))
    assert (row["status"], row["error"]) == ("unavailable", code)
    assert (row["raw_reply"], row["session"]) == (None, None)


def test_a_reply_of_the_route_of_v2_is_no_verdict_of_v3(tmp_path: Path) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    v.plan_round(world.round_1, world.drafts, world.inputs)
    # The client of v2 returns a reply and nothing of the session that gave it.
    result = v.verify(world.round_1, OPUS, world.drafts, world.inputs, client=t.Fake(OPUS))
    assert (result["valid"], result["unavailable"]) == (0, "session_record")


def test_a_stored_verdict_without_the_record_of_a_clean_session_is_not_read(
    tmp_path: Path,
) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    first_round(world, {})
    rows = t.rows_of(store(world))
    rows[2]["session"] = {**SESSION, "turns": 2}
    store(world).write_bytes(v.jsonl(rows))
    with pytest.raises(ValueError, match="a stored reply the route does not vouch for"):
        v.load_round(world.round_1, world.drafts)
    del rows[2]["session"]
    store(world).write_bytes(v.jsonl(rows))
    with pytest.raises(ValueError, match="a stored reply the route does not vouch for"):
        v.decide(world.round_1, world.drafts)


def test_a_plan_of_v3_is_sent_by_the_isolated_route_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    v.plan_round(world.round_1, world.drafts, world.inputs)
    _, texts = v.build_round(world.drafts, world.inputs)
    voice = Voice(texts, dict.fromkeys(texts, t.reply()))
    asked: list[tuple[str, str]] = []

    def route(name: str, system_prompt: str = lv.CLI_SYSTEM_PROMPT) -> Voice:
        asked.append((name, system_prompt))
        return voice

    def old_route(name: str) -> Any:
        raise AssertionError("the route of v2 was asked for")

    monkeypatch.setattr(v, "isolated_client", route)
    monkeypatch.setattr(v, "make_client", old_route)
    result = v.verify(world.round_1, OPUS, world.drafts, world.inputs, limit=1)
    assert asked == [(OPUS, lv.CLI_SYSTEM_PROMPT)]
    assert (result["valid"], result["sent"]) == (1, 1)


def test_the_isolated_client_is_one_request_of_the_isolated_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str, str, float]] = []

    def send(
        executable: str, system_prompt: str, message: str, *, timeout_s: float
    ) -> isolated.IsolatedReply:
        sent.append((executable, system_prompt, message, timeout_s))
        return isolated.IsolatedReply("{}", OPUS, {}, 0.1, SESSION)

    monkeypatch.setattr(isolated, "send", send)
    monkeypatch.setenv("RAG_VERIFY_CLAUDE_CLI", " C:/tools/claude.cmd ")
    client = v.isolated_client(OPUS, "A system prompt.")
    assert client.grade("request").session == SESSION
    assert sent == [("C:/tools/claude.cmd", "A system prompt.", "request", v.CLI_TIMEOUT_S)]
    with pytest.raises(ValueError, match="no route is registered for the verifier another"):
        v.isolated_client("another-model")
    monkeypatch.delenv("RAG_VERIFY_CLAUDE_CLI")
    monkeypatch.setattr(isolated, "find_cli", lambda: None)
    with pytest.raises(JudgeUnavailable) as raised:
        v.isolated_client(OPUS).grade("request")
    assert raised.value.code == "cli_missing"


# --- the word of a confirmed label ---------------------------------------------------------


def test_a_label_checked_by_its_own_author_is_named_self_checked(tmp_path: Path) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    first_round(world, {})
    rows, register = t.apply(world)
    assert len(rows) == 4
    for label in labels(rows).values():
        assert label == {
            "status": lv.SELF_CHECKED,
            "verifiers": [OPUS],
            "rubric_version": lv.RUBRIC_V3,
            "round": 1,
        }
    assert register["rubric_version"] == lv.RUBRIC_V3
    assert register["draft_author"] == {"model": OPUS, "vendor": "Anthropic"}
    assert register["complete"] is True
    assert t.check(world)["status"] == "ok"


def test_a_draft_of_another_vendor_keeps_its_word_until_it_is_repaired(tmp_path: Path) -> None:
    world = v3_world(tmp_path, t.drafts_cases(), generator=SOL)
    first_round(world, {"M-02": t.reply("high", t.REJECT_3)})
    repairs = world.write("repairs.jsonl", [t.repaired_m02()])
    answer_round(world, world.round_2, replace(world.second, repairs=repairs), {})
    rows, _ = t.apply(world, repairs)
    found = labels(rows)
    assert found["M-01"]["status"] == "single_model_verified"
    assert "repair_author" not in found["M-01"]
    # The label checked in round 2 was written by the model that checked it.
    assert found["M-02"] == {
        "status": lv.SELF_CHECKED,
        "verifiers": [OPUS],
        "rubric_version": lv.RUBRIC_V3,
        "round": 2,
        "repair_author": lv.REPAIR_AUTHOR,
    }
    assert t.check(world, repairs)["status"] == "ok"


def test_a_label_repaired_before_it_came_into_the_set_is_its_repairers(tmp_path: Path) -> None:
    world = v3_world(tmp_path, t.drafts_cases(), generator=SOL)
    world = replace(world, drafts=replace(world.drafts, label_authors={"M-02": lv.REPAIR_AUTHOR}))
    assert world.drafts.label_author("M-02") == lv.REPAIR_AUTHOR
    assert world.drafts.label_author("M-01") == {"model": SOL, "vendor": "OpenAI"}
    first_round(world, {})
    rows, _ = t.apply(world)
    found = labels(rows)
    assert found["M-02"] == {
        "status": lv.SELF_CHECKED,
        "verifiers": [OPUS],
        "rubric_version": lv.RUBRIC_V3,
        "round": 1,
        "repair_author": lv.REPAIR_AUTHOR,
    }
    assert found["M-01"]["status"] == "single_model_verified"
    assert t.check(world)["status"] == "ok"
    # The word is recomputed from the author of the label, not read from the row.
    verified, _ = t.outputs(world)
    rows[1]["label_check"]["status"] = "single_model_verified"
    verified.write_bytes(v.jsonl(rows))
    with pytest.raises(ValueError, match="the verified set is not what the decisions give"):
        t.check(world)


def test_the_word_of_v2_does_not_look_at_the_author() -> None:
    verifiers = {OPUS: lv.VERIFIERS[OPUS]}
    anthropic, openai = lv.draft_author(OPUS), lv.draft_author(SOL)
    assert lv.label_status(lv.RUBRIC_VERSION, anthropic, verifiers) == "single_model_verified"
    assert lv.label_status(lv.RUBRIC_V3, anthropic, verifiers) == lv.SELF_CHECKED
    assert lv.label_status(lv.RUBRIC_V3, openai, verifiers) == "single_model_verified"
    assert lv.RUBRICS == (lv.RUBRIC_VERSION, lv.RUBRIC_V3)


# --- the holdout ---------------------------------------------------------------------------


def test_a_case_of_the_holdout_is_bound_to_the_reserve(tmp_path: Path) -> None:
    held = v3_world(tmp_path / "holdout", [held_case()], holdout=True).drafts
    assert held.barred == {t.ALPHA, t.BETA, t.GAMMA}
    assert held.barred_name == "a document outside the holdout reserve"
    needs_reserve = {"case_id": "H-01", "ground": lv.RESERVE_DROP, "documents": [t.DELTA]}
    no_repair = {"case_id": "H-01", "ground": lv.NO_REPAIR_DROP, "reason": "The question is vague."}
    assert held.drop_problem(needs_reserve) == (
        "a case of the holdout has no ground repair_needs_reserve"
    )
    assert held.drop_problem(no_repair) is None
    outside = t.case(
        "H-01",
        held_case()["question"],
        held_case()["reference_answer"],
        t.DELTA,
        (t.BETA,),
        (HELD_FACT, t.BETA_FACT),
    )
    assert v.repair_problem(held, outside) == (
        f"a repair cites a document outside the holdout reserve: {t.BETA}"
    )
    development = v3_world(tmp_path / "development", t.drafts_cases()).drafts
    assert development.barred == {t.DELTA}
    assert development.barred_name == "the holdout reserve"
    assert development.drop_problem({**needs_reserve, "case_id": "M-02"}) is None


def test_a_round_of_the_holdout_is_planned_and_decided(tmp_path: Path) -> None:
    world = v3_world(tmp_path, [held_case()], holdout=True)
    first_round(world, {})
    rows, register = t.apply(world)
    assert labels(rows)["H-01"]["status"] == lv.SELF_CHECKED
    assert register["complete"] is True
    assert register["summary"]["verified_by_class"] == {"single-doc": 1}


# --- the sets ------------------------------------------------------------------------------


def test_the_sets_of_step_1_3d_keep_their_rounds_and_outputs_apart() -> None:
    assert sorted(v.SETS) == [
        "development",
        "development-replacements",
        "holdout",
        "holdout-replacements",
        "pilot",
        "pilot-v3",
    ]
    assert v.SETS["pilot"] == v.DraftSet(v.BASE, v.VERIFIED, v.REGISTER)
    chosen = v.SETS["holdout-replacements"]
    assert chosen.base == v.BASE / "v3" / "holdout-replacements"
    assert chosen.verified == v.EVALUATION / "devset_holdout_replacements_verified.jsonl"
    assert chosen.register == v.EVALUATION / "devset_holdout_replacements_label_checks.json"
    written = [path for files in v.SETS.values() for path in (files.verified, files.register)]
    assert len(set(written)) == len(written)
    assert len({files.base for files in v.SETS.values()}) == len(v.SETS)
    # The replacements of a split start from the register its first verification writes.
    for split in ("development", "holdout"):
        assert draft_tool.checks_path(split) == v.SETS[split].register


def test_apply_writes_neither_the_drafts_nor_the_outputs_of_another_set(tmp_path: Path) -> None:
    kept = set(v.protected("development"))
    assert set(v.PROTECTED) <= kept
    assert not {v.SETS["development"].verified, v.SETS["development"].register} & kept
    assert {
        v.SETS["holdout"].verified,
        v.SETS["pilot"].register,
        draft_tool.drafts_path("development"),
        draft_tool.manifest_path("holdout", True),
    } <= kept
    world = v3_world(tmp_path, t.drafts_cases())
    first_round(world, {})
    with pytest.raises(ValueError, match="do not replace the drafts"):
        v.apply(
            world.drafts,
            world.round_1,
            None,
            repairs=None,
            verified=tmp_path / "verified.jsonl",
            register=tmp_path / "taken.json",
            protected=(tmp_path / "taken.json",),
        )
    assert not (tmp_path / "verified.jsonl").exists()


def test_a_set_is_loaded_by_its_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    def pilot() -> str:
        seen.append("pilot")
        return "the pilot"

    def pilot_again() -> str:
        seen.append("pilot-v3")
        return "the pilot under v3"

    def split(name: str, replacement: bool = False) -> str:
        seen.append((name, replacement))
        return "a split"

    monkeypatch.setattr(v, "pilot_drafts", pilot)
    monkeypatch.setattr(v, "pilot_v3_drafts", pilot_again)
    monkeypatch.setattr(v, "split_drafts", split)
    names = ("pilot", "pilot-v3", "development", "holdout-replacements")
    assert [v.load_set(name) for name in names] == [
        "the pilot",
        "the pilot under v3",
        "a split",
        "a split",
    ]
    assert seen == ["pilot", "pilot-v3", ("development", False), ("holdout", True)]


def test_the_commands_of_a_set_default_to_its_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    first_round(world, {})
    files = v.DraftSet(tmp_path, tmp_path / "verified.jsonl", tmp_path / "checks.json")
    monkeypatch.setitem(v.SETS, "development", files)
    monkeypatch.setattr(v, "load_set", lambda name: world.drafts)
    assert v.main(["decide", "--set", "development", "--round", "1"]) == 0
    assert v.main(["apply", "--set", "development"]) == 0
    assert v.main(["check", "--set", "development"]) == 0
    register = json.loads(files.register.read_text(encoding="utf-8"))
    assert register["rubric_version"] == lv.RUBRIC_V3
    assert len(t.rows_of(files.verified)) == 4


def test_round_1_of_development_waits_for_the_register_of_pilot_v3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = v3_world(tmp_path, t.drafts_cases())
    register = tmp_path / "pilot_v3_checks.json"
    monkeypatch.setattr(draft_tool, "checks_path", lambda split: register)
    gated = replace(world.drafts, gate=v.pilot_closed)
    waits = "round 1 of development waits for pilot-v3: "
    with pytest.raises(ValueError, match=waits + "the verification of pilot-v3 is not complete"):
        v.build_round(gated, world.inputs)
    verified = {"case_id": "P-01", "state": "verified"}
    register.write_bytes(v.dump({"complete": False, "cases": [verified]}))
    with pytest.raises(ValueError, match=waits + "the verification of pilot-v3 is not complete"):
        v.plan_round(world.round_1, gated, world.inputs)
    # A dropped pilot case is seated with the dropped drafts of development: the code that
    # seats it comes before the first check of a development draft, not after its verdicts.
    dropped = {"case_id": "P-07", "state": "dropped"}
    register.write_bytes(v.dump({"complete": True, "cases": [verified, dropped]}))
    with pytest.raises(ValueError, match=waits + "pilot-v3 holds dropped cases, .*: P-07"):
        v.plan_round(world.round_1, gated, world.inputs)
    assert not (world.round_1 / "plan.json").exists()
    register.write_bytes(v.dump({"complete": True, "cases": [verified]}))
    plan, _ = v.build_round(gated, world.inputs)
    assert plan == v.build_round(world.drafts, world.inputs)[0]
    # The gate is of round 1: a later round is planned on what round 1 left.
    first_round(replace(world, drafts=gated), {})
    register.unlink()
    assert v.build_round(gated, world.second)[0]["requests"] == []


def test_the_verified_pilot_set_comes_back_as_a_set_of_v3() -> None:
    drafts = v.pilot_v3_drafts()
    rows = v.read_jsonl(v.VERIFIED)
    assert (drafts.rubric, drafts.holdout) == (lv.RUBRIC_V3, False)
    assert [case["case_id"] for case in drafts.cases] == [row["case_id"] for row in rows]
    assert not any(set(case) & set(lv.ADDED_FIELDS) for case in drafts.cases)
    assert drafts.manifest["jsonl_sha256"] == v.sha256_bytes(v.VERIFIED.read_bytes())
    repaired = {row["case_id"] for row in rows if "repair_author" in row["label_check"]}
    assert set(drafts.label_authors or {}) == repaired
    assert (len(rows), len(repaired)) == (30, 5)
    # Twenty-five drafts of their author and five labels of the model that checks them now.
    words = Counter(
        lv.label_status(drafts.rubric, drafts.label_author(case["case_id"]), drafts.verifiers())
        for case in drafts.cases
    )
    assert words == {"single_model_verified": 25, lv.SELF_CHECKED: 5}


def test_a_verified_pilot_set_its_register_does_not_give_is_not_checked_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    edited = tmp_path / "verified.jsonl"
    edited.write_bytes(v.VERIFIED.read_bytes() + b"\n")
    monkeypatch.setattr(v, "VERIFIED", edited)
    with pytest.raises(ValueError, match="not the one its register gives"):
        v.pilot_v3_drafts()


def test_the_drafts_of_a_split_are_a_set_of_v3_held_to_the_draft_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = [held_case()]
    drafts_file = tmp_path / "drafts.jsonl"
    drafts_file.write_bytes(v.jsonl(cases))
    manifest_file = tmp_path / "manifest.json"
    manifest = {
        "generator": OPUS,
        "jsonl_sha256": t.sha(v.jsonl(cases)),
        "families_sha256": t.sha("families"),
    }
    manifest_file.write_bytes(v.dump(manifest))
    checked: list[Any] = []

    def inputs_of(split: str, directory: Path, *, replacement: bool = False) -> Any:
        return (split, directory, replacement)

    def check(out: Path, inputs: Any, drafts: Path, manifest: Path) -> None:
        checked.append((out, inputs, drafts, manifest))

    monkeypatch.setattr(draft_tool, "drafts_path", lambda split, replacement=False: drafts_file)
    monkeypatch.setattr(draft_tool, "manifest_path", lambda split, replacement=False: manifest_file)
    monkeypatch.setattr(draft_tool, "load_inputs", inputs_of)
    monkeypatch.setattr(draft_tool, "check", check)
    held = v.split_drafts("holdout", True)
    assert (held.rubric, held.holdout, held.cases) == (lv.RUBRIC_V3, True, cases)
    assert held.author == {"model": OPUS, "vendor": "Anthropic"}
    assert held.manifest == manifest
    assert not v.split_drafts("development").holdout
    # Only the first drafts of development wait for the second check of the pilot.
    assert v.split_drafts("development").gate is v.pilot_closed
    assert (held.gate, v.split_drafts("development", True).gate) == (None, None)
    assert v.split_drafts("holdout").gate is None
    # The verify script of the set is the check of the draft tool on the files of the split.
    held.verify(tmp_path)
    assert checked == [
        (
            draft_tool.out_dir("holdout", True),
            ("holdout", tmp_path, True),
            drafts_file,
            manifest_file,
        )
    ]
