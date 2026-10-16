"""Read-only digest of the ready Chroma index the live runs used (provenance, no writes).

Usage: index_digest.py CHROMA_DIR -> collections, chunk counts and sha256 over sorted chunk texts.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1]) / "chroma.sqlite3"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
rows = con.execute(
    "SELECT c.name, m.string_value FROM embedding_metadata m "
    "JOIN embeddings e ON e.id = m.id "
    "JOIN segments s ON s.id = e.segment_id "
    "JOIN collections c ON c.id = s.collection "
    "WHERE m.key = 'chroma:document'"
).fetchall()
by_collection = {}
for name, text in rows:
    by_collection.setdefault(name, []).append(text or "")
out = {}
for name, texts in sorted(by_collection.items()):
    digest = hashlib.sha256("\n\x1e\n".join(sorted(texts)).encode("utf-8")).hexdigest()
    out[name] = {"chunks": len(texts), "sha256_sorted_texts": digest}
print(json.dumps(out, indent=1))
