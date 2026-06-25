"""Apple App Store reviews via the public iTunes RSS feed.

Apple exposes a paginated JSON RSS endpoint for customer reviews - no API key
required. Pages 1-10 are typically retrievable per storefront. Each page has
~50 reviews. We sweep several storefronts for balanced geography.

Endpoint format:
    https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortBy=mostRecent/json
"""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

SPOTIFY_APP_ID = 324684580

# (country_code, max_pages) - Apple caps at 10 pages × ~50 reviews each.
# Total ~600 raw → ~400 survive the normalize-stage cap (see config.REVIEW_BUDGET_BY_SOURCE).
COUNTRIES: list[tuple[str, int]] = [
    ("us", 4),
    ("gb", 3),
    ("in", 3),
    ("ca", 2),
    ("au", 2),
    ("de", 2),
    ("fr", 1),
    ("br", 2),
    ("mx", 1),
    ("es", 1),
]


def _fetch_page(country: str, page: int, timeout: float = 15.0) -> list[dict]:
    url = (
        f"https://itunes.apple.com/{country}/rss/customerreviews/"
        f"page={page}/id={SPOTIFY_APP_ID}/sortBy=mostRecent/json"
    )
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (spotify-discovery-pm/0.1)"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("App Store %s p%d failed: %s", country, page, exc)
        return []

    feed = data.get("feed") or {}
    entries = feed.get("entry") or []
    # Apple includes the app metadata as the first entry on page 1; skip it
    if entries and isinstance(entries, list) and "im:name" in entries[0]:
        entries = entries[1:]
    return entries


def fetch_appstore(per_country_max_pages: int | None = None) -> list[dict]:
    """Fetch Spotify App Store reviews. Returns raw dicts (un-normalized)."""
    out: list[dict] = []
    for country, default_pages in COUNTRIES:
        n_pages = per_country_max_pages or default_pages
        country_count = 0
        for page in range(1, n_pages + 1):
            entries = _fetch_page(country, page)
            if not entries:
                break
            for e in entries:
                try:
                    rid = e.get("id", {}).get("label", "")
                    title = e.get("title", {}).get("label", "")
                    content = e.get("content", {}).get("label", "")
                    rating = int(e.get("im:rating", {}).get("label", 0) or 0)
                    author = e.get("author", {}).get("name", {}).get("label", "")
                    updated = e.get("updated", {}).get("label", "")
                    out.append(
                        {
                            "id": rid,
                            "text": (f"{title}\n{content}" if title else content).strip(),
                            "rating": rating,
                            "author": author,
                            "date": updated,                       # ISO string
                            "locale": f"en-{country.upper()}",
                            "url": f"https://apps.apple.com/{country}/app/spotify/id{SPOTIFY_APP_ID}",
                            "_country": country,
                            "_page": page,
                        }
                    )
                    country_count += 1
                except Exception as exc:                            # noqa: BLE001
                    log.debug("App Store entry parse failed: %s", exc)
                    continue
            time.sleep(0.5)
        log.info("App Store %s: %d reviews", country, country_count)
        time.sleep(0.5)
    return out
