"""
ui/theme.py - Design system tokens, WCAG 2.2 AA contrast rules, and control-room styling.
"""

from __future__ import annotations
import streamlit as st

# ==============================================================================
# Color Palette Tokens & Dual Visual Encodings (WCAG 2.2 Success Criterion 1.4.1)
# ==============================================================================

SURFACES = {
    "bg_app": "#08111F",       # Base dark navy canvas
    "bg_sidebar": "#0D1829",   # Elevated sidebar container
    "card": "#111C2E",         # Surface 1 card background
    "card_alt": "#16233B",     # Surface 2 alternate/nested card
    "border": "#25334A",       # Subtle card & component border
    "border_focus": "#38BDF8", # Active focus ring border
    "border_alert": "#FB7185", # High alert border
}

TEXT_COLORS = {
    "primary": "#F8FAFC",      # High contrast body/titles (Contrast > 14:1)
    "secondary": "#94A3B8",    # Supporting metadata (Contrast > 5.5:1)
    "muted": "#64748B",        # Captions & inactive tabs (Contrast > 3.5:1)
    "accent": "#38BDF8",       # Sky blue highlight
}

# Line Encoding: ALWAYS pair color with explicit text tag [ALP] / [BET]
LINE_THEME = {
    "ALP": {
        "color": "#22D3EE",
        "bg": "rgba(34, 211, 238, 0.15)",
        "border": "rgba(34, 211, 238, 0.5)",
        "text_tag": "[ALP] Alpha Line",
        "icon": "🔵",
    },
    "BET": {
        "color": "#A78BFA",
        "bg": "rgba(167, 139, 250, 0.15)",
        "border": "rgba(167, 139, 250, 0.5)",
        "text_tag": "[BET] Beta Line",
        "icon": "🟣",
    },
}

# Operational States: ALWAYS pair color with icon + text badge
STATUS_THEME = {
    "FEASIBLE": {
        "color": "#34D399",
        "bg": "rgba(52, 211, 153, 0.15)",
        "border": "#34D399",
        "text": "100% FEASIBLE",
        "icon": "✓",
    },
    "BREACH": {
        "color": "#FB7185",
        "bg": "rgba(251, 113, 133, 0.2)",
        "border": "#FB7185",
        "text": "VIOLATION DETECTED",
        "icon": "✕",
    },
    "ON_TIME": {
        "color": "#34D399",
        "bg": "rgba(52, 211, 153, 0.15)",
        "border": "#34D399",
        "text": "ON-TIME",
        "icon": "✓",
    },
    "OVERRUN": {
        "color": "#FB7185",
        "bg": "rgba(251, 113, 133, 0.2)",
        "border": "#FB7185",
        "text": "OVERRUN",
        "icon": "⚠️",
    },
    "ECLO": {
        "color": "#F59E0B",
        "bg": "rgba(245, 158, 11, 0.18)",
        "border": "#F59E0B",
        "text": "ECLO EXTENDED",
        "icon": "⚡",
    },
    "EXCESS": {
        "color": "#E11D48",
        "bg": "rgba(225, 29, 72, 0.25)",
        "border": "#E11D48",
        "text": "OVER-CAPACITY EXCESS",
        "icon": "⚠️",
    },
}

# Closure Footprint Dual Encoding (Color + Shape/Style + Text)
CLOSURE_THEME = {
    "direct": {
        "color": "#38BDF8",
        "line_style": "solid",
        "symbol": "square",
        "label": "[DIRECT] Active Work Span",
    },
    "buffer": {
        "color": "#FBBF24",
        "line_style": "dash",
        "symbol": "diamond",
        "label": "[BUFFER] Non-Live Safety Buffer",
    },
    "mirror": {
        "color": "#F43F5E",
        "line_style": "longdash",
        "symbol": "triangle-up",
        "label": "[MIRROR] Live Power Catenary Mirror",
    },
    "cross_line": {
        "color": "#C084FC",
        "line_style": "dot",
        "symbol": "circle",
        "label": "[CROSS-LINE] Crossover Catenary Isolation",
    },
}

# ==============================================================================
# Global CSS Injection
# ==============================================================================

CUSTOM_CSS = """
<style>
/* 1. Base Dark Control-Room Canvas */
.stApp {
    background-color: #08111F !important;
    color: #F8FAFC !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    overflow-x: hidden !important;
}

header[data-testid="stHeader"] {
    background-color: #08111F !important;
    border-bottom: 1px solid #1E293B;
}

/* 2. Responsive Sidebar with High Contrast */
section[data-testid="stSidebar"] {
    background-color: #0D1829 !important;
    border-right: 1px solid #1E293B !important;
}
section[data-testid="stSidebar"] h1, 
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3 {
    color: #38BDF8 !important;
    letter-spacing: 0.02em;
}

/* 3. Typography Scale & Heading Height Control */
h1 {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #F8FAFC !important;
    margin-bottom: 0.25rem !important;
    line-height: 1.25 !important;
}
h2 {
    font-size: 1.35rem !important;
    font-weight: 600 !important;
    color: #38BDF8 !important;
    margin-top: 1rem !important;
    margin-bottom: 0.5rem !important;
}
h3 {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: #F1F5F9 !important;
    margin-top: 0.75rem !important;
    margin-bottom: 0.4rem !important;
}
p, span, label {
    font-size: 0.92rem;
    color: #E2E8F0;
}

/* 4. Modular Control Room Card Components */
.cr-card {
    background: #111C2E;
    border: 1px solid #25334A;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25);
    transition: border-color 0.15s ease-in-out;
}
.cr-card:hover {
    border-color: #3B82F6;
}
.cr-card-header {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #94A3B8;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.cr-card-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: #F8FAFC;
    line-height: 1.2;
}
.cr-card-delta {
    font-size: 0.78rem;
    font-weight: 500;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 4px;
}

/* 5. Semantic Badges with Text & Icon Encodings */
.op-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 9px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
}
.badge-alp {
    background: rgba(34, 211, 238, 0.12);
    color: #22D3EE;
    border: 1px solid rgba(34, 211, 238, 0.45);
}
.badge-bet {
    background: rgba(167, 139, 250, 0.12);
    color: #A78BFA;
    border: 1px solid rgba(167, 139, 250, 0.45);
}
.badge-pass {
    background: rgba(52, 211, 153, 0.12);
    color: #34D399;
    border: 1px solid rgba(52, 211, 153, 0.45);
}
.badge-breach {
    background: rgba(251, 113, 133, 0.18);
    color: #FB7185;
    border: 1px solid rgba(251, 113, 133, 0.5);
}
.badge-eclo {
    background: rgba(245, 158, 11, 0.15);
    color: #FBBF24;
    border: 1px dashed rgba(245, 158, 11, 0.6);
}
.badge-excess {
    background: rgba(225, 29, 72, 0.22);
    color: #FDA4AF;
    border: 2px solid #E11D48;
}

/* 6. Form Controls & Button Visual Treatment */
button[kind="primary"] {
    background-color: #0284C7 !important;
    border: 1px solid #38BDF8 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}
button[kind="primary"]:hover {
    background-color: #0369A1 !important;
    border-color: #7DD3FC !important;
}
button[kind="secondary"] {
    background-color: #1E293B !important;
    border: 1px solid #334155 !important;
    color: #E2E8F0 !important;
    border-radius: 6px !important;
}
button[kind="secondary"]:hover {
    background-color: #334155 !important;
    border-color: #64748B !important;
}

/* Ensure disabled buttons remain readable and clearly styled */
button:disabled {
    background-color: #0F172A !important;
    border-color: #1E293B !important;
    color: #64748B !important;
    opacity: 0.6 !important;
    cursor: not-allowed !important;
}

/* 7. Tables & DataFrames */
div[data-testid="stDataFrame"] {
    border: 1px solid #25334A !important;
    border-radius: 6px !important;
}

/* 8. Container Width Clamping & Horizontal Overflow Prevention */
.block-container {
    padding-top: 3.5rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
}

/* Custom Operational Callout Box */
.op-callout {
    padding: 10px 14px;
    border-radius: 6px;
    margin: 8px 0;
    font-size: 0.88rem;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.op-callout-info {
    background: rgba(56, 189, 248, 0.1);
    border-left: 4px solid #38BDF8;
    color: #E0F2FE;
}
.op-callout-warning {
    background: rgba(245, 158, 11, 0.12);
    border-left: 4px solid #F59E0B;
    color: #FEF3C7;
}
.op-callout-success {
    background: rgba(52, 211, 153, 0.1);
    border-left: 4px solid #34D399;
    color: #D1FAE5;
}
</style>
"""

def inject_custom_theme():
    """Injects high-contrast control-room CSS and layout tokens."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
