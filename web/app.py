import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.exporter import ScheduleExporter, ScheduleSolution
from src.graph import RailNetworkGraph, parse_location_id
from src.models import ProblemInstance, load_problem_instance
from src.rules import RuleEngine
from src.solver import TrackAccessSolver
from src.validator import Validator

st.set_page_config(
    page_title="NebulaX PS1 | Works Controller Dispatch Center",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for 2:00 AM Works Controller (High contrast, modern dispatch deck)
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1e2530;
        border: 1px solid #2e3846;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-val {
        font-size: 28px;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-lbl {
        font-size: 13px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-pass {
        background-color: #065f46;
        color: #34d399;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-warn {
        background-color: #78350f;
        color: #fbbf24;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_default_instance():
    data_dir = ROOT_DIR / "01_data"
    return load_problem_instance(data_dir)


def load_solution_for_scenario(instance: ProblemInstance, scenario: str) -> ScheduleSolution:
    sol_dir = ROOT_DIR / "results" / f"scenario_{scenario}"
    if (sol_dir / "SCHEDULE_ACCESS.csv").exists():
        acc = pd.read_csv(sol_dir / "SCHEDULE_ACCESS.csv")
        occ = pd.read_csv(sol_dir / "SCHEDULE_OCCUPANCY.csv")
        res = pd.read_csv(sol_dir / "RESULTS.csv")
        return ScheduleSolution(
            scenario=scenario,
            access_records=acc.to_dict(orient="records"),
            occupancy_records=occ.to_dict(orient="records"),
            results_records=res.to_dict(orient="records"),
        )
    solver = TrackAccessSolver(instance)
    return solver.solve(scenario)


@st.cache_data(show_spinner=False)
def solve_uploaded_instance(
    uploaded_payload: tuple[tuple[str, bytes], ...], scenario: str
) -> tuple[ProblemInstance, ScheduleSolution]:
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir)
        for file_name, contents in uploaded_payload:
            (data_dir / file_name).write_bytes(contents)
        uploaded_instance = load_problem_instance(data_dir)
    solution = TrackAccessSolver(uploaded_instance).solve(scenario, time_limit_sec=60)
    return uploaded_instance, solution


# Sidebar controls
st.sidebar.image(
    "https://img.icons8.com/fluency/96/subway.png",
    width=64,
)
st.sidebar.title("NebulaX PS1 Dispatch")
st.sidebar.markdown("**Dual-Line Track Access Optimiser**")

st.sidebar.divider()

# Scenario Selector
scenario = st.sidebar.radio(
    "Select Optimization Scenario:",
    ["A", "B", "C"],
    format_func=lambda s: {
        "A": "Scenario A: Rigid Supply (Zero Excess, 0 ECLO)",
        "B": "Scenario B: Strict Deadlines (0 Overrun, Flexible Supply)",
        "C": "Scenario C: Balanced Elasticity (2-Wk ECLO Window)",
    }[s],
    index=0,
)

required_instance_files = {
    "01_LINES.csv",
    "02_STATIONS.csv",
    "03_SECTORS.csv",
    "04_LOCATION_SUPPLY.csv",
    "05_BUFFER_LOCATION.csv",
    "06_PARAMETERS.csv",
    "07_PROJECT_DETAILS.csv",
    "08_ACTIVITY_DETAILS.csv",
}
uploaded_files = st.sidebar.file_uploader(
    "Upload hidden instance (8 CSV files)",
    type="csv",
    accept_multiple_files=True,
)

st.sidebar.divider()
st.sidebar.markdown("### Quick Navigation")
st.sidebar.markdown("- 📊 **Executive Scorecard**")
st.sidebar.markdown("- 📅 **Interactive Gantt Timeline**")
st.sidebar.markdown("- 🗺️ **Spatial Topology & Buffer Map**")
st.sidebar.markdown("- 🔍 **Validator & Rule Compliance**")
st.sidebar.markdown("- ⚡ **What-If Disruption Sandbox**")
st.sidebar.markdown("- 💾 **Export Submission CSVs**")


# Main App Header
st.title("🚆 Works Controller Decision Support System")
st.markdown(
    f"**Real-Time Railway Track Access Scheduling Engine** | Active: **Scenario {scenario}**"
)

# Load the public instance or solve an uploaded hidden instance.
if uploaded_files:
    uploaded_names = {file.name for file in uploaded_files}
    missing_files = sorted(required_instance_files - uploaded_names)
    unexpected_files = sorted(uploaded_names - required_instance_files)
    if missing_files or unexpected_files:
        st.error(
            f"Instance file set is invalid. Missing: {missing_files or 'none'}; "
            f"unexpected: {unexpected_files or 'none'}."
        )
        st.stop()
    payload = tuple(sorted((file.name, file.getvalue()) for file in uploaded_files))
    with st.spinner(f"Optimizing uploaded instance for Scenario {scenario}..."):
        instance, solution = solve_uploaded_instance(payload, scenario)
else:
    instance = get_default_instance()
    solution = load_solution_for_scenario(instance, scenario)

graph = RailNetworkGraph(instance)
rules = RuleEngine(instance, graph)
validator = Validator(instance)

access_df = pd.DataFrame(solution.access_records)
occ_df = pd.DataFrame(solution.occupancy_records)
results_df = pd.DataFrame(solution.results_records)

# Run validation report
report = validator.validate(access_df, occ_df, results_df, scenario)

# Executive Metrics Row
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    status_html = (
        '<div class="metric-card"><div class="badge-pass">FEASIBLE (0 FAILS)</div><div class="metric-lbl">Rule Integrity</div></div>'
        if report.feasible
        else '<div class="metric-card"><div class="badge-warn">VIOLATIONS DETECTED</div><div class="metric-lbl">Rule Integrity</div></div>'
    )
    st.markdown(status_html, unsafe_allow_html=True)

with col2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{report.soft_scores["overrun_days_total"]} d</div><div class="metric-lbl">Total Overrun</div></div>',
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{report.soft_scores["contracts_overrunning"]} / 14</div><div class="metric-lbl">Overrunning Contracts</div></div>',
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{report.soft_scores["eclo_nights_total"]}</div><div class="metric-lbl">ECLO Nights Used</div></div>',
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        f'<div class="metric-card"><div class="metric-val">{report.soft_scores["objective_score"]}</div><div class="metric-lbl">Scenario Score</div></div>',
        unsafe_allow_html=True,
    )

st.write("")

# Main Tabs
tab_gantt, tab_map, tab_validator, tab_whatif, tab_export = st.tabs([
    "📅 Master Gantt Timeline",
    "🗺️ Network Digital Twin & Buffer Map",
    "🛡️ Specification Checks & Scoring",
    "⚡ What-If Disruption Sandbox",
    "💾 Submission & Data Export",
])

# -------------------------------------------------------------
# TAB 1: MASTER GANTT TIMELINE
# -------------------------------------------------------------
with tab_gantt:
    st.subheader("Interactive 30-Week Schedule Gantt Chart")
    st.markdown("Filter activities by contract priority, access type, or specific contractors:")

    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        priority_filter = st.multiselect("Contract Priority", [1, 2, 3], default=[1, 2, 3])
    with f_col2:
        access_type_filter = st.multiselect("Access Type", ["PM", "PC", "C"], default=["PM", "PC", "C"])
    with f_col3:
        all_contracts = sorted(list(instance.contracts.keys()))
        contract_filter = st.multiselect("Filter Specific Contracts", all_contracts, default=all_contracts[:7])

    # Build Gantt data
    gantt_rows = []
    for _, row in access_df.iterrows():
        act_id = row["activity_id"]
        wk = int(row["week"])
        eclo = int(row["eclo"])
        act = instance.activities[act_id]
        c = instance.contracts[act.contract_number]

        if c.contract_priority not in priority_filter:
            continue
        if c.access_type not in access_type_filter:
            continue
        if contract_filter and c.contract_number not in contract_filter:
            continue

        start_date = instance.horizon_start + pd.Timedelta(days=(wk - 1) * 7)
        end_date = instance.horizon_start + pd.Timedelta(days=wk * 7)

        gantt_rows.append({
            "Activity": act_id,
            "Contract": c.contract_number,
            "Priority": f"P{c.contract_priority}",
            "Access Type": c.access_type,
            "Start": start_date,
            "End": end_date,
            "Week": wk,
            "ECLO": "Yes" if eclo == 1 else "No",
            "Night Index": row["access_night"],
            "Location Start": act.start_location_id,
            "Location End": act.end_location_id,
        })

    if gantt_rows:
        gantt_df = pd.DataFrame(gantt_rows)
        fig = px.timeline(
            gantt_df,
            x_start="Start",
            x_end="End",
            y="Activity",
            color="Contract",
            hover_data=["Week", "ECLO", "Night Index", "Access Type", "Priority", "Location Start", "Location End"],
            title=f"Schedule Timeline (Scenario {scenario})",
            height=600,
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            xaxis_title="Calendar Date",
            yaxis_title="Activity ID",
            template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No activities match the selected filters.")

    # Contract Completion Summary Table
    st.markdown("### Contract Delivery Status")
    st.dataframe(results_df, use_container_width=True)


# -------------------------------------------------------------
# TAB 2: NETWORK DIGITAL TWIN & BUFFER MAP
# -------------------------------------------------------------
with tab_map:
    st.subheader("Spatial Track Possession & Safety Buffer Visualizer")
    st.markdown(
        "Inspect which sectors are closed, safe-buffered, or mirror-locked on any given week:"
    )

    s_col1, s_col2 = st.columns(2)
    with s_col1:
        sel_week = st.slider("Select Week", min_value=1, max_value=instance.horizon_weeks, value=18)
    with s_col2:
        sel_line = st.selectbox("Select Line Topology", ["ALP (Line Alpha)", "BET (Line Beta)"])
        line_code = "ALP" if "ALP" in sel_line else "BET"

    # Find activities in selected week and line
    week_access = access_df[access_df["week"] == sel_week]
    week_acts = week_access["activity_id"].unique()

    # Collect closed, buffer, and mirror sectors
    phys_closed_sec = set()
    buffer_sec = set()
    mirror_sec = set()
    cross_line_sec = set()

    for act_id in week_acts:
        fp = rules.activity_footprints[act_id]
        for loc in fp.physical_occupancy:
            if loc.startswith("SEC:"):
                phys_closed_sec.add(loc)
        for loc in fp.buffer_locations:
            if loc.startswith("SEC:"):
                buffer_sec.add(loc)
        for loc in fp.mirrored_locations:
            if loc.startswith("SEC:"):
                mirror_sec.add(loc)
        for loc in fp.cross_line_locations:
            if loc.startswith("SEC:"):
                cross_line_sec.add(loc)

    # Render interactive sector map table
    line_sectors = graph.line_sectors[line_code]
    map_data = []
    for sec in line_sectors:
        from_to = f"{sec.from_station_id}_{sec.to_station_id}"
        sec_eb = f"SEC:{line_code}:{from_to}:EB"
        sec_wb = f"SEC:{line_code}:{from_to}:WB"

        def get_status(sec_id):
            if sec_id in phys_closed_sec:
                return "🔴 OCCUPIED (Workzone)"
            if sec_id in buffer_sec:
                return "🟡 BUFFER ZONE (Safety)"
            if sec_id in mirror_sec:
                return "⚡ MIRRORED CLOSURE (Live)"
            if sec_id in cross_line_sec:
                return "🟣 INTERCHANGE LOCKOUT"
            return "🟢 OPEN (Operational)"

        map_data.append({
            "Sector": f"{sec.from_station_id} ↔ {sec.to_station_id}",
            "Sequence": sec.seq,
            "Eastbound (EB) Status": get_status(sec_eb),
            "Westbound (WB) Status": get_status(sec_wb),
            "Shared Track": "Yes" if sec.is_shared else "No",
        })

    map_df = pd.DataFrame(map_data)
    st.table(map_df)

    st.caption("🔴 Red: Work possession | 🟡 Yellow: Safety exclusion buffer | ⚡ Amber: Live rail opposite bound mirror | 🟢 Green: Normal track")


# -------------------------------------------------------------
# TAB 3: LOCAL SPECIFICATION CHECKS & SCORING
# -------------------------------------------------------------
with tab_validator:
    st.subheader("Local Specification Verification")
    st.markdown("Verifies all 10 strict physical, topological, and operational constraints:")

    col_chk1, col_chk2 = st.columns(2)
    with col_chk1:
        st.markdown(f"- **Workload Conservation (100%)**: {'✅ PASSED' if not any(v.rule == 'workload' for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **Planned Start Date**: {'✅ PASSED' if not any(v.rule == 'planned_start' for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **Predecessor FS+0 (> week)**: {'✅ PASSED' if not any(v.rule == 'predecessor' for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **Weekly Allocation Cap**: {'✅ PASSED' if not any(v.rule == 'weekly_allocation' for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **Workfront Concurrency**: {'✅ PASSED' if not any(v.rule == 'workfront' for v in report.hard_violations) else '❌ FAILED'}")
    with col_chk2:
        st.markdown(f"- **Possession Legal Mix (PM/PC/C)**: {'✅ PASSED' if not any(v.rule == 'legal_mix' for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **Supply Capacity**: {'✅ PASSED' if not any(v.rule == 'capacity' for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **ECLO Protocol**: {'✅ PASSED' if not any('eclo' in v.rule for v in report.hard_violations) else '❌ FAILED'}")
        st.markdown(f"- **Scenario Strict Target**: {'✅ PASSED' if not any(v.rule == 'planned_date' for v in report.hard_violations) else '❌ FAILED'}")

    st.divider()
    st.markdown("### Local JSON Validation Report")
    st.json(report.to_dict())


# -------------------------------------------------------------
# TAB 4: WHAT-IF DISRUPTION SANDBOX
# -------------------------------------------------------------
with tab_whatif:
    st.subheader("What-If Track Disruption & Emergency Re-Planning")
    st.markdown(
        "Simulate unplanned track closures or emergency speed restrictions mid-horizon and evaluate system resilience:"
    )

    w_col1, w_col2, w_col3 = st.columns(3)
    with w_col1:
        disrupt_sector = st.selectbox("Disrupted Sector", [f"SEC:ALP:S03_S04:EB", "SEC:BET:H01_H02:EB", "SEC:ALP:S05_S06:WB"])
    with w_col2:
        disrupt_start_wk = st.slider("Disruption Start Week", 1, 25, 12)
    with w_col3:
        disrupt_duration = st.slider("Duration (Weeks)", 1, 6, 2)

    if st.button("🚨 Simulate Track Fault Disruption"):
        disrupt_end_wk = disrupt_start_wk + disrupt_duration - 1
        conflicted_acts = occ_df[
            (occ_df["location_id"] == disrupt_sector)
            & (occ_df["week"] >= disrupt_start_wk)
            & (occ_df["week"] <= disrupt_end_wk)
        ]["activity_id"].unique()

        if len(conflicted_acts) > 0:
            st.error(f"⚠️ DISRUPTION IMPACT: {len(conflicted_acts)} activities directly blocked on {disrupt_sector} between Week {disrupt_start_wk} and {disrupt_end_wk}: {list(conflicted_acts)}")
            st.info("System recommendation: Trigger agile rescheduling heuristic to shift affected accesses into neighboring spare possession slots.")
        else:
            st.success(f"✅ ZERO IMPACT: No track access was scheduled on {disrupt_sector} between Week {disrupt_start_wk} and {disrupt_end_wk}. Normal operations continue.")


# -------------------------------------------------------------
# TAB 5: SUBMISSION & DATA EXPORT
# -------------------------------------------------------------
with tab_export:
    st.subheader("Competition Deliverables & CSV Exporter")
    st.markdown("Download pre-computed and validated submission files:")

    e_col1, e_col2, e_col3 = st.columns(3)
    with e_col1:
        st.download_button(
            "📥 Download SCHEDULE_ACCESS.csv",
            data=access_df.to_csv(index=False),
            file_name="SCHEDULE_ACCESS.csv",
            mime="text/csv",
        )
    with e_col2:
        st.download_button(
            "📥 Download SCHEDULE_OCCUPANCY.csv",
            data=occ_df.to_csv(index=False),
            file_name="SCHEDULE_OCCUPANCY.csv",
            mime="text/csv",
        )
    with e_col3:
        st.download_button(
            "📥 Download RESULTS.csv",
            data=results_df.to_csv(index=False),
            file_name="RESULTS.csv",
            mime="text/csv",
        )

    st.write("")
    # Zip package downloader
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("SCHEDULE_ACCESS.csv", access_df.to_csv(index=False))
        zip_file.writestr("SCHEDULE_OCCUPANCY.csv", occ_df.to_csv(index=False))
        zip_file.writestr("RESULTS.csv", results_df.to_csv(index=False))

    st.download_button(
        label=f"📦 Download Complete Submission Package (Scenario {scenario} ZIP)",
        data=zip_buffer.getvalue(),
        file_name=f"NebulaX_PS1_Submission_Scenario_{scenario}.zip",
        mime="application/zip",
    )
