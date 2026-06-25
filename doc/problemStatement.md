# Problem Statement — Spotify Discovery Pain

> Capstone PM project, Growth Team at Spotify. This document is the single
> source of truth for what we're solving, who we're solving it for, and how
> the AI-native solution is structured across 4 project parts.

---

## 1. Context

Spotify has world-class technology and ~600M+ users globally. It has shipped
one of the most sophisticated music recommendation systems in tech:
Discover Weekly, Release Radar, Daily Mix, Daylist, Smart Shuffle, DJ,
AI Playlist, Niche Mixes, Blend — all powered by collaborative filtering,
content embeddings, and (more recently) generative AI.

**And yet:** a significant percentage of listening still comes from
repeat playlists, familiar artists, and previously discovered tracks.

The company's strategic goal:

> **Increase meaningful music discovery and reduce repetitive listening behavior.**

This project is a Growth PM's attempt to ground that goal in real user
voice, validate it with primary research, and ship an AI-native MVP.

---

## 2. The Core Problem (Working Hypothesis)

> Spotify's algorithmic discovery over-indexes on a user's listening history.
> The result is a *filter bubble* that gets tighter over time. Even users who
> *want* to discover new music end up replaying familiar tracks because:
>
> - Recommendations recycle the same artists across surfaces (Discover Weekly,
>   Daily Mix, Release Radar, Daylist all draw from the same taste profile).
> - Negative signals (skips, low-rating, manual replacement) are under-weighted.
> - There is no user-controllable "discovery intensity" — every recommendation
>   is tuned for safety and engagement, not novelty.
> - Regional, multilingual, niche, and emerging-artist catalogs exist in the
>   library but are systematically under-exposed in personalised surfaces.
> - The product offers no "break-out" mode for users explicitly trying to
>   escape their current taste graph.

Phase 1 (the AI Review Engine) confirms or rejects this hypothesis with
evidence from real users across App Store, Play Store, Reddit, and community
forums.

---

## 3. Project Brief — The 4 Mandated Parts

### Part 1: Build an AI-Powered Review Discovery Engine

Build an AI system that analyses user feedback at scale.

**Inputs:**
- App Store reviews
- Play Store reviews
- Reddit discussions (r/spotify, r/truespotify, r/musicsuggestions, r/LetsTalkMusic)
- Community forums (Spotify Community)
- Social media conversations (best-effort)

**Outputs:** The engine must answer the 6 canonical questions below — and only
those (with a graceful out-of-scope refusal for anything else). Each answer
must be grounded in retrieved review evidence (RAG), with the supporting
reviews displayed beneath the answer.

**The 6 Canonical Questions:**

| ID | Question |
|---|---|
| Q1 | Why do users struggle to discover new music? |
| Q2 | What are the most common frustrations with recommendations? |
| Q3 | What listening behaviours are users trying to achieve? |
| Q4 | What causes users to repeatedly listen to the same content? |
| Q5 | Which user segments experience different discovery challenges? |
| Q6 | What unmet needs emerge consistently across reviews? |

**Functional requirements (from the user's expanded brief):**

1. **Groq LLM** as the primary LLM (free tier — Llama 3.3 70B Versatile).
2. **RAG** for both classifying scraped data under themes AND answering questions.
3. **Auto-answer the 6 canonical questions** out of the box (precomputed at refresh).
4. **Scope wrapper**: a user-submitted custom question that is similar to the 6
   is routed to RAG; anything else returns a friendly "Out of scope" message.
5. **Per-answer review evidence**: 5 reviews shown initially, "View More" /
   shimmer to load the next 5.
6. **Curated seed reviews** supplement scraped data where the scrape is thin —
   transparently flagged in the UI with a `🌱` badge so credibility holds.
7. **GitHub Actions weekly refresh**: re-scrape → normalize → dedupe →
   discovery-relevance filter → embed → upsert into Chroma → re-categorize →
   update metadata → commit → triggers Streamlit Cloud auto-redeploy.
8. **Metadata header in the UI**: last scrape date, last GitHub Action run,
   total review count, normalized count, relevant count.
9. **Excel export**: download the full dataset as `.xlsx`.
10. **Filter to discovery-relevant only** before categorising under themes.
11. **Spotify-specific lexicon** baked into every prompt and surface (so the
    analysis cites concrete features: Discover Weekly, DJ, Smart Shuffle,
    Daily Mix, Daylist, Blend, Niche Mixes, Release Radar, etc.).

### Part 2: Validate the Opportunity Through User Research

5–6 user interviews with respondents from the segment surfaced by Phase 1.
Outputs: interview guide, recordings/notes, synthesis (affinity map / theme
table). Phase 1's segment analysis (Q5) determines who we recruit.

### Part 3: Define the Problem

Articulate:
1. The **root cause** (not the symptom).
2. The **target segment** (with sizing).
3. **Why solving this makes business sense** (retention, ARPU, discovery
   surface engagement, time-spent, churn reduction).

This becomes slides 3 & 4 of the deck.

### Part 4: Build an AI-Native MVP

Design and build a functional MVP — a prototype of a new feature inside
Spotify, with the AI doing the real work behind a mocked Spotify UI.

**Deploy to production** (Hugging Face Spaces or Streamlit Cloud, public URL).

The MVP must demonstrate why AI is *uniquely* suited to solving this problem,
which means the deck must explain:

- **Why traditional recommendation systems are insufficient** for this problem
  (collaborative filtering + content embeddings cannot reason about intent,
  context, novelty preference, or break-out cues).
- **What AI unlocks that was previously difficult** (natural-language intent
  capture, conversational discovery, on-the-fly justification, multi-modal
  context reasoning, explicit novelty control).
- **How AI changes the user experience** (from passive consumption of a
  taste-driven feed to active, intent-driven musical exploration).

---

## 4. Target User Segments (Hypothesis — to be validated in Phase 2)

Based on Phase 1 review analysis, we expect the following segments to surface.
The interview cohort will be drawn from the top segment.

| Segment | Pain Profile |
|---|---|
| **Stuck Heavy Users** (Premium, 5+ year tenure) | Filter bubble fatigue; high LTV at risk of churn to Apple Music / YouTube Music. |
| **Multilingual Listeners** (esp. India, LATAM, SEA) | Regional / language catalog underexposed; demographic profiling overrides taste signals. |
| **Niche-Genre Enthusiasts** (jazz, classical, indie, regional, electronic sub-genres) | Algorithm collapses sub-genre diversity into a few well-known artists. |
| **Discovery-Motivated Casual Users** (Free + low engagement Premium) | Algorithm needs daily input to update; sparse listeners get worse recs over time. |
| **Cross-Genre Explorers** (eclectic taste) | Algorithm treats tastes as binary; one strong signal collapses other interests. |

---

## 5. Deliverables Checklist

| # | Deliverable | Form | Where it ships |
|---|---|---|---|
| 1 | Review Analysis Workflow | Live URL | Streamlit Community Cloud |
| 2 | Workflow architecture | 1 slide inside deck | Slide 6 of `NL Spotify.pdf` |
| 3 | MVP prototype | Live URL | Hugging Face Spaces / Streamlit Cloud |
| 4 | Strategy & insights deck | 10-slide PDF, <40 MB | `NL Spotify.pdf` |
| 5 | Interview synthesis | Linked artefacts in deck | Notion / Google Doc |
| 6 | Survey / supporting docs | Linked artefacts in deck | Google Forms (if used) |

Naming rule: `NL Spotify.pdf` (no fellow name anywhere in the slide deck).

---

## 6. Constraints

| Constraint | Detail |
|---|---|
| Timeline | ≤7 calendar days end-to-end |
| Budget | $0 — every tool in the stack is free-tier |
| Stack | Python (code-based, not no-code) |
| LLM | Groq only (free tier) |
| Embeddings | Local sentence-transformers (no API quota) |
| Vector store | ChromaDB (committed to repo for free deployment) |
| Hosting | Streamlit Community Cloud + Hugging Face Spaces |
| CI | GitHub Actions (free for public repos) |
| Privacy | No PII collected; reviews from public sources only; curated reviews flagged |

---

## 7. Why AI Is the Right Tool (the defense we must build into the MVP)

Traditional recommendation systems are optimised for **engagement**, not
**discovery**. They are built on:

- Collaborative filtering (users like you → items they liked)
- Content-based embeddings (this song → similar songs)
- Heavy reliance on positive implicit signals (plays, likes, completes)
- Negative signals (skips, rate-down) under-weighted

These approaches **structurally cannot** do four things that this problem
demands:

1. **Reason about intent.** A user saying "I want to escape my usual taste"
   is a meta-request about the recommender itself. Classical recommenders
   have no API for that.
2. **Explain themselves.** Black-box recommendations make users distrust
   suggestions. Reviews repeatedly ask for "why this song?" — LLMs can answer.
3. **Handle context naturally.** "Recommend me music to study to as a
   bilingual Indian student" is a 3-axis ask (function × language × identity).
   Tag-based systems flatten this. LLMs reason across axes.
4. **Be novelty-aware on demand.** Today novelty is a side-effect of the
   training data mix; with LLMs we can expose an explicit dial that users
   control turn-by-turn.

The MVP (Phase 4–5) operationalises one or more of these.

---

## 8. Out of Scope (this project)

- Solving Spotify's bug-report backlog (login, audio quality, billing).
- Podcast / audiobook discovery (mentioned only as a discovery-surface conflict).
- Subscription pricing strategy.
- Music licensing / royalty issues.
- Live performance / event discovery.

Any question outside the 6 canonical questions returns the friendly
out-of-scope refusal in the dashboard.

---

## 9. Success Criteria (for this project, not for Spotify)

Project succeeds if:

- [ ] The Review Engine answers all 6 canonical questions with cited evidence
      from real reviews.
- [ ] The scope wrapper correctly routes ≥90% of test queries.
- [ ] The GitHub Action runs weekly and updates Chroma + metadata.
- [ ] The 10-slide deck tells a coherent story grounded in the engine's output
      and the 5–6 interviews.
- [ ] The MVP is deployed at a public URL and demonstrates an AI-native
      discovery interaction a classical recommender could not.
- [ ] Both live URLs (workflow + MVP) are clickable in the final deck.
