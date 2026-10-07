"""The parts of the external bases (plan slice 1.6): which questions a run may read, and when.

A base is cut into parts before any run reads one of its questions. The cut takes the cases of
the base as converted (``evaluation/external_bases.json``, ``cases_sha256``) and the seed, and
nothing else: no model, no index, no result of a run. Its rules are ``RULES``:

- **Order.** Everything is drawn by one order: ascending SHA-256 of
  ``'<seed>:<base>:<kind>:<id>'``, the kind being ``document`` or ``question``.
- **ConditionalQA.** The unit is the document: a question is asked about one page, and the
  questions of a page share its text. The documents that carry a question stand in the order and
  are cut into three runs — ``tuning``, ``locked``, ``reserve`` — whose sizes differ by one at
  most. A question stands in the part of its document, a not-answerable one too. The pages that
  carry no question stay in the index and belong to no part.
- **WixQA.** ``locked`` is every ExpertWritten question. ``tuning`` is the Simulated questions
  that share no gold article with a locked one; the Simulated questions that do are
  ``excluded``, because tuning on them would tune on a gold article of the locked part. There is
  no reserve.
- **MultiHop-RAG.** ``advisory`` is the questions of the types inference and null, the sub-slice
  of plan slice 1.5d. Nothing of the base is locked: its labels were written by a model and it
  decides nothing. The other types stand in no part.

A part is ``open`` to development runs or ``locked``. A locked part is read by no run until an
entry of ``opened`` in the registration names it, and only acceptance 4.1 adds one: ``read``
refuses before that, so opening a part is a commit that changes the registration and the test
that holds ``opened`` empty. Today an entry opens the whole of a part; the spec registers that a
locked part is read once, by one selection, and that an entry will name the selection.

A *selection* is what one run reads of a part: a prefix of the part's order, by a rule that
names its size. A size chosen later therefore draws nothing anew, and of two selections by one
rule on one stratum with one number of questions a document the larger holds the smaller.
``pilot`` is registered here; a later selection is added to the file by a commit, before the run
that reads it.

``evaluation/external_parts.json`` holds the ids of every part and selection, in order, with
their SHA-256. An id names a row of a pinned public file and carries none of its text, so the
lists of ids are read as provenance and are committed with the counts and the digests; the
questions, the texts and the names of the documents stay on the hosts (``external_bases.json``,
"redistribution").

Usage: python -m evaluation.external_parts --data DIR [--write]

    DIR holds <base>/cases.jsonl of the three bases, as ``scripts.external_base convert`` wrote
    them. Without --write the registration is rebuilt and compared byte for byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation import external_bases as bases
from evaluation.semantic_ruler import family_clusters

ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = ROOT / "evaluation" / "external_parts.json"
REGISTERED = "2026-10-05"
SEED = 20260925
OPEN = "open"
LOCKED = "locked"
ACCESS = {
    "conditionalqa": {"tuning": OPEN, "locked": LOCKED, "reserve": LOCKED},
    "wixqa": {"tuning": OPEN, "locked": LOCKED, "excluded": LOCKED},
    "multihoprag": {"advisory": OPEN},
}
ADVISORY_TYPES = ("inference_query", "null_query")
PILOT: dict[str, dict[str, Any]] = {
    "conditionalqa": {"part": "tuning", "stratum": "primary", "documents": 25, "per_document": 2},
    "wixqa": {"part": "tuning", "questions": 40},
}
RULES = {
    "order": (
        "ascending SHA-256 of '<seed>:<base>:<kind>:<id>', the kind being 'document' or "
        "'question'; nothing else is drawn"
    ),
    "conditionalqa": (
        "the documents that carry a question, in the order, are cut into three runs whose sizes "
        "differ by one at most, an earlier run the larger: tuning, locked, reserve; a question "
        "stands in the part of its document, a not-answerable one too; inside a part the "
        "questions stand by document, and those of one document by the order"
    ),
    "wixqa": (
        "locked is every ExpertWritten question; tuning is the Simulated questions that share "
        "no gold article with a locked one; excluded is the Simulated questions that do; each "
        "part in the order; there is no reserve"
    ),
    "multihoprag": (
        "advisory is the questions of the types inference_query and null_query, in the order; "
        "nothing is locked; the other types stand in no part"
    ),
    "strata": (
        "ConditionalQA: primary - an answerable question with an evidence group and no "
        "unresolved evidence, the denominator of all_evidence_coverage; several_sections - a "
        "primary question whose evidence cannot be placed in one section of its page; a "
        "not-answerable question stands outside both. WixQA and MultiHop-RAG: the stratum the "
        "case carries"
    ),
    "clusters": (
        "ConditionalQA: the primary questions of one document; WixQA and MultiHop-RAG: the "
        "questions joined by a shared gold document, directly or through other questions, "
        "counted inside the part or the selection that is read"
    ),
    "selection": (
        "a prefix of the order of its part, read on the questions of the stratum the rule "
        "names, or on all of them when it names none: by documents - the first documents that "
        "carry at least the asked number of such questions, and of each its first ones up to "
        "that number; by questions - the first such questions of the part"
    ),
    "access": (
        "open - a development run may read the part; locked - no run reads a question of the "
        "part until an entry of 'opened' names it, and acceptance 4.1 alone adds one"
    ),
}


class Locked(PermissionError):
    """A run asked for questions of a part that acceptance has not opened."""


def rank(base: str, kind: str, identifier: str) -> str:
    return hashlib.sha256(f"{SEED}:{base}:{kind}:{identifier}".encode()).hexdigest()


def in_order(base: str, kind: str, identifiers: Iterable[str]) -> list[str]:
    return sorted(identifiers, key=lambda identifier: (rank(base, kind, identifier), identifier))


def digest(identifiers: Iterable[str]) -> str:
    """SHA-256 of a list of ids, one a line."""
    return hashlib.sha256("".join(f"{item}\n" for item in identifiers).encode()).hexdigest()


def primary(case: Mapping[str, Any]) -> bool:
    """Whether a ConditionalQA question stands in the denominator of ``all_evidence_coverage``."""
    return (
        case["stratum"] == "answerable"
        and bool(case["evidence_groups"])
        and not case["unresolved_evidence"]
    )


def in_stratum(base: str, case: Mapping[str, Any], stratum: str) -> bool:
    """Whether a case belongs to a stratum a selection rule may name."""
    if base != "conditionalqa" or stratum == "not_answerable":
        return bool(case["stratum"] == stratum)
    if stratum == "primary":
        return primary(case)
    if stratum == "several_sections":
        return primary(case) and bases.evidence_spread(case["evidence_groups"], "section")
    raise ValueError(f"unregistered stratum of ConditionalQA: {stratum}")


def _questions(base: str, cases: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    by_id = {case["case_id"]: case for case in cases}
    return [by_id[case_id] for case_id in in_order(base, "question", by_id)]


def _sizes(values: Iterable[int]) -> dict[str, int]:
    """How many clusters there are of each size."""
    return {str(size): count for size, count in sorted(Counter(values).items())}


def _components(cases: Sequence[Mapping[str, Any]]) -> list[int]:
    """Sizes of the clusters that shared gold documents make of the cases that have gold."""
    with_gold = {case["case_id"]: case["gold_sources"] for case in cases if case["gold_sources"]}
    return [len(cluster) for cluster in family_clusters(with_gold)]


def _conditionalqa_counts(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    per_document = Counter(case["document"] for case in cases if primary(case))
    several = [case for case in cases if in_stratum("conditionalqa", case, "several_sections")]
    several_per_document = Counter(case["document"] for case in several)
    documents = list(dict.fromkeys(case["document"] for case in cases))
    return {
        "documents": len(documents),
        "documents_sha256": digest(documents),
        "answerable": sum(case["stratum"] == "answerable" for case in cases),
        "not_answerable": sum(case["stratum"] == "not_answerable" for case in cases),
        "primary": sum(per_document.values()),
        "primary_with_evidence_in_several_sections": len(several),
        "clusters": len(per_document),
        "clusters_with_a_several_section_question": len({case["document"] for case in several}),
        "cluster_sizes": _sizes(per_document.values()),
        # The questions of each stratum a document carries, the documents in the order of the
        # part: what a prefix of the part holds can be counted without its cases.
        "primary_by_document": [per_document[document] for document in documents],
        "several_sections_by_document": [several_per_document[document] for document in documents],
    }


def _gold_counts(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    articles = sorted({name for case in cases for name in case["gold_sources"]})
    components = _components(cases)
    return {
        "gold_documents": len(articles),
        "gold_documents_sha256": digest(articles),
        "questions_by_gold_documents": _sizes(len(case["gold_sources"]) for case in cases),
        "distinct_gold_sets": len({tuple(sorted(case["gold_sources"])) for case in cases}),
        "clusters": len(components),
        "cluster_sizes": _sizes(components),
    }


def _counts(base: str, cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if base == "conditionalqa":
        return _conditionalqa_counts(cases)
    counts = _gold_counts(cases)
    if base == "multihoprag":
        counts["questions_by_type"] = dict(
            sorted(Counter(case["stratum"] for case in cases).items())
        )
    return counts


def _listed(base: str, cases: Sequence[Mapping[str, Any]], **head: Any) -> dict[str, Any]:
    ids = [case["case_id"] for case in cases]
    return {
        **head,
        "cases": len(ids),
        "cases_sha256": digest(ids),
        **_counts(base, cases),
        "case_ids": ids,
    }


def _thirds(count: int) -> tuple[int, int, int]:
    size, extra = divmod(count, 3)
    return size + (extra > 0), size + (extra > 1), size


def split(base: str, cases: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    """The parts of a base: the cases of each, in the order of the part."""
    if base == "conditionalqa":
        by_document: dict[str, list[Mapping[str, Any]]] = {}
        for case in cases:
            by_document.setdefault(case["document"], []).append(case)
        documents = in_order(base, "document", by_document)
        parts: dict[str, list[Mapping[str, Any]]] = {}
        start = 0
        for name, size in zip(ACCESS[base], _thirds(len(documents)), strict=True):
            parts[name] = [
                case
                for document in documents[start : start + size]
                for case in _questions(base, by_document[document])
            ]
            start += size
        return parts
    if base == "wixqa":
        locked = [case for case in cases if case["stratum"] == "expertwritten"]
        simulated = [case for case in cases if case["stratum"] == "simulated"]
        if len(locked) + len(simulated) != len(cases):
            raise ValueError("a WixQA case of an unregistered stratum")
        held = {name for case in locked for name in case["gold_sources"]}
        shared = [case for case in simulated if held.intersection(case["gold_sources"])]
        free = [case for case in simulated if not held.intersection(case["gold_sources"])]
        return {
            "tuning": _questions(base, free),
            "locked": _questions(base, locked),
            "excluded": _questions(base, shared),
        }
    if base == "multihoprag":
        return {
            "advisory": _questions(
                base, [case for case in cases if case["stratum"] in ADVISORY_TYPES]
            )
        }
    raise ValueError(f"unregistered base: {base}")


def select(
    base: str, part: Sequence[Mapping[str, Any]], rule: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """The cases a rule takes of a part given in its order."""
    stratum = rule.get("stratum")
    members = [case for case in part if stratum is None or in_stratum(base, case, stratum)]
    if "questions" in rule:
        if len(members) < rule["questions"]:
            raise ValueError("the part holds fewer questions than the rule asks")
        return members[: rule["questions"]]
    if base != "conditionalqa" or stratum is None:
        raise ValueError("a selection by documents needs a stratum of ConditionalQA")
    by_document: dict[str, list[Mapping[str, Any]]] = {}
    for case in members:
        by_document.setdefault(case["document"], []).append(case)
    carrying = [group for group in by_document.values() if len(group) >= rule["per_document"]]
    if len(carrying) < rule["documents"]:
        raise ValueError("the part holds fewer such documents than the rule asks")
    return [
        case for group in carrying[: rule["documents"]] for case in group[: rule["per_document"]]
    ]


def build_base(
    base: str,
    cases: Sequence[Mapping[str, Any]],
    cases_sha256: str,
    *,
    selection_rules: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The registered block of a base and its selections."""
    parts = split(base, cases)
    block = {
        "cases": len(cases),
        "cases_sha256": cases_sha256,
        "in_no_part": len(cases) - sum(len(part) for part in parts.values()),
        "parts": {
            name: _listed(base, part, access=ACCESS[base][name]) for name, part in parts.items()
        },
    }
    rules: dict[str, Mapping[str, Any]] = {"pilot": PILOT[base]} if base in PILOT else {}
    rules.update({name: rule for name, rule in (selection_rules or {}).items() if name not in rules})
    selections = {
        name: _listed(base, select(base, parts[rule["part"]], rule), rule=rule)
        for name, rule in rules.items()
    }
    return block, selections


def build(
    cases: Mapping[str, Sequence[Mapping[str, Any]]],
    cases_sha256: Mapping[str, str],
    *,
    selection_rules: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    built = {
        base: build_base(
            base, cases[base], cases_sha256[base],
            selection_rules=(selection_rules or {}).get(base),
        )
        for base in ACCESS
    }
    return {
        "schema_version": 1,
        "registered": REGISTERED,
        "seed": SEED,
        "rules": RULES,
        "bases": {base: block for base, (block, _) in built.items()},
        "selections": {base: chosen for base, (_, chosen) in built.items() if chosen},
        "opened": [],
    }


def dump(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def registration(path: Path | None = None) -> dict[str, Any]:
    registered: dict[str, Any] = json.loads((path or REGISTRATION).read_text(encoding="utf-8"))
    if registered["seed"] != SEED or registered["rules"] != RULES:
        raise ValueError("the registration names another seed or other rules")
    access = {
        base: {name: part["access"] for name, part in block["parts"].items()}
        for base, block in registered["bases"].items()
    }
    if access != ACCESS:
        raise ValueError("the registration names other parts or another access")
    return registered


def is_open(registered: Mapping[str, Any], base: str, part: str) -> bool:
    if registered["bases"][base]["parts"][part]["access"] == OPEN:
        return True
    return any(entry["base"] == base and entry["part"] == part for entry in registered["opened"])


def read(
    registered: Mapping[str, Any],
    base: str,
    *,
    part: str | None = None,
    selection: str | None = None,
) -> list[str]:
    """The case ids of a part or of a selection, in order; a locked part is refused."""
    if (part is None) == (selection is None):
        raise ValueError("name a part or a selection")
    if selection is not None:
        chosen = registered["selections"][base][selection]
        part = chosen["rule"]["part"]
    else:
        chosen = registered["bases"][base]["parts"][part]
    if not is_open(registered, base, str(part)):
        raise Locked(f"{base}: the part '{part}' is locked until acceptance 4.1 opens it")
    return list(chosen["case_ids"])


def verify(
    registered: Mapping[str, Any], base: str, cases: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Hold the registered parts of a base to its cases; the counts that may leave the host.

    The first check rebuilds the block. The others read the registered ids alone, so they do not
    rest on the code that drew them: no question stands in two parts, no document of
    ConditionalQA and no gold article of the tuning and locked parts of WixQA is shared, and a
    selection lies inside its part.
    """
    block = registered["bases"][base]
    chosen = registered["selections"].get(base, {})
    if (block, chosen) != build_base(
        base, cases, block["cases_sha256"],
        selection_rules={name: selection["rule"] for name, selection in chosen.items()},
    ):
        raise ValueError(f"{base}: the registered parts are not those the rules give")
    by_id = {case["case_id"]: case for case in cases}
    ids = {name: part["case_ids"] for name, part in block["parts"].items()}
    listed = [case_id for part in ids.values() for case_id in part]
    if len(set(listed)) != len(listed) or not set(listed) <= set(by_id):
        raise ValueError(f"{base}: a question stands in two parts or in no case file")
    if base == "conditionalqa":
        held = {
            name: {by_id[case_id]["document"] for case_id in part} for name, part in ids.items()
        }
        apart: tuple[str, ...] = ("tuning", "locked", "reserve")
    else:
        held = {
            name: {source for case_id in part for source in by_id[case_id]["gold_sources"]}
            for name, part in ids.items()
        }
        apart = ("tuning", "locked")
    shared = {
        f"{first}/{second}": len(held[first] & held[second])
        for position, first in enumerate(apart)
        for second in apart[position + 1 :]
        if first in held and second in held
    }
    if any(shared.values()):
        raise ValueError(f"{base}: parts share a document: {shared}")
    for name, selection in chosen.items():
        if not set(selection["case_ids"]) <= set(ids[selection["rule"]["part"]]):
            raise ValueError(f"{base}: the selection '{name}' leaves its part")
    slim = {"case_ids"}
    return {
        "base": base,
        "seed": registered["seed"],
        "cases": block["cases"],
        "cases_sha256": block["cases_sha256"],
        "in_no_part": block["in_no_part"],
        "shared_between_parts": shared,
        "parts": {
            name: {key: value for key, value in part.items() if key not in slim}
            for name, part in block["parts"].items()
        },
        "selections": {
            name: {key: value for key, value in selection.items() if key not in slim}
            for name, selection in chosen.items()
        },
    }


def load_cases(directory: Path, base: str, converted: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The cases of a converted base from its directory, checked against ``external_bases.json``."""
    raw = (directory / "cases.jsonl").read_bytes()
    if bases.sha256(raw) != converted["bases"][base]["converted"]["cases_sha256"]:
        raise ValueError(f"{base}: cases.jsonl differs from the registered conversion")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, required=True, help="holds <base>/cases.jsonl")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    converted = bases.registration()
    cases = {base: load_cases(args.data / base, base, converted) for base in ACCESS}
    existing = json.loads(REGISTRATION.read_text(encoding="utf-8")) if REGISTRATION.exists() else {}
    built = build(
        cases, {base: converted["bases"][base]["converted"]["cases_sha256"] for base in ACCESS},
        selection_rules={
            base: {name: selection["rule"] for name, selection in chosen.items()}
            for base, chosen in existing.get("selections", {}).items()
        },
    )
    if args.write:
        REGISTRATION.write_bytes(dump(built))
    elif REGISTRATION.read_bytes() != dump(built):
        print("the registration differs from the one the rules give")
        return 1
    registered = registration()
    report = {base: verify(registered, base, cases[base]) for base in ACCESS}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
