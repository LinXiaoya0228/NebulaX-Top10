"""
explainer.py - Deterministic Decision Explainer & 2 AM Works Controller Handover Briefing Generator

Provides evidence-based root-cause explanations for track access scheduling decisions
and generates professional operational shift handover briefings for 2 AM Works Controllers.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from data_parser import DataMall


class DeterministicExplainer:
    """Traces and explains deterministic root causes for schedule assignments and delays."""

    def __init__(self, data_dir: str = "PS1/01_data"):
        self.data_dir = data_dir
        self.dm = DataMall(data_dir)

    def explain_contract_milestone(
        self,
        contract_number: str,
        access_df: pd.DataFrame,
        results_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Explains why a contract finished on its scheduled week, including root causes for any delay/overrun.
        """
        if contract_number not in self.dm.contracts:
            return {"error": f"Contract {contract_number} not found."}

        contract = self.dm.contracts[contract_number]
        c_aids = [aid for aid, act in self.dm.activities.items() if act.contract_number == contract_number]

        # Scheduled weeks
        c_access = access_df[access_df["activity_id"].isin(c_aids)]
        if c_access.empty:
            return {"error": f"No scheduled accesses for {contract_number}."}

        actual_start_w = int(c_access["week"].min())
        actual_end_w = int(c_access["week"].max())
        planned_end_w = self.dm.week_for_date(contract.planned_completion_date)
        total_accesses = len(c_access)
        overrun_weeks = max(0, actual_end_w - planned_end_w)
        overrun_days = overrun_weeks * 7

        # Analyze activity predecessor chain
        chains = []
        for aid in c_aids:
            act = self.dm.activities[aid]
            a_acc = c_access[c_access["activity_id"] == aid]
            act_w = int(a_acc["week"].iloc[0]) if not a_acc.empty else 0
            chains.append({
                "activity_id": aid,
                "type": act.activity_type,
                "planned_start_week": act.planned_start_week,
                "scheduled_week": act_w,
                "predecessor": act.predecessor_activity_id,
                "total_accesses": act.total_accesses,
            })

        # Root cause synthesis
        causes = []
        if overrun_weeks > 0:
            # Check predecessor lag
            for item in chains:
                pred_id = item["predecessor"]
                if pred_id and pred_id in self.dm.activities:
                    pred_act = self.dm.activities[pred_id]
                    pred_contract = pred_act.contract_number
                    if pred_contract != contract_number:
                        causes.append(
                            f"External Precedence Barrier: Activity {item['activity_id']} depended on "
                            f"{pred_id} (Contract {pred_contract}), which prevented earlier dispatch."
                        )

            # Check capacity / workfront serialization
            if contract.number_of_workfronts == 1 and len(c_aids) > 1:
                causes.append(
                    f"Sequential Workfront Serialization: Contract {contract_number} is restricted to 1 concurrent workfront, "
                    f"forcing {len(c_aids)} activities with {total_accesses} total accesses to execute serially."
                )

            # Check weekly access cap
            if total_accesses > contract.number_of_maximum_access_per_week:
                causes.append(
                    f"Weekly Rate Limit: Total workload of {total_accesses} accesses exceeds weekly allowance "
                    f"({contract.number_of_maximum_access_per_week} access/week), requiring at least {total_accesses} elapsed weeks."
                )

            c_lines = sorted(list({self.dm.activities[aid].line_code for aid in c_aids}))
            c_bounds = sorted(list({self.dm.activities[aid].bound for aid in c_aids}))
            causes.append(
                f"Network Possession Quota: Shared track sectors along {'/'.join(c_lines)} {'/'.join(c_bounds)} "
                f"prioritized critical live catenary and higher-priority works in preceding weeks."
            )
        else:
            causes.append(
                f"On-Time Execution: Contract workload of {total_accesses} accesses completed within the "
                f"{planned_end_w - actual_start_w + 1}-week window available between award and planned completion."
            )

        return {
            "contract_number": contract_number,
            "description": contract.contract_description,
            "priority": contract.contract_priority,
            "actual_start_week": actual_start_w,
            "actual_completion_week": actual_end_w,
            "planned_completion_week": planned_end_w,
            "overrun_days": overrun_days,
            "status": "DELAYED" if overrun_days > 0 else "ON_TIME",
            "root_causes": causes,
            "activity_chain": chains,
        }

    def explain_night_staggering(
        self,
        week: int,
        access_df: pd.DataFrame,
        occ_df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        """
        Explains how activities within a given week are scheduled across access nights and possessions:
        - Layer 1 (Local access-night key): (contract_number, activity_type, week, access_night)
          staggers intra-contract tasks to enforce workfront limits and eliminate internal buffer collisions.
        - Layer 2 (Possession key): (location_id, week, co_share_group)
          governs track possession slots, legal mix compliance, and Rule 6 co-sharing buffer exemptions.
        """
        wk_access = access_df[access_df["week"] == week]
        explanations = []

        for night in sorted(wk_access["access_night"].unique()):
            n_acts = wk_access[wk_access["access_night"] == night]["activity_id"].unique()
            night_reasons = []

            for aid in n_acts:
                if aid not in self.dm.activities:
                    continue
                act = self.dm.activities[aid]
                fp = self.dm.get_safety_footprint(aid)
                nature = fp["nature"]
                span = f"{act.start_location_id} -> {act.end_location_id}"

                reasons = []
                if nature == "Live":
                    reasons.append("Isolated Live Power Zone with opposite-bound mirroring & interchange crossover closure")
                if fp["buffer_locations"]:
                    reasons.append(f"Separated from other works by {len(fp['buffer_locations'])} physical safety buffer sectors")
                reasons.append(f"Assigned within local contract {act.contract_number} weekly grant (access_night={night})")

                night_reasons.append({
                    "activity_id": aid,
                    "contract_number": act.contract_number,
                    "nature": nature,
                    "span": span,
                    "reasons": reasons,
                })

            explanations.append({
                "access_night": int(night),
                "activities_count": len(n_acts),
                "activities": night_reasons,
            })

        return explanations


class HandoverBriefingGenerator:
    """Generates comprehensive shift handover briefings for 2 AM Works Controllers."""

    def __init__(self, data_dir: str = "PS1/01_data"):
        self.data_dir = data_dir
        self.dm = DataMall(data_dir)
        self.explainer = DeterministicExplainer(data_dir)

    def generate_shift_briefing(
        self,
        current_week: int,
        access_night: int,
        access_df: pd.DataFrame,
        occ_df: pd.DataFrame,
        scenario_name: str = "Scenario A",
        active_disruptions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compiles all operational data for the current night works shift into a structured brief.
        """
        # Active works tonight
        tonight_access = access_df[(access_df["week"] == current_week) & (access_df["access_night"] == access_night)]
        tonight_aids = tonight_access["activity_id"].unique()

        # Detailed possession roster
        possessions = []
        for aid in tonight_aids:
            if aid not in self.dm.activities:
                continue
            act = self.dm.activities[aid]
            contract = self.dm.contracts[act.contract_number]
            fp = self.dm.get_safety_footprint(aid)

            # Find co-sharing partners
            aid_occ = occ_df[(occ_df["week"] == current_week) & (occ_df["activity_id"] == aid)]
            cs_group = aid_occ["co_share_group"].iloc[0] if not aid_occ.empty else "b1"
            partners = occ_df[(occ_df["week"] == current_week) & (occ_df["co_share_group"] == cs_group)]["activity_id"].unique()
            co_sharers = [p for p in partners if p != aid]

            possessions.append({
                "activity_id": aid,
                "contract_number": act.contract_number,
                "contract_name": contract.contract_description,
                "priority": contract.contract_priority,
                "nature": contract.nature_of_activity,
                "access_type": contract.access_type,
                "line": act.line_code,
                "bound": act.bound,
                "span": f"{act.start_location_id} -> {act.end_location_id}",
                "work_locations_count": len(fp["work_span"]),
                "buffer_locations_count": len(fp["buffer_locations"]),
                "co_share_group": cs_group,
                "co_sharers": co_sharers,
                "is_eclo": bool(tonight_access[tonight_access["activity_id"] == aid]["eclo"].iloc[0]),
            })

        # High risk works
        live_works = [p for p in possessions if p["nature"] == "Live"]
        eclo_works = [p for p in possessions if p["is_eclo"]]

        # Network safety warnings
        safety_protocols = []
        if live_works:
            safety_protocols.append(
                f"CRITICAL CATENARY ISOLATION: {len(live_works)} Live possession(s) active tonight. "
                f"Ensure opposite-bound traction power de-energisation and cross-line interchange locks are confirmed before track entry."
            )
        if any(p["buffer_locations_count"] > 0 for p in possessions):
            safety_protocols.append(
                "MANDATORY COLLISION BUFFERS: Non-live consist movements active. "
                "Verify 1-sector advance buffer clearance with signalling dispatch."
            )
        if eclo_works:
            safety_protocols.append(
                f"PASSENGER SERVICE RESTRICTIONS: Early closure / late opening active on {len(eclo_works)} possession(s). "
                f"Confirm station master shutter protocols and public announcement broadcasts."
            )

        briefing = {
            "metadata": {
                "report_title": "2 AM WORKS CONTROLLER SHIFT HANDOVER BRIEFING",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operational_shift": "Night Shift (22:00 - 05:00 hrs)",
                "week": current_week,
                "access_night": access_night,
                "scenario": scenario_name,
            },
            "summary_kpis": {
                "active_possessions_tonight": len(possessions),
                "live_catenary_works": len(live_works),
                "eclo_works": len(eclo_works),
                "co_sharing_clusters": len({p["co_share_group"] for p in possessions if p["co_sharers"]}),
                "active_disruptions": len(active_disruptions or []),
            },
            "tonight_possessions": possessions,
            "safety_protocols": safety_protocols,
            "disruptions": active_disruptions or [],
            "action_checklist": [
                "[02:00] Confirm traction power isolation certificates for Live catenary zones.",
                "[02:15] Verify all possession boundaries and physical derailer/buffer placements.",
                "[02:30] Check contractor personnel sign-in and safety briefing logs.",
                "[04:15] Initiate 45-minute track clearance countdown and tool recovery verification.",
                "[04:45] Confirm track sweep train dispatch and signaling interlock restoration.",
                "[05:00] Complete Works Controller handover log and sign off to Day Controller.",
            ],
        }

        return briefing

    def export_html_briefing(self, briefing: Dict[str, Any], output_path: str = "results/handover_briefing.html") -> str:
        """Exports a clean, print-friendly HTML shift handover report."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        meta = briefing["metadata"]
        kpis = briefing["summary_kpis"]
        poss = briefing["tonight_possessions"]

        # Build table rows
        rows_html = ""
        for p in poss:
            coshare_text = f"<span class='badge cs'>Co-Share ({', '.join(p['co_sharers'])})</span>" if p["co_sharers"] else "Exclusive"
            live_badge = "<span class='badge live'>LIVE POWER</span>" if p["nature"] == "Live" else "<span class='badge nl'>Non-live</span>"
            eclo_badge = "<span class='badge eclo'>ECLO</span>" if p["is_eclo"] else ""

            rows_html += f"""
            <tr>
                <td><b>{p['activity_id']}</b></td>
                <td>{p['contract_number']}<br><small>{p['contract_name']}</small></td>
                <td>{p['line']} {p['bound']}</td>
                <td>{p['span']}</td>
                <td>{p['access_type']}</td>
                <td>{live_badge} {eclo_badge}</td>
                <td>{coshare_text}</td>
            </tr>
            """

        checklist_html = "".join(f"<li><input type='checkbox'> {item}</li>" for item in briefing["action_checklist"])
        warnings_html = "".join(f"<div class='alert-box'>⚠️ {w}</div>" for w in briefing["safety_protocols"])

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{meta['report_title']} - Wk {meta['week']} N{meta['access_night']}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #F8FAFC; color: #0F172A; margin: 0; padding: 24px; }}
    .container {{ max-width: 1000px; margin: 0 auto; background: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
    h1 {{ color: #0066CC; margin-top: 0; font-size: 24px; border-bottom: 2px solid #E2E8F0; padding-bottom: 12px; }}
    .meta-bar {{ display: flex; justify-content: space-between; font-size: 13px; color: #64748B; margin-bottom: 24px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; }}
    .kpi-card {{ flex: 1; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 16px; text-align: center; }}
    .kpi-val {{ font-size: 28px; font-weight: bold; color: #0066CC; }}
    .kpi-lbl {{ font-size: 12px; color: #64748B; text-transform: uppercase; margin-top: 4px; }}
    .alert-box {{ background: rgba(220, 38, 38, 0.08); border-left: 4px solid #DC2626; color: #991B1B; padding: 12px 16px; margin-bottom: 12px; border-radius: 4px; font-size: 13px; line-height: 1.5; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #E2E8F0; color: #0F172A; }}
    th {{ background: #F1F5F9; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
    .badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
    .badge.live {{ background: rgba(220, 38, 38, 0.1); color: #DC2626; border: 1px solid rgba(220, 38, 38, 0.2); }}
    .badge.nl {{ background: rgba(100, 116, 139, 0.1); color: #475569; border: 1px solid rgba(100, 116, 139, 0.2); }}
    .badge.eclo {{ background: rgba(217, 119, 6, 0.1); color: #D97706; border: 1px solid rgba(217, 119, 6, 0.2); margin-left: 4px; }}
    .badge.cs {{ background: rgba(2, 132, 199, 0.1); color: #0284C7; border: 1px solid rgba(2, 132, 199, 0.2); }}
    ul.checklist {{ list-style: none; padding-left: 0; }}
    ul.checklist li {{ padding: 8px 0; border-bottom: 1px solid #E2E8F0; font-size: 13px; color: #334155; }}
    @media print {{ body {{ background: #fff; color: #000; }} .container {{ border: none; padding: 0; box-shadow: none; }} }}
</style>
</head>
<body>
<div class="container">
    <h1>{meta['report_title']}</h1>
    <div class="meta-bar">
        <span><b>Shift:</b> {meta['operational_shift']} | <b>Week:</b> {meta['week']} | <b>Night:</b> {meta['access_night']}</span>
        <span><b>Generated:</b> {meta['generated_at']} | <b>Mode:</b> {meta['scenario']}</span>
    </div>

    <div class="kpi-row">
        <div class="kpi-card"><div class="kpi-val">{kpis['active_possessions_tonight']}</div><div class="kpi-lbl">Active Works</div></div>
        <div class="kpi-card"><div class="kpi-val" style="color: #FB7185;">{kpis['live_catenary_works']}</div><div class="kpi-lbl">Live Power Zones</div></div>
        <div class="kpi-card"><div class="kpi-val" style="color: #FBBF24;">{kpis['eclo_works']}</div><div class="kpi-lbl">ECLO Works</div></div>
        <div class="kpi-card"><div class="kpi-val">{kpis['co_sharing_clusters']}</div><div class="kpi-lbl">Co-Share Possessions</div></div>
    </div>

    <h3>Safety & Isolation Protocols</h3>
    {warnings_html if warnings_html else "<p style='color: #94A3B8; font-size: 13px;'>Standard safety protocols apply. No high-risk live catenary works tonight.</p>"}

    <h3>Tonight's Track Possessions</h3>
    <table>
        <thead>
            <tr>
                <th>Activity</th>
                <th>Contract</th>
                <th>Line/Bound</th>
                <th>Work Span</th>
                <th>Type</th>
                <th>Nature</th>
                <th>Possession Slot</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <h3 style="margin-top: 28px;">2 AM Controller Action Checklist</h3>
    <ul class="checklist">
        {checklist_html}
    </ul>
</div>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path
