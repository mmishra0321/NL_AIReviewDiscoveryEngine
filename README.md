# 01 — Spotify Discovery Pain · AI Review Discovery Engine

> Part 1 of a 3-folder capstone PM project on Spotify music discovery.
> An AI-native workflow that mines Spotify user feedback at scale to
> surface why discovery feels broken — even with world-class recommendations.

📁 **Sibling folders:**
- [`../02-mvp/`](../02-mvp/) — the AI-native MVP (Sonar) that operationalises these insights
- [`../03-research-and-deck/`](../03-research-and-deck/) — interviews, problem definition, and the final 10-slide deck

📄 **Read first:**
- [`doc/problemStatement.md`](./doc/problemStatement.md) — full project brief + this engine's mandate
- [`doc/architecture.md`](./doc/architecture.md) — detailed engine architecture (every component mapped to a file)
- [`doc/deployment.md`](./doc/deployment.md) — how to deploy this to Streamlit Cloud + wire up GitHub Actions

## Working hypothesis

Spotify's algorithmic discovery (Discover Weekly, Release Radar, Daily Mixes) over-indexes
on listening history and creates a filter bubble. Users who *want* to discover new music
can't escape their past — especially across mood shifts, genre crossings, and language /
regional boundaries. Even discovery-motivated users end up replaying familiar tracks.

This repo's review engine confirms or rejects this hypothesis with evidence from real users.

## What this engine does

1. **Scrapes** Spotify reviews from App Store, Play Store, Reddit, and Community forums.
2. **Filters** to discovery-relevant reviews using a Groq LLM classifier.
3. **Embeds** filtered reviews locally (sentence-transformers) into a persistent Chroma DB.
4. **Categorizes** each review under the 6 canonical questions + emergent sub-themes.
5. **Answers** the 6 canonical questions via RAG (vector retrieval + Groq synthesis).
6. **Wraps** custom questions with a scope guardrail (in-scope → RAG, out-of-scope → friendly refusal).
7. **Refreshes** weekly via GitHub Actions, recomputing metadata.
8. **Exposes** everything in a deployed Streamlit dashboard with paginated review evidence.

## The 6 canonical questions

1. Why do users struggle to discover new music?
2. What are the most common frustrations with recommendations?
3. What listening behaviours are users trying to achieve?
4. What causes users to repeatedly listen to the same content?
5. Which user segments experience different discovery challenges?
6. What unmet needs emerge consistently across reviews?

## Stack (all free tier)

| Layer | Tool |
|---|---|
| LLM | Groq (Llama 3.3 70B Versatile) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local CPU) |
| Vector store | ChromaDB (persistent, committed to repo) |
| Scraping | google-play-scraper, app-store-scraper, PRAW |
| Frontend | Streamlit |
| CI | GitHub Actions (weekly cron) |
| Deploy | Streamlit Community Cloud |

## Repo layout

```
.
├── app/                  # Streamlit dashboard
├── src/
│   ├── config.py         # Paths, constants
│   ├── lexicon.py        # Spotify feature lexicon
│   ├── canonical.py      # 6 canonical questions
│   ├── scrapers/         # Per-source scrapers
│   ├── pipeline/         # Normalize, dedupe, filter, embed, categorize
│   └── rag/              # Retrieval, scope wrapper, answer generation
├── data/
│   ├── raw/              # Scraped JSONL per source
│   ├── seed/             # Curated supplementary reviews
│   ├── processed/        # reviews.jsonl (canonical store)
│   ├── chroma_db/        # Vector index (committed)
│   ├── insights/         # Pre-computed answers per question
│   └── metadata.json     # Last scrape, counts, last action
├── .github/workflows/    # Weekly refresh action
└── deck/                 # Slide outline + exported diagrams
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
cp .env.example .env             # then fill in keys
```

## Run locally

```bash
# 1. Fetch reviews (one-shot; weekly refresh is automated via GH Actions)
python -m src.pipeline.refresh

# 2. Launch dashboard
streamlit run app/streamlit_app.py
```

## Deploy

Streamlit Cloud auto-deploys from `main`. The weekly GitHub Action commits new data,
which triggers an automatic redeploy — keeping the live URL fresh.
