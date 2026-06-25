"""Reddit scraper using the public JSON API (no OAuth required).

Reddit exposes a `.json` endpoint on most pages. We search several Spotify-related
subreddits for discovery / recommendation / playlist topics, then for each top
post we also fetch the top-N comments.

Polite usage:
- Custom User-Agent
- 1.5s sleep between requests (Reddit's stated rate limit is 60/min for unauthed)
- Best-effort error handling so one failed sub doesn't kill the run

Authentication is intentionally avoided so the GitHub Action doesn't need
extra secrets beyond GROQ_API_KEY.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

log = logging.getLogger(__name__)

USER_AGENT = "spotify-discovery-pm:v0.1 (research; +contact via github)"
TIMEOUT = 20.0
SLEEP_BETWEEN_CALLS = 1.6  # seconds - stay well under 60 req/min

# (subreddit, search_query, max_posts)
SEARCH_PLAN: list[tuple[str, str, int]] = [
    ("spotify", "discover weekly", 25),
    ("spotify", "recommendations", 25),
    ("spotify", "discovery", 20),
    ("spotify", "daily mix", 15),
    ("spotify", "release radar", 15),
    ("spotify", "DJ algorithm", 15),
    ("truespotify", "discover", 25),
    ("truespotify", "recommendations", 25),
    ("truespotify", "algorithm", 20),
    ("musicsuggestions", "spotify discovery", 15),
    ("LetsTalkMusic", "spotify algorithm", 10),
]

MAX_COMMENTS_PER_POST = 6
MIN_TEXT_LEN = 40   # filter near-empty posts/comments


def _get_json(url: str) -> dict | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if resp.status_code == 429:
            log.warning("Reddit 429 on %s - backing off 30s", url)
            time.sleep(30)
            return None
        if resp.status_code != 200:
            log.warning("Reddit %d on %s", resp.status_code, url)
            return None
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("Reddit request failed (%s): %s", url, exc)
        return None


def _post_to_dict(post: dict, subreddit: str) -> dict | None:
    data = post.get("data") or {}
    text_parts = [data.get("title") or "", data.get("selftext") or ""]
    body = "\n".join(p for p in text_parts if p).strip()
    if len(body) < MIN_TEXT_LEN:
        return None
    return {
        "id": f"post_{data.get('id')}",
        "text": body,
        "rating": None,
        "author": data.get("author"),
        "date": data.get("created_utc"),
        "url": f"https://reddit.com{data.get('permalink', '')}",
        "locale": "en",
        "_subreddit": subreddit,
        "_score": data.get("score"),
        "_num_comments": data.get("num_comments"),
        "_kind": "post",
    }


def _comment_to_dict(comment: dict, subreddit: str, post_id: str) -> dict | None:
    data = comment.get("data") or {}
    body = (data.get("body") or "").strip()
    if len(body) < MIN_TEXT_LEN or body in {"[deleted]", "[removed]"}:
        return None
    return {
        "id": f"comm_{data.get('id')}",
        "text": body,
        "rating": None,
        "author": data.get("author"),
        "date": data.get("created_utc"),
        "url": f"https://reddit.com{data.get('permalink', '')}",
        "locale": "en",
        "_subreddit": subreddit,
        "_score": data.get("score"),
        "_parent_post": post_id,
        "_kind": "comment",
    }


def _fetch_top_comments(subreddit: str, post_id: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?sort=top&limit={MAX_COMMENTS_PER_POST}"
    data = _get_json(url)
    time.sleep(SLEEP_BETWEEN_CALLS)
    if not data or not isinstance(data, list) or len(data) < 2:
        return []
    # The comments listing is the second array element
    children = (data[1].get("data") or {}).get("children") or []
    out: list[dict] = []
    for c in children[:MAX_COMMENTS_PER_POST]:
        if c.get("kind") != "t1":
            continue
        d = _comment_to_dict(c, subreddit, post_id)
        if d:
            out.append(d)
    return out


def fetch_reddit() -> list[dict]:
    """Fetch Spotify-related Reddit posts + top comments. Returns raw dicts.

    NOTE: Reddit shut down anonymous JSON API access in mid-2023. This scraper
    will short-circuit on the first 403 with a clear message. To enable Reddit,
    register an OAuth app at https://www.reddit.com/prefs/apps and switch to
    PRAW with REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (see .env.example).
    """
    # Probe one endpoint before walking the full plan; if we're blocked,
    # bail loudly once instead of spamming warnings.
    probe = _get_json(
        "https://www.reddit.com/r/spotify/top.json?t=year&limit=1"
    )
    if not probe:
        log.warning(
            "Reddit anonymous API blocked (403). Add Reddit OAuth credentials "
            "to .env (REDDIT_CLIENT_ID/SECRET) + switch to PRAW to enable. "
            "Skipping Reddit for this run."
        )
        return []

    out: list[dict] = []
    seen_post_ids: set[str] = set()

    for sub, query, max_posts in SEARCH_PLAN:
        url = (
            f"https://www.reddit.com/r/{sub}/search.json"
            f"?q={requests.utils.quote(query)}"
            f"&restrict_sr=1&sort=relevance&t=year&limit={max_posts}"
        )
        data = _get_json(url)
        time.sleep(SLEEP_BETWEEN_CALLS)
        if not data:
            continue

        children = (data.get("data") or {}).get("children") or []
        sub_post_count = 0
        sub_comm_count = 0
        for child in children:
            if child.get("kind") != "t3":
                continue
            post_dict = _post_to_dict(child, sub)
            if not post_dict:
                continue
            post_data_id = (child.get("data") or {}).get("id")
            if not post_data_id or post_data_id in seen_post_ids:
                continue
            seen_post_ids.add(post_data_id)
            out.append(post_dict)
            sub_post_count += 1

            # Fetch top comments for this post (best-effort)
            for cd in _fetch_top_comments(sub, post_data_id):
                out.append(cd)
                sub_comm_count += 1

        log.info("Reddit r/%s '%s' → %d posts + %d comments",
                 sub, query, sub_post_count, sub_comm_count)

    return out
