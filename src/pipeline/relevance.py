"""Discovery-relevance classifier.

Goes through normalized reviews, batches them to Groq, and tags each as
relevant/irrelevant + (if relevant) which of the 6 canonical questions
it supports.

Most reviews are bug complaints (audio quality, login, premium issues)
that are irrelevant to *discovery*. This stage prunes hard so downstream
clustering and RAG operate on signal only.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from tqdm import tqdm

from src.canonical import CANONICAL_QUESTIONS
from src.config import RELEVANCE_BATCH_SIZE
from src.lexicon import feature_lexicon_for_prompt
from src.pipeline.groq_client import fast_client
from src.schema import Review

log = logging.getLogger(__name__)

CANONICAL_LIST_PROMPT = "\n".join(
    f"- {q.id}: {q.full}" for q in CANONICAL_QUESTIONS
)

SYSTEM_PROMPT = f"""You are an expert PM analyst classifying Spotify user reviews.

For each review, decide:
1. is_relevant: TRUE only if the review is about *music discovery*, *recommendations*,
   *repetitive listening*, *exploring new artists/genres*, or *Spotify discovery
   surfaces*. Bug reports, login issues, billing, audio quality, podcast/audiobook
   specific issues are NOT relevant unless they directly impact discovery.
2. canonical_tags: which of these canonical questions does this review support?
   (zero, one, or many)
{CANONICAL_LIST_PROMPT}

You are aware of these Spotify features when interpreting reviews:
{feature_lexicon_for_prompt()}

Output STRICT JSON shaped exactly like:
{{
  "verdicts": [
    {{"id": "<review id>", "is_relevant": true|false,
      "reason": "<one short clause>",
      "canonical_tags": ["Q1_struggle", ...] }}
  ]
}}

Only include entries for reviews provided. Do not invent IDs.
"""


def _batch(items: list[Review], size: int) -> Iterable[list[Review]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _format_user_payload(batch: list[Review]) -> str:
    rows = [
        {"id": r.id, "text": r.text[:600], "rating": r.rating, "source": r.source}
        for r in batch
    ]
    return "Reviews to classify:\n" + json.dumps(rows, ensure_ascii=False)


def classify_relevance(
    reviews: list[Review],
    *,
    batch_size: int | None = None,
    show_progress: bool = True,
) -> list[Review]:
    """Tag each review's is_relevant + canonical_tags in place. Returns the list."""
    client = fast_client()
    bs = batch_size or RELEVANCE_BATCH_SIZE
    by_id = {r.id: r for r in reviews}
    batches = list(_batch(reviews, bs))
    iterator = tqdm(batches, desc="Classifying relevance") if show_progress else batches

    for batch in iterator:
        try:
            data = client.chat_json(
                system=SYSTEM_PROMPT,
                user=_format_user_payload(batch),
                max_tokens=2048,
                temperature=0.0,
            )
        except Exception as exc:                                # noqa: BLE001
            log.warning("Relevance batch failed: %s", exc)
            continue

        verdicts = data.get("verdicts", []) if isinstance(data, dict) else []
        for v in verdicts:
            rid = v.get("id")
            if rid not in by_id:
                continue
            target = by_id[rid]
            target.is_relevant = bool(v.get("is_relevant", False))
            target.relevance_reason = v.get("reason", "")
            target.canonical_tags = [
                t for t in v.get("canonical_tags", [])
                if any(t == q.id for q in CANONICAL_QUESTIONS)
            ]
    return reviews


def filter_relevant(reviews: list[Review]) -> list[Review]:
    return [r for r in reviews if r.is_relevant]
