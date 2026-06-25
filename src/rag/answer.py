"""RAG answer generation — assemble retrieved reviews + question + lexicon
into a strict prompt and ask Groq for a structured synthesis.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.lexicon import feature_lexicon_for_prompt
from src.pipeline.groq_client import default_client
from src.rag.retrieve import RetrievedReview, retrieve
from src.schema import RagAnswer

log = logging.getLogger(__name__)


SYSTEM_PROMPT = f"""You are a senior PM analyst at Spotify, synthesising user
review evidence to answer ONE focused question.

GROUND RULES (strict):
1. Use ONLY the provided reviews as evidence. Do NOT invent data points.
2. If reviews disagree, surface the disagreement.
3. Cite Spotify features by their canonical names when reviews mention them.
4. Identify user segments (free vs Premium, regional / language, casual vs heavy,
   age cohort, niche-genre) when reviews indicate them.
5. Keep the answer concise (160-220 words). Avoid filler.
6. Note ALL review IDs that supported your synthesis under supporting_review_ids.

Spotify feature lexicon for canonical naming:
{feature_lexicon_for_prompt()}

Output STRICT JSON exactly like:
{{
  "answer": "<160-220 word synthesis>",
  "spotify_features_mentioned": ["Discover Weekly", "Daily Mix", ...],
  "user_segments_affected": ["premium", "regional_indian", ...],
  "supporting_review_ids": ["<id1>", "<id2>", ...],
  "confidence": "high" | "medium" | "low"
}}

Confidence rubric:
- high  : 8+ reviews directly support, multiple sources/segments agree
- medium: 4-7 reviews support, some signal divergence
- low   : <4 reviews support OR heavy disagreement
"""


def _format_reviews_for_prompt(reviews: list[RetrievedReview]) -> str:
    rows = []
    for r in reviews:
        rows.append(
            {
                "id": r.id,
                "source": r.metadata.get("source", "unknown"),
                "rating": r.metadata.get("rating", -1),
                "text": r.text[:600],
                "features": r.metadata.get("features", ""),
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=1)


@dataclass
class AnsweredQuestion:
    question: str
    answer: RagAnswer
    reviews: list[RetrievedReview]      # in the same order as supporting_review_ids


def answer_question(
    question: str,
    *,
    filter_canonical: str | None = None,
    k_initial: int | None = None,
    k_final: int | None = None,
) -> AnsweredQuestion | None:
    reviews = retrieve(
        question,
        k_initial=k_initial,
        k_final=k_final,
        filter_canonical=filter_canonical,
    )
    if not reviews:
        log.warning("No reviews retrieved for question: %s", question)
        return None

    user_payload = (
        f"Question: {question}\n\n"
        f"Reviews ({len(reviews)} retrieved):\n{_format_reviews_for_prompt(reviews)}"
    )

    rag = default_client().chat_pydantic(
        system=SYSTEM_PROMPT,
        user=user_payload,
        schema=RagAnswer,
        max_tokens=1200,
        temperature=0.2,
    )
    if rag is None:
        # Fallback: minimal answer pointing to reviews so the UI still works
        rag = RagAnswer(
            answer=(
                "The synthesiser is temporarily unavailable. Here are the most relevant "
                "reviews retrieved for this question; please read them directly."
            ),
            supporting_review_ids=[r.id for r in reviews],
            confidence="low",
        )

    # Re-order returned reviews to match supporting_review_ids order (then append rest)
    review_by_id = {r.id: r for r in reviews}
    ordered: list[RetrievedReview] = []
    seen: set[str] = set()
    for rid in rag.supporting_review_ids:
        if rid in review_by_id:
            ordered.append(review_by_id[rid])
            seen.add(rid)
    for r in reviews:
        if r.id not in seen:
            ordered.append(r)

    return AnsweredQuestion(question=question, answer=rag, reviews=ordered)
