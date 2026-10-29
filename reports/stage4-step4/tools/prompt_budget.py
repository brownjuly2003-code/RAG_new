"""Stage 4, step 4: a shorter prompt - num_ctx below 4,096, read at «sent» on stage 2's lists.

docs/specs/stage4-step4-prompt-budget.md, registered with this tool before the count; PLAN.md
stage 4, item 4. Reads what the K curve read, through the no-reranker point's tool (its
loading, checks, expansion and exact McNemar): stage 2's retrieval records of stand 5e308fe and
the bases' chunk archives on the Mac, the committed export of the same runs, and V4's committed
answer rows; no model:

  python reports/stage4-step4/tools/prompt_budget.py RUNS DATA_ROOT [OUT]
  e.g. ... /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1

For each window - num_ctx, the setting OLLAMA_CONTEXT_WINDOW - and every question, the
product's own fitting of the answer prompt on the recorded documents: the product's
HybridRetriever._expand_parents over the chunk archive on the recorded five, then
api.routers.conversation._fit_stream_prompt with an owner of that context_window, the question
and no history, under the code's answer prompt (QA_PROMPT_V4). Per question with gold, stage
2's reading at «sent» (retrieval_summary.coverage); each window below 4,096 against 4,096, per
base and pooled.

The tool stops and writes nothing when the expansion is not the recorded one, when stage 2's
answer prompt (QA_PROMPT_V3, agent/prompts.py at 5e308fe) at 4,096 does not give each record's
sent documents and prompt, when the code's prompt at 4,096 is not the prompt V4's run sent on a
question where V4 retrieved what the record holds, or when stage 2's reading at «sent», read
again, is not the export's. A question whose «sent» point cannot be read at some window is left
out of every window; more than MAX_UNREAD such questions on a base make its comparison
NOT_EVIDENCE.

Writes OUT/record.json (provenance, the checks, the pairs, the reading) and OUT/rows.jsonl (one
question a line: ids, flags, numbers); stage2_common.without_text refuses either when a string
of it names a document of the base or holds a question.
"""

import ast
import functools
import hashlib
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "no-rerank" / "tools"))
import no_rerank_point as nr  # noqa: E402
import retrieval_summary  # noqa: E402
from retrieval_summary import position  # noqa: E402
from stage2_common import load_jsonl, sha256, spread, without_text  # noqa: E402

SPEC = "docs/specs/stage4-step4-prompt-budget.md"
# num_ctx in steps of 256 down from today's; a window's input limit is window_input_limit(w, 1024).
WINDOWS = (4096, 3840, 3584, 3328, 3072, 2816, 2560, 2304)
TODAY = WINDOWS[0]
OUTPUT_BUDGET = 1024
MAX_UNREAD = 5
NOT_EVIDENCE = nr.NOT_EVIDENCE
OUT = WS / "reports" / "stage4-step4" / "5e308fe"
V4_ROWS = WS / "reports" / "answer-prompt-v4" / "4f48fed"
V4_BASES = ("aircargo", "wixqa", "conditionalqa")
STAGE2_PROMPT_ID = "QA_PROMPT_V3"
CODE_PROMPT_ID = "QA_PROMPT_V4"
MEASURE_CODE = (
    *nr.MEASURE_CODE,
    "reports/no-rerank/tools/no_rerank_point.py",
    "api/routers/conversation.py",
    "agent/context_window.py",
    "agent/prompts.py",
    "agent/prompt_registry.py",
    "llm/providers/base.py",
    "llm/role_params.py",
)
# The no-reranker point's pair names its sides by its two points; here they are 4,096 and w.
RENAMED = {"b_reranker_only": "b_today_only", "c_fused_only": "c_window_only"}


def input_limit(window):
    from llm.providers.base import window_input_limit

    return window_input_limit(window, OUTPUT_BUDGET)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def registry_of(source):
    """The PROMPT_REGISTRY of agent/prompts.py's source, read as a literal, never run."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        else:
            continue
        if isinstance(target, ast.Name) and target.id == "PROMPT_REGISTRY":
            return ast.literal_eval(node.value)
    raise SystemExit("agent/prompts.py holds no PROMPT_REGISTRY")


def stage2_prompt():
    """The answer prompt stage 2's stand sent: agent/prompts.py at its commit."""
    shown = subprocess.run(
        ["git", "-C", str(WS), "show", f"{nr.CODE_SHA}:agent/prompts.py"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    qa = registry_of(shown)["qa"]
    if qa["prompt_id"] != STAGE2_PROMPT_ID:
        raise SystemExit(f"stage 2's answer prompt is {qa['prompt_id']}, not {STAGE2_PROMPT_ID}")
    return qa["text"]


def code_prompt():
    """The code's answer prompt as the chat resolves it, with no override of any kind, and the
    answer's output budget the window leaves room for."""
    from agent.prompt_registry import get_prompt
    from agent.prompts import PROMPT_REGISTRY
    from llm.role_params import generation_kwargs_for_role

    qa = PROMPT_REGISTRY["qa"]
    if qa["prompt_id"] != CODE_PROMPT_ID or get_prompt("qa") != qa["text"]:
        raise SystemExit(f"the chat's answer prompt is not the code's {CODE_PROMPT_ID}")
    if int(generation_kwargs_for_role("generate")["max_tokens"]) != OUTPUT_BUDGET:
        raise SystemExit(f"the answer's output budget is not {OUTPUT_BUDGET}")
    return qa["text"]


@contextmanager
def answer_prompt(text):
    """The calls inside resolve the answer prompt to text, by the product's own override:
    agent.prompt_registry.get_prompt reads CURRENT_EXPERIMENT's prompt_overrides first."""
    from agent.prompt_registry import CURRENT_EXPERIMENT

    token = CURRENT_EXPERIMENT.set(SimpleNamespace(prompt_overrides={"qa": text}))
    try:
        yield
    finally:
        CURRENT_EXPERIMENT.reset(token)


def fit(window, question, plain):
    """The chat's fitting of a first question's answer prompt at num_ctx = window: the prompt
    as the provider flattens it, and the documents it holds."""
    from api.routers.conversation import _fit_stream_prompt
    from llm.providers.base import flatten_messages

    owner = SimpleNamespace(context_window=window)
    prompt, fitted = _fit_stream_prompt(owner, question, plain, [])
    return flatten_messages([{"role": "user", "content": prompt}]), fitted


def sent(fitted, plain):
    """The documents of a fitted prompt as stage 2's records hold them."""
    return [
        {
            "source": d["metadata"].get("source"),
            "chunk_index": d["metadata"].get("chunk_index"),
            "text": d["page_content"],
            "cut": d["page_content"] != plain[i]["page_content"],
        }
        for i, d in enumerate(fitted)
    ]


class Documents(nr.Expansion):
    """The no-reranker point's expansion, giving the product's documents themselves, with the
    metadata the fitting reads: the source of a document's label, a chunk's header."""

    def documents(self, members):
        import config.settings as config

        # _expand_parents reads the chunk overlap from get_settings() when it is called.
        real = config.get_settings
        config.get_settings = lambda: SimpleNamespace(chunk_overlap=self.overlap)
        try:
            return self.retriever._expand_parents([self.docs[m] for m in members])
        finally:
            config.get_settings = real


class Base:
    """What one base's questions share: its run's settings, its documents' texts, the two
    answer prompts and V4's rows."""

    def __init__(self, base, settings, root, prompts, v4):
        self.settings = settings
        self.stage2, self.code = prompts
        self.v4 = v4
        self.expansion = None
        self.sources = None
        if base in nr.METRICS and base != "wixqa":
            from scripts import external_base

            self.sources = external_base._corpus(root / base)[1]

    def documents(self, chunks, members):
        if self.expansion is None:
            self.expansion = Documents(chunks, self.settings)
        return self.expansion.documents(members)


def same_retrieval(record, v4):
    """Whether V4's run retrieved what the record holds, by what its row keeps: the five's
    scores to six places and the expanded characters."""
    scores = [round(float(r[2]), 6) for r in record["ranked"][: nr.TOP]]
    chars = sum(len(e["text"]) for e in record["expanded"])
    return scores == v4.get("ranked_scores") and chars == v4.get("expanded_chars")


def question(base, case, record, chunks, places, expand, at):
    """One question's row: at every window the documents and tokens sent and, with gold, the
    point at «sent». Stage 2's prompt and V4's are held to their records first. The no-reranker
    point's expand gives texts; the fitting needs the documents, which at gives."""
    from llm.providers.base import estimate_window_tokens

    case_id = record["case_id"]
    ranked = [position(r, chunks) for r in record["ranked"]][: nr.TOP]
    docs = at.documents(chunks, ranked)
    recorded = [
        {"metadata": {"chunk_index": e["chunk_index"]}, "text": e["text"]}
        for e in record["expanded"]
    ]
    if nr.described(docs) != recorded:
        raise SystemExit(f"{case_id}: the product's expansion is not the recorded one")
    plain = [{"page_content": d.page_content, "metadata": d.metadata or {}} for d in docs]
    asked = record["question"]
    with answer_prompt(at.stage2):
        flat, fitted = fit(TODAY, asked, plain)
    if sent(fitted, plain) != record["sent"] or digest(flat) != record["prompt"]["sha256"]:
        raise SystemExit(f"{case_id}: stage 2's prompt at {TODAY} is not the recorded one")
    v4 = None if at.v4 is None else at.v4.get(case_id)
    row = {
        "case_id": case_id,
        "base": base,
        "index": record["index"],
        "v4_same_retrieval": None if v4 is None else same_retrieval(record, v4),
        "v4_prompt_checked": False,
        "windows": [],
    }
    documents = {}
    with answer_prompt(at.code):
        for window in WINDOWS:
            flat, fitted = fit(window, asked, plain)
            documents[window] = sent(fitted, plain)
            if window == TODAY and row["v4_same_retrieval"]:
                if digest(flat) != v4["prompts"][0]["sha256"]:
                    raise SystemExit(f"{case_id}: the code's prompt at {TODAY} is not V4's run's")
                row["v4_prompt_checked"] = True
            row["windows"].append(
                {
                    "window": window,
                    "documents": len(fitted),
                    "cut": any(d["cut"] for d in documents[window]),
                    "chars": len(flat),
                    "est_tokens": estimate_window_tokens(flat),
                }
            )
    if case is None:
        return row
    stage2 = retrieval_summary.coverage(base, case, record, places, at.sources, chunks)
    if stage2["unresolved"] is not None:
        raise SystemExit(f"{case_id}: stage 2's points do not read, where the export read them")
    row.update(stratum=case.get("stratum"), unresolved=None)
    # ranked and expanded_ranked for no_rerank_point.recount, sent for this tool's.
    row["points"] = {
        "ranked": stage2["points"]["ranked"],
        "expanded_ranked": stage2["points"]["expanded"],
        "sent": stage2["points"]["sent"],
    }
    row["excerpt_pieces_missed"] = stage2["excerpt_pieces_missed"]
    for entry in row["windows"]:
        # «sent» reads the sent documents against the expanded ones; without the pool and the
        # lanes the reading skips the K curve, which no window moves.
        view = {**record, "sent": documents[entry["window"]], "pool": None, "lanes": None}
        got = retrieval_summary.coverage(base, case, view, places, at.sources, chunks)
        if got["unresolved"] is not None:
            row["unresolved"] = entry["window"]
            break
        entry["sent"] = got["points"]["sent"]
        entry["excerpt_pieces_missed"] = got["excerpt_pieces_missed"]
    return row


def recount(rows, committed):
    """Stage 2's point at «sent», read again from the record, is the export's."""
    for row in rows:
        if "points" not in row:
            continue
        exported = committed[row["case_id"]]
        if (row["points"]["sent"], row["excerpt_pieces_missed"]) != (
            exported["points"]["sent"],
            exported["excerpt_pieces_missed"],
        ):
            raise SystemExit(f"{row['case_id']}: «sent» read again differs from the export")


def v4_rows(base):
    if base not in V4_BASES:
        return None
    return {r["case_id"]: r for r in load_jsonl(V4_ROWS / f"v4-{base}.cases.jsonl")}


def base_rows(base, runs, root, manifest, prompts):
    """The no-reranker point's loading and checks of one base, with this step's rows."""
    label = nr.LABELS[base]
    settings = json.loads((runs / label / "effective_settings.json").read_text("utf-8"))["all"]
    at = Base(base, settings, root, prompts, v4_rows(base))
    # no_rerank_point.base_rows builds a row a question through its module's question(); this
    # step's row takes its place for the one call, and the loading and checks stay its own.
    original = nr.question
    nr.question = functools.partial(question, at=at)
    try:
        rows, provenance, names, questions = nr.base_rows(base, runs, root, manifest)
    finally:
        nr.question = original
    recount(rows, nr.export_rows(label, manifest))
    if base in V4_BASES:
        provenance["v4_rows_sha256"] = sha256(V4_ROWS / f"v4-{base}.cases.jsonl")
    return rows, provenance, names, questions


def at_window(row, window):
    """A row's entry at a window; a row holds them in the order of WINDOWS."""
    return row["windows"][WINDOWS.index(window)]


def renamed(got, names):
    return {names.get(key, key): value for key, value in got.items()}


def pair(rows, window):
    """The window against 4,096 at «sent», by each question's primary metric: the no-reranker
    point's pair, with b - gold at 4,096 only - and c - gold at the window only."""
    view = [
        {
            "base": r["base"],
            "points": {
                "today": at_window(r, TODAY)["sent"],
                "window": at_window(r, window)["sent"],
            },
        }
        for r in rows
    ]
    return renamed(nr.pair(view, "today", "window"), RENAMED)


def stage2_against_today(rows):
    """Stage 2's «sent» - QA_PROMPT_V3 at 4,096 - against the code's prompt at 4,096."""
    view = [
        {
            "base": r["base"],
            "points": {"stage2": r["points"]["sent"], "today": at_window(r, TODAY)["sent"]},
        }
        for r in rows
    ]
    names = {"b_reranker_only": "b_stage2_only", "c_fused_only": "c_today_only"}
    return renamed(nr.pair(view, "stage2", "today"), names)


def summary(base, rows):
    """A base's counts, each window's pair against 4,096 and what stands beside them."""
    out = {"questions": len(rows)}
    read, not_evidence = [], False
    if base in nr.METRICS:
        gold = [r for r in rows if "points" in r]
        read = [r for r in gold if r["unresolved"] is None]
        not_evidence = len(gold) - len(read) > MAX_UNREAD
        out.update(with_gold=len(gold), unresolved=len(gold) - len(read))
        out["stage2_against_today"] = stage2_against_today(read)
    if base in V4_BASES:
        out["v4"] = {
            "same_retrieval": sum(1 for r in rows if r["v4_same_retrieval"]),
            "prompts_checked": sum(1 for r in rows if r["v4_prompt_checked"]),
        }
    out["windows"] = []
    for window in WINDOWS:
        entries = [at_window(r, window) for r in rows]
        today = [at_window(r, TODAY)["est_tokens"] for r in rows]
        saved = [t - e["est_tokens"] for t, e in zip(today, entries, strict=True)]
        point = {
            "window": window,
            "input_limit": input_limit(window),
            "documents": spread([e["documents"] for e in entries]),
            "cut": sum(1 for e in entries if e["cut"]),
            "est_tokens": spread([e["est_tokens"] for e in entries]),
            "shorter": sum(1 for s in saved if s > 0),
            "est_tokens_saved": spread(saved),
        }
        if base in nr.METRICS:
            point["excerpt_pieces_missed"] = sum(
                at_window(r, window)["excerpt_pieces_missed"] for r in read
            )
            if window != TODAY:
                point["sent"] = NOT_EVIDENCE if not_evidence else pair(read, window)
        out["windows"].append(point)
    return out


def pooled_windows(rows, not_evidence):
    """Each window's pair over the three bases' questions read at every window."""
    read = [r for r in rows if "points" in r and r["unresolved"] is None]
    return [
        {"window": w, "sent": NOT_EVIDENCE if not_evidence else pair(read, w)} for w in WINDOWS[1:]
    ]


def decision(per_base, pooled):
    """The smallest window from which no window below 4,096 reads a loss, on any base or
    pooled."""
    curves = {**{base: got["windows"] for base, got in per_base.items()}, "pooled": pooled}
    at_sent = {
        where: {p["window"]: p["sent"] for p in curve if "sent" in p}
        for where, curve in curves.items()
    }
    if any(got == NOT_EVIDENCE for by_window in at_sent.values() for got in by_window.values()):
        return NOT_EVIDENCE
    losses = {
        where: [w for w in WINDOWS if w in by_window and by_window[w]["reading"] == "loss"]
        for where, by_window in at_sent.items()
    }
    lost = {w for found in losses.values() for w in found}
    smallest = TODAY
    for window in WINDOWS[1:]:
        if window in lost:
            break
        smallest = window
    return {
        "smallest_window_without_a_detected_loss": smallest,
        "its_input_limit": input_limit(smallest),
        "losses": losses,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    runs, root = Path(argv[0]), Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else OUT
    manifest = json.loads((nr.EXPORT / "manifest.json").read_text(encoding="utf-8"))
    if manifest["code_sha"] != nr.CODE_SHA:
        raise SystemExit("the export is not of the stand the records are")
    prompts = (stage2_prompt(), code_prompt())
    all_rows, provenance, bases, names, questions = [], {}, {}, set(), []
    for base in nr.LABELS:
        rows, provenance[base], held, asked = base_rows(base, runs, root, manifest, prompts)
        bases[base] = summary(base, rows)
        all_rows += rows
        names |= held
        questions += asked
        print(f"{base}: {len(rows)} questions", flush=True)
    per_base = {b: bases[b] for b in nr.METRICS}
    pooled = pooled_windows(
        [r for r in all_rows if r["base"] in nr.METRICS],
        any(got["unresolved"] > MAX_UNREAD for got in per_base.values()),
    )
    record = {
        "spec": SPEC,
        "stand_code_sha": nr.CODE_SHA,
        "measured_at_head": nr.git_head(),
        "inputs": {
            "runs": str(runs),
            "data_root": str(root),
            "export": str(nr.EXPORT.relative_to(WS)),
            "export_manifest_sha256": sha256(nr.EXPORT / "manifest.json"),
            "v4_rows": str(V4_ROWS.relative_to(WS)),
        },
        "tool_sha256": sha256(Path(__file__)),
        "measure_code_sha256": {n: sha256(WS / n) for n in MEASURE_CODE},
        "prompts": {
            "stage2": {"prompt_id": STAGE2_PROMPT_ID, "sha256": digest(prompts[0])},
            "code": {"prompt_id": CODE_PROMPT_ID, "sha256": digest(prompts[1])},
        },
        "output_budget": OUTPUT_BUDGET,
        "windows": [{"window": w, "input_limit": input_limit(w)} for w in WINDOWS],
        "provenance": provenance,
        "bases": bases,
        "pooled": pooled,
        "decision": decision(per_base, pooled),
    }
    without_text(record, names, questions)
    without_text(all_rows, names, questions)
    out.mkdir(parents=True, exist_ok=True)
    (out / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8"
    )
    for where, curve in [*((b, got["windows"]) for b, got in per_base.items()), ("pooled", pooled)]:
        for point in curve:
            got = point.get("sent")
            if isinstance(got, dict):
                print(
                    f"{where} w={point['window']}: {got['hits']['today']} at {TODAY}, "
                    f"{got['hits']['window']} at w, b {got['b_today_only']}, "
                    f"c {got['c_window_only']}, p {got['p']}, {got['reading']}"
                )
    print(json.dumps({"decision": record["decision"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
