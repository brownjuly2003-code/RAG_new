"""Native Mac PostgreSQL acceptance for the disposable Phase D experiment."""
import os
import uuid

from scripts.pgvector_spike import pg_search
from scripts.pgvector_spike_db import setup


def test_real_pgvector_retrieval_and_forced_rls():
    dsn = os.environ["SPIKE_ADMIN_DSN"]
    vector = [1.0] + [0.0] * 1023
    other = [0.0, 1.0] + [0.0] * 1022
    conn = setup(dsn, "rag_spike_test_" + uuid.uuid4().hex[:12],
                 ["cargo plane", "truck road"], [vector, other])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            assert cur.fetchone() == (False, False)
            for table in ("spike_chunks", "kb_graph_nodes"):
                cur.execute(f"SELECT count(*) FROM public.{table}")
                assert cur.fetchone()[0] == 0
        conn.commit()
        assert pg_search(conn, vector, "cargo", "aircargo", 2) == [0, 1]
        with conn.cursor() as cur:
            for table in ("spike_chunks", "kb_graph_nodes"):
                cur.execute(f"SELECT count(*) FROM public.{table} WHERE tenant_id='zzz_other'")
                assert cur.fetchone()[0] == 0
                cur.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=%s", (table,))
                assert cur.fetchone() == (True, True)
        conn.commit()
        assert pg_search(conn, vector, "sentinel", "zzz_other", 2) == [2]
        conn.commit()
        assert pg_search(conn, vector, "cargo", "absent", 2) == []
        conn.commit()
    finally:
        conn.close()
