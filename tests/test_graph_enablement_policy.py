"""The graph enablement policy speaks the vocabulary of the code.

`docs/specs/graph-enablement-policy.md` (plan step 3.0) places every question class, every
reason code and every entity graph status in a rule. A class, a code or a status added to the
code has to be placed there too, and the thresholds the policy retires are the ones the
settings still carry.
"""

from pathlib import Path

import pytest

from agent import graph
from agent.state import create_initial_state
from config.settings import Settings
from ingestion import entity_graph_loading

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "specs" / "graph-enablement-policy.md"
# Reason codes written without asking the model: by the classifier node and by the initial state.
NODE_CODES = ("ROUTING_DISABLED", "LEGACY_COMPLEXITY_ONLY", "SCHEMA_FIELDS_INVALID")
INITIAL_CODE = "NOT_CLASSIFIED"


@pytest.fixture(scope="module")
def text() -> str:
    return SPEC.read_text(encoding="utf-8")


def _rule_rows(text: str) -> list[list[str]]:
    """The cells of the selection table: the rows between its header and the next blank line."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| `question_class` |"))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def test_every_class_and_reason_code_is_placed(text: str) -> None:
    source = (ROOT / "agent" / "graph.py").read_text(encoding="utf-8")
    for code in NODE_CODES:
        assert f'"{code}"' in source
    initial = create_initial_state("question")
    assert initial["reason_code"] == INITIAL_CODE
    assert initial["question_class"] == "unknown"
    placed = (
        *graph._SGR_QUESTION_CLASSES,
        "unknown",
        *graph._SGR_REASON_CODES,
        *NODE_CODES,
        INITIAL_CODE,
    )
    for name in placed:
        assert f"`{name}`" in text, name


def test_the_branch_opens_for_three_pairs_only(text: str) -> None:
    rows = _rule_rows(text)
    opened = {(row[0].strip("`"), row[1].strip("`")) for row in rows if row[2] == "graph"}
    assert opened == {
        ("multi_hop", "MULTI_SOURCE_CHAIN"),
        ("aggregation", "MULTI_SOURCE_AGGREGATION"),
        ("global", "CORPUS_GLOBAL"),
    }
    assert {name for name, _ in opened} == set(graph._SGR_MULTI_HOP_CLASSES)
    assert {code for _, code in opened} <= set(graph._SGR_REASON_CODES)
    assert {row[2] for row in rows} == {"graph", "hybrid"}
    assert any(row[0] == "`single_hop`" and row[2] == "hybrid" for row in rows)
    assert any(row[0] == "`unknown`" and row[2] == "hybrid" for row in rows)


def test_every_entity_graph_status_is_named(text: str) -> None:
    statuses = {
        value
        for name, value in vars(entity_graph_loading).items()
        if name.startswith("ENTITY_GRAPH_")
    }
    assert len(statuses) == 6
    for status in statuses:
        assert f"`{status}`" in text, status


def test_the_retired_thresholds_are_the_ones_of_the_settings(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("RAG_GRAPH_RETRIEVAL", "RAG_GRAPH_MIN_CHUNKS", "RAG_GRAPH_MIN_CROSSDOC_SHARE"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.graph_retrieval == "off"
    assert settings.graph_min_chunks == 20000
    assert settings.graph_min_crossdoc_share == 0.15
    assert "20 000 chunks" in text
    assert "share of 0.15" in text
