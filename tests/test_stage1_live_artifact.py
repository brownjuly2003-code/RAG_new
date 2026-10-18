"""Check the published records of stage 1's live audit: one question per corpus, before and after.

PLAN.md stage 1, docs/specs/stage1-fixes.md. One question per tenant - aircargo and the three
external bases, each the question `tools/audit.sh` names - through `/api/ask/stream`, each
tenant on a fresh API of a stand (`git archive` of a commit on the Mac), Qwen3-4B-Instruct-2507
at the code defaults. Before the fixes: stand `99cd15f`, the first-generation indexes. After
them, on the second generation, built at `e5e135a` into `/Users/julia/RAG_new_external_s1`:
stand `0892441`, the V2 prompts, where MultiHop-RAG still answered in Russian; then stand
`4ca5ddd`, the V3 prompts, written in English. `tools/audit_summary.py` wrote each record:
counts, ids and the API's own log lines, no text of an external base. `875f274/` holds the
record of the spec's row 2, WixQA's pages through the product's loader. Nothing here needs a
model, the network or the Mac: the test pins the bytes, applies the criteria the spec
registered before each run, and derives every published number from the records.
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "reports/stage1"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
d9ef99b22199a52c92cb9b8695698c1d15e03ea2fc872d44e082c1c3474c38f5 9496 99cd15f/before.json
0e762eaa57ffd779bf61fff3efe0312d9c9ff5c6e8dc2722aba976bdc0b9bd7f 9637 0892441/after.json
e38f40de432df5e5f2cbcd10cf03681c1f98add1b1f1799157739d5a78a55721 9904 4ca5ddd/after.json
6afd58e1dd8f56a6432904ddc0fd82e957498c1e34f1be5696fae5398b674071 2305 875f274/wixqa-loader-check.json
65807f793ef28ce376f01032fe11901934c99cc8629bc9fe90624bc045140a69 3625 tools/audit.sh
6146f4629680576cf19ad303a6f9bdc2be5943141d93130e620f0fec3b0f2fa3 5654 tools/audit_summary.py
3098a60df73f86d349a2c9619666340503f13d1f3113fb0b23a1eb1475da7531 701 tools/launch.py
8e4b428d9f41412f8e4fc4515d5283567c9075f5b8fcc1fb88eecd4e902a5131 9167 tools/live_api.py
fd5f7d7b66e5be827cb1cbc23074d6b7955f64d18143a11a1f9cd4dbe9caf4d1 7645 tools/live_runner.py
32e5a40552b62c37ee1e3cc387ae01a453b7729adadd7b9f790d73bb1906138c 18865 tools/live_supervisor.py
a5e3c0439a02d4e98b898d085206a2a77ea4021443580a4592290e7bc604b6c8 14727 tools/s1_supervisor.py
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
BEFORE, AFTER_V2, AFTER_V3 = "99cd15f/before.json", "0892441/after.json", "4ca5ddd/after.json"
# The commit `git archive` gave each stand.
STANDS = {
    BEFORE: "99cd15f63967575aca0cb53d3ca33b0caacef289",
    AFTER_V2: "0892441f6f93f9adbe50cfb2e19b31c685562a1d",
    AFTER_V3: "4ca5ddd3dfa7d9ee3df643dcaeabc38e3db9f03d",
}
GENERATIONS = {
    BEFORE: "/Users/julia/RAG_new_external",
    AFTER_V2: "/Users/julia/RAG_new_external_s1",
    AFTER_V3: "/Users/julia/RAG_new_external_s1",
}
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
# The code defaults since 468224b, which the supervisor's `prod` mode puts back.
DEFAULTS = {
    "REQUEST_TIMEOUT_SEC": "3600",
    "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
    "STREAMING_TIMEOUT_SEC": "3600",
    "RAG_DEVICE": "cpu",
}
TENANTS = {
    "aircargo": "aircargo",
    "conditionalqa": "ext_conditionalqa",
    "wixqa": "ext_wixqa",
    "multihoprag": "ext_multihoprag",
}
EXTERNAL = ["conditionalqa", "wixqa", "multihoprag"]
QUESTIONS = {
    "aircargo": "aircargo-probation-data",
    "conditionalqa": "conditionalqa-train-1484",
    "wixqa": "wixqa-simulated-074",
    "multihoprag": "multihoprag-0448",
}
# Each index's chunks, the same in both generations (the spec's row 8 counts them).
CHUNKS = {"aircargo": 5589, "conditionalqa": 13778, "wixqa": 37571, "multihoprag": 11231}
SOURCES = {"corpus.manifest.json", "chunks-report.json", "index/index-receipt.json"}


def runs(name: str) -> dict:
    return json.loads((RECORDS / name).read_text(encoding="utf-8"))["runs"]


def only(run: dict, key: str) -> dict:
    (item,) = run[key]
    return item


def script(letters: dict) -> str:
    """The script most of the letters are written in."""
    return "cyrillic" if letters["cyrillic"] > letters["latin"] else "latin"


def flat(path: str) -> str:
    """A document's text, every run of spaces and line breaks read as one space."""
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def evidence_row() -> str:
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    (row,) = [line for line in index.splitlines() if "`tests/test_stage1_live_artifact.py`" in line]
    return row


def criteria(tenant: str, run: dict) -> dict[str, bool]:
    """The check after the fixes as the spec registered it before its first run."""
    route, sent, asked = only(run, "paths"), only(run, "prompts"), only(run, "cases")
    log = run["bm25_restore_log"]
    return {
        # `kind` alone does not tell: the vector-only run before the fixes also says `hybrid`
        "paths": (
            route["candidates"]["vector"],
            route["candidates"]["bm25"],
            route["rerank_status"],
            route["retained_contexts"],
        )
        == (20, 20, "ok", 5),
        # the summary keeps the restore lines and the failures, nothing else
        "bm25_restore_log": len(log) == 1
        and re.match(rf"Restored \d+ chunks for tenant {TENANTS[tenant]} ", log[0]) is not None,
        "answer_letters": script(asked["answer_letters"]) == script(asked["question_letters"]),
        # window fitting may drop a document or cut one to an excerpt without its header line
        "prompts": sent["labels_dokument"] == sent["header_kontekst"] == 0
        and sent["labels_source"] >= 1
        and sent["header_first_line"] >= 1,
    }


def failed(name: str) -> set[tuple[str, str]]:
    return {
        (tenant, criterion)
        for tenant, run in runs(name).items()
        for criterion, passed in criteria(tenant, run).items()
        if not passed
    }


def restored(run: dict) -> int:
    match = re.match(r"Restored (\d+) chunks", run["bm25_restore_log"][0])
    assert match, run["bm25_restore_log"]
    return int(match.group(1))


def test_published_files_are_pinned() -> None:
    # `__pycache__/` is git-ignored: whatever imports a tool writes it
    published = {
        path.relative_to(RECORDS).as_posix()
        for path in RECORDS.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert published == set(FILES), "every published file is pinned, and only those"
    for name, (sha256, size) in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha256, size), name


def test_the_questions_are_the_first_of_their_registered_order() -> None:
    audit = (RECORDS / "tools/audit.sh").read_text(encoding="utf-8")
    assert all(case_id in audit for case_id in QUESTIONS.values())
    curated = (ROOT / "evaluation/curated_cases_aircargo.jsonl").read_text(encoding="utf-8")
    assert json.loads(curated.splitlines()[0])["case_id"] == QUESTIONS["aircargo"]
    parts = json.loads((ROOT / "evaluation/external_parts.json").read_text(encoding="utf-8"))
    assert parts["selections"]["wixqa"]["pilot"]["case_ids"][0] == QUESTIONS["wixqa"]
    advisory = parts["bases"]["multihoprag"]["parts"]["advisory"]
    assert advisory["case_ids"][0] == QUESTIONS["multihoprag"]
    for name in STANDS:
        for tenant, run in runs(name).items():
            assert [case["case_id"] for case in run["cases"]] == [QUESTIONS[tenant]], name
            asked = only(run, "cases")["question_letters"]
            assert script(asked) == ("cyrillic" if tenant == "aircargo" else "latin")


def test_each_check_ran_on_its_stand_and_generation_at_the_code_defaults() -> None:
    for name, sha in STANDS.items():
        prefix = Path(name).stem
        stand = f"/Users/julia/RAG_new_chat_{sha[:7]}/chatlive/runs"
        assert list(runs(name)) == list(TENANTS), name
        finished = ""
        for tenant, run in runs(name).items():
            launch, label = run["launch"], f"{prefix}-{tenant}"
            assert (launch["label"], launch["code_sha"], launch["tenant"]) == (
                label,
                sha,
                TENANTS[tenant],
            )
            assert (launch["model"], launch["model_digest"]) == (MODEL, MODEL_DIGEST)
            assert (launch["mode"], launch["overrides"]) == ("prod", DEFAULTS), label
            # Complete, and no question stopped: a capped or failed run is NOT_EVIDENCE.
            assert launch["client_cap_sec"] == "1020", "3x the forecast of 340 s"
            assert (launch["status"], launch["runner_exit"]) == ("complete", 0), label
            assert launch["error"] is None and launch["api_killed"] is None, label
            assert only(run, "cases")["client_error"] is None, label
            # one fresh API after another
            assert finished < launch["started"] < launch["finished"], label
            finished = launch["finished"]
            assert run["data_root"] == GENERATIONS[name]
            # Each run read a copy of its index; before the fixes aircargo's was the one
            # the ask100 runtime's env.json names, outside the data root.
            copy = (
                "env.json" if (name, tenant) == (BEFORE, "aircargo") else f"{stand}/{label}.chroma"
            )
            assert launch["chroma_dir"] == copy, label
            cases = (
                "evaluation/curated_cases_aircargo.jsonl"
                if tenant == "aircargo"
                else f"{GENERATIONS[name]}/{tenant}/cases.jsonl"
            )
            assert launch["cases_file"] == cases, label


def test_the_checks_after_read_one_new_generation_of_the_same_corpora() -> None:
    before, v2, v3 = (runs(name) for name in STANDS)
    for tenant in TENANTS:
        assert set(v3[tenant]["source_sha256"]) == SOURCES, tenant
        assert v2[tenant]["source_sha256"] == v3[tenant]["source_sha256"], tenant
    assert before["aircargo"]["source_sha256"] == {}
    for tenant in EXTERNAL:
        old, new = before[tenant]["source_sha256"], v3[tenant]["source_sha256"]
        # the same corpus, cut and indexed anew
        assert old["corpus.manifest.json"] == new["corpus.manifest.json"], tenant
        assert old["chunks-report.json"] != new["chunks-report.json"], tenant
        assert old["index/index-receipt.json"] != new["index/index-receipt.json"], tenant


def test_before_the_fixes() -> None:
    before, row = runs(BEFORE), evidence_row()
    assert failed(BEFORE) == {
        ("wixqa", "paths"),
        ("wixqa", "bm25_restore_log"),
        ("conditionalqa", "answer_letters"),
        ("multihoprag", "answer_letters"),
        *((tenant, "prompts") for tenant in TENANTS),
    }
    for tenant, run in before.items():
        route, sent = only(run, "paths"), only(run, "prompts")
        assert (route["kind"], route["rerank_status"], route["retained_contexts"]) == (
            "hybrid",
            "ok",
            5,
        )
        bm25 = 0 if tenant == "wixqa" else 20
        assert (route["candidates"]["vector"], route["candidates"]["bm25"]) == (20, bm25)
        # «[Документ N» labels, each document opened by a «[Контекст:» header
        assert sent["labels_dokument"] == sent["header_kontekst"] >= 1, tenant
        assert sent["labels_source"] == sent["header_first_line"] == 0, tenant
        if tenant != "wixqa":
            assert restored(run) == CHUNKS[tenant], tenant
    failure, degraded = before["wixqa"]["bm25_restore_log"]
    assert failure.startswith("Chunk restore failed for tenant ext_wixqa")
    assert "too many SQL variables" in failure and "WITHOUT BM25" in degraded
    assert "20 vector and 0 BM25 candidates" in row and "«too many SQL variables»" in row
    cqa, mhr = (
        only(before[t], "cases")["answer_letters"] for t in ("conditionalqa", "multihoprag")
    )
    assert (
        f"({cqa['cyrillic']} and {mhr['cyrillic']} Cyrillic letters against {cqa['latin']} and "
        f"{mhr['latin']} Latin)"
    ) in row


def test_the_first_check_after_failed_one_criterion() -> None:
    v2 = runs(AFTER_V2)
    assert failed(AFTER_V2) == {("multihoprag", "answer_letters")}
    letters = only(v2["multihoprag"], "cases")["answer_letters"]
    phrase = f"{letters['cyrillic']} Cyrillic letters against {letters['latin']} Latin"
    assert phrase in flat("docs/specs/stage1-fixes.md") and phrase in evidence_row()
    # The prompt's letters are counted since V3; V2's 608 were counted on the Mac.
    assert all("letters" not in only(run, "prompts") for run in v2.values())


def test_the_rerun_on_v3_passed_every_criterion() -> None:
    v3, row = runs(AFTER_V3), evidence_row()
    assert failed(AFTER_V3) == set()
    # the criterion registered for the rerun: no Cyrillic letter in an external answer prompt
    for tenant in EXTERNAL:
        letters = only(v3[tenant], "prompts")["letters"]
        assert letters["cyrillic"] == 0 and letters["latin"] > 0, tenant
        assert only(v3[tenant], "cases")["answer_letters"]["cyrillic"] == 0, tenant
    counts = [restored(run) for run in v3.values()]
    assert counts == list(CHUNKS.values())
    assert "(" + " / ".join(f"{count:,}" for count in counts) + ")" in row
    aircargo = only(v3["aircargo"], "cases")["answer_letters"]
    assert (
        f"aircargo {aircargo['cyrillic']} Cyrillic letters against {aircargo['latin']} Latin" in row
    )
    results = [only(run, "cases")["result_sec"] for run in v3.values()]
    assert f"The four answers took {round(min(results))}–{round(max(results))} s" in row


def test_what_moved_beside_the_criteria() -> None:
    v2, v3 = runs(AFTER_V2), runs(AFTER_V3)
    spec, row = flat("docs/specs/stage1-fixes.md"), evidence_row()
    first, second = (
        {tenant: only(run, "cases") for tenant, run in record.items()} for record in (v2, v3)
    )
    assert [first[t]["route"] for t in TENANTS] == ["auto", "human", "auto", "auto"]
    assert [second[t]["route"] for t in TENANTS] == ["auto", "auto", "auto", "human"]
    moved = (
        f"ConditionalQA {first['conditionalqa']['quality_score']} → "
        f"{second['conditionalqa']['quality_score']}, MultiHop-RAG "
        f"{first['multihoprag']['quality_score']} → {second['multihoprag']['quality_score']}"
    )
    assert moved in spec and moved in row
    old, new = first["aircargo"], second["aircargo"]
    assert (
        f"aircargo's answer grew from {old['tokens']} to {new['tokens']} tokens and its result "
        f"from {round(old['result_sec'])} to {round(new['result_sec'])} s"
    ) in spec


def test_the_forecast_table_reads_the_records_time() -> None:
    spec = flat("docs/specs/stage1-fixes.md")
    for name in STANDS:
        launches = [run["launch"] for run in runs(name).values()]
        start = datetime.fromisoformat(launches[0]["started"])
        end = datetime.fromisoformat(launches[-1]["finished"])
        minutes = round((end - start).total_seconds() / 60)
        assert f"{minutes} min, {start:%H:%M}–{end:%H:%M} UTC" in spec, name


def test_the_answer_script_signal_on_the_records() -> None:
    """S8 of the handover plan, a candidate since stage 1: the question's script in the answer."""
    plan = flat("docs/specs/handover-signal.md")
    marked, other = [], []
    for name in STANDS:
        answers = [only(run, "cases") for run in runs(name).values()]
        hits = [
            case
            for case in answers
            if case["answer_letters"][script(case["question_letters"])]
            < sum(case["answer_letters"].values()) / 2
        ]
        marked.append(len(hits))
        other += hits
    assert (
        f"S8 marks {marked[0]} of 4 answers before the fixes, {marked[1]} of 4 on V2 and "
        f"{marked[2]} of 4 on V3"
    ) in plan
    sent = [case for case in other if case["route"] == "auto"]
    assert {case["quality_score"] for case in sent} == {100}
    assert (len(other), len(sent)) == (3, 2)
    assert (
        "hold three answers in the other script, and the chat's rule sent two of them `auto`, "
        "each scored 100"
    ) in plan


def test_the_loader_record_of_row_2() -> None:
    check = json.loads((RECORDS / "875f274/wixqa-loader-check.json").read_text(encoding="utf-8"))
    pages, gold = check["documents"], check["gold_articles"]
    assert pages == check["documents_whole"] == check["documents_with_every_table_row"]
    assert pages == check["documents_with_every_heading_in_order"]
    assert check["visible_characters_held"] == check["visible_characters"]
    assert (
        gold == check["gold_articles_whole"] == check["gold_articles_with_every_heading_in_order"]
    )
    connection = check["connection"]
    assert connection["documents_with_the_visible_text_of_contents"] == pages
    assert connection["documents_with_every_heading_in_order"] == pages
    # the loader skipped only pages with nothing beyond their title
    empty = check["documents_without_text_beyond_title"]
    assert check["loaded"] == pages - empty
    spec = flat("docs/specs/stage1-fixes.md")
    assert f"WixQA's {pages:,} source pages through the loader" in spec
    assert f"the {gold} gold articles too" in spec
    assert f"{empty} pages hold nothing beyond their title" in spec
