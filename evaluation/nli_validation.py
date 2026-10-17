"""Sample, requests and reference labels of the NLI judge validation - plan slice 2.8.

The slice asks whether the NLI judge of the answer metrics can be trusted. Its material is the
assertions of the two phase C generator benchmarks, C.1a and C.1b: every line the splitter of
the benchmark cut an answer into, with the five contexts the judge scored it against. The NLI
research (`archive/docs/specs/research-nli-judges.md`, section 3) fixed the pool, the strata, the
sample sizes and the quotas; the specification (`docs/specs/semantic-precision-metrics.md`,
«Checks by one model in slices 2.8 and 4.1») gave the reference label of an assertion to one
model, asked twice in requests that share nothing.

This module is the part of both that needs no model. It rebuilds the pool from the committed
artifacts and refuses one whose counts are not the research's; draws the sample, the top-up
and the labeller's control; builds the text of a request and reads a reply; and computes the
stability bound of the labels. What it does not do: send a request (`scripts/nli_reference.py`)
or run a judge.

Words used here:

- *unit* - one assertion: a (source, case, text) triple. The same text of the same case in
  both sources is two units and one *labelling unit*: it is labelled once, by one request.
- *stratum* - a cell of source, current NLI score and lexical overlap; a unit of a stratum
  stands for `pool / sample` units of it.
- *pass* - one of the two requests a labelling unit is sent in; the second shows the contexts
  and the label definitions in another order.
- *reduced label* - supported, not supported or not a claim: what the four labels of the
  rubric come to in every number.
- *control* - a request that shows a unit beside the contexts of another unit: nothing in
  them was retrieved for it, so a labeller that reads the contexts cannot call it supported.
"""

from __future__ import annotations

import functools
import gzip
import hashlib
import json
import math
import random
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from evaluation.label_verification import ReplyFormatError, json_objects, sha256_text

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260925
RUBRIC_VERSION = "nli-reference/v1"

# The inputs, by SHA-256. The candidates archive unpacks to the scratch file the research read.
REPORTS = {
    "c1a": (
        "evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json",
        "ac8d9cc20a8d414490fd0ada46e35731d7a2891e7169c3ec22ef88a4644db534",
    ),
    "c1b": (
        "evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json",
        "1663ea598b769af2aee6464c5da90a001b9187f83114217f03f6552856a70f5f",
    ),
}
CANDIDATES = (
    "evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz",
    "c28d676ac79450d54904cc83c697ddb709dfe95e6bbe86d305c3505db50338c3",
)
CANDIDATES_UNPACKED_SHA256 = "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10"
FAMILIES = (
    "evaluation/document_families.json",
    "54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584",
)

# Research section 3.2. A stratum: its source, its units in the pool, its units in the sample.
STRATA: dict[str, tuple[str, int, int]] = {
    "b1": ("c1b", 5, 5),
    "b2": ("c1b", 18, 18),
    "b3": ("c1b", 117, 57),
    "a1": ("c1a", 81, 40),
    "a2": ("c1a", 59, 25),
    "a3": ("c1a", 56, 20),
    "a4": ("c1a", 320, 35),
}
SUPPORT_THRESHOLD = 0.5
HIGH_SCORE = 0.95
HIGH_OVERLAP = 0.6
# A quota: the flag, the least number of sample units that carry it, the units of the pool
# that carry it by the research's count. They are met in this order.
QUOTAS: tuple[tuple[str, int, int], ...] = (
    ("no_cyrillic", 20, 79),
    ("numeric", 15, 30),
    ("intro", 15, 61),
    ("fragment", 40, 251),
    ("low_llm", 15, 56),
)
CAP = 4
FRAGMENT_WORDS = 3
LOW_LLM = 0.6
TOP_UP_STRATA = ("a2", "a3", "b2")
TOP_UP_UNITS = 50
TOP_UP_BELOW = 40
CONTROL_STRATA = ("b3", "a4")
CONTROL_FIRST = 20
CONTROL_READ = 10
CONTROL_TAG = "nli_control"

LABELS = ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "NOT_CLAIM")
REDUCED = {
    "SUPPORTED": "supported",
    "PARTIAL": "not_supported",
    "UNSUPPORTED": "not_supported",
    "NOT_CLAIM": "not_claim",
}
FLAGS = ("MULTI", "FRAGMENT", "CONTRA", "OUTSIDE", "REFUSAL")
PASSES = (1, 2)
PASS_SUFFIX = "~pass2"
CONTROL_PREFIX = "control-"
ATTEMPTS = 3
UNSTABLE_SHARE = 0.10
PASS_KAPPA = 0.6
CONTROL_SHARE = 0.10
RESAMPLES = 2000
MARK_OPEN = ">>>"
MARK_CLOSE = "<<<"

_WORD = re.compile(r"\w+")
_CYRILLIC = re.compile("[а-яёА-ЯЁ]")
_DIGIT = re.compile(r"\d")
_LINE = re.compile(r"[^\r\n]+")
_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_SENTENCE_GAP = re.compile(r"(?<=[.!?])\s+")

SYSTEM_PROMPT = (
    "You label one unit of an answer against the passages the answer was written from. Use "
    "only the material in the message and reply with the one JSON object it asks for."
)
SYSTEM_PROMPT_SHA256 = "c8b0fe6315813cd8fa768601d8672055b5d5426c462aa00e1ca7b0dbf26ca094"

LABEL_DEFINITIONS = {
    "SUPPORTED": (
        "SUPPORTED - every factual element of the unit is stated in some passage or follows "
        "from it unambiguously. An accurate paraphrase counts."
    ),
    "PARTIAL": (
        "PARTIAL - some factual elements of the unit are supported and some are not: an item "
        "too many, a wrong number, period or term, a generalisation stronger than the source "
        "(always where the source says as a rule)."
    ),
    "UNSUPPORTED": (
        "UNSUPPORTED - no factual element of the unit is supported, or the unit contradicts a "
        "passage (flag CONTRA), or it comes from outside the passages, even if it is true "
        "(flag OUTSIDE)."
    ),
    "NOT_CLAIM": (
        "NOT_CLAIM - the unit states no fact: a line that only introduces a list, a greeting, "
        "a caveat or a piece of advice without a fact, a statement that the passages do not "
        "hold the answer (flag REFUSAL)."
    ),
}
PROMPT_TEMPLATE = """\
You are given a question, the answer a system gave to it, one unit of that answer and five
passages. The answer was written from the passages. Decide whether the passages support the
unit.

Read the unit in the context of the question and of its answer: an item of a list together
with the line that introduces the list, a short answer together with the question. Label the
unit alone; the rest of the answer is there to read it by. Support comes from the passages
only: knowledge of the world that no passage states supports nothing.

Give the unit one of four labels.

{labels}

Add every flag that applies, or none:
- MULTI - the support needs two or more passages together;
- FRAGMENT - without the question or the introducing line the unit cannot be understood;
- CONTRA - a passage contradicts the unit;
- OUTSIDE - the unit states something no passage holds, whether or not it is true;
- REFUSAL - the unit says that the passages do not hold the answer.

Reply with one JSON object and nothing else: no text before or after it and no code fence.

{{"label": "...", "flags": [], "passages": [], "reason": "..."}}

`label` is one of SUPPORTED, PARTIAL, UNSUPPORTED, NOT_CLAIM. `flags` lists the flags that
apply. `passages` lists the numbers of the passages that support the unit or a part of it and
is empty when none does. `reason` is one sentence in English.

QUESTION
{question}

ANSWER (the unit stands between {mark_open} and {mark_close})
{answer}

UNIT
{unit}

{passages}
"""
# Registered in docs/specs/semantic-precision-metrics.md with plan slice 2.8: a changed text is
# a new rubric version, and a plan refuses a template whose SHA-256 is not this one.
PROMPT_SHA256 = "3fe45ff2e08abed52ceb18e282fb7056618be293590812e76bea80ac75ce7f37"


def prompt_sha256() -> str:
    """One digest of everything a request is built from besides the unit itself."""
    return sha256_text(
        json.dumps(
            {"template": PROMPT_TEMPLATE, "labels": LABEL_DEFINITIONS},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def claim_id(source: str, case_id: str, text: str) -> str:
    return sha256_text(f"{source}|{case_id}|{text}")


def _hash(tag: str, name: str) -> str:
    return sha256_text(f"{SEED}:{tag}:{name}")


def sending_order(request: str) -> str:
    """The key the requests of a stage are sent by: neither a pass nor the control goes first."""
    return _hash("order", request)


def claim_spans(answer: str) -> list[tuple[str, int, int]]:
    """The units of an answer with their places in it.

    The texts are those of `split_material_claims` of the benchmark: lines without their list
    marker, cut after a full stop, a question mark or an exclamation mark.
    """
    spans: list[tuple[str, int, int]] = []
    stripped = answer.strip()
    shift = len(answer) - len(answer.lstrip())
    for line in _LINE.finditer(stripped):
        marker = _MARKER.match(line.group())
        body = line.group()[marker.end() if marker else 0 :]
        cleaned = body.strip()
        if not cleaned:
            continue
        base = shift + line.start() + (marker.end() if marker else 0)
        base += len(body) - len(body.lstrip())
        position = 0
        for part in _SENTENCE_GAP.split(cleaned):
            index = cleaned.index(part, position)
            position = index + len(part)
            claim = part.strip()
            if claim:
                start = base + index + len(part) - len(part.lstrip())
                spans.append((claim, start, start + len(claim)))
    return spans


def cut_contexts(contexts: Sequence[str], max_chars: int) -> list[str]:
    """The contexts as the judge of the benchmark saw them (`_truncate_contexts`)."""
    if max_chars <= 0:
        return [str(item) for item in contexts]
    remaining = max_chars
    selected: list[str] = []
    for context in contexts:
        if remaining <= 0:
            break
        text = str(context)
        if not text:
            continue
        selected.append(text[:remaining])
        remaining -= len(selected[-1])
    return selected


def lexical_overlap(text: str, contexts: Sequence[str]) -> float:
    """Share of the unit's word forms found in the context that holds most of them."""
    words = [word.lower() for word in _WORD.findall(text)]
    if not words:
        return 0.0
    best = 0
    for context in contexts:
        held = {word.lower() for word in _WORD.findall(context)}
        best = max(best, sum(word in held for word in words))
    return best / len(words)


def stratum_of(source: str, score: float, overlap: float) -> str:
    letter = source[-1]
    if score < SUPPORT_THRESHOLD:
        name = f"{letter}1"
    elif score < HIGH_SCORE:
        name = "a2" if letter == "a" else "b1"
    elif overlap < HIGH_OVERLAP:
        name = "a3" if letter == "a" else "b2"
    else:
        name = "a4" if letter == "a" else "b3"
    if name not in STRATA or STRATA[name][0] != source:
        raise ValueError(f"no stratum of {source} holds the score {score}")
    return name


def _read(root: Path, registered: tuple[str, str]) -> bytes:
    path, digest = registered
    data = (root / path).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"not the registered file: {path}")
    return data


def family_map(root: Path = ROOT, registered: tuple[str, str] = FAMILIES) -> dict[str, str]:
    register = json.loads(_read(root, registered))
    return {
        member["source_id"]: family["family_id"]
        for family in register["families"]
        for member in family["members"]
    }


def build_pool(root: Path = ROOT) -> list[dict[str, Any]]:
    """Every unit of C.1a and C.1b, in the order of its id; refused unless the research's.

    A unit met in several runs, or twice in an answer, is taken where it is met first: the
    answer, the place in it and the score of the answer's own judge are those of that run.
    The units are shared between calls and are not to be changed.
    """
    return list(_pool(root, tuple(REPORTS.items()), CANDIDATES, FAMILIES))


@functools.lru_cache(maxsize=4)
def _pool(
    root: Path,
    reports: tuple[tuple[str, tuple[str, str]], ...],
    archive: tuple[str, str],
    register: tuple[str, str],
) -> tuple[dict[str, Any], ...]:
    unpacked = gzip.decompress(_read(root, archive))
    if hashlib.sha256(unpacked).hexdigest() != CANDIDATES_UNPACKED_SHA256:
        raise ValueError("the candidates archive does not unpack to the registered file")
    candidates = {row["case_id"]: row for row in json.loads(unpacked)}
    families = family_map(root, register)
    units: dict[str, dict[str, Any]] = {}
    for source, registered in reports:
        report = json.loads(_read(root, registered))
        config = report["provenance"]["config"]
        if config["nli_support_threshold"] != SUPPORT_THRESHOLD:
            raise ValueError(f"{source} was judged at another threshold")
        for run in report["runs"]:
            for case in run["cases"]:
                claims = (case.get("nli") or {}).get("claims") or []
                spans = claim_spans(case["answer"])
                if [item["claim"] for item in claims] != [span[0] for span in spans]:
                    raise ValueError(f"the stored units are not the splitter's: {case['case_id']}")
                entry = candidates[case["case_id"]]
                shown = entry["cands"][: entry["rerank_k"]]
                contexts = cut_contexts(shown, config["context_chars"])
                names = entry["cand_sources"][: entry["rerank_k"]]
                if len(contexts) != len(shown) or len(names) != len(shown):
                    raise ValueError(f"a context of {case['case_id']} is empty or unnamed")
                if MARK_OPEN in case["answer"] or MARK_CLOSE in case["answer"]:
                    raise ValueError(f"an answer holds the mark of a unit: {case['case_id']}")
                for item, (text, start, end) in zip(claims, spans, strict=True):
                    key = claim_id(source, case["case_id"], text)
                    scores = [float(value) for value in item["entailment_scores"]]
                    if len(scores) != len(contexts):
                        raise ValueError(f"scores and contexts differ in number: {key}")
                    best = float(item["best_entailment"])
                    if key in units:
                        if abs(units[key]["nli_best"] - best) > 1e-6:
                            raise ValueError(f"one unit, two scores: {key}")
                        continue
                    overlap = lexical_overlap(text, contexts)
                    judged = case["scores"].get("faithfulness")
                    units[key] = {
                        "claim_id": key,
                        "source": source,
                        "case_id": case["case_id"],
                        "text": text,
                        "question": case["query"],
                        "answer": case["answer"],
                        "span": [start, end],
                        "contexts": contexts,
                        "context_sources": list(names),
                        "families": sorted({families[name] for name in names}),
                        "nli_scores": scores,
                        "nli_best": best,
                        "overlap": overlap,
                        "stratum": stratum_of(source, best, overlap),
                        "llm_faithfulness": judged,
                        "flags": {
                            "no_cyrillic": not _CYRILLIC.search(text),
                            "numeric": bool(_DIGIT.search(text)),
                            "intro": text.endswith(":"),
                            "fragment": len(_WORD.findall(text)) <= FRAGMENT_WORDS,
                            "low_llm": judged is not None and judged <= LOW_LLM,
                        },
                    }
    pool = [units[key] for key in sorted(units)]
    held = Counter(unit["stratum"] for unit in pool)
    flagged = {name: sum(unit["flags"][name] for unit in pool) for name, _, _ in QUOTAS}
    if {name: held[name] for name in STRATA} != {name: row[1] for name, row in STRATA.items()}:
        raise ValueError(f"the strata are not the research's: {dict(sorted(held.items()))}")
    if flagged != {name: count for name, _, count in QUOTAS}:
        raise ValueError(f"the quota pools are not the research's: {flagged}")
    return tuple(pool)


def _completable(
    lacking: Mapping[str, int], ahead: Mapping[tuple[str, str], int], cases: Mapping[str, int]
) -> bool:
    """Can every stratum still get the units it lacks, with at most `CAP` units a question?

    `lacking` - units each unfilled stratum lacks; `ahead` - units of a (stratum, question) the
    walk has not reached; `cases` - units of a question in the sample. The strata can all be
    filled exactly when no group of them lacks more than the questions can give it: a question
    gives a group the lesser of its free places and of its units of the group still ahead. (The
    condition of a feasible flow from strata through questions; with seven strata the groups
    are few enough to try each.)
    """
    names = sorted(lacking)
    questions = sorted({case for (name, case), units in ahead.items() if units and name in lacking})
    for group in range(1, 2 ** len(names)):
        members = [name for index, name in enumerate(names) if group >> index & 1]
        gives = sum(
            min(CAP - cases.get(case, 0), sum(ahead.get((name, case), 0) for name in members))
            for case in questions
        )
        if sum(lacking[name] for name in members) > gives:
            return False
    return True


def draw(pool: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The sample: sizes of the research, at most `CAP` units a question, every quota met.

    A stratum the sample takes whole enters first. The rest of the pool is walked once in the
    first order - ascending SHA-256 of `<seed>:nli_sample:<claim id>` - and a unit enters when
    its stratum lacks units, its question has fewer than `CAP`, and the sample can still be
    completed with it in (`_completable`): a few questions hold most units of some strata, and
    a walk that looked no further would spend their places and end a stratum short. The quotas
    are then read in their order; an unmet one is met by replacements inside a stratum: the
    unit that enters is the first in the second order (`nli_sample2`) that carries the flag and
    never was in the sample, the unit that leaves is the last in the first order among the
    units of the same stratum that were drawn, lack the flag and can go without breaking the
    cap or a quota that is met.
    """
    sizes = {name: row[2] for name, row in STRATA.items()}
    whole = {name for name, row in STRATA.items() if row[1] == row[2]}
    first = sorted(pool, key=lambda unit: _hash("nli_sample", unit["claim_id"]))
    second = sorted(pool, key=lambda unit: _hash("nli_sample2", unit["claim_id"]))
    rank = {unit["claim_id"]: index for index, unit in enumerate(first)}
    sample: dict[str, Mapping[str, Any]] = {}
    cases: Counter[str] = Counter()
    strata: Counter[str] = Counter()

    def enter(unit: Mapping[str, Any]) -> None:
        sample[unit["claim_id"]] = unit
        cases[unit["case_id"]] += 1
        strata[unit["stratum"]] += 1

    def leave(unit: Mapping[str, Any]) -> None:
        del sample[unit["claim_id"]]
        cases[unit["case_id"]] -= 1
        strata[unit["stratum"]] -= 1

    def count(flag: str) -> int:
        return sum(unit["flags"][flag] for unit in sample.values())

    for unit in first:
        if unit["stratum"] in whole:
            enter(unit)
    if any(units > CAP for units in cases.values()):
        raise ValueError("a stratum taken whole holds more units of a question than the cap")
    ahead: Counter[tuple[str, str]] = Counter(
        (unit["stratum"], unit["case_id"]) for unit in first if unit["stratum"] not in whole
    )

    def lacking() -> dict[str, int]:
        return {name: sizes[name] - strata[name] for name in STRATA if sizes[name] > strata[name]}

    if not _completable(lacking(), ahead, cases):
        raise ValueError("no sample holds the sizes of the strata under the cap")
    for unit in first:
        name = unit["stratum"]
        if name in whole:
            continue
        ahead[(name, unit["case_id"])] -= 1
        if strata[name] >= sizes[name] or cases[unit["case_id"]] >= CAP:
            continue
        enter(unit)
        if not _completable(lacking(), ahead, cases):
            leave(unit)
    if any(strata[name] != sizes[name] for name in STRATA):
        raise ValueError(f"the walk left a stratum short: {dict(strata)}")
    drawn = sorted(sample)
    entered: set[str] = set()
    gone: set[str] = set()
    replacements: list[dict[str, str]] = []
    for flag, least, _ in QUOTAS:
        while count(flag) < least:
            met = [(name, low) for name, low, _ in QUOTAS if name != flag and count(name) >= low]
            swap: tuple[Mapping[str, Any], Mapping[str, Any]] | None = None
            for incoming in second:
                key = incoming["claim_id"]
                if key in sample or key in gone or not incoming["flags"][flag]:
                    continue
                leaving = [
                    unit
                    for unit in sample.values()
                    if unit["stratum"] == incoming["stratum"]
                    and unit["claim_id"] not in entered
                    and not unit["flags"][flag]
                    and cases[incoming["case_id"]] - (unit["case_id"] == incoming["case_id"]) < CAP
                    and all(
                        count(name) - unit["flags"][name] + incoming["flags"][name] >= low
                        for name, low in met
                    )
                ]
                if leaving:
                    swap = (max(leaving, key=lambda unit: rank[unit["claim_id"]]), incoming)
                    break
            if swap is None:
                raise ValueError(f"the quota {flag} cannot be met")
            outgoing, incoming = swap
            leave(outgoing)
            enter(incoming)
            gone.add(outgoing["claim_id"])
            entered.add(incoming["claim_id"])
            replacements.append(
                {
                    "quota": flag,
                    "stratum": incoming["stratum"],
                    "out": outgoing["claim_id"],
                    "in": incoming["claim_id"],
                }
            )
    return {"drawn": drawn, "sample": sorted(sample), "replacements": replacements}


def top_up(pool: Sequence[Mapping[str, Any]], sample: Sequence[str]) -> list[str]:
    """The units the top-up rule adds: the first order goes on over its strata, cap kept."""
    taken = set(sample)
    cases = Counter(unit["case_id"] for unit in pool if unit["claim_id"] in taken)
    added: list[str] = []
    for unit in sorted(pool, key=lambda unit: _hash("nli_sample", unit["claim_id"])):
        if len(added) == TOP_UP_UNITS:
            break
        if unit["stratum"] not in TOP_UP_STRATA or unit["claim_id"] in taken:
            continue
        if cases[unit["case_id"]] >= CAP:
            continue
        added.append(unit["claim_id"])
        cases[unit["case_id"]] += 1
    return sorted(added)


def summary(pool: Sequence[Mapping[str, Any]], sample: Sequence[str]) -> dict[str, Any]:
    """Counts of a sample: by stratum with the weights, by quota, by question."""
    chosen = [unit for unit in pool if unit["claim_id"] in set(sample)]
    strata = Counter(unit["stratum"] for unit in chosen)
    cases = Counter(unit["case_id"] for unit in chosen)
    return {
        "units": len(chosen),
        "strata": {
            name: {"pool": row[1], "sample": strata[name], "weight": row[1] / strata[name]}
            for name, row in STRATA.items()
        },
        "quotas": {
            name: {"least": least, "sample": sum(unit["flags"][name] for unit in chosen)}
            for name, least, _ in QUOTAS
        },
        "questions": len(cases),
        "most_units_a_question": max(cases.values()),
    }


def labelling_units(
    pool: Sequence[Mapping[str, Any]], claims: Sequence[str], labelled: Sequence[str] = ()
) -> list[dict[str, Any]]:
    """The requests that label `claims`: one a (case, text) pair, shown by its lowest id.

    `labelled` are the request ids of an earlier stage: a unit whose pair one of them shows is
    served by that request and gets none of its own.
    """
    by_id = {unit["claim_id"]: unit for unit in pool}
    pairs: dict[tuple[str, str], list[str]] = {}
    for key in sorted(claims):
        unit = by_id[key]
        pairs.setdefault((unit["case_id"], unit["text"]), []).append(key)
    earlier = {(by_id[key]["case_id"], by_id[key]["text"]): key for key in labelled}
    units = []
    for pair, keys in sorted(pairs.items(), key=lambda item: item[1][0]):
        units.append(
            {
                "request_id": earlier.get(pair, keys[0]),
                "serves": keys,
                "new": pair not in earlier,
            }
        )
    return units


def control_order(
    pool: Sequence[Mapping[str, Any]], sample: Sequence[str], tag: str = CONTROL_TAG
) -> list[str]:
    """The sample's units of the control strata in the order the control is drawn in."""
    chosen = set(sample)
    return sorted(
        (
            unit["claim_id"]
            for unit in pool
            if unit["claim_id"] in chosen and unit["stratum"] in CONTROL_STRATA
        ),
        key=lambda key: _hash(tag, key),
    )


def control_partner(order: Sequence[Mapping[str, Any]], index: int, drawn: int) -> int | None:
    """Whose contexts the control shows beside unit `index` of the control order.

    The next drawn unit, cyclically, of another question, whose contexts come from no document
    family of this unit's contexts; None when no drawn unit is such.
    """
    unit = order[index]
    for step in range(1, drawn):
        other = (index + step) % drawn
        if order[other]["case_id"] != unit["case_id"] and not (
            set(order[other]["families"]) & set(unit["families"])
        ):
            return other
    return None


def control_drawn(supported: Sequence[bool]) -> int:
    """How many units of the control order are drawn, given which are supported where retrieved.

    The first `CONTROL_FIRST` always; then on, until `CONTROL_READ` of the drawn are stable and
    supported in their own contexts, or the order ends.
    """
    drawn = min(CONTROL_FIRST, len(supported))
    while drawn < len(supported) and sum(supported[:drawn]) < CONTROL_READ:
        drawn += 1
    return drawn


def request_id(shown: str, pass_number: int, *, control: bool = False) -> str:
    if pass_number not in PASSES:
        raise ValueError("a unit is sent in two passes")
    name = f"{CONTROL_PREFIX}{shown}" if control else shown
    return name + (PASS_SUFFIX if pass_number == 2 else "")


def second_order(request: str, kind: str, names: Sequence[str]) -> list[int]:
    """The order the second pass shows `names` in: by hash, and never the first order."""
    order = sorted(
        range(len(names)), key=lambda index: _hash("pass2", f"{request}:{kind}:{names[index]}")
    )
    if order == list(range(len(names))) and len(names) > 1:
        order = order[1:] + order[:1]
    return order


def presentation(request: str, passages: int) -> dict[str, list[int]]:
    """Which label definition and which context stand at each place of a request."""
    if not request.endswith(PASS_SUFFIX):
        return {"labels": list(range(len(LABELS))), "passages": list(range(passages))}
    return {
        "labels": second_order(request, "label", LABELS),
        "passages": second_order(request, "context", [str(n + 1) for n in range(passages)]),
    }


def request_text(unit: Mapping[str, Any], contexts: Sequence[str], request: str) -> str:
    """The text of one request: the unit in its answer, beside `contexts`.

    Nothing of the request id, the pass, the source, a score or a judge stands in it.
    """
    shown = presentation(request, len(contexts))
    start, end = unit["span"]
    answer = unit["answer"]
    if answer[start:end] != unit["text"]:
        raise ValueError(f"the unit is not at its place in the answer: {unit['claim_id']}")
    marked = f"{answer[:start]}{MARK_OPEN}{answer[start:end]}{MARK_CLOSE}{answer[end:]}"
    return PROMPT_TEMPLATE.format(
        labels="\n".join(f"- {LABEL_DEFINITIONS[LABELS[index]]}" for index in shown["labels"]),
        question=unit["question"].strip(),
        mark_open=MARK_OPEN,
        mark_close=MARK_CLOSE,
        answer=marked.strip(),
        unit=unit["text"],
        passages="\n\n".join(
            f"PASSAGE {place + 1}\n{contexts[index].strip()}"
            for place, index in enumerate(shown["passages"])
        ),
    )


def parse_reply(text: str, passages: int = 5) -> dict[str, Any]:
    """Read one reply in the registered form, or raise ReplyFormatError."""
    replies = [value for value in json_objects(text) if "label" in value]
    if len(replies) != 1:
        raise ReplyFormatError("the reply is not one JSON object with a label")
    reply = replies[0]
    label = reply["label"].strip().upper() if isinstance(reply["label"], str) else None
    if label not in LABELS:
        raise ReplyFormatError("the label is not one of the four")
    flags = reply.get("flags", [])
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ReplyFormatError("the flags are not a list of names")
    named = {flag.strip().upper() for flag in flags}
    if not named <= set(FLAGS):
        raise ReplyFormatError("a flag is not one of the registered")
    numbers = reply.get("passages", [])
    if (
        not isinstance(numbers, list)
        or not all(type(number) is int and 1 <= number <= passages for number in numbers)
        or len(set(numbers)) != len(numbers)
    ):
        raise ReplyFormatError("the passages are not a list of their numbers")
    reason = reply.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ReplyFormatError("no reason")
    return {
        "label": label,
        "flags": [flag for flag in FLAGS if flag in named],
        "passages": sorted(numbers),
        "reason": reason.strip(),
    }


def cited_contexts(reply: Mapping[str, Any], request: str, passages: int = 5) -> list[int]:
    """The stored places (from 0) of the contexts a reply names by their numbers in a request."""
    shown = presentation(request, passages)["passages"]
    return sorted(shown[number - 1] for number in reply["passages"])


class Reference(TypedDict):
    """What two passes come to: `stable`, `unstable` or `invalid`, and the label of a stable one."""

    state: str
    label: str | None


def reference(first: str | None, second: str | None) -> Reference:
    """The reference label of a labelling unit from the labels of its two passes.

    `stable` when both passes give one reduced label, which is then the reference label;
    `unstable` when they differ; `invalid` when a pass has no valid reply.
    """
    if first is None or second is None:
        return {"state": "invalid", "label": None}
    if REDUCED[first] == REDUCED[second]:
        return {"state": "stable", "label": REDUCED[first]}
    return {"state": "unstable", "label": None}


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Cohen's kappa of two labellings; None when one label is all either of them gives."""
    if not pairs:
        return None
    total = len(pairs)
    agreed = sum(left == right for left, right in pairs) / total
    lefts = Counter(left for left, _ in pairs)
    rights = Counter(right for _, right in pairs)
    chance = sum(lefts[label] * rights[label] for label in lefts) / total**2
    if math.isclose(chance, 1.0):
        return None
    return (agreed - chance) / (1 - chance)


def _quantile(ordered: Sequence[float], p: float) -> float:
    position = (len(ordered) - 1) * p
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def kappa_interval(
    rows: Sequence[tuple[str, str, str]], *, seed: int = SEED, resamples: int = RESAMPLES
) -> dict[str, Any]:
    """Kappa of (question, first label, second label) rows with its cluster bootstrap by question.

    Percentile interval over `resamples` resamples of the questions. A resample in which kappa
    is undefined is not counted, and their number is returned.
    """
    clusters: dict[str, list[tuple[str, str]]] = {}
    for case, left, right in rows:
        clusters.setdefault(case, []).append((left, right))
    blocks = [clusters[case] for case in sorted(clusters)]
    point = cohen_kappa([pair for block in blocks for pair in block])
    rng = random.Random(seed)
    values: list[float] = []
    undefined = 0
    for _ in range(resamples):
        drawn = rng.choices(blocks, k=len(blocks)) if blocks else []
        value = cohen_kappa([pair for block in drawn for pair in block])
        if value is None:
            undefined += 1
        else:
            values.append(value)
    values.sort()
    return {
        "kappa": point,
        "ci95": [_quantile(values, 0.025), _quantile(values, 0.975)] if values else None,
        "units": len(rows),
        "questions": len(blocks),
        "resamples": resamples,
        "undefined_resamples": undefined,
    }


def stability(
    units: Sequence[Mapping[str, Any]], control: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """The stability bound of a rubric version, before any judge is joined to a label.

    `units`: one row a labelling unit - `case_id`, `serves` (how many sample units it labels),
    `first` and `second` (the labels of the passes, None for an invalid pass). `control`: one
    row a drawn control unit - `own` (its reference in its own contexts), `first` and `second`
    (its labels beside the contexts of another unit), `partner` (False when it had none).
    """
    states = [reference(unit["first"], unit["second"]) for unit in units]
    sample = sum(unit["serves"] for unit in units)
    counted: Counter[str] = Counter()
    for unit, state in zip(units, states, strict=True):
        counted[state["state"]] += unit["serves"]
    not_stable = counted["unstable"] + counted["invalid"]
    passes = kappa_interval(
        [
            (unit["case_id"], REDUCED[unit["first"]], REDUCED[unit["second"]])
            for unit in units
            if unit["first"] is not None and unit["second"] is not None
        ]
    )
    read = [
        row
        for row in control
        if row["partner"] and row["own"] == {"state": "stable", "label": "supported"}
    ]
    answered = [row for row in read if row["first"] is not None and row["second"] is not None]
    fooled = sum(
        REDUCED[row["first"]] == "supported" and REDUCED[row["second"]] == "supported"
        for row in answered
    )
    failures = []
    if not_stable > UNSTABLE_SHARE * sample:
        failures.append("unstable_share")
    if passes["ci95"] is None or passes["ci95"][0] < PASS_KAPPA:
        failures.append("pass_kappa")
    if len(read) >= CONTROL_READ and fooled > CONTROL_SHARE * len(read):
        failures.append("control")
    return {
        "sample_units": sample,
        "stable": counted["stable"],
        "unstable": counted["unstable"],
        "invalid": counted["invalid"],
        "not_stable_share": not_stable / sample if sample else None,
        "pass_kappa": passes,
        "control": {
            "drawn": len(control),
            "without_partner": sum(not row["partner"] for row in control),
            "read": len(read),
            "answered_in_both_passes": len(answered),
            "supported_in_both_passes": fooled,
            "bounds": len(read) >= CONTROL_READ,
        },
        "failures": failures,
        "ambiguous": bool(failures),
    }
