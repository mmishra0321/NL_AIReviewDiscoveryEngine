"""Pydantic schemas - the canonical data shapes across the pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ReviewSource = Literal[
    "app_store",
    "play_store",
    "reddit",
    "trustpilot",
    "youtube",
    "community",
    "curated_seed",
]


class Review(BaseModel):
    """Normalized review record.

    `id` is a deterministic hash of (source, source_id) so re-scrapes dedupe.
    """

    id: str
    source: ReviewSource
    source_id: str
    text: str
    rating: int | None = None              # 1-5 where applicable
    author: str | None = None
    date: datetime | None = None
    url: str | None = None
    locale: str | None = None              # e.g. "en-US", "hi-IN"
    extra: dict = Field(default_factory=dict)

    # Derived (populated by pipeline)
    is_relevant: bool | None = None
    relevance_reason: str | None = None
    canonical_tags: list[str] = Field(default_factory=list)   # e.g. ["Q1_struggle", "Q4_repetition"]
    features_mentioned: list[str] = Field(default_factory=list)
    user_segments: list[str] = Field(default_factory=list)    # e.g. ["premium", "indian_listener"]


class RelevanceVerdict(BaseModel):
    """LLM output for the discovery-relevance classifier."""

    is_relevant: bool
    reason: str = ""
    canonical_tags: list[str] = Field(default_factory=list)


class RagAnswer(BaseModel):
    """LLM output for a RAG question."""

    answer: str
    spotify_features_mentioned: list[str] = Field(default_factory=list)
    user_segments_affected: list[str] = Field(default_factory=list)
    supporting_review_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class ScopeVerdict(BaseModel):
    """LLM output for the scope wrapper (LLM fallback path)."""

    in_scope: bool
    reason: str = ""
