"""Spotify feature lexicon — used to extract feature-level mentions from reviews
and to ground LLM prompts in product specifics. Keeps the analysis "meticulous".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Feature:
    canonical: str               # canonical display name
    category: str                # see CATEGORIES
    aliases: tuple[str, ...] = field(default_factory=tuple)


CATEGORIES = (
    "algorithmic_playlist",
    "ai_feature",
    "social",
    "discovery_surface",
    "playback",
    "subscription",
    "library",
    "podcast_audiobook",
    "device",
    "other",
)

FEATURES: tuple[Feature, ...] = (
    # --- Algorithmic playlists ---
    Feature("Discover Weekly", "algorithmic_playlist", ("discover weekly", "dw", "discoverweekly")),
    Feature("Release Radar", "algorithmic_playlist", ("release radar",)),
    Feature("Daily Mix", "algorithmic_playlist", ("daily mix", "daily mixes", "dailymix")),
    Feature("Daylist", "algorithmic_playlist", ("daylist", "day list")),
    Feature("On Repeat", "algorithmic_playlist", ("on repeat",)),
    Feature("Repeat Rewind", "algorithmic_playlist", ("repeat rewind",)),
    Feature("Niche Mixes", "algorithmic_playlist", ("niche mix", "niche mixes")),
    Feature("Time Capsule", "algorithmic_playlist", ("time capsule",)),
    Feature("Made For You", "algorithmic_playlist", ("made for you",)),
    # --- AI features ---
    Feature("DJ", "ai_feature", ("spotify dj", " dj ", "ai dj")),
    Feature("AI Playlist", "ai_feature", ("ai playlist",)),
    Feature("Smart Shuffle", "ai_feature", ("smart shuffle",)),
    Feature("Autoplay", "playback", ("autoplay", "auto-play", "auto play")),
    # --- Social ---
    Feature("Blend", "social", ("blend",)),
    Feature("Jam", "social", ("jam ", " jam"," jamming")),
    Feature("Friend Activity", "social", ("friend activity",)),
    Feature("Spotify Wrapped", "social", ("wrapped",)),
    Feature("Collaborative Playlist", "social", ("collaborative playlist", "collab playlist")),
    # --- Discovery surfaces ---
    Feature("Home", "discovery_surface", ("home page", "home screen", "home tab")),
    Feature("Search", "discovery_surface", ("search ", " search",)),
    Feature("Browse", "discovery_surface", ("browse",)),
    Feature("Radio", "discovery_surface", ("artist radio", "song radio", "spotify radio")),
    Feature("Enhance", "discovery_surface", ("enhance",)),
    # --- Playback / library ---
    Feature("Queue", "playback", ("queue",)),
    Feature("Crossfade", "playback", ("crossfade",)),
    Feature("Liked Songs", "library", ("liked songs", "your library", "saved songs")),
    Feature("Playlists", "library", ("my playlist", "my playlists")),
    # --- Subscription ---
    Feature("Free Tier", "subscription", ("free tier", "free plan", "free version")),
    Feature("Premium", "subscription", ("premium",)),
    Feature("Shuffle Lock (Free)", "subscription", ("shuffle only", "shuffle lock", "can't pick")),
    Feature("Skip Limit (Free)", "subscription", ("skip limit", "limited skips")),
    Feature("Ads", "subscription", ("ads", "advertisements")),
    # --- Other ---
    Feature("Lyrics", "other", ("lyrics",)),
    Feature("Canvas", "other", ("canvas",)),
    Feature("Connect", "device", ("spotify connect", "connect to",)),
    Feature("Car Mode", "device", ("car mode", "car view")),
    Feature("Podcasts", "podcast_audiobook", ("podcast", "podcasts")),
    Feature("Audiobooks", "podcast_audiobook", ("audiobook", "audio book")),
)


def detect_features(text: str) -> list[str]:
    """Return canonical feature names mentioned in text (case-insensitive)."""
    if not text:
        return []
    lowered = " " + text.lower() + " "
    hits: list[str] = []
    for feat in FEATURES:
        for alias in feat.aliases:
            # Use word-boundary-ish check (alias already includes spaces where needed)
            if alias in lowered:
                hits.append(feat.canonical)
                break
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def feature_lexicon_for_prompt() -> str:
    """Compact string of all features for inclusion in LLM system prompts."""
    by_cat: dict[str, list[str]] = {}
    for f in FEATURES:
        by_cat.setdefault(f.category, []).append(f.canonical)
    lines = []
    for cat in CATEGORIES:
        if cat in by_cat:
            lines.append(f"- {cat}: {', '.join(by_cat[cat])}")
    return "\n".join(lines)
