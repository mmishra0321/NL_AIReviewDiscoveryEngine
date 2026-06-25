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
from src.pipeline.groq_client import fast_client
from src.schema import Review

log = logging.getLogger(__name__)

CANONICAL_LIST_PROMPT = "\n".join(
    f"- {q.id}: {q.short}" for q in CANONICAL_QUESTIONS
)

# Compact system prompt - every token here multiplies by N batches. Aim ~350 tok.
SYSTEM_PROMPT = f"""Classify Spotify reviews for music-DISCOVERY relevance.

is_relevant=TRUE iff review touches: music discovery, recommendations, repetitive
listening, exploring new artists/genres, or Spotify discovery surfaces (Discover
Weekly, Daily Mix, Daylist, Release Radar, DJ, AI Playlist, Smart Shuffle, Blend,
Niche Mixes, Radio, Search, Home).
is_relevant=FALSE for: login, billing, audio quality, podcasts/audiobooks,
account, ads, sync - unless they directly affect discovery.

canonical_tags: zero or more of:
{CANONICAL_LIST_PROMPT}

Output strict JSON: {{"verdicts":[{{"id":"...","is_relevant":bool,"reason":"<8w>","canonical_tags":["Q1_struggle",...]}}]}}.
Include one entry per input id. Do not invent ids."""


def _batch(items: list[Review], size: int) -> Iterable[list[Review]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _format_user_payload(batch: list[Review]) -> str:
    # Tight payload: just id + truncated text. Rating/source aren't needed for
    # the relevance call (we have them in the DB) and burn tokens.
    rows = [
        {"id": r.id, "text": r.text[:280]}
        for r in batch
    ]
    return json.dumps(rows, ensure_ascii=False)


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
                max_tokens=700,
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
