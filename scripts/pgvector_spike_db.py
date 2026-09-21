"""Mac-only benchmark over corpus data in a new disposable database, never production."""
import json
import math
import re

import psycopg2
from psycopg2.extras import execute_values
from psycopg2.sql import SQL, Identifier

TENANT = "aircargo"
SENTINEL_TENANT = "zzz_other"
DIM = 1024


def setup(dsn: str, database: str, texts: list[str], vectors) -> psycopg2.extensions.connection:
    """Create a NEW spike database and same-named NOLOGIN NOSUPERUSER NOBYPASSRLS role
    (fails if either already exists; never DROPs), load chunks, add HNSW/GIN indexes,
    FORCE RLS keyed to app.tenant_id, and return a connection with SET ROLE already
    committed. kb_graph_nodes rows are synthetic chunk-membership rows for every chunk
    only -- NOT a real graph; the sentinel row (other tenant, idx=len(texts)) exists
    solely to prove tenant isolation under RLS."""
    parsed = psycopg2.extensions.parse_dsn(dsn)
    assert parsed.get("host") in ("127.0.0.1", "localhost"), "local-only spike"
    assert str(parsed.get("port")) == "55432", "spike port only"
    if not re.fullmatch(r"rag_spike_[a-z0-9_]+", database or "") or len(database) > 50:
        raise ValueError("database must match rag_spike_[a-z0-9_]+ and be <=50 chars")
    if not texts or len(texts) != len(vectors):
        raise ValueError("texts and vectors must be non-empty and equal length")
    for vec in vectors:
        if len(vec) != DIM:
            raise ValueError("embedding dimensionality must be 1024")
        if not all(math.isfinite(float(x)) for x in vec):
            raise ValueError("embedding components must be finite")
    admin = {k: v for k, v in parsed.items() if k != "dbname"}
    role = Identifier(database)
    maint = psycopg2.connect(**admin, dbname="postgres")
    try:
        maint.autocommit = True  # CREATE DATABASE cannot run inside a transaction
        with maint.cursor() as cur:
            cur.execute(SQL("CREATE DATABASE {}").format(role))  # fails if exists; no DROP
            cur.execute(SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(role))
    finally:
        maint.close()
    conn = psycopg2.connect(**admin, dbname=database)
    chunks = Identifier("public", "spike_chunks")
    nodes = Identifier("public", "kb_graph_nodes")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION vector")
        cur.execute(SQL("CREATE TABLE {} (tenant_id text, idx int, content text,"
                        " embedding vector(1024), lex tsvector,"
                        " PRIMARY KEY (tenant_id, idx))").format(chunks))
        cur.execute(SQL("CREATE TABLE {} (tenant_id text, chunk_idx int, kind text,"
                        " PRIMARY KEY (tenant_id, chunk_idx))").format(nodes))
        rows = [(TENANT, i, t, json.dumps([float(x) for x in v]), t)
                for i, (t, v) in enumerate(zip(texts, vectors, strict=True))]
        rows.append((SENTINEL_TENANT, len(texts), "sentinel",
                     json.dumps([float(x) for x in vectors[0]]), "sentinel"))
        execute_values(cur, SQL("INSERT INTO {} (tenant_id, idx, content, embedding, lex)"
                                " VALUES %s").format(chunks), rows,
                       template="(%s, %s, %s, %s, to_tsvector('russian', %s))",
                       page_size=100)
        execute_values(cur, SQL("INSERT INTO {} (tenant_id, chunk_idx, kind)"
                                " VALUES %s").format(nodes),
                       [(TENANT, i, "chunk") for i in range(len(texts))]
                       + [(SENTINEL_TENANT, len(texts), "chunk")], page_size=100)
        cur.execute(SQL("CREATE INDEX ON {} USING hnsw (embedding vector_cosine_ops)"
                        ).format(chunks))
        cur.execute(SQL("CREATE INDEX ON {} USING gin (lex)").format(chunks))
        cur.execute("ANALYZE")
        for table in (chunks, nodes):
            cur.execute(SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(table))
            cur.execute(SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(table))
            cur.execute(SQL("CREATE POLICY tenant_isolation ON {} USING (tenant_id ="
                            " current_setting('app.tenant_id', true))").format(table))
            cur.execute(SQL("GRANT SELECT ON {} TO {}").format(table, role))
        conn.commit()
        cur.execute(SQL("SET ROLE {}").format(role))
        conn.commit()
    return conn
