"""Scope wrapper - decides if a custom question is in-scope.

Hybrid:
- Fast path: cosine similarity between user question and the 6 canonical questions
  using the same local embedder we already loaded.
  - If max_sim >= SCOPE_IN_THRESHOLD       -> IN_SCOPE
  - If max_sim <  SCOPE_OUT_THRESHOLD      -> OUT_OF_SCOPE
- Borderline band: fall back to a small Groq classifier call.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from src.canonical import CANONICAL_QUESTIONS
from src.config import SCOPE_IN_THRESHOLD, SCOPE_OUT_THRESHOLD
from src.pipeline.embed import embed_texts
from src.pipeline.groq_client import fast_client
from src.schema import ScopeVerdict

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _canonical_vectors() -> np.ndarray:
    texts = [q.full + " " + q.description for q in CANONICAL_QUESTIONS]
    return np.array(embed_texts(texts))


SCOPE_SYSTEM = """You are a strict scope classifier for a Spotify music-discovery
research tool. The tool ONLY answers questions about:
- Why users struggle to discover new music on Spotify
- Frustrations with Spotify's recommendations
- Listening behaviours users are trying to achieve
- Why users repeatedly listen to the same content
- How different user segments experience discovery differently
- Unmet needs that emerge in user reviews

If the user question is about any of the above (even loosely paraphrased), return
in_scope=true. Otherwise (greetings, Spotify pricing, podcasts unrelated to discovery,
unrelated topics, off-platform questions) return in_scope=false.

Reply STRICT JSON: {"in_scope": true|false, "reason": "one short clause"}"""


@dataclass
class ScopeResult:
    in_scope: bool
    confidence: str            # "high" if decided by fast path; "llm" if escalated
    max_similarity: float
    nearest_canonical_id: str
    reason: str


def evaluate_scope(question: str) -> ScopeResult:
    q = (question or "").strip()
    if not q:
        return ScopeResult(False, "high", 0.0, "", "Empty question.")

    canon = _canonical_vectors()
    qv = np.array(embed_texts([q])[0])
    sims = canon @ qv                                            # cosine (vectors are normalized)
    idx = int(np.argmax(sims))
    max_sim = float(sims[idx])
    nearest_id = CANONICAL_QUESTIONS[idx].id

    if max_sim >= SCOPE_IN_THRESHOLD:
        return ScopeResult(True, "high", max_sim, nearest_id,
                           f"High similarity ({max_sim:.2f}) to {nearest_id}.")
    if max_sim < SCOPE_OUT_THRESHOLD:
        return ScopeResult(False, "high", max_sim, nearest_id,
                           f"Low similarity ({max_sim:.2f}) to all canonical Qs.")

    # Borderline → LLM
    try:
        verdict = fast_client().chat_pydantic(
            system=SCOPE_SYSTEM,
            user=f"User question: {q}",
            schema=ScopeVerdict,
            temperature=0.0,
            max_tokens=128,
        )
    except Exception as exc:                                      # noqa: BLE001
        log.warning("Scope LLM fallback failed: %s; defaulting to in-scope.", exc)
        return ScopeResult(True, "llm", max_sim, nearest_id, "LLM unavailable; allowed.")

    if verdict is None:
        return ScopeResult(True, "llm", max_sim, nearest_id, "LLM response invalid; allowed.")
    return ScopeResult(verdict.in_scope, "llm", max_sim, nearest_id, verdict.reason)


OUT_OF_SCOPE_MESSAGE = (
    "This tool only answers questions about Spotify music discovery - why users "
    "struggle to discover new music, frustrations with recommendations, listening "
    "behaviours they want, causes of repetitive listening, segment differences, "
    "and unmet needs. Try rephrasing toward one of those, or pick one of the 6 "
    "canonical questions above."
)
