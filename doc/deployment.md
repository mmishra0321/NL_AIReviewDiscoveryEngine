# Deployment Guide

## 1. GitHub repo configuration (one-time)

After pushing to GitHub, configure two things:

### Add the Groq API key as a secret

The weekly GitHub Action needs the same `GROQ_API_KEY` you set in `.env`.

1. Open: https://github.com/mmishra0321/NL_AIReviewDiscoveryEngine/settings/secrets/actions
2. Click **New repository secret**
3. **Name:** `GROQ_API_KEY`
4. **Value:** paste your Groq key (same one in `.env`)
5. Click **Add secret**

### Grant the Action write access to commit refreshed data

1. Open: https://github.com/mmishra0321/NL_AIReviewDiscoveryEngine/settings/actions
2. Scroll to **Workflow permissions**
3. Select **Read and write permissions**
4. Check **Allow GitHub Actions to create and approve pull requests** (optional but useful)
5. Click **Save**

### Trigger the Action once to verify

1. Open: https://github.com/mmishra0321/NL_AIReviewDiscoveryEngine/actions
2. Click **Weekly Review Refresh** in the left sidebar
3. Click **Run workflow** → leave defaults (or check "seed_only=true" for first test) → **Run workflow**
4. Watch the run — should complete in 3-7 minutes
5. After it succeeds, check the `main` branch — `data/metadata.json` should show a fresh `last_refresh_utc`

## 2. Streamlit Community Cloud deployment

1. Open: https://share.streamlit.io
2. Sign in with your GitHub account (`mmishra0321`)
3. Click **Create app** → **Deploy a public app from GitHub**
4. **Repository:** `mmishra0321/NL_AIReviewDiscoveryEngine`
5. **Branch:** `main`
6. **Main file path:** `app/streamlit_app.py`
7. **App URL:** customize to something like `spotify-discovery-pm` so the URL is clean
8. Click **Advanced settings** → **Secrets** → paste:

```toml
GROQ_API_KEY = "gsk_your_real_key_here"
```

9. Click **Deploy!**

First deploy takes 3-5 minutes (Streamlit installs all dependencies). Subsequent redeploys (triggered by the weekly Action committing new data) are faster.

You'll get a public URL like `https://spotify-discovery-pm.streamlit.app`.

## 3. Embed the URL in the deck

Add the live URL to:
- README.md (add a badge at the top)
- Slide 6 of the deck (the AI Review Workflow slide)
- Project submission deliverables doc

## 4. Verify the auto-redeploy loop

The whole point of the GitHub Action + Streamlit Cloud combo is the
auto-refresh loop:

```
   GH Action (weekly cron)
        │
        ▼
   Scrape → normalize → classify → embed → upsert → precompute
        │
        ▼
   git commit + push to main
        │
        ▼
   Streamlit Cloud detects push → auto-rebuilds → live URL has new data
```

To verify: after the first manual Action run, refresh your Streamlit URL.
The "Last refresh" pill in the header should show the new timestamp.

## 5. Known constraints (free tier)

| Component | Limit | What we do |
|---|---|---|
| Groq Llama 3.1 8B Instant | ~30 RPM | tenacity retries with exponential backoff |
| Groq Llama 3.3 70B Versatile | ~30 RPM | only 6 calls per refresh (one per canonical Q) |
| Streamlit Cloud free | 1GB RAM, 1 CPU, sleeps after inactivity | adequate for our app |
| GitHub Actions free | 2,000 mins/month for private; unlimited for public | a refresh run uses ~10 mins → fine |
| ChromaDB committed to repo | ~5 MB for 1,000 reviews | safely under GitHub's 100 MB soft limit |

If you ever hit the Streamlit Cloud memory limit, the first culprit will be
the sentence-transformers model. Mitigation: switch `EMBED_MODEL` in
`src/config.py` to a smaller model like `paraphrase-MiniLM-L3-v2`.
