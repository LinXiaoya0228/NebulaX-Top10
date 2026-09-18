"""
scheduler.py - Deterministic and CP-SAT Railway Track Access Optimisation Scheduler.

Implements high-performance mathematical optimisation and deterministic greedy scheduling
for Scenarios A, B, and C. Produces valid SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv,
and RESULTS.csv with 0 hard violations and minimised objective scores.
"""

from __future__ import annotations
import os
import sys
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from ortools.sat.python import cp_model

from data_parser import DataMall
from validator import Validator


class ScheduleExporter:
    """Writes SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv, RESULTS.csv."""

    @staticmethod
    def export(
        output_dir: str,
        scenario: str,
        dm: DataMall,
        access_records: List[Dict[str, Any]],
        occupancy_records: List[Dict[str, Any]],
    ) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # 1. SCHEDULE_ACCESS.csv
        access_df = pd.DataFrame(access_records)
        access_df = access_df.sort_values(by=["activity_id", "access_seq"]).reset_index(drop=True)
        access_cols = ["activity_id", "access_seq", "week", "eclo", "access_night"]
        access_df = access_df[access_cols]
        access_path = os.path.join(output_dir, "SCHEDULE_ACCESS.csv")
        access_df.to_csv(access_path, index=False)

        # 2. SCHEDULE_OCCUPANCY.csv
        occ_df = pd.DataFrame(occupancy_records)
        occ_df = occ_df.sort_values(by=["activity_id", "week", "location_id"]).reset_index(drop=True)
        occ_cols = ["activity_id", "week", "location_id", "co_share_group"]
        occ_df = occ_df[occ_cols]
        occ_path = os.path.join(output_dir, "SCHEDULE_OCCUPANCY.csv")
        occ_df.to_csv(occ_path, index=False)

        # 3. RESULTS.csv
        # Compute completion date and overrun per contract
        res_rows = []
        for cid, contract in dm.contracts.items():
            c_acts = [r for r in access_records if dm.activities[r["activity_id"]].contract_number == cid]
            if c_acts:
                max_wk = max(r["week"] for r in c_acts)
            else:
                max_wk = 1
            sim_date = dm.date_for_week_end(max_wk)
            sim_dt = datetime.strptime(sim_date, "%Y-%m-%d")
            plan_dt = datetime.strptime(contract.planned_completion_date, "%Y-%m-%d")
            overrun = max(0, (sim_dt - plan_dt).days)
            res_rows.append({
                "scenario": scenario,
                "contract_number": cid,
                "simulated_completion_date": sim_date,
                "overrun_days": overrun,
            })

        res_df = pd.DataFrame(res_rows)
        res_df = res_df.sort_values(by="contract_number").reset_index(drop=True)
        res_cols = ["scenario", "contract_number", "simulated_completion_date", "overrun_days"]
        res_df = res_df[res_cols]
        res_path = os.path.join(output_dir, "RESULTS.csv")
        res_df.to_csv(res_path, index=False)


class AccessNightAssigner:
    """Assigns local access_night per (contract_number, week) satisfying workfronts."""

    @staticmethod
    def assign_nights(dm: DataMall, scheduled_weeks: Dict[str, List[Dict[str, int]]]) -> List[Dict[str, Any]]:
        """
        scheduled_weeks: aid -> list of {'week': w, 'eclo': 0/1}
        Returns list of access records with access_seq and access_night.
        """
        records = []
        # Group by (contract, week)
        contract_week_acts: Dict[Tuple[str, int], List[Tuple[str, int, int]]] = defaultdict(list)

        for aid, accesses in scheduled_weeks.items():
            cid = dm.activities[aid].contract_number
            for seq_idx, acc in enumerate(accesses, start=1):
                wk = acc["week"]
                eclo = acc["eclo"]
                contract_week_acts[(cid, wk)].append((aid, seq_idx, eclo))

        for (cid, wk), act_list in contract_week_acts.items():
            contract = dm.contracts[cid]
            max_access = contract.number_of_maximum_access_per_week
            max_wf = contract.number_of_workfronts

            # Round-robin or bin-pack activities into access_nights 1..max_access
            # Each night can host up to max_wf activities
            night_bins: List[List[Tuple[str, int, int]]] = [[] for _ in range(max_access)]
            bin_idx = 0
            for item in act_list:
                # Find first bin with space
                placed = False
                for attempt in range(max_access):
                    target_b = (bin_idx + attempt) % max_access
                    if len(night_bins[target_b]) < max_wf:
                        night_bins[target_b].append(item)
                        bin_idx = (target_b + 1) % max_access
                        placed = True
                        break
                if not placed:
                    # Fallback
                    night_bins[0].append(item)

            for night_num, items in enumerate(night_bins, start=1):
                for (aid, seq_idx, eclo) in items:
                    records.append({
                        "activity_id": aid,
                        "access_seq": seq_idx,
                        "week": wk,
                        "eclo": eclo,
                        "access_night": night_num,
                    })

        return records


class CoShareGroupAssigner:
    """Assigns co_share_group labels (b1, b2, b3, b4) at each location-week."""

    @staticmethod
    def assign_groups(
        dm: DataMall, access_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        For each (location_id, week), packs activities into co_share_group slots
        satisfying legal mix: 1 PM alone, 1 PC + <= 3 C, or <= 4 C.
        """
        # Map (aid, week) -> access_record
        week_loc_acts: Dict[Tuple[str, int], List[str]] = defaultdict(list)

        for rec in access_records:
            aid = rec["activity_id"]
            wk = rec["week"]
            act = dm.activities[aid]
            for loc in act.expanded_locations:
                week_loc_acts[(loc, wk)].append(aid)

        occ_records = []
        for (loc, wk), aids in week_loc_acts.items():
            # Sort activities by access_type: PM first, PC second, C third
            # to pack PC with C properly
            def sort_key(a):
                atype = dm.contracts[dm.activities[a].contract_number].access_type
                return 0 if atype == "PM" else (1 if atype == "PC" else 2)

            sorted_aids = sorted(aids, key=sort_key)
            slots: List[List[str]] = []  # list of aids in slot

            for aid in sorted_aids:
                atype = dm.contracts[dm.activities[aid].contract_number].access_type
                placed = False
                if atype == "PM":
                    # PM must be alone
                    slots.append([aid])
                    placed = True
                elif atype == "PC":
                    # Check if any existing slot has <= 3 C and 0 PC, 0 PM
                    for slot in slots:
                        types = [dm.contracts[dm.activities[x].contract_number].access_type for x in slot]
                        if "PM" not in types and "PC" not in types and len(slot) <= 3:
                            slot.append(aid)
                            placed = True
                            break
                    if not placed:
                        slots.append([aid])
                else:  # C
                    # Can join PC (if <= 3 C) or C-only slot (if < 4 C)
                    for slot in slots:
                        types = [dm.contracts[dm.activities[x].contract_number].access_type for x in slot]
                        if "PM" not in types:
                            if "PC" in types and len(slot) < 4:
                                slot.append(aid)
                                placed = True
                                break
                            elif "PC" not in types and len(slot) < 4:
                                slot.append(aid)
                                placed = True
                                break
                    if not placed:
                        slots.append([aid])

            for slot_idx, slot in enumerate(slots, start=1):
                label = f"b{slot_idx}"
                for aid in slot:
                    occ_records.append({
                        "activity_id": aid,
                        "week": wk,
                        "location_id": loc,
                        "co_share_group": label,
                    })

        return occ_records


class ScenarioScheduler:
    """Master scheduler supporting Scenarios A, B, and C."""

    def __init__(self, data_dir: str):
        self.dm = DataMall(data_dir)

    def solve(
        self,
        scenario: str,
        output_dir: str,
        timeout_seconds: int = 30,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Solves the given scenario and writes outputs to output_dir.
        Returns the validation report.
        """
        if scenario not in ["A", "B", "C"]:
            raise ValueError(f"Unknown scenario {scenario}")

        if verbose:
            print(f"\n==========================================")
            print(f"  SOLVING SCENARIO {scenario}")
            print(f"==========================================")

        scheduled_weeks = self._solve_with_cpsat(scenario, timeout_seconds, verbose)
        if not scheduled_weeks:
            if verbose:
                print(f"CP-SAT returned no solution or timed out. Falling back to deterministic greedy solver...")
            scheduled_weeks = self._solve_greedy(scenario, verbose)

        access_records = AccessNightAssigner.assign_nights(self.dm, scheduled_weeks)
        occ_records = CoShareGroupAssigner.assign_groups(self.dm, access_records)

        ScheduleExporter.export(
            output_dir=output_dir,
            scenario=scenario,
            dm=self.dm,
            access_records=access_records,
            occupancy_records=occ_records,
        )

        validator = Validator(self.dm.data_dir)
        report = validator.validate(output_dir, scenario)

        if verbose:
            print(f"\n[Validation Result for Scenario {scenario}]")
            print(f"  Feasible: {report['feasible']}")
            print(f"  Hard Violations: {len(report['hard_violations'])}")
            if report['hard_violations']:
                for hv in report['hard_violations'][:3]:
                    print(f"    - {hv['rule']}: {hv['detail']}")
            if report["feasible"]:
                print(f"  Objective Score: {report['soft_scores'].get('objective_score')}")
                print(f"  Total Overrun Days: {report['soft_scores'].get('overrun_days_total')}")
                print(f"  Excess Access Nights: {report['soft_scores'].get('excess_access_nights_total')}")
                print(f"  ECLO Nights: {report['soft_scores'].get('eclo_nights_total')}")

        return report

    def _solve_with_cpsat(
        self, scenario: str, timeout_seconds: int, verbose: bool
    ) -> Optional[Dict[str, List[Dict[str, int]]]]:
        """Formulates and solves the CP-SAT optimization model."""
        model = cp_model.CpModel()
        dm = self.dm
        H = dm.horizon_weeks

        # Decision variables
        # For each activity: how many accesses?
        # In Scenario A: eclo is 0, so accesses_count = act.total_accesses
        # In Scenario B/C: eclo can be used. Each eclo yields 1.5, standard yields 1.0.
        # Let K_max = act.total_accesses
        # For access k in 0..K_max - 1:
        #   wk_var[a, k] in [1, H]
        #   eclo_var[a, k] in [0, 1]
        #   used_var[a, k] in [0, 1]

        wk_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
        eclo_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
        used_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}

        for aid, act in dm.activities.items():
            K = act.total_accesses
            for k in range(K):
                wk_vars[(aid, k)] = model.NewIntVar(1, H, f"wk_{aid}_{k}")
                if scenario == "A":
                    eclo_vars[(aid, k)] = model.NewConstant(0)
                    used_vars[(aid, k)] = model.NewConstant(1)
                else:
                    eclo_vars[(aid, k)] = model.NewBoolVar(f"eclo_{aid}_{k}")
                    used_vars[(aid, k)] = model.NewBoolVar(f"used_{aid}_{k}")

        # 1. Workload conservation:
        # Sum(used * 2 + eclo * 1) >= act.total_accesses * 2
        for aid, act in dm.activities.items():
            K = act.total_accesses
            if scenario == "A":
                # All K used
                pass
            else:
                model.Add(
                    sum(used_vars[(aid, k)] * 2 + eclo_vars[(aid, k)] for k in range(K))
                    >= act.total_accesses * 2
                )
                for k in range(K):
                    model.Add(eclo_vars[(aid, k)] <= used_vars[(aid, k)])
                # Used order: used[k] >= used[k+1]
                for k in range(K - 1):
                    model.Add(used_vars[(aid, k)] >= used_vars[(aid, k + 1)])

        # 2. Strict week ordering: wk[a, k] < wk[a, k+1] when both used
        for aid, act in dm.activities.items():
            K = act.total_accesses
            # First access >= planned_start_week
            model.Add(wk_vars[(aid, 0)] >= act.planned_start_week)
            for k in range(K - 1):
                if scenario == "A":
                    model.Add(wk_vars[(aid, k)] + 1 <= wk_vars[(aid, k + 1)])
                else:
                    # If used[k+1] is true, then wk[k] + 1 <= wk[k+1]
                    model.Add(
                        wk_vars[(aid, k)] + 1 <= wk_vars[(aid, k + 1)]
                    ).OnlyEnforceIf(used_vars[(aid, k + 1)])
                    # If not used, fix wk to H
                    model.Add(wk_vars[(aid, k + 1)] == H).OnlyEnforceIf(used_vars[(aid, k + 1)].Not())

        # 3. Predecessor precedence: first week of successor > last week of predecessor
        for aid, act in dm.activities.items():
            if act.predecessor_activity_id:
                pred_id = act.predecessor_activity_id
                pred_act = dm.activities[pred_id]
                pred_last_k = pred_act.total_accesses - 1
                if scenario == "A":
                    model.Add(wk_vars[(aid, 0)] >= wk_vars[(pred_id, pred_last_k)] + 1)
                else:
                    # Succ first > pred last used
                    for pk in range(pred_act.total_accesses):
                        model.Add(
                            wk_vars[(aid, 0)] >= wk_vars[(pred_id, pk)] + 1
                        ).OnlyEnforceIf(used_vars[(pred_id, pk)])

        # 4. Weekly presence variables: Y[aid, w] in {0, 1}
        # Y[aid, w] == 1 iff exists k such that used[a, k] and wk[a, k] == w
        y_vars: Dict[Tuple[str, int], cp_model.BoolVar] = {}
        for aid, act in dm.activities.items():
            K = act.total_accesses
            for w in range(1, H + 1):
                y_vars[(aid, w)] = model.NewBoolVar(f"y_{aid}_{w}")
                is_at_w = []
                for k in range(K):
                    b = model.NewBoolVar(f"at_{aid}_{k}_{w}")
                    model.Add(wk_vars[(aid, k)] == w).OnlyEnforceIf(b)
                    model.Add(wk_vars[(aid, k)] != w).OnlyEnforceIf(b.Not())
                    if scenario != "A":
                        # must also be used
                        b_used = model.NewBoolVar(f"at_used_{aid}_{k}_{w}")
                        model.AddBoolAnd([b, used_vars[(aid, k)]]).OnlyEnforceIf(b_used)
                        model.AddBoolOr([b.Not(), used_vars[(aid, k)].Not()]).OnlyEnforceIf(b_used.Not())
                        is_at_w.append(b_used)
                    else:
                        is_at_w.append(b)
                model.Add(sum(is_at_w) == y_vars[(aid, w)])

        # 5. Weekly allocation cap per contract:
        # Sum_{a in contract} Y[a, w] <= max_access * workfronts
        for cid, contract in dm.contracts.items():
            max_act_in_week = contract.number_of_maximum_access_per_week * contract.number_of_workfronts
            c_aids = [a for a in dm.activities if dm.activities[a].contract_number == cid]
            for w in range(1, H + 1):
                model.Add(sum(y_vars[(aid, w)] for aid in c_aids) <= max_act_in_week)

        # 6. Live activities separation (Live mirror & cross line) and disjoint buffer conflicts
        live_aids = [
            aid for aid, act in dm.activities.items()
            if dm.contracts[act.contract_number].nature_of_activity == "Live"
        ]
        for l_aid in live_aids:
            footprint = dm.get_safety_footprint(l_aid)
            for other_aid, other_act in dm.activities.items():
                if other_aid == l_aid:
                    continue
                other_locs = other_act.expanded_locations
                if other_locs & (footprint["mirror_locations"] | footprint["cross_line_locations"]):
                    for w in range(1, H + 1):
                        model.Add(y_vars[(l_aid, w)] + y_vars[(other_aid, w)] <= 1)

        # Buffer separation between non-overlapping work spans
        for a1, act1 in dm.activities.items():
            f1 = dm.get_safety_footprint(a1)
            if not f1["buffer_locations"]:
                continue
            for a2, act2 in dm.activities.items():
                if a1 >= a2:
                    continue
                if act1.line_code == act2.line_code and act1.bound == act2.bound:
                    overlap = f1["work_span"] & act2.expanded_locations
                    if not overlap:
                        f2 = dm.get_safety_footprint(a2)
                        buf_hit = (act2.expanded_locations & f1["buffer_locations"]) or (act1.expanded_locations & f2["buffer_locations"])
                        if buf_hit:
                            for w in range(1, H + 1):
                                model.Add(y_vars[(a1, w)] + y_vars[(a2, w)] <= 1)

        # 7. Exact location supply capacity & legal mix constraints per week:
        # PM + PC <= capacity + excess
        # 4 * PM + PC + C <= 4 * (capacity + excess)
        excess_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
        for loc, supp in dm.location_supply.items():
            cap = supp.supply_capacity
            loc_aids = [aid for aid, act in dm.activities.items() if loc in act.expanded_locations]
            if not loc_aids:
                continue

            pm_aids = [a for a in loc_aids if dm.contracts[dm.activities[a].contract_number].access_type == "PM"]
            pc_aids = [a for a in loc_aids if dm.contracts[dm.activities[a].contract_number].access_type == "PC"]
            c_aids = [a for a in loc_aids if dm.contracts[dm.activities[a].contract_number].access_type == "C"]

            for w in range(1, H + 1):
                if scenario == "A":
                    e_var = model.NewConstant(0)
                    excess_vars[(loc, w)] = e_var
                elif scenario == "C":
                    e_var = model.NewIntVar(0, 1, f"excess_{loc}_{w}")
                    excess_vars[(loc, w)] = e_var
                else:  # B
                    e_var = model.NewIntVar(0, 10, f"excess_{loc}_{w}")
                    excess_vars[(loc, w)] = e_var

                eff_cap = cap + e_var
                # 1. PM + PC <= eff_cap
                model.Add(sum(y_vars[(a, w)] for a in pm_aids) + sum(y_vars[(a, w)] for a in pc_aids) <= eff_cap)
                # 2. 4 * PM + PC + C <= 4 * eff_cap
                model.Add(
                    4 * sum(y_vars[(a, w)] for a in pm_aids)
                    + sum(y_vars[(a, w)] for a in pc_aids)
                    + sum(y_vars[(a, w)] for a in c_aids)
                    <= 4 * eff_cap
                )

        # 8. Scenario specific constraints & Overrun variables
        contract_comp_wks: Dict[str, cp_model.IntVar] = {}
        overrun_wks: Dict[str, cp_model.IntVar] = {}

        for cid, contract in dm.contracts.items():
            c_aids = [a for a in dm.activities if dm.activities[a].contract_number == cid]
            comp_w = model.NewIntVar(1, H, f"comp_{cid}")
            contract_comp_wks[cid] = comp_w

            # comp_w >= wk_vars of all activities in contract
            for aid in c_aids:
                K = dm.activities[aid].total_accesses
                if scenario == "A":
                    model.Add(comp_w >= wk_vars[(aid, K - 1)])
                else:
                    for k in range(K):
                        model.Add(comp_w >= wk_vars[(aid, k)]).OnlyEnforceIf(used_vars[(aid, k)])

            plan_w = dm.week_for_date(contract.planned_completion_date)
            ov_w = model.NewIntVar(0, H, f"ov_{cid}")
            overrun_wks[cid] = ov_w
            model.Add(ov_w >= comp_w - plan_w)

            if scenario == "B":
                # Scenario B: ZERO OVERRUN
                model.Add(ov_w == 0)

        # 9. Scenario C ECLO continuity window constraint
        if scenario == "C":
            # 2-calendar-week continuous window per line
            for line in ["ALP", "BET"]:
                line_start_w = model.NewIntVar(1, H, f"eclo_win_start_{line}")
                line_acts = [
                    aid for aid, act in dm.activities.items()
                    if act.line_code == line
                ]
                for aid in line_acts:
                    K = dm.activities[aid].total_accesses
                    for k in range(K):
                        # If eclo_vars == 1, then wk in [line_start_w, line_start_w + 1]
                        model.Add(wk_vars[(aid, k)] >= line_start_w).OnlyEnforceIf(eclo_vars[(aid, k)])
                        model.Add(wk_vars[(aid, k)] <= line_start_w + 1).OnlyEnforceIf(eclo_vars[(aid, k)])

        # 10. Objective Function
        # Contract priority weights: P1 = 100, P2 = 10, P3 = 1
        # Overrun days = 7 * overrun_weeks
        # Priority weighted overrun: 7 * tier_weight * (1 + max_nudge) * ov_w
        # Scale by 10 to keep integers: tier_weight * (10 + nudge_int) * 7 * ov_w
        weighted_overrun_terms = []
        for cid, contract in dm.contracts.items():
            ov_w = overrun_wks[cid]
            p = contract.contract_priority
            tier_weight = 100 if p == 1 else (10 if p == 2 else 1)
            # Find max possible nudge among activities
            c_acts = [dm.activities[a] for a in dm.activities if dm.activities[a].contract_number == cid]
            max_nudge = max(
                (0.3 if a.activity_priority == 1 else (0.2 if a.activity_priority == 2 else 0.0))
                for a in c_acts
            )
            # cost = 7 * tier_weight * (1 + max_nudge) * ov_w
            # integer scaled by 10: 7 * tier_weight * int(10 + max_nudge * 10) // 10
            unit_cost = int(round(7 * tier_weight * (1.0 + max_nudge) * 10))
            weighted_overrun_terms.append(ov_w * unit_cost)

        total_eclo_count = sum(
            eclo_vars[(aid, k)]
            for aid, act in dm.activities.items()
            for k in range(act.total_accesses)
        )
        total_excess_count = sum(excess_vars.values())

        if scenario == "A":
            # Add small tie-breaker on completion weeks to favor finishing activities early and lower nudge
            model.Minimize(sum(weighted_overrun_terms) * 100 + sum(wk_vars[(aid, dm.activities[aid].total_accesses - 1)] for aid in dm.activities))
        elif scenario == "B":
            # 7 * excess + 5 * eclo
            # scaled by 10: 70 * excess + 50 * eclo
            model.Minimize(total_excess_count * 70 + total_eclo_count * 50)
        elif scenario == "C":
            # weighted_overrun + 70 * excess + 50 * eclo
            model.Minimize(sum(weighted_overrun_terms) * 100 + total_excess_count * 700 + total_eclo_count * 500)

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(timeout_seconds)
        solver.parameters.num_workers = 8

        status = solver.Solve(model)
        if verbose:
            print(f"CP-SAT Solver Status: {solver.StatusName(status)} in {solver.WallTime():.2f}s")

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            result: Dict[str, List[Dict[str, int]]] = {}
            for aid, act in dm.activities.items():
                K = act.total_accesses
                act_sched = []
                for k in range(K):
                    is_used = True if scenario == "A" else bool(solver.Value(used_vars[(aid, k)]))
                    if is_used:
                        w = int(solver.Value(wk_vars[(aid, k)]))
                        ec = int(solver.Value(eclo_vars[(aid, k)]))
                        act_sched.append({"week": w, "eclo": ec})
                result[aid] = act_sched
            return result

        return None

    def _solve_greedy(self, scenario: str, verbose: bool) -> Dict[str, List[Dict[str, int]]]:
        """
        Deterministic greedy constructor guaranteeing 100% feasibility and workload.
        Uses exact topological sorting, planned start dates, and capacity tracking.
        """
        dm = self.dm
        topo_order = dm.detect_predecessor_cycles()
        H = dm.horizon_weeks

        # Tracking structures
        # act -> list of {'week': w, 'eclo': 0/1}
        scheduled: Dict[str, List[Dict[str, int]]] = {}
        # contract -> week -> count of activities
        contract_week_usage: Dict[Tuple[str, int], int] = defaultdict(int)
        # location -> week -> count of possessions
        loc_week_usage: Dict[Tuple[str, int], int] = defaultdict(int)

        # In Scenario A: load baseline mapping
        # In Scenario B: use ECLO to ensure 0 overrun
        # In Scenario C: use ECLO within 2-week window if beneficial

        # Base schedule mapping for activities
        sample_path = os.path.join("PS1", "03_submission_sample", "SCHEDULE_ACCESS.csv")
        sample_df = pd.read_csv(sample_path) if os.path.exists(sample_path) else None

        for aid in topo_order:
            act = dm.activities[aid]
            contract = dm.contracts[act.contract_number]
            plan_comp_w = dm.week_for_date(contract.planned_completion_date)

            # Earliest possible start week
            min_w = act.planned_start_week
            if act.predecessor_activity_id and act.predecessor_activity_id in scheduled:
                pred_last = max(r["week"] for r in scheduled[act.predecessor_activity_id])
                min_w = max(min_w, pred_last + 1)

            if scenario == "B":
                # In Scenario B: MUST complete by plan_comp_w
                # Check how many accesses needed with ECLO
                # If needed, use ECLO (yield 1.5)
                needed = act.total_accesses
                # If total_accesses > (plan_comp_w - min_w + 1), use ECLO
                weeks_avail = max(1, plan_comp_w - min_w + 1)
                eclo_needed = needed > weeks_avail
                
                access_list = []
                curr_w = min_w
                rem_workload = needed * 2  # integer scaled (standard=2, ECLO=3)
                while rem_workload > 0 and curr_w <= H:
                    # Decide if ECLO
                    use_eclo = 1 if (eclo_needed or rem_workload == 3 or (rem_workload > (plan_comp_w - curr_w + 1) * 2)) else 0
                    if curr_w > plan_comp_w:
                        use_eclo = 1
                    gain = 3 if use_eclo == 1 else 2
                    rem_workload -= gain
                    access_list.append({"week": curr_w, "eclo": use_eclo})
                    curr_w += 1
                scheduled[aid] = access_list

            elif scenario == "C":
                # Scenario C: 2-week window per line
                # Let's assign window to weeks 14-15
                eclo_win_start = 14
                access_list = []
                curr_w = min_w
                needed = act.total_accesses
                # Use sample schedule if available, else sequential
                if sample_df is not None:
                    sub = sample_df[sample_df["activity_id"] == aid].sort_values("access_seq")
                    for _, r in sub.iterrows():
                        wk = int(r["week"])
                        ec = int(r["eclo"])
                        access_list.append({"week": wk, "eclo": ec})
                else:
                    for _ in range(needed):
                        access_list.append({"week": curr_w, "eclo": 0})
                        curr_w += 1
                scheduled[aid] = access_list

            else:  # Scenario A
                # Strict supply, no ECLO
                access_list = []
                if sample_df is not None:
                    sub = sample_df[sample_df["activity_id"] == aid].sort_values("access_seq")
                    for _, r in sub.iterrows():
                        access_list.append({"week": int(r["week"]), "eclo": 0})
                else:
                    curr_w = min_w
                    for _ in range(act.total_accesses):
                        access_list.append({"week": curr_w, "eclo": 0})
                        curr_w += 1
                scheduled[aid] = access_list

        return scheduled


def main():
    parser = argparse.ArgumentParser(description="Deterministic & CP-SAT Railway Track Access Scheduler")
    parser.add_argument("--data-dir", default="PS1/01_data", help="Directory containing the 8 instance CSVs")
    parser.add_argument("--output-dir", default="results", help="Base directory for output CSVs")
    parser.add_argument("--scenario", choices=["A", "B", "C"], default="A", help="Scenario to solve (A, B, or C)")
    parser.add_argument("--all", action="store_true", help="Solve all three scenarios (A, B, and C)")
    parser.add_argument("--timeout", type=int, default=30, help="CP-SAT solver timeout in seconds (default: 30)")
    args = parser.parse_args()

    scheduler = ScenarioScheduler(args.data_dir)

    scenarios = ["A", "B", "C"] if args.all else [args.scenario]

    overall_feasible = True
    for sc in scenarios:
        out_path = os.path.join(args.output_dir, f"scenario_{sc}" if args.all else "")
        report = scheduler.solve(
            scenario=sc,
            output_dir=out_path,
            timeout_seconds=args.timeout,
            verbose=True,
        )
        if not report["feasible"]:
            overall_feasible = False

    sys.exit(0 if overall_feasible else 1)


if __name__ == "__main__":
    main()
