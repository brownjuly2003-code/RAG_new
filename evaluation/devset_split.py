"""The split of plan step 1.3c: blocks of document families and the draw order of each split.

Computed from the registered corpus, the registered family map and the verified pilot cases.
No model takes part and no result is read: the file this module writes is registered before a
draft of step 1.3d exists, and its test rebuilds it from the inputs.

    python -m evaluation.devset_split            compare the registered file with a rebuild
    python -m evaluation.devset_split --write    write evaluation/devset_split.json

A block is what a new case may draw its documents from. A topic family of two or more documents
is a block; families of one document are paired by the similarity of their texts, because a case
of several documents needs a second document and a pair joins the fewest families. The unit of
independence stays the family: a pair is one cluster once a case draws on both of its families
and two clusters until then. The draw order of a split goes round its blocks, one section a
round, so the cases spread over as many blocks as the split has. Each position of the order has
its primary class from a fixed sequence and takes the first section that passes the test of that
class: the script decides what a section may be asked for, the generator of step 1.3d does not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation import devset_sources as sources
from evaluation.semantic_ruler import family_clusters

ROOT = Path(__file__).resolve().parents[1]
REGISTERED = ROOT / "evaluation/devset_split.json"
VERSION = "devset-split-v1"
SEED = 20260925
CLASSES = ("multi-doc", "single-doc", "aggregation", "needs-refusal/clarification")
SEVERAL_DOCUMENTS = ("multi-doc", "aggregation")
DEV_NEW = {"single-doc": 8, "multi-doc": 10, "aggregation": 6, "needs-refusal/clarification": 6}
HOLDOUT_SHARES = {
    "single-doc": 24,
    "multi-doc": 40,
    "aggregation": 16,
    "needs-refusal/clarification": 20,
}
HOLDOUT_ROUNDS = 4
AGGREGATION_ITEMS = 3
# What the first verification of a split leaves of a seated position (rule `replacement`).
OUTCOMES = ("confirmed", "dropped", "empty")
TOKEN = re.compile(r"[^\W\d_]{3,}")
ITEM = re.compile(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s+\S|^\s*\|.*\|\s*$")
RULES = {
    "frame": "sections of devset_sources.eligible_sections that no pilot case used as its "
    "seed or partner section",
    "similarity": "cosine of TF-IDF vectors, rounded to 9 decimals: tokens are runs of three "
    "or more letters, case-folded; idf = ln(documents / documents with the token) over the "
    "eligible-section text of every corpus document",
    "blocks": "a topic family of two or more documents is a block; families of one document "
    "are paired within the split in descending similarity of their eligible-section text, "
    "ties by document name; a family left over is a block of its own",
    "order": "blocks by the number of pilot cases they hold, then by SHA-256 of "
    "'<seed>:<split>:block:<block_id>'; sections of a block by SHA-256 of "
    "'<seed>:<split>:section:<source_id>:<char_start>'; round r takes the r-th section of "
    "every block that has one",
    "sequence": "position p takes the class with the largest quota * p - placed * total, "
    "ties in the order multi-doc, single-doc, aggregation, needs-refusal/clarification",
    "tests": "single-doc and needs-refusal/clarification: every section; multi-doc: the block "
    "has another document with a frame section, and the pair of the section and its partner "
    "is the pair of no earlier position; aggregation: the multi-doc test, and the section "
    "holds three or more list items or table rows",
    "partner": "the frame section of the other documents of the block most similar to the "
    "seed section, ties by document name and offset",
    "cap": "holdout: a section is passed over when its block holds four positions; "
    "development: none",
    "quota": "development: 18 single-doc, 20 multi-doc, 10 aggregation and 12 "
    "needs-refusal/clarification of 60, less the classes of the 30 pilot cases; holdout: "
    "single-doc 24, multi-doc 40, aggregation 16 and needs-refusal/clarification 20 per cent "
    "of the positions the cap leaves room for — the sum over the blocks of the smaller of "
    "four and the frame sections of the block — by largest remainder, ties in the order of "
    "the sequence",
    "replacement": "the order and the tests are applied to the state the first verification "
    "of the split left: a section that was the seed of any draft of the split, dropped drafts "
    "and earlier replacements included, is not taken; a pair of a section and its partner "
    "that any draft or earlier replacement used is the pair of an earlier position; the cap "
    "counts the confirmed drafts of a block and the replacements seated in it, not its "
    "dropped drafts; the partner is found by the partner rule among all frame sections of "
    "the other documents of the block",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rank(*parts: Any) -> str:
    text = ":".join(str(part) for part in (SEED, *parts))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key(section: Mapping[str, Any]) -> tuple[str, int]:
    return section["source_id"], section["char_start"]


def weights(texts: Mapping[str, str]) -> dict[str, float]:
    """Inverse document frequency of every token over the named texts."""
    counted = Counter(
        token for text in texts.values() for token in set(TOKEN.findall(text.casefold()))
    )
    return {token: math.log(len(texts) / count) for token, count in counted.items()}


def vector(text: str, idf: Mapping[str, float]) -> dict[str, float]:
    counted = Counter(TOKEN.findall(text.casefold()))
    raw = {token: count * idf.get(token, 0.0) for token, count in counted.items()}
    norm = math.sqrt(math.fsum(value * value for value in raw.values()))
    return {token: value / norm for token, value in raw.items() if value} if norm else {}


def similarity(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if len(right) < len(left):
        left, right = right, left
    shared = (value * right[token] for token, value in left.items() if token in right)
    return round(math.fsum(shared), 9)


def build_blocks(
    families: Mapping[str, Sequence[str]], vectors: Mapping[str, Mapping[str, float]]
) -> list[dict[str, Any]]:
    """Blocks of one split: a family of several documents as it is, the rest in pairs."""
    blocks: list[dict[str, Any]] = [
        {"documents": sorted(members), "families": [family], "basis": "family"}
        for family, members in sorted(families.items())
        if len(members) > 1
    ]
    single = {members[0]: family for family, members in families.items() if len(members) == 1}
    candidates = sorted(
        (-similarity(vectors[a], vectors[b]), a, b) for a in single for b in single if a < b
    )
    paired: set[str] = set()
    for negative, a, b in candidates:
        if a in paired or b in paired:
            continue
        paired.update((a, b))
        blocks.append(
            {
                "documents": [a, b],
                "families": sorted((single[a], single[b])),
                "basis": "pair",
                "similarity": -negative,
            }
        )
    for document in sorted(set(single) - paired):
        blocks.append({"documents": [document], "families": [single[document]], "basis": "single"})
    for block in blocks:
        joined = "|".join(block["documents"]).encode("utf-8")
        block["block_id"] = "block-" + hashlib.sha256(joined).hexdigest()[:12]
    return sorted(blocks, key=lambda block: block["block_id"])


def draw_order(
    split: str,
    blocks: Sequence[Mapping[str, Any]],
    frame: Sequence[dict[str, Any]],
    held: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Round the blocks, one section a round; blocks that hold pilot cases come last."""
    by_document: dict[str, list[dict[str, Any]]] = {}
    for section in frame:
        by_document.setdefault(section["source_id"], []).append(section)
    queues = []
    for block in sorted(
        blocks,
        key=lambda b: (held.get(b["block_id"], 0), rank(split, "block", b["block_id"])),
    ):
        sections = [s for document in block["documents"] for s in by_document.get(document, [])]
        queues.append(sorted(sections, key=lambda s: rank(split, "section", *key(s))))
    order: list[dict[str, Any]] = []
    for turn in range(max(map(len, queues), default=0)):
        order.extend(queue[turn] for queue in queues if turn < len(queue))
    return order


def quotas(shares: Mapping[str, int], total: int) -> dict[str, int]:
    """Largest-remainder counts of the registered shares, ties in class order."""
    whole = sum(shares.values())
    counts = {name: shares[name] * total // whole for name in CLASSES}
    by_remainder = sorted(
        CLASSES, key=lambda name: (-(shares[name] * total % whole), CLASSES.index(name))
    )
    for name in by_remainder[: total - sum(counts.values())]:
        counts[name] += 1
    return counts


def class_sequence(counts: Mapping[str, int]) -> list[str]:
    """Spread the classes evenly along the positions; exact, in whole numbers."""
    total = sum(counts.values())
    placed: Counter[str] = Counter()
    sequence = []
    for position in range(1, total + 1):
        chosen = max(
            CLASSES,
            key=lambda name: (counts[name] * position - placed[name] * total, -CLASSES.index(name)),
        )
        placed[chosen] += 1
        sequence.append(chosen)
    return sequence


def list_items(body: str) -> int:
    return len(ITEM.findall(body))


class Seating:
    """What positions are seated in: the order, the tests of the classes and what is used.

    `taken` are the sections that were a seed, `pairs` the pairs of a section and its partner
    that a position used, `seated` the positions a block holds for the cap.
    """

    def __init__(
        self,
        order: Sequence[dict[str, Any]],
        blocks: Sequence[Mapping[str, Any]],
        texts: Mapping[str, str],
        idf: Mapping[str, float],
        cap: int | None,
    ) -> None:
        self.order = order
        self.texts = texts
        self.idf = idf
        self.cap = cap
        self.block_of = {document: block for block in blocks for document in block["documents"]}
        self.by_document: dict[str, list[dict[str, Any]]] = {}
        for section in order:
            self.by_document.setdefault(section["source_id"], []).append(section)
        self.vectors: dict[tuple[str, int], dict[str, float]] = {}
        self.taken: set[tuple[str, int]] = set()
        self.pairs: set[frozenset[tuple[str, int]]] = set()
        self.seated: Counter[str] = Counter()

    def body(self, section: Mapping[str, Any]) -> str:
        return self.texts[section["source_id"]][section["char_start"] : section["char_end"]]

    def vectorised(self, section: Mapping[str, Any]) -> dict[str, float]:
        if key(section) not in self.vectors:
            self.vectors[key(section)] = vector(self.body(section), self.idf)
        return self.vectors[key(section)]

    def partner(self, section: Mapping[str, Any]) -> dict[str, Any] | None:
        """The rule `partner`: among all sections of the order of the block's other documents."""
        block = self.block_of[section["source_id"]]
        others = [
            other
            for document in block["documents"]
            if document != section["source_id"]
            for other in self.by_document.get(document, [])
        ]
        if not others:
            return None
        own = self.vectorised(section)
        return min(
            others, key=lambda other: (-similarity(own, self.vectorised(other)), *key(other))
        )

    def place(self, number: int, primary_class: str) -> dict[str, Any]:
        """Seat one position at the first section of the order that passes the test of its class."""
        place: dict[str, Any] = {
            "position": number,
            "primary_class": primary_class,
            "block_id": None,
            "seed": None,
            "partner": None,
        }
        for section in self.order:
            block_id = self.block_of[section["source_id"]]["block_id"]
            if key(section) in self.taken or (
                self.cap is not None and self.seated[block_id] >= self.cap
            ):
                continue
            other = None
            if primary_class in SEVERAL_DOCUMENTS:
                other = self.partner(section)
                if other is None or frozenset((key(section), key(other))) in self.pairs:
                    continue
                if (
                    primary_class == "aggregation"
                    and list_items(self.body(section)) < AGGREGATION_ITEMS
                ):
                    continue
                self.pairs.add(frozenset((key(section), key(other))))
            self.taken.add(key(section))
            self.seated[block_id] += 1
            place.update(block_id=block_id, seed=section, partner=other)
            break
        return place


def seat(
    sequence: Sequence[str],
    order: Sequence[dict[str, Any]],
    blocks: Sequence[Mapping[str, Any]],
    texts: Mapping[str, str],
    idf: Mapping[str, float],
    cap: int | None,
) -> list[dict[str, Any]]:
    """Give every position the first section of the order that passes the test of its class."""
    seating = Seating(order, blocks, texts, idf, cap)
    return [
        seating.place(number, primary_class) for number, primary_class in enumerate(sequence, 1)
    ]


def reseat(
    positions: Sequence[Mapping[str, Any]],
    outcomes: Mapping[int, str],
    order: Sequence[dict[str, Any]],
    blocks: Sequence[Mapping[str, Any]],
    texts: Mapping[str, str],
    idf: Mapping[str, float],
    cap: int | None,
) -> list[dict[str, Any]]:
    """The place of the replacement of every dropped draft of a split, by the rule `replacement`.

    `outcomes` says what the first verification left of every seated position: its draft was
    confirmed, its draft was dropped, or it is empty because no draft was written for it. The
    order and the tests are those of `seat`, applied to that state. A draft, confirmed or
    dropped, bars its seed section and its pair; a confirmed draft counts for the cap of its
    block and a dropped one does not. A position that never had a draft bars nothing: its
    section was the seed of no draft. The dropped positions are replaced in ascending number,
    each on the state the replacements before it left; a place with no section stays empty.
    """
    seated = sorted(
        (place for place in positions if place["seed"] is not None),
        key=lambda place: place["position"],
    )
    if set(outcomes) != {place["position"] for place in seated} or not set(
        outcomes.values()
    ) <= set(OUTCOMES):
        raise ValueError("the outcomes are not those of the seated positions of the split")
    seating = Seating(order, blocks, texts, idf, cap)
    for place in seated:
        if outcomes[place["position"]] == "empty":
            continue
        seating.taken.add(key(place["seed"]))
        if place["partner"] is not None:
            seating.pairs.add(frozenset((key(place["seed"]), key(place["partner"]))))
        if outcomes[place["position"]] == "confirmed":
            seating.seated[place["block_id"]] += 1
    return [
        seating.place(place["position"], place["primary_class"])
        for place in seated
        if outcomes[place["position"]] == "dropped"
    ]


def family_index(register: Mapping[str, Any]) -> dict[str, str]:
    """The family of every document of the family map."""
    return {
        member["source_id"]: family["family_id"]
        for family in register["families"]
        for member in family["members"]
    }


def case_families(
    positions: Sequence[Mapping[str, Any]],
    family_of: Mapping[str, str],
    pilot: Sequence[Mapping[str, Any]] = (),
) -> dict[str, list[str]]:
    """The case–family graph of a split: each seated position and pilot case with its families."""
    graph = {
        f"position-{place['position']}": sorted(
            {
                family_of[section["source_id"]]
                for section in (place["seed"], place["partner"])
                if section is not None
            }
        )
        for place in positions
        if place["seed"] is not None
    }
    graph.update(
        {case["case_id"]: sorted({family_of[name] for name in case["documents"]}) for case in pilot}
    )
    return graph


def eligible_text(
    texts: Mapping[str, str], eligible: Sequence[Mapping[str, Any]]
) -> dict[str, str]:
    """The eligible-section text of every corpus document: what the similarity is computed on."""
    joined: dict[str, str] = {name: "" for name in texts}
    for section in eligible:
        name = section["source_id"]
        joined[name] += texts[name][section["char_start"] : section["char_end"]] + "\n"
    return joined


def replacements(
    split: str,
    registered: Mapping[str, Any],
    texts: Mapping[str, str],
    outcomes: Mapping[int, str],
) -> list[dict[str, Any]]:
    """Apply the rule `replacement` to one split of the registered file and this corpus."""
    part = registered["splits"][split]
    eligible = sources.eligible_sections(dict(texts))
    by_key = {key(section): section for section in eligible}
    try:
        order = [by_key[name, start] for name, start in part["order"]]
    except KeyError:
        raise ValueError("the registered order is not of this corpus") from None
    return reseat(
        part["positions"],
        outcomes,
        order,
        part["blocks"],
        texts,
        weights(eligible_text(texts, eligible)),
        HOLDOUT_ROUNDS if split == "holdout" else None,
    )


def build(
    texts: Mapping[str, str], register: Mapping[str, Any], pilot: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """The registered split, from the corpus texts, the family map and the pilot cases."""
    eligible = sources.eligible_sections(dict(texts))
    used = {
        key(section)
        for case in pilot
        for section in [case["seed_selected_source_section"], *case["partner_sections"]]
    }
    frame = [section for section in eligible if key(section) not in used]
    frame_text = eligible_text(texts, eligible)
    idf = weights(frame_text)
    vectors = {name: vector(text, idf) for name, text in frame_text.items()}
    members = {
        family["family_id"]: [member["source_id"] for member in family["members"]]
        for family in register["families"]
    }
    family_of = family_index(register)
    reserve = set(register["holdout_reserve_families"])
    result: dict[str, Any] = {
        "version": VERSION,
        "seed": SEED,
        "rules": RULES,
        "frame_sections": {"eligible": len(eligible), "used_by_pilot": len(eligible) - len(frame)},
        "splits": {},
    }
    for split in ("development", "holdout"):
        families = {
            family: names
            for family, names in members.items()
            if (family in reserve) == (split == "holdout")
        }
        documents = {name for names in families.values() for name in names}
        blocks = build_blocks(families, vectors)
        split_frame = [section for section in frame if section["source_id"] in documents]
        held: Counter[str] = Counter()
        if split == "development":
            for case in pilot:
                for block in blocks:
                    held[block["block_id"]] += bool(
                        set(case["documents"]) & set(block["documents"])
                    )
        order = draw_order(split, blocks, split_frame, held)
        per_block = Counter(
            block["block_id"]
            for block in blocks
            for document in block["documents"]
            for section in split_frame
            if section["source_id"] == document
        )
        if split == "development":
            counts, cap = dict(DEV_NEW), None
        else:
            cap = HOLDOUT_ROUNDS
            counts = quotas(HOLDOUT_SHARES, sum(min(cap, per_block[b["block_id"]]) for b in blocks))
        positions = seat(class_sequence(counts), order, blocks, texts, idf, cap)
        seated = [place for place in positions if place["seed"] is not None]
        graph = case_families(positions, family_of, pilot if split == "development" else ())
        clusters = family_clusters(graph)
        result["splits"][split] = {
            "families": len(families),
            "documents": len(documents),
            "frame_sections": len(split_frame),
            "blocks": [
                {
                    **block,
                    "frame_sections": per_block[block["block_id"]],
                    "pilot_cases": held[block["block_id"]],
                }
                for block in blocks
            ],
            "quotas": counts,
            "positions": positions,
            "seated": dict(Counter(place["primary_class"] for place in seated)),
            "empty_positions": [place["position"] for place in positions if place["seed"] is None],
            "cases": len(graph),
            "clusters": len(clusters),
            "cluster_sizes": sorted((len(cluster) for cluster in clusters), reverse=True),
            "order": [list(key(section)) for section in order],
        }
    return result


def load_inputs() -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    evaluation = ROOT / "evaluation"
    manifest = json.loads(
        (evaluation / "aircargo_corpus.manifest.json").read_text(encoding="utf-8")
    )
    texts = sources.read_sources(manifest, sources.corpus_directory())
    register = json.loads((evaluation / "document_families.json").read_text(encoding="utf-8"))
    pilot_path = evaluation / "devset_pilot_verified.jsonl"
    pilot = [
        json.loads(line) for line in pilot_path.read_text(encoding="utf-8").splitlines() if line
    ]
    inputs = {
        "corpus_sha256": manifest["corpus_sha256"],
        "corpus_manifest_sha256": sha256(evaluation / "aircargo_corpus.manifest.json"),
        "families_sha256": sha256(evaluation / "document_families.json"),
        "pilot_verified_sha256": sha256(pilot_path),
    }
    return texts, register, pilot, inputs


def rebuilt() -> dict[str, Any]:
    texts, register, pilot, inputs = load_inputs()
    return {**build(texts, register, pilot), "inputs": inputs}


def dump(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    text = dump(rebuilt())
    if args.write:
        REGISTERED.write_text(text, encoding="utf-8", newline="\n")
    elif REGISTERED.read_text(encoding="utf-8") != text:
        print("the registered split differs from a rebuild")
        return 1
    value = json.loads(text)
    for split, summary in value["splits"].items():
        print(
            split,
            {
                name: summary[name]
                for name in ("families", "documents", "frame_sections", "cases", "clusters")
            },
            "blocks",
            dict(Counter(block["basis"] for block in summary["blocks"])),
            "seated",
            summary["seated"],
            "empty",
            summary["empty_positions"],
        )
        print("  cluster sizes", summary["cluster_sizes"])
    print("sha256", hashlib.sha256(text.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
