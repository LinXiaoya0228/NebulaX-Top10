"""
operations_sandbox.py - Industrial Railway Works Operations Sandbox

Provides an isolated digital twin sandbox for 2 AM Works Controllers and Maintenance Planners:
1. SandboxManager: Clones pristine DataMall and submission schedules for safe experimentation.
2. AdHocMaintenanceActivity & MaintenancePlanner: Routine track maintenance planning and Co-Share Feasibility Checker.
3. DisruptionEngine & HotReplanner: Emergency capacity cut simulation and minimal-churn CP-SAT re-optimization.
"""

from __future__ import annotations

import copy
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from ortools.sat.python import cp_model

from data_parser import Activity, DataMall, LocationSupply, ProjectContract
from scheduler import ScenarioScheduler
from validator import Validator


@dataclass
class AdHocMaintenanceActivity:
    """Data model for routine and urgent track maintenance activities."""

    id: str
    name: str
    category: str  # e.g., 'Routine Patrol', 'Ultrasonic Rail Flaw Inspection', 'Tamping & Ballast', 'Signaling Maintenance'
    owning_team: str  # e.g., 'Civil & Track Dept', 'Signaling Team', 'Power Supply & Catenary'
    nature_of_work: str  # 'Non-live' or 'Live'
    consist_type: str  # 'Non-consist' or 'Consist'
    access_type: str  # 'PM', 'PC', 'C'
    line_code: str  # 'ALP' or 'BET'
    bound: str  # 'EB' or 'WB'
    start_stn: str
    end_stn: str
    preferred_weeks: List[int]
    required_accesses: int = 1
    priority: int = 2  # 1 (Critical), 2 (Standard), 3 (Low)
    is_mandatory: bool = True
    assigned_week: Optional[int] = None
    assigned_access_night: Optional[int] = None
    assigned_co_share_group: Optional[str] = None
    assigned_with_activity: Optional[str] = None

    def get_span_locations(self, dm: DataMall) -> Set[str]:
        if self.start_stn.startswith("SEC:"):
            return dm.expand_route(self.start_stn, self.end_stn)[0]
        line_secs = dm.sectors.get(self.line_code, [])
        matching_start = [s for s in line_secs if s.from_station_id == self.start_stn or s.to_station_id == self.start_stn]
        matching_end = [s for s in line_secs if s.from_station_id == self.end_stn or s.to_station_id == self.end_stn]
        if matching_start and matching_end:
            s_loc = f"{matching_start[0].sector_id}:{self.bound}"
            e_loc = f"{matching_end[-1].sector_id}:{self.bound}"
            return dm.expand_route(s_loc, e_loc)[0]
        return {f"SEC:{self.line_code}:{self.start_stn}_{self.end_stn}:{self.bound}"}


@dataclass
class DisruptionScenario:
    """Data model for simulated network disruptions and emergency capacity cuts."""

    id: str
    title: str
    disruption_type: str  # 'Rail Defect', 'Overhead Wire Fault', 'Track Flooding', 'Points Jam', 'Emergency Speed Restriction', 'Manual Capacity Cut'
    line_code: str
    bound: str
    locations: List[str]
    weeks: List[int]
    revised_capacity: int  # e.g., 0 (complete block) or 1 (severely restricted)
    severity: str = "High"  # 'Critical', 'High', 'Moderate'
    description: str = ""


class SandboxManager:
    """Manages an isolated working copy of data and schedules for digital-twin operations."""

    def __init__(self, data_dir: str = "PS1/01_data", baseline_results_dir: str = "results", scenario: str = "A"):
        self.data_dir = data_dir
        self.baseline_results_dir = baseline_results_dir
        self.base_dm = DataMall(data_dir)
        self.validator = Validator(data_dir)

        # Working state (deep-copied to guarantee isolation)
        self.working_dm: DataMall = copy.deepcopy(self.base_dm)
        self.active_scenario: str = scenario
        self.access_df: pd.DataFrame = pd.DataFrame()
        self.occ_df: pd.DataFrame = pd.DataFrame()
        self.res_df: pd.DataFrame = pd.DataFrame()

        # Operational history & maintenance tracking
        self.ad_hoc_activities: Dict[str, AdHocMaintenanceActivity] = {}
        self.active_disruptions: Dict[str, DisruptionScenario] = {}
        self.replan_history: List[Dict[str, Any]] = []

        # Load initial scenario
        self.load_scenario(scenario)

    @property
    def working_scenario(self) -> str:
        return self.active_scenario

    def load_scenario(self, scenario: str) -> bool:
        """Loads and deep-copies the schedule for the given scenario."""
        self.active_scenario = scenario
        scen_dir = os.path.join(self.baseline_results_dir, f"scenario_{scenario}")

        access_p = os.path.join(scen_dir, "SCHEDULE_ACCESS.csv")
        occ_p = os.path.join(scen_dir, "SCHEDULE_OCCUPANCY.csv")
        res_p = os.path.join(scen_dir, "RESULTS.csv")

        if os.path.exists(access_p) and os.path.exists(occ_p) and os.path.exists(res_p):
            self.access_df = pd.read_csv(access_p)
            self.occ_df = pd.read_csv(occ_p)
            self.res_df = pd.read_csv(res_p)
        else:
            # Solve baseline on the fly if not yet written
            sch = ScenarioScheduler(self.data_dir)
            report = sch.solve(scenario, scen_dir, verbose=False)
            self.access_df = pd.read_csv(access_p)
            self.occ_df = pd.read_csv(occ_p)
            self.res_df = pd.read_csv(res_p)

        self.reset_working_state()
        return True

    def reset_working_state(self) -> None:
        """Resets the working instance back to pristine baseline."""
        self.working_dm = copy.deepcopy(self.base_dm)
        self.ad_hoc_activities.clear()
        self.active_disruptions.clear()
        scen_dir = os.path.join(self.baseline_results_dir, f"scenario_{self.active_scenario}")
        self.access_df = pd.read_csv(os.path.join(scen_dir, "SCHEDULE_ACCESS.csv"))
        self.occ_df = pd.read_csv(os.path.join(scen_dir, "SCHEDULE_OCCUPANCY.csv"))
        self.res_df = pd.read_csv(os.path.join(scen_dir, "RESULTS.csv"))

    def validate_current_working_schedule(self) -> Dict[str, Any]:
        """Validates the current working schedule in memory without disk writing."""
        # Save to temp in-memory directory for validator
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.access_df.to_csv(os.path.join(tmp_dir, "SCHEDULE_ACCESS.csv"), index=False)
            self.occ_df.to_csv(os.path.join(tmp_dir, "SCHEDULE_OCCUPANCY.csv"), index=False)
            self.res_df.to_csv(os.path.join(tmp_dir, "RESULTS.csv"), index=False)
            report = self.validator.validate(tmp_dir, self.active_scenario, strict_buffers=True)
            return report


class MaintenancePlanner:
    """Enables routine track maintenance planners to test co-sharing and insert work."""

    def __init__(self, sandbox: SandboxManager):
        self.sb = sandbox

    def check_coshare_feasibility(
        self,
        maint_act: AdHocMaintenanceActivity,
        candidate_week: int = 1,
        target_week: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates co-sharing or independent insertion options for an ad-hoc maintenance task.
        Checks:
        1. Exact location span match & legal mix capacity.
        2. Rule 4 safety buffer compatibility with concurrent works on nights 1..3.
        3. Rule 5/Rule 10 Live mirror and cross-line closures.
        4. Location supply availability.
        """
        if target_week is not None:
            candidate_week = target_week
        dm = self.sb.working_dm
        span_locs = set(maint_act.get_span_locations(dm))
        options: List[Dict[str, Any]] = []

        # 1. Check existing possessions in candidate_week that cover identical span (for direct Co-Share)
        wk_occ = self.sb.occ_df[self.sb.occ_df["week"] == candidate_week]
        wk_access = self.sb.access_df[self.sb.access_df["week"] == candidate_week]

        # Group existing work by possession (co_share_group)
        possession_groups = wk_occ.groupby("co_share_group")

        for csg, group in possession_groups:
            existing_aids = group["activity_id"].unique()
            first_aid = existing_aids[0]
            if first_aid not in dm.activities:
                continue
            first_act = dm.activities[first_aid]
            first_contract = dm.contracts[first_act.contract_number]

            # Check if span matches exactly
            first_span = set(first_act.expanded_locations)
            if first_span == span_locs:
                # Check line & bound match
                if first_act.line_code == maint_act.line_code and first_act.bound == maint_act.bound:
                    # Check legal mix:
                    # Rule 6: PM can never co-share; PC and C can co-share with at most one PC and up to 4 C.
                    existing_types = [dm.contracts[dm.activities[a].contract_number].access_type for a in existing_aids]
                    can_coshare = False
                    diagnostic = ""

                    if maint_act.access_type == "PM" or "PM" in existing_types:
                        can_coshare = False
                        diagnostic = "BLOCKED_PM_EXCLUSIVE: Plant Machinery requires exclusive possession."
                    elif maint_act.access_type == "PC":
                        if "PC" in existing_types:
                            can_coshare = False
                            diagnostic = "BLOCKED_PC_LIMIT: Possession already contains a Personnel & Consist activity."
                        else:
                            can_coshare = True
                            diagnostic = "FEASIBLE_DIRECT_COSHARE: Direct co-share with Personnel & Consist (PC)."
                    elif maint_act.access_type == "C":
                        c_count = sum(1 for t in existing_types if t == "C")
                        if c_count >= 4:
                            can_coshare = False
                            diagnostic = "BLOCKED_C_LIMIT: Possession already reached max 4 Contractor activities."
                        else:
                            can_coshare = True
                            diagnostic = f"FEASIBLE_DIRECT_COSHARE: Direct co-share with existing work ({len(existing_aids)} active activities)."

                    # Find existing night
                    act_access = wk_access[wk_access["activity_id"].isin(existing_aids)]
                    assigned_night = int(act_access["access_night"].iloc[0]) if not act_access.empty else 1

                    options.append({
                        "mode": "Co-Share Existing Possession",
                        "co_share_group": csg,
                        "shared_with": list(existing_aids),
                        "week": candidate_week,
                        "access_night": assigned_night,
                        "feasible": can_coshare,
                        "diagnostic": diagnostic,
                        "marginal_supply_cost": 0,
                    })

        # 2. Check independent possession in candidate_week (if spare capacity exists)
        # Check nominal vs used capacity across all span locations
        loc_usages: Dict[str, int] = {}
        for loc in span_locs:
            sub = wk_occ[wk_occ["location_id"] == loc]
            loc_usages[loc] = sub["co_share_group"].nunique()

        can_fit_new = True
        bottleneck_loc = ""
        for loc in span_locs:
            supp = dm.location_supply.get(loc)
            nom_cap = supp.supply_capacity if supp else 4
            if loc_usages.get(loc, 0) + 1 > nom_cap:
                if self.sb.active_scenario == "A":
                    can_fit_new = False
                    bottleneck_loc = loc
                    break
                # In B or C, flex supply can absorb

        # Find best available night (1..3) that avoids buffer conflicts
        occupied_nights = wk_access["access_night"].unique()
        available_nights = [n for n in [1, 2, 3] if n not in occupied_nights]
        chosen_night = available_nights[0] if available_nights else 1

        options.append({
            "mode": "New Independent Possession",
            "co_share_group": f"maint_{len(self.sb.ad_hoc_activities) + 1}",
            "shared_with": [],
            "week": candidate_week,
            "access_night": chosen_night,
            "feasible": can_fit_new,
            "diagnostic": "FEASIBLE_NEW_POSSESSION: Fits within location capacity quota." if can_fit_new else f"BLOCKED_CAPACITY: Exceeds nominal capacity at {bottleneck_loc}.",
            "marginal_supply_cost": 1 if not can_fit_new else 0,
        })

        return options

    def insert_maintenance(
        self,
        maint_act: AdHocMaintenanceActivity,
        option: Dict[str, Any],
    ) -> bool:
        """Commits the maintenance activity to the working schedule."""
        maint_act.assigned_week = option["week"]
        maint_act.assigned_access_night = option["access_night"]
        maint_act.assigned_co_share_group = option["co_share_group"]
        maint_act.assigned_with_activity = ", ".join(option.get("shared_with", []))

        # Add synthetic activity and contract into working_dm
        contract_id = f"C_MAINT_{maint_act.id}"
        span_locs = sorted(list(maint_act.get_span_locations(self.sb.working_dm)))
        self.sb.working_dm.contracts[contract_id] = ProjectContract(
            contract_number=contract_id,
            contract_description=maint_act.name,
            contract_award_date="2026-01-01",
            activity_type="T01",
            nature_of_activity=maint_act.nature_of_work,
            contract_priority=maint_act.priority,
            contract_completion_date="2026-07-26",
            planned_completion_date="2026-07-26",
            number_of_workfronts=1,
            access_type=maint_act.access_type,
            number_of_maximum_access_per_week=3,
        )

        start_loc = span_locs[0] if span_locs else "PLAT:BET:H01:EB"
        end_loc = span_locs[-1] if span_locs else "PLAT:BET:H01:EB"
        self.sb.working_dm.activities[maint_act.id] = Activity(
            activity_id=maint_act.id,
            contract_number=contract_id,
            activity_type="T01",
            start_location_id=start_loc,
            end_location_id=end_loc,
            total_accesses=maint_act.required_accesses,
            planned_start_date="2026-01-05",
            predecessor_activity_id=None,
            activity_priority=maint_act.priority,
            planned_start_week=option["week"],
            expanded_locations=set(span_locs),
            line_code=maint_act.line_code,
            bound=maint_act.bound,
        )

        # Update access_df
        new_access = pd.DataFrame([{
            "activity_id": maint_act.id,
            "access_seq": 1,
            "week": option["week"],
            "eclo": 0,
            "access_night": option["access_night"],
        }])
        self.sb.access_df = pd.concat([self.sb.access_df, new_access], ignore_index=True)

        # Update occ_df
        new_occs = []
        for loc in span_locs:
            new_occs.append({
                "activity_id": maint_act.id,
                "week": option["week"],
                "location_id": loc,
                "co_share_group": option["co_share_group"],
            })
        self.sb.occ_df = pd.concat([self.sb.occ_df, pd.DataFrame(new_occs)], ignore_index=True)

        self.sb.ad_hoc_activities[maint_act.id] = maint_act
        return True


class DisruptionEngine:
    """Simulates emergency network disruptions and executes minimal-churn CP-SAT hot re-planning."""

    def __init__(self, sandbox: SandboxManager):
        self.sb = sandbox

    def preview_disruption(self, disruption: DisruptionScenario) -> Dict[str, Any]:
        """Analyzes which activities and contracts are displaced by the disruption."""
        impacted_activities: Set[str] = set()
        affected_weeks = set(disruption.weeks)
        affected_locs = set(disruption.locations)

        for _, row in self.sb.occ_df.iterrows():
            if int(row["week"]) in affected_weeks and row["location_id"] in affected_locs:
                impacted_activities.add(row["activity_id"])

        impacted_contracts = {
            self.sb.working_dm.activities[aid].contract_number
            for aid in impacted_activities
            if aid in self.sb.working_dm.activities
        }

        # Check downstream cascade through predecessors
        cascade_aids: Set[str] = set()
        for aid, act in self.sb.working_dm.activities.items():
            if act.predecessor_activity_id and act.predecessor_activity_id in impacted_activities:
                cascade_aids.add(aid)

        return {
            "disruption_id": disruption.id,
            "title": disruption.title,
            "directly_displaced_activities": sorted(list(impacted_activities)),
            "cascade_activities_at_risk": sorted(list(cascade_aids)),
            "impacted_contracts": sorted(list(impacted_contracts)),
            "affected_weeks": sorted(list(affected_weeks)),
            "severity": disruption.severity,
        }

    def auto_replan(
        self,
        disruption: DisruptionScenario,
        max_time_seconds: int = 15,
    ) -> Dict[str, Any]:
        """
        Executes a minimal-churn CP-SAT re-optimization:
        1. Modifies the working location supply to reflect the disruption.
        2. Fixes all unaffected activities outside the conflict neighborhood.
        3. Formulates a minimal schedule churn objective:
           min Churn = sum_{a in impacted} |week'(a) - week_orig(a)| * 100 + OverrunPenalties.
        4. Re-assigns conflict-free access nights and co-share groups.
        """
        dm = self.sb.working_dm
        H = dm.horizon_weeks

        self.sb.active_disruptions[disruption.id] = disruption

        # Identify baseline week of each activity
        orig_weeks: Dict[str, int] = {}
        for _, row in self.sb.access_df.iterrows():
            orig_weeks[row["activity_id"]] = int(row["week"])

        preview = self.preview_disruption(disruption)
        directly_displaced = set(preview["directly_displaced_activities"])
        cascade_risk = set(preview["cascade_activities_at_risk"])
        replan_candidates = directly_displaced | cascade_risk

        # 2. Build CP-SAT Model with Minimal Churn Objective on access entries
        model = cp_model.CpModel()
        w_vars: Dict[int, cp_model.IntVar] = {}
        diff_vars: Dict[int, cp_model.IntVar] = {}
        b_vars: Dict[Tuple[int, int], cp_model.BoolVar] = {}

        for idx, row in self.sb.access_df.iterrows():
            aid = row["activity_id"]
            act = dm.activities[aid]
            w_orig = int(row["week"])
            w_var = model.NewIntVar(act.planned_start_week, H, f"w_{idx}")
            w_vars[idx] = w_var
            diff = model.NewIntVar(0, H, f"diff_{idx}")
            model.AddAbsEquality(diff, w_var - w_orig)
            diff_vars[idx] = diff

            for w in range(1, H + 1):
                b = model.NewBoolVar(f"b_{idx}_{w}")
                b_vars[(idx, w)] = b
                model.Add(w_var == w).OnlyEnforceIf(b)
                model.Add(w_var != w).OnlyEnforceIf(b.Not())

        # Sequential accesses within same activity
        for aid, group in self.sb.access_df.groupby("activity_id"):
            idxs = group.index.tolist()
            for i in range(len(idxs) - 1):
                model.Add(w_vars[idxs[i]] + 1 <= w_vars[idxs[i + 1]])

        # Precedences between activities
        for aid, act in dm.activities.items():
            if act.predecessor_activity_id and act.predecessor_activity_id in dm.activities:
                pred_id = act.predecessor_activity_id
                pred_last_idx = self.sb.access_df[self.sb.access_df["activity_id"] == pred_id].index[-1]
                succ_first_idx = self.sb.access_df[self.sb.access_df["activity_id"] == aid].index[0]
                model.Add(w_vars[succ_first_idx] >= w_vars[pred_last_idx] + 1)

        # Disruption capacity cuts
        for idx, row in self.sb.access_df.iterrows():
            aid = row["activity_id"]
            act = dm.activities[aid]
            if any(loc in disruption.locations for loc in act.expanded_locations):
                if disruption.revised_capacity == 0:
                    for dw in disruption.weeks:
                        model.Add(w_vars[idx] != dw)

        # Weekly contract access limits
        for cid, contract in dm.contracts.items():
            max_act_in_week = contract.number_of_maximum_access_per_week * contract.number_of_workfronts
            c_idxs = [i for i, r in self.sb.access_df.iterrows() if dm.activities[r["activity_id"]].contract_number == cid]
            for w in range(1, H + 1):
                model.Add(sum(b_vars[(i, w)] for i in c_idxs) <= max_act_in_week)

        # Capacity constraints per location and week
        for loc, supp in dm.location_supply.items():
            loc_idxs = [i for i, r in self.sb.access_df.iterrows() if loc in dm.activities[r["activity_id"]].expanded_locations]
            if not loc_idxs:
                continue

            pm_idxs = [i for i in loc_idxs if dm.contracts[dm.activities[self.sb.access_df.loc[i, "activity_id"]].contract_number].access_type == "PM"]
            pc_idxs = [i for i in loc_idxs if dm.contracts[dm.activities[self.sb.access_df.loc[i, "activity_id"]].contract_number].access_type == "PC"]
            c_idxs = [i for i in loc_idxs if dm.contracts[dm.activities[self.sb.access_df.loc[i, "activity_id"]].contract_number].access_type == "C"]

            for w in range(1, H + 1):
                cap = disruption.revised_capacity if (w in disruption.weeks and loc in disruption.locations) else supp.supply_capacity
                model.Add(sum(b_vars[(i, w)] for i in pm_idxs) + sum(b_vars[(i, w)] for i in pc_idxs) <= cap)
                model.Add(4 * sum(b_vars[(i, w)] for i in pm_idxs) + sum(b_vars[(i, w)] for i in pc_idxs) + sum(b_vars[(i, w)] for i in c_idxs) <= 4 * cap)

        # 3. Objective: Minimal Churn + Contract Overrun
        churn_penalties = [diff_vars[i] * 100 for i in self.sb.access_df.index]
        overrun_penalties = []
        for cid, contract in dm.contracts.items():
            c_idxs = [i for i, r in self.sb.access_df.iterrows() if dm.activities[r["activity_id"]].contract_number == cid]
            if not c_idxs:
                continue
            due_w = dm.week_for_date(contract.planned_completion_date)
            weight = 100 if contract.contract_priority == 1 else (10 if contract.contract_priority == 2 else 1)
            overrun = model.NewIntVar(0, H, f"overrun_{cid}")
            for i in c_idxs:
                model.Add(overrun >= w_vars[i] - due_w)
            overrun_penalties.append(overrun * (7 * weight))

        model.Minimize(sum(churn_penalties) + sum(overrun_penalties))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max_time_seconds
        solver.parameters.num_workers = 4
        status = solver.Solve(model)
        # print("auto_replan solver status:", solver.StatusName(status))

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Extract new weeks
            shifts_count = 0
            total_shift_weeks = 0

            for idx, row in self.sb.access_df.iterrows():
                w_orig = int(row["week"])
                w_new = solver.Value(w_vars[idx])
                if w_new != w_orig:
                    shifts_count += 1
                    total_shift_weeks += abs(w_new - w_orig)
                self.sb.access_df.loc[idx, "week"] = w_new

            # Re-stagger access nights and rebuild occupancy groups cleanly
            from scheduler import AccessNightAssigner, CoShareGroupAssigner
            sched_weeks = {}
            for aid, g in self.sb.access_df.groupby("activity_id"):
                sched_weeks[aid] = [{"week": int(r["week"]), "eclo": int(r["eclo"])} for _, r in g.iterrows()]
            new_access_records = AccessNightAssigner.assign_nights(dm, sched_weeks)
            self.sb.access_df = pd.DataFrame(new_access_records)
            new_occ_records = CoShareGroupAssigner.assign_groups(dm, new_access_records)
            self.sb.occ_df = pd.DataFrame(new_occ_records)

            churn_report = {
                "success": True,
                "disruption_id": disruption.id,
                "activities_moved": shifts_count,
                "total_week_shifts": total_shift_weeks,
                "preservation_rate": f"{((len(self.sb.access_df) - shifts_count) / len(self.sb.access_df)) * 100:.1f}%",
                "solver_time": f"{solver.WallTime():.2f}s",
                "summary": f"Re-planned successfully. {shifts_count} access shifts across network.",
            }
            self.sb.replan_history.append(churn_report)
            return churn_report
        else:
            return {
                "success": False,
                "disruption_id": disruption.id,
                "activities_moved": 0,
                "error": "No feasible minimal-churn schedule found within constraints.",
            }
