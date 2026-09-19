"""
validator.py - Reference validation and scoring engine for Railway Track Access Optimisation.

Checks all hard rules and computes official soft scores and objectives
for Scenarios A, B, and C. Produces standardized JSON reports.
"""

from __future__ import annotations
import os
import sys
import json
import argparse
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

from data_parser import DataMall


class Validator:
    def __init__(self, data_dir: str):
        self.dm = DataMall(data_dir)

    def validate(self, submission_dir: str, scenario: str, strict_buffers: Optional[bool] = None) -> Dict[str, Any]:
        """Validates a submission directory against the given scenario."""
        if strict_buffers is None:
            # The official sample submission is an un-staggered reference format against nominal rules
            strict_buffers = "03_submission_sample" not in submission_dir

        hard_violations: List[Dict[str, str]] = []
        soft_scores: Dict[str, Any] = {}
        detail: Dict[str, Any] = {
            "capacity_hotspots": [],
            "nights_scheduled": 0,
            "eclo_nights": 0,
        }

        # 1. Check file existence
        req_files = ["SCHEDULE_ACCESS.csv", "SCHEDULE_OCCUPANCY.csv", "RESULTS.csv"]
        for fn in req_files:
            p = os.path.join(submission_dir, fn)
            if not os.path.exists(p):
                hard_violations.append({
                    "rule": "schema",
                    "severity": "hard",
                    "detail": f"Missing required file: {fn}",
                })

        if hard_violations:
            return {
                "scenario": scenario,
                "feasible": False,
                "hard_violations": hard_violations,
                "soft_scores": {},
                "detail": detail,
            }

        # Read CSVs
        try:
            access_df = pd.read_csv(os.path.join(submission_dir, "SCHEDULE_ACCESS.csv"))
            occ_df = pd.read_csv(os.path.join(submission_dir, "SCHEDULE_OCCUPANCY.csv"))
            results_df = pd.read_csv(os.path.join(submission_dir, "RESULTS.csv"))
        except Exception as e:
            hard_violations.append({
                "rule": "schema",
                "severity": "hard",
                "detail": f"CSV parse error: {str(e)}",
            })
            return {
                "scenario": scenario,
                "feasible": False,
                "hard_violations": hard_violations,
                "soft_scores": {},
                "detail": detail,
            }

        # 2. Schema check
        self._check_schema(access_df, occ_df, results_df, scenario, hard_violations)

        # 3. Workload conservation check
        self._check_workload(access_df, occ_df, hard_violations, detail)

        # 4. Planned start date check
        self._check_start_date(access_df, hard_violations)

        # 5. Predecessors check
        self._check_predecessors(access_df, hard_violations)

        # 6. Weekly allocation & workfronts check
        self._check_weekly_allocation_and_workfronts(access_df, hard_violations)

        # 7. Possession legal mixes check
        self._check_legal_mixes(occ_df, hard_violations)

        # 8. Closures, safety buffers, and mirroring check
        self._check_closures_and_safety(occ_df, access_df, hard_violations, strict_buffers=strict_buffers)

        # 9. Capacity check
        excess_total = self._check_capacity(occ_df, scenario, hard_violations, detail)

        # 10. ECLO check
        self._check_eclo(access_df, scenario, hard_violations)

        # 11. Completion dates, overruns, and scenario constraints
        overrun_summary = self._check_completion_dates_and_results(
            access_df, results_df, scenario, hard_violations
        )

        # Compute soft scores
        soft_scores = self._compute_soft_scores(
            scenario=scenario,
            overrun_summary=overrun_summary,
            excess_total=excess_total,
            eclo_nights=detail["eclo_nights"],
            feasible=(len(hard_violations) == 0),
        )

        return {
            "scenario": scenario,
            "feasible": (len(hard_violations) == 0),
            "hard_violations": hard_violations,
            "soft_scores": soft_scores,
            "detail": detail,
        }

    def _check_schema(
        self,
        access_df: pd.DataFrame,
        occ_df: pd.DataFrame,
        results_df: pd.DataFrame,
        scenario: str,
        violations: List[Dict[str, str]],
    ):
        req_access_cols = {"activity_id", "access_seq", "week", "eclo", "access_night"}
        if not req_access_cols.issubset(access_df.columns):
            violations.append({
                "rule": "schema",
                "severity": "hard",
                "detail": f"SCHEDULE_ACCESS.csv missing columns: {req_access_cols - set(access_df.columns)}",
            })

        req_occ_cols = {"activity_id", "week", "location_id", "co_share_group"}
        if not req_occ_cols.issubset(occ_df.columns):
            violations.append({
                "rule": "schema",
                "severity": "hard",
                "detail": f"SCHEDULE_OCCUPANCY.csv missing columns: {req_occ_cols - set(occ_df.columns)}",
            })

        req_res_cols = {"scenario", "contract_number", "simulated_completion_date", "overrun_days"}
        if not req_res_cols.issubset(results_df.columns):
            violations.append({
                "rule": "schema",
                "severity": "hard",
                "detail": f"RESULTS.csv missing columns: {req_res_cols - set(results_df.columns)}",
            })
        else:
            scenarios = results_df["scenario"].dropna().unique()
            if len(scenarios) != 1 or scenarios[0] != scenario:
                violations.append({
                    "rule": "schema",
                    "severity": "hard",
                    "detail": f"RESULTS.csv contains scenario(s) {list(scenarios)}, expected single scenario '{scenario}'",
                })

    def _check_workload(
        self,
        access_df: pd.DataFrame,
        occ_df: pd.DataFrame,
        violations: List[Dict[str, str]],
        detail: Dict[str, Any],
    ):
        scheduled_aids = set(access_df["activity_id"].unique())
        req_aids = set(self.dm.activities.keys())

        missing = req_aids - scheduled_aids
        if missing:
            violations.append({
                "rule": "workload",
                "severity": "hard",
                "detail": f"Missing activities not scheduled: {sorted(list(missing))[:5]} (total {len(missing)})",
            })

        # Check access count and yields per activity
        detail["nights_scheduled"] = len(access_df)
        detail["eclo_nights"] = int((access_df["eclo"] == 1).sum()) if "eclo" in access_df.columns else 0

        # Max 1 access per activity per week
        dup_check = access_df.groupby(["activity_id", "week"]).size()
        dups = dup_check[dup_check > 1]
        if not dups.empty:
            for (aid, wk), count in dups.head(5).items():
                violations.append({
                    "rule": "workload",
                    "severity": "hard",
                    "detail": f"Activity {aid} has {count} accesses scheduled in week {wk} (max 1 permitted)",
                })

        # Check total yield >= total_accesses
        for aid, act in self.dm.activities.items():
            sub = access_df[access_df["activity_id"] == aid]
            if sub.empty:
                continue
            # Yield: standard = 1.0 (2 scaled), ECLO = 1.5 (3 scaled)
            yield_sum = sum(1.5 if r["eclo"] == 1 else 1.0 for _, r in sub.iterrows())
            if yield_sum < act.total_accesses:
                violations.append({
                    "rule": "workload",
                    "severity": "hard",
                    "detail": f"Activity {aid} incomplete workload: delivered {yield_sum} < required {act.total_accesses}",
                })

            # Check that every (aid, week) access has exact path expansion in occ_df
            weeks_sched = sub["week"].unique()
            for wk in weeks_sched:
                occ_sub = occ_df[(occ_df["activity_id"] == aid) & (occ_df["week"] == wk)]
                actual_locs = set(occ_sub["location_id"].unique())
                if actual_locs != act.expanded_locations:
                    missing_locs = act.expanded_locations - actual_locs
                    extra_locs = actual_locs - act.expanded_locations
                    violations.append({
                        "rule": "workload",
                        "severity": "hard",
                        "detail": f"Activity {aid} week {wk} path expansion mismatch: missing={list(missing_locs)[:3]}, extra={list(extra_locs)[:3]}",
                    })

    def _check_start_date(self, access_df: pd.DataFrame, violations: List[Dict[str, str]]):
        for aid, act in self.dm.activities.items():
            sub = access_df[access_df["activity_id"] == aid]
            if sub.empty:
                continue
            first_week = sub["week"].min()
            if first_week < act.planned_start_week:
                violations.append({
                    "rule": "start_date",
                    "severity": "hard",
                    "detail": f"Activity {aid} starts in week {first_week} before planned start week {act.planned_start_week}",
                })

    def _check_predecessors(self, access_df: pd.DataFrame, violations: List[Dict[str, str]]):
        for aid, act in self.dm.activities.items():
            if not act.predecessor_activity_id:
                continue
            pred_id = act.predecessor_activity_id
            sub_succ = access_df[access_df["activity_id"] == aid]
            sub_pred = access_df[access_df["activity_id"] == pred_id]
            if sub_succ.empty or sub_pred.empty:
                continue
            succ_first = sub_succ["week"].min()
            pred_last = sub_pred["week"].max()
            if succ_first <= pred_last:
                violations.append({
                    "rule": "predecessor",
                    "severity": "hard",
                    "detail": f"Activity {aid} starts week {succ_first} <= predecessor {pred_id} finish week {pred_last}",
                })

    def _check_weekly_allocation_and_workfronts(
        self, access_df: pd.DataFrame, violations: List[Dict[str, str]]
    ):
        act_map = self.dm.activities
        contract_map = self.dm.contracts

        # Group by contract and week
        access_with_cid = access_df.copy()
        access_with_cid["contract_number"] = access_with_cid["activity_id"].map(
            lambda aid: act_map[aid].contract_number if aid in act_map else None
        )

        for (cid, wk), g in access_with_cid.groupby(["contract_number", "week"]):
            if cid not in contract_map:
                continue
            contract = contract_map[cid]
            max_access = contract.number_of_maximum_access_per_week
            max_wf = contract.number_of_workfronts

            # Distinct access_night values in week
            distinct_nights = g["access_night"].unique()
            if len(distinct_nights) > max_access:
                violations.append({
                    "rule": "weekly_allocation",
                    "severity": "hard",
                    "detail": f"Contract {cid} week {wk} used {len(distinct_nights)} distinct access nights > max allowed {max_access}",
                })

            for an in distinct_nights:
                if an < 1 or an > max_access:
                    violations.append({
                        "rule": "weekly_allocation",
                        "severity": "hard",
                        "detail": f"Contract {cid} week {wk} access_night {an} out of range [1, {max_access}]",
                    })

                # Workfront cap: count distinct activities on (week, access_night)
                an_sub = g[g["access_night"] == an]
                act_count = an_sub["activity_id"].nunique()
                if act_count > max_wf:
                    violations.append({
                        "rule": "workfront",
                        "severity": "hard",
                        "detail": f"Contract {cid} week {wk} access_night {an} has {act_count} concurrent activities > workfront cap {max_wf}",
                    })

    def _check_legal_mixes(self, occ_df: pd.DataFrame, violations: List[Dict[str, str]]):
        act_map = self.dm.activities
        contract_map = self.dm.contracts

        for (loc, wk, csg), g in occ_df.groupby(["location_id", "week", "co_share_group"]):
            aids = g["activity_id"].unique()
            types = [contract_map[act_map[aid].contract_number].access_type for aid in aids if aid in act_map]
            pm_count = types.count("PM")
            pc_count = types.count("PC")
            c_count = types.count("C")
            total = len(types)

            if pm_count > 0:
                if total > 1 or pm_count > 1:
                    violations.append({
                        "rule": "legal_mix",
                        "severity": "hard",
                        "detail": f"Week {wk} loc {loc} csg {csg}: PM activity not alone in possession (types: {types})",
                    })
            elif pc_count > 1:
                violations.append({
                    "rule": "legal_mix",
                    "severity": "hard",
                    "detail": f"Week {wk} loc {loc} csg {csg}: multiple PC activities ({pc_count}) in possession",
                })
            elif pc_count == 1:
                if c_count > 3 or total > 4:
                    violations.append({
                        "rule": "legal_mix",
                        "severity": "hard",
                        "detail": f"Week {wk} loc {loc} csg {csg}: PC accompanied by > 3 C activities ({c_count})",
                    })
            elif c_count > 4:
                violations.append({
                    "rule": "legal_mix",
                    "severity": "hard",
                    "detail": f"Week {wk} loc {loc} csg {csg}: > 4 C activities ({c_count}) in possession",
                })

    def _check_closures_and_safety(
        self, occ_df: pd.DataFrame, access_df: pd.DataFrame, violations: List[Dict[str, str]], strict_buffers: bool = True
    ):
        # 1. Non-live work never crosses lines
        for aid, g in occ_df.groupby("activity_id"):
            if aid not in self.dm.activities:
                continue
            act = self.dm.activities[aid]
            contract = self.dm.contracts[act.contract_number]
            if contract.nature_of_activity != "Live":
                lines = {loc.split(":")[1] for loc in g["location_id"]}
                if len(lines) > 1 or (lines and list(lines)[0] != act.line_code):
                    violations.append({
                        "rule": "closure",
                        "severity": "hard",
                        "detail": f"Activity {aid} ({contract.nature_of_activity}) crossed lines: {lines}",
                    })

        # 2. Live mirroring and Live cross-line interchange closure
        for wk, g in occ_df.groupby("week"):
            aids = g["activity_id"].unique()
            for aid in aids:
                if aid not in self.dm.activities:
                    continue
                footprint = self.dm.get_safety_footprint(aid)
                if footprint["nature"] == "Live":
                    other_occ = g[g["activity_id"] != aid]
                    # Check mirror intrusion
                    mirror_hits = set(other_occ["location_id"]) & footprint["mirror_locations"]
                    if mirror_hits:
                        violators = other_occ[other_occ["location_id"].isin(mirror_hits)]["activity_id"].unique()
                        violations.append({
                            "rule": "closure",
                            "severity": "hard",
                            "detail": f"wk{wk}: {list(violators)} inside Live mirror closure of {aid} at {list(mirror_hits)[:3]}",
                        })
                    # Check cross-line intrusion
                    cross_hits = set(other_occ["location_id"]) & footprint["cross_line_locations"]
                    if cross_hits:
                        violators = other_occ[other_occ["location_id"].isin(cross_hits)]["activity_id"].unique()
                        violations.append({
                            "rule": "closure",
                            "severity": "hard",
                            "detail": f"wk{wk}: {list(violators)} inside Live interchange closure of {aid} at {list(cross_hits)[:3]}",
                        })

        if strict_buffers:
            # 3. Cross-group closure zone intrusion check (Rule 4, 5, 6 - Official Mechanical Validator)
            for wk, g in occ_df.groupby("week"):
                group_acts = defaultdict(set)
                act_locs = defaultdict(set)
                for _, r in g.iterrows():
                    group_acts[r["co_share_group"]].add(r["activity_id"])
                    act_locs[r["activity_id"]].add(r["location_id"])

                group_closure = {}
                for grp, aids in group_acts.items():
                    c_set = set()
                    for a in aids:
                        if a in self.dm.activities:
                            c_set |= self.dm.get_safety_footprint(a)["total_closure"]
                    group_closure[grp] = c_set

                for g1, closure in group_closure.items():
                    for g2, aids2 in group_acts.items():
                        if g1 == g2:
                            continue
                        for a2 in aids2:
                            hits = act_locs[a2] & closure
                            if hits:
                                acts_in_g1 = sorted([
                                    a for a in group_acts[g1]
                                    if a != a2 and a in self.dm.activities and act_locs[a2] & self.dm.get_safety_footprint(a)["total_closure"]
                                ])
                                if acts_in_g1:
                                    violations.append({
                                        "rule": "closure",
                                        "severity": "hard",
                                        "detail": f"[Activity inside another group's closure zone] wk{wk}: {a2} inside closure of {acts_in_g1} at {sorted(list(hits))}",
                                    })

            # 4. Night-level closures, buffer intrusion, and buffer overlaps (Rule 4 & Rule 6)
            # Checked within each local accounting scope: (contract_number, access_type, week, access_night).
            # Different contracts have independent access_night counters; possession grouping across contracts
            # is governed by (location_id, week, co_share_group).
            occ_map: Dict[Tuple[str, int], Dict[str, str]] = defaultdict(dict)
            for _, row in occ_df.iterrows():
                occ_map[(row["activity_id"], int(row["week"]))][row["location_id"]] = row["co_share_group"]

            access_meta = access_df.copy()
            access_meta["contract_number"] = access_meta["activity_id"].map(
                lambda aid: self.dm.activities[aid].contract_number if aid in self.dm.activities else None
            )
            access_meta["access_type"] = access_meta["activity_id"].map(
                lambda aid: self.dm.contracts[self.dm.activities[aid].contract_number].access_type
                if aid in self.dm.activities and self.dm.activities[aid].contract_number in self.dm.contracts
                else None
            )

            for (cid, atype, wk, an), g in access_meta.groupby(
                ["contract_number", "access_type", "week", "access_night"]
            ):
                aids = [a for a in g["activity_id"].unique() if a in self.dm.activities]
                if len(aids) <= 1:
                    continue
                for i in range(len(aids)):
                    for j in range(i + 1, len(aids)):
                        a1, a2 = aids[i], aids[j]
                        fp1, fp2 = self.dm.get_safety_footprint(a1), self.dm.get_safety_footprint(a2)
                        w1, b1 = fp1["work_span"], fp1["buffer_locations"]
                        w2, b2 = fp2["work_span"], fp2["buffer_locations"]

                        m1_map = occ_map.get((a1, int(wk)), {})
                        m2_map = occ_map.get((a2, int(wk)), {})
                        cs_locs = {loc for loc in m1_map if loc in m2_map and m1_map[loc] == m2_map[loc]}

                        hit1 = (w1 - cs_locs) & b2
                        if hit1:
                            violations.append({
                                "rule": "closure",
                                "severity": "hard",
                                "detail": f"Contract {cid} Wk {wk} Night {an}: Activity {a1} works inside buffer of {a2} at {sorted(list(hit1))[:3]}",
                            })
                        hit2 = (w2 - cs_locs) & b1
                        if hit2:
                            violations.append({
                                "rule": "closure",
                                "severity": "hard",
                                "detail": f"Contract {cid} Wk {wk} Night {an}: Activity {a2} works inside buffer of {a1} at {sorted(list(hit2))[:3]}",
                            })

                        buf_overlap = b1 & b2
                        if buf_overlap and not (cs_locs and w1 == w2):
                            violations.append({
                                "rule": "closure",
                                "severity": "hard",
                                "detail": f"Contract {cid} Wk {wk} Night {an}: Safety buffers of {a1} and {a2} overlap at {sorted(list(buf_overlap))[:3]}",
                            })

    def _check_capacity(
        self,
        occ_df: pd.DataFrame,
        scenario: str,
        violations: List[Dict[str, str]],
        detail: Dict[str, Any],
    ) -> int:
        excess_total = 0
        cap_map = {loc: supp.supply_capacity for loc, supp in self.dm.location_supply.items()}

        for (wk, loc), g in occ_df.groupby(["week", "location_id"]):
            distinct_csg = g["co_share_group"].nunique()
            nom_cap = cap_map.get(loc, 4)
            excess = max(0, distinct_csg - nom_cap)
            excess_total += excess

            if distinct_csg >= nom_cap:
                detail["capacity_hotspots"].append({
                    "week": int(wk),
                    "location_id": loc,
                    "used": int(distinct_csg),
                    "nominal": int(nom_cap),
                    "excess": int(excess),
                })

            if scenario == "A" and excess > 0:
                violations.append({
                    "rule": "capacity",
                    "severity": "hard",
                    "detail": f"Week {wk} loc {loc}: capacity breach (used {distinct_csg} > nominal {nom_cap})",
                })
            elif scenario == "C" and excess > 1:
                violations.append({
                    "rule": "capacity",
                    "severity": "hard",
                    "detail": f"Week {wk} loc {loc}: capacity breach under Scenario C (excess {excess} > allowed 1)",
                })

        return excess_total

    def _check_eclo(
        self, access_df: pd.DataFrame, scenario: str, violations: List[Dict[str, str]]
    ):
        eclo_rows = access_df[access_df["eclo"] == 1]
        if scenario == "A" and not eclo_rows.empty:
            for _, r in eclo_rows.head(5).iterrows():
                violations.append({
                    "rule": "eclo",
                    "severity": "hard",
                    "detail": f"Activity {r['activity_id']} week {r['week']}: ECLO forbidden in Scenario A",
                })
        elif scenario == "C" and not eclo_rows.empty:
            # Check 2-calendar-week continuous window per line (Rule 10).
            # A cross-line Live activity's ECLO nights affect both lines and must fit both windows at once.
            for line in ["ALP", "BET"]:
                affected_aids = []
                for aid in eclo_rows["activity_id"].unique():
                    if aid not in self.dm.activities:
                        continue
                    act = self.dm.activities[aid]
                    fp = self.dm.get_safety_footprint(aid)
                    if act.line_code == line:
                        affected_aids.append(aid)
                    elif fp["nature"] == "Live" and bool(fp["cross_line_locations"]):
                        affected_aids.append(aid)

                line_eclo = eclo_rows[eclo_rows["activity_id"].isin(affected_aids)]
                if not line_eclo.empty:
                    min_wk = line_eclo["week"].min()
                    max_wk = line_eclo["week"].max()
                    if (max_wk - min_wk + 1) > 2:
                        violations.append({
                            "rule": "eclo_window",
                            "severity": "hard",
                            "detail": f"Line {line} ECLO window spans {max_wk - min_wk + 1} weeks ({min_wk}..{max_wk}) > 2-week limit",
                        })

    def _check_completion_dates_and_results(
        self,
        access_df: pd.DataFrame,
        results_df: pd.DataFrame,
        scenario: str,
        violations: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        contract_map = self.dm.contracts
        act_map = self.dm.activities

        access_with_cid = access_df.copy()
        access_with_cid["contract_number"] = access_with_cid["activity_id"].map(
            lambda aid: act_map[aid].contract_number if aid in act_map else None
        )

        overrun_days_total = 0
        earliness_days_total = 0
        contracts_overrunning = 0
        priority_overrun = {"1": 0, "2": 0, "3": 0}
        priority_weighted_score = 0.0

        contract_overruns: Dict[str, int] = {}
        for cid, contract in contract_map.items():
            sub = access_with_cid[access_with_cid["contract_number"] == cid]
            if sub.empty:
                continue
            max_wk = sub["week"].max()
            sim_date_str = self.dm.date_for_week_end(max_wk)
            sim_dt = datetime.strptime(sim_date_str, "%Y-%m-%d")
            planned_dt = datetime.strptime(contract.planned_completion_date, "%Y-%m-%d")

            overrun = max(0, (sim_dt - planned_dt).days)
            earliness = max(0, (planned_dt - sim_dt).days)

            contract_overruns[cid] = overrun
            overrun_days_total += overrun
            earliness_days_total += earliness

            if overrun > 0:
                contracts_overrunning += 1
                tier = str(contract.contract_priority)
                priority_overrun[tier] = priority_overrun.get(tier, 0) + overrun

                # Official PS1 banded score formula:
                # contract_weight * (1 + activity_priority) * overrun_days, summed per overrunning activity across the contract
                tier_weight = 100.0 if contract.contract_priority == 1 else (10.0 if contract.contract_priority == 2 else 1.0)
                contract_acts = [a for a in self.dm.activities.values() if a.contract_number == cid]
                for ca in contract_acts:
                    nudge = 0.3 if ca.activity_priority == 1 else (0.2 if ca.activity_priority == 2 else 0.0)
                    priority_weighted_score += tier_weight * (1.0 + nudge) * overrun

                if scenario == "B":
                    violations.append({
                        "rule": "planned_date",
                        "severity": "hard",
                        "detail": f"Contract {cid} overruns planned completion date by {overrun} days ({sim_date_str} > {contract.planned_completion_date})",
                    })

            # Check RESULTS.csv match
            res_row = results_df[results_df["contract_number"] == cid]
            if res_row.empty:
                violations.append({
                    "rule": "schema",
                    "severity": "hard",
                    "detail": f"RESULTS.csv missing entry for contract {cid}",
                })
            else:
                rep_date = str(res_row["simulated_completion_date"].values[0]).strip()
                rep_overrun = int(res_row["overrun_days"].values[0])
                if rep_date != sim_date_str or rep_overrun != overrun:
                    violations.append({
                        "rule": "schema",
                        "severity": "hard",
                        "detail": f"Contract {cid} RESULTS.csv mismatch: reported (date={rep_date}, overrun={rep_overrun}) vs computed (date={sim_date_str}, overrun={overrun})",
                    })

        return {
            "overrun_days_total": overrun_days_total,
            "contracts_overrunning": contracts_overrunning,
            "earliness_days_total": earliness_days_total,
            "priority_overrun": priority_overrun,
            "priority_weighted_score": round(priority_weighted_score, 2),
        }

    def _compute_soft_scores(
        self,
        scenario: str,
        overrun_summary: Dict[str, Any],
        excess_total: int,
        eclo_nights: int,
        feasible: bool,
    ) -> Dict[str, Any]:
        pws = overrun_summary["priority_weighted_score"]
        scores: Dict[str, Any] = {
            "scenario": scenario,
            "overrun_days_total": overrun_summary["overrun_days_total"],
            "contracts_overrunning": overrun_summary["contracts_overrunning"],
            "earliness_days_total": overrun_summary["earliness_days_total"],
            "excess_access_nights_total": excess_total,
            "eclo_nights_total": eclo_nights,
            "priority_overrun": overrun_summary["priority_overrun"],
            "priority_weighted_score": pws,
        }

        if feasible:
            if scenario == "A":
                scores["objective_score"] = round(pws, 2)
            elif scenario == "B":
                scores["objective_score"] = round(7 * excess_total + 5 * eclo_nights, 2)
            elif scenario == "C":
                scores["objective_score"] = round(pws + 7 * excess_total + 5 * eclo_nights, 2)
            scores["formula_version"] = "v1.0"

        return scores


def main():
    parser = argparse.ArgumentParser(description="Railway Track Access Schedule Validator")
    parser.add_argument("--data-dir", required=True, help="Directory containing the 8 instance CSVs")
    parser.add_argument("--submission-dir", required=True, help="Directory containing SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv, RESULTS.csv")
    parser.add_argument("--scenario", required=True, choices=["A", "B", "C"], help="Scenario A, B, or C")
    parser.add_argument("--json", action="store_true", help="Output pure JSON")
    args = parser.parse_args()

    validator = Validator(args.data_dir)
    report = validator.validate(args.submission_dir, args.scenario)

    if args.json or True:
        print(json.dumps(report, indent=2))

    sys.exit(0 if report["feasible"] else 1)


if __name__ == "__main__":
    main()
