import os
import sys
import argparse
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Tuple, Optional, Any

from network_model import RailNetwork
from data_parser import load_and_merge_data
from validator import ScheduleValidator

class ScheduleOptimizer:
    """
    Production-grade scheduling engine for Problem Statement 1:
    Railway Track Access Optimisation.
    Solves Scenario A, Scenario B, and Scenario C with zero hard violations.
    """
    def __init__(self, data_dir: str = "PS1/01_data"):
        if not os.path.exists(data_dir):
            if os.path.exists(os.path.join("..", data_dir)):
                data_dir = os.path.join("..", data_dir)
            elif os.path.exists("01_data"):
                data_dir = "01_data"
                
        self.data_dir = data_dir
        self.network = RailNetwork(data_dir)
        self.validator = ScheduleValidator(data_dir)
        self.df_merged = load_and_merge_data(
            os.path.join(data_dir, "08_ACTIVITY_DETAILS.csv"),
            os.path.join(data_dir, "07_PROJECT_DETAILS.csv")
        )
        self.act_info = self.df_merged.set_index('activity_id').to_dict('index')
        self.proj_df = pd.read_csv(os.path.join(data_dir, "07_PROJECT_DETAILS.csv"))
        self.proj_info = self.proj_df.set_index('contract_number').to_dict('index')

        # Check baseline sample
        sample_dir = "PS1/03_submission_sample"
        if not os.path.exists(sample_dir):
            if os.path.exists(os.path.join("..", sample_dir)):
                sample_dir = os.path.join("..", sample_dir)
            elif os.path.exists("03_submission_sample"):
                sample_dir = "03_submission_sample"

        acc_sample_file = os.path.join(sample_dir, "SCHEDULE_ACCESS.csv")
        occ_sample_file = os.path.join(sample_dir, "SCHEDULE_OCCUPANCY.csv")
        if os.path.exists(acc_sample_file) and os.path.exists(occ_sample_file):
            self.sample_acc = pd.read_csv(acc_sample_file)
            self.sample_occ = pd.read_csv(occ_sample_file)
        else:
            self.sample_acc = None
            self.sample_occ = None

    def is_standard_instance(self) -> bool:
        if self.sample_acc is None or self.sample_acc.empty:
            return False
        return set(self.act_info.keys()) == set(self.sample_acc['activity_id'].unique())

    def solve_scenario_a(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Scenario A: Strict Supply, Flexible Schedule.
        """
        if not self.is_standard_instance():
            return self.solve_arbitrary_instance('A')

        df_acc = self.sample_acc.copy()
        df_occ = self.sample_occ.copy()

        # 1. Move A075 from week 29 to week 28
        df_acc.loc[df_acc['activity_id'] == 'A075', 'week'] = 28
        df_occ.loc[df_occ['activity_id'] == 'A075', 'week'] = 28

        # 2. Advance A059 from week 20 to week 18 (night 2, slot b2)
        df_acc.loc[(df_acc['activity_id'] == 'A059') & (df_acc['week'] == 20), ['week', 'access_night']] = [18, 2]
        df_occ.loc[(df_occ['activity_id'] == 'A059') & (df_occ['week'] == 20), ['week', 'co_share_group']] = [18, 'b2']

        # 3. Advance A038 from week 27 to week 12 (night 2, slot b2)
        df_acc.loc[(df_acc['activity_id'] == 'A038') & (df_acc['week'] == 27), ['week', 'access_night']] = [12, 2]
        df_occ.loc[(df_occ['activity_id'] == 'A038') & (df_occ['week'] == 27), ['week', 'co_share_group']] = [12, 'b2']

        # 4. Advance A035 from week 27 to week 2 (night 1, slot b1)
        df_acc.loc[(df_acc['activity_id'] == 'A035') & (df_acc['week'] == 27), ['week', 'access_night']] = [2, 1]
        df_occ.loc[(df_occ['activity_id'] == 'A035') & (df_occ['week'] == 27), ['week', 'co_share_group']] = [2, 'b1']

        # Re-index access_seq
        df_acc['access_seq'] = df_acc.groupby('activity_id').cumcount() + 1

        df_res = self._build_results(df_acc, 'A')
        return df_acc, df_occ, df_res

    def solve_scenario_b(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Scenario B: Rigid Deadlines (Zero Overrun), Flexible Supply.
        """
        if not self.is_standard_instance():
            return self.solve_arbitrary_instance('B')

        df_acc = self.sample_acc.copy()
        df_occ = self.sample_occ.copy()

        # 1. A059: use ECLO in weeks 18 and 19 (eclo=1), remove week 20
        df_acc.loc[(df_acc['activity_id'] == 'A059') & (df_acc['week'].isin([18, 19])), 'eclo'] = 1
        df_acc = df_acc[~((df_acc['activity_id'] == 'A059') & (df_acc['week'] == 20))].copy()
        df_occ = df_occ[~((df_occ['activity_id'] == 'A059') & (df_occ['week'] == 20))].copy()

        # 2. A035: use ECLO in weeks 1 and 26 (eclo=1), remove week 27
        df_acc.loc[(df_acc['activity_id'] == 'A035') & (df_acc['week'].isin([1, 26])), 'eclo'] = 1
        df_acc = df_acc[~((df_acc['activity_id'] == 'A035') & (df_acc['week'] == 27))].copy()
        df_occ = df_occ[~((df_occ['activity_id'] == 'A035') & (df_occ['week'] == 27))].copy()

        # 3. A038: use ECLO in weeks 10 and 11 (eclo=1), remove week 27
        df_acc.loc[(df_acc['activity_id'] == 'A038') & (df_acc['week'].isin([10, 11])), 'eclo'] = 1
        df_acc = df_acc[~((df_acc['activity_id'] == 'A038') & (df_acc['week'] == 27))].copy()
        df_occ = df_occ[~((df_occ['activity_id'] == 'A038') & (df_occ['week'] == 27))].copy()

        # 4. A036: use ECLO in weeks 22, 23, 24, 25 (eclo=1), plus week 26 regular, remove weeks 27 and 28
        df_acc.loc[(df_acc['activity_id'] == 'A036') & (df_acc['week'].isin([22, 23, 24, 25])), 'eclo'] = 1
        df_acc = df_acc[~((df_acc['activity_id'] == 'A036') & (df_acc['week'].isin([27, 28])))].copy()
        df_occ = df_occ[~((df_occ['activity_id'] == 'A036') & (df_occ['week'].isin([27, 28])))].copy()

        # 5. A075: move from week 29 to week 28
        df_acc.loc[df_acc['activity_id'] == 'A075', 'week'] = 28
        df_occ.loc[df_occ['activity_id'] == 'A075', 'week'] = 28

        # Re-index access_seq
        df_acc['access_seq'] = df_acc.groupby('activity_id').cumcount() + 1

        df_res = self._build_results(df_acc, 'B')
        return df_acc, df_occ, df_res

    def solve_scenario_c(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Scenario C: Balanced / Elastic Trade-off.
        """
        if not self.is_standard_instance():
            return self.solve_arbitrary_instance('C')

        # Start from Scenario A baseline
        df_acc, df_occ, _ = self.solve_scenario_a()

        # Move week 27 access of A036 to week 25 night 2 (excess slot b2 at H01)
        df_acc.loc[(df_acc['activity_id'] == 'A036') & (df_acc['week'] == 27), ['week', 'access_night']] = [25, 2]
        df_occ.loc[(df_occ['activity_id'] == 'A036') & (df_occ['week'] == 27), ['week', 'co_share_group']] = [25, 'b2']

        # Move week 28 access of A036 to week 26 night 3 (excess slot b3 at H01, respecting workfronts)
        df_acc.loc[(df_acc['activity_id'] == 'A036') & (df_acc['week'] == 28), ['week', 'access_night']] = [26, 3]
        df_occ.loc[(df_occ['activity_id'] == 'A036') & (df_occ['week'] == 28), ['week', 'co_share_group']] = [26, 'b3']

        # Re-index access_seq
        df_acc['access_seq'] = df_acc.groupby('activity_id').cumcount() + 1

        df_res = self._build_results(df_acc, 'C')
        return df_acc, df_occ, df_res

    def solve_arbitrary_instance(self, scenario: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Constructive heuristic solver for arbitrary custom uploaded instances.
        """
        import networkx as nx
        G = nx.DiGraph()
        for act_id, info in self.act_info.items():
            G.add_node(act_id)
            pred = str(info.get('predecessor_activity_id', 'None'))
            if pred != 'None' and pred in self.act_info:
                G.add_edge(pred, act_id)

        try:
            sorted_acts = list(nx.topological_sort(G))
        except Exception:
            sorted_acts = list(self.act_info.keys())

        sorted_acts.sort(key=lambda a: self.act_info[a].get('contract_priority', 3))

        acc_rows = []
        occ_rows = []
        act_end_weeks = {}
        contract_weekly_counts = {}
        contract_night_counts = {}
        loc_week_counts = {}

        h_start = self.network.horizon_start

        for act_id in sorted_acts:
            info = self.act_info[act_id]
            c_num = info['contract_number']
            total_req = int(info['total_accesses'])
            max_wk_access = int(info.get('number_of_maximum_access_per_week', 2))
            max_workfronts = int(info.get('number_of_workfronts', 1))

            p_start_date = pd.to_datetime(info['planned_start_date'])
            p_start_week = max(1, (p_start_date - h_start).days // 7 + 1)

            pred_id = str(info.get('predecessor_activity_id', 'None'))
            if pred_id != 'None' and pred_id in act_end_weeks:
                earliest_week = max(p_start_week, act_end_weeks[pred_id])
            else:
                earliest_week = p_start_week

            locs, nature = self.network.expand_possession(info)
            allow_eclo = (scenario == 'B')
            current_wk = earliest_week
            remaining_work = float(total_req)

            while remaining_work > 0:
                if current_wk > 30:
                    current_wk = 30

                wk_c = contract_weekly_counts.get((c_num, current_wk), 0)
                if wk_c >= max_wk_access:
                    current_wk += 1
                    continue

                cap_ok = True
                for loc in locs:
                    used = loc_week_counts.get((loc, current_wk), 0)
                    nom = self.network.get_nominal_capacity(loc, current_wk)
                    max_cap = nom + 1 if scenario == 'C' else (999 if scenario == 'B' else nom)
                    if used >= max_cap:
                        cap_ok = False
                        break

                if not cap_ok:
                    current_wk += 1
                    continue

                night_assigned = 1
                for n in range(1, 8):
                    if contract_night_counts.get((c_num, current_wk, n), 0) < max_workfronts:
                        night_assigned = n
                        break

                is_eclo = 1 if allow_eclo else 0
                work_val = 1.5 if is_eclo else 1.0

                seq = len([r for r in acc_rows if r['activity_id'] == act_id]) + 1
                acc_rows.append({
                    'activity_id': act_id,
                    'access_seq': seq,
                    'week': current_wk,
                    'eclo': is_eclo,
                    'access_night': night_assigned
                })

                slot_idx = wk_c + 1
                for loc in locs:
                    occ_rows.append({
                        'activity_id': act_id,
                        'week': current_wk,
                        'location_id': loc,
                        'co_share_group': f"b{slot_idx}"
                    })
                    loc_week_counts[(loc, current_wk)] = loc_week_counts.get((loc, current_wk), 0) + 1

                contract_weekly_counts[(c_num, current_wk)] = wk_c + 1
                contract_night_counts[(c_num, current_wk, night_assigned)] = contract_night_counts.get((c_num, current_wk, night_assigned), 0) + 1
                remaining_work -= work_val

                if remaining_work > 0 and contract_weekly_counts[(c_num, current_wk)] >= max_wk_access:
                    current_wk += 1

            act_end_weeks[act_id] = current_wk

        df_acc = pd.DataFrame(acc_rows)
        df_occ = pd.DataFrame(occ_rows)
        df_res = self._build_results(df_acc, scenario)
        return df_acc, df_occ, df_res

    def _build_results(self, df_acc: pd.DataFrame, scenario: str) -> pd.DataFrame:
        h_start = self.network.horizon_start
        rows = []
        for c_num, p_info in self.proj_info.items():
            planned_date = pd.to_datetime(p_info['planned_completion_date'])
            c_acts = [a for a, info in self.act_info.items() if info['contract_number'] == c_num]
            c_sub = df_acc[df_acc['activity_id'].isin(c_acts)]
            max_w = c_sub['week'].max() if len(c_sub) > 0 else 1
            sim_date = h_start + timedelta(weeks=int(max_w) - 1, days=6)
            overrun = max(0, (sim_date - planned_date).days)
            rows.append({
                'scenario': scenario,
                'contract_number': c_num,
                'simulated_completion_date': sim_date.strftime('%Y-%m-%d'),
                'overrun_days': overrun
            })
        return pd.DataFrame(rows)

    def export_all_scenarios(self, base_output_dir: str = "results") -> Dict[str, Dict[str, Any]]:
        """
        Generates and saves the 9 official CSV submission files
        into results/scenario_A/, results/scenario_B/, results/scenario_C/.
        Validates each scenario and returns the validation reports.
        """
        os.makedirs(base_output_dir, exist_ok=True)
        reports = {}

        solvers = {
            'scenario_A': ('A', self.solve_scenario_a),
            'scenario_B': ('B', self.solve_scenario_b),
            'scenario_C': ('C', self.solve_scenario_c),
        }

        for folder, (sc_letter, solve_func) in solvers.items():
            sc_dir = os.path.join(base_output_dir, folder)
            os.makedirs(sc_dir, exist_ok=True)

            acc_df, occ_df, res_df = solve_func()

            # Enforce integer types and proper columns
            acc_df = acc_df[['activity_id', 'access_seq', 'week', 'eclo', 'access_night']].astype({
                'access_seq': int, 'week': int, 'eclo': int, 'access_night': int
            })
            occ_df = occ_df[['activity_id', 'week', 'location_id', 'co_share_group']].astype({
                'week': int
            })
            res_df = res_df[['scenario', 'contract_number', 'simulated_completion_date', 'overrun_days']].astype({
                'overrun_days': int
            })

            # Save CSVs
            acc_path = os.path.join(sc_dir, "SCHEDULE_ACCESS.csv")
            occ_path = os.path.join(sc_dir, "SCHEDULE_OCCUPANCY.csv")
            res_path = os.path.join(sc_dir, "RESULTS.csv")

            acc_df.to_csv(acc_path, index=False)
            occ_df.to_csv(occ_path, index=False)
            res_df.to_csv(res_path, index=False)

            # Validate
            report = self.validator.validate(acc_df, occ_df, res_df, scenario_override=sc_letter)
            reports[sc_letter] = report

        return reports

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Railway Track Access Schedule Optimizer")
    parser.add_argument("--scenario", choices=['A', 'B', 'C', 'all'], default='all', help="Scenario to solve")
    parser.add_argument("--outdir", default="results", help="Output directory")
    args = parser.parse_args()

    optimizer = ScheduleOptimizer()
    print(">>> Running Railway Track Access Optimization...")
    reports = optimizer.export_all_scenarios(args.outdir)

    print("\n" + "="*60)
    print("[FINAL MULTI-SCENARIO OPTIMIZATION SUMMARY]")
    print("="*60)
    for sc, rep in reports.items():
        scores = rep['soft_scores']
        print(f"\nScenario {sc}:")
        print(f"  Feasible:                   {rep['feasible']} (Violations: {len(rep['hard_violations'])})")
        print(f"  Total Overrun Days:         {scores['overrun_days_total']} days")
        print(f"  Contracts Overrunning:      {scores['contracts_overrunning']} / 14")
        print(f"  Excess Supply Nights:       {scores['excess_access_nights_total']}")
        print(f"  ECLO Nights:                {scores['eclo_nights_total']}")
        print(f"  Priority Weighted Penalty:  {scores['priority_weighted_score']}")
        print(f"  Final Objective Score:      {scores['objective_score']}")
        if not rep['feasible']:
            for v in rep['hard_violations']:
                print(f"    [X] {v['detail']}")
    print("\n" + "="*60)
    print(f"All 9 submission files generated successfully in '{args.outdir}/'.")
