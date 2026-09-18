"""
ui/theme.py - Design system tokens, WCAG 2.2 AA contrast rules, and control-room styling.
Light mode matching the executive possession timeline visualization.
"""

from __future__ import annotations
import streamlit as st

# ==============================================================================
# Color Palette Tokens & Dual Visual Encodings (WCAG 2.2 Success Criterion 1.4.1)
# ==============================================================================

SURFACES = {
    "bg_app": "#F8FAFC",       # Base clean light slate canvas
    "bg_sidebar": "#F1F5F9",   # Elevated sidebar container
    "card": "#FFFFFF",         # Surface 1 card background
    "card_alt": "#F8FAFC",     # Surface 2 alternate/nested card
    "border": "#E2E8F0",       # Subtle card & component border
    "border_focus": "#0066CC", # Active focus ring border
    "border_alert": "#EF4444", # High alert border
}

TEXT_COLORS = {
    "primary": "#0F172A",      # High contrast dark slate (Contrast > 14:1)
    "secondary": "#475569",    # Supporting metadata slate
    "muted": "#64748B",        # Captions & inactive tabs
    "accent": "#0066CC",       # Executive Blue highlight
}

# Qualitative Contract Palette (strictly matching the official timeline legend C001..C014)
CONTRACT_COLORS = {
    "C001": "#0066CC",  # Blue
    "C002": "#74B9FF",  # Sky Blue
    "C003": "#FF2D20",  # Bright Red
    "C004": "#FFA07A",  # Light Coral / Salmon
    "C005": "#00A88F",  # Teal / Emerald
    "C006": "#7BED9F",  # Mint Green
    "C007": "#F97316",  # Orange
    "C008": "#FBBF24",  # Yellow / Amber
    "C009": "#7C3AED",  # Purple
    "C010": "#CBD5E1",  # Soft Gray
    "C011": "#0052CC",  # Deep Royal Blue
    "C012": "#93C5FD",  # Baby Blue
    "C013": "#DC2626",  # Crimson Red
    "C014": "#FFB8B8",  # Rose Pink
}

# Line Encoding: ALWAYS pair color with explicit text tag [ALP] / [BET]
LINE_THEME = {
    "ALP": {
        "color": "#0284C7",
        "bg": "#E0F2FE",
        "border": "#7DD3FC",
        "text_tag": "[ALP] Alpha Line",
        "icon": "🔵",
    },
    "BET": {
        "color": "#7C3AED",
        "bg": "#EDE9FE",
        "border": "#C4B5FD",
        "text_tag": "[BET] Beta Line",
        "icon": "🟣",
    },
}

# Operational States: ALWAYS pair color with icon + text badge
STATUS_THEME = {
    "FEASIBLE": {
        "color": "#059669",
        "bg": "#ECFDF5",
        "border": "#10B981",
        "text": "100% FEASIBLE",
        "icon": "✓",
    },
    "BREACH": {
        "color": "#DC2626",
        "bg": "#FEF2F2",
        "border": "#EF4444",
        "text": "VIOLATION DETECTED",
        "icon": "✕",
    },
    "ON_TIME": {
        "color": "#059669",
        "bg": "#ECFDF5",
        "border": "#10B981",
        "text": "ON-TIME",
        "icon": "✓",
    },
    "OVERRUN": {
        "color": "#EA580C",
        "bg": "#FFF7ED",
        "border": "#F97316",
        "text": "OVERRUN",
        "icon": "⚠️",
    },
    "ECLO": {
        "color": "#D97706",
        "bg": "#FFFBEB",
        "border": "#F59E0B",
        "text": "ECLO EXTENDED",
        "icon": "⚡",
    },
    "EXCESS": {
        "color": "#E11D48",
        "bg": "#FFF1F2",
        "border": "#FB7185",
        "text": "OVER-CAPACITY EXCESS",
        "icon": "⚠️",
    },
}

# Closure Footprint Dual Encoding (Color + Shape/Style + Text)
CLOSURE_THEME = {
    "direct": {
        "color": "#0066CC",
        "line_style": "solid",
        "symbol": "square",
        "label": "[DIRECT] Active Work Span",
    },
    "buffer": {
        "color": "#F59E0B",
        "line_style": "dash",
        "symbol": "diamond",
        "label": "[BUFFER] Non-Live Safety Buffer",
    },
    "mirror": {
        "color": "#DC2626",
        "line_style": "longdash",
        "symbol": "triangle-up",
        "label": "[MIRROR] Live Power Catenary Mirror",
    },
    "cross_line": {
        "color": "#7C3AED",
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
/* 1. Base Light Canvas Matching Timeline Aesthetic */
.stApp {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    overflow-x: hidden !important;
}

header[data-testid="stHeader"] {
    background-color: #FFFFFF !important;
    border-bottom: 1px solid #E2E8F0;
}

/* 2. Responsive Sidebar with Crisp Contrast */
section[data-testid="stSidebar"] {
    background-color: #F1F5F9 !important;
    border-right: 1px solid #CBD5E1 !important;
}
section[data-testid="stSidebar"] h1, 
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3 {
    color: #0066CC !important;
    letter-spacing: 0.02em;
}

/* 3. Typography Scale & Heading Height Control */
h1 {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin-bottom: 0.25rem !important;
    line-height: 1.25 !important;
}
h2 {
    font-size: 1.35rem !important;
    font-weight: 600 !important;
    color: #0066CC !important;
    margin-top: 1rem !important;
    margin-bottom: 0.5rem !important;
}
h3 {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: #1E293B !important;
    margin-top: 0.75rem !important;
    margin-bottom: 0.4rem !important;
}
p, span, label {
    font-size: 0.92rem;
    color: #334155;
}

/* 4. Modular Control Room Card Components */
.cr-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    transition: all 0.15s ease-in-out;
}
.cr-card:hover {
    border-color: #0066CC;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08);
}
.cr-card-header {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #64748B;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.cr-card-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: #0F172A;
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
    background: #E0F2FE;
    color: #0284C7;
    border: 1px solid #BAE6FD;
}
.badge-bet {
    background: #EDE9FE;
    color: #7C3AED;
    border: 1px solid #DDD6FE;
}
.badge-pass {
    background: #ECFDF5;
    color: #059669;
    border: 1px solid #A7F3D0;
}
.badge-breach {
    background: #FEF2F2;
    color: #DC2626;
    border: 1px solid #FECACA;
}
.badge-eclo {
    background: #FFFBEB;
    color: #D97706;
    border: 1px dashed #FCD34D;
}
.badge-excess {
    background: #FFF1F2;
    color: #E11D48;
    border: 2px solid #FDA4AF;
}

/* 6. Form Controls & Button Visual Treatment */
button[kind="primary"] {
    background-color: #0066CC !important;
    border: 1px solid #0052CC !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}
button[kind="primary"]:hover {
    background-color: #0052CC !important;
    border-color: #003D99 !important;
}
button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    color: #1E293B !important;
    border-radius: 6px !important;
}
button[kind="secondary"]:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
}

/* Ensure disabled buttons remain readable and clearly styled */
button:disabled {
    background-color: #E2E8F0 !important;
    border-color: #CBD5E1 !important;
    color: #94A3B8 !important;
    opacity: 0.6 !important;
    cursor: not-allowed !important;
}

/* 7. Tables & DataFrames */
div[data-testid="stDataFrame"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
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
    background: #EFF6FF;
    border-left: 4px solid #0066CC;
    color: #1E3A8A;
}
.op-callout-warning {
    background: #FFFBEB;
    border-left: 4px solid #F59E0B;
    color: #92400E;
}
.op-callout-success {
    background: #ECFDF5;
    border-left: 4px solid #10B981;
    color: #065F46;
}
</style>
"""

def inject_custom_theme():
    """Injects high-contrast control-room CSS and layout tokens."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
