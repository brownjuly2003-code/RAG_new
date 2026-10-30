"""Stage 4, item 5a, its second lever: n-gram decoding in the answer model's own llama-server.

docs/specs/stage4-step5a-ngram-decoding.md, registered with this tool and its test before the
first request; PLAN.md stage 4, item 5a. The chat's answer call of step 4b's thirteen aircargo
questions - V4's answer prompt at num_ctx 4,096, rebuilt from step 4b's inputs and rendered by
Ollama itself - goes to the llama-server binary Ollama 0.33.2 runs as the model's runner,
started directly with the runner's own arguments and environment: as it is (base), and with
`--spec-type ngram-simple` at its defaults (ngram). Block 0 sends the same calls through
Ollama, so the direct base is held against the product's own generation:

  python reports/stage4-step5a-ngram/tools/ngram_decode.py inputs STEP4B_INPUTS OUT
  python reports/stage4-step5a-ngram/tools/ngram_decode.py series OUT [LAST]
  python reports/stage4-step5a-ngram/tools/ngram_decode.py block N OUT
  python reports/stage4-step5a-ngram/tools/ngram_decode.py read OUT TARGET

`inputs` runs once, with step 4's interpreter for step 4's fitting (it imports the product);
the blocks and the read need the standard library only. The answers' text stays in the
blocks' files on the Mac: record.json and rows.jsonl hold its SHA-256, length and numbers.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import signal
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage4-step4b" / "tools"))

import window_timing as wt  # noqa: E402

SPEC = "docs/specs/stage4-step5a-ngram-decoding.md"
SCHEMA = "stage4-step5a-ngram/v1"
# Step 4b's inputs on the Mac, as its record names them: the thirteen's documents and prompts.
STEP4B_RECORD = WS / "reports" / "stage4-step4b" / "d1ef9e5" / "record.json"
STEP4B_INPUTS_SHA256 = "6dc8f49ef2e4c5bce8c53e7a1dfa95595baad6c1cf72883860485e68ae930db7"
CASES = wt.CASES
MODEL, DIGEST, WINDOW = wt.MODEL, wt.DIGEST, wt.TODAY
OLLAMA_VERSION = wt.OLLAMA_VERSION
# The chat's answer call (llm/role_params.py, role "generate"), one seed for every call.
SEED = 1030
REQUEST = {"num_ctx": WINDOW, **wt.ANSWER_OPTIONS, "seed": SEED}
WARM_UP = "Ответь одним предложением: что такое испытательный срок?"
SCHEDULE = {0: "ollama", 1: "base", 2: "ngram", 3: "ngram", 4: "base"}
ARMS = {"base": (), "ngram": ("--spec-type", "ngram-simple")}
REPEATS = {"base": ("1", "4"), "ngram": ("2", "3")}
PAIRS = (("1", "2"), ("4", "3"), ("1", "3"), ("4", "2"))
FIDELITY = 3  # block 0's questions after its warm-up
PORT = 18093
# Ollama 0.33.2's api.DefaultOptions (api/types.go) for the fields its runner sends
# llama-server (llm/llama_server.go, llamaServerCompletionRequest); the model's parameters and
# the request's options go over them, in that order (server/routes.go, modelOptions).
DEFAULTS = {
    "num_predict": -1,
    "num_keep": 4,
    "temperature": 0.8,
    "top_k": 40,
    "top_p": 0.9,
    "min_p": 0.0,
    "typical_p": 1.0,
    "repeat_last_n": 64,
    "repeat_penalty": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "seed": -1,
    "stop": [],
}
INTEGERS = {"num_predict", "num_keep", "top_k", "repeat_last_n", "seed", "num_ctx"}
OMITEMPTY = ("n_predict", "n_keep", "stop", "typical_p")
OPEN_ENDED = 10  # openEndedGenerationContextMultiplier
# The runner's environment the binary or its libraries read; nothing else is kept.
ENV = re.compile(r"(?:LLAMA_|GGML_|DYLD_|OMP_)[A-Z0-9_]*")
# What Ollama draws anew for each runner it starts (llm/llama_server.go,
# newLlamaServerMediaMarker): a media marker llama-server reads only with a projector, so two
# runners are compared without it.
PER_START = ("LLAMA_MEDIA_MARKER",)
# What Ollama or ps may raise while a sample is taken: the sample is then disturbed, no end.
SAMPLE_ERRORS = (OSError, ValueError, subprocess.SubprocessError, http.client.HTTPException)
STOP_TYPES = ("eos", "word", "limit")
DONE_REASONS = ("stop", "length")
START_LIMIT = 300
QUESTION_LIMIT = 900
HEALTH_POLL = 0.5
POLL = 5
IDLE_LIMIT = 3600
IDLE_POLL = 15
LOAD_LIMIT = 2.0
BUSY = 100.0
MIN_READABLE = 10
ALPHA = 0.05
NOT_EVIDENCE = "NOT_EVIDENCE"
EXIT = {"stop": 3, "idle": 4, "slow": 5, "stand": 6, "fidelity": 7, "gate": 8, "twice": 9}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sha256(path):
    got = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            got.update(chunk)
    return got.hexdigest()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def median(values):
    kept = [v for v in values if v is not None]
    return round(statistics.median(kept), 3) if kept else None


def lines_of(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


def write_line(sink, value):
    sink.write(json.dumps(value, ensure_ascii=False) + "\n")
    sink.flush()


# --- the call: the chat's to Ollama, and Ollama's runner's to llama-server ---


def product_body(prompt, stream=True):
    """The chat's /api/generate call (step 4b's dry run: format, model, options, prompt, stream,
    think) with the seed."""
    return {
        "format": "",
        "model": MODEL,
        "options": dict(REQUEST),
        "prompt": prompt,
        "stream": stream,
        "think": False,
    }


def parameters(text):
    """/api/show's parameters - `name value` a line, a string quoted, stop repeated."""
    got = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        name, value = line.split(None, 1)
        value = value.strip()
        if value.startswith('"'):
            value = json.loads(value)
        elif name in INTEGERS:
            value = int(value)
        else:
            value = float(value)
        if name == "stop":
            got.setdefault("stop", []).append(value)
        else:
            got[name] = value
    return got


def options_of(show):
    merged = {**DEFAULTS, "stop": list(DEFAULTS["stop"])}
    merged.update(parameters(show.get("parameters") or ""))
    merged.update(REQUEST)
    return merged


def handlers_of(show):
    """The model's renderer and parser, by /api/show's fields or its Modelfile's lines. With
    either, Ollama renders the call or rewrites its answer and sends the runner the parser's
    preserved tokens (server/routes.go, GenerateHandler), which the direct body does not carry."""
    lines = [line.split(None, 1) for line in (show.get("modelfile") or "").splitlines()]
    return {
        name: show.get(name)
        or next((x[1].strip() for x in lines if len(x) == 2 and x[0] == name.upper()), None)
        for name in ("renderer", "parser")
    }


def completion_body(options, prompt):
    """What Ollama 0.33.2's runner POSTs to llama-server's /completion for a call with these
    options (llm/llama_server.go, Completion); Go's omitempty leaves out a zero or an empty
    list."""
    limit = OPEN_ENDED * options["num_ctx"]
    predict = options["num_predict"]
    body = {
        "prompt": prompt,
        "stream": True,
        "cache_prompt": True,
        "n_predict": limit if predict < 0 or predict > limit else predict,
        "n_keep": options["num_keep"],
        "temperature": options["temperature"],
        "top_k": options["top_k"],
        "top_p": options["top_p"],
        "min_p": options["min_p"],
        "stop": options["stop"],
        "repeat_penalty": options["repeat_penalty"],
        "repeat_last_n": options["repeat_last_n"],
        "frequency_penalty": options["frequency_penalty"],
        "presence_penalty": options["presence_penalty"],
        "typical_p": options["typical_p"],
        "seed": options["seed"],
    }
    return {k: v for k, v in body.items() if k not in OMITEMPTY or v}


def streamed(lines, started, key, last_of):
    """The text a stream's events make, the event that ends it, the seconds to its first text."""
    pieces, first = [], None
    for line in lines:
        event = json.loads(line)
        if event.get("error"):
            raise RuntimeError("the stream carried an error")
        if event.get(key):
            if first is None:
                first = round(time.monotonic() - started, 3)
            pieces.append(event[key])
        if last_of(event):
            return "".join(pieces), event, first
    raise RuntimeError("the stream ended without its last event")


def sse(reply):
    for raw in reply:
        line = raw.decode("utf-8").strip()
        if line.startswith("data: "):
            yield line[len("data: ") :]


def direct(body, timeout=QUESTION_LIMIT):
    """One /completion call on the direct server, read as Ollama's runner reads it."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/completion",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with OPENER.open(request, timeout=timeout) as reply:
        text, last, first = streamed(sse(reply), started, "content", lambda e: e.get("stop"))
    timings = last.get("timings") or {}
    return {
        "text": text,
        "text_sha256": digest(text),
        "wall_sec": round(time.monotonic() - started, 3),
        "first_sec": first,
        "stop_type": last.get("stop_type"),
        "truncated": last.get("truncated"),
        "tokens_predicted": last.get("tokens_predicted"),
        "tokens_evaluated": last.get("tokens_evaluated"),
        "timings": {
            k: timings.get(k)
            for k in (
                "cache_n",
                "prompt_n",
                "prompt_ms",
                "predicted_n",
                "predicted_ms",
                "draft_n",
                "draft_n_accepted",
            )
        },
        "settings": last.get("generation_settings"),
    }


def through_ollama(prompt, timeout=QUESTION_LIMIT):
    """The chat's call through Ollama: its text and Ollama's counters."""
    request = urllib.request.Request(
        wt.OLLAMA + "/api/generate",
        data=json.dumps(product_body(prompt), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with OPENER.open(request, timeout=timeout) as reply:
        lines = (raw.decode("utf-8") for raw in reply if raw.strip())
        text, last, first = streamed(lines, started, "response", lambda e: e.get("done"))
    return {
        "text": text,
        "text_sha256": digest(text),
        "wall_sec": round(time.monotonic() - started, 3),
        "first_sec": first,
        "done_reason": last.get("done_reason"),
        "counters": {k: last.get(k) for k in wt.COUNTERS},
    }


# --- the stand ---


def runner():
    """Ollama's runner of the model while it holds it: its executable, its arguments without
    the port, its model file, and the part of its environment ENV names."""
    listing = subprocess.run(
        ["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True, check=True
    ).stdout
    found = []
    for line in listing.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[1].split(" ", 1)[0].rsplit("/", 1)[-1] == "llama-server":
            found.append(parts)
    if len(found) != 1:
        raise SystemExit(f"{len(found)} llama-server processes, not Ollama's one")
    pid, command = found[0]
    shown = subprocess.run(
        ["ps", "-E", "-ww", "-o", "command=", "-p", pid], capture_output=True, text=True, check=True
    ).stdout.strip()
    if not shown.startswith(command):
        raise SystemExit("the runner's environment does not follow its command")
    env, key = {}, None
    for item in shown[len(command) :].split():
        if "=" in item:
            key, value = item.split("=", 1)
            env[key] = value
        elif key and ENV.fullmatch(key):
            # ps -E separates the variables by spaces: a kept value with one would be cut.
            raise SystemExit(f"the runner's {key} holds a space")
    argv = command.split(" ")
    args = argv[1:]
    port = args.index("--port")
    args = args[:port] + args[port + 2 :]
    return {
        "binary": argv[0],
        "args": args,
        "model": args[args.index("--model") + 1],
        "env": {k: v for k, v in sorted(env.items()) if ENV.fullmatch(k)},
    }


def runner_differs(run, read):
    """What differs between two readings of Ollama's runner: its binary, its arguments, and
    each variable of its environment but the ones Ollama draws anew for every runner."""
    names = sorted((set(run["env"]) | set(read["env"])) - set(PER_START))
    return [k for k in ("binary", "args") if run[k] != read[k]] + [
        f"env {k}" for k in names if run["env"].get(k) != read["env"].get(k)
    ]


def port_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", PORT)) == 0


def servers_on_port():
    """The direct servers: llama-server processes on PORT, never Ollama's runner."""
    listing = subprocess.run(
        ["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True, check=False
    ).stdout
    return [
        int(parts[0])
        for parts in (line.strip().split(None, 1) for line in listing.splitlines())
        if len(parts) == 2
        and parts[1].split(" ", 1)[0].rsplit("/", 1)[-1] == "llama-server"
        and f" --port {PORT} " in f"{parts[1]} "
    ]


def stand(facts):
    """What differs from the registered stand before a block's first call."""
    reasons = []
    if wt.LLAMA_CONFIG.exists():
        reasons.append("llama.cpp's config.ini exists")
    run = facts["runner"]
    if not Path(run["binary"]).exists() or sha256(run["binary"]) != run["binary_sha256"]:
        reasons.append("another llama-server")
    gguf = Path(facts["gguf"]["path"])
    if not gguf.exists() or gguf.stat().st_size != facts["gguf"]["bytes"]:
        reasons.append("another model file")
    version = wt.ollama("/api/version").get("version")
    if version != OLLAMA_VERSION:
        reasons.append(f"Ollama {version}")
    tags = {m.get("name"): m.get("digest") for m in wt.ollama("/api/tags").get("models") or []}
    if tags.get(MODEL) != DIGEST:
        reasons.append("another model under the name")
    if port_taken():
        reasons.append(f"port {PORT} taken")
    return reasons


def pids_of(*names):
    listing = subprocess.run(
        ["ps", "-axo", "pid=,comm="], capture_output=True, text=True, check=False
    ).stdout
    return {
        int(parts[0])
        for parts in (line.split(None, 1) for line in listing.splitlines())
        if len(parts) == 2 and parts[0].isdigit() and parts[1].strip().rsplit("/", 1)[-1] in names
    }


def sample(own):
    """What runs beside a call: step 0's processes, every other process's CPU, Ollama's models,
    the llama-servers, the one-minute load and the swap. When Ollama or ps does not answer, the
    sample names the error instead of ending the block."""
    got = dict.fromkeys(("foreign", "others_cpu", "models", "llama_servers", "load1", "swap_mb"))
    try:
        listing = subprocess.run(
            ["ps", "-Ao", "pid=,pcpu="], capture_output=True, text=True, check=True, timeout=20
        ).stdout
        busy = 0.0
        for line in listing.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and int(parts[0]) not in own:
                busy += float(parts[1])
        got["others_cpu"] = round(busy, 1)
        got["foreign"] = wt.foreign()
        got["models"] = wt.models()
        got["llama_servers"] = wt.llama_servers()
        got["load1"] = round(os.getloadavg()[0], 2)
        got["swap_mb"] = wt.swap_used_mb()
    except SAMPLE_ERRORS as exc:
        got["error"] = type(exc).__name__
    return got


def disturbed(got, arm):
    """A call is disturbed when step 0's processes ran, the others took more than a core,
    another model or server ran, or Ollama or ps did not answer the sample: in block 0 Ollama
    holds the model, in the others nothing."""
    models = [MODEL] if arm == "ollama" else []
    return bool(
        got.get("error")
        or got["foreign"]
        or got["others_cpu"] > BUSY
        or got["models"] != models
        or got["llama_servers"] != 1
    )


def server_env(run):
    """The runner's binary's environment outside Ollama: the runner's variables ENV keeps over a
    bare PATH, HOME and LC_ALL=C."""
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(Path.home()),
        "LC_ALL": "C",
        **run["env"],
    }


class Server:
    """The runner's binary on PORT with the runner's arguments and environment, the arm's
    arguments after them; its log beside the block's file."""

    def __init__(self, facts, arm, log):
        run = facts["runner"]
        self.command = [run["binary"], *run["args"], "--port", str(PORT), *ARMS[arm]]
        self.env = server_env(run)
        self.log, self.process = log, None

    def start(self):
        with self.log.open("ab") as sink:
            self.process = subprocess.Popen(
                self.command,
                stdout=sink,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=self.env,
            )
        deadline = time.monotonic() + START_LIMIT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"the server exited {self.process.returncode}")
            try:
                with OPENER.open(f"http://127.0.0.1:{PORT}/health", timeout=5) as reply:
                    if reply.status == 200:
                        return
            except OSError:
                pass
            time.sleep(HEALTH_POLL)
        raise RuntimeError("the server not ready in time")

    def rss_mib(self):
        shown = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(self.process.pid)], capture_output=True, text=True
        ).stdout.strip()
        return round(int(shown) / 1024, 1) if shown.isdigit() else None

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


# --- inputs ---


def clean():
    """The worktree the tool runs from holds no change and no untracked file."""
    return not wt.git("status", "--porcelain", "--untracked-files=normal")


def inputs(step4b, out):
    """The prompts and the stand, once, before the blocks, from a clean worktree: step 4b's
    thirteen prompts at 4,096 rebuilt and held to its SHA-256, with the prompt tokens step 4b's
    record counted for each, each rendered by Ollama as it renders the chat's call
    (_debug_render_only), the runner read from ps while Ollama holds the model, then unloaded."""
    if not clean():
        raise SystemExit("the worktree is not clean")
    if sha256(step4b) != STEP4B_INPUTS_SHA256:
        raise SystemExit("not step 4b's inputs")
    sys.path.insert(0, str(WS / "reports" / "stage4-step4" / "tools"))
    import prompt_budget as pb

    stored = json.loads(Path(step4b).read_text(encoding="utf-8"))
    if tuple(c["case_id"] for c in stored["cases"]) != CASES:
        raise SystemExit("step 4b's inputs do not hold the thirteen in order")
    flats = [("warm-up", WARM_UP)]
    with pb.answer_prompt(pb.code_prompt()):
        for case in stored["cases"]:
            flat, _ = pb.fit(WINDOW, case["question"], case["plain"])
            if digest(flat) != case["prompts"][str(WINDOW)]["sha256"]:
                raise SystemExit(f"{case['case_id']}: not step 4b's prompt at {WINDOW}")
            flats.append((case["case_id"], flat))
    # Ollama's prompt_eval_count for each prompt in step 4b, on the same model and Ollama.
    counted = {
        pair["case_id"]: pair["w4096_answer_prompt_tokens"]
        for pair in json.loads(STEP4B_RECORD.read_text(encoding="utf-8"))["pairs"]
    }
    if wt.LLAMA_CONFIG.exists() or wt.models() or wt.llama_servers():
        raise SystemExit("config.ini, a model in Ollama or a llama-server before the inputs")
    show = wt.ollama("/api/show", {"model": MODEL})
    handlers = handlers_of(show)
    if any(handlers.values()):
        raise SystemExit(f"the model has a renderer or a parser: {handlers}")
    calls = []
    for case_id, flat in flats:
        body = {**product_body(flat, stream=False), "_debug_render_only": True}
        rendered = wt.ollama("/api/generate", body, 600)["_debug_info"]["rendered_template"]
        call = {
            "case_id": case_id,
            "flat": flat,
            "flat_sha256": digest(flat),
            "rendered": rendered,
            "rendered_sha256": digest(rendered),
        }
        if case_id != "warm-up":
            call["step4b_prompt_tokens"] = counted[case_id]
        calls.append(call)
    held = wt.loaded()
    if held.get("digest") != DIGEST:
        raise SystemExit("Ollama holds another model")
    run = runner()
    unloaded = wt.unload()
    if "DYLD_LIBRARY_PATH" not in run["env"]:
        raise SystemExit("no DYLD_LIBRARY_PATH in the runner's environment")
    gguf = Path(run["model"])
    gguf_sha = sha256(gguf)
    if gguf.name != f"sha256-{gguf_sha}":
        raise SystemExit("the model file is not the one its name says")
    shown = subprocess.run(
        [run["binary"], "--version"],
        capture_output=True,
        text=True,
        env=server_env(run),
        timeout=60,
    )
    if shown.returncode != 0:
        raise SystemExit(f"the runner's binary exits {shown.returncode} on --version")
    value = {
        "schema": SCHEMA,
        "spec": SPEC,
        "code_sha": wt.git("rev-parse", "HEAD"),
        "tool_sha256": sha256(Path(__file__)),
        "step4b_inputs": {"path": str(step4b), "sha256": STEP4B_INPUTS_SHA256},
        "model": MODEL,
        "digest": DIGEST,
        "ollama_version": wt.ollama("/api/version").get("version"),
        "show": {
            "parameters": show.get("parameters"),
            "template_sha256": digest(show.get("template") or ""),
            "details": show.get("details"),
            **handlers,
        },
        "options": options_of(show),
        "runner": {
            "binary": run["binary"],
            "binary_sha256": sha256(run["binary"]),
            "version": (shown.stdout + shown.stderr).strip(),
            "args": run["args"],
            "env": run["env"],
        },
        "gguf": {"path": str(gguf), "bytes": gguf.stat().st_size, "sha256": gguf_sha},
        "loaded": held,
        "unload": unloaded,
        "warm_up": calls[0],
        "cases": calls[1:],
    }
    out.mkdir(parents=True, exist_ok=True)
    wt.write_json(out / "inputs.json", value)
    print(" ".join(value["runner"]["args"]))
    print("environment: " + " ".join(value["runner"]["env"]))
    print(json.dumps(value["options"], ensure_ascii=False))
    print(f"inputs.json sha256 {sha256(out / 'inputs.json')}")
    return 0


# --- blocks ---


def calls_of(facts, arm):
    calls = [facts["warm_up"], *facts["cases"]]
    return calls[: FIDELITY + 1] if arm == "ollama" else calls


def block(number, out):
    """One block into OUT/blocks/NN.jsonl: a head line, a line a call, an end line. Exit 6 when
    the stand is not the registered one."""
    arm = SCHEDULE[number]
    facts = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    partial = out / "blocks" / f"{number:02d}.partial.jsonl"
    own = {os.getpid(), os.getppid()}
    reasons = stand(facts)
    head = {
        "block": number,
        "arm": arm,
        "tool_sha256": sha256(Path(__file__)),
        "inputs_sha256": sha256(out / "inputs.json"),
        "started_at": now(),
        "stand": reasons,
        "machine": wt.machine(),
    }
    with partial.open("w", encoding="utf-8") as sink:
        write_line(sink, head)
        if reasons:
            return EXIT["stand"]
        server, end, rss = None, {}, []
        if arm != "ollama":
            server = Server(facts, arm, out / "blocks" / f"{number:02d}.server.log")

        def mine():
            # Block 0's work is Ollama's and its runner's, started by its first call.
            return own | pids_of("ollama", "llama-server") if arm == "ollama" else own

        try:
            if server:
                started = time.monotonic()
                server.start()
                own.add(server.process.pid)
                end["load_sec"] = round(time.monotonic() - started, 3)
                rss.append(server.rss_mib())
            for position, call in enumerate(calls_of(facts, arm)):
                before = sample(mine())
                if arm == "ollama":
                    prompt = call["flat"]
                    got = through_ollama(prompt)
                    got["sent_sha256"] = digest(prompt)
                    if position == 0:
                        # The runner Ollama started for the calls is the one the inputs read,
                        # but for what Ollama draws anew for each runner.
                        run = runner()
                        end["runner"] = run
                        end["runner_differs"] = runner_differs(run, facts["runner"])
                else:
                    body = completion_body(facts["options"], call["rendered"])
                    got = direct(body)
                    got["sent_sha256"] = digest(body["prompt"])
                    rss.append(server.rss_mib())
                line = {"position": position, "case_id": call["case_id"], "before": before}
                write_line(sink, {**line, **got, "after": sample(mine())})
        finally:
            if server:
                server.stop()
        if arm == "ollama":
            end["unload"] = wt.unload()
        else:
            # Read once after the load and once after each call, never during one.
            end.update(
                rss_after_load_mib=rss[0],
                rss_max_after_calls_mib=max((r for r in rss[1:] if r), default=None),
            )
        write_line(sink, {"done": True, "ended_at": now(), **end})
    partial.rename(out / "blocks" / f"{number:02d}.jsonl")
    return 0


def check(number, path, facts, out):
    """A block's file against the schedule and the inputs: the reasons it fails its gate."""
    arm = SCHEDULE[number]
    lines = lines_of(path)
    if len(lines) < 3:
        return ["no head, call and end"]
    head, body, end = lines[0], lines[1:-1], lines[-1]
    reasons = []
    if (head.get("block"), head.get("arm")) != (number, arm):
        reasons.append("not the schedule's block")
    if head.get("tool_sha256") != sha256(Path(__file__)):
        reasons.append("another tool")
    if head.get("inputs_sha256") != sha256(out / "inputs.json"):
        reasons.append("other inputs")
    if head.get("stand"):
        reasons.append("the stand: " + "; ".join(head["stand"]))
    if end.get("done") is not True:
        reasons.append("no end line")
    calls = calls_of(facts, arm)
    if [(x.get("position"), x.get("case_id")) for x in body] != [
        (i, c["case_id"]) for i, c in enumerate(calls)
    ]:
        return [*reasons, "not the schedule's calls"]
    if arm == "ollama" and end.get("runner_differs") != []:
        differs = end.get("runner_differs") or ["not read"]
        reasons.append("Ollama's runner not the one the inputs read: " + ", ".join(differs))
    for line, call in zip(body, calls, strict=True):
        name = call["case_id"]
        if not line.get("text") or line.get("text_sha256") != digest(line["text"]):
            reasons.append(f"{name}: no text or not its SHA-256")
        if arm == "ollama":
            counters = line.get("counters") or {}
            if line.get("sent_sha256") != call["flat_sha256"]:
                reasons.append(f"{name}: another prompt")
            if line.get("done_reason") not in DONE_REASONS or not counters.get("eval_count"):
                reasons.append(f"{name}: not a finished call")
            continue
        timings = line.get("timings") or {}
        if line.get("sent_sha256") != call["rendered_sha256"]:
            reasons.append(f"{name}: another prompt")
        # Ollama's count of the same prompt in step 4b: none for the warm-up.
        counted = call.get("step4b_prompt_tokens")
        if counted is not None and line.get("tokens_evaluated") != counted:
            tokens = line.get("tokens_evaluated")
            reasons.append(f"{name}: {tokens} prompt tokens, not step 4b's {counted}")
        if line.get("stop_type") not in STOP_TYPES or line.get("truncated"):
            reasons.append(f"{name}: not a finished call")
        if not timings.get("predicted_n") or not timings.get("predicted_ms"):
            reasons.append(f"{name}: no decode timings")
        elif (timings.get("cache_n") or 0) + (timings.get("prompt_n") or 0) != line.get(
            "tokens_evaluated"
        ):
            reasons.append(f"{name}: the prompt's tokens do not add up")
    return reasons


def fidelity(zero, one):
    """Block 0 through Ollama against block 1's direct base on the same calls: the same text,
    the same prompt and answer token counts (Ollama's prompt_eval_count is cache_n + prompt_n,
    its eval_count predicted_n)."""
    calls = []
    for a, b in zip(lines_of(zero)[1:-1], lines_of(one)[1:-1], strict=False):
        t = b["timings"]
        calls.append(
            {
                "case_id": a["case_id"],
                "same_text": a["text_sha256"] == b["text_sha256"],
                "prompt_tokens": [a["counters"]["prompt_eval_count"], t["cache_n"] + t["prompt_n"]],
                "answer_tokens": [a["counters"]["eval_count"], t["predicted_n"]],
            }
        )
    holds = len(calls) == FIDELITY + 1 and all(
        c["same_text"]
        and c["prompt_tokens"][0] == c["prompt_tokens"][1]
        and c["answer_tokens"][0] == c["answer_tokens"][1]
        for c in calls
    )
    return {"calls": calls, "reading": "holds" if holds else "fails"}


def idle(first, own):
    """Wait for the idle Mac: no step 0 process, no model in Ollama, no llama-server, no
    ci-local lock, the others under a core; before the first block the 5-minute load below 2.
    A sample Ollama or ps did not answer is not idle."""
    deadline = time.monotonic() + IDLE_LIMIT
    while True:
        got = sample(own)
        if (
            not got.get("error")
            and not got["foreign"]
            and not got["models"]
            and not got["llama_servers"]
            and not wt.CI_LOCK.exists()
            and got["others_cpu"] <= BUSY
            and (not first or os.getloadavg()[1] < LOAD_LIMIT)
        ):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(IDLE_POLL)


def launch(number, out):
    """The block in a process of its own; killed when its head line or its next call does not
    come within the limit."""
    partial = out / "blocks" / f"{number:02d}.partial.jsonl"
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "block", str(number), str(out)]
    with (out / "blocks.out").open("a", encoding="utf-8") as sink:
        process = subprocess.Popen(
            command, stdout=sink, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
        )
        seen, since = 0, time.monotonic()
        while process.poll() is None:
            time.sleep(POLL)
            count = len(partial.read_bytes().splitlines()) if partial.exists() else 0
            if count != seen:
                seen, since = count, time.monotonic()
            elif time.monotonic() - since > (QUESTION_LIMIT if seen else START_LIMIT):
                process.kill()
                process.wait()
                # The killed block's own server, or Ollama's model when it was block 0.
                for pid in servers_on_port():
                    os.kill(pid, signal.SIGTERM)
                if SCHEDULE[number] == "ollama":
                    try:
                        wt.unload()
                    except (OSError, TimeoutError, ValueError):
                        pass
                return EXIT["slow"]
    return process.returncode


def series(out, last):
    """The schedule's blocks up to LAST, from the first without a file, on a clean worktree read
    at the start and before each block; see the spec's Stops."""
    (out / "blocks").mkdir(parents=True, exist_ok=True)
    (out / "rejected").mkdir(exist_ok=True)
    facts = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    tool = sha256(Path(__file__))
    state_path = out / "series.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"tool_sha256": tool, "attempts": {}}
    )

    def say(text):
        with (out / "series.log").open("a", encoding="utf-8") as log:
            log.write(f"{now()} {text}\n")

    if not clean():
        say("the worktree is not clean")
        return EXIT["stand"]
    if state["tool_sha256"] != tool:
        say("another tool started this series")
        return EXIT["stand"]

    def faithful(number):
        if number != 1:
            return True
        got = fidelity(out / "blocks" / "00.jsonl", out / "blocks" / "01.jsonl")
        if got["reading"] != "holds":
            say(f"block 1 fidelity: {json.dumps(got['calls'])}")
            return False
        return True

    own, first = {os.getpid()}, True
    for number in range(last + 1):
        arm = SCHEDULE[number]
        final = out / "blocks" / f"{number:02d}.jsonl"
        if final.exists():
            # A block kept from an earlier start is read again: its stop holds on every start.
            reasons = check(number, final, facts, out)
            if reasons:
                say(f"block {number} kept but failing: {'; '.join(reasons)}")
                return EXIT["gate"]
            if not faithful(number):
                return EXIT["fidelity"]
            continue
        if (out / "stop").exists():
            say("stop file")
            return EXIT["stop"]
        tried = state["attempts"].get(str(number), 0)
        if tried >= 2:
            say(f"block {number} failed twice")
            return EXIT["twice"]
        if not idle(first, own):
            say("the Mac not idle within an hour")
            return EXIT["idle"]
        if not clean():
            say("the worktree is not clean")
            return EXIT["stand"]
        first = False
        state["attempts"][str(number)] = tried + 1
        state_path.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
        say(f"block {number} {arm}, attempt {tried + 1}")
        code = launch(number, out)
        reasons = check(number, final, facts, out) if code == 0 and final.exists() else None
        if code != 0 or reasons:
            for path in (final, out / "blocks" / f"{number:02d}.partial.jsonl"):
                if path.exists():
                    path.rename(out / "rejected" / f"{number:02d}-{tried + 1}-{path.name}")
            say(f"block {number} failed: {'; '.join(reasons or [f'exit {code}'])}")
            return {EXIT["slow"]: EXIT["slow"], EXIT["stand"]: EXIT["stand"]}.get(
                code, EXIT["gate"]
            )
        if not faithful(number):
            return EXIT["fidelity"]
        say(f"block {number} read")
    # SERIES_DONE only for the whole schedule; a shorter LAST is the first part of it.
    say("SERIES_DONE" if last == max(SCHEDULE) else f"blocks to {last} done")
    return 0


# --- the reading ---


def numbers(line, arm):
    t = line["timings"]
    return {
        "text_sha256": line["text_sha256"],
        "chars": len(line["text"]),
        "stop_type": line["stop_type"],
        "tokens_evaluated": line["tokens_evaluated"],
        "cache_n": t["cache_n"],
        "prompt_n": t["prompt_n"],
        "prompt_ms": round(t["prompt_ms"], 1),
        "predicted_n": t["predicted_n"],
        "predicted_ms": round(t["predicted_ms"], 1),
        "draft_n": t.get("draft_n") or 0,
        "draft_n_accepted": t.get("draft_n_accepted") or 0,
        "wall_sec": line["wall_sec"],
        "first_sec": line["first_sec"],
        "disturbed": disturbed(line["before"], arm) or disturbed(line["after"], arm),
    }


def first_difference(a, b):
    """The first character where two texts part; the shorter's length when one begins the
    other."""
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return i
    return min(len(a), len(b))


def per_token(entry):
    return entry["predicted_ms"] / entry["predicted_n"]


def speed(rows):
    """ngram's decode against base's, a question at a time: each arm's two blocks' mean of
    milliseconds a generated token; the exact two-sided sign test on the questions no block
    disturbed."""
    readable = [r for r in rows if not r["disturbed"]]
    base, ngram, saved, ratio = [], [], [], []
    for row in readable:
        b = statistics.mean(per_token(row["blocks"][n]) for n in REPEATS["base"])
        g = statistics.mean(per_token(row["blocks"][n]) for n in REPEATS["ngram"])
        bs = statistics.mean(row["blocks"][n]["predicted_ms"] for n in REPEATS["base"]) / 1000
        gs = statistics.mean(row["blocks"][n]["predicted_ms"] for n in REPEATS["ngram"]) / 1000
        base.append(b)
        ngram.append(g)
        saved.append(bs - gs)
        ratio.append(b / g)
    faster = sum(1 for b, g in zip(base, ngram, strict=True) if g < b)
    slower = sum(1 for b, g in zip(base, ngram, strict=True) if g > b)
    p = wt.sign_p(faster, slower)
    if len(readable) < MIN_READABLE:
        reading = NOT_EVIDENCE
    elif p < ALPHA and faster > slower:
        reading = "faster"
    elif p < ALPHA and slower > faster:
        reading = "slower"
    else:
        reading = "no detected difference"

    def wall(arm):
        return median(
            statistics.mean(r["blocks"][n]["wall_sec"] for n in REPEATS[arm]) for r in readable
        )

    return {
        "questions": len(rows),
        "readable": len(readable),
        "disturbed": [r["case_id"] for r in rows if r["disturbed"]],
        "faster": faster,
        "slower": slower,
        "p": round(p, 6),
        "reading": reading,
        "base_ms_per_token_median": median(base),
        "ngram_ms_per_token_median": median(ngram),
        "ratio_median": median(ratio),
        "saved_decode_sec_median": median(saved),
        "base_wall_sec_median": wall("base"),
        "ngram_wall_sec_median": wall("ngram"),
    }


def equality(rows):
    """Byte-equality of the answers: each arm's two blocks, then base's against ngram's. A base
    that does not repeat itself reads nothing."""
    n = len(rows)

    def same(a, b):
        return sum(
            1 for r in rows if r["blocks"][a]["text_sha256"] == r["blocks"][b]["text_sha256"]
        )

    repeat = {arm: same(*blocks) for arm, blocks in REPEATS.items()}
    pairs = {f"{a}-{b}": same(a, b) for a, b in PAIRS}
    if repeat["base"] < n:
        reading = NOT_EVIDENCE
    elif all(v == n for v in pairs.values()):
        reading = "byte-equal"
    else:
        reading = "differ"
    return {"questions": n, "repeat": repeat, "pairs": pairs, "reading": reading}


def acceptance(rows):
    got = {}
    for n in REPEATS["ngram"]:
        drafted = sum(r["blocks"][n]["draft_n"] for r in rows)
        accepted = sum(r["blocks"][n]["draft_n_accepted"] for r in rows)
        got[n] = {
            "draft_n": drafted,
            "draft_n_accepted": accepted,
            "rate": round(accepted / drafted, 4) if drafted else None,
        }
    return got


def outcome(readings):
    if readings["fidelity"]["reading"] != "holds":
        return NOT_EVIDENCE
    pace = readings["speed"]["reading"]
    if pace != "faster":
        return pace if pace == NOT_EVIDENCE else "not faster"
    same = readings["equality"]["reading"]
    if same == NOT_EVIDENCE:
        return NOT_EVIDENCE
    return "faster and byte-equal" if same == "byte-equal" else "faster, answers differ"


def block_summary(lines, arm):
    head, body, end = lines[0], lines[1:-1], lines[-1]
    samples = [line[k] for line in body for k in ("before", "after")]
    got = {
        "arm": arm,
        "started_at": head["started_at"],
        "ended_at": end["ended_at"],
        "calls": len(body),
        "warm_up_sec": body[0]["wall_sec"],
        "disturbed": sum(
            1
            for line in body[1:]
            if disturbed(line["before"], arm) or disturbed(line["after"], arm)
        ),
        "others_cpu_max": max(
            (s["others_cpu"] for s in samples if s["others_cpu"] is not None), default=None
        ),
        "sample_errors": sum(1 for s in samples if s.get("error")),
        "swap_mb": [samples[0]["swap_mb"], samples[-1]["swap_mb"]],
    }
    if arm == "ollama":
        got["unload_sec"] = end["unload"]["unload_sec"]
    else:
        got.update(
            load_sec=end["load_sec"],
            rss_after_load_mib=end["rss_after_load_mib"],
            rss_max_after_calls_mib=end["rss_max_after_calls_mib"],
            settings=body[1]["settings"],
        )
    return got


def read(out, target):
    """The record of a series that ended SERIES_DONE, or that stopped on block 1's fidelity:
    then blocks 0 and 1 only, the fidelity's calls, no rows."""
    facts = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    blocks, faithful = {}, None
    for number in SCHEDULE:
        if number == 2:
            faithful = fidelity(out / "blocks" / "00.jsonl", out / "blocks" / "01.jsonl")
            if faithful["reading"] != "holds":
                break
        path = out / "blocks" / f"{number:02d}.jsonl"
        reasons = check(number, path, facts, out) if path.exists() else ["no file"]
        if reasons:
            raise SystemExit(f"block {number}: {'; '.join(reasons)}")
        blocks[number] = lines_of(path)
    rows = []
    every = len(blocks) == len(SCHEDULE)
    for position, case in enumerate(facts["cases"] if every else [], start=1):
        lines = {str(n): blocks[n][position + 1] for n in SCHEDULE if n}
        row = {
            "case_id": case["case_id"],
            "position": position,
            "blocks": {n: numbers(line, SCHEDULE[int(n)]) for n, line in lines.items()},
        }
        row["disturbed"] = any(entry["disturbed"] for entry in row["blocks"].values())
        row["first_difference"] = {
            f"{a}-{b}": first_difference(lines[a]["text"], lines[b]["text"])
            for a, b in (*REPEATS.values(), *PAIRS)
            if lines[a]["text_sha256"] != lines[b]["text_sha256"]
        }
        if position <= FIDELITY:
            zero = blocks[0][position + 1]
            row["ollama"] = {
                "text_sha256": zero["text_sha256"],
                "done_reason": zero["done_reason"],
                "wall_sec": zero["wall_sec"],
                **{k: zero["counters"][k] for k in wt.COUNTERS},
            }
        rows.append(row)
    readings = {"fidelity": faithful}
    if every:
        readings.update(equality=equality(rows), speed=speed(rows), acceptance=acceptance(rows))
    state = json.loads((out / "series.json").read_text(encoding="utf-8"))
    record = {
        "schema": SCHEMA,
        "spec": SPEC,
        "measured_at_head": facts["code_sha"],
        "tool_sha256": sha256(Path(__file__)),
        "inputs": {
            "sha256": sha256(out / "inputs.json"),
            "step4b_inputs_sha256": facts["step4b_inputs"]["sha256"],
            **{k: facts[k] for k in ("model", "digest", "ollama_version", "show", "options")},
            "runner": facts["runner"],
            "gguf": facts["gguf"],
            "calls": [
                {k: c[k] for k in ("case_id", "flat_sha256", "rendered_sha256")}
                for c in (facts["warm_up"], *facts["cases"])
            ],
        },
        "blocks": {str(n): block_summary(lines, SCHEDULE[n]) for n, lines in blocks.items()},
        "attempts": state["attempts"],
        "rejected": sorted(p.name for p in (out / "rejected").iterdir()),
        "readings": readings,
        "outcome": outcome(readings),
    }
    target.mkdir(parents=True, exist_ok=True)
    wt.write_json(target / "record.json", record)
    with (target / "rows.jsonl").open("w", encoding="utf-8") as sink:
        for row in rows:
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"readings": readings, "outcome": record["outcome"]}, ensure_ascii=False))
    return 0


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["inputs"] and len(args) == 3:
        return inputs(Path(args[1]), Path(args[2]))
    if args[:1] == ["series"] and len(args) in (2, 3):
        return series(Path(args[1]), int(args[2]) if len(args) == 3 else max(SCHEDULE))
    if args[:1] == ["block"] and len(args) == 3:
        return block(int(args[1]), Path(args[2]))
    if args[:1] == ["read"] and len(args) == 3:
        return read(Path(args[1]), Path(args[2]))
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
