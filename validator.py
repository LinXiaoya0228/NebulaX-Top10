import os
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from network_model import RailNetwork
from data_parser import load_and_merge_data

class ScheduleValidator:
    """
    Official 10-rule schedule validator for Problem Statement 1.
    Evaluates feasibility (hard rules) and calculates soft optimization penalties.
    """
    def __init__(self, data_dir: str = "PS1/01_data"):
        if not os.path.exists(data_dir):
            if os.path.exists(os.path.join("..", data_dir)):
                data_dir = os.path.join("..", data_dir)
            elif os.path.exists("01_data"):
                data_dir = "01_data"
                
        self.data_dir = data_dir
        self.network = RailNetwork(data_dir)
        self.df_merged = load_and_merge_data(
            os.path.join(data_dir, "08_ACTIVITY_DETAILS.csv"),
            os.path.join(data_dir, "07_PROJECT_DETAILS.csv")
        )
        self.act_info = self.df_merged.set_index('activity_id').to_dict('index')
        self.proj_df = pd.read_csv(os.path.join(data_dir, "07_PROJECT_DETAILS.csv"))
        self.proj_info = self.proj_df.set_index('contract_number').to_dict('index')

    def validate(
        self,
        schedule_access: Union[str, pd.DataFrame],
        schedule_occupancy: Union[str, pd.DataFrame],
        results: Union[str, pd.DataFrame],
        scenario_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate submission files against the 10 domain rules.
        Returns a dict matching §2.7 of PS1_README.md.
        """
        # 1. Load DataFrames
        df_acc = pd.read_csv(schedule_access) if isinstance(schedule_access, str) else schedule_access.copy()
        df_occ = pd.read_csv(schedule_occupancy) if isinstance(schedule_occupancy, str) else schedule_occupancy.copy()
        df_res = pd.read_csv(results) if isinstance(results, str) else results.copy()

        # Clean string columns
        for c in ['activity_id']:
            if c in df_acc.columns: df_acc[c] = df_acc[c].astype(str).str.strip()
            if c in df_occ.columns: df_occ[c] = df_occ[c].astype(str).str.strip()
        if 'contract_number' in df_res.columns:
            df_res['contract_number'] = df_res['contract_number'].astype(str).str.strip()
        if 'location_id' in df_occ.columns:
            df_occ['location_id'] = df_occ['location_id'].astype(str).str.strip()
        if 'co_share_group' in df_occ.columns:
            df_occ['co_share_group'] = df_occ['co_share_group'].astype(str).str.strip()

        scenario = scenario_override or (df_res['scenario'].iloc[0] if 'scenario' in df_res.columns and len(df_res) > 0 else 'A')

        hard_violations = []

        # ==========================================
        # RULE 1: Workload Conservation
        # ==========================================
        df_acc['work_units'] = df_acc['eclo'].apply(lambda x: 1.5 if x == 1 else 1.0)
        units_by_act = df_acc.groupby('activity_id')['work_units'].sum().to_dict()

        for act_id, info in self.act_info.items():
            required = info['total_accesses']
            actual = units_by_act.get(act_id, 0.0)
            if actual < required:
                hard_violations.append({
                    "rule": "workload",
                    "severity": "hard",
                    "detail": f"Activity {act_id} incomplete: scheduled {actual} / {required} work units"
                })

        # ==========================================
        # RULE 2: Planned Start Date
        # ==========================================
        h_start = self.network.horizon_start
        min_week_by_act = df_acc.groupby('activity_id')['week'].min().to_dict()
        max_week_by_act = df_acc.groupby('activity_id')['week'].max().to_dict()

        for act_id, info in self.act_info.items():
            p_start_date = pd.to_datetime(info['planned_start_date'])
            planned_start_week = (p_start_date - h_start).days // 7 + 1
            act_min_week = min_week_by_act.get(act_id)
            if act_min_week is not None and act_min_week < planned_start_week:
                hard_violations.append({
                    "rule": "start_date",
                    "severity": "hard",
                    "detail": f"Activity {act_id} starts in week {act_min_week} before planned start week {planned_start_week}"
                })

        # ==========================================
        # RULE 3: Predecessor Precedence (FS+0)
        # ==========================================
        for act_id, info in self.act_info.items():
            pred = info.get('predecessor_activity_id')
            if pd.notna(pred) and str(pred).strip():
                pred = str(pred).strip()
                p_max = max_week_by_act.get(pred)
                s_min = min_week_by_act.get(act_id)
                if p_max is not None and s_min is not None:
                    if s_min <= p_max:
                        hard_violations.append({
                            "rule": "predecessor",
                            "severity": "hard",
                            "detail": f"Activity {act_id} (wk {s_min}) starts before predecessor {pred} finished (wk {p_max})"
                        })

        # ==========================================
        # RULE 7: Weekly Allocation Budget
        # ==========================================
        # Distinct access_night per contract per week <= number_of_maximum_access_per_week
        acc_with_contract = df_acc.copy()
        acc_with_contract['contract_number'] = acc_with_contract['activity_id'].map(lambda a: self.act_info[a]['contract_number'])
        
        for (c_num, wk), g in acc_with_contract.groupby(['contract_number', 'week']):
            max_alloc = self.proj_info[c_num]['number_of_maximum_access_per_week']
            distinct_nights = g['access_night'].nunique()
            if distinct_nights > max_alloc:
                hard_violations.append({
                    "rule": "weekly_allocation",
                    "severity": "hard",
                    "detail": f"Contract {c_num} in week {wk} used {distinct_nights} distinct nights, exceeding max allocation {max_alloc}"
                })

        # ==========================================
        # RULE 8: Workfronts
        # ==========================================
        # At most number_of_workfronts distinct activities per contract on the same access_night
        for (c_num, wk, night), g in acc_with_contract.groupby(['contract_number', 'week', 'access_night']):
            max_wf = self.proj_info[c_num]['number_of_workfronts']
            concurrent_acts = g['activity_id'].nunique()
            if concurrent_acts > max_wf:
                hard_violations.append({
                    "rule": "workfront",
                    "severity": "hard",
                    "detail": f"Contract {c_num} in week {wk} on night {night} had {concurrent_acts} concurrent activities, exceeding workfronts {max_wf}"
                })

        # ==========================================
        # RULE 5: Possession Locations & Legal Mixes
        # ==========================================
        # Per (week, location_id, co_share_group): 1 PM alone, or 1 PC + <=3 C, or <=4 C
        occ_with_type = df_occ.copy()
        occ_with_type['access_type'] = occ_with_type['activity_id'].map(lambda a: self.act_info[a]['access_type'])

        for (wk, loc, grp), g in occ_with_type.groupby(['week', 'location_id', 'co_share_group']):
            types = list(g['access_type'])
            pm_c = types.count('PM')
            pc_c = types.count('PC')
            c_c = types.count('C')
            if pm_c > 1 or (pm_c == 1 and (pc_c > 0 or c_c > 0)):
                hard_violations.append({
                    "rule": "legal_mix",
                    "severity": "hard",
                    "detail": f"Illegal mix at {loc} wk {wk} grp {grp}: PM cannot co-share with other activities ({types})"
                })
            elif pc_c > 1:
                hard_violations.append({
                    "rule": "legal_mix",
                    "severity": "hard",
                    "detail": f"Illegal mix at {loc} wk {wk} grp {grp}: Multiple PC activities ({types})"
                })
            elif pc_c == 1 and c_c > 3:
                hard_violations.append({
                    "rule": "legal_mix",
                    "severity": "hard",
                    "detail": f"Illegal mix at {loc} wk {wk} grp {grp}: PC with {c_c} > 3 co-workers ({types})"
                })
            elif pc_c == 0 and c_c > 4:
                hard_violations.append({
                    "rule": "legal_mix",
                    "severity": "hard",
                    "detail": f"Illegal mix at {loc} wk {wk} grp {grp}: {c_c} > 4 co-workers alone ({types})"
                })

        # ==========================================
        # RULE 9 & 10: ECLO Rules
        # ==========================================
        eclo_df = df_acc[df_acc['eclo'] == 1]
        eclo_nights_total = len(eclo_df)

        if scenario == 'A' and eclo_nights_total > 0:
            hard_violations.append({
                "rule": "eclo",
                "severity": "hard",
                "detail": f"Scenario A strictly forbids ECLO, but found {eclo_nights_total} ECLO nights scheduled"
            })
        elif scenario == 'C' and eclo_nights_total > 0:
            # ECLO Continuity Window: continuous span of at most 2 calendar weeks chosen independently per line
            eclo_merged = pd.merge(eclo_df, self.df_merged[['activity_id', 'start_location_id']], on='activity_id')
            eclo_merged['line'] = eclo_merged['start_location_id'].apply(lambda x: x.split(':')[1])
            
            for line, g in eclo_merged.groupby('line'):
                weeks = sorted(g['week'].unique())
                if len(weeks) > 0:
                    span = max(weeks) - min(weeks) + 1
                    if span > 2:
                        hard_violations.append({
                            "rule": "eclo",
                            "severity": "hard",
                            "detail": f"Scenario C ECLO on Line {line} spans {span} weeks ({weeks}), exceeding maximum continuous 2-week window"
                        })

        # ==========================================
        # RULE 10 (Capacity): Supply & Excess Capacity
        # ==========================================
        # Distinct co_share_group per location-week
        occ_counts = df_occ.groupby(['week', 'location_id'])['co_share_group'].nunique().reset_index()
        occ_counts['capacity'] = occ_counts['location_id'].map(self.network.location_capacity).fillna(4)
        occ_counts['excess'] = (occ_counts['co_share_group'] - occ_counts['capacity']).apply(lambda x: max(0, int(x)))

        excess_access_nights_total = int(occ_counts['excess'].sum())

        if scenario == 'A':
            over_cap = occ_counts[occ_counts['co_share_group'] > occ_counts['capacity']]
            for _, r in over_cap.iterrows():
                hard_violations.append({
                    "rule": "capacity",
                    "severity": "hard",
                    "detail": f"Capacity exceeded at {r['location_id']} wk {r['week']}: used {r['co_share_group']} > nominal supply {r['capacity']}"
                })
        elif scenario == 'C':
            over_cap = occ_counts[occ_counts['excess'] > 1]
            for _, r in over_cap.iterrows():
                hard_violations.append({
                    "rule": "capacity",
                    "severity": "hard",
                    "detail": f"Scenario C allows max 1 excess night per location-week, but {r['location_id']} wk {r['week']} has {r['excess']} excess"
                })

        # ==========================================
        # RESULTS.CSV Validation & Overrun Soft Scoring
        # ==========================================
        overrun_days_total = 0
        contracts_overrunning = 0
        earliness_days_total = 0
        priority_overrun = {"1": 0, "2": 0, "3": 0}
        priority_weighted_score = 0.0

        for _, r in df_res.iterrows():
            c_num = r['contract_number']
            sim_date = pd.to_datetime(r['simulated_completion_date'])
            overrun = int(r['overrun_days'])
            
            p_info = self.proj_info.get(c_num)
            if not p_info:
                continue
            planned_date = pd.to_datetime(p_info['planned_completion_date'])
            c_priority = p_info['contract_priority']

            # Check simulated date matches actual max week of scheduled activities
            c_acts = [a for a, info in self.act_info.items() if info['contract_number'] == c_num]
            c_acc = df_acc[df_acc['activity_id'].isin(c_acts)]
            if len(c_acc) > 0:
                act_max_w = c_acc['week'].max()
                expected_end_date = h_start + timedelta(weeks=int(act_max_w) - 1, days=6)
                if sim_date.date() != expected_end_date.date():
                    hard_violations.append({
                        "rule": "results",
                        "severity": "hard",
                        "detail": f"Contract {c_num} simulated completion date {sim_date.strftime('%Y-%m-%d')} does not match max week {act_max_w} end date {expected_end_date.strftime('%Y-%m-%d')}"
                    })
                expected_overrun = max(0, (expected_end_date - planned_date).days)
                if overrun != expected_overrun:
                    hard_violations.append({
                        "rule": "results",
                        "severity": "hard",
                        "detail": f"Contract {c_num} reported overrun {overrun} days != expected overrun {expected_overrun} days"
                    })
            else:
                expected_overrun = 0

            if overrun > 0:
                overrun_days_total += overrun
                contracts_overrunning += 1
                priority_overrun[str(c_priority)] = priority_overrun.get(str(c_priority), 0) + overrun
                
                # Activity nudge inside contract band
                # contract_weight * (1 + activity_priority) * overrun_days
                # Find the overrunning activity in this contract
                c_act_priorities = [self.act_info[a]['activity_priority'] for a in c_acts]
                avg_act_priority = min(c_act_priorities) if c_act_priorities else 2
                nudge = 0.3 if avg_act_priority == 1 else (0.2 if avg_act_priority == 2 else 0.0)
                tier_weight = 100 if c_priority == 1 else (10 if c_priority == 2 else 1)
                priority_weighted_score += tier_weight * (1.0 + nudge) * overrun

        # Scenario B hard requirement: zero overrun
        if scenario == 'B' and overrun_days_total > 0:
            hard_violations.append({
                "rule": "planned_date",
                "severity": "hard",
                "detail": f"Scenario B strictly requires zero overrun, but found {overrun_days_total} overrun days across {contracts_overrunning} contracts"
            })

        # Calculate combined objective score
        if scenario == 'A':
            objective_score = float(priority_weighted_score)
        elif scenario == 'B':
            objective_score = float(7 * excess_access_nights_total + 5 * eclo_nights_total)
        else: # Scenario C
            objective_score = float(priority_weighted_score + 7 * excess_access_nights_total + 5 * eclo_nights_total)

        feasible = (len(hard_violations) == 0)

        # Capacity hotspots
        hotspots = occ_counts[occ_counts['co_share_group'] >= occ_counts['capacity']][['week', 'location_id', 'co_share_group', 'capacity']].to_dict('records')

        return {
            "scenario": scenario,
            "feasible": feasible,
            "hard_violations": hard_violations,
            "soft_scores": {
                "scenario": scenario,
                "overrun_days_total": overrun_days_total,
                "contracts_overrunning": contracts_overrunning,
                "earliness_days_total": earliness_days_total,
                "excess_access_nights_total": excess_access_nights_total,
                "eclo_nights_total": eclo_nights_total,
                "priority_overrun": priority_overrun,
                "priority_weighted_score": round(priority_weighted_score, 2),
                "objective_score": round(objective_score, 2)
            },
            "detail": {
                "capacity_hotspots": hotspots,
                "nights_scheduled": len(df_acc),
                "eclo_nights": eclo_nights_total
            }
        }

if __name__ == "__main__":
    validator = ScheduleValidator()
    res = validator.validate(
        "PS1/03_submission_sample/SCHEDULE_ACCESS.csv",
        "PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv",
        "PS1/03_submission_sample/RESULTS.csv"
    )
    print("Validation Result for 03_submission_sample:")
    print("Feasible:", res["feasible"])
    print("Hard Violations:", len(res["hard_violations"]))
    if res["hard_violations"]:
        for v in res["hard_violations"]:
            print(" -", v)
    print("Soft Scores:", res["soft_scores"])
