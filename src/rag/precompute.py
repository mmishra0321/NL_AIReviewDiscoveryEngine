"""Precompute the 6 canonical RAG answers at refresh time.

Result is written to data/insights/canonical_answers.json so the Streamlit
dashboard loads them instantly without making any LLM calls. Custom user
questions still hit the live RAG path through src/rag/answer.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.canonical import CANONICAL_QUESTIONS
from src.config import INSIGHTS_DIR
from src.rag.answer import answer_question

log = logging.getLogger(__name__)

CANONICAL_OUTPUT = INSIGHTS_DIR / "canonical_answers.json"


def precompute_all() -> dict:
    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "answers": {},
    }
    for q in CANONICAL_QUESTIONS:
        log.info("Computing canonical answer for %s...", q.id)
        ans = answer_question(q.full, filter_canonical=q.id)
        if ans is None:
            out["answers"][q.id] = None
            continue
        out["answers"][q.id] = {
            "question_id": q.id,
            "question_full": q.full,
            "question_short": q.short,
            "answer": ans.answer.answer,
            "spotify_features_mentioned": ans.answer.spotify_features_mentioned,
            "user_segments_affected": ans.answer.user_segments_affected,
            "confidence": ans.answer.confidence,
            "review_ids": [r.id for r in ans.reviews],
        }
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    CANONICAL_OUTPUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", CANONICAL_OUTPUT)
    return out


def load_canonical_answers() -> dict:
    if not CANONICAL_OUTPUT.exists():
        return {"generated_at": None, "answers": {}}
    return json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    precompute_all()
