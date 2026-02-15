"""
Polymarket Market Idea Validator — Streamlit App

Wires together polymarket_checker, reddit_checker, and analyzer to validate
prediction market ideas end-to-end.
"""

import datetime
import streamlit as st

from polymarket_checker import load_all_events, find_matching_markets
from reddit_checker import RedditChecker
from analyzer import (
    extract_keywords,
    generate_search_queries,
    filter_relevant_posts,
    compute_heat_score,
    generate_verdict,
)

# ---------------------------------------------------------------------------
# Page config — centered layout, not wide
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Market Curator",
    page_icon="\u25b2",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Inject full CSS overhaul
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ========================================================================
   GLOBAL RESET & FOUNDATIONS
   ======================================================================== */

.block-container {
    padding-top: 2.5rem !important;
    padding-bottom: 4rem !important;
    max-width: 820px !important;
}

hr { border-color: #1e2330 !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ========================================================================
   TYPOGRAPHY
   ======================================================================== */
h1, h2, h3, h4, h5, h6 {
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
}

/* ========================================================================
   SEARCH CARD — the main input container
   ======================================================================== */
.search-card {
    background: #131720;
    border: 1.5px solid #1e2330;
    border-radius: 16px;
    padding: 1.1rem 1.25rem 0.9rem 1.25rem;
    margin-bottom: 0.4rem;
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}
.search-card:focus-within {
    border-color: #00d4aa44;
    box-shadow: 0 0 0 1px #00d4aa1a;
}

/* ---------- Suggestion row beneath the card ---------- */
.suggestions {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.35rem 0.3rem 0 0.3rem;
    margin-bottom: 1.8rem;
    flex-wrap: wrap;
}
.suggestions-label {
    font-size: 0.68rem;
    color: #3a4050;
    font-weight: 500;
    letter-spacing: 0.03em;
    margin-right: 0.1rem;
}

/* ========================================================================
   INPUTS — text input inside the search card
   ======================================================================== */
div[data-testid="stTextInput"] input {
    background: transparent !important;
    border: 1.5px solid #1e233066 !important;
    border-radius: 10px !important;
    padding: 0.7rem 0.9rem !important;
    font-size: 0.95rem !important;
    color: #f0f0f0 !important;
    transition: border-color 0.2s ease;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #00d4aa55 !important;
    box-shadow: none !important;
}
div[data-testid="stTextInput"] input::placeholder {
    color: #3a4050 !important;
}

/* Form submit button (primary) — compact pill next to input */
button[kind="primaryFormSubmit"],
button[kind="primary"] {
    background: #00d4aa !important;
    color: #0e1117 !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.7rem 1.4rem !important;
    letter-spacing: 0.01em !important;
    transition: background 0.15s ease, transform 0.1s ease;
    height: auto !important;
    margin-top: 0 !important;
}
button[kind="primaryFormSubmit"]:hover,
button[kind="primary"]:hover {
    background: #00e8bb !important;
    transform: translateY(-1px);
}
button[kind="primaryFormSubmit"]:active,
button[kind="primary"]:active {
    transform: translateY(0px);
}

/* Example query buttons — tiny ghost chips */
button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid #1e233088 !important;
    border-radius: 100px !important;
    color: #4a5064 !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    padding: 0.22rem 0.65rem !important;
    transition: all 0.15s ease;
    min-height: 0 !important;
    line-height: 1.3 !important;
}
button[kind="secondary"]:hover {
    border-color: #00d4aa44 !important;
    color: #00d4aa !important;
    background: #00d4aa08 !important;
}

/* ========================================================================
   FORM OVERRIDES — kill Streamlit's form chrome
   ======================================================================== */
/* Remove the default border Streamlit puts around forms */
[data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
}
/* Tighten vertical gap inside form between input row elements */
[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
    align-items: end !important;
    gap: 0.5rem !important;
}
/* Hide the "Press Enter to submit" text Streamlit auto-adds */
[data-testid="stForm"] .stFormSubmitContent {
    display: none !important;
}

/* ========================================================================
   METRICS — refined card look
   ======================================================================== */
[data-testid="stMetric"] {
    background: #131720;
    border: 1px solid #1e2330;
    border-radius: 14px;
    padding: 1rem 1.1rem 0.85rem 1.1rem;
}
[data-testid="stMetricLabel"] {
    color: #5a6377 !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    font-weight: 700 !important;
    font-size: 1.35rem !important;
}

/* ========================================================================
   EXPANDERS — cleaner toggle
   ======================================================================== */
[data-testid="stExpander"] {
    border: 1px solid #1e2330 !important;
    border-radius: 14px !important;
    background: #131720 !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #7a8194 !important;
    padding: 0.75rem 1rem !important;
}
[data-testid="stExpander"] summary:hover { color: #b0b8c8 !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 0 1rem 0.85rem 1rem !important;
}

/* ========================================================================
   CUSTOM COMPONENTS
   ======================================================================== */

/* ---------- Hero / Title area ---------- */
.hero-title {
    font-size: 1.45rem;
    font-weight: 700;
    color: #f0f2f5;
    letter-spacing: -0.03em;
    margin-bottom: 0.1rem;
    line-height: 1.2;
}
.hero-sub {
    font-size: 0.8rem;
    color: #3a4050;
    font-weight: 400;
    margin-bottom: 1.1rem;
    line-height: 1.5;
}
.hero-accent {
    color: #00d4aa;
}

/* ---------- Results divider ---------- */
.results-divider {
    border: none;
    border-top: 1px solid #1e2330;
    margin: 0.6rem 0 0.2rem 0;
}

/* ---------- Keyword pills ---------- */
.kw-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
    margin-bottom: 0.2rem;
}
.kw-label {
    font-size: 0.65rem;
    color: #3a4050;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.kw-pill {
    display: inline-block;
    background: #00d4aa0a;
    color: #00d4aa99;
    border: 1px solid #00d4aa15;
    border-radius: 100px;
    padding: 0.15rem 0.6rem;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}

/* ---------- Verdict ---------- */
.verdict-container {
    text-align: center;
    padding: 1.8rem 0 1.3rem 0;
}
.verdict-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #4a5064;
    margin-bottom: 0.6rem;
}
.verdict-text {
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin-bottom: 0.4rem;
}
.verdict-desc {
    font-size: 0.85rem;
    color: #5a6377;
    max-width: 500px;
    margin: 0 auto;
    line-height: 1.5;
}
.verdict-strong-launch   .verdict-text { color: #00d4aa; }
.verdict-worth-considering .verdict-text { color: #f0b90b; }
.verdict-adjacent        .verdict-text { color: #6ea8fe; }
.verdict-already-covered .verdict-text { color: #ef4444; }
.verdict-low-priority    .verdict-text { color: #5a6377; }

/* ---------- Section headers ---------- */
.section-header {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #4a5064;
    margin-bottom: 0.9rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #1e2330;
}

/* ---------- Market card ---------- */
.pm-card {
    background: #131720;
    border: 1px solid #1e2330;
    border-radius: 14px;
    padding: 1rem 1.15rem;
    margin-bottom: 0.6rem;
    transition: border-color 0.15s ease;
}
.pm-card:hover { border-color: #2a3040; }
.pm-card-q {
    font-size: 0.88rem;
    font-weight: 600;
    color: #e8eaed;
    line-height: 1.35;
    margin-bottom: 0.45rem;
}
.pm-card-prices {
    display: flex;
    gap: 0.6rem;
    margin-bottom: 0.35rem;
}
.pm-outcome {
    background: #0e1117;
    border: 1px solid #1e2330;
    border-radius: 8px;
    padding: 0.3rem 0.6rem;
    font-size: 0.78rem;
    font-weight: 500;
}
.pm-outcome-yes { color: #00d4aa; }
.pm-outcome-no  { color: #ef4444; }
.pm-outcome-other { color: #7a8194; }
.pm-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.3rem;
}
.pm-vol {
    font-size: 0.72rem;
    color: #4a5064;
}
.pm-link {
    font-size: 0.72rem;
    color: #00d4aa;
    text-decoration: none;
    font-weight: 500;
    opacity: 0.7;
    transition: opacity 0.15s ease;
}
.pm-link:hover { opacity: 1; text-decoration: none; }
.pm-match {
    font-size: 0.68rem;
    color: #3a4050;
    font-weight: 500;
}

/* ---------- Reddit card ---------- */
.rd-card {
    background: #131720;
    border: 1px solid #1e2330;
    border-radius: 14px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.5rem;
    transition: border-color 0.15s ease;
}
.rd-card:hover { border-color: #2a3040; }
.rd-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}
.rd-sub {
    font-size: 0.72rem;
    font-weight: 600;
    color: #00d4aa;
    opacity: 0.8;
}
.rd-stats {
    font-size: 0.7rem;
    color: #3a4050;
}
.rd-title {
    font-size: 0.83rem;
    color: #c8ccd4;
    line-height: 1.4;
    margin-bottom: 0.3rem;
}
.rd-link {
    font-size: 0.7rem;
    color: #4a5064;
    text-decoration: none;
    transition: color 0.15s ease;
}
.rd-link:hover { color: #6ea8fe; }

/* ---------- Heat gauge ---------- */
.heat-gauge {
    text-align: center;
    padding: 0.5rem 0 0.75rem 0;
}
.heat-number {
    font-size: 3rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1;
}
.heat-of {
    font-size: 0.9rem;
    color: #3a4050;
    font-weight: 500;
}
.heat-label-tag {
    display: inline-block;
    border-radius: 100px;
    padding: 0.2rem 0.75rem;
    font-size: 0.7rem;
    font-weight: 600;
    margin-top: 0.4rem;
    letter-spacing: 0.03em;
}

/* Heat bar */
.hbar-bg {
    background: #1e2330;
    border-radius: 100px;
    height: 6px;
    width: 100%;
    margin-top: 0.5rem;
    overflow: hidden;
}
.hbar-fill {
    height: 6px;
    border-radius: 100px;
}

/* ---------- Breakdown row ---------- */
.bd-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0;
    border-bottom: 1px solid #1a1f2a;
}
.bd-row:last-child { border-bottom: none; }
.bd-label {
    font-size: 0.78rem;
    color: #5a6377;
    font-weight: 500;
}
.bd-value {
    font-size: 0.78rem;
    color: #b0b8c8;
    font-weight: 600;
}

/* ---------- Empty state ---------- */
.empty-state {
    text-align: center;
    padding: 2.5rem 1rem;
    color: #3a4050;
}
.empty-icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    opacity: 0.4;
}
.empty-text {
    font-size: 0.82rem;
    color: #4a5064;
}

/* ---------- History ---------- */
.hist-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.65rem 0;
    border-bottom: 1px solid #151a24;
}
.hist-item:last-child { border-bottom: none; }
.hist-time {
    font-size: 0.7rem;
    color: #3a4050;
    font-weight: 500;
    min-width: 48px;
    font-variant-numeric: tabular-nums;
}
.hist-idea {
    flex: 1;
    font-size: 0.82rem;
    color: #8a91a4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.hist-verdict {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.15rem 0.5rem;
    border-radius: 6px;
    white-space: nowrap;
}
.hv-green  { color: #00d4aa; background: #00d4aa10; }
.hv-yellow { color: #f0b90b; background: #f0b90b10; }
.hv-blue   { color: #6ea8fe; background: #6ea8fe10; }
.hv-red    { color: #ef4444; background: #ef444410; }
.hv-gray   { color: #5a6377; background: #5a637710; }
.hist-heat {
    font-size: 0.72rem;
    font-weight: 600;
    color: #3a4050;
    font-variant-numeric: tabular-nums;
    min-width: 24px;
    text-align: right;
}

/* ========================================================================
   STREAMLIT OVERRIDES — hide noisy defaults
   ======================================================================== */

/* Collapse gap between columns */
[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }

/* Info boxes */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: 1px solid #1e2330 !important;
    background: #131720 !important;
}

/* Spinner */
[data-testid="stSpinner"] {
    color: #00d4aa !important;
}

/* ========================================================================
   ANIMATIONS — landing page floating bubbles & transitions
   ======================================================================== */

/* Gentle drift for suggestion bubbles — irregular keyframes so buttons
   sharing this animation still look organic */
@keyframes bubble-float {
    0%   { transform: translateY(0px) rotate(0deg); }
    12%  { transform: translateY(-7px) rotate(0.4deg); }
    28%  { transform: translateY(-3px) rotate(-0.3deg); }
    45%  { transform: translateY(-11px) rotate(0.6deg); }
    58%  { transform: translateY(-5px) rotate(-0.2deg); }
    73%  { transform: translateY(-9px) rotate(0.3deg); }
    88%  { transform: translateY(-2px) rotate(-0.15deg); }
    100% { transform: translateY(0px) rotate(0deg); }
}

/* Pulsing teal glow on the search card */
@keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px 2px #00d4aa08, 0 8px 32px -8px #00000040; }
    50%      { box-shadow: 0 0 35px 5px #00d4aa14, 0 8px 40px -8px #00000050; }
}

/* One-shot slide-up for results page load */
@keyframes slide-up-appear {
    0%   { opacity: 0; transform: translateY(25px); }
    100% { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "reddit_checker" not in st.session_state:
    st.session_state.reddit_checker = RedditChecker()

if "reddit_status" not in st.session_state:
    st.session_state.reddit_status = []

if "idea_input" not in st.session_state:
    st.session_state.idea_input = ""

# ---------------------------------------------------------------------------
# Hero header — tight, the search card is the focal point
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="hero-title">'
    '<span class="hero-accent">\u25b2</span> Market Curator'
    '</div>'
    '<div class="hero-sub">'
    'Validate prediction market ideas against Polymarket coverage and Reddit demand.'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Search card — input + button side-by-side inside a contained card
# ---------------------------------------------------------------------------
EXAMPLES = [
    "Taylor Swift Travis Kelce married",
    "Bitcoin 200k 2026",
    "Champions League winner",
    "AI regulation US",
]

# Contained search card with form (Enter to submit)
st.markdown('<div class="search-card">', unsafe_allow_html=True)

with st.form("search_form", clear_on_submit=False, border=False):
    col_input, col_btn = st.columns([5, 1], gap="small")

    with col_input:
        idea = st.text_input(
            "Market idea",
            value=st.session_state.idea_input,
            placeholder="Describe a prediction market idea...",
            label_visibility="collapsed",
        )

    with col_btn:
        submit = st.form_submit_button(
            "\u2192  Validate",
            type="primary",
            use_container_width=True,
        )

st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Determine mode: landing (centered, floating bubbles) vs results
# ---------------------------------------------------------------------------
will_show_results = submit and idea.strip()
is_landing = not will_show_results

# ---------------------------------------------------------------------------
# Landing mode CSS — injected AFTER the form so we know the mode.
# CSS <style> blocks apply retroactively to the entire page.
# ---------------------------------------------------------------------------
if is_landing:
    st.markdown("""
    <style>
    /* Vertical centering */
    .block-container { padding-top: 25vh !important; }
    @media (max-height: 600px) {
        .block-container { padding-top: 10vh !important; }
    }

    /* Center hero text */
    .hero-title, .hero-sub { text-align: center; }

    /* Search card floating glow */
    .search-card {
        box-shadow: 0 0 25px 3px #00d4aa0c, 0 8px 32px -8px #00000040;
        animation: glow-pulse 4s ease-in-out infinite;
    }

    /* Suggestion buttons — floating bubble style */
    button[kind="secondary"] {
        animation: bubble-float 8s ease-in-out infinite !important;
        background: #131720 !important;
        border: 1px solid #1e233066 !important;
        border-radius: 100px !important;
        padding: 0.4rem 1rem !important;
        font-size: 0.76rem !important;
        box-shadow: 0 4px 20px -4px #00000030 !important;
        white-space: nowrap !important;
        color: #4a5064 !important;
    }
    button[kind="secondary"]:hover {
        border-color: #00d4aa55 !important;
        color: #00d4aa !important;
        background: #00d4aa08 !important;
        box-shadow: 0 4px 24px -4px #00d4aa15 !important;
        transform: scale(1.05);
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Suggestion bubbles — 2-row scattered layout in landing mode only
# ---------------------------------------------------------------------------
example_clicked = False

if is_landing:
    st.markdown('<div style="height:1.2rem;"></div>', unsafe_allow_html=True)

    # Row 1: two buttons with spacer columns for scatter effect
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns([1.5, 2, 2.5, 2, 1.5])
    with r1c2:
        if st.button(EXAMPLES[0], key="ex_0"):
            st.session_state.idea_input = EXAMPLES[0]
            example_clicked = True
    with r1c4:
        if st.button(EXAMPLES[1], key="ex_1"):
            st.session_state.idea_input = EXAMPLES[1]
            example_clicked = True

    # Row 2: offset from row 1 for organic asymmetry
    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns([0.8, 2, 3, 2, 0.8])
    with r2c2:
        if st.button(EXAMPLES[2], key="ex_2"):
            st.session_state.idea_input = EXAMPLES[2]
            example_clicked = True
    with r2c4:
        if st.button(EXAMPLES[3], key="ex_3"):
            st.session_state.idea_input = EXAMPLES[3]
            example_clicked = True

if example_clicked:
    st.rerun()

# ---------------------------------------------------------------------------
# Verdict styling maps
# ---------------------------------------------------------------------------
VERDICT_CSS = {
    "STRONG LAUNCH": "verdict-strong-launch",
    "WORTH CONSIDERING": "verdict-worth-considering",
    "ADJACENT OPPORTUNITY": "verdict-adjacent",
    "ALREADY COVERED": "verdict-already-covered",
    "LOW PRIORITY": "verdict-low-priority",
}
VERDICT_EMOJI = {
    "STRONG LAUNCH": "\U0001f680",
    "WORTH CONSIDERING": "\U0001f7e1",
    "ADJACENT OPPORTUNITY": "\U0001f535",
    "ALREADY COVERED": "\U0001f6d1",
    "LOW PRIORITY": "\u26aa",
}
VERDICT_HIST_CLASS = {
    "STRONG LAUNCH": "hv-green",
    "WORTH CONSIDERING": "hv-yellow",
    "ADJACENT OPPORTUNITY": "hv-blue",
    "ALREADY COVERED": "hv-red",
    "LOW PRIORITY": "hv-gray",
}


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------
def _heat_color(score):
    """Return the accent color for a given heat score."""
    if score >= 70:
        return "#00d4aa"
    if score >= 50:
        return "#f0b90b"
    if score >= 30:
        return "#f97316"
    return "#3a4050"


def _heat_label_style(score):
    """Return (label, text-color, bg-color) for a heat score."""
    if score >= 70:
        return "Very Hot", "#00d4aa", "#00d4aa15"
    if score >= 50:
        return "Hot", "#f0b90b", "#f0b90b15"
    if score >= 30:
        return "Moderate", "#f97316", "#f9731615"
    if score > 0:
        return "Low", "#5a6377", "#5a637712"
    return "No Signal", "#3a4050", "#3a405012"


def _render_market_card(m):
    """Render a single Polymarket market card."""
    # Build outcome chips
    chips = ""
    for i, outcome in enumerate(m.get("outcomes", [])):
        price = m["outcome_prices"][i] if i < len(m.get("outcome_prices", [])) else "?"
        # Color the first outcome green, second red, rest gray
        if i == 0:
            cls = "pm-outcome-yes"
        elif i == 1:
            cls = "pm-outcome-no"
        else:
            cls = "pm-outcome-other"
        chips += f'<span class="pm-outcome {cls}">{outcome} {price}</span>'

    vol_str = ""
    vol = m.get("volume", 0)
    if vol:
        try:
            vol_str = f"${float(vol):,.0f} vol"
        except (ValueError, TypeError):
            pass

    slug = m.get("slug", "")
    link_html = (
        f'<a class="pm-link" href="https://polymarket.com/event/{slug}" '
        f'target="_blank">Open \u2197</a>'
        if slug else ""
    )

    overlap_pct = f"{m['overlap_ratio'] * 100:.0f}%"

    st.markdown(
        f'<div class="pm-card">'
        f'  <div class="pm-card-q">{m["question"]}</div>'
        f'  <div class="pm-card-prices">{chips}</div>'
        f'  <div class="pm-meta">'
        f'    <span class="pm-vol">{vol_str}</span>'
        f'    <span class="pm-match">{overlap_pct} match</span>'
        f'    {link_html}'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_reddit_card(post):
    """Render a single Reddit post card."""
    st.markdown(
        f'<div class="rd-card">'
        f'  <div class="rd-header">'
        f'    <span class="rd-sub">r/{post["subreddit"]}</span>'
        f'    <span class="rd-stats">{post["score"]:,} pts \u00b7 '
        f'    {post["num_comments"]:,} comments</span>'
        f'  </div>'
        f'  <div class="rd-title">{post["title"]}</div>'
        f'  <a class="rd-link" href="https://reddit.com{post["permalink"]}" '
        f'  target="_blank">reddit.com{post["permalink"][:50]}...</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------
if submit and not idea.strip():
    st.warning("Please enter a market idea to validate.")

if submit and idea.strip():
    # Results-mode CSS — subtle slide-up animation on entry
    st.markdown("""
    <style>
    .search-card {
        animation: slide-up-appear 0.35s ease-out;
    }
    .verdict-container,
    .section-header,
    .pm-card,
    .rd-card {
        animation: slide-up-appear 0.4s ease-out;
    }
    </style>
    """, unsafe_allow_html=True)

    st.session_state.idea_input = ""
    keywords = extract_keywords(idea)

    if not keywords:
        st.warning("Could not extract keywords. Try a more specific idea.")
    else:
        # Keyword pills + visual break before results
        pills = "".join(f'<span class="kw-pill">{kw}</span>' for kw in keywords)
        st.markdown(
            '<hr class="results-divider">'
            f'<div class="kw-row">'
            f'<span class="kw-label">Keywords</span> {pills}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- Polymarket check ---
        pm_failed = False
        with st.spinner("Checking Polymarket..."):
            try:
                events = load_all_events()
                pm_matches = find_matching_markets(keywords, events)
            except Exception as e:
                pm_failed = True
                pm_matches = []
                st.warning(
                    "Could not reach Polymarket API. "
                    "Results will use Reddit data only."
                )

        # --- Reddit check ---
        queries = generate_search_queries(idea)
        all_posts = []
        seen_ids = set()
        reddit_warnings = []

        reddit_status_placeholder = st.empty()

        def _reddit_status_cb(msg):
            """Surface Reddit status (rate limits, retries) in the UI."""
            reddit_warnings.append(msg)
            reddit_status_placeholder.info(f"\u23f3 {msg}")

        checker = st.session_state.reddit_checker
        checker._status_callback = _reddit_status_cb

        with st.spinner(f"Scanning Reddit ({len(queries)} queries)..."):
            try:
                posts = checker.multi_search(queries[0])
                for post in posts:
                    if post["id"] not in seen_ids:
                        seen_ids.add(post["id"])
                        all_posts.append(post)
            except Exception as e:
                st.warning(f"Reddit search failed for '{queries[0]}': {e}")

            for q in queries[1:]:
                try:
                    posts = checker.search(q, sort="relevance", timeframe="month")
                    for post in posts:
                        if post["id"] not in seen_ids:
                            seen_ids.add(post["id"])
                            all_posts.append(post)
                except Exception as e:
                    st.warning(f"Reddit search failed for '{q}': {e}")

        # Clear the live status placeholder once scanning is complete
        reddit_status_placeholder.empty()

        # Filter
        all_posts = filter_relevant_posts(all_posts, idea)

        # Score & verdict
        heat_result = compute_heat_score(all_posts)
        verdict = generate_verdict(pm_matches, heat_result)

        # =================================================================
        # VERDICT — centered hero block
        # =================================================================
        v_css = VERDICT_CSS.get(verdict["verdict"], "verdict-low-priority")
        v_emoji = VERDICT_EMOJI.get(verdict["verdict"], verdict["emoji"])
        st.markdown(
            f'<div class="verdict-container {v_css}">'
            f'  <div class="verdict-label">Verdict</div>'
            f'  <div class="verdict-text">{v_emoji} {verdict["verdict"]}</div>'
            f'  <div class="verdict-desc">{verdict["description"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # =================================================================
        # TWO COLUMNS: Polymarket | Reddit
        # =================================================================
        col_pm, col_rd = st.columns(2, gap="large")

        # ---- LEFT: Polymarket ----
        with col_pm:
            st.markdown(
                '<div class="section-header">Polymarket Coverage</div>',
                unsafe_allow_html=True,
            )
            if pm_matches:
                for m in pm_matches[:4]:
                    _render_market_card(m)
                if len(pm_matches) > 4:
                    with st.expander(f"{len(pm_matches) - 4} more markets"):
                        for m in pm_matches[4:]:
                            _render_market_card(m)
            elif pm_failed:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-icon">\u26a0\ufe0f</div>'
                    '<div class="empty-text">'
                    'Polymarket API unavailable.<br>'
                    'Could not check for existing markets.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-icon">\u2205</div>'
                    '<div class="empty-text">'
                    'No existing markets found.<br>This topic is open.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )

        # ---- RIGHT: Reddit ----
        with col_rd:
            st.markdown(
                '<div class="section-header">Reddit Demand</div>',
                unsafe_allow_html=True,
            )

            score = heat_result["score"]
            bd = heat_result["breakdown"]

            if bd["post_count"] == 0:
                # --- Empty state: no Reddit discussion found ---
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-icon">\U0001f50d</div>'
                    '<div class="empty-text">'
                    'No Reddit discussion found.<br>'
                    'This topic may be too niche or too new.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                # --- Full heat gauge + metrics ---
                color = _heat_color(score)
                label, lbl_color, lbl_bg = _heat_label_style(score)

                st.markdown(
                    f'<div class="heat-gauge">'
                    f'  <div class="heat-number" style="color:{color};">'
                    f'{score}</div>'
                    f'  <div class="heat-of">/100</div>'
                    f'  <span class="heat-label-tag" style="color:{lbl_color};'
                    f'  background:{lbl_bg};">{label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Thin heat bar
                st.markdown(
                    f'<div class="hbar-bg">'
                    f'<div class="hbar-fill" style="width:{score}%;'
                    f'background:{color};"></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Metric row
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Posts", bd["post_count"])
                with m2:
                    st.metric("Upvotes", f"{bd['total_score']:,}")
                with m3:
                    st.metric("Comments", f"{bd['total_comments']:,}")

                m4, m5 = st.columns(2)
                with m4:
                    st.metric("Subreddits", bd["subreddit_count"])
                with m5:
                    st.metric("Recent 7d", f"{bd['recency_pct'] * 100:.0f}%")

                # Score breakdown
                with st.expander("Score breakdown"):
                    components = [
                        ("Post count", bd["count_pts"], 25),
                        ("Upvotes", bd["score_pts"], 25),
                        ("Comments", bd["comment_pts"], 25),
                        ("Subreddit spread", bd["spread_pts"], 15),
                        ("Recency", bd["recency_pts"], 10),
                    ]
                    for name, pts, mx in components:
                        st.markdown(
                            f'<div class="bd-row">'
                            f'  <span class="bd-label">{name}</span>'
                            f'  <span class="bd-value">{pts:.1f}'
                            f'<span style="color:#3a4050;'
                            f'  font-weight:400;"> / {mx}</span></span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                # Top posts
                if heat_result["top_posts"]:
                    with st.expander(
                        f"Top posts ({len(heat_result['top_posts'])})"
                    ):
                        for post in heat_result["top_posts"]:
                            _render_reddit_card(post)

        # --- Save to history ---
        st.session_state.history.append({
            "idea": idea,
            "keywords": ", ".join(keywords),
            "verdict": verdict["verdict"],
            "verdict_emoji": VERDICT_EMOJI.get(verdict["verdict"], verdict["emoji"]),
            "heat": heat_result["score"],
            "pm_matches": len(pm_matches),
            "reddit_posts": bd["post_count"],
            "time": datetime.datetime.now().strftime("%H:%M"),
        })

# ---------------------------------------------------------------------------
# Session History — minimal list under a divider
# ---------------------------------------------------------------------------
if st.session_state.history:
    st.markdown("---")
    st.markdown(
        '<div class="section-header">History</div>',
        unsafe_allow_html=True,
    )
    rows = ""
    for h in reversed(st.session_state.history):
        hv_cls = VERDICT_HIST_CLASS.get(h["verdict"], "hv-gray")
        idea_trunc = h["idea"][:55] + ("..." if len(h["idea"]) > 55 else "")
        rows += (
            f'<div class="hist-item">'
            f'  <span class="hist-time">{h["time"]}</span>'
            f'  <span class="hist-idea">{idea_trunc}</span>'
            f'  <span class="hist-verdict {hv_cls}">{h["verdict_emoji"]} {h["verdict"]}</span>'
            f'  <span class="hist-heat">{h["heat"]}</span>'
            f'</div>'
        )
    st.markdown(rows, unsafe_allow_html=True)
