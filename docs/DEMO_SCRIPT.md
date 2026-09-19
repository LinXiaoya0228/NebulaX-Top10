# 🎬 3-Minute Video Demo Script & Visual Storyboard
## LTA NebulaX 2026 — Problem Statement 1: Railway Track Access Optimisation
**System Name:** NebulaX RailWorks Controller Suite  
**Hosted Live Web App URL:** [https://nebulax-control-centre-570754541444.us-central1.run.app/](https://nebulax-control-centre-570754541444.us-central1.run.app/)  
**Target Audience:** LTA Hackathon Judging Panel & Senior Operations Planners  
**Duration:** Exactly 3 Minutes (180 Seconds)  

---

### 📋 Overview & Director's Cue Sheet

| Timestamp | Phase | Scene / Page | Key Visual Focus | Core Message |
| :--- | :--- | :--- | :--- | :--- |
| **0:00 - 0:25** | **The Hook** | Control Room (Page 1) | Executive KPI cards, Active Scenario Selector, Dark/Light executive theme | Every night, track access is contested between renewals and passenger service. |
| **0:25 - 0:55** | **The Engine** | Schedule Timeline (Page 2) | Continuous Work Capsules, Pearl markers, Single-week pills, Filters | CP-SAT solver achieves 100% feasibility, zero hard breaches across all 14 rules in <1.5s. |
| **0:55 - 1:25** | **The Network** | Network Capacity (Page 3) | Sequential gradient heatmap (Navy vs Alert Red), Bottleneck location inspection | Real-time capacity visibility: distinguishing 100% normal utilisation from true excess. |
| **1:25 - 1:55** | **Digital Twin** | Operations Sandbox (Page 5) | Emergency capacity cut, One-click HotReplanner, Churn metric | Real-world resilience: when urgent defects strike, replan in seconds with minimal churn. |
| **1:55 - 2:25** | **The Human Touch** | Passenger Impact (Page 6) & Brief (Page 7) | ECLO commuter volume curve, 2 AM shift handover printable briefing | Balancing engineering possessions against passenger impact; empowering the 2 AM controller. |
| **2:25 - 3:00** | **Judging Panel** | Validator & Downloads (Page 8) | Reviewer Test Instance Uploader, Live CP-SAT solve, 14/14 rules PASS | Hidden test instance live evaluation: upload, solve in 1s, verify, and download submission ZIP. |

---

### 🎙️ Shot-by-Shot Script & Narration

#### Scene 1: The Hook & Executive Control Room (0:00 - 0:25)
- **Visual Setup:** Screen opens on `Page 1: Control Room` in crisp Executive Day Mode (`#F8FAFC` slate canvas, pure white elevated cards, `#0F172A` deep navy typography). Camera gently pans across the four KPI cards (`100% Feasible`, `0 Hard Breaches`, `14 Contracts Scheduled`, `Objective Score`).
- **On-Screen Action:**
  1. Point out the sidebar **Dataset & Instance** selector: reviewers can effortlessly toggle between the pre-computed official benchmark and uploading custom/hidden test instances (CSVs or ZIP).
  2. Hover over the Scenario selector on the sidebar, switching from `Scenario A` to `Scenario B` and `Scenario C`.
  3. The KPI cards, Delay Cost Breakdown, and Contract Milestone Progress bars update instantaneously.
- **Narrator (Spoken):**
  > *"Every night between 1 AM and 4:30 AM, Singapore's railway network undergoes critical renewals. Every night is contested: multiple capital contracts compete for track access, bringing 750V live-rail traction cutoffs, rolling safety exclusion zones, and shared interchange tunnels.*  
  > *Welcome to NebulaX RailWorks — an enterprise-grade decision support platform, built specifically for LTA's Works Controllers and Reviewers to plan, prove, and dispatch track possessions with zero safety breaches."*

---

#### Scene 2: Mathematical Optimisation & Visual Schedule (0:25 - 0:55)
- **Visual Setup:** Navigate to `Page 2: Schedule`. The screen displays the high-density **Continuous Work Capsules** Gantt chart.
- **On-Screen Action:**
  1. Highlight the rounded 13px capsules spanning multi-week contracts.
  2. Hover over an Alpha Line pearl marker (white center with sapphire blue border) to reveal the rich tooltip: Activity ID, Contract Number, Line, Bound, Week, Access Night, and Co-Share Group.
  3. Toggle the view filter from `Continuous Capsules` to `Discrete Points` and `Contract Milestones`.
- **Narrator (Spoken):**
  > *"Behind this intuitive interface lies an exact mathematical model enforcing all 14 rigid physical and operating rules. Notice how activities are packed into harmonious work capsules. Single-week tasks render as sleek rounded pills, while weekly accesses are tracked with distinct pearl markers for Alpha and Beta lines.*  
  > *The engine mathematically optimizes co-sharing cliques: packing compatible Possession Masters and Co-workers into shared slots, while automatically enforcing traction power shut-offs and cross-line isolation at interchange hubs H01 and H02."*

---

#### Scene 3: Network Capacity Heatmap & Bottleneck Resolution (0:55 - 1:25)
- **Visual Setup:** Navigate to `Page 3: Network`. The screen displays the **Track Capacity Heatmap** across all 20 planning weeks and 36 network sectors.
- **On-Screen Action:**
  1. Scroll through the heatmap, showing the executive sequential gradient: soft mist blue $\to$ deep sapphire $\to$ executive slate navy (`#1E293B`) at 100% full capacity.
  2. Point out that unlike naive tools that paint normal busy tracks in alarming red, our heatmap preserves crimson red (`#DC2626`) strictly for true illegal over-capacity.
  3. Click on sector `SEC:ALP:H01_H02:EB` to display the detailed nightly occupancy breakdown.
- **Narrator (Spoken):**
  > *"Spatial-temporal bottleneck detection is immediate. Our capacity heatmap utilizes an executive sequential color scale: healthy 100% full capacity is rendered in deep slate navy, reserving warning crimson strictly for true over-capacity excess.*  
  > *Controllers can inspect any platform or tunnel sector to see exactly which contractors share possessions, how safety buffers are spaced, and where maintenance headroom remains."*

---

#### Scene 4: Digital Twin Sandbox & Minimal-Churn Re-planning (1:25 - 1:55)
- **Visual Setup:** Navigate to `Page 5: Operations Sandbox`.
- **On-Screen Action:**
  1. Under the **Disruption Engine**, select Week 6, Location `SEC:BET:S13_S14:WB`, and simulate an emergency rail break: reduce capacity from 4 nights to 1 night.
  2. Click the prominent button: **`⚡ Execute HotReplanner (Minimal Churn CP-SAT)`**.
  3. Within 1.2 seconds, the solver re-optimizes. The diff display highlights displaced activities, preserving 94% of the original schedule without ripple disruptions.
- **Narrator (Spoken):**
  > *"In real railway operations, disruptions happen. In our Operations Sandbox, controllers can inject emergency rail defects, urgent unscheduled tamping, or weather halts.*  
  > *With one click, our Large Neighborhood Search HotReplanner re-optimizes the entire schedule in under 2 seconds. It isolates the disrupted sector, relocates displaced work, and minimizes schedule churn — ensuring works teams aren't rescheduled unnecessarily."*

---

#### Scene 5: Commuter ECLO Advisor & 2 AM Shift Handover (1:55 - 2:25)
- **Visual Setup:** Swiftly show `Page 6: Passenger Impact & ECLO`, then transition to `Page 7: Decision Brief`.
- **On-Screen Action:**
  1. On Page 6: Show the hourly passenger exposure curves derived from LTA DataMall telemetry, proving how Scenario C balances engineering hours against commuter disruptions.
  2. On Page 7: Click **`Generate 2 AM Works Controller Handover Briefing`**.
  3. Display the clean, printable HTML shift handover document complete with nightly possession manifests, traction isolation checklists, and emergency buffer zones.
- **Narrator (Spoken):**
  > *"Track access directly impacts passengers. Our ECLO Advisor integrates LTA DataMall hourly passenger volume telemetry, calculating exact commuter disruption to justify extended 1.5x possessions.*  
  > *And for the 2 AM Works Controller on the graveyard shift, our Root-Cause Explainer demystifies milestone bottlenecks, while the Handover Generator produces an instant, print-ready shift brief with critical traction cuts and safety checklists."*

---

#### Scene 6: Reviewer Live Evaluation & Final Proof (2:25 - 3:00)
- **Visual Setup:** Navigate to `Page 8: Validator & Downloads`. Open the **Reviewer / Judge Live Evaluation Panel**.
- **On-Screen Action:**
  1. Show the dedicated dropzone: judges can upload an undisclosed test dataset (as 8 individual CSVs or a single `.zip`).
  2. Demonstrate automatic backfilling: even if reviewers provide only work demand files (`07` & `08`), our system auto-backfills network infrastructure files (`01` through `06`).
  3. Click **`🚀 Run Live Optimization & Validation`**.
  4. The OR-Tools CP-SAT solver optimizes the schedule live on screen in **~1.1 seconds**.
  5. The Official Validator card turns vibrant green: `PASS (100% FEASIBLE) | Hard Violations: 0`.
  6. Click **`📦 Download Official Submission ZIP`** to demonstrate instant compliance artifact export.
- **Narrator (Spoken):**
  > *"Finally, we invite the judging panel to test our system live. On our Validator page or via the sidebar, judges can upload any undisclosed benchmark instance — as raw CSVs or a zip. Our platform automatically ingests the topology, executes CP-SAT live in ~1 second, and runs the official mathematical validator.*  
  > *Zero hard violations. Zero dropped activities. Mathematically proven schedules ready for real-world dispatch. This is NebulaX RailWorks — elevating Singapore's railway operations to new heights."*

---

### 🎨 Visual & Production Guidelines
- **Resolution:** 1080p (1920x1080) or 4K, 60 FPS.
- **Theme:** Default to the crisp, executive Day Mode (`#F8FAFC` background, `#FFFFFF` elevated cards, `#2563EB` Alpha sapphire blue, `#7C3AED` Beta violet, `#0F172A` deep typography).
- **Audio:** Crisp narration with clean microphone, subtle high-tech ambient background track at -22 dB (ducked to -28 dB during speech).
- **Mouse Cursors:** Enable mouse click halos and smooth pointer movement. Highlight clickable elements with gentle zooms or callout boxes.

