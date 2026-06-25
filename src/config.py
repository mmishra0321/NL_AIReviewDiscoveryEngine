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
RELEVANCE_BATCH_SIZE = 10            # reviews per LLM classifier call
RAG_RETRIEVE_K = 25                  # initial retrieval
RAG_TOP_K = 15                       # after MMR re-rank, fed to LLM
RAG_DISPLAY_PAGE = 5                 # reviews shown per UI page

# Scope wrapper thresholds (cosine similarity to nearest canonical Q)
SCOPE_IN_THRESHOLD = 0.55            # >= → in-scope (fast path)
SCOPE_OUT_THRESHOLD = 0.30           # <  → out-of-scope (fast path)
# Between thresholds → escalate to LLM classifier

# Chroma collection
CHROMA_COLLECTION = "spotify_reviews"
