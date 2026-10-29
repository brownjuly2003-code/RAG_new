"""Stage 4's step 3: the record read again with the committed reader; its gates, its stand, its
questions and its privacy (docs/specs/stage4-step3-k-timing.md, «Records»). Every table row of
docs/evidence/stage4-step3-record.md is built from the record, and so is every number of its
prose that a test below pins."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import statistics
import sys
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step3" / "tools"
RECORDS = ROOT / "reports" / "stage4-step3" / "4f48fed"
SPEC = ROOT / "docs" / "specs" / "stage4-step3-k-timing.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step3-record.md"
CASES_FILE = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
K_CURVE = ROOT / "reports" / "k-curve" / "5e308fe"
# the drivers each run ran, two levels above it, as committed
DRIVERS = {
    "live_api.py": ROOT / "reports" / "stage2" / "tools" / "live_api.py",
    "live_retrieval.py": ROOT / "reports" / "stage2" / "tools" / "live_retrieval.py",
    "live_supervisor.py": ROOT / "reports" / "stage4-step1" / "tools" / "live_supervisor.py",
    "stage2_common.py": ROOT / "reports" / "stage2" / "tools" / "stage2_common.py",
}
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
# the files as copied from the Mac, by their SHA-256, which the Mac's copies matched
FILES = {
    "step3.json": "efdbdedcfc607b87792a3f342653a30256edbec5c973f25522af72bab5b70e34",
    "s3-k20-1.step3.json": "e2061a05da5665f7d7fee6d513ae352a8db2b0fe01662a3d79bc4bd61b740ada",
    "s3-k14-1.step3.json": "717b82068fc99e018e2ef0de4956ff342b8e008937c0ea4c7e9aa63c0510b2cc",
    "s3-k14-2.step3.json": "836e08c145ec9bc44a3dfc801a2b66a69e5d5931e047b374653bf54fc02c7e23",
    "s3-k20-2.step3.json": "97f61a28c152aeae533836ef07243bd51033fb92f6c79671cff8c7178dad8fc4",
    "s3-k20-1.q1.step3.json": "92fc29edd3b73262aedf4cef46d62ad82d7d3b9ab078491b6f78c9b3f564fe7a",
}
GATE = ("launch", "settings", "drivers", "asks", "summary")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("step3_reader_record", TOOLS / "step3_reader.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["step3_reader_record"] = module
    spec.loader.exec_module(module)
    return module


reader = _load()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


record = _json(RECORDS / "step3.json")
own = {label: _json(RECORDS / f"{label}.step3.json") for label in reader.RUNS}
q1 = _json(RECORDS / "s3-k20-1.q1.step3.json")
v4 = _json(V4 / "v4-aircargo.json")["provenance"]
k_curve = _json(K_CURVE / "record.json")
# the K curve's points of aircargo's questions, by K: the candidates and how many of the five
# kept are K = 20's
curve = {
    row["case_id"]: {point["k"]: point for point in row["curve"]}
    for row in _lines(K_CURVE / "rows.jsonl")
    if row["base"] == "aircargo"
}
runs = {run["label"]: run for run in record["runs"]}
pairs = record["pairs"]
K20 = [label for label, k in reader.RUNS.items() if k == 20]
K14 = [label for label, k in reader.RUNS.items() if k == 14]


def fmt(value: float) -> str:
    return f"{value:.3f}"


def mid(values: list[float]) -> float:
    return round(statistics.median(values), 3)


def at(position: int, k: int, key: str) -> set[Any]:
    """One field of a question's asks at one K, over both runs of that K."""
    return {run["asks"][position - 1][key] for run in runs.values() if run["k"] == k}


def same_five(position: int) -> bool:
    """The five kept at K = 14 are K = 20's, in K = 20's order, by SHA-256."""
    return at(position, 20, "ranked_sha256") == at(position, 14, "ranked_sha256")


def curve_five(case: str) -> int:
    """How many of the five the K curve kept at K = 14 are K = 20's."""
    return int(curve[case][14]["same_five"])


def only(values: set[Any]) -> Any:
    (value,) = values
    return value


def candidates_ratio(pair: dict[str, Any]) -> float:
    """The pool at K = 14 over the pool at K = 20."""
    (k14,), (k20,) = pair["k14_pool"], pair["k20_pool"]
    return float(k14 / k20)


def run_total(run: dict[str, Any]) -> float:
    """The retriever's build and the thirteen retrievals' walls, in seconds."""
    return float(run["retriever_build_sec"] + sum(ask["retrieval"] for ask in run["asks"]))


def against(label: str) -> tuple[int, float, float, float, float]:
    """K = 14 against one K = 20 run alone (mine, no rule of the spec): the questions below
    it, the median saving and ratio, and the ratio's lowest and highest."""
    i = K20.index(label)
    savings, ratios = [], []
    for pair in pairs:
        k14 = statistics.fmean(pair["k14_rerank"])
        k20 = pair["k20_rerank"][i]
        savings.append(k20 - k14)
        ratios.append(k14 / k20)
    below = sum(1 for value in savings if value > 0)
    return below, mid(savings), mid(ratios), min(ratios), max(ratios)


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_record_was_read_by_the_reader_and_the_drivers_the_spec_lists() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert len(listed) == 6
    for path, digest in listed.items():
        assert sha(ROOT / path) == digest, path
    tools = {"step3_reader.py": listed["reports/stage4-step3/tools/step3_reader.py"]}
    assert (reader.SCHEMA, reader.CODE_SHA, reader.SPEC) == (
        "stage4-step3/v1",
        CODE_SHA,
        SPEC.relative_to(ROOT).as_posix(),
    )
    for read in (record, *own.values(), q1):
        assert (read["schema"], read["spec"], read["tools_sha256"]) == (
            reader.SCHEMA,
            reader.SPEC,
            tools,
        )
    drivers = {name: listed[path.relative_to(ROOT).as_posix()] for name, path in DRIVERS.items()}
    assert drivers == reader.DRIVERS_SHA256
    # V4's own live_api.py and stage2_common.py; the supervisor is step 1's copy
    for name in ("live_api.py", "stage2_common.py"):
        assert drivers[name] == v4["tools_sha256"][name], name
    for run in (*record["runs"], *q1["runs"]):
        assert run["drivers_sha256"] == drivers, run["label"]


def test_the_pairs_and_the_readings_are_read_again_from_the_asks() -> None:
    for read in (record, *own.values(), q1):
        again = reader.pair_up(read["runs"])
        assert again == read["pairs"]
        assert reader.readings(again) == read["readings"]
    # a side lists its K's asks in the runs' order, ABBA
    assert [pair["case_id"] for pair in pairs] == list(reader.PAIRED)
    for pair in pairs:
        assert (pair["readable"], pair["why"]) == (True, []), pair["case_id"]
        for k, labels in ((20, K20), (14, K14)):
            asks = [runs[label]["asks"][pair["position"] - 1] for label in labels]
            assert pair[f"k{k}_rerank"] == [ask["rerank"] for ask in asks]


def test_each_runs_own_read_is_the_records_run() -> None:
    assert list(runs) == list(reader.RUNS)
    for label, read in own.items():
        assert read["runs"] == [runs[label]]
        got = read["readings"]
        assert (got["answer"], got["readable_questions"]) == (reader.NOT_EVIDENCE, 0)


def test_the_first_questions_read_is_run_ones_first_ask_taken_while_it_went_on() -> None:
    (run,) = q1["runs"]
    first = runs[K20[0]]
    assert run["asks"] == first["asks"][:1]
    assert run["asks"][0]["read"] is True
    assert run["gate"] == {
        **{key: key in ("settings", "drivers") for key in GATE},
        "passed": False,
    }
    assert run["notes"] == ["run: no readable retrieval-cpu.json"]
    # the launch file as the supervisor kept it while the run went on
    launch = run["launch"]
    assert (launch["status"], launch["variants"], "ollama_models_after" in launch) == (
        "running",
        {},
        False,
    )
    moved = ("status", "variants", "ollama_models_after")
    assert {key: value for key, value in launch.items() if key not in moved} == {
        key: value for key, value in first["launch"].items() if key not in moved
    }
    assert (run["label"], run["k"], run["settings"]) == (
        first["label"],
        first["k"],
        first["settings"],
    )
    assert run["sha256"]["effective_settings.json"] == first["sha256"]["effective_settings.json"]
    assert run["sha256"]["launch.json"] != first["sha256"]["launch.json"]
    assert (run["sha256"]["retrieval-cpu.json"], run["retriever_build_sec"]) == (None, None)
    assert q1["readings"]["answer"] == reader.NOT_EVIDENCE


def test_all_four_runs_pass_their_gates_on_all_five_points() -> None:
    for label, run in runs.items():
        k = reader.RUNS[label]
        assert run["k"] == k
        assert run["gate"] == {**dict.fromkeys(GATE, True), "passed": True}, label
        assert run["notes"] == [], label
        assert [ask["case_id"] for ask in run["asks"]] == list(reader.CASES)
        assert [ask["index"] for ask in run["asks"]] == list(range(1, len(reader.CASES) + 1))
        for ask in run["asks"]:
            assert (ask["read"], ask["unread"]) == (True, []), (label, ask["case_id"])
            assert (ask["rerank_status"], ask["reranker_ok"], ask["ranked"]) == ("ok", True, 5)
            # both lanes K long, and the rerank scored every merged candidate
            assert ask["lanes"] == {"vector": k, "bm25": k}, (label, ask["case_id"])
            assert ask["pool"] == ask["merged"], (label, ask["case_id"])
        assert run["sha256"].keys() == {
            "launch.json",
            "effective_settings.json",
            "retrieval-cpu.json",
        }
        assert all(re.fullmatch("[0-9a-f]{64}", digest) for digest in run["sha256"].values())


def test_the_stand_the_settings_and_the_questions_are_the_specs() -> None:
    # the record names no corpus: the stand's is V4's by the spec
    assert "corpus" not in record and "corpus" not in q1
    assert [run["k"] for run in runs.values()] == [20, 14, 14, 20]
    starts = [when(run["launch"]["started"]) for run in runs.values()]
    assert starts == sorted(starts)
    for label, run in runs.items():
        k, launch = run["k"], run["launch"]
        assert (launch["label"], launch["code_sha"], launch["mode"], launch["tenant"]) == (
            label,
            CODE_SHA,
            "retrieval",
            "aircargo",
        )
        assert (launch["status"], launch["variants"], launch["variant_order"]) == (
            "complete",
            {"cpu": 0},
            ["cpu"],
        )
        assert (launch["ollama_models_before"], launch["ollama_models_after"]) == ([], [])
        assert (launch["cases"], launch["client_cap_sec"]) == (list(reader.CASES), "1400")
        assert [launch["model"]] == v4["model"] == [MODEL]
        assert launch["k_override"] == ("14" if k == 14 else None)
        # V4's settings, K aside
        assert run["settings"] == {
            **{key: v4["settings"][key] for key in run["settings"]},
            "retrieval_top_k": k,
        }
    assert v4["settings"]["retrieval_top_k"] == 20
    assert [v4["code_sha"], v4["code"]["code_sha"]] == [[CODE_SHA], CODE_SHA]
    # the questions: the committed file's first thirteen, V4's and the K curve's file
    cases = [json.loads(line)["case_id"] for line in CASES_FILE.read_text("utf-8").splitlines()]
    assert cases[: len(reader.CASES)] == list(reader.CASES)
    digest = sha(CASES_FILE)
    assert digest == v4["cases_file_sha256"]
    assert digest == k_curve["provenance"]["aircargo"]["cases_file_sha256"]
    assert f"(`{digest[:8]}…`)" in SPEC.read_text(encoding="utf-8")


def test_the_live_pools_have_the_k_curves_counts_and_its_five_where_it_kept_all_five() -> None:
    assert {
        case: (curve[case][14]["candidates"], curve[case][20]["candidates"])
        for case in reader.CASES
    } == reader.K_CURVE_CANDIDATES
    for label, run in runs.items():
        for case, ask in zip(reader.CASES, run["asks"], strict=True):
            assert ask["pool"] == curve[case][run["k"]]["candidates"], (label, case)
    # both runs of a K reranked one pool and kept one five, and would send the same
    questions = list(enumerate(reader.CASES, start=1))
    for position, case in questions:
        for k in (20, 14):
            for key in ("pool_sha256", "ranked_sha256", "sent", "prompt_est_tokens"):
                assert len(at(position, k, key)) == 1, (case, k, key)
    kept = [case for position, case in questions if same_five(position)]
    assert kept == [case for case in reader.CASES if curve_five(case) == 5]
    assert len(kept) == 8 and {curve_five(case) for case in reader.CASES} == {4, 5}
    # what would be sent moved on one question alone
    moved = {
        case: [
            (only(at(position, k, "sent")), only(at(position, k, "prompt_est_tokens")))
            for k in (20, 14)
        ]
        for position, case in questions
        if any(
            at(position, 20, key) != at(position, 14, key) for key in ("sent", "prompt_est_tokens")
        )
    }
    assert moved == {"aircargo-matliab-disputed": [(4, 2636), (3, 2599)]}


HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
# the reader's note of a pair whose sides a lone run cannot fill
SIDE_NOTE = re.compile(r"[01] read asks at K = (?:14|20), not two")
WORDS = {
    # the record's schema and the spec's path, its enums, values and the reader's fixed note
    *("stage4-step3/v1", "docs/specs/stage4-step3-k-timing.md", "NOT_EVIDENCE", "faster"),
    *("retrieval", "aircargo", "complete", "running", "cpu", "ok", "14", "1400", MODEL),
    "run: no readable retrieval-cpu.json",
}


def strings(value: Any) -> Iterator[tuple[str, bool]]:
    """Every string of a parsed file, keys too, each with whether it is a key."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, True
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value, False


def test_the_record_holds_numbers_ids_enums_and_hashes_only() -> None:
    ids = set(reader.RUNS) | set(reader.CASES)
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        assert "/Users/" not in text, name
        for value, key in strings(_json(RECORDS / name)):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            shapes = (HEX, TIME, SIDE_NOTE)
            known = value in WORDS or value in ids or any(s.fullmatch(value) for s in shapes)
            assert known, (name, value)


def test_the_readings_against_the_forecast() -> None:
    got = record["readings"]
    assert (got["answer"], got["readable_questions"]) == ("faster", 12)
    assert (got["k14_faster"], got["k14_slower"], got["sign_p"]) == (12, 0, 0.000488)
    # with twelve readable questions faster needed ten: the spec's p = 0.039
    assert reader.sign_p(10, 2) < reader.ALPHA <= reader.sign_p(9, 3)
    assert round(reader.sign_p(10, 2), 3) == 0.039
    assert (got["median_rerank_saving_sec"], got["median_rerank_ratio"]) == (14.566, 0.528)
    printed = got["printed_deciding_nothing"]
    assert printed["median_rerank_sec"] == {"k20": 31.82, "k14": 15.188}
    assert (printed["median_retrieval_saving_sec"], printed["median_vector_saving_sec"]) == (
        14.644,
        0.108,
    )
    assert printed["same_k_spread"] == {"k20": 0.277, "k14": 0.004}
    for key in ("same_pool_both_asks", "same_five_both_asks", "pools_as_k_curve"):
        assert printed[key] == {"k20": 12, "k14": 12}, key
    # the forecast: faster on 12 of 12 held; the ratio fell below the candidates' and 0.70, the
    # saving above 7-9 s; K = 20's rerank was slower than 25-28 s
    ratios = [pair["rerank_ratio"] for pair in pairs]
    assert max(ratios) < min(candidates_ratio(pair) for pair in pairs)
    assert got["median_rerank_saving_sec"] > 9 and printed["median_rerank_sec"]["k20"] > 28
    # against either K = 20 run alone K = 14 is below on all twelve
    assert [against(label)[0] for label in K20] == [12, 12]
    # a run read alone pairs nothing, nor does the first question's read
    for read in (*own.values(), q1):
        assert read["readings"]["answer"] == reader.NOT_EVIDENCE


def readings_rows() -> list[str]:
    got = record["readings"]
    savings = [pair["rerank_saving_sec"] for pair in pairs]
    ratios = [pair["rerank_ratio"] for pair in pairs]
    return [
        "| The answer: K = 14 below on more questions, the exact two-sided sign test's p below"
        f" 0.05 | **{got['answer']}** | below on {got['k14_faster']} of"
        f" {got['readable_questions']} readable questions, above on {got['k14_slower']};"
        f" p {got['sign_p']:.6f} | faster, on 12 of 12 |",
        "| The number: the median saving, K = 20's rerank seconds less K = 14's"
        f" | **{fmt(got['median_rerank_saving_sec'])} s**"
        f" | {fmt(min(savings))}–{fmt(max(savings))} s by question | ≈ 7–9 s |",
        "| The number: the median ratio, K = 14's rerank seconds over K = 20's"
        f" | **{fmt(got['median_rerank_ratio'])}**"
        f" | {fmt(min(ratios))}–{fmt(max(ratios))} by question | ≈ 0.70 |",
    ]


def pair_rows() -> list[str]:
    out = []
    for pair in pairs:
        (pool20,), (pool14,) = pair["k20_pool"], pair["k14_pool"]
        out.append(
            f"| {pair['position']} | `{pair['case_id']}` | {pool20} / {pool14}"
            f" | {' / '.join(fmt(value) for value in pair['k20_rerank'])}"
            f" | {' / '.join(fmt(value) for value in pair['k14_rerank'])}"
            f" | {fmt(pair['rerank_saving_sec'])} | {fmt(pair['rerank_ratio'])}"
            f" | {fmt(candidates_ratio(pair))} | {'yes' if same_five(pair['position']) else 'no'} |"
        )
    return out


def run_rows() -> list[str]:
    out = []
    for label, run in runs.items():
        first, rest = run["asks"][0], run["asks"][1:]
        out.append(
            f"| `{label}` | {run['k']} | {when(run['launch']['started']):%H:%M:%S}"
            f" | {fmt(run['retriever_build_sec'])} | {fmt(first['vector'])}"
            f" | {fmt(first['rerank'])} | {fmt(mid([ask['rerank'] for ask in rest]))}"
            f" | {fmt(run_total(run))} |"
        )
    return out


def printed_rows() -> list[str]:
    got = record["readings"]["printed_deciding_nothing"]
    n = record["readings"]["readable_questions"]

    def row(name: str, key: str, show: Callable[[Any], str]) -> str:
        return f"| {name} | {show(got[key]['k20'])} | {show(got[key]['k14'])} |"

    def count(value: int) -> str:
        return f"{value} of {n}"

    return [
        row(
            "The rerank's seconds, a median over both asks of the twelve", "median_rerank_sec", fmt
        ),
        row(
            "The same K's spread, a median of the two asks' difference over their mean",
            "same_k_spread",
            fmt,
        ),
        row("Questions whose two asks reranked the same pool", "same_pool_both_asks", count),
        row("Questions whose two asks kept the same five", "same_five_both_asks", count),
        row("Questions whose pool had the K curve's count", "pools_as_k_curve", count),
    ]


def alone_rows() -> list[str]:
    out = []
    for label in K20:
        below, saving, ratio, low, high = against(label)
        out.append(
            f"| `{label}` | {below} of {len(pairs)} | {fmt(saving)} | {fmt(ratio)}"
            f" | {fmt(low)}–{fmt(high)} |"
        )
    return out


# the spec's two forecasts, in its words
FORECAST = (
    "**faster**, on 12 of 12",
    "the ratio ≈ 0.70, the K curve's candidates at 14 over 20 for these twelve (0.64–0.73)",
    "a saving ≈ 7–9 s of a rerank ≈ 25–28 s at K = 20",
    "a K = 20 run ≈ 7.6 min",
    "a K = 14 run ≈ 6 min",
    "≈ 27 min for the four, ≈ 35 min with the copies, the checks and the reads",
)


def minutes(labels: list[str]) -> str:
    """The runs' build and thirteen retrievals, in minutes, the same for both runs of a K."""
    (shown,) = {f"{run_total(runs[label]) / 60:.1f}" for label in labels}
    return shown


def span() -> tuple[float, float]:
    """Minutes from the first start to the last, and to the last run's last retrieval's end at
    the earliest: its start, its build and its thirteen retrievals."""
    starts = [when(run["launch"]["started"]) for run in runs.values()]
    between = (starts[-1] - starts[0]).total_seconds()
    return between / 60, (between + run_total(runs[K20[-1]])) / 60


def forecast_rows() -> list[str]:
    got = record["readings"]
    rerank = got["printed_deciding_nothing"]["median_rerank_sec"]["k20"]
    cand = [candidates_ratio(pair) for pair in pairs]
    by_run = [fmt(mid([ask["rerank"] for ask in runs[label]["asks"][1:]])) for label in K20]
    total = sum(run_total(run) for run in runs.values()) / 60
    measured = (
        f"**{got['answer']}**, on {got['k14_faster']} of {got['readable_questions']}",
        f"{fmt(got['median_rerank_ratio'])}; those candidates' ratio a median"
        f" {fmt(statistics.median(cand))}, {fmt(min(cand))}–{fmt(max(cand))}",
        f"a saving of {fmt(got['median_rerank_saving_sec'])} s of a rerank of {fmt(rerank)} s"
        f" at K = 20, {' and '.join(by_run)} s by run",
        f"{minutes(K20)} min in each, its build and thirteen retrievals",
        f"{minutes(K14)} min in each",
        f"{total:.1f} min of the four builds and retrievals; from the first start to the last"
        f" retrieval's end at least {span()[1]:.1f} min",
    )
    return [f"| {said} | {seen} |" for said, seen in zip(FORECAST, measured, strict=True)]


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def test_the_capsule_tables_are_the_records() -> None:
    lines = CAPSULE.read_text(encoding="utf-8").splitlines()
    tables = {
        readings_rows: 3,
        pair_rows: 12,
        run_rows: 4,
        printed_rows: 5,
        alone_rows: 2,
        forecast_rows: 6,
        file_rows: 6,
    }
    for build, count in tables.items():
        rows = build()
        assert len(rows) == count, build.__name__
        for row in rows:
            assert row in lines, row


# the capsule's own words for its limits and its reading; each sits on one line of it
PHRASES = (
    "The record holds no question, document, source name, prompt or command line.",
    "in `3fc8ce7` before the first request; nothing changed after it.",
    "all four runs' gates passed on all five points",
    "Retrieval seconds only; nothing on quality.",
    "No K is adopted here.",
    "changing K in production is Julia's word",
    "The record does not say why.",
    "A pool's count is not its set:",
    "(mine, no rule of the spec)",
    "Step 3's record names no corpus file",
    "the record holds no load",
)


def computed_phrases() -> list[str]:
    got = record["readings"]
    printed = got["printed_deciding_nothing"]
    n = got["readable_questions"]
    ratios = [pair["rerank_ratio"] for pair in pairs]
    cand = [candidates_ratio(pair) for pair in pairs]
    gaps = {k: [abs(a - b) for pair in pairs for a, b in [pair[f"k{k}_rerank"]]] for k in (20, 14)}
    slower = sum(1 for pair in pairs if pair["k20_rerank"][1] > pair["k20_rerank"][0])
    alone = [against(label)[2] for label in K20]
    below = only({against(label)[0] for label in K20})
    positions = range(1, len(reader.CASES) + 1)
    kept = sum(1 for position in positions if same_five(position))
    starts = [when(run["launch"]["started"]) for run in runs.values()]
    (pooled,) = [point["expanded"] for point in k_curve["pooled"] if point["k"] == 14]
    cap = int(runs[K20[0]]["launch"]["client_cap_sec"])
    position = reader.CASES.index("aircargo-matliab-disputed") + 1
    sent20, sent14 = (only(at(position, k, "sent")) for k in (20, 14))
    tokens20, tokens14 = (only(at(position, k, "prompt_est_tokens")) for k in (20, 14))
    return [
        f"The runs started between {starts[0]:%H:%M} and {starts[-1]:%H:%M} UTC",
        f"(its manifest `{v4['source_sha256']['corpus.manifest.json'][:8]}…`)",
        f"`evaluation/curated_cases_aircargo.jsonl` (`{sha(CASES_FILE)[:8]}…`",
        f"`{v4['settings']['reranker_model']}` by V4's settings",
        f"The supervisor's bound was {cap:,} s.",
        f"below K = 20 on {got['k14_faster']} of {n} questions, p {got['sign_p']:.6f}",
        f"The median saving is {fmt(got['median_rerank_saving_sec'])} s, the median ratio"
        f" {fmt(got['median_rerank_ratio'])}.",
        f"a median ratio of {fmt(got['median_rerank_ratio'])} against the pools'"
        f" {fmt(statistics.median(cand))}",
        f"Every question's ratio, {fmt(max(ratios))} at most,",
        f"every question's candidates' ratio, {fmt(min(cand))} at least.",
        f"the whole retrieval saved a median {fmt(printed['median_retrieval_saving_sec'])} s"
        f" and its vector search {fmt(printed['median_vector_saving_sec'])} s",
        f"`{K20[1]}` reranked slower than `{K20[0]}` on {slower} of {n} questions",
        f"spread was {fmt(printed['same_k_spread']['k20'])} at K = 20 against"
        f" {fmt(printed['same_k_spread']['k14'])} at K = 14",
        f"at most {fmt(max(gaps[14]))} s apart, its two K = 20 asks"
        f" {fmt(min(gaps[20]))}–{fmt(max(gaps[20]))} s",
        f"Against either K = 20 run alone K = 14 is below on {below} of {n}",
        f"the ratio is {fmt(alone[0])} against the first and {fmt(alone[1])} against the second",
        f"on {kept} of {len(reader.CASES)} questions, exactly those where the K curve kept all"
        " five",
        f"{sent20} documents and {tokens20:,} tokens at K = 20, {sent14} and {tokens14:,} at"
        " K = 14",
        f"in {pooled['hits']['k']} of {pooled['n']} questions against {pooled['hits']['k20']}"
        f" at K = 20 (b {pooled['b_k20_only']}, c {pooled['c_k_only']}, exact McNemar"
        f" p {pooled['p']})",
        f"against ({fmt(min(alone))}–{fmt(max(alone))})",
    ]


def test_the_capsule_states_its_limits_and_the_records_numbers_each_on_one_line() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    assert not re.search("[\u0400-\u04ff]", text)
    lines = text.splitlines()
    built = computed_phrases()
    assert len(built) == 20
    for phrase in (*PHRASES, *built):
        assert any(phrase in line for line in lines), phrase


def test_the_spec_names_this_record_and_its_forecasts_as_the_capsule_quotes_them() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage4-step3-record.md)" in spec
    flat = " ".join(spec.split())
    for said in FORECAST:
        assert said in flat, said
