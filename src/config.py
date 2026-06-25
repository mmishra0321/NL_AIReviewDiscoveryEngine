"""Central configuration: paths, constants, model identifiers."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SEED_DIR = DATA_DIR / "seed"
PROCESSED_DIR = DATA_DIR / "processed"
INSIGHTS_DIR = DATA_DIR / "insights"
CHROMA_DIR = DATA_DIR / "chroma_db"
METADATA_PATH = DATA_DIR / "metadata.json"

REVIEWS_PATH = PROCESSED_DIR / "reviews.jsonl"
SEED_PATH = SEED_DIR / "seed_reviews.jsonl"

# Ensure directories exist
for p in (RAW_DIR, SEED_DIR, PROCESSED_DIR, INSIGHTS_DIR, CHROMA_DIR):
    p.mkdir(parents=True, exist_ok=True)

# --- API keys ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "spotify-discovery-pm/0.1")

# --- Models ---
# Groq Llama 3.3 70B Versatile — high quality, fast, generous free tier
GROQ_MODEL = "llama-3.3-70b-versatile"
# Smaller / cheaper for high-volume relevance classification
GROQ_MODEL_FAST = "llama-3.1-8b-instant"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

# --- Pipeline knobs ---
RELEVANCE_BATCH_SIZE = 15            # reviews per LLM classifier call (tuned for 6k TPM)
RAG_RETRIEVE_K = 25                  # initial retrieval
RAG_TOP_K = 15                       # after MMR re-rank, fed to LLM
RAG_DISPLAY_PAGE = 5                 # reviews shown per UI page

# --- Groq free-tier guardrails ---
# Free tier today: 30 RPM but the binding constraint is TPM (~6k tok/min on
# llama-3.1-8b-instant, ~12k on llama-3.3-70b-versatile).
# Each relevance-classify call burns ~1500-2000 tokens, so the effective RPM
# we can sustain is ~4-6/min, i.e. ~12-15s between calls. We throttle to 13s
# so Groq never has to 429 us — cleaner logs, predictable pace, same throughput.
GROQ_MIN_INTERVAL_SECONDS = 13.0

# Hard ceiling on how many normalized reviews enter the relevance classifier
# (and therefore get embedded + indexed). Keeps Groq token usage bounded.
# Set to 1000 by default — gives 100 batches × ~500 tok = ~50k tok per refresh,
# well under daily limits.
MAX_REVIEWS_TO_CLASSIFY = 1000

# Per-source quotas when applying MAX_REVIEWS_TO_CLASSIFY. Seed reviews are
# always kept in full; the remaining budget is split across scraped sources.
# Any source that under-delivers donates its slack to the others.
REVIEW_BUDGET_BY_SOURCE: dict[str, int] = {
    "curated_seed": 100,
    "app_store":    400,
    "play_store":   350,
    "youtube":      150,
    "reddit":       0,    # requires OAuth; off by default
    "trustpilot":   0,    # blocked by Cloudflare; off by default
    "community":    0,
}

# Scope wrapper thresholds (cosine similarity to nearest canonical Q)
SCOPE_IN_THRESHOLD = 0.55            # >= → in-scope (fast path)
SCOPE_OUT_THRESHOLD = 0.30           # <  → out-of-scope (fast path)
# Between thresholds → escalate to LLM classifier

# Chroma collection
CHROMA_COLLECTION = "spotify_reviews"
