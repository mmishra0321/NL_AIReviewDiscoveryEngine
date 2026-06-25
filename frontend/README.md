# Frontend - Spotify Discovery Review Engine

React + Vite + TypeScript + Tailwind UI for the AI Review Discovery Engine.

## Local dev (two-terminal setup)

**Terminal 1 - backend (port 8000):**

```bash
cd ..                                # back to 01-ai-review-engine/
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 - frontend (port 5173):**

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api/*` to the FastAPI backend, so no CORS/env config is needed locally.

## What you can do in the UI

- **Metadata bar** - last refresh, total normalized (capped at 1000), discovery-relevant count + %, Chroma index size, per-source breakdown chips, per-canonical-tag counts
- **Excel export** - one-click multi-sheet workbook (canonical Q&A, all reviews, themes, metadata)
- **Reload** - drops backend in-memory caches without restarting (picks up a fresh refresh)
- **6 canonical question cards** - click to expand the precomputed RAG synthesis + supporting reviews
- **Supporting reviews** - paginated 5-at-a-time with "View N more"
- **Ask a custom question** - scope wrapper (fast cosine + LLM fallback) routes in-scope questions through live RAG; out-of-scope questions are gracefully refused

## Folder layout

```
frontend/
├─ src/
│  ├─ components/
│  │  ├─ ui/              # Button, Card, Badge, Input, Skeleton
│  │  ├─ MetadataBar.tsx
│  │  ├─ CanonicalGrid.tsx
│  │  ├─ AnswerPanel.tsx
│  │  ├─ ReviewList.tsx
│  │  └─ AskBox.tsx
│  ├─ lib/
│  │  ├─ api.ts           # typed fetch client
│  │  ├─ types.ts         # mirrors backend Pydantic shapes
│  │  └─ utils.ts         # cn(), formatters, color maps
│  ├─ App.tsx
│  ├─ main.tsx
│  └─ index.css           # Tailwind + Spotify palette
├─ tailwind.config.js
├─ postcss.config.js
├─ vite.config.ts         # /api proxy → :8000
└─ tsconfig.app.json
```

## Production build

```bash
npm run build              # outputs /dist
npm run preview            # local preview of /dist
```

For deployment, set `VITE_API_BASE` to the deployed backend URL (e.g. `https://your-engine.onrender.com`) before `npm run build`.

## Why no shadcn CLI

We use the same patterns (Radix-style headless behavior, Tailwind class composition, `cn` helper) but the components live directly in `src/components/ui/`. This avoids the interactive shadcn CLI and keeps the dependency list minimal.
