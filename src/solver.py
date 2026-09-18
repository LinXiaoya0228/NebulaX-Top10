from datetime import datetime
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import pandas as pd
from ortools.sat.python import cp_model

from src.exporter import ScheduleSolution
from src.graph import RailNetworkGraph, parse_location_id
from src.models import ProblemInstance
from src.rules import RuleEngine


class TrackAccessSolver:
    """Self-contained CP-SAT scheduler for the three PS1 scenarios."""

    def __init__(self, instance: ProblemInstance, graph: Optional[RailNetworkGraph] = None):
        self.instance = instance
        self.graph = graph or RailNetworkGraph(instance)
        self.rules = RuleEngine(instance, self.graph)

    def solve(
        self,
        scenario: str = "A",
        seed_access_df: Optional[pd.DataFrame] = None,
        seed_occ_df: Optional[pd.DataFrame] = None,
        time_limit_sec: int = 30,
    ) -> ScheduleSolution:
        scenario = scenario.upper().strip()
        if scenario not in {"A", "B", "C"}:
            raise ValueError("scenario must be A, B, or C")

        model = cp_model.CpModel()
        weeks = range(1, self.instance.horizon_weeks + 1)
        activities = list(self.instance.activities.values())
        physical = {
            activity.activity_id: self.graph.expand_activity_occupancy(
                activity.start_location_id, activity.end_location_id
            )
            for activity in activities
        }
        selected: Dict[Tuple[str, int], cp_model.IntVar] = {}
        eclo: Dict[Tuple[str, int], cp_model.IntVar] = {}
        night: Dict[Tuple[str, int, int], cp_model.IntVar] = {}

        for activity in activities:
            contract = self.instance.contracts[activity.contract_number]
            start_week = max(1, self.instance.date_to_week(activity.planned_start_date))
            for week in weeks:
                key = (activity.activity_id, week)
                selected[key] = model.NewBoolVar(f"selected_{activity.activity_id}_{week}")
                eclo[key] = model.NewBoolVar(f"eclo_{activity.activity_id}_{week}")
                model.Add(eclo[key] <= selected[key])
                if week < start_week:
                    model.Add(selected[key] == 0)
                if scenario == "A":
                    model.Add(eclo[key] == 0)
                night_vars = []
                for access_night in range(1, contract.number_of_maximum_access_per_week + 1):
                    variable = model.NewBoolVar(
                        f"night_{activity.activity_id}_{week}_{access_night}"
                    )
                    night[activity.activity_id, week, access_night] = variable
                    night_vars.append(variable)
                model.Add(sum(night_vars) == selected[key])
            delivered_units = sum(
                2 * selected[activity.activity_id, week]
                + eclo[activity.activity_id, week]
                for week in weeks
            )
            model.Add(delivered_units >= 2 * activity.total_accesses)
            model.Add(delivered_units <= 2 * activity.total_accesses + 1)

        for contract_number, contract in self.instance.contracts.items():
            contract_activities = self.instance.activities_by_contract.get(contract_number, [])
            for week in weeks:
                for access_night in range(1, contract.number_of_maximum_access_per_week + 1):
                    model.Add(
                        sum(
                            night[activity.activity_id, week, access_night]
                            for activity in contract_activities
                        )
                        <= contract.number_of_workfronts
                    )

        for successor in activities:
            predecessor_id = successor.predecessor_activity_id
            if not predecessor_id or predecessor_id not in self.instance.activities:
                continue
            for predecessor_week in weeks:
                for successor_week in range(1, predecessor_week + 1):
                    model.Add(
                        selected[predecessor_id, predecessor_week]
                        + selected[successor.activity_id, successor_week]
                        <= 1
                    )

        closure_conflicts = [
            (first.activity_id, second.activity_id)
            for first, second in combinations(activities, 2)
            if self.rules.closure_conflict_types(first.activity_id, second.activity_id)
            or self.rules.closure_conflict_types(second.activity_id, first.activity_id)
        ]
        for first_id, second_id in closure_conflicts:
            for week in weeks:
                model.Add(selected[first_id, week] + selected[second_id, week] <= 1)

        assignments: Dict[Tuple[str, int, str, int], cp_model.IntVar] = {}
        excess_terms: List[cp_model.IntVar] = []
        activities_by_location: Dict[str, List[str]] = {}
        for activity_id, locations in physical.items():
            for location in locations:
                activities_by_location.setdefault(location, []).append(activity_id)

        for location, location_activities in activities_by_location.items():
            supply = self.instance.location_supply.get(location)
            if supply is None:
                raise ValueError(f"Missing LOCATION_SUPPLY row for {location}")
            max_slots = (
                supply.supply_capacity
                if scenario == "A"
                else supply.supply_capacity + 1
                if scenario == "C"
                else max(supply.supply_capacity, len(location_activities))
            )
            for week in weeks:
                used_vars = []
                for slot in range(1, max_slots + 1):
                    used = model.NewBoolVar(f"used_{location}_{week}_{slot}")
                    used_vars.append(used)
                    pm_vars = []
                    pc_vars = []
                    c_vars = []
                    all_vars = []
                    for activity_id in location_activities:
                        assigned = model.NewBoolVar(
                            f"assign_{activity_id}_{week}_{location}_{slot}"
                        )
                        assignments[activity_id, week, location, slot] = assigned
                        model.Add(assigned <= selected[activity_id, week])
                        model.Add(assigned <= used)
                        all_vars.append(assigned)
                        activity = self.instance.activities[activity_id]
                        access_type = self.instance.contracts[activity.contract_number].access_type
                        {"PM": pm_vars, "PC": pc_vars, "C": c_vars}[access_type].append(assigned)
                    model.Add(sum(all_vars) >= used)
                    model.Add(sum(pm_vars) <= 1)
                    model.Add(sum(pc_vars) <= 1)
                    model.Add(sum(all_vars) <= 4)
                    if pm_vars:
                        model.Add(sum(all_vars) <= 1 + 3 * (1 - sum(pm_vars)))
                    if pc_vars:
                        model.Add(sum(c_vars) <= 3 + 4 * (1 - sum(pc_vars)))
                for activity_id in location_activities:
                    model.Add(
                        sum(
                            assignments[activity_id, week, location, slot]
                            for slot in range(1, max_slots + 1)
                        )
                        == selected[activity_id, week]
                    )
                for index in range(1, len(used_vars)):
                    model.Add(used_vars[index] <= used_vars[index - 1])
                excess_terms.extend(used_vars[supply.supply_capacity :])

        if scenario == "C":
            window_start = {
                line: model.NewIntVar(1, self.instance.horizon_weeks, f"eclo_start_{line}")
                for line in self.instance.lines
            }
            for activity in activities:
                line = parse_location_id(activity.start_location_id)[1]
                affected_lines = {line}
                contract = self.instance.contracts[activity.contract_number]
                if contract.nature_of_activity == "Live" and self.rules.activity_footprints[activity.activity_id].cross_line_locations:
                    affected_lines.update(self.instance.lines)
                for week in weeks:
                    for affected_line in affected_lines:
                        model.Add(window_start[affected_line] <= week).OnlyEnforceIf(
                            eclo[activity.activity_id, week]
                        )
                        model.Add(window_start[affected_line] >= week - 1).OnlyEnforceIf(
                            eclo[activity.activity_id, week]
                        )

        weighted_overrun_terms = []
        for contract_number, contract in self.instance.contracts.items():
            end_week = model.NewIntVar(0, self.instance.horizon_weeks, f"end_{contract_number}")
            for activity in self.instance.activities_by_contract.get(contract_number, []):
                for week in weeks:
                    model.Add(end_week >= week * selected[activity.activity_id, week])
            planned_date = datetime.strptime(contract.planned_completion_date, "%Y-%m-%d").date()
            planned_offset = (planned_date - self.instance.horizon_start).days + 1
            overrun = model.NewIntVar(0, self.instance.horizon_weeks * 7, f"overrun_{contract_number}")
            model.Add(overrun >= 7 * end_week - planned_offset)
            if scenario == "B":
                model.Add(overrun == 0)
            tier_weight = {1: 1000, 2: 100, 3: 10}[contract.contract_priority]
            nudge = max(
                ({1: 3, 2: 2, 3: 0}[activity.activity_priority]
                 for activity in self.instance.activities_by_contract.get(contract_number, [])),
                default=0,
            )
            weighted_overrun_terms.append((tier_weight + tier_weight * nudge // 10) * overrun)

        objective = []
        if scenario in {"A", "C"}:
            objective.extend(weighted_overrun_terms)
        if scenario in {"B", "C"}:
            objective.extend(70 * term for term in excess_terms)
            objective.extend(50 * term for term in eclo.values())
        model.Minimize(sum(objective))
        self._add_seed_hints(model, selected, eclo, seed_access_df)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(1, time_limit_sec)
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = 2026
        status = solver.Solve(model)
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            raise RuntimeError(
                f"No feasible Scenario {scenario} schedule found: {solver.StatusName(status)}"
            )

        access_records: List[Dict] = []
        occupancy_records: List[Dict] = []
        for activity in activities:
            access_seq = 1
            for week in weeks:
                if not solver.BooleanValue(selected[activity.activity_id, week]):
                    continue
                contract = self.instance.contracts[activity.contract_number]
                access_night = next(
                    value
                    for value in range(1, contract.number_of_maximum_access_per_week + 1)
                    if solver.BooleanValue(night[activity.activity_id, week, value])
                )
                access_records.append(
                    {
                        "activity_id": activity.activity_id,
                        "access_seq": access_seq,
                        "week": week,
                        "eclo": int(solver.BooleanValue(eclo[activity.activity_id, week])),
                        "access_night": access_night,
                    }
                )
                access_seq += 1
                for location in physical[activity.activity_id]:
                    assigned_slot = next(
                        key[3]
                        for key, variable in assignments.items()
                        if key[:3] == (activity.activity_id, week, location)
                        and solver.BooleanValue(variable)
                    )
                    occupancy_records.append(
                        {
                            "activity_id": activity.activity_id,
                            "week": week,
                            "location_id": location,
                            "co_share_group": f"b{assigned_slot}",
                        }
                    )

        access_df = pd.DataFrame(access_records)
        results_df = self._build_results_df(access_df, scenario)
        return ScheduleSolution(
            scenario=scenario,
            access_records=access_records,
            occupancy_records=occupancy_records,
            results_records=results_df.to_dict(orient="records"),
        )

    @staticmethod
    def _add_seed_hints(model, selected, eclo, seed_access_df):
        if seed_access_df is None:
            return
        seeded = {
            (str(row["activity_id"]), int(row["week"])): int(row.get("eclo", 0))
            for _, row in seed_access_df.iterrows()
        }
        for key, variable in selected.items():
            model.AddHint(variable, int(key in seeded))
            model.AddHint(eclo[key], seeded.get(key, 0))

    def _build_results_df(self, access_df: pd.DataFrame, scenario: str) -> pd.DataFrame:
        results = []
        for contract_number, contract in self.instance.contracts.items():
            activity_ids = [
                activity.activity_id
                for activity in self.instance.activities_by_contract.get(contract_number, [])
            ]
            contract_weeks = access_df[access_df["activity_id"].isin(activity_ids)]["week"]
            if contract_weeks.empty:
                simulated_date = contract.planned_completion_date
                overrun = 0
            else:
                simulated = self.instance.week_end_date(int(contract_weeks.max()))
                simulated_date = simulated.isoformat()
                planned = datetime.strptime(contract.planned_completion_date, "%Y-%m-%d").date()
                overrun = max(0, (simulated - planned).days)
            results.append(
                {
                    "scenario": scenario,
                    "contract_number": contract_number,
                    "simulated_completion_date": simulated_date,
                    "overrun_days": overrun,
                }
            )
        return pd.DataFrame(results).sort_values("contract_number").reset_index(drop=True)