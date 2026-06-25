"""Normalize raw scrape outputs into the canonical Review schema, plus dedupe."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from src.config import REVIEWS_PATH
from src.schema import Review, ReviewSource

log = logging.getLogger(__name__)


def make_id(source: str, source_id: str) -> str:
    """Stable hash so re-scrapes dedupe automatically."""
    return hashlib.sha256(f"{source}:{source_id}".encode()).hexdigest()[:16]


_WHITESPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\t", " ")
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def normalize_record(raw: dict, source: ReviewSource) -> Review | None:
    """Convert a source-specific raw dict into a canonical Review.

    Raw record contract per source:
    - app_store / play_store: {"id", "content"/"text", "score"/"rating",
                                "userName"/"author", "at"/"date", "url"?}
    - reddit:                 {"id", "body"/"selftext", "author", "created_utc", "permalink"}
    - community:              {"id", "body", "author", "date", "url"}
    - curated_seed:           {"id", "text", ...}
    """
    sid = str(raw.get("id") or raw.get("source_id") or "")
    text_raw = (
        raw.get("text")
        or raw.get("content")
        or raw.get("body")
        or raw.get("selftext")
        or raw.get("review")
        or ""
    )
    text = clean_text(text_raw)
    if not sid or len(text) < 15:
        return None

    rating = raw.get("rating") or raw.get("score") or raw.get("stars")
    try:
        rating = int(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None

    author = raw.get("author") or raw.get("userName") or raw.get("user") or None

    raw_date = raw.get("date") or raw.get("at") or raw.get("created_utc")
    parsed_date: datetime | None = None
    if isinstance(raw_date, datetime):
        parsed_date = raw_date
    elif isinstance(raw_date, (int, float)):
        try:
            parsed_date = datetime.utcfromtimestamp(float(raw_date))
        except (OSError, ValueError):
            parsed_date = None
    elif isinstance(raw_date, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(raw_date[: len(fmt) + 2], fmt)
                break
            except ValueError:
                continue

    url = raw.get("url")
    if not url and source == "reddit" and raw.get("permalink"):
        url = f"https://reddit.com{raw['permalink']}"

    return Review(
        id=make_id(source, sid),
        source=source,
        source_id=sid,
        text=text,
        rating=rating,
        author=author,
        date=parsed_date,
        url=url,
        locale=raw.get("locale"),
        extra={k: v for k, v in raw.items() if k not in {
            "id", "content", "text", "body", "selftext", "rating", "score",
            "stars", "userName", "author", "user", "date", "at",
            "created_utc", "url", "permalink", "locale",
        }},
    )


def load_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def merge_and_dedupe(reviews: Iterable[Review]) -> list[Review]:
    """Dedupe by stable id; later entries win (assumes refresh order is newest-last)."""
    by_id: dict[str, Review] = {}
    for r in reviews:
        by_id[r.id] = r
    return list(by_id.values())


def write_canonical_store(reviews: Iterable[Review]) -> int:
    return write_jsonl(REVIEWS_PATH, (r.model_dump(mode="json") for r in reviews))


def load_canonical_store() -> list[Review]:
    return [Review.model_validate(r) for r in load_jsonl(REVIEWS_PATH)]
