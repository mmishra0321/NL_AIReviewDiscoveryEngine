"""The 6 canonical questions that drive this engine.

These are mirrored 1:1 from the project brief. Every relevant review is
tagged with which of these it supports (multi-label). The Streamlit UI
shows one card per question with a pre-computed RAG answer.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalQuestion:
    id: str
    short: str          # for buttons / nav
    full: str           # full question text
    description: str    # one-line context for the LLM


CANONICAL_QUESTIONS: list[CanonicalQuestion] = [
    CanonicalQuestion(
        id="Q1_struggle",
        short="Why discovery struggles",
        full="Why do users struggle to discover new music on Spotify?",
        description=(
            "Identify the root causes that block users from finding music they haven't "
            "heard before. Focus on Spotify-specific surfaces (Discover Weekly, Release "
            "Radar, Daily Mixes, Daylist, Smart Shuffle, DJ, Search, Browse), algorithmic "
            "limitations, and UX friction."
        ),
    ),
    CanonicalQuestion(
        id="Q2_frustrations",
        short="Recommendation frustrations",
        full="What are the most common frustrations with Spotify's recommendations?",
        description=(
            "Catalogue concrete complaints: stale playlists, recommending already-liked "
            "songs, narrow genre repetition, over-personalization, mood mismatch, "
            "language/regional gaps, lack of explanation/transparency."
        ),
    ),
    CanonicalQuestion(
        id="Q3_jobs",
        short="Listening jobs-to-be-done",
        full="What listening behaviours are users trying to achieve?",
        description=(
            "Surface the underlying jobs: discovering unheard artists, escaping a rut, "
            "matching specific moods/activities, exploring genres/eras, finding regional "
            "or niche music, building shareable identity."
        ),
    ),
    CanonicalQuestion(
        id="Q4_repetition",
        short="Causes of repeat-listening",
        full="What causes users to repeatedly listen to the same content on Spotify?",
        description=(
            "Identify mechanisms behind repetition: comfort/familiarity, algorithm "
            "reinforcement, autoplay defaults, friction to explore, Liked-Songs gravity, "
            "limited skip/seek (free tier), Daily Mix overlap."
        ),
    ),
    CanonicalQuestion(
        id="Q5_segments",
        short="Segment differences",
        full="Which user segments experience different discovery challenges?",
        description=(
            "Compare segments: heavy vs casual listeners, free vs Premium, English vs "
            "non-English / regional listeners, genre-specific (indie, classical, hip-hop, "
            "regional), age/cohort, mobile vs desktop, new-to-app vs long-tenured."
        ),
    ),
    CanonicalQuestion(
        id="Q6_unmet",
        short="Unmet needs",
        full="What unmet needs emerge consistently across reviews?",
        description=(
            "Identify recurring asks that Spotify does not yet serve: explainable "
            "recommendations, intent/context-driven discovery, time-bound exploration "
            "modes, multi-language blending, deeper artist context, cross-cultural mixes."
        ),
    ),
]

QUESTION_TEXTS: list[str] = [q.full for q in CANONICAL_QUESTIONS]
QUESTION_BY_ID: dict[str, CanonicalQuestion] = {q.id: q for q in CANONICAL_QUESTIONS}
