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
    page_title="Spotify Discovery Pain · AI Review Engine",
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
    /* ============================================================
       React-parity theme. Mirrors the Tailwind tokens used in the
       local dev React UI (frontend/src/index.css + tailwind.config).
       ============================================================ */
    .stApp {{ background-color: #0a0a0a; color: #ffffff; }}
    .block-container {{ padding-top: 1.5rem !important; max-width: 1280px !important; }}
    h1, h2, h3, h4, h5, h6 {{ color: #ffffff; letter-spacing: -0.01em; }}
    a {{ color: #b3b3b3; text-decoration: none; }}
    a:hover {{ color: #ffffff; }}

    /* ----- Header ----- */
    .app-header {{
        display: flex; align-items: center; gap: 12px;
        padding: 4px 0 12px 0;
        border-bottom: 1px solid #2a2a2a;
        margin-bottom: 24px;
    }}
    .logo-box {{
        width: 32px; height: 32px; border-radius: 8px;
        background: rgba(29,185,84,0.15);
        border: 1px solid rgba(29,185,84,0.30);
        display: inline-flex; align-items: center; justify-content: center;
        color: {SPOTIFY_GREEN}; font-size: 16px;
    }}
    .brand-block {{ display: flex; flex-direction: column; line-height: 1.15; }}
    .brand-text {{ font-size: 14px; font-weight: 600; color: #fff; }}
    .brand-sub  {{ font-size: 11px; color: #6b7280; }}
    .header-right {{ margin-left: auto; display: flex; gap: 14px; }}
    .header-right a {{ font-size: 12px; color: #b3b3b3; }}

    /* ----- Hero card ----- */
    .hero {{
        border-radius: 16px;
        border: 1px solid #2a2a2a;
        background: linear-gradient(135deg, #141414 0%, #141414 50%, #1a1a1a 100%);
        padding: 28px 28px;
        margin-bottom: 28px;
    }}
    .kicker {{
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.10em;
        color: {SPOTIFY_GREEN}; font-weight: 600;
    }}
    .hero h1 {{
        font-size: 26px; font-weight: 700; margin: 6px 0 10px 0;
        color: #fff; line-height: 1.22; max-width: 760px;
    }}
    .hero p {{
        font-size: 14px; color: #b3b3b3; line-height: 1.65; margin: 0; max-width: 760px;
    }}

    /* ----- Stat tile ----- */
    .stat-tile {{
        border-radius: 10px;
        border: 1px solid #2a2a2a;
        background: #141414;
        padding: 10px 14px;
        height: 100%;
    }}
    .stat-label {{
        font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.08em;
        color: #6b7280; font-weight: 500; display: flex; align-items: center; gap: 5px;
    }}
    .stat-value {{ font-size: 17px; font-weight: 700; color: #fff; margin-top: 3px; }}
    .stat-sub   {{ font-size: 11px; color: #6b7280; margin-top: 1px;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

    /* ----- Source pills ----- */
    .src-pill {{
        display: inline-flex; align-items: center; gap: 5px;
        padding: 2px 8px; margin: 2px 3px 2px 0;
        border-radius: 6px; font-size: 11.5px;
        border: 1px solid;
    }}
    .src-app_store    {{ background: rgba(59,130,246,.15); color: #93c5fd; border-color: rgba(59,130,246,.3); }}
    .src-play_store   {{ background: rgba(16,185,129,.15); color: #6ee7b7; border-color: rgba(16,185,129,.3); }}
    .src-youtube      {{ background: rgba(239,68,68,.15);  color: #fca5a5; border-color: rgba(239,68,68,.3); }}
    .src-reddit       {{ background: rgba(249,115,22,.15); color: #fdba74; border-color: rgba(249,115,22,.3); }}
    .src-trustpilot   {{ background: rgba(20,184,166,.15); color: #5eead4; border-color: rgba(20,184,166,.3); }}
    .src-curated_seed {{ background: rgba(168,85,247,.15); color: #d8b4fe; border-color: rgba(168,85,247,.3); }}
    .src-default      {{ background: #1a1a1a; color: #b3b3b3; border-color: #2a2a2a; }}

    /* ----- Tagged pills ----- */
    .tag-pill {{
        display: inline-block; padding: 2px 8px; margin: 2px 3px 2px 0;
        background: rgba(59,130,246,.15); color: #93c5fd;
        border: 1px solid rgba(59,130,246,.3);
        border-radius: 6px; font-size: 11.5px;
    }}
    .meta-label {{ color: #6b7280; font-size: 12px; padding-right: 6px; }}

    /* ----- Section header (kicker + title + subtitle) ----- */
    .section-head {{ margin: 12px 0 10px 0; }}
    .section-head h2 {{ font-size: 18px; font-weight: 600; color: #fff;
                       margin: 2px 0 2px 0; letter-spacing: -0.01em; }}
    .section-head p  {{ font-size: 13px; color: #b3b3b3; margin: 0; }}

    /* ----- Canonical question card ----- */
    .qcard {{
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 12px;
        padding: 14px 16px;
        height: 100%;
        transition: border-color .15s ease, background .15s ease;
    }}
    .qcard:hover {{ border-color: {SPOTIFY_GREEN}; }}
    .qcard-selected {{
        background: #18221c !important;
        border-color: {SPOTIFY_GREEN} !important;
        box-shadow: 0 0 0 1px rgba(29,185,84,0.35);
    }}
    .qcard .qid {{
        font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.08em;
        color: #6b7280; font-weight: 500;
    }}
    .qcard .qshort {{ font-size: 14.5px; font-weight: 600; color: #fff; margin: 4px 0 6px 0; }}
    .qcard .qfull  {{ font-size: 12.5px; color: #b3b3b3; line-height: 1.45; }}

    /* ----- GitHub Action run row ----- */
    .run-row {{
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        background: rgba(26,26,26,.4);
        padding: 12px 14px; margin-bottom: 10px;
    }}
    .run-row.primary {{ border-color: rgba(29,185,84,0.40); }}
    .run-line {{ display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }}
    .run-title {{ font-weight: 600; color: #fff; font-size: 14px; }}
    .run-meta  {{ color: #6b7280; font-size: 12px; }}
    .run-sha   {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #6b7280; font-size: 11px; }}
    .status-badge {{
        display: inline-flex; align-items: center; gap: 4px;
        padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;
        border: 1px solid;
    }}
    .status-success       {{ background: rgba(29,185,84,.15);  color: {SPOTIFY_GREEN}; border-color: rgba(29,185,84,.4); }}
    .status-failure       {{ background: rgba(239,68,68,.15);  color: #fca5a5;        border-color: rgba(239,68,68,.3); }}
    .status-pending       {{ background: rgba(245,158,11,.15); color: #fcd34d;        border-color: rgba(245,158,11,.3); }}
    .status-cancelled,
    .status-skipped       {{ background: #1a1a1a;              color: #b3b3b3;        border-color: #2a2a2a; }}
    .status-no_action_yet {{ background: rgba(59,130,246,.15); color: #93c5fd;        border-color: rgba(59,130,246,.3); }}
    .dl-btn {{
        display: inline-flex; align-items: center; gap: 5px;
        padding: 5px 10px; border-radius: 6px;
        background: rgba(255,255,255,.04); color: #d1d5db;
        border: 1px solid #2a2a2a;
        font-size: 11.5px; text-decoration: none;
        margin: 4px 6px 0 0;
    }}
    .dl-btn:hover {{ background: rgba(29,185,84,.10); color: #fff; border-color: rgba(29,185,84,.4); }}

    /* ----- Review card (in answer panels) ----- */
    .review-card {{
        background: rgba(26,26,26,.5);
        border: 1px solid #2a2a2a;
        border-left: 3px solid {SPOTIFY_GREEN};
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
        font-size: 13.5px; line-height: 1.55;
    }}
    .review-meta {{ color: #6b7280; font-size: 11.5px; margin-top: 6px; }}
    .seed-badge {{
        display: inline-block; background: rgba(168,85,247,.15); color: #d8b4fe;
        border: 1px solid rgba(168,85,247,.3);
        padding: 1px 7px; border-radius: 4px; font-size: 10.5px; margin-left: 6px;
    }}
    .source-badge {{
        display: inline-block; padding: 1px 7px; border-radius: 4px;
        font-size: 10.5px; margin-right: 6px; background: #2a2a2a; color: #d1d5db;
    }}

    /* ----- Answer block ----- */
    .answer-block {{
        background: linear-gradient(135deg, rgba(29,185,84,.05), transparent);
        border: 1px solid rgba(29,185,84,.30);
        padding: 16px 18px;
        border-radius: 10px;
        line-height: 1.6;
        font-size: 14.5px; color: rgba(255,255,255,.95);
        white-space: pre-wrap;
    }}
    .feature-pill {{
        display: inline-block; background: rgba(29,185,84,.15); color: #6ee7b7;
        border: 1px solid rgba(29,185,84,.3);
        padding: 2px 8px; border-radius: 6px; margin: 2px 4px 2px 0;
        font-size: 11.5px;
    }}
    .scope-out {{
        background: rgba(245,158,11,.07);
        border: 1px solid rgba(245,158,11,.30);
        color: #fcd34d;
        padding: 14px 16px; border-radius: 10px; margin-top: 12px;
    }}

    /* ----- Streamlit native widget restyling ----- */
    .stTextInput input, .stTextArea textarea {{
        background: #141414;
        color: #ffffff;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {SPOTIFY_GREEN};
        box-shadow: 0 0 0 2px rgba(29,185,84,.20);
    }}
    .stSelectbox > div > div {{ background: #141414; border-color: #2a2a2a; }}
    .stMultiSelect > div > div {{ background: #141414; border-color: #2a2a2a; }}
    /* Default (secondary) button -> outlined; primary -> Spotify green */
    .stButton > button {{
        background: #141414;
        color: #d1d5db;
        font-weight: 500;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        transition: all .15s ease;
    }}
    .stButton > button:hover:not(:disabled) {{
        background: rgba(29,185,84,.10);
        color: #fff;
        border-color: rgba(29,185,84,.4);
    }}
    .stButton > button[kind="primary"] {{
        background: {SPOTIFY_GREEN};
        color: #0a0a0a;
        font-weight: 600;
        border-color: {SPOTIFY_GREEN};
    }}
    .stButton > button[kind="primary"]:hover {{
        background: #1ED760;
        color: #0a0a0a;
        border-color: #1ED760;
    }}
    .stDownloadButton > button {{
        background: {SPOTIFY_GREEN};
        color: #0a0a0a;
        font-weight: 600;
        border: 1px solid {SPOTIFY_GREEN};
        border-radius: 8px;
    }}
    .stDownloadButton > button:hover {{ background: #1ED760; border-color: #1ED760; color: #0a0a0a; }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid #2a2a2a; }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent; color: #b3b3b3; font-size: 13px;
        padding: 8px 12px; border-radius: 8px 8px 0 0;
    }}
    .stTabs [aria-selected="true"] {{
        color: {SPOTIFY_GREEN} !important;
        border-bottom: 2px solid {SPOTIFY_GREEN};
    }}

    /* Code block (architecture diagram) */
    .stCode {{ background: #0f0f0f !important; border: 1px solid #2a2a2a; border-radius: 10px; }}

    /* Footer */
    .app-footer {{
        margin-top: 36px; padding: 18px 0;
        border-top: 1px solid #2a2a2a;
        color: #6b7280; font-size: 11.5px;
        display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px;
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

def _relative(iso: str | None) -> str:
    if not iso:
        return "unknown"
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:                                                 # noqa: BLE001
        return iso
    diff = (datetime.now(t.tzinfo) - t).total_seconds()
    if diff < 60:   return f"{int(diff)}s ago"
    if diff < 3600: return f"{int(diff // 60)}m ago"
    if diff < 86400: return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


def _format_utc(iso: str | None) -> str:
    if not iso:
        return "never"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%a, %d %b %Y %H:%M UTC")
    except Exception:                                                 # noqa: BLE001
        return iso


def _source_label(s: str) -> str:
    return {
        "app_store": "App Store", "play_store": "Play Store", "youtube": "YouTube",
        "reddit": "Reddit", "trustpilot": "Trustpilot", "community": "Community",
        "curated_seed": "Seed",
    }.get(s, s)


def _source_class(s: str) -> str:
    known = {"app_store", "play_store", "youtube", "reddit", "trustpilot", "curated_seed"}
    return f"src-{s}" if s in known else "src-default"


def stat_tile_html(icon: str, label: str, value: str, sub: str | None = None) -> str:
    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="stat-tile">'
        f'  <div class="stat-label">{icon}{label}</div>'
        f'  <div class="stat-value">{value}</div>'
        f'  {sub_html}'
        f'</div>'
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="app-header">
            <div class="logo-box">♪</div>
            <div class="brand-block">
                <div class="brand-text">Spotify Discovery · AI Review Engine</div>
                <div class="brand-sub">RAG over App Store · Play Store · YouTube</div>
            </div>
            <div class="header-right">
                <a href="https://github.com/mmishra0321/NL_AIReviewDiscoveryEngine" target="_blank">↗ repo</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="kicker">PM CAPSTONE · SPOTIFY GROWTH</div>
            <h1>Why meaningful music discovery still fails at scale, in users' own words.</h1>
            <p>This engine scrapes, normalizes, classifies, embeds, and RAG-synthesizes thousands of
            real reviews to answer six canonical PM questions about discovery, recommendations, and
            repetitive listening. Every answer cites the exact reviews that support it.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_head(kicker: str, title: str, subtitle: str | None = None) -> None:
    sub_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="section-head">
            <div class="kicker">{kicker}</div>
            <h2>{title}</h2>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_review(rid: str, df: pd.DataFrame) -> None:
    row = df[df["id"] == rid]
    if row.empty:
        return
    r = row.iloc[0]
    src = r["source"]
    src_html = f'<span class="src-pill {_source_class(src)}">{_source_label(src)}</span>'
    rating = f"{'⭐' * int(r['rating'])}" if r["rating"] and r["rating"] > 0 else ""
    url = r.get("url") or ""
    url_link = (
        f'<a href="{url}" target="_blank" style="color:#9ca3af;">↗</a>'
        if url else ""
    )
    locale = r["locale"] or ""
    date = (r["date"] or "")[:10]
    st.markdown(
        f"""<div class="review-card">
            <div style="margin-bottom:6px;">{src_html} {rating}
                <span style="color:#9ca3af;font-size:11.5px;margin-left:4px;">
                    {locale}{' · ' if locale and date else ''}{date}
                </span>
                <span style="float:right;">{url_link}</span>
            </div>
            <div style="color:rgba(255,255,255,.92);">{r['text']}</div>
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


# ---------------- Page render ----------------

render_header()
render_hero()

meta = load_metadata()
df_reviews = load_reviews_df()
canon = load_canon_answers()

# --- Stat tiles row ---
scrape_counts = meta.get("scrape_counts_this_run") or {}
scraped_this_run = sum(scrape_counts.values()) if scrape_counts else 0
total_norm = meta.get("total_normalized", 0)
total_rel = meta.get("total_relevant", 0)
relevance_pct = round((total_rel / total_norm) * 100) if total_norm else 0
last_iso = meta.get("last_refresh_utc")
last_rel = _relative(last_iso) if last_iso else "never"
last_utc = _format_utc(last_iso)
chroma_size = meta.get("chroma_collection_size", 0)

tile_cols = st.columns([1.2, 1, 1.2, 1, 1.2, 1.2], gap="small")
with tile_cols[0]:
    st.markdown(stat_tile_html("🕒 ", "Last refresh", last_rel, last_utc if last_iso else None),
                unsafe_allow_html=True)
with tile_cols[1]:
    st.markdown(stat_tile_html("📦 ", "Normalized", f"{total_norm:,}", "capped to 1000"),
                unsafe_allow_html=True)
with tile_cols[2]:
    st.markdown(stat_tile_html("🎯 ", "Discovery-relevant", f"{total_rel:,}",
                                f"{relevance_pct}% of capped"),
                unsafe_allow_html=True)
with tile_cols[3]:
    st.markdown(stat_tile_html("🧠 ", "In Chroma", f"{chroma_size:,}", "embeddings"),
                unsafe_allow_html=True)
with tile_cols[4]:
    scrape_sub = (
        " · ".join(f"{k}:{v}" for k, v in scrape_counts.items())
        if scraped_this_run else "reused cached raw"
    )
    st.markdown(stat_tile_html("🌐 ", "Scraped this run",
                                f"{scraped_this_run:,}" if scraped_this_run else "-",
                                scrape_sub),
                unsafe_allow_html=True)
with tile_cols[5]:
    if not df_reviews.empty:
        st.download_button(
            label="⬇ Excel",
            data=reviews_to_excel_bytes(df_reviews),
            file_name=f"spotify_reviews_{datetime.utcnow().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.download_button(
            label="⬇ Relevant only",
            data=reviews_to_excel_bytes(df_reviews[df_reviews["is_relevant"] == True]),
            file_name=f"spotify_reviews_relevant_{datetime.utcnow().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# --- Source + Tagged pills row ---
by_source = meta.get("by_source", {}) or {}
by_tag = meta.get("by_canonical_tag", {}) or {}

source_pills = "".join(
    f'<span class="src-pill {_source_class(s)}"><strong>{n:,}</strong> {_source_label(s)}</span>'
    for s, n in by_source.items()
)
tag_pills = "".join(
    f'<span class="tag-pill">{k.replace("Q1_", "").replace("Q2_", "").replace("Q3_", "").replace("Q4_", "").replace("Q5_", "").replace("Q6_", "")} · {v}</span>'
    for k, v in by_tag.items()
)
st.markdown(
    f'<div style="margin-top:10px;font-size:12px;">'
    f'<span class="meta-label">By source:</span>{source_pills}'
    f'<span class="meta-label" style="padding-left:14px;">Tagged:</span>{tag_pills}'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------------- GitHub Actions history ----------------

@st.cache_data(ttl=300)
def load_action_runs() -> dict:
    if list_action_runs is None:
        return {"runs": [], "actions_tab_url": None}
    try:
        return list_action_runs(limit=10)
    except Exception as exc:                                      # noqa: BLE001
        return {"runs": [], "actions_tab_url": None, "error": str(exc)}


def _status_badge_html(status: str) -> str:
    label = {
        "no_action_yet": "initial commit",
        "failure": "failed",
        "pending": "running",
        "success": "success",
        "cancelled": "cancelled",
        "skipped": "skipped",
    }.get(status, status)
    icon = {
        "success": "✓", "failure": "✕", "pending": "●",
        "cancelled": "✕", "skipped": "—", "no_action_yet": "○",
    }.get(status, "●")
    return f'<span class="status-badge status-{status}">{icon} {label}</span>'


actions = load_action_runs()
render_section_head(
    "WEEKLY AUTOMATION",
    "Recent GitHub Action runs",
    "Each successful run commits fresh data to the repo. Download the exact data snapshot from any past run below.",
)

if actions.get("error"):
    st.warning(f"Could not fetch run history: {actions['error']}")

runs = actions.get("runs", [])
if not runs:
    st.info("No runs found yet. After the first GitHub Action runs, completed snapshots will appear here.")
else:
    show_all = (
        st.toggle(f"Show all {len(runs)} runs", value=False, key="show_all_runs")
        if len(runs) > 1 else True
    )
    visible = runs if show_all else runs[:1]

    for idx, r in enumerate(visible):
        badge = _status_badge_html(r.get("status", "pending"))
        title = r.get("title", "refresh")
        when = _relative(r.get("started_at"))
        utc = _format_utc(r.get("started_at"))
        sha = (r.get("output_sha") or "unknown")[:7]
        run_link = (
            f'<a href="{r["html_url"]}" target="_blank" '
            f'style="margin-left:auto;color:#9CA3AF;font-size:12px;">↗ view run</a>'
            if r.get("html_url") else ""
        )
        dl = r.get("downloads") or {}
        dl_buttons = ""
        if dl:
            dl_items = [
                ("reviews_jsonl",     "📄 reviews.jsonl"),
                ("metadata",          "🧾 metadata.json"),
                ("canonical_answers", "🧠 canonical answers"),
                ("seed_reviews",      "🌱 seed reviews"),
            ]
            dl_buttons = (
                '<div style="margin-top:10px;">'
                '<span style="color:#6b7280;font-size:11.5px;margin-right:6px;">Download data from this run:</span>'
                + "".join(
                    f'<a class="dl-btn" href="{dl[k]}" target="_blank" download>⬇ {lbl}</a>'
                    for k, lbl in dl_items if dl.get(k)
                )
                + "</div>"
            )

        primary_cls = " primary" if idx == 0 else ""
        st.markdown(
            f"""<div class="run-row{primary_cls}">
                <div class="run-line">
                    {badge}
                    <span class="run-title">{title}</span>
                    <span class="run-meta">⏱ {when}</span>
                    <span class="run-meta" style="display:none;">{utc}</span>
                    <span class="run-sha">#{sha}</span>
                    {run_link}
                </div>
                {dl_buttons}
            </div>""",
            unsafe_allow_html=True,
        )

    if actions.get("actions_tab_url"):
        st.markdown(
            f'<div style="margin-top:6px;font-size:11.5px;color:#6b7280;">'
            f'<a href="{actions["actions_tab_url"]}" target="_blank">↗ view all runs on GitHub</a>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ---------------- The 6 canonical questions (main section, React-parity) ----------------

render_section_head(
    "PRE-COMPUTED RAG SYNTHESIS",
    "The 6 canonical questions",
    "Click a card to read the full synthesis and the supporting reviews.",
)

answers = canon.get("answers", {})

if "selected_canonical_id" not in st.session_state:
    st.session_state["selected_canonical_id"] = None
selected_id = st.session_state["selected_canonical_id"]

grid_cols = st.columns(3, gap="small")
for idx, q in enumerate(CANONICAL_QUESTIONS):
    a = answers.get(q.id)
    is_selected = (selected_id == q.id)
    card_class = "qcard qcard-selected" if is_selected else "qcard"
    with grid_cols[idx % 3]:
        st.markdown(
            f"""<div class="{card_class}">
                <div class="qid">{q.id}</div>
                <div class="qshort">{q.short}</div>
                <div class="qfull">{q.full}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if a is None:
            st.button("Not computed yet", key=f"open_{q.id}", disabled=True,
                      use_container_width=True)
        else:
            btn_label = "Showing below ↓" if is_selected else "View answer & reviews →"
            if st.button(btn_label, key=f"open_{q.id}", use_container_width=True,
                         type="primary" if is_selected else "secondary"):
                st.session_state["selected_canonical_id"] = None if is_selected else q.id
                st.rerun()

selected_id = st.session_state["selected_canonical_id"]
if selected_id:
    a = answers.get(selected_id)
    if not a:
        st.warning("No precomputed answer for this question yet. Run `python -m src.pipeline.refresh` first.")
    else:
        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
        head_cols = st.columns([6, 1])
        head_cols[0].markdown(f"#### {a['question_full']}")
        if head_cols[1].button("✕ Close", key="close_canonical", use_container_width=True):
            st.session_state["selected_canonical_id"] = None
            st.rerun()
        render_answer_with_reviews(
            answer_text=a["answer"],
            features=a.get("spotify_features_mentioned", []),
            segments=a.get("user_segments_affected", []),
            confidence=a.get("confidence", "medium"),
            review_ids=a.get("review_ids", []),
            df=df_reviews,
            state_key=f"canon_{selected_id}",
        )

# ---------------- Ask Your Own (main section, React-parity) ----------------

render_section_head(
    "IN-SCOPE ONLY · GROUNDED IN USER REVIEWS",
    "Ask your own question",
    "The scope wrapper accepts paraphrases of the 6 canonical questions and refuses everything else.",
)

user_q = st.text_input(
    "",
    placeholder="Ask anything about Spotify discovery, recommendations, or repetitive listening...",
    label_visibility="collapsed",
    key="custom_q_input",
)

sample_qs = [
    "Why does Spotify keep recommending songs I already love?",
    "How do regional listeners feel about Discover Weekly?",
    "What do users say about the DJ feature?",
]
sample_cols = st.columns(len(sample_qs))
for i, sq in enumerate(sample_qs):
    if sample_cols[i].button(sq, key=f"sample_{i}", use_container_width=True):
        st.session_state["custom_q_input"] = sq
        st.rerun()

active_q = st.session_state.get("custom_q_input") or user_q
if active_q:
    with st.spinner("Checking scope..."):
        scope = evaluate_scope(active_q)

    st.caption(
        f"Scope decision: **{'in-scope' if scope.in_scope else 'out-of-scope'}** "
        f"· similarity={scope.max_similarity:.2f} · nearest={scope.nearest_canonical_id} "
        f"· path={scope.confidence}"
    )

    if not scope.in_scope:
        st.markdown(f'<div class="scope-out"><strong>Out of scope.</strong> {OUT_OF_SCOPE_MESSAGE}</div>',
                    unsafe_allow_html=True)
    else:
        with st.spinner("Retrieving evidence and synthesising..."):
            ans = answer_question(active_q)
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
                state_key=f"custom_{hash(active_q) % 100000}",
            )

# ---------------- Tabs: Themes / Architecture / Raw Data ----------------

render_section_head(
    "DEEPER VIEWS",
    "Themes, architecture, and raw data",
    "Browse mention frequencies, the engine's architecture diagram, and the full filterable review table.",
)
tab_themes, tab_arch, tab_raw = st.tabs(
    ["🎯 Themes & Segments", "🏗 Architecture", "📋 Raw Data"]
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
- **Refreshable:** the Chroma index is upserted weekly by GitHub Actions, so
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
    st.subheader(f"Raw reviews · {len(df_reviews):,} rows")
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

# ---------------- Footer ----------------

st.markdown(
    """
    <div class="app-footer">
        <div>Powered by Groq (Llama-3.x) · Sentence-Transformers · ChromaDB · Streamlit</div>
        <div>PM Capstone · Spotify Discovery Pain</div>
    </div>
    """,
    unsafe_allow_html=True,
)
