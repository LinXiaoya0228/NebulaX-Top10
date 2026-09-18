from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from src.graph import RailNetworkGraph, parse_location_id
from src.models import ProblemInstance, load_problem_instance
from src.rules import RuleEngine


@dataclass
class HardViolation:
    rule: str
    severity: str = "hard"
    detail: str = ""


@dataclass
class ValidationReport:
    scenario: str
    feasible: bool
    hard_violations: List[HardViolation]
    soft_scores: Dict[str, Any]
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "feasible": self.feasible,
            "hard_violations": [
                {"rule": v.rule, "severity": v.severity, "detail": v.detail}
                for v in self.hard_violations
            ],
            "soft_scores": self.soft_scores,
            "detail": self.detail,
        }


class Validator:
    def __init__(self, instance: ProblemInstance):
        self.instance = instance
        self.graph = RailNetworkGraph(instance)
        self.rules = RuleEngine(instance, self.graph)

    def validate(
        self,
        schedule_access_df: pd.DataFrame,
        schedule_occupancy_df: pd.DataFrame,
        results_df: pd.DataFrame,
        scenario: Optional[str] = None,
    ) -> ValidationReport:
        hard_violations: List[HardViolation] = []

        # Determine scenario
        if scenario is None:
            if not results_df.empty and "scenario" in results_df.columns:
                scenario = str(results_df["scenario"].iloc[0]).strip().upper()
            else:
                scenario = "A"
        scenario = scenario.upper()

        # Check single scenario consistency in RESULTS.csv
        scenarios_in_results = set(results_df["scenario"].dropna().unique())
        if len(scenarios_in_results) > 1:
            hard_violations.append(
                HardViolation(
                    rule="results_schema",
                    detail=f"RESULTS.csv contains multiple scenarios: {scenarios_in_results}",
                )
            )

        # 1. Workload Conservation (100% baseline gate)
        activity_yields: Dict[str, float] = {}
        activity_weeks: Dict[str, List[int]] = {}
        activity_eclo: Dict[str, List[int]] = {}

        for _, row in schedule_access_df.iterrows():
            act_id = str(row["activity_id"]).strip()
            week = int(row["week"])
            eclo = int(row["eclo"])
            yield_val = 1.5 if eclo == 1 else 1.0

            activity_yields[act_id] = activity_yields.get(act_id, 0.0) + yield_val
            activity_weeks.setdefault(act_id, []).append(week)
            activity_eclo.setdefault(act_id, []).append(eclo)

        for act_id, act in self.instance.activities.items():
            actual_yield = activity_yields.get(act_id, 0.0)
            if actual_yield < act.total_accesses:
                hard_violations.append(
                    HardViolation(
                        rule="workload",
                        detail=f"Activity {act_id} incomplete: scheduled yield {actual_yield} < required {act.total_accesses}",
                    )
                )

        # Every scheduled access must have exactly the expanded physical occupancy.
        expected_occupancy: Set[Tuple[str, int, str]] = set()
        for act_id, weeks in activity_weeks.items():
            act = self.instance.activities.get(act_id)
            if act is None:
                hard_violations.append(
                    HardViolation(rule="schema", detail=f"Unknown activity in schedule: {act_id}")
                )
                continue
            locations = self.graph.expand_activity_occupancy(
                act.start_location_id, act.end_location_id
            )
            for week in weeks:
                expected_occupancy.update((act_id, week, loc) for loc in locations)

        actual_occupancy = {
            (str(row["activity_id"]).strip(), int(row["week"]), str(row["location_id"]).strip())
            for _, row in schedule_occupancy_df.iterrows()
        }
        missing_occupancy = expected_occupancy - actual_occupancy
        extra_occupancy = actual_occupancy - expected_occupancy
        if missing_occupancy or extra_occupancy:
            hard_violations.append(
                HardViolation(
                    rule="occupancy",
                    detail=(
                        f"Occupancy does not match scheduled footprints: "
                        f"{len(missing_occupancy)} missing, {len(extra_occupancy)} extra"
                    ),
                )
            )

        # 2. Planned Start Date
        for act_id, weeks in activity_weeks.items():
            if act_id in self.instance.activities:
                act = self.instance.activities[act_id]
                planned_wk = self.instance.date_to_week(act.planned_start_date)
                for wk in weeks:
                    if wk < planned_wk:
                        hard_violations.append(
                            HardViolation(
                                rule="planned_start",
                                detail=f"Activity {act_id} scheduled in week {wk} before planned start week {planned_wk} ({act.planned_start_date})",
                            )
                        )

        # 3. Predecessor Precedence (FS+0 strictly later week)
        for act_id, act in self.instance.activities.items():
            if act.predecessor_activity_id and act.predecessor_activity_id in activity_weeks:
                pred_id = act.predecessor_activity_id
                pred_weeks = activity_weeks.get(pred_id, [])
                succ_weeks = activity_weeks.get(act_id, [])
                if pred_weeks and succ_weeks:
                    max_pred_wk = max(pred_weeks)
                    min_succ_wk = min(succ_weeks)
                    if min_succ_wk <= max_pred_wk:
                        hard_violations.append(
                            HardViolation(
                                rule="predecessor",
                                detail=f"Predecessor violation: {act_id} starts in wk {min_succ_wk} before {pred_id} finished in wk {max_pred_wk}",
                            )
                        )

        # 4. Weekly Allocation & 5. Workfronts
        # Group accesses by (contract, week, access_night)
        access_by_contract_week: Dict[Tuple[str, int], Set[int]] = {}
        activities_by_night: Dict[Tuple[str, int, int], List[str]] = {}

        for _, row in schedule_access_df.iterrows():
            act_id = str(row["activity_id"]).strip()
            week = int(row["week"])
            access_night = int(row["access_night"])
            if act_id in self.instance.activities:
                contract_num = self.instance.activities[act_id].contract_number
                access_by_contract_week.setdefault((contract_num, week), set()).add(access_night)
                activities_by_night.setdefault((contract_num, week, access_night), []).append(act_id)

        for (c_num, wk), night_set in access_by_contract_week.items():
            contract = self.instance.contracts[c_num]
            if len(night_set) > contract.number_of_maximum_access_per_week:
                hard_violations.append(
                    HardViolation(
                        rule="weekly_allocation",
                        detail=f"Contract {c_num} in week {wk} used {len(night_set)} access nights > max {contract.number_of_maximum_access_per_week}",
                    )
                )

        for (c_num, wk, night), act_list in activities_by_night.items():
            contract = self.instance.contracts[c_num]
            if len(act_list) > contract.number_of_workfronts:
                hard_violations.append(
                    HardViolation(
                        rule="workfront",
                        detail=f"Contract {c_num} in week {wk} night {night} had {len(act_list)} concurrent activities > workfronts {contract.number_of_workfronts}",
                    )
                )

        # 6. Possession Legal Mix & Capacity
        # Check SCHEDULE_OCCUPANCY.csv
        occ_by_loc_week: Dict[Tuple[str, int], Dict[str, List[str]]] = {}
        for _, row in schedule_occupancy_df.iterrows():
            act_id = str(row["activity_id"]).strip()
            week = int(row["week"])
            loc_id = str(row["location_id"]).strip()
            grp = str(row["co_share_group"]).strip()

            occ_by_loc_week.setdefault((loc_id, week), {}).setdefault(grp, []).append(act_id)

        # Capacity check
        excess_nights_by_loc_wk: Dict[Tuple[str, int], int] = {}
        for (loc_id, wk), grp_map in occ_by_loc_week.items():
            supply_obj = self.instance.location_supply.get(loc_id)
            nominal_cap = supply_obj.supply_capacity if supply_obj else 4
            num_groups = len(grp_map)
            excess = max(0, num_groups - nominal_cap)
            if excess > 0:
                excess_nights_by_loc_wk[(loc_id, wk)] = excess

            if scenario == "A" and excess > 0:
                hard_violations.append(
                    HardViolation(
                        rule="capacity",
                        detail=f"Scenario A capacity breach at {loc_id} in wk {wk}: {num_groups} groups > supply {nominal_cap}",
                    )
                )
            elif scenario == "C" and excess > 1:
                hard_violations.append(
                    HardViolation(
                        rule="capacity",
                        detail=f"Scenario C capacity breach at {loc_id} in wk {wk}: {excess} excess nights > 1 allowance (total {num_groups} > supply {nominal_cap})",
                    )
                )

        # Legal mix in each co-share group
        for (loc_id, wk), grp_map in occ_by_loc_week.items():
            for grp, act_list in grp_map.items():
                types = [
                    self.instance.contracts[self.instance.activities[a].contract_number].access_type
                    for a in act_list if a in self.instance.activities
                ]
                pm_count = types.count("PM")
                pc_count = types.count("PC")
                c_count = types.count("C")
                total = len(types)

                if pm_count > 0 and total > 1:
                    hard_violations.append(
                        HardViolation(
                            rule="legal_mix",
                            detail=f"Illegal mix at {loc_id} wk {wk} grp {grp}: PM must be alone, found {types}",
                        )
                    )
                elif pc_count > 1:
                    hard_violations.append(
                        HardViolation(
                            rule="legal_mix",
                            detail=f"Illegal mix at {loc_id} wk {wk} grp {grp}: Multiple PCs found ({pc_count})",
                        )
                    )
                elif pc_count == 1 and c_count > 3:
                    hard_violations.append(
                        HardViolation(
                            rule="legal_mix",
                            detail=f"Illegal mix at {loc_id} wk {wk} grp {grp}: PC with {c_count} C > max 3",
                        )
                    )
                elif pc_count == 0 and pm_count == 0 and c_count > 4:
                    hard_violations.append(
                        HardViolation(
                            rule="legal_mix",
                            detail=f"Illegal mix at {loc_id} wk {wk} grp {grp}: {c_count} C > max 4",
                        )
                    )

        # 7. ECLO Rules
        eclo_accesses: List[Tuple[str, int]] = []
        for _, row in schedule_access_df.iterrows():
            if int(row["eclo"]) == 1:
                eclo_accesses.append((str(row["activity_id"]).strip(), int(row["week"])))

        if scenario == "A" and len(eclo_accesses) > 0:
            hard_violations.append(
                HardViolation(
                    rule="eclo",
                    detail=f"Scenario A hard-forbids ECLO, but found {len(eclo_accesses)} ECLO accesses",
                )
            )

        if scenario == "C" and len(eclo_accesses) > 0:
            # Check continuity window of <= 2 weeks per line
            line_eclo_weeks: Dict[str, Set[int]] = {"ALP": set(), "BET": set()}
            for act_id, wk in eclo_accesses:
                if act_id in self.instance.activities:
                    act = self.instance.activities[act_id]
                    _, line_code, _, _ = parse_location_id(act.start_location_id)
                    line_eclo_weeks[line_code].add(wk)
                    # If Live and touches interchange, affects both lines
                    contract = self.instance.contracts[act.contract_number]
                    if contract.nature_of_activity == "Live":
                        fp = self.rules.activity_footprints[act_id]
                        if any("H01" in l or "H02" in l for l in fp.all_closed_locations):
                            other_line = "BET" if line_code == "ALP" else "ALP"
                            line_eclo_weeks[other_line].add(wk)

            for line_code, wks in line_eclo_weeks.items():
                if len(wks) > 0:
                    span = max(wks) - min(wks) + 1
                    if span > 2:
                        hard_violations.append(
                            HardViolation(
                                rule="eclo_continuity",
                                detail=f"Scenario C ECLO continuity violation on {line_code}: span is {span} weeks ({sorted(wks)}) > max 2 weeks",
                            )
                        )

        # 8. Recompute RESULTS from the access schedule; never trust submitted scores.
        submitted_results: Dict[str, Tuple[str, int]] = {}
        for _, row in results_df.iterrows():
            c_num = str(row["contract_number"]).strip()
            sim_date_str = str(row["simulated_completion_date"]).strip()
            overrun = int(row["overrun_days"])
            submitted_results[c_num] = (sim_date_str, overrun)

        simulated_overruns: Dict[str, int] = {}
        for c_num, contract in self.instance.contracts.items():
            contract_weeks = [
                week
                for act in self.instance.activities_by_contract.get(c_num, [])
                for week in activity_weeks.get(act.activity_id, [])
            ]
            if contract_weeks:
                simulated_date = self.instance.week_end_date(max(contract_weeks))
                planned_date = datetime.strptime(
                    contract.planned_completion_date, "%Y-%m-%d"
                ).date()
                overrun = max(0, (simulated_date - planned_date).days)
                simulated_date_str = simulated_date.isoformat()
            else:
                simulated_date_str = contract.planned_completion_date
                overrun = 0

            simulated_overruns[c_num] = overrun
            submitted = submitted_results.get(c_num)
            if submitted != (simulated_date_str, overrun):
                hard_violations.append(
                    HardViolation(
                        rule="results_mismatch",
                        detail=(
                            f"Contract {c_num} RESULTS mismatch: submitted {submitted}, "
                            f"computed {(simulated_date_str, overrun)}"
                        ),
                    )
                )

            if scenario == "B" and overrun > 0:
                hard_violations.append(
                    HardViolation(
                        rule="planned_date",
                        detail=f"Scenario B strict deadline violated by contract {c_num}: overrun_days = {overrun}",
                    )
                )

        # Calculate Soft Scores
        total_overrun_days = sum(simulated_overruns.values())
        contracts_overrunning = sum(1 for v in simulated_overruns.values() if v > 0)
        excess_access_nights_total = sum(excess_nights_by_loc_wk.values())
        eclo_nights_total = len(eclo_accesses)

        # Priority overrun breakdown
        priority_overrun: Dict[str, int] = {"1": 0, "2": 0, "3": 0}
        priority_weighted_score = 0.0

        for c_num, overrun in simulated_overruns.items():
            if c_num in self.instance.contracts and overrun > 0:
                contract = self.instance.contracts[c_num]
                tier_str = str(contract.contract_priority)
                priority_overrun[tier_str] = priority_overrun.get(tier_str, 0) + overrun

                # Banded priority weighted score
                tier_weight = 100.0 if contract.contract_priority == 1 else (10.0 if contract.contract_priority == 2 else 1.0)
                # Compute nudge based on activities in contract
                acts_in_c = self.instance.activities_by_contract.get(c_num, [])
                # If multiple activities overrun, average/max nudge
                nudges = [0.3 if a.activity_priority == 1 else (0.2 if a.activity_priority == 2 else 0.0) for a in acts_in_c]
                avg_nudge = max(nudges) if nudges else 0.0
                priority_weighted_score += tier_weight * (1.0 + avg_nudge) * overrun

        # Objective score calculation
        if scenario == "A":
            objective_score = priority_weighted_score
        elif scenario == "B":
            objective_score = 7.0 * excess_access_nights_total + 5.0 * eclo_nights_total
        else:  # Scenario C
            objective_score = priority_weighted_score + 7.0 * excess_access_nights_total + 5.0 * eclo_nights_total

        feasible = len(hard_violations) == 0

        soft_scores = {
            "scenario": scenario,
            "overrun_days_total": total_overrun_days,
            "contracts_overrunning": contracts_overrunning,
            "excess_access_nights_total": excess_access_nights_total,
            "eclo_nights_total": eclo_nights_total,
            "priority_overrun": priority_overrun,
            "priority_weighted_score": round(priority_weighted_score, 2),
            "objective_score": round(objective_score, 2),
        }

        detail = {
            "capacity_hotspots": list(excess_nights_by_loc_wk.keys()),
            "nights_scheduled": len(schedule_access_df),
            "eclo_nights": eclo_nights_total,
        }

        return ValidationReport(
            scenario=scenario,
            feasible=feasible,
            hard_violations=hard_violations,
            soft_scores=soft_scores,
            detail=detail,
        )


def validate_submission_files(
    instance_dir: str | Path,
    submission_dir: str | Path,
    scenario: Optional[str] = None,
) -> ValidationReport:
    instance = load_problem_instance(instance_dir)
    sub_path = Path(submission_dir)
    access_df = pd.read_csv(sub_path / "SCHEDULE_ACCESS.csv")
    occ_df = pd.read_csv(sub_path / "SCHEDULE_OCCUPANCY.csv")
    results_df = pd.read_csv(sub_path / "RESULTS.csv")

    validator = Validator(instance)
    return validator.validate(access_df, occ_df, results_df, scenario)
