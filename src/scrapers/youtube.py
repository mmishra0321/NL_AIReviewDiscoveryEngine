"""YouTube vlog comments scraper for Spotify discovery discussion.

Two-step pipeline:
1. `yt-dlp` searches YouTube for Spotify-discovery topics → returns top video
   URLs (no API key, no auth).
2. `youtube-comment-downloader` scrapes the public comment feed of each video
   (also no auth).

The comment threads under tech-reviewer / music-journalist / listener-rant
videos are a rich source of vlog-era opinion that App Store / Play Store
reviews don't capture.
"""
from __future__ import annotations

import logging
from itertools import islice
from typing import Any

log = logging.getLogger(__name__)

# Search queries → number of top videos to pull comments from.
# Sized so we yield ~200 comments raw → ~150 survive the normalize-stage cap.
SEARCH_QUERIES: list[tuple[str, int]] = [
    ("spotify discover weekly review", 2),
    ("spotify recommendations broken", 2),
    ("spotify vs apple music discovery", 1),
    ("spotify DJ AI honest review", 1),
    ("how to discover new music spotify", 1),
]

MAX_COMMENTS_PER_VIDEO = 40
MIN_TEXT_LEN = 35


def _search_videos(query: str, max_results: int) -> list[dict]:
    """Return [{'url', 'id', 'title'}, ...] for top YouTube hits matching query."""
    try:
        from yt_dlp import YoutubeDL                                # noqa: WPS433
    except ImportError:
        log.warning("yt-dlp not installed — YouTube search disabled.")
        return []

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch",
    }
    out: list[dict] = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"ytsearch{max_results}:{query}",
                download=False,
            )
        entries = (info or {}).get("entries") or []
        for e in entries:
            vid = e.get("id")
            url = e.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
            if not vid or not url:
                continue
            out.append({"url": url, "id": vid, "title": e.get("title") or ""})
    except Exception as exc:                                         # noqa: BLE001
        log.warning("YouTube search '%s' failed: %s", query, exc)
    return out


def _download_comments(video_url: str, max_per_video: int) -> list[dict[str, Any]]:
    """Return up to `max_per_video` popular comments from `video_url`."""
    try:
        from youtube_comment_downloader import (                    # noqa: WPS433
            SORT_BY_POPULAR,
            YoutubeCommentDownloader,
        )
    except ImportError:
        log.warning("youtube-comment-downloader not installed — skipping.")
        return []

    out: list[dict] = []
    try:
        downloader = YoutubeCommentDownloader()
        gen = downloader.get_comments_from_url(video_url, sort_by=SORT_BY_POPULAR)
        for c in islice(gen, max_per_video):
            out.append(c)
    except Exception as exc:                                         # noqa: BLE001
        log.warning("Comment download failed for %s: %s", video_url, exc)
    return out


def fetch_youtube(max_per_video: int = MAX_COMMENTS_PER_VIDEO) -> list[dict]:
    """Search Spotify-discovery queries on YouTube + scrape top comments.

    Returns raw dicts ready for normalize_record(...).
    """
    all_records: list[dict] = []
    seen_comment_ids: set[str] = set()
    seen_video_ids: set[str] = set()

    for query, top_n in SEARCH_QUERIES:
        videos = _search_videos(query, top_n)
        log.info("YouTube search '%s' → %d videos", query, len(videos))

        for v in videos:
            if v["id"] in seen_video_ids:
                continue
            seen_video_ids.add(v["id"])

            comments = _download_comments(v["url"], max_per_video)
            kept = 0
            for c in comments:
                text = (c.get("text") or "").strip()
                if len(text) < MIN_TEXT_LEN:
                    continue
                cid = c.get("cid") or c.get("id") or ""
                if not cid or cid in seen_comment_ids:
                    continue
                seen_comment_ids.add(cid)
                all_records.append({
                    "id": f"yt_{cid}",
                    "text": text,
                    "rating": None,
                    "author": c.get("author"),
                    "date": c.get("time_parsed") or c.get("time"),
                    "url": v["url"],
                    "locale": "en",
                    "_video_id": v["id"],
                    "_video_title": v["title"],
                    "_query": query,
                    "_votes": c.get("votes"),
                })
                kept += 1

            log.info("  → %s '%s' → %d comments kept", v["id"], v["title"][:60], kept)

    log.info("YouTube total: %d comments across %d videos", len(all_records), len(seen_video_ids))
    return all_records
