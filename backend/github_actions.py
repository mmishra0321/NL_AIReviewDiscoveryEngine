"""Surface the GitHub Actions refresh history in the UI.

We expose two endpoints worth of data:

1. The list of past *successful* runs of the weekly refresh workflow, fetched
   from `GET /repos/{o}/{r}/actions/workflows/{file}/runs`.
2. For each run, three "raw content" download URLs pinned to the commit that
   the run produced (queried separately from the commits API, filtered by the
   bot author). These are stable, public, and never require authentication.

Anonymous GitHub API is rate-limited to 60 req/hour per source IP, so the
results are cached for 5 minutes.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from src.config import (
    GITHUB_BOT_AUTHOR,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_WORKFLOW_FILE,
)

log = logging.getLogger(__name__)

GH_API = "https://api.github.com"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}"

# Files exposed for per-run download. Keep this list small; we link, we don't
# proxy bytes (so even an HTTP 200 hop through the backend is avoided).
DOWNLOADABLE_FILES = {
    "metadata":             "data/metadata.json",
    "reviews_jsonl":        "data/processed/reviews.jsonl",
    "canonical_answers":    "data/insights/canonical_answers.json",
    "seed_reviews":         "data/seed/seed_reviews.jsonl",
}

# --- 5 minute response cache --------------------------------------------

_CACHE_TTL = 300
_cache: dict[str, tuple[float, Any]] = {}


def _get_cached(key: str) -> Any | None:
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < _CACHE_TTL:
        return hit[1]
    return None


def _set_cached(key: str, val: Any) -> None:
    _cache[key] = (time.time(), val)


# --- GitHub API wrappers ------------------------------------------------

def _gh_get(path: str, params: dict | None = None) -> Any:
    """Anonymous GET to the GitHub REST API."""
    r = requests.get(
        f"{GH_API}{path}",
        params=params or {},
        headers={"Accept": "application/vnd.github+json", "User-Agent": "spotify-discovery-engine"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _workflow_runs(limit: int = 10) -> list[dict]:
    """Recent runs of the refresh workflow."""
    try:
        data = _gh_get(
            f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_FILE}/runs",
            params={"per_page": limit},
        )
        return data.get("workflow_runs", []) or []
    except Exception as exc:                                # noqa: BLE001
        log.warning("Workflow runs API failed: %s", exc)
        return []


def _bot_commits(limit: int = 10) -> list[dict]:
    """Recent commits authored by the refresh bot. Each commit's SHA is the
    output of one successful workflow run."""
    try:
        return _gh_get(
            f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits",
            params={"author": GITHUB_BOT_AUTHOR, "per_page": limit},
        )
    except Exception as exc:                                # noqa: BLE001
        log.warning("Commits API failed: %s", exc)
        return []


def _latest_main_commit() -> dict | None:
    try:
        return _gh_get(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/main")
    except Exception as exc:                                # noqa: BLE001
        log.warning("Latest main commit fetch failed: %s", exc)
        return None


def _downloads_for(sha: str) -> dict[str, str]:
    return {
        key: f"{RAW_BASE}/{sha}/{path}"
        for key, path in DOWNLOADABLE_FILES.items()
    }


# --- Public service ------------------------------------------------------

def list_action_runs(limit: int = 10) -> dict[str, Any]:
    """Return a UI-friendly history of the refresh action.

    Shape:
        {
          "owner": "...", "repo": "...", "workflow_file": "...",
          "actions_tab_url": "https://github.com/.../actions/workflows/refresh.yml",
          "runs": [
            {
              "id": int,
              "title": str,
              "status": "success" | "failure" | "pending" | "no_action_yet",
              "started_at": iso,
              "finished_at": iso | None,
              "html_url": str,
              "head_sha": str,
              "output_sha": str | None,   # bot commit produced by this run
              "downloads": {key: raw_url}, # only present when output_sha is known
            },
            ...
          ],
          "last_success": {...} | None,
        }
    """
    key = f"runs:{limit}"
    cached = _get_cached(key)
    if cached is not None:
        return cached

    actions_tab_url = (
        f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/workflows/{GITHUB_WORKFLOW_FILE}"
    )

    runs = _workflow_runs(limit=limit)
    bot_commits = _bot_commits(limit=limit + 5)

    # Index bot commits by date (descending) so we can match them to runs.
    # Strategy: each successful run produces ~1 commit; pair the i-th
    # successful run with the i-th bot commit (both sorted newest first).
    bot_iter = iter(bot_commits)
    runs_out: list[dict] = []
    last_success: dict | None = None

    for r in runs:
        conclusion = r.get("conclusion") or "pending"
        status_norm = {
            "success": "success", "failure": "failure", "cancelled": "cancelled",
            "neutral": "success", "timed_out": "failure", "skipped": "skipped",
            None: "pending", "": "pending",
        }.get(conclusion, conclusion)

        output_sha: str | None = None
        if status_norm == "success":
            bc = next(bot_iter, None)
            if bc:
                output_sha = bc.get("sha")

        row = {
            "id": r.get("id"),
            "title": r.get("display_title") or r.get("name", "refresh"),
            "status": status_norm,
            "started_at": r.get("created_at") or r.get("run_started_at"),
            "finished_at": r.get("updated_at"),
            "html_url": r.get("html_url"),
            "head_sha": r.get("head_sha"),
            "output_sha": output_sha,
            "downloads": _downloads_for(output_sha) if output_sha else None,
        }
        runs_out.append(row)
        if last_success is None and status_norm == "success":
            last_success = row

    # If the workflow hasn't run yet on GitHub (fresh repo), surface the latest
    # commit on `main` as a synthetic "no_action_yet" row so the UI still has
    # working download links.
    if not runs_out:
        latest = _latest_main_commit()
        if latest:
            sha = latest.get("sha")
            commit = latest.get("commit") or {}
            runs_out.append({
                "id": None,
                "title": "Initial seed data (no Action run yet)",
                "status": "no_action_yet",
                "started_at": (commit.get("author") or {}).get("date"),
                "finished_at": (commit.get("author") or {}).get("date"),
                "html_url": latest.get("html_url"),
                "head_sha": sha,
                "output_sha": sha,
                "downloads": _downloads_for(sha) if sha else None,
            })

    payload = {
        "owner": GITHUB_OWNER,
        "repo": GITHUB_REPO,
        "workflow_file": GITHUB_WORKFLOW_FILE,
        "actions_tab_url": actions_tab_url,
        "runs": runs_out,
        "last_success": last_success or (runs_out[0] if runs_out else None),
    }
    _set_cached(key, payload)
    return payload
