"""Google Play Store scraper for Spotify reviews.

Uses google-play-scraper. Balanced geography per project setting:
US + UK + IN-en + IN-hi + DE + BR.
"""
from __future__ import annotations

import logging
from typing import Iterable

from google_play_scraper import Sort, reviews

log = logging.getLogger(__name__)

SPOTIFY_APP_ID = "com.spotify.music"

# Country code, language code, soft cap on reviews
COUNTRY_CONFIG: list[tuple[str, str, int]] = [
    ("us", "en", 300),
    ("gb", "en", 200),
    ("in", "en", 250),
    ("in", "hi", 150),
    ("de", "de", 100),
    ("br", "pt", 100),
]


def fetch_playstore(per_country_cap: int | None = None) -> list[dict]:
    """Fetch Spotify Play Store reviews. Returns raw dicts (un-normalized)."""
    out: list[dict] = []
    for country, lang, default_cap in COUNTRY_CONFIG:
        cap = per_country_cap or default_cap
        try:
            results, _ = reviews(
                SPOTIFY_APP_ID,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=cap,
            )
        except Exception as exc:                                  # noqa: BLE001
            log.warning("Play Store fetch failed (%s/%s): %s", country, lang, exc)
            continue

        log.info("Play Store %s/%s: %d reviews", country, lang, len(results))
        for r in results:
            # google-play-scraper returns dicts with: reviewId, content, score, at, userName, ...
            out.append(
                {
                    "id": r.get("reviewId"),
                    "text": r.get("content"),
                    "rating": r.get("score"),
                    "author": r.get("userName"),
                    "date": r.get("at"),                          # datetime
                    "locale": f"{lang}-{country.upper()}",
                    "url": f"https://play.google.com/store/apps/details?id={SPOTIFY_APP_ID}&reviewId={r.get('reviewId')}",
                    "_country": country,
                    "_lang": lang,
                }
            )
    return out


def fetch_playstore_normalized() -> Iterable[dict]:
    """Convenience: yields dicts directly suitable for normalize.normalize_record."""
    for r in fetch_playstore():
        yield r
