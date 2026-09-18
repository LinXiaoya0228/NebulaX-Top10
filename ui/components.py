"""
ui/components.py - Reusable, accessible UI components for Railway Works Control Centre.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
import streamlit as st
from ui.theme import LINE_THEME, STATUS_THEME


def render_compact_header(
    active_scenario: str = "A",
    report: Optional[Dict[str, Any]] = None,
    current_time_str: Optional[str] = None,
):
    """
    Renders an operational control-room header conforming to:
    - Max desktop height: 100-120 px
    - Title on single line: 'Railway Works Control Centre'
    - Subtitle in smaller secondary text
    - Responsive status group with line indicators, system time, and compliance badge
    - Zero absolute positioning, zero fixed offsets, natural wrapping on smaller screens
    """
    if current_time_str is None:
        current_time_str = datetime.now().strftime("%H:%M:%S SGT")

    feasible = report.get("feasible", True) if report else True
    violations = len(report.get("hard_violations", [])) if report else 0

    col_title, col_status = st.columns([1.6, 1.4], gap="medium")

    with col_title:
        st.markdown(
            """
            <div style="margin-bottom: 2px;">
                <h1 style="display: flex; align-items: center; gap: 8px; margin: 0; padding: 0;">
                    <span>🚇</span> <span>Railway Works Control Centre</span>
                </h1>
                <div style="color: #94A3B8; font-size: 0.82rem; margin-top: 2px;">
                    Multi-Disciplinary Track Access Scheduling & Real-Time Operational Decision Support
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_status:
        # Dual-encoded status indicators (Color + Icon + Text)
        val_class = "badge-pass" if feasible else "badge-breach"
        val_icon = "✓ PASS" if feasible else f"✕ {violations} VIOLATION"

        st.markdown(
            f"""
            <div style="display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 6px; padding-top: 6px;">
                <span class="op-badge badge-alp" title="Alpha Line Operational Status">
                    🔵 [ALP] Alpha: Active
                </span>
                <span class="op-badge badge-bet" title="Beta Line Operational Status">
                    🟣 [BET] Beta: Active
                </span>
                <span class="op-badge {val_class}" title="Official Baseline Validation State">
                    {val_icon} (Scenario {active_scenario})
                </span>
                <span class="op-badge" style="background: #16233B; color: #CBD5E1; border: 1px solid #334155;" title="Engineering Window Clock">
                    🕒 {current_time_str} | Window 01:00–04:30
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='margin: 8px 0 16px 0; border: none; border-bottom: 1px solid #1E293B;' />", unsafe_allow_html=True)


def render_kpi_card(
    title: str,
    value: str,
    delta: str,
    status: str = "neutral",
    icon: Optional[str] = None,
):
    """
    Renders a consistent, accessible KPI metric card.
    status: 'ok', 'warning', 'alert', or 'neutral'
    """
    color_map = {
        "ok": "#34D399",
        "warning": "#FBBF24",
        "alert": "#FB7185",
        "neutral": "#38BDF8",
    }
    val_color = color_map.get(status, "#F8FAFC")
    delta_icon = "✓" if status == "ok" else ("⚠️" if status in ("warning", "alert") else "•")

    icon_html = f"<span>{icon}</span> " if icon else ""

    st.markdown(
        f"""
        <div class="cr-card">
            <div class="cr-card-header">
                <span>{icon_html}{title}</span>
            </div>
            <div class="cr-card-value" style="color: {val_color};">
                {value}
            </div>
            <div class="cr-card-delta" style="color: {val_color};">
                <span>{delta_icon}</span> <span>{delta}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_op_callout(text: str, level: str = "info", icon: Optional[str] = None):
    """
    Renders a semantic operational banner (info, warning, success, alert).
    """
    class_map = {
        "info": ("op-callout-info", icon or "ℹ️"),
        "warning": ("op-callout-warning", icon or "⚠️"),
        "success": ("op-callout-success", icon or "✅"),
        "alert": ("op-callout-warning", icon or "🚨"),
    }
    css_class, default_icon = class_map.get(level, ("op-callout-info", "ℹ️"))
    st.markdown(
        f"""
        <div class="op-callout {css_class}">
            <div style="font-size: 1.1rem; line-height: 1;">{default_icon}</div>
            <div style="flex: 1; font-size: 0.88rem;">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_line_badge(line_code: str) -> str:
    """Returns HTML for line badge with explicit text and icon."""
    if line_code == "ALP":
        return '<span class="op-badge badge-alp">🔵 [ALP] Alpha Line</span>'
    elif line_code == "BET":
        return '<span class="op-badge badge-bet">🟣 [BET] Beta Line</span>'
    return f'<span class="op-badge">{line_code}</span>'


def render_bound_badge(bound: str) -> str:
    """Returns HTML for bound badge with direction arrow and text."""
    if bound == "EB":
        return '<span class="op-badge" style="background:#1E293B; color:#38BDF8; border:1px solid #38BDF8;">→ [EB] Eastbound</span>'
    elif bound == "WB":
        return '<span class="op-badge" style="background:#1E293B; color:#FBBF24; border:1px solid #FBBF24;">← [WB] Westbound</span>'
    return f'<span class="op-badge">{bound}</span>'


def render_eclo_badge() -> str:
    """Returns HTML for ECLO badge with dual visual cues."""
    return '<span class="op-badge badge-eclo">⚡ [ECLO] Extended Access</span>'

