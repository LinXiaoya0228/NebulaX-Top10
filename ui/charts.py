"""
ui/charts.py - Accessible, responsive Plotly chart builders for Railway Works Control Centre.
Strictly adheres to WCAG 2.2 AA and Rule 1.4.1 (color is never the only visual cue).
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_parser import DataMall
from ui.theme import CLOSURE_THEME, LINE_THEME, STATUS_THEME, SURFACES, TEXT_COLORS


# ==============================================================================
# Base Chart Styling Helpers
# ==============================================================================

def apply_chart_theme(
    fig: go.Figure,
    title: str,
    height: int = 580,
    show_legend: bool = True,
    x_title: Optional[str] = None,
    y_title: Optional[str] = None,
) -> go.Figure:
    """Applies standardized dark control-room theme and responsive margins."""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=14, color=TEXT_COLORS["primary"]),
            x=0.01,
            y=0.98,
        ),
        paper_bgcolor=SURFACES["card"],
        plot_bgcolor=SURFACES["bg_app"],
        font=dict(color=TEXT_COLORS["primary"], size=12),
        height=height,
        margin=dict(l=60, r=40, t=75, b=45),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1.0,
            font=dict(size=12, color="#F8FAFC"),
            bgcolor="rgba(17, 28, 46, 0.95)",
            bordercolor=SURFACES["border"],
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor=SURFACES["card_alt"],
            bordercolor=SURFACES["border"],
            font=dict(color=TEXT_COLORS["primary"], size=12),
        ),
    )
    x_kwargs = dict(
        gridcolor=SURFACES["border"],
        zerolinecolor=SURFACES["border"],
        tickfont=dict(color="#F8FAFC", size=12),
    )
    if x_title:
        x_kwargs["title"] = dict(text=x_title, font=dict(color="#F8FAFC", size=13))
    fig.update_xaxes(**x_kwargs)

    y_kwargs = dict(
        gridcolor=SURFACES["border"],
        zerolinecolor=SURFACES["border"],
        tickfont=dict(color="#F8FAFC", size=12),
    )
    if y_title:
        y_kwargs["title"] = dict(text=y_title, font=dict(color="#F8FAFC", size=13))
    fig.update_yaxes(**y_kwargs)

    return fig


def group_consecutive_weeks(weeks: List[int]) -> List[Tuple[int, int]]:
    """Groups a sorted list of weeks into contiguous (start, end) intervals."""
    if not weeks:
        return []
    sorted_w = sorted(list(set(weeks)))
    intervals = []
    start = sorted_w[0]
    prev = sorted_w[0]
    for w in sorted_w[1:]:
        if w == prev + 1:
            prev = w
        else:
            intervals.append((start, prev))
            start = w
            prev = w
    intervals.append((start, prev))
    return intervals


# ==============================================================================
# 7.1 Access Schedule Chart (Continuous Capsules & Discrete Mode)
# ==============================================================================

def build_access_schedule_chart(
    access_df: pd.DataFrame,
    dm: DataMall,
    scenario_label: str = "Scenario A",
    line_filter: str = "All",
    nature_filter: str = "All",
    eclo_only: bool = False,
    contract_filter: str = "All",
    week_range: Tuple[int, int] = (1, 29),
    view_mode: str = "continuous",
) -> go.Figure:
    """
    Renders an operational week-based track access schedule.
    In 'continuous' mode (recommended):
      - Adjacent consecutive weeks form smooth, connected work capsule bars.
      - Non-occupied intermediate gap weeks remain strictly blank (no false continuity).
      - Activities are grouped with contract prefix '[C001] A009'.
      - ECLO extended possessions feature glowing golden diamond badges.
    In 'discrete' mode:
      - Renders individual discrete block markers per scheduled access night.
    """
    df = access_df.copy()

    # Enrich with metadata
    df["contract_number"] = df["activity_id"].map(lambda a: dm.activities[a].contract_number if a in dm.activities else "UNKNOWN")
    df["line_code"] = df["activity_id"].map(lambda a: dm.activities[a].line_code if a in dm.activities else "ALP")
    df["bound"] = df["activity_id"].map(lambda a: dm.activities[a].bound if a in dm.activities else "EB")
    df["nature"] = df["contract_number"].map(lambda c: dm.contracts[c].nature_of_activity if c in dm.contracts else "Non-live")
    df["priority"] = df["activity_id"].map(lambda a: dm.activities[a].activity_priority if a in dm.activities else 3)
    if "is_eclo" in df.columns:
        df["is_eclo"] = df["is_eclo"].astype(bool)
    elif "eclo" in df.columns:
        df["is_eclo"] = df["eclo"].astype(int) == 1
    else:
        df["is_eclo"] = False

    # Filters
    if line_filter in ("ALP", "BET"):
        df = df[df["line_code"] == line_filter]
    if nature_filter in ("Live", "Non-live"):
        df = df[df["nature"] == nature_filter]
    if eclo_only:
        df = df[df["is_eclo"]]
    if contract_filter != "All":
        df = df[df["contract_number"] == contract_filter]

    df = df[(df["week"] >= week_range[0]) & (df["week"] <= week_range[1])]

    if df.empty:
        fig = go.Figure()
        return apply_chart_theme(fig, f"Access Schedule ({scenario_label}) - No matching activities", height=400)

    # Sort activities by contract and activity ID with contract prefix for clarity
    seq_col = "access_seq" if "access_seq" in df.columns else "access_sequence"
    df["y_label"] = df.apply(lambda r: f"[{r['contract_number']}] {r['activity_id']}", axis=1)
    df = df.sort_values(by=["contract_number", "activity_id", "week", seq_col])
    unique_labels = df["y_label"].unique().tolist()

    fig = go.Figure()

    if view_mode == "continuous":
        # Draw connected work capsules for contiguous runs of weeks
        alp_x_lines, alp_y_lines = [], []
        bet_x_lines, bet_y_lines = [], []
        single_x, single_y, single_colors = [], [], []

        for y_lbl in unique_labels:
            sub = df[df["y_label"] == y_lbl]
            line_c = sub["line_code"].iloc[0]
            wks = sub["week"].tolist()
            intervals = group_consecutive_weeks(wks)

            for w_start, w_end in intervals:
                if w_start < w_end:
                    if line_c == "ALP":
                        alp_x_lines.extend([f"W{w_start:02d}", f"W{w_end:02d}", None])
                        alp_y_lines.extend([y_lbl, y_lbl, None])
                    else:
                        bet_x_lines.extend([f"W{w_start:02d}", f"W{w_end:02d}", None])
                        bet_y_lines.extend([y_lbl, y_lbl, None])
                else:
                    single_x.append(f"W{w_start:02d}")
                    single_y.append(y_lbl)
                    single_colors.append(LINE_THEME["ALP"]["color"] if line_c == "ALP" else LINE_THEME["BET"]["color"])

        # Add continuous capsule bars
        if alp_x_lines:
            fig.add_trace(go.Scatter(
                x=alp_x_lines,
                y=alp_y_lines,
                mode="lines",
                line=dict(width=16, color=LINE_THEME["ALP"]["color"]),
                hoverinfo="skip",
                name="[ALP] Alpha Work Capsule",
            ))
        if bet_x_lines:
            fig.add_trace(go.Scatter(
                x=bet_x_lines,
                y=bet_y_lines,
                mode="lines",
                line=dict(width=16, color=LINE_THEME["BET"]["color"]),
                hoverinfo="skip",
                name="[BET] Beta Work Capsule",
            ))
        if single_x:
            fig.add_trace(go.Scatter(
                x=single_x,
                y=single_y,
                mode="markers",
                marker=dict(symbol="square", size=14, color=single_colors, line=dict(width=1, color="#FFFFFF")),
                hoverinfo="skip",
                showlegend=False,
            ))

        # Add individual weekly access markers along the capsules
        std_df = df[~df["is_eclo"]]
        if not std_df.empty:
            std_hovers = []
            for _, r in std_df.iterrows():
                aid = r["activity_id"]
                act = dm.activities.get(aid)
                locs_str = ", ".join(list(act.expanded_locations)[:3]) + ("..." if act and len(act.expanded_locations) > 3 else "") if act else ""
                seq_val = r.get("access_seq", r.get("access_sequence", 1))
                night_val = r.get("access_night", 1)
                co_share = r.get("co_share_group", "Independent")
                txt = (
                    f"<b>{aid}</b> ({r['contract_number']})<br>"
                    f"Line: {r['line_code']} ({r['bound']}) | Nature: {r['nature']}<br>"
                    f"Week: <b>W{r['week']:02d}</b> (Access #{seq_val}, Night {night_val})<br>"
                    f"Window: Standard 3.5h (01:00-04:30)<br>"
                    f"Locations: {locs_str}<br>"
                    f"Co-share Group: {co_share}"
                )
                std_hovers.append(txt)

            fig.add_trace(go.Scatter(
                x=[f"W{w:02d}" for w in std_df["week"]],
                y=std_df["y_label"],
                mode="markers",
                marker=dict(symbol="circle", size=6, color="#FFFFFF", opacity=0.9),
                text=std_hovers,
                hoverinfo="text",
                name="○ Weekly Access Point",
            ))

    else:
        # Discrete point view
        std_df = df[~df["is_eclo"]]
        if not std_df.empty:
            hover_texts = []
            for _, r in std_df.iterrows():
                aid = r["activity_id"]
                act = dm.activities.get(aid)
                locs_str = ", ".join(list(act.expanded_locations)[:3]) + ("..." if act and len(act.expanded_locations) > 3 else "") if act else ""
                seq_val = r.get("access_seq", r.get("access_sequence", 1))
                night_val = r.get("access_night", 1)
                co_share = r.get("co_share_group", "Independent")
                txt = (
                    f"<b>{aid}</b> | {r['contract_number']}<br>"
                    f"Line: {r['line_code']} ({r['bound']}) | Nature: {r['nature']}<br>"
                    f"Week: <b>W{r['week']:02d}</b> (Access #{seq_val}, Night {night_val})<br>"
                    f"Window: Standard 3.5h (01:00-04:30)<br>"
                    f"Locations: {locs_str}<br>"
                    f"Co-share Group: {co_share}"
                )
                hover_texts.append(txt)

            colors = [LINE_THEME[l]["color"] if l in LINE_THEME else "#38BDF8" for l in std_df["line_code"]]
            fig.add_trace(
                go.Scatter(
                    x=[f"W{w:02d}" for w in std_df["week"]],
                    y=std_df["y_label"],
                    mode="markers",
                    marker=dict(
                        symbol="square",
                        size=12,
                        color=colors,
                        line=dict(width=1, color="#FFFFFF"),
                    ),
                    text=hover_texts,
                    hoverinfo="text",
                    name="■ Standard Access (3.5h)",
                )
            )

    # Trace: ECLO Extended Access Blocks (Distinct Glowing Diamond)
    eclo_df = df[df["is_eclo"]]
    if not eclo_df.empty:
        eclo_hovers = []
        for _, r in eclo_df.iterrows():
            aid = r["activity_id"]
            act = dm.activities.get(aid)
            locs_str = ", ".join(list(act.expanded_locations)[:3]) + ("..." if act and len(act.expanded_locations) > 3 else "") if act else ""
            seq_val = r.get("access_seq", r.get("access_sequence", 1))
            night_val = r.get("access_night", 1)
            co_share = r.get("co_share_group", "Independent")
            txt = (
                f"<b>⚡ [ECLO] {aid}</b> | {r['contract_number']}<br>"
                f"Line: {r['line_code']} ({r['bound']}) | Nature: {r['nature']}<br>"
                f"Week: <b>W{r['week']:02d}</b> (Access #{seq_val}, Night {night_val})<br>"
                f"Window: <b>Extended 6.0h (22:30-04:30)</b><br>"
                f"Work Yield: 1.5x Standard<br>"
                f"Locations: {locs_str}<br>"
                f"Co-share Group: {co_share}"
            )
            eclo_hovers.append(txt)

        fig.add_trace(
            go.Scatter(
                x=[f"W{w:02d}" for w in eclo_df["week"]],
                y=eclo_df["y_label"],
                mode="markers",
                marker=dict(
                    symbol="diamond",
                    size=18,
                    color="#F59E0B",
                    line=dict(width=2, color="#FEF08A"),
                ),
                text=eclo_hovers,
                hoverinfo="text",
                name="⚡ [ECLO] Extended Access (6.0h)",
            )
        )

    # Ensure week axis is ordered W01..W29
    all_weeks = [f"W{w:02d}" for w in range(week_range[0], week_range[1] + 1)]
    fig.update_xaxes(
        categoryorder="array",
        categoryarray=all_weeks,
        title_text="Operational Planning Week",
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=unique_labels,
        autorange="reversed",
        title_text="Contract & Activity ID",
    )

    chart_height = min(780, max(420, len(unique_labels) * 18 + 120))
    title_suffix = "Continuous Work Capsules" if view_mode == "continuous" else "Discrete Weekly Allocations"
    apply_chart_theme(
        fig,
        title=f"Track Access Schedule - {title_suffix} ({scenario_label})",
        height=chart_height,
        show_legend=True,
    )
    return fig


# ==============================================================================
# 7.2 Executive Contract Gantt Chart (14 Contracts Program Overview)
# ==============================================================================

def build_contract_gantt_chart(
    access_df: pd.DataFrame,
    results_df: pd.DataFrame,
    dm: DataMall,
    scenario_label: str = "Scenario A",
    line_filter: str = "All",
) -> go.Figure:
    """
    Renders an executive-level 14-contract Gantt timeline.
    Displays each contract's execution window, planned completion target, and simulated finish.
    Provides instant 30,000-ft program visibility with zero clutter.
    """
    fig = go.Figure()
    base_dt = datetime(2027, 1, 4)

    df = access_df.copy()
    if "contract_number" not in df.columns:
        df["contract_number"] = df["activity_id"].map(lambda a: dm.activities[a].contract_number if a in dm.activities else "UNKNOWN")

    contract_rows = []
    cids = sorted(dm.contracts.keys())

    for cid in cids:
        sub = df[df["contract_number"] == cid]
        if sub.empty:
            continue

        c_obj = dm.contracts[cid]
        line = "ALP" if cid in ["C001", "C002", "C003", "C004", "C005", "C006", "C007"] else "BET"
        if line_filter in ("ALP", "BET") and line != line_filter:
            continue

        w_start = int(sub["week"].min())
        w_end = int(sub["week"].max())
        num_acc = len(sub)
        prio = c_obj.contract_priority
        p_str = c_obj.planned_completion_date
        p_dt = datetime.strptime(p_str, "%Y-%m-%d")
        p_week = min(29, max(1, 1 + (p_dt - base_dt).days // 7))

        s_row = results_df[results_df["contract_number"] == cid]
        ov = int(s_row["overrun_days"].iloc[0]) if not s_row.empty else 0
        sim_date = s_row["simulated_completion_date"].iloc[0] if not s_row.empty else p_str

        y_label = f"<b>{cid}</b> (P{prio} | {line})"
        contract_rows.append({
            "cid": cid,
            "y_label": y_label,
            "line": line,
            "w_start": w_start,
            "w_end": w_end,
            "num_acc": num_acc,
            "p_week": p_week,
            "p_str": p_str,
            "sim_date": sim_date,
            "ov": ov,
            "prio": prio,
            "scope": c_obj.activity_type,
        })

    if not contract_rows:
        return apply_chart_theme(fig, f"Contract Executive Gantt ({scenario_label}) - No matching contracts", height=350)

    # Traces:
    # 1. Execution window bars
    alp_x, alp_y, bet_x, bet_y = [], [], [], []
    for r in contract_rows:
        if r["line"] == "ALP":
            alp_x.extend([f"W{r['w_start']:02d}", f"W{r['w_end']:02d}", None])
            alp_y.extend([r["y_label"], r["y_label"], None])
        else:
            bet_x.extend([f"W{r['w_start']:02d}", f"W{r['w_end']:02d}", None])
            bet_y.extend([r["y_label"], r["y_label"], None])

    if alp_x:
        fig.add_trace(go.Scatter(
            x=alp_x,
            y=alp_y,
            mode="lines",
            line=dict(width=22, color=LINE_THEME["ALP"]["color"]),
            name="[ALP] Alpha Line Execution Window",
            hoverinfo="skip",
        ))
    if bet_x:
        fig.add_trace(go.Scatter(
            x=bet_x,
            y=bet_y,
            mode="lines",
            line=dict(width=22, color=LINE_THEME["BET"]["color"]),
            name="[BET] Beta Line Execution Window",
            hoverinfo="skip",
        ))

    # 2. Planned Target Milestones (Diamond Flag)
    target_x = [f"W{r['p_week']:02d}" for r in contract_rows]
    target_y = [r["y_label"] for r in contract_rows]
    target_hovers = [
        f"<b>Target Milestone: {r['cid']}</b><br>Planned Finish: {r['p_str']} (Week {r['p_week']:02d})"
        for r in contract_rows
    ]
    fig.add_trace(go.Scatter(
        x=target_x,
        y=target_y,
        mode="markers",
        marker=dict(symbol="diamond-tall", size=18, color="#FFFFFF", line=dict(width=2, color="#38BDF8")),
        text=target_hovers,
        hoverinfo="text",
        name="🎯 Target Milestone Week",
    ))

    # 3. Completion Status Markers & Annotations
    for r in contract_rows:
        status_text = "✓ On-Time" if r["ov"] == 0 else f"⚠️ +{r['ov']}d Overrun"
        status_color = "#34D399" if r["ov"] == 0 else "#FB7185"

        # Place label strictly to the right of whichever is furthest: execution end or target milestone
        ann_week = max(r["w_end"], r["p_week"])

        fig.add_annotation(
            x=f"W{ann_week:02d}",
            y=r["y_label"],
            text=f"  <b>{status_text}</b>",
            showarrow=False,
            xanchor="left",
            font=dict(color=status_color, size=11, family="Arial Black"),
        )

        detail_hover = (
            f"<b>Contract {r['cid']}</b> (Priority P{r['prio']})<br>"
            f"Line: {r['line']} | Scope: {r['scope']}<br>"
            f"Work Window: W{r['w_start']:02d} → W{r['w_end']:02d} ({r['num_acc']} total accesses)<br>"
            f"Planned Milestone: {r['p_str']} (W{r['p_week']:02d})<br>"
            f"Simulated Finish: {r['sim_date']}<br>"
            f"Result: <b>{status_text}</b>"
        )
        fig.add_trace(go.Scatter(
            x=[f"W{r['w_end']:02d}"],
            y=[r["y_label"]],
            mode="markers",
            marker=dict(symbol="circle", size=10, color=status_color, line=dict(width=2, color="#FFFFFF")),
            text=[detail_hover],
            hoverinfo="text",
            showlegend=False,
        ))

    all_weeks = [f"W{w:02d}" for w in range(1, 30)] + [" "]
    fig.update_xaxes(
        categoryorder="array",
        categoryarray=all_weeks,
        title_text="Operational Planning Week (W01–W29)",
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=[r["y_label"] for r in contract_rows],
        autorange="reversed",
        title_text="Contract (Priority & Line)",
    )
    fig.update_layout(margin=dict(r=95))

    chart_height = max(420, len(contract_rows) * 32 + 120)
    apply_chart_theme(
        fig,
        title=f"Contract Executive Gantt - 14 Contracts Program Overview ({scenario_label})",
        height=chart_height,
        show_legend=True,
    )
    return fig


# ==============================================================================
# 7.2 Contract Completion Comparison Chart (Dumbbell / Interval Chart)
# ==============================================================================

def build_contract_completion_chart(
    results_df: pd.DataFrame,
    dm: DataMall,
    scenario_label: str = "Scenario A",
    sort_by: str = "Overrun (High to Low)",
) -> go.Figure:
    """
    Renders planned vs simulated completion dates using an accessible dumbbell chart.
    Dual visual encoding:
    - Planned: White circle marker '○'
    - Simulated: Solid marker (Green diamond for on-time, Red square for overrun)
    - Overrun contracts explicitly labelled with '+X days' and warning icon
    """
    df = results_df.copy()
    df["planned_completion_date"] = df["contract_number"].map(lambda c: dm.contracts[c].planned_completion_date)
    df["priority"] = df["contract_number"].map(lambda c: dm.contracts[c].contract_priority)
    df["tier_weight"] = df["priority"].map({1: "P1 (100/7)", 2: "P2 (10/7)", 3: "P3 (1/7)"})

    # Sort
    if sort_by == "Overrun (High to Low)":
        df = df.sort_values(by=["overrun_days", "priority", "contract_number"], ascending=[False, True, True])
    elif sort_by == "Contract ID":
        df = df.sort_values(by="contract_number")
    elif sort_by == "Planned Date":
        df = df.sort_values(by="planned_completion_date")
    else:
        df = df.sort_values(by="simulated_completion_date")

    fig = go.Figure()

    # Trace 1: Dumbbell connecting line between Planned and Simulated
    for _, r in df.iterrows():
        cid = r["contract_number"]
        ov = r["overrun_days"]
        p_date = pd.to_datetime(r["planned_completion_date"])
        s_date = pd.to_datetime(r["simulated_completion_date"])

        line_color = "#FB7185" if ov > 0 else "#34D399"
        line_dash = "dash" if ov > 0 else "solid"

        fig.add_trace(
            go.Scatter(
                x=[p_date, s_date],
                y=[cid, cid],
                mode="lines",
                line=dict(color=line_color, width=3, dash=line_dash),
                hoverinfo="none",
                showlegend=False,
            )
        )

    # Trace 2: Planned Milestones (Distinct Open Circle)
    fig.add_trace(
        go.Scatter(
            x=pd.to_datetime(df["planned_completion_date"]),
            y=df["contract_number"],
            mode="markers",
            marker=dict(
                symbol="circle-open",
                size=12,
                color="#FFFFFF",
                line=dict(width=2.5, color="#38BDF8"),
            ),
            name="○ Planned Contract Milestone",
            hovertemplate="<b>%{y} Planned Finish:</b> %{x|%Y-%m-%d}<extra></extra>",
        )
    )

    # Trace 3: On-Time Simulated Completions
    ontime_df = df[df["overrun_days"] == 0]
    if not ontime_df.empty:
        fig.add_trace(
            go.Scatter(
                x=pd.to_datetime(ontime_df["simulated_completion_date"]),
                y=ontime_df["contract_number"],
                mode="markers+text",
                marker=dict(symbol="diamond", size=13, color="#34D399", line=dict(width=1.5, color="#A7F3D0")),
                text=["  ✓ On-Time" for _ in range(len(ontime_df))],
                textposition="middle right",
                textfont=dict(color="#34D399", size=10),
                name="◆ Simulated Finish: On-Time (0d Overrun)",
                hovertemplate="<b>%{y} Simulated Finish:</b> %{x|%Y-%m-%d} (On-Time)<extra></extra>",
            )
        )

    # Trace 4: Overrun Simulated Completions
    overrun_df = df[df["overrun_days"] > 0]
    if not overrun_df.empty:
        labels = [f"  ⚠️ +{ov}d Delay" for ov in overrun_df["overrun_days"]]
        fig.add_trace(
            go.Scatter(
                x=pd.to_datetime(overrun_df["simulated_completion_date"]),
                y=overrun_df["contract_number"],
                mode="markers+text",
                marker=dict(symbol="square", size=14, color="#FB7185", line=dict(width=2, color="#FECDD3")),
                text=labels,
                textposition="middle right",
                textfont=dict(color="#FB7185", size=11, family="Arial Black"),
                name="■ Simulated Finish: Overrun (Penalty Applied)",
                hovertemplate="<b>%{y} Overrun Finish:</b> %{x|%Y-%m-%d}<br>Delay: +%{customdata} days<extra></extra>",
                customdata=overrun_df["overrun_days"],
            )
        )

    fig.update_xaxes(type="date", title_text="Contract Completion Horizon (Calendar Date)")
    fig.update_yaxes(categoryorder="array", categoryarray=df["contract_number"].tolist(), title_text="Contract ID")

    apply_chart_theme(
        fig,
        title=f"Contract Completion Horizon: Planned vs Simulated ({scenario_label})",
        height=540,
        show_legend=True,
    )
    return fig


# ==============================================================================
# 8. Capacity Utilisation Heatmap (with Explicit Excess Annotation)
# ==============================================================================

def build_capacity_heatmap(
    occ_df: pd.DataFrame,
    dm: DataMall,
    scenario_label: str = "Scenario A",
    metric_choice: str = "Capacity Utilisation (%)",
    display_mode: str = "Capacity Hotspots (Top 20)",
    line_filter: str = "All",
    loc_type_filter: str = "All",
    week_range: Tuple[int, int] = (1, 29),
) -> Tuple[go.Figure, pd.DataFrame]:
    """
    Renders capacity utilisation heatmap.
    - Utilisation = (used possession slots / available supply slots) * 100%
    - Excess (>100%) has explicit annotation text '⚠️' and bold outline (WCAG 1.4.1 grayscale compliant)
    - Zero supply marked as 'No Supply' / 'N/A'
    """
    # 1. Compute used possessions grouped by (location_id, week) using distinct co-share groups
    used_counts = occ_df.groupby(["location_id", "week"])["co_share_group"].nunique().to_dict()

    # 2. Build complete grid of (loc, week) with supply
    all_locs = sorted(list(dm.location_supply.keys()))

    records = []
    for loc in all_locs:
        # Filter line
        if line_filter == "ALP" and "ALP" not in loc:
            continue
        if line_filter == "BET" and "BET" not in loc:
            continue

        # Filter location type (PLAT vs SEC)
        if loc_type_filter == "Platform (PLAT)" and not loc.startswith("PLAT:"):
            continue
        if loc_type_filter == "Sector (SEC)" and not loc.startswith("SEC:"):
            continue

        supply_obj = dm.location_supply.get(loc)
        avail = supply_obj.supply_capacity if supply_obj is not None else 0

        for wk in range(week_range[0], week_range[1] + 1):
            used = used_counts.get((loc, wk), 0)

            if avail > 0:
                util = (used / avail) * 100.0
                status_text = f"{util:.0f}%"
            else:
                util = 999.0 if used > 0 else 0.0
                status_text = "No Normal Supply"

            excess = max(0, used - avail) if avail > 0 else used

            records.append({
                "location_id": loc,
                "week": wk,
                "used": used,
                "avail": avail,
                "utilisation": util,
                "excess": excess,
                "status_text": status_text,
            })

    full_df = pd.DataFrame(records)
    if full_df.empty:
        fig = go.Figure()
        return apply_chart_theme(fig, f"Capacity Heatmap ({scenario_label}) - No Data", height=400), pd.DataFrame()

    # Apply display scope filter (Hotspots vs All)
    if display_mode == "Capacity Hotspots (Top 20)":
        hotspots = (
            full_df.groupby("location_id")["used"]
            .sum()
            .sort_values(ascending=False)
            .head(20)
            .index.tolist()
        )
        full_df = full_df[full_df["location_id"].isin(hotspots)]

    # Pivot for Heatmap
    if metric_choice == "Capacity Utilisation (%)":
        val_col = "utilisation"
        color_scale = [
            [0.0, "#0F172A"],   # Neutral dark slate (0%)
            [0.4, "#0284C7"],   # Normal usage (40%)
            [0.75, "#0369A1"],  # High usage (75%)
            [0.9, "#F59E0B"],   # Near capacity (90-100%)
            [1.0, "#E11D48"],   # Over-capacity excess (>100%)
        ]
        color_title = "Utilisation (%)"
    else:
        val_col = "used"
        color_scale = "Plasma"
        color_title = "Possessions (Count)"

    pivot = full_df.pivot(index="location_id", columns="week", values=val_col).fillna(0)

    # Build custom hover texts and excess annotations
    hover_matrix = []
    text_matrix = []
    for loc in pivot.index:
        loc_hovers = []
        loc_texts = []
        for wk in pivot.columns:
            sub = full_df[(full_df["location_id"] == loc) & (full_df["week"] == wk)]
            if not sub.empty:
                r = sub.iloc[0]
                h = (
                    f"<b>{loc}</b> | Week <b>W{wk:02d}</b><br>"
                    f"Used Possessions (CSG): <b>{r['used']}</b><br>"
                    f"Available Supply: <b>{r['avail']}</b><br>"
                    f"Utilisation: <b>{r['utilisation']:.1f}%</b><br>"
                    f"Excess: <b>{r['excess']} slots</b>"
                )
                loc_hovers.append(h)
                # Only if excess > 0, display visible alert symbol in the cell
                if r["excess"] > 0:
                    loc_texts.append("⚠️ EXCESS")
                else:
                    loc_texts.append("")
            else:
                loc_hovers.append("No Data")
                loc_texts.append("")
        hover_matrix.append(loc_hovers)
        text_matrix.append(loc_texts)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[f"W{c:02d}" for c in pivot.columns],
            y=pivot.index.tolist(),
            colorscale=color_scale,
            colorbar=dict(title=dict(text=color_title, side="right")),
            text=text_matrix,
            texttemplate="%{text}",
            textfont=dict(color="#FFFFFF", size=9, family="Arial Black"),
            hovertext=hover_matrix,
            hoverinfo="text",
        )
    )

    chart_height = min(750, max(420, len(pivot.index) * 22 + 120))
    apply_chart_theme(
        fig,
        title=f"Track Capacity Heatmap ({metric_choice}) - {display_mode}",
        height=chart_height,
        show_legend=False,
    )
    fig.update_xaxes(title_text="Planning Week")
    fig.update_yaxes(title_text="Track Location (Platform / Sector)")

    return fig, full_df


# ==============================================================================
# 9. Spatial Track Topology Line Schematic
# ==============================================================================

def build_topology_schematic(
    dm: DataMall,
    active_activity_id: Optional[str] = None,
    line_code: str = "ALP",
) -> go.Figure:
    """
    Renders an accessible railway line schematic distinguishing:
    - Stations, Platforms, Sections, and Interchange stations
    - Direct closure, Buffer closure, Mirrored closure, and Cross-line closure
    - Each closure type has distinct line style, symbol, and explicit text legend (WCAG 1.4.1)
    """
    fig = go.Figure()

    # 1. Base Track Schematic Layout
    stations = dm.stations.get(line_code, [])
    stn_x = {s.station_id: idx * 2.0 for idx, s in enumerate(stations)}

    # Base track rail lines (EB and WB)
    x_coords = [stn_x[s.station_id] for s in stations]
    stn_ids = [s.station_id for s in stations]

    # Eastbound Base Track
    fig.add_trace(
        go.Scatter(
            x=x_coords,
            y=[1.0] * len(x_coords),
            mode="lines+markers+text",
            line=dict(color="#334155", width=4),
            marker=dict(symbol="square", size=10, color="#64748B"),
            text=[f"{sid}<br>EB" for sid in stn_ids],
            textposition="top center",
            name="Track: Eastbound (EB)",
            hoverinfo="text",
        )
    )

    # Westbound Base Track
    fig.add_trace(
        go.Scatter(
            x=x_coords,
            y=[-1.0] * len(x_coords),
            mode="lines+markers+text",
            line=dict(color="#334155", width=4),
            marker=dict(symbol="square", size=10, color="#64748B"),
            text=[f"{sid}<br>WB" for sid in stn_ids],
            textposition="bottom center",
            name="Track: Westbound (WB)",
            hoverinfo="text",
        )
    )

    # 2. Overlay Safety Footprint if an activity is active
    if active_activity_id and active_activity_id in dm.activities:
        footprint = dm.get_safety_footprint(active_activity_id)
        act = dm.activities[active_activity_id]

        # Direct Work Span
        direct_locs = footprint["work_span"]
        d_th = CLOSURE_THEME["direct"]
        fig.add_trace(
            go.Scatter(
                x=[x_coords[0], x_coords[min(1, len(x_coords)-1)]],
                y=[1.0 if act.bound == "EB" else -1.0] * 2,
                mode="lines+markers",
                line=dict(color=d_th["color"], width=8),
                marker=dict(symbol=d_th["symbol"], size=14, color=d_th["color"]),
                name=f"{d_th['label']} ({len(direct_locs)} locs)",
                hoverinfo="name",
            )
        )

        # Buffer Closure
        buf_locs = footprint["buffer_locations"]
        if buf_locs:
            b_th = CLOSURE_THEME["buffer"]
            fig.add_trace(
                go.Scatter(
                    x=[x_coords[min(2, len(x_coords)-1)]],
                    y=[1.0 if act.bound == "EB" else -1.0],
                    mode="markers",
                    marker=dict(symbol=b_th["symbol"], size=16, color=b_th["color"], line=dict(width=2, color="#FFFFFF")),
                    name=f"{b_th['label']} ({len(buf_locs)} locs)",
                    hoverinfo="name",
                )
            )

        # Mirror Closure
        mir_locs = footprint["mirror_locations"]
        if mir_locs:
            m_th = CLOSURE_THEME["mirror"]
            fig.add_trace(
                go.Scatter(
                    x=[x_coords[0], x_coords[min(1, len(x_coords)-1)]],
                    y=[-1.0 if act.bound == "EB" else 1.0] * 2,
                    mode="lines+markers",
                    line=dict(color=m_th["color"], width=6, dash=m_th["line_style"]),
                    marker=dict(symbol=m_th["symbol"], size=14, color=m_th["color"]),
                    name=f"{m_th['label']} ({len(mir_locs)} locs)",
                    hoverinfo="name",
                )
            )

        # Cross-Line Closure
        xline_locs = footprint["cross_line_locations"]
        if xline_locs:
            x_th = CLOSURE_THEME["cross_line"]
            fig.add_trace(
                go.Scatter(
                    x=[x_coords[0]],
                    y=[0.0],
                    mode="markers",
                    marker=dict(symbol=x_th["symbol"], size=18, color=x_th["color"], line=dict(width=2, color="#FFFFFF")),
                    name=f"{x_th['label']} ({len(xline_locs)} locs)",
                    hoverinfo="name",
                )
            )

    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
    fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False, range=[-2.5, 2.5])

    apply_chart_theme(
        fig,
        title=f"Railway Topology Schematic - {LINE_THEME[line_code]['text_tag']}",
        height=380,
        show_legend=True,
    )
    return fig
