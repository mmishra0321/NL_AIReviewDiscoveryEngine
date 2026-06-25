"""Streamlit dashboard - the deployed Review Discovery Engine UI.

Layout:
- Metadata header (last refresh, counts, Excel download)
- 6 canonical question cards (precomputed answers)
- Expanded view per question with paginated review evidence (5 + View More)
- Custom question box with scope wrapper (in-scope -> live RAG, out -> refusal)
- Themes tab (segments + feature mention frequency)
- Architecture tab (the required 1-slider for the deck)
- Raw data tab (searchable, filterable, downloadable)
"""
from __future__ import annotations

import io
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Make `src` importable regardless of where streamlit was launched from
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from src.canonical import CANONICAL_QUESTIONS, QUESTION_BY_ID
from src.config import METADATA_PATH, RAG_DISPLAY_PAGE, REVIEWS_PATH
from src.lexicon import FEATURES
from src.pipeline.normalize import load_canonical_store
from src.rag.answer import answer_question
from src.rag.precompute import load_canonical_answers
from src.rag.scope import OUT_OF_SCOPE_MESSAGE, evaluate_scope

# Backend service for GitHub Actions history (works in-process; no HTTP hop)
try:
    from backend.github_actions import list_action_runs
except Exception:                                                 # noqa: BLE001
    list_action_runs = None                                       # type: ignore[assignment]

logging.basicConfig(level=logging.INFO)

# ---------------- Page config + theme ----------------

st.set_page_config(
    page_title="Spotify Discovery Pain - AI Review Engine",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SPOTIFY_GREEN = "#1DB954"
SPOTIFY_BLACK = "#191414"
SPOTIFY_GRAY = "#B3B3B3"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {SPOTIFY_BLACK}; color: #FFFFFF; }}
    h1, h2, h3, h4 {{ color: #FFFFFF; }}
    .metric-pill {{
        display: inline-block;
        background: #2A2A2A;
        border: 1px solid #333;
        color: #FFFFFF;
        padding: 6px 14px;
        border-radius: 999px;
        margin-right: 8px;
        margin-bottom: 8px;
        font-size: 13px;
    }}
    .metric-pill strong {{ color: {SPOTIFY_GREEN}; }}
    .qcard {{
        background: #232323;
        border: 1px solid #2F2F2F;
        border-radius: 12px;
        padding: 16px 18px;
        height: 100%;
    }}
    .qcard:hover {{ border-color: {SPOTIFY_GREEN}; }}
    .review-card {{
        background: #1C1C1C;
        border-left: 3px solid {SPOTIFY_GREEN};
        padding: 12px 14px;
        border-radius: 8px;
        margin-bottom: 10px;
        font-size: 14px;
    }}
    .review-meta {{
        color: {SPOTIFY_GRAY};
        font-size: 12px;
        margin-top: 6px;
    }}
    .seed-badge {{
        display: inline-block;
        background: #2D5016;
        color: #B8E994;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        margin-left: 6px;
    }}
    .source-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        margin-right: 6px;
        background: #333;
    }}
    .scope-out {{
        background: #3A1C1C;
        border: 1px solid #6F2D2D;
        color: #FFB4B4;
        padding: 14px;
        border-radius: 8px;
        margin-top: 12px;
    }}
    .answer-block {{
        background: #1E1E1E;
        border-left: 4px solid {SPOTIFY_GREEN};
        padding: 16px 18px;
        border-radius: 6px;
        line-height: 1.55;
        font-size: 15px;
    }}
    .feature-pill {{
        display: inline-block;
        background: #1E3A28;
        color: #B8E994;
        padding: 2px 8px;
        border-radius: 12px;
        margin: 2px 4px 2px 0;
        font-size: 12px;
    }}
    .stTextInput input, .stTextArea textarea {{
        background: #2A2A2A;
        color: #FFFFFF;
        border: 1px solid #444;
    }}
    .stButton button {{
        background: {SPOTIFY_GREEN};
        color: {SPOTIFY_BLACK};
        font-weight: 600;
        border: none;
    }}
    .stButton button:hover {{
        background: #1ED760;
        color: {SPOTIFY_BLACK};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- Data loaders ----------------

@st.cache_data(ttl=300)
def load_metadata() -> dict:
    if not METADATA_PATH.exists():
        return {}
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


@st.cache_data(ttl=300)
def load_reviews_df() -> pd.DataFrame:
    if not REVIEWS_PATH.exists():
        return pd.DataFrame()
    rows = []
    for r in load_canonical_store():
        rows.append({
            "id": r.id,
            "source": r.source,
            "text": r.text,
            "rating": r.rating,
            "author": r.author,
            "date": r.date.isoformat() if r.date else "",
            "locale": r.locale,
            "url": r.url,
            "is_relevant": r.is_relevant,
            "canonical_tags": ",".join(r.canonical_tags),
            "features_mentioned": ",".join(r.features_mentioned or []),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_canon_answers() -> dict:
    return load_canonical_answers()


def reviews_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="reviews", index=False)
    return buf.getvalue()


# ---------------- Helpers ----------------

def format_metadata_pills(meta: dict) -> str:
    last = meta.get("last_refresh_utc")
    if last:
        try:
            last_human = datetime.fromisoformat(last.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
        except Exception:                                            # noqa: BLE001
            last_human = last
    else:
        last_human = "never"
    return (
        f'<div class="metric-pill">Last refresh: <strong>{last_human}</strong></div>'
        f'<div class="metric-pill">Reviews collected: <strong>{meta.get("total_normalized", 0):,}</strong></div>'
        f'<div class="metric-pill">Discovery-relevant: <strong>{meta.get("total_relevant", 0):,}</strong></div>'
        f'<div class="metric-pill">In vector index: <strong>{meta.get("chroma_collection_size", 0):,}</strong></div>'
    )


def render_review(rid: str, df: pd.DataFrame) -> None:
    row = df[df["id"] == rid]
    if row.empty:
        return
    r = row.iloc[0]
    seed_badge = '<span class="seed-badge">🌱 curated seed</span>' if r["source"] == "curated_seed" else ""
    rating = f"{'⭐' * int(r['rating'])}" if r["rating"] and r["rating"] > 0 else ""
    url = r.get("url") or ""
    url_link = f'<a href="{url}" target="_blank" style="color:#888;text-decoration:none;">↗ source</a>' if url else ""
    st.markdown(
        f"""<div class="review-card">
            <div>{r['text']}</div>
            <div class="review-meta">
                <span class="source-badge">{r['source']}</span>
                {rating} · {r['locale'] or ''} · {(r['date'] or '')[:10]} {seed_badge} · {url_link}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_answer_with_reviews(answer_text: str, features: list[str], segments: list[str],
                               confidence: str, review_ids: list[str], df: pd.DataFrame,
                               state_key: str) -> None:
    st.markdown(f'<div class="answer-block">{answer_text}</div>', unsafe_allow_html=True)

    if features:
        st.markdown(
            "**Spotify features mentioned:** "
            + " ".join(f'<span class="feature-pill">{f}</span>' for f in features),
            unsafe_allow_html=True,
        )
    if segments:
        st.markdown(
            "**User segments affected:** "
            + " ".join(f'<span class="feature-pill">{s}</span>' for s in segments),
            unsafe_allow_html=True,
        )
    st.caption(f"Confidence: **{confidence}** · {len(review_ids)} reviews retrieved")

    st.markdown("---")
    st.markdown("##### Supporting reviews")

    page_key = f"{state_key}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    shown = st.session_state[page_key] * RAG_DISPLAY_PAGE
    visible = review_ids[:shown]

    for rid in visible:
        render_review(rid, df)

    remaining = len(review_ids) - shown
    if remaining > 0:
        if st.button(f"View {min(RAG_DISPLAY_PAGE, remaining)} more", key=f"more_{state_key}"):
            st.session_state[page_key] += 1
            st.rerun()
    elif len(review_ids) > RAG_DISPLAY_PAGE:
        st.caption("All supporting reviews shown.")


# ---------------- Header ----------------

st.markdown(
    f"""
    <h1 style="color:{SPOTIFY_GREEN};margin-bottom:0;">🎧 Spotify Discovery Pain</h1>
    <p style="color:{SPOTIFY_GRAY};margin-top:4px;">
        AI-powered review discovery engine. What real users say about Spotify's recommendations.
    </p>
    """,
    unsafe_allow_html=True,
)

meta = load_metadata()
df_reviews = load_reviews_df()
canon = load_canon_answers()

st.markdown(format_metadata_pills(meta), unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 4])
with c1:
    if not df_reviews.empty:
        st.download_button(
            label="⬇ Download all (Excel)",
            data=reviews_to_excel_bytes(df_reviews),
            file_name=f"spotify_reviews_{datetime.utcnow().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
with c2:
    if not df_reviews.empty:
        st.download_button(
            label="⬇ Relevant only (Excel)",
            data=reviews_to_excel_bytes(df_reviews[df_reviews["is_relevant"] == True]),
            file_name=f"spotify_reviews_relevant_{datetime.utcnow().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.markdown("---")

# ---------------- GitHub Actions history ----------------

@st.cache_data(ttl=300)
def load_action_runs() -> dict:
    if list_action_runs is None:
        return {"runs": [], "actions_tab_url": None}
    try:
        return list_action_runs(limit=10)
    except Exception as exc:                                      # noqa: BLE001
        return {"runs": [], "actions_tab_url": None, "error": str(exc)}


def _status_pill(status: str) -> str:
    palette = {
        "success":       ("#0d4a26", "#1DB954"),
        "failure":       ("#3A1C1C", "#FFB4B4"),
        "cancelled":     ("#2A2A2A", "#B3B3B3"),
        "skipped":       ("#2A2A2A", "#B3B3B3"),
        "pending":       ("#4A3A0D", "#FFD180"),
        "no_action_yet": ("#1C2A3A", "#90C8FF"),
    }
    bg, fg = palette.get(status, ("#2A2A2A", "#B3B3B3"))
    label = {"no_action_yet": "initial commit", "failure": "failed", "pending": "running"}.get(status, status)
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-size:11px;font-weight:600;">{label}</span>'
    )


def _relative(iso: str | None) -> str:
    if not iso:
        return "unknown"
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:                                             # noqa: BLE001
        return iso
    diff = (datetime.now(t.tzinfo) - t).total_seconds()
    if diff < 60:   return f"{int(diff)}s ago"
    if diff < 3600: return f"{int(diff // 60)}m ago"
    if diff < 86400: return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


actions = load_action_runs()
st.markdown("### 🔁 Weekly refresh history")
st.caption(
    "GitHub Actions run every Monday at 02:00 UTC. Each successful run commits "
    "fresh data to the repo. Download the exact snapshot from any past run below."
)

if actions.get("error"):
    st.warning(f"Could not fetch run history: {actions['error']}")

runs = actions.get("runs", [])
if not runs:
    st.info(
        "No runs found yet. After the first GitHub Action runs, completed snapshots "
        "will appear here."
    )
else:
    show_all = st.checkbox(
        f"Show all {len(runs)} runs", value=False, key="show_all_runs",
    ) if len(runs) > 1 else True
    visible = runs if show_all else runs[:1]

    for r in visible:
        pill = _status_pill(r.get("status", "pending"))
        title = r.get("title", "refresh")
        when = _relative(r.get("started_at"))
        utc = (r.get("started_at") or "").replace("T", " ").replace("Z", "")
        sha = (r.get("output_sha") or "")[:7]
        run_link = (
            f'<a href="{r["html_url"]}" target="_blank" '
            f'style="color:#9CA3AF;font-size:12px;text-decoration:none;">↗ view run</a>'
            if r.get("html_url") else ""
        )
        st.markdown(
            f"""<div style="border:1px solid #2F2F2F;border-radius:10px;
                            background:#1C1C1C;padding:12px 14px;margin-bottom:8px;">
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    {pill}
                    <span style="font-weight:600;color:#FFFFFF;">{title}</span>
                    <span style="color:#9CA3AF;font-size:12px;">{when}</span>
                    <span style="color:#6B7280;font-size:12px;">{utc}</span>
                    <span style="font-family:monospace;color:#6B7280;font-size:11px;">#{sha}</span>
                    <span style="margin-left:auto;">{run_link}</span>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        dl = r.get("downloads") or {}
        if dl:
            cols = st.columns(4)
            for col, (key, label) in zip(cols, [
                ("reviews_jsonl",     "📄 reviews.jsonl"),
                ("metadata",          "🧾 metadata.json"),
                ("canonical_answers", "🧠 canonical answers"),
                ("seed_reviews",      "🌱 seed reviews"),
            ]):
                url = dl.get(key)
                if url:
                    col.markdown(
                        f'<a href="{url}" target="_blank" download '
                        f'style="display:inline-block;background:#1DB954;color:#000;'
                        f'padding:6px 12px;border-radius:6px;font-weight:600;'
                        f'font-size:12px;text-decoration:none;width:100%;text-align:center;">'
                        f'⬇ {label}</a>',
                        unsafe_allow_html=True,
                    )

    if actions.get("actions_tab_url"):
        st.caption(
            f"[View all runs on GitHub →]({actions['actions_tab_url']})"
        )

st.markdown("---")

# ---------------- Tabs ----------------

tab_questions, tab_custom, tab_themes, tab_arch, tab_raw = st.tabs(
    ["🧠 6 Canonical Questions", "💬 Ask Your Own", "🎯 Themes & Segments",
     "🏗 Architecture", "📋 Raw Data"]
)

# ---- Tab: Canonical Questions ----
with tab_questions:
    st.subheader("Answers grounded in real user reviews (RAG)")
    st.caption("Each answer is pre-computed at refresh time and cites supporting review evidence.")

    answers = canon.get("answers", {})

    # Card grid - 2 columns of 3
    cols = st.columns(3)
    for idx, q in enumerate(CANONICAL_QUESTIONS):
        a = answers.get(q.id)
        with cols[idx % 3]:
            with st.container(border=False):
                st.markdown(
                    f"""<div class="qcard">
                        <h4 style="color:{SPOTIFY_GREEN};margin:0 0 8px 0;">Q{idx+1}</h4>
                        <p style="margin:0 0 8px 0;font-weight:600;">{q.short}</p>
                        <p style="color:{SPOTIFY_GRAY};font-size:13px;">{q.full}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if a is None:
                    st.warning("Not yet computed (run refresh).")

    st.markdown("---")
    chosen_label = st.selectbox(
        "Expand a question:",
        [f"Q{i+1}: {q.short}" for i, q in enumerate(CANONICAL_QUESTIONS)],
        index=0,
    )
    chosen_id = CANONICAL_QUESTIONS[int(chosen_label.split(":")[0][1:]) - 1].id
    a = answers.get(chosen_id)
    if not a:
        st.info("No precomputed answer yet. Run `python -m src.pipeline.refresh` first.")
    else:
        st.markdown(f"### {a['question_full']}")
        render_answer_with_reviews(
            answer_text=a["answer"],
            features=a.get("spotify_features_mentioned", []),
            segments=a.get("user_segments_affected", []),
            confidence=a.get("confidence", "medium"),
            review_ids=a.get("review_ids", []),
            df=df_reviews,
            state_key=f"canon_{chosen_id}",
        )

# ---- Tab: Custom Question ----
with tab_custom:
    st.subheader("Ask any question - scope-wrapped")
    st.caption(
        "If your question is similar to one of the 6 canonical questions, the engine "
        "answers it with retrieved review evidence. Otherwise it returns an out-of-scope message."
    )
    user_q = st.text_input(
        "Your question",
        placeholder="e.g. Why do casual listeners get worse recommendations over time?",
    )

    if user_q:
        with st.spinner("Checking scope..."):
            scope = evaluate_scope(user_q)

        st.caption(
            f"Scope decision: **{'in-scope' if scope.in_scope else 'out-of-scope'}** "
            f"· similarity={scope.max_similarity:.2f} · nearest={scope.nearest_canonical_id} "
            f"· path={scope.confidence}"
        )

        if not scope.in_scope:
            st.markdown(f'<div class="scope-out">{OUT_OF_SCOPE_MESSAGE}</div>',
                        unsafe_allow_html=True)
        else:
            with st.spinner("Retrieving evidence and synthesising..."):
                ans = answer_question(user_q)
            if ans is None:
                st.error("Could not generate an answer. The vector index may be empty.")
            else:
                render_answer_with_reviews(
                    answer_text=ans.answer.answer,
                    features=ans.answer.spotify_features_mentioned,
                    segments=ans.answer.user_segments_affected,
                    confidence=ans.answer.confidence,
                    review_ids=[r.id for r in ans.reviews],
                    df=df_reviews,
                    state_key=f"custom_{hash(user_q) % 100000}",
                )

# ---- Tab: Themes & Segments ----
with tab_themes:
    st.subheader("Spotify feature mention frequency")
    st.caption("Across all discovery-relevant reviews. Higher count = more user pain attached to that feature.")
    feat_counts = meta.get("feature_mention_counts", {})
    if feat_counts:
        feat_df = pd.DataFrame(
            [{"feature": k, "mentions": v} for k, v in feat_counts.items()]
        ).sort_values("mentions", ascending=True)
        st.bar_chart(feat_df.set_index("feature"))
    else:
        st.info("No feature mention data yet. Run refresh first.")

    st.markdown("---")
    st.subheader("Distribution across the 6 canonical themes")
    by_canon = meta.get("by_canonical_tag", {})
    if by_canon:
        bcdf = pd.DataFrame([
            {"question": QUESTION_BY_ID[k].short if k in QUESTION_BY_ID else k, "count": v}
            for k, v in by_canon.items()
        ])
        st.bar_chart(bcdf.set_index("question"))

    st.markdown("---")
    st.subheader("Source mix")
    by_src = meta.get("by_source", {})
    if by_src:
        st.dataframe(
            pd.DataFrame([{"source": k, "count": v} for k, v in by_src.items()]),
            use_container_width=True,
            hide_index=True,
        )

# ---- Tab: Architecture ----
with tab_arch:
    st.subheader("How this engine works")
    st.caption("This diagram doubles as the required 1-slider inside the project deck.")
    st.code(
        """\
+-------------------- WEEKLY GITHUB ACTIONS (cron) ---------------------+
|                                                                       |
|  Scrapers (App Store / Play Store / Reddit / Community + Seed)        |
|         |                                                             |
|         v                                                             |
|  Normalize -> Dedupe (hash)                                           |
|         |                                                             |
|         v                                                             |
|  Relevance Filter (Groq Llama 3.1 8B Instant)                         |
|     - drops bug/billing/login noise                                   |
|     - tags each kept review with which of the 6 Qs it supports        |
|         |                                                             |
|         v                                                             |
|  Local embeddings (sentence-transformers MiniLM)                      |
|         |                                                             |
|         v                                                             |
|  Upsert into ChromaDB (persistent, committed in repo)                 |
|         |                                                             |
|         v                                                             |
|  Pre-compute answers for the 6 canonical questions                    |
|  (RAG: vector retrieval -> MMR re-rank -> Groq Llama 3.3 70B)         |
|         |                                                             |
|         v                                                             |
|  Write metadata.json -> git commit -> Streamlit Cloud redeploys       |
+-----------------------------------------------------------------------+
              |
              v
+--------------------------- STREAMLIT APP -----------------------------+
|  Header metadata (last refresh, counts, Excel export)                 |
|  6 canonical question cards (precomputed answers + cited evidence)    |
|  Custom question box                                                  |
|     -> Scope wrapper (cosine fast-path + Groq LLM borderline fallback)|
|     -> If in-scope: live RAG retrieval + synthesis                    |
|     -> If out-of-scope: friendly refusal message                      |
|  Themes / segments dashboard                                          |
+-----------------------------------------------------------------------+
""",
        language="text",
    )

    st.markdown("---")
    st.subheader("Why this is RAG, not just LLM-in-a-box")
    st.markdown(
        f"""
- **Grounded:** every answer cites the specific reviews it drew from.
  Click into any answer and read the verbatim user voice.
- **Refreshable:** the Chroma index is upserted weekly by GitHub Actions -
  new reviews automatically shift answers.
- **Bounded:** the scope wrapper prevents the LLM from inventing answers
  to questions this dataset can't support.
- **Spotify-literate:** feature lexicon ({len(FEATURES)} canonical features)
  is baked into prompts so reviews mentioning *DJ*, *Daylist*, *Smart Shuffle*
  are interpreted correctly.
        """
    )

# ---- Tab: Raw Data ----
with tab_raw:
    st.subheader(f"Raw reviews - {len(df_reviews):,} rows")
    if df_reviews.empty:
        st.info("No data yet. Run `python -m src.pipeline.refresh` first.")
    else:
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            src_filter = st.multiselect(
                "Source",
                sorted(df_reviews["source"].unique().tolist()),
                default=sorted(df_reviews["source"].unique().tolist()),
            )
        with col_b:
            relevance_filter = st.selectbox(
                "Relevance", ["All", "Relevant only", "Irrelevant only"], index=1
            )
        with col_c:
            search = st.text_input("Text search", "")

        filtered = df_reviews[df_reviews["source"].isin(src_filter)]
        if relevance_filter == "Relevant only":
            filtered = filtered[filtered["is_relevant"] == True]
        elif relevance_filter == "Irrelevant only":
            filtered = filtered[filtered["is_relevant"] == False]
        if search:
            filtered = filtered[filtered["text"].str.contains(search, case=False, na=False)]

        st.caption(f"{len(filtered):,} rows match")
        st.dataframe(
            filtered[["source", "rating", "text", "canonical_tags",
                     "features_mentioned", "locale", "date"]],
            use_container_width=True,
            height=500,
        )
