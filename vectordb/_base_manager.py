"""
vectordb/_base_manager.py (canonical base implementation)

NOTE: This file is the canonical vector-store manager. The package-level
`vectordb.manager` wraps these symbols and adds tenant-aware caching on top.
Legacy root-level `manager` imports are kept through a compatibility shim.

Менеджер векторной БД для RAG-проекта.

Level 1: BGE-M3, Hybrid Search (BM25+Vector+RRF), Cross-Encoder Reranker
Level 2: Semantic Chunking
Level 3: Contextual Retrieval, Parent Document Retrieval, Multi-Query

Публичные функции:

- get_embeddings() — embedding model factory
- build_vector_store(docs, chunk_config) — режет на чанки, строит БД
- get_retriever(vector_store, chunks) — HybridRetriever
- add_contextual_headers(docs, llm) — Level 3: Contextual Retrieval
- ParentDocumentStore — Level 3: Parent Document Retrieval
- MultiQueryRetriever — Level 3: Multi-Query Retrieval
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
_BM25_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

try:
    from langchain_core.documents import Document  # type: ignore
except ImportError:
    from langchain.schema import Document  # type: ignore

RecursiveCharacterTextSplitter: Any | None = None
SemanticChunker: Any | None = None
HAS_SEMANTIC_CHUNKER: bool | None = None

# Vector-store backends are lazy-loaded so importing this module does not pull
# optional embedding/reranker stacks into sys.modules.
Chroma: Any | None = None
QdrantVectorStore: Any | None = None
QdrantClient: Any | None = None
HAS_CHROMA: bool | None = None
HAS_QDRANT: bool | None = None

# BM25
try:
    from rank_bm25 import BM25Okapi  # type: ignore
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

# Cross-encoder reranker
CrossEncoder: Any | None = None
HAS_CROSS_ENCODER: bool | None = None


# ---------------------------------------------------------------------------
# Embedding model factory
# ---------------------------------------------------------------------------

_cached_embeddings: Any = None


def _resolve_device(device: str | None = None) -> str:
    """Resolve the SentenceTransformers/CrossEncoder device.

    ``None``/``"auto"``/empty → detect cuda → mps → cpu. Detection is guarded:
    if torch is unavailable or probing raises, falls back to ``"cpu"``. Any
    other value (``"cpu"``, ``"cuda"``, ``"cuda:0"``, ``"mps"``) is used as-is.
    """
    if device is None:
        from config.settings import get_settings

        device = get_settings().rag_device

    normalized = (device or "").strip().lower()
    if normalized and normalized != "auto":
        return normalized

    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # torch missing or probe failed — CPU is always safe
        logger.debug("device auto-detection fell back to cpu", exc_info=True)
    return "cpu"


def _load_chroma() -> Any | None:
    global Chroma, HAS_CHROMA
    if HAS_CHROMA is False:
        return None
    if Chroma is not None:
        HAS_CHROMA = True
        return Chroma

    try:
        from langchain_chroma import Chroma as chroma_cls  # type: ignore
    except ImportError:
        HAS_CHROMA = False
        return None

    Chroma = chroma_cls
    HAS_CHROMA = True
    return chroma_cls


def _load_qdrant() -> tuple[Any, Any] | None:
    global QdrantClient, QdrantVectorStore, HAS_QDRANT
    if HAS_QDRANT is False:
        return None
    if QdrantClient is not None and QdrantVectorStore is not None:
        HAS_QDRANT = True
        return QdrantVectorStore, QdrantClient

    try:
        from langchain_qdrant import QdrantVectorStore as qdrant_store_cls  # type: ignore
        from qdrant_client import QdrantClient as qdrant_client_cls  # type: ignore
    except ImportError:
        HAS_QDRANT = False
        return None

    QdrantVectorStore = qdrant_store_cls
    QdrantClient = qdrant_client_cls
    HAS_QDRANT = True
    return qdrant_store_cls, qdrant_client_cls


def _load_recursive_text_splitter() -> Any:
    global RecursiveCharacterTextSplitter
    if RecursiveCharacterTextSplitter is not None:
        return RecursiveCharacterTextSplitter

    try:
        from langchain_text_splitters import (
            RecursiveCharacterTextSplitter as splitter_cls,  # type: ignore
        )
    except ImportError:
        from langchain.text_splitter import (
            RecursiveCharacterTextSplitter as splitter_cls,  # type: ignore
        )

    RecursiveCharacterTextSplitter = splitter_cls
    return splitter_cls


_PLACEHOLDER_API_KEYS = {"changeme", "change-me", "change_me", ""}


class _RemoteEmbeddings:
    """OpenAI/Mistral-compatible remote embedding backend.

    POSTs ``{model, input: [...]}`` with Bearer auth to ``url`` and batches the
    document list. Vectors are L2-normalized to match the local
    SentenceTransformer path (``normalize_embeddings=True``) so cosine similarity
    behaves identically across backends. The API key is read from the env var
    *named* by ``api_key_env`` — it is never persisted in settings or logs.
    ``embedding_dimension`` is the configured expected width; response vectors
    are validated against it so the declaration cannot silently lie.
    """

    def __init__(
        self,
        *,
        url: str,
        model: str,
        api_key: str,
        batch_size: int,
        timeout_sec: float,
        embedding_dimension: int = 1024,
    ) -> None:
        self._url = url
        self._model = model
        self._api_key = api_key
        self._batch_size = max(1, int(batch_size))
        self._timeout_sec = float(timeout_sec)
        self.embedding_dimension = max(1, int(embedding_dimension))
        from vectordb.embedder_manifest import EmbedderManifest

        self.manifest = EmbedderManifest(
            backend="remote",
            model_id=model,
            revision=None,
            revision_source="remote_unversioned",
            dimension=self.embedding_dimension,
            query_prompt="",
            document_prompt="",
            normalize=True,
        )

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(component * component for component in vector))
        if norm <= 0.0:
            return vector
        return [component / norm for component in vector]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import httpx

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        out: list[list[float]] = []
        expected_dim = self.embedding_dimension
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = httpx.post(
                self._url,
                headers=headers,
                json={"model": self._model, "input": batch},
                timeout=self._timeout_sec,
            )
            response.raise_for_status()
            data = response.json()
            # OpenAI/Mistral shape: {"data": [{"embedding": [...], "index": i}, ...]}
            rows = sorted(
                data.get("data") or [],
                key=lambda item: int(item.get("index", 0)),
            )
            if len(rows) != len(batch):
                raise RuntimeError(
                    f"Remote embeddings returned {len(rows)} vectors for "
                    f"{len(batch)} inputs"
                )
            for row in rows:
                vector = [float(x) for x in row.get("embedding") or []]
                if len(vector) != expected_dim:
                    raise RuntimeError(
                        f"Remote embeddings returned dimension {len(vector)}, "
                        f"expected {expected_dim}"
                    )
                out.append(self._normalize(vector))
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text])
        return vectors[0] if vectors else []


def _build_remote_embeddings(settings: Any) -> _RemoteEmbeddings:
    api_key_env = str(getattr(settings, "embedding_remote_api_key_env", "MISTRAL_API_KEY"))
    api_key = (os.getenv(api_key_env, "") or "").strip()
    if api_key.lower() in _PLACEHOLDER_API_KEYS:
        raise RuntimeError(
            f"{api_key_env} is required for the remote embedding backend "
            "(RAG_EMBEDDING_BACKEND=remote)"
        )
    url = str(getattr(settings, "embedding_remote_url", ""))
    model = str(getattr(settings, "embedding_remote_model", "mistral-embed"))
    # Safe default for older settings doubles that omit the field.
    raw_dimension = getattr(settings, "embedding_remote_dimension", 1024)
    try:
        embedding_dimension = max(1, int(raw_dimension or 1024))
    except (TypeError, ValueError):
        embedding_dimension = 1024
    logger.info("Using remote embedding backend: %s (model=%s)", url, model)
    return _RemoteEmbeddings(
        url=url,
        model=model,
        api_key=api_key,
        batch_size=int(getattr(settings, "embedding_remote_batch", 32)),
        timeout_sec=float(getattr(settings, "embedding_remote_timeout_sec", 60.0)),
        embedding_dimension=embedding_dimension,
    )


def get_embeddings(model_name: str | None = None) -> Any:
    """Создаёт LangChain-совместимый embedding объект.

    По умолчанию использует локальный SentenceTransformer; при
    ``RAG_EMBEDDING_BACKEND=remote`` — удалённый OpenAI/Mistral-совместимый
    backend (см. ``_RemoteEmbeddings``). Результат кешируется — повторный вызов
    возвращает тот же объект.
    """
    global _cached_embeddings
    if _cached_embeddings is not None:
        return _cached_embeddings

    from config.settings import get_settings

    settings = get_settings()

    # Remote backend is selected only when the caller did not pin a local model
    # name explicitly (forcing a model name implies the local ST path).
    if model_name is None:
        if str(getattr(settings, "embedding_backend", "local") or "local").strip().lower() == "remote":
            remote = _build_remote_embeddings(settings)
            _cached_embeddings = remote
            return remote
        model_name = settings.embedding_model

    logger.info("Loading embedding model: %s", model_name)
    start = time.time()

    from sentence_transformers import SentenceTransformer  # type: ignore

    class _STEmbeddings:
        """Минимальная LangChain-совместимая обёртка над SentenceTransformer."""
        def __init__(self, st_model: SentenceTransformer, model_id: str):
            self._model = st_model
            # Read-only declared width from the model metadata — never encode.
            self.embedding_dimension: int | None = None
            getter = getattr(st_model, "get_sentence_embedding_dimension", None)
            if callable(getter):
                try:
                    reported = getter()
                except Exception:
                    reported = None
                if reported is not None:
                    try:
                        dim = int(reported)
                    except (TypeError, ValueError):
                        dim = 0
                    if dim > 0:
                        self.embedding_dimension = dim
            from vectordb.embedder_manifest import local_manifest

            self.manifest = local_manifest(st_model, model_id, self.embedding_dimension)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._model.encode(texts, normalize_embeddings=True).tolist()

        def embed_query(self, text: str) -> list[float]:
            return self._model.encode([text], normalize_embeddings=True)[0].tolist()

    device = _resolve_device()
    logger.info("Embedding device: %s", device)
    revision = getattr(settings, "embedding_model_revision", None)
    model = SentenceTransformer(
        model_name, device=device, **({"revision": revision} if revision else {})
    )
    embeddings = _STEmbeddings(model, model_name)

    elapsed = time.time() - start
    logger.info("Embedding model loaded in %.1fs", elapsed)
    _cached_embeddings = embeddings
    return embeddings


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

_cached_reranker: Any = None


def _load_cross_encoder() -> Any | None:
    global CrossEncoder, HAS_CROSS_ENCODER
    if HAS_CROSS_ENCODER is False:
        return None
    if CrossEncoder is not None:
        HAS_CROSS_ENCODER = True
        return CrossEncoder

    try:
        from sentence_transformers import CrossEncoder as cross_encoder_cls  # type: ignore
    except ImportError:
        HAS_CROSS_ENCODER = False
        return None

    CrossEncoder = cross_encoder_cls
    HAS_CROSS_ENCODER = True
    return cross_encoder_cls


def get_reranker(model_name: str | None = None) -> Any | None:
    """Создаёт CrossEncoder reranker. Возвращает None если отключён или недоступен."""
    global _cached_reranker
    if _cached_reranker is not None:
        return _cached_reranker

    if model_name is None:
        from config.settings import get_settings
        model_name = get_settings().reranker_model

    if not model_name:
        return None

    cross_encoder_cls = _load_cross_encoder()
    if cross_encoder_cls is None:
        logger.warning("sentence-transformers not installed — reranker disabled")
        return None

    device = _resolve_device()
    logger.info("Loading reranker: %s (device=%s)", model_name, device)
    start = time.time()
    reranker = cross_encoder_cls(model_name, device=device)
    elapsed = time.time() - start
    logger.info("Reranker loaded in %.1fs", elapsed)
    _cached_reranker = reranker
    return reranker


# ---------------------------------------------------------------------------
# Hybrid Retriever: BM25 + Vector + Reranker
# ---------------------------------------------------------------------------

def _tokenize_for_bm25(text: str) -> list[str]:
    return _BM25_TOKEN_RE.findall(text.casefold())


def _rrf_document_key(doc: Document, prefix_chars: int = 200) -> str:
    metadata = doc.metadata or {}
    doc_id = metadata.get("doc_id") or metadata.get("source") or metadata.get("file_path")
    chunk_id = metadata.get("chunk_id") or metadata.get("chunk_index")

    if doc_id is not None and chunk_id is not None:
        return f"metadata:{doc_id}:{chunk_id}"

    digest = hashlib.sha256(doc.page_content.encode("utf-8")).hexdigest()
    prefix = doc.page_content[:prefix_chars]
    return f"content:{prefix}:{digest}"


class HybridRetriever:
    """Гибридный ретривер: BM25 (keyword) + Vector (semantic) + Reranker.

    Алгоритм:
    1. BM25 ищет top-k по ключевым словам (TF-IDF)
    2. Vector store ищет top-k по cosine similarity
    3. Reciprocal Rank Fusion (RRF) объединяет оба ранжирования
    4. Cross-encoder reranker пересчитывает релевантность top кандидатов
    5. Возвращает финальный top-n

    Если BM25 недоступен — fallback на чистый vector search.
    Если reranker недоступен — пропускает шаг 4.
    """

    def __init__(
        self,
        vector_store: Any,
        chunks: list[Document],
        retrieval_k: int = 20,
        rerank_k: int = 5,
        rrf_k: int = 60,
        doc_key_chars: int = 200,
        reranker: Any = None,
        use_bm25: bool = True,
        parent_expansion: bool = False,
        parent_expansion_window: int = 1,
        parent_expansion_max_chars: int = 2400,
        graph_projection: Any = None,
        rerank_batch: int | None = None,
    ):
        self._vector_store = vector_store
        self._chunks = chunks
        self._retrieval_k = retrieval_k
        self._rerank_k = rerank_k
        self._rrf_k = rrf_k
        self._doc_key_chars = doc_key_chars
        self._reranker = reranker
        self._rerank_batch = rerank_batch if rerank_batch and rerank_batch > 0 else None
        self._parent_expansion = parent_expansion
        self._parent_window = max(0, parent_expansion_window)
        self._parent_max_chars = parent_expansion_max_chars
        self._graph_projection = graph_projection
        self._graph_category_sources: dict[str, set[str]] = {}
        self._graph_chunk_sections: dict[str, str] = {}
        self._graph_section_chunks: dict[str, list[Document]] = {}
        self._entity_index: Any = None
        # Provenance of the projected graph, recorded by the runtime factory on
        # the projection's graph attributes; None when the caller set none.
        graph_attrs = getattr(graph_projection, "graph", None) or {}
        self._graph_version: str | None = graph_attrs.get("digest") or None
        self._entity_graph_status: str | None = graph_attrs.get("entity_graph_status") or None
        if graph_projection is not None:
            self._index_graph_projection(graph_projection)

        # Position of each chunk in ingestion order — neighbour lookup for
        # parent-expansion. Keyed the same way as RRF dedup, so documents
        # returned by the vector store map back to their ingestion position.
        self._chunk_positions: dict[str, int] = {}
        if parent_expansion and chunks:
            for idx, doc in enumerate(chunks):
                self._chunk_positions.setdefault(_rrf_document_key(doc, doc_key_chars), idx)

        # Build BM25 index
        self._bm25 = None
        if use_bm25 and HAS_BM25 and chunks:
            tokenized = [_tokenize_for_bm25(doc.page_content) for doc in chunks]
            self._bm25 = BM25Okapi(tokenized)
            logger.debug("BM25 index built: %d chunks", len(chunks))

    def _vector_search(self, query: str) -> list[Document]:
        try:
            if hasattr(self._vector_store, "similarity_search"):
                return self._vector_store.similarity_search(query, k=self._retrieval_k)
            else:
                retriever = self._vector_store.as_retriever(search_kwargs={"k": self._retrieval_k})
                return retriever.get_relevant_documents(query)
        except Exception as e:
            logger.warning("[HybridRetriever] Vector search error: %s", e)
            return []

    @staticmethod
    def _graph_chunk_identity(source: Any, chunk_index: Any) -> tuple[str, str] | None:
        if source is None or chunk_index is None:
            return None
        return str(source).strip().casefold(), str(chunk_index)

    @staticmethod
    def _graph_chunk_order(metadata: dict[str, Any], position: int) -> int:
        raw_index = metadata.get("chunk_index")
        if isinstance(raw_index, int) and not isinstance(raw_index, bool) and raw_index >= 0:
            return raw_index
        if isinstance(raw_index, str) and raw_index.isdecimal():
            return int(raw_index)
        return position

    def _index_graph_projection(self, projection: Any) -> None:
        docs_by_identity: dict[tuple[str, str], Document] = {}
        chunk_order: dict[str, int] = {}
        for position, doc in enumerate(self._chunks):
            metadata = doc.metadata or {}
            identity = self._graph_chunk_identity(
                metadata.get("source"), self._graph_chunk_order(metadata, position)
            )
            if identity is not None:
                docs_by_identity.setdefault(identity, doc)
            chunk_order.setdefault(_rrf_document_key(doc, self._doc_key_chars), position)

        node_data = dict(projection.nodes(data=True))
        graph_chunk_docs: dict[str, Document] = {}
        for node_id, data in node_data.items():
            attributes = data.get("attributes") or {}
            kind = data.get("kind")
            if kind == "document":
                source = attributes.get("source")
                raw_categories = attributes.get("categories") or ()
                if isinstance(raw_categories, str):
                    raw_categories = (raw_categories,)
                if source is not None:
                    for category in raw_categories:
                        category_key = str(category).strip().casefold()
                        if category_key:
                            self._graph_category_sources.setdefault(category_key, set()).add(
                                str(source)
                            )
            elif kind == "chunk":
                identity = self._graph_chunk_identity(
                    attributes.get("source"), attributes.get("chunk_index")
                )
                if identity is not None and identity in docs_by_identity:
                    graph_chunk_docs[str(node_id)] = docs_by_identity[identity]

        from ingestion.entity_retrieval import EntityIndex

        self._entity_index = EntityIndex(projection, graph_chunk_docs)
        for section_id, chunk_id, edge_data in projection.edges(data=True):
            if edge_data.get("kind") != "contains":
                continue
            attributes = edge_data.get("attributes") or {}
            if attributes.get("level") != "chunk":
                continue
            doc = graph_chunk_docs.get(str(chunk_id))
            if doc is None or (node_data.get(section_id) or {}).get("kind") != "section":
                continue
            section_key = str(section_id)
            doc_key = _rrf_document_key(doc, self._doc_key_chars)
            self._graph_chunk_sections[doc_key] = section_key
            self._graph_section_chunks.setdefault(section_key, []).append(doc)

        for section_docs in self._graph_section_chunks.values():
            section_docs.sort(
                key=lambda doc: chunk_order.get(
                    _rrf_document_key(doc, self._doc_key_chars), len(self._chunks)
                )
            )

    def _graph_sources_for_categories(
        self, categories: Sequence[str] | None
    ) -> list[str] | None:
        if not categories:
            return None
        sources: set[str] = set()
        for category in categories:
            sources.update(
                self._graph_category_sources.get(str(category).strip().casefold(), ())
            )
        return sorted(sources) or None

    @staticmethod
    def _source_key(doc: Document) -> str | None:
        source = (doc.metadata or {}).get("source")
        if source is None:
            return None
        return str(source).strip().casefold()

    def _vector_search_for_sources(
        self, query: str, sources: Sequence[str]
    ) -> list[Document]:
        source_filter = {"source": {"$in": list(sources)}}
        try:
            if hasattr(self._vector_store, "similarity_search"):
                try:
                    docs = self._vector_store.similarity_search(
                        query, k=self._retrieval_k, filter=source_filter
                    )
                except TypeError:
                    docs = self._vector_store.similarity_search(
                        query, k=self._retrieval_k
                    )
            else:
                try:
                    retriever = self._vector_store.as_retriever(
                        search_kwargs={"k": self._retrieval_k, "filter": source_filter}
                    )
                    docs = retriever.get_relevant_documents(query)
                except TypeError:
                    retriever = self._vector_store.as_retriever(
                        search_kwargs={"k": self._retrieval_k}
                    )
                    docs = retriever.get_relevant_documents(query)
        except Exception as e:
            logger.warning("[HybridRetriever] Filtered vector search error: %s", e)
            return []

        allowed = {source.strip().casefold() for source in sources}
        return [doc for doc in docs if self._source_key(doc) in allowed]

    def _graph_bm25_documents(
        self, query: str, sources: Sequence[str] | None
    ) -> list[Document]:
        if self._bm25 is None:
            return []
        allowed = (
            {source.strip().casefold() for source in sources}
            if sources is not None
            else None
        )
        scores = self._bm25.get_scores(_tokenize_for_bm25(query))
        eligible = [
            index
            for index in range(len(scores))
            if allowed is None or self._source_key(self._chunks[index]) in allowed
        ]
        top_indices = sorted(eligible, key=lambda index: scores[index], reverse=True)[
            : self._retrieval_k
        ]
        return [self._chunks[index] for index in top_indices if scores[index] > 0]

    def _apply_graph_coherence(self, docs: list[Document]) -> list[Document]:
        return self._graph_coherence_split(docs)[0]

    def _graph_coherence_split(
        self, docs: list[Document]
    ) -> tuple[list[Document], list[dict[str, Any]]]:
        """Section coherence: kept documents plus a record of every drop.

        The drop record names the rank, source, chunk and section of each
        document the filter removed and why, so a lost singleton source is
        visible in the trace rather than inferred (audit 2026-09-30, F5).
        """
        groups: dict[str, list[int]] = {}
        unmapped: set[int] = set()
        for rank, doc in enumerate(docs):
            section = self._graph_chunk_sections.get(
                _rrf_document_key(doc, self._doc_key_chars)
            )
            if section is None:
                unmapped.add(rank)
                continue
            groups.setdefault(section, []).append(rank)

        scores = {
            section: sum(1.0 / (rank + 1) for rank in ranks)
            for section, ranks in groups.items()
        }
        strongest = max(scores.values(), default=0.0)
        ordered: list[tuple[int, int]] = []
        dropped: list[dict[str, Any]] = []
        for rank, doc in enumerate(docs):
            if rank in unmapped:
                ordered.append((1, rank))
                continue
            section = self._graph_chunk_sections[
                _rrf_document_key(doc, self._doc_key_chars)
            ]
            if len(groups[section]) > 1:
                ordered.append((0, rank))
                continue
            strength = scores[section] / strongest if strongest else 0.0
            if strength <= 0.25 and scores[section] < strongest:
                metadata = doc.metadata or {}
                dropped.append({
                    "rank": rank,
                    "source": metadata.get("source"),
                    "chunk_index": metadata.get("chunk_index"),
                    "section": section,
                    "reason": "weak_singleton_section",
                    "relative_strength": round(strength, 4),
                })
                continue
            ordered.append((2, rank))

        ordered.sort()
        kept_ranks = [rank for _, rank in ordered[: self._rerank_k]]
        for _, rank in ordered[self._rerank_k:]:
            metadata = docs[rank].metadata or {}
            dropped.append({
                "rank": rank,
                "source": metadata.get("source"),
                "chunk_index": metadata.get("chunk_index"),
                "section": self._graph_chunk_sections.get(
                    _rrf_document_key(docs[rank], self._doc_key_chars)
                ),
                "reason": "beyond_rerank_k",
                "relative_strength": None,
            })
        return [docs[rank] for rank in kept_ranks], dropped

    def _expand_graph_sections(self, docs: list[Document]) -> list[Document]:
        used_keys = {_rrf_document_key(doc, self._doc_key_chars) for doc in docs}
        expanded: list[Document] = []
        for doc in docs:
            doc_key = _rrf_document_key(doc, self._doc_key_chars)
            section = self._graph_chunk_sections.get(doc_key)
            section_docs = self._graph_section_chunks.get(section or "", [])
            positions = [
                index
                for index, candidate in enumerate(section_docs)
                if _rrf_document_key(candidate, self._doc_key_chars) == doc_key
            ]
            if not positions:
                expanded.append(doc)
                continue

            before: list[str] = []
            after: list[str] = []
            budget = self._parent_max_chars - len(doc.page_content)
            position = positions[0]
            for distance in range(1, len(section_docs)):
                for side, sibling_position in (
                    (before, position - distance),
                    (after, position + distance),
                ):
                    if sibling_position < 0 or sibling_position >= len(section_docs):
                        continue
                    sibling = section_docs[sibling_position]
                    sibling_key = _rrf_document_key(sibling, self._doc_key_chars)
                    if sibling_key in used_keys:
                        continue
                    text = self._strip_contextual_header(sibling.page_content).strip()
                    if not text or len(text) > budget:
                        continue
                    budget -= len(text)
                    used_keys.add(sibling_key)
                    side.append(text)

            if not before and not after:
                expanded.append(doc)
                continue
            parts = list(reversed(before)) + [doc.page_content] + after
            expanded.append(
                Document(
                    page_content="\n\n".join(parts),
                    metadata={**(doc.metadata or {}), "graph_section_expanded": True},
                )
            )
        return expanded

    def get_vector_documents(self, query: str) -> list[Document]:
        """Vector-only retrieval path for cheap simple-query routing."""
        docs = self._vector_search(query)[:self._rerank_k]
        if self._parent_expansion and docs:
            docs = self._expand_parents(docs)
        return docs

    def get_graph_documents(
        self, query: str, *, categories: Sequence[str] | None = None
    ) -> list[Document]:
        """Structural retrieval with category prefilter and section coherence."""
        return self.get_graph_documents_with_path(query, categories=categories)[0]

    def get_graph_documents_with_path(
        self, query: str, *, categories: Sequence[str] | None = None,
        question_class: str = "single_hop", entities: Sequence[str] = (),
    ) -> tuple[list[Document], dict[str, Any] | None]:
        if self._graph_projection is None:
            return self.get_relevant_documents(query), None

        started = time.perf_counter()
        sources = self._graph_sources_for_categories(categories)
        vector_results = (
            self._vector_search_for_sources(query, sources)
            if sources is not None
            else self._vector_search(query)
        )
        bm25_results = self._graph_bm25_documents(query, sources)
        entity_docs: list[Document] = []
        matched: list[str] = []
        hops = 0
        if question_class in {"multi_hop", "aggregation", "global"}:
            entity_docs, matched, hops = self._entity_index.search(entities, sources=sources)
        merged = (
            self._rrf_merge(vector_results, bm25_results, entity_docs)
            if bm25_results or entity_docs
            else vector_results
        )
        pool_size = len(merged)
        pools_done = time.perf_counter()
        rerank_status = "not_configured"
        scores_by_key: dict[str, float] = {}
        duplicate_drops: list[dict[str, Any]] = []
        if self._reranker is not None and merged:
            scored, reranker_ok = self._rerank_scored_with_status(query, merged)
            merged = [doc for doc, _ in scored]
            scores_by_key, duplicate_drops, rerank_status = self._score_table(scored, reranker_ok)
        else:
            merged = merged[: self._rerank_k]
        rerank_done = time.perf_counter()
        coherent, dropped = self._graph_coherence_split(merged)
        # dropped = coherence drops first, duplicate-key drops after them.
        dropped = dropped + duplicate_drops
        expanded = self._expand_graph_sections(coherent)
        finished = time.perf_counter()
        sections = sorted({
            self._graph_chunk_sections[key]
            for doc in coherent
            if (key := _rrf_document_key(doc, self._doc_key_chars)) in self._graph_chunk_sections
        })
        return expanded, {
            "kind": "structural_entity" if entity_docs else "structural", "prefilter_applied": sources is not None,
            "sections": sections, "entities": matched, "hops": hops,
            "retrieved_contexts": len(merged), "retained_contexts": len(coherent),
            "expanded_contexts": sum(bool(doc.metadata.get("graph_section_expanded")) for doc in expanded),
            # Observability added 2026-09-30 (audit F3/F5/F7): what each source
            # contributed, what the filter removed, what the reranker said, how
            # long each stage took, and which graph answered.
            "categories": [str(category) for category in (categories or ())],
            "candidates": {
                "vector": len(vector_results), "bm25": len(bm25_results),
                "entity": len(entity_docs), "merged": pool_size,
            },
            "rerank_status": rerank_status,
            "rerank_scores": [
                scores_by_key.get(_rrf_document_key(doc, self._doc_key_chars))
                for doc in coherent
            ],
            "rerank_batch_effective": self._rerank_batch,
            "dropped": dropped,
            "timings_ms": {
                "pools": round((pools_done - started) * 1000.0, 3),
                "rerank": round((rerank_done - pools_done) * 1000.0, 3),
                "coherence_expand": round((finished - rerank_done) * 1000.0, 3),
                "total": round((finished - started) * 1000.0, 3),
            },
            "graph_version": self._graph_version,
            "entity_graph_status": self._entity_graph_status,
        }

    def get_relevant_documents(self, query: str) -> list[Document]:
        """Гибридный поиск с RRF и reranking."""
        return self.get_relevant_documents_with_path(query)[0]

    def get_relevant_documents_with_path(
        self, query: str
    ) -> tuple[list[Document], dict[str, Any]]:
        """Hybrid retrieval with the observability dict of the graph lane."""
        started = time.perf_counter()

        # Step 1: Vector search
        vector_results = self._vector_search(query)

        # Step 2: BM25 search
        bm25_results: list[Document] = []
        if self._bm25 is not None:
            tokenized_query = _tokenize_for_bm25(query)
            scores = self._bm25.get_scores(tokenized_query)
            top_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[: self._retrieval_k]
            bm25_results = [self._chunks[i] for i in top_indices if scores[i] > 0]

        # Step 3: Reciprocal Rank Fusion
        merged_before_rerank: list[Document]
        if bm25_results:
            merged_before_rerank = self._rrf_merge(vector_results, bm25_results)
        else:
            merged_before_rerank = vector_results
        pools_done = time.perf_counter()

        # Step 4: Reranker
        rerank_ran = self._reranker is not None and bool(merged_before_rerank)
        rerank_status = "not_configured"
        scores_by_key: dict[str, float] = {}
        duplicate_drops: list[dict[str, Any]] = []
        rerank_ms = 0.0
        selected_after_rerank_cut: list[Document]
        if rerank_ran:
            rerank_started = time.perf_counter()
            scored, reranker_ok = self._rerank_scored_with_status(query, merged_before_rerank)
            selected_after_rerank_cut = [doc for doc, _ in scored]
            scores_by_key, duplicate_drops, rerank_status = self._score_table(scored, reranker_ok)
            rerank_ms = round((time.perf_counter() - rerank_started) * 1000.0, 3)
        else:
            selected_after_rerank_cut = merged_before_rerank[: self._rerank_k]

        # Scores are looked up before parent expansion: expansion may replace
        # the selected objects and their content.
        rerank_scores: list[float | None] = []
        if rerank_ran:
            rerank_scores = [
                scores_by_key.get(_rrf_document_key(doc, self._doc_key_chars))
                for doc in selected_after_rerank_cut
            ]

        # Step 5: Parent expansion (post-rerank, selection unchanged)
        result_docs: list[Document]
        if self._parent_expansion and selected_after_rerank_cut:
            result_docs = self._expand_parents(selected_after_rerank_cut)
        else:
            result_docs = selected_after_rerank_cut
        finished = time.perf_counter()

        return result_docs, {
            "kind": "hybrid",
            "candidates": {
                "vector": len(vector_results),
                "bm25": len(bm25_results),
                "merged": len(merged_before_rerank),
            },
            "rerank_status": rerank_status,
            "rerank_scores": rerank_scores,
            "rerank_batch_effective": self._rerank_batch,
            "retrieved_contexts": len(merged_before_rerank),
            "retained_contexts": len(selected_after_rerank_cut),
            "dropped": duplicate_drops,
            "timings_ms": {
                "pools": round((pools_done - started) * 1000.0, 3),
                "rerank": rerank_ms,
                "total": round((finished - started) * 1000.0, 3),
            },
            "graph_version": None,
            "entity_graph_status": None,
        }

    def _rrf_merge(self, list_a: list[Document], list_b: list[Document],
                   *additional: list[Document]) -> list[Document]:
        """Reciprocal Rank Fusion: объединяет ранжированные списки.

        score(doc) = sum( 1 / (k + rank_in_list) ) для каждого списка.
        k = 60 (стандарт) — сглаживает доминирование высоких рангов.
        """
        scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for documents in (list_a, list_b, *additional):
            for rank, doc in enumerate(documents):
                key = _rrf_document_key(doc, self._doc_key_chars)
                scores[key] = scores.get(key, 0) + 1.0 / (self._rrf_k + rank)
                doc_map[key] = doc

        sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)
        return [doc_map[k] for k in sorted_keys]

    def _rerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Cross-encoder reranking: пересчитывает релевантность каждого документа."""
        return [doc for doc, _ in self._rerank_scored(query, docs)]

    def _rerank_scored(
        self, query: str, docs: list[Document]
    ) -> list[tuple[Document, float | None]]:
        """Pairs only; see _rerank_scored_with_status for the reranker outcome."""
        return self._rerank_scored_with_status(query, docs)[0]

    def _rerank_scored_with_status(
        self, query: str, docs: list[Document]
    ) -> tuple[list[tuple[Document, float | None]], bool]:
        """Rerank and keep each document's score beside it.

        Documents are returned as the same objects the caller passed, so the
        legacy selection contract is unchanged; a score is None on the
        reranker-error fallback (which keeps input order) and for NaN/Inf
        values, which keep their input order after every finite score. The
        second element says whether the reranker call itself succeeded.
        """
        if not docs:
            return [], True

        # Cooperative deadline (plan §3.1h): refuse new reranker work after wall.
        # Fail-closed: do not degrade to top-k as silent success after expiry.
        from utils.request_deadline import (
            RequestDeadlineExceeded,
            check_request_deadline,
            get_request_deadline,
        )

        check_request_deadline("retriever.rerank")

        pairs = [(query, doc.page_content) for doc in docs]
        try:
            if self._rerank_batch is not None and get_request_deadline() is not None:
                # A single predict call otherwise processes every library batch
                # even after the HTTP request stops waiting. Keep the configured
                # inference batch and check the same wall budget between batches.
                scores = []
                for start in range(0, len(pairs), self._rerank_batch):
                    check_request_deadline("retriever.rerank")
                    batch = pairs[start : start + self._rerank_batch]
                    batch_scores = self._reranker.predict(batch, batch_size=self._rerank_batch)
                    check_request_deadline("retriever.rerank")
                    if len(batch_scores) != len(batch):
                        raise ValueError("Reranker must return one score per pair")
                    scores.extend(batch_scores)
            elif self._rerank_batch is not None:
                scores = self._reranker.predict(pairs, batch_size=self._rerank_batch)
            else:
                scores = self._reranker.predict(pairs)
            check_request_deadline("retriever.rerank")
            # strict=True: predict returns exactly one score per (query, doc) pair.
            converted: list[float | None] = []
            for score in scores:
                value = float(score)
                converted.append(value if math.isfinite(value) else None)
            # Deterministic ordering: one stable sort with reverse=True on the
            # tuple key (score is finite, score or 0.0) — finite scores rank
            # first in descending order; NaN/Inf share the key and keep their
            # input order after every finite score.
            scored_docs = sorted(
                zip(docs, converted, strict=True),
                key=lambda item: (item[1] is not None, item[1] or 0.0),
                reverse=True,
            )
            return scored_docs[: self._rerank_k], True
        except RequestDeadlineExceeded:
            raise
        except Exception as e:
            logger.warning("[HybridRetriever] Reranker error: %s", e)
            return [(doc, None) for doc in docs[: self._rerank_k]], False

    def _score_table(
        self, scored: list[tuple[Document, float | None]], reranker_ok: bool = True
    ) -> tuple[dict[str, float], list[dict[str, Any]], str]:
        """Score/duplicate bookkeeping shared by the graph and hybrid paths.

        The maximum finite score wins when a document key repeats; every later
        duplicate becomes a ``duplicate_key`` drop. The status tells a clean
        rerank (``ok``) from NaN/Inf gaps (``partial``) and from the reranker
        exception fallback (``reranker_ok`` False). ``scored`` is never empty.
        """
        scores_by_key: dict[str, float] = {}
        duplicate_drops: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for rank, (doc, score) in enumerate(scored):
            key = _rrf_document_key(doc, self._doc_key_chars)
            if key in seen_keys:
                metadata = doc.metadata or {}
                duplicate_drops.append({
                    "rank": rank,
                    "source": metadata.get("source"),
                    "chunk_index": metadata.get("chunk_index"),
                    "section": None,
                    "reason": "duplicate_key",
                    "relative_strength": None,
                })
            else:
                seen_keys.add(key)
            if score is not None:
                current = scores_by_key.get(key)
                scores_by_key[key] = score if current is None else max(current, score)
        # The status follows the reranker outcome, not the count of usable
        # scores: a predict() that returned only NaN/Inf is a partial result;
        # the exception fallback is the only reranker error (review F-T-59-3).
        if not reranker_ok:
            rerank_status = "fallback:reranker_error"
        elif all(score is not None for _, score in scored):
            rerank_status = "ok"
        else:
            rerank_status = "partial"
        return scores_by_key, duplicate_drops, rerank_status

    @staticmethod
    def _strip_contextual_header(text: str) -> str:
        """Neighbour sections join an already-anchored core chunk — their own
        "[Контекст: ...]" line would only add noise to the merged text."""
        if text.startswith("[Контекст:"):
            first_nl = text.find("\n")
            if first_nl != -1:
                return text[first_nl + 1:]
        return text

    def _expand_parents(self, docs: list[Document]) -> list[Document]:
        """Parent-expansion: дополняет финальные top-k чанки соседними
        structural-секциями их source-документа.

        Чистый текст-lookup по порядку ингеста (self._chunks) — отбор
        BM25+RRF+reranker уже сделан и не меняется. Бьёт в кейсы, где
        retrieval находит правильный док, но не тем чанком
        (archive/docs/operations/2026-06-05-residual-miss-diagnosis.md, потенциал 8/8).
        """
        # Чанки, уже выбранные в top-k, и добавленные соседи не дублируются.
        used_keys = {_rrf_document_key(d, self._doc_key_chars) for d in docs}
        expanded: list[Document] = []
        for doc in docs:
            pos = self._chunk_positions.get(_rrf_document_key(doc, self._doc_key_chars))
            source = (doc.metadata or {}).get("source")
            if pos is None or source is None:
                expanded.append(doc)
                continue
            before: list[str] = []
            after: list[str] = []
            budget = self._parent_max_chars - len(doc.page_content)
            # Ближайшие секции первыми — у них больше шансов влезть в бюджет.
            for dist in range(1, self._parent_window + 1):
                for side, npos in ((before, pos - dist), (after, pos + dist)):
                    if npos < 0 or npos >= len(self._chunks):
                        continue
                    neighbor = self._chunks[npos]
                    if (neighbor.metadata or {}).get("source") != source:
                        continue
                    nkey = _rrf_document_key(neighbor, self._doc_key_chars)
                    if nkey in used_keys:
                        continue
                    text = self._strip_contextual_header(neighbor.page_content).strip()
                    if not text or len(text) > budget:
                        continue
                    budget -= len(text)
                    used_keys.add(nkey)
                    side.append(text)
            if not before and not after:
                expanded.append(doc)
                continue
            # before собран от ближнего к дальнему — разворачиваем в порядок документа.
            parts = list(reversed(before)) + [doc.page_content] + after
            expanded.append(Document(
                page_content="\n\n".join(parts),
                metadata={**(doc.metadata or {}), "parent_expanded": True},
            ))
        return expanded

    def invoke(self, query: str) -> list[Document]:
        return self.get_relevant_documents(query)


# ---------------------------------------------------------------------------
# Path/backend helpers
# ---------------------------------------------------------------------------

def _normalize_retrieval_strategy(settings: Any) -> str:
    strategy = str(getattr(settings, "retrieval_strategy", "hybrid") or "hybrid").strip().lower()
    if strategy in {"vector", "hybrid", "graph"}:
        return strategy
    return "hybrid"


def _project_root() -> Path:
    # vectordb/_base_manager.py -> repository root (parent of the vectordb
    # package), mirroring config.settings.PROJECT_ROOT and integrations.mock_inbox.
    # Returning the package directory made _data_dir() resolve to
    # vectordb/data/vectordb/, so _build_chroma/_build_qdrant wrote an invisible
    # store that production (settings.vectordb_chroma_dir, under <root>/data/) never
    # reads. (F-14 tail)
    return Path(__file__).resolve().parent.parent

def _data_dir() -> Path:
    root = _project_root()
    data = root / "data" / "vectordb"
    data.mkdir(parents=True, exist_ok=True)
    return data

def _get_backend() -> str:
    backend = os.getenv("VECTOR_DB_TYPE", "chroma").strip().lower()
    if backend not in {"chroma", "qdrant"}:
        backend = "chroma"
    return backend

def _build_text_splitter(chunk_size: int, chunk_overlap: int) -> Any:
    splitter_cls = _load_recursive_text_splitter()
    return splitter_cls(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


# ---------------------------------------------------------------------------
# Level 2: Semantic Chunking
# ---------------------------------------------------------------------------

def _load_semantic_chunker() -> Any | None:
    global HAS_SEMANTIC_CHUNKER, SemanticChunker
    if HAS_SEMANTIC_CHUNKER is False:
        return None
    if SemanticChunker is not None:
        HAS_SEMANTIC_CHUNKER = True
        return SemanticChunker

    try:
        from langchain_experimental.text_splitter import (
            SemanticChunker as semantic_chunker_cls,  # type: ignore
        )
    except ImportError:
        HAS_SEMANTIC_CHUNKER = False
        return None

    SemanticChunker = semantic_chunker_cls
    HAS_SEMANTIC_CHUNKER = True
    return semantic_chunker_cls


def semantic_split(
    docs: list[Document],
    embeddings: Any,
    breakpoint_threshold: float = 0.3,
    min_chunk_size: int = 100,
    max_chunk_size: int = 2000,
) -> list[Document]:
    """Семантический сплиттер через langchain_experimental.SemanticChunker."""
    _ = breakpoint_threshold

    if embeddings is None:
        logger.warning(
            "Embeddings are unavailable, fallback to RecursiveCharacterTextSplitter",
        )
        splitter = _build_text_splitter(max_chunk_size, min_chunk_size // 2)
        return splitter.split_documents(list(docs))

    semantic_chunker_cls = _load_semantic_chunker()
    if semantic_chunker_cls is not None:
        try:
            splitter = semantic_chunker_cls(embeddings)
            return splitter.split_documents(list(docs))
        except Exception as exc:
            logger.warning(
                "SemanticChunker failed, fallback to RecursiveCharacterTextSplitter: %s",
                exc,
            )

    splitter = _build_text_splitter(max_chunk_size, min_chunk_size // 2)
    return splitter.split_documents(list(docs))


# ---------------------------------------------------------------------------
# Markdown-structural chunking (opt-in)
# ---------------------------------------------------------------------------

# MarkdownHeaderTextSplitter оставляет в строке только printable-символы, а пробельные
# разделители, кроме обычного пробела, к ним не относятся: "10 000" выходило "10000",
# "a\tb" — "ab", одинокий "\r" склеивал строки. Перед сплиттером они становятся пробелом
# или переводом строки (те же границы строк, что у str.splitlines).
_SPACE_SEPARATORS = "\t\x1f\xa0              　"
_LINE_SEPARATORS = "\r\x0b\x0c\x1c\x1d\x1e\x85  "
_PLAIN_WHITESPACE = str.maketrans(
    {**dict.fromkeys(_SPACE_SEPARATORS, " "), **dict.fromkeys(_LINE_SEPARATORS, "\n")}
)


def plain_whitespace(text: str) -> str:
    """Whitespace the header splitter would delete, as a plain space or a line break."""
    return text.replace("\r\n", "\n").translate(_PLAIN_WHITESPACE)


def structural_split(
    docs: list[Document],
    max_chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """Split markdown by headers, then cap each section to ``max_chunk_size``.

    A chunk becomes a logical section (under its heading) instead of N raw chars.
    Pure text transform — no embeddings, so it is unit-testable without models.
    Falls back to the fixed splitter if a markdown header splitter is unavailable.
    """
    headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
    try:
        from langchain_text_splitters import MarkdownHeaderTextSplitter  # type: ignore
    except ImportError:
        try:
            from langchain.text_splitter import MarkdownHeaderTextSplitter  # type: ignore
        except ImportError:
            logger.warning(
                "MarkdownHeaderTextSplitter unavailable, fallback to RecursiveCharacterTextSplitter",
            )
            return _build_text_splitter(max_chunk_size, chunk_overlap).split_documents(list(docs))

    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    char_splitter = _build_text_splitter(max_chunk_size, chunk_overlap)

    out: list[Document] = []
    for doc in docs:
        try:
            sections = md_splitter.split_text(plain_whitespace(doc.page_content))
        except Exception as exc:
            logger.warning("MarkdownHeaderTextSplitter failed for one doc, fallback: %s", exc)
            sections = char_splitter.split_documents([doc])
        for section in sections:
            meta = dict(doc.metadata or {})
            meta.update(getattr(section, "metadata", {}) or {})
            content = section.page_content
            if len(content) > max_chunk_size:
                for piece in char_splitter.split_text(content):
                    out.append(Document(page_content=piece, metadata=dict(meta)))
            else:
                out.append(Document(page_content=content, metadata=dict(meta)))
    return out


def select_chunks(
    docs: list[Document],
    embeddings: Any,
    chunk_size: int,
    chunk_overlap: int,
    *,
    settings: Any = None,
    use_semantic: bool = False,
) -> list[Document]:
    """Single chunking-strategy selector shared by all build sites.

    Precedence: structural (opt-in flag) > semantic > fixed. With the structural
    flag off the result is identical to the previous semantic/fixed branch, so the
    default ingestion path is unchanged. Callers pass their already-resolved
    ``settings`` so the same settings instance drives the decision.
    """
    if settings is None:
        from config.settings import get_settings
        settings = get_settings()
    if getattr(settings, "structural_chunking", False):
        logger.info("Using markdown-structural chunking (opt-in)")
        return structural_split(list(docs), max_chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if settings.semantic_chunking or use_semantic:
        logger.info("Using semantic chunking (Level 2)")
        return semantic_split(
            list(docs), embeddings, min_chunk_size=chunk_overlap, max_chunk_size=chunk_size,
        )
    return _build_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap).split_documents(list(docs))


# ---------------------------------------------------------------------------
# Level 3: Contextual Retrieval
# ---------------------------------------------------------------------------


def add_contextual_headers(
    chunks: list[Document],
    llm: Any,
    full_documents: Optional[list[Document]] = None,
) -> list[Document]:
    """Добавляет контекстный заголовок к каждому чанку (Anthropic Contextual Retrieval).

    Идея: чанк сам по себе может быть непонятен ("Рекомендуемое масло: 5W-30").
    Добавляем краткое описание: "Из раздела 'Ошибка E21' документа errors.txt:
    Рекомендуемое масло: 5W-30".

    Это повышает точность retrieval на ~49% (по данным Anthropic).

    Если LLM недоступна, генерирует заголовок из metadata (source, page).
    """
    enriched: list[Document] = []

    # Группируем чанки по source документу для контекста
    source_texts: dict[str, str] = {}
    if full_documents:
        for doc in full_documents:
            src = (doc.metadata or {}).get("source", "unknown")
            source_texts[src] = doc.page_content[:2000]  # Первые 2000 символов

    for chunk in chunks:
        source = (chunk.metadata or {}).get("source", "unknown")

        if llm is not None:
            # LLM генерирует краткое описание контекста
            doc_preview = source_texts.get(source, "")[:500]
            prompt = (
                "Дан фрагмент документа и начало этого документа для контекста.\n"
                "Напиши ОДНО краткое предложение (до 30 слов), описывающее,\n"
                "о чём этот фрагмент и откуда он.\n"
                "Не повторяй содержимое фрагмента, просто опиши его место в документе.\n\n"
                f"Документ: {source}\n"
                f"Начало документа: {doc_preview}\n\n"
                f"Фрагмент:\n{chunk.page_content}\n\n"
                "Краткое описание контекста:"
            )
            try:
                header = llm.invoke(prompt).strip()
                if len(header) > 200:
                    header = header[:200]
            except Exception:
                header = f"Из документа {source}"
        else:
            # Fallback: генерируем из metadata (без LLM).
            # Несём markdown heading-path (h1..h4, которые проставляет
            # structural_split) — это даёт чанку-таблице якорь раздела
            # ("Обязательные поля") + тему дока, чего не хватало для запросов
            # класса "какие поля нужны для X" (см.
            # archive/docs/operations/2026-06-03-r7-llm-judged-baseline.md).
            meta = chunk.metadata or {}
            header = f"Из документа {source}"
            heading_path = [str(meta[h]).strip() for h in ("h1", "h2", "h3", "h4") if meta.get(h)]
            if heading_path:
                header += ", раздел: " + " › ".join(heading_path)
            page = meta.get("page", "")
            if page:
                header += f", стр. {page}"
            # Та же граница, что у LLM-пути: заголовок — якорь, не контент,
            # и его длина должна быть ограничена (см. manager.add_contextual_headers,
            # который больше не режет тело чанка и полагается на эту границу).
            if len(header) > 200:
                header = header[:200]

        # Prepend header to chunk content
        new_content = f"[Контекст: {header}]\n{chunk.page_content}"
        enriched.append(Document(
            page_content=new_content,
            metadata={**(chunk.metadata or {}), "contextual_header": header},
        ))

    return enriched


# ---------------------------------------------------------------------------
# Level 3: Parent Document Retrieval
# ---------------------------------------------------------------------------


class ParentDocumentStore:
    """Хранит маленькие чанки для поиска, но возвращает большие (parent) для контекста.

    Проблема: маленькие чанки (200-300 символов) → точный поиск, но мало контекста.
    Большие чанки (1000+) → много контекста, но размытый поиск.

    Решение: индексируем маленькие child-чанки, но при retrieval возвращаем
    parent-чанк (объединение нескольких child-ов с перекрытием).

    Пример:
        Документ: "AAAA BBBB CCCC DDDD"
        Parent chunks (1000 chars):  [AAAA BBBB] [CCCC DDDD]
        Child chunks  (300 chars):   [AAAA] [BBBB] [CCCC] [DDDD]
        Поиск по child, возврат parent.
    """

    def __init__(
        self,
        docs: list[Document],
        embeddings: Any,
        child_chunk_size: int = 300,
        child_overlap: int = 50,
        parent_chunk_size: int = 1200,
        parent_overlap: int = 200,
    ):
        self._embeddings = embeddings

        # Создаём parent chunks
        parent_splitter = _build_text_splitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_overlap,
        )
        self._parents: list[Document] = parent_splitter.split_documents(docs)

        # Создаём child chunks с привязкой к parent
        child_splitter = _build_text_splitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_overlap,
        )
        self._children: list[Document] = []
        self._child_to_parent: dict[int, int] = {}

        for parent_idx, parent in enumerate(self._parents):
            child_docs = child_splitter.split_documents([parent])
            for child in child_docs:
                child_idx = len(self._children)
                child.metadata = {
                    **(child.metadata or {}),
                    "parent_idx": parent_idx,
                }
                self._children.append(child)
                self._child_to_parent[child_idx] = parent_idx

        # Векторизуем children
        texts = [c.page_content for c in self._children]
        self._vectors = embeddings.embed_documents(texts)

        logger.debug("ParentDocumentStore: %d parents, %d children", len(self._parents), len(self._children))

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        """Ищет по child-чанкам, возвращает parent-чанки (дедуплицированные)."""
        q_vec = self._embeddings.embed_query(query)
        scores = [(i, self._cosine(q_vec, v)) for i, v in enumerate(self._vectors)]
        scores.sort(key=lambda x: x[1], reverse=True)

        seen_parents: set = set()
        results: list[Document] = []

        for child_idx, score in scores:
            parent_idx = self._child_to_parent[child_idx]
            if parent_idx not in seen_parents:
                seen_parents.add(parent_idx)
                results.append(self._parents[parent_idx])
                if len(results) >= k:
                    break

        return results

    def get_relevant_documents(self, query: str) -> list[Document]:
        from config.settings import get_settings  # noqa: PLC0415

        return self.similarity_search(query, k=get_settings().rerank_top_k)

    def get_children(self) -> list[Document]:
        """Возвращает child-чанки (для BM25 индекса)."""
        return self._children


# ---------------------------------------------------------------------------
# Level 3: Multi-Query Retriever
# ---------------------------------------------------------------------------


class MultiQueryRetriever:
    """Разбивает сложный вопрос на несколько подвопросов, ищет по каждому.

    Пример:
        Вопрос: "Что делать при ошибке E20 и покрывается ли ремонт гарантией?"
        Подвопросы:
            1. "Ошибка E20 действия при перегреве"
            2. "Гарантия покрытие ремонт"
        Поиск по каждому → объединение результатов через RRF.
    """

    def __init__(
        self,
        base_retriever: Any,
        llm: Any,
        max_queries: int = 3,
    ):
        self._retriever = base_retriever
        self._llm = llm
        self._max_queries = max_queries

    def get_relevant_documents(self, query: str) -> list[Document]:
        """Multi-query retrieval."""
        sub_queries = self._generate_sub_queries(query)
        if not sub_queries:
            return self._retriever.get_relevant_documents(query)

        # Retrieve for each sub-query
        all_results: list[list[Document]] = []
        for sq in sub_queries:
            try:
                docs = self._retriever.get_relevant_documents(sq)
                all_results.append(docs)
            except Exception:
                continue

        if not all_results:
            return self._retriever.get_relevant_documents(query)

        # Merge all results via RRF
        return self._rrf_merge_multiple(all_results)

    def _generate_sub_queries(self, query: str) -> list[str]:
        """Генерирует подвопросы через LLM."""
        if self._llm is None:
            return [query]

        prompt = (
            "Разбей вопрос пользователя на 2-3 независимых поисковых запроса.\n"
            "Каждый запрос должен искать один конкретный аспект вопроса.\n"
            "Если вопрос простой и не требует разбиения — верни его как есть.\n\n"
            f"Вопрос: {query}\n\n"
            "Выведи запросы, по одному на строку (2-3 строки, без нумерации):"
        )
        try:
            raw = self._llm.invoke(prompt).strip()
            lines = [ln.strip().lstrip("0123456789.-) ") for ln in raw.split("\n") if ln.strip()]
            # Фильтруем мусор
            queries = [ln for ln in lines if len(ln) >= 5][:self._max_queries]
            return queries if queries else [query]
        except Exception:
            return [query]

    def _rrf_merge_multiple(self, result_lists: list[list[Document]], k: int = 60) -> list[Document]:
        """RRF merge для нескольких списков."""
        from config.settings import get_settings

        settings = get_settings()
        key_chars = getattr(settings, "rrf_doc_key_chars", 200)
        rrf_k = getattr(settings, "rrf_k", k)
        scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for result_list in result_lists:
            for rank, doc in enumerate(result_list):
                key = _rrf_document_key(doc, key_chars)
                scores[key] = scores.get(key, 0) + 1.0 / (rrf_k + rank)
                doc_map[key] = doc

        sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
        return [doc_map[k] for k in sorted_keys]

    def invoke(self, query: str) -> list[Document]:
        return self.get_relevant_documents(query)


# ---------------------------------------------------------------------------
# Stub store (fallback if no vector DB available)
# ---------------------------------------------------------------------------

class QdrantStubStore:
    """In-memory stub for Qdrant when dependencies are missing."""

    def __init__(self, docs: Sequence[Document], embeddings: Any):
        self._docs: list[Document] = list(docs)
        self._embeddings = embeddings
        self._vectors: list[list[float]] = self._embed_documents()

    def _embed_documents(self) -> list[list[float]]:
        texts = [d.page_content for d in self._docs]
        return self._embeddings.embed_documents(texts)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def similarity_search(self, query: str, k: int = 6) -> list[Document]:
        q = self._embeddings.embed_query(query)
        scores = [(idx, self._cosine(q, v)) for idx, v in enumerate(self._vectors)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [self._docs[idx] for idx, _ in scores[:k]]

    def as_retriever(self, search_kwargs: Optional[dict[str, Any]] = None) -> "QdrantStubRetriever":
        search_kwargs = search_kwargs or {"k": 6}
        return QdrantStubRetriever(self, search_kwargs)


class QdrantStubRetriever:
    def __init__(self, store: QdrantStubStore, search_kwargs: dict[str, Any]):
        self._store = store
        self._k = int(search_kwargs.get("k", 6))

    def get_relevant_documents(self, query: str) -> list[Document]:
        return self._store.similarity_search(query, k=self._k)

    def invoke(self, query: str) -> list[Document]:
        return self.get_relevant_documents(query)


# ---------------------------------------------------------------------------
# Build vector store
# ---------------------------------------------------------------------------

def _build_chroma(docs: Sequence[Document], embeddings: Any) -> Any:
    chroma_cls = _load_chroma()
    if chroma_cls is None:
        raise ImportError(
            "Chroma not installed. Install 'langchain-chroma' "
            "or switch backend (VECTOR_DB_TYPE) to 'qdrant'."
        )
    chroma_dir = _data_dir() / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Building Chroma in %s", chroma_dir)
    from vectordb.embedder_manifest import open_chroma_for_write

    open_chroma_for_write(
        chroma_cls, embeddings, persist_directory=str(chroma_dir), collection_name="documents"
    )
    store = chroma_cls.from_documents(
        documents=list(docs),
        embedding=embeddings,
        persist_directory=str(chroma_dir),
        collection_name="documents",
    )
    if hasattr(store, "persist"):
        store.persist()
    logger.info("Chroma ready: %d chunks", len(docs))
    return store


def _build_qdrant(docs: Sequence[Document], embeddings: Any) -> Any:
    qdrant_backend = _load_qdrant()
    if qdrant_backend is None:
        logger.warning("Qdrant unavailable — using in-memory stub")
        return QdrantStubStore(docs, embeddings)
    qdrant_store_cls, qdrant_client_cls = qdrant_backend
    qdrant_dir = _data_dir() / "qdrant"
    qdrant_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Building local Qdrant in %s", qdrant_dir)
    try:
        client = qdrant_client_cls(path=str(qdrant_dir))
        store = qdrant_store_cls.from_documents(
            documents=list(docs),
            embedding=embeddings,
            client=client,
            collection_name="documents",
        )
        logger.info("Qdrant ready: %d chunks", len(docs))
        return store
    except Exception as e:
        logger.error("Qdrant init error: %r, falling back to in-memory stub", e)
        return QdrantStubStore(docs, embeddings)


def build_vector_store(
    docs: Sequence[Document],
    chunk_config: dict[str, int],
    embeddings: Any | None = None,
    use_semantic_chunking: bool = False,
) -> tuple[Any, list[Document]]:
    """Строит векторное хранилище из документов.

    Args:
        docs: исходные документы.
        chunk_config: {"chunk_size": int, "chunk_overlap": int}.
        embeddings: embedding model (если None — создаётся автоматически).
        use_semantic_chunking: True → семантический сплиттинг (Level 2).

    Returns:
        (vector_store, chunks) — хранилище и список чанков (нужен для BM25).
    """
    if not docs:
        raise ValueError("Document list is empty.")

    if embeddings is None:
        embeddings = get_embeddings()

    from config.settings import get_settings
    settings = get_settings()

    chunk_size = int(chunk_config.get("chunk_size", getattr(settings, "chunk_size", 800)))
    chunk_overlap = int(chunk_config.get("chunk_overlap", getattr(settings, "chunk_overlap", 200)))
    chunks = select_chunks(
        list(docs), embeddings, chunk_size, chunk_overlap,
        settings=settings, use_semantic=use_semantic_chunking,
    )

    backend = _get_backend()
    if getattr(settings, "structural_chunking", False):
        mode = "structural"
    elif settings.semantic_chunking or use_semantic_chunking:
        mode = "semantic"
    else:
        mode = f"fixed(size={chunk_size}, overlap={chunk_overlap})"
    logger.info("Backend: %s, chunks: %d, mode: %s", backend.upper(), len(chunks), mode)

    if backend == "qdrant":
        store = _build_qdrant(chunks, embeddings)
    else:
        store = _build_chroma(chunks, embeddings)

    try:
        setattr(store, "_source_docs", list(docs))
        setattr(store, "_source_embeddings", embeddings)
    except Exception:
        # Best-effort: these attrs back parent-doc/source-embedding retrieval;
        # log so a silent loss of those features is diagnosable.
        logger.debug("could not attach source docs/embeddings to store", exc_info=True)

    return store, chunks


# ---------------------------------------------------------------------------
# Build retriever
# ---------------------------------------------------------------------------


def build_retriever(
    docs: list[Document],
    embeddings: Any,
    vector_store: Any | None = None,
    chunks: list[Document] | None = None,
    k: int | None = None,
    graph_projection: Any = None,
) -> Any:
    """Builds a retriever according to current settings."""
    from config.settings import get_settings

    settings = get_settings()

    if settings.parent_child and graph_projection is None:
        logger.info("Retriever: ParentDocumentStore (parent_child=true)")
        return ParentDocumentStore(
            docs=docs,
            embeddings=embeddings,
            child_chunk_size=300,
            child_overlap=50,
            parent_chunk_size=1200,
            parent_overlap=200,
        )

    retrieval_k = k or settings.retrieval_top_k
    rerank_k = settings.rerank_top_k
    chunk_size = getattr(settings, "chunk_size", 800)
    chunk_overlap = getattr(settings, "chunk_overlap", 200)

    if vector_store is None or chunks is None:
        chunks = select_chunks(list(docs), embeddings, chunk_size, chunk_overlap, settings=settings)
        vector_store = QdrantStubStore(chunks, embeddings)

    retrieval_strategy = _normalize_retrieval_strategy(settings)
    use_hybrid_components = retrieval_strategy != "vector"
    use_bm25 = use_hybrid_components and settings.hybrid_search and chunks is not None
    reranker = get_reranker() if use_hybrid_components and settings.reranker_model else None
    parent_expansion = bool(getattr(settings, "parent_expansion", False))
    logger.info("Retriever: HybridRetriever (parent_child=false)")

    if use_bm25 or reranker or (parent_expansion and bool(chunks)) or graph_projection is not None:
        return HybridRetriever(
            vector_store=vector_store,
            chunks=chunks or [],
            retrieval_k=retrieval_k,
            rerank_k=rerank_k,
            rrf_k=getattr(settings, "rrf_k", 60),
            doc_key_chars=getattr(settings, "rrf_doc_key_chars", 200),
            reranker=reranker,
            use_bm25=use_bm25,
            parent_expansion=parent_expansion,
            parent_expansion_window=getattr(settings, "parent_expansion_window", 1),
            parent_expansion_max_chars=getattr(settings, "parent_expansion_max_chars", 2400),
            graph_projection=graph_projection,
            rerank_batch=_effective_rerank_batch(settings),
        )

    if hasattr(vector_store, "as_retriever"):
        return vector_store.as_retriever(search_kwargs={"k": rerank_k})

    class _SimpleRetriever:
        def __init__(self, store: Any, top_k: int):
            self._store = store
            self._k = top_k

        def get_relevant_documents(self, query: str) -> list[Document]:
            return self._store.similarity_search(query, k=self._k)

        def invoke(self, query: str) -> list[Document]:
            return self.get_relevant_documents(query)

    return _SimpleRetriever(vector_store, rerank_k)


# ---------------------------------------------------------------------------
# Get retriever (upgraded: hybrid + reranker)
# ---------------------------------------------------------------------------

def _effective_rerank_batch(settings: Any) -> int | None:
    """RAG_RERANK_BATCH as of this retriever build.

    The environment is re-read here so a runtime change applies to the next
    build (after reset_retriever_cache); with the variable unset the Settings
    value applies. Cached retrievers keep the batch they were built with
    (review F-T-59-2).
    """
    raw = os.getenv("RAG_RERANK_BATCH")
    if raw is not None and raw.strip():
        from config.settings import _parse_rerank_batch

        return _parse_rerank_batch(raw)
    value = getattr(settings, "rerank_batch", None)
    return value if isinstance(value, int) and value > 0 else None


def get_retriever(
    vector_store: Any,
    chunks: list[Document] | None = None,
    k: int | None = None,
    graph_projection: Any = None,
) -> Any:
    """Возвращает retriever с hybrid search и reranker.

    Args:
        vector_store: Chroma/Qdrant/Stub store.
        chunks: список чанков для BM25 индекса. Если None — только vector search.
        k: override для retrieval_top_k (по умолчанию из settings).

    Returns:
        HybridRetriever если доступны BM25/reranker или parent-expansion с
        чанками, иначе простой vector retriever.
    """
    source_docs = getattr(vector_store, "_source_docs", None)
    source_embeddings = getattr(vector_store, "_source_embeddings", None)
    if source_docs is not None and source_embeddings is not None:
        return build_retriever(
            docs=list(source_docs),
            embeddings=source_embeddings,
            vector_store=vector_store,
            chunks=chunks,
            k=k,
            graph_projection=graph_projection,
        )

    from config.settings import get_settings
    settings = get_settings()

    retrieval_k = k or settings.retrieval_top_k
    rerank_k = settings.rerank_top_k

    # Try to build hybrid retriever
    retrieval_strategy = _normalize_retrieval_strategy(settings)
    use_hybrid_components = retrieval_strategy != "vector"
    use_bm25 = use_hybrid_components and settings.hybrid_search and chunks is not None
    reranker = get_reranker() if use_hybrid_components and settings.reranker_model else None
    parent_expansion = bool(getattr(settings, "parent_expansion", False))

    if use_bm25 or reranker or (parent_expansion and bool(chunks)) or graph_projection is not None:
        return HybridRetriever(
            vector_store=vector_store,
            chunks=chunks or [],
            retrieval_k=retrieval_k,
            rerank_k=rerank_k,
            rrf_k=getattr(settings, "rrf_k", 60),
            doc_key_chars=getattr(settings, "rrf_doc_key_chars", 200),
            reranker=reranker,
            use_bm25=use_bm25,
            parent_expansion=parent_expansion,
            parent_expansion_window=getattr(settings, "parent_expansion_window", 1),
            parent_expansion_max_chars=getattr(settings, "parent_expansion_max_chars", 2400),
            graph_projection=graph_projection,
            rerank_batch=_effective_rerank_batch(settings),
        )

    # Fallback: simple vector retriever
    if hasattr(vector_store, "as_retriever"):
        return vector_store.as_retriever(search_kwargs={"k": rerank_k})

    class _SimpleRetriever:
        def __init__(self, store: Any, top_k: int):
            self._store = store
            self._k = top_k
        def get_relevant_documents(self, query: str) -> list[Document]:
            return self._store.similarity_search(query, k=self._k)
        def invoke(self, query: str) -> list[Document]:
            return self.get_relevant_documents(query)

    return _SimpleRetriever(vector_store, rerank_k)
