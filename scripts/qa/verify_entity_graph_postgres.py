import importlib.util
import os
import sys
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path.cwd()))
from ingestion.entity_graph import add_entity_graph
from ingestion.structure_graph_repository import StructuralGraphRepository
from tests.test_entity_graph import _input


def migration(name, operations):
    path = Path('alembic/versions') / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


url = make_url(os.environ['RESOLUTION_ADMIN_DATABASE_URL'])
assert url.host in ('127.0.0.1', 'localhost') and url.port == 55432
engine = create_engine(url.set(database='postgres', drivername='postgresql+psycopg2'),
                       connect_args={'connect_timeout': 5}, hide_parameters=True)
with engine.connect() as connection:
    transaction = connection.begin()
    try:
        schema = 'gr2_test_' + uuid4().hex
        connection.execute(text(f'CREATE SCHEMA {schema}'))
        connection.execute(text(f'SET LOCAL search_path TO {schema}'))
        operations = Operations(MigrationContext.configure(connection))
        old = migration('032_kb_structure_graph.py', operations)
        new = migration('033_kb_entity_graph.py', operations)
        old.upgrade()
        new.upgrade()
        graph, _, entities = _input()
        enriched = add_entity_graph(graph, entities)
        with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
            repo = StructuralGraphRepository(session)
            repo.replace(enriched)
            assert len(repo.load(graph.tenant_id).nodes) == len(enriched.nodes)
            session.commit()
        savepoint = connection.begin_nested()
        try:
            new.downgrade()
        except Exception as exc:
            assert getattr(exc.orig, 'pgcode', None) == '23514', type(exc)
            savepoint.rollback()
        else:
            raise AssertionError('Downgrade unexpectedly discarded entity data')
        assert connection.execute(text("SELECT count(*) FROM kb_graph_nodes WHERE kind='entity'")).scalar() == 2
        connection.execute(text('DELETE FROM kb_graph_edges'))
        connection.execute(text('DELETE FROM kb_graph_nodes'))
        new.downgrade()
        new.upgrade()
        print('PASS: PostgreSQL 032->033, entity persistence, data-preserving downgrade refusal, empty round trip', flush=True)
    finally:
        transaction.rollback()
        print('ROLLBACK: temporary schema and all test data', flush=True)
