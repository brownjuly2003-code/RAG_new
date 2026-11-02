"""V6 replay of package prompts; no retrieval and no product edits."""

import argparse
import asyncio
import math
import re
import signal
import time
from pathlib import Path

from shown_text import shown_text
from v6_common import (
    DIGEST,
    FORECAST,
    HERE,
    KEYS,
    MODEL,
    STANDS,
    digest,
    final,
    load,
    outside,
    public,
    read,
    registration,
    require,
    sha,
    stand_receipt,
    tool_hashes,
    unicode_gate,
    unique,
    v5,
    write,
)

BATCHES, PER_BATCH = 10, 10
CEILING = 3600


class Builder(v5.Builder):
    def __init__(self, owner):
        import agent.prompts as prompts
        from agent.context_window import prompt_input_limit
        from api.routers.conversation import _fit_stream_prompt
        from llm.providers.base import estimate_window_tokens, flatten_messages

        self.owner, self.prompts = owner, prompts
        self.fit, self.flatten, self.estimate = (
            _fit_stream_prompt,
            flatten_messages,
            estimate_window_tokens,
        )
        self.v4 = prompts.PROMPT_REGISTRY["qa"]["text"]
        self.v5 = (HERE / "qa_prompt_v6.txt").read_bytes().decode("utf-8")
        require(
            prompts.PROMPT_REGISTRY["qa"]["prompt_id"] == "QA_PROMPT_V4",
            "package prompt id differs",
        )
        require(prompt_input_limit(owner, "generate") == 2176, "package input limit differs")

    def build(self, text, question, documents):
        prompt, flat, fitted = super().build(text, question, documents)
        expected = text.format(
            context_block=self.prompts._format_context_block(fitted), question=question
        )
        require(prompt == expected, "prompt override precedes registered text")
        return prompt, flat, fitted


def cases(runs, key):
    """Every batch and case is checked before the first model call of the key."""
    from scripts import chat_answer_judge as judge

    require(not list(Path(runs).rglob("._*")), "AppleDouble in package runs")
    found = []
    for number in range(1, BATCHES + 1):
        folder = Path(runs) / f"final-answers-{key}-b{number:02d}"
        launch = read(folder / "launch.json")
        require(launch.get("status") == "complete", "incomplete package batch")
        require(str(launch.get("code_sha", "")).startswith(STANDS[key]), "package stand differs")
        require(
            launch.get("model") == MODEL and launch.get("model_digest") == DIGEST,
            "package model differs",
        )
        answers = judge.run_answers(folder)
        require(len(answers) == PER_BATCH, "package batch count differs")
        require([a["case_id"] for a in answers] == launch.get("cases"), "package order differs")
        originals = {read(p)["case_id"]: p for p in sorted((folder / "cases").glob("*.json"))}
        timings = v5.streams(folder)
        for answer in answers:
            saved = (folder / "prompts" / answer["prompt_file"]).read_bytes().decode("utf-8")
            require(
                "\r" not in saved and answer["prompt_id"] == "QA_PROMPT_V4",
                "package prompt bytes/frame differ",
            )
            require(digest(saved) == answer["prompt_sha256"], "package prompt translation differs")
            timing = timings[answer["prompt_file"]]
            require(
                all(
                    isinstance(timing.get(n), (int, float))
                    and math.isfinite(timing[n])
                    and timing[n] >= 0
                    for n in ("wall_sec", "first_chunk_sec")
                )
                and timing["first_chunk_sec"] <= timing["wall_sec"] <= CEILING,
                "package stream timing missing/invalid",
            )
            require(
                type(timing.get("chunks")) is int and timing["chunks"] >= 0,
                "package chunk count missing/invalid",
            )
            found.append(
                {
                    **answer,
                    "saved": saved,
                    "batch": number,
                    "file": originals[answer["case_id"]].name,
                }
            )
    unique(found)
    require(len({a["question"] for a in found}) == len(found), "duplicate package questions")
    return found


def parity(builder, items):
    checked = []
    for item in items:
        question, documents = v5.read_saved(item["saved"])
        require(question == item["question"], "case question differs from saved prompt")
        package, flat, _ = builder.build(builder.v4, question, documents)
        prompt, v6_flat, fitted = builder.build(builder.v5, question, documents)
        require(flat == item["saved"], "package prompt cannot be rebuilt byte for byte")
        checked.append(
            {
                "case_id": item["case_id"],
                "batch": item["batch"],
                "parity": True,
                "package_prompt_sha256": digest(flat),
                "v6_prompt_sha256": digest(v6_flat),
                "same_context": v5.same_context(documents, fitted),
                "documents_package": len(documents),
                "documents_v6": len(fitted),
                "prompt": prompt,
                "flat": v6_flat,
                "package": package,
            }
        )
    return checked


def settings_gate(settings, recorded, llm):
    names = set(final.SETTINGS) | set(v5.SETTINGS)
    require(all(n in recorded for n in names), "recorded effective setting missing")
    for name in names:
        require(
            str(getattr(settings, name, None)) == str(recorded[name]),
            "effective setting differs: " + name,
        )
    require(all(recorded[k] == v for k, v in final.SETTINGS.items()), "not package settings")
    inner = getattr(llm, "_provider", llm)
    require(
        type(inner).__name__ == "OllamaProvider"
        and getattr(llm, "_fallback_provider", None) is None
        and llm.model_name == MODEL,
        "runtime model/fallback differs",
    )


def policy_chunk(raw, question, previous, result):
    """A unit boundary, tag end or citation close can change an unfinished display."""
    import regex

    if regex.search(r"[\r\n。！？>\]]|[.!?]\s", raw[max(0, previous - 1) :]):
        return shown_text(raw, question, finished=False, details=True)
    return result


def stream_reading(raw, question, timeline, tagged=True):
    """Recompute the private timeline and display; never trust saved release times."""
    chunks, end = timeline["chunks"], timeline["end_sec"]
    require(
        isinstance(end, (float, int)) and math.isfinite(end) and 0 <= end <= CEILING,
        "invalid timeline end",
    )
    require(
        timeline["end_state"] in ("policy", "answer_tag", "eos", "token_cap", "ceiling"),
        "invalid stream end state",
    )
    last_chars, last_sec, first_shown, opened = 0, 0, None, None
    completed, result = [], None
    for index, chunk in enumerate(chunks):
        chars, sec = chunk["chars"], chunk["sec"]
        require(
            type(chars) is int
            and last_chars <= chars <= len(raw)
            and isinstance(sec, (float, int))
            and math.isfinite(sec)
            and last_sec <= sec <= end,
            "invalid chunk timeline",
        )
        if tagged:
            result = policy_chunk(raw[:chars], question, last_chars, result)
            if result is not None:
                if result["answer_open"] is not None and opened is None:
                    opened = sec
                completed.extend([sec] * (len(result["unit_ends"]) - len(completed)))
                if result["text"] and first_shown is None:
                    first_shown = sec
                require(not result["stop"] or index == len(chunks) - 1, "chunks after display stop")
        else:
            ends = list(re.finditer(r"[。！？]|[\r\n]|[.!?](?=\s)", raw[:chars]))
            completed.extend([sec] * (len(ends) - len(completed)))
            if chars and first_shown is None:
                first_shown = sec
        last_chars, last_sec = chars, sec
    require(last_chars == len(raw), "timeline does not cover raw")
    if tagged:
        stopped = result is not None and result["stop"]
        require(
            (timeline["end_state"] in ("policy", "answer_tag")) == stopped,
            "stream end state differs from policy",
        )
        if stopped:
            require(
                timeline["end_state"] == ("policy" if result["flags"] else "answer_tag"),
                "stream end state differs from stop kind",
            )
        result = shown_text(raw, question, details=True)
        completed.extend([end] * (len(result["unit_ends"]) - len(completed)))
        if result["text"] and first_shown is None:
            first_shown = end
    else:
        result = {"text": raw, "flags": [], "cut_at": None, "prefix_whole_disagreement": False}
        ends = list(re.finditer(r"[。！？]|[\r\n]|[.!?](?=\s)", raw))
        if raw and (not ends or ends[-1].end() < len(raw)):
            completed.append(end)
    return {
        **result,
        "first_shown_sec": first_shown,
        "answer_open_sec": opened,
        "unit_seconds": completed,
        "full_buffer_sec": last_sec if tagged and stopped else end,
    }


async def collect(llm, prompt, params, tagged=False, budget=CEILING, question=""):
    started = time.monotonic()
    raw, chunks, end_state = "", [], "eos"
    result = None
    stream = llm.generate_stream([{"role": "user", "content": prompt}], **params)
    try:
        while True:
            remaining = budget - (time.monotonic() - started)
            try:
                if remaining <= 0:
                    raise TimeoutError
                token = await asyncio.wait_for(anext(stream), remaining)
            except StopAsyncIteration:
                end_state = "token_cap" if len(chunks) >= params.get("max_tokens", 1024) else "eos"
                break
            except TimeoutError:
                end_state = "ceiling"
                break
            previous = len(raw)
            raw += token
            chunks.append({"sec": min(budget, time.monotonic() - started), "chars": len(raw)})
            if tagged:
                result = policy_chunk(raw, question, previous, result)
                if result is not None and result["stop"]:
                    end_state = "policy" if result["flags"] else "answer_tag"
                    break
    finally:
        await stream.aclose()
    timeline = {
        "chunks": chunks,
        "end_sec": min(budget, time.monotonic() - started),
        "end_state": end_state,
    }
    result = stream_reading(raw, question, timeline, tagged)
    timeline.update({k: result[k] for k in ("answer_open_sec", "unit_seconds", "first_shown_sec")})
    return {
        "raw": raw,
        "first": chunks[0]["sec"] if chunks else None,
        "chunks": len(chunks),
        "seconds": timeline["end_sec"],
        "timeline": timeline,
        "display": result,
    }


async def answer(llm, prompt, package, question, params, budget=CEILING):
    first = await collect(llm, prompt, params, tagged=True, budget=budget, question=question)
    result = first["display"]
    shown = result["text"]
    fallback = bool(set(result["flags"]) & {"parse", "language"})
    second = None
    first_shown = result["first_shown_sec"]
    if fallback:
        second = await collect(llm, package, params, budget=budget)
        shown = second["raw"]
        when = second["display"]["first_shown_sec"]
        first_shown = first["seconds"] + when if when is not None else None
    return {
        "answer": shown,
        "flags": result["flags"],
        "fallback": fallback,
        "raw": first["raw"],
        "fallback_raw": second["raw"] if second else None,
        "timeline": {"v6": first["timeline"], "fallback": second["timeline"] if second else None},
        "cut_at": result["cut_at"],
        "prefix_whole_disagreement": result["prefix_whole_disagreement"],
        "v6_stream_sec": first["seconds"],
        "fallback_stream_sec": second["seconds"] if second else None,
        "first_shown_sec": first_shown,
        "full_buffer_sec": first_shown if fallback else result["full_buffer_sec"],
        "first_raw_sec": first["first"],
        "total_sec": first["seconds"] + (second["seconds"] if second else 0),
        "chunks": first["chunks"],
        "fallback_chunks": second["chunks"] if second else None,
    }


def form_stop(batch):
    require(len(batch) == PER_BATCH, "form gate needs the first ten answers")
    return sum("parse" in row["flags"] for row in batch) > PER_BATCH / 2


def run(key, runs, out, spec_path, check_only=False):
    versions = unicode_gate()
    from config.settings import get_settings
    from llm.providers.runtime import build_provider_runtime
    from llm.role_params import generation_kwargs_for_role

    spec_hash = registration(spec_path)
    runs, out = Path(runs).resolve(), outside(out)
    require(
        not out.is_relative_to(runs) and not runs.is_relative_to(out),
        "output overlaps package runs",
    )
    require(not out.exists(), "new key output required; no automatic retry")
    driver = load("reports/stage4-final/tools/run.py", "v6_package_driver")
    stand = load("reports/stage4-final/tools/stand.py", "v6_package_stand")
    code = driver.code_check()
    require(code.startswith(STANDS[key]), "wrong replay stand")
    settings = get_settings()
    llm = build_provider_runtime(settings).strong
    items = cases(runs, key)
    for number in range(1, BATCHES + 1):
        source = runs / f"final-answers-{key}-b{number:02d}"
        recorded = read(source / "effective_settings.json")["all"]
        settings_gate(settings, recorded, llm)
        require(read(source / "launch.json")["code_sha"] == code, "full package SHA differs")
    builder = Builder(llm)
    checked = parity(builder, items)
    before = stand.check()
    for number in range(1, BATCHES + 1):
        require(
            stand_receipt(read(runs / f"final-answers-{key}-b{number:02d}" / "stand.json"))
            == stand_receipt(before),
            "package environment/server changed since saved batch",
        )
    params = generation_kwargs_for_role("generate")
    require(
        params.get("max_tokens") == 1024 and params.get("temperature") == 0.2,
        "generate kwargs differ",
    )
    if check_only:
        idle = driver.idle_check()
        require(
            "a model is resident" not in idle["reasons"], "a model is resident; path cannot start"
        )
        print(
            "CHECK",
            key,
            len(checked),
            "same_context",
            sum(r["same_context"] for r in checked),
            "regex",
            versions["regex_version"],
            "unicodedata",
            versions["unidata_version"],
            "idle",
            idle,
        )
        return
    out.mkdir(parents=True)
    deadline = time.monotonic() + 3 * FORECAST[key]
    summary = {
        "key": key,
        "code_sha": code,
        "spec_sha256": spec_hash,
        "tools": tool_hashes(),
        "prompt_template_sha256": sha(HERE / "qa_prompt_v6.txt"),
        **versions,
        "environment_before": before,
        "idle": [],
        "started": v5.now(),
        "whole": False,
        "rows": [],
        "parity": [
            {k: v for k, v in r.items() if k not in ("prompt", "flat", "package")} for r in checked
        ],
    }
    write(out / "summary.json", summary)
    sup, sampler = final.frozen("supervisor"), final.frozen("sampler")
    loaded = False
    try:
        for number in range(1, BATCHES + 1):
            require(not (out.parent / "STOP").exists(), "operator/harm stop")
            source = runs / f"final-answers-{key}-b{number:02d}"
            idle = driver.wait_idle(out / f"idle-{number:02d}.json", deadline, speed=False)
            summary["idle"].append({"batch": number, **idle})
            write(out / "summary.json", summary)
            folder = out / f"v6-{key}-b{number:02d}"
            for name in ("cases", "prompts", "raw"):
                (folder / name).mkdir(parents=True, exist_ok=True)
            old = read(source / "launch.json")
            launch = {
                k: old.get(k)
                for k in ("tenant", "chroma_dir", "cases_file", "model", "model_digest", "code_sha")
            }
            launch.update(
                label=folder.name,
                status="running",
                prompt_id="QA_PROMPT_V5",
                params=params,
                tools_sha256=tool_hashes(),
                spec_sha256=spec_hash,
                started=v5.now(),
            )
            write(folder / "launch.json", launch)
            loaded = True
            launch.update(driver.preload(sup, sampler, before["settings"]))
            write(folder / "launch.json", launch)
            batch_rows = []
            streams = v5.streams(source)
            for item, fitted in zip(items, checked, strict=True):
                if item["batch"] != number:
                    continue
                require(not (out.parent / "STOP").exists(), "operator/harm stop")
                left = deadline - time.monotonic()
                require(left > 0, "3x key forecast")

                # The whole pair is bounded by the remaining key clock; each call by 3,600 s.
                async def pair_call():
                    return await asyncio.wait_for(
                        answer(llm, fitted["prompt"], fitted["package"], item["question"], params),
                        left,
                    )

                got = asyncio.run(pair_call())
                name = f"{len(batch_rows) + 1:03d}-stream.txt"
                (folder / "prompts" / name).write_bytes(fitted["flat"].encode("utf-8"))
                (folder / "raw" / (name + ".raw")).write_bytes(got.pop("raw").encode("utf-8"))
                write(folder / "raw" / (name + ".timeline.json"), got.pop("timeline"))
                fallback_raw = got.pop("fallback_raw")
                if fallback_raw is not None:
                    (folder / "raw" / (name + ".fallback")).write_bytes(
                        fallback_raw.encode("utf-8")
                    )
                case = {
                    **got,
                    "case_id": item["case_id"],
                    "question": item["question"],
                    "prompt_file": name,
                    "events": [{"type": "result", "answer": got["answer"], "route": None}],
                }
                write(folder / "cases" / item["file"], case)
                old_stream = streams[item["prompt_file"]]
                row = {k: v for k, v in fitted.items() if k not in ("prompt", "flat", "package")}
                row.update({k: got[k] for k in got if k != "answer"})
                row.update(
                    idle_clean=not idle["busy"],
                    answer_chars=len(got["answer"]),
                    package_answer_chars=len(item["answer"]),
                    package_stream_sec=old_stream["wall_sec"],
                    package_first_sec=old_stream["first_chunk_sec"],
                    package_chunks=old_stream["chunks"],
                    package_quoted=v5.quoted(item["answer"], item["documents"]),
                    v6_quoted=v5.quoted(got["answer"], v5.read_saved(fitted["flat"])[1]),
                    shown_sha256=digest(got["answer"].strip()),
                    package_answer_sha256=digest(item["answer"].strip()),
                )
                batch_rows.append(row)
                summary["rows"].append(row)
                write(out / "summary.json", summary)
                print(
                    "ANSWER",
                    key,
                    item["case_id"],
                    got["flags"],
                    round(got["total_sec"], 3),
                    flush=True,
                )
            driver.unload(sup, sampler, MODEL, out / f"unload-{number:02d}.json")
            loaded = False
            launch.update(
                status="complete", cases=[r["case_id"] for r in batch_rows], finished=v5.now()
            )
            write(folder / "launch.json", launch)
            if number == 1 and form_stop(batch_rows):
                write(out.parent / "STOP", {"reason": "parse-majority", "key": key})
                require(False, "parse-majority: amend spec before the rest")
        require(time.monotonic() < deadline, "3x key forecast")
        summary["environment_after"] = stand.check()
        require(
            stand_receipt(summary["environment_after"]) == stand_receipt(before),
            "environment drift",
        )
        require(
            driver.code_check() == code and tool_hashes() == summary["tools"], "code/tools drift"
        )
        summary.update(whole=True, finished=v5.now())
        write(out / "summary.json", summary)
        names = {name for item in items for name, _ in item["documents"]}
        public(out / f"v6-{key}.json", summary, names, [i["question"] for i in items])
        write(out / "COMPLETE", {"summary_sha256": sha(out / f"v6-{key}.json")})
    except BaseException as exc:
        write(out / "FAILED.json", {"status": "NOT_EVIDENCE", "kind": type(exc).__name__})
        raise
    finally:
        if loaded:
            driver.unload(sup, sampler, MODEL, out / "unload-failure.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "run"))
    parser.add_argument("key", choices=KEYS)
    for name in ("runs", "out", "spec"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()

    def stopped(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stopped)
    run(args.key, args.runs, args.out, args.spec, args.command == "check")


if __name__ == "__main__":
    main()
