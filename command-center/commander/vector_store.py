"""
Layer 2 — Live Semantic Store (ChromaDB).
Every event is embedded and stored as a vector on write.
At query time, semantic similarity search retrieves the most
relevant chunks from the entire mission history.

Commander is the SOLE writer. No agent writes directly.
"""
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_collection = None

COLLECTION_NAME = "secunet_mission"
CHROMA_PATH     = os.getenv("CHROMA_PATH", "/tmp/secunet_chroma")


def init() -> None:
    """Initialise ChromaDB persistent client. Called at CC startup."""
    global _client, _collection
    import chromadb
    from chromadb.config import Settings

    _client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB ready at %s — %d documents", CHROMA_PATH, _collection.count())


def _get_collection():
    if _collection is None:
        raise RuntimeError("Vector store not initialised — call init() first")
    return _collection


def add(documents: list[str], metadatas: list[dict], ids: list[str]) -> None:
    """
    Embed and store documents. Called by write_pipeline only.
    ChromaDB uses its default embedding function (all-MiniLM-L6-v2).
    """
    if not documents:
        return
    col = _get_collection()
    # Upsert so re-runs don't create duplicates
    col.upsert(documents=documents, metadatas=metadatas, ids=ids)


def query(
    query_text: str,
    n_results: int = 5,
    where: dict[str, Any] | None = None,
) -> list[dict]:
    """
    Semantic similarity search across entire mission history.
    Returns list of {document, metadata, distance} dicts.
    """
    col = _get_collection()
    count = col.count()
    if count == 0:
        return []

    n_results = min(n_results, count)
    kwargs: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results":   n_results,
        "include":     ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    try:
        results = col.query(**kwargs)
    except Exception as exc:
        logger.warning("ChromaDB query failed: %s", exc)
        return []

    chunks = []
    docs       = results.get("documents", [[]])[0]
    metas      = results.get("metadatas", [[]])[0]
    distances  = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        chunks.append({"document": doc, "metadata": meta, "distance": dist})

    return chunks


def count() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0


def reset() -> None:
    """Delete and recreate the ChromaDB collection (full wipe)."""
    global _collection
    if _client is None:
        return
    try:
        _client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection reset — 0 documents")
