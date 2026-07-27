"""
Siemens Startup Evaluation Agent — web UI (Streamlit).

Run:
    pip install -r requirements.txt
    streamlit run app.py

Opens in your browser. Type a startup name -> it pulls the GlassDollar row, enriches it
via DuckDuckGo, scores it on the 6 weighted dimensions, matches the Siemens portfolio,
and routes it to Empower / Collaborate / Connect / Pass.
"""

import os
import json
import re
import hashlib
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; env vars must be set manually
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core

st.set_page_config(page_title="Siemens Startup Evaluation Agent", page_icon="🟩", layout="wide",
                   initial_sidebar_state="collapsed")   # legacy UI — the React app is the main frontend

# Siemens iX classic-dark palette — pillar identity colors, mirroring the --ix-pillar-* tokens.
PILLAR_COLORS = {"Empower": "#357fff", "Collaborate": "#00bde3",
                 "Connect": "#44cc00", "Pass": "#b6b8b9"}

# Mirrors the CSS --ix-* tokens below. Plotly cannot read CSS custom properties, so the
# handful of colors needed for chart styling are restated here in Python. Never used for
# any HTML/CSS rendering — those always go through the --ix-* vars in the <style> block.
IX = {
    "bg": "#0f1619", "surface": "#283236", "elevated": "#3c484d",
    "text": "#f5fcff", "soft": "rgba(229,247,255,.65)",
    "grid": "rgba(211,236,248,.25)",
    "primary": "#00bde3", "success": "#44cc00", "warning": "#ffbb00",
    "alarm": "#ff2453", "info": "#357fff", "neutral": "#b6b8b9",
}

# ----------------------------------------------------------------- frontend-only sample preview
# Mirrors the exact shape of core.evaluate()'s return dict, with obviously-synthetic values,
# so every tab can render without a live backend call. NEVER written into session_state.runs
# or session_state.last_result — it is only ever passed straight into render_result().
SAMPLE_RESULT = {
    "found": True,
    "source": "glassdollar",
    "engine": "sample:preview-data",
    "company": "Sample Startup Inc.",
    "profile": {
        "company_name": "Sample Startup Inc.",
        "website": "https://sample-startup.example",
        "hq": "Munich, Germany",
        "founded_year": "2021",
        "employees_count": "42",
        "funding": "€6.5M Series A (synthetic)",
        "linkedin_url": "https://linkedin.com/company/sample-startup",
        "crunchbase_url": "https://crunchbase.com/organization/sample-startup",
        "customers": "Acme Robotics, Northwind Energy, Contoso Manufacturing",
        "Business model": "B2B SaaS",
        "Development stage of your solution": "Early market stage",
    },
    "summary": ("Sample Startup Inc. builds a predictive-maintenance platform for industrial "
                "equipment, combining edge sensors with cloud analytics. (Synthetic preview data "
                "— not a real evaluation.)"),
    "facts": [
        {"key": "hq", "value": "Munich, Germany", "source_url": "GlassDollar", "method": "glassdollar_db",
         "confidence": 0.55, "verified": False, "retrieved_at": "2026-07-16T00:00:00+00:00"},
        {"key": "funding", "value": "€6.5M Series A (synthetic)", "source_url": "GlassDollar",
         "method": "glassdollar_db", "confidence": 0.55, "verified": False,
         "retrieved_at": "2026-07-16T00:00:00+00:00"},
        {"key": "verify:Acme Robotics", "value": "Acme Robotics case study — sample-startup.example",
         "source_url": "https://sample-startup.example/case-studies/acme", "method": "ddg_search",
         "confidence": 0.7, "verified": True, "retrieved_at": "2026-07-16T00:00:00+00:00"},
    ],
    "verification": {
        "method": "llm",
        "claims": [
            {"field": "funding", "value": "€6.5M Series A (synthetic)", "status": "partial",
             "evidence_url": "https://sample-startup.example/news", "confidence": 0.6,
             "note": "Amount not independently confirmed"},
            {"field": "hq", "value": "Munich, Germany", "status": "verified",
             "evidence_url": "https://sample-startup.example/contact", "confidence": 0.8,
             "note": "Matches website"},
            {"field": "reference_customer", "value": "Acme Robotics", "status": "verified",
             "evidence_url": "https://sample-startup.example/case-studies/acme", "confidence": 0.75,
             "note": "Case study corroborated"},
            {"field": "reference_customer", "value": "Northwind Energy", "status": "unverified",
             "evidence_url": "", "confidence": 0.3, "note": "No corroboration found"},
        ],
        "red_flags": ["Synthetic preview — one reference customer could not be corroborated online."],
    },
    "fit": {
        "aligned": True,
        "method": "llm",
        "matches": [
            {"tool": "Senseye Predictive Maintenance", "division": "Digital Industries", "confidence": 88,
             "rationale": "Direct overlap with edge-sensor predictive maintenance capability."},
            {"tool": "Insights Hub", "division": "Digital Industries", "confidence": 74,
             "rationale": "Cloud analytics layer complements existing IoT data pipelines."},
        ],
    },
    "score": {
        "dimensions": {"traction": 62.0, "siemens_fit": 88.0, "product": 65.0,
                       "market": 70.0, "founder": 70.0, "ecosystem": 58.0},
        "raw_score": 71.4, "data_completeness": 0.78, "data_confidence": 0.89,
        "final_score": 63.5, "effective_traction": 1.75,
        "verified_customers": 1, "unverified_customers": 1, "contradicted": 0,
    },
    "routing": {
        "pillar": "Collaborate", "confidence": 0.81,
        "reasons": [
            "Strong Siemens portfolio fit around predictive-maintenance tooling.",
            "Early but real reference-customer traction, partially corroborated online.",
        ],
        "risks": [
            "One reference customer not yet corroborated — verify before commitment.",
            "Funding amount is self-reported and only partially confirmed.",
        ],
    },
    "trend": {
        "label": "Rising", "color": IX["success"], "momentum": 68,
        "niche": "Predictive maintenance / industrial IoT",
        "summary": ("Search interest and funding activity in predictive-maintenance startups has "
                    "trended upward over the past two quarters. (Synthetic preview data.)"),
        "signals": ["Rising DDG search volume for 'predictive maintenance SaaS'",
                    "Two adjacent competitors raised Series A/B rounds in the last 6 months"],
        "evidence": [{"title": "Sample market note", "url": "https://sample-startup.example/market",
                      "snippet": "Synthetic evidence for preview purposes only."}],
        "method": "sample",
    },
}

st.markdown("""
<style>
:root{
  /* backgrounds */
  --ix-1:#0f1619; --ix-1-hover:#283236; --ix-1-active:#222b2f;
  --ix-2:#283236; --ix-3:#3c484d; --ix-4:#4c5a60;
  --ix-header:#000028;
  /* text */
  --ix-text:rgba(245,252,255,.9); --ix-soft:rgba(229,247,255,.65);
  --ix-weak:rgba(219,244,255,.4); --ix-contrast:#ffffff;
  /* borders */
  --ix-soft-bdr:rgba(211,236,248,.4); --ix-std-bdr:rgba(211,236,248,.55);
  --ix-weak-bdr:rgba(224,245,255,.25);
  /* interactive */
  --ix-primary:#00bde3; --ix-primary-hover:#1aecff; --ix-primary-active:#00d3e5;
  --ix-primary-contrast:#000000; --ix-dynamic:#00eaff; --ix-focus:#199fff;
  --ix-ghost-hover:rgba(140,161,171,.2); --ix-ghost-sel:rgba(0,255,255,.1);
  /* status */
  --ix-success:#44cc00; --ix-warning:#ffbb00; --ix-critical:#eb7a0a;
  --ix-alarm:#ff2453; --ix-alarm-text:#ff7694; --ix-info:#357fff; --ix-neutral:#b6b8b9;
  /* routing pillars (DESIGN MAPPING onto status ramp) */
  --ix-pillar-connect:#44cc00;
  --ix-pillar-collaborate:#00bde3;
  --ix-pillar-empower:#357fff;
  --ix-pillar-pass:#b6b8b9;
  /* shape/type */
  --ix-radius:4px; --ix-radius-lg:6px;
  --ix-font:"Siemens Sans","Segoe UI",Roboto,Arial,sans-serif;
}
.stApp {background:var(--ix-1);}
#MainMenu, footer {visibility:hidden;}
html, body, [class*="css"] {font-family:var(--ix-font); color:var(--ix-text);}
h1 {font:700 33px/1.25 var(--ix-font); color:var(--ix-text);}
h2 {font:700 28px/1.3 var(--ix-font); color:var(--ix-text);}
h3 {font:700 23px/1.35 var(--ix-font); color:var(--ix-text);}
.stMarkdown h4 {font:700 20px/1.4 var(--ix-font); color:var(--ix-text);}
.block-container {padding-top:1rem; max-width:1240px;}
.sie-header {background:var(--ix-header);border-bottom:3px solid var(--ix-primary);
  border-radius:0 0 var(--ix-radius) var(--ix-radius);padding:16px 24px;margin:-1rem -1rem 1.3rem -1rem;}
.sie-wordmark {letter-spacing:3px;font-weight:700;font-size:24px;color:var(--ix-contrast);}
.sie-sub {color:var(--ix-soft);font-size:13px;margin-top:3px;}
.card {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);border-radius:var(--ix-radius);
  padding:12px 16px;margin-bottom:12px;transition:background .15s ease;}
.card:hover {background:var(--ix-1-hover);}
.card--accent {border-left:3px solid var(--ix-primary);}
.pill {display:inline-block;color:var(--ix-contrast);padding:4px 14px;border-radius:var(--ix-radius);font-weight:700;font-size:16px;}
.kv {color:var(--ix-soft);font-size:12px;text-transform:uppercase;letter-spacing:.3px;}
.kvv{font-weight:600;font-size:15px;color:var(--ix-text);}
.toolname{font-weight:700;font-size:15px;color:var(--ix-text);} .muted{color:var(--ix-soft);font-size:13px;}
.badge{background:var(--ix-3);color:var(--ix-text);border:1px solid var(--ix-soft-bdr);border-radius:var(--ix-radius);
  padding:2px 8px;font-size:12px;font-weight:600;}
.metric-xl{font:700 40px/1 var(--ix-font);color:var(--ix-text);}
.stButton>button {background:var(--ix-primary);color:var(--ix-primary-contrast);border:0;border-radius:var(--ix-radius);
  font-weight:700;padding:.4rem 1rem;}
.stButton>button:hover {background:var(--ix-primary-hover);color:var(--ix-primary-contrast);}
.stButton>button:active {background:var(--ix-primary-active);color:var(--ix-primary-contrast);}
.stButton>button[kind="secondary"] {background:transparent;color:var(--ix-primary);border:1px solid var(--ix-primary);}
.stButton>button[kind="secondary"]:hover {background:var(--ix-ghost-hover);color:var(--ix-primary);}
.stProgress > div > div > div > div {background:var(--ix-primary);}
/* ---- tabs: make EVERY tab label visible (default was black-on-black) ---- */
.stTabs [data-baseweb="tab-list"] {gap:4px; border-bottom:1px solid var(--ix-weak-bdr);}
.stTabs [data-baseweb="tab"] {color:var(--ix-soft) !important; font-weight:600;
  padding:8px 16px; border-radius:var(--ix-radius) var(--ix-radius) 0 0;}
.stTabs [data-baseweb="tab"] * {color:inherit !important;}
.stTabs [data-baseweb="tab"]:hover {color:var(--ix-text) !important; background:var(--ix-ghost-hover);}
.stTabs [aria-selected="true"] {color:var(--ix-primary) !important; border-bottom-color:var(--ix-primary) !important;}
.stTabs [aria-selected="true"] * {color:var(--ix-primary) !important;}
/* ---- form widgets: dark fields with light text (defaults were black-on-black) ---- */
.stTextInput input, .stNumberInput input, .stTextArea textarea {
  background:var(--ix-2) !important; color:var(--ix-text) !important;
  border:1px solid var(--ix-soft-bdr) !important;}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {color:var(--ix-weak) !important;}
div[data-baseweb="select"] > div {background:var(--ix-2) !important; color:var(--ix-text) !important;
  border:1px solid var(--ix-soft-bdr) !important;}
div[data-baseweb="select"] * {color:var(--ix-text) !important;}
label, .stCheckbox label, .stRadio label, .stSelectbox label, .stTextInput label,
.stMultiSelect label, .stToggle label {color:var(--ix-text) !important;}
.stTabs [aria-selected="true"] {color:var(--ix-primary) !important; border-bottom-color:var(--ix-primary) !important;}

/* ---- global text visibility: force light text on all native Streamlit text ---- */
.stApp, .stApp p, .stApp span, .stApp li, .stApp label, .stApp div,
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span,
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] span {
  color:var(--ix-text);}
/* captions / help text render soft gray, never black */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *,
small, .stCaption {color:var(--ix-soft) !important;}
/* expander header + body */
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary *,
.streamlit-expanderHeader, .streamlit-expanderHeader * {color:var(--ix-text) !important;}
[data-testid="stExpander"] {background:var(--ix-2); border:1px solid var(--ix-soft-bdr);
  border-radius:var(--ix-radius);}
/* alert boxes (info/warning/success/error) — light text on tinted bg */
[data-testid="stAlert"], [data-testid="stAlert"] * {color:var(--ix-text) !important;}
[data-testid="stNotification"], [data-testid="stNotification"] * {color:var(--ix-text) !important;}
/* dataframe / table text */
[data-testid="stDataFrame"] *, .stDataFrame * {color:var(--ix-text) !important;}
/* chat message bubbles */
[data-testid="stChatMessage"], [data-testid="stChatMessage"] * {color:var(--ix-text);}
/* multiselect selected chips */
[data-baseweb="tag"] {background:var(--ix-3) !important;}
[data-baseweb="tag"] * {color:var(--ix-text) !important;}
/* dropdown popover options */
[data-baseweb="popover"] li, [data-baseweb="menu"] li {color:var(--ix-text) !important;}
/* download button labels */
[data-testid="stDownloadButton"] button, [data-testid="stDownloadButton"] button * {
  color:var(--ix-primary-contrast) !important;}
/* keep our own helper classes at their intended soft/colored shades */
.stApp .muted, .stApp .kv, .stApp .sie-sub, .stApp .it-k {color:var(--ix-soft) !important;}

/* live process ribbon (pipeline stepper) */
.ribbon {display:flex;align-items:center;flex-wrap:wrap;gap:0;margin:6px 0 10px 0;}
.ribbon-step {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);border-radius:var(--ix-radius);
  padding:6px 14px;font-size:12px;font-weight:700;letter-spacing:.4px;color:var(--ix-soft);text-transform:uppercase;
  transition:background .2s ease,color .2s ease,border-color .2s ease;}
.ribbon-step--active {background:var(--ix-primary);color:var(--ix-primary-contrast);
  border-color:var(--ix-primary);animation:ribbonPulse 1s ease-in-out infinite;}
.ribbon-step--done {background:rgba(68,204,0,.16);color:var(--ix-success);border-color:var(--ix-success);}
.ribbon-step--done::before {content:"✓ ";font-weight:800;}
.ribbon-arrow {color:var(--ix-weak-bdr);padding:0 6px;font-size:14px;}
@keyframes ribbonPulse {0%,100%{opacity:1} 50%{opacity:.55}}

/* "why this routing" verdict panel */
.verdict {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);border-radius:var(--ix-radius);padding:12px 16px;}
.verdict-reason, .verdict-risk {font-size:13px;padding:3px 0;color:var(--ix-text);}
.verdict-reason::before {content:"✓ ";color:var(--ix-success);font-weight:700;}
.verdict-risk::before {content:"! ";color:var(--ix-warning);font-weight:700;}

/* claim-verification status chips */
.status-chip {display:inline-block;padding:2px 10px;border-radius:var(--ix-radius);font-size:12px;font-weight:700;
  border:1px solid var(--ix-soft-bdr);}
.status-chip--ok {color:var(--ix-success);border-color:var(--ix-success);}
.status-chip--warn {color:var(--ix-warning);border-color:var(--ix-warning);}
.status-chip--neutral {color:var(--ix-neutral);border-color:var(--ix-neutral);}
.status-chip--alarm {color:var(--ix-alarm);border-color:var(--ix-alarm);}

/* honesty badge — sample-mode banner + future live-progress stub label */
.badge-preview {display:inline-block;background:transparent;color:var(--ix-warning);
  border:1px solid var(--ix-warning);border-radius:var(--ix-radius);padding:3px 10px;
  font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;}

/* ---- Overview: clean info-tile grid (replaces the dense text wall) ---- */
.info-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:4px 0 8px 0;}
.info-tile {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);border-left:3px solid var(--ix-primary);
  border-radius:var(--ix-radius);padding:12px 16px;transition:background .15s ease;min-height:64px;}
.info-tile:hover {background:var(--ix-1-hover);}
.info-tile .it-k {color:var(--ix-soft);font-size:11px;text-transform:uppercase;letter-spacing:.4px;
  display:flex;align-items:center;gap:6px;margin-bottom:4px;}
.info-tile .it-v {color:var(--ix-text);font-size:16px;font-weight:600;word-break:break-word;line-height:1.35;}
.info-tile .it-v a {color:var(--ix-primary);text-decoration:none;}
.info-tile .it-v a:hover {text-decoration:underline;}
/* stat tiles — single short values (employee count, founded year) get a big, glanceable number */
.info-tile--stat {text-align:left;}
.info-tile--stat .it-v {font:800 30px/1.1 var(--ix-font);color:var(--ix-text);}
/* bullet tiles — comma/line lists become clean bullet points instead of a wall of text */
.info-tile--list {grid-column:span 2;}
.it-bullets {margin:2px 0 0 0;padding-left:18px;}
.it-bullets li {color:var(--ix-text);font-size:14px;line-height:1.5;margin-bottom:2px;}
.section-label {color:var(--ix-soft);font-size:12px;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;margin:10px 0 6px 0;}
/* ==== Overview redesign: compact KPI chips + spec list + customer tags ==== */
/* KPI chip row — small, uniform, glanceable stats (no oversized boxes) */
.kpi-row {display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:2px 0 14px 0;}
.kpi {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);border-radius:var(--ix-radius-lg);
  padding:12px 14px;position:relative;overflow:hidden;transition:transform .12s ease,background .15s ease;}
.kpi:hover {background:var(--ix-1-hover);transform:translateY(-1px);}
.kpi::before {content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--ix-primary);}
.kpi .kpi-k {color:var(--ix-soft);font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;
  display:flex;align-items:center;gap:5px;margin-bottom:6px;}
.kpi .kpi-v {color:var(--ix-text);font:800 24px/1 var(--ix-font);}
.kpi .kpi-sub {color:var(--ix-weak);font-size:11px;margin-top:3px;}
/* spec list — dense two-column label/value rows inside one card (Siemens data-list style) */
.spec-card {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);border-radius:var(--ix-radius-lg);
  padding:4px 16px;margin-bottom:14px;}
.spec-row {display:flex;align-items:flex-start;gap:14px;padding:10px 0;
  border-bottom:1px solid var(--ix-weak-bdr);}
.spec-row:last-child {border-bottom:0;}
.spec-row .spec-k {flex:0 0 160px;color:var(--ix-soft);font-size:12px;font-weight:600;
  text-transform:uppercase;letter-spacing:.3px;display:flex;align-items:center;gap:8px;padding-top:1px;}
.spec-row .spec-v {flex:1;color:var(--ix-text);font-size:15px;font-weight:500;line-height:1.45;word-break:break-word;}
.spec-row .spec-v a {color:var(--ix-primary);text-decoration:none;}
.spec-row .spec-v a:hover {text-decoration:underline;}
.spec-row .spec-v.empty {color:var(--ix-weak);}
/* customer tag chips — replaces bullet wall */
.tag-wrap {display:flex;flex-wrap:wrap;gap:7px;}
.tag-chip {display:inline-flex;align-items:center;gap:6px;background:var(--ix-3);color:var(--ix-text);
  border:1px solid var(--ix-soft-bdr);border-radius:20px;padding:4px 12px;font-size:13px;font-weight:600;}
.tag-chip::before {content:"";width:6px;height:6px;border-radius:50%;background:var(--ix-primary);}
/* ---- st.metric: force visible light text on the dark theme ---- */
[data-testid="stMetric"] {background:var(--ix-2);border:1px solid var(--ix-soft-bdr);
  border-radius:var(--ix-radius);padding:12px 16px;}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {color:var(--ix-soft) !important;
  font-size:12px !important;text-transform:uppercase;letter-spacing:.4px;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {color:var(--ix-text) !important;
  font-weight:800 !important;}
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * {color:var(--ix-soft) !important;}
</style>
<div class="sie-header">
  <div class="sie-wordmark">SIEMENS</div>
  <div class="sie-sub">Open Innovation · Startup Scouting — Automated Startup Evaluation Agent</div>
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------- shared dark Plotly helpers
def _dark_layout(fig: "go.Figure", height: int = 220) -> "go.Figure":
    """Apply the one shared dark layout every Plotly figure in this app must use."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=IX["text"], family="Segoe UI, Roboto, Arial, sans-serif"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
    )
    return fig


def _status_color(final_score: float, pillar: str) -> str:
    """Status-thresholded color for the final-score gauge. Pass overrides to neutral —
    the routing pillars are a ladder, not a literal success/error signal."""
    if pillar == "Pass":
        return IX["neutral"]
    if final_score >= 70:
        return IX["success"]
    if final_score >= 55:
        return IX["warning"]
    return IX["alarm"]


def make_gauge(final_score: float, pillar: str) -> "go.Figure":
    color = _status_color(final_score, pillar)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=final_score,
        number={"font": {"size": 38, "color": color}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": IX["grid"], "tickfont": {"color": IX["soft"]}},
            "bar": {"color": color},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 1,
            "bordercolor": IX["grid"],
            "steps": [
                {"range": [0, 55], "color": "rgba(255,36,83,.12)"},
                {"range": [55, 70], "color": "rgba(255,187,0,.12)"},
                {"range": [70, 100], "color": "rgba(68,204,0,.12)"},
            ],
        },
    ))
    return _dark_layout(fig, height=200)


_DIM_LABELS = {"traction": "Traction", "siemens_fit": "Siemens Fit", "product": "Product",
               "market": "Market", "founder": "Founder", "ecosystem": "Ecosystem"}


def make_radar(dimensions: dict, height: int = 360) -> "go.Figure":
    cats = [_DIM_LABELS.get(k, k) for k in dimensions]
    vals = list(dimensions.values())
    cats_loop, vals_loop = cats + [cats[0]], vals + [vals[0]]
    fig = go.Figure(go.Scatterpolar(
        r=vals_loop, theta=cats_loop, fill="toself",
        line=dict(color=IX["primary"]), fillcolor="rgba(0,189,227,.25)",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=IX["grid"], color=IX["soft"]),
            angularaxis=dict(gridcolor=IX["grid"], color=IX["text"]),
        ),
        showlegend=False,
    )
    return _dark_layout(fig, height=height)


def make_radar_overlay(runs: dict, selected: list) -> "go.Figure":
    """Compare-view mini radar overlay: one trace per selected run, colored by its pillar."""
    fig = go.Figure()
    for name in selected:
        r = runs.get(name)
        if not r:
            continue
        dims = r["score"]["dimensions"]
        cats = [_DIM_LABELS.get(k, k) for k in dims]
        vals = list(dims.values())
        cats_loop, vals_loop = cats + [cats[0]], vals + [vals[0]]
        color = PILLAR_COLORS.get(r["routing"]["pillar"], IX["neutral"])
        fig.add_trace(go.Scatterpolar(r=vals_loop, theta=cats_loop, name=name,
                                      line=dict(color=color)))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=IX["grid"], color=IX["soft"]),
            angularaxis=dict(gridcolor=IX["grid"], color=IX["text"]),
        ),
        showlegend=True, legend=dict(font=dict(color=IX["text"])),
    )
    return _dark_layout(fig, height=340)


# ----------------------------------------------------------------- sidebar / config
st.session_state.setdefault("runs", {})
st.session_state.setdefault("show_portfolio", False)
st.session_state.setdefault("sample_mode", False)
# Reserved for a future live per-step progress stub — not used to fake progress today.
st.session_state.setdefault("pipeline_step", None)

with st.sidebar:
    st.subheader("Run history")
    compare_selection = []
    if st.session_state.runs:
        for _name, _r in st.session_state.runs.items():
            _label = f"{_name} — {_r['score']['final_score']:.0f}"
            if st.button(_label, key=f"history_{_name}", use_container_width=True):
                st.session_state["last_result"] = _r
                st.session_state["active_run"] = _name
                st.rerun()
        if st.button("Clear history", type="secondary", use_container_width=True):
            st.session_state.runs = {}
            st.rerun()
        compare_selection = st.multiselect("Compare runs", options=list(st.session_state.runs))
    else:
        st.caption("No runs yet — evaluate a startup to build history.")

    st.divider()
    st.session_state.show_portfolio = st.toggle(
        "📊 Portfolio view", value=st.session_state.show_portfolio,
        help="Show a sortable table of every startup evaluated in this session.")

    st.divider()
    st.session_state.sample_mode = st.checkbox(
        "🧪 Load sample result (preview)", value=st.session_state.sample_mode,
        help="Frontend-only preview using synthetic data — no backend call, never saved to run history.")

    st.divider()
    with st.expander("⚙ Settings", expanded=False):
        gd_key_input = st.text_input(
            "GlassDollar API key", value="", type="password",
            help="Leave blank to use the GLASSDOLLAR_API_KEY environment variable.")
        if gd_key_input.strip():
            os.environ["GLASSDOLLAR_API_KEY"] = gd_key_input.strip()
        gd_key_active = (gd_key_input.strip() or os.getenv("GLASSDOLLAR_API_KEY", "")).strip()
        gd_path = None  # API mode — the Excel path is no longer used.
        tools_path = st.text_input("Siemens tools CSV", core.DEFAULT_TOOLS_CSV)
        do_web = st.toggle("Web enrichment (DuckDuckGo)", value=True,
                           help="Free DDG search. Turn off for instant, offline-only runs.")
        st.caption(("🟢 GlassDollar API key detected — live company data."
                    if gd_key_active else
                    "🟡 No GLASSDOLLAR_API_KEY — set one to load companies from the GlassDollar API."))
        has_key = bool(core.openai_api_key())
        st.caption(("🟢 OpenAI key detected — full AI reasoning."
                    if has_key else "🟡 No OPENAI_API_KEY — running free offline fallback."))
        st.divider()
        st.caption("Set the keys once per session:")
        st.code('$env:GLASSDOLLAR_API_KEY = "..."\n$env:OPENAI_API_KEY = "sk-..."', language="powershell")


RIBBON_STEPS = ["INPUT", "ENRICH", "VERIFY", "STRUCTURE", "SCORE", "REVIEW", "ROUTE"]


def _ribbon_html(done=None, active=None) -> str:
    """Build the pipeline stepper HTML, highlighting completed and in-progress steps."""
    done = done or set()
    chips = []
    for i, s in enumerate(RIBBON_STEPS):
        cls = "ribbon-step"
        if s in done:
            cls += " ribbon-step--done"
        elif s == active:
            cls += " ribbon-step--active"
        chips.append(f"<span class='{cls}'>{s}</span>")
        if i < len(RIBBON_STEPS) - 1:
            chips.append("<span class='ribbon-arrow'>→</span>")
    return f"<div class='ribbon'>{''.join(chips)}</div>"


_ribbon_slot = st.empty()
_ribbon_slot.markdown(_ribbon_html(), unsafe_allow_html=True)
_pipeline_status_slot = st.empty()
_pipeline_status_slot.markdown(
    "<span class='muted'>Idle — evaluate a startup to watch each pipeline stage light up live.</span>",
    unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=1800)
def _search_glassdollar_cached(query: str, key_sig: str) -> pd.DataFrame:
    # key_sig makes the cache reload when the active API key changes.
    return core.search_glassdollar(query, limit=10)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_xlsx_cached(path: str) -> pd.DataFrame:
    """Load the local GlassDollar applications Excel; cached for 1 hour."""
    import os as _os
    if not path or not _os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_excel(path).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _evaluate_cached(query: str, tools_path: str, do_web: bool, df, on_step=None):
    return core.evaluate(query, None, tools_path, do_web=do_web, df=df, on_step=on_step)


# ------------------------------------------------ Solve a problem (problem -> startups)
with st.expander("🧩 Solve a problem — describe a challenge, get matching startups", expanded=False):
    _prob = st.text_area("What problem should be solved?", key="solve_problem_text",
                         placeholder="e.g. We need predictive maintenance for legacy PLCs on our shop floor",
                         height=80)
    s1, s2 = st.columns([1, 3])
    with s1:
        _solve_run = st.button("Find startups", type="primary", use_container_width=True)
    with s2:
        from core.solve import load_challenges
        _nch = len(load_challenges())
        st.caption(f"Challenge library: {_nch} recorded problem{'s' if _nch != 1 else ''} "
                   "— every question you ask is saved and sharpens future fit scoring.")
    if _solve_run and _prob.strip():
        from core.solve import solve_problem

        @st.cache_data(show_spinner=False, ttl=1800)
        def _load_applications_xlsx(path: str):
            # local Siemens applications file — searched ONLY in problem mode
            import os as _os
            if not path or not _os.path.exists(path):
                return None
            _df_apps = pd.read_excel(path).fillna("")
            _df_apps.columns = [str(c).strip() for c in _df_apps.columns]
            return _df_apps

        with st.spinner("Deriving capabilities and searching for solver startups…"):
            st.session_state["solve_result"] = solve_problem(
                _prob, llm=core.LLMClient(), do_web=True, use_glassdollar=bool(gd_key_active),
                local_df=_load_applications_xlsx(core.DEFAULT_GLASSDOLLAR))
    elif _solve_run:
        st.warning("Describe the problem first.")

    _sr = st.session_state.get("solve_result")
    if _sr and _sr.get("candidates"):
        st.markdown("**Capability search terms:** " +
                    " ".join(f"<span class='tag-chip'>{k}</span>" for k in _sr["keywords"]),
                    unsafe_allow_html=True)
        for i, c in enumerate(_sr["candidates"]):
            cc1, cc2, cc3 = st.columns([3, 1, 1])
            with cc1:
                _src = ("🗄 GlassDollar" if c["source"] == "glassdollar"
                        else "📄 Applications" if c["source"] == "applications"
                        else "🌐 Web")
                st.markdown(f"**{c['name']}** <span class='badge'>{_src}</span><br>"
                            f"<span class='muted'>{c.get('rationale') or c.get('description','')}</span>",
                            unsafe_allow_html=True)
            with cc2:
                st.progress(min(1.0, c.get("relevance", 0) / 100.0),
                            text=f"{c.get('relevance', 0)}")
            with cc3:
                if st.button("Evaluate →", key=f"solve_eval_{i}", use_container_width=True):
                    st.session_state["solve_eval_request"] = c["name"]
                    st.rerun()
    elif _sr is not None:
        st.caption("No credible solver startups found — try rephrasing the problem.")

# a "Evaluate →" click from the solve panel triggers a full pipeline run on that startup
_solve_req = st.session_state.pop("solve_eval_request", None)

# startup picker
_gd_key_sig = hashlib.sha256((gd_key_active or "").encode()).hexdigest()[:12] if gd_key_active else ""

col_a, col_b = st.columns([3, 1])
with col_a:
    typed = st.text_input("Startup name", placeholder="e.g. Celonis")

# Search both the local xlsx and the GlassDollar API for matches while the user types.
_xlsx_df = _load_xlsx_cached(core.DEFAULT_GLASSDOLLAR)
_xlsx_name_col = ("company_name" if not _xlsx_df.empty and "company_name" in _xlsx_df.columns
                  else (_xlsx_df.columns[0] if not _xlsx_df.empty else "company_name"))

_df_api = None
names: list = []
_name_source: dict = {}  # name -> "xlsx" | "api"

if typed.strip() and len(typed.strip()) >= 2:
    q_low = typed.strip().lower()
    # 1. local xlsx — fast substring match, no API key needed
    if not _xlsx_df.empty:
        _mask = _xlsx_df[_xlsx_name_col].astype(str).str.lower().str.contains(q_low, na=False)
        for n in _xlsx_df[_mask].head(10)[_xlsx_name_col].astype(str).tolist():
            if n.strip() and n.strip() not in _name_source:
                names.append(n.strip())
                _name_source[n.strip()] = "xlsx"
    # 2. GlassDollar API — live search (only when key is set)
    if gd_key_active:
        try:
            _df_api = _search_glassdollar_cached(typed.strip(), _gd_key_sig)
            for n in _df_api.get("company_name", pd.Series(dtype=str)).astype(str).tolist():
                if n.strip() and n.strip() not in _name_source:
                    names.append(n.strip())
                    _name_source[n.strip()] = "api"
        except Exception as e:
            _df_api = None
            st.error(f"GlassDollar search failed: {e}")
elif not gd_key_active and _xlsx_df.empty:
    st.warning("No GlassDollar API key set and no local xlsx found — add a key under ⚙ Settings or place glassdollar_applications.xlsx in the data folder.")

with col_b:
    picked = st.selectbox("…matches", [""] + names) if names else ""

# Resolve selected name to the correct source DataFrame
_df = None
if picked:
    if _name_source.get(picked) == "xlsx" and not _xlsx_df.empty:
        _df = _xlsx_df[_xlsx_df[_xlsx_name_col].astype(str) == picked].reset_index(drop=True)
    elif _df_api is not None:
        _df = _df_api[_df_api["company_name"].astype(str) == picked].reset_index(drop=True)
query = (picked or typed).strip()
run = st.button("Evaluate", type="primary", use_container_width=True)
if _solve_req:                      # forwarded from the Solve-a-problem panel
    query, run, _df = _solve_req, True, None


def metric_bar(label, val):
    st.markdown(f"<div class='kv'>{label}</div>", unsafe_allow_html=True)
    st.progress(min(1.0, val / 100.0), text=f"{val:.0f}")


if run and query:
    _done_steps: set = set()

    def _on_step(label: str, status: str) -> None:
        # Fired from core.evaluate() on the main script thread, so it can safely
        # drive the ribbon + status placeholders live as each stage progresses.
        if status == "running":
            _ribbon_slot.markdown(_ribbon_html(_done_steps, active=label), unsafe_allow_html=True)
            _pipeline_status_slot.markdown(
                f"<span class='badge-preview'>Running</span> "
                f"<span class='muted'>{label.title()} in progress…</span>",
                unsafe_allow_html=True)
        elif status == "done":
            _done_steps.add(label)
            _ribbon_slot.markdown(_ribbon_html(_done_steps), unsafe_allow_html=True)
        elif status == "error":
            _pipeline_status_slot.markdown(
                f"<span style='color:var(--ix-alarm);font-weight:700'>⚑ {label} failed</span>",
                unsafe_allow_html=True)

    with st.spinner(f"Evaluating {query}…"):
        _res = _evaluate_cached(query, tools_path, do_web, _df, on_step=_on_step)

    if not _res.get("found"):
        st.session_state.pop("last_result", None)
        st.warning(f"No match for “{query}” — not in the database and the web search returned nothing. "
                   f"Try the exact company name or check your connection.")
        st.stop()

    _ribbon_slot.markdown(_ribbon_html(set(RIBBON_STEPS)), unsafe_allow_html=True)
    _pipeline_status_slot.markdown(
        f"<span class='status-chip status-chip--ok'>Complete</span> "
        f"<span class='muted'>Evaluated {_res['company']} through all {len(RIBBON_STEPS)} stages.</span>",
        unsafe_allow_html=True)

    st.session_state["last_result"] = _res
    st.session_state["active_run"] = _res["company"]
    st.session_state.runs[_res["company"]] = _res
elif run:
    st.warning("Type or pick a startup name first.")


def render_ask_tab():
    """The 'Ask for more' multi-source chat. Renders regardless of whether an
    evaluation result is currently active — it can run source-only."""
    st.markdown("#### 💬 Ask for more")

    if "chat" not in st.session_state:
        st.session_state.chat = []          # list of {role, text, source, evidence}

    last_company = st.session_state.get("last_company", "")
    last_context = st.session_state.get("last_context", "")
    st.caption("Answers combine AI knowledge with a targeted web check: the AI drafts and picks "
               "the exact search queries, DuckDuckGo fetches evidence, and the AI refines the "
               "answer against it — one combined, cited response.")
    if last_company:
        scope = st.checkbox(f"Build on {last_company}", value=True,
                            help="Ground answers in the startup you just evaluated (its profile, score, customers and Siemens fit).")
    else:
        scope = False

    q = st.chat_input("Ask anything about a startup or the market…")
    if q:
        ctx_company = last_company if scope else ""
        ctx_brief = last_context if scope else ""
        llm = st.session_state.get("chat_llm") or core.LLMClient()
        st.session_state.chat_llm = llm
        with st.spinner("Drafting, searching the web, refining…"):
            resp = core.chat_smart(q, llm=llm, context_company=ctx_company, context_brief=ctx_brief)
        st.session_state.chat.append({"role": "user", "text": q, "source": "", "evidence": []})
        st.session_state.chat.append({"role": "assistant", "text": resp["answer"],
                                      "source": resp["source"], "evidence": resp.get("evidence", [])})

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            if m["role"] == "assistant":
                st.caption(f"source: {m['source']}")
            st.markdown(m["text"])
            if m.get("evidence"):
                with st.expander("Sources"):
                    for e in m["evidence"]:
                        snip = (e.get("snippet", "") or "")[:160]
                        if e.get("url"):
                            st.markdown(f"- [{e.get('title') or e['url']}]({e['url']}) — {snip}")
                        else:
                            st.markdown(f"- **{e.get('title','')}** — {snip}")

    if st.session_state.chat:
        if st.button("Clear chat", type="secondary"):
            st.session_state.chat = []
            st.rerun()


def _status_chip(status: str) -> str:
    cls = {"verified": "status-chip--ok", "partial": "status-chip--warn",
           "unverified": "status-chip--neutral", "contradicted": "status-chip--alarm"}.get(status, "status-chip--neutral")
    label = {"verified": "Verified", "partial": "Partial",
             "unverified": "Unverified", "contradicted": "Contradicted"}.get(status, status or "—")
    return f"<span class='status-chip {cls}'>{label}</span>"


def render_result(res):
    """Persistent result header + tabbed content for the active evaluation.
    Guarded to still show a usable Ask tab when there is no active result."""

    if res:
        st.session_state["last_company"] = res["company"]
        rt, sc, fit = res["routing"], res["score"], res["fit"]
        color = PILLAR_COLORS.get(rt["pillar"], IX["neutral"])

        # ---- build a compact brief so the chat below can build on this search
        p = res["profile"]
        _cust = p.get("customers") or p.get("Reference customers") or "—"
        _tools = (", ".join(m["tool"] for m in fit.get("matches", [])[:5])
                  if fit.get("aligned") and fit.get("matches") else "none")
        st.session_state["last_context"] = (
            f"Company: {res['company']}\n"
            f"Summary: {res.get('summary','')}\n"
            f"HQ: {p.get('hq','—')} | Funding: {p.get('funding','—')} | "
            f"Stage: {p.get('Development stage of your solution','—')}\n"
            f"Customers: {_cust}\n"
            f"Final score: {sc['final_score']:.0f} | Routing: {rt['pillar']} "
            f"(confidence {rt['confidence']:.0%})\n"
            f"Siemens fit tools: {_tools}"
        )

        # ---- persistent hero band (always visible, above the tabs):
        # col1 = final-score gauge, col2 = company + summary, col3 = routing verdict + why-panel
        hero1, hero2, hero3 = st.columns([1, 2, 2])
        with hero1:
            st.plotly_chart(make_gauge(sc["final_score"], rt["pillar"]),
                            use_container_width=True, config={"displayModeBar": False})
            st.markdown("<div class='kv' style='text-align:center'>Final score</div>", unsafe_allow_html=True)
        with hero2:
            st.subheader(res["company"])
            st.markdown(f"<span class='badge'>engine: {res['engine']}</span>", unsafe_allow_html=True)
            st.markdown(f"<div class='card card--accent'>{res['summary']}</div>", unsafe_allow_html=True)
        with hero3:
            _pills = f"<span class='pill' style='background:{color}'>{rt['pillar']}</span>"
            for _sp in rt.get("secondary", []):
                _sc2 = PILLAR_COLORS.get(_sp, IX["neutral"])
                _pills += f" <span class='pill' style='background:{_sc2};opacity:.75'>+ {_sp}</span>"
            if rt.get("sfs_relevant"):
                _pills += (" <span class='pill' style='background:#8a6d1a' "
                           f"title=\"{rt.get('sfs_rationale','')}\">💶 SFS financing</span>")
            st.markdown(f"<div class='kv'>Routing</div>{_pills}"
                        f"<div class='muted'>confidence {rt['confidence']:.0%}</div>", unsafe_allow_html=True)
            _verdict = "<div class='verdict'><div class='kv'>Why this routing</div>"
            for r in rt.get("reasons", [])[:2]:
                _verdict += f"<div class='verdict-reason'>{r}</div>"
            for r in rt.get("risks", [])[:1]:
                _verdict += f"<div class='verdict-risk'>{r}</div>"
            _verdict += "</div>"
            st.markdown(_verdict, unsafe_allow_html=True)

        if res.get("source") == "web":
            st.info(f"“{res['company']}” isn't in the GlassDollar database — this profile was assembled "
                    f"live from the web, so treat the figures as provisional and verify before relying on them.")
        st.caption("Details below are split across tabs — open Ask to chat about this startup.")

    tab_overview, tab_scoring, tab_market, tab_evidence, tab_ask = st.tabs(
        ["Overview", "Scoring & Fit", "Market & Risk", "Evidence", "Ask"])

    if not res:
        placeholder = "Evaluate a startup to see its Overview, Scoring, Market and Evidence."
        with tab_overview:
            st.info(placeholder)
        with tab_scoring:
            st.info(placeholder)
        with tab_market:
            st.info(placeholder)
        with tab_evidence:
            st.info(placeholder)
        with tab_ask:
            render_ask_tab()
        return

    p = res["profile"]
    rt, sc, fit = res["routing"], res["score"], res["fit"]

    # ---------------------------------------------------------------- Overview
    with tab_overview:
        import html as _html

        def _esc(v):
            return _html.escape(str(v).strip()) if v and str(v).strip() else ""

        def _link_html(url):
            u = _esc(url)
            if not u:
                return ""
            label = u.replace("https://", "").replace("http://", "").rstrip("/")
            return f"<a href='{u}' target='_blank'>{label}</a>"

        def _spec_row(icon, key, value_html):
            cls = "spec-v" if value_html else "spec-v empty"
            shown = value_html or "—"
            return (f"<div class='spec-row'><div class='spec-k'>{icon} {key}</div>"
                    f"<div class='{cls}'>{shown}</div></div>")

        # --- KPI chip row: small, uniform, glanceable (no oversized boxes) ---
        _emp = _esc(p.get("employees_count") or p.get("employee_band"))
        _founded = _esc(p.get("founded_year"))
        kpis = [
            ("👥", "Employees", _emp or "—", ""),
            ("📅", "Founded", _founded or "—", ""),
            ("📊", "Completeness", f"{sc['data_completeness']:.0%}", "of profile filled"),
            ("📈", "Traction", f"{sc['effective_traction']}", "effective"),
            ("🎯", "Routed to", rt["pillar"], f"{rt['confidence']:.0%} confidence"),
        ]
        kpi_html = "".join(
            f"<div class='kpi'><div class='kpi-k'>{ic} {k}</div>"
            f"<div class='kpi-v'>{_html.escape(str(v))}</div>"
            + (f"<div class='kpi-sub'>{sub}</div>" if sub else "")
            + "</div>"
            for ic, k, v, sub in kpis
        )
        st.markdown(f"<div class='kpi-row'>{kpi_html}</div>", unsafe_allow_html=True)

        # --- Profile spec list: dense label/value rows in one card ---------
        st.markdown("<div class='section-label'>Profile</div>", unsafe_allow_html=True)
        spec_rows = [
            _spec_row("📍", "Headquarters", _esc(p.get("hq"))),
            _spec_row("🏷️", "Stage", _esc(p.get("Development stage of your solution"))),
            _spec_row("🧩", "Business model", _esc(p.get("Business model"))),
            _spec_row("💰", "Funding", _esc(p.get("funding"))),
            _spec_row("🌐", "Website", _link_html(p.get("website"))),
            _spec_row("in", "LinkedIn", _link_html(p.get("linkedin_url"))),
        ]
        st.markdown(f"<div class='spec-card'>{''.join(spec_rows)}</div>", unsafe_allow_html=True)

        # --- Team & Ecosystem: founders / advisors / programs / parent group ---
        dp = res.get("deep_profile") or {}
        _founders = [f for f in dp.get("founders", []) if isinstance(f, dict) and f.get("name")]
        _advisors = [a for a in dp.get("advisors", []) if isinstance(a, dict) and a.get("name")]
        _programs = [x for x in dp.get("programs", []) if isinstance(x, dict) and x.get("name")]
        _parent = str(dp.get("parent_group", "")).strip()
        if _founders or _advisors or _programs or _parent:
            st.markdown("<div class='section-label'>Team &amp; Ecosystem</div>", unsafe_allow_html=True)
            team_rows = []
            for f in _founders:
                _v = _esc(f"{f.get('name')} — {f.get('role','') or 'founder'}")
                if f.get("linkedin"):
                    _v += f" · {_link_html(f['linkedin'])}"
                if str(f.get("background", "")).strip():
                    _v += f"<div class='muted'>{_esc(f['background'])}</div>"
                team_rows.append(_spec_row("🧑‍💼", "Founder", _v))
            for a in _advisors:
                team_rows.append(_spec_row("🎓", "Advisor",
                    _esc(f"{a.get('name')} — {a.get('role','') or 'advisor'}"
                         + (f", {a['affiliation']}" if a.get('affiliation') else ""))))
            if _parent:
                team_rows.append(_spec_row("🏢", "Part of group", _esc(_parent)))
            if dp.get("employees"):
                team_rows.append(_spec_row("👥", "Employees (researched)", _esc(dp["employees"])))
            st.markdown(f"<div class='spec-card'>{''.join(team_rows)}</div>", unsafe_allow_html=True)
            if _programs:
                chips = "".join(
                    f"<span class='tag-chip' title='{_esc(x.get('type',''))}'>🚀 {_esc(x.get('name'))}</span>"
                    for x in _programs)
                st.markdown(f"<div class='tag-wrap'>{chips}</div>", unsafe_allow_html=True)

        # --- Reference customers as tag chips (was a dense wall / bullets) --
        _cust_raw = (", ".join(dp.get("reference_customers", []))
                     or p.get("customers") or p.get("Reference customers") or "")
        _cust_parts = [x.strip() for x in re.split(r"[,\n;·|]+", str(_cust_raw)) if x.strip()]
        st.markdown("<div class='section-label'>Reference customers</div>", unsafe_allow_html=True)
        if _cust_parts:
            chips = "".join(f"<span class='tag-chip'>{_html.escape(c)}</span>" for c in _cust_parts)
            st.markdown(f"<div class='tag-wrap'>{chips}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='muted'>No reference customers on record.</span>", unsafe_allow_html=True)

        st.divider()
        st.markdown("##### Download")
        top_tool = fit["matches"][0]["tool"] if fit.get("aligned") and fit.get("matches") else "—"
        dims_df = pd.DataFrame([{"field": f"score_{k}", "value": v} for k, v in sc["dimensions"].items()])
        profile_df = pd.DataFrame([{"field": k, "value": v} for k, v in p.items()])
        export_df = pd.concat([dims_df, profile_df], ignore_index=True)
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        json_bytes = json.dumps(res, default=str).encode("utf-8")
        md_summary = (
            f"# {res['company']}\n\n"
            f"{res.get('summary','')}\n\n"
            f"**Final score:** {sc['final_score']:.0f}\n\n"
            f"**Routing:** {rt['pillar']} (confidence {rt['confidence']:.0%})\n\n"
            f"**Top Siemens tool:** {top_tool}\n"
        )
        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button("CSV (scores + profile)", data=csv_bytes,
                               file_name=f"{res['company']}_scores.csv", mime="text/csv",
                               use_container_width=True)
        with d2:
            st.download_button("JSON (full result)", data=json_bytes,
                               file_name=f"{res['company']}_result.json", mime="application/json",
                               use_container_width=True)
        with d3:
            st.download_button("Markdown summary", data=md_summary.encode("utf-8"),
                               file_name=f"{res['company']}_summary.md", mime="text/markdown",
                               use_container_width=True)

    # ---------------------------------------------------------- Scoring & Fit
    with tab_scoring:
        st.markdown("#### Score radar")
        st.plotly_chart(make_radar(sc["dimensions"]), use_container_width=True,
                        config={"displayModeBar": False})

        left, right = st.columns(2)

        with left:
            st.markdown("#### Score breakdown")
            labels = {"traction": "Traction (28%)", "siemens_fit": "Siemens Fit (27%)",
                      "product": "Product (15%)", "market": "Market (12%)",
                      "founder": "Founder (10%)", "ecosystem": "Ecosystem (8%)"}
            for k, lab in labels.items():
                metric_bar(lab, sc["dimensions"][k])
            st.caption(f"Raw {sc['raw_score']} × DataConfidence {sc['data_confidence']} "
                       f"(completeness {sc['data_completeness']:.0%}) = **{sc['final_score']:.0f}**. "
                       f"Effective traction {sc['effective_traction']} "
                       f"(verified {sc['verified_customers']} / unverified {sc['unverified_customers']}).")

        with right:
            st.markdown("#### Siemens portfolio fit")
            if fit.get("aligned") and fit.get("matches"):
                for m in fit["matches"]:
                    st.markdown(
                        f"<div class='card card--accent'><span class='toolname'>{m['tool']}</span> "
                        f"<span class='badge'>{m.get('division','')}</span> "
                        f"<span style='float:right;font-weight:700'>{float(m['confidence']):.0f}%</span>"
                        f"<div class='muted'>{m.get('rationale','')}</div></div>", unsafe_allow_html=True)
            else:
                st.info("**Not aligned with the current Siemens software portfolio.** "
                        "No tool met the fit threshold — routed to Pass.")
            st.caption(f"Match method: {fit.get('method','—')}")

        st.markdown("#### Routing rationale")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.markdown("**Reasons**")
            for r in rt["reasons"]:
                st.markdown(f"- {r}")
        with rc2:
            st.markdown("**Risks**")
            for r in rt["risks"]:
                st.markdown(f"- {r}")

    # -------------------------------------------------------- Market & Risk
    with tab_market:
        trend = res.get("trend", {})
        if trend and trend.get("method") != "disabled":
            st.markdown("#### 🌐 Market trend")
            t_label    = trend.get("label", "—")
            t_color    = trend.get("color", IX["neutral"])
            t_momentum = trend.get("momentum", 0)
            t_niche    = trend.get("niche", "")
            t_summary  = trend.get("summary", "")
            t_signals  = trend.get("signals", [])
            t_evidence = trend.get("evidence", [])
            t_method   = trend.get("method", "—")

            tc1, tc2 = st.columns([1, 3])
            with tc1:
                st.markdown(
                    f"<div style='background:{t_color}22;border-left:3px solid {t_color};"
                    f"border-radius:var(--ix-radius);padding:12px 16px;'>"
                    f"<div style='font-size:22px;font-weight:800;color:{t_color}'>{t_label}</div>"
                    f"<div style='color:var(--ix-soft);font-size:13px;margin-top:4px'>Momentum</div>"
                    f"<div style='font-size:32px;font-weight:800;color:{t_color}'>{t_momentum}</div>"
                    f"<div style='color:var(--ix-soft);font-size:11px'>/ 100</div>"
                    f"</div>", unsafe_allow_html=True)
            with tc2:
                if t_niche:
                    st.caption(f"Niche: **{t_niche}**  ·  data: {t_method}")
                st.progress(min(1.0, t_momentum / 100), text="")
                if t_summary:
                    st.markdown(f"<div class='card'>{t_summary}</div>", unsafe_allow_html=True)
                if t_signals:
                    st.markdown("**Key signals:**")
                    for sig in t_signals:
                        st.markdown(f"- {sig}")

            if t_evidence:
                with st.expander(f"Trend sources ({len(t_evidence)} results)"):
                    for e in t_evidence:
                        snip = (e.get("snippet", "") or "")[:160]
                        if e.get("url"):
                            st.markdown(f"- [{e.get('title') or e['url']}]({e['url']}) — {snip}")
                        else:
                            st.markdown(f"- {e.get('title','')} — {snip}")

        # ---- claim verification (LLM-confirmed against web evidence)
        ver = res.get("verification", {})
        if ver.get("claims"):
            st.markdown("#### Claim verification")
            st.caption(f"Each self-reported claim confirmed against web evidence · method: {ver.get('method','—')}")
            _table = ("<table style='width:100%;border-collapse:collapse'><tr>" +
                      "".join(f"<th class='kv' style='text-align:left;padding:6px 8px'>{h}</th>"
                              for h in ["Field", "Claim", "Status", "Confidence", "Evidence", "Note"]) +
                      "</tr>")
            for c in ver["claims"]:
                ev_url = c.get("evidence_url", "")
                ev_html = f"<a href='{ev_url}' target='_blank'>source</a>" if ev_url else "—"
                _table += (
                    "<tr style='border-top:1px solid var(--ix-weak-bdr)'>"
                    f"<td style='padding:6px 8px' class='kvv'>{c.get('field','')}</td>"
                    f"<td style='padding:6px 8px' class='muted'>{str(c.get('value'))[:60]}</td>"
                    f"<td style='padding:6px 8px'>{_status_chip(c.get('status',''))}</td>"
                    f"<td style='padding:6px 8px' class='muted'>{c.get('confidence','')}</td>"
                    f"<td style='padding:6px 8px' class='muted'>{ev_html}</td>"
                    f"<td style='padding:6px 8px' class='muted'>{c.get('note','')}</td>"
                    "</tr>"
                )
            _table += "</table>"
            st.markdown(_table, unsafe_allow_html=True)
            for rf in ver.get("red_flags", []):
                st.markdown(f"<span style='color:var(--ix-alarm);font-weight:600'>⚑ {rf}</span>", unsafe_allow_html=True)

    # ------------------------------------------------------------- Evidence
    with tab_evidence:
        st.markdown("#### Evidence & provenance")
        st.caption("Every enriched fact, one click to source.")
        rows = []
        for f in res["facts"]:
            rows.append({"fact": f["key"], "value": str(f["value"])[:80], "method": f["method"],
                         "verified": "✅" if f["verified"] else "🟡",
                         "confidence": f["confidence"], "source": f["source_url"],
                         "retrieved_at": f["retrieved_at"]})
        if rows:
            ev_df = pd.DataFrame(rows)
            filter_q = st.text_input("Filter facts", key="evidence_filter",
                                     placeholder="Search fact, value or source…")
            if filter_q:
                q_low = filter_q.lower()
                mask = (ev_df["fact"].astype(str).str.lower().str.contains(q_low, na=False) |
                        ev_df["value"].astype(str).str.lower().str.contains(q_low, na=False) |
                        ev_df["source"].astype(str).str.lower().str.contains(q_low, na=False))
                ev_df = ev_df[mask]
            st.dataframe(ev_df, use_container_width=True,
                         column_config={"source": st.column_config.LinkColumn("source")})
        else:
            st.caption("No enrichment facts (web enrichment was off or returned nothing).")

        with st.expander("Raw result JSON (debug)"):
            st.json(res)

    # ----------------------------------------------------------------- Ask
    with tab_ask:
        render_ask_tab()


def render_portfolio():
    """Sortable table of every run evaluated in this session. SAMPLE_RESULT never appears here."""
    st.markdown("### 📊 Portfolio")
    if not st.session_state.runs:
        st.info("No evaluated runs yet — evaluate a startup to populate the portfolio.")
        return

    rows = []
    for name, r in st.session_state.runs.items():
        rt, sc, fit = r["routing"], r["score"], r["fit"]
        top_tool = fit["matches"][0]["tool"] if fit.get("aligned") and fit.get("matches") else "—"
        trend = r.get("trend", {})
        rows.append({
            "company": name,
            "final_score": sc["final_score"],
            "pillar": rt["pillar"],
            "top_siemens_tool": top_tool,
            "momentum": trend.get("momentum", "—"),
            "engine": r.get("engine", "—"),
        })
    pf_df = pd.DataFrame(rows).sort_values("final_score", ascending=False).reset_index(drop=True)

    def _pillar_style(v):
        return f"color:{PILLAR_COLORS.get(v, IX['neutral'])};font-weight:700"

    st.dataframe(pf_df.style.map(_pillar_style, subset=["pillar"]),
                 use_container_width=True, hide_index=True)

    st.caption("Reload a run as the active result:")
    pcol1, pcol2 = st.columns([3, 1])
    with pcol1:
        reload_choice = st.selectbox("Run", [""] + list(pf_df["company"]),
                                     key="portfolio_reload", label_visibility="collapsed")
    with pcol2:
        if st.button("Load", key="portfolio_load_btn", use_container_width=True, disabled=not reload_choice):
            st.session_state["last_result"] = st.session_state.runs[reload_choice]
            st.session_state["active_run"] = reload_choice
            st.rerun()


# ---- Portfolio (gated by sidebar toggle, rendered above the tabs)
if st.session_state.show_portfolio:
    render_portfolio()
    st.divider()

# ---- Compare selected runs (sidebar multiselect drives this, rendered above the tabs)
if len(compare_selection) >= 2:
    with st.expander("Compare selected", expanded=True):
        st.plotly_chart(make_radar_overlay(st.session_state.runs, compare_selection),
                        use_container_width=True, config={"displayModeBar": False})
        ccols = st.columns(len(compare_selection))
        for ccol, cname in zip(ccols, compare_selection):
            cres = st.session_state.runs.get(cname)
            if not cres:
                continue
            with ccol:
                crt, csc, cfit = cres["routing"], cres["score"], cres["fit"]
                ctrend = cres.get("trend", {})
                ccolor = PILLAR_COLORS.get(crt["pillar"], IX["neutral"])
                ctop_tool = (cfit["matches"][0]["tool"]
                             if cfit.get("aligned") and cfit.get("matches") else "—")
                st.markdown(f"**{cname}**")
                st.markdown(f"<div class='kv'>Final score</div><div class='metric-xl'>{csc['final_score']:.0f}</div>",
                            unsafe_allow_html=True)
                st.markdown(f"<span class='pill' style='background:{ccolor}'>{crt['pillar']}</span>",
                            unsafe_allow_html=True)
                st.markdown(f"<div class='kv'>Top Siemens tool</div><div class='kvv'>{ctop_tool}</div>",
                            unsafe_allow_html=True)
                st.markdown(f"<div class='kv'>Momentum / trend</div>"
                            f"<div class='kvv'>{ctrend.get('label','—')} ({ctrend.get('momentum', 0)})</div>",
                            unsafe_allow_html=True)

# ---- Sample preview mode banner + render (SAMPLE_RESULT never touches runs/last_result)
if st.session_state.sample_mode:
    st.markdown("<span class='badge-preview'>Preview — sample data, not a live evaluation</span>",
                unsafe_allow_html=True)
    _display_res = SAMPLE_RESULT
else:
    _display_res = st.session_state.get("last_result")

render_result(_display_res)