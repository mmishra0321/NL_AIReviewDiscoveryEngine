"""FastAPI app - the public surface consumed by the React frontend.

Run locally:
    uvicorn backend.main:app --reload --port 8000

Then the React dev server (vite, default :5173) proxies /api/* to :8000.
CORS is also enabled wide-open in dev so direct fetches work too.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

# Make `src` importable when uvicorn is launched from this folder
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend import export, github_actions, services              # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("backend")

app = FastAPI(
    title="Spotify Discovery - AI Review Engine API",
    version="1.0.0",
    description=(
        "REST API powering the React review-discovery dashboard. Wraps the "
        "Groq + RAG pipeline. All routes are prefixed with `/api`."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # dev: any origin. Tighten before deploy.
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


# ============================================================
# Request models
# ============================================================

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500,
                          description="Free-text question from the user.")


# ============================================================
# Routes
# ============================================================

@app.get("/api/health", tags=["meta"])
def health() -> dict:
    meta = services.metadata()
    return {
        "ok": True,
        "version": app.version,
        "last_refresh_utc": meta.get("last_refresh_utc"),
        "total_normalized": meta.get("total_normalized"),
        "total_relevant": meta.get("total_relevant"),
    }


@app.get("/api/meta", tags=["meta"])
def get_meta() -> dict:
    """Full metadata.json from the most recent refresh."""
    return services.metadata()


@app.post("/api/admin/reload", tags=["meta"])
def reload_caches() -> dict:
    """Drop in-memory caches so a fresh pipeline run is picked up
    without a server restart."""
    services.invalidate_caches()
    return {"ok": True, "reloaded": True}


# ----- Canonical answers (precomputed) ---------------------

@app.get("/api/canonical", tags=["canonical"])
def list_canonical() -> dict:
    """Summary list for the 6 canonical questions, sized for the home grid."""
    return {
        "generated_at": services.canonical_answers().get("generated_at"),
        "items": services.list_canonical_summaries(),
    }


@app.get("/api/canonical/{qid}", tags=["canonical"])
def canonical_detail(qid: str) -> dict:
    """Full answer + hydrated supporting reviews for one canonical question."""
    out = services.get_canonical_detail(qid)
    if out is None:
        raise HTTPException(status_code=404, detail=f"Unknown canonical id: {qid}")
    return out


# ----- Custom Q (scope + live RAG) -------------------------

@app.post("/api/ask", tags=["rag"])
def ask(req: AskRequest) -> dict:
    """Hybrid scope check, then live RAG synthesis if in scope."""
    try:
        return services.ask_custom_question(req.question)
    except Exception as exc:                                       # noqa: BLE001
        log.exception("ask failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ----- Review browse ---------------------------------------

@app.get("/api/reviews", tags=["reviews"])
def list_reviews(
    source: str | None = Query(None, description="Filter by source"),
    q: str | None = Query(None, description="Substring search on review text"),
    canonical_tag: str | None = Query(None, description="Filter by canonical tag id"),
    relevant_only: bool = Query(False, description="Only show reviews marked relevant"),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
) -> dict:
    return services.list_reviews(
        source=source, q=q, canonical_tag=canonical_tag,
        relevant_only=relevant_only, page=page, size=size,
    )


# ----- GitHub Actions history ------------------------------

@app.get("/api/actions", tags=["actions"])
def list_actions(limit: int = Query(10, ge=1, le=30)) -> dict:
    """Recent runs of the weekly refresh workflow, with per-run download
    URLs pinned to the commit each run produced. Cached server-side for 5 min."""
    return github_actions.list_action_runs(limit=limit)


# ----- Excel export ----------------------------------------

@app.get("/api/export.xlsx", tags=["export"])
def export_xlsx() -> Response:
    """Multi-sheet workbook: canonical Q&A, all reviews, themes, metadata."""
    blob = export.build_workbook()
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="spotify_discovery_review_engine.xlsx"',
        },
    )
