"""Request-local, bounded entity expansion for an existing graph projection."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from ingestion.entity_normalization import normalize_entities
from vectordb._base_manager import HAS_BM25, BM25Okapi, Document, _tokenize_for_bm25


class EntityIndex:
    def __init__(self, projection: Any, chunks: dict[str, Document]) -> None:
        self.labels = {str(key): str(data["label"])
                       for key, data in projection.nodes(data=True) if data.get("kind") == "entity"}
        self.ids = sorted(self.labels, key=lambda key: (self.labels[key], key))
        self.chunks = chunks
        self.mentions: dict[str, set[str]] = defaultdict(set)
        self.neighbors: dict[str, dict[str, float]] = defaultdict(dict)
        for source, target, data in projection.edges(data=True):
            if data.get("kind") == "mentions" and source in chunks and target in self.labels:
                self.mentions[target].add(source)
            elif data.get("kind") == "co_occurs" and source in self.labels and target in self.labels:
                self.neighbors[source][target] = float((data.get("attributes") or {}).get("weight", 1))
        tokens = [_tokenize_for_bm25(self.labels[key]) for key in self.ids]
        self.bm25 = BM25Okapi(tokens) if HAS_BM25 and tokens else None

    def search(self, entities: Sequence[str], *, sources: Sequence[str] | None = None,
               ) -> tuple[list[Document], list[str], int]:
        seeds: set[str] = set()
        for entity in normalize_entities(entities):
            exact = [key for key in self.ids if self.labels[key] == entity]
            if exact:
                seeds.update(exact)
            elif self.bm25 is not None:
                scores = self.bm25.get_scores(_tokenize_for_bm25(entity))
                ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], self.ids[i]))
                seeds.update(self.ids[i] for i in ranked[:3] if scores[i] > 0)
        frontier = sorted(seeds)
        visited = set(frontier)
        ordered = list(frontier)
        hops = 0
        for depth in (1, 2):
            weights: dict[str, float] = defaultdict(float)
            for key in frontier:
                for neighbor, weight in self.neighbors.get(key, {}).items():
                    if neighbor not in visited:
                        weights[neighbor] += weight
            frontier = sorted(weights, key=lambda key: (-weights[key], key))[:50]
            if not frontier:
                break
            visited.update(frontier)
            ordered.extend(frontier)
            hops = depth
        allowed = {source.strip().casefold() for source in sources} if sources is not None else None
        documents: list[Document] = []
        seen: set[str] = set()
        for entity_id in ordered:
            for chunk_id in sorted(self.mentions.get(entity_id, ())):
                doc = self.chunks[chunk_id]
                if chunk_id in seen or (allowed is not None and
                                        str(doc.metadata.get("source", "")).strip().casefold() not in allowed):
                    continue
                seen.add(chunk_id)
                documents.append(doc)
                if len(documents) == 50:
                    return documents, sorted(self.labels[key] for key in seeds), hops
        return documents, sorted(self.labels[key] for key in seeds), hops
