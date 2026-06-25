# Architecture - AI Review Discovery Engine (Part 1)

> Companion to [`problemStatement.md`](./problemStatement.md). Every component
> below maps to a concrete file in this repo and to one of the 11 functional
> requirements (R1-R11) in the brief.

---

## 1. System at a glance

```mermaid
flowchart TB
    subgraph SRC["📥 Data Sources"]
        S1[App Store reviews<br/>iTunes RSS · 5 storefronts]
        S2[Play Store reviews<br/>google-play-scraper · 6 storefronts]
        S3[Reddit · deferred to v2]
        S4[Curated seed reviews 🌱<br/>100 records]
    end

    subgraph CI["⏱ Weekly GitHub Actions (cron 02:00 UTC Mon)"]
        N[Normalize + Dedupe<br/>SHA-256 stable hash]
        R[Discovery-Relevance Filter<br/>Groq Llama 3.1 8B Instant<br/>batched JSON output]
        E[Local Embeddings<br/>sentence-transformers MiniLM<br/>384-dim, CPU]
        V[(ChromaDB<br/>persistent · committed)]
        P[Pre-compute 6 Canonical Answers<br/>RAG: retrieve → MMR → Groq Llama 3.3 70B]
        M[metadata.json<br/>git commit + push]
    end

    subgraph UI["🖥 Streamlit Cloud (always-on dashboard)"]
        H[Metadata Header<br/>counts · last refresh · Excel export]
        Q6[6 Canonical Question Cards<br/>precomputed answers + cited evidence]
        CQ[Custom Question Box]
        SW{Hybrid Scope Wrapper<br/>cosine fast-path +<br/>Groq LLM borderline fallback}
        RAG[Live RAG<br/>Chroma retrieval → MMR → Groq synthesis]
        OOS[Out-of-Scope refusal]
        PAG[Paginated review evidence<br/>5 at a time · View More]
        TH[Themes & Segments tab]
        ARCH[Architecture tab<br/>= the 1-slider for the deck]
        RAW[Raw Data tab<br/>search · filter · Excel]
    end

    S1 --> N
    S2 --> N
    S3 -.-> N
    S4 --> N
    N --> R --> E --> V --> P --> M
    M -.->|auto redeploy| UI
    H --- Q6 --- CQ
    CQ --> SW
    SW -->|in-scope| RAG
    SW -->|out-of-scope| OOS
    RAG --> PAG
    Q6 --> PAG

    style CI fill:#191414,stroke:#1DB954,color:#fff
    style UI fill:#191414,stroke:#1DB954,color:#fff
    style V fill:#1DB954,stroke:#fff,color:#191414
    style SW fill:#2D5016,stroke:#1DB954,color:#fff
    style RAG fill:#2D5016,stroke:#1DB954,color:#fff
```

---

## 2. Build Phases (Phase-by-Phase Plan Architecture)

The engine was built in **8 internal phases (E0 - E7)**. Phases E0-E6 are
complete; E7 (production deploy) waits for the GitHub push.

```mermaid
flowchart LR
    E0[E0 · Scaffold<br/>1h ✅] --> E1[E1 · Ingestion<br/>2h ✅]
    E1 --> E2[E2 · Normalize +<br/>Filter · 2h ✅]
    E2 --> E3[E3 · Embed +<br/>Index · 1h ✅]
    E3 --> E4[E4 · RAG System<br/>3h ✅]
    E4 --> E5[E5 · Dashboard<br/>3h ✅]
    E5 --> E6[E6 · CI/CD<br/>1h ✅]
    E6 --> E7[E7 · Deploy<br/>30m ⏳]

    style E7 fill:#2D5016,stroke:#1DB954,color:#fff
```

This phase chain is *strictly sequential* - each phase consumes the
previous phase's output. Total build time across E0-E6: ~13 hours of
focused work, which collapsed into a single intense build day.

---

### E0 - Scaffold (config, schema, Groq client, canonicals, lexicon)

| Field | Value |
|---|---|
| **Objective** | Lay the foundation files every other phase depends on |
| **Duration** | ~1 hour · ✅ Done |
| **Inputs** | Brief's 6 canonical questions; Groq API key; Spotify feature list |
| **Outputs** | Working Groq client with retries; Pydantic schemas; the canonical questions encoded as data; the Spotify lexicon |
| **Tools** | `groq` SDK, `pydantic`, `python-dotenv`, `tenacity` |
| **Files produced** | `src/config.py`, `src/canonical.py`, `src/lexicon.py`, `src/schema.py`, `src/pipeline/groq_client.py`, `.env`, `.env.example`, `requirements.txt` |
| **Acceptance** | `[1]` and `[2]` smoke checks pass (env loaded; Groq PING→PONG) |

---

### E1 - Data Ingestion (scrapers + curated seed reviews)

| Field | Value |
|---|---|
| **Objective** | Pull review data from multiple public sources; bootstrap with curated seeds |
| **Duration** | ~2 hours · ✅ Done (seed loaded; scrapers ready for first weekly run in E7) |
| **Inputs** | iTunes RSS endpoints (5 storefronts), Play Store package ID `com.spotify.music` (6 storefronts), 100 hand-crafted seed records |
| **Outputs** | Raw record streams from App Store + Play Store; 100 seed reviews in JSONL |
| **Tools** | `requests` (iTunes RSS), `google-play-scraper`, JSONL |

```mermaid
flowchart LR
    APP[Apple iTunes RSS<br/>5 storefronts × 8 pages] --> RAW[Raw record stream]
    PLAY[google-play-scraper<br/>6 storefronts × 200] --> RAW
    SEED[100 curated seed reviews<br/>🌱 transparently flagged] --> RAW
```

| Field | Value |
|---|---|
| **Files produced** | `src/scrapers/appstore.py`, `src/scrapers/playstore.py`, `data/seed/seed_reviews.jsonl` |
| **Acceptance** | `[6]` smoke check (100 seed records loadable); scrapers callable with no exceptions |

---

### E2 - Normalization, Dedupe & Discovery-Relevance Filtering

| Field | Value |
|---|---|
| **Objective** | Convert raw records into a canonical store; mark each review's discovery-relevance + canonical tags |
| **Duration** | ~2 hours · ✅ Done |
| **Inputs** | Raw record streams from E1 |
| **Outputs** | `data/processed/reviews.jsonl` with `is_relevant`, `canonical_tags`, `features_mentioned` per record |
| **Tools** | Groq Llama 3.1 8B Instant (cheap classifier), `tenacity` exponential backoff, Pydantic |

```mermaid
flowchart LR
    RAW[Raw records] --> NORM[Normalize<br/>+ SHA-256 stable ID]
    NORM --> DEDUPE[Dedupe by ID]
    DEDUPE --> BATCH[Batch · 10 reviews/call]
    BATCH --> GROQ[Groq 8B JSON mode<br/>relevance + canonical tags]
    GROQ --> MERGE[Merge verdicts into Review]
    MERGE --> JSONL[reviews.jsonl]
```

| Field | Value |
|---|---|
| **Files produced** | `src/pipeline/normalize.py`, `src/pipeline/relevance.py` |
| **Acceptance** | 100 normalized → 97 classified discovery-relevant (verified) |

---

### E3 - Embeddings & Vector Indexing

| Field | Value |
|---|---|
| **Objective** | Build a searchable semantic index from relevant reviews |
| **Duration** | ~1 hour · ✅ Done |
| **Inputs** | 97 relevant reviews from E2 |
| **Outputs** | ChromaDB collection `spotify_reviews` at `data/chroma_db/` (97 vectors × 384 dim) |
| **Tools** | `sentence-transformers/all-MiniLM-L6-v2` (local, CPU, ~50 records/sec), ChromaDB persistent client |

```mermaid
flowchart LR
    REVIEWS[97 relevant reviews] --> CHUNK[Build text body<br/>title + body + features]
    CHUNK --> EMB[MiniLM 384-dim<br/>normalized]
    EMB --> META[Build metadata<br/>source · canonical_tags · features]
    EMB --> UPSERT[Chroma upsert<br/>by stable ID]
    META --> UPSERT
    UPSERT --> CHROMA[(chroma_db/<br/>committed to repo)]
```

| Field | Value |
|---|---|
| **Files produced** | `src/pipeline/embed.py`, `data/chroma_db/` (sqlite + HNSW binaries) |
| **Acceptance** | `[3]` and `[4]` smoke checks pass (384-dim vectors; count 97→98→97 round-trip) |

---

### E4 - RAG System (Scope · Retrieve · Answer · Precompute)

| Field | Value |
|---|---|
| **Objective** | Serve grounded answers for the 6 canonical questions + a runtime endpoint for custom ones |
| **Duration** | ~3 hours · ✅ Done |
| **Inputs** | ChromaDB from E3; the 6 canonical question definitions from E0 |
| **Outputs** | `data/insights/canonical_answers.json` (6 precomputed answers) + live RAG callable for custom questions |
| **Tools** | Groq Llama 3.3 70B Versatile (high-quality synthesis), Groq 8B (scope borderline), MMR re-ranker, Pydantic structured output |

```mermaid
flowchart TB
    Q[Question] --> SCOPE{Scope wrapper<br/>cosine + LLM hybrid}
    SCOPE -->|out| REFUSE[Friendly refusal]
    SCOPE -->|in| EMB[Embed query]
    EMB --> SIM[Chroma top-25]
    SIM --> MMR[MMR λ=0.7 → top-15]
    MMR --> PROMPT[Build prompt:<br/>question + reviews + lexicon]
    PROMPT --> GROQ[Groq 70B<br/>JSON-mode structured output]
    GROQ --> ANS["RagAnswer<br/>answer · features · segments · confidence · cited IDs"]

    PRE[Precompute loop<br/>for each canonical Q] --> Q
    ANS --> JSON[canonical_answers.json]

    style ANS fill:#1DB954,stroke:#fff,color:#191414
```

| Field | Value |
|---|---|
| **Files produced** | `src/rag/scope.py`, `src/rag/retrieve.py`, `src/rag/answer.py`, `src/rag/precompute.py`, `data/insights/canonical_answers.json` |
| **Acceptance** | `[5]` smoke check (in=0.75, out=0.04 cosine); all 6 canonical answers populated in JSON |

---

### E5 - Streamlit Dashboard UI

| Field | Value |
|---|---|
| **Objective** | Render every requirement (R1-R11) as a tab/widget a human can interact with |
| **Duration** | ~3 hours · ✅ Done |
| **Inputs** | `metadata.json` + `canonical_answers.json` + `reviews.jsonl` + ChromaDB |
| **Outputs** | A 5-tab dashboard with Spotify-dark theme, metadata header, Excel downloads, paginated review evidence, scope-wrapped custom question box |
| **Tools** | Streamlit, Plotly (theme bar charts), `openpyxl` + `xlsxwriter` (Excel export), custom CSS |

```mermaid
flowchart LR
    META[metadata.json] --> HEADER[Metadata header<br/>last refresh · counts · downloads]
    PRECOMP[canonical_answers.json] --> TAB1[Tab 1<br/>6 canonical Q cards]
    CHROMA[(ChromaDB)] --> TAB2[Tab 2<br/>Ask Your Own + scope]
    REVIEWS[reviews.jsonl] --> TAB3[Tab 3<br/>Themes & Segments]
    DOCS[architecture.md] --> TAB4[Tab 4<br/>Architecture · 1-slider]
    REVIEWS --> TAB5[Tab 5<br/>Raw Data + Excel]
```

| Field | Value |
|---|---|
| **Files produced** | `app/streamlit_app.py`, `.streamlit/config.toml` |
| **Acceptance** | All 5 tabs render with seed data; Excel downloads produce valid `.xlsx`; review pagination works ("View More" loads next 5) |

---

### E6 - CI/CD (GitHub Actions weekly refresh)

| Field | Value |
|---|---|
| **Objective** | Make the engine self-refresh weekly without human intervention |
| **Duration** | ~1 hour · ✅ Built (first end-to-end run waits for E7) |
| **Inputs** | A `main` branch on GitHub + the `GROQ_API_KEY` secret |
| **Outputs** | Mondays at 02:00 UTC, the engine re-scrapes, re-classifies, re-embeds, re-precomputes, commits updated `data/` back to the repo |
| **Tools** | GitHub Actions (free for public repos), `cron` syntax, `workflow_dispatch` for manual trigger |

```mermaid
flowchart LR
    CRON[cron 02:00 UTC Mon] --> CHK[Checkout]
    DISPATCH[workflow_dispatch<br/>manual] --> CHK
    CHK --> SETUP[Setup Python 3.11<br/>+ pip cache]
    SETUP --> INSTALL[Install requirements]
    INSTALL --> RUN[python -m src.pipeline.refresh]
    RUN --> COMMIT[git commit<br/>under bot identity]
    COMMIT --> PUSH[git push → main]
    PUSH --> REDEPLOY[Streamlit Cloud<br/>auto-redeploy]
```

| Field | Value |
|---|---|
| **Files produced** | `.github/workflows/refresh.yml`, `src/pipeline/refresh.py` |
| **Acceptance** | Workflow file lints clean (`act --list` succeeds); first `workflow_dispatch` will be verified in E7 |

---

### E7 - Production Deployment

| Field | Value |
|---|---|
| **Objective** | Get the engine live on the public internet, served via Streamlit Cloud, with weekly CI passing |
| **Duration** | ~30 min · ⏳ Pending |
| **Inputs** | Local repo at green state · GitHub PAT · Streamlit Cloud account · `GROQ_API_KEY` |
| **Outputs** | Live public URL; weekly cron green; auto-redeploy on push |
| **Tools** | GitHub PAT (interactive), Streamlit Community Cloud, GitHub Repo Settings → Secrets |

**Steps:**
1. `git push -u origin main` (authenticated with PAT)
2. Add `GROQ_API_KEY` as a repo secret (GitHub → Settings → Secrets and variables → Actions)
3. share.streamlit.io → New app → point at `app/streamlit_app.py` on `main`
4. Add `GROQ_API_KEY` under "Advanced settings → Secrets" (TOML format: `GROQ_API_KEY = "gsk_..."`)
5. Deploy; wait for first build (~3 min)
6. Manually trigger the weekly workflow once (`Actions → Refresh → Run workflow`) to verify CI works
7. Smoke-check the live URL in an incognito window

| Field | Value |
|---|---|
| **Files touched** | None new; configuration in Streamlit Cloud + GitHub Settings |
| **Acceptance** | Live URL renders the dashboard for an anonymous visitor; `workflow_dispatch` run completes with a green check |

---

### Engine phase dependency graph

```mermaid
flowchart LR
    E0 --> E1 --> E2 --> E3 --> E4
    E4 --> E5
    E4 --> E6
    E5 --> E7
    E6 --> E7

    classDef done fill:#1DB954,stroke:#fff,color:#191414
    classDef pending fill:#2D5016,stroke:#1DB954,color:#fff
    class E0,E1,E2,E3,E4,E5,E6 done
    class E7 pending
```

Note that **E5 (UI) and E6 (CI) are parallelisable after E4** - they don't
depend on each other. Both must complete before E7 (deploy).

---

## 3. Component-by-component walkthrough

Every component below lists: **what it does · file · inputs · outputs · why this design**.

### 2.1 Data ingestion

#### 2.1.1 App Store scraper
- **File:** `src/scrapers/appstore.py`
- **Mechanism:** Direct GET against Apple's public iTunes RSS endpoint:
  `https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id=324684580/sortBy=mostRecent/json`
- **Storefronts:** US, GB, IN, DE, BR · up to 8 pages each (~400 reviews/storefront max)
- **Inputs:** none (network)
- **Outputs:** raw dict list with `id`, `text`, `rating`, `author`, `date`, `locale`, `url`
- **Why:** No API key needed, no third-party dependency that pins old `requests`. Native control over pagination + rate-limit politeness (`time.sleep(0.5)` per page).

#### 2.1.2 Play Store scraper
- **File:** `src/scrapers/playstore.py`
- **Mechanism:** `google-play-scraper` (active OSS, no key)
- **Storefronts:** `us`, `gb`, `in/en`, `in/hi`, `de`, `br` · 100-300 reviews each
- **Outputs:** same shape as App Store
- **Why:** Most mature scraper in the ecosystem; supports multi-locale; no auth.

#### 2.1.3 Curated seed reviews
- **File:** `data/seed/seed_reviews.jsonl` (100 records)
- **Mechanism:** Hand-authored to cover all 6 canonical questions × multiple segments × specific Spotify features
- **Transparency:** Tagged `source: "curated_seed"`; rendered with a 🌱 badge in the UI; mentioned in deck
- **Why:** Bootstraps a working v1 even before scrapers run; ensures rare segments (multilingual, niche genre, 50+ age cohort) are represented from day 1.

### 2.2 Normalization & dedupe

- **File:** `src/pipeline/normalize.py`
- **Functions:** `normalize_record(raw, source) → Review`, `merge_and_dedupe(reviews)`, `write_canonical_store(reviews)`
- **Stable ID:** `sha256(source + ":" + source_id)[:16]` - same review across re-scrapes produces the same ID → upserts are idempotent
- **Schema:** `src/schema.py` defines `Review` (Pydantic), including derived fields populated downstream: `is_relevant`, `canonical_tags`, `features_mentioned`, `user_segments`
- **Why JSONL:** Streaming-friendly, line-diff-friendly in git, no parquet/columnar dependency for tiny scale.

### 2.3 Discovery-relevance classifier (LLM filter)

- **File:** `src/pipeline/relevance.py`
- **Model:** Groq Llama 3.1 8B Instant (cheap + fast for high-volume classification)
- **Prompting:** System prompt embeds the 6 canonical questions + the full Spotify feature lexicon; instructs the model to output strict JSON for a batch of 10 reviews per call
- **Why batched:** Cuts per-review API cost ~10×; fewer rate-limit hits
- **Output per review:** `is_relevant` (bool), `reason` (one clause), `canonical_tags` (subset of Q1-Q6)
- **Rate-limit handling:** `tenacity` retry with exponential backoff (multiplier=2, min=2s, max=30s, 5 attempts) - verified working: actual run hit Groq 429s and auto-recovered

```mermaid
sequenceDiagram
    participant P as relevance.py
    participant G as Groq Llama 3.1 8B
    participant T as Tenacity

    P->>P: batch reviews into groups of 10
    loop For each batch
        P->>G: POST /chat/completions (JSON mode)
        alt 429 Rate Limit
            G-->>P: 429
            T->>T: wait exponential
            P->>G: retry
        end
        G-->>P: {"verdicts": [{id, is_relevant, canonical_tags, reason}, ...]}
        P->>P: merge verdicts into Review objects
    end
```

### 2.4 Embedding layer

- **File:** `src/pipeline/embed.py`
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~80 MB, CPU)
- **Why local, not API:** Zero rate limit, zero cost, deterministic across runs; ~50 reviews/sec on a modern CPU
- **Normalisation:** `normalize_embeddings=True` → cosine similarity = dot product, simpler downstream math
- **Cached:** `@lru_cache` so the model loads once per process

### 2.5 Vector store - ChromaDB

- **Persistence:** `data/chroma_db/` (committed to repo)
- **Why committed:** Streamlit Cloud has no persistent disk between deploys; baking the index into the repo means every redeploy is zero-setup
- **Size budget:** ~10-20 MB for 5k reviews × 384-dim float32 → well below git's 100 MB warning
- **Collection name:** `spotify_reviews`
- **Metadata fields:** `source`, `rating`, `date`, `url`, `canonical_tags` (CSV), `features` (CSV), `author`
- **Upsert semantics:** stable review IDs ensure weekly refreshes update existing rows, never duplicate

### 2.6 Theme categorization (the 6 canonical themes)

- **Mechanism:** Done inline by the relevance classifier (single LLM call assigns relevance + canonical tags)
- **Multi-label:** A single review can support multiple Qs (typical: a Q1 review often also supports Q4)
- **Why LLM, not unsupervised clustering:** The 6 questions are pre-defined; we need *deterministic* mapping to those buckets, not emergent clusters. Clustering would be overkill and harder to defend to reviewers.
- **Future sub-themes:** v2 can layer HDBSCAN within each canonical bucket for emergent sub-themes (e.g., within Q1 → "filter bubble fatigue", "regional underexposure", "casual-user starvation").

### 2.7 RAG retrieval

- **File:** `src/rag/retrieve.py`
- **Step 1 - Initial similarity:** Chroma's HNSW cosine search retrieves top-25 (`RAG_RETRIEVE_K`)
- **Step 2 - Optional canonical filter:** When called from `precompute.py` with `filter_canonical=Q1_struggle`, only reviews tagged with that question are considered
- **Step 3 - MMR re-rank:** Greedy Maximal Marginal Relevance with λ=0.7 reduces near-duplicates to a final top-15 (`RAG_TOP_K`)
- **Why MMR:** Without it, the LLM sees 15 reviews that all say roughly the same thing; with it, the LLM sees 15 *diverse* reviews from the same theme → richer synthesis

```mermaid
flowchart LR
    Q[Question] --> EMB[Embed]
    EMB --> SIM[Cosine top-25]
    SIM --> FIL{Canonical filter?}
    FIL -->|yes| FK[Keep matching tag]
    FIL -->|no| FN[Keep all]
    FK --> MMR[MMR re-rank λ=0.7]
    FN --> MMR
    MMR --> OUT[Top-15 diverse reviews]
```

### 2.8 RAG answer generation

- **File:** `src/rag/answer.py`
- **Model:** Groq Llama 3.3 70B Versatile (high-quality synthesis)
- **System prompt strictness:** "Use ONLY the provided reviews as evidence. Do NOT invent data."
- **Output schema (Pydantic):** `answer`, `spotify_features_mentioned`, `user_segments_affected`, `supporting_review_ids`, `confidence` (high/med/low)
- **Confidence rubric (in prompt):**
  - **high:** 8+ reviews directly support, multiple sources/segments agree
  - **medium:** 4-7 reviews support, some divergence
  - **low:** <4 reviews support OR heavy disagreement
- **Fallback:** If LLM returns invalid JSON, we fall back to a "Top relevant reviews retrieved - please read them" stub so the UI never empties

### 2.9 Scope wrapper (the "no-go for off-topic" guardrail)

- **File:** `src/rag/scope.py`
- **Architecture:** Two-stage hybrid

```mermaid
flowchart TD
    Q[User question] --> EMB[Embed question]
    EMB --> CMP[Compute max cosine sim<br/>vs 6 canonical Qs]
    CMP --> DEC{max_sim?}
    DEC -->|>= 0.55| INH[IN-SCOPE high confidence]
    DEC -->|< 0.30| OUTH[OUT-OF-SCOPE high confidence]
    DEC -->|0.30 - 0.55| ESC[Escalate to LLM]
    ESC --> LLM[Groq Llama 3.1 8B<br/>strict scope classifier]
    LLM -->|in_scope=true| INL[IN-SCOPE LLM]
    LLM -->|in_scope=false| OUTL[OUT-OF-SCOPE LLM]
    INH --> RAG[Route to RAG]
    INL --> RAG
    OUTH --> MSG[Friendly refusal]
    OUTL --> MSG
```

- **Why hybrid:** Fast-path decides ~95% of queries with **zero LLM calls** (verified during smoke test: in-scope sim=0.75, out-of-scope sim=0.04). The LLM only escalates on genuinely borderline queries (e.g. "how does Spotify decide what to show me?" - could be discovery, could be UX).
- **Thresholds calibration:** `SCOPE_IN_THRESHOLD = 0.55`, `SCOPE_OUT_THRESHOLD = 0.30` (in `src/config.py`)
- **Out-of-scope copy:** `OUT_OF_SCOPE_MESSAGE` in `scope.py` - friendly, redirects to the 6 questions

### 2.10 Pre-compute layer

- **File:** `src/rag/precompute.py`
- **What:** Computes all 6 canonical answers once per refresh and writes `data/insights/canonical_answers.json`
- **Why pre-compute:** 6 questions × 1 Groq call each = 6 LLM calls per refresh. Free-tier friendly. Dashboard loads them instantly; users never wait for the LLM on first render.
- **Custom questions still hit the live LLM** (rate-limited by Groq tier, but typically <1 request/min per user)

### 2.11 Streamlit dashboard

- **File:** `app/streamlit_app.py`
- **Theme:** Spotify dark (green `#1DB954` on black `#191414`) via inline CSS + `.streamlit/config.toml`
- **5 tabs:**
  1. **6 Canonical Questions** - card grid + expanded view with paginated evidence (5 at a time, "View More")
  2. **Ask Your Own** - scope-wrapped custom question box
  3. **Themes & Segments** - bar charts of feature mentions, canonical distribution, source mix
  4. **Architecture** - text-art diagram (= the 1-slider for the deck)
  5. **Raw Data** - searchable, filterable table; Excel download
- **Excel export:** `pandas.to_excel` with `openpyxl` - two buttons (all reviews / relevant only)
- **Metadata header:** Pills showing last refresh, total normalized, relevant count, Chroma size
- **Caching:** `@st.cache_data(ttl=300)` on data loaders so the UI is snappy

### 2.12 GitHub Actions weekly refresh

- **File:** `.github/workflows/refresh.yml`
- **Trigger:** `cron: "0 2 * * 1"` (Mondays 02:00 UTC) + `workflow_dispatch` (manual button)
- **Steps:**
  1. Checkout
  2. Set up Python 3.11 + pip cache
  3. Install deps
  4. Run `python -m src.pipeline.refresh`
  5. Print `data/metadata.json`
  6. Commit changes under bot identity, push back to main
- **Auto-redeploy:** Streamlit Cloud watches `main`; new commit → redeploy with refreshed data
- **Secrets:** `GROQ_API_KEY` (set in repo settings)

### 2.13 Smoke test

- **File:** `scripts/smoke_test.py`
- **Checks:** Env key, Groq SDK, embeddings, Chroma round-trip, scope wrapper routing, seed loadability
- **Outcome:** Verified end-to-end: all 6 checks pass

---

## 4. Data flow (end-to-end)

```mermaid
sequenceDiagram
    participant U as User browser
    participant ST as Streamlit Cloud
    participant CH as ChromaDB (in repo)
    participant GR as Groq API
    participant GH as GitHub Actions
    participant SP as Spotify reviews (App Store / Play Store)

    Note over GH,SP: Weekly refresh (Mondays 02:00 UTC)
    GH->>SP: scrape 5 + 6 storefronts
    SP-->>GH: ~3k raw reviews
    GH->>GH: normalize + dedupe → reviews.jsonl
    GH->>GR: classify relevance (batched 10/call)
    GR-->>GH: per-review verdicts
    GH->>GH: embed locally (MiniLM)
    GH->>CH: upsert (idempotent by stable ID)
    GH->>GR: 6× canonical answer (RAG)
    GR-->>GH: 6 structured answers
    GH->>GH: write canonical_answers.json + metadata.json
    GH->>GH: git commit + push
    Note over ST: Streamlit Cloud auto-redeploys

    Note over U,ST: User session
    U->>ST: GET /
    ST->>ST: load metadata.json + canonical_answers.json + reviews.jsonl
    ST-->>U: header + 6 cards (instant)
    U->>ST: type custom question
    ST->>ST: scope wrapper (cosine fast-path)
    alt Borderline
        ST->>GR: scope classifier
        GR-->>ST: in/out verdict
    end
    alt In-scope
        ST->>CH: similarity search top-25
        CH-->>ST: top-25 reviews + vectors
        ST->>ST: MMR re-rank → top-15
        ST->>GR: synthesise answer
        GR-->>ST: structured RAG answer
        ST-->>U: answer + paginated 5 reviews
    else Out-of-scope
        ST-->>U: friendly refusal
    end
```

---

## 5. File ↔ functional requirement matrix

| Requirement | Files |
|---|---|
| R1 - Groq as primary LLM | `src/pipeline/groq_client.py`, `src/config.py` |
| R2 - RAG for classification + answering | `src/pipeline/relevance.py`, `src/rag/retrieve.py`, `src/rag/answer.py` |
| R3 - Auto-answer 6 canonical questions | `src/canonical.py`, `src/rag/precompute.py`, `data/insights/canonical_answers.json` |
| R4 - Scope wrapper (out-of-scope refusal) | `src/rag/scope.py` |
| R5 - Per-answer review evidence, 5+View More | `app/streamlit_app.py` (`render_answer_with_reviews`) |
| R6 - Curated seed reviews with transparency | `data/seed/seed_reviews.jsonl`, UI 🌱 badge |
| R7 - GitHub Actions weekly refresh | `.github/workflows/refresh.yml`, `src/pipeline/refresh.py` |
| R8 - Metadata header (counts, dates) | `data/metadata.json`, `app/streamlit_app.py` header |
| R9 - Excel export | `app/streamlit_app.py` `st.download_button` + `openpyxl` |
| R10 - Filter to relevant only, then categorize | `src/pipeline/relevance.py` + canonical tags |
| R11 - Spotify-specific lexicon in prompts | `src/lexicon.py` + injected into every system prompt |

---

## 6. Key design decisions (and their justifications)

| Decision | Alternative considered | Why we chose this |
|---|---|---|
| Two Groq models: 8B (classify) + 70B (synthesise) | 70B for everything | Cost & rate-limit math - classification is per-review (high volume), synthesis is per-question (6 calls). 8B is 10× cheaper. |
| Local sentence-transformers, not Groq/OpenAI embeddings | API embeddings | No rate limit, no quota burn, deterministic across deploys |
| ChromaDB committed to repo | External hosted vector DB | Free-tier-friendly; redeploys are stateless |
| Stable hash IDs | Auto-increment | Idempotent re-scrapes - same review never duplicates |
| Hybrid scope wrapper | LLM-only or cosine-only | 95% queries decided without LLM; LLM only for genuinely borderline (saves quota + latency) |
| Pre-computed canonical answers | Live LLM on every card | Dashboard loads instantly; Groq calls happen once per refresh, not per visitor |
| Curated seed reviews flagged in UI | Hidden / unflagged | Credibility: a reviewer who probes the data finds full transparency |
| Per-tab structure in Streamlit | Single long scroll | Cognitive load - each tab does one job well |
| Multi-locale scraping (US + UK + IN + DE + BR) | US-only | Surfaces regional/multilingual pain points that English-only would miss |

---

## 7. Operating envelope

| Dimension | v1 (now) | v2 (post-deck) |
|---|---|---|
| Reviews indexed | 97 (seed) → ~3k post-scrape | 10k+ with Reddit + Community |
| Refresh cadence | Weekly cron | Daily or on-demand |
| LLM calls per refresh | ~10 (classify) + 6 (synth) = 16 | ~300 + 6 |
| LLM calls per user query | 0 (canonical) / 1 (custom) | Same |
| Vector store size on disk | ~5 MB | ~30 MB |
| Free-tier viability | ✅ Yes, comfortably | ✅ Still within Groq + Streamlit free |

---

## 8. What this engine deliberately does *not* do

- **Does not answer questions about Spotify pricing, podcast bugs, login issues, etc.** - that's what the scope wrapper enforces.
- **Does not invent insights.** Every claim ties to retrieved review IDs.
- **Does not silently inflate the dataset.** Curated seeds are flagged.
- **Does not perform sentiment analysis as a separate stage.** Sentiment is implicit in the rating + canonical tagging; building a separate sentiment classifier added complexity without insight gain.
- **Does not run unsupervised clustering in v1.** Canonical tags cover the brief's 6 questions; clustering is a v2 enhancement.

---

## 9. Where to start reading the code

1. `doc/problemStatement.md` - the *why*
2. `src/canonical.py` - the 6 questions, the contract
3. `src/lexicon.py` - Spotify-domain vocabulary
4. `src/schema.py` - data shapes
5. `src/pipeline/refresh.py` - the orchestrator (read this top-to-bottom to understand the full pipeline)
6. `src/rag/scope.py` + `src/rag/answer.py` - the runtime engine
7. `app/streamlit_app.py` - the UI
8. `.github/workflows/refresh.yml` - the CI loop
