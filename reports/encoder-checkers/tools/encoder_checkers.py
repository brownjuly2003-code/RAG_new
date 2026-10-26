"""The encoder checkers on saved answers: docs/specs/encoder-checkers.md, registered before the
first checker call; PLAN.md stage 3 and §8.3, item 13.

  python reports/encoder-checkers/tools/encoder_checkers.py parity OUT
  python reports/encoder-checkers/tools/encoder_checkers.py score CHECKER OUT
  python reports/encoder-checkers/tools/encoder_checkers.py record OUT

``parity`` (check 1) and ``score`` run on the Mac in the gate checkout, with the ML venv's
interpreter and the separate ``transformers`` of SITE; ``score`` writes OUT/scores-CHECKER.jsonl,
one checker a process, and resumes a stopped file. ``record`` reads OUT's rows anywhere and
writes OUT/record.json: per checker the threshold chosen on the calibration answers, the frozen
reading on the 80 classed aircargo answers, and beside them seconds, memory, AUROC, RU's catching
by type and the truncation counts; then the outcome. Rows hold ids, labels, scores, counts and
seconds, never a text.
"""

import ast
import csv
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(1, str(WS / "reports" / "handover-signal" / "tools"))
sys.path.insert(2, str(WS))
import signal_record  # noqa: E402
from stage2_common import load_jsonl, sha256  # noqa: E402

from scripts import chat_answer_judge as judge  # noqa: E402

SPEC = "docs/specs/encoder-checkers.md"
SITE = "/Users/julia/RAG_new_encoder_site"
CACHE = Path("/Users/julia/RAG_new_encoder_models")
RUNS = Path("/Users/julia/RAG_new_chat_4f48fed/chatlive/runs")
RUSHALLU = Path("/Users/julia/RAG_new_ext_rushallu/repo")
RUSHALLU_COMMIT = "345907f983da91e1b7720b5944d982ea9c9aeb83"
RUSHALLU_FILES = {"sberquad-rag": 200, "ruscibench-rag": 100}
PLAN = WS / "reports/handover-signal/d260d95/plan.json"
JUDGE = {
    "aircargo": WS / "reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl",
    "wixqa": WS / "reports/answer-prompt-v4/4f48fed/v4-wixqa-judge-m1.cases.jsonl",
    "conditionalqa": WS / "reports/answer-prompt-v4/4f48fed/v4-conditionalqa-judge-m1.cases.jsonl",
}
CHECKERS = {
    "H": {
        "repo": "Horizon-Labs/hallucination-guard-small",
        "revision": "7c015323d2a1f755de0a3aac62b729ecad6da607",
        "forecast_min": 30,
    },
    "L": {
        "repo": "KRLabsOrg/lettucedect-v2-mmbert-base",
        "revision": "8831ce063dff760b01efe4519b4188f5ee2456f2",
        "forecast_min": 30,
    },
    "N": {
        "repo": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
        "revision": "b5113eb38ab63efdd7f280f8c144ea8b13f978ce",
        "forecast_min": 80,
    },
}
SEED = 20261026
STOP_FACTOR = 3
MIN_GOOD, MIN_TARGET = 30, 15
OVER_SHARE = Fraction(1, 3)
PARITY_TOLERANCE = 0.01
THREADS = 4
H_MAX, L_MAX = 2048, 4096
N_MAX, N_WINDOW, N_SHARED, N_SENTENCE = 512, 400, 50, 300
GROUNDING = {"Contradiction", "Unconfirmed"}
SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")
WORD = re.compile(r"[^\W_]")
MARKS = re.compile(r"\s*" + judge.MARK.pattern)
NOT_EVIDENCE = "NOT_EVIDENCE"


# --- the rules, without a model -------------------------------------------------------------


def strip_marks(text):
    """The answer without its reference marks [n] and [n, m] and the spaces before them."""
    return MARKS.sub("", text)


def sentences(text):
    """The card's split after . ! ? and a space, and at line breaks; wordless pieces dropped."""
    return [piece.strip() for piece in SPLIT.split(text) if WORD.search(piece)]


def windows(count, size=N_WINDOW, shared=N_SHARED):
    """Token windows of at most SIZE covering COUNT tokens, each sharing SHARED with the next."""
    out, start = [], 0
    while start < count:
        end = min(start + size, count)
        out.append((start, end))
        if end == count:
            break
        start = end - shared
    return out


def judge_class(row):
    """The handover plan's classes: target - bad or a decline; good - good and not declining."""
    declined = row["answers_question"] == "declined"
    if row["grade"] == "bad" or declined:
        return "target"
    if row["grade"] == "good":
        return "good"
    return None


def rushallu_class(spans):
    """Good - the human labels hold only the type None; target - any other type."""
    types = {str(span.get("type")) for span in spans}
    named = types - {"None"}
    return (
        "target" if named else "good",
        {"grounding": bool(named & GROUNDING), "other": bool(named - GROUNDING)},
    )


def rushallu_sample(rows_by_file):
    """Each file's seeded shuffle, its first rows by RUSHALLU_FILES; then one shuffle of all."""
    picked = []
    for name, size in RUSHALLU_FILES.items():
        order = list(range(len(rows_by_file[name])))
        random.Random(SEED).shuffle(order)
        picked += [(name, index) for index in order[:size]]
    random.Random(SEED).shuffle(picked)
    return picked


def marks(score, threshold):
    return score is not None and threshold is not None and score < threshold


def threshold(rows):
    """S7's rule over the calibration answers, RU and EN weighing equally (the spec)."""
    classed = [row for row in rows if row["class"] in ("good", "target")]
    totals = {}
    for row in classed:
        key = (row["set"], row["class"])
        totals[key] = totals.get(key, 0) + 1
    halves = sorted({row["set"] for row in classed})

    def share(marked, cls):
        return sum(
            Fraction(sum(1 for row in marked if row["set"] == half and row["class"] == cls))
            / totals[(half, cls)]
            for half in halves
            if totals.get((half, cls))
        ) / len(halves)

    scores = sorted({row["score"] for row in classed if row["score"] is not None})
    best = None
    for candidate in scores:
        marked = [row for row in classed if marks(row["score"], candidate)]
        over, caught = share(marked, "good"), share(marked, "target")
        if over <= OVER_SHARE and (best is None or caught > best[1]):
            best = (candidate, caught, over)
    if best is None or best[1] == 0:
        return {"threshold": None, "candidates": len(scores)}
    return {
        "threshold": best[0],
        "candidates": len(scores),
        "caught_share": float(best[1]),
        "over_marked_share": float(best[2]),
    }


def counts(rows, cut):
    targets = [row for row in rows if row["class"] == "target"]
    goods = [row for row in rows if row["class"] == "good"]
    return {
        "caught": sum(1 for row in targets if marks(row["score"], cut)),
        "target": len(targets),
        "over_marked": sum(1 for row in goods if marks(row["score"], cut)),
        "good_not_declining": len(goods),
    }


def reading(rows, cut):
    """The handover plan's frozen reading of the marks on the classed reading answers."""
    entry = counts(rows, cut)
    entry["reading"] = "useless" if cut is None else signal_record.read(entry)
    return entry


def auroc(rows):
    """The chance a good answer scores above a target, ties a half; unscored answers left out."""
    goods = [row["score"] for row in rows if row["class"] == "good" and row["score"] is not None]
    targets = [
        row["score"] for row in rows if row["class"] == "target" and row["score"] is not None
    ]
    if not goods or not targets:
        return None
    wins = sum((g > t) + 0.5 * (g == t) for g in goods for t in targets)
    return wins / (len(goods) * len(targets))


def spread(values):
    if not values:
        return None
    values = sorted(values)
    p90 = statistics.quantiles(values, n=10)[-1] if len(values) > 1 else values[0]
    return {"n": len(values), "median": statistics.median(values), "p90": p90}


def checker_record(rows):
    """One checker's numbers from its score rows (the spec's threshold, reading and beside)."""
    starts = [row for row in rows if row["kind"] == "start"]
    start = starts[0]
    for key in ("tool_sha256", "weights_sha256", "inputs_sha256", "planned", "revision"):
        if any(row[key] != start[key] for row in starts):
            raise SystemExit(f"{start['checker']}: a resumed segment differs in {key}")
    answers = [row for row in rows if row["kind"] == "answer"]
    ends = [row for row in rows if row["kind"] == "end"]
    by_set = {
        name: [row for row in answers if row["set"] == name] for name in ("reading", "EN", "RU")
    }
    calibration = by_set["EN"] + by_set["RU"]
    short = [
        f"{half} {cls}"
        for half in ("EN", "RU")
        for cls, least in (("good", MIN_GOOD), ("target", MIN_TARGET))
        if sum(1 for row in by_set[half] if row["class"] == cls) < least
    ]
    whole = len(by_set["reading"]) == start["planned"]["reading"]
    cut = threshold(calibration)
    out = {
        "repo": start["repo"],
        "revision": start["revision"],
        "planned": start["planned"],
        "reached": {name: len(by_set[name]) for name in by_set},
        "segments": len(starts),
        "stopped": any(row["stopped"] for row in ends),
        "threshold": cut,
        "calibration": {half: counts(by_set[half], cut["threshold"]) for half in ("EN", "RU")},
        "reading": NOT_EVIDENCE
        if not whole or short
        else reading(by_set["reading"], cut["threshold"]),
        "not_evidence_because": ([] if whole else ["the reading set is not whole"]) + short,
        "auroc": {name: auroc(by_set[name]) for name in by_set},
        "ru_types": {
            group: {
                "target": sum(1 for row in by_set["RU"] if row.get("groups", {}).get(group)),
                "caught": sum(
                    1
                    for row in by_set["RU"]
                    if row.get("groups", {}).get(group) and marks(row["score"], cut["threshold"])
                ),
            }
            for group in ("grounding", "other")
        },
        "seconds": {name: spread([row["seconds"] for row in by_set[name]]) for name in by_set},
        "truncated": {name: sum(row["truncated"] for row in by_set[name]) for name in by_set},
        "unscored": {
            name: sum(1 for row in by_set[name] if row["score"] is None) for name in by_set
        },
        "peak_rss_bytes": max((row["peak_rss_bytes"] for row in ends), default=None),
        "load": [row["load"] for row in rows if row["kind"] in ("start", "end")],
        "seconds_total": sum(row["seconds"] for row in answers),
    }
    return out


def outcome(per_checker):
    """Worth wiring - the best of those; else NOT_EVIDENCE if any is; else in between; else none."""
    read = {name: entry["reading"] for name, entry in per_checker.items()}
    worth = [
        name
        for name, entry in read.items()
        if entry != NOT_EVIDENCE and entry["reading"] == "worth wiring"
    ]
    if worth:
        best = min(
            worth,
            key=lambda name: (
                -read[name]["caught"],
                read[name]["over_marked"],
                per_checker[name]["seconds"]["reading"]["median"],
            ),
        )
        return {"decision": f"worth wiring: {best}", "worth_wiring": best}
    missing = [name for name, entry in read.items() if entry == NOT_EVIDENCE]
    if missing:
        return {"decision": f"{NOT_EVIDENCE}: {', '.join(missing)}", "worth_wiring": None}
    between = [name for name, entry in read.items() if entry["reading"] == "in between"]
    if between:
        return {"decision": f"in between: {', '.join(between)}", "worth_wiring": None}
    return {"decision": "none worth wiring", "worth_wiring": None}


# --- the inputs, on the Mac ------------------------------------------------------------------


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def v4_answers(base):
    """Every answer of the base's V4 runs, by (run, case), with its documents and digests."""
    found = {}
    for run in sorted(RUNS.glob(f"v4-{base}-b??")):
        if not run.is_dir():
            continue
        for answer in judge.run_answers(run):
            key = (run.name, answer["case_id"])
            if key in found:
                raise SystemExit(f"{key}: two answers")
            found[key] = answer
    return found


def item(set_name, base, key, cls, answer, documents):
    return {
        "set": set_name,
        "base": base,
        "id": "/".join(key),
        "class": cls,
        "answer": strip_marks(answer),
        "documents": documents,
    }


def inputs():
    """The spec's answers in its order: the reading set, EN, then RU's seeded sample."""
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    out = []
    judged = {}
    for base, path in JUDGE.items():
        judged[base] = {(row["run"], row["case_id"]): row for row in load_jsonl(path)}
    found = v4_answers("aircargo")
    if len(plan["items"]) != len(judged["aircargo"]):
        raise SystemExit("the plan and the aircargo judge differ in size")
    for entry in plan["items"]:
        key = (entry["run"], entry["case_id"])
        answer, row = found[key], judged["aircargo"][key]
        if row["missing"] or not (
            answer["prompt_sha256"] == entry["prompt_sha256"] == row["prompt_sha256"]
            and digest(answer["answer"]) == entry["answer_sha256"]
        ):
            raise SystemExit(f"{key}: the run record is not the plan's or the judge's")
        texts = [body for _, body in answer["documents"]]
        out.append(item("reading", "aircargo", key, judge_class(row), answer["answer"], texts))
    for base in ("wixqa", "conditionalqa"):
        found = v4_answers(base)
        for key in sorted(judged[base]):
            row = judged[base][key]
            cls = judge_class(row)
            if cls is None:
                continue
            answer = found[key]
            if answer["prompt_sha256"] != row["prompt_sha256"] or row["missing"]:
                raise SystemExit(f"{key}: the judge graded another answer, or none")
            texts = [body for _, body in answer["documents"]]
            out.append(item("EN", base, key, cls, answer["answer"], texts))
    rows_by_file = rushallu_rows()
    for name, index in rushallu_sample(rows_by_file):
        row = rows_by_file[name][index]
        cls, groups = rushallu_class(json.loads(row["answer"]))
        entry = item(
            "RU",
            name,
            (name, row["query_id"]),
            cls,
            row["model_output"],
            [doc["doc_text"] for doc in ast.literal_eval(row["docs"])],
        )
        entry["groups"] = groups
        out.append(entry)
    return out


def rushallu_paths():
    return {
        name: RUSHALLU / "results/annotation/human/merged" / f"{name}.csv"
        for name in RUSHALLU_FILES
    }


def rushallu_rows():
    csv.field_size_limit(10**9)
    out = {}
    for name, path in rushallu_paths().items():
        with open(path, encoding="utf-8", newline="") as handle:
            out[name] = list(csv.DictReader(handle))
    return out


def input_hashes():
    return {
        "plan": sha256(PLAN),
        **{f"judge {base}": sha256(path) for base, path in JUDGE.items()},
        **{f"rushallu {name}": sha256(path) for name, path in rushallu_paths().items()},
    }


# --- the checkers, on the Mac ----------------------------------------------------------------


def snapshot(name):
    spec = CHECKERS[name]
    return CACHE / f"models--{spec['repo'].replace('/', '--')}" / "snapshots" / spec["revision"]


def load(name):
    """The checker's tokenizer and model, fp32 on the CPU; ModernBERT's rope bases from its file."""
    import torch
    import transformers

    torch.set_num_threads(THREADS)
    path = snapshot(name)
    stored = json.loads((path / "config.json").read_text(encoding="utf-8"))
    extra = {}
    if stored["model_type"] == "modernbert":
        rope = stored["rope_parameters"]
        extra = {
            "global_rope_theta": rope["full_attention"]["rope_theta"],
            "local_rope_theta": rope["sliding_attention"]["rope_theta"],
        }
    config = transformers.AutoConfig.from_pretrained(path, **extra)
    if stored["model_type"] == "modernbert":
        every = config.global_attn_every_n_layers
        expected = [
            "full_attention" if index % every == 0 else "sliding_attention"
            for index in range(config.num_hidden_layers)
        ]
        if (
            stored["layer_types"] != expected
            or config.global_rope_theta != extra["global_rope_theta"]
            or config.local_rope_theta != extra["local_rope_theta"]
            or config.local_attention != stored["local_attention"]
        ):
            raise SystemExit(f"{name}: the loaded config is not the file's")
    kind = (
        transformers.AutoModelForTokenClassification
        if name == "L"
        else transformers.AutoModelForSequenceClassification
    )
    model = kind.from_pretrained(path, config=config, torch_dtype=torch.float32).eval()
    tokenizer = transformers.AutoTokenizer.from_pretrained(path)
    return tokenizer, model


def _probs(model, ids, mask):
    import torch

    with torch.inference_mode():
        logits = model(input_ids=ids, attention_mask=mask).logits
    return torch.softmax(logits.float(), dim=-1)


def score_h(tokenizer, model, documents, text):
    source = "\n\n".join(documents)
    label = model.config.label2id["SUPPORTED"]
    found, tokens, cut = [], 0, 0
    for sentence in sentences(text):
        full = len(tokenizer(source, sentence)["input_ids"])
        cut += full > H_MAX
        enc = tokenizer(source, sentence, truncation=True, max_length=H_MAX, return_tensors="pt")
        tokens += enc["input_ids"].shape[1]
        probs = _probs(model, enc["input_ids"], enc["attention_mask"])
        found.append(float(probs[0, label]))
    return (min(found) if found else None), len(found), tokens, cut


def score_l(tokenizer, model, documents, text):
    if not sentences(text):
        return None, 0, 0, 0
    context = "\n\n".join(documents)
    label = model.config.label2id["hallucinated"]
    full = len(tokenizer(context, text)["input_ids"])
    enc = tokenizer(
        context,
        text,
        truncation="only_first",
        max_length=L_MAX,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    probs = _probs(model, enc["input_ids"], enc["attention_mask"])
    offsets = enc["offset_mapping"][0].tolist()
    picked = [
        float(probs[0, index, label])
        for index, (sid, (a, b)) in enumerate(zip(enc.sequence_ids(0), offsets, strict=True))
        if sid == 1 and a != b
    ]
    if not picked:
        return None, 0, enc["input_ids"].shape[1], int(full > L_MAX)
    return 1.0 - max(picked), len(picked), enc["input_ids"].shape[1], int(full > L_MAX)


def score_n(tokenizer, model, documents, text):
    import torch

    label = model.config.label2id["entailment"]
    premises = [tokenizer(doc, add_special_tokens=False)["input_ids"] for doc in documents]
    found, units, tokens, cut = [], 0, 0, 0
    for sentence in sentences(text):
        hypothesis = tokenizer(sentence, add_special_tokens=False)["input_ids"]
        if len(hypothesis) > N_SENTENCE:
            hypothesis, cut = hypothesis[:N_SENTENCE], cut + 1
        size = min(N_WINDOW, N_MAX - 3 - len(hypothesis))
        pairs = [
            tokenizer.build_inputs_with_special_tokens(ids[a:b], hypothesis)
            for ids in premises
            for a, b in windows(len(ids), size)
        ]
        if not pairs:
            continue
        width = max(len(pair) for pair in pairs)
        pad = tokenizer.pad_token_id
        ids = torch.tensor([pair + [pad] * (width - len(pair)) for pair in pairs])
        mask = torch.tensor([[1] * len(pair) + [0] * (width - len(pair)) for pair in pairs])
        probs = _probs(model, ids, mask)
        found.append(float(probs[:, label].max()))
        units += len(pairs)
        tokens += sum(len(pair) for pair in pairs)
    return (min(found) if found else None), units, tokens, cut


SCORERS = {"H": score_h, "L": score_l, "N": score_n}


def peak_rss():
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS


def git_head():
    done = subprocess.run(
        ["git", "-C", str(WS), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or None


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def score(name, out):
    """Score the spec's answers in its order; stop at three times the forecast, resume a file."""
    import torch
    import transformers

    out.mkdir(parents=True, exist_ok=True)
    path = out / f"scores-{name}.jsonl"
    rows = load_jsonl(path)
    done = {row["id"] for row in rows if row["kind"] == "answer"}
    spent = sum(row["seconds"] for row in rows if row["kind"] == "answer")
    if any(row["kind"] == "end" and row["stopped"] for row in rows):
        raise SystemExit(f"{path} stopped by the rule; it is not resumed")
    todo = inputs()
    planned = {
        name_: sum(1 for x in todo if x["set"] == name_) for name_ in ("reading", "EN", "RU")
    }
    weights = snapshot(name) / "model.safetensors"
    start = {
        "kind": "start",
        "checker": name,
        **{key: CHECKERS[name][key] for key in ("repo", "revision", "forecast_min")},
        "weights_sha256": sha256(weights),
        "spec": SPEC,
        "tool_sha256": sha256(Path(__file__)),
        "measured_at_head": git_head(),
        "inputs": input_hashes(),
        "inputs_sha256": digest(json.dumps(todo, ensure_ascii=False, sort_keys=True)),
        "rushallu_commit": RUSHALLU_COMMIT,
        "planned": planned,
        "resumed_after": len(done),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "threads": THREADS,
        "load": list(os.getloadavg()),
        "at": now(),
    }
    tokenizer, model = load(name)
    scorer = SCORERS[name]
    stopped = False
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(start, ensure_ascii=False) + "\n")
        for entry in todo:
            if entry["id"] in done:
                continue
            if spent > STOP_FACTOR * 60 * CHECKERS[name]["forecast_min"]:
                stopped = True
                break
            began = time.perf_counter()
            if entry["documents"]:
                value, units, tokens, cut = scorer(
                    tokenizer, model, entry["documents"], entry["answer"]
                )
            else:
                value, units, tokens, cut = None, 0, 0, 0
            seconds = time.perf_counter() - began
            spent += seconds
            row = {
                "kind": "answer",
                "set": entry["set"],
                "base": entry["base"],
                "id": entry["id"],
                "class": entry["class"],
                "score": value,
                "sentences": len(sentences(entry["answer"])),
                "units": units,
                "tokens": tokens,
                "truncated": cut,
                "seconds": round(seconds, 3),
            }
            if "groups" in entry:
                row["groups"] = entry["groups"]
            handle.write(json.dumps(row) + "\n")
            handle.flush()
        handle.write(
            json.dumps(
                {
                    "kind": "end",
                    "stopped": stopped,
                    "seconds_spent": round(spent, 1),
                    "peak_rss_bytes": peak_rss(),
                    "load": list(os.getloadavg()),
                    "at": now(),
                }
            )
            + "\n"
        )
    print(path, "stopped" if stopped else "whole", round(spent / 60, 1), "min")


# --- check 1: the loading path ----------------------------------------------------------------

SHORT = {
    "ru": [
        (
            "Пекарня на Садовой улице работает с восьми утра до восьми вечера, по воскресеньям "
            "выходной. Хлеб привозят дважды в день.",
            "По воскресеньям пекарня не работает.",
        ),
        (
            "Пекарня на Садовой улице работает с восьми утра до восьми вечера, по воскресеньям "
            "выходной. Хлеб привозят дважды в день.",
            "Пекарня открыта до десяти вечера.",
        ),
        (
            "Абонемент в бассейн стоит три тысячи рублей в месяц и включает двенадцать посещений.",
            "Абонемент даёт двенадцать посещений в месяц.",
        ),
    ],
    "en": [
        (
            "The museum opens at 10 a.m. and closes at 6 p.m.; tickets cost 12 euros, children "
            "enter free.",
            "Children do not pay for entry.",
        ),
        (
            "The museum opens at 10 a.m. and closes at 6 p.m.; tickets cost 12 euros, children "
            "enter free.",
            "The museum closes at 9 p.m.",
        ),
        (
            "A parcel of up to 2 kg ships in three working days; heavier parcels take five.",
            "A 4 kg parcel ships in five working days.",
        ),
    ],
}


def long_source(language):
    if language == "ru":
        line = "Склад номер {i} открыт с {h} до {e} часов, его площадь {a} квадратных метров."
    else:
        line = "Warehouse {i} opens at {h}:00, closes at {e}:00 and holds {a} pallets."
    return " ".join(
        line.format(i=i, h=6 + i % 5, e=15 + i % 6, a=100 + 37 * i) for i in range(1, 61)
    )


def parity_pairs():
    pairs = [pair for language in ("ru", "en") for pair in SHORT[language]]
    claims = {
        "ru": [
            "Склад номер 37 открыт с 8 до 16 часов.",
            "Склад номер 12 открыт круглосуточно.",
            "Площадь склада номер 50 составляет 1950 квадратных метров.",
        ],
        "en": [
            "Warehouse 37 opens at 8:00.",
            "Warehouse 12 is open around the clock.",
            "Warehouse 50 holds 1950 pallets.",
        ],
    }
    for language in ("ru", "en"):
        pairs += [(long_source(language), claim) for claim in claims[language]]
    return pairs


def parity(out):
    """Check 1: H's and N's PyTorch path against their authors' ONNX exports; L's config."""
    import numpy
    import onnxruntime

    out.mkdir(parents=True, exist_ok=True)
    found = {"pairs": len(parity_pairs()), "onnxruntime": onnxruntime.__version__}
    ok = True
    for name, most in (("H", H_MAX), ("N", N_MAX)):
        tokenizer, model = load(name)
        onnx = snapshot(name) / "onnx" / "model.onnx"
        session = onnxruntime.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
        names = {node.name for node in session.get_inputs()}
        worst, same, lengths = 0.0, True, []
        for source, claim in parity_pairs():
            enc = tokenizer(source, claim, truncation=True, max_length=most, return_tensors="pt")
            lengths.append(int(enc["input_ids"].shape[1]))
            torch_probs = _probs(model, enc["input_ids"], enc["attention_mask"])[0].numpy()
            feed = {key: enc[key].numpy().astype(numpy.int64) for key in enc if key in names}
            logits = session.run(None, feed)[0][0].astype(numpy.float64)
            onnx_probs = numpy.exp(logits - logits.max())
            onnx_probs /= onnx_probs.sum()
            worst = max(worst, float(numpy.abs(torch_probs - onnx_probs).max()))
            same = same and int(torch_probs.argmax()) == int(onnx_probs.argmax())
        passed = worst <= PARITY_TOLERANCE and same
        ok = ok and passed
        found[name] = {
            "onnx_sha256": sha256(onnx),
            "max_abs_difference": worst,
            "same_top_label": same,
            "tokens": [min(lengths), max(lengths)],
            "passed": passed,
        }
        del model
    load("L")  # raises when the loaded config is not the file's
    found["L"] = {"config_matches_file": True}
    found["passed"] = ok
    found["tool_sha256"] = sha256(Path(__file__))
    found["measured_at_head"] = git_head()
    (out / "parity.json").write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(found, indent=1))
    if not ok:
        raise SystemExit("check 1 failed: the PyTorch path is not the authors' export")


# --- the record --------------------------------------------------------------------------------


def record(out):
    per_checker = {}
    for name in CHECKERS:
        rows = load_jsonl(out / f"scores-{name}.jsonl")
        if not rows:
            raise SystemExit(f"no scores of {name}")
        per_checker[name] = checker_record(rows)
    parity_found = json.loads((out / "parity.json").read_text(encoding="utf-8"))
    result = {
        "spec": SPEC,
        "tool_sha256": sha256(Path(__file__)),
        "parity": parity_found,
        "checkers": per_checker,
        **outcome(per_checker),
    }
    (out / "record.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(result["decision"])
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["parity"] and len(argv) == 2:
        sys.path.insert(0, SITE)
        parity(Path(argv[1]))
    elif argv[:1] == ["score"] and len(argv) == 3 and argv[1] in CHECKERS:
        sys.path.insert(0, SITE)
        score(argv[1], Path(argv[2]))
    elif argv[:1] == ["record"] and len(argv) == 2:
        record(Path(argv[1]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
