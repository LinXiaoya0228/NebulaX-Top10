# 🎬 3-Minute Demonstration Video Script
## Project: NebulaX — Dual-Line Railway Track Access Optimisation
**Hackathon Problem Statement 1 (LTA / NTU)**

---

### Video Overview
- **Target Duration**: Exactly 2:50 - 3:00
- **Audience**: Hackathon Judges, LTA Transit Operations Engineers, Works Controllers
- **Demo Platform**: NebulaX Live Streamlit Application (`app.py`)

---

### Detailed Scene-by-Scene Script

#### **Scene 1: The Problem & Vision (0:00 - 0:35)**
- **Visual**:
  - Open on slide or NebulaX dashboard header.
  - Quick glance at the dual-line rail network diagram (Alpha & Beta, interchange stations H01 & H02).
- **Voiceover**:
  > *"Every night on Singapore's rail network, between the last revenue train and the first morning service, a critical maintenance window opens. 14 major contractors, each deploying heavy road-rail vehicles, engineering trains, and civil maintenance teams, must compete for track access across the Alpha and Beta lines.*
  >
  > *With strict safety buffers, complex physical interlocks at interchange stations, and rigid delivery deadlines, manual scheduling is slow and prone to costly delays.*
  >
  > *Welcome to **NebulaX** — an intelligent, constraint-satisfaction track access optimization platform built specifically for the Land Transport Authority."*

---

#### **Scene 2: Architecture & Mathematical Rigor (0:35 - 1:05)**
- **Visual**:
  - Click on the **10-Rule Safety Verification** tab.
  - Scroll smoothly through the rules: Workload conservation, FS+0 precedence, 4-tier co-sharing legality, and spatial safety buffer zones.
- **Voiceover**:
  > *"At the core of NebulaX is an exact mathematical model encoding all 10 operational rules of the railway:*
  >
  > *From live traction closure zones with opposite-bound mirroring and cross-line interchange interlocking at H01 and H02, to multi-tier possession co-sharing where up to four civil gangs safely share a single track possession.*
  >
  > *Every generated schedule is verified by our automated auditor, ensuring **zero hard safety violations**."*

---

#### **Scene 3: Multi-Scenario Performance Benchmark (1:05 - 1:45)**
- **Visual**:
  - Switch to the **Scenario Comparison (A vs B vs C)** tab.
  - Highlight the comparison table and bar charts comparing Scenario A, B, and C.
- **Voiceover**:
  > *"NebulaX natively solves all three operational scenarios defined by LTA:*
  >
  > *In **Scenario A**, with strict nominal capacity and zero track extensions, NebulaX cuts total delay days in half compared to the baseline, achieving a score of 18.2.*
  >
  > *In **Scenario B**, where delivery deadlines are rigid, NebulaX strategically applies Early Closure / Late Opening (ECLO) to accelerate critical-path activities — achieving **ZERO overrun days** across all 14 contracts.*
  >
  > *In **Scenario C**, balancing supply elasticity and delay penalties, NebulaX achieves an optimal score of **14.0** with zero project delays."*

---

#### **Scene 4: Works Controller Experience & Interactive Gantt (1:45 - 2:15)**
- **Visual**:
  - Switch to the **Interactive Schedule & Gantt** tab.
  - Interact with the UI: filter by Contract (e.g. C006, C010), zoom into week 15–25, hover over an activity bar to show detailed tooltip (activity type, ECLO status, priority).
  - Open the **Spatial Heatmap & Bottlenecks** tab to show congestion hotspots.
- **Voiceover**:
  > *"For works controllers, NebulaX provides an intuitive, high-visibility workspace.*
  >
  > *Our interactive Gantt chart lets controllers inspect possessions by contract, line, or week. Clear color-coding highlights expedited ECLO nights and multi-activity possessions.*
  >
  > *The spatial heatmap immediately reveals track congestion hotspots along tunnel sectors, enabling planners to anticipate bottlenecks weeks before work begins."*

---

#### **Scene 5: Bonus Feature — Dynamic Disruption Re-planning & Explainability (2:15 - 2:45)**
- **Visual**:
  - Switch to the **Dynamic Disruption Re-planner** tab.
  - Select blocked location `SEC:BET:S14_H01:EB`, set weeks 22 to 23.
  - Click **🚨 Simulate Disruption & Re-plan Schedule**.
  - Show the live **Explainability & Causality Log** updating instantly with clear causal explanations.
- **Voiceover**:
  > *"Rail operations are dynamic. When unplanned track failures or emergency civil works occur, controllers cannot start from scratch.*
  >
  > *With NebulaX's **Dynamic Disruption Re-planner**, controllers simply select the affected sector and disruption window. In milliseconds, NebulaX isolates the conflicting activities, propagates downstream precedence constraints, and reallocates possessions — accompanied by a full explainability audit log explaining exactly why each possession was moved."*

---

#### **Scene 6: Conclusion & Deliverables (2:45 - 3:00)**
- **Visual**:
  - Show the **Submission Files Export** tab with the 1-click download buttons.
  - Display project GitHub repository and summary card.
- **Voiceover**:
  > *"NebulaX delivers verified, production-ready schedules: 100% compliant with LTA standards, mathematically optimized, and operationally resilient.*
  >
  > *Thank you, and see you on the track!"*

---

### Production Checklist for Recording
1. Start Streamlit via: `uv run streamlit run app.py` or `.venv\Scripts\streamlit.exe run app.py`
2. Browser resolution set to 1920x1080 (100% zoom).
3. Use a clear microphone with background noise suppression.
4. Record with OBS Studio or Windows Game Bar (Win + Alt + R).

