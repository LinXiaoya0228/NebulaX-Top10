"""
app.py - Interactive Streamlit Web Application for Railway Track Access Optimisation.
Provides full end-to-end workflow: upload hidden instance CSVs, run CP-SAT optimisation,
inspect violations and official objective scores, visualize timelines & heatmaps,
and download validated submission packages.
"""

import io
import os
import shutil
import tempfile
import zipfile
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_parser import DataMall
from scheduler import ScenarioScheduler
from validator import Validator

# Configure page
st.set_page_config(
    page_title="Railway Track Access Optimiser",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-label { font-size: 0.85rem; color: #555; font-weight: 500; }
    .metric-value { font-size: 1.6rem; font-weight: 700; color: #111; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 45px; white-space: pre-wrap; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_default_data_dir() -> str:
    default_dir = os.path.join(os.path.dirname(__file__), "PS1", "01_data")
    if os.path.isdir(default_dir):
        return default_dir
    return "PS1/01_data"


def save_uploaded_files(uploaded_files) -> str:
    """Saves uploaded files to a temporary directory and returns the path."""
    temp_dir = tempfile.mkdtemp()
    for f in uploaded_files:
        path = os.path.join(temp_dir, f.name)
        with open(path, "wb") as out:
            out.write(f.getbuffer())
    return temp_dir


def create_submission_zip(output_dir: str, scenario_name: str) -> bytes:
    """Zips the 3 output files for download."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ["SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv", "RESULTS.csv"]:
            fpath = os.path.join(output_dir, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
    buf.seek(0)
    return buf.getvalue()


# Sidebar Configuration
st.sidebar.title("🚆 Track Access Optimiser")
st.sidebar.caption("Deterministic & Globally Optimal Railway Access Scheduling")

data_source = st.sidebar.radio(
    "Data Source",
    ["Use Official Benchmark (PS1/01_data)", "Upload Instance CSVs"],
)

active_data_dir = None
if data_source == "Use Official Benchmark (PS1/01_data)":
    active_data_dir = get_default_data_dir()
    st.sidebar.success(f"Loaded: `{active_data_dir}`")
else:
    uploaded = st.sidebar.file_uploader(
        "Upload the 8 instance CSVs",
        type=["csv"],
        accept_multiple_files=True,
        help="Upload 01_LINES.csv through 08_ACTIVITY_DETAILS.csv",
    )
    if uploaded:
        if len(uploaded) >= 8:
            active_data_dir = save_uploaded_files(uploaded)
            st.sidebar.success(f"Uploaded {len(uploaded)} files successfully.")
        else:
            st.sidebar.warning(f"Please upload all 8 CSV files ({len(uploaded)}/8 provided).")

st.sidebar.markdown("---")
scenario_option = st.sidebar.selectbox(
    "Scenario to Optimise",
    ["Scenario A (Strict Overrun Minimisation)", "Scenario B (Zero Overrun Guarantee)", "Scenario C (Pareto Trade-off)", "All Scenarios (A, B, C)"],
)

scenario_code = {
    "Scenario A (Strict Overrun Minimisation)": "A",
    "Scenario B (Zero Overrun Guarantee)": "B",
    "Scenario C (Pareto Trade-off)": "C",
    "All Scenarios (A, B, C)": "ALL",
}[scenario_option]

timeout = st.sidebar.slider("Solver Timeout (seconds)", min_value=5, max_value=60, value=20)
run_button = st.sidebar.button("🚀 Run Optimisation", type="primary", width="stretch")

# Title Header
st.title("🚆 Railway Track Access Optimisation Engine")
st.markdown(
    """
    **Deterministic, Globally Optimal, Zero-Hard-Violation Access Scheduler** for complex multi-line railway engineering horizons.
    Models track safety geometry (buffers, opposite-bound mirroring, hub crossovers), legal possession mix constraints,
    and contract workfront allocations.
    """
)

# App State Storage
if "reports" not in st.session_state:
    st.session_state.reports = {}
if "results_dirs" not in st.session_state:
    st.session_state.results_dirs = {}

# Check existing results
results_base = os.path.join(os.path.dirname(__file__), "results")
for sc in ["A", "B", "C"]:
    sc_dir = os.path.join(results_base, f"scenario_{sc}")
    if os.path.exists(os.path.join(sc_dir, "RESULTS.csv")) and sc not in st.session_state.reports:
        try:
            val = Validator(active_data_dir or get_default_data_dir())
            st.session_state.reports[sc] = val.validate(sc_dir, sc)
            st.session_state.results_dirs[sc] = sc_dir
        except Exception:
            pass

# Run optimization when triggered
if run_button:
    if not active_data_dir or not os.path.isdir(active_data_dir):
        st.error("Invalid data directory. Please check file uploads or default path.")
    else:
        scenarios_to_run = ["A", "B", "C"] if scenario_code == "ALL" else [scenario_code]
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, sc in enumerate(scenarios_to_run):
            status_text.text(f"Optimising Scenario {sc} via CP-SAT Solver...")
            sc_out_dir = os.path.join(results_base, f"scenario_{sc}")
            os.makedirs(sc_out_dir, exist_ok=True)

            scheduler = ScenarioScheduler(active_data_dir)
            report = scheduler.solve(sc, sc_out_dir, timeout_seconds=timeout, verbose=False)

            st.session_state.reports[sc] = report
            st.session_state.results_dirs[sc] = sc_out_dir
            progress_bar.progress((idx + 1) / len(scenarios_to_run))

        status_text.text("Optimisation complete!")
        progress_bar.empty()
        st.success(f"Successfully solved scenario(s): {', '.join(scenarios_to_run)}!")

# Main Dashboard display
if st.session_state.reports:
    # Select active view scenario
    available_scs = list(st.session_state.reports.keys())
    selected_sc = st.radio(
        "View Scenario Results",
        available_scs,
        format_func=lambda x: f"Scenario {x}",
        horizontal=True,
    )

    report = st.session_state.reports[selected_sc]
    out_dir = st.session_state.results_dirs[selected_sc]
    scores = report["soft_scores"]

    # Top KPI Metrics Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric(
            label="Feasibility",
            value="FEASIBLE" if report["feasible"] else "INFEASIBLE",
            delta="0 Hard Violations" if report["feasible"] else f"{len(report['hard_violations'])} Violations",
            delta_color="normal" if report["feasible"] else "inverse",
        )
    with m2:
        st.metric(
            label="Official Score",
            value=f"{scores['objective_score']:.1f}",
            delta=f"v1.0 Formula",
        )
    with m3:
        st.metric(
            label="Total Overrun",
            value=f"{scores['overrun_days_total']} days",
            delta=f"{scores['contracts_overrunning']} contracts",
            delta_color="inverse" if scores['overrun_days_total'] > 0 else "normal",
        )
    with m4:
        st.metric(
            label="ECLO Nights",
            value=f"{scores['eclo_nights_total']}",
            delta="Yield 1.5",
        )
    with m5:
        st.metric(
            label="Excess Nights",
            value=f"{scores['excess_access_nights_total']}",
            delta="Capacity Breaches",
            delta_color="inverse" if scores['excess_access_nights_total'] > 0 else "normal",
        )
    with m6:
        st.metric(
            label="Total Earliness",
            value=f"{scores.get('earliness_days_total', 0)} days",
            delta="Bonus Pushed Ahead",
        )

    # Tabs for detailed views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Score Diagnostics",
        "📅 Contract Schedule & Gantt",
        "🗺️ Track Possession Density",
        "🔍 Access Schedule Tables",
        "📥 Download Submission Package",
    ])

    # Tab 1: Diagnostics
    with tab1:
        st.subheader(f"Scenario {selected_sc} Validation & Objective Breakdown")
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("#### Official Score Components")
            score_data = {
                "Component": [
                    "Priority 1 Overrun Days",
                    "Priority 2 Overrun Days",
                    "Priority 3 Overrun Days",
                    "Weighted Overrun Subtotal",
                    "Excess Access Nights Penalty",
                    "ECLO Nights Penalty",
                    "Total Official Objective Score",
                ],
                "Value": [
                    scores.get("priority_overrun", {}).get("1", 0),
                    scores.get("priority_overrun", {}).get("2", 0),
                    scores.get("priority_overrun", {}).get("3", 0),
                    scores.get("priority_weighted_score", 0.0),
                    scores.get("excess_access_nights_total", 0) * 7.0,
                    scores.get("eclo_nights_total", 0) * 5.0,
                    scores.get("objective_score", 0.0),
                ],
            }
            st.dataframe(pd.DataFrame(score_data), width="stretch", hide_index=True)

        with col_right:
            st.markdown("#### Hard Violations Checklist")
            if report["feasible"]:
                st.success("✅ All 11 Strict Hard Rules PASSED (Zero Violations)")
            else:
                st.error(f"❌ {len(report['hard_violations'])} Hard Violations Detected:")
                for v in report["hard_violations"]:
                    st.write(f"- **[{v['rule']}]**: {v['message']}")

    # Tab 2: Timeline & Gantt
    with tab2:
        st.subheader("Contract Completion Dates vs Planned Milestones")
        res_file = os.path.join(out_dir, "RESULTS.csv")
        dm = DataMall(active_data_dir or get_default_data_dir())

        if os.path.exists(res_file):
            results_df = pd.read_csv(res_file)
            # Add planned date and priority
            results_df["planned_completion_date"] = results_df["contract_number"].map(
                lambda c: dm.contracts[c].planned_completion_date
            )
            results_df["priority"] = results_df["contract_number"].map(
                lambda c: dm.contracts[c].contract_priority
            )
            results_df["start_date"] = results_df["contract_number"].map(
                lambda c: min(act.planned_start_date for act in dm.activities.values() if act.contract_number == c)
            )

            fig = go.Figure()
            for _, row in results_df.iterrows():
                cid = row["contract_number"]
                ov = row["overrun_days"]
                color = "#4CAF50" if ov == 0 else "#F44336"

                # Contract simulated span
                fig.add_trace(
                    go.Bar(
                        name=cid,
                        y=[cid],
                        x=[pd.to_datetime(row["simulated_completion_date"]) - pd.to_datetime(row["start_date"])],
                        base=[pd.to_datetime(row["start_date"])],
                        orientation="h",
                        marker=dict(color=color),
                        hovertemplate=f"<b>{cid}</b><br>Planned: {row['planned_completion_date']}<br>Simulated: {row['simulated_completion_date']}<br>Overrun: {ov} days<extra></extra>",
                        showlegend=False,
                    )
                )

                # Add planned milestone marker
                fig.add_trace(
                    go.Scatter(
                        x=[pd.to_datetime(row["planned_completion_date"])],
                        y=[cid],
                        mode="markers",
                        marker=dict(symbol="line-ns", size=18, color="black", line=dict(width=3, color="black")),
                        name="Planned Milestone" if cid == "C001" else "",
                        showlegend=(cid == "C001"),
                        hovertemplate=f"Planned Milestone: {row['planned_completion_date']}<extra></extra>",
                    )
                )

            fig.update_layout(
                title=f"Contract Execution Horizon & Milestones (Scenario {selected_sc})",
                xaxis_title="Date",
                yaxis_title="Contract",
                barmode="overlay",
                height=500,
                xaxis=dict(type="date"),
            )
            st.plotly_chart(fig, width="stretch")

    # Tab 3: Possession Density Heatmap
    with tab3:
        st.subheader("Weekly Network Possession Density")
        occ_file = os.path.join(out_dir, "SCHEDULE_OCCUPANCY.csv")
        if os.path.exists(occ_file):
            occ_df = pd.read_csv(occ_file)
            heat_data = occ_df.groupby(["location_id", "week"]).size().reset_index(name="occupancy_count")
            pivot = heat_data.pivot(index="location_id", columns="week", values="occupancy_count").fillna(0)

            fig = px.imshow(
                pivot,
                labels=dict(x="Week Number", y="Location", color="Possessions"),
                x=pivot.columns,
                y=pivot.index,
                color_continuous_scale="Viridis",
                aspect="auto",
            )
            fig.update_layout(height=650, title=f"Possession Density by Location & Week (Scenario {selected_sc})")
            st.plotly_chart(fig, width="stretch")

    # Tab 4: Access Schedule Tables
    with tab4:
        st.subheader("Interactive Schedule Inspector")
        acc_file = os.path.join(out_dir, "SCHEDULE_ACCESS.csv")
        if os.path.exists(acc_file):
            acc_df = pd.read_csv(acc_file)

            # Predecessor Dependency & Activity Summary View
            st.markdown("#### 🔗 Activity & Predecessor Dependency Summary")
            dm = DataMall(active_data_dir or get_default_data_dir())

            act_summary = []
            for aid, act in dm.activities.items():
                act_accs = acc_df[acc_df["activity_id"] == aid]
                if not act_accs.empty:
                    min_w = int(act_accs["week"].min())
                    max_w = int(act_accs["week"].max())
                    cnt = len(act_accs)
                    eclo_cnt = int(act_accs["eclo"].sum())
                    pred = act.predecessor_activity_id
                    pred_finish = None
                    pred_status = "N/A (No Predecessor)"
                    if pred:
                        pred_accs = acc_df[acc_df["activity_id"] == pred]
                        if not pred_accs.empty:
                            pred_finish = int(pred_accs["week"].max())
                            if min_w > pred_finish:
                                pred_status = f"✅ Valid (Pred {pred} finished W{pred_finish} < Succ start W{min_w})"
                            else:
                                pred_status = f"❌ VIOLATION (Pred {pred} finished W{pred_finish} >= Succ start W{min_w})"

                    act_summary.append({
                        "Activity": aid,
                        "Contract": act.contract_number,
                        "Planned Start Wk": act.planned_start_week,
                        "Start Week": min_w,
                        "Finish Week": max_w,
                        "Accesses Delivered": cnt,
                        "ECLO Accesses": eclo_cnt,
                        "Predecessor ID": pred or "None",
                        "Predecessor Status (FS+0)": pred_status,
                    })

            act_sum_df = pd.DataFrame(act_summary)
            # Filter to show activities with predecessors or all
            show_only_preds = st.checkbox("Show only activities with Predecessor dependencies", value=False)
            if show_only_preds:
                filtered_sum_df = act_sum_df[act_sum_df["Predecessor ID"] != "None"]
                st.dataframe(filtered_sum_df, width="stretch", hide_index=True)
            else:
                st.dataframe(act_sum_df, width="stretch", hide_index=True)

            st.markdown("#### Detailed Nightly Access Records (`SCHEDULE_ACCESS.csv`)")
            st.dataframe(acc_df, width="stretch")

    # Tab 5: Download Package
    with tab5:
        st.subheader(f"Download Submission Artifacts (Scenario {selected_sc})")
        zip_bytes = create_submission_zip(out_dir, selected_sc)
        st.download_button(
            label=f"📦 Download Complete Submission ZIP (Scenario {selected_sc})",
            data=zip_bytes,
            file_name=f"submission_scenario_{selected_sc}.zip",
            mime="application/zip",
            type="primary",
        )

        st.markdown("#### Individual Files")
        c1, c2, c3 = st.columns(3)
        with c1:
            p = os.path.join(out_dir, "SCHEDULE_ACCESS.csv")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    st.download_button("Download SCHEDULE_ACCESS.csv", f, "SCHEDULE_ACCESS.csv", "text/csv")
        with c2:
            p = os.path.join(out_dir, "SCHEDULE_OCCUPANCY.csv")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    st.download_button("Download SCHEDULE_OCCUPANCY.csv", f, "SCHEDULE_OCCUPANCY.csv", "text/csv")
        with c3:
            p = os.path.join(out_dir, "RESULTS.csv")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    st.download_button("Download RESULTS.csv", f, "RESULTS.csv", "text/csv")
else:
    st.info("👈 Click **Run Optimisation** in the sidebar to generate schedules for Scenarios A, B, and C.")
