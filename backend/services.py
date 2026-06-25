"""Service layer — caches expensive resources + adapts internal data shapes
to the API response shapes the React frontend wants.

We intentionally keep this thin: the heavy lifting (RAG retrieve+answer,
scope wrapper, embeddings) all lives in `src/`. This module just wires it
to FastAPI handlers and adds small DTO transforms + in-memory caches.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.canonical import CANONICAL_QUESTIONS, QUESTION_BY_ID
from src.config import METADATA_PATH
from src.pipeline.normalize import load_canonical_store
from src.rag.answer import AnsweredQuestion, answer_question
from src.rag.precompute import load_canonical_answers
from src.rag.scope import OUT_OF_SCOPE_MESSAGE, evaluate_scope
from src.schema import Review

log = logging.getLogger(__name__)


# ---------------- Cached resource loaders ----------------

@lru_cache(maxsize=1)
def reviews_by_id() -> dict[str, Review]:
    """All normalized reviews indexed by stable id. Cached for the lifetime
    of the process; restart the server to pick up a fresh refresh."""
    store = load_canonical_store()
    log.info("Loaded %d normalized reviews into in-memory index.", len(store))
    return {r.id: r for r in store}


@lru_cache(maxsize=1)
def all_reviews() -> list[Review]:
    return list(reviews_by_id().values())


@lru_cache(maxsize=1)
def canonical_answers() -> dict[str, Any]:
    """The precomputed canonical answers dict (whole file)."""
    return load_canonical_answers()


@lru_cache(maxsize=1)
def metadata() -> dict[str, Any]:
    if not Path(METADATA_PATH).exists():
        return {"last_refresh_utc": None}
    return json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))


def invalidate_caches() -> None:
    """Called by /api/admin/reload — picks up a new pipeline run without restart."""
    reviews_by_id.cache_clear()
    all_reviews.cache_clear()
    canonical_answers.cache_clear()
    metadata.cache_clear()


# ---------------- DTO transforms ----------------

def review_to_dto(r: Review) -> dict[str, Any]:
    """Frontend-friendly review shape. Drops fields the UI doesn't need."""
    return {
        "id": r.id,
        "source": r.source,
        "text": r.text,
        "rating": r.rating,
        "author": r.author,
        "date": r.date.isoformat() if r.date else None,
        "url": r.url,
        "locale": r.locale,
        "features_mentioned": r.features_mentioned,
        "canonical_tags": r.canonical_tags,
        "user_segments": r.user_segments,
    }


def reviews_for_ids(ids: list[str]) -> list[dict[str, Any]]:
    """Hydrate a list of review ids to full DTOs, preserving input order."""
    idx = reviews_by_id()
    out: list[dict[str, Any]] = []
    for rid in ids:
        r = idx.get(rid)
        if r is not None:
            out.append(review_to_dto(r))
    return out


# ---------------- Canonical Q&A ----------------

def list_canonical_summaries() -> list[dict[str, Any]]:
    """Card-level summary for the home grid — no review hydration here
    (keeps the home payload small)."""
    answers = canonical_answers().get("answers", {})
    out: list[dict[str, Any]] = []
    for q in CANONICAL_QUESTIONS:
        a = answers.get(q.id)
        out.append({
            "id": q.id,
            "short": q.short,
            "full": q.full,
            "description": q.description,
            "has_answer": a is not None,
            "confidence": a.get("confidence") if a else None,
            "preview": (a["answer"][:240] + "…") if a and len(a.get("answer", "")) > 240 else (a.get("answer") if a else None),
            "review_count": len(a.get("review_ids", [])) if a else 0,
            "spotify_features_mentioned": (a or {}).get("spotify_features_mentioned", []),
            "user_segments_affected": (a or {}).get("user_segments_affected", []),
        })
    return out


def get_canonical_detail(qid: str) -> dict[str, Any] | None:
    """Full payload for one canonical question: answer + paginated reviews."""
    q = QUESTION_BY_ID.get(qid)
    if q is None:
        return None
    a = canonical_answers().get("answers", {}).get(qid)
    if a is None:
        return None
    return {
        "id": q.id,
        "short": q.short,
        "full": q.full,
        "description": q.description,
        "answer": a["answer"],
        "spotify_features_mentioned": a.get("spotify_features_mentioned", []),
        "user_segments_affected": a.get("user_segments_affected", []),
        "confidence": a.get("confidence"),
        "reviews": reviews_for_ids(a.get("review_ids", [])),
    }


# ---------------- Custom Q (scope + live RAG) ----------------

def ask_custom_question(question: str) -> dict[str, Any]:
    """Hybrid scope check, then live RAG if in-scope. Returns a response
    shape the UI can render directly."""
    scope = evaluate_scope(question)
    if not scope.in_scope:
        return {
            "in_scope": False,
            "scope_confidence": scope.confidence,
            "max_similarity": scope.max_similarity,
            "nearest_canonical_id": scope.nearest_canonical_id,
            "reason": scope.reason,
            "message": OUT_OF_SCOPE_MESSAGE,
        }

    res: AnsweredQuestion | None = answer_question(question)
    if res is None:
        return {
            "in_scope": True,
            "scope_confidence": scope.confidence,
            "max_similarity": scope.max_similarity,
            "nearest_canonical_id": scope.nearest_canonical_id,
            "answer": None,
            "reviews": [],
            "error": "No supporting reviews retrieved.",
        }

    return {
        "in_scope": True,
        "scope_confidence": scope.confidence,
        "max_similarity": scope.max_similarity,
        "nearest_canonical_id": scope.nearest_canonical_id,
        "question": res.question,
        "answer": res.answer.answer,
        "spotify_features_mentioned": res.answer.spotify_features_mentioned,
        "user_segments_affected": res.answer.user_segments_affected,
        "confidence": res.answer.confidence,
        "reviews": [
            review_to_dto(reviews_by_id().get(r.id) or Review(
                id=r.id, source="curated_seed", source_id=r.id, text=r.text,
            ))
            for r in res.reviews
        ],
    }


# ---------------- Review browse ----------------

def list_reviews(
    *,
    source: str | None = None,
    q: str | None = None,
    canonical_tag: str | None = None,
    relevant_only: bool = False,
    page: int = 1,
    size: int = 25,
) -> dict[str, Any]:
    """Paginated, filterable review list for the raw-data tab."""
    items = all_reviews()
    if relevant_only:
        items = [r for r in items if r.is_relevant]
    if source:
        items = [r for r in items if r.source == source]
    if canonical_tag:
        items = [r for r in items if canonical_tag in (r.canonical_tags or [])]
    if q:
        ql = q.lower()
        items = [r for r in items if ql in (r.text or "").lower()]

    total = len(items)
    page = max(1, page)
    size = max(1, min(100, size))
    start = (page - 1) * size
    sliced = items[start : start + size]
    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
        "items": [review_to_dto(r) for r in sliced],
    }
