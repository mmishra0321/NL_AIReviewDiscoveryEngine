"""Local embeddings + persistent Chroma collection.

We use sentence-transformers (CPU, free, no API limits). Chroma is
persistent — the directory ships in the repo so deployment is zero-setup.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from src.config import CHROMA_COLLECTION, CHROMA_DIR, EMBED_MODEL
from src.lexicon import detect_features
from src.schema import Review

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    log.info("Loading embedding model: %s", EMBED_MODEL)
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def upsert_reviews(reviews: Iterable[Review], *, only_relevant: bool = True) -> int:
    """Upsert reviews into Chroma. Returns count upserted."""
    coll = get_collection()
    batch_texts: list[str] = []
    batch_ids: list[str] = []
    batch_meta: list[dict] = []

    for r in reviews:
        if only_relevant and not r.is_relevant:
            continue
        feats = r.features_mentioned or detect_features(r.text)
        batch_texts.append(r.text)
        batch_ids.append(r.id)
        batch_meta.append(
            {
                "source": r.source,
                "rating": r.rating if r.rating is not None else -1,
                "date": r.date.isoformat() if r.date else "",
                "url": r.url or "",
                "canonical_tags": ",".join(r.canonical_tags),
                "features": ",".join(feats),
                "author": (r.author or "")[:60],
            }
        )

    if not batch_ids:
        return 0

    # Chroma upserts in chunks to keep memory reasonable
    CHUNK = 200
    total = 0
    for i in range(0, len(batch_ids), CHUNK):
        ids = batch_ids[i : i + CHUNK]
        texts = batch_texts[i : i + CHUNK]
        metas = batch_meta[i : i + CHUNK]
        vectors = embed_texts(texts)
        coll.upsert(
            ids=ids,
            documents=texts,
            embeddings=vectors,
            metadatas=metas,
        )
        total += len(ids)
    log.info("Upserted %d reviews into Chroma collection %s", total, CHROMA_COLLECTION)
    return total


def collection_size() -> int:
    try:
        return get_collection().count()
    except Exception:                                            # noqa: BLE001
        return 0
