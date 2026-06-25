"""Trustpilot scraper for Spotify reviews.

Trustpilot publishes consumer reviews at trustpilot.com/review/spotify.com.
Each review page has ~20 reviews; we paginate through several pages.

Strategy: parse the embedded `__NEXT_DATA__` JSON blob (most reliable),
then fall back to HTML scraping if the JSON shape changes.

No API key needed.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://www.trustpilot.com/review/spotify.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 25.0
SLEEP_BETWEEN_PAGES = 1.0
DEFAULT_MAX_PAGES = 30  # ~600 reviews
MIN_TEXT_LEN = 30


def _fetch_page_html(page: int) -> str | None:
    url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        log.warning("Trustpilot page %d failed: %s", page, exc)
        return None


def _extract_next_data(html: str) -> dict | None:
    """Pull the __NEXT_DATA__ JSON blob from Trustpilot's Next.js page."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def _walk_reviews(next_data: dict) -> list[dict]:
    """Find the review list inside the Next.js page state.

    Trustpilot's JSON shape changes occasionally; we walk recursively and
    pick out lists of dicts that look like reviews (have 'text' + 'rating'
    or 'title' + 'consumer').
    """
    found: list[dict] = []

    def looks_like_review(d: dict) -> bool:
        keys = set(d.keys())
        return (
            ("text" in keys or "title" in keys)
            and ("rating" in keys or "stars" in keys or "score" in keys)
        )

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if looks_like_review(node):
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(next_data)
    return found


def _normalize_one(raw: dict, page: int) -> dict | None:
    text_parts: list[str] = []
    if isinstance(raw.get("title"), str):
        text_parts.append(raw["title"].strip())
    if isinstance(raw.get("text"), str):
        text_parts.append(raw["text"].strip())
    text = "\n".join(p for p in text_parts if p)
    if len(text) < MIN_TEXT_LEN:
        return None

    rating_val = raw.get("rating") or raw.get("stars") or raw.get("score")
    try:
        rating = int(rating_val) if rating_val is not None else None
    except (TypeError, ValueError):
        rating = None

    rid = (
        raw.get("id")
        or raw.get("reviewId")
        or raw.get("uuid")
        or raw.get("slug")
    )
    if not rid:
        # Fallback: derive a stable hash from text + rating
        rid = f"tp_{abs(hash((text[:80], rating, page)))}"
    rid = str(rid)

    consumer = raw.get("consumer") or {}
    if not isinstance(consumer, dict):
        consumer = {}
    author = (
        consumer.get("displayName")
        or consumer.get("name")
        or raw.get("author")
        or None
    )
    locale = (
        (consumer.get("countryCode") or "").lower()
        if consumer.get("countryCode")
        else None
    )

    date = raw.get("dates", {}).get("publishedDate") if isinstance(raw.get("dates"), dict) else None
    date = date or raw.get("publishedDate") or raw.get("createdAt") or raw.get("date")

    return {
        "id": f"tp_{rid}",
        "text": text,
        "rating": rating,
        "author": author,
        "date": date,
        "url": BASE_URL,
        "locale": locale,
        "_page": page,
    }


def fetch_trustpilot(max_pages: int = DEFAULT_MAX_PAGES) -> list[dict]:
    """Fetch Trustpilot reviews of spotify.com. Returns raw dicts (un-normalized).

    NOTE: Trustpilot serves pages behind Cloudflare. Without a Cloudflare-aware
    client (e.g. `cloudscraper`, `curl_cffi`), most plain-`requests` calls get
    403'd. This scraper handles that gracefully — if page 1 fails, we skip
    Trustpilot entirely for this run.
    """
    out: list[dict] = []
    seen_ids: set[str] = set()

    for page in range(1, max_pages + 1):
        html = _fetch_page_html(page)
        if not html:
            if page == 1:
                log.warning(
                    "Trustpilot page 1 blocked (likely Cloudflare). To enable, "
                    "install `cloudscraper` and swap the requests.get() in this "
                    "module. Skipping Trustpilot for this run."
                )
            else:
                log.info("Trustpilot stopped at page %d (no HTML)", page)
            break

        next_data = _extract_next_data(html)
        if not next_data:
            log.warning("Trustpilot page %d: no __NEXT_DATA__ found", page)
            time.sleep(SLEEP_BETWEEN_PAGES)
            continue

        candidates = _walk_reviews(next_data)
        page_count_before = len(out)
        for raw in candidates:
            n = _normalize_one(raw, page)
            if n and n["id"] not in seen_ids:
                seen_ids.add(n["id"])
                out.append(n)

        added = len(out) - page_count_before
        log.info("Trustpilot page %d: +%d reviews (total=%d)", page, added, len(out))
        if added == 0:
            # Either page is empty or shape changed — bail out gracefully
            log.info("Trustpilot: no new reviews on page %d, stopping", page)
            break

        time.sleep(SLEEP_BETWEEN_PAGES)

    return out
