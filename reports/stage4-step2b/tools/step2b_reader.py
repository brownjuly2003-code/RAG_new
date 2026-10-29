"""Stage 4, step 2b's reader: the continuation read cold, beside step 2's warm one and on V4's 80.

docs/specs/stage4-step2b-continuation-labels.md, registered with this tool before the first
request. On the Mac after the replay, any Python 3.11, the standard library only:

  python -I step2b_reader.py OUT RUN_DIR PLAN LABELS STEP2_DIR

RUN_DIR is step 2b's folder: bridge/ and labels/, each the OUT of step2b_replay.py's run of that
phase (launch.json, continuations.jsonl and, where a call failed, failures.jsonl), and
environment.jsonl, stand_env.py's lines taken before the bridge, between the phases and after
the 80. PLAN and LABELS are the 80's inputs: the handover signals' plan, which keeps each of
V4's answers' classic self-evaluation as its quality_score, and the judge's grades of the same
answers. STEP2_DIR holds step 2's records of its runs, step2.json of s2-both and
step2.s2-both-r2.json: the asks their reader read, each with its case file's SHA-256 and its two
self-evaluations.

The bridge: each ask step 2 read, its continuation warm as step 2 asked it and cold as the
replay asked it again. A pair is readable when the bridge's gate passed and its line holds. Each
side's route is the stream's: a score of -1 (none) to the classic, which then decides; under 80
to a person; 80 and over to the answer as it stands. The 80: the 17 targets (graded bad, or
declined) and the 63 goods (graded good, not declined), signal_record.py's classes, the targets
first, each class in the plan's order. An answer is flagged when its score is under 80, the
stream's route to a person. A pair is an answer and its continuation's line, readable when the
80's gate passed and the line holds. Its effective score is the continuation's where it scored
1-100 and the classic's saved one where it did not, as the chat then falls back to the classic;
a line without a score (-1) is counted apart, by its outcome. The readings - the bridge, the
scores held, the catches of the 17, the over-marks of the 63 and the signal - are functions of
the pairs alone; the first answer's stop, of the bridge's first line alone.

OUT holds numbers, enums, ids, file names, the paths named here and SHA-256 strings: no
question, answer, prompt, document or reply, and of an error its type only. Prints the gates,
the first answer's stop and the spec's readings; refuses an existing OUT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "stage4-step2b-reader/v1"
SPEC = "docs/specs/stage4-step2b-continuation-labels.md"
HERE = Path(__file__).resolve().parent
TOOLS = ("step2b_reader.py",)
NOT_EVIDENCE = "NOT_EVIDENCE"
# The stand's commit: step 2's, on which step 2 closed.
CODE_SHA = "57420db746e0510465bb5a08b7610e092b32e650"
REPLAY_SCHEMA = "stage4-step2b/v1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
KEY = "aircargo"
STREAM_PATH = "provider"
PROMPT_ID = "SELF_EVAL_CONTINUATION_V1"
INSTRUCTION_SHA256 = "5062156de04ad24c573d9d6161a81aeb34fae4c82ba49e7f537dabff4104000c"
NUM_CTX = 4096
INPUT_LIMIT = 3443
PARAMS = {"temperature": 0.0, "max_tokens": 128}
ANSWER_STOP = 255.0
RELOAD_EVERY = 5
OLLAMA_VERSION = "0.33.2"
# What the replay must have run: this folder's replay, V5's replay whose loading and rebuild it
# uses as they are, and the template V5's Builder reads.
REPLAY_SHA256 = {
    "step2b_replay.py": "7d0b46bb26943c5c2209bdfc7b827a720fcdb67365902d70d3eb49d21b21ff19",
    "replay.py": "ca954c59710e93925cc923f5b2a7f175ce86f7e1fa7b96a46d3b3bbeec4d6eed",
    "qa_prompt_v5.txt": "835b0f2cf1ac7bc86ad30605367d81457b02e7436a5a5071642a5b881471c276",
}
# The 80's inputs as committed: reports/handover-signal/d260d95/plan.json and
# reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl.
INPUTS_SHA256 = {
    "plan": "30e0a598e6f6edabd7d72ac64b4ce4923655ed9845c5852f02107e345e9df16e",
    "labels": "a1413cbadc5b7f1e629f9ad16ca77c7baba36870122c21a678a5dfd57b1b6718",
}
# Step 2's records of its runs as committed (reports/stage4-step2/57420db/): s2-both's and
# s2-both-r2's.
STEP2_LABELS = ("s2-both", "s2-both-r2")
STEP2_RECORDS = {"s2-both": "step2.json", "s2-both-r2": "step2.s2-both-r2.json"}
STEP2_SHA256 = {
    "s2-both": "e28b0fcbf032f2e745593d07baa01db9536a29f5ed52d961534779e78919e15f",
    "s2-both-r2": "2cc0d1dd284d4790bb92122a8c42eec59db108a0a4fadc40abaae6e03b5fa65c",
}
TARGETS, GOODS = 17, 63
# The classic's saved scores on them: S1 and S1' of docs/evidence/handover-signal-v4-aircargo.md.
CLASSIC = {"caught": 2, "over_marked": 0}
CLASSIC_UNDER_100 = {"caught": 3, "over_marked": 4}
PHASES = ("bridge", "labels")
CLASSES = ("target", "good")
OUTCOMES = ("scored", "not one integer", "window", "error")
CHECKS = {
    "bridge": ("files", "sent", "answer", "stream"),
    "labels": ("files", "prompt_sha256", "parity", "sent", "answer", "answer_sha256", "stream"),
}
IDS = {
    "bridge": ("n", "run", "case_id", "case_file", "case_sha256"),
    "labels": (
        "n",
        "class",
        "item",
        "run",
        "case_id",
        "case_file",
        "prompt_file",
        "prompt_sha256",
        "answer_sha256",
    ),
}
COUNTERS = ("prompt_tokens", "prompt_sec", "eval_tokens", "eval_sec")
# A reload before an answer: the unload's seconds and polls, the load's seconds.
RELOAD = ("unload_sec", "polls", "load_sec")
SIDES = ("classic", "effective")
# What the replay's first segment froze, and what each segment adds.
FROZEN = (
    "schema",
    "spec",
    "phase",
    "key",
    "code_sha",
    "model",
    "model_digest",
    "stream_path",
    "prompt_id",
    "instruction_sha256",
    "num_ctx",
    "input_limit",
    "params",
    "answer_stop_sec",
    "reload_every",
    "tools_sha256",
    "inputs_sha256",
    "runs",
    "planned",
)
LAUNCH_KEYS = (*FROZEN, "started", "finished", "model_errors", "answers", "status", "segments")
# A segment's end: the first answer's, an interruption the spec resumes from, or the whole.
INTERRUPTIONS = ("stopped", "answer_stop", "model_error", "unload_stop", "load_stop")
STATUSES = ("first", *INTERRUPTIONS, "complete")
MAX_SEGMENTS = 6
REPLAY_FILES = ("launch.json", "continuations.jsonl", "failures.jsonl")
# The spec's readings, frozen with it.
THRESHOLD = 80
PRINTED_THRESHOLD = 100
MIN_BRIDGE = 10
BRIDGE_DIFFS = 1
MAX_NO_SCORE = 6
OVER_MARGIN = 1
ALPHA = 0.05
SIGNAL_PARTS = ("scores", "catches", "over_marks")


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def median(values: Sequence[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def num(value: Any) -> int | float | None:
    """A number as it is; anything else (a bool included) is None."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def an_id(value: Any) -> str | None:
    """A run, case or file name as it is; anything else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.-]+", str(value)) else "<not an id>"


def a_name(value: Any) -> str | None:
    """A model name, a path named here or an enum as it is (a tag holds ":"); else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[\w.:/-]+", str(value)) else "<not a name>"


def a_sha(value: Any) -> str | None:
    """A SHA-256 string as it is; anything else masked."""
    if value is None:
        return None
    return str(value) if re.fullmatch(r"[0-9a-f]{64}", str(value)) else "<not a sha256>"


def a_stamp(value: Any) -> str | None:
    """An ISO time as the replay and stand_env.py write it; anything else masked."""
    if value is None:
        return None
    stamp = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:\d\d|Z)?"
    return str(value) if re.fullmatch(stamp, str(value)) else "<not a time>"


def a_time(value: str | None) -> datetime | None:
    """A kept stamp as a time, None if it is none or names no zone."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def error_type(value: Any) -> str | None:
    """An error's type, the text before its first colon; never its message."""
    if value is None or value is False:
        return None
    head = str(value).split(":", 1)[0].strip()
    return head if re.fullmatch(r"[A-Za-z_][\w.]*", head) else "<error>"


def rounded(value: float | None, places: int = 3) -> float | None:
    return None if value is None else round(value, places)


def a_score(value: Any) -> int | None:
    """A self-evaluation's score, an integer as it is (-1 is the code's "no score"); else None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def scored(value: Any) -> bool:
    return a_score(value) is not None and 1 <= value <= 100


def route_of(score: int) -> str:
    """The stream's route for a continuation's score (api/routers/conversation.py): -1 to the
    classic, which then decides; under 80 to a person; else the answer as it stands."""
    if score == -1:
        return "classic"
    return "auto" if score >= THRESHOLD else "human"


def sign_p(wins: int, losses: int) -> float:
    """The exact two-sided sign test at one half: on discordant pairs, the exact McNemar test."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def wilson(hits: int, n: int, z: float = 1.96) -> list[float] | None:
    """Wilson's 95 % limits, as signal_record.py's, rounded to four places."""
    if n == 0:
        return None
    share = hits / n
    denominator = 1 + z * z / n
    centre = (share + z * z / (2 * n)) / denominator
    half = z * math.sqrt(share * (1 - share) / n + z * z / (4 * n * n)) / denominator
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def read_rows(
    path: Path, notes: list[str], name: str, *, optional: bool = False
) -> tuple[list[dict[str, Any]], int]:
    """A JSON-lines file's objects, and how many of its lines are none."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        if not (optional and not path.exists()):
            notes.append(f"{name}: not readable")
        return [], 0
    rows, bad = [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if isinstance(row, dict):
            rows.append(row)
        else:
            bad += 1
            notes.append(f"{name}: a line that is no JSON object")
    return rows, bad


def read_inputs(plan_path: Path, labels_path: Path, notes: list[str]) -> dict[str, Any]:
    """The 80 answers the replay was to score, in its order, each with its class and the
    classic's saved score and its source; ids, file names and SHA-256 strings only."""
    try:
        items = json.loads(plan_path.read_text(encoding="utf-8"))["items"]
        items = [item for item in items if isinstance(item, dict)]
    except (OSError, ValueError, KeyError, TypeError):
        notes.append("inputs: no readable plan")
        items = []
    rows, _ = read_rows(labels_path, notes, "labels")
    by_case = {(row.get("run"), row.get("case_id")): row for row in rows}
    targets, goods, unjudged = [], [], 0
    for item in items:
        row = by_case.get((item.get("run"), item.get("case_id")))
        if (
            row is None
            or row.get("prompt_sha256") != item.get("prompt_sha256")
            or row.get("missing")
        ):
            unjudged += 1
            continue
        if row.get("grade") == "bad" or row.get("answers_question") == "declined":
            targets.append(item)
        elif row.get("grade") == "good":
            goods.append(item)
    if unjudged:
        notes.append(f"inputs: {unjudged} plan answers the judge did not grade as planned")
    if len(by_case) != len(items):
        notes.append("inputs: the judge holds answers the plan does not")
    order = [("target", item) for item in targets] + [("good", item) for item in goods]
    answers: list[dict[str, Any]] = []
    for n, (kind, item) in enumerate(order, start=1):
        source = item.get("quality_source")
        answers.append(
            {
                "n": n,
                "class": kind,
                "item": num(item.get("item")),
                "run": an_id(item.get("run")),
                "case_id": an_id(item.get("case_id")),
                "case_file": an_id(item.get("case_file")),
                "prompt_file": an_id(item.get("prompt_file")),
                "prompt_sha256": a_sha(item.get("prompt_sha256")),
                "answer_sha256": a_sha(item.get("answer_sha256")),
                "classic": {
                    "score": a_score(item.get("quality_score")),
                    "source": a_name(source) if isinstance(source, str) else None,
                },
            }
        )
    classes = (len(targets), len(goods)) == (TARGETS, GOODS)
    classes = classes and not unjudged and len(by_case) == len(items)
    all_scored = all(
        answer["classic"]["source"] == "llm" and scored(answer["classic"]["score"])
        for answer in answers
    )

    def counts(threshold: int) -> dict[str, int]:
        flagged = [
            answer["class"]
            for answer in answers
            if scored(answer["classic"]["score"]) and answer["classic"]["score"] < threshold
        ]
        return {"caught": flagged.count("target"), "over_marked": flagged.count("good")}

    classic = {"at_80": counts(THRESHOLD), "under_100": counts(PRINTED_THRESHOLD)}
    return {
        "plan": str(plan_path),
        "labels": str(labels_path),
        "sha256": {"plan": sha256(plan_path), "labels": sha256(labels_path)},
        "targets": len(targets),
        "goods": len(goods),
        "unjudged": unjudged,
        "classic": classic,
        "classes_hold": bool(classes),
        "classic_holds": bool(
            classes
            and all_scored
            and classic["at_80"] == CLASSIC
            and classic["under_100"] == CLASSIC_UNDER_100
        ),
        "answers": answers,
    }


def a_side(value: Any) -> dict[str, Any] | None:
    """A self-evaluation as a result or a line keeps it: its score, seconds and counters."""
    if not isinstance(value, dict):
        return None
    sec = num(value.get("sec"))
    out: dict[str, Any] = {"score": a_score(value.get("score"))}
    out["sec"] = sec if sec is not None and sec >= 0 else None
    out.update({key: num(value.get(key)) for key in COUNTERS})
    return out


def read_step2(folder: Path) -> dict[str, Any]:
    """The asks step 2's records read, each run's in its order, s2-both's first: each with its
    case file, that file's SHA-256 and the continuation's warm score, seconds and counters."""
    notes: list[str] = []
    asks: list[dict[str, Any]] = []
    planned: dict[str, int] = {}
    for label in STEP2_LABELS:
        path = folder / STEP2_RECORDS[label]
        try:
            run = json.loads(path.read_text(encoding="utf-8"))["run"]
            given = [ask for ask in run["asks"] if isinstance(ask, dict)]
            if run.get("label") != label:
                raise ValueError("another run's record")
        except (OSError, ValueError, KeyError, TypeError):
            notes.append(f"step 2: no readable record of {label}")
            continue
        read = [ask for ask in given if ask.get("read") is True]
        read.sort(key=lambda ask: (num(ask.get("index")) is None, num(ask.get("index")) or 0))
        planned[label] = len(read)
        for ask in read:
            index, case_id = num(ask.get("index")), an_id(ask.get("case_id"))
            both = ask.get("self_eval")
            side = a_side(both.get("continuation")) if isinstance(both, dict) else None
            asks.append(
                {
                    "n": len(asks) + 1,
                    "run": label,
                    "case_id": case_id,
                    "case_file": f"{index:02d}-{case_id}.json" if isinstance(index, int) else None,
                    "case_sha256": a_sha(ask.get("sha256")),
                    "warm": side,
                }
            )
    sha = {label: sha256(folder / name) for label, name in STEP2_RECORDS.items()}
    return {
        "dir": str(folder),
        "sha256": sha,
        "planned": planned,
        "asks": asks,
        "holds": sha == STEP2_SHA256 and not notes,
        "notes": notes,
    }


def read_line(row: dict[str, Any], phase: str) -> dict[str, Any]:
    """One continuation line, every field masked to its kind: ids, checks, the outcome, the
    score, the seconds, Ollama's counters, the window's numbers and the reload."""
    given = row.get("checks")
    checks: dict[str, Any] = given if isinstance(given, dict) else {}
    line: dict[str, Any] = {
        "phase": row.get("phase") if row.get("phase") in PHASES else None,
        "n": num(row.get("n")),
        "segment": num(row.get("segment")),
        "class": row.get("class") if row.get("class") in CLASSES else None,
        "item": num(row.get("item")),
        "run": an_id(row.get("run")),
        "case_id": an_id(row.get("case_id")),
        "case_file": an_id(row.get("case_file")),
        "prompt_file": an_id(row.get("prompt_file")),
        "case_sha256": a_sha(row.get("case_sha256")),
        "prompt_sha256": a_sha(row.get("prompt_sha256")),
        "answer_sha256": a_sha(row.get("answer_sha256")),
        "sent_answer_sha256": a_sha(row.get("sent_answer_sha256")),
        "answer_chars": num(row.get("answer_chars")),
        "warm": a_side(row.get("warm")),
        "checks": {key: checks.get(key) is True for key in CHECKS[phase]},
        "stream_path": a_name(row.get("stream_path")),
        "outcome": row.get("outcome") if row.get("outcome") in OUTCOMES else None,
        "error": error_type(row.get("error")),
        "score": a_score(row.get("score")),
        "sec": num(row.get("sec")),
        "num_ctx": num(row.get("num_ctx")),
        "est_input_tokens": num(row.get("est_input_tokens")),
        "input_limit": num(row.get("input_limit")),
        "reply_chars": num(row.get("reply_chars")),
        "done_reason": a_name(row.get("done_reason")),
        "started": a_stamp(row.get("started")),
        "finished": a_stamp(row.get("finished")),
    }
    line.update({key: num(row.get(key)) for key in COUNTERS})
    reload = row.get("reload")
    line["reload"] = (
        {key: num(reload.get(key)) for key in RELOAD} if isinstance(reload, dict) else None
    )
    return line


def line_holds(line: dict[str, Any], expected: dict[str, Any], phase: str) -> list[str]:
    """Why a line is not its answer's continuation as the spec runs it; empty when it is."""
    why = []
    if line["phase"] != phase:
        why.append("another phase")
    if any(line[key] != expected[key] for key in IDS[phase]):
        why.append("its ids are not its answer's")
    if phase == "bridge":
        warm, given = line["warm"] or {}, expected["warm"] or {}
        if warm.get("score") is None or warm != given:
            why.append("its warm continuation is not step 2's")
    if not all(line["checks"].values()):
        why.append("a check of its answer failed")
    if line["segment"] is None:
        why.append("no segment")
    if line["stream_path"] != STREAM_PATH:
        why.append("another stream path")
    if (line["num_ctx"], line["input_limit"]) != (NUM_CTX, INPUT_LIMIT):
        why.append("another window")
    outcome, score, est = line["outcome"], line["score"], line["est_input_tokens"]
    if outcome is None:
        why.append("no outcome")
    elif (outcome == "scored") != scored(score) or (outcome != "scored" and score != -1):
        why.append("its score is not its outcome's")
    if est is None or (outcome == "window") != (est > INPUT_LIMIT):
        why.append("its estimate is not its outcome's")
    if (outcome == "error") != (line["error"] is not None):
        why.append("its error is not its outcome's")
    if line["sec"] is None or line["sec"] < 0:
        why.append("no seconds")
    return why


def read_segment(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    before = value.get("ollama_models_before")
    final = value.get("final_unload")
    return {
        "started": a_stamp(value.get("started")),
        "finished": a_stamp(value.get("finished")),
        "first": value.get("first") is True,
        "from_n": num(value.get("from_n")),
        "status": a_name(value.get("status")),
        "ollama_models_before": [a_name(m) for m in before] if isinstance(before, list) else None,
        "llama_servers_before": num(value.get("llama_servers_before")),
        "ollama_load_sec": num(value.get("ollama_load_sec")),
        "load_error": error_type(value.get("load_error")),
        "unload_error": error_type(value.get("unload_error")),
        "crash": error_type(value.get("crash")),
        "final_unload": (
            {key: num(final.get(key)) for key in ("unload_sec", "polls")}
            if isinstance(final, dict)
            else None
        ),
        "final_unload_error": error_type(value.get("final_unload_error")),
    }


def read_launch(launch: dict[str, Any]) -> dict[str, Any]:
    kept: dict[str, Any] = {}
    for key in LAUNCH_KEYS:
        if key not in launch:
            continue
        value = launch[key]
        if key in ("tools_sha256", "inputs_sha256"):
            value = (
                {an_id(k): a_sha(v) for k, v in sorted(value.items())}
                if isinstance(value, dict)
                else None
            )
        elif key in ("params", "planned"):
            value = (
                {an_id(k): num(v) for k, v in sorted(value.items())}
                if isinstance(value, dict)
                else None
            )
        elif key == "segments":
            value = [read_segment(item) for item in value] if isinstance(value, list) else None
        elif key in ("started", "finished"):
            value = a_stamp(value)
        elif key in (
            "num_ctx",
            "input_limit",
            "answer_stop_sec",
            "reload_every",
            "model_errors",
            "answers",
        ):
            value = num(value)
        elif key in ("model_digest", "instruction_sha256"):
            value = a_sha(value)
        else:
            value = a_name(value)
        kept[key] = value
    return kept


def history(segments: Sequence[Any], lines: Sequence[dict[str, Any]], planned: int) -> list[str]:
    """Why the launch's segments are not the spec's; empty when they are. Each started from an
    idle Mac and loaded the model before its first answer; the first answer's may stand first;
    an interruption ends a segment as its last line says, and a failed call or an answer past
    the stop ends its own; a reload stands before each of answers n = 6, 11, ... that its
    segment does not start with; the last completed the plan."""
    why: list[str] = []
    if not segments or any(segment is None for segment in segments):
        return ["no segments, or one unreadable"]
    statuses = [segment["status"] for segment in segments]
    if any(status not in STATUSES for status in statuses):
        why.append("a segment is still running, crashed or holds no status")
    if statuses[-1] != "complete" or statuses.count("complete") != 1:
        why.append("the last segment, and it alone, is not the complete one")
    if "first" in statuses[1:]:
        why.append("a first answer's segment after the first")
    if len(segments) > MAX_SEGMENTS:
        why.append(f"more than {MAX_SEGMENTS} segments")
    starts = [segment["from_n"] for segment in segments]
    if starts[0] != 1 or any(
        not isinstance(start, int) or start < 1 or (index and start < starts[index - 1])
        for index, start in enumerate(starts)
    ):
        why.append("the segments do not start in order from the first answer")
        return why

    def bounds(index: int) -> tuple[int, int]:
        """The answers segment `index` was to ask: from its first to the next one's first."""
        return starts[index - 1], starts[index] if index < len(starts) else planned + 1

    by_segment: dict[int, list[dict[str, Any]]] = {}
    for line in lines:
        index, n = line["segment"], line["n"]
        if not isinstance(index, int) or not 1 <= index <= len(segments):
            why.append(f"line {n}: no segment of the launch")
            continue
        low, high = bounds(index)
        if not isinstance(n, int) or not low <= n < high:
            why.append(f"line {n}: outside its segment")
            continue
        by_segment.setdefault(index, []).append(line)
        due = n != low and (n - 1) % RELOAD_EVERY == 0
        reload = line["reload"]
        if due != (reload is not None) or (
            reload is not None and any(reload[key] is None for key in RELOAD)
        ):
            why.append(f"line {n}: its reload is not the spec's")
    for index, segment in enumerate(segments, start=1):
        own = by_segment.get(index, [])
        low, _ = bounds(index)
        last = own[-1] if own else None
        if segment["ollama_models_before"] != [] or segment["llama_servers_before"] != 0:
            why.append(f"segment {index}: did not start on an idle Mac")
        if own and segment["ollama_load_sec"] is None:
            why.append(f"segment {index}: no load before its first answer")
        if [line["n"] for line in own] != list(range(low, low + len(own))):
            why.append(f"segment {index}: its lines are not its answers in order")
        status = segment["status"]
        for line in own:
            # The replay stops at a failed call first, then at an answer past the stop.
            stop = "model_error" if line["outcome"] == "error" else None
            if stop is None and (line["sec"] or 0) > ANSWER_STOP:
                stop = "answer_stop"
            if stop is not None and (line is not last or status != stop):
                why.append(f"line {line['n']}: its stop did not end its segment")
        if status in ("first", "model_error", "answer_stop", "complete"):
            ends = {
                "first": last is not None and len(own) == 1 and segment["first"],
                "model_error": last is not None and last["outcome"] == "error",
                "answer_stop": last is not None and (last["sec"] or 0) > ANSWER_STOP,
                "complete": low + len(own) == planned + 1,
            }
            if not ends[status]:
                why.append(f"segment {index}: its end is not its last line's")
        if status in ("unload_stop", "load_stop") and not (
            segment["unload_error"] or segment["load_error"]
        ):
            why.append(f"segment {index}: its stop names no error")
    return why


def read_phase(
    folder: Path,
    phase: str,
    expected: Sequence[dict[str, Any]],
    *,
    planned: dict[str, int],
    inputs_sha256: dict[str, str],
) -> dict[str, Any]:
    """A phase's launch, lines and failures, and its gate's own points."""
    notes: list[str] = []
    try:
        launch = json.loads((folder / REPLAY_FILES[0]).read_text(encoding="utf-8"))
        if not isinstance(launch, dict):
            raise ValueError("launch.json is no object")
    except (OSError, ValueError):
        notes.append(f"{phase}: no readable launch.json")
        launch = {}
    kept = read_launch(launch)
    rows, bad = read_rows(folder / REPLAY_FILES[1], notes, f"{phase} lines")
    lines = [read_line(row, phase) for row in rows]
    failure_rows, bad_failures = read_rows(
        folder / REPLAY_FILES[2], notes, f"{phase} failures", optional=True
    )
    failures = [
        {
            "n": num(row.get("n")),
            "run": an_id(row.get("run")),
            "case_id": an_id(row.get("case_id")),
            "error": error_type(row.get("error")),
            "sec": num(row.get("sec")),
            "at": a_stamp(row.get("at")),
        }
        for row in failure_rows
    ]
    for index, line in enumerate(lines):
        if index < len(expected):
            for why in line_holds(line, expected[index], phase):
                notes.append(f"{phase} line {index + 1}: {why}")
    if len(lines) != len(expected):
        notes.append(f"{phase}: {len(lines)} lines for {len(expected)} answers")
    errors = sorted(
        (line["n"], line["run"], line["case_id"], line["error"])
        for line in lines
        if line["outcome"] == "error"
    )
    failed = sorted((row["n"], row["run"], row["case_id"], row["error"]) for row in failures)
    segments = kept.get("segments")
    order = history(segments if isinstance(segments, list) else [], lines, len(expected))
    notes += [f"{phase} segments: {why}" for why in order]
    frozen = {
        "schema": REPLAY_SCHEMA,
        "spec": SPEC,
        "phase": phase,
        "key": KEY,
        "code_sha": CODE_SHA,
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "stream_path": STREAM_PATH,
        "prompt_id": PROMPT_ID,
        "instruction_sha256": INSTRUCTION_SHA256,
        "num_ctx": NUM_CTX,
        "input_limit": INPUT_LIMIT,
        "params": PARAMS,
        "answer_stop_sec": ANSWER_STOP,
        "reload_every": RELOAD_EVERY,
        "planned": planned,
    }
    gate = {
        "launch": all(kept.get(key) == value for key, value in frozen.items())
        and kept.get("status") == "complete"
        and kept.get("answers") == len(expected),
        "tools": kept.get("tools_sha256") == REPLAY_SHA256,
        "inputs": kept.get("inputs_sha256") == inputs_sha256,
        "lines": not bad
        and bool(expected)
        and len(lines) == len(expected)
        and all(not line_holds(line, e, phase) for line, e in zip(lines, expected, strict=True)),
        "failures": not bad_failures
        and errors == failed
        and kept.get("model_errors") == len(failed),
        "segments": not order,
    }
    return {
        "dir": str(folder),
        "launch": kept,
        "sha256": {name: sha256(folder / name) for name in REPLAY_FILES},
        "lines": lines,
        "failures": failures,
        "gate": gate,
        "notes": notes,
    }


def read_environment(path: Path, notes: list[str]) -> list[dict[str, Any]]:
    """stand_env.py's lines: when each was taken, Ollama's version, its serving processes and
    the times its binary and its app last changed; no path."""
    rows, _ = read_rows(path, notes, "environment")
    lines = []
    for row in rows:
        given = row.get("ollama")
        ollama: dict[str, Any] = given if isinstance(given, dict) else {}
        servers = ollama.get("servers")
        lines.append(
            {
                "taken": a_stamp(row.get("taken")),
                "server_version": a_name(ollama.get("server_version")),
                "server_error": error_type(ollama.get("server_error")),
                "servers": (
                    [
                        {
                            "pid": num(server.get("pid")),
                            "started": a_stamp(server.get("started")),
                            "binary_changed": a_stamp(server.get("binary_changed")),
                        }
                        for server in servers
                        if isinstance(server, dict)
                    ]
                    if isinstance(servers, list)
                    else None
                ),
                "app_changed": a_stamp(ollama.get("app_changed")),
            }
        )
    return lines


def environment_holds(lines: Sequence[dict[str, Any]], phase: dict[str, Any]) -> list[str]:
    """Why the environment's lines do not hold a phase; empty when they do: Ollama's version is
    the spec's in every line, one server serves, the same in all of them with its binary and
    app unchanged, and a line was taken before the phase's first segment and one after its
    last."""
    why = []
    if len(lines) < 2:
        why.append("fewer than two environment lines")
    for line in lines:
        if line["server_version"] != OLLAMA_VERSION or line["server_error"] is not None:
            why.append("an environment line without the spec's Ollama")
        if not isinstance(line["servers"], list) or len(line["servers"]) != 1:
            why.append("an environment line without one Ollama server")
    if len({json.dumps([line["servers"], line["app_changed"]]) for line in lines}) > 1:
        why.append("Ollama's server, binary or app changed between the lines")
    segments = [s for s in phase["launch"].get("segments") or [] if s is not None]
    begun = a_time(segments[0]["started"]) if segments else None
    ended = a_time(segments[-1]["finished"]) if segments else None
    taken = [a_time(line["taken"]) for line in lines]
    times = [time for time in taken if time is not None]
    if begun is None or ended is None or len(times) != len(taken):
        why.append("no times to set the lines beside the phase")
    else:
        if not any(time <= begun for time in times):
            why.append("no environment line before the phase")
        if not any(time >= ended for time in times):
            why.append("no environment line after the phase")
    return why


def first_answer(
    lines: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """The spec's stop after the first answer, the bridge's, read before the replay goes on: it
    stops unless the first line is the first answer's, holds, and scored 1-100 within the
    answer stop."""
    line = next((line for line in lines if line["n"] == 1), None)
    head = expected[0] if expected else {}
    out: dict[str, Any] = {"n": 1, "run": head.get("run"), "case_id": head.get("case_id")}
    if line is None or not expected:
        why = ["no line of the first answer"]
    else:
        why = line_holds(line, expected[0], "bridge")
        out.update(outcome=line["outcome"], score=line["score"], sec=line["sec"])
        out.update(est_input_tokens=line["est_input_tokens"], warm=head.get("warm"))
        out["counters"] = {key: line[key] for key in COUNTERS}
        if line["outcome"] != "scored":
            why.append("the continuation gave no score")
        if line["sec"] is not None and line["sec"] > ANSWER_STOP:
            why.append("it took longer than the answer stop")
    out.update(stop=bool(why), why=why)
    return out


def bridge_pair(
    expected: dict[str, Any], line: dict[str, Any] | None, passed: bool
) -> dict[str, Any]:
    """An ask step 2 read and its cold continuation as a pair, readable when the bridge's gate
    passed and its line holds: each side's score and route."""
    why = [] if passed else ["the bridge's gate did not pass"]
    why += ["no line"] if line is None else line_holds(line, expected, "bridge")
    pair: dict[str, Any] = {key: expected[key] for key in ("n", "run", "case_id")}
    pair.update(readable=not why, unreadable=why)
    if why or line is None:
        return pair
    warm = expected["warm"]
    score = {"warm": warm["score"], "cold": line["score"]}
    routes = {side: route_of(value) for side, value in score.items()}
    pair.update(outcome=line["outcome"], score=score, routes=routes)
    pair.update(
        routes_differ=routes["warm"] != routes["cold"], equal=score["warm"] == score["cold"]
    )
    pair["printed"] = {
        "sec": {"warm": warm["sec"], "cold": line["sec"]},
        "counters": {
            "warm": {key: warm[key] for key in COUNTERS},
            "cold": {key: line[key] for key in COUNTERS},
        },
        "est_input_tokens": line["est_input_tokens"],
        "reload": line["reload"],
    }
    return pair


def bridge_reading(pairs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The bridge's reading, a function of its pairs alone: held when at least MIN_BRIDGE are
    readable and the cold route differs from the warm on at most BRIDGE_DIFFS of them."""
    readable = [pair for pair in pairs if pair["readable"]]
    differ = [pair["n"] for pair in readable if pair["routes_differ"]]
    answer = NOT_EVIDENCE
    if len(readable) >= MIN_BRIDGE:
        answer = "held" if len(differ) <= BRIDGE_DIFFS else "not held"
    both = [pair for pair in readable if -1 not in pair["score"].values()]
    diffs = [pair["score"]["cold"] - pair["score"]["warm"] for pair in both]

    def side(name: str) -> dict[str, Any]:
        values = Counter(pair["score"][name] for pair in readable)
        sec = [pair["printed"]["sec"][name] for pair in readable]
        counters = {
            key: median(
                [
                    value
                    for value in (pair["printed"]["counters"][name][key] for pair in readable)
                    if value is not None
                ]
            )
            for key in COUNTERS
        }
        return {
            "scores": {str(score): count for score, count in sorted(values.items())},
            "median_sec": median([value for value in sec if value is not None]),
            "median_counters": counters,
        }

    routes = Counter(f"{pair['routes']['warm']}->{pair['routes']['cold']}" for pair in readable)
    return {
        "answer": answer,
        "readable_pairs": len(readable),
        "min_pairs": MIN_BRIDGE,
        "routes_differ": len(differ),
        "max_routes_differ": BRIDGE_DIFFS,
        "differ": differ,
        "printed_deciding_nothing": {
            "equal": sum(1 for pair in readable if pair["equal"]),
            "routes": dict(sorted(routes.items())),
            "warm_at_100": sum(1 for pair in readable if pair["score"]["warm"] == 100),
            "cold_minus_warm": {
                "higher": sum(d > 0 for d in diffs),
                "same": sum(d == 0 for d in diffs),
                "lower": sum(d < 0 for d in diffs),
                "median_diff": median(diffs),
            },
            "by_outcome": dict(sorted(Counter(pair["outcome"] for pair in readable).items())),
            "by_run": dict(sorted(Counter(pair["run"] for pair in readable).items())),
            "warm": side("warm"),
            "cold": side("cold"),
        },
    }


def pair_of(answer: dict[str, Any], line: dict[str, Any] | None, passed: bool) -> dict[str, Any]:
    """An answer and its continuation as a pair, readable when the 80's gate passed and its
    line holds: the classic's saved score, the continuation's where it scored 1-100, and the
    effective score - the continuation's, else the classic's, as the chat falls back - each
    flagged under 80, the stream's route to a person."""
    why = [] if passed else ["the 80's gate did not pass"]
    why += ["no line"] if line is None else line_holds(line, answer, "labels")
    classic = answer["classic"]["score"]
    if not scored(classic):
        why.append("no classic score of 1-100")
    pair: dict[str, Any] = {key: answer[key] for key in ("n", "class", "run", "case_id")}
    pair.update(readable=not why, unreadable=why)
    if why or line is None:
        return pair
    own = line["score"] if line["outcome"] == "scored" else None
    effective = classic if own is None else own
    pair.update(outcome=line["outcome"])
    pair["score"] = {"classic": classic, "continuation": own, "effective": effective}

    def flags(threshold: int) -> dict[str, bool | None]:
        out: dict[str, bool | None] = {side: pair["score"][side] < threshold for side in SIDES}
        out["continuation"] = None if own is None else own < threshold
        return out

    pair.update(flagged=flags(THRESHOLD), flagged_under_100=flags(PRINTED_THRESHOLD))
    pair["printed"] = {
        "sec": line["sec"],
        "counters": {key: line[key] for key in COUNTERS},
        "est_input_tokens": line["est_input_tokens"],
        "reply_chars": line["reply_chars"],
        "done_reason": line["done_reason"],
        "error": line["error"],
        "reload": line["reload"],
    }
    return pair


def paired(pairs: Sequence[dict[str, Any]], key: str = "flagged") -> dict[str, Any]:
    """Which answers each side flags, and the exact McNemar test of the effective flags against
    the classic's: the two-sided sign test on the discordant pairs."""
    effective_only = [p["n"] for p in pairs if p[key]["effective"] and not p[key]["classic"]]
    classic_only = [p["n"] for p in pairs if p[key]["classic"] and not p[key]["effective"]]
    p_value = sign_p(len(effective_only), len(classic_only))
    found = "no difference"
    if p_value < ALPHA:
        found = "effective more" if len(effective_only) > len(classic_only) else "effective fewer"
    return {
        "both": [p["n"] for p in pairs if p[key]["effective"] and p[key]["classic"]],
        "effective_only": effective_only,
        "classic_only": classic_only,
        "exact_p": round(p_value, 6),
        "found": found,
    }


def readings(pairs: Sequence[dict[str, Any]], bridge: str) -> dict[str, Any]:
    """The spec's readings of the 80, functions of the pairs alone: the scores held over the 80,
    the catches over the 17 targets and the over-marks over the 63 goods; then the signal, held
    when they and the bridge's reading `bridge` all held."""
    readable = [pair for pair in pairs if pair["readable"]]
    targets = [pair for pair in readable if pair["class"] == "target"]
    goods = [pair for pair in readable if pair["class"] == "good"]
    whole = (len(targets), len(goods)) == (TARGETS, GOODS)
    no_score = [pair for pair in readable if pair["outcome"] != "scored"]
    caught = {side: sum(pair["flagged"][side] for pair in targets) for side in SIDES}
    over = {side: sum(pair["flagged"][side] for pair in goods) for side in SIDES}
    scores = catches = over_marks = NOT_EVIDENCE
    if whole:
        scores = "held" if len(no_score) <= MAX_NO_SCORE else "not held"
        catches = "held" if caught["effective"] >= caught["classic"] else "not held"
        over_marks = "held" if over["effective"] <= over["classic"] + OVER_MARGIN else "not held"
    answers = (bridge, scores, catches, over_marks)
    signal = NOT_EVIDENCE
    if "not held" in answers:
        signal = "not held"
    elif all(answer == "held" for answer in answers):
        signal = "held"

    def flagged(group: Sequence[dict[str, Any]], side: str, key: str = "flagged") -> list[int]:
        return [pair["n"] for pair in group if pair[key][side]]

    def under_100(group: Sequence[dict[str, Any]]) -> dict[str, int]:
        return {side: len(flagged(group, side, "flagged_under_100")) for side in SIDES}

    def own(group: Sequence[dict[str, Any]]) -> dict[str, int]:
        scored_here = [pair for pair in group if pair["flagged"]["continuation"] is not None]
        return {
            "scored": len(scored_here),
            "flagged": sum(1 for pair in scored_here if pair["flagged"]["continuation"]),
        }

    def scores_of(group: Sequence[dict[str, Any]], side: str) -> dict[str, int]:
        values = Counter(pair["score"][side] for pair in group if pair["score"][side] is not None)
        return {str(score): count for score, count in sorted(values.items())}

    def medians(group: Sequence[dict[str, Any]]) -> dict[str, float | None]:
        return {
            side: median([pair["score"][side] for pair in group if pair["score"][side] is not None])
            for side in ("classic", "continuation", "effective")
        }

    both = [pair for pair in readable if pair["score"]["continuation"] is not None]
    diffs = [pair["score"]["continuation"] - pair["score"]["classic"] for pair in both]
    seconds = [pair["printed"]["sec"] for pair in readable if pair["outcome"] != "window"]
    estimates = [pair["printed"]["est_input_tokens"] for pair in readable]
    reloaded = [pair for pair in readable if pair["printed"]["reload"] is not None]

    def counter(key: str) -> float | None:
        values = [pair["printed"]["counters"][key] for pair in readable]
        return median([value for value in values if value is not None])

    def spread(key: str) -> dict[str, float | None]:
        values = [pair["printed"]["reload"][key] for pair in reloaded]
        values = [value for value in values if value is not None]
        return {"median": median(values), "max": max(values, default=None)}

    return {
        "scores": {
            "answer": scores,
            "readable_pairs": len(readable),
            "no_score": len(no_score),
            "max_no_score": MAX_NO_SCORE,
            "by_outcome": dict(sorted(Counter(pair["outcome"] for pair in readable).items())),
            "no_score_answers": [pair["n"] for pair in no_score],
            "no_score_targets": sum(1 for pair in no_score if pair["class"] == "target"),
        },
        "catches": {
            "answer": catches,
            "of": len(targets),
            **caught,
            "caught": {side: flagged(targets, side) for side in SIDES},
        },
        "over_marks": {
            "answer": over_marks,
            "of": len(goods),
            **over,
            "margin": OVER_MARGIN,
            "over_marked": {side: flagged(goods, side) for side in SIDES},
        },
        "signal": {
            "answer": signal,
            "of": dict(zip(("bridge", *SIGNAL_PARTS), answers, strict=True)),
        },
        "printed_deciding_nothing": {
            "paired": {"catches": paired(targets), "over_marks": paired(goods)},
            "under_100": {"catches": under_100(targets), "over_marks": under_100(goods)},
            "continuation_alone": {"targets": own(targets), "goods": own(goods)},
            "wilson": {
                "caught": {side: wilson(caught[side], len(targets)) for side in SIDES},
                "over_marked": {side: wilson(over[side], len(goods)) for side in SIDES},
            },
            "scores": {
                kind: {
                    side: scores_of(group, side)
                    for side in ("classic", "continuation", "effective")
                }
                for kind, group in (("target", targets), ("good", goods))
            },
            "median_score": {"target": medians(targets), "good": medians(goods)},
            "continuation_scored": {
                "higher": sum(d > 0 for d in diffs),
                "same": sum(d == 0 for d in diffs),
                "lower": sum(d < 0 for d in diffs),
                "median_diff": median(diffs),
            },
            "sec": {
                "median": median(seconds),
                "max": max(seconds) if seconds else None,
                "total": rounded(sum(seconds)) if seconds else None,
            },
            "median_counters": {key: counter(key) for key in COUNTERS},
            "est_input_tokens": {
                "median": median([e for e in estimates if e is not None]),
                "max": max((e for e in estimates if e is not None), default=None),
            },
            "done_reasons": dict(
                sorted(Counter(str(pair["printed"]["done_reason"]) for pair in readable).items())
            ),
            "reply_chars": dict(
                sorted(Counter(str(pair["printed"]["reply_chars"]) for pair in readable).items())
            ),
            "reloads": {
                "before": [pair["n"] for pair in reloaded],
                "unload_sec": spread("unload_sec"),
                "load_sec": spread("load_sec"),
            },
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    for name in ("out", "run_dir", "plan", "labels", "step2_dir"):
        parser.add_argument(name)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"refused: {out} exists", file=sys.stderr)
        return 2
    run_dir = Path(args.run_dir)
    notes: list[str] = []
    inputs = read_inputs(Path(args.plan), Path(args.labels), notes)
    step2 = read_step2(Path(args.step2_dir))
    environment = read_environment(run_dir / "environment.jsonl", notes)
    phases = {
        "bridge": read_phase(
            run_dir / "bridge",
            "bridge",
            step2["asks"],
            planned=step2["planned"],
            inputs_sha256={},
        ),
        "labels": read_phase(
            run_dir / "labels",
            "labels",
            inputs["answers"],
            planned={"goods": GOODS, "targets": TARGETS},
            inputs_sha256=INPUTS_SHA256,
        ),
    }
    first = first_answer(phases["bridge"]["lines"], step2["asks"])
    extra = {
        "bridge": {"step2": step2["holds"], "first": not first["stop"]},
        "labels": {
            "input_files": inputs["sha256"] == INPUTS_SHA256,
            "classes": inputs["classes_hold"],
            "classic": inputs["classic_holds"],
        },
    }
    for name, phase in phases.items():
        why = environment_holds(environment, phase)
        phase["notes"] += [f"{name} environment: {reason}" for reason in why]
        phase["gate"].update(extra[name], environment=not why)
        phase["gate"]["passed"] = all(phase["gate"].values())
    bridge, labels = phases["bridge"], phases["labels"]
    by_n: dict[str, dict[Any, dict[str, Any]]] = {name: {} for name in phases}
    for name, phase in phases.items():
        for line in phase["lines"]:
            by_n[name].setdefault(line["n"], line)
    bridge_pairs = [
        bridge_pair(ask, by_n["bridge"].get(ask["n"]), bridge["gate"]["passed"])
        for ask in step2["asks"]
    ]
    pairs = [
        pair_of(answer, by_n["labels"].get(answer["n"]), labels["gate"]["passed"])
        for answer in inputs["answers"]
    ]
    bridged = bridge_reading(bridge_pairs)
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "tools_sha256": {name: sha256(HERE / name) for name in TOOLS},
        "inputs": {**inputs, "notes": notes},
        "step2": step2,
        "environment": environment,
        "bridge": bridge,
        "labels": labels,
        "first_answer": first,
        "bridge_pairs": bridge_pairs,
        "pairs": pairs,
        "readings": {"bridge": bridged, **readings(pairs, bridged["answer"])},
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    gates = {name: phase["gate"] for name, phase in phases.items()}
    print(json.dumps({"gates": gates, "first_answer": first}, sort_keys=True))
    print(json.dumps(record["readings"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
