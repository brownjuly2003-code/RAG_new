"""The answer prompt V5 on V4's saved contexts: a key's answers again, the prompt alone changed.

docs/specs/answer-prompt-v5.md, «The replay». On the Mac, in the stand of 4f48fed, whose folder
v5/ holds these tools, by the stage's interpreter with the gate's site on its path:

  $PY v5/replay.py check KEY V4_RUNS
  $PY v5/replay.py run KEY V4_RUNS OUT
  $PY v5/replay.py summary KEY V4_RUNS OUT RECORDS

KEY is wixqa, conditionalqa or aircargo; V4_RUNS holds V4's runs v4-KEY-b01 ... b10.

Every answered case of those runs, in order: the question and the documents of its saved
stream prompt, cut at the labels the chat writes (agent.prompts._format_context_block). The
chat's own fitting (api.routers.conversation._fit_stream_prompt, no history) rebuilds V4's
prompt from them, and the rebuilt prompt, flattened as the provider sends it, must be the saved
file byte for byte. Then the same fitting with qa_prompt_v5.txt as the registry's "qa" text: a
V5 prompt holds V4's documents, or fewer, or its last one cut shorter, never more.

check: every case's parity and its V5 prompt's size, no model call, a JSON line a case on
stdout and the count on stderr; exit 3 if a case fails.
run: check, then each V5 prompt through the chat's own stream call - the provider runtime's
strong model, generate_stream, the "generate" role's kwargs, the chat's deadline - into
OUT/v5-KEY-bNN in V4's run layout: cases/NN-<case>.json, prompts/NNN-stream.txt, stages.jsonl,
launch.json, so the judge's adapter reads them as it read V4's. A batch whole is kept and a case
answered is kept: a stopped key resumes, a prompt a killed process left without its case
removed first and counted. A saved prompt holding a carriage return is refused. Exit 4: an answer took longer than ANSWER_STOP seconds
(saved; the key stops); 5: the stop file OUT/v5-KEY.stop; 6: the settings, the model or the
window are not V4's; 7: the model call failed (not saved; resuming asks it again).
summary: the key's V5 answers beside V4's, ids, flags and numbers only, into RECORDS: what
v5_record.py reads with the judge's records.
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = next(p for p in HERE.parents if (p / "agent" / "prompts.py").exists())
sys.path.insert(0, str(WS))

KEYS = ("wixqa", "conditionalqa", "aircargo")
BATCHES = 10
V5 = HERE / "qa_prompt_v5.txt"
V4_ID, V5_ID = "QA_PROMPT_V4", "QA_PROMPT_V5"
# The citation sentences that tell the prompts apart (scripts/chat_answer_judge.PROMPT_IDS).
V4_MARK = "[1] for the first document in the context list,"
V5_MARK = "[1] for the context's first document,"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
# The input V4's prompts were fitted to: num_ctx 4096 less the "generate" role's 1,024.
LIMIT = 2636
ANSWER_STOP = 1200.0
OLLAMA = "http://127.0.0.1:11434"
# The chat's settings as V4's runs recorded them (effective_settings.json, "all"); the base URL
# is masked there.
SETTINGS = (
    "llm_provider_profile",
    "ollama_model_name",
    "model_routing_enabled",
    "ollama_context_window",
    "llm_role_params_json",
    "streaming_timeout_sec",
    "ollama_request_timeout_sec",
    "provider_registry_path",
)
# The chat's frame of an answer prompt (scripts/chat_answer_judge.py) and its join of documents.
CONTEXT_START = "CONTEXT:\n"
CONTEXT_END = "\n--------------------\n\nQUESTION:\n"
QUESTION_END = "\n\nWhen you rely on"
LABEL = re.compile(r"(?m)^\[(\d+) \| source=([^\]\n]*)\]\n")
SEPARATOR = "\n\n"
TOOLS = ("replay.py", "qa_prompt_v5.txt", "v5_chain.sh")
STAGE = "ollama.generate_stream"
# A passage this long, white space aside, copied from the context marks an answer that quotes it.
QUOTE, QUOTE_STEP = 40, 10


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rounded(value):
    return None if value is None else round(value, 3)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_saved(text):
    """The question and the documents (source, text) of a saved stream prompt, as the chat's
    _format_context_block joined them."""
    context = text.split(CONTEXT_START, 1)[1].split(CONTEXT_END, 1)[0]
    question = text.split(CONTEXT_END, 1)[1].split(QUESTION_END, 1)[0]
    if context == "[]":
        return question, []
    labels = list(LABEL.finditer(context))
    if not labels or labels[0].start() != 0:
        raise ValueError("the context does not start with a document label")
    documents = []
    for index, label in enumerate(labels, start=1):
        if int(label[1]) != index:
            raise ValueError(f"document label {label[1]} stands where {index} is due")
        if index < len(labels):
            end = labels[index].start() - len(SEPARATOR)
            if context[end : labels[index].start()] != SEPARATOR:
                raise ValueError("the documents are not joined as the chat joins them")
        else:
            end = len(context)
        documents.append((label[2], context[label.end() : end]))
    return question, documents


def as_docs(documents):
    return [{"page_content": text, "metadata": {"source": source}} for source, text in documents]


def v4_cases(runs, key):
    """V4's answered cases of a key, batch by batch: (batch name, case file, case, prompt)."""
    out = []
    for number in range(1, BATCHES + 1):
        run = Path(runs) / f"v4-{key}-b{number:02d}"
        prompts = {}
        for path in sorted((run / "prompts").glob("*-stream.txt")):
            # Bytes, not read_text: its newline translation would hand V5 other white space.
            text = path.read_bytes().decode("utf-8")
            if V4_MARK not in text:
                continue
            if "\r" in text:
                raise SystemExit(
                    f"{run.name}/{path.name}: a carriage return the judge reads as \\n"
                )
            question, _ = read_saved(text)
            prompts.setdefault(question, []).append((path.name, text))
        for path in sorted((run / "cases").glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            if str(case["case_id"]).startswith("warmup-"):
                continue
            found = prompts.get(case["question"], [])
            if len(found) != 1:
                raise SystemExit(
                    f"{run.name}/{path.name}: {len(found)} V4 prompts hold its question"
                )
            out.append((run.name, path.name, case, found[0]))
    return out


class Builder:
    """The chat's prompt of a question and documents, V4's or V5's, flattened as sent."""

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
        self.v5 = V5.read_text(encoding="utf-8")
        if V4_MARK not in self.v4 or prompts.PROMPT_REGISTRY["qa"]["prompt_id"] != V4_ID:
            raise SystemExit("the stand's qa prompt is not V4")
        if V5_MARK not in self.v5 or V4_MARK in self.v5:
            raise SystemExit("qa_prompt_v5.txt does not hold V5's citation sentence alone")
        if prompt_input_limit(owner, "generate") != LIMIT:
            raise SystemExit(f"the model's input window is not V4's {LIMIT} tokens")

    def build(self, text, question, documents):
        """(the prompt the chat passes, as the provider flattens it, the documents it holds)."""
        registry = self.prompts.PROMPT_REGISTRY["qa"]
        registry["text"] = text
        try:
            prompt, fitted = self.fit(self.owner, question, as_docs(documents), [])
        finally:
            registry["text"] = self.v4
        # An experiment's or a staged override of "qa" would stand before the registry's text.
        mark = V5_MARK if text == self.v5 else V4_MARK
        if mark not in prompt:
            raise SystemExit("the chat built its prompt from another text than the one given")
        return prompt, self.flatten([{"role": "user", "content": prompt}]), fitted


def same_context(documents, fitted):
    return [(d["metadata"]["source"], d["page_content"]) for d in fitted] == list(documents)


def check(builder, cases):
    """Each case's parity and its V5 prompt; refuses on a case whose V4 prompt is not rebuilt."""
    rows, failed = [], []
    for batch, name, case, (prompt_file, saved) in cases:
        question, documents = read_saved(saved)
        _, rebuilt, _ = builder.build(builder.v4, question, documents)
        _, v5, fitted = builder.build(builder.v5, question, documents)
        row = {
            "batch": batch,
            "case_id": case["case_id"],
            "v4_prompt_file": prompt_file,
            "v4_prompt_sha256": digest(saved),
            "parity": rebuilt == saved,
            "documents_v4": len(documents),
            "documents_v5": len(fitted),
            "same_context": same_context(documents, fitted),
            "v5_prompt_chars": len(v5),
            "v5_prompt_est_tokens": builder.estimate(v5),
        }
        rows.append(row)
        if not row["parity"]:
            failed.append(f"{batch}/{name}")
    return rows, failed


def ollama(path, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read() or b"{}")


def provider_and_settings(runs, key):
    """The chat's stream model, its settings held against V4's first run of the key."""
    from config.settings import get_settings
    from llm.providers.runtime import build_provider_runtime

    settings = get_settings()
    recorded = json.loads(
        (Path(runs) / f"v4-{key}-b01" / "effective_settings.json").read_text(encoding="utf-8")
    )["all"]
    differ = [n for n in SETTINGS if str(getattr(settings, n, None)) != str(recorded.get(n))]
    llm = build_provider_runtime(settings).strong
    # The runtime wraps its provider (llm.providers.base.ProviderBackedLLM); no fallback.
    inner = getattr(llm, "_provider", llm)
    if (
        type(inner).__name__ != "OllamaProvider"
        or getattr(llm, "_fallback_provider", None) is not None
        or llm.model_name != MODEL
    ):
        differ.append("the stream model")
    if differ:
        print("not V4's: " + ", ".join(differ), file=sys.stderr)
        raise SystemExit(6)
    return llm, settings


async def stream(llm, prompt, params, budget):
    """The chat's token loop: tokens joined; stopped past its wall-clock budget."""
    started = time.monotonic()
    deadline = started + budget
    text, first, chunks, truncated = "", None, 0, False
    async for token in llm.generate_stream([{"role": "user", "content": prompt}], **params):
        if first is None:
            first = time.monotonic() - started
        text += token
        chunks += 1
        if time.monotonic() > deadline:
            truncated = True
            break
    return text, first, chunks, truncated, time.monotonic() - started


def append(path, row):
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def ask(llm, builder, folder, params, budget, saved):
    """One V5 answer: its prompt saved as the stand saves one, the stream timed as the stand
    times it. Returns the answer's fields, or None when the model call failed (nothing kept)."""
    question, documents = read_saved(saved)
    prompt, flat, fitted = builder.build(builder.v5, question, documents)
    name = f"{len(list((folder / 'prompts').glob('*-stream.txt'))) + 1:03d}-stream.txt"
    (folder / "prompts" / name).write_bytes(flat.encode("utf-8"))
    info = {
        "prompt_file": name,
        "prompt_chars": len(flat),
        "prompt_est_tokens": builder.estimate(flat),
        "max_tokens": params["max_tokens"],
    }
    stages = folder / "stages.jsonl"
    append(stages, {"stage": STAGE, "event": "start", **info, "monotonic": time.monotonic()})
    begun = now()
    try:
        text, first, chunks, truncated, wall = asyncio.run(stream(llm, prompt, params, budget))
    except Exception as exc:  # noqa: BLE001 - recorded; the key stops and resumes here
        append(
            stages,
            {
                "stage": STAGE,
                "event": "end",
                **info,
                "error": type(exc).__name__,
                "monotonic": time.monotonic(),
            },
        )
        (folder / "prompts" / name).unlink()
        return None
    append(
        stages,
        {
            "stage": STAGE,
            "event": "end",
            **info,
            "wall_sec": wall,
            "first_chunk_sec": first,
            "chunks": chunks,
            "output_chars": len(text),
            "truncated": truncated,
            "error": None,
            "monotonic": time.monotonic(),
        },
    )
    answer = text.strip()
    return {
        "started": begun,
        "events": [{"type": "result", "answer": answer, "route": None}],
        "answer": answer,
        "first_token_sec": first,
        "tokens": chunks,
        "total_sec": wall,
        "truncated": truncated,
        "finished": now(),
        "prompt_file": name,
        "documents_v4": len(documents),
        "documents_v5": len(fitted),
        "same_context": same_context(documents, fitted),
    }


def run(key, runs, out):
    from llm.role_params import generation_kwargs_for_role

    llm, settings = provider_and_settings(runs, key)
    builder = Builder(llm)
    cases = v4_cases(runs, key)
    if check(builder, cases)[1]:
        return 3
    tags = {m.get("name"): m.get("digest") for m in ollama("/api/tags").get("models", [])}
    if tags.get(MODEL) != DIGEST:
        return 6
    params = generation_kwargs_for_role("generate")
    budget = float(settings.streaming_timeout_sec)
    stop = Path(out) / f"v5-{key}.stop"
    tools = {name: sha256(HERE / name) for name in TOOLS}
    code_sha = (WS / "CODE_SHA").read_text(encoding="utf-8").strip()
    loaded = False
    try:
        for number in range(1, BATCHES + 1):
            source = Path(runs) / f"v4-{key}-b{number:02d}"
            folder = Path(out) / f"v5-{key}-b{number:02d}"
            launch_path = folder / "launch.json"
            launch = (
                json.loads(launch_path.read_text(encoding="utf-8")) if launch_path.exists() else {}
            )
            if launch.get("status") == "complete":
                continue
            (folder / "cases").mkdir(parents=True, exist_ok=True)
            (folder / "prompts").mkdir(exist_ok=True)
            # A process killed between a prompt and its case leaves the prompt without a case:
            # the judge's adapter would find two prompts for the question asked again.
            named = {
                json.loads(path.read_text(encoding="utf-8"))["prompt_file"]
                for path in (folder / "cases").glob("*.json")
            }
            orphans = [p for p in (folder / "prompts").glob("*-stream.txt") if p.name not in named]
            for path in orphans:
                path.unlink()
            before = json.loads((source / "launch.json").read_text(encoding="utf-8"))
            launch = {
                **{field: before.get(field) for field in ("tenant", "chroma_dir", "cases_file")},
                "label": folder.name,
                "replay_of": source.name,
                "code_sha": code_sha,
                "model": MODEL,
                "model_digest": tags[MODEL],
                "prompt_id": V5_ID,
                "tools_sha256": tools,
                "params": params,
                "budget_sec": budget,
                "started": launch.get("started") or now(),
                "orphan_prompts": launch.get("orphan_prompts", 0) + len(orphans),
                "model_errors": launch.get("model_errors", 0),
                "status": "running",
            }
            save(launch_path, launch)
            mine = [item for item in cases if item[0] == source.name]
            for index, (_, name, case, (prompt_file, saved)) in enumerate(mine, start=1):
                target = folder / "cases" / name
                if target.exists():
                    continue
                if stop.exists():
                    launch["status"] = "stopped"
                    save(launch_path, launch)
                    return 5
                if not loaded:
                    started = time.monotonic()
                    ollama("/api/generate", {"model": MODEL, "keep_alive": "30m"}, timeout=300)
                    launch["ollama_load_sec"] = round(time.monotonic() - started, 3)
                    loaded = True
                got = ask(llm, builder, folder, params, budget, saved)
                if got is None:
                    launch.update(status="model_error", model_errors=launch["model_errors"] + 1)
                    save(launch_path, launch)
                    return 7
                head = {"case_id": case["case_id"], "question": case["question"], "index": index}
                tail = {"v4_prompt_file": prompt_file, "v4_prompt_sha256": digest(saved)}
                save(target, {**head, **got, **tail})
                if got["total_sec"] > ANSWER_STOP:
                    launch["status"] = "answer_stop"
                    save(launch_path, launch)
                    return 4
            launch.update(status="complete", finished=now(), cases=len(mine))
            save(launch_path, launch)
    finally:
        if loaded:
            ollama("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=60)
    return 0


def flat(text):
    return " ".join(text.split())


def quoted(answer, documents):
    """The answer copies its context: a passage of QUOTE characters, white space aside, found in
    one of its documents word for word."""
    said = flat(answer)
    sources = [flat(text) for _, text in documents]
    return any(
        said[start : start + QUOTE] in text
        for start in range(0, max(len(said) - QUOTE + 1, 0), QUOTE_STEP)
        for text in sources
    )


def streams(run):
    """The stand's stream rows of a run, by prompt file."""
    path = Path(run) / "stages.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {r["prompt_file"]: r for r in rows if r["stage"] == STAGE and r["event"] == "end"}


def summary(key, runs, out, records):
    """The answers of V5 and V4 on a key, ids, flags and numbers only: RECORDS/v5-KEY.cases.jsonl
    and RECORDS/v5-KEY.json."""
    rows, launches = [], []
    for number in range(1, BATCHES + 1):
        folder = Path(out) / f"v5-{key}-b{number:02d}"
        source = Path(runs) / f"v4-{key}-b{number:02d}"
        launch = json.loads((folder / "launch.json").read_text(encoding="utf-8"))
        launches.append(launch)
        v5_streams, v4_streams = streams(folder), streams(source)
        for path in sorted((folder / "cases").glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            v4 = json.loads((source / "cases" / path.name).read_text(encoding="utf-8"))
            v4_prompt = (source / "prompts" / case["v4_prompt_file"]).read_text(encoding="utf-8")
            v5_prompt = (folder / "prompts" / case["prompt_file"]).read_text(encoding="utf-8")
            if digest(v4_prompt) != case["v4_prompt_sha256"]:
                raise SystemExit(f"{folder.name}/{path.name}: V4's prompt is not the one replayed")
            v4_answer = str(v4.get("answer") or "").strip()
            mine, before = v5_streams[case["prompt_file"]], v4_streams[case["v4_prompt_file"]]
            rows.append(
                {
                    "run": folder.name,
                    "case_id": case["case_id"],
                    "index": case["index"],
                    "documents_v4": case["documents_v4"],
                    "documents_v5": case["documents_v5"],
                    "same_context": case["same_context"],
                    "prompt_est_tokens": {
                        "v4": before["prompt_est_tokens"],
                        "v5": mine["prompt_est_tokens"],
                    },
                    "chunks": {"v4": before["chunks"], "v5": mine["chunks"]},
                    "stream_sec": {
                        "v4": rounded(before["wall_sec"]),
                        "v5": rounded(mine["wall_sec"]),
                    },
                    "first_chunk_sec": {
                        "v4": rounded(before["first_chunk_sec"]),
                        "v5": rounded(mine["first_chunk_sec"]),
                    },
                    "truncated": case["truncated"],
                    # A stream chunk is a token: an answer of max_tokens chunks met the cap.
                    "at_token_cap": {
                        "v4": before["chunks"] >= launch["params"]["max_tokens"],
                        "v5": mine["chunks"] >= launch["params"]["max_tokens"],
                    },
                    "answer_chars": {"v4": len(v4_answer), "v5": len(case["answer"])},
                    "quoted": {
                        "v4": quoted(v4_answer, read_saved(v4_prompt)[1]),
                        "v5": quoted(case["answer"], read_saved(v5_prompt)[1]),
                    },
                    "v5_prompt_sha256": digest(v5_prompt),
                }
            )
    keep = (
        "label",
        "replay_of",
        "code_sha",
        "model",
        "model_digest",
        "prompt_id",
        "tools_sha256",
        "params",
        "budget_sec",
        "started",
        "finished",
        "status",
        "cases",
        "ollama_load_sec",
        "tenant",
        "orphan_prompts",
        "model_errors",
    )
    record = {
        "key": key,
        "launches": [{field: launch.get(field) for field in keep} for launch in launches],
        "answers": len(rows),
        "whole": all(launch.get("status") == "complete" for launch in launches),
    }
    Path(records).mkdir(parents=True, exist_ok=True)
    with (Path(records) / f"v5-{key}.cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    save(Path(records) / f"v5-{key}.json", record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("check", "run", "summary"))
    parser.add_argument("key", choices=KEYS)
    parser.add_argument("runs")
    parser.add_argument("out", nargs="?")
    parser.add_argument("records", nargs="?")
    args = parser.parse_args(argv)
    if args.command == "summary":
        if not (args.out and args.records):
            parser.error("summary needs OUT and RECORDS")
        record = summary(args.key, args.runs, args.out, args.records)
        print(f"SUMMARY {args.key} answers {record['answers']} whole {record['whole']}")
        return 0
    if args.command == "check":
        llm, _ = provider_and_settings(args.runs, args.key)
        rows, failed = check(Builder(llm), v4_cases(args.runs, args.key))
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        print(
            f"CHECK {args.key} cases {len(rows)} parity_failed {len(failed)} "
            f"same_context {sum(r['same_context'] for r in rows)}",
            file=sys.stderr,
        )
        return 3 if failed else 0
    if not args.out:
        parser.error("run needs OUT")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    code = run(args.key, args.runs, args.out)
    print(f"REPLAY {args.key} exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
