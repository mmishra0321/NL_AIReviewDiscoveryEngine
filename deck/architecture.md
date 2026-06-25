# Review Engine Architecture (the required 1-slider)

```mermaid
flowchart TD
    subgraph CI["⏱ Weekly GitHub Actions (cron)"]
        direction TB
        S1[Scrapers<br/>App Store · Play Store · Reddit · Community]
        S2[Curated Seed Reviews 🌱]
        N[Normalize + Dedupe by hash]
        S1 --> N
        S2 --> N
        R[Discovery Relevance Filter<br/>Groq Llama 3.1 8B Instant<br/>Drops bugs / login / billing noise]
        N --> R
        T["Tag with which of the 6 Qs each review supports<br/>(Q1-Q6, multi-label)"]
        R --> T
        E[Local Embeddings<br/>sentence-transformers MiniLM]
        T --> E
        C[(ChromaDB<br/>persistent + committed)]
        E --> C
        P[Pre-compute 6 Canonical Answers<br/>RAG: Retrieve → MMR → Groq Llama 3.3 70B]
        C --> P
        M[Write metadata.json + git commit + push]
        P --> M
    end

    M -.->|auto redeploy| ST

    subgraph ST["🖥 Streamlit Cloud (deployed dashboard)"]
        direction TB
        H[Metadata Header<br/>last refresh · counts · Excel export]
        Q6["6 Canonical Question Cards<br/>(precomputed, instant)"]
        CQ[Custom Question Box]
        SW{Scope Wrapper<br/>cosine fast-path +<br/>Groq LLM borderline fallback}
        RAG[Live RAG<br/>Chroma retrieval → MMR → Groq synthesis]
        OOS[Out-of-Scope refusal]
        REV[Paginated review evidence<br/>5 at a time, View More]

        H --- Q6 --- CQ
        CQ --> SW
        SW -->|in-scope| RAG
        SW -->|out-of-scope| OOS
        RAG --> REV
        Q6 --> REV
    end

    style CI fill:#191414,stroke:#1DB954,color:#fff
    style ST fill:#191414,stroke:#1DB954,color:#fff
    style C fill:#1DB954,stroke:#fff,color:#191414
    style SW fill:#2D5016,stroke:#1DB954,color:#fff
    style RAG fill:#2D5016,stroke:#1DB954,color:#fff
```

## Key design decisions

| Decision | Why |
|---|---|
| **Groq Llama 3.3 70B** for synthesis, Llama 3.1 8B for classification | Free, fast, large enough; 8B handles high-volume batch classification cheaply, 70B handles low-volume synthesis quality |
| **Local sentence-transformers** for embeddings | No API quota, no rate limits, deterministic |
| **ChromaDB persisted in repo** | Free deployment, no external vector DB needed, redeploys are zero-friction |
| **Pre-computed canonical answers** | Instant load on the dashboard; LLM only runs at refresh time (1 per question) |
| **Live RAG for custom questions** | Flexible, but rate-limited by scope wrapper so we don't blow the Groq quota |
| **Hybrid scope wrapper** | Cosine fast-path decides 95% of queries; LLM only escalates on borderline |
| **Curated seed reviews flagged 🌱** | Transparently supplements scraped data without compromising credibility |
