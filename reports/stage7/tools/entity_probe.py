"""Stage 7's entity-extraction cost probe: an English prompt on 100 MultiHop-RAG chunks.

docs/specs/stage7-entity-probe.md. On the Mac, any Python 3.11, the standard library only:

  python -I entity_probe.py run RUN_DIR [--archive PATH] [--ollama URL]
  python -I entity_probe.py read OUT RUN_DIR

run first checks the registered stand (the endpoint, platform.system(), platform.machine(),
Ollama's version) and step 0's idle rule (the 5-minute load below 2, no other measurement or job
by pgrep, no CI lock, no model in Ollama), and refuses otherwise. It sends PROMPT, filled with one
chunk, to the production model in Ollama as the product's extraction would
(scripts/extract_graph_entities.py through llm/providers/pinned_ollama.py): /api/chat, stream
false, keep_alive 30m, temperature 0, seed 42, num_ctx 4096 and the extraction cache's schema as
`format`, then the digest in /api/tags, both under one timer. After the load the model must sit
on the CPU with a context of 4096 in one llama-server runner started with `-np 1` and `-c 4096`.
One warm-up chunk first, then 100 chunks at evenly spaced indices of the archive's chunk list,
every tenth first. A chunk's row in RUN_DIR/chunks.jsonl holds its seconds, Ollama's counters,
whether the output passes the cache's acceptance rule, its entity counts and the contention seen
after it; the spec's sequential rule may stop the run as G2 failed. A chat that reaches the
product's 900 s is cut and ends the run by that rule; a reply the product's client would raise
on breaks the run, and so does a cap reached by the load, the warm-up or the run. Every request
is timed on the clock against its cap. Exit 0 when the run is complete or stopped, 3 when
refused (nothing written), 5 when broken (end.json says why).

read gates RUN_DIR and reads gate G2: stop E if 11,231 times the upper 95 % bound of the mean
seconds exceeds 24 h, or if fewer than 95 of the 100 outputs are valid. A malformed field anywhere
reads as NOT_EVIDENCE with a note, never as an exception. It refuses an existing OUT.

Every file either writes holds numbers, enums, ids, model names, the paths named here and SHA-256
strings: never a chunk's text, an output's text, a source name, a host name, a command line or the
filled prompt.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import json
import math
import os
import platform
import re
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_ID = "stage7-entity-probe/v1"
SPEC = "docs/specs/stage7-entity-probe.md"
HERE = Path(__file__).resolve().parent
NOT_EVIDENCE = "NOT_EVIDENCE"

# The stand: the production model in Ollama 0.33.2 on the Mac's CPU (stage 4, step 0's record).
OLLAMA = "http://127.0.0.1:11434"
OLLAMA_VERSION = "0.33.2"
SYSTEM = "Darwin"
MACHINE = "x86_64"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
# The product's call (llm/providers/pinned_ollama.py): its options and its keep-alive.
OPTIONS: dict[str, Any] = {"temperature": 0, "seed": 42, "num_ctx": 4096}
KEEP_ALIVE = "30m"

# Step 0's idle rule, applied at the start: the 5-minute load below MAX_LOAD5, none of IDLE's
# processes but this probe and its parent, no CI lock, no model in Ollama. After each chunk the
# probe counts OTHERS: IDLE without the stand's own two, the model's runner and the probe.
IDLE = r"[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl|[e]ntity_probe"
OTHERS = r"[p]ytest|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl"
# The model's runner after the load: Ollama starts llama-server with `-c NumCtx * slots` and
# `-np slots` (llm/llama_server.go), and /api/ps's context_length does not show the slots.
RUNNER = r"[l]lama-server"
SLOTS = 1  # OLLAMA_NUM_PARALLEL's default (envconfig/config.go)
LOCK = Path.home() / "ci_local" / ".lock_ci-local"
MAX_LOAD5 = 2.0
RELOAD_NS = 1_000_000_000  # a chat's load_duration above 1 s: the model was loaded again

# MultiHop-RAG's chunks of the second index generation (built at e5e135a), as stage 2 read them.
ARCHIVE = "/Users/julia/RAG_new_external_s1/multihoprag/chunks.json.gz"
ARCHIVE_SHA256 = "db25b882fc9fe6cd6e76101330ffc816a9081813268706a016a263171cf80300"
TENANT = "ext_multihoprag"

# Gate G2, the stop rule and the projections.
N_MULTIHOP = 11_231
N_OTHER = 51_349  # ConditionalQA 13,778 + WixQA 37,571: printed, deciding nothing
DAY = 86_400
TOTAL = 100
MIN_VALID = 95
MAX_INVALID = TOTAL - MIN_VALID
CHECKPOINTS = (10, 20, 40, 70)

# Caps, in seconds: a chat request (PinnedOllamaChat's own timeout), the model's load, the run
# from its start to the end of its last request, any other request or check, and the wait for
# the unload, longer after a cut.
CHUNK_CAP: float = 900
LOAD_CAP: float = 300
RUN_CAP: float = 3_000
CALL_CAP: float = 30
UNLOAD_CAP: float = 60
UNLOAD_CUT_CAP: float = 1_200

# The English prompt: no domain word, names in the passage's own language.
PROMPT = (
    "Extract the key entities from the passage below: named people, organisations, places,"
    " products and events, and the specific terms the passage is about. Skip dates, numbers"
    " and generic words that would fit any passage. Write each entity in its base form, in the"
    " language of the passage; do not translate. Reply only with a JSON array of 3 to 12"
    " strings.\n\nPassage:\n{chunk}\n\nJSON:"
)
# The extraction cache's schema (ingestion/entity_extraction.py, EXTRACT_SCHEMA), unchanged: the
# loader reads a list of entity strings a chunk and derives its edges itself.
SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string", "minLength": 1, "maxLength": 128},
    "maxItems": 12,
}
PROMPT_SHA256 = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()
FORMAT_SHA256 = hashlib.sha256(
    json.dumps(SCHEMA, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

REASONS = ("ok", "empty", "not_json", "schema", "cap")
STATUSES = ("ok", "cap")
RULES = ("invalid", "seconds", "lower")
# Why a run broke. The chat_* reasons mirror PinnedOllamaChat's raise paths; chat_transport is a
# 5xx or another transport error, which the product retries and the probe does not.
BROKEN = (
    "load_failed",
    "load_cap",
    "ps_failed",
    "not_loaded",
    "stand",
    "warmup_cap",
    "chat_transport",
    "chat_http_4xx",
    "chat_not_json",
    "chat_not_object",
    "chat_error",
    "chat_no_message",
    "chat_no_content",
    "counters",
    "tags_failed",
    "digest",
    "run_cap",
    "interrupted",
)
DONE_REASONS = ("stop", "length", "load", "unload")
COUNTERS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)
ROW_KEYS = (
    "position",
    "pick",
    "index",
    "content_sha256",
    "content_chars",
    "status",
    "sec",
    "chat_sec",
    "valid",
    "reason",
    "entities",
    "distinct",
    "pairs",
    "output_sha256",
    "output_chars",
    "ollama",
    "digest_ok",
    "others",
    "lock",
    "alone",
)
LAUNCH_KEYS = (
    "schema",
    "spec",
    "tool_sha256",
    "started",
    "python",
    "system",
    "machine",
    "loadavg",
    "others",
    "lock",
    "swap_used_mib",
    "archive",
    "archive_sha256",
    "tenant",
    "n_chunks",
    "ollama",
    "ollama_version",
    "ollama_models_before",
    "model",
    "model_digest",
    "options",
    "keep_alive",
    "prompt_sha256",
    "format_sha256",
    "picks",
    "order",
    "warmup_index",
    "total",
    "checkpoints",
    "max_invalid",
    "caps_sec",
)
LOAD_KEYS = (
    "sec",
    "load_duration",
    "size",
    "size_vram",
    "context_length",
    "runners",
    "runner_np",
    "runner_c",
)
END_KEYS = (
    "status",
    "reason",
    "stop",
    "n",
    "ended",
    "run_sec",
    "wall_sec",
    "load",
    "unload_cap_sec",
    "unload_sec",
    "ollama_models_end",
    "ollama_models_after",
    "loadavg",
    "swap_used_mib",
)
INT64 = 2**63 - 1
_FENCE = re.compile(r"```(?:json)?\s*(\[.*\])\s*```", re.S)
_TOKEN = re.compile(r"[^\W_]+")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[\w.:/-]{1,200}", re.ASCII)
_VERSION = re.compile(r"\d+(\.\d+){0,3}[\w.+-]{0,20}", re.ASCII)
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", re.ASCII)
NOT_A_NAME = "<not a name>"

# Indirections the test replaces: the network, the clock, the pause, the processes, the platform.
_urlopen: Callable[..., Any] = urllib.request.urlopen
_clock: Callable[[], float] = time.perf_counter
_sleep: Callable[[float], None] = time.sleep
_run: Callable[..., Any] = subprocess.run
_system: Callable[[], str] = platform.system
_machine: Callable[[], str] = platform.machine


def _loadavg() -> list[float] | None:
    """The load averages over 1, 5 and 15 minutes, unrounded; None where there are none."""
    if sys.platform == "win32":
        return None
    try:
        return list(os.getloadavg())
    except OSError:
        return None


def _swap_used_mib() -> float | None:
    """The swap in use, in MiB (macOS `sysctl -n vm.swapusage`); None elsewhere."""
    try:
        out = _run(
            ["sysctl", "-n", "vm.swapusage"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        match = re.search(r"used = ([\d.]+)M", str(out))
        return float(match.group(1)) if match else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def caps() -> dict[str, float]:
    return {
        "chunk": CHUNK_CAP,
        "load": LOAD_CAP,
        "run": RUN_CAP,
        "call": CALL_CAP,
        "unload": UNLOAD_CAP,
        "unload_cut": UNLOAD_CUT_CAP,
    }


# --- small helpers -----------------------------------------------------------------------------


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def a_count(value: Any) -> int | None:
    """An int from 0 to INT64 as it is; anything else (a bool and a float included) is None."""
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= INT64:
        return value
    return None


def a_name(value: Any) -> str | None:
    """A model name, a tag or a digest as it is (a tag holds ":"); anything else masked."""
    if value is None:
        return None
    return value if isinstance(value, str) and _NAME.fullmatch(value) else NOT_A_NAME


def a_version(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and _VERSION.fullmatch(value) else "<other>"


def an_enum(value: Any, known: Sequence[str]) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) and value in known else "<other>"


def put(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_bytes(text.encode("utf-8"))


def append_row(path: Path, row: dict[str, Any]) -> None:
    with path.open("ab") as stream:
        stream.write((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


# --- the Mac around the stand ------------------------------------------------------------------


def pids(pattern: str) -> list[int] | None:
    """The processes `pgrep -f pattern` finds besides this one and its parent; None when pgrep
    fails."""
    try:
        done = _run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=CALL_CAP,
            check=False,
        )
        code, tokens = done.returncode, str(done.stdout).split()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if code == 1:
        return []
    if code != 0 or not all(token.isascii() and token.isdigit() for token in tokens):
        return None
    own = {os.getpid(), os.getppid()}
    return [int(token) for token in tokens if int(token) not in own]


def processes(pattern: str) -> int | None:
    """How many processes pids() finds; None when pgrep fails. A count only: never a command
    line."""
    found = pids(pattern)
    return None if found is None else len(found)


def runner_flags() -> dict[str, int | None]:
    """The model's runner as Ollama started it: how many llama-server processes pgrep finds and,
    when it finds one, the integers after its `-np` and `-c`. Its arguments are read by ps and
    dropped: only these three numbers are kept, never a command line."""
    found = pids(RUNNER)
    flags: dict[str, int | None] = {
        "runners": None if found is None else len(found),
        "runner_np": None,
        "runner_c": None,
    }
    if found is None or len(found) != 1:
        return flags
    try:
        done = _run(
            ["ps", "-ww", "-o", "args=", "-p", str(found[0])],
            capture_output=True,
            text=True,
            timeout=CALL_CAP,
            check=False,
        )
        tokens = str(done.stdout).split() if done.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        tokens = []
    for flag, key in (("-np", "runner_np"), ("-c", "runner_c")):
        at = [i for i, token in enumerate(tokens) if token == flag]
        if len(at) == 1 and at[0] + 1 < len(tokens):
            value = tokens[at[0] + 1]
            if value.isascii() and value.isdigit() and len(value) <= 18:
                flags[key] = int(value)
    return flags


def locked() -> bool:
    """Whether the CI's lock file is there; a lock that cannot be checked counts as held."""
    try:
        return LOCK.exists()
    except OSError:
        return True


# --- the choice, the order, the output's check -------------------------------------------------


def picks(n_chunks: int) -> list[int]:
    """TOTAL indices evenly spaced over a list of n_chunks from 0: pick i is i * n_chunks // TOTAL
    (scripts/graph_probe.py's int(i * step), in integers)."""
    if n_chunks <= TOTAL:
        raise ValueError("the list must be longer than the picks")
    return [i * n_chunks // TOTAL for i in range(TOTAL)]


def run_order() -> list[int]:
    """The picks in the order they run: every tenth first (0, 10, ..., 90, 1, 11, ...), so the
    chunks before each checkpoint spread over the whole list."""
    return sorted(range(TOTAL), key=lambda i: (i % 10, i // 10))


def sequence(n_chunks: int) -> list[tuple[int, int | None, int]]:
    """(position, pick, index) in the order the run sends them: the warm-up, the list's last
    chunk, at position 0, then the 100 picks."""
    chosen = picks(n_chunks)
    return [(0, None, n_chunks - 1)] + [
        (position, pick, chosen[pick]) for position, pick in enumerate(run_order(), start=1)
    ]


def validate(content: object) -> tuple[str, list[str] | None]:
    """The extraction cache's acceptance rule (ingestion/entity_extraction.py, _entities): the
    stripped output, a ```json fence allowed, is a JSON list of at most 12 strings of 1-128
    characters once stripped. The reason and the list, or the reason and None."""
    if not isinstance(content, str) or not content.strip():
        return "empty", None
    text = content.strip()
    fenced = _FENCE.fullmatch(text)
    if fenced:
        text = fenced.group(1)
    try:
        values = json.loads(text)
    except (ValueError, RecursionError):
        return "not_json", None
    if (
        not isinstance(values, list)
        or len(values) > 12
        or any(
            not isinstance(value, str) or not value.strip() or len(value.strip()) > 128
            for value in values
        )
    ):
        return "schema", None
    return "ok", values


def keys(values: Sequence[str]) -> list[str]:
    """The loader's entity keys without its two dictionaries (ingestion/entity_normalization.py):
    casefolded Unicode word tokens joined by a space; empty and repeated keys dropped; at most
    12."""
    result: list[str] = []
    for value in values:
        key = " ".join(_TOKEN.findall(value.casefold()))
        if key and key not in result:
            result.append(key)
            if len(result) == 12:
                break
    return result


# --- the interval, the stop rule, gate G2 ------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """The continued fraction of the regularized incomplete beta function (Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        step = d * c
        h *= step
        if abs(step - 1.0) < 1e-15:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t: float, df: int) -> float:
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t >= 0 else tail


@lru_cache(maxsize=None)
def t975(df: int) -> float:
    """Student's t quantile 0.975 with df degrees of freedom, by bisection."""
    low, high = 0.0, 1000.0
    for _ in range(200):
        middle = (low + high) / 2
        if _t_cdf(middle, df) < 0.975:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def bounds(seconds: Sequence[float]) -> tuple[float, float, float]:
    """The mean and its two-sided 95 % interval, mean -/+ t975(n - 1) * s / sqrt(n)."""
    n = len(seconds)
    mean = statistics.fmean(seconds)
    half = t975(n - 1) * statistics.stdev(seconds) / math.sqrt(n)
    return mean, mean - half, mean + half


def stop_at(seconds: Sequence[float], valid: Sequence[bool]) -> str | None:
    """The sequential rule after the n-th of the 100 (n below 100): the rule that stops the run
    as G2 failed, or None. More than 5 invalid and the seconds already past 100 chunks at the
    line make G2's failure certain and are read after every chunk; the lower bound above the
    line is read at the checkpoints. A run passes only after all 100."""
    n = len(seconds)
    if n >= TOTAL:
        return None
    if n - sum(valid) > MAX_INVALID:
        return "invalid"
    if N_MULTIHOP * math.fsum(seconds) > TOTAL * DAY:
        return "seconds"
    if n in CHECKPOINTS and N_MULTIHOP * bounds(seconds)[1] > DAY:
        return "lower"
    return None


def first_stop(seconds: Sequence[float], valid: Sequence[bool]) -> tuple[str, int] | None:
    """Where the rule first stops a run of these chunks, in their order, or None."""
    for n in range(1, min(len(seconds), TOTAL - 1) + 1):
        rule = stop_at(seconds[:n], valid[:n])
        if rule:
            return rule, n
    return None


def g2(seconds: Sequence[float], valid: Sequence[bool]) -> dict[str, Any]:
    """Gate G2 on all 100: stop E if 11,231 times the upper bound exceeds 24 h, or if fewer than
    95 outputs are valid. A bound exactly on the line passes."""
    if len(seconds) != TOTAL or len(valid) != TOTAL:
        raise ValueError("G2 reads all 100")
    mean, lower, upper = bounds(seconds)
    failed_by = []
    if N_MULTIHOP * upper > DAY:
        failed_by.append("seconds")
    if sum(valid) < MIN_VALID:
        failed_by.append("valid")
    return {
        "verdict": "failed" if failed_by else "passed",
        "failed_by": failed_by,
        "n": TOTAL,
        "valid": sum(valid),
        "mean_sec": round(mean, 6),
        "lower_sec": round(lower, 6),
        "upper_sec": round(upper, 6),
        "line_sec": round(DAY / N_MULTIHOP, 6),
    }


# --- Ollama ------------------------------------------------------------------------------------


class Broken(Exception):
    """The stand failed: the run ends as broken, with this reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Failure(Exception):
    """A request to Ollama that gave no usable JSON object; kind says how."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def call(base: str, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    """One request to Ollama and its JSON object, or a Failure whose kind follows
    PinnedOllamaChat: timeout; transport (an HTTP 5xx or another transport error, both retried by
    the product); http_4xx (any other HTTP status, raised at once); not_json; not_object; error
    (an object with an "error" key). A request that reaches `timeout` on the clock is a timeout
    whatever came, as urllib's timeout bounds each socket operation, not the request."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=data,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    kind: str | None = None
    raw = b""
    began = _clock()
    try:
        with _urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        kind = "transport" if 500 <= exc.code <= 599 else "http_4xx"
    except urllib.error.URLError as exc:
        kind = "timeout" if isinstance(exc.reason, TimeoutError) else "transport"
    except TimeoutError:
        kind = "timeout"
    except (OSError, http.client.HTTPException, ValueError):
        kind = "transport"
    if _clock() - began >= timeout:
        kind = "timeout"
    if kind is not None:
        raise Failure(kind)
    try:
        body = json.loads(bytes(raw).decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise Failure("not_json") from exc
    if not isinstance(body, dict):
        raise Failure("not_object")
    if "error" in body:
        raise Failure("error")
    return body


def ps(base: str) -> list[dict[str, Any]]:
    """The models Ollama holds (/api/ps), each entry an object; else a Failure."""
    models = call(base, "/api/ps", None, CALL_CAP).get("models")
    if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
        raise Failure("not_object")
    return models


def loaded(base: str) -> list[str | None]:
    return [a_name(item.get("name")) for item in ps(base)]


def ps_entry(base: str) -> dict[str, Any] | None:
    for item in ps(base):
        if item.get("name") == MODEL:
            return item
    return None


def alone(base: str) -> bool | None:
    """Whether Ollama holds exactly one model, this one by name and digest; None when /api/ps
    fails."""
    try:
        models = ps(base)
    except Failure:
        return None
    return (
        len(models) == 1
        and models[0].get("name") == MODEL
        and models[0].get("digest") == MODEL_DIGEST
    )


def tag_digest(base: str) -> str | None:
    """The model's digest in /api/tags, as the product's pinned client confirms it."""
    models = call(base, "/api/tags", None, CALL_CAP).get("models")
    if not isinstance(models, list):
        raise Failure("not_object")
    for item in models:
        if isinstance(item, dict) and item.get("name") == MODEL:
            digest = item.get("digest")
            return digest if isinstance(digest, str) and _HEX64.fullmatch(digest) else "<bad>"
    return None


def chat_content(body: dict[str, Any]) -> str:
    """The reply's content as PinnedOllamaChat's _chat_content returns it, or Broken."""
    message = body.get("message")
    if not isinstance(message, dict):
        raise Broken("chat_no_message")
    content = message.get("content")
    if not isinstance(content, str) or content == "":
        raise Broken("chat_no_content")
    return content


def count_in(body: dict[str, Any], key: str) -> int | None:
    """A counter of Ollama's reply: None when omitted (its fields are omitempty, so read as 0),
    else an int from 0 to INT64. One present but not such an int breaks the run: it could not be
    told from a reload."""
    if key not in body:
        return None
    value = a_count(body[key])
    if value is None:
        raise Broken("counters")
    return value


def counters(body: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {key: count_in(body, key) for key in COUNTERS}
    out["done_reason"] = an_enum(body.get("done_reason"), DONE_REASONS)
    return out


def contention(base: str) -> dict[str, Any]:
    """Read after a chunk, outside its timer: how many processes of other measurements and jobs
    run, whether the CI's lock is held, and whether Ollama holds this model alone."""
    return {"others": processes(OTHERS), "lock": locked(), "alone": alone(base)}


def one_chunk(base: str, position: int, pick: int | None, index: int, text: str) -> dict[str, Any]:
    """One extraction request as the product's ingestion sends it, its digest check under the same
    timer (PinnedOllamaChat.chat), and its row: numbers, enums, ids and SHA-256 strings only. A
    chat that reaches CHUNK_CAP on the clock is cut, whatever came: its row keeps the measured
    seconds and no output or counters. A reply the product's client would raise on is Broken."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(chunk=text)}],
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": dict(OPTIONS),
        "format": SCHEMA,
    }
    body: dict[str, Any] | None = None
    started = _clock()
    try:
        body = call(base, "/api/chat", payload, CHUNK_CAP)
    except Failure as exc:
        if exc.kind != "timeout":
            raise Broken(f"chat_{exc.kind}") from exc
    chat_sec = float(_clock() - started)
    cut = chat_sec >= CHUNK_CAP
    if body is None and not cut:
        raise Broken("chat_transport")  # a timeout short of the cap is not the cap's
    content = None if cut or body is None else chat_content(body)
    ollama = None if cut or body is None else counters(body)
    digest_ok: bool | None
    try:
        digest_ok = tag_digest(base) == MODEL_DIGEST
    except Failure:
        digest_ok = None
    sec = float(_clock() - started)
    reason, values = ("cap", None) if content is None else validate(content)
    found = keys(values) if values is not None else None
    return {
        "position": position,
        "pick": pick,
        "index": index,
        "content_sha256": sha256_text(text),
        "content_chars": len(text),
        "status": "cap" if cut else "ok",
        "sec": sec,
        "chat_sec": chat_sec,
        "valid": reason == "ok",
        "reason": reason,
        "entities": None if values is None else len(values),
        "distinct": None if found is None else len(found),
        "pairs": None if found is None else math.comb(len(found), 2),
        "output_sha256": None if content is None else sha256_text(content),
        "output_chars": None if content is None else len(content),
        "ollama": ollama,
        "digest_ok": digest_ok,
    }


def unload(
    base: str, bound: float
) -> tuple[list[str | None] | None, list[str | None] | None, float | None]:
    """The models before the unload, the models after it, and the seconds from keep_alive 0 to
    the reply that showed this model gone (None if none did): a look once a second until one does
    or `bound` seconds have passed (Ollama unloads once no request holds it). A reply that shows
    it gone late is kept with its seconds, for the gate to read."""
    before: list[str | None] | None
    try:
        before = loaded(base)
    except Failure:
        before = None
    began = _clock()
    try:
        call(base, "/api/generate", {"model": MODEL, "keep_alive": 0}, CALL_CAP)
    except Failure:
        pass  # the looks below show whether the model went
    after: list[str | None] | None = None
    gone: float | None = None
    for _ in range(math.ceil(bound) + 1):
        try:
            after = loaded(base)
        except Failure:
            after = None
        waited = float(_clock() - began)
        if after is not None and MODEL not in after:
            gone = waited
            break
        if waited >= bound:
            break
        _sleep(1.0)
    return before, after, gone


# --- run ---------------------------------------------------------------------------------------


def refuse(reason: str) -> int:
    print(f"refused: {reason}", file=sys.stderr)
    return 3


def run(run_dir: Path, archive: Path, base: str) -> int:
    if run_dir.exists():
        return refuse(f"{run_dir} exists")
    # The registered stand first, as cheap as a refusal gets; the gate reads it again.
    base = base.rstrip("/")
    if base != OLLAMA:
        return refuse("the endpoint is not the registered one")
    if _system() != SYSTEM:
        return refuse("the system is not the registered one")
    if _machine() != MACHINE:
        return refuse("the machine is not the registered one")
    try:
        data = archive.read_bytes()
    except OSError:
        return refuse("the archive cannot be read")
    archive_sha256 = hashlib.sha256(data).hexdigest()
    if archive_sha256 != ARCHIVE_SHA256:
        return refuse("the archive is not the registered one")
    payload = json.loads(gzip.decompress(data).decode("utf-8"))
    chunks = [chunk.get("page_content") for chunk in payload.get("chunks") or []]
    if (
        payload.get("tenant_id") != TENANT
        or len(chunks) != N_MULTIHOP
        or not all(isinstance(text, str) for text in chunks)
    ):
        return refuse("the archive's tenant or chunk count is not the registered one")
    plan = sequence(len(chunks))
    texts: dict[int, str] = {index: chunks[index] for _, _, index in plan}
    del payload, chunks
    try:
        version = call(base, "/api/version", None, CALL_CAP).get("version")
        before = loaded(base)
        digest = tag_digest(base)
    except Failure:
        return refuse("Ollama does not answer")
    if version != OLLAMA_VERSION:
        return refuse("Ollama's version is not the registered one")
    if before:
        return refuse("a model is loaded in Ollama: the Mac is not idle")
    if digest != MODEL_DIGEST:
        return refuse("the model is absent or its digest is not the registered one")
    load_average = _loadavg()
    if load_average is None or not load_average[1] < MAX_LOAD5:
        return refuse("the 5-minute load is not below 2: the Mac is not idle")
    others = processes(IDLE)
    if others != 0:
        return refuse("pgrep finds another measurement or job, or fails: the Mac is not idle")
    lock = locked()
    if lock:
        return refuse("the CI lock is held: the Mac is not idle")

    run_dir.mkdir(parents=True)
    rows_path = run_dir / "chunks.jsonl"
    put(
        run_dir / "launch.json",
        {
            "schema": SCHEMA_ID,
            "spec": SPEC,
            "tool_sha256": sha256_file(Path(__file__).resolve()),
            "started": now(),
            "python": platform.python_version(),
            "system": _system(),
            "machine": _machine(),
            "loadavg": load_average,
            "others": others,
            "lock": lock,
            "swap_used_mib": _swap_used_mib(),
            "archive": str(archive),
            "archive_sha256": archive_sha256,
            "tenant": TENANT,
            "n_chunks": N_MULTIHOP,
            "ollama": base,
            "ollama_version": a_version(version),
            "ollama_models_before": before,
            "model": MODEL,
            "model_digest": digest,
            "options": OPTIONS,
            "keep_alive": KEEP_ALIVE,
            "prompt_sha256": PROMPT_SHA256,
            "format_sha256": FORMAT_SHA256,
            "picks": picks(N_MULTIHOP),
            "order": run_order(),
            "warmup_index": N_MULTIHOP - 1,
            "total": TOTAL,
            "checkpoints": list(CHECKPOINTS),
            "max_invalid": MAX_INVALID,
            "caps_sec": caps(),
        },
    )
    started = _clock()
    status, reason, stop = "broken", None, None
    load: dict[str, Any] = dict.fromkeys(LOAD_KEYS)
    rows: list[dict[str, Any]] = []
    run_sec: float | None = None
    try:
        began = _clock()
        try:
            body = call(
                base,
                "/api/generate",
                {"model": MODEL, "keep_alive": KEEP_ALIVE, "options": dict(OPTIONS)},
                LOAD_CAP,
            )
        except Failure as exc:
            load["sec"] = float(_clock() - began)
            raise Broken("load_cap" if exc.kind == "timeout" else "load_failed") from exc
        load["sec"] = float(_clock() - began)
        load["load_duration"] = count_in(body, "load_duration")
        if load["sec"] >= LOAD_CAP:
            raise Broken("load_cap")
        try:
            entry = ps_entry(base)
        except Failure as exc:
            raise Broken("ps_failed") from exc
        if entry is None:
            raise Broken("not_loaded")
        for key in ("size", "size_vram", "context_length"):
            load[key] = a_count(entry.get(key))
        load.update(runner_flags())
        print(
            f"loaded in {load['sec']:.1f} s, size_vram {load['size_vram']},"
            f" context_length {load['context_length']}, runners {load['runners']},"
            f" -np {load['runner_np']}, -c {load['runner_c']}",
            flush=True,
        )
        if (
            load["size_vram"] != 0
            or load["context_length"] != OPTIONS["num_ctx"]
            or load["runners"] != 1
            or load["runner_np"] != SLOTS
            or load["runner_c"] != SLOTS * OPTIONS["num_ctx"]
        ):
            raise Broken("stand")
        run_sec = float(_clock() - started)
        if run_sec >= RUN_CAP:
            raise Broken("run_cap")
        for position, pick, index in plan:
            row = one_chunk(base, position, pick, index, texts[index])
            row.update(contention(base))
            rows.append(row)
            append_row(rows_path, row)
            print(
                f"chunk {position} pick {pick} index {index} sec {row['sec']:.3f}"
                f" {row['reason']} entities {row['entities']}"
                f" others {row['others']} lock {row['lock']} alone {row['alone']}",
                flush=True,
            )
            if row["digest_ok"] is None:
                raise Broken("tags_failed")
            if not row["digest_ok"]:
                raise Broken("digest")
            if position == 0 and row["status"] == "cap":
                raise Broken("warmup_cap")
            run_sec = float(_clock() - started)
            if run_sec >= RUN_CAP:
                raise Broken("run_cap")
            if position == 0:
                continue
            measured = rows[1:]
            seconds = [item["sec"] for item in measured]
            if position in CHECKPOINTS:
                mean, lower, upper = bounds(seconds)
                print(
                    f"look {position}: mean {mean:.3f} lower {lower:.3f} upper {upper:.3f}"
                    f" line {DAY / N_MULTIHOP:.3f}",
                    flush=True,
                )
            rule = stop_at(seconds, [item["valid"] for item in measured])
            if rule:
                status, stop = "stopped", {"rule": rule, "at": position}
                break
        else:
            status = "complete"
    except Broken as exc:
        reason = exc.reason
    except KeyboardInterrupt:
        reason = "interrupted"
    finally:
        bound = UNLOAD_CUT_CAP if rows and rows[-1]["status"] == "cap" else UNLOAD_CAP
        models_end, models_after, gone = unload(base, bound)
        put(
            run_dir / "end.json",
            {
                "status": status,
                "reason": reason,
                "stop": stop,
                "n": max(len(rows) - 1, 0),
                "ended": now(),
                "run_sec": run_sec,
                "wall_sec": float(_clock() - started),
                "load": load,
                "unload_cap_sec": bound,
                "unload_sec": gone,
                "ollama_models_end": models_end,
                "ollama_models_after": models_after,
                "loadavg": _loadavg(),
                "swap_used_mib": _swap_used_mib(),
            },
        )
    detail = f"{stop['rule']} at {stop['at']}" if stop else (reason or "")
    print(f"PROBE_DONE {status} {detail}".rstrip(), flush=True)
    return 0 if status in ("complete", "stopped") else 5


# --- read --------------------------------------------------------------------------------------


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        return None


def _rows(path: Path) -> list[Any] | None:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, ValueError):
        return None
    if text and not text.endswith("\n"):
        return None
    try:
        return [json.loads(line) for line in text.split("\n")[:-1]]
    except (ValueError, RecursionError):
        return None


def _count(value: Any, high: int = INT64) -> bool:
    """An int from 0 to high (a bool is not one)."""
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= high


def _finite(value: Any, high: float = 1e9) -> bool:
    """A number from 0 to high: NaN and the infinities fail (a bool is not one)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0 <= value <= high


def _hex64(value: Any) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _same(value: Any, expected: Any) -> bool:
    """Equal as JSON: 1, 1.0 and true differ."""
    try:
        return json.dumps(value, sort_keys=True) == json.dumps(expected, sort_keys=True)
    except (TypeError, ValueError, RecursionError):
        return False


def _names_ok(value: Any) -> bool:
    return value is None or (
        isinstance(value, list)
        and all(
            item is None
            or (isinstance(item, str) and (item == NOT_A_NAME or _NAME.fullmatch(item)))
            for item in value
        )
    )


def _loadavg_ok(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(_finite(item) for item in value)


def _counters_ok(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {*COUNTERS, "done_reason"}
        and all(value[key] is None or _count(value[key]) for key in COUNTERS)
        and (value["done_reason"] is None or value["done_reason"] in (*DONE_REASONS, "<other>"))
    )


def _row_ok(row: Any, position: int, pick: int | None, index: int) -> bool:
    """D7's row: every field well formed and the fields consistent with each other; the chat's
    seconds decide the cut, as the probe decided it, and lie within the row's."""
    if not isinstance(row, dict) or set(row) != set(ROW_KEYS):
        return False
    status, reason, valid = row["status"], row["reason"], row["valid"]
    if not (
        _same([row["position"], row["pick"], row["index"]], [position, pick, index])
        and _hex64(row["content_sha256"])
        and _count(row["content_chars"])
        and status in STATUSES
        and reason in REASONS
        and (status == "cap") == (reason == "cap")
        and valid is (reason == "ok")
        and _finite(row["sec"])
        and _finite(row["chat_sec"])
        and row["chat_sec"] <= row["sec"]
        and (status == "cap") == (row["chat_sec"] >= CHUNK_CAP)
        and (row["digest_ok"] is None or isinstance(row["digest_ok"], bool))
        and (row["others"] is None or _count(row["others"]))
        and isinstance(row["lock"], bool)
        and (row["alone"] is None or isinstance(row["alone"], bool))
    ):
        return False
    if status == "cap":
        kept = (
            row["output_sha256"] is None and row["output_chars"] is None and row["ollama"] is None
        )
    else:
        kept = (
            _hex64(row["output_sha256"])
            and _count(row["output_chars"])
            and row["output_chars"] >= 1
            and _counters_ok(row["ollama"])
        )
    entities, distinct, pairs = row["entities"], row["distinct"], row["pairs"]
    if not valid:
        return kept and entities is None and distinct is None and pairs is None
    return (
        kept
        and _count(entities, 12)
        and _count(distinct, 12)
        and distinct <= entities
        and _same(pairs, math.comb(distinct, 2))
    )


def _rows_ok(rows: Any, notes: list[str]) -> bool:
    if not isinstance(rows, list) or not rows:
        notes.append("chunks.jsonl missing, unreadable or empty")
        return False
    if len(rows) > TOTAL + 1:
        notes.append("more rows than the warm-up and the 100")
        return False
    expected = sequence(N_MULTIHOP)[: len(rows)]
    bad = [
        position
        for row, (position, pick, index) in zip(rows, expected, strict=True)
        if not _row_ok(row, position, pick, index)
    ]
    notes.extend(f"row {position} does not have the registered shape" for position in bad)
    return not bad


def _clean(rows: list[dict[str, Any]], notes: list[str]) -> bool:
    """No row, the warm-up's included, saw another measurement or job, the CI lock, another model
    or none, or a reload of this one: a job seen after the warm-up may have run into the first
    measured chunk."""
    clean = True
    for row in rows:
        why = []
        if row["others"] is None:
            why.append("pgrep failed")
        elif row["others"] > 0:
            why.append("other processes")
        if row["lock"]:
            why.append("the CI lock")
        if row["alone"] is None:
            why.append("/api/ps failed")
        elif not row["alone"]:
            why.append("not this model alone")
        ollama = row["ollama"]
        if ollama is not None and (ollama["load_duration"] or 0) > RELOAD_NS:
            why.append("a reload")
        if why:
            notes.append(f"row {row['position']} contended: {', '.join(why)}")
            clean = False
    return clean


def _launch_ok(launch: Any, notes: list[str]) -> bool:
    if not isinstance(launch, dict):
        notes.append("launch.json missing or unreadable")
        return False
    if set(launch) != set(LAUNCH_KEYS):
        notes.append("launch: keys other than the registered ones")
        return False
    expected = {
        "schema": SCHEMA_ID,
        "spec": SPEC,
        "tool_sha256": sha256_file(HERE / "entity_probe.py"),
        "system": SYSTEM,
        "machine": MACHINE,
        "others": 0,
        "lock": False,
        "archive_sha256": ARCHIVE_SHA256,
        "tenant": TENANT,
        "n_chunks": N_MULTIHOP,
        "ollama": OLLAMA,
        "ollama_version": OLLAMA_VERSION,
        "ollama_models_before": [],
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "options": OPTIONS,
        "keep_alive": KEEP_ALIVE,
        "prompt_sha256": PROMPT_SHA256,
        "format_sha256": FORMAT_SHA256,
        "picks": picks(N_MULTIHOP),
        "order": run_order(),
        "warmup_index": N_MULTIHOP - 1,
        "total": TOTAL,
        "checkpoints": list(CHECKPOINTS),
        "max_invalid": MAX_INVALID,
        "caps_sec": caps(),
    }
    wrong = [key for key, value in expected.items() if not _same(launch[key], value)]
    average = launch["loadavg"]
    if not (_loadavg_ok(average) and average[1] < MAX_LOAD5):
        wrong.append("loadavg")
    if not (launch["swap_used_mib"] is None or _finite(launch["swap_used_mib"])):
        wrong.append("swap_used_mib")
    for key, pattern in (("started", _STAMP), ("python", _VERSION)):
        if not (isinstance(launch[key], str) and pattern.fullmatch(launch[key])):
            wrong.append(key)
    if not isinstance(launch["archive"], str):
        wrong.append("archive")
    notes.extend(f"launch: {key} is not the registered value" for key in sorted(wrong))
    return not wrong


def _load_ok(load: Any) -> bool:
    return (
        isinstance(load, dict)
        and set(load) == set(LOAD_KEYS)
        and (load["sec"] is None or _finite(load["sec"]))
        and all(load[key] is None or _count(load[key]) for key in LOAD_KEYS[1:])
    )


def _end_shape_ok(end: Any) -> bool:
    """Every field of end.json well formed, whatever the run's status."""
    if not isinstance(end, dict) or set(end) != set(END_KEYS):
        return False
    stop = end["stop"]
    return bool(
        end["status"] in ("complete", "stopped", "broken")
        and (end["reason"] is None or end["reason"] in BROKEN)
        and (
            stop is None
            or (
                isinstance(stop, dict)
                and set(stop) == {"rule", "at"}
                and stop["rule"] in RULES
                and _count(stop["at"], TOTAL)
            )
        )
        and _count(end["n"], TOTAL)
        and isinstance(end["ended"], str)
        and _STAMP.fullmatch(end["ended"])
        and (end["run_sec"] is None or _finite(end["run_sec"]))
        and _finite(end["wall_sec"])
        and _load_ok(end["load"])
        and (
            _same(end["unload_cap_sec"], UNLOAD_CAP) or _same(end["unload_cap_sec"], UNLOAD_CUT_CAP)
        )
        and (end["unload_sec"] is None or _finite(end["unload_sec"]))
        and _names_ok(end["ollama_models_end"])
        and _names_ok(end["ollama_models_after"])
        and (end["loadavg"] is None or _loadavg_ok(end["loadavg"]))
        and (end["swap_used_mib"] is None or _finite(end["swap_used_mib"]))
    )


def _end_ok(end: Any, rows: list[dict[str, Any]], notes: list[str]) -> bool:
    if not isinstance(end, dict):
        notes.append("end.json missing or unreadable")
        return False
    if not _end_shape_ok(end):
        notes.append("end.json does not have the registered shape")
        return False
    if end["status"] == "broken":
        notes.append(f"the run is broken: {end['reason']}")
        return False
    if not rows:
        return False  # the rows' own note says why
    measured = rows[1:]
    found = first_stop([row["sec"] for row in measured], [row["valid"] for row in measured])
    ok = end["reason"] is None and end["n"] == len(measured)
    if end["status"] == "complete":
        ok = ok and len(measured) == TOTAL and end["stop"] is None and found is None
    else:
        ok = (
            ok
            and found is not None
            and len(measured) == found[1]
            and _same(end["stop"], {"rule": found[0], "at": found[1]})
        )
    load, run_sec = end["load"], end["run_sec"]
    ok = (
        ok
        and load["sec"] is not None
        and load["sec"] < LOAD_CAP
        and load["size_vram"] == 0
        and load["context_length"] == OPTIONS["num_ctx"]
        and load["runners"] == 1
        and load["runner_np"] == SLOTS
        and load["runner_c"] == SLOTS * OPTIONS["num_ctx"]
        and run_sec is not None
        and run_sec < RUN_CAP
        and end["wall_sec"] >= run_sec
        # The load and the rows are spans of the run, one after another, on one clock.
        and math.fsum([load["sec"], *(row["sec"] for row in rows)]) <= run_sec
        and all(row["digest_ok"] is True for row in rows)
        and rows[0]["status"] != "cap"
        and _same(
            end["unload_cap_sec"], UNLOAD_CUT_CAP if rows[-1]["status"] == "cap" else UNLOAD_CAP
        )
    )
    if not ok:
        notes.append(
            "end.json does not agree with the rows, the stop rule, the stand, the seconds or the"
            " caps"
        )
    shared = end["ollama_models_end"] != [MODEL]
    if shared:
        notes.append("the models in Ollama at the end were not this one alone")
    left = end["ollama_models_after"] != []
    if left:
        notes.append("a model was still in Ollama after the unload")
    late = not left and (end["unload_sec"] is None or end["unload_sec"] > end["unload_cap_sec"])
    if late:
        notes.append("no reply within the unload's bound showed the model gone")
    return ok and not shared and not left and not late


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _median(values: Sequence[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def _hours(chunks: int, sec: float | None) -> float | None:
    return None if sec is None else round(chunks * sec / 3600, 1)


def printed(
    launch: dict[str, Any] | None, rows: list[dict[str, Any]], end: dict[str, Any] | None
) -> dict[str, Any]:
    """What stands beside G2 and decides nothing: from checked rows, and from launch.json and
    end.json only when their fields were checked (else None). Rounded here, for display only."""
    measured = rows[1:]
    seconds = [row["sec"] for row in measured]
    mean = lower = upper = None
    if len(seconds) >= 2:
        mean, lower, upper = bounds(seconds)
    counted = [row["ollama"] for row in measured if row["ollama"] is not None]

    def total(key: str) -> float:
        return math.fsum(item[key] for item in counted if item[key] is not None)

    def rate(count: str, duration: str) -> float | None:
        seconds_spent = total(duration) / 1e9
        return round(total(count) / seconds_spent, 2) if seconds_spent else None

    def median_of(key: str) -> float | None:
        return _median([item[key] for item in counted if item[key] is not None])

    valid_rows = [row for row in measured if row["valid"]]
    half = len(seconds) // 2
    load = None if end is None else end["load"]
    return {
        "n": len(measured),
        "valid": len(valid_rows),
        "reasons": dict(Counter(row["reason"] for row in measured)),
        "empty_arrays": sum(1 for row in valid_rows if row["entities"] == 0),
        "mean_sec": _round(mean, 6),
        "lower_sec": _round(lower, 6),
        "upper_sec": _round(upper, 6),
        "median_sec": _median(seconds),
        "p90_sec": (
            round(sorted(seconds)[math.ceil(0.9 * len(seconds)) - 1], 3) if seconds else None
        ),
        "max_sec": round(max(seconds), 3) if seconds else None,
        "line_sec": round(DAY / N_MULTIHOP, 6),
        "projected_hours": {
            "multihoprag_at_mean": _hours(N_MULTIHOP, mean),
            "multihoprag_at_upper": _hours(N_MULTIHOP, upper),
            "conditionalqa_wixqa_at_mean": _hours(N_OTHER, mean),
            "conditionalqa_wixqa_at_upper": _hours(N_OTHER, upper),
        },
        "halves_mean_sec": (
            [round(statistics.fmean(part), 3) for part in (seconds[:half], seconds[half:])]
            if half
            else None
        ),
        "prompt_eval_count_median": median_of("prompt_eval_count"),
        "eval_count_median": median_of("eval_count"),
        "prompt_tokens_per_sec": rate("prompt_eval_count", "prompt_eval_duration"),
        "generated_tokens_per_sec": rate("eval_count", "eval_duration"),
        "wall_less_ollama_median_sec": _median(
            [
                row["sec"] - row["ollama"]["total_duration"] / 1e9
                for row in measured
                if row["ollama"] is not None and row["ollama"]["total_duration"] is not None
            ]
        ),
        "reloads": sum(1 for item in counted if (item["load_duration"] or 0) > RELOAD_NS),
        "done_reasons": dict(Counter(str(item["done_reason"]) for item in counted)),
        "entities_median": _median([row["entities"] for row in valid_rows]),
        "distinct_median": _median([row["distinct"] for row in valid_rows]),
        "pairs_median": _median([row["pairs"] for row in valid_rows]),
        "content_chars_median": _median([row["content_chars"] for row in measured]),
        "warmup": {"sec": round(rows[0]["sec"], 3), "reason": rows[0]["reason"]},
        "load": (
            None
            if load is None
            else {**{key: load[key] for key in LOAD_KEYS[1:]}, "sec": _round(load["sec"], 3)}
        ),
        "run_sec": None if end is None else _round(end["run_sec"], 3),
        "wall_sec": None if end is None else round(end["wall_sec"], 3),
        "loadavg": {
            "launch": None if launch is None else [round(v, 2) for v in launch["loadavg"]],
            "end": (
                None
                if end is None or end["loadavg"] is None
                else [round(v, 2) for v in end["loadavg"]]
            ),
        },
        "swap_used_mib": {
            "launch": None if launch is None else _round(launch["swap_used_mib"], 1),
            "end": None if end is None else _round(end["swap_used_mib"], 1),
        },
        "unload_sec": None if end is None else _round(end["unload_sec"], 3),
        "ollama_models_after": None if end is None else end["ollama_models_after"],
    }


def read(run_dir: Path) -> dict[str, Any]:
    notes: list[str] = []
    launch = _json(run_dir / "launch.json")
    rows = _rows(run_dir / "chunks.jsonl")
    end = _json(run_dir / "end.json")
    gate = {"launch": _launch_ok(launch, notes), "rows": _rows_ok(rows, notes)}
    usable: list[dict[str, Any]] = rows if gate["rows"] and isinstance(rows, list) else []
    gate["end"] = _end_ok(end, usable, notes)
    gate["clean"] = bool(usable) and _clean(usable, notes)
    reading: dict[str, Any]
    if not all(gate.values()):
        reading = {"verdict": NOT_EVIDENCE}
    elif end["status"] == "stopped":
        stop = end["stop"]
        reading = {"verdict": "failed", "failed_by": [stop["rule"]], "stopped_at": stop["at"]}
    else:
        measured = usable[1:]
        reading = g2([row["sec"] for row in measured], [row["valid"] for row in measured])
    shown = None
    if usable:
        checked_end = end if _end_shape_ok(end) else None
        shown = printed(launch if gate["launch"] else None, usable, checked_end)
    return {
        "schema": SCHEMA_ID,
        "spec": SPEC,
        "tool_sha256": sha256_file(HERE / "entity_probe.py"),
        "run": run_dir.name,
        "files_sha256": {
            name: sha256_file(run_dir / name)
            for name in ("launch.json", "chunks.jsonl", "end.json")
        },
        "gate": gate,
        "notes": notes,
        "g2": reading,
        "printed_deciding_nothing": shown,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("run_dir", type=Path)
    run_parser.add_argument("--archive", type=Path, default=Path(ARCHIVE))
    run_parser.add_argument("--ollama", default=OLLAMA)
    read_parser = commands.add_parser("read")
    read_parser.add_argument("out", type=Path)
    read_parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args.run_dir, args.archive, args.ollama)
    if args.out.exists():
        print(f"refused: {args.out} exists", file=sys.stderr)
        return 2
    record = read(args.run_dir)
    put(args.out, record)
    print(json.dumps({"gate": record["gate"], "g2": record["g2"]}, sort_keys=True))
    return 0


def _terminate(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _terminate)
    raise SystemExit(main())
