"""Read actual saved prompts by the registered external range-coverage rule; no model calls."""

import gzip
import itertools
import json
import math
from pathlib import Path

from protocol import frozen, questions, read, require, rows, runs_gate, sha, table


class SentGold:
    def __init__(self, base, data):
        from run import corpus

        from evaluation import external_bases, external_parts
        from scripts import external_base
        from scripts.external_pilot import Places

        self.base = base
        corpus(base, data)  # Registered chunk-archive hash, tenant and generation receipts.
        self.chunks = json.loads(gzip.decompress((data / base / "chunks.json.gz").read_bytes()))[
            "chunks"
        ]
        converted = external_bases.registration()
        self.cases = {
            r["case_id"]: r for r in external_parts.load_cases(data / base, base, converted)
        }
        self.sources = None if base == "wixqa" else external_base._corpus(data / base)[1]
        self.places = Places(self.chunks, self.sources, converted["chunking"]["chunk_overlap"], 1)
        self.arms = frozen("arms")

    def saved_point(self, case, documents):
        """Minimal historical archives contain prompts, not retrieval traces.

        Locate only the visible sent pieces, never credit a merely matching gold string.
        Repeats are admitted only when every placement gives the same gold reading.
        """
        from retrieval_summary import Excerpted

        from agent.context_window import EXCERPT_GAP
        from evaluation import external_gold as gold
        from scripts.external_pilot import gold_documents, read_gold
        from vectordb import table_header

        require(0 < len(documents) <= 5, "historical sent document count differs")
        members, options = [], []
        for source, text in documents:
            seeds = [i for i, c in enumerate(self.chunks) if c["metadata"]["source"] == source]
            require(bool(seeds), "historical sent source is absent")
            for piece in text.split(EXCERPT_GAP):
                bodies = {gold.strip_header(piece, self.chunks[i]["metadata"]) for i in seeds}
                stripped = {body for body in bodies if body != piece}
                bodies = stripped or bodies
                if self.sources is None:
                    if any(gold.visible(body)[0] for body in bodies):
                        members.append(seeds[0])
                    continue
                require(source in self.sources, "historical sent source has no coordinates")
                if not any(gold.visible(body)[0] for body in bodies):
                    continue

                def placements(body):
                    # The chunker repeats a continued table's header; locate_chunks strips it.
                    found = self.sources[source].occurrences(body)
                    if found:
                        return found
                    variants = {
                        body[table_header.prefix(body, self.chunks[i]["metadata"]) :] for i in seeds
                    }
                    return sorted(
                        {p for b in variants for p in self.sources[source].occurrences(b)}
                    )

                places = {p for body in bodies for p in placements(body)}
                alternatives = {((source, p),) for p in places}
                if not places:
                    # Parent expansion can join nonadjacent bodies with a blank line.
                    # Credit each visible paragraph, never the intervening source range.
                    for body in bodies:
                        spans = [placements(p) for p in body.split("\n\n") if gold.visible(p)[0]]
                        if spans and all(spans):
                            require(
                                math.prod(map(len, spans)) <= 256,
                                "historical placements exceed 256",
                            )
                            alternatives.update(
                                tuple((source, p) for p in combo)
                                for combo in itertools.product(*spans)
                            )
                require(bool(alternatives), "historical sent excerpt unplaceable or ambiguous")
                options.append(sorted(alternatives))
                require(math.prod(map(len, options)) <= 256, "historical placements exceed 256")
        if not gold_documents(self.base, case):
            return {"gold": False, "hit": None, "fraction": None}
        require(not case.get("unresolved_evidence"), "gold evidence unresolved")
        names = (
            ("gold_article", "gold_articles")
            if self.base == "wixqa"
            else ("all_evidence_coverage", "evidence_recall")
        )
        readings = set()
        for combo in itertools.product(*options):
            extra = [piece for alternative in combo for piece in alternative]
            point = read_gold(self.base, case, members, Excerpted(self.places, extra))
            readings.add((int(point[names[0]]), point[names[1]]))
        require(
            len(readings) == 1, "historical sent excerpt unplaceable or ambiguous in its reading"
        )
        hit, fraction = readings.pop()
        return {"gold": True, "hit": hit, "fraction": fraction}

    def saved_run(self, folder, published):
        from scripts import chat_answer_judge as judge

        parsed = table(judge.run_answers(folder), list(published))
        result = []
        for ident, held in published.items():
            answer = parsed[ident]
            require(
                len(held["prompts"]) == 1
                and sha(folder / "prompts" / held["prompts"][0]["file"])
                == held["prompts"][0]["sha256"]
                == answer["prompt_sha256"],
                "saved prompt differs from published answer",
            )
            require(answer["question"] == self.cases[ident]["query"], "saved question differs")
            result.append(
                {
                    "case_id": ident,
                    "prompt_sha256": answer["prompt_sha256"],
                    **self.saved_point(self.cases[ident], answer["documents"]),
                }
            )
        return result

    def one(self, case, documents, expanded, settings):
        from evaluation import external_gold as gold
        from scripts.external_pilot import gold_documents

        require(0 < len(documents) <= len(expanded), "sent document count differs")
        members, sent = [], []
        for (source, text), whole in zip(documents, expanded, strict=False):
            require(source == whole.metadata["source"], "sent source order differs")
            seed = whole.metadata["chunk_index"]
            joined = gold.expansion_members(
                whole.page_content,
                seed,
                self.chunks,
                settings["parent_expansion_window"],
                settings["chunk_overlap"],
            )
            members.append(joined)
            sent.append({"text": text, "chunk_index": seed, "cut": text != whole.page_content})
        has_gold = bool(gold_documents(self.base, case))
        if not has_gold:
            return {"gold": False, "hit": None, "fraction": None}
        require(not case.get("unresolved_evidence"), "gold evidence unresolved")
        point, missed = self.arms.sent_point(
            self.base,
            case,
            sent,
            members,
            {"places": self.places, "sources": self.sources, "chunks": self.chunks},
        )
        require(missed == 0, "sent excerpt could not be placed")
        names = (
            ("gold_article", "gold_articles")
            if self.base == "wixqa"
            else ("all_evidence_coverage", "evidence_recall")
        )
        require(point[names[0]] in (0, 1) and 0 <= point[names[1]] <= 1, "invalid gold reading")
        return {"gold": True, "hit": int(point[names[0]]), "fraction": point[names[1]]}

    def run(self, folder, published):
        from scripts import chat_answer_judge as judge

        settings = read(folder / "effective_settings.json")["all"]
        replay = self.arms.Replay(self.chunks, settings, "ext_" + self.base, 32)
        stages = rows(folder / "stages.jsonl")
        raw = table([read(p) for p in sorted((folder / "cases").glob("*.json"))], list(published))
        parsed = table(judge.run_answers(folder), list(published))
        result = []
        for ident, held in published.items():
            original, answer = raw[ident], parsed[ident]
            prompt = held["prompts"][0]
            require(
                len(held["prompts"]) == 1
                and sha(folder / "prompts" / prompt["file"])
                == prompt["sha256"]
                == answer["prompt_sha256"],
                "saved prompt differs from published answer",
            )
            require(original["question"] == self.cases[ident]["query"], "saved question differs")
            start, end = original["t0_monotonic"], original["t0_monotonic"] + original["total_sec"]

            def event(name):
                found = [
                    r
                    for r in stages
                    if r.get("event") == "end"
                    and r.get("stage") == name
                    and start <= r["monotonic"] <= end
                ]
                require(len(found) == 1, "one observed retrieval stage required")
                return found[0]

            ranked = event("hybrid._rerank_scored_with_status")
            require(
                ranked["reranker_ok"] is True and len(ranked["chunk_index"]) == 5,
                "historical rerank broke",
            )
            require(
                len(set(ranked["chunk_index"])) == 5
                and all(
                    type(i) is int and 0 <= i < len(replay.docs) for i in ranked["chunk_index"]
                ),
                "ranked chunk positions differ",
            )
            with self.arms.overlap_of(settings["chunk_overlap"]):
                expanded = replay.hybrid._expand_parents(
                    [replay.docs[i] for i in ranked["chunk_index"]]
                )
            observed = event("hybrid._expand_parents")
            require(
                [d.metadata["chunk_index"] for d in expanded] == observed["chunk_index"]
                and sum(len(d.page_content) for d in expanded) == observed["chars"],
                "expansion replay differs from observed answer",
            )
            result.append(
                {
                    "case_id": ident,
                    "prompt_sha256": prompt["sha256"],
                    **self.one(self.cases[ident], answer["documents"], expanded, settings),
                }
            )
        return result


def measure(base, data, runs, cases, historical=False):
    runs_gate(runs)
    _, ids = questions(base, data)
    table(cases, ids)
    reader = SentGold(base, data)
    result = []
    labels = dict.fromkeys(r["run"] for r in cases)
    for label in labels:
        require(Path(label).name == label, "invalid run label")
        result.extend(
            (reader.saved_run if historical else reader.run)(
                runs / label, {r["case_id"]: r for r in cases if r["run"] == label}
            )
        )
    found = table(result, ids)
    return [found[i] for i in ids]


def stage2_gate(data, run, exported, combined, answer_cases):
    """Stage 2 read p2-multihoprag, whose prompts were paired byte-for-byte with p4."""
    from protocol import committed
    from run import corpus

    from scripts.chat_answer_judge import read_prompt
    from scripts.external_pilot import gold_documents

    runs_gate(run)
    reader = SentGold("multihoprag", data)
    from retrieval_summary import coverage

    _, ids = questions("multihoprag", data)
    old = table(rows(exported.with_suffix(".cases.jsonl")), ids)
    answers = table(answer_cases, ids)
    committed(exported)
    committed(exported.with_suffix(".cases.jsonl"))
    committed(combined)
    launch = read(run / "launch.json")
    require(
        launch["status"] == "complete"
        and launch["code_sha"].startswith("5e308fe")
        and launch["tenant"] == "ext_multihoprag"
        and launch["cases"] == ids,
        "stage2 retrieval run differs",
    )
    effective = read(run / "effective_settings.json")
    settings = effective["all"]
    p = read(exported)["provenance"]
    cases_file, _ = questions("multihoprag", data)
    require(
        p["code_sha"] == launch["code_sha"]
        and p["settings"] == effective["settings"]
        and p["parent_expansion_window"] == settings["parent_expansion_window"]
        and p["archive_sha256"] == sha(data / "multihoprag/chunks.json.gz")
        and p["source_sha256"] == corpus("multihoprag", data)
        and p["cases_file_sha256"] == sha(cases_file),
        "stage2 retrieval provenance differs",
    )
    reader.places.window = settings["parent_expansion_window"]
    records = table([read(p) for p in sorted((run / "retrieval").glob("*.json"))], ids)
    result = []
    for ident in ids:
        row, raw = old[ident], records[ident]
        question, documents = read_prompt(raw["prompt"]["text"])
        require(
            not row["path_breaks"]
            and row["answer_prompt_same"] is True
            and raw["prompt"]["sha256"]
            == row["prompt"]["sha256"]
            == answers[ident]["prompts"][0]["sha256"]
            and reader.arms.digest(raw["prompt"]["text"]) == row["prompt"]["sha256"],
            "stage2 retrieval/answer prompt parity failed",
        )
        require(
            question == raw["question"] == reader.cases[ident]["query"]
            and documents == [(d["source"], d["text"].rstrip("\n")) for d in raw["sent"]],
            "stage2 sent text or question differs from the prompt",
        )
        require(
            0 < len(raw["sent"]) <= len(raw["expanded"])
            and all(
                doc["source"] == whole["source"]
                and doc["chunk_index"] == whole["chunk_index"]
                and doc["cut"] is (doc["text"] != whole["text"])
                for doc, whole in zip(raw["sent"], raw["expanded"], strict=False)
            ),
            "stage2 sent seeds or cut flags differ",
        )
        require(
            bool(row["gold"]) == bool(gold_documents("multihoprag", reader.cases[ident]))
            and (not row["gold"] or not reader.cases[ident].get("unresolved_evidence")),
            "stage2 gold membership differs",
        )
        value = {"gold": bool(row["gold"]), "hit": None, "fraction": None}
        if row["gold"]:
            got = coverage(
                "multihoprag",
                reader.cases[ident],
                raw,
                reader.places,
                reader.sources,
                reader.chunks,
            )
            require(
                got["unresolved"] is None
                and got["excerpt_pieces_missed"] == 0
                and got["points"]["sent"] == row["points"]["sent"],
                "stage2 sent M3 parity failed",
            )
            value.update(
                hit=int(got["points"]["sent"]["all_evidence_coverage"]),
                fraction=got["points"]["sent"]["evidence_recall"],
            )
        result.append({"case_id": ident, "prompt_sha256": row["prompt"]["sha256"], **value})
    published = read(combined)["corpora"]["multihoprag"]
    require(published["m2"]["status"] == "NOT_EVIDENCE", "stage2 MultiHop M2 status differs")
    expected = published["m3"]["points"]["sent"]["all_evidence_coverage"]
    require(
        sum(r["gold"] for r in result) == expected["n"]
        and sum(r["hit"] or 0 for r in result) == expected["hits"],
        "stage2 combined M3 differs",
    )
    return result
