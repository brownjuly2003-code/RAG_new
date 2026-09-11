"""GR-1 migration and tenant-scoped structural graph persistence."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import Session

from db.models import KbGraphEdge, KbGraphNode
from ingestion.structure_graph import build_structural_graph
from ingestion.structure_graph_repository import StructuralGraphRepository

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_PATH = PROJECT_ROOT / "alembic" / "versions" / "032_kb_structure_graph.py"


def _load_migration() -> ModuleType:
    assert MIGRATION_PATH.is_file(), f"missing migration: {MIGRATION_PATH}"
    spec = importlib.util.spec_from_file_location("migration_032_kb_structure_graph", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _graph(*, tenant_id: str = "acme", extra_chunk: bool = True):
    chunks = [
        SimpleNamespace(
            page_content="See policy.md",
            metadata={
                "source": "guide.md",
                "chunk_index": 0,
                "categories": ["shipping"],
                "h1": "Guide",
            },
        ),
        SimpleNamespace(
            page_content="# Policy",
            metadata={
                "source": "policy.md",
                "chunk_index": 1,
                "categories": ["shipping"],
                "h1": "Policy",
            },
        ),
    ]
    if extra_chunk:
        chunks.append(
            SimpleNamespace(
                page_content="Second policy chunk",
                metadata={
                    "source": "policy.md",
                    "chunk_index": 2,
                    "categories": ["shipping"],
                    "h1": "Policy",
                },
            )
        )
    return build_structural_graph(chunks, tenant_id=tenant_id)


def test_graph_models_pin_tenant_owned_keys_and_edge_foreign_keys() -> None:
    node_table = KbGraphNode.__table__
    edge_table = KbGraphEdge.__table__

    assert tuple(column.name for column in node_table.primary_key.columns) == (
        "tenant_id",
        "node_id",
    )
    assert tuple(column.name for column in edge_table.primary_key.columns) == (
        "tenant_id",
        "edge_id",
    )

    node_uniques = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in node_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert node_uniques["uq_kb_graph_nodes_tenant_kind_key"] == (
        "tenant_id",
        "kind",
        "natural_key",
    )

    foreign_keys = [
        constraint
        for constraint in edge_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 2
    assert {
        (
            tuple(column.name for column in constraint.columns),
            tuple(element.column.name for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in foreign_keys
    } == {
        (("tenant_id", "source_node_id"), ("tenant_id", "node_id"), "CASCADE"),
        (("tenant_id", "target_node_id"), ("tenant_id", "node_id"), "CASCADE"),
    }


def test_migration_032_creates_both_tables_with_forced_tenant_rls() -> None:
    module = _load_migration()

    assert module.revision == "032"
    assert module.down_revision == "031"
    assert module._TENANT_TABLES == ("kb_graph_nodes", "kb_graph_edges")
    assert "current_setting('app.current_tenant_id', true)" in module._TENANT_EXPRESSION

    upgrade_source = inspect.getsource(module.upgrade)
    downgrade_source = inspect.getsource(module.downgrade)
    assert upgrade_source.index('"kb_graph_nodes"') < upgrade_source.index('"kb_graph_edges"')
    assert "ENABLE ROW LEVEL SECURITY" in upgrade_source
    assert "FORCE ROW LEVEL SECURITY" in upgrade_source
    assert "CREATE POLICY" in upgrade_source
    assert downgrade_source.index('drop_table("kb_graph_edges")') < downgrade_source.index(
        'drop_table("kb_graph_nodes")'
    )


def test_repository_replaces_and_round_trips_one_tenant_graph() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    KbGraphNode.__table__.create(engine)
    KbGraphEdge.__table__.create(engine)
    first_graph = _graph()

    with Session(engine) as session:
        repository = StructuralGraphRepository(session)
        receipt = repository.replace(first_graph)
        session.commit()

        assert receipt.tenant_id == "acme"
        assert receipt.node_count == len(first_graph.nodes)
        assert receipt.edge_count == len(first_graph.edges)
        assert repository.load("acme") == first_graph

        replacement = _graph(extra_chunk=False)
        repository.replace(replacement)
        session.commit()

        assert repository.load("acme") == replacement
        assert session.scalar(select(func.count()).select_from(KbGraphNode)) == len(
            replacement.nodes
        )
        assert session.scalar(select(func.count()).select_from(KbGraphEdge)) == len(
            replacement.edges
        )


def test_repository_sets_postgres_tenant_context_before_replace() -> None:
    calls: list[tuple[Any, Any]] = []

    class _RecordingSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement: Any, params: Any = None) -> None:
            calls.append((statement, params))

        def add_all(self, rows: list[Any]) -> None:
            calls.append(("add_all", rows))

        def flush(self) -> None:
            calls.append(("flush", None))

    graph = _graph(extra_chunk=False)
    StructuralGraphRepository(_RecordingSession()).replace(graph)  # type: ignore[arg-type]

    assert "set_config('app.current_tenant_id'" in str(calls[0][0])
    assert calls[0][1] == {"tenant_id": "acme"}
