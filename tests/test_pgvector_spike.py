"""Contracts for the offline Phase D comparison; no production DB required."""
import json

import pytest
from rank_bm25 import BM25Okapi

from scripts.pgvector_spike import chroma_search, pg_search, rrf, score_rows


def test_rrf_deduplicates_and_breaks_ties_by_id():
    assert rrf([[2, 2, 1], [1, 2]]) == [1, 2]
    assert rrf([]) == []


def test_pg_parameter_binding_and_transaction_local_tenant():
    class Cursor:
        def execute(self, sql, params):
            if "set_config" in sql:
                assert params == ("aircargo",)
                assert "true" in sql
            else:
                assert params == ("[1.0,0.0]", "aircargo", "[1.0,0.0]", 2,
                                  "cargo", "aircargo", 2, 4)

        def fetchall(self):
            return [(3, 0.03), (1, 0.02)]

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

    assert pg_search(Connection(), [1, 0], "cargo", "aircargo", 2) == [3, 1]


def test_chroma_uses_real_bm25_api():
    texts = ["cargo", "train", "truck"]
    bm25 = BM25Okapi([text.split() for text in texts])

    class Collection:
        def query(self, **kwargs):
            assert kwargs == {"query_embeddings": [[1.0, 0.0]], "n_results": 2}
            return {"ids": [["2", "0"]]}

    assert chroma_search(Collection(), bm25, texts, [1.0, 0.0], "cargo", 2) == [0, 2]


def test_scoring_caps_aggregate_context():
    cases = [{"case_id": "one", "query": "cargo", "kws": ["needle"]}]
    result = score_rows(cases, [[0, 1]], ["x" * 6000, "needle"])
    assert result["mean_context_recall"] == 0
    assert score_rows(cases, [[1, 0]], ["x" * 6000, "needle"])["mean_context_recall"] == 1
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("rankings", [[[2]], [[-1]], [[True]]])
def test_scoring_rejects_bad_indices(rankings):
    with pytest.raises(ValueError):
        score_rows([{"case_id": "one", "query": "x", "kws": ["x"]}], rankings, ["x"])


def test_scoring_rejects_mismatched_rows():
    with pytest.raises(ValueError):
        score_rows([{"case_id": "one", "query": "x", "kws": []}], [], ["x"])
