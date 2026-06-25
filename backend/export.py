"""Multi-sheet Excel export — used by GET /api/export.xlsx.

Sheets:
1. Canonical Q&A   — the 6 precomputed answers
2. Reviews         — all normalized reviews (incl. raw + derived fields)
3. Themes / Tags   — counts per canonical tag and Spotify feature
4. Metadata        — last refresh, sources, totals
"""
from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from src.canonical import CANONICAL_QUESTIONS
from backend import services


def build_workbook() -> bytes:
    """Return an in-memory .xlsx as bytes."""
    buf = io.BytesIO()

    canonical_rows: list[dict[str, Any]] = []
    answers = services.canonical_answers().get("answers", {})
    for q in CANONICAL_QUESTIONS:
        a = answers.get(q.id) or {}
        canonical_rows.append({
            "question_id": q.id,
            "question": q.full,
            "answer": a.get("answer", ""),
            "confidence": a.get("confidence", ""),
            "spotify_features_mentioned": ", ".join(a.get("spotify_features_mentioned", []) or []),
            "user_segments_affected": ", ".join(a.get("user_segments_affected", []) or []),
            "supporting_review_count": len(a.get("review_ids", []) or []),
        })

    reviews_rows: list[dict[str, Any]] = []
    for r in services.all_reviews():
        reviews_rows.append({
            "id": r.id,
            "source": r.source,
            "rating": r.rating,
            "author": r.author,
            "date": r.date.isoformat() if r.date else None,
            "locale": r.locale,
            "is_relevant": r.is_relevant,
            "canonical_tags": ", ".join(r.canonical_tags or []),
            "features_mentioned": ", ".join(r.features_mentioned or []),
            "text": r.text,
            "url": r.url,
        })

    meta = services.metadata()
    tag_rows = [{"canonical_tag": k, "review_count": v}
                for k, v in (meta.get("by_canonical_tag") or {}).items()]
    feature_rows = [{"feature": k, "mention_count": v}
                    for k, v in (meta.get("feature_mention_counts") or {}).items()]
    source_rows = [{"source": k, "review_count": v}
                   for k, v in (meta.get("by_source") or {}).items()]
    meta_summary = [
        {"key": "last_refresh_utc", "value": meta.get("last_refresh_utc")},
        {"key": "total_normalized", "value": meta.get("total_normalized")},
        {"key": "total_relevant",   "value": meta.get("total_relevant")},
        {"key": "chroma_collection_size", "value": meta.get("chroma_collection_size")},
    ]

    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        pd.DataFrame(canonical_rows).to_excel(xw, sheet_name="Canonical Q&A", index=False)
        pd.DataFrame(reviews_rows).to_excel(xw, sheet_name="Reviews", index=False)
        pd.DataFrame(tag_rows).to_excel(xw, sheet_name="Canonical Tags", index=False)
        pd.DataFrame(feature_rows).to_excel(xw, sheet_name="Spotify Features", index=False)
        pd.DataFrame(source_rows).to_excel(xw, sheet_name="By Source", index=False)
        pd.DataFrame(meta_summary).to_excel(xw, sheet_name="Metadata", index=False)

    buf.seek(0)
    return buf.read()
