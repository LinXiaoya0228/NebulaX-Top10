# NebulaX Hackathon — PS1: Railway Track Access Optimisation

> **Team NebulaX-Top10** | Branch: `Siwen`  
> An automated CP-SAT Track Access Allocation system for dual-line rail networks (Line Alpha & Line Beta).

---

## 📋 Executive Summary

Railway track access during engineering engineering hours (01:30 – 04:30) is the ultimate operational bottleneck. Track managers face a combinatorial challenge: scheduling heavy engineering works, rail renewals, and signaling upgrades across shared tracks while guaranteeing absolute spatial safety, respect for live-rail electrical boundaries, and contract milestone delivery.

This solution provides:
1. **Mathematical Optimization Engine**: Self-contained multi-scenario solver powered by Google OR-Tools CP-SAT with optional warm-start hints.
2. **Topological & Spatial Buffer Engine**: Models directional tracks, station platforms (`PLAT:...`), tunnel sectors (`SEC:...`), opposite-bound live rail mirrors, and cross-line interchange closures.
3. **Independent Rule Validator**: Local specification validator with recomputed results and access-to-occupancy integrity checks.
4. **2:00 AM Works Controller Decision Support Deck**: A high-contrast, interactive Streamlit web dashboard featuring interactive Gantt charts, digital twin spatial heatmaps, disruption "What-If" sandboxes, and one-click submission exports.

---

## 🏆 Benchmark Results

All scenarios evaluated with the repository's local specification validator on the public competition dataset:

| Metric | Scenario A (Rigid Supply) | Scenario B (Strict Schedule) | Scenario C (Balanced Elasticity) |
| :--- | :---: | :---: | :---: |
| **Feasibility Status** | **✅ FEASIBLE (0 FAILS)** | **✅ FEASIBLE (0 FAILS)** | **✅ FEASIBLE (0 FAILS)** |
| **Hard Violations Count** | **0** | **0** | **0** |
| **Total Overrun Days** | 21 days (P3 only) | **0 days (100% on-time)** | 21 days (P3 only) |
| **Contracts Overrunning** | 2 / 14 | **0 / 14** | 2 / 14 |
| **Excess Access Nights** | 0 | 0 | 0 |
| **ECLO Nights Used** | 0 (Forbidden) | 6 | 0 |
| **Priority 1 Overruns** | **0 days** | **0 days** | **0 days** |
| **Priority 2 Overruns** | **0 days** | **0 days** | **0 days** |
| **Objective Score** | **27.3** | **30.0** | **27.3** |

---

## 📐 System Architecture

```mermaid
flowchart TD
    subgraph Data Layer ["Input Data Layer (8 CSVs)"]
        D1["01_LINES & 02_STATIONS"]
        D2["03_SECTORS & 04_LOCATION_SUPPLY"]
        D3["05_BUFFER & 06_PARAMETERS"]
        D4["07_PROJECTS & 08_ACTIVITIES"]
    end

    subgraph Core Engine ["Core Physics & Topological Engine"]
        G["RailNetworkGraph<br/>• SEC & PLAT Path Expansion<br/>• Dual-Line Interchange Map"]
        R["RuleEngine<br/>• Live 2-Sector Buffer<br/>• Opposite-Bound Mirroring<br/>• Cross-Line H01_H02 Propagation<br/>• Legal Co-sharing Mixes"]
    end

    subgraph Optimization Layer ["Multi-Scenario Optimization"]
        SOL["TrackAccessSolver<br/>(Google OR-Tools CP-SAT + Heuristics)"]
        SA["Scenario A: Rigid Supply, 0 ECLO"]
        SB["Scenario B: 0 Overrun, Elastic Supply"]
        SC["Scenario C: Balanced, 2-Wk ECLO Window"]
    end

    subgraph Verification Layer ["Verification & Submission"]
        VAL["Validator<br/>• 10 Strict Physical Rules<br/>• Workload Conservation<br/>• Predecessor FS+0 (> week)"]
        EXP["ScheduleExporter<br/>• SCHEDULE_ACCESS.csv<br/>• SCHEDULE_OCCUPANCY.csv<br/>• RESULTS.csv"]
    end

    subgraph UI Layer ["Works Controller Dashboard"]
        APP["Streamlit Web App (web/app.py)<br/>• Interactive Plotly Gantt<br/>• Spatial Network Digital Twin<br/>• What-If Disruption Sandbox<br/>• 1-Click ZIP Exporter"]
    end

    Data Layer --> Core Engine
    Core Engine --> Optimization Layer
    Optimization Layer --> Verification Layer
    Verification Layer --> UI Layer
```

---

## 📂 Repository Structure

```
NebulaX-Top10/
├── 01_data/                          # Provided 8 domain CSV inputs
├── src/
│   ├── __init__.py
│   ├── models.py                     # Domain models and CSV loader
│   ├── graph.py                      # Rail topology & sector/platform expansion
│   ├── rules.py                      # Buffer calculations & conflict engine
│   ├── solver.py                     # Multi-scenario CP-SAT optimizer
│   ├── validator.py                  # Local specification validator
│   └── exporter.py                   # Submission CSV generator
├── web/
│   ├── __init__.py
│   └── app.py                        # Streamlit Works Controller Dashboard
├── results/
│   ├── scenario_A/                   # Generated outputs for Scenario A
│   ├── scenario_B/                   # Generated outputs for Scenario B
│   └── scenario_C/                   # Generated outputs for Scenario C
├── tests/
│   ├── __init__.py
│   └── test_validator.py             # Automated pytest verification suite
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Production container definition
└── README.md                         # Project documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
Python 3.11+ recommended. Install required packages:
```bash
pip install -r requirements.txt
```

### 2. Run Automated Test Suite
Verify that all 3 scenarios pass the repository's local specification checks:
```bash
pytest tests/test_validator.py -v
```

The organizer's executable validator is not included in the public problem repository.
Run the generated submissions through that validator before final submission, especially
to confirm the exact buffer/closure interpretation across location-week possession slots.

### 3. Launch the Interactive Web Application
Start the Works Controller Dashboard:
```bash
streamlit run web/app.py
```
Open your browser at `http://localhost:8501`.

---

## ⚙️ Key Operational Constraints Enforced

1. **Workload Conservation (100% Gate)**: Every activity in `08_ACTIVITY_DETAILS.csv` is scheduled with nightly yields summing to $\ge \text{total\_accesses}$ (standard = 1.0, ECLO = 1.5).
2. **Path & Platform Footprint**: Every activity books both its tunnel sectors (`SEC:...`) and all intermediate platform sectors (`PLAT:...`).
3. **Safety Exclusion Buffers**:
   - `Live`: 2 sectors ahead/behind + opposite-bound track mirror (`EB` $\leftrightarrow$ `WB`) + cross-line interchange lockout at `H01_H02`.
   - `Non-live (Consist)`: 1 sector ahead/behind, same bound.
   - `Non-live (Others)`: 0 buffer.
   - Buffers between distinct possessions never overlap.
4. **Co-Sharing Legal Mixes**: Max 1 PM alone, 1 PC + $\le 3$ C, or $\le 4$ C per `(location_id, week, co_share_group)`. Activities in the same possession are mutually exempt from closures.
5. **Finish-to-Start Precedence (FS+0)**: Successor activity start week is strictly greater than predecessor last night week ($\min(\text{weeks}(Y)) > \max(\text{weeks}(X))$).
6. **Scenario Constraints**:
   - **Scenario A**: Zero excess capacity, zero ECLO.
   - **Scenario B**: Zero overrun days across all contracts, flexible capacity.
   - **Scenario C**: Max 1 excess night per location-week, ECLO strictly bounded inside a single continuous 2-calendar-week window per line.