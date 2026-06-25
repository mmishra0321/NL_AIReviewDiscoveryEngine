"""End-to-end pipeline: scrape -> normalize -> dedupe -> relevance filter
-> embed -> upsert into Chroma -> categorize -> precompute canonical answers
-> write metadata.

This is the single entry point used both locally and by the weekly
GitHub Actions workflow.

Usage:
    python -m src.pipeline.refresh                  # full refresh
    python -m src.pipeline.refresh --seed-only      # use only curated seed reviews
    python -m src.pipeline.refresh --skip-scrape    # use whatever's in data/raw
    python -m src.pipeline.refresh --skip-rag       # skip canonical pre-compute
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    MAX_REVIEWS_TO_CLASSIFY,
    METADATA_PATH,
    PROCESSED_DIR,
    RAW_DIR,
    REVIEW_BUDGET_BY_SOURCE,
    REVIEWS_PATH,
    SEED_PATH,
)
from src.lexicon import detect_features
from src.pipeline.embed import collection_size, upsert_reviews
from src.pipeline.normalize import (
    load_canonical_store,
    load_jsonl,
    merge_and_dedupe,
    normalize_record,
    write_canonical_store,
    write_jsonl,
)
from src.pipeline.relevance import classify_relevance, filter_relevant
from src.schema import Review

log = logging.getLogger(__name__)


# ---------- individual stages ----------

def stage_scrape(skip: bool = False) -> dict[str, int]:
    """Run all scrapers, write raw JSONL per source, return per-source counts."""
    counts: dict[str, int] = {}
    if skip:
        log.info("Skipping scrape (existing raw data will be reused).")
        return counts

    # Play Store
    try:
        from src.scrapers.playstore import fetch_playstore
        ps = fetch_playstore()
        if ps:
            n = write_jsonl(RAW_DIR / "play_store.jsonl", ps)
            counts["play_store"] = n
            log.info("Play Store: wrote %d", n)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("Play Store scraper failed: %s", exc)

    # App Store
    try:
        from src.scrapers.appstore import fetch_appstore
        ap = fetch_appstore()
        if ap:
            n = write_jsonl(RAW_DIR / "app_store.jsonl", ap)
            counts["app_store"] = n
            log.info("App Store: wrote %d", n)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("App Store scraper failed: %s", exc)

    # Reddit (public JSON API; no auth)
    try:
        from src.scrapers.reddit import fetch_reddit
        rd = fetch_reddit()
        if rd:
            n = write_jsonl(RAW_DIR / "reddit.jsonl", rd)
            counts["reddit"] = n
            log.info("Reddit: wrote %d", n)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("Reddit scraper failed: %s", exc)

    # Trustpilot (HTML + __NEXT_DATA__)
    try:
        from src.scrapers.trustpilot import fetch_trustpilot
        tp = fetch_trustpilot()
        if tp:
            n = write_jsonl(RAW_DIR / "trustpilot.jsonl", tp)
            counts["trustpilot"] = n
            log.info("Trustpilot: wrote %d", n)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("Trustpilot scraper failed: %s", exc)

    # YouTube vlog comments (no auth)
    try:
        from src.scrapers.youtube import fetch_youtube
        yt = fetch_youtube()
        if yt:
            n = write_jsonl(RAW_DIR / "youtube.jsonl", yt)
            counts["youtube"] = n
            log.info("YouTube: wrote %d", n)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("YouTube scraper failed: %s", exc)

    return counts


def stage_normalize(seed_only: bool = False) -> list[Review]:
    """Load raw + seed, normalize, dedupe, write to canonical store."""
    candidates: list[Review] = []

    # Curated seed (always)
    if SEED_PATH.exists():
        for raw in load_jsonl(SEED_PATH):
            n = normalize_record(raw, source="curated_seed")
            if n:
                candidates.append(n)
        log.info("Loaded %d curated seed reviews", len(candidates))

    if not seed_only:
        # source-name → file mapping
        from src.schema import ReviewSource
        scraped_sources: list[tuple[ReviewSource, str]] = [
            ("play_store", "play_store.jsonl"),
            ("app_store", "app_store.jsonl"),
            ("reddit", "reddit.jsonl"),
            ("trustpilot", "trustpilot.jsonl"),
            ("youtube", "youtube.jsonl"),
        ]
        for src_name, fname in scraped_sources:
            path = RAW_DIR / fname
            if not path.exists():
                continue
            count_in = 0
            for raw in load_jsonl(path):
                n = normalize_record(raw, source=src_name)
                if n:
                    candidates.append(n)
                    count_in += 1
            log.info("Normalized %d %s reviews", count_in, src_name)

    deduped = merge_and_dedupe(candidates)
    log.info("After dedupe: %d unique reviews", len(deduped))

    # Apply per-source budget cap so we never exceed MAX_REVIEWS_TO_CLASSIFY.
    # Keeps Groq token consumption bounded (~50k tokens / refresh at default cap).
    capped = _apply_source_budget(deduped)
    if len(capped) < len(deduped):
        log.info(
            "Cap applied: %d → %d reviews (MAX_REVIEWS_TO_CLASSIFY=%d, per-source budget: %s)",
            len(deduped), len(capped), MAX_REVIEWS_TO_CLASSIFY, REVIEW_BUDGET_BY_SOURCE,
        )

    # Cache lexicon features at normalize time (no LLM needed for this)
    for r in capped:
        r.features_mentioned = detect_features(r.text)

    write_canonical_store(capped)
    return capped


def _apply_source_budget(reviews: list[Review]) -> list[Review]:
    """Trim to MAX_REVIEWS_TO_CLASSIFY using REVIEW_BUDGET_BY_SOURCE quotas.

    Algorithm:
    1. Bucket reviews by source.
    2. Per bucket, take up to its quota (newest-first, leveraging insertion order).
    3. If we have leftover headroom (because some sources under-delivered),
       round-robin extra reviews from the over-supplied sources until we hit
       MAX_REVIEWS_TO_CLASSIFY.
    """
    if not reviews:
        return []

    by_source: dict[str, list[Review]] = {}
    for r in reviews:
        by_source.setdefault(r.source, []).append(r)

    out: list[Review] = []
    overflow: dict[str, list[Review]] = {}
    for src, lst in by_source.items():
        quota = REVIEW_BUDGET_BY_SOURCE.get(src, 0)
        if quota <= 0:
            # No quota configured for this source — keep nothing by default
            continue
        kept = lst[:quota]
        out.extend(kept)
        if len(lst) > quota:
            overflow[src] = lst[quota:]

    # Distribute remaining headroom across the sources that have extras
    headroom = MAX_REVIEWS_TO_CLASSIFY - len(out)
    if headroom > 0 and overflow:
        # Round-robin to keep the mix balanced
        idx = 0
        ordered_overflow = list(overflow.values())
        while headroom > 0 and any(ordered_overflow):
            bucket = ordered_overflow[idx % len(ordered_overflow)]
            if bucket:
                out.append(bucket.pop(0))
                headroom -= 1
            idx += 1
            if idx > 100_000:                              # paranoia bail
                break

    return out[:MAX_REVIEWS_TO_CLASSIFY]


def stage_classify(reviews: list[Review]) -> list[Review]:
    """Tag each review's is_relevant + canonical_tags via Groq."""
    classified = classify_relevance(reviews)
    relevant = filter_relevant(classified)
    log.info("Relevance: %d/%d reviews are discovery-relevant",
             len(relevant), len(classified))
    write_canonical_store(classified)                              # rewrite with tags
    return classified


def stage_embed(reviews: list[Review]) -> int:
    """Upsert relevant reviews into Chroma."""
    n = upsert_reviews(reviews, only_relevant=True)
    log.info("Chroma upsert: %d reviews now in collection (total=%d)",
             n, collection_size())
    return n


def stage_precompute() -> bool:
    """Precompute the 6 canonical RAG answers."""
    try:
        from src.rag.precompute import precompute_all
        precompute_all()
        return True
    except Exception as exc:                                       # noqa: BLE001
        log.warning("Canonical pre-compute failed: %s", exc)
        return False


def stage_metadata(scrape_counts: dict[str, int], reviews: list[Review]) -> None:
    relevant_count = sum(1 for r in reviews if r.is_relevant)
    sources: dict[str, int] = {}
    for r in reviews:
        sources[r.source] = sources.get(r.source, 0) + 1

    by_canonical: dict[str, int] = {}
    for r in reviews:
        if not r.is_relevant:
            continue
        for t in r.canonical_tags:
            by_canonical[t] = by_canonical.get(t, 0) + 1

    feature_counts: dict[str, int] = {}
    for r in reviews:
        if not r.is_relevant:
            continue
        for f in (r.features_mentioned or []):
            feature_counts[f] = feature_counts.get(f, 0) + 1

    meta = {
        "last_refresh_utc": datetime.now(timezone.utc).isoformat(),
        "total_normalized": len(reviews),
        "total_relevant": relevant_count,
        "by_source": sources,
        "by_canonical_tag": by_canonical,
        "feature_mention_counts": dict(sorted(
            feature_counts.items(), key=lambda x: -x[1])[:25]),
        "scrape_counts_this_run": scrape_counts,
        "chroma_collection_size": collection_size(),
    }
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("Wrote metadata to %s", METADATA_PATH)


# ---------- main ----------

def main(seed_only: bool = False, skip_scrape: bool = False, skip_rag: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scrape_counts = stage_scrape(skip=skip_scrape or seed_only)
    reviews = stage_normalize(seed_only=seed_only)
    if not reviews:
        log.error("No reviews after normalize. Aborting.")
        return

    reviews = stage_classify(reviews)
    stage_embed(reviews)

    if not skip_rag:
        stage_precompute()

    stage_metadata(scrape_counts, reviews)
    log.info("Refresh complete.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-only", action="store_true",
                    help="Use only curated seed reviews (skip scrape).")
    ap.add_argument("--skip-scrape", action="store_true",
                    help="Reuse existing data/raw without re-scraping.")
    ap.add_argument("--skip-rag", action="store_true",
                    help="Skip canonical pre-compute (no LLM RAG calls).")
    args = ap.parse_args()
    main(
        seed_only=args.seed_only,
        skip_scrape=args.skip_scrape,
        skip_rag=args.skip_rag,
    )
