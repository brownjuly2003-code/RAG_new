"""Stage 7's entity probe: the records read again with the committed probe; its gate, G2's stop,
the stand, the frozen values, the log and the privacy (docs/specs/stage7-entity-probe.md,
«Records»). Every table row of docs/evidence/stage7-entity-probe-record.md is built from the
records, and so is every number of its prose that a test below pins."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
import tempfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports" / "stage7" / "tools" / "entity_probe.py"
RECORDS = ROOT / "reports" / "stage7" / "entity-probe" / "52dd160"
SPEC = ROOT / "docs" / "specs" / "stage7-entity-probe.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage7-entity-probe-record.md"
# the files as copied from the Mac, by their SHA-256, which the Mac's copies matched
FILES = {
    "launch.json": "2f14772b476ae64274fd8f906e835e61a9a93c66cba3d54c8c2038b2661c32ec",
    "chunks.jsonl": "2e6234bda0a124ccf40d76ed3ce878ad2f18b5ef07dc4a6820820254021324d0",
    "end.json": "c7a634a219dff511296f76f502fec8d9508bec4aa39ca228b0e6162927781d2d",
    "e1.log": "376d85c6e1b467b6038b8eacd2ae8a45830145938619a55a9a8d78183ef6ff50",
    "e1.probe.json": "82a973b60896fb09625b32f3365cf30656603dddbe949c01bdb028ff3efa5d37",
}
RUN_FILES = ("launch.json", "chunks.jsonl", "end.json")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("entity_probe_record", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["entity_probe_record"] = module
    spec.loader.exec_module(module)
    return module


probe = _load()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


record = _json(RECORDS / "e1.probe.json")
launch = _json(RECORDS / "launch.json")
end = _json(RECORDS / "end.json")
rows = [json.loads(line) for line in (RECORDS / "chunks.jsonl").read_text("utf-8").splitlines()]
measured = rows[1:]
seconds = [row["sec"] for row in measured]
valid = [row["valid"] for row in measured]
printed = record["printed_deciding_nothing"]
mean, lower, upper = probe.bounds(seconds)
LINE = probe.DAY / probe.N_MULTIHOP


def fmt(value: float) -> str:
    return f"{value:.3f}"


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_record_is_the_committed_probes_read_of_the_three_files() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    tool = listed["reports/stage7/tools/entity_probe.py"]
    assert sha(TOOL) == tool == record["tool_sha256"] == launch["tool_sha256"]
    assert record["files_sha256"] == {name: FILES[name] for name in RUN_FILES}
    with tempfile.TemporaryDirectory() as folder:
        run_dir = Path(folder) / "e1"
        run_dir.mkdir()
        for name in RUN_FILES:
            (run_dir / name).write_bytes((RECORDS / name).read_bytes())
        again = probe.read(run_dir)
        probe.put(Path(folder) / "again.json", again)
        assert again == record
        assert (Path(folder) / "again.json").read_bytes() == (
            RECORDS / "e1.probe.json"
        ).read_bytes()


def test_the_gate_passed_and_the_lower_bound_stopped_the_run_at_the_first_look() -> None:
    assert record["gate"] == {"launch": True, "rows": True, "end": True, "clean": True}
    assert record["notes"] == []
    assert record["g2"] == {"verdict": "failed", "failed_by": ["lower"], "stopped_at": 10}
    assert (end["status"], end["reason"], end["stop"], end["n"]) == (
        "stopped",
        None,
        {"rule": "lower", "at": 10},
        10,
    )
    # the stop again from the rows' seconds: no rule before chunk 10, the lower bound at it
    assert probe.first_stop(seconds, valid) == ("lower", 10)
    assert len(seconds) == probe.CHECKPOINTS[0] == 10
    assert probe.N_MULTIHOP * lower > probe.DAY
    assert probe.N_MULTIHOP * math.fsum(seconds) <= probe.TOTAL * probe.DAY
    assert all(valid)
    assert (printed["mean_sec"], printed["lower_sec"], printed["upper_sec"]) == (
        round(mean, 6),
        round(lower, 6),
        round(upper, 6),
    )


def test_the_stand_and_the_frozen_values_are_the_specs() -> None:
    frozen = {
        "schema": probe.SCHEMA_ID,
        "spec": probe.SPEC,
        "system": probe.SYSTEM,
        "machine": probe.MACHINE,
        "ollama": probe.OLLAMA,
        "ollama_version": probe.OLLAMA_VERSION,
        "model": probe.MODEL,
        "model_digest": probe.MODEL_DIGEST,
        "options": probe.OPTIONS,
        "keep_alive": probe.KEEP_ALIVE,
        "prompt_sha256": probe.PROMPT_SHA256,
        "format_sha256": probe.FORMAT_SHA256,
        "archive": probe.ARCHIVE,
        "archive_sha256": probe.ARCHIVE_SHA256,
        "tenant": probe.TENANT,
        "n_chunks": probe.N_MULTIHOP,
        "picks": probe.picks(probe.N_MULTIHOP),
        "order": probe.run_order(),
        "warmup_index": probe.N_MULTIHOP - 1,
        "total": probe.TOTAL,
        "checkpoints": list(probe.CHECKPOINTS),
        "max_invalid": probe.MAX_INVALID,
        "caps_sec": probe.caps(),
    }
    assert {key: launch[key] for key in frozen} == frozen
    # the idle check at the start: nothing of others', no CI lock, no model, the load below 2
    assert (launch["others"], launch["lock"], launch["ollama_models_before"]) == (0, False, [])
    assert launch["loadavg"][1] < 2 and launch["python"].startswith("3.11.")
    # the runner after the load: one, on the CPU, one slot of the registered context
    load = end["load"]
    stand = ("size_vram", "context_length", "runners", "runner_np", "runner_c")
    assert tuple(load[key] for key in stand) == (0, 4096, 1, 1, 4096)
    assert load["sec"] < probe.LOAD_CAP
    assert end["ollama_models_end"] == [probe.MODEL] and end["ollama_models_after"] == []
    assert 0 <= end["unload_sec"] < end["unload_cap_sec"] == probe.UNLOAD_CAP
    spans = math.fsum([end["load"]["sec"], *(row["sec"] for row in rows)])
    assert spans <= end["run_sec"] <= end["wall_sec"] and end["run_sec"] < probe.RUN_CAP
    # the warm-up, then picks 0, 10, …, 90 in the run's order, each by its index
    picks = probe.picks(probe.N_MULTIHOP)
    assert [row["position"] for row in rows] == list(range(11))
    assert [row["pick"] for row in rows] == [None, *probe.run_order()[:10]]
    assert [row["index"] for row in rows] == [
        probe.N_MULTIHOP - 1,
        *(picks[pick] for pick in probe.run_order()[:10]),
    ]
    for row in rows:
        flags = (row["status"], row["reason"], row["valid"], row["digest_ok"])
        assert flags == ("ok", "ok", True, True), row["position"]
        assert (row["others"], row["lock"], row["alone"]) == (0, False, True), row["position"]
        assert row["ollama"]["load_duration"] < probe.RELOAD_NS, row["position"]
        assert row["ollama"]["done_reason"] == "stop", row["position"]
        assert row["chat_sec"] <= row["sec"] < probe.CHUNK_CAP, row["position"]
        assert row["entities"] == row["distinct"] and row["pairs"] == math.comb(row["distinct"], 2)


def log_lines() -> list[str]:
    """The probe's log as its run prints it, built from the rows and the end."""
    load = end["load"]
    lines = [
        f"loaded in {load['sec']:.1f} s, size_vram {load['size_vram']},"
        f" context_length {load['context_length']}, runners {load['runners']},"
        f" -np {load['runner_np']}, -c {load['runner_c']}"
    ]
    for row in rows:
        lines.append(
            f"chunk {row['position']} pick {row['pick']} index {row['index']} sec {row['sec']:.3f}"
            f" {row['reason']} entities {row['entities']}"
            f" others {row['others']} lock {row['lock']} alone {row['alone']}"
        )
        if row["position"] in probe.CHECKPOINTS:
            at = probe.bounds([item["sec"] for item in rows[1 : row["position"] + 1]])
            lines.append(
                f"look {row['position']}: mean {at[0]:.3f} lower {at[1]:.3f}"
                f" upper {at[2]:.3f} line {LINE:.3f}"
            )
    lines.append(f"PROBE_DONE {end['status']} {end['stop']['rule']} at {end['stop']['at']}")
    return lines


def test_the_log_is_the_rows_the_look_and_the_end() -> None:
    assert (RECORDS / "e1.log").read_text(encoding="utf-8").splitlines() == log_lines()


HEX = re.compile(r"[0-9a-f]{64}")
TIME = re.compile(r"2026-10-29T\d\d:\d\d:\d\d\+00:00")
VERSION = re.compile(r"\d+(?:\.\d+)+")
WORDS = {
    # the schema, the spec's path, the model, the tenant, the endpoint, the archive, the stand
    *(probe.SCHEMA_ID, probe.SPEC, probe.MODEL, probe.TENANT, probe.OLLAMA, probe.ARCHIVE),
    *(probe.KEEP_ALIVE, probe.SYSTEM, probe.MACHINE, "e1"),
    # the enums
    *(*probe.REASONS, *probe.STATUSES, *probe.RULES, "stop", "stopped", "failed"),
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


def test_the_records_hold_numbers_ids_enums_paths_and_hashes_only() -> None:
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        if name.endswith(".log"):
            continue  # every line of it is built above from the rows and the end
        lines = text.splitlines() if name.endswith(".jsonl") else [text]
        for value, key in strings([json.loads(line) for line in lines]):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            shapes = (HEX, TIME, VERSION)
            assert value in WORDS or any(s.fullmatch(value) for s in shapes), (name, value)


def yes(flag: bool) -> str:
    return "yes" if flag else "no"


def reading_rows() -> list[str]:
    gate = record["gate"]
    points = ", ".join(
        "passed" if gate[key] else "failed" for key in ("launch", "rows", "end", "clean")
    )
    n = printed["n"]
    return [
        f"| The gate: launch, rows, end, clean | {points}; no note |",
        f"| G2 | **{record['g2']['verdict']}**, by the lower bound at the look after chunk"
        f" {record['g2']['stopped_at']} |",
        f"| The look after {n} chunks: the mean, the lower bound, the upper bound |"
        f" {fmt(mean)} s, {fmt(lower)} s, {fmt(upper)} s |",
        f"| The line, 86,400 / 11,231 | {fmt(LINE)} s |",
        f"| 11,231 × the lower bound | {probe.N_MULTIHOP * lower:,.0f} s,"
        f" {probe.N_MULTIHOP * lower / 3600:.1f} h: over 24 h |",
        f"| Valid | {printed['valid']} of {n}, {printed['empty_arrays']} empty |",
    ]


def chunk_rows() -> list[str]:
    built = []
    for row in rows:
        position = "0, the warm-up" if row["position"] == 0 else str(row["position"])
        pick = "—" if row["pick"] is None else str(row["pick"])
        counters = row["ollama"]
        built.append(
            f"| {position} | {pick} | {row['index']:,} | {row['content_chars']:,}"
            f" | {fmt(row['sec'])} | {counters['prompt_eval_count']} | {counters['eval_count']}"
            f" | {row['entities']} | {yes(row['valid'])} |"
        )
    return built


def triple(values: list[float]) -> str:
    return ", ".join(f"{value:.2f}" for value in values)


def printed_rows() -> list[str]:
    hours = printed["projected_hours"]
    load = printed["load"]
    average, swap = printed["loadavg"], printed["swap_used_mib"]
    first, second = printed["halves_mean_sec"]
    reasons = ", ".join(f"`{key}` {count}" for key, count in printed["done_reasons"].items())
    after = ", ".join(printed["ollama_models_after"]) or "none"
    return [
        "| Seconds a chunk: the median, the 90th percentile, the longest |"
        f" {fmt(printed['median_sec'])}, {fmt(printed['p90_sec'])}, {fmt(printed['max_sec'])} |",
        f"| The halves' means: chunks 1–5, chunks 6–10 | {fmt(first)} s, {fmt(second)} s |",
        "| Projected hours, MultiHop-RAG's 11,231 chunks: at the mean, at the upper bound |"
        f" {hours['multihoprag_at_mean']}, {hours['multihoprag_at_upper']} |",
        "| Projected hours, ConditionalQA's and WixQA's 51,349: at the mean, at the upper bound |"
        f" {hours['conditionalqa_wixqa_at_mean']}, {hours['conditionalqa_wixqa_at_upper']} |",
        "| Prompt tokens, generated tokens: medians a chunk, Ollama's counts |"
        f" {printed['prompt_eval_count_median']}, {printed['eval_count_median']} |",
        "| Prompt tokens a second, generated tokens a second, Ollama's |"
        f" {printed['prompt_tokens_per_sec']}, {printed['generated_tokens_per_sec']} |",
        "| The client's seconds over Ollama's own, median |"
        f" {fmt(printed['wall_less_ollama_median_sec'])} |",
        "| Entities, distinct keys, their pairs: medians a chunk |"
        f" {printed['entities_median']:g}, {printed['distinct_median']:g},"
        f" {printed['pairs_median']:g} |",
        f"| A chunk's characters, median | {printed['content_chars_median']:g} |",
        f"| Reloads; done reasons | {printed['reloads']}; {reasons} |",
        f"| The warm-up | {fmt(printed['warmup']['sec'])} s, `{printed['warmup']['reason']}` |",
        "| The load: seconds; size and size_vram, bytes; context_length; runners, -np, -c |"
        f" {fmt(load['sec'])}; {load['size']:,} and {load['size_vram']};"
        f" {load['context_length']}; {load['runners']}, {load['runner_np']}, {load['runner_c']} |",
        f"| The run's seconds; its wall time | {fmt(printed['run_sec'])};"
        f" {fmt(printed['wall_sec'])} |",
        "| Load average over 1, 5 and 15 min: at launch; at the end |"
        f" {triple(average['launch'])}; {triple(average['end'])} |",
        f"| Swap used, MiB: at launch; at the end | {swap['launch']:,.1f}; {swap['end']:,.1f} |",
        f"| The unload's seconds; Ollama's models after it | {fmt(printed['unload_sec'])};"
        f" {after} |",
    ]


# the spec's forecast, written before the first request, as the capsule quotes it
FORECAST = (
    "So **G2 fails at the first look**, the mean 2–7 × the line, with 10 of 10 valid",
    "Low 210/42 + 40/4.0 = 15.0 s; mid 210/33 + 65/3.0 = 28.0 s; high, nothing reused,"
    " 295/24 + 90/2.1 = 55.2 s; idle, at the known 4.3–4.7 tokens a second,"
    " 210/42 + 65/4.5 = 19.4 s",
    "At 24–42 prompt tokens a second and 2.1–4.0 generated",
    "≈ 210 new a chunk (a median 850 characters in `reports/external/36f1167/connection.json`);"
    " 40–90 generated",
    "At ≈ 20 s, ≈ 62 h for MultiHop-RAG and ≈ 285 h for ConditionalQA and WixQA",
    "GR-2's 11.4 s for a 7B is faster than these rates allow the 4B; the probe settles it",
    "The Mac ≈ 5 min (the load 31–51 s in step 1, the warm-up ≈ 25 s, ten chunks), 3–11 min"
    " across the cases",
)


def forecast_rows() -> list[str]:
    hours = printed["projected_hours"]
    generated = [row["ollama"]["eval_count"] for row in measured]
    measured_as = (
        f"failed at the first look, by the lower bound; the mean {mean / LINE:.2f} × the line;"
        f" {printed['valid']} of {printed['n']} valid",
        f"{fmt(mean)} s at the mean, under the low case",
        f"{printed['prompt_tokens_per_sec']} prompt tokens a second and"
        f" {printed['generated_tokens_per_sec']} generated, Ollama's",
        f"Ollama's prompt count a median {printed['prompt_eval_count_median']}, the text a median"
        f" {printed['content_chars_median']:g} characters; generated a median"
        f" {printed['eval_count_median']}, {min(generated)}–{max(generated)}",
        f"at the mean, {fmt(mean)} s: {hours['multihoprag_at_mean']} h and"
        f" {hours['conditionalqa_wixqa_at_mean']} h",
        f"the 4B {fmt(mean)} s a chunk at the mean, under the 7B's 11.4 s",
        f"{fmt(printed['wall_sec'])} s in all: the load {fmt(printed['load']['sec'])} s, the"
        f" warm-up {fmt(printed['warmup']['sec'])} s, ten chunks",
    )
    return [f"| {said} | {got} |" for said, got in zip(FORECAST, measured_as, strict=True)]


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def test_the_capsule_tables_are_the_records() -> None:
    lines = CAPSULE.read_text(encoding="utf-8").splitlines()
    tables = {
        reading_rows: 6,
        chunk_rows: 11,
        printed_rows: 16,
        forecast_rows: 7,
        file_rows: 5,
    }
    for build, count in tables.items():
        built = build()
        assert len(built) == count, build.__name__
        for row in built:
            assert row in lines, row


# the capsule's own words for its limits and its reading; each sits on one line of it
PHRASES = (
    "The record holds no chunk's text, output's text, source name, host name, command line or"
    " filled prompt.",
    "**G2 failed, so E stops**",
    "The probe is no slice by the acceptance rule",
    "**Ten chunks, by design.**",
    "**The entities' quality is not read.**",
    "**No other way to extract was tried.**",
)


def computed_phrases() -> list[str]:
    started, ended = when(launch["started"]), when(end["ended"])
    return [
        f"The run `e1` went from {started:%H:%M:%S} to {ended:%H:%M:%S} UTC on 2026-10-29",
        f"the lower bound of the mean, {fmt(lower)} s, puts MultiHop-RAG's 11,231 chunks at"
        f" {probe.N_MULTIHOP * lower / 3600:.1f} h",
        f"{printed['valid']} of {printed['n']} outputs valid",
        f"read {printed['prompt_tokens_per_sec']} prompt tokens a second and wrote"
        f" {printed['generated_tokens_per_sec']}",
        f"{mean / LINE:.2f} × the line at the mean",
    ]


def test_the_capsule_states_its_limits_and_the_records_numbers_each_on_one_line() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    assert not re.search("[\u0400-\u04ff]", text)
    lines = text.splitlines()
    built = computed_phrases()
    assert len(built) == 5
    for phrase in (*PHRASES, *built):
        assert any(phrase in line for line in lines), phrase


def test_the_spec_names_this_record_and_its_forecast_as_the_capsule_quotes_it() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage7-entity-probe-record.md)" in spec
    flat = " ".join(spec.split())
    for said in FORECAST:
        assert said in flat, said
    # what follows a failed G2, in the spec's words and the capsule's
    capsule = " ".join(CAPSULE.read_text(encoding="utf-8").split())
    said = "Past G2 the full extraction of MultiHop-RAG runs; else E stops."
    assert said in flat and said in capsule
