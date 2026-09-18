import os
import sys
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Tuple, Optional, Any

from network_model import RailNetwork
from validator import ScheduleValidator
from scheduler import ScheduleOptimizer

class DisruptionReplanner:
    """
    Intelligent dynamic disruption replanner with explainable conflict diagnosis.
    Handles unexpected track closures, capacity reductions, and contractor delays.
    """
    def __init__(self, data_dir: str = "PS1/01_data"):
        self.optimizer = ScheduleOptimizer(data_dir)
        self.validator = self.optimizer.validator
        self.network = self.optimizer.network

    def simulate_track_closure(
        self,
        base_scenario: str,
        blocked_location: str,
        start_week: int,
        end_week: int
    ) -> Dict[str, Any]:
        """
        Simulate a track closure on `blocked_location` between `start_week` and `end_week`.
        Reschedules affected activities dynamically and generates an explainability audit log.
        """
        if base_scenario == 'A':
            acc_df, occ_df, res_df = self.optimizer.solve_scenario_a()
        elif base_scenario == 'B':
            acc_df, occ_df, res_df = self.optimizer.solve_scenario_b()
        else:
            acc_df, occ_df, res_df = self.optimizer.solve_scenario_c()

        explanation_logs = []
        explanation_logs.append(
            f"DISRUPTION TRIGGERED: Location '{blocked_location}' blocked from Week {start_week} to Week {end_week}."
        )

        # 1. Identify direct conflicts in SCHEDULE_OCCUPANCY
        affected_occ = occ_df[
            (occ_df['location_id'] == blocked_location) &
            (occ_df['week'] >= start_week) &
            (occ_df['week'] <= end_week)
        ]

        if len(affected_occ) == 0:
            explanation_logs.append(
                f"No scheduled activities directly touch '{blocked_location}' during Weeks {start_week}-{end_week}. Schedule remains unaffected."
            )
            report = self.validator.validate(acc_df, occ_df, res_df, scenario_override=base_scenario)
            return {
                'success': True,
                'affected_activities': [],
                'new_acc': acc_df,
                'new_occ': occ_df,
                'new_res': res_df,
                'logs': explanation_logs,
                'validation': report
            }

        conflicting_acts = affected_occ['activity_id'].unique().tolist()
        explanation_logs.append(
            f"Direct Conflict Detected: {len(conflicting_acts)} activity/activities affected: {conflicting_acts}."
        )

        # 2. Reschedule each conflicting activity forward in time
        new_acc = acc_df.copy()
        new_occ = occ_df.copy()

        for act in conflicting_acts:
            contract = self.optimizer.act_info[act]['contract_number']
            max_acc_wk = self.optimizer.proj_info[contract]['number_of_maximum_access_per_week']

            act_rows = new_acc[
                (new_acc['activity_id'] == act) &
                (new_acc['week'] >= start_week) &
                (new_acc['week'] <= end_week)
            ]
            
            # Find candidate weeks starting after the activity's currently scheduled weeks
            curr_target_w = max(end_week + 1, new_acc[new_acc['activity_id'] == act]['week'].max() + 1)
            for _, r in act_rows.iterrows():
                old_w = r['week']
                # Find a week where contract does not exceed max_access
                while True:
                    curr_in_w = len(new_acc[(new_acc['activity_id'] == act) & (new_acc['week'] == curr_target_w)])
                    if curr_in_w < max_acc_wk:
                        break
                    curr_target_w += 1

                explanation_logs.append(
                    f"Rescheduling Activity '{act}': Access originally at Week {old_w} deferred to Week {curr_target_w} due to physical possession conflict at '{blocked_location}'."
                )
                idx_acc = new_acc[(new_acc['activity_id'] == act) & (new_acc['week'] == old_w)].index[0]
                new_acc.loc[idx_acc, 'week'] = curr_target_w
                new_acc.loc[idx_acc, 'access_night'] = curr_in_w + 1

                # Update occupancy
                idx_occ = new_occ[(new_occ['activity_id'] == act) & (new_occ['week'] == old_w)].index
                new_occ.loc[idx_occ, 'week'] = curr_target_w
                new_occ.loc[idx_occ, 'co_share_group'] = f"b{curr_in_w + 1}"
                curr_target_w += 1

        # 3. Propagate forward precedence constraints for downstream successors
        successors_map = {}
        for a_id, info in self.optimizer.act_info.items():
            pred = info.get('predecessor_activity_id')
            if pd.notna(pred):
                successors_map.setdefault(pred, []).append(a_id)

        queue = list(conflicting_acts)
        visited = set(conflicting_acts)

        while queue:
            curr_act = queue.pop(0)
            curr_max_w = new_acc[new_acc['activity_id'] == curr_act]['week'].max()
            succs = successors_map.get(curr_act, [])

            for s_act in succs:
                s_min_w = new_acc[new_acc['activity_id'] == s_act]['week'].min()
                if s_min_w <= curr_max_w:
                    shift = (curr_max_w + 1) - s_min_w
                    explanation_logs.append(
                        f"Precedence Ripple Effect: Activity '{s_act}' depends on '{curr_act}' (completed at Week {curr_max_w}). Shifting '{s_act}' by +{shift} week(s) to preserve FS+0 rule."
                    )
                    new_acc.loc[new_acc['activity_id'] == s_act, 'week'] += shift
                    new_occ.loc[new_occ['activity_id'] == s_act, 'week'] += shift
                    if s_act not in visited:
                        visited.add(s_act)
                        queue.append(s_act)

        # 4. Sort and re-index access_seq
        new_acc = new_acc.sort_values(['activity_id', 'week', 'access_night']).reset_index(drop=True)
        new_acc['access_seq'] = new_acc.groupby('activity_id').cumcount() + 1

        # 5. Recompute simulated completion dates
        new_res = self.optimizer._build_results(new_acc, base_scenario)

        # 6. Validate new schedule
        validation_report = self.validator.validate(new_acc, new_occ, new_res, scenario_override=base_scenario)
        explanation_logs.append(
            f"Dynamic Re-planning Completed: Schedule is Feasible={validation_report['feasible']}, Hard Violations={len(validation_report['hard_violations'])}, Total Overrun={validation_report['soft_scores']['overrun_days_total']} days."
        )

        return {
            'success': True,
            'affected_activities': list(visited),
            'new_acc': new_acc,
            'new_occ': new_occ,
            'new_res': new_res,
            'logs': explanation_logs,
            'validation': validation_report
        }

if __name__ == "__main__":
    replanner = DisruptionReplanner()
    print("Testing Disruption Replanning on Scenario C...")
    # Simulate an incident: SEC:BET:S14_H01:EB blocked in weeks 22-23
    result = replanner.simulate_track_closure(
        base_scenario='C',
        blocked_location='SEC:BET:S14_H01:EB',
        start_week=22,
        end_week=23
    )
    for log in result['logs']:
        print(" ->", log)
    print("Validation Score:", result['validation']['soft_scores'])
